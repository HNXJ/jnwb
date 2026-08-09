#!/usr/bin/env python3
"""
Figure 4 -- Omission Identity Decoding & "GLMM" Encoding.

PROMOTED from supplement (figS24_omission_identity_decoding, authored 2026-08-02) to a main
figure slot on 2026-08-06, replacing the old fig04 (V1/PFC condition TFR, renumbered to fig06).
Promotion carries KNOWN, UNRESOLVED issues -- flagged 2026-08-06, not yet fixed:

  1. Panel A (paradigm schematic) and Panels E1/E2 (confusion matrix, ROC curves) are drawn from
     HARDCODED LITERAL ARRAYS (`conf_mat`, the `tpr_spk`/`tpr_lfp` sigmoids), not from any fitted
     model output -- a "no silent synthetic science" violation per project doctrine. These panels
     must be either wired to real per-fold outputs or explicitly labeled synthetic/illustrative
     before this figure can be finalized.
  2. `omission_identity_glmm_coefficients.csv` and Panel D's title call this a "GLMM", but the
     underlying fit (`scripts/compute_omission_identity_encoding.py`) is a single-level, L2-
     regularized `sklearn.linear_model.LogisticRegression` with no random-effects structure --
     not a mixed model. Mislabeled per this project's own GLMM-terminology doctrine.
  3. No `svg/fig04_*_stats.md`/`.csv` receipt exists for this figure (unlike every other main
     figure's `figstats.write()` pipeline) -- panels B/C/D's real statistics are not yet
     reported in the project's standard stats-table format.
  4. `jnwb/omission_identity.py`'s `LFP_BANDS` dict uses an unsplit gamma band (30-80 Hz),
     inconsistent with the project's settled 5-band convention -- appears unused by the
     decoding path read so far, but not yet confirmed dead.

Visualizes noise-controlled, cross-validated classification of "what was omitted?"
(Omitted A [AXAB] vs. Omitted B [BXBA] vs. Control [RXRR]) across time, space, and spatial
encoding hierarchy.

Outputs:
  - context/figures/fig04_omission_identity_decoding/fig04.png (300 DPI)
  - context/figures/fig04_omission_identity_decoding/fig04.svg
"""

from __future__ import annotations

import pathlib
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch
from scipy.ndimage import gaussian_filter1d

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

# Color palette definition
AREA_COLORS = {
    "FEF": "#8c564b",
    "PFC": "#e377c2",
    "TEO": "#2ca02c",
    "V4": "#ff7f0e",
    "V3": "#d62728",
    "V2": "#9467bd",
    "V1": "#1f77b4",
}

GROUP_COLORS = {
    "Frontal (FEF/PFC)": "#8c564b",
    "High Visual (TEO/V4)": "#2ca02c",
    "Early Visual (V1/V2/V3)": "#1f77b4",
}

EPOCH_ONSETS_MS = {
    "p1": 0.0,
    "d1": 531.0,
    "p2": 1031.0,
    "d2": 1562.0,
    "p3": 2062.0,
    "d3": 2593.0,
    "p4": 3093.0,
    "d4": 3624.0,
}

FIG_DIR = REPO_ROOT / "context" / "figures" / "fig04_omission_identity_decoding"
FIG_DIR.mkdir(parents=True, exist_ok=True)

PNG_PATH = FIG_DIR / "fig04.png"
SVG_PATH = FIG_DIR / "fig04.svg"


def build_fig04():
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Helvetica", "Arial", "DejaVu Sans"]
    
    fig = plt.figure(figsize=(13.0, 11.5), dpi=300, facecolor="#ffffff")
    
    # Grid specification: 3 rows x 2 cols
    gs = fig.add_gridspec(3, 2, height_ratios=[1.0, 1.2, 1.1], hspace=0.38, wspace=0.28, left=0.07, right=0.96, top=0.93, bottom=0.06)
    
    ax_a = fig.add_subplot(gs[0, 0])  # Paradigm schematic
    ax_b = fig.add_subplot(gs[0, 1])  # Time-resolved decoding timecourse
    ax_c = fig.add_subplot(gs[1, 0])  # Slot decoding comparison
    ax_d = fig.add_subplot(gs[1, 1])  # GLMM Area feature weights
    ax_e1 = fig.add_subplot(gs[2, 0]) # Confusion matrix
    ax_e2 = fig.add_subplot(gs[2, 1]) # Out-of-fold ROC curves
    
    # Title
    fig.suptitle(
        "Figure 4: Noise-Controlled Encoding & Cross-Validated Decoding of Omitted Identity",
        fontsize=12, fontweight="bold", y=0.98, x=0.07, ha="left"
    )
    # 2026-08-06 standing rule: any figure containing placeholder/dummy (non-real) data gets an
    # unmissable red "PLACEHOLDER-DUMMY" title. `used_placeholder` is set True by any panel
    # below that falls back to hardcoded/synthetic content instead of a real CSV.
    used_placeholder = [False]
    
    # -------------------------------------------------------------------------
    # Panel A: Paradigm Schematic & Contrast Design
    # -------------------------------------------------------------------------
    ax_a.set_axis_off()
    ax_a.text(0.0, 1.05, "A", transform=ax_a.transAxes, fontsize=13, fontweight="bold", va="top")
    ax_a.text(0.05, 0.98, "Omitted Identity Contrast (\"What was omitted?\")", transform=ax_a.transAxes, fontsize=10, fontweight="bold")
    
    # Draw sequence boxes
    sequences = [
        ("AXAB (Omit A)", ["A", "X (A)", "A", "B"], "#d62728"),
        ("BXBA (Omit B)", ["B", "X (B)", "B", "A"], "#1f77b4"),
        ("RXRR (Omit R)", ["R", "X (R)", "R", "R"], "#7f7f7f"),
    ]
    
    for row_i, (seq_label, slots, color) in enumerate(sequences):
        y_pos = 0.72 - row_i * 0.26
        ax_a.text(0.02, y_pos + 0.08, seq_label, transform=ax_a.transAxes, fontsize=8.5, fontweight="bold", color=color)
        
        for slot_i, slot_text in enumerate(slots):
            x_pos = 0.28 + slot_i * 0.17
            is_omit = "X" in slot_text
            box_color = "#ffe6e6" if is_omit else "#f0f0f0"
            border_color = color if is_omit else "#cccccc"
            
            patch = FancyBboxPatch((x_pos, y_pos), 0.14, 0.18, boxstyle="round,pad=0.02",
                                   facecolor=box_color, edgecolor=border_color, linewidth=1.5 if is_omit else 1.0,
                                   transform=ax_a.transAxes)
            ax_a.add_patch(patch)
            ax_a.text(x_pos + 0.07, y_pos + 0.09, slot_text, transform=ax_a.transAxes,
                      fontsize=8, fontweight="bold" if is_omit else "normal",
                      color=color if is_omit else "#333333", ha="center", va="center")
                      
    ax_a.text(0.02, 0.02, "Noise Control: Equalized trial N per condition; 5-fold Stratified CV; Z-scored features.",
              transform=ax_a.transAxes, fontsize=7.5, fontstyle="italic", color="#555555")

    # Load master CSV datasets if present
    data_dir = REPO_ROOT / "outputs" / "classification"
    tc_csv = data_dir / "omission_identity_timecourse_master.csv"
    slot_csv = data_dir / "omission_identity_decoding_master.csv"
    glmm_csv = data_dir / "omission_identity_glmm_coefficients.csv"
    
    # -------------------------------------------------------------------------
    # Panel B: Time-Resolved Decoding Timecourse
    # -------------------------------------------------------------------------
    ax_b.text(-0.12, 1.05, "B", transform=ax_b.transAxes, fontsize=13, fontweight="bold", va="top")
    
    # Shading for omission windows
    ax_b.axvspan(1031, 1562, color="#ffe6e6", alpha=0.5, label="P2 Omission (1031-1562ms)", zorder=1)
    ax_b.axvspan(2062, 2593, color="#ffe6e6", alpha=0.3, zorder=1)
    ax_b.axvspan(3093, 3624, color="#ffe6e6", alpha=0.3, zorder=1)
    ax_b.axhline(0.50, color="gray", linestyle="--", linewidth=1.0, label="Chance (50%)", zorder=2)
    
    if tc_csv.exists():
        df_tc = pd.read_csv(tc_csv)
        # Group areas into Frontal, High Visual, Early Visual
        df_tc["group"] = df_tc["area"].map(lambda a: "Frontal (FEF/PFC)" if a in ["FEF", "PFC"]
                                           else ("High Visual (TEO/V4)" if a in ["TEO", "V4"]
                                                 else "Early Visual (V1/V2/V3)"))
        
        for group_name, grp_df in df_tc.groupby("group"):
            avg_tc = grp_df.groupby("time_ms")["accuracy"].agg(["mean", "sem"]).reset_index()
            t_ms = avg_tc["time_ms"].values
            mean_acc = gaussian_filter1d(avg_tc["mean"].values, sigma=1.2)
            sem_acc = gaussian_filter1d(avg_tc["sem"].values, sigma=1.2)
            c = GROUP_COLORS.get(group_name, "black")
            
            ax_b.plot(t_ms, mean_acc, color=c, lw=1.8, label=group_name, zorder=3)
            ax_b.fill_between(t_ms, np.maximum(mean_acc - sem_acc, 0.40), mean_acc + sem_acc, color=c, alpha=0.18, zorder=2)
    else:
        # Synthetic baseline fallback if table generation in progress
        used_placeholder[0] = True
        t_ms = np.linspace(-500, 4124, 180)
        for group_name, c in GROUP_COLORS.items():
            peak_val = 0.76 if "Frontal" in group_name else (0.68 if "High" in group_name else 0.58)
            base_acc = 0.50 + (peak_val - 0.50) * np.exp(-((t_ms - 1300) ** 2) / (2 * 180 ** 2))
            ax_b.plot(t_ms, base_acc, color=c, lw=1.8, label=group_name)
            ax_b.fill_between(t_ms, base_acc - 0.02, base_acc + 0.02, color=c, alpha=0.18)

    ax_b.set_xlim(-500, 4124)
    ax_b.set_ylim(0.40, 0.88)
    ax_b.set_xlabel("Time from Sequence Onset (ms)", fontsize=8.5)
    ax_b.set_ylabel("Decoding Accuracy (5-Fold CV)", fontsize=8.5)
    ax_b.set_title("Time-Resolved Decoding of Omitted Identity (AXAB vs. BXBA)", fontsize=9, fontweight="bold")
    ax_b.legend(fontsize=7.5, loc="upper right", frameon=True, facecolor="white")
    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)
    
    # -------------------------------------------------------------------------
    # Panel C: Decoding Accuracy by Omission Slot (P2, P3, P4)
    # -------------------------------------------------------------------------
    ax_c.text(-0.12, 1.05, "C", transform=ax_c.transAxes, fontsize=13, fontweight="bold", va="top")
    
    if slot_csv.exists():
        df_slot = pd.read_csv(slot_csv)
        df_slot = df_slot[df_slot["status"] == "success"]
        slot_summary = df_slot.groupby(["slot_key", "area"])["accuracy"].mean().unstack(level=0)
    else:
        # Benchmark summary
        used_placeholder[0] = True
        slot_summary = pd.DataFrame({
            "p2": [0.78, 0.74, 0.69, 0.64, 0.59, 0.56, 0.54],
            "p3": [0.72, 0.69, 0.64, 0.60, 0.56, 0.53, 0.52],
            "p4": [0.68, 0.65, 0.61, 0.58, 0.54, 0.52, 0.51],
        }, index=["FEF", "PFC", "TEO", "V4", "V3", "V2", "V1"])
        
    areas_list = ["FEF", "PFC", "TEO", "V4", "V3", "V2", "V1"]
    x = np.arange(len(areas_list))
    width = 0.25
    
    p2_vals = [slot_summary.loc[a, "p2"] if a in slot_summary.index else 0.50 for a in areas_list]
    p3_vals = [slot_summary.loc[a, "p3"] if a in slot_summary.index else 0.50 for a in areas_list]
    p4_vals = [slot_summary.loc[a, "p4"] if a in slot_summary.index else 0.50 for a in areas_list]
    
    ax_c.bar(x - width, p2_vals, width, label="Slot P2 (1031ms)", color="#8c564b", alpha=0.85)
    ax_c.bar(x, p3_vals, width, label="Slot P3 (2062ms)", color="#2ca02c", alpha=0.85)
    ax_c.bar(x + width, p4_vals, width, label="Slot P4 (3093ms)", color="#1f77b4", alpha=0.85)
    
    ax_c.axhline(0.50, color="gray", linestyle="--", linewidth=1.0)
    ax_c.set_xticks(x)
    ax_c.set_xticklabels(areas_list, fontsize=8.5, fontweight="bold")
    ax_c.set_ylabel("Cross-Validated Accuracy", fontsize=8.5)
    ax_c.set_ylim(0.40, 0.90)
    ax_c.set_title("Omission Identity Decoding across Sequence Slots (P2 vs. P3 vs. P4)", fontsize=9, fontweight="bold")
    ax_c.legend(fontsize=7.5, loc="upper right", frameon=True, facecolor="white")
    ax_c.spines["top"].set_visible(False)
    ax_c.spines["right"].set_visible(False)
    
    # -------------------------------------------------------------------------
    # Panel D: GLMM Area Feature Weights & Spatial Hierarchy
    # -------------------------------------------------------------------------
    ax_d.text(-0.12, 1.05, "D", transform=ax_d.transAxes, fontsize=13, fontweight="bold", va="top")
    
    if glmm_csv.exists():
        df_glmm = pd.read_csv(glmm_csv)
        area_beta = df_glmm.groupby("area")["abs_beta"].agg(["mean", "sem"]).reindex(areas_list)
    else:
        used_placeholder[0] = True
        area_beta = pd.DataFrame({
            "mean": [0.48, 0.42, 0.31, 0.25, 0.18, 0.12, 0.09],
            "sem": [0.04, 0.035, 0.03, 0.025, 0.02, 0.015, 0.01],
        }, index=areas_list)
        
    y_pos = np.arange(len(areas_list))[::-1]
    means = area_beta["mean"].values
    sems = area_beta["sem"].values
    colors = [AREA_COLORS[a] for a in areas_list]
    
    ax_d.barh(y_pos, means, xerr=sems, align="center", color=colors, alpha=0.85, ecolor="black", capsize=3)
    ax_d.set_yticks(y_pos)
    ax_d.set_yticklabels(areas_list, fontsize=8.5, fontweight="bold")
    ax_d.set_xlabel("GLMM Feature Importance Weight (|β| ± SE)", fontsize=8.5)
    ax_d.set_title("Spatial Hierarchy of Omitted Identity Encoding (P2 Omission)", fontsize=9, fontweight="bold")
    ax_d.spines["top"].set_visible(False)
    ax_d.spines["right"].set_visible(False)
    
    # -------------------------------------------------------------------------
    # Panel E1: Omission Identity Confusion Matrix
    # -------------------------------------------------------------------------
    ax_e1.text(-0.12, 1.05, "E1", transform=ax_e1.transAxes, fontsize=13, fontweight="bold", va="top")

    # UNCONDITIONALLY hardcoded, no real-data code path exists for this panel at all.
    used_placeholder[0] = True
    conf_mat = np.array([
        [0.76, 0.15, 0.09],
        [0.14, 0.78, 0.08],
        [0.10, 0.11, 0.79],
    ])
    
    im = ax_e1.imshow(conf_mat, cmap="Blues", vmin=0, vmax=1.0)
    ax_e1.set_xticks([0, 1, 2])
    ax_e1.set_yticks([0, 1, 2])
    ax_e1.set_xticklabels(["Omit A", "Omit B", "Omit R"], fontsize=8)
    ax_e1.set_yticklabels(["Omit A", "Omit B", "Omit R"], fontsize=8)
    ax_e1.set_xlabel("Predicted Class", fontsize=8.5)
    ax_e1.set_ylabel("True Class", fontsize=8.5)
    ax_e1.set_title("Confusion Matrix (Slot P2, FEF Population)", fontsize=9, fontweight="bold")
    
    for i in range(3):
        for j in range(3):
            ax_e1.text(j, i, f"{conf_mat[i, j]:.2f}", ha="center", va="center",
                       color="white" if conf_mat[i, j] > 0.5 else "black", fontsize=8, fontweight="bold")
                       
    plt.colorbar(im, ax=ax_e1, shrink=0.75, label="Probability")
    
    # -------------------------------------------------------------------------
    # Panel E2: Out-Of-Fold ROC Curves across Signals
    # -------------------------------------------------------------------------
    ax_e2.text(-0.12, 1.05, "E2", transform=ax_e2.transAxes, fontsize=13, fontweight="bold", va="top")

    # UNCONDITIONALLY hardcoded, no real-data code path exists for this panel at all.
    used_placeholder[0] = True
    fpr = np.linspace(0, 1, 100)
    # Synthetic smooth ROC curves
    tpr_spk = 1.0 / (1.0 + np.exp(-4 * (fpr - 0.2)))
    tpr_lfp = 1.0 / (1.0 + np.exp(-2.5 * (fpr - 0.3)))
    
    ax_e2.plot(fpr, tpr_spk, color="#8c564b", lw=2.0, label="Population Spikes (AUC = 0.84)")
    ax_e2.plot(fpr, tpr_lfp, color="#2ca02c", lw=2.0, label="LFP Beta/Gamma Power (AUC = 0.72)")
    ax_e2.plot([0, 1], [0, 1], color="gray", linestyle="--", linewidth=1.0, label="Chance (AUC = 0.50)")
    
    ax_e2.set_xlim(0, 1)
    ax_e2.set_ylim(0, 1)
    ax_e2.set_xlabel("False Positive Rate", fontsize=8.5)
    ax_e2.set_ylabel("True Positive Rate", fontsize=8.5)
    ax_e2.set_title("Out-Of-Fold ROC Curves (Slot P2 Omission)", fontsize=9, fontweight="bold")
    ax_e2.legend(fontsize=7.5, loc="lower right", frameon=True, facecolor="white")
    ax_e2.spines["top"].set_visible(False)
    ax_e2.spines["right"].set_visible(False)
    
    # Standing rule (2026-08-06): any figure containing placeholder/dummy content gets an
    # unmissable red title, in addition to (not replacing) the real title -- so no rendered
    # figure can be mistaken for a real result by a viewer who doesn't read the code.
    if used_placeholder[0]:
        fig.text(0.5, 0.995, "PLACEHOLDER-DUMMY", color="red", fontsize=20, fontweight="bold",
                 ha="center", va="top")

    # Save outputs
    plt.savefig(PNG_PATH, dpi=300, facecolor="#ffffff", edgecolor="none")
    plt.savefig(SVG_PATH, facecolor="#ffffff", edgecolor="none")
    plt.close()

    print(f"Successfully generated Figure 4:")
    print(f"  - PNG (300 DPI): {PNG_PATH}")
    print(f"  - SVG: {SVG_PATH}")
    if used_placeholder[0]:
        print("  WARNING: one or more panels used placeholder/dummy data -- 'PLACEHOLDER-DUMMY' "
             "title added per the 2026-08-06 standing rule. See panels B/C/D (conditional "
             "fallback) and E1/E2 (unconditional, no real-data path exists).")


if __name__ == "__main__":
    build_fig04()
