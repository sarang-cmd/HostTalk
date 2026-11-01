"""The static landing page kept at the repository root.

It is published as a file, so nothing at runtime would notice a broken path.
These tests read the file and check what it points at.
"""

from __future__ import annotations

import re

from hosttalk.config import project_root

REFERENCES = re.compile(r'(?:src|href)="([^"#][^"]*)"')


def landing_text() -> str:
    return (project_root() / "index.html").read_text(encoding="utf-8")


def local_references() -> list[str]:
    found = []
    for target in REFERENCES.findall(landing_text()):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        found.append(target)
    return found


def test_landing_page_exists_at_the_root():
    path = project_root() / "index.html"
    assert path.is_file()
    body = path.read_text(encoding="utf-8")
    assert "<title>" in body
    assert "A room for the people on your network." in body


def test_landing_page_references_exist():
    root = project_root()
    missing = [target for target in local_references() if not (root / target).exists()]
    assert missing == []


def test_landing_page_uses_the_shared_stylesheets():
    body = landing_text()
    for sheet in ("tokens.css", "base.css", "marketing.css"):
        assert f"static/css/{sheet}" in body


def test_stylesheet_font_paths_resolve():
    """tokens.css sits in static/css, so its font URLs climb one folder."""
    css = (project_root() / "static" / "css" / "tokens.css").read_text(encoding="utf-8")
    fonts = re.findall(r'url\("([^"]+)"\)', css)
    assert fonts
    base = project_root() / "static" / "css"
    missing = [name for name in fonts if not (base / name).resolve().exists()]
    assert missing == []


def test_landing_page_has_one_main_heading():
    body = landing_text()
    assert body.count("<h1>") == 1
    assert body.count("<main") == 1


def test_landing_page_labels_simulated_content():
    body = landing_text()
    assert "Screenshots come from a demo room" in body
    assert "placeholders" in body
