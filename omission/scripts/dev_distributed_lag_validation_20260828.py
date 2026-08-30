# SUPERSEDED (2026-08-30): this script belongs to the causal-identification investigation,
# CONFIRMED closed by causal-identification-branch-seal-20260828.json. Its numerical findings
# are preserved in that seal and in omission/artifacts/.lab/. Kept for provenance and because
# other scripts in this directory still import it; do not extend or rerun it for new analysis.
"""Validate the distributed-lag nested-model machinery (M0-M3/M3_bad) against the adversarial
generator's negative controls and one positive control. Primary sanity check: M3_bad should show
spurious Delta_LFP_bad on confounded negative-control data; properly-conditioned M3 should show
Delta_LFP ~ 0. Run with: python -m omission.scripts.dev_distributed_lag_validation_20260828
"""
import json
from pathlib import Path

import numpy as np

from omission.jnwb_ext.common_driver_control import synthesize_general_adversarial_pair
from omission.jnwb_ext.distributed_lag_model import build_trial_level_dataset, fit_nested_models

SCENARIOS = {
    "timing_only": dict(jitter_sd_ms=8.0, amp_gain=0.0, coupling_strength=0.0),
    "amplitude_only": dict(jitter_sd_ms=0.0, amp_gain=0.6, coupling_strength=0.0),
    "combined": dict(jitter_sd_ms=8.0, amp_gain=0.6, coupling_strength=0.0),
    "positive_control_timing_confound_plus_coupling": dict(
        jitter_sd_ms=8.0, amp_gain=0.0, coupling_strength=0.6, coupling_lag_ms=30.0,
    ),
}

N_TRIALS = 300
SEEDS = list(range(10))
results = {}

for name, params in SCENARIOS.items():
    seed_results = []
    for seed in SEEDS:
        P, R, true_jitter, true_gain = synthesize_general_adversarial_pair(
            n_trials=N_TRIALS, seed=seed, **params
        )
        dataset = build_trial_level_dataset(P, R, seed=seed)
        fit = fit_nested_models(dataset, seed=seed)
        seed_results.append(fit)

    delta_lfp = np.array([r["delta_lfp"] for r in seed_results])
    delta_lfp_bad = np.array([r["delta_lfp_bad"] for r in seed_results])
    results[name] = {
        "n_trials": N_TRIALS,
        "n_seeds": len(SEEDS),
        "delta_lfp_mean": float(delta_lfp.mean()),
        "delta_lfp_sd": float(delta_lfp.std(ddof=1)),
        "delta_lfp_values": delta_lfp.tolist(),
        "delta_lfp_bad_mean": float(delta_lfp_bad.mean()),
        "delta_lfp_bad_sd": float(delta_lfp_bad.std(ddof=1)),
        "delta_lfp_bad_values": delta_lfp_bad.tolist(),
        "r2_M2_mean": float(np.mean([r["r2"]["M2"] for r in seed_results])),
        "r2_M3_mean": float(np.mean([r["r2"]["M3"] for r in seed_results])),
        "r2_M1_mean": float(np.mean([r["r2"]["M1"] for r in seed_results])),
        "r2_M3_bad_mean": float(np.mean([r["r2"]["M3_bad"] for r in seed_results])),
    }
    print(f"{name:55s} DeltaLFP={results[name]['delta_lfp_mean']:+.4f}+-{results[name]['delta_lfp_sd']:.4f}"
          f"  DeltaLFP_bad={results[name]['delta_lfp_bad_mean']:+.4f}+-{results[name]['delta_lfp_bad_sd']:.4f}")

out_path = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "distributed-lag-model-validation-20260828.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps({
    "schema_version": 3,
    "id": "distributed-lag-model-validation-20260828",
    "kind": "evidence",
    "title": "Distributed-lag nested model (M0-M3/M3_bad) validation on adversarial generator",
    "status": "provisional",
    "results": results,
}, indent=2))
print(f"\nWrote {out_path}")
