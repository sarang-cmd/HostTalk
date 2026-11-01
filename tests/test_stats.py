"""The stats module and the pages built on it."""

from __future__ import annotations

from hosttalk.config import project_root
from hosttalk.stats import (
    human_bytes,
    human_duration,
    instance_stats,
    runtime_stats,
    source_stats,
)


def test_human_bytes_uses_one_unit():
    assert human_bytes(0) == "0 B"
    assert human_bytes(999) == "999 B"
    assert human_bytes(1024) == "1.0 KB"
    assert human_bytes(20 * 1024 * 1024) == "20.0 MB"
    assert human_bytes(3 * 1024**3) == "3.0 GB"


def test_human_duration_stops_at_two_units():
    assert human_duration(-5) == "0 s"
    assert human_duration(45) == "45 s"
    assert human_duration(90) == "1 m 30 s"
    assert human_duration(3700) == "1 h 1 m"
    assert human_duration(90000) == "1 d 1 h"


def test_source_stats_counts_this_checkout():
    figures = source_stats()
    names = [area["name"] for area in figures["areas"]]
    assert names == [
        "Server package",
        "Room scripts",
        "Styles",
        "Templates",
        "Tests",
        "Deployment",
        "Docs",
    ]
    assert figures["totals"]["files"] > 30
    assert figures["totals"]["lines"] > 5000
    assert figures["test_cases"] >= 61
    assert figures["test_files"] >= 4
    assert figures["screenshots"] >= 10
    assert figures["packages"] >= 5
    shares = sum(area["share"] for area in figures["areas"])
    assert abs(shares - 100) < 1


def test_source_stats_leaves_bundled_libraries_out():
    figures = source_stats()
    scripts = next(area for area in figures["areas"] if area["name"] == "Room scripts")
    assert scripts["files"] == len(list((project_root() / "static" / "js").glob("*.js")))
    assert scripts["files"] < figures["totals"]["files"]
    vendored = [item["name"] for item in figures["vendored"]]
    assert "fflate.min.js" in vendored


def test_runtime_stats_reports_real_versions():
    figures = runtime_stats()
    assert figures["version"] == "2.0.0"
    assert figures["codename"] == "Roomtone"
    assert figures["python"].startswith("3.")
    assert figures["flask"] != "not installed"
    assert figures["sqlite"]


def test_instance_stats_match_the_store(services):
    figures = instance_stats(services)
    stored = services.store.stats()
    assert figures["messages"] == stored["messages"]
    assert figures["rooms"] == stored["rooms"]
    assert figures["people"] == stored["users"]
    assert figures["port"] == services.config.port
    assert figures["uptime"] >= 0
    assert figures["disk_bytes"] >= figures["db_bytes"]
