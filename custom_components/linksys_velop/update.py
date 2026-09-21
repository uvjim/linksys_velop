"""Update entities for Linksys Velop."""

# region #-- imports --#
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, cast, override

from homeassistant.components.update import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.mesh import FirmwareUpdatePolicy
from pyvelop.mesh_entity import NodeEntity

from . import LinksysVelopConfigEntry
from .const import CONF_NODE_IMAGES
from .coordinator import CoordinatorTimers, LinksysVelopDataUpdateCoordinatorMultiUse
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


@dataclass(frozen=True, kw_only=True)
class LinksysVelopUpdateEntityDescription(
    LinksysVelopEntityDescription, UpdateEntityDescription
):
    """Describes Velop update entity."""

    pic_fn: Callable[..., str | None] | None = None


ENTITIES: Mapping[str, tuple[LinksysVelopUpdateEntityDescription, ...]] = (
    MappingProxyType({})
)


class LinksysVelopUpdateMultiUseEntity(LinksysVelopMultiUseEntity, UpdateEntity):
    """Linksys Velop update entity."""

    entity_description: LinksysVelopUpdateEntityDescription
    _entity_domain: str = ENTITY_DOMAIN

    @property
    @override
    def auto_update(self) -> bool:

        mesh_data = self.coordinator.data.mesh
        if mesh_data is None:
            return False

        ret: bool = False
        ret = mesh_data.firmware_update_setting != FirmwareUpdatePolicy.MANUAL

        return ret

    @property
    @override
    def entity_picture(self) -> str | None:

        ret: str | None = None

        if self.entity_description.pic_fn is not None:
            ret = self.entity_description.pic_fn(self._get_target())

        return ret

    @property
    @override
    def installed_version(self) -> str | None:

        ret: str | None = cast(NodeEntity, self._get_target()).firmware.get("version")

        return ret

    @property
    @override
    def latest_version(self) -> str | None:

        ret: str | None = cast(NodeEntity, self._get_target()).firmware.get(
            "latest_version"
        )

        return ret


type LinksysVelopUpdateCoordinatorEntity = LinksysVelopUpdateMultiUseEntity


def _has_capability(capabilities: tuple[Mapping[str, Any], ...], name: str) -> bool:
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


def _init_device_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> tuple[LinksysVelopUpdateCoordinatorEntity, ...]:
    """Describe the entities that target devices.

    :param coordinator: The coordinator providing the runtime data.
    :return: A tuple of device-targeted update entities.
    """
    return ()


def _init_mesh_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> tuple[LinksysVelopUpdateCoordinatorEntity, ...]:
    """Describe the entities that target the mesh.

    :param coordinator: The coordinator providing the runtime data.
    :return: A tuple of mesh-targeted update entities.
    """
    return ()


def _init_node_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
    known_nodes: set[str],
) -> tuple[LinksysVelopUpdateCoordinatorEntity, ...]:
    """Describe the entities that target nodes.

    :param coordinator: The coordinator providing the runtime data.
    :param known_nodes: A set of node IDs that have already been initialised.
    :return: A tuple of node-targeted update entities.
    """
    config_entry = coordinator.config_entry
    mesh_data = coordinator.data.mesh
    if mesh_data is None:
        return ()

    current_node_ids = {
        str(node.unique_id) for node in mesh_data.nodes if node.unique_id.value
    }
    new_node_ids = current_node_ids - known_nodes
    known_nodes.update(new_node_ids)

    descriptions = [
        entity
        for attr, entities in ENTITIES.items()
        if hasattr(NodeEntity, attr)
        for entity in entities
        if entity.target_type is EntityType.NODE
    ]

    if hasattr(NodeEntity, "firmware"):
        prefix = config_entry.options.get(CONF_NODE_IMAGES)
        descriptions.append(
            LinksysVelopUpdateEntityDescription(
                device_class=UpdateDeviceClass.FIRMWARE,
                key="",
                name="Update",
                pic_fn=lambda node: (
                    f"{prefix.rstrip('/').strip()}/{cast(NodeEntity, node).model.value}.png"
                    if prefix
                    else None
                ),
                target_type=EntityType.NODE,
                translation_key="update",
            ),
        )

    return tuple(
        LinksysVelopUpdateMultiUseEntity(
            entity_context=LinksysVelopEntityContext(unique_id=node_id),
            coordinator=coordinator,
            description=description,
        )
        for node_id in new_node_ids
        for description in descriptions
    )


def _remove_stale_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> None:
    """Remove entities that are no longer required from the entity registry.

    :param coordinator: The coordinator providing the runtime data.
    """
    config_entry = coordinator.config_entry
    if hasattr(NodeEntity, "firmware") or (mesh_data := coordinator.data.mesh) is None:
        return

    for node in mesh_data.nodes:
        remove_velop_entity_from_registry(
            coordinator.hass,
            config_entry.entry_id,
            f"{node.unique_id}::{ENTITY_DOMAIN}::update",
        )


def create_node_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
    known_nodes: set[str],
    async_add_entities: AddEntitiesCallback,
):
    """Create and add node entities to Home Assistant.

    :param coordinator: The coordinator providing the runtime data.
    :param known_nodes: The set of already known node IDs.
    :param async_add_entities: The callback to add entities to the system.
    """
    if entities := _init_node_entities(coordinator, known_nodes):
        async_add_entities(entities)


def create_static_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
    async_add_entities: AddEntitiesCallback,
):
    """Create and add static mesh and device entities to Home Assistant.

    :param coordinator: The coordinator providing the runtime data.
    :param async_add_entities: The callback to add entities to the system.
    """

    entities = _init_device_entities(coordinator) + _init_mesh_entities(coordinator)
    if entities:
        async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialise the update entities for a Linksys Velop device.

    :param hass: The Home Assistant instance.
    :param config_entry: The configuration entry for this device.
    :param async_add_entities: The callback to add entities to the system.
    """

    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse = (
        config_entry.runtime_data.coordinator
    )
    known_nodes: set[str] = set()

    _remove_stale_entities(coordinator)
    create_static_entities(coordinator, async_add_entities)
    create_node_entities(coordinator, known_nodes, async_add_entities)

    config_entry.async_on_unload(
        coordinator.add_listener_for_timer_type(
            CoordinatorTimers.MESH,
            lambda: create_node_entities(coordinator, known_nodes, async_add_entities),
        )
    )
