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
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType
from pyvelop.mesh import Mesh

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


def _create_coordinator(
    hass: HomeAssistant, entry: LinksysVelopConfigEntry, api: Mesh
) -> LinksysVelopDataUpdateCoordinatorMultiUse:
    """Factory to create the DataUpdateCoordinator.

    :param hass: The Home Assistant core instance.
    :param entry: The config entry containing polling intervals.
    :param api: The Mesh API instance to be used by the coordinator.
    :returns: A configured LinksysVelopDataUpdateCoordinatorMultiUse instance.
    """
    update_interval = entry.options.get(CONF_SCAN_INTERVAL, DEF_SCAN_INTERVAL)

    intervals = {"update_interval_secs": update_interval}
    if entry.options.get(CONF_DEVICE_TRACKERS):
        intervals["tracker_update_interval_secs"] = entry.options.get(
            CONF_SCAN_INTERVAL_DEVICE_TRACKER, DEF_SCAN_INTERVAL_DEVICE_TRACKER
        )

    return LinksysVelopDataUpdateCoordinatorMultiUse(
        hass,
        _LOGGER.get_logger(),
        config_entry=entry,
        name=f"{DOMAIN} mesh ({entry.title})",
        api=api,
        **intervals,
    )


def _create_mesh_api(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry
) -> Mesh:
    """Factory to create the Mesh API instance.

    :param hass: The Home Assistant core instance.
    :param config_entry: The config entry containing API credentials and options.
    :returns: An initialized Mesh API instance.
    """
    return Mesh(
        node=config_entry.options[CONF_NODE],
        password=config_entry.options[CONF_PASSWORD],
        request_timeout=config_entry.options.get(
            CONF_API_REQUEST_TIMEOUT, DEF_API_REQUEST_TIMEOUT
        ),
        session=async_get_clientsession(hass=hass),
        supplementary_redactions=config_entry.options.get(CONF_REDACT_OPTIONS),
    )


async def async_cleanup_device_registry(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry
) -> dict[str, Any]:
    """Handles removal of unwanted devices and trackers from the registry.

    :param hass: The Home Assistant core instance.
    :param config_entry: The config entry containing the list of devices/trackers to remove.
    :returns: A updated data dictionary with cleanup lists cleared.
    """
    new_data = {**config_entry.data}

    # remove UI devices
    for ui_device in new_data.get(CONF_UI_DEVICES_TO_REMOVE, []):
        remove_velop_device_from_registry(hass, ui_device, config_entry.entry_id)
    new_data[CONF_UI_DEVICES_TO_REMOVE] = []

    # remove device trackers
    connections = set()
    mesh_device = get_mesh_device_for_config_entry(hass, config_entry)
    if mesh_device:
        connections = set(mesh_device.connections)

    for tracker in new_data.get(CONF_DEVICE_TRACKERS_TO_REMOVE, []):
        remove_velop_entity_from_registry(
            hass,
            config_entry.entry_id,
            f"{config_entry.entry_id}::{Platform.DEVICE_TRACKER}::{tracker}",
        )

        # update local connection set based on coordinator data
        mesh_data = config_entry.runtime_data.coordinator.data.mesh
        if mesh_data:
            device = next(
                (d for d in mesh_data.devices if d.unique_id.value == tracker), None
            )
            if device:
                adi = next(iter(device.adapter_info), None)
                if adi:
                    connections.discard(
                        (dr.CONNECTION_NETWORK_MAC, dr.format_mac(adi.mac))
                    )

    # update mesh device in registry
    if mesh_device:
        dr.async_get(hass).async_update_device(
            mesh_device.id, new_connections=connections
        )

    new_data[CONF_DEVICE_TRACKERS_TO_REMOVE] = []
    return new_data


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Allow device removal.

    Do not allow the Mesh device to be removed.

    :param hass: The Home Assistant core instance.
    :param config_entry: The config entry containing the list of devices/trackers to remove.
    :param device_entry: device entry from the Home Assistant registry.
    :returns: `True` when successful. `False` otherwise.
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
    """Migrate entries.

    :param hass: The Home Assistant core instance.
    :param config_entry: The config entry containing the list of devices/trackers to remove.
    :returns: `True` if successful, `False` otherwise.
    """

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
    """Set up the integration.

    :param hass: The Home Assistant core instance.
    :param config: Configuration dictionary provided by Home Assistant.
    :returns: `True` when successful, `False` otherwise.
    """

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
    """Create a config entry.

    :param hass: The Home Assistant core instance.
    :param config_entry: The config entry for this specific instance of the integration.
    :returns: True if setup was successful, False otherwise.
    """

    # ensure services are registered
    if not hass.services.async_services_for_domain(DOMAIN):
        LinksysVelopServiceHandler(hass).register_services()

    _LOGGER.debug(
        "using integration version: %s", await async_get_integration_version(hass)
    )

    # initialize API and Coordinator
    mesh_api = _create_mesh_api(hass, config_entry)
    coordinator = _create_coordinator(hass, config_entry, mesh_api)

    # initialize runtime data
    config_entry.runtime_data = LinksysVelopRuntimeData(
        api=mesh_api,
        coordinator=coordinator,
    )
    await coordinator.async_config_entry_first_refresh()

    # setup platforms
    _LOGGER.debug("setting up platforms: %s", list(map(str, _PLATFORMS)))
    await hass.config_entries.async_forward_entry_setups(config_entry, _PLATFORMS)

    # handle registry cleanup and update config entry data
    updated_data = await async_cleanup_device_registry(hass, config_entry)
    hass.config_entries.async_update_entry(config_entry, data=updated_data)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry
) -> bool:
    """Cleanup when unloading a config entry.

    :param hass: The Home Assistant core instance.
    :param config_entry: The config entry for this specific instance of the integration.
    :returns: True if setup was successful, False otherwise.
    """

    # remove services but only if there are no other instances
    if not hass.config_entries.async_loaded_entries(DOMAIN):
        _LOGGER.debug("unregistering services")
        LinksysVelopServiceHandler(hass).unregister_services()

    # clean up the platforms
    _LOGGER.debug("cleaning up platforms: %s", _PLATFORMS)
    ret = await hass.config_entries.async_unload_platforms(config_entry, _PLATFORMS)

    return ret
