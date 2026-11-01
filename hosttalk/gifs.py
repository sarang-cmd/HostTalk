"""GIF search through a server-side KLIPY proxy."""

from __future__ import annotations

import threading
import time
from typing import Any

import requests

BASE_URL = "https://api.klipy.com/api/v1/{key}/gifs"
TIMEOUT = 6.0
CACHE_TTL = 300
CACHE_LIMIT = 60
PER_PAGE = 24


class GifError(RuntimeError):
    """Search failed. The status tells the console whether to blame setup."""

    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


class GifService:
    """Keeps the KLIPY key on the host and caches results for the room."""

    def __init__(self, api_key: str, *, enabled: bool = True):
        self.api_key = api_key.strip()
        self.enabled = enabled
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str) -> list[dict[str, Any]]:
        if not self.enabled:
            raise GifError("GIF search is turned off in the host console", 409)
        if not self.api_key:
            raise GifError("Add a KLIPY API key in the host console to search GIFs", 409)
        query = " ".join((query or "").split())[:60]
        key = query.lower() or "__trending__"
        cached = self._cached(key)
        if cached is not None:
            return cached
        path = "search" if query else "trending"
        params: dict[str, Any] = {
            "per_page": PER_PAGE,
            "page": 1,
            "content_filter": "medium",
        }
        if query:
            params["q"] = query
        try:
            response = requests.get(
                f"{BASE_URL.format(key=self.api_key)}/{path}",
                params=params,
                timeout=TIMEOUT,
                headers={"Accept": "application/json"},
            )
            if response.status_code in {401, 403}:
                raise GifError("KLIPY rejected the API key")
            if response.status_code == 429:
                raise GifError("KLIPY rate limit reached. Try again in a minute.")
            if response.status_code >= 400:
                raise GifError("KLIPY is not answering right now")
            payload = response.json()
        except requests.RequestException as exc:
            raise GifError("No internet route to KLIPY") from exc
        except ValueError as exc:
            raise GifError("KLIPY sent an unexpected reply") from exc

        gifs = _parse(payload)
        self._store(key, gifs)
        return gifs

    def _cached(self, key: str) -> list[dict[str, Any]] | None:
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            stamp, value = entry
            if time.time() - stamp > CACHE_TTL:
                self._cache.pop(key, None)
                return None
            return value

    def _store(self, key: str, value: list[dict[str, Any]]) -> None:
        with self._lock:
            if len(self._cache) >= CACHE_LIMIT:
                self._cache.clear()
            self._cache[key] = (time.time(), value)


def _parse(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """KLIPY returns two levels of data, then a file set per size."""
    body = payload.get("data") if isinstance(payload, dict) else None
    items = body.get("data") if isinstance(body, dict) else None
    if not isinstance(items, list):
        return []
    gifs: list[dict[str, Any]] = []
    for item in items[:PER_PAGE]:
        if not isinstance(item, dict):
            continue
        files = item.get("file") or {}
        full = _url(files, "md", "gif") or _url(files, "hd", "gif") or _url(files, "sm", "gif")
        preview = (
            _url(files, "sm", "webp")
            or _url(files, "xs", "webp")
            or _url(files, "sm", "gif")
            or full
        )
        if not full or not preview:
            continue
        gifs.append(
            {
                "id": str(item.get("slug") or item.get("id") or "")[:64],
                "title": str(item.get("title") or "GIF")[:80],
                "preview": preview,
                "url": full,
                "width": _int(_size(files, "md", "gif").get("width")),
                "height": _int(_size(files, "md", "gif").get("height")),
            }
        )
    return gifs


def _size(files: Any, size: str, fmt: str) -> dict[str, Any]:
    if not isinstance(files, dict):
        return {}
    bucket = files.get(size)
    if not isinstance(bucket, dict):
        return {}
    entry = bucket.get(fmt)
    return entry if isinstance(entry, dict) else {}


def _url(files: Any, size: str, fmt: str) -> str:
    value = _size(files, size, fmt).get("url")
    if not isinstance(value, str):
        return ""
    # Media loads straight from KLIPY. Nothing is copied to this server.
    return value if value.startswith("https://") else ""


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
