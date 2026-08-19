r"""
scripts/fit_s_plus_onset_latency_s1.py

S+ onset-latency hierarchy test, S1-sourced (Hamm, 2026-08-17: "find the S++/S+ temporal
progression order (causality adjusted) for V1 to PFC").

WHY A NEW SCRIPT, NOT AN EDIT TO fit_class_onset_latency.py
    That script's S+ population comes from grand_s_and_o_units.csv (legacy template-correlation,
    fx=0 in its O+ template) via load_unit_class_table(). Hamm retired that pipeline entirely for
    this project on 2026-08-17 (artifacts/.lab/handout-fig03-oplusplus-threshold-20260817.md) in
    favor of outputs/classification/unit_inclusion_v1.csv's own local-baseline is_s_plus (S1,
    never the buggy mechanism, unchanged by the S1 rework itself). fit_class_onset_latency.py
    also still computes O+/O-/omnibus/S- against the legacy table and other things may depend on
    it -- editing it in place risks silently changing those. This script imports its already-
    built, unmodified primitives (population_psth, fit_one_cell, bootstrap_area_class,
    hierarchy_test, causal_exp_smooth via omission.jnwb_ext.onset_fitting) and only replaces the unit-selection
    step. Conservation: original preserved, new file for the new population.

CAUSALITY (unchanged from fit_class_onset_latency.py, reused not reimplemented)
    fit_exponential_onset's t0 is bounded to [0, window_end] by construction
    (jnwb/onset_fitting.py). Any fitted onset <40ms (MIN_VISUAL_LATENCY_MS, visual-system minimum
    latency) is flagged, not silently accepted. Same S_WIN_MS/S_BASELINE_MS/EXTRACTION_MARGIN_MS
    as the original script (baseline window pulled back into the -500..0ms fixation period,
    clear of any pre-stimulus ramp -- see that script's 2026-08-15 module comment for the
    rationale, reused verbatim here since it's a bug fix, not a judgment call specific to S1).

POPULATION
    outputs/classification/unit_inclusion_v1.csv, quality_tier != 'mua', is_s_plus == True.
    This is the SAME non-mua restriction Hamm confirmed (2026-08-17) matches the "~1200+" figure
    for the corpus-wide S+ count.

OUTPUT
    outputs/classification/onset_hierarchy_s1/cell_fits.csv
    outputs/classification/onset_hierarchy_s1/area_summary.csv
    outputs/classification/onset_hierarchy_s1/hierarchy_test_result.json
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "context" / "figures"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import omission as oa  # noqa: E402
from jnwb import paths as _P  # noqa: E402
from figstyle import AREA_ORDER  # noqa: E402
from figstats import holm, bh  # noqa: E402

from fit_class_onset_latency import (  # noqa: E402 -- reused, not reimplemented
    S_WIN_MS, S_BASELINE_MS, MIN_UNITS, MIN_SESSIONS_PER_CELL, MIN_R2,
    MIN_VISUAL_LATENCY_MS, T0_PIN_THRESH_MS, N_BOOT, N_PERM, SEED,
    p1_onsets_s, fit_one_cell, bootstrap_area_class, hierarchy_test,
)

OUT_DIR = REPO_ROOT / "outputs" / "classification" / "onset_hierarchy_s1"
CELL_CSV = OUT_DIR / "cell_fits.csv"
SUMMARY_CSV = OUT_DIR / "area_summary.csv"


def load_s1_s_plus_table() -> pd.DataFrame:
    s1 = pd.read_csv(_P.outputs_dir("classification", "unit_inclusion_v1.csv"))
    nonmua = s1[s1["quality_tier"] != "mua"].copy()
    return nonmua[["session", "unit_row", "area", "is_s_plus"]]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    unit_table = load_s1_s_plus_table()

    readiness = pd.read_csv(REPO_ROOT / "artifacts/data/session_readiness.csv")
    sessions = readiness.loc[readiness.nwb_ok, "session_prefix"].tolist()

    rows = []
    t_start = time.time()
    for k, prefix in enumerate(sessions, 1):
        try:
            sess = oa.read(str(_P.resolve_nwb_path(prefix)))
        except Exception as e:
            print(f"[{k}/{len(sessions)}] {prefix}: load failed -- {e}")
            continue
        sub = unit_table[unit_table["session"] == prefix]
        if sub.empty:
            continue
        p1_onsets = p1_onsets_s(sess)

        for area in AREA_ORDER:
            area_sub = sub[(sub["area"] == area) & (sub["is_s_plus"])]
            unit_rows = area_sub["unit_row"].tolist()
            if len(unit_rows) < MIN_UNITS:
                continue
            try:
                fit = fit_one_cell(sess, unit_rows, p1_onsets, S_WIN_MS, S_BASELINE_MS)
            except Exception as e:
                print(f"  {prefix} {area} S+: fit failed -- {e}")
                continue
            if fit is None:
                continue
            fit.update({"session": prefix, "area": area, "class": "S+"})
            rows.append(fit)

        if k % 5 == 0 or k == len(sessions):
            print(f"[{k}/{len(sessions)}] {prefix} done, {len(rows)} cells so far, "
                  f"{time.time()-t_start:.0f}s", flush=True)
            pd.DataFrame(rows).to_csv(CELL_CSV, index=False)

    df_cell = pd.DataFrame(rows)
    df_cell.to_csv(CELL_CSV, index=False)
    print(f"WROTE {CELL_CSV} ({len(df_cell)} cells)")
    if df_cell.empty:
        print("No cells fit -- aborting.")
        return

    rng = np.random.default_rng(SEED)
    summary_rows = []
    for area in AREA_ORDER:
        r = bootstrap_area_class(df_cell, area, "S+", rng)
        if r is not None:
            summary_rows.append(r)
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(SUMMARY_CSV, index=False)
    print(f"WROTE {SUMMARY_CSV} ({len(summary)} areas)")
    print(summary.to_string(index=False))

    test_result = hierarchy_test(summary.assign(**{"class": "S+"}), "S+", rng)
    if np.isfinite(test_result.get("p", np.nan)):
        test_result["p_holm"] = float(holm(np.array([test_result["p"]]))[0])
        test_result["q_bh"] = float(bh(np.array([test_result["p"]]))[0])
    print("\nHierarchy test (S1-sourced S+):", test_result)

    flags = []
    for _, r in summary.iterrows():
        if r["onset_ms"] < MIN_VISUAL_LATENCY_MS:
            flags.append(f"S+ {r['area']}: onset {r['onset_ms']:.1f}ms < "
                         f"{MIN_VISUAL_LATENCY_MS}ms minimum visual latency")
    gated = df_cell[(df_cell["r2"] >= MIN_R2) & (df_cell["converged"].astype(bool))]
    for area, g in gated.groupby("area"):
        n_pinned = int((g["t0"] < T0_PIN_THRESH_MS).sum())
        if n_pinned > 0:
            flags.append(f"S+ {area}: {n_pinned}/{len(g)} gate-passing sessions boundary-pinned "
                         f"(t0<{T0_PIN_THRESH_MS}ms)")
    if flags:
        print("\nFLAGGED (physically implausible or causality-adjacent, NOT auto-excluded):")
        for f in flags:
            print(" -", f)
    else:
        print("\nNo physical-plausibility flags.")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "population_source": str(_P.outputs_dir("classification", "unit_inclusion_v1.csv")),
        "population_filter": "quality_tier != 'mua', is_s_plus == True",
        "n_sessions_attempted": len(sessions),
        "n_cells_fit": int(len(df_cell)),
        "s_win_ms": list(S_WIN_MS), "s_baseline_ms": list(S_BASELINE_MS),
        "min_visual_latency_ms": MIN_VISUAL_LATENCY_MS,
        "n_boot": N_BOOT, "n_perm": N_PERM, "seed": SEED,
        "flags": flags,
        "hierarchy_test": test_result,
    }
    with open(OUT_DIR / "hierarchy_test_result.json", "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2, default=str)
    print(f"WROTE {OUT_DIR / 'hierarchy_test_result.json'}")


if __name__ == "__main__":
    main()
