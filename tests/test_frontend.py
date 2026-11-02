"""Keeps the browser files loading.

The tests here parse every script under `static/js` and check that each asset
the scripts ask for is on disk. A broken script leaves a blank room and no
error a server test would catch.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = sorted((ROOT / "static" / "js").glob("*.js"))
NODE = shutil.which("node")


@pytest.mark.parametrize("path", SCRIPTS, ids=[path.name for path in SCRIPTS])
def test_every_script_parses_as_a_module(path: Path):
    if NODE is None:
        pytest.skip("node is not installed here")
    result = subprocess.run(
        [NODE, "--input-type=module", "--check"],
        stdin=path.open("rb"),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_every_static_asset_the_scripts_ask_for_is_on_disk():
    wanted = set()
    for path in SCRIPTS:
        text = path.read_text(encoding="utf-8")
        wanted.update(re.findall(r'["\']/static/([A-Za-z0-9_.-]+\.(?:mp3|png|svg|woff2?))["\']', text))
    missing = sorted(name for name in wanted if not (ROOT / "static" / name).exists())
    assert missing == []


def test_the_site_pages_carry_one_nav_and_one_footer():
    """Every public page offers the same links in the header and the footer."""
    import re

    pages = ["about.html", "landing.html", "privacy.html", "stats.html", "terms.html"]
    heads, feet = {}, {}
    for name in pages:
        body = (ROOT / "templates" / name).read_text(encoding="utf-8")
        heads[name] = re.findall(r'<nav class="site-nav".*?</nav>', body, re.S)[0]
        feet[name] = re.findall(r"<footer.*?</footer>", body, re.S)[0]

    def links(block: str) -> list[str]:
        return re.findall(r'<a href="([^"]+)"', block)

    first = links(heads[pages[0]])
    for name, block in heads.items():
        assert links(block) == first, name
    first_foot = links(feet[pages[0]])
    for name, block in feet.items():
        assert links(block) == first_foot, name


def test_every_page_states_a_title_and_a_theme_colour():
    import re

    for path in sorted((ROOT / "templates").glob("*.html")):
        body = path.read_text(encoding="utf-8")
        assert re.search(r"<title>[^<]+</title>", body), path.name
        assert 'name="theme-color"' in body, path.name
