"""Diagnostics support for Linksys Velop."""

# region #-- imports --#
from __future__ import annotations

from typing import Any, List, Optional

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyvelop.mesh import Device, Mesh, Node

from .const import CONF_COORDINATOR, DOMAIN

# endregion


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Diagnostics for the config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        CONF_COORDINATOR
    ]
    mesh: Mesh = coordinator.data
    mesh_attributes: dict = getattr(mesh, "_mesh_attributes")
    _: Optional[List[Device]] = mesh_attributes.pop(
        "devices", None
    )  # these will be a non-serialisable form
    _: Optional[List[Node]] = mesh_attributes.pop(
        "nodes", None
    )  # these will be a non-serialisable form

    # region #-- create generic details --#
    ret: dict[str, Any] = {
        "config_entry": config_entry.as_dict(),  # get the config entry details
        "mesh_details": {  # get mesh details
            key: mesh_attributes.get(key) for key in mesh_attributes
        },
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
        (
            CONF_PASSWORD,
            "macAddress",
            "apBSSID",
            "stationBSSID",
            "serialNumber",
            "unique_id",
        ),
    )
