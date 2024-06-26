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
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyvelop.const import DEF_EMPTY_NAME
from pyvelop.device import Device
from pyvelop.mesh import Mesh

from . import LinksysVelopMeshEntity
from .const import (
    CONF_COORDINATOR,
    CONF_SELECT_TEMP_UI_DEVICE,
    DEF_UI_DEVICE_ID,
    DOMAIN,
    SIGNAL_UPDATE_PLACEHOLDER_UI_DEVICE,
)

# endregion

_LOGGER = logging.getLogger(__name__)


def _get_device_details(mesh: Mesh, device_name: str) -> dict | None:
    """Get the properties for a device with the given name."""
    if not device_name:
        return None

    # -- return all properties from the Device object for use --#
    required_properties: List[str] = [
        prop for prop in dir(Device) if not prop.startswith("_")
    ]

    ret = None
    dev: Device
    match_on: str = (
        device_name
        if not device_name.startswith(f"{DEF_EMPTY_NAME} (")
        else device_name.split("(")[1].strip(")")
    )
    for dev in mesh.devices:
        match_against: List[str] = [dev.name.lower(), dev.unique_id]
        if device_name.startswith(f"{DEF_EMPTY_NAME} (") and dev.status:
            match_against.append(dev.connected_adapters[0].get("ip"))
        if device_name and (match_on.lower() in match_against):
            ret = {p: getattr(dev, p, None) or None for p in required_properties}
            break

    return ret


# region #-- select entity descriptions --#
@dataclasses.dataclass(frozen=True)
class AdditionalSelectDescription:
    """Represent the additional properties for the select description."""

    custom_options: Callable[[Any], list[str]] | list[str] = dataclasses.field(
        default_factory=list
    )
    extra_attributes_args: dict | None = dataclasses.field(default_factory=dict)
    extra_attributes: Callable[[Any], dict] | None = None


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
            additional_description=AdditionalSelectDescription(
                custom_options=lambda m: (
                    [
                        (
                            device.name
                            if device.name != DEF_EMPTY_NAME
                            else f"{device.name} ({device.connected_adapters[0].get('ip') if device.status else device.unique_id})"
                        )
                        for device in m.devices
                    ]
                ),
                extra_attributes=_get_device_details,
            ),
            config_entry=config_entry,
            coordinator=coordinator,
            description=SelectEntityDescription(
                entity_registry_enabled_default=False,
                key="devices",
                name="Devices",
                translation_key="mesh_devices",
            ),
        )
    ]

    async_add_entities(selects)


class LinksysVelopMeshSelect(LinksysVelopMeshEntity, SelectEntity, ABC):
    """Representation for a select entity in the Mesh."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: SelectEntityDescription,
        additional_description: AdditionalSelectDescription | None = None,
    ) -> None:
        """Initialise."""
        self._additional_description: AdditionalSelectDescription | None = (
            additional_description
        )
        self._attr_current_option = None
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self.entity_domain = ENTITY_DOMAIN

        super().__init__(
            config_entry=config_entry, coordinator=coordinator, description=description
        )

    async def _reset_option(self, device_id: str) -> None:
        """Reset the select entity."""
        if device_id == DEF_UI_DEVICE_ID:
            self._attr_current_option = None
            self.async_schedule_update_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Select the option."""
        self._attr_current_option = option
        if self._config.options.get(CONF_SELECT_TEMP_UI_DEVICE):
            device_details = _get_device_details(mesh=self._mesh, device_name=option)
            if device_details is not None:
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_UPDATE_PLACEHOLDER_UI_DEVICE,
                    device_details.get("unique_id"),
                )

    async def async_added_to_hass(self) -> None:
        """Register for callbacks and set initial value."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=SIGNAL_UPDATE_PLACEHOLDER_UI_DEVICE,
                target=self._reset_option,
            )
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Additional attributes."""
        if (
            self._additional_description.extra_attributes
            and isinstance(self._additional_description.extra_attributes, Callable)
            and not self._config.options.get(CONF_SELECT_TEMP_UI_DEVICE)
        ):
            ea_args: dict
            if self._additional_description.extra_attributes_args:
                ea_args = self._additional_description.extra_attributes_args.copy()
            else:
                ea_args = {}
            ea_args["mesh"] = self._mesh
            ea_args["device_name"] = self.current_option
            return self._additional_description.extra_attributes(**ea_args)

        return None

    @property
    def options(self) -> list[str]:
        """Build the options for the select."""
        if isinstance(self._additional_description.custom_options, Callable):
            return self._additional_description.custom_options(self._mesh)

        return (
            self._additional_description.custom_options
            or self.entity_description.options
        )
