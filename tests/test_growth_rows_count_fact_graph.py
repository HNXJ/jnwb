"""The `scripts/` line count in the state growth row covers the whole scripts tree.

`growth_rows` reports the lines of the generator scripts per release. A package under
`scripts/` (the fact-graph modules) must count too, or its growth is invisible in the row.
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts.reconstruct_state import growth_rows  # noqa: E402


def _lines(path: pathlib.Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def test_scripts_row_counts_fact_graph_modules():
    package_files = sorted((REPO_ROOT / "scripts" / "fact_graph").glob("*.py"))
    assert package_files, "fixture must have a scripts/fact_graph package to count"

    expected = sum(_lines(p) for p in (REPO_ROOT / "scripts").glob("*.py"))
    expected += sum(_lines(p) for p in package_files)

    match = re.search(r"`scripts/` (\d+)", growth_rows())
    assert match is not None, "growth row has no scripts/ cell"
    assert int(match.group(1)) == expected
