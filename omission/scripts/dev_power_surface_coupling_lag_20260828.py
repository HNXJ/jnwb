# SUPERSEDED (2026-08-30): this script belongs to the causal-identification investigation,
# CONFIRMED closed by causal-identification-branch-seal-20260828.json. Its numerical findings
# are preserved in that seal and in omission/artifacts/.lab/. Kept for provenance and because
# other scripts in this directory still import it; do not extend or rerun it for new analysis.
"""dev_power_surface_coupling_lag_20260828.py

One axis of the power/calibration surface Hamm asked for: coupling_strength x true_lag_ms,
for Candidate B2 (matched_filter_peak_realign -> trial_shuffle_pvalue) vs Candidate C
(matched_permutation_pvalue with n_bins=20), evaluated at n_trials=200 for BOTH methods so the
comparison is apples-to-apples and C is inside its known-valid regime (naive quantile binning
needs n_trials>=200 with ~10 trials/bin; n_bins=20 at n_trials=200 satisfies that).

For every (coupling_strength, true_lag_ms) grid cell, ONE shared synthetic dataset is drawn per
seed and BOTH methods are evaluated on that SAME draw (paired design) to cut Monte Carlo noise
between the two methods' comparison. coupling_direction="P_to_R" only (direction is being
checked by a separate agent per Hamm's assignment).

Compute-time note: a direct benchmark of trial_shuffle_pvalue/matched_permutation_pvalue at
n_trials=200 with n_perm=20 measured ~10.7s wall time (dominated by lagged_association's
301-lag x ~80,000-sample corrcoef loop inside common_driver_control.py, which this script does
not modify). At the originally suggested n_perm=150 the full 4x4x8 grid x 2 methods would take
roughly 5-6 hours single-threaded. This script instead uses n_perm=60 (still >> the 8 seeds x
1/(n_perm+1) resolution needed to resolve alpha=0.05 -- min achievable p = 1/61 = 0.0164) and
parallelizes across (coupling_strength, true_lag, seed) work units with
concurrent.futures.ProcessPoolExecutor. n_perm=60 is stated here and in every output artifact;
it is a compute-budget reduction from the suggested n_perm=150, not a silent one.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from omission.jnwb_ext.common_driver_control import (
    synthesize_adversarial_pair,
    matched_filter_peak_realign,
    matched_permutation_pvalue,
    trial_shuffle_pvalue,
)

N_TRIALS = 200
N_BINS_C = 20
N_PERM = 60
N_SEEDS = 8
COUPLING_STRENGTHS = [0.6, 1.2, 2.0, 3.0]
TRUE_LAGS_MS = [10, 30, 60, 100]
ALPHA = 0.05
COUPLING_DIRECTION = "P_to_R"

OUT_JSON = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / \
    "dev-power-surface-coupling-lag-20260828.json"


def _cell_seed_base(cs_idx: int, lag_idx: int, seed_idx: int) -> int:
    # distinct, non-overlapping seed regions per (cs, lag, seed) cell so no draw is reused
    # across cells or across the B2/C evaluation within a cell.
    return 1_000_000 + cs_idx * 10_000 + lag_idx * 1_000 + seed_idx * 10


def _run_one(args):
    cs_idx, lag_idx, seed_idx, coupling_strength, true_lag_ms = args
    base = _cell_seed_base(cs_idx, lag_idx, seed_idx)

    P, R, _true_jitter = synthesize_adversarial_pair(
        n_trials=N_TRIALS,
        coupling_strength=coupling_strength,
        coupling_lag_ms=true_lag_ms,
        coupling_direction=COUPLING_DIRECTION,
        seed=base,
    )

    # Candidate B2: realign, then shared trial_shuffle_pvalue null.
    P_al, R_al, _shifts = matched_filter_peak_realign(P, R, n_folds=5, max_shift=60, seed=base + 1)
    res_b2 = trial_shuffle_pvalue(P_al, R_al, n_perm=N_PERM, seed=base + 2)

    # Candidate C: matched-permutation null directly on raw (unaligned) P/R.
    res_c = matched_permutation_pvalue(P, R, n_bins=N_BINS_C, n_perm=N_PERM, seed=base + 3)

    return {
        "cs_idx": cs_idx, "lag_idx": lag_idx, "seed_idx": seed_idx,
        "coupling_strength": coupling_strength, "true_lag_ms": true_lag_ms,
        "b2_p": res_b2["p"], "b2_observed_lag_ms": res_b2["observed_lag_ms"],
        "c_p": res_c["p"], "c_observed_lag_ms": res_c["observed_lag_ms"],
    }


def _aggregate(records, cs, lag, method_prefix):
    sel = [r for r in records if r["coupling_strength"] == cs and r["true_lag_ms"] == lag]
    p_key = f"{method_prefix}_p"
    lag_key = f"{method_prefix}_observed_lag_ms"
    ps = np.array([r[p_key] for r in sel])
    recovered = np.array([r[lag_key] for r in sel])
    tp_rate = float(np.mean(ps < ALPHA))
    bias = recovered - lag
    return {
        "n_seeds": len(sel),
        "tp_rate": tp_rate,
        "mean_recovered_lag_ms": float(recovered.mean()),
        "lag_bias_ms": float(bias.mean()),
        "lag_sd_ms": float(recovered.std(ddof=1)) if len(recovered) > 1 else 0.0,
        "lag_rmse_ms": float(np.sqrt(np.mean(bias ** 2))),
    }


def main():
    jobs = []
    for cs_idx, cs in enumerate(COUPLING_STRENGTHS):
        for lag_idx, lag in enumerate(TRUE_LAGS_MS):
            for seed_idx in range(N_SEEDS):
                jobs.append((cs_idx, lag_idx, seed_idx, cs, lag))

    print(f"Running {len(jobs)} (coupling_strength, true_lag, seed) draws, "
          f"n_trials={N_TRIALS}, n_perm={N_PERM}, n_bins(C)={N_BINS_C}, "
          f"coupling_direction={COUPLING_DIRECTION!r}")
    t0 = time.time()
    records = []
    with ProcessPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(_run_one, j): j for j in jobs}
        done = 0
        for fut in as_completed(futs):
            records.append(fut.result())
            done += 1
            if done % 16 == 0 or done == len(jobs):
                elapsed = time.time() - t0
                print(f"  {done}/{len(jobs)} done ({elapsed:.0f}s elapsed)")
    elapsed = time.time() - t0
    print(f"All draws complete in {elapsed:.0f}s")

    records.sort(key=lambda r: (r["cs_idx"], r["lag_idx"], r["seed_idx"]))

    grid = {"B2": {}, "C": {}}
    for cs in COUPLING_STRENGTHS:
        grid["B2"][str(cs)] = {}
        grid["C"][str(cs)] = {}
        for lag in TRUE_LAGS_MS:
            grid["B2"][str(cs)][str(lag)] = _aggregate(records, cs, lag, "b2")
            grid["C"][str(cs)][str(lag)] = _aggregate(records, cs, lag, "c")

    out = {
        "generated": "2026-08-28",
        "script": "omission/scripts/dev_power_surface_coupling_lag_20260828.py",
        "config": {
            "n_trials": N_TRIALS,
            "n_perm": N_PERM,
            "n_bins_C": N_BINS_C,
            "n_seeds": N_SEEDS,
            "coupling_strengths": COUPLING_STRENGTHS,
            "true_lags_ms": TRUE_LAGS_MS,
            "coupling_direction": COUPLING_DIRECTION,
            "alpha": ALPHA,
            "n_perm_note": (
                "Reduced from the suggested n_perm=150 to n_perm=60 for compute-time "
                "feasibility (see module docstring); min resolvable p = 1/(n_perm+1) = 0.0164."
            ),
        },
        "grid": grid,
        "raw_records": records,
        "elapsed_seconds": elapsed,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {OUT_JSON}")

    for method in ("B2", "C"):
        print(f"\n=== {method} true-positive rate at alpha={ALPHA} "
              f"(rows=coupling_strength, cols=true_lag_ms) ===")
        header = "cs\\lag".ljust(8) + "".join(str(l).rjust(8) for l in TRUE_LAGS_MS)
        print(header)
        for cs in COUPLING_STRENGTHS:
            row = str(cs).ljust(8)
            for lag in TRUE_LAGS_MS:
                tp = grid[method][str(cs)][str(lag)]["tp_rate"]
                row += f"{tp:8.3f}"
            print(row)

        print(f"\n=== {method} lag RMSE (ms) (rows=coupling_strength, cols=true_lag_ms) ===")
        print(header)
        for cs in COUPLING_STRENGTHS:
            row = str(cs).ljust(8)
            for lag in TRUE_LAGS_MS:
                rmse = grid[method][str(cs)][str(lag)]["lag_rmse_ms"]
                row += f"{rmse:8.2f}"
            print(row)

        print(f"\n=== {method} lag bias (ms) (rows=coupling_strength, cols=true_lag_ms) ===")
        print(header)
        for cs in COUPLING_STRENGTHS:
            row = str(cs).ljust(8)
            for lag in TRUE_LAGS_MS:
                bias = grid[method][str(cs)][str(lag)]["lag_bias_ms"]
                row += f"{bias:8.2f}"
            print(row)


if __name__ == "__main__":
    main()
