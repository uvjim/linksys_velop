"""Device trackers."""

# region #-- imports --#
from __future__ import annotations

import copy
import logging
from typing import Callable, Dict, List, Optional

from homeassistant.components.device_tracker import CONF_CONSIDER_HOME
from homeassistant.components.device_tracker import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util
from pyvelop.device import Device
from pyvelop.exceptions import MeshDeviceNotFoundResponse
from pyvelop.mesh import Mesh

from . import _get_device_registry_entry
from .const import (CONF_COORDINATOR_MESH, CONF_DEVICE_TRACKERS,
                    DEF_CONSIDER_HOME, DOMAIN, ENTITY_SLUG,
                    SIGNAL_UPDATE_DEVICE_TRACKER)
from .logger import Logger

# endregion

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Add the entities."""
    device_trackers: List[LinksysVelopMeshDeviceTracker] = [
        LinksysVelopMeshDeviceTracker(
            config_entry=config,
            device_id=tracker,
            hass=hass,
        )
        for tracker in config.options.get(CONF_DEVICE_TRACKERS, [])
    ]

    async_add_entities(device_trackers)


class LinksysVelopMeshDeviceTracker(ScannerEntity):
    """Representation of a device tracker."""

    def __init__(self, config_entry: ConfigEntry, device_id: str, hass: HomeAssistant) -> None:
        """Initialise."""
        self._attr_should_poll = False

        self._config: ConfigEntry = config_entry
        self._listener_consider_home: Optional[Callable] = None
        self._log_formatter: Logger = Logger(unique_id=self._config.unique_id)
        self._device: Optional[Device] = None
        self._hass: HomeAssistant = hass
        self._ip: str = ""
        self._is_connected: bool = False
        self._mac: str = ""

        # region #-- get the device specific info --#
        mesh: Mesh = self._hass.data[DOMAIN][self._config.entry_id][CONF_COORDINATOR_MESH]
        device: Device
        for device in mesh.devices:
            if device.unique_id == device_id:
                self._device = device
                self._is_connected = device.status
                self._get_device_adapter_info()
                _LOGGER.debug(self._log_formatter.format("mac: %s"), self._mac)
                self._update_mesh_device_connections()
                try:
                    _ = self.has_entity_name
                    self._attr_has_entity_name = True
                    self._attr_name = device.name
                except AttributeError:
                    self._attr_name = f"{ENTITY_SLUG} Mesh: {device.name}"
                break
        else:  # got to the end and didn't find it
            _LOGGER.warning(
                self._log_formatter.format("%s not found on the mesh. Removing it from being tracked."),
                device_id
            )
            self._stop_tracking(unique_id=device_id)
        # endregion

    def _get_device_adapter_info(self) -> None:
        """Gather the network details about the device tracker."""
        adapter: List[Dict] = [a for a in self._device.network]
        if adapter:
            self._mac = dr.format_mac(adapter[0].get("mac", ""))
            self._ip = adapter[0].get("ip", "")

    def _get_mesh_from_registry(self) -> Optional[DeviceEntry]:
        """Retrieve the Mesh device from the registry."""
        dr_mesh: List[DeviceEntry] = _get_device_registry_entry(
            config_entry_id=self._config.entry_id,
            device_registry=dr.async_get(hass=self._hass),
            entry_type="mesh",
        )
        if not dr_mesh:
            return

        return dr_mesh[0]

    def _stop_tracking(self, unique_id: str) -> None:
        """Stop monitoring the tracker."""
        new_options = copy.deepcopy(dict(**self._config.options))  # deepcopy a dict copy so we get all the options
        trackers: List[str]
        if (trackers := new_options.get(CONF_DEVICE_TRACKERS, None)) is not None:
            trackers.remove(unique_id)
            new_options[CONF_DEVICE_TRACKERS] = trackers
            self._hass.config_entries.async_update_entry(entry=self._config, options=new_options)

    def _update_mesh_device_connections(self) -> None:
        """Update the `connections` property for the Mesh.

        N.B.  HASS versions prior to 2022.2 do not have the `merge_connections` parameter
        so fall back to using `_attr_device_info` (should do this in HASS 2022.2 and later)
        """
        if not self._mac:
            return

        dr_mesh: DeviceEntry = self._get_mesh_from_registry()
        if not {(dr.CONNECTION_NETWORK_MAC, self._mac)}.issubset(dr_mesh.connections):
            dev_reg: DeviceRegistry = dr.async_get(hass=self._hass)
            try:
                dev_reg.async_update_device(
                    device_id=dr_mesh.id,
                    merge_connections={(dr.CONNECTION_NETWORK_MAC, self._mac)}
                )
            except TypeError:  # TODO: remove when bumping min HASS version to 2022.2
                self._attr_device_info: DeviceInfo = DeviceInfo(
                    connections={(dr.CONNECTION_NETWORK_MAC, self._mac)},
                    identifiers={(DOMAIN, self._config.entry_id)},
                )
                dev_reg.async_load()  # reload the device registry so the entity is immediately available

    async def _async_get_device_info(self, evt: Optional[dt_util.dt.datetime] = None) -> None:
        """Retrieve the current status of the device and update the status if need be."""
        if self._device is None:
            return

        mark_online: bool = False
        mesh: Mesh = self._hass.data[DOMAIN][self._config.entry_id][CONF_COORDINATOR_MESH]
        try:
            tracker_details: Device = await mesh.async_get_device_from_id(
                device_id=self._device.unique_id,
                force_refresh=True,
            )
        except MeshDeviceNotFoundResponse:
            _LOGGER.warning(
               self._log_formatter.format("%s is no longer on the mesh. Removing it from being tracked."),
               self._device.name,
            )
            self._stop_tracking(unique_id=self._device.unique_id)
            return

        self._device = tracker_details
        if evt is not None:  # here because the listener fired
            _LOGGER.debug(self._log_formatter.format("%s is now being marked offline"), self._device.name)
            self._is_connected = False
            self._listener_consider_home = None
            await self.async_update_ha_state()
            return

        if self._is_connected != self._device.status:  # status changed
            if not self._device.status:  # just disconnected so start the listener
                if self._listener_consider_home is None:
                    fire_at: dt_util.dt.datetime = dt_util.dt.datetime.fromtimestamp(
                        int(self._device.results_time) +
                        self._config.options.get(CONF_CONSIDER_HOME, DEF_CONSIDER_HOME)
                    )
                    _LOGGER.debug(
                        self._log_formatter.format("%s: setting consider home listener for %s"),
                        self._device.name,
                        fire_at,
                    )
                    # noinspection PyTypeChecker
                    self._listener_consider_home = async_track_point_in_time(
                        hass=self._hass,
                        action=self._async_get_device_info,
                        point_in_time=fire_at
                    )
            else:
                _LOGGER.debug(
                    self._log_formatter.format("%s: back online"), self._device.name
                )
                self._is_connected = True
                mark_online = True
        else:
            self._is_connected = self._device.status
            if self._is_connected and self._listener_consider_home is not None:
                _LOGGER.debug(
                    self._log_formatter.format("%s: back online in consider_home period"), self._device.name
                )
                mark_online = True

        if mark_online:
            if self._listener_consider_home is not None:  # just connected so cancel the listener
                _LOGGER.debug(
                    self._log_formatter.format("%s: cancelling consider home listener"), self._device.name
                )
                self._listener_consider_home()
                self._listener_consider_home = None

            self._get_device_adapter_info()
            self._update_mesh_device_connections()
            await self.async_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Create listeners."""
        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=SIGNAL_UPDATE_DEVICE_TRACKER,
                target=self._async_get_device_info,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel listeners."""
        # region #-- cancel the listeners --#
        if self._listener_consider_home is not None:
            self._listener_consider_home()
        # endregion

    @property
    def ip_address(self) -> str | None:
        """Get the IP address."""
        return self._ip

    @property
    def is_connected(self) -> bool:
        """Get whether the device tracker is connected or not."""
        return self._is_connected

    @property
    def mac_address(self) -> str | None:
        """Get the MAC address."""
        return self._mac

    @property
    def source_type(self) -> str:
        """Get the source of the device tracker."""
        return SOURCE_TYPE_ROUTER

    @property
    def unique_id(self) -> Optional[str]:
        """Get the unique_id."""
        if self._device is not None:
            return f"{self._config.entry_id}::" \
                   f"{ENTITY_DOMAIN.lower()}::" \
                   f"{self._device.unique_id}"
