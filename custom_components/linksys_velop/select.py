"""Select entities."""

# region #-- imports --#
from __future__ import annotations

import dataclasses
import logging
from abc import ABC
from typing import Any, Callable, List, Mapping

from homeassistant.components.select import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyvelop.device import Device
from pyvelop.mesh import Mesh

from . import LinksysVelopMeshEntity
from .const import CONF_COORDINATOR, DOMAIN

# endregion

_LOGGER = logging.getLogger(__name__)


def _get_device_details(mesh: Mesh, device_name: str) -> dict | None:
    """Get the properties for a device with the given name."""
    # -- return all properties from the Device object for use --#
    required_properties: List[str] = [
        prop for prop in dir(Device) if not prop.startswith("_")
    ]

    ret = None
    dev: Device
    device: List[Device] = [
        dev
        for dev in mesh.devices
        if device_name and dev.name.lower() == device_name.lower()
    ]
    if device:
        ret = {p: getattr(device[0], p, None) or None for p in required_properties}

    return ret


# region #-- select entity descriptions --#
@dataclasses.dataclass
class OptionalLinksysVelopDescription:
    """Represent the optional attributes of the select description."""

    custom_options: Callable[[Any], list[str]] | list[str] = dataclasses.field(
        default_factory=list
    )
    extra_attributes_args: dict | None = dataclasses.field(default_factory=dict)
    extra_attributes: Callable[[Any], dict] | None = None


@dataclasses.dataclass
class RequiredLinksysVelopDescription:
    """Represent the required attributes of the select description."""


@dataclasses.dataclass
class LinksysVelopSelectDescription(
    OptionalLinksysVelopDescription,
    SelectEntityDescription,
    RequiredLinksysVelopDescription,
):
    """Describes select entity."""


# endregion


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]

    selects: List[LinksysVelopMeshSelect] = [
        LinksysVelopMeshSelect(
            config_entry=config_entry,
            coordinator=coordinator,
            description=LinksysVelopSelectDescription(
                custom_options=lambda m: ([device.name for device in m.devices]),
                extra_attributes=_get_device_details,
                key="devices",
                name="Devices",
            ),
        )
    ]

    async_add_entities(selects)


class LinksysVelopMeshSelect(LinksysVelopMeshEntity, SelectEntity, ABC):
    """Representation for a select entity in the Mesh."""

    entity_description: LinksysVelopSelectDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: LinksysVelopSelectDescription,
    ) -> None:
        """Initialise."""
        self._attr_current_option = None
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = False
        self.entity_domain = ENTITY_DOMAIN

        super().__init__(
            config_entry=config_entry, coordinator=coordinator, description=description
        )

    async def async_select_option(self, option: str) -> None:
        """Select the option."""
        self._attr_current_option = option
        await self.async_update_ha_state()

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Additional attributes."""
        if self.entity_description.extra_attributes and isinstance(
            self.entity_description.extra_attributes, Callable
        ):
            ea_args: dict
            if self.entity_description.extra_attributes_args:
                ea_args = self.entity_description.extra_attributes_args.copy()
            else:
                ea_args = {}
            ea_args["mesh"] = self._mesh
            ea_args["device_name"] = self.current_option
            return self.entity_description.extra_attributes(**ea_args)

    @property
    def options(self) -> list[str]:
        """Build the options for the select."""
        if isinstance(self.entity_description.custom_options, Callable):
            return self.entity_description.custom_options(self._mesh)

        return self.entity_description.custom_options or self.entity_description.options
