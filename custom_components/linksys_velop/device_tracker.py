"""Device trackers for the mesh"""
import logging
from abc import ABC
from typing import (
    Callable,
    List,
    Optional,
)

import homeassistant.helpers.device_registry as dr
from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util
from pyvelop.device import Device
from pyvelop.exceptions import MeshDeviceNotFoundResponse
from pyvelop.mesh import Mesh

from .const import (
    CONF_COORDINATOR,
    CONF_DEVICE_TRACKERS,
    DEF_CONSIDER_HOME,
    DOMAIN,
    SIGNAL_UPDATE_DEVICE_TRACKER,
)
from .data_update_coordinator import LinksysVelopDataUpdateCoordinator
from .entity_helpers import (
    LinksysVelopDeviceTracker,
    LinksysVelopMeshEntity
)
from .logger import VelopLogger

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the device trackers based on a config entry"""

    device_trackers: List[str] = config.options.get(CONF_DEVICE_TRACKERS, [])

    coordinator: LinksysVelopDataUpdateCoordinator = hass.data[DOMAIN][config.entry_id][CONF_COORDINATOR]
    mesh: Mesh = coordinator.data
    entities: list = []

    # region #-- get the mesh device from the registry --#
    device_registry = dr.async_get(hass=hass)
    config_devices: List[dr.DeviceEntry] = dr.async_entries_for_config_entry(
        registry=device_registry,
        config_entry_id=config.entry_id
    )
    mesh_device = [
        d
        for d in config_devices
        if d.name.lower() == "mesh"
    ]
    # endregion

    for device_tracker in device_trackers:
        try:
            device = await mesh.async_get_device_from_id(device_id=device_tracker)
        except MeshDeviceNotFoundResponse:
            _LOGGER.warning(VelopLogger().message_format("Device tracker with id %s was not found"), device_tracker)
        else:
            # region #-- add the connection info to the mesh device --#
            if mesh_device:
                mac_address = [
                    adapter
                    for adapter in device.network
                ]
                # TODO: Fix up the try/except block when setting the minimum HASS version to 2022.2
                # HASS 2022.2 introduces some new ways of working with device_trackers, this makes
                # sure that the device_tracker MAC is listed as a connection against the mesh allowing
                # the device tracker to automatically enable and link to the mesh device.
                try:
                    device_registry.async_update_device(
                        device_id=mesh_device[0].id,
                        merge_connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac_address[0].get("mac")))},
                    )
                except TypeError:  # this will be thrown if merge_connections isn't available (device_id should be)
                    pass
            # endregion

            entities.append(
                LinksysVelopMeshDeviceTracker(
                    coordinator=coordinator,
                    device=device,
                    config=config,
                )
            )

    async_add_entities(entities)


class LinksysVelopMeshDeviceTracker(LinksysVelopDeviceTracker, LinksysVelopMeshEntity, ABC):
    """Representation of a device tracker"""

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator, config: ConfigEntry, device: Device) -> None:
        """Constructor"""

        self._attribute: str = device.name
        self._config: ConfigEntry = config
        self._consider_home_listener: Optional[Callable] = None
        self._device: Device = device
        self._device_id = device.unique_id
        self._identity: str = self._config.entry_id
        self._is_connected: bool = device.status
        self._log_formatter: VelopLogger = VelopLogger(unique_id=config.unique_id)
        self._mesh: Mesh = coordinator.data
        self._tracking: bool = False

    async def _async_get_current_device_status(self, evt: Optional[dt_util.dt.datetime] = None) -> None:
        """"""

        # region #-- get the current device status --#
        devices: List[Device] = await self._mesh.async_get_devices()
        device: List[Device] = [
            d
            for d in devices
            if d.unique_id == self._device_id
        ]
        if device:
            self._device = device[0]
        # endregion

        if self._is_connected != self._device.status:
            if evt:  # made it here because of the listener so must be offline now
                _LOGGER.debug(self._log_formatter.message_format("%s is offline"), self._device.name)
                self._is_connected = False
                self._consider_home_listener = None

        if not self._device.status:  # start listener for the CONF_CONSIDER_HOME period
            if not self._consider_home_listener and self._is_connected != self._device.status:
                _LOGGER.debug(
                    self._log_formatter.message_format("%s: setting consider home listener"), self._device.name
                )
                # noinspection PyTypeChecker
                self._consider_home_listener = async_track_point_in_time(
                    hass=self.hass,
                    action=self._async_get_current_device_status,
                    point_in_time=dt_util.dt.datetime.fromtimestamp(
                        int(self._device.results_time) +
                        self._config.options.get(CONF_CONSIDER_HOME, DEF_CONSIDER_HOME)
                    )
                )
        else:
            if self._is_connected != self._device.status:
                _LOGGER.debug(self._log_formatter.message_format("%s is online"), self._device.name)
            self._is_connected = True
            # stop listener if it is going
            if self._consider_home_listener:
                _LOGGER.debug(
                    self._log_formatter.message_format("%s: cancelling consider home listener"), self._device.name
                )
                self._consider_home_listener()
                self._consider_home_listener = None

        await self.async_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks and set initial status"""

        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=SIGNAL_UPDATE_DEVICE_TRACKER,
                target=self._async_get_current_device_status,
            )
        )

    @property
    def is_connected(self) -> bool:
        """Return True if the tracker is connected, False otherwise"""

        return self._is_connected

    @property
    def mac_address(self) -> str:
        """Set the MAC address for the tracker"""

        ret = ""
        mac_address = [adapter for adapter in self._device.connected_adapters]
        if mac_address:
            ret = mac_address[0].get("mac", "")

        return ret
