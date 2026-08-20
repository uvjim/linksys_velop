"""Constants for Linksys Velop."""

# region #-- imports --#
from dataclasses import dataclass
from enum import StrEnum, auto
from importlib.metadata import PackageNotFoundError, distribution, version

# endregion


@dataclass
class DataCoordinatorFormattedData:
    """Base class for data being returned for an entity."""

    connected_node: str


@dataclass
class ChannelScanInfo(DataCoordinatorFormattedData):
    """Representation of Channel Scan information."""

    is_running: bool
    selected_channels: dict[str, list[dict[str, int | str]]] | None = None


class IntensiveTask(StrEnum):
    """Representation of tasks that could cause a delay in response from the Mesh."""

    CHANNEL_SCAN = "Channel Scan"
    REBOOT = "Reboot"


class EventSubTypes(StrEnum):
    """Available event types."""

    MESH_REBOOTED = auto()
    MESH_REBOOTING = auto()
    NEW_DEVICE_FOUND = auto()
    NEW_NODE_FOUND = auto()


DOMAIN: str = "linksys_velop"

CONF_ALLOW_MESH_REBOOT: str = "allow_mesh_reboot"
CONF_API_REQUEST_TIMEOUT: str = "api_request_timeout"
CONF_DEVICE_TRACKERS: str = "tracked"
CONF_DEVICE_TRACKERS_TO_REMOVE: str = "tracked_to_remove"
CONF_EVENTS_OPTIONS: str = "events_options"
CONF_EVENTS_WAIT_IP: str = "events_wait_ip"
CONF_FLOW_NAME: str = "name"
CONF_REDACT_OPTIONS: str = "redact_options"
CONF_NODE: str = "node"
CONF_NODE_IMAGES: str = "node_images"
CONF_SCAN_INTERVAL_DEVICE_TRACKER: str = "scan_interval_device_tracker"
CONF_SELECT_TEMP_UI_DEVICE: str = "select_temp_ui_device"
CONF_UI_PLACEHOLDER_DEVICE_ID: str = "ui_placeholder_device_id"
CONF_TITLE_PLACEHOLDERS: str = "title_placeholders"
CONF_UI_DEVICES_TO_REMOVE: str = "ui_devices_to_remove"
CONF_UI_DEVICES: str = "ui_devices"

DEF_ALLOW_MESH_REBOOT: bool = False
DEF_API_CONFIG_FLOW_REQUEST_TIMEOUT: int = 60
DEF_API_REQUEST_TIMEOUT: int = 15
DEF_CHANNEL_SCAN_PROGRESS_INTERVAL_SECS: float = 40
DEF_CONSIDER_HOME: int = 180
DEF_EVENTS_OPTIONS: list[str] = [event.value for event in EventSubTypes]
DEF_EVENTS_WAIT_IP: bool = False
DEF_FLOW_NAME: str = "Linksys Velop Mesh"
DEF_SCAN_INTERVAL: int = 60
DEF_SCAN_INTERVAL_DEVICE_TRACKER: int = 10
DEF_SELECT_TEMP_UI_DEVICE: bool = False
DEF_SPEEDTEST_PROGRESS_INTERVAL_SECS: float = 1

ISSUE_MISSING_DEVICE_TRACKER: str = "missing_device_tracker"
ISSUE_MISSING_UI_DEVICE: str = "missing_ui_device"

try:
    PYVELOP_NAME: str = "pyvelop"
    PYVELOP_AUTHOR: str = distribution(PYVELOP_NAME).metadata.get("Author", "")
    PYVELOP_VERSION: str = version(PYVELOP_NAME)
except PackageNotFoundError:
    pass


SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE: str = f"{DOMAIN}_ui_placeholder_update"

ST_IGD: str = "urn:schemas-upnp-org:device:InternetGatewayDevice:2"
