"""Integration events."""

# region #-- imports --#
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from homeassistant.backports.enum import StrEnum
from homeassistant.config_entries import ConfigEntry
from homeassistant.config_entries import device_registry as dr
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from pyvelop.device import Device
from pyvelop.mesh import Mesh
from pyvelop.node import Node

from .const import CONF_SUBTYPE, DOMAIN
from .helpers import dr_mesh_for_config_entry

# endregion

EVENT_TYPE: str = f"{DOMAIN}_event"


@dataclass
class EventSubType(StrEnum):
    """Event sub type definitions."""

    LOGGING_STOPPED = "logging_stopped"
    NEW_DEVICE = "new_device"
    NEW_NODE = "new_node"
    NEW_PRIMARY_NODE = "new_primary_node"


def build_payload(
    config_entry: ConfigEntry,
    event: EventSubType,
    hass: HomeAssistant,
    device: Device | Node | None = None,
) -> Dict[str, Any]:
    """Build the payload for the fired events."""
    event_properties: List[str] = []

    if event is EventSubType.NEW_DEVICE:
        event_properties = [
            "connected_adapters",
            "description",
            "manufacturer",
            "model",
            "name",
            "operating_system",
            "parent_name",
            "serial",
            "status",
            "unique_id",
        ]
    elif event is EventSubType.NEW_NODE:
        event_properties = [
            "backhaul",
            "connected_adapters",
            "model",
            "name",
            "parent_name",
            "serial",
            "status",
            "unique_id",
        ]
    elif event is EventSubType.NEW_PRIMARY_NODE:
        event_properties = [
            "connected_adapters",
            "model",
            "name",
            "serial",
            "unique_id",
        ]

    if device:
        ret: Dict[str, Any] = {
            prop: getattr(device, prop, None) for prop in event_properties
        }
        if ret:
            # region #-- get the mesh device_id --#
            mesh_details: Mesh = dr_mesh_for_config_entry(
                config=config_entry, device_registry=dr.async_get(hass=hass)
            )

            if mesh_details:
                ret["mesh_device_id"] = mesh_details.id
            # endregion
    else:
        if event is EventSubType.LOGGING_STOPPED:
            ret = {CONF_NAME: config_entry.title}

    ret[CONF_SUBTYPE] = event

    return ret
