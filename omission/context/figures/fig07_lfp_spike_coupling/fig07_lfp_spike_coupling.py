r"""
Figure 7 -- population firing rate x LFP band-power modulation, by area, functional group and
band (headline, redesigned 2026-08-05). PPC (per-unit spike-LFP phase coupling, 0/60 in both
contexts after correction) is demoted to a supplement below.

HEADLINE (2026-08-05)
    scripts/extract_population_firing_lfp_power_corr.py + aggregate_..._corr.py +
    fit_population_firing_lfp_power_glmm.py answer: does population-level firing rate (mean
    per-unit rate across a functional group's qualifying units in an area) co-vary trial-to-trial
    with that area's LFP band power, within session (trial-matched, trial-mismatch shuffle
    null), pooled across sessions only after testing (feedback_pool_after_testing_not_before
    memory)? A GLMM (same backbone as figure 5: MixedLM/REML, session random intercept, subject
    additive fixed effect) on the resulting per-session Z finds band is the dominant factor
    (high_gamma/low_gamma >> theta/alpha/beta, Holm p<1e-5), O+ units are LESS coupled than
    Other or S+ units (Holm p<2e-5), MT/MST differ from FEF/PFC/TEO, and condition group
    (baseline/stim/omission) has no detectable effect -- see
    outputs/population_firing_lfp_power_corr/README.md for the full result.

SUPPLEMENT: PPC (built 2026-07-30)
    Pairwise phase consistency between each SUA unit's spike times and its own area's
    representative-channel LFP phase. No area x band effect survives correction at the group
    level in either context (0/60 in each of omission/stimulus). See this directory's git
    history / outputs/spike_lfp_coupling for the full method; kept here as a supplement because
    it is the originally-planned per-unit method this headline replaces, not because it found
    something.

MULTIPLICITY
    Each declared family (population main effects, population pairwise contrasts, PPC omission
    grid, PPC stimulus grid, PPC identity) is corrected together, in one write() call, never
    split or merged across families.
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
from scipy import stats as sst
from statsmodels.stats.multitest import multipletests

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.dirname(HERE)
sys.path.insert(0, FIGDIR)
from figstyle import AREA_COLORS, AREA_ORDER, BANDS  # noqa: E402
from figstats import Result, group_location, paired_location, write  # noqa: E402
from svgassemble import assemble  # noqa: E402

REPO = os.path.dirname(os.path.dirname(FIGDIR))
POP_DIR = os.path.join(REPO, "outputs", "population_firing_lfp_power_corr")
COUPLING_NPZ = os.path.join(REPO, "outputs", "spike_lfp_coupling", "coupling.npz")
SVG_DIR = os.path.join(HERE, "svg")

RAW_BAND = {"Theta": "theta", "Alpha": "alpha", "Beta": "beta",
           "Low": "low_gamma", "High": "high_gamma"}
FUNC_GROUP_ORDER = ["Other", "S+", "S-", "O+", "O++"]
FUNC_GROUP_COLORS = {"Other": "#BDBDBD", "S+": "#1B9E5A", "S-": "#B5651D", "O+": "#C51B8A",
                     "O++": "#7A0177"}
Z_THRESH, ALPHA, MIN_SESSIONS = 1.96, 0.05, 3
SIG_COLORS = {"holm": "#D62728", "bh": "#FF7F0E", "ns": "0.75"}  # red / orange / gray


# ============================================================ headline: population coupling
def band_key_from_disp(band_disp):
    for prefix, raw in RAW_BAND.items():
        if band_disp.startswith(prefix):
            return raw
    return None


def load_population():
    df = pd.read_csv(os.path.join(POP_DIR, "all_session_rows.csv.gz"))
    # session-level effect, averaged across condition groups first (GLMM found no condition
    # group effect -- see module docstring), so each session contributes one value per
    # (area, func_group, band), matching this project's "unit of inference is session" rule.
    sess_effect = df.groupby(["session", "area", "func_group", "band"],
                             as_index=False)["z"].mean()
    return sess_effect


def build_population_panel(sess_effect, areas):
    """dict func_group -> dict band_disp -> (means, sems, ns) across areas -- one cell per
    (functional_type row, band column) in the 2026-08-06 grid layout."""
    cells = {}
    for fg in FUNC_GROUP_ORDER:
        cells[fg] = {}
        for band_disp in BANDS:
            band_key = band_key_from_disp(band_disp)
            d = sess_effect[(sess_effect.band == band_key) & (sess_effect.func_group == fg)]
            m, s, n = [], [], []
            for a in areas:
                vals = d[d.area == a].z.values
                m.append(np.mean(vals) if len(vals) else np.nan)
                s.append(np.std(vals, ddof=1) / np.sqrt(len(vals)) if len(vals) > 1 else np.nan)
                n.append(len(vals))
            cells[fg][band_disp] = (np.array(m), np.array(s), np.array(n))
    return cells


def population_cell_significance(sess_effect, areas):
    """NEW declared family (2026-08-06), fig07_population_cell_hitrate -- one hit-rate test per
    (area, func_group, band) cell on the SAME condition-group-averaged per-session Z the figure
    actually plots (sess_effect: one row per session x area x func_group x band, already
    averaged over baseline/stim/omission per the GLMM's own finding of no condition-group
    effect). This is a NEW test, not a re-read of outputs/population_firing_lfp_power_corr/
    hit_rates.csv -- that file's hit rates are per condition-group (3x as many cells, a
    different, finer-grained question) and averaging THEIR significance flags across condition
    groups post hoc would be exactly the kind of selection this project's own doctrine warns
    against. Session counts as a hit at |Z|>=Z_THRESH; hit rate tested against ALPHA via exact
    binomial; Holm + BH-FDR across the full (area x func_group x band) family, cells with
    >=MIN_SESSIONS sessions only.

    Returns: dict (area, func_group, band_key) -> 'holm'/'bh'/'ns', and the list of Result rows
    (for figstats.write()) for full traceability."""
    rows = []
    for fg in FUNC_GROUP_ORDER:
        for band_key in RAW_BAND.values():
            d = sess_effect[(sess_effect.func_group == fg) & (sess_effect.band == band_key)]
            for a in areas:
                vals = d[d.area == a].z.values
                n = len(vals)
                if n == 0:
                    continue
                k = int(np.sum(np.abs(vals) >= Z_THRESH))
                rows.append({"area": a, "func_group": fg, "band": band_key, "n": n, "k": k})
    cell_df = pd.DataFrame(rows)
    cell_df["binom_p"] = [sst.binomtest(int(r.k), int(r.n), ALPHA,
                                        alternative="greater").pvalue
                          for r in cell_df.itertuples()]
    fam = cell_df[cell_df.n >= MIN_SESSIONS].copy()
    _, holm_p, _, _ = multipletests(fam.binom_p, alpha=ALPHA, method="holm")
    _, bh_p, _, _ = multipletests(fam.binom_p, alpha=ALPHA, method="fdr_bh")
    fam["holm_p"], fam["bh_q"] = holm_p, bh_p

    status = {}
    results = []
    for _, r in cell_df.merge(
            fam[["area", "func_group", "band", "holm_p", "bh_q"]],
            on=["area", "func_group", "band"], how="left").iterrows():
        key = (r.area, r.func_group, r.band)
        if pd.notna(r.holm_p) and r.holm_p < ALPHA:
            status[key] = "holm"
        elif pd.notna(r.bh_q) and r.bh_q < ALPHA:
            status[key] = "bh"
        else:
            status[key] = "ns"
        results.append(Result(
            figure="fig07", panel="population_cell_hitrate",
            question=f"{r.area} {r.func_group} {r.band} hit rate > {ALPHA}",
            test="exact binomial (one-sided, k>=Z_THRESH sessions vs ALPHA)",
            statistic_name="k/n", statistic=float(r.k) / r.n if r.n else np.nan,
            df="", n=int(r.n), unit="session", effect_name="hit_rate",
            effect=float(r.k) / r.n if r.n else np.nan, p=float(r.binom_p),
            family="fig07_population_cell_hitrate",
            note=f"n_sessions={int(r.n)}" + ("" if r.n >= MIN_SESSIONS
                                             else f" (< {MIN_SESSIONS}, excluded from family)")))
    return status, results


def draw_population_figure(sess_effect, areas, sig_status, out_stem):
    """2026-08-06 layout: one ROW per functional_type (population group), one COLUMN per band
    -- replaces the earlier single-row/grouped-bar-per-band version, per explicit request.
    2026-08-06 (later same day): bars colored by the cell's OWN significance status
    (population_cell_significance) instead of by functional-group identity -- red = Holm-
    Bonferroni significant, orange = BH-FDR significant only, gray = neither -- since rows
    already carry functional-group identity via the y-axis label, color is free to carry
    significance instead."""
    cells = build_population_panel(sess_effect, areas)
    n_bands, n_rows = len(BANDS), len(FUNC_GROUP_ORDER)
    x = np.arange(len(areas))
    fig, axes = plt.subplots(n_rows, n_bands, figsize=(2.6 * n_bands, 2.4 * n_rows), sharex=True)
    for ri, fg in enumerate(FUNC_GROUP_ORDER):
        row_vals = [cells[fg][b][0] for b in BANDS]
        ymax = np.nanmax(np.abs(np.concatenate(row_vals))) if np.any(np.isfinite(
            np.concatenate(row_vals))) else 1.0
        for ci, band_disp in enumerate(BANDS):
            band_key = band_key_from_disp(band_disp)
            ax = axes[ri, ci]
            means, sems, ns = cells[fg][band_disp]
            colors = [SIG_COLORS[sig_status.get((a, fg, band_key), "ns")] for a in areas]
            ax.bar(x, means, yerr=sems, color=colors, edgecolor="black",
                  linewidth=0.3, capsize=1.5)
            ax.axhline(0, color="black", lw=0.8)
            ax.set_ylim(-1.15 * ymax, 1.15 * ymax)
            if ri == 0:
                ax.set_title(band_disp, fontsize=8)
            if ri == n_rows - 1:
                ax.set_xticks(x); ax.set_xticklabels(areas, rotation=90, fontsize=6)
            else:
                ax.set_xticks(x); ax.set_xticklabels([])
        axes[ri, 0].set_ylabel(f"{fg}\nZ (mean +- SEM)", fontsize=8)
    fig.suptitle("Population firing rate x LFP band power (trial-matched, within-session-first) "
                "-- rows: functional type, columns: band", fontsize=11, fontweight="bold",
                y=1.02)
    fig.text(0.5, -0.005, "Bar color: cross-session hit-rate significance per (area, "
            "functional type, band) cell -- red = Holm-Bonferroni, orange = BH-FDR only, "
            "gray = neither (family: fig07_population_cell_hitrate).",
            ha="center", fontsize=7, color="0.25")
    out = os.path.join(SVG_DIR, out_stem)
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)
    return out + ".svg"


def population_stats():
    """Wrap the already-fitted GLMM (fit_population_firing_lfp_power_glmm.py) as Result rows --
    NOT a second inferential framework. This project's own doctrine is to minimize the diversity
    of tests; the GLMM is the single declared backbone (same one figure 5 uses), and this
    function only reformats its output for figstats.write()'s standard fig07_stats.md/csv."""
    main_df = pd.read_csv(os.path.join(POP_DIR, "glmm_summary.csv"))
    pw_df = pd.read_csv(os.path.join(POP_DIR, "glmm_pairwise.csv"))
    results = []
    for _, r in main_df[main_df.term != "Intercept"].iterrows():
        results.append(Result(
            figure="fig07", panel="population_main", question=f"GLMM term {r.term} != 0",
            test="MixedLM (REML) coefficient t-test", statistic_name="t",
            statistic=float(r.tstat), df="", n=int(r.n_obs), unit="session",
            effect_name="Z units", effect=float(r.estimate_z), p=float(r.p_raw),
            family="fig07_population_main",
            note=f"estimator={r.estimator}; ref levels: area=V1, band=theta, "
                 f"func_group=Other, condition_group=baseline"))
    for _, r in pw_df.iterrows():
        results.append(Result(
            figure="fig07", panel="population_pairwise",
            question=f"{r.factor} pairwise: {r.term}",
            test="MixedLM (REML) contrast t-test", statistic_name="t",
            statistic=float(r.tstat), df="", n=0, unit="session",
            effect_name="Z units", effect=float(r.estimate_z), p=float(r.p_raw),
            family="fig07_population_pairwise", note=f"factor={r.factor}"))
    return results


# ============================================================ supplement: PPC
def load_ppc():
    d = np.load(COUPLING_NPZ, allow_pickle=True)
    keys, vals = d["keys"], d["values"]
    rows = []
    for k, v in zip(keys, vals):
        session, ctx, band, area, layer, unit_row = k.split("|")
        rows.append({"session": session, "context": ctx, "band": band, "area": area,
                    "layer": layer, "unit_row": int(unit_row),
                    "obs": v[0], "null_mu": v[1], "null_sd": v[2],
                    "n_shuffle": v[3], "n_spikes": v[4]})
    return pd.DataFrame(rows)


def session_area_band_effect(df, context, band_key):
    sub = df[(df.context == context) & (df.band == band_key)].copy()
    sub["effect"] = sub.obs - sub.null_mu
    return sub.groupby(["session", "area"], as_index=False)["effect"].mean()


def identity_stats(df, areas):
    ctx_map = {"A": "identity_A", "B": "identity_B", "R": "omission"}
    stats = []
    for band_disp in BANDS:
        band_key = band_key_from_disp(band_disp)
        pooled = {ident: session_area_band_effect(df, ctx, band_key)
                 for ident, ctx in ctx_map.items()}
        for a in areas:
            groups, labels = [], []
            for ident, p in pooled.items():
                vals = p[p.area == a].effect.values
                if len(vals) >= 3:
                    groups.append(vals)
                    labels.append(ident)
            if len(groups) >= 2:
                stats.append(group_location(
                    groups, labels, figure="fig07_supp", panel="identity",
                    question=f"{band_key} {a} spike-LFP PPC differs by A/B/R identity",
                    unit="session", family="fig07_supp_identity",
                    note="identity_R reuses the omission context (RXRR); same window "
                         "(1.031-1.562s) across all three identities"))
    return stats


def build_panel_and_stats(df, context, areas):
    stats = []
    band_effects = {}
    for band_disp in BANDS:
        band_key = band_key_from_disp(band_disp)
        pooled = session_area_band_effect(df, context, band_key)
        means, sems, ns = [], [], []
        for a in areas:
            vals = pooled[pooled.area == a].effect.values
            means.append(np.mean(vals) if len(vals) else np.nan)
            sems.append(np.std(vals, ddof=1) / np.sqrt(len(vals)) if len(vals) > 1 else np.nan)
            ns.append(len(vals))
            if len(vals) >= 3:
                stats.append(paired_location(
                    vals, np.zeros_like(vals), figure="fig07_supp", panel=context,
                    question=f"{band_key} {a} {context} spike-LFP PPC vs null", unit="session",
                    family=f"fig07_supp_{context}", note=f"n={len(vals)} sessions"))
        band_effects[band_disp] = (np.array(means), np.array(sems), np.array(ns))
    return band_effects, stats


def draw_context_figure(df, context, areas, out_stem, title):
    band_effects, stats = build_panel_and_stats(df, context, areas)
    n_bands = len(BANDS)
    fig, axes = plt.subplots(1, n_bands, figsize=(2.9 * n_bands, 3.2), sharey=True)
    x = np.arange(len(areas))
    for ax, (band, (means, sems, ns)) in zip(axes, band_effects.items()):
        colors = [AREA_COLORS.get(a, "0.5") for a in areas]
        ax.bar(x, means, yerr=sems, color=colors, edgecolor="black", linewidth=0.4, capsize=2)
        ax.axhline(0, color="black", lw=0.8)
        ax.set_xticks(x); ax.set_xticklabels(areas, rotation=90, fontsize=6)
        ax.set_title(band, fontsize=8)
        for xi, n in zip(x, ns):
            if n:
                ax.text(xi, 0, str(n), fontsize=5, ha="center", va="bottom", color="0.3")
    axes[0].set_ylabel("PPC observed - shuffle null\n(mean +- SEM across sessions)", fontsize=8)
    fig.suptitle(title, fontsize=11, fontweight="bold", y=1.05)
    out = os.path.join(SVG_DIR, out_stem)
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)
    return out + ".svg", stats


def main():
    os.makedirs(SVG_DIR, exist_ok=True)
    all_stats = []

    # ---- headline: population firing x LFP band power -----------------------------
    sess_effect = load_population()
    pop_areas = [a for a in AREA_ORDER if a in set(sess_effect.area)]
    print(f"population panel areas: {pop_areas}")
    print(f"population panel sessions: {sess_effect.session.nunique()}")
    sig_status, cell_sig_results = population_cell_significance(sess_effect, pop_areas)
    n_holm_cell = sum(1 for v in sig_status.values() if v == "holm")
    n_bh_cell = sum(1 for v in sig_status.values() if v == "bh")
    print(f"population cell hit-rate significance: {n_holm_cell}/{len(sig_status)} Holm, "
         f"{n_bh_cell}/{len(sig_status)} BH-FDR only")
    pop_svg = draw_population_figure(sess_effect, pop_areas, sig_status,
                                     "fig07_population_headline")
    all_stats += population_stats()
    all_stats += cell_sig_results

    # ---- supplement: PPC ------------------------------------------------------------
    df = load_ppc()
    ppc_areas = [a for a in AREA_ORDER if a in set(df.area)]
    print(f"PPC areas present: {ppc_areas}")
    print(f"PPC sessions present: {df.session.nunique()}")
    print(f"PPC units present: {df.groupby(['session', 'area', 'unit_row']).ngroups}")

    omission_svg, stats_o = draw_context_figure(
        df, "omission", ppc_areas, "fig07_omission_ppc",
        "Supplement: spike-LFP phase coupling (PPC), omission window (RXRR, p2 omitted)")
    all_stats += stats_o
    stim_svg, stats_s = draw_context_figure(
        df, "stimulus", ppc_areas, "fig07_stimulus_ppc",
        "Supplement: spike-LFP phase coupling (PPC), stimulus window (p1, present in every "
        "condition)")
    all_stats += stats_s
    if {"identity_A", "identity_B"}.issubset(set(df.context.unique())):
        stats_id = identity_stats(df, ppc_areas)
        all_stats += stats_id
        print(f"PPC identity (A/B/R) stats: {len(stats_id)} tests")

    out, w, h = assemble([pop_svg], os.path.join(HERE, "fig07.svg"), ncol=1)
    print(f"assembled main -> {out}  {w:.1f} x {h:.1f} pt")
    supp_out, sw, sh = assemble([omission_svg, stim_svg],
                               os.path.join(HERE, "fig07_supp_ppc.svg"), ncol=1)
    print(f"assembled PPC supplement -> {supp_out}  {sw:.1f} x {sh:.1f} pt")

    write(all_stats, SVG_DIR, "fig07",
         title="Figure 7 -- population firing rate x LFP band power (headline) + PPC "
               "(supplement)",
         preamble="HEADLINE: within-session, trial-matched Pearson correlation between "
                  "population firing rate (mean per-unit rate across a functional group's "
                  "qualifying units in an area) and that area's LFP band power, against a "
                  "trial-mismatch shuffle null; pooled across sessions only after testing "
                  "(feedback_pool_after_testing_not_before). Reported through a single GLMM "
                  "backbone (MixedLM/REML, session random intercept, subject additive fixed "
                  "effect -- same convention as figure 5), fit on the per-session Z; "
                  "fig07_population_main is the vs-reference coefficients, "
                  "fig07_population_pairwise is every pairwise contrast from that one fit. "
                  "fig07_population_cell_hitrate is a SEPARATE, later-added (2026-08-06) family: "
                  "one exact-binomial hit-rate test per (area, functional type, band) cell on "
                  "the same condition-group-averaged per-session Z the headline figure plots -- "
                  "this is what colors each bar (red=Holm, orange=BH-FDR only, gray=neither), "
                  "and is NOT a re-read of outputs/population_firing_lfp_power_corr/"
                  "hit_rates.csv (that file's cells are per condition-group, a finer and "
                  "different family). See outputs/population_firing_lfp_power_corr/README.md "
                  "for the full result and extraction/aggregation provenance. SUPPLEMENT: "
                  "pairwise phase consistency "
                  "(Vinck et al. 2010) between each SUA unit's spike times and its own area's "
                  "representative-channel LFP phase, per band, same-electrode-excluded, against "
                  "a spike-count-matched random-time-resampling null. No area x band effect "
                  "survives correction in either context (0/60). Unit of inference is session "
                  "throughout.")
    print(f"stats: {len(all_stats)} tests written")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "headline_source": POP_DIR, "ppc_supplement_source": COUPLING_NPZ,
        "headline_areas": pop_areas, "headline_sessions": int(sess_effect.session.nunique()),
        "ppc_areas": ppc_areas, "ppc_sessions": int(df.session.nunique()),
        "bands": list(BANDS),
        "redesign_note": "2026-08-05: population firing-rate x LFP band-power GLMM promoted to "
                         "headline; per-unit PPC (0/60 significant after correction) demoted to "
                         "fig07_supp_ppc.svg, per user direction",
    }
    with open(os.path.join(SVG_DIR, "fig07_receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)


if __name__ == "__main__":
    main()
