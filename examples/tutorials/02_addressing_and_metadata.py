"""Tutorial 02: Addressing and Metadata — Events, Units, and Electrodes.

Run: python examples/tutorials/02_addressing_and_metadata.py
"""

from __future__ import annotations

import sys

import tempfile
from pathlib import Path

import numpy as np

# This file is run from a checkout, so prefer that checkout over any installed jnwb:
# Python puts this directory on sys.path, not the repository root.
_CHECKOUT = Path(__file__).resolve().parents[2]
if (_CHECKOUT / "jnwb" / "__init__.py").exists():
    sys.path.insert(0, str(_CHECKOUT))

import jnwb
from jnwb.testing.nwb_fixtures import (
    CODE_LABEL_A,
    CODE_LABEL_B,
    TASK_TABLE,
    canonical_co_resident_options,
    write_synth_nwb,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "ses-01_recording.nwb"
        receipt = write_synth_nwb(path, canonical_co_resident_options(seed=42))

        # 1. Event Table Access: retrieve EventTable wrapper
        et = jnwb.events(path, table=TASK_TABLE)
        assert et.time_unit == "seconds"
        assert et.code_column == "codes"
        assert et.n_events == len(receipt.task_onsets_s)
        print(f"Event table '{TASK_TABLE}': {et.n_events} events (timestamps in {et.time_unit})")

        # 2. Condition-specific event onsets (strictly in seconds)
        onsets_a = jnwb.event_onsets(path, table=TASK_TABLE, codes=[CODE_LABEL_A])
        onsets_b = jnwb.event_onsets(path, table=TASK_TABLE, codes=[CODE_LABEL_B])
        np.testing.assert_allclose(onsets_a, receipt.task_onsets_s[::2])
        np.testing.assert_allclose(onsets_b, receipt.task_onsets_s[1::2])
        print(f"Condition '{CODE_LABEL_A}' onsets (s): {onsets_a[:3]}... ({len(onsets_a)} total)")
        print(f"Condition '{CODE_LABEL_B}' onsets (s): {onsets_b[:3]}... ({len(onsets_b)} total)")

        # 3. Units Metadata Census
        units_meta = jnwb.get_all_units_metadata(path)
        assert len(units_meta) == 2
        print(f"Units census: {len(units_meta)} units indexed with columns {list(units_meta.columns)}")

        # 4. Electrode Inventory & Channel Mapping
        elec_inv = jnwb.electrode_inventory(path)
        assert len(elec_inv) == receipt.options.n_channels
        print(f"Electrode inventory: {len(elec_inv)} channels on groups {elec_inv['group_name'].unique().tolist()}")

        # 5. Explicit Addressing Invariant: calling without table raises AmbiguousIntervalTableError if ambiguous
        try:
            jnwb.event_onsets(path, codes=[CODE_LABEL_A])
            raise AssertionError("Should have raised AmbiguousIntervalTableError for ambiguous table selection")
        except jnwb.AmbiguousIntervalTableError as err:
            print(f"Verified explicit addressing guard: {err}")


if __name__ == "__main__":
    main()
