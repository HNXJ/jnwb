#!/usr/bin/env python3
"""Render Figure 4 exclusively from leakage-safe persisted artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import auc, confusion_matrix, roc_curve

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = Path(
    os.environ.get(
        "OMISSION_FIG04_CLASSIFICATION_DIR", str(REPO / "outputs" / "classification")
    )
)
FIGURE_DIR = Path(os.environ.get("OMISSION_FIG04_OUTPUT_DIR", str(HERE)))
SVG = FIGURE_DIR / "svg"

sys.path.insert(0, str(REPO / "context" / "figures"))
from figstats import paired_location, write  # noqa: E402


AREAS = ["FEF", "PFC", "TEO", "V4", "V3", "V2", "V1"]
SLOTS = ["p2", "p3", "p4"]
LABELS = ["A", "B", "R"]
PALETTE = ["#CFB87C", "#2563EB", "#8F00FF", "#DC2626", "#16A34A", "#000000",
           "#FF1493", "#8B4513", "#00FFCC", "#FF5E00", "#C9A88A", "#D3D3D3", "#FFFFFF"]
AREA_COLORS = {area: PALETTE[i % len(PALETTE)] for i, area in enumerate(AREAS)}
SLOT_COLORS = {"p2": PALETTE[0], "p3": PALETTE[2], "p4": PALETTE[1]}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    files = {
        "cells": OUT / "omission_identity_leakage_safe_cells.csv",
        "oof": OUT / "omission_identity_leakage_safe_oof.csv",
        "folds": OUT / "omission_identity_leakage_safe_folds.csv",
        "null": OUT / "omission_identity_leakage_safe_null.csv",
        "analysis_receipt": OUT / "omission_identity_leakage_safe_receipt.json",
    }
    missing = [str(path) for path in files.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Figure 4 inputs missing: " + ", ".join(missing))
    receipt = json.loads(files["analysis_receipt"].read_text(encoding="utf-8"))
    if receipt.get("analysis_status") != "complete":
        raise RuntimeError("Figure 4 refuses a non-complete leakage-safe analysis receipt")
    cells = pd.read_csv(files["cells"])
    oof = pd.read_csv(files["oof"])
    cells = cells[cells["status"] == "success"].copy()
    if cells.empty or oof.empty:
        raise RuntimeError("Figure 4 has no successful leakage-safe observations to render")
    return cells, oof, receipt, files


def _panel_a(ax):
    ax.set_axis_off()
    ax.text(0.0, 1.04, "A", transform=ax.transAxes, fontsize=13, fontweight="bold")
    ax.text(
        0.04,
        0.94,
        "Omitted-identity contrast",
        transform=ax.transAxes,
        fontsize=10,
        fontweight="bold",
    )
    sequences = [
        ("AXAB", ["A", "X(A)", "A", "B"], PALETTE[3]),
        ("BXBA", ["B", "X(B)", "B", "A"], PALETTE[1]),
        ("RXRR", ["R", "X(R)", "R", "R"], PALETTE[11]),
    ]
    for row, (name, slots, color) in enumerate(sequences):
        y = 0.70 - row * 0.25
        ax.text(0.02, y + 0.06, name, transform=ax.transAxes, color=color,
                fontsize=8.5, fontweight="bold")
        for col, label in enumerate(slots):
            x = 0.28 + col * 0.17
            omitted = label.startswith("X")
            ax.add_patch(
                plt.Rectangle(
                    (x, y), 0.13, 0.16, transform=ax.transAxes,
                    facecolor=PALETTE[12] if not omitted else PALETTE[0],
                    edgecolor=color if omitted else PALETTE[11],
                    linewidth=1.5 if omitted else 1.0,
                )
            )
            ax.text(x + 0.065, y + 0.08, label, transform=ax.transAxes,
                    ha="center", va="center", fontsize=7.5,
                    color=color if omitted else PALETTE[5])
    ax.text(
        0.02,
        0.02,
        "SPK/SUA counts; P1-aligned trials; leave-one-temporal-cycle-out CV",
        transform=ax.transAxes,
        fontsize=7.5,
        color=PALETTE[5],
    )


def _panel_b(ax, cells):
    ax.text(-0.12, 1.05, "B", transform=ax.transAxes, fontsize=13, fontweight="bold")
    means = cells.groupby(["slot_key", "area"])["accuracy_loco_balanced"].mean().reset_index()
    for area in AREAS:
        part = means[means["area"] == area].set_index("slot_key").reindex(SLOTS)
        if part["accuracy_loco_balanced"].notna().any():
            ax.plot(
                SLOTS,
                part["accuracy_loco_balanced"],
                marker="o",
                linewidth=1.4,
                label=area,
                color=AREA_COLORS[area],
            )
    ax.axhline(0.5, color=PALETTE[11], linestyle="--", linewidth=1.0, label="Chance")
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Balanced accuracy")
    ax.set_title("Cycle-safe decoding by omission slot")
    ax.legend(fontsize=6.5, ncol=2, frameon=False)


def _panel_c(ax, cells):
    ax.text(-0.12, 1.05, "C", transform=ax.transAxes, fontsize=13, fontweight="bold")
    pivot = cells.pivot_table(
        index="area", columns="slot_key", values="accuracy_loco_balanced", aggfunc="mean"
    ).reindex(index=AREAS, columns=SLOTS)
    image = ax.imshow(pivot.to_numpy(float), vmin=0.0, vmax=1.0, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(SLOTS)), ["P2", "P3", "P4"])
    ax.set_yticks(range(len(AREAS)), AREAS)
    ax.set_title("Session-mean balanced accuracy")
    ax.set_xlabel("Omitted slot")
    ax.set_ylabel("Area")
    for row in range(len(AREAS)):
        for col in range(len(SLOTS)):
            value = pivot.iloc[row, col]
            if np.isfinite(value):
                ax.text(col, row, f"{value:.2f}", ha="center", va="center",
                        color=PALETTE[12] if value > 0.55 else PALETTE[5], fontsize=7)
    plt.colorbar(image, ax=ax, shrink=0.78, label="Balanced accuracy")


def _panel_d(ax, cells):
    ax.text(-0.12, 1.05, "D", transform=ax.transAxes, fontsize=13, fontweight="bold")
    data = [
        cells.loc[cells["area"] == area, "accuracy_loco_balanced"].dropna().to_numpy()
        for area in AREAS
    ]
    usable = [(area, values) for area, values in zip(AREAS, data) if len(values)]
    if not usable:
        raise RuntimeError("No area-level leakage-safe observations for Panel D")
    ax.boxplot(
        [values for _, values in usable],
        tick_labels=[area for area, _ in usable],
        patch_artist=True,
        boxprops={"facecolor": PALETTE[12], "edgecolor": PALETTE[5]},
        medianprops={"color": PALETTE[3]},
    )
    ax.axhline(0.5, color=PALETTE[11], linestyle="--", linewidth=1.0)
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Balanced accuracy")
    ax.set_title("Session/slot distribution by area")


def _panel_e1(ax, oof):
    ax.text(-0.12, 1.05, "E1", transform=ax.transAxes, fontsize=13, fontweight="bold")
    multi = oof[oof["analysis"] == "multiclass"].dropna(subset=["y_true", "y_pred"])
    if multi.empty:
        raise RuntimeError("No multiclass held-out predictions for Panel E1")
    matrix = confusion_matrix(
        multi["y_true"].astype(int), multi["y_pred"].astype(int), labels=[0, 1, 2]
    ).astype(float)
    matrix /= np.maximum(matrix.sum(axis=1, keepdims=True), 1.0)
    image = ax.imshow(matrix, cmap="Blues", vmin=0.0, vmax=1.0)
    ax.set_xticks(range(3), LABELS)
    ax.set_yticks(range(3), LABELS)
    ax.set_xlabel("Predicted identity")
    ax.set_ylabel("True identity")
    ax.set_title("Pooled held-out confusion matrix")
    for row in range(3):
        for col in range(3):
            ax.text(col, row, f"{matrix[row, col]:.2f}", ha="center", va="center",
                    color=PALETTE[12] if matrix[row, col] > 0.55 else PALETTE[5])
    plt.colorbar(image, ax=ax, shrink=0.78, label="Row proportion")


def _panel_e2(ax, oof):
    ax.text(-0.12, 1.05, "E2", transform=ax.transAxes, fontsize=13, fontweight="bold")
    binary = oof[oof["analysis"] == "binary"].dropna(subset=["y_true", "decision_score"])
    if binary.empty or binary["y_true"].nunique() < 2:
        raise RuntimeError("No binary held-out predictions for Panel E2")
    fpr, tpr, _ = roc_curve(binary["y_true"].astype(int), binary["decision_score"])
    auc_value = auc(fpr, tpr)
    ax.plot(fpr, tpr, color=PALETTE[1], linewidth=2.0, label=f"SPK/SUA AUC = {auc_value:.3f}")
    ax.plot([0, 1], [0, 1], color=PALETTE[11], linestyle="--", label="Chance")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("False-positive rate")
    ax.set_ylabel("True-positive rate")
    ax.set_title("Pooled held-out ROC (descriptive)")
    ax.legend(fontsize=7, frameon=False)


def _write_stats(cells):
    results = []
    for slot in SLOTS:
        session_values = (
            cells[cells["slot_key"] == slot]
            .groupby("session")["accuracy_loco_balanced"]
            .mean()
            .dropna()
            .to_numpy()
        )
        if len(session_values):
            results.append(
                paired_location(
                    session_values,
                    np.full(len(session_values), 0.5),
                    figure="fig04",
                    panel="B/C",
                    question=f"Cycle-safe {slot} decoding differs from chance",
                    unit="session",
                    family="fig04_cycle_safe_slots",
                    note="Session is the inferential unit; area cells are averaged within session.",
                )
            )
    return write(
        results,
        str(SVG),
        "fig04",
        "Figure 4 leakage-safe decoding statistics",
        preamble=(
            "All quantitative panels use outputs/classification/omission_identity_leakage_safe_*."
            " The random-CV diagnostic is excluded from the plotted inferential evidence."
        ),
    )


def build_fig04() -> Path:
    cells, oof, analysis_receipt, input_files = _require_inputs()
    SVG.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(13.0, 11.5), dpi=300, facecolor=PALETTE[12])
    gs = fig.add_gridspec(
        3, 2, height_ratios=[1.0, 1.2, 1.1], hspace=0.38, wspace=0.28,
        left=0.07, right=0.96, top=0.93, bottom=0.06,
    )
    axes = [fig.add_subplot(gs[row, col]) for row in range(3) for col in range(2)]
    fig.suptitle(
        "Figure 4: Leakage-Safe Omitted-Identity Decoding (SPK/SUA)",
        fontsize=12, fontweight="bold", y=0.98, x=0.07, ha="left",
    )
    _panel_a(axes[0])
    _panel_b(axes[1], cells)
    _panel_c(axes[2], cells)
    _panel_d(axes[3], cells)
    _panel_e1(axes[4], oof)
    _panel_e2(axes[5], oof)

    png_path = FIGURE_DIR / "fig04.png"
    svg_path = FIGURE_DIR / "fig04.svg"
    plt.savefig(png_path, dpi=300, facecolor=PALETTE[12], edgecolor="none")
    plt.savefig(svg_path, facecolor=PALETTE[12], edgecolor="none")
    plt.close(fig)
    stats_csv, stats_md = _write_stats(cells)

    figure_receipt = {
        "status": "complete",
        "git_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "analysis_receipt": str(input_files["analysis_receipt"]),
        "analysis_receipt_sha256": _sha256(input_files["analysis_receipt"]),
        "panel_inputs": {
            "A": {"input": "task constants in renderer", "estimator": "schematic only"},
            "B": {"input": str(input_files["cells"]), "estimator": "mean by slot/area"},
            "C": {"input": str(input_files["cells"]), "estimator": "session mean by area/slot"},
            "D": {"input": str(input_files["cells"]), "estimator": "session/slot distribution"},
            "E1": {"input": str(input_files["oof"]), "estimator": "pooled multiclass held-out confusion"},
            "E2": {"input": str(input_files["oof"]), "estimator": "pooled binary held-out ROC"},
        },
        "outputs": {
            "png": str(png_path),
            "svg": str(svg_path),
            "stats_csv": str(stats_csv),
            "stats_md": str(stats_md),
        },
        "output_hashes": {
            "png": _sha256(png_path),
            "svg": _sha256(svg_path),
            "stats_csv": _sha256(Path(stats_csv)),
            "stats_md": _sha256(Path(stats_md)),
        },
        "receipt_hash_scope": "receipt hash intentionally excludes this JSON file",
        "scientific_scope": "SPK/SUA only; no LFP decoding claim",
        "random_cv_diagnostic": "excluded from confirmatory panels",
    }
    receipt_path = SVG / "fig04_provenance_receipt.json"
    receipt_path.write_text(json.dumps(figure_receipt, indent=2), encoding="utf-8")
    print(f"Rendered {svg_path}")
    return svg_path


if __name__ == "__main__":
    build_fig04()
