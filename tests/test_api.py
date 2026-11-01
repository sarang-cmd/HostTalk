"""HTTP behaviour: pages, headers, join flow, messages, host console, limits."""

from __future__ import annotations

import io


def join(client, name="Mara", password="frontroom"):
    return client.post(
        "/api/session",
        json={"name": name, "password": password, "device_key": f"device-{name.lower()}"},
    )


def test_public_pages_load(client):
    for path in ("/", "/about", "/terms", "/privacy", "/console"):
        response = client.get(path)
        assert response.status_code == 200, path


def test_unknown_page_uses_error_template(client):
    response = client.get("/nothing-here")
    assert response.status_code == 404
    body = response.get_data(as_text=True)
    assert "Open the room" in body


def test_security_headers(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert "unsafe-eval" not in response.headers["Content-Security-Policy"]


def test_api_is_marked_no_store(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    assert "no-store" in response.headers["Cache-Control"]
    payload = response.get_json()
    assert payload["server"]["port"] == 7284
    assert payload["server"]["max_upload_mb"] == 20


def test_healthz_reports_counts(client):
    payload = client.get("/healthz").get_json()
    assert payload["status"] == "ok"
    assert payload["port"] == 7284


def test_wrong_password_is_rejected(client):
    response = join(client, password="wrong")
    assert response.status_code == 401
    assert response.get_json()["field"] == "password"


def test_join_sets_session_and_lists_rooms(client):
    response = join(client)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["user"]["name"] == "Mara"
    assert payload["user"]["color"].startswith("#")
    assert any(room["id"] == "main" for room in payload["rooms"])

    me = client.get("/api/me").get_json()
    assert me["user"]["name"] == "Mara"


def test_duplicate_name_from_other_device_is_refused(client):
    join(client, "Mara")
    second = client.post(
        "/api/session",
        json={"name": "Mara", "password": "frontroom", "device_key": "another-device"},
    )
    assert second.status_code == 409


def test_message_round_trip(client):
    join(client)
    created = client.post("/api/messages", json={"room_id": "main", "body": "hello there"})
    assert created.status_code == 200
    message = created.get_json()["message"]
    assert message["body"] == "hello there"

    listing = client.get("/api/rooms/main/messages").get_json()
    assert listing["messages"][-1]["id"] == message["id"]


def test_message_length_is_enforced(client):
    join(client)
    response = client.post("/api/messages", json={"room_id": "main", "body": "x" * 5000})
    assert response.status_code == 400


def test_reply_quote_must_match_room(client):
    join(client)
    room = client.post("/api/rooms", json={"name": "Workshop"}).get_json()["room"]
    created = client.post("/api/messages", json={"room_id": room["id"], "body": "in the room"})
    message_id = created.get_json()["message"]["id"]
    response = client.post(
        "/api/messages", json={"room_id": "main", "body": "wrong room", "quote_id": message_id}
    )
    assert response.status_code == 400


def test_upload_rejects_empty_file(client):
    join(client)
    response = client.post(
        "/api/uploads",
        data={"file": (io.BytesIO(b""), "empty.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


def test_upload_accepts_text_and_serves_it(client):
    join(client)
    response = client.post(
        "/api/uploads",
        data={"file": (io.BytesIO(b"notes for the room"), "notes.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    attachment = response.get_json()["attachment"]
    assert attachment["filename"] == "notes.txt"
    assert attachment["size"] == 18
    download = client.get(f"/api/files/{attachment['id']}")
    assert download.status_code == 200
    assert download.data == b"notes for the room"


def test_host_console_requires_password(client):
    response = client.post("/api/host/session", json={"password": "wrong"})
    assert response.status_code == 401
    blocked = client.get("/api/host/summary")
    assert blocked.status_code == 403


def test_host_console_summary(client):
    assert client.post("/api/host/session", json={"password": "frontroom"}).status_code == 200
    payload = client.get("/api/host/summary").get_json()
    assert payload["server"]["port"] == 7284
    assert payload["config"]["password_hash"] == "set"
    assert isinstance(payload["checks"], list) and payload["checks"]
    rooms = payload["rooms"]
    assert any(room["kind"] == "main" for room in rooms)


def test_setup_runs_once(client):
    first = client.post(
        "/api/setup", json={"room_name": "Second room", "password": "another", "port": 7301}
    )
    assert first.status_code == 409


def test_setup_is_local_only(client, services):
    services.config.update({"setup_complete": False})
    response = client.post(
        "/api/setup",
        json={"room_name": "Second room", "password": "another"},
        environ_base={"REMOTE_ADDR": "192.168.1.40"},
    )
    assert response.status_code == 403


def test_room_creation_and_leave(client):
    join(client)
    created = client.post("/api/rooms", json={"name": "Workshop"}).get_json()["room"]
    assert created["kind"] == "group"
    assert created["member_limit"] == 20
    left = client.post(f"/api/rooms/{created['id']}/leave")
    assert left.status_code == 200
    rooms = client.get("/api/rooms").get_json()["rooms"]
    assert all(room["id"] != created["id"] for room in rooms)


def test_dm_needs_another_person(client):
    join(client)
    response = client.post("/api/dm", json={"user_id": "missing"})
    assert response.status_code == 404


def test_direct_thread_between_two_people(client, services):
    join(client, "Mara")
    store = services.store
    other, _ = store.claim_name("Jonas", "device-jonas")
    opened = client.post("/api/dm", json={"user_id": other["id"]})
    assert opened.status_code == 200
    room = opened.get_json()["room"]
    assert room["kind"] == "dm"
    again = client.post("/api/dm", json={"user_id": other["id"]}).get_json()["room"]
    assert again["id"] == room["id"]


def test_search_finds_text(client):
    join(client)
    client.post("/api/messages", json={"room_id": "main", "body": "the kettle is on"})
    found = client.get("/api/search?q=kettle").get_json()
    assert any("kettle" in item["body"] for item in found["results"])


def test_preview_blocks_private_addresses(client):
    join(client)
    response = client.get("/api/previews?url=http://127.0.0.1:8000/secret")
    assert response.status_code == 422
    assert response.get_json()["ok"] is False


def test_gif_search_without_key_says_so(client):
    join(client)
    response = client.get("/api/gifs?q=hello")
    assert response.status_code == 409
    assert "key" in response.get_json()["message"].lower()


def test_logs_are_readable_by_the_host(client):
    assert client.post("/api/host/session", json={"password": "frontroom"}).status_code == 200
    payload = client.get("/api/host/logs?limit=20").get_json()
    assert "records" in payload


def test_disconnect_requires_host(client):
    join(client)
    response = client.post("/api/host/users/someone/disconnect")
    assert response.status_code == 403
