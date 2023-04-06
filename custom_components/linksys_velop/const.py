"""Constants for Linksys Velop."""

# region #-- imports --#
import uuid
from typing import List, Optional

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN

# endregion

DOMAIN: str = "linksys_velop"
ENTITY_SLUG: str = "Velop"

CONF_API_REQUEST_TIMEOUT: str = "api_request_timeout"
CONF_COORDINATOR: str = "coordinator"
CONF_COORDINATOR_MESH: str = "mesh"
CONF_DEVICE_UI: str = "ui_devices"
CONF_DEVICE_UI_MISSING: str = "ui_devices_missing"
CONF_DEVICE_TRACKERS: str = "tracked"
CONF_DEVICE_TRACKERS_MISSING: str = "tracked_missing"
CONF_ENTRY_RELOAD: str = "reloading"
CONF_FLOW_NAME: str = "name"
CONF_LOGGING_JNAP_RESPONSE: str = "logging_jnap_response"
CONF_LOGGING_MODE: str = "logging_mode"
CONF_LOGGING_MODE_OFF: str = "off"
CONF_LOGGING_MODE_SINGLE: str = "single"
CONF_LOGGING_OPTION_INCLUDE_QUERY_RESPONSE: str = "include_query_response"
CONF_LOGGING_OPTION_INCLUDE_SERIAL: str = "include_serial"
CONF_LOGGING_OPTIONS: str = "logging_options"
CONF_LOGGING_SERIAL: str = "logging_serial"
CONF_NODE: str = "node"
CONF_NODE_IMAGES: str = "node_images"
CONF_SCAN_INTERVAL_DEVICE_TRACKER: str = "scan_interval_device_tracker"
CONF_SELECT_TEMP_UI_DEVICE: str = "select_temp_ui_device"
CONF_SERVICES_HANDLER: str = "services_handler"
CONF_SUBTYPE: str = "subtype"
CONF_TITLE_PLACEHOLDERS: str = "title_placeholders"
CONF_UNSUB_UPDATE_LISTENER: str = "unsub_update_listener"

DEF_API_REQUEST_TIMEOUT: int = 10
DEF_CONSIDER_HOME: int = 180
DEF_FLOW_NAME: str = "Linksys Velop Mesh"
DEF_LOGGING_MODE: str = CONF_LOGGING_MODE_OFF
DEF_LOGGING_OPTIONS: List[str] = []
DEF_SCAN_INTERVAL: int = 60
DEF_SCAN_INTERVAL_DEVICE_TRACKER: int = 10
DEF_SELECT_TEMP_UI_DEVICE: bool = False
DEF_UI_DEVICE_ID: str = str(uuid.UUID(int=0))

ISSUE_MISSING_DEVICE_TRACKER: str = "missing_device_tracker"
ISSUE_MISSING_UI_DEVICE: str = "missing_ui_device"

PLATFORMS: List[Optional[str]] = [
    BINARY_SENSOR_DOMAIN,
    BUTTON_DOMAIN,
    SELECT_DOMAIN,
    SENSOR_DOMAIN,
    SWITCH_DOMAIN,
    UPDATE_DOMAIN,
    DEVICE_TRACKER_DOMAIN,
]

SIGNAL_UPDATE_CHANNEL_SCANNING: str = f"{DOMAIN}_channel_scanning"
SIGNAL_UPDATE_DEVICE_TRACKER: str = f"{DOMAIN}_update_device_tracker"
SIGNAL_UPDATE_PLACEHOLDER_UI_DEVICE: str = f"{DOMAIN}_update_placeholder_ui_device"
SIGNAL_UPDATE_SPEEDTEST_PROGRESS: str = f"{DOMAIN}_update_speedtest_progress"
SIGNAL_UPDATE_SPEEDTEST_RESULTS: str = f"{DOMAIN}_update_speedtest_results"
SIGNAL_UPDATE_SPEEDTEST_STATUS: str = f"{DOMAIN}_update_speedtest_status"

ST_IGD: str = "urn:schemas-upnp-org:device:InternetGatewayDevice:2"
