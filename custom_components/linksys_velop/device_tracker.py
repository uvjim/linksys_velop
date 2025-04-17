"""Device tracker entities for Linksys Velop."""

# region #-- imports --#
import logging
from functools import cached_property

from homeassistant.components.device_tracker import CONF_CONSIDER_HOME
from homeassistant.components.device_tracker import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.device_tracker.config_entry import (
    ScannerEntity,
    SourceType,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util
from pyvelop.mesh import Mesh
from pyvelop.mesh_entity import DeviceEntity

from .const import CONF_DEVICE_TRACKERS, DEF_CONSIDER_HOME, SIGNAL_DEVICE_TRACKER_UPDATE
from .helpers import get_mesh_device_for_config_entry
from .types import LinksysVelopConfigEntry, LinksysVelopLogFormatter

# endregion

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create entities for device trackers."""

    adapter: list[dict]
    device: list[DeviceEntity]
    device_trackers: list[LinksysVelopMeshDeviceTracker] = []
    connections: set[tuple[str, str]] = set()
    mesh: Mesh = config_entry.runtime_data.mesh
    for tracked_device in config_entry.options.get(CONF_DEVICE_TRACKERS, []):
        if device := [d for d in mesh.devices if d.unique_id == tracked_device]:
            device_trackers.append(
                LinksysVelopMeshDeviceTracker(
                    config_entry=config_entry,
                    device=device[0],
                    mesh=mesh,
                )
            )

            if adapter := list(device[0].adapter_info):
                connections.add(
                    (
                        dr.CONNECTION_NETWORK_MAC,
                        dr.format_mac(next(iter(adapter), {}).get("mac", "")),
                    )
                )

    device_registry: DeviceRegistry = dr.async_get(hass)
    mesh_device: DeviceEntry = get_mesh_device_for_config_entry(hass, config_entry)
    device_registry.async_update_device(mesh_device.id, merge_connections=connections)

    async_add_entities(device_trackers)


class LinksysVelopMeshDeviceTracker(ScannerEntity):
    """Representation of a device tracker."""

    def __init__(
        self, config_entry: LinksysVelopConfigEntry, device: DeviceEntity, mesh: Mesh
    ) -> None:
        """Initialise."""
        self._config_entry: LinksysVelopConfigEntry = config_entry
        self._device_id: str = device.unique_id

        self._attr_has_entity_name = True
        self._attr_name = device.name
        self._attr_should_poll = False
        self._attr_unique_id = (
            f"{self._config_entry.entry_id}::{ENTITY_DOMAIN.lower()}::{self._device_id}"
        )
        self._consider_home_cancel: CALLBACK_TYPE | None = None
        self._ip_address: str = self._get_ip_address(device)
        self._is_connected: bool = device.status
        self._log_formatter: LinksysVelopLogFormatter = (
            self._config_entry.runtime_data.log_formatter
        )
        self._mac_address: str = self._get_mac_address(device)

    def _get_ip_address(self, device: DeviceEntity) -> str:
        """Retrieve the IP address from the device object."""
        adapter: list[dict]
        if adapter := list(device.adapter_info):
            return next(iter(adapter), {}).get("ip")

    def _get_mac_address(self, device: DeviceEntity) -> str:
        """Retrieve the MAC address from the device object."""
        adapter: list[dict]
        if adapter := list(device.adapter_info):
            return dr.format_mac(next(iter(adapter), {}).get("mac", ""))

    async def _async_mark_offline(self, _: dt_util.dt.datetime) -> None:
        """Mark the device tracker as offline."""
        _LOGGER.debug(
            self._log_formatter("%s is now being marked offline"),
            self.name,
        )
        self._is_connected = False
        self._consider_home_cancel = None
        self.async_schedule_update_ha_state()

    async def _async_process_device_update(self, device: DeviceEntity) -> None:
        """Establish device state or attribute changes."""
        self._ip_address = self._get_ip_address(device)
        self._mac_address = self._get_mac_address(device)
        if device.status != self.is_connected:
            if device.status:
                _LOGGER.debug(self._log_formatter("%s: back online"), self.name)
                self._is_connected = True
                self.async_schedule_update_ha_state()
            else:
                if self._consider_home_cancel is None:
                    fire_at: dt_util.dt.datetime = dt_util.dt.datetime.fromtimestamp(
                        int(device.results_time)
                        + self._config_entry.options.get(
                            CONF_CONSIDER_HOME, DEF_CONSIDER_HOME
                        )
                    )
                    _LOGGER.debug(
                        self._log_formatter(
                            "%s: setting consider home listener for %s"
                        ),
                        self.name,
                        fire_at,
                    )
                    self._consider_home_cancel = async_track_point_in_time(
                        hass=self.hass,
                        action=self._async_mark_offline,
                        point_in_time=fire_at,
                    )
        else:
            if self._consider_home_cancel is not None:
                _LOGGER.debug(
                    self._log_formatter("%s: back online in consider_home period"),
                    self.name,
                )
                _LOGGER.debug(
                    self._log_formatter("%s: cancelling consider home"),
                    self.name,
                )
                self._consider_home_cancel()
                self._consider_home_cancel = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_DEVICE_TRACKER_UPDATE}_{self._device_id}",
                self._async_process_device_update,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup."""
        if self._consider_home_cancel is not None:
            self._consider_home_cancel()

    @property
    def ip_address(self) -> str | None:
        """Return the ip address of the device."""
        return self._ip_address

    @property
    def is_connected(self) -> bool:
        """True if connected."""
        return self._is_connected

    @cached_property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._mac_address

    @cached_property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.ROUTER

    @cached_property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._attr_unique_id
