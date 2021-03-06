
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
  - IP, MAC, guest network
- Node: Update Available (only if HASS < 2022.4.0)

#### Buttons

- Mesh: Check for Updates
- Node: Reboot

#### Device Trackers

These are selectable and are presented as part of the configuration at both 
install time and from reconfiguring the integration.

#### Select

- Mesh: Devices *(disabled by default)*
  - Once a device is selected the attributes will be updated to reflect the 
    following: connected adapters, description, manufacturer, model, name, 
    operating_system, parent name, serial, status and unique_id

#### Sensors

- Mesh: Number of Offline Devices
  - list of device objects containing names and unique ID of devices that are 
    offline
- Mesh: Number of Online Devices
  - list of device objects containing names, unique IDs, IP addresses, adapter 
    types and guest network state for the online devices
- Mesh: Number of Guest Devices *(disabled by default)*
  - list of device names, IP addresses, adapter types etc
- Mesh: Date of Latest Speedtest
  - Exit code, Latency, Download/Upload bandwidth, Result ID
- Mesh: Number of Available Storage Partitions *(disabled by default)*
  - list of the available partitions including the following information: IP, 
    label, available Kb, used Kb, used %age and last checked time
- Node: Number of Connected Devices
  - list of names, IP addresses, type of connection and guest network state for 
    the connected devices
- Node: Current Firmware Version (only if HASS < 2022.4.0)
- Node: Last Update Check *(disabled by default)*
- Node: Model Number
- Node: Newest Firmware Version (only if HASS < 2022.4.0)
- Node: Parent Name
  - IP address of the parent, backhaul information (connection type, speed 
    in Mbps and last checked time)
- Node: Serial Number
- Node: Type of Node, e.g. Primary Secondary

#### Switches

- Mesh: Guest Wi-Fi state
  - list of guest networks available
- Mesh: Parental Control state
  - list of the rules being applied

#### Update (only if HASS > 2022.4.0)

- Node: Firmware update available.
  - includes current and latest firmware versions 

### Events Fired

#### `linksys_velop_new_device_on_mesh`

This event is fired when a brand-new device appears on the Mesh. A device is 
considered new if it presents a device ID (determined by the Velop) that was 
not seen at the last poll period. This means that it will not fire for 
devices that change from online to offline and vice-versa.

The event is fired for each new device that is discovered. The data is as 
the Velop mesh sees it, i.e. there is no magic by the integration to 
establish the manufacturer, model, operating system or serial.

> **N.B.** The name will default to `Network Device` if there is no name 
established by the Velop or assigned by the user.

The event looks as follows: -

```json
{
    "event_type": "linksys_velop_new_device_on_mesh",
    "data": {
        "connected_adapters": [
            {
                "mac": "11:22:33:44:55:66",
                "ip": "192.168.1.45",
                "guest_network": false
            }
        ],
        "description": null,
        "manufacturer": null,
        "model": null,
        "name": "Network Device",
        "operating_system": null,
        "parent_name": "Test Parent",
        "serial": null,
        "status": true,
        "mesh_device_id": "04e9bfe6c39d52f8272de96cbf85909c"
    },
    "origin": "LOCAL",
    "time_fired": "2022-03-27T13:43:48.335952+00:00",
    "context": {
        "id": "0bcafe321fc4919958c350da1aaef6de",
        "parent_id": null,
        "user_id": null
    }
}
```

#### `linksys_velop_new_node_on_mesh` 

This event is fired when a new node is found on the Mesh. A node is 
considered new if it is not currently configured in HASS. It may not be 
configured for a couple of reasons: the device was deleted from the UI, or 
you've added a new node to your Mesh.

The event is fired for each new node that is discovered.

The event looks as follows: -

```json
{
    "event_type": "linksys_velop_new_node_on_mesh",
    "data": {
        "backhaul": {
            "connection": "Wireless",
            "last_checked": "2022-04-14T12:11:23Z",
            "speed_mbps": 115.037
        },
        "connected_adapters": [
            {
                "mac": "11:22:33:44:55:66",
                "ip": "192.168.123.31",
                "guest_network": false
            }
        ],
        "model": "WHW01",
        "name": "Utility",
        "parent_name": "Front Bedroom",
        "serial": "1234567890",
        "status": true,
        "mesh_device_id": "1ca89cc86d79dff3f3bf91cfc5f6973f"
    },
    "origin": "LOCAL",
    "time_fired": "2022-04-14T12:15:10.150604+00:00",
    "context": {
        "id": "7510f408cfc36511b0c6372542fbfdc0",
        "parent_id": null,
        "user_id": null
    }
}
```

#### `linksys_velop_new_primary_node`

This event is fired when a new primary node is detected. The check for this 
is based on the serial number and is currently only found as part of SSDP 
discovery. If the serial numbers do not match, this event is fired and the 
unique_id of the integration instance is update.

This should stop the mesh being discovered again by SSDP when the primary 
node is changed. 

```json
{
    "event_type": "linksys_velop_new_primary_node",
    "data": {
        "host": "192.168.123.254",
        "model": "velop ax4200 wifi 6 system",
        "serial": "1234567890"
    },
    "origin": "LOCAL",
    "time_fired": "2022-04-13T12:29:28.749528+00:00",
    "context": {
        "id": "d0cb4b018867b3311f2edb24e156d541",
        "parent_id": null,
        "user_id": null
    }
}
```

### Services

The following services are available.  Each service is described in metadata 
so paramters are described in the Home Assistant Services page. 

- Check for Updates
- Delete Device
- Execute Speedtest &ast;
- Reboot Node

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

### Timers

![Configure Timers](images/config_timers.png)

- `Scan Interval`: the frequency of updates for the sensors, default `30s`
- `Device Tracker Interval`: the frequency of updates for the device 
  trackers, default `10s`
- `Consider Home Period`: the time to wait before considering a device away 
  after it notifies of becoming disconnected, default `180s`
- `Response Timeout`: the number of seconds to wait for a response from 
  an individual request to the API

### Device Trackers

![Configure Device Trackers](images/config_device_trackers.png)

- `Available devices`: a multi-select list of the devices found on the mesh. 
  This list excludes any device which doesn't have a name - typically 
  displayed in the official interfaces as `Network Device`

## Advanced Options

This section details the options that cannot be configured in the UI but are 
still available of you configure them in the underlying HASS config files.

* `node_images`: the path to the folder location containing the images to 
  use for nodes. This is currently used in the card and also for the 
  `update` entity. e.g. `/local/velop_nodes`

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

Example output can be found [here](examples/diagnostics_ouput.json)

# Example Lovelace UI

## Main UI

| Dark Mode | Light Mode |
|:---:|:---:|
| ![Lovelace Dark UI](images/lovelace_dark.png) | ![Lovelace Light UI](images/lovelace_light.png) |

*Some items of detail have been pixelated for privacy purposes.*

The view consists of 3 main cards.  These are detailed below.

### Card 1

This card is used mainly to work around a limitation in Button Card documented
[here](https://github.com/custom-cards/button-card#injecting-css-with-extra_styles).

#### Pre-requisites

The following custom cards are required for this part of the view.

- [Button Card](https://github.com/custom-cards/button-card)
- [card-mod](https://github.com/thomasloven/lovelace-card-mod)

<details>
  <summary>YAML for the card</summary>

```yaml
type: custom:button-card
color_type: blank-card
card_mod:
  style: |
    :host { display: none !important; }
```
</details>

### Card 2

This card creates the Mesh part of the view.

#### Pre-requisites

- [Button Card](https://github.com/custom-cards/button-card)
- [card-mod](https://github.com/thomasloven/lovelace-card-mod)
- [fold-entity-row](https://github.com/thomasloven/lovelace-fold-entity-row)
- [hui-element](https://github.com/thomasloven/lovelace-hui-element)
- [template-entity-row](https://github.com/thomasloven/lovelace-template-entity-row)

<details>
  <summary>YAML for the card</summary>

```yaml
type: entities
card_mod:
  style:
    .: |
      #states { padding-top: 0px; }
    fold-entity-row:
      $:
        template-entity-row:
          $: |
            state-badge { display: none; }
            state-badge + div { margin-left: 8px !important; }
            .info.pointer { font-weight: 500; }
            .state { margin-right: 10px; }
entities:
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
          if (entity_speedtest.state != 'unknown') {
            var d = new Date(entity_speedtest.state)
            return "As at: " + d.toLocaleString()
          } else {
            return "No Speedtest results"
          }
        ]]]
      attr_speedtest_details: |
        [[[
          var round2 = (num) => Math.round(num * 100) / 100
          var spacing_internal = 5
          var spacing_external = 30
          var icon_size = 22
          var entity_speedtest = states['sensor.velop_mesh_speedtest_latest']
          if (entity_speedtest.state != 'unknown') {
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
          }
        ]]]
    state:
      - value: 'on'
        color: darkcyan
      - value: 'off'
        color: darkred
    styles:
      card:
        - box-shadow: none
        - padding: 16px 8px
      grid:
        - grid-template-areas: >-
            "attr_dns_servers . attr_public_ip" "i i i" "attr_speedtest_details
            attr_speedtest_details attr_speedtest_details"
            "attr_speedtest_latest attr_speedtest_latest attr_speedtest_latest"
        - grid-template-rows: 5% 1fr 15% 5%
        - grid-template-columns: 1fr min-content 1fr
      custom_fields:
        attr_dns_servers:
          - justify-self: self-start
        attr_public_ip:
          - justify-self: self-end
    extra_styles: |
      div[id^="attr_"] { font-size: smaller; color: var(--disabled-text-color);
      }
      div[id^="attr_speedtest_"] { margin-top: 10px; }
      #attr_public_ip::before { content: 'Public IP: ' }
      #attr_dns_servers::before { content: 'DNS: ' }
  - type: conditional
    conditions:
      - entity: binary_sensor.velop_mesh_speedtest_status
        state: 'on'
    row:
      type: section
  - type: custom:template-entity-row
    card_mod:
      style: >
        state-badge { display: none; } state-badge + div.info { margin-left: 8px
        !important; margin-right: 8px; text-align: center; }
    condition: '{{ is_state(''binary_sensor.velop_mesh_speedtest_status'', ''on'') }}'
    name: '{{ state_attr(''binary_sensor.velop_mesh_speedtest_status'', ''status'') }}'
    tap_action:
      action: none
  - type: section
  - type: custom:auto-entities
    card:
      type: horizontal-stack
    card_param: cards
    sort:
      method: friendly_name
    filter:
      include:
        - entity_id: /^(button|switch)\.velop_mesh_/
          options:
            type: custom:button-card
            hold_action:
              action: more-info
            tap_action:
              action: >-
                [[[ return (entity.entity_id.startsWith("button")) ?
                "call-service" : "toggle" ]]]
              service: >-
                [[[ return (entity.entity_id.startsWith("button")) ?
                "button.press" : undefined ]]]
              service_data:
                entity_id: entity
            name: |-
              [[[
                var friendly_name = entity.attributes.friendly_name.replace("Velop Mesh:", "").trim()
                var idx = friendly_name.lastIndexOf(" ");
                var ret = friendly_name.substring(0, idx) + "<br />" + friendly_name.substring(idx + 1)
                return ret
              ]]]
            styles:
              card:
                - box-shadow: none
                - margin-bottom: 3px
              icon:
                - animation: |-
                    [[[
                      var ret
                      if (entity.entity_id == "button.velop_mesh_start_speedtest" && states["binary_sensor.velop_mesh_speedtest_status"].state == "on") {
                        ret = "rotating 2s linear infinite"
                      }
                      return ret
                    ]]]
                - color: |-
                    [[[ 
                      var ret
                      var col_on = "darkcyan"
                      var col_off = "var(--primary-text-color)"
                      ret = (entity.state == "on") ? col_on : col_off
                      if (entity.entity_id == "button.velop_mesh_start_speedtest") {
                        ret = (states["binary_sensor.velop_mesh_speedtest_status"].state == "on") ? col_on : col_off
                      }
                      return ret
                    ]]]
              name:
                - font-size: smaller
                - color: |-
                    [[[
                      var ret
                      var col_on = "darkcyan"
                      var col_off = "var(--primary-text-color)"
                      ret = (entity.state == "on") ? col_on : col_off
                      if (entity.entity_id == "button.velop_mesh_start_speedtest") {
                        ret = (states["binary_sensor.velop_mesh_speedtest_status"].state == "on") ? col_on : col_off
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
        {% set friendly_name = state_attr(config.entity, 'friendly_name') %} {%
        if friendly_name %}
          {{ friendly_name.split(':')[1].strip() }}
        {% endif %}
      card_mod:
        style: |
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
              table { width: 100%; border-collapse: separate; border-spacing:
              0px; }

              tbody tr:nth-child(2n+1) { background-color:
              var(--table-row-background-color); }

              thead tr th, tbody tr td { padding: 4px 10px; }
        content: >
          {% set devices = state_attr('sensor.velop_mesh_online_devices',
          'devices') %} | # | Name | IP | Type |

          |:---:|:---|---:|:---:| {%- for device in devices -%}
            {%- set device_ip = device.ip -%}
            {%- set connection_type = device.connection | lower -%}
            {%- set guest_network = device.guest_network -%}
            {%- if connection_type == "wired" -%}
              {%- set connection_icon = "ethernet" -%}
            {% elif connection_type == "wireless" -%}
              {%- set connection_icon = "wifi" -%}
            {% elif connection_type == "unknown" -%}
              {%- set connection_icon = "help" -%}
            {% else -%}
              {%- set connection_icon = "" -%}
            {%- endif %}
          {{ "| {} | {}{} | {} | {} |".format(loop.index, device.name,
          '&nbsp;<ha-icon icon="hass:account-multiple"></ha-icon>' if
          guest_network else '', device_ip, '<ha-icon icon="hass:' ~
          connection_icon ~ '"></ha-icon>') }}
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
        {% set friendly_name = state_attr(config.entity, 'friendly_name') %} {%
        if friendly_name %}
          {{ friendly_name.split(':')[1].strip() }}
        {% endif %}
      card_mod:
        style: |
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
              table { width: 100%; border-collapse: separate; border-spacing:
              0px; }

              tbody tr:nth-child(2n+1) { background-color:
              var(--table-row-background-color); }

              thead tr th, tbody tr td { padding: 4px 10px; }
        content: >
          {% set devices = state_attr('sensor.velop_mesh_offline_devices',
          'devices') %}

          | # | Name |

          |:---:|:---|

          {% for device in devices %} {{ "| {} | {} |".format(loop.index,
          device.name) }}

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
                table { width: 100%; border-collapse: separate; border-spacing:
                0px; }        

                tbody tr:nth-child(2n+1) { background-color:
                var(--table-row-background-color); }

                thead tr th, tbody tr td { padding: 4px 10px; }
          content: >
            {% set partitions =
            state_attr('sensor.velop_mesh_available_storage', 'partitions') %}

            | Host | Label | %age used

            |:---:|:---:|:---:|

            {% for partition in partitions %} {{ "| {} | {} | {}
            |".format(partition.ip, partition.label, partition.used_percent) }}

            {% endfor %}
```
</details>

### Card 3

This card creates the Node part of the view.

#### Pre-requisites

- [auto-entities](https://github.com/thomasloven/lovelace-auto-entities)
- [Button Card](https://github.com/custom-cards/button-card)
- [card-mod](https://github.com/thomasloven/lovelace-card-mod)
- [Config Template Card](https://github.com/thomasloven/lovelace-hui-element)
- [fold-entity-row](https://github.com/thomasloven/lovelace-fold-entity-row)
- [hui-element](https://github.com/thomasloven/lovelace-hui-element)
- [template-entity-row](https://github.com/thomasloven/lovelace-template-entity-row)

<details>
  <summary>YAML for the card</summary>

```yaml
type: custom:auto-entities
card:
  type: vertical-stack
card_param: cards
filter:
  include:
    - integration: linksys_velop
      device_manufacturer: Linksys
      attributes:
        device_class: connectivity
      options:
        type: entities
        entities:
          - type: custom:config-template-card
            variables:
              ID_ENTITY_PART: |
                "this.entity_id".split(".")[1].split("_").slice(0,-1).join("_")
              ID_MODEL: |
                "sensor." + vars["ID_ENTITY_PART"] + "_model"
              ID_PARENT: |
                "sensor." + vars["ID_ENTITY_PART"] + "_parent"
              ID_SERIAL: |
                "sensor." + vars["ID_ENTITY_PART"] + "_serial"
              ID_UPDATE: |
                "update." + vars["ID_ENTITY_PART"] + "_update"
            entities:
              - this.entity_id
              - ${ID_MODEL}
              - ${ID_PARENT}
              - ${ID_SERIAL}
              - ${ID_UPDATE}
            card:
              type: custom:button-card
              entity: this.entity_id
              entity_picture: >-
                ${'/local/velop_nodes/' + states[vars['ID_MODEL']].state +
                '.png'}
              name: >-
                [[[ return
                entity.attributes.friendly_name.split(":")[0].replace(/velop/i,
                "").trim() ]]]
              show_entity_picture: true
              show_last_changed: true
              show_state: true
              size: 100%
              state_display: |
                [[[
                  return `<ha-icon 
                    icon="hass:checkbox-blank-circle"
                    style="width: 24px; height: 24px;">
                    </ha-icon>`
                ]]]
              tap_action:
                action: none
              custom_fields:
                attr_label_model: Model
                attr_model: ${states[vars["ID_MODEL"]].state}
                attr_label_serial: Serial
                attr_serial: ${states[vars["ID_SERIAL"]].state}
                attr_label_ip: IP
                attr_ip: '[[[ return entity.attributes.ip || ''N/A'' ]]]'
                attr_parent: >-
                  ${(states[vars["ID_PARENT"]].state != 'unknown') ?
                  states[vars["ID_PARENT"]].state : 'N/A'}
                attr_update: |-
                  ${(states[vars["ID_UPDATE"]].state == 'on')
                    ? `<ha-icon icon="hass:package-up" style="width: 24px; height: 24px;"></ha-icon>`
                    : ''
                  }
              extra_styles: >
                div[id^="attr_"] { justify-self: end; } div[id^="attr_label_"] {
                justify-self: start; margin-left: 20px; } #label, #attr_parent {
                padding-top: 25px; font-size: smaller; }
              styles:
                card:
                  - box-shadow: none
                  - padding: 0px 8px 8px
                custom_fields:
                  attr_update:
                    - color: darkred
                    - justify-self: end
                    - padding-bottom: 25px
                grid:
                  - grid-template-areas: |
                      "n n attr_update s"
                      "i attr_label_model attr_label_model attr_model"
                      "i attr_label_serial attr_label_serial attr_serial"
                      "i attr_label_ip attr_label_ip attr_ip"
                      "l l l attr_parent"
                  - grid-template-columns: 15% 1fr 30px 30px
                label:
                  - justify-self: start
                name:
                  - font-size: larger
                  - justify-self: start
                  - padding-bottom: 25px
                state:
                  - justify-self: end
                  - padding-bottom: 25px
                  - color: |-
                      [[[
                        return (entity.state == 'on' ? 'darkcyan' : 'darkred')
                      ]]]
          - type: custom:config-template-card
            entities:
              - this.entity_id
              - ${ID_LAST_UPDATE_CHECK}
              - ${ID_PARENT}
            variables:
              ID_ENTITY_PART: >
                "this.entity_id".split(".")[1].split("_").slice(0, -1).join("_")
              ID_LAST_UPDATE_CHECK: >
                "sensor." + vars["ID_ENTITY_PART"] + "_last_update_check"
              ID_PARENT: >
                "sensor." + vars["ID_ENTITY_PART"] + "_parent"
            card:
              type: entity-filter
              show_empty: false
              entities:
                - entity: ${ID_LAST_UPDATE_CHECK}
                  name: Last update check
                  state_filter:
                    - operator: '!='
                      value: unavailable
                  card_mod:
                    style:
                      hui-generic-entity-row$: |
                        state-badge { display: none; }
                        state-badge + div.info.pointer { margin-left: 8px; }
                - entity: ${ID_PARENT}
                  type: custom:template-entity-row
                  name: Backhaul
                  state: >
                    {% set backhaul_info = state_attr(config.entity, 'backhaul')
                    %} {% set backhaul_speed = backhaul_info.speed_mbps |
                    round(2) %} {% if (backhaul_speed | string).split('.')[1] ==
                    '0' %}
                      {% set backhaul_speed = backhaul_speed | int %}
                    {% endif %} {{ backhaul_info.connection }} ({{
                    backhaul_speed }} Mbps)
                  state_filter:
                    - operator: '!='
                      value: unknown
                  card_mod:
                    style: >
                      #wrapper { min-height: unset !important; } #wrapper
                      state-badge { display: none; }

                      #wrapper state-badge + div.info.pointer { margin-left:
                      8px; }
              card:
                type: custom:fold-entity-row
                head:
                  type: section
                  label: Additional Information
                padding: 0
          - type: custom:config-template-card
            entities:
              - this.entity_id
            variables:
              ID_ENTITY_PART: |
                "this.entity_id".split(".")[1].split("_").slice(0,-1).join("_")
              BUTTONS: |
                () => {
                  var ret = []
                  var entity_prefix = "button." + vars['ID_ENTITY_PART']
                  for (var entity_id in states) {
                    if (entity_id.startsWith(entity_prefix)) {
                      var entity_action = states[entity_id].attributes.friendly_name.split(':')[1].trim()
                      var entity_name = states[entity_id].attributes.friendly_name.split(':')[0].replace('Velop', '').trim()
                      ret.push({
                        'entity': entity_id,
                        'name': entity_action,
                        'tap_action': {
                            'action': 'call-service',
                            'service': 'button.press',
                            'service_data': {
                              'entity_id': entity_id,
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
            card:
              type: custom:auto-entities
              show_empty: false
              filter:
                include:
                  - domain: button
                    entity_id: ${"/" + vars['ID_ENTITY_PART'] + "/"}
              card:
                type: custom:fold-entity-row
                head:
                  type: section
                  label: Actions
                padding: 0
                entities:
                  - type: buttons
                    entities: ${BUTTONS()}
          - type: section
          - type: custom:config-template-card
            entities:
              - this.entity_id
              - ${ID_CONNECTED_DEVICES}
            variables:
              ID_CONNECTED_DEVICES: >
                "sensor." + "this.entity_id".split(".")[1].split("_").slice(0,
                -1).join("_") + "_connected_devices"
              CONNECTED_DEVICES_CONTENT: |
                () => {
                  var ret = `
                | # | Name | IP | Type |
                |:---:|:---|---:|:---:|
                `
                  if (states[vars['ID_CONNECTED_DEVICES']].attributes.devices) {
                    states[vars['ID_CONNECTED_DEVICES']].attributes.devices.forEach((device, idx) => {
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
                      ret += "| " + (idx + 1) + " | " + device.name + ((device.guest_network) ? "&nbsp;<ha-icon icon='hass:account-multiple'></ha-icon>" : "") + " | " + device.ip + " | <ha-icon icon='hass:" + connection_icon + "'></ha-icon> |\n"
                    })
                  }
                  return ret
                }
            card:
              type: custom:fold-entity-row
              head:
                type: custom:template-entity-row
                entity: ${ID_CONNECTED_DEVICES}
                name: Connected Devices
                tap_action:
                  action: fire-dom-event
                  fold_row: true
                card_mod:
                  style: |
                    state-badge { display: none; }
                    state-badge + div { margin-left: 8px !important; }
                    .info.pointer { font-weight: 500; }
                    .state { margin-right: 10px; }
              padding: 0
              entities:
                - type: custom:hui-element
                  card_type: markdown
                  content: ${ CONNECTED_DEVICES_CONTENT() }
                  card_mod:
                    style:
                      .: |
                        ha-card { border-radius: 0px; box-shadow: none; }
                        ha-markdown { padding: 16px 0px 0px !important; }
                      ha-markdown$: >
                        table { width: 100%; border-collapse: collapse; }

                        tbody tr:nth-child(2n+1) { background-color:
                        var(--table-row-background-color); }

                        thead tr th, tbody tr td { padding: 4px 10px; }
sort:
  method: friendly_name
```
</details>

## Using the Select Entity

This card allows you to select a device and see details about it.

![Lovelace Device Details](images/lovelace_device_details.png)

### Pre-requisites

- [card-mod](https://github.com/thomasloven/lovelace-card-mod)
- [template-entity-row](https://github.com/thomasloven/lovelace-template-entity-row)
- [state-switch](https://github.com/thomasloven/lovelace-state-switch)

<details>
  <summary>YAML for the card</summary>

```yaml
type: entities
title: Device Details
entities:
  - entity: select.velop_mesh_devices
  - type: attribute
    entity: select.velop_mesh_devices
    attribute: unique_id
    name: ID
    tap_action:
      action: none
  - type: attribute
    entity: select.velop_mesh_devices
    attribute: manufacturer
    name: Manufacturer
    tap_action:
      action: none
  - type: attribute
    entity: select.velop_mesh_devices
    attribute: model
    name: Model
    tap_action:
      action: none
  - type: attribute
    entity: select.velop_mesh_devices
    attribute: description
    name: Description
    tap_action:
      action: none
  - type: attribute
    entity: select.velop_mesh_devices
    attribute: parent_name
    name: Parent Node
    tap_action:
      action: none
  - type: attribute
    entity: select.velop_mesh_devices
    attribute: serial
    name: Serial
    tap_action:
      action: none
  - type: attribute
    entity: select.velop_mesh_devices
    attribute: operating_system
    name: Operating System
    tap_action:
      action: none
  - type: custom:template-entity-row
    entity: select.velop_mesh_devices
    name: Connected
    state: |-
      {% if states('select.velop_mesh_devices') == 'unknown' %}
        ???
      {% else %}
        {{ "Yes" if state_attr(config.entity, "status") is eq true else "No" }}
      {% endif %}
    tap_action:
      action: none
  - type: custom:template-entity-row
    entity: select.velop_mesh_devices
    name: IP
    state: |-
      {% if states('select.velop_mesh_devices') == 'unknown' %}
        ???
      {% else %}
        {{ (state_attr('select.velop_mesh_devices', 'connected_adapters') | first).ip }}
      {% endif %}
    tap_action:
      action: none
  - type: custom:template-entity-row
    entity: select.velop_mesh_devices
    name: MAC
    state: |-
      {% if states('select.velop_mesh_devices') == 'unknown' %}
        ???
      {% else %}
        {{ (state_attr(config.entity, 'connected_adapters') | first).mac }}
      {% endif %}
    tap_action:
      action: none
  - type: custom:template-entity-row
    entity: select.velop_mesh_devices
    name: Guest Network
    state: |-
      {% if states("select.velop_mesh_devices") == "unknown" %}
        ???
      {% else %}
        {{ "Yes" if (state_attr(config.entity, "connected_adapters") | first).guest_network else "No" }}
      {% endif %}
    tap_action:
      action: none
  - type: custom:state-switch
    entity: >-
      {% set schedules = state_attr("select.velop_mesh_devices",
      "parental_control_schedule") %} {% if schedules is not none and (schedules
      | map(attribute="blocked_internet_access") | list | length) %}
        display
      {% endif %}
    default: default
    states:
      default:
        type: custom:template-entity-row
        name: Blocked Internet Access
        state: ???
        tap_action:
          action: none
      display:
        type: markdown
        card_mod:
          style:
            ha-markdown$: >
              table { width: 100%; border-collapse: collapse; }

              p { margin-bottom: 0px; }

              tbody tr:nth-child(2n+1) { background-color:
              var(--table-row-background-color); }

              tbody tr td { padding: 4px 0px; }

              tbody tr td:first-of-type { padding-left: 20px; }
        content: >-
          Blocked Internet Access

          |  |  |

          |---|---:| {% set schedules = state_attr("select.velop_mesh_devices",
          "parental_control_schedule") %} {% if schedules is not none and
          (schedules | map(attribute="blocked_internet_access") | list | length)
          %}
            {% for day in schedules.blocked_internet_access -%}
              |{{ day | title }}|{{ schedules.blocked_internet_access[day] | join(", ") }}|
            {% endfor -%}
          {% endif %}
  - type: custom:state-switch
    entity: >-
      {% set sites = state_attr("select.velop_mesh_devices",
      "parental_control_schedule") %} {% if sites is not none and (sites |
      map(attribute="blocked_sites") | list | length) %}
        display
      {% endif %}
    default: default
    states:
      default:
        type: custom:template-entity-row
        name: Blocked Sites
        state: ???
        tap_action:
          action: none
      display:
        type: markdown
        card_mod:
          style:
            ha-markdown$: >
              table { width: 100%; border-collapse: collapse; }

              p { margin-bottom: 0px; }

              tbody tr:nth-child(2n+1) { background-color:
              var(--table-row-background-color); }

              tbody tr td { padding: 4px 0px; }

              tbody tr td:first-of-type { padding-left: 20px; }
        content: >-
          Blocked Sites

          |  |

          |:---|

          {% set sites = state_attr("select.velop_mesh_devices",
          "parental_control_schedule") %} {% if sites is not none and (sites |
          map(attribute="blocked_sites") | list | length) %}
            {%- for site in sites.blocked_sites -%}
              |{{ site }}|
            {% endfor -%}
          {% endif %}
show_header_toggle: false
card_mod:
  style:
    .: |
      #states > div:first-of-type { margin-bottom: 20px; }
    hui-select-entity-row:
      $:
        hui-generic-entity-row:
          $: |
            state-badge { display: none; }
            state-badge + div.info { margin-left: 0px; }
    hui-attribute-row:
      $:
        hui-generic-entity-row:
          $: |
            state-badge { display: none; }
            state-badge + div.info { margin-left: 0px; }
    template-entity-row:
      $: |
        #wrapper { min-height: auto !important; }
        state-badge { display: none; }
        state-badge + div.info { margin-left: 0px; }
    state-switch:
      $:
        template-entity-row:
          $: |
            #wrapper { min-height: auto !important; }
            state-badge { display: none; }
            state-badge + div.info { margin-left: 0px; }
        hui-markdown-card:
          $:
            .: |
              ha-card { border-radius: 0px; box-shadow: none; }
              ha-markdown { padding: 0px !important; }
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

<details>
  <summary>Notify when a brand-new device comes onto the Mesh</summary>

```yaml
alias: 'Notify: New Device on Mesh'
description: ''
trigger:
  - platform: event
    event_type: linksys_velop_new_device_on_mesh
condition: []
action:
  - service: persistent_notification.create
    data:
      notification_id: >-
        linksys_velop_new_device_{{
        trigger.event.data.connected_adapters[0].get('mac', 'N/A') }}
      title: ???? Device Found
      message: >-
        <b>{{ trigger.event.data.name }}</b>

        |   |   |   |

        |---|---|---| {% if trigger.event.data.mesh_device_id is not none %}

        |Mesh:|&emsp;|{{ device_attr(trigger.event.data.mesh_device_id,
        'name_by_user') or device_attr(trigger.event.data.mesh_device_id,
        'name') }}| {% endif %} {% if trigger.event.data.parent_name is not none
        %}

        |Parent:|&emsp;|{{ trigger.event.data.parent_name }}| {% endif %} {% if
        trigger.event.data.connected_adapters is not none %}

        |Guest:|&emsp;|{{ 'Yes' if
        trigger.event.data.connected_adapters[0].get('guest_network', False) is
        eq true else 'No' }}|

        |IP:|&emsp;|{{ trigger.event.data.connected_adapters[0].get('ip', 'N/A')
        }}|

        |MAC:|&emsp;|{{ trigger.event.data.connected_adapters[0].get('mac',
        'N/A') }}| {% endif %} {% if trigger.event.data.description is not none
        %}

        |Description:|&emsp;|{{ trigger.event.data.description }}| {% endif %}
        {% if trigger.event.data.manufacturer is not none %}

        |Manufacturer:|&emsp;|{{ trigger.event.data.manufacturer }}| {% endif %}
        {% if trigger.event.data.model is not none %}

        |Model:|&emsp;|{{ trigger.event.data.model }}| {% endif %} {% if
        trigger.event.data.serial is not none %}

        |Serial:|&emsp;|{{ trigger.event.data.serial }}| {% endif %} {% if
        trigger.event.data.operating_system is not none %}

        |Operating System:|&emsp;|{{ trigger.event.data.operating_system }}| {%
        endif %}
mode: parallel
````

This will create a notification that looks like the following screenshot.

![new device on mesh](images/linksys_velop_new_device_on_mesh.png)
</details>

<details>
  <summary>Notify when a new node comes onto the Mesh</summary>

```yaml
alias: New Automation
description: ''
trigger:
  - platform: event
    event_type: linksys_velop_new_node_on_mesh
condition: []
action:
  - service: persistent_notification.create
    data:
      notification_id: linksys_velop_new_node_{{ trigger.event.data.serial }}
      title: ???? Node Found
      message: >-
        |   |   |   |

        |---|---|---|

        |Name:|&emsp;|{{ trigger.event.data.name }}|

        |Model:|&emsp;|{{ trigger.event.data.model }}|

        |Parent:|&emsp;|{{ trigger.event.data.parent_name }}|

        |IP:|&emsp;|{{ trigger.event.data.connected_adapters[0].get('ip', 'N/A')
        }}|

        |Mesh:|&emsp;|{{ device_attr(trigger.event.data.mesh_device_id, 
        'name_by_user')
        or device_attr(trigger.event.data.mesh_device_id, 'name') }}|
mode: single
```

This will create a notification that looks like this: -

![new node on mesh](images/linksys_velop_new_node_on_mesh.png)
</details>

<details>
  <summary>Notify on events</summary>

```yaml
alias: 'Notify: Velop Information'
description: ''
trigger:
  - platform: event
    event_type: linksys_velop_new_device_on_mesh
    id: Device Found
  - platform: event
    event_type: linksys_velop_new_node_on_mesh
    id: Node Found
  - platform: event
    event_type: linksys_velop_new_primary_node
    event_data: {}
    id: Primary Node Changed
condition: []
action:
  - service: persistent_notification.create
    data:
      notification_id: >-
        {{ trigger.event.event_type }}_{{ trigger.event.data.get('unique_id') or
        trigger.event.data.get('serial') }}
      title: Linksys Velop - {{ trigger.id }}
      message: >-
        {% if trigger.event.data.get('name') is not none %}
          ## {{ trigger.event.data.name }}
        {% endif %}

        |   |   |   |

        |---|---|---| {% if trigger.event.data.get('mesh_device_id') is not none
        %}

        |Mesh:|&emsp;|{{ device_attr(trigger.event.data.mesh_device_id,
        'name_by_user') or device_attr(trigger.event.data.mesh_device_id,
        'name') }}| {% endif %} {% if trigger.event.data.get('parent_name') is
        not none %}

        |Parent:|&emsp;|{{ trigger.event.data.parent_name }}| {% endif %} {% if
        trigger.event.data.get('host') is not none %}

        |Host:|&emsp;|{{ trigger.event.data.host }}| {% endif %} {% if
        trigger.event.data.get('connected_adapters') is not none and
        trigger.event.data.get('connected_adapters') | count > 0 %}

        |Guest:|&emsp;|{{ 'Yes' if
        trigger.event.data.connected_adapters[0].get('guest_network', False) is
        eq true else 'No' }}|

        |IP:|&emsp;|{{ trigger.event.data.connected_adapters[0].get('ip', 'N/A')
        }}|

        |MAC:|&emsp;|{{ trigger.event.data.connected_adapters[0].get('mac',
        'N/A') }}| {% endif %} {% if trigger.event.data.get('description') is
        not none %}

        |Description:|&emsp;|{{ trigger.event.data.description }}| {% endif %}
        {% if trigger.event.data.get('manufacturer') is not none %}

        |Manufacturer:|&emsp;|{{ trigger.event.data.manufacturer }}| {% endif %}
        {% if trigger.event.data.get('model') is not none %}

        |Model:|&emsp;|{{ trigger.event.data.model }}| {% endif %} {% if
        trigger.event.data.get('serial') is not none %}

        |Serial:|&emsp;|{{ trigger.event.data.serial }}| {% endif %} {% if
        trigger.event.data.get('operating_system') is not none %}

        |Operating System:|&emsp;|{{ trigger.event.data.operating_system }}| {%
        endif %}
mode: parallel
```
</details>