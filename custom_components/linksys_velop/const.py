"""Constants for Linksys Velop"""

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
try:
    from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
except ImportError:
    BUTTON_DOMAIN = None
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
try:
    from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
except ImportError:
    SELECT_DOMAIN = None
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN

DOMAIN = "linksys_velop"
ENTITY_SLUG = "Velop"

CONF_API_REQUEST_TIMEOUT = "api_request_timeout"
CONF_COORDINATOR = "coordinator"
CONF_COORDINATOR_MESH = "mesh"
CONF_DEVICE_TRACKERS = "tracked"
CONF_FLOW_NAME = "name"
CONF_NODE = "node"
CONF_SCAN_INTERVAL_DEVICE_TRACKER = "scan_interval_device_tracker"
CONF_SERVICES_HANDLER = "services_handler"
CONF_TITLE_PLACEHOLDERS = "title_placeholders"
CONF_UNSUB_UPDATE_LISTENER = "unsub_update_listener"

DEF_API_REQUEST_TIMEOUT = 10
DEF_CONSIDER_HOME = 180
DEF_FLOW_NAME = "Linksys Velop Mesh"
DEF_SCAN_INTERVAL = 30
DEF_SCAN_INTERVAL_DEVICE_TRACKER = 10

PLATFORMS = [
    BINARY_SENSOR_DOMAIN,
    BUTTON_DOMAIN,
    DEVICE_TRACKER_DOMAIN,
    SELECT_DOMAIN,
    SENSOR_DOMAIN,
    SWITCH_DOMAIN,
]

SIGNAL_UPDATE_DEVICE_TRACKER = "update_device_tracker"
SIGNAL_UPDATE_SPEEDTEST_RESULTS = "update_speedtest_results"
SIGNAL_UPDATE_SPEEDTEST_STATUS = "update_speedtest_status"

ST_IGD = "urn:schemas-upnp-org:device:InternetGatewayDevice:2"

STEP_USER = "user"
STEP_TIMERS = "timers"
STEP_DEVICE_TRACKERS = "device_trackers"
