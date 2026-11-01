"""Session handling, rate limiting, and input validation."""

from __future__ import annotations

import re
import time
import unicodedata
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from flask import g, jsonify, request, session

from .config import Config
from .netinfo import is_loopback
from .store import Store

MAX_NAME_LEN = 32
MAX_MESSAGE_LEN = 4000
MAX_ROOM_NAME_LEN = 40
NICKNAME_COOLDOWN_SECONDS = 3600
ALLOWED_REACTIONS = ["👍", "🎉", "👀", "✅", "😂", "🙏", "🔥", "💡", "❤️", "🤝"]

# Twenty distinct colors. Each passes 4.5:1 contrast against white text.
COLOR_GRID = [
    "#B5483A", "#9C6019", "#7A6A1B", "#3F7A3F", "#1F7A6A",
    "#1F6B8C", "#2B4B9B", "#5B3F9B", "#8C3F86", "#A33F63",
    "#6B4A3A", "#4A5A38", "#2F6E4A", "#2C6E8F", "#434C6B",
    "#6B3F2F", "#8A5A0F", "#3A6B5A", "#6B2F4A", "#34527A",
]
_SAFE_NAME = re.compile(r"^[^\x00-\x1f\x7f]{1,32}$")


class ValidationError(ValueError):
    def __init__(self, message: str, *, field: str = "", status: int = 400):
        super().__init__(message)
        self.message = message
        self.field = field
        self.status = status


def clean_name(raw: Any) -> str:
    text = unicodedata.normalize("NFKC", str(raw or ""))
    text = " ".join(text.split())
    if not text:
        raise ValidationError("Enter a name", field="name")
    if len(text) > MAX_NAME_LEN:
        raise ValidationError(f"Name must be {MAX_NAME_LEN} characters or fewer", field="name")
    if not _SAFE_NAME.match(text):
        raise ValidationError("Name contains characters that are not allowed", field="name")
    if text.lower() in {"system", "hosttalk", "admin"}:
        raise ValidationError("Choose a different name", field="name")
    return text


def clean_message(raw: Any) -> str:
    text = str(raw or "").replace("\r\n", "\n").strip()
    if not text:
        raise ValidationError("Write a message first", field="body")
    if len(text) > MAX_MESSAGE_LEN:
        raise ValidationError(
            f"Messages limit is {MAX_MESSAGE_LEN} characters", field="body"
        )
    # Three blank lines in a row add height and no meaning.
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text


def clean_room_name(raw: Any) -> str:
    text = " ".join(str(raw or "").split())
    if not text:
        raise ValidationError("Enter a room name", field="name")
    if not any(char.isalnum() for char in text):
        raise ValidationError("Add a letter or a number to the room name", field="name")
    if len(text) > MAX_ROOM_NAME_LEN:
        raise ValidationError(
            f"Room names limit is {MAX_ROOM_NAME_LEN} characters", field="name"
        )
    return text


def clean_color(raw: Any) -> str:
    """Return a palette color. The grid is closed, so every name stays readable."""
    text = str(raw or "").strip().upper()
    if text not in COLOR_GRID:
        raise ValidationError("Pick a color from the grid", field="color")
    return text


def clean_emoji(raw: Any) -> str:
    text = str(raw or "")
    if text not in ALLOWED_REACTIONS:
        raise ValidationError("That reaction is not available", field="emoji")
    return text


def luminance_contrast(hex_color: str) -> float:
    """Contrast ratio against white, used to keep avatars readable."""
    value = hex_color.lstrip("#")
    channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    rel = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    return 1.05 / (rel + 0.05)


@dataclass
class Attempt:
    times: deque[float] = field(default_factory=deque)
    blocked_until: float = 0.0


class RateLimiter:
    """Sliding window limiter with a short lockout after repeated failures."""

    def __init__(self, limit: int, window: float, lockout: float = 0.0):
        self.limit = limit
        self.window = window
        self.lockout = lockout
        self._attempts: dict[str, Attempt] = {}

    def check(self, key: str) -> tuple[bool, int]:
        stamp = time.time()
        attempt = self._attempts.setdefault(key, Attempt())
        if attempt.blocked_until > stamp:
            return False, int(attempt.blocked_until - stamp) + 1
        while attempt.times and stamp - attempt.times[0] > self.window:
            attempt.times.popleft()
        if len(attempt.times) >= self.limit:
            return False, int(self.window - (stamp - attempt.times[0])) + 1
        return True, 0

    def hit(self, key: str, *, failed: bool = False) -> None:
        stamp = time.time()
        attempt = self._attempts.setdefault(key, Attempt())
        attempt.times.append(stamp)
        if failed and self.lockout and len(attempt.times) >= self.limit:
            attempt.blocked_until = stamp + self.lockout

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)

    def snapshot(self) -> dict[str, int]:
        return {key: len(attempt.times) for key, attempt in self._attempts.items()}


def client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def origin_allowed() -> bool:
    """Reject cross-site writes even when cookies are sent."""
    origin = request.headers.get("Origin")
    if not origin:
        return True
    allowed = {
        request.host,
        request.headers.get("X-Forwarded-Host", ""),
    }
    from urllib.parse import urlsplit

    return urlsplit(origin).netloc in {value for value in allowed if value}


def current_user_id() -> str:
    return str(session.get("user_id", ""))


def load_user(store: Store) -> dict[str, Any] | None:
    user_id = current_user_id()
    if not user_id:
        return None
    return store.get_user(user_id)


def bind_session(user: dict[str, Any]) -> None:
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    session.modified = True


def clear_session() -> None:
    session.clear()


def host_session() -> bool:
    return bool(session.get("host_ok"))


def host_access_allowed(config: Config) -> bool:
    if not host_session():
        return False
    if config.values["console_local_only"]:
        return is_loopback(client_ip())
    return True


def is_host_request(config: Config) -> bool:
    """True when the request comes from the machine running the server."""
    if not is_loopback(client_ip()):
        return False
    return bool(config.values["console_local_only"])


def json_error(message: str, status: int = 400, **extra: Any):
    payload = {"ok": False, "message": message}
    payload.update(extra)
    response = jsonify(payload)
    response.status_code = status
    return response


def api_guard(config: Config) -> Callable:
    """Decorator that requires a signed-in chat session for API routes."""

    def decorator(view: Callable):
        def wrapper(*args, **kwargs):
            if not origin_allowed():
                return json_error("This request came from another site", 403)
            user = load_user(g.store) if hasattr(g, "store") else None
            if not user:
                return json_error("Join the room first", 401)
            g.user = user
            return view(*args, **kwargs)

        wrapper.__name__ = view.__name__
        return wrapper

    return decorator


def available_colors(store: Store, active_colors: set[str]) -> list[str]:
    taken = {color.upper() for color in active_colors}
    return [color for color in COLOR_GRID if color.upper() not in taken]


def assign_color(store: Store, user: dict[str, Any], active_colors: set[str]) -> str:
    existing = (user.get("color") or "").upper()
    taken = {color.upper() for color in active_colors}
    if existing in COLOR_GRID and existing not in taken:
        return existing
    free = available_colors(store, taken)
    color = free[0] if free else COLOR_GRID[hash(user["id"]) % len(COLOR_GRID)]
    store.set_user_color(user["id"], color)
    return color
