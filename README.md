
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
  - list of device names, IP addresses, adapter types and guest network 
    state for the online devices
- Mesh: Date of Latest Speedtest
  - Exit code, Latency, Download/Upload bandwidth, Result ID
- Mesh: Number of Available Storage Partitions *(disabled by default)*
  - list of the available partitions including the following information: IP, 
    label, available Kb, used Kb, used %age and last checked time
- Node: Number of Connected Devices
  - list of names, IP addresses and guest network state for the connected 
    devices
- Node: Current Firmware Version
- Node: Last Update Check *(disabled by default)*
- Node: Model Number
- Node: Newest Firmware Version
- Node: Parent Name
  - IP address of the parent, backhaul information (connection type and 
    speed in Mbps)
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

Example output can be found [here](examples/diagnostics_ouput.json)

# Example Lovelace UI

| Dark Mode | Light Mode |
|:---:|:---:|
| ![Lovelace Dark UI](images/lovelace_dark.png) | ![Lovelace Light UI](images/lovelace_light.png) |

*Some items of detail have been pixelated for privacy purposes.*

The view consists of 3 main cards.  These are detailed below.

## Card 1

This card is used mainly to work around a limitation in Button Card documented
[here](https://github.com/custom-cards/button-card#injecting-css-with-extra_styles).

### Pre-requisites

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

## Card 2

This card creates the Mesh part of the view.

### Pre-requisites

- [Button Card](https://github.com/custom-cards/button-card)
- [card-mod](https://github.com/thomasloven/lovelace-card-mod)
- [fold-entity-row](https://github.com/thomasloven/lovelace-fold-entity-row)
- [hui-element](https://github.com/thomasloven/lovelace-hui-element)
- [Stack In Card](https://github.com/custom-cards/stack-in-card)
- [template-entity-row](https://github.com/thomasloven/lovelace-template-entity-row)

<details>
  <summary>YAML for the card</summary>

```yaml
type: custom:stack-in-card
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

              div.info { text-align: center !important; width: 100%; margin: 0;
              padding: 4px; }
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
              action: toggle
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
            {% set friendly_name = state_attr(config.entity, 'friendly_name') %}
            {% if friendly_name %}
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
              {% set devices = state_attr('sensor.velop_mesh_online_devices',
              'devices') %} | # | Name | IP | Type |

              |:---:|:---|---:|:---:| {%- for device in devices -%}
                {% set idx = loop.index %}
                {%- for device_name, device_details in device.items() -%}
                  {%- set device_ip = device_details.ip -%}
                  {%- set connection_type = device_details.connection | lower -%}
                  {%- if connection_type == "wired" -%}
                    {%- set connection_icon = "ethernet" -%}
                  {% elif connection_type == "wireless" -%}
                    {%- set connection_icon = "wifi" -%}
                  {% elif connection_type == "unknown" -%}
                    {%- set connection_icon = "help" -%}
                  {% else -%}
                    {%- set connection_icon = "" -%}
                  {%- endif %}
              {{ "| {} | {} | {} | {} |".format(idx, device_name, device_ip,
              '<ha-icon icon="hass:' ~ connection_icon ~ '"></ha-icon>') }}
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
            {% set friendly_name = state_attr(config.entity, 'friendly_name') %}
            {% if friendly_name %}
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
              {% set devices = state_attr('sensor.velop_mesh_offline_devices',
              'devices') %}

              | # | Name |

              |:---:|:---|

              {% for device in devices %} {{ "| {} | {} |".format(loop.index,
              device) }}

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
                state_attr('sensor.velop_mesh_available_storage', 'partitions')
                %}

                | Host | Label | %age used

                |:---:|:---:|:---:|

                {% for partition in partitions %} {{ "| {} | {} | {}
                |".format(partition.ip, partition.label, partition.used_percent)
                }}

                {% endfor %}
```
</details>

## Card 3

This card creates the Node part of the view.

### Pre-requisites

- [auto-entities](https://github.com/thomasloven/lovelace-auto-entities)
- [Button Card](https://github.com/custom-cards/button-card)
- [card-mod](https://github.com/thomasloven/lovelace-card-mod)
- [Config Template Card](https://github.com/thomasloven/lovelace-hui-element)
- [fold-entity-row](https://github.com/thomasloven/lovelace-fold-entity-row)
- [hui-element](https://github.com/thomasloven/lovelace-hui-element)
- [Stack In Card](https://github.com/custom-cards/stack-in-card)
- [template-entity-row](https://github.com/thomasloven/lovelace-template-entity-row)

<details>
  <summary>YAML for the card</summary>

```yaml
type: custom:auto-entities
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
            "sensor." + "this.entity_id".split(".")[1].split("_").slice(0,
            -1).join("_") + "_connected_devices"
          ID_LAST_UPDATE_CHECK: >
            "sensor." + "this.entity_id".split(".")[1].split("_").slice(0,
            -1).join("_") + "_last_update_check"
          ID_MODEL: >
            "sensor." +
            "this.entity_id".split(".")[1].split("_").slice(0,-1).join("_") +
            "_model"
          ID_PARENT: >
            "sensor." +
            "this.entity_id".split(".")[1].split("_").slice(0,-1).join("_") +
            "_parent"
          ID_SERIAL: >
            "sensor." +
            "this.entity_id".split(".")[1].split("_").slice(0,-1).join("_") +
            "_serial"
          ID_UPDATE_AVAILABLE: >
            "binary_sensor." +
            "this.entity_id".split(".")[1].split("_").slice(0,-1).join("_") +
            "_update_available"
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
              entity_picture: ${'/local/velop_nodes/' + states[ID_MODEL].state + '.png'}
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
                  ${(states[ID_PARENT].state && states[ID_PARENT].state !=
                  'unknown') ? 'Connected to ' + states[ID_PARENT].state :
                  'N/A'}
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
                div[id^="attr_"] { justify-self: end; } div[id^="attr_label_"] {
                justify-self: start; margin-left: 20px; } #label, #attr_parent {
                padding-top: 25px; font-size: smaller; }
              styles:
                card:
                  - padding: 16px
                grid:
                  - grid-template-areas: >-
                      "n n attr_update s" "i attr_label_model attr_label_model
                      attr_model" "i attr_label_serial attr_label_serial
                      attr_serial" "i attr_label_ip attr_label_ip attr_ip" "l l
                      l attr_parent"
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
                              state-badge { display: none; } state-badge + div {
                              margin-left: 8px !important; padding-top: 10px; }
                          '#wrapper': >
                            state-badge { display: none; } state-badge + div {
                            margin-left: 8px !important; }
                    head:
                      type: section
                      label: Additional Information
                    padding: 0
                  filter:
                    include:
                      - entity_id: ${ID_LAST_UPDATE_CHECK}
                        options:
                          name: Last update check
                      - entity_id: ${ID_PARENT}
                        not:
                          state: unknown
                        options:
                          type: custom:template-entity-row
                          name: Backhaul
                          state: >-
                            {% set backhaul_info = state_attr(config.entity,
                            'backhaul') %} {% set backhaul_speed =
                            backhaul_info.speed_mbps | round(2) %} {% if
                            (backhaul_speed | string).split('.')[1] == '0' %}
                              {% set backhaul_speed = backhaul_speed | int %}
                            {% endif %} {{ backhaul_info.connection }} ({{
                            backhaul_speed }} Mbps)
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
                      style: |
                        state-badge { display: none; }
                        state-badge + div { margin-left: 8px !important; }
                        .info.pointer { font-weight: 500; }
                        .state { margin-right: 10px; }
                    entity: ${ID_CONNECTED_DEVICES}
                    name: >-
                      {% set name = state_attr(config.entity, 'friendly_name')
                      %} {% if name %}
                        {{ name.split(':')[1].strip() }}
                      {% endif %}
                  entities:
                    - type: custom:hui-element
                      card_type: markdown
                      content: ${CONNECTED_DEVICES_TEXT(ID_CONNECTED_DEVICES)}
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
