"""Helpers shared by the JSON API blueprints."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import g, jsonify, request, session

from .auth import origin_allowed
from .services import Services
from .store import MAIN_ROOM


def services() -> Services:
    return g.services


def payload() -> dict[str, Any]:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def ok(**fields: Any):
    return jsonify({"ok": True, **fields})


def fail(message: str, status: int = 400, **fields: Any):
    response = jsonify({"ok": False, "message": message, **fields})
    response.status_code = status
    return response


def public_attachment(attachment: dict[str, Any] | None) -> dict[str, Any] | None:
    if not attachment:
        return None
    mime = attachment.get("mime") or "application/octet-stream"
    return {
        "id": attachment["id"],
        "filename": attachment["filename"],
        "mime": mime,
        "size": int(attachment["size"]),
        "url": f"/api/files/{attachment['id']}",
        "is_image": mime.startswith("image/"),
        "created_at": attachment["created_at"],
    }


def avatar_url(user_id: str, filename: str, updated: Any = 0) -> str:
    """Empty when the person has no picture, so the client falls back to initials."""
    if not filename:
        return ""
    try:
        version = int(float(updated or 0))
    except (TypeError, ValueError):
        version = 0
    return f"/api/avatars/{user_id}?v={version}"


def public_person(user: dict[str, Any], services_: Services) -> dict[str, Any]:
    person = services_.presence.get(user["id"])
    color = (person.color if person else user.get("color")) or "#34527A"
    role = (person.role if person else user.get("role")) or "member"
    avatar_file = person.avatar_file if person else user.get("avatar_file") or ""
    updated = person.avatar_updated if person else user.get("avatar_updated") or 0
    return {
        "id": user["id"],
        "name": user["name"],
        "color": color,
        "avatar_seed": user.get("avatar_seed") or user["id"][:8],
        "avatar_url": avatar_url(user["id"], avatar_file, updated),
        "role": role,
        "badge_icon": (person.badge_icon if person else user.get("badge_icon")) or "",
        "badge_text": (person.badge_text if person else user.get("badge_text")) or "",
        "online": bool(person),
    }


def public_rooms_for(user_id: str, services_: Services) -> list[dict[str, Any]]:
    rooms = services_.store.list_rooms_for(user_id)
    return [services_.room_public(room, user_id) for room in rooms]


def serialize_messages(messages: list[dict[str, Any]], services_: Services) -> list[dict[str, Any]]:
    if not messages:
        return []
    users = {user["id"]: user for user in services_.store.list_users()}
    reactions = services_.store.reactions_for([message["id"] for message in messages])
    quotes = services_.store.get_messages(
        [message["quote_id"] for message in messages if message.get("quote_id")]
    )
    output = []
    for message in messages:
        output.append(serialize_message(message, services_, users, reactions, quotes))
    return output


def serialize_message(
    message: dict[str, Any],
    services_: Services,
    users: dict[str, dict[str, Any]] | None = None,
    reactions: dict[str, dict[str, list[str]]] | None = None,
    quotes: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    users = users if users is not None else {
        user["id"]: user for user in services_.store.list_users()
    }
    user = users.get(message["user_id"]) or {
        "id": message["user_id"],
        "name": message["name"],
        "color": "",
    }
    person = services_.presence.get(message["user_id"])
    avatar_file = person.avatar_file if person else user.get("avatar_file") or ""
    avatar_updated = person.avatar_updated if person else user.get("avatar_updated") or 0
    attachment = None
    if message.get("attachment_id"):
        attachment = public_attachment(services_.store.get_attachment(message["attachment_id"]))
    quote = None
    if message.get("quote_id"):
        source = (quotes or {}).get(message["quote_id"])
        if source is None and not quotes:
            source = services_.store.get_message(message["quote_id"])
        if source:
            quote = {
                "id": source["id"],
                "name": source["name"],
                "body": source["body"][:180],
                "kind": source["kind"],
            }
    return {
        "id": message["id"],
        "seq": message["seq"],
        "room_id": message["room_id"],
        "user_id": message["user_id"],
        "name": message["name"],
        "color": (person.color if person else user.get("color")) or "#34527A",
        "avatar_seed": user.get("avatar_seed") or "",
        "avatar_url": avatar_url(message["user_id"], avatar_file, avatar_updated),
        "role": (person.role if person else user.get("role")) or "member",
        "badge_icon": (person.badge_icon if person else user.get("badge_icon")) or "",
        "badge_text": (person.badge_text if person else user.get("badge_text")) or "",
        "kind": message["kind"],
        "body": message["body"],
        "attachment": attachment,
        "quote": quote,
        "reactions": reactions.get(message["id"], {}) if reactions is not None else {},
        "meta": message.get("meta") or {},
        "created_at": message["created_at"],
        "edited_at": message.get("edited_at"),
        "deleted_at": message.get("deleted_at"),
        "pinned_at": message.get("pinned_at"),
    }


def session_user():
    """Return the signed-in user for a request, or None."""
    if not origin_allowed():
        return None
    user_id = str(session.get("user_id", ""))
    if not user_id:
        return None
    return services().store.get_user(user_id)


def login_required(view: Callable):
    def wrapper(*args, **kwargs):
        if not origin_allowed():
            return fail("This request came from another site", 403)
        user = session_user()
        if not user:
            return fail("Join the room first", 401)
        g.user = user
        return view(*args, **kwargs)

    wrapper.__name__ = view.__name__
    return wrapper


def host_required(view: Callable):
    def wrapper(*args, **kwargs):
        from .auth import host_access_allowed

        if not origin_allowed():
            return fail("This request came from another site", 403)
        if not host_access_allowed(services().config):
            return fail("Open the host console from this machine and sign in", 403)
        return view(*args, **kwargs)

    wrapper.__name__ = view.__name__
    return wrapper


def room_for_user(room_id: str, user_id: str) -> tuple[dict[str, Any] | None, str]:
    room = services().store.get_room(room_id)
    if not room:
        return None, "That room does not exist"
    if room["id"] != MAIN_ROOM and not services().store.is_member(room_id, user_id):
        return None, "Join that room first"
    return room, ""
