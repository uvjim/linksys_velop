"""Sensors for the mesh, nodes and devices."""

# region #-- imports --#
from __future__ import annotations

import dataclasses
import logging
from typing import Any, Callable, Dict, List, Mapping

from homeassistant.components.sensor import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT

# TODO: remove try/except when minimum version is 2023.1.0
try:
    from homeassistant.const import UnitOfDataRate

    DATA_RATE_MEGABITS_PER_SECOND = UnitOfDataRate.MEGABITS_PER_SECOND
except ImportError:
    from homeassistant.const import DATA_RATE_MEGABITS_PER_SECOND

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from pyvelop.device import Device
from pyvelop.mesh import Mesh
from pyvelop.node import Node, NodeType

from . import LinksysVelopMeshEntity, LinksysVelopNodeEntity, entity_cleanup
from .const import (
    CONF_COORDINATOR,
    CONF_NODE_IMAGES,
    DOMAIN,
    SIGNAL_UPDATE_SPEEDTEST_RESULTS,
    UPDATE_DOMAIN,
)

# endregion

_LOGGER = logging.getLogger(__name__)


# region #-- sensor entity descriptions --#
@dataclasses.dataclass
class OptionalLinksysVelopDescription:
    """Represent the optional attributes of the sensor description."""

    if not hasattr(SensorEntityDescription, "entity_picture"):
        entity_picture: str | None = None
    extra_attributes: Callable | None = None
    state_value: Callable | None = None
    # TODO: remove when minimum version is 2023.1.0
    if not hasattr(SensorEntityDescription, "options"):
        options: List[str] | None = None
    # TODO: remove when minimum version is 2023.1.0
    if not hasattr(SensorEntityDescription, "translation_key"):
        translation_key: str | None = None


@dataclasses.dataclass
class RequiredLinksysVelopDescription:
    """Represent the required attributes of the sensor description."""


@dataclasses.dataclass
class LinksysVelopSensorDescription(
    OptionalLinksysVelopDescription,
    SensorEntityDescription,
    RequiredLinksysVelopDescription,
):
    """Describes sensor entity."""


# endregion


# region #-- general functions for nodes and the mesh --#
def get_devices(mesh: Mesh, state: bool = True) -> List[Dict[str, Any]]:
    """Get the matching devices from the Mesh."""
    ret: List[Dict[str, Any]] = []
    device: Device
    for device in mesh.devices:
        if device.status is state:
            ret.append({"name": device.name, "id": device.unique_id})
            for adapter in device.network:
                if adapter.get("ip"):
                    ret[-1] = dict(
                        **ret[-1],
                        ip=adapter.get("ip"),
                        connection=adapter.get("type"),
                        guest_network=adapter.get("guest_network"),
                    )

    return ret


# endregion


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
    mesh: Mesh = coordinator.data
    sensors: List[
        LinksysVelopMeshSensor
        | LinksysVelopNodeSensor
        | LinksysVelopMeshSpeedtestLatestSensor
    ] = []
    sensors_to_remove: List[LinksysVelopMeshSensor | LinksysVelopNodeSensor] = []

    # region #-- Mesh sensors --#
    mesh_sensor_descriptions: tuple[LinksysVelopSensorDescription, ...] = (
        LinksysVelopSensorDescription(
            entity_registry_enabled_default=False,
            extra_attributes=lambda m: {"partitions": m.storage_available or None},
            icon="mdi:nas",
            key="available_storage",
            name="Available Storage",
            state_value=lambda m: len(m.storage_available),
        ),
        LinksysVelopSensorDescription(
            entity_registry_enabled_default=False,
            extra_attributes=lambda m: {
                "reservations": m.dhcp_reservations,
            },
            key="dhcp_reservations",
            name="DHCP Reservations",
            state_value=lambda m: len(m.dhcp_reservations),
        ),
        LinksysVelopSensorDescription(
            entity_registry_enabled_default=False,
            extra_attributes=lambda m: {
                "devices": [d for d in get_devices(mesh=m) if d.get("guest_network")]
            },
            key="guest_devices",
            name="Guest Devices",
            state_value=lambda m: len(
                [d for d in get_devices(mesh=m) if d.get("guest_network")]
            ),
        ),
        LinksysVelopSensorDescription(
            extra_attributes=(
                lambda m: {
                    "devices": [
                        {"name": d.get("name", ""), "id": d.get("id", "")}
                        for d in get_devices(mesh=m, state=False)
                    ]
                }
            ),
            key="offline_devices",
            name="Offline Devices",
            state_value=lambda m: len(get_devices(mesh=m, state=False)),
        ),
        LinksysVelopSensorDescription(
            extra_attributes=lambda m: {"devices": get_devices(mesh=m)},
            key="online_devices",
            name="Online Devices",
            state_value=lambda m: len(get_devices(mesh=m)),
        ),
        LinksysVelopSensorDescription(
            icon="mdi:ip-network-outline",
            key="wan_ip",
            name="WAN IP",
        ),
    )
    for sensor_description in mesh_sensor_descriptions:
        sensors.append(
            LinksysVelopMeshSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=sensor_description,
            )
        )

    sensors.extend(
        [
            LinksysVelopMeshSpeedtestLatestSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=LinksysVelopSensorDescription(
                    device_class=SensorDeviceClass.TIMESTAMP,
                    key="",
                    name="Speedtest Latest",
                ),
            )
        ]
    )
    # endregion

    # region #-- Node sensors --#
    node: Node
    for node in mesh.nodes:
        # region #-- standard sensors --#
        sensors.extend(
            [
                LinksysVelopNodeSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=LinksysVelopSensorDescription(
                        extra_attributes=lambda n: {"devices": n.connected_devices}
                        if n.connected_devices
                        else {},
                        key="",
                        name="Connected devices",
                        state_value=lambda n: len(n.connected_devices),
                    ),
                ),
                LinksysVelopNodeSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=LinksysVelopSensorDescription(
                        device_class=SensorDeviceClass.TIMESTAMP,
                        entity_registry_enabled_default=False,
                        key="",
                        name="Last Update Check",
                        state_value=lambda n: dt_util.parse_datetime(
                            n.last_update_check
                        )
                        if n.last_update_check
                        else None,
                    ),
                ),
                LinksysVelopNodeSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    # TODO: remove if SensorEntityDescription ever includes entity_picture natively
                    description=LinksysVelopSensorDescription(  # pylint: disable=unexpected-keyword-arg
                        entity_picture=(
                            f"{config_entry.options.get(CONF_NODE_IMAGES, '').rstrip('/ ').strip()}/{node.model}.png"
                        )
                        if config_entry.options.get(CONF_NODE_IMAGES, "")
                        else None,
                        key="model",
                        name="Model",
                    ),
                ),
                LinksysVelopNodeSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=LinksysVelopSensorDescription(
                        extra_attributes=lambda n: {"parent_ip": n.parent_ip},
                        icon="hass:family-tree",
                        key="parent_name",
                        name="Parent",
                    ),
                ),
                LinksysVelopNodeSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=LinksysVelopSensorDescription(
                        icon="hass:barcode", key="serial", name="Serial"
                    ),
                ),
                LinksysVelopNodeSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    # TODO: remove pylint disables when minimum version is 2023.1.0
                    description=LinksysVelopSensorDescription(  # pylint: disable=unexpected-keyword-arg
                        device_class=SensorDeviceClass.ENUM  # pylint: disable=no-member
                        if hasattr(SensorDeviceClass, "ENUM")
                        else "",
                        key="type",
                        name="Type",
                        options=["primary", "secondary"],
                        state_value=lambda n: n.type.value,
                        translation_key="node_type",
                    ),
                ),
            ]
        )
        # endregion

        # region #-- backhaul sensors --#
        if node.type is not NodeType.PRIMARY:
            sensors_to_remove.extend(  # remove the old backhaul sensor
                [
                    LinksysVelopNodeSensor(
                        config_entry=config_entry,
                        coordinator=coordinator,
                        node=node,
                        description=LinksysVelopSensorDescription(
                            key="",
                            name="Backhaul",
                        ),
                    ),
                ]
            )
            sensors.extend(
                [
                    LinksysVelopNodeSensor(
                        config_entry=config_entry,
                        coordinator=coordinator,
                        node=node,
                        description=LinksysVelopSensorDescription(
                            device_class=SensorDeviceClass.TIMESTAMP,
                            entity_registry_enabled_default=False,
                            key="",
                            name="Backhaul Last Checked",
                            state_value=lambda n: dt_util.parse_datetime(
                                n.backhaul.get("last_checked")
                            )
                            if n.backhaul.get("last_checked")
                            else None,
                        ),
                    ),
                    LinksysVelopNodeSensor(
                        config_entry=config_entry,
                        coordinator=coordinator,
                        node=node,
                        description=LinksysVelopSensorDescription(
                            # TODO: remove pylint disables when minimum version is 2023.1.0
                            device_class=SensorDeviceClass.DATA_RATE  # pylint: disable=no-member
                            if hasattr(SensorDeviceClass, "DATA_RATE")
                            else "",
                            key="",
                            name="Backhaul Speed",
                            state_value=lambda n: n.backhaul.get("speed_mbps"),
                            native_unit_of_measurement=DATA_RATE_MEGABITS_PER_SECOND,
                        ),
                    ),
                    LinksysVelopNodeSensor(
                        config_entry=config_entry,
                        coordinator=coordinator,
                        node=node,
                        # TODO: remove pylint disables when minimum version is 2023.1.0
                        description=LinksysVelopSensorDescription(  # pylint: disable=unexpected-keyword-arg
                            device_class=SensorDeviceClass.ENUM  # pylint: disable=no-member
                            if hasattr(SensorDeviceClass, "ENUM")
                            else "",
                            icon="mdi:lan-connect"
                            if node.backhaul.get("connection", "").lower() == "wired"
                            else "mdi:wifi",
                            key="",
                            name="Backhaul Type",
                            options=["wired", "wireless"],
                            state_value=lambda n: n.backhaul.get(
                                "connection", ""
                            ).lower(),
                            translation_key="connection_type",
                        ),
                    ),
                ]
            )
            # only add the backhaul signal strength if wireless, remove it otherwise
            if node.backhaul.get("connection", "").lower() == "wireless":
                sensors.append(
                    LinksysVelopNodeSensor(
                        config_entry=config_entry,
                        coordinator=coordinator,
                        node=node,
                        description=LinksysVelopSensorDescription(
                            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                            extra_attributes=lambda n: {
                                k: v
                                for k, v in n.backhaul.items()
                                if k
                                not in (
                                    "connection",
                                    "last_checked",
                                    "rssi_dbm",
                                    "speed_mbps",
                                )
                            },
                            key="",
                            name="Backhaul Signal Strength",
                            native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                            state_value=lambda n: n.backhaul.get("rssi_dbm"),
                        ),
                    )
                )
            else:
                sensors_to_remove.append(
                    LinksysVelopNodeSensor(
                        config_entry=config_entry,
                        coordinator=coordinator,
                        node=node,
                        description=LinksysVelopSensorDescription(
                            key="",
                            name="Backhaul Signal Strength",
                        ),
                    )
                )
        # endregion

        # region #-- image path sensor --#
        if config_entry.options.get(CONF_NODE_IMAGES):
            sensors.append(
                LinksysVelopNodeSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=LinksysVelopSensorDescription(
                        entity_registry_enabled_default=False,
                        key="",
                        name="Image",
                        state_value=lambda n: (
                            f"{config_entry.options.get(CONF_NODE_IMAGES, '').rstrip('/ ').strip()}/{n.model}.png"
                        ),
                    ),
                )
            )
        else:  # remove the sensor if not needed anymore
            sensors_to_remove.append(
                LinksysVelopNodeSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=LinksysVelopSensorDescription(
                        key="",
                        name="Image",
                    ),
                )
            )
        # endregion

        # region #-- version sensors if needed --#
        sensors_versions: List[LinksysVelopNodeSensor] = [
            LinksysVelopNodeSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                node=node,
                description=LinksysVelopSensorDescription(
                    key="",
                    name="Newest Version",
                    state_value=lambda n: n.firmware.get("latest_version", None),
                ),
            ),
            LinksysVelopNodeSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                node=node,
                description=LinksysVelopSensorDescription(
                    key="",
                    name="Version",
                    state_value=lambda n: n.firmware.get("version", None),
                ),
            ),
        ]
        if UPDATE_DOMAIN is None:
            sensors.extend(sensors_versions)
        else:
            sensors_to_remove.extend(sensors_versions)
        # endregion

    # endregion

    async_add_entities(sensors)

    if sensors_to_remove:
        entity_cleanup(config_entry=config_entry, entities=sensors_to_remove, hass=hass)


class LinksysVelopMeshSensor(LinksysVelopMeshEntity, SensorEntity):
    """Representation of a sensor related to the Mesh."""

    entity_description: LinksysVelopSensorDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: LinksysVelopSensorDescription,
    ) -> None:
        """Initialise Mesh sensor."""
        self.entity_domain = ENTITY_DOMAIN
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        super().__init__(
            config_entry=config_entry, coordinator=coordinator, description=description
        )

    @property
    def native_value(self) -> StateType:
        """Get the state of the sensor."""
        if self.entity_description.state_value:
            return self.entity_description.state_value(self._mesh)

        return getattr(self._mesh, self.entity_description.key, None)


class LinksysVelopNodeSensor(LinksysVelopNodeEntity, SensorEntity):
    """Representation of a sensor for a node."""

    entity_description: LinksysVelopSensorDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        node: Node,
        config_entry: ConfigEntry,
        description: LinksysVelopSensorDescription,
    ) -> None:
        """Initialise Node sensor."""
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self.entity_domain = ENTITY_DOMAIN
        super().__init__(
            config_entry=config_entry,
            coordinator=coordinator,
            description=description,
            node=node,
        )

    @property
    def native_value(self) -> StateType:
        """Get the state of the sensor."""
        if self.entity_description.state_value:
            return self.entity_description.state_value(self._node)

        return getattr(self._node, self.entity_description.key, None)


class LinksysVelopMeshSpeedtestLatestSensor(LinksysVelopMeshSensor):
    """Representation of the sensor the latest Speedtest results."""

    _value: Dict = {}

    async def _get_results(self):
        """Refresh the Speedtest details from the API."""
        results: List = await self._mesh.async_get_speedtest_results(
            only_completed=True, only_latest=True
        )
        if results:
            self._value = results[0]

        self.async_schedule_update_ha_state()

    def _handle_coordinator_update(self) -> None:
        """Update the status information when the coordinator updates."""
        self._value = self._mesh.latest_speedtest_result
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """Register for callbacks and set initial value."""
        await super().async_added_to_hass()
        self._value = self._mesh.latest_speedtest_result
        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=SIGNAL_UPDATE_SPEEDTEST_RESULTS,
                target=self._get_results,
            )
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Set the additional attributes for the sensor."""
        ret = None
        if self._value:
            ret = self._value.copy()
            ret.pop("timestamp")

        return ret

    @property
    def native_value(self) -> dt_util.dt.datetime:
        """Set the value of the sensor to the time the results were generated."""
        ret = None

        if self._value:
            ret = dt_util.parse_datetime(self._value.get("timestamp"))
        return ret
