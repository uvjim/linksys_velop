""""""

# region #-- imports --#
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

# endregion


class CoordinatorTypes(StrEnum):
    """"""

    CHANNEL_SCAN = "coordinator_channel_scan"
    MESH = "coordinator_mesh"
    SPEEDTEST = "coordinator_speedtest"


class EventSubTypes(StrEnum):
    """"""

    # MESH_REBOOTED = auto()
    MESH_REBOOTING = auto()
    NEW_DEVICE_FOUND = auto()
    NEW_NODE_FOUND = auto()


@dataclass
class LinksysVelopData:
    """"""

    coordinators: dict[CoordinatorTypes, DataUpdateCoordinator[Any]] = field(
        default_factory=dict
    )
    intensive_running_tasks: list[str] = field(default_factory=list)
    mesh_is_rebooting: bool = False
    service_handler: Any = None


type LinksysVelopConfigEntry = ConfigEntry[LinksysVelopData]
