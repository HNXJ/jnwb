"""Tutorial 2: Discover event codes and retrieve onset times (seconds).

Run: python examples/tutorials/02_event_codes_and_onsets.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_TUTORIALS = Path(__file__).resolve().parent
if str(_TUTORIALS) not in sys.path:
    sys.path.insert(0, str(_TUTORIALS))

import jnwb
from _support import CODE_LABEL_A, CODE_LABEL_B, TASK_TABLE, build_canonical_fixture
from jnwb.testing.nwb_fixtures import FLASH_TABLE, RF_TABLE


def main() -> None:
    path, receipt = build_canonical_fixture()

    info = jnwb.inspect(path)
    task = next(t for t in info["interval_tables"] if t["name"] == TASK_TABLE)
    codes_col = next(c for c in task["columns"] if c["name"] == "codes")
    unique_codes = sorted(set(codes_col["sample_values"]))
    print(f"codes in {TASK_TABLE}: {unique_codes}")

    onsets_a = jnwb.event_onsets(path, table=TASK_TABLE, codes=[CODE_LABEL_A])
    onsets_b = jnwb.event_onsets(path, table=TASK_TABLE, codes=[CODE_LABEL_B])
    np.testing.assert_allclose(onsets_a, receipt.task_onsets_s[::2])
    np.testing.assert_allclose(onsets_b, receipt.task_onsets_s[1::2])

    et = jnwb.events(path, table=TASK_TABLE)
    assert et.time_unit == "seconds"
    assert et.code_column == "codes"
    assert et.onset_column == "start_time"
    assert et.n_events == len(receipt.task_onsets_s)

    rf_onsets = jnwb.event_onsets(path, table=RF_TABLE, codes=[CODE_LABEL_A])
    flash_onsets = jnwb.event_onsets(path, table=FLASH_TABLE, codes=[CODE_LABEL_B])
    np.testing.assert_allclose(rf_onsets, receipt.rf_onsets_s[::2])
    np.testing.assert_allclose(flash_onsets, receipt.flash_onsets_s[1::2])

    print(f"{CODE_LABEL_A} onsets (s): {onsets_a}")
    print(f"{CODE_LABEL_B} onsets (s): {onsets_b}")


if __name__ == "__main__":
    main()
