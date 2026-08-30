"""Assemble the independent-verification receipt from the V1/V2/V4/V6 partials, and compute the
V5 power-metric audit from the paired gain_null / gain_PC2 deltas produced in V2.

V5 arithmetic performed here (nothing new is simulated):
  * "power" exactly as the original computed it: mean(pos_delta > quantile(null_delta, 0.95)),
    with both distributions taken at the SAME behavioural fidelity;
  * the FPR that same threshold implies (0.05 by construction) -- shown next to the FPR the
    original actually reported at that fidelity (1.00 at delta>0.05), to make explicit that the
    two numbers describe two different tests;
  * a threshold-free discrimination measure, AUC = P(pos_delta > null_delta) over the seed x seed
    product (Mann-Whitney), plus the PAIRED rate (same seed, same nuisance realisation), neither
    of which needs a threshold at all.

Run: python -m omission.scripts.verify_zhat3_assemble_receipt
"""
import json
from pathlib import Path

import numpy as np

from omission.scripts.verify_zhat3_common import clopper_pearson

LAB = Path(__file__).resolve().parents[1] / "artifacts" / ".lab"
v1 = json.loads((LAB / "_verify_zhat3_v1_partial.json").read_text())
v2 = json.loads((LAB / "_verify_zhat3_v2_partial.json").read_text())
v4 = json.loads((LAB / "_verify_zhat3_v4_partial.json").read_text())
v6 = json.loads((LAB / "_verify_zhat3_v6_partial.json").read_text())

# ---------------------------------------------------------------- V5 power-metric audit
R_GRID = v2["config"]["r_grid"]
power_audit = {}
for r in R_GRID:
    dn = np.array(v2["raw"]["gain_null"]["A"][str(r)]["delta_indep"])
    dp = np.array(v2["raw"]["gain_PC2"]["A"][str(r)]["delta_indep"])
    thr = float(np.quantile(dn, 0.95))
    auc = float(np.mean(dp[:, None] > dn[None, :]))
    paired = float(np.mean(dp > dn))
    k_fixed = int(np.sum(dn > 0.05))
    cp_fixed = clopper_pearson(k_fixed, len(dn))
    k_pow = int(np.sum(dp > thr))
    cp_pow = clopper_pearson(k_pow, len(dp))
    power_audit[str(r)] = {
        "null_delta_mean": float(dn.mean()), "pc2_delta_mean": float(dp.mean()),
        "original_style_power_threshold_null_q95": thr,
        "original_style_power": k_pow / len(dp),
        "original_style_power_clopper_pearson_95": list(cp_pow),
        "fpr_implied_by_that_same_threshold": 0.05,
        "fpr_actually_reported_at_delta_gt_0.05": k_fixed / len(dn),
        "fpr_at_0.05_clopper_pearson_95": list(cp_fixed),
        "auc_unpaired_P(pc2>null)": auc,
        "paired_rate_same_seed_pc2_gt_null": paired,
    }

# ---------------------------------------------------------------- V3 magnitude comparison
pure = v2["summary"]["pure_PC2"]["no_B"]
mag = {"genuine_coupling_delta_no_confound_pure_PC2": {
    "indep_delta_mean": pure["indep_delta_mean"], "indep_delta_sd": pure["indep_delta_sd"],
    "definition": "amp_gain=0, jitter=0, beta=1.5: Delta with a real P->R edge and NO confound"}}
for r in [0.4, 0.5, 0.6]:
    n = v2["summary"]["gain_null"]["A"][str(r)]
    p = v2["summary"]["gain_PC2"]["A"][str(r)]
    mag[f"r={r}"] = {
        "spurious_null_delta_mean": n["indep_delta_mean"],
        "spurious_null_delta_sd": n["indep_delta_sd"],
        "spurious_null_delta_range": [n["indep_delta_min"], n["indep_delta_max"]],
        "confounded_PC2_delta_mean": p["indep_delta_mean"],
        "increment_attributable_to_real_coupling": p["indep_delta_mean"] - n["indep_delta_mean"],
        "spurious_as_fraction_of_unconfounded_genuine_delta":
            n["indep_delta_mean"] / pure["indep_delta_mean"],
        "spurious_over_real_increment_ratio":
            n["indep_delta_mean"] / (p["indep_delta_mean"] - n["indep_delta_mean"]),
    }

# ---------------------------------------------------------------- transition location
trans = {}
for con, label in [("A", "exact_r_linear"), ("B", "sluggish_AR1_observation")]:
    rows = v2["summary"]["gain_null"][con]
    key = "rule_A_indep_gt_0.05"
    seq = [(rows[str(r)]["achieved_r_mean"], rows[str(r)][key]["fpr"],
            rows[str(r)][key]["clopper_pearson_95"], rows[str(r)]["indep_delta_mean"])
           for r in R_GRID]
    below10 = next((a for a, f, _c, _d in seq if f < 0.10), None)
    below05 = next((a for a, f, _c, _d in seq if f < 0.05), None)
    trans[label] = {
        "fpr_vs_achieved_r": [{"achieved_r": a, "fpr": f, "clopper_pearson_95": c,
                                "null_delta_mean": d} for a, f, c, d in seq],
        "lowest_achieved_r_with_fpr_below_0.10": below10,
        "lowest_achieved_r_with_fpr_below_0.05": below05,
        "highest_achieved_r_still_at_fpr_1.00": max(
            [a for a, f, _c, _d in seq if f >= 1.0], default=None),
    }

verification = {
    "V1_gain_null_FPR_reproduces_on_fresh_seeds": {
        "verdict": "PASS",
        "decision_rules_used": {
            "rule_A": "delta > 0.05 (the original's convention)",
            "rule_A0": "delta > 0 (most lenient conceivable)",
            "rule_B": "percentile bootstrap over trials of held-out Delta; detect if 95% CI "
                      "lower bound > 0",
            "rule_C": "within-dataset lag-feature trial-permutation null (200 permutations), "
                      "one-sided p < 0.05 -- the ONLY rule here an analyst could run on real "
                      "data without knowing the confound's magnitude",
        },
        "gain_null_FPR_all_four_rules_all_three_observable_tiers": 1.00,
        "gain_null_FPR_clopper_pearson_95": [0.8628, 1.0],
        "oracle_positive_control_gain_null_FPR": 0.00,
        "oracle_gain_null_delta_mean_orig_path": v1["summary"]["gain_null"]["oracle"]["orig_delta_mean"],
        "combined_null_FPR_observable_tiers_all_rules": 1.00,
        "original_vs_independent_estimator_agreement": (
            "the original Ridge/5-fold/sklearn path and a from-scratch OLS/10-fold/numpy path "
            "agree to <0.003 in mean Delta in every scenario x tier cell"),
        "note": "the conclusion does not depend on the arbitrary 0.05 cut: at the gain confound "
                "the spurious Delta is ~0.55, more than 8 sigma above it, and every rule fires "
                "on every seed.",
    },
    "V2_independent_behavioural_fidelity_sweep": {
        "verdict": "PASS (with a refinement: the transition sits near r~0.90-0.92, not 0.95)",
        "simulate_behavioral_proxy_was_NOT_used": True,
        "constructions": {
            "exact_r_linear": "Gram-Schmidt; achieved finite-sample r equals target exactly "
                              "(achieved_r_sd = 0.0000 at every grid point -- measured, not assumed)",
            "sluggish_AR1_observation": "noisy read of the gain state through a first-order lag "
                                        "(lam=0.5); noise sd found by bisection on the ACHIEVED "
                                        "empirical r",
        },
        "transition": trans,
        "agreement_between_constructions": (
            "the two mechanistically different proxies give FPR curves that agree within one "
            "seed at every grid point, so the result is a property of proxy FIDELITY, not of "
            "the noise mechanism"),
    },
    "V3_is_r_0.4_to_0.6_unambiguously_miscalibrated": {
        "verdict": "PASS -- yes, unambiguously",
        "fpr_and_exact_intervals": {
            str(r): {
                "fpr": v2["summary"]["gain_null"]["A"][str(r)]["rule_A_indep_gt_0.05"]["fpr"],
                "k_of_n": [v2["summary"]["gain_null"]["A"][str(r)]["rule_A_indep_gt_0.05"]["k"],
                            v2["summary"]["gain_null"]["A"][str(r)]["rule_A_indep_gt_0.05"]["n"]],
                "clopper_pearson_95":
                    v2["summary"]["gain_null"]["A"][str(r)]["rule_A_indep_gt_0.05"]["clopper_pearson_95"],
                "bootstrap_rule_B_fpr":
                    v2["summary"]["gain_null"]["A"][str(r)]["rule_B_boot_ci_excludes_zero"]["fpr"],
                "permutation_rule_C_fpr":
                    v2["summary"]["gain_null"]["A"][str(r)]["rule_C_perm_p_lt_0.05"]["fpr"],
            } for r in [0.4, 0.5, 0.6]},
        "lower_bound_of_exact_interval": 0.8628,
        "far_above_0.20": True,
        "magnitude_comparison": mag,
        "plain_statement": (
            "At r=0.4-0.6 every one of 25 fresh seeds is a false positive under all three "
            "decision rules; the exact 95% interval on the FPR is [0.863, 1.000], i.e. its LOWER "
            "bound is more than four times the 0.20 benchmark and more than seventeen times a "
            "nominal 0.05. The spurious Delta (0.30-0.44) is 42-60% of the entire Delta produced "
            "by genuine coupling with no confound at all (0.731), and 1.4x (r=0.6), 2.6x (r=0.5) "
            "and 4.8x (r=0.4) LARGER than the increment that genuine coupling actually adds on "
            "top of the confound (0.217, 0.145, 0.092). Spurious effects are not merely "
            "comparable in size to real ones here -- at every fidelity in this regime they are "
            "bigger."),
    },
    "V4_Zhat3_does_not_satisfy_P4_unlock_criteria": {
        "verdict": "FAIL for every observable tier (i.e. the unlock criteria are NOT met) -- "
                   "which confirms the claim under audit",
        "criteria": {
            "a_timing_confound_calibrated": {
                "Zhat-2_FPR_delta_gt_0.05": v1["summary"]["timing_null"]["Zhat-2_plus_timing_gain"]["rule_A_orig_delta_gt_0.05"]["fpr"],
                "status": "MET for Zhat-2 (0/25)"},
            "b_gain_confound_calibrated": {
                "Zhat-2_FPR": 1.0, "Zhat-2+B(r<=0.6)_FPR": 1.0,
                "status": "NOT MET -- 25/25 at every observable tier and at every plausible B fidelity"},
            "c_combined_confound_calibrated": {
                "Zhat-2_FPR": v1["summary"]["combined_null"]["Zhat-2_plus_timing_gain"]["rule_A_orig_delta_gt_0.05"]["fpr"],
                "status": "NOT MET -- 25/25"},
            "d_slow_shared_state_calibrated": {
                "reading_of_the_generator": (
                    "amp_phi=0.95 makes true_gain an AR(1) random walk ACROSS TRIALS "
                    "(realized_coupling_generator lines 116-121), so the gain-null scenario IS a "
                    "slow shared state -- that reading is fair and is confirmed by reading the "
                    "generator source. It is however the SAME process that defines criterion (b), "
                    "so testing (d) only through it would be circular."),
                "verifier_added_distinct_scenario": (
                    "slow_timing_null: true_jitter supplied as an AR(1) phi=0.95 series (sd 8 ms) "
                    "with amp_gain=0 -- a slow shared state acting on TIMING rather than gain"),
                "slow_timing_null_Zhat-2_FPR": v1["summary"]["slow_timing_null"]["Zhat-2_plus_timing_gain"]["rule_A_orig_delta_gt_0.05"]["fpr"],
                "slow_timing_null_Zhat-0_FPR": v1["summary"]["slow_timing_null"]["Zhat-0_design_only"]["rule_A_orig_delta_gt_0.05"]["fpr"],
                "status": "MET for Zhat-2 (1/25) on the slow-TIMING variant; NOT MET for the "
                          "slow-GAIN variant, and NOT MET for Zhat-0/1 even on slow timing (5/25)"},
            "e_useful_PC2_detection_power": {
                "status": "NOT INTERPRETABLE under gain confounding -- see V5; the statistic does "
                          "not even order the two conditions correctly (AUC below 0.5 at low B "
                          "fidelity)"},
            "f_correct_directional_asymmetry": {
                "status": "NOT MET -- and it fails in the most damaging way",
                "null_ref_no_coupling_in_either_direction_under_gain_confound": {
                    "Zhat-2_forward_delta_mean": v4["summary"]["null_ref"]["Zhat-2"]["fwd_delta_mean"],
                    "Zhat-2_A_mean": v4["summary"]["null_ref"]["Zhat-2"]["A_mean"],
                    "Zhat-2_forward_detection_rate_delta_gt_0.05":
                        v4["summary"]["null_ref"]["Zhat-2"]["fwd_gt_0.05"],
                    "Zhat-2+B(r=0.6)_forward_detection_rate_delta_gt_0.05":
                        v4["summary"]["null_ref"]["Zhat-2+B(r=0.6)"]["fwd_gt_0.05"],
                    "oracle_forward_detection_rate_delta_gt_0.05":
                        v4["summary"]["null_ref"]["oracle"]["fwd_gt_0.05"],
                    "interpretation": (
                        "with NO coupling in either direction, Zhat-2 reports a positive P->R "
                        "asymmetry of +0.223 -- 54% of the +0.417 it reports when a real P->R edge "
                        "IS present -- and declares P->R coupling on 20/20 seeds. The oracle "
                        "declares it on 0/20. The asymmetry statistic is therefore not "
                        "confound-free: it manufactures a directional claim from a gain state.")},
                "R_to_P_only_wrong_direction_also_declared": {
                    "Zhat-2_forward_detection_rate": v4["summary"]["R_to_P_only"]["Zhat-2"]["fwd_gt_0.05"],
                    "note": "when the TRUE edge is R->P, Zhat-2 additionally declares the "
                            "non-existent P->R edge on 16/20 seeds"},
                "sign_of_A_alone_is_recovered": (
                    "the SIGN of A is correct 20/20 in both single-direction scenarios; it is the "
                    "null case that breaks the criterion, so 'correct directional asymmetry' holds "
                    "only conditional on already knowing coupling exists"),
            },
        },
        "joint_verdict": "no observable tier -- Zhat-0, Zhat-1, Zhat-2, or Zhat-2+B at r<=0.6 -- "
                          "satisfies (b), (c) and (f) simultaneously; the criteria are jointly "
                          "unmet on fresh seeds.",
    },
    "V5_power_metric_validity": {
        "verdict": "CONFIRMED -- the original's reasoning defect is real; the power numbers as "
                   "reported are misleading",
        "what_the_original_did": (
            "dev_zhat3_behavioral_bridge_20260828.py line 68 computes FPR as "
            "mean(null_delta > 0.05), and line 69 computes power as "
            "mean(pos_delta > quantile(null_delta, 0.95)). The two numbers printed side by side "
            "in the same row of results are therefore two DIFFERENT tests with two DIFFERENT "
            "thresholds. dev_zhat_bridge_benchmark_20260828.py does the same thing with "
            "null_mean + 2*null_sd (lines 240-249)."),
        "why_it_is_misleading": (
            "(1) the power threshold is derived from the true null Delta distribution AT THE SAME "
            "confound magnitude, which no real analysis can know -- it is oracle calibration "
            "smuggled into a row whose headline claim is that the observable procedure is "
            "uncalibrated; (2) any threshold that yields the quoted power has FPR = 0.05 BY "
            "CONSTRUCTION, not the 1.00 reported one column to its left, so the pair (FPR=1.00, "
            "power=0.95) cannot describe one operating point of one test; (3) at low B fidelity "
            "the statistic does not even ORDER the conditions correctly."),
        "decisive_number": (
            "at B fidelity r=0 the null Delta mean (0.5550) EXCEEDS the true-coupling Delta mean "
            "(0.5381): adding a genuine P->R edge DECREASES the statistic. AUC = "
            f"{power_audit['0.0']['auc_unpaired_P(pc2>null)']:.3f} (< 0.5) and the paired "
            f"same-seed rate is {power_audit['0.0']['paired_rate_same_seed_pc2_gt_null']:.2f}. "
            "The original's own receipt shows the same inversion (0.5537 vs 0.5647) and still "
            "reports 'power = 0.10' there rather than flagging it."),
        "per_fidelity_audit": power_audit,
        "what_should_be_reported_instead": (
            "a threshold-free discrimination measure (AUC / paired rate) alongside the FPR at the "
            "SAME decision rule; or power computed at the threshold that achieves nominal FPR, "
            "with the explicit statement that that threshold is unobtainable without oracle "
            "knowledge of the confound."),
        "scope_note": "this criticises the REPORTING, not the arithmetic: every number in the "
                      "original receipts recomputed correctly here.",
        "counter_argument_stated_in_full": (
            "At r=0.6 the threshold-free AUC between the null and true-coupling Delta "
            "distributions is 1.000 and the paired same-seed rate is 25/25. So the Delta "
            "statistic DOES carry information about coupling at plausible fidelity -- the "
            "failure is calibration, not information. This is the strongest available argument "
            "against the negative conclusion and is stated here rather than buried. It does not "
            "rescue identification, because separating the two distributions requires a matched "
            "null generated at the SAME confound magnitude, which on real data would have to be "
            "known or simulated -- exactly the oracle knowledge whose absence defines the "
            "problem. The correct phrasing of the negative result is therefore 'not identifiable "
            "without a validated matched null', not 'the statistic contains no signal'."),
    },
    "V6_verifier_added_adversarial_probe_stronger_observable_proxy": {
        "verdict": "CONCERN RESOLVED IN FAVOUR OF THE ORIGINAL CONCLUSION",
        "motivation": (
            "the three coded tiers do not exhaust observability. Because the gain state is AR(1) "
            "phi=0.95 ACROSS TRIALS, an analyst can denoise it by averaging each trial's pre-event "
            "baseline amplitude with its NEIGHBOURS' -- fully observable, same material Zhat-1 "
            "already uses. If that worked, the negative conclusion would be overstated."),
        "result": {
            "proxy_fidelity_r_with_true_gain": v6["summary"]["observable_gain_proxy_fidelity"],
            "single_trial_amplitude_FPR": v6["summary"]["amp_raw"]["gain_null_FPR_delta_gt_0.05"],
            "neighbour_smoothed_amplitude_FPR": v6["summary"]["amp_smooth"]["gain_null_FPR_delta_gt_0.05"],
            "leave_one_out_smoothed_FPR": v6["summary"]["amp_smooth_loo"]["gain_null_FPR_delta_gt_0.05"],
            "cubic_in_single_trial_amplitude_FPR": v6["summary"]["amp_raw_cubic"]["gain_null_FPR_delta_gt_0.05"],
        },
        "interpretation": (
            "neighbour smoothing more than doubles the observable proxy's fidelity "
            "(r 0.25 -> 0.62, leave-one-out 0.60) -- a genuine improvement the original never "
            "tried -- and the gain-null FPR is STILL 1.00 (25/25, exact 95% interval "
            "[0.863, 1.000]). Its spurious Delta (0.280) lands exactly where the independent "
            "fidelity curve predicts for r~0.6 (0.304), an out-of-sample consistency check "
            "between two separately-seeded experiments. Adding cubic capacity in the raw "
            "amplitude changes nothing (0.554 vs 0.551), which separates the failure mode: this "
            "is errors-in-variables in the proxy, not insufficient functional form."),
    },
}

concerns = [
    {"id": "C1", "severity": "moderate",
     "text": "The trial-permutation decision rule (rule_C) is itself miscalibrated on the "
             "NON-gain nulls: it fires on 11-13/25 seeds under timing_null and 3-6/25 even at "
             "the oracle tier. A flat shuffle is not exchangeable against AR(1)/jitter row "
             "structure (omission-statistics: 'permutation exchangeability is the caller's "
             "responsibility'). It is reported here only as a second, analyst-applicable rule "
             "that ALSO gives FPR=1.00 under gain confounding, not as a recommended test."},
    {"id": "C2", "severity": "moderate",
     "text": "The exact FPR of Zhat-1/Zhat-2 is not a law of nature: it depends on the "
             "generator's noise_sd and baseline_amp, which together fix the single-trial "
             "amplitude proxy's fidelity (r~0.25 here). The load-bearing, parameter-light result "
             "is the fidelity->calibration CURVE (calibration needs r~0.90+), which V2 and V6 "
             "reproduce from two different directions. Any claim should be phrased in terms of "
             "required proxy fidelity, not in terms of 'Zhat-2 fails'."},
    {"id": "C3", "severity": "low",
     "text": "The transition sits at achieved r~0.90-0.92 in this verification, not at 0.95. The "
             "original's coarse grid (0.8 -> 0.95) could not locate it. This does not move the "
             "conclusion (0.4-0.6 is far below either value) but the constant 0.95 should not be "
             "quoted as the threshold."},
    {"id": "C4", "severity": "low",
     "text": "Everything here is synthetic. Whether the real corpus's LFP->spike setting actually "
             "contains a latent multiplicative gain state of comparable strength (amp_gain=0.6, "
             "amp_phi=0.95) is an empirical question this benchmark does not answer. The negative "
             "conclusion is correctly stated as 'not identifiable under a gain confound of this "
             "kind', and must not silently become 'there is no LFP->spike coupling'."},
    {"id": "C6", "severity": "moderate",
     "text": "The negative conclusion should be stated as a CALIBRATION failure, not an "
             "information failure: at r=0.6 the null-vs-coupling AUC is 1.000. Wording that "
             "implies the distributed-lag statistic is blind to real coupling would overstate "
             "the finding. What is unavailable is a usable decision threshold, because forming "
             "one requires a matched null at the true confound magnitude."},
    {"id": "C5", "severity": "low",
     "text": "n=25 seeds gives an exact upper bound of 0.137 on a 0/25 FPR, so 'FPR=0.00' at "
             "r>=0.92 is consistent with a true FPR up to ~0.14. Well-calibrated is not "
             "demonstrated at these seed counts; catastrophically-miscalibrated is (25/25 has "
             "lower bound 0.863)."},
]

payload = {
    "schema_version": 3,
    "id": "independent-verification-zhat3-failure-20260828",
    "kind": "evidence",
    "title": "Independent adversarial verification of the Zhat-3 negative conclusion: no "
             "observable nuisance tier identifies LFP->spike directionality against a latent "
             "gain confound",
    "status": "provisional",
    "date": "2026-08-28",
    "role": "independent verification (fresh seeds, re-implemented estimator, own decision rules)",
    "claim_under_audit": (
        "The empirically plausible observable-proxy fidelity regime (r ~ 0.4-0.6 with the latent "
        "gain state) remains far inside the catastrophically-miscalibrated region, so no "
        "observable nuisance tier permits identification of LFP->spike directionality against a "
        "latent gain confound."),
    "overall_verdict": "SUPPORTED. Independently reproduced on disjoint seeds, with a "
                        "from-scratch estimator, under four decision rules, and against a "
                        "stronger observable gain proxy than the original ever tried. Two "
                        "refinements: the calibration transition is at r~0.90-0.92 rather than "
                        "0.95, and the original's PSHOWN power numbers are not interpretable as "
                        "reported (V5).",
    "independence": {
        "seed_blocks": {"V1": "z 3000-3024 / priv 3500000-3500024",
                         "V2_V3": "z 4000-4024 / priv 4500000-4500024",
                         "V4": "z 5000-5019 / priv 5500000-5500019",
                         "V6": "z 6000-6024 / priv 6500000-6500024",
                         "originals_for_contrast": "z 0-19 / priv +700000 or +960000"},
        "estimator": "held-out Delta re-implemented from scratch: 10-fold CV with an own fold "
                      "dealer (not sklearn.KFold), ordinary least squares via numpy.linalg.lstsq "
                      "(not Ridge alpha=1), no feature scaling (not _FloorScaler); trial-level "
                      "features and the cross-fit matched-filter timing estimate also "
                      "re-derived. The original path was run alongside purely for comparison.",
        "proxy": "simulate_behavioral_proxy was NOT called; two independent constructions were "
                  "written and their achieved r MEASURED at every grid point.",
        "intervals": "Clopper-Pearson exact binomial throughout (omission-statistics)",
        "inferential_unit": "one synthetic dataset (seed) = one independent replicate for every "
                             "FPR/power proportion; trials are the unit only inside the "
                             "per-dataset bootstrap.",
    },
    "verification": verification,
    "concerns": concerns,
    "scripts": [
        "omission/scripts/verify_zhat3_common.py",
        "omission/scripts/verify_zhat3_v1_calibration.py",
        "omission/scripts/verify_zhat3_v2_fidelity.py",
        "omission/scripts/verify_zhat3_v4_direction.py",
        "omission/scripts/verify_zhat3_v6_adversarial_proxy.py",
        "omission/scripts/verify_zhat3_assemble_receipt.py",
    ],
    "partial_receipts": [
        "omission/artifacts/.lab/_verify_zhat3_v1_partial.json",
        "omission/artifacts/.lab/_verify_zhat3_v2_partial.json",
        "omission/artifacts/.lab/_verify_zhat3_v4_partial.json",
        "omission/artifacts/.lab/_verify_zhat3_v6_partial.json",
    ],
    "audited_receipts": [
        "omission/artifacts/.lab/zhat-oracle-bridge-benchmark-20260828.json",
        "omission/artifacts/.lab/zhat3-behavioral-bridge-fidelity-sweep-20260828.json",
    ],
    "config": {"n_trials": 300, "rho": 0.5, "delay_ms": 30.0, "coupling_kind": "realized",
                "beta_positive_control": 1.5, "amp_gain": 0.6, "amp_phi": 0.95,
                "n_seeds": {"V1": 25, "V2_V3": 25, "V4": 20, "V6": 25},
                "wall_clock_s": {"V1": v1["config"]["wall_clock_s"],
                                  "V2": v2["config"]["wall_clock_s"],
                                  "V4": v4["config"]["wall_clock_s"],
                                  "V6": v6["config"]["wall_clock_s"]}},
    "full_tables": {"V1_calibration": v1["summary"], "V1_nuisance_fidelity": v1["nuisance_fidelity"],
                     "V2_V3_fidelity_sweep": v2["summary"], "V4_direction": v4["summary"],
                     "V6_adversarial_proxy": v6["summary"]},
}

out = LAB / "independent-verification-zhat3-failure-20260828.json"
out.write_text(json.dumps(payload, indent=2))
print(f"Wrote {out}")
for r in ["0.0", "0.4", "0.6", "0.9", "0.92"]:
    a = power_audit[r]
    print(f"  r={r:5s} null_d={a['null_delta_mean']:+.4f} pc2_d={a['pc2_delta_mean']:+.4f} "
          f"AUC={a['auc_unpaired_P(pc2>null)']:.3f} paired={a['paired_rate_same_seed_pc2_gt_null']:.2f} "
          f"orig_style_power={a['original_style_power']:.2f} fpr@0.05={a['fpr_actually_reported_at_delta_gt_0.05']:.2f}")
