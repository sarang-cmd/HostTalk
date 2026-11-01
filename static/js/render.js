import {
  api,
  avatarHtml,
  badgeHtml,
  canModerate,
  currentRoom,
  escapeHtml,
  extractUrls,
  formatDay,
  formatSize,
  formatTime,
  linkify,
  qrSvg,
  reactionHtml,
  reactionLabel,
  roleBadge,
  roleLabel,
  roomMessages,
  state,
} from "./core.js";
import { EMOJI_GROUPS } from "./emoji.js";

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
  const known = new Set(groups.map((room) => room.id));
  const children = new Map();
  for (const room of groups) {
    const parent = room.parent_id && known.has(room.parent_id) ? room.parent_id : "";
    if (!children.has(parent)) children.set(parent, []);
    children.get(parent).push(room);
  }
  const ordered = [];
  const walk = (parent, depth) => {
    for (const room of children.get(parent) || []) {
      ordered.push({ room, depth });
      walk(room.id, depth + 1);
    }
  };
  walk("", 0);
  list.innerHTML = ordered
    .map(({ room, depth }) => {
      const unread = state.unread.get(room.id) || 0;
      const kind = room.kind === "main" ? "main" : "room";
      return `
        <li>
          <button class="rail__item${depth ? " rail__item--child" : ""}" type="button" data-action="switch-room" data-room="${room.id}"
            data-joined="${room.joined ? "true" : "false"}"
            ${room.id === state.activeRoomId ? 'aria-current="true"' : ""}>
            <svg class="icon icon--sm" aria-hidden="true"><use href="#${room.kind === "main" ? "i-hash" : "i-room"}"></use></svg>
            <span class="rail__item-name">${escapeHtml(room.name)}</span>
            ${room.has_password ? '<svg class="icon icon--sm" aria-label="Password required"><use href="#i-lock"></use></svg>' : ""}
            ${room.joined ? "" : '<span class="rail__badge">not joined</span>'}
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
    avatar.innerHTML = avatarHtml(state.me, "avatar", { lazy: false });
  }
  setText("me-name", state.me.name);
  const role = roleLabel(state.me.role);
  setText("me-color-label", role ? `${role} of this room` : "In the room");
  setText("settings-role", roleText(state.me.role));
  const nameInput = document.getElementById("settings-name");
  if (nameInput && document.activeElement !== nameInput) nameInput.value = state.me.name;
  const roomName = document.getElementById("settings-room-name");
  if (roomName) roomName.textContent = state.bootstrap.room_name;
  const meta = document.getElementById("settings-room-meta");
  if (meta) meta.textContent = `${state.people.filter((p) => p.online).length} here · ${state.rooms.length} rooms`;
  renderColorGrid();
}

function roleText(role) {
  if (role === "host") return "Host. You hand out moderator roles, pin messages, and delete any message.";
  if (role === "moderator") return "Moderator. You pin messages and delete other people's messages.";
  return "Member. You look after your own messages. The host can make you a moderator.";
}

export function renderAvatarSettings() {
  const slot = document.getElementById("settings-avatar-slot");
  if (slot && state.me) slot.innerHTML = avatarHtml(state.me, "avatar avatar--xl", { lazy: false });
  const remove = document.getElementById("settings-avatar-remove");
  if (remove) remove.hidden = !(state.me && state.me.avatar_url);
  const hint = document.getElementById("settings-avatar-hint");
  if (hint) {
    hint.textContent = state.me && state.me.avatar_url
      ? "Shown in messages, the people panel, and the rail."
      : "Add a picture, or keep the initials from your name.";
  }
}

export function renderBadgeSettings() {
  const grid = document.getElementById("badge-icons");
  const input = document.getElementById("settings-badge-text");
  if (!grid || !state.me) return;
  const icons = state.bootstrap.badge_icons || [];
  const current = state.me.badge_icon || "";
  grid.innerHTML = icons
    .map(
      (icon) => `<button class="badge-choice" type="button" data-badge-icon="${icon}"
        aria-pressed="${icon === current}" aria-label="Badge icon ${icon}">
        <svg class="icon" aria-hidden="true"><use href="#i-${icon}"></use></svg>
      </button>`
    )
    .join("");
  if (input && document.activeElement !== input) input.value = state.me.badge_text || "";
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
  const iAmHost = Boolean(state.me && state.me.role === "host");
  list.innerHTML = members
    .map((person) => {
      const isMe = state.me && person.id === state.me.id;
      const sub = isMe ? "This device" : person.role === "moderator" ? "Keeps the room tidy" : "In the room";
      const nextRole = person.role === "moderator" ? "member" : "moderator";
      const roleButton =
        iAmHost && !isMe
          ? `<button class="icon-btn" type="button" data-action="role" data-user="${person.id}" data-role="${nextRole}"
              aria-label="${nextRole === "moderator" ? "Make" : "Remove"} moderator ${escapeHtml(person.name)}">
              <svg class="icon" aria-hidden="true"><use href="#i-shield"></use></svg></button>`
          : "";
      return `
        <li class="person">
          ${avatarHtml(person, "avatar avatar--lg")}
          <span class="person__meta">
            <span class="person__name">${escapeHtml(person.name)}${badgeHtml(person)}${roleBadge(person.role)}${isMe ? ' <span class="msg__you">you</span>' : ""}</span>
            <span class="person__sub">${sub}</span>
          </span>
          <span class="person__action">
            ${roleButton}
            ${isMe ? "" : `<button class="icon-btn" type="button" data-action="open-dm" data-user="${person.id}" aria-label="Message ${escapeHtml(person.name)}"><svg class="icon" aria-hidden="true"><use href="#i-reply"></use></svg></button>`}
          </span>
        </li>`;
    })
    .join("");
  const address = document.getElementById("panel-address");
  if (address) address.textContent = state.bootstrap.address || window.location.origin;
}

export function renderPinnedList(messages) {
  const list = document.getElementById("pinned-list");
  if (!list) return;
  if (!messages.length) {
    list.innerHTML =
      '<li class="empty"><span class="empty__title">Nothing pinned</span><p>Pin a message the room should keep in sight.</p></li>';
    return;
  }
  list.innerHTML = messages
    .map(
      (message) => `
      <li class="pinned-item">
        ${avatarHtml(message, "avatar avatar--lg")}
        <div class="pinned-item__body">
          <div class="pinned-item__head">
            <span class="pinned-item__name">${escapeHtml(message.name)}</span>
            ${badgeHtml(message)}
            ${roleBadge(message.role)}
            <span class="pinned-item__time">${formatTime(message.created_at)}</span>
          </div>
          <p class="pinned-item__text">${escapeHtml(message.body || "Attachment")}</p>
        </div>
        <button class="icon-btn" type="button" data-action="jump" data-room="${message.room_id}" data-id="${message.id}" data-seq="${message.seq}" aria-label="Go to pinned message">
          <svg class="icon" aria-hidden="true"><use href="#i-arrow-left"></use></svg>
        </button>
      </li>`
    )
    .join("");
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
  const privileged = canModerate(state.me);
  node.innerHTML = `
    ${avatarHtml(message, "msg__avatar")}
    <div class="msg__main">
      ${
        continued
          ? ""
          : `<div class="msg__head">
              <span class="msg__name">${escapeHtml(message.name)}</span>
              ${badgeHtml(message)}
              ${roleBadge(message.role)}
              ${mine ? '<span class="msg__you">you</span>' : ""}
              <span class="msg__time">${formatTime(message.created_at)}</span>
              ${message.edited_at ? '<span class="msg__edited">edited</span>' : ""}
              ${message.pinned_at ? '<span class="msg__pinned" title="Pinned message"><svg class="icon icon--sm" aria-hidden="true"><use href="#i-pin"></use></svg>Pinned</span>' : ""}
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
        ${privileged && !message.deleted_at ? `<button class="icon-btn" type="button" data-action="pin" data-id="${message.id}" data-pinned="${message.pinned_at ? "true" : "false"}" aria-label="${message.pinned_at ? "Unpin message" : "Pin message"}"><svg class="icon" aria-hidden="true"><use href="#i-pin"></use></svg></button>` : ""}
        ${(mine || privileged) && !message.deleted_at ? '<span class="msg__toolbar-divider" aria-hidden="true"></span>' : ""}
        ${(mine || privileged) && !message.deleted_at ? `<button class="icon-btn" type="button" data-action="delete" data-id="${message.id}" aria-label="Delete message"><svg class="icon" aria-hidden="true"><use href="#i-trash"></use></svg></button>` : ""}
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
      return `<button class="reaction" type="button" data-action="react-one" data-id="${message.id}" data-emoji="${escapeHtml(emoji)}" data-mine="${mine ? "true" : "false"}" aria-label="${escapeHtml(reactionLabel(emoji, users.length))}">
        ${reactionHtml(emoji)}<span>${users.length}</span>
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

  const custom = (state.emoji || [])
    .map(
      (item) => `<button class="reaction-picker__emoji reaction-picker__emoji--img" type="button"
        data-action="react-one" data-id="${row.dataset.id}" data-emoji="${escapeHtml(item.token)}"
        aria-label="React with :${escapeHtml(item.name)}:">
        <img src="${escapeHtml(item.url)}" alt="" loading="lazy">
      </button>`
    )
    .join("");

  const groups = EMOJI_GROUPS.map(
    (group) => `<p class="reaction-picker__label">${group.name}</p>
      <div class="reaction-picker__row">${group.emoji
        .map(
          (emoji) => `<button class="reaction-picker__emoji" type="button" data-action="react-one"
            data-id="${row.dataset.id}" data-emoji="${emoji}" aria-label="React with ${emoji}">${emoji}</button>`
        )
        .join("")}</div>`
  ).join("");

  picker.innerHTML = `
    ${custom ? `<div class="reaction-picker__custom">${custom}</div>` : ""}
    <div class="reaction-picker__grid">${groups}</div>
    <form class="reaction-picker__any">
      <input class="reaction-picker__input" maxlength="16" placeholder="Type or paste any emoji" aria-label="Any emoji">
      <button class="btn btn--sm" type="submit">React</button>
    </form>`;
  row.querySelector(".msg__main").appendChild(picker);
  picker.querySelector("form").addEventListener("submit", (event) => {
    event.preventDefault();
    const value = picker.querySelector("input").value.trim();
    if (!value) return;
    document.dispatchEvent(
      new CustomEvent("hosttalk:react", { detail: { id: row.dataset.id, emoji: value } })
    );
  });
}

export function renderEmojiManager() {
  const section = document.getElementById("emoji-section");
  if (section) section.hidden = !(state.me && state.me.role === "host");
  const list = document.getElementById("emoji-manage");
  if (!list) return;
  if (!state.emoji || !state.emoji.length) {
    list.innerHTML = '<li class="emoji-manage__empty">No custom emoji yet.</li>';
    return;
  }
  list.innerHTML = state.emoji
    .map(
      (item) => `<li class="emoji-manage__item">
        <img class="emoji-manage__img" src="${escapeHtml(item.url)}" alt="" loading="lazy">
        <span class="emoji-manage__name">:${escapeHtml(item.name)}:</span>
        <button class="icon-btn" type="button" data-action="delete-emoji" data-id="${escapeHtml(item.id)}" aria-label="Remove :${escapeHtml(item.name)}:">
          <svg class="icon" aria-hidden="true"><use href="#i-trash"></use></svg>
        </button>
      </li>`
    )
    .join("");
}
