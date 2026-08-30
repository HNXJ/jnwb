# SUPERSEDED (2026-08-30): this script belongs to the causal-identification investigation,
# CONFIRMED closed by causal-identification-branch-seal-20260828.json. Its numerical findings
# are preserved in that seal and in omission/artifacts/.lab/. Kept for provenance and because
# other scripts in this directory still import it; do not extend or rerun it for new analysis.
"""Follow-up to dev_distributed_lag_diagnosis_20260828: the oracle-conditioning test showed
linear conditioning on true_jitter FAILS to zero out negative-control Delta_LFP on the timing
confound (Delta_oracle=+0.233), while linear conditioning on true_gain SUCCEEDS (Delta_oracle~=0).
Hypothesis: the timing confound's effect on windowed-mean features is nonlinear in e_i (a kernel
shift), so linear regression on the exact e_i still can't null it out. Test directly: can a
NONLINEAR model recover, from true_jitter/true_gain alone, the residual that linear oracle-M2
left behind? If yes, the leftover is nonlinear-in-latents (supports the shift-nonlinearity
mechanism). If no, the leftover residual carries no simple nonlinear latent signature either,
which would point elsewhere (leakage/overlap/target construction).

Run with: python -m omission.scripts.dev_distributed_lag_nonlinearity_check_20260828
"""
import json
from pathlib import Path

import numpy as np

from omission.jnwb_ext.common_driver_control import synthesize_general_adversarial_pair
from omission.jnwb_ext.distributed_lag_model import (
    build_trial_level_dataset, held_out_residuals_M2_oracle, nonlinear_predict_r2,
    predict_latent_from_features,
)

SCENARIOS = {
    "timing_only": dict(jitter_sd_ms=8.0, amp_gain=0.0, coupling_strength=0.0),
    "combined": dict(jitter_sd_ms=8.0, amp_gain=0.6, coupling_strength=0.0),
}
N_TRIALS = 300
SEEDS = list(range(10))
results = {}

for name, params in SCENARIOS.items():
    linear_r2s, nonlinear_r2s = [], []
    for seed in SEEDS:
        P, R, true_jitter, true_gain = synthesize_general_adversarial_pair(n_trials=N_TRIALS, seed=seed, **params)
        dataset = build_trial_level_dataset(P, R, seed=seed)
        e_oracle = held_out_residuals_M2_oracle(dataset, true_jitter, true_gain, seed=seed)
        latents = np.stack([true_jitter, true_gain], axis=1)
        linear_r2s.append(predict_latent_from_features(latents, e_oracle, seed=seed)["held_out_r2"])
        nonlinear_r2s.append(nonlinear_predict_r2(latents, e_oracle, seed=seed))
    lin = np.array(linear_r2s)
    nl = np.array(nonlinear_r2s)
    results[name] = {
        "e_M2_oracle_from_latents_linear_r2_mean": float(lin.mean()),
        "e_M2_oracle_from_latents_linear_r2_sd": float(lin.std(ddof=1)),
        "e_M2_oracle_from_latents_nonlinear_r2_mean": float(nl.mean()),
        "e_M2_oracle_from_latents_nonlinear_r2_sd": float(nl.std(ddof=1)),
        "nonlinear_minus_linear_r2_mean": float((nl - lin).mean()),
    }
    print(f"{name:15s} linear R2={lin.mean():+.4f}+-{lin.std(ddof=1):.4f}   "
          f"nonlinear(RF) R2={nl.mean():+.4f}+-{nl.std(ddof=1):.4f}   "
          f"gap={float((nl-lin).mean()):+.4f}")

out_path = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "distributed-lag-nonlinearity-check-20260828.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps({
    "schema_version": 3,
    "id": "distributed-lag-nonlinearity-check-20260828",
    "kind": "evidence",
    "title": "Nonlinear recoverability of oracle-M2 residuals from true_jitter/true_gain",
    "status": "provisional",
    "n_trials": N_TRIALS,
    "n_seeds": len(SEEDS),
    "results": results,
}, indent=2))
print(f"\nWrote {out_path}")
