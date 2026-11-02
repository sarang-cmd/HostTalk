"""Keeps the documents in step with the code.

Each test reads a claim a reader acts on and checks it against the source:
the version string, the service name, the route table, the schema, and the
palette. A rename that misses one place fails here before a reader finds it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def route_table() -> set[tuple[str, str]]:
    block = read("README.md").split("## HTTP API")[1].split("Host routes need")[0]
    return set(re.findall(r"\|\s*(GET|POST|PATCH|DELETE)\s*\|\s*`([^`]+)`", block))


def real_routes() -> set[tuple[str, str]]:
    found = set()
    for path in sorted((ROOT / "hosttalk").glob("api_*.py")):
        text = path.read_text(encoding="utf-8")
        for method, route in re.findall(r'@bp\.(get|post|patch|delete)\("([^"]+)"\)', text):
            found.add((method.upper(), route))
    return found


def normalise(route: str) -> str:
    return re.sub(r"<[a-z_]+>", "<id>", route)


@pytest.mark.parametrize(
    ("path", "pattern"),
    [
        ("landing/package.json", r'"version": "{version}"'),
        ("deploy/docker-compose.yml", r"hosttalk:{version}"),
        ("static/sw.js", r'hosttalk-shell-{version}-'),
        ("README.md", r"Version {version}, codename {codename}"),
        ("CHANGELOG.md", r"## {version} {codename}"),
    ],
)
def test_the_version_is_the_same_everywhere(path: str, pattern: str):
    version = re.search(r'__version__ = "([^"]+)"', read("hosttalk/version.py")).group(1)
    codename = re.search(r'CODENAME = "([^"]+)"', read("hosttalk/version.py")).group(1)
    wanted = pattern.format(version=re.escape(version), codename=re.escape(codename))
    assert re.search(wanted, read(path)), f"{path} does not carry {version} {codename}"


def test_no_page_names_the_old_gif_service():
    for path in [*sorted((ROOT / "templates").glob("*.html")), *sorted((ROOT / "static/js").glob("*.js"))]:
        text = path.read_text(encoding="utf-8")
        assert "GIPHY" not in text and "giphy" not in text, path.name


def test_the_route_table_covers_every_route():
    documented = {(method, normalise(route)) for method, route in route_table()}
    actual = {(method, normalise(route)) for method, route in real_routes()}
    assert sorted(actual - documented) == []
    assert sorted(documented - actual) == []


def test_the_table_count_matches_the_schema():
    tables = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", read("hosttalk/store.py"))
    assert f"{len(tables)} tables" in read("README.md")


def test_the_palette_size_matches_the_readme():
    block = re.search(r"COLOR_GRID = \[([^\]]*)\]", read("hosttalk/auth.py"), re.S).group(1)
    colors = re.findall(r"#[0-9A-Fa-f]{6}", block)
    assert f"{len(colors)} step palette" in read("README.md")


def command_block() -> str:
    return read("README.md").split("## Command line")[1].split("## HTTP API")[0]


def documented_commands() -> dict[str, set[str]]:
    """Each line of the block opens with a command and names its flags."""
    found: dict[str, set[str]] = {}
    for line in command_block().splitlines():
        line = line.strip()
        if not line.startswith("hosttalk "):
            continue
        command = line.split()[1]
        found[command] = set(re.findall(r"--[a-z-]+", line))
    return found


def parser_flag_groups() -> dict[str, list[set[str]]]:
    """Ask the command line itself, so the flags come from the code.

    A line such as ``--host BIND, --bind BIND`` carries two names for one
    setting, so each line becomes one group. One name in the group is enough.
    """
    import subprocess
    import sys

    root = Path(__file__).resolve().parent.parent
    groups: dict[str, list[set[str]]] = {}
    for command in ["serve", "app", "setup", "config", "reset-password", "doctor", "version"]:
        result = subprocess.run(
            [sys.executable, "-m", "hosttalk", command, "--help"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        found: list[set[str]] = []
        for line in result.stdout.splitlines():
            if not line.startswith("  -"):
                continue
            flags = set(re.findall(r"--[a-z][a-z-]*", line)) - {"--help"}
            if flags:
                found.append(flags)
        groups[command] = found
    return groups


def test_the_command_block_names_every_flag():
    documented = documented_commands()
    groups = parser_flag_groups()
    assert sorted(groups) == sorted(documented)
    for command, group_list in groups.items():
        for group in group_list:
            assert group & documented[command], f"{command} hides {sorted(group)}"
        known = set().union(*group_list) if group_list else set()
        assert sorted(documented[command] - known) == [], f"{command} names a flag the code lacks"


def test_the_layout_names_every_module():
    block = read("README.md").split("## Repository layout")[1].split("## Credits")[0]
    listed = set(re.findall(r"^  (\w+\.py)\s{2,}", block, re.M))
    # Package plumbing is not something a reader navigates to, so it stays out.
    real = {path.name for path in (ROOT / "hosttalk").glob("*.py") if not path.name.startswith("__")}
    assert sorted(real - listed) == [], "a module is missing from the layout"
    assert sorted(listed - real) == [], "the layout names a module that is gone"


def test_every_screenshot_in_the_table_exists():
    block = read("docs/SCREENSHOTS.md").split("## Files")[1].split("## Social preview")[0]
    names = re.findall(r"\| `([^`]+)`", block)
    assert names, "the screenshot table went missing"
    missing = [
        name
        for name in names
        if not (ROOT / "static" / "screenshots" / name).exists() and not (ROOT / name).exists()
    ]
    assert missing == []


def test_the_build_workflow_validates():
    """A quote inside a condition stops GitHub from starting any job.

    The build sat broken for a day because the publish job carried
    `if: startsWith(github.ref, 'refs/tags/')`. Every push recorded a failed run
    with no jobs. A tag push now uses a shell check instead, and this test keeps
    quoted conditions out.
    """
    import yaml

    workflow = yaml.safe_load(read(".github/workflows/build.yml"))
    jobs = workflow["jobs"]
    assert {"build-windows", "build-macos", "build-linux", "publish"} <= set(jobs)

    for name, job in jobs.items():
        assert job.get("runs-on"), f"{name} has no runner"
        entries = [job, *job.get("steps", [])]
        for entry in entries:
            condition = entry.get("if")
            if condition:
                assert "'" not in condition and '"' not in condition, f"{name} quotes a condition"

    publish = jobs["publish"]
    steps = " ".join(str(step.get("run", "")) for step in publish["steps"])
    assert "gh release create" in steps
    assert "gh release upload" in steps

    # A tag push has to reach the workflow at all.
    assert "tags:" in read(".github/workflows/build.yml")


def test_the_icon_sources_cover_every_size():
    """Windows takes icon.ico, macOS builds its icns from the square sources."""
    from PIL import Image

    ico = Image.open(ROOT / "icon.ico")
    sizes = {size for size in ico.info.get("sizes", set())}
    assert (256, 256) in sizes, "Windows wants a 256 frame"
    assert (16, 16) in sizes, "the tab and taskbar want a 16 frame"

    for name, expected in (("icon-512.png", 512), ("icon-1024.png", 1024)):
        image = Image.open(ROOT / "static" / "icons" / name)
        assert image.size == (expected, expected)
