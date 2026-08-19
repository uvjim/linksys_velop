"""Update entities for Linksys Velop."""

# region #-- imports --#
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast, override

from homeassistant.components.update import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.action_registry import Actions
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

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LinksysVelopUpdateEntityDescription(
    LinksysVelopEntityDescription, UpdateEntityDescription
):
    """Describes Velop update entity."""

    pic_fn: Callable[..., str | None] | None = None


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

        if len(entities_to_add) > 0:
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
        ret: tuple[LinksysVelopUpdateCoordinatorEntity, ...] = ()
        ret_temp: list[LinksysVelopUpdateCoordinatorEntity] = []
        current_nodes: set[str] = {
            str(cast(NodeEntity, n).unique_id)
            for n in config_entry.runtime_data.mesh.nodes
            if cast(NodeEntity, n).unique_id.value is not None
        }
        new_nodes: set[str] = current_nodes - known_nodes

        if new_nodes:
            known_nodes.update(new_nodes)
            for node in new_nodes:
                context: LinksysVelopEntityContext = LinksysVelopEntityContext(
                    unique_id=node
                )
                mesh_entities: list[LinksysVelopUpdateEntityDescription] = []

                if (
                    Actions.GET_UPDATE_FIRMWARE_STATE.key
                    in config_entry.runtime_data.mesh.capabilities
                ):
                    mesh_entities.append(
                        LinksysVelopUpdateEntityDescription(
                            device_class=UpdateDeviceClass.FIRMWARE,
                            key="",
                            name="Update",
                            pic_fn=lambda n: (
                                f"{prefix.rstrip('/').strip()}/{cast(NodeEntity, n).model.value}.png"
                                if (
                                    prefix := config_entry.options.get(CONF_NODE_IMAGES)
                                )
                                not in (None, "")
                                else None
                            ),
                            target_type=EntityType.NODE,
                            translation_key="update",
                        ),
                    )

                ret_temp.extend(
                    [
                        LinksysVelopUpdateMultiUseEntity(
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

        entities_to_remove: set[str] = set()

        # region #-- remove unnecessary node entities --#
        for node in config_entry.runtime_data.mesh.nodes:
            if (
                Actions.GET_UPDATE_FIRMWARE_STATE.key
                not in config_entry.runtime_data.mesh.capabilities
            ):
                entities_to_remove.add(f"{node.unique_id}::{ENTITY_DOMAIN}::update")
        # endregion

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

        entities_to_add = _init_node_entities()

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
