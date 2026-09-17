"""Sensor entities for Linksys Velop."""

# region #-- imports --#
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
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
from homeassistant.util import slugify
from pyvelop.mesh import MeshSnapshot
from pyvelop.mesh_attribute import MeshAttribute
from pyvelop.mesh_entity import AdapterInfo, DeviceEntity, NodeAdapterInfo, NodeEntity

from .const import CONF_UI_DEVICES
from .coordinator import (
    BlockingTasks,
    CoordinatorTimers,
    LinksysVelopConfigEntry,
)
from .entities import (
    EntityType,
    LinksysVelopEntityContext,
    LinksysVelopEntityDescription,
    LinksysVelopMultiUseEntity,
)
from .helpers import remove_velop_entity_from_registry
from .logger import Logger

# endregion

_LOGGER: Logger = Logger(logging.getLogger(__name__))
CAP_CHANNEL_SCAN: str = "START_CHANNEL_SCAN"


@dataclass(frozen=True, kw_only=True)
class LinksysVelopBinarySensorEntityDescription(
    LinksysVelopEntityDescription, BinarySensorEntityDescription
):
    """Describes Velop binary sensor entity."""

    esa_fn: Callable[..., dict[str, Any] | None] | None = None
    value_fn: Callable[..., bool | None] | None = None


def get_device_adapter_info(device: DeviceEntity, key: str) -> Any:
    """Retrieve the give details about a device adapter."""

    ret: Any = None
    adi: AdapterInfo | None = next(iter(device.adapter_info), None)
    if adi is not None:
        ret = getattr(adi, key, None)

    return ret


def has_capability(capabilities: tuple[Mapping[str, Any], ...], name: str) -> bool:
    """Determine of the mesh has a spevcified capability.

    :param capabilities: Capabilities as returned from the mesh.
    :returns: `True` if the capability is available, `False` otherwise.
    """

    found: Mapping[str, Any] | None = next(
        (
            cap
            for cap in capabilities
            if cap.get("key", "") == name and cap.get("is_valid", False) is not False
        ),
        None,
    )

    return bool(found)


def status_extra_attributes(n: NodeEntity) -> dict[str, Any] | None:
    """Return the extra attributes for the Status binary sensor."""

    ret: dict[str, Any] | None = None

    primary_adapter: NodeAdapterInfo | None
    if (
        primary_adapter := next((adi for adi in n.adapter_info if adi.primary), None)
    ) is not None:
        ret = primary_adapter.to_dict()
        del ret["primary"]

    return ret


ENTITIES: Mapping[str, tuple[LinksysVelopBinarySensorEntityDescription, ...]] = (
    MappingProxyType(
        {
            "adapter_info": (
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="",
                    name="Guest Network",
                    target_type=EntityType.DEVICE,
                    translation_key="guest_network",
                    value_fn=lambda device: (
                        get_device_adapter_info(device, "guest_network")
                        if device is not None
                        else None
                    ),
                ),
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="",
                    name="Reserved IP",
                    target_type=EntityType.DEVICE,
                    translation_key="reserved_ip",
                    value_fn=lambda device: (
                        get_device_adapter_info(device, "reservation")
                        if device is not None
                        else None
                    ),
                ),
            ),
            "client_steering_enabled": (
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="client_steering_enabled",
                    name="Client Steering",
                    target_type=EntityType.MESH,
                    translation_key="client_steering",
                ),
            ),
            "dhcp_enabled": (
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="dhcp_enabled",
                    name="DHCP Server",
                    target_type=EntityType.MESH,
                    translation_key="dhcp_server",
                ),
            ),
            "express_forwarding_enabled": (
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="express_forwarding_enabled",
                    name="Express Forwarding",
                    target_type=EntityType.MESH,
                    translation_key="express_forwarding",
                ),
            ),
            "homekit_paired": (
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="homekit_paired",
                    name="HomeKit Integration Paired",
                    target_type=EntityType.MESH,
                    translation_key="homekit_paired",
                ),
            ),
            "mac_filtering_enabled": (
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    esa_fn=lambda mesh: (
                        {
                            "mode": str(cast(MeshSnapshot, mesh).mac_filtering_mode),
                            "addresses": cast(
                                MeshSnapshot, mesh
                            ).mac_filtering_addresses.value,
                        }
                        if mesh is not None
                        else None
                    ),
                    key="mac_filtering_enabled",
                    name="MAC Filtering",
                    translation_key="mac_filtering",
                    target_type=EntityType.MESH,
                ),
            ),
            "mlo_state": (
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="mlo_state",
                    name="Muti-Link Operation (MLO)",
                    translation_key="multi_link_operation",
                    target_type=EntityType.MESH,
                ),
            ),
            "node_steering_enabled": (
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="node_steering_enabled",
                    name="Node Steering",
                    target_type=EntityType.MESH,
                    translation_key="node_steering",
                ),
            ),
            "parental_control_schedule": (
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    esa_fn=lambda device: (
                        device.parental_control_schedule.get("blocked_internet_access")
                        if device is not None
                        else None
                    ),
                    key="",
                    name="Blocked Times",
                    target_type=EntityType.DEVICE,
                    translation_key="blocked_times",
                    value_fn=lambda device: (
                        (
                            device.parental_control_schedule is not None
                            and device.parental_control_schedule.get(
                                "blocked_internet_access"
                            )
                            is not None
                            and any(
                                device.parental_control_schedule.get(
                                    "blocked_internet_access"
                                ).values()
                            )
                        )
                        if device is not None
                        else None
                    ),
                ),
            ),
            "sip_enabled": (
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="sip_enabled",
                    name="SIP",
                    target_type=EntityType.MESH,
                    translation_key="sip",
                ),
            ),
            "status": (
                LinksysVelopBinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.CONNECTIVITY,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="status",
                    name="Status",
                    target_type=EntityType.DEVICE,
                    translation_key="status",
                ),
                LinksysVelopBinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.CONNECTIVITY,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    esa_fn=status_extra_attributes,
                    key="status",
                    name="Status",
                    target_type=EntityType.NODE,
                    translation_key="status",
                ),
            ),
            "upnp_allow_change_settings": (
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="upnp_allow_change_settings",
                    name="UPnP Allow Users to Configure",
                    target_type=EntityType.MESH,
                    translation_key="upnp_allow_change_settings",
                ),
            ),
            "upnp_allow_disable_internet": (
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="upnp_allow_disable_internet",
                    name="UPnP Allow Users to Disable Internet",
                    target_type=EntityType.MESH,
                    translation_key="upnp_allow_disable_internet",
                ),
            ),
            "wan_status": (
                LinksysVelopBinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.CONNECTIVITY,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    esa_fn=lambda mesh: (
                        {
                            "ip": cast(MeshSnapshot, mesh).wan_ip.value,
                            "dns": cast(MeshSnapshot, mesh).wan_dns.value or None,
                            "mac": cast(MeshSnapshot, mesh).wan_mac.value,
                        }
                        if mesh is not None
                        else None
                    ),
                    key="wan_status",
                    name="WAN Status",
                    target_type=EntityType.MESH,
                    translation_key="wan_status",
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
    """Initialise a binary sensor."""

    known_node_ids: set[str] = set()

    def _create_entities() -> None:
        """Create the mesh and device entities."""

        entities_to_add: tuple[LinksysVelopBinarySensorCoordinatorEntity, ...] = (
            _init_device_entities() + _init_mesh_entities()
        )

        if entities_to_add:
            async_add_entities(entities_to_add)

    def _init_device_entities() -> (
        tuple[LinksysVelopBinarySensorCoordinatorEntity, ...]
    ):
        """Describe the entities that target devices."""

        descriptions = tuple(
            entity
            for attr, entities in ENTITIES.items()
            if hasattr(DeviceEntity, attr)
            for entity in entities
            if entity.target_type is EntityType.DEVICE
        )

        coordinator = config_entry.runtime_data.coordinator

        return tuple(
            LinksysVelopBinarySensorMultiUseEntity(
                entity_context=LinksysVelopEntityContext(unique_id=device_id),
                coordinator=coordinator,
                description=description,
            )
            for device_id in config_entry.options.get(CONF_UI_DEVICES, [])
            for description in descriptions
        )

    def _init_mesh_entities() -> tuple[LinksysVelopBinarySensorCoordinatorEntity, ...]:
        """Describe the entities that target the mesh."""

        coordinator = config_entry.runtime_data.coordinator
        mesh = coordinator.data.mesh
        if mesh is None:
            return ()

        descriptions = tuple(
            entity
            for attr, entities in ENTITIES.items()
            if hasattr(mesh, attr)
            for entity in entities
            if entity.target_type is EntityType.MESH
        )

        # Add this entity here to provide easy access to config_entry.
        if has_capability(mesh.capabilities, CAP_CHANNEL_SCAN):
            descriptions += (
                LinksysVelopBinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.RUNNING,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="",
                    name="Channel Scanning",
                    target_type=EntityType.MESH,
                    translation_key="channel_scanning",
                    value_fn=lambda _: (
                        BlockingTasks.CHANNEL_SCAN
                        in config_entry.runtime_data.blocking_tasks
                    ),
                ),
            )

        # Add this entity here to provide easy access to config_entry.
        if hasattr(mesh, "speedtest_results"):
            descriptions += (
                LinksysVelopBinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.RUNNING,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="",
                    name="Speedtest Status",
                    target_type=EntityType.MESH,
                    translation_key="speedtest_status",
                    value_fn=lambda _: (
                        BlockingTasks.SPEEDTEST
                        in config_entry.runtime_data.blocking_tasks
                    ),
                ),
            )

        coordinator = config_entry.runtime_data.coordinator

        context = LinksysVelopEntityContext(unique_id=config_entry.entry_id)

        return tuple(
            LinksysVelopBinarySensorMultiUseEntity(
                entity_context=context,
                coordinator=coordinator,
                description=description,
            )
            for description in descriptions
        )

    def _init_node_entities() -> tuple[LinksysVelopBinarySensorCoordinatorEntity, ...]:
        """Describe the entities that target nodes."""

        coordinator = config_entry.runtime_data.coordinator
        mesh_data = coordinator.data.mesh
        if mesh_data is None:
            return ()

        current_node_ids = {
            node.unique_id.value
            for node in mesh_data.nodes
            if node.unique_id.value is not None
        }
        new_node_ids = current_node_ids - known_node_ids
        known_node_ids.update(new_node_ids)

        descriptions = tuple(
            entity
            for attr, entities in ENTITIES.items()
            if hasattr(NodeEntity, attr)
            for entity in entities
            if entity.target_type is EntityType.NODE
        )

        coordinator = config_entry.runtime_data.coordinator

        return tuple(
            LinksysVelopBinarySensorMultiUseEntity(
                entity_context=LinksysVelopEntityContext(unique_id=node_id),
                coordinator=coordinator,
                description=description,
            )
            for node_id in new_node_ids
            for description in descriptions
        )

    def _remove_stale_entities() -> None:
        """Remove entities that are no longer required."""

        coordinator = config_entry.runtime_data.coordinator
        mesh_data = coordinator.data.mesh
        if mesh_data is None:
            return

        entities_to_remove = {
            # Removed in 2024.11.1b4; replaced by a switch.
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::upnp",
        }

        # Remove mesh entities that are no longer available.
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

        if not has_capability(mesh_data.capabilities, CAP_CHANNEL_SCAN):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::channel_scanning"
            )

        if not hasattr(mesh_data, "speedtest_results"):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::speedtest_status"
            )

        # Remove device entities that are no longer available.
        device_entities = {
            attr if len(entities) == 1 else slugify(str(entity.name))
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
        config_entry.runtime_data.coordinator.add_listener_for_timer_type(
            CoordinatorTimers.MESH, create_node_entities
        )
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
            if isinstance(ret, MeshAttribute):
                ret = ret.value

        return ret


type LinksysVelopBinarySensorCoordinatorEntity = LinksysVelopBinarySensorMultiUseEntity
