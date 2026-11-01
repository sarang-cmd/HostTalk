"""Rooms, messages, reactions, typing, link previews, and GIF search."""

from __future__ import annotations

import time

import bcrypt
from flask import Blueprint, g, request

from .api_common import (
    fail,
    login_required,
    ok,
    payload,
    room_for_user,
    serialize_message,
    serialize_messages,
    services,
)
from .auth import (
    CUSTOM_EMOJI_PREFIX,
    RateLimiter,
    ValidationError,
    can_moderate,
    clean_emoji,
    clean_message,
    clean_room_name,
)
from .gifs import GifError
from .previews import PreviewCache, PreviewError, parse_preview, validate_url
from .store import MAIN_ROOM

bp = Blueprint("chat", __name__)
MAX_ALT_BODY = 900


def _message_limiter() -> RateLimiter:
    svc = services()
    if svc.message_limiter is None:
        svc.message_limiter = RateLimiter(limit=20, window=10)
    return svc.message_limiter


def _typing_limiter() -> RateLimiter:
    svc = services()
    if svc.typing_limiter is None:
        svc.typing_limiter = RateLimiter(limit=1, window=2)
    return svc.typing_limiter


@bp.get("/api/rooms")
@login_required
def list_rooms():
    svc = services()
    return ok(rooms=[svc.room_public(room, g.user["id"]) for room in svc.store.list_rooms_for(g.user["id"])])


@bp.post("/api/rooms")
@login_required
def create_room():
    svc = services()
    user = g.user
    data = payload()
    try:
        name = clean_room_name(data.get("name"))
    except ValidationError as exc:
        return fail(exc.message, exc.status, field="name")
    parent_id = str(data.get("parent_id") or "").strip()
    if parent_id:
        parent = svc.store.get_room(parent_id)
        if not parent or parent["kind"] == "dm":
            return fail("That room cannot hold another room", 400, field="parent_id")
        if parent_id != MAIN_ROOM and not svc.store.is_member(parent_id, user["id"]):
            return fail("Join the room above this one first", 403, field="parent_id")
    password = str(data.get("password") or "")
    if password and len(password) < 4:
        return fail("Use at least 4 characters", 400, field="password")
    room = svc.store.create_room(
        name,
        user["id"],
        kind="group",
        member_limit=svc.config.max_room_members,
        password_hash=(
            bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            if password
            else ""
        ),
        parent_id=parent_id,
    )
    svc.store.add_member(room["id"], user["id"])
    svc.broker.subscribe_rooms(user["id"], [room["id"]])
    svc.broker.publish(
        [room["id"]],
        "room.created",
        {"room": svc.room_public(svc.store.get_room(room["id"]) or room, user["id"])},
    )
    svc.logger.info("Room created: %s", name, extra={"event": "room.create", "room": name, "user": user["name"]})
    return ok(room=svc.room_public(svc.store.get_room(room["id"]) or room, user["id"]), messages=[])


@bp.post("/api/rooms/join")
@login_required
def join_room():
    svc = services()
    user = g.user
    data = payload()
    code = str(data.get("code") or "").strip()
    if not code:
        return fail("That invite link is missing a code", 400, field="code")
    invite = svc.store.get_invite(code)
    if not invite:
        return fail("That invite link is not valid", 404, field="code")
    if invite["expires_at"] < time.time():
        return fail("That invite link expired", 410, field="code")
    if invite["uses"] >= invite["max_uses"]:
        return fail("That invite link reached its limit", 410, field="code")
    room = svc.store.get_room(invite["room_id"])
    if not room:
        return fail("That room no longer exists", 404)
    if svc.store.is_member(room["id"], user["id"]):
        svc.broker.subscribe_rooms(user["id"], [room["id"]])
        return ok(room=svc.room_public(room, user["id"]), already_member=True)
    if room["kind"] != "main" and svc.store.member_count(room["id"]) >= int(room["member_limit"]):
        return fail("That room is full", 409)
    password = str(data.get("password") or "")
    stored = invite.get("password_hash") or room.get("password_hash") or ""
    if stored:
        if not password:
            return fail("This room asks for a password", 401, password_required=True)
        if not bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8")):
            return fail("Wrong password for that room", 401, password_required=True)
    svc.store.use_invite(code)
    svc.store.add_member(room["id"], user["id"])
    svc.broker.subscribe_rooms(user["id"], [room["id"]])
    svc.broker.publish(
        [room["id"]],
        "room.member_joined",
        {"room_id": room["id"], "user": {"id": user["id"], "name": user["name"]}},
    )
    messages = serialize_messages(svc.store.list_messages(room["id"], limit=50), svc)
    svc.logger.info(
        "Room join: %s", room["name"], extra={"event": "room.join", "room": room["name"], "user": user["name"]}
    )
    return ok(room=svc.room_public(svc.store.get_room(room["id"]) or room, user["id"]), messages=messages)


@bp.post("/api/rooms/<room_id>/enter")
@login_required
def enter_room(room_id: str):
    """Step into a room that sits inside a room you already joined."""
    svc = services()
    user = g.user
    room = svc.store.get_room(room_id)
    if not room or room["kind"] == "main":
        return fail("That room does not exist", 404)
    if svc.store.is_member(room_id, user["id"]):
        return ok(room=svc.room_public(room, user["id"]), already_member=True)
    parent_id = room.get("parent_id") or ""
    if parent_id and parent_id != MAIN_ROOM and not svc.store.is_member(parent_id, user["id"]):
        return fail("Join the room above this one first", 403)
    if svc.store.member_count(room_id) >= int(room["member_limit"]):
        return fail("That room is full", 409)
    stored = room.get("password_hash") or ""
    if stored:
        password = str(payload().get("password") or "")
        if not password:
            return fail("This room asks for a password", 401, password_required=True)
        if not bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8")):
            return fail("Wrong password for that room", 401, password_required=True)
    svc.store.add_member(room_id, user["id"])
    svc.broker.subscribe_rooms(user["id"], [room_id])
    svc.broker.publish(
        [room_id],
        "room.member_joined",
        {"room_id": room_id, "user": {"id": user["id"], "name": user["name"]}},
    )
    messages = serialize_messages(svc.store.list_messages(room_id, limit=50), svc)
    svc.logger.info(
        "Room enter: %s",
        room["name"],
        extra={"event": "room.enter", "room": room["name"], "user": user["name"]},
    )
    return ok(
        room=svc.room_public(svc.store.get_room(room_id) or room, user["id"]),
        messages=messages,
    )


@bp.post("/api/rooms/<room_id>/leave")
@login_required
def leave_room(room_id: str):
    svc = services()
    user = g.user
    if room_id == MAIN_ROOM:
        return fail("You cannot leave the main room", 400)
    room = svc.store.get_room(room_id)
    if not room:
        return fail("That room does not exist", 404)
    if not svc.store.is_member(room_id, user["id"]):
        return fail("You are not in that room", 409)
    svc.store.remove_member(room_id, user["id"])
    svc.broker.publish([room_id], "room.member_left", {"room_id": room_id, "user_id": user["id"]})
    return ok(left=room_id)


@bp.get("/api/rooms/<room_id>/members")
@login_required
def room_members(room_id: str):
    svc = services()
    room, error = room_for_user(room_id, g.user["id"])
    if not room:
        return fail(error, 404)
    if room["id"] == MAIN_ROOM:
        people = svc.presence.snapshot()
        return ok(members=people, count=len(people), limit=None, online=len(people))
    members = []
    for user in svc.store.room_members(room_id):
        person = svc.presence.get(user["id"])
        members.append(
            {
                "id": user["id"],
                "name": user["name"],
                "color": person.color if person else user.get("color") or "#34527A",
                "avatar_seed": user.get("avatar_seed") or "",
                "online": bool(person),
            }
        )
    return ok(
        members=members,
        count=len(members),
        limit=int(room["member_limit"]),
        online=sum(1 for member in members if member["online"]),
    )


@bp.post("/api/rooms/<room_id>/verify")
@login_required
def verify_room(room_id: str):
    svc = services()
    room, _ = room_for_user(room_id, g.user["id"])
    if not room:
        room = svc.store.get_room(room_id)
        if not room:
            return fail("That room does not exist", 404)
    stored = room.get("password_hash") or ""
    if not stored:
        return ok(valid=True)
    password = str(payload().get("password") or "")
    if not password:
        return fail("Enter the room password", 401, password_required=True)
    if not bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8")):
        return fail("Wrong password", 401, password_required=True)
    return ok(valid=True)


@bp.post("/api/rooms/<room_id>/password")
@login_required
def set_room_password(room_id: str):
    svc = services()
    room, error = room_for_user(room_id, g.user["id"])
    if not room:
        return fail(error, 404)
    if room["kind"] == "main":
        return fail("The main room uses the server password", 400)
    data = payload()
    password = str(data.get("password") or "")
    if password and len(password) < 4:
        return fail("Use at least 4 characters", 400, field="password")
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8") if password else ""
    svc.store.set_room_password(room_id, hashed)
    svc.broker.publish(
        [room_id], "room.updated", {"room": svc.room_public(svc.store.get_room(room_id) or room, g.user["id"])}
    )
    return ok(has_password=bool(password))


@bp.post("/api/dm")
@login_required
def open_dm():
    svc = services()
    user = g.user
    data = payload()
    other_id = str(data.get("user_id") or "")
    if not other_id or other_id == user["id"]:
        return fail("Pick someone else to message", 400, field="user_id")
    other = svc.store.get_user(other_id)
    if not other:
        return fail("That person is not in the room", 404)
    room = svc.store.find_dm_room(user["id"], other["id"])
    created = False
    if not room:
        room = svc.store.create_room(
            f"{user['name']} and {other['name']}",
            user["id"],
            kind="dm",
            member_limit=2,
        )
        svc.store.add_member(room["id"], user["id"])
        svc.store.add_member(room["id"], other["id"])
        created = True
    if not svc.store.is_member(room["id"], user["id"]):
        if room.get("password_hash"):
            password = str(data.get("password") or "")
            if not password:
                return fail("This conversation asks for a password", 401, password_required=True)
            if not bcrypt.checkpw(password.encode("utf-8"), room["password_hash"].encode("utf-8")):
                return fail("Wrong password", 401, password_required=True)
        svc.store.add_member(room["id"], user["id"])
    svc.broker.subscribe_rooms(user["id"], [room["id"]])
    if created:
        svc.broker.publish(
            [room["id"]],
            "room.created",
            {"room": svc.room_public(svc.store.get_room(room["id"]) or room, user["id"])},
        )
    messages = serialize_messages(svc.store.list_messages(room["id"], limit=50), svc)
    return ok(room=svc.room_public(svc.store.get_room(room["id"]) or room, user["id"]), messages=messages)


@bp.get("/api/rooms/<room_id>/messages")
@login_required
def list_messages(room_id: str):
    svc = services()
    room, error = room_for_user(room_id, g.user["id"])
    if not room:
        return fail(error, 404 if not svc.store.get_room(room_id) else 403)
    before = request.args.get("before", type=int)
    limit = max(1, min(100, request.args.get("limit", default=50, type=int) or 50))
    fetched = svc.store.list_messages(room_id, before_seq=before, limit=limit + 1)
    has_more = len(fetched) > limit
    messages = fetched[-limit:]
    return ok(
        messages=serialize_messages(messages, svc),
        room=svc.room_public(room, g.user["id"]),
        has_more=has_more,
    )


@bp.post("/api/messages")
@login_required
def send_message():
    svc = services()
    user = g.user
    limiter = _message_limiter()
    allowed, retry = limiter.check(user["id"])
    if not allowed:
        return fail("Slow down for a moment", 429, retry_after=retry)
    limiter.hit(user["id"])

    privileged = bool(session_host()) or can_moderate(user.get("role") or "")
    config = svc.config
    if config.values.get("read_only") and not privileged:
        return fail("The host set this room to read only", 403)
    slow_seconds = int(config.values.get("slow_mode_seconds") or 0)
    if slow_seconds and not privileged:
        if svc.slow_limiter is None or svc.slow_window != slow_seconds:
            svc.slow_limiter = RateLimiter(limit=1, window=slow_seconds)
            svc.slow_window = slow_seconds
        ok_slow, wait = svc.slow_limiter.check(user["id"])
        if not ok_slow:
            return fail(f"Slow mode. Wait {wait} seconds.", 429, retry_after=wait)
        svc.slow_limiter.hit(user["id"])

    data = payload()
    room_id = str(data.get("room_id") or MAIN_ROOM)
    room, error = room_for_user(room_id, user["id"])
    if not room:
        return fail(error, 404 if not svc.store.get_room(room_id) else 403)
    kind = str(data.get("kind") or "text")
    if kind not in {"text", "image", "file", "gif"}:
        return fail("That message type is not supported", 400, field="kind")
    body = ""
    if kind == "text":
        try:
            body = clean_message(data.get("body"))
        except ValidationError as exc:
            return fail(exc.message, exc.status, field="body")
    else:
        body = str(data.get("body") or "")[:MAX_ALT_BODY]
        if kind == "gif" and not str(body).startswith(("https://", "http://")):
            return fail("That GIF link is not valid", 400, field="body")

    attachment_id = data.get("attachment_id") or None
    attachment = None
    if attachment_id:
        attachment = svc.store.get_attachment(str(attachment_id))
        if not attachment:
            return fail("That file is missing", 404, field="attachment_id")
        if attachment["uploader"] != user["id"]:
            return fail("That file belongs to another upload", 403)
        if not body:
            body = attachment["filename"]
        if kind == "text":
            kind = "image" if attachment["mime"].startswith("image/") else "file"

    quote_id = data.get("quote_id") or None
    if quote_id:
        quoted = svc.store.get_message(str(quote_id))
        if not quoted or quoted["room_id"] != room_id:
            return fail("That message is not in this room", 400, field="quote_id")
        if quoted.get("deleted_at"):
            return fail("That message was deleted", 400, field="quote_id")

    message = svc.store.add_message(
        room_id,
        user["id"],
        user["name"],
        body,
        kind=kind,
        attachment_id=str(attachment_id) if attachment_id else None,
        quote_id=str(quote_id) if quote_id else None,
        meta={"gif": body} if kind == "gif" else {},
    )
    public = serialize_message(message, svc)
    svc.broker.publish([room_id], "message.created", {"message": public, "room_id": room_id})
    return ok(message=public)


@bp.patch("/api/messages/<message_id>")
@login_required
def edit_message(message_id: str):
    svc = services()
    user = g.user
    message = svc.store.get_message(message_id)
    if not message:
        return fail("That message was not found", 404)
    if message["user_id"] != user["id"]:
        return fail("You can only edit your own messages", 403)
    if message["kind"] not in {"text", "gif"}:
        return fail("Messages with files keep their text", 400)
    data = payload()
    try:
        body = clean_message(data.get("body"))
    except ValidationError as exc:
        return fail(exc.message, exc.status, field="body")
    updated = svc.store.edit_message(message_id, user["id"], body)
    public = serialize_message(updated or message, svc)
    svc.broker.publish([message["room_id"]], "message.updated", {"message": public})
    return ok(message=public)


@bp.delete("/api/messages/<message_id>")
@login_required
def delete_message(message_id: str):
    svc = services()
    user = g.user
    message = svc.store.get_message(message_id)
    if not message:
        return fail("That message was not found", 404)
    privileged = bool(session_host()) or can_moderate(user.get("role") or "")
    if message["user_id"] != user["id"] and not privileged:
        return fail("Only the host and moderators delete other messages", 403)
    updated = svc.store.delete_message(message_id)
    public = serialize_message(updated or message, svc)
    svc.broker.publish([message["room_id"]], "message.deleted", {"message": public})
    return ok(message=public)


@bp.post("/api/messages/<message_id>/pin")
@login_required
def pin_message(message_id: str):
    svc = services()
    user = g.user
    message = svc.store.get_message(message_id)
    if not message or message.get("deleted_at"):
        return fail("That message was not found", 404)
    room, error = room_for_user(message["room_id"], user["id"])
    if not room:
        return fail(error, 403)
    if not (bool(session_host()) or can_moderate(user.get("role") or "")):
        return fail("Only the host and moderators pin messages", 403)
    pinned = bool(payload().get("pinned", True))
    updated = svc.store.set_pinned(message_id, pinned=pinned, user_id=user["id"])
    public = serialize_message(updated or message, svc)
    svc.broker.publish(
        [message["room_id"]],
        "message.updated",
        {"message": public, "pinned": pinned, "by": user["name"]},
    )
    svc.logger.info(
        "%s a message", "Pinned" if pinned else "Unpinned",
        extra={"event": "pin", "user": user["name"], "detail": message_id},
    )
    return ok(message=public, pinned=pinned)


@bp.get("/api/rooms/<room_id>/pinned")
@login_required
def pinned_messages(room_id: str):
    svc = services()
    room, error = room_for_user(room_id, g.user["id"])
    if not room:
        return fail(error, 404 if not svc.store.get_room(room_id) else 403)
    messages = svc.store.pinned_messages(room_id)
    return ok(messages=serialize_messages(messages, svc), room_id=room_id)


@bp.post("/api/messages/<message_id>/reactions")
@login_required
def react(message_id: str):
    svc = services()
    message = svc.store.get_message(message_id)
    if not message:
        return fail("That message was not found", 404)
    if not svc.store.is_member(message["room_id"], g.user["id"]):
        return fail("Join that room first", 403)
    try:
        emoji = clean_emoji(payload().get("emoji"))
    except ValidationError as exc:
        return fail(exc.message, exc.status, field="emoji")
    if emoji.startswith(CUSTOM_EMOJI_PREFIX):
        emoji_id = emoji.split(":", 1)[1]
        if not svc.store.get_custom_emoji(emoji_id):
            return fail("That emoji is gone", 404, field="emoji")
    reactions = svc.store.toggle_reaction(message_id, g.user["id"], emoji)
    svc.broker.publish(
        [message["room_id"]],
        "message.reactions",
        {"message_id": message_id, "reactions": reactions},
    )
    return ok(reactions=reactions)


@bp.post("/api/typing")
@login_required
def typing():
    svc = services()
    user = g.user
    data = payload()
    room_id = str(data.get("room_id") or MAIN_ROOM)
    if not svc.store.is_member(room_id, user["id"]):
        return fail("Join that room first", 403)
    limiter = _typing_limiter()
    allowed, _ = limiter.check(user["id"])
    if not allowed:
        return ok(sent=False)
    limiter.hit(user["id"])
    svc.broker.publish(
        [room_id],
        "typing",
        {"room_id": room_id, "user_id": user["id"], "name": user["name"], "at": time.time()},
        exclude_user=user["id"],
    )
    return ok(sent=True)


@bp.get("/api/search")
@login_required
def search():
    svc = services()
    query = str(request.args.get("q") or "").strip()
    if len(query) < 2:
        return ok(results=[], query=query)
    rooms = {room["id"]: room["name"] for room in svc.store.list_rooms_for(g.user["id"])}
    results = svc.store.search_messages(query, rooms.keys(), limit=40)
    return ok(
        query=query,
        results=[
            {**serialize_message(message, svc), "room_name": rooms.get(message["room_id"], "")}
            for message in results
        ],
    )


@bp.get("/api/previews")
@login_required
def preview():
    svc = services()
    if not svc.config.previews_enabled:
        return fail("Link previews are turned off", 403)
    url = str(request.args.get("url") or "")
    cache: PreviewCache = svc.previews
    cached = cache.get(url)
    if cached:
        return ok(preview=cached)
    try:
        validate_url(url)
        data = parse_preview(url)
    except PreviewError as exc:
        return fail(str(exc), 422)
    except Exception:
        svc.logger.exception("Preview failed for %s", url)
        return fail("That page did not answer", 502)
    cache.put(url, data)
    return ok(preview=data)


@bp.get("/api/gifs")
@login_required
def gifs():
    svc = services()
    query = str(request.args.get("q") or "").strip()
    try:
        results = svc.gifs.search(query)
    except GifError as exc:
        return fail(str(exc), getattr(exc, "status", 502))
    return ok(gifs=results, query=query)



def session_host() -> bool:
    from flask import session

    return bool(session.get("host_ok"))
