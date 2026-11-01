"""Health checks shown in the host console and printed by the CLI doctor."""

from __future__ import annotations

import os
import shutil
import socket
import tempfile
import time

from .netinfo import lan_ip, local_addresses, wifi_name
from .services import Services


def _result(check_id: str, label: str, status: str, detail: str, fix: str = "") -> dict[str, str]:
    return {"id": check_id, "label": label, "status": status, "detail": detail, "fix": fix}


def run_checks(services: Services) -> list[dict[str, str]]:
    config = services.config
    results: list[dict[str, str]] = []

    results.append(
        _result(
            "password",
            "Room password",
            "ok" if config.values["password_hash"] else "fail",
            "Set" if config.values["password_hash"] else "Anyone on the network can join",
            "Set a password in the host console",
        )
    )

    try:
        config.data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=config.data_dir, delete=True) as handle:
            handle.write(b"hosttalk")
        results.append(_result("data", "Data folder", "ok", str(config.data_dir)))
    except OSError as exc:
        results.append(
            _result("data", "Data folder", "fail", str(exc), "Check folder permissions")
        )

    try:
        usage = shutil.disk_usage(config.data_dir)
        free_gb = usage.free / (1024 ** 3)
        results.append(
            _result(
                "disk",
                "Free space",
                "ok" if free_gb >= 1 else "warn",
                f"{free_gb:.1f} GB free",
                "Free up space for uploads",
            )
        )
    except OSError as exc:
        results.append(_result("disk", "Free space", "warn", str(exc)))

    try:
        with socket.create_connection(("127.0.0.1", config.port), timeout=1.0):
            results.append(
                _result("port", "Server port", "ok", f"Listening on {config.port}")
            )
    except OSError:
        results.append(
            _result(
                "port",
                "Server port",
                "warn",
                f"Nothing answered on {config.port}",
                "Start the server or change the port in settings",
            )
        )

    address = lan_ip()
    if address.startswith("127."):
        results.append(
            _result(
                "lan",
                "Network address",
                "warn",
                "No LAN address found",
                "Connect the host to Wi-Fi or Ethernet",
            )
        )
    else:
        results.append(
            _result(
                "lan",
                "Network address",
                "ok",
                f"{address} ({len(local_addresses())} interface{'s' if len(local_addresses()) != 1 else ''})",
            )
        )

    ssid = wifi_name()
    results.append(
        _result(
            "wifi",
            "Wi-Fi name",
            "ok" if ssid else "warn",
            ssid or "Not detected. Guests still join by address.",
        )
    )

    results.append(
        _result(
            "previews",
            "Link previews",
            "ok" if config.previews_enabled else "warn",
            "On" if config.previews_enabled else "Off",
        )
    )
    results.append(
        _result(
            "gifs",
            "GIF search",
            "ok" if config.klipy_key else "warn",
            "Ready" if config.klipy_key else "Add a KLIPY key to enable search",
            "Get a key at partner.klipy.com",
        )
    )
    manager = services.localsend
    if manager.enabled:
        detail = manager.last_error or f"{len(manager.devices())} device(s) seen"
        results.append(
            _result(
                "localsend",
                "LocalSend",
                "warn" if manager.last_error else "ok",
                detail,
                "Check that multicast is allowed on this network",
            )
        )
    else:
        results.append(_result("localsend", "LocalSend", "warn", "Off"))

    results.append(
        _result(
            "console",
            "Host console access",
            "ok",
            "This machine only"
            if config.values["console_local_only"]
            else "Open to the network with the password",
        )
    )
    results.append(
        _result("clock", "Server clock", "ok", time.strftime("%Y-%m-%d %H:%M:%S %Z"))
    )

    if os.name == "nt":
        results.append(
            _result(
                "firewall",
                "Windows firewall",
                "warn",
                f"Allow Python or the HostTalk app on port {config.port}",
                "Windows Security, Firewall, Allow an app",
            )
        )
    return results


def overall(checks: list[dict[str, str]]) -> str:
    if any(check["status"] == "fail" for check in checks):
        return "fail"
    if any(check["status"] == "warn" for check in checks):
        return "warn"
    return "ok"
