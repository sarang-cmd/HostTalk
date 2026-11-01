"""Custom emoji. The host adds them, everyone reacts with them."""

from __future__ import annotations

import contextlib
import os
import secrets

from flask import Blueprint, g, request, send_file

from .api_common import fail, login_required, ok, services, session_user
from .api_files import image_suffix
from .auth import ROLE_HOST, ValidationError, clean_emoji_name, host_session

bp = Blueprint("emoji", __name__)

MAX_EMOJI_BYTES = 512 * 1024
MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
}


def _folder():
    path = services().config.upload_dir / "emoji"
    path.mkdir(parents=True, exist_ok=True)
    return path


def public_emoji(emoji: dict) -> dict:
    return {
        "id": emoji["id"],
        "name": emoji["name"],
        "token": f"custom:{emoji['id']}",
        "url": f"/api/emoji/{emoji['id']}/image",
    }


def all_emoji() -> list[dict]:
    return [public_emoji(emoji) for emoji in services().store.list_custom_emoji()]


@bp.get("/api/emoji")
@login_required
def list_emoji():
    return ok(emoji=all_emoji())


@bp.post("/api/emoji")
@login_required
def add_emoji():
    svc = services()
    user = g.user
    if (user.get("role") or "member") != ROLE_HOST:
        return fail("Only the host adds custom emoji", 403, field="name")
    file = request.files.get("file") or request.files.get("emoji")
    if file is None or not file.filename:
        return fail("Choose a picture for the emoji", 400, field="file")
    try:
        name = clean_emoji_name(request.form.get("name"))
    except ValidationError as exc:
        return fail(exc.message, exc.status, field="name")
    if svc.store.get_custom_emoji_by_name(name):
        return fail("That emoji name is taken", 409, field="name")
    data = file.stream.read(MAX_EMOJI_BYTES + 1)
    if not data:
        return fail("That picture is empty", 400, field="file")
    if len(data) > MAX_EMOJI_BYTES:
        return fail("Emoji pictures limit is 512 KB", 413, field="file")
    suffix = image_suffix(data)
    if not suffix or suffix == ".avif":
        return fail("Use a PNG, JPEG, GIF, or WebP picture", 415, field="file")
    stored_name = f"{secrets.token_hex(8)}{suffix}"
    (_folder() / stored_name).write_bytes(data)
    emoji = svc.store.add_custom_emoji(name, stored_name, user["id"])
    public = public_emoji(emoji)
    svc.broker.broadcast("emoji.changed", {"emoji": all_emoji()})
    svc.logger.info(
        "Custom emoji: %s", name, extra={"event": "emoji.add", "user": user["name"], "detail": name}
    )
    return ok(emoji=public, all=all_emoji())


@bp.delete("/api/emoji/<emoji_id>")
@login_required
def delete_emoji(emoji_id: str):
    svc = services()
    user = g.user
    if (user.get("role") or "member") != ROLE_HOST:
        return fail("Only the host removes custom emoji", 403)
    emoji = svc.store.delete_custom_emoji(emoji_id)
    if not emoji:
        return fail("That emoji is gone", 404)
    path = _folder() / os.path.basename(emoji["stored_name"])
    with contextlib.suppress(OSError):
        path.unlink(missing_ok=True)
    svc.broker.broadcast("emoji.changed", {"emoji": all_emoji()})
    return ok(all=all_emoji())


@bp.get("/api/emoji/<emoji_id>/image")
def emoji_image(emoji_id: str):
    svc = services()
    if not session_user() and not host_session():
        return fail("Join the room first", 401)
    emoji = svc.store.get_custom_emoji(emoji_id)
    if not emoji:
        return fail("That emoji is gone", 404)
    path = _folder() / os.path.basename(emoji["stored_name"])
    if not path.exists():
        return fail("That emoji is gone", 404)
    response = send_file(
        path,
        mimetype=MIME.get(path.suffix.lower(), "application/octet-stream"),
        conditional=True,
        max_age=86400,
    )
    response.headers["Cache-Control"] = "private, max-age=86400"
    return response
