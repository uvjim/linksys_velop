"""Event entities for the Linksys Velop."""

# region #-- imports --#
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.event import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.mesh_attribute import MeshAttribute
from pyvelop.mesh_entity import DeviceEntity, NodeEntity

from .const import DOMAIN, EventSubTypes
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
)
from .helpers import remove_velop_entity_from_registry
from .logger import Logger

# endregion

_LOGGER: Logger = Logger(logging.getLogger(__name__))


@dataclass(frozen=True, kw_only=True)
class LinksysVelopEventEntityDescription(
    LinksysVelopEntityDescription, EventEntityDescription
):
    """Describes Velop event entity."""


def _build_event_properties(
    properties: list[str], obj: DeviceEntity | NodeEntity
) -> dict[str, Any]:
    """Create the required properties for the event."""

    props: dict[str, Any] = {}
    for prop in properties:
        attr = getattr(obj, prop, None)
        if isinstance(attr, MeshAttribute):
            attr = attr.to_dict(include_audit=False)
        props[prop] = attr

    return {"data": props}


class LinksysVelopEventEntity(EventEntity):
    """Base class representing an event entity."""

    entity_description: LinksysVelopEventEntityDescription
    _entity_domain: str = ENTITY_DOMAIN


class LinksysVelopEventMultiUseEntity(
    LinksysVelopEventEntity, LinksysVelopMultiUseEntity
):
    """Representation of the event entity."""

    async def _async_process_event_new_device_found(self, device: DeviceEntity) -> None:
        """Respond to a new device beig found."""

        event_properties: list[str] = [
            "adapter_info",
            "description",
            "manufacturer",
            "model",
            "name",
            "operating_system",
            "parent_name",
            "serial",
            "status",
            "unique_id",
        ]

        event_attributes: dict[str, Any] = _build_event_properties(
            event_properties, device
        )
        self._trigger_event(EventSubTypes.NEW_DEVICE_FOUND.value, event_attributes)
        self.async_write_ha_state()

    async def _async_process_event_new_node_found(self, node: NodeEntity) -> None:
        """Respond to a new node being found."""

        event_properties: list[str] = [
            "backhaul",
            "adapter_info",
            "model",
            "name",
            "parent_name",
            "serial",
            "status",
            "unique_id",
        ]

        event_attributes: dict[str, Any] = _build_event_properties(
            event_properties, node
        )
        self._trigger_event(EventSubTypes.NEW_NODE_FOUND.value, event_attributes)
        self.async_write_ha_state()

    async def _async_process_event_mesh_rebooted(self) -> None:
        """Process the mesh rebooted event."""

        self._trigger_event(EventSubTypes.MESH_REBOOTED)
        self.async_write_ha_state()

    async def _async_process_event_mesh_rebooting(self) -> None:
        """Process the mesh rebooting event."""

        self._trigger_event(EventSubTypes.MESH_REBOOTING)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Initialise necessary listeners."""

        await super().async_added_to_hass()
        for event in self.event_types:
            func_name: str = f"_async_process_event_{event}"
            if not hasattr(self, func_name):
                _LOGGER.warning("no event processor for event %s", func_name)
                continue

            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"{DOMAIN}_{event}",
                    getattr(self, func_name),
                )
            )


type LinksysVelopEventCoordinatorEntity = LinksysVelopEventMultiUseEntity


def _init_device_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> tuple[LinksysVelopEventMultiUseEntity, ...]:
    """Describe the entities that target devices.

    :param coordinator: The coordinator providing the runtime data.
    :return: A tuple of device-targeted entities.
    """

    ret: tuple[LinksysVelopEventMultiUseEntity, ...] = ()

    return ret


def _init_mesh_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> tuple[LinksysVelopEventMultiUseEntity, ...]:
    """Describe the entities that target the mesh.

    :param coordinator: The coordinator providing the runtime data.
    :return: A tuple of mesh-targeted entities.
    """

    descriptions = (
        LinksysVelopEventEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            event_types=[event.value for event in EventSubTypes],
            has_entity_name=True,
            key="",
            name="Events",
            target_type=EntityType.MESH,
            translation_key="mesh_events",
        ),
    )

    config_entry = coordinator.config_entry
    context = LinksysVelopEntityContext(unique_id=config_entry.entry_id)

    return tuple(
        LinksysVelopEventMultiUseEntity(
            entity_context=context,
            coordinator=coordinator,
            description=description,
        )
        for description in descriptions
    )


def _init_node_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> tuple[LinksysVelopEventMultiUseEntity, ...]:
    """Describe the entities that target nodes.

    :param coordinator: The coordinator providing the runtime data.
    :return: A tuple of node-targeted entities.
    """
    ret: tuple[LinksysVelopEventMultiUseEntity, ...] = ()

    return ret


def _remove_stale_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> None:
    """Remove entities is they are no longer required.

    :param coordinator: The coordinator providing the runtime data.
    """

    entities_to_remove: set[str] = set()

    for entity_unique_id in entities_to_remove:
        remove_velop_entity_from_registry(
            coordinator.hass,
            coordinator.config_entry.entry_id,
            entity_unique_id,
        )


def create_node_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the node entities.

    This is in a separate function because new nodes can be added to the mesh whilst the integration is running.

    :param coordinator: The data update coordinator.
    :param async_add_entities: Callback to add entities to Home Assistant.
    """

    entities_to_add: tuple[LinksysVelopEventMultiUseEntity, ...] = _init_node_entities(
        coordinator
    )

    if entities_to_add:
        async_add_entities(entities_to_add)


def create_static_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the mesh and device entities.

    :param coordinator: The data update coordinator.
    :param async_add_entities: Callback to add entities to Home Assistant.
    """

    entities_to_add: tuple[LinksysVelopEventMultiUseEntity, ...] = (
        _init_device_entities(coordinator) + _init_mesh_entities(coordinator)
    )

    if entities_to_add:
        async_add_entities(entities_to_add)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialise an event entity.

    :param hass: The Home Assistant instance.
    :param config_entry: The configuration entry for the device.
    :param async_add_entities: Callback to add entities to Home Assistant.
    """

    coordinator = config_entry.runtime_data.coordinator

    _remove_stale_entities(coordinator)
    create_static_entities(coordinator, async_add_entities)
    create_node_entities(coordinator, async_add_entities)

    config_entry.async_on_unload(
        config_entry.runtime_data.coordinator.add_listener_for_timer_type(
            CoordinatorTimers.MESH,
            lambda: create_node_entities(coordinator, async_add_entities),
        )
    )
