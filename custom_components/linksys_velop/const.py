"""Constants for Linksys Velop"""

DOMAIN = "linksys_velop"
ENTITY_SLUG = "Velop"

CONF_API_REQUEST_TIMEOUT = "api_request_timeout"
CONF_COORDINATOR = "coordinator"
CONF_DEVICE_TRACKERS = "tracked"
CONF_FLOW_NAME = "name"
CONF_MESH = "mesh"
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
    "binary_sensor",
    "device_tracker",
    "sensor",
    "switch",
]

SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS = "update_check_for_updates_status"
SIGNAL_UPDATE_DEVICE_TRACKER = "update_device_tracker"
SIGNAL_UPDATE_PARENTAL_CONTROL_STATUS = "update_parental_control"
SIGNAL_UPDATE_SPEEDTEST_RESULTS = "update_speedtest_results"
SIGNAL_UPDATE_SPEEDTEST_STATUS = "update_speedtest_status"

ST_IGD = "urn:schemas-upnp-org:device:InternetGatewayDevice:2"

STEP_USER = "user"
STEP_TIMERS = "timers"
STEP_DEVICE_TRACKERS = "device_trackers"
