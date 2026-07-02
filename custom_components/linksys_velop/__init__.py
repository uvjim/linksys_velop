"""The Linksys Velop integration."""

# region #-- imports --#
import contextlib
import copy
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from pyvelop.mesh import Mesh, MeshCapability
from pyvelop.mesh_entity import DeviceEntity

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
    PLATFORMS,
    SELECT_DOMAIN,
)
from .coordinator import (
    LinksysVelopUpdateCoordinator,
    LinksysVelopUpdateCoordinatorChannelScan,
    LinksysVelopUpdateCoordinatorSpeedtest,
)
from .helpers import (
    async_get_integration_version,
    get_mesh_device_for_config_entry,
    remove_velop_device_from_registry,
    remove_velop_entity_from_registry,
)
from .logger import Logger
from .service_handler import LinksysVelopServiceHandler
from .types import (
    CoordinatorTypes,
    LinksysVelopConfigEntry,
    LinksysVelopRuntimeData,
)

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

    mesh_id: set = {(DOMAIN, config_entry.entry_id)}
    if device_entry.identifiers.intersection(mesh_id):
        _LOGGER.error(
            config_entry.runtime_data.log_formatter(
                "Attempt to remove the Mesh device rejected"
            )
        )
        return False

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry
) -> bool:
    """Create a config entry."""

    global _SETUP_PLATFORMS

    log_formatter: Logger = Logger(
        unique_id=config_entry.unique_id if config_entry.unique_id is not None else ""
    )
    _LOGGER.debug(log_formatter.format("entered"))

    # region #-- initialise runtime data --#
    config_entry.runtime_data = LinksysVelopRuntimeData(
        log_formatter=log_formatter.format,
        mesh=Mesh(
            node=config_entry.options[CONF_NODE],
            password=config_entry.options[CONF_PASSWORD],
            request_timeout=config_entry.options.get(
                CONF_API_REQUEST_TIMEOUT, DEF_API_REQUEST_TIMEOUT
            ),
            session=async_get_clientsession(hass=hass),
        ),
    )
    # endregion

    _LOGGER.debug(
        config_entry.runtime_data.log_formatter("using integration version: %s"),
        await async_get_integration_version(hass),
    )

    # region #-- setup the coordinators --#
    coordinator_name_suffix: str = ""
    if getattr(log_formatter, "_unique_id"):
        coordinator_name_suffix += f" ({getattr(log_formatter, '_unique_id')})"

    # region #--- mesh coordinator --#
    update_interval: float = config_entry.options.get(
        CONF_SCAN_INTERVAL, DEF_SCAN_INTERVAL
    )
    _LOGGER.debug(
        config_entry.runtime_data.log_formatter(
            "setting up the mesh coordinator with interval: %s"
        ),
        update_interval,
    )
    coordinator_name = f"{DOMAIN} mesh{coordinator_name_suffix}"
    update_intervals: dict[str, float] = {
        "update_interval_secs": update_interval,
    }
    if len(config_entry.options.get(CONF_DEVICE_TRACKERS, [])) > 0:
        update_intervals["tracker_update_interval_secs"] = config_entry.options.get(
            CONF_SCAN_INTERVAL_DEVICE_TRACKER, DEF_SCAN_INTERVAL_DEVICE_TRACKER
        )
    config_entry.runtime_data.coordinators[CoordinatorTypes.MESH] = (
        LinksysVelopUpdateCoordinator(
            hass,
            _LOGGER,
            coordinator_name,
            config_entry=config_entry,
            **update_intervals,
        )
    )
    await config_entry.runtime_data.coordinators[
        CoordinatorTypes.MESH
    ].async_config_entry_first_refresh()
    # endregion

    # region #-- speedtest coordinator --#
    if (
        MeshCapability.GET_SPEEDTEST_RESULTS
        in config_entry.runtime_data.mesh.capabilities
    ):
        update_interval: float = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEF_SCAN_INTERVAL
        )
        _LOGGER.debug(
            config_entry.runtime_data.log_formatter(
                "setting up the speedtest coordinator with interval: %s"
            ),
            update_interval,
        )
        coordinator_name = f"{DOMAIN} speedtest{coordinator_name_suffix}"
        config_entry.runtime_data.coordinators[CoordinatorTypes.SPEEDTEST] = (
            LinksysVelopUpdateCoordinatorSpeedtest(
                hass,
                _LOGGER,
                coordinator_name,
                config_entry=config_entry,
                update_interval_secs=update_interval,
            )
        )
        await config_entry.runtime_data.coordinators[
            CoordinatorTypes.SPEEDTEST
        ].async_config_entry_first_refresh()
    # endregion

    # region #-- channel scan coordinator --#
    if (
        MeshCapability.GET_CHANNEL_SCAN_STATUS
        in config_entry.runtime_data.mesh.capabilities
    ):
        update_interval: float = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEF_SCAN_INTERVAL
        )
        _LOGGER.debug(
            config_entry.runtime_data.log_formatter(
                "setting up the channel scan coordinator with interval: %s"
            ),
            update_interval,
        )
        coordinator_name = f"{DOMAIN} channel scan{coordinator_name_suffix}"
        config_entry.runtime_data.coordinators[CoordinatorTypes.CHANNEL_SCAN] = (
            LinksysVelopUpdateCoordinatorChannelScan(
                hass,
                _LOGGER,
                coordinator_name,
                config_entry=config_entry,
                update_interval_secs=update_interval,
            )
        )
        await config_entry.runtime_data.coordinators[
            CoordinatorTypes.CHANNEL_SCAN
        ].async_config_entry_first_refresh()
    # endregion

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
    if (
        config_entry.options.get(CONF_SELECT_TEMP_UI_DEVICE, DEF_SELECT_TEMP_UI_DEVICE)
        or MeshCapability.GET_SCHEDULED_REBOOT_SETTINGS
        in config_entry.runtime_data.mesh.capabilities
    ):
        _SETUP_PLATFORMS.append(SELECT_DOMAIN)
    else:
        with contextlib.suppress(ValueError):
            _SETUP_PLATFORMS.remove(SELECT_DOMAIN)
    if len(config_entry.options.get(CONF_DEVICE_TRACKERS, [])) > 0:
        _SETUP_PLATFORMS.append(DEVICE_TRACKER_DOMAIN)
    else:
        with contextlib.suppress(ValueError):
            _SETUP_PLATFORMS.remove(DEVICE_TRACKER_DOMAIN)
    _LOGGER.debug(
        config_entry.runtime_data.log_formatter("setting up platforms: %s"),
        _SETUP_PLATFORMS,
    )
    await hass.config_entries.async_forward_entry_setups(config_entry, _SETUP_PLATFORMS)
    # endregion

    # region #-- remove unnecessary ui devices --#
    _LOGGER.debug(config_entry.runtime_data.log_formatter("cleaning up ui devices"))
    for ui_device in config_entry.options.get(CONF_UI_DEVICES_TO_REMOVE, []):
        remove_velop_device_from_registry(hass, ui_device)
    new_options = copy.deepcopy(dict(config_entry.options))
    new_options.get(CONF_UI_DEVICES_TO_REMOVE, []).clear()
    hass.config_entries.async_update_entry(config_entry, options=new_options)
    # endregion

    # region #-- remove unnecessary device trackers --#
    _LOGGER.debug(
        config_entry.runtime_data.log_formatter("cleaning up device trackers")
    )
    connections: set[tuple[str, str]] = set()
    mesh_device: DeviceEntry | None = get_mesh_device_for_config_entry(
        hass, config_entry
    )
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
        device: list[DeviceEntity]
        if device := [
            d for d in config_entry.runtime_data.mesh.devices if d.unique_id == tracker
        ]:
            if adapter := list(device[0].adapter_info):
                connections.discard(
                    (
                        dr.CONNECTION_NETWORK_MAC,
                        dr.format_mac(adapter[0].get("mac", "")),
                    )
                )
        # endregion

    # region #-- update the mesh device --#
    device_registry: DeviceRegistry = dr.async_get(hass)
    mesh_device = get_mesh_device_for_config_entry(hass, config_entry)
    if mesh_device is not None:
        device_registry.async_update_device(mesh_device.id, new_connections=connections)
    # endregion

    new_options = copy.deepcopy(dict(config_entry.options))
    new_options.get(CONF_DEVICE_TRACKERS_TO_REMOVE, []).clear()
    hass.config_entries.async_update_entry(config_entry, options=new_options)
    # endregion

    # region #-- service definition --#
    _LOGGER.debug(config_entry.runtime_data.log_formatter("registering services"))
    LinksysVelopServiceHandler(hass).register_services()
    # endregion

    # region #-- listen for config changes --#
    _LOGGER.debug(
        config_entry.runtime_data.log_formatter("listening for config changes")
    )
    config_entry.async_on_unload(
        config_entry.add_update_listener(_async_update_listener)
    )
    # endregion

    _LOGGER.debug(config_entry.runtime_data.log_formatter("exited"))

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry
) -> bool:
    """Cleanup when unloading a config entry."""
    _LOGGER.debug(config_entry.runtime_data.log_formatter("entered"))

    # region #-- remove services but only if there are no other instances --#
    all_config_entries = hass.config_entries.async_entries(domain=DOMAIN)
    _LOGGER.debug(
        config_entry.runtime_data.log_formatter("%i instances"), len(all_config_entries)
    )
    if len(all_config_entries) == 1:
        _LOGGER.debug(config_entry.runtime_data.log_formatter("unregistering services"))
        LinksysVelopServiceHandler(hass).unregister_services()
    # endregion

    # region #-- clean up the platforms --#
    _LOGGER.debug(
        config_entry.runtime_data.log_formatter("cleaning up platforms: %s"),
        _SETUP_PLATFORMS,
    )
    ret = await hass.config_entries.async_unload_platforms(
        config_entry, _SETUP_PLATFORMS
    )
    # endregion

    _LOGGER.debug(config_entry.runtime_data.log_formatter("exited"))
    return ret


async def _async_update_listener(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Reload the config entry."""
    await hass.config_entries.async_reload(config_entry.entry_id)
