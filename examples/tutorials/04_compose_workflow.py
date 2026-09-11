"""Tutorial 4: Compose inspect → select events → align → one analysis step.

Run: python examples/tutorials/04_compose_workflow.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_TUTORIALS = Path(__file__).resolve().parent
if str(_TUTORIALS) not in sys.path:
    sys.path.insert(0, str(_TUTORIALS))

import jnwb
from _support import CODE_LABEL_A, TASK_TABLE, build_canonical_fixture


def main() -> None:
    path, receipt = build_canonical_fixture()

    info = jnwb.inspect(path)
    assert info["units"]["n_rows"] >= 1
    table_names = {t["name"] for t in info["interval_tables"]}
    assert TASK_TABLE in table_names

    onsets = jnwb.event_onsets(path, table=TASK_TABLE, codes=[CODE_LABEL_A])
    np.testing.assert_allclose(onsets, receipt.task_onsets_s[::2])

    spike_times = jnwb.unit_spike_times(path, unit_index=0)
    metrics = jnwb.compute_response_metrics(
        spike_times,
        onsets,
        response_window=(0.0, 0.2),
    )
    assert "response_rate" in metrics
    assert np.isfinite(metrics["response_rate"])

    sig = jnwb.classify_response_significance(metrics)
    assert "is_significant" in sig

    print(f"composed workflow on {path.name}")
    print(f"events: {len(onsets)} onsets for {CODE_LABEL_A}")
    print(f"response_rate: {metrics['response_rate']:.2f} Hz; significant: {sig['is_significant']}")


if __name__ == "__main__":
    main()
