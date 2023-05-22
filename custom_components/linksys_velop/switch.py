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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyvelop.device import Device, ParentalControl

from . import LinksysVelopDeviceEntity, LinksysVelopMeshEntity, entity_cleanup
from .const import (
    CONF_COORDINATOR,
    CONF_DEVICE_UI,
    DEF_UI_DEVICE_ID,
    DOMAIN,
    SIGNAL_UPDATE_PLACEHOLDER_UI_DEVICE,
)

# endregion

_LOGGER = logging.getLogger(__name__)


# region #-- switch entity descriptions --#
@dataclasses.dataclass
class OptionalLinksysVelopDescription:
    """Represent the optional attributes of the switch description."""

    extra_attributes: Callable | None = None
    icon_off: str | None = None
    icon_on: str | None = None
    state_value: Callable | None = None
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


def _device_internet_access_state(device_details: Device) -> bool | None:
    """Get the state of interent access for the device."""
    if device_details.unique_id == DEF_UI_DEVICE_ID:
        return None

    blocked_internet_access: dict[
        str, str
    ] = device_details.parental_control_schedule.get("blocked_internet_access", {})

    return all(hrs == "00:00-00:00" for hrs in blocked_internet_access.values())


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switches from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
    switches: List[LinksysVelopMeshSwitch] = []
    switches_to_remove: List[LinksysVelopMeshSwitch] = []

    # region #-- Device switches --#
    device_switch_descriptions: tuple[LinksysVelopSwitchDescription, ...]
    for device_id in config_entry.options.get(CONF_DEVICE_UI, []):
        device_switch_descriptions = (
            LinksysVelopSwitchDescription(
                icon_off="mdi:web-off",
                icon_on="mdi:web",
                key="",
                name="Internet Access",
                state_value=_device_internet_access_state,
                translation_key="internet_access",
                turn_off="async_set_parental_control_rules",
                turn_off_args=lambda d: {
                    "device_id": d.unique_id,
                    "rules": dict(
                        map(
                            lambda weekday, readable_schedule: (
                                weekday.name,
                                readable_schedule,
                            ),
                            ParentalControl.WEEKDAYS,
                            ("00:00-00:00",) * len(ParentalControl.WEEKDAYS),
                        )
                    ),
                },
                turn_on="async_set_parental_control_rules",
                turn_on_args=lambda d: {"device_id": d.unique_id, "rules": {}},
            ),
        )

        for switch_description in device_switch_descriptions:
            switches.append(
                LinksysVelopDeviceSwitch(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=switch_description,
                    device_id=device_id,
                )
            )
    # endregion

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
            translation_key="guest_wifi",
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
            key="homekit_enabled",
            name="HomeKit Integration",
            translation_key="homekit",
            turn_off="async_set_homekit_state",
            turn_off_args={
                "state": False,
            },
            turn_on="async_set_homekit_state",
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
            translation_key="parental_control",
            turn_off="async_set_parental_control_state",
            turn_off_args={
                "state": False,
            },
            turn_on="async_set_parental_control_state",
            turn_on_args={
                "state": True,
            },
        ),
        LinksysVelopSwitchDescription(
            key="wps_state",
            name="WPS",
            translation_key="wps",
            turn_off="async_set_wps_state",
            turn_off_args={
                "state": False,
            },
            turn_on="async_set_wps_state",
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


class LinksysVelopDeviceSwitch(LinksysVelopDeviceEntity, SwitchEntity, ABC):
    """Representation of a device switch."""

    entity_description: LinksysVelopSwitchDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: LinksysVelopSwitchDescription,
        device_id: str,
    ) -> None:
        """Initialise."""
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_entity_category = EntityCategory.CONFIG
        self._value: bool | None = None
        self.entity_domain = ENTITY_DOMAIN

        super().__init__(
            config_entry=config_entry,
            coordinator=coordinator,
            description=description,
            device_id=device_id,
        )

    def _get_value(self, device_id: str | None = None) -> bool | None:
        """Get the current value of the switch."""
        if device_id is not None:
            self._update_device_id(device_id=device_id)

        if isinstance(self.entity_description.state_value, Callable):
            self._value = self.entity_description.state_value(self._device)
        else:
            self._value = getattr(self._device, self.entity_description.key, None)

        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        super()._handle_coordinator_update()
        self._get_value()

    async def async_added_to_hass(self) -> None:
        """Register for callbacks."""
        await super().async_added_to_hass()
        if self.unique_id.startswith(DEF_UI_DEVICE_ID):
            self.async_on_remove(
                async_dispatcher_connect(
                    hass=self.hass,
                    signal=SIGNAL_UPDATE_PLACEHOLDER_UI_DEVICE,
                    target=self._get_value,
                )
            )
        self._get_value()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        action = getattr(self._mesh, self.entity_description.turn_off)
        if isinstance(self.entity_description.turn_off_args, Callable):
            action_args = self.entity_description.turn_off_args(self._device)
        else:
            action_args = self.entity_description.turn_off_args
        if isinstance(action, Callable):
            await action(**action_args)
            self._value = False
            self.async_schedule_update_ha_state()
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        action = getattr(self._mesh, self.entity_description.turn_on)
        if isinstance(self.entity_description.turn_on_args, Callable):
            action_args = self.entity_description.turn_on_args(self._device)
        else:
            action_args = self.entity_description.turn_on_args
        if isinstance(action, Callable):
            await action(**action_args)
            self._value = True
            self.async_schedule_update_ha_state()
            await self.coordinator.async_request_refresh()

    @property
    def icon(self) -> str | None:
        """Get the icon."""
        if self.entity_description.icon_on and self.is_on:
            return self.entity_description.icon_on

        return self.entity_description.icon_off

    @property
    def is_on(self) -> bool | None:
        """Get the value of the switch."""
        return self._value


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
            self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        action = getattr(self._mesh, self.entity_description.turn_on)
        if isinstance(action, Callable):
            await action(**self.entity_description.turn_on_args)
            self._value = True
            self.async_schedule_update_ha_state()

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
