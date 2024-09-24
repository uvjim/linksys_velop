"""Sensor entities for Linksys Velop."""

# region #-- imports --#
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, UnitOfDataRate
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from pyvelop.device import Device
from pyvelop.mesh import Mesh
from pyvelop.node import NodeType

from .const import CONF_NODE_IMAGES
from .entities import EntityDetails, EntityType, LinksysVelopEntity, build_entities
from .types import CoordinatorTypes, LinksysVelopConfigEntry

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass
class SensorDetails(EntityDetails):
    description: SensorEntityDescription


def get_devices(mesh: Mesh, state: bool = True) -> list[dict[str, Any]]:
    """Get the matching devices from the Mesh."""
    ret: list[dict[str, Any]] = []
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


ENTITY_DETAILS: list[SensorDetails] = [
    # region #-- device sensors --#
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="Blocked Sites",
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="blocked_sites",
        ),
        entity_type=EntityType.DEVICE,
        esa_value_func=lambda d: {
            "sites": d.parental_control_schedule.get("blocked_sites", [])
        },
        state_value_func=lambda d: len(
            d.parental_control_schedule.get("blocked_sites", [])
        ),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="description",
            name="Description",
            translation_key="description",
        ),
        entity_type=EntityType.DEVICE,
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="Friendly Signal Strength",
            translation_key="friendly_signal_strength",
        ),
        entity_type=EntityType.DEVICE,
        state_value_func=lambda d: next(iter(d.connected_adapters), {})
        .get("signal_strength", "")
        .lower()
        or None,
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="IP",
            translation_key="ip",
        ),
        entity_type=EntityType.DEVICE,
        state_value_func=lambda d: next(iter(d.connected_adapters), {}).get("ip"),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="IPv6",
            translation_key="ipv6",
        ),
        entity_type=EntityType.DEVICE,
        state_value_func=lambda d: next(iter(d.connected_adapters), {}).get("ipv6"),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="MAC",
            translation_key="mac",
        ),
        entity_type=EntityType.DEVICE,
        state_value_func=lambda d: next(iter(d.connected_adapters), {}).get("mac"),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="manufacturer",
            name="Manufacturer",
            translation_key="manufacturer",
        ),
        entity_type=EntityType.DEVICE,
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="model",
            name="Model",
            translation_key="model",
        ),
        entity_type=EntityType.DEVICE,
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="name",
            name="Name",
            translation_key="name",
        ),
        entity_type=EntityType.DEVICE,
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="operating_system",
            name="Operating System",
            translation_key="operating_system",
        ),
        entity_type=EntityType.DEVICE,
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="parent_name",
            name="Parent",
            translation_key="parent_name",
        ),
        entity_type=EntityType.DEVICE,
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="serial",
            name="Serial",
            translation_key="serial",
        ),
        entity_type=EntityType.DEVICE,
    ),
    SensorDetails(
        description=SensorEntityDescription(
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="Signal Strength",
            native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            translation_key="signal_strength",
        ),
        entity_type=EntityType.DEVICE,
        state_value_func=lambda d: next(iter(d.connected_adapters), {}).get("rssi"),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="ui_type",
            name="UI Type",
            translation_key="ui_type",
        ),
        entity_type=EntityType.DEVICE,
        pic_value_func=lambda d, c: (
            f"{c.options.get(CONF_NODE_IMAGES, '').rstrip('/ ').strip()}/"
            f"{d.ui_type.lower()}.png"
            if d.ui_type is not None
            else None
        ),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="unique_id",
            name="ID",
            translation_key="id",
        ),
        entity_type=EntityType.DEVICE,
    ),
    # endregion
    # region #-- mesh sensors --#
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="",
            name="Available Storage",
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="available_storage",
        ),
        entity_type=EntityType.MESH,
        esa_value_func=lambda m: {"partitions": m.storage_available or None},
        state_value_func=lambda m: len(m.storage_available),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="",
            name="DHCP Reservations",
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="dhcp_reservations",
        ),
        entity_type=EntityType.MESH,
        esa_value_func=lambda m: {
            "reservations": m.dhcp_reservations,
        },
        state_value_func=lambda m: len(m.dhcp_reservations),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="Guest Devices",
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="guest_devices",
        ),
        entity_type=EntityType.MESH,
        esa_value_func=lambda m: {
            "devices": [d for d in get_devices(m) if d.get("guest_network")]
        },
        state_value_func=lambda m: len(
            [d for d in get_devices(m) if d.get("guest_network")]
        ),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="Offline Devices",
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="offline_devices",
        ),
        entity_type=EntityType.MESH,
        esa_value_func=lambda m: {"devices": get_devices(m, False)},
        state_value_func=lambda m: len(get_devices(m, False)),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="Online Devices",
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="online_devices",
        ),
        entity_type=EntityType.MESH,
        esa_value_func=lambda m: {"devices": get_devices(m)},
        state_value_func=lambda m: len(get_devices(m)),
    ),
    SensorDetails(
        coordinator_type=CoordinatorTypes.SPEEDTEST,
        description=SensorEntityDescription(
            device_class=SensorDeviceClass.DATA_RATE,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="download_bandwidth",
            name="Speedtest Download Bandwidth",
            native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
            translation_key="download_bandwidth",
        ),
        entity_type=EntityType.MESH,
    ),
    SensorDetails(
        coordinator_type=CoordinatorTypes.SPEEDTEST,
        description=SensorEntityDescription(
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="",
            name="Speedtest Last Run",
            translation_key="speedtest_last_run",
        ),
        entity_type=EntityType.MESH,
        state_value_func=lambda r: dt_util.parse_datetime(r.timestamp),
    ),
    SensorDetails(
        coordinator_type=CoordinatorTypes.SPEEDTEST,
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="latency",
            name="Speedtest Latency",
            native_unit_of_measurement="ms",
            translation_key="speedtest_latency",
        ),
        entity_type=EntityType.MESH,
    ),
    SensorDetails(
        coordinator_type=CoordinatorTypes.SPEEDTEST,
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="friendly_status",
            name="Speedtest Progress",
            translation_key="speedtest_progress",
        ),
        entity_type=EntityType.MESH,
    ),
    SensorDetails(
        coordinator_type=CoordinatorTypes.SPEEDTEST,
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="exit_code",
            name="Speedtest Result",
            translation_key="speedtest_result",
        ),
        entity_type=EntityType.MESH,
    ),
    SensorDetails(
        coordinator_type=CoordinatorTypes.SPEEDTEST,
        description=SensorEntityDescription(
            device_class=SensorDeviceClass.DATA_RATE,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="upload_bandwidth",
            name="Speedtest Upload Bandwidth",
            native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
            translation_key="upload_bandwidth",
        ),
        entity_type=EntityType.MESH,
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="wan_ip",
            name="WAN IP",
            translation_key="wan_ip",
        ),
        entity_type=EntityType.MESH,
    ),
    # endregion
    # region #-- node sensors --#
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="Backhaul Friendly Signal Strength",
            translation_key="backhaul_friendly_signal_strength",
        ),
        entity_type=EntityType.WIFI_NODE,
        state_value_func=lambda n: (
            n.backhaul.get("signal_strength", "").lower()
            if n.backhaul.get("signal_strength")
            else None
        ),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="",
            name="Backhaul Last Checked",
            translation_key="backhaul_last_checked",
        ),
        entity_type=EntityType.SECONDARY_NODE,
        state_value_func=lambda n: (
            dt_util.parse_datetime(n.backhaul.get("last_checked"))
            if n.backhaul.get("last_checked")
            else None
        ),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            key="",
            name="Backhaul Signal Strength",
            native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            translation_key="backhaul_signal_strength",
        ),
        entity_type=EntityType.WIFI_NODE,
        state_value_func=lambda n: n.backhaul.get("rssi_dbm"),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            device_class=SensorDeviceClass.DATA_RATE,
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="Backhaul Speed",
            native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
            translation_key="backhaul_speed",
        ),
        entity_type=EntityType.SECONDARY_NODE,
        state_value_func=lambda n: n.backhaul.get("speed_mbps"),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            device_class=SensorDeviceClass.ENUM,
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="Backhaul Type",
            options=["unknown", "wired", "wireless"],
            translation_key="backhaul_connection_type",
        ),
        entity_type=EntityType.SECONDARY_NODE,
        icon_value_func=lambda n: (
            "mdi:lan-connect"
            if n.backhaul.get("connection", "").lower() == "wired"
            else "mdi:wifi"
        ),
        state_value_func=lambda n: n.backhaul.get("connection", "unknown").lower(),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="Connected Devices",
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="connected_devices",
        ),
        entity_type=EntityType.NODE,
        esa_value_func=lambda n: (
            {"devices": n.connected_devices} if n.connected_devices else {}
        ),
        state_value_func=lambda n: len(n.connected_devices),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="",
            name="Last Update Check",
            translation_key="last_update_check",
        ),
        entity_type=EntityType.NODE,
        state_value_func=lambda n: (
            dt_util.parse_datetime(n.last_update_check) if n.last_update_check else None
        ),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="model",
            name="Model",
            translation_key="model",
        ),
        entity_type=EntityType.NODE,
        pic_value_func=lambda n, c: (
            f"{c.options.get(CONF_NODE_IMAGES, '').rstrip('/ ').strip()}/{n.model}.png"
            if c.options.get(CONF_NODE_IMAGES, "")
            else None
        ),
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="parent_name",
            name="Parent",
            translation_key="parent_name",
        ),
        entity_type=EntityType.SECONDARY_NODE,
        esa_value_func=lambda n: {"parent_ip": n.parent_ip},
    ),
    SensorDetails(
        description=SensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="serial",
            name="Serial",
            translation_key="serial",
        ),
        entity_type=EntityType.NODE,
    ),
    SensorDetails(
        description=SensorEntityDescription(
            device_class=SensorDeviceClass.ENUM,
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="Type",
            options=[member.value for member in NodeType],
            translation_key="node_type",
        ),
        entity_type=EntityType.NODE,
        state_value_func=lambda n: n.type.value,
    ),
    # endregion
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize a sensor."""

    entities_to_add: list[LinksysVelopSensor] = []

    entities = build_entities(ENTITY_DETAILS, config_entry, ENTITY_DOMAIN)
    entities_to_add = [LinksysVelopSensor(**entity) for entity in entities]

    if len(entities_to_add) > 0:
        async_add_entities(entities_to_add)


class LinksysVelopSensor(LinksysVelopEntity, SensorEntity):
    """Linksys Velop sensor."""

    @callback
    def _update_attr_value(self) -> None:
        """"""

        if self._context_data is None:
            self._attr_native_value = None
            return

        if self._entity_details.state_value_func is not None:
            self._attr_native_value = self._entity_details.state_value_func(
                self._context_data
            )
        elif self.entity_description.key:
            try:
                self._attr_native_value = getattr(
                    self._context_data, self.entity_description.key
                )
            except AttributeError:
                self._attr_native_value = None
        else:
            self._attr_native_value = None
