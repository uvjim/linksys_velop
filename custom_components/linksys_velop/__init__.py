"""The Linksys Velop integration."""

# region #-- imports --#
import copy
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.config_entries import entity_registry as er
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotFound
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.issue_registry import IssueSeverity
from pyvelop.const import _PACKAGE_NAME as PYVELOP_NAME
from pyvelop.device import Device
from pyvelop.exceptions import (
    MeshConnectionError,
    MeshDeviceNotFoundResponse,
    MeshException,
    MeshTimeoutError,
)
from pyvelop.mesh import Mesh

from .const import (
    CONF_API_REQUEST_TIMEOUT,
    CONF_DEVICE_TRACKERS,
    CONF_DEVICE_TRACKERS_TO_REMOVE,
    CONF_EVENTS_OPTIONS,
    CONF_LOGGING_MODE,
    CONF_LOGGING_MODE_OFF,
    CONF_LOGGING_OPTION_INCLUDE_QUERY_RESPONSE,
    CONF_LOGGING_OPTIONS,
    CONF_NODE,
    CONF_SCAN_INTERVAL_DEVICE_TRACKER,
    CONF_SELECT_TEMP_UI_DEVICE,
    CONF_UI_DEVICES_TO_REMOVE,
    DEF_API_REQUEST_TIMEOUT,
    DEF_EVENTS_OPTIONS,
    DEF_LOGGING_MODE,
    DEF_LOGGING_OPTIONS,
    DEF_SCAN_INTERVAL,
    DEF_SCAN_INTERVAL_DEVICE_TRACKER,
    DEF_SELECT_TEMP_UI_DEVICE,
    DEVICE_TRACKER_DOMAIN,
    DOMAIN,
    EVENT_DOMAIN,
    ISSUE_MISSING_DEVICE_TRACKER,
    PLATFORMS,
    SELECT_DOMAIN,
    SIGNAL_DEVICE_TRACKER_UPDATE,
)
from .coordinator import (
    LinksysVelopUpdateCoordinator,
    LinksysVelopUpdateCoordinatorChannelScan,
    LinksysVelopUpdateCoordinatorSpeedtest,
)
from .helpers import (
    get_mesh_device_for_config_entry,
    include_serial_logging,
    remove_velop_device_from_registry,
    remove_velop_entity_from_registry,
)
from .logger import Logger
from .service_handler import LinksysVelopServiceHandler
from .types import CoordinatorTypes, LinksysVelopConfigEntry, LinksysVelopData

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)
_SETUP_PLATFORMS: list[str] = []

LOGGING_ON: str = logging.getLevelName(logging.DEBUG)
LOGGING_OFF: str = logging.getLevelName(_LOGGER.level)
LOGGING_REVERT: str = logging.getLevelName(logging.getLogger("").level)
LOGGING_DISABLED: bool = False


async def async_logging_state(
    config_entry: ConfigEntry, hass: HomeAssistant, log_formatter: Logger, state: bool
) -> None:
    """Turn logging on or off."""
    global LOGGING_DISABLED  # pylint: disable=global-statement

    logging_level: str = LOGGING_ON if state else LOGGING_OFF
    if (
        logging_level == LOGGING_ON
        and CONF_LOGGING_OPTION_INCLUDE_QUERY_RESPONSE
        in config_entry.options.get(CONF_LOGGING_OPTIONS, DEF_LOGGING_OPTIONS)
    ):
        logging_level_jnap_response: str = LOGGING_ON
    else:
        logging_level_jnap_response: str = LOGGING_REVERT
    if not state:
        _LOGGER.debug(log_formatter.format("log state: %s"), logging_level)
        _LOGGER.debug(
            log_formatter.format("JNAP response log state: %s"),
            logging_level_jnap_response,
        )
    try:
        await hass.services.async_call(
            blocking=True,
            domain="logger",
            service="set_level",
            service_data={
                f"custom_components.{DOMAIN}": logging_level,
                PYVELOP_NAME: logging_level,
                f"{PYVELOP_NAME}.jnap.verbose": logging_level_jnap_response,
            },
        )
    except ServiceNotFound:
        if not LOGGING_DISABLED:
            _LOGGER.warning(
                log_formatter.format(
                    "The logger integration is not enabled. Turning integration logging off."
                )
            )
            options: dict[str, Any] = dict(**config_entry.options)
            options[CONF_LOGGING_MODE] = CONF_LOGGING_MODE_OFF
            hass.config_entries.async_update_entry(entry=config_entry, options=options)
            LOGGING_DISABLED = True
    else:
        _LOGGER.debug(log_formatter.format("log state: %s"), logging_level)
        _LOGGER.debug(
            log_formatter.format("JNAP response log state: %s"),
            logging_level_jnap_response,
        )
        if (
            not state
            and config_entry.options.get(CONF_LOGGING_MODE, DEF_LOGGING_MODE)
            != CONF_LOGGING_MODE_OFF
        ):
            options: dict[str, Any] = dict(**config_entry.options)
            options[CONF_LOGGING_MODE] = CONF_LOGGING_MODE_OFF
            hass.config_entries.async_update_entry(entry=config_entry, options=options)


async def async_remove_config_entry_device(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Allow device removal.

    Do not allow the Mesh device to be removed
    """
    if include_serial_logging(config_entry):
        log_formatter = Logger(unique_id=config_entry.unique_id)
    else:
        log_formatter = Logger()

    mesh_id: set = {(DOMAIN, config_entry.entry_id)}
    if device_entry.identifiers.intersection(mesh_id):
        _LOGGER.error(
            log_formatter.format("Attempt to remove the Mesh device rejected")
        )
        return False

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry
) -> bool:
    """Create a config entry."""

    global _SETUP_PLATFORMS

    # region #-- setup logging --#
    if include_serial_logging(config_entry):
        log_formatter = Logger(unique_id=config_entry.unique_id)
    else:
        log_formatter = Logger()
    # endregion

    # region #-- start logging if needed --#
    logging_mode: bool = config_entry.options.get(CONF_LOGGING_MODE, DEF_LOGGING_MODE)
    if logging_mode != CONF_LOGGING_MODE_OFF:
        await async_logging_state(
            config_entry=config_entry,
            hass=hass,
            log_formatter=log_formatter,
            state=True,
        )
    # endregion

    _LOGGER.debug(log_formatter.format("entered"))
    _LOGGER.debug(
        log_formatter.format("logging mode: %s"),
        logging_mode,
    )

    # region #-- initialise runtime data --#
    config_entry.runtime_data = LinksysVelopData()
    # endregion

    mesh: Mesh = Mesh(
        node=config_entry.options[CONF_NODE],
        password=config_entry.options[CONF_PASSWORD],
        request_timeout=config_entry.options.get(
            CONF_API_REQUEST_TIMEOUT, DEF_API_REQUEST_TIMEOUT
        ),
        session=async_get_clientsession(hass=hass),
    )

    # region #-- setup the coordinators --#
    _LOGGER.debug(log_formatter.format("setting up Mesh for the coordinator"))
    # region #--- mesh coordinator --#
    _LOGGER.debug(log_formatter.format("setting up the mesh coordinator"))
    coordinator_name = DOMAIN
    if getattr(log_formatter, "_unique_id"):
        coordinator_name += f" ({getattr(log_formatter, '_unique_id')})"

    coordinator = LinksysVelopUpdateCoordinator(
        hass,
        _LOGGER,
        mesh,
        coordinator_name,
        update_interval_secs=config_entry.options.get(
            CONF_SCAN_INTERVAL, DEF_SCAN_INTERVAL
        ),
    )
    await coordinator.async_config_entry_first_refresh()
    config_entry.runtime_data.coordinators[CoordinatorTypes.MESH] = coordinator
    # endregion
    # region #-- speedtest coordinator --#
    _LOGGER.debug(log_formatter.format("setting up the speedtest coordinator"))
    coordinator_name = f"{DOMAIN} speedtest"
    if getattr(log_formatter, "_unique_id"):
        coordinator_name += f" ({getattr(log_formatter, '_unique_id')})"

    coordinator = LinksysVelopUpdateCoordinatorSpeedtest(
        hass,
        _LOGGER,
        mesh,
        coordinator_name,
        update_interval_secs=config_entry.options.get(
            CONF_SCAN_INTERVAL, DEF_SCAN_INTERVAL
        ),
    )
    await coordinator.async_config_entry_first_refresh()
    config_entry.runtime_data.coordinators[CoordinatorTypes.SPEEDTEST] = coordinator
    # endregion
    # region #-- channel scan coordinator --#
    _LOGGER.debug(log_formatter.format("setting up the channel scan coordinator"))
    coordinator_name = f"{DOMAIN} channel scan"
    if getattr(log_formatter, "_unique_id"):
        coordinator_name += f" ({getattr(log_formatter, '_unique_id')})"

    coordinator = LinksysVelopUpdateCoordinatorChannelScan(
        hass,
        _LOGGER,
        mesh,
        coordinator_name,
        update_interval_secs=config_entry.options.get(
            CONF_SCAN_INTERVAL, DEF_SCAN_INTERVAL
        ),
    )
    await coordinator.async_config_entry_first_refresh()
    config_entry.runtime_data.coordinators[CoordinatorTypes.CHANNEL_SCAN] = coordinator
    # endregion
    # endregion

    # region #-- setup the timer for device trackers --#
    async def async_device_tracker_update(_: datetime) -> None:
        """Retrieve the tracked devices from the Mesh."""
        try:
            devices: list[Device] = await mesh.async_get_device_from_id(
                config_entry.options.get(CONF_DEVICE_TRACKERS, []), True
            )
            for device in devices:
                async_dispatcher_send(
                    hass,
                    f"{SIGNAL_DEVICE_TRACKER_UPDATE}_{device.unique_id}",
                    device,
                )
        except MeshDeviceNotFoundResponse as err:
            for tracker_missing in err.devices:
                entity_registry: er.EntityRegistry = er.async_get(hass)
                config_entities: list[er.RegistryEntry] = (
                    er.async_entries_for_config_entry(
                        entity_registry, config_entry.entry_id
                    )
                )
                tracker_entity: list[er.RegistryEntry]
                if tracker_entity := [
                    e
                    for e in config_entities
                    if e.unique_id
                    == f"{config_entry.entry_id}::{DEVICE_TRACKER_DOMAIN}::{tracker_missing}"
                ]:
                    # region #-- raise an issue --#
                    ir.async_create_issue(
                        hass,
                        DOMAIN,
                        ISSUE_MISSING_DEVICE_TRACKER,
                        data={
                            "device_id": tracker_entity[0].entity_id,
                            "device_name": tracker_entity[0].name
                            or tracker_entity[0].original_name,
                        },
                        is_fixable=True,
                        is_persistent=False,
                        severity=IssueSeverity.ERROR,
                        translation_key=ISSUE_MISSING_DEVICE_TRACKER,
                        translation_placeholders={
                            "device_name": tracker_entity[0].name
                            or tracker_entity[0].original_name
                        },
                    )
                    # endregion
        except (MeshConnectionError, MeshTimeoutError) as err:
            pass
            # TODO: check for long running task and suppress error
            # TODO: no long running task, log warning
        except MeshException as err:
            pass
            # TODO: handle unexpected error

    if len(config_entry.options.get(CONF_DEVICE_TRACKERS, [])) > 0:
        scan_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL_DEVICE_TRACKER, DEF_SCAN_INTERVAL_DEVICE_TRACKER
        )
        config_entry.async_on_unload(
            async_track_time_interval(
                hass, async_device_tracker_update, timedelta(seconds=scan_interval)
            )
        )
    # endregion

    # region #-- setup the platforms --#
    _SETUP_PLATFORMS = list(filter(None, PLATFORMS))
    if len(config_entry.options.get(CONF_EVENTS_OPTIONS, DEF_EVENTS_OPTIONS)) > 0:
        _SETUP_PLATFORMS.append(EVENT_DOMAIN)
    else:
        remove_velop_entity_from_registry(
            hass,
            config_entry.entry_id,
            f"{config_entry.entry_id}::{EVENT_DOMAIN}::events",
        )
    if config_entry.options.get(CONF_SELECT_TEMP_UI_DEVICE, DEF_SELECT_TEMP_UI_DEVICE):
        _SETUP_PLATFORMS.append(SELECT_DOMAIN)
    else:
        if SELECT_DOMAIN in _SETUP_PLATFORMS:
            _SETUP_PLATFORMS.remove(SELECT_DOMAIN)
    if len(config_entry.options.get(CONF_DEVICE_TRACKERS, [])) > 0:
        _SETUP_PLATFORMS.append(DEVICE_TRACKER_DOMAIN)
    else:
        if DEVICE_TRACKER_DOMAIN in _SETUP_PLATFORMS:
            _SETUP_PLATFORMS.remove(DEVICE_TRACKER_DOMAIN)
    _LOGGER.debug(log_formatter.format("setting up platforms: %s"), _SETUP_PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(config_entry, _SETUP_PLATFORMS)
    # endregion

    # region #-- remove unnecessary ui devices --#
    _LOGGER.debug(log_formatter.format("cleaning up ui devices"))
    for ui_device in config_entry.options.get(CONF_UI_DEVICES_TO_REMOVE, []):
        remove_velop_device_from_registry(hass, ui_device)
    new_options = copy.deepcopy(dict(config_entry.options))
    new_options.get(CONF_UI_DEVICES_TO_REMOVE, []).clear()
    hass.config_entries.async_update_entry(config_entry, options=new_options)
    # endregion

    # region #-- remove unnecessary device trackers --#
    _LOGGER.debug(log_formatter.format("cleaning up device trackers"))
    connections: set[tuple[str, str]] = set()
    mesh_device: DeviceEntry = get_mesh_device_for_config_entry(hass, config_entry)
    if mesh_device is not None:
        connections = mesh_device.connections
    for tracker in config_entry.options.get(CONF_DEVICE_TRACKERS_TO_REMOVE, []):
        # region #-- remove entity --#
        remove_velop_entity_from_registry(
            hass,
            config_entry.entry_id,
            f"{config_entry.entry_id}::{DEVICE_TRACKER_DOMAIN}::{tracker}",
        )
        # endregion
        # region #-- remove connection from the mesh device --#
        device: Device
        if device := [d for d in mesh.devices if d.unique_id == tracker]:
            if adapter := [a for a in device[0].network]:
                connections.discard(
                    (
                        dr.CONNECTION_NETWORK_MAC,
                        dr.format_mac(adapter[0].get("mac", "")),
                    )
                )
        # endregion

    # region #-- update the mesh device --#
    device_registry: DeviceRegistry = dr.async_get(hass)
    mesh_device: DeviceEntry = get_mesh_device_for_config_entry(hass, config_entry)
    device_registry.async_update_device(mesh_device.id, new_connections=connections)
    # endregion

    new_options = copy.deepcopy(dict(config_entry.options))
    new_options.get(CONF_DEVICE_TRACKERS_TO_REMOVE, []).clear()
    hass.config_entries.async_update_entry(config_entry, options=new_options)
    # endregion

    # region #-- service definition --#
    _LOGGER.debug(log_formatter.format("registering services"))
    config_entry.runtime_data.service_handler = LinksysVelopServiceHandler(hass)
    config_entry.runtime_data.service_handler.register_services()
    # endregion

    # region #-- listen for config changes --#
    _LOGGER.debug(log_formatter.format("listening for config changes"))
    config_entry.async_on_unload(
        config_entry.add_update_listener(_async_update_listener)
    )
    # endregion

    _LOGGER.debug(log_formatter.format("exited"))

    if logging_mode == "single":
        await async_logging_state(
            config_entry=config_entry,
            hass=hass,
            log_formatter=log_formatter,
            state=False,
        )

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry
) -> bool:
    """Cleanup when unloading a config entry."""
    if include_serial_logging(config_entry):
        log_formatter = Logger(unique_id=config_entry.unique_id)
    else:
        log_formatter = Logger()

    _LOGGER.debug(log_formatter.format("entered"))

    # region #-- remove services but only if there are no other instances --#
    all_config_entries = hass.config_entries.async_entries(domain=DOMAIN)
    _LOGGER.debug(log_formatter.format("%i instances"), len(all_config_entries))
    if len(all_config_entries) == 1:
        _LOGGER.debug(log_formatter.format("unregistering services"))
        config_entry.runtime_data.service_handler.unregister_services()
    # endregion

    # region #-- clean up the platforms --#
    _LOGGER.debug(log_formatter.format("cleaning up platforms: %s"), _SETUP_PLATFORMS)
    ret = await hass.config_entries.async_unload_platforms(
        config_entry, _SETUP_PLATFORMS
    )
    # endregion

    _LOGGER.debug(log_formatter.format("exited"))
    return ret


async def _async_update_listener(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Reload the config entry."""
    await hass.config_entries.async_reload(config_entry.entry_id)
