
# Linksys Velop

Home Assistant integration for the Linksys Velop Wi-Fi system.

## Description

This custom component has been designed to for Home Assistant and enables 
access to the functions that would be useful in the Home Assistant environment.

### Definitions
 
- _Mesh_: the mesh is the network itself and refers to anything that is not 
  attributed to a single node or device in  the network.
- _Node_: a node is a device that helps to form the mesh.
- _Device_: a device is an endpoint that connects to the mesh network. Think 
  of these as the endpoint devices, such as a laptop, phone or tablet. 

### Entities Provided
Where applicable the sub-items in the list detail the additional attributes 
available.

#### Binary Sensors

- Mesh: Speedtest state
  - current stage of the Speedtest, e.g. Detecting server, Checking latency
- Mesh: WAN Status
  - IP, DNS, MAC
- Node: Status
  - IP, MAC
- Node: Update Available

#### Buttons

- Mesh: Check for Updates
- Node: Reboot

#### Device  Trackers

These are selectable and are presented as part of the configuration at both 
install time and from reconfiguring the integration.

#### Sensors

- Mesh: Number of Offline Devices
  - list of device names that are offline
- Mesh: Number of Online Devices
  - list of device names, IP addresses and adapter types that are online
- Mesh: Date of Latest Speedtest
  - Exit code, Latency, Download/Upload bandwidth, Result ID
- Mesh: Number of Available Storage Partitions *(disabled by default)*
  - list of the available partitions including the following information: IP, 
    label, available Kb, used Kb, used %age and last checked time
- Node: Number of Connected Devices
  - list of device names and IP addresses that are connected
- Node: Current Firmware Version
- Node: Last Update Check *(disabled by default)*
- Node: Model Number
- Node: Newest Firmware Version
- Node: Parent Name
  - IP address of the parent
- Node: Serial Number
- Node: Type of Node, e.g. Primary Secondary

#### Switches

- Mesh: Guest Wi-Fi state
  - list of guest networks available
- Mesh: Parental Control state

### Services

Services are available for the following: -

- Start a Speedtest &ast;
- Initiate a check for firmware updates for the nodes &ast;
- Delete a machine from the device list

> &ast; these are considered long-running tasks. When the binary sensors spot 
  these tasks are running an additional timer is set up that polls every 
  second to get updates and updates the relevant attributes for that sensor.    

## Setup

When setting up the integration you will be asked for the following information.

![Initial Setup Screen](images/setup_user.png)

- `Primary node address`: must be the node classed as the primary node
- `Password`: the password you would use to log in to the router. This may 
  not be the same as the password for the application or web UI if you use 
  the Linksys cloud service.

On successful set up the following screen will be seen detailing the Mesh 
device and the individual nodes found in the mesh.

![Final Setup Screen](images/setup_final.png)

## Configurable Options

It is possible to configure the following options for the integration.

#### Timers

![Configure Timers](images/config_timers.png)

- `Scan Interval`: the frequency of updates for the sensors, default `30s`
- `Device Tracker Interval`: the frequency of updates for the device 
  trackers, default `10s`
- `Consider Home Period`: the time to wait before considering a device away 
  after it notifies of becoming disconnected, default `180s`

#### Device Trackers

![Configure Device Trackers](images/config_device_trackers.png)

- `Available devices`: a multi-select list of the devices found on the mesh. 
  This list excludes any device which doesn't have a name - typically 
  displayed in the official interfaces as `Network Device`

## Troubleshooting

### Debug Logging

Debug logging can be enabled in Home Assistant using the `logger` 
integration see [here](https://www.home-assistant.io/integrations/logger/).

```yaml
logger:
  default: warning
  logs:
    custom_components.linksys_velop: debug
    pyvelop: debug
```

### Diagnostics Integration

Starting with Home Assistant 2022.2 a new diagnostics integration can be 
used to provide troubleshooting for integrations. This integration supports 
that as of version `2021.1.3`.

The highlighted area in the image below shows where the link for downloading 
diagnostics can be found.

![Diagnostics link](images/diagnostics.png)

<details>
  <summary>Example output</summary>
  
```json
{
  "home_assistant": {
    "installation_type": "Home Assistant Core",
    "version": "2022.2.0b0",
    "dev": false,
    "hassio": false,
    "virtualenv": true,
    "python_version": "3.9.2",
    "docker": false,
    "arch": "aarch64",
    "timezone": "UTC",
    "os_name": "Linux",
    "os_version": "5.10.63-v8+",
    "run_as_root": false
  },
  "custom_components": {
    "linksys_velop": {
      "version": "2022.1.3",
      "requirements": [
        "pyvelop==2022.1.1"
      ]
    },
    "virginmedia_tv": {
      "version": "2021.11.1",
      "requirements": [
        "beautifulsoup4"
      ]
    }
  },
  "integration_manifest": {
    "codeowners": [
      "@uvjim"
    ],
    "config_flow": true,
    "dependencies": [
      "ssdp"
    ],
    "domain": "linksys_velop",
    "documentation": "https://github.com/uvjim/linksys_velop",
    "iot_class": "local_polling",
    "issue_tracker": "https://github.com/uvjim/linksys_velop/issues",
    "name": "Linksys Velop",
    "requirements": [
      "pyvelop==2022.1.1"
    ],
    "ssdp": [
      {
        "st": "urn:schemas-upnp-org:device:InternetGatewayDevice:2",
        "manufacturer": "Linksys"
      }
    ],
    "version": "2022.1.3",
    "is_built_in": false
  },
  "data": {
    "config_entry": {
      "entry_id": "980e0dbc7161d4bff5842d210e3b271e",
      "version": 1,
      "domain": "linksys_velop",
      "title": "192.168.123.254",
      "data": {
        "node": "192.168.123.254"
      },
      "options": {
        "node": "192.168.123.254",
        "password": "**REDACTED**",
        "api_request_timeout": 10,
        "scan_interval": 30,
        "scan_interval_device_tracker": 10,
        "consider_home": 180,
        "tracked": [
          "76a5f29d-00c0-48ff-be05-be99a8fb6061"
        ]
      },
      "pref_disable_new_entities": false,
      "pref_disable_polling": false,
      "source": "ssdp",
      "unique_id": "38U10M3BA40594",
      "disabled_by": null
    },
    "mesh_details": {
      "check_update_state": {
        "firmwareUpdateStatus": [
          {
            "deviceUUID": "614b8c65-c044-ee54-3052-e89f8060c837",
            "lastSuccessfulCheckTime": "2022-01-27T19:12:34Z"
          },
          {
            "deviceUUID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870",
            "lastSuccessfulCheckTime": "2022-01-27T19:12:34Z"
          },
          {
            "deviceUUID": "29bd9b5f-da9e-f1ad-e1dc-24f5a2a3e814",
            "lastSuccessfulCheckTime": "2022-01-27T19:12:33Z"
          },
          {
            "deviceUUID": "d6fab79b-cbd1-9ed8-af64-302303a62234",
            "lastSuccessfulCheckTime": "2022-01-27T19:12:34Z"
          }
        ]
      },
      "guest_network": {
        "isGuestNetworkACaptivePortal": false,
        "isGuestNetworkEnabled": false,
        "radios": [
          {
            "radioID": "RADIO_2.4GHz",
            "isEnabled": true,
            "broadcastGuestSSID": true,
            "guestSSID": "**REDACTED**",
            "guestWPAPassphrase": "**REDACTED**",
            "canEnableRadio": true
          },
          {
            "radioID": "RADIO_5GHz",
            "isEnabled": true,
            "broadcastGuestSSID": true,
            "guestSSID": "**REDACTED**",
            "guestWPAPassphrase": "**REDACTED**",
            "canEnableRadio": true
          }
        ]
      },
      "parental_control": {
        "isParentalControlEnabled": false,
        "rules": [],
        "maxRuleDescriptionLength": 32,
        "maxRuleMACAddresses": 10,
        "maxRuleBlockedURLLength": 32,
        "maxRuleBlockedURLs": 10,
        "maxRules": 14
      },
      "speedtest_results": [
        {
          "timestamp": "2022-01-25T14:59:03Z",
          "exit_code": "Success",
          "latency": 15,
          "upload_bandwidth": 36782,
          "download_bandwidth": 382667,
          "result_id": 97459
        }
      ],
      "speedtest_state": "",
      "wan_info": {
        "supportedWANTypes": [
          "DHCP",
          "Static",
          "PPPoE",
          "PPTP",
          "L2TP",
          "Bridge"
        ],
        "supportedIPv6WANTypes": [
          "Automatic",
          "PPPoE",
          "Pass-through"
        ],
        "supportedWANCombinations": [
          {
            "wanType": "DHCP",
            "wanIPv6Type": "Automatic"
          },
          {
            "wanType": "Static",
            "wanIPv6Type": "Automatic"
          },
          {
            "wanType": "PPPoE",
            "wanIPv6Type": "Automatic"
          },
          {
            "wanType": "L2TP",
            "wanIPv6Type": "Automatic"
          },
          {
            "wanType": "PPTP",
            "wanIPv6Type": "Automatic"
          },
          {
            "wanType": "Bridge",
            "wanIPv6Type": "Automatic"
          },
          {
            "wanType": "DHCP",
            "wanIPv6Type": "Pass-through"
          },
          {
            "wanType": "PPPoE",
            "wanIPv6Type": "PPPoE"
          }
        ],
        "isDetectingWANType": false,
        "detectedWANType": "DHCP",
        "wanStatus": "Connected",
        "wanConnection": {
          "wanType": "DHCP",
          "ipAddress": "**REDACTED**",
          "networkPrefixLength": 23,
          "gateway": "**REDACTED**",
          "mtu": 0,
          "dhcpLeaseMinutes": 10080,
          "dnsServer1": "194.168.4.100",
          "dnsServer2": "194.168.8.100"
        },
        "wanIPv6Status": "Connecting",
        "linkLocalIPv6Address": "fe80:0000:0000:0000:ea9f:80ff:fe60:c837",
        "macAddress": "**REDACTED**"
      }
    },
    "nodes": [
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "614b8c65-c044-ee54-3052-e89f8060c837",
          "lastChangeRevision": 141795,
          "model": {
            "deviceType": "Infrastructure",
            "manufacturer": "Linksys",
            "modelNumber": "MX42",
            "hardwareVersion": "1",
            "description": "Velop AX4200 WiFi 6 System"
          },
          "unit": {
            "serialNumber": "38U10M3BA40594",
            "firmwareVersion": "1.0.11.208553",
            "firmwareDate": "2021-09-16T18:21:28Z"
          },
          "isAuthority": true,
          "nodeType": "Master",
          "isHomeKitSupported": true,
          "friendlyName": "router",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.254"
            }
          ],
          "properties": [
            {
              "name": "userDeviceLocation",
              "value": "Lounge"
            },
            {
              "name": "userDeviceName",
              "value": "Lounge"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "backhaul": {},
          "updates": {
            "deviceUUID": "614b8c65-c044-ee54-3052-e89f8060c837",
            "lastSuccessfulCheckTime": "2022-01-27T19:12:34Z"
          }
        },
        "connected_devices": [
          {
            "name": "Mumbie - Phone",
            "ip": "192.168.123.49",
            "type": "Wireless"
          },
          {
            "name": "Bedroom - Meross",
            "ip": "192.168.123.196",
            "type": "Wireless"
          },
          {
            "name": "Back Bedroom - Meross",
            "ip": "192.168.123.195",
            "type": "Wireless"
          },
          {
            "name": "Lounge - Meross Extension",
            "ip": "192.168.123.198",
            "type": "Wireless"
          },
          {
            "name": "Lounge - Meross Chargers",
            "ip": "192.168.123.199",
            "type": "Wireless"
          },
          {
            "name": "Lounge - Meross",
            "ip": "192.168.123.194",
            "type": "Wireless"
          },
          {
            "name": "Lounge - Roku",
            "ip": "192.168.123.35",
            "type": "Wireless"
          },
          {
            "name": "Lounge - Blink SM2",
            "ip": "192.168.123.22",
            "type": "Wireless"
          },
          {
            "name": "Lounge - Meross Alcove",
            "ip": "192.168.123.191",
            "type": "Wireless"
          },
          {
            "name": "Lounge - Meross Alcove Cupboard",
            "ip": "192.168.123.190",
            "type": "Wireless"
          },
          {
            "name": "Bedroom - Meross Bed",
            "ip": "192.168.123.197",
            "type": "Wireless"
          },
          {
            "name": "Bedroom - Harmony Hub",
            "ip": "192.168.123.245",
            "type": "Wireless"
          },
          {
            "name": "Bedroom - HEOS",
            "ip": "192.168.123.71",
            "type": "Wireless"
          },
          {
            "name": "Back Bedroom - HEOS",
            "ip": "192.168.123.57",
            "type": "Wireless"
          },
          {
            "name": "Hallway - Nest Thermostat",
            "ip": "192.168.123.43",
            "type": "Wireless"
          },
          {
            "name": "Office - Printer",
            "ip": "192.168.123.3",
            "type": "Wireless"
          },
          {
            "name": "Bedroom - TiVo",
            "ip": "192.168.123.239",
            "type": "Wireless"
          },
          {
            "name": "Lounge - TiVo",
            "ip": "192.168.123.241",
            "type": "Wireless"
          },
          {
            "name": "Lounge - Ring Chime",
            "ip": "192.168.123.6",
            "type": "Wireless"
          },
          {
            "name": "VM - dbserver",
            "ip": "192.168.123.250",
            "type": "Unknown"
          },
          {
            "name": "Lounge - Pi Hole",
            "ip": "192.168.123.238",
            "type": "Wired"
          },
          {
            "name": "Front Bedroom - Hubitat",
            "ip": "192.168.123.242",
            "type": "Wired"
          },
          {
            "name": "Bedroom - OSMC",
            "ip": "192.168.123.16",
            "type": "Wired"
          },
          {
            "name": "VM - rproxy",
            "ip": "192.168.123.236",
            "type": "Wired"
          },
          {
            "name": "Bedroom - HDHomeRun",
            "ip": "192.168.123.10",
            "type": "Unknown"
          },
          {
            "name": "Garden - Camera",
            "ip": "192.168.123.37",
            "type": "Wireless"
          },
          {
            "name": "Lounge - HEOS Bar",
            "ip": "192.168.123.18",
            "type": "Wireless"
          },
          {
            "name": "James - Work Laptop (Wired)",
            "ip": "192.168.123.62",
            "type": "Unknown"
          },
          {
            "name": "Lounge - Harmony Hub",
            "ip": "192.168.123.248",
            "type": "Wireless"
          },
          {
            "name": "HASS Test (WiFi)",
            "ip": "192.168.123.69",
            "type": "Wireless"
          },
          {
            "name": "HASS Test (Wired)",
            "ip": "192.168.123.189",
            "type": "Wired"
          },
          {
            "name": "James - Running Phone",
            "ip": "192.168.123.68",
            "type": "Wireless"
          },
          {
            "name": "Lounge - Twinkly Music",
            "ip": "192.168.123.5",
            "type": "Wireless"
          }
        ]
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "29bd9b5f-da9e-f1ad-e1dc-24f5a2a3e814",
          "lastChangeRevision": 140815,
          "model": {
            "deviceType": "Infrastructure",
            "manufacturer": "Linksys",
            "modelNumber": "WHW01",
            "hardwareVersion": "1",
            "description": "Velop"
          },
          "unit": {
            "serialNumber": "25F10604844966",
            "firmwareVersion": "1.1.13.202617",
            "firmwareDate": "2020-09-05T12:34:29Z"
          },
          "isAuthority": false,
          "nodeType": "Slave",
          "isHomeKitSupported": false,
          "friendlyName": "LINKSYS44966",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            },
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "5GHz"
            },
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            },
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.31"
            }
          ],
          "properties": [
            {
              "name": "userDeviceLocation",
              "value": "Utility"
            },
            {
              "name": "userDeviceName",
              "value": "Utility"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "backhaul": {
            "deviceUUID": "29bd9b5f-da9e-f1ad-e1dc-24f5a2a3e814",
            "ipAddress": "192.168.123.31",
            "parentIPAddress": "192.168.123.254",
            "connectionType": "Wireless",
            "wirelessConnectionInfo": {
              "radioID": "5GL",
              "channel": 48,
              "apRSSI": -82,
              "stationRSSI": -74,
              "apBSSID": "**REDACTED**",
              "stationBSSID": "**REDACTED**"
            },
            "speedMbps": "116.287",
            "timestamp": "2022-01-28T14:21:18Z"
          },
          "updates": {
            "deviceUUID": "29bd9b5f-da9e-f1ad-e1dc-24f5a2a3e814",
            "lastSuccessfulCheckTime": "2022-01-27T19:12:33Z"
          }
        },
        "connected_devices": []
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "d6fab79b-cbd1-9ed8-af64-302303a62234",
          "lastChangeRevision": 141758,
          "model": {
            "deviceType": "Infrastructure",
            "manufacturer": "Linksys",
            "modelNumber": "WHW01P",
            "hardwareVersion": "1",
            "description": "Velop Plug-In"
          },
          "unit": {
            "serialNumber": "29A10606900954",
            "firmwareVersion": "1.1.13.202795",
            "firmwareDate": "2020-09-21T17:45:30Z"
          },
          "isAuthority": false,
          "nodeType": "Slave",
          "isHomeKitSupported": false,
          "friendlyName": "LINKSYS00954",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            },
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "5GHz"
            },
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            },
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.27",
              "parentDeviceID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870"
            }
          ],
          "properties": [
            {
              "name": "userDeviceLocation",
              "value": "Bedroom"
            },
            {
              "name": "userDeviceName",
              "value": "Bedroom"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "backhaul": {
            "deviceUUID": "d6fab79b-cbd1-9ed8-af64-302303a62234",
            "ipAddress": "192.168.123.27",
            "parentIPAddress": "192.168.123.254",
            "connectionType": "Wireless",
            "wirelessConnectionInfo": {
              "radioID": "5GL",
              "channel": 48,
              "apRSSI": -53,
              "stationRSSI": -54,
              "apBSSID": "**REDACTED**",
              "stationBSSID": "**REDACTED**"
            },
            "speedMbps": "20.428",
            "timestamp": "2022-01-28T14:21:25Z"
          },
          "updates": {
            "deviceUUID": "d6fab79b-cbd1-9ed8-af64-302303a62234",
            "lastSuccessfulCheckTime": "2022-01-27T19:12:34Z"
          }
        },
        "connected_devices": []
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870",
          "lastChangeRevision": 124089,
          "model": {
            "deviceType": "Infrastructure",
            "manufacturer": "Linksys",
            "modelNumber": "WHW01",
            "hardwareVersion": "1",
            "description": "Velop"
          },
          "unit": {
            "serialNumber": "25F10604844989",
            "firmwareVersion": "1.1.13.202617",
            "firmwareDate": "2020-09-05T12:34:29Z"
          },
          "isAuthority": false,
          "nodeType": "Slave",
          "isHomeKitSupported": false,
          "friendlyName": "LINKSYS44989",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.44",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceLocation",
              "value": "Front Bedroom"
            },
            {
              "name": "userDeviceName",
              "value": "Front Bedroom"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "backhaul": {
            "deviceUUID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870",
            "ipAddress": "192.168.123.44",
            "parentIPAddress": "192.168.123.254",
            "connectionType": "Wired",
            "speedMbps": "1024",
            "timestamp": "2022-01-28T14:21:06Z"
          },
          "updates": {
            "deviceUUID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870",
            "lastSuccessfulCheckTime": "2022-01-27T19:12:34Z"
          }
        },
        "connected_devices": [
          {
            "name": "Front Bedroom - HEOS",
            "ip": "192.168.123.28",
            "type": "Wireless"
          },
          {
            "name": "Driveway - Camera",
            "ip": "192.168.123.41",
            "type": "Wireless"
          },
          {
            "name": "Lounge - TV",
            "ip": "192.168.123.243",
            "type": "Wired"
          },
          {
            "name": "Lounge - OSMC",
            "ip": "192.168.123.21",
            "type": "Wired"
          },
          {
            "name": "Front Bedroom - Harmony Hub",
            "ip": "192.168.123.246",
            "type": "Wireless"
          },
          {
            "name": "Front Bedroom - Meross",
            "ip": "192.168.123.193",
            "type": "Wireless"
          },
          {
            "name": "IPMI",
            "ip": "192.168.123.237",
            "type": "Wired"
          },
          {
            "name": "storage",
            "ip": "192.168.123.244",
            "type": "Unknown"
          },
          {
            "name": "Lounge - LightwaveRF LinkPlus",
            "ip": "192.168.123.15",
            "type": "Wired"
          },
          {
            "name": "VM - tvserver",
            "ip": "192.168.123.240",
            "type": "Wired"
          },
          {
            "name": "VM - vpnserver",
            "ip": "192.168.123.251",
            "type": "Wired"
          },
          {
            "name": "Porch - Ring Doorbell",
            "ip": "192.168.123.48",
            "type": "Wireless"
          },
          {
            "name": "VM - nextcloud",
            "ip": "192.168.123.252",
            "type": "Wired"
          }
        ]
      }
    ],
    "devices": [
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "76a5f29d-00c0-48ff-be05-be99a8fb6061",
          "lastChangeRevision": 141878,
          "model": {
            "deviceType": "Mobile"
          },
          "unit": {
            "operatingSystem": "Android"
          },
          "isAuthority": false,
          "friendlyName": "Android-2",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "5GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.49",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceOS",
              "value": "Android 11"
            },
            {
              "name": "userDeviceName",
              "value": "Mumbie - Phone"
            },
            {
              "name": "userDeviceType",
              "value": "smartphone"
            },
            {
              "name": "userDeviceManufacturer",
              "value": "Oneplus"
            },
            {
              "name": "userDeviceModelNumber",
              "value": "IN2023"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "68eaffe2-8f62-4ba9-b37b-b2cc93b7b57d",
          "lastChangeRevision": 141883,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "Meross_Smart_Switch",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.196",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Bedroom - Meross"
            },
            {
              "name": "userDeviceType",
              "value": "power-strip"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "b83856e8-e22a-4480-b927-85ecd077059c",
          "lastChangeRevision": 141875,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.195",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Back Bedroom - Meross"
            },
            {
              "name": "userDeviceType",
              "value": "power-strip"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "2e2aedaf-c664-4999-bf0d-39e7d3c9e20c",
          "lastChangeRevision": 141892,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.198",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - Meross Extension"
            },
            {
              "name": "userDeviceType",
              "value": "power-strip"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "f785a815-2a41-4ae6-94b2-ec4aefe38aaf",
          "lastChangeRevision": 141874,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.199",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - Meross Chargers"
            },
            {
              "name": "userDeviceType",
              "value": "power-strip"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "b2a76d32-32be-42bd-bb22-4034877586fe",
          "lastChangeRevision": 141871,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.194",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - Meross"
            },
            {
              "name": "userDeviceType",
              "value": "power-strip"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "2ddf2f78-d488-4a89-a0ce-c19cdd7edac8",
          "lastChangeRevision": 141849,
          "model": {
            "deviceType": "MediaPlayer",
            "manufacturer": "Roku, Inc.",
            "modelNumber": "3810EU",
            "description": "Roku Streaming Player Network Media"
          },
          "unit": {
            "serialNumber": "YH009T524285"
          },
          "isAuthority": false,
          "friendlyName": "Streaming Stick+",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "5GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.35",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - Roku"
            },
            {
              "name": "userDeviceType",
              "value": "media-stick"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "af0d9fa6-081d-44fc-9689-d8fe4096cc35",
          "lastChangeRevision": 141854,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "blink-sync-module",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.22",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - Blink SM2"
            },
            {
              "name": "userDeviceType",
              "value": "wemo-maker"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "513addaa-77aa-4580-9997-57f0a263e64f",
          "lastChangeRevision": 141890,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.191",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - Meross Alcove"
            },
            {
              "name": "userDeviceType",
              "value": "power-strip"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "6b3c893c-9144-4014-aa47-ac049b6538f9",
          "lastChangeRevision": 141870,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.190",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - Meross Alcove Cupboard"
            },
            {
              "name": "userDeviceType",
              "value": "power-strip"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "eacf19a9-f2e4-47d4-87a8-f38188ce85b2",
          "lastChangeRevision": 141877,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.197",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Bedroom - Meross Bed"
            },
            {
              "name": "userDeviceType",
              "value": "power-strip"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "e44c7208-211a-4911-af38-8bd500cd9575",
          "lastChangeRevision": 141879,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.245",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Bedroom - Harmony Hub"
            },
            {
              "name": "userDeviceType",
              "value": "linksys-bridge"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "058cf556-5c6a-4f9a-9e35-1c17c24dfa65",
          "lastChangeRevision": 141869,
          "model": {
            "deviceType": "MediaPlayer",
            "manufacturer": "Denon",
            "modelNumber": "HEOS 1"
          },
          "unit": {
            "serialNumber": "ACLG9170717839"
          },
          "isAuthority": false,
          "friendlyName": "Bedroom",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.71",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Bedroom - HEOS"
            },
            {
              "name": "userDeviceType",
              "value": "apple-homepod"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Front Bedroom",
        "raw_attributes": {
          "deviceID": "4fcd5873-940e-4380-a932-5b2ca79e6edc",
          "lastChangeRevision": 141866,
          "model": {
            "deviceType": "MediaPlayer",
            "manufacturer": "Denon",
            "modelNumber": "HEOS 1"
          },
          "unit": {
            "serialNumber": "ACLG9170819787"
          },
          "isAuthority": false,
          "friendlyName": "Front Bedroom",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.28",
              "parentDeviceID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Front Bedroom - HEOS"
            },
            {
              "name": "userDeviceType",
              "value": "apple-homepod"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "578ac274-1cf1-4a6d-842d-8e9802c18be6",
          "lastChangeRevision": 141872,
          "model": {
            "deviceType": "MediaPlayer",
            "manufacturer": "Denon",
            "modelNumber": "HEOS 1"
          },
          "unit": {
            "serialNumber": "ACLG9170717841"
          },
          "isAuthority": false,
          "friendlyName": "Back Bedroom",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "5GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.57",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Back Bedroom - HEOS"
            },
            {
              "name": "userDeviceType",
              "value": "apple-homepod"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "30be2507-652c-49ce-88c6-8a5cb11edace",
          "lastChangeRevision": 141867,
          "model": {
            "deviceType": "",
            "manufacturer": "Nest Labs Inc."
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "5GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.43",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Hallway - Nest Thermostat"
            },
            {
              "name": "userDeviceType",
              "value": "amazon-spot"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "2f0c4ab3-ee1b-43cf-858f-43e3cb2c35db",
          "lastChangeRevision": 141893,
          "model": {
            "deviceType": "Printer"
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "8C0D3A000000",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.3",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Office - Printer"
            },
            {
              "name": "userDeviceType",
              "value": "printer-inkjet"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "af58a817-d099-4083-a994-6c6c3b9ba225",
          "lastChangeRevision": 141862,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "757D",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "5GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.239",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Bedroom - TiVo"
            },
            {
              "name": "userDeviceType",
              "value": "digital-media-player"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "e5956056-76a0-4c98-9724-cc2686d5904b",
          "lastChangeRevision": 141889,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "E40B",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "5GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.241",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - TiVo"
            },
            {
              "name": "userDeviceType",
              "value": "digital-media-player"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "1e9e055b-bfe2-454c-8308-2927197ddf13",
          "lastChangeRevision": 141880,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "94E36D74E0AF-mysimplelink",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.6",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - Ring Chime"
            },
            {
              "name": "userDeviceType",
              "value": "linksys-extender"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "df665b96-8fc7-4e7d-8f41-7bfdfc9da277",
          "lastChangeRevision": 141923,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.250",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "VM - dbserver"
            },
            {
              "name": "userDeviceType",
              "value": "amazon-tap"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Front Bedroom",
        "raw_attributes": {
          "deviceID": "6fe03ca5-6412-45b9-bf18-d4cf28dc87b4",
          "lastChangeRevision": 141887,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "G24676640",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.41",
              "parentDeviceID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Driveway - Camera"
            },
            {
              "name": "userDeviceType",
              "value": "nest-cam"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "75e5f238-5ecc-4f57-8722-aea622dc7996",
          "lastChangeRevision": 141914,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "pihole2",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.238",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - Pi Hole"
            },
            {
              "name": "userDeviceType",
              "value": "amazon-tap"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "06e4b01a-0b7f-4e3a-9b69-b86e498b5cd9",
          "lastChangeRevision": 141846,
          "model": {
            "deviceType": "Computer",
            "manufacturer": "Roku",
            "modelNumber": "Roku 4",
            "description": "Emulated Roku"
          },
          "unit": {
            "serialNumber": "Bedroom - HASS",
            "operatingSystem": "Windows 7"
          },
          "isAuthority": false,
          "friendlyName": "KD-65XF9005",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Office - HASS"
            },
            {
              "name": "userDeviceType",
              "value": "amazon-tap"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Front Bedroom",
        "raw_attributes": {
          "deviceID": "b62064f2-1ce0-4fe2-85df-4d99c811eaa7",
          "lastChangeRevision": 141855,
          "model": {
            "deviceType": "MediaPlayer",
            "manufacturer": "SONY Visual Products Inc.",
            "modelNumber": "MediaRenderer",
            "description": "Sony 2017 4K TV"
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "KD-65XF9005",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.243",
              "parentDeviceID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - TV"
            },
            {
              "name": "userDeviceType",
              "value": "generic-display"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Front Bedroom",
        "raw_attributes": {
          "deviceID": "24415074-e65a-4c3f-9ba0-146544665a21",
          "lastChangeRevision": 141863,
          "model": {
            "deviceType": "",
            "manufacturer": "XBMC Foundation",
            "modelNumber": "Kodi",
            "description": "Kodi - Media Server"
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "osmc-lounge",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.21",
              "parentDeviceID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - OSMC"
            },
            {
              "name": "userDeviceType",
              "value": "set-top-box"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "dcef273d-ef80-4220-a43f-12f75d54356a",
          "lastChangeRevision": 141864,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "hubitat",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.242",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Front Bedroom - Hubitat"
            },
            {
              "name": "userDeviceType",
              "value": "automation-hub"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Front Bedroom",
        "raw_attributes": {
          "deviceID": "a960d199-fcbf-4521-86bb-e61c008187de",
          "lastChangeRevision": 141865,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.246",
              "parentDeviceID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Front Bedroom - Harmony Hub"
            },
            {
              "name": "userDeviceType",
              "value": "linksys-bridge"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Front Bedroom",
        "raw_attributes": {
          "deviceID": "9c5e7e66-ff21-4eb9-9809-0784fc8bba2e",
          "lastChangeRevision": 141888,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.193",
              "parentDeviceID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Front Bedroom - Meross"
            },
            {
              "name": "userDeviceType",
              "value": "power-strip"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "cf9a4283-5787-4ed2-aa39-736ccff83e9e",
          "lastChangeRevision": 141868,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "osmc-bed1",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.16",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Bedroom - OSMC"
            },
            {
              "name": "userDeviceType",
              "value": "set-top-box"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "26319515-24e1-4b74-b53b-e4faacbc44c3",
          "lastChangeRevision": 141856,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "rproxy",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.236",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "VM - rproxy"
            },
            {
              "name": "userDeviceType",
              "value": "amazon-tap"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Front Bedroom",
        "raw_attributes": {
          "deviceID": "3d24e810-41bc-4074-8e28-a11afacf4698",
          "lastChangeRevision": 141853,
          "model": {
            "deviceType": "",
            "manufacturer": "American Megatrends Inc",
            "modelNumber": "AMI SPX",
            "description": "AMI Serivce Processor Stack SPX running on AST2050 SOC on AST2050EVB"
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "AMID05099E17326",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.237",
              "parentDeviceID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "IPMI"
            },
            {
              "name": "userDeviceType",
              "value": "generic-device"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Front Bedroom",
        "raw_attributes": {
          "deviceID": "c958bb18-3fff-4be7-b8a6-db1a079ee607",
          "lastChangeRevision": 141885,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "storage",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.244",
              "parentDeviceID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "storage"
            },
            {
              "name": "userDeviceType",
              "value": "server-pc"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Front Bedroom",
        "raw_attributes": {
          "deviceID": "45a8e7ac-306a-489d-883b-d47800c528ef",
          "lastChangeRevision": 141881,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "LIGHTWAVE-311102",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.15",
              "parentDeviceID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - LightwaveRF LinkPlus"
            },
            {
              "name": "userDeviceType",
              "value": "wemo-link"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Front Bedroom",
        "raw_attributes": {
          "deviceID": "e7e33734-b896-47c0-b339-57ddddc8acf5",
          "lastChangeRevision": 141884,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "tvserver2",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.240",
              "parentDeviceID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "VM - tvserver"
            },
            {
              "name": "userDeviceType",
              "value": "amazon-tap"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Front Bedroom",
        "raw_attributes": {
          "deviceID": "5a2896eb-5ae4-4d02-9344-a0230517ef17",
          "lastChangeRevision": 141876,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "wireguard",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.251",
              "parentDeviceID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "VM - vpnserver"
            },
            {
              "name": "userDeviceType",
              "value": "amazon-tap"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Front Bedroom",
        "raw_attributes": {
          "deviceID": "e2f5aa24-ece6-4033-aa5b-09b3838e614f",
          "lastChangeRevision": 141858,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.48",
              "parentDeviceID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Porch - Ring Doorbell"
            },
            {
              "name": "userDeviceType",
              "value": "wemo-lightswitch"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "da389c2c-3251-4ff3-809c-9d0eefa517eb",
          "lastChangeRevision": 141857,
          "model": {
            "deviceType": "",
            "manufacturer": "Silicondust",
            "modelNumber": "HDHomeRun CONNECT QUATRO",
            "description": "HDHR5-4DT HDHomeRun CONNECT QUATRO"
          },
          "unit": {
            "serialNumber": "1251129F"
          },
          "isAuthority": false,
          "friendlyName": "HDHomeRun DMS 1251129F",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.10",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Bedroom - HDHomeRun"
            },
            {
              "name": "userDeviceType",
              "value": "device-router"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Front Bedroom",
        "raw_attributes": {
          "deviceID": "0a27cb72-517d-4c9e-9957-4646062f1155",
          "lastChangeRevision": 141873,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.252",
              "parentDeviceID": "2041f9d7-07bd-7e3a-c83a-24f5a2a3e870"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "VM - nextcloud"
            },
            {
              "name": "userDeviceType",
              "value": "amazon-tap"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "e42437a0-81d7-45b1-b658-8a20851aebc4",
          "lastChangeRevision": 141916,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "DAR-L36509",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.37",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Garden - Camera"
            },
            {
              "name": "userDeviceType",
              "value": "nest-cam"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "94526dce-9bfd-4113-88a3-1d886789555c",
          "lastChangeRevision": 141909,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "Android",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Hiney - Phone"
            },
            {
              "name": "userDeviceType",
              "value": "android-white"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "0d315c55-601f-4534-bfed-5f26187c43e0",
          "lastChangeRevision": 141851,
          "model": {
            "deviceType": "MediaPlayer",
            "manufacturer": "Denon",
            "modelNumber": "HEOS Bar"
          },
          "unit": {
            "serialNumber": "ADAG9161202349"
          },
          "isAuthority": false,
          "friendlyName": "Lounge",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "5GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.18",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - HEOS Bar"
            },
            {
              "name": "userDeviceType",
              "value": "sound-bar"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "33e572c0-1f06-4ad1-8f24-56a15f5dbe3b",
          "lastChangeRevision": 141906,
          "model": {
            "deviceType": "Computer"
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "DAR-L36509",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.62",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "James - Work Laptop (Wired)"
            },
            {
              "name": "userDeviceType",
              "value": "laptop-pc"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "c7fda7b1-2831-4d37-a726-21c2daf118fe",
          "lastChangeRevision": 141651,
          "model": {
            "deviceType": "MediaPlayer",
            "manufacturer": "Panasonic",
            "modelNumber": "Panasonic VIErA",
            "description": ""
          },
          "unit": {
            "serialNumber": ""
          },
          "isAuthority": false,
          "friendlyName": "TV-Bedroom",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Bedroom - TV"
            },
            {
              "name": "userDeviceType",
              "value": "generic-display"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "32ffa2da-0581-4a20-88b1-09d5291de4aa",
          "lastChangeRevision": 141850,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.248",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - Harmony Hub"
            },
            {
              "name": "userDeviceType",
              "value": "linksys-bridge"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "4f01942e-3569-488c-abe4-7497a1143eab",
          "lastChangeRevision": 141912,
          "model": {
            "deviceType": "Computer"
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "KD-65XF9005",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "James - Work Laptop (WiFi)"
            },
            {
              "name": "userDeviceType",
              "value": "laptop-pc"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "6134154e-a3be-4d1c-bbb5-bbcb484822b4",
          "lastChangeRevision": 141751,
          "model": {
            "deviceType": "",
            "manufacturer": "Nest Labs Inc."
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Hallway - Nest Protect"
            },
            {
              "name": "userDeviceType",
              "value": "smart-smoke-detector"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "03fb3a22-6294-40a7-8449-884a07755297",
          "lastChangeRevision": 141894,
          "model": {
            "deviceType": "",
            "manufacturer": "Nest Labs Inc."
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Landing - Nest Protect"
            },
            {
              "name": "userDeviceType",
              "value": "smart-smoke-detector"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "0dad2515-5d5d-4a24-b65c-de3def79e74a",
          "lastChangeRevision": 141662,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Hallway - Camera"
            },
            {
              "name": "userDeviceType",
              "value": "wemo-netcam"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "9120d827-c2b6-4867-93c9-b4e732e1e2e0",
          "lastChangeRevision": 137051,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - Camera"
            },
            {
              "name": "userDeviceType",
              "value": "wemo-netcam"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "72566b66-3d53-43e1-9d13-f1ef1d4b7562",
          "lastChangeRevision": 141661,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - Camera Main"
            },
            {
              "name": "userDeviceType",
              "value": "net-camera"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "fcc5b2e8-8cbd-4722-bb4f-33793cfc616c",
          "lastChangeRevision": 135957,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "James - Watch"
            },
            {
              "name": "userDeviceType",
              "value": "smart-watch"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "28f0fbcc-7e16-4836-b948-8ded6c1e82b1",
          "lastChangeRevision": 0,
          "model": {
            "deviceType": "Computer"
          },
          "unit": {
            "operatingSystem": "Windows 10"
          },
          "isAuthority": false,
          "friendlyName": "JAMES-LAPTOP",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Laptop (WiFi)"
            },
            {
              "name": "userDeviceType",
              "value": "laptop-pc"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "87fd6075-e068-46cb-b144-90a5116af55f",
          "lastChangeRevision": 141886,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "hass-test",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "5GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.69",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "HASS Test (WiFi)"
            },
            {
              "name": "userDeviceType",
              "value": "amazon-tap"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "f471f897-aff5-4a9c-9927-cbf0bb54a877",
          "lastChangeRevision": 141917,
          "model": {
            "deviceType": "Printer"
          },
          "unit": {},
          "isAuthority": false,
          "friendlyName": "KD-65XF9005",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wired"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.189",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "HASS Test (Wired)"
            },
            {
              "name": "userDeviceType",
              "value": "amazon-tap"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "367b2021-11e3-46ed-8ba1-e46045227282",
          "lastChangeRevision": 47101,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [],
          "properties": [],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "87e2a715-85aa-467e-91c2-cdeefb9f778a",
          "lastChangeRevision": 22526,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [],
          "properties": [],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "cf4edb8f-96e9-426a-a62d-2259625ddcd8",
          "lastChangeRevision": 112102,
          "model": {
            "deviceType": "MediaPlayer",
            "manufacturer": "Denon",
            "modelNumber": "HEOS 1"
          },
          "unit": {
            "serialNumber": "ACLG9170819649"
          },
          "isAuthority": false,
          "friendlyName": "Lounge - RL",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [],
          "properties": [],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "954af070-3c32-43b2-b886-c49af8b5abd3",
          "lastChangeRevision": 112101,
          "model": {
            "deviceType": "MediaPlayer",
            "manufacturer": "Denon",
            "modelNumber": "HEOS 1"
          },
          "unit": {
            "serialNumber": "ACLG9170819567"
          },
          "isAuthority": false,
          "friendlyName": "Lounge - RR",
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [],
          "properties": [],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": null,
        "raw_attributes": {
          "deviceID": "8d3ba484-092f-405d-90f5-c9c700c4dbfb",
          "lastChangeRevision": 123847,
          "model": {
            "deviceType": "",
            "manufacturer": "OnePlus Technology (Shenzhen) Co., Ltd"
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Unknown"
            }
          ],
          "connections": [],
          "properties": [],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "4b9bff09-3c5c-4101-8e27-42e197fe4760",
          "lastChangeRevision": 141931,
          "model": {
            "deviceType": "",
            "manufacturer": "Samsung Electronics Co., Ltd."
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "5GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.68",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "James - Running Phone"
            },
            {
              "name": "userDeviceType",
              "value": "android-white"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      },
      {
        "parent_name": "Lounge",
        "raw_attributes": {
          "deviceID": "dc932c51-2cc3-4d99-8b92-5aaff502d33d",
          "lastChangeRevision": 141848,
          "model": {
            "deviceType": ""
          },
          "unit": {},
          "isAuthority": false,
          "knownInterfaces": [
            {
              "macAddress": "**REDACTED**",
              "interfaceType": "Wireless",
              "band": "2.4GHz"
            }
          ],
          "connections": [
            {
              "macAddress": "**REDACTED**",
              "ipAddress": "192.168.123.5",
              "parentDeviceID": "614b8c65-c044-ee54-3052-e89f8060c837"
            }
          ],
          "properties": [
            {
              "name": "userDeviceName",
              "value": "Lounge - Twinkly Music"
            },
            {
              "name": "userDeviceType",
              "value": "media-stick"
            }
          ],
          "maxAllowedProperties": 16,
          "results_time": 1643379790,
          "parental_controls": []
        }
      }
    ]
  }
}
```
</details>

# Example Lovelace UI

| Dark Mode | Light Mode |
|:---:|:---:|
| ![Lovelace Dark UI](images/lovelace_dark.png) | ![Lovelace Light UI](images/lovelace_light.png) |

*Some items of detail have been pixelated for privacy purposes.*

To create this view a number of custom cards have been used.  These are: -

- [Button Card](https://github.com/custom-cards/button-card)
- [Config Template Card](https://github.com/thomasloven/lovelace-hui-element)
- [Stack In Card](https://github.com/custom-cards/stack-in-card)
- [auto-entities](https://github.com/thomasloven/lovelace-auto-entities)
- [card-mod](https://github.com/thomasloven/lovelace-card-mod)
- [fold-entity-row](https://github.com/thomasloven/lovelace-fold-entity-row)
- [hui-element](https://github.com/thomasloven/lovelace-hui-element)
- [template-entity-row](https://github.com/thomasloven/lovelace-template-entity-row)

<details>
  <summary>YAML for the view</summary>

  ```yaml
  - title: Velop
    path: velop
    badges: []
    cards:
      - type: custom:button-card
        color_type: blank-card
      - type: custom:stack-in-card
        cards:
          - type: custom:button-card
            entity: binary_sensor.velop_mesh_wan_status
            show_name: false
            icon: hass:web
            tap_action:
              action: none
            custom_fields:
              attr_dns_servers: '[[[ return entity.attributes.dns ]]]'
              attr_public_ip: '[[[ return entity.attributes.ip ]]]'
              attr_speedtest_latest: |
                [[[
                  var entity_speedtest = states['sensor.velop_mesh_speedtest_latest']          
                  var d = new Date(entity_speedtest.state)
                  return d.toLocaleString()
                ]]]
              attr_speedtest_details: |
                [[[
                  var round2 = (num) => Math.round(num * 100) / 100
                  var spacing_internal = 5
                  var spacing_external = 30
                  var icon_size = 22
                  var entity_speedtest = states['sensor.velop_mesh_speedtest_latest']
                  var latency = entity_speedtest.attributes.latency
                  var download_bandwidth = round2(entity_speedtest.attributes.download_bandwidth / 1000)
                  var upload_bandwidth = round2(entity_speedtest.attributes.upload_bandwidth / 1000)        

                  return `<span style="margin-right: ${spacing_external}px;">
                            <ha-icon icon="hass:swap-horizontal" style="width: ${icon_size}px;"></ha-icon>
                            <span>${latency}ms</span>
                          </span>
                          <span style="margin-right: ${spacing_external}px;">
                            <ha-icon icon="hass:cloud-download-outline" style="width: ${icon_size}px;"></ha-icon>
                            <span>${download_bandwidth} Mbps</span>
                          </span>
                          <span>
                            <ha-icon icon="hass:cloud-upload-outline" style="width: ${icon_size}px;"></ha-icon>
                            <span>${upload_bandwidth} Mbps</span>
                          </span>
                          `
                ]]]
            state:
              - value: 'on'
                color: darkcyan
              - value: 'off'
                color: darkred
            styles:
              card:
                - padding: 16px
              grid:
                - grid-template-areas: >-
                    "attr_dns_servers . attr_public_ip" "i i i"
                    "attr_speedtest_details attr_speedtest_details
                    attr_speedtest_details" "attr_speedtest_latest
                    attr_speedtest_latest attr_speedtest_latest"
                - grid-template-rows: 5% 1fr 15% 5%
                - grid-template-columns: 1fr min-content 1fr
              custom_fields:
                attr_dns_servers:
                  - justify-self: self-start
                attr_public_ip:
                  - justify-self: self-end
            extra_styles: >
              div[id^="attr_"] { font-size: smaller; color:
              var(--disabled-text-color);

              }

              div[id^="attr_speedtest_"] { margin-top: 10px; }

              #attr_speedtest_latest::before { content: 'As at:' }

              #attr_public_ip::before { content: 'Public IP: ' }

              #attr_dns_servers::before { content: 'DNS: ' }
          - type: entities
            entities:
              - type: conditional
                conditions:
                  - entity: binary_sensor.velop_mesh_speedtest_status
                    state: 'on'
                row:
                  type: section
              - type: conditional
                card_mod:
                  style:
                    template-entity-row$: >
                      state-badge, div.state { display: none; }

                      div.info { text-align: center !important; width: 100%;
                      margin: 0; padding: 4px; }
                conditions:
                  - entity: binary_sensor.velop_mesh_speedtest_status
                    state: 'on'
                row:
                  type: custom:button-card
                  entity: binary_sensor.velop_mesh_speedtest_status
                  show_icon: false
                  show_name: false
                  show_label: true
                  label: '[[[ return entity.attributes.status ]]]'
                  tap_action:
                    action: none
                  styles:
                    card:
                      - box-shadow: none
                      - padding: 4px
              - type: section
              - type: custom:stack-in-card
                mode: horizontal
                keep:
                  margin: true
                card_mod:
                  style: |
                    ha-card { box-shadow: none }
                cards:
                  - type: custom:button-card
                    tap_action:
                      action: call-service
                      service: linksys_velop.check_updates
                    name: Check for Update
                    icon: hass:update
                    state:
                      - value: 'on'
                        color: darkcyan
                        icon: hass:refresh
                        spin: true
                      - value: 'off'
                        color: var(--primary-text-color)
                    styles:
                      card:
                        - margin-bottom: 3px
                      name:
                        - white-space: normal
                        - font-size: smaller
                  - type: custom:button-card
                    entity: switch.velop_mesh_guest_wi_fi
                    tap_action:
                      action: none
                    name: Guest<br />Wi-Fi
                    state:
                      - value: 'on'
                        color: darkcyan
                      - value: 'off'
                        color: var(--primary-text-color)
                    styles:
                      card:
                        - margin-bottom: 3px
                      name:
                        - font-size: smaller
                        - color: |
                            [[[
                              var ret = 'var(--primary-text-color)'
                              if (entity.state == 'on') {
                                ret = 'darkcyan'
                              }
                              return ret
                            ]]]
                  - type: custom:button-card
                    entity: switch.velop_mesh_parental_control
                    tap_action:
                      action: toggle
                    name: Parental<br />Control
                    state:
                      - value: 'on'
                        color: darkcyan
                      - value: 'off'
                        color: var(--primary-text-color)
                    styles:
                      card:
                        - margin-bottom: 3px
                      name:
                        - font-size: smaller
                        - color: |
                            [[[
                              var ret = 'var(--primary-text-color)'
                              if (entity.state == 'on') {
                                ret = 'darkcyan'
                              }
                              return ret
                            ]]]
                  - type: custom:button-card
                    entity: binary_sensor.velop_mesh_speedtest_status
                    tap_action:
                      action: call-service
                      service: linksys_velop.start_speedtest
                    name: Speedtest
                    icon: hass:refresh
                    state:
                      - value: 'on'
                        color: darkcyan
                        spin: true
                      - value: 'off'
                        color: var(--primary-text-color)
                    styles:
                      card:
                        - margin-bottom: 3px
                      name:
                        - font-size: smaller
                        - color: |
                            [[[
                              var ret = 'var(--primary-text-color)'
                              if (entity.state == 'on') {
                                ret = 'darkcyan'
                              }
                              return ret
                            ]]]
              - type: section
              - type: custom:fold-entity-row
                padding: 0
                head:
                  type: custom:template-entity-row
                  entity: sensor.velop_mesh_online_devices
                  tap_action:
                    action: fire-dom-event
                    fold_row: true
                  name: >-
                    {% set friendly_name = state_attr(config.entity,
                    'friendly_name') %} {% if friendly_name %}
                      {{ friendly_name.split(':')[1].strip() }}
                    {% endif %}
                  card_mod:
                    style: |
                      state-badge { display: none; }
                      state-badge + div { margin-left: 8px !important; }
                      .info.pointer { font-weight: 500; }
                      .state { margin-right: 10px; }
                entities:
                  - type: custom:hui-element
                    card_type: markdown
                    card_mod:
                      style:
                        .: |
                          ha-card { border-radius: 0px; box-shadow: none; }
                          ha-markdown { padding: 16px 0px 0px !important; }
                        ha-markdown$: >
                          table { width: 100%; border-collapse: separate;
                          border-spacing: 0px; }

                          tbody tr:nth-child(2n+1) { background-color:
                          var(--table-row-background-color); }

                          thead tr th, tbody tr td { padding: 4px 10px; }
                    content: >
                      {% set devices =
                      state_attr('sensor.velop_mesh_online_devices', 'devices')
                      %} | # | Name | IP | Type |

                      |:---:|:---|---:|:---:| {%- for device in devices -%}
                        {% set idx = loop.index %}
                        {%- for device_name, device_details in device.items() -%}
                          {%- set device_ip = device_details.keys() | list | first -%}
                          {%- set connection_type = device_details.values() | list | first | lower -%}
                          {%- if connection_type == "wired" -%}
                            {%- set connection_icon = "ethernet" -%}
                          {% elif connection_type == "wireless" -%}
                            {%- set connection_icon = "wifi" -%}
                          {% elif connection_type == "unknown" -%}
                            {%- set connection_icon = "help" -%}
                          {% else -%}
                            {%- set connection_icon = "" -%}
                          {%- endif %}
                      {{ "| {} | {} | {} | {} |".format(idx, device_name,
                      device_ip, '<ha-icon icon="hass:' ~ connection_icon ~
                      '"></ha-icon>') }}
                        {%- endfor %}
                      {%- endfor %}
              - type: custom:fold-entity-row
                padding: 0
                head:
                  type: custom:template-entity-row
                  entity: sensor.velop_mesh_offline_devices
                  tap_action:
                    action: fire-dom-event
                    fold_row: true
                  name: >-
                    {% set friendly_name = state_attr(config.entity,
                    'friendly_name') %} {% if friendly_name %}
                      {{ friendly_name.split(':')[1].strip() }}
                    {% endif %}
                  card_mod:
                    style: |
                      state-badge { display: none; }
                      state-badge + div { margin-left: 8px !important; }
                      .info.pointer { font-weight: 500; }
                      .state { margin-right: 10px; }
                entities:
                  - type: custom:hui-element
                    card_type: markdown
                    card_mod:
                      style:
                        .: |
                          ha-card { border-radius: 0px; box-shadow: none; }
                          ha-markdown { padding: 16px 0px 0px !important; }
                        ha-markdown$: >
                          table { width: 100%; border-collapse: separate;
                          border-spacing: 0px; }

                          tbody tr:nth-child(2n+1) { background-color:
                          var(--table-row-background-color); }

                          thead tr th, tbody tr td { padding: 4px 10px; }
                    content: >
                      {% set devices =
                      state_attr('sensor.velop_mesh_offline_devices', 'devices')
                      %}

                      | # | Name |

                      |:---:|:---|

                      {% for device in devices %} {{ "| {} | {}
                      |".format(loop.index, device) }}

                      {% endfor %}
              - type: conditional
                conditions:
                  - entity: sensor.velop_mesh_available_storage
                    state_not: '0'
                  - entity: sensor.velop_mesh_available_storage
                    state_not: unavailable
                row:
                  type: custom:fold-entity-row
                  padding: 0
                  head:
                    type: section
                    label: Storage
                  entities:
                    - type: custom:hui-element
                      card_type: markdown
                      card_mod:
                        style:
                          .: |
                            ha-card { border-radius: 0px; box-shadow: none; }
                            ha-markdown { padding: 16px 0px 0px !important; }
                          ha-markdown$: >
                            table { width: 100%; border-collapse: separate;
                            border-spacing: 0px; }

                            tbody tr:nth-child(2n+1) { background-color:
                            var(--table-row-background-color); }

                            thead tr th, tbody tr td { padding: 4px 10px; }
                      content: >
                        {% set partitions =
                        state_attr('sensor.velop_mesh_available_storage',
                        'partitions') %}

                        | Host | Label | %age used

                        |:---:|:---:|:---:|

                        {% for partition in partitions %} {{ "| {} | {} | {}
                        |".format(partition.ip, partition.label,
                        partition.used_percent) }}

                        {% endfor %}
      - type: custom:auto-entities
        card:
          type: vertical-stack
        card_param: cards
        sort:
          method: friendly_name
          reverse: false
        filter:
          include:
            - entity_id: /^binary_sensor\.velop_(?!(mesh)).*_status/
              options:
                type: custom:config-template-card
                variables:
                  BUTTONS: |
                    () => {
                      var ret = []
                      var entity_prefix = "button." + "this.entity_id".split(".")[1].split("_").slice(0, -1).join("_")
                      for (var entity_id in states) {
                        if (entity_id.startsWith(entity_prefix)) {
                          var entity_action = states[entity_id].attributes.friendly_name.split(':')[1].trim()
                          var entity_name = states[entity_id].attributes.friendly_name.split(':')[0].replace('Velop', '').trim()
                          ret.push({
                            'entity': entity_id,
                            'name': entity_action,
                            'tap_action': {
                                'action': 'call-service',
                                'service': 'linksys_velop.' + entity_action.toLowerCase() + '_node',
                                'service_data': {
                                  'node_name': entity_name,
                                },
                                'confirmation': {
                                  'text': 'Are you sure you want to reboot the ' + entity_name + ' node?'
                              }
                            }
                          })
                        }
                      }
                      return ret
                    }
                  ID_CONNECTED_DEVICES: >
                    "sensor." +
                    "this.entity_id".split(".")[1].split("_").slice(0,
                    -1).join("_") + "_connected_devices"
                  ID_LAST_UPDATE_CHECK: >
                    "sensor." +
                    "this.entity_id".split(".")[1].split("_").slice(0,
                    -1).join("_") + "_last_update_check"
                  ID_MODEL: >
                    "sensor." +
                    "this.entity_id".split(".")[1].split("_").slice(0,-1).join("_")
                    + "_model"
                  ID_PARENT: >
                    "sensor." +
                    "this.entity_id".split(".")[1].split("_").slice(0,-1).join("_")
                    + "_parent"
                  ID_SERIAL: >
                    "sensor." +
                    "this.entity_id".split(".")[1].split("_").slice(0,-1).join("_")
                    + "_serial"
                  ID_UPDATE_AVAILABLE: >
                    "binary_sensor." +
                    "this.entity_id".split(".")[1].split("_").slice(0,-1).join("_")
                    + "_update_available"
                  CONNECTED_DEVICES_TEXT: |
                    (entity_id) => {
                      var ret = `
                    | # | Name | IP | Type |
                    |:---:|:---|---:|:---:|
                    `
                      if (states[entity_id].attributes.devices) {
                        states[entity_id].attributes.devices.forEach((device, idx) => {
                          var connection_icon
                          switch (device.type.toLowerCase()) {
                            case "wireless":
                              connection_icon = "wifi"
                              break
                            case "wired":
                              connection_icon = "ethernet"
                              break
                            case "unknown":
                              connection_icon = "help"
                              break
                          }
                          ret += "| " + (idx + 1) + " | " + device.name + " | " + device.ip + " | <ha-icon icon='hass:" + connection_icon + "'></ha-icon> |\n"
                        })
                      }
                      return ret
                    }
                entities:
                  - this.entity_id
                  - ${ID_CONNECTED_DEVICES}
                  - ${ID_LAST_UPDATE_CHECK}
                  - ${ID_MODEL}
                  - ${ID_PARENT}
                  - ${ID_SERIAL}
                  - ${ID_UPDATE_AVAILABLE}
                card:
                  type: custom:stack-in-card
                  cards:
                    - type: custom:button-card
                      entity: this.entity_id
                      aspect_ratio: 3/1
                      size: 100%
                      show_entity_picture: true
                      show_last_changed: true
                      show_state: true
                      entity_picture: >-
                        ${'/local/velop_nodes/' + states[ID_MODEL].state +
                        '.png'}
                      name: |
                        [[[
                          var ret = entity.attributes.friendly_name
                          if (ret) {
                            ret = ret.replace("Velop", "").split(":")[0].trim()
                          }
                          return ret || "N/A"
                        ]]]
                      state_display: |
                        [[[
                          return `<ha-icon 
                            icon="hass:checkbox-blank-circle"
                            style="width: 24px; height: 24px;">
                            </ha-icon>`
                        ]]]
                      custom_fields:
                        attr_label_model: Model
                        attr_model: ${states[ID_MODEL].state}
                        attr_label_serial: Serial
                        attr_serial: ${states[ID_SERIAL].state}
                        attr_parent: >-
                          ${(states[ID_PARENT].state && states[ID_PARENT].state
                          != 'unknown') ? 'Connected to ' +
                          states[ID_PARENT].state : 'N/A'}
                        attr_label_ip: IP Address
                        attr_ip: '[[[ return entity.attributes.ip || ''N/A'' ]]]'
                        attr_update: |
                          [[[
                            var ret
                            var entity_update = 'binary_sensor.' + entity.entity_id.split('.')[1].split('_').slice(0, -1).join('_') + '_update_available'
                            var update_available = states[entity_update].state
                            if (update_available == 'on') {
                              ret = `<ha-icon
                                  icon="hass:package-up"
                                  style="width: 24px; height: 24px;"
                                >
                                </ha-icon>`
                            }
                            return ret
                          ]]]
                      extra_styles: >
                        div[id^="attr_"] { justify-self: end; }
                        div[id^="attr_label_"] { justify-self: start;
                        margin-left: 20px; } #label, #attr_parent { padding-top:
                        25px; font-size: smaller; }
                      styles:
                        card:
                          - padding: 16px
                        grid:
                          - grid-template-areas: >-
                              "n n attr_update s" "i attr_label_model
                              attr_label_model attr_model" "i attr_label_serial
                              attr_label_serial attr_serial" "i attr_label_ip
                              attr_label_ip attr_ip" "l l l attr_parent"
                          - grid-template-rows: 1fr 1fr 1fr 1fr 1fr
                          - grid-template-columns: 15% 1fr 30px 30px
                        name:
                          - font-size: larger
                          - justify-self: start
                          - padding-bottom: 20px
                        label:
                          - justify-self: start
                        custom_fields:
                          attr_label_last_update_check:
                            - margin-left: 0px
                          attr_last_update_check:
                            - justify-self: end
                          attr_parent:
                            - justify-self: end
                          attr_update:
                            - color: darkred
                            - justify-self: end
                            - padding-bottom: 20px
                        state:
                          - justify-self: end
                          - padding-bottom: 20px
                          - color: |-
                              [[[
                                return (entity.state == 'on' ? 'darkcyan' : 'darkred')
                              ]]]
                    - type: entities
                      card_mod:
                        style:
                          .: |
                            #states { padding-left: 8px; }
                      entities:
                        - type: custom:auto-entities
                          show_empty: false
                          card:
                            type: custom:fold-entity-row
                            group_config:
                              card_mod:
                                style:
                                  hui-generic-entity-row:
                                    $: >
                                      state-badge { display: none; }

                                      state-badge + div { margin-left: 8px
                                      !important; padding-top: 10px; }
                            head:
                              type: section
                              label: Additional Information
                            padding: 0
                          filter:
                            include:
                              - entity_id: ${ID_LAST_UPDATE_CHECK}
                                options:
                                  name: Last update check
                        - type: custom:auto-entities
                          show_empty: false
                          filter:
                            include:
                              - domain: button
                                entity_id: >-
                                  ${"/" +
                                  "this.entity_id".split(".")[1].split("_").slice(0,-1).join("_")
                                  + "/"}
                          card:
                            type: custom:fold-entity-row
                            padding: 0
                            head:
                              type: section
                              label: Actions
                            entities:
                              - type: buttons
                                entities: ${BUTTONS()}
                        - type: section
                        - type: custom:fold-entity-row
                          padding: 0
                          head:
                            type: custom:template-entity-row
                            tap_action:
                              action: fire-dom-event
                              fold_row: true
                            card_mod:
                              style: >
                                state-badge { display: none; }

                                state-badge + div { margin-left: 8px !important;
                                }

                                .info.pointer { font-weight: 500; }

                                .state { margin-right: 10px; }
                            entity: ${ID_CONNECTED_DEVICES}
                            name: >-
                              {% set name = state_attr(config.entity,
                              'friendly_name') %} {% if name %}
                                {{ name.split(':')[1].strip() }}
                              {% endif %}
                          entities:
                            - type: custom:hui-element
                              card_type: markdown
                              content: ${CONNECTED_DEVICES_TEXT(ID_CONNECTED_DEVICES)}
                              card_mod:
                                style:
                                  .: >
                                    ha-card { border-radius: 0px; box-shadow:
                                    none; }

                                    ha-markdown { padding: 16px 0px 0px
                                    !important; }
                                  ha-markdown$: >
                                    table { width: 100%; border-collapse:
                                    collapse; }

                                    tbody tr:nth-child(2n+1) { background-color:
                                    var(--table-row-background-color); }

                                    thead tr th, tbody tr td { padding: 4px
                                    10px; }
  ```
</details>

# Example Automations

Below are some example automations. I'm aware some of these could be more 
generic or even done in a better way but these are for example purposes only.

<details>
  <summary>Notify when a node goes offline or comes online</summary>

  ```yaml
  alias: 'Notify: Velop node online/offline'
  description: ''
  trigger:
    - platform: state
      entity_id: binary_sensor.velop_utility_status
      id: Node Online
      from: 'off'
      to: 'on'
    - platform: state
      entity_id: binary_sensor.velop_utility_status
      id: Node Offline
      from: 'on'
      to: 'off'
  condition: []
  action:
    - choose:
        - conditions:
            - condition: trigger
              id: Node Online
          sequence:
            - service: persistent_notification.create
              data:
                message: Node is online
        - conditions:
            - condition: trigger
              id: Node Offline
          sequence:
            - service: persistent_notification.create
              data:
                message: Node is offline
      default: []
  mode: single
  ```
</details>
