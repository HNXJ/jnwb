# SUPERSEDED (2026-08-30): this script belongs to the causal-identification investigation,
# CONFIRMED closed by causal-identification-branch-seal-20260828.json. Its numerical findings
# are preserved in that seal and in omission/artifacts/.lab/. Kept for provenance and because
# other scripts in this directory still import it; do not extend or rerun it for new analysis.
"""Decisive oracle rerun (2026-08-28) against the REPAIRED, structurally valid PC1 (innovation-
coupling) generator (realized_coupling_generator.synthesize_realized_coupling_pair), after the
prior positive control was found degenerate (coupling was a deterministic function of e_i alone,
observationally identical to the confound -- see distributed-lag-structured-timing-20260828.json).

Tests, per scenario (timing/gain/combined null and +true PC1 coupling):
  - translated-template oracle (M2 = own_history + analytic E[shared P/R | e_i, a_i];
    M3 = M2 + REAL observed lag features) -- the strongest nuisance-removal method carried over
    from the (correctly) degenerate-generator diagnosis, re-tested here.
  - linear oracle (M2 = own_history + true_jitter + true_gain) for comparison.

Required outcome for the architecture to be viable: null scenarios Delta~=0, coupling scenarios
Delta>0, i.e. D = Delta_positive - Delta_negative clearly positive.

Run with: python -m omission.scripts.dev_realized_coupling_oracle_rerun_20260828
"""
import json
from pathlib import Path

import numpy as np

from omission.jnwb_ext.realized_coupling_generator import synthesize_realized_coupling_pair
from omission.jnwb_ext.distributed_lag_model import (
    build_trial_level_dataset, translated_template_nuisance, fit_translated_template_oracle,
    fit_oracle_nested_models,
)

N_TRIALS = 300
SEEDS = list(range(10))
RHO = 0.5
BETA = 1.5
DELAY_MS = 30.0

SCENARIOS = {
    "timing_null":        dict(jitter_sd_ms=8.0, amp_gain=0.0, beta=0.0),
    "gain_null":          dict(jitter_sd_ms=0.0, amp_gain=0.6, beta=0.0),
    "combined_null":      dict(jitter_sd_ms=8.0, amp_gain=0.6, beta=0.0),
    "timing_coupling":    dict(jitter_sd_ms=8.0, amp_gain=0.0, beta=BETA),
    "gain_coupling":      dict(jitter_sd_ms=0.0, amp_gain=0.6, beta=BETA),
    "combined_coupling":  dict(jitter_sd_ms=8.0, amp_gain=0.6, beta=BETA),
}

results = {}
for name, params in SCENARIOS.items():
    template_deltas, linear_deltas = [], []
    for seed in SEEDS:
        P, R, true_jitter, true_gain, P_private = synthesize_realized_coupling_pair(
            n_trials=N_TRIALS, rho=RHO, delay_ms=DELAY_MS, coupling_kind="innovation",
            z_seed=seed, private_seed=seed + 500000, **params,
        )
        dataset = build_trial_level_dataset(P, R, seed=seed)

        hist_t, lag_t = translated_template_nuisance(true_jitter, true_gain)
        template_fit = fit_translated_template_oracle(dataset, hist_t, lag_t, seed=seed)
        template_deltas.append(template_fit["delta"])

        linear_fit = fit_oracle_nested_models(dataset, true_jitter, true_gain, seed=seed)
        linear_deltas.append(linear_fit["delta_oracle"])

    t_d = np.array(template_deltas)
    l_d = np.array(linear_deltas)
    results[name] = {
        "template_delta_mean": float(t_d.mean()), "template_delta_sd": float(t_d.std(ddof=1)),
        "linear_delta_mean": float(l_d.mean()), "linear_delta_sd": float(l_d.std(ddof=1)),
    }
    print(f"{name:20s} template={t_d.mean():+.4f}+-{t_d.std(ddof=1):.4f}   linear={l_d.mean():+.4f}+-{l_d.std(ddof=1):.4f}")

# separation
for base in ["timing", "gain", "combined"]:
    D_template = results[f"{base}_coupling"]["template_delta_mean"] - results[f"{base}_null"]["template_delta_mean"]
    D_linear = results[f"{base}_coupling"]["linear_delta_mean"] - results[f"{base}_null"]["linear_delta_mean"]
    results[f"{base}_D_template"] = D_template
    results[f"{base}_D_linear"] = D_linear
    print(f"D[{base}] template={D_template:+.4f}   linear={D_linear:+.4f}")

out_path = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "realized-coupling-oracle-rerun-20260828.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps({
    "schema_version": 3,
    "id": "realized-coupling-oracle-rerun-20260828",
    "kind": "evidence",
    "title": "Oracle rerun (translated-template + linear) against repaired PC1 realized-coupling generator",
    "status": "provisional",
    "n_trials": N_TRIALS, "n_seeds": len(SEEDS), "rho": RHO, "beta": BETA, "delay_ms": DELAY_MS,
    "results": results,
}, indent=2))
print(f"\nWrote {out_path}")
