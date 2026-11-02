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
