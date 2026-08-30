# SUPERSEDED (2026-08-30): this script belongs to the causal-identification investigation,
# CONFIRMED closed by causal-identification-branch-seal-20260828.json. Its numerical findings
# are preserved in that seal and in omission/artifacts/.lab/. Kept for provenance and because
# other scripts in this directory still import it; do not extend or rerun it for new analysis.
"""omission.scripts.dev_rho_beta_identifiability_surface_20260828 -- rho x beta identifiability
sweep for the PC1 (innovation-coupling) realized-coupling generator, under oracle
(translated-template) nuisance conditioning.

2026-08-28 (Hamm). Follow-up to `dev_realized_coupling_oracle_rerun_20260828.py`, which
established Delta_LFP separation at a single (rho=0.5, beta=1.5) point under the timing-only
nuisance scenario. This script maps the surface: does D = Delta_positive - Delta_null grow
smoothly with rho and beta, where (if anywhere) does detection become unreliable, and does the
estimator recover the correct coupling direction and approximate delay.

Base scenario throughout: timing-only nuisance (jitter_sd_ms=8.0, amp_gain=0.0 -- no gain
confound), delay_ms=30.0, coupling_kind="innovation" (PC1), n_trials=300. Gain is deliberately
NOT varied here (would make the grid 3D); the prior single-point run already showed
timing/gain/combined scenarios behave similarly, so this 2D rho x beta grid on the timing-only
case is the scoped target.

Grid: rho in [0.0, 0.1, 0.2, 0.3, 0.5, 0.8, 1.2] x beta in [0.0, 0.5, 1.0, 1.5, 2.5, 4.0].
8 seeds per cell, z_seed = 0..7 held IDENTICAL across every beta at a fixed rho (private_seed =
z_seed + 500000), so nuisance (Z) and private-innovation draws are matched across beta
comparisons within a rho row -- this reduces seed-to-seed noise in the Delta_positive -
Delta_null comparison, since only beta (and hence the injected coupling term) differs between
matched-seed cells in the same row.

Per-cell statistic: Delta_LFP = fit_translated_template_oracle(...)['delta'] -- the analytic-
oracle-nuisance-conditioned held-out incremental R^2 of adding REAL observed lag-bin LFP
features on top of a nuisance representation that already includes the EXACT analytic
null-hypothesis shape of every M3 feature (translated_template_nuisance). This is the strongest
available oracle-conditioned statistic from `distributed_lag_model.py`; see that module's
docstring for M1/M2/M3 definitions in this specific oracle-template variant.

Detection ("power") criterion: for a given rho, the 8 beta=0 seeds' Delta_LFP values give an
empirical null distribution for that row. threshold = the 95th percentile of those 8 null
Delta_LFP values (np.percentile(..., 95), linear interpolation, the numpy default). A seed at
beta>0 in the same row is "detected" if its Delta_LFP > threshold. Power = fraction of the 8
seeds detected. NOTE: with only 8 null draws this is a coarse plug-in estimate of a 95th
percentile, not a calibrated test -- stated explicitly, not smoothed over.

Direction recovery: fraction of seeds (per cell) for which
integrated_lag_coefficients(dataset)['sign_of_integrated_mass'] == 'positive' (the true
generator direction for beta>0 innovation coupling).

Lag/delay recovery: see LAG_BIN_TO_RESPONSE_LAG_MS below for the explicit bin-center-to-
response-window-center mapping and the true-delay-bracketing bins.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from omission.jnwb_ext.distributed_lag_model import (
    build_trial_level_dataset,
    fit_translated_template_oracle,
    integrated_lag_coefficients,
    translated_template_nuisance,
)
from omission.jnwb_ext.realized_coupling_generator import synthesize_realized_coupling_pair

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "omission" / "artifacts" / ".lab" / "rho-beta-identifiability-surface-20260828.json"

RHO_GRID = [0.0, 0.1, 0.2, 0.3, 0.5, 0.8, 1.2]
BETA_GRID = [0.0, 0.5, 1.0, 1.5, 2.5, 4.0]
N_SEEDS = 8
N_TRIALS = 300
TRIAL_LEN = 400
BASELINE_WINDOW = (0, 80)
JITTER_SD_MS = 8.0
AMP_GAIN = 0.0
DELAY_MS = 30.0
COUPLING_KIND = "innovation"
RESPONSE_WINDOW = (210, 230)
HISTORY_WINDOW = (180, 205)
LAG_BINS_MS = ((130, 150), (150, 170), (170, 190), (190, 210))

# --- explicit lag-bin -> "ms before response window" mapping -----------------------------
# Response window is (210,230)ms, center 220ms. Coupling is injected as an elementwise causal
# shift: R(t) += beta * P_private(t - delay_samples), delay_ms=30 => delay_samples=30 (FS=1000).
# So R's response-window samples t in [210,230) draw on P_private at t-30 in [180,200), i.e. the
# TRUE driving P-source window is [180,200)ms, center 190ms -- NOT aligned to any single lag-bin
# edge. Bin (170,190)ms has center 180 (10ms from true center); bin (190,210)ms has center 200
# (10ms from true center) -- the true source window straddles the boundary between these two
# bins almost exactly symmetrically. So "delay recovered" is defined as: peak-coefficient bin in
# {"170-190ms", "190-210ms"} (the two bins bracketing the true source window), NOT a single bin.
RESPONSE_CENTER_MS = float(np.mean(RESPONSE_WINDOW))
LAG_BIN_TO_RESPONSE_LAG_MS = {
    f"{lo}-{hi}ms": RESPONSE_CENTER_MS - float(np.mean((lo, hi))) for lo, hi in LAG_BINS_MS
}
TRUE_SOURCE_WINDOW_MS = (RESPONSE_WINDOW[0] - DELAY_MS, RESPONSE_WINDOW[1] - DELAY_MS)
TRUE_SOURCE_CENTER_MS = float(np.mean(TRUE_SOURCE_WINDOW_MS))
BRACKETING_BINS = ["170-190ms", "190-210ms"]


def run_cell(rho: float, beta: float, seed: int) -> dict:
    z_seed = seed
    private_seed = seed + 500000
    P, R, true_jitter, true_gain, P_private = synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, trial_len=TRIAL_LEN, baseline_window=BASELINE_WINDOW,
        jitter_sd_ms=JITTER_SD_MS, amp_gain=AMP_GAIN, rho=rho, beta=beta,
        delay_ms=DELAY_MS, coupling_kind=COUPLING_KIND, z_seed=z_seed, private_seed=private_seed,
    )
    if rho == 0.0:
        assert np.all(P_private == 0.0), (
            f"rho=0.0 must yield exactly zero P_private (generator sanity check failed at "
            f"seed={seed}, beta={beta})"
        )
    dataset = build_trial_level_dataset(
        P, R, baseline_window=BASELINE_WINDOW, history_window=HISTORY_WINDOW,
        response_window=RESPONSE_WINDOW, lag_bins_ms=LAG_BINS_MS, seed=seed,
    )
    hist_template, lag_template = translated_template_nuisance(
        true_jitter, true_gain, trial_len=TRIAL_LEN, history_window=HISTORY_WINDOW,
        lag_bins_ms=LAG_BINS_MS,
    )
    oracle = fit_translated_template_oracle(dataset, hist_template, lag_template, seed=seed)
    ilc = integrated_lag_coefficients(dataset)
    return {
        "delta": float(oracle["delta"]),
        "r2_M1": float(oracle["r2_M1"]),
        "r2_M2": float(oracle["r2_M2"]),
        "r2_M3": float(oracle["r2_M3"]),
        "sign_of_integrated_mass": ilc["sign_of_integrated_mass"],
        "tau_star_secondary_descriptive": ilc["tau_star_secondary_descriptive"],
        "lag_bin_coefficients": ilc["lag_bin_coefficients"],
        "max_abs_P_private": float(np.max(np.abs(P_private))),
    }


def main():
    t_start = time.time()
    raw = {}  # raw[rho][beta] = list of per-seed result dicts
    for rho in RHO_GRID:
        raw[rho] = {}
        for beta in BETA_GRID:
            cell_results = []
            for seed in range(N_SEEDS):
                cell_results.append(run_cell(rho, beta, seed))
            raw[rho][beta] = cell_results
            print(f"rho={rho} beta={beta}: mean delta={np.mean([r['delta'] for r in cell_results]):+.4f} "
                  f"(elapsed {time.time()-t_start:.0f}s)", flush=True)

    # ---- aggregation ----
    cells = []
    rho_boundary_check = {}
    for rho in RHO_GRID:
        null_deltas = np.array([r["delta"] for r in raw[rho][0.0]])
        null_mean, null_sd = float(null_deltas.mean()), float(null_deltas.std(ddof=1))
        null_threshold_95 = float(np.percentile(null_deltas, 95))

        if rho == 0.0:
            max_abs_pp = max(r["max_abs_P_private"] for beta_results in raw[rho].values() for r in beta_results)
            rho_boundary_check["rho_0_max_abs_P_private"] = max_abs_pp
            rho_boundary_check["rho_0_verified_zero_private"] = bool(max_abs_pp == 0.0)

        for beta in BETA_GRID:
            cell_results = raw[rho][beta]
            deltas = np.array([r["delta"] for r in cell_results])
            delta_mean, delta_sd = float(deltas.mean()), float(deltas.std(ddof=1))
            D = delta_mean - null_mean
            if beta == 0.0:
                power = float("nan")  # power undefined for the null itself
            else:
                power = float(np.mean(deltas > null_threshold_95))
            direction_frac_positive = float(
                np.mean([r["sign_of_integrated_mass"] == "positive" for r in cell_results])
            )
            peak_bins = [r["tau_star_secondary_descriptive"] for r in cell_results]
            frac_peak_in_bracketing_bins = float(np.mean([b in BRACKETING_BINS for b in peak_bins]))
            cells.append({
                "rho": rho, "beta": beta,
                "delta_mean": delta_mean, "delta_sd": delta_sd,
                "D": D,
                "power_vs_null_p95": power,
                "null_threshold_p95_used": null_threshold_95,
                "direction_recovery_fraction_positive": direction_frac_positive,
                "peak_lag_bin_per_seed": peak_bins,
                "lag_recovery_fraction_bracketing_bins": frac_peak_in_bracketing_bins,
                "n_seeds": N_SEEDS,
            })

    elapsed_s = time.time() - t_start

    # ---- interpretation (computed, not asserted) ----
    # approximate identifiability threshold: smallest rho (>0) at which, for beta>=1.0, power
    # reaches >=0.8 in at least one beta value tested.
    threshold_rho = None
    for rho in RHO_GRID:
        if rho == 0.0:
            continue
        row_cells = [c for c in cells if c["rho"] == rho and c["beta"] > 0]
        if any(c["power_vs_null_p95"] >= 0.8 for c in row_cells):
            threshold_rho = rho
            break

    d_grid = {rho: {beta: next(c["D"] for c in cells if c["rho"] == rho and c["beta"] == beta)
                     for beta in BETA_GRID} for rho in RHO_GRID}
    rho0_max_abs_D = max(abs(d_grid[0.0][b]) for b in BETA_GRID)

    interpretation = {
        "rho_zero_boundary": (
            f"At rho=0.0, P_private is EXACTLY zero for every trial by construction "
            f"(_make_private_waveform returns np.zeros when rho==0.0, verified programmatically: "
            f"max|P_private|={rho_boundary_check['rho_0_max_abs_P_private']} across all beta/seed "
            f"combinations at rho=0). Since coupling(t) = beta * causal_shift(P_private, delay) "
            f"and coupling_kind='innovation' uses P_private as its source, the injected coupling "
            f"term is IDENTICALLY ZERO at rho=0 regardless of beta -- beta=4.0 and beta=0.0 "
            f"generate bit-identical R_trials at rho=0 (same seeds). Observed max|D| across the "
            f"rho=0 row = {rho0_max_abs_D:.4f}, consistent with this being a trivial degenerate "
            f"boundary (no coupling signal exists to detect), not an estimator failure. This is "
            f"a documented generator sanity check, not a discovered identifiability limitation."
        ),
        "approx_identifiability_threshold_rho": threshold_rho,
        "threshold_note": (
            "Smallest rho>0 in the tested grid at which some beta>0 cell reaches power>=0.8 "
            "against the same-row empirical null p95 threshold. None found in grid." if threshold_rho is None
            else f"First rho in grid at which power>=0.8 is achieved for at least one beta value: rho={threshold_rho}."
        ),
        "lag_bin_response_mapping": LAG_BIN_TO_RESPONSE_LAG_MS,
        "true_source_window_ms": list(TRUE_SOURCE_WINDOW_MS),
        "true_source_center_ms": TRUE_SOURCE_CENTER_MS,
        "bracketing_bins_used_for_lag_recovery": BRACKETING_BINS,
    }

    receipt = {
        "schema_version": 3,
        "id": "rho-beta-identifiability-surface-20260828",
        "kind": "evidence",
        "title": "rho x beta identifiability surface for PC1 innovation-coupling generator under oracle-template nuisance conditioning",
        "status": "provisional",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "generated_by": "omission/scripts/dev_rho_beta_identifiability_surface_20260828.py",
        "parameters": {
            "rho_grid": RHO_GRID, "beta_grid": BETA_GRID, "n_seeds": N_SEEDS,
            "n_trials": N_TRIALS, "trial_len": TRIAL_LEN, "baseline_window": list(BASELINE_WINDOW),
            "jitter_sd_ms": JITTER_SD_MS, "amp_gain": AMP_GAIN, "delay_ms": DELAY_MS,
            "coupling_kind": COUPLING_KIND, "response_window": list(RESPONSE_WINDOW),
            "history_window": list(HISTORY_WINDOW), "lag_bins_ms": [list(b) for b in LAG_BINS_MS],
            "z_seed_range": [0, N_SEEDS - 1], "private_seed_offset": 500000,
            "seed_matching": "z_seed and private_seed identical across every beta at fixed rho (matched-seed comparison within row)",
        },
        "statistic_definition": {
            "delta_lfp": "fit_translated_template_oracle(...)['delta'] = held-out R2(M3_template) - R2(M2_template), analytic-oracle nuisance conditioning (translated_template_nuisance)",
            "power_definition": "fraction of 8 seeds at (rho,beta>0) with delta_lfp > 95th percentile of the 8 beta=0 delta_lfp values at the SAME rho (empirical, per-row null; coarse with n=8)",
            "direction_recovery": "fraction of seeds with integrated_lag_coefficients(dataset)['sign_of_integrated_mass'] == 'positive'",
            "lag_recovery": "fraction of seeds whose peak (tau_star_secondary_descriptive) lag bin is in {170-190ms, 190-210ms}, the two bins bracketing the true P-source window (see lag_bin_response_mapping)",
        },
        "cells": cells,
        "interpretation": interpretation,
        "runtime_seconds": elapsed_s,
        "notes": [
            "This is a synthetic-generator identifiability sweep, not a fit on real corpus data.",
            "Oracle (translated_template_nuisance) conditioning is used throughout -- this is the strongest available nuisance representation (exact analytic null-hypothesis shape), not a proxy estimated from data. Results here are an upper bound on what a non-oracle estimator could achieve.",
            "n_seeds=8 as specified (grid ran to completion within the foreground timeout; no seed reduction was needed).",
        ],
        "verification": {
            "run_command": "python -m omission.scripts.dev_rho_beta_identifiability_surface_20260828",
            "runtime_seconds": elapsed_s,
        },
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(receipt, f, indent=2)
    print(f"\nWrote receipt to {OUT_PATH} ({elapsed_s:.0f}s total)")
    print(f"rho=0 boundary check: max|P_private| = {rho_boundary_check['rho_0_max_abs_P_private']}")
    print(f"approx identifiability threshold rho (power>=0.8 first reached): {threshold_rho}")


if __name__ == "__main__":
    main()
