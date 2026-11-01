"""Shared service objects created once per server process."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .config import Config
from .events import Broker
from .gifs import GifService
from .localsend import LocalSendManager
from .logging_setup import configure_logging
from .presence import Presence
from .previews import PreviewCache
from .store import MAIN_ROOM, Store


class ServerControl:
    """Lets the host console stop the HTTP server cleanly."""

    def __init__(self) -> None:
        self._stop_callbacks: list[Callable[[], None]] = []
        self.requested_at: float | None = None
        self._lock = threading.Lock()

    def on_stop(self, callback: Callable[[], None]) -> None:
        with self._lock:
            self._stop_callbacks.append(callback)

    def request_stop(self) -> None:
        with self._lock:
            self.requested_at = time.time()
            callbacks = list(self._stop_callbacks)
        for callback in callbacks:
            try:
                callback()
            except Exception:  # pragma: no cover - shutdown must keep going
                logging.getLogger("hosttalk").exception("Stop callback failed")


@dataclass
class Services:
    config: Config
    store: Store
    presence: Presence
    broker: Broker
    previews: PreviewCache
    gifs: GifService
    localsend: LocalSendManager
    control: ServerControl
    logger: logging.Logger
    started_at: float = field(default_factory=time.time)
    auth_limiter: Any = None
    message_limiter: Any = None
    upload_limiter: Any = None
    typing_limiter: Any = None

    def shutdown(self) -> None:
        """Stop discovery and close the database. Safe to call twice."""
        self.localsend.stop()
        self.store.close()

    def room_public(self, room: dict[str, Any], user_id: str) -> dict[str, Any]:
        members = self.store.room_members(room["id"]) if room["kind"] != "main" else []
        return {
            "id": room["id"],
            "name": room["name"],
            "kind": room["kind"],
            "created_at": room["created_at"],
            "created_by": room.get("created_by", ""),
            "member_limit": int(room.get("member_limit", self.config.max_room_members)),
            "members": int(room.get("members", len(members))),
            "has_password": bool(room.get("password_hash")),
            "joined": room["id"] == MAIN_ROOM or self.store.is_member(room["id"], user_id),
            "last_seq": room.get("last_seq"),
            "messages": int(room.get("message_count") or self.store.count_messages(room["id"])),
        }


def build_services(config: Config, *, start_localsend: bool = True) -> Services:
    logger = configure_logging(config.log_dir, config.log_level)
    store = Store(config.database_path)
    store.ensure_room(MAIN_ROOM, config.room_name, kind="main")
    presence = Presence(store)
    broker = Broker()

    def on_receive(record: dict[str, Any]) -> None:
        room_id = MAIN_ROOM
        user = store.get_user_by_name("LocalSend")
        if not user:
            user = store.create_user("LocalSend", device_key="localsend")
        store.add_message(
            room_id,
            user["id"],
            "LocalSend",
            f"Received {record.get('filename', 'a file')} from {record.get('alias', 'a device')}",
            kind="system",
            meta={"source": "localsend", "filename": record.get("filename")},
        )

    localsend = LocalSendManager(
        enabled=bool(config.localsend.get("enabled")),
        alias=str(config.localsend.get("alias") or "HostTalk"),
        secret=config.secret_key,
        pin=str(config.localsend.get("pin") or ""),
        protocol="https" if config.localsend.get("https") else "http",
        logger=logger.getChild("localsend"),
        on_receive=on_receive,
    )
    if start_localsend:
        localsend.start()

    return Services(
        config=config,
        store=store,
        presence=presence,
        broker=broker,
        previews=PreviewCache(),
        gifs=GifService(config.giphy_key, enabled=bool(config.values["gifs_enabled"])),
        localsend=localsend,
        control=ServerControl(),
        logger=logger,
    )
