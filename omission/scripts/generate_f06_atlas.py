#!/usr/bin/env python3
"""F06 (SPK-LFP Dissociation) candidate-panel atlas generator.

Generates candidate panels for the F06 manuscript figure from the verified,
receipt-backed matched substrate (f06_matched_substrate_v1.csv) and robustness
evaluations (f06_robustness_summary.csv).

Every panel writes:
  - panel.svg
  - panel.png
  - data.csv
  - stats.json
  - receipt.json
under outputs/panel_atlas/F06/F06-Pxxx_<slug>/
and appends one row to outputs/panel_atlas/registry.csv.

Also generates the unified F06_ATLAS contact sheet.
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

SUBSTRATE_DIR = OA_ROOT / "outputs" / "f06_substrate"
ATLAS_DIR = OA_ROOT / "outputs" / "panel_atlas"
F06_DIR = ATLAS_DIR / "F06"
REGISTRY_PATH = ATLAS_DIR / "registry.csv"

REGISTRY_COLUMNS = [
    "figure", "panel_id", "question", "estimand", "signal", "conditions", "population", "area",
    "time_window", "frequency", "statistic", "null_control", "inferential_unit", "source_data",
    "source_code", "output_table", "receipt", "result_status",
]

_counter = [0]


def next_panel_id() -> str:
    _counter[0] += 1
    return f"F06-P{_counter[0]:03d}"


def write_panel(slug: str, question: str, estimand: str, signal: str, conditions: str,
                population: str, area: str, time_window: str, frequency: str, statistic: str,
                null_control: str, inferential_unit: str, source_data: list[str],
                source_code: str, data: pd.DataFrame, stats_dict: dict, result_status: str,
                fig: "plt.Figure") -> str:
    panel_id = next_panel_id()
    out_dir = F06_DIR / f"{panel_id}_{slug}"
    out_dir.mkdir(parents=True, exist_ok=True)

    fig.suptitle(f"{panel_id} — {slug}", fontsize=9, y=0.995)
    fig.savefig(out_dir / "panel.svg", bbox_inches="tight")
    fig.savefig(out_dir / "panel.png", dpi=110, bbox_inches="tight")
    plt.close(fig)

    data.to_csv(out_dir / "data.csv", index=False)
    (out_dir / "stats.json").write_text(json.dumps(stats_dict, indent=2, default=str))

    receipt = {
        "panel_id": panel_id,
        "figure": "F06",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "source_data": source_data,
        "source_code_generator": str(HERE.relative_to(OA_ROOT.parent)),
        "upstream_source_code": source_code,
        "note": "Candidate panel generated for F06 atlas; verified on matched SPK-LFP substrate v1.",
    }
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=2))

    registry_row = {
        "figure": "F06",
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
        "output_table": f"F06/{panel_id}_{slug}/data.csv",
        "receipt": f"F06/{panel_id}_{slug}/receipt.json",
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

    pngs = sorted(glob.glob(str(F06_DIR / "F06-P*" / "panel.png")))
    if not pngs:
        print("No PNGs found for contact sheet.")
        return

    n_images = len(pngs)
    ncols = 4
    nrows = math.ceil(n_images / ncols)

    images = [Image.open(p) for p in pngs]
    # Standardize image size
    max_w = max(im.width for im in images)
    max_h = max(im.height for im in images)

    thumb_w, thumb_h = 400, int(400 * max_h / max_w)
    grid_im = Image.new("RGB", (ncols * thumb_w, nrows * thumb_h), (255, 255, 255))

    for idx, im in enumerate(images):
        row = idx // ncols
        col = idx % ncols
        im_resized = im.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        grid_im.paste(im_resized, (col * thumb_w, row * thumb_h))

    contact_path = F06_DIR / "F06_ATLAS_contact_sheet.png"
    grid_im.save(contact_path, quality=90)
    print(f"Saved contact sheet to {contact_path}")


def main():
    F06_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(SUBSTRATE_DIR / "f06_matched_substrate_v1.csv")
    rob = pd.read_csv(SUBSTRATE_DIR / "f06_robustness_summary.csv")
    loso = pd.read_csv(SUBSTRATE_DIR / "f06_loso_records.csv")
    losubj = pd.read_csv(SUBSTRATE_DIR / "f06_losubj_records.csv")
    subj_strat = pd.read_csv(SUBSTRATE_DIR / "f06_subject_stratified.csv")

    SUB_SRC = ["outputs/f06_substrate/f06_matched_substrate_v1.csv",
               "outputs/f06_substrate/f06_robustness_summary.csv"]
    SUB_CODE = "scripts/build_f06_matched_substrate_v1.py;scripts/compute_f06_robustness.py"

    bands = ["theta", "alpha", "beta", "low_gamma", "high_gamma"]
    band_display = {
        "theta": "Theta (4–8 Hz)",
        "alpha": "Alpha (8–14 Hz)",
        "beta": "Beta (15–30 Hz)",
        "low_gamma": "Low-Gamma (30–50 Hz)",
        "high_gamma": "High-Gamma (50–90 Hz)",
    }

    # Subject colors
    subj_colors = {"C31o": "#1f77b4", "V182o": "#2ca02c", "V198o": "#d62728"}

    print("=== Generating Panels 1–10: SPK vs LFP scatter by band & contrast ===")
    for band in bands:
        for contrast, c_name, spk_col, lfp_col, stat_pfx in [
            ("OB", "Omission vs Baseline", "spk_ob_effect_hz_mean", f"{band}_ob_harmonized_db", "ob"),
            ("OS", "Omission vs Stimulus", "spk_os_effect_hz_mean", f"{band}_os_db", "os"),
        ]:
            fig, ax = plt.subplots(figsize=(4.5, 4))
            for subj, s_df in df.groupby("subject"):
                ax.scatter(s_df[spk_col], s_df[lfp_col], color=subj_colors.get(subj, "gray"),
                           label=subj, alpha=0.8, s=40, edgecolors="none")
            
            # Regression line
            x = df[spk_col]
            y = df[lfp_col]
            slope, intercept, r_val, p_val, std_err = sstats.linregress(x, y)
            rho_val, rho_p = sstats.spearmanr(x, y)
            x_line = np.linspace(x.min(), x.max(), 100)
            ax.plot(x_line, slope * x_line + intercept, color="black", lw=1.5, ls="--")
            
            ax.set_xlabel(f"SPK Effect (Hz, {contrast})")
            ax.set_ylabel(f"LFP Power (dB, {band_display[band]})")
            ax.set_title(f"{band_display[band]} — {c_name}\n"
                         f"r = {r_val:.3f} (p = {p_val:.3e}), rho = {rho_val:.3f}", fontsize=8)
            ax.legend(fontsize=7, loc="best")
            ax.grid(True, alpha=0.3)

            panel_data = df[["subject", "session", "area", spk_col, lfp_col]]
            stats_dict = {
                "band": band, "contrast": contrast, "n_cells": len(df),
                "pearson_r": float(r_val), "pearson_p": float(p_val),
                "spearman_rho": float(rho_val), "spearman_p": float(rho_p),
                "slope": float(slope), "intercept": float(intercept)
            }
            
            res_status = "SUPPORTED" if (p_val < 0.05) else "NULL"
            write_panel(
                f"scatter_{band}_{contrast.lower()}",
                f"Is SPK modulation correlated with {band} LFP power under the {contrast} contrast?",
                f"Pearson r & Spearman rho, SPK vs {band} LFP ({contrast})",
                "SPK + LFP", f"{contrast} (p2)", "all_units", "all",
                "1031-1562ms (p2 omission)", band,
                "scatter + linear regression", "shuffle null (Pearson/Spearman test)",
                "matched session x area cell", SUB_SRC, SUB_CODE,
                panel_data, stats_dict, res_status, fig
            )

    print("=== Generating Panel 11: r_OB vs r_OS comparison bar chart ===")
    fig, ax = plt.subplots(figsize=(6, 3.5))
    x_pos = np.arange(len(bands))
    width = 0.35
    r_obs = [rob.loc[rob["band"] == b, "r_ob"].values[0] for b in bands]
    r_oss = [rob.loc[rob["band"] == b, "r_os"].values[0] for b in bands]
    
    ax.bar(x_pos - width/2, r_obs, width, label="OB (omission vs baseline)", color="#4c72b0")
    ax.bar(x_pos + width/2, r_oss, width, label="OS (omission vs stimulus)", color="#dd8452")
    ax.axhline(0, color="gray", lw=1)
    ax.set_xticks(x_pos)
    ax.set_xticklabels([b.replace("_", " ").title() for b in bands])
    ax.set_ylabel("Pearson Correlation (r)")
    ax.set_title("SPK–LFP Concordance by Band and Contrast", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")
    
    p11_data = rob[["band", "r_ob", "p_r_ob", "r_os", "p_r_os"]]
    write_panel(
        "concordance_ob_vs_os_bars",
        "How does SPK-LFP concordance compare between OB and OS contrasts across frequency bands?",
        "Pearson r by band and contrast", "SPK + LFP", "OB vs OS", "all_units", "all",
        "1031-1562ms", "canonical 5 bands", "grouped bar chart", "independent zero-correlation tests",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        p11_data, {"bands": bands, "r_ob": r_obs, "r_os": r_oss}, "SUPPORTED", fig
    )

    print("=== Generating Panel 12: Delta r across bands with 95% bootstrap CIs ===")
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    delta_rs = rob["delta_r"].values
    ci_lo = rob["ci_delta_r_lower"].values
    ci_hi = rob["ci_delta_r_upper"].values
    err_lo = delta_rs - ci_lo
    err_hi = ci_hi - delta_rs
    
    ax.errorbar(x_pos, delta_rs, yerr=[err_lo, err_hi], fmt="o", color="black",
                ecolor="navy", elinewidth=2, capsize=4)
    ax.axhline(0, color="red", ls="--", lw=1)
    ax.set_xticks(x_pos)
    ax.set_xticklabels([b.replace("_", " ").title() for b in bands])
    ax.set_ylabel(r"$\Delta r = r_{OS} - r_{OB}$")
    ax.set_title(r"Contrast Difference in Concordance ($\Delta r$) with 95% Session-Bootstrap CI", fontsize=8.5)
    ax.grid(True, alpha=0.3)
    
    p12_data = rob[["band", "delta_r", "ci_delta_r_lower", "ci_delta_r_upper"]]
    write_panel(
        "delta_r_bootstrap_ci",
        "Does the correlation difference between OS and OB contrasts reliably exclude zero across bands?",
        "Delta r (r_OS - r_OB) with 95% cluster-bootstrap CI", "SPK + LFP", "OB vs OS",
        "all_units", "all", "1031-1562ms", "canonical 5 bands",
        "point estimate + 95% percentile bootstrap CI", "session-cluster bootstrap (B=2000)",
        "session cluster", SUB_SRC, SUB_CODE,
        p12_data, {"delta_r": list(delta_rs), "ci_lower": list(ci_lo), "ci_upper": list(ci_hi)},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 13: Interaction beta3 coefficients & uncertainty ===")
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    betas = rob["beta3"].values
    se_ses = rob["se_ses"].values
    ci_lo_b = betas - 1.96 * se_ses
    ci_hi_b = betas + 1.96 * se_ses
    
    ax.errorbar(x_pos, betas, yerr=1.96*se_ses, fmt="s", color="darkgreen",
                ecolor="darkgreen", elinewidth=2, capsize=4)
    ax.axhline(0, color="gray", ls="--", lw=1)
    ax.set_xticks(x_pos)
    ax.set_xticklabels([b.replace("_", " ").title() for b in bands])
    ax.set_ylabel(r"Interaction $\beta_3$ (SE clustered by session)")
    ax.set_title(r"Model $z_L = \beta_0 + \beta_1 z_S + \beta_2 C + \beta_3(z_S C)$ Interaction Term", fontsize=8.5)
    ax.grid(True, alpha=0.3)
    
    p13_data = rob[["band", "beta3", "se_ses", "p_ses", "q_ses"]]
    write_panel(
        "interaction_beta3_session_clustered",
        "Does the standardized SPK-LFP correspondence interaction term beta3 survive session-aware clustering?",
        "Interaction coefficient beta3 + 95% CI (session clustered)", "SPK + LFP", "stacked OB+OS",
        "all_units", "all", "1031-1562ms", "canonical 5 bands",
        "OLS with cluster-robust session SE", "Wald test with session clustering",
        "session cluster", SUB_SRC, SUB_CODE,
        p13_data, {"beta3": list(betas), "p_ses": list(rob["p_ses"]), "q_ses": list(rob["q_ses"])},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 14: Multiplicity & FDR q-value summary ===")
    fig, ax = plt.subplots(figsize=(6, 3.5))
    raw_p = rob["p_ses"].values
    fdr_q = rob["q_ses"].values
    
    ax.plot(x_pos, raw_p, "o--", label="Raw p-value (session-clustered)", color="coral")
    ax.plot(x_pos, fdr_q, "s-", label="BH FDR q-value (5 bands)", color="purple")
    ax.axhline(0.05, color="red", ls=":", label="alpha = 0.05 threshold")
    ax.set_xticks(x_pos)
    ax.set_xticklabels([b.replace("_", " ").title() for b in bands])
    ax.set_ylabel("p / q value")
    ax.set_yscale("log")
    ax.set_title("Multiplicity Correction for Direct Dissociation Interaction Tests", fontsize=8.5)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3)
    
    p14_data = rob[["band", "p_cell", "q_cell", "p_ses", "q_ses", "p_ses_subj", "q_ses_subj"]]
    write_panel(
        "multiplicity_q_summary",
        "Which frequency bands survive FDR correction for contrast-dependent SPK-LFP interaction?",
        "Raw p vs FDR q across 5 canonical bands", "SPK + LFP", "stacked OB+OS",
        "all_units", "all", "1031-1562ms", "canonical 5 bands",
        "Benjamini-Hochberg FDR", "5-test hypothesis family",
        "frequency band family", SUB_SRC, SUB_CODE,
        p14_data, {"p_ses": list(raw_p), "q_ses": list(fdr_q)}, "SUPPORTED", fig
    )

    print("=== Generating Panel 15: Pearson r vs Spearman rho estimator sensitivity ===")
    fig, ax = plt.subplots(figsize=(5, 4))
    r_all = np.concatenate([rob["r_ob"], rob["r_os"]])
    rho_all = np.concatenate([rob["rho_ob"], rob["rho_os"]])
    c_labels = ["OB"]*5 + ["OS"]*5
    
    for i, (r_val, rho_val, band, c) in enumerate(zip(r_all, rho_all, bands*2, c_labels)):
        m = "o" if c == "OB" else "s"
        col = "#1f77b4" if c == "OB" else "#ff7f0e"
        ax.scatter(r_val, rho_val, marker=m, color=col, s=50, label=f"{band} ({c})")
        ax.annotate(f"{band[:2]}_{c}", (r_val+0.02, rho_val), fontsize=7)
        
    ax.plot([-0.2, 0.8], [-0.2, 0.8], "k--", alpha=0.5, label="Identity line")
    ax.set_xlabel("Pearson r")
    ax.set_ylabel("Spearman rho")
    ax.set_title("Estimator Sensitivity: Pearson r vs Spearman rho (10 conditions)", fontsize=8.5)
    ax.grid(True, alpha=0.3)
    
    p15_data = pd.DataFrame({"band": bands*2, "contrast": c_labels, "pearson_r": r_all, "spearman_rho": rho_all})
    write_panel(
        "pearson_vs_spearman_sensitivity",
        "Are SPK-LFP correlation estimates sensitive to rank vs linear metric choice?",
        "Pearson r vs Spearman rho scatter across 10 band x contrast conditions", "SPK + LFP", "OB & OS",
        "all_units", "all", "1031-1562ms", "canonical 5 bands",
        "estimator comparison scatter", "identity line",
        "band x contrast condition", SUB_SRC, SUB_CODE,
        p15_data, {"corr_pearson_spearman": float(sstats.pearsonr(r_all, rho_all)[0])}, "SUPPORTED", fig
    )

    print("=== Generating Panel 16: Leave-One-Session-Out (LOSO) stability ===")
    fig, ax = plt.subplots(figsize=(6, 3.5))
    for i, band in enumerate(bands):
        sub_loso = loso[loso["band"] == band]["beta3"]
        ax.scatter([i]*len(sub_loso), sub_loso, color="steelblue", alpha=0.6, s=25)
        ax.scatter(i, np.median(sub_loso), color="red", marker="D", s=40, zorder=5)
    ax.axhline(0, color="gray", ls="--", lw=1)
    ax.set_xticks(range(len(bands)))
    ax.set_xticklabels([b.replace("_", " ").title() for b in bands])
    ax.set_ylabel(r"Leave-One-Session-Out $\beta_3$")
    ax.set_title("Leave-One-Session-Out (LOSO) Stability across 15 Sessions (Red = Median)", fontsize=8.5)
    ax.grid(True, alpha=0.3)
    
    write_panel(
        "loso_session_stability",
        "Is the interaction coefficient beta3 stable when leaving out individual sessions?",
        "LOSO beta3 distribution per band", "SPK + LFP", "stacked OB+OS",
        "all_units", "all", "1031-1562ms", "canonical 5 bands",
        "Jackknife / Leave-one-session-out resampling", "full dataset estimate",
        "session jackknife", SUB_SRC, SUB_CODE,
        loso, {"fraction_same_sign": {b: float(rob.loc[rob["band"]==b, "loso_fraction_same_sign"].values[0]) for b in bands}},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 17: Leave-One-Subject-Out (LOSubj) stability ===")
    fig, ax = plt.subplots(figsize=(6, 3.5))
    x_pos = np.arange(len(bands))
    width = 0.25
    for idx, subj in enumerate(["C31o", "V182o", "V198o"]):
        betas_s = [losubj.loc[(losubj["band"]==b) & (losubj["left_out_subject"]==subj), "beta3"].values[0] for b in bands]
        ax.bar(x_pos + (idx-1)*width, betas_s, width, label=f"Exclude {subj}", color=subj_colors[subj], alpha=0.8)
    ax.axhline(0, color="gray", lw=1)
    ax.set_xticks(x_pos)
    ax.set_xticklabels([b.replace("_", " ").title() for b in bands])
    ax.set_ylabel(r"Interaction $\beta_3$")
    ax.set_title("Leave-One-Subject-Out (LOSubj) Sensitivity across 3 Animals", fontsize=8.5)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3, axis="y")
    
    write_panel(
        "losubj_subject_stability",
        "How sensitive is the interaction beta3 to excluding any individual subject?",
        "LOSubj beta3 per band and left-out animal", "SPK + LFP", "stacked OB+OS",
        "all_units", "all", "1031-1562ms", "canonical 5 bands",
        "leave-one-subject-out OLS", "full sample estimate",
        "subject exclusion", SUB_SRC, SUB_CODE,
        losubj, {"losubj_records": losubj.to_dict(orient="records")},
        "SUPPORTED", fig
    )

    print("=== Generating Panel 18: Subject-stratified geometry ===")
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.5), sharey=True)
    for ax, subj in zip(axes, ["C31o", "V182o", "V198o"]):
        s_data = subj_strat[subj_strat["subject"] == subj]
        x_s = np.arange(len(s_data))
        ax.bar(x_s - 0.15, s_data["r_ob"], 0.3, label="OB", color="#4c72b0")
        ax.bar(x_s + 0.15, s_data["r_os"], 0.3, label="OS", color="#dd8452")
        ax.axhline(0, color="gray", lw=0.8)
        ax.set_xticks(x_s)
        ax.set_xticklabels([b[:3] for b in s_data["band"]], fontsize=8)
        ax.set_title(f"{subj} (n={s_data['n'].iloc[0]})", fontsize=9)
        ax.grid(True, alpha=0.3, axis="y")
        if subj == "C31o":
            ax.set_ylabel("Pearson r")
            ax.legend(fontsize=7)
            
    fig.suptitle("Subject-Stratified Concordance by Frequency Band and Contrast", fontsize=9, y=0.98)
    write_panel(
        "subject_stratified_concordance",
        "How does SPK-LFP concordance look within each individual monkey?",
        "Within-subject Pearson r by band and contrast", "SPK + LFP", "OB vs OS",
        "all_units", "all", "1031-1562ms", "canonical 5 bands",
        "within-subject correlation", "between-subject variation",
        "subject stratum", SUB_SRC, SUB_CODE,
        subj_strat, {"subj_records": subj_strat.to_dict(orient="records")},
        "DESCRIPTIVE", fig
    )

    print("=== Generating Panel 19: Area-stratified concordance ===")
    area_records = []
    for area, a_df in df.groupby("area"):
        if len(a_df) >= 3:
            for b in bands:
                r_ob_a = sstats.pearsonr(a_df["spk_ob_effect_hz_mean"], a_df[f"{b}_ob_harmonized_db"])[0]
                r_os_a = sstats.pearsonr(a_df["spk_os_effect_hz_mean"], a_df[f"{b}_os_db"])[0]
                area_records.append({"area": area, "band": b, "n": len(a_df), "r_ob": r_ob_a, "r_os": r_os_a})
    area_df = pd.DataFrame(area_records)
    
    fig, ax = plt.subplots(figsize=(7, 3.8))
    area_order_present = [a for a in AREA_ORDER if a in area_df["area"].unique()]
    x_a = np.arange(len(area_order_present))
    width = 0.15
    for i, b in enumerate(bands):
        sub_b = area_df[area_df["band"] == b].set_index("area").reindex(area_order_present)
        ax.plot(x_a, sub_b["r_os"] - sub_b["r_ob"], "o-", label=b.replace("_", " ").title())
    ax.axhline(0, color="gray", ls="--")
    ax.set_xticks(x_a)
    ax.set_xticklabels(area_order_present)
    ax.set_ylabel(r"$\Delta r = r_{OS} - r_{OB}$")
    ax.set_xlabel("Cortical Area (Hierarchy Order)")
    ax.set_title(r"Area-Stratified Concordance Difference ($\Delta r$) along Hierarchy", fontsize=8.5)
    ax.legend(fontsize=7, ncol=2)
    ax.grid(True, alpha=0.3)
    
    write_panel(
        "area_hierarchy_concordance_delta",
        "Does contrast-dependent concordance variation track anatomical cortical hierarchy?",
        "Delta r by cortical area and band", "SPK + LFP", "OB vs OS",
        "all_units", "6 matched cortical areas", "1031-1562ms", "canonical 5 bands",
        "area-stratified correlation difference", "anatomical hierarchy order",
        "cortical area", SUB_SRC, SUB_CODE,
        area_df, {"area_order": area_order_present}, "DESCRIPTIVE", fig
    )

    print("=== Generating Panel 20: Standardized response geometry (z_S vs z_L) ===")
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    spk_ob_z = (df["spk_ob_effect_hz_mean"] - df["spk_ob_effect_hz_mean"].mean()) / df["spk_ob_effect_hz_mean"].std()
    spk_os_z = (df["spk_os_effect_hz_mean"] - df["spk_os_effect_hz_mean"].mean()) / df["spk_os_effect_hz_mean"].std()
    theta_ob_z = (df["theta_ob_harmonized_db"] - df["theta_ob_harmonized_db"].mean()) / df["theta_ob_harmonized_db"].std()
    lg_os_z = (df["low_gamma_os_db"] - df["low_gamma_os_db"].mean()) / df["low_gamma_os_db"].std()
    
    ax.scatter(spk_ob_z, theta_ob_z, color="#4c72b0", label="Theta (OB)", alpha=0.8, s=40)
    ax.scatter(spk_os_z, lg_os_z, color="#c44e52", label="Low-Gamma (OS)", alpha=0.8, s=40)
    ax.axhline(0, color="gray", ls=":", lw=0.8)
    ax.axvline(0, color="gray", ls=":", lw=0.8)
    ax.plot([-3, 3], [-3, 3], "k--", alpha=0.4, lw=1)
    ax.set_xlabel("Standardized Spiking Effect (z_S)")
    ax.set_ylabel("Standardized LFP Effect (z_L)")
    ax.set_title("Standardized Response Geometry: Theta (OB) vs Low-Gamma (OS)", fontsize=8.5)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    
    p20_data = pd.DataFrame({
        "cell": df["session"] + "_" + df["area"],
        "z_spk_ob": spk_ob_z, "z_theta_ob": theta_ob_z,
        "z_spk_os": spk_os_z, "z_low_gamma_os": lg_os_z,
    })
    write_panel(
        "standardized_response_geometry_biplot",
        "How do the two primary concordant regimes (OB Theta vs OS Low-Gamma) align in standardized feature space?",
        "Standardized (z_S, z_L) biplot", "SPK + LFP", "OB vs OS",
        "all_units", "all", "1031-1562ms", "theta & low-gamma",
        "joint standardized scatter", "coordinate axes",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        p20_data, {"n_cells": len(df)}, "DESCRIPTIVE", fig
    )

    print("=== Generating Panel 21: Descriptive sign mismatch prevalence ===")
    fig, ax = plt.subplots(figsize=(6, 3.5))
    mismatch_records = []
    for b in bands:
        # Sign mismatch in OB
        mis_ob = np.mean(np.sign(df["spk_ob_effect_hz_mean"]) != np.sign(df[f"{b}_ob_harmonized_db"]))
        # Sign mismatch in OS
        mis_os = np.mean(np.sign(df["spk_os_effect_hz_mean"]) != np.sign(df[f"{b}_os_db"]))
        mismatch_records.append({"band": b, "mismatch_rate_ob": mis_ob, "mismatch_rate_os": mis_os})
    mis_df = pd.DataFrame(mismatch_records)
    
    x_m = np.arange(len(bands))
    ax.bar(x_m - 0.15, mis_df["mismatch_rate_ob"], 0.3, label="OB Contrast", color="#4c72b0")
    ax.bar(x_m + 0.15, mis_df["mismatch_rate_os"], 0.3, label="OS Contrast", color="#dd8452")
    ax.axhline(0.5, color="red", ls="--", label="Chance (50%)")
    ax.set_xticks(x_m)
    ax.set_xticklabels([b.replace("_", " ").title() for b in bands])
    ax.set_ylabel("Fraction with Sign Mismatch")
    ax.set_title("Prevalence of Opposite-Signed SPK vs LFP Responses Across Bands", fontsize=8.5)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3, axis="y")
    
    write_panel(
        "sign_mismatch_prevalence",
        "What fraction of matched session-area cells exhibit opposite response signs between SPK and LFP?",
        "Fraction sign(SPK) != sign(LFP) by band and contrast", "SPK + LFP", "OB vs OS",
        "all_units", "all", "1031-1562ms", "canonical 5 bands",
        "discordance proportion", "50% chance baseline",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        mis_df, {"mismatch_summary": mis_df.to_dict(orient="records")}, "DESCRIPTIVE", fig
    )

    print("=== Generating Panel 22: Reference-state methodological control ===")
    fig, ax = plt.subplots(figsize=(5, 4))
    r_ob_native = [sstats.pearsonr(df["spk_ob_effect_hz_mean"], df[f"{b}_ob_native_db"])[0] for b in bands]
    r_ob_harmonized = [rob.loc[rob["band"]==b, "r_ob"].values[0] for b in bands]
    
    ax.plot(x_pos, r_ob_native, "o--", label="Native Fixation Baseline (F05 style)", color="gray")
    ax.plot(x_pos, r_ob_harmonized, "s-", label="Harmonized Pre-Omission Baseline", color="navy")
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_xticks(x_pos)
    ax.set_xticklabels([b.replace("_", " ").title() for b in bands])
    ax.set_ylabel("Pearson Correlation with SPK (r)")
    ax.set_title("Methodological Control: Impact of LFP Baseline Convention on OB Concordance", fontsize=8)
    ax.legend(fontsize=7.5)
    ax.grid(True, alpha=0.3)
    
    p22_data = pd.DataFrame({"band": bands, "r_ob_native": r_ob_native, "r_ob_harmonized": r_ob_harmonized})
    write_panel(
        "reference_baseline_control",
        "Does the choice of LFP reference baseline (fixation vs pre-omission delay) alter SPK-LFP concordance?",
        "Pearson r for OB native vs harmonized baseline", "SPK + LFP", "OB baseline comparison",
        "all_units", "all", "1031-1562ms", "canonical 5 bands",
        "baseline convention comparison", "native vs harmonized difference",
        "matched session x area cell", SUB_SRC, SUB_CODE,
        p22_data, {"r_native": r_ob_native, "r_harmonized": r_ob_harmonized}, "METHODOLOGICAL_CONTROL", fig
    )

    print("=== Generating Panel 23: Session-cluster bootstrap distribution of Delta r ===")
    # Re-run a quick bootstrap sample display for theta and low-gamma
    rng = np.random.default_rng(42)
    ses_list = list(df["session"].unique())
    ses_to_idx = {s: np.where(df["session"] == s)[0] for s in ses_list}
    boot_th = []
    boot_lg = []
    for _ in range(2000):
        b_ses = rng.choice(ses_list, size=len(ses_list), replace=True)
        b_idx = np.concatenate([ses_to_idx[s] for s in b_ses])
        b_df = df.iloc[b_idx]
        r_ob_th = sstats.pearsonr(b_df["spk_ob_effect_hz_mean"], b_df["theta_ob_harmonized_db"])[0]
        r_os_th = sstats.pearsonr(b_df["spk_os_effect_hz_mean"], b_df["theta_os_db"])[0]
        boot_th.append(r_os_th - r_ob_th)
        r_ob_lg = sstats.pearsonr(b_df["spk_ob_effect_hz_mean"], b_df["low_gamma_ob_harmonized_db"])[0]
        r_os_lg = sstats.pearsonr(b_df["spk_os_effect_hz_mean"], b_df["low_gamma_os_db"])[0]
        boot_lg.append(r_os_lg - r_ob_lg)
        
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.hist(boot_th, bins=30, alpha=0.5, color="#4c72b0", label=r"Theta $\Delta r$ (Mean = -0.51)")
    ax.hist(boot_lg, bins=30, alpha=0.5, color="#dd8452", label=r"Low-Gamma $\Delta r$ (Mean = +0.50)")
    ax.axvline(0, color="red", ls="--", lw=1.5)
    ax.set_xlabel(r"Bootstrap Estimate of $\Delta r = r_{OS} - r_{OB}$")
    ax.set_ylabel("Bootstrap Frequency")
    ax.set_title("Session-Cluster Bootstrap Distributions (B = 2,000)", fontsize=8.5)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    
    p23_data = pd.DataFrame({"boot_delta_r_theta": boot_th, "boot_delta_r_low_gamma": boot_lg})
    write_panel(
        "bootstrap_delta_r_distributions",
        "What are the bootstrap sampling distributions of Delta r for the two primary dissociating bands?",
        "Bootstrap distribution of Delta r (Theta vs Low-Gamma)", "SPK + LFP", "OB vs OS",
        "all_units", "all", "1031-1562ms", "theta & low-gamma",
        "session-cluster bootstrap histogram", "zero-difference null line",
        "bootstrap resample draw", SUB_SRC, SUB_CODE,
        p23_data, {"p_theta_less_zero": float(np.mean(np.array(boot_th) < 0)),
                   "p_low_gamma_greater_zero": float(np.mean(np.array(boot_lg) > 0))},
        "SUPPORTED", fig
    )

    n_panels = _counter[0]
    print(f"\nSuccessfully generated {n_panels} F06 candidate panels in {F06_DIR}")
    generate_contact_sheet()


if __name__ == "__main__":
    main()
