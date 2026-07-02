"""Types."""

# region #-- imports --#
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any, Protocol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyvelop.mesh import Mesh

# endregion


class LinksysVelopLogFormatter(Protocol):
    """Protocol for the log formatter."""

    def __call__(
        self, message: str, include_caller: bool = True, include_lineno: bool = False, /
    ) -> str:  # pragma: no cover - protocol
        ...


type LinksysVelopConfigEntry = ConfigEntry[LinksysVelopRuntimeData]


class CoordinatorTypes(StrEnum):
    """The type of coordinator."""

    CHANNEL_SCAN = "coordinator_channel_scan"
    DEVICE_TRACKER = "coordinator_device_tracker"
    MESH = "coordinator_mesh"
    SPEEDTEST = "coordinator_speedtest"


class EventSubTypes(StrEnum):
    """Available event types."""

    MESH_REBOOTED = auto()
    MESH_REBOOTING = auto()
    NEW_DEVICE_FOUND = auto()
    NEW_NODE_FOUND = auto()


@dataclass
class LinksysVelopRuntimeData:
    """Runtime data for the ConfigEntry."""

    log_formatter: LinksysVelopLogFormatter
    mesh: Mesh
    coordinators: dict[CoordinatorTypes, DataUpdateCoordinator[Any]] = field(
        default_factory=dict
    )
    device_tracker_unsub: CALLBACK_TYPE = lambda: None
    mesh_is_rebooting: bool = False
    intensive_running_tasks: list[str] = field(default_factory=list)
