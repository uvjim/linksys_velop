"""Switches for the mesh"""
# region #-- imports --#
# TODO: Remove the try/except block when setting the minimum HASS version to 2021.12
try:
    from homeassistant.helpers.entity import EntityCategory
except ImportError:
    EntityCategory = None
    # TODO: Remove the try/except block when setting the minimum HASS version to 2021.11
    try:
        from homeassistant.const import (
            ENTITY_CATEGORY_CONFIG,
            ENTITY_CATEGORY_DIAGNOSTIC,
        )
    except ImportError:
        ENTITY_CATEGORY_CONFIG: str = "config"
        ENTITY_CATEGORY_DIAGNOSTIC: str = "diagnostic"

# TODO: Fix up the try/except block when setting the minimum HASS version to 2021.12
# HASS 2021.12 introduces StrEnum for DEVICE_CLASS_* constants
try:
    from homeassistant.components.switch import SwitchDeviceClass
    DEVICE_CLASS_SWITCH = SwitchDeviceClass.SWITCH
except ImportError:
    SwitchDeviceClass = None
    from homeassistant.components.switch import DEVICE_CLASS_SWITCH

import dataclasses
import logging
from abc import ABC
from typing import (
    Any,
    Callable,
    List,
    Mapping,
    Optional,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.switch import (
    DOMAIN as ENTITY_DOMAIN,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify

from pyvelop.mesh import Mesh
from pyvelop.device import Device

from . import (
    entity_cleanup,
    LinksysVelopMeshEntity
)
from .const import (
    CONF_COORDINATOR,
    DOMAIN,
    ENTITY_SLUG,
)
# endregion

_LOGGER = logging.getLogger(__name__)


# region #-- switch entity descriptions --#
@dataclasses.dataclass
class OptionalLinksysVelopDescription:
    """Represent the optional attributes of the switch description."""

    extra_attributes: Optional[Callable] = None
    icon_off: Optional[str] = None
    icon_on: Optional[str] = None
    turn_off_args: Optional[dict] = dict
    turn_on_args: Optional[dict] = dict


@dataclasses.dataclass
class RequiredLinksysVelopDescription:
    """Represent the required attributes of the switch description."""

    turn_off: str
    turn_on: str


@dataclasses.dataclass
class LinksysVelopSwitchDescription(
    OptionalLinksysVelopDescription,
    SwitchEntityDescription,
    RequiredLinksysVelopDescription
):
    """Describes switch entity"""
# endregion


SWITCH_DESCRIPTIONS: tuple[LinksysVelopSwitchDescription, ...] = (
    LinksysVelopSwitchDescription(
        extra_attributes=lambda m: {f"network {idx}": network for idx, network in enumerate(m.guest_wifi_details)},
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
        }
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
        }
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the switches from a config entry"""

    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]

    switches: List[LinksysVelopMeshSwitch] = [
        LinksysVelopMeshSwitch(
            config_entry=config_entry,
            coordinator=coordinator,
            description=switch_description,
        )
        for switch_description in SWITCH_DESCRIPTIONS
    ]

    async_add_entities(switches)

    switches_to_remove: List = []
    if switches_to_remove:
        entity_cleanup(config_entry=config_entry, entities=switches_to_remove, hass=hass)


class LinksysVelopMeshSwitch(LinksysVelopMeshEntity, SwitchEntity, ABC):
    """"""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: LinksysVelopSwitchDescription
    ) -> None:
        """Constructor"""

        super().__init__(config_entry=config_entry, coordinator=coordinator)

        self._attr_device_class = DEVICE_CLASS_SWITCH
        self._attr_entity_category = ENTITY_CATEGORY_CONFIG if EntityCategory is None else EntityCategory.CONFIG

        self.entity_description: LinksysVelopSwitchDescription = description

        self._attr_name = f"{ENTITY_SLUG} Mesh: {self.entity_description.name}"
        self._attr_unique_id = f"{config_entry.entry_id}::" \
                               f"{ENTITY_DOMAIN.lower()}::" \
                               f"{slugify(self.entity_description.name)}"

        self._value = self._get_value()

    def _get_value(self) -> bool:
        """Get the value from the coordinator"""

        return getattr(self._mesh, self.entity_description.key, False)

    def _handle_coordinator_update(self) -> None:
        """Update the switch value information when the coordinator updates"""

        self._value = self._get_value()
        super()._handle_coordinator_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off"""

        action = getattr(self._mesh, self.entity_description.turn_off)
        if isinstance(action, Callable):
            await action(**self.entity_description.turn_off_args)
            self._value = False
            await self.async_update_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on"""

        action = getattr(self._mesh, self.entity_description.turn_on)
        if isinstance(action, Callable):
            await action(**self.entity_description.turn_on_args)
            self._value = True
            await self.async_update_ha_state()

    @property
    def extra_state_attributes(self) -> Optional[Mapping[str, Any]]:
        """"""

        if (
            self.entity_description.extra_attributes
            and isinstance(self.entity_description.extra_attributes, Callable)
        ):
            return self.entity_description.extra_attributes(self._mesh)

    @property
    def icon(self) -> Optional[str]:
        """Get the icon"""

        if self.entity_description.icon_on and self.is_on:
            return self.entity_description.icon_on
        elif self.entity_description.icon_off and not self.is_on:
            return self.entity_description.icon_off

    @property
    def is_on(self) -> Optional[bool]:
        """Get the current state of the switch"""

        return self._value
