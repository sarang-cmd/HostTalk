"""Validation helpers, rate limits, and the preview URL guard."""

from __future__ import annotations

import pytest

from hosttalk.auth import (
    COLOR_GRID,
    RateLimiter,
    ValidationError,
    clean_color,
    clean_emoji,
    clean_message,
    clean_name,
    clean_room_name,
    luminance_contrast,
)
from hosttalk.previews import PreviewError, validate_url


def test_names_are_trimmed_and_bounded():
    assert clean_name("  Mara  ") == "Mara"
    with pytest.raises(ValidationError):
        clean_name("")
    with pytest.raises(ValidationError):
        clean_name("x" * 40)


def test_names_reject_control_characters():
    with pytest.raises(ValidationError):
        clean_name("Mara\x00")


def test_message_whitespace_collapses():
    assert clean_message("hello\n\n\nworld") == "hello\n\nworld"
    with pytest.raises(ValidationError):
        clean_message("")
    with pytest.raises(ValidationError):
        clean_message("x" * 4001)


def test_room_names_need_letters():
    assert clean_room_name(" Kitchen plans ") == "Kitchen plans"
    with pytest.raises(ValidationError):
        clean_room_name("")
    with pytest.raises(ValidationError):
        clean_room_name("!!!")


def test_colors_come_from_the_grid():
    assert clean_color(COLOR_GRID[3]) == COLOR_GRID[3]
    with pytest.raises(ValidationError):
        clean_color("#123456")


def test_palette_contrast_stays_readable():
    for color in COLOR_GRID:
        assert luminance_contrast(color) >= 4.5


def test_any_emoji_is_a_valid_reaction():
    assert clean_emoji("👍") == "👍"
    assert clean_emoji("🚀") == "🚀"
    assert clean_emoji("🧑‍🚀") == "🧑‍🚀"
    assert clean_emoji("custom:e_abc123") == "custom:e_abc123"
    for text in ("", "hello", "abc👍", "x" * 40):
        with pytest.raises(ValidationError):
            clean_emoji(text)


def test_rate_limiter_locks_after_failures():
    limiter = RateLimiter(limit=2, window=60, lockout=60)
    allowed, _ = limiter.check("1.2.3.4")
    assert allowed
    limiter.hit("1.2.3.4", failed=True)
    limiter.hit("1.2.3.4", failed=True)
    blocked, retry = limiter.check("1.2.3.4")
    assert not blocked
    assert retry > 0


def test_rate_limiter_resets():
    limiter = RateLimiter(limit=1, window=60)
    limiter.hit("5.5.5.5")
    limiter.reset("5.5.5.5")
    allowed, _ = limiter.check("5.5.5.5")
    assert allowed


def test_preview_url_allows_public_http():
    assert validate_url("http://93.184.216.34/page") == "http://93.184.216.34/page"


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://localhost/",
        "http://127.0.0.1/",
        "http://192.168.1.10/",
        "http://[::1]/",
        "javascript:alert(1)",
    ],
)
def test_preview_url_blocks_local_targets(url):
    with pytest.raises(PreviewError):
        validate_url(url)
