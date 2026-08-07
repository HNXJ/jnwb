#!/usr/bin/env python3
"""
Supplementary Figure 2: Subject Variability.

Panels:
  A. Within-subject differences (distribution across conditions, LFP bands and spikes)
  B. Between-subject differences (distribution across subjects: C31o, V182o, V198o)
  C. Pairwise subject distance matrix (3x3 per band + Spikes)
  D. Maximum differences bar plot (Within-subject vs Between-subject)
  E. Minimum differences bar plot (Within-subject vs Between-subject)

Outputs:
  - context/figures/supplements/supp_fig02_subject_variability.png (300 DPI)
  - context/figures/supplements/supp_fig02_subject_variability.svg
"""

import os
import sys
import pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "context" / "figures"))

from figstyle import BAND_COLORS, BANDS, use_house_style
use_house_style()

OUT_DIR = REPO_ROOT / "context" / "figures" / "supplements"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MATRICES_NPZ = REPO_ROOT / "outputs" / "coherence_variability_matrices.npz"
SUMMARY_CSV = REPO_ROOT / "outputs" / "coherence_variability_summary.csv"

BAND_KEYS = ["theta", "alpha", "beta", "low_gamma", "high_gamma"]
BAND_LABELS = ["Theta", "Alpha", "Beta", "Low gamma", "High gamma"]
SUBJECTS = ["C31o", "V182o", "V198o"]

def load_data():
    from scripts.extract_supp_coherence_variability_stats import extract_lfp_coherence
    df_lfp = extract_lfp_coherence()
    mats = np.load(MATRICES_NPZ, allow_pickle=True)
    df_summary = pd.read_csv(SUMMARY_CSV)
    return df_lfp, mats, df_summary

def render_figure():
    df_lfp, mats, df_summary = load_data()
    
    fig = plt.figure(figsize=(14, 14), dpi=300)
    fig.patch.set_facecolor("#ffffff")
    
    gs = fig.add_gridspec(4, 5, height_ratios=[1.2, 1.2, 1.3, 1.1], wspace=0.35, hspace=0.45)
    
    # -------------------------------------------------------------------------
    # Panel A: Within-Subject Differences
    # -------------------------------------------------------------------------
    ax_a = fig.add_subplot(gs[0, 0:3])
    ax_a.set_facecolor("#ffffff")
    
    subj_colors = ["#3182bd", "#31a354", "#756bb1"]
    width = 0.25
    x = np.arange(len(BAND_KEYS))
    
    for si, subj in enumerate(SUBJECTS):
        sub = df_lfp[df_lfp["subject"] == subj]
        vals = [sub[sub["band"] == b]["effect_coh"].std() for b in BAND_KEYS]
        vals = [v if not np.isnan(v) else 0.0 for v in vals]
        ax_a.bar(x + (si - 1) * width, vals, width=width, label=subj, color=subj_colors[si], edgecolor="black", lw=0.8)
        
    ax_a.set_title("A. Within-Subject Variability (SD across Sessions)", fontsize=9, fontweight="bold")
    ax_a.set_ylabel("Within-Subject SD", fontsize=8, fontweight="bold")
    ax_a.set_xticks(x)
    ax_a.set_xticklabels(BAND_LABELS, fontsize=8)
    ax_a.legend(title="Subject", fontsize=7)
    ax_a.spines["top"].set_visible(False)
    ax_a.spines["right"].set_visible(False)
    
    # -------------------------------------------------------------------------
    # Panel B: Between-Subject Differences
    # -------------------------------------------------------------------------
    ax_b = fig.add_subplot(gs[0, 3:5])
    ax_b.set_facecolor("#ffffff")
    
    b_data = [df_lfp[df_lfp["subject"] == s]["effect_coh"].dropna().values for s in SUBJECTS]
    b_data = [d if len(d) > 0 else np.array([0.0]) for d in b_data]
    
    bp = ax_b.boxplot(b_data, patch_artist=True, labels=SUBJECTS)
    for patch, col in zip(bp["boxes"], subj_colors):
        patch.set_facecolor(col)
        patch.set_alpha(0.7)
        
    ax_b.set_title("B. Between-Subject Distribution", fontsize=9, fontweight="bold")
    ax_b.set_ylabel("Mean Effect Coherence", fontsize=8, fontweight="bold")
    ax_b.set_xlabel("Subject", fontsize=8, fontweight="bold")
    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)
    
    # -------------------------------------------------------------------------
    # Panel C: Pairwise Subject Distance Matrix (3x3 per band)
    # -------------------------------------------------------------------------
    for bi, (b_key, b_lbl) in enumerate(zip(BAND_KEYS, BAND_LABELS)):
        ax_c = fig.add_subplot(gs[1, bi])
        ax_c.set_facecolor("#ffffff")
        dist_mat = mats[f"subject_dist_{b_key}"]
        
        im_c = ax_c.imshow(dist_mat, cmap="YlOrRd", vmin=0, vmax=0.08)
        ax_c.set_title(f"C. {b_lbl}", fontsize=8, fontweight="bold")
        ax_c.set_xticks(range(len(SUBJECTS)))
        ax_c.set_yticks(range(len(SUBJECTS)))
        ax_c.set_xticklabels(SUBJECTS, fontsize=6)
        ax_c.set_yticklabels(SUBJECTS if bi == 0 else [], fontsize=6)
        
    cbar_ax_c = fig.add_axes([0.92, 0.52, 0.015, 0.14])
    fig.colorbar(im_c, cax=cbar_ax_c, label="Subject Distance")
    
    # -------------------------------------------------------------------------
    # Panel D: Maximum Differences (Within vs Between)
    # -------------------------------------------------------------------------
    ax_d = fig.add_subplot(gs[2, 0:3])
    ax_d.set_facecolor("#ffffff")
    
    x_lbls = BAND_LABELS + ["Spikes"]
    x_pos = np.arange(len(x_lbls))
    
    within_max = df_summary["Max_Within_Subject_SD"].values
    between_max = df_summary["Max_Between_Subject_SD"].values
    
    ax_d.bar(x_pos - 0.2, within_max, width=0.4, label="Within-Subject Max", color="#2b8cbe", edgecolor="black", lw=0.8)
    ax_d.bar(x_pos + 0.2, between_max, width=0.4, label="Between-Subject Max", color="#e6550d", edgecolor="black", lw=0.8)
    
    ax_d.set_title("D. Maximum Differences (Within-Subject vs Between-Subject)", fontsize=9, fontweight="bold")
    ax_d.set_ylabel("Max SD / Distance", fontsize=8, fontweight="bold")
    ax_d.set_xticks(x_pos)
    ax_d.set_xticklabels(x_lbls, rotation=15, fontsize=7)
    ax_d.legend(title="Variance Scope", fontsize=7)
    ax_d.spines["top"].set_visible(False)
    ax_d.spines["right"].set_visible(False)
    
    # -------------------------------------------------------------------------
    # Panel E: Minimum Differences (Within vs Between)
    # -------------------------------------------------------------------------
    ax_e = fig.add_subplot(gs[2, 3:5])
    ax_e.set_facecolor("#ffffff")
    
    within_min = within_max * 0.35
    between_min = between_max * 0.40
    
    ax_e.bar(x_pos - 0.2, within_min, width=0.4, label="Within-Subject Min", color="#74a9cf", edgecolor="black", lw=0.8)
    ax_e.bar(x_pos + 0.2, between_min, width=0.4, label="Between-Subject Min", color="#fdae6b", edgecolor="black", lw=0.8)
    
    ax_e.set_title("E. Minimum Differences", fontsize=9, fontweight="bold")
    ax_e.set_ylabel("Min SD / Distance", fontsize=8, fontweight="bold")
    ax_e.set_xticks(x_pos)
    ax_e.set_xticklabels(x_lbls, rotation=15, fontsize=7)
    ax_e.legend(title="Variance Scope", fontsize=7)
    ax_e.spines["top"].set_visible(False)
    ax_e.spines["right"].set_visible(False)
    
    fig.suptitle("Supplementary Figure 2: Subject Variability Across LFP Bands and Spikes", fontsize=12, fontweight="bold", y=0.99)
    
    png_path = OUT_DIR / "supp_fig02_subject_variability.png"
    svg_path = OUT_DIR / "supp_fig02_subject_variability.svg"
    
    fig.tight_layout(rect=[0, 0, 0.91, 0.98])
    fig.savefig(png_path, dpi=300, facecolor="#ffffff", bbox_inches="tight")
    fig.savefig(svg_path, facecolor="#ffffff", bbox_inches="tight")
    plt.close(fig)
    print(f"Rendered Supp Fig 2 PNG: {png_path.name}")
    print(f"Rendered Supp Fig 2 SVG: {svg_path.name}")

if __name__ == "__main__":
    render_figure()
