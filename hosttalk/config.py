"""Paths and typed settings for HostTalk.

Settings live in ``config.json`` inside the data directory. Environment
variables and command line flags override the file. The file is written with
owner-only permissions and never stores passwords in plain text.
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import bcrypt
from dotenv import load_dotenv

APP_NAME = "HostTalk"
CONFIG_FILENAME = "config.json"
DATABASE_FILENAME = "hosttalk.db"
DEFAULT_PORT = 7284  # ASCII H (72) and T (84).
LEGACY_PORT = 6767
DEFAULT_BIND = "0.0.0.0"
MIN_PORT = 1024
MAX_PORT = 65535

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "room_name": "Front room",
    "port": DEFAULT_PORT,
    "bind": DEFAULT_BIND,
    "open_browser": True,
    "setup_complete": False,
    "password_hash": "",
    "host_user": "host",
    "host_password_hash": "",
    "secret_key": "",
    "console_local_only": True,
    "max_room_members": 20,
    "max_upload_mb": 20,
    "message_limit": 50,
    "log_level": "INFO",
    "default_theme": "auto",
    "previews_enabled": True,
    "gifs_enabled": True,
    "klipy_key": "",
    "retention_days": 0,
    "room_locked": False,
    "read_only": False,
    "slow_mode_seconds": 0,
    "notice_text": "",
    "localsend": {
        "enabled": True,
        "alias": "HostTalk",
        "announce": True,
        "https": False,
        "pin": "",
    },
}


class ConfigError(RuntimeError):
    """Raised when a setting value fails validation."""


def platform_data_dir() -> Path:
    """Return the per-user data directory for the current platform."""
    override = os.getenv("HOSTTALK_HOME")
    if override:
        return Path(override).expanduser()

    if sys.platform.startswith("win"):
        base = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    xdg = os.getenv("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "hosttalk"
    return Path.home() / ".local" / "share" / "hosttalk"


def project_root() -> Path:
    """Directory that holds bundled templates and static files."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return Path(__file__).resolve().parent.parent


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off", ""}:
        return False
    raise ConfigError(f"Expected a boolean, received {value!r}")


def coerce_port(value: Any) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError("Port must be a whole number") from exc
    if port < MIN_PORT or port > MAX_PORT:
        raise ConfigError(f"Port must be between {MIN_PORT} and {MAX_PORT}")
    return port


def coerce_level(value: Any) -> str:
    level = str(value).upper().strip()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigError("Log level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
    return level


def merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Recursive merge that keeps unknown keys out of the result."""
    result = dict(base)
    for key, value in incoming.items():
        if key not in base:
            continue
        current = base[key]
        if isinstance(current, dict) and isinstance(value, dict):
            result[key] = merge(current, value)
        else:
            result[key] = value
    return result


@dataclass
class Config:
    """Loaded configuration with validation and atomic persistence."""

    data_dir: Path
    values: dict[str, Any] = field(default_factory=lambda: json.loads(json.dumps(DEFAULT_CONFIG)))
    path: Path | None = None

    # ---------------------------------------------------------------- loading
    @classmethod
    def load(cls, data_dir: Path | None = None, overrides: dict[str, Any] | None = None) -> Config:
        load_dotenv(project_root() / ".env", override=False)
        home = Path(data_dir).expanduser() if data_dir else platform_data_dir()
        home.mkdir(parents=True, exist_ok=True)
        path = home / CONFIG_FILENAME
        stored: dict[str, Any] = {}
        if path.exists():
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                stored = {}
        values = merge(DEFAULT_CONFIG, stored if isinstance(stored, dict) else {})
        config = cls(data_dir=home, values=values, path=path)
        config._apply_environment()
        if overrides:
            config._apply_overrides(overrides)
        config._migrate_legacy_password()
        config._migrate_host_credentials()
        if not config.values["secret_key"]:
            config.values["secret_key"] = secrets.token_hex(32)
        config.save()
        return config

    def _apply_environment(self) -> None:
        env = os.environ
        if env.get("HOSTTALK_PORT"):
            self.values["port"] = coerce_port(env["HOSTTALK_PORT"])
        if env.get("PORT") and env.get("HOSTTALK_USE_PORT_ENV") == "1":
            self.values["port"] = coerce_port(env["PORT"])
        if env.get("HOSTTALK_BIND"):
            self.values["bind"] = env["HOSTTALK_BIND"].strip()
        if env.get("HOSTTALK_ROOM_NAME"):
            self.values["room_name"] = env["HOSTTALK_ROOM_NAME"].strip()
        if env.get("HOSTTALK_NO_BROWSER"):
            self.values["open_browser"] = not coerce_bool(env["HOSTTALK_NO_BROWSER"])
        if env.get("HOSTTALK_CONSOLE_LOCAL_ONLY"):
            self.values["console_local_only"] = coerce_bool(env["HOSTTALK_CONSOLE_LOCAL_ONLY"])
        if env.get("LOG_LEVEL"):
            self.values["log_level"] = coerce_level(env["LOG_LEVEL"])
        # The old variable name still reads, so an existing .env keeps working.
        gif_key = env.get("KLIPY_API_KEY") or env.get("GIPHY_API_KEY")
        if gif_key:
            self.values["klipy_key"] = gif_key.strip()
        if env.get("HOSTTALK_LOCALSEND"):
            self.values["localsend"]["enabled"] = coerce_bool(env["HOSTTALK_LOCALSEND"])
        if env.get("HOSTTALK_LS_PIN"):
            self.values["localsend"]["pin"] = env["HOSTTALK_LS_PIN"].strip()
        if env.get("HOSTTALK_MAX_UPLOAD_MB"):
            self.values["max_upload_mb"] = int(env["HOSTTALK_MAX_UPLOAD_MB"])
        if env.get("HOSTTALK_MAX_MEMBERS"):
            self.values["max_room_members"] = int(env["HOSTTALK_MAX_MEMBERS"])
        if env.get("HOSTTALK_THEME"):
            self.values["default_theme"] = env["HOSTTALK_THEME"].strip().lower()

    def _apply_overrides(self, overrides: dict[str, Any]) -> None:
        for key, value in overrides.items():
            if value is None:
                continue
            if key == "port":
                self.values["port"] = coerce_port(value)
            elif key == "bind":
                self.values["bind"] = str(value).strip()
            elif key == "open_browser":
                self.values["open_browser"] = coerce_bool(value)
            elif key == "log_level":
                self.values["log_level"] = coerce_level(value)
            elif key == "data_dir":
                continue
            elif key in self.values:
                self.values[key] = value

    def _migrate_host_credentials(self) -> None:
        """Before 2.2 the console used the room password. Keep those installs in."""
        if not self.values.get("host_password_hash") and self.values.get("password_hash"):
            self.values["host_password_hash"] = self.values["password_hash"]
        if not str(self.values.get("host_user") or "").strip():
            self.values["host_user"] = "host"

    def _migrate_legacy_password(self) -> None:
        """Hash a plain password from .env once, then rely on config.json."""
        if self.values["password_hash"]:
            return
        legacy = os.getenv("SERVER_PASSWORD", "").strip()
        if not legacy:
            return
        self.values["password_hash"] = bcrypt.hashpw(
            legacy.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        self.values["setup_complete"] = True

    # ----------------------------------------------------------------- saving
    def save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.values, indent=2, sort_keys=True) + "\n"
        fd, tmp = tempfile.mkstemp(dir=str(self.data_dir), prefix=".config-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            with contextlib.suppress(OSError):
                os.chmod(tmp, 0o600)
            os.replace(tmp, self.path or (self.data_dir / CONFIG_FILENAME))
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    # ------------------------------------------------------------- properties
    @property
    def port(self) -> int:
        return int(self.values["port"])

    @property
    def bind(self) -> str:
        return str(self.values["bind"])

    @property
    def room_name(self) -> str:
        return str(self.values["room_name"])

    @property
    def setup_complete(self) -> bool:
        return bool(self.values["setup_complete"] and self.values["password_hash"])

    @property
    def secret_key(self) -> str:
        return str(self.values["secret_key"])

    @property
    def log_level(self) -> str:
        return str(self.values["log_level"])

    @property
    def upload_limit_bytes(self) -> int:
        return int(self.values["max_upload_mb"]) * 1024 * 1024

    @property
    def max_room_members(self) -> int:
        return int(self.values["max_room_members"])

    @property
    def host_user(self) -> str:
        return str(self.values.get("host_user") or "host")

    @property
    def klipy_key(self) -> str:
        return str(self.values.get("klipy_key", "")).strip()

    @property
    def localsend(self) -> dict[str, Any]:
        return dict(self.values["localsend"])

    @property
    def previews_enabled(self) -> bool:
        return bool(self.values["previews_enabled"])

    @property
    def database_path(self) -> Path:
        return self.data_dir / DATABASE_FILENAME

    @property
    def upload_dir(self) -> Path:
        path = self.data_dir / "uploads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def log_dir(self) -> Path:
        path = self.data_dir / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    # -------------------------------------------------------------- passwords
    def verify_password(self, password: str) -> bool:
        stored = str(self.values.get("password_hash") or "")
        if not stored or not password:
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except ValueError:
            return False

    def verify_host_password(self, password: str) -> bool:
        stored = str(self.values.get("host_password_hash") or "")
        if not stored or not password:
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except ValueError:
            return False

    def set_host_password(self, password: str) -> None:
        text = str(password or "")
        if len(text.strip()) < 6:
            raise ConfigError("Use at least 6 characters for the host password")
        if len(text) > 128:
            raise ConfigError("Keep the host password under 128 characters")
        self.values["host_password_hash"] = bcrypt.hashpw(
            text.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        self.save()

    def set_host_user(self, username: str) -> str:
        text = str(username or "").strip()
        if not 2 <= len(text) <= 32:
            raise ConfigError("The host name needs 2 to 32 characters")
        if not all(char.isalnum() or char in "._-" for char in text):
            raise ConfigError("Use letters, numbers, dots, dashes, or underscores")
        self.values["host_user"] = text
        self.save()
        return text

    def verify_host_user(self, username: str) -> bool:
        return secrets.compare_digest(str(username or "").strip().lower(), self.host_user.lower())

    def set_password(self, password: str) -> None:
        if len(password.strip()) < 4:
            raise ConfigError("Password must be at least 4 characters")
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        self.values["password_hash"] = hashed
        if not self.values.get("host_password_hash"):
            # A fresh install has one password. The console asks for its own later.
            self.values["host_password_hash"] = hashed
        self.values["setup_complete"] = True
        self.save()

    # ------------------------------------------------------------------ edits
    def update(self, patch: dict[str, Any], *, allow_secret: bool = False) -> dict[str, Any]:
        """Validate and apply a settings patch. Returns the applied values."""
        applied: dict[str, Any] = {}
        for key, raw in (patch or {}).items():
            if key not in DEFAULT_CONFIG:
                continue
            if key in {"password_hash", "host_password_hash", "secret_key"} and not allow_secret:
                continue
            if key == "port":
                value: Any = coerce_port(raw)
            elif key == "log_level":
                value = coerce_level(raw)
            elif key in {
                "open_browser",
                "console_local_only",
                "previews_enabled",
                "gifs_enabled",
                "setup_complete",
                "room_locked",
                "read_only",
            }:
                value = coerce_bool(raw)
            elif key == "slow_mode_seconds":
                value = max(0, min(3600, int(raw)))
            elif key == "notice_text":
                value = str(raw or "").replace("\n", " ").strip()[:200]
            elif key == "host_user":
                continue
            elif key == "room_name":
                value = self._clean_room_name(raw)
            elif key == "max_room_members":
                value = max(2, min(200, int(raw)))
            elif key == "max_upload_mb":
                value = max(1, min(100, int(raw)))
            elif key == "retention_days":
                value = max(0, min(3650, int(raw)))
            elif key == "bind":
                value = self._clean_bind(raw)
            elif key == "localsend" and isinstance(raw, dict):
                value = merge(self.values["localsend"], raw)
                if "enabled" in raw:
                    value["enabled"] = coerce_bool(raw["enabled"])
                if "announce" in raw:
                    value["announce"] = coerce_bool(raw["announce"])
                if "https" in raw:
                    value["https"] = coerce_bool(raw["https"])
                value["alias"] = self._clean_label(value.get("alias", "HostTalk"), "Alias")
                value["pin"] = str(value.get("pin", ""))[:32]
            else:
                value = raw
            self.values[key] = value
            applied[key] = value
        self.save()
        return applied

    @staticmethod
    def _clean_room_name(value: Any) -> str:
        text = str(value).replace("\n", " ").strip()
        if not text:
            raise ConfigError("Room name cannot be empty")
        if len(text) > 48:
            raise ConfigError("Room name must be 48 characters or fewer")
        return text

    @staticmethod
    def _clean_bind(value: Any) -> str:
        text = str(value).strip()
        if text in {"localhost", "127.0.0.1", "::1"}:
            return "127.0.0.1"
        if text == "0.0.0.0":
            return "0.0.0.0"
        parts = text.split(".")
        if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
            return text
        raise ConfigError("Bind address must be 0.0.0.0 or a local IPv4 address")

    @staticmethod
    def _clean_label(value: Any, label: str) -> str:
        text = str(value).replace("\n", " ").strip()
        if not text:
            raise ConfigError(f"{label} cannot be empty")
        return text[:48]

    # ----------------------------------------------------------------- public
    def public_settings(self) -> dict[str, Any]:
        return {
            "room_name": self.room_name,
            "port": self.port,
            "bind": self.bind,
            "default_theme": self.values["default_theme"],
            "previews_enabled": self.previews_enabled,
            "gifs_enabled": bool(self.values["gifs_enabled"]) and bool(self.klipy_key),
            "localsend_enabled": bool(self.localsend.get("enabled")),
            "max_upload_mb": int(self.values["max_upload_mb"]),
            "setup_complete": self.setup_complete,
        }

    def redacted(self) -> dict[str, Any]:
        """Settings safe to render in the host console."""
        values = json.loads(json.dumps(self.values))
        values["password_hash"] = "set" if values.get("password_hash") else ""
        values["secret_key"] = "set" if values.get("secret_key") else ""
        values["klipy_key"] = "set" if values.get("klipy_key") else ""
        values["host_password_hash"] = "set" if values.get("host_password_hash") else ""
        values["gifs_enabled"] = bool(values.get("gifs_enabled"))
        values["previews_enabled"] = bool(values.get("previews_enabled"))
        values["localsend"]["pin"] = "set" if values["localsend"].get("pin") else ""
        return values
