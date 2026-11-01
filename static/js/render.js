import {
  api,
  avatarStyle,
  currentRoom,
  escapeHtml,
  extractUrls,
  formatDay,
  formatSize,
  formatTime,
  initials,
  linkify,
  qrSvg,
  roomMessages,
  state,
} from "./core.js";

const previewCache = new Map();
const MAX_PREVIEWS = 30;

/* --------------------------------------------------------------------- toasts */
export function toast(message, tone = "default", timeout = 3600) {
  const stack = document.getElementById("toasts");
  if (!stack) return;
  const node = document.createElement("div");
  node.className = "toast";
  node.dataset.tone = tone;
  node.setAttribute("role", tone === "error" ? "alert" : "status");
  node.textContent = message;
  stack.appendChild(node);
  setTimeout(() => {
    node.style.opacity = "0";
    node.style.transform = "translateY(4px)";
    setTimeout(() => node.remove(), 200);
  }, timeout);
}

/* -------------------------------------------------------------------- dialogs */
export function openDialog(id) {
  const dialog = document.getElementById(id);
  if (!dialog) return null;
  if (!dialog.open) dialog.showModal();
  return dialog;
}

export function closeDialog(id) {
  const dialog = document.getElementById(id);
  if (dialog && dialog.open) dialog.close();
}

export function wireDialogs() {
  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.querySelectorAll("[data-close-dialog]").forEach((button) => {
      button.addEventListener("click", () => dialog.close());
    });
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  });
}

export function setText(id, value) {
  const node = document.getElementById(id);
  if (!node) return;
  if ("value" in node && node.tagName === "INPUT") node.value = value;
  else node.textContent = value;
}

export function showFormError(id, message) {
  const node = document.getElementById(id);
  if (!node) return;
  node.textContent = message || "";
  node.dataset.visible = message ? "true" : "false";
}

/* -------------------------------------------------------------------- invites */
export function renderQr(targetId, text) {
  const node = document.getElementById(targetId);
  if (!node) return;
  const svg = qrSvg(text, 4);
  if (!svg) {
    node.dataset.ready = "false";
    return;
  }
  node.innerHTML = svg;
  node.dataset.ready = "true";
}

export function paintInvite({ address, roomName = "", note = "", link = "" }) {
  const safeAddress = address || state.bootstrap.address || window.location.origin;
  setText("invite-address", safeAddress);
  setText("invite-note", note || "The room password is required.");
  const open = document.getElementById("invite-open");
  if (open) open.href = link || safeAddress;
  const linkWrap = document.getElementById("invite-link-wrap");
  const linkNode = document.getElementById("invite-link");
  if (linkWrap && linkNode) {
    linkNode.textContent = link;
    linkWrap.hidden = !link;
  }
  renderQr("invite-qr", link || safeAddress);
}

/* ------------------------------------------------------------------ app chrome */
export function renderHeader() {
  const room = currentRoom();
  const title = document.getElementById("room-title");
  const threadTitle = document.getElementById("thread-title");
  const meta = document.getElementById("thread-meta");
  const roomMeta = document.getElementById("room-meta");
  const leave = document.getElementById("room-leave-btn");
  if (!room) return;
  if (title) title.textContent = room.name;
  if (threadTitle) threadTitle.textContent = room.name;
  const online = state.people.filter((person) => person.online).length;
  if (room.kind === "dm") {
    const other = roomMembers(room).filter((person) => person.id !== state.me.id);
    const label = other.length ? other[0].name : "Direct message";
    if (meta) meta.textContent = `${label} · ${online} here`;
    if (roomMeta) roomMeta.textContent = label;
  } else if (room.kind === "main") {
    if (meta) meta.textContent = `${online} here · messages stay on this machine`;
    if (roomMeta) roomMeta.textContent = `${online} here`;
  } else {
    if (meta) meta.textContent = `${room.members} of ${room.member_limit} joined · ${online} here`;
    if (roomMeta) roomMeta.textContent = `${room.members} joined`;
  }
  if (leave) leave.hidden = room.kind === "main";
  const inviteBtn = document.getElementById("room-invite-btn");
  if (inviteBtn) inviteBtn.hidden = false;
}

export function renderRoomList() {
  const list = document.getElementById("room-list");
  const dmList = document.getElementById("dm-list");
  const empty = document.getElementById("dm-empty");
  if (!list || !dmList) return;
  const groups = state.rooms.filter((room) => room.kind !== "dm");
  const dms = state.rooms.filter((room) => room.kind === "dm");
  list.innerHTML = groups
    .map((room) => {
      const unread = state.unread.get(room.id) || 0;
      const kind = room.kind === "main" ? "main" : "room";
      return `
        <li>
          <button class="rail__item" type="button" data-action="switch-room" data-room="${room.id}"
            ${room.id === state.activeRoomId ? 'aria-current="true"' : ""}>
            <svg class="icon icon--sm" aria-hidden="true"><use href="#${room.kind === "main" ? "i-hash" : "i-room"}"></use></svg>
            <span class="rail__item-name">${escapeHtml(room.name)}</span>
            ${room.has_password ? '<svg class="icon icon--sm" aria-label="Password required"><use href="#i-lock"></use></svg>' : ""}
            ${unread ? `<span class="rail__unread">${unread}</span>` : ""}
            <span class="visually-hidden">${kind}</span>
          </button>
        </li>`;
    })
    .join("");
  if (dms.length === 0) {
    dmList.innerHTML = "";
    if (empty) empty.hidden = false;
  } else {
    if (empty) empty.hidden = true;
    dmList.innerHTML = dms
      .map((room) => {
        const unread = state.unread.get(room.id) || 0;
        const others = roomMembers(room).filter((person) => person.id !== state.me.id);
        const other = others[0];
        const label = other ? other.name : room.name;
        return `
          <li>
            <button class="rail__item" type="button" data-action="switch-room" data-room="${room.id}"
              ${room.id === state.activeRoomId ? 'aria-current="true"' : ""}>
              <span class="dot" style="background:${other ? escapeHtml(other.color) : "var(--muted)"}"></span>
              <span class="rail__item-name">${escapeHtml(label)}</span>
              ${room.has_password ? '<svg class="icon icon--sm" aria-label="Password required"><use href="#i-lock"></use></svg>' : ""}
              ${unread ? `<span class="rail__unread">${unread}</span>` : ""}
            </button>
          </li>`;
      })
      .join("");
  }
}

export function renderMe() {
  if (!state.me) return;
  const avatar = document.getElementById("me-avatar");
  if (avatar) {
    avatar.textContent = initials(state.me.name);
    avatar.style.background = state.me.color;
  }
  setText("me-name", state.me.name);
  setText("me-color-label", "In the room");
  const nameInput = document.getElementById("settings-name");
  if (nameInput && document.activeElement !== nameInput) nameInput.value = state.me.name;
  const roomName = document.getElementById("settings-room-name");
  if (roomName) roomName.textContent = state.bootstrap.room_name;
  const meta = document.getElementById("settings-room-meta");
  if (meta) meta.textContent = `${state.people.filter((p) => p.online).length} here · ${state.rooms.length} rooms`;
  renderColorGrid();
}

export function renderColorGrid() {
  const grid = document.getElementById("settings-colors");
  if (!grid) return;
  const mine = state.me ? state.me.color.toUpperCase() : "";
  const taken = new Set(
    state.people.filter((person) => person.id !== (state.me && state.me.id)).map((person) => person.color.toUpperCase())
  );
  grid.innerHTML = state.palette
    .map((color) => {
      const used = taken.has(color.toUpperCase());
      return `<button class="color-swatch" type="button" data-action="pick-color" data-color="${color}"
        style="background:${color}" aria-label="Use color ${color}" aria-pressed="${color.toUpperCase() === mine}"
        ${used ? 'disabled aria-description="Used by someone in the room"' : ""}></button>`;
    })
    .join("");
}

export function renderPeoplePanel() {
  const list = document.getElementById("people-list");
  if (!list) return;
  const members = state.people.filter((person) => person.online);
  if (!members.length) {
    list.innerHTML = '<li class="empty"><span class="empty__title">The room is quiet</span><p>Send the invite link and someone shows up here.</p></li>';
    return;
  }
  list.innerHTML = members
    .map((person) => {
      const isMe = state.me && person.id === state.me.id;
      return `
        <li class="person">
          <span class="avatar avatar--lg" style="${avatarStyle(person.color)}" aria-hidden="true">${initials(person.name)}</span>
          <span class="person__meta">
            <span class="person__name">${escapeHtml(person.name)}${isMe ? ' <span class="msg__you">you</span>' : ""}</span>
            <span class="person__sub">${isMe ? "This device" : "In the room"}</span>
          </span>
          ${isMe ? "" : `<span class="person__action"><button class="icon-btn" type="button" data-action="open-dm" data-user="${person.id}" aria-label="Message ${escapeHtml(person.name)}"><svg class="icon" aria-hidden="true"><use href="#i-reply"></use></svg></button></span>`}
        </li>`;
    })
    .join("");
  const address = document.getElementById("panel-address");
  if (address) address.textContent = state.bootstrap.address || window.location.origin;
}

export function roomMembers(room) {
  if (!room) return [];
  if (room.kind === "main") return state.people;
  return (state.members && state.members.get(room.id)) || [];
}

/* -------------------------------------------------------------------- messages */
export function renderThread({ stick = true } = {}) {
  const inner = document.getElementById("messages-inner");
  const scroller = document.getElementById("messages");
  if (!inner) return;
  const previousHeight = scroller ? scroller.scrollHeight : 0;
  const wasNearBottom = scroller ? scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 80 : true;
  const messages = roomMessages();
  inner.innerHTML = "";
  if (state.hasMore.get(state.activeRoomId)) {
    const older = document.createElement("button");
    older.className = "btn btn--sm load-older";
    older.type = "button";
    older.dataset.action = "load-older";
    older.textContent = "Load older messages";
    inner.appendChild(older);
  }
  if (!messages.length) {
    inner.insertAdjacentHTML(
      "beforeend",
      `<div class="empty" style="padding:24px 8px">
        <span class="empty__title">No messages yet</span>
        <p>Say hello. Everything you write stays on the machine that runs this room.</p>
      </div>`
    );
    return;
  }
  let lastDay = "";
  let lastUser = "";
  let lastTime = 0;
  for (const message of messages) {
    const day = formatDay(message.created_at);
    if (day !== lastDay) {
      const divider = document.createElement("div");
      divider.className = "messages__day";
      divider.innerHTML = `<span>${escapeHtml(day)}</span>`;
      inner.appendChild(divider);
      lastDay = day;
      lastUser = "";
    }
    if (message.kind === "system") {
      const row = document.createElement("div");
      row.className = "system-row";
      row.innerHTML = `<span>${escapeHtml(message.body)}</span>`;
      inner.appendChild(row);
      lastUser = "";
      continue;
    }
    const continued =
      lastUser === message.user_id && message.created_at - lastTime < 300 && !message.quote;
    const node = messageRow(message, continued);
    inner.appendChild(node);
    lastUser = message.user_id;
    lastTime = message.created_at;
  }
  inner.insertAdjacentHTML("beforeend", '<div class="messages__end">No more messages</div>');
  if (scroller && stick) {
    if (wasNearBottom) scroller.scrollTop = scroller.scrollHeight;
    else scroller.scrollTop = scroller.scrollHeight - previousHeight + scroller.scrollTop;
  }
  ensurePreviews(messages.slice(-MAX_PREVIEWS));
}

function messageRow(message, continued) {
  const node = document.createElement("article");
  const mine = state.me && message.user_id === state.me.id;
  node.className = `msg${mine ? " msg--mine" : ""}${continued ? " msg--continued" : ""}${!continued ? " msg--group-start" : ""}${message.deleted_at ? " msg--deleted" : ""}`;
  node.id = `msg-${message.id}`;
  node.dataset.id = message.id;
  node.dataset.seq = message.seq;
  node.dataset.user = message.user_id;
  node.innerHTML = `
    <div class="msg__avatar" style="${avatarStyle(message.color)}" aria-hidden="true">${initials(message.name)}</div>
    <div class="msg__main">
      ${
        continued
          ? ""
          : `<div class="msg__head">
              <span class="msg__name">${escapeHtml(message.name)}</span>
              ${mine ? '<span class="msg__you">you</span>' : ""}
              <span class="msg__time">${formatTime(message.created_at)}</span>
              ${message.edited_at ? '<span class="msg__edited">edited</span>' : ""}
            </div>`
      }
      ${message.quote ? quoteBlock(message.quote) : ""}
      <div class="msg__body">${renderBody(message)}</div>
      <div class="msg__attachments">${attachmentBlock(message)}</div>
      <div class="reactions" data-role="reactions">${reactionButtons(message)}</div>
      <div class="msg__toolbar">
        ${message.deleted_at ? "" : `<button class="icon-btn" type="button" data-action="reply" data-id="${message.id}" aria-label="Reply to ${escapeHtml(message.name)}"><svg class="icon" aria-hidden="true"><use href="#i-reply"></use></svg></button>`}
        ${message.deleted_at ? "" : `<button class="icon-btn" type="button" data-action="react" data-id="${message.id}" aria-label="Add a reaction"><svg class="icon" aria-hidden="true"><use href="#i-smile"></use></svg></button>`}
        ${mine && !message.deleted_at ? `<button class="icon-btn" type="button" data-action="edit" data-id="${message.id}" aria-label="Edit message"><svg class="icon" aria-hidden="true"><use href="#i-sliders"></use></svg></button>` : ""}
        ${mine && !message.deleted_at ? `<button class="icon-btn" type="button" data-action="delete" data-id="${message.id}" aria-label="Delete message"><svg class="icon" aria-hidden="true"><use href="#i-trash"></use></svg></button>` : ""}
      </div>
    </div>`;
  return node;
}

function renderBody(message) {
  if (message.deleted_at) return "Message deleted";
  if (message.kind === "gif") {
    return `<a href="${escapeHtml(message.body)}" target="_blank" rel="noopener noreferrer" class="visually-hidden">Open GIF</a>`;
  }
  return linkify(message.body);
}

function quoteBlock(quote) {
  return `<div class="quote">
      <span class="quote__name">${escapeHtml(quote.name)}</span>
      <span class="quote__body">${escapeHtml(quote.body || "Attachment")}</span>
    </div>`;
}

function attachmentBlock(message) {
  const attachment = message.attachment;
  if (message.kind === "gif" && !message.deleted_at) {
    const url = escapeHtml(message.body);
    return `<button class="attachment-image" type="button" data-action="lightbox" data-url="${url}" aria-label="Open GIF">
        <img src="${url}" alt="GIF" loading="lazy" referrerpolicy="no-referrer">
      </button>`;
  }
  if (!attachment || message.deleted_at) return "";
  if (attachment.is_image) {
    return `<button class="attachment-image" type="button" data-action="lightbox" data-url="${escapeHtml(attachment.url)}" aria-label="Open ${escapeHtml(attachment.filename)}">
        <img src="${escapeHtml(attachment.url)}" alt="${escapeHtml(attachment.filename)}" loading="lazy">
      </button>`;
  }
  return `<a class="attachment-file" href="${escapeHtml(attachment.url)}" download="${escapeHtml(attachment.filename)}">
      <span class="attachment-file__icon"><svg class="icon" aria-hidden="true"><use href="#i-file"></use></svg></span>
      <span class="attachment-file__meta">
        <span class="attachment-file__name">${escapeHtml(attachment.filename)}</span>
        <span class="attachment-file__size">${formatSize(attachment.size)}</span>
      </span>
      <svg class="icon" aria-hidden="true" style="margin-left:auto"><use href="#i-download"></use></svg>
    </a>`;
}

function reactionButtons(message) {
  const entries = Object.entries(message.reactions || {});
  if (!entries.length) return "";
  return entries
    .map(([emoji, users]) => {
      const mine = state.me && users.includes(state.me.id);
      return `<button class="reaction" type="button" data-action="react-one" data-id="${message.id}" data-emoji="${emoji}" data-mine="${mine ? "true" : "false"}" aria-label="${emoji}, ${users.length} reactions">
        <span aria-hidden="true">${emoji}</span><span>${users.length}</span>
      </button>`;
    })
    .join("");
}

export function updateMessageNode(message) {
  const row = document.getElementById(`msg-${message.id}`);
  if (!row) return;
  const wasContinued = row.classList.contains("msg--continued");
  const replacement = messageRow(message, wasContinued);
  row.replaceWith(replacement);
}

export function removeMessageNode(id) {
  const row = document.getElementById(`msg-${id}`);
  if (row) row.remove();
}

export function appendMessage(message, { stick = true } = {}) {
  if (!message) return;
  if (message.kind === "system") {
    renderThread({ stick });
    return;
  }
  const inner = document.getElementById("messages-inner");
  const scroller = document.getElementById("messages");
  if (!inner) return;
  const nearBottom = scroller ? scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 120 : true;
  const empty = inner.querySelector(".empty");
  if (empty) inner.innerHTML = "";
  const end = inner.querySelector(".messages__end");
  if (end) end.remove();
  const messages = roomMessages();
  const previous = messages[messages.length - 2];
  const continued =
    previous &&
    previous.user_id === message.user_id &&
    message.created_at - previous.created_at < 300 &&
    !message.quote;
  inner.appendChild(messageRow(message, Boolean(continued)));
  inner.insertAdjacentHTML("beforeend", '<div class="messages__end">No more messages</div>');
  if (stick && nearBottom && scroller) scroller.scrollTop = scroller.scrollHeight;
  ensurePreviews([message]);
}

export function markHighlight(id) {
  const node = document.getElementById(`msg-${id}`);
  if (!node) return false;
  node.scrollIntoView({ block: "center" });
  node.classList.remove("msg--highlight");
  void node.offsetWidth;
  node.classList.add("msg--highlight");
  return true;
}

/* ------------------------------------------------------------- link previews */
async function ensurePreviews(messages) {
  if (!state.bootstrap.previews_enabled) return;
  for (const message of messages) {
    if (message.deleted_at || message.preview) continue;
    const urls = extractUrls(message.body).filter((url) => url.length < 400);
    if (!urls.length) continue;
    const url = urls[0];
    if (previewCache.has(url)) {
      const cached = previewCache.get(url);
      if (cached) attachPreview(message.id, cached);
      continue;
    }
    previewCache.set(url, null);
    try {
      const data = await api.get(`/api/previews?url=${encodeURIComponent(url)}`);
      if (data.preview) {
        previewCache.set(url, data.preview);
        attachPreview(message.id, data.preview);
      }
    } catch (error) {
      /* A preview is optional. Stay quiet when a site blocks the fetch. */
    }
  }
}

function attachPreview(messageId, preview) {
  const row = document.getElementById(`msg-${messageId}`);
  if (!row || row.querySelector(".link-preview")) return;
  if (!preview || !preview.title) return;
  const container = row.querySelector(".msg__attachments");
  if (!container) return;
  const link = document.createElement("a");
  link.className = "link-preview";
  link.href = preview.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.innerHTML = `
    ${preview.image ? `<img class="link-preview__image" src="${escapeHtml(preview.image)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : ""}
    <span class="link-preview__body">
      <span class="link-preview__site">${escapeHtml(preview.site || "")}</span>
      <span class="link-preview__title">${escapeHtml(preview.title)}</span>
      ${preview.description ? `<span class="link-preview__desc">${escapeHtml(preview.description)}</span>` : ""}
    </span>`;
  container.appendChild(link);
}

/* ---------------------------------------------------------------------- typing */
export function renderTyping() {
  const slot = document.getElementById("typing-slot");
  if (!slot) return;
  const now = Date.now();
  const names = [...state.typing.entries()]
    .filter(([, value]) => now - value.at < 3200)
    .map(([, value]) => value.name);
  if (!names.length) {
    slot.innerHTML = "";
    return;
  }
  const label = names.length === 1 ? `${names[0]} is typing` : `${names.length} people are typing`;
  slot.innerHTML = `<span class="typing__dots" aria-hidden="true"><span></span><span></span><span></span></span><span>${escapeHtml(label)}</span>`;
}

export function renderConnection() {
  const dot = document.getElementById("connection-dot");
  if (!dot) return;
  dot.style.background = state.connected ? "var(--live)" : "var(--warn)";
}

export function renderReactionPicker(target) {
  document.querySelectorAll(".reaction-picker").forEach((node) => node.remove());
  const row = target.closest(".msg");
  if (!row) return;
  const picker = document.createElement("div");
  picker.className = "reaction-picker";
  picker.setAttribute("role", "group");
  picker.setAttribute("aria-label", "Reactions");
  picker.innerHTML = (state.reactions.length ? state.reactions : ["👍", "🎉", "👀", "✅", "😂", "🙏"])
    .map((emoji) => `<button type="button" data-action="react-one" data-id="${row.dataset.id}" data-emoji="${emoji}" aria-label="React with ${emoji}">${emoji}</button>`)
    .join("");
  row.querySelector(".msg__main").appendChild(picker);
}
