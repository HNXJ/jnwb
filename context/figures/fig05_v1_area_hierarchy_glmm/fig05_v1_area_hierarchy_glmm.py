r"""
Figure 5 -- LFP band-power hierarchy vs V1, subject-controlled GLMM (area x band).

WHY THIS IS FIGURE 5, NOT A CONNECTIVITY NETWORK
    All three LFP-LFP connectivity methods attempted for this slot -- undirected imaginary
    coherency, directed Granger causality, transfer entropy -- came back null at the group
    level on this corpus (see ../lfp_lfp_connectivity_supplement/README.md for the full
    three-method record, preserved as supplements, not discarded). Per
    feedback_figures_require_significance (figures 4-7 must carry a group-level significant
    result), fig05 pivoted 2026-08-05 to this area x band contrast instead, which IS
    significant once two real bugs in its source analysis were found and fixed -- see
    artifacts/.lab/v3ad_beta_glmm_two_bugs_fixed_20260805.json for the full bug/fix record
    before citing any number from this figure.

INPUT
    outputs/lfp_band_census_v2/glmm_summary.csv, model 'F_area_subject_controlled_session_level'
    -- written by scripts/fit_omission_band_power_glmm.py. Response: db_mid_omirel (power in
    the omitted slot relative to the -250..-50 ms omission-relative baseline, dB, trial-averaged
    within channel, then session-averaged within area before this model sees it).

MODEL
    db ~ C(area, Treatment('V1')) + C(subject), session-level (one row per session x area,
    collapsing channels first to avoid pseudo-replication), all 23 sessions, all 3 subjects.
    Subject is an explicit ADDITIVE fixed effect -- not a random-effect stratification (Model C,
    confounded) and not a same-session-probe-pairing requirement (Model D, limited to 5
    sessions/1 subject by the recording design). Identifiable because the area x subject design
    is connected (every area recorded in >=2 subjects; V4 spans all three) -- CLAUDE.md's own
    verification doctrine established this property for this exact corpus.
    Fit via MixedLM (REML, session random intercept) where it converges (low_gamma, high_gamma);
    OLS with session-cluster-robust SEs where MixedLM hits a singular matrix (theta, alpha,
    beta) -- the estimator used is disclosed per cell, not hidden (see 'estimator' column in the
    source CSV).

STATISTICS
    All 9 areas x 5 bands = 45 tests are ONE declared family (the full grid), corrected together
    via figstats.correct() (Holm for family-wise error rate, BH for false discovery rate) --
    NOT corrected per-area-across-bands, which the source script's own internal correction does
    for its own bookkeeping but which is not the family this figure reports.

RESULT
    2/45 survive Holm-Bonferroni: FEF low-gamma (p_holm=0.0076) and PFC low-gamma
    (p_holm=0.0088) -- the headline. 11/45 survive Benjamini-Hochberg FDR, including V3a/d beta
    (q_BH=0.030) and V3a/d low-gamma (q_BH=0.030) -- reported as FDR-level evidence, a weaker
    guarantee than the two Holm survivors, not folded into the same claim.

OUTPUT
    fig05.svg, svg/fig05_area_band_heatmap.svg/.png
    svg/fig05_stats.md/.csv
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.dirname(HERE)
sys.path.insert(0, FIGDIR)
from figstyle import AREA_ORDER  # noqa: E402
from figstats import Result, correct, write  # noqa: E402
from svgassemble import assemble  # noqa: E402

REPO = os.path.dirname(os.path.dirname(FIGDIR))
GLMM_CSV = os.path.join(REPO, "outputs", "lfp_band_census_v2", "glmm_summary.csv")
STIM_GLMM_CSV = os.path.join(REPO, "outputs", "lfp_band_census_stim", "glmm_summary.csv")
SVG_DIR = os.path.join(HERE, "svg")

BANDS = ["theta", "alpha", "beta", "low_gamma", "high_gamma"]
BAND_DISPLAY = {"theta": "Theta(4-8Hz)", "alpha": "Alpha(8-14Hz)", "beta": "Beta(14-30Hz)",
                "low_gamma": "Gamma(Low,30-50Hz)", "high_gamma": "Gamma(High,50-80Hz)"}
MODEL = "F_area_subject_controlled_session_level"
REF_AREA = "V1"


def load_model_f(csv_path=GLMM_CSV):
    df = pd.read_csv(csv_path)
    d = df[(df.model == MODEL) & (df.term.str.startswith("C(area"))].copy()
    d["area"] = d.term.str.extract(r"\[T\.(.+)\]")
    return d


def build_family(d, family="fig05_area_band", figure="fig05"):
    results = []
    for _, row in d.iterrows():
        results.append(Result(
            figure=figure, panel="area_band_glmm",
            question=f"{row.area} {row.band} vs {REF_AREA}",
            test=f"{row.estimator} (Model F, subject-controlled)", statistic_name="t",
            statistic=float(row.z), df=None, n=int(row.n_sessions), unit="session",
            effect_name="estimate_db", effect=float(row.estimate_db), p=float(row.p_raw),
            family=family,
            note=f"estimator={row.estimator}; n_sessions={int(row.n_sessions)}"))
    return correct(results)


def draw_heatmap(d, corrected, areas, out_stem, title=None, window_label="omitted-slot window"):
    sig = {}
    for r in corrected:
        area, band = r.question.split(" ")[0], r.question.split(" ")[1]
        sig[(area, band)] = (r.p_holm, r.q_bh)

    n_areas, n_bands = len(areas), len(BANDS)
    mat = np.full((n_areas, n_bands), np.nan)
    for i, a in enumerate(areas):
        for j, b in enumerate(BANDS):
            row = d[(d.area == a) & (d.band == b)]
            if not row.empty:
                mat[i, j] = row.estimate_db.values[0]

    fig, ax = plt.subplots(figsize=(6.0, 5.2))
    vmax = np.nanmax(np.abs(mat))
    im = ax.imshow(mat, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    for i, a in enumerate(areas):
        for j, b in enumerate(BANDS):
            p_holm, q_bh = sig.get((a, b), (np.nan, np.nan))
            # inset from the cell boundary so adjacent significant cells don't share an edge --
            # a shared edge reads as one merged region rather than two distinct significant
            # cells, found by rendering and looking, not assumed to be fine from the code alone.
            m = 0.09
            if np.isfinite(p_holm) and p_holm < 0.05:
                ax.add_patch(plt.Rectangle((j - 0.5 + m, i - 0.5 + m), 1 - 2 * m, 1 - 2 * m,
                                           fill=False, edgecolor="black", lw=2.2))
            elif np.isfinite(q_bh) and q_bh < 0.05:
                ax.add_patch(plt.Rectangle((j - 0.5 + m, i - 0.5 + m), 1 - 2 * m, 1 - 2 * m,
                                           fill=False, edgecolor="black", lw=1.2, linestyle="--"))
    ax.set_xticks(range(n_bands))
    ax.set_xticklabels([BAND_DISPLAY[b] for b in BANDS], rotation=30, ha="right", fontsize=9)
    ax.set_yticks(range(n_areas))
    ax.set_yticklabels(areas, fontsize=10)
    ax.set_title(title or f"LFP band power vs {REF_AREA}, subject-controlled (Model F, "
                f"23 sessions, 3 subjects)", fontsize=10)
    cb = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
    cb.set_label(f"dB vs {REF_AREA} ({window_label})", rotation=270, labelpad=14, fontsize=9)
    fig.text(0.5, -0.02, "Solid outline: p_holm < 0.05 (family-wise, 45 tests).  "
            "Dashed outline: q_BH < 0.05 only (FDR, weaker guarantee).",
            ha="center", fontsize=7.5, color="0.25")
    out = os.path.join(SVG_DIR, out_stem)
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)
    return out + ".svg"


def draw_band_panels(d, corrected, areas, out_stem, title=None, window_label="omitted-slot window"):
    """Main-figure layout as of 2026-08-06: one bar-chart subpanel per band (area vs V1),
    replacing the single combined heatmap (moved to svg/fig05_area_band_heatmap.svg as a
    supplement) -- per explicit user direction that the headline should be split by band rather
    than shown as one dense grid."""
    sig = {}
    for r in corrected:
        area, band = r.question.split(" ")[0], r.question.split(" ")[1]
        sig[(area, band)] = (r.p_holm, r.q_bh)

    fig, axes = plt.subplots(1, len(BANDS), figsize=(3.0 * len(BANDS), 3.4), sharey=True)
    x = np.arange(len(areas))
    for ax, band in zip(axes, BANDS):
        vals, ses = [], []
        for a in areas:
            row = d[(d.area == a) & (d.band == band)]
            vals.append(row.estimate_db.values[0] if not row.empty else np.nan)
            ses.append(row.se.values[0] if not row.empty else np.nan)
        vals, ses = np.array(vals), np.array(ses)
        colors = ["#A63603" if np.isfinite(sig.get((a, band), (np.nan, np.nan))[0]) and
                  sig[(a, band)][0] < 0.05 else
                  ("#FDAE6B" if np.isfinite(sig.get((a, band), (np.nan, np.nan))[1]) and
                   sig[(a, band)][1] < 0.05 else "0.75")
                  for a in areas]
        ax.bar(x, vals, yerr=ses, color=colors, edgecolor="black", linewidth=0.4, capsize=2)
        ax.axhline(0, color="black", lw=0.8)
        ax.set_xticks(x); ax.set_xticklabels(areas, rotation=90, fontsize=7)
        ax.set_title(BAND_DISPLAY[band], fontsize=8)
    axes[0].set_ylabel(f"dB vs {REF_AREA} ({window_label})\n(estimate +- SE, Model F)",
                       fontsize=8)
    fig.suptitle(title or f"LFP band power vs {REF_AREA}, subject-controlled (Model F, "
                f"23 sessions, 3 subjects)", fontsize=11, fontweight="bold", y=1.06)
    fig.text(0.5, -0.04, "Dark orange: p_holm < 0.05 (family-wise, 45 tests). "
            "Light orange: q_BH < 0.05 only (FDR, weaker guarantee). Gray: neither.",
            ha="center", fontsize=7.5, color="0.25")
    out = os.path.join(SVG_DIR, out_stem)
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)
    return out + ".svg"


def _pairwise_value_lookup(pw):
    """dict (frozenset({areaA,areaB}), band) -> (areaA, areaB, estimate_db, se). Stored
    convention (see load_pairwise): estimate_db = areaB - areaA, term = 'areaB - areaA'."""
    out = {}
    for _, row in pw.iterrows():
        out[(frozenset((row.areaA, row.areaB)), row.band)] = \
            (row.areaA, row.areaB, row.estimate_db, row.se)
    return out


def _pairwise_sig_lookup(pw_corrected):
    """dict (frozenset({areaA,areaB}), band) -> (p_holm, q_bh), from the ALREADY-corrected
    225-test pairwise family (build_pairwise_family) -- a genuinely different declared family
    from the main figure's 45-test vs-V1 family, per this script's own module docstring."""
    sig = {}
    for r in pw_corrected:
        parts = r.question.split(" ")
        a, b_area, band = parts[0], parts[2], parts[3]
        sig[(frozenset((a, b_area)), band)] = (r.p_holm, r.q_bh)
    return sig


def _ref_row_from_pairwise(val_lookup, sig_lookup, ref_area, areas):
    """area - ref_area, per band, for every area != ref_area -- derived from the pairwise
    225-test family, NOT refit. Returns dict band -> (vals, ses, sig_list)."""
    out = {}
    for band in BANDS:
        vals, ses, sigs = [], [], []
        for a in areas:
            key = (frozenset((a, ref_area)), band)
            if key not in val_lookup:
                vals.append(np.nan); ses.append(np.nan); sigs.append((np.nan, np.nan))
                continue
            area_a, area_b, est, se = val_lookup[key]
            # want a - ref_area; stored est = area_b - area_a
            if area_b == a and area_a == ref_area:
                v = est
            elif area_b == ref_area and area_a == a:
                v = -est
            else:
                v = np.nan
            vals.append(v); ses.append(se)
            sigs.append(sig_lookup.get(key, (np.nan, np.nan)))
        out[band] = (np.array(vals), np.array(ses), sigs)
    return out


def _row_from_model_f(d, corrected, areas):
    """area - V1, per band, from Model F's own dedicated 45-test family (NOT the pairwise
    family) -- kept as the original headline's basis, unchanged. Returns dict band ->
    (vals, ses, sig_list)."""
    sig = {}
    for r in corrected:
        area, band = r.question.split(" ")[0], r.question.split(" ")[1]
        sig[(area, band)] = (r.p_holm, r.q_bh)
    out = {}
    for band in BANDS:
        vals, ses, sigs = [], [], []
        for a in areas:
            row = d[(d.area == a) & (d.band == band)]
            vals.append(row.estimate_db.values[0] if not row.empty else np.nan)
            ses.append(row.se.values[0] if not row.empty else np.nan)
            sigs.append(sig.get((a, band), (np.nan, np.nan)))
        out[band] = (np.array(vals), np.array(ses), sigs)
    return out


def draw_multi_ref_band_panels(rows_spec, out_stem, window_label="omitted-slot window"):
    """rows_spec: list of (ref_area, areas_for_row, row_data, family_label) where row_data is
    the dict band -> (vals, ses, sig_list) from _row_from_model_f (V1 row, 45-test family) or
    _ref_row_from_pairwise (V4/PFC rows, 225-test pairwise family) -- two DIFFERENT declared
    families, deliberately not conflated (see module docstring); family_label is shown per row
    so a reader always knows which correction basis that row's colors come from.

    2026-08-06: added per explicit request for "vs V4" and "vs PFC" rows alongside the original
    "vs V1" headline row -- three rows, one per reference area, five columns, one per band.
    """
    n_rows, n_bands = len(rows_spec), len(BANDS)
    fig, axes = plt.subplots(n_rows, n_bands, figsize=(3.0 * n_bands, 3.0 * n_rows), sharex=False)
    if n_rows == 1:
        axes = axes[None, :]
    for ri, (ref_area, areas, row_data, family_label) in enumerate(rows_spec):
        x = np.arange(len(areas))
        for ci, band in enumerate(BANDS):
            ax = axes[ri, ci]
            vals, ses, sigs = row_data[band]
            colors = ["#A63603" if np.isfinite(p) and p < 0.05 else
                      ("#FDAE6B" if np.isfinite(q) and q < 0.05 else "0.75")
                      for (p, q) in sigs]
            ax.bar(x, vals, yerr=ses, color=colors, edgecolor="black", linewidth=0.4, capsize=2)
            ax.axhline(0, color="black", lw=0.8)
            ax.set_xticks(x); ax.set_xticklabels(areas, rotation=90, fontsize=7)
            if ri == 0:
                ax.set_title(BAND_DISPLAY[band], fontsize=8)
        axes[ri, 0].set_ylabel(f"dB vs {ref_area} ({window_label})\n(estimate +- SE)"
                               f"\n[{family_label}]", fontsize=7)
    fig.suptitle("LFP band power vs V1 / V4 / PFC, subject-controlled (Model F, 23 sessions, "
                "3 subjects)", fontsize=11, fontweight="bold", y=1.01)
    fig.text(0.5, -0.01, "Dark orange: p_holm < 0.05 within that row's own declared family. "
            "Light orange: q_BH < 0.05 only. Gray: neither. Row 1 (vs V1): Model F's own "
            "45-test family. Rows 2-3 (vs V4, vs PFC): derived from the SAME pairwise-contrast "
            "model fit, but drawn from the 225-test all-pairs family, not refit or re-corrected.",
            ha="center", fontsize=7, color="0.25")
    out = os.path.join(SVG_DIR, out_stem)
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)
    return out + ".svg"


def load_pairwise(csv_path=GLMM_CSV):
    df = pd.read_csv(csv_path)
    d = df[df.model == "F_pairwise_area_contrasts"].copy()
    d["areaB"] = d.term.str.split(" - ").str[0]
    d["areaA"] = d.term.str.split(" - ").str[1]
    return d


def build_pairwise_family(d, family="fig05_supp_pairwise_area_band", figure="fig05_supp"):
    """All C(10,2)=45 area pairs x 5 bands = 225 tests, declared as its own family -- a
    genuinely different question ('which area PAIRS differ') from the 45-test vs-V1 family
    above ('which areas differ from V1'), not a superset silently reusing the same correction."""
    results = []
    for _, row in d.iterrows():
        results.append(Result(
            figure=figure, panel="pairwise_area_band_glmm",
            question=f"{row.areaA} vs {row.areaB} {row.band}",
            test=f"{row.estimator} (Model F pairwise contrast)", statistic_name="t",
            statistic=float(row.z), df=None, n=int(row.n_sessions), unit="session",
            effect_name="estimate_db", effect=float(row.estimate_db), p=float(row.p_raw),
            family=family,
            note=f"estimator={row.estimator}; n_sessions={int(row.n_sessions)}"))
    return correct(results)


def draw_pairwise_grid(d, corrected, areas, out_stem, title, cbar_label):
    sig = {}
    for r in corrected:
        parts = r.question.split(" ")
        a, b_area, band = parts[0], parts[2], parts[3]
        sig[(a, b_area, band)] = (r.p_holm, r.q_bh)
        sig[(b_area, a, band)] = (r.p_holm, r.q_bh)

    n = len(areas)
    fig, axes = plt.subplots(1, len(BANDS), figsize=(3.3 * len(BANDS), 3.6))
    mats = {}
    for band in BANDS:
        mat = np.full((n, n), np.nan)
        for i, a in enumerate(areas):
            for j, b_area in enumerate(areas):
                if i == j:
                    continue
                row = d[(d.band == band) & (((d.areaA == a) & (d.areaB == b_area)) |
                                            ((d.areaA == b_area) & (d.areaB == a)))]
                if row.empty:
                    continue
                # stored estimate_db = areaB - areaA (see load_pairwise); mat[i=a, j=b_area]
                # must equal a - b_area (row minus column, per the figure's own caption) --
                # flip sign whenever the stored row's areaB is the COLUMN area, since that
                # means the stored value is b_area - a, the negative of what this cell needs.
                val = row.estimate_db.values[0]
                sign = -1.0 if row.areaB.values[0] == b_area else 1.0
                mat[i, j] = sign * val
        mats[band] = mat
    vmax = max(np.nanmax(np.abs(m)) for m in mats.values() if np.any(np.isfinite(m)))
    im0 = None
    for ax, band in zip(axes, BANDS):
        mat = mats[band]
        im = ax.imshow(mat, cmap="RdBu_r", vmin=-vmax, vmax=vmax)
        im0 = im0 or im
        m = 0.09
        for i, a in enumerate(areas):
            for j, b_area in enumerate(areas):
                if i >= j:
                    continue
                p_holm, q_bh = sig.get((a, b_area, band), (np.nan, np.nan))
                if np.isfinite(p_holm) and p_holm < 0.05:
                    ax.add_patch(plt.Rectangle((j - 0.5 + m, i - 0.5 + m), 1 - 2 * m, 1 - 2 * m,
                                               fill=False, edgecolor="black", lw=1.8))
                elif np.isfinite(q_bh) and q_bh < 0.05:
                    ax.add_patch(plt.Rectangle((j - 0.5 + m, i - 0.5 + m), 1 - 2 * m, 1 - 2 * m,
                                               fill=False, edgecolor="black", lw=1.0,
                                               linestyle="--"))
        ax.set_xticks(range(n)); ax.set_xticklabels(areas, rotation=90, fontsize=6)
        ax.set_yticks(range(n)); ax.set_yticklabels(areas, fontsize=6)
        ax.set_title(BAND_DISPLAY[band], fontsize=8)
    fig.suptitle(title, fontsize=11, y=1.03)
    cb = fig.colorbar(im0, ax=axes, shrink=0.75, pad=0.01)
    cb.set_label(cbar_label, rotation=270, labelpad=14, fontsize=8)
    fig.text(0.5, -0.03, "Row minus column, dB. Solid: p_holm<0.05 (family of 225: all area "
            "pairs x bands). Dashed: q_BH<0.05 only.", ha="center", fontsize=7, color="0.3")
    out = os.path.join(SVG_DIR, out_stem)
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)
    return out + ".svg"


def main():
    os.makedirs(SVG_DIR, exist_ok=True)
    d = load_model_f()
    areas = [a for a in AREA_ORDER if a != REF_AREA and a in set(d.area)]
    corrected = build_family(d)

    write(corrected, SVG_DIR, "fig05",
         title="Figure 5 -- LFP band-power hierarchy vs V1, subject-controlled GLMM",
         preamble="Model F: db ~ C(area, Treatment('V1')) + C(subject), session-level, all 23 "
                  "sessions, all 3 subjects, subject as an additive fixed effect (see "
                  "scripts/fit_omission_band_power_glmm.py). Full 9-area x 5-band grid (45 "
                  "tests) is ONE declared family, Holm and BH-FDR both reported. Two bugs in "
                  "the source script were found and fixed before this figure was built -- see "
                  "artifacts/.lab/v3ad_beta_glmm_two_bugs_fixed_20260805.json.")

    n_holm = sum(1 for r in corrected if r.p_holm is not None and r.p_holm < 0.05)
    n_bh = sum(1 for r in corrected if r.q_bh is not None and r.q_bh < 0.05)
    print(f"significant: {n_holm}/45 Holm, {n_bh}/45 BH-FDR")

    heatmap_svg = draw_heatmap(d, corrected, areas, "fig05_area_band_heatmap")

    # ---- pairwise family (needed both for its own supplement and for the vs-V4/vs-PFC rows
    # below -- computed here, before the headline, so the headline can use it) ----------------
    pw = load_pairwise()
    all_areas = [a for a in AREA_ORDER if a in set(pw.areaA) | set(pw.areaB)]
    pw_corrected = build_pairwise_family(pw)

    # Headline (2026-08-06, extended 2026-08-06): bar-chart subpanels, one row per reference
    # area (V1, V4, PFC) x one column per band, per explicit request -- replaces the
    # single-row-vs-V1-only version. V1 row from Model F's own dedicated 45-test family
    # (unchanged); V4/PFC rows derived from the SAME pairwise-contrast fit but read through the
    # 225-test all-pairs family (see draw_multi_ref_band_panels docstring for why these are two
    # different declared families, not conflated).
    val_lookup = _pairwise_value_lookup(pw)
    sig_lookup_pw = _pairwise_sig_lookup(pw_corrected)
    rows_spec = [("V1", areas, _row_from_model_f(d, corrected, areas), "vs-V1, 45-test family")]
    for ref in ("V4", "PFC"):
        row_areas = [a for a in AREA_ORDER if a != ref and a in all_areas]
        rows_spec.append((ref, row_areas,
                          _ref_row_from_pairwise(val_lookup, sig_lookup_pw, ref, row_areas),
                          "vs-" + ref + ", 225-test pairwise family"))
    band_panels_svg = draw_multi_ref_band_panels(rows_spec, "fig05_area_band_panels")
    out, w, h = assemble([band_panels_svg], os.path.join(HERE, "fig05.svg"), ncol=1)
    print(f"assembled -> {out}  {w:.1f} x {h:.1f} pt")

    # ---- supplement: full area x area pairwise matrix (omission window) ------------------
    write(pw_corrected, SVG_DIR, "fig05_supp_pairwise",
         title="Figure 5 supplement -- all area x area LFP band-power contrasts, omission window",
         preamble="Same Model F fit as the main figure, all C(10,2)=45 area pairs x 5 bands = "
                  "225 tests, declared as its OWN family (a different question -- 'which area "
                  "pairs differ' -- from the main figure's 45-test 'which areas differ from "
                  "V1' family), corrected together.")
    n_pw_holm = sum(1 for r in pw_corrected if r.p_holm is not None and r.p_holm < 0.05)
    n_pw_bh = sum(1 for r in pw_corrected if r.q_bh is not None and r.q_bh < 0.05)
    print(f"pairwise significant: {n_pw_holm}/225 Holm, {n_pw_bh}/225 BH-FDR")
    draw_pairwise_grid(pw, pw_corrected, all_areas, "fig05_supp_pairwise_omission",
                       "All-area LFP band-power contrasts, omission window (omitted-slot vs "
                       "pre-omission baseline)", "dB (row - column)")

    # ---- supplement: stimulus-window counterpart (real stimulus vs its own baseline) ------
    # Matched design, same Model F, same estimator choices, fit on
    # scripts/fit_stim_band_power_glmm.py's output. Result: NULL (0/45 Holm, 0/45 BH) -- unlike
    # the omission window, the area hierarchy does not survive correction for a real stimulus.
    # Reported honestly, not smoothed over: this is itself informative (the omission-linked
    # hierarchy looks specific to the omission window, not a generic baseline area difference
    # that would show up regardless of condition), not folded into the main figure's claim.
    d_stim = load_model_f(STIM_GLMM_CSV)
    areas_stim = [a for a in AREA_ORDER if a != REF_AREA and a in set(d_stim.area)]
    corrected_stim = build_family(d_stim, family="fig05_stim_area_band", figure="fig05_supp")
    write(corrected_stim, SVG_DIR, "fig05_supp_stim",
         title="Figure 5 supplement -- LFP band-power hierarchy vs V1, stimulus window "
               "(subject-controlled GLMM)",
         preamble="Matched counterpart to the main figure's omission-window Model F, same "
                  "design, same 45-cell family, fit on a real-stimulus census "
                  "(scripts/compute_stim_channel_band_power_census.py, "
                  "scripts/fit_stim_band_power_glmm.py). NULL: 0/45 Holm, 0/45 BH-FDR.")
    n_stim_holm = sum(1 for r in corrected_stim if r.p_holm is not None and r.p_holm < 0.05)
    n_stim_bh = sum(1 for r in corrected_stim if r.q_bh is not None and r.q_bh < 0.05)
    print(f"stimulus-window significant: {n_stim_holm}/45 Holm, {n_stim_bh}/45 BH-FDR "
         "(expected null)")
    draw_heatmap(d_stim, corrected_stim, areas_stim, "fig05_supp_area_band_heatmap_stim",
                title="LFP band power vs V1, stimulus window, subject-controlled (Model F)",
                window_label="real-stimulus window")

    pw_stim = load_pairwise(STIM_GLMM_CSV)
    all_areas_stim = [a for a in AREA_ORDER if a in set(pw_stim.areaA) | set(pw_stim.areaB)]
    pw_stim_corrected = build_pairwise_family(
        pw_stim, family="fig05_supp_pairwise_area_band_stim", figure="fig05_supp")
    write(pw_stim_corrected, SVG_DIR, "fig05_supp_pairwise_stim",
         title="Figure 5 supplement -- all area x area LFP band-power contrasts, "
               "stimulus window",
         preamble="Stimulus-window counterpart to the omission-window pairwise supplement, "
                  "same 225-test family design.")
    n_pws_holm = sum(1 for r in pw_stim_corrected if r.p_holm is not None and r.p_holm < 0.05)
    n_pws_bh = sum(1 for r in pw_stim_corrected if r.q_bh is not None and r.q_bh < 0.05)
    print(f"stimulus-window pairwise significant: {n_pws_holm}/225 Holm, {n_pws_bh}/225 BH-FDR")
    draw_pairwise_grid(pw_stim, pw_stim_corrected, all_areas_stim,
                       "fig05_supp_pairwise_stim",
                       "All-area LFP band-power contrasts, stimulus window (real stimulus vs "
                       "its own pre-stimulus baseline)", "dB (row - column)")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__), "source": GLMM_CSV, "model": MODEL,
        "reference_area": REF_AREA, "areas": areas, "bands": BANDS,
        "n_sessions": 23, "n_subjects": 3,
        "n_significant_holm": n_holm, "n_significant_bh": n_bh,
        "pairwise_n_significant_holm": n_pw_holm, "pairwise_n_significant_bh": n_pw_bh,
        "stimulus_window_n_significant_holm": n_stim_holm,
        "stimulus_window_n_significant_bh": n_stim_bh,
        "stimulus_window_note": "NULL, as expected/reported -- see README",
        "stimulus_pairwise_n_significant_holm": n_pws_holm,
        "stimulus_pairwise_n_significant_bh": n_pws_bh,
        "bug_fix_receipt": "artifacts/.lab/v3ad_beta_glmm_two_bugs_fixed_20260805.json",
    }
    with open(os.path.join(SVG_DIR, "fig05_receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)


if __name__ == "__main__":
    main()
