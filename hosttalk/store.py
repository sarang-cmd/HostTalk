"""SQLite persistence for rooms, messages, people, and attachments."""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

MAIN_ROOM = "main"
MESSAGE_KINDS = {"text", "image", "file", "system", "gif"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    color TEXT NOT NULL DEFAULT '',
    device_key TEXT NOT NULL DEFAULT '',
    avatar_seed TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    last_nick_at REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS rooms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'group',
    created_by TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    password_hash TEXT NOT NULL DEFAULT '',
    member_limit INTEGER NOT NULL DEFAULT 20
);
CREATE TABLE IF NOT EXISTS room_members (
    room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at REAL NOT NULL,
    PRIMARY KEY (room_id, user_id)
);
CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    mime TEXT NOT NULL,
    size INTEGER NOT NULL,
    stored_name TEXT NOT NULL,
    uploader TEXT NOT NULL,
    sha256 TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'text',
    body TEXT NOT NULL DEFAULT '',
    attachment_id TEXT,
    quote_id TEXT,
    meta TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL,
    edited_at REAL,
    deleted_at REAL
);
CREATE INDEX IF NOT EXISTS idx_messages_room_seq ON messages(room_id, seq);
CREATE INDEX IF NOT EXISTS idx_messages_quote ON messages(quote_id);
CREATE TABLE IF NOT EXISTS reactions (
    message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    emoji TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (message_id, user_id, emoji)
);
CREATE TABLE IF NOT EXISTS invites (
    code TEXT PRIMARY KEY,
    room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    created_by TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    password_hash TEXT NOT NULL DEFAULT '',
    max_uses INTEGER NOT NULL DEFAULT 50,
    uses INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS nickname_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    old_name TEXT NOT NULL,
    new_name TEXT NOT NULL,
    ip TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
"""


def now() -> float:
    return time.time()


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:20]}"


class Store:
    """Thread-safe SQLite wrapper using one connection per thread."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._lock = threading.Lock()
        self._migrate()

    # ------------------------------------------------------------- connection
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @property
    def conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._connect()
            self._local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def _migrate(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(SCHEMA)
                conn.execute(
                    "INSERT INTO meta(key, value) VALUES('schema', '3') "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
                )
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    # ------------------------------------------------------------------- meta
    def get_meta(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    # ------------------------------------------------------------------ users
    def get_user(self, user_id: str) -> dict[str, Any] | None:
        return self._row(
            self.conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        )

    def get_user_by_name(self, name: str) -> dict[str, Any] | None:
        return self._row(
            self.conn.execute("SELECT * FROM users WHERE name=? COLLATE NOCASE", (name,)).fetchone()
        )

    def create_user(self, name: str, device_key: str = "", color: str = "") -> dict[str, Any]:
        user_id = new_id("u_")
        self.conn.execute(
            "INSERT INTO users(id, name, color, device_key, avatar_seed, created_at) "
            "VALUES(?,?,?,?,?,?)",
            (user_id, name, color, device_key, secrets.token_hex(4), now()),
        )
        self.conn.commit()
        return self.get_user(user_id) or {}

    def get_or_create_user(self, name: str, color: str = "", device_key: str = "") -> dict[str, Any]:
        existing = self.get_user_by_name(name)
        if existing:
            return existing
        return self.create_user(name, device_key=device_key, color=color)

    def set_device_key(self, user_id: str, device_key: str) -> None:
        self.conn.execute("UPDATE users SET device_key=? WHERE id=?", (device_key, user_id))
        self.conn.commit()

    def claim_name(self, name: str, device_key: str) -> tuple[dict[str, Any] | None, str]:
        """Return (user, error). Names bind to the first device that claims them."""
        user = self.get_user_by_name(name)
        if user is None:
            return self.create_user(name, device_key=device_key), ""
        stored = user.get("device_key") or ""
        if stored and device_key and stored != device_key:
            return None, "That name belongs to another device. Pick a different name."
        if not stored and device_key:
            self.set_device_key(user["id"], device_key)
        return user, ""

    def list_users(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
        return [dict(row) for row in rows]

    def set_user_color(self, user_id: str, color: str) -> None:
        self.conn.execute("UPDATE users SET color=? WHERE id=?", (color, user_id))
        self.conn.commit()

    def rename_user(
        self, user_id: str, new_name: str, *, ip: str = "", cooldown_seconds: int = 3600
    ) -> dict[str, Any]:
        user = self.get_user(user_id)
        if not user:
            raise KeyError("Unknown user")
        stamp = now()
        self.conn.execute(
            "UPDATE users SET name=?, last_nick_at=? WHERE id=?",
            (new_name, stamp, user_id),
        )
        self.conn.execute(
            "INSERT INTO nickname_log(user_id, old_name, new_name, ip, created_at) VALUES(?,?,?,?,?)",
            (user_id, user["name"], new_name, ip, stamp),
        )
        self.conn.execute(
            "UPDATE messages SET name=? WHERE user_id=?", (new_name, user_id)
        )
        self.conn.commit()
        return self.get_user(user_id) or {}

    def nickname_log(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM nickname_log ORDER BY id DESC LIMIT ?", (max(1, limit),)
        ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------ rooms
    def ensure_room(self, room_id: str, name: str, kind: str = "group") -> dict[str, Any]:
        room = self.get_room(room_id)
        if room:
            if name and room["name"] != name:
                self.conn.execute("UPDATE rooms SET name=? WHERE id=?", (name, room_id))
                self.conn.commit()
                room = self.get_room(room_id) or room
            return room
        self.conn.execute(
            "INSERT INTO rooms(id, name, kind, created_at, member_limit) VALUES(?,?,?,?,?)",
            (room_id, name, kind, now(), 20),
        )
        self.conn.commit()
        return self.get_room(room_id) or {}

    def get_room(self, room_id: str) -> dict[str, Any] | None:
        return self._row(self.conn.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone())

    def create_room(
        self,
        name: str,
        created_by: str,
        *,
        kind: str = "group",
        member_limit: int = 20,
        password_hash: str = "",
        room_id: str | None = None,
    ) -> dict[str, Any]:
        rid = room_id or new_id("r_")
        self.conn.execute(
            "INSERT INTO rooms(id, name, kind, created_by, created_at, password_hash, member_limit) "
            "VALUES(?,?,?,?,?,?,?)",
            (rid, name, kind, created_by, now(), password_hash, member_limit),
        )
        self.conn.commit()
        return self.get_room(rid) or {}

    def list_rooms_for(self, user_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT r.*, (SELECT COUNT(*) FROM room_members m WHERE m.room_id=r.id) AS members,
                   (SELECT MAX(seq) FROM messages msg WHERE msg.room_id=r.id) AS last_seq
            FROM rooms r
            WHERE r.id=? OR EXISTS (
                SELECT 1 FROM room_members m WHERE m.room_id=r.id AND m.user_id=?
            )
            ORDER BY CASE r.kind WHEN 'main' THEN 0 WHEN 'dm' THEN 1 ELSE 2 END, r.created_at
            """,
            (MAIN_ROOM, user_id),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_all_rooms(self) -> list[dict[str, Any]]:
        """Every room, for the host console. No membership filter."""
        rows = self.conn.execute(
            """
            SELECT r.*, (SELECT COUNT(*) FROM room_members m WHERE m.room_id=r.id) AS members,
                   (SELECT MAX(seq) FROM messages msg WHERE msg.room_id=r.id) AS last_seq,
                   (SELECT COUNT(*) FROM messages msg WHERE msg.room_id=r.id) AS message_count
            FROM rooms r
            ORDER BY CASE r.kind WHEN 'main' THEN 0 WHEN 'group' THEN 1 ELSE 2 END, r.created_at
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def add_member(self, room_id: str, user_id: str) -> bool:
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO room_members(room_id, user_id, joined_at) VALUES(?,?,?)",
                (room_id, user_id, now()),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_member(self, room_id: str, user_id: str) -> None:
        self.conn.execute(
            "DELETE FROM room_members WHERE room_id=? AND user_id=?", (room_id, user_id)
        )
        self.conn.commit()

    def is_member(self, room_id: str, user_id: str) -> bool:
        if room_id == MAIN_ROOM:
            return True
        row = self.conn.execute(
            "SELECT 1 FROM room_members WHERE room_id=? AND user_id=?", (room_id, user_id)
        ).fetchone()
        return row is not None

    def room_members(self, room_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT u.*, m.joined_at FROM room_members m
            JOIN users u ON u.id=m.user_id
            WHERE m.room_id=? ORDER BY m.joined_at
            """,
            (room_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def member_count(self, room_id: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS c FROM room_members WHERE room_id=?", (room_id,)
        ).fetchone()
        return int(row["c"]) if row else 0

    def delete_room(self, room_id: str) -> None:
        if room_id == MAIN_ROOM:
            raise ValueError("The main room cannot be deleted")
        self.conn.execute("DELETE FROM rooms WHERE id=?", (room_id,))
        self.conn.commit()

    def set_room_password(self, room_id: str, password_hash: str) -> None:
        self.conn.execute(
            "UPDATE rooms SET password_hash=? WHERE id=?", (password_hash, room_id)
        )
        self.conn.commit()

    def find_dm_room(self, user_a: str, user_b: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT r.* FROM rooms r
            JOIN room_members a ON a.room_id=r.id AND a.user_id=?
            JOIN room_members b ON b.room_id=r.id AND b.user_id=?
            WHERE r.kind='dm'
            LIMIT 1
            """,
            (user_a, user_b),
        ).fetchone()
        return self._row(row)

    # --------------------------------------------------------------- messages
    def add_message(
        self,
        room_id: str,
        user_id: str,
        name: str,
        body: str,
        *,
        kind: str = "text",
        attachment_id: str | None = None,
        quote_id: str | None = None,
        meta: dict[str, Any] | None = None,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        if kind not in MESSAGE_KINDS:
            kind = "text"
        mid = message_id or new_id("m_")
        self.conn.execute(
            """
            INSERT INTO messages(id, room_id, user_id, name, kind, body, attachment_id,
                                 quote_id, meta, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                mid,
                room_id,
                user_id,
                name,
                kind,
                body,
                attachment_id,
                quote_id,
                json.dumps(meta or {}),
                now(),
            ),
        )
        self.conn.commit()
        return self.get_message(mid) or {}

    def get_message(self, message_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
        return self._decorate(row)

    def _decorate(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        try:
            data["meta"] = json.loads(data.get("meta") or "{}")
        except json.JSONDecodeError:
            data["meta"] = {}
        return data

    def list_messages(
        self, room_id: str, *, before_seq: int | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        limit = max(1, min(200, limit))
        if before_seq:
            rows = self.conn.execute(
                "SELECT * FROM messages WHERE room_id=? AND seq<? ORDER BY seq DESC LIMIT ?",
                (room_id, before_seq, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM messages WHERE room_id=? ORDER BY seq DESC LIMIT ?",
                (room_id, limit),
            ).fetchall()
        return [self._decorate(row) or {} for row in reversed(rows)]

    def get_messages(self, message_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        ids = [message_id for message_id in message_ids if message_id]
        if not ids:
            return {}
        marks = ",".join("?" for _ in ids)
        rows = self.conn.execute(
            f"SELECT * FROM messages WHERE id IN ({marks})", ids
        ).fetchall()
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            item = self._decorate(row)
            if item:
                result[item["id"]] = item
        return result

    def messages_after(self, room_id: str, seq: int, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE room_id=? AND seq>? ORDER BY seq LIMIT ?",
            (room_id, seq, max(1, min(500, limit))),
        ).fetchall()
        return [self._decorate(row) or {} for row in rows]

    def edit_message(self, message_id: str, user_id: str, body: str) -> dict[str, Any] | None:
        self.conn.execute(
            "UPDATE messages SET body=?, edited_at=? WHERE id=? AND user_id=? AND deleted_at IS NULL",
            (body, now(), message_id, user_id),
        )
        self.conn.commit()
        return self.get_message(message_id)

    def delete_message(self, message_id: str, *, user_id: str | None = None) -> dict[str, Any] | None:
        message = self.get_message(message_id)
        if not message:
            return None
        if user_id and message["user_id"] != user_id:
            raise PermissionError("You can only delete your own messages")
        self.conn.execute(
            "UPDATE messages SET deleted_at=?, body='', attachment_id=NULL WHERE id=?",
            (now(), message_id),
        )
        self.conn.commit()
        return self.get_message(message_id)

    def clear_room(self, room_id: str) -> int:
        cursor = self.conn.execute("DELETE FROM messages WHERE room_id=?", (room_id,))
        self.conn.commit()
        return cursor.rowcount or 0

    def count_messages(self, room_id: str | None = None) -> int:
        if room_id:
            row = self.conn.execute(
                "SELECT COUNT(*) AS c FROM messages WHERE room_id=?", (room_id,)
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()
        return int(row["c"]) if row else 0

    def search_messages(
        self, query: str, room_ids: Iterable[str], limit: int = 50
    ) -> list[dict[str, Any]]:
        ids = [room_id for room_id in room_ids]
        if not ids or not query.strip():
            return []
        marks = ",".join("?" for _ in ids)
        rows = self.conn.execute(
            f"""
            SELECT * FROM messages
            WHERE room_id IN ({marks}) AND deleted_at IS NULL
              AND kind='text' AND body LIKE ? ESCAPE '\\'
            ORDER BY seq DESC LIMIT ?
            """,
            (*ids, f"%{query.strip()}%", max(1, min(100, limit))),
        ).fetchall()
        return [self._decorate(row) or {} for row in rows]

    # -------------------------------------------------------------- reactions
    def toggle_reaction(self, message_id: str, user_id: str, emoji: str) -> dict[str, Any]:
        existing = self.conn.execute(
            "SELECT 1 FROM reactions WHERE message_id=? AND user_id=? AND emoji=?",
            (message_id, user_id, emoji),
        ).fetchone()
        if existing:
            self.conn.execute(
                "DELETE FROM reactions WHERE message_id=? AND user_id=? AND emoji=?",
                (message_id, user_id, emoji),
            )
        else:
            self.conn.execute(
                "INSERT INTO reactions(message_id, user_id, emoji, created_at) VALUES(?,?,?,?)",
                (message_id, user_id, emoji, now()),
            )
        self.conn.commit()
        return self.reactions_for([message_id]).get(message_id, {})

    def reactions_for(self, message_ids: Iterable[str]) -> dict[str, dict[str, list[str]]]:
        ids = list(message_ids)
        if not ids:
            return {}
        marks = ",".join("?" for _ in ids)
        rows = self.conn.execute(
            f"SELECT message_id, emoji, user_id FROM reactions WHERE message_id IN ({marks})",
            ids,
        ).fetchall()
        result: dict[str, dict[str, list[str]]] = {}
        for row in rows:
            bucket = result.setdefault(row["message_id"], {})
            bucket.setdefault(row["emoji"], []).append(row["user_id"])
        return result

    # ------------------------------------------------------------ attachments
    def add_attachment(
        self,
        *,
        filename: str,
        mime: str,
        size: int,
        stored_name: str,
        uploader: str,
        attachment_id: str | None = None,
        sha256: str = "",
    ) -> dict[str, Any]:
        aid = attachment_id or new_id("a_")
        self.conn.execute(
            """
            INSERT INTO attachments(id, filename, mime, size, stored_name, uploader, sha256, created_at)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (aid, filename, mime, size, stored_name, uploader, sha256, now()),
        )
        self.conn.commit()
        return self.get_attachment(aid) or {}

    def get_attachment(self, attachment_id: str) -> dict[str, Any] | None:
        return self._row(
            self.conn.execute("SELECT * FROM attachments WHERE id=?", (attachment_id,)).fetchone()
        )

    # ---------------------------------------------------------------- invites
    def create_invite(
        self,
        room_id: str,
        created_by: str,
        *,
        ttl_seconds: int = 7 * 24 * 3600,
        max_uses: int = 50,
        password_hash: str = "",
    ) -> dict[str, Any]:
        code = secrets.token_urlsafe(9).replace("-", "x").replace("_", "y")[:12]
        stamp = now()
        self.conn.execute(
            """INSERT INTO invites(code, room_id, created_by, created_at, expires_at,
                                   password_hash, max_uses, uses)
               VALUES(?,?,?,?,?,?,?,0)""",
            (code, room_id, created_by, stamp, stamp + ttl_seconds, password_hash, max_uses),
        )
        self.conn.commit()
        return self.get_invite(code) or {}

    def get_invite(self, code: str) -> dict[str, Any] | None:
        return self._row(
            self.conn.execute("SELECT * FROM invites WHERE code=?", (code,)).fetchone()
        )

    def use_invite(self, code: str) -> dict[str, Any] | None:
        invite = self.get_invite(code)
        if not invite:
            return None
        if invite["expires_at"] < now() or invite["uses"] >= invite["max_uses"]:
            return None
        self.conn.execute("UPDATE invites SET uses=uses+1 WHERE code=?", (code,))
        self.conn.commit()
        return invite

    def prune_invites(self) -> None:
        self.conn.execute("DELETE FROM invites WHERE expires_at < ?", (now(),))
        self.conn.commit()

    # ------------------------------------------------------------------ stats
    def stats(self) -> dict[str, Any]:
        def scalar(query: str) -> int:
            row = self.conn.execute(query).fetchone()
            return int(row[0]) if row else 0

        return {
            "users": scalar("SELECT COUNT(*) FROM users"),
            "rooms": scalar("SELECT COUNT(*) FROM rooms"),
            "messages": scalar("SELECT COUNT(*) FROM messages WHERE deleted_at IS NULL"),
            "attachments": scalar("SELECT COUNT(*) FROM attachments"),
            "attachment_bytes": scalar("SELECT COALESCE(SUM(size), 0) FROM attachments"),
            "db_bytes": self.path.stat().st_size if self.path.exists() else 0,
        }

    def export_messages(self, room_id: str, limit: int = 5000) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE room_id=? ORDER BY seq DESC LIMIT ?",
            (room_id, limit),
        ).fetchall()
        return [self._decorate(row) or {} for row in reversed(rows)]

    def retention_purge(self, days: int) -> int:
        if days <= 0:
            return 0
        cutoff = now() - days * 86400
        cursor = self.conn.execute("DELETE FROM messages WHERE created_at < ?", (cutoff,))
        self.conn.commit()
        return cursor.rowcount or 0
