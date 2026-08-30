# SUPERSEDED (2026-08-30): this script belongs to the causal-identification investigation,
# CONFIRMED closed by causal-identification-branch-seal-20260828.json. Its numerical findings
# are preserved in that seal and in omission/artifacts/.lab/. Kept for provenance and because
# other scripts in this directory still import it; do not extend or rerun it for new analysis.
"""dev_b2_bias_diagnosis_20260828.py -- mechanistic ablation of the ~+6-8ms positive lag bias
observed when running Candidate B2 (matched_filter_peak_realign) then trial_shuffle_pvalue on
the standard adversarial-benchmark positive control in
omission/jnwb_ext/common_driver_control.py (n_trials=60, jitter_sd_ms=8.0,
coupling_strength=1.2, coupling_lag_ms=30.0, coupling_direction="P_to_R").

Standalone diagnostic script. Does NOT edit common_driver_control.py (other agents work in that
shared file in parallel) -- only imports from it, or reimplements small generator variants here
for ablation purposes. Read-only with respect to the rest of the repo; writes no artifacts other
than this file's own stdout output (and, at the end, a small JSON summary next to this script).

Run: python omission/scripts/dev_b2_bias_diagnosis_20260828.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from omission.jnwb_ext.common_driver_control import (  # noqa: E402
    FS,
    LAGS_MS,
    matched_filter_peak_realign,
    synthesize_adversarial_pair,
    trial_shuffle_pvalue,
)
from omission.jnwb_ext.lag_estimation import lagged_association  # noqa: E402

# NOTE on speed: trial_shuffle_pvalue's observed_lag_ms/observed_peak are computed from
# C_obs = lagged_association(P_concat, R_concat, LAGS_MS, fs=FS) BEFORE any permutation --
# the n_perm=200 null-shuffle loop that follows is irrelevant to the lag-bias question this
# script asks (it only feeds the p-value, which we don't need). To keep this diagnosis
# tractable we replicate ONLY the observed-statistic computation (identical estimator, same
# LAGS_MS/FS, same lagged_association call) and skip the permutation null entirely.


def observed_lag_from_pair(P_trials, R_trials):
    """Replicates trial_shuffle_pvalue's observed_peak/observed_lag_ms computation exactly,
    without its (unused-here) n_perm=200 permutation-null loop."""
    P_concat = P_trials.reshape(-1)
    R_concat = R_trials.reshape(-1)
    C_obs = lagged_association(P_concat, R_concat, LAGS_MS, fs=FS)
    observed_peak = float(np.nanmax(np.abs(C_obs)))
    observed_lag = float(LAGS_MS[np.nanargmax(np.abs(C_obs))])
    return {"observed_peak": observed_peak, "observed_lag_ms": observed_lag}

# ---------------------------------------------------------------------------------------------
# Standard benchmark config (the setting where the +6-8ms bias was reported)
# ---------------------------------------------------------------------------------------------
STD = dict(
    n_trials=60, trial_len=400, p_center=150.0, p_sigma=25.0, r_center=220.0, r_sigma=5.0,
    jitter_sd_ms=8.0, coupling_strength=1.2, coupling_lag_ms=30.0, coupling_direction="P_to_R",
    noise_sd=0.3,
)
TRUE_LAG = STD["coupling_lag_ms"]
SEEDS = list(range(10))  # n=10 seeds for a stable readout


def _gaussian_kernel(t, center, sigma):
    return np.exp(-0.5 * ((t - center) / sigma) ** 2)


def synth_no_rindep(seed, **overrides):
    """Reimplementation of synthesize_adversarial_pair's inner loop with r_indep forced to
    zero, so R_trials = r_coupled + noise ONLY. Same RNG draw sequence/order as the original
    (e_i then noise draws) so this is a clean single-term ablation, not a different random
    stream. P_to_R direction only (matches STD)."""
    cfg = {**STD, **overrides}
    assert cfg["coupling_direction"] == "P_to_R"
    rng = np.random.default_rng(seed)
    t = np.arange(cfg["trial_len"])
    n_trials = cfg["n_trials"]
    P_trials = np.empty((n_trials, cfg["trial_len"]))
    R_trials = np.empty((n_trials, cfg["trial_len"]))
    for i in range(n_trials):
        e_i = rng.normal(0, cfg["jitter_sd_ms"]) if cfg["jitter_sd_ms"] > 0 else 0.0
        p_clean = _gaussian_kernel(t, cfg["p_center"] + e_i, cfg["p_sigma"])
        # r_indep intentionally OMITTED (ablation 1)
        r_coupled = cfg["coupling_strength"] * _gaussian_kernel(
            t, cfg["p_center"] + e_i + cfg["coupling_lag_ms"], cfg["p_sigma"]
        )
        P_trials[i] = p_clean + rng.normal(0, cfg["noise_sd"], cfg["trial_len"])
        R_trials[i] = r_coupled + rng.normal(0, cfg["noise_sd"], cfg["trial_len"])
    return P_trials, R_trials


def run_b2_then_pvalue(P_trials, R_trials, seed):
    P_al, R_al, shifts = matched_filter_peak_realign(P_trials, R_trials, seed=seed)
    res = observed_lag_from_pair(P_al, R_al)
    return res, shifts


def summarize(name, lags, true_lag=TRUE_LAG):
    lags = np.asarray(lags, dtype=float)
    mean_l = float(lags.mean())
    sd_l = float(lags.std(ddof=1)) if len(lags) > 1 else 0.0
    bias = mean_l - true_lag
    print(f"[{name}] n={len(lags)} mean={mean_l:.2f}ms sd={sd_l:.2f}ms "
          f"bias_vs_true={bias:+.2f}ms  raw_lags={lags.tolist()}")
    return {"name": name, "mean_lag_ms": mean_l, "sd_lag_ms": sd_l, "bias_ms": bias,
            "n_seeds": len(lags), "raw_lags_ms": lags.tolist()}


results = {}

# Sanity check: confirm observed_lag_from_pair's shortcut matches trial_shuffle_pvalue's own
# observed_lag_ms exactly (same estimator, we're just skipping its unused permutation null).
# Use n_perm=5 here (cheap) purely to exercise the real function once for the cross-check.
_P_chk, _R_chk, _ = synthesize_adversarial_pair(seed=0, **STD)
_Pal_chk, _Ral_chk, _ = matched_filter_peak_realign(_P_chk, _R_chk, seed=0)
_full = trial_shuffle_pvalue(_Pal_chk, _Ral_chk, n_perm=5, seed=100)
_fast = observed_lag_from_pair(_Pal_chk, _Ral_chk)
assert _full["observed_lag_ms"] == _fast["observed_lag_ms"], (
    f"shortcut mismatch: full={_full['observed_lag_ms']} fast={_fast['observed_lag_ms']}"
)
assert abs(_full["observed_peak"] - _fast["observed_peak"]) < 1e-12
print(f"[sanity check] observed_lag_from_pair matches trial_shuffle_pvalue's observed_lag_ms "
      f"exactly (seed=0, standard config, B2-realigned): {_fast['observed_lag_ms']}ms\n")

print("=" * 100)
print("ABLATION 0: baseline reproduction -- standard config, B2 realign, then trial_shuffle_pvalue")
print("=" * 100)
lags0 = []
for s in SEEDS:
    P, R, _ = synthesize_adversarial_pair(seed=s, **STD)
    res, _ = run_b2_then_pvalue(P, R, s)
    lags0.append(res["observed_lag_ms"])
results["0_baseline"] = summarize("0_baseline (B2 + pvalue, standard config)", lags0)

print()
print("=" * 100)
print("ABLATION 1: r_indep removed from R (R = r_coupled + noise only)")
print("=" * 100)
lags1 = []
for s in SEEDS:
    P, R = synth_no_rindep(s)
    res, _ = run_b2_then_pvalue(P, R, s)
    lags1.append(res["observed_lag_ms"])
results["1_no_rindep"] = summarize("1_no_rindep (B2 + pvalue, r_indep removed)", lags1)

print()
print("=" * 100)
print("ABLATION 2: symmetric kernel widths (r_sigma = p_sigma = 25.0)")
print("=" * 100)
lags2 = []
cfg2 = {**STD, "r_sigma": 25.0}
for s in SEEDS:
    P, R, _ = synthesize_adversarial_pair(seed=s, **cfg2)
    res, _ = run_b2_then_pvalue(P, R, s)
    lags2.append(res["observed_lag_ms"])
results["2_symmetric_kernels"] = summarize("2_symmetric_kernels (r_sigma=p_sigma=25)", lags2)

print()
print("=" * 100)
print("ABLATION 3: noiseless (noise_sd = 0.0)")
print("=" * 100)
lags3 = []
cfg3 = {**STD, "noise_sd": 0.0}
for s in SEEDS:
    P, R, _ = synthesize_adversarial_pair(seed=s, **cfg3)
    res, _ = run_b2_then_pvalue(P, R, s)
    lags3.append(res["observed_lag_ms"])
results["3_noiseless"] = summarize("3_noiseless (noise_sd=0.0)", lags3)

print()
print("=" * 100)
print("ABLATION 3b: noiseless AND r_indep removed (isolates pure geometric/structural residual)")
print("=" * 100)
lags3b = []
for s in SEEDS:
    P, R = synth_no_rindep(s, noise_sd=0.0)
    res, _ = run_b2_then_pvalue(P, R, s)
    lags3b.append(res["observed_lag_ms"])
results["3b_noiseless_no_rindep"] = summarize("3b_noiseless_no_rindep", lags3b)

print()
print("=" * 100)
print("ABLATION 4: lag-grid discretization check -- rerun ablation 0's realigned pairs on a")
print("finer 0.1ms lag grid; also report min |lag_grid_step| relative to observed bias size")
print("=" * 100)
fine_lags_ms = np.arange(-150, 150.05, 0.1)
lags4 = []
for s in SEEDS:
    P, R, _ = synthesize_adversarial_pair(seed=s, **STD)
    P_al, R_al, _ = matched_filter_peak_realign(P, R, seed=s)
    P_c = P_al.reshape(-1)
    R_c = R_al.reshape(-1)
    C = lagged_association(P_c, R_c, fine_lags_ms, fs=FS)
    peak_lag = float(fine_lags_ms[np.nanargmax(np.abs(C))])
    lags4.append(peak_lag)
print(f"Standard grid step = {LAGS_MS[1]-LAGS_MS[0]:.3f}ms; fine grid step = "
      f"{fine_lags_ms[1]-fine_lags_ms[0]:.3f}ms")
results["4_fine_grid"] = summarize("4_fine_grid (0.1ms resolution, same realigned pairs)", lags4)
print("If ablation 0 and ablation 4 means match closely, the 1ms grid is not the source of the "
      "bias (bias is not a discretization artifact).")

print()
print("=" * 100)
print("ABLATION 5: matched-filter shift-estimate bias -- does adding coupling to R change the")
print("DISTRIBUTION of P's own estimated per-trial shifts, and where does P_aligned's kernel")
print("end up relative to R's coupling bump after realignment?")
print("=" * 100)
for s in SEEDS[:5]:
    P0, R0, jit0 = synthesize_adversarial_pair(seed=s, **{**STD, "coupling_strength": 0.0})
    P1, R1, jit1 = synthesize_adversarial_pair(seed=s, **STD)
    same_P = np.allclose(P0, P1)
    _, _, shifts0 = matched_filter_peak_realign(P0, R0, seed=s)
    _, _, shifts1 = matched_filter_peak_realign(P1, R1, seed=s)
    same_shifts = np.array_equal(shifts0, shifts1)
    print(f"  seed={s}: P identical across coupling_strength 0 vs 1.2? {same_P} | "
          f"B2 shifts identical? {same_shifts} | "
          f"shift diff (max abs) = {np.max(np.abs(shifts0 - shifts1))}")
results["5_note"] = "see stdout: confirms whether P generation / P-based shift estimate depends on coupling_strength"

print()
print("=" * 100)
print("ABLATION 6: no realignment at all -- trial_shuffle_pvalue on RAW (unaligned) standard pair")
print("=" * 100)
lags6 = []
for s in SEEDS:
    P, R, _ = synthesize_adversarial_pair(seed=s, **STD)
    res = observed_lag_from_pair(P, R)
    lags6.append(res["observed_lag_ms"])
results["6_no_realign"] = summarize("6_no_realign (raw pair, no B2)", lags6)

print()
print("=" * 100)
print("SUMMARY TABLE (mean recovered lag vs true=%.1fms)" % TRUE_LAG)
print("=" * 100)
for key in ["0_baseline", "1_no_rindep", "2_symmetric_kernels", "3_noiseless",
            "3b_noiseless_no_rindep", "4_fine_grid", "6_no_realign"]:
    r = results[key]
    print(f"  {key:28s} mean={r['mean_lag_ms']:7.2f}ms  sd={r['sd_lag_ms']:6.2f}ms  "
          f"bias={r['bias_ms']:+6.2f}ms  n={r['n_seeds']}")

out_path = Path(__file__).with_suffix(".summary.json")
with open(out_path, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nWrote summary JSON to {out_path}")
