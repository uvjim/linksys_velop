"""Diagnostics support for Linksys Velop."""

# region #-- imports --#
from __future__ import annotations

import copy
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from pyvelop.action_registry import Actions

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

    mesh_snapshot = config_entry.runtime_data.coordinator.data.mesh

    # create generic details
    ret: dict[str, Any] = {"config_entry": config_entry.as_dict()}
    if mesh_snapshot is not None:
        ret["mesh"] = mesh_snapshot.to_dict(include_audit=True)

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
