"""The Linksys Velop integration."""

# region #-- imports --#
import contextlib
import copy
import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.issue_registry import IssueSeverity
from pyvelop.device import Device
from pyvelop.exceptions import (
    MeshConnectionError,
    MeshDeviceNotFoundResponse,
    MeshTimeoutError,
)
from pyvelop.mesh import Mesh, MeshCapability

from .const import (
    CONF_API_REQUEST_TIMEOUT,
    CONF_DEVICE_TRACKERS,
    CONF_DEVICE_TRACKERS_TO_REMOVE,
    CONF_EVENTS_OPTIONS,
    CONF_NODE,
    CONF_SCAN_INTERVAL_DEVICE_TRACKER,
    CONF_SELECT_TEMP_UI_DEVICE,
    CONF_UI_DEVICES_TO_REMOVE,
    DEF_API_REQUEST_TIMEOUT,
    DEF_EVENTS_OPTIONS,
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
from .exceptions import (
    DeviceTrackerMeshTimeout,
    GeneralException,
    GeneralMeshTimeout,
    IntensiveTaskRunning,
)
from .helpers import (
    get_mesh_device_for_config_entry,
    remove_velop_device_from_registry,
    remove_velop_entity_from_registry,
)
from .logger import Logger
from .service_handler import LinksysVelopServiceHandler
from .types import CoordinatorTypes, LinksysVelopConfigEntry, LinksysVelopData

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)
_SETUP_PLATFORMS: list[str] = []


async def async_remove_config_entry_device(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Allow device removal.

    Do not allow the Mesh device to be removed
    """
    log_formatter = Logger(unique_id=config_entry.unique_id)

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

    log_formatter = Logger(unique_id=config_entry.unique_id)
    _LOGGER.debug(log_formatter.format("entered"))

    # region #-- initialise runtime data --#
    config_entry.runtime_data = LinksysVelopData()
    # endregion

    _LOGGER.debug(log_formatter.format("setting up Mesh for the coordinator"))
    mesh: Mesh = Mesh(
        node=config_entry.options[CONF_NODE],
        password=config_entry.options[CONF_PASSWORD],
        request_timeout=config_entry.options.get(
            CONF_API_REQUEST_TIMEOUT, DEF_API_REQUEST_TIMEOUT
        ),
        session=async_get_clientsession(hass=hass),
    )

    # region #-- test auth --#
    valid_auth: bool = await mesh.async_test_credentials()
    if not valid_auth:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="failed_login",
        )
    # endregion

    try:
        await mesh.async_initialise()
        config_entry.runtime_data.mesh = mesh
    except MeshTimeoutError as exc:
        exc_mesh_timeout: GeneralMeshTimeout = GeneralMeshTimeout(
            translation_domain=DOMAIN,
            translation_key="initialise_mesh_timeout",
            translation_placeholders={
                "current_timeout": config_entry.options.get(
                    CONF_API_REQUEST_TIMEOUT, DEF_API_REQUEST_TIMEOUT
                )
            },
        )
        raise exc_mesh_timeout from exc

    # region #-- setup the coordinators --#
    coordinator_name_suffix: str = ""
    if getattr(log_formatter, "_unique_id"):
        coordinator_name_suffix += f" ({getattr(log_formatter, '_unique_id')})"
    # region #--- mesh coordinator --#
    _LOGGER.debug(log_formatter.format("setting up the mesh coordinator"))
    coordinator_name = f"{DOMAIN} mesh{coordinator_name_suffix}"
    config_entry.runtime_data.coordinators[CoordinatorTypes.MESH] = (
        LinksysVelopUpdateCoordinator(
            hass,
            _LOGGER,
            coordinator_name,
            config_entry=config_entry,
            update_interval_secs=config_entry.options.get(
                CONF_SCAN_INTERVAL, DEF_SCAN_INTERVAL
            ),
        )
    )
    await config_entry.runtime_data.coordinators[
        CoordinatorTypes.MESH
    ].async_config_entry_first_refresh()
    # endregion
    # region #-- speedtest coordinator --#
    if MeshCapability.GET_SPEEDTEST_RESULTS in mesh.capabilities:
        _LOGGER.debug(log_formatter.format("setting up the speedtest coordinator"))
        coordinator_name = f"{DOMAIN} speedtest{coordinator_name_suffix}"
        config_entry.runtime_data.coordinators[CoordinatorTypes.SPEEDTEST] = (
            LinksysVelopUpdateCoordinatorSpeedtest(
                hass,
                _LOGGER,
                coordinator_name,
                config_entry=config_entry,
                update_interval_secs=config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEF_SCAN_INTERVAL
                ),
            )
        )
        await config_entry.runtime_data.coordinators[
            CoordinatorTypes.SPEEDTEST
        ].async_config_entry_first_refresh()
    # endregion
    # region #-- channel scan coordinator --#
    if MeshCapability.GET_CHANNEL_SCAN_STATUS in mesh.capabilities:
        _LOGGER.debug(log_formatter.format("setting up the channel scan coordinator"))
        coordinator_name = f"{DOMAIN} channel scan{coordinator_name_suffix}"
        config_entry.runtime_data.coordinators[CoordinatorTypes.CHANNEL_SCAN] = (
            LinksysVelopUpdateCoordinatorChannelScan(
                hass,
                _LOGGER,
                coordinator_name,
                config_entry=config_entry,
                update_interval_secs=config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEF_SCAN_INTERVAL
                ),
            )
        )
        await config_entry.runtime_data.coordinators[
            CoordinatorTypes.CHANNEL_SCAN
        ].async_config_entry_first_refresh()
    # endregion
    # endregion

    # region #-- setup the timer for device trackers --#
    async def async_device_tracker_update(_: datetime) -> None:
        """Retrieve the tracked devices from the Mesh."""

        if config_entry.runtime_data.mesh_is_rebooting:
            return

        try:
            devices: list[Device] = await mesh.async_get_device_from_id(
                config_entry.options.get(CONF_DEVICE_TRACKERS, []), True
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
        except (MeshConnectionError, MeshTimeoutError):
            if len(config_entry.runtime_data.intensive_running_tasks) > 0:
                exc: IntensiveTaskRunning = IntensiveTaskRunning(
                    translation_domain=DOMAIN,
                    translation_key="intensive_task",
                    translation_placeholders={
                        "tasks": config_entry.runtime_data.intensive_running_tasks
                    },
                )
                _LOGGER.warning(exc)
            else:
                exc_timeout: DeviceTrackerMeshTimeout = DeviceTrackerMeshTimeout(
                    translation_domain=DOMAIN,
                    translation_key="device_tracker_timeout",
                )
                _LOGGER.warning(exc_timeout)
        except Exception as err:
            exc_general: GeneralException = GeneralException(
                translation_domain=DOMAIN,
                translation_key="general",
                translation_placeholders={
                    "exc_type": type(err),
                    "exc_msg": str(err),
                },
            )
            _LOGGER.warning(exc_general)
        else:
            for device in devices:
                async_dispatcher_send(
                    hass,
                    f"{SIGNAL_DEVICE_TRACKER_UPDATE}_{device.unique_id}",
                    device,
                )

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
        with contextlib.suppress(ValueError):
            _SETUP_PLATFORMS.remove(SELECT_DOMAIN)
    if len(config_entry.options.get(CONF_DEVICE_TRACKERS, [])) > 0:
        _SETUP_PLATFORMS.append(DEVICE_TRACKER_DOMAIN)
    else:
        with contextlib.suppress(ValueError):
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
            if adapter := list(device[0].network):
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

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry
) -> bool:
    """Cleanup when unloading a config entry."""
    log_formatter = Logger(unique_id=config_entry.unique_id)
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
