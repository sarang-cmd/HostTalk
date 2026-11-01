"""Config loading, validation, redaction, and environment overrides."""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from hosttalk.config import DEFAULT_PORT, Config, ConfigError


def test_default_port_is_not_6767():
    assert DEFAULT_PORT == 7284


def test_password_is_hashed_not_stored(data_dir: Path):
    config = Config.load(data_dir)
    config.set_password("frontroom")
    written = json.loads((data_dir / "config.json").read_text())
    assert "frontroom" not in json.dumps(written)
    assert written["password_hash"].startswith("$2b$")
    assert config.verify_password("frontroom")
    assert not config.verify_password("backroom")


def test_config_file_is_private(data_dir: Path):
    Config.load(data_dir)
    mode = stat.S_IMODE((data_dir / "config.json").stat().st_mode)
    assert mode == 0o600


def test_invalid_port_is_rejected(data_dir: Path):
    config = Config.load(data_dir)
    with pytest.raises((ConfigError, ValueError)):
        config.update({"port": 80})


def test_environment_overrides_file(data_dir: Path, monkeypatch):
    config = Config.load(data_dir)
    config.update({"port": 7300})
    monkeypatch.setenv("HOSTTALK_PORT", "7311")
    reloaded = Config.load(data_dir)
    assert reloaded.port == 7311


def test_redaction_hides_secrets(data_dir: Path):
    config = Config.load(data_dir)
    config.set_password("frontroom")
    config.update({"klipy_key": "abc123", "localsend": {"pin": "9911"}})
    shown = config.redacted()
    assert shown["password_hash"] == "set"
    assert shown["klipy_key"] == "set"
    assert shown["host_password_hash"] == "set"
    assert shown["localsend"]["pin"] == "set"
    assert "secret_key" not in json.dumps(shown) or shown["secret_key"] == "set"


def test_setup_flag_tracks_password(data_dir: Path):
    config = Config.load(data_dir)
    assert not config.setup_complete
    config.set_password("four")
    assert config.setup_complete


def test_upload_limit_follows_settings(data_dir: Path):
    config = Config.load(data_dir)
    config.update({"max_upload_mb": 4})
    assert config.upload_limit_bytes == 4 * 1024 * 1024
