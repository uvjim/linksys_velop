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
from pyvelop.mesh import FirmwareUpdatePolicy, Mesh
from pyvelop.mesh_entity import NodeEntity

from . import LinksysVelopConfigEntry
from .const import CONF_NODE_IMAGES
from .coordinator import (
    CoordinatorTimers,
    CoordinatorTypes,
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
class LinksysVelopUpdateEntityDescription(
    LinksysVelopEntityDescription, UpdateEntityDescription
):
    """Describes Velop update entity."""

    pic_fn: Callable[..., str | None] | None = None


def has_capability(capabilities: tuple[Mapping[str, Any], ...], name: str) -> bool:
    """Determine of the mesh has a spevcified capability.

    :param capabilities: Capabilities as returned from the mesh.
    :returns: `True` if the capability is available, `False` otherwise.
    """

    found: Mapping[str, Any] | None = next(
        (cap for cap in capabilities if cap.get("key", "") == name), None
    )

    return bool(found)


ENTITIES: Mapping[str, tuple[LinksysVelopUpdateEntityDescription, ...]] = (
    MappingProxyType({})
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize an update entity."""

    known_nodes: set[str] = set()

    def _create_entities() -> None:
        """Create the mesh and device entities."""

        entities_to_add: tuple[LinksysVelopUpdateCoordinatorEntity, ...] = (
            _init_device_entities() + _init_mesh_entities()
        )

        if entities_to_add:
            async_add_entities(entities_to_add)

    def _init_device_entities() -> tuple[LinksysVelopUpdateCoordinatorEntity, ...]:
        """Describe the entities that target devices."""
        ret: tuple[LinksysVelopUpdateCoordinatorEntity, ...] = ()

        return ret

    def _init_mesh_entities() -> tuple[LinksysVelopUpdateCoordinatorEntity, ...]:
        """Describe the entities that target the mesh."""
        ret: tuple[LinksysVelopUpdateCoordinatorEntity, ...] = ()

        return ret

    def _init_node_entities() -> tuple[LinksysVelopUpdateCoordinatorEntity, ...]:
        """Describe the entities that target nodes."""

        current_node_ids = {
            str(node.unique_id)
            for node in config_entry.runtime_data.mesh.nodes
            if node.unique_id.value is not None
        }
        new_node_ids = current_node_ids - known_nodes
        known_nodes.update(new_node_ids)

        descriptions = tuple(
            entity
            for attr, entities in ENTITIES.items()
            if hasattr(NodeEntity, attr)
            for entity in entities
            if entity.target_type is EntityType.NODE
        )

        # Handle this here so that we have access to config_entry.
        if hasattr(NodeEntity, "firmware"):
            descriptions += (
                LinksysVelopUpdateEntityDescription(
                    device_class=UpdateDeviceClass.FIRMWARE,
                    key="",
                    name="Update",
                    pic_fn=lambda node: (
                        f"{prefix.rstrip('/').strip()}/"
                        f"{cast(NodeEntity, node).model.value}.png"
                        if (prefix := config_entry.options.get(CONF_NODE_IMAGES))
                        not in (None, "")
                        else None
                    ),
                    target_type=EntityType.NODE,
                    translation_key="update",
                ),
            )

        coordinator = cast(
            LinksysVelopDataUpdateCoordinatorMultiUse,
            config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH),
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

    def _remove_stale_entities() -> None:
        """Remove entities that are no longer required."""

        if hasattr(NodeEntity, "firmware"):
            return

        entities_to_remove = {
            f"{node.unique_id}::{ENTITY_DOMAIN}::update"
            for node in config_entry.runtime_data.mesh.nodes
        }

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

        entities_to_add = _init_node_entities()

        if entities_to_add:
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


class LinksysVelopUpdateMultiUseEntity(LinksysVelopMultiUseEntity, UpdateEntity):
    """Linksys Velop update entity."""

    entity_description: LinksysVelopUpdateEntityDescription
    _entity_domain: str = ENTITY_DOMAIN

    @property
    @override
    def auto_update(self) -> bool:

        _mesh: Mesh | None = self.coordinator.data.get(CoordinatorTimers.MESH)
        ret: bool = False
        if _mesh is not None:
            ret = _mesh.firmware_update_setting != FirmwareUpdatePolicy.MANUAL

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
