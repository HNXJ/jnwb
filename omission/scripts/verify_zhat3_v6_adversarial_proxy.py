"""V6 (verifier-added, adversarial): can a BETTER OBSERVABLE gain proxy rescue the tiers?

The negative conclusion says no observable nuisance tier permits identification against the
latent gain confound. Before accepting that, the strongest observable proxy an analyst could
actually build must be tried -- otherwise the conclusion is only about the three tiers that
happened to be coded, not about observability.

The latent gain state is AR(1) with amp_phi=0.95 ACROSS TRIALS. The single-trial baseline
amplitude is a noisy read of it (r ~ 0.27). But an analyst can average each trial's baseline
amplitude with its NEIGHBOURING trials' baseline amplitudes: the gain state barely moves over a
few trials while the measurement noise averages down. That estimator uses only P's pre-event
baseline windows -- exactly the same material Zhat-1 already declared safe -- so it is fully
observable and carries no extra causal risk.

Three observable gain estimators are compared on the same fresh gain-null data (z_seed=6000+s,
private_seed=6500000+s, 25 seeds):
    amp_raw        single-trial baseline amplitude (= Zhat-1/2's proxy)
    amp_smooth     exponentially weighted average over +-W trials, weights phi^|lag|, phi=0.95
    amp_smooth_loo the same, but LEAVE-ONE-OUT (current trial excluded) -- a stricter variant
                   that cannot be accused of re-using the trial's own baseline twice
plus nonlinear capacity checks (cubic polynomial in amp_raw, and amp_raw + amp_smooth jointly),
because "the proxy is noisy" and "the conditioning is not flexible enough" are different failure
modes and must be separated.

Reports achieved r with true_gain and the gain-null FPR for each. Also runs the matched positive
control (beta=1.5) so any estimator that DOES fix calibration can be checked for retained power.

Run: python -m omission.scripts.verify_zhat3_v6_adversarial_proxy
"""
import json
import time
from pathlib import Path

import numpy as np

from omission.jnwb_ext.realized_coupling_generator import synthesize_realized_coupling_pair
from omission.scripts.verify_zhat3_common import (
    indep_features, indep_timing_hat, indep_delta, clopper_pearson,
)

N_TRIALS = 300
RHO = 0.5
DELAY_MS = 30.0
N_SEEDS = 25
Z_SEED_BASE = 6000
PRIV_SEED_BASE = 6500000
PHI = 0.95
W = 40


def ewma_neighbour(x, phi=PHI, w=W, leave_one_out=False):
    """Symmetric exponentially-weighted neighbour average of a per-trial scalar. Weight phi^|lag|
    matches the AR(1) autocorrelation of the latent state. leave_one_out drops the centre weight."""
    n = len(x)
    lags = np.arange(-w, w + 1)
    wt = phi ** np.abs(lags)
    if leave_one_out:
        wt[lags == 0] = 0.0
    out = np.empty(n)
    for i in range(n):
        idx = i + lags
        ok = (idx >= 0) & (idx < n)
        out[i] = np.sum(wt[ok] * x[idx[ok]]) / np.sum(wt[ok])
    return out


def poly3(x):
    z = (x - x.mean()) / (x.std() + 1e-12)
    return [z, z ** 2, z ** 3]


t_start = time.time()
VARIANTS = ["amp_raw", "amp_raw_cubic", "amp_smooth", "amp_smooth_loo", "amp_raw+amp_smooth"]
store = {sc: {v: {"delta": []} for v in VARIANTS} for sc in ["gain_null", "gain_PC2"]}
fid = {"amp_raw": [], "amp_smooth": [], "amp_smooth_loo": []}

for sc, beta in [("gain_null", 0.0), ("gain_PC2", 1.5)]:
    t0 = time.time()
    for s in range(N_SEEDS):
        P, R, tj, tg, _ = synthesize_realized_coupling_pair(
            n_trials=N_TRIALS, jitter_sd_ms=0.0, amp_gain=0.6, beta=beta, rho=RHO,
            delay_ms=DELAY_MS, coupling_kind="realized",
            z_seed=Z_SEED_BASE + s, private_seed=PRIV_SEED_BASE + s)
        feat = indep_features(P, R)
        th = indep_timing_hat(P, n_folds=10, seed=s + 991)
        amp = feat["amplitude"]
        amp_s = ewma_neighbour(amp)
        amp_l = ewma_neighbour(amp, leave_one_out=True)
        if sc == "gain_null":
            fid["amp_raw"].append(float(np.corrcoef(amp, tg)[0, 1]))
            fid["amp_smooth"].append(float(np.corrcoef(amp_s, tg)[0, 1]))
            fid["amp_smooth_loo"].append(float(np.corrcoef(amp_l, tg)[0, 1]))
        Zsets = {
            "amp_raw": [amp, th],
            "amp_raw_cubic": poly3(amp) + [th],
            "amp_smooth": [amp_s, th],
            "amp_smooth_loo": [amp_l, th],
            "amp_raw+amp_smooth": [amp, amp_s, th],
        }
        for v in VARIANTS:
            store[sc][v]["delta"].append(float(indep_delta(feat, Zsets[v], seed=s)["delta"]))
    print(f"{sc:10s} [{time.time()-t0:5.1f}s] " +
          "  ".join(f"{v}={np.mean(store[sc][v]['delta']):+.4f}" for v in VARIANTS))

summary = {"observable_gain_proxy_fidelity": {
    k: {"mean_r_with_true_gain": float(np.mean(v)), "sd": float(np.std(v, ddof=1))}
    for k, v in fid.items()}}
for v in VARIANTS:
    dn = np.array(store["gain_null"][v]["delta"])
    dp = np.array(store["gain_PC2"][v]["delta"])
    k = int(np.sum(dn > 0.05))
    cp = clopper_pearson(k, N_SEEDS)
    summary[v] = {
        "gain_null_delta_mean": float(dn.mean()), "gain_null_delta_sd": float(dn.std(ddof=1)),
        "gain_null_delta_min": float(dn.min()), "gain_null_delta_max": float(dn.max()),
        "gain_null_FPR_delta_gt_0.05": {"k": k, "n": N_SEEDS, "fpr": k / N_SEEDS,
                                         "clopper_pearson_95": [cp[0], cp[1]]},
        "gain_PC2_delta_mean": float(dp.mean()), "gain_PC2_delta_sd": float(dp.std(ddof=1)),
        "paired_PC2_minus_null_mean": float(np.mean(dp - dn)),
    }

out = {"config": {"n_trials": N_TRIALS, "n_seeds": N_SEEDS, "rho": RHO, "delay_ms": DELAY_MS,
                  "amp_gain": 0.6, "amp_phi_generator": 0.95, "smoothing_phi": PHI,
                  "smoothing_halfwidth_trials": W, "z_seed_base": Z_SEED_BASE,
                  "private_seed_base": PRIV_SEED_BASE, "wall_clock_s": time.time() - t_start},
       "summary": summary, "raw": store}
p = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "_verify_zhat3_v6_partial.json"
p.write_text(json.dumps(out, indent=1))
print("\n" + json.dumps(summary, indent=1))
print(f"-> {p}")
