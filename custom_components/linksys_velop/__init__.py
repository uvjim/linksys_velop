"""The Linksys Velop integration."""

# region #-- imports --#
import logging
import uuid
from typing import Any

from awesomeversion import AwesomeVersion
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, Platform
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.typing import ConfigType
from pyvelop.mesh import Mesh
from pyvelop.mesh_entity import AdapterInfo, DeviceEntity

from .const import (
    CONF_API_REQUEST_TIMEOUT,
    CONF_DEVICE_TRACKERS,
    CONF_DEVICE_TRACKERS_TO_REMOVE,
    CONF_NODE,
    CONF_REDACT_OPTIONS,
    CONF_SCAN_INTERVAL_DEVICE_TRACKER,
    CONF_SELECT_TEMP_UI_DEVICE,
    CONF_UI_DEVICES_TO_REMOVE,
    CONF_UI_PLACEHOLDER_DEVICE_ID,
    DEF_API_REQUEST_TIMEOUT,
    DEF_SCAN_INTERVAL,
    DEF_SCAN_INTERVAL_DEVICE_TRACKER,
    DOMAIN,
    MIN_HA_VERSION,
)
from .coordinator import (
    LinksysVelopConfigEntry,
    LinksysVelopDataUpdateCoordinatorMultiUse,
    LinksysVelopRuntimeData,
    get_mesh_device_for_config_entry,
)
from .helpers import (
    async_get_integration_version,
    remove_velop_device_from_registry,
    remove_velop_entity_from_registry,
)
from .logger import Logger
from .service_handler import LinksysVelopServiceHandler

# endregion

_LOGGER: Logger = Logger(logging.getLogger(__name__))
_PLATFORMS: tuple[Platform, ...] = (
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.EVENT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.UPDATE,
)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Allow device removal.

    Do not allow the Mesh device to be removed
    """

    mesh_id: set = {(DOMAIN, config_entry.entry_id)}
    if device_entry.identifiers.intersection(mesh_id):
        _LOGGER.error("Attempt to remove the Mesh device rejected")
        return False

    return True


async def async_migrate_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
) -> bool:
    """Migrate entries."""

    _LOGGER.debug(
        "migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    new_data: dict[str, Any] = {**config_entry.data}
    new_options: dict[str, Any] = {**config_entry.options}
    ret: bool = False

    if config_entry.version == 1:
        # region #-- migrate the ui device id --#
        ## v1 only set this in the ui_devices, however, this causes issues with multiple instances.
        ## if the placeholder device is already in use, ensure it exists in the data so the ConfigEntry
        ## can pick it up.
        ## The placeholder device was an all 0 guid - this will be randomised from v2 onwards.

        # placeholder device is enabled and it isn't set in data
        if (
            config_entry.options.get(CONF_SELECT_TEMP_UI_DEVICE, False)
            and new_data.get(CONF_UI_PLACEHOLDER_DEVICE_ID) is None
        ):
            new_data[CONF_UI_PLACEHOLDER_DEVICE_ID] = str(uuid.UUID(int=0))

        # endregion

        # region #-- migrate the ui devices/trackers that should be removed --#
        new_data[CONF_DEVICE_TRACKERS_TO_REMOVE] = new_options.pop(
            CONF_DEVICE_TRACKERS_TO_REMOVE, []
        )
        new_data[CONF_UI_DEVICES_TO_REMOVE] = new_options.pop(
            CONF_UI_DEVICES_TO_REMOVE, []
        )
        # endregion

        # region #-- remove old options --#
        new_options.pop("logging_jnap_response", None)
        new_options.pop("logging_serial", None)
        new_options.pop("logging_mode", None)
        new_options.pop("logging_options", None)
        new_options.pop("ui_devices_missing", None)
        new_options.pop("tracked_missing", None)
        # endregion

        ret = hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            options=new_options,
            version=2,
        )

    _LOGGER.debug(
        "migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return ret


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""

    if AwesomeVersion(HA_VERSION) < AwesomeVersion(MIN_HA_VERSION):
        msg = (
            "This integration requires at least Home Assistant version "
            f"{MIN_HA_VERSION}, you are running version {HA_VERSION}. "
            "Please upgrade Home Assistant to continue using this integration."
        )
        _LOGGER.critical(msg)
        return False

    # region #-- service definition --#
    _LOGGER.debug("registering services")
    LinksysVelopServiceHandler(hass).register_services()
    # endregion

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry
) -> bool:
    """Create a config entry."""

    # region #-- register services if they haven't been registered --#
    # this could happen if all instances were disabled (removes the services)
    # but then one is enabled again - async_setup doesn't run again so we'll recreate here.
    if not hass.services.async_services_for_domain(DOMAIN):
        LinksysVelopServiceHandler(hass).register_services()
    # endregion

    _LOGGER.debug(
        "using integration version: %s",
        await async_get_integration_version(hass),
    )

    # region #--- mesh coordinator --#
    coordinator_name_suffix: str = f" ({config_entry.title})"
    update_interval: float = config_entry.options.get(
        CONF_SCAN_INTERVAL, DEF_SCAN_INTERVAL
    )
    _LOGGER.debug(
        "setting up the mesh coordinator with interval: %s",
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
    mesh_api: Mesh = Mesh(
        node=config_entry.options[CONF_NODE],
        password=config_entry.options[CONF_PASSWORD],
        request_timeout=config_entry.options.get(
            CONF_API_REQUEST_TIMEOUT, DEF_API_REQUEST_TIMEOUT
        ),
        session=async_get_clientsession(hass=hass),
        supplementary_redactions=config_entry.options.get(CONF_REDACT_OPTIONS),
    )
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse = (
        LinksysVelopDataUpdateCoordinatorMultiUse(
            hass,
            _LOGGER.get_logger(),
            config_entry=config_entry,
            name=coordinator_name,
            api=mesh_api,
            **update_intervals,
        )
    )
    # endregion

    # region #-- initialise runtime data --#
    config_entry.runtime_data = LinksysVelopRuntimeData(
        api=mesh_api,
        coordinator=coordinator,
    )
    await coordinator.async_config_entry_first_refresh()
    # endregion

    # region #-- setup the platforms --#
    _LOGGER.debug(
        "setting up platforms: %s",
        list(map(str, _PLATFORMS)),
    )
    await hass.config_entries.async_forward_entry_setups(config_entry, _PLATFORMS)
    # endregion

    # region #-- remove unnecessary ui devices --#
    _LOGGER.debug("cleaning up ui devices")
    new_data: dict[str, Any] = {**config_entry.data}
    for ui_device in new_data.get(CONF_UI_DEVICES_TO_REMOVE, []):
        remove_velop_device_from_registry(hass, ui_device)
    if CONF_UI_DEVICES_TO_REMOVE in new_data:
        new_data[CONF_UI_DEVICES_TO_REMOVE] = []
    # endregion

    # region #-- remove unnecessary device trackers --#
    _LOGGER.debug("cleaning up device trackers")
    connections: set[tuple[str, str]] = set()
    mesh_device: DeviceEntry | None = get_mesh_device_for_config_entry(
        hass, config_entry
    )
    if mesh_device is not None:
        connections = mesh_device.connections
    for tracker in new_data.get(CONF_DEVICE_TRACKERS_TO_REMOVE, []):
        # region #-- remove entity --#
        remove_velop_entity_from_registry(
            hass,
            config_entry.entry_id,
            f"{config_entry.entry_id}::{Platform.DEVICE_TRACKER}::{tracker}",
        )
        # endregion
        # region #-- remove connection from the mesh device --#
        mesh_data = config_entry.runtime_data.coordinator.data.mesh
        if mesh_data is not None:
            device: DeviceEntity | None = next(
                (d for d in mesh_data.devices if d.unique_id.value == tracker),
                None,
            )
            if device is not None:
                adi: AdapterInfo | None = next(iter(device.adapter_info), None)
                if adi is not None:
                    connections.discard(
                        (
                            dr.CONNECTION_NETWORK_MAC,
                            dr.format_mac(adi.mac),
                        )
                    )
        # endregion

    # region #-- update the mesh device --#
    device_registry: DeviceRegistry = dr.async_get(hass)
    mesh_device = get_mesh_device_for_config_entry(hass, config_entry)
    if mesh_device is not None:
        device_registry.async_update_device(mesh_device.id, new_connections=connections)
    # endregion

    if CONF_DEVICE_TRACKERS_TO_REMOVE in new_data:
        new_data[CONF_DEVICE_TRACKERS_TO_REMOVE] = []

    hass.config_entries.async_update_entry(config_entry, data=new_data)
    # endregion

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry
) -> bool:
    """Cleanup when unloading a config entry."""
    _LOGGER.debug("entered")

    # region #-- remove services but only if there are no other instances --#
    if not hass.config_entries.async_loaded_entries(DOMAIN):
        _LOGGER.debug("unregistering services")
        LinksysVelopServiceHandler(hass).unregister_services()
    # endregion

    # region #-- clean up the platforms --#
    _LOGGER.debug("cleaning up platforms: %s", _PLATFORMS)
    ret = await hass.config_entries.async_unload_platforms(config_entry, _PLATFORMS)
    # endregion

    _LOGGER.debug("exited")
    return ret
