"""The project page: React source in landing/, built output in site/.

The built page is committed, so these tests read what a visitor receives.
"""

from __future__ import annotations

import json
import re

from hosttalk.config import project_root

ROOT = project_root()
SITE = ROOT / "site"
LANDING = ROOT / "landing"

REFERENCE = re.compile(r'(?:src|href)="(\./[^"]+)"')


def built_html() -> str:
    return (SITE / "index.html").read_text(encoding="utf-8")


def test_the_page_source_uses_react_and_tailwind():
    package = json.loads((LANDING / "package.json").read_text(encoding="utf-8"))
    dependencies = package["dependencies"]
    dev = package["devDependencies"]
    assert "react" in dependencies
    assert "react-dom" in dependencies
    assert "tailwindcss" in dev
    assert "@tailwindcss/vite" in dev
    assert (LANDING / "src" / "App.tsx").is_file()
    assert (LANDING / "src" / "main.tsx").is_file()


def test_the_build_output_is_committed():
    assert (SITE / "index.html").is_file()
    assets = sorted((SITE / "assets").glob("*"))
    assert any(path.suffix == ".js" for path in assets)
    assert any(path.suffix == ".css" for path in assets)
    assert any(path.suffix == ".woff2" for path in assets)
    assert any(path.suffix == ".png" for path in assets)


def test_every_reference_in_the_build_resolves():
    html = built_html()
    targets = REFERENCE.findall(html)
    assert targets
    missing = [target for target in targets if not (SITE / target).resolve().exists()]
    assert missing == []


def test_references_stay_relative():
    """A page published under a subpath must not reach for a server root."""
    for target in REFERENCE.findall(built_html()):
        assert target.startswith("./")
        assert "/static/" not in target
        assert "http" not in target


def test_the_built_page_carries_head_metadata():
    html = built_html()
    assert "<title>HostTalk" in html
    assert 'name="description"' in html
    assert 'name="viewport"' in html
    assert 'property="og:title"' in html


def test_the_page_explains_itself_without_script():
    html = built_html()
    start = html.index("<noscript>")
    block = html[start : html.index("</noscript>", start)]
    assert "A room for the people on your network." in block
    assert "releases/latest" in block


def test_the_copy_keeps_the_demo_label():
    """Screenshots hold placeholder names, so the page has to say so."""
    source = (LANDING / "src" / "content.ts").read_text(encoding="utf-8")
    assert "Screenshots come from a demo room. The names and messages are placeholders." in source
    hero = (LANDING / "src" / "components" / "Hero.tsx").read_text(encoding="utf-8")
    assert "A room for the people on your network." in hero


def test_the_stylesheet_points_at_local_fonts():
    """Fonts load from the hashed build, never from a third party."""
    stylesheets = sorted((SITE / "assets").glob("*.css"))
    assert stylesheets
    css = "\n".join(path.read_text(encoding="utf-8") for path in stylesheets)
    assert "url(./" in css
    assert "url(/" not in css
    assert "fonts.googleapis" not in css


def test_generated_output_stays_out_of_source_control_noise():
    """The build folder is regenerated, so it holds only the page and hashed assets."""
    names = {path.name for path in SITE.iterdir()}
    assert names == {"index.html", "assets", "favicon.ico"}


def test_source_tree_has_no_installed_packages():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "node_modules/" in ignore
