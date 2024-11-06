"""Select entities for Linksys Velop."""

# region #-- imports --#
import logging
from dataclasses import dataclass

from homeassistant.components.select import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.const import DEF_EMPTY_NAME
from pyvelop.mesh import Mesh

from .const import SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE
from .entities import EntityDetails, EntityType, LinksysVelopEntity, build_entities
from .types import CoordinatorTypes, LinksysVelopConfigEntry

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass
class SelectDetails(EntityDetails):
    """Representation of the details that make up the entity."""

    description: SelectEntityDescription


ENTITY_DETAILS: list[SelectDetails] = []


def _build_options(mesh: Mesh) -> list[str]:
    """Create the available options for the select entity."""

    return [
        (
            d.name
            if d.name != DEF_EMPTY_NAME
            else f"{d.name} ({next(iter(d.connected_adapters), {}).get('ip') if d.status else d.unique_id})"
        )
        for d in mesh.devices
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize a sensor."""

    entities_to_add: list[LinksysVelopSelect] = []

    entities = build_entities(ENTITY_DETAILS, config_entry, ENTITY_DOMAIN)
    entities_to_add = [LinksysVelopSelect(**entity) for entity in entities]
    entities_to_add.extend(
        [
            LinksysVelopSelectPlaceholderEntity(**entity)
            for entity in build_entities(
                [
                    SelectDetails(
                        description=SelectEntityDescription(
                            entity_category=EntityCategory.CONFIG,
                            key="",
                            name="Devices",
                            options=_build_options(
                                config_entry.runtime_data.coordinators.get(
                                    CoordinatorTypes.MESH
                                ).data
                            ),
                            translation_key="mesh_devices",
                        ),
                        entity_type=EntityType.PLACEHOLDER_DEVICE,
                    )
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        ]
    )

    if len(entities_to_add) > 0:
        async_add_entities(entities_to_add)


class LinksysVelopSelect(LinksysVelopEntity, SelectEntity):
    """Linksys Velop sensor."""

    _attr_current_option: str | None = None


class LinksysVelopSelectPlaceholderEntity(LinksysVelopSelect):
    """Linksys Velop sensor."""

    async def async_select_option(self, option: str) -> None:
        """Update the values once a device had been selected."""

        self._attr_current_option = option
        async_dispatcher_send(self.hass, SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE, option)
        await self._config_entry.runtime_data.coordinators.get(
            CoordinatorTypes.MESH
        ).async_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._attr_options = _build_options(
            self._config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH).data
        )
        if self.current_option not in self._attr_options:
            self._attr_current_option = None
            async_dispatcher_send(
                self.hass,
                SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE,
                self._attr_current_option,
            )

        super()._handle_coordinator_update()
