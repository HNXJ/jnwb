r"""
Figure 5 supplement (2026-08-06, per request): Models A-E from
scripts/fit_omission_band_power_glmm.py, each as its own figure in fig05's own visual style
(one bar-chart subpanel per band, x-axis = that model's grouping variable, dark orange = Holm-
Bonferroni, light orange = BH-FDR only, gray = neither) -- the same `draw_band_panels` layout
fig05's own headline uses, generalized to whatever each model's grouping variable is. Each
model gets its OWN declared correction family (never pooled across models).

MODELS (see fit_omission_band_power_glmm.py's own docstring for the full design rationale)
    A  corpus-wide, per band: db ~ 1, session/probe random effects. Tests whether the omitted
       slot differs from the local pre-omission baseline, pooling every area and subject.
       Uses the SESSION-LEVEL companion (A_session_level, one obs per session, avoiding
       channel pseudo-replication) -- not the channel-level model, per this project's own
       stated preference for the session-level numbers.
    B  per subject, per band: same as A, fit separately within each of the 3 subjects. Shows
       whether the corpus-wide (Model A) result is carried by one animal.
    C  area effects, DESCRIPTIVE: db ~ C(area), session-level. Area and subject are confounded
       in this corpus (several areas recorded in only one animal), so this is NOT the
       subject-controlled result (that is Model F, the main figure) -- reported here only as
       the uncontrolled comparison Model F was built to improve on.
    D  the one defensible V3 contrast: V3a/d vs V1/V2 within a single subject (V198o, the only
       one with V3a/d and V1/V2 on separate probes in the same sessions), session-level.
    E  laminar: db ~ C(putative_layer), channel-level (session/probe as variance components,
       no separate session-level companion exists for this model -- fit_omission_band_power_
       glmm.py only fits it once). Interpret with the channel-level caveat that applies to any
       model without a session-level collapse.

OUTPUT
    svg/fig05_supp_modelA.svg/.png ... svg/fig05_supp_modelE.svg/.png
    svg/fig05_supp_modelA_stats.md/.csv ... (one stats file per model, own family)
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.dirname(HERE)
sys.path.insert(0, FIGDIR)
from figstats import Result, correct, write  # noqa: E402

REPO = os.path.dirname(os.path.dirname(FIGDIR))
GLMM_CSV = os.path.join(REPO, "outputs", "lfp_band_census_v2", "glmm_summary.csv")
SVG_DIR = os.path.join(HERE, "svg")

BANDS = ["theta", "alpha", "beta", "low_gamma", "high_gamma"]
BAND_DISPLAY = {"theta": "Theta(4-8Hz)", "alpha": "Alpha(8-14Hz)", "beta": "Beta(14-30Hz)",
                "low_gamma": "Gamma(Low,30-50Hz)", "high_gamma": "Gamma(High,50-80Hz)"}


def draw_model_band_panels(rows_by_band_group, groups, out_stem, title, ylabel, n_tests):
    """rows_by_band_group[band][group] = (estimate, se, p_holm, q_bh). One row (5 band
    subpanels), x-axis = groups -- byte-identical visual style to fig05_v1_area_hierarchy_glmm.
    draw_band_panels."""
    fig, axes = plt.subplots(1, len(BANDS), figsize=(3.0 * len(BANDS), 3.2), sharey=True)
    x = np.arange(len(groups))
    for ax, band in zip(axes, BANDS):
        vals, ses, colors = [], [], []
        for g in groups:
            est, se, p_holm, q_bh = rows_by_band_group[band].get(g, (np.nan, np.nan, np.nan, np.nan))
            vals.append(est); ses.append(se)
            if np.isfinite(p_holm) and p_holm < 0.05:
                colors.append("#A63603")
            elif np.isfinite(q_bh) and q_bh < 0.05:
                colors.append("#FDAE6B")
            else:
                colors.append("0.75")
        ax.bar(x, vals, yerr=ses, color=colors, edgecolor="black", linewidth=0.4, capsize=2)
        ax.axhline(0, color="black", lw=0.8)
        ax.set_xticks(x); ax.set_xticklabels(groups, rotation=90 if len(groups) > 3 else 0,
                                             fontsize=7)
        ax.set_title(BAND_DISPLAY[band], fontsize=8)
    axes[0].set_ylabel(ylabel, fontsize=8)
    fig.suptitle(title, fontsize=11, fontweight="bold", y=1.05)
    fig.text(0.5, -0.02, f"Dark orange: p_holm < 0.05 (family of {n_tests} tests, this model "
            "only). Light orange: q_BH < 0.05 only. Gray: neither.",
            ha="center", fontsize=7.5, color="0.25")
    out = os.path.join(SVG_DIR, out_stem)
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)
    return out + ".svg"


def build_and_draw(df, model, group_col, groups, drop_intercept, out_stem, title, ylabel,
                   family, figure_name, question_fmt):
    sub = df[df.model == model].copy()
    if drop_intercept:
        sub = sub[sub.term != "Intercept"]
    results = []
    for _, row in sub.iterrows():
        g = row[group_col] if group_col != "term" else row.term
        results.append(Result(
            figure=figure_name, panel=model, question=question_fmt.format(g=g, band=row.band),
            test=f"{row.estimator} ({model})", statistic_name="t", statistic=float(row.z),
            df="", n=int(row.n_sessions) if pd.notna(row.n_sessions) else int(row.n_obs),
            unit="session" if pd.notna(row.n_sessions) else "channel",
            effect_name="estimate_db", effect=float(row.estimate_db), p=float(row.p_raw),
            family=family, note=f"estimator={row.estimator}"))
    corrected = correct(results)

    rows_by_band_group = {b: {} for b in BANDS}
    sig_lookup = {}
    for r, row in zip(corrected, sub.itertuples()):
        g = getattr(row, group_col) if group_col != "term" else row.term
        rows_by_band_group[row.band][g] = (row.estimate_db, row.se, r.p_holm, r.q_bh)

    svg = draw_model_band_panels(rows_by_band_group, groups, out_stem, title, ylabel,
                                 len(results))
    n_holm = sum(1 for r in corrected if r.p_holm is not None and r.p_holm < 0.05)
    n_bh = sum(1 for r in corrected if r.q_bh is not None and r.q_bh < 0.05)
    print(f"{model}: {n_holm}/{len(results)} Holm, {n_bh}/{len(results)} BH-FDR")
    write(results, SVG_DIR, out_stem, title=title,
         preamble=f"Family: all {len(results)} tests for this model alone, corrected together "
                  f"(Holm-Bonferroni + BH-FDR), never pooled with any other model's family.")
    return svg


def main():
    os.makedirs(SVG_DIR, exist_ok=True)
    df = pd.read_csv(GLMM_CSV)

    svgs = []
    df_a = df.copy()
    df_a.loc[df_a.model == "A_session_level", "term"] = "corpus"
    svgs.append(build_and_draw(
        df_a, "A_session_level", "term", ["corpus"], drop_intercept=False,
        out_stem="fig05_supp_modelA",
        title="Model A -- corpus-wide, per band (all areas & subjects pooled)",
        ylabel="dB, omitted slot vs local baseline\n(estimate +- SE)",
        family="fig05_supp_modelA", figure_name="fig05_supp_A",
        question_fmt="corpus-wide {band} != 0"))

    d_b = df[df.model == "B_session_level"].copy()
    subjects_b = sorted(d_b.subject.unique())
    svgs.append(build_and_draw(
        df, "B_session_level", "subject", subjects_b, drop_intercept=False,
        out_stem="fig05_supp_modelB",
        title="Model B -- per subject, per band",
        ylabel="dB, omitted slot vs local baseline\n(estimate +- SE)",
        family="fig05_supp_modelB", figure_name="fig05_supp_B",
        question_fmt="{g} {band} != 0"))

    d_c = df[df.model == "C_area_session_level"].copy()
    areas_c = sorted(d_c[d_c.term != "Intercept"].term.str.extract(r"\[T\.(.+)\]")[0].unique())
    d_c["area"] = d_c.term.str.extract(r"\[T\.(.+)\]")
    svgs.append(build_and_draw(
        d_c, "C_area_session_level", "area", areas_c, drop_intercept=True,
        out_stem="fig05_supp_modelC",
        title="Model C -- area effects vs V1, DESCRIPTIVE (confounded with subject)",
        ylabel="dB vs V1\n(estimate +- SE)",
        family="fig05_supp_modelC", figure_name="fig05_supp_C",
        question_fmt="{g} {band} vs V1 (descriptive)"))

    d_d = df[df.model == "D_session_level_V3_vs_V1V2"].copy()
    subjects_d = sorted(d_d.subject.unique())
    svgs.append(build_and_draw(
        df, "D_session_level_V3_vs_V1V2", "subject", subjects_d, drop_intercept=False,
        out_stem="fig05_supp_modelD",
        title="Model D -- V3a/d vs V1/V2, within-subject (only design supporting this contrast)",
        ylabel="dB, V3a/d - V1/V2\n(estimate +- SE)",
        family="fig05_supp_modelD", figure_name="fig05_supp_D",
        question_fmt="{g} V3a/d vs V1/V2 {band}"))

    d_e = df[df.model == "E_laminar"].copy()
    layers_e = sorted(d_e[d_e.term != "Intercept"].term.str.extract(r"\[T\.(.+)\]")[0].unique())
    d_e["layer"] = d_e.term.str.extract(r"\[T\.(.+)\]")
    svgs.append(build_and_draw(
        d_e, "E_laminar", "layer", layers_e, drop_intercept=True,
        out_stem="fig05_supp_modelE",
        title="Model E -- laminar (putative layer vs deep), channel-level",
        ylabel="dB vs deep\n(estimate +- SE)",
        family="fig05_supp_modelE", figure_name="fig05_supp_E",
        question_fmt="{g} vs deep {band} (channel-level)"))

    print(f"\nWROTE {len(svgs)} model supplement figures to {SVG_DIR}/")
    for s in svgs:
        print(" ", s)


if __name__ == "__main__":
    main()
