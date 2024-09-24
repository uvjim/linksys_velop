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

    NEW_DEVICE_FOUND = auto()
    NEW_NODE_FOUND = auto()
    NEW_PRIMARY_NODE = auto()


@dataclass
class LinksysVelopData:
    """"""

    coordinators: dict[CoordinatorTypes, DataUpdateCoordinator[Any]] = field(
        default_factory=dict
    )
    intensive_running_tasks: list[str] = field(default_factory=list)
    service_handler: Any = None


type LinksysVelopConfigEntry = ConfigEntry[LinksysVelopData]
