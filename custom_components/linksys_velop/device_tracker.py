"""Device tracker entities for Linksys Velop."""

# region #-- imports --#
import logging
from functools import cached_property

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
)
from homeassistant.components.device_tracker import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.device_tracker import (
    ScannerEntity,
    SourceType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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
    mesh_device: DeviceEntry | None = get_mesh_device_for_config_entry(
        hass, config_entry
    )
    if mesh_device is not None:
        device_registry.async_update_device(
            mesh_device.id, merge_connections=connections
        )

    async_add_entities(device_trackers)


class LinksysVelopMeshDeviceTracker(ScannerEntity):
    """Representation of a device tracker."""

    def __init__(
        self, config_entry: LinksysVelopConfigEntry, device: DeviceEntity
    ) -> None:
        """Initialise."""
        self._config_entry: LinksysVelopConfigEntry = config_entry
        self._device_id: str = str(device.unique_id)

        self._attr_has_entity_name = True
        self._attr_name = device.name
        self._attr_should_poll = False
        self._attr_unique_id = (
            f"{self._config_entry.entry_id}::{ENTITY_DOMAIN.lower()}::{self._device_id}"
        )
        # self._consider_home_cancel: CALLBACK_TYPE | None = None
        self._consider_home_period: int = self._config_entry.options.get(
            CONF_CONSIDER_HOME, DEF_CONSIDER_HOME
        )
        self._ip_address: str = self._get_ip_address(device)
        self._is_connected: bool = device.status
        self._log_formatter: LinksysVelopLogFormatter = (
            self._config_entry.runtime_data.log_formatter
        )
        self._mac_address: str = self._get_mac_address(device)
        self._offline_first_seen: int | None = None

    def _get_ip_address(self, device: DeviceEntity) -> str:
        """Retrieve the IP address from the device object."""
        adapter: list[dict]
        if adapter := list(device.adapter_info):
            return next(iter(adapter), {}).get("ip", "")

        return ""

    def _get_mac_address(self, device: DeviceEntity) -> str:
        """Retrieve the MAC address from the device object."""
        adapter: list[dict]
        if adapter := list(device.adapter_info):
            return dr.format_mac(next(iter(adapter), {}).get("mac", ""))

        return ""

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
                if device.results_time is not None:
                    if self._offline_first_seen is None:
                        # TODO: change this when pyvelop returns the results_time as int
                        self._offline_first_seen = int(device.results_time)
                        _LOGGER.debug(
                            self._log_formatter(
                                "%s: waiting for consider_home period %s"
                            ),
                            self.name,
                            self._consider_home_period,
                        )
                    else:
                        if (
                            int(device.results_time) - self._offline_first_seen
                            >= self._consider_home_period
                        ):
                            _LOGGER.debug(
                                self._log_formatter("%s: consider_home period expired"),
                                self.name,
                            )
                            self._is_connected = False
                            self._offline_first_seen = None
                            self.async_schedule_update_ha_state()
        else:
            if self._offline_first_seen is not None:
                _LOGGER.debug(
                    self._log_formatter("%s: back online in consider_home period"),
                    self.name,
                )
                self._offline_first_seen = None

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
        return str(self._attr_unique_id)
