"""Update entities for Linksys Velop."""

# region #-- imports --#
import logging
from dataclasses import dataclass

from homeassistant.components.update import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.mesh import Mesh, MeshCapability

from . import LinksysVelopConfigEntry
from .const import CONF_NODE_IMAGES
from .entities import EntityDetails, EntityType, LinksysVelopEntity, build_entities
from .helpers import remove_velop_entity_from_registry
from .types import CoordinatorTypes

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass
class UpdateDetails(EntityDetails):
    """Representation of the details that make up the entity."""

    description: UpdateEntityDescription


ENTITY_DETAILS: list[UpdateDetails] = []


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize an update entity."""

    entities_to_add: list[LinksysVelopUpdate] = []
    entities_to_remove: list[str] = []
    entities = build_entities(ENTITY_DETAILS, config_entry, ENTITY_DOMAIN)

    # region #-- add conditional update entities --#
    mesh: Mesh = config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH).data
    if MeshCapability.GET_UPDATE_FIRMWARE_STATE in mesh.capabilities:
        entities.extend(
            build_entities(
                [
                    UpdateDetails(
                        description=UpdateEntityDescription(
                            device_class=UpdateDeviceClass.FIRMWARE,
                            key="",
                            name="Update",
                            translation_key="update",
                        ),
                        entity_type=EntityType.NODE,
                        pic_value_func=lambda n, c: (
                            f"{c.options.get(CONF_NODE_IMAGES, '').rstrip('/ ').strip()}/{n.model}.png"
                            if c.options.get(CONF_NODE_IMAGES, "")
                            else None
                        ),
                    )
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        for node in config_entry.runtime_data.coordinators.get(
            CoordinatorTypes.MESH
        ).data.nodes:
            entities_to_remove.append(f"{node.unique_id}::{ENTITY_DOMAIN}::update")
    # endregion

    entities_to_add = [LinksysVelopUpdate(**entity) for entity in entities]
    if len(entities_to_add) > 0:
        async_add_entities(entities_to_add)

    if len(entities_to_remove) > 0:
        for entity_unique_id in entities_to_remove:
            remove_velop_entity_from_registry(
                hass,
                config_entry.entry_id,
                entity_unique_id,
            )


class LinksysVelopUpdate(LinksysVelopEntity, UpdateEntity):
    """Linksys Velop update entity."""

    @callback
    def _update_attr_value(self) -> None:
        """Update the value of the entity."""

        if self._context_data is None:
            self._attr_auto_update = False
            self._attr_installed_version = None
            self._attr_latest_version = None
            return

        self._attr_auto_update = (
            self.coordinator.data.firmware_update_setting != "manual"
        )
        self._attr_installed_version = self._context_data.firmware.get("version", None)
        self._attr_latest_version = self._context_data.firmware.get(
            "latest_version", None
        )
