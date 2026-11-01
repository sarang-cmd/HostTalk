"""Uploads, file delivery, and LocalSend endpoints."""

from __future__ import annotations

import contextlib
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
    public_person,
    serialize_message,
    services,
    session_user,
)
from .auth import MAX_AVATAR_BYTES, RateLimiter, host_session
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

AVATAR_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
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


def image_suffix(data: bytes) -> str:
    """Trust the bytes, not the filename the browser sent."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[4:8] == b"ftyp" and data[8:12] in {b"avif", b"avis"}:
        return ".avif"
    return ""


def _avatar_dir():
    folder = services().config.upload_dir / "avatars"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _drop_avatar_file(filename: str) -> None:
    if not filename:
        return
    path = _avatar_dir() / os.path.basename(filename)
    with contextlib.suppress(OSError):
        path.unlink(missing_ok=True)


@bp.post("/api/me/avatar")
@login_required
def upload_avatar():
    svc = services()
    user = g.user
    file = request.files.get("avatar") or request.files.get("file")
    if not file or not file.filename:
        return fail("Choose a picture first", 400, field="avatar")
    data = file.stream.read(MAX_AVATAR_BYTES + 1)
    if not data:
        return fail("That picture is empty", 400, field="avatar")
    if len(data) > MAX_AVATAR_BYTES:
        return fail("Pictures limit is 3 MB", 413, field="avatar")
    suffix = image_suffix(data)
    if not suffix:
        return fail("Use a PNG, JPEG, GIF, WebP, or AVIF picture", 415, field="avatar")

    stored_name = f"{user['id']}-{secrets.token_hex(6)}{suffix}"
    (_avatar_dir() / stored_name).write_bytes(data)
    updated = svc.store.set_user_avatar(user["id"], stored_name) or user
    _drop_avatar_file(user.get("avatar_file") or "")
    svc.presence.set_avatar(user["id"], stored_name, float(updated.get("avatar_updated") or 0))
    public = public_person(updated, svc)
    svc.broker.broadcast("user.updated", {"user": public, "user_id": user["id"]})
    svc.broker.broadcast(
        "presence.changed",
        {"people": svc.presence.snapshot(), "count": svc.presence.count()},
    )
    svc.logger.info(
        "Profile picture: %s (%s bytes)",
        user["name"],
        len(data),
        extra={"event": "avatar", "user": user["name"], "count": len(data)},
    )
    return ok(user=public)


@bp.delete("/api/me/avatar")
@login_required
def remove_avatar():
    svc = services()
    user = g.user
    _drop_avatar_file(user.get("avatar_file") or "")
    updated = svc.store.set_user_avatar(user["id"], "") or user
    svc.presence.set_avatar(user["id"], "", float(updated.get("avatar_updated") or 0))
    public = public_person(updated, svc)
    svc.broker.broadcast("user.updated", {"user": public, "user_id": user["id"]})
    svc.broker.broadcast(
        "presence.changed",
        {"people": svc.presence.snapshot(), "count": svc.presence.count()},
    )
    return ok(user=public)


@bp.get("/api/avatars/<user_id>")
def serve_avatar(user_id: str):
    """Pictures are for people in the room or at the host console."""
    svc = services()
    if not session_user() and not host_session():
        return fail("Join the room first", 401)
    user = svc.store.get_user(user_id)
    if not user or not user.get("avatar_file"):
        return fail("No picture for that person", 404)
    path = _avatar_dir() / os.path.basename(user["avatar_file"])
    if not path.exists():
        return fail("That picture is gone", 404)
    response = send_file(
        path,
        mimetype=AVATAR_MIME.get(path.suffix.lower(), "application/octet-stream"),
        conditional=True,
        max_age=86400,
    )
    response.headers["Cache-Control"] = "private, max-age=86400"
    return response


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
