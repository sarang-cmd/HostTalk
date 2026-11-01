"""Network discovery helpers: LAN address, Wi-Fi name, invite URL."""

from __future__ import annotations

import ipaddress
import platform
import socket
import subprocess
from typing import Any
from urllib.parse import urlsplit


def _run(command: list[str], timeout: float = 2.0) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (result.stdout or "").strip()


def lan_ip() -> str:
    """Return the address other devices on the network use to reach this host."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 9))  # Documentation range, no packets sent.
        address = sock.getsockname()[0]
    except OSError:
        address = ""
    finally:
        sock.close()
    if address and not address.startswith("127."):
        return address
    return local_addresses()[0] if local_addresses() else "127.0.0.1"


def local_addresses() -> list[str]:
    addresses: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.add(info[4][0])
    except OSError:
        pass
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("192.0.2.1", 9))
        addresses.add(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    return sorted(address for address in addresses if not address.startswith("127."))


def wifi_name() -> str:
    system = platform.system()
    if system == "Windows":
        raw = _run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-NetConnectionProfile | Where-Object {$_.InterfaceAlias -like '*Wi-Fi*'}).Name",
            ]
        )
        return raw.splitlines()[0] if raw else ""
    if system == "Linux":
        name = _run(["iwgetid", "-r"])
        if name:
            return name
        name = _run(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"])
        for line in name.splitlines():
            if line.startswith("yes:"):
                return line.split(":", 1)[1]
        return ""
    if system == "Darwin":
        raw = _run(
            [
                "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",
                "-I",
            ]
        )
        for line in raw.splitlines():
            if line.strip().startswith("SSID:"):
                return line.split(":", 1)[1].strip()
    return ""


def is_loopback(value: str | None) -> bool:
    if not value:
        return False
    candidate = value.strip()
    if candidate in {"localhost", "::1"}:
        return True
    if candidate.startswith("::ffff:"):
        candidate = candidate[7:]
    try:
        return ipaddress.ip_address(candidate).is_loopback
    except ValueError:
        return False


def host_from_request(headers: dict[str, str], fallback: str = "") -> str:
    """Resolve the host header to a reachable address for invite links."""
    raw = (headers.get("X-Forwarded-Host") or headers.get("Host") or "").split(",")[0].strip()
    if not raw:
        return fallback
    parsed = urlsplit("//" + raw)
    return parsed.hostname or fallback


def invite_address(host: str, port: int, lan: str | None = None) -> str:
    host = (host or "").strip()
    if host in {"", "localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        host = lan or lan_ip()
    return f"http://{host}:{port}"


def network_summary(headers: dict[str, str] | None = None, port: int | None = None) -> dict[str, Any]:
    headers = headers or {}
    lan = lan_ip()
    resolved_port = port or 7284
    address = invite_address(host_from_request(headers, lan), resolved_port, lan)
    return {
        "lan_ip": lan,
        "ssid": wifi_name(),
        "port": resolved_port,
        "address": address,
        "hostname": socket.gethostname(),
        "platform": platform.system(),
    }
