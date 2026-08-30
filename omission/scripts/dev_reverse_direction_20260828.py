# SUPERSEDED (2026-08-30): this script belongs to the causal-identification investigation,
# CONFIRMED closed by causal-identification-branch-seal-20260828.json. Its numerical findings
# are preserved in that seal and in omission/artifacts/.lab/. Kept for provenance and because
# other scripts in this directory still import it; do not extend or rerun it for new analysis.
"""Reverse-direction / directional-asymmetry benchmark (2026-08-28, Hamm). Uses
synthesize_bidirectional_coupling_pair (independent P_private/R_private, coupling injectable in
either/both directions) with energy-matched beta (calibrate_matched_beta_r_to_p) so P->R and
R->P conditions inject comparable coupling energy despite P/R's differing shared-kernel widths.

For the R->P direction, the SAME build_trial_level_dataset/translated_template_nuisance machinery
is reused by SWAPPING which physical array plays predictor vs outcome role (R as predictor, P as
outcome) and swapping the corresponding p_center/p_sigma <-> r_center/r_sigma identity into
translated_template_nuisance -- no new estimator code, since the "own_history/lag_features/
response_window" window logic is agnostic to which physical channel it's applied to; only the
analytic nuisance-template formula needs to know which channel's own shared-kernel identity
(center, sigma) belongs to which role.

Reports, per condition (no coupling / P->R only / R->P only / bidirectional):
  Delta_P_to_R, Delta_R_to_P, A = Delta_P_to_R - Delta_R_to_P
Per Hamm: do NOT require the "wrong-direction" Delta to be exactly zero (own-history/private
autocorrelation can leak some information both ways); the calibrated asymmetry statistic A is
the defensible directional criterion, not a bare significance flag on one model.

Run with: python -m omission.scripts.dev_reverse_direction_20260828
"""
import json
from pathlib import Path

import numpy as np

from omission.jnwb_ext.realized_coupling_generator import (
    synthesize_bidirectional_coupling_pair, calibrate_matched_beta_r_to_p,
)
from omission.jnwb_ext.distributed_lag_model import build_trial_level_dataset, translated_template_nuisance, fit_translated_template_oracle

N_TRIALS = 300
SEEDS = list(range(10))
RHO = 0.5
TARGET_BETA_P_TO_R = 1.5
DELAY_MS = 30.0
P_CENTER, P_SIGMA, R_CENTER, R_SIGMA = 150.0, 25.0, 220.0, 5.0
JITTER_SD = 8.0

calib = calibrate_matched_beta_r_to_p(
    TARGET_BETA_P_TO_R, coupling_kind="realized", p_center=P_CENTER, p_sigma=P_SIGMA,
    r_center=R_CENTER, r_sigma=R_SIGMA, rho=RHO, trial_len=400,
)
BETA_R_TO_P = calib["calibrated_beta_r_to_p"]
print("=== Energy calibration ===")
print(json.dumps(calib, indent=2))
print(f"relative_mismatch = {calib['relative_mismatch']:.4f} (target: small)")

CONDITIONS = {
    "no_coupling":   dict(beta_p_to_r=0.0, beta_r_to_p=0.0),
    "P_to_R_only":   dict(beta_p_to_r=TARGET_BETA_P_TO_R, beta_r_to_p=0.0),
    "R_to_P_only":   dict(beta_p_to_r=0.0, beta_r_to_p=BETA_R_TO_P),
    "bidirectional": dict(beta_p_to_r=TARGET_BETA_P_TO_R, beta_r_to_p=BETA_R_TO_P),
}

results = {"calibration": calib, "conditions": {}}

print("\n=== Reverse-direction / directional-asymmetry battery ===")
for name, betas in CONDITIONS.items():
    delta_p2r, delta_r2p = [], []
    for seed in SEEDS:
        P, R, true_jitter, true_gain, P_private, R_private = synthesize_bidirectional_coupling_pair(
            n_trials=N_TRIALS, trial_len=400, jitter_sd_ms=JITTER_SD, amp_gain=0.0, rho=RHO,
            delay_ms=DELAY_MS, coupling_kind="realized",
            p_center=P_CENTER, p_sigma=P_SIGMA, r_center=R_CENTER, r_sigma=R_SIGMA,
            z_seed=seed, private_seed=seed + 800000, **betas,
        )

        # forward: predict future R from past P (standard orientation)
        ds_fwd = build_trial_level_dataset(P, R, seed=seed)
        ht_fwd, lt_fwd = translated_template_nuisance(true_jitter, true_gain, p_center=P_CENTER, p_sigma=P_SIGMA, r_center=R_CENTER, r_sigma=R_SIGMA)
        fit_fwd = fit_translated_template_oracle(ds_fwd, ht_fwd, lt_fwd, seed=seed)
        delta_p2r.append(fit_fwd["delta"])

        # reverse: predict future P from past R (swapped arguments + swapped nuisance identity)
        ds_rev = build_trial_level_dataset(R, P, seed=seed)
        ht_rev, lt_rev = translated_template_nuisance(true_jitter, true_gain, p_center=R_CENTER, p_sigma=R_SIGMA, r_center=P_CENTER, r_sigma=P_SIGMA)
        fit_rev = fit_translated_template_oracle(ds_rev, ht_rev, lt_rev, seed=seed)
        delta_r2p.append(fit_rev["delta"])

    dp = np.array(delta_p2r)
    dr = np.array(delta_r2p)
    A_per_seed = dp - dr
    results["conditions"][name] = {
        "delta_p_to_r_mean": float(dp.mean()), "delta_p_to_r_sd": float(dp.std(ddof=1)),
        "delta_r_to_p_mean": float(dr.mean()), "delta_r_to_p_sd": float(dr.std(ddof=1)),
        "A_mean": float(A_per_seed.mean()), "A_sd": float(A_per_seed.std(ddof=1)),
    }
    print(f"  {name:15s} Delta_P->R={dp.mean():+.4f}+-{dp.std(ddof=1):.4f}   "
          f"Delta_R->P={dr.mean():+.4f}+-{dr.std(ddof=1):.4f}   A={A_per_seed.mean():+.4f}+-{A_per_seed.std(ddof=1):.4f}")

out_path = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "reverse-direction-asymmetry-20260828.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps({
    "schema_version": 3,
    "id": "reverse-direction-asymmetry-20260828",
    "kind": "evidence",
    "title": "Reverse-direction generator + directional-asymmetry statistic A = Delta_P->R - Delta_R->P",
    "status": "provisional",
    "n_trials": N_TRIALS, "n_seeds": len(SEEDS), "rho": RHO, "target_beta_p_to_r": TARGET_BETA_P_TO_R,
    "beta_r_to_p_calibrated": BETA_R_TO_P, "delay_ms": DELAY_MS,
    "results": results,
}, indent=2))
print(f"\nWrote {out_path}")
