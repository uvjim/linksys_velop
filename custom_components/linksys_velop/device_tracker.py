"""Device trackers"""

# region #-- imports --#
from __future__ import annotations

import logging
from typing import (
    Callable,
    Dict,
    List,
    Optional,
)

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DOMAIN as ENTITY_DOMAIN,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    DeviceRegistry,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_AUTHOR as PYVELOP_AUTHOR
from pyvelop.device import Device
from pyvelop.mesh import Mesh

from .const import (
    CONF_COORDINATOR_MESH,
    CONF_DEVICE_TRACKERS,
    DEF_CONSIDER_HOME,
    DOMAIN,
    ENTITY_SLUG,
    SIGNAL_UPDATE_DEVICE_TRACKER,
)
from .logger import Logger

# endregion

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Add the entities"""

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
    """Representation of a device tracker"""

    def __init__(self, config_entry: ConfigEntry, device_id: str, hass: HomeAssistant) -> None:
        """Constructor"""

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
                self._update_mesh_device_connections()
                self._attr_name = f"{ENTITY_SLUG} Mesh: {device.name}"
                break
        # endregion

    def _get_device_adapter_info(self) -> None:
        """Gather the network details about the device tracker"""

        adapter: List[Dict] = [a for a in self._device.connected_adapters]
        if adapter:
            self._mac = dr.format_mac(adapter[0].get("mac", ""))
            self._ip = adapter[0].get("ip", "")

    def _get_mesh_from_registry(self) -> Optional[DeviceEntry]:
        """Retrieve the Mesh device from the registry"""

        dev_reg: DeviceRegistry = dr.async_get(hass=self._hass)
        dev_entries: List[DeviceEntry] = dr.async_entries_for_config_entry(
            registry=dev_reg,
            config_entry_id=self._config.entry_id
        )
        dr_mesh: List[DeviceEntry] | DeviceEntry = [
            dr_dev
            for dr_dev in dev_entries
            if all([
                dr_dev.manufacturer == PYVELOP_AUTHOR,
                dr_dev.name.lower() == "mesh",
            ])
        ]
        if not dr_mesh:
            return

        return dr_mesh[0]

    def _update_mesh_device_connections(self) -> None:
        """Update the `connections` property for the Mesh

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
        """Retrieve the current status of the device and update the status if need be"""

        mesh: Mesh = self._hass.data[DOMAIN][self._config.entry_id][CONF_COORDINATOR_MESH]
        self._device: Device = await mesh.async_get_device_from_id(device_id=self._device.unique_id, force_refresh=True)

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
            else:  # just connected so cancel the listener
                _LOGGER.debug(self._log_formatter.format("%s is online"), self._device.name)
                self._is_connected = True
                if self._listener_consider_home is not None:
                    _LOGGER.debug(
                        self._log_formatter.format("%s: cancelling consider home listener"), self._device.name
                    )
                    self._listener_consider_home()
                    self._listener_consider_home = None

                self._get_device_adapter_info()
                self._update_mesh_device_connections()
                await self.async_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Setup listeners"""

        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=SIGNAL_UPDATE_DEVICE_TRACKER,
                target=self._async_get_device_info,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel listeners"""

        # region #-- cancel the listeners --#
        if self._listener_consider_home is not None:
            self._listener_consider_home()
        # endregion

    @property
    def ip_address(self) -> str | None:
        """"""

        return self._ip

    @property
    def is_connected(self) -> bool:
        """"""

        return self._is_connected

    @property
    def mac_address(self) -> str | None:
        """"""

        return self._mac

    @property
    def source_type(self) -> str:
        """"""

        return SOURCE_TYPE_ROUTER

    @property
    def unique_id(self) -> Optional[str]:
        """"""

        return f"{self._config.entry_id}::" \
               f"{ENTITY_DOMAIN.lower()}::" \
               f"{self._device.unique_id}"
