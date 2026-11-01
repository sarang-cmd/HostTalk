"""Logging configuration and log reading for the host console."""

from __future__ import annotations

import json
import logging
import logging.handlers
import time
from pathlib import Path
from typing import Any, Iterator

LOG_FILENAME = "hosttalk.jsonl"
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 3
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class JsonLineFormatter(logging.Formatter):
    """Write one JSON object per line so the console can filter safely."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": round(record.created, 3),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        event = getattr(record, "event", None)
        if event:
            payload["event"] = event
        for key in ("user", "room", "ip", "detail", "count"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["traceback"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(log_dir: Path, level: str = "INFO") -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("hosttalk")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.propagate = False

    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / LOG_FILENAME,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(JsonLineFormatter())
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
    root.addHandler(console)
    return root


def log(logger: logging.Logger, event: str, message: str, **fields: Any) -> None:
    level = fields.pop("level", logging.INFO)
    logger.log(level, message, extra={"event": event, **fields})


def read_logs(log_dir: Path, *, level: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    """Return the newest log records, newest last."""
    path = log_dir / LOG_FILENAME
    if not path.exists():
        return []
    threshold = levels_at_or_above(level)
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if threshold and levels_at_or_above(record.get("level")) < threshold:
                continue
            rows.append(record)
    return rows[-max(1, min(limit, 2000)):]


def levels_at_or_above(level: str | None) -> int:
    if not level:
        return 0
    try:
        return getattr(logging, str(level).upper())
    except AttributeError:
        return 0


def iter_log_files(log_dir: Path) -> Iterator[Path]:
    for path in sorted(log_dir.glob("hosttalk.jsonl*")):
        if path.is_file():
            yield path


def log_stats(log_dir: Path) -> dict[str, Any]:
    total = sum(path.stat().st_size for path in iter_log_files(log_dir))
    newest = log_dir / LOG_FILENAME
    return {
        "bytes": total,
        "updated_at": newest.stat().st_mtime if newest.exists() else None,
        "now": time.time(),
    }
