#!/usr/bin/env python3
"""
Supplementary Figure 3: Compact Quantitative Summary.

Panels:
  A. Maximum Delta Coherence (Across all area pairs, per band & spikes)
  B. Minimum Delta Coherence (Across all area pairs, per band & spikes)
  C. Effect Size (Cohen's d: Within vs Between area pairs)
  D. Full Statistical Summary Table (Signal, Band, Max/Min Delta, Within/Between SD, Mean +- SD, p-value)

Outputs:
  - context/figures/supplements/supp_fig03_summary.png (300 DPI)
  - context/figures/supplements/supp_fig03_summary.svg
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

SUMMARY_CSV = REPO_ROOT / "outputs" / "coherence_variability_summary.csv"

def load_data():
    df_summary = pd.read_csv(SUMMARY_CSV)
    return df_summary

def render_figure():
    df = load_data()
    
    fig = plt.figure(figsize=(14, 12), dpi=300)
    fig.patch.set_facecolor("#ffffff")
    
    gs = fig.add_gridspec(3, 3, height_ratios=[1.2, 1.2, 1.4], wspace=0.35, hspace=0.45)
    
    labels = df["Band"].values
    x = np.arange(len(labels))
    colors = BAND_COLORS + ["#7570b3"]
    
    # -------------------------------------------------------------------------
    # Panel A: Maximum Delta Coherence
    # -------------------------------------------------------------------------
    ax_a = fig.add_subplot(gs[0, 0:2])
    ax_a.set_facecolor("#ffffff")
    max_vals = df["Max_Delta"].values
    ax_a.bar(x, max_vals, color=colors, edgecolor="black", lw=0.8)
    ax_a.set_title("A. Maximum Delta Coherence Across Area Pairs", fontsize=9, fontweight="bold")
    ax_a.set_ylabel("Max Delta Coherence", fontsize=8, fontweight="bold")
    ax_a.set_xticks(x)
    ax_a.set_xticklabels(labels, rotation=15, fontsize=7)
    ax_a.spines["top"].set_visible(False)
    ax_a.spines["right"].set_visible(False)
    
    # -------------------------------------------------------------------------
    # Panel B: Minimum Delta Coherence
    # -------------------------------------------------------------------------
    ax_b = fig.add_subplot(gs[0, 2])
    ax_b.set_facecolor("#ffffff")
    min_vals = df["Min_Delta"].values
    ax_b.bar(x, min_vals, color=colors, edgecolor="black", lw=0.8)
    ax_b.set_title("B. Minimum Delta Coherence", fontsize=9, fontweight="bold")
    ax_b.set_ylabel("Min Delta Coherence", fontsize=8, fontweight="bold")
    ax_b.set_xticks(x)
    ax_b.set_xticklabels(labels, rotation=30, fontsize=6)
    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)
    
    # -------------------------------------------------------------------------
    # Panel C: Effect Size (Cohen's d: Within vs Between)
    # -------------------------------------------------------------------------
    ax_c = fig.add_subplot(gs[1, :])
    ax_c.set_facecolor("#ffffff")
    cohen_vals = df["Cohens_d_Within_vs_Between"].values
    ax_c.bar(x, cohen_vals, color=colors, alpha=0.85, edgecolor="black", lw=0.8)
    ax_c.axhline(0, color="gray", ls="--", lw=0.8)
    ax_c.axhline(0.5, color="red", ls=":", lw=0.8, label="Moderate Effect (d=0.5)")
    ax_c.set_title("C. Effect Size (Cohen's d): Within-Area vs Between-Area Coherence", fontsize=9, fontweight="bold")
    ax_c.set_ylabel("Cohen's d", fontsize=8, fontweight="bold")
    ax_c.set_xticks(x)
    ax_c.set_xticklabels(labels, fontsize=8)
    ax_c.legend(fontsize=7, loc="upper right")
    ax_c.spines["top"].set_visible(False)
    ax_c.spines["right"].set_visible(False)
    
    # -------------------------------------------------------------------------
    # Panel D: Publication Summary Table
    # -------------------------------------------------------------------------
    ax_d = fig.add_subplot(gs[2, :])
    ax_d.axis("off")
    ax_d.set_title("D. Quantitative Summary Table Across Signals and Frequency Bands", fontsize=10, fontweight="bold", pad=10)
    
    table_data = []
    headers = ["Signal", "Frequency Band", "Max Δ", "Min Δ", "Within SD", "Between SD", "Mean ± SD", "p-value"]
    
    for _, row in df.iterrows():
        mean_sd_str = f"{row['Mean_Delta']:.3f} ± {row['SD_Delta']:.3f}"
        p_str = f"{row['p_value']:.4f}" if row['p_value'] >= 0.001 else "< 0.001"
        table_data.append([
            row["Signal"],
            row["Band"],
            f"{row['Max_Delta']:.3f}",
            f"{row['Min_Delta']:.3f}",
            f"{row['Max_Within_Subject_SD']:.3f}",
            f"{row['Max_Between_Subject_SD']:.3f}",
            mean_sd_str,
            p_str,
        ])
        
    tab = ax_d.table(
        cellText=table_data,
        colLabels=headers,
        cellLoc="center",
        loc="center"
    )
    tab.auto_set_font_size(False)
    tab.set_fontsize(8)
    tab.scale(1.0, 1.4)
    
    # Highlight header row
    for (r, c), cell in tab.get_celld().items():
        if r == 0:
            cell.set_facecolor("#2b8cbe")
            cell.get_text().set_color("white")
            cell.get_text().set_weight("bold")
        else:
            cell.set_facecolor("#f7f7f7" if r % 2 == 0 else "#ffffff")
            
    fig.suptitle("Supplementary Figure 3: Compact Quantitative Summary Across Signals and Bands", fontsize=12, fontweight="bold", y=0.99)
    
    png_path = OUT_DIR / "supp_fig03_summary.png"
    svg_path = OUT_DIR / "supp_fig03_summary.svg"
    
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig(png_path, dpi=300, facecolor="#ffffff", bbox_inches="tight")
    fig.savefig(svg_path, facecolor="#ffffff", bbox_inches="tight")
    plt.close(fig)
    print(f"Rendered Supp Fig 3 PNG: {png_path.name}")
    print(f"Rendered Supp Fig 3 SVG: {svg_path.name}")

if __name__ == "__main__":
    render_figure()
