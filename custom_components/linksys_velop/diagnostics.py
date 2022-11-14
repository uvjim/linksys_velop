"""Diagnostics support for Linksys Velop."""

# region #-- imports --#
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyvelop.mesh import Device, Mesh, Node

from .const import CONF_COORDINATOR, DOMAIN
from .helpers import dr_device_is_mesh

# endregion


ATTR_REDACT: Iterable = {
    CONF_PASSWORD,
    "macAddress",
    "apBSSID",
    "stationBSSID",
    "serialNumber",
    "unique_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Diagnostics for the config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        CONF_COORDINATOR
    ]
    mesh: Mesh = coordinator.data
    mesh_attributes: Dict = getattr(mesh, "_mesh_attributes")

    # region #-- non-serialisable objects --#
    devices: List[Device] | None = mesh_attributes.pop("devices", None)
    nodes: List[Node] | None = mesh_attributes.pop("nodes", None)
    # endregion

    # region #-- create generic details --#
    ret: Dict[str, Any] = {
        "config_entry": config_entry.as_dict(),  # get the config entry details
        "mesh_details": {  # get mesh details
            key: mesh_attributes.get(key) for key in mesh_attributes
        },
        "nodes": [node.__dict__ for node in nodes if nodes],
        "devices": [device.__dict__ for device in devices if devices],
    }
    # endregion

    # region #-- redact additional buried data --#
    if (
        ret.get("mesh_details", {})
        .get("wan_info", {})
        .get("wanConnection", {})
        .get("ipAddress")
    ):
        ret["mesh_details"]["wan_info"]["wanConnection"]["ipAddress"] = REDACTED
    if (
        ret.get("mesh_details", {})
        .get("wan_info", {})
        .get("wanConnection", {})
        .get("gateway")
    ):
        ret["mesh_details"]["wan_info"]["wanConnection"]["gateway"] = REDACTED
    if ret.get("mesh_details", {}).get("guest_network", {}).get("radios", []):
        keys = ("guestWPAPassphrase", "guestSSID")
        for idx, _ in enumerate(
            ret.get("mesh_details", {}).get("guest_network", {}).get("radios", [])
        ):
            for k in keys:
                ret["mesh_details"]["guest_network"]["radios"][idx][k] = REDACTED
    # endregion

    return async_redact_data(
        ret,
        ATTR_REDACT,
    )


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
):
    """Diagnostics for a specific device.

    N.B. If the device is the Mesh then data for the ConfigEntry diagnostics is returned
    """
    if dr_device_is_mesh(device=device):
        return await async_get_config_entry_diagnostics(hass, config_entry)

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        CONF_COORDINATOR
    ]
    mesh: Mesh = coordinator.data

    ret: Dict[str, Any] = {
        "device_entry": {
            p: getattr(device, p, None)
            for p in [prop for prop in dir(DeviceEntry) if not prop.startswith("_")]
        }
    }

    node: List[Node] = [
        n
        for n in mesh.nodes
        if mesh.nodes and n.serial == next(iter(device.identifiers))[1]
    ]
    if node:
        ret["node"] = node[0].__dict__

    ret = async_redact_data(ret, ATTR_REDACT.union({"identifiers"}))

    return ret
