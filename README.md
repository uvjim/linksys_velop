
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

- Mesh: Checking for Updates
- Mesh: Speedtest state
  - current stage of the Speedtest, e.g. Detecting server, Checking latency
- Mesh: WAN Status
  - IP, DNS, MAC
- Node: Status
  - IP, MAC
- Node: Update Available

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
- Node: Number of Connected Devices
  - list of device names and IP addresses that are connected
- Node: Current Firmware Version
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

![Initial Setup Screen](https://github.com/uvjim/linksys_velop/raw/main/images/setup_user.png)

- `Primary node address`: must be the node classed as the primary node
- `Password`: the password you would use to log in to either the app or the 
  web UI

On successful set up the following screen will be seen detailing the Mesh 
device and the individual nodes found in the mesh.

![Final Setup Screen](https://github.com/uvjim/linksys_velop/raw/main/images/setup_final.png)

## Configurable Options

It is possible to configure the following options for the integration.

#### Timers

![Configure Timers](https://github.com/uvjim/linksys_velop/raw/main/images/config_timers.png)

- `Scan Interval`: the frequency of updates for the sensors, default `30s`
- `Device Tracker Interval`: the frequency of updates for the device 
  trackers, default `10s`
- `Consider Home Period`: the time to wait before considering a device away 
  after it notifies of becoming disconnected, default `180s`

#### Device Trackers

![Configure Device Trackers](https://github.com/uvjim/linksys_velop/raw/main/images/config_device_trackers.png)

- `Available devices`: a multi-select list of the devices found on the mesh. 
  This list excludes any device which doesn't have a name - typically 
  displayed in the official interfaces as `Network Device`

# Example Lovelace UI

| Dark Mode | Light Mode |
|:---:|:---:|
| ![Lovelace Dark UI](https://github.com/uvjim/linksys_velop/raw/main/images/lovelace_dark.png) | ![Lovelace Light UI](https://github.com/uvjim/linksys_velop/raw/main/images/lovelace_light.png) |

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
  - title: Mesh
    path: mesh
    icon: ''
    badges: []
    cards:
      - type: custom:button-card
        color_type: blank-card
      - type: custom:stack-in-card
        view_layout:
          grid-area: first
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
                  type: divider
              - type: conditional
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
                card_mod:
                  style:
                    hui-attribute-row$:
                      hui-generic-entity-row$: >
                        state-badge, .info.pointer.text-content { display: none;
                        }
                      hui-generic-entity-row: >
                        div { text-align: center !important; width: 100%;
                        margin: 0; padding: 4px; }
              - type: divider
              - type: custom:stack-in-card
                mode: horizontal
                keep:
                  margin: true
                card_mod:
                  style: |
                    ha-card { box-shadow: none }
                cards:
                  - type: custom:button-card
                    entity: binary_sensor.velop_mesh_check_for_updates_status
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
                        - color: |
                            [[[
                              var ret = 'var(--primary-text-color)'
                              if (entity.state == 'on') {
                                ret = 'darkcyan'
                              }
                              return ret
                            ]]]
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
              - type: divider
              - type: custom:fold-entity-row
                padding: 0
                clickable: true
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

                      |:---:|---|---|:---:| {%- for device in devices -%}
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
                clickable: true
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

                      |:---:|---|

                      {% for device in devices %} {{ "| {} | {}
                      |".format(loop.index, device) }}

                      {% endfor %}
      - type: custom:auto-entities
        card:
          type: vertical-stack
        card_param: cards
        filter:
          include:
            - entity_id: /^binary_sensor\.velop_(?!(mesh)).*_status/
              options:
                type: custom:config-template-card
                variables:
                  ID_CONNECTED_DEVICES: >
                    "sensor." +
                    "this.entity_id".split(".")[1].split("_").slice(0,
                    -1).join("_") + "_connected_devices"
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
                    |:---:|---|---|:---:|
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
                              "n n n" "i attr_label_model attr_model" "i
                              attr_label_serial attr_serial" "i attr_label_ip
                              attr_ip" "l l attr_parent"
                          - grid-template-rows: 1fr 1fr 1fr 1fr 1fr
                          - grid-template-columns: 15% 1fr max-content
                        name:
                          - font-size: larger
                          - justify-self: start
                          - padding-bottom: 20px
                        label:
                          - justify-self: start
                        custom_fields:
                          attr_parent:
                            - justify-self: end
                          attr_update:
                            - position: absolute
                            - top: 8px
                            - right: 48px
                            - color: darkred
                        state:
                          - position: absolute
                          - top: 8px
                          - right: 16px
                          - color: |-
                              [[[
                                return (entity.state == 'on' ? 'darkcyan' : 'darkred')
                              ]]]
                    - type: entities
                      card_mod:
                        style: |
                          #states { padding-left: 8px; padding-right: 8px; }
                      entities:
                        - type: divider
                        - type: custom:fold-entity-row
                          padding: 0
                          clickable: true
                          group_config:
                            card_mod:
                              style:
                                hui-generic-entity-row:
                                  $: >
                                    state-badge { display: none; }

                                    state-badge + div { margin-left: 8px
                                    !important; }
                          head:
                            type: custom:template-entity-row
                            entity: ${ID_CONNECTED_DEVICES}
                            tap_action:
                              action: fire-dom-event
                              fold_row: true
                            name: >-
                              {% set name = state_attr(config.entity,
                              'friendly_name') %} {% if name %}
                                {{ name.split(':')[1].strip() }}
                              {% endif %}
                            card_mod:
                              style: >
                                state-badge { display: none; }

                                state-badge + div { margin-left: 8px !important;
                                }

                                .info.pointer { font-weight: 500; }

                                .state { margin-right: 10px; }
                          entities:
                            - type: custom:hui-element
                              card_type: markdown
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
                              content: ${CONNECTED_DEVICES_TEXT(ID_CONNECTED_DEVICES)}
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
