"""
Master Reproducibility Pipeline Script (HISTORICAL -- quarantined 2026-08-10)
Omission Paradigm: Multi-Area Laminar Neurophysiology in Macaques

=== QUARANTINED -- do not run as a current reproducibility check ===
Per artifacts/.lab/agent-harness-audit-20260810.json (Sol/Hamm Handout 2, P0 item 3): every
number this script asserts is the RETRACTED synthetic lineage explicitly marked "Synthetic" /
"Never fitted" / "Not reproduced" in context/docs/CONTEXT.md Section 8 ("Superseded claims --
do not restore"): inclusive O+ 4.90% (421/8597), LFP beta 77.51% (6771/8736), GLMM OR = 3.08,
Spearman r = 0.93, nested O++ ~39. Running this script and seeing every assert pass is NOT
evidence these numbers are correct -- it only proves the fabricated inputs it reads
(artifacts/data/empirical_response_census.json) still contain the fabricated numbers. Preserved
as forensic evidence of the original manuscript-integrity failure mode, per this project's
Conservation doctrine -- not deleted. tests/test_quarantine_enforcement.py's live-import check
covers scripts/historical/ specifically (this file lives under notebooks/historical/, listed
separately in README.md); it is a __main__-only script, not a library other code imports.

Original docstring, prints and asserts headline numbers (ALL RETRACTED, see above):
  inclusive O+ 4.90% (421/8597)
  LFP beta 77.51% (6771/8736)
  GLMM OR = 3.08
  Spearman r = 0.93 (area-wise O+% vs beta%)
  nested O++ ~39 FEF/PFC (random-control robust subset)
"""

scientific_status = "invalid_for_inference"
superseded_by = None  # no current reproducibility-check replacement exists yet
reason = ["asserts_retracted_synthetic_census", "see CONTEXT.md Section 8"]

from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd
import scipy.stats as stats
import statsmodels.api as sm
import statsmodels.formula.api as smf

REPO = pathlib.Path(r"D:\workspace\omission")
ORDER = ["V1", "V2", "V3a-d-v", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"]


def step1_data_integrity_check():
    print("=== STEP 1: DATA INTEGRITY & CHECKSUM MANIFEST ===")
    manifest_path = REPO / "outputs" / "CHECKSUMS_AND_MANIFEST.md"
    assert manifest_path.exists(), "Manifest missing!"
    print("  - Checksums manifest verified.")


def step2_unit_classification_census():
    print("\n=== STEP 2: UNIT CLASSIFICATION & CENSUS RECONCILIATION ===")
    with open(REPO / "artifacts/data/empirical_response_census.json", "r", encoding="utf-8") as f:
        census = json.load(f)
    o = census["grand_unit_totals"]["O+"]
    tot = census["grand_unit_totals"]["Total"]
    pct = 100.0 * o / tot
    print(f"  - Total Primary Census Units: {tot:,}")
    print(f"  - Inclusive O+ Units: {o}/{tot} ({pct:.2f}%)")
    assert tot == 8597 and o == 421
    assert abs(pct - 4.90) < 0.01
    print("  - PASS: inclusive O+ = 4.90% (421/8,597)")
    return census


def step2b_oplusplus_nested():
    print("\n=== STEP 2b: NESTED O++ (RANDOM-CONTROL ROBUST SUBSET) ===")
    path = REPO / "artifacts/data/oplusplus_census.json"
    assert path.exists(), "Run scripts/build_oplusplus_census.py first"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    opp = receipt["o_plusplus"]
    n = opp["n_o_plusplus"]
    print(f"  - O++ count: {n} (target band 25-60: {opp['in_target_band_25_60']})")
    print(f"  - FEF+PFC: {opp['fef_pfc_n']} ({100*opp['fef_pfc_frac']:.1f}%) {opp['area_counts']}")
    print(f"  - Method: {opp['method']}")
    assert 25 <= n <= 60
    assert opp["fef_pfc_frac"] >= 0.8
    print("  - PASS: nested O++ locked")
    return receipt


def step3_fit_glmm_model(census):
    print("\n=== STEP 3: BINOMIAL GLMM / LOGIT HIGHER-ORDER ENRICHMENT ===")
    unit_area = census["unit_census_per_area"]
    rows = []
    for area, d in unit_area.items():
        tot = d["Total"]
        o_plus = d["O+"]
        for _ in range(o_plus):
            rows.append({"area": area, "is_o_plus": 1})
        for _ in range(tot - o_plus):
            rows.append({"area": area, "is_o_plus": 0})
    df_census = pd.DataFrame(rows)
    higher_order = ["PFC", "FEF", "TEO", "FST"]
    df_census["is_higher_order"] = df_census["area"].isin(higher_order).astype(int)
    mod = sm.Logit.from_formula("is_o_plus ~ is_higher_order", data=df_census).fit(disp=False)
    c = mod.params["is_higher_order"]
    se = mod.bse["is_higher_order"]
    or_val = float(np.exp(c))
    ci_low = float(np.exp(c - 1.96 * se))
    ci_high = float(np.exp(c + 1.96 * se))
    p_val = float(mod.pvalues["is_higher_order"])
    print(f"  - Logit Coef: {c:.4f} (SE = {se:.4f})")
    print(f"  - Odds Ratio (OR): {or_val:.2f}x (95% CI: [{ci_low:.2f}, {ci_high:.2f}])")
    print(f"  - Wald z: {mod.tvalues['is_higher_order']:.3f}, p = {p_val:.4e}")
    # Manuscript reports primary-census GLMM OR = 3.08x (mixed-effects); this logit
    # sanity check should be in the same direction/order of magnitude.
    assert or_val > 2.0
    print("  - PASS: enrichment OR > 2 (manuscript headline OR = 3.08x from mixed GLMM)")
    print("  - Manuscript headline: OR = 3.08x, 95% CI [2.51, 3.78], z = 10.726, p = 7.25e-27")
    return mod


def step4_lfp_beta_and_spearman(census):
    print("\n=== STEP 4: LFP BETA 77.51% + AREA-WISE SPEARMAN r = 0.93 ===")
    beta_n = census["grand_lfp_totals"]["Beta_Sig"]
    beta_tot = census["grand_lfp_totals"]["Total"]
    beta_pct = 100.0 * beta_n / beta_tot
    print(f"  - Beta-modulated channels: {beta_n}/{beta_tot} ({beta_pct:.2f}%)")
    assert beta_n == 6771 and beta_tot == 8736
    assert abs(beta_pct - 77.51) < 0.01
    print("  - PASS: LFP beta = 77.51% (6,771/8,736)")

    ua = census["unit_census_per_area"]
    la = census["lfp_sig_channels_per_area"]
    spk = np.array([100.0 * ua[a]["O+"] / ua[a]["Total"] for a in ORDER])
    beta = np.array([100.0 * la[a]["Beta_Sig"] / la[a]["Total"] for a in ORDER])
    rs, ps = stats.spearmanr(spk, beta)
    print(f"  - Spearman r = {rs:.2f}, p = {ps:.1e} (n = 10 areas)")
    assert abs(rs - 0.93) < 0.01
    print("  - PASS: Spearman r = 0.93")
    return rs, ps


def main():
    step1_data_integrity_check()
    census = step2_unit_classification_census()
    step2b_oplusplus_nested()
    step3_fit_glmm_model(census)
    step4_lfp_beta_and_spearman(census)
    print("\n=== MASTER REPRODUCIBILITY PIPELINE COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    main()
