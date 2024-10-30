
# Linksys Velop

Home Assistant integration for the Linksys Velop Wi-Fi system.

## Table of Contents

* [Description](#description)
  * [Installation](#installation)
  * [Definitions](#definitions)
  * [Entities Provided](#entities-provided)
    * [Binary Sensors](#binary-sensors)
    * [Buttons](#buttons)
    * [Device Trackers](#device-trackers)
    * [Event](#event)
    * [Select](#select)
    * [Sensors](#sensors)
    * [Switches](#switches)
  * [Services](#services)
* [Setup](#setup)
* [Configurable Options](#configurable-options)
  * [Timers](#timers)
  * [Device Trackers](#device-trackers-1)
  * [UI Devices](#ui-devices)
  * [Events](#events)
  * [Advanced Options](#advanced-options)
* [Troubleshooting](#troubleshooting)
  * [Debug Logging](#debug-logging)
  * [Diagnostics Integration](#diagnostics-integration)

## Description

This custom component has been designed for Home Assistant and enables access
to the functions that would be useful (and probably some that aren't) in the
Home Assistant environment.

### Installation

The integration can be installed using [HACS](https://hacs.xyz/).  The
integrations is not available in the default repositories, so you will need to
add the URL of this repository as a custom repository to HACS (see
[here](https://hacs.xyz/docs/faq/custom_repositories)).

Alternatively you can use the button below.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=uvjim&repository=linksys_velop&category=Integration)

### Definitions

* _Mesh_: the mesh is the network itself and refers to anything that is not
  attributed to a single node or device in the network.
* _Node_: a node is a device that helps to form the mesh.
* _Device_: a device is an endpoint that connects to the mesh network. Think
  of these as the endpoint devices, such as a laptop, phone or tablet.

### Entities Provided

Where applicable the sub-items in the list detail the additional attributes
available.

All device entities are only available if the [UI Device](#ui-devices) is
enabled.

#### Binary Sensors

* Device: Blocked Times
  * Times of the week that are blocked
* Device: Guest Network
* Device: Reserved IP
* Device: Connected
* Mesh: Channel Scanning _(disabled by default)_
* Mesh: Client Steering _(disabled by default)_
* Mesh: DHCP Server _(disabled by default)_
* Mesh: Express Forwarding _(disabled by default)_
* Mesh: HomeKit Integration Paired _(disabled by default)_
* Mesh: MAC Filtering _(disabled by default)_
  * mode, address list
* Mesh: Node Steering _(disabled by default)_
* Mesh: SIP _(disabled by default)_
* Mesh: Speedtest state _(disabled by default)_
* Mesh: UPnP _(disabled by default)_
* Mesh: UPnP Allow Users to Configure _(disabled by default)_
* Mesh: UPnP Allow Users to Disable Internet _(disabled by default)_
* Mesh: WAN Status
  * IP, DNS, MAC
* Node: Status
  * Guest network, IP, IPv6, MAC, Reservation

#### Buttons

* Device: Delete
* Mesh: Check for Updates
* Mesh: Reboot the Whole Mesh (see [Configurable Options -> Advanced Options](#advanced-options))
* Mesh: Start Channel Scanning _(interval: 40s)_
* Mesh: Start Speedtest _(interval: 1s)_ _(disabled by default)_
* Node: Reboot

> **N.B.** Buttons with an interval in brackets start a long running task.
  When they are pressed or the corresponding `binary_sensor` realises that the
  task is running updates are switched to the specified interval.
>
> **N.B.** There is deliberately no button provided to restart the Primary node.
Restarting the Primary node will cause all nodes in the Mesh to reboot and
I consider this to be quite a destructive action. There is no confirmation in
the HASS UI when a button is pressed so there is no time to warn anyone. If
you'd like to reboot the Primary you node you must use the
[service](#services) with the `is_primary` flag provided, or the `Mesh: Reboot
the Whole Mesh` button.

#### Device Trackers

These are selectable and are presented as part of the configuration at both
install time and from reconfiguring the integration.

Device trackers should be enabled by default and will be seen as entities of the
mesh. This is achieved by adding the MAC address to the connections for the mesh
and you will see these allocated to the Mesh device in the HASS UI. When the
tracker is removed, the MAC is also removed from the Mesh device.

#### Event

This entity provides access to data for the events selected in the configuration.
Available events are: -

* Mesh rebooting
* New device found
* New node found

#### Select

* Device: Devices _(only available if [temporary device](#advanced-options) is enabled_

#### Sensors

* Device: Blocked Sites
  * list of sites blocked
* Device: Description
* Device: Friendly Signal Strength
* Device: ID
* Device: IP
* Device: IPv6
* Device: MAC
* Device: Manufacturer
* Device: Model
* Device: Name
* Device: Operating System
* Device: Parent
* Device: Serial
* Device: Signal Strength _(i.e., RSSI)_
* Device: UI Type _(the `entity_picture` attribute will be set if `node_images`
  are configured, see [here](#advanced-options))_
* Mesh: DHCP Reservations _(disabled by default)_
  * list of DHCP reservations on the mesh
* Mesh: Number of Offline Devices
  * list of device objects containing names and unique ID of devices that are
    offline
* Mesh: Number of Online Devices
  * list of device objects containing names, unique IDs, IP addresses, adapter
    types and guest network state for the online devices
* Mesh: Number of Guest Devices
  * list of device names, IP addresses, adapter types etc
* Mesh: Speedtest Download Bandwidth _(disabled by default)_
* Mesh: Speedtest Last Run _(disabled by default)_
* Mesh: Speedtest Latency _(disabled by default)_
* Mesh: Speedtest Progress  _(disabled by default)_, e.g. Detecting server,
  Checking latency
* Mesh: Speedtest Result _(disabled by default)_
* Mesh: Speedtest Upload Bandwidth _(disabled by default)_
* Mesh: Number of Available Storage Partitions _(disabled by default)_
  * list of the available partitions including the following information: IP,
    label, available Kb, used Kb, used %age and last checked time
* Mesh: WAN IP
* Node: Number of Connected Devices
  * list of names, IP addresses, type of connection and guest network state for
    the connected devices
* Node: Backhaul Friendly Signal Strength _(only if a wireless backhaul)_
* Node: Backhaul Last Checked _(only if not the primary node)_
  _(disabled by default)_
* Node: Backhaul Signal Strength _(only if a wireless backhaul)_
* Node: Backhaul Speed
* Node: Backhaul Type
* Node: Last Update Check _(disabled by default)_
* Node: Model _(The `entity_picture` attribute will be set if `node_images` are
  configured, see [here](#advanced-options))_
* Node: Parent Name _(only if the node is not the primary)_
  * IP address of the parent
* Node: Serial Number
* Node: Type, e.g. Primary Secondary

#### Switches

* Device: Internet Access
* Mesh: Guest Wi-Fi state
  * list of guest networks available
* Mesh: HomeKit Integration
* Mesh: Parental Control state
  * list of the rules being applied
* Mesh: WPS

#### Update

* Node: Firmware update available.
  * includes current and latest firmware versions

### Services

The following services are available. Each service is described in metadata
so paramters are described in the Home Assistant Services page.

* Control Internet Access for a Device - allow/block access to the Internet
  for a device.
* Delete Device - delete a device from the Mesh device list.
* Reboot Node - reboot the given node.
* Rename Device - rename the given device in the Mesh device list.
* Set Device Parental Controls - set the times a device is blocked from using
  the Internet.

All services require that you select the Mesh device that the request should be
directed to. Other requirements by the services should be self-explanatory.

> **&ast;** these are considered long-running tasks. When the binary sensors
  spot these tasks are running an additional timer is set up that polls at
  intervals to get updates and updates the relevant attributes for that
  sensor.
>
> **^** these are deprecated services. A warning will be displayed in the HASS
  log when they are used. They are subject to removal at any time.

## Setup

When setting up the integration you will be asked for the following information.

![Initial Setup Screen](images/setup_user.png)

* `Primary node address`: must be the node classed as the primary node
* `Password`: the password you would use to log in to the router. This may
  not be the same as the password for the application or web UI if you use
  the Linksys cloud service.

![Configure Timers](images/config_timers.png)

* `Scan Interval`: the frequency of updates for the sensors, default `60s`
* `Device Tracker Interval`: the frequency of updates for the device
  trackers, default `10s`
* `Consider Home Period`: the time to wait before considering a device away
  after it notifies of becoming disconnected, default `180s`
* `Response Timeout`: the number of seconds to wait for a response from
  an individual request to the API, default `10s`

![Configure Device Trackers](images/config_device_trackers.png)

* `Available devices`: a multi-select list of the devices found on the mesh.

On successful set up the following screen will be seen detailing the Mesh
device and the individual nodes found in the mesh.

![Final Setup Screen](images/setup_final.png)

## Configurable Options

It is possible to configure the following options for the integration.

### Timers

![Configure Timers](images/config_timers.png)

* `Scan Interval`: the frequency of updates for the sensors, default `60s`
* `Device Tracker Interval`: the frequency of updates for the device
  trackers, default `10s`
* `Consider Home Period`: the time to wait before considering a device away
  after it notifies of becoming disconnected, default `180s`
* `Response Timeout`: the number of seconds to wait for a response from
  an individual request to the API, default `10s`

### Device Trackers

![Configure Device Trackers](images/config_device_trackers.png)

* `Available devices`: a multi-select list of the devices found on the mesh.

### UI Devices

A UI device is one which is available on the mesh and you would like to have
further information available in Home Assistant. IT could be that you want to
create automations based on a device signal strength, parent node or state
(without using a `device tracker`).

![Configure UI Devices](images/config_ui_devices.png)

* `Available devices`: a multi-select list of the devices found on the mesh.
  This list excludes any device which doesn't have a name - typically
  displayed in the official interfaces as `Network Device`

### Events

The events selected here will be raised with the `event` entity.

![Configure Events](images/config_events.png)

### Advanced Options

**This section is only available if "Advanced Mode" is enabled for the current**
**user. See**
**[here](https://www.home-assistant.io/blog/2019/07/17/release-96/#advanced-mode).**

![Configure Advanced Options](images/config_advanced_options.png)

* `Velop image path`: the path to the folder location containing the images to
  use for integration purposes. This is currently used for to set the entity
  picture for various entities. It relies on the `http` integration from HASS,
  details of which can be found
  [here](https://www.home-assistant.io/integrations/http), and more specifically
  [here](https://www.home-assistant.io/integrations/http#hosting-files) for the
  path to place the files in.
* `Use a temporary device for select entity details`: creates a placeholder
  device that will be populated with the details of the device selected in
  the [select](#select) entity. The `select` entity will no longer have the
  details populated to its attributes.
* `Allow rebooting the Mesh`: creates a button on the Mesh entity that allows
  rebooting the whole mesh.

## Troubleshooting

### Debug Logging

> This way of logging is most useful if there is an intermitent problem as it
will continue logging until it is disabled again.

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

The highlighted area in the image below shows where the link for downloading
diagnostics can be found.

![Diagnostics link](images/diagnostics.png)

Example output: -

* [Device](examples/device_diagnostics.json)
* [Configuration Entry and Mesh](examples/config_entry_and_mesh_diagnostics.json)
