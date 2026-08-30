"""V1 (+ V4 null legs): INDEPENDENT re-check of observable-tier null calibration on FRESH seeds.

Fresh, disjoint RNG streams: z_seed = 3000+s, private_seed = 3500000+s, s in 0..24 (25 seeds).
The originals used z_seed 0-19 with private_seed +700000 / +960000, so no draw is shared.

Four null scenarios (beta=0 throughout, coupling_kind="realized", n_trials=300, rho=0.5,
delay_ms=30):
    gain_null        jitter_sd_ms=0,  amp_gain=0.6        (AR(1) amp_phi=0.95 latent gain)
    combined_null    jitter_sd_ms=8,  amp_gain=0.6
    timing_null      jitter_sd_ms=8,  amp_gain=0
    slow_timing_null amp_gain=0, true_jitter supplied as an AR(1)(phi=0.95, sd=8ms) SERIES
                     -- a slow shared state that is NOT the amplitude-gain state, added because
                     the P4 criterion (d) "slow shared-state confounding" would otherwise be
                     tested only by the same AR(1) gain process that already defines (b).

Four tiers (Zhat-0/1/2 + oracle) evaluated BOTH through the original `fit_nuisance_tier`
(reproduction) and through a fully independent OLS/10-fold/numpy implementation
(verify_zhat3_common) whose features and cross-fit timing estimate are also re-derived.

Three decision rules, so the conclusion cannot rest on the original's arbitrary delta>0.05 cut:
    rule_A  delta > 0.05                       (original convention)
    rule_A0 delta > 0                          (most lenient possible)
    rule_B  bootstrap-over-trials 95% CI of delta excludes 0 from below
    rule_C  within-dataset lag-feature trial-permutation null, one-sided p < 0.05
            (the only one of the four an analyst could actually run on real data)

Run: python -m omission.scripts.verify_zhat3_v1_calibration
"""
import json
import time
from pathlib import Path

import numpy as np

from omission.jnwb_ext.realized_coupling_generator import synthesize_realized_coupling_pair
from omission.jnwb_ext.distributed_lag_model import (
    build_trial_level_dataset, estimate_timing_nested, fit_nuisance_tier,
)
from omission.scripts.verify_zhat3_common import (
    indep_features, indep_timing_hat, indep_delta, bootstrap_delta_ci, permutation_delta_p,
    clopper_pearson,
)

N_TRIALS = 300
RHO = 0.5
DELAY_MS = 30.0
N_SEEDS = 25
SEEDS = list(range(N_SEEDS))
Z_SEED_BASE = 3000
PRIV_SEED_BASE = 3500000
N_PERM = 200
TIERS = ["Zhat-0_design_only", "Zhat-1_plus_pre_neural_state", "Zhat-2_plus_timing_gain", "oracle"]

SCENARIOS = {
    "gain_null":        dict(jitter_sd_ms=0.0, amp_gain=0.6, beta=0.0),
    "combined_null":    dict(jitter_sd_ms=8.0, amp_gain=0.6, beta=0.0),
    "timing_null":      dict(jitter_sd_ms=8.0, amp_gain=0.0, beta=0.0),
    "slow_timing_null": dict(jitter_sd_ms=0.0, amp_gain=0.0, beta=0.0),  # true_jitter injected
}


def ar1_series(n, phi, sd, rng):
    z = np.zeros(n)
    z[0] = rng.normal(0, 1)
    for i in range(1, n):
        z[i] = phi * z[i - 1] + rng.normal(0, np.sqrt(max(1 - phi ** 2, 1e-9)))
    return sd * z


def make(scenario, s):
    z_seed, priv_seed = Z_SEED_BASE + s, PRIV_SEED_BASE + s
    kw = dict(SCENARIOS[scenario])
    tj = None
    if scenario == "slow_timing_null":
        tj = ar1_series(N_TRIALS, 0.95, 8.0, np.random.default_rng(z_seed + 55555))
    return synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, rho=RHO, delay_ms=DELAY_MS, coupling_kind="realized",
        z_seed=z_seed, private_seed=priv_seed, true_jitter=tj, **kw)


t_start = time.time()
raw = {sc: {t: {"orig_delta": [], "indep_delta": [], "boot_lo": [], "boot_hi": [], "perm_p": []}
            for t in TIERS} for sc in SCENARIOS}
timing_fidelity = {sc: [] for sc in SCENARIOS}
gain_fidelity = {sc: [] for sc in SCENARIOS}

for sc in SCENARIOS:
    t0 = time.time()
    for s in SEEDS:
        P, R, true_jitter, true_gain, _ = make(sc, s)

        # ---- original code path
        ds = build_trial_level_dataset(P, R, seed=s)
        th = estimate_timing_nested(P, n_splits=5, seed=s)
        for tier in TIERS:
            fit = fit_nuisance_tier(ds, tier, timing_hat=th, true_jitter=true_jitter,
                                    true_gain=true_gain, n_splits=5, seed=s)
            raw[sc][tier]["orig_delta"].append(float(fit["delta"]))

        # ---- independent code path
        feat = indep_features(P, R)
        th_i = indep_timing_hat(P, n_folds=10, seed=s + 991)
        Zmap = {
            "Zhat-0_design_only": [],
            "Zhat-1_plus_pre_neural_state": [feat["amplitude"]],
            "Zhat-2_plus_timing_gain": [feat["amplitude"], th_i],
            "oracle": [true_jitter, true_gain],
        }
        for tier in TIERS:
            res = indep_delta(feat, Zmap[tier], n_folds=10, seed=s)
            raw[sc][tier]["indep_delta"].append(float(res["delta"]))
            lo, hi = bootstrap_delta_ci(res["y"], res["pred_M2"], res["pred_M3"], n_boot=2000, seed=s)
            raw[sc][tier]["boot_lo"].append(lo)
            raw[sc][tier]["boot_hi"].append(hi)
            raw[sc][tier]["perm_p"].append(permutation_delta_p(res, n_perm=N_PERM, seed=s))

        if np.std(true_jitter) > 0:
            timing_fidelity[sc].append(float(np.corrcoef(th_i, true_jitter)[0, 1]))
        if np.std(true_gain) > 0:
            gain_fidelity[sc].append(float(np.corrcoef(feat["amplitude"], true_gain)[0, 1]))
    print(f"{sc:18s} [{time.time()-t0:6.1f}s] " + "  ".join(
        f"{t.split('_')[0]}: orig={np.mean(raw[sc][t]['orig_delta']):+.3f} "
        f"indep={np.mean(raw[sc][t]['indep_delta']):+.3f}" for t in TIERS))

summary = {}
for sc in SCENARIOS:
    summary[sc] = {}
    for tier in TIERS:
        d_o = np.array(raw[sc][tier]["orig_delta"])
        d_i = np.array(raw[sc][tier]["indep_delta"])
        lo = np.array(raw[sc][tier]["boot_lo"])
        pp = np.array(raw[sc][tier]["perm_p"])
        cell = {
            "n_seeds": N_SEEDS,
            "orig_delta_mean": float(d_o.mean()), "orig_delta_sd": float(d_o.std(ddof=1)),
            "orig_delta_min": float(d_o.min()), "orig_delta_max": float(d_o.max()),
            "indep_delta_mean": float(d_i.mean()), "indep_delta_sd": float(d_i.std(ddof=1)),
            "indep_delta_min": float(d_i.min()), "indep_delta_max": float(d_i.max()),
        }
        for label, k in [("rule_A_orig_delta_gt_0.05", int(np.sum(d_o > 0.05))),
                         ("rule_A_indep_delta_gt_0.05", int(np.sum(d_i > 0.05))),
                         ("rule_A0_indep_delta_gt_0", int(np.sum(d_i > 0))),
                         ("rule_B_boot_ci_excludes_zero", int(np.sum(lo > 0))),
                         ("rule_C_perm_p_lt_0.05", int(np.sum(pp < 0.05)))]:
            cp = clopper_pearson(k, N_SEEDS)
            cell[label] = {"k": k, "n": N_SEEDS, "fpr": k / N_SEEDS,
                           "clopper_pearson_95": [cp[0], cp[1]]}
        summary[sc][tier] = cell

out = {
    "config": {"n_trials": N_TRIALS, "rho": RHO, "delay_ms": DELAY_MS, "n_seeds": N_SEEDS,
               "z_seed_base": Z_SEED_BASE, "private_seed_base": PRIV_SEED_BASE,
               "n_perm": N_PERM, "tiers": TIERS,
               "scenarios": {k: dict(v) for k, v in SCENARIOS.items()},
               "slow_timing_null_note": "true_jitter supplied as AR(1) phi=0.95, marginal sd 8 ms, "
                                        "amp_gain=0 -> a slow shared state acting on TIMING, "
                                        "structurally distinct from the AR(1) gain state",
               "wall_clock_s": None},
    "summary": summary,
    "nuisance_fidelity": {
        "indep_timing_hat_vs_true_jitter_mean_r": {sc: (float(np.mean(v)) if v else None)
                                                   for sc, v in timing_fidelity.items()},
        "amplitude_vs_true_gain_mean_r": {sc: (float(np.mean(v)) if v else None)
                                           for sc, v in gain_fidelity.items()},
    },
    "raw": raw,
}
out["config"]["wall_clock_s"] = time.time() - t_start
p = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "_verify_zhat3_v1_partial.json"
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(out, indent=1))
print(f"\nwall {out['config']['wall_clock_s']:.1f}s -> {p}")
