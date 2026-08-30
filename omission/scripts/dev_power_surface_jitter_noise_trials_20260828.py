# SUPERSEDED (2026-08-30): this script belongs to the causal-identification investigation,
# CONFIRMED closed by causal-identification-branch-seal-20260828.json. Its numerical findings
# are preserved in that seal and in omission/artifacts/.lab/. Kept for provenance and because
# other scripts in this directory still import it; do not extend or rerun it for new analysis.
"""Power/calibration surface, axes 2-3 of 3: jitter_sd_ms, noise_sd, n_trials (Hamm, 2026-08-28).

Standalone script -- imports ONLY from omission.jnwb_ext.common_driver_control (does not edit
it; other agents are working in that shared file in parallel).

Benchmarks two candidate confound controls against the adversarial shared-common-driver
generator (synthesize_adversarial_pair):

  B2 = matched_filter_peak_realign + trial_shuffle_pvalue (validated baseline regime:
       n_trials=60, jitter_sd_ms=8.0, coupling_strength=1.2, coupling_lag_ms=30.0,
       noise_sd=0.3 -> ~0% FP, ~50% TP)
  C  = matched_permutation_pvalue (validated baseline regime: n_trials=200, n_bins=20 ->
       near-nominal FP; known NOT to work at n_trials=60)

Three one-parameter-at-a-time sweeps, all at coupling_lag_ms=30.0, coupling_direction="P_to_R":
  1. jitter_sd_ms in {2, 8, 16, 30}      (n_trials fixed: B2=60, C=200/n_bins=20)
  2. noise_sd in {0.1, 0.3, 0.6, 1.0}    (n_trials fixed: B2=60, C=200/n_bins=20)
  3. n_trials in {60, 120, 200, 400}     (C's n_bins scaled to keep ~10 trials/bin)

Each cell: 8 seeds x {negative control (coupling_strength=0.0), positive control
(coupling_strength=1.2)}, n_perm=60 (reduced from the requested 150; the first attempt at
n_perm=150 was killed after >45 minutes without finishing sweep 1 -- `lagged_association`
(omission/jnwb_ext/lag_estimation.py) does a pure-Python for-loop over 301 lags with an
np.corrcoef call each, and at n_perm=150 the full 3-sweep design requires ~58,000 such calls
(~17.5M corrcoef evaluations), which is untenable at this session's time budget. n_perm=60 cuts
that ~2.5x. This is a SECOND reduction beyond the task's own 200->150; flagged explicitly per
the task instruction to state any n_perm reduction.

Alpha = 0.05 (two-sided rejection reported as p < 0.05, consistent with
test_adversarial_shared_event_null.py's convention and omission-statistics doctrine).

Lag bias / lag SD are computed from the POSITIVE-control runs' observed_lag_ms (from the
p-value dict), against the true coupling_lag_ms=30.0, regardless of whether that individual run
was significant -- this reports the estimator's timing recovery, not just the detection rate.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from omission.jnwb_ext.common_driver_control import (
    matched_filter_peak_realign,
    matched_permutation_pvalue,
    synthesize_adversarial_pair,
    trial_shuffle_pvalue,
)

ALPHA = 0.05
N_PERM = 60
N_SEEDS = 8
SEEDS = list(range(N_SEEDS))
COUPLING_LAG_MS = 30.0
COUPLING_DIRECTION = "P_to_R"

OUT_PATH = Path("omission/artifacts/.lab/dev_power_surface_jitter_noise_trials_20260828.json")
PARTIAL_PATH = OUT_PATH.with_name(OUT_PATH.stem + "_partial.json")


def _save_partial(all_sweeps):
    """Incremental checkpoint so progress is visible/recoverable even if the run is interrupted
    before main() writes the final OUT_PATH."""
    PARTIAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PARTIAL_PATH, "w") as f:
        json.dump({"generated": "2026-08-28 (partial/in-progress checkpoint)",
                    "n_perm": N_PERM, "n_seeds": N_SEEDS, "sweeps": all_sweeps}, f, indent=2)


def run_b2_cell(n_trials, jitter_sd_ms, noise_sd, coupling_strength, seed):
    P, R, _ = synthesize_adversarial_pair(
        n_trials=n_trials, jitter_sd_ms=jitter_sd_ms, noise_sd=noise_sd,
        coupling_strength=coupling_strength, coupling_lag_ms=COUPLING_LAG_MS,
        coupling_direction=COUPLING_DIRECTION, seed=seed,
    )
    P_al, R_al, _shifts = matched_filter_peak_realign(P, R, seed=seed)
    res = trial_shuffle_pvalue(P_al, R_al, n_perm=N_PERM, seed=seed + 1000)
    return res


def run_c_cell(n_trials, n_bins, jitter_sd_ms, noise_sd, coupling_strength, seed):
    P, R, _ = synthesize_adversarial_pair(
        n_trials=n_trials, jitter_sd_ms=jitter_sd_ms, noise_sd=noise_sd,
        coupling_strength=coupling_strength, coupling_lag_ms=COUPLING_LAG_MS,
        coupling_direction=COUPLING_DIRECTION, seed=seed,
    )
    res = matched_permutation_pvalue(P, R, n_bins=n_bins, n_perm=N_PERM, seed=seed)
    return res


def summarize(neg_results, pos_results):
    fp_rate = float(np.mean([r["p"] < ALPHA for r in neg_results]))
    tp_rate = float(np.mean([r["p"] < ALPHA for r in pos_results]))
    pos_lags = np.array([r["observed_lag_ms"] for r in pos_results], dtype=float)
    lag_bias = float(np.mean(pos_lags - COUPLING_LAG_MS))
    lag_sd = float(np.std(pos_lags))
    return {
        "fp_rate": fp_rate, "tp_rate": tp_rate,
        "lag_bias_ms": lag_bias, "lag_sd_ms": lag_sd,
        "n_seeds": N_SEEDS, "n_perm": N_PERM,
        "neg_p_values": [float(r["p"]) for r in neg_results],
        "pos_p_values": [float(r["p"]) for r in pos_results],
        "pos_observed_lags_ms": pos_lags.tolist(),
    }


def sweep_jitter(checkpoint_ctx=None):
    values = [2.0, 8.0, 16.0, 30.0]
    n_trials_b2 = 60
    n_trials_c, n_bins_c = 200, 20
    cells = {}
    for jsd in values:
        t_cell = time.time()
        neg_b2 = [run_b2_cell(n_trials_b2, jsd, 0.3, 0.0, s) for s in SEEDS]
        pos_b2 = [run_b2_cell(n_trials_b2, jsd, 0.3, 1.2, s) for s in SEEDS]
        neg_c = [run_c_cell(n_trials_c, n_bins_c, jsd, 0.3, 0.0, s) for s in SEEDS]
        pos_c = [run_c_cell(n_trials_c, n_bins_c, jsd, 0.3, 1.2, s) for s in SEEDS]
        cells[str(jsd)] = {
            "B2": summarize(neg_b2, pos_b2),
            "C": summarize(neg_c, pos_c),
            "params": {"jitter_sd_ms": jsd, "n_trials_B2": n_trials_b2,
                       "n_trials_C": n_trials_c, "n_bins_C": n_bins_c, "noise_sd": 0.3},
        }
        print(f"  [jitter_sd_ms={jsd}] B2 FP={cells[str(jsd)]['B2']['fp_rate']:.3f} "
              f"TP={cells[str(jsd)]['B2']['tp_rate']:.3f} | "
              f"C FP={cells[str(jsd)]['C']['fp_rate']:.3f} TP={cells[str(jsd)]['C']['tp_rate']:.3f} "
              f"({time.time() - t_cell:.1f}s)", flush=True)
        if checkpoint_ctx is not None:
            checkpoint_ctx["sweeps"]["jitter_sd_ms"] = {"values": values, "cells": cells}
            _save_partial(checkpoint_ctx["sweeps"])
    return {"values": values, "cells": cells}


def sweep_noise(checkpoint_ctx=None):
    values = [0.1, 0.3, 0.6, 1.0]
    n_trials_b2 = 60
    n_trials_c, n_bins_c = 200, 20
    cells = {}
    for ns in values:
        t_cell = time.time()
        neg_b2 = [run_b2_cell(n_trials_b2, 8.0, ns, 0.0, s) for s in SEEDS]
        pos_b2 = [run_b2_cell(n_trials_b2, 8.0, ns, 1.2, s) for s in SEEDS]
        neg_c = [run_c_cell(n_trials_c, n_bins_c, 8.0, ns, 0.0, s) for s in SEEDS]
        pos_c = [run_c_cell(n_trials_c, n_bins_c, 8.0, ns, 1.2, s) for s in SEEDS]
        cells[str(ns)] = {
            "B2": summarize(neg_b2, pos_b2),
            "C": summarize(neg_c, pos_c),
            "params": {"noise_sd": ns, "n_trials_B2": n_trials_b2,
                       "n_trials_C": n_trials_c, "n_bins_C": n_bins_c, "jitter_sd_ms": 8.0},
        }
        print(f"  [noise_sd={ns}] B2 FP={cells[str(ns)]['B2']['fp_rate']:.3f} "
              f"TP={cells[str(ns)]['B2']['tp_rate']:.3f} | "
              f"C FP={cells[str(ns)]['C']['fp_rate']:.3f} TP={cells[str(ns)]['C']['tp_rate']:.3f} "
              f"({time.time() - t_cell:.1f}s)", flush=True)
        if checkpoint_ctx is not None:
            checkpoint_ctx["sweeps"]["noise_sd"] = {"values": values, "cells": cells}
            _save_partial(checkpoint_ctx["sweeps"])
    return {"values": values, "cells": cells}


def sweep_n_trials(checkpoint_ctx=None):
    values = [60, 120, 200, 400]
    cells = {}
    for nt in values:
        t_cell = time.time()
        n_bins_c = max(2, nt // 10)
        neg_b2 = [run_b2_cell(nt, 8.0, 0.3, 0.0, s) for s in SEEDS]
        pos_b2 = [run_b2_cell(nt, 8.0, 0.3, 1.2, s) for s in SEEDS]
        neg_c = [run_c_cell(nt, n_bins_c, 8.0, 0.3, 0.0, s) for s in SEEDS]
        pos_c = [run_c_cell(nt, n_bins_c, 8.0, 0.3, 1.2, s) for s in SEEDS]
        cells[str(nt)] = {
            "B2": summarize(neg_b2, pos_b2),
            "C": summarize(neg_c, pos_c),
            "params": {"n_trials": nt, "n_bins_C": n_bins_c, "jitter_sd_ms": 8.0, "noise_sd": 0.3},
        }
        print(f"  [n_trials={nt}] B2 FP={cells[str(nt)]['B2']['fp_rate']:.3f} "
              f"TP={cells[str(nt)]['B2']['tp_rate']:.3f} | "
              f"C (n_bins={n_bins_c}) FP={cells[str(nt)]['C']['fp_rate']:.3f} "
              f"TP={cells[str(nt)]['C']['tp_rate']:.3f} "
              f"({time.time() - t_cell:.1f}s)", flush=True)
        if checkpoint_ctx is not None:
            checkpoint_ctx["sweeps"]["n_trials"] = {"values": values, "cells": cells}
            _save_partial(checkpoint_ctx["sweeps"])
    return {"values": values, "cells": cells}


def print_table(name, sweep, param_label):
    print(f"\n=== {name} ({param_label}) ===", flush=True)
    print(f"{param_label:>14} | {'B2 FP':>7} {'B2 TP':>7} {'B2 lagbias':>11} {'B2 lagSD':>9} "
          f"| {'C FP':>7} {'C TP':>7} {'C lagbias':>10} {'C lagSD':>8}", flush=True)
    for v in sweep["values"]:
        c = sweep["cells"][str(v)]
        b2, cc = c["B2"], c["C"]
        print(f"{v!s:>14} | {b2['fp_rate']:>7.3f} {b2['tp_rate']:>7.3f} "
              f"{b2['lag_bias_ms']:>11.2f} {b2['lag_sd_ms']:>9.2f} "
              f"| {cc['fp_rate']:>7.3f} {cc['tp_rate']:>7.3f} "
              f"{cc['lag_bias_ms']:>10.2f} {cc['lag_sd_ms']:>8.2f}", flush=True)


def main():
    t0 = time.time()
    checkpoint_ctx = {"sweeps": {}}
    print("Sweep 1: jitter_sd_ms in {2, 8, 16, 30} (B2 n_trials=60; C n_trials=200, n_bins=20)", flush=True)
    sweep1 = sweep_jitter(checkpoint_ctx)
    print("\nSweep 2: noise_sd in {0.1, 0.3, 0.6, 1.0} (B2 n_trials=60; C n_trials=200, n_bins=20)", flush=True)
    sweep2 = sweep_noise(checkpoint_ctx)
    print("\nSweep 3: n_trials in {60, 120, 200, 400} (C n_bins = n_trials // 10, min 2)", flush=True)
    sweep3 = sweep_n_trials(checkpoint_ctx)

    print_table("Sweep 1", sweep1, "jitter_sd_ms")
    print_table("Sweep 2", sweep2, "noise_sd")
    print_table("Sweep 3", sweep3, "n_trials")

    out = {
        "generated": "2026-08-28",
        "script": "omission/scripts/dev_power_surface_jitter_noise_trials_20260828.py",
        "alpha": ALPHA,
        "n_perm": N_PERM,
        "n_perm_note": ("Reduced from the task-requested 150 to 60. A first attempt at n_perm=150 "
                        "was killed after >45 minutes without completing sweep 1: "
                        "omission/jnwb_ext/lag_estimation.py:lagged_association does a pure-Python "
                        "for-loop over 301 lags with an np.corrcoef call per lag, and the full "
                        "3-sweep x 8-seed x pos/neg x B2/C design at n_perm=150 requires ~58,000 "
                        "such calls (~17.5M corrcoef evaluations) -- untenable at this session's "
                        "time budget. n_perm=60 was chosen to bring this into a bounded runtime; "
                        "flagged per the task's own instruction to state any n_perm reduction."),
        "n_seeds": N_SEEDS,
        "seeds": SEEDS,
        "coupling_lag_ms": COUPLING_LAG_MS,
        "coupling_direction": COUPLING_DIRECTION,
        "coupling_strength_neg": 0.0,
        "coupling_strength_pos": 1.2,
        "sweeps": {
            "jitter_sd_ms": sweep1,
            "noise_sd": sweep2,
            "n_trials": sweep3,
        },
        "runtime_sec": None,
    }
    out["runtime_sec"] = time.time() - t0
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {OUT_PATH} ({time.time() - t0:.1f}s total)", flush=True)
    if PARTIAL_PATH.exists():
        PARTIAL_PATH.unlink()


if __name__ == "__main__":
    main()
