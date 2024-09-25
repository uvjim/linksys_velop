"""Helpers."""

# region #-- imports --#
import logging

from homeassistant.config_entries import device_registry as dr
from homeassistant.config_entries import entity_registry as er
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    DeviceEntryType,
    DeviceRegistry,
)
from homeassistant.helpers.entity_registry import EntityRegistry, RegistryEntry
from pyvelop.const import _PACKAGE_AUTHOR as PYVELOP_AUTHOR
from pyvelop.const import _PACKAGE_NAME as PYVELOP_NAME
from pyvelop.const import _PACKAGE_VERSION as PYVELOP_VERSION

from .const import DOMAIN
from .types import LinksysVelopConfigEntry

# endregion


_LOGGER: logging.Logger = logging.getLogger(__name__)


def get_mesh_device_for_config_entry(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry
) -> DeviceEntry | None:
    """"""
    device_registry: DeviceRegistry = dr.async_get(hass)
    found_mesh: DeviceEntry | None = device_registry.async_get_device(
        {(DOMAIN, config_entry.entry_id)}
    )
    return found_mesh


def remove_velop_device_from_registry(hass: HomeAssistant, device_id: str) -> None:
    """"""

    device_registry: DeviceRegistry = dr.async_get(hass)
    found_device: DeviceEntry | None
    if (
        found_device := device_registry.async_get_device({(DOMAIN, device_id)})
    ) is not None:
        device_registry.async_remove_device(found_device.id)
    else:
        _LOGGER.debug("remove_velop_device_from_registry: device not found")


def remove_velop_entity_from_registry(
    hass: HomeAssistant, config_entry_id: str, unique_id: str
) -> None:
    """Remove an entity from the registry."""

    entity_registry: EntityRegistry = er.async_get(hass)
    config_entities: list[RegistryEntry] = er.async_entries_for_config_entry(
        entity_registry, config_entry_id
    )
    found_entity: list[RegistryEntry]
    if found_entity := [e for e in config_entities if e.unique_id == unique_id]:
        entity_registry.async_remove(found_entity[0].entity_id)


#
#  TODO: Check all the following to see if they are required.
#


def dr_device_is_mesh(device: DeviceEntry) -> bool:
    """Establish if the given device is the Mesh."""
    return all(
        [
            device.entry_type == DeviceEntryType.SERVICE,
            device.manufacturer == PYVELOP_AUTHOR,
            device.model == f"{PYVELOP_NAME} ({PYVELOP_VERSION})",
            device.name.lower() == "mesh",
        ]
    )
