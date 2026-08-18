r"""
Rerun of the H1/H2/H3 onset-hierarchy test (scripts/fit_class_onset_latency.py) restricted to
sessions NOT flagged by scripts/diagnose_onset_hierarchy_boundary_pinning.py's broadened
(2026-08-15) pinning definition (t0 < 1ms, hard or soft variant -- see that script's docstring).

WHY
    diagnose_onset_hierarchy_boundary_pinning.py found 68.3% of gate-passing cells (r2>=0.3,
    converged) across the whole onset_hierarchy run are boundary-pinned once the soft (large-tau,
    slow-ramp-compressed-against-t0=0) variant is counted, not just the 20.8% the narrower
    original version found. Per-class: omnibus 85.5%, O+ 100%, O- 83.3%, S- 100% pinned -- these
    four classes' area_class_summary.csv / hierarchy_test_results.csv values are built from
    mostly-or-entirely artifact cells and should not be cited. S+ is 34.9% pinned -- worse than
    first reported (was called "essentially clean" based on the narrower diagnostic, which missed
    the soft variant entirely) but still has a real clean majority (65.1%) concentrated in
    specific areas.

    This script does NOT change the fitting method (jnwb/onset_fitting.py, unmodified) or the
    extraction (scripts/fit_class_onset_latency.py, unmodified, its own functions imported and
    reused rather than duplicated). It only restricts the INPUT to bootstrap_area_class and
    hierarchy_test to cells classify() calls "clean", to see whether the classes/areas with
    enough surviving clean sessions still support a legitimate, artifact-free hierarchy
    comparison at all, given MIN_SESSIONS_PER_CELL=3 must still be met on the clean subset alone.

OUTPUT
    outputs/classification/onset_hierarchy/area_class_summary_clean_only.csv
    outputs/classification/onset_hierarchy/hierarchy_test_results_clean_only.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from fit_class_onset_latency import (  # noqa: E402
    AREA_ORDER, CLASSES, MIN_SESSIONS_PER_CELL, N_BOOT, N_PERM, SEED,
    bootstrap_area_class, hierarchy_test,
)
from diagnose_onset_hierarchy_boundary_pinning import T0_PIN_THRESH_MS  # noqa: E402
from figstats import holm, bh  # noqa: E402

CELL_CSV = REPO_ROOT / ".." / "outputs" / "classification" / "onset_hierarchy" / "cell_fits.csv"
OUT_DIR = REPO_ROOT / ".." / "outputs" / "classification" / "onset_hierarchy"
SUMMARY_CSV = OUT_DIR / "area_class_summary_clean_only.csv"
TEST_CSV = OUT_DIR / "hierarchy_test_results_clean_only.csv"


def main():
    df = pd.read_csv(CELL_CSV)
    df["gate_pass"] = (df["r2"] >= 0.3) & (df["converged"].astype(bool))
    # "clean" = passes the existing r2/converged gate AND t0 is not pinned near 0. A cell that
    # fails the r2/converged gate is already excluded by bootstrap_area_class itself; only the
    # additional pinning filter is new here.
    clean = df[df["gate_pass"] & (df["t0"] >= T0_PIN_THRESH_MS)].copy()

    rng = np.random.default_rng(SEED)
    summary_rows = []
    for area in AREA_ORDER:
        for cls in CLASSES:
            r = bootstrap_area_class(clean, area, cls, rng)
            if r is not None:
                summary_rows.append(r)
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(SUMMARY_CSV, index=False)
    print(f"WROTE {SUMMARY_CSV} ({len(summary)} area x class cells survive clean-only "
          f"MIN_SESSIONS_PER_CELL={MIN_SESSIONS_PER_CELL})")
    if not summary.empty:
        print(summary.to_string(index=False))

    if summary.empty:
        print("\nNo area x class cell has >=3 clean sessions -- hierarchy test cannot run "
              "on the clean subset for any class.")
        return

    test_rows = [hierarchy_test(summary, cls, rng) for cls in CLASSES]
    test_df = pd.DataFrame(test_rows)
    valid = test_df["p"].notna()
    if valid.any():
        test_df.loc[valid, "p_holm"] = holm(test_df.loc[valid, "p"].to_numpy())
        test_df.loc[valid, "q_bh"] = bh(test_df.loc[valid, "p"].to_numpy())

    def verdict(row):
        if not np.isfinite(row.get("p_holm", np.nan)):
            return "insufficient_data"
        if row["p_holm"] < 0.05:
            return "H1_low_then_high" if row["rho"] > 0 else "H2_high_then_low"
        return "H3_superposition_candidate"
    test_df["verdict"] = test_df.apply(verdict, axis=1)
    test_df.to_csv(TEST_CSV, index=False)
    print(f"\nWROTE {TEST_CSV}")
    print(test_df[["class", "n_areas", "rho", "p", "p_holm", "q_bh", "verdict"]].to_string(index=False))


if __name__ == "__main__":
    main()
