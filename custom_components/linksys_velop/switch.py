"""Switches for the mesh."""

# region #-- imports --#
from __future__ import annotations

import dataclasses
import logging
from abc import ABC
from typing import Any, Callable, List

from homeassistant.components.switch import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import LinksysVelopMeshEntity, entity_cleanup
from .const import CONF_COORDINATOR, DOMAIN

# endregion

_LOGGER = logging.getLogger(__name__)


# region #-- switch entity descriptions --#
@dataclasses.dataclass
class OptionalLinksysVelopDescription:
    """Represent the optional attributes of the switch description."""

    extra_attributes: Callable | None = None
    icon_off: str | None = None
    icon_on: str | None = None
    turn_off_args: dict | None = dict
    turn_on_args: dict | None = dict


@dataclasses.dataclass
class RequiredLinksysVelopDescription:
    """Represent the required attributes of the switch description."""

    turn_off: str
    turn_on: str


@dataclasses.dataclass
class LinksysVelopSwitchDescription(
    OptionalLinksysVelopDescription,
    SwitchEntityDescription,
    RequiredLinksysVelopDescription,
):
    """Describes switch entity."""


# endregion


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switches from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
    switches: List[LinksysVelopMeshSwitch] = []
    switches_to_remove: List[LinksysVelopMeshSwitch] = []

    # region #-- Mesh switches --#
    mesh_switch_descriptions: tuple[LinksysVelopSwitchDescription, ...] = (
        LinksysVelopSwitchDescription(
            extra_attributes=lambda m: {
                f"network {idx}": network
                for idx, network in enumerate(m.guest_wifi_details)
            },
            icon_off="hass:wifi-off",
            icon_on="hass:wifi",
            key="guest_wifi_enabled",
            name="Guest Wi-Fi",
            turn_off="async_set_guest_wifi_state",
            turn_off_args={
                "state": False,
            },
            turn_on="async_set_guest_wifi_state",
            turn_on_args={
                "state": True,
            },
        ),
        LinksysVelopSwitchDescription(
            extra_attributes=lambda m: (
                {
                    "rules": {
                        device.name: device.parental_control_schedule
                        for device in m.devices
                        if device.parental_control_schedule
                    }
                }
            ),
            icon_off="hass:account-off",
            icon_on="hass:account",
            key="parental_control_enabled",
            name="Parental Control",
            turn_off="async_set_parental_control_state",
            turn_off_args={
                "state": False,
            },
            turn_on="async_set_parental_control_state",
            turn_on_args={
                "state": True,
            },
        ),
    )

    for switch_description in mesh_switch_descriptions:
        switches.append(
            LinksysVelopMeshSwitch(
                config_entry=config_entry,
                coordinator=coordinator,
                description=switch_description,
            )
        )
    # endregion

    async_add_entities(switches)

    if switches_to_remove:
        entity_cleanup(
            config_entry=config_entry, entities=switches_to_remove, hass=hass
        )


class LinksysVelopMeshSwitch(LinksysVelopMeshEntity, SwitchEntity, ABC):
    """Representation of Mesh switch."""

    entity_description: LinksysVelopSwitchDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: LinksysVelopSwitchDescription,
    ) -> None:
        """Initialise."""
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_entity_category = EntityCategory.CONFIG
        self.entity_domain = ENTITY_DOMAIN

        super().__init__(
            config_entry=config_entry, coordinator=coordinator, description=description
        )

        self._value = self._get_value()

    def _get_value(self) -> bool:
        """Get the value from the coordinator."""
        return getattr(self._mesh, self.entity_description.key, False)

    def _handle_coordinator_update(self) -> None:
        """Update the switch value information when the coordinator updates."""
        self._value = self._get_value()
        super()._handle_coordinator_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        action = getattr(self._mesh, self.entity_description.turn_off)
        if isinstance(action, Callable):
            await action(**self.entity_description.turn_off_args)
            self._value = False
            await self.async_update_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        action = getattr(self._mesh, self.entity_description.turn_on)
        if isinstance(action, Callable):
            await action(**self.entity_description.turn_on_args)
            self._value = True
            await self.async_update_ha_state()

    @property
    def icon(self) -> str | None:
        """Get the icon."""
        if self.entity_description.icon_on and self.is_on:
            return self.entity_description.icon_on

        return self.entity_description.icon_off

    @property
    def is_on(self) -> bool | None:
        """Get the current state of the switch."""
        return self._value
