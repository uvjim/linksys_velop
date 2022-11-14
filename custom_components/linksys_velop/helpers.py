"""Helpers."""

# region #-- imports --#
from __future__ import annotations

import copy

from typing import List, Tuple

from homeassistant.config_entries import ConfigEntry
from homeassistant.config_entries import device_registry as dr
from homeassistant.config_entries import entity_registry as er
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry, DeviceEntryType
from homeassistant.helpers.entity_registry import EntityRegistry
from pyvelop.const import _PACKAGE_AUTHOR as PYVELOP_AUTHOR
from pyvelop.const import _PACKAGE_NAME as PYVELOP_NAME
from pyvelop.const import _PACKAGE_VERSION as PYVELOP_VERSION
from pyvelop.mesh import Mesh
from pyvelop.node import Node

from .const import CONF_DEVICE_TRACKERS

# endregion


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


def dr_mesh_for_config_entry(
    config: ConfigEntry, device_registry: dr.DeviceRegistry
) -> Mesh | None:
    """Get the Mesh object for the ConfigEntry."""
    my_devices: List[DeviceEntry] = dr.async_entries_for_config_entry(
        registry=device_registry, config_entry_id=config.entry_id
    )
    ret: List[DeviceEntry] = [
        dr_device for dr_device in my_devices if dr_device_is_mesh(device=dr_device)
    ]

    if ret:
        return ret[0]

    return None


def dr_nodes_for_mesh(
    config: ConfigEntry, device_registry: dr.DeviceRegistry
) -> List[Node]:
    """Get the Nodes for a Mesh object."""
    my_devices: List[DeviceEntry] = dr.async_entries_for_config_entry(
        registry=device_registry, config_entry_id=config.entry_id
    )
    ret: List[DeviceEntry] = [
        dr_device
        for dr_device in my_devices
        if all(
            [
                dr_device.manufacturer != PYVELOP_AUTHOR,
                dr_device.name.lower() != "mesh",
            ]
        )
    ]

    return ret or None


def mesh_intensive_action_running(
    config_entry: ConfigEntry,
    hass: HomeAssistant,
) -> Tuple[bool, str]:
    """Establish if an intesive action is running."""
    intensive_actions: List[str] = ["Channel Scanning"]

    entity_registry: EntityRegistry = er.async_get(hass=hass)

    reg_entry: er.RegistryEntry
    ce_entities: List[er.RegistryEntry] = [
        reg_entry
        for _, reg_entry in entity_registry.entities.items()
        if reg_entry.domain == "binary_sensor"
        and reg_entry.config_entry_id == config_entry.entry_id
        and reg_entry.original_name in intensive_actions
    ]
    ce_entity_states: List[bool] = [
        hass.states.is_state(ce_entity.entity_id, "on") for ce_entity in ce_entities
    ]
    if any(ce_entity_states):
        idx: int = ce_entity_states.index(True)
        ret = (True, ce_entities[idx].original_name)
    else:
        ret = (False, "")

    return ret


def stop_tracking_device(
    config_entry: ConfigEntry, device_id: List[str] | str, hass: HomeAssistant
) -> None:
    """Stop tracking the given device."""
    if not isinstance(device_id, list):
        device_id = [device_id]

    new_options = copy.deepcopy(
        dict(**config_entry.options)
    )  # deepcopy a dict copy so we get all the options
    trackers: List[str]
    if (trackers := new_options.get(CONF_DEVICE_TRACKERS, None)) is not None:
        for tracker_id in device_id:
            trackers.remove(tracker_id)
        new_options[CONF_DEVICE_TRACKERS] = trackers
        hass.config_entries.async_update_entry(entry=config_entry, options=new_options)
