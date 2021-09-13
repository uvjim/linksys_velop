import logging
from typing import List

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_COORDINATOR,
    DOMAIN,
    SIGNAL_UPDATE_DEVICE_TRACKER,
)
from .const import (
    CONF_DEVICE_TRACKERS
)
from .data_update_coordinator import LinksysVelopDataUpdateCoordinator
from .entity_helpers import (
    LinksysVelopDeviceTracker,
)
from .pyvelop.device import Device
from .pyvelop.mesh import Mesh

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """"""

    device_trackers: List[str] = config.options.get(CONF_DEVICE_TRACKERS, [])

    coordinator: LinksysVelopDataUpdateCoordinator = hass.data[DOMAIN][config.entry_id][CONF_COORDINATOR]
    mesh: Mesh = coordinator.data

    for device_tracker in device_trackers:
        async_add_entities([LinksysVelopMeshDeviceTracker(
            hass=hass,
            config=config,
            device=await mesh.async_get_device_from_id(device_id=device_tracker)
        )])


class LinksysVelopMeshDeviceTracker(LinksysVelopDeviceTracker):
    """"""

    _latest_dt_status: Device

    def __init__(self, hass: HomeAssistant, config: ConfigEntry, device: Device) -> None:

        self._config = config
        coordinator: LinksysVelopDataUpdateCoordinator = hass.data[DOMAIN][self._config.entry_id][CONF_COORDINATOR]
        self._device: Device = device

        super().__init__(identity=self._device.unique_id)

        self._attribute: str = self._device.name
        self._mesh: Mesh = coordinator.data
        self._offline_at: int = 0

    @callback
    def _update_callback(self, devices: List[Device]):
        self._latest_dt_status = [
            device
            for device in devices
            if device.unique_id == self._device.unique_id
        ][0]
        self.async_schedule_update_ha_state(force_refresh=True)

    async def async_added_to_hass(self) -> None:
        """"""

        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=SIGNAL_UPDATE_DEVICE_TRACKER,
                target=self._update_callback,
            )
        )

    async def async_update(self) -> None:
        """"""

        if self._latest_dt_status.status:
            if not self.is_connected:
                self._offline_at = 0
        else:
            if self.is_connected:
                if not self._offline_at:
                    self._offline_at = self._latest_dt_status.results_time

                if self._offline_at + self._config.options[CONF_CONSIDER_HOME] > self._latest_dt_status.results_time:
                    return

        self._device = self._latest_dt_status

    @property
    def is_connected(self) -> bool:
        """"""

        return self._device.status

    @property
    def mac_address(self) -> str:
        """"""

        ret = ""
        mac_address = [adapter for adapter in self._device.connected_adapters]
        if mac_address:
            ret = mac_address[0].get("mac", "")

        return ret
