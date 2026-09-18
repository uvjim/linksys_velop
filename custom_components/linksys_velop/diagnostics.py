"""Diagnostics support for Linksys Velop."""

# region #-- imports --#
from __future__ import annotations

import copy
import logging
from collections.abc import Sequence
from typing import Any

from homeassistant.core import HomeAssistant
from pyvelop.action_registry import Actions
from pyvelop.mesh_attribute import MeshAttribute
from pyvelop.mesh_entity import DeviceEntity, NodeEntity

from .const import CONF_REDACT_OPTIONS
from .coordinator import LinksysVelopConfigEntry

# endregion

_LOGGER = logging.getLogger(__name__)

DEF_REDACTED: str = "**REDACTED**"


def redact(data: dict[str, Any], to_redact: set[str] | None = None) -> dict[str, Any]:
    """Redact sensitive data in a dict. Dotted paths may traverse dicts and lists."""

    if to_redact is None:
        to_redact = set()
    ret: dict[str, Any] = copy.copy(data)

    def apply_redaction(obj: Any, parts: list[str]) -> None:
        if not parts:
            return

        # If we're at the final key, redact it wherever obj is a dict.
        if len(parts) == 1:
            key = parts[0]
            if isinstance(obj, dict) and key in obj:
                obj[key] = DEF_REDACTED
            elif isinstance(obj, list):
                for item in obj:
                    apply_redaction(item, parts)
            return

        # Still have more segments to traverse.
        head = parts[0]
        tail = parts[1:]

        if isinstance(obj, dict):
            if head in obj:
                apply_redaction(obj[head], tail)

        elif isinstance(obj, list):
            for item in obj:
                apply_redaction(item, parts)

    for redaction in to_redact:
        parts = [p for p in redaction.split(".") if p]
        if parts:
            apply_redaction(ret, parts)

    return ret


# TODO: tidy this up once `pyvelop` is serialising `MeshSnapshot` properly
async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry
) -> dict[str, Any]:
    """Diagnostics for the config entry."""

    def get_properties[T](cls: type[T]) -> set[str]:
        """Retrieve the properties for the given class type."""

        properties: set[str] = set()
        seen: set[str] = set()

        # respect normal attribute resolution when inspecting properties
        for base in cls.__mro__:
            for name, value in base.__dict__.items():
                if name in seen:
                    continue

                seen.add(name)

                if isinstance(value, property):
                    properties.add(name)

        return properties

    mesh_snapshot = config_entry.runtime_data.coordinator.data.mesh
    mesh_dump = {}
    for prop in get_properties(type(mesh_snapshot)):
        val = getattr(mesh_snapshot, prop, None)
        if isinstance(val, MeshAttribute):
            val = val.to_dict(include_audit=True)
        elif isinstance(val, Sequence):
            val = [
                (
                    item.to_dict(include_audit=True)
                    if isinstance(item, (DeviceEntity, NodeEntity))
                    else item
                )
                for item in val
            ]

        mesh_dump[prop] = val

    # create generic details
    ret: dict[str, Any] = {"config_entry": config_entry.as_dict(), "mesh": mesh_dump}

    # carry out redaction
    to_redact: set[str] = {
        "config_entry.options.node",
        "config_entry.options.password",
        "config_entry.unique_id",
    }
    for action in Actions.values():
        default_redactions: set[str] = action.redactions
        supplementary_redactions: set[str] = config_entry.options.get(
            CONF_REDACT_OPTIONS, {}
        ).get(action.key, set())
        redactions: set[str] = default_redactions.union(supplementary_redactions)
        to_redact.update([f"mesh_details.{action.key}.{r}" for r in redactions])

    ret = redact(
        ret,
        to_redact,
    )

    return ret
