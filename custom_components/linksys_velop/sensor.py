""""""

import logging
from typing import Mapping, Any, List

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    DEVICE_CLASS_TIMESTAMP,
)
from homeassistant.config_entries import ConfigEntry
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
from .pyvelop.node import Node

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """"""

    sensor_classes = [
        LinksysVelopMeshOfflineDevicesSensor,
        LinksysVelopMeshOnlineDevicesSensor,
        LinksysVelopMeshSpeedtestLatestSensor,
        LinksysVelopNodeConnectedDevicesSensor,
        LinksysVelopNodeCurrentFirmwareSensor,
        LinksysVelopNodeModelSensor,
        LinksysVelopNodeParentNameSensor,
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
    """"""

    _attribute = "Offline Devices"
    _attr_state_class = STATE_CLASS_MEASUREMENT
    _device_state = False

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "devices": [
                device.name
                for device in self._get_devices(status=self._device_state)
            ]
        }

    @property
    def native_value(self) -> StateType:
        return len(self._get_devices(status=self._device_state))


class LinksysVelopMeshOnlineDevicesSensor(LinksysVelopMeshPolledSensor):
    """"""

    _attribute = "Online Devices"
    _attr_state_class = STATE_CLASS_MEASUREMENT
    _device_state = True

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "devices": [
                {
                    device.name: [adapter.get("ip") for adapter in device.network if adapter.get("ip")]
                }
                for device in self._get_devices(status=self._device_state)
            ]
        }

    @property
    def native_value(self) -> StateType:
        return str(len(self._get_devices(status=self._device_state)))


class LinksysVelopMeshSpeedtestLatestSensor(LinksysVelopMeshPolledSensor):
    """"""

    _attribute = "Speedtest Latest"
    _attr_device_class = DEVICE_CLASS_TIMESTAMP
    _value: List = []

    async def _force_refresh(self):
        """"""

        results = await self._mesh.async_get_speedtest_results(only_completed=True, only_latest=True)
        if results:
            self._value = results
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """"""

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
        """"""

        ret = self._value[0].copy()
        ret.pop("timestamp")

        return ret

    @property
    def native_value(self) -> StateType:
        """"""

        ret = self._value[0].get("timestamp")
        return ret


class LinksysVelopNodeConnectedDevicesSensor(LinksysVelopNodePolledSensor):
    """"""

    _attribute = "Connected devices"

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        ret = {}
        node: Node = self._get_node()
        if node.connected_devices:
            ret["devices"] = node.connected_devices

        return ret

    @property
    def native_value(self) -> StateType:
        node: Node = self._get_node()
        ret = len(node.connected_devices)
        return ret


class LinksysVelopNodeCurrentFirmwareSensor(LinksysVelopNodePolledSensor):
    """"""

    _attribute = "Version"

    @property
    def native_value(self) -> StateType:
        node: Node = self._get_node()
        return node.firmware.get("version", None)


class LinksysVelopNodeModelSensor(LinksysVelopNodePolledSensor):
    """"""

    _attribute = "Model"

    @property
    def native_value(self) -> StateType:
        node: Node = self._get_node()
        return node.model


class LinksysVelopNodeParentNameSensor(LinksysVelopNodePolledSensor):
    """"""

    _attribute = "Parent"
    _attr_icon = "hass:family-tree"

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        node: Node = self._get_node()
        ret = {
            "parent_ip": node.parent_ip
        }
        return ret

    @property
    def native_value(self) -> StateType:
        node: Node = self._get_node()
        return node.parent_name


class LinksysVelopNodeSerialSensor(LinksysVelopNodePolledSensor):
    """"""

    _attribute = "Serial"
    _attr_icon = "hass:barcode"

    @property
    def native_value(self) -> StateType:
        node: Node = self._get_node()
        return node.serial


class LinksysVelopNodeTypeSensor(LinksysVelopNodePolledSensor):
    """"""

    _attribute = "Type"

    @property
    def native_value(self) -> StateType:
        node: Node = self._get_node()
        return node.type.title()
