"""Sensor entities for Linksys Velop."""

# region #-- imports --#
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast, override

from homeassistant.components.binary_sensor import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.mesh import MeshCapability
from pyvelop.mesh_entity import NodeEntity

from .const import CONF_UI_DEVICES
from .coordinator import (
    CoordinatorTimers,
    CoordinatorTypes,
    LinksysVelopConfigEntry,
    LinksysVelopDataUpdateCoordinatorChannelScan,
    LinksysVelopDataUpdateCoordinatorMultiUse,
    LinksysVelopDataUpdateCoordinatorSpeedtest,
    SpeedtestStatus,
)
from .entities import (
    EntityType,
    LinksysVelopChannelScanEntity,
    LinksysVelopEntityContext,
    LinksysVelopEntityDescription,
    LinksysVelopMultiUseEntity,
    LinksysVelopSpeedtestEntity,
)
from .helpers import remove_velop_entity_from_registry

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LinksysVelopBinarySensorEntityDescription(
    LinksysVelopEntityDescription, BinarySensorEntityDescription
):
    """Describes Velop binary sensor entity."""

    esa_fn: Callable[..., dict[str, Any] | None] | None = None
    value_fn: Callable[..., bool | None] | None = None


def status_extra_attributes(n: NodeEntity) -> dict[str, Any] | None:
    """Return the extra attributes for the Status binary sensor."""

    ret: dict[str, Any] | None = None

    if (
        primary_adapter := next(
            (adapter for adapter in n.adapter_info if adapter.get("primary")), None
        )
    ) is not None:
        del primary_adapter["primary"]
        ret = primary_adapter

    return ret


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialise a binary sensor."""

    known_nodes: set[str] = set()

    def _create_entities() -> None:
        """Create the mesh and device entities."""

        entities_to_add: tuple[LinksysVelopBinarySensorCoordinatorEntity, ...] = (
            _init_device_entities() + _init_mesh_entities()
        )

        if len(entities_to_add) > 0:
            async_add_entities(entities_to_add)

    def _init_device_entities() -> (
        tuple[LinksysVelopBinarySensorCoordinatorEntity, ...]
    ):
        """Describe the entities that target devices."""
        ret: tuple[LinksysVelopBinarySensorCoordinatorEntity, ...] = ()
        ret_temp: list[LinksysVelopBinarySensorCoordinatorEntity] = []

        for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
            context: LinksysVelopEntityContext = LinksysVelopEntityContext(
                unique_id=ui_device
            )
            mesh_entities: list[LinksysVelopBinarySensorEntityDescription] = []

            mesh_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.CONNECTIVITY,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="status",
                    name="Status",
                    target_type=EntityType.DEVICE,
                    translation_key="status",
                )
            )

            if (
                MeshCapability.GET_GUEST_NETWORK_INFO
                in config_entry.runtime_data.mesh.capabilities
            ):
                mesh_entities.append(
                    LinksysVelopBinarySensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="",
                        name="Guest Network",
                        target_type=EntityType.DEVICE,
                        translation_key="guest_network",
                        value_fn=lambda d: (
                            next(iter(d.adapter_info), {}).get("guest_network")
                            if d is not None
                            else None
                        ),
                    )
                )

            if (
                MeshCapability.GET_LAN_SETTINGS
                in config_entry.runtime_data.mesh.capabilities
            ):
                mesh_entities.append(
                    LinksysVelopBinarySensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="",
                        name="Reserved IP",
                        target_type=EntityType.DEVICE,
                        translation_key="reserved_ip",
                        value_fn=lambda d: (
                            next(iter(d.adapter_info), {}).get("reservation")
                            if d is not None
                            else None
                        ),
                    )
                )

            if (
                MeshCapability.GET_PARENTAL_CONTROL_INFO
                in config_entry.runtime_data.mesh.capabilities
            ):
                mesh_entities.append(
                    LinksysVelopBinarySensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        esa_fn=lambda d: (
                            d.parental_control_schedule.get("blocked_internet_access")
                            if d is not None
                            else None
                        ),
                        key="",
                        name="Blocked Times",
                        target_type=EntityType.DEVICE,
                        translation_key="blocked_times",
                        value_fn=lambda d: (
                            (
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
                            )
                            if d is not None
                            else None
                        ),
                    )
                )

            ret_temp.extend(
                [
                    LinksysVelopBinarySensorMultiUseEntity(
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

    def _init_mesh_entities() -> tuple[LinksysVelopBinarySensorCoordinatorEntity, ...]:
        """Describe the entities that target the mesh."""
        ret: tuple[LinksysVelopBinarySensorCoordinatorEntity, ...] = ()
        context: LinksysVelopEntityContext = LinksysVelopEntityContext(
            unique_id=config_entry.entry_id
        )
        mesh_entities: list[LinksysVelopBinarySensorEntityDescription] = []
        channelscan_entities: list[LinksysVelopBinarySensorEntityDescription] = []
        speedtest_entities: list[LinksysVelopBinarySensorEntityDescription] = []

        if (
            MeshCapability.GET_ALG_SETTINGS
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="sip_enabled",
                    name="SIP",
                    target_type=EntityType.MESH,
                    translation_key="sip",
                ),
            )

        if (
            MeshCapability.GET_CHANNEL_SCAN_STATUS
            in config_entry.runtime_data.mesh.capabilities
        ):
            channelscan_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.RUNNING,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="is_running",
                    name="Channel Scanning",
                    target_type=EntityType.MESH,
                    translation_key="channel_scanning",
                )
            )

        if (
            MeshCapability.GET_EXPRESS_FORWARDING
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="express_forwarding_enabled",
                    name="Express Forwarding",
                    target_type=EntityType.MESH,
                    translation_key="express_forwarding",
                )
            )

        if (
            MeshCapability.GET_HOMEKIT_SETTINGS
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="homekit_paired",
                    name="HomeKit Integration Paired",
                    target_type=EntityType.MESH,
                    translation_key="homekit_paired",
                )
            )

        if (
            MeshCapability.GET_LAN_SETTINGS
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="dhcp_enabled",
                    name="DHCP Server",
                    target_type=EntityType.MESH,
                    translation_key="dhcp_server",
                )
            )

        if (
            MeshCapability.GET_MAC_FILTERING_SETTINGS
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    esa_fn=lambda m: (
                        {
                            "mode": m.mac_filtering_mode,
                            "addresses": m.mac_filtering_addresses,
                        }
                        if m is not None
                        else None
                    ),
                    key="mac_filtering_enabled",
                    name="MAC Filtering",
                    translation_key="mac_filtering",
                    target_type=EntityType.MESH,
                )
            )

        if (
            MeshCapability.GET_MLO_SETTINGS
            in config_entry.runtime_data.mesh.capabilities
        ):
            if config_entry.runtime_data.mesh.mlo_state is not None:
                mesh_entities.append(
                    LinksysVelopBinarySensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        key="mlo_state",
                        name="Muti-Link Operation (MLO)",
                        translation_key="multi_link_operation",
                        target_type=EntityType.MESH,
                    )
                )

        if (
            MeshCapability.GET_SPEEDTEST_STATUS
            in config_entry.runtime_data.mesh.capabilities
        ):
            speedtest_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.RUNNING,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="",
                    name="Speedtest Status",
                    target_type=EntityType.MESH,
                    translation_key="speedtest_status",
                    value_fn=lambda r: r.friendly_status
                    not in (SpeedtestStatus.FINISHED, SpeedtestStatus.UNKNOWN),
                )
            )

        if (
            MeshCapability.GET_TOPOLOGY_OPTIMISATION_SETTINGS
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.extend(
                [
                    LinksysVelopBinarySensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        key="client_steering_enabled",
                        name="Client Steering",
                        target_type=EntityType.MESH,
                        translation_key="client_steering",
                    ),
                    LinksysVelopBinarySensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        key="node_steering_enabled",
                        name="Node Steering",
                        target_type=EntityType.MESH,
                        translation_key="node_steering",
                    ),
                ],
            )

        if (
            MeshCapability.GET_UPNP_SETTINGS
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.extend(
                [
                    LinksysVelopBinarySensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        key="upnp_allow_change_settings",
                        name="UPnP Allow Users to Configure",
                        target_type=EntityType.MESH,
                        translation_key="upnp_allow_change_settings",
                    ),
                    LinksysVelopBinarySensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        key="upnp_allow_disable_internet",
                        name="UPnP Allow Users to Disable Internet",
                        target_type=EntityType.MESH,
                        translation_key="upnp_allow_disable_internet",
                    ),
                ]
            )

        if MeshCapability.GET_WAN_INFO in config_entry.runtime_data.mesh.capabilities:
            mesh_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.CONNECTIVITY,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    esa_fn=lambda m: (
                        {
                            "ip": m.wan_ip,
                            "dns": m.wan_dns or None,
                            "mac": m.wan_mac,
                        }
                        if m is not None
                        else None
                    ),
                    key="wan_status",
                    name="WAN Status",
                    target_type=EntityType.MESH,
                    translation_key="wan_status",
                )
            )

        ret = (
            *[
                LinksysVelopBinarySensorMultiUseEntity(
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
            ],
            *[
                LinksysVelopBinarySensorSpeedtestEntity(
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
            ],
            *[
                LinksysVelopBinarySensorChannelScanEntity(
                    entity_context=context,
                    coordinator=cast(
                        LinksysVelopDataUpdateCoordinatorChannelScan,
                        config_entry.runtime_data.coordinators.get(
                            CoordinatorTypes.CHANNEL_SCAN
                        ),
                    ),
                    description=desc,
                )
                for desc in channelscan_entities
            ],
        )

        return ret

    def _init_node_entities() -> tuple[LinksysVelopBinarySensorCoordinatorEntity, ...]:
        """Describe the entities that target nodes."""
        ret: tuple[LinksysVelopBinarySensorCoordinatorEntity, ...] = ()
        ret_temp: list[LinksysVelopBinarySensorCoordinatorEntity] = []

        current_nodes: set[str] = {
            n.unique_id
            for n in config_entry.runtime_data.mesh.nodes
            if n.unique_id is not None
        }
        new_nodes: set[str] = current_nodes - known_nodes

        if new_nodes:
            known_nodes.update(new_nodes)
            for node in new_nodes:
                context: LinksysVelopEntityContext = LinksysVelopEntityContext(
                    unique_id=node
                )
                mesh_entities: list[LinksysVelopBinarySensorEntityDescription] = []

                mesh_entities.append(
                    LinksysVelopBinarySensorEntityDescription(
                        device_class=BinarySensorDeviceClass.CONNECTIVITY,
                        entity_category=EntityCategory.DIAGNOSTIC,
                        esa_fn=status_extra_attributes,
                        key="status",
                        name="Status",
                        target_type=EntityType.NODE,
                        translation_key="status",
                    )
                )

                ret_temp.extend(
                    [
                        LinksysVelopBinarySensorMultiUseEntity(
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

        entities_to_remove: set[str] = {
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::upnp",  # 2024.11.1b4 remove as we now have a switch
        }

        if (
            MeshCapability.GET_ALG_SETTINGS
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(f"{config_entry.entry_id}::{ENTITY_DOMAIN}::sip")

        if (
            MeshCapability.GET_CHANNEL_SCAN_STATUS
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::channel_scanning"
            )

        if (
            MeshCapability.GET_EXPRESS_FORWARDING
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::express_forwarding"
            )

        if (
            MeshCapability.GET_GUEST_NETWORK_INFO
            not in config_entry.runtime_data.mesh.capabilities
        ):
            for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
                entities_to_remove.add(f"{ui_device}::{ENTITY_DOMAIN}::guest_network")

        if (
            MeshCapability.GET_HOMEKIT_SETTINGS
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::homekit_integration_paired"
            )

        if (
            MeshCapability.GET_LAN_SETTINGS
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::dhcp_server"
            )
            for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
                entities_to_remove.add(f"{ui_device}::{ENTITY_DOMAIN}::reserved_ip")

        if (
            MeshCapability.GET_PARENTAL_CONTROL_INFO
            not in config_entry.runtime_data.mesh.capabilities
        ):
            for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
                entities_to_remove.add(f"{ui_device}::{ENTITY_DOMAIN}::blocked_times")

        if (
            MeshCapability.GET_MAC_FILTERING_SETTINGS
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::mac_filtering"
            )

        if (
            MeshCapability.GET_MLO_SETTINGS
            not in config_entry.runtime_data.mesh.capabilities
            or config_entry.runtime_data.mesh.mlo_state is None
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::mlo_state"
            )

        if (
            MeshCapability.GET_SPEEDTEST_STATUS
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::speedtest_status"
            )

        if (
            MeshCapability.GET_TOPOLOGY_OPTIMISATION_SETTINGS
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.update(
                {
                    f"{config_entry.entry_id}::{ENTITY_DOMAIN}::client_steering",
                    f"{config_entry.entry_id}::{ENTITY_DOMAIN}::node_steering",
                }
            )

        if (
            MeshCapability.GET_UPNP_SETTINGS
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.update(
                {
                    f"{config_entry.entry_id}::{ENTITY_DOMAIN}::upnp_allow_users_to_configure",
                    f"{config_entry.entry_id}::{ENTITY_DOMAIN}::upnp_allow_users_to_disable_internet",
                }
            )

        if (
            MeshCapability.GET_WAN_INFO
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::wan_status"
            )

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

        entities_to_add: tuple[LinksysVelopBinarySensorCoordinatorEntity, ...] = (
            _init_node_entities()
        )

        if len(entities_to_add) > 0:
            async_add_entities(entities_to_add)

    _remove_stale_entities()
    _create_entities()
    create_node_entities()

    config_entry.async_on_unload(
        cast(
            LinksysVelopDataUpdateCoordinatorMultiUse,
            config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH),
        ).add_listener_for_timer_type(CoordinatorTimers.MESH, create_node_entities)
    )


class LinksysVelopBinarySensorEntity(BinarySensorEntity):
    """Base class representing a binary sensor entity."""

    entity_description: LinksysVelopBinarySensorEntityDescription
    _entity_domain: str = ENTITY_DOMAIN


class LinksysVelopBinarySensorMultiUseEntity(
    LinksysVelopBinarySensorEntity, LinksysVelopMultiUseEntity
):
    """Linksys Velop binary sensor that uses the multi use DataUpdateCoordinator."""

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:

        ret: dict[str, Any] | None = None

        if self.entity_description.esa_fn is not None:
            ret = self.entity_description.esa_fn(self._get_target())

        return ret

    @property
    @override
    def is_on(self) -> bool | None:

        ret: bool | None = None

        if self.entity_description.value_fn is not None:
            ret = self.entity_description.value_fn(self._get_target())
        elif self.entity_description.key:
            ret = getattr(
                self._get_target(),
                self.entity_description.key,
                None,
            )

        return ret


class LinksysVelopBinarySensorChannelScanEntity(
    LinksysVelopBinarySensorEntity, LinksysVelopChannelScanEntity
):
    """Linksys Velop binary sensor that uses the channel scan DataUpdateCoordinator."""

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:

        ret: dict[str, Any] | None = None

        if self.entity_description.esa_fn is not None:
            ret = self.entity_description.esa_fn(self.coordinator.data)

        return ret

    @property
    @override
    def is_on(self) -> bool | None:

        ret: bool | None = None
        if self.entity_description.value_fn is not None:
            ret = self.entity_description.value_fn(self.coordinator.data)
        elif self.entity_description.key:
            ret = getattr(self.coordinator.data, self.entity_description.key, None)

        return ret


class LinksysVelopBinarySensorSpeedtestEntity(
    LinksysVelopBinarySensorEntity, LinksysVelopSpeedtestEntity
):
    """Linksys Velop binary sensor that uses the Speedtest DataUpdateCoordinator."""

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:

        ret: dict[str, Any] | None = None

        if self.entity_description.esa_fn is not None:
            ret = self.entity_description.esa_fn(self.coordinator.data)

        return ret

    @property
    @override
    def is_on(self) -> bool | None:

        ret: bool | None = None
        if self.entity_description.value_fn is not None:
            ret = self.entity_description.value_fn(self.coordinator.data)
        elif self.entity_description.key:
            ret = getattr(self.coordinator.data, self.entity_description.key, None)

        return ret


type LinksysVelopBinarySensorCoordinatorEntity = LinksysVelopBinarySensorChannelScanEntity | LinksysVelopBinarySensorMultiUseEntity | LinksysVelopBinarySensorSpeedtestEntity
