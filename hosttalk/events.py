"""Server-sent events hub for messages, presence, and typing."""

from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

DEFAULT_QUEUE_SIZE = 200


@dataclass
class Subscriber:
    id: str
    user_id: str
    rooms: set[str] = field(default_factory=set)
    queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=DEFAULT_QUEUE_SIZE))
    created_at: float = field(default_factory=time.time)

    def send(self, event: str, data: dict[str, Any]) -> bool:
        try:
            self.queue.put_nowait((event, data))
            return True
        except queue.Full:
            return False


class Broker:
    """Fan-out hub. One queue per connected browser tab."""

    def __init__(self) -> None:
        self._subscribers: dict[str, Subscriber] = {}
        self._lock = threading.RLock()
        self._counter = 0

    def subscribe(self, user_id: str, rooms: Iterable[str]) -> Subscriber:
        with self._lock:
            self._counter += 1
            subscriber = Subscriber(
                id=f"s{self._counter}",
                user_id=user_id,
                rooms=set(rooms),
            )
            self._subscribers[subscriber.id] = subscriber
            return subscriber

    def unsubscribe(self, subscriber: Subscriber) -> None:
        with self._lock:
            self._subscribers.pop(subscriber.id, None)

    def subscribe_rooms(self, user_id: str, rooms: Iterable[str]) -> None:
        with self._lock:
            for subscriber in self._subscribers.values():
                if subscriber.user_id == user_id:
                    subscriber.rooms |= set(rooms)

    def set_rooms(self, user_id: str, rooms: Iterable[str]) -> None:
        with self._lock:
            for subscriber in self._subscribers.values():
                if subscriber.user_id == user_id:
                    subscriber.rooms = set(rooms)

    def publish(
        self,
        rooms: Iterable[str],
        event: str,
        data: dict[str, Any],
        *,
        exclude_user: str = "",
    ) -> int:
        targets = set(rooms)
        delivered = 0
        with self._lock:
            subscribers = list(self._subscribers.values())
        for subscriber in subscribers:
            if exclude_user and subscriber.user_id == exclude_user:
                continue
            if targets & subscriber.rooms and subscriber.send(event, data):
                delivered += 1
        return delivered

    def broadcast(self, event: str, data: dict[str, Any], *, exclude_user: str = "") -> int:
        delivered = 0
        with self._lock:
            subscribers = list(self._subscribers.values())
        for subscriber in subscribers:
            if exclude_user and subscriber.user_id == exclude_user:
                continue
            if subscriber.send(event, data):
                delivered += 1
        return delivered

    def user_connections(self, user_id: str) -> list[Subscriber]:
        with self._lock:
            return [sub for sub in self._subscribers.values() if sub.user_id == user_id]

    def count(self) -> int:
        with self._lock:
            return len(self._subscribers)


def format_event(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


HEARTBEAT = ": ping\n\n"
