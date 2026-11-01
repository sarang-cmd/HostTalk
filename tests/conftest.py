"""Shared fixtures. Every test gets a fresh data folder and no network services."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in (
        "HOSTTALK_PORT",
        "HOSTTALK_BIND",
        "HOSTTALK_ROOM_NAME",
        "HOSTTALK_NO_BROWSER",
        "HOSTTALK_CONSOLE_LOCAL_ONLY",
        "HOSTTALK_LOCALSEND",
        "HOSTTALK_LS_PIN",
        "SERVER_PASSWORD",
        "GIPHY_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    path = tmp_path / "data"
    path.mkdir()
    return path


@pytest.fixture
def config(data_dir: Path):
    from hosttalk.config import Config

    loaded = Config.load(data_dir)
    loaded.set_password("frontroom")
    loaded.update({"room_name": "Test room", "setup_complete": True})
    return loaded


@pytest.fixture
def services(config):
    from hosttalk.services import build_services

    built = build_services(config, start_localsend=False)
    yield built
    built.shutdown()


@pytest.fixture
def app(services):
    from hosttalk.app import create_app

    instance = create_app(services)
    instance.config.update(TESTING=True)
    return instance


@pytest.fixture
def client(app):
    return app.test_client()
