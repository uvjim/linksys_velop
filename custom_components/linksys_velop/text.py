"""Text entities for Linksys Velop."""

# region #-- imports --#
import logging
from dataclasses import dataclass
from typing import cast, override

from homeassistant.components.text import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.mesh_attribute import MeshAttribute
from pyvelop.mesh_entity import DeviceEntity

from .const import (
    CONF_SELECT_TEMP_UI_DEVICE,
    CONF_UI_DEVICES,
    DEF_SELECT_TEMP_UI_DEVICE,
)
from .coordinator import (
    CoordinatorTimers,
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
class LinksysVelopTextEntityDescription(
    LinksysVelopEntityDescription, TextEntityDescription
):
    """Describes Velop text entity."""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialise a text entity."""

    known_nodes: set[str] = set()

    def _create_entities() -> None:
        """Create the mesh and device entities."""

        entities_to_add: tuple[LinksysVelopTextCoordinatorEntity, ...] = (
            _init_device_entities() + _init_mesh_entities()
        )

        if len(entities_to_add) > 0:
            async_add_entities(entities_to_add)

    def _init_device_entities() -> tuple[LinksysVelopTextCoordinatorEntity, ...]:
        """Describe the entities that target devices."""
        ret: tuple[LinksysVelopTextCoordinatorEntity, ...] = ()
        ret_temp: list[LinksysVelopTextCoordinatorEntity] = []

        for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
            context: LinksysVelopEntityContext = LinksysVelopEntityContext(
                unique_id=ui_device
            )
            mesh_entities: list[LinksysVelopTextEntityDescription] = []
            mesh_entities.extend(
                [
                    LinksysVelopTextEntityDescription(
                        entity_category=EntityCategory.CONFIG,
                        key="name",
                        name="Name",
                        target_type=EntityType.DEVICE,
                        translation_key="name",
                    ),
                ]
            )

            ret_temp.extend(
                [
                    LinksysVelopTextMultiUseEntity(
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

    def _init_mesh_entities() -> tuple[LinksysVelopTextCoordinatorEntity, ...]:
        """Describe the entities that target the mesh."""
        ret: tuple[LinksysVelopTextCoordinatorEntity, ...] = ()

        return ret

    def _init_node_entities() -> tuple[LinksysVelopTextCoordinatorEntity, ...]:
        """Describe the entities that target nodes."""

        ret: tuple[LinksysVelopTextCoordinatorEntity, ...] = ()

        return ret

    def _remove_stale_entities() -> None:
        """Remove entities is they are no longer required."""

        entities_to_remove: set[str] = set()

        # region #-- remove unnecessary device entities --#

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

        entities_to_add: tuple[LinksysVelopTextCoordinatorEntity, ...] = (
            _init_node_entities()
        )

        if len(entities_to_add) > 0:
            async_add_entities(entities_to_add)

    _remove_stale_entities()
    if config_entry.options.get(CONF_SELECT_TEMP_UI_DEVICE, DEF_SELECT_TEMP_UI_DEVICE):
        _create_entities()
        create_node_entities()

        config_entry.async_on_unload(
            cast(
                LinksysVelopDataUpdateCoordinatorMultiUse,
                config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH),
            ).add_listener_for_timer_type(CoordinatorTimers.MESH, create_node_entities)
        )


class LinksysVelopTextEntity(TextEntity):
    """Base class representing a text entity."""

    entity_description: LinksysVelopTextEntityDescription
    _entity_domain: str = ENTITY_DOMAIN
    _attr_native_min: int = 1


class LinksysVelopTextMultiUseEntity(
    LinksysVelopTextEntity, LinksysVelopMultiUseEntity
):
    """Linksys Velop text entity that uses multi use DataUpdateCoordinator."""

    @override
    async def async_set_value(self, value: str) -> None:

        device: DeviceEntity | None = self._get_target()
        if device is not None:
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
