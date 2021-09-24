"""Provide UI for configuring the integration"""

import logging
from typing import List

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries, data_entry_flow
from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry

from .const import (
    CONF_API_REQUEST_TIMEOUT,
    CONF_DEVICE_TRACKERS,
    CONF_NODE,
    CONF_SCAN_INTERVAL_DEVICE_TRACKER,
    DEF_API_REQUEST_TIMEOUT,
    DEF_NAME,
    DEF_CONSIDER_HOME,
    DEF_SCAN_INTERVAL,
    DEF_SCAN_INTERVAL_DEVICE_TRACKER,
    DOMAIN,
    STEP_DEVICE_TRACKERS,
    STEP_TIMERS,
    STEP_USER,
)
from pyvelop.device import Device
from pyvelop.exceptions import (
    MeshInvalidCredentials,
    MeshNodeNotPrimary,
    MeshBadResponse
)
from pyvelop.mesh import Mesh

_LOGGER = logging.getLogger(__name__)


async def _async_build_schema_with_user_input(step: str, user_input: dict, **kwargs) -> vol.Schema:
    """Build the input and validation schema for the config UI

    :param step: the step we're in for a configuration or installation of the integration
    :param user_input: the data that should be used as defaults
    :param kwargs: additional information that might be required
    :return: the schema including necessary restrictions, defaults, pre-selections etc.
    """

    schema = {}
    if step == STEP_USER:
        schema = {
            vol.Required(
                CONF_NODE,
                default=user_input.get(CONF_NODE, "")
            ): str,
            vol.Required(
                CONF_PASSWORD,
                default=user_input.get(CONF_PASSWORD, "")
            ): str,
        }
    elif step == STEP_TIMERS:
        schema = {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=user_input.get(CONF_SCAN_INTERVAL, DEF_SCAN_INTERVAL)
            ): cv.positive_int,
            vol.Required(
                CONF_SCAN_INTERVAL_DEVICE_TRACKER,
                default=user_input.get(
                    CONF_SCAN_INTERVAL_DEVICE_TRACKER,
                    DEF_SCAN_INTERVAL_DEVICE_TRACKER
                )
            ): cv.positive_int,
            vol.Required(
                CONF_CONSIDER_HOME,
                default=user_input.get(CONF_CONSIDER_HOME, DEF_CONSIDER_HOME)
            ): cv.positive_int,
        }
    elif step == STEP_DEVICE_TRACKERS:
        schema = {
            vol.Optional(
                CONF_DEVICE_TRACKERS,
                default=user_input.get(CONF_DEVICE_TRACKERS, [])
            ): cv.multi_select(kwargs["multi_select_contents"])
        }

    return vol.Schema(schema)


async def _async_get_devices(mesh: Mesh) -> dict:
    """Get the devices from the mesh for display purposes

    The device unique_id (as per the Mesh) is used as the key.

    :param mesh: the Mesh object
    :return: a dictionary containing the devices to present
    """

    ret: dict = {}

    devices: List[Device] = await mesh.async_get_devices()
    await mesh.close()
    devices = [device for device in devices if device.name != "Network Device"]
    for device in devices:
        for adapter in device.network:
            ret[device.unique_id] = f"{device.name} --> {adapter.get('mac')}"

    return ret


class LinksysVelopConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial install ConfigFlow"""

    task_login = None  # task for the potentially slow login process
    _mesh: Mesh  # mesh object for the class

    def __init__(self):
        """Constructor"""

        self._errors: dict = {}
        self._finish: bool = False
        self._options: dict = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler"""

        return LinksysOptionsFlowHandler(config_entry=config_entry)

    async def _async_task_login(self, user_input) -> None:
        """Login to the Mesh

        Sets the instance variable if successful

        :param user_input: details of the mesh as per the config UI
        :return: None
        """

        async with Mesh(**user_input) as mesh:
            try:
                await mesh.async_gather_details()
            except MeshInvalidCredentials:
                self._errors["base"] = "login_error"
            except MeshBadResponse:
                self._errors["base"] = "login_bad_response"
            except MeshNodeNotPrimary:
                self._errors["base"] = "node_not_primary"
            else:
                self._mesh = mesh

        self.hass.async_create_task(self.hass.config_entries.flow.async_configure(flow_id=self.flow_id))

    async def async_step_user(self, user_input=None) -> data_entry_flow.FlowResult:
        """Handle a flow initiated by the user"""

        if user_input is not None:
            self.task_login = None
            self._errors = {}
            self._options.update(user_input)
            return await self.async_step_login(user_input=user_input)

        return self.async_show_form(
            step_id=STEP_USER,
            data_schema=await _async_build_schema_with_user_input(STEP_USER, self._options),
            errors=self._errors
        )

    async def async_step_login(self, user_input=None) -> data_entry_flow.FlowResult:
        """Initiate the login task

        Shows the login task progress and then moves onto the next step, stays on the user step or
        aborts the process on unknown errors.

        :param user_input: details entered by the user
        :return: the necessary FlowResult
        """

        if not self.task_login:
            self.task_login = self.hass.async_create_task(
                self._async_task_login(user_input=dict(**user_input, **{"request_timeout": DEF_API_REQUEST_TIMEOUT}))
            )
            return self.async_show_progress(step_id="login", progress_action="task_login")

        # noinspection PyBroadException
        try:
            await self.task_login
        except Exception:
            return self.async_abort(reason="abort_login")

        if self._errors:
            return self.async_show_progress_done(next_step_id=STEP_USER)

        return self.async_show_progress_done(next_step_id=STEP_TIMERS)

    async def async_step_timers(self, user_input=None) -> data_entry_flow.FlowResult:
        """Allow the user to set the relevant timers for the integration"""

        if user_input is not None:
            self._errors = {}
            self._options.update(user_input, CONF_API_REQUEST_TIMEOUT=DEF_API_REQUEST_TIMEOUT)
            return await self.async_step_device_trackers()

        return self.async_show_form(
            step_id=STEP_TIMERS,
            data_schema=await _async_build_schema_with_user_input(STEP_TIMERS, self._options),
            errors=self._errors,
        )

    async def async_step_device_trackers(self, user_input=None) -> data_entry_flow.FlowResult:
        """Allow the user to select the device trackers for presence detection"""

        if user_input is not None:
            self._errors = {}
            self._options.update(user_input)
            return self.async_create_entry(title=DEF_NAME, data={}, options=self._options)

        devices: dict = await _async_get_devices(mesh=self._mesh)

        return self.async_show_form(
            step_id=STEP_DEVICE_TRACKERS,
            data_schema=await _async_build_schema_with_user_input(
                STEP_DEVICE_TRACKERS,
                self._options,
                multi_select_contents=devices
            ),
            errors=self._errors,
        )


class LinksysOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options from the configuration of the integration"""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Constructor"""

        super().__init__()
        self._config_entry = config_entry
        self._errors: dict = {}
        self._options: dict = dict(config_entry.options)

    async def async_step_init(self, user_input=None) -> data_entry_flow.FlowResult:
        """"""

        return await self.async_step_timers()

    async def async_step_device_trackers(self, user_input=None) -> data_entry_flow.FlowResult:
        """Manage the device trackers"""

        if user_input is not None:
            current_device_trackers: List = self._options.get(CONF_DEVICE_TRACKERS)

            # region #-- remove any device trackers that are no longer needed --#
            remove_device_trackers: set = set(current_device_trackers) - set(user_input.get(CONF_DEVICE_TRACKERS))
            if remove_device_trackers:
                er: entity_registry.EntityRegistry = await entity_registry.async_get_registry(self.hass)
                entities = entity_registry.async_entries_for_config_entry(er, self._config_entry.entry_id)
                remove_device_tracker_entities: List[entity_registry.RegistryEntry] = []
                for tracker in remove_device_trackers:
                    rdte = [
                        e
                        for e in entities
                        if e.unique_id == f"{self._config_entry.entry_id}::device_tracker::{tracker}"
                    ]
                    if rdte:
                        remove_device_tracker_entities.append(rdte[0])
                for entity in remove_device_tracker_entities:
                    er.async_remove(entity_id=entity.entity_id)
            # endregion

            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        mesh = Mesh(
            node=self._config_entry.options[CONF_NODE],
            password=self._config_entry.options[CONF_PASSWORD]
        )
        devices: dict = await _async_get_devices(mesh=mesh)

        return self.async_show_form(
            step_id=STEP_DEVICE_TRACKERS,
            data_schema=await _async_build_schema_with_user_input(
                STEP_DEVICE_TRACKERS,
                self._options,
                multi_select_contents=devices
            ),
            errors=self._errors,
        )

    async def async_step_timers(self, user_input=None) -> data_entry_flow.FlowResult:
        """Manage the timer options available for the integration"""

        if user_input is not None:
            if CONF_API_REQUEST_TIMEOUT not in self._options:
                self._options[CONF_API_REQUEST_TIMEOUT] = DEF_API_REQUEST_TIMEOUT
            self._options.update(user_input)
            return await self.async_step_device_trackers()

        return self.async_show_form(
            step_id=STEP_TIMERS,
            data_schema=await _async_build_schema_with_user_input(STEP_TIMERS, self._options),
            errors=self._errors,
        )
