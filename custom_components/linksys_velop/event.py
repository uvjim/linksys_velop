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
from pyvelop.device import Device
from pyvelop.node import Node

from .const import DOMAIN
from .entities import EntityDetails, EntityType, LinksysVelopEntity, build_entities
from .types import EventSubTypes, LinksysVelopConfigEntry

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass
class EventDetails(EntityDetails):
    """Representation of the details that make up the entity."""

    description: EventEntityDescription


ENTITY_DETAILS: list[EventDetails] = [
    EventDetails(
        description=EventEntityDescription(
            entity_category=EntityCategory.DIAGNOSTIC,
            event_types=[ev.value for ev in EventSubTypes],
            has_entity_name=True,
            key="",
            name="Events",
            translation_key="mesh_events",
        ),
        entity_type=EntityType.MESH,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize a sensor."""

    entities_to_add: list[LinksysVelopEventEntity] = []

    entities = build_entities(ENTITY_DETAILS, config_entry, ENTITY_DOMAIN)
    entities_to_add = [LinksysVelopEventEntity(**entity) for entity in entities]

    if len(entities_to_add) > 0:
        async_add_entities(entities_to_add)


def _build_event_properties(
    properties: list[str], obj: Device | Node
) -> dict[str, Any]:
    """Create the required properties for the event."""

    return {prop: getattr(obj, prop, None) for prop in properties}


class LinksysVelopEventEntity(LinksysVelopEntity, EventEntity):
    """Representation of the event entity."""

    async def _async_process_event_new_device_found(self, device: Device) -> None:
        """Respond to a new device beig found."""

        event_properties: list[str] = [
            "connected_adapters",
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

    async def _async_process_event_new_node_found(self, node: Node) -> None:
        """Respond to a new node being found."""

        event_properties: list[str] = [
            "backhaul",
            "connected_adapters",
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
                _LOGGER.warning("No event processor for event %s", func_name)
                continue

            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"{DOMAIN}_{event}",
                    getattr(self, func_name),
                )
            )
