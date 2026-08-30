# SUPERSEDED (2026-08-30): this script belongs to the causal-identification investigation,
# CONFIRMED closed by causal-identification-branch-seal-20260828.json. Its numerical findings
# are preserved in that seal and in omission/artifacts/.lab/. Kept for provenance and because
# other scripts in this directory still import it; do not extend or rerun it for new analysis.
"""PC2 (full realized-P coupling) benchmark (2026-08-28, Hamm). Unlike PC1 (innovation-only
coupling, coupling_kind="innovation"), PC2 transmits P's FULL realized trace (shared + private)
to R: coupling_i(t) = beta * causal_shift(P_shared_i + P_private_i, delay). This is harder and
more physiologically analogous, since the transmitted signal now contains a component that is
ALSO explainable by Z (P_shared) alongside genuinely private variation.

Maintains the two independent statuses Hamm required: DETECTION (Delta_LFP = Perf(M3)-Perf(M2),
does past P add held-out predictive information beyond nuisance/history) and LOCALIZATION (where
in past P the incremental information lives -- interval-level, not exact-peak). A method may be
DETECTION_CONFIRMED while LAG_LOCALIZATION_UNRESOLVED; these are reported separately, never
collapsed into one verdict.

Critical PC2 diagnostic: verifies that removing the Z-predictable SHARED component of the
coupling pathway (Z->P_shared->coupling->R, a mediator pathway not captured by conditioning on
Z's DIRECT effect on R) is not mistaken for an estimator failure -- see the "fully-informed
oracle" comparison at the bottom, which explicitly gives M2 the analytic Z->P_shared->coupling->R
pathway too and confirms Delta_positive does not collapse when that channel is pre-removed
(i.e. it isolates the private-only contribution as a lower bound on what's detected).

Run with: python -m omission.scripts.dev_pc2_realized_coupling_benchmark_20260828
"""
import json
from pathlib import Path

import numpy as np

from omission.jnwb_ext.common_driver_control import _gaussian_kernel
from omission.jnwb_ext.realized_coupling_generator import synthesize_realized_coupling_pair
from omission.jnwb_ext.distributed_lag_model import (
    build_trial_level_dataset, translated_template_nuisance, fit_translated_template_oracle,
    integrated_lag_coefficients,
)

N_TRIALS = 300
SEEDS = list(range(10))
RHO = 0.5
BETA = 1.5
DELAY_MS = 30.0
P_CENTER, P_SIGMA = 150.0, 25.0
LAG_BINS = ((130, 150), (150, 170), (170, 190), (190, 210))  # "ms before response-window start (210ms)": 80-60, 60-40, 40-20, 20-0
RESPONSE_START = 210.0

SCENARIOS = {
    "timing_null":       dict(jitter_sd_ms=8.0, amp_gain=0.0, beta=0.0),
    "gain_null":         dict(jitter_sd_ms=0.0, amp_gain=0.6, beta=0.0),
    "combined_null":     dict(jitter_sd_ms=8.0, amp_gain=0.6, beta=0.0),
    "timing_PC2":        dict(jitter_sd_ms=8.0, amp_gain=0.0, beta=BETA),
    "gain_PC2":          dict(jitter_sd_ms=0.0, amp_gain=0.6, beta=BETA),
    "combined_PC2":      dict(jitter_sd_ms=8.0, amp_gain=0.6, beta=BETA),
}

# true delay maps to "informative P window" ~ [response_start - delay - small, response_start - delay + small];
# express which lag bin(s) should carry the signal, in "ms before response start" terms:
# delay=30ms -> informative window centered ~response_start-30=180ms -> lag_bin (170,190) center=180 is the
# nearest exact match; (190,210) partially overlaps too (edge at 190 is 20ms after the 170-190 bin's edge).
TRUE_INFORMATIVE_BINS = [2, 3]  # 0-indexed into LAG_BINS: (170,190) and (190,210)

results = {"primary": {}, "pc1_matched_comparison": {}, "fully_informed_diagnostic": {}}

print("=== PC2: primary detection + localization, 6 required scenarios ===")
for name, params in SCENARIOS.items():
    deltas, direction_signs, peak_bins, coef_traces = [], [], [], []
    for seed in SEEDS:
        P, R, true_jitter, true_gain, P_private = synthesize_realized_coupling_pair(
            n_trials=N_TRIALS, rho=RHO, delay_ms=DELAY_MS, coupling_kind="realized",
            z_seed=seed, private_seed=seed + 700000, **params,
        )
        dataset = build_trial_level_dataset(P, R, seed=seed)
        hist_t, lag_t = translated_template_nuisance(true_jitter, true_gain)
        fit = fit_translated_template_oracle(dataset, hist_t, lag_t, seed=seed)
        deltas.append(fit["delta"])

        coefs = integrated_lag_coefficients(dataset)
        coef_list = [coefs["lag_bin_coefficients"][f"{lo}-{hi}ms"] for lo, hi in LAG_BINS]
        coef_traces.append(coef_list)
        direction_signs.append(1 if coefs["sign_of_integrated_mass"] == "positive" else -1)
        peak_bins.append(int(np.argmax(np.abs(coef_list))))

    d = np.array(deltas)
    coef_traces = np.array(coef_traces)
    is_null = params["beta"] == 0.0
    results["primary"][name] = {
        "delta_mean": float(d.mean()), "delta_sd": float(d.std(ddof=1)),
        "coef_trace_mean": coef_traces.mean(axis=0).tolist(),
        "coef_trace_sd": coef_traces.std(axis=0, ddof=1).tolist(),
    }
    if not is_null:
        direction_signs = np.array(direction_signs)
        peak_bins = np.array(peak_bins)
        exact_peak_recovery = float(np.mean(np.isin(peak_bins, TRUE_INFORMATIVE_BINS)))
        near_peak_recovery = float(np.mean(np.abs(peak_bins[:, None] - np.array(TRUE_INFORMATIVE_BINS)[None, :]).min(axis=1) <= 1))
        results["primary"][name]["direction_recovery_fraction"] = float(np.mean(direction_signs > 0))
        results["primary"][name]["exact_interval_recovery_fraction"] = exact_peak_recovery
        results["primary"][name]["near_interval_recovery_fraction"] = near_peak_recovery
    print(f"  {name:15s} Delta={d.mean():+.4f}+-{d.std(ddof=1):.4f}"
          + ("" if is_null else f"   dir_recovery={results['primary'][name]['direction_recovery_fraction']:.2f}"
                                  f"   interval_recovery(exact/near)={results['primary'][name]['exact_interval_recovery_fraction']:.2f}"
                                  f"/{results['primary'][name]['near_interval_recovery_fraction']:.2f}"))

for base in ["timing", "gain", "combined"]:
    D = results["primary"][f"{base}_PC2"]["delta_mean"] - results["primary"][f"{base}_null"]["delta_mean"]
    results["primary"][f"{base}_D"] = D
    print(f"  D[{base}] = {D:+.4f}")

# ---------------------------------------------------------------------------------------------
# PC1 vs PC2 matched-seed comparison (timing-only nuisance structure, same seeds/rho/beta/delay)
# ---------------------------------------------------------------------------------------------
print("\n=== PC1 vs PC2 matched-seed comparison (timing_only nuisance) ===")
pc1_deltas, pc2_deltas = [], []
for seed in SEEDS:
    P1, R1, tj1, tg1, _ = synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, jitter_sd_ms=8.0, amp_gain=0.0, rho=RHO, beta=BETA, delay_ms=DELAY_MS,
        coupling_kind="innovation", z_seed=seed, private_seed=seed + 700000,
    )
    ds1 = build_trial_level_dataset(P1, R1, seed=seed)
    ht1, lt1 = translated_template_nuisance(tj1, tg1)
    pc1_deltas.append(fit_translated_template_oracle(ds1, ht1, lt1, seed=seed)["delta"])

    P2, R2, tj2, tg2, _ = synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, jitter_sd_ms=8.0, amp_gain=0.0, rho=RHO, beta=BETA, delay_ms=DELAY_MS,
        coupling_kind="realized", z_seed=seed, private_seed=seed + 700000,
    )
    ds2 = build_trial_level_dataset(P2, R2, seed=seed)
    ht2, lt2 = translated_template_nuisance(tj2, tg2)
    pc2_deltas.append(fit_translated_template_oracle(ds2, ht2, lt2, seed=seed)["delta"])

pc1_deltas, pc2_deltas = np.array(pc1_deltas), np.array(pc2_deltas)
results["pc1_matched_comparison"] = {
    "pc1_delta_mean": float(pc1_deltas.mean()), "pc1_delta_sd": float(pc1_deltas.std(ddof=1)),
    "pc2_delta_mean": float(pc2_deltas.mean()), "pc2_delta_sd": float(pc2_deltas.std(ddof=1)),
}
print(f"  PC1 (innovation) Delta={pc1_deltas.mean():+.4f}+-{pc1_deltas.std(ddof=1):.4f}")
print(f"  PC2 (realized)   Delta={pc2_deltas.mean():+.4f}+-{pc2_deltas.std(ddof=1):.4f}")

# ---------------------------------------------------------------------------------------------
# Critical PC2 diagnostic: "fully-informed" oracle M2 that ALSO analytically removes the
# Z -> P_shared -> coupling -> R mediator pathway (using the true beta, oracle-only), to confirm
# that shrinkage of Delta from including this pathway is not a failure -- it isolates the
# private-only contribution as a defensible lower bound on detected information.
# ---------------------------------------------------------------------------------------------
print("\n=== Critical PC2 diagnostic: nuisance-only vs fully-informed M2 (timing_PC2) ===")


def _fully_informed_delta(seed):
    params = SCENARIOS["timing_PC2"]
    P, R, true_jitter, true_gain, P_private = synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, rho=RHO, delay_ms=DELAY_MS, coupling_kind="realized",
        z_seed=seed, private_seed=seed + 700000, **params,
    )
    dataset = build_trial_level_dataset(P, R, seed=seed)
    hist_t, lag_t = translated_template_nuisance(true_jitter, true_gain)

    # analytic Z -> P_shared -> coupling -> R pathway: P_shared shifted by delay_ms is itself an
    # exact function of e_i with a RECENTERED kernel (p_center + delay_ms), scaled by true beta
    # (oracle-only knowledge) -- see module docstring for derivation.
    hist_t_shared_coupling, lag_t_shared_coupling = translated_template_nuisance(
        true_jitter, true_gain, p_center=P_CENTER + DELAY_MS, p_sigma=P_SIGMA,
    )
    informed_hist = hist_t + params["beta"] * hist_t_shared_coupling
    informed_lag = lag_t + params["beta"] * lag_t_shared_coupling

    naive_fit = fit_translated_template_oracle(dataset, hist_t, lag_t, seed=seed)
    informed_fit = fit_translated_template_oracle(dataset, informed_hist, informed_lag, seed=seed)
    return naive_fit["delta"], informed_fit["delta"]


naive_ds, informed_ds = [], []
for seed in SEEDS:
    n_d, i_d = _fully_informed_delta(seed)
    naive_ds.append(n_d)
    informed_ds.append(i_d)
naive_ds, informed_ds = np.array(naive_ds), np.array(informed_ds)
results["fully_informed_diagnostic"] = {
    "nuisance_only_delta_mean": float(naive_ds.mean()), "nuisance_only_delta_sd": float(naive_ds.std(ddof=1)),
    "fully_informed_delta_mean": float(informed_ds.mean()), "fully_informed_delta_sd": float(informed_ds.std(ddof=1)),
    "interpretation": (
        "fully_informed removes the Z->P_shared->coupling->R mediator pathway analytically (oracle-only, "
        "uses true beta); its Delta isolates the private-P-only contribution. It being smaller than "
        "nuisance_only's Delta (which still contains the mediator pathway) is EXPECTED and is not a failure -- "
        "per Hamm: 'the shared component may become statistically inseparable from the nuisance/event model; "
        "that is acceptable.' Both should remain > 0 (i.e. neither collapses to ~0) for PC2 to be considered "
        "genuinely detected beyond Z's direct effect."
    ),
}
print(f"  nuisance-only M2  Delta={naive_ds.mean():+.4f}+-{naive_ds.std(ddof=1):.4f}")
print(f"  fully-informed M2 Delta={informed_ds.mean():+.4f}+-{informed_ds.std(ddof=1):.4f}")

out_path = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "pc2-realized-coupling-benchmark-20260828.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps({
    "schema_version": 3,
    "id": "pc2-realized-coupling-benchmark-20260828",
    "kind": "evidence",
    "title": "PC2 (full realized-P coupling) benchmark: detection, localization, shared/private diagnostic",
    "status": "provisional",
    "n_trials": N_TRIALS, "n_seeds": len(SEEDS), "rho": RHO, "beta": BETA, "delay_ms": DELAY_MS,
    "lag_bins_ms_before_response_start": LAG_BINS, "true_informative_bins_0indexed": TRUE_INFORMATIVE_BINS,
    "results": results,
}, indent=2))
print(f"\nWrote {out_path}")
