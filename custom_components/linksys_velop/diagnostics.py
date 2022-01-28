"""Diagnostics support for Linksys Velop"""

from typing import (
    Any,
    List,
    Union,
)

from homeassistant.components.diagnostics import (
    async_redact_data,
    REDACTED,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyvelop.mesh import (
    Device,
    Mesh,
    Node,
)

from .const import (
    CONF_COORDINATOR,
    DOMAIN,
)


async def async_get_config_entry_diagnostics(hass: HomeAssistant, config_entry: ConfigEntry) -> dict[str, Any]:
    """Diagnostics for the config entry"""

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
    mesh: Mesh = coordinator.data
    mesh_attributes = getattr(mesh, "_Mesh__mesh_attributes")
    mesh_details_keys = (
        "check_update_state",
        "guest_network",
        "parental_control",
        "speedtest_results",
        "speedtest_state",
        "wan_info",
    )

    # region #-- create generic details --#
    ret: dict[str, Any] = {
        "config_entry": config_entry.as_dict(),  # get the config entry details
        "mesh_details": {  # get mesh details
            key: mesh_attributes.get(key)
            for key in mesh_details_keys
        },
    }
    # endregion

    # region #-- get the node and device details --#
    keys = ("nodes", "devices")
    for k in keys:
        items: List[Union[Device, Node]] = mesh_attributes.get(k, [])
        if items:
            ret[k] = []
            for i in items:
                ret[k].append({
                    "parent_name": i.parent_name,
                    "raw_attributes": getattr(i, "_attribs"),
                })
                if isinstance(i, Node):
                    ret[k][-1]["connected_devices"] = getattr(i, "_Node__connected_devices")
        else:
            ret[k] = items
    # endregion

    # region #-- redact additional buried data --#
    if ret.get("mesh_details", {}).get("wan_info", {}).get("wanConnection", {}).get("ipAddress"):
        ret["mesh_details"]["wan_info"]["wanConnection"]["ipAddress"] = REDACTED
    if ret.get("mesh_details", {}).get("wan_info", {}).get("wanConnection", {}).get("gateway"):
        ret["mesh_details"]["wan_info"]["wanConnection"]["gateway"] = REDACTED
    if ret.get("mesh_details", {}).get("guest_network", {}).get("radios", []):
        keys = ("guestWPAPassphrase", "guestSSID")
        for idx, radio in enumerate(ret.get("mesh_details", {}).get("guest_network", {}).get("radios", [])):
            for k in keys:
                ret["mesh_details"]["guest_network"]["radios"][idx][k] = REDACTED
    # endregion

    return async_redact_data(ret, (CONF_PASSWORD, "macAddress", "apBSSID", "stationBSSID"))
