"""Independent verifier (2026-08-28) for PC2 realized-coupling and reverse-direction/bidirectional
generator claims, plus the _FloorScaler fix in distributed_lag_model.py.

Fresh script, own decomposition/regression logic -- NOT a re-run of
dev_pc2_realized_coupling_benchmark_20260828.py or dev_reverse_direction_20260828.py. Treats
those scripts' receipts as claims to check, not facts.

Four items (see task spec):
  1. PC2 structural coupling: does coupling_kind="realized" transmit BOTH P_shared and P_private
     into R? -- own analytic P_shared reconstruction + joint OLS regression of R's residual on
     [causal_shift(P_shared), causal_shift(P_private)] (no CV, no Ridge, no scaler -- deliberately
     independent of the estimator machinery under test elsewhere).
  2. Fully-informed oracle claim at a DIFFERENT (beta, rho) than the original 1.5/0.5.
  3. Energy-matching calibration, independently recomputed, at rho=0.2 and rho=0.8 (not just the
     original 0.5), plus a check against the REALIZED injected-coupling std (not just the
     pre-coupling source std the calibration function itself reports).
  4. Four-condition directional-asymmetry battery on fresh disjoint seeds + an adversarial stress
     test of the _FloorScaler fix (near/at/below/above the 1e-4 floor), including a side-by-side
     comparison against the UNPATCHED bare sklearn StandardScaler to show the fix is load-bearing.

Run with: python -m omission.scripts.verify_pc2_reverse_independent_20260828
"""
import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler as SKStandardScaler

from omission.jnwb_ext.common_driver_control import _gaussian_kernel
from omission.jnwb_ext.realized_coupling_generator import (
    synthesize_realized_coupling_pair,
    synthesize_bidirectional_coupling_pair,
    calibrate_matched_beta_r_to_p,
)
from omission.jnwb_ext.distributed_lag_model import (
    build_trial_level_dataset,
    translated_template_nuisance,
    fit_translated_template_oracle,
    _held_out_predict,
    _FloorScaler,
    _r2_from_pred,
)

FS = 1000.0
verification = {}


def _my_causal_shift(x, d):
    """Own independent re-implementation of the causal forward-shift (not imported from the
    generator module), to avoid trusting the module's own _causal_shift for this check."""
    out = np.zeros_like(x)
    if d <= 0:
        return x.copy()
    if d < len(x):
        out[d:] = x[: len(x) - d]
    return out


# =====================================================================================
# ITEM 1 -- PC2 structural coupling: does R's coupling term depend on BOTH P_shared and
# P_private, not just one?
# =====================================================================================
print("=== ITEM 1: PC2 structural coupling (own decomposition + joint OLS) ===")

N1 = 220
BETA1 = 1.3
DELAY1_MS = 25.0
P_CENTER, P_SIGMA, R_CENTER, R_SIGMA = 150.0, 25.0, 220.0, 5.0
BASELINE_WINDOW = (0, 80)
BASELINE_AMP = 0.15

P1, R1, tj1, tg1, Ppriv1 = synthesize_realized_coupling_pair(
    n_trials=N1, jitter_sd_ms=8.0, amp_gain=0.5, rho=0.4, beta=BETA1, delay_ms=DELAY1_MS,
    coupling_kind="realized", z_seed=777, private_seed=999888,
)
trial_len = P1.shape[1]
t = np.arange(trial_len)
delay1_samples = int(round(DELAY1_MS * FS / 1000.0))

lo_b, hi_b = BASELINE_WINDOW
baseline_shape = np.zeros(trial_len)
baseline_shape[lo_b:hi_b] = 1.0

# own analytic reconstruction of P_shared, R_shared, R's baseline term
p_shared1 = np.stack([tg1[i] * _gaussian_kernel(t, P_CENTER + tj1[i], P_SIGMA) for i in range(N1)])
r_shared1 = np.stack([tg1[i] * _gaussian_kernel(t, R_CENTER + tj1[i], R_SIGMA) for i in range(N1)])
r_base1 = np.stack([BASELINE_AMP * tg1[i] * baseline_shape for i in range(N1)])

residual1 = R1 - r_shared1 - r_base1  # should equal beta*shift(p_shared+p_priv) + measurement noise

X1_shared = np.stack([_my_causal_shift(p_shared1[i], delay1_samples) for i in range(N1)])
X1_priv = np.stack([_my_causal_shift(Ppriv1[i], delay1_samples) for i in range(N1)])

y_flat = residual1.reshape(-1)
x_shared_flat = X1_shared.reshape(-1)
x_priv_flat = X1_priv.reshape(-1)

# joint OLS: residual ~ b0 + b1*shift(P_shared) + b2*shift(P_private)
design = np.column_stack([np.ones_like(y_flat), x_shared_flat, x_priv_flat])
coef, res_ss, rank, sv = np.linalg.lstsq(design, y_flat, rcond=None)
n_obs = len(y_flat)
resid_ols = y_flat - design @ coef
sigma2 = np.sum(resid_ols ** 2) / (n_obs - design.shape[1])
xtx_inv = np.linalg.inv(design.T @ design)
se = np.sqrt(np.diag(sigma2 * xtx_inv))
b0, b1_shared, b2_priv = coef
se0, se1, se2 = se

# ablation: shared-only and private-only single-regressor models, R^2 comparison
design_shared_only = np.column_stack([np.ones_like(y_flat), x_shared_flat])
coef_so, *_ = np.linalg.lstsq(design_shared_only, y_flat, rcond=None)
pred_so = design_shared_only @ coef_so
r2_shared_only = 1 - np.sum((y_flat - pred_so) ** 2) / np.sum((y_flat - y_flat.mean()) ** 2)

design_priv_only = np.column_stack([np.ones_like(y_flat), x_priv_flat])
coef_po, *_ = np.linalg.lstsq(design_priv_only, y_flat, rcond=None)
pred_po = design_priv_only @ coef_po
r2_priv_only = 1 - np.sum((y_flat - pred_po) ** 2) / np.sum((y_flat - y_flat.mean()) ** 2)

pred_joint = design @ coef
r2_joint = 1 - np.sum((y_flat - pred_joint) ** 2) / np.sum((y_flat - y_flat.mean()) ** 2)

item1_pass = (
    abs(b1_shared - BETA1) < 5 * se1 and abs(b1_shared - BETA1) / BETA1 < 0.1
    and abs(b2_priv - BETA1) < 5 * se2 and abs(b2_priv - BETA1) / BETA1 < 0.1
    and r2_joint > max(r2_shared_only, r2_priv_only) - 1e-6
)
print(f"  beta_true={BETA1}  b_shared={b1_shared:+.4f}+-{se1:.4f}  b_private={b2_priv:+.4f}+-{se2:.4f}")
print(f"  R2 joint={r2_joint:.4f}  R2 shared-only={r2_shared_only:.4f}  R2 private-only={r2_priv_only:.4f}")
print(f"  -> {'PASS' if item1_pass else 'FAIL'}")

verification["item1_pc2_structural_coupling"] = {
    "check": "joint OLS of R's coupling residual (R - r_shared_analytic - r_baseline_analytic) on "
             "[causal_shift(P_shared_analytic, delay), causal_shift(P_private, delay)] -- both "
             "coefficients should recover the true beta if BOTH pieces are transmitted, not just one",
    "beta_true": BETA1, "delay_ms": DELAY1_MS, "n_trials": N1,
    "coef_intercept": float(b0), "se_intercept": float(se0),
    "coef_shared": float(b1_shared), "se_shared": float(se1),
    "coef_private": float(b2_priv), "se_private": float(se2),
    "r2_joint": float(r2_joint), "r2_shared_only": float(r2_shared_only), "r2_private_only": float(r2_priv_only),
    "verdict": "PASS" if item1_pass else "FAIL",
}

# =====================================================================================
# ITEM 2 -- fully-informed oracle claim at a DIFFERENT (beta, rho) than 1.5/0.5
# =====================================================================================
print("\n=== ITEM 2: fully-informed oracle diagnostic at a different (beta, rho) ===")

N2 = 250
BETA2 = 1.0
RHO2 = 0.35
DELAY2_MS = 25.0
SEEDS2 = list(range(5))

naive_deltas2, informed_deltas2 = [], []
for seed in SEEDS2:
    z_seed = 3000 + seed
    private_seed = 3500000 + seed
    P, R, tj, tg, Ppriv = synthesize_realized_coupling_pair(
        n_trials=N2, jitter_sd_ms=8.0, amp_gain=0.0, rho=RHO2, beta=BETA2, delay_ms=DELAY2_MS,
        coupling_kind="realized", z_seed=z_seed, private_seed=private_seed,
    )
    dataset = build_trial_level_dataset(P, R, seed=seed)
    hist_t, lag_t = translated_template_nuisance(tj, tg)
    hist_sc, lag_sc = translated_template_nuisance(tj, tg, p_center=P_CENTER + DELAY2_MS, p_sigma=P_SIGMA)
    informed_hist = hist_t + BETA2 * hist_sc
    informed_lag = lag_t + BETA2 * lag_sc

    naive_fit = fit_translated_template_oracle(dataset, hist_t, lag_t, seed=seed)
    informed_fit = fit_translated_template_oracle(dataset, informed_hist, informed_lag, seed=seed)
    naive_deltas2.append(naive_fit["delta"])
    informed_deltas2.append(informed_fit["delta"])

naive_deltas2 = np.array(naive_deltas2)
informed_deltas2 = np.array(informed_deltas2)
naive_mean2, naive_sd2 = float(naive_deltas2.mean()), float(naive_deltas2.std(ddof=1))
informed_mean2, informed_sd2 = float(informed_deltas2.mean()), float(informed_deltas2.std(ddof=1))
se_naive2 = naive_sd2 / np.sqrt(len(SEEDS2))
se_informed2 = informed_sd2 / np.sqrt(len(SEEDS2))

item2_pass = (naive_mean2 - 2 * se_naive2 > 0) and (informed_mean2 - 2 * se_informed2 > 0)
print(f"  beta={BETA2}, rho={RHO2}: naive Delta={naive_mean2:+.4f}+-{naive_sd2:.4f}   "
      f"informed Delta={informed_mean2:+.4f}+-{informed_sd2:.4f}")
print(f"  informed < naive (expected shrinkage): {informed_mean2 < naive_mean2}")
print(f"  -> {'PASS' if item2_pass else 'FAIL'}")

verification["item2_fully_informed_oracle_diff_params"] = {
    "check": "same fully-informed-oracle diagnostic as the existing script but at beta="
             f"{BETA2}, rho={RHO2} (existing script only checked beta=1.5, rho=0.5); both naive "
             "and fully-informed Delta must remain clearly positive (2 SE below zero) for the claim "
             "not to be a coincidence of the original parameterization",
    "beta": BETA2, "rho": RHO2, "delay_ms": DELAY2_MS, "n_trials": N2, "n_seeds": len(SEEDS2),
    "naive_delta_per_seed": naive_deltas2.tolist(), "informed_delta_per_seed": informed_deltas2.tolist(),
    "naive_delta_mean": naive_mean2, "naive_delta_sd": naive_sd2,
    "informed_delta_mean": informed_mean2, "informed_delta_sd": informed_sd2,
    "informed_lt_naive": bool(informed_mean2 < naive_mean2),
    "verdict": "PASS" if item2_pass else "FAIL",
}

# =====================================================================================
# ITEM 3 -- energy-matching calibration, independently recomputed at rho=0.2 and rho=0.8
# =====================================================================================
print("\n=== ITEM 3: energy-matching calibration at rho=0.2 and rho=0.8 (own recomputation) ===")

TARGET_BETA = 1.2
DELAY3_MS = 30.0
item3_results = {}
item3_all_pass = True
for rho in (0.2, 0.8):
    calib = calibrate_matched_beta_r_to_p(
        TARGET_BETA, coupling_kind="realized", p_center=P_CENTER, p_sigma=P_SIGMA,
        r_center=R_CENTER, r_sigma=R_SIGMA, rho=rho, trial_len=400,
    )
    beta_r_to_p = calib["calibrated_beta_r_to_p"]

    # own, independent recomputation of source stds: DIFFERENT seed than calibrate()'s internal
    # calib_seed=999 default, own loop, own analytic P_shared/R_shared construction
    N3 = 500
    z_seed3, priv_seed3 = 44444, 55555
    P3, R3, tj3, tg3, Ppriv3, Rpriv3 = synthesize_bidirectional_coupling_pair(
        n_trials=N3, trial_len=400, rho=rho, beta_p_to_r=0.0, beta_r_to_p=0.0, noise_sd=0.0,
        p_center=P_CENTER, p_sigma=P_SIGMA, r_center=R_CENTER, r_sigma=R_SIGMA,
        z_seed=z_seed3, private_seed=priv_seed3,
    )
    t3 = np.arange(400)
    my_source_P = np.stack([tg3[i] * _gaussian_kernel(t3, P_CENTER + tj3[i], P_SIGMA) for i in range(N3)]) + Ppriv3
    my_source_R = np.stack([tg3[i] * _gaussian_kernel(t3, R_CENTER + tj3[i], R_SIGMA) for i in range(N3)]) + Rpriv3
    my_std_P = float(my_source_P.std())
    my_std_R = float(my_source_R.std())
    my_beta_r_to_p = TARGET_BETA * my_std_P / my_std_R

    rel_diff_beta = abs(my_beta_r_to_p - beta_r_to_p) / beta_r_to_p

    # direct check: actually inject coupling with calib's beta_r_to_p and measure the REALIZED
    # injected coupling std on each side (not just the pre-coupling source std), independent of
    # calibrate()'s own reported "achieved_*" numbers
    Pc, Rc, tjc, tgc, Ppc, Rpc = synthesize_bidirectional_coupling_pair(
        n_trials=N3, trial_len=400, rho=rho, beta_p_to_r=TARGET_BETA, beta_r_to_p=beta_r_to_p,
        delay_ms=DELAY3_MS, coupling_kind="realized", noise_sd=0.0,
        p_center=P_CENTER, p_sigma=P_SIGMA, r_center=R_CENTER, r_sigma=R_SIGMA,
        z_seed=z_seed3 + 1, private_seed=priv_seed3 + 1,
    )
    delay3_samples = int(round(DELAY3_MS * FS / 1000.0))
    source_p_c = np.stack([tgc[i] * _gaussian_kernel(t3, P_CENTER + tjc[i], P_SIGMA) for i in range(N3)]) + Ppc
    source_r_c = np.stack([tgc[i] * _gaussian_kernel(t3, R_CENTER + tjc[i], R_SIGMA) for i in range(N3)]) + Rpc
    coupling_to_r_realized = TARGET_BETA * np.stack([_my_causal_shift(source_p_c[i], delay3_samples) for i in range(N3)])
    coupling_to_p_realized = beta_r_to_p * np.stack([_my_causal_shift(source_r_c[i], delay3_samples) for i in range(N3)])
    # exclude the zero-forced pre-delay samples from the std computation (they're not part of the
    # injected waveform's support, and including them would bias std toward zero unequally between
    # the two sides only if delay differed -- here delay is identical so it's a minor correction)
    std_inj_r = float(coupling_to_r_realized[:, delay3_samples:].std())
    std_inj_p = float(coupling_to_p_realized[:, delay3_samples:].std())
    rel_mismatch_realized = abs(std_inj_r - std_inj_p) / std_inj_r

    pass_rho = rel_diff_beta < 0.08 and rel_mismatch_realized < 0.08
    item3_all_pass = item3_all_pass and pass_rho
    print(f"  rho={rho}: calib beta_r_to_p={beta_r_to_p:.4f}  my_beta_r_to_p={my_beta_r_to_p:.4f}  "
          f"rel_diff={rel_diff_beta:.4f}")
    print(f"           realized injected std: to_R={std_inj_r:.4f}  to_P={std_inj_p:.4f}  "
          f"rel_mismatch={rel_mismatch_realized:.4f}  -> {'PASS' if pass_rho else 'FAIL'}")

    item3_results[f"rho_{rho}"] = {
        "calib_reported_beta_r_to_p": beta_r_to_p,
        "calib_reported_std_P": calib["std_source_P"], "calib_reported_std_R": calib["std_source_R"],
        "calib_reported_relative_mismatch": calib["relative_mismatch"],
        "my_independent_std_P": my_std_P, "my_independent_std_R": my_std_R,
        "my_independent_beta_r_to_p": my_beta_r_to_p,
        "relative_diff_beta_vs_calib": rel_diff_beta,
        "realized_injected_std_to_r": std_inj_r, "realized_injected_std_to_p": std_inj_p,
        "realized_relative_mismatch": rel_mismatch_realized,
        "verdict": "PASS" if pass_rho else "FAIL",
    }

verification["item3_energy_calibration_rho_sweep"] = {
    "check": "independent recomputation (own seeds, own analytic P_shared/R_shared, own std) of "
             "calibrate_matched_beta_r_to_p's energy-matching claim at rho=0.2 and rho=0.8, plus a "
             "direct measurement of the REALIZED injected coupling std under the calibrated beta "
             "(not just calibrate()'s own reported pre-coupling source std)",
    "target_beta_p_to_r": TARGET_BETA, "delay_ms": DELAY3_MS, "n_calib_trials": N3,
    "per_rho": item3_results,
    "verdict": "PASS" if item3_all_pass else "FAIL",
}

# =====================================================================================
# ITEM 4a -- four-condition directional-asymmetry battery on FRESH disjoint seeds
# =====================================================================================
print("\n=== ITEM 4a: directional-asymmetry battery, fresh seeds (z_seed 2000-2007) ===")

N4 = 220
TARGET_BETA_P2R = 1.5
DELAY4_MS = 30.0
JITTER_SD4 = 8.0
SEEDS4 = list(range(2000, 2008))  # disjoint from original 0-9

calib4 = calibrate_matched_beta_r_to_p(
    TARGET_BETA_P2R, coupling_kind="realized", p_center=P_CENTER, p_sigma=P_SIGMA,
    r_center=R_CENTER, r_sigma=R_SIGMA, rho=0.5, trial_len=400,
)
BETA_R2P4 = calib4["calibrated_beta_r_to_p"]

CONDITIONS4 = {
    "no_coupling":   dict(beta_p_to_r=0.0, beta_r_to_p=0.0),
    "P_to_R_only":   dict(beta_p_to_r=TARGET_BETA_P2R, beta_r_to_p=0.0),
    "R_to_P_only":   dict(beta_p_to_r=0.0, beta_r_to_p=BETA_R2P4),
    "bidirectional": dict(beta_p_to_r=TARGET_BETA_P2R, beta_r_to_p=BETA_R2P4),
}

battery_results = {}
all_deltas_flat = []
blowup_found = False
for name, betas in CONDITIONS4.items():
    dp_list, dr_list = [], []
    for i, seed in enumerate(SEEDS4):
        private_seed = 2500000 + i
        P, R, tj, tg, Ppriv, Rpriv = synthesize_bidirectional_coupling_pair(
            n_trials=N4, trial_len=400, jitter_sd_ms=JITTER_SD4, amp_gain=0.0, rho=0.5,
            delay_ms=DELAY4_MS, coupling_kind="realized",
            p_center=P_CENTER, p_sigma=P_SIGMA, r_center=R_CENTER, r_sigma=R_SIGMA,
            z_seed=seed, private_seed=private_seed, **betas,
        )
        ds_fwd = build_trial_level_dataset(P, R, seed=seed)
        ht_fwd, lt_fwd = translated_template_nuisance(tj, tg, p_center=P_CENTER, p_sigma=P_SIGMA, r_center=R_CENTER, r_sigma=R_SIGMA)
        fit_fwd = fit_translated_template_oracle(ds_fwd, ht_fwd, lt_fwd, seed=seed)

        ds_rev = build_trial_level_dataset(R, P, seed=seed)
        ht_rev, lt_rev = translated_template_nuisance(tj, tg, p_center=R_CENTER, p_sigma=R_SIGMA, r_center=P_CENTER, r_sigma=P_SIGMA)
        fit_rev = fit_translated_template_oracle(ds_rev, ht_rev, lt_rev, seed=seed)

        dp_list.append(fit_fwd["delta"])
        dr_list.append(fit_rev["delta"])
        all_deltas_flat.extend([fit_fwd["delta"], fit_rev["delta"]])
        if abs(fit_fwd["delta"]) > 10 or abs(fit_rev["delta"]) > 10:
            blowup_found = True

    dp = np.array(dp_list)
    dr = np.array(dr_list)
    A = dp - dr
    battery_results[name] = {
        "delta_p_to_r_mean": float(dp.mean()), "delta_p_to_r_sd": float(dp.std(ddof=1)),
        "delta_r_to_p_mean": float(dr.mean()), "delta_r_to_p_sd": float(dr.std(ddof=1)),
        "A_mean": float(A.mean()), "A_sd": float(A.std(ddof=1)),
    }
    print(f"  {name:15s} Delta_P->R={dp.mean():+.4f}+-{dp.std(ddof=1):.4f}   "
          f"Delta_R->P={dr.mean():+.4f}+-{dr.std(ddof=1):.4f}   A={A.mean():+.4f}+-{A.std(ddof=1):.4f}")

max_abs_delta = float(np.max(np.abs(all_deltas_flat)))
no_blowup = (not blowup_found) and max_abs_delta < 10.0

# qualitative pattern check
A_no = battery_results["no_coupling"]["A_mean"]
A_p2r = battery_results["P_to_R_only"]["A_mean"]
A_r2p = battery_results["R_to_P_only"]["A_mean"]
A_bidir = battery_results["bidirectional"]["A_mean"]
sd_no = battery_results["no_coupling"]["A_sd"] / np.sqrt(len(SEEDS4))

pattern_ok = (
    abs(A_no) < 3 * sd_no + 0.1  # near zero at no-coupling
    and A_p2r > 0.15             # correctly signed, substantial, P->R
    and A_r2p < -0.15            # correctly signed, substantial, R->P (opposite sign)
    and abs(A_bidir) < max(abs(A_p2r), abs(A_r2p))  # attenuated under bidirectional
)
item4a_pass = no_blowup and pattern_ok
print(f"  max|Delta| across all fits = {max_abs_delta:.4f}   no_blowup={no_blowup}")
print(f"  A: no_coupling={A_no:+.4f}  P->R_only={A_p2r:+.4f}  R->P_only={A_r2p:+.4f}  bidir={A_bidir:+.4f}")
print(f"  pattern reproduces: {pattern_ok}")
print(f"  -> {'PASS' if item4a_pass else 'FAIL'}")

verification["item4a_directional_asymmetry_fresh_seeds"] = {
    "check": "four-condition battery (no_coupling/P_to_R_only/R_to_P_only/bidirectional) on fresh "
             "disjoint seeds z_seed 2000-2007, private_seed 2500000+i -- checks for numerical "
             "blow-up (scaler-fix regression) and qualitative reproduction of the directional "
             "asymmetry pattern",
    "n_trials": N4, "n_seeds": len(SEEDS4), "target_beta_p_to_r": TARGET_BETA_P2R,
    "beta_r_to_p_calibrated": BETA_R2P4, "delay_ms": DELAY4_MS,
    "conditions": battery_results, "max_abs_delta_any_fit": max_abs_delta,
    "no_numerical_blowup": no_blowup, "qualitative_pattern_reproduces": pattern_ok,
    "verdict": "PASS" if item4a_pass else "FAIL",
}

# =====================================================================================
# ITEM 4b -- stress-test the _FloorScaler fix directly: synthetic near-degenerate columns
# at/below/above the 1e-4 floor, plus a side-by-side comparison against the UNPATCHED bare
# sklearn StandardScaler to demonstrate the fix is load-bearing, not cosmetic.
# =====================================================================================
print("\n=== ITEM 4b: _FloorScaler adequacy stress test ===")

rng = np.random.default_rng(13579)
n_rows = 220
col_informative = rng.normal(0, 2.0, n_rows)          # genuine signal
y_stress = 3.0 * col_informative + rng.normal(0, 1.0, n_rows)

stress_cases = {
    "std_5e-9_bug_scale": 5e-9,     # exact scale the original bug was found at
    "std_1e-5_below_floor": 1e-5,
    "std_1e-4_at_floor": 1e-4,      # strict '<' in _FloorScaler -> NOT clamped
    "std_9.9e-5_just_below_floor": 9.9e-5,
    "std_2e-4_just_above_floor": 2e-4,
}


def _held_out_predict_raw_sklearn(X, y, n_splits=5, alpha=1.0, seed=0):
    """UNPATCHED replica of _held_out_predict using the bare sklearn StandardScaler (pre-fix
    behavior), for direct comparison against the patched _FloorScaler pipeline on the SAME data."""
    n = len(y)
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    y_pred = np.full(n, np.nan)
    for train_idx, test_idx in kf.split(X):
        scaler = SKStandardScaler().fit(X[train_idx])
        Xtr, Xte = scaler.transform(X[train_idx]), scaler.transform(X[test_idx])
        model = Ridge(alpha=alpha).fit(Xtr, y[train_idx])
        y_pred[test_idx] = model.predict(Xte)
    return y_pred


stress_results = {}
item4b_all_pass = True
y_scale = float(np.std(y_stress))
sane_threshold = 200.0 * y_scale  # generous bound; the actual bug produced 1e6-1e8 scale errors

# --- adversarial fold-mismatch construction: this is the actual documented failure MECHANISM,
# not just "a column with a small population std". A fixed population std (all cases above) never
# reproduces the original bug with plain sklearn StandardScaler either, because a representative
# std means train- and test-fold values stay the same order of magnitude. The real bug requires a
# TRAIN-FOLD std that is orders of magnitude smaller than the values the TEST fold actually takes
# -- i.e. per-trial noise-floor HETEROGENEITY across the KFold split, exactly what "a narrow-kernel
# signal's analytic support doesn't reach a given window" produces (near-zero for most trials,
# genuinely nonzero for a structured subset). Constructed directly (not via translated_template_
# nuisance) to isolate the mechanism: one contiguous block of trials carries a distinct, larger
# noise floor (5e-6) than the rest (1e-14, nominally machine-epsilon-scale), and KFold(shuffle=
# False) puts that whole block in one fold's TEST set -- so its TRAIN fold sees only the tiny
# noise floor.
print("  -- adversarial fold-std-mismatch construction (isolates the actual failure mechanism) --")
rng_adv = np.random.default_rng(2468)
n_adv = 220
col_info_adv = rng_adv.normal(0, 2.0, n_adv)
y_adv = 3.0 * col_info_adv + rng_adv.normal(0, 1.0, n_adv)
degenerate_adv = rng_adv.normal(0, 1e-14, n_adv)
degenerate_adv[0:44] = rng_adv.normal(0, 5e-6, 44)  # exactly one KFold(shuffle=False) fold's test block
X_adv = np.column_stack([col_info_adv, degenerate_adv])

kf_adv = KFold(n_splits=5, shuffle=False)
y_pred_adv_patched = np.full(n_adv, np.nan)
y_pred_adv_unpatched = np.full(n_adv, np.nan)
fold_train_stds_unpatched = []
for train_idx, test_idx in kf_adv.split(X_adv):
    sc_p = _FloorScaler().fit(X_adv[train_idx])
    Xtr_p, Xte_p = sc_p.transform(X_adv[train_idx]), sc_p.transform(X_adv[test_idx])
    y_pred_adv_patched[test_idx] = Ridge(alpha=1.0).fit(Xtr_p, y_adv[train_idx]).predict(Xte_p)

    sc_u = SKStandardScaler().fit(X_adv[train_idx])
    fold_train_stds_unpatched.append(float(sc_u.scale_[1]))
    Xtr_u, Xte_u = sc_u.transform(X_adv[train_idx]), sc_u.transform(X_adv[test_idx])
    y_pred_adv_unpatched[test_idx] = Ridge(alpha=1.0).fit(Xtr_u, y_adv[train_idx]).predict(Xte_u)

max_abs_adv_patched = float(np.max(np.abs(y_pred_adv_patched)))
max_abs_adv_unpatched = float(np.max(np.abs(y_pred_adv_unpatched)))
adv_patched_sane = max_abs_adv_patched < sane_threshold
adv_unpatched_blows_up = max_abs_adv_unpatched > 1e4  # confirms the mechanism actually fires
adv_pass = adv_patched_sane and adv_unpatched_blows_up
item4b_all_pass = item4b_all_pass and adv_pass
print(f"  adversarial_fold_mismatch     unpatched min train-fold std={min(fold_train_stds_unpatched):.2e}  "
      f"max|pred| patched={max_abs_adv_patched:.3e}  unpatched={max_abs_adv_unpatched:.3e}  "
      f"(unpatched blow-up reproduced: {adv_unpatched_blows_up})  -> {'PASS' if adv_pass else 'FAIL'}")
stress_results["adversarial_fold_std_mismatch"] = {
    "description": "one 44-trial block has a distinct larger noise floor (5e-6) than the rest "
                    "(1e-14); KFold(shuffle=False) isolates it entirely into one fold's test set, "
                    "so that fold's TRAIN std is ~1e-14 (near machine epsilon) while its TEST "
                    "values are ~5e-6 -- this is the actual documented failure mechanism, not just "
                    "a small fixed population std",
    "unpatched_min_train_fold_std": float(min(fold_train_stds_unpatched)),
    "max_abs_pred_patched": max_abs_adv_patched, "max_abs_pred_unpatched_raw_sklearn": max_abs_adv_unpatched,
    "patched_sane": adv_patched_sane, "unpatched_blowup_reproduced": adv_unpatched_blows_up,
    "verdict": "PASS" if adv_pass else "FAIL",
}

for case_name, degenerate_std in stress_cases.items():
    # scale to an EXACT realized std (not just a target std for the draw -- with n_rows=220 the
    # sampling std of a std estimate is large enough that a boundary case like "1e-4" or "9.9e-5"
    # could land on the wrong side of the floor by chance; exact scaling makes the boundary test
    # precise)
    raw = rng.normal(0, 1.0, n_rows)
    degenerate_col = (raw - raw.mean()) / raw.std() * degenerate_std
    X_stress = np.column_stack([col_informative, degenerate_col])

    y_pred_patched = _held_out_predict(X_stress, y_stress, seed=0)
    max_abs_patched = float(np.max(np.abs(y_pred_patched)))
    r2_patched = _r2_from_pred(y_stress, y_pred_patched)
    patched_sane = max_abs_patched < sane_threshold

    y_pred_unpatched = _held_out_predict_raw_sklearn(X_stress, y_stress, seed=0)
    max_abs_unpatched = float(np.max(np.abs(y_pred_unpatched)))
    unpatched_sane = max_abs_unpatched < sane_threshold

    # also confirm _FloorScaler's clamp decision directly, on the FULL column (matches its own
    # fit() semantics), independent of the CV loop
    # X.std(axis=0), computed inside _FloorScaler.fit on the FULL 2-column array, can differ from
    # a standalone np.std(degenerate_col) in the last ULP (verified directly: at the exact
    # nominal 1e-4 case the two differ by ~1e-20, enough to flip which side of "< floor" the
    # column lands on). So AT the exact boundary the clamp decision is itself sub-ULP-noise
    # dependent -- not a bug, but a genuine (harmless, since sane either way) numerical-precision
    # note, not a hard pass/fail criterion for that one case.
    scaler_direct = _FloorScaler().fit(X_stress)
    full_std = float(np.std(degenerate_col))
    clamped = bool(scaler_direct.scale_[1] == 1.0)
    expected_clamped = full_std < 1e-4
    at_exact_boundary = abs(degenerate_std - 1e-4) < 1e-12
    clamp_matches_expectation = clamped == expected_clamped

    case_pass = patched_sane if at_exact_boundary else (patched_sane and clamp_matches_expectation)
    item4b_all_pass = item4b_all_pass and case_pass
    boundary_note = " (exact-boundary sub-ULP ambiguity, not treated as fail criterion)" if at_exact_boundary and not clamp_matches_expectation else ""
    print(f"  {case_name:28s} full_std={full_std:.2e}  clamped={clamped} (expected {expected_clamped}){boundary_note}  "
          f"max|pred| patched={max_abs_patched:.3e}  unpatched={max_abs_unpatched:.3e}  "
          f"patched_sane={patched_sane}  -> {'PASS' if case_pass else 'FAIL'}")

    stress_results[case_name] = {
        "nominal_std": degenerate_std, "realized_full_column_std": full_std,
        "clamped_by_floor_scaler": clamped, "expected_clamped": expected_clamped,
        "at_exact_boundary": at_exact_boundary, "clamp_matches_expectation": clamp_matches_expectation,
        "max_abs_pred_patched": max_abs_patched, "r2_patched": r2_patched,
        "max_abs_pred_unpatched_raw_sklearn": max_abs_unpatched,
        "patched_sane": patched_sane, "unpatched_sane": unpatched_sane,
        "sane_threshold": sane_threshold,
        "verdict": "PASS" if case_pass else "FAIL",
    }

print(f"  -> overall stress test: {'PASS' if item4b_all_pass else 'FAIL'}")

verification["item4b_floor_scaler_adequacy_stress_test"] = {
    "check": "synthetic 2-column design matrix (1 informative + 1 near-degenerate at std "
             "5e-9/1e-5/1e-4/9.9e-5/2e-4), run through the PATCHED _held_out_predict (module "
             "default, uses _FloorScaler) and an UNPATCHED replica using bare sklearn "
             "StandardScaler, to confirm the fix prevents blow-up across the floor boundary and "
             "that the clamp decision matches the documented '< floor' semantics",
    "sane_threshold_definition": "200x the std of y (generous; the documented bug produced 1e6-1e8 scale errors)",
    "per_case": stress_results,
    "verdict": "PASS" if item4b_all_pass else "FAIL",
}

item4_pass = item4a_pass and item4b_all_pass

# =====================================================================================
# Write consolidated receipt
# =====================================================================================
overall_pass = all(v["verdict"] == "PASS" for v in verification.values())
overall_verdict = "confirmed" if overall_pass else "contested"

out = {
    "schema_version": 3,
    "id": "independent-verification-pc2-reverse-20260828",
    "kind": "evidence",
    "title": "Independent verification of PC2 realized coupling, reverse-direction generator, and the _FloorScaler fix",
    "status": overall_verdict,
    "notes": [
        "Independent verifier, second round: PC2 (coupling_kind='realized') and "
        "synthesize_bidirectional_coupling_pair/calibrate_matched_beta_r_to_p are NEW since the "
        "prior round (independent-verification-realized-coupling-20260828.json), which only "
        "covered PC1 and one-directional structure -- not just re-read here.",
        "Own scripts written fresh (omission/scripts/verify_pc2_reverse_independent_20260828.py), "
        "not a re-run of dev_pc2_realized_coupling_benchmark_20260828.py or "
        "dev_reverse_direction_20260828.py.",
    ],
    "issues": [],
    "plan": {},
    "verification": verification,
    "overall_verdict": overall_verdict.upper(),
    "per_item_verdict": {k: v["verdict"] for k, v in verification.items()},
    "generated_by": "omission/scripts/verify_pc2_reverse_independent_20260828.py",
    "generated_at": "2026-08-28",
}

out_path = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "independent-verification-pc2-reverse-20260828.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(out, indent=2))
print(f"\nOverall verdict: {out['overall_verdict']}")
print(f"Wrote {out_path}")
