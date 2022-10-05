"""Helpers."""

# region #-- imports --#
from __future__ import annotations

from typing import List

from homeassistant.config_entries import ConfigEntry
from homeassistant.config_entries import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry, DeviceEntryType
from pyvelop.const import _PACKAGE_AUTHOR as PYVELOP_AUTHOR
from pyvelop.const import _PACKAGE_NAME as PYVELOP_NAME
from pyvelop.const import _PACKAGE_VERSION as PYVELOP_VERSION
from pyvelop.mesh import Mesh
from pyvelop.node import Node

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
