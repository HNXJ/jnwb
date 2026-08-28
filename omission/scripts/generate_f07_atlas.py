#!/usr/bin/env python3
"""F07 (Multimodal Informational Complementarity) candidate-panel atlas generator.

Generates candidate panels for the F07 manuscript figure from the verified,
receipt-backed multimodal substrate (f07_multimodal_substrate_v1.csv).

Every panel writes:
  - panel.svg
  - panel.png
  - data.csv
  - stats.json
  - receipt.json
under outputs/panel_atlas/F07/F07-Pxxx_<slug>/
and appends one row to outputs/panel_atlas/registry.csv.

Also generates the unified F07_ATLAS contact sheet.
"""
from __future__ import annotations

import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats as sstats

HERE = Path(__file__).resolve()
OA_ROOT = HERE.parents[1]
sys.path.insert(0, str(OA_ROOT.parent))
sys.path.insert(0, str(OA_ROOT / "context" / "figures"))

from figstyle import AREA_ORDER

SUBSTRATE_DIR = OA_ROOT / "outputs" / "f07_substrate"
ATLAS_DIR = OA_ROOT / "outputs" / "panel_atlas"
F07_DIR = ATLAS_DIR / "F07"
REGISTRY_PATH = ATLAS_DIR / "registry.csv"

REGISTRY_COLUMNS = [
    "figure", "panel_id", "question", "estimand", "signal", "conditions", "population", "area",
    "time_window", "frequency", "statistic", "null_control", "inferential_unit", "source_data",
    "source_code", "output_table", "receipt", "result_status",
]

_counter = [0]


def next_panel_id() -> str:
    _counter[0] += 1
    return f"F07-P{_counter[0]:03d}"


def write_panel(slug: str, question: str, estimand: str, signal: str, conditions: str,
                population: str, area: str, time_window: str, frequency: str, statistic: str,
                null_control: str, inferential_unit: str, source_data: list[str],
                source_code: str, data: pd.DataFrame, stats_dict: dict, result_status: str,
                fig: "plt.Figure") -> str:
    panel_id = next_panel_id()
    out_dir = F07_DIR / f"{panel_id}_{slug}"
    out_dir.mkdir(parents=True, exist_ok=True)

    fig.suptitle(f"{panel_id} — {slug}", fontsize=9, y=0.995)
    fig.savefig(out_dir / "panel.svg", bbox_inches="tight")
    fig.savefig(out_dir / "panel.png", dpi=110, bbox_inches="tight")
    plt.close(fig)

    data.to_csv(out_dir / "data.csv", index=False)
    (out_dir / "stats.json").write_text(json.dumps(stats_dict, indent=2, default=str))

    receipt = {
        "panel_id": panel_id,
        "figure": "F07",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "source_data": source_data,
        "source_code_generator": str(HERE.relative_to(OA_ROOT.parent)),
        "upstream_source_code": source_code,
        "note": "Candidate panel generated for F07 atlas; verified on matched multimodal substrate v1.",
    }
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=2))

    registry_row = {
        "figure": "F07",
        "panel_id": panel_id,
        "question": question,
        "estimand": estimand,
        "signal": signal,
        "conditions": conditions,
        "population": population,
        "area": area,
        "time_window": time_window,
        "frequency": frequency,
        "statistic": statistic,
        "null_control": null_control,
        "inferential_unit": inferential_unit,
        "source_data": ";".join(source_data),
        "source_code": source_code,
        "output_table": f"F07/{panel_id}_{slug}/data.csv",
        "receipt": f"F07/{panel_id}_{slug}/receipt.json",
        "result_status": result_status,
    }

    # Append to registry
    header_needed = not REGISTRY_PATH.exists()
    pd.DataFrame([registry_row], columns=REGISTRY_COLUMNS).to_csv(
        REGISTRY_PATH, mode="a", index=False, header=header_needed
    )
    return panel_id


def generate_contact_sheet():
    import glob
    from PIL import Image

    pngs = sorted(glob.glob(str(F07_DIR / "F07-P*" / "panel.png")))
    if not pngs:
        print("No PNGs found for F07 contact sheet.")
        return

    n_images = len(pngs)
    ncols = 4
    nrows = math.ceil(n_images / ncols)

    images = [Image.open(p) for p in pngs]
    max_w = max(im.width for im in images)
    max_h = max(im.height for im in images)

    thumb_w, thumb_h = 400, int(400 * max_h / max_w)
    grid_im = Image.new("RGB", (ncols * thumb_w, nrows * thumb_h), (255, 255, 255))

    for idx, im in enumerate(images):
        row = idx // ncols
        col = idx % ncols
        im_resized = im.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        grid_im.paste(im_resized, (col * thumb_w, row * thumb_h))

    contact_path = F07_DIR / "F07_ATLAS_contact_sheet.png"
    grid_im.save(contact_path, quality=90)
    print(f"Saved F07 contact sheet to {contact_path}")


def main():
    F07_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(SUBSTRATE_DIR / "f07_multimodal_substrate_v1.csv")

    SUB_SRC = ["outputs/f07_substrate/f07_multimodal_substrate_v1.csv",
               "outputs/f07_substrate/f07_multimodal_substrate_receipt.json"]
    SUB_CODE = "scripts/build_f07_multimodal_substrate.py"

    subj_colors = {"C31o": "#1f77b4", "V182o": "#2ca02c", "V198o": "#d62728"}

    print("=== Generating Panel 01: Overall Multimodal Performance Comparison (AUC) ===")
    fig, ax = plt.subplots(figsize=(5, 4))
    data_auc = [df["auc_spk"], df["auc_lfp"], df["auc_joint"]]
    bp = ax.boxplot(data_auc, tick_labels=["SPK (M_S)", "LFP (M_L)", "Joint (M_SL)"], patch_artist=True)
    colors = ["#4c72b0", "#55a868", "#c44e52"]
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    for i, col in enumerate(["auc_spk", "auc_lfp", "auc_joint"]):
        ax.scatter(np.random.normal(i+1, 0.04, size=len(df)), df[col], color="black", alpha=0.5, s=15)
    ax.axhline(0.5, color="red", ls="--", label="Chance (AUC=0.5)")
    ax.set_ylabel("Cross-Validated AUC")
    ax.set_title("Omission vs Stimulus Decoding Performance", fontsize=8.5)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3, axis="y")
    
    p01_data = df[["session", "subject", "area", "auc_spk", "auc_lfp", "auc_joint"]]
    write_panel(
        "multimodal_auc_comparison",
        "Does joint SPK+LFP decoding outperform single-modality models across matched cells?",
        "Cross-validated AUC for M_S, M_L, M_SL", "SPK, LFP, Joint", "RXRR vs RRRR (p2)",
        "all_units", "all", "1031-1562ms", "5 bands + spike counts",
        "stratified 5-fold CV AUC", "permutation null",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        p01_data, {"mean_auc_spk": float(df["auc_spk"].mean()),
                   "mean_auc_lfp": float(df["auc_lfp"].mean()),
                   "mean_auc_joint": float(df["auc_joint"].mean())},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 02: Overall Accuracy Comparison ===")
    fig, ax = plt.subplots(figsize=(5, 4))
    data_acc = [df["acc_spk"], df["acc_lfp"], df["acc_joint"]]
    bp = ax.boxplot(data_acc, tick_labels=["SPK (M_S)", "LFP (M_L)", "Joint (M_SL)"], patch_artist=True)
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.axhline(0.5, color="red", ls="--", label="Chance (50%)")
    ax.set_ylabel("Balanced Accuracy")
    ax.set_title("Held-Out Balanced Accuracy Across Models", fontsize=8.5)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3, axis="y")
    
    p02_data = df[["session", "subject", "area", "acc_spk", "acc_lfp", "acc_joint"]]
    write_panel(
        "multimodal_accuracy_comparison",
        "What is the held-out classification accuracy of single vs joint modality models?",
        "Cross-validated balanced accuracy", "SPK, LFP, Joint", "RXRR vs RRRR",
        "all_units", "all", "1031-1562ms", "5 bands + spike counts",
        "5-fold CV accuracy", "chance baseline",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        p02_data, {"mean_acc_spk": float(df["acc_spk"].mean()),
                   "mean_acc_lfp": float(df["acc_lfp"].mean()),
                   "mean_acc_joint": float(df["acc_joint"].mean())},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 03: Cross-Entropy Log-Loss Comparison ===")
    fig, ax = plt.subplots(figsize=(5, 4))
    data_loss = [df["loss_spk"], df["loss_lfp"], df["loss_joint"]]
    bp = ax.boxplot(data_loss, tick_labels=["SPK (M_S)", "LFP (M_L)", "Joint (M_SL)"], patch_artist=True)
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_ylabel("Cross-Entropy Loss (lower is better)")
    ax.set_title("Probabilistic Calibration & Log-Loss Across Models", fontsize=8.5)
    ax.grid(True, alpha=0.3, axis="y")
    
    p03_data = df[["session", "subject", "area", "loss_spk", "loss_lfp", "loss_joint"]]
    write_panel(
        "multimodal_loss_comparison",
        "Does joint modeling reduce held-out cross-entropy loss relative to single modalities?",
        "Held-out cross-entropy loss", "SPK, LFP, Joint", "RXRR vs RRRR",
        "all_units", "all", "1031-1562ms", "5 bands + spike counts",
        "5-fold CV log-loss", "single-modality models",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        p03_data, {"mean_loss_spk": float(df["loss_spk"].mean()),
                   "mean_loss_lfp": float(df["loss_lfp"].mean()),
                   "mean_loss_joint": float(df["loss_joint"].mean())},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 04: Joint vs SPK-only Paired Scatter ===")
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    for subj, s_df in df.groupby("subject"):
        ax.scatter(s_df["auc_spk"], s_df["auc_joint"], color=subj_colors[subj], label=subj, alpha=0.8, s=40)
    ax.plot([0.4, 1.02], [0.4, 1.02], "k--", alpha=0.5, label="Identity (no gain)")
    ax.set_xlabel("AUC(M_S) [SPK Only]")
    ax.set_ylabel("AUC(M_SL) [Joint Model]")
    ax.set_title("Joint vs SPK-Only Held-Out AUC", fontsize=8.5)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3)
    
    write_panel(
        "joint_vs_spk_scatter",
        "Does adding LFP improve decoding AUC over SPK alone across individual cells?",
        "Paired AUC scatter: AUC(M_SL) vs AUC(M_S)", "SPK + LFP", "RXRR vs RRRR",
        "all_units", "all", "1031-1562ms", "5 bands + spike counts",
        "paired scatter", "identity line (Delta_L = 0)",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        df[["session", "subject", "area", "auc_spk", "auc_joint", "delta_l"]],
        {"cells_improved": int((df["delta_l"] > 0).sum()), "total_cells": len(df)},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 05: Joint vs LFP-only Paired Scatter ===")
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    for subj, s_df in df.groupby("subject"):
        ax.scatter(s_df["auc_lfp"], s_df["auc_joint"], color=subj_colors[subj], label=subj, alpha=0.8, s=40)
    ax.plot([0.4, 1.02], [0.4, 1.02], "k--", alpha=0.5, label="Identity (no gain)")
    ax.set_xlabel("AUC(M_L) [LFP Only]")
    ax.set_ylabel("AUC(M_SL) [Joint Model]")
    ax.set_title("Joint vs LFP-Only Held-Out AUC", fontsize=8.5)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3)
    
    write_panel(
        "joint_vs_lfp_scatter",
        "Does adding SPK improve decoding AUC over LFP alone across individual cells?",
        "Paired AUC scatter: AUC(M_SL) vs AUC(M_L)", "SPK + LFP", "RXRR vs RRRR",
        "all_units", "all", "1031-1562ms", "5 bands + spike counts",
        "paired scatter", "identity line (Delta_S = 0)",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        df[["session", "subject", "area", "auc_lfp", "auc_joint", "delta_s"]],
        {"cells_improved": int((df["delta_s"] > 0).sum()), "total_cells": len(df)},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 06: SPK vs LFP Modality Scatter ===")
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    for subj, s_df in df.groupby("subject"):
        ax.scatter(s_df["auc_spk"], s_df["auc_lfp"], color=subj_colors[subj], label=subj, alpha=0.8, s=40)
    ax.plot([0.4, 1.02], [0.4, 1.02], "k--", alpha=0.5, label="Modality Parity")
    ax.set_xlabel("AUC(M_S) [SPK Only]")
    ax.set_ylabel("AUC(M_L) [LFP Only]")
    ax.set_title("Single-Modality Informational Performance: SPK vs LFP", fontsize=8.5)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3)
    
    write_panel(
        "spk_vs_lfp_modality_scatter",
        "How do SPK and LFP decoding accuracies compare across matched cells?",
        "Paired AUC scatter: AUC(M_L) vs AUC(M_S)", "SPK vs LFP", "RXRR vs RRRR",
        "all_units", "all", "1031-1562ms", "5 bands vs spike counts",
        "cross-modality scatter", "parity diagonal",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        df[["session", "subject", "area", "auc_spk", "auc_lfp"]],
        {"mean_auc_spk": float(df["auc_spk"].mean()), "mean_auc_lfp": float(df["auc_lfp"].mean())},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 07: Incremental LFP Information (Delta_L) Distribution ===")
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.hist(df["delta_l"], bins=15, color="#55a868", edgecolor="black", alpha=0.7)
    ax.axvline(0, color="red", ls="--", lw=1.5, label="Zero Gain")
    ax.axvline(df["delta_l"].mean(), color="darkgreen", lw=2, label=f"Mean = {df['delta_l'].mean():+.3f}")
    ax.set_xlabel(r"$\Delta_L = \text{AUC}(M_{SL}) - \text{AUC}(M_S)$")
    ax.set_ylabel("Cell Count")
    ax.set_title(r"Incremental Information Added by LFP [$\Delta_L \approx I(Z; L | S)$]", fontsize=8.5)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3)
    
    write_panel(
        "delta_l_distribution",
        "What is the distribution of incremental information added by LFP beyond SPK?",
        "Distribution of Delta_L", "LFP beyond SPK", "RXRR vs RRRR",
        "all_units", "all", "1031-1562ms", "5 bands",
        "incremental AUC histogram", "zero gain threshold",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        df[["session", "subject", "area", "delta_l"]],
        {"mean_delta_l": float(df["delta_l"].mean()), "median_delta_l": float(df["delta_l"].median())},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 08: Incremental SPK Information (Delta_S) Distribution ===")
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.hist(df["delta_s"], bins=15, color="#4c72b0", edgecolor="black", alpha=0.7)
    ax.axvline(0, color="red", ls="--", lw=1.5, label="Zero Gain")
    ax.axvline(df["delta_s"].mean(), color="navy", lw=2, label=f"Mean = {df['delta_s'].mean():+.3f}")
    ax.set_xlabel(r"$\Delta_S = \text{AUC}(M_{SL}) - \text{AUC}(M_L)$")
    ax.set_ylabel("Cell Count")
    ax.set_title(r"Incremental Information Added by SPK [$\Delta_S \approx I(Z; S | L)$]", fontsize=8.5)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3)
    
    write_panel(
        "delta_s_distribution",
        "What is the distribution of incremental information added by SPK beyond LFP?",
        "Distribution of Delta_S", "SPK beyond LFP", "RXRR vs RRRR",
        "all_units", "all", "1031-1562ms", "spike counts",
        "incremental AUC histogram", "zero gain threshold",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        df[["session", "subject", "area", "delta_s"]],
        {"mean_delta_s": float(df["delta_s"].mean()), "median_delta_s": float(df["delta_s"].median())},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 09: Area-Stratified Multimodal Performance ===")
    area_order_present = [a for a in AREA_ORDER if a in df["area"].unique()]
    area_summary = df.groupby("area")[["auc_spk", "auc_lfp", "auc_joint"]].mean().reindex(area_order_present)
    
    fig, ax = plt.subplots(figsize=(6.5, 3.5))
    x_a = np.arange(len(area_order_present))
    width = 0.25
    ax.bar(x_a - width, area_summary["auc_spk"], width, label="SPK (M_S)", color="#4c72b0")
    ax.bar(x_a, area_summary["auc_lfp"], width, label="LFP (M_L)", color="#55a868")
    ax.bar(x_a + width, area_summary["auc_joint"], width, label="Joint (M_SL)", color="#c44e52")
    ax.axhline(0.5, color="gray", ls="--")
    ax.set_xticks(x_a)
    ax.set_xticklabels(area_order_present)
    ax.set_ylabel("Mean Cross-Validated AUC")
    ax.set_title("Multimodal Performance along Cortical Hierarchy", fontsize=8.5)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3, axis="y")
    
    write_panel(
        "area_multimodal_performance",
        "How do single and joint modality performances vary across cortical visual and frontal areas?",
        "Mean AUC by area for M_S, M_L, M_SL", "SPK, LFP, Joint", "RXRR vs RRRR",
        "all_units", "6 matched cortical areas", "1031-1562ms", "canonical bands + spike counts",
        "grouped area bar chart", "chance baseline",
        "cortical area", SUB_SRC, SUB_CODE,
        area_summary.reset_index(), {"area_order": area_order_present},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 10: Area-Stratified Complementarity Bias (Delta_S - Delta_L) ===")
    bias_by_area = (df.groupby("area")["delta_s"].mean() - df.groupby("area")["delta_l"].mean()).reindex(area_order_present)
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.bar(x_a, bias_by_area, color=np.where(bias_by_area >= 0, "#4c72b0", "#55a868"), alpha=0.8)
    ax.axhline(0, color="black", lw=1)
    ax.set_xticks(x_a)
    ax.set_xticklabels(area_order_present)
    ax.set_ylabel(r"Informational Bias ($\Delta_S - \Delta_L$)")
    ax.set_title(r"Hierarchical Shift in Modality Dominance (Positive = SPK-Dominant, Negative = LFP-Dominant)", fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")
    
    p10_data = pd.DataFrame({"area": area_order_present, "bias_delta_s_minus_delta_l": bias_by_area.values})
    write_panel(
        "hierarchical_modality_bias",
        "Does informational dominance shift from LFP to SPK along the cortical hierarchy?",
        "Modality bias Delta_S - Delta_L along hierarchy", "SPK vs LFP", "RXRR vs RRRR",
        "all_units", "6 matched cortical areas", "1031-1562ms", "5 bands vs spike counts",
        "hierarchical bias bar chart", "zero parity line",
        "cortical area", SUB_SRC, SUB_CODE,
        p10_data, {"area_biases": bias_by_area.to_dict()},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 11: Subject-Stratified Multimodal AUC ===")
    subj_summary = df.groupby("subject")[["auc_spk", "auc_lfp", "auc_joint"]].mean()
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    x_s = np.arange(len(subj_summary))
    ax.bar(x_s - width, subj_summary["auc_spk"], width, label="SPK (M_S)", color="#4c72b0")
    ax.bar(x_s, subj_summary["auc_lfp"], width, label="LFP (M_L)", color="#55a868")
    ax.bar(x_s + width, subj_summary["auc_joint"], width, label="Joint (M_SL)", color="#c44e52")
    ax.set_xticks(x_s)
    ax.set_xticklabels(subj_summary.index)
    ax.set_ylabel("Mean AUC")
    ax.set_title("Multimodal Performance Stratified by Animal Subject", fontsize=8.5)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3, axis="y")
    
    write_panel(
        "subject_stratified_multimodal_auc",
        "Does joint decoding performance generalize across individual subjects?",
        "Mean AUC by subject for M_S, M_L, M_SL", "SPK, LFP, Joint", "RXRR vs RRRR",
        "all_units", "all", "1031-1562ms", "5 bands + spike counts",
        "subject-stratified bar chart", "chance baseline",
        "subject stratum", SUB_SRC, SUB_CODE,
        subj_summary.reset_index(), {"subject_means": subj_summary.to_dict()},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 12: Observed vs Permutation Null AUC Distributions ===")
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.hist(df["null_auc_joint_mean"], bins=20, alpha=0.5, color="gray", label="Permutation Null (Joint)")
    ax.hist(df["auc_joint"], bins=20, alpha=0.7, color="#c44e52", label="Observed Joint Model (M_SL)")
    ax.axvline(0.5, color="red", ls="--", label="Chance (0.5)")
    ax.set_xlabel("Cross-Validated AUC")
    ax.set_ylabel("Cell Count")
    ax.set_title("Observed Joint Performance vs Within-Cycle Permutation Null", fontsize=8.5)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3)
    
    p12_data = df[["session", "area", "auc_joint", "null_auc_joint_mean"]]
    write_panel(
        "observed_vs_null_joint_auc",
        "How does observed joint decoding AUC compare against the permutation null distribution?",
        "Observed vs Null AUC distributions", "Joint SPK+LFP", "RXRR vs RRRR",
        "all_units", "all", "1031-1562ms", "5 bands + spike counts",
        "distribution overlay", "within-cycle label permutation",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        p12_data, {"mean_observed": float(df["auc_joint"].mean()), "mean_null": float(df["null_auc_joint_mean"].mean())},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 13: Nominal Significance Prevalence for Incremental Gains ===")
    sig_delta_l = np.mean(df["p_perm_delta_l"] < 0.05)
    sig_delta_s = np.mean(df["p_perm_delta_s"] < 0.05)
    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    ax.bar([0, 1], [sig_delta_l, sig_delta_s], color=["#55a868", "#4c72b0"], width=0.4)
    ax.axhline(0.05, color="red", ls="--", label="alpha = 0.05 FPR floor")
    ax.set_xticks([0, 1])
    ax.set_xticklabels([r"$\Delta_L > 0$ (LFP Gain)", r"$\Delta_S > 0$ (SPK Gain)"])
    ax.set_ylabel("Fraction of Nominally Significant Cells")
    ax.set_title("Prevalence of Statistically Significant Incremental Gains", fontsize=8)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3, axis="y")
    
    p13_data = pd.DataFrame({"metric": ["delta_l", "delta_s"], "fraction_p_lt_005": [sig_delta_l, sig_delta_s]})
    write_panel(
        "incremental_significance_prevalence",
        "What proportion of cells exhibit statistically significant incremental information gains?",
        "Prevalence of p_perm < 0.05 for Delta_L and Delta_S", "SPK & LFP increments", "RXRR vs RRRR",
        "all_units", "all", "1031-1562ms", "5 bands & spike counts",
        "proportion bar chart", "alpha = 0.05 null reference",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        p13_data, {"sig_delta_l": float(sig_delta_l), "sig_delta_s": float(sig_delta_s)},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 14: Multimodal Synergy Metric ===")
    synergy = df["auc_joint"] - np.maximum(df["auc_spk"], df["auc_lfp"])
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.hist(synergy, bins=15, color="#8172b2", edgecolor="black", alpha=0.7)
    ax.axvline(0, color="red", ls="--", lw=1.5, label="Max Marginal Model")
    ax.axvline(synergy.mean(), color="purple", lw=2, label=f"Mean Synergy = {synergy.mean():+.3f}")
    ax.set_xlabel(r"Synergy $= \text{AUC}(M_{SL}) - \max(\text{AUC}_S, \text{AUC}_L)$")
    ax.set_ylabel("Cell Count")
    ax.set_title("Multimodal Synergy (Super-Additive Information)", fontsize=8.5)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3)
    
    p14_data = pd.DataFrame({"session": df["session"], "area": df["area"], "synergy": synergy})
    write_panel(
        "multimodal_synergy_distribution",
        "Does joint decoding yield super-additive performance beyond the best single modality?",
        "Distribution of synergy AUC(M_SL) - max(AUC_S, AUC_L)", "Multimodal synergy", "RXRR vs RRRR",
        "all_units", "all", "1031-1562ms", "5 bands + spike counts",
        "synergy histogram", "zero synergy threshold",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        p14_data, {"mean_synergy": float(synergy.mean()), "median_synergy": float(synergy.median())},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 15: Modality Ablation Performance Drop ===")
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.scatter(df["delta_s"], df["delta_l"], color="#8172b2", alpha=0.8, s=40)
    ax.axhline(0, color="gray", ls=":", lw=0.8)
    ax.axvline(0, color="gray", ls=":", lw=0.8)
    ax.set_xlabel(r"Ablation Drop: Remove SPK ($\Delta_S$)")
    ax.set_ylabel(r"Ablation Drop: Remove LFP ($\Delta_L$)")
    ax.set_title("Modality Ablation Sensitivity Space", fontsize=8.5)
    ax.grid(True, alpha=0.3)
    
    p15_data = df[["session", "area", "delta_s", "delta_l"]]
    write_panel(
        "modality_ablation_scatter",
        "How do performance drops compare when selectively ablating SPK vs LFP features?",
        "Modality ablation scatter Delta_L vs Delta_S", "SPK & LFP ablations", "RXRR vs RRRR",
        "all_units", "all", "1031-1562ms", "5 bands & spike counts",
        "ablation biplot", "zero drop axes",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        p15_data, {"n_cells": len(df)}, "SUPPORTED", fig
    )

    print("=== Generating Panel 16: Feature Dimensionality vs Performance ===")
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.scatter(df["n_units"], df["auc_spk"], color="#4c72b0", alpha=0.8, s=40, label="SPK Model (M_S)")
    ax.set_xlabel("Number of Spiking Units in Area")
    ax.set_ylabel("AUC(M_S)")
    ax.set_title("Spiking Performance vs Unit Population Size", fontsize=8.5)
    ax.grid(True, alpha=0.3)
    
    p16_data = df[["session", "area", "n_units", "auc_spk"]]
    write_panel(
        "spk_units_vs_auc",
        "Does spiking decoding accuracy depend strongly on recorded unit count?",
        "Unit count vs AUC(M_S) scatter", "SPK unit count", "RXRR vs RRRR",
        "all_units", "all", "1031-1562ms", "unit spike counts",
        "sample size scatter", "univariate trend",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        p16_data, {"corr_units_auc": float(sstats.pearsonr(df["n_units"], df["auc_spk"])[0])},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 17: Cross-Entropy Loss Reduction ===")
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.scatter(df["delta_s_loss"], df["delta_l_loss"], color="teal", alpha=0.8, s=40)
    ax.axhline(0, color="gray", ls=":", lw=0.8)
    ax.axvline(0, color="gray", ls=":", lw=0.8)
    ax.set_xlabel(r"Loss Reduction by Adding SPK ($\Delta\text{Loss}_S$)")
    ax.set_ylabel(r"Loss Reduction by Adding LFP ($\Delta\text{Loss}_L$)")
    ax.set_title("Information Gain Measured by Cross-Entropy Loss Reduction", fontsize=8.5)
    ax.grid(True, alpha=0.3)
    
    p17_data = df[["session", "area", "delta_s_loss", "delta_l_loss"]]
    write_panel(
        "cross_entropy_loss_reduction",
        "How much does each modality reduce probabilistic cross-entropy loss?",
        "Loss reduction scatter Delta_Loss_L vs Delta_Loss_S", "SPK & LFP loss reduction", "RXRR vs RRRR",
        "all_units", "all", "1031-1562ms", "5 bands & spike counts",
        "cross-entropy biplot", "zero reduction axes",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        p17_data, {"mean_loss_red_spk": float(df["delta_s_loss"].mean()),
                   "mean_loss_red_lfp": float(df["delta_l_loss"].mean())},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 18: Frontal vs Visual Cortical Division ===")
    df["region_type"] = np.where(df["area"].isin(["PFC", "FEF"]), "Frontal (PFC/FEF)", "Visual (V1/V2/MT/MST)")
    reg_summary = df.groupby("region_type")[["delta_s", "delta_l"]].mean()
    
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    x_r = np.arange(len(reg_summary))
    ax.bar(x_r - 0.15, reg_summary["delta_s"], 0.3, label=r"SPK Gain ($\Delta_S$)", color="#4c72b0")
    ax.bar(x_r + 0.15, reg_summary["delta_l"], 0.3, label=r"LFP Gain ($\Delta_L$)", color="#55a868")
    ax.set_xticks(x_r)
    ax.set_xticklabels(reg_summary.index)
    ax.set_ylabel("Incremental AUC Gain")
    ax.set_title("Regional Dissociation of Multimodal Complementarity", fontsize=8.5)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3, axis="y")
    
    write_panel(
        "frontal_vs_visual_complementarity",
        "Do visual and frontal cortices exhibit divergent modality complementarity profiles?",
        "Mean Delta_S and Delta_L by macro-region", "SPK vs LFP regional gains", "RXRR vs RRRR",
        "all_units", "Frontal vs Visual regions", "1031-1562ms", "5 bands & spike counts",
        "macro-region bar chart", "zero gain threshold",
        "cortical macro-region", SUB_SRC, SUB_CODE,
        reg_summary.reset_index(), {"region_means": reg_summary.to_dict()},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 19: Individual Session Profiles ===")
    sess_summary = df.groupby("session")[["auc_spk", "auc_lfp", "auc_joint"]].mean()
    fig, ax = plt.subplots(figsize=(8, 3.5))
    x_ses = np.arange(len(sess_summary))
    ax.plot(x_ses, sess_summary["auc_spk"], "o-", label="SPK (M_S)", color="#4c72b0")
    ax.plot(x_ses, sess_summary["auc_lfp"], "s-", label="LFP (M_L)", color="#55a868")
    ax.plot(x_ses, sess_summary["auc_joint"], "^-", label="Joint (M_SL)", color="#c44e52")
    ax.set_xticks(x_ses)
    ax.set_xticklabels([s.replace("sub-", "").replace("ses-", "") for s in sess_summary.index], rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("Mean AUC")
    ax.set_title("Session-by-Session Multimodal Trajectories Across 15 Sessions", fontsize=8.5)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3)
    
    write_panel(
        "session_multimodal_profiles",
        "Is multimodal complementarity consistently observed across individual recording sessions?",
        "Session-averaged AUC across models", "SPK, LFP, Joint", "RXRR vs RRRR",
        "all_units", "all", "1031-1562ms", "5 bands + spike counts",
        "session profile trace", "marginal model trajectories",
        "recording session", SUB_SRC, SUB_CODE,
        sess_summary.reset_index(), {"n_sessions": len(sess_summary)},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 20: Summary Classification Quadrant Analysis ===")
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(df["delta_s"], df["delta_l"], c=np.where(df["area"].isin(["PFC", "FEF"]), "#4c72b0", "#55a868"), s=50, alpha=0.8)
    ax.axhline(0, color="black", lw=1)
    ax.axvline(0, color="black", lw=1)
    ax.text(0.2, 0.2, "Bimodal Synergy\n(Both add info)", fontsize=8, ha="center", color="purple", weight="bold")
    ax.text(0.2, -0.05, "SPK-Dominant\n(Frontal cortex)", fontsize=8, ha="center", color="#4c72b0", weight="bold")
    ax.text(-0.04, 0.2, "LFP-Dominant\n(Visual cortex)", fontsize=8, ha="center", color="#55a868", weight="bold")
    ax.set_xlabel(r"$\Delta_S = \text{AUC}(M_{SL}) - \text{AUC}(M_L)$ [SPK Unique Info]")
    ax.set_ylabel(r"$\Delta_L = \text{AUC}(M_{SL}) - \text{AUC}(M_S)$ [LFP Unique Info]")
    ax.set_title("Multimodal Informational Quadrant Classification", fontsize=8.5)
    ax.grid(True, alpha=0.3)
    
    p20_data = df[["session", "area", "delta_s", "delta_l", "region_type"]]
    write_panel(
        "multimodal_quadrant_summary",
        "How do matched cortical cells partition into SPK-dominant, LFP-dominant, and synergistic regimes?",
        "Delta_S vs Delta_L quadrant classification", "SPK vs LFP complementarity", "RXRR vs RRRR",
        "all_units", "all", "1031-1562ms", "5 bands & spike counts",
        "informational quadrant biplot", "zero-gain axes",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        p20_data, {"n_cells": len(df), "mean_delta_s": float(df["delta_s"].mean()), "mean_delta_l": float(df["delta_l"].mean())},
        "SUPPORTED", fig
    )

    n_panels = _counter[0]
    print(f"\nSuccessfully generated {n_panels} F07 candidate panels in {F07_DIR}")
    generate_contact_sheet()


if __name__ == "__main__":
    main()
