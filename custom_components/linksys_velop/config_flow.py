"""Provide UI for configuring the integration."""

# region #-- imports --#
from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Mapping
from enum import StrEnum, auto
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries, data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.device_tracker import CONF_CONSIDER_HOME
from homeassistant.components.diagnostics import async_redact_data

# TODO: remove when setting minimum version to 2025.2.x or later
try:
    from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
except ImportError:
    from homeassistant.components.ssdp import SsdpServiceInfo

from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pyvelop.exceptions import (
    MeshBadResponse,
    MeshConnectionError,
    MeshException,
    MeshInvalidInput,
    MeshNodeNotPrimary,
    MeshTimeoutError,
)
from pyvelop.mesh import Mesh
from pyvelop.mesh_entity import DeviceEntity, NodeEntity

from . import LinksysVelopConfigEntry
from .const import (
    CONF_ALLOW_MESH_REBOOT,
    CONF_API_REQUEST_TIMEOUT,
    CONF_DEVICE_TRACKERS,
    CONF_DEVICE_TRACKERS_TO_REMOVE,
    CONF_EVENTS_OPTIONS,
    CONF_FLOW_NAME,
    CONF_NODE,
    CONF_NODE_IMAGES,
    CONF_SCAN_INTERVAL_DEVICE_TRACKER,
    CONF_SELECT_TEMP_UI_DEVICE,
    CONF_TITLE_PLACEHOLDERS,
    CONF_UI_DEVICES,
    CONF_UI_DEVICES_TO_REMOVE,
    DEF_ALLOW_MESH_REBOOT,
    DEF_API_CONFIG_FLOW_REQUEST_TIMEOUT,
    DEF_API_REQUEST_TIMEOUT,
    DEF_CONSIDER_HOME,
    DEF_EVENTS_OPTIONS,
    DEF_FLOW_NAME,
    DEF_SCAN_INTERVAL,
    DEF_SCAN_INTERVAL_DEVICE_TRACKER,
    DEF_SELECT_TEMP_UI_DEVICE,
    DEF_UI_PLACEHOLDER_DEVICE_ID,
    DOMAIN,
    ST_IGD,
)
from .helpers import async_get_integration_version
from .logger import Logger
from .types import EventSubTypes

# endregion


class Steps(StrEnum):
    """Define the steps vailable to the config flow."""

    ADVANCED_OPTIONS = auto()
    DEVICE_TRACKERS = auto()
    EVENTS = auto()
    FINALISE = auto()
    GATHER_DETAILS = auto()
    INIT = auto()
    LOGIN = auto()
    REAUTH_CONFIRM = auto()
    TIMERS = auto()
    UI_DEVICE = auto()
    USER = auto()


_LOGGER: logging.Logger = logging.getLogger(__name__)


def _is_mesh_by_host(hass: HomeAssistant, host: str) -> LinksysVelopConfigEntry | None:
    """Check if the given host is a Mesh."""
    current_entries = hass.config_entries.async_entries(DOMAIN)
    matching_entry = [
        config_entry
        for config_entry in current_entries
        if config_entry.options.get(CONF_NODE) == host
    ]
    if matching_entry:
        return matching_entry[0]

    return None


def _redact_for_display(data: Mapping) -> dict:
    """Redact information for display purposes."""

    to_redact: set[str] = {"password"}
    return async_redact_data(data, to_redact)


async def _async_build_schema_with_user_input(
    step: str, user_input: dict, **kwargs
) -> vol.Schema:
    """Build the input and validation schema for the config UI.

    :param step: the step we're in for a configuration or installation of the integration
    :param user_input: the data that should be used as defaults
    :param kwargs: additional information that might be required
    :return: the schema including necessary restrictions, defaults, pre-selections etc.
    """
    schema: vol.Schema = vol.Schema({})
    if step == Steps.ADVANCED_OPTIONS:
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NODE_IMAGES,
                    default=user_input.get(CONF_NODE_IMAGES, ""),
                ): selector.TextSelector(),
                vol.Required(
                    CONF_SELECT_TEMP_UI_DEVICE,
                    default=user_input.get(
                        CONF_SELECT_TEMP_UI_DEVICE, DEF_SELECT_TEMP_UI_DEVICE
                    ),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_ALLOW_MESH_REBOOT,
                    default=user_input.get(
                        CONF_ALLOW_MESH_REBOOT, DEF_ALLOW_MESH_REBOOT
                    ),
                ): selector.BooleanSelector(),
            }
        )
    elif step == Steps.DEVICE_TRACKERS:
        valid_trackers = [
            tracker
            for tracker in user_input.get(CONF_DEVICE_TRACKERS, [])
            if tracker in kwargs["multi_select_contents"]
        ]
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_DEVICE_TRACKERS, default=valid_trackers
                ): selector.SelectSelector(
                    config=selector.SelectSelectorConfig(
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        multiple=True,
                        options=[
                            {"label": label, "value": value}
                            for value, label in kwargs["multi_select_contents"].items()
                        ],
                    )
                )
            }
        )
    elif step == Steps.EVENTS:
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_EVENTS_OPTIONS,
                    default=user_input.get(CONF_EVENTS_OPTIONS, DEF_EVENTS_OPTIONS),
                ): selector.SelectSelector(
                    config=selector.SelectSelectorConfig(
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        multiple=True,
                        options=DEF_EVENTS_OPTIONS,
                        translation_key=CONF_EVENTS_OPTIONS,
                    )
                )
            }
        )
    elif step == Steps.REAUTH_CONFIRM:
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                ): selector.TextSelector(
                    config=selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD
                    )
                ),
            }
        )
    elif step == Steps.TIMERS:
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=user_input.get(CONF_SCAN_INTERVAL, DEF_SCAN_INTERVAL),
                ): selector.NumberSelector(
                    config=selector.NumberSelectorConfig(
                        min=0,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL_DEVICE_TRACKER,
                    default=user_input.get(
                        CONF_SCAN_INTERVAL_DEVICE_TRACKER,
                        DEF_SCAN_INTERVAL_DEVICE_TRACKER,
                    ),
                ): selector.NumberSelector(
                    config=selector.NumberSelectorConfig(
                        min=0,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_CONSIDER_HOME,
                    default=user_input.get(CONF_CONSIDER_HOME, DEF_CONSIDER_HOME),
                ): selector.NumberSelector(
                    config=selector.NumberSelectorConfig(
                        min=0,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_API_REQUEST_TIMEOUT,
                    default=user_input.get(
                        CONF_API_REQUEST_TIMEOUT, DEF_API_REQUEST_TIMEOUT
                    ),
                ): cv.positive_float,
            }
        )
    elif step == Steps.UI_DEVICE:
        valid_devices = [
            device
            for device in user_input.get(CONF_UI_DEVICES, [])
            if device in kwargs["multi_select_contents"]
        ]
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_UI_DEVICES, default=valid_devices
                ): selector.SelectSelector(
                    config=selector.SelectSelectorConfig(
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        multiple=True,
                        options=[
                            {"label": label, "value": value}
                            for value, label in kwargs["multi_select_contents"].items()
                        ],
                    )
                )
            }
        )
    elif step == Steps.USER:
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NODE, default=user_input.get(CONF_NODE, "")
                ): selector.TextSelector(),
                vol.Required(
                    CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                ): selector.TextSelector(
                    config=selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD
                    )
                ),
            }
        )

    return schema


async def _async_get_devices(mesh: Mesh) -> dict:
    """Get the devices from the mesh for display purposes.

    The device unique_id (as per the Mesh) is used as the key.

    :param mesh: the Mesh object
    :return: a dictionary containing the devices to present
    """
    ret: dict = {}

    devices: list[DeviceEntity] = await mesh.async_get_devices()
    for device in devices:
        for adapter in device.adapter_info:
            ret[device.unique_id] = f"{device.name} --> {adapter.get('mac')}"

    return ret


class LinksysVelopConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial installation ConfigFlow."""

    reauth_entry: LinksysVelopConfigEntry | None = None
    task_login: asyncio.Task | None = None
    task_gather: asyncio.Task | None = None
    _mesh: Mesh

    def __init__(self):
        """Initialise."""
        self._errors: dict = {}
        self._finish: bool = False
        self._options: dict = {}
        self._log_formatter: Logger = Logger()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: LinksysVelopConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return LinksysOptionsFlowHandler(config_entry=config_entry)

    def _set_error(self, exc: MeshException) -> None:
        """Set the error for the flow based on the exception received."""
        if isinstance(exc, MeshConnectionError):
            _LOGGER.debug(self._log_formatter.format("connection error"))
            self._errors["base"] = "connection_error"
        elif isinstance(exc, MeshBadResponse):
            _LOGGER.debug(self._log_formatter.format("bad response"))
            self._errors["base"] = "login_bad_response"
        elif isinstance(exc, MeshInvalidInput):
            _LOGGER.debug(self._log_formatter.format("invalid input"))
            _LOGGER.warning("%s", exc)
            self._errors["base"] = "invalid_input"
        elif isinstance(exc, MeshNodeNotPrimary):
            _LOGGER.debug(self._log_formatter.format("not primary"))
            self._errors["base"] = "node_not_primary"
        elif isinstance(exc, MeshTimeoutError):
            _LOGGER.debug(self._log_formatter.format("timeout"))
            self._errors["base"] = "node_timeout"
        else:
            _LOGGER.debug(self._log_formatter.format(f"{type(exc)} - {exc}"))
            self._errors["base"] = "general"

    async def _async_task_gather_details(self) -> None:
        """Gather the details about the Mesh."""
        _LOGGER.debug(self._log_formatter.format("entered"))
        try:
            await self._mesh.async_initialise()
        except MeshException as exc:
            self._set_error(exc)
        except Exception as exc:
            self._set_error(exc)
        else:
            _LOGGER.debug(self._log_formatter.format("no exceptions"))

        _LOGGER.debug(self._log_formatter.format("exited"))

    async def _async_task_login(self, details) -> None:
        """Test the credentials for the Mesh."""
        _LOGGER.debug(
            self._log_formatter.format("entered, details: %s"),
            _redact_for_display(details),
        )

        _mesh = Mesh(**details, session=async_get_clientsession(hass=self.hass))
        try:
            _LOGGER.debug(self._log_formatter.format("testing credentials"))
            valid: bool = await _mesh.async_test_credentials()
            _LOGGER.debug(self._log_formatter.format("credentials tested"))
            if not valid:
                _LOGGER.debug(self._log_formatter.format("credentials are not valid"))
                self._errors["base"] = "login_error"
            else:
                _LOGGER.debug(self._log_formatter.format("credentials are valid"))
                self._mesh = _mesh
        except MeshException as exc:
            self._set_error(exc)
        except Exception as exc:
            self._set_error(exc)
        else:
            _LOGGER.debug(self._log_formatter.format("no exceptions"))

        _LOGGER.debug(self._log_formatter.format("exited"))

    async def async_step_device_trackers(
        self, user_input=None
    ) -> data_entry_flow.FlowResult:
        """Allow the user to select the device trackers for presence detection."""
        _LOGGER.debug(self._log_formatter.format("entered, user_input: %s"), user_input)
        if user_input is not None:
            self._errors = {}
            self._options.update(user_input)
            return await self.async_step_finish()

        devices: dict = await _async_get_devices(mesh=self._mesh)

        return self.async_show_form(
            step_id=Steps.DEVICE_TRACKERS,
            data_schema=await _async_build_schema_with_user_input(
                Steps.DEVICE_TRACKERS, self._options, multi_select_contents=devices
            ),
            errors=self._errors,
            last_step=False,
        )

    async def async_step_finish(self) -> data_entry_flow.FlowResult:
        """Finalise the configuration entry."""
        _LOGGER.debug(self._log_formatter.format("entered"))
        _title = (
            self.context.get(CONF_TITLE_PLACEHOLDERS, {}).get(CONF_FLOW_NAME)
            or DEF_FLOW_NAME
        )
        return self.async_create_entry(title=_title, data={}, options=self._options)

    async def async_step_gather_details(
        self, user_input=None
    ) -> data_entry_flow.FlowResult:
        """Initiate gathering Mesh details."""
        _LOGGER.debug(self._log_formatter.format("entered, user_input: %s"), user_input)

        if self.task_gather is None:
            _LOGGER.debug(
                self._log_formatter.format("creating task for gathering details")
            )
            self.task_gather = self.hass.async_create_task(
                self._async_task_gather_details()
            )

        if self.task_gather.done():
            _LOGGER.debug(self._log_formatter.format("_errors: %s"), self._errors)
            next_step: str = Steps.TIMERS
            if self._errors:
                next_step = Steps.USER

            _LOGGER.debug(self._log_formatter.format("next step: %s"), next_step)
            return self.async_show_progress_done(next_step_id=next_step)

        return self.async_show_progress(
            step_id=Steps.GATHER_DETAILS,
            progress_action="task_gather_details",
            progress_task=self.task_gather,
        )

    async def async_step_login(self, user_input=None) -> data_entry_flow.FlowResult:
        """Initiate the credential test."""
        _LOGGER.debug(
            self._log_formatter.format("entered, user_input: %s"),
            _redact_for_display(user_input),
        )

        if self.task_login is None:
            _LOGGER.debug(self._log_formatter.format("creating credential test task"))
            details: dict = {
                "node": self._options.get(CONF_NODE),
                "password": self._options.get(CONF_PASSWORD),
                "request_timeout": DEF_API_CONFIG_FLOW_REQUEST_TIMEOUT,
            }
            self.task_login = self.hass.async_create_task(
                self._async_task_login(details)
            )

        if self.task_login.done():
            _LOGGER.debug(self._log_formatter.format("_errors: %s"), self._errors)
            next_step: str = Steps.GATHER_DETAILS
            if self._errors:
                next_step = Steps.USER

            _LOGGER.debug(self._log_formatter.format("next step: %s"), next_step)
            return self.async_show_progress_done(next_step_id=next_step)

        return self.async_show_progress(
            step_id=Steps.LOGIN,
            progress_action="task_login",
            progress_task=self.task_login,
        )

    async def async_step_reauth(self, user_input=None) -> data_entry_flow.FlowResult:
        """Manage reauthentication."""

        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input=None
    ) -> data_entry_flow.FlowResult:
        """Store the new auth details."""

        if user_input is not None:
            if self.reauth_entry:
                _options = dict(self.reauth_entry.options)
                _options.update(user_input)
                return self.async_update_reload_and_abort(
                    self.reauth_entry,
                    options=_options,
                )

        return self.async_show_form(
            step_id=Steps.REAUTH_CONFIRM,
            data_schema=await _async_build_schema_with_user_input(
                Steps.REAUTH_CONFIRM, self.reauth_entry.options
            ),
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> data_entry_flow.FlowResult:
        """Allow the Mesh primary node to be discovered via SSDP."""
        _LOGGER.debug(
            self._log_formatter.format("entered, discovery_info: %s"), discovery_info
        )

        # region #-- get the important info --#
        _host = discovery_info.ssdp_headers.get("_host", "")
        _manufacturer = discovery_info.upnp.get("manufacturer", "")
        _model = discovery_info.upnp.get("modelNumber", "")
        _model_description = discovery_info.upnp.get("modelDescription", "")
        _serial = discovery_info.upnp.get("serialNumber", "")
        # endregion

        # region #-- check for a valid Velop device --#
        if "velop" not in _model_description.lower():
            _LOGGER.debug(self._log_formatter.format("not a Velop model"))
            return self.async_abort(reason="not_velop")
        # endregion

        # region #-- try and update the config entry if it exists and doesn't have a unique_id --#
        # This region assumes that the host is unique for the Mesh (it should be but isn't guaranteed)
        # It will match on host and then update the config entry with the serial number, then abort
        update_unique_id: bool = False
        matching_entry: LinksysVelopConfigEntry = _is_mesh_by_host(
            hass=self.hass, host=_host
        )
        if matching_entry:
            if not matching_entry.unique_id:  # no unique_id even though the host exists
                _LOGGER.debug(
                    self._log_formatter.format("no unique_id in the config entry")
                )
                update_unique_id = True
            elif matching_entry.unique_id != _serial:  # parent node changed?
                _LOGGER.debug(
                    self._log_formatter.format("assuming the primary node has changed")
                )
                update_unique_id = True

                if EventSubTypes.NEW_PRIMARY_NODE in matching_entry.options.get(
                    CONF_EVENTS_OPTIONS, DEF_EVENTS_OPTIONS
                ):
                    event_properties: dict[str, Any] = {
                        "host": _host,
                        "manufacturer": _manufacturer,
                        "model": _model,
                        "description": _model_description,
                        "serial": _serial,
                    }
                    async_dispatcher_send(
                        self.hass,
                        f"{DOMAIN}_{EventSubTypes.NEW_PRIMARY_NODE.value}",
                        event_properties,
                    )

        if update_unique_id:
            _LOGGER.debug(self._log_formatter.format("updating unique_id"))
            if self.hass.config_entries.async_update_entry(
                entry=matching_entry, unique_id=_serial
            ):
                return self.async_abort(reason="already_configured")

        # endregion

        # region #-- set a unique_id, update details if device has changed IP --#
        _LOGGER.debug(self._log_formatter.format("setting unique_id"))
        await self.async_set_unique_id(_serial)
        self._abort_if_unique_id_configured(updates={CONF_NODE: _host})
        # endregion

        self.context[CONF_TITLE_PLACEHOLDERS] = {
            CONF_FLOW_NAME: _host
        }  # set the name of the flow

        self._options[CONF_NODE] = _host
        return await self.async_step_user()

    async def async_step_timers(self, user_input=None) -> data_entry_flow.FlowResult:
        """Allow the user to set the relevant timers for the integration."""
        _LOGGER.debug(self._log_formatter.format("entered, user_input: %s"), user_input)
        if user_input is not None:
            self._errors = {}
            self._options[CONF_API_REQUEST_TIMEOUT] = DEF_API_REQUEST_TIMEOUT
            self._options.update(user_input)
            return await self.async_step_device_trackers()

        # region #-- handle the unique_id now --#
        if not self.unique_id:
            _LOGGER.debug(self._log_formatter.format("no unique_id"))
            # region #-- get the unique_id --#
            unique_id: str | None = None
            if self._mesh:
                nodes: list[NodeEntity] = self._mesh.nodes
                for node in nodes:
                    if node.type == "primary":
                        unique_id = node.serial
            # endregion

            # region #-- do we have matching host? --#
            # didn't always have unique_id so let's look for it by host and set it if we can then abort
            matching_entry = _is_mesh_by_host(
                hass=self.hass, host=self._options.get(CONF_NODE)
            )
            if matching_entry:
                if not matching_entry.unique_id:
                    _LOGGER.debug(
                        self._log_formatter.format("updating config entry unique_id")
                    )
                    self.hass.config_entries.async_update_entry(
                        entry=matching_entry, unique_id=unique_id
                    )
                return self.async_abort(reason="already_configured")
            else:
                _LOGGER.debug(self._log_formatter.format("setting unique_id"))
                await self.async_set_unique_id(unique_id, raise_on_progress=False)
                self._abort_if_unique_id_configured()
            # endregion
        # endregion

        return self.async_show_form(
            step_id=Steps.TIMERS,
            data_schema=await _async_build_schema_with_user_input(
                Steps.TIMERS, self._options
            ),
            errors=self._errors,
            last_step=False,
        )

    async def async_step_unignore(self, user_input=None) -> data_entry_flow.FlowResult:
        """Rediscover the devices if the config entry is being unignored."""
        _LOGGER.debug(self._log_formatter.format("entered, user_input: %s"), user_input)

        # region #-- get the original unique_id --#
        unique_id = user_input.get("unique_id")
        await self.async_set_unique_id(unique_id)
        # endregion

        # region #-- discover the necessary devices --#
        devices: list[SsdpServiceInfo] = await ssdp.async_get_discovery_info_by_st(
            self.hass,
            ST_IGD,
        )
        # endregion

        # region #-- try and find this device --#
        device_info = [
            device
            for device in devices
            if device.upnp.get("serialNumber", "") == unique_id
        ]

        if not device_info:
            _LOGGER.debug(self._log_formatter.format("device not found"))
            return self.async_abort(reason="not_found")
        # endregion

        return await self.async_step_ssdp(device_info[0])

    async def async_step_user(self, user_input=None) -> data_entry_flow.FlowResult:
        """Handle a flow initiated by the user."""
        _LOGGER.debug(
            self._log_formatter.format("Using integration version: %s"),
            await async_get_integration_version(self.hass),
        )
        _LOGGER.debug(
            self._log_formatter.format("entered, user_input: %s"),
            _redact_for_display(user_input),
        )

        if user_input is not None:
            self.task_login = None
            self._errors = {}
            self._options.update(user_input)
            return await self.async_step_login()

        return self.async_show_form(
            step_id=Steps.USER,
            data_schema=await _async_build_schema_with_user_input(
                Steps.USER, self._options
            ),
            errors=self._errors,
            last_step=False,
        )


class LinksysOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options from the configuration of the integration."""

    def __init__(self, config_entry: LinksysVelopConfigEntry):
        """Intialise."""
        super().__init__()
        self._config_entry: LinksysVelopConfigEntry = config_entry
        self._devices: dict | None = None
        self._errors: dict = {}
        self._options: dict = dict(self._config_entry.options)
        self._log_formatter: Logger = Logger()

    async def async_step_advanced_options(
        self, user_input=None
    ) -> data_entry_flow.FlowResult:
        """Manage the advanced options for the configuration."""
        _LOGGER.debug(self._log_formatter.format("entered, user_input: %s"), user_input)

        if user_input is not None:
            if user_input.get(CONF_NODE_IMAGES) == "*":
                user_input[CONF_NODE_IMAGES] = ""
            self._options.update(user_input)
            return await self.async_step_finalise()

        return self.async_show_form(
            step_id=Steps.ADVANCED_OPTIONS,
            data_schema=await _async_build_schema_with_user_input(
                Steps.ADVANCED_OPTIONS, self._options
            ),
            errors=self._errors,
            last_step=True,
        )

    async def async_step_device_trackers(
        self, user_input=None
    ) -> data_entry_flow.FlowResult:
        """Manage the device trackers."""
        _LOGGER.debug(self._log_formatter.format("entered, user_input: %s"), user_input)

        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_ui_device()

        if self._devices is None:
            mesh: Mesh
            if (mesh := self._config_entry.runtime_data.mesh) is None:
                mesh = Mesh(
                    node=self._options[CONF_NODE],
                    password=self._options[CONF_PASSWORD],
                    request_timeout=self._options[CONF_API_REQUEST_TIMEOUT],
                    session=async_get_clientsession(hass=self.hass),
                )
                await mesh.async_initialise()
            self._devices = await _async_get_devices(mesh=mesh)

        return self.async_show_form(
            step_id=Steps.DEVICE_TRACKERS,
            data_schema=await _async_build_schema_with_user_input(
                Steps.DEVICE_TRACKERS,
                self._options,
                multi_select_contents=self._devices,
            ),
            errors=self._errors,
            last_step=False,
        )

    async def async_step_events(self, user_input=None) -> data_entry_flow.FlowResult:
        """Event options."""
        _LOGGER.debug(self._log_formatter.format("entered, user_input: %s"), user_input)

        if user_input is not None:
            self._options.update(user_input)
            if self.show_advanced_options:
                return await self.async_step_advanced_options()
            return await self.async_step_finalise()

        return self.async_show_form(
            step_id=Steps.EVENTS,
            data_schema=await _async_build_schema_with_user_input(
                Steps.EVENTS, self._options
            ),
            errors=self._errors,
            last_step=False if self.show_advanced_options else True,
        )

    async def async_step_finalise(self, user_input=None) -> data_entry_flow.FlowResult:
        """Run the final pieces of the flow."""
        _LOGGER.debug(self._log_formatter.format("entered, user_input: %s"), user_input)

        # region #-- set device trackers no longer required to be removed --#
        prev_trackers: set[str] = set(
            self._config_entry.options.get(CONF_DEVICE_TRACKERS, [])
        )
        self._options[CONF_DEVICE_TRACKERS_TO_REMOVE] = list(
            prev_trackers.difference(set(self._options.get(CONF_DEVICE_TRACKERS, [])))
        )
        # endregion

        # region #-- set ui devices to remove if no longer needed --#
        prev_ui_devices: set[str] = set(
            self._config_entry.options.get(CONF_UI_DEVICES, [])
        )
        prev_ui_devices.discard(DEF_UI_PLACEHOLDER_DEVICE_ID)
        self._options[CONF_UI_DEVICES_TO_REMOVE] = list(
            prev_ui_devices.difference(set(self._options.get(CONF_UI_DEVICES, [])))
        )
        if not self._options.get(CONF_SELECT_TEMP_UI_DEVICE):
            self._options[CONF_UI_DEVICES_TO_REMOVE].append(
                DEF_UI_PLACEHOLDER_DEVICE_ID
            )
        # endregion

        # region #-- add the placeholder ui device if needed --#
        if self._options.get(CONF_SELECT_TEMP_UI_DEVICE):
            if DEF_UI_PLACEHOLDER_DEVICE_ID not in self._options.get(
                CONF_UI_DEVICES, []
            ):
                if self._options.get(CONF_UI_DEVICES) is not None:
                    self._options[CONF_UI_DEVICES].append(DEF_UI_PLACEHOLDER_DEVICE_ID)
                else:
                    self._options[CONF_UI_DEVICES] = [DEF_UI_PLACEHOLDER_DEVICE_ID]
        else:
            with contextlib.suppress(ValueError):
                self._options.get(CONF_UI_DEVICES, []).remove(
                    DEF_UI_PLACEHOLDER_DEVICE_ID
                )
        # endregion

        # region #-- remove up the old options --#
        self._options.pop("logging_jnap_response", None)
        self._options.pop("logging_serial", None)
        self._options.pop("logging_mode", None)
        self._options.pop("logging_options", None)
        self._options.pop("ui_devices_missing", None)
        self._options.pop("tracked_missing", None)
        # endregion

        return self.async_create_entry(title="", data=self._options)

    async def async_step_init(self, user_input=None) -> data_entry_flow.FlowResult:
        """First Step."""
        _LOGGER.debug(self._log_formatter.format("entered, user_input: %s"), user_input)
        _LOGGER.debug(
            self._log_formatter.format("show advanced options: %s"),
            self.show_advanced_options,
        )

        menu_options: list[str] = [
            Steps.TIMERS,
            Steps.DEVICE_TRACKERS,
            Steps.UI_DEVICE,
            Steps.EVENTS,
        ]
        if self.show_advanced_options:
            menu_options.append(Steps.ADVANCED_OPTIONS)

        return self.async_show_menu(
            step_id=Steps.INIT,
            menu_options=menu_options,
        )

    async def async_step_timers(self, user_input=None) -> data_entry_flow.FlowResult:
        """Manage the timer options available for the integration."""
        _LOGGER.debug(self._log_formatter.format("entered, user_input: %s"), user_input)

        if user_input is not None:
            # TODO: This can be removed after a length of time but it does no harm
            # region #-- tidy up the config after a misconfig on setting up the integration
            self._options.pop("CONF_API_REQUEST_TIMEOUT", None)
            # endregion

            if CONF_API_REQUEST_TIMEOUT not in self._options:
                self._options[CONF_API_REQUEST_TIMEOUT] = DEF_API_REQUEST_TIMEOUT
            self._options.update(user_input)
            return await self.async_step_device_trackers()

        return self.async_show_form(
            step_id=Steps.TIMERS,
            data_schema=await _async_build_schema_with_user_input(
                Steps.TIMERS, self._options
            ),
            errors=self._errors,
            last_step=False,
        )

    async def async_step_ui_device(self, user_input=None) -> data_entry_flow.FlowResult:
        """Manage the devices that should be created in the UI."""
        _LOGGER.debug(self._log_formatter.format("entered, user_input: %s"), user_input)

        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_events()

        if self._devices is None:
            mesh: Mesh
            if (mesh := self._config_entry.runtime_data.mesh) is None:
                mesh = Mesh(
                    node=self._options[CONF_NODE],
                    password=self._options[CONF_PASSWORD],
                    request_timeout=self._options[CONF_API_REQUEST_TIMEOUT],
                    session=async_get_clientsession(hass=self.hass),
                )
                await mesh.async_initialise()
            self._devices = await _async_get_devices(mesh=mesh)

        return self.async_show_form(
            step_id=Steps.UI_DEVICE,
            data_schema=await _async_build_schema_with_user_input(
                Steps.UI_DEVICE, self._options, multi_select_contents=self._devices
            ),
            errors=self._errors,
            last_step=False,
        )
