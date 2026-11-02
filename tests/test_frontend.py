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
