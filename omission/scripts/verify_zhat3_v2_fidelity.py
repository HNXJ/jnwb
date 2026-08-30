"""V2/V3: INDEPENDENT behavioral-proxy fidelity sweep. Does NOT call simulate_behavioral_proxy.

Two proxy constructions, both with the achieved empirical r(B, true_gain) MEASURED, not assumed:

  construction_A "exact_r_linear" -- Gram-Schmidt: center true_gain to u (unit norm), draw fresh
      noise, residualise it against u to get v (unit norm, exactly orthogonal), set
      B = r*u + sqrt(1-r^2)*v. The FINITE-SAMPLE Pearson correlation with true_gain is then
      exactly r, removing the sampling scatter in achieved r that the original's
      sigma_noise = sigma_gain*sqrt(1/r^2 - 1) algebra leaves behind.

  construction_B "sluggish_AR1_observation" -- a mechanistically different, more realistic proxy:
      a noisy observation of the gain state passed through a first-order lag,
      raw_i = gain_i + sd*e_i ;  B_i = (1-lam)*raw_i + lam*B_{i-1},  lam = 0.5,
      i.e. the behavioural readout responds sluggishly (pupil-like). sd is found by BISECTION on
      the achieved empirical correlation, so the target r is hit empirically rather than
      algebraically.

Grid resolves the transition the original left under-sampled (it jumped 0.8 -> 0.95):
  0.0 0.2 0.4 0.5 0.6 0.7 0.8 0.85 0.88 0.90 0.92 0.95 0.98

Fresh seed block, disjoint from V1's and from both originals': z_seed = 4000+s,
private_seed = 4500000+s, s in 0..24.

Scenarios: gain_null (beta=0), gain_PC2 (beta=1.5, same confound), pure_PC2 (beta=1.5, NO
confound -- the magnitude of genuine coupling with nothing spurious mixed in).

Run: python -m omission.scripts.verify_zhat3_v2_fidelity
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
BETA = 1.5
N_SEEDS = 25
SEEDS = list(range(N_SEEDS))
Z_SEED_BASE = 4000
PRIV_SEED_BASE = 4500000
R_GRID = [0.0, 0.2, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.88, 0.90, 0.92, 0.95, 0.98]
FOCUS_R = [0.4, 0.5, 0.6]           # V3 load-bearing regime
N_PERM = 200

SCENARIOS = {
    "gain_null": dict(jitter_sd_ms=0.0, amp_gain=0.6, beta=0.0),
    "gain_PC2":  dict(jitter_sd_ms=0.0, amp_gain=0.6, beta=BETA),
    "pure_PC2":  dict(jitter_sd_ms=0.0, amp_gain=0.0, beta=BETA),
}


def proxy_exact_r_linear(true_gain, r, rng):
    g = true_gain - true_gain.mean()
    u = g / np.linalg.norm(g)
    e = rng.normal(0, 1, len(g))
    e = e - e.mean()
    e = e - (e @ u) * u
    v = e / np.linalg.norm(e)
    return r * u + np.sqrt(max(1 - r ** 2, 0.0)) * v


def _sluggish(true_gain, sd, rng_state_seed, lam=0.5):
    rng = np.random.default_rng(rng_state_seed)
    raw = true_gain + sd * rng.normal(0, 1, len(true_gain))
    b = np.empty_like(raw)
    b[0] = raw[0]
    for i in range(1, len(raw)):
        b[i] = (1 - lam) * raw[i] + lam * b[i - 1]
    return b


def proxy_sluggish_ar1(true_gain, r_target, seed):
    """Bisect the observation-noise sd so the ACHIEVED empirical r hits r_target."""
    if r_target <= 0:
        return np.random.default_rng(seed).normal(0, 1, len(true_gain))
    lo, hi = 0.0, 50.0 * (np.std(true_gain) + 1e-9)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        b = _sluggish(true_gain, mid, seed)
        rr = np.corrcoef(b, true_gain)[0, 1]
        if rr > r_target:
            lo = mid
        else:
            hi = mid
    return _sluggish(true_gain, 0.5 * (lo + hi), seed)


def make(scenario, s):
    return synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, rho=RHO, delay_ms=DELAY_MS, coupling_kind="realized",
        z_seed=Z_SEED_BASE + s, private_seed=PRIV_SEED_BASE + s, **SCENARIOS[scenario])


t_start = time.time()
store = {sc: {"no_B_orig": [], "no_B_indep": [],
              "A": {str(r): {"delta_orig": [], "delta_indep": [], "achieved_r": [],
                             "boot_lo": [], "perm_p": []} for r in R_GRID},
              "B": {str(r): {"delta_indep": [], "achieved_r": []} for r in R_GRID}}
         for sc in SCENARIOS}

for sc in SCENARIOS:
    t0 = time.time()
    for s in SEEDS:
        P, R, true_jitter, true_gain, _ = make(sc, s)
        ds = build_trial_level_dataset(P, R, seed=s)
        th = estimate_timing_nested(P, n_splits=5, seed=s)
        feat = indep_features(P, R)
        th_i = indep_timing_hat(P, n_folds=10, seed=s + 991)
        base_Z_orig = dict(timing_hat=th)
        base_Z_indep = [feat["amplitude"], th_i]

        store[sc]["no_B_orig"].append(float(fit_nuisance_tier(
            ds, "Zhat-2_plus_timing_gain", n_splits=5, seed=s, **base_Z_orig)["delta"]))
        store[sc]["no_B_indep"].append(float(indep_delta(feat, base_Z_indep, seed=s)["delta"]))

        if np.std(true_gain) == 0:      # pure_PC2 has no gain state; B is undefined there
            continue

        rng = np.random.default_rng(Z_SEED_BASE + s + 12345)
        for r in R_GRID:
            BA = proxy_exact_r_linear(true_gain, r, rng)
            achA = float(np.corrcoef(BA, true_gain)[0, 1])
            fo = fit_nuisance_tier(ds, "Zhat-2_plus_timing_gain", timing_hat=th,
                                   extra_Z=[BA], n_splits=5, seed=s)
            resA = indep_delta(feat, base_Z_indep + [BA], seed=s)
            cell = store[sc]["A"][str(r)]
            cell["delta_orig"].append(float(fo["delta"]))
            cell["delta_indep"].append(float(resA["delta"]))
            cell["achieved_r"].append(achA)
            if sc == "gain_null" and r in FOCUS_R:
                lo, _hi = bootstrap_delta_ci(resA["y"], resA["pred_M2"], resA["pred_M3"],
                                             n_boot=2000, seed=s)
                cell["boot_lo"].append(lo)
                cell["perm_p"].append(permutation_delta_p(resA, n_perm=N_PERM, seed=s))

            BB = proxy_sluggish_ar1(true_gain, r, Z_SEED_BASE + 777 + s)
            achB = float(np.corrcoef(BB, true_gain)[0, 1])
            resB = indep_delta(feat, base_Z_indep + [BB], seed=s)
            store[sc]["B"][str(r)]["delta_indep"].append(float(resB["delta"]))
            store[sc]["B"][str(r)]["achieved_r"].append(achB)
    print(f"{sc:10s} [{time.time()-t0:6.1f}s] no_B orig={np.mean(store[sc]['no_B_orig']):+.4f} "
          f"indep={np.mean(store[sc]['no_B_indep']):+.4f}")

# ------------------------------------------------------------------ summarise
summary = {}
for sc in SCENARIOS:
    summary[sc] = {"no_B": {
        "orig_delta_mean": float(np.mean(store[sc]["no_B_orig"])),
        "orig_delta_sd": float(np.std(store[sc]["no_B_orig"], ddof=1)),
        "indep_delta_mean": float(np.mean(store[sc]["no_B_indep"])),
        "indep_delta_sd": float(np.std(store[sc]["no_B_indep"], ddof=1)),
    }}
    for con in ["A", "B"]:
        summary[sc][con] = {}
        for r in R_GRID:
            c = store[sc][con][str(r)]
            if not c["delta_indep"]:
                continue
            di = np.array(c["delta_indep"])
            row = {"target_r": r,
                   "achieved_r_mean": float(np.mean(c["achieved_r"])),
                   "achieved_r_sd": float(np.std(c["achieved_r"], ddof=1)),
                   "indep_delta_mean": float(di.mean()), "indep_delta_sd": float(di.std(ddof=1)),
                   "indep_delta_min": float(di.min()), "indep_delta_max": float(di.max())}
            if con == "A":
                do = np.array(c["delta_orig"])
                row.update({"orig_delta_mean": float(do.mean()), "orig_delta_sd": float(do.std(ddof=1)),
                            "orig_delta_min": float(do.min()), "orig_delta_max": float(do.max())})
            if SCENARIOS[sc]["beta"] == 0.0:
                for label, arr in [("rule_A_indep_gt_0.05", di > 0.05)] + (
                        [("rule_A_orig_gt_0.05", np.array(c["delta_orig"]) > 0.05)] if con == "A" else []):
                    k = int(arr.sum())
                    cp = clopper_pearson(k, len(arr))
                    row[label] = {"k": k, "n": int(len(arr)), "fpr": k / len(arr),
                                  "clopper_pearson_95": [cp[0], cp[1]]}
                if c.get("boot_lo"):
                    k = int(np.sum(np.array(c["boot_lo"]) > 0))
                    cp = clopper_pearson(k, len(c["boot_lo"]))
                    row["rule_B_boot_ci_excludes_zero"] = {
                        "k": k, "n": len(c["boot_lo"]), "fpr": k / len(c["boot_lo"]),
                        "clopper_pearson_95": [cp[0], cp[1]]}
                if c.get("perm_p"):
                    k = int(np.sum(np.array(c["perm_p"]) < 0.05))
                    cp = clopper_pearson(k, len(c["perm_p"]))
                    row["rule_C_perm_p_lt_0.05"] = {
                        "k": k, "n": len(c["perm_p"]), "fpr": k / len(c["perm_p"]),
                        "clopper_pearson_95": [cp[0], cp[1]]}
            summary[sc][con][str(r)] = row

out = {"config": {"n_trials": N_TRIALS, "rho": RHO, "delay_ms": DELAY_MS, "beta": BETA,
                  "n_seeds": N_SEEDS, "z_seed_base": Z_SEED_BASE,
                  "private_seed_base": PRIV_SEED_BASE, "r_grid": R_GRID, "focus_r": FOCUS_R,
                  "n_perm": N_PERM, "scenarios": {k: dict(v) for k, v in SCENARIOS.items()},
                  "wall_clock_s": None},
       "summary": summary, "raw": store}
out["config"]["wall_clock_s"] = time.time() - t_start
p = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "_verify_zhat3_v2_partial.json"
p.write_text(json.dumps(out, indent=1))
print(f"\nwall {out['config']['wall_clock_s']:.1f}s -> {p}")
