"""Sensors for the mesh, nodes and devices"""
# TODO: Fix up the try/except block when setting the minimum HASS version to 2021.12
# HASS 2021.12 introduces StrEnum for DEVICE_CLASS_* constants
try:
    from homeassistant.components.sensor import SensorDeviceClass
    DEVICE_CLASS_TIMESTAMP = SensorDeviceClass.TIMESTAMP
except ImportError:
    SensorDeviceClass = None
    from homeassistant.components.sensor import DEVICE_CLASS_TIMESTAMP

import logging
from typing import Mapping, Any, List, Optional

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import (
    SIGNAL_UPDATE_SPEEDTEST_RESULTS
)
from .entity_helpers import (
    entity_remove,
    entity_setup,
    LinksysVelopDiagnosticEntity,
    LinksysVelopMeshSensorPolled,
    LinksysVelopNodeSensorPolled,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """"""

    remove_binary_sensor_classes = []

    entity_remove(config=config, entity_classes=remove_binary_sensor_classes, hass=hass)

    sensor_classes = [
        LinksysVelopMeshOfflineDevicesSensor,
        LinksysVelopMeshOnlineDevicesSensor,
        LinksysVelopMeshSpeedtestLatestSensor,
        LinksysVelopMeshStorageSensor,
        LinksysVelopNodeConnectedDevicesSensor,
        LinksysVelopNodeCurrentFirmwareSensor,
        LinksysVelopNodeLastFirmwareUpdateCheckSensor,
        LinksysVelopNodeLatestFirmwareSensor,
        LinksysVelopNodeModelSensor,
        LinksysVelopNodeParentSensor,
        LinksysVelopNodeSerialSensor,
        LinksysVelopNodeTypeSensor,
    ]

    entity_setup(async_add_entities=async_add_entities, config=config, entity_classes=sensor_classes, hass=hass)


class LinksysVelopMeshOfflineDevicesSensor(LinksysVelopMeshSensorPolled, LinksysVelopDiagnosticEntity):
    """Representation of the offline devices' sensor for the mesh"""

    _attribute = "Offline Devices"
    _attr_state_class = STATE_CLASS_MEASUREMENT
    _device_state = False

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


class LinksysVelopMeshOnlineDevicesSensor(LinksysVelopMeshSensorPolled, LinksysVelopDiagnosticEntity):
    """Representation of the online devices' sensor for the mesh"""

    _attribute = "Online Devices"
    _attr_state_class = STATE_CLASS_MEASUREMENT
    _device_state = True

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


class LinksysVelopMeshSpeedtestLatestSensor(LinksysVelopMeshSensorPolled, LinksysVelopDiagnosticEntity):
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
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Set the additional attributes for the sensor"""

        ret = None
        if self._value:
            ret = self._value[0].copy()
            ret.pop("timestamp")

        return ret

    @property
    def native_value(self) -> dt_util.dt.datetime:
        """Set the value of the sensor to the time the results were generated"""

        ret = None

        if self._value:
            ret = dt_util.parse_datetime(self._value[0].get("timestamp"))
        return ret


class LinksysVelopMeshStorageSensor(LinksysVelopMeshSensorPolled, LinksysVelopDiagnosticEntity):
    """Representation of the available storage for the mesh"""

    _attribute = "Available Storage"

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Set the additional attributes for the sensor"""

        ret = {
            "partitions": self._mesh.storage_available
        }

        return ret

    @property
    def native_value(self) -> int:
        """Set the value of the sensor to the time the results were generated"""

        return len(self._mesh.storage_available)


class LinksysVelopNodeConnectedDevicesSensor(LinksysVelopNodeSensorPolled, LinksysVelopDiagnosticEntity):
    """Representation of the devices connected to a node"""

    _attribute = "Connected devices"

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Set the additional attributes to be the list of connected devices"""

        ret = {}
        if self._node.connected_devices:
            ret["devices"] = self._node.connected_devices

        return ret

    @property
    def native_value(self) -> StateType:
        """Set the value of the sensor to the number of connected devices"""

        ret = len(self._node.connected_devices)
        return ret


class LinksysVelopNodeCurrentFirmwareSensor(LinksysVelopNodeSensorPolled, LinksysVelopDiagnosticEntity):
    """Representation of the current firmware sensor"""

    _attribute = "Version"

    @property
    def native_value(self) -> StateType:
        """Sets the value to the version number of the current firmware"""

        return self._node.firmware.get("version", None)


class LinksysVelopNodeLastFirmwareUpdateCheckSensor(LinksysVelopNodeSensorPolled, LinksysVelopDiagnosticEntity):
    """Representation of the last firmware update check sensor"""

    _attribute = "Last Update Check"
    _attr_device_class = DEVICE_CLASS_TIMESTAMP

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Disable the entity by default"""

        return False

    @property
    def native_value(self) -> Optional[dt_util.dt.datetime]:
        """"""

        ret = None
        if self._node.last_update_check:
            ret = dt_util.parse_datetime(self._node.last_update_check)

        return ret


class LinksysVelopNodeLatestFirmwareSensor(LinksysVelopNodeSensorPolled, LinksysVelopDiagnosticEntity):
    """Representation of the current firmware sensor"""

    _attribute = "Newest Version"

    @property
    def native_value(self) -> StateType:
        """Sets the value to the version number of the latest firmware"""

        return self._node.firmware.get("latest_version", None)


class LinksysVelopNodeModelSensor(LinksysVelopNodeSensorPolled, LinksysVelopDiagnosticEntity):
    """Representation of the model sensor"""

    _attribute = "Model"

    @property
    def native_value(self) -> StateType:
        """Sets the value of the sensor to the model number of the node"""

        return self._node.model


class LinksysVelopNodeParentSensor(LinksysVelopNodeSensorPolled, LinksysVelopDiagnosticEntity):
    """Representation of the parent name sensor"""

    _attribute = "Parent"
    _attr_icon = "hass:family-tree"

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Set the additional attributes to be the details of the parent node"""

        ret = {
            "parent_ip": self._node.parent_ip,
            "backhaul": self._node.backhaul or None,
        }
        return ret

    @property
    def native_value(self) -> StateType:
        """Sets the value of the sensor to be the name of the parent node"""

        return self._node.parent_name


class LinksysVelopNodeSerialSensor(LinksysVelopNodeSensorPolled, LinksysVelopDiagnosticEntity):
    """Representation of the serial number sensor"""

    _attribute = "Serial"
    _attr_icon = "hass:barcode"

    @property
    def native_value(self) -> StateType:
        """Sets the value to be the serial number of the node"""

        return self._node.serial


class LinksysVelopNodeTypeSensor(LinksysVelopNodeSensorPolled, LinksysVelopDiagnosticEntity):
    """Representation of the node type sensor"""

    _attribute = "Type"

    @property
    def native_value(self) -> StateType:
        """Sets the value of the sensor to be the node type"""

        return self._node.type
