import {
  api,
  applyTheme,
  avatarStyle,
  bootstrap,
  copyText,
  currentRoom,
  debounce,
  deviceKey,
  escapeHtml,
  formatSize,
  initials,
  rememberName,
  roomMessages,
  savedName,
  setSounds,
  setTheme,
  state,
} from "./core.js";
import {
  appendMessage,
  closeDialog,
  markHighlight,
  openDialog,
  paintInvite,
  removeMessageNode,
  renderColorGrid,
  renderConnection,
  renderHeader,
  renderMe,
  renderPeoplePanel,
  renderReactionPicker,
  renderRoomList,
  renderThread,
  renderTyping,
  setText,
  showFormError,
  toast,
  updateMessageNode,
  wireDialogs,
} from "./render.js";

const elements = {};
let eventSource = null;
let typingTimer = 0;
let activeTypingTimer = 0;
let confirmHandler = null;
let passwordHandler = null;
let pendingJoinCode = "";
let receivedAudio = null;

function byId(id) {
  return document.getElementById(id);
}

/* ---------------------------------------------------------------------- boot */
const bootStarted = performance.now();

/* Reveal the first screen quickly. The splash never covers a control for long. */
function hideBoot() {
  const boot = byId("boot");
  if (!boot || boot.hidden) return;
  const wait = Math.max(0, 260 - (performance.now() - bootStarted));
  setTimeout(() => {
    boot.hidden = true;
  }, wait);
}
document.addEventListener("DOMContentLoaded", () => {
  applyTheme(state.prefs.theme);
  wireDialogs();
  bind();
  syncSettingsControls();
  showLocalLinks();
  checkSession().finally(hideBoot);
});

function bind() {
  byId("join-form").addEventListener("submit", onJoinSubmit);
  byId("join-copy").addEventListener("click", () => copyAddress(state.bootstrap.address, "Address copied"));
  byId("join-name").value = savedName();

  byId("composer").addEventListener("submit", (event) => {
    event.preventDefault();
    sendText();
  });
  byId("composer-input").addEventListener("input", onComposerInput);
  byId("composer-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      sendText();
    }
    if (event.key === "Escape") cancelReply();
  });
  byId("reply-cancel").addEventListener("click", cancelReply);
  byId("attach-btn").addEventListener("click", () => byId("file-input").click());
  byId("file-input").addEventListener("change", onFileChosen);
  byId("gif-btn").addEventListener("click", openGifDialog);
  byId("gif-search-btn").addEventListener("click", searchGifs);
  byId("gif-query").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      searchGifs();
    }
  });

  byId("invite-btn").addEventListener("click", () => openInvite());
  byId("room-invite-btn").addEventListener("click", () => openInvite());
  byId("panel-invite").addEventListener("click", () => openInvite());
  byId("invite-copy").addEventListener("click", onInviteCopy);
  byId("panel-copy").addEventListener("click", () => copyAddress(state.bootstrap.address, "Address copied"));

  byId("settings-btn").addEventListener("click", openSettings);
  byId("settings-btn-2").addEventListener("click", openSettings);
  byId("settings-name-save").addEventListener("click", saveName);
  byId("settings-name").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      saveName();
    }
  });
  byId("settings-leave").addEventListener("click", leaveDevice);
  document.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      setTheme(button.dataset.themeChoice);
      syncSettingsControls();
    });
  });
  document.querySelectorAll("[data-sounds-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      setSounds(button.dataset.soundsChoice === "on");
      syncSettingsControls();
    });
  });

  byId("search-btn").addEventListener("click", openSearch);
  byId("search-input").addEventListener("input", debounce(runSearch, 320));
  byId("new-room-btn").addEventListener("click", () => {
    byId("new-room-error").dataset.visible = "false";
    openDialog("new-room-dialog");
    setTimeout(() => byId("new-room-name").focus(), 30);
  });
  byId("new-room-create").addEventListener("click", createRoom);
  byId("join-code-btn").addEventListener("click", () => joinCode(byId("join-code").value.trim()));

  byId("people-btn").addEventListener("click", togglePeople);
  byId("close-people").addEventListener("click", closeDrawers);
  byId("open-rail").addEventListener("click", toggleRail);
  byId("scrim").addEventListener("click", closeDrawers);
  byId("room-leave-btn").addEventListener("click", leaveRoom);
  byId("room-lock-btn").addEventListener("click", setRoomPassword);
  byId("lightbox-close").addEventListener("click", () => closeDialog("lightbox"));
  byId("confirm-action").addEventListener("click", () => {
    const handler = confirmHandler;
    confirmHandler = null;
    closeDialog("confirm-dialog");
    if (handler) handler();
  });
  byId("password-form").addEventListener("submit", onPasswordSubmit);

  document.addEventListener("click", onDocumentClick);
  document.addEventListener("keydown", onGlobalKey);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (state.prefs.theme === "auto") applyTheme("auto");
  });
  window.addEventListener("beforeunload", storeDraft);
}

/* --------------------------------------------------------------- session flow */
async function checkSession() {
  try {
    const data = await api.get("/api/me");
    if (data.user) enterApp(data);
    else showJoin();
  } catch (error) {
    showJoin();
  }
  refreshStatus();
}

async function refreshStatus() {
  try {
    const data = await api.get("/api/status");
    const server = data.server || {};
    state.bootstrap.setup_complete = server.setup_complete;
    state.bootstrap.requires_password = server.requires_password;
    state.bootstrap.address = server.address || state.bootstrap.address;
    state.bootstrap.online = server.online || 0;
    state.bootstrap.room_name = server.room_name || state.bootstrap.room_name;
    state.gifReady = Boolean(server.gifs_ready);
    if (!state.me) paintJoin();
  } catch (error) {
    /* The join screen still works without status details. */
  }
}

function showJoin() {
  byId("app-view").hidden = true;
  byId("join-view").hidden = false;
  paintJoin();
  hideBoot();
  const focusTarget = savedName() ? byId("join-password") : byId("join-name");
  setTimeout(() => focusTarget && focusTarget.focus(), 60);
}

function paintJoin() {
  const address = state.bootstrap.address || window.location.origin;
  setText("join-address", address);
  paintQrFallback(address);
  const count = Number(state.bootstrap.online || 0);
  setText("join-count", count);
  setText("join-count-label", count === 1 ? "person here" : count === 0 ? "nobody yet" : "people here");

  const requiresPassword = Boolean(state.bootstrap.requires_password);
  byId("password-field").hidden = !requiresPassword;
  byId("join-password").required = requiresPassword;
  byId("join-fineprint").textContent = requiresPassword
    ? "The room password is required to join."
    : "No password on this room yet. The host can add one in the console.";

  const setupNeeded = !state.bootstrap.setup_complete;
  byId("join-form").hidden = setupNeeded;
  byId("join-lede").hidden = setupNeeded;
  byId("join-setup").hidden = !(setupNeeded && state.bootstrap.local);
  if (setupNeeded && !state.bootstrap.local) {
    byId("join-lede").hidden = false;
    byId("join-lede").textContent = "This room has no password yet. Ask the host to finish setup on the machine that runs HostTalk.";
  }
  const code = new URLSearchParams(window.location.search).get("join");
  if (code) {
    byId("join-invite-note").hidden = false;
    byId("join-invite-note").textContent = "You were invited. Join, then the room opens for you.";
    pendingJoinCode = code;
  }
}

function paintQrFallback(address) {
  const target = byId("join-qr");
  if (target) target.dataset.ready = "false";
  if (!target || typeof globalThis.qrcode !== "function") return;
  try {
    const qr = globalThis.qrcode(0, "M");
    qr.addData(address);
    qr.make();
    target.innerHTML = qr.createSvgTag({ cellSize: 4, margin: 0, scalable: true });
    target.dataset.ready = "true";
  } catch (error) {
    target.dataset.ready = "false";
  }
}

async function onJoinSubmit(event) {
  event.preventDefault();
  const name = byId("join-name").value.trim();
  const password = byId("join-password").value;
  const button = byId("join-submit");
  showFormError("join-error", "");
  if (!name) {
    showFormError("join-error", "Enter a name first.");
    byId("join-name").focus();
    return;
  }
  button.disabled = true;
  button.textContent = "Joining";
  try {
    const data = await api.post("/api/session", {
      name,
      password,
      device_key: deviceKey(),
    });
    rememberName(data.user.name);
    enterApp(data);
    if (pendingJoinCode) {
      const code = pendingJoinCode;
      pendingJoinCode = "";
      await joinCode(code);
    }
  } catch (error) {
    const data = error.data || {};
    if (data.field === "name") {
      byId("name-field").classList.add("field--invalid");
      byId("join-name").focus();
    }
    if (data.field === "password" || error.status === 401) {
      byId("password-field").classList.add("field--invalid");
      byId("join-password").focus();
      byId("join-password").select();
    }
    showFormError("join-error", error.message || "Could not join. Try again.");
  } finally {
    button.disabled = false;
    button.textContent = "Join the room";
  }
}

function enterApp(data) {
  state.me = data.user;
  state.rooms = data.rooms || [];
  state.people = data.people || [];
  state.palette = data.palette || state.bootstrap.palette || [];
  state.reactions = data.reactions || [];
  state.gifReady = Boolean(data.server && data.server.gifs_ready);
  state.activeRoomId = state.activeRoomId || "main";
  if (!state.rooms.some((room) => room.id === state.activeRoomId)) {
    state.activeRoomId = state.rooms[0] ? state.rooms[0].id : "main";
  }
  byId("join-view").hidden = true;
  byId("app-view").hidden = false;
  hideBoot();
  showLocalLinks();
  renderMe();
  renderRoomList();
  renderPeoplePanel();
  renderHeader();
  connectEvents();
  loadRoom(state.activeRoomId, { initial: true });
  const composer = byId("composer-input");
  setTimeout(() => composer && composer.focus(), 120);
  const params = new URLSearchParams(window.location.search);
  if (params.get("join")) {
    params.delete("join");
    const query = params.toString();
    history.replaceState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
  }
}

function showLocalLinks() {
  document.querySelectorAll("[data-local-only]").forEach((node) => {
    node.hidden = !state.bootstrap.local;
  });
}

/* ------------------------------------------------------------------ realtime */
function connectEvents() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/api/events");
  eventSource.addEventListener("ready", (event) => {
    state.connected = true;
    renderConnection();
    const data = JSON.parse(event.data);
    if (data.people) {
      state.people = data.people;
      renderPeoplePanel();
      renderHeader();
      renderColorGrid();
    }
  });
  eventSource.addEventListener("message.created", (event) => {
    const data = JSON.parse(event.data);
    ingestMessage(data.message, { fromSelf: data.message.user_id === (state.me && state.me.id) });
  });
  eventSource.addEventListener("message.updated", (event) => {
    const data = JSON.parse(event.data);
    applyMessageUpdate(data.message);
  });
  eventSource.addEventListener("message.deleted", (event) => {
    const data = JSON.parse(event.data);
    applyMessageUpdate(data.message);
  });
  eventSource.addEventListener("message.reactions", (event) => {
    const data = JSON.parse(event.data);
    const message = findMessage(data.message_id);
    if (!message) return;
    message.reactions = data.reactions;
    updateMessageNode(message);
  });
  eventSource.addEventListener("typing", (event) => {
    const data = JSON.parse(event.data);
    if (data.room_id !== state.activeRoomId) return;
    state.typing.set(data.user_id, { name: data.name, at: Date.now() });
    renderTyping();
    clearTimeout(activeTypingTimer);
    activeTypingTimer = setTimeout(renderTyping, 3400);
  });
  eventSource.addEventListener("presence.changed", (event) => {
    const data = JSON.parse(event.data);
    if (Array.isArray(data.people)) {
      state.people = data.people;
      renderPeoplePanel();
      renderHeader();
      renderColorGrid();
      updateTitle();
    }
  });
  eventSource.addEventListener("user.updated", (event) => {
    const data = JSON.parse(event.data);
    const person = state.people.find((entry) => entry.id === data.user_id);
    if (person && data.user) Object.assign(person, data.user);
    if (state.me && data.user_id === state.me.id && data.user) {
      state.me = { ...state.me, ...data.user };
      renderMe();
    }
    renderPeoplePanel();
    renderHeader();
  });
  eventSource.addEventListener("room.created", () => refreshRooms());
  eventSource.addEventListener("room.member_joined", () => refreshRooms());
  eventSource.addEventListener("room.member_left", () => refreshRooms());
  eventSource.addEventListener("room.updated", (event) => {
    const data = JSON.parse(event.data);
    if (data.room) {
      const room = state.rooms.find((entry) => entry.id === data.room.id);
      if (room) Object.assign(room, data.room);
      renderRoomList();
      renderHeader();
      if (data.room.id === state.activeRoomId) updateLockButton();
    }
  });
  eventSource.addEventListener("room.cleared", (event) => {
    const data = JSON.parse(event.data);
    state.messages.set(data.room_id, []);
    if (data.room_id === state.activeRoomId) renderThread();
  });
  eventSource.addEventListener("server.updated", (event) => {
    const data = JSON.parse(event.data);
    if (data.room_name) {
      state.bootstrap.room_name = data.room_name;
      const room = state.rooms.find((entry) => entry.id === "main");
      if (room) room.name = data.room_name;
      renderRoomList();
      renderHeader();
    }
    if (data.password_changed) toast("The room password changed on the host.");
  });
  eventSource.addEventListener("session.revoked", (event) => {
    const data = JSON.parse(event.data);
    toast(data.reason || "The host ended this session.", "error", 6000);
    eventSource.close();
    setTimeout(() => window.location.reload(), 1600);
  });
  eventSource.onerror = () => {
    state.connected = false;
    renderConnection();
  };
  eventSource.onopen = () => {
    state.connected = true;
    renderConnection();
  };
}

/* --------------------------------------------------------------- message state */
function ingestMessage(message, { fromSelf = false, sound = true } = {}) {
  const added = addMessage(message);
  if (message.room_id === state.activeRoomId) {
    if (added) appendMessage(message);
    else updateMessageNode(message);
    markRead(message.room_id);
  } else if (!fromSelf) {
    state.unread.set(message.room_id, (state.unread.get(message.room_id) || 0) + 1);
    renderRoomList();
    updateTitle();
  }
  const room = state.rooms.find((entry) => entry.id === message.room_id);
  if (room) room.last_seq = Math.max(room.last_seq || 0, message.seq);
  if (!fromSelf && sound && state.prefs.sounds) playReceived();
}

function addMessage(message) {
  const list = state.messages.get(message.room_id) || [];
  if (list.some((entry) => entry.id === message.id)) return false;
  list.push(message);
  list.sort((a, b) => a.seq - b.seq);
  state.messages.set(message.room_id, list);
  return true;
}

function applyMessageUpdate(message) {
  const list = state.messages.get(message.room_id) || [];
  const index = list.findIndex((entry) => entry.id === message.id);
  if (index >= 0) list[index] = { ...list[index], ...message };
  if (message.room_id === state.activeRoomId) updateMessageNode(message);
}

function findMessage(id) {
  for (const list of state.messages.values()) {
    const found = list.find((entry) => entry.id === id);
    if (found) return found;
  }
  return null;
}

function markRead(roomId) {
  state.unread.delete(roomId);
  const list = state.messages.get(roomId) || [];
  if (list.length) {
    const seen = JSON.parse(localStorage.getItem("hosttalk.seen") || "{}");
    seen[roomId] = list[list.length - 1].seq;
    localStorage.setItem("hosttalk.seen", JSON.stringify(seen));
  }
  renderRoomList();
  updateTitle();
}

function updateTitle() {
  const room = currentRoom();
  const unread = [...state.unread.values()].reduce((sum, value) => sum + value, 0);
  const name = room ? room.name : state.bootstrap.room_name || "HostTalk";
  document.title = `${unread ? `(${unread}) ` : ""}${name} · HostTalk`;
}

/* -------------------------------------------------------------------- rooms */
async function loadRoom(roomId, { initial = false, keepScroll = false } = {}) {
  const room = state.rooms.find((entry) => entry.id === roomId);
  if (!room) return;
  const unlocked = await ensureRoomAccess(room);
  if (!unlocked) return;
  state.activeRoomId = roomId;
  state.replyTo = null;
  paintReply();
  renderHeader();
  renderRoomList();
  updateLockButton();
  closeDrawers();
  const input = byId("composer-input");
  if (input) {
    input.value = state.drafts.get(roomId) || "";
    autoGrow(input);
  }
  const cached = state.messages.get(roomId);
  if (!cached || initial) {
    showThreadSkeleton();
    try {
      const data = await api.get(`/api/rooms/${roomId}/messages?limit=50`);
      state.messages.set(roomId, data.messages || []);
      state.hasMore.set(roomId, Boolean(data.has_more));
      if (data.room) Object.assign(room, data.room);
    } catch (error) {
      toast(error.message, "error");
      state.messages.set(roomId, []);
    }
  }
  renderThread({ stick: !keepScroll });
  markRead(roomId);
  updateTitle();
  if (room.kind !== "main") await loadMembers(room.id);
  else renderPeoplePanel();
  renderHeader();
  if (!initial) {
    const composer = byId("composer-input");
    if (composer && window.innerWidth > 860) composer.focus();
  }
}

async function loadMembers(roomId) {
  try {
    const data = await api.get(`/api/rooms/${roomId}/members`);
    state.members.set(roomId, data.members || []);
    renderHeader();
  } catch (error) {
    /* Members are informative; the thread still works. */
  }
}

async function ensureRoomAccess(room) {
  if (room.kind !== "dm" || !room.has_password || state.unlocked.has(room.id)) return true;
  return new Promise((resolve) => {
    askPassword({
      title: "This conversation is locked",
      sub: "Enter the password a member set for this direct message.",
      submit: "Unlock",
      onSubmit: async (value) => {
        await api.post(`/api/rooms/${room.id}/verify`, { password: value });
        state.unlocked.add(room.id);
        resolve(true);
        return true;
      },
      onCancel: () => resolve(false),
    });
  });
}

async function refreshRooms() {
  try {
    const data = await api.get("/api/rooms");
    state.rooms = data.rooms || [];
    if (!state.rooms.some((room) => room.id === state.activeRoomId)) {
      state.activeRoomId = state.rooms.length ? state.rooms[0].id : "main";
    }
    renderRoomList();
    renderHeader();
    updateLockButton();
  } catch (error) {
    /* Keep the current list. */
  }
}

function switchRoom(roomId) {
  if (roomId === state.activeRoomId) {
    closeDrawers();
    return;
  }
  loadRoom(roomId);
}

async function createRoom() {
  const name = byId("new-room-name").value.trim();
  const button = byId("new-room-create");
  showFormError("new-room-error", "");
  if (!name) {
    showFormError("new-room-error", "Give the room a name.");
    return;
  }
  button.disabled = true;
  try {
    const data = await api.post("/api/rooms", { name });
    state.rooms.push(data.room);
    state.messages.set(data.room.id, []);
    byId("new-room-name").value = "";
    closeDialog("new-room-dialog");
    renderRoomList();
    await loadRoom(data.room.id);
    toast(`Room created: ${data.room.name}`);
  } catch (error) {
    showFormError("new-room-error", error.message);
  } finally {
    button.disabled = false;
  }
}

async function joinCode(code) {
  if (!code) {
    showFormError("join-code-error", "Paste the code from the invite link.");
    return;
  }
  const clean = code.includes("join=") ? code.split("join=")[1].split("&")[0] : code;
  try {
    const data = await api.post("/api/rooms/join", { code: clean });
    upsertRoom(data.room);
    if (data.messages) state.messages.set(data.room.id, data.messages);
    closeDialog("new-room-dialog");
    renderRoomList();
    await loadRoom(data.room.id, { initial: false });
    toast(`Joined ${data.room.name}`);
    return true;
  } catch (error) {
    if (error.status === 401 && (error.data || {}).password_required) {
      askPassword({
        title: "Room password",
        sub: "This room asks for a password before it opens.",
        submit: "Join room",
        onSubmit: async (value) => {
          const data = await api.post("/api/rooms/join", { code: clean, password: value });
          upsertRoom(data.room);
          if (data.messages) state.messages.set(data.room.id, data.messages);
          closeDialog("new-room-dialog");
          renderRoomList();
          await loadRoom(data.room.id);
          toast(`Joined ${data.room.name}`);
          return true;
        },
      });
      return false;
    }
    const target = document.getElementById("join-code-error");
    if (target) showFormError("join-code-error", error.message);
    else toast(error.message, "error");
    return false;
  }
}

function upsertRoom(room) {
  if (!room) return;
  const existing = state.rooms.find((entry) => entry.id === room.id);
  if (existing) Object.assign(existing, room);
  else state.rooms.push(room);
}

async function openDirectMessage(userId) {
  if (!userId || (state.me && userId === state.me.id)) return;
  try {
    const data = await api.post("/api/dm", { user_id: userId });
    upsertRoom(data.room);
    if (data.messages) state.messages.set(data.room.id, data.messages);
    renderRoomList();
    await loadRoom(data.room.id);
  } catch (error) {
    if (error.status === 401 && (error.data || {}).password_required) {
      askPassword({
        title: "This conversation is locked",
        sub: "Enter the password a member set for this direct message.",
        submit: "Unlock",
        onSubmit: async (value) => {
          const data = await api.post("/api/dm", { user_id: userId, password: value });
          upsertRoom(data.room);
          state.unlocked.add(data.room.id);
          if (data.messages) state.messages.set(data.room.id, data.messages);
          renderRoomList();
          await loadRoom(data.room.id);
          return true;
        },
      });
      return;
    }
    toast(error.message, "error");
  }
}

function leaveRoom() {
  const room = currentRoom();
  if (!room || room.kind === "main") return;
  askConfirm({
    title: `Leave ${room.name}?`,
    body: "The messages stay on the host machine. You can join again with a new invite link.",
    confirmLabel: "Leave room",
    onConfirm: async () => {
      try {
        await api.post(`/api/rooms/${room.id}/leave`);
        state.rooms = state.rooms.filter((entry) => entry.id !== room.id);
        state.messages.delete(room.id);
        state.members.delete(room.id);
        renderRoomList();
        await loadRoom("main");
        toast(`Left ${room.name}`);
      } catch (error) {
        toast(error.message, "error");
      }
    },
  });
}

function updateLockButton() {
  const room = currentRoom();
  const button = byId("room-lock-btn");
  if (!button) return;
  button.hidden = !room || room.kind === "main";
  if (room) button.setAttribute("aria-pressed", String(Boolean(room.has_password)));
}

function setRoomPassword() {
  const room = currentRoom();
  if (!room || room.kind === "main") return;
  askPassword({
    title: room.has_password ? "Change the room password" : "Lock this room",
    sub: "People need this password to open the invite link.",
    submit: "Save password",
    allowEmpty: true,
    hint: "Leave empty to remove the password.",
    onSubmit: async (value) => {
      const data = await api.post(`/api/rooms/${room.id}/password`, { password: value });
      room.has_password = data.has_password;
      updateLockButton();
      renderRoomList();
      toast(data.has_password ? "Room locked" : "Room password removed");
      return true;
    },
  });
}

/* --------------------------------------------------------------------- replies */
function startReply(messageId) {
  const message = findMessage(messageId);
  if (!message) return;
  state.replyTo = message;
  paintReply();
  const input = byId("composer-input");
  input.focus();
}

function paintReply() {
  const box = byId("reply-preview");
  if (!box) return;
  if (!state.replyTo) {
    box.dataset.visible = "false";
    return;
  }
  box.dataset.visible = "true";
  setText("reply-name", state.replyTo.name);
  setText("reply-body", state.replyTo.body || "Attachment");
}

function cancelReply() {
  state.replyTo = null;
  paintReply();
}

/* -------------------------------------------------------------------- sending */
function tempMessage(body, kind = "text", attachment = null) {
  const list = roomMessages();
  const last = list.length ? list[list.length - 1].seq : 0;
  return {
    id: `temp-${crypto.randomUUID ? crypto.randomUUID() : Date.now()}`,
    seq: last + 0.5,
    room_id: state.activeRoomId,
    user_id: state.me.id,
    name: state.me.name,
    color: state.me.color,
    kind,
    body,
    attachment,
    quote: state.replyTo
      ? { id: state.replyTo.id, name: state.replyTo.name, body: state.replyTo.body }
      : null,
    reactions: {},
    created_at: Date.now() / 1000,
    edited_at: null,
    deleted_at: null,
    pending: true,
  };
}

async function sendText() {
  const input = byId("composer-input");
  const text = input.value.trim();
  if (!text) return;
  const room = currentRoom();
  if (!room) return;
  if (text.length > 4000) {
    toast("Messages limit is 4000 characters", "error");
    return;
  }
  await deliver({ body: text, kind: "text", input });
}

async function deliver({ body, kind, attachment = null, input = null }) {
  const room = currentRoom();
  if (!room) return;
  const payload = { room_id: room.id, body, kind };
  if (attachment) payload.attachment_id = attachment.id;
  if (state.replyTo) payload.quote_id = state.replyTo.id;
  const draftStore = input ? input.value : "";
  if (input) {
    input.value = "";
    autoGrow(input);
    state.drafts.delete(room.id);
  }
  cancelReply();
  const temp = tempMessage(body, kind, attachment);
  addMessage(temp);
  if (room.id === state.activeRoomId) appendMessage(temp);
  try {
    const data = await api.post("/api/messages", payload);
    removeMessageNode(temp.id);
    state.messages.set(room.id, (state.messages.get(room.id) || []).filter((entry) => entry.id !== temp.id));
    const added = addMessage(data.message);
    if (data.message.room_id === state.activeRoomId) {
      if (added) appendMessage(data.message);
      else updateMessageNode(data.message);
    }
    markRead(room.id);
  } catch (error) {
    removeMessageNode(temp.id);
    state.messages.set(room.id, (state.messages.get(room.id) || []).filter((entry) => entry.id !== temp.id));
    if (input) {
      input.value = draftStore;
      autoGrow(input);
      input.focus();
    }
    toast(error.message, "error");
  }
}

const signalTyping = throttle(() => {
  api.post("/api/typing", { room_id: state.activeRoomId }).catch(() => {});
}, 2200);

function onComposerInput(event) {
  const input = event.target;
  autoGrow(input);
  storeDraft();
  signalTyping();
  const remaining = 4000 - input.value.length;
  const size = byId("composer-size");
  if (size) {
    size.dataset.warn = String(remaining < 200);
    size.textContent =
      remaining < 200
        ? `${remaining} characters left`
        : "Enter sends. Shift and Enter adds a line.";
  }
}

function storeDraft() {
  const input = byId("composer-input");
  if (!input) return;
  if (input.value) state.drafts.set(state.activeRoomId, input.value);
  else state.drafts.delete(state.activeRoomId);
}

function autoGrow(input) {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 168)}px`;
}

/* -------------------------------------------------------------------- uploads */
async function onFileChosen(event) {
  const file = event.target.files && event.target.files[0];
  event.target.value = "";
  if (file) await uploadAndSend(file);
}

async function uploadAndSend(file) {
  const limit = Number(state.bootstrap.max_upload_mb || 20) * 1024 * 1024;
  let upload = file;
  let name = file.name;
  let mime = file.type || "application/octet-stream";
  try {
    if (file.size > limit) {
      if (file.type.startsWith("image/")) {
        toast("Image is over the limit. Compressing it.");
        upload = await compressImage(file, limit);
        if (!upload) throw new Error("That image is too large for this room");
        name = upload.name || `${file.name.replace(/\.[^.]+$/, "")}.jpg`;
        mime = upload.type;
      } else {
        toast("File is over the limit. Compressing it.");
        upload = await gzipFile(file);
        if (!upload) throw new Error("That file is too large for this room");
        name = upload.name;
        mime = upload.type;
      }
      if (upload.size > limit) throw new Error("That file is still too large for this room");
    }
    toast(`Uploading ${name}`);
    const form = new FormData();
    form.append("file", upload, name);
    const data = await api.post("/api/uploads", form);
    const attachment = data.attachment;
    const kind = mime.startsWith("image/") ? "image" : "file";
    await deliver({ body: name, kind, attachment });
  } catch (error) {
    toast(error.message || "Upload failed", "error", 5000);
  }
}

function compressImage(file, limit) {
  return new Promise((resolve) => {
    const qualities = [0.86, 0.74, 0.6, 0.45, 0.32];
    let index = 0;
    const attempt = () => {
      if (typeof globalThis.Compressor !== "function" || index >= qualities.length) {
        resolve(null);
        return;
      }
      const quality = qualities[index++];
      new globalThis.Compressor(file, {
        quality,
        maxWidth: 2000,
        maxHeight: 2000,
        mimeType: "image/jpeg",
        success: (result) => {
          if (result.size <= limit) resolve(result);
          else attempt();
        },
        error: () => resolve(null),
      });
    };
    attempt();
  });
}

async function gzipFile(file) {
  const data = new Uint8Array(await file.arrayBuffer());
  const gzipped = globalThis.fflate.gzipSync(data, { level: 6 });
  return new File([gzipped], `${file.name}.gz`, { type: "application/gzip" });
}

/* ------------------------------------------------------------------------ GIFs */
function openGifDialog() {
  const errorNode = byId("gif-error");
  errorNode.dataset.visible = "false";
  byId("gif-grid").innerHTML = "";
  if (!state.gifReady) {
    byId("gif-sub").textContent = "GIF search is off. The host adds a GIPHY key in the host console.";
    byId("gif-search-btn").disabled = true;
  } else {
    byId("gif-sub").textContent = "Search GIPHY. Results come through this server.";
    byId("gif-search-btn").disabled = false;
  }
  openDialog("gif-dialog");
  if (state.gifReady) searchGifs("");
}

async function searchGifs(queryOverride) {
  if (!state.gifReady) return;
  const query = typeof queryOverride === "string" ? queryOverride : byId("gif-query").value.trim();
  const grid = byId("gif-grid");
  showFormError("gif-error", "");
  grid.setAttribute("aria-busy", "true");
  grid.innerHTML = '<div class="skeleton" style="height:90px"></div><div class="skeleton" style="height:90px"></div><div class="skeleton" style="height:90px"></div>';
  try {
    const data = await api.get(`/api/gifs?q=${encodeURIComponent(query)}`);
    grid.removeAttribute("aria-busy");
    if (!data.gifs.length) {
      grid.innerHTML = '<p class="fineprint">Nothing came back for that search.</p>';
      return;
    }
    grid.innerHTML = data.gifs
      .map(
        (gif) =>
          `<button type="button" data-action="send-gif" data-url="${escapeHtml(gif.url)}" aria-label="${escapeHtml(gif.title)}"><img src="${escapeHtml(gif.preview)}" alt="${escapeHtml(gif.title)}" loading="lazy" referrerpolicy="no-referrer"></button>`
      )
      .join("");
  } catch (error) {
    grid.removeAttribute("aria-busy");
    grid.innerHTML = "";
    showFormError("gif-error", error.message);
  }
}

/* --------------------------------------------------------------------- invites */
async function openInvite(message) {
  const room = currentRoom();
  let address = state.bootstrap.address || window.location.origin;
  let link = "";
  try {
    if (room && room.kind !== "main") {
      const data = await api.post(`/api/rooms/${room.id}/invite`, {});
      address = data.network.address;
      link = data.url;
    } else {
      const data = await api.get("/api/invite");
      address = data.network.address;
    }
  } catch (error) {
    toast(error.message, "error");
    return;
  }
  paintInvite({
    address,
    link,
    note: state.bootstrap.requires_password
      ? "The room password is required."
      : "No password on this room yet.",
  });
  const copy = byId("invite-copy");
  copy.textContent = link ? "Copy invite link" : "Copy address";
  copy.dataset.value = link || address;
  openDialog("invite-dialog");
}

async function onInviteCopy() {
  const button = byId("invite-copy");
  const copied = await copyText(button.dataset.value || state.bootstrap.address);
  toast(copied ? "Copied" : "Copy failed. Select the address by hand.");
}

async function copyAddress(address, label) {
  const copied = await copyText(address || "");
  toast(copied ? label : "Copy failed. Select the address by hand.");
}

/* -------------------------------------------------------------------- settings */
function openSettings() {
  if (!state.me) return;
  syncSettingsControls();
  renderMe();
  showFormError("settings-name-error", "");
  showFormError("settings-color-error", "");
  openDialog("settings-dialog");
}

function syncSettingsControls() {
  document.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.themeChoice === state.prefs.theme));
  });
  document.querySelectorAll("[data-sounds-choice]").forEach((button) => {
    button.setAttribute(
      "aria-pressed",
      String((button.dataset.soundsChoice === "on") === Boolean(state.prefs.sounds))
    );
  });
}

async function saveName() {
  const value = byId("settings-name").value.trim();
  if (!value || !state.me) return;
  showFormError("settings-name-error", "");
  try {
    const data = await api.patch("/api/me", { name: value });
    state.me = data.user;
    rememberName(state.me.name);
    renderMe();
    renderPeoplePanel();
    renderHeader();
    toast("Name saved");
  } catch (error) {
    const wait = error.data && error.data.retry_after;
    const message =
      error.status === 429 && wait
        ? `${error.message} (${Math.ceil(wait / 60)} minutes)`
        : error.message;
    showFormError("settings-name-error", message);
  }
}

async function pickColor(color) {
  if (!state.me || !color) return;
  showFormError("settings-color-error", "");
  try {
    const data = await api.patch("/api/me", { color });
    state.me = data.user;
    renderMe();
    renderPeoplePanel();
    renderHeader();
    toast("Color updated");
  } catch (error) {
    showFormError("settings-color-error", error.message);
  }
}

function leaveDevice() {
  askConfirm({
    title: "Leave this device?",
    body: "The name and color stay on the server. You join again with a name and the room password.",
    confirmLabel: "Leave",
    onConfirm: async () => {
      try {
        await api.delete("/api/session");
      } catch (error) {
        /* Leaving is local. */
      }
      window.location.reload();
    },
  });
}

/* ---------------------------------------------------------------------- search */
function openSearch() {
  if (!state.me) return;
  byId("search-input").value = "";
  byId("search-results").innerHTML = "";
  showFormError("search-error", "");
  openDialog("search-dialog");
  setTimeout(() => byId("search-input").focus(), 40);
}

async function runSearch() {
  const query = byId("search-input").value.trim();
  const results = byId("search-results");
  if (query.length < 2) {
    results.innerHTML = "";
    return;
  }
  results.innerHTML = '<div class="skeleton" style="height:52px"></div>';
  try {
    const data = await api.get(`/api/search?q=${encodeURIComponent(query)}`);
    if (!data.results.length) {
      results.innerHTML = `<p class="fineprint">No messages match “${escapeHtml(query)}”.</p>`;
      return;
    }
    results.innerHTML = data.results
      .map(
        (message) => `<button class="search-result" type="button" data-action="jump" data-room="${message.room_id}" data-id="${message.id}" data-seq="${message.seq}">
          <span class="search-result__meta">${escapeHtml(message.room_name || "")} · ${escapeHtml(message.name)}</span>
          <span class="search-result__body">${escapeHtml(message.body)}</span>
        </button>`
      )
      .join("");
  } catch (error) {
    results.innerHTML = "";
    showFormError("search-error", error.message);
  }
}

async function jumpToResult(roomId, messageId, seq) {
  closeDialog("search-dialog");
  if (roomId !== state.activeRoomId) await loadRoom(roomId);
  await new Promise((resolve) => setTimeout(resolve, 30));
  if (markHighlight(messageId)) return;
  try {
    const data = await api.get(`/api/rooms/${roomId}/messages?before=${Number(seq) + 1}&limit=50`);
    for (const message of data.messages || []) addMessage(message);
    renderThread({ stick: false });
    setTimeout(() => {
      if (!markHighlight(messageId)) toast("That message is further back in the room.", "error");
    }, 60);
  } catch (error) {
    toast(error.message, "error");
  }
}

/* --------------------------------------------------------------- confirmation */
function askConfirm({ title, body, confirmLabel = "Continue", onConfirm }) {
  setText("confirm-title", title);
  setText("confirm-body", body);
  setText("confirm-sub", "");
  const action = byId("confirm-action");
  action.textContent = confirmLabel;
  confirmHandler = onConfirm;
  openDialog("confirm-dialog");
}

function askPassword({ title, sub, submit = "Continue", hint = "", allowEmpty = false, onSubmit, onCancel }) {
  setText("password-title", title);
  setText("password-sub", sub || "");
  setText("password-hint", hint || (allowEmpty ? "Leave empty to remove the password." : ""));
  byId("password-submit").textContent = submit;
  byId("password-input").value = "";
  showFormError("password-error", "");
  passwordHandler = { onSubmit, allowEmpty, onCancel };
  openDialog("password-dialog");
  setTimeout(() => byId("password-input").focus(), 40);
  byId("password-dialog").addEventListener(
    "close",
    () => {
      if (passwordHandler && passwordHandler.onCancel) passwordHandler.onCancel();
      passwordHandler = null;
    },
    { once: true }
  );
}

async function onPasswordSubmit(event) {
  event.preventDefault();
  if (!passwordHandler) return;
  const value = byId("password-input").value;
  if (!value && !passwordHandler.allowEmpty) {
    showFormError("password-error", "Enter the password.");
    return;
  }
  const submit = byId("password-submit");
  submit.disabled = true;
  showFormError("password-error", "");
  try {
    const result = await passwordHandler.onSubmit(value);
    passwordHandler = null;
    submit.disabled = false;
    closeDialog("password-dialog");
    return result;
  } catch (error) {
    submit.disabled = false;
    showFormError("password-error", error.message);
  }
}

/* -------------------------------------------------------------------- editing */
function startEdit(messageId) {
  const message = findMessage(messageId);
  const row = document.getElementById(`msg-${messageId}`);
  if (!message || !row || row.querySelector(".msg-editor")) return;
  const body = row.querySelector(".msg__body");
  const editor = document.createElement("form");
  editor.className = "msg-editor";
  editor.innerHTML = `
    <textarea class="textarea" rows="3" aria-label="Edit message">${escapeHtml(message.body)}</textarea>
    <div style="display:flex;gap:8px;margin-top:6px">
      <button class="btn btn--sm btn--primary" type="submit">Save</button>
      <button class="btn btn--sm" type="button" data-cancel>Cancel</button>
    </div>`;
  body.replaceWith(editor);
  editor.querySelector("textarea").focus();
  editor.querySelector("[data-cancel]").addEventListener("click", () => renderThread({ stick: false }));
  editor.addEventListener("submit", async (event) => {
    event.preventDefault();
    const value = editor.querySelector("textarea").value.trim();
    if (!value) return;
    try {
      const data = await api.patch(`/api/messages/${messageId}`, { body: value });
      applyMessageUpdate(data.message);
    } catch (error) {
      toast(error.message, "error");
    }
  });
}

function deleteMessage(messageId) {
  askConfirm({
    title: "Delete this message?",
    body: "The text disappears for everyone. The room keeps a quiet placeholder in its place.",
    confirmLabel: "Delete message",
    onConfirm: async () => {
      try {
        const data = await api.delete(`/api/messages/${messageId}`);
        applyMessageUpdate(data.message);
      } catch (error) {
        toast(error.message, "error");
      }
    },
  });
}

async function toggleReaction(messageId, emoji) {
  document.querySelectorAll(".reaction-picker").forEach((node) => node.remove());
  try {
    const data = await api.post(`/api/messages/${messageId}/reactions`, { emoji });
    const message = findMessage(messageId);
    if (message) {
      message.reactions = data.reactions;
      updateMessageNode(message);
    }
  } catch (error) {
    toast(error.message, "error");
  }
}

function openLightbox(url) {
  const image = byId("lightbox-img");
  image.src = url;
  image.alt = "Shared image";
  openDialog("lightbox");
}

/* --------------------------------------------------------------------- events */
function onDocumentClick(event) {
  const target = event.target.closest("[data-action]");
  if (!target) {
    document.querySelectorAll(".reaction-picker").forEach((node) => node.remove());
    return;
  }
  const action = target.dataset.action;
  if (action === "switch-room") switchRoom(target.dataset.room);
  else if (action === "open-dm") openDirectMessage(target.dataset.user);
  else if (action === "reply") startReply(target.dataset.id);
  else if (action === "react") renderReactionPicker(target);
  else if (action === "react-one") toggleReaction(target.dataset.id, target.dataset.emoji);
  else if (action === "edit") startEdit(target.dataset.id);
  else if (action === "delete") deleteMessage(target.dataset.id);
  else if (action === "lightbox") openLightbox(target.dataset.url);
  else if (action === "jump") jumpToResult(target.dataset.room, target.dataset.id, target.dataset.seq);
  else if (action === "load-older") loadOlder();
  else if (action === "pick-color") pickColor(target.dataset.color);
  else if (action === "send-gif") {
    closeDialog("gif-dialog");
    deliver({ body: target.dataset.url, kind: "gif" });
  }
}

async function loadOlder() {
  const roomId = state.activeRoomId;
  const list = state.messages.get(roomId) || [];
  if (!list.length) return;
  const before = list[0].seq;
  try {
    const data = await api.get(`/api/rooms/${roomId}/messages?before=${before}&limit=50`);
    if (!data.messages.length) {
      state.hasMore.set(roomId, false);
      renderThread({ stick: false });
      return;
    }
    state.messages.set(roomId, [...data.messages, ...list]);
    state.hasMore.set(roomId, Boolean(data.has_more));
    const scroller = byId("messages");
    const height = scroller.scrollHeight;
    renderThread({ stick: false });
    scroller.scrollTop = scroller.scrollHeight - height;
  } catch (error) {
    toast(error.message, "error");
  }
}

function onGlobalKey(event) {
  const meta = event.metaKey || event.ctrlKey;
  if (meta && event.key.toLowerCase() === "k") {
    event.preventDefault();
    openSearch();
  }
  if (event.key === "Escape") {
    if (state.replyTo) {
      cancelReply();
      return;
    }
    closeDrawers();
  }
}

/* -------------------------------------------------------------------- drawers */
function togglePeople() {
  const panel = byId("people-panel");
  const open = panel.dataset.open !== "true";
  panel.dataset.open = String(open);
  byId("people-btn").setAttribute("aria-pressed", String(open));
  byId("scrim").dataset.visible = String(open);
  if (open) closeRailOnly();
}

function toggleRail() {
  const rail = byId("rail");
  const open = rail.dataset.open !== "true";
  closePeopleOnly();
  rail.dataset.open = String(open);
  byId("open-rail").setAttribute("aria-expanded", String(open));
  byId("scrim").dataset.visible = String(open);
}

function closeRailOnly() {
  byId("rail").dataset.open = "false";
  byId("open-rail").setAttribute("aria-expanded", "false");
}

function closePeopleOnly() {
  byId("people-panel").dataset.open = "false";
  byId("people-btn").setAttribute("aria-pressed", "false");
}

function closeDrawers() {
  closeRailOnly();
  closePeopleOnly();
  byId("scrim").dataset.visible = "false";
}

/* --------------------------------------------------------------------- helpers */
function showThreadSkeleton() {
  const inner = byId("messages-inner");
  if (!inner) return;
  inner.innerHTML = `
    <div style="display:grid;gap:16px;padding:16px 4px" aria-hidden="true">
      <div class="skeleton" style="height:44px;width:72%"></div>
      <div class="skeleton" style="height:44px;width:56%"></div>
      <div class="skeleton" style="height:44px;width:64%"></div>
    </div>`;
}

function playReceived() {
  try {
    if (!receivedAudio) {
      receivedAudio = new Audio("/static/recieved.mp3");
      receivedAudio.volume = 0.28;
    }
    receivedAudio.currentTime = 0;
    receivedAudio.play().catch(() => {});
  } catch (error) {
    /* Audio is optional. */
  }
}

function throttle(fn, wait) {
  let last = 0;
  return (...args) => {
    const now = Date.now();
    if (now - last < wait) return;
    last = now;
    fn(...args);
  };
}

