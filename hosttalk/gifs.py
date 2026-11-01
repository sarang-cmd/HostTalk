"""GIF search through a server-side GIPHY proxy."""

from __future__ import annotations

import threading
import time
from typing import Any

import requests

SEARCH_URL = "https://api.giphy.com/v1/gifs/search"
TRENDING_URL = "https://api.giphy.com/v1/gifs/trending"
TIMEOUT = 6.0
CACHE_TTL = 300
CACHE_LIMIT = 60


class GifError(RuntimeError):
    """Search failed. The status tells the console whether to blame setup."""

    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


class GifService:
    """Keeps the API key on the host and caches results for the room."""

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
            raise GifError("Add a GIPHY API key in the host console to search GIFs", 409)
        query = " ".join((query or "").split())[:60]
        key = query.lower() or "__trending__"
        cached = self._cached(key)
        if cached is not None:
            return cached
        url = SEARCH_URL if query else TRENDING_URL
        params = {"api_key": self.api_key, "limit": 24, "rating": "pg-13"}
        if query:
            params["q"] = query
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT)
            if response.status_code == 401:
                raise GifError("GIPHY rejected the API key")
            if response.status_code >= 400:
                raise GifError("GIPHY is not answering right now")
            payload = response.json()
        except requests.RequestException as exc:
            raise GifError("No internet route to GIPHY") from exc
        except ValueError as exc:
            raise GifError("GIPHY sent an unexpected reply") from exc

        gifs = []
        for item in payload.get("data", [])[:24]:
            images = item.get("images", {})
            preview = images.get("fixed_width_small", {}).get("url") or images.get(
                "fixed_width", {}
            ).get("url")
            full = images.get("fixed_width", {}).get("url") or (item.get("url") or "")
            if not preview or not full:
                continue
            gifs.append(
                {
                    "id": str(item.get("id", ""))[:32],
                    "title": str(item.get("title", "GIF"))[:80],
                    "preview": preview,
                    "url": full,
                    "width": _int(images.get("fixed_width", {}).get("width")),
                    "height": _int(images.get("fixed_width", {}).get("height")),
                }
            )
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


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
