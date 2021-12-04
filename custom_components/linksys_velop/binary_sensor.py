"""Binary sensors for the mesh, nodes and devices"""

import logging
from datetime import timedelta, datetime
from typing import Mapping, Any, Union

# TODO: Fix up the try/except block when setting the minimum HASS version to 2021.12
# HASS 2021.12 introduces StrEnum for DEVICE_CLASS_* constants
try:
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    DEVICE_CLASS_CONNECTIVITY = BinarySensorDeviceClass.CONNECTIVITY
    DEVICE_CLASS_UPDATE = BinarySensorDeviceClass.UPDATE
except ImportError:
    BinarySensorDeviceClass = None
    from homeassistant.components.binary_sensor import (
        DEVICE_CLASS_CONNECTIVITY,
        DEVICE_CLASS_UPDATE
    )

from homeassistant.config_entries import ConfigEntry

# TODO: Remove the try/except block when setting the minimum HASS version to 2021.11
try:
    from homeassistant.const import (
        ENTITY_CATEGORY_CONFIG,
        ENTITY_CATEGORY_DIAGNOSTIC,
    )
except ImportError:
    ENTITY_CATEGORY_CONFIG: str = ""
    ENTITY_CATEGORY_DIAGNOSTIC: str = ""

from homeassistant.core import (
    HomeAssistant,
    callback,
    CALLBACK_TYPE,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS,
    SIGNAL_UPDATE_SPEEDTEST_RESULTS,
    SIGNAL_UPDATE_SPEEDTEST_STATUS,
)
from .entity_helpers import (
    entity_setup,
    LinksysVelopMeshPolledBinarySensor,
    LinksysVelopNodePolledBinarySensor,
    LinksysVelopMeshBinarySensor,
)
from pyvelop.node import Node

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the binary sensors from a config entry"""

    binary_sensor_classes = [
        LinksysVelopMeshCheckForUpdateStatusBinarySensor,
        LinksysVelopMeshSpeedtestStatusBinarySensor,
        LinksysVelopMeshWANBinarySensor,
        LinksysVelopNodeStatusBinarySensor,
        LinksysVelopNodeUpdateAvailableBinarySensor,
    ]

    entity_setup(
        async_add_entities=async_add_entities,
        config=config,
        entity_classes=binary_sensor_classes,
        hass=hass,
    )


class LinksysVelopMeshCheckForUpdateStatusBinarySensor(LinksysVelopMeshBinarySensor):
    """Representation of the check for updates binary sensor"""

    _attribute = "Check for Updates Status"
    _status_update_interval: int = 1
    _status_value: bool
    _remove_time_interval: Union[CALLBACK_TYPE, None] = None

    @callback
    async def async_update_callback(self, _: Union[datetime, None] = None):
        """Update the state of the binary sensor

        Triggers a time interval to ensure that data is checked for more regularly when the state
        is on.
        """

        self._status_value = await self._mesh.async_get_update_state()

        if self._status_value and not self._remove_time_interval:
            self._remove_time_interval = async_track_time_interval(
                self.hass,
                self.async_update_callback,
                timedelta(seconds=self._status_update_interval)
            )

        if not self._status_value and self._remove_time_interval:
            self._remove_time_interval()
            self._remove_time_interval = None

        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks and set initial status"""

        self._status_value = self._mesh.check_for_update_status
        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS,
                target=self.async_update_callback,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Tidy up when removed"""

        if self._remove_time_interval:
            self._remove_time_interval()

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Return True if the mesh is currently checking for updates, False otherwise"""

        return self._status_value


class LinksysVelopMeshSpeedtestStatusBinarySensor(LinksysVelopMeshBinarySensor):
    """Representation of the Speedtest status binary sensor"""

    _attribute = "Speedtest Status"
    _status_text: str = ""
    _status_update_interval: int = 1
    _remove_time_interval: Union[CALLBACK_TYPE, None] = None

    @callback
    async def async_update_callback(self, _: Union[datetime, None] = None):
        """Update the state of the binary sensor

        Triggers a time interval to ensure that data is checked for more regularly when the state
        is on.
        """

        self._status_text = await self._mesh.async_get_speedtest_state()
        if self._status_text:
            if not self._remove_time_interval:
                self._remove_time_interval = async_track_time_interval(
                    self.hass,
                    self.async_update_callback,
                    timedelta(seconds=self._status_update_interval)
                )
        else:
            if self._remove_time_interval:
                self._remove_time_interval()
                self._remove_time_interval = None
                async_dispatcher_send(self.hass, SIGNAL_UPDATE_SPEEDTEST_RESULTS)
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks"""

        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=SIGNAL_UPDATE_SPEEDTEST_STATUS,
                target=self.async_update_callback,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Tidy up when removed"""

        if self._remove_time_interval:
            self._remove_time_interval()

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Set the current stage of the test as an attribute"""

        return {
            "status": self._status_text
        }

    @property
    def is_on(self) -> bool:
        """Return True if the mesh is currently running a Speedtest, False otherwise"""

        return self._status_text != ""


class LinksysVelopMeshWANBinarySensor(LinksysVelopMeshPolledBinarySensor):
    """Representation of the WAN binary sensor"""

    _attribute = "WAN Status"
    _attr_device_class = DEVICE_CLASS_CONNECTIVITY

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Set additional attributes detailing the WAN details"""

        return {
            "ip": self._mesh.wan_ip,
            "dns": self._mesh.wan_dns,
            "mac": self._mesh.wan_mac,
        }

    @property
    def is_on(self) -> bool:
        """Returns True if the WAN is connected, False otherwise"""

        return self._mesh.wan_status


class LinksysVelopNodeStatusBinarySensor(LinksysVelopNodePolledBinarySensor):
    """Representation of the Node status"""

    _attribute = "Status"
    _attr_device_class = DEVICE_CLASS_CONNECTIVITY

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Set attributes detailing the network adapters that are connected"""

        ret = {}
        node: Node = self._get_node()
        if node.connected_adapters:
            ret = node.connected_adapters[0]

        return ret

    @property
    def is_on(self) -> bool:
        """Returns True if the node is connected, False otherwise"""

        node: Node = self._get_node()
        return node.status


class LinksysVelopNodeUpdateAvailableBinarySensor(LinksysVelopNodePolledBinarySensor):
    """Representation of the Update Available sensor"""

    _attribute = "Update Available"
    _attr_device_class = DEVICE_CLASS_UPDATE

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Returns True if there is an update available, False otherwise"""

        ret: bool = False

        node: Node = self._get_node()
        if node.firmware.get("version") and node.firmware.get("latest_version"):
            ret = node.firmware.get("version") != node.firmware.get("latest_version")

        return ret
