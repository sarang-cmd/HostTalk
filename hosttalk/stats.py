"""Measurements for the project stats page.

Two sets of numbers. The source tree on this disk, and the rows in this
instance. Both are counted here, on the host. Nothing is sent anywhere.
"""

from __future__ import annotations

import functools
import platform
import sqlite3
import time
from importlib import metadata
from pathlib import Path
from typing import Any

from .config import project_root
from .version import CODENAME, SCHEMA_VERSION, __version__

# Areas counted for the code table. A target is a folder or a single file.
# Suffixes narrow the count. None counts every file in the folder.
AREAS: tuple[tuple[str, tuple[str, ...], tuple[str, ...] | None], ...] = (
    ("Server package", ("hosttalk",), (".py",)),
    ("Room scripts", ("static/js",), (".js",)),
    ("Styles", ("static/css",), (".css",)),
    ("Templates", ("templates",), (".html",)),
    ("Tests", ("tests",), (".py",)),
    ("Deployment", ("deploy",), None),
    ("Docs", ("README.md", "SETUP_GUIDE.md", "docs"), (".md",)),
)

BYTE_UNITS = ("B", "KB", "MB", "GB", "TB")


def human_bytes(value: int | float) -> str:
    """Render a byte count with one decimal above the byte range."""
    size = max(0.0, float(value or 0))
    for unit in BYTE_UNITS:
        if size < 1024 or unit == BYTE_UNITS[-1]:
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return "0 B"


def human_duration(seconds: int | float) -> str:
    """Render an uptime as two units at most."""
    total = max(0, int(seconds or 0))
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    if days:
        return f"{days} d {hours} h"
    if hours:
        return f"{hours} h {minutes} m"
    if minutes:
        return f"{minutes} m {secs} s"
    return f"{secs} s"


def _collect(root: Path, targets: tuple[str, ...], suffixes: tuple[str, ...] | None) -> list[Path]:
    found: list[Path] = []
    for target in targets:
        base = root / target
        if base.is_file():
            if suffixes is None or base.suffix in suffixes:
                found.append(base)
            continue
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if suffixes is None or path.suffix in suffixes:
                found.append(path)
    return found


def _lines(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    except OSError:
        return 0


@functools.lru_cache(maxsize=4)
def _source_stats(root_key: str) -> dict[str, Any]:
    root = Path(root_key)
    areas: list[dict[str, Any]] = []
    for name, targets, suffixes in AREAS:
        files = _collect(root, targets, suffixes)
        areas.append(
            {
                "name": name,
                "files": len(files),
                "lines": sum(_lines(path) for path in files),
            }
        )
    total_lines = sum(area["lines"] for area in areas) or 1
    for area in areas:
        area["share"] = round(area["lines"] * 100 / total_lines, 1)

    tests = _collect(root, ("tests",), (".py",))
    test_cases = 0
    for path in tests:
        text = path.read_text(encoding="utf-8", errors="ignore")
        test_cases += sum(1 for line in text.splitlines() if line.lstrip().startswith("def test_"))

    requirements = root / "requirements.txt"
    packages = 0
    if requirements.is_file():
        packages = sum(
            1
            for line in requirements.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )

    shots = _collect(root, ("static/screenshots",), (".png",))
    screenshots = [path for path in shots if not path.name.startswith("demo-")]

    vendored = []
    for path in sorted((root / "static" / "lib").glob("*")):
        if path.is_file() and not path.name.startswith("."):
            vendored.append(
                {
                    "name": path.name,
                    "bytes": path.stat().st_size,
                    "note": "0.8.2" if path.name.startswith("fflate") else "",
                }
            )

    return {
        "areas": areas,
        "totals": {
            "files": sum(area["files"] for area in areas),
            "lines": sum(area["lines"] for area in areas),
        },
        "test_cases": test_cases,
        "test_files": len(tests),
        "screenshots": len(screenshots),
        "packages": packages,
        "vendored": vendored,
    }


def source_stats() -> dict[str, Any]:
    """Line and file counts for this install. Cached for the process."""
    return _source_stats(str(project_root()))


def _package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "not installed"


def runtime_stats() -> dict[str, Any]:
    """Versions of the pieces under the app."""
    return {
        "version": __version__,
        "codename": CODENAME,
        "schema": SCHEMA_VERSION,
        "python": platform.python_version(),
        "flask": _package_version("flask"),
        "waitress": _package_version("waitress"),
        "sqlite": sqlite3.sqlite_version,
        "platform": platform.system(),
        "machine": platform.machine(),
    }


def _tree_bytes(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    total = 0
    for path in folder.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def instance_stats(services: Any) -> dict[str, Any]:
    """Live figures from the store, the presence table, and the data folder."""
    stored = services.store.stats()
    data_dir: Path = services.config.data_dir
    uploads = _tree_bytes(data_dir / "uploads")
    logs = _tree_bytes(data_dir / "logs")
    return {
        "online": services.presence.count(),
        "people": stored["users"],
        "rooms": stored["rooms"],
        "messages": stored["messages"],
        "attachments": stored["attachments"],
        "attachment_bytes": stored["attachment_bytes"],
        "db_bytes": stored["db_bytes"],
        "upload_bytes": uploads,
        "log_bytes": logs,
        "disk_bytes": stored["db_bytes"] + uploads + logs,
        "uptime": int(time.time() - services.started_at),
        "port": services.config.port,
        "counted_at": time.strftime("%Y-%m-%d %H:%M"),
    }
