"""Types."""

# region #-- imports --#
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyvelop.mesh import Mesh

# endregion


type LinksysVelopLogFormatter = Callable[[str, bool, bool], str] | None
type LinksysVelopConfigEntry = ConfigEntry[LinksysVelopData]


class CoordinatorTypes(StrEnum):
    """The type of coordinator."""

    CHANNEL_SCAN = "coordinator_channel_scan"
    MESH = "coordinator_mesh"
    SPEEDTEST = "coordinator_speedtest"


class EventSubTypes(StrEnum):
    """Available event types."""

    MESH_REBOOTED = auto()
    MESH_REBOOTING = auto()
    NEW_DEVICE_FOUND = auto()
    NEW_NODE_FOUND = auto()


@dataclass
class LinksysVelopData:
    """Data being held in the runtime of the ConfigEntry."""

    coordinators: dict[CoordinatorTypes, DataUpdateCoordinator[Any]] = field(
        default_factory=dict
    )
    intensive_running_tasks: list[str] = field(default_factory=list)
    log_formatter: LinksysVelopLogFormatter = None
    mesh: Mesh | None = None
    mesh_is_rebooting: bool = False
    service_handler: Any = None
