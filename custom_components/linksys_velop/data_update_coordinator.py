"""Manage fetching data from a single endpoint"""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyvelop.mesh import Mesh

from .const import (
    CONF_API_REQUEST_TIMEOUT,
    CONF_NODE,
    DEF_API_REQUEST_TIMEOUT,
    DOMAIN,
    SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS,
    SIGNAL_UPDATE_SPEEDTEST_STATUS,
)

_LOGGER = logging.getLogger(__name__)


class LinksysVelopDataUpdateCoordinator(DataUpdateCoordinator):
    """Manage fetching data from a single endpoint"""

    _mesh: Mesh

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Constructor"""

        self._hass = hass
        self._mesh = Mesh(
            node=config_entry.options[CONF_NODE],
            password=config_entry.options[CONF_PASSWORD],
            request_timeout=config_entry.options.get(CONF_API_REQUEST_TIMEOUT, DEF_API_REQUEST_TIMEOUT),
        )
        update_interval = timedelta(seconds=config_entry.options[CONF_SCAN_INTERVAL])
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self.async_update_data,
            update_interval=update_interval
        )

    async def async_update_data(self) -> Mesh:
        """Fetch the latest data from the source

        Will signal relevant sensors that have a state that needs updating more frequently or uses a state that is a
        combination of the real state and one assumed by an action
        """

        try:
            await self._mesh.async_gather_details()
            if self._mesh.speedtest_status:
                async_dispatcher_send(self._hass, SIGNAL_UPDATE_SPEEDTEST_STATUS)
            if self._mesh.check_for_update_status:
                async_dispatcher_send(self._hass, SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS)
        except Exception as err:
            if self._mesh:
                await self._mesh.close()
            raise UpdateFailed(err)

        return self._mesh
