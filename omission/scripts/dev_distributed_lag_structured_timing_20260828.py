# SUPERSEDED (2026-08-30): this script belongs to the causal-identification investigation,
# CONFIRMED closed by causal-identification-branch-seal-20260828.json. Its numerical findings
# are preserved in that seal and in omission/artifacts/.lab/. Kept for provenance and because
# other scripts in this directory still import it; do not extend or rerun it for new analysis.
"""Structured nonlinear conditioning of the timing nuisance (2026-08-28, Hamm). Prior diagnosis
established: gain confound is a PROXY-FIDELITY problem (linear oracle conditioning fixes it,
Delta_oracle~=0); timing confound is a MODEL-SPECIFICATION problem (linear oracle conditioning
leaves Delta_oracle~=+0.233, and a nonlinear model recovers ~55-60% of the held-out residual
variance from the SAME latents already linearly conditioned on).

This script (a) verifies the nonlinear feature-vs-jitter geometry directly (item 2), (b) tests
progressively richer timing-nuisance representations -- linear/quadratic/cubic/spline -- against
both a negative control (timing_only) and a positive control (item 3), and (c) tests the
strongest possible oracle: an analytically exact translated-template nuisance built from the
known generator kernel formula (item 4). Then repeats the winning representation on
amplitude-only, combined, and combined+true-coupling (item 8).

Run with: python -m omission.scripts.dev_distributed_lag_structured_timing_20260828
"""
import json
from pathlib import Path

import numpy as np

from omission.jnwb_ext.common_driver_control import synthesize_general_adversarial_pair
from omission.jnwb_ext.distributed_lag_model import (
    build_trial_level_dataset, feature_vs_jitter_nonlinearity, fit_structured_timing_oracle,
    fit_structured_timing_oracle_spline, translated_template_nuisance, fit_translated_template_oracle,
    _poly_expand,
)

N_TRIALS = 300
SEEDS = list(range(10))
TIMING_ONLY = dict(jitter_sd_ms=8.0, amp_gain=0.0, coupling_strength=0.0)
POSITIVE = dict(jitter_sd_ms=8.0, amp_gain=0.0, coupling_strength=0.6, coupling_lag_ms=30.0)
AMPLITUDE_ONLY = dict(jitter_sd_ms=0.0, amp_gain=0.6, coupling_strength=0.0)
COMBINED = dict(jitter_sd_ms=8.0, amp_gain=0.6, coupling_strength=0.0)
COMBINED_POS = dict(jitter_sd_ms=8.0, amp_gain=0.6, coupling_strength=0.6, coupling_lag_ms=30.0)

results = {}

# ---------------------------------------------------------------------------------------------
# Item 2: feature-vs-jitter nonlinear geometry (timing_only scenario, isolates jitter)
# ---------------------------------------------------------------------------------------------
print("=== Item 2: per-feature nonlinearity vs true_jitter (timing_only) ===")
feature_geometry = {"outcome": [], "own_history": [], "lag_bin_0": [], "lag_bin_1": [], "lag_bin_2": [], "lag_bin_3": []}
for seed in SEEDS:
    P, R, true_jitter, true_gain = synthesize_general_adversarial_pair(n_trials=N_TRIALS, seed=seed, **TIMING_ONLY)
    dataset = build_trial_level_dataset(P, R, seed=seed)
    feature_geometry["outcome"].append(feature_vs_jitter_nonlinearity(dataset["outcome"], true_jitter, seed=seed))
    feature_geometry["own_history"].append(feature_vs_jitter_nonlinearity(dataset["own_history"], true_jitter, seed=seed))
    for k in range(4):
        feature_geometry[f"lag_bin_{k}"].append(feature_vs_jitter_nonlinearity(dataset["lag_features"][:, k], true_jitter, seed=seed))

geometry_summary = {}
for fname, runs in feature_geometry.items():
    geometry_summary[fname] = {
        kind: {"mean": float(np.mean([r[kind] for r in runs])), "sd": float(np.std([r[kind] for r in runs], ddof=1))}
        for kind in ["linear", "quadratic", "cubic", "spline"]
    }
    print(f"  {fname:12s} linear={geometry_summary[fname]['linear']['mean']:+.3f}  "
          f"quad={geometry_summary[fname]['quadratic']['mean']:+.3f}  "
          f"cubic={geometry_summary[fname]['cubic']['mean']:+.3f}  "
          f"spline={geometry_summary[fname]['spline']['mean']:+.3f}")
results["item2_feature_geometry"] = geometry_summary

# ---------------------------------------------------------------------------------------------
# Item 3: structured timing-nuisance representations, negative + positive control
# ---------------------------------------------------------------------------------------------
print("\n=== Item 3: structured timing oracle conditioning ===")


def _run_representation(rep_name, build_Z_fn, scenario_params, gain_present=False):
    deltas = []
    for seed in SEEDS:
        P, R, true_jitter, true_gain = synthesize_general_adversarial_pair(n_trials=N_TRIALS, seed=seed, **scenario_params)
        dataset = build_trial_level_dataset(P, R, seed=seed)
        gain_Z = true_gain if gain_present else None
        fit = build_Z_fn(dataset, true_jitter, gain_Z, seed)
        deltas.append(fit["delta"])
    d = np.array(deltas)
    return {"mean": float(d.mean()), "sd": float(d.std(ddof=1)), "n": len(d)}


def _linear(dataset, tj, gz, seed):
    return fit_structured_timing_oracle(dataset, tj.reshape(-1, 1), gain_Z=gz, seed=seed)


def _quadratic(dataset, tj, gz, seed):
    return fit_structured_timing_oracle(dataset, _poly_expand(tj, 2), gain_Z=gz, seed=seed)


def _cubic(dataset, tj, gz, seed):
    return fit_structured_timing_oracle(dataset, _poly_expand(tj, 3), gain_Z=gz, seed=seed)


def _spline(dataset, tj, gz, seed):
    return fit_structured_timing_oracle_spline(dataset, tj, gain_Z=gz, seed=seed)


REPRESENTATIONS = {"linear": _linear, "quadratic": _quadratic, "cubic": _cubic, "spline": _spline}

table = {}
for rep_name, fn in REPRESENTATIONS.items():
    neg = _run_representation(rep_name, fn, TIMING_ONLY)
    pos = _run_representation(rep_name, fn, POSITIVE)
    D = pos["mean"] - neg["mean"]
    table[rep_name] = {"timing_null_delta": neg, "true_coupling_delta": pos, "D": D}
    print(f"  {rep_name:10s} null={neg['mean']:+.4f}+-{neg['sd']:.4f}  "
          f"coupling={pos['mean']:+.4f}+-{pos['sd']:.4f}  D={D:+.4f}")

# ---------------------------------------------------------------------------------------------
# Item 4: translated-template oracle (analytically exact null-hypothesis feature shape)
# ---------------------------------------------------------------------------------------------
print("\n=== Item 4: translated-template oracle ===")


def _run_template(scenario_params):
    deltas = []
    for seed in SEEDS:
        P, R, true_jitter, true_gain = synthesize_general_adversarial_pair(n_trials=N_TRIALS, seed=seed, **scenario_params)
        dataset = build_trial_level_dataset(P, R, seed=seed)
        hist_t, lag_t = translated_template_nuisance(true_jitter, true_gain)
        fit = fit_translated_template_oracle(dataset, hist_t, lag_t, seed=seed)
        deltas.append(fit["delta"])
    d = np.array(deltas)
    return {"mean": float(d.mean()), "sd": float(d.std(ddof=1)), "n": len(d)}


template_neg = _run_template(TIMING_ONLY)
template_pos = _run_template(POSITIVE)
D_template = template_pos["mean"] - template_neg["mean"]
table["translated_template_oracle"] = {"timing_null_delta": template_neg, "true_coupling_delta": template_pos, "D": D_template}
print(f"  template   null={template_neg['mean']:+.4f}+-{template_neg['sd']:.4f}  "
      f"coupling={template_pos['mean']:+.4f}+-{template_pos['sd']:.4f}  D={D_template:+.4f}")

results["item3_item4_decision_table"] = table

# ---------------------------------------------------------------------------------------------
# Pick winner by D magnitude while requiring null <~ small; then repeat on remaining scenarios
# ---------------------------------------------------------------------------------------------
NULL_OK_THRESHOLD = 0.05
candidates = {k: v for k, v in table.items() if abs(v["timing_null_delta"]["mean"]) < NULL_OK_THRESHOLD}
if candidates:
    winner = max(candidates, key=lambda k: candidates[k]["D"])
else:
    winner = max(table, key=lambda k: table[k]["D"])
print(f"\n>>> WINNING REPRESENTATION: {winner} (selected by max D among null<{NULL_OK_THRESHOLD}; "
      f"fallback max D if none qualify)")
results["winner"] = winner

print(f"\n=== Item 8: repeating '{winner}' on amplitude_only / combined / combined+true_coupling ===")
extra = {}
if winner == "translated_template_oracle":
    extra["amplitude_only"] = _run_template(AMPLITUDE_ONLY)
    extra["combined"] = _run_template(COMBINED)
    extra["combined_plus_true_coupling"] = _run_template(COMBINED_POS)
else:
    fn = REPRESENTATIONS[winner]
    extra["amplitude_only"] = _run_representation(winner, fn, AMPLITUDE_ONLY, gain_present=True)
    extra["combined"] = _run_representation(winner, fn, COMBINED, gain_present=True)
    extra["combined_plus_true_coupling"] = _run_representation(winner, fn, COMBINED_POS, gain_present=True)
for k, v in extra.items():
    print(f"  {k:30s} delta={v['mean']:+.4f}+-{v['sd']:.4f}")
results["item8_extended_scenarios"] = extra

out_path = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "distributed-lag-structured-timing-20260828.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps({
    "schema_version": 3,
    "id": "distributed-lag-structured-timing-20260828",
    "kind": "evidence",
    "title": "Structured nonlinear timing-nuisance conditioning: poly/spline/translated-template oracle",
    "status": "provisional",
    "n_trials": N_TRIALS,
    "n_seeds": len(SEEDS),
    "results": results,
}, indent=2))
print(f"\nWrote {out_path}")
