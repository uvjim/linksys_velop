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

# Field names in `MeshSnapshot.to_dict()` (and the entities it contains) that identify the
# network or its devices. The action redactions name fields in the raw JNAP responses, which
# the snapshot renames, so they are matched by their last segment as well (see below).
MESH_REDACTIONS: set[str] = {
    "client_id",
    "dhcp_reservations",
    "guest_wifi_details",
    "hostname",
    "ip",
    "ipv6",
    "mac",
    "mac_filtering_addresses",
    "name",
    "parent",
    "parent_ip",
    "parent_ipv6",
    "parent_name",
    "reservation_description",
    "serial",
    "wan_dns",
    "wan_ip",
    "wan_mac",
}


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


def redact_keys(obj: Any, keys: set[str]) -> Any:
    """Redact every dict value whose key is in `keys`, at any depth, in dicts and lists."""

    if isinstance(obj, dict):
        return {
            k: DEF_REDACTED if k in keys else redact_keys(v, keys)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [redact_keys(item, keys) for item in obj]
    return obj


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
    ret = redact(ret, to_redact)

    # The snapshot is not keyed by action, so the default and supplementary action
    # redactions are applied by field name wherever they occur in it.
    mesh_keys: set[str] = set(MESH_REDACTIONS)
    for action in Actions.values():
        supplementary_redactions: set[str] = config_entry.options.get(
            CONF_REDACT_OPTIONS, {}
        ).get(action.key, set())
        for r in action.redactions.union(supplementary_redactions):
            mesh_keys.add(r.split(".")[-1])
    if "mesh" in ret:
        ret["mesh"] = redact_keys(ret["mesh"], mesh_keys)

    return ret
