"""Sensor entities for Linksys Velop."""

# region #-- imports --#
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
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
from homeassistant.util import dt as dt_util
from pyvelop.mesh import Mesh, MeshCapability
from pyvelop.mesh_entity import DeviceEntity, NodeEntity
from pyvelop.types import NodeType

from .const import CONF_NODE_IMAGES, CONF_UI_DEVICES
from .coordinator import (
    CoordinatorTypes,
    LinksysVelopConfigEntry,
    LinksysVelopDataUpdateCoordinatorMultiUse,
    LinksysVelopDataUpdateCoordinatorSpeedtest,
    SpeedtestResults,
)
from .entities import (
    EntityType,
    LinksysVelopEntityContext,
    LinksysVelopEntityDescription,
    LinksysVelopMultiUseEntity,
    LinksysVelopSpeedtestEntity,
)
from .helpers import remove_velop_entity_from_registry

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LinksysVelopSensorEntityDescription(
    LinksysVelopEntityDescription, SensorEntityDescription
):
    """Describes Velop sensor entity."""

    esa_fn: Callable[[Mesh], dict[str, Any]] | None = None
    has_entity_pic: bool = False
    value_fn: Callable[..., StateType | date | datetime | Decimal] | None = None


def get_devices(mesh: Mesh, state: bool = True) -> list[dict[str, Any]]:
    """Get the matching devices from the Mesh."""
    ret: list[dict[str, Any]] = []
    device: DeviceEntity
    for device in mesh.devices:
        if device.status is state:
            ret.append({"name": device.name, "id": device.unique_id})
            for adapter in device.adapter_info:
                if adapter.get("ip"):
                    ret[-1] = dict(
                        **ret[-1],
                        ip=adapter.get("ip"),
                        connection=adapter.get("type"),
                        guest_network=adapter.get("guest_network"),
                    )

    return ret


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

        if len(entities_to_add) > 0:
            async_add_entities(entities_to_add)

    def _init_device_entities() -> tuple[LinksysVelopSensorCoordinatorEntity, ...]:
        """Describe the entities that target devices."""
        ret: tuple[LinksysVelopSensorCoordinatorEntity, ...] = ()
        ret_temp: list[LinksysVelopSensorCoordinatorEntity] = []

        for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
            context: LinksysVelopEntityContext = LinksysVelopEntityContext(
                unique_id=ui_device
            )
            mesh_entities: list[LinksysVelopSensorEntityDescription] = []

            mesh_entities.extend(
                [
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="description",
                        name="Description",
                        target_type=EntityType.DEVICE,
                        translation_key="description",
                    ),
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="",
                        name="Friendly Signal Strength",
                        target_type=EntityType.DEVICE,
                        translation_key="friendly_signal_strength",
                        value_fn=lambda d: (
                            next(iter(cast(DeviceEntity, d).adapter_info), {}).get(
                                "signal_strength", ""
                            )
                            if d is not None
                            else None
                        ),
                    ),
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="",
                        name="IP",
                        target_type=EntityType.DEVICE,
                        translation_key="ip",
                        value_fn=lambda d: (
                            next(iter(cast(DeviceEntity, d).adapter_info), {}).get("ip")
                            if d is not None
                            else None
                        ),
                    ),
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="",
                        name="IPv6",
                        target_type=EntityType.DEVICE,
                        translation_key="ipv6",
                        value_fn=lambda d: (
                            next(iter(cast(DeviceEntity, d).adapter_info), {}).get(
                                "ipv6"
                            )
                            if d is not None
                            else None
                        ),
                    ),
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="",
                        name="MAC",
                        target_type=EntityType.DEVICE,
                        translation_key="mac",
                        value_fn=lambda d: (
                            next(iter(cast(DeviceEntity, d).adapter_info), {}).get(
                                "mac"
                            )
                            if d is not None
                            else None
                        ),
                    ),
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="manufacturer",
                        name="Manufacturer",
                        target_type=EntityType.DEVICE,
                        translation_key="manufacturer",
                    ),
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="model",
                        name="Model",
                        target_type=EntityType.DEVICE,
                        translation_key="model",
                    ),
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="name",
                        name="Name",
                        target_type=EntityType.DEVICE,
                        translation_key="name",
                    ),
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="operating_system",
                        name="Operating System",
                        target_type=EntityType.DEVICE,
                        translation_key="operating_system",
                    ),
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="parent_name",
                        name="Parent",
                        translation_key="parent_name",
                        target_type=EntityType.DEVICE,
                    ),
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="serial",
                        name="Serial",
                        target_type=EntityType.DEVICE,
                        translation_key="serial",
                    ),
                    LinksysVelopSensorEntityDescription(
                        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="",
                        name="Signal Strength",
                        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                        target_type=EntityType.DEVICE,
                        translation_key="signal_strength",
                        value_fn=lambda d: (
                            next(iter(cast(DeviceEntity, d).adapter_info), {}).get(
                                "rssi"
                            )
                            if d is not None
                            else None
                        ),
                    ),
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        has_entity_pic=True,
                        key="ui_type",
                        name="UI Type",
                        target_type=EntityType.DEVICE,
                        translation_key="ui_type",
                    ),
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="unique_id",
                        name="ID",
                        target_type=EntityType.DEVICE,
                        translation_key="id",
                    ),
                ]
            )

            if (
                MeshCapability.GET_PARENTAL_CONTROL_INFO
                in config_entry.runtime_data.mesh.capabilities
            ):
                mesh_entities.extend(
                    [
                        LinksysVelopSensorEntityDescription(
                            entity_category=EntityCategory.DIAGNOSTIC,
                            esa_fn=lambda d: (
                                {
                                    "sites": cast(
                                        DeviceEntity, d
                                    ).parental_control_schedule.get("blocked_sites", [])
                                }
                                if len(
                                    cast(DeviceEntity, d).parental_control_schedule.get(
                                        "blocked_sites", []
                                    )
                                )
                                > 0
                                else {}
                            ),
                            key="",
                            name="Blocked Sites",
                            state_class=SensorStateClass.MEASUREMENT,
                            target_type=EntityType.DEVICE,
                            translation_key="blocked_sites",
                            value_fn=lambda d: (
                                len(
                                    cast(DeviceEntity, d).parental_control_schedule.get(
                                        "blocked_sites", []
                                    )
                                )
                                if d is not None
                                else None
                            ),
                        )
                    ]
                )

            ret_temp.extend(
                [
                    LinksysVelopSensorMultiUseEntity(
                        entity_context=context,
                        coordinator=cast(
                            LinksysVelopDataUpdateCoordinatorMultiUse,
                            config_entry.runtime_data.coordinators.get(
                                CoordinatorTypes.MESH
                            ),
                        ),
                        description=desc,
                    )
                    for desc in mesh_entities
                ]
            )

        ret = tuple(ret_temp)
        return ret

    def _init_mesh_entities() -> tuple[LinksysVelopSensorCoordinatorEntity, ...]:
        """Describe the entities that target the mesh."""
        ret: tuple[LinksysVelopSensorCoordinatorEntity, ...] = ()
        context: LinksysVelopEntityContext = LinksysVelopEntityContext(
            unique_id=config_entry.entry_id
        )
        mesh_entities: list[LinksysVelopSensorEntityDescription] = []
        speedtest_entities: list[LinksysVelopSensorEntityDescription] = []

        if MeshCapability.GET_DEVICES in config_entry.runtime_data.mesh.capabilities:
            mesh_entities.extend(
                [
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="",
                        name="Offline Devices",
                        state_class=SensorStateClass.MEASUREMENT,
                        target_type=EntityType.MESH,
                        translation_key="offline_devices",
                        value_fn=lambda m: (len(get_devices(cast(Mesh, m), False))),
                    ),
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        esa_fn=lambda m: (
                            {"devices": get_devices(m)} if get_devices(m) else {}
                        ),
                        key="",
                        name="Online Devices",
                        state_class=SensorStateClass.MEASUREMENT,
                        target_type=EntityType.MESH,
                        translation_key="online_devices",
                        value_fn=lambda m: len(get_devices(cast(Mesh, m))),
                    ),
                ]
            )

        if (
            MeshCapability.GET_GUEST_NETWORK_INFO
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    esa_fn=lambda m: (
                        {
                            "devices": (
                                [d for d in get_devices(m) if d.get("guest_network")]
                            )
                        }
                        if get_devices(m)
                        else {}
                    ),
                    key="",
                    name="Guest Devices",
                    state_class=SensorStateClass.MEASUREMENT,
                    target_type=EntityType.MESH,
                    translation_key="guest_devices",
                    value_fn=lambda m: (
                        len(
                            [
                                d
                                for d in get_devices(cast(Mesh, m))
                                if d.get("guest_network")
                            ]
                        )
                    ),
                ),
            )

        if (
            MeshCapability.GET_LAN_SETTINGS
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    esa_fn=lambda m: (
                        {
                            "reservations": m.dhcp_reservations,
                        }
                        if m.dhcp_reservations
                        else {}
                    ),
                    key="",
                    name="DHCP Reservations",
                    state_class=SensorStateClass.MEASUREMENT,
                    target_type=EntityType.MESH,
                    translation_key="dhcp_reservations",
                    value_fn=lambda m: (len(cast(Mesh, m).dhcp_reservations)),
                ),
            )

        if (
            MeshCapability.GET_SPEEDTEST_RESULTS
            in config_entry.runtime_data.mesh.capabilities
        ):
            speedtest_entities.extend(
                [
                    LinksysVelopSensorEntityDescription(
                        device_class=SensorDeviceClass.DATA_RATE,
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        key="download_bandwidth",
                        name="Speedtest Download Bandwidth",
                        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
                        suggested_display_precision=2,
                        target_type=EntityType.MESH,
                        translation_key="download_bandwidth",
                    ),
                    LinksysVelopSensorEntityDescription(
                        device_class=SensorDeviceClass.TIMESTAMP,
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        key="",
                        name="Speedtest Last Run",
                        target_type=EntityType.MESH,
                        translation_key="speedtest_last_run",
                        value_fn=lambda r: (
                            dt_util.parse_datetime(cast(SpeedtestResults, r).timestamp)
                        ),
                    ),
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        key="latency",
                        name="Speedtest Latency",
                        native_unit_of_measurement="ms",
                        target_type=EntityType.MESH,
                        translation_key="speedtest_latency",
                    ),
                    LinksysVelopSensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        key="exit_code",
                        name="Speedtest Result",
                        target_type=EntityType.MESH,
                        translation_key="speedtest_result",
                    ),
                    LinksysVelopSensorEntityDescription(
                        device_class=SensorDeviceClass.DATA_RATE,
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        key="upload_bandwidth",
                        name="Speedtest Upload Bandwidth",
                        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
                        suggested_display_precision=2,
                        target_type=EntityType.MESH,
                        translation_key="upload_bandwidth",
                    ),
                ]
            )

        if (
            MeshCapability.GET_SPEEDTEST_STATUS
            in config_entry.runtime_data.mesh.capabilities
        ):
            speedtest_entities.append(
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="friendly_status",
                    name="Speedtest Progress",
                    target_type=EntityType.MESH,
                    translation_key="speedtest_progress",
                ),
            )

        if (
            MeshCapability.GET_STORAGE_PARTITIONS
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    esa_fn=lambda m: (
                        {"partitions": (m.storage_available)}
                        if len(m.storage_available) > 0
                        else {}
                    ),
                    key="",
                    name="Available Storage",
                    state_class=SensorStateClass.MEASUREMENT,
                    target_type=EntityType.MESH,
                    translation_key="available_storage",
                    value_fn=lambda m: (len(cast(Mesh, m).storage_available)),
                ),
            )

        if MeshCapability.GET_WAN_INFO in config_entry.runtime_data.mesh.capabilities:
            mesh_entities.append(
                LinksysVelopSensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="wan_ip",
                    name="WAN IP",
                    target_type=EntityType.MESH,
                    translation_key="wan_ip",
                ),
            )

        ret = *[
            LinksysVelopSensorMultiUseEntity(
                entity_context=context,
                coordinator=cast(
                    LinksysVelopDataUpdateCoordinatorMultiUse,
                    config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH),
                ),
                description=desc,
            )
            for desc in mesh_entities
        ], *[
            LinksysVelopSensorSpeedtestEntity(
                entity_context=context,
                coordinator=cast(
                    LinksysVelopDataUpdateCoordinatorSpeedtest,
                    config_entry.runtime_data.coordinators.get(
                        CoordinatorTypes.SPEEDTEST
                    ),
                ),
                description=desc,
            )
            for desc in speedtest_entities
        ]

        return ret

    def _init_node_entities() -> tuple[LinksysVelopSensorCoordinatorEntity, ...]:
        """Describe the entities that target nodes."""

        ret: tuple[LinksysVelopSensorCoordinatorEntity, ...] = ()
        ret_temp: list[LinksysVelopSensorCoordinatorEntity] = []
        current_nodes: set[str] = {
            n.unique_id
            for n in config_entry.runtime_data.mesh.nodes
            if n.unique_id is not None
        }
        new_nodes: set[str] = current_nodes - known_nodes

        if new_nodes:
            known_nodes.update(new_nodes)
            for node in new_nodes:
                mesh_entities: list[LinksysVelopSensorEntityDescription] = []
                context: LinksysVelopEntityContext = LinksysVelopEntityContext(
                    unique_id=node
                )
                node_details: NodeEntity | None = next(
                    (
                        n
                        for n in config_entry.runtime_data.mesh.nodes
                        if n.unique_id == context.unique_id
                    ),
                    None,
                )

                if node_details is not None:
                    is_wifi_node: bool = (
                        node_details.backhaul.get("connection", "").lower()
                        == "wireless"
                    )

                    if (
                        MeshCapability.GET_BACKHAUL
                        in config_entry.runtime_data.mesh.capabilities
                        and node_details.type == NodeType.SECONDARY
                    ):
                        mesh_entities.extend(
                            [
                                LinksysVelopSensorEntityDescription(
                                    device_class=SensorDeviceClass.TIMESTAMP,
                                    entity_category=EntityCategory.DIAGNOSTIC,
                                    entity_registry_enabled_default=False,
                                    key="",
                                    name="Backhaul Last Checked",
                                    target_type=EntityType.NODE,
                                    translation_key="backhaul_last_checked",
                                    value_fn=lambda n: (
                                        dt_util.parse_datetime(
                                            cast(NodeEntity, n).backhaul.get(
                                                "last_checked", ""
                                            )
                                        )
                                        if cast(NodeEntity, n).backhaul.get(
                                            "last_checked"
                                        )
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
                                    value_fn=lambda n: (
                                        cast(NodeEntity, n).backhaul.get("speed_mbps")
                                    ),
                                ),
                                LinksysVelopSensorEntityDescription(
                                    device_class=SensorDeviceClass.ENUM,
                                    entity_category=EntityCategory.DIAGNOSTIC,
                                    key="",
                                    name="Backhaul Type",
                                    options=["unknown", "wired", "wireless"],
                                    target_type=EntityType.NODE,
                                    translation_key="backhaul_connection_type",
                                    value_fn=lambda n: (
                                        cast(NodeEntity, n)
                                        .backhaul.get("connection", "unknown")
                                        .lower()
                                    ),
                                ),
                                LinksysVelopSensorEntityDescription(
                                    entity_category=EntityCategory.DIAGNOSTIC,
                                    esa_fn=lambda n: (
                                        {"parent_ip": cast(NodeEntity, n).parent_ip}
                                    ),
                                    key="parent_name",
                                    name="Parent",
                                    target_type=EntityType.NODE,
                                    translation_key="parent_name",
                                ),
                            ]
                        )

                        if is_wifi_node:
                            mesh_entities.extend(
                                [
                                    LinksysVelopSensorEntityDescription(
                                        entity_category=EntityCategory.DIAGNOSTIC,
                                        key="",
                                        name="Backhaul Friendly Signal Strength",
                                        target_type=EntityType.NODE,
                                        translation_key="backhaul_friendly_signal_strength",
                                        value_fn=lambda n: (
                                            cast(NodeEntity, n)
                                            .backhaul.get("signal_strength", "")
                                            .lower()
                                            if cast(NodeEntity, n).backhaul.get(
                                                "signal_strength"
                                            )
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
                                        value_fn=lambda n: (
                                            cast(NodeEntity, n).backhaul.get("rssi_dbm")
                                        ),
                                    ),
                                ]
                            )

                    if (
                        MeshCapability.GET_DEVICES
                        in config_entry.runtime_data.mesh.capabilities
                    ):
                        mesh_entities.extend(
                            [
                                LinksysVelopSensorEntityDescription(
                                    entity_category=EntityCategory.DIAGNOSTIC,
                                    esa_fn=lambda n: (
                                        {
                                            "devices": cast(
                                                NodeEntity, n
                                            ).connected_devices
                                        }
                                        if cast(NodeEntity, n).connected_devices
                                        else {}
                                    ),
                                    key="",
                                    name="Connected Devices",
                                    state_class=SensorStateClass.MEASUREMENT,
                                    target_type=EntityType.NODE,
                                    translation_key="connected_devices",
                                    value_fn=lambda n: (
                                        len(cast(NodeEntity, n).connected_devices)
                                    ),
                                ),
                                LinksysVelopSensorEntityDescription(
                                    entity_category=EntityCategory.DIAGNOSTIC,
                                    has_entity_pic=True,
                                    key="model",
                                    name="Model",
                                    target_type=EntityType.NODE,
                                    translation_key="model",
                                ),
                                LinksysVelopSensorEntityDescription(
                                    entity_category=EntityCategory.DIAGNOSTIC,
                                    key="serial",
                                    name="Serial",
                                    target_type=EntityType.NODE,
                                    translation_key="serial",
                                ),
                                LinksysVelopSensorEntityDescription(
                                    device_class=SensorDeviceClass.ENUM,
                                    entity_category=EntityCategory.DIAGNOSTIC,
                                    key="",
                                    name="Type",
                                    options=[member.value for member in NodeType],
                                    target_type=EntityType.NODE,
                                    translation_key="node_type",
                                    value_fn=lambda n: cast(NodeEntity, n).type.value,
                                ),
                            ]
                        )

                    if (
                        MeshCapability.GET_UPDATE_FIRMWARE_STATE
                        in config_entry.runtime_data.mesh.capabilities
                    ):
                        mesh_entities.append(
                            LinksysVelopSensorEntityDescription(
                                device_class=SensorDeviceClass.TIMESTAMP,
                                entity_category=EntityCategory.DIAGNOSTIC,
                                entity_registry_enabled_default=False,
                                key="",
                                name="Last Update Check",
                                target_type=EntityType.NODE,
                                translation_key="last_update_check",
                                value_fn=lambda n: (
                                    dt_util.parse_datetime(
                                        str(cast(NodeEntity, n).last_update_check)
                                    )
                                    if cast(NodeEntity, n).last_update_check is not None
                                    else None
                                ),
                            ),
                        )

                ret_temp.extend(
                    [
                        LinksysVelopSensorMultiUseEntity(
                            entity_context=context,
                            coordinator=cast(
                                LinksysVelopDataUpdateCoordinatorMultiUse,
                                config_entry.runtime_data.coordinators.get(
                                    CoordinatorTypes.MESH
                                ),
                            ),
                            description=desc,
                        )
                        for desc in mesh_entities
                    ]
                )

        ret = tuple(ret_temp)
        return ret

    def _remove_stale_entities() -> None:
        """Remove entities is they are no longer required."""

        entities_to_remove: set[str] = set()

        # region #-- remove unnecessary node entities  --#
        for node in config_entry.runtime_data.mesh.nodes:
            is_wifi_node: bool = (
                node.backhaul.get("connection", "").lower() == "wireless"
            )

            if (
                MeshCapability.GET_UPDATE_FIRMWARE_STATE
                not in config_entry.runtime_data.mesh.capabilities
            ):
                entities_to_remove.add(
                    f"{node.unique_id}::{ENTITY_DOMAIN}::last_update_check"
                )

            if (
                MeshCapability.GET_BACKHAUL
                not in config_entry.runtime_data.mesh.capabilities
            ) or not is_wifi_node:
                entities_to_remove.update(
                    {
                        f"{node.unique_id}::{ENTITY_DOMAIN}::backhaul_friendly_signal_strength",
                        f"{node.unique_id}::{ENTITY_DOMAIN}::backhaul_signal_strength",
                    }
                )

            if (
                MeshCapability.GET_BACKHAUL
                not in config_entry.runtime_data.mesh.capabilities
            ) or node.type != NodeType.SECONDARY:
                entities_to_remove.update(
                    {
                        f"{node.unique_id}::{ENTITY_DOMAIN}::backhaul_last_checked",
                        f"{node.unique_id}::{ENTITY_DOMAIN}::backhaul_speed",
                        f"{node.unique_id}::{ENTITY_DOMAIN}::backhaul_type",
                        f"{node.unique_id}::{ENTITY_DOMAIN}::parent",
                    }
                )

        # endregion

        # region #-- remove unnecessary device entities --#
        for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
            if (
                MeshCapability.GET_PARENTAL_CONTROL_INFO
                not in config_entry.runtime_data.mesh.capabilities
            ):
                entities_to_remove.add(f"{ui_device}::{ENTITY_DOMAIN}::blocked_sites")

        # endregion

        # region #-- remove unnecessary mesh entities --#
        if (
            MeshCapability.GET_DEVICES
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.update(
                {
                    f"{config_entry.entry_id}::{ENTITY_DOMAIN}::offline_devices",
                    f"{config_entry.entry_id}::{ENTITY_DOMAIN}::online_devices",
                }
            )

        if (
            MeshCapability.GET_GUEST_NETWORK_INFO
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::guest_devices"
            )

        if (
            MeshCapability.GET_LAN_SETTINGS
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::dhcp_reservations"
            )

        if (
            MeshCapability.GET_SPEEDTEST_RESULTS
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.update(
                {
                    f"{config_entry.entry_id}::{ENTITY_DOMAIN}::speedtest_download_bandwidth",
                    f"{config_entry.entry_id}::{ENTITY_DOMAIN}::speedtest_last_run",
                    f"{config_entry.entry_id}::{ENTITY_DOMAIN}::speedtest_latency",
                    f"{config_entry.entry_id}::{ENTITY_DOMAIN}::speedtest_result",
                    f"{config_entry.entry_id}::{ENTITY_DOMAIN}::speedtest_upload_bandwidth",
                }
            )

        if (
            MeshCapability.GET_SPEEDTEST_STATUS
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::speedtest_progress"
            )

        if (
            MeshCapability.GET_STORAGE_PARTITIONS
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::available_storage"
            )

        if (
            MeshCapability.GET_WAN_INFO
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(f"{config_entry.entry_id}::{ENTITY_DOMAIN}::wan_ip")
        # endregion

        if len(entities_to_remove) > 0:
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

        if len(entities_to_add) > 0:
            async_add_entities(entities_to_add)

    _remove_stale_entities()
    _create_entities()
    create_node_entities()


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

        # region #-- construct the entity picture path --#
        if (
            self.entity_description.has_entity_pic
            and self.entity_description.key != ""
            and (prefix := self.coordinator.config_entry.options.get(CONF_NODE_IMAGES))
            not in (None, "")
        ):

            ret = f"{prefix.rstrip('/').strip()}/{self.entity_description.key}.png"
        # endregion

        return ret

    @property
    @override
    def native_value(self) -> StateType | date | datetime | Decimal:

        ret: StateType | date | datetime | Decimal = None
        if self.entity_description.value_fn is not None:
            ret = self.entity_description.value_fn(self._get_target())
        elif self.entity_description.key:
            ret = getattr(
                self._get_target(),
                self.entity_description.key,
                None,
            )

        return ret


class LinksysVelopSensorSpeedtestEntity(
    LinksysVelopSensorEntity, LinksysVelopSpeedtestEntity
):
    """Linksys Velop sensor that uses Speedtest DataUpdateCoordinator."""

    @property
    @override
    def native_value(self) -> StateType | date | datetime | Decimal:

        ret: StateType | date | datetime | Decimal = None
        if self.entity_description.value_fn is not None:
            ret = self.entity_description.value_fn(self.coordinator.data)
        elif self.entity_description.key:
            ret = getattr(self.coordinator.data, self.entity_description.key, None)

        return ret


type LinksysVelopSensorCoordinatorEntity = LinksysVelopSensorMultiUseEntity | LinksysVelopSensorSpeedtestEntity
