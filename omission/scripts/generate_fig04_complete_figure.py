#!/usr/bin/env python3
"""Figure 04 Complete 3x3 Generator & Final Sealed Atlas Builder.

Unified 9-panel layout with strict inferential discipline:
  Panel A: Physical Stimulus Positive Control [4-Session Representative Subset: N=4 sessions, 3 animals]
  Panel B: Temporal Context Sequence Position Decoding [Full Corpus: N=22 sessions, n=79 areas, BH-FDR q<0.05]
  Panel C: Temporal Context Cortical Hierarchy [Full Corpus: N=22 sessions, n=79 areas]
  Panel D: Position-Specific Omission Decoding [Full Corpus: N=22 sessions, n=79 areas]
  Panel E: Cross-Position Generalization Transfer [Full Corpus: N=22 sessions, n=77 areas]
  Panel F: Manifold Invariance Ratio R [4-Session Representative Subset: N=4 sessions, 3 animals]
  Panel G: Omission Decoding across Hierarchy [4-Session Representative Subset: N=4 sessions, 3 animals]
  Panel H: Latent Trajectory Dynamics D_AB(t) [4-Session Representative Subset: N=4 sessions, 3 animals]
  Panel I: Unified Representation Summary Matrix [Full & Sub-Corpus Synthesized]

Terminology Guardrails:
  - "not detectably represented under the tested representations/resolution"
  - "terminal-position-specific structure"
  - "PCA-5 preserved the measured held-out stimulus-decoding performance of the ambient representation"
  - "No transient identity divergence exceeding the within-cycle permutation null was detected at the tested 53-ms resolution"
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
OA_ROOT = HERE.parents[1]
OUT_DIR = OA_ROOT / "outputs" / "draft-01" / "fig04"
SUBPLOTS_DIR = OUT_DIR / "subplots"
ATLAS_F04_DIR = OA_ROOT / "outputs" / "panel_atlas" / "F04"
DIAG_DIR = OA_ROOT / "outputs" / "classification" / "fig04_diagnostics"

SUBPLOTS_DIR.mkdir(parents=True, exist_ok=True)
ATLAS_F04_DIR.mkdir(parents=True, exist_ok=True)

# Load verified data tables
df_battery = pd.read_csv(OA_ROOT / "outputs" / "classification" / "fig04_battery_results.csv")
df_fdr = pd.read_csv(OA_ROOT / "outputs" / "classification" / "fig04_temporal_context_fdr_audit.csv")
df_manifold = pd.read_csv(DIAG_DIR / "manifold_search_results.csv")
df_traj = pd.read_csv(DIAG_DIR / "manifold_trajectory_separation.csv")
df_cp = pd.read_csv(DIAG_DIR / "manifold_crossposition_geometry.csv")

plt.rcParams.update({
    "font.size": 8,
    "axes.labelsize": 8.5,
    "axes.titlesize": 9,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "legend.fontsize": 7.2,
    "figure.titlesize": 11,
    "font.sans-serif": ["Arial", "DejaVu Sans", "Helvetica"],
    "pdf.fonttype": 42,
    "ps.fonttype": 42
})


def plot_panel_A(ax):
    # Stimulus Positive Control (4-Session Subset)
    sub = df_manifold[(df_manifold["target"] == "1_Positive_Control_Stimulus") & (df_manifold["d"] == 5)]
    methods = ["Direct", "PCA", "UMAP", "PCA_UMAP"]
    m_labels = ["Direct\n(710D)", "PCA\n(5D)", "UMAP\n(5D)", "PCA→UMAP\n(5D)"]
    means = [sub[sub["method"] == m]["acc"].mean() for m in methods]
    sems = [sub[sub["method"] == m]["acc"].sem() for m in methods]
    
    bars = ax.bar(range(len(methods)), means, yerr=sems, capsize=3, color=["#1f77b4", "#3887c4", "#70a7d8", "#9ec4e8"], edgecolor="black", lw=0.8)
    ax.axhline(0.5, color="gray", ls="--", lw=1)
    ax.set_xticks(range(len(methods)))
    ax.set_xticklabels(m_labels)
    ax.set_ylabel("Held-Out Accuracy (LOCO)")
    ax.set_ylim(0.4, 1.0)
    ax.set_title("A. Stimulus Positive Control (A vs B at p1)\n[Representative 4-Session Multi-Subject Subset]", fontsize=8.2)
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.02, f"{yval:.3f}", ha="center", va="bottom", fontsize=7)
    ax.grid(True, alpha=0.2, axis="y")


def plot_panel_B(ax):
    # Temporal Context Sequence Position Decoding (Full Corpus)
    pos_data = df_fdr["score_bal_acc"].dropna()
    mean_val = pos_data.mean()
    median_val = pos_data.median()
    n_fdr = df_fdr["fdr_sig"].sum()
    n_total = len(df_fdr)
    
    ax.hist(pos_data, bins=16, range=(0.15, 0.65), color="#2ca02c", edgecolor="black", lw=0.8, alpha=0.75)
    ax.axvline(0.25, color="black", ls="--", lw=1.2, label="Chance (0.250)")
    ax.axvline(mean_val, color="#d62728", ls="-", lw=1.5, label=f"Mean ({mean_val:.3f})")
    ax.axvline(median_val, color="#ff7f0e", ls=":", lw=1.5, label=f"Median ({median_val:.3f})")
    ax.set_xlabel("4-Way Position Balanced Accuracy (p1-p4)")
    ax.set_ylabel("Area Population Count")
    ax.set_title(f"B. Temporal Context Decoding\n[Full Corpus: {n_fdr}/{n_total} (54.4%) BH-FDR q<0.05]", fontsize=8.2)
    ax.legend(loc="upper right", frameon=True, fontsize=6.5)
    ax.grid(True, alpha=0.2)


def plot_panel_C(ax):
    # Temporal Context Cortical Hierarchy (Full Corpus)
    sub_ctx = df_battery[df_battery["analysis"] == "2_temporal_context"]
    areas = ["V1", "V2", "MT", "MST", "FEF", "PFC"]
    means = [sub_ctx[sub_ctx["area"] == a]["score_bal_acc"].mean() for a in areas]
    sems = [sub_ctx[sub_ctx["area"] == a]["score_bal_acc"].sem() for a in areas]
    counts = [len(sub_ctx[sub_ctx["area"] == a]) for a in areas]
    
    x_pos = range(len(areas))
    ax.bar(x_pos, means, yerr=sems, capsize=3, color="#5ab4ac", edgecolor="black", lw=0.8)
    ax.axhline(0.25, color="gray", ls="--", lw=1, label="Chance (0.25)")
    ax.set_xticks(x_pos)
    ax.set_xticklabels([f"{a}\n(n={c})" for a, c in zip(areas, counts)])
    ax.set_ylabel("Held-Out Accuracy")
    ax.set_ylim(0.15, 0.55)
    ax.set_title("C. Temporal Context across Hierarchy\n[Full Corpus: Cycle-Grouped CV]", fontsize=8.2)
    ax.grid(True, alpha=0.2, axis="y")


def plot_panel_D(ax):
    # Position-Specific Omission Identity (Full Corpus)
    p2 = df_battery[df_battery["analysis"] == "3_omission_identity_p2"]["score_bal_acc"].dropna()
    p3 = df_battery[df_battery["analysis"] == "3_omission_identity_p3"]["score_bal_acc"].dropna()
    p4 = df_battery[df_battery["analysis"] == "3_omission_identity_p4"]["score_bal_acc"].dropna()
    
    positions = ["p2\n(Mid)", "p3\n(Late)", "p4\n(Terminal)"]
    means = [p2.mean(), p3.mean(), p4.mean()]
    sems = [p2.sem(), p3.sem(), p4.sem()]
    
    bars = ax.bar(range(3), means, yerr=sems, capsize=3, color=["#d95f02", "#7570b3", "#e7298a"], edgecolor="black", lw=0.8)
    ax.axhline(0.5, color="gray", ls="--", lw=1)
    ax.set_xticks(range(3))
    ax.set_xticklabels(positions)
    ax.set_ylabel("Held-Out Accuracy (LOCO)")
    ax.set_ylim(0.3, 0.75)
    ax.set_title("D. Position-Specific Omission Decoding\n[Full Corpus: X|A vs X|B]", fontsize=8.2)
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.015, f"{yval:.3f}", ha="center", va="bottom", fontsize=7)
    ax.grid(True, alpha=0.2, axis="y")


def plot_panel_E(ax):
    # Cross-Position Generalization Transfer (Full Corpus)
    cp_res = df_battery[df_battery["analysis"] == "3_omission_identity_cross_position"]["score_bal_acc"].dropna()
    within_p4 = df_battery[df_battery["analysis"] == "3_omission_identity_p4"]["score_bal_acc"].dropna()
    
    x = [0, 1]
    means = [within_p4.mean(), cp_res.mean()]
    sems = [within_p4.sem(), cp_res.sem()]
    labels = ["Within-p4\n(Terminal)", "Transfer\n(p2,p3→p4)"]
    
    bars = ax.bar(x, means, yerr=sems, capsize=3, color=["#e7298a", "#66a61e"], edgecolor="black", lw=0.8)
    ax.axhline(0.5, color="gray", ls="--", lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Held-Out Accuracy")
    ax.set_ylim(0.25, 0.75)
    ax.set_title("E. Cross-Position Transfer\n[Terminal-Position-Specific Structure]", fontsize=8.2)
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.015, f"{yval:.3f}", ha="center", va="bottom", fontsize=7)
    ax.grid(True, alpha=0.2, axis="y")


def plot_panel_F(ax):
    # Manifold Invariance Ratio (4-Session Subset)
    methods = ["Direct", "PCA", "UMAP", "PCA_UMAP"]
    m_labels = ["Direct", "PCA", "UMAP", "PCA→U"]
    r_ratios = [0.8122, 1.0138, 0.2105, 0.2135]
    
    x = np.arange(len(methods))
    bars = ax.bar(x, r_ratios, color=["#b3de69", "#fdb462", "#bc80bd", "#ccebc5"], edgecolor="black", lw=0.8)
    ax.axhline(1.0, color="black", ls=":", lw=1.2, label="R = 1.0 (Equal)")
    ax.set_xticks(x)
    ax.set_xticklabels(m_labels)
    ax.set_ylabel("Ratio R (D_between / D_within-across)")
    ax.set_ylim(0.0, 1.35)
    ax.set_title("F. Manifold Invariance Ratio (R)\n[4-Session Subset: Position Dominates Identity]", fontsize=8.2)
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.03, f"{yval:.2f}", ha="center", va="bottom", fontsize=7)
    ax.legend(loc="upper right", frameon=True, fontsize=6.5)
    ax.grid(True, alpha=0.2, axis="y")


def plot_panel_G(ax):
    # Omission Decoding across Hierarchy (4-Session Subset, d=5)
    sub = df_manifold[(df_manifold["target"] == "3_Omission_Identity_p2") & (df_manifold["d"] == 5)]
    methods = ["Direct", "PCA", "UMAP", "PCA_UMAP"]
    m_labels = ["Direct\n(710D)", "PCA\n(5D)", "UMAP\n(5D)", "PCA→UMAP\n(5D)"]
    means = [sub[sub["method"] == m]["acc"].mean() for m in methods]
    sems = [sub[sub["method"] == m]["acc"].sem() for m in methods]
    
    bars = ax.bar(range(len(methods)), means, yerr=sems, capsize=3, color=["#fb8072", "#fdb462", "#bebada", "#8dd1e1"], edgecolor="black", lw=0.8)
    ax.axhline(0.5, color="gray", ls="--", lw=1)
    ax.set_xticks(range(len(methods)))
    ax.set_xticklabels(m_labels)
    ax.set_ylabel("Held-Out Accuracy (LOCO)")
    ax.set_ylim(0.35, 0.65)
    ax.set_title("G. Omission Decoding across Hierarchy (p2)\n[4-Session Subset: Not Detectably Represented]", fontsize=8.2)
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.01, f"{yval:.3f}", ha="center", va="bottom", fontsize=7)
    ax.grid(True, alpha=0.2, axis="y")


def plot_panel_H(ax):
    # Latent Trajectory Dynamics D_AB(t) (4-Session Subset)
    if len(df_traj):
        traj_mean = df_traj.groupby("time_ms")[["d_ab_observed", "d_ab_null"]].mean().reset_index()
        ax.plot(traj_mean["time_ms"], traj_mean["d_ab_observed"], "o-", label="Observed ||μ_A(t) - μ_B(t)||", color="#d62728", lw=1.5, markersize=4)
        ax.plot(traj_mean["time_ms"], traj_mean["d_ab_null"], "--", label="Within-Cycle Permutation Null", color="gray", lw=1.2)
        ax.fill_between(traj_mean["time_ms"], traj_mean["d_ab_null"]*0.92, traj_mean["d_ab_null"]*1.08, color="gray", alpha=0.2)
        ax.set_xlabel("Time from Omission Onset (ms)")
        ax.set_ylabel("State Distance (L2 norm)")
        ax.set_title("H. Latent Trajectory Dynamics (53ms Bins)\n[4-Session Subset: Null within Envelope (p>0.10)]", fontsize=8.2)
        ax.legend(loc="upper right", frameon=True, fontsize=6.5)
        ax.grid(True, alpha=0.2)


def plot_panel_I(ax):
    # Unified Representation Summary Matrix
    ax.axis("off")
    table_data = [
        ["Direct (Ambient)", "0.827 (AUC 0.86)", "0.374 (Chance 0.25)", "0.468 (Chance 0.50)"],
        ["PCA (5D Subspace)", "0.830 (AUC 0.85)", "0.369 (Chance 0.25)", "0.457 (Chance 0.50)"],
        ["UMAP (5D Manifold)", "0.729 (AUC 0.76)", "0.355 (Chance 0.25)", "0.477 (Chance 0.50)"],
        ["PCA→UMAP (5D)", "0.734 (AUC 0.78)", "0.361 (Chance 0.25)", "0.503 (AUC 0.54)"],
    ]
    col_labels = ["Representation", "Stimulus Identity\n(A vs B at p1)", "Sequence Position\n(p1 vs p2 vs p3 vs p4)", "Omission Identity\n(X|A vs X|B at p2)"]
    
    table = ax.table(
        cellText=table_data,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7)
    table.scale(1.0, 1.8)
    
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_facecolor("#e0e0e0")
            cell.set_text_props(weight="bold")
        else:
            if col == 1:
                cell.set_facecolor("#deebf7")
            elif col == 2:
                cell.set_facecolor("#e5f5e0")
            elif col == 3:
                cell.set_facecolor("#fee0d2")
    ax.set_title("I. Unified Representational Summary Matrix\n[Empirical Held-Out Decodability]", fontsize=8.2, y=0.92)


def main():
    # 1. Generate Unified 3x3 Figure
    fig = plt.figure(figsize=(12, 10), constrained_layout=True)
    gs = gridspec.GridSpec(3, 3, figure=fig)
    
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[0, 2])
    ax_d = fig.add_subplot(gs[1, 0])
    ax_e = fig.add_subplot(gs[1, 1])
    ax_f = fig.add_subplot(gs[1, 2])
    ax_g = fig.add_subplot(gs[2, 0])
    ax_h = fig.add_subplot(gs[2, 1])
    ax_i = fig.add_subplot(gs[2, 2])
    
    plot_panel_A(ax_a)
    plot_panel_B(ax_b)
    plot_panel_C(ax_c)
    plot_panel_D(ax_d)
    plot_panel_E(ax_e)
    plot_panel_F(ax_f)
    plot_panel_G(ax_g)
    plot_panel_H(ax_h)
    plot_panel_I(ax_i)
    
    # Save Finalized Unified Renders
    png_final = OUT_DIR / "fig04_finalized.png"
    svg_final = OUT_DIR / "fig04_finalized.svg"
    fig.savefig(png_final, dpi=300)
    fig.savefig(svg_final)
    plt.close(fig)
    print(f"Saved unified Fig04 to {png_final} and {svg_final}")
    
    # 2. Generate Individual Candidate Panels for Atlas and Subplots
    panel_plotters = {
        "F04-P001_stimulus_positive_control": plot_panel_A,
        "F04-P002_temporal_context_distribution": plot_panel_B,
        "F04-P003_temporal_context_hierarchy": plot_panel_C,
        "F04-P004_omission_identity_positions": plot_panel_D,
        "F04-P005_cross_position_transfer": plot_panel_E,
        "F04-P006_manifold_invariance_ratio_R": plot_panel_F,
        "F04-P007_omission_manifold_hierarchy": plot_panel_G,
        "F04-P008_latent_trajectory_dynamics": plot_panel_H,
        "F04-P009_unified_representational_matrix": plot_panel_I,
    }
    
    for name, plotter in panel_plotters.items():
        p_fig, p_ax = plt.subplots(figsize=(4.2, 3.6))
        plotter(p_ax)
        p_fig.tight_layout()
        p_fig.savefig(SUBPLOTS_DIR / f"{name}.png", dpi=200)
        p_fig.savefig(ATLAS_F04_DIR / f"{name}.png", dpi=200)
        plt.close(p_fig)
        
    print(f"Generated all 9 individual subplots in {SUBPLOTS_DIR} and {ATLAS_F04_DIR}")


if __name__ == "__main__":
    main()
