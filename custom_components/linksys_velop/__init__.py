"""The Linksys Velop integration"""

# region #-- imports --#
import datetime
import logging
from datetime import timedelta
from typing import (
    List,
    Optional,
)

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryNotReady
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_AUTHOR as PYVELOP_AUTHOR
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_NAME as PYVELOP_NAME
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_VERSION as PYVELOP_VERSION
from pyvelop.device import Device
from pyvelop.mesh import Mesh
from pyvelop.node import Node

from .const import (
    CONF_COORDINATOR,
    CONF_DEVICE_TRACKERS,
    CONF_SCAN_INTERVAL_DEVICE_TRACKER,
    CONF_SERVICES_HANDLER,
    CONF_UNSUB_UPDATE_LISTENER,
    DEF_SCAN_INTERVAL,
    DEF_SCAN_INTERVAL_DEVICE_TRACKER,
    DOMAIN,
    PLATFORMS,
    SIGNAL_UPDATE_DEVICE_TRACKER,
    SIGNAL_UPDATE_SPEEDTEST_STATUS,
)
from .data_update_coordinator import LinksysVelopDataUpdateCoordinator
from .logger import VelopLogger
from .service_handler import LinksysVelopServiceHandler
# endregion

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Setup a config entry"""

    # region #-- prepare the memory storage --#
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(config_entry.entry_id, {})
    # endregion

    # region #-- setup the coordinator for data updates --#
    coordinator = LinksysVelopDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
    )

    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady(coordinator.last_exception)

    hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR] = coordinator
    # endregion

    # region #-- setup the platforms --#
    setup_platforms: List[str] = list(filter(None, PLATFORMS))
    hass.config_entries.async_setup_platforms(config_entry, setup_platforms)
    # endregion

    # region #-- Service Definition --#
    services = LinksysVelopServiceHandler(hass=hass, config_entry=config_entry)
    services.register_services()
    hass.data[DOMAIN][config_entry.entry_id][CONF_SERVICES_HANDLER] = services
    # endregion

    # region #-- listen for config changes --#
    hass.data[DOMAIN][config_entry.entry_id][CONF_UNSUB_UPDATE_LISTENER] = config_entry.add_update_listener(
        _async_update_listener
    )
    # endregion

    async def device_tracker_update(_: datetime.datetime) -> None:
        """Manage the device tracker updates

        Uses the _ variable to ignore IDE checking for unused variables

        Gets the device list from the mesh before dispatching the message

        :param _: datetime object for when the event was fired
        :return: None
        """

        mesh: Mesh = coordinator.data
        try:
            devices: List[Device] = await mesh.async_get_devices()
        except Exception as err:
            _LOGGER.error(VelopLogger().message_format("%s"), err)
        else:
            async_dispatcher_send(hass, SIGNAL_UPDATE_DEVICE_TRACKER, devices)

    # region #-- set up the timer for checking device trackers --#
    if config_entry.options[CONF_DEVICE_TRACKERS]:  # only do setup if device trackers were selected
        await device_tracker_update(datetime.datetime.now())  # update before setting the timer
        scan_interval = config_entry.options.get(CONF_SCAN_INTERVAL_DEVICE_TRACKER, DEF_SCAN_INTERVAL_DEVICE_TRACKER)
        config_entry.async_on_unload(
            async_track_time_interval(hass, device_tracker_update, timedelta(seconds=scan_interval))
        )
    # endregion

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Cleanup when unloading a config entry"""

    # region #-- close the mesh connection --#
    coordinator: LinksysVelopDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
    mesh: Mesh = coordinator.data
    await mesh.close()
    # endregion

    # region #-- unsubscribe from listening for updates --#
    hass.data[DOMAIN][config_entry.entry_id][CONF_UNSUB_UPDATE_LISTENER]()
    # endregion

    # region #-- remove services --#
    services: LinksysVelopServiceHandler = hass.data[DOMAIN][config_entry.entry_id][CONF_SERVICES_HANDLER]
    services.unregister_services()
    # endregion

    # region #-- clean up the platforms --#
    ret = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    if ret:
        hass.data[DOMAIN].pop(config_entry.entry_id)
        ret = True
    else:
        ret = False
    # endregion

    return ret


async def _async_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Reload the config entry"""

    return await hass.config_entries.async_reload(config_entry.entry_id)


# region #-- base entities --#
class LinksysVelopMeshEntity(CoordinatorEntity):
    """"""

    def __init__(
        self,
        coordinator: LinksysVelopDataUpdateCoordinator,
        config_entry: ConfigEntry
    ) -> None:
        """"""

        super().__init__(coordinator=coordinator)
        self._config = config_entry
        self._mesh: Mesh = coordinator.data

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information of the entity."""

        # noinspection HttpUrlsUsage
        ret = DeviceInfo(**{
            "configuration_url": f"http://{self._mesh.connected_node}",
            "identifiers": {(DOMAIN, self._config.entry_id)},
            "manufacturer": PYVELOP_AUTHOR,
            "model": f"{PYVELOP_NAME} ({PYVELOP_VERSION})",
            "name": "Mesh",
            "sw_version": "",
        })
        return ret


class LinksysVelopNodeEntity(CoordinatorEntity):
    """"""

    _node_id: str

    def __init__(
        self,
        coordinator: LinksysVelopDataUpdateCoordinator,
        config_entry: ConfigEntry
    ) -> None:
        """"""

        super().__init__(coordinator=coordinator)
        self._config = config_entry
        self._mesh: Mesh = coordinator.data
        self._node: Node = self._get_node()

    def _get_node(self) -> Optional[Node]:
        """Get the current node"""

        node = [n for n in self._mesh.nodes if n.unique_id == self._node_id]
        if node:
            return node[0]

        return None

    def _handle_coordinator_update(self) -> None:
        """Update the node information when the coordinator updates"""

        self._node = self._get_node()
        super()._handle_coordinator_update()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information of the entity."""

        ret = DeviceInfo(**{
            "hw_version": self._node.hardware_version,
            "identifiers": {(DOMAIN, self._node.serial)},
            "model": self._node.model,
            "name": self._node.name,
            "manufacturer": self._node.manufacturer,
            "sw_version": self._node.firmware.get("version", ""),
        })

        return ret
# endregion
