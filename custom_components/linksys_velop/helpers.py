"""Helpers."""

# region #-- imports --#
import logging
from typing import Any

from awesomeversion import AwesomeVersion
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry, RegistryEntry
from homeassistant.loader import Integration, async_get_integration
from pyvelop.mesh import Mesh
from pyvelop.mesh_entity import NodeEntity

from .const import DOMAIN

# endregion


_LOGGER: logging.Logger = logging.getLogger(__name__)


def get_mesh_parent_node(node: NodeEntity, mesh: Mesh) -> NodeEntity | None:
    """Retrieve the parent node from the mesh."""

    parent_node: NodeEntity | None = None

    _LOGGER.debug("getting parent node for, %s", node)

    # region #-- get the primary adapater for the node --#
    adapter_main: dict[str, Any] | None = next(
        (adi for adi in node.adapter_info if adi.get("primary", False)),
        None,
    )
    # endregion

    # region #-- get the parent based on ID --#
    if adapter_main:
        _LOGGER.debug("looking for parent based on ID")
        parent_node = next(
            (n for n in mesh.nodes if n.unique_id == adapter_main.get("parent_id")),
            None,
        )
    # endregion

    # region #-- if we don't have the parent yet lookup based on name --#
    if parent_node is None:
        _LOGGER.debug("looking for parent based on name")
        parent_node = next(
            (n for n in mesh.nodes if n.name == node.parent_name),
            None,
        )
    # endregion

    _LOGGER.debug("parent_node, %s", parent_node)
    return parent_node


def remove_velop_device_from_registry(hass: HomeAssistant, device_id: str) -> None:
    """Remove a device from the registry."""

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
    found_entity: RegistryEntry | None = None
    if (
        found_entity := next(
            (e for e in config_entities if e.unique_id == unique_id), None
        )
    ) is not None:
        _LOGGER.debug("removing %s", found_entity.entity_id)
        entity_registry.async_remove(found_entity.entity_id)


async def async_get_integration_version(hass: HomeAssistant) -> AwesomeVersion | None:
    """Retrieve the version number for the integration."""

    ret: Integration = await async_get_integration(hass, DOMAIN)
    return ret.version
