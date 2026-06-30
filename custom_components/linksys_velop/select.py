"""Select entities for Linksys Velop."""

# region #-- imports --#
import logging
from dataclasses import dataclass
from typing import cast

from homeassistant.components.select import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.const import DEF_EMPTY_NAME, MeshCapability, ScheduledRebootInterval
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


def _build_options(mesh: Mesh) -> list[str]:
    """Create the available options for the select entity."""

    return [
        (
            d.name
            if d.name != DEF_EMPTY_NAME
            else f"{d.name} ({next(iter(d.adapter_info), {}).get('ip') if d.status else d.unique_id})"
        )
        for d in mesh.devices
    ]


def _build_scheduled_reboot_options() -> list[str]:
    """Build the options available for the scheduled reboot interval."""
    ret: list[str] = ["off"]

    for opt in ScheduledRebootInterval:
        ret.append(opt.value.lower())

    return ret


ENTITY_DETAILS: list[SelectDetails] = []


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize a sensor."""

    entities_to_add: list[LinksysVelopSelect] = []

    mesh: Mesh = config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH).data
    entities = build_entities(ENTITY_DETAILS, config_entry, ENTITY_DOMAIN)
    entities_to_add = [LinksysVelopSelect(**entity) for entity in entities]

    if MeshCapability.GET_SCHEDULED_REBOOT_SETTINGS in mesh.capabilities:
        entities_to_add.extend(
            [
                LinksysVelopSelectScheduledReboot(**entity)
                for entity in build_entities(
                    [
                        SelectDetails(
                            description=SelectEntityDescription(
                                entity_category=EntityCategory.CONFIG,
                                key="",
                                name="Scheduled Reboot",
                                options=_build_scheduled_reboot_options(),
                                translation_key="mesh_scheduled_reboot",
                            ),
                            entity_type=EntityType.MESH,
                        )
                    ],
                    config_entry,
                    ENTITY_DOMAIN,
                )
            ]
        )

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


class LinksysVelopSelectScheduledReboot(LinksysVelopSelect):
    """Linksys Velop select entity for scheduled reboot."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the scheduled reboot select entity."""

        super().__init__(*args, **kwargs)
        self._update_attr_value()

    def _update_attr_value(self) -> None:
        """Update the selected option for the entity."""

        mesh: Mesh = cast(Mesh, self._context_data)
        if mesh.scheduled_reboot_enabled:
            self._attr_current_option = (
                mesh.scheduled_reboot_interval.value.lower()
                if mesh.scheduled_reboot_interval is not None
                else None
            )
        else:
            self._attr_current_option = "off"

    async def async_select_option(self, option: str) -> None:
        """React to the option being changed."""

        mesh: Mesh = cast(Mesh, self._context_data)
        self._attr_current_option = option
        if option == "off":
            await mesh.async_set_scheduled_reboot_state(False)
        else:
            await mesh.async_set_scheduled_reboot_interval(
                ScheduledRebootInterval(option.title())
            )
        await self.coordinator.async_refresh()
