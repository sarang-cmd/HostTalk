"""Link previews with a guard against requests to private networks."""

from __future__ import annotations

import ipaddress
import socket
import threading
import time
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

MAX_BYTES = 262_144
TIMEOUT = 6.0
CACHE_TTL = 900
CACHE_LIMIT = 200
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 HostTalkPreview/2.0"
)


class PreviewError(RuntimeError):
    pass


def _resolved_ips(hostname: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError as exc:
        raise PreviewError("That address did not resolve") from exc
    addresses = []
    for info in infos:
        value = info[4][0]
        if value not in addresses:
            addresses.append(value)
    return addresses


def is_public_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.split("%")[0])
    except ValueError:
        return False
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def validate_url(raw: str) -> str:
    text = (raw or "").strip()
    if len(text) > 2048:
        raise PreviewError("That link is too long")
    parts = urlsplit(text)
    if parts.scheme not in {"http", "https"}:
        raise PreviewError("Only http and https links get previews")
    if not parts.hostname:
        raise PreviewError("That link has no host")
    host = parts.hostname
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise PreviewError("Links to this network stay private")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal and not is_public_ip(str(literal)):
        raise PreviewError("Links to this network stay private")
    return text


def _fetch(url: str, depth: int = 0) -> tuple[str, str]:
    if depth > 3:
        raise PreviewError("Too many redirects")
    if not is_public_ip(
        _resolved_ips(urlsplit(url).hostname or "")[0]
    ):
        raise PreviewError("Links to this network stay private")
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        timeout=TIMEOUT,
        stream=True,
        allow_redirects=False,
    )
    try:
        if response.is_redirect:
            target = urljoin(url, response.headers.get("Location", ""))
            validate_url(target)
            return _fetch(target, depth + 1)
        if response.status_code >= 400:
            raise PreviewError(f"The site answered {response.status_code}")
        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type.lower():
            raise PreviewError("That link is not a web page")
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(16384):
            chunks.append(chunk)
            total += len(chunk)
            if total >= MAX_BYTES:
                break
        charset = response.encoding or "utf-8"
        return b"".join(chunks).decode(charset, errors="replace"), response.url
    finally:
        response.close()


def _meta(soup: BeautifulSoup, *, prop: str = "", name: str = "") -> str:
    tag = None
    if prop:
        tag = soup.find("meta", attrs={"property": prop})
    if tag is None and name:
        tag = soup.find("meta", attrs={"name": name})
    if tag and tag.get("content"):
        return str(tag["content"]).strip()
    return ""


def parse_preview(url: str) -> dict[str, Any]:
    html, final_url = _fetch(url)
    soup = BeautifulSoup(html, "html.parser")
    title = _meta(soup, prop="og:title", name="twitter:title")
    if not title and soup.title and soup.title.string:
        title = str(soup.title.string).strip()
    description = _meta(soup, prop="og:description", name="description")
    image = _meta(soup, prop="og:image", name="twitter:image")
    site = _meta(soup, prop="og:site_name")
    if image:
        image = urljoin(final_url, image)
    host = urlsplit(final_url).hostname or ""
    return {
        "url": url,
        "title": (title or host)[:180],
        "description": description[:280],
        "image": image[:2048],
        "site": site[:80] or host,
    }


class PreviewCache:
    def __init__(self) -> None:
        self._items: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def get(self, url: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._items.get(url)
            if not entry:
                return None
            stamp, payload = entry
            if time.time() - stamp > CACHE_TTL:
                self._items.pop(url, None)
                return None
            return payload

    def put(self, url: str, payload: dict[str, Any]) -> None:
        with self._lock:
            if len(self._items) >= CACHE_LIMIT:
                oldest = sorted(self._items.items(), key=lambda item: item[1][0])[:20]
                for key, _ in oldest:
                    self._items.pop(key, None)
            self._items[url] = (time.time(), payload)

    def size(self) -> int:
        with self._lock:
            return len(self._items)
