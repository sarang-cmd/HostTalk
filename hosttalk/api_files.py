"""Uploads, file delivery, and LocalSend endpoints."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from flask import Blueprint, g, jsonify, request, send_file

from .api_common import (
    fail,
    login_required,
    ok,
    public_attachment,
    serialize_message,
    services,
)
from .auth import RateLimiter
from .localsend import LocalSendError

bp = Blueprint("files", __name__)

MAX_FILENAME = 120
IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/avif"}
ALLOWED_MIME_PREFIXES = ("image/", "audio/", "video/", "text/")
ALLOWED_MIME = {
    "application/pdf",
    "application/zip",
    "application/x-7z-compressed",
    "application/x-rar-compressed",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/octet-stream",
    "application/gzip",
}
ALLOWED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif",
    ".pdf", ".txt", ".md", ".csv", ".doc", ".docx", ".xls", ".xlsx",
    ".ppt", ".pptx", ".zip", ".7z", ".rar", ".gz",
    ".mp3", ".wav", ".ogg", ".m4a", ".mp4", ".webm", ".mov",
}
BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".ps1", ".sh", ".msi", ".com", ".scr", ".js", ".html", ".htm", ".svg",
}

_localSend_sessions: dict[str, dict[str, Any]] = {}
_session_lock = threading.Lock()
SESSION_TTL = 600


def _upload_limiter() -> RateLimiter:
    svc = services()
    if svc.upload_limiter is None:
        svc.upload_limiter = RateLimiter(limit=12, window=60)
    return svc.upload_limiter


def clean_filename(raw: str) -> str:
    name = os.path.basename(str(raw or "")).replace("\x00", "").strip()
    name = re.sub(r"[\r\n\t]+", " ", name)
    name = name[:MAX_FILENAME].strip(" .")
    return name or "file"


def allowed_upload(filename: str, mime: str) -> tuple[bool, str]:
    suffix = Path(filename).suffix.lower()
    if suffix in BLOCKED_EXTENSIONS:
        return False, "That file type is not allowed"
    if suffix not in ALLOWED_EXTENSIONS:
        return False, "That file type is not on the allow list"
    if mime.startswith(ALLOWED_MIME_PREFIXES) or mime in ALLOWED_MIME:
        return True, ""
    return False, "That content type is not allowed"


@bp.post("/api/uploads")
@login_required
def upload():
    svc = services()
    user = g.user
    limiter = _upload_limiter()
    allowed, retry = limiter.check(user["id"])
    if not allowed:
        return fail("Too many uploads. Wait a minute.", 429, retry_after=retry)
    limiter.hit(user["id"])

    file = request.files.get("file")
    if not file or not file.filename:
        return fail("Choose a file first", 400, field="file")
    filename = clean_filename(file.filename)
    mime = (file.mimetype or "application/octet-stream").split(";")[0].strip()
    allowed_type, reason = allowed_upload(filename, mime)
    if not allowed_type:
        return fail(reason, 415, field="file")

    limit = svc.config.upload_limit_bytes
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size <= 0:
        return fail("That file is empty", 400, field="file")
    if size > limit:
        return fail(
            f"Files limit is {svc.config.values['max_upload_mb']} MB after compression",
            413,
            field="file",
            max_bytes=limit,
        )

    stored_name = f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
    target = svc.config.upload_dir / stored_name
    digest = hashlib.sha256()
    written = 0
    with target.open("wb") as handle:
        while True:
            chunk = file.stream.read(65536)
            if not chunk:
                break
            written += len(chunk)
            if written > limit:
                handle.close()
                target.unlink(missing_ok=True)
                return fail("That file is larger than the limit", 413, field="file")
            digest.update(chunk)
            handle.write(chunk)

    attachment = svc.store.add_attachment(
        filename=filename,
        mime=mime,
        size=written,
        stored_name=stored_name,
        uploader=user["id"],
        sha256=digest.hexdigest(),
    )
    svc.logger.info(
        "Upload: %s (%s bytes)", filename, written,
        extra={"event": "upload", "user": user["name"], "detail": filename, "count": written},
    )
    return ok(attachment=public_attachment(attachment))


@bp.get("/api/files/<attachment_id>")
@login_required
def serve_file(attachment_id: str):
    svc = services()
    attachment = svc.store.get_attachment(attachment_id)
    if not attachment:
        return fail("That file is gone", 404)
    path = svc.config.upload_dir / attachment["stored_name"]
    if not path.exists():
        return fail("That file is gone", 404)
    inline = attachment["mime"] in IMAGE_TYPES or attachment["mime"].startswith("audio/")
    response = send_file(
        path,
        mimetype=attachment["mime"],
        as_attachment=not inline,
        download_name=attachment["filename"],
        conditional=True,
    )
    response.headers["Cache-Control"] = "private, max-age=3600"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


# --------------------------------------------------------------------- LocalSend
@bp.get("/api/localsend/status")
@login_required
def localsend_status():
    svc = services()
    manager = svc.localsend
    return ok(
        enabled=bool(manager.enabled),
        alias=manager.alias,
        fingerprint=manager.fingerprint,
        protocol=manager.protocol,
        port=manager.port,
        last_error=manager.last_error,
        devices=manager.devices(),
        received=manager.received[:10],
    )


@bp.get("/api/localsend/devices")
@login_required
def localsend_devices():
    svc = services()
    return ok(devices=svc.localsend.devices(), enabled=bool(svc.localsend.enabled))


@bp.post("/api/localsend/scan")
@login_required
def localsend_scan():
    svc = services()
    data = request.get_json(silent=True) or {}
    try:
        devices = svc.localsend.scan(subnet_sweep=bool(data.get("subnet", True)))
    except LocalSendError as exc:
        return fail(str(exc), 409)
    return ok(devices=devices)


@bp.post("/api/localsend/send")
@login_required
def localsend_send():
    svc = services()
    data = request.get_json(silent=True) or {}
    fingerprint = str(data.get("fingerprint") or "")
    attachment_id = str(data.get("attachment_id") or "")
    attachment = svc.store.get_attachment(attachment_id)
    if not attachment:
        return fail("Choose a file that is already in this room", 404, field="attachment_id")
    path = svc.config.upload_dir / attachment["stored_name"]
    if not path.exists():
        return fail("That file is gone", 404)
    try:
        result = svc.localsend.send_file(
            fingerprint, path, attachment["filename"], attachment["mime"]
        )
    except LocalSendError as exc:
        return fail(str(exc), 502)
    return ok(result=result)


@bp.get("/api/localsend/v2/info")
def localsend_info():
    """LocalSend peers probe this without a HostTalk session."""
    svc = services()
    return jsonify(svc.localsend.info())


@bp.post("/api/localsend/v2/register")
def localsend_register():
    svc = services()
    return jsonify(svc.localsend.info())


@bp.post("/api/localsend/v2/prepare-upload")
def localsend_prepare_upload():
    svc = services()
    manager = svc.localsend
    if not manager.enabled:
        return jsonify({"message": "LocalSend is off"}), 403
    pin = request.args.get("pin") or request.headers.get("X-LocalSend-Pin", "")
    if not manager.check_pin(pin):
        return jsonify({"message": "PIN required"}), 401
    data = request.get_json(silent=True) or {}
    files = data.get("files") or {}
    if not isinstance(files, dict) or not files:
        return jsonify({"message": "No files in request"}), 400
    session_id = secrets.token_urlsafe(12)
    tokens: dict[str, str] = {}
    accepted: dict[str, dict[str, Any]] = {}
    limit = svc.config.upload_limit_bytes
    for file_id, info in list(files.items())[:20]:
        if not isinstance(info, dict):
            continue
        size = int(info.get("size") or 0)
        name = clean_filename(info.get("fileName") or f"file-{file_id}")
        if size <= 0 or size > limit:
            continue
        suffix = Path(name).suffix.lower()
        if suffix in BLOCKED_EXTENSIONS or suffix not in ALLOWED_EXTENSIONS:
            continue
        token = secrets.token_urlsafe(16)
        tokens[str(file_id)] = token
        accepted[str(file_id)] = {
            "filename": name,
            "size": size,
            "mime": str(info.get("fileType") or "application/octet-stream")[:100],
            "token": token,
            "sender": str((data.get("info") or {}).get("alias") or "LocalSend")[:64],
        }
    if not tokens:
        return jsonify({"message": "No accepted files"}), 403
    with _session_lock:
        _cleanup_sessions()
        _localSend_sessions[session_id] = {"files": accepted, "created": time.time()}
    return jsonify({"sessionId": session_id, "fileTokens": tokens})


@bp.post("/api/localsend/v2/upload")
def localsend_upload():
    svc = services()
    manager = svc.localsend
    if not manager.enabled:
        return jsonify({"message": "LocalSend is off"}), 403
    pin = request.args.get("pin") or request.headers.get("X-LocalSend-Pin", "")
    if not manager.check_pin(pin):
        return jsonify({"message": "PIN required"}), 401
    session_id = request.args.get("sessionId", "")
    file_id = request.args.get("fileId", "")
    token = request.args.get("token", "")
    with _session_lock:
        session = _localSend_sessions.get(session_id)
    if not session:
        return jsonify({"message": "Unknown session"}), 404
    entry = session["files"].get(file_id)
    if not entry or not secrets.compare_digest(entry["token"], token):
        return jsonify({"message": "Bad token"}), 403

    stored_name = f"{uuid.uuid4().hex}{Path(entry['filename']).suffix.lower()}"
    target = svc.config.upload_dir / stored_name
    digest = hashlib.sha256()
    written = 0
    limit = svc.config.upload_limit_bytes
    with target.open("wb") as handle:
        while True:
            chunk = request.stream.read(65536)
            if not chunk:
                break
            written += len(chunk)
            if written > limit:
                handle.close()
                target.unlink(missing_ok=True)
                return jsonify({"message": "File too large"}), 413
            digest.update(chunk)
            handle.write(chunk)

    attachment = svc.store.add_attachment(
        filename=entry["filename"],
        mime=entry["mime"],
        size=written,
        stored_name=stored_name,
        uploader="localsend",
        sha256=digest.hexdigest(),
    )
    system_user = svc.store.get_user_by_name("LocalSend") or svc.store.get_or_create_user(
        "LocalSend", device_key="localsend"
    )
    message = svc.store.add_message(
        "main",
        system_user["id"],
        "LocalSend",
        f"Received {entry['filename']} from {entry['sender']}",
        kind="image" if entry["mime"].startswith("image/") else "file",
        attachment_id=attachment["id"],
        meta={"source": "localsend", "sender": entry["sender"]},
    )
    svc.broker.publish(["main"], "message.created", {"message": serialize_message(message, svc), "room_id": "main"})
    manager.record_received(
        {
            "filename": entry["filename"],
            "alias": entry["sender"],
            "size": written,
            "at": time.time(),
        }
    )
    with _session_lock:
        session["files"].pop(file_id, None)
    return jsonify({"ok": True})


@bp.post("/api/localsend/v2/cancel")
def localsend_cancel():
    session_id = request.args.get("sessionId", "")
    with _session_lock:
        _localSend_sessions.pop(session_id, None)
    return jsonify({"ok": True})


def _cleanup_sessions() -> None:
    cutoff = time.time() - SESSION_TTL
    for key in [key for key, value in _localSend_sessions.items() if value["created"] < cutoff]:
        _localSend_sessions.pop(key, None)
