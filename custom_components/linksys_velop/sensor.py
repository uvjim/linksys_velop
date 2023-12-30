"""Sensors for the mesh, nodes and devices."""

# region #-- imports --#
from __future__ import annotations

import dataclasses
import logging
from typing import Any, Callable, Dict, List

from homeassistant.components.sensor import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, UnitOfDataRate
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

from . import (
    LinksysVelopDeviceEntity,
    LinksysVelopMeshEntity,
    LinksysVelopNodeEntity,
    entity_cleanup,
)
from .const import (
    CONF_COORDINATOR,
    CONF_DEVICE_UI,
    CONF_NODE_IMAGES,
    DEF_UI_DEVICE_ID,
    DOMAIN,
    SIGNAL_UPDATE_SPEEDTEST_PROGRESS,
    SIGNAL_UPDATE_SPEEDTEST_RESULTS,
    UPDATE_DOMAIN,
)

# endregion

_LOGGER = logging.getLogger(__name__)


# region #-- sensor entity descriptions --#
@dataclasses.dataclass(frozen=True)
class AdditionalSensorDescription:
    """Represent the additional attributes for the sensor description."""

    if not hasattr(SensorEntityDescription, "entity_picture"):
        entity_picture: str | None = None
    extra_attributes: Callable | None = None
    state_value: Callable | None = None


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

    # region #-- Device sensors --#
    for device_id in config_entry.options.get(CONF_DEVICE_UI, []):
        sensors.extend(
            [
                LinksysVelopDeviceSensor(
                    additional_description=AdditionalSensorDescription(
                        extra_attributes=lambda d: {
                            "sites": d.parental_control_schedule.get(
                                "blocked_sites", []
                            )
                        },
                        state_value=lambda d: len(
                            d.parental_control_schedule.get("blocked_sites", [])
                        )
                        if d.unique_id != DEF_UI_DEVICE_ID
                        else None,
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        key="",
                        name="Blocked Sites",
                        state_class=SensorStateClass.MEASUREMENT,
                        translation_key="blocked_sites",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        key="description",
                        name="Description",
                        translation_key="description",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceSensor(
                    additional_description=AdditionalSensorDescription(
                        state_value=lambda d: next(iter(d.connected_adapters), {})
                        .get("signal_strength", "")
                        .lower()
                        or None,
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        key="",
                        name="Friendly Signal Strength",
                        translation_key="friendly_signal_strength",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceSensor(
                    additional_description=AdditionalSensorDescription(
                        state_value=lambda d: next(iter(d.connected_adapters), {}).get(
                            "ip"
                        ),
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        key="",
                        name="IP",
                        translation_key="ip",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceSensor(
                    additional_description=AdditionalSensorDescription(
                        state_value=lambda d: next(iter(d.connected_adapters), {}).get(
                            "ipv6"
                        ),
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        key="",
                        name="IPv6",
                        translation_key="ipv6",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceSensor(
                    additional_description=AdditionalSensorDescription(
                        state_value=lambda d: next(iter(d.connected_adapters), {}).get(
                            "mac"
                        ),
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        key="",
                        name="MAC",
                        translation_key="mac",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        key="manufacturer",
                        name="Manufacturer",
                        translation_key="manufacturer",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        key="model",
                        name="Model",
                        translation_key="model",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceSensor(
                    additional_description=AdditionalSensorDescription(
                        state_value=lambda d: d.name
                        if d.unique_id != DEF_UI_DEVICE_ID
                        else None,
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        key="",
                        name="Name",
                        translation_key="name",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        key="operating_system",
                        name="Operating System",
                        translation_key="operating_system",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        icon="hass:family-tree",
                        key="parent_name",
                        name="Parent",
                        translation_key="parent_name",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        icon="hass:barcode",
                        key="serial",
                        name="Serial",
                        translation_key="serial",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceSensor(
                    additional_description=AdditionalSensorDescription(
                        state_value=lambda d: next(iter(d.connected_adapters), {}).get(
                            "rssi"
                        ),
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                        key="",
                        name="Signal Strength",
                        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                        translation_key="signal_strength",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceSensor(
                    additional_description=AdditionalSensorDescription(
                        extra_attributes=(
                            lambda d: {
                                "entity_picture": f"{config_entry.options.get(CONF_NODE_IMAGES, '').rstrip('/ ').strip()}/"
                                f"{d.ui_type.lower()}.png"
                                if d.ui_type is not None
                                else None
                            }
                        )
                        if config_entry.options.get(CONF_NODE_IMAGES, "")
                        else None,
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        key="ui_type",
                        name="UI Type",
                        translation_key="ui_type",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceSensor(
                    additional_description=AdditionalSensorDescription(
                        state_value=lambda d: d.unique_id
                        if d.unique_id != DEF_UI_DEVICE_ID
                        else None,
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        key="unique_id",
                        name="ID",
                        translation_key="id",
                    ),
                    device_id=device_id,
                ),
            ]
        )
    # endregion

    # region #-- Mesh sensors --#
    sensors.extend(
        [
            LinksysVelopMeshSensor(
                additional_description=AdditionalSensorDescription(
                    extra_attributes=lambda m: {
                        "partitions": m.storage_available or None
                    },
                    state_value=lambda m: len(m.storage_available),
                ),
                config_entry=config_entry,
                coordinator=coordinator,
                description=SensorEntityDescription(
                    entity_registry_enabled_default=False,
                    icon="mdi:nas",
                    key="available_storage",
                    name="Available Storage",
                    state_class=SensorStateClass.MEASUREMENT,
                    translation_key="available_storage",
                ),
            ),
            LinksysVelopMeshSensor(
                additional_description=AdditionalSensorDescription(
                    extra_attributes=lambda m: {
                        "reservations": m.dhcp_reservations,
                    },
                    state_value=lambda m: len(m.dhcp_reservations),
                ),
                config_entry=config_entry,
                coordinator=coordinator,
                description=SensorEntityDescription(
                    entity_registry_enabled_default=False,
                    key="dhcp_reservations",
                    name="DHCP Reservations",
                    state_class=SensorStateClass.MEASUREMENT,
                    translation_key="dhcp_reservations",
                ),
            ),
            LinksysVelopMeshSensor(
                additional_description=AdditionalSensorDescription(
                    extra_attributes=lambda m: {
                        "devices": [
                            d for d in get_devices(mesh=m) if d.get("guest_network")
                        ]
                    },
                    state_value=lambda m: len(
                        [d for d in get_devices(mesh=m) if d.get("guest_network")]
                    ),
                ),
                config_entry=config_entry,
                coordinator=coordinator,
                description=SensorEntityDescription(
                    entity_registry_enabled_default=False,
                    key="guest_devices",
                    name="Guest Devices",
                    state_class=SensorStateClass.MEASUREMENT,
                    translation_key="guest_devices",
                ),
            ),
            LinksysVelopMeshSensor(
                additional_description=AdditionalSensorDescription(
                    extra_attributes=(
                        lambda m: {
                            "devices": [
                                {"name": d.get("name", ""), "id": d.get("id", "")}
                                for d in get_devices(mesh=m, state=False)
                            ]
                        }
                    ),
                    state_value=lambda m: len(get_devices(mesh=m, state=False)),
                ),
                config_entry=config_entry,
                coordinator=coordinator,
                description=SensorEntityDescription(
                    key="offline_devices",
                    name="Offline Devices",
                    state_class=SensorStateClass.MEASUREMENT,
                    translation_key="offline_devices",
                ),
            ),
            LinksysVelopMeshSensor(
                additional_description=AdditionalSensorDescription(
                    extra_attributes=lambda m: {"devices": get_devices(mesh=m)},
                    state_value=lambda m: len(get_devices(mesh=m)),
                ),
                config_entry=config_entry,
                coordinator=coordinator,
                description=SensorEntityDescription(
                    key="online_devices",
                    name="Online Devices",
                    state_class=SensorStateClass.MEASUREMENT,
                    translation_key="online_devices",
                ),
            ),
            LinksysVelopMeshSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=SensorEntityDescription(
                    icon="mdi:ip-network-outline",
                    key="wan_ip",
                    name="WAN IP",
                    translation_key="wan_ip",
                ),
            ),
        ]
    )

    # region #-- Speedtest sensors --#
    sensors_to_remove.append(
        LinksysVelopMeshSpeedtestLatestSensor(
            config_entry=config_entry,
            coordinator=coordinator,
            description=SensorEntityDescription(
                key="",
                name="Speedtest Latest",
            ),
        )
    )
    sensors.extend(
        [
            LinsysVelopMeshSpeedtestCurrentStatusSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=SensorEntityDescription(
                    entity_registry_enabled_default=False,
                    key="",
                    name="Speedtest Progress",
                    translation_key="speedtest_progress",
                ),
            ),
            LinksysVelopMeshSpeedtestLatestSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=SensorEntityDescription(
                    device_class=SensorDeviceClass.DATA_RATE,
                    entity_registry_enabled_default=False,
                    icon="mdi:cloud-download-outline",
                    key="download_bandwidth",
                    name="Speedtest Download Bandwidth",
                    native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
                    translation_key="download_bandwidth",
                ),
            ),
            LinksysVelopMeshSpeedtestLatestSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=SensorEntityDescription(
                    entity_registry_enabled_default=False,
                    icon="mdi:keyboard-return",
                    key="exit_code",
                    name="Speedtest Result",
                    translation_key="speedtest_result",
                ),
            ),
            LinksysVelopMeshSpeedtestLatestSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=SensorEntityDescription(
                    device_class=SensorDeviceClass.TIMESTAMP,
                    entity_registry_enabled_default=False,
                    key="timestamp",
                    name="Speedtest Last Run",
                    translation_key="speedtest_last_run",
                ),
            ),
            LinksysVelopMeshSpeedtestLatestSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=SensorEntityDescription(
                    entity_registry_enabled_default=False,
                    icon="mdi:timer-sync-outline",
                    key="latency",
                    name="Speedtest Latency",
                    native_unit_of_measurement="ms",
                    translation_key="speedtest_latency",
                ),
            ),
            LinksysVelopMeshSpeedtestLatestSensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=SensorEntityDescription(
                    device_class=SensorDeviceClass.DATA_RATE,
                    entity_registry_enabled_default=False,
                    icon="mdi:cloud-upload-outline",
                    key="upload_bandwidth",
                    name="Speedtest Upload Bandwidth",
                    native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
                    translation_key="upload_bandwidth",
                ),
            ),
        ]
    )
    # endregion
    # endregion

    # region #-- Node sensors --#
    node: Node
    for node in mesh.nodes:
        # region #-- standard sensors --#
        sensors.extend(
            [
                LinksysVelopNodeSensor(
                    additional_description=AdditionalSensorDescription(
                        extra_attributes=lambda n: {"devices": n.connected_devices}
                        if n.connected_devices
                        else {},
                        state_value=lambda n: len(n.connected_devices),
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=SensorEntityDescription(
                        key="",
                        name="Connected devices",
                        state_class=SensorStateClass.MEASUREMENT,
                        translation_key="connected_devices",
                    ),
                ),
                LinksysVelopNodeSensor(
                    additional_description=AdditionalSensorDescription(
                        state_value=lambda n: dt_util.parse_datetime(
                            n.last_update_check
                        )
                        if n.last_update_check
                        else None,
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=SensorEntityDescription(
                        device_class=SensorDeviceClass.TIMESTAMP,
                        entity_registry_enabled_default=False,
                        key="",
                        name="Last Update Check",
                        translation_key="last_update_check",
                    ),
                ),
                LinksysVelopNodeSensor(
                    additional_description=AdditionalSensorDescription(
                        entity_picture=(
                            f"{config_entry.options.get(CONF_NODE_IMAGES, '').rstrip('/ ').strip()}/{node.model}.png"
                        )
                        if config_entry.options.get(CONF_NODE_IMAGES, "")
                        else None,
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=SensorEntityDescription(
                        key="model",
                        name="Model",
                        translation_key="model",
                    ),
                ),
                LinksysVelopNodeSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=SensorEntityDescription(
                        icon="hass:barcode",
                        key="serial",
                        name="Serial",
                        translation_key="serial",
                    ),
                ),
                LinksysVelopNodeSensor(
                    additional_description=AdditionalSensorDescription(
                        state_value=lambda n: n.type.value,
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=SensorEntityDescription(
                        device_class=SensorDeviceClass.ENUM
                        if hasattr(SensorDeviceClass, "ENUM")
                        else "",
                        key="type",
                        name="Type",
                        options=["primary", "secondary"],
                        translation_key="node_type",
                    ),
                ),
            ]
        )
        if node.type is not NodeType.PRIMARY:
            sensors.append(
                LinksysVelopNodeSensor(
                    additional_description=AdditionalSensorDescription(
                        extra_attributes=lambda n: {"parent_ip": n.parent_ip},
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=SensorEntityDescription(
                        icon="hass:family-tree",
                        key="parent_name",
                        name="Parent",
                        translation_key="parent_name",
                    ),
                )
            )
        else:
            sensors_to_remove.append(
                LinksysVelopNodeSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=SensorEntityDescription(
                        key="parent_name",
                        name="Parent",
                    ),
                )
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
                        description=SensorEntityDescription(
                            key="",
                            name="Backhaul",
                        ),
                    ),
                ]
            )
            sensors.extend(
                [
                    LinksysVelopNodeSensor(
                        additional_description=AdditionalSensorDescription(
                            state_value=lambda n: dt_util.parse_datetime(
                                n.backhaul.get("last_checked")
                            )
                            if n.backhaul.get("last_checked")
                            else None,
                        ),
                        config_entry=config_entry,
                        coordinator=coordinator,
                        node=node,
                        description=SensorEntityDescription(
                            device_class=SensorDeviceClass.TIMESTAMP,
                            entity_registry_enabled_default=False,
                            key="",
                            name="Backhaul Last Checked",
                            translation_key="backhaul_last_checked",
                        ),
                    ),
                    LinksysVelopNodeSensor(
                        additional_description=AdditionalSensorDescription(
                            state_value=lambda n: n.backhaul.get("speed_mbps"),
                        ),
                        config_entry=config_entry,
                        coordinator=coordinator,
                        node=node,
                        description=SensorEntityDescription(
                            device_class=SensorDeviceClass.DATA_RATE
                            if hasattr(SensorDeviceClass, "DATA_RATE")
                            else "",
                            key="",
                            name="Backhaul Speed",
                            native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
                            translation_key="backhaul_speed",
                        ),
                    ),
                    LinksysVelopNodeSensor(
                        additional_description=AdditionalSensorDescription(
                            state_value=lambda n: n.backhaul.get(
                                "connection", "unknown"
                            ).lower(),
                        ),
                        config_entry=config_entry,
                        coordinator=coordinator,
                        node=node,
                        description=SensorEntityDescription(
                            device_class=SensorDeviceClass.ENUM
                            if hasattr(SensorDeviceClass, "ENUM")
                            else "",
                            icon="mdi:lan-connect"
                            if node.backhaul.get("connection", "").lower() == "wired"
                            else "mdi:wifi",
                            key="",
                            name="Backhaul Type",
                            options=["unknown", "wired", "wireless"],
                            translation_key="backhaul_connection_type",
                        ),
                    ),
                ]
            )
            # only add the backhaul signal strength if wireless, remove it otherwise
            if node.backhaul.get("connection", "").lower() == "wireless":
                sensors.extend(
                    [
                        LinksysVelopNodeSensor(
                            additional_description=AdditionalSensorDescription(
                                state_value=lambda n: n.backhaul.get("rssi_dbm"),
                            ),
                            config_entry=config_entry,
                            coordinator=coordinator,
                            node=node,
                            description=SensorEntityDescription(
                                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                                key="",
                                name="Backhaul Signal Strength",
                                native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                                translation_key="backhaul_signal_strength",
                            ),
                        ),
                        LinksysVelopNodeSensor(
                            additional_description=AdditionalSensorDescription(
                                state_value=lambda n: n.backhaul.get(
                                    "signal_strength", ""
                                ).lower()
                                or None,
                            ),
                            config_entry=config_entry,
                            coordinator=coordinator,
                            node=node,
                            description=SensorEntityDescription(
                                key="",
                                name="Backhaul Friendly Signal Strength",
                                translation_key="backhaul_friendly_signal_strength",
                            ),
                        ),
                    ]
                )
            else:
                sensors_to_remove.extend(
                    [
                        LinksysVelopNodeSensor(
                            config_entry=config_entry,
                            coordinator=coordinator,
                            node=node,
                            description=SensorEntityDescription(
                                key="",
                                name="Backhaul Signal Strength",
                            ),
                        ),
                        LinksysVelopNodeSensor(
                            config_entry=config_entry,
                            coordinator=coordinator,
                            node=node,
                            description=SensorEntityDescription(
                                key="",
                                name="Backhaul Friendly Signal Strength",
                            ),
                        ),
                    ]
                )
        # endregion

        # region #-- image path sensor --#
        if config_entry.options.get(CONF_NODE_IMAGES):
            sensors.append(
                LinksysVelopNodeSensor(
                    additional_description=AdditionalSensorDescription(
                        state_value=lambda n: (
                            f"{config_entry.options.get(CONF_NODE_IMAGES, '').rstrip('/ ').strip()}/{n.model}.png"
                        ),
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=SensorEntityDescription(
                        entity_registry_enabled_default=False,
                        key="",
                        name="Image",
                        translation_key="image",
                    ),
                )
            )
        else:  # remove the sensor if not needed anymore
            sensors_to_remove.append(
                LinksysVelopNodeSensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=SensorEntityDescription(
                        key="",
                        name="Image",
                    ),
                )
            )
        # endregion

        # region #-- version sensors if needed --#
        sensors_versions: List[LinksysVelopNodeSensor] = [
            LinksysVelopNodeSensor(
                additional_description=AdditionalSensorDescription(
                    state_value=lambda n: n.firmware.get("latest_version", None),
                ),
                config_entry=config_entry,
                coordinator=coordinator,
                node=node,
                description=SensorEntityDescription(
                    key="",
                    name="Newest Version",
                ),
            ),
            LinksysVelopNodeSensor(
                additional_description=AdditionalSensorDescription(
                    state_value=lambda n: n.firmware.get("version", None),
                ),
                config_entry=config_entry,
                coordinator=coordinator,
                node=node,
                description=SensorEntityDescription(
                    key="",
                    name="Version",
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


class LinksysVelopDeviceSensor(LinksysVelopDeviceEntity, SensorEntity):
    """Representation of a sensor related to the Device."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: SensorEntityDescription,
        device_id: str,
        additional_description: AdditionalSensorDescription | None = None,
    ) -> None:
        """Initialise Device sensor."""
        self.entity_domain = ENTITY_DOMAIN
        self._additional_description: AdditionalSensorDescription | None = (
            additional_description
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        super().__init__(
            config_entry=config_entry,
            coordinator=coordinator,
            description=description,
            device_id=device_id,
        )

    @property
    def native_value(self) -> StateType:
        """Get the state of the sensor."""
        if (
            self._additional_description is not None
            and self._additional_description.state_value
        ):
            return self._additional_description.state_value(self._device)

        return getattr(self._device, self.entity_description.key, None)


class LinksysVelopMeshSensor(LinksysVelopMeshEntity, SensorEntity):
    """Representation of a sensor related to the Mesh."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: SensorEntityDescription,
        additional_description: AdditionalSensorDescription | None = None,
    ) -> None:
        """Initialise Mesh sensor."""
        self.entity_domain = ENTITY_DOMAIN
        self._additional_description: AdditionalSensorDescription | None = (
            additional_description
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        super().__init__(
            config_entry=config_entry, coordinator=coordinator, description=description
        )

    @property
    def native_value(self) -> StateType:
        """Get the state of the sensor."""
        if (
            self._additional_description is not None
            and self._additional_description.state_value
        ):
            return self._additional_description.state_value(self._mesh)

        return getattr(self._mesh, self.entity_description.key, None)


class LinksysVelopNodeSensor(LinksysVelopNodeEntity, SensorEntity):
    """Representation of a sensor for a node."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        node: Node,
        config_entry: ConfigEntry,
        description: SensorEntityDescription,
        additional_description: AdditionalSensorDescription | None = None,
    ) -> None:
        """Initialise Node sensor."""
        self._additional_description: AdditionalSensorDescription | None = (
            additional_description
        )
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
        if (
            self._additional_description is not None
            and self._additional_description.state_value
        ):
            return self._additional_description.state_value(self._node)

        return getattr(self._node, self.entity_description.key, None)


class LinksysVelopMeshSpeedtestLatestSensor(LinksysVelopMeshSensor):
    """Representation of a Speedtest sensor."""

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
    def native_value(self) -> StateType:
        """Set the value of the sensor."""
        ret = None
        if self._value:
            ret = self._value.get(self.entity_description.key)
            if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
                ret = dt_util.parse_datetime(ret)

        return ret


class LinsysVelopMeshSpeedtestCurrentStatusSensor(LinksysVelopMeshSensor):
    """Representation of the Speedtest current status sensor."""

    _value: str = ""

    async def _set_value(self, progress: str) -> None:
        """Set the value of the sensor to the status given by the signal."""
        self._value = progress
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register for callbacks and set initial value."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=SIGNAL_UPDATE_SPEEDTEST_PROGRESS,
                target=self._set_value,
            )
        )

    @property
    def native_value(self) -> StateType:
        """Set the value of the sensor."""
        return self._value
