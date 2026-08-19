r"""
Figure 3 supplement: per-area composition battery.

WHY THIS FILE EXISTS
    Hamm asked (2026-08-17), after the O++ threshold/area-restriction correction landed in
    fig03.svg, for "as many barplots as we can have per area, similar to panel a" -- i.e. more
    100%-stacked-by-area composition panels, covering the classification dimensions this
    session's work (S1 unit-inclusion rework, corrected O++ template-correlation threshold)
    and the pre-existing grand table already support, laid out as one assembled supplement
    sheet rather than eight disconnected PNGs.

    This file does NOT modify fig03_unit_census.py, fig03.svg, or panel a's legacy
    composition -- it is read-only with respect to the classification pipelines it draws from,
    and imports fig03_unit_census's own helpers (attach_*, _stacked_pct, AREA_MERGE_MST_FST,
    class8, CLASS8_COLORS) rather than reimplementing them, per Conservation. Two panels here
    (S1 composition, corrected-O composition) are genuinely new views not present anywhere
    else in the repo; the rest reuse existing per-area logic already in fig03_unit_census.py
    that is computed there but never assembled into a sheet (layer, presence/stability,
    waveform type) or is reused directly from that script's own most recent run (peak-rate,
    which needs an NWB pass fig03_unit_census.py already paid for).

POPULATIONS -- stated once here, every panel says which one it uses
    grand  = outputs/classification/omission_grand_units.csv, all screened units, Q1 O+/O++/
             O-/O-- (omission_class) plus the corrected template-correlation O++/candidate
             flags attached via fig03_unit_census.attach_template_corr_oplusplus (r>=0.65,
             causally restricted to V4/TEO/FEF/PFC -- see that file's OPLUSPLUS_MIN_CORRELATION
             comment).
    s1     = outputs/classification/unit_inclusion_v1.csv (S1, this session's unit-inclusion
             rework), non-mua only (quality_tier != 'mua'), is_s_plus/is_s_minus. NOT the same
             population as grand's legacy S++/S+/S-/S-- (see fig03_unit_census.attach_legacy's
             own docstring for that population's scope) -- this is the corrected,
             fixation-baseline-bug-fixed classifier, joined onto `grand` by (session,
             unit_row) so area10 (grand's canonical, merged area label) is used throughout,
             not s1's own raw `area` column (V3/V3a/V3d unmerged).

PROVISIONAL PANEL
    "unified_provisional" applies ONE possible class-priority order (O++ > O+(non-O++) > O-- >
    O- > S+ > S- > Other) to produce a single mutually-exclusive class per unit. This priority
    order has NOT been confirmed by Hamm -- the S1/legacy retirement plan explicitly lists it
    as an open decision (S++/S-- tier fate, priority order). Labelled PROVISIONAL in its own
    title; not a replacement for panel a and not treated as settled.

OUTPUT
    svg/fig03_supp_area_composition_battery.svg (+ .png)
    svg/fig03_supp_area_composition_battery_receipt.json
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
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, REPO_ROOT)

from figstyle import AREA_ORDER, save, use_house_style
from svgassemble import assemble
from jnwb import paths as oa_paths

import fig03_unit_census as f3

FIG_DIR = os.path.join(HERE, "svg")

# ---- 1. S1 functional composition by area (non-mua) ------------------------------------

S1_ORDER = ["S+", "S-", "Other"]
S1_COLORS = {"S+": f3.CLASS8_COLORS["S+"], "S-": f3.CLASS8_COLORS["S-"],
             "Other": f3.CLASS8_COLORS["Other"]}


def load_s1_nonmua():
    s1 = pd.read_csv(oa_paths.outputs_dir("classification", "unit_inclusion_v1.csv"))
    return s1[s1["quality_tier"] != "mua"][["session", "unit_row", "is_s_plus", "is_s_minus"]]


def attach_s1(df):
    s1 = load_s1_nonmua()
    s1 = s1.rename(columns={"is_s_plus": "s1_is_s_plus", "is_s_minus": "s1_is_s_minus"})
    m = df.merge(s1, on=["session", "unit_row"], how="left")
    m["s1_screened"] = m["s1_is_s_plus"].notna()
    return m


def s1_class(df):
    return np.select(
        [df.s1_is_s_plus == True, df.s1_is_s_minus == True],   # noqa: E712
        ["S+", "S-"], default="Other")


def panel_s1_composition_by_area(df_s1):
    """S1 functional composition (S+/S-/Other), non-mua only. Corrected, fixation-bug-fixed
    classifier -- see omission/jnwb_ext/unit_inclusion.py and artifacts/.lab/handout-fig03-oplusplus-
    threshold-20260817.md's "retire legacy" section. NOT restricted to a legacy-screened
    subset the way panel a is (S1 screens every non-mua unit corpus-wide)."""
    d = df_s1[df_s1.s1_screened].copy()
    d["cls"] = s1_class(d)
    d["area_m"] = d.area10.replace(f3.AREA_MERGE_MST_FST)
    areas = [f3.AREA_MERGE_MST_FST.get(a, a) for a in AREA_ORDER if a != "FST"]
    areas = [a for a in areas if (d.area_m == a).any()]
    counts = {a: d.loc[d.area_m == a, "cls"].value_counts().to_dict() for a in areas}
    fig, ax = plt.subplots(figsize=(7.0, 7.0 * 3.0 / 4.5))
    f3._stacked_pct(ax, areas, counts, S1_ORDER, S1_COLORS,
                     "S1 composition (% of non-mua units)", legend_show_total=True)
    ax.set_title("S1 (unit_inclusion_v1.csv, this session): fixation-baseline bug fixed, "
                  "non-mua units only, no legacy-screened restriction", fontsize=7.5)
    fig.tight_layout(rect=[0, 0.07, 1, 0.94])
    return fig, counts, areas


# ---- 1b. O++ share of ALL screened units by area (not just candidates) -----------------

def panel_oplusplus_pct_of_total_by_area(df):
    """% O++ (r>=0.65, causally restricted to V4/TEO/FEF/PFC) of ALL screened units per area --
    denominator is every screened unit in that area, not the R-family candidate pool fig03.svg
    panel b uses. That framing (share of candidates) answers "of the units that even looked
    like a plausible O+ shape, how many were genuine O++"; this framing answers "of everything
    recorded in this area, how many are O++" -- a much smaller number since most units never
    clear the r>0.40 candidate prefilter at all. Same Clopper-Pearson bar primitive
    (fig03_unit_census._bars) fig03.svg's own panels a/c/d use."""
    d = df.copy()
    d["area_m"] = d.area10.replace(f3.AREA_MERGE_MST_FST)
    areas = [f3.AREA_MERGE_MST_FST.get(a, a) for a in AREA_ORDER if a != "FST"]
    areas = [a for a in areas if (d.area_m == a).any()]
    k = [int(((d.area_m == a) & d.is_oplusplus_tc).sum()) for a in areas]
    n = [int((d.area_m == a).sum()) for a in areas]
    fig, ax = plt.subplots(figsize=(7.0, 7.0 * 3.0 / 4.5))
    f3._bars(ax, areas, k, n, [f3.CLASS8_COLORS["O++"]] * len(areas),
             "O++ (% of ALL screened units in area)")
    ax.set_title(f"O++ (r>={f3.OPLUSPLUS_MIN_CORRELATION:.2f}, causally restricted to "
                  f"{'/'.join(f3.OPLUSPLUS_AREAS)}) as % of every screened unit in the area, "
                  f"not just candidates -- total {sum(k)}/{sum(n)}", fontsize=7.5)
    fig.tight_layout(rect=[0, 0.02, 1, 0.90])
    return fig, dict(zip(areas, k)), dict(zip(areas, n)), areas


# ---- 2. Corrected template-correlation O composition by area ---------------------------

O_CORR_ORDER = ["O++", "O+ (candidate, not O++)", "Other"]
O_CORR_COLORS = {"O++": f3.CLASS8_COLORS["O++"], "O+ (candidate, not O++)": f3.CLASS8_COLORS["O+"],
                  "Other": f3.CLASS8_COLORS["Other"]}


def o_corr_class(df):
    return np.select(
        [df.is_oplusplus_tc == True, df.is_tc_candidate == True],   # noqa: E712
        ["O++", "O+ (candidate, not O++)"], default="Other")


def panel_o_corrected_composition_by_area(df):
    """Corrected template-correlation O++ (r>=0.65, causally restricted to V4/TEO/FEF/PFC) and
    the remaining R-family candidate pool (r>0.40 prefilter, not O++), as % of ALL screened
    units per area (not just candidates) -- shows both how rare the candidate pool is
    corpus-wide AND how it concentrates in V4/TEO/FEF/PFC, in one panel. Complements panel b's
    share-of-candidates framing with a share-of-all-units framing."""
    d = df.copy()
    d["cls"] = o_corr_class(d)
    d["area_m"] = d.area10.replace(f3.AREA_MERGE_MST_FST)
    areas = [f3.AREA_MERGE_MST_FST.get(a, a) for a in AREA_ORDER if a != "FST"]
    areas = [a for a in areas if (d.area_m == a).any()]
    counts = {a: d.loc[d.area_m == a, "cls"].value_counts().to_dict() for a in areas}
    fig, ax = plt.subplots(figsize=(7.0, 7.0 * 3.0 / 4.5))
    f3._stacked_pct(ax, areas, counts, O_CORR_ORDER, O_CORR_COLORS,
                     "Composition (% of all screened units)", legend_show_total=True)
    ax.set_title(f"Corrected template-corr O++ (r>={f3.OPLUSPLUS_MIN_CORRELATION:.2f}, "
                  f"{'/'.join(f3.OPLUSPLUS_AREAS)} only) vs remaining candidates, all areas, "
                  "all units", fontsize=7.8)
    fig.tight_layout(rect=[0, 0.07, 1, 0.94])
    return fig, counts, areas


# ---- 3. Provisional unified 6-class composition by area --------------------------------

UNIFIED_ORDER = ["O++", "O+", "O--", "O-", "S+", "S-", "Other"]
UNIFIED_COLORS = {"O++": f3.CLASS8_COLORS["O++"], "O+": f3.CLASS8_COLORS["O+"],
                   "O--": f3.CLASS8_COLORS["O--"], "O-": f3.CLASS8_COLORS["O-"],
                   "S+": f3.CLASS8_COLORS["S+"], "S-": f3.CLASS8_COLORS["S-"],
                   "Other": f3.CLASS8_COLORS["Other"]}
UNIFIED_PRIORITY_NOTE = ("PROVISIONAL priority order (not yet confirmed by Hamm): "
                          "O++ > O+ (non-O++ candidate) > O-- > O- > S+ > S- > Other")


def unified_class(df):
    o_pp = df.is_oplusplus_tc == True                                   # noqa: E712
    o_p = (df.is_tc_candidate == True) & ~o_pp                          # noqa: E712
    o_mm = df.omission_class == "O--"
    o_m = df.omission_class == "O-"
    s_p = (df.s1_is_s_plus == True) & ~o_pp & ~o_p & ~o_mm & ~o_m       # noqa: E712
    s_m = (df.s1_is_s_minus == True) & ~o_pp & ~o_p & ~o_mm & ~o_m & ~s_p  # noqa: E712
    return np.select([o_pp, o_p, o_mm, o_m, s_p, s_m],
                      ["O++", "O+", "O--", "O-", "S+", "S-"], default="Other")


def panel_unified_provisional_by_area(df):
    """PROVISIONAL: one mutually-exclusive class per unit, O-family from the corrected
    template-corr O++ + legacy Q1 O-/O-- (O+/O++ not yet re-derived from a causally-validated
    O- pipeline -- see this session's per-neuron onset-fit finding that a rising-exponential
    model cannot characterize O-/S- suppression onsets), S-family from S1 non-mua. Units with
    no S1 row (mua, or session outside S1's corpus) fall to Other even if they have no O-class
    either -- Other here means 'not in any positive functional class among the ones checked',
    not 'screened negative on every classifier'."""
    d = df.copy()
    d["cls"] = unified_class(d)
    d["area_m"] = d.area10.replace(f3.AREA_MERGE_MST_FST)
    areas = [f3.AREA_MERGE_MST_FST.get(a, a) for a in AREA_ORDER if a != "FST"]
    areas = [a for a in areas if (d.area_m == a).any()]
    counts = {a: d.loc[d.area_m == a, "cls"].value_counts().to_dict() for a in areas}
    fig, ax = plt.subplots(figsize=(7.0, 7.0 * 3.0 / 4.5))
    f3._stacked_pct(ax, areas, counts, UNIFIED_ORDER, UNIFIED_COLORS,
                     "Composition (% of all screened units)", legend_show_total=True)
    ax.set_title("PROVISIONAL -- priority order not yet confirmed (see script docstring)",
                  fontsize=7.8, color="#C51B8A", fontweight="bold")
    fig.tight_layout(rect=[0, 0.07, 1, 0.90])
    return fig, counts, areas


# ---- 4. SUA vs MUA composition by area --------------------------------------------------

QUALITY_ORDER = ["SUA", "MUA"]
QUALITY_COLORS = {"SUA": "#238B45", "MUA": "0.6"}


def panel_quality_by_area(df):
    """SUA (quality==1, NWB/Kilosort well-isolated) vs MUA (quality==0), all screened units,
    every area -- the coarsest quality split, upstream of stable/unstable (panel below)."""
    d = df.copy()
    d["cls"] = np.where(d.quality == 1, "SUA", "MUA")
    d["area_m"] = d.area10.replace(f3.AREA_MERGE_MST_FST)
    areas = [f3.AREA_MERGE_MST_FST.get(a, a) for a in AREA_ORDER if a != "FST"]
    areas = [a for a in areas if (d.area_m == a).any()]
    counts = {a: d.loc[d.area_m == a, "cls"].value_counts().to_dict() for a in areas}
    fig, ax = plt.subplots(figsize=(7.0, 7.0 * 3.0 / 4.5))
    f3._stacked_pct(ax, areas, counts, QUALITY_ORDER, QUALITY_COLORS,
                     "Composition (% of all screened units)", legend_show_total=True)
    ax.set_title("quality field from omission_grand_units.csv (0=MUA, 1=SUA)", fontsize=7.8)
    fig.tight_layout(rect=[0, 0.07, 1, 0.94])
    return fig, counts, areas


# ---- 5. Waveform narrow/broad composition by area ----------------------------------------

WAVE_ORDER = ["narrow", "broad"]
WAVE_COLORS = {"narrow": "#F16913", "broad": "#2171B5"}


def panel_waveform_type_by_area(df):
    """Narrow- vs broad-spiking, split at the corpus-wide median waveform_duration (same cut
    panel d in the main figure uses), stacked per area rather than d's single corpus-wide bar
    pair. Units with waveform_duration missing are excluded from both the cut and the panel."""
    d = df.dropna(subset=["waveform_duration"]).copy()
    cut = float(d.waveform_duration.median())
    d["cls"] = np.where(d.waveform_duration <= cut, "narrow", "broad")
    d["area_m"] = d.area10.replace(f3.AREA_MERGE_MST_FST)
    areas = [f3.AREA_MERGE_MST_FST.get(a, a) for a in AREA_ORDER if a != "FST"]
    areas = [a for a in areas if (d.area_m == a).any()]
    counts = {a: d.loc[d.area_m == a, "cls"].value_counts().to_dict() for a in areas}
    fig, ax = plt.subplots(figsize=(7.0, 7.0 * 3.0 / 4.5))
    f3._stacked_pct(ax, areas, counts, WAVE_ORDER, WAVE_COLORS,
                     "Composition (% of units with a resolvable waveform)", legend_show_total=True)
    ax.set_title(f"Split at corpus median waveform_duration = {cut:.3g} (units missing this "
                  f"field excluded, n={int(d.shape[0])}/{int(df.shape[0])})", fontsize=7.8)
    fig.tight_layout(rect=[0, 0.07, 1, 0.94])
    return fig, counts, areas, cut


def main():
    use_house_style()
    os.makedirs(FIG_DIR, exist_ok=True)

    df = f3.load()
    df = f3.attach_template_corr_oplusplus(df)
    df_s1 = attach_s1(df)

    made = {}

    fig, s1_counts, s1_areas = panel_s1_composition_by_area(df_s1)
    made["s1"] = save(fig, FIG_DIR, "fig03_supp_s1_composition_by_area"); plt.close(fig)

    fig, opp_k, opp_n, opp_areas = panel_oplusplus_pct_of_total_by_area(df)
    made["opp_pct"] = save(fig, FIG_DIR, "fig03_supp_oplusplus_pct_of_total_by_area"); plt.close(fig)

    fig, ocorr_counts, ocorr_areas = panel_o_corrected_composition_by_area(df)
    made["ocorr"] = save(fig, FIG_DIR, "fig03_supp_o_corrected_composition_by_area"); plt.close(fig)

    fig, uni_counts, uni_areas = panel_unified_provisional_by_area(df_s1)
    made["unified"] = save(fig, FIG_DIR, "fig03_supp_unified_provisional_by_area"); plt.close(fig)

    fig, qual_counts, qual_areas = panel_quality_by_area(df)
    made["quality"] = save(fig, FIG_DIR, "fig03_supp_quality_by_area"); plt.close(fig)

    fig, wave_counts, wave_areas, wave_cut = panel_waveform_type_by_area(df)
    made["waveform"] = save(fig, FIG_DIR, "fig03_supp_waveform_type_by_area"); plt.close(fig)

    # Reused (imports fig03_unit_census's own functions, no reimplementation, no re-scan of
    # NWB where fig03_unit_census.py already paid that cost this session):
    df_layer, layer_matched, layer_table_n = f3.attach_layer(df)
    fig, layer_counts, layer_areas = f3.panel_layer_by_area(df_layer)
    made["layer"] = save(fig, FIG_DIR, "fig03_supp_layer_by_area_battery"); plt.close(fig)

    df_stab, stable_table_n, presence_n = f3.attach_stability(df)
    fig, presence_counts, presence_areas = f3.panel_presence_by_area(df_stab)
    made["presence"] = save(fig, FIG_DIR, "fig03_supp_presence_by_area_battery"); plt.close(fig)

    # Peak-rate needs an NWB pass (compute_peak_rate_by_unit); fig03_unit_census.py's own most
    # recent run already produced this exact panel from the same `df` population -- reused
    # directly rather than re-paying that NWB cost here.
    peakrate_svg = os.path.join(FIG_DIR, "fig03_supp_peak_rate_by_area.svg")
    have_peakrate = os.path.exists(peakrate_svg)
    if have_peakrate:
        made["peakrate"] = peakrate_svg

    row1 = os.path.join(FIG_DIR, "fig03_supp_battery_row1.svg")
    row2 = os.path.join(FIG_DIR, "fig03_supp_battery_row2.svg")
    row3 = os.path.join(FIG_DIR, "fig03_supp_battery_row3.svg")
    row4 = os.path.join(FIG_DIR, "fig03_supp_battery_row4.svg")
    row5 = os.path.join(FIG_DIR, "fig03_supp_battery_row5.svg")
    assemble([made["s1"], made["opp_pct"]], row1, ncol=2, letters=True, letter_offset=0)
    assemble([made["unified"], made["quality"]], row2, ncol=2, letters=True, letter_offset=2)
    assemble([made["presence"], made["waveform"]], row3, ncol=2, letters=True, letter_offset=4)
    last_row_panels = [made["layer"]] + ([made["peakrate"]] if have_peakrate else [])
    assemble(last_row_panels, row4, ncol=len(last_row_panels), letters=True, letter_offset=6)
    n_row4 = len(last_row_panels)
    assemble([made["ocorr"]], row5, ncol=1, letters=True, letter_offset=6 + n_row4)
    rows = [row1, row2, row3, row4, row5]
    out, w, h = assemble(rows, os.path.join(FIG_DIR, "fig03_supp_area_composition_battery.svg"),
                          ncol=1, gap=1.0, label_inset=True, letters=False)
    print(f"assembled -> {out}  {w:.1f} x {h:.1f} pt")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "panels": {
            "s1_composition": {"description": "S1 (unit_inclusion_v1.csv) S+/S-/Other, non-mua",
                                "counts_by_area": s1_counts},
            "oplusplus_pct_of_total": {
                "description": f"O++ (r>={f3.OPLUSPLUS_MIN_CORRELATION}, "
                                f"{f3.OPLUSPLUS_AREAS}) as % of ALL screened units per area "
                                "(not just candidates) -- Clopper-Pearson bar, requested by "
                                "Hamm directly (2026-08-17) after seeing panel b's stacked "
                                "composition made the O++ segment too thin to read",
                "k_by_area": opp_k, "n_by_area": opp_n},
            "o_corrected_composition": {
                "description": f"template-corr O++ (r>={f3.OPLUSPLUS_MIN_CORRELATION}, "
                                f"{f3.OPLUSPLUS_AREAS}) / remaining candidates / Other, all "
                                "screened units",
                "counts_by_area": ocorr_counts},
            "unified_provisional": {"description": UNIFIED_PRIORITY_NOTE,
                                     "status": "PROVISIONAL, not confirmed by Hamm",
                                     "counts_by_area": uni_counts},
            "quality": {"description": "SUA vs MUA, omission_grand_units.csv quality field",
                        "counts_by_area": qual_counts},
            "waveform_type": {"description": f"narrow/broad, corpus median cut = {wave_cut:.4g}",
                               "counts_by_area": wave_counts},
            "layer": {"description": "reused from fig03_unit_census.attach_layer/"
                                      "panel_layer_by_area", "counts_by_area": layer_counts},
            "presence": {"description": "reused from fig03_unit_census.attach_stability/"
                                         "panel_presence_by_area",
                         "counts_by_area": presence_counts},
            "peak_rate": {"description": "reused image from fig03_unit_census.py's own most "
                                          "recent run (needs an NWB pass); not recomputed here",
                          "reused": have_peakrate},
        },
    }
    with open(os.path.join(FIG_DIR, "fig03_supp_area_composition_battery_receipt.json"), "w",
              encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2, default=str)
    print("wrote receipt")


if __name__ == "__main__":
    main()
