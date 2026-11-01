"""Host console API. Local by default, password gated always."""

from __future__ import annotations

import json
import logging
import time

from flask import Blueprint, Response, jsonify, request, session

from .api_common import fail, host_required, ok, payload, public_person, services
from .auth import (
    ROLE_LABELS,
    ROLES,
    RateLimiter,
    ValidationError,
    clean_role,
    client_ip,
    is_loopback,
)
from .diagnostics import overall, run_checks
from .logging_setup import log_stats, read_logs
from .netinfo import network_summary
from .version import __version__

bp = Blueprint("host", __name__)


def _limiter() -> RateLimiter:
    svc = services()
    if svc.auth_limiter is None:
        svc.auth_limiter = RateLimiter(limit=8, window=300, lockout=120)
    return svc.auth_limiter


@bp.post("/api/host/session")
def host_login():
    svc = services()
    config = svc.config
    if config.values["console_local_only"] and not is_loopback(client_ip()):
        return fail("Open the host console from the machine that runs the server", 403)
    limiter = _limiter()
    key = f"host:{client_ip()}"
    allowed, retry = limiter.check(key)
    if not allowed:
        return fail("Too many attempts. Wait a moment.", 429, retry_after=retry)
    data = payload()
    username = str(data.get("username") or config.host_user)
    password = str(data.get("password") or "")
    if not config.verify_host_user(username) or not config.verify_host_password(password):
        limiter.hit(key, failed=True)
        svc.logger.warning(
            "Host console login failed", extra={"event": "host.login_failed", "ip": client_ip()}
        )
        return fail("Wrong host name or password", 401, field="password")
    limiter.reset(key)
    session["host_ok"] = True
    session.permanent = True
    svc.logger.info("Host console signed in", extra={"event": "host.login", "ip": client_ip()})
    return ok(
        signed_in=True,
        host_user=config.host_user,
        setup_complete=config.setup_complete,
        local=is_loopback(client_ip()),
    )


@bp.delete("/api/host/session")
def host_logout():
    session.pop("host_ok", None)
    return ok(signed_in=False)


@bp.get("/api/host/summary")
@host_required
def summary():
    svc = services()
    config = svc.config
    stats = svc.store.stats()
    checks = run_checks(svc)
    return ok(
        server={
            "version": __version__,
            "started_at": svc.started_at,
            "uptime": int(time.time() - svc.started_at),
            "room_name": config.room_name,
            "port": config.port,
            "bind": config.bind,
            "setup_complete": config.setup_complete,
            "console_local_only": bool(config.values["console_local_only"]),
            "python": f"{__import__('sys').version.split()[0]}",
            "platform": __import__("platform").platform(),
            "data_dir": str(config.data_dir),
        },
        network=network_summary(request.headers, config.port),
        stats=stats,
        presence=svc.presence.snapshot(),
        people=svc.store.list_users(),
        rooms=[svc.room_public(room, "") for room in svc.store.list_all_rooms()],
        logs=log_stats(config.log_dir),
        checks=checks,
        check_status=overall(checks),
        config=config.redacted(),
        localsend={
            "enabled": bool(svc.localsend.enabled),
            "alias": svc.localsend.alias,
            "fingerprint": svc.localsend.fingerprint,
            "last_error": svc.localsend.last_error,
            "devices": svc.localsend.devices(),
            "received": svc.localsend.received[:12],
        },
        palette=svc.presence.palette(),
    )


@bp.patch("/api/host/settings")
@host_required
def update_settings():
    svc = services()
    config = svc.config
    data = payload()
    restart_keys = {"port", "bind"}
    restart_required = any(key in data and str(data[key]) != str(config.values.get(key)) for key in restart_keys)

    if "klipy_key" in data:
        data["klipy_key"] = str(data["klipy_key"]).strip()[:120]
    if "default_theme" in data and data["default_theme"] not in {"auto", "light", "dark"}:
        return fail("Theme must be auto, light, or dark", 400, field="default_theme")
    try:
        applied = config.update(data)
    except ValidationError as exc:
        return fail(exc.message, exc.status, field=exc.field)
    except Exception as exc:
        return fail(str(exc), 400)

    if "room_name" in applied:
        svc.store.ensure_room("main", config.room_name, kind="main")
        svc.broker.broadcast("server.updated", {"room_name": config.room_name})
    rule_keys = {"room_locked", "read_only", "slow_mode_seconds", "notice_text"}
    if rule_keys & set(applied):
        svc.broker.broadcast(
            "server.updated",
            {
                "rules": {
                    "room_locked": bool(config.values.get("room_locked")),
                    "read_only": bool(config.values.get("read_only")),
                    "slow_mode_seconds": int(config.values.get("slow_mode_seconds") or 0),
                    "notice_text": config.values.get("notice_text") or "",
                }
            },
        )
    if "log_level" in applied:
        svc.logger.setLevel(config.log_level)
        for handler in svc.logger.handlers:
            handler.setLevel(config.log_level)
    if "klipy_key" in applied:
        svc.gifs.api_key = config.klipy_key
    if "gifs_enabled" in applied:
        svc.gifs.enabled = bool(config.values["gifs_enabled"])
    if "localsend" in applied:
        svc.localsend.reconfigure(
            enabled=bool(config.localsend.get("enabled")),
            alias=str(config.localsend.get("alias") or "HostTalk"),
            pin=str(config.localsend.get("pin") or ""),
            protocol="https" if config.localsend.get("https") else "http",
        )
    svc.logger.info("Settings updated", extra={"event": "host.settings", "ip": client_ip()})
    return ok(
        config=config.redacted(),
        applied=applied,
        restart_required=restart_required,
    )


@bp.post("/api/host/credentials")
@host_required
def change_credentials():
    """The host name and host password change on the hosting machine only."""
    svc = services()
    config = svc.config
    if not is_loopback(client_ip()):
        return fail("Change host credentials on the machine that runs HostTalk", 403)
    data = payload()
    current = str(data.get("current") or "")
    if not config.verify_host_password(current):
        return fail("Current host password is wrong", 401, field="current")
    try:
        if str(data.get("host_user") or "").strip():
            config.set_host_user(str(data["host_user"]))
        if str(data.get("new") or ""):
            config.set_host_password(str(data["new"]))
    except Exception as exc:
        return fail(str(exc), 400, field="new")
    svc.logger.info("Host credentials changed", extra={"event": "host.credentials", "ip": client_ip()})
    return ok(host_user=config.host_user)


@bp.post("/api/host/password")
@host_required
def change_password():
    svc = services()
    config = svc.config
    if not is_loopback(client_ip()):
        return fail("Change the room password on the machine that runs HostTalk", 403)
    data = payload()
    current = str(data.get("current") or "")
    new = str(data.get("new") or "")
    if not config.verify_password(current):
        return fail("Current password is wrong", 401, field="current")
    if len(new) < 4:
        return fail("Use at least 4 characters", 400, field="new")
    if len(new) > 128:
        return fail("Keep the password under 128 characters", 400, field="new")
    config.set_password(new)
    svc.logger.info("Room password changed", extra={"event": "host.password", "ip": client_ip()})
    svc.broker.broadcast("server.updated", {"password_changed": True})
    return ok(changed=True)


@bp.get("/api/host/logs")
@host_required
def logs():
    svc = services()
    level = str(request.args.get("level") or "").upper() or None
    limit = request.args.get("limit", default=200, type=int) or 200
    records = read_logs(svc.config.log_dir, level=level, limit=limit)
    return ok(records=records, stats=log_stats(svc.config.log_dir))


@bp.get("/api/host/logs/download")
@host_required
def download_logs():
    svc = services()
    records = read_logs(svc.config.log_dir, limit=2000)
    body = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
    response = Response(body + "\n", mimetype="application/x-ndjson")
    response.headers["Content-Disposition"] = 'attachment; filename="hosttalk-logs.ndjson"'
    return response


@bp.get("/api/host/export")
@host_required
def export_room():
    svc = services()
    room_id = str(request.args.get("room") or "main")
    room = svc.store.get_room(room_id)
    if not room:
        return fail("That room does not exist", 404)
    payload_out = {
        "room": room,
        "exported_at": time.time(),
        "messages": svc.store.export_messages(room_id),
    }
    response = Response(
        json.dumps(payload_out, indent=2, ensure_ascii=False), mimetype="application/json"
    )
    response.headers["Content-Disposition"] = (
        f'attachment; filename="hosttalk-{room_id}-export.json"'
    )
    return response


@bp.post("/api/host/rooms/<room_id>/clear")
@host_required
def clear_room(room_id: str):
    svc = services()
    room = svc.store.get_room(room_id)
    if not room:
        return fail("That room does not exist", 404)
    removed = svc.store.clear_room(room_id)
    svc.broker.publish([room_id], "room.cleared", {"room_id": room_id, "removed": removed})
    svc.logger.info(
        "Room cleared", extra={"event": "host.clear", "room": room["name"], "count": removed}
    )
    return ok(removed=removed)


@bp.post("/api/host/users/<user_id>/disconnect")
@host_required
def disconnect_user(user_id: str):
    svc = services()
    user = svc.store.get_user(user_id)
    if not user:
        return fail("That person is not here", 404)
    for subscriber in svc.broker.user_connections(user_id):
        subscriber.send("session.revoked", {"reason": "The host ended this session"})
    svc.presence.disconnect(user_id)
    svc.broker.broadcast("presence.changed", {"people": svc.presence.snapshot(), "count": svc.presence.count()})
    svc.logger.info(
        "Host ended a session", extra={"event": "host.disconnect", "user": user["name"], "ip": client_ip()}
    )
    return ok(disconnected=user["name"])


@bp.get("/api/host/diagnostics")
@host_required
def diagnostics():
    svc = services()
    checks = run_checks(svc)
    return ok(checks=checks, status=overall(checks))


@bp.post("/api/host/localsend/scan")
@host_required
def host_localsend_scan():
    svc = services()
    try:
        devices = svc.localsend.scan()
    except Exception as exc:
        return fail(str(exc), 409)
    return ok(devices=devices)


@bp.post("/api/host/shutdown")
@host_required
def shutdown():
    svc = services()
    if not is_loopback(client_ip()):
        return fail("Stop the server from the machine that runs it", 403)
    svc.logger.info("Shutdown requested from the host console", extra={"event": "host.shutdown"})
    svc.control.request_stop()
    return ok(stopping=True)


@bp.get("/api/host/people")
@host_required
def host_people():
    svc = services()
    online = {person["id"] for person in svc.presence.snapshot()}
    people = []
    for user in svc.store.list_users():
        item = public_person(user, svc)
        item["online"] = user["id"] in online
        item["last_nick_at"] = user.get("last_nick_at")
        item["role"] = user.get("role") or "member"
        item["rooms"] = [
            room["name"]
            for room in svc.store.list_rooms_for(user["id"])
            if room["id"] != "main"
        ]
        people.append(item)
    nickname_log = svc.store.nickname_log(limit=50)
    return ok(
        people=people,
        nickname_log=nickname_log,
        palette=svc.presence.palette(),
        roles=[{"id": role, "label": ROLE_LABELS[role]} for role in ROLES],
    )


@bp.post("/api/host/users/<user_id>/role")
@host_required
def set_user_role(user_id: str):
    """The console moves every role, including the host role."""
    svc = services()
    target = svc.store.get_user(user_id)
    if not target:
        return fail("That person is not here", 404)
    try:
        role = clean_role(payload().get("role"), allowed=ROLES)
    except ValidationError as exc:
        return fail(exc.message, exc.status, field=exc.field)
    updated = svc.store.set_user_role(target["id"], role) or target
    svc.presence.set_role(target["id"], role)
    public = public_person(updated, svc)
    svc.broker.broadcast("user.updated", {"user": public, "user_id": updated["id"], "role": role})
    svc.broker.broadcast(
        "presence.changed",
        {"people": svc.presence.snapshot(), "count": svc.presence.count()},
    )
    svc.logger.info(
        "Console role change: %s is %s",
        updated["name"],
        role,
        extra={"event": "host.role", "user": updated["name"], "detail": role, "ip": client_ip()},
    )
    return ok(user=public)


@bp.get("/api/host/theme-preview")
@host_required
def theme_preview():
    return jsonify({"ok": True, "themes": ["auto", "light", "dark"]})


@bp.post("/api/host/theme")
@host_required
def set_default_theme():
    svc = services()
    data = payload()
    theme = str(data.get("theme") or "")
    if theme not in {"auto", "light", "dark"}:
        return fail("Theme must be auto, light, or dark", 400)
    svc.config.update({"default_theme": theme})
    return ok(theme=theme)


def _bad(message: str):
    response = jsonify({"ok": False, "message": message})
    response.status_code = 400
    return response


logging.getLogger("hosttalk.host").debug("host api loaded")
