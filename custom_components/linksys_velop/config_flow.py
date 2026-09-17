"""Provide UI for configuring the integration."""

# region #-- imports --#
from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.device_tracker import CONF_CONSIDER_HOME
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from pyvelop.action_registry import Actions
from pyvelop.exceptions import (
    MeshConnectionError,
    MeshCredentialCheckDelayed,
    MeshInvalidCredentials,
    MeshInvalidCredentialsNoRetry,
    MeshInvalidCredentialsWithDelay,
    MeshNodeNotPrimary,
)
from pyvelop.mesh import Mesh
from pyvelop.mesh_entity import DeviceEntity, NodeEntity, NodeType

from . import LinksysVelopConfigEntry
from .const import (
    CONF_ALLOW_MESH_REBOOT,
    CONF_API_REQUEST_TIMEOUT,
    CONF_DEVICE_TRACKERS,
    CONF_DEVICE_TRACKERS_TO_REMOVE,
    CONF_EVENTS_OPTIONS,
    CONF_EVENTS_WAIT_IP,
    CONF_FLOW_NAME,
    CONF_NODE,
    CONF_NODE_IMAGES,
    CONF_REDACT_OPTIONS,
    CONF_SCAN_INTERVAL_DEVICE_TRACKER,
    CONF_SELECT_TEMP_UI_DEVICE,
    CONF_TITLE_PLACEHOLDERS,
    CONF_UI_DEVICES,
    CONF_UI_DEVICES_TO_REMOVE,
    CONF_UI_PLACEHOLDER_DEVICE_ID,
    DEF_ALLOW_MESH_REBOOT,
    DEF_API_CONFIG_FLOW_REQUEST_TIMEOUT,
    DEF_API_REQUEST_TIMEOUT,
    DEF_CONSIDER_HOME,
    DEF_EVENTS_OPTIONS,
    DEF_EVENTS_WAIT_IP,
    DEF_FLOW_NAME,
    DEF_SCAN_INTERVAL,
    DEF_SCAN_INTERVAL_DEVICE_TRACKER,
    DEF_SELECT_TEMP_UI_DEVICE,
    DOMAIN,
    ST_IGD,
)
from .helpers import async_get_integration_version
from .logger import Logger

# endregion
_LOGGER: Logger = Logger(logging.getLogger(__name__))


@dataclass
class ErrorDetails:
    """Representation of error details to be shown to the user.

    Consists of error and description placeholder objects.
    """

    error: dict[str, str] = field(default_factory=dict, init=False)
    placeholders: dict[str, str] = field(default_factory=dict, init=False)

    def clear(self) -> None:
        """Clear the error and placeholder objects."""

        self.error = {}
        self.placeholders = {}

    def has_error(self) -> bool:
        """Determine if there is an error stored.

        This doesn't check whether there are any placeholders set - there is no
        requirement to do so.

        :returns: `True` if there is an error; `False` otherwise.
        """
        return len(self.error) != 0

    def set_error(
        self,
        key: str,
        field_name: str | None = None,
        msg_placeholders: Mapping[str, str] | None = None,
    ) -> None:
        """Set an error.

        Specify an optional field name that the error belongs to. If not specified `base` is used
        making it a generic error for display, i.e. it isn't tied to a field.

        :param key: Translation key for the error to be displayed.
        :param field_name: Optional field name that the error belongs to.
        :param msg_placeholders: Optional mapping for when the message provided by `key` has placeholders to
        be populated.
        """

        fname: str = field_name if field_name is not None else "base"
        self.error = {fname: key}
        if msg_placeholders is not None:
            self.placeholders = dict(msg_placeholders)


class Steps(StrEnum):
    """Define the steps vailable to the config flow."""

    ENTITY_OPTIONS = auto()
    DEVICE_TRACKERS = auto()
    EVENTS = auto()
    FINALISE = auto()
    GATHER_DETAILS = auto()
    INIT = auto()
    LOGGING = auto()
    MESH_DELAY = auto()
    MESH_INITIALISE = auto()
    REAUTH_CONFIRM = auto()
    TIMERS = auto()
    UI_DEVICE = auto()
    USER = auto()


def _get_input_default(
    user_input: Mapping[str, Any],
    key: str,
    default: Any,
) -> Any:
    """Return a value from user input, or a default if it is absent.

    :param user_input: Previously submitted config-flow input.
    :param key: Key to retrieve from the input.
    :param default: Value to return when the key is absent.
    :returns: The submitted value or the default value.
    """
    return user_input.get(key, default)


def _build_schema_multi_select(
    *,
    contents: Mapping[str, str] | Sequence[str],
    translation_key: str | None = None,
) -> selector.SelectSelector:
    """Build a multiple-selection dropdown selector.

    :param contents: Mapping of option values to display labels.
    :returns: A configured multiple-selection selector.
    """

    available_options: Sequence[selector.SelectOptionDict] | Sequence[str] | None = None
    if isinstance(contents, Mapping):
        available_options = [
            {"label": label, "value": value} for value, label in contents.items()
        ]
    else:
        available_options = contents

    config = {
        "mode": selector.SelectSelectorMode.DROPDOWN,
        "multiple": True,
        "options": available_options,
    }
    if translation_key is not None:
        config["translation_key"] = translation_key

    return selector.SelectSelector(config=selector.SelectSelectorConfig(**config))


def _build_schema_step_device_trackers(
    user_input: Mapping[str, Any],
    *,
    multi_select_contents: Mapping[str, str],
    **_: Any,
) -> vol.Schema:
    """Build the device-tracker selection schema.

    :param user_input: Previously submitted config-flow input.
    :param multi_select_contents: Available tracker values and labels.
    :returns: The schema for the device-trackers step.
    """
    selected_trackers = [
        tracker
        for tracker in _get_input_default(user_input, CONF_DEVICE_TRACKERS, [])
        if tracker in multi_select_contents
    ]

    return vol.Schema(
        {
            vol.Optional(
                CONF_DEVICE_TRACKERS,
                default=selected_trackers,
            ): _build_schema_multi_select(
                contents=multi_select_contents,
            )
        }
    )


def _build_schema_step_entity_options(
    user_input: Mapping[str, Any],
    **_: Any,
) -> vol.Schema:
    """Build the initial entity options schema.

    :param user_input: Previously submitted config-flow input.
    :returns: The schema for the entity options step.
    """
    return vol.Schema(
        {
            vol.Optional(
                CONF_NODE_IMAGES,
                default=_get_input_default(user_input, CONF_NODE_IMAGES, ""),
            ): selector.TextSelector(),
            vol.Required(
                CONF_SELECT_TEMP_UI_DEVICE,
                default=_get_input_default(
                    user_input, CONF_SELECT_TEMP_UI_DEVICE, DEF_SELECT_TEMP_UI_DEVICE
                ),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_ALLOW_MESH_REBOOT,
                default=_get_input_default(
                    user_input, CONF_ALLOW_MESH_REBOOT, DEF_ALLOW_MESH_REBOOT
                ),
            ): selector.BooleanSelector(),
        }
    )


def _build_schema_step_events(
    user_input: Mapping[str, Any],
    *,
    multi_select_contents: Mapping[str, str],
    **_: Any,
) -> vol.Schema:
    """Build the event selection schema.

    :param user_input: Previously submitted config flow input.
    :param multi_select_contents: Available events values and labels.
    :returns: The schema for the UI device step.
    """

    selected_events = [
        event
        for event in _get_input_default(
            user_input, CONF_EVENTS_OPTIONS, DEF_EVENTS_OPTIONS
        )
        if event in multi_select_contents
    ]

    return vol.Schema(
        {
            vol.Optional(
                CONF_EVENTS_OPTIONS,
                default=selected_events,
            ): _build_schema_multi_select(
                contents=multi_select_contents,
                translation_key=CONF_EVENTS_OPTIONS,
            ),
            vol.Required(
                CONF_EVENTS_WAIT_IP,
                default=user_input.get(CONF_EVENTS_WAIT_IP, DEF_EVENTS_WAIT_IP),
            ): selector.BooleanSelector(),
        }
    )


def _build_schema_step_logging(
    user_input: Mapping[str, Any],
    **_: Any,
) -> vol.Schema:
    """Build the initial logging schema.

    :param user_input: Previously submitted config-flow input.
    :returns: The schema for the user step.
    """
    return vol.Schema(
        {
            vol.Optional(
                CONF_REDACT_OPTIONS,
                default=_get_input_default(
                    user_input,
                    CONF_REDACT_OPTIONS,
                    {action.key: [] for action in Actions.values()},
                ),
            ): selector.ObjectSelector(config=selector.ObjectSelectorConfig())
        }
    )


def _build_schema_step_reauth_confirm(
    user_input: Mapping[str, Any],
    **_: Any,
) -> vol.Schema:
    """Build the initial reauth confirmation schema.

    :param user_input: Previously submitted config-flow input.
    :returns: The schema for the user step.
    """
    return vol.Schema(
        {
            vol.Required(
                CONF_PASSWORD,
                default=_get_input_default(user_input, CONF_PASSWORD, ""),
            ): selector.TextSelector(
                config=selector.TextSelectorConfig(
                    type=selector.TextSelectorType.PASSWORD
                )
            ),
        }
    )


def _build_schema_step_timers(
    user_input: Mapping[str, Any],
    **_: Any,
) -> vol.Schema:
    """Build the initial timers schema.

    :param user_input: Previously submitted config-flow input.
    :returns: The schema for the user step.
    """
    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=_get_input_default(
                    user_input, CONF_SCAN_INTERVAL, DEF_SCAN_INTERVAL
                ),
            ): selector.NumberSelector(
                config=selector.NumberSelectorConfig(
                    min=0,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SCAN_INTERVAL_DEVICE_TRACKER,
                default=_get_input_default(
                    user_input,
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
                default=_get_input_default(
                    user_input, CONF_CONSIDER_HOME, DEF_CONSIDER_HOME
                ),
            ): selector.NumberSelector(
                config=selector.NumberSelectorConfig(
                    min=0,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_API_REQUEST_TIMEOUT,
                default=_get_input_default(
                    user_input, CONF_API_REQUEST_TIMEOUT, DEF_API_REQUEST_TIMEOUT
                ),
            ): cv.positive_float,
        }
    )


def _build_schema_step_ui_devices(
    user_input: Mapping[str, Any],
    *,
    multi_select_contents: Mapping[str, str],
    **_: Any,
) -> vol.Schema:
    """Build the UI device selection schema.

    :param user_input: Previously submitted config flow input.
    :param multi_select_contents: Available UI device values and labels.
    :returns: The schema for the UI device step.
    """

    selected_devices = [
        device
        for device in _get_input_default(user_input, CONF_UI_DEVICES, [])
        if device in multi_select_contents
    ]

    return vol.Schema(
        {
            vol.Optional(
                CONF_UI_DEVICES,
                default=selected_devices,
            ): _build_schema_multi_select(
                contents=multi_select_contents,
            )
        }
    )


def _build_schema_step_user(
    user_input: Mapping[str, Any],
    **_: Any,
) -> vol.Schema:
    """Build the initial user schema.

    :param user_input: Previously submitted config-flow input.
    :returns: The schema for the user step.
    """
    return vol.Schema(
        {
            vol.Required(
                CONF_NODE,
                default=_get_input_default(user_input, CONF_NODE, ""),
            ): selector.TextSelector(),
            vol.Required(
                CONF_PASSWORD,
                default=_get_input_default(user_input, CONF_PASSWORD, ""),
            ): selector.TextSelector(
                config=selector.TextSelectorConfig(
                    type=selector.TextSelectorType.PASSWORD,
                )
            ),
        }
    )


def _build_schema_step(
    step: Steps,
    user_input: Mapping[str, Any],
    *,
    multi_select_contents: Mapping[str, str] | Sequence[str] | None = None,
) -> vol.Schema:
    """Build the schema for a config-flow step.

    The schema uses values from ``user_input`` as defaults and applies
    step-specific selectors and validation rules.

    :param step: Config-flow step for which to build the schema.
    :param user_input: Previously submitted input used to populate defaults.
    :param multi_select_contents: Available options for multi-select steps.
    :returns: A voluptuous schema suitable for ``async_show_form``.
    :raises ValueError: If no schema builder exists for ``step``.
    """
    try:
        builder = _SCHEMA_BUILDERS[step]
    except KeyError as err:
        raise ValueError(f"Unsupported config-flow step: {step}") from err

    return builder(
        user_input,
        multi_select_contents=multi_select_contents or {},
    )


_SCHEMA_BUILDERS: dict[
    Steps,
    Callable[..., vol.Schema],
] = {
    Steps.DEVICE_TRACKERS: _build_schema_step_device_trackers,
    Steps.ENTITY_OPTIONS: _build_schema_step_entity_options,
    Steps.EVENTS: _build_schema_step_events,
    Steps.LOGGING: _build_schema_step_logging,
    Steps.REAUTH_CONFIRM: _build_schema_step_reauth_confirm,
    Steps.TIMERS: _build_schema_step_timers,
    Steps.UI_DEVICE: _build_schema_step_ui_devices,
    Steps.USER: _build_schema_step_user,
}


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


def _redact_for_display(data: Mapping[str, Any]) -> dict:
    """Redact information for display purposes."""

    to_redact: set[str] = {"password"}
    return async_redact_data(data, to_redact)


async def _async_get_devices(mesh: Mesh) -> dict[str, str]:
    """Get the devices from the mesh for display purposes.

    The device unique_id (as per the Mesh) is used as the key.

    :param mesh: the Mesh object
    :return: a dictionary containing the devices to present
    """
    ret: dict = {}

    devices: tuple[DeviceEntity, ...] = await mesh.async_get_devices()
    for device in devices:
        for adapter in device.adapter_info:
            ret[device.unique_id.value] = f"{device.name} --> {adapter.mac}"

    return ret


class LinksysVelopConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial installation ConfigFlow."""

    VERSION = 2

    reauth_entry: LinksysVelopConfigEntry | None = None

    def __init__(self):
        """Initialise."""
        self._error_details: ErrorDetails = ErrorDetails()
        self._mesh: Mesh | None = None
        self._options: dict[str, Any] = {}
        self.task_delay: asyncio.Task[None] | None = None
        self.task_init: asyncio.Task[Mesh] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: LinksysVelopConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return LinksysOptionsFlowHandler()

    async def _async_task_mesh_initialise(self, details: Mapping[str, Any]) -> Mesh:
        """Authenticate and refresh the data available in the Mesh.

        :param details: basic details for connecting to the mesh.
        :return: Mesh object to be used for subsequent data retrieval.
        """

        mesh = Mesh(**details, session=async_get_clientsession(self.hass))
        await mesh.async_authenticate_and_refresh()

        return mesh

    async def async_step_device_trackers(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Allow the user to select the device trackers for presence detection.

        :param user_input: User-provided configuration data, or `None` when
        the form has not yet been submitted.
        :returns: The next config flow result.
        """

        devices: dict[str, str] = {}

        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_finish()

        if self._mesh is not None:
            devices = await _async_get_devices(self._mesh)

        errors: dict[str, str] | None = None
        placeholders: dict[str, str] | None = None

        if self._error_details.has_error():
            errors = self._error_details.error.copy()
            placeholders = self._error_details.placeholders.copy()
            self._error_details.clear()

        return self.async_show_form(
            step_id=Steps.DEVICE_TRACKERS,
            data_schema=_build_schema_step(
                Steps.DEVICE_TRACKERS, self._options, multi_select_contents=devices
            ),
            description_placeholders=placeholders,
            errors=errors,
            last_step=False,
        )

    async def async_step_finish(self) -> config_entries.ConfigFlowResult:
        """Finalise the configuration entry."""
        _LOGGER.debug("entered")
        _title = (
            self.context.get(CONF_TITLE_PLACEHOLDERS, {}).get(CONF_FLOW_NAME)
            or DEF_FLOW_NAME
        )
        return self.async_create_entry(title=_title, data={}, options=self._options)

    async def async_step_mesh_delay(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show a delay when mesh authentication is in a cooldown period.

        :param user_input: User-provided configuration data, or `None` when
        the form has not yet been submitted.
        :returns: The next config flow result.
        """

        if self.task_delay is None and self._error_details.has_error():
            delay: float = float(
                self._error_details.placeholders.pop("wait_for", "10.0")
            )
            self.task_delay = self.hass.async_create_task(asyncio.sleep(delay))

        # task is still running - tell frontend to display progress
        if self.task_delay is not None and not self.task_delay.done():
            return self.async_show_progress(
                description_placeholders={
                    "wait_for": str(int(delay)),
                },
                step_id=Steps.MESH_DELAY,
                progress_action="task_delay",
                progress_task=self.task_delay,
            )

        self.task_delay = None
        return self.async_show_progress_done(next_step_id=Steps.USER)

    async def async_step_mesh_initialise(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Initialise the mesh.

        This step is only used to provide progress and to allow moving back
        to the user step should an error occur.

        :param user_input: User-provided configuration data, or `None` when
        the form has not yet been submitted.
        :returns: The next config flow result.
        """

        # the task isn't running, so start it.
        if self.task_init is None:
            self._error_details.clear()
            details: dict[str, Any] = {
                "node": self._options.get(CONF_NODE),
                "password": self._options.get(CONF_PASSWORD),
                "request_timeout": DEF_API_CONFIG_FLOW_REQUEST_TIMEOUT,
            }
            self.task_init = self.hass.async_create_task(
                self._async_task_mesh_initialise(details)
            )

        # task is still running - tell frontend to display progress
        if self.task_init is not None and not self.task_init.done():
            return self.async_show_progress(
                step_id=Steps.MESH_INITIALISE,
                progress_action="task_init",
                progress_task=self.task_init,
            )

        # task is complete, process results or exceptions
        try:
            mesh: Mesh = self.task_init.result()
        except MeshConnectionError:
            self._error_details.set_error("connection_error", CONF_NODE)
        except MeshCredentialCheckDelayed as exc:
            self._error_details.set_error(
                "login_error_delayed",
                CONF_PASSWORD,
                {
                    "attempts_remaining": exc.details.get("attempts_remaining", ""),
                    "wait_for": exc.details.get("delay_time_remaining_secs", ""),
                },
            )
            self.task_init = None
            return self.async_show_progress_done(next_step_id=Steps.MESH_DELAY)
        except MeshInvalidCredentialsWithDelay as exc:
            self._error_details.set_error(
                "login_error_delay",
                CONF_PASSWORD,
                {
                    "attempts_remaining": exc.details.get("attempts_remaining", ""),
                    "wait_for": exc.details.get("delay_time_remaining_secs", ""),
                },
            )
            self.task_init = None
            return self.async_show_progress_done(next_step_id=Steps.MESH_DELAY)
        except MeshInvalidCredentialsNoRetry:
            self._error_details.set_error("login_error_no_retry", CONF_PASSWORD)
        except MeshInvalidCredentials:
            self._error_details.set_error("login_error", CONF_PASSWORD)
        except MeshNodeNotPrimary:
            self._error_details.set_error("node_not_primary", CONF_NODE)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("%s", exc)
            self._error_details.set_error(
                "general", msg_placeholders={"exc_msg": str(exc)}
            )
        else:
            self._mesh = mesh
            self.task_init = None
            return self.async_show_progress_done(next_step_id=Steps.TIMERS)

        self.task_init = None
        return self.async_show_progress_done(next_step_id=Steps.USER)

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage reauthentication.

        :param user_input: User-provided configuration data, or `None` when
        the form has not yet been submitted.
        :returns: The next config flow result.
        """
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context.get("entry_id", "")
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Store the new auth details.

        :param user_input: User-provided configuration data, or `None` when
        the form has not yet been submitted.
        :returns: The next config flow result.
        """

        if user_input is not None and self.reauth_entry is not None:
            _options = dict(self.reauth_entry.options)
            _options.update(user_input)
            return self.async_update_reload_and_abort(
                self.reauth_entry,
                options=_options,
            )

        return self.async_show_form(
            step_id=Steps.REAUTH_CONFIRM,
            data_schema=_build_schema_step(
                Steps.REAUTH_CONFIRM,
                (
                    dict(self.reauth_entry.options)
                    if self.reauth_entry is not None
                    else {}
                ),
            ),
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Allow the Mesh primary node to be discovered via SSDP.

        :param discovery_info: Information found as part of the discovery.
        :returns: The next config flow result.
        """

        # region #-- get the important info --#
        _host = discovery_info.ssdp_headers.get("_host", "")
        _manufacturer = discovery_info.upnp.get("manufacturer", "")
        _model = discovery_info.upnp.get("modelNumber", "")
        _model_description = discovery_info.upnp.get("modelDescription", "")
        _serial = discovery_info.upnp.get("serialNumber", "")
        # endregion

        # region #-- check for a valid Velop device --#
        if "velop" not in _model_description.lower():
            _LOGGER.debug("not a Velop model")
            return self.async_abort(reason="not_velop")
        # endregion

        # region #-- try and update the config entry if it exists and doesn't have a unique_id --#
        # This region assumes that the host is unique for the Mesh (it should be but isn't guaranteed)
        # It will match on host and then update the config entry with the serial number, then abort
        update_unique_id: bool = False
        matching_entry: LinksysVelopConfigEntry | None = _is_mesh_by_host(
            hass=self.hass, host=_host
        )
        if matching_entry is not None:
            if not matching_entry.unique_id:  # no unique_id even though the host exists
                _LOGGER.debug("no unique_id in the config entry")
                update_unique_id = True
            elif matching_entry.unique_id != _serial:  # parent node changed?
                _LOGGER.debug("assuming the primary node has changed")
                update_unique_id = True

            if update_unique_id:
                _LOGGER.debug("updating unique_id")
                if self.hass.config_entries.async_update_entry(
                    entry=matching_entry, unique_id=_serial
                ):
                    return self.async_abort(reason="already_configured")

        # endregion

        # region #-- set a unique_id, update details if device has changed IP --#
        await self.async_set_unique_id(_serial)
        self._abort_if_unique_id_configured(updates={CONF_NODE: _host})
        # endregion

        self.context[CONF_TITLE_PLACEHOLDERS] = {
            CONF_FLOW_NAME: _host
        }  # set the name of the flow

        self._options[CONF_NODE] = _host
        return await self.async_step_user()

    async def async_step_timers(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Allow the user to set the relevant timers for the integration."""

        if user_input is not None:
            self._options[CONF_API_REQUEST_TIMEOUT] = DEF_API_REQUEST_TIMEOUT
            self._options.update(user_input)
            return await self.async_step_device_trackers()

        # region #-- handle the unique_id now --#
        if not self.unique_id:
            # region #-- get the unique_id --#
            unique_id: str | None = None
            if self._mesh is not None and self._mesh.latest_snapshot is not None:
                nodes: tuple[NodeEntity, ...] = self._mesh.latest_snapshot.nodes
                for node in nodes:
                    if node.type == NodeType.PRIMARY:
                        unique_id = node.serial.value
            # endregion

            if unique_id is not None:
                await self.async_set_unique_id(unique_id, raise_on_progress=False)
                self._abort_if_unique_id_configured()
        # endregion

        errors: dict[str, str] | None = None
        placeholders: dict[str, str] | None = None

        if self._error_details.has_error():
            errors = self._error_details.error.copy()
            placeholders = self._error_details.placeholders.copy()
            self._error_details.clear()

        return self.async_show_form(
            step_id=Steps.TIMERS,
            data_schema=_build_schema_step(Steps.TIMERS, self._options),
            description_placeholders=placeholders,
            errors=errors,
            last_step=False,
        )

    async def async_step_unignore(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Rediscover the devices if the config entry is being unignored."""

        # region #-- get the original unique_id --#
        if user_input is not None:
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
            return self.async_abort(reason="not_found")
        # endregion

        return await self.async_step_ssdp(device_info[0])

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initiated by the user.

        :param user_input: User-provided configuration data, or `None` when
        the form has not yet been submitted.
        :returns: The next config flow result.
        """

        # only show version information if it's the first time we're here
        if not user_input and not self._error_details.has_error():
            _LOGGER.debug(
                "using integration version: %s",
                await async_get_integration_version(self.hass),
            )

        errors: dict[str, str] | None = None
        placeholders: dict[str, str] | None = None

        # form has been submitted
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_mesh_initialise()

        # form display
        if self._error_details.has_error():
            errors = self._error_details.error.copy()
            placeholders = self._error_details.placeholders.copy()
            self._error_details.clear()

        return self.async_show_form(
            step_id=Steps.USER,
            data_schema=_build_schema_step(Steps.USER, self._options),
            description_placeholders=placeholders,
            errors=errors,
            last_step=False,
        )


class LinksysOptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Handle options from the configuration of the integration."""

    config_entry: LinksysVelopConfigEntry

    def __init__(self) -> None:
        """Initialise."""

        self._data: dict[str, Any] = {}
        self._devices: dict[str, str] | None = None
        self._error_details: ErrorDetails = ErrorDetails()
        self._options: dict[str, Any] = {}

    async def async_step_device_trackers(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the device trackers.

        :param user_input: User-provided configuration data, or `None` when
        the form has not yet been submitted.
        :returns: The next config flow result.
        """

        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_ui_device()

        # region #-- retrieve devices --#
        if self._devices is None:
            mesh_api: Mesh = self.config_entry.runtime_data.api
            self._devices = await _async_get_devices(mesh_api)
        # endregion

        errors: dict[str, str] | None = None
        placeholders: dict[str, str] | None = None

        if self._error_details.has_error():
            errors = self._error_details.error.copy()
            placeholders = self._error_details.placeholders.copy()
            self._error_details.clear()

        return self.async_show_form(
            step_id=Steps.DEVICE_TRACKERS,
            data_schema=_build_schema_step(
                Steps.DEVICE_TRACKERS,
                self._options,
                multi_select_contents=self._devices,
            ),
            description_placeholders=placeholders,
            errors=errors,
            last_step=False,
        )

    async def async_step_entity_options(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the advanced options for the configuration.

        :param user_input: User-provided configuration data, or `None` when
        the form has not yet been submitted.
        :returns: The next config flow result.
        """

        if user_input is not None:
            # region #-- update options --#
            # blank out the image path if needed
            if user_input.get(CONF_NODE_IMAGES) == "*":
                user_input[CONF_NODE_IMAGES] = ""
            self._options.update(user_input)
            # endregion

            # region #-- create a unique id for the placeholder device --#
            if self._data.get(CONF_UI_PLACEHOLDER_DEVICE_ID) is None:
                self._data.update({CONF_UI_PLACEHOLDER_DEVICE_ID: str(uuid.uuid4())})
            # endregion
            return await self.async_step_logging()

        errors: dict[str, str] | None = None
        placeholders: dict[str, str] | None = None

        if self._error_details.has_error():
            errors = self._error_details.error.copy()
            placeholders = self._error_details.placeholders.copy()
            self._error_details.clear()

        return self.async_show_form(
            step_id=Steps.ENTITY_OPTIONS,
            data_schema=_build_schema_step(Steps.ENTITY_OPTIONS, self._options),
            description_placeholders=placeholders,
            errors=errors,
            last_step=False,
        )

    async def async_step_events(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Event options.

        :param user_input: User-provided configuration data, or `None` when
        the form has not yet been submitted.
        :returns: The next config flow result.
        """

        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_entity_options()

        errors: dict[str, str] | None = None
        placeholders: dict[str, str] | None = None

        if self._error_details.has_error():
            errors = self._error_details.error.copy()
            placeholders = self._error_details.placeholders.copy()
            self._error_details.clear()

        return self.async_show_form(
            step_id=Steps.EVENTS,
            data_schema=_build_schema_step(
                Steps.EVENTS, self._options, multi_select_contents=DEF_EVENTS_OPTIONS
            ),
            description_placeholders=placeholders,
            errors=errors,
            last_step=False,
        )

    async def async_step_finalise(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Run the final pieces of the flow.

        :param user_input: User-provided configuration data, or `None` when
        the form has not yet been submitted.
        :returns: The next config flow result.
        """

        # region #-- set device trackers no longer required to be removed --#
        prev_trackers: set[str] = set(
            self.config_entry.options.get(CONF_DEVICE_TRACKERS, [])
        )
        self._data.update(
            {
                CONF_DEVICE_TRACKERS_TO_REMOVE: list(
                    prev_trackers.difference(
                        set(self._options.get(CONF_DEVICE_TRACKERS, []))
                    )
                )
            }
        )
        # endregion

        # region #-- set ui devices to remove if no longer needed --#
        ui_device_id: str | None = self._data.get(CONF_UI_PLACEHOLDER_DEVICE_ID)
        prev_ui_devices: set[str] = set(
            self.config_entry.options.get(CONF_UI_DEVICES, [])
        )
        prev_ui_devices.discard(ui_device_id)
        self._data.update(
            {
                CONF_UI_DEVICES_TO_REMOVE: list(
                    prev_ui_devices.difference(
                        set(self._options.get(CONF_UI_DEVICES, []))
                    )
                )
            }
        )
        if not self._options.get(
            CONF_SELECT_TEMP_UI_DEVICE
        ) and ui_device_id in self.config_entry.options.get(CONF_UI_DEVICES, []):
            self._data.get(CONF_UI_DEVICES_TO_REMOVE, []).append(ui_device_id)
        # endregion

        # region #-- add the placeholder ui device if needed --#
        if self._options.get(CONF_SELECT_TEMP_UI_DEVICE):
            if ui_device_id not in self._options.get(CONF_UI_DEVICES, []):
                if self._options.get(CONF_UI_DEVICES) is not None:
                    self._options[CONF_UI_DEVICES].append(ui_device_id)
                else:
                    self._options[CONF_UI_DEVICES] = [ui_device_id]
        else:
            with contextlib.suppress(ValueError):
                self._options.get(CONF_UI_DEVICES, []).remove(ui_device_id)
        # endregion

        self.hass.config_entries.async_update_entry(self.config_entry, data=self._data)
        return self.async_create_entry(title="", data=self._options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """First Step.

        :param user_input: User-provided configuration data, or `None` when
        the form has not yet been submitted.
        :returns: The next config flow result.
        """

        # region #-- initialise the instance vars that rely on config_entry --#
        # we can't do this any earlier because they aren't available.
        self._data = {**self.config_entry.data}
        self._options = {**self.config_entry.options}
        # endregion

        menu_options: tuple[str, ...] = (
            Steps.TIMERS,
            Steps.DEVICE_TRACKERS,
            Steps.UI_DEVICE,
            Steps.EVENTS,
            Steps.ENTITY_OPTIONS,
            Steps.LOGGING,
        )

        return self.async_show_menu(
            step_id=Steps.INIT,
            menu_options=menu_options,
        )

    async def async_step_logging(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Display and process logging options."""

        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_finalise()

        errors: dict[str, str] | None = None
        placeholders: dict[str, str] | None = None

        if self._error_details.has_error():
            errors = self._error_details.error.copy()
            placeholders = self._error_details.placeholders.copy()
            self._error_details.clear()

        return self.async_show_form(
            step_id=Steps.LOGGING,
            data_schema=_build_schema_step(Steps.LOGGING, self._options),
            description_placeholders=placeholders,
            errors=errors,
            last_step=True,
        )

    async def async_step_timers(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the timer options available for the integration.

        :param user_input: User-provided configuration data, or `None` when
        the form has not yet been submitted.
        :returns: The next config flow result.
        """
        if user_input is not None:
            if CONF_API_REQUEST_TIMEOUT not in self._options:
                self._options[CONF_API_REQUEST_TIMEOUT] = DEF_API_REQUEST_TIMEOUT
            self._options.update(user_input)
            return await self.async_step_device_trackers()

        errors: dict[str, str] | None = None
        placeholders: dict[str, str] | None = None

        if self._error_details.has_error():
            errors = self._error_details.error.copy()
            placeholders = self._error_details.placeholders.copy()
            self._error_details.clear()

        return self.async_show_form(
            step_id=Steps.TIMERS,
            data_schema=_build_schema_step(Steps.TIMERS, self._options),
            description_placeholders=placeholders,
            errors=errors,
            last_step=False,
        )

    async def async_step_ui_device(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the devices that should be created in the UI.

        :param user_input: User-provided configuration data, or `None` when
        the form has not yet been submitted.
        :returns: The next config flow result.
        """

        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_events()

        # region #-- retrieve devices --#
        # if the mesh hasn't been initialised then initialise it
        # shouldn't really be in that situation but you never know...
        if self._devices is None:
            mesh_api: Mesh = self.config_entry.runtime_data.api
            self._devices = await _async_get_devices(mesh_api)
        # endregion

        errors: dict[str, str] | None = None
        placeholders: dict[str, str] | None = None

        if self._error_details.has_error():
            errors = self._error_details.error.copy()
            placeholders = self._error_details.placeholders.copy()
            self._error_details.clear()

        return self.async_show_form(
            step_id=Steps.UI_DEVICE,
            data_schema=_build_schema_step(
                Steps.UI_DEVICE, self._options, multi_select_contents=self._devices
            ),
            description_placeholders=placeholders,
            errors=errors,
            last_step=False,
        )
