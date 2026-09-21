"""Sensor entities for Linksys Velop."""

# region #-- imports --#
import datetime as dt
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Any, cast, override

from homeassistant.components.sensor import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify
from pyvelop.mesh import (
    MeshSnapshot,
    SpeedtestExitCode,
    SpeedtestResult,
    SpeedtestStatus,
)
from pyvelop.mesh_attribute import MeshAttribute
from pyvelop.mesh_entity import (
    AdapterInfo,
    ConnectionType,
    DeviceEntity,
    NodeEntity,
    NodeType,
    SignalStrength,
)

from .const import CONF_NODE_IMAGES, CONF_UI_DEVICES
from .coordinator import (
    CoordinatorTimers,
    LinksysVelopConfigEntry,
    LinksysVelopDataUpdateCoordinatorMultiUse,
)
from .entities import (
    EntityType,
    LinksysVelopEntityContext,
    LinksysVelopEntityDescription,
    LinksysVelopMultiUseEntity,
    TargetEntityType,
)
from .helpers import remove_velop_entity_from_registry
from .logger import Logger

# endregion

_LOGGER: Logger = Logger(logging.getLogger(__name__))


@dataclass(frozen=True, kw_only=True)
class LinksysVelopSensorEntityDescription(
    LinksysVelopEntityDescription, SensorEntityDescription
):
    """Describes Velop sensor entity."""

    esa_fn: Callable[..., dict[str, Any]] | None = None
    pic_fn: (
        Callable[
            [LinksysVelopDataUpdateCoordinatorMultiUse, TargetEntityType], str | None
        ]
        | None
    ) = None
    value_fn: (
        Callable[
            [
                LinksysVelopDataUpdateCoordinatorMultiUse,
                TargetEntityType,
            ],
            StateType | dt.date | dt.datetime | Decimal,
        ]
        | None
    ) = None


def get_devices(mesh: TargetEntityType, state: bool = True) -> list[dict[str, Any]]:
    """Get the matching devices from the Mesh."""
    ret: list[dict[str, Any]] = []

    if not isinstance(mesh, MeshSnapshot):
        return ret

    for device in mesh.devices:
        if device.status.value == state:
            props: dict[str, Any] = {
                "name": device.name.value,
                "id": device.unique_id.value,
            }
            adi: AdapterInfo | None = next(
                (adapter for adapter in device.adapter_info), None
            )
            if adi is not None and device.status.value:
                props["type"] = adi.type.value
                props["guest_network"] = adi.guest_network
                props["ip"] = adi.ip
                props["ipv6"] = adi.ipv6
                props["parent_name"] = device.parent_name.value
            ret.append(props)

    return ret


def get_device_adapter_info(device: DeviceEntity, key: str) -> Any:
    """Retrieve the give details about a device adapter."""

    ret: Any = None
    adi: AdapterInfo | None = next(iter(device.adapter_info), None)
    if adi is not None:
        ret = getattr(adi, key, None)

    return ret


def get_node_backhaul_info(node: NodeEntity, key: str) -> Any:
    """Get the given backhaul property."""

    ret: Any = None
    if node.backhaul is not None:
        ret = getattr(node.backhaul, key, None)

    return ret


def get_node_devices(node: NodeEntity) -> list[dict[str, Any]]:
    """Get the details needed for the connected devices extra attributes."""

    ret: list[dict[str, Any]] = []
    for device in node.connected_devices:
        props: dict[str, Any] = {
            "name": device.name.value,
            "id": device.unique_id.value,
        }
        adi: AdapterInfo | None = next((adi for adi in device.adapter_info), None)
        if adi is not None:
            props["type"] = adi.type
            props["guest_network"] = adi.guest_network
            props["ip"] = adi.ip
            props["ipv6"] = adi.ipv6
        ret.append(props)

    return ret


def get_node_picture(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse, target: TargetEntityType
) -> str | None:
    """Retrieve the path to the icon to show for target.

    :param coordinator: The data update coordinator used to refresh the mesh state.
    :param target: The mesh entity to retrieve the icon for.
    :returns: Path to the icon.
    """

    if not isinstance(target, NodeEntity):
        return

    prefix: str = coordinator.config_entry.options.get(CONF_NODE_IMAGES, "")
    if not prefix:
        return

    return f"{prefix.rstrip('/').strip()}/{target.model}.png"


def get_speedtest_data(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse, name: str
) -> StateType | dt.date | dt.datetime | Decimal:
    """Retrieve the specified property for Speedtest properties.

    Priortiy is given to data when a Speedtest is in progress.

    :param coordinator:
    :param name:
    :return: the required data
    """

    speedtest_results: SpeedtestResult | None = (
        coordinator.config_entry.runtime_data.speedtest_data
    )
    if speedtest_results is None and coordinator.data.mesh is not None:
        speedtest_results = coordinator.data.mesh.speedtest_latest_complete.value

    if speedtest_results is None or not hasattr(speedtest_results, name):
        return None

    return getattr(speedtest_results, name, None)


def get_speedtest_enum(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse, name: str
) -> str | None:
    """Retrieve the specified Speedtest property as a lower-cased enum option.

    :param coordinator:
    :param name:
    :return: the lower-cased value or None if there is no value
    """

    ret: StateType | dt.date | dt.datetime | Decimal = get_speedtest_data(
        coordinator, name
    )

    return str(ret).lower() if ret is not None else None


ENTITIES: Mapping[str, tuple[LinksysVelopSensorEntityDescription, ...]] = (
    MappingProxyType(
        {
            "adapter_info": (
                LinksysVelopSensorEntityDescription(
                    device_class=SensorDeviceClass.ENUM,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="",
                    name="Friendly Signal Strength",
                    options=[val.lower() for val in SignalStrength],
                    target_type=EntityType.DEVICE,
                    translation_key="friendly_signal_strength",
                    value_fn=lambda _, device: (
                        str(get_device_adapter_info(device, "signal_strength")).lower()
                        if isinstance(device, DeviceEntity)
                        and get_device_adapter_info(device, "signal_strength")
                        is not None
                        else None
                    ),
                ),
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="",
                    name="IP",
                    target_type=EntityType.DEVICE,
                    translation_key="ip",
                    value_fn=lambda _, device: (
                        get_device_adapter_info(device, "ip")
                        if isinstance(device, DeviceEntity)
                        else None
                    ),
                ),
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="",
                    name="IPv6",
                    target_type=EntityType.DEVICE,
                    translation_key="ipv6",
                    value_fn=lambda _, device: (
                        get_device_adapter_info(device, "ipv6")
                        if isinstance(device, DeviceEntity)
                        else None
                    ),
                ),
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="",
                    name="MAC",
                    target_type=EntityType.DEVICE,
                    translation_key="mac",
                    value_fn=lambda _, device: (
                        get_device_adapter_info(device, "mac")
                        if isinstance(device, DeviceEntity)
                        else None
                    ),
                ),
                LinksysVelopSensorEntityDescription(
                    device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="",
                    name="Signal Strength",
                    native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                    target_type=EntityType.DEVICE,
                    translation_key="signal_strength",
                    value_fn=lambda _, device: (
                        get_device_adapter_info(device, "rssi_dbm")
                        if isinstance(device, DeviceEntity)
                        else None
                    ),
                ),
            ),
            "connected_devices": (
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    esa_fn=lambda node: (
                        {"devices": get_node_devices(node)}
                        if isinstance(node, NodeEntity) and len(node.connected_devices)
                        else {}
                    ),
                    key="",
                    name="Connected Devices",
                    state_class=SensorStateClass.MEASUREMENT,
                    target_type=EntityType.NODE,
                    translation_key="connected_devices",
                    value_fn=lambda _, node: (
                        len(node.connected_devices)
                        if isinstance(node, NodeEntity)
                        else None
                    ),
                ),
            ),
            "description": (
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="description",
                    name="Description",
                    target_type=EntityType.DEVICE,
                    translation_key="description",
                ),
            ),
            "devices": (
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    esa_fn=lambda mesh: (
                        {"devices": get_devices(mesh, False)}
                        if get_devices(mesh, False)
                        else {}
                    ),
                    key="",
                    name="Offline Devices",
                    state_class=SensorStateClass.MEASUREMENT,
                    target_type=EntityType.MESH,
                    translation_key="offline_devices",
                    value_fn=lambda _, mesh: (
                        len(get_devices(mesh, False))
                        if isinstance(mesh, MeshSnapshot)
                        else None
                    ),
                ),
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    esa_fn=lambda mesh: (
                        {"devices": get_devices(mesh)} if get_devices(mesh) else {}
                    ),
                    key="",
                    name="Online Devices",
                    state_class=SensorStateClass.MEASUREMENT,
                    target_type=EntityType.MESH,
                    translation_key="online_devices",
                    value_fn=lambda _, mesh: (
                        len(get_devices(mesh))
                        if isinstance(mesh, MeshSnapshot)
                        else None
                    ),
                ),
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    esa_fn=lambda mesh: (
                        {
                            "devices": (
                                [
                                    device
                                    for device in get_devices(mesh)
                                    if device.get("guest_network")
                                ]
                            )
                        }
                        if [
                            device
                            for device in get_devices(mesh)
                            if device.get("guest_network")
                        ]
                        else {}
                    ),
                    key="",
                    name="Guest Devices",
                    state_class=SensorStateClass.MEASUREMENT,
                    target_type=EntityType.MESH,
                    translation_key="guest_devices",
                    value_fn=lambda _, mesh: (
                        len(
                            [
                                device
                                for device in get_devices(mesh)
                                if device.get("guest_network")
                            ]
                        )
                        if isinstance(mesh, MeshSnapshot)
                        else None
                    ),
                ),
            ),
            "dhcp_reservations": (
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    esa_fn=lambda mesh: (
                        {
                            "reservations": mesh.dhcp_reservations.value,
                        }
                        if mesh.dhcp_reservations
                        else {}
                    ),
                    key="",
                    name="DHCP Reservations",
                    state_class=SensorStateClass.MEASUREMENT,
                    target_type=EntityType.MESH,
                    translation_key="dhcp_reservations",
                    value_fn=lambda _, mesh: (
                        len(mesh.dhcp_reservations)
                        if isinstance(mesh, MeshSnapshot)
                        else None
                    ),
                ),
            ),
            "last_update_check": (
                LinksysVelopSensorEntityDescription(
                    device_class=SensorDeviceClass.TIMESTAMP,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="",
                    name="Last Update Check",
                    target_type=EntityType.NODE,
                    translation_key="last_update_check",
                    value_fn=lambda _, node: (
                        node.last_update_check.value
                        if isinstance(node, NodeEntity)
                        and node.last_update_check.value is not None
                        else None
                    ),
                ),
            ),
            "manufacturer": (
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="manufacturer",
                    name="Manufacturer",
                    target_type=EntityType.DEVICE,
                    translation_key="manufacturer",
                ),
            ),
            "model": (
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="model",
                    name="Model",
                    target_type=EntityType.DEVICE,
                    translation_key="model",
                ),
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="model",
                    name="Model",
                    pic_fn=get_node_picture,
                    target_type=EntityType.NODE,
                    translation_key="model",
                ),
            ),
            "operating_system": (
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="operating_system",
                    name="Operating System",
                    target_type=EntityType.DEVICE,
                    translation_key="operating_system",
                ),
            ),
            "parent_name": (
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="parent_name",
                    name="Parent",
                    translation_key="parent_name",
                    target_type=EntityType.DEVICE,
                ),
            ),
            "parental_control_schedule": (
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    esa_fn=lambda device: (
                        {
                            "sites": device.parental_control_schedule.value.get(
                                "blocked_sites", []
                            )
                        }
                        if isinstance(device, DeviceEntity)
                        and device.parental_control_schedule.value.get(
                            "blocked_sites", []
                        )
                        else {}
                    ),
                    key="",
                    name="Blocked Sites",
                    state_class=SensorStateClass.MEASUREMENT,
                    target_type=EntityType.DEVICE,
                    translation_key="blocked_sites",
                    value_fn=lambda _, device: (
                        len(
                            device.parental_control_schedule.value.get(
                                "blocked_sites", []
                            )
                        )
                        if isinstance(device, DeviceEntity)
                        else None
                    ),
                ),
            ),
            "serial": (
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="serial",
                    name="Serial",
                    target_type=EntityType.DEVICE,
                    translation_key="serial",
                ),
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="serial",
                    name="Serial",
                    target_type=EntityType.NODE,
                    translation_key="serial",
                ),
            ),
            "speedtest_latest_complete": (
                LinksysVelopSensorEntityDescription(
                    device_class=SensorDeviceClass.DATA_RATE,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="",
                    name="Speedtest Download Bandwidth",
                    native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
                    suggested_display_precision=2,
                    target_type=EntityType.MESH,
                    translation_key="download_bandwidth",
                    value_fn=lambda coordinator, _: (
                        get_speedtest_data(coordinator, "download_bandwidth")
                        if isinstance(
                            coordinator, LinksysVelopDataUpdateCoordinatorMultiUse
                        )
                        else None
                    ),
                ),
                LinksysVelopSensorEntityDescription(
                    device_class=SensorDeviceClass.TIMESTAMP,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="",
                    name="Speedtest Last Run",
                    target_type=EntityType.MESH,
                    translation_key="speedtest_last_run",
                    value_fn=lambda coordinator, _: (
                        get_speedtest_data(coordinator, "timestamp")
                        if isinstance(
                            coordinator, LinksysVelopDataUpdateCoordinatorMultiUse
                        )
                        and get_speedtest_data(coordinator, "timestamp")
                        != dt.datetime.min.replace(tzinfo=dt.UTC)
                        else None
                    ),
                ),
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="",
                    name="Speedtest Latency",
                    native_unit_of_measurement="ms",
                    target_type=EntityType.MESH,
                    translation_key="speedtest_latency",
                    value_fn=lambda coordinator, _: (
                        get_speedtest_data(coordinator, "latency")
                        if isinstance(
                            coordinator, LinksysVelopDataUpdateCoordinatorMultiUse
                        )
                        else None
                    ),
                ),
                LinksysVelopSensorEntityDescription(
                    device_class=SensorDeviceClass.ENUM,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="",
                    name="Speedtest Progress",
                    options=[val.lower() for val in SpeedtestStatus],
                    target_type=EntityType.MESH,
                    translation_key="speedtest_progress",
                    value_fn=lambda coordinator, _: (
                        get_speedtest_enum(coordinator, "friendly_status")
                        if isinstance(
                            coordinator, LinksysVelopDataUpdateCoordinatorMultiUse
                        )
                        else None
                    ),
                ),
                LinksysVelopSensorEntityDescription(
                    device_class=SensorDeviceClass.ENUM,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="",
                    name="Speedtest Result",
                    options=[val.lower() for val in SpeedtestExitCode],
                    target_type=EntityType.MESH,
                    translation_key="speedtest_result",
                    value_fn=lambda coordinator, _: (
                        get_speedtest_enum(coordinator, "exit_code")
                        if isinstance(
                            coordinator, LinksysVelopDataUpdateCoordinatorMultiUse
                        )
                        else None
                    ),
                ),
                LinksysVelopSensorEntityDescription(
                    device_class=SensorDeviceClass.DATA_RATE,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="",
                    name="Speedtest Upload Bandwidth",
                    native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
                    suggested_display_precision=2,
                    target_type=EntityType.MESH,
                    translation_key="upload_bandwidth",
                    value_fn=lambda coordinator, _: (
                        get_speedtest_data(coordinator, "upload_bandwidth")
                        if isinstance(
                            coordinator, LinksysVelopDataUpdateCoordinatorMultiUse
                        )
                        else None
                    ),
                ),
            ),
            "storage_available": (
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    esa_fn=lambda mesh: (
                        {"partitions": (mesh.storage_available.value)}
                        if isinstance(mesh, MeshSnapshot)
                        and mesh.storage_available.value
                        else {}
                    ),
                    key="",
                    name="Available Storage",
                    state_class=SensorStateClass.MEASUREMENT,
                    target_type=EntityType.MESH,
                    translation_key="available_storage",
                    value_fn=lambda _, mesh: (
                        len(mesh.storage_available.value)
                        if isinstance(mesh, MeshSnapshot)
                        else None
                    ),
                ),
            ),
            "type": (
                LinksysVelopSensorEntityDescription(
                    device_class=SensorDeviceClass.ENUM,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="",
                    name="Type",
                    options=[member.value for member in NodeType],
                    target_type=EntityType.NODE,
                    translation_key="node_type",
                    value_fn=lambda _, node: (
                        node.type.value if isinstance(node, NodeEntity) else None
                    ),
                ),
            ),
            "unique_id": (
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="unique_id",
                    name="ID",
                    target_type=EntityType.DEVICE,
                    translation_key="id",
                ),
            ),
            "wan_ip": (
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="wan_ip",
                    name="WAN IP",
                    target_type=EntityType.MESH,
                    translation_key="wan_ip",
                ),
            ),
        }
    )
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialise a sensor."""

    known_nodes: set[str] = set()

    def _create_entities() -> None:
        """Create the mesh and device entities."""

        entities_to_add: tuple[LinksysVelopSensorCoordinatorEntity, ...] = (
            _init_device_entities() + _init_mesh_entities()
        )

        if entities_to_add:
            async_add_entities(entities_to_add)

    def _init_device_entities() -> tuple[LinksysVelopSensorCoordinatorEntity, ...]:
        """Describe the entities that target devices."""
        coordinator = config_entry.runtime_data.coordinator
        device_ids = config_entry.options.get(CONF_UI_DEVICES, [])

        descriptions = [
            entity
            for attr, entities in ENTITIES.items()
            if hasattr(DeviceEntity, attr)
            for entity in entities
            if entity.target_type is EntityType.DEVICE
        ]

        return tuple(
            LinksysVelopSensorMultiUseEntity(
                entity_context=LinksysVelopEntityContext(unique_id=device_id),
                coordinator=coordinator,
                description=description,
            )
            for device_id in device_ids
            for description in descriptions
        )

    def _init_mesh_entities() -> tuple[LinksysVelopSensorCoordinatorEntity, ...]:
        """Describe the entities that target the mesh."""
        coordinator = config_entry.runtime_data.coordinator
        mesh_data = coordinator.data.mesh
        context = LinksysVelopEntityContext(unique_id=config_entry.entry_id)

        descriptions = [
            entity
            for attr, entities in ENTITIES.items()
            if hasattr(mesh_data, attr)
            for entity in entities
            if entity.target_type is EntityType.MESH
        ]

        return tuple(
            LinksysVelopSensorMultiUseEntity(
                entity_context=context,
                coordinator=coordinator,
                description=description,
            )
            for description in descriptions
        )

    def _init_node_entities() -> tuple[LinksysVelopSensorCoordinatorEntity, ...]:
        """Describe the entities that target nodes."""
        coordinator = config_entry.runtime_data.coordinator
        mesh_data = coordinator.data.mesh
        if mesh_data is None:
            return ()

        # filter nodes with valid IDs and identify only new ones
        nodes_by_id = {
            node.unique_id.value: node
            for node in mesh_data.nodes
            if node.unique_id.value is not None
        }

        new_node_ids = set(nodes_by_id.keys()) - known_nodes
        known_nodes.update(new_node_ids)

        # pre-filter base descriptions to avoid repeated loop logic
        base_descriptions = [
            entity
            for attr, entities in ENTITIES.items()
            if hasattr(NodeEntity, attr)
            for entity in entities
            if entity.target_type == EntityType.NODE
        ]

        entities: list[LinksysVelopSensorCoordinatorEntity] = []

        for node_id in new_node_ids:
            node = nodes_by_id[node_id]
            node_descriptions = list(base_descriptions)

            # handle backhaul sensors for secondary nodes
            if node.type == NodeType.SECONDARY and hasattr(node, "backhaul"):
                node_descriptions.extend(
                    (
                        LinksysVelopSensorEntityDescription(
                            device_class=SensorDeviceClass.TIMESTAMP,
                            entity_category=EntityCategory.DIAGNOSTIC,
                            entity_registry_enabled_default=False,
                            key="",
                            name="Backhaul Last Checked",
                            target_type=EntityType.NODE,
                            translation_key="backhaul_last_checked",
                            value_fn=lambda _, n: (
                                get_node_backhaul_info(n, "last_checked")
                                if isinstance(n, NodeEntity)
                                else None
                            ),
                        ),
                        LinksysVelopSensorEntityDescription(
                            device_class=SensorDeviceClass.DATA_RATE,
                            entity_category=EntityCategory.DIAGNOSTIC,
                            key="",
                            name="Backhaul Speed",
                            native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
                            suggested_display_precision=2,
                            target_type=EntityType.NODE,
                            translation_key="backhaul_speed",
                            value_fn=lambda _, n: (
                                get_node_backhaul_info(n, "speed_mbps")
                                if isinstance(n, NodeEntity)
                                else None
                            ),
                        ),
                        LinksysVelopSensorEntityDescription(
                            device_class=SensorDeviceClass.ENUM,
                            entity_category=EntityCategory.DIAGNOSTIC,
                            key="",
                            name="Backhaul Type",
                            options=[v.lower() for v in ConnectionType],
                            target_type=EntityType.NODE,
                            translation_key="backhaul_connection_type",
                            value_fn=lambda _, n: (
                                cast(
                                    ConnectionType,
                                    get_node_backhaul_info(n, "connection"),
                                ).lower()
                                if isinstance(n, NodeEntity)
                                and get_node_backhaul_info(n, "connection")
                                else None
                            ),
                        ),
                        LinksysVelopSensorEntityDescription(
                            entity_category=EntityCategory.DIAGNOSTIC,
                            esa_fn=lambda n: {
                                "parent_ip": (
                                    n.parent_ip if isinstance(n, NodeEntity) else None
                                )
                            },
                            key="parent_name",
                            name="Parent",
                            target_type=EntityType.NODE,
                            translation_key="parent_name",
                        ),
                    )
                )

                # additional sensors for wireless backhaul
                if (
                    node.backhaul.value is not None
                    and node.backhaul.connection == ConnectionType.WIRELESS
                ):
                    node_descriptions.extend(
                        (
                            LinksysVelopSensorEntityDescription(
                                device_class=SensorDeviceClass.ENUM,
                                entity_category=EntityCategory.DIAGNOSTIC,
                                key="",
                                name="Backhaul Friendly Signal Strength",
                                options=[v.lower() for v in SignalStrength],
                                target_type=EntityType.NODE,
                                translation_key="backhaul_friendly_signal_strength",
                                value_fn=lambda _, n: (
                                    cast(
                                        SignalStrength,
                                        get_node_backhaul_info(n, "signal_strength"),
                                    ).lower()
                                    if isinstance(n, NodeEntity)
                                    and get_node_backhaul_info(n, "signal_strength")
                                    else None
                                ),
                            ),
                            LinksysVelopSensorEntityDescription(
                                entity_category=EntityCategory.DIAGNOSTIC,
                                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                                key="",
                                name="Backhaul Signal Strength",
                                native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                                target_type=EntityType.NODE,
                                translation_key="backhaul_signal_strength",
                                value_fn=lambda _, n: (
                                    get_node_backhaul_info(n, "rssi_dbm")
                                    if isinstance(n, NodeEntity)
                                    else None
                                ),
                            ),
                        )
                    )

            context = LinksysVelopEntityContext(unique_id=node_id)
            entities.extend(
                LinksysVelopSensorMultiUseEntity(
                    entity_context=context,
                    coordinator=coordinator,
                    description=desc,
                )
                for desc in node_descriptions
            )

        return tuple(entities)

    def _remove_stale_entities() -> None:
        """Remove entities that are no longer required."""

        coordinator = config_entry.runtime_data.coordinator
        mesh_data = coordinator.data.mesh
        if mesh_data is None:
            return

        entities_to_remove: set[str] = set()

        # Remove stale mesh entities.
        mesh_entities = {
            slugify(str(entity.name))
            for attr, entities in ENTITIES.items()
            if not hasattr(mesh_data, attr)
            for entity in entities
            if entity.target_type == EntityType.MESH
        }

        entities_to_remove.update(
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::{entity}"
            for entity in mesh_entities
        )

        # Remove stale device entities.
        device_entities = {
            slugify(str(entity.name))
            for attr, entities in ENTITIES.items()
            if not hasattr(DeviceEntity, attr)
            for entity in entities
            if entity.target_type == EntityType.DEVICE
        }

        entities_to_remove.update(
            f"{device_id}::{ENTITY_DOMAIN}::{entity}"
            for device_id in config_entry.options.get(CONF_UI_DEVICES, [])
            for entity in device_entities
        )

        # Remove stale node entities.
        node_entities = {
            slugify(str(entity.name))
            for attr, entities in ENTITIES.items()
            if not hasattr(NodeEntity, attr)
            for entity in entities
            if entity.target_type == EntityType.NODE
        }

        entities_to_remove.update(
            f"{node.unique_id.value}::{ENTITY_DOMAIN}::{entity}"
            for node in mesh_data.nodes
            for entity in node_entities
        )

        # Remove node entities when backhaul is unavailable.
        for node in mesh_data.nodes:
            node_id = node.unique_id.value

            if not hasattr(node, "backhaul"):
                entities_to_remove.update(
                    {
                        f"{node_id}::{ENTITY_DOMAIN}::backhaul_friendly_signal_strength",
                        f"{node_id}::{ENTITY_DOMAIN}::backhaul_signal_strength",
                    }
                )

                if node.type != NodeType.SECONDARY:
                    entities_to_remove.update(
                        {
                            f"{node_id}::{ENTITY_DOMAIN}::backhaul_last_checked",
                            f"{node_id}::{ENTITY_DOMAIN}::backhaul_speed",
                            f"{node_id}::{ENTITY_DOMAIN}::backhaul_type",
                            f"{node_id}::{ENTITY_DOMAIN}::parent",
                        }
                    )

        for entity_unique_id in entities_to_remove:
            remove_velop_entity_from_registry(
                hass,
                config_entry.entry_id,
                entity_unique_id,
            )

    def create_node_entities() -> None:
        """Create the node entities.

        This is in a separate function because new nodes can be added to the mesh whilst the integration is running.
        """

        entities_to_add: tuple[LinksysVelopSensorCoordinatorEntity, ...] = (
            _init_node_entities()
        )

        if entities_to_add:
            async_add_entities(entities_to_add)

    _remove_stale_entities()
    _create_entities()
    create_node_entities()

    config_entry.async_on_unload(
        config_entry.runtime_data.coordinator.add_listener_for_timer_type(
            CoordinatorTimers.MESH, create_node_entities
        )
    )


class LinksysVelopSensorEntity(SensorEntity):
    """Base class representing a sensor entity."""

    entity_description: LinksysVelopSensorEntityDescription
    _entity_domain: str = ENTITY_DOMAIN


class LinksysVelopSensorMultiUseEntity(
    LinksysVelopSensorEntity, LinksysVelopMultiUseEntity
):
    """Linksys Velop sensor that uses multi use DataUpdateCoordinator."""

    @property
    @override
    def entity_picture(self) -> str | None:

        ret: str | None = None
        if self.entity_description.pic_fn is not None:
            ret = self.entity_description.pic_fn(self.coordinator, self._get_target())

        return ret

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:

        ret: dict[str, Any] | None = None

        if self.entity_description.esa_fn is not None:
            ret = self.entity_description.esa_fn(self._get_target())

        return ret

    @property
    @override
    def native_value(self) -> StateType | dt.date | dt.datetime | Decimal:

        ret: StateType | dt.date | dt.datetime | Decimal = None
        target: TargetEntityType = self._get_target()
        if self.entity_description.value_fn is not None:
            ret = self.entity_description.value_fn(self.coordinator, target)
        elif self.entity_description.key:
            ret = getattr(target, self.entity_description.key, None)
            if isinstance(ret, MeshAttribute):
                ret = ret.value

        return ret


type LinksysVelopSensorCoordinatorEntity = LinksysVelopSensorMultiUseEntity
