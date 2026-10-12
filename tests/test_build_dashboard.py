"""The dashboard data builder: its output validates against the data contract, its counts agree
with the entries they count, its API total is the imported package's and its groups cover it
exactly once, its order rows are the measured tables' rows, its peak-memory rows are the
record's, a CHANGELOG parses to the counts it holds, and an output directory inside the
repository is refused before anything is written."""

from __future__ import annotations

import importlib
import json
import sys
from collections import Counter
from pathlib import Path

import jnwb
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

SCHEMA_PATH = REPO_ROOT / "scripts" / "dashboard" / "data.schema.json"
PEAK_MEMORY_PATH = REPO_ROOT / "artifacts" / "benchmarks" / "peak_memory.json"
ORDER_RECORD_PATH = REPO_ROOT / "artifacts" / "evidence" / "0.2.6" / "computational_order.md"
ORDER_HEADER = ("| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved "
                "| admissible | cls | gap |")

# Two released sections and an [Unreleased] one that must be left out. The first release repeats
# a subsection heading, so its counts add both blocks. The paragraph ends a list and is no entry.
CHANGELOG_FIXTURE = """# Changelog

## [Unreleased]

### Added

- Not released yet.

## [0.3.0] - 2026-02-02

### Added

- First entry with a
  continuation line.
  - nested detail
- Second entry.

### Fixed

- A fix.

### Fixed

- A second fix under the same heading.

## [0.2.0] - 2026-01-01

### Changed

- Old change.

A paragraph after the list, not part of any bullet.

- Bullet after paragraph.
"""


def _builder():
    return importlib.import_module("scripts.build_dashboard")


def _measured_order_rows_on_disk() -> int:
    """Data rows under every measured-order table header, counted from the record alone."""
    rows = 0
    under_header = False
    separator_next = False
    for raw in ORDER_RECORD_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line == ORDER_HEADER:
            under_header = separator_next = True
        elif not under_header:
            continue
        elif separator_next:
            separator_next = False
        elif line.startswith("|"):
            rows += 1
        else:
            under_header = False
    return rows


@pytest.fixture(scope="module")
def data():
    return _builder().build_data()


def test_output_validates_against_the_schema(data):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        missing = [key for key in schema["required"] if key not in data]
        assert not missing, f"required keys absent: {missing}"
    else:
        jsonschema.validate(data, schema)


def test_release_counts_equal_entries_per_kind(data):
    assert data["releases"], "fixture must have releases"
    for release in data["releases"]:
        per_kind = dict(Counter(entry["kind"] for entry in release["entries"]))
        assert release["counts"] == per_kind, release["version"]


def test_api_total_is_len_of_all(data):
    assert Path(jnwb.__file__).resolve().is_relative_to(REPO_ROOT), jnwb.__file__
    assert data["api"]["total"] > 0, "fixture must export symbols"
    assert data["api"]["total"] == len(jnwb.__all__)


def test_peak_memory_operations_equal_the_record(data):
    record = json.loads(PEAK_MEMORY_PATH.read_text(encoding="utf-8"))
    expected = [
        (name, row["peak_mib"], row["added_mib"], row["added_is"])
        for name, row in record["operations"].items()
    ]
    assert expected, "the record must hold operations"
    actual = [
        (op["name"], op["peak_mib"], op["added_mib"], op["added_is"])
        for op in data["performance"]["peak_memory"]["operations"]
    ]
    assert actual == expected


def test_changelog_fixture_parses_to_known_counts(tmp_path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(CHANGELOG_FIXTURE, encoding="utf-8", newline="\n")
    releases = _builder().parse_changelog(path)
    assert [r["version"] for r in releases] == ["0.3.0", "0.2.0"]
    assert releases[0]["counts"] == {"Added": 2, "Fixed": 2}
    assert releases[1]["counts"] == {"Changed": 2}
    assert [e["text"] for e in releases[0]["entries"]] == [
        "First entry with a\n  continuation line.\n  - nested detail",
        "Second entry.",
        "A fix.",
        "A second fix under the same heading.",
    ]
    assert [e["text"] for e in releases[1]["entries"]] == [
        "Old change.",
        "Bullet after paragraph.",
    ]


def test_order_has_one_row_per_measured_table_row(data):
    counted = _measured_order_rows_on_disk()
    assert counted > 0, "fixture must have measured-order tables"
    assert data["order"] is not None, "order must not be null while its record exists"
    assert len(data["order"]) == counted


def test_api_groups_cover_all_exactly_once(data):
    from jnwb._lazy_exports import EXPORT_MODULES

    groups = data["api"]["groups"]
    union = [name for group in groups for name in group["symbols"]]
    assert sorted(union) == sorted(jnwb.__all__)
    home = {name: group["module"] for group in groups for name in group["symbols"]}
    mapped = {name: module for name, module in EXPORT_MODULES.items() if name in home}
    assert mapped, "fixture must map some exports"
    assert len({home[name] for name in mapped}) > 1, "grouping must split the exports"
    for name, module in mapped.items():
        assert home[name] == f"jnwb.{module}", name


def test_out_inside_the_repository_is_refused():
    inside = REPO_ROOT / "_refused_dashboard_out"
    with pytest.raises(ValueError) as info:
        _builder().main(["--out", str(inside)])
    assert "_refused_dashboard_out" in str(info.value)
    assert not inside.exists()
