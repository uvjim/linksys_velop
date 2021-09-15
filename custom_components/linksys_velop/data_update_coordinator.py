"""Manage fetching data from a single endpoint"""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_NODE,
    DOMAIN,
    SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS,
    SIGNAL_UPDATE_SPEEDTEST_STATUS,
)
from pyvelop.mesh import Mesh

_LOGGER = logging.getLogger(__name__)


class LinksysVelopDataUpdateCoordinator(DataUpdateCoordinator):
    """Manage fetching data from a single endpoint"""

    _mesh: Mesh

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Constructor"""

        self._hass = hass
        self._mesh = Mesh(node=config_entry.options[CONF_NODE], password=config_entry.options[CONF_PASSWORD])
        update_interval = timedelta(seconds=config_entry.options[CONF_SCAN_INTERVAL])
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> Mesh:
        """Fetch the latest data from the source

        Will signal relevant sensors that have a state that needs updating more frequently
        """

        try:
            await self._mesh.async_gather_details()
            if self._mesh.async_get_speedtest_state():
                async_dispatcher_send(self._hass, SIGNAL_UPDATE_SPEEDTEST_STATUS)
            if self._mesh.async_get_update_state():
                async_dispatcher_send(self._hass, SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS)
        except Exception as err:
            _LOGGER.error(err)

        return self._mesh
