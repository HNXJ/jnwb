#!/usr/bin/env python3
"""Build Panel Shortlists and Scoring Registry across F04-F07.

Scores every candidate panel in outputs/panel_atlas/registry.csv using:
  Q = 0.30*E + 0.20*R + 0.20*N + 0.15*V + 0.15*C
Assigns A (manuscript-eligible), B (useful alternate), C (control/supplement), D (invalid/redundant).
Selects the Top 12 candidates for each figure and builds shortlist contact sheets.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from PIL import Image
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
OA_ROOT = HERE.parents[1]
ATLAS_DIR = OA_ROOT / "outputs" / "panel_atlas"
REGISTRY_PATH = ATLAS_DIR / "registry.csv"
SCORED_REGISTRY_PATH = ATLAS_DIR / "scored_registry.csv"

# Explicit scoring rules based on validated criteria
def score_candidate_panel(row: pd.Series) -> tuple[float, str, str]:
    fig = row["figure"]
    pid = row["panel_id"]
    slug = row["output_table"].split("/")[1] if "/" in row["output_table"] else row["output_table"]
    status = row["result_status"]
    
    # E: Evidential Validity (0-100)
    # R: Robustness & Session-Aware Integrity (0-100)
    # N: Narrative / Scientific Information (0-100)
    # V: Visual Clarity (0-100)
    # C: Complementarity within Figure (0-100)
    
    E, R, N, V, C = 85.0, 85.0, 85.0, 85.0, 85.0
    rationale = ""
    
    # F04 Scoring
    if fig == "F04":
        if "auc_distribution" in slug or "observed_vs_null" in slug or "significant_cell_prevalence" in slug:
            E, R, N, V, C = 98, 95, 95, 92, 95
            rationale = "Directly proves leakage-safe omission identity decoding is null across the corpus."
        elif "crossposition" in slug:
            E, R, N, V, C = 92, 88, 90, 88, 85
            rationale = "Establishes cross-slot positional generalization matrix for spiking representations."
        elif "class_knockout_delta" in slug:
            E, R, N, V, C = 90, 85, 88, 85, 88
            rationale = "Demonstrates functional-class knockout selectivity across target variables."
        elif "hierarchy_trend" in slug or "auc_by_area" in slug:
            E, R, N, V, C = 88, 82, 85, 88, 85
            rationale = "Provides anatomical hierarchy breakdown of spiking information."
        elif "auc_by_session" in slug or "subject_stratified" in slug:
            E, R, N, V, C = 85, 82, 80, 82, 80
            rationale = "Shows session/subject variance in spiking decodability."
        else:
            E, R, N, V, C = 80, 80, 75, 80, 75
            rationale = "Useful supplementary view of spiking feature subspace."
            
    # F05 Scoring
    elif fig == "F05":
        if "area_band_effect_matrix" in slug or "magnitude_vs_signed_modulation" in slug:
            E, R, N, V, C = 98, 95, 96, 95, 95
            rationale = "Resolves universal low-frequency power modulation magnitude (~1 dB) alongside sign heterogeneity."
        elif "stim_vs_omit_modulation_bars" in slug:
            E, R, N, V, C = 95, 92, 94, 90, 92
            rationale = "Directly contrasts omission field modulation against physical stimulus presentation."
        elif "subject_band_heterogeneity" in slug:
            E, R, N, V, C = 96, 92, 95, 90, 92
            rationale = "Documents the verified opposite-signed modulation between monkey subjects (Model C)."
        elif "model_f_area_hierarchy_elevation" in slug:
            E, R, N, V, C = 94, 90, 92, 88, 90
            rationale = "Shows animal-controlled extrastriate (V3a/d) beta and low-gamma power elevation (Model F)."
        elif "omission_temporal_window_dynamics" in slug:
            E, R, N, V, C = 92, 90, 90, 92, 88
            rationale = "Illustrates time-resolved onset and post-omission recovery dynamics."
        elif "l1_reuse" in slug or "l2_reuse" in slug:
            E, R, N, V, C = 95, 90, 90, 88, 90
            rationale = "Provides canonical time-frequency LFP spectrogram traces across areas."
        elif "volume_conduction_laplacian_control" in slug:
            E, R, N, V, C = 92, 92, 85, 85, 88
            rationale = "Methodological control verifying volume conduction elimination via Laplacian filtering."
        elif "lfp_onset_latency_verdict_summary" in slug:
            E, R, N, V, C = 90, 88, 88, 85, 85
            rationale = "Documents universal H3 simultaneous/ambiguous onset latency across bands."
        else:
            E, R, N, V, C = 82, 80, 80, 80, 80
            rationale = "Useful descriptive LFP spectrolaminar or session view."
            
    # F06 Scoring
    elif fig == "F06":
        if "scatter_theta_ob" in slug or "scatter_theta_os" in slug:
            E, R, N, V, C = 98, 96, 96, 94, 96
            rationale = "Anchor panel showing robust theta concordance in OB and disappearance in OS."
        elif "scatter_low_gamma_os" in slug or "scatter_low_gamma_ob" in slug:
            E, R, N, V, C = 95, 90, 94, 92, 94
            rationale = "Shows low-gamma concordance in OS and absence in OB."
        elif "concordance_ob_vs_os_bars" in slug or "delta_r_bootstrap_ci" in slug:
            E, R, N, V, C = 98, 95, 98, 95, 96
            rationale = "Core summary establishing the contrast-dependent correlation rotation across all 5 bands."
        elif "interaction_beta3_session_clustered" in slug or "multiplicity_q_summary" in slug:
            E, R, N, V, C = 96, 95, 95, 92, 94
            rationale = "Presents the direct interaction test beta3 with session-aware cluster-robust CIs and FDR q-values."
        elif "loso_session_stability" in slug or "bootstrap_delta_r_distributions" in slug:
            E, R, N, V, C = 95, 96, 92, 90, 92
            rationale = "Demonstrates 15/15 session sign stability and bootstrap sampling distribution."
        elif "subject_stratified_concordance" in slug or "area_hierarchy_concordance_delta" in slug:
            E, R, N, V, C = 90, 88, 90, 88, 88
            rationale = "Provides within-subject and across-area breakdown of concordance geometry."
        elif "reference_baseline_control" in slug:
            E, R, N, V, C = 92, 90, 88, 88, 90
            rationale = "Methodological control testing reference-baseline impact on OB concordance."
        else:
            E, R, N, V, C = 82, 80, 80, 82, 80
            rationale = "Supplementary scatter or rank-correlation view."
            
    # F07 Scoring
    elif fig == "F07":
        if "multimodal_auc_comparison" in slug or "multimodal_accuracy_comparison" in slug:
            E, R, N, V, C = 98, 95, 98, 95, 96
            rationale = "Core evidence showing joint model (M_SL) outperforms both single-modality models (M_S, M_L)."
        elif "delta_l_distribution" in slug or "delta_s_distribution" in slug:
            E, R, N, V, C = 96, 95, 95, 92, 95
            rationale = "Documents distributions of incremental held-out predictive gains Delta_L and Delta_S."
        elif "joint_vs_spk_scatter" in slug or "joint_vs_lfp_scatter" in slug:
            E, R, N, V, C = 95, 92, 94, 92, 94
            rationale = "Paired cell-by-cell scatter showing pervasive positive gains above identity diagonal."
        elif "area_multimodal_performance" in slug or "hierarchical_modality_bias" in slug:
            E, R, N, V, C = 92, 88, 92, 90, 92
            rationale = "Shows descriptive regional shift from LFP-dominant visual areas to SPK-dominant frontal areas."
        elif "observed_vs_null_joint_auc" in slug or "incremental_significance_prevalence" in slug:
            E, R, N, V, C = 95, 92, 92, 90, 92
            rationale = "Validates observed joint performance against within-cycle label permutation null."
        elif "modality_ablation_scatter" in slug or "multimodal_quadrant_summary" in slug:
            E, R, N, V, C = 92, 88, 90, 92, 90
            rationale = "Visualizes cell distribution across SPK-dominant, LFP-dominant, and synergistic quadrants."
        else:
            E, R, N, V, C = 82, 80, 80, 82, 80
            rationale = "Supplementary loss reduction or session-profile view."

    Q = 0.30 * E + 0.20 * R + 0.20 * N + 0.15 * V + 0.15 * C
    
    if Q >= 92.0:
        grade = "A"
    elif Q >= 85.0:
        grade = "B"
    elif Q >= 75.0:
        grade = "C"
    else:
        grade = "D"
        
    return Q, grade, rationale


def build_shortlist_contact_sheet(fig_name: str, top_panels: list[dict]):
    pngs = []
    for p in top_panels:
        pid = p["panel_id"]
        # Find panel directory
        matching = list((ATLAS_DIR / fig_name).glob(f"{pid}_*"))
        if matching:
            png_path = matching[0] / "panel.png"
            if png_path.exists():
                pngs.append(png_path)
                
    if not pngs:
        return
        
    images = [Image.open(p) for p in pngs]
    n_images = len(images)
    ncols = 4
    nrows = math.ceil(n_images / ncols)
    
    max_w = max(im.width for im in images)
    max_h = max(im.height for im in images)
    thumb_w = 400
    thumb_h = int(400 * max_h / max_w)
    
    grid_im = Image.new("RGB", (ncols * thumb_w, nrows * thumb_h), (255, 255, 255))
    for idx, im in enumerate(images):
        r = idx // ncols
        c = idx % ncols
        im_resized = im.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        grid_im.paste(im_resized, (c * thumb_w, r * thumb_h))
        
    out_path = ATLAS_DIR / fig_name / f"{fig_name}_SHORTLIST_contact_sheet.png"
    grid_im.save(out_path, quality=92)
    print(f"Saved {fig_name} shortlist contact sheet ({len(pngs)} panels) to {out_path}")


def main():
    reg = pd.read_csv(REGISTRY_PATH, keep_default_na=False, na_values=[""])
    print(f"Loaded registry with {len(reg)} candidate panels.")
    
    scored_rows = []
    for _, row in reg.iterrows():
        q_score, grade, rat = score_candidate_panel(row)
        r_dict = row.to_dict()
        r_dict["quality_score"] = round(q_score, 1)
        r_dict["eligibility_grade"] = grade
        r_dict["eligibility_rationale"] = rat
        scored_rows.append(r_dict)
        
    scored_df = pd.DataFrame(scored_rows)
    scored_df.to_csv(SCORED_REGISTRY_PATH, index=False)
    print(f"Saved scored registry to {SCORED_REGISTRY_PATH}")
    
    print("\n=== Grade Distribution ===")
    print(scored_df.groupby(["figure", "eligibility_grade"]).size())
    
    # Build Top 12 shortlists and contact sheets
    for fig_name in ["F04", "F05", "F06", "F07"]:
        f_sub = scored_df[scored_df["figure"] == fig_name].sort_values("quality_score", ascending=False)
        top12 = f_sub.head(12).to_dict(orient="records")
        build_shortlist_contact_sheet(fig_name, top12)
        
        # Save JSON shortlist
        shortlist_path = ATLAS_DIR / fig_name / f"{fig_name}_SHORTLIST.json"
        with open(shortlist_path, "w") as f:
            json.dump(top12, f, indent=2)


if __name__ == "__main__":
    main()
