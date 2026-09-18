"""Tutorial 01: NWB Basics — Inspecting Files and Discovering Layouts.

Run: python examples/tutorials/01_nwb_basics.py
"""

from __future__ import annotations

import sys

import tempfile
from pathlib import Path

# This file is run from a checkout, so prefer that checkout over any installed jnwb:
# Python puts this directory on sys.path, not the repository root. A run that is
# deliberately qualifying an installed copy says so with JNWB_EXPECTED_PACKAGE_ROOT,
# and then this guard stands aside -- otherwise it would quietly redirect CI's
# installed-wheel tutorial step back to the checkout.
import os

_CHECKOUT = Path(__file__).resolve().parents[2]
if not os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT") and (
    _CHECKOUT / "jnwb" / "__init__.py"
).exists():
    sys.path.insert(0, str(_CHECKOUT))

import jnwb
from jnwb.testing.nwb_fixtures import (
    CODE_LABEL_A,
    TASK_TABLE,
    canonical_co_resident_options,
    write_synth_nwb,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "synthetic_recording.nwb"
        receipt = write_synth_nwb(path, canonical_co_resident_options(seed=42))

        # Inspect top-level file structure without guessing default tables
        info = jnwb.inspect(path)

        # 1. Session-level identifier and metadata
        assert info["session"]["identifier"] == "TEST_SYNTH_CANONICAL"
        print(f"Session identifier: {info['session']['identifier']}")

        # 2. Acquisition time series
        acq_names = [a["name"] for a in info["acquisitions"]]
        assert len(acq_names) >= 1
        print(f"Acquisitions: {acq_names}")

        # 3. Sorted units inventory
        n_units = info["units"]["n_rows"]
        assert n_units == 2
        print(f"Discovered units: {n_units} units")

        # 4. Interval tables and column discovery
        table_names = {t["name"] for t in info["interval_tables"]}
        assert TASK_TABLE in table_names
        assert receipt.rf_table in table_names
        assert receipt.flash_table in table_names
        print(f"Interval tables: {sorted(table_names)}")

        # 5. Column schema for task table
        task = next(t for t in info["interval_tables"] if t["name"] == TASK_TABLE)
        col_names = {c["name"] for c in task["columns"]}
        assert "codes" in col_names
        assert "start_time" in col_names
        codes_col = next(c for c in task["columns"] if c["name"] == "codes")
        assert CODE_LABEL_A in codes_col["sample_values"]
        print(f"Columns in {TASK_TABLE}: {sorted(col_names)}")
        print(f"Sample codes: {codes_col['sample_values']}")


if __name__ == "__main__":
    main()
