"""Constants for Linksys Velop."""

# region #-- imports --#
import uuid
from enum import StrEnum
from importlib.metadata import PackageNotFoundError, distribution, version

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.event import DOMAIN as EVENT_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN

from .types import EventSubTypes

# endregion

DOMAIN: str = "linksys_velop"

CONF_ALLOW_MESH_REBOOT: str = "allow_mesh_reboot"
CONF_API_REQUEST_TIMEOUT: str = "api_request_timeout"
CONF_DEVICE_TRACKERS: str = "tracked"
CONF_DEVICE_TRACKERS_TO_REMOVE: str = "tracked_to_remove"
CONF_EVENTS_OPTIONS: str = "events_options"
CONF_FLOW_NAME: str = "name"
CONF_NODE: str = "node"
CONF_NODE_IMAGES: str = "node_images"
CONF_SCAN_INTERVAL_DEVICE_TRACKER: str = "scan_interval_device_tracker"
CONF_SELECT_TEMP_UI_DEVICE: str = "select_temp_ui_device"
CONF_TITLE_PLACEHOLDERS: str = "title_placeholders"
CONF_UI_DEVICES_TO_REMOVE: str = "ui_devices_to_remove"
CONF_UI_DEVICES: str = "ui_devices"

DEF_ALLOW_MESH_REBOOT: bool = False
DEF_API_REQUEST_TIMEOUT: int = 10
DEF_CHANNEL_SCAN_PROGRESS_INTERVAL_SECS: float = 40
DEF_CONSIDER_HOME: int = 180
DEF_EVENTS_OPTIONS: list[str] = [ev.value for ev in EventSubTypes]
DEF_FLOW_NAME: str = "Linksys Velop Mesh"
DEF_SCAN_INTERVAL: int = 60
DEF_SCAN_INTERVAL_DEVICE_TRACKER: int = 10
DEF_SELECT_TEMP_UI_DEVICE: bool = False
DEF_SPEEDTEST_PROGRESS_INTERVAL_SECS: float = 1
DEF_UI_PLACEHOLDER_DEVICE_ID: str = str(uuid.UUID(int=0))

ISSUE_MISSING_DEVICE_TRACKER: str = "missing_device_tracker"
ISSUE_MISSING_NODE: str = "missing_node"
ISSUE_MISSING_UI_DEVICE: str = "missing_ui_device"

PLATFORMS: list[str | None] = [
    BINARY_SENSOR_DOMAIN,
    BUTTON_DOMAIN,
    SENSOR_DOMAIN,
    SWITCH_DOMAIN,
    UPDATE_DOMAIN,
]

try:
    PYVELOP_NAME: str = "pyvelop"
    PYVELOP_AUTHOR: str = distribution(PYVELOP_NAME).metadata.get("Author")
    PYVELOP_VERSION: str = version(PYVELOP_NAME)
except PackageNotFoundError:
    pass


SIGNAL_DEVICE_TRACKER_UPDATE: str = f"{DOMAIN}_device_tracker_update"
SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE: str = f"{DOMAIN}_ui_placeholder_update"

ST_IGD: str = "urn:schemas-upnp-org:device:InternetGatewayDevice:2"


class IntensiveTask(StrEnum):
    """"""

    CHANNEL_SCAN = "Channel Scan"
