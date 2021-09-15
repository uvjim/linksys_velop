"""The Linksys Velop integration"""

import datetime
import logging
from datetime import timedelta
from typing import List

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

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
from .service_handler import LinksysVelopServiceHandler
from pyvelop.device import Device
from pyvelop.mesh import Mesh

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
    hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR] = coordinator
    # endregion

    # region #-- setup the platforms --#
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)
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
        devices: List[Device] = await mesh.async_get_devices()
        async_dispatcher_send(hass, SIGNAL_UPDATE_DEVICE_TRACKER, devices)

    # region #-- setup the timer for checking device trackers --#
    if config_entry.options[CONF_DEVICE_TRACKERS]:  # only do setup if device trackers were selected
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
