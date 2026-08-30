"""V4: directional-asymmetry + PC2-detection leg of the P4 unlock check, UNDER THE GAIN CONFOUND.

The bridge benchmark's directional-asymmetry scenarios (7-9) were run with amp_gain=0.0 -- i.e.
with the timing confound only, never with the gain confound that is the whole problem. This
script re-runs the asymmetry test WITH the AR(1) gain state active, on fresh seeds
(z_seed = 5000+s, private_seed = 5500000+s, s in 0..19), which is what criterion "correct
directional asymmetry" has to survive if the tiers are to be unlocked.

Scenarios (bidirectional generator, jitter_sd_ms=0, amp_gain=0.6, coupling_kind="realized"):
    P_to_R_only  beta_p_to_r=1.5, beta_r_to_p=0
    R_to_P_only  beta_p_to_r=0,   beta_r_to_p=calibrated-to-matched-energy
    null_ref     both 0

Tiers: Zhat-2, Zhat-2 + behavioural proxy B at a PLAUSIBLE fidelity (exact r = 0.6), and oracle.
A = delta(P->R direction) - delta(R->P direction); correct asymmetry = A>0 for P_to_R_only and
A<0 for R_to_P_only.

Run: python -m omission.scripts.verify_zhat3_v4_direction
"""
import json
import time
from pathlib import Path

import numpy as np

from omission.jnwb_ext.realized_coupling_generator import (
    synthesize_bidirectional_coupling_pair, calibrate_matched_beta_r_to_p,
)
from omission.scripts.verify_zhat3_common import (
    indep_features, indep_timing_hat, indep_delta, clopper_pearson, proxy_exact_r_linear,
)

N_TRIALS = 300
RHO = 0.5
DELAY_MS = 30.0
BETA = 1.5
N_SEEDS = 20
Z_SEED_BASE = 5000
PRIV_SEED_BASE = 5500000
B_FIDELITY = 0.6

calib = calibrate_matched_beta_r_to_p(target_beta_p_to_r=BETA, coupling_kind="realized")
BRP = calib["calibrated_beta_r_to_p"]
print(f"calibrated beta_r_to_p={BRP:.5f} (relative_mismatch={calib['relative_mismatch']:.4f})")

SCEN = {
    "P_to_R_only": dict(beta_p_to_r=BETA, beta_r_to_p=0.0),
    "R_to_P_only": dict(beta_p_to_r=0.0, beta_r_to_p=BRP),
    "null_ref":    dict(beta_p_to_r=0.0, beta_r_to_p=0.0),
}
TIERS = ["Zhat-2", "Zhat-2+B(r=0.6)", "oracle"]

t_start = time.time()
store = {sc: {t: {"fwd": [], "swap": [], "A": []} for t in TIERS} for sc in SCEN}

for sc, kw in SCEN.items():
    t0 = time.time()
    for s in range(N_SEEDS):
        P, R, tj, tg, _pp, _rp = synthesize_bidirectional_coupling_pair(
            n_trials=N_TRIALS, jitter_sd_ms=0.0, amp_gain=0.6, rho=RHO, delay_ms=DELAY_MS,
            coupling_kind="realized", z_seed=Z_SEED_BASE + s, private_seed=PRIV_SEED_BASE + s, **kw)
        B = proxy_exact_r_linear(tg, B_FIDELITY, np.random.default_rng(Z_SEED_BASE + s + 999))

        feat_f = indep_features(P, R)
        feat_s = indep_features(R, P)
        th_f = indep_timing_hat(P, n_folds=10, seed=s + 991)
        th_s = indep_timing_hat(R, n_folds=10, seed=s + 991)
        Z = {
            "Zhat-2": ([feat_f["amplitude"], th_f], [feat_s["amplitude"], th_s]),
            "Zhat-2+B(r=0.6)": ([feat_f["amplitude"], th_f, B], [feat_s["amplitude"], th_s, B]),
            "oracle": ([tj, tg], [tj, tg]),
        }
        for tier in TIERS:
            zf, zs = Z[tier]
            df = indep_delta(feat_f, zf, seed=s)["delta"]
            dsw = indep_delta(feat_s, zs, seed=s)["delta"]
            store[sc][tier]["fwd"].append(float(df))
            store[sc][tier]["swap"].append(float(dsw))
            store[sc][tier]["A"].append(float(df - dsw))
    print(f"{sc:13s} [{time.time()-t0:5.1f}s] " + "  ".join(
        f"{t}: fwd={np.mean(store[sc][t]['fwd']):+.3f} swap={np.mean(store[sc][t]['swap']):+.3f} "
        f"A={np.mean(store[sc][t]['A']):+.3f}" for t in TIERS))

summary = {}
for sc in SCEN:
    summary[sc] = {}
    for tier in TIERS:
        f = np.array(store[sc][tier]["fwd"])
        w = np.array(store[sc][tier]["swap"])
        A = np.array(store[sc][tier]["A"])
        cell = {"fwd_delta_mean": float(f.mean()), "fwd_delta_sd": float(f.std(ddof=1)),
                "swap_delta_mean": float(w.mean()), "swap_delta_sd": float(w.std(ddof=1)),
                "A_mean": float(A.mean()), "A_sd": float(A.std(ddof=1)), "n_seeds": N_SEEDS}
        if sc != "null_ref":
            want_pos = sc == "P_to_R_only"
            k = int(np.sum(A > 0)) if want_pos else int(np.sum(A < 0))
            cp = clopper_pearson(k, N_SEEDS)
            cell["correct_asymmetry_sign"] = {
                "k": k, "n": N_SEEDS, "rate": k / N_SEEDS, "clopper_pearson_95": [cp[0], cp[1]],
                "expected_sign": "A>0" if want_pos else "A<0"}
        for lbl, arr in [("fwd_gt_0.05", f), ("swap_gt_0.05", w)]:
            k = int(np.sum(arr > 0.05))
            cp = clopper_pearson(k, N_SEEDS)
            cell[lbl] = {"k": k, "n": N_SEEDS, "rate": k / N_SEEDS, "clopper_pearson_95": [cp[0], cp[1]]}
        summary[sc][tier] = cell

out = {"config": {"n_trials": N_TRIALS, "rho": RHO, "delay_ms": DELAY_MS, "beta_p_to_r": BETA,
                  "beta_r_to_p_calibrated": BRP, "calibration": calib, "n_seeds": N_SEEDS,
                  "z_seed_base": Z_SEED_BASE, "private_seed_base": PRIV_SEED_BASE,
                  "amp_gain": 0.6, "jitter_sd_ms": 0.0, "B_fidelity_r": B_FIDELITY,
                  "wall_clock_s": time.time() - t_start},
       "summary": summary, "raw": store}
p = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "_verify_zhat3_v4_partial.json"
p.write_text(json.dumps(out, indent=1))
print(f"\nwall {out['config']['wall_clock_s']:.1f}s -> {p}")
