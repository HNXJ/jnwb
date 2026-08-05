r"""
Figure 3: the single-unit census -- how many units answer each question, and where.

WHY THIS FIGURE EXISTS IN THIS FORM
    The asset previously staged as figure 3 was a mock-up: every count in it was a literal
    typed into scripts/generate_publication_figures.py, including a total of 8,597 units that
    matches no population in this corpus and an O+ count of 421 that is on the retraction
    list. See this directory's README. Nothing here is hardcoded; every number is read from
    the grand classification table and every proportion carries an exact interval.

WHAT IS COUNTED
    outputs/classification/omission_grand_units.csv, one row per screened unit, produced by
    scripts/classify_omission_units_grand.py. Four questions, each with its own
    Benjamini-Hochberg family across all screened units, which controls FDR and not FWER:

      Q1  does the unit peak or trough AT the omitted slot -- significant against BOTH
          flanking delays and in the same direction against both. O++/O-- additionally
          carry a within-slot ramp of the same sign.
      Q2  does it distinguish WHEN the omission fell (slot 2, 3 or 4)
      Q3  does it distinguish WHAT was omitted (A versus B)
      Q4  is the stimulus after an omission treated differently from the first stimulus

PROPORTIONS
    Clopper-Pearson exact binomial intervals throughout, never a bootstrap: the estimand is a
    proportion built from a count and a denominator, so an exact interval needs no RNG, no
    seed and no resample count to reproduce.

    Panel b normalises by units screened per area, because raw counts follow recording effort.
    PFC contributes roughly twice V1's units, so an unnormalised bar chart ranks recording
    effort. The session count behind every area is printed, because units concentrated in one
    or two sessions describe those recordings and not the population.

OUTPUT
    svg/fig03_*.{svg,png} -- panels, main and supplementary
    fig03.svg             -- the assembled main figure
    svg/fig03_receipt.json
"""
from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, r"D:/workspace/omission")
from figstyle import (AREA_COLORS, AREA_ORDER, CLASS_COLORS, CLASS_ORDER, FULL_TRIAL_WIN,
                      STIM_MS, clopper_pearson, full_trial_ticks, mark_full_trial_axis, save,
                      use_house_style)
from svgassemble import assemble
from figstats import (contingency, correlation, correlation_with_shuffle_null, group_location,
                      proportion_vs_reference, shuffle_null_distribution, trend_in_proportions,
                      write)

import jnwb as oa
from jnwb.unit_classification import EPOCH_ONSETS_MS, GLO_CONDITIONS, precompute_condition_onsets

TABLE = r"D:/workspace/omission/outputs/classification/omission_grand_units.csv"
LEGACY_TABLE = r"D:/workspace/omission/outputs/classification/grand_s_and_o_units.csv"
LAYER_TABLE = r"D:/workspace/omission/outputs/layers/unit_layers.csv"
STABLE_TABLE = r"D:/workspace/omission/outputs/classification/unit_trial_presence.csv"
NWB_DIR = r"D:/analysis/nwb"
FIG_DIR = os.path.join(HERE, "svg")

# A unit counts as "stable" if it fired >=1 spike in more than this fraction of its session's
# correct sequence trials (unit_trial_presence.csv: trial_presence_fraction, computed directly
# from spike times against the full-trial window, not an upstream drift-outlier screen -- see
# scripts/compute_unit_trial_presence.py). Among SUA units (quality == 1) this yields 2,611/
# 4,447 = 58.7% stable, consistent with the "at least half" expectation this threshold was
# chosen against.
STABLE_KEEP_THRESHOLD = 0.98
PRESENCE3_ORDER = ["stable", "unstable", "mua"]
PRESENCE3_COLORS = {"stable": "#238B45", "unstable": "#FDAE61", "mua": "0.6"}

QUESTIONS = [("q1_q", "Peaks or troughs\nat the omitted slot"),
             ("q2_q", "Distinguishes\nWHEN it was omitted"),
             ("q3_q", "Distinguishes\nWHAT was omitted"),
             ("q4_q", "Treats the stimulus after\nan omission differently")]
ALPHA = 0.025          # the FDR threshold the classifier used; read back from the receipt

# 8-way composition, in the order the user asked for. Priority when a unit qualifies for
# more than one bucket: the corrected Q1 conjunction (O-family) outranks the legacy
# correlation-to-template classifier (S-family), and within a family the double-threshold
# ("++"/"--") class outranks the single-threshold one -- each is a strictly more specific
# claim about the same unit, not an independent measurement.
CLASS8_ORDER = ["S++", "S+", "S-", "S--", "O-", "O--", "O+", "O++", "Null"]
CLASS8_COLORS = {"S++": "#00441B", "S+": "#1B9E5A", "S-": "#B5651D", "S--": "#6E3A0A",
                 "O-": CLASS_COLORS["O-"], "O--": CLASS_COLORS["O--"],
                 "O+": CLASS_COLORS["O+"], "O++": CLASS_COLORS["O++"],
                 "Null": CLASS_COLORS["ns"]}
CLASS5_ORDER = ["O+", "O-", "S+", "S-", "Null"]
CLASS5_COLORS = {"O+": CLASS_COLORS["O+"], "O-": CLASS_COLORS["O-"], "S+": "#1B9E5A",
                 "S-": "#B5651D", "Null": CLASS_COLORS["ns"]}
LAYER3_ORDER = ["sup", "deep", "Null"]
LAYER3_COLORS = {"sup": "#3182BD", "deep": "#E6550D", "Null": "0.75"}

# omission condition -> omitted slot index; the population PSTH pools every condition, same
# convention as fig02 and the grand classifier itself.
OMISSIONS = {"AXAB": 2, "AAXB": 3, "AAAX": 4, "BXBA": 2, "BBXA": 3, "BBBX": 4,
             "RXRR": 2, "RRXR": 3, "RRRX": 4}
PSTH_WIN = (-1500, 1500)
PSTH_BIN_MS = 25


def load():
    df = pd.read_csv(TABLE)
    df["area10"] = df["area10"].fillna(df["area"])
    return df


def attach_legacy(df):
    """Join the legacy S+/S- template-correlation classifier onto the grand table.

    The legacy classifier ran on 15 of the grand table's 21 sessions and, even within those
    15, wrote a row for only 2,921 of the 6,650 grand-table units there (it applies its own
    upstream trial-count/quality filter before ever scoring a unit). Session membership alone
    therefore is NOT sufficient to say a unit was screened -- a unit can sit in a "legacy"
    session and still have no legacy row. `legacy_screened` is set from the join match itself
    (is_Splus.notna()), not from session membership, so it never mistakes "never evaluated"
    for "evaluated and negative". Every panel that uses class8/class5 below restricts to it.
    """
    legacy = pd.read_csv(LEGACY_TABLE)
    legacy_sessions = set(legacy.session_prefix.unique())
    m = df.merge(legacy[["session_prefix", "unit_row_idx", "is_Splus", "is_Splus_double",
                         "is_Sminus", "is_Sminus_double"]],
                 left_on=["session", "unit_row"], right_on=["session_prefix", "unit_row_idx"],
                 how="left")
    m["legacy_screened"] = m.is_Splus.notna()
    return m, legacy_sessions, int(legacy.shape[0])


def attach_layer(df):
    """Join vFLIP putative layer onto the grand table via peak-channel row identity.

    unit_layers.csv spans 23 sessions against the grand table's 21 (21 in common); of the
    matched rows, most carry 'na' -- vFLIP processed the channel but could not assign it -- not
    a real 'mid' assignment. 'na', unmatched, and 'mid' are all folded into the Null bucket the
    user asked for; sup and deep are the only two informative classes here.
    """
    layer = pd.read_csv(LAYER_TABLE)
    m = df.merge(layer[["session_prefix", "unit_index", "unit_layer"]],
                 left_on=["session", "unit_row"], right_on=["session_prefix", "unit_index"],
                 how="left")
    m["layer3"] = np.where(m.unit_layer == "sup", "sup",
                    np.where(m.unit_layer == "deep", "deep", "Null"))
    matched = int(m.unit_layer.notna().sum())
    return m, matched, int(layer.shape[0])


def attach_stability(df):
    """Join per-unit trial presence (unit_trial_presence.csv) and derive stable/unstable/mua.

    'mua' is read from the grand table's OWN `quality` field (0 = multi-unit, 1 = the
    NWB/Kilosort curation label for a well-isolated single unit). Among quality == 1 (SUA)
    units, 'stable' vs 'unstable' comes from `trial_presence_fraction` -- literally, the
    fraction of that session's correct sequence trials (up to 960) in which the unit fired
    >=1 spike anywhere in the full-trial window -- against STABLE_KEEP_THRESHOLD (see
    scripts/compute_unit_trial_presence.py; this is a directly-computed quantity, not the
    upstream drift-outlier screen the panel used previously). A unit with no row in that table
    cannot be placed in either bucket and is excluded from the panel's denominator, not folded
    into either the numerator or the "mua" bucket.
    """
    stab = pd.read_csv(STABLE_TABLE)
    m = df.merge(stab[["session", "unit_row", "trial_presence_fraction"]],
                 on=["session", "unit_row"], how="left")
    stable_evaluable = (m.quality == 0) | m.trial_presence_fraction.notna()
    presence3 = np.where(m.quality == 0, "mua",
                 np.where(m.trial_presence_fraction > STABLE_KEEP_THRESHOLD, "stable",
                 np.where(m.trial_presence_fraction.notna(), "unstable", None)))
    m["presence3"] = presence3
    m["presence_evaluable"] = stable_evaluable
    return m, int(stab.shape[0]), int(stable_evaluable.sum())


def class8(df):
    """S++ > S+ / S-- > S- outranked by O-- > O- / O++ > O+; else Null. See attach_legacy."""
    s = np.where(df.is_Splus_double == True, "S++",                       # noqa: E712
        np.where(df.is_Splus == True, "S+",                               # noqa: E712
        np.where(df.is_Sminus_double == True, "S--",                      # noqa: E712
        np.where(df.is_Sminus == True, "S-", "Null"))))                   # noqa: E712
    return np.where(df.omission_class != "ns", df.omission_class, s)


def class5(df):
    """O+/O++ pooled to O+, O-/O-- pooled to O-, else the legacy S flag, else Null."""
    o = np.where(df.omission_class.isin(["O+", "O++"]), "O+",
        np.where(df.omission_class.isin(["O-", "O--"]), "O-", None))
    s = np.where(df.is_Splus == True, "S+",                                # noqa: E712
        np.where(df.is_Sminus == True, "S-", "Null"))                      # noqa: E712
    return np.where(o != None, o, s)                                       # noqa: E711


def _bars(ax, labels, k, n, colors, ylabel):
    """Proportions with exact binomial intervals, counts printed on each bar."""
    p = np.array([100.0 * ki / ni if ni else np.nan for ki, ni in zip(k, n)])
    lo, hi = np.array([clopper_pearson(ki, ni) for ki, ni in zip(k, n)]).T * 100.0
    x = np.arange(len(labels))
    ax.bar(x, p, color=colors, edgecolor="black", linewidth=0.6, zorder=3)
    ax.errorbar(x, p, yerr=[p - lo, hi - p], fmt="none", ecolor="black", elinewidth=0.9,
                capsize=2.5, zorder=4)
    for xi, pi, ki, ni in zip(x, p, k, n):
        ax.text(xi, hi[xi] + 0.35, f"{ki}/{ni}", ha="center", va="bottom", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, max(np.nanmax(hi) * 1.22, 1.0))
    ax.grid(axis="y", ls=":", alpha=0.5, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def panel_questions(df, alpha):
    """a | how many of the screened units answer each of the four questions."""
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    n = len(df)
    # Q1 is a conjunction: q1_p is already the weaker of the two flank tests, so q1_q <= alpha
    # means both legs cleared. It does not mean the unit peaked -- a unit can differ from both
    # flanks in opposite directions. Only the same-signed set is a peak or a trough, and that
    # is the set the classifier labels O+/O++/O-/O--. Count that, not the bare q-value.
    k = [int(df.omission_responsive.sum())] + \
        [int((df[c] <= alpha).sum()) for c, _ in QUESTIONS[1:]]
    _bars(ax, [lab for _, lab in QUESTIONS], k, [n] * len(k),
          ["#7A0177", "#C51B8A", "#2C7FB8", "#41AB5D"],
          "Units answering (% of screened)")
    ax.set_title(f"{n:,} units screened, {df.session.nunique()} sessions, "
                 f"{df.animal.nunique()} animals; BH FDR q \u2264 {alpha}", fontsize=9)
    fig.tight_layout()
    return fig, dict(zip([c for c, _ in QUESTIONS], k)), n


def panel_classes(df):
    """b | the omission response classes, with the ramp conjunction separated out."""
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    n = len(df)
    k = [int((df.omission_class == c).sum()) for c in CLASS_ORDER]
    _bars(ax, CLASS_ORDER, k, [n] * len(k), [CLASS_COLORS[c] for c in CLASS_ORDER],
          "Units in class (% of screened)")
    ax.set_title("O++ and O-- additionally require a within-slot ramp of the same sign",
                 fontsize=9)
    fig.tight_layout()
    return fig, dict(zip(CLASS_ORDER, k))


def panel_by_area(df, col="omission_responsive"):
    """c | prevalence by area, normalised by units screened in that area."""
    areas = [a for a in AREA_ORDER if (df.area10 == a).any()]
    n = [int((df.area10 == a).sum()) for a in areas]
    k = [int(((df.area10 == a) & df[col]).sum()) for a in areas]
    ses = [int(df.loc[df.area10 == a, "session"].nunique()) for a in areas]
    fig, ax = plt.subplots(figsize=(6.4, 3.1))
    _bars(ax, areas, k, n, [AREA_COLORS[a] for a in areas],
          "Omission-responsive units (% of area)")
    for xi, s in enumerate(ses):
        ax.text(xi, -ax.get_ylim()[1] * 0.09, f"{s} ses", ha="center", va="top", fontsize=7,
                color="0.35")
    ax.set_title("Normalised by units screened per area; raw counts follow recording effort",
                 fontsize=9)
    fig.tight_layout()
    return fig, dict(zip(areas, k)), dict(zip(areas, n)), dict(zip(areas, ses))


def panel_by_type(df):
    """d | narrow- against broad-spiking, split at the waveform-duration median."""
    d = df.dropna(subset=["waveform_duration"]).copy()
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    if d.empty:
        ax.text(0.5, 0.5, "waveform_duration absent from the table", ha="center",
                transform=ax.transAxes)
        fig.tight_layout()
        return fig, {}, {}, np.nan
    cut = float(d.waveform_duration.median())
    d["type"] = np.where(d.waveform_duration <= cut, "narrow", "broad")
    labs = ["narrow", "broad"]
    n = [int((d.type == t).sum()) for t in labs]
    k = [int(((d.type == t) & d.omission_responsive).sum()) for t in labs]
    _bars(ax, [f"narrow \u2264 {cut:.3g}", f"broad > {cut:.3g}"], k, n,
          ["#F16913", "#2171B5"], "Omission-responsive (% of type)")
    ax.set_title("Split at the corpus median waveform duration; units are the same "
                 "population as a", fontsize=9)
    fig.tight_layout()
    return fig, dict(zip(labs, k)), dict(zip(labs, n)), cut


def panel_area_by_question(df, alpha):
    """supplementary | every question against every area, as a prevalence heat map."""
    areas = [a for a in AREA_ORDER if (df.area10 == a).any()]
    # Row 1 uses the same-signed conjunction as panel a, not the bare q-value.
    hits = [df.omission_responsive] + [df[c] <= alpha for c, _ in QUESTIONS[1:]]
    m = np.array([[100.0 * ((df.area10 == a) & h).sum() / max((df.area10 == a).sum(), 1)
                   for a in areas] for h in hits])
    fig, ax = plt.subplots(figsize=(6.6, 2.6))
    im = ax.imshow(m, cmap="magma_r", aspect="auto", vmin=0)
    ax.set_xticks(range(len(areas)))
    ax.set_xticklabels(areas)
    ax.set_yticks(range(len(QUESTIONS)))
    ax.set_yticklabels([lab.replace("\n", " ") for _, lab in QUESTIONS], fontsize=8)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            ax.text(j, i, f"{m[i, j]:.1f}", ha="center", va="center", fontsize=7,
                    color="white" if m[i, j] > 0.6 * np.nanmax(m) else "black")
    fig.colorbar(im, ax=ax, shrink=0.85, label="% of area's units")
    fig.tight_layout()
    return fig


def _stacked_pct(ax, areas, counts_by_area, order, colors, ylabel, mark_areas=None,
                 mark_label=None, show_segment_n=False, legend_loc="bottom",
                 legend_show_total=False):
    """100%-stacked composition bars: one bar per area, one segment per class in `order`.

    `mark_areas` draws a red star above the named bars and adds `mark_label` to the legend --
    used to flag which areas contain the class a viewer would otherwise not be able to see
    (a segment can be too thin at this scale to read, e.g. 1-2 O++ units in a bar of hundreds).
    `show_segment_n` prints each segment's raw unit count centered inside it (skipped for
    segments too thin to hold readable text). `legend_show_total` appends each class's total
    unit count, pooled across every area plotted here, to its legend label -- e.g. "O++
    (n=15)" -- so the legend states the corpus-wide N behind a class alongside its colour, not
    just its per-area, per-bar share.
    """
    x = np.arange(len(areas))
    bottom = np.zeros(len(areas))
    totals = np.array([sum(counts_by_area[a].values()) for a in areas], float)
    for cls in order:
        raw = np.array([counts_by_area[a].get(cls, 0) for a in areas])
        vals = np.array([100.0 * counts_by_area[a].get(cls, 0) / t if t else 0.0
                         for a, t in zip(areas, totals)])
        label = f"{cls} (n={int(raw.sum())})" if legend_show_total else cls
        ax.bar(x, vals, bottom=bottom, color=colors[cls], edgecolor="white", linewidth=0.4,
              label=label, zorder=3)
        if show_segment_n:
            for xi, (v, n) in enumerate(zip(vals, raw)):
                if v >= 6:
                    ax.text(xi, bottom[xi] + v / 2.0, f"n={int(n)}", ha="center", va="center",
                           fontsize=6, color="black", zorder=4)
        bottom += vals
    ax.set_xticks(x)
    ax.set_xticklabels(areas, fontsize=8)
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, 118)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    for xi, t in zip(x, totals):
        ax.text(xi, 103, f"n={int(t)}", ha="center", va="bottom", fontsize=6.5, color="0.3")
    # A plain asterisk, not a unicode star glyph: Cambria (the house font) has no glyph for
    # U+2605 and matplotlib silently drops it, leaving no mark on the figure at all.
    handles, labs = ax.get_legend_handles_labels()
    if mark_areas:
        for xi, a in enumerate(areas):
            if a in mark_areas:
                ax.text(xi, 110, "*", ha="center", va="center", fontsize=14, color="red",
                       fontweight="bold", zorder=5)
        handles.append(plt.Line2D([0], [0], marker="*", color="red", lw=0, markersize=9))
        labs.append(mark_label or "marked")
    # Cap columns at 6 so a long class list (e.g. the 10-entry composition8 legend, longer
    # still once legend_show_total appends "(n=...)" to every label) wraps onto a second row
    # instead of running past the figure's right edge and getting silently clipped there.
    ncol = min(len(labs), 6)
    if legend_loc == "top":
        ax.legend(handles, labs, fontsize=6.5, ncol=ncol, loc="lower center",
                 bbox_to_anchor=(0.5, 1.10), frameon=False, columnspacing=0.9,
                 handlelength=1.1)
    else:
        ax.legend(handles, labs, fontsize=6.5, ncol=ncol, loc="upper center",
                 bbox_to_anchor=(0.5, -0.22), frameon=False, columnspacing=0.9,
                 handlelength=1.1)
    ax.grid(axis="y", ls=":", alpha=0.5, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def panel_presence_by_area(dfp):
    """presence-per-area | stable/unstable/mua composition, one 100%-stacked bar per area.

    See attach_stability() for the exact definition. Restricted to units with a resolvable
    presence3 (presence_evaluable == True). MST and FST are merged into one bar (MST+FST),
    same pooling panel B's composition8 bars use -- FST has too few units for its own bar to
    be read at this scale.
    """
    d = dfp[dfp.presence_evaluable].copy()
    d["area_m"] = d.area10.replace(AREA_MERGE_MST_FST)
    areas = [AREA_MERGE_MST_FST.get(a, a) for a in AREA_ORDER if a != "FST"]
    areas = [a for a in areas if (d.area_m == a).any()]
    counts = {a: d.loc[d.area_m == a, "presence3"].value_counts().to_dict() for a in areas}
    fig, ax = plt.subplots(figsize=(6.4, 2.75))
    _stacked_pct(ax, areas, counts, PRESENCE3_ORDER, PRESENCE3_COLORS,
                "Presence composition (% of area's units)", show_segment_n=True,
                legend_loc="top", legend_show_total=True)
    fig.tight_layout(rect=[0, 0.01, 1, 0.86])
    return fig, counts, areas


AREA_MERGE_MST_FST = {"MST": "MST+FST", "FST": "MST+FST"}


def panel_composition8_by_area(df8, screened_col="legacy_screened"):
    """functionality-per-area | S++/S+/S-/S--/O-/O+/O++/Null composition, 100%-stacked.

    Restricted to units where every bucket is resolvable: O-family is defined for all 8,592
    units; S-family only for the 2,921 with a legacy classifier row (see attach_legacy). A
    unit that is O-negative and was never legacy-screened cannot be told apart from a true
    Null, so it is excluded here rather than silently counted as one.

    MST and FST are merged into one bar (MST+FST): FST has only 11 legacy-screened units, too
    few for its own bar to be read at this scale. O++ is vanishingly rare (15 units
    corpus-wide) and its stacked segment can be a sliver too thin to see even where present --
    areas with at least one O++ unit are marked with a red star so that absence-from-view is
    never confused with true absence.
    """
    d = df8[df8[screened_col]].copy()
    c8 = class8(d)
    d["class8"] = np.where(c8 == "Null", "Other", c8)  # display label only; same bucket
    d["area_m"] = d.area10.replace(AREA_MERGE_MST_FST)
    areas = [AREA_MERGE_MST_FST.get(a, a) for a in AREA_ORDER if a != "FST"]
    areas = [a for a in areas if (d.area_m == a).any()]
    counts = {a: d.loc[d.area_m == a, "class8"].value_counts().to_dict() for a in areas}
    has_opp = [a for a in areas if counts[a].get("O++", 0) > 0]
    class8_order_disp = [c if c != "Null" else "Other" for c in CLASS8_ORDER]
    class8_colors_disp = {(c if c != "Null" else "Other"): v for c, v in CLASS8_COLORS.items()}
    fig, ax = plt.subplots(figsize=(7.0, 3.55))
    _stacked_pct(ax, areas, counts, class8_order_disp, class8_colors_disp,
                "Composition (% of legacy-screened units)", mark_areas=has_opp,
                mark_label="contains ≥ 1 O++ unit", legend_show_total=True)
    fig.tight_layout(rect=[0, 0.09, 1, 0.94])
    return fig, counts, areas


def panel_layer_by_area(dfl):
    """f | sup/deep/Null layer composition, one 100%-stacked bar per area."""
    areas = [a for a in AREA_ORDER if (dfl.area10 == a).any()]
    counts = {a: dfl.loc[dfl.area10 == a, "layer3"].value_counts().to_dict() for a in areas}
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    _stacked_pct(ax, areas, counts, LAYER3_ORDER, LAYER3_COLORS,
                "Layer composition (% of area's units)", legend_show_total=True)
    ax.set_title("Null = vFLIP 'mid', unresolved ('na'), or no unit_layers.csv match; see "
                 "the receipt for the match rate", fontsize=7.2, pad=8)
    fig.tight_layout(rect=[0, 0.02, 1, 0.98])
    return fig, counts, areas


def panel_stim_omission_correlation(df):
    """g | overall firing rate vs the omission effect, with a label-shuffle null overlaid.

    'Overall firing rate' (firing_rate, from the NWB units table) is a whole-session average,
    dominated by the stimulus- and delay-filled majority of every trial -- the omitted slot is
    a single ~530 ms window out of a ~4.6 s trial. It is NOT a stimulus-epoch-only rate: that
    would require re-deriving per-epoch rates from raw spikes for all 8,592 units, an NWB pass
    of the same cost as the grand classifier itself, which is out of scope here and is owed
    (see this directory's README).
    """
    x = df.firing_rate.values
    y = df.q1_effect_hz.values
    res = correlation_with_shuffle_null(x, y, "fig03", "g",
                                        "overall firing rate vs omission effect", "unit",
                                        "fig03_correlation", method="spearman", n_shuffle=2000,
                                        seed=0,
                                        note="descriptive: unit is the unit of inference; "
                                             "'firing rate' is a whole-session average, not a "
                                             "stimulus-epoch-only rate -- see the panel g note "
                                             "in the script docstring")
    m = np.isfinite(x) & np.isfinite(y)
    _, null_r, _ = shuffle_null_distribution(x[m], y[m], method="spearman", n_shuffle=2000,
                                             seed=0)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.0),
                                   gridspec_kw={"width_ratios": [1.5, 1]})
    ax1.scatter(x[m], y[m], s=3, alpha=0.25, color="#2C7FB8", linewidths=0, rasterized=True)
    ax1.set_xlabel("Overall firing rate (Hz)")
    ax1.set_ylabel("Omission effect: slot − flanks (Hz)")
    ax1.axhline(0, color="0.5", lw=0.7, zorder=0)
    ax1.set_title(f"Spearman rho = {res.statistic:.3f}, n = {res.n}", fontsize=9)
    for s in ("top", "right"):
        ax1.spines[s].set_visible(False)

    ax2.hist(null_r, bins=40, color="0.75", edgecolor="white", linewidth=0.3)
    ax2.axvline(res.statistic, color="#C51B8A", lw=1.6)
    ax2.set_xlabel("Shuffle-null rho (n = 2000)")
    ax2.set_ylabel("Shuffles")
    ax2.set_title(f"p (analytic) = {res.p:.2g}\np (shuffle) = {res.extra['p_shuffle']:.2g}",
                  fontsize=8)
    for s in ("top", "right"):
        ax2.spines[s].set_visible(False)
    fig.tight_layout()
    return fig, res


def _psth(st, onsets, win, bin_ms):
    if onsets.size == 0:
        edges = np.arange(win[0], win[1] + bin_ms, bin_ms)
        return np.full(edges.size - 1, np.nan)
    lo, hi = win[0] / 1000.0, win[1] / 1000.0
    edges_s = np.arange(win[0], win[1] + bin_ms, bin_ms) / 1000.0
    counts = np.stack([np.histogram(st[(st >= t + lo) & (st < t + hi)] - t, bins=edges_s)[0]
                       for t in onsets]).astype(float)
    return counts.mean(axis=0) / (bin_ms / 1000.0)


def _pooled_omission_onsets(on):
    """All omission conditions pooled, offset to the omitted slot -- the alignment panel h and
    fig02's OMISSIONS convention share."""
    onsets = []
    for cond, slot in OMISSIONS.items():
        t = on.get(cond)
        if t is None or len(t) == 0:
            continue
        onsets.append(np.asarray(t, float) + EPOCH_ONSETS_MS[f"p{slot}"] / 1000.0)
    return np.concatenate(onsets) if onsets else np.zeros(0)


def compute_population_psth(df, class_col, order, win, bin_ms, onset_fn):
    """Population PSTH per class, pooled across sessions -- the analysis behind both panel h
    (5 classes, all omission conditions pooled, omission-aligned) and the RXRR template trace
    (7 classes, RXRR only, p1-aligned, full trial).

    One NWB load per session, not per unit -- get_spike_times is cheap once a session's tables
    are cached, so this touches every requested unit directly rather than subsampling. Per
    unit: mean rate across every trial `onset_fn` selects, binned at `bin_ms`. Per class: mean
    of the per-unit traces, SEM across units.

    `onset_fn(on)` takes the session's precompute_condition_onsets() dict and returns the
    array of onset times (seconds) to align every unit's PSTH to.
    """
    edges = np.arange(win[0], win[1] + bin_ms, bin_ms)
    ctr = (edges[:-1] + edges[1:]) / 2.0
    traces = {c: [] for c in order}
    n_no_trials = 0

    for sess_id, g in df.groupby("session"):
        path = os.path.join(NWB_DIR, sess_id + "_rec.nwb")
        if not os.path.exists(path):
            path = os.path.join(NWB_DIR, sess_id + ".nwb")
        if not os.path.exists(path):
            continue
        sess = oa.read(path)
        on = precompute_condition_onsets(sess, correct_only=True)
        onsets = onset_fn(on)
        if onsets.size == 0:
            n_no_trials += len(g)
            continue
        onsets = np.sort(onsets)
        for _, row in g.iterrows():
            cls = row[class_col]
            if cls not in traces:      # e.g. 'Null' when `order` excludes it (RXRR trace)
                continue
            st = np.sort(np.asarray(sess.get_spike_times(int(row.unit_row)), float))
            traces[cls].append(_psth(st, onsets, win, bin_ms))

    mu, sem, ns = {}, {}, {}
    for c in order:
        a = np.array(traces[c]) if traces[c] else np.zeros((0, ctr.size))
        ns[c] = a.shape[0]
        if a.shape[0]:
            mu[c] = np.nanmean(a, axis=0)
            n_eff = np.sum(np.isfinite(a), axis=0)
            sem[c] = np.nanstd(a, axis=0, ddof=1) / np.sqrt(np.maximum(n_eff, 1))
        else:
            mu[c] = np.full(ctr.size, np.nan)
            sem[c] = np.full(ctr.size, np.nan)
    return ctr, mu, sem, ns, n_no_trials


def panel_group_traces(ctr, mu, sem, ns):
    """h | average firing (trace +- SEM) for O+/O-/S+/S-/Null, aligned to the omitted slot."""
    from figstyle import mark_omission_axis
    fig, ax = plt.subplots(figsize=(6.8, 3.1))
    for c in CLASS5_ORDER:
        if ns[c] == 0:
            continue
        col = CLASS5_COLORS[c]
        ax.plot(ctr, mu[c], color=col, lw=1.7, label=f"{c} (n={ns[c]})", zorder=3)
        ax.fill_between(ctr, mu[c] - sem[c], mu[c] + sem[c], color=col, alpha=0.20, lw=0,
                        zorder=2)
    mark_omission_axis(ax, PSTH_WIN, flanks=True)
    ax.set_xlabel("Time from the omitted slot (ms)", color="green")
    ax.tick_params(axis="x", colors="green")
    ax.set_ylabel("Rate (spikes/s), mean ± SEM across units")
    ax.legend(fontsize=7.5, frameon=False, ncol=5, loc="upper center",
             bbox_to_anchor=(0.5, -0.24))
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout(rect=[0.015, 0.04, 1, 1])
    return fig


# Per-area peak instantaneous firing-rate composition: for each screened unit, the maximum
# mean rate in any 1-second sliding window of its trial-averaged PSTH, maximized across all
# 12 GLO_CONDITIONS (not pooled -- a unit that only fires briefly in one condition's stimulus
# window is still credited with its true peak). Class boundaries as specified by the user.
PEAK_BIN_MS = 25
PEAK_WINDOW_MS = 1000
SPEED_ORDER = ["slow", "moderate-slow", "moderate", "moderate-fast", "fast"]
SPEED_EDGES = [0.0, 1.0, 5.0, 10.0, 25.0, np.inf]     # left-closed: [edge_i, edge_i+1)
SPEED_LABELS = {"slow": "slow (<1 Hz)", "moderate-slow": "moderate-slow (1-5 Hz)",
                "moderate": "moderate (5-10 Hz)", "moderate-fast": "moderate-fast (10-25 Hz)",
                "fast": "fast (≥25 Hz)"}
SPEED_COLORS = {"slow": "#FFFFB2", "moderate-slow": "#FECC5C", "moderate": "#FD8D3C",
                "moderate-fast": "#F03B20", "fast": "#BD0026"}


def compute_peak_rate_by_unit(df):
    """Per-unit peak instantaneous firing rate across all 12 GLO conditions.

    For each of the 12 GLO_CONDITIONS separately (not pooled), builds that unit's
    trial-averaged PSTH over the full trial window (_psth, same binning as the population
    traces above), then slides a 1-second window across it and takes the mean rate in that
    window. The unit's peak is the max of that sliding-window mean over every window in every
    condition -- so a unit whose only strong response is a brief burst in one condition (e.g.
    RXRR's omitted slot) is still credited with its true peak, not diluted by pooling across
    conditions where it fires normally or not at all.

    One NWB load per session (spike times + condition onsets), touching every unit in `df`
    directly, same session-batched pattern as compute_population_psth. Returns a Series aligned
    to df.index (NaN where the unit's session NWB is missing or has no trials in any of the 12
    conditions) and the count of units skipped for that reason.
    """
    bin_win = int(round(PEAK_WINDOW_MS / PEAK_BIN_MS))
    peak = pd.Series(np.nan, index=df.index, dtype=float)
    n_no_trials = 0

    for sess_id, g in df.groupby("session"):
        path = os.path.join(NWB_DIR, sess_id + "_rec.nwb")
        if not os.path.exists(path):
            path = os.path.join(NWB_DIR, sess_id + ".nwb")
        if not os.path.exists(path):
            continue
        sess = oa.read(path)
        on = precompute_condition_onsets(sess, correct_only=True)
        cond_onsets = {c: np.sort(np.asarray(on.get(c, []), float)) for c in GLO_CONDITIONS}
        if not any(o.size for o in cond_onsets.values()):
            n_no_trials += len(g)
            continue
        for idx, row in g.iterrows():
            st = np.sort(np.asarray(sess.get_spike_times(int(row.unit_row)), float))
            best = 0.0
            for onsets in cond_onsets.values():
                if onsets.size == 0:
                    continue
                trace = _psth(st, onsets, FULL_TRIAL_WIN, PEAK_BIN_MS)
                if trace.size < bin_win or not np.isfinite(trace).any():
                    continue
                trace = np.nan_to_num(trace, nan=0.0)
                csum = np.cumsum(np.insert(trace, 0, 0.0))
                win_mean = (csum[bin_win:] - csum[:-bin_win]) / bin_win
                if win_mean.size:
                    best = max(best, float(win_mean.max()))
            peak.loc[idx] = best
    return peak, n_no_trials


def panel_peak_rate_by_area(df, peak_col="peak_hz"):
    """peak-rate | per-area composition by peak instantaneous firing-rate class.

    Classes: slow (<1 Hz), moderate-slow (1-5 Hz), moderate (5-10 Hz), moderate-fast
    (10-25 Hz), fast (>=25 Hz) -- boundaries as specified by the user, left-closed
    (`right=False` in the pd.cut call, so a unit peaking at exactly 1.000 Hz falls in
    moderate-slow, not slow). Restricted to units with a resolvable peak (dropna), same
    population as panel c (all screened units, not the legacy-screened subset panels e/h/
    template-trace use).
    """
    d = df.dropna(subset=[peak_col]).copy()
    d["speed_class"] = pd.cut(d[peak_col], bins=SPEED_EDGES, labels=SPEED_ORDER, right=False)
    d["area_m"] = d.area10.replace(AREA_MERGE_MST_FST)
    areas = [AREA_MERGE_MST_FST.get(a, a) for a in AREA_ORDER if a != "FST"]
    areas = [a for a in areas if (d.area_m == a).any()]
    counts = {a: d.loc[d.area_m == a, "speed_class"].value_counts().to_dict() for a in areas}
    fig, ax = plt.subplots(figsize=(6.6, 2.9))
    _stacked_pct(ax, areas, counts, SPEED_ORDER, SPEED_COLORS,
                "Peak-rate composition (% of area's units)")
    # Replace the legend text with the full band description + pooled N -- computed here from
    # `counts` rather than inside _stacked_pct's generic legend_show_total, since these labels
    # need the descriptive band text, not just the short SPEED_ORDER key.
    totals = {c: sum(counts[a].get(c, 0) for a in areas) for c in SPEED_ORDER}
    handles, _ = ax.get_legend_handles_labels()
    new_labels = [f"{SPEED_LABELS[c]} (n={totals[c]})" for c in SPEED_ORDER]
    ax.legend(handles, new_labels, fontsize=6.2, ncol=len(new_labels), loc="upper center",
             bbox_to_anchor=(0.5, -0.26), frameon=False, columnspacing=0.7, handlelength=1.1)
    ax.set_title(f"Peak = max mean rate in any 1-second sliding window, any of the "
                f"{len(GLO_CONDITIONS)} GLO conditions, per unit", fontsize=8)
    fig.tight_layout(rect=[0, 0.01, 1, 0.98])
    return fig, counts, areas


# The order the user specified for the RXRR template trace -- 7 of the 8 CLASS8 buckets,
# O-- omitted (4 units corpus-wide; too few for a population trace to mean anything and it is
# not requested).
RXRR_TRACE_ORDER = ["S++", "S+", "S-", "S--", "O-", "O+", "O++"]


def _gaussian_smooth(y, sigma_bins=1.5):
    """Zero-phase Gaussian smoothing (edge-reflected) for a bin-averaged trace."""
    radius = max(1, int(round(3 * sigma_bins)))
    xk = np.arange(-radius, radius + 1)
    kernel = np.exp(-0.5 * (xk / sigma_bins) ** 2)
    kernel /= kernel.sum()
    padded = np.pad(y, radius, mode="reflect")
    return np.convolve(padded, kernel, mode="valid")


S_MERGE = {"S++": "S+", "S--": "S-"}          # trace panel only -- pools ++/- - into +/-
TRACE_ORDER_MERGED = ["S+", "S-", "O-", "O+", "O++"]
S_TRACE_ORDER = ["S+", "S-"]
O_TRACE_ORDER = ["O-", "O+", "O++"]
S_SMOOTH_SIGMA = 3.0
O_SMOOTH_SIGMA = 6.0


def _schematic_curve(t_ms, slot_centers_ms, width_ms, amp, baseline=0.5):
    """Sum of Gaussian bumps (amp > 0) or dips (amp < 0) centered on `slot_centers_ms`, added
    to a flat `baseline` and clipped to [0, 1]. Used only by the idealized schematic panel --
    never fit to or read from data."""
    y = np.full_like(t_ms, baseline, dtype=float)
    for c in slot_centers_ms:
        y = y + amp * np.exp(-0.5 * ((t_ms - c) / width_ms) ** 2)
    return np.clip(y, 0.0, 1.0)


def panel_ideal_template_schematic(ax):
    """SCHEMATIC, not data -- an idealized key for what each class label means as a shape.

    A reader unfamiliar with the classifier can look at this panel first and then read the two
    real-data panels beside it: S+/S- are defined by their response to every REAL stimulus
    presentation (bumps/dips at p1, p3, p4 -- p2 is the omitted slot in RXRR, so it carries no
    real-stimulus response), while O+/O++ are defined by a response specifically AT the omitted
    slot and nowhere else, with O++ requiring the additional within-slot ramp that makes it a
    sharper, taller idealized bump than O+. These are hand-specified Gaussian bumps/dips on a
    flat 0.5 a.u. baseline (`_schematic_curve`), not fit to or derived from any unit's spike
    train -- see the panel's own title and this docstring before citing a shape from it.
    """
    t = np.linspace(FULL_TRIAL_WIN[0], FULL_TRIAL_WIN[1], 600)
    real_stim_mid = [EPOCH_ONSETS_MS[f"p{k}"] + STIM_MS / 2.0 for k in (1, 3, 4)]  # p2 omitted
    omit_mid = [EPOCH_ONSETS_MS["p2"] + STIM_MS / 2.0]
    curves = {"S+": _schematic_curve(t, real_stim_mid, 170.0, +0.42),
              "S-": _schematic_curve(t, real_stim_mid, 170.0, -0.42),
              "O+": _schematic_curve(t, omit_mid, 170.0, +0.30),
              "O++": _schematic_curve(t, omit_mid, 100.0, +0.46)}
    ticks, labels = full_trial_ticks()
    for c in ("S+", "S-", "O+", "O++"):
        ax.plot(t, curves[c], color=CLASS8_COLORS[c], lw=1.8, label=c, zorder=3)
    ax.axhline(0.5, color=CLASS8_COLORS["Null"], lw=1.2, ls="--", zorder=2,
              label="Null (baseline)")
    mark_full_trial_axis(ax, FULL_TRIAL_WIN, omit_slot=2)
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, rotation=55, fontsize=6, ha="right")
    ax.set_ylabel("Rate (a.u.)")
    ax.set_ylim(-0.05, 1.05)
    # ncol=3 (2 rows for 5 entries), matching the other two subplots' 2-row legend height.
    # bbox_to_anchor y=-0.62, not -0.30: the rotated (55 deg) tick labels below this axis
    # extend down roughly 0.3 of the axes fraction on their own (found by rendering and
    # cropping -- -0.30 put the legend's top row directly on top of them), so the legend
    # needs to clear that band, not start where it begins.
    ax.legend(fontsize=7, frameon=False, ncol=3, loc="upper center",
             bbox_to_anchor=(0.5, -0.62), columnspacing=0.9, handlelength=1.2)
    ax.set_title("SCHEMATIC — idealized, not measured", fontsize=8, color="#B30000",
                fontweight="bold")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def panel_template_trace_rxrr(ctr, mu, sem, ns):
    """template trace | mean firing rate, full trial, RXRR only -- what the average unit of
    each class actually looks like across a whole trial. Three subplots: an idealized
    SCHEMATIC key (panel_ideal_template_schematic -- hand-specified, not data, see its own
    docstring) on the left, then S-family (S++ pooled into S+, S-- pooled into S-) in the
    middle, then O-family (O-/O+/O++) on the right with a flat dashed reference line at 0.5
    a.u. standing in for Null (not a real Null population trace -- a neutral reference the
    O-family lines are read against). `mu`/`ns` are keyed by the pooled classes (see
    TRACE_ORDER_MERGED / attach_stability call site) and only feed the two real-data subplots.

    Real-data traces only, no SEM band -- each class's mean trace is Gaussian-smoothed (sigma
    = 3 bins, ~75 ms, for S-family; 6 bins, ~150 ms, for O-family, whose small n makes it
    noisier) then min-max scaled to [0, 1] (a.u.) so that shape/timing, not absolute rate or
    bin-to-bin noise, is what's compared across classes of very different firing rates on one
    shared axis.
    """
    fig, (axS0, axL, axR) = plt.subplots(1, 3, figsize=(13.6, 3.5))
    panel_ideal_template_schematic(axS0)
    ticks, labels = full_trial_ticks()
    for ax, order, sigma in ((axL, S_TRACE_ORDER, S_SMOOTH_SIGMA),
                             (axR, O_TRACE_ORDER, O_SMOOTH_SIGMA)):
        for c in order:
            if ns[c] == 0:
                continue
            col = CLASS8_COLORS[c]
            m = _gaussian_smooth(mu[c], sigma_bins=sigma)
            span = m.max() - m.min()
            scaled = (m - m.min()) / span if span > 0 else np.zeros_like(m)
            ax.plot(ctr, scaled, color=col, lw=1.6, label=f"{c} (n={ns[c]})", zorder=3)
        if ax is axR:
            ax.axhline(0.5, color=CLASS8_COLORS["Null"], lw=1.4, ls="--", zorder=3,
                      label="Null (reference)")
        mark_full_trial_axis(ax, FULL_TRIAL_WIN, omit_slot=2)
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, rotation=55, fontsize=6, ha="right")
        # Same -0.62 clearance as the schematic subplot's legend -- see that call's comment.
        ax.legend(fontsize=7, frameon=False, ncol=2, loc="upper center",
                 bbox_to_anchor=(0.5, -0.62), columnspacing=0.9, handlelength=1.2)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axL.set_ylabel("Rate (a.u., per-class min-max)")
    axL.set_title("S-family (real data, RXRR)", fontsize=8)
    axR.set_title("O-family (real data, RXRR)", fontsize=8)
    # subplots_adjust, not tight_layout: tight_layout refused to expand the bottom margin far
    # enough for the rotated tick labels plus a legend below them (silently no-ops with a
    # UserWarning when it can't, leaving the legend positioned past the canvas edge and
    # invisible in the saved file -- found by rendering this panel standalone and checking).
    # An explicit fixed margin, sized for this panel's known content, doesn't have that
    # failure mode.
    fig.subplots_adjust(left=0.035, right=0.99, top=0.88, bottom=0.44, wspace=0.22)
    return fig


def main():
    use_house_style()
    os.makedirs(FIG_DIR, exist_ok=True)
    df = load()

    alpha = ALPHA
    rec_path = os.path.join(os.path.dirname(TABLE), "omission_grand_receipt.json")
    if os.path.exists(rec_path):
        alpha = float(json.load(open(rec_path, encoding="utf-8")).get("alpha_fdr", ALPHA))

    df["omission_responsive"] = df.omission_class != "ns"

    made = {}
    fig, q_counts, n_units = panel_questions(df, alpha)
    made["a"] = save(fig, FIG_DIR, "fig03_a_questions"); plt.close(fig)

    fig, class_counts = panel_classes(df)
    made["b"] = save(fig, FIG_DIR, "fig03_b_classes"); plt.close(fig)

    fig, area_k, area_n, area_ses = panel_by_area(df)
    made["c"] = save(fig, FIG_DIR, "fig03_c_by_area"); plt.close(fig)

    fig, type_k, type_n, cut = panel_by_type(df)
    made["d"] = save(fig, FIG_DIR, "fig03_d_by_type"); plt.close(fig)

    fig = panel_area_by_question(df, alpha)
    save(fig, FIG_DIR, "supp_fig03_area_by_question"); plt.close(fig)

    df_legacy, legacy_sessions, legacy_n = attach_legacy(df)
    fig, comp8_counts, comp8_areas = panel_composition8_by_area(df_legacy)
    made["e"] = save(fig, FIG_DIR, "fig03_e_composition8_by_area"); plt.close(fig)

    df_layer, layer_matched, layer_table_n = attach_layer(df)
    fig, layer_counts, layer_areas = panel_layer_by_area(df_layer)
    made["f"] = save(fig, FIG_DIR, "fig03_f_layer_by_area"); plt.close(fig)

    fig, corr_res = panel_stim_omission_correlation(df)
    made["g"] = save(fig, FIG_DIR, "fig03_g_stim_omission_correlation"); plt.close(fig)
    # corr_res is appended to `stats` below, once the list exists -- see "g:" comment.

    d5 = df_legacy[df_legacy.legacy_screened].copy()
    d5["class5"] = class5(d5)
    ctr, mu, sem, ns5, n_no_omission = compute_population_psth(
        d5, "class5", CLASS5_ORDER, PSTH_WIN, PSTH_BIN_MS, _pooled_omission_onsets)
    fig = panel_group_traces(ctr, mu, sem, ns5)
    made["h"] = save(fig, FIG_DIR, "fig03_h_group_traces"); plt.close(fig)

    # ---- the four panels the current main figure is built from -------------------------
    df_stab, stable_table_n, presence_n = attach_stability(df)
    fig, presence_counts, presence_areas = panel_presence_by_area(df_stab)
    made["p1"] = save(fig, FIG_DIR, "fig03_p1_presence_by_area"); plt.close(fig)

    peak_hz, n_no_peak_trials = compute_peak_rate_by_unit(df)
    df_peak = df.copy()
    df_peak["peak_hz"] = peak_hz
    fig, peak_counts, peak_areas = panel_peak_rate_by_area(df_peak)
    made["p2"] = save(fig, FIG_DIR, "fig03_p2_peak_rate_by_area"); plt.close(fig)

    d8 = df_legacy[df_legacy.legacy_screened].copy()
    d8["class8"] = class8(d8)
    d8["class8_trace"] = d8["class8"].replace(S_MERGE)
    ctr8, mu8, sem8, ns8, n_no_rxrr = compute_population_psth(
        d8, "class8_trace", TRACE_ORDER_MERGED, FULL_TRIAL_WIN, PSTH_BIN_MS,
        lambda on: np.asarray(on.get("RXRR", []), float))
    fig = panel_template_trace_rxrr(ctr8, mu8, sem8, ns8)
    made["p3"] = save(fig, FIG_DIR, "fig03_p3_template_trace_rxrr"); plt.close(fig)

    out, w, h = assemble([made["p1"], made["e"], made["p2"], made["p3"]],
                         os.path.join(HERE, "fig03.svg"), ncol=1, gap=1.0, label_inset=True)
    print(f"assembled -> {out}  {w:.1f} x {h:.1f} pt")

    stats = []
    # a: is each question answered by more units than the nominal FDR rate would produce by
    # chance alone? Reference is alpha itself -- under the null the BH procedure is expected
    # to pass about alpha of the corpus, so this asks whether the observed fraction exceeds
    # that. Descriptive: the unit of inference is the unit, not the session.
    for c, lab in QUESTIONS:
        hits = int(df.omission_responsive.sum()) if c == "q1_q" else int((df[c] <= alpha).sum())
        stats.append(proportion_vs_reference(
            hits, n_units, alpha, "fig03", "a", lab.replace("\n", " "), "unit",
            "fig03_questions",
            note="descriptive: unit is the unit of inference, not session; reference rate "
                 "is the nominal FDR threshold, not a fitted null"))

    # c: does area predict omission responsiveness -- both as an unordered association
    # (chi-square) and as a monotone trend along the hierarchy (Cochran-Armitage), which is
    # the form the visual hierarchy hypothesis actually makes.
    areas_c = list(area_k)
    table = np.array([[area_k[a], area_n[a] - area_k[a]] for a in areas_c])
    stats.append(contingency(table, "fig03", "c", "area predicts responsiveness", "unit",
                             "fig03_area", rows=areas_c, cols=["responsive", "not"],
                             note="descriptive: unit is the unit of inference; counts follow "
                                  "recording effort even though the panel is normalised"))
    ranks = [AREA_ORDER.index(a) + 1 for a in areas_c]
    stats.append(trend_in_proportions(
        [area_k[a] for a in areas_c], [area_n[a] for a in areas_c], ranks,
        "fig03", "c", "responsiveness trends with hierarchy rank", "unit", "fig03_area",
        note="descriptive: unit is the unit of inference; hierarchy position is the "
             "pre-registered ordering in figstyle.AREA_ORDER, not fitted to these data"))
    stats.append(correlation(
        ranks, [100.0 * area_k[a] / area_n[a] for a in areas_c], "fig03", "c",
        "area prevalence vs hierarchy rank", "area", "fig03_area", method="spearman",
        note=f"descriptive: {len(areas_c)} non-independent area aggregates carry almost no "
             "inferential weight on their own; read alongside the trend test above"))

    # d: narrow- versus broad-spiking units, both as a contingency on responsiveness and as a
    # location comparison on the continuous omission effect size, chosen parametric or not by
    # testing the assumption rather than by habit.
    if type_k:
        tt = np.array([[type_k[t], type_n[t] - type_k[t]] for t in type_k])
        stats.append(contingency(tt, "fig03", "d", "waveform type predicts responsiveness",
                                 "unit", "fig03_type", rows=list(type_k),
                                 cols=["responsive", "not"],
                                 note="descriptive: unit is the unit of inference"))
        d2 = df.dropna(subset=["waveform_duration"]).copy()
        d2["type"] = np.where(d2.waveform_duration <= cut, "narrow", "broad")
        stats.append(group_location(
            [d2.loc[d2.type == "narrow", "q1_effect_hz"],
             d2.loc[d2.type == "broad", "q1_effect_hz"]], ["narrow", "broad"],
            "fig03", "d", "omission effect size by spike width", "unit", "fig03_type",
            note="descriptive: unit is the unit of inference"))

    # e: does area predict the 8-way S/O composition -- an r x c omnibus over the
    # legacy-screened population only (see attach_legacy).
    class8_order_disp = [c if c != "Null" else "Other" for c in CLASS8_ORDER]
    table8 = np.array([[comp8_counts[a].get(c, 0) for c in class8_order_disp]
                       for a in comp8_areas])
    # g: was computed above (panel_stim_omission_correlation) but never reached this list until
    # 2026-07-30 -- the figure and its shuffle-null p_shuffle were drawn and shipped, but the
    # analytic/shuffle statistic never reached fig03_stats.md. Found during the inventory deep
    # review; fixed by appending it here instead of leaving it a dangling local variable.
    stats.append(corr_res)

    stats.append(contingency(table8, "fig03", "e", "area predicts S/O composition", "unit",
                             "fig03_composition", rows=comp8_areas, cols=class8_order_disp,
                             note="descriptive: unit is the unit of inference; restricted to "
                                  f"the {int(df_legacy.legacy_screened.sum())} units screened "
                                  "by both classifiers"))

    # f: does area predict the sup/deep/Null layer split.
    tablef = np.array([[layer_counts[a].get(c, 0) for c in LAYER3_ORDER] for a in layer_areas])
    stats.append(contingency(tablef, "fig03", "f", "area predicts layer composition", "unit",
                             "fig03_layer", rows=layer_areas, cols=LAYER3_ORDER,
                             note="descriptive: unit is the unit of inference; "
                                  f"{layer_matched}/{n_units} units matched a row in "
                                  "unit_layers.csv"))

    # h: an omnibus location test across the five trace groups on each unit's own q1_effect_hz
    # (the same slot-minus-flanks scalar the classifier's Q1 test uses) -- Kruskal-Wallis
    # unless all five groups pass Shapiro-Wilk and Levene, in which case one-way ANOVA.
    groups_h = [d5.loc[d5.class5 == c, "q1_effect_hz"] for c in CLASS5_ORDER if ns5[c]]
    labels_h = [c for c in CLASS5_ORDER if ns5[c]]
    if len(groups_h) >= 2:
        stats.append(group_location(
            groups_h, labels_h, "fig03", "h", "omission effect size differs across S/O/Null "
            "groups", "unit", "fig03_traces",
            note="descriptive: unit is the unit of inference; restricted to the "
                 f"{int(d5.shape[0])} legacy-screened units behind panel h"))
    # presence: does area predict the stable/unstable/mua split.
    tablep = np.array([[presence_counts[a].get(c, 0) for c in PRESENCE3_ORDER]
                       for a in presence_areas])
    stats.append(contingency(tablep, "fig03", "presence", "area predicts presence "
                             "composition", "unit", "fig03_presence", rows=presence_areas,
                             cols=PRESENCE3_ORDER,
                             note="descriptive: unit is the unit of inference; "
                                  f"{presence_n}/{n_units} units had a resolvable "
                                  "stable/unstable/mua label (see attach_stability)"))

    # peak-rate: does area predict the peak-firing-rate speed-class composition.
    tablepk = np.array([[peak_counts[a].get(c, 0) for c in SPEED_ORDER] for a in peak_areas])
    stats.append(contingency(tablepk, "fig03", "peak_rate", "area predicts peak firing-rate "
                             "composition", "unit", "fig03_peak_rate", rows=peak_areas,
                             cols=SPEED_ORDER,
                             note="descriptive: unit is the unit of inference; peak is the max "
                                  "mean rate in any 1-second sliding window of the "
                                  f"trial-averaged PSTH, maximized over all {len(GLO_CONDITIONS)} "
                                  "GLO conditions; "
                                  f"{int(df_peak.peak_hz.notna().sum())}/{n_units} units had a "
                                  "resolvable peak"))

    # RXRR template trace: an omnibus across the five pooled functional classes (S++/S--
    # merged into S+/S-) on each unit's own q1_effect_hz, restricted to RXRR trials and the
    # legacy-screened population behind the trace itself -- the same test panel h runs.
    groups_r = [d8.loc[d8.class8_trace == c, "q1_effect_hz"] for c in TRACE_ORDER_MERGED
               if ns8[c]]
    labels_r = [c for c in TRACE_ORDER_MERGED if ns8[c]]
    if len(groups_r) >= 2:
        stats.append(group_location(
            groups_r, labels_r, "fig03", "template_trace", "omission effect size differs "
            "across the five pooled RXRR functional classes", "unit", "fig03_rxrr_trace",
            note="descriptive: unit is the unit of inference; restricted to the "
                 f"{int(d8.shape[0])} legacy-screened units behind the RXRR template trace"))

    write(stats, FIG_DIR, "fig03",
         "Figure 3 -- unit census: statistics",
         preamble="Population: all units screened by classify_omission_units_grand.py "
                  f"(n = {n_units}, {df.session.nunique()} session(s), "
                  f"{df.animal.nunique()} animal(s) in the table read here). Every row in "
                  "this table is unit-level and therefore descriptive by the corpus's own "
                  "unit-of-inference rule; a session- or animal-level re-test is owed before "
                  "any of these support a population claim.")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "table": TABLE,
        "population": "all units screened by classify_omission_units_grand.py",
        "n_units": int(n_units),
        "n_sessions": int(df.session.nunique()),
        "n_animals": int(df.animal.nunique()),
        "alpha_fdr": alpha,
        "correction": "Benjamini-Hochberg across all screened units, one family per question; "
                      "controls FDR, not FWER",
        "interval": "Clopper-Pearson exact binomial, 95 percent",
        "units_answering_each_question": q_counts,
        "omission_class_counts": class_counts,
        "omission_responsive_by_area": area_k,
        "units_screened_by_area": area_n,
        "sessions_by_area": area_ses,
        "waveform_split_ms": cut,
        "omission_responsive_by_type": type_k,
        "units_by_type": type_n,
        "legacy_s_classifier": {
            "table": LEGACY_TABLE, "sessions": sorted(legacy_sessions), "n_rows": legacy_n,
            "units_screened_of_grand": int(df_legacy.legacy_screened.sum()),
            "note": "spans 15 of the grand table's 21 sessions, and within those 15 wrote a "
                    "row for only a subset of units (its own upstream trial-count/quality "
                    "filter); legacy_screened is set from the per-unit join match, not "
                    "session membership. Panels e and h are restricted to legacy-screened "
                    "units so 'Null' means screened-negative, not never-tested"},
        "class8_priority": "O-- > O++ > O- > O+ > S-- > S++ > S- > S+ > Null (each a strictly "
                           "more specific claim about the same unit)",
        "composition8_counts_by_area": comp8_counts,
        "layer_table": {"table": LAYER_TABLE, "n_rows": layer_table_n,
                        "units_matched_of_grand": layer_matched},
        "layer3_counts_by_area": layer_counts,
        "stim_omission_correlation": {
            "x": "firing_rate (whole-session average, NWB units table)",
            "y": "q1_effect_hz (omission slot minus flanking delays)",
            "method": "Spearman", "rho": corr_res.statistic, "r_squared": corr_res.effect,
            "p_analytic": corr_res.p, "p_shuffle": corr_res.extra["p_shuffle"],
            "n_shuffle": corr_res.extra["n_shuffle"], "seed": corr_res.extra["seed"],
            "caveat": "x is not a stimulus-epoch-only rate; see the panel g docstring note"},
        "group_traces": {
            "window_ms": list(PSTH_WIN), "bin_ms": PSTH_BIN_MS,
            "alignment": "onset of the omitted slot, all three positions pooled",
            "n_per_class": ns5, "n_units_no_omission_trials": n_no_omission,
            "population": "legacy-screened units only (same restriction as panel e)"},
        "presence_stability": {
            "table": STABLE_TABLE, "n_rows": stable_table_n,
            "keep_threshold": STABLE_KEEP_THRESHOLD,
            "units_evaluable_of_grand": presence_n,
            "quality_discrepancy": "grand_stable_firing_rates.csv carries its own 'quality' "
                                   "column that disagrees with the grand table's on 1,942 of "
                                   "6,650 shared units (29%); unit_layers.csv agrees with the "
                                   "grand table on every one of those, so the grand table's "
                                   "quality field is used for mua/SUA and the stable-rates "
                                   "table is used only for stable_trials_keep_fraction",
            "presence3_counts_by_area": presence_counts},
        "main_figure_panels": ["presence-per-area (stable/unstable/mua)",
                               "functionality-per-area (S++/S+/S-/S--/O-/O++/O+/O++/Null, "
                               "MST+FST merged, O++-containing areas starred)",
                               "peak-rate-per-area (slow/moderate-slow/moderate/"
                               "moderate-fast/fast, max mean rate in any 1-second sliding "
                               f"window across all {len(GLO_CONDITIONS)} GLO conditions)",
                               "template trace S+/S-/O-/O+/O++ (S++ pooled into S+, S-- "
                               "pooled into S-), RXRR only, full trial, plus an idealized "
                               "SCHEMATIC key subplot (not data)"],
        "peak_rate_by_area": {
            "method": "per unit: trial-averaged PSTH per GLO condition (25 ms bins, full "
                      "trial window), 1-second sliding-window mean rate, max over all windows "
                      f"and all {len(GLO_CONDITIONS)} conditions",
            "conditions": list(GLO_CONDITIONS), "bin_ms": PEAK_BIN_MS,
            "window_ms": PEAK_WINDOW_MS,
            "speed_class_edges_hz": {"slow": "[0, 1)", "moderate-slow": "[1, 5)",
                                     "moderate": "[5, 10)", "moderate-fast": "[10, 25)",
                                     "fast": "[25, inf)"},
            "units_evaluable_of_grand": int(df_peak.peak_hz.notna().sum()),
            "n_units_no_glo_trials": int(n_no_peak_trials),
            "speed_class_counts_by_area": peak_counts},
        "rxrr_template_trace": {
            "condition": "RXRR only", "window_ms": list(FULL_TRIAL_WIN), "bin_ms": PSTH_BIN_MS,
            "alignment": "p1 onset (t = 0), omitted slot is p2",
            "class_order": TRACE_ORDER_MERGED, "n_per_class": ns8,
            "n_units_no_rxrr_trials": n_no_rxrr,
            "population": "legacy-screened units only (same restriction as panel e)"},
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__, "matplotlib": matplotlib.__version__},
    }
    with open(os.path.join(FIG_DIR, "fig03_receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print("units:", n_units, "sessions:", df.session.nunique())
    print("classes:", class_counts)
    print("by question:", q_counts)
    print("composition8 areas:", comp8_areas)
    print("layer3 areas:", layer_areas)
    print("presence3 areas:", presence_areas, "evaluable:", presence_n, "/", n_units)
    print("peak-rate areas:", peak_areas, "evaluable:", int(df_peak.peak_hz.notna().sum()),
         "/", n_units, "no-GLO-trial units:", n_no_peak_trials)
    print("stim/omission corr: rho=%.3f p_analytic=%.3g p_shuffle=%.3g" %
         (corr_res.statistic, corr_res.p, corr_res.extra["p_shuffle"]))
    print("group trace n:", ns5, "no-omission units skipped:", n_no_omission)
    print("RXRR template trace n:", ns8, "no-RXRR units skipped:", n_no_rxrr)


if __name__ == "__main__":
    main()
