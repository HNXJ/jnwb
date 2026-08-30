# SUPERSEDED (2026-08-30): this script belongs to the causal-identification investigation,
# CONFIRMED closed by causal-identification-branch-seal-20260828.json. Its numerical findings
# are preserved in that seal and in omission/artifacts/.lab/. Kept for provenance and because
# other scripts in this directory still import it; do not extend or rerun it for new analysis.
"""Oracle-Z -> observable-Zhat bridge benchmark (2026-08-28, Hamm).

The distributed-lag conditional predictive model (does past LFP-proxy P predictively improve
prediction of future spike-proxy R beyond common causes?) has been validated under ORACLE
nuisance knowledge (true_jitter/true_gain as covariates -- unavailable on real data). This
script measures how much identification degrades when the oracle is replaced by OBSERVABLE
proxies estimable from data alone:

    Zhat-0_design_only          : own_history alone (no nuisance covariate at all)
    Zhat-1_plus_pre_neural_state: own_history + amplitude (P's pre-event baseline, safe
                                   common-cause proxy)
    Zhat-2_plus_timing_gain     : Zhat-1 + timing_hat (matched-filter estimate from P alone,
                                   cross-fit with the SAME KFold split used for the outer M2/M3
                                   evaluation -- see estimate_timing_nested's docstring)
    oracle                      : own_history + true_jitter + true_gain (comparison-only, never
                                   real-data-usable)

9 scenarios x 4 tiers x N_SEEDS (>=15 required; see N_SEEDS below for the exact count and
justification), n_trials=300, rho=0.5, delay_ms=30.0, coupling_kind="realized" (PC2) throughout.
Scenarios 1-6 use synthesize_realized_coupling_pair (one-directional P->R generator, beta=0 for
nulls). Scenarios 7-9 use synthesize_bidirectional_coupling_pair and require BOTH directions'
Delta per tier (forward P->R, and swapped R->P via build_trial_level_dataset(R, P) +
estimate_timing_nested(R, ...)); oracle Z is symmetric (same true_jitter/true_gain both ways, no
swap needed there).

An auxiliary "bidirectional_null_reference" (beta_p_to_r=0, beta_r_to_p=0, same jitter/gain as
scenarios 7-9) is generated so the power calculation for 7-9 uses a null distribution built from
the SAME generator function and window/estimator machinery as those scenarios, rather than
reusing scenario 1's one-directional-generator null (which has a structurally different R: the
one-directional generator's R carries no private-innovation term at all, while the bidirectional
generator's R always does, even under beta=0 -- these are not the same null distribution and
must not be conflated).

Explicit thresholds used throughout (documented once here, applied consistently):
  - FPR threshold: delta > 0.05 (ad hoc but small, fixed enum, applied identically to every
    null cell -- both the 3 named null scenarios and the bidirectional_null_reference).
  - Power threshold: delta > null_mean + 2*null_sd, i.e. "clearly separated from the matched
    null's own dispersion", using the null distribution's OWN tier-matched mean/sd (not a
    a cross-tier or cross-scenario mixture).

Nuisance-estimation fidelity (separate from downstream calibration, reported but never treated
as a calibration substitute per Hamm's instruction) is measured on timing_null (jitter varies,
gain constant -- so amplitude-vs-true_gain correlation is degenerate there and skipped) and
combined_null (both vary).

Run with: python -m omission.scripts.dev_zhat_bridge_benchmark_20260828
"""
import json
import time
from pathlib import Path

import numpy as np

from omission.jnwb_ext.realized_coupling_generator import (
    synthesize_realized_coupling_pair, synthesize_bidirectional_coupling_pair,
    calibrate_matched_beta_r_to_p,
)
from omission.jnwb_ext.distributed_lag_model import (
    build_trial_level_dataset, estimate_timing_nested, fit_nuisance_tier,
    integrated_lag_coefficients, ZHAT_TIER_DEFINITIONS,
)

T_START = time.time()

N_TRIALS = 300
RHO = 0.5
DELAY_MS = 30.0
BETA = 1.5
N_SPLITS = 5
BASELINE_AMP = 0.15  # generator default; used to rescale amplitude -> a true_gain-comparable unit
N_SEEDS = 20  # >=15-20 required per task; 20 chosen, ran within the foreground time budget (see
              # printed wall-clock time at the end) -- not reduced to 12.
SEEDS = list(range(N_SEEDS))

TIERS = list(ZHAT_TIER_DEFINITIONS.keys()) + ["oracle"]
LAG_BINS = ((130, 150), (150, 170), (170, 190), (190, 210))
TRUE_INFORMATIVE_BINS = [2, 3]  # (170,190) and (190,210), matching dev_pc2_realized_coupling_benchmark_20260828.py

FPR_THRESHOLD = 0.05
POWER_SD_MULT = 2.0

SCENARIOS_1TO6 = {
    "timing_null":   dict(jitter_sd_ms=8.0, amp_gain=0.0, beta=0.0),
    "gain_null":     dict(jitter_sd_ms=0.0, amp_gain=0.6, beta=0.0),
    "combined_null": dict(jitter_sd_ms=8.0, amp_gain=0.6, beta=0.0),
    "timing_PC2":    dict(jitter_sd_ms=8.0, amp_gain=0.0, beta=BETA),
    "gain_PC2":      dict(jitter_sd_ms=0.0, amp_gain=0.6, beta=BETA),
    "combined_PC2":  dict(jitter_sd_ms=8.0, amp_gain=0.6, beta=BETA),
}
NULL_REF_FOR_PC2 = {"timing_PC2": "timing_null", "gain_PC2": "gain_null", "combined_PC2": "combined_null"}

print("Calibrating beta_r_to_p to match beta_p_to_r=1.5 coupling energy...")
_calib = calibrate_matched_beta_r_to_p(target_beta_p_to_r=BETA, coupling_kind="realized")
BETA_R_TO_P_CALIBRATED = _calib["calibrated_beta_r_to_p"]
print(f"  calibrated_beta_r_to_p = {BETA_R_TO_P_CALIBRATED:.5f} "
      f"(relative_mismatch={_calib['relative_mismatch']:.4f})")

SCENARIOS_7TO9 = {
    "P_to_R_only":  dict(jitter_sd_ms=8.0, amp_gain=0.0, beta_p_to_r=BETA, beta_r_to_p=0.0),
    "R_to_P_only":  dict(jitter_sd_ms=8.0, amp_gain=0.0, beta_p_to_r=0.0, beta_r_to_p=BETA_R_TO_P_CALIBRATED),
    "bidirectional": dict(jitter_sd_ms=8.0, amp_gain=0.0, beta_p_to_r=BETA, beta_r_to_p=BETA_R_TO_P_CALIBRATED),
}
NULL_REF_7TO9 = dict(jitter_sd_ms=8.0, amp_gain=0.0, beta_p_to_r=0.0, beta_r_to_p=0.0)


def _empty_tier_store():
    return {tier: [] for tier in TIERS}


def _fit_all_tiers(dataset, timing_hat, true_jitter, true_gain, seed):
    out = {}
    for tier in TIERS:
        fit = fit_nuisance_tier(dataset, tier, timing_hat=timing_hat, true_jitter=true_jitter,
                                 true_gain=true_gain, n_splits=N_SPLITS, seed=seed)
        out[tier] = fit["delta"]
    return out


# ================================================================================================
# Scenarios 1-6 (one-directional generator)
# ================================================================================================
results_1to6 = {name: _empty_tier_store() for name in SCENARIOS_1TO6}
localization_1to6 = {name: {"direction_sign": [], "peak_bin": [], "coef_trace": []} for name in SCENARIOS_1TO6}

# fidelity accumulators
fidelity_pool = {
    "timing_null": {"true_jitter": [], "timing_hat": []},
    "combined_null": {"true_jitter": [], "timing_hat": [], "true_gain": [], "amplitude": []},
}

print("\n=== Scenarios 1-6 (one-directional generator) ===")
for name, params in SCENARIOS_1TO6.items():
    t0 = time.time()
    for seed in SEEDS:
        P, R, true_jitter, true_gain, P_private = synthesize_realized_coupling_pair(
            n_trials=N_TRIALS, rho=RHO, delay_ms=DELAY_MS, coupling_kind="realized",
            z_seed=seed, private_seed=seed + 700000, **params,
        )
        dataset = build_trial_level_dataset(P, R, seed=seed)
        timing_hat = estimate_timing_nested(P, n_splits=N_SPLITS, seed=seed)

        deltas = _fit_all_tiers(dataset, timing_hat, true_jitter, true_gain, seed)
        for tier in TIERS:
            results_1to6[name][tier].append(deltas[tier])

        if params["beta"] > 0:
            coefs = integrated_lag_coefficients(dataset)
            coef_list = [coefs["lag_bin_coefficients"][f"{lo}-{hi}ms"] for lo, hi in LAG_BINS]
            localization_1to6[name]["coef_trace"].append(coef_list)
            localization_1to6[name]["direction_sign"].append(1 if coefs["sign_of_integrated_mass"] == "positive" else -1)
            localization_1to6[name]["peak_bin"].append(int(np.argmax(np.abs(coef_list))))

        if name in fidelity_pool:
            fidelity_pool[name]["true_jitter"].append(true_jitter)
            fidelity_pool[name]["timing_hat"].append(timing_hat)
            if name == "combined_null":
                fidelity_pool[name]["true_gain"].append(true_gain)
                fidelity_pool[name]["amplitude"].append(dataset["amplitude"])

    dt = time.time() - t0
    means = {tier: float(np.mean(results_1to6[name][tier])) for tier in TIERS}
    print(f"  {name:15s} [{dt:5.1f}s]  " + "  ".join(f"{t.split('_')[0]}={means[t]:+.4f}" for t in TIERS))

# ================================================================================================
# Scenarios 7-9 (bidirectional generator) + null reference
# ================================================================================================
results_7to9 = {name: {"p_to_r": _empty_tier_store(), "r_to_p": _empty_tier_store()} for name in SCENARIOS_7TO9}
localization_7to9 = {name: {"fwd": {"direction_sign": [], "peak_bin": [], "coef_trace": []},
                             "swap": {"direction_sign": [], "peak_bin": [], "coef_trace": []}}
                     for name in SCENARIOS_7TO9}
null_ref_7to9 = {"p_to_r": _empty_tier_store(), "r_to_p": _empty_tier_store()}


def _fwd_swap_fit(P, R, true_jitter, true_gain, seed):
    dataset_fwd = build_trial_level_dataset(P, R, seed=seed)
    dataset_swap = build_trial_level_dataset(R, P, seed=seed)
    timing_hat_fwd = estimate_timing_nested(P, n_splits=N_SPLITS, seed=seed)
    timing_hat_swap = estimate_timing_nested(R, n_splits=N_SPLITS, seed=seed)
    deltas_fwd = _fit_all_tiers(dataset_fwd, timing_hat_fwd, true_jitter, true_gain, seed)
    deltas_swap = _fit_all_tiers(dataset_swap, timing_hat_swap, true_jitter, true_gain, seed)
    return dataset_fwd, dataset_swap, deltas_fwd, deltas_swap


print("\n=== Scenarios 7-9 (bidirectional generator) ===")
for name, params in SCENARIOS_7TO9.items():
    t0 = time.time()
    for seed in SEEDS:
        P, R, true_jitter, true_gain, P_priv, R_priv = synthesize_bidirectional_coupling_pair(
            n_trials=N_TRIALS, rho=RHO, delay_ms=DELAY_MS, coupling_kind="realized",
            z_seed=seed, private_seed=seed + 700000, **params,
        )
        dataset_fwd, dataset_swap, deltas_fwd, deltas_swap = _fwd_swap_fit(P, R, true_jitter, true_gain, seed)
        for tier in TIERS:
            results_7to9[name]["p_to_r"][tier].append(deltas_fwd[tier])
            results_7to9[name]["r_to_p"][tier].append(deltas_swap[tier])

        if params["beta_p_to_r"] > 0:
            c = integrated_lag_coefficients(dataset_fwd)
            cl = [c["lag_bin_coefficients"][f"{lo}-{hi}ms"] for lo, hi in LAG_BINS]
            localization_7to9[name]["fwd"]["coef_trace"].append(cl)
            localization_7to9[name]["fwd"]["direction_sign"].append(1 if c["sign_of_integrated_mass"] == "positive" else -1)
            localization_7to9[name]["fwd"]["peak_bin"].append(int(np.argmax(np.abs(cl))))
        if params["beta_r_to_p"] > 0:
            c = integrated_lag_coefficients(dataset_swap)
            cl = [c["lag_bin_coefficients"][f"{lo}-{hi}ms"] for lo, hi in LAG_BINS]
            localization_7to9[name]["swap"]["coef_trace"].append(cl)
            localization_7to9[name]["swap"]["direction_sign"].append(1 if c["sign_of_integrated_mass"] == "positive" else -1)
            localization_7to9[name]["swap"]["peak_bin"].append(int(np.argmax(np.abs(cl))))

    dt = time.time() - t0
    means_fwd = {tier: float(np.mean(results_7to9[name]["p_to_r"][tier])) for tier in TIERS}
    means_swap = {tier: float(np.mean(results_7to9[name]["r_to_p"][tier])) for tier in TIERS}
    print(f"  {name:15s} [{dt:5.1f}s]")
    print(f"    P->R  " + "  ".join(f"{t.split('_')[0]}={means_fwd[t]:+.4f}" for t in TIERS))
    print(f"    R->P  " + "  ".join(f"{t.split('_')[0]}={means_swap[t]:+.4f}" for t in TIERS))

print("\n=== Bidirectional null reference (beta_p_to_r=0, beta_r_to_p=0) ===")
t0 = time.time()
for seed in SEEDS:
    P, R, true_jitter, true_gain, P_priv, R_priv = synthesize_bidirectional_coupling_pair(
        n_trials=N_TRIALS, rho=RHO, delay_ms=DELAY_MS, coupling_kind="realized",
        z_seed=seed, private_seed=seed + 700000, **NULL_REF_7TO9,
    )
    _, _, deltas_fwd, deltas_swap = _fwd_swap_fit(P, R, true_jitter, true_gain, seed)
    for tier in TIERS:
        null_ref_7to9["p_to_r"][tier].append(deltas_fwd[tier])
        null_ref_7to9["r_to_p"][tier].append(deltas_swap[tier])
dt = time.time() - t0
means_fwd = {tier: float(np.mean(null_ref_7to9["p_to_r"][tier])) for tier in TIERS}
means_swap = {tier: float(np.mean(null_ref_7to9["r_to_p"][tier])) for tier in TIERS}
print(f"  [{dt:5.1f}s]")
print(f"    P->R  " + "  ".join(f"{t.split('_')[0]}={means_fwd[t]:+.4f}" for t in TIERS))
print(f"    R->P  " + "  ".join(f"{t.split('_')[0]}={means_swap[t]:+.4f}" for t in TIERS))


# ================================================================================================
# Assemble per-(scenario,tier) table: means/sds, FPR (nulls), power (positive controls)
# ================================================================================================

def _fpr(deltas):
    d = np.asarray(deltas)
    return float(np.mean((d > 0) & (d > FPR_THRESHOLD)))


def _power(pc_deltas, null_deltas):
    null = np.asarray(null_deltas)
    threshold = float(null.mean() + POWER_SD_MULT * null.std(ddof=1))
    pc = np.asarray(pc_deltas)
    return float(np.mean(pc > threshold)), threshold


table = {}

for name in SCENARIOS_1TO6:
    is_null = SCENARIOS_1TO6[name]["beta"] == 0.0
    table[name] = {}
    for tier in TIERS:
        d = np.asarray(results_1to6[name][tier])
        cell = {"delta_mean": float(d.mean()), "delta_sd": float(d.std(ddof=1)), "n_seeds": len(d)}
        if is_null:
            cell["empirical_fpr"] = _fpr(d)
            cell["fpr_threshold_used"] = FPR_THRESHOLD
        else:
            null_name = NULL_REF_FOR_PC2[name]
            null_d = results_1to6[null_name][tier]
            power, thr = _power(d, null_d)
            cell["power"] = power
            cell["power_threshold_used"] = thr
            cell["power_reference_null_scenario"] = null_name
        table[name][tier] = cell
    if not is_null:
        loc = localization_1to6[name]
        signs = np.array(loc["direction_sign"])
        peaks = np.array(loc["peak_bin"])
        coef_trace = np.array(loc["coef_trace"])
        table[name]["localization"] = {
            "direction_recovery_fraction": float(np.mean(signs > 0)),
            "exact_interval_recovery_fraction": float(np.mean(np.isin(peaks, TRUE_INFORMATIVE_BINS))),
            "near_interval_recovery_fraction": float(np.mean(
                np.abs(peaks[:, None] - np.array(TRUE_INFORMATIVE_BINS)[None, :]).min(axis=1) <= 1)),
            "coef_trace_mean": coef_trace.mean(axis=0).tolist(),
            "coef_trace_sd": coef_trace.std(axis=0, ddof=1).tolist(),
            "note": "descriptive, computed once per seed via integrated_lag_coefficients on the "
                    "full-data M3 fit -- NOT conditioned on which Zhat tier produced the delta "
                    "table above; tier-invariant by construction of integrated_lag_coefficients.",
        }

for name in SCENARIOS_7TO9:
    table[name] = {"p_to_r": {}, "r_to_p": {}, "A": {}}
    for direction, key in [("p_to_r", "p_to_r"), ("r_to_p", "r_to_p")]:
        true_beta_this_dir = params_dir = (SCENARIOS_7TO9[name]["beta_p_to_r"] if direction == "p_to_r"
                                            else SCENARIOS_7TO9[name]["beta_r_to_p"])
        for tier in TIERS:
            d = np.asarray(results_7to9[name][key][tier])
            cell = {"delta_mean": float(d.mean()), "delta_sd": float(d.std(ddof=1)), "n_seeds": len(d)}
            null_d = null_ref_7to9[key][tier]
            if true_beta_this_dir > 0:
                power, thr = _power(d, null_d)
                cell["power"] = power
                cell["power_threshold_used"] = thr
                cell["power_reference"] = "bidirectional_null_reference"
            else:
                cell["empirical_fpr"] = _fpr(d)
                cell["fpr_threshold_used"] = FPR_THRESHOLD
                cell["note"] = "no true coupling injected in this direction for this scenario -- specificity check"
            table[name][direction][tier] = cell
    for tier in TIERS:
        dp = np.asarray(results_7to9[name]["p_to_r"][tier])
        dr = np.asarray(results_7to9[name]["r_to_p"][tier])
        A = dp - dr
        table[name]["A"][tier] = {"A_mean": float(A.mean()), "A_sd": float(A.std(ddof=1))}

    loc = localization_7to9[name]
    loc_out = {}
    for direction, dkey in [("p_to_r", "fwd"), ("r_to_p", "swap")]:
        true_beta_this_dir = (SCENARIOS_7TO9[name]["beta_p_to_r"] if direction == "p_to_r"
                               else SCENARIOS_7TO9[name]["beta_r_to_p"])
        if true_beta_this_dir > 0 and len(loc[dkey]["direction_sign"]) > 0:
            signs = np.array(loc[dkey]["direction_sign"])
            peaks = np.array(loc[dkey]["peak_bin"])
            coef_trace = np.array(loc[dkey]["coef_trace"])
            loc_out[direction] = {
                "direction_recovery_fraction": float(np.mean(signs > 0)),
                "exact_interval_recovery_fraction": float(np.mean(np.isin(peaks, TRUE_INFORMATIVE_BINS))),
                "near_interval_recovery_fraction": float(np.mean(
                    np.abs(peaks[:, None] - np.array(TRUE_INFORMATIVE_BINS)[None, :]).min(axis=1) <= 1)),
                "coef_trace_mean": coef_trace.mean(axis=0).tolist(),
                "coef_trace_sd": coef_trace.std(axis=0, ddof=1).tolist(),
            }
    table[name]["localization"] = loc_out

# null reference table entry (auxiliary, not one of the 9 required scenarios)
table["bidirectional_null_reference"] = {"p_to_r": {}, "r_to_p": {}}
for key in ["p_to_r", "r_to_p"]:
    for tier in TIERS:
        d = np.asarray(null_ref_7to9[key][tier])
        table["bidirectional_null_reference"][key][tier] = {
            "delta_mean": float(d.mean()), "delta_sd": float(d.std(ddof=1)),
            "n_seeds": len(d), "empirical_fpr": _fpr(d), "fpr_threshold_used": FPR_THRESHOLD,
        }

# ================================================================================================
# Nuisance-estimation fidelity: timing_hat vs true_jitter (timing_null, combined_null); amplitude
# vs true_gain (combined_null only -- true_gain is constant/degenerate in timing_null)
# ================================================================================================
print("\n=== Nuisance-estimation fidelity ===")
fidelity = {}


def _fidelity_block(est, true, label):
    est = np.asarray(est).ravel()
    true = np.asarray(true).ravel()
    err = est - true
    r = float(np.corrcoef(est, true)[0, 1])
    bias = float(err.mean())
    rmse = float(np.sqrt(np.mean(err ** 2)))
    err_sd = err.std(ddof=1)
    outlier_rate = float(np.mean(np.abs(err - err.mean()) > 3 * err_sd)) if err_sd > 0 else float("nan")
    print(f"  {label:35s} r={r:+.4f}  bias={bias:+.4f}  rmse={rmse:.4f}  outlier_rate={outlier_rate:.4f}")
    return {"pearson_r": r, "bias_mean_signed_diff": bias, "rmse": rmse,
            "outlier_rate_gt_3sd_of_error": outlier_rate, "n_trials_pooled": len(est)}


tj_pool = np.concatenate(fidelity_pool["timing_null"]["true_jitter"])
th_pool = np.concatenate(fidelity_pool["timing_null"]["timing_hat"])
fidelity["timing_null_timing_hat_vs_true_jitter"] = _fidelity_block(th_pool, tj_pool, "timing_null: timing_hat vs true_jitter")

tj_pool_c = np.concatenate(fidelity_pool["combined_null"]["true_jitter"])
th_pool_c = np.concatenate(fidelity_pool["combined_null"]["timing_hat"])
fidelity["combined_null_timing_hat_vs_true_jitter"] = _fidelity_block(th_pool_c, tj_pool_c, "combined_null: timing_hat vs true_jitter")

tg_pool = np.concatenate(fidelity_pool["combined_null"]["true_gain"])
amp_pool = np.concatenate(fidelity_pool["combined_null"]["amplitude"])
amp_pool_rescaled = amp_pool / BASELINE_AMP  # rescale to a true_gain-comparable unit (amplitude ~= baseline_amp*gain)
fidelity["combined_null_amplitude_vs_true_gain"] = _fidelity_block(
    amp_pool_rescaled, tg_pool, "combined_null: amplitude/baseline_amp vs true_gain")
fidelity["combined_null_amplitude_vs_true_gain"]["rescaling_note"] = (
    f"amplitude estimate (pre-event baseline-window mean of P) is compared to true_gain after "
    f"dividing by the generator's baseline_amp constant ({BASELINE_AMP}), since "
    f"amplitude_i ~= baseline_amp * true_gain_i + noise by generator construction -- raw units "
    f"differ, this rescaling makes bias/rmse interpretable on true_gain's own scale."
)
fidelity["timing_null_amplitude_vs_true_gain"] = {
    "status": "skipped_degenerate",
    "reason": "timing_null has amp_gain=0.0 so true_gain is constant (=1.0) for every trial and "
              "every seed -- correlation/bias/rmse against a zero-variance target is undefined. "
              "Use combined_null_amplitude_vs_true_gain instead.",
}

FIDELITY_HIGH_CORRELATION_CAVEAT = (
    "Hamm's explicit instruction: high correlation here is NOT sufficient on its own. The "
    "downstream calibration (empirical_fpr) and power numbers in `table` are the actual "
    "acceptance criterion for whether a Zhat tier is usable -- a good fidelity number must not "
    "be allowed to stand in for or overshadow a bad downstream calibration number."
)

# ================================================================================================
# Write receipt
# ================================================================================================
WALL_CLOCK_S = time.time() - T_START
print(f"\nTotal wall-clock time: {WALL_CLOCK_S:.1f}s")

out_path = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "zhat-oracle-bridge-benchmark-20260828.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
payload = {
    "schema_version": 3,
    "id": "zhat-oracle-bridge-benchmark-20260828",
    "kind": "evidence",
    "title": "Oracle-Z -> observable-Zhat bridge benchmark: 9 scenarios x 4 tiers, calibration+power+direction+localization",
    "status": "provisional",
    "config": {
        "n_trials": N_TRIALS, "rho": RHO, "delay_ms": DELAY_MS, "beta_p_to_r": BETA,
        "beta_r_to_p_calibrated": BETA_R_TO_P_CALIBRATED, "calibration_diagnostic": _calib,
        "n_splits": N_SPLITS, "n_seeds": N_SEEDS, "seeds": SEEDS,
        "lag_bins_ms": LAG_BINS, "true_informative_bins_0indexed": TRUE_INFORMATIVE_BINS,
        "fpr_threshold": FPR_THRESHOLD, "power_sd_multiplier": POWER_SD_MULT,
        "tiers": TIERS, "wall_clock_seconds": WALL_CLOCK_S,
        "seed_count_note": (
            f"N_SEEDS={N_SEEDS}, within the required >=15-20 range and NOT reduced to the 12-seed "
            f"floor -- the sweep completed in {WALL_CLOCK_S:.0f}s, well inside the foreground time "
            f"budget."
        ),
    },
    "table": table,
    "nuisance_estimation_fidelity": fidelity,
    "fidelity_caveat": FIDELITY_HIGH_CORRELATION_CAVEAT,
    "notes": [],
}
out_path.write_text(json.dumps(payload, indent=2))
print(f"Wrote {out_path}")
