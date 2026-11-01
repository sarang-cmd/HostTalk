"""Store behaviour: names, device keys, rooms, pagination, reactions, nicknames."""

from __future__ import annotations

import time


def test_device_key_owns_the_name(services):
    store = services.store
    user, error = store.claim_name("Mara", "device-a")
    assert error == "" and user["name"] == "Mara"

    again, error = store.claim_name("Mara", "device-a")
    assert error == "" and again["id"] == user["id"]

    other, error = store.claim_name("Mara", "device-b")
    assert other is None
    assert "another device" in error


def test_names_are_unique_case_insensitive(services):
    store = services.store
    store.claim_name("Mara", "device-a")
    taken, error = store.claim_name("mara", "device-b")
    assert taken is None
    assert error


def test_nickname_change_is_logged(services):
    store = services.store
    user, _ = store.claim_name("Mara", "device-a")
    renamed = store.rename_user(user["id"], "Mara B", ip="10.0.0.5")
    assert renamed["name"] == "Mara B"
    entries = store.nickname_log(limit=10)
    assert entries[0]["old_name"] == "Mara"
    assert entries[0]["new_name"] == "Mara B"
    assert entries[0]["ip"] == "10.0.0.5"
    assert renamed["last_nick_at"] > time.time() - 5


def test_nickname_cooldown_value(services):
    from hosttalk.auth import NICKNAME_COOLDOWN_SECONDS

    assert NICKNAME_COOLDOWN_SECONDS == 3600


def test_messages_paginate_by_sequence(services):
    store = services.store
    user, _ = store.claim_name("Mara", "device-a")
    for index in range(60):
        store.add_message("main", user["id"], user["name"], f"message {index}")
    page = store.list_messages("main", limit=50)
    assert len(page) == 50
    assert page[-1]["body"] == "message 59"

    older = store.list_messages("main", before_seq=page[0]["seq"], limit=50)
    assert len(older) == 10
    assert older[-1]["body"] == "message 9"


def test_reaction_toggles(services):
    store = services.store
    user, _ = store.claim_name("Mara", "device-a")
    message = store.add_message("main", user["id"], user["name"], "hello")
    marks = store.toggle_reaction(message["id"], user["id"], "👍")
    assert marks["👍"] == [user["id"]]
    assert store.reactions_for([message["id"]])[message["id"]]["👍"] == [user["id"]]
    store.toggle_reaction(message["id"], user["id"], "👍")
    assert store.reactions_for([message["id"]]) == {}


def test_group_room_member_count(services):
    store = services.store
    owner, _ = store.claim_name("Mara", "device-a")
    room = store.create_room("Workshop", owner["id"], kind="group", member_limit=20)
    store.add_member(room["id"], owner["id"])
    second, _ = store.claim_name("Jonas", "device-b")
    assert store.add_member(room["id"], second["id"])
    assert store.member_count(room["id"]) == 2
    assert store.get_room(room["id"])["member_limit"] == 20


def test_direct_room_is_reused(services):
    store = services.store
    mara, _ = store.claim_name("Mara", "device-a")
    jonas, _ = store.claim_name("Jonas", "device-b")
    first = store.create_room("Mara and Jonas", mara["id"], kind="dm", member_limit=2)
    store.add_member(first["id"], mara["id"])
    store.add_member(first["id"], jonas["id"])
    assert store.find_dm_room(mara["id"], jonas["id"])["id"] == first["id"]


def test_invite_use_limit(services):
    store = services.store
    owner, _ = store.claim_name("Mara", "device-a")
    room = store.create_room("Workshop", owner["id"], kind="group")
    invite = store.create_invite(room["id"], owner["id"], max_uses=1)
    store.use_invite(invite["code"])
    assert store.get_invite(invite["code"])["uses"] == 1


def test_clear_room_keeps_the_room(services):
    store = services.store
    user, _ = store.claim_name("Mara", "device-a")
    store.add_message("main", user["id"], user["name"], "one")
    store.add_message("main", user["id"], user["name"], "two")
    removed = store.clear_room("main")
    assert removed == 2
    assert store.get_room("main") is not None
    assert store.count_messages("main") == 0


def test_export_includes_messages(services):
    store = services.store
    user, _ = store.claim_name("Mara", "device-a")
    store.add_message("main", user["id"], user["name"], "export me")
    exported = store.export_messages("main")
    assert any(item["body"] == "export me" for item in exported)


def test_attachment_digest_is_stored(services):
    store = services.store
    user, _ = store.claim_name("Mara", "device-a")
    attachment = store.add_attachment(
        filename="notes.txt",
        mime="text/plain",
        size=12,
        stored_name="abc.txt",
        uploader=user["id"],
        sha256="0" * 64,
    )
    assert store.get_attachment(attachment["id"])["sha256"] == "0" * 64
