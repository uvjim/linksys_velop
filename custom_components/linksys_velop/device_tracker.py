"""Device trackers."""

# region #-- imports --#
from __future__ import annotations

import logging
from typing import Callable, Dict, List

from homeassistant.components.device_tracker import CONF_CONSIDER_HOME
from homeassistant.components.device_tracker import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util
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
from .helpers import include_serial_logging
from .logger import Logger

# endregion

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
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

    def __init__(
        self, config_entry: ConfigEntry, device_id: str, hass: HomeAssistant
    ) -> None:
        """Initialise."""
        self._attr_should_poll = False

        self._config: ConfigEntry = config_entry
        self._listener_consider_home: Callable | None = None
        if include_serial_logging(config=self._config):
            self._log_formatter: Logger = Logger(unique_id=self._config.unique_id)
        else:
            self._log_formatter: Logger = Logger()
        self._device: Device | None = None
        self._ip: str = ""
        self._is_connected: bool = False
        self._mac: str = ""

        self.hass = hass

        mesh: Mesh = hass.data[DOMAIN][self._config.entry_id][CONF_COORDINATOR_MESH]
        device: Device
        for device in mesh.devices:  # get the device specific info
            if device.unique_id == device_id:
                self._device = device
                self._is_connected = device.status
                self._get_device_adapter_info()
                _LOGGER.debug(self._log_formatter.format("mac: %s"), self._mac)
                try:
                    _ = self.has_entity_name
                    self._attr_has_entity_name = True
                    self._attr_name = device.name
                except AttributeError:
                    self._attr_name = f"{ENTITY_SLUG} Mesh: {device.name}"
                break

    def _get_device_adapter_info(self) -> None:
        """Gather the network details about the device tracker."""
        adapter: List[Dict] = [a for a in self._device.network]
        if adapter:
            self._mac = dr.format_mac(adapter[0].get("mac", ""))
            self._ip = adapter[0].get("ip", "")

    async def _async_process_device_info(self, device_info: Device) -> None:
        """Process the data passed in by the signal."""
        _LOGGER.debug(self._log_formatter.format("entered, %s"), device_info)
        self._device = device_info
        if self._is_connected != device_info.status:  # status changed
            if not device_info.status:  # disconnected
                if self._listener_consider_home is None:
                    fire_at: dt_util.dt.datetime = dt_util.dt.datetime.fromtimestamp(
                        int(self._device.results_time)
                        + self._config.options.get(
                            CONF_CONSIDER_HOME, DEF_CONSIDER_HOME
                        )
                    )
                    _LOGGER.debug(
                        self._log_formatter.format(
                            "%s: setting consider home listener for %s"
                        ),
                        self._device.name,
                        fire_at,
                    )
                    self._listener_consider_home = async_track_point_in_time(
                        hass=self.hass,
                        action=self._async_mark_offline,
                        point_in_time=fire_at,
                    )
            else:  # connected
                _LOGGER.debug(
                    self._log_formatter.format("%s: back online"), self._device.name
                )
                self._is_connected = True
                self.async_schedule_update_ha_state()
        else:
            if self._listener_consider_home is not None:
                _LOGGER.debug(
                    self._log_formatter.format(
                        "%s: back online in consider_home period"
                    ),
                    self._device.name,
                )
                _LOGGER.debug(
                    self._log_formatter.format("%s: cancelling consider home listener"),
                    self._device.name,
                )
                self._listener_consider_home()
                self._listener_consider_home = None

    async def _async_mark_offline(self, _: dt_util.dt.datetime) -> None:
        """Mark the device tracker as offline."""
        _LOGGER.debug(
            self._log_formatter.format("%s is now being marked offline"),
            self._device.name,
        )
        self._is_connected = False
        self._listener_consider_home = None
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Create listeners."""
        if self._device is not None:
            self.async_on_remove(
                async_dispatcher_connect(
                    hass=self.hass,
                    signal=f"{SIGNAL_UPDATE_DEVICE_TRACKER}_{self._device.unique_id}",
                    target=self._async_process_device_info,
                )
            )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel listeners."""
        if self._listener_consider_home is not None:
            self._listener_consider_home()

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
        return SourceType.ROUTER

    @property
    def unique_id(self) -> str | None:
        """Get the unique_id."""
        if self._device is not None:
            return (
                f"{self._config.entry_id}::"
                f"{ENTITY_DOMAIN.lower()}::"
                f"{self._device.unique_id}"
            )

        return None
