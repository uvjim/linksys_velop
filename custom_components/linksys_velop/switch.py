"""Switch entities for Linksys Velop."""

# region #-- imports --#
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from homeassistant.components.switch import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LinksysVelopConfigEntry
from .entities import (
    EntityContext,
    EntityDetails,
    EntityType,
    LinksysVelopEntity,
    build_entities,
)

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass
class SwitchDetails(EntityDetails):
    description: SwitchEntityDescription
    off_func: str = field(kw_only=True)
    on_func: str = field(kw_only=True)


ENTITY_DETAILS: list[SwitchDetails] = [
    # region #-- mesh switches --#
    SwitchDetails(
        description=SwitchEntityDescription(
            entity_category=EntityCategory.CONFIG,
            key="guest_wifi_enabled",
            name="Guest Wi-Fi",
            translation_key="guest_wifi",
        ),
        entity_type=EntityType.MESH,
        esa_value_func=lambda m: {
            f"network {idx}": network
            for idx, network in enumerate(m.guest_wifi_details)
        },
        off_func="async_set_guest_wifi_state",
        on_func="async_set_guest_wifi_state",
    ),
    SwitchDetails(
        description=SwitchEntityDescription(
            entity_category=EntityCategory.CONFIG,
            key="homekit_enabled",
            name="HomeKit Integration",
            translation_key="homekit",
        ),
        entity_type=EntityType.MESH,
        off_func="async_set_homekit_state",
        on_func="async_set_homekit_state",
    ),
    SwitchDetails(
        description=SwitchEntityDescription(
            entity_category=EntityCategory.CONFIG,
            key="parental_control_enabled",
            name="Parental Control",
            translation_key="parental_control",
        ),
        entity_type=EntityType.MESH,
        esa_value_func=lambda m: (
            {
                "rules": {
                    device.name: device.parental_control_schedule
                    for device in m.devices
                    if device.parental_control_schedule
                }
            }
        ),
        off_func="async_set_parental_control_state",
        on_func="async_set_parental_control_state",
    ),
    SwitchDetails(
        description=SwitchEntityDescription(
            entity_category=EntityCategory.CONFIG,
            key="wps_state",
            name="WPS",
            translation_key="wps",
        ),
        entity_type=EntityType.MESH,
        off_func="async_set_wps_state",
        on_func="async_set_wps_state",
    ),
    # endregion
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize a switch."""

    entities_to_add: list[LinksysVelopSwitch] = []

    entities = build_entities(ENTITY_DETAILS, config_entry, ENTITY_DOMAIN)
    entities_to_add = [LinksysVelopSwitch(**entity) for entity in entities]

    if len(entities_to_add) > 0:
        async_add_entities(entities_to_add)


class LinksysVelopSwitch(LinksysVelopEntity, SwitchEntity):
    """Linksys Velop switch."""

    def __init__(
        self,
        context: EntityContext,
        config_entry: LinksysVelopConfigEntry,
        entity_details: SwitchDetails,
        entity_domain: str,
    ) -> None:
        """Initialise."""
        super().__init__(
            context,
            config_entry,
            entity_details,
            entity_domain,
        )

        self._off_func = entity_details.off_func
        self._on_func = entity_details.on_func

    async def async_turn_on(self, **kwargs: Any) -> None:
        """"""
        if (func := getattr(self.coordinator.data, self._on_func, None)) is not None:
            if isinstance(func, Callable):
                await func(True)
                await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """"""
        if (func := getattr(self.coordinator.data, self._on_func, None)) is not None:
            if isinstance(func, Callable):
                await func(False)
                await self.coordinator.async_refresh()

    @callback
    def _update_attr_value(self) -> None:
        """"""

        if self._context_data is None:
            self._attr_is_on = None
            return

        if self._entity_details.state_value_func is not None:
            self._attr_is_on = self._entity_details.state_value_func(self._context_data)
        elif self.entity_description.key:
            try:
                self._attr_is_on = getattr(
                    self._context_data, self.entity_description.key
                )
            except AttributeError:
                self._attr_is_on = None
        else:
            self._attr_is_on = None
