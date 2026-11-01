"""Who is here right now."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from .auth import COLOR_GRID, assign_color
from .store import Store


@dataclass
class Person:
    user_id: str
    name: str
    color: str
    avatar_seed: str
    role: str = "member"
    avatar_file: str = ""
    avatar_updated: float = 0.0
    badge_icon: str = ""
    badge_text: str = ""
    connections: int = 0
    last_seen: float = field(default_factory=time.time)
    rooms: set[str] = field(default_factory=set)


class Presence:
    """Tracks live connections and hands out free colors."""

    def __init__(self, store: Store):
        self.store = store
        self._people: dict[str, Person] = {}
        self._lock = threading.RLock()

    def connect(self, user: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            person = self._people.get(user["id"])
            active = {entry.color for entry in self._people.values() if entry.user_id != user["id"]}
            if person is None:
                color = assign_color(self.store, user, active)
                person = Person(
                    user_id=user["id"],
                    name=user["name"],
                    color=color,
                    avatar_seed=user.get("avatar_seed") or user["id"][:8],
                    role=user.get("role") or "member",
                    avatar_file=user.get("avatar_file") or "",
                    avatar_updated=float(user.get("avatar_updated") or 0),
                    badge_icon=user.get("badge_icon") or "",
                    badge_text=user.get("badge_text") or "",
                )
                self._people[user["id"]] = person
            person.connections += 1
            person.last_seen = time.time()
            person.name = user["name"]
            person.role = user.get("role") or person.role
            person.avatar_file = user.get("avatar_file") or ""
            person.avatar_updated = float(user.get("avatar_updated") or 0)
            person.badge_icon = user.get("badge_icon") or ""
            person.badge_text = user.get("badge_text") or ""
            return self._public(person)

    def disconnect(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            person = self._people.get(user_id)
            if not person:
                return None
            person.connections = max(0, person.connections - 1)
            person.last_seen = time.time()
            if person.connections == 0:
                self._people.pop(user_id, None)
                return None
            return self._public(person)

    def touch(self, user_id: str) -> None:
        with self._lock:
            person = self._people.get(user_id)
            if person:
                person.last_seen = time.time()

    def rename(self, user_id: str, name: str) -> None:
        with self._lock:
            person = self._people.get(user_id)
            if person:
                person.name = name

    def set_color(self, user_id: str, color: str) -> None:
        with self._lock:
            person = self._people.get(user_id)
            if person:
                person.color = color

    def set_role(self, user_id: str, role: str) -> None:
        with self._lock:
            person = self._people.get(user_id)
            if person:
                person.role = role

    def set_badge(self, user_id: str, icon: str, text: str) -> None:
        with self._lock:
            person = self._people.get(user_id)
            if person:
                person.badge_icon = icon
                person.badge_text = text

    def set_avatar(self, user_id: str, filename: str, updated: float) -> None:
        with self._lock:
            person = self._people.get(user_id)
            if person:
                person.avatar_file = filename
                person.avatar_updated = updated

    def set_rooms(self, user_id: str, rooms: set[str]) -> None:
        with self._lock:
            person = self._people.get(user_id)
            if person:
                person.rooms = set(rooms)

    def get(self, user_id: str) -> Person | None:
        with self._lock:
            return self._people.get(user_id)

    def active_colors(self) -> set[str]:
        with self._lock:
            return {person.color for person in self._people.values()}

    def online(self, user_id: str) -> bool:
        with self._lock:
            return user_id in self._people

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            people = sorted(self._people.values(), key=lambda person: person.name.lower())
            return [self._public(person) for person in people]

    def count(self) -> int:
        with self._lock:
            return len(self._people)

    @staticmethod
    def _public(person: Person) -> dict[str, Any]:
        return {
            "id": person.user_id,
            "name": person.name,
            "color": person.color,
            "avatar_seed": person.avatar_seed,
            "avatar_url": (
                f"/api/avatars/{person.user_id}?v={int(person.avatar_updated)}"
                if person.avatar_file
                else ""
            ),
            "role": person.role,
            "badge_icon": person.badge_icon,
            "badge_text": person.badge_text,
            "online": True,
            "rooms": sorted(person.rooms),
        }

    @staticmethod
    def palette() -> list[str]:
        return list(COLOR_GRID)
