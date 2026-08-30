# SUPERSEDED (2026-08-30): this script belongs to the causal-identification investigation,
# CONFIRMED closed by causal-identification-branch-seal-20260828.json. Its numerical findings
# are preserved in that seal and in omission/artifacts/.lab/. Kept for provenance and because
# other scripts in this directory still import it; do not extend or rerun it for new analysis.
"""dev_paired_benchmark_20260828.py -- PAIRED comparison of common-driver-confound controls.

Hamm's explicit ask (2026-08-28): for every synthetic (P, R) realization, evaluate all THREE
candidate methods -- raw trial-shuffle, Candidate B2 (matched_filter_peak_realign), Candidate C
(matched_permutation_pvalue, n_bins=20) -- on the SAME draw, so any difference between methods is
attributable to the estimator, not to Monte Carlo variation across different random seeds. Run at
n_trials=200 (the scale where Candidate C's naive quantile binning was found, immediately prior
to this script, to reach near-nominal FPR), for the negative control (coupling_strength=0.0) and
the positive control (coupling_strength=1.2, coupling_lag_ms=30.0) in BOTH coupling directions
(P_to_R and R_to_P).

This is a standalone, read-only-of-common_driver_control.py script -- per instruction, does NOT
edit that shared module (other agents are concurrently working in it); only imports from it.

Sign-convention prediction (worked out BEFORE running, from lag_estimation.lagged_association's
docstring: "lag > 0 => LFP precedes spike", C(tau) = Assoc(P(t), R(t+tau))):
  - P_to_R coupling: R's coupled kernel is centered at p_center + e_i + coupling_lag_ms, i.e. R's
    coupling-driven response occurs coupling_lag_ms AFTER the shared per-trial event time that P
    is locked to. So P leads R by ~coupling_lag_ms -> expect observed_lag_ms ~= +30.
  - R_to_P coupling: P's coupled kernel is centered at r_center + e_i + coupling_lag_ms, i.e. P's
    coupling-driven response occurs coupling_lag_ms AFTER R's own event time. So R leads P by
    ~coupling_lag_ms, i.e. spike precedes LFP -> expect observed_lag_ms ~= -30 (opposite sign from
    P_to_R, as the module's own convention requires).
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

N_TRIALS = 200
N_PERM = 40
N_BINS = 20
ALPHA = 0.05
COUPLING_STRENGTH = 1.2
COUPLING_LAG_MS = 30.0
JITTER_SD_MS = 8.0
SEEDS = list(range(1, 6))  # 5 seeds per condition

# DEVIATION FROM ORIGINAL SPEC (recorded here + in the receipt's "deviation_note"):
# Hamm's task asked for n_perm=200 and >=15 seeds/condition. A single-seed timing probe run
# immediately before this (n_trials=200, n_perm=100) measured raw=122.8s, B2=129.2s, C=129.4s
# -- ~381s per (seed, condition) for all three methods sequentially, on a machine already at
# 99% CPU load from ~27 concurrent python processes (other agents' concurrent work, confirmed via
# `tasklist`/`wmic`). The original design (20 seeds x 3 conditions x 3 methods, n_perm=200) would
# take on the order of 6+ hours serially. Per explicit coordinator instruction (after an earlier
# attempt to background this went unnoticed), this run uses n_perm=40 and 5 seeds/condition,
# executed with multiprocessing across (condition, seed) pairs, inside ONE blocking foreground
# call, to produce a real completed (if smaller/noisier) result rather than an incomplete large
# one. n_perm=40 still resolves p down to 1/41=0.024, well under alpha=0.05, so significance
# calls remain valid; only the FPR/TP-rate and lag-SD point estimates are noisier (5 seeds -> a
# rate estimate's granularity is 20 percentage points, not a precise CI).
N_WORKERS = 8

CONDITIONS = [
    dict(name="negative", coupling_strength=0.0, coupling_lag_ms=COUPLING_LAG_MS,
         coupling_direction="P_to_R", kind="negative"),
    dict(name="positive_P_to_R", coupling_strength=COUPLING_STRENGTH, coupling_lag_ms=COUPLING_LAG_MS,
         coupling_direction="P_to_R", kind="positive"),
    dict(name="positive_R_to_P", coupling_strength=COUPLING_STRENGTH, coupling_lag_ms=COUPLING_LAG_MS,
         coupling_direction="R_to_P", kind="positive"),
]

EXPECTED_LAG_SIGN = {"positive_P_to_R": +1, "positive_R_to_P": -1}


def run_one(cond: dict, seed: int) -> dict:
    P, R, true_jitter = synthesize_adversarial_pair(
        n_trials=N_TRIALS, jitter_sd_ms=JITTER_SD_MS,
        coupling_strength=cond["coupling_strength"], coupling_lag_ms=cond["coupling_lag_ms"],
        coupling_direction=cond["coupling_direction"], seed=seed,
    )

    t0 = time.perf_counter()
    raw = trial_shuffle_pvalue(P, R, n_perm=N_PERM, seed=seed * 1000)
    t_raw = time.perf_counter() - t0

    t0 = time.perf_counter()
    P_al, R_al, shifts = matched_filter_peak_realign(P, R, seed=seed)
    b2 = trial_shuffle_pvalue(P_al, R_al, n_perm=N_PERM, seed=seed * 1000)
    t_b2 = time.perf_counter() - t0

    t0 = time.perf_counter()
    c = matched_permutation_pvalue(P, R, n_bins=N_BINS, n_perm=N_PERM, seed=seed)
    t_c = time.perf_counter() - t0

    return {
        "seed": seed,
        "raw": {"p": raw["p"], "observed_lag_ms": raw["observed_lag_ms"],
                "observed_peak": raw["observed_peak"], "time_s": t_raw},
        "B2": {"p": b2["p"], "observed_lag_ms": b2["observed_lag_ms"],
               "observed_peak": b2["observed_peak"], "time_s": t_b2},
        "C": {"p": c["p"], "observed_lag_ms": c["observed_lag_ms"],
              "observed_peak": c["observed_peak"], "time_s": t_c,
              "bin_counts": c["bin_counts"]},
    }


def summarize(records: list[dict], method: str, kind: str) -> dict:
    ps = np.array([r[method]["p"] for r in records])
    lags = np.array([r[method]["observed_lag_ms"] for r in records])
    times = np.array([r[method]["time_s"] for r in records])
    rate = float(np.mean(ps < ALPHA))
    out = {
        "rate_label": "FP_rate" if kind == "negative" else "TP_rate",
        "rate": rate,
        "n": len(records),
        "mean_time_s": float(times.mean()),
        "sd_time_s": float(times.std()),
    }
    if kind == "positive":
        out["lag_mean_ms"] = float(lags.mean())
        out["lag_sd_ms"] = float(lags.std())
    return out


def _run_job(job):
    cond, seed = job
    return cond["name"], seed, run_one(cond, seed)


def main():
    import multiprocessing as mp

    jobs = [(cond, seed) for cond in CONDITIONS for seed in SEEDS]
    print(f"Launching {len(jobs)} (condition, seed) jobs across {N_WORKERS} worker processes "
          f"(n_perm={N_PERM}, n_trials={N_TRIALS})...", flush=True)

    wall_t0 = time.perf_counter()
    raw_by_cond = {c["name"]: [] for c in CONDITIONS}
    with mp.Pool(processes=N_WORKERS) as pool:
        for name, seed, rec in pool.imap_unordered(_run_job, jobs):
            raw_by_cond[name].append((seed, rec))
            print(f"  [{name}] seed={seed:3d} done  raw p={rec['raw']['p']:.4f}  "
                  f"B2 p={rec['B2']['p']:.4f}  C p={rec['C']['p']:.4f}", flush=True)
    wall_elapsed = time.perf_counter() - wall_t0

    all_results = {}
    summary = {}
    for cond in CONDITIONS:
        name = cond["name"]
        records = [rec for seed, rec in sorted(raw_by_cond[name], key=lambda x: x[0])]
        all_results[name] = records
        summary[name] = {
            method: summarize(records, method, cond["kind"]) for method in ("raw", "B2", "C")
        }

    # --- sign-convention check ---
    sign_check = {}
    for name, expected_sign in EXPECTED_LAG_SIGN.items():
        for method in ("raw", "B2", "C"):
            lags = np.array([r[method]["observed_lag_ms"] for r in all_results[name]])
            mean_lag = float(lags.mean())
            matches = bool(np.sign(mean_lag) == expected_sign) if mean_lag != 0 else False
            sign_check[f"{name}/{method}"] = {
                "expected_sign": expected_sign, "mean_observed_lag_ms": mean_lag,
                "matches_expected_sign": matches,
            }

    receipt = {
        "script": "omission/scripts/dev_paired_benchmark_20260828.py",
        "generated": "2026-08-28",
        "config": {
            "n_trials": N_TRIALS, "n_perm": N_PERM, "n_bins": N_BINS, "alpha": ALPHA,
            "coupling_strength": COUPLING_STRENGTH, "coupling_lag_ms": COUPLING_LAG_MS,
            "jitter_sd_ms": JITTER_SD_MS, "seeds": SEEDS, "n_seeds": len(SEEDS),
        },
        "paired": True,
        "note": "For each seed, the SAME synthesize_adversarial_pair() draw is evaluated by all "
                "three methods (raw, B2, C), so cross-method differences are not confounded with "
                "Monte Carlo variation across different random draws.",
        "deviation_note": (
            "Original spec: n_perm=200, >=15 seeds/condition. Reduced to n_perm=40, 5 "
            "seeds/condition (run via multiprocessing, N_WORKERS={}) after a single-seed timing "
            "probe (n_trials=200, n_perm=100) measured raw=122.8s, B2=129.2s, C=129.4s per "
            "method on a machine at 99% CPU load from ~27 concurrent python processes (other "
            "agents' concurrent work) -- the original design would take hours. p-value floor at "
            "n_perm=40 is 1/41=0.024, still below alpha=0.05, so significance calls are valid; "
            "rate estimates are coarser (20-percentage-point granularity at n=5) than a 15-20 "
            "seed run would give.".format(N_WORKERS)
        ),
        "summary": summary,
        "sign_convention_check": sign_check,
        "wall_elapsed_s": wall_elapsed,
        "per_seed_results": all_results,
    }

    out_path = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / \
        "paired-common-driver-control-benchmark-20260828.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(receipt, f, indent=2)
    print(f"\nWrote receipt: {out_path}")

    # --- clean summary table ---
    print("\n" + "=" * 100)
    print(f"{'condition':<20}{'method':<8}{'metric':<10}{'value':<10}{'lag_mean':<12}{'lag_sd':<10}{'mean_t(s)':<10}")
    print("-" * 100)
    for cond in CONDITIONS:
        name = cond["name"]
        for method in ("raw", "B2", "C"):
            s = summary[name][method]
            lag_mean = f"{s.get('lag_mean_ms', float('nan')):.2f}" if "lag_mean_ms" in s else "--"
            lag_sd = f"{s.get('lag_sd_ms', float('nan')):.2f}" if "lag_sd_ms" in s else "--"
            print(f"{name:<20}{method:<8}{s['rate_label']:<10}{s['rate']:<10.3f}"
                  f"{lag_mean:<12}{lag_sd:<10}{s['mean_time_s']:<10.3f}")
    print("=" * 100)

    print("\nSign-convention check (expected vs observed mean lag sign):")
    for k, v in sign_check.items():
        flag = "OK" if v["matches_expected_sign"] else "MISMATCH"
        print(f"  {k:<20} expected_sign={v['expected_sign']:+d}  "
              f"mean_observed_lag_ms={v['mean_observed_lag_ms']:+.2f}  [{flag}]")

    print(f"\nTotal wall time: {wall_elapsed:.1f}s")


if __name__ == "__main__":
    main()
