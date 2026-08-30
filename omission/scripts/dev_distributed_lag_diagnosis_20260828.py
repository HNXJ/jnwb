# SUPERSEDED (2026-08-30): this script belongs to the causal-identification investigation,
# CONFIRMED closed by causal-identification-branch-seal-20260828.json. Its numerical findings
# are preserved in that seal and in omission/artifacts/.lab/. Kept for provenance and because
# other scripts in this directory still import it; do not extend or rerun it for new analysis.
"""Diagnose the distributed-lag M3_bad regression-test failure (2026-08-28): M2 (own-history +
timing/amplitude proxy Z) reduces but does not zero out negative-control Delta_LFP. Per Hamm's
instruction, do NOT rebuild Z yet -- first determine WHERE the residual confound signal lives:
in M2's held-out residuals (item 1), in the lag features vs. Z as latent-nuisance predictors
(item 2), and whether an ORACLE Z (ground-truth true_jitter/true_gain, available only in
synthetic data) fixes the problem (item 3, decisive) -- then, only if oracle succeeds, a
proxy-noise interpolation curve (item 4).

Run with: python -m omission.scripts.dev_distributed_lag_diagnosis_20260828
"""
import json
from pathlib import Path
from scipy import stats

import numpy as np

from omission.jnwb_ext.common_driver_control import synthesize_general_adversarial_pair
from omission.jnwb_ext.distributed_lag_model import (
    build_trial_level_dataset, fit_nested_models, held_out_residuals_M2,
    predict_latent_from_features, fit_oracle_nested_models, fit_noisy_oracle_nested_models,
)

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
PROXY_NOISE_SWEEP_JITTER = [0.0, 1.0, 2.4, 5.0, 8.0, 15.0]  # ms; 2.4 ~= empirical matched-filter SD
PROXY_NOISE_SWEEP_GAIN = [0.0, 0.1, 0.25, 0.5, 1.0]

results = {"per_scenario": {}, "oracle_summary": {}, "proxy_noise_sweep": {}}

for name, params in SCENARIOS.items():
    residual_vs_jitter_pearson, residual_vs_jitter_spearman = [], []
    residual_vs_gain_pearson, residual_vs_gain_spearman = [], []
    residual_from_latents_r2 = []
    jitter_from_lag_r2, jitter_from_Z_r2 = [], []
    gain_from_lag_r2, gain_from_Z_r2 = [], []
    oracle_deltas, oracle_r2_M2, oracle_r2_M3 = [], [], []
    current_deltas = []

    for seed in SEEDS:
        P, R, true_jitter, true_gain = synthesize_general_adversarial_pair(
            n_trials=N_TRIALS, seed=seed, **params
        )
        dataset = build_trial_level_dataset(P, R, seed=seed)

        # item 0: current-Z Delta_LFP for reference alongside this diagnostic run
        current_fit = fit_nested_models(dataset, seed=seed)
        current_deltas.append(current_fit["delta_lfp"])

        # item 1: residual vs ground truth
        e_M2 = held_out_residuals_M2(dataset, seed=seed)
        if np.std(true_jitter) > 0:
            r, _ = stats.pearsonr(e_M2, true_jitter)
            rs, _ = stats.spearmanr(e_M2, true_jitter)
            residual_vs_jitter_pearson.append(r)
            residual_vs_jitter_spearman.append(rs)
        if np.std(true_gain) > 0:
            r, _ = stats.pearsonr(e_M2, true_gain)
            rs, _ = stats.spearmanr(e_M2, true_gain)
            residual_vs_gain_pearson.append(r)
            residual_vs_gain_spearman.append(rs)
        latents = np.stack([true_jitter, true_gain], axis=1)
        if np.std(true_jitter) > 0 or np.std(true_gain) > 0:
            res_pred = predict_latent_from_features(latents, e_M2, seed=seed)
            residual_from_latents_r2.append(res_pred["held_out_r2"])

        # item 2: latent predictability from lag features vs. from current Z
        Z_current = np.stack([dataset["timing"], dataset["amplitude"]], axis=1)
        if np.std(true_jitter) > 0:
            jitter_from_lag_r2.append(predict_latent_from_features(dataset["lag_features"], true_jitter, seed=seed)["held_out_r2"])
            jitter_from_Z_r2.append(predict_latent_from_features(Z_current, true_jitter, seed=seed)["held_out_r2"])
        if np.std(true_gain) > 0:
            gain_from_lag_r2.append(predict_latent_from_features(dataset["lag_features"], true_gain, seed=seed)["held_out_r2"])
            gain_from_Z_r2.append(predict_latent_from_features(Z_current, true_gain, seed=seed)["held_out_r2"])

        # item 3: oracle conditioning
        oracle_fit = fit_oracle_nested_models(dataset, true_jitter, true_gain, seed=seed)
        oracle_deltas.append(oracle_fit["delta_oracle"])
        oracle_r2_M2.append(oracle_fit["r2_M2_oracle"])
        oracle_r2_M3.append(oracle_fit["r2_M3_oracle"])

    def _summ(x):
        x = np.array(x, dtype=float)
        x = x[~np.isnan(x)]
        if len(x) == 0:
            return {"mean": None, "sd": None, "n": 0}
        return {"mean": float(x.mean()), "sd": float(x.std(ddof=1)) if len(x) > 1 else 0.0, "n": int(len(x))}

    results["per_scenario"][name] = {
        "current_delta_lfp": _summ(current_deltas),
        "residual_vs_true_jitter_pearson": _summ(residual_vs_jitter_pearson),
        "residual_vs_true_jitter_spearman": _summ(residual_vs_jitter_spearman),
        "residual_vs_true_gain_pearson": _summ(residual_vs_gain_pearson),
        "residual_vs_true_gain_spearman": _summ(residual_vs_gain_spearman),
        "residual_predicted_from_latents_r2": _summ(residual_from_latents_r2),
        "true_jitter_from_lag_features_r2": _summ(jitter_from_lag_r2),
        "true_jitter_from_current_Z_r2": _summ(jitter_from_Z_r2),
        "true_gain_from_lag_features_r2": _summ(gain_from_lag_r2),
        "true_gain_from_current_Z_r2": _summ(gain_from_Z_r2),
        "oracle_delta": _summ(oracle_deltas),
        "oracle_r2_M2": _summ(oracle_r2_M2),
        "oracle_r2_M3": _summ(oracle_r2_M3),
    }

    print(f"\n=== {name} ===")
    print(f"  current Delta_LFP        : {results['per_scenario'][name]['current_delta_lfp']}")
    print(f"  oracle  Delta_LFP        : {results['per_scenario'][name]['oracle_delta']}")
    print(f"  e_M2 vs true_jitter (r)  : {results['per_scenario'][name]['residual_vs_true_jitter_pearson']}")
    print(f"  e_M2 vs true_gain (r)    : {results['per_scenario'][name]['residual_vs_true_gain_pearson']}")
    print(f"  e_M2 <- [jitter,gain] R2 : {results['per_scenario'][name]['residual_predicted_from_latents_r2']}")
    print(f"  true_jitter <- lag R2   vs  <- Z R2 : "
          f"{results['per_scenario'][name]['true_jitter_from_lag_features_r2']['mean']}  vs  "
          f"{results['per_scenario'][name]['true_jitter_from_current_Z_r2']['mean']}")
    print(f"  true_gain   <- lag R2   vs  <- Z R2 : "
          f"{results['per_scenario'][name]['true_gain_from_lag_features_r2']['mean']}  vs  "
          f"{results['per_scenario'][name]['true_gain_from_current_Z_r2']['mean']}")

# Decision point (item 3): does oracle conditioning fix negative controls?
neg_ctrl_names = ["timing_only", "amplitude_only", "combined"]
oracle_neg_means = [results["per_scenario"][n]["oracle_delta"]["mean"] for n in neg_ctrl_names]
oracle_pos_mean = results["per_scenario"]["positive_control_timing_confound_plus_coupling"]["oracle_delta"]["mean"]
oracle_fixes_it = all(abs(m) < 0.03 for m in oracle_neg_means) and oracle_pos_mean > 0.05
results["oracle_summary"] = {
    "oracle_delta_negative_controls": dict(zip(neg_ctrl_names, oracle_neg_means)),
    "oracle_delta_positive_control": oracle_pos_mean,
    "oracle_conditioning_fixes_negative_controls": oracle_fixes_it,
}
print(f"\n>>> ORACLE CONDITIONING FIXES NEGATIVE CONTROLS: {oracle_fixes_it}")
print(f"    negative-control oracle deltas: {dict(zip(neg_ctrl_names, [round(m,4) for m in oracle_neg_means]))}")
print(f"    positive-control oracle delta : {round(oracle_pos_mean,4)}")

# item 4: proxy-noise interpolation, only meaningful (and only run) if oracle succeeded
if oracle_fixes_it:
    print("\n=== Item 4: proxy-noise interpolation (timing_only scenario, jitter noise sweep) ===")
    sweep_jitter = []
    for noise_sd in PROXY_NOISE_SWEEP_JITTER:
        deltas = []
        for seed in SEEDS:
            P, R, true_jitter, true_gain = synthesize_general_adversarial_pair(
                n_trials=N_TRIALS, seed=seed, **SCENARIOS["timing_only"]
            )
            dataset = build_trial_level_dataset(P, R, seed=seed)
            fit = fit_noisy_oracle_nested_models(dataset, true_jitter, true_gain,
                                                  proxy_noise_sd_jitter=noise_sd, seed=seed)
            deltas.append(fit["delta_oracle"])
        deltas = np.array(deltas)
        sweep_jitter.append({"proxy_noise_sd_ms": noise_sd, "delta_mean": float(deltas.mean()),
                              "delta_sd": float(deltas.std(ddof=1))})
        print(f"  jitter proxy noise SD={noise_sd:5.1f}ms -> Delta_oracle={deltas.mean():+.4f}+-{deltas.std(ddof=1):.4f}")

    print("\n=== Item 4: proxy-noise interpolation (amplitude_only scenario, gain noise sweep) ===")
    sweep_gain = []
    for noise_sd in PROXY_NOISE_SWEEP_GAIN:
        deltas = []
        for seed in SEEDS:
            P, R, true_jitter, true_gain = synthesize_general_adversarial_pair(
                n_trials=N_TRIALS, seed=seed, **SCENARIOS["amplitude_only"]
            )
            dataset = build_trial_level_dataset(P, R, seed=seed)
            fit = fit_noisy_oracle_nested_models(dataset, true_jitter, true_gain,
                                                  proxy_noise_sd_gain=noise_sd, seed=seed)
            deltas.append(fit["delta_oracle"])
        deltas = np.array(deltas)
        sweep_gain.append({"proxy_noise_sd_gain": noise_sd, "delta_mean": float(deltas.mean()),
                            "delta_sd": float(deltas.std(ddof=1))})
        print(f"  gain proxy noise SD={noise_sd:5.2f} -> Delta_oracle={deltas.mean():+.4f}+-{deltas.std(ddof=1):.4f}")

    results["proxy_noise_sweep"] = {"jitter_sweep_timing_only": sweep_jitter, "gain_sweep_amplitude_only": sweep_gain}
else:
    print("\n>>> Oracle conditioning did NOT fix negative controls -- skipping item 4 (proxy-noise "
          "interpolation is only informative if the architecture is otherwise sound). Per Hamm's "
          "instruction: stop treating nuisance-proxy fidelity as the explanation; inspect the "
          "estimator/generator/leakage/overlap instead.")
    results["proxy_noise_sweep"] = "skipped_oracle_did_not_fix"

out_path = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "distributed-lag-oracle-diagnosis-20260828.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps({
    "schema_version": 3,
    "id": "distributed-lag-oracle-diagnosis-20260828",
    "kind": "evidence",
    "title": "Oracle/residual diagnosis of M3_bad regression-test failure in distributed-lag model",
    "status": "provisional",
    "n_trials": N_TRIALS,
    "n_seeds": len(SEEDS),
    "results": results,
}, indent=2))
print(f"\nWrote {out_path}")
