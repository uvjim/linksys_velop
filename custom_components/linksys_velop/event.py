"""Event entities for the Linksys Velop."""

# region #-- imports --#
import logging
from dataclasses import dataclass
from typing import Any, cast

from homeassistant.components.event import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.mesh_entity import DeviceEntity, NodeEntity

from .const import DOMAIN, EventSubTypes
from .coordinator import (
    CoordinatorTypes,
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

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LinksysVelopEventEntityDescription(
    LinksysVelopEntityDescription, EventEntityDescription
):
    """Describes Velop event entity."""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialise an event entity."""

    def _create_entities() -> None:
        """Create the mesh and device entities."""

        entities_to_add: tuple[LinksysVelopEventMultiUseEntity, ...] = (
            _init_device_entities() + _init_mesh_entities()
        )

        if len(entities_to_add) > 0:
            async_add_entities(entities_to_add)

    def _init_device_entities() -> tuple[LinksysVelopEventMultiUseEntity, ...]:
        """Describe the entities that target devices."""
        ret: tuple[LinksysVelopEventMultiUseEntity, ...] = ()

        return ret

    def _init_mesh_entities() -> tuple[LinksysVelopEventMultiUseEntity, ...]:
        """Describe the entities that target the mesh."""
        ret: tuple[LinksysVelopEventMultiUseEntity, ...] = ()
        context: LinksysVelopEntityContext = LinksysVelopEntityContext(
            unique_id=config_entry.entry_id
        )
        mesh_entities: list[LinksysVelopEventEntityDescription] = []

        mesh_entities.append(
            LinksysVelopEventEntityDescription(
                entity_category=EntityCategory.DIAGNOSTIC,
                event_types=[ev.value for ev in EventSubTypes],
                has_entity_name=True,
                key="",
                name="Events",
                target_type=EntityType.MESH,
                translation_key="mesh_events",
            ),
        )

        ret = tuple(
            [
                LinksysVelopEventMultiUseEntity(
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

        return ret

    def _init_node_entities() -> tuple[LinksysVelopEventMultiUseEntity, ...]:
        """Describe the entities that target nodes."""
        ret: tuple[LinksysVelopEventMultiUseEntity, ...] = ()

        return ret

    def _remove_stale_entities() -> None:
        """Remove entities is they are no longer required."""

        entities_to_remove: set[str] = set()

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

        entities_to_add: tuple[LinksysVelopEventMultiUseEntity, ...] = (
            _init_node_entities()
        )

        if len(entities_to_add) > 0:
            async_add_entities(entities_to_add)

    _remove_stale_entities()
    _create_entities()
    create_node_entities()


def _build_event_properties(
    properties: list[str], obj: DeviceEntity | NodeEntity
) -> dict[str, Any]:
    """Create the required properties for the event."""

    return {"data": {prop: getattr(obj, prop, None) for prop in properties}}


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

    async def _async_process_event_new_node_found(self, node: NodeEntity) -> None:
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
