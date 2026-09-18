"""Helpers."""

# region #-- imports --#
import logging

from awesomeversion import AwesomeVersion
from homeassistant.core import HomeAssistant
from homeassistant.core import __version__ as HA_VERSION
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry, RegistryEntry
from homeassistant.loader import Integration, async_get_integration
from pyvelop.mesh import MeshSnapshot
from pyvelop.mesh_entity import AdapterInfo, NodeEntity

from .const import DOMAIN
from .logger import Logger

# endregion


_LOGGER: Logger = Logger(logging.getLogger(__name__))


def get_mesh_parent_node(node: NodeEntity, mesh: MeshSnapshot) -> NodeEntity | None:
    """Retrieve the parent node from the mesh."""

    parent_node: NodeEntity | None = None

    # region #-- get the primary adapater for the node --#
    adapter_main: AdapterInfo | None = next(
        (adi for adi in node.adapter_info if adi.primary),
        None,
    )
    # endregion

    # region #-- get the parent based on ID --#
    if adapter_main:
        parent_node = next(
            (n for n in mesh.nodes if n.unique_id == adapter_main.parent_id),
            None,
        )
    # endregion

    # region #-- if we don't have the parent yet lookup based on name --#
    if parent_node is None:
        parent_node = next(
            (n for n in mesh.nodes if n.name == node.parent_name),
            None,
        )
    # endregion

    return parent_node


def get_registry_device(
    hass: HomeAssistant, device_id: str, config_entry_id: str | None = None
) -> DeviceEntry | None:
    """Retrieve the device from the Home Assistant device registry.

    This is currently backwardly compatible with Home Assistant versions.

    :param hass: Home Assistant root object.
    :param device_id: ID of the device in the registry.
    :param: config_entry_id: Must be supplied if the Home Assistant version is higher then 2026.8.0.
    :returns: `DeviceEntry` object from the registry or `None` if not found.
    :raises ValueError: when supplied arguments are incorrect.
    """

    device_registry: DeviceRegistry = dr.async_get(hass)

    # TODO: fix up this branch when bumping min HA version
    if AwesomeVersion(HA_VERSION) >= AwesomeVersion("2026.8.0"):
        if config_entry_id is None:
            raise ValueError("config_entry_id must be supplied")

        found_device: DeviceEntry | None = (
            device_registry.async_get_device_by_identifier(
                (DOMAIN, device_id),
                config_entry_id,
            )
        )
    else:
        found_device: DeviceEntry | None = device_registry.async_get_device(
            {(DOMAIN, device_id)}
        )

    return found_device


def remove_velop_device_from_registry(
    hass: HomeAssistant, device_id: str, config_entry_id: str | None = None
) -> None:
    """Remove a device from the registry."""

    device_registry: DeviceRegistry = dr.async_get(hass)
    found_device: DeviceEntry | None = get_registry_device(
        hass,
        device_id,
        config_entry_id,
    )
    found_device: DeviceEntry | None
    if found_device is not None:
        device_registry.async_remove_device(found_device.id)


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
