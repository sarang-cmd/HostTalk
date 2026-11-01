import { api, applyTheme, formatSize, state } from "./core.js";

const $ = (id) => document.getElementById(id);
let confirmHandler = null;
let summary = null;
let setupMode = false;

document.addEventListener("DOMContentLoaded", () => {
  applyTheme(state.prefs.theme);
  wireDialogs();
  $("login-form").addEventListener("submit", onLogin);
  $("setup-form").addEventListener("submit", onSetup);
  $("settings-form").addEventListener("submit", onSaveSettings);
  $("password-form").addEventListener("submit", onChangePassword);
  $("controls-form").addEventListener("submit", onSaveControls);
  $("host-form").addEventListener("submit", onSaveHost);
  $("logs-refresh").addEventListener("click", () => loadLogs());
  $("log-level").addEventListener("change", () => loadLogs());
  $("refresh-all").addEventListener("click", () => loadSummary());
  $("ls-scan").addEventListener("click", scanLocalSend);
  $("shutdown-btn").addEventListener("click", onShutdown);
  $("console-confirm-action").addEventListener("click", () => {
    const handler = confirmHandler;
    confirmHandler = null;
    closeDialog("console-confirm");
    if (handler) handler();
  });
  start();
});

async function start() {
  try {
    const status = await api.get("/api/status");
    if (!status.server.setup_complete) {
      showSetup();
      return;
    }
  } catch (error) {
    showLogin(error.message);
    return;
  }
  await loadSummary(true);
}

/* ---------------------------------------------------------------------- views */
function showSetup() {
  setupMode = true;
  $("setup-view").hidden = false;
  $("login-view").hidden = true;
  $("dashboard").hidden = true;
  setTimeout(() => $("setup-password").focus(), 40);
}

function showLogin(message = "") {
  $("login-view").hidden = false;
  $("setup-view").hidden = true;
  $("dashboard").hidden = true;
  if (message) showError("login-error", message);
  setTimeout(() => $("login-password").focus(), 40);
}

function showDashboard() {
  $("login-view").hidden = true;
  $("setup-view").hidden = true;
  $("dashboard").hidden = false;
}

/* --------------------------------------------------------------------- setup */
async function onSetup(event) {
  event.preventDefault();
  const submit = $("setup-submit");
  showError("setup-error", "");
  const payload = {
    room_name: $("setup-room").value.trim(),
    password: $("setup-password").value,
    host_user: $("setup-host-user").value.trim(),
    host_password: $("setup-host-password").value,
    port: Number($("setup-port").value),
    bind: $("setup-bind").value,
    localsend: $("setup-localsend").checked,
  };
  if (!payload.room_name) {
    showError("setup-error", "Give the room a name.");
    return;
  }
  if (payload.password.length < 4) {
    showError("setup-error", "Use at least 4 characters for the join password.");
    return;
  }
  if (!payload.host_user) {
    showError("setup-error", "Give the host a name.");
    return;
  }
  if (payload.host_password.length < 6) {
    showError("setup-error", "Use at least 6 characters for the host password.");
    return;
  }
  submit.disabled = true;
  submit.textContent = "Setting up";
  try {
    const data = await api.post("/api/setup", payload);
    if (data.localsend !== undefined) {
      await api.post("/api/host/session", {
        username: payload.host_user,
        password: payload.host_password,
      });
      await api.patch("/api/host/settings", { localsend: { enabled: Boolean(payload.localsend) } });
    }
    const currentPort = Number(window.location.port || 80);
    if (data.port && Number(data.port) !== currentPort) {
      $("setup-note").textContent = `Saved. Restart HostTalk to listen on port ${data.port}, then open the console again.`;
      submit.textContent = "Saved";
      return;
    }
    window.location.reload();
  } catch (error) {
    showError("setup-error", error.message);
    submit.disabled = false;
    submit.textContent = "Finish setup";
  }
}

/* --------------------------------------------------------------------- login */
async function onLogin(event) {
  event.preventDefault();
  const submit = $("login-submit");
  showError("login-error", "");
  submit.disabled = true;
  try {
    await api.post("/api/host/session", {
      username: $("login-user").value.trim(),
      password: $("login-password").value,
    });
    await loadSummary(true);
  } catch (error) {
    showError("login-error", error.message);
    $("login-password").select();
  } finally {
    submit.disabled = false;
  }
}

/* ----------------------------------------------------------------- dashboard */
async function loadSummary(initial = false) {
  try {
    summary = await api.get("/api/host/summary");
  } catch (error) {
    if (initial || error.status === 403) showLogin(error.status === 403 ? "" : error.message);
    else toast(error.message, "error");
    return;
  }
  showDashboard();
  renderHero();
  renderChecks();
  renderSettings();
  renderLocalSend();
  renderRooms();
  await Promise.all([loadPeople(), loadLogs()]);
}

function renderHero() {
  const server = summary.server;
  $("dash-room").textContent = server.room_name;
  $("dash-address").textContent = summary.network.address;
  $("dash-port").textContent = server.port;
  $("dash-version").textContent = server.version;
  const statePill = $("dash-state");
  statePill.className = `pill ${summary.check_status === "ok" ? "pill--live" : "pill--warn"}`;
  statePill.innerHTML = `<span class="dot"></span>${summary.check_status === "ok" ? "Live" : "Check the warnings"}`;
  $("data-note").textContent = `${summary.stats.messages} messages, ${summary.stats.attachments} files (${formatSize(summary.stats.attachment_bytes)}), database ${formatSize(summary.stats.db_bytes)}. Data folder: ${server.data_dir}.`;
}

function renderChecks() {
  const list = $("checks");
  list.innerHTML = summary.checks
    .map(
      (check) => `<li class="check" data-status="${check.status}">
        <span class="check__icon" aria-hidden="true"></span>
        <span>
          <span class="check__label">${escapeText(check.label)}</span>
          <span class="check__detail">${escapeText(check.detail)}</span>
          ${check.fix && check.status !== "ok" ? `<span class="check__fix">${escapeText(check.fix)}</span>` : ""}
        </span>
        <span class="pill ${check.status === "ok" ? "pill--live" : "pill--warn"}">${check.status}</span>
      </li>`
    )
    .join("");
  const pill = $("checks-status");
  pill.textContent = summary.check_status === "ok" ? "All good" : summary.check_status === "warn" ? "Warnings" : "Problems";
  pill.className = `pill ${summary.check_status === "ok" ? "pill--live" : "pill--warn"}`;
}

function renderSettings() {
  const config = summary.config;
  $("set-room-name").value = config.room_name;
  $("set-port").value = config.port;
  $("set-bind").value = config.bind === "127.0.0.1" ? "127.0.0.1" : "0.0.0.0";
  $("set-max-upload").value = config.max_upload_mb;
  $("set-max-members").value = config.max_room_members;
  $("set-theme").value = config.default_theme || "auto";
  $("set-level").value = config.log_level;
  $("set-previews").checked = Boolean(config.previews_enabled);
  $("set-gifs").checked = Boolean(config.gifs_enabled);
  $("set-console-local").checked = Boolean(config.console_local_only);
  $("set-localsend").checked = Boolean(config.localsend.enabled);
  $("set-ls-alias").value = config.localsend.alias || "HostTalk";
  $("set-ls-pin").value = "";
  $("set-ls-pin").placeholder = config.localsend.pin === "set" ? "Set. Type a new PIN." : "Optional";
  $("set-klipy").value = "";
  $("set-klipy").placeholder = config.klipy_key === "set" ? "Set. Type a new key." : "Not set";
  $("restart-pill").hidden = true;
  $("set-locked").checked = Boolean(config.room_locked);
  $("set-read-only").checked = Boolean(config.read_only);
  $("set-slow-mode").value = Number(config.slow_mode_seconds || 0);
  $("set-notice").value = config.notice_text || "";
  const hostUser = $("host-user");
  if (hostUser && document.activeElement !== hostUser) hostUser.value = config.host_user || "host";
}

async function onSaveSettings(event) {
  event.preventDefault();
  const status = $("settings-status");
  status.textContent = "Saving";
  status.dataset.tone = "";
  const patch = {
    room_name: $("set-room-name").value.trim(),
    port: Number($("set-port").value),
    bind: $("set-bind").value,
    max_upload_mb: Number($("set-max-upload").value),
    max_room_members: Number($("set-max-members").value),
    default_theme: $("set-theme").value,
    log_level: $("set-level").value,
    previews_enabled: $("set-previews").checked,
    gifs_enabled: $("set-gifs").checked,
    console_local_only: $("set-console-local").checked,
    localsend: {
      enabled: $("set-localsend").checked,
      alias: $("set-ls-alias").value.trim() || "HostTalk",
    },
  };
  const pin = $("set-ls-pin").value.trim();
  if (pin) patch.localsend.pin = pin;
  const klipy = $("set-klipy").value.trim();
  if (klipy) patch.klipy_key = klipy;
  try {
    const data = await api.patch("/api/host/settings", patch);
    status.textContent = data.restart_required
      ? "Saved. Restart HostTalk to listen on the new address."
      : "Saved.";
    status.dataset.tone = data.restart_required ? "warn" : "";
    $("restart-pill").hidden = !data.restart_required;
    await loadSummary();
  } catch (error) {
    status.textContent = error.message;
    status.dataset.tone = "error";
  }
}

async function onSaveControls(event) {
  event.preventDefault();
  const status = $("controls-status");
  status.textContent = "Saving";
  status.dataset.tone = "";
  try {
    await api.patch("/api/host/settings", {
      room_locked: $("set-locked").checked,
      read_only: $("set-read-only").checked,
      slow_mode_seconds: Number($("set-slow-mode").value || 0),
      notice_text: $("set-notice").value.trim(),
    });
    status.textContent = "Saved.";
    await loadSummary();
  } catch (error) {
    status.textContent = error.message;
    status.dataset.tone = "error";
  }
}

async function onSaveHost(event) {
  event.preventDefault();
  const status = $("host-status");
  status.textContent = "Saving";
  status.dataset.tone = "";
  try {
    const data = await api.post("/api/host/credentials", {
      current: $("host-current").value,
      host_user: $("host-user").value.trim(),
      new: $("host-new").value,
    });
    $("host-current").value = "";
    $("host-new").value = "";
    status.textContent = `Saved. Sign in as ${data.host_user}.`;
    await loadSummary();
  } catch (error) {
    status.textContent = error.message;
    status.dataset.tone = "error";
  }
}

async function onChangePassword(event) {
  event.preventDefault();
  const status = $("pw-status");
  status.textContent = "";
  status.dataset.tone = "";
  try {
    await api.post("/api/host/password", {
      current: $("pw-current").value,
      new: $("pw-new").value,
    });
    $("pw-current").value = "";
    $("pw-new").value = "";
    status.textContent = "Join password changed.";
  } catch (error) {
    status.textContent = error.message;
    status.dataset.tone = "error";
  }
}

async function loadPeople() {
  const body = $("people-body");
  try {
    const data = await api.get("/api/host/people");
    const roles = data.roles || [
      { id: "host", label: "Host" },
      { id: "moderator", label: "Moderator" },
      { id: "member", label: "Member" },
    ];
    $("people-count").textContent = `${data.people.filter((person) => person.online).length} here of ${data.people.length}`;
    if (!data.people.length) {
      body.innerHTML = '<tr><td colspan="5" class="empty-line">Nobody has joined yet.</td></tr>';
      return;
    }
    body.innerHTML = data.people
      .map(
        (person) => `<tr>
          <td><span class="table__name"><span class="status-dot" data-online="${person.online}"></span>${escapeText(person.name)}</span></td>
          <td>${person.online ? "Now" : "Away"}</td>
          <td class="table__muted">${escapeText((person.rooms || []).join(", ") || "Main room")}</td>
          <td>
            <select class="select" data-role-user="${person.id}" aria-label="Role for ${escapeText(person.name)}" style="min-height:32px;padding:4px 8px;font-size:12px">
              ${roles
                .map(
                  (role) =>
                    `<option value="${role.id}"${person.role === role.id ? " selected" : ""}>${escapeText(role.label)}</option>`
                )
                .join("")}
            </select>
          </td>
          <td class="table__actions">
            ${person.online ? `<button class="btn btn--sm" type="button" data-disconnect="${person.id}">End session</button>` : ""}
          </td>
        </tr>`
      )
      .join("");
    body.querySelectorAll("[data-role-user]").forEach((select) => {
      select.addEventListener("change", async () => {
        const person = data.people.find((entry) => entry.id === select.dataset.roleUser);
        select.disabled = true;
        try {
          await api.post(`/api/host/users/${select.dataset.roleUser}/role`, { role: select.value });
          toast(`${person ? person.name : "Person"} is now ${select.value}`);
        } catch (error) {
          toast(error.message, "error");
          loadPeople();
        } finally {
          select.disabled = false;
        }
      });
    });
    body.querySelectorAll("[data-disconnect]").forEach((button) => {
      button.addEventListener("click", () => {
        const person = data.people.find((entry) => entry.id === button.dataset.disconnect);
        askConfirm({
          title: `End ${person.name}'s session?`,
          body: "The browser loses its session and the person joins again with a name and the room password.",
          confirmLabel: "End session",
          onConfirm: async () => {
            try {
              await api.post(`/api/host/users/${person.id}/disconnect`);
              toast("Session ended");
              loadPeople();
            } catch (error) {
              toast(error.message, "error");
            }
          },
        });
      });
    });
  } catch (error) {
    body.innerHTML = `<tr><td colspan="5" class="empty-line">${escapeText(error.message)}</td></tr>`;
  }
}

function renderRooms() {
  const body = $("rooms-body");
  const rooms = summary.rooms || [];
  $("rooms-count").textContent = rooms.length === 1 ? "1 room" : `${rooms.length} rooms`;
  if (!rooms.length) {
    body.innerHTML = '<tr><td colspan="4" class="empty-line">No rooms yet.</td></tr>';
    return;
  }
  body.innerHTML = rooms
    .map(
      (room) => `<tr>
        <td><span class="table__name">${escapeText(room.name)} ${room.kind === "main" ? '<span class="pill">main</span>' : room.kind === "dm" ? '<span class="pill">direct</span>' : ""}</span></td>
        <td class="table__muted">${room.kind === "main" ? "open" : room.members}</td>
        <td class="table__muted">${room.messages === 1 ? "1 message" : `${room.messages} messages`}</td>
        <td class="table__actions"><button class="btn btn--sm btn--danger" type="button" data-clear="${room.id}">Clear</button></td>
      </tr>`
    )
    .join("");
  body.querySelectorAll("[data-clear]").forEach((button) => {
    button.addEventListener("click", () => {
      const room = rooms.find((entry) => entry.id === button.dataset.clear);
      askConfirm({
        title: `Clear ${room.name}?`,
        body: "Every message in this room is deleted for everyone. This cannot be undone.",
        confirmLabel: "Clear room",
        onConfirm: async () => {
          try {
            const data = await api.post(`/api/host/rooms/${room.id}/clear`, {});
            toast(`${data.removed} messages removed`);
            loadSummary();
          } catch (error) {
            toast(error.message, "error");
          }
        },
      });
    });
  });
}

async function loadLogs() {
  const list = $("logs");
  const level = $("log-level").value;
  list.innerHTML = '<div class="log-row"><span></span><span></span><span class="log-row__message">Loading</span></div>';
  try {
    const data = await api.get(`/api/host/logs?limit=200${level ? `&level=${level}` : ""}`);
    if (!data.records.length) {
      list.innerHTML = '<div class="empty-line">No log entries at this level.</div>';
      return;
    }
    list.innerHTML = data.records
      .slice()
      .reverse()
      .map(
        (record) => `<div class="log-row" data-level="${escapeText(record.level)}">
          <span class="log-row__time">${formatClock(record.ts)}</span>
          <span class="log-row__level">${escapeText(record.level)}</span>
          <span class="log-row__message">${escapeText(record.message)}</span>
        </div>`
      )
      .join("");
  } catch (error) {
    list.innerHTML = `<div class="empty-line">${escapeText(error.message)}</div>`;
  }
}

function renderLocalSend() {
  const manager = summary.localsend;
  const status = $("ls-status");
  status.textContent = manager.enabled
    ? manager.last_error || `${manager.alias} answers as ${manager.fingerprint.slice(0, 8)}.`
    : "LocalSend discovery is off.";
  const list = $("ls-devices");
  if (!manager.devices.length) {
    list.innerHTML = '<li class="empty-line">No devices seen yet. Open LocalSend on a phone, then scan.</li>';
    return;
  }
  list.innerHTML = manager.devices
    .map(
      (device) => `<li class="check" data-status="ok">
        <span class="check__icon"></span>
        <span>
          <span class="check__label">${escapeText(device.alias)}</span>
          <span class="check__detail">${escapeText(device.ip)} · ${escapeText(device.device_type || "device")} · seen ${device.last_seen_ago}s ago</span>
        </span>
      </li>`
    )
    .join("");
}

async function scanLocalSend() {
  const status = $("ls-status");
  status.textContent = "Scanning the network. This takes a moment.";
  try {
    const data = await api.post("/api/host/localsend/scan", {});
    status.textContent = `${data.devices.length} device(s) found.`;
    await loadSummary();
  } catch (error) {
    status.textContent = error.message;
  }
}

function onShutdown() {
  askConfirm({
    title: "Stop the server?",
    body: "Everyone loses the room until HostTalk starts again. Start it with python server.py or the desktop app.",
    confirmLabel: "Stop server",
    onConfirm: async () => {
      try {
        await api.post("/api/host/shutdown", {});
        toast("Stopping. This page stops working when the server closes.");
      } catch (error) {
        toast(error.message, "error");
      }
    },
  });
}

/* -------------------------------------------------------------------- helpers */
function askConfirm({ title, body, confirmLabel, onConfirm }) {
  $("console-confirm-title").textContent = title;
  $("console-confirm-body").textContent = body;
  $("console-confirm-action").textContent = confirmLabel;
  confirmHandler = onConfirm;
  openDialog("console-confirm");
}

function openDialog(id) {
  const dialog = $(id);
  if (dialog && !dialog.open) dialog.showModal();
}

function closeDialog(id) {
  const dialog = $(id);
  if (dialog && dialog.open) dialog.close();
}

function wireDialogs() {
  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.querySelectorAll("[data-close-dialog]").forEach((button) => {
      button.addEventListener("click", () => dialog.close());
    });
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  });
}

function showError(id, message) {
  const node = $(id);
  if (!node) return;
  node.textContent = message || "";
  node.dataset.visible = message ? "true" : "false";
}

function escapeText(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatClock(ts) {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function toast(message, tone = "default") {
  const stack = $("toasts");
  if (!stack) return;
  const node = document.createElement("div");
  node.className = "toast";
  node.dataset.tone = tone;
  node.textContent = message;
  stack.appendChild(node);
  setTimeout(() => node.remove(), 4000);
}
