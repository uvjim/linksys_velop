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

from . import LinksysVelopConfigEntry
from .const import CONF_NODE_IMAGES
from .entities import EntityDetails, EntityType, LinksysVelopEntity, build_entities

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass
class UpdateDetails(EntityDetails):
    description: UpdateEntityDescription


ENTITY_DETAILS: list[UpdateDetails] = [
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
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize an update entity."""

    entities_to_add: list[LinksysVelopUpdate] = []

    entities = build_entities(ENTITY_DETAILS, config_entry, ENTITY_DOMAIN)
    entities_to_add = [LinksysVelopUpdate(**entity) for entity in entities]

    if len(entities_to_add) > 0:
        async_add_entities(entities_to_add)


class LinksysVelopUpdate(LinksysVelopEntity, UpdateEntity):
    """Linksys Velop update entity."""

    @callback
    def _update_attr_value(self) -> None:
        """"""

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
