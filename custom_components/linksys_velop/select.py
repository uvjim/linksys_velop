"""Select entities"""

# region #-- imports --#
from __future__ import annotations

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

from homeassistant.components.select import (
    SelectEntity,
    SelectEntityDescription,
    DOMAIN as ENTITY_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify
from pyvelop.device import Device
from pyvelop.mesh import Mesh

from . import LinksysVelopMeshEntity
from .const import (
    CONF_COORDINATOR,
    DOMAIN,
    ENTITY_SLUG,
)
# endregion

_LOGGER = logging.getLogger(__name__)


def _get_device_details(mesh: Mesh, device_name: str) -> Optional[dict]:
    """"""

    required_properties = [
        "connected_adapters",
        "description",
        "manufacturer",
        "model",
        "name",
        "operating_system",
        "parent_name",
        "parental_control_schedule",
        "serial",
        "status",
        "unique_id",
    ]

    ret = None
    d: Device
    device: List[Device] = [d for d in mesh.devices if device_name and d.name.lower() == device_name.lower()]
    if device:
        ret = {
            p: getattr(device[0], p, None)
            for p in required_properties
        }

    return ret


# region #-- select entity descriptions --#
@dataclasses.dataclass
class OptionalLinksysVelopDescription:
    """Represent the optional attributes of the select description."""

    extra_attributes_args: Optional[dict] = dataclasses.field(default_factory=dict)
    extra_attributes: Optional[Callable[[Any], dict]] = None


@dataclasses.dataclass
class RequiredLinksysVelopDescription:
    """Represent the required attributes of the select description."""

    options: Callable[[Any], list[str]] | list[str]


@dataclasses.dataclass
class LinksysVelopSelectDescription(
    OptionalLinksysVelopDescription,
    SelectEntityDescription,
    RequiredLinksysVelopDescription
):
    """Describes select entity"""
# endregion


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """"""

    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]

    selects: List[LinksysVelopMeshSelect] = [
        LinksysVelopMeshSelect(
            config_entry=config_entry,
            coordinator=coordinator,
            description=LinksysVelopSelectDescription(
                extra_attributes=_get_device_details,
                key="devices",
                name="Devices",
                options=lambda m: (
                    [
                        device.name
                        for device in m.devices
                    ]
                )
            )
        )
    ]

    async_add_entities(selects)


class LinksysVelopMeshSelect(LinksysVelopMeshEntity, SelectEntity, ABC):
    """Representation for a button in the Mesh"""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: LinksysVelopSelectDescription
    ) -> None:
        """Constructor"""

        super().__init__(config_entry=config_entry, coordinator=coordinator)

        self.entity_description: LinksysVelopSelectDescription = description

        self._attr_current_option = None
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = False
        self._attr_name = f"{ENTITY_SLUG} Mesh: {self.entity_description.name}"
        self._attr_unique_id = f"{config_entry.entry_id}::" \
                               f"{ENTITY_DOMAIN.lower()}::" \
                               f"{slugify(self.entity_description.name)}"

    async def async_select_option(self, option: str) -> None:
        """Select the option"""

        self._attr_current_option = option
        await self.async_update_ha_state()

    @property
    def extra_state_attributes(self) -> Optional[Mapping[str, Any]]:
        """Additional attributes"""

        if (
            self.entity_description.extra_attributes
            and isinstance(self.entity_description.extra_attributes, Callable)
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
        """Build the options for the select"""

        if isinstance(self.entity_description.options, Callable):
            return self.entity_description.options(self._mesh)
        else:
            return self.entity_description.options
