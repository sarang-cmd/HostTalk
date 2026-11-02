const PREF_KEY = "hosttalk.prefs.v2";
const NAME_KEY = "hosttalk.name";
const DEVICE_KEY = "hosttalk.device";

export const bootstrap = readBootstrap();
export const state = {
  bootstrap,
  me: null,
  rooms: [],
  people: [],
  messages: new Map(),
  members: new Map(),
  hasMore: new Map(),
  activeRoomId: "main",
  replyTo: null,
  typing: new Map(),
  unread: new Map(),
  lastSeen: new Map(),
  palette: bootstrap.palette || [],
  reactions: [],
  emoji: [],
  connected: false,
  gifReady: Boolean(bootstrap.gifs_ready),
  prefs: loadPrefs(),
  drafts: new Map(),
  pending: new Map(),
  unlocked: new Set(),
};

function readBootstrap() {
  try {
    return JSON.parse(document.body.dataset.bootstrap || "{}");
  } catch (error) {
    return {};
  }
}

export function loadPrefs() {
  const defaults = { theme: "auto", sounds: true };
  try {
    const stored = JSON.parse(localStorage.getItem(PREF_KEY) || "{}");
    return { ...defaults, ...stored };
  } catch (error) {
    return defaults;
  }
}

export function savePrefs() {
  localStorage.setItem(PREF_KEY, JSON.stringify(state.prefs));
}

export function deviceKey() {
  let key = localStorage.getItem(DEVICE_KEY);
  if (!key) {
    key = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    localStorage.setItem(DEVICE_KEY, key);
  }
  return key;
}

export function savedName() {
  return localStorage.getItem(NAME_KEY) || "";
}

export function rememberName(name) {
  localStorage.setItem(NAME_KEY, name);
}

/* ------------------------------------------------------------------ requests */
export async function request(path, options = {}) {
  const { method = "GET", body, headers = {}, signal } = options;
  const config = { method, headers: { ...headers }, credentials: "same-origin", signal };
  if (body instanceof FormData) {
    config.body = body;
  } else if (body !== undefined) {
    config.headers["Content-Type"] = "application/json";
    config.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, config);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    const offline = new Error("No connection to the room. Check the Wi-Fi.");
    offline.offline = true;
    throw offline;
  }
  let data = null;
  const type = response.headers.get("content-type") || "";
  if (type.includes("application/json")) {
    try {
      data = await response.json();
    } catch (error) {
      data = null;
    }
  }
  if (!response.ok) {
    const failure = new Error((data && data.message) || `Request failed (${response.status})`);
    failure.status = response.status;
    failure.data = data || {};
    throw failure;
  }
  return data || {};
}

export const api = {
  get: (path, options) => request(path, { ...options, method: "GET" }),
  post: (path, body, options) => request(path, { ...options, method: "POST", body }),
  patch: (path, body, options) => request(path, { ...options, method: "PATCH", body }),
  delete: (path, options) => request(path, { ...options, method: "DELETE" }),
};

/* -------------------------------------------------------------------- helpers */
export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

const URL_PATTERN = /(https?:\/\/[^\s<>"']+)/gi;

export function linkify(text) {
  return escapeHtml(text).replace(URL_PATTERN, (match) => {
    const clean = match.replace(/[.,;:!?)]+$/, "");
    const trailing = match.slice(clean.length);
    return `<a href="${clean}" target="_blank" rel="noopener noreferrer">${clean}</a>${trailing}`;
  });
}

export function extractUrls(text) {
  const matches = String(text || "").match(URL_PATTERN);
  return matches ? [...new Set(matches.map((url) => url.replace(/[.,;:!?)]+$/, "")))] : [];
}

export function initials(name) {
  const parts = String(name || "?").trim().split(/\s+/).slice(0, 2);
  return parts.map((part) => Array.from(part)[0] || "").join("").toUpperCase() || "?";
}

const timeFormat = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
const dayFormat = new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric" });

export function formatTime(value) {
  if (!value) return "";
  return timeFormat.format(new Date(value * 1000));
}

export function formatDay(value) {
  const date = new Date(value * 1000);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  const sameDay = (a, b) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  if (sameDay(date, today)) return "Today";
  if (sameDay(date, yesterday)) return "Yesterday";
  return dayFormat.format(date);
}

export function formatSize(bytes) {
  const size = Number(bytes) || 0;
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(size < 10240 ? 1 : 0)} KB`;
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  return `${(size / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function debounce(fn, wait = 200) {
  let timer = 0;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

export function debouncePer(fn, wait = 2000) {
  const timers = new Map();
  return (key, ...args) => {
    const last = timers.get(key) || 0;
    const now = Date.now();
    if (now - last < wait) return;
    timers.set(key, now);
    fn(...args);
  };
}

export function avatarStyle(color) {
  return `background:${color || "#34527A"}`;
}

/**
 * A picture when the person has one, initials when they do not.
 * The initials ride along on the image so a broken file falls back cleanly.
 */
export function avatarHtml(person, className = "avatar", { lazy = true } = {}) {
  const safe = person || {};
  const label = initials(safe.name);
  const color = safe.color || "#34527A";
  if (safe.avatar_url) {
    return `<img class="${className} avatar--img" src="${escapeHtml(safe.avatar_url)}" alt=""
      data-initials="${escapeHtml(label)}" data-color="${escapeHtml(color)}"
      aria-hidden="true"${lazy ? ' loading="lazy"' : ""}>`;
  }
  return `<span class="${className}" style="${avatarStyle(color)}" aria-hidden="true">${label}</span>`;
}

export function badgeHtml(person) {
  const icon = (person && person.badge_icon) || "";
  const text = (person && person.badge_text) || "";
  // The server keeps an icon with empty text, so the pill shows the icon alone.
  if (!icon) return "";
  const label = text ? escapeHtml(text) : "";
  return `<span class="badge" title="Badge"><svg class="icon icon--xs" aria-hidden="true"><use href="#i-${escapeHtml(icon)}"></use></svg>${label}</span>`;
}

export function roleLabel(role) {
  if (role === "host") return "Host";
  if (role === "moderator") return "Mod";
  return "";
}

export function roleBadge(role) {
  const label = roleLabel(role);
  if (!label) return "";
  return `<span class="role role--${escapeHtml(role)}">${label}</span>`;
}

export function customEmoji(value) {
  if (!value || !value.startsWith("custom:")) return null;
  return (state.emoji || []).find((item) => item.token === value) || null;
}

export function reactionHtml(value) {
  const custom = customEmoji(value);
  if (custom) {
    return `<img class="reaction__img" src="${escapeHtml(custom.url)}" alt=":${escapeHtml(custom.name)}:" loading="lazy">`;
  }
  if (String(value).startsWith("custom:")) {
    return '<span class="reaction__gone" aria-hidden="true">?</span>';
  }
  return `<span aria-hidden="true">${escapeHtml(value)}</span>`;
}

export function reactionLabel(value, count) {
  const custom = customEmoji(value);
  const name = custom ? `:${custom.name}:` : value;
  return `${name}, ${count} ${count === 1 ? "reaction" : "reactions"}`;
}

export function canModerate(person) {
  return Boolean(person && (person.role === "host" || person.role === "moderator"));
}

export function qrSvg(text, cellSize = 4) {
  const factory = globalThis.qrcode;
  if (!factory || !text) return "";
  try {
    const qr = factory(0, "M");
    qr.addData(text);
    qr.make();
    return qr.createSvgTag({ cellSize, margin: 0, scalable: true });
  } catch (error) {
    return "";
  }
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (error) {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const copied = document.execCommand("copy");
    area.remove();
    return copied;
  }
}

export function applyTheme(theme) {
  const resolved =
    theme === "auto"
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : theme;
  document.documentElement.dataset.theme = resolved;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", resolved === "dark" ? "#101311" : "#f1f0eb");
}

export function setTheme(theme) {
  state.prefs.theme = theme;
  savePrefs();
  applyTheme(theme);
  document.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.themeChoice === theme));
  });
}

export function setSounds(enabled) {
  state.prefs.sounds = Boolean(enabled);
  savePrefs();
  document.querySelectorAll("[data-sounds-choice]").forEach((button) => {
    button.setAttribute("aria-pressed", String((button.dataset.soundsChoice === "on") === state.prefs.sounds));
  });
}

export function currentRoom() {
  return state.rooms.find((room) => room.id === state.activeRoomId) || null;
}

export function roomMessages(roomId = state.activeRoomId) {
  return state.messages.get(roomId) || [];
}

export function personById(id) {
  return state.people.find((person) => person.id === id) || null;
}

export function isOnline(id) {
  const person = personById(id);
  return Boolean(person && person.online);
}

export function toastToneFor(error) {
  return error && error.status && error.status < 500 ? "error" : "error";
}
