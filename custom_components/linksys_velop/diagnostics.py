"""Diagnostics support for Linksys Velop."""

# region #-- imports --#
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from pyvelop.mesh import MeshSnapshot
from pyvelop.redaction import redact

from .coordinator import LinksysVelopConfigEntry

# endregion

_LOGGER = logging.getLogger(__name__)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the config entry."""

    mesh_snapshot: MeshSnapshot | None = config_entry.runtime_data.coordinator.data.mesh

    # create generic details
    to_redact: set[str] = {
        "options.node",
        "options.password",
        "unique_id",
    }
    ret: dict[str, Any] = {"config_entry": redact(config_entry.as_dict(), to_redact)}
    if mesh_snapshot is not None:
        ret["mesh"] = mesh_snapshot.get_action_data()

    return ret
