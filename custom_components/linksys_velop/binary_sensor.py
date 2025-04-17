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
from pyvelop.mesh import Mesh, MeshCapability
from pyvelop.mesh_entity import NodeEntity

from .const import CONF_UI_DEVICES
from .coordinator import SpeedtestStatus
from .entities import EntityDetails, EntityType, LinksysVelopEntity, build_entities
from .helpers import remove_velop_entity_from_registry
from .types import CoordinatorTypes, LinksysVelopConfigEntry

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass
class BinarySensorDetails(EntityDetails):
    """Representation of the binary sensor."""

    description: BinarySensorEntityDescription


def status_extra_attributes(n: NodeEntity) -> dict[str, Any]:
    """Return the extra attributes for the Status binary sensor."""

    ret: dict[str, Any] = {}

    if (
        primary_adapter := next(
            (adapter for adapter in n.adapter_info if adapter.get("primary")), None
        )
    ) is not None:
        del primary_adapter["primary"]
        ret = primary_adapter

    return ret


ENTITY_DETAILS: list[BinarySensorDetails] = [
    # region #-- device sensors --#
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
    entities_to_remove: list[str] = [
        f"{config_entry.entry_id}::{ENTITY_DOMAIN}::upnp",  # 2024.11.1b4 remove as we now have a switch
    ]
    entities = build_entities(ENTITY_DETAILS, config_entry, ENTITY_DOMAIN)

    # region #-- add conditional binary sensors --#
    mesh: Mesh = config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH).data
    if MeshCapability.GET_ALG_SETTINGS in mesh.capabilities:
        entities.extend(
            build_entities(
                [
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
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        entities_to_remove.append(f"{config_entry.entry_id}::{ENTITY_DOMAIN}::sip")

    if MeshCapability.GET_CHANNEL_SCAN_STATUS in mesh.capabilities:
        entities.extend(
            build_entities(
                [
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
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        entities_to_remove.append(
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::channel_scanning"
        )

    if MeshCapability.GET_EXPRESS_FORWARDING in mesh.capabilities:
        entities.extend(
            build_entities(
                [
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
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        entities_to_remove.append(
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::express_forwarding"
        )

    if MeshCapability.GET_GUEST_NETWORK_INFO in mesh.capabilities:
        entities.extend(
            build_entities(
                [
                    BinarySensorDetails(
                        description=BinarySensorEntityDescription(
                            entity_category=EntityCategory.DIAGNOSTIC,
                            key="",
                            name="Guest Network",
                            translation_key="guest_network",
                        ),
                        entity_type=EntityType.DEVICE,
                        state_value_func=lambda d: next(iter(d.adapter_info), {}).get(
                            "guest_network"
                        ),
                    ),
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
            entities_to_remove.append(f"{ui_device}::{ENTITY_DOMAIN}::guest_network")

    if MeshCapability.GET_HOMEKIT_SETTINGS in mesh.capabilities:
        entities.extend(
            build_entities(
                [
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
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        entities_to_remove.append(
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::homekit_integration_paired"
        )

    if MeshCapability.GET_LAN_SETTINGS in mesh.capabilities:
        entities.extend(
            build_entities(
                [
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
                            key="",
                            name="Reserved IP",
                            translation_key="reserved_ip",
                        ),
                        entity_type=EntityType.DEVICE,
                        state_value_func=lambda d: next(iter(d.adapter_info), {}).get(
                            "reservation"
                        ),
                    ),
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        entities_to_remove.append(
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::dhcp_server"
        )
        for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
            entities_to_remove.append(f"{ui_device}::{ENTITY_DOMAIN}::reserved_ip")

    if MeshCapability.GET_PARENTAL_CONTROL_INFO in mesh.capabilities:
        entities.extend(
            build_entities(
                [
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
                            and d.parental_control_schedule.get(
                                "blocked_internet_access"
                            )
                            is not None
                            and any(
                                d.parental_control_schedule.get(
                                    "blocked_internet_access"
                                ).values()
                            )
                        ),
                    ),
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
            entities_to_remove.append(f"{ui_device}::{ENTITY_DOMAIN}::blocked_times")

    if MeshCapability.GET_MAC_FILTERING_SETTINGS in mesh.capabilities:
        entities.extend(
            build_entities(
                [
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
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        entities_to_remove.append(
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::mac_filtering"
        )

    if MeshCapability.GET_SPEEDTEST_STATUS in mesh.capabilities:
        entities.extend(
            build_entities(
                [
                    BinarySensorDetails(
                        description=BinarySensorEntityDescription(
                            device_class=BinarySensorDeviceClass.RUNNING,
                            entity_category=EntityCategory.DIAGNOSTIC,
                            entity_registry_enabled_default=False,
                            key="",
                            name="Speedtest Status",
                            translation_key="speedtest_status",
                        ),
                        coordinator_type=CoordinatorTypes.SPEEDTEST,
                        entity_type=EntityType.MESH,
                        state_value_func=lambda r: r.friendly_status
                        not in (SpeedtestStatus.FINISHED, SpeedtestStatus.UNKNOWN),
                    ),
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        entities_to_remove.append(
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::speedtest_status"
        )

    if MeshCapability.GET_TOPOLOGY_OPTIMISATION_SETTINGS in mesh.capabilities:
        entities.extend(
            build_entities(
                [
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
                            key="node_steering_enabled",
                            name="Node Steering",
                            translation_key="node_steering",
                        ),
                        entity_type=EntityType.MESH,
                    ),
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        entities_to_remove.extend(
            [
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::client_steering",
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::node_steering",
            ]
        )

    if MeshCapability.GET_UPNP_SETTINGS in mesh.capabilities:
        entities.extend(
            build_entities(
                [
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
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        entities.extend(
            [
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::upnp_allow_users_to_configure",
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::upnp_allow_users_to_disable_internet",
            ]
        )

    if MeshCapability.GET_WAN_INFO in mesh.capabilities:
        entities.extend(
            build_entities(
                [
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
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        entities_to_remove.append(
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::wan_status"
        )
    # endregion

    entities_to_add = [LinksysVelopBinarySensor(**entity) for entity in entities]
    if len(entities_to_add) > 0:
        async_add_entities(entities_to_add)

    if len(entities_to_remove) > 0:
        for entity_unique_id in entities_to_remove:
            remove_velop_entity_from_registry(
                hass,
                config_entry.entry_id,
                entity_unique_id,
            )


class LinksysVelopBinarySensor(LinksysVelopEntity, BinarySensorEntity):
    """Linksys Velop binary sensor."""

    @callback
    def _update_attr_value(self) -> None:
        """Set the value attribute."""

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
