#!/usr/bin/env python3
"""F04 (SPK information) candidate-panel atlas generator.

Generates candidate panels for the new manuscript F04 coordinate system from *already-computed,
receipt-backed* outputs -- no new model fitting or decoding happens here. Per the atlas-phase
directive: candidate generation is for scientific coverage, not significance fishing; null and
negative panels are saved with the same provenance as positive ones and never discarded for
being nonsignificant.

Source data (all pre-existing, `analysis_status: complete` in their own receipts):
  - omission_identity_leakage_safe_{cells,oof,null}.csv  (2026-08-21) -- the corpus-wide
    leakage-safe spike identity decoding this session's evidence review found and verified null.
  - fig04_encoding_matrix_{cells,ablation,crossposition}.csv (2026-08-21) -- multi-target
    (Y_stim/Y_omit/Y_pos/Y_prev) encoding performance, SSA-decile ablation, cross-position
    generalization.
  - fig04_class_knockout_cells.csv (2026-08-21) -- per-functional-class knockout effect on the
    same four targets.

Every panel writes panel.svg + panel.png + data.csv + stats.json + receipt.json under
outputs/panel_atlas/F04/F04-Pxxx_<slug>/ and appends one row to outputs/panel_atlas/registry.csv.
"""
from __future__ import annotations

import json
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

from figstyle import AREA_ORDER  # noqa: E402

CLS_DIR = OA_ROOT / "outputs" / "classification"
ATLAS_DIR = OA_ROOT / "outputs" / "panel_atlas"
F04_DIR = ATLAS_DIR / "F04"
REGISTRY_PATH = ATLAS_DIR / "registry.csv"

REGISTRY_COLUMNS = [
    "figure", "panel_id", "question", "estimand", "signal", "conditions", "population", "area",
    "time_window", "frequency", "statistic", "null_control", "inferential_unit", "source_data",
    "source_code", "output_table", "receipt", "result_status",
]

_counter = [0]


def next_panel_id() -> str:
    _counter[0] += 1
    return f"F04-P{_counter[0]:03d}"


def area_sort_key(area: str) -> int:
    return AREA_ORDER.index(area) if area in AREA_ORDER else len(AREA_ORDER)


def clopper_pearson(k: int, n: int, alpha: float = 0.05):
    if n == 0:
        return (np.nan, np.nan)
    ci = sstats.binomtest(k, n, p=0.5).proportion_ci(confidence_level=1 - alpha, method="exact")
    return (ci.low, ci.high)


def write_panel(slug: str, question: str, estimand: str, signal: str, conditions: str,
                 population: str, area: str, time_window: str, frequency: str, statistic: str,
                 null_control: str, inferential_unit: str, source_data: list[str],
                 source_code: str, data: pd.DataFrame, stats_dict: dict, result_status: str,
                 fig: "plt.Figure") -> None:
    panel_id = next_panel_id()
    out_dir = F04_DIR / f"{panel_id}_{slug}"
    out_dir.mkdir(parents=True, exist_ok=True)

    fig.suptitle(f"{panel_id} — {slug}", fontsize=9, y=0.995)
    fig.savefig(out_dir / "panel.svg", bbox_inches="tight")
    fig.savefig(out_dir / "panel.png", dpi=110, bbox_inches="tight")
    plt.close(fig)

    data.to_csv(out_dir / "data.csv", index=False)
    (out_dir / "stats.json").write_text(json.dumps(stats_dict, indent=2, default=str))

    receipt = {
        "panel_id": panel_id,
        "figure": "F04",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "source_data": source_data,
        "source_code_generator": str(HERE.relative_to(OA_ROOT.parent)),
        "upstream_source_code": source_code,
        "note": "No new model fitting/decoding performed; this generator only aggregates and "
                "visualizes pre-existing, receipt-backed outputs listed in source_data.",
    }
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=2))

    row = {
        "figure": "F04", "panel_id": panel_id, "question": question, "estimand": estimand,
        "signal": signal, "conditions": conditions, "population": population, "area": area,
        "time_window": time_window, "frequency": frequency, "statistic": statistic,
        "null_control": null_control, "inferential_unit": inferential_unit,
        "source_data": ";".join(source_data), "source_code": source_code,
        "output_table": str((out_dir / "data.csv").relative_to(ATLAS_DIR)),
        "receipt": str((out_dir / "receipt.json").relative_to(ATLAS_DIR)),
        "result_status": result_status,
    }
    header_needed = not REGISTRY_PATH.exists()
    pd.DataFrame([row], columns=REGISTRY_COLUMNS).to_csv(
        REGISTRY_PATH, mode="a", index=False, header=header_needed)
    print(f"  {panel_id}: {slug} [{result_status}]")


def main() -> None:
    F04_DIR.mkdir(parents=True, exist_ok=True)
    if REGISTRY_PATH.exists():
        REGISTRY_PATH.unlink()  # regenerate deterministically each run

    cells = pd.read_csv(CLS_DIR / "omission_identity_leakage_safe_cells.csv")
    oof = pd.read_csv(CLS_DIR / "omission_identity_leakage_safe_oof.csv")
    null = pd.read_csv(CLS_DIR / "omission_identity_leakage_safe_null.csv")
    ok = cells[cells["status"] == "success"].copy()
    ok["area_ord"] = ok["area"].map(area_sort_key)
    LS_SRC = ["outputs/classification/omission_identity_leakage_safe_cells.csv",
              "outputs/classification/omission_identity_leakage_safe_null.csv",
              "outputs/classification/omission_identity_leakage_safe_receipt.json"]
    LS_CODE = "scripts/compute_omission_identity_leakage_safe.py"

    print("=== F04 leakage-safe identity decoding panels ===")

    # P: AUC by session
    fig, ax = plt.subplots(figsize=(7, 3.5))
    order = sorted(ok["session"].unique())
    ax.boxplot([ok.loc[ok["session"] == s, "auc_loco"] for s in order], tick_labels=order,
               vert=True)
    ax.axhline(0.5, ls="--", c="gray", lw=1)
    ax.set_ylabel("AUC (LOCO)"); ax.tick_params(axis="x", rotation=90, labelsize=6)
    write_panel("auc_by_session", "Does leakage-safe decoding AUC vary by session?",
                "I(Z;S) cross-validated AUC, by session", "spike counts", "A/B/R identity",
                "all_units", "all", "trial window (see receipt feature_window_ms)", "n/a",
                "AUC (LOCO-CV)", "within-cycle label permutation (per-cell, not shown here)",
                "session x area x omission-position cell", LS_SRC, LS_CODE,
                ok[["session", "area", "slot_key", "auc_loco"]], {
                    "n_cells": int(len(ok)), "median_auc": float(ok["auc_loco"].median())},
                "NULL", fig)

    # P: AUC by area
    fig, ax = plt.subplots(figsize=(6, 3.5))
    area_order = sorted(ok["area"].unique(), key=area_sort_key)
    ax.boxplot([ok.loc[ok["area"] == a, "auc_loco"] for a in area_order], tick_labels=area_order)
    ax.axhline(0.5, ls="--", c="gray", lw=1)
    ax.set_ylabel("AUC (LOCO)"); ax.set_xlabel("area (anatomical order)")
    write_panel("auc_by_area", "Does decoding AUC differ by area?",
                "I(Z;S) AUC, by area", "spike counts", "A/B/R identity", "all_units", "all areas",
                "trial window", "n/a", "AUC (LOCO-CV)", "n/a (descriptive)",
                "session x area x position cell", LS_SRC, LS_CODE,
                ok[["area", "auc_loco"]], {a: float(ok.loc[ok["area"] == a, "auc_loco"].median())
                                            for a in area_order}, "NULL", fig)

    # P: AUC by omission position (slot)
    fig, ax = plt.subplots(figsize=(4, 3.5))
    slot_order = sorted(ok["slot_key"].unique())
    ax.boxplot([ok.loc[ok["slot_key"] == s, "auc_loco"] for s in slot_order], tick_labels=slot_order)
    ax.axhline(0.5, ls="--", c="gray", lw=1)
    ax.set_ylabel("AUC (LOCO)"); ax.set_xlabel("omission position")
    write_panel("auc_by_position", "Does decoding AUC differ by omission position (p2/p3/p4)?",
                "I(Z;S) AUC, by position", "spike counts", "A/B/R identity", "all_units", "all",
                "trial window", "n/a", "AUC (LOCO-CV)", "n/a (descriptive)",
                "session x area x position cell", LS_SRC, LS_CODE,
                ok[["slot_key", "auc_loco"]], {s: float(ok.loc[ok["slot_key"] == s, "auc_loco"].median())
                                                for s in slot_order}, "NULL", fig)

    # P: AUC distribution across all cells
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.hist(ok["auc_loco"], bins=20, color="steelblue", edgecolor="white")
    ax.axvline(0.5, ls="--", c="gray"); ax.axvline(ok["auc_loco"].mean(), c="red", lw=1,
                                                     label=f"mean={ok['auc_loco'].mean():.3f}")
    ax.set_xlabel("AUC (LOCO)"); ax.set_ylabel("n cells"); ax.legend(fontsize=7)
    write_panel("auc_distribution", "What is the full distribution of decoding AUC across the corpus?",
                "I(Z;S) AUC distribution", "spike counts", "A/B/R identity", "all_units", "all",
                "trial window", "n/a", "AUC (LOCO-CV) histogram", "n/a (descriptive)",
                "session x area x position cell", LS_SRC, LS_CODE,
                ok[["auc_loco"]], {"n": int(len(ok)), "mean": float(ok["auc_loco"].mean()),
                                    "sd": float(ok["auc_loco"].std())}, "NULL", fig)

    # P: observed vs permutation null (pooled)
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.hist(null["accuracy_loco_balanced"], bins=30, color="lightgray", density=True,
            label="pooled permutation null")
    ax.hist(ok["accuracy_loco_balanced"], bins=30, color="steelblue", density=True, alpha=0.6,
            label="observed (successful cells)")
    ax.axvline(0.5, ls="--", c="gray")
    ax.set_xlabel("balanced accuracy"); ax.legend(fontsize=7)
    write_panel("observed_vs_null", "Does the observed accuracy distribution differ from the pooled permutation null?",
                "observed vs null balanced-accuracy distributions", "spike counts", "A/B/R identity",
                "all_units", "all", "trial window", "n/a", "distribution overlay",
                "within-cycle label permutation, pooled across cells",
                "session x area x position cell (cells) / permutation draw (null)",
                LS_SRC, LS_CODE, pd.concat([
                    ok[["accuracy_loco_balanced"]].assign(kind="observed"),
                    null[["accuracy_loco_balanced"]].assign(kind="null")]),
                {"observed_mean": float(ok["accuracy_loco_balanced"].mean()),
                 "null_mean": float(null["accuracy_loco_balanced"].mean()),
                 "null_sd": float(null["accuracy_loco_balanced"].std())}, "NULL", fig)

    # P: significant-cell prevalence with Clopper-Pearson CI
    k = int((ok["p_permutation"] < 0.05).sum()); n = int(len(ok))
    lo, hi = clopper_pearson(k, n)
    fig, ax = plt.subplots(figsize=(3.5, 3.5))
    ax.bar([0], [k / n], color="steelblue", width=0.5)
    ax.errorbar([0], [k / n], yerr=[[k / n - lo], [hi - k / n]], fmt="none", c="black", capsize=6)
    ax.axhline(0.05, ls="--", c="red", label="expected FPR (0.05)")
    ax.set_xticks([0]); ax.set_xticklabels([f"{k}/{n} cells"])
    ax.set_ylabel("proportion p<0.05"); ax.legend(fontsize=7)
    write_panel("significant_cell_prevalence", "Does the proportion of nominally-significant cells exceed the expected false-positive rate?",
                "prevalence of p<0.05 cells vs expected FPR", "spike counts", "A/B/R identity",
                "all_units", "all", "trial window", "n/a", "proportion + exact Clopper-Pearson CI",
                "within-cycle label permutation (per cell)", "session x area x position cell",
                LS_SRC, LS_CODE, ok[["session", "area", "slot_key", "p_permutation"]],
                {"k_significant": k, "n_cells": n, "proportion": k / n,
                 "clopper_pearson_95ci": [lo, hi], "expected_fpr": 0.05,
                 "ci_contains_expected_fpr": bool(lo <= 0.05 <= hi)}, "NULL", fig)

    # P: effect relative to chance (AUC - 0.5)
    fig, ax = plt.subplots(figsize=(5, 3.5))
    delta = ok["auc_loco"] - 0.5
    ax.hist(delta, bins=20, color="steelblue", edgecolor="white")
    ax.axvline(0, ls="--", c="gray")
    t, p = sstats.ttest_1samp(delta, 0.0)
    ax.set_xlabel("AUC - 0.5"); ax.set_title(f"one-sample t={t:.2f}, p={p:.3f}", fontsize=8)
    write_panel("effect_vs_chance", "Is AUC-minus-chance systematically different from zero across cells?",
                "AUC - 0.5, one-sample test across cells", "spike counts", "A/B/R identity",
                "all_units", "all", "trial window", "n/a", "one-sample t-test (descriptive; cells are not independent replicates -- see caveat)",
                "n/a", "session x area x position cell (non-independent -- caveat below)",
                LS_SRC, LS_CODE, ok[["session", "area", "slot_key"]].assign(delta_auc=delta),
                {"t": float(t), "p": float(p), "mean_delta": float(delta.mean()),
                 "caveat": "cells share sessions/areas and are not independent replicates; this "
                           "is a descriptive screen, not the corpus-level inferential test (that "
                           "is the Clopper-Pearson proportion panel above, per project doctrine "
                           "of testing within-session first and pooling as a proportion)"},
                "NULL", fig)

    # P: subject-stratified performance
    fig, ax = plt.subplots(figsize=(4, 3.5))
    subj_order = sorted(ok["subject"].unique())
    ax.boxplot([ok.loc[ok["subject"] == s, "auc_loco"] for s in subj_order], tick_labels=subj_order)
    ax.axhline(0.5, ls="--", c="gray"); ax.set_ylabel("AUC (LOCO)")
    write_panel("subject_stratified", "Does decoding performance differ by subject?",
                "I(Z;S) AUC, by subject", "spike counts", "A/B/R identity", "all_units", "all",
                "trial window", "n/a", "AUC (LOCO-CV)", "n/a (descriptive)",
                "session x area x position cell", LS_SRC, LS_CODE,
                ok[["subject", "auc_loco"]], {s: float(ok.loc[ok["subject"] == s, "auc_loco"].median())
                                               for s in subj_order}, "NULL", fig)

    # P: hierarchy trend (AUC vs anatomical area order)
    fig, ax = plt.subplots(figsize=(6, 3.5))
    med = ok.groupby("area")["auc_loco"].median().reindex(
        [a for a in AREA_ORDER if a in ok["area"].unique()])
    ax.plot(range(len(med)), med.values, "o-", color="steelblue")
    ax.set_xticks(range(len(med))); ax.set_xticklabels(med.index, rotation=45, ha="right")
    ax.axhline(0.5, ls="--", c="gray"); ax.set_ylabel("median AUC")
    write_panel("hierarchy_trend", "Does median decoding AUC trend along the anatomical hierarchy?",
                "I(Z;S) AUC vs anatomical position", "spike counts", "A/B/R identity", "all_units",
                "hierarchy-ordered areas", "trial window", "n/a", "median AUC per area, hierarchy order",
                "n/a (descriptive)", "area (aggregated over session x position cells)",
                LS_SRC, LS_CODE, med.reset_index(), {"spearman_rho_vs_hierarchy_rank": float(
                    sstats.spearmanr(range(len(med)), med.values).statistic)}, "NULL", fig)

    # P: status/coverage breakdown by area (null characterization -- where decoding "fails")
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ct = pd.crosstab(cells["area"], cells["status"])
    ct = ct.reindex([a for a in AREA_ORDER if a in cells["area"].unique()])
    ct.plot(kind="bar", stacked=True, ax=ax, colormap="tab10")
    ax.set_ylabel("n cells"); ax.legend(fontsize=6, loc="upper right")
    write_panel("coverage_by_area", "Where does the leakage-safe design have insufficient data to even attempt decoding?",
                "cell status breakdown (success / insufficient_units / insufficient_cycles_or_classes / no_valid_folds)",
                "n/a", "A/B/R identity", "all_units", "all", "n/a", "n/a", "stacked count by status",
                "n/a", "session x area x position cell", LS_SRC, LS_CODE, ct.reset_index(),
                ct.sum().to_dict(), "DESCRIPTIVE", fig)

    # P: identity of the significant cells (clustering check)
    sig = ok[ok["p_permutation"] < 0.05][["session", "subject", "area", "slot_key", "auc_loco", "p_permutation"]]
    fig, ax = plt.subplots(figsize=(6, 2 + 0.3 * max(len(sig), 1)))
    ax.axis("off")
    tbl = ax.table(cellText=sig.round(3).values, colLabels=sig.columns, loc="center", fontsize=8)
    tbl.auto_set_font_size(False); tbl.set_fontsize(7)
    write_panel("significant_cell_identity", "Do the nominally-significant cells cluster by subject, area, or position (vs. scattering as expected under a true null)?",
                "identity/location of p<0.05 cells", "spike counts", "A/B/R identity", "all_units",
                "all", "trial window", "n/a", "listing, visual clustering check", "n/a",
                "session x area x position cell", LS_SRC, LS_CODE, sig,
                {"n_significant": int(len(sig)),
                 "areas_represented": sorted(sig["area"].unique().tolist()),
                 "subjects_represented": sorted(sig["subject"].unique().tolist()),
                 "clusters_by_single_area_or_subject": bool(
                     sig["area"].nunique() <= 1 or sig["subject"].nunique() <= 1) if len(sig) else False},
                "NULL", fig)

    print("=== F04 encoding-matrix (multi-target) panels ===")
    em = pd.read_csv(CLS_DIR / "fig04_encoding_matrix_cells.csv")
    em_ok = em[em["status"] == "success"].copy()
    EM_SRC = ["outputs/classification/fig04_encoding_matrix_cells.csv",
              "outputs/classification/fig04_encoding_matrix_receipt.json"]
    EM_CODE = "scripts/compute_fig04_encoding_matrix.py"
    targets = sorted(em_ok["target"].unique())

    # P: accuracy by target
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.boxplot([em_ok.loc[em_ok["target"] == t, "accuracy_loco_balanced"] for t in targets],
               tick_labels=targets)
    ax.axhline(0.5, ls="--", c="gray"); ax.set_ylabel("balanced accuracy (LOCO)")
    write_panel("accuracy_by_target", "How does decodability differ across the four omission-related targets?",
                "balanced accuracy, by target (Y_stim/Y_omit/Y_pos/Y_prev)", "spike counts",
                "target-specific", "all_units", "all", "trial window", "n/a",
                "balanced accuracy (LOCO-CV)", "within-cycle label permutation (per-cell)",
                "session x area x target cell", EM_SRC, EM_CODE,
                em_ok[["target", "area", "accuracy_loco_balanced"]],
                {t: float(em_ok.loc[em_ok["target"] == t, "accuracy_loco_balanced"].median())
                 for t in targets}, "DESCRIPTIVE", fig)

    # P: AUC by target x area heatmap
    piv = em_ok.pivot_table(index="area", columns="target", values="auc_loco", aggfunc="median")
    piv = piv.reindex([a for a in AREA_ORDER if a in piv.index])
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(piv.values, cmap="RdBu_r", vmin=0.3, vmax=0.7, aspect="auto")
    ax.set_xticks(range(len(piv.columns))); ax.set_xticklabels(piv.columns)
    ax.set_yticks(range(len(piv.index))); ax.set_yticklabels(piv.index)
    fig.colorbar(im, ax=ax, label="median AUC")
    write_panel("target_area_matrix", "Which (target, area) combinations show above-chance median AUC?",
                "median AUC matrix, target x area", "spike counts", "target-specific", "all_units",
                "hierarchy-ordered", "trial window", "n/a", "median AUC heatmap", "n/a (descriptive)",
                "area x target (aggregated over sessions)", EM_SRC, EM_CODE, piv.reset_index(),
                {"max_median_auc": float(np.nanmax(piv.values)),
                 "min_median_auc": float(np.nanmin(piv.values))}, "DESCRIPTIVE", fig)

    # P: cross-entropy by target
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.boxplot([em_ok.loc[em_ok["target"] == t, "cross_entropy"] for t in targets], tick_labels=targets)
    ax.set_ylabel("cross-entropy")
    write_panel("cross_entropy_by_target", "Does predictive cross-entropy differ across targets?",
                "held-out cross-entropy, by target", "spike counts", "target-specific", "all_units",
                "all", "trial window", "n/a", "cross-entropy distribution", "n/a (descriptive)",
                "session x area x target cell", EM_SRC, EM_CODE,
                em_ok[["target", "cross_entropy"]], {t: float(em_ok.loc[em_ok["target"] == t, "cross_entropy"].median())
                                                       for t in targets}, "DESCRIPTIVE", fig)

    # P: significant-cell prevalence by target (Clopper-Pearson)
    fig, ax = plt.subplots(figsize=(5, 3.5))
    props, los, his, ks, ns = [], [], [], [], []
    for t in targets:
        sub = em_ok[em_ok["target"] == t]
        k = int((sub["p_permutation"] < 0.05).sum()); n = int(len(sub))
        lo, hi = clopper_pearson(k, n)
        props.append(k / n if n else np.nan); los.append(lo); his.append(hi); ks.append(k); ns.append(n)
    x = np.arange(len(targets))
    ax.bar(x, props, color="steelblue")
    ax.errorbar(x, props, yerr=[np.array(props) - np.array(los), np.array(his) - np.array(props)],
                fmt="none", c="black", capsize=5)
    ax.axhline(0.05, ls="--", c="red")
    ax.set_xticks(x); ax.set_xticklabels(targets)
    ax.set_ylabel("proportion p<0.05")
    write_panel("significant_prevalence_by_target", "Does any target show above-chance prevalence of significant cells?",
                "prevalence of p<0.05 cells vs expected FPR, by target", "spike counts",
                "target-specific", "all_units", "all", "trial window", "n/a",
                "proportion + Clopper-Pearson CI, by target", "within-cycle label permutation",
                "session x area x target cell", EM_SRC, EM_CODE,
                pd.DataFrame({"target": targets, "k": ks, "n": ns, "proportion": props,
                              "ci_lo": los, "ci_hi": his}),
                {t: {"k": k, "n": n, "prop": p} for t, k, n, p in zip(targets, ks, ns, props)},
                "NULL" if all(lo <= 0.05 <= hi for lo, hi in zip(los, his)) else "SUPPORTED", fig)

    print("=== F04 ablation (SSA-decile) panels ===")
    abl = pd.read_csv(CLS_DIR / "fig04_encoding_matrix_ablation.csv")
    abl_ok = abl[abl["status"] == "success"].copy()
    ABL_SRC = ["outputs/classification/fig04_encoding_matrix_ablation.csv",
               "outputs/classification/fig04_encoding_matrix_receipt.json"]

    fig, ax = plt.subplots(figsize=(4, 3.5))
    ax.hist(abl_ok["ssa_percentile_of_controlled"], bins=20, color="steelblue")
    ax.axvline(50, ls="--", c="gray")
    write_panel("ssa_ablation_percentile", "Does removing the top-SSA-decile units hurt encoding performance more than removing a random matched-size set?",
                "percentile of SSA-removed cross-entropy within the random-removal null",
                "spike counts", "n/a", "all_units", "all", "trial window", "n/a",
                "percentile-of-null histogram", "matched random-removal draws",
                "session x area cell", ABL_SRC, EM_CODE, abl_ok[["session", "area", "ssa_percentile_of_controlled"]],
                {"median_percentile": float(abl_ok["ssa_percentile_of_controlled"].median())},
                "DESCRIPTIVE", fig)

    print("=== F04 cross-position generalization panels ===")
    xpos = pd.read_csv(CLS_DIR / "fig04_encoding_matrix_crossposition.csv")
    xpos_ok = xpos[xpos["status"] == "success"].copy()
    XPOS_SRC = ["outputs/classification/fig04_encoding_matrix_crossposition.csv",
                "outputs/classification/fig04_encoding_matrix_receipt.json"]
    piv2 = xpos_ok.pivot_table(index="train_position", columns="test_position",
                                values="cross_entropy", aggfunc="median")
    fig, ax = plt.subplots(figsize=(4, 3.5))
    im = ax.imshow(piv2.values, cmap="viridis", aspect="auto")
    ax.set_xticks(range(len(piv2.columns))); ax.set_xticklabels(piv2.columns)
    ax.set_yticks(range(len(piv2.index))); ax.set_yticklabels(piv2.index)
    ax.set_xlabel("test position"); ax.set_ylabel("train position")
    fig.colorbar(im, ax=ax, label="median cross-entropy")
    write_panel("crossposition_generalization", "Does a decoder trained at one omission position generalize to another?",
                "median cross-entropy, train-position x test-position", "spike counts",
                "cross-position", "all_units", "all", "trial window", "n/a",
                "cross-entropy heatmap", "n/a (descriptive)", "train-position x test-position cell",
                XPOS_SRC, EM_CODE, piv2.reset_index(), {"diag_vs_offdiag_gap": float(
                    np.nanmean(np.diag(piv2.values)) - np.nanmean(piv2.values[~np.eye(len(piv2), dtype=bool)]))
                    if len(piv2) > 1 else np.nan}, "DESCRIPTIVE", fig)

    print("=== F04 functional-class knockout panels ===")
    ko = pd.read_csv(CLS_DIR / "fig04_class_knockout_cells.csv")
    ko_ok = ko[ko["status"] == "success"].copy()
    KO_SRC = ["outputs/classification/fig04_class_knockout_cells.csv",
              "outputs/classification/fig04_class_knockout_receipt.json"]
    KO_CODE = "scripts/compute_fig04_class_knockout.py"
    KO_NOTE = ("removal_condition classes come from unit_inclusion_v1.csv::display_class -- the "
               "modern-native classifier, a DIFFERENT O+/O++ definition than fig03_unit_census.py's "
               "template-correlation definition. Per this session's F3 evidence review, that "
               "definition disagreement is an open, unresolved scientific decision -- these panels "
               "are labeled with their exact source classifier and must not be silently merged "
               "with fig03 counts.")

    fig, ax = plt.subplots(figsize=(7, 4))
    classes = sorted(ko_ok["removal_condition"].unique())
    for i, t in enumerate(targets):
        sub = ko_ok[ko_ok["target"] == t]
        means = [sub.loc[sub["removal_condition"] == c, "delta"].mean() for c in classes]
        ax.bar(np.arange(len(classes)) + i * 0.2, means, width=0.2, label=t)
    ax.set_xticks(np.arange(len(classes)) + 0.3); ax.set_xticklabels(classes, rotation=45, ha="right")
    ax.axhline(0, c="gray", lw=1); ax.set_ylabel("mean delta (removed - full)")
    ax.legend(fontsize=7)
    write_panel("class_knockout_delta_by_target", "Does removing a specific functional class hurt encoding more for the target that class was defined by (manipulation check, not novel finding)?",
                "mean performance delta, by removed class x target", "spike counts",
                "class-specific removal", "class-restricted (unit_inclusion_v1.csv::display_class)",
                "all", "trial window", "n/a", "mean delta bar chart", "matched random-removal draws",
                "session x area x class x target cell", KO_SRC, KO_CODE,
                ko_ok[["removal_condition", "target", "delta", "area"]],
                {"note": KO_NOTE, "classes": classes}, "DESCRIPTIVE", fig)

    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.hist(ko_ok["percentile_of_removed"], bins=20, color="steelblue")
    ax.axvline(50, ls="--", c="gray")
    write_panel("class_knockout_percentile", "How extreme is a named-class removal relative to a random matched-size removal, across all class x target cells?",
                "percentile of class-removed performance within the random-removal null",
                "spike counts", "class-specific removal",
                "class-restricted (unit_inclusion_v1.csv::display_class)", "all", "trial window",
                "n/a", "percentile-of-null histogram", "matched random-removal draws",
                "session x area x class x target cell", KO_SRC, KO_CODE,
                ko_ok[["removal_condition", "target", "percentile_of_removed"]],
                {"note": KO_NOTE, "median_percentile": float(ko_ok["percentile_of_removed"].median())},
                "DESCRIPTIVE", fig)

    n_panels = _counter[0]
    print(f"\n{n_panels} F04 panels written to {F04_DIR}")
    print(f"registry: {REGISTRY_PATH}")


if __name__ == "__main__":
    main()
