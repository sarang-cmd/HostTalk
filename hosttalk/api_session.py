"""Join flow, profile, presence, invites, and the event stream."""

from __future__ import annotations

import queue
import time
from typing import Any

from flask import Blueprint, Response, g, request, session, stream_with_context

from .api_common import (
    fail,
    login_required,
    ok,
    payload,
    public_person,
    public_rooms_for,
    services,
    session_user,
)
from .auth import (
    COLOR_GRID,
    NICKNAME_COOLDOWN_SECONDS,
    RateLimiter,
    ValidationError,
    bind_session,
    clean_color,
    clean_name,
    clean_room_name,
    client_ip,
    is_host_request,
    luminance_contrast,
)
from .events import HEARTBEAT, format_event
from .netinfo import network_summary
from .version import __version__

bp = Blueprint("session", __name__)


def _login_limiter() -> RateLimiter:
    svc = services()
    if svc.auth_limiter is None:
        svc.auth_limiter = RateLimiter(limit=8, window=300, lockout=120)
    return svc.auth_limiter


@bp.get("/api/status")
def status():
    svc = services()
    config = svc.config
    return ok(
        server={
            "version": __version__,
            "room_name": config.room_name,
            "setup_complete": config.setup_complete,
            "requires_password": bool(config.values["password_hash"]),
            "port": config.port,
            "local": is_host_request(config),
            "max_upload_mb": int(config.values["max_upload_mb"]),
            "max_room_members": config.max_room_members,
            "previews_enabled": config.previews_enabled,
            "gifs_enabled": bool(config.values["gifs_enabled"]),
            "gifs_ready": bool(config.klipy_key),
            "localsend_enabled": bool(config.localsend.get("enabled")),
            "default_theme": config.values["default_theme"],
            "palette": COLOR_GRID,
            "online": svc.presence.count(),
        }
    )


@bp.post("/api/setup")
def setup():
    """First run only, from the machine that runs the server."""
    svc = services()
    config = svc.config
    if config.setup_complete:
        return fail("This server is already set up", 409)
    if not is_host_request(config):
        return fail("Run setup from the machine that hosts HostTalk", 403)
    data = payload()
    try:
        room_name = clean_room_name(data.get("room_name") or config.room_name)
        password = str(data.get("password") or "")
        if len(password) < 4:
            raise ValidationError("Use at least 4 characters for the password", field="password")
        patch: dict[str, Any] = {"room_name": room_name}
        for key in ("port", "bind", "open_browser"):
            if key in data:
                patch[key] = data[key]
        config.set_password(password)
        config.update(patch)
        svc.store.ensure_room("main", config.room_name, kind="main")
        svc.logger.info("Setup finished", extra={"event": "setup", "ip": client_ip()})
        return ok(room_name=config.room_name, port=config.port, next="/room")
    except ValidationError as exc:
        return fail(exc.message, exc.status, field=exc.field)
    except Exception as exc:  # ConfigError and other validation problems
        return fail(str(exc), 400)


@bp.post("/api/session")
def create_session():
    svc = services()
    config = svc.config
    limiter = _login_limiter()
    ip = client_ip()
    allowed, retry_after = limiter.check(ip)
    if not allowed:
        return fail("Too many attempts. Wait a moment.", 429, retry_after=retry_after)
    data = payload()
    try:
        name = clean_name(data.get("name"))
    except ValidationError as exc:
        return fail(exc.message, exc.status, field=exc.field)
    password = str(data.get("password") or "")
    device_key = str(data.get("device_key") or "")[:64]

    if config.setup_complete and not config.verify_password(password):
        limiter.hit(ip, failed=True)
        svc.logger.warning("Wrong password from %s", ip, extra={"event": "auth.failed", "ip": ip})
        return fail("Wrong password. Try again.", 401, field="password")
    limiter.reset(ip)
    limiter.hit(ip)

    user, error = svc.store.claim_name(name, device_key)
    if error or not user:
        return fail(error or "That name is not available", 409, field="name")

    bind_session(user)
    svc.broker.broadcast("presence.changed", _presence_payload())
    svc.logger.info(
        "Join: %s", user["name"], extra={"event": "session.join", "user": user["name"], "ip": ip}
    )
    return ok(
        user=public_person(user, svc),
        rooms=public_rooms_for(user["id"], svc),
        palette=COLOR_GRID,
        people=svc.presence.snapshot(),
        server=svc.config.public_settings(),
        reactions=_reactions(),
    )


@bp.delete("/api/session")
def delete_session():
    svc = services()
    user = session_user()
    session.clear()
    if user:
        svc.logger.info("Leave: %s", user["name"], extra={"event": "session.leave", "user": user["name"]})
    return ok()


@bp.get("/api/me")
def me():
    """Signed-in profile. Guests get a 200 so the join screen boots quietly."""
    svc = services()
    user = session_user()
    if not user:
        return ok(user=None, rooms=[], server=svc.config.public_settings(), palette=COLOR_GRID, reactions=_reactions())
    return ok(
        user=public_person(user, svc),
        rooms=public_rooms_for(user["id"], svc),
        server=svc.config.public_settings(),
        palette=COLOR_GRID,
        reactions=_reactions(),
    )


@bp.patch("/api/me")
@login_required
def update_me():
    svc = services()
    user = g.user
    data = payload()
    changes: dict[str, Any] = {}

    if "name" in data:
        try:
            new_name = clean_name(data.get("name"))
        except ValidationError as exc:
            return fail(exc.message, exc.status, field="name")
        if new_name.lower() != user["name"].lower():
            existing = svc.store.get_user_by_name(new_name)
            if existing and existing["id"] != user["id"]:
                return fail("That name is already in the room", 409, field="name")
            last_change = float(user.get("last_nick_at") or 0)
            wait = NICKNAME_COOLDOWN_SECONDS - (time.time() - last_change)
            if wait > 0:
                return fail(
                    "Names change once an hour. Try again later.",
                    429,
                    retry_after=int(wait),
                    field="name",
                )
            user = svc.store.rename_user(
                user["id"], new_name, ip=client_ip(), cooldown_seconds=NICKNAME_COOLDOWN_SECONDS
            )
            svc.presence.rename(user["id"], new_name)
            changes["name"] = new_name
            svc.broker.broadcast(
                "user.updated",
                {"user": public_person(user, svc), "name": new_name, "user_id": user["id"]},
            )
            svc.logger.info(
                "Name change: %s",
                new_name,
                extra={"event": "nickname", "user": new_name, "ip": client_ip()},
            )

    if "color" in data:
        try:
            color = clean_color(data.get("color"))
        except ValidationError as exc:
            return fail(exc.message, exc.status, field="color")
        if luminance_contrast(color) < 4.5:
            return fail("Pick a darker color so white text stays readable", 400, field="color")
        for person in svc.presence.snapshot():
            if person["color"] == color and person["id"] != user["id"]:
                return fail("Someone else uses that color right now", 409, field="color")
        svc.store.set_user_color(user["id"], color)
        svc.presence.set_color(user["id"], color)
        changes["color"] = color
        svc.broker.broadcast(
            "user.updated",
            {"user": {**public_person(user, svc), "color": color}, "user_id": user["id"]},
        )

    svc.broker.broadcast("presence.changed", _presence_payload())
    return ok(user=public_person(svc.store.get_user(user["id"]) or user, svc), changes=changes)


@bp.get("/api/people")
@login_required
def people():
    svc = services()
    all_users = svc.store.list_users()
    online_ids = {person["id"] for person in svc.presence.snapshot()}
    everyone = []
    for user in all_users:
        item = public_person(user, svc)
        item["online"] = user["id"] in online_ids
        everyone.append(item)
    everyone.sort(key=lambda item: (not item["online"], item["name"].lower()))
    return ok(people=everyone, online=svc.presence.snapshot(), palette=COLOR_GRID)


@bp.get("/api/invite")
@login_required
def invite():
    svc = services()
    summary = network_summary(request.headers, svc.config.port)
    return ok(
        network=summary,
        needs_password=bool(svc.config.values["password_hash"]),
        room={"id": "main", "name": svc.config.room_name},
        note="Anyone on this network with the address and password joins the room.",
    )


@bp.post("/api/rooms/<room_id>/invite")
@login_required
def room_invite(room_id: str):
    svc = services()
    user = g.user
    room = svc.store.get_room(room_id)
    if not room:
        return fail("That room does not exist", 404)
    if room["id"] != "main" and not svc.store.is_member(room_id, user["id"]):
        return fail("Join that room first", 403)
    data = payload()
    invite_row = svc.store.create_invite(
        room_id,
        user["id"],
        ttl_seconds=int(data.get("ttl_seconds") or 7 * 24 * 3600),
        max_uses=int(data.get("max_uses") or 50),
    )
    summary = network_summary(request.headers, svc.config.port)
    url = f"{summary['address']}?join={invite_row['code']}"
    return ok(code=invite_row["code"], url=url, network=summary, room=svc.room_public(room, user["id"]))


@bp.get("/api/events")
@login_required
def events():
    svc = services()
    user = g.user
    rooms = [room["id"] for room in svc.store.list_rooms_for(user["id"])]
    subscriber = svc.broker.subscribe(user["id"], rooms)
    svc.presence.connect(user)
    svc.broker.broadcast("presence.changed", _presence_payload())

    def stream():
        try:
            yield "retry: 2500\n\n"
            yield format_event(
                "ready",
                {
                    "user": public_person(user, svc),
                    "server_time": time.time(),
                    "people": svc.presence.snapshot(),
                },
            )
            while True:
                try:
                    event, data = subscriber.queue.get(timeout=20)
                except queue.Empty:
                    svc.presence.touch(user["id"])
                    yield HEARTBEAT
                    continue
                yield format_event(event, data)
        finally:
            svc.broker.unsubscribe(subscriber)
            svc.presence.disconnect(user["id"])
            svc.broker.broadcast("presence.changed", _presence_payload())

    response = Response(stream_with_context(stream()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache, no-store"
    response.headers["X-Accel-Buffering"] = "no"
    return response


def _presence_payload() -> dict[str, Any]:
    svc = services()
    return {"people": svc.presence.snapshot(), "count": svc.presence.count()}


def _reactions() -> list[str]:
    from .auth import ALLOWED_REACTIONS

    return list(ALLOWED_REACTIONS)
