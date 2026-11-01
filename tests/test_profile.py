"""Names, profile pictures, roles, and pins."""

from __future__ import annotations

import io
import struct
import zlib


def _png() -> bytes:
    """Build a valid 1 by 1 PNG at run time."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    body = zlib.compress(b"\x00\x17\x1a\x18")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", body) + chunk(b"IEND", b"")


def join(client, name="", password="frontroom", device_key=""):
    key = device_key or f"device-{name or 'guest'}"
    return client.post(
        "/api/session",
        json={"name": name, "password": password, "device_key": key},
    )


def test_joining_without_a_name_uses_the_house_name(client):
    response = join(client)
    assert response.status_code == 200
    user = response.get_json()["user"]
    assert user["name"] == "John Appleseed"
    assert user["role"] == "host"


def test_a_second_guest_gets_a_numbered_name(app):
    first = app.test_client()
    second = app.test_client()
    assert join(first, device_key="laptop-one").get_json()["user"]["name"] == "John Appleseed"
    assert join(second, device_key="laptop-two").get_json()["user"]["name"] == "John Appleseed 2"


def test_profile_picture_round_trip(client, app):
    user = join(client).get_json()["user"]
    assert user["avatar_url"] == ""

    upload = client.post(
        "/api/me/avatar",
        data={"avatar": (io.BytesIO(_png()), "me.png")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 200, upload.get_json()
    updated = upload.get_json()["user"]
    assert updated["avatar_url"].startswith(f"/api/avatars/{user['id']}")

    picture = client.get(updated["avatar_url"])
    assert picture.status_code == 200
    assert picture.headers["Content-Type"] == "image/png"
    assert picture.data == _png()

    people = client.get("/api/people").get_json()["people"]
    mine = next(person for person in people if person["id"] == user["id"])
    assert mine["avatar_url"] == updated["avatar_url"]

    removed = client.delete("/api/me/avatar")
    assert removed.status_code == 200
    assert removed.get_json()["user"]["avatar_url"] == ""
    assert client.get(updated["avatar_url"]).status_code == 404


def test_profile_picture_must_be_an_image(client):
    join(client)
    response = client.post(
        "/api/me/avatar",
        data={"avatar": (io.BytesIO(b"not a picture"), "notes.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 415
    assert response.get_json()["field"] == "avatar"


def test_roles_decide_who_deletes(app):
    host_client = app.test_client()
    member_client = app.test_client()
    host_client.post("/api/session", json={"name": "Ada", "password": "frontroom", "device_key": "a"})
    member_client.post(
        "/api/session", json={"name": "Rae", "password": "frontroom", "device_key": "b"}
    )

    from_host = host_client.post("/api/messages", json={"room_id": "main", "body": "Hello"}).get_json()
    from_member = member_client.post(
        "/api/messages", json={"room_id": "main", "body": "Hi"}
    ).get_json()

    refused = member_client.delete(f"/api/messages/{from_host['message']['id']}")
    assert refused.status_code == 403

    allowed = host_client.delete(f"/api/messages/{from_member['message']['id']}")
    assert allowed.status_code == 200

    member_me = member_client.get("/api/me").get_json()["user"]
    promoted = host_client.post(
        f"/api/people/{member_me['id']}/role", json={"role": "moderator"}
    )
    assert promoted.status_code == 200
    assert promoted.get_json()["user"]["role"] == "moderator"

    again = member_client.post("/api/messages", json={"room_id": "main", "body": "Second"}).get_json()
    assert member_client.delete(f"/api/messages/{from_host['message']['id']}").status_code == 200
    assert host_client.delete(f"/api/messages/{again['message']['id']}").status_code == 200


def test_only_the_host_changes_roles(app):
    host_client = app.test_client()
    other_client = app.test_client()
    host_client.post("/api/session", json={"name": "Ada", "password": "frontroom", "device_key": "a"})
    other_client.post(
        "/api/session", json={"name": "Rae", "password": "frontroom", "device_key": "b"}
    )
    host_id = host_client.get("/api/me").get_json()["user"]["id"]
    response = other_client.post(f"/api/people/{host_id}/role", json={"role": "moderator"})
    assert response.status_code == 403


def test_pins_need_moderation(client):
    join(client)
    message = client.post("/api/messages", json={"room_id": "main", "body": "Plans"}).get_json()
    message_id = message["message"]["id"]

    pinned = client.post(f"/api/messages/{message_id}/pin", json={"pinned": True})
    assert pinned.status_code == 200
    assert pinned.get_json()["message"]["pinned_at"] is not None

    listing = client.get("/api/rooms/main/pinned").get_json()["messages"]
    assert [item["id"] for item in listing] == [message_id]

    unpinned = client.post(f"/api/messages/{message_id}/pin", json={"pinned": False})
    assert unpinned.get_json()["message"]["pinned_at"] is None
    assert client.get("/api/rooms/main/pinned").get_json()["messages"] == []


def test_members_cannot_pin(app):
    host_client = app.test_client()
    member_client = app.test_client()
    host_client.post("/api/session", json={"name": "Ada", "password": "frontroom", "device_key": "a"})
    member_client.post(
        "/api/session", json={"name": "Rae", "password": "frontroom", "device_key": "b"}
    )
    message = member_client.post("/api/messages", json={"room_id": "main", "body": "Mine"}).get_json()
    response = member_client.post(f"/api/messages/{message['message']['id']}/pin", json={"pinned": True})
    assert response.status_code == 403


def test_console_moves_roles(client):
    joined = join(client).get_json()["user"]
    assert client.post("/api/host/session", json={"password": "frontroom"}).status_code == 200
    response = client.post(f"/api/host/users/{joined['id']}/role", json={"role": "moderator"})
    assert response.status_code == 200
    assert response.get_json()["user"]["role"] == "moderator"
    people = client.get("/api/host/people").get_json()
    assert people["roles"][0]["id"] in {"host", "moderator", "member"}


def test_avatar_needs_a_session(client):
    assert client.get("/api/avatars/nobody").status_code == 401


def test_house_name_is_a_real_name():
    from hosttalk.auth import DEFAULT_NAME, name_or_default

    assert DEFAULT_NAME == "John Appleseed"
    assert name_or_default("   ") == "John Appleseed"
    assert name_or_default(" Mara ") == "Mara"


def test_old_data_folders_gain_the_new_columns(tmp_path):
    import sqlite3

    from hosttalk.store import Store

    path = tmp_path / "old.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            color TEXT NOT NULL DEFAULT '',
            device_key TEXT NOT NULL DEFAULT '',
            avatar_seed TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            last_nick_at REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE messages (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            id TEXT NOT NULL UNIQUE,
            room_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'text',
            body TEXT NOT NULL DEFAULT '',
            attachment_id TEXT,
            quote_id TEXT,
            meta TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL,
            edited_at REAL,
            deleted_at REAL
        );
        INSERT INTO users(id, name, created_at) VALUES('u_old', 'Mara', 1.0);
        """
    )
    connection.commit()
    connection.close()

    store = Store(path)
    try:
        user = store.get_user("u_old")
        assert user["role"] == "member"
        assert user["avatar_file"] == ""
        promoted = store.promote_first_host("u_old")
        assert promoted["role"] == "host"
    finally:
        store.close()


def test_badges_take_one_icon_and_four_characters(client):
    join(client)
    saved = client.patch("/api/me", json={"badge_icon": "shield", "badge_text": "OPS"})
    assert saved.status_code == 200
    user = saved.get_json()["user"]
    assert user["badge_icon"] == "shield"
    assert user["badge_text"] == "OPS"

    message = client.post("/api/messages", json={"room_id": "main", "body": "Hello"}).get_json()
    assert message["message"]["badge_text"] == "OPS"

    too_long = client.patch("/api/me", json={"badge_icon": "shield", "badge_text": "ABCDE"})
    assert too_long.status_code == 400
    assert too_long.get_json()["field"] == "badge_text"

    unknown = client.patch("/api/me", json={"badge_icon": "rocket", "badge_text": "HI"})
    assert unknown.status_code == 400
    assert unknown.get_json()["field"] == "badge_icon"

    cleared = client.patch("/api/me", json={"badge_icon": "", "badge_text": ""})
    assert cleared.get_json()["user"]["badge_text"] == ""


def test_any_emoji_reaction(client):
    join(client)
    message = client.post("/api/messages", json={"room_id": "main", "body": "Ship it"}).get_json()
    message_id = message["message"]["id"]
    for emoji in ("🚀", "🧑‍🚀", "🫡"):
        response = client.post(f"/api/messages/{message_id}/reactions", json={"emoji": emoji})
        assert response.status_code == 200, emoji
        assert emoji in response.get_json()["reactions"]
    plain = client.post(f"/api/messages/{message_id}/reactions", json={"emoji": "yes"})
    assert plain.status_code == 400


def test_only_the_host_adds_custom_emoji(app):
    host_client = app.test_client()
    member_client = app.test_client()
    host_client.post("/api/session", json={"name": "Ada", "password": "frontroom", "device_key": "a"})
    member_client.post(
        "/api/session", json={"name": "Rae", "password": "frontroom", "device_key": "b"}
    )
    refused = member_client.post(
        "/api/emoji",
        data={"name": "party", "file": (io.BytesIO(_png()), "party.png")},
        content_type="multipart/form-data",
    )
    assert refused.status_code == 403

    added = host_client.post(
        "/api/emoji",
        data={"name": "party", "file": (io.BytesIO(_png()), "party.png")},
        content_type="multipart/form-data",
    )
    assert added.status_code == 200, added.get_json()
    emoji = added.get_json()["emoji"]
    assert emoji["token"].startswith("custom:")
    assert host_client.get(emoji["url"]).status_code == 200

    message = host_client.post("/api/messages", json={"room_id": "main", "body": "Hi"}).get_json()
    reacted = host_client.post(
        f"/api/messages/{message['message']['id']}/reactions", json={"emoji": emoji["token"]}
    )
    assert reacted.status_code == 200
    assert emoji["token"] in reacted.get_json()["reactions"]

    assert host_client.delete(f"/api/emoji/{emoji['id']}").status_code == 200
    gone = host_client.post(
        f"/api/messages/{message['message']['id']}/reactions", json={"emoji": emoji["token"]}
    )
    assert gone.status_code == 404


def test_devices_keep_their_name(client):
    first = join(client, "Mara", device_key="laptop-one")
    assert first.get_json()["user"]["name"] == "Mara"
    client.delete("/api/session")
    again = join(client, "Someone Else", device_key="laptop-one")
    assert again.get_json()["user"]["name"] == "Mara"


def test_rooms_inside_rooms(app):
    owner = app.test_client()
    guest = app.test_client()
    owner.post("/api/session", json={"name": "Ada", "password": "frontroom", "device_key": "a"})
    guest.post("/api/session", json={"name": "Rae", "password": "frontroom", "device_key": "b"})

    outer = owner.post(
        "/api/rooms", json={"name": "Studio", "password": "outerpass"}
    ).get_json()["room"]
    inner = owner.post(
        "/api/rooms",
        json={"name": "Corner", "parent_id": outer["id"], "password": "innerpass"},
    ).get_json()["room"]
    assert inner["parent_id"] == outer["id"]

    # The guest sees nothing yet: they are outside the outer room.
    listed = guest.get("/api/rooms").get_json()["rooms"]
    assert all(room["id"] != inner["id"] for room in listed)

    blocked = guest.post(f"/api/rooms/{inner['id']}/enter", json={"password": "innerpass"})
    assert blocked.status_code == 403

    entered_outer = guest.post(f"/api/rooms/{outer['id']}/enter", json={"password": "outerpass"})
    assert entered_outer.status_code == 200
    listed = guest.get("/api/rooms").get_json()["rooms"]
    assert any(room["id"] == inner["id"] and not room["joined"] for room in listed)

    wrong = guest.post(f"/api/rooms/{inner['id']}/enter", json={"password": "nope"})
    assert wrong.status_code == 401
    right = guest.post(f"/api/rooms/{inner['id']}/enter", json={"password": "innerpass"})
    assert right.status_code == 200
    assert right.get_json()["room"]["joined"] is True


def test_host_controls(app):
    host_client = app.test_client()
    member_client = app.test_client()
    joined = join(host_client).get_json()["user"]
    assert joined["role"] == "host"
    join(member_client, "Rae", device_key="rae-laptop")
    assert host_client.post("/api/host/session", json={"password": "frontroom"}).status_code == 200
    saved = host_client.patch(
        "/api/host/settings",
        json={"read_only": True, "slow_mode_seconds": 30, "notice_text": "Back at six"},
    )
    assert saved.status_code == 200
    status = member_client.get("/api/status").get_json()["server"]
    assert status["read_only"] is True
    assert status["slow_mode_seconds"] == 30
    assert status["notice_text"] == "Back at six"

    blocked = member_client.post("/api/messages", json={"room_id": "main", "body": "Hello"})
    assert blocked.status_code == 403

    allowed = host_client.post("/api/messages", json={"room_id": "main", "body": "Hello"})
    assert allowed.status_code == 200
