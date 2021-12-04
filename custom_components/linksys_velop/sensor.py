"""Sensors for the mesh, nodes and devices"""

import logging
from typing import Mapping, Any, List, Union

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT

# TODO: Fix up the try/except block when setting the minimum HASS version to 2021.12
# HASS 2021.12 introduces StrEnum for DEVICE_CLASS_* constants
try:
    from homeassistant.components.sensor import SensorDeviceClass
    DEVICE_CLASS_TIMESTAMP = SensorDeviceClass.TIMESTAMP
except ImportError:
    SensorDeviceClass = None
    from homeassistant.components.sensor import DEVICE_CLASS_TIMESTAMP

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

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    SIGNAL_UPDATE_SPEEDTEST_RESULTS
)
from .entity_helpers import (
    entity_setup,
    LinksysVelopMeshPolledSensor,
    LinksysVelopNodePolledSensor,
)
from pyvelop.node import Node

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """"""

    sensor_classes = [
        LinksysVelopMeshOfflineDevicesSensor,
        LinksysVelopMeshOnlineDevicesSensor,
        LinksysVelopMeshSpeedtestLatestSensor,
        LinksysVelopNodeConnectedDevicesSensor,
        LinksysVelopNodeCurrentFirmwareSensor,
        LinksysVelopNodeLatestFirmwareSensor,
        LinksysVelopNodeModelSensor,
        LinksysVelopNodeParentSensor,
        LinksysVelopNodeSerialSensor,
        LinksysVelopNodeTypeSensor,
    ]

    entity_setup(
        async_add_entities=async_add_entities,
        config=config,
        entity_classes=sensor_classes,
        hass=hass,
    )


class LinksysVelopMeshOfflineDevicesSensor(LinksysVelopMeshPolledSensor):
    """Representation of the offline devices sensor for the mesh"""

    _attribute = "Offline Devices"
    _attr_state_class = STATE_CLASS_MEASUREMENT
    _device_state = False

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Sets the additional attributes of the sensor to be the list of devices"""

        return {
            "devices": [
                device.name
                for device in self._get_devices(status=self._device_state)
            ]
        }

    @property
    def native_value(self) -> StateType:
        """The count of offline devices"""

        return len(self._get_devices(status=self._device_state))


class LinksysVelopMeshOnlineDevicesSensor(LinksysVelopMeshPolledSensor):
    """Representation of the online devices sensor for the mesh"""

    _attribute = "Online Devices"
    _attr_state_class = STATE_CLASS_MEASUREMENT
    _device_state = True

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Sets the additional attributes of the sensor to be the list of devices"""

        return {
            "devices": [
                {
                    device.name: {
                        adapter.get("ip"): adapter.get("type")
                        for adapter in device.network
                        if adapter.get("ip")
                    }
                }
                for device in self._get_devices(status=self._device_state)
            ]
        }

    @property
    def native_value(self) -> StateType:
        """Returns the count of online devices"""

        return len(self._get_devices(status=self._device_state))


class LinksysVelopMeshSpeedtestLatestSensor(LinksysVelopMeshPolledSensor):
    """Representation of the latest Speedtest details for the mesh"""

    _attribute = "Speedtest Latest"
    _attr_device_class = DEVICE_CLASS_TIMESTAMP
    _value: List = []

    async def _force_refresh(self):
        """Refresh the Speedtest details from the API"""

        results = await self._mesh.async_get_speedtest_results(only_completed=True, only_latest=True)
        if results:
            self._value = results
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register for callbacks and set initial value"""

        self._value = self._mesh.speedtest_results
        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=SIGNAL_UPDATE_SPEEDTEST_RESULTS,
                target=self._force_refresh,
            )
        )

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Set the additional attributes for the sensor"""

        ret = None
        if self._value:
            ret = self._value[0].copy()
            ret.pop("timestamp")

        return ret

    @property
    def native_value(self) -> StateType:
        """Set the value of the sensor to the time the results were generated"""

        ret = None

        if self._value:
            ret = self._value[0].get("timestamp")
        return ret


class LinksysVelopNodeConnectedDevicesSensor(LinksysVelopNodePolledSensor):
    """Representation of the devices connected to a node"""

    _attribute = "Connected devices"

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Set the additional attributes to be the list of connected devices"""

        ret = {}
        node: Node = self._get_node()
        if node.connected_devices:
            ret["devices"] = node.connected_devices

        return ret

    @property
    def native_value(self) -> StateType:
        """Set the value of the sensor to the number of connected devices"""

        node: Node = self._get_node()
        ret = len(node.connected_devices)
        return ret


class LinksysVelopNodeCurrentFirmwareSensor(LinksysVelopNodePolledSensor):
    """Representation of the current firmware sensor"""

    _attribute = "Version"

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def native_value(self) -> StateType:
        """Sets the value to the version number of the current firmware"""

        node: Node = self._get_node()
        return node.firmware.get("version", None)


class LinksysVelopNodeLatestFirmwareSensor(LinksysVelopNodePolledSensor):
    """Representation of the current firmware sensor"""

    _attribute = "Newest Version"

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def native_value(self) -> StateType:
        """Sets the value to the version number of the latest firmware"""

        node: Node = self._get_node()
        return node.firmware.get("latest_version", None)


class LinksysVelopNodeModelSensor(LinksysVelopNodePolledSensor):
    """Representation of the model sensor"""

    _attribute = "Model"

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def native_value(self) -> StateType:
        """Sets the value of the sensor to the model number of the node"""

        node: Node = self._get_node()
        return node.model


class LinksysVelopNodeParentSensor(LinksysVelopNodePolledSensor):
    """Representation of the parent name sensor"""

    _attribute = "Parent"
    _attr_icon = "hass:family-tree"

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Set the additional attributes to be the details of the parent node"""

        node: Node = self._get_node()
        ret = {
            "parent_ip": node.parent_ip
        }
        return ret

    @property
    def native_value(self) -> StateType:
        """Sets the value of the sensor to be the name of the parent node"""

        node: Node = self._get_node()
        return node.parent_name


class LinksysVelopNodeSerialSensor(LinksysVelopNodePolledSensor):
    """Representation of the serial number sensor"""

    _attribute = "Serial"
    _attr_icon = "hass:barcode"

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def native_value(self) -> StateType:
        """Sets the value to be the serial number of the node"""

        node: Node = self._get_node()
        return node.serial


class LinksysVelopNodeTypeSensor(LinksysVelopNodePolledSensor):
    """Representation of the node type sensor"""

    _attribute = "Type"

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def native_value(self) -> StateType:
        """Sets the value of the sensor to be the node type"""

        node: Node = self._get_node()
        return node.type
