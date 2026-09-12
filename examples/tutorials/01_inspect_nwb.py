"""Tutorial 1: What is in this NWB file?

Run: python examples/tutorials/01_inspect_nwb.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_TUTORIALS = Path(__file__).resolve().parent
_REPO_ROOT = _TUTORIALS.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_TUTORIALS) not in sys.path:
    sys.path.insert(0, str(_TUTORIALS))

import jnwb
from _support import CODE_LABEL_A, TASK_TABLE, build_canonical_fixture


def main() -> None:
    path, receipt = build_canonical_fixture()
    info = jnwb.inspect(path)

    assert info["session"]["identifier"] == "TEST_SYNTH_CANONICAL"
    assert len(info["acquisitions"]) >= 1
    assert info["units"]["n_rows"] == 2

    table_names = {t["name"] for t in info["interval_tables"]}
    assert TASK_TABLE in table_names
    assert receipt.rf_table in table_names
    assert receipt.flash_table in table_names

    task = next(t for t in info["interval_tables"] if t["name"] == TASK_TABLE)
    col_names = {c["name"] for c in task["columns"]}
    assert "codes" in col_names
    assert "start_time" in col_names
    codes_col = next(c for c in task["columns"] if c["name"] == "codes")
    assert CODE_LABEL_A in codes_col["sample_values"]

    print(f"session: {info['session']['identifier']}")
    print(f"acquisitions: {[a['name'] for a in info['acquisitions']]}")
    print(f"interval tables: {sorted(table_names)}")
    print(f"units: {info['units']['n_rows']} rows")


if __name__ == "__main__":
    main()
