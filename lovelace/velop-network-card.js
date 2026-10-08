/**
 * Velop Network Card — schematic of a Linksys Velop mesh for Home Assistant.
 *
 * Reads the entities of the `linksys_velop` integration via the entity
 * registry, so no entity IDs need configuring. Reads left to right: Internet →
 * primary node → secondary nodes (by backhaul parent), each layer indented, with
 * the backhaul link (wired/Wi-Fi, speed, signal) on the connector and each node's
 * connected clients listed beneath it as Wired or RSSI. The Internet box shows
 * the latest Velop speed test when those (default-disabled) sensors are on.
 *
 * Config (all optional):
 *   type: custom:velop-network-card
 *   title: Velop network
 *   weak_rssi: -70      # dBm at or below which a client is highlighted
 *   slow_mbps: 10       # negotiated rate below which a client is highlighted
 *   sort: signal        # signal (wired, then strongest to weakest, no reading last) | name
 *   collapsed: false    # start with client lists collapsed
 *   show_rate: true     # show negotiated rate column
 *   rename: true        # click a client to rename it (written back to the mesh via linksys_velop.rename_device)
 *   group_wired: true   # list wired clients in one "Wired LAN" group (the mesh can't locate them reliably)
 */

const CARD_VERSION = "2.5.0";
const PLATFORM = "linksys_velop";

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const num = (v) => {
  const n = Number(v);
  return v !== null && v !== "" && Number.isFinite(n) ? n : null;
};

const fmtSpeed = (mbps) => {
  if (mbps == null) return null;
  if (mbps >= 1000) return `${+(mbps / 1000).toFixed(mbps % 1000 < 50 ? 0 : 1)} Gb/s`;
  return `${Math.round(mbps)} Mb/s`;
};

const COLOURS = {
  excellent: "var(--success-color, #43a047)",
  good: "var(--success-color, #43a047)",
  fair: "var(--warning-color, #ffa600)",
  weak: "var(--error-color, #db4437)",
  unknown: "var(--disabled-text-color, #9e9e9e)",
  wired: "var(--secondary-text-color, #727272)",
  link: "var(--primary-color, #03a9f4)",
};

// node-scoped readings report SNR; on this hardware dBm ≈ SNR − 94 (measured offset 91–97), used only as an estimate
const SNR_OFFSET = 94;
const effRssi = (c) => (c.rssi != null ? c.rssi : c.snr != null ? c.snr - SNR_OFFSET : null);

function bucket(rssi) {
  if (rssi == null) return "unknown";
  if (rssi > -50) return "excellent";
  if (rssi > -60) return "good";
  if (rssi > -70) return "fair";
  return "weak";
}

// "Garage - 7475" -> ["Garage", "7475"]
const splitName = (name) => {
  const m = /^(.*) - ([^-]+)$/.exec(name);
  return m ? [m[1], m[2]] : [name, ""];
};

class VelopNetworkCard extends HTMLElement {
  setConfig(config) {
    this._config = {
      title: "Velop network",
      weak_rssi: -70,
      slow_mbps: 10,
      sort: "signal",
      collapsed: false,
      show_rate: true,
      rename: true,
      group_wired: true,
      ...config,
    };
    this._sig = null;
    this._open = new Map();
    this._pending = this._pending || new Map();
    this._editing = null;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 8;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 4, rows: "auto" };
  }

  static getStubConfig() {
    return {};
  }

  // region -- model --
  _model() {
    const hass = this._hass;
    const byDevice = new Map();
    for (const ent of Object.values(hass.entities || {})) {
      if (ent.platform !== PLATFORM || !ent.device_id || !ent.translation_key) continue;
      if (!byDevice.has(ent.device_id)) byDevice.set(ent.device_id, {});
      byDevice.get(ent.device_id)[ent.translation_key] = ent.entity_id;
    }
    const st = (id) => (id ? hass.states[id] : undefined);

    let mesh = null;
    let meshEntry = null;
    const nodes = [];
    for (const [deviceId, keys] of byDevice) {
      if (keys.wan_status) {
        mesh = keys;
        meshEntry = hass.devices?.[deviceId]?.config_entries?.[0] || null;
        continue;
      }
      if (!keys.node_type) continue;
      const device = hass.devices?.[deviceId];
      meshEntry = meshEntry || device?.config_entries?.[0] || null;
      const clients = (st(keys.connected_devices)?.attributes?.devices || [])
        .map((c) => {
          const type = String(c.type || "").toLowerCase();
          const rssi = num(c.rssi_dbm);
          const reported = c.name || c.mac || "Unknown";
          // show a just-saved name until the integration reports it (or it times out)
          const pending = c.id ? this._pending.get(c.id) : null;
          if (pending && (pending.name === reported || Date.now() > pending.until)) this._pending.delete(c.id);
          const showPending = pending && this._pending.has(c.id);
          return {
            id: c.id || null,
            mac: c.mac || null,
            ip: c.ip || null,
            name: showPending ? pending.name : reported,
            pending: !!showPending,
            type,
            rssi: rssi != null && rssi < 0 ? rssi : null,
            snr: num(c.snr_db) != null && num(c.snr_db) > 0 ? num(c.snr_db) : null,
            band: c.band || null,
            rate: num(c.negotiated_mbps),
            guest: !!c.guest_network,
          };
        })
        // only clients we know how they're connected; type "unknown" is typically a stale/disconnected entry
        .filter((c) => c.type === "wired" || c.type === "wireless");
      nodes.push({
        id: deviceId,
        name: device?.name_by_user || device?.name || deviceId,
        model: st(keys.model)?.state || device?.model || "",
        role: (st(keys.node_type)?.state || "").toLowerCase(),
        online: st(keys.status) ? st(keys.status).state === "on" : true,
        moreInfo: keys.status || keys.connected_devices || keys.node_type,
        clientsEntity: keys.connected_devices,
        parentName: st(keys.parent_name)?.state,
        viaDevice: device?.via_device_id,
        backhaul: {
          type: (st(keys.backhaul_connection_type)?.state || "").toLowerCase(),
          speed: num(st(keys.backhaul_speed)?.state),
          rssi: num(st(keys.backhaul_signal_strength)?.state),
        },
        clients: this._sortClients(clients),
        updateAvailable: st(keys.update)?.state === "on",
      });
    }

    // parent: parent sensor (device name) → device registry via_device → primary node
    const byName = new Map(nodes.map((n) => [n.name, n]));
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const primary = nodes.find((n) => n.role === "primary") || null;
    for (const n of nodes) {
      n.parent = n === primary ? null : byName.get(n.parentName) || byId.get(n.viaDevice) || primary;
      if (n.parent === n) n.parent = null;
      n.children = [];
    }
    for (const n of nodes) if (n.parent) n.parent.children.push(n);
    for (const n of nodes) n.children.sort((a, b) => a.name.localeCompare(b.name));
    const roots = nodes.filter((n) => !n.parent).sort((a, b) => (a === primary ? -1 : b === primary ? 1 : 0));

    // Wired clients: the mesh can't tell which node a switch-attached client is behind (sources disagree),
    // so list them once in their own LAN group instead of under a guessed node.
    let wired = [];
    if (this._config.group_wired) {
      const seen = new Set();
      for (const n of nodes) {
        for (const c of n.clients) {
          if (c.type !== "wired") continue;
          const key = c.id || c.mac || c.name;
          if (!seen.has(key)) {
            seen.add(key);
            wired.push({ ...c, node: n });
          }
        }
        n.clients = n.clients.filter((c) => c.type !== "wired");
      }
      wired = wired.sort((a, b) => a.name.localeCompare(b.name));
    }

    const wan = mesh ? st(mesh.wan_status) : undefined;
    return {
      nodes,
      roots,
      primary: primary || roots[0] || null,
      wired,
      wan: wan ? { online: wan.state === "on", ip: st(mesh.wan_ip)?.state, entity: mesh.wan_status } : null,
      speedtest: mesh ? this._speedtest(mesh, st) : null,
      meshEntry,
    };
  }

  // the mesh's own speedtest sensors (disabled by default in the integration); null if none have a value
  _speedtest(keys, st) {
    const mbps = (id) => {
      const s = st(id);
      const v = num(s?.state);
      if (v == null) return null;
      const unit = String(s.attributes?.unit_of_measurement || "Mbit/s").toLowerCase();
      if (unit.startsWith("kbit")) return v / 1000;
      if (unit.startsWith("gbit")) return v * 1000;
      if (unit.startsWith("bit")) return v / 1e6;
      return v;
    };
    const down = mbps(keys.download_bandwidth);
    const up = mbps(keys.upload_bandwidth);
    const latency = num(st(keys.speedtest_latency)?.state);
    const when = st(keys.speedtest_last_run)?.state;
    const time = when && !Number.isNaN(Date.parse(when)) ? new Date(when) : null;
    if (down == null && up == null && latency == null) return null;
    return { down, up, latency, time, entity: keys.download_bandwidth || keys.speedtest_last_run };
  }

  _when(time) {
    if (!time) return null;
    const mins = Math.round((Date.now() - time.getTime()) / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins} min ago`;
    if (mins < 24 * 60) return `${Math.round(mins / 60)} h ago`;
    const lang = this._hass?.locale?.language || undefined;
    return time.toLocaleDateString(lang, { day: "numeric", month: "short" });
  }

  _sortClients(clients) {
    if (this._config.sort === "name") return clients.sort((a, b) => a.name.localeCompare(b.name));
    // wired first, then wireless strongest to weakest, then wireless with no reading; ties by name
    const key = (c) => (c.type === "wired" ? [0, 0] : effRssi(c) == null ? [2, 0] : [1, -effRssi(c)]);
    return clients.sort((a, b) => {
      const [ga, va] = key(a);
      const [gb, vb] = key(b);
      return ga - gb || va - vb || a.name.localeCompare(b.name);
    });
  }

  _flag(c) {
    if (c.type !== "wireless") return { weak: false, slow: false };
    return {
      weak: effRssi(c) != null && effRssi(c) <= this._config.weak_rssi,
      slow: c.rate != null && c.rate < this._config.slow_mbps,
    };
  }
  // endregion

  // region -- render --
  _signature() {
    const ids = Object.values(this._hass.entities || {})
      .filter((e) => e.platform === PLATFORM)
      .map((e) => `${e.entity_id}@${this._hass.states[e.entity_id]?.last_updated}`);
    return JSON.stringify([this._config, ids]);
  }

  _render() {
    if (!this._config || !this._hass || !this.shadowRoot) return;
    if (this._editing) return; // don't replace the DOM under an open rename editor; re-rendered on close
    const sig = this._signature();
    if (sig === this._sig) return;
    this._sig = sig;

    // keep the user's expand/collapse choices across re-renders
    this.shadowRoot.querySelectorAll("details[data-node]").forEach((d) => this._open.set(d.dataset.node, d.open));

    const model = this._model();
    const cfg = this._config;
    this._meshEntry = model.meshEntry;
    this._canRename = !!(cfg.rename && model.meshEntry);
    this._clients = new Map();
    for (const n of model.nodes) for (const c of n.clients) if (c.id) this._clients.set(c.id, { client: c, node: n });
    for (const c of model.wired) if (c.id) this._clients.set(c.id, { client: c, node: c.node });
    let body;
    if (!model.nodes.length) {
      body = `<div class="empty">No <code>linksys_velop</code> nodes found. Is the Linksys Velop integration set up?</div>`;
    } else {
      const wan = model.wan;
      const sp = model.speedtest;
      // a failed run is still the latest completed run, and reports 0 bandwidth
      const failed = sp && sp.down === 0 && sp.up === 0;
      const speed = sp
        ? `<span class="speed clickable" data-entity="${esc(sp.entity)}" tabindex="0" role="button" title="Latest Velop speed test">
            <ha-icon icon="mdi:speedometer"></ha-icon>
            ${failed ? `<span class="muted">Last speed test failed</span>` : ""}
            ${!failed && sp.down != null ? `<span>↓ ${esc(fmtSpeed(sp.down))}</span>` : ""}
            ${!failed && sp.up != null ? `<span>↑ ${esc(fmtSpeed(sp.up))}</span>` : ""}
            ${!failed && sp.latency != null ? `<span>${esc(sp.latency)} ms</span>` : ""}
            ${sp.time ? `<span class="meta">${esc(this._when(sp.time))}</span>` : ""}
          </span>`
        : "";
      body = `
        <div class="tree">
          <div class="internet${wan && !wan.online ? " down" : ""}">
            <span class="wan${wan ? " clickable" : ""}" ${wan ? `data-entity="${esc(wan.entity)}" tabindex="0" role="button"` : ""}>
              <ha-icon icon="mdi:web"></ha-icon>
              <span class="name">Internet</span>
              ${wan ? `<span class="meta">${wan.online ? "online" : "offline"}${wan.ip ? ` · ${esc(wan.ip)}` : ""}</span>` : ""}
            </span>
            ${speed}
          </div>
          <ul>${model.roots.map((n) => this._branch(n, model)).join("")}</ul>
        </div>`;
    }

    this.shadowRoot.innerHTML = `
      <style>${STYLES}</style>
      <ha-card>
        ${cfg.title ? `<h1 class="card-header">${esc(cfg.title)}</h1>` : ""}
        <div class="content">${body}</div>
      </ha-card>`;

    this.shadowRoot.querySelectorAll("[data-entity]").forEach((el) => {
      const open = (ev) => {
        ev.stopPropagation();
        this.dispatchEvent(
          new CustomEvent("hass-more-info", { detail: { entityId: el.dataset.entity }, bubbles: true, composed: true })
        );
      };
      el.addEventListener("click", open);
      el.addEventListener("keydown", (ev) => (ev.key === "Enter" || ev.key === " ") && (ev.preventDefault(), open(ev)));
    });

    this.shadowRoot.querySelectorAll(".client.editable").forEach((row) => {
      row.addEventListener("click", () => this._startEdit(row));
      row.addEventListener("keydown", (ev) => {
        if (ev.target === row && (ev.key === "Enter" || ev.key === " ")) {
          ev.preventDefault();
          this._startEdit(row);
        }
      });
    });
  }

  // inline rename: writes the new name back to the mesh via linksys_velop.rename_device
  _startEdit(row) {
    if (this._editing) return;
    const id = row.dataset.client;
    const info = this._clients.get(id);
    if (!info) return;
    this._editing = id;

    const form = document.createElement("form");
    form.className = "rename";
    const input = document.createElement("input");
    input.value = info.client.name;
    input.maxLength = 64;
    input.setAttribute("aria-label", `New name for ${info.client.name}`);
    const save = document.createElement("button");
    save.type = "submit";
    save.textContent = "Save";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = "Cancel";
    cancel.className = "secondary";
    const msg = document.createElement("span");
    msg.className = "msg";
    form.append(input, save, cancel, msg);
    form.addEventListener("click", (ev) => ev.stopPropagation());

    const finish = () => {
      this._editing = null;
      this._sig = null;
      this._render();
    };
    cancel.addEventListener("click", finish);
    input.addEventListener("keydown", (ev) => {
      ev.stopPropagation();
      if (ev.key === "Escape") finish();
    });
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const name = input.value.trim();
      if (!name || name === info.client.name) return finish();
      input.disabled = save.disabled = cancel.disabled = true;
      msg.classList.remove("bad");
      msg.textContent = "Saving to the mesh…";
      try {
        await this._hass.callService(PLATFORM, "rename_device", { mesh: this._meshEntry, device: id, new_name: name });
        this._pending.set(id, { name, until: Date.now() + 3 * 60 * 1000 });
        finish();
        // ask the integration to poll now so the new name is confirmed sooner
        if (info.node.clientsEntity) {
          this._hass
            .callService("homeassistant", "update_entity", { entity_id: info.node.clientsEntity })
            .catch(() => {});
        }
      } catch (err) {
        input.disabled = save.disabled = cancel.disabled = false;
        msg.classList.add("bad");
        msg.textContent = `Rename failed: ${err?.message || err}`;
        input.focus();
      }
    });

    row.classList.add("editing");
    row.removeAttribute("title");
    row.querySelector(".cname").replaceWith(form);
    input.focus();
    input.select();
  }

  _linkLabel(n, model) {
    if (!n.parent) {
      const down = model.wan && !model.wan.online;
      return { text: down ? "WAN down" : "WAN", colour: down ? COLOURS.weak : COLOURS.link, dashed: false };
    }
    if (n.backhaul.type === "wireless") {
      const rssi = n.backhaul.rssi != null && n.backhaul.rssi < 0 ? n.backhaul.rssi : null;
      return {
        text: ["Wi-Fi", fmtSpeed(n.backhaul.speed), rssi != null ? `${rssi} dBm` : null].filter(Boolean).join(" · "),
        colour: COLOURS[bucket(rssi)],
        dashed: true,
      };
    }
    return {
      text: [n.backhaul.type === "wired" ? "Wired" : "Backhaul", fmtSpeed(n.backhaul.speed)].filter(Boolean).join(" · "),
      colour: COLOURS.link,
      dashed: false,
    };
  }

  _branch(n, model) {
    const link = this._linkLabel(n, model);
    const colour = n.online ? link.colour : COLOURS.unknown;
    const [short, serial] = splitName(n.name);
    const meta = [n.model, n.role, serial ? `#${serial}` : null].filter(Boolean).join(" · ");
    const open = this._open.has(n.id) ? this._open.get(n.id) : !this._config.collapsed;

    return `
      <li class="branch${link.dashed ? " dashed" : ""}" style="--link:${colour}">
        <div class="link-label" style="color:${colour}">${esc(link.text)}</div>
        <div class="node${n.online ? "" : " offline"}">
          <div class="node-head clickable" data-entity="${esc(n.moreInfo)}" tabindex="0" role="button">
            <span class="status" style="background:${n.online ? COLOURS.excellent : COLOURS.weak}"
              title="${n.online ? "online" : "offline"}"></span>
            <span class="name">${esc(short)}</span>
            <span class="meta">${esc(meta)}</span>
            ${n.updateAvailable ? `<ha-icon class="update" icon="mdi:arrow-up-circle" title="Firmware update available"></ha-icon>` : ""}
          </div>
          ${this._clientList(n.id, n.clients, this._config.group_wired ? "Wi-Fi client" : "client", open)}
        </div>
        ${this._children(n, model)}
      </li>`;
  }

  _children(n, model) {
    const lan = n === model.primary && model.wired.length ? this._wiredBranch(model) : "";
    const kids = n.children.map((k) => this._branch(k, model)).join("");
    return kids || lan ? `<ul>${kids}${lan}</ul>` : "";
  }

  _clientList(key, clients, noun, open) {
    if (!clients.length) return `<div class="none">No ${noun}s</div>`;
    return `
      <details data-node="${esc(key)}" ${open ? "open" : ""}>
        <summary>${clients.length} ${noun}${clients.length === 1 ? "" : "s"}</summary>
        <div class="clients">${clients.map((c) => this._client(c)).join("")}</div>
      </details>`;
  }

  _wiredBranch(model) {
    const key = "wired-lan";
    const open = this._open.has(key) ? this._open.get(key) : !this._config.collapsed;
    return `
      <li class="branch lan" style="--link:${COLOURS.link}">
        <div class="link-label" style="color:${COLOURS.link}">LAN</div>
        <div class="node lan">
          <div class="node-head">
            <ha-icon class="lan-icon" icon="mdi:lan"></ha-icon>
            <span class="name">Wired LAN</span>
            <span class="meta" title="Wired clients share the LAN with every wired node, so the mesh can't say which node or switch they're behind.">location not reported by the mesh</span>
          </div>
          ${this._clientList(key, model.wired, "wired client", open)}
        </div>
      </li>`;
  }

  _client(c) {
    const f = this._flag(c);
    let icon;
    let signal;
    if (c.type === "wired") {
      icon = `<ha-icon icon="mdi:ethernet" style="color:${COLOURS.wired}"></ha-icon>`;
      signal = `<span class="sig muted">Wired</span>`;
    } else {
      const r = effRssi(c);
      const colour = COLOURS[bucket(r)];
      icon = `<ha-icon icon="${r == null ? "mdi:wifi-strength-outline" : r > -60 ? "mdi:wifi-strength-4" : r > -70 ? "mdi:wifi-strength-2" : "mdi:wifi-strength-1"}" style="color:${colour}"></ha-icon>`;
      const text = c.rssi != null ? `${c.rssi} dBm` : c.snr != null ? `SNR ${c.snr} dB` : "Wi-Fi";
      signal = `<span class="sig${f.weak ? " bad" : ""}">${text}</span>`;
    }
    const rate =
      this._config.show_rate && c.type === "wireless" && c.rate != null
        ? `<span class="rate${f.slow ? " bad" : ""}">${c.rate} Mb/s</span>`
        : `<span class="rate"></span>`;
    const editable = this._canRename && c.id;
    const title = [
      c.pending ? `${c.name} (saving…)` : c.name,
      c.mac ? `MAC: ${c.mac}` : null,
      c.ip ? `IP: ${c.ip}` : null,
      c.snr != null ? `SNR: ${c.snr} dB${c.rssi == null ? ` (≈ ${c.snr - SNR_OFFSET} dBm)` : ""}` : null,
      editable && !c.pending ? "Click to rename" : null,
    ]
      .filter(Boolean)
      .join("\n");
    return `
      <div class="client ${c.type}${f.weak || f.slow ? " flagged" : ""}${c.pending ? " pending" : ""}${editable ? " editable" : ""}"
        title="${esc(title)}"
        ${editable ? `data-client="${esc(c.id)}" tabindex="0" role="button" aria-label="Rename ${esc(c.name)}"` : ""}>
        ${icon}
        <span class="cname">${esc(c.name)}${c.guest ? `<span class="tag">guest</span>` : ""}</span>
        <span class="band">${esc(c.band || "")}</span>
        ${signal}
        ${rate}
      </div>`;
  }
  // endregion
}

const STYLES = `
  :host { display: block; --indent: 22px; --elbow: 40px; --line: var(--divider-color, #e0e0e0); }
  .content { padding: 0 16px 16px; }
  .empty { color: var(--secondary-text-color); font-size: 14px; }
  .clickable { cursor: pointer; outline: none; border-radius: 8px; }
  .clickable:focus-visible { box-shadow: 0 0 0 2px var(--primary-color, #03a9f4); }
  ha-icon { --mdc-icon-size: 18px; display: inline-flex; flex: none; }

  .internet {
    display: inline-flex; align-items: center; flex-wrap: wrap; column-gap: 14px; row-gap: 2px; padding: 6px 14px;
    border: 1.5px solid var(--primary-color, #03a9f4); border-radius: 22px;
    color: var(--primary-text-color); max-width: 100%; box-sizing: border-box;
  }
  .wan, .speed { display: inline-flex; align-items: center; gap: 8px; }
  .speed { font-size: 13px; font-variant-numeric: tabular-nums; }
  .speed ha-icon { --mdc-icon-size: 16px; color: var(--secondary-text-color); }
  .internet.down { border-color: var(--error-color, #db4437); }
  .internet ha-icon { color: var(--primary-color, #03a9f4); }
  .internet.down ha-icon { color: var(--error-color, #db4437); }
  .name { font-weight: 600; font-size: 15px; color: var(--primary-text-color); }
  .meta { font-size: 12px; color: var(--secondary-text-color); }

  /* indented tree with elbow connectors */
  .tree ul { list-style: none; margin: 0 0 0 calc(var(--indent) - 1px); padding: 0; }
  .tree > ul { margin-left: 18px; }
  .branch { position: relative; padding: 6px 0 0 var(--indent); }
  .branch::before {           /* trunk from parent down past this branch */
    content: ""; position: absolute; left: 0; top: 0; bottom: 0; border-left: 2px solid var(--line);
  }
  .branch:last-child::before { bottom: auto; height: var(--elbow); }
  .branch::after {            /* elbow into this node, styled as the backhaul link */
    content: ""; position: absolute; left: 0; top: 0; width: calc(var(--indent) - 3px); height: var(--elbow);
    border-left: 2px solid var(--link); border-bottom: 2px solid var(--link); border-bottom-left-radius: 8px;
  }
  .branch.dashed::after { border-left-style: dashed; border-bottom-style: dashed; }
  .link-label { font-size: 11px; line-height: 14px; height: 14px; margin: 0 0 2px 2px; white-space: nowrap; }

  .node {
    background: var(--secondary-background-color, #f5f5f5);
    border: 1px solid var(--line); border-radius: 12px; padding: 6px 10px 8px; min-width: 0;
  }
  .node.offline { border-color: var(--error-color, #db4437); opacity: 0.7; }
  .node-head { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; padding: 2px 0; }
  .status { width: 9px; height: 9px; border-radius: 50%; flex: none; align-self: center; }
  .update { color: var(--warning-color, #ffa600); --mdc-icon-size: 16px; align-self: center; margin-left: auto; }

  details > summary {
    font-size: 12px; color: var(--secondary-text-color); cursor: pointer; padding: 2px 0; list-style-position: inside;
  }

  .clients { margin-top: 4px; }
  .client {
    display: flex; align-items: center; column-gap: 8px; flex-wrap: wrap;
    padding: 3px 0; border-top: 1px solid var(--line); font-size: 13px; color: var(--primary-text-color);
  }
  .cname { flex: 1 1 0; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; line-height: 18px; }
  .band { flex: none; width: 44px; font-size: 11px; color: var(--secondary-text-color); }
  .sig, .rate { flex: none; text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .sig { width: 72px; }
  .rate { width: 64px; font-size: 12px; color: var(--secondary-text-color); }
  .node { container-type: inline-size; }
  /* narrow node: readings wrap onto a second line under the name */
  .client > ha-icon { width: 20px; overflow: hidden; }
  @container (max-width: 340px) {
    .client:not(.wired) .cname { flex-basis: calc(100% - 34px); }
    .sig, .rate { width: auto; }
    .client .band { margin-left: 28px; width: auto; flex: 1 1 0; min-width: 0; }
    .client.wired .band, .client .rate:empty { display: none; }
  }
  .muted { color: var(--secondary-text-color); }
  .bad { color: var(--error-color, #db4437) !important; font-weight: 600; }
  .client.flagged .cname { font-weight: 500; }
  .none { font-size: 12px; color: var(--secondary-text-color); padding: 2px 0; }
  .node.lan .node-head { cursor: default; }
  .lan-icon { color: var(--primary-color, #03a9f4); align-self: center; --mdc-icon-size: 18px; }
  .node.lan .meta { cursor: help; }
  .client.editable { cursor: pointer; outline: none; }
  .client.editable:hover .cname { text-decoration: underline dotted var(--secondary-text-color); text-underline-offset: 3px; }
  .client.editable:focus-visible { box-shadow: inset 0 0 0 2px var(--primary-color, #03a9f4); border-radius: 4px; }
  .client.pending .cname { font-style: italic; color: var(--secondary-text-color); }
  .client.editing .band, .client.editing .sig, .client.editing .rate { display: none; }
  form.rename { flex: 1 1 0; min-width: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 0; }
  form.rename input {
    flex: 1 1 120px; min-width: 0; font: inherit; font-size: 13px; padding: 3px 6px;
    border: 1px solid var(--primary-color, #03a9f4); border-radius: 6px;
    background: var(--card-background-color, #fff); color: var(--primary-text-color);
  }
  form.rename button {
    font: inherit; font-size: 12px; padding: 3px 10px; border-radius: 6px; cursor: pointer;
    border: 1px solid var(--primary-color, #03a9f4); background: var(--primary-color, #03a9f4);
    color: var(--text-primary-color, #fff);
  }
  form.rename button.secondary { background: transparent; color: var(--primary-color, #03a9f4); }
  form.rename button:disabled { opacity: 0.5; cursor: default; }
  form.rename .msg { flex-basis: 100%; font-size: 11px; color: var(--secondary-text-color); }
  form.rename .msg:empty { display: none; }
  form.rename .msg.bad { color: var(--error-color, #db4437); }
  .tag {
    font-size: 10px; margin-left: 6px; padding: 0 5px; border-radius: 6px;
    background: var(--divider-color, #e0e0e0); color: var(--secondary-text-color);
  }
`;

if (!customElements.get("velop-network-card")) customElements.define("velop-network-card", VelopNetworkCard);

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "velop-network-card")) {
  window.customCards.push({
    type: "velop-network-card",
    name: "Velop Network Card",
    description: "Linksys Velop mesh as a left-to-right tree: nodes, backhaul links and each node's clients.",
    preview: false,
  });
}

console.info(`%c VELOP-NETWORK-CARD %c ${CARD_VERSION} `, "color:#fff;background:#03a9f4", "");
