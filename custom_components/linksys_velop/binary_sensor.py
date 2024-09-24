"""Sensor entities for Linksys Velop."""

# region #-- imports --#
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.node import Node

from .coordinator import SpeedtestStatus, UpdateCoordinatorChangeableInterval
from .entities import EntityDetails, EntityType, LinksysVelopEntity, build_entities
from .types import CoordinatorTypes, LinksysVelopConfigEntry

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass
class BinarySensorDetails(EntityDetails):
    description: BinarySensorEntityDescription


def status_extra_attributes(n: Node) -> dict[str, Any]:
    """Return the extra attributes for the Status binary sensor."""

    ret: dict[str, Any] = {}

    primary_adapter: list[dict[str, Any]] = [
        adapter for adapter in n.connected_adapters if adapter.get("primary")
    ]

    if primary_adapter:
        del primary_adapter[0]["primary"]
        ret = primary_adapter[0]

    return ret


ENTITY_DETAILS: list[BinarySensorDetails] = [
    # region #-- device sensors --#
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="Blocked Times",
            translation_key="blocked_times",
        ),
        entity_type=EntityType.DEVICE,
        esa_value_func=lambda d: d.parental_control_schedule.get(
            "blocked_internet_access"
        ),
        state_value_func=lambda d: (
            d.parental_control_schedule is not None
            and d.parental_control_schedule.get("blocked_internet_access") is not None
            and any(d.parental_control_schedule.get("blocked_internet_access").values())
        ),
    ),
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="Guest Network",
            translation_key="guest_network",
        ),
        entity_type=EntityType.DEVICE,
        state_value_func=lambda d: next(iter(d.connected_adapters), {}).get(
            "guest_network"
        ),
    ),
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="Reserved IP",
            translation_key="reserved_ip",
        ),
        entity_type=EntityType.DEVICE,
        state_value_func=lambda d: next(iter(d.connected_adapters), {}).get(
            "reservation"
        ),
    ),
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            entity_category=EntityCategory.DIAGNOSTIC,
            key="status",
            name="Status",
            translation_key="status",
        ),
        entity_type=EntityType.DEVICE,
    ),
    # endregion
    # region #-- mesh sensors --#
    BinarySensorDetails(
        coordinator_type=CoordinatorTypes.CHANNEL_SCAN,
        description=BinarySensorEntityDescription(
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="is_running",
            name="Channel Scanning",
            translation_key="channel_scanning",
        ),
        entity_type=EntityType.MESH,
    ),
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="client_steering_enabled",
            name="Client Steering",
            translation_key="client_steering",
        ),
        entity_type=EntityType.MESH,
    ),
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="dhcp_enabled",
            name="DHCP Server",
            translation_key="dhcp_server",
        ),
        entity_type=EntityType.MESH,
    ),
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="express_forwarding_enabled",
            name="Express Forwarding",
            translation_key="express_forwarding",
        ),
        entity_type=EntityType.MESH,
    ),
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="homekit_paired",
            name="HomeKit Integration Paired",
            translation_key="homekit_paired",
        ),
        entity_type=EntityType.MESH,
    ),
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="mac_filtering_enabled",
            name="MAC Filtering",
            translation_key="mac_filtering",
        ),
        entity_type=EntityType.MESH,
        esa_value_func=lambda m: {
            "mode": m.mac_filtering_mode,
            "addresses": m.mac_filtering_addresses,
        },
    ),
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="node_steering_enabled",
            name="Node Steering",
            translation_key="node_steering",
        ),
        entity_type=EntityType.MESH,
    ),
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="sip_enabled",
            name="SIP",
            translation_key="sip",
        ),
        entity_type=EntityType.MESH,
    ),
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_category=EntityCategory.DIAGNOSTIC,
            key="",
            name="Speedtest Status",
            translation_key="speedtest_status",
        ),
        coordinator_type=CoordinatorTypes.SPEEDTEST,
        entity_type=EntityType.MESH,
        state_value_func=lambda r: r.friendly_status
        not in (SpeedtestStatus.FINISHED, SpeedtestStatus.UNKNOWN),
    ),
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="upnp_allow_change_settings",
            name="UPnP Allow Users to Configure",
            translation_key="upnp_allow_change_settings",
        ),
        entity_type=EntityType.MESH,
    ),
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="upnp_allow_disable_internet",
            name="UPnP Allow Users to Disable Internet",
            translation_key="upnp_allow_disable_internet",
        ),
        entity_type=EntityType.MESH,
    ),
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            key="upnp_enabled",
            name="UPnP",
            translation_key="upnp",
        ),
        entity_type=EntityType.MESH,
    ),
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            entity_category=EntityCategory.DIAGNOSTIC,
            key="wan_status",
            name="WAN Status",
            translation_key="wan_status",
        ),
        entity_type=EntityType.MESH,
        esa_value_func=lambda m: {
            "ip": m.wan_ip,
            "dns": m.wan_dns or None,
            "mac": m.wan_mac,
        },
    ),
    # endregion
    # region #-- node binary sensors --#
    BinarySensorDetails(
        description=BinarySensorEntityDescription(
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            entity_category=EntityCategory.DIAGNOSTIC,
            key="status",
            name="Status",
            translation_key="status",
        ),
        entity_type=EntityType.NODE,
        esa_value_func=status_extra_attributes,
    ),
    # endregion
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize a binary sensor."""

    entities_to_add: list[LinksysVelopBinarySensor] = []

    entities = build_entities(ENTITY_DETAILS, config_entry, ENTITY_DOMAIN)
    entities_to_add = [LinksysVelopBinarySensor(**entity) for entity in entities]

    if len(entities_to_add) > 0:
        async_add_entities(entities_to_add)


class LinksysVelopBinarySensor(LinksysVelopEntity, BinarySensorEntity):
    """Linksys Velop binary sensor."""

    @callback
    def _update_attr_value(self) -> None:
        """"""

        if self._context_data is None:
            self._attr_is_on = None
            return

        if self._entity_details.state_value_func is not None:
            self._attr_is_on = self._entity_details.state_value_func(self._context_data)
        elif self.entity_description.key:
            try:
                self._attr_is_on = getattr(
                    self._context_data, self.entity_description.key
                )
            except AttributeError:
                self._attr_is_on = None
        else:
            self._attr_is_on = None
