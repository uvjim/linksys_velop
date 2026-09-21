"""Text entities for Linksys Velop."""

# region #-- imports --#
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import override

from homeassistant.components.text import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.mesh_attribute import MeshAttribute
from pyvelop.mesh_entity import DeviceEntity

from .const import CONF_UI_DEVICES
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
class LinksysVelopTextEntityDescription(
    LinksysVelopEntityDescription, TextEntityDescription
):
    """Describes Velop text entity."""


ENTITIES: Mapping[str, tuple[LinksysVelopTextEntityDescription, ...]] = (
    MappingProxyType(
        {
            "name": (
                LinksysVelopTextEntityDescription(
                    entity_category=EntityCategory.CONFIG,
                    key="name",
                    name="Name",
                    target_type=EntityType.DEVICE,
                    translation_key="name",
                ),
            )
        }
    )
)


class LinksysVelopTextEntity(TextEntity):
    """Base class representing a text entity."""

    entity_description: LinksysVelopTextEntityDescription
    _entity_domain: str = ENTITY_DOMAIN
    _attr_native_min: int = 1


class LinksysVelopTextMultiUseEntity(
    LinksysVelopTextEntity, LinksysVelopMultiUseEntity
):
    """Linksys Velop text entity that uses multi use LinksysVelopDataUpdateCoordinatorMultiUse."""

    @override
    async def async_set_value(self, value: str) -> None:

        device: TargetEntityType = self._get_target()
        if isinstance(device, DeviceEntity):
            await device.async_rename(value)
            await self.coordinator.async_force_refresh(CoordinatorTimers.MESH)

    @property
    @override
    def native_value(self) -> str | None:

        ret: str | None = None

        if self.entity_description.key:
            ret = getattr(
                self._get_target(),
                self.entity_description.key,
                None,
            )
            if isinstance(ret, MeshAttribute):
                ret = ret.value

        return ret


type LinksysVelopTextCoordinatorEntity = LinksysVelopTextMultiUseEntity


def _init_device_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> tuple[LinksysVelopTextCoordinatorEntity, ...]:
    """Initialise the entities that target devices.

    :param coordinator: The data update coordinator.
    :return: A tuple of initialised device entities.
    """
    config_entry = coordinator.config_entry
    descriptions = tuple(
        entity
        for attr, entities in ENTITIES.items()
        if hasattr(DeviceEntity, attr)
        for entity in entities
        if entity.target_type is EntityType.DEVICE
    )

    return tuple(
        LinksysVelopTextMultiUseEntity(
            entity_context=LinksysVelopEntityContext(unique_id=device_id),
            coordinator=coordinator,
            description=description,
        )
        for device_id in config_entry.options.get(CONF_UI_DEVICES, [])
        for description in descriptions
    )


def _init_mesh_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> tuple[LinksysVelopTextCoordinatorEntity, ...]:
    """Initialise the entities that target the mesh.

    :return: A tuple of initialised mesh entities.
    """
    return ()


def _init_node_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
    known_nodes: set[str],
) -> tuple[LinksysVelopTextCoordinatorEntity, ...]:
    """Describe the entities that target nodes.

    :param coordinator: The coordinator providing the runtime data.
    :param known_nodes: A set of node IDs that have already been initialised.
    :return: A tuple of node-targeted update entities.
    """
    return ()


def _remove_stale_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> None:
    """Remove entities if they are no longer required.

    :param coordinator: The data update coordinator.
    """
    hass = coordinator.hass
    config_entry = coordinator.config_entry
    entities_to_remove: set[str] = set()

    for entity_unique_id in entities_to_remove:
        remove_velop_entity_from_registry(
            hass,
            config_entry.entry_id,
            entity_unique_id,
        )


def create_static_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the mesh and device entities.

    :param coordinator: The data update coordinator.
    :param async_add_entities: Callback to add entities to Home Assistant.
    """
    entities_to_add = _init_device_entities(coordinator) + _init_mesh_entities(
        coordinator
    )
    if entities_to_add:
        async_add_entities(entities_to_add)


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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialise the integration entry.

    :param hass: The Home Assistant instance.
    :param config_entry: The configuration entry for the device.
    :param async_add_entities: Callback to add entities to Home Assistant.
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
