"""Sensors for the mesh, nodes and devices"""

# region #-- imports --#
# TODO: Fix up the try/except block when setting the minimum HASS version to 2021.12
# HASS 2021.12 introduces StrEnum for DEVICE_CLASS_* constants
try:
    from homeassistant.components.sensor import SensorDeviceClass
    DEVICE_CLASS_TIMESTAMP = SensorDeviceClass.TIMESTAMP
except ImportError:
    SensorDeviceClass = None
    from homeassistant.components.sensor import DEVICE_CLASS_TIMESTAMP

# TODO: Remove the try/except block when setting the minimum HASS version to 2021.12
try:
    from homeassistant.helpers.entity import EntityCategory
except ImportError:
    EntityCategory = None
    # TODO: Remove the try/except block when setting the minimum HASS version to 2021.11
    try:
        from homeassistant.const import (
            ENTITY_CATEGORY_CONFIG,
            ENTITY_CATEGORY_DIAGNOSTIC,
        )
    except ImportError:
        ENTITY_CATEGORY_CONFIG: str = "config"
        ENTITY_CATEGORY_DIAGNOSTIC: str = "diagnostic"

import dataclasses
import logging
from typing import (
    Any,
    Callable,
    List,
    Mapping,
    Optional,
    Union,
)

from homeassistant.components.sensor import (
    DOMAIN as ENTITY_DOMAIN,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify
from pyvelop.device import Device
from pyvelop.mesh import Mesh
from pyvelop.node import Node

from . import (
    LinksysVelopMeshEntity,
    LinksysVelopNodeEntity,
)
from .const import (
    CONF_COORDINATOR,
    DOMAIN,
    ENTITY_SLUG,
    SIGNAL_UPDATE_SPEEDTEST_RESULTS,
)
from .data_update_coordinator import LinksysVelopDataUpdateCoordinator
# endregion

_LOGGER = logging.getLogger(__name__)


# region #-- functions for classes --#
def _get_online_devices(mesh: Mesh) -> dict:
    """Get the online devices in the mesh"""

    device: Device

    return {
        "devices": [
            {
                device.name: {
                    "ip": adapter.get("ip"),
                    "connection": adapter.get("type"),
                    "guest_network": adapter.get("guest_network"),
                }
                for adapter in device.network
                if adapter.get("ip")
            }
            for device in mesh.devices if device.status is True
        ]
    }
# endregion


# region #-- sensor entity descriptions --#
@dataclasses.dataclass
class OptionalLinksysVelopDescription:
    """Represent the optional attributes of the sensor description."""

    extra_attributes: Optional[Callable] = None
    state_value: Optional[Callable] = None


@dataclasses.dataclass
class RequiredLinksysVelopDescription:
    """Represent the required attributes of the sensor description."""


@dataclasses.dataclass
class LinksysVelopSensorDescription(
    OptionalLinksysVelopDescription,
    SensorEntityDescription,
    RequiredLinksysVelopDescription
):
    """Describes sensor entity"""
# endregion


SENSOR_DESCRIPTIONS: tuple[LinksysVelopSensorDescription, ...] = (
    LinksysVelopSensorDescription(
        extra_attributes=lambda m: {"devices": [device.name for device in m.devices if device.status is False]},
        key="offline_devices",
        name="Offline Devices",
        state_value=lambda m: len([d for d in m.devices if d.status is False])
    ),
    LinksysVelopSensorDescription(
        extra_attributes=_get_online_devices,
        key="online_devices",
        name="Online Devices",
        state_value=lambda m: len([d for d in m.devices if d.status is True])
    ),
    LinksysVelopSensorDescription(
        entity_registry_enabled_default=False,
        extra_attributes=lambda m: {"partitions": m.storage_available or None},
        icon="mdi:nas",
        key="available_storage",
        name="Available Storage",
        state_value=lambda m: len(m.storage_available)
    )
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors from a config entry"""

    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
    mesh: Mesh = coordinator.data

    sensors: List[Union[
        LinksysVelopMeshSensor,
        LinksysVelopNodeSensor,
        LinksysVelopMeshSpeedtestLatestSensor
    ]] = [
        LinksysVelopMeshSensor(
            config_entry=config_entry,
            coordinator=coordinator,
            description=sensor_description,
        )
        for sensor_description in SENSOR_DESCRIPTIONS
    ]

    sensors.extend([
        LinksysVelopMeshSpeedtestLatestSensor(
            config_entry=config_entry,
            coordinator=coordinator,
            description=LinksysVelopSensorDescription(
                device_class=DEVICE_CLASS_TIMESTAMP,
                key="",
                name="Speedtest Latest"
            )
        )
    ])

    # region #-- node sensors --#
    node: Node
    for node in mesh.nodes:
        sensors.extend([
            LinksysVelopNodeSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                node=node,
                description=LinksysVelopSensorDescription(
                    extra_attributes=lambda n: {"devices": n.connected_devices} if n.connected_devices else {},
                    key="",
                    name="Connected devices",
                    state_value=lambda n: len(n.connected_devices),
                )
            ),
            LinksysVelopNodeSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                node=node,
                description=LinksysVelopSensorDescription(
                    device_class=DEVICE_CLASS_TIMESTAMP,
                    entity_registry_enabled_default=False,
                    key="",
                    name="Last Update Check",
                    state_value=lambda n: dt_util.parse_datetime(n.last_update_check) if n.last_update_check else None
                )
            ),
            LinksysVelopNodeSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                node=node,
                description=LinksysVelopSensorDescription(
                    key="model",
                    name="Model"
                )
            ),
            LinksysVelopNodeSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                node=node,
                description=LinksysVelopSensorDescription(
                    extra_attributes=lambda n: {"parent_ip": n.parent_ip, "backhaul": n.backhaul or None},
                    icon="hass:family-tree",
                    key="parent_name",
                    name="Parent"
                )
            ),
            LinksysVelopNodeSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                node=node,
                description=LinksysVelopSensorDescription(
                    key="",
                    name="Newest Version",
                    state_value=lambda n: n.firmware.get("latest_version", None)
                )
            ),

            LinksysVelopNodeSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                node=node,
                description=LinksysVelopSensorDescription(
                    icon="hass:barcode",
                    key="serial",
                    name="Serial"
                )
            ),
            LinksysVelopNodeSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                node=node,
                description=LinksysVelopSensorDescription(
                    key="type",
                    name="Type"
                )
            ),
            LinksysVelopNodeSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                node=node,
                description=LinksysVelopSensorDescription(
                    key="",
                    name="Version",
                    state_value=lambda n: n.firmware.get("version", None)
                )
            ),
        ])
    # endregion

    async_add_entities(sensors)


class LinksysVelopMeshSensor(LinksysVelopMeshEntity, SensorEntity):
    """Representation of a sensor related to the Mesh"""

    def __init__(
        self,
        coordinator: LinksysVelopDataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: LinksysVelopSensorDescription
    ) -> None:
        """Constructor"""

        super().__init__(config_entry=config_entry, coordinator=coordinator)

        self._attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC if EntityCategory is None else EntityCategory.DIAGNOSTIC

        self.entity_description: LinksysVelopSensorDescription = description

        self._attr_name = f"{ENTITY_SLUG} Mesh: {self.entity_description.name}"
        self._attr_unique_id = f"{config_entry.entry_id}::" \
                               f"{ENTITY_DOMAIN.lower()}::" \
                               f"{slugify(self.entity_description.name)}"

    @property
    def extra_state_attributes(self) -> Optional[Mapping[str, Any]]:
        """Additional attributes for the sensor"""

        if (
            self.entity_description.extra_attributes
            and isinstance(self.entity_description.extra_attributes, Callable)
        ):
            return self.entity_description.extra_attributes(self._mesh)

    @property
    def native_value(self) -> StateType:
        """Get the state of the sensor"""

        if self.entity_description.state_value:
            return self.entity_description.state_value(self._mesh)
        else:
            return getattr(self._mesh, self.entity_description.key, None)


class LinksysVelopNodeSensor(LinksysVelopNodeEntity, SensorEntity):
    """Representation of a sensor for a node"""

    def __init__(
        self,
        coordinator: LinksysVelopDataUpdateCoordinator,
        node: Node,
        config_entry: ConfigEntry,
        description: LinksysVelopSensorDescription
    ) -> None:
        """Constructor"""

        self._node_id: str = node.unique_id
        super().__init__(config_entry=config_entry, coordinator=coordinator)

        self._attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC if EntityCategory is None else EntityCategory.DIAGNOSTIC

        self.entity_description: LinksysVelopSensorDescription = description

        self._attr_name = f"{ENTITY_SLUG} {self._node.name}: {self.entity_description.name}"
        self._attr_unique_id = f"{self._node.unique_id}::" \
                               f"{ENTITY_DOMAIN.lower()}::" \
                               f"{slugify(self.entity_description.name)}"

    @property
    def extra_state_attributes(self) -> Optional[Mapping[str, Any]]:
        """Additional attributes for the sensor"""

        if (
            self.entity_description.extra_attributes
            and isinstance(self.entity_description.extra_attributes, Callable)
        ):
            return self.entity_description.extra_attributes(self._node)

    @property
    def native_value(self) -> StateType:
        """Get the state of the sensor"""

        if self.entity_description.state_value:
            return self.entity_description.state_value(self._node)
        else:
            return getattr(self._node, self.entity_description.key, None)


class LinksysVelopMeshSpeedtestLatestSensor(LinksysVelopMeshSensor):
    """Representation of the sensor the latest Speedtest results"""

    _value: List = []

    async def _get_results(self):
        """Refresh the Speedtest details from the API"""

        results: List = await self._mesh.async_get_speedtest_results(only_completed=True, only_latest=True)
        if results:
            self._value = results

        self.async_schedule_update_ha_state()

    def _handle_coordinator_update(self) -> None:
        """Update the status information when the coordinator updates"""

        self._value = self._mesh.speedtest_results
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """Register for callbacks and set initial value"""

        await super().async_added_to_hass()
        self._value = self._mesh.speedtest_results
        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=SIGNAL_UPDATE_SPEEDTEST_RESULTS,
                target=self._get_results,
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
