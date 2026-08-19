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
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))  # .../context/figures/fig03_unit_census -> repo root
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, REPO_ROOT)
from figstyle import (AREA_COLORS, AREA_ORDER, CLASS_COLORS, CLASS_ORDER, FULL_TRIAL_WIN,
                      STIM_MS, clopper_pearson, full_trial_ticks, mark_full_trial_axis, save,
                      use_house_style)
from svgassemble import assemble, rasterize
from figstats import (contingency, correlation, correlation_with_shuffle_null, group_location,
                      proportion_vs_reference, shuffle_null_distribution, trend_in_proportions,
                      write)

import omission as oa
from jnwb import paths as oa_paths
from omission.jnwb_ext.unit_classification import EPOCH_ONSETS_MS, GLO_CONDITIONS, precompute_condition_onsets

# Paths were hardcoded to the pre-2026-08-08 D:/workspace/omission layout, which no longer
# exists (data volume moved to D:/nwb + D:/analysis; see jnwb/paths.py and
# artifacts/.lab/data-volume-layout-and-tfr-spec-transfer-20260808.json). Resolved via the
# canonical jnwb.paths dispatch instead of a second hardcoded drive-letter root.
TABLE = str(oa_paths.outputs_dir("classification", "omission_grand_units.csv"))
LEGACY_TABLE = str(oa_paths.outputs_dir("classification", "grand_s_and_o_units.csv"))
LAYER_TABLE = str(oa_paths.outputs_dir("layers", "unit_layers.csv"))
STABLE_TABLE = str(oa_paths.outputs_dir("classification", "unit_trial_presence.csv"))
# Template-correlation O++ (2026-08-13, direct request Hamm): scripts/archive_oneoff/
# find_all_oplus_units.py, corpus-wide candidate pool (r>0.40 prefilter + permutation
# p<=0.05, baked into grand_oplus_units.csv at write time -- see attach_template_corr_
# oplusplus). Threshold and area scope corrected 2026-08-17 (this session, superseding the
# 2026-08-13 note this comment used to carry): the precomputed grand_oplusplus_units.csv
# (build_oplusplus_census.py) baked in r>=0.60 with NO area restriction and was found to
# double-count units that qualify under both the O+ and O*+ pattern (row count, not unit
# count) -- see artifacts/.lab/bug-oplus-row-vs-unit-count-inflation-20260817.json. At
# r>=0.60 the O+ candidate pool is also 55-71% contaminated by S-/S-- (suppressed) units
# whose Pearson correlation to the O+ template survives despite no real above-baseline
# omission response, because correlation is scale/sign-invariant to the unit's own absolute
# rate -- see artifacts/.lab/bug-oplus-candidate-pool-suppressed-unit-contamination-
# 20260817.json. Raising the threshold to r>=0.65 and computing straight from the
# deduplicated candidate table (not the stale precomputed grand_oplusplus_units.csv) gives 52
# unique units in V4/TEO/FEF/PFC, matching Hamm's own domain expectation ("at least 50
# neurons, all in V4/TEO/FEF/PFC"). The V4/TEO/FEF/PFC restriction is no longer just a
# validation hint (the 2026-08-13 language) -- it was causally tested this session (RRRR-vs-
# omission-condition divergence before the 40ms causal floor, plus Hamm's own peak-after/
# gradual-decay-vs-sharp-cliff falsifier) at all three omission slots and passed only in
# these four areas; see artifacts/.lab/
# finding-oplus-area-restriction-causally-validated-20260817.json. omission_class (Q1) is
# untouched everywhere else in the repo (fig05 GLMM, fig07, fig02 exemplar picker) -- this
# correction is scoped to fig03 only.
TC_CANDIDATE_TABLE = str(oa_paths.outputs_dir("classification", "grand_oplus_units.csv"))
OPLUSPLUS_MIN_CORRELATION = 0.65
OPLUSPLUS_AREAS = ("V4", "TEO", "FEF", "PFC")
NWB_DIR = str(oa_paths.nwb_dir())
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
# "Other" = not functionally part of the S+/S-/O+ families (renamed from "Null" 2026-08-06).
CLASS8_ORDER = ["S++", "S+", "S-", "S--", "O-", "O--", "O+", "O++", "Other"]
CLASS8_COLORS = {"S++": "#00441B", "S+": "#1B9E5A", "S-": "#B5651D", "S--": "#6E3A0A",
                 "O-": CLASS_COLORS["O-"], "O--": CLASS_COLORS["O--"],
                 "O+": CLASS_COLORS["O+"], "O++": CLASS_COLORS["O++"],
                 "Other": CLASS_COLORS["ns"]}
CLASS5_ORDER = ["O+", "O-", "S+", "S-", "Other"]
CLASS5_COLORS = {"O+": CLASS_COLORS["O+"], "O-": CLASS_COLORS["O-"], "S+": "#1B9E5A",
                 "S-": "#B5651D", "Other": CLASS_COLORS["ns"]}
# Layer bucket -- a DIFFERENT "Null" (unresolved vFLIP layer assignment), not the functional
# S+/S-/O+/Other grouping above. Left as "Null" deliberately -- not part of this rename's scope.
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


def attach_template_corr_oplusplus(df):
    """Join the template-correlation O++ classifier (grand_oplus_units.csv, r>0.40 prefilter +
    perm p<0.05 already baked in at write time by find_all_oplus_units.py) onto the grand
    table, keyed on (session, unit_row) vs (session_prefix, unit_row_idx) -- same key
    convention as attach_legacy/attach_layer. A unit can appear as more than one candidate row
    (O+ pattern and O*+ pattern scored separately); dedupe to one row per unit before merging,
    since fig03 asks a per-unit yes/no question, not a per-pattern one -- this was the source
    of the row-vs-unit double-counting bug found 2026-08-17 (see the OPLUSPLUS_MIN_CORRELATION
    comment above). `is_tc_candidate` = unit cleared the r>0.40 prefilter + perm p<0.05 screen
    for either pattern (the denominator for panel B, corpus-wide, all areas). `is_oplusplus_tc`
    = unit additionally cleared mean_correlation>=OPLUSPLUS_MIN_CORRELATION (0.65) AND sits in
    OPLUSPLUS_AREAS (V4/TEO/FEF/PFC) -- both thresholds corrected 2026-08-17 from the stale
    precomputed grand_oplusplus_units.csv (r>=0.60, no area gate); see the block comment above
    for the contamination and row-count-inflation findings this replaces."""
    cand = pd.read_csv(TC_CANDIDATE_TABLE)
    cand_units = cand[["session_prefix", "unit_row_idx"]].drop_duplicates()
    cand_units["is_tc_candidate"] = True
    opp_mask = (cand["mean_correlation"] >= OPLUSPLUS_MIN_CORRELATION) & (cand["permutation_pval"] <= 0.05)
    opp_units = cand.loc[opp_mask, ["session_prefix", "unit_row_idx"]].drop_duplicates()
    opp_units["is_oplusplus_tc_corr"] = True
    m = df.merge(cand_units, left_on=["session", "unit_row"],
                right_on=["session_prefix", "unit_row_idx"], how="left")
    m = m.drop(columns=["session_prefix", "unit_row_idx"])
    m = m.merge(opp_units, left_on=["session", "unit_row"],
               right_on=["session_prefix", "unit_row_idx"], how="left")
    m = m.drop(columns=["session_prefix", "unit_row_idx"])
    m["is_tc_candidate"] = m["is_tc_candidate"].fillna(False)
    m["is_oplusplus_tc_corr"] = m["is_oplusplus_tc_corr"].fillna(False)
    # Causally-validated O++: correlation threshold AND area restriction, both required. See
    # the finding-oplus-area-restriction-causally-validated-20260817.json evidence node.
    m["is_oplusplus_tc"] = m["is_oplusplus_tc_corr"] & m["area10"].isin(OPLUSPLUS_AREAS)
    return m


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
    """O++ (ground truth) > S++ > S+ / S-- > S- outranked by O-- > O- / O+; else Other.

    O++ here is the causally-validated template-correlation definition (`is_oplusplus_tc`,
    r>=0.65, restricted to V4/TEO/FEF/PFC, 52 units corpus-wide -- Hamm, 2026-08-17: "that is
    ground truth"), not the legacy Q1 (`omission_class=="O++"`) test. The two populations are
    DISJOINT on this corpus (confirmed by direct recomputation, 2026-08-17: 0 units satisfy
    both; Q1's 12 O++ units and the 52 TC-O++ units share no member), so this is a real
    reclassification, not a relabeling of the same units. Q1's own O++/O+ split is itself
    "up-significant-vs-both-flanks" (O+) plus an additional ramp-significance requirement
    (O++) -- a Q1 unit that clears the O+ bar but is not independently TC-confirmed keeps its
    Q1-O+ standing rather than being demoted further or invented into a new bucket; only the
    O++ label itself is redefined. Requires `is_oplusplus_tc` on `df` (see
    attach_template_corr_oplusplus, which must run before this).

    "Other" (renamed from "Null" 2026-08-06) means: not functionally part of the S+/S-/O+
    families -- a screened unit that met none of the S++/S+/S-/S--/O-/O--/O+/O++ criteria.
    """
    q1 = np.where(df.omission_class == "O++", "O+", df.omission_class)
    s = np.where(df.is_Splus_double == True, "S++",                       # noqa: E712
        np.where(df.is_Splus == True, "S+",                               # noqa: E712
        np.where(df.is_Sminus_double == True, "S--",                      # noqa: E712
        np.where(df.is_Sminus == True, "S-", "Other"))))                  # noqa: E712
    base = np.where(q1 != "ns", q1, s)
    return np.where(df.is_oplusplus_tc == True, "O++", base)              # noqa: E712


def class5(df):
    """O+/O++ pooled to O+, O-/O-- pooled to O-, else the legacy S flag, else Other (not
    functionally part of S+/S-/O+; renamed from "Null" 2026-08-06)."""
    o = np.where(df.omission_class.isin(["O+", "O++"]), "O+",
        np.where(df.omission_class.isin(["O-", "O--"]), "O-", None))
    s = np.where(df.is_Splus == True, "S+",                                # noqa: E712
        np.where(df.is_Sminus == True, "S-", "Other"))                     # noqa: E712
    return np.where(o != None, o, s)                                       # noqa: E711


UMAP_CLASS_ORDER = ["S++", "S+", "S-", "S--", "O+", "O++", "Other"]


def class_umap(df):
    """S++/S+/S-/S--/O+/O++/Other -- the bucket split used only by the embedding panel
    (2026-08-06). O++ is kept as its OWN trace bucket (not merged into O+) specifically so the
    panel can mark those units individually (red stars, same convention as
    panel_composition8_by_area's "contains >=1 O++ unit" flag) while still coloring/grouping
    them with O+ visually, since O++ is a strictly more specific claim about an O+ unit, not a
    separate population. O-/O-- units are EXCLUDED from this panel (not part of the requested
    buckets) rather than folded into Other, since lumping a real suppressive omission response
    in with "not functionally part of S+/S-/O+" would misrepresent it."""
    c8 = class8(df)
    return np.where(np.isin(c8, ["O-", "O--"]), None, c8)


CI_BAND_HALFGAP = 0.22   # point-estimate bar and CI band bar sit side by side, not overlaid
BAR_PAIR_WIDTH = 0.40
CI_BAND_ALPHA = 0.55
POINT_BAR_WIDTH = BAR_PAIR_WIDTH
CI_BAND_WIDTH = BAR_PAIR_WIDTH


def _bars(ax, labels, k, n, colors, ylabel):
    """Proportions with exact binomial intervals, counts printed on each bar.

    Point-estimate bar and CI-range bar sit side by side (not overlaid) at each x position
    (2026-08-17, Hamm: "put two bars instead of errorbars wide", then "put the bars next to
    eachother ; to show that more O++ per function are in some areas") -- makes an area's CI
    width directly comparable to its neighbor's without the bars occluding each other. Used
    everywhere a per-area/per-class proportion is drawn: fig03.svg panels a/c/d and the
    area-composition-battery supplement's panel b, so every proportion-bar panel in the figure
    family reads the same way.
    """
    p = np.array([100.0 * ki / ni if ni else np.nan for ki, ni in zip(k, n)])
    lo, hi = np.array([clopper_pearson(ki, ni) for ki, ni in zip(k, n)]).T * 100.0
    x = np.arange(len(labels))
    x_point = x - CI_BAND_HALFGAP
    x_band = x + CI_BAND_HALFGAP
    ax.bar(x_point, p, width=POINT_BAR_WIDTH, color=colors, edgecolor="black", linewidth=0.6,
           zorder=3)
    ax.bar(x_band, hi - lo, bottom=lo, width=CI_BAND_WIDTH, color=colors, alpha=CI_BAND_ALPHA,
           edgecolor="black", linewidth=0.4, zorder=3)
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
                 legend_show_total=False, legend_bbox_y=-0.22):
    """100%-stacked composition bars: one bar per area, one segment per class in `order`.

    `mark_areas` draws a red star above the named bars and adds `mark_label` to the legend --
    used to flag which areas contain the class a viewer would otherwise not be able to see
    (a segment can be too thin at this scale to read, e.g. 1-2 O++ units in a bar of hundreds).
    `show_segment_n` prints each segment's raw unit count centered inside it (skipped for
    segments too thin to hold readable text). `legend_show_total` appends each class's total
    unit count, pooled across every area plotted here, to its legend label -- e.g. "O++
    (n=15)" -- so the legend states the corpus-wide N behind a class alongside its colour, not
    just its per-area, per-bar share. `legend_bbox_y` (legend_loc="bottom" only) is the
    below-axis y-offset (axes fraction) the legend's top anchors to -- default -0.22 fits every
    existing caller; panel_composition8_by_area passes a shallower offset because its own
    figsize was independently made taller than the other three callers', which stretches this
    same fractional offset into much more absolute canvas than the legend needs (2026-08-18).
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
                 bbox_to_anchor=(0.5, legend_bbox_y), frameon=False, columnspacing=0.9,
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

    Restricted to units where every bucket is resolvable: O-family is defined for every row of
    the grand table (TABLE, 22-session corpus); S-family only for the subset with a legacy
    classifier row (see attach_legacy). A unit that is O-negative and was never legacy-screened
    cannot be told apart from a true Null, so it is excluded here rather than silently counted
    as one. Both population sizes are read live off df8/screened_col, never hardcoded here --
    see the printed `n=` above each bar for the exact per-area count.

    MST and FST are merged into one bar (MST+FST): FST has too few legacy-screened units for its
    own bar to be read at this scale.

    O++ here is class8()'s ground-truth definition (template-correlation, r>=0.65, restricted to
    V4/TEO/FEF/PFC, 52 units corpus-wide -- Hamm, 2026-08-17), same population panel B plots,
    intersected with this panel's own legacy-screened restriction (48 of the 52 fall inside it;
    4 sit in the 7 sessions the legacy classifier never ran on and so cannot appear here).
    Because the 52-unit population and the legacy-screened S-family population are independent
    restrictions (session coverage, not a shared filter), a unit is O++ here regardless of what
    its Q1 omission_class or S-flags say -- see class8()'s own docstring for the exact priority
    rule. O++'s stacked segment can still be a sliver too thin to see even where present -- areas
    with at least one O++ unit are marked with a red star so that absence-from-view is never
    confused with true absence.
    """
    d = df8[df8[screened_col]].copy()
    d["class8"] = class8(d)
    d["area_m"] = d.area10.replace(AREA_MERGE_MST_FST)
    areas = [AREA_MERGE_MST_FST.get(a, a) for a in AREA_ORDER if a != "FST"]
    areas = [a for a in areas if (d.area_m == a).any()]
    counts = {a: d.loc[d.area_m == a, "class8"].value_counts().to_dict() for a in areas}
    has_opp = [a for a in areas if counts[a].get("O++", 0) > 0]
    # figsize height was matched to panel b's aspect ratio (4.5x3.0 -> h/w=0.6667) 2026-08-13,
    # which equalizes the two SVGs' own canvas heights under assemble()'s shared-column-width
    # row1 layout -- but panel b's tight_layout() fills its canvas edge to edge, while this
    # panel reserves a fixed-fraction bottom margin (rect) plus a below-axis legend offset for
    # its 2-row, 10-entry legend, which left real, visible blank canvas beneath it once the
    # legend grew to include O++'s ground-truth-count relabelling. 2026-08-18, Hamm: taller by
    # ~20% -- rect and legend_bbox_y both tightened in the same step so the added height goes
    # to the plot, not to a bigger version of the same blank strip (tuned empirically against a
    # standalone render of this exact legend/axes combination, since the old rect=[0,0.09,1,0.94]
    # / bbox_y=-0.22 pairing was already imperfect at the old, smaller figsize and would only
    # have left more absolute blank space at this one, unscaled). Was (7.0, 4.6667).
    fig, ax = plt.subplots(figsize=(7.0, 7.0 * 3.0 / 4.5 * 1.2))
    _stacked_pct(ax, areas, counts, CLASS8_ORDER, CLASS8_COLORS,
                "Composition (% of legacy-screened units)", mark_areas=has_opp,
                mark_label="contains ≥ 1 O++ unit", legend_show_total=True,
                legend_bbox_y=-0.11)
    fig.tight_layout(rect=[0, 0.005, 1, 0.985])
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


def _psth(st, onsets, win, bin_ms, return_trials=False):
    """return_trials=True additionally returns the (n_trials, n_bins) per-trial rate matrix,
    for callers that need trial-level values rather than only the unit's trial-averaged trace
    (see panel E/F's trial-pooled SEM, panel_grand_average_by_condition)."""
    edges = np.arange(win[0], win[1] + bin_ms, bin_ms)
    if onsets.size == 0:
        empty_mean = np.full(edges.size - 1, np.nan)
        return (np.zeros((0, edges.size - 1)), empty_mean) if return_trials else empty_mean
    lo, hi = win[0] / 1000.0, win[1] / 1000.0
    edges_s = edges / 1000.0
    counts = np.stack([np.histogram(st[(st >= t + lo) & (st < t + hi)] - t, bins=edges_s)[0]
                       for t in onsets]).astype(float)
    rates = counts / (bin_ms / 1000.0)
    mean_rate = rates.mean(axis=0)
    return (rates, mean_rate) if return_trials else mean_rate


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
    # per-unit traces, kept for panels that need the individual vectors (e.g. the embedding
    # panel below) rather than only the class mean/SEM -- same extraction, no extra NWB access.
    unit_traces = {c: (np.array(traces[c]) if traces[c] else np.zeros((0, ctr.size)))
                  for c in order}
    return ctr, mu, sem, ns, n_no_trials, unit_traces


# 2026-08-06: fig03 redesign, panels C-F. Same per-unit PSTH primitive as compute_population_psth,
# but computes MULTIPLE real conditions (RRRR/RXRR/RRXR/RRRX) in a single session/spike-time pass
# instead of one compute_population_psth call per condition -- avoids re-reading every unit's
# spike times 4 times over.
def compute_population_psth_multi_condition(df, class_col, order, win, bin_ms, condition_names,
                                             trial_pooled_classes=frozenset()):
    """Per (class, condition) mean +- SEM trace, full trial window, p1-aligned. One NWB load and
    one get_spike_times call per unit per session, reused across all `condition_names`.

    `trial_pooled_classes` -- classes for which the SEM band pools every trial from every unit
    as a flat replicate (std over the concatenated (n_trials_total, n_bins) matrix, /sqrt(n_eff)
    per bin) instead of the default std-across-per-unit-means/sqrt(n_units). Requested
    explicitly for panels E/F (O+, O++) on 2026-08-13: labelled DESCRIPTIVE, not a substitute
    unit-level uncertainty estimate -- trials within a unit are not independent replicates of
    the population effect, so this band is tighter than the unit-level one and answers a
    different question (residual trial-to-trial spread pooled across a small, nearly-fixed
    unit set), most consequential for O++ where only 3 units carry the whole population term.
    `mu` is unaffected -- always the mean of per-unit means, for every class.

    Returns (out, unit_traces, n_no_trials). out = {condition: (ctr, mu, sem, ns, n_trials,
    sem_kind)} -- ns is always the unit count; n_trials is the pooled trial count for
    trial_pooled_classes (None otherwise); sem_kind is "trial_pooled" or "unit" per class, so
    the panel function can label the band correctly. unit_traces = {condition: {class:
    matrix[n_units, n_bins]}} -- the raw per-unit mean trace matrix `mu` and `sem` were reduced
    from (2026-08-18, added for panel_grand_average_matched_n's bootstrap resampling, which
    needs the individual unit rows, not just their mean/SEM).
    """
    edges = np.arange(win[0], win[1] + bin_ms, bin_ms)
    ctr = (edges[:-1] + edges[1:]) / 2.0
    traces = {cond: {c: [] for c in order} for cond in condition_names}
    trial_traces = {cond: {c: [] for c in order} for cond in condition_names}
    n_no_trials = 0

    for sess_id, g in df.groupby("session"):
        path = os.path.join(NWB_DIR, sess_id + "_rec.nwb")
        if not os.path.exists(path):
            path = os.path.join(NWB_DIR, sess_id + ".nwb")
        if not os.path.exists(path):
            continue
        sess = oa.read(path)
        on = precompute_condition_onsets(sess, correct_only=True)
        cond_onsets = {cond: np.sort(np.asarray(on.get(cond, []), float)) for cond in condition_names}
        if not any(o.size for o in cond_onsets.values()):
            n_no_trials += len(g)
            continue
        for _, row in g.iterrows():
            cls = row[class_col]
            if cls not in order:
                continue
            st = np.sort(np.asarray(sess.get_spike_times(int(row.unit_row)), float))
            for cond in condition_names:
                onsets = cond_onsets[cond]
                if onsets.size == 0:
                    continue
                if cls in trial_pooled_classes:
                    trials, unit_mean = _psth(st, onsets, win, bin_ms, return_trials=True)
                    trial_traces[cond][cls].append(trials)
                    traces[cond][cls].append(unit_mean)
                else:
                    traces[cond][cls].append(_psth(st, onsets, win, bin_ms))

    out, unit_traces_out = {}, {}
    for cond in condition_names:
        mu, sem, ns, n_trials, sem_kind = {}, {}, {}, {}, {}
        unit_traces_out[cond] = {}
        for c in order:
            a = np.array(traces[cond][c]) if traces[cond][c] else np.zeros((0, ctr.size))
            unit_traces_out[cond][c] = a
            ns[c] = a.shape[0]
            n_trials[c] = None
            if a.shape[0]:
                mu[c] = np.nanmean(a, axis=0)
            else:
                mu[c] = np.full(ctr.size, np.nan)
            if c in trial_pooled_classes and trial_traces[cond][c]:
                pooled = np.concatenate(trial_traces[cond][c], axis=0)
                n_eff = np.sum(np.isfinite(pooled), axis=0)
                sem[c] = np.nanstd(pooled, axis=0, ddof=1) / np.sqrt(np.maximum(n_eff, 1))
                n_trials[c] = int(pooled.shape[0])
                sem_kind[c] = "trial_pooled"
            elif a.shape[0]:
                n_eff = np.sum(np.isfinite(a), axis=0)
                sem[c] = np.nanstd(a, axis=0, ddof=1) / np.sqrt(np.maximum(n_eff, 1))
                sem_kind[c] = "unit"
            else:
                sem[c] = np.full(ctr.size, np.nan)
                sem_kind[c] = "unit"
        out[cond] = (ctr, mu, sem, ns, n_trials, sem_kind)
    return out, unit_traces_out, n_no_trials


GRAND_AVG_CONDITIONS = ["RRRR", "RXRR", "RRXR", "RRRX"]
GRAND_AVG_CONDITION_COLORS = {"RRRR": "#252525", "RXRR": "#D7191C", "RRXR": "#2C7BB6",
                              "RRRX": "#33A02C"}
GRAND_AVG_CONDITION_OMIT_SLOT = {"RRRR": None, "RXRR": 2, "RRXR": 3, "RRRX": 4}


def panel_grand_average_by_condition(cond_data, cls, title, color, smooth_sigma=None,
                                     log_y=False):
    """C/D/E/F | one functional class, grand average +- SEM firing rate, full trial, p1-aligned,
    RRRR/RXRR/RRXR/RRRX overlaid on one axis -- the no-omission baseline plus the three slot
    positions an omission can fall at. Same visual grammar the earlier excited/inhibited/
    correlated-by-slot figure used (line + shaded SEM ribbon, per-condition color, omission-slot
    aware), generalized to functional class instead of response-sign category.

    2026-08-06: both the mean AND the SEM band are Gaussian-smoothed (same `_gaussian_smooth`
    used by the old template-trace panel) when `smooth_sigma` is given -- reduces bin-to-bin
    noise so the underlying shape is easier to read; does not change what the shape actually is.

    2026-08-13: if `cond_data`'s `sem_kind` marks `cls` "trial_pooled" (panels E/F, O+/O++, see
    compute_population_psth_multi_condition), the legend shows the pooled trial count instead
    of the unit count, and the y-axis label says so explicitly -- this band pools every trial
    from every unit as a flat replicate and is DESCRIPTIVE, not the unit-level uncertainty
    estimate panels C/D show. Do not read it as "more units", especially for O++ (n=3 units).

    `log_y=True` (panel F only, requested against a reference image of a similarly-styled log-
    scale rate plot) uses a log y-axis; the SEM lower band is floored at a small positive value
    before plotting since log(<=0) is undefined -- the floor is visual only, does not change m
    or the upper band, and is noted directly on the axis.
    """
    fig, ax = plt.subplots(figsize=(4.5, 3.0))
    mark_full_trial_axis(ax, FULL_TRIAL_WIN)
    is_trial_pooled = False
    for cond in GRAND_AVG_CONDITIONS:
        ctr, mu, sem, ns, n_trials, sem_kind = cond_data[cond]
        if cls not in ns or ns[cls] == 0:
            continue
        c = GRAND_AVG_CONDITION_COLORS[cond]
        slot = GRAND_AVG_CONDITION_OMIT_SLOT[cond]
        if sem_kind.get(cls) == "trial_pooled":
            is_trial_pooled = True
            label = (f"{cond} (units={ns[cls]}, trials={n_trials[cls]})"
                    + (f", omit p{slot}" if slot else ""))
        else:
            label = f"{cond} (n={ns[cls]})" + (f", omit p{slot}" if slot else "")
        m, s = mu[cls], sem[cls]
        if smooth_sigma:
            m = _gaussian_smooth(m, sigma_bins=smooth_sigma)
            s = _gaussian_smooth(s, sigma_bins=smooth_sigma)
        ax.plot(ctr, m, color=c, lw=1.5, label=label, zorder=3)
        lo_band = np.maximum(m - s, 1e-3) if log_y else m - s
        ax.fill_between(ctr, lo_band, m + s, color=c, alpha=0.20, lw=0, zorder=2)
    ticks, labels = full_trial_ticks()
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, rotation=55, fontsize=6, ha="right")
    if log_y:
        ax.set_yscale("log")
    ylabel_suffix = " (log scale)" if log_y else ""
    if is_trial_pooled:
        # 3 short lines at a smaller size (was 2 lines at fontsize=7) -- rotated 90 deg, a
        # y-label's *line length* is constrained by the axes HEIGHT the same way a title's
        # length is constrained by figure WIDTH; the 2-line version's first line ran to ~67
        # chars, longer than this panel's ~3in-tall canvas could hold at fontsize=7 and
        # rendered visibly clipped at the top edge of the panel's own PNG (2026-08-18, found
        # while double-checking panels C-F -- same overflow failure mode as panel B's title,
        # just rotated).
        ax.set_ylabel(f"Rate (spikes/s){ylabel_suffix}, mean ± SEM\n(pooled across trials and "
                      "units,\ndescriptive -- not a unit-level uncertainty estimate)",
                      fontsize=6)
    else:
        ax.set_ylabel(f"Rate (spikes/s){ylabel_suffix}, mean ± SEM", fontsize=8)
    ax.set_title(title, fontsize=9, fontweight="bold", color=color)
    ax.legend(fontsize=6.5, frameon=False, loc="upper left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    return fig


def panel_grand_average_matched_n(class_specs, n_match, n_boot=1000, seed=0):
    """Supp | matched-N bootstrap sensitivity: every class's grand average recomputed by
    resampling `n_match` units WITH replacement, `n_boot` times, from that class's own
    per-unit trace pool, so every class is compared at the same nominal N regardless of how
    many units it actually has.

    2026-08-18, Hamm: panels C-F's full-N bands (panel_grand_average_by_condition) show real,
    honest differences in width driven by real N differences (e.g. S+ n=861 units vs O++ n=52)
    -- that is correct and stays the primary result, not something to paper over. This is an
    explicit, separately-labelled SENSITIVITY comparison, answering "if every class had the
    same N, would the shapes still look this different" -- not a replacement for panels C-F,
    and not a claim that the classes actually have matched precision (they don't). Standard
    percentile bootstrap (95% CI from the 2.5/97.5 percentiles of the bootstrap-mean
    distribution), local `np.random.default_rng(seed)`, no global RNG mutation (see
    omission-statistics skill). `n_match` should be the smallest class's own unit count (52,
    O++) so every class is subsampled down, never padded up past what it actually has.

    class_specs: {label: (unit_traces_by_cond, color)} where unit_traces_by_cond is
    compute_population_psth_multi_condition's own per-condition {cond: (ctr, mu, sem, ns,
    n_trials, sem_kind)} tuple's matching unit_traces[cond][cls] entry, one per class already
    plotted in panels C-F, i.e. {cond: matrix[n_units, n_bins]} -- ctr (the time-bin centers)
    is read from the shared FULL_TRIAL_WIN/PSTH_BIN_MS grid used everywhere else in this file.
    """
    edges = np.arange(FULL_TRIAL_WIN[0], FULL_TRIAL_WIN[1] + PSTH_BIN_MS, PSTH_BIN_MS)
    ctr = (edges[:-1] + edges[1:]) / 2.0
    rng = np.random.default_rng(seed)
    fig, axes = plt.subplots(2, 2, figsize=(9.0, 7.2))
    for ax, (label, (unit_traces_by_cond, color)) in zip(axes.flat, class_specs.items()):
        for cond in GRAND_AVG_CONDITIONS:
            mat = unit_traces_by_cond[cond]
            n_units = mat.shape[0]
            if n_units == 0:
                continue
            boot_means = np.empty((n_boot, mat.shape[1]))
            for b in range(n_boot):
                idx = rng.integers(0, n_units, size=n_match)
                boot_means[b] = np.nanmean(mat[idx], axis=0)
            m = boot_means.mean(axis=0)
            lo, hi = np.percentile(boot_means, [2.5, 97.5], axis=0)
            c = GRAND_AVG_CONDITION_COLORS[cond]
            slot = GRAND_AVG_CONDITION_OMIT_SLOT[cond]
            lbl = cond + (f", omit p{slot}" if slot else "")
            ax.plot(ctr, m, color=c, lw=1.3, label=lbl, zorder=3)
            ax.fill_between(ctr, lo, hi, color=c, alpha=0.20, lw=0, zorder=2)
        ticks, labels = full_trial_ticks()
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, rotation=55, fontsize=5.5, ha="right")
        real_n = unit_traces_by_cond["RRRR"].shape[0]
        ax.set_ylabel("Rate (spikes/s), bootstrap mean, 95% CI", fontsize=7)
        ax.set_title(f"{label} (real n={real_n}, matched N={n_match}, B={n_boot})",
                     fontsize=7.5, fontweight="bold", color=color)
        ax.legend(fontsize=5.5, frameon=False, loc="upper left")
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    fig.suptitle(f"Matched-N bootstrap sensitivity (every class resampled to N={n_match},\n"
                f"O++'s own real count) -- compares band SHAPE at equal nominal precision; "
                f"panels C-F's real,\nunequal N is the primary result, not this",
                fontsize=7.5, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    return fig


def panel_composition_oplusplus_by_area(df, areas):
    """B | distribution of the 52 ground-truth O++ units across areas -- 2026-08-13, switched
    from the Q1 peak+ramp omission_class definition to scripts/archive_oneoff/
    find_all_oplus_units.py (direct request, Hamm: the Q1-based O++ grand-average trace did
    not resemble the manually-observed FEF/PFC O++ template, so the classifier itself was
    suspect, not just the plotting). `is_oplusplus_tc`: mean_correlation>=
    OPLUSPLUS_MIN_CORRELATION (0.65) & permutation_pval<=0.05 against the RXRR/RRXR/RRRX O+ or
    O*+ template, AND area in OPLUSPLUS_AREAS (V4/TEO/FEF/PFC) -- both corrected 2026-08-17,
    see the OPLUSPLUS_MIN_CORRELATION comment near the top of this file.

    2026-08-18, Hamm: the previous version plotted each area's O++ share OF ITS OWN R-family
    candidate pool (k/n, a per-area enrichment rate, denominator varying area to area) with a
    floating lo-hi CI bar Hamm called "weird". This version plots each area's share of the
    corpus-wide 52-unit O++ total instead (k/total_k, a fixed denominator across every bar --
    a distribution over areas that sums to 100%, not a set of independent rates), and both the
    point-estimate and CI bars are grounded at 0 (no floating bar) -- the CI's lower bound is
    now a tick mark on the second bar rather than its own bottom, so no information is dropped,
    just re-anchored. `is_tc_candidate` (the R-family candidate pool size, `n`) is kept only
    for the title's existing total_n provenance line, not as a plotted denominator.

    Takes the FULL grand table (`df`, all units, every session) joined via
    attach_template_corr_oplusplus, NOT panel a's legacy-screened subset -- the template-corr
    classifier does not depend on the legacy S+/S- classifier at all.

    omission_class (Q1) is UNCHANGED and still used by panel a's 8-class composition and
    everywhere else in the repo (fig05 GLMM, fig07, fig02) -- this switch is scoped to this
    panel only, per Hamm's explicit direction to not touch omission_class corpus-wide yet.
    """
    d = df.copy()
    d["area_m"] = d.area10.replace(AREA_MERGE_MST_FST)
    k = np.array([((d.area_m == a) & d.is_oplusplus_tc).sum() for a in areas])
    n = np.array([((d.area_m == a) & d.is_tc_candidate).sum() for a in areas])
    total_k, total_n = int(k.sum()), int(n.sum())
    pct = 100.0 * k / total_k
    lo, hi = np.array([clopper_pearson(ki, total_k) for ki in k]).T * 100.0
    # figsize height kept at h/w=0.8 to match panel a's own aspect ratio (2026-08-18, panel a
    # grew ~20% taller to fix its own whitespace problem -- see panel_composition8_by_area's
    # docstring) -- was (4.5, 3.0), h/w=0.6667, until panel a's height changed out from under it.
    fig, ax = plt.subplots(figsize=(4.5, 3.6))
    x = np.arange(len(areas))
    x_point, x_band = x - CI_BAND_HALFGAP, x + CI_BAND_HALFGAP
    # Point-estimate bar and CI bar side by side, both grounded at 0 (2026-08-18, Hamm: the
    # earlier lo-to-hi floating CI bar read as "weird") -- the lower CI bound is drawn as a
    # tick across the CI bar instead of being its bottom, so it stays visible without floating
    # the bar itself. Kept in sync manually since this panel builds its own bar rather than
    # calling _bars (different fixed single-color scheme, and _bars' own CI bar still floats
    # lo-to-hi -- unchanged there, this fix is scoped to this panel only per Hamm's request).
    ax.bar(x_point, pct, width=POINT_BAR_WIDTH, color=CLASS8_COLORS["O++"],
          edgecolor="black", linewidth=0.6, zorder=3)
    ax.bar(x_band, hi, width=CI_BAND_WIDTH, color=CLASS8_COLORS["O++"], alpha=CI_BAND_ALPHA,
          edgecolor="black", linewidth=0.4, zorder=3)
    ax.hlines(lo, x_band - CI_BAND_WIDTH / 2, x_band + CI_BAND_WIDTH / 2, color="black",
             linewidth=1.1, zorder=4)
    for xi, ki in zip(x, k):
        ax.text(xi, hi[xi] + 0.05 * np.nanmax([np.nanmax(hi), 0.5]), f"{ki}/{total_k}",
               ha="center", fontsize=6)
    ax.set_xticks(x)
    ax.set_xticklabels(areas, fontsize=7.5)
    ax.set_ylabel("Share of all O++ units, %, 95% CI", fontsize=7.8)
    # Wrapped onto 4 short lines at a smaller size (was 2 lines at 8.5) -- the single-line-per-
    # clause version was wider than this panel's own 4.5in canvas at 8.5pt bold and rendered
    # visibly clipped in the panel's own PNG companion; matplotlib's tight_layout() reserves
    # vertical room for a title automatically but never wraps or shrinks text that overflows
    # horizontally, so this needed an explicit fix, not just a taller figure (2026-08-18).
    ax.set_title(f"Distribution of O++ units across areas\n"
                f"(V1->PFC hierarchy, left->right)\n"
                f"total: {total_k}/{total_n} O++ units, r>={OPLUSPLUS_MIN_CORRELATION:.2f},\n"
                f"causally restricted to {'/'.join(OPLUSPLUS_AREAS)} (2026-08-17)",
                fontsize=7.2, fontweight="bold")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    return fig


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
    ax.axhline(0.5, color=CLASS8_COLORS["Other"], lw=1.2, ls="--", zorder=2,
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
            ax.axhline(0.5, color=CLASS8_COLORS["Other"], lw=1.4, ls="--", zorder=3,
                      label="Other (reference)")
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


def _correlation_distance_matrix(x):
    """x: (n_units, n_bins). Pairwise correlation distance (1 - Pearson r) between per-unit
    RXRR traces -- the distance metric the panel is built around. Rows with zero variance
    (flat traces) get distance 1 to everything (maximally dissimilar, not undefined/NaN)."""
    mu = x.mean(axis=1, keepdims=True)
    sd = x.std(axis=1, keepdims=True)
    ok = sd[:, 0] > 0
    z = np.zeros_like(x)
    z[ok] = (x[ok] - mu[ok]) / sd[ok]
    n = z.shape[1]
    corr = (z @ z.T) / n
    corr = np.clip(corr, -1.0, 1.0)
    dist = 1.0 - corr
    dist[~ok, :] = 1.0
    dist[:, ~ok] = 1.0
    np.fill_diagonal(dist, 0.0)
    return dist


def panel_class_embedding(unit_traces, order, n_shuffle=1000, seed=42):
    """NEW panel (2026-08-06, additional subpanel, does not replace anything): a 2D UMAP
    embedding of per-unit RXRR full-trial firing-rate traces (same condition, same window/bin
    as panel_template_trace_rxrr's real-data traces), colored by functional class
    (S++/S+/S-/S--/O+/Other), with a quantitative separation statistic (silhouette score on the
    correlation-distance matrix, tested against a label-permutation null) -- not just a picture
    to eyeball. If units of the same class are well separated from other classes by their own
    firing pattern, this class distinction is doing real work in activity space, not only in
    whatever criterion originally assigned the label.

    O++ (2026-08-06; O++ definition updated 2026-08-17 to the ground-truth template-correlation
    population, see class8()): `order` carries O++ as its own key (from class_umap), and is
    MERGED into the "O+" label for coloring, the silhouette score and the permutation test
    (keeps this a 2-population-plus-Other statistic, not a 3rd tiny class) -- and separately
    marked with a red star overlay, same convention as panel_composition8_by_area's "contains
    >=1 O++ unit" flag. NOTE: under the current ground-truth O++ definition this merge is a
    display convenience, not a subset relationship -- only 4 of the 52 O++ units were ever also
    Q1-O+ (the other 48 were Q1 "ns"); the two are largely disjoint populations, not nested. The
    silhouette/permutation statistic below therefore tests O+union O++ vs S++/S+/S-/S--/Other,
    not "O+ including its O++ sub-tier" as the pre-2026-08-17 wording implied.

    DISTANCE METRIC: correlation distance (1 - Pearson r) between two units' RXRR traces --
    shape/timing similarity, not raw firing-rate magnitude (a fast unit and a slow unit with the
    identical temporal profile have zero correlation distance). This is the metric silhouette
    is computed on; UMAP's 2D layout (metric='correlation') is a visualization of the same
    space, not an independent statistic.

    GPU: checked before building (RTX A4000, torch/cupy available) -- not used. RAPIDS cuML
    (the GPU UMAP implementation) is not installable on this native-Windows environment without
    WSL2/Linux, and at this data scale (a few thousand units x ~190 time bins) CPU UMAP and a
    dense correlation-distance matrix both run in seconds; GPU would not be the bottleneck here.
    """
    X, y, is_opp = [], [], []
    for c in order:
        arr = unit_traces.get(c, np.zeros((0, 0)))
        if arr.size == 0:
            continue
        X.append(arr)
        disp = "O+" if c == "O++" else c          # O++ merged into O+ for color/silhouette
        y += [disp] * arr.shape[0]
        is_opp += [c == "O++"] * arr.shape[0]
    X = np.concatenate(X, axis=0)
    y = np.array(y)
    is_opp = np.array(is_opp)
    finite = np.isfinite(X).all(axis=1)
    X, y, is_opp = X[finite], y[finite], is_opp[finite]
    display_order = [c for c in order if c != "O++"]

    dist = _correlation_distance_matrix(X)

    import umap
    reducer = umap.UMAP(n_neighbors=15, min_dist=0.1, metric="correlation",
                        random_state=seed)
    emb = reducer.fit_transform(X)

    from sklearn.metrics import silhouette_score
    sil_obs = silhouette_score(dist, y, metric="precomputed")
    rng = np.random.default_rng(seed)
    null = np.empty(n_shuffle)
    for s in range(n_shuffle):
        y_shuf = rng.permutation(y)
        null[s] = silhouette_score(dist, y_shuf, metric="precomputed")
    p_perm = float((np.sum(null >= sil_obs) + 1) / (n_shuffle + 1))

    fig, ax = plt.subplots(figsize=(6.4, 6.0))
    for c in display_order:
        m = y == c
        if not m.any():
            continue
        ax.scatter(emb[m, 0], emb[m, 1], s=14, alpha=0.75, color=CLASS8_COLORS[c],
                  edgecolor="black", linewidth=0.2, label=f"{c} (n={m.sum()})")
    if is_opp.any():
        ax.scatter(emb[is_opp, 0], emb[is_opp, 1], s=90, marker="*", color="red",
                  edgecolor="black", linewidth=0.4, zorder=5,
                  label=f"O++ (n={int(is_opp.sum())})")
    ax.set_xlabel("UMAP-1"); ax.set_ylabel("UMAP-2")
    ax.set_title(f"RXRR firing-pattern embedding, {len(y)} units\n"
                f"silhouette = {sil_obs:.3f} (permutation P = {p_perm:.4f}, "
                f"n_shuffle={n_shuffle})", fontsize=9)
    ax.legend(fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.08),
             ncol=3, columnspacing=0.9, handlelength=1.2)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.subplots_adjust(bottom=0.22)
    return fig, {"n_units": int(len(y)), "silhouette_observed": float(sil_obs),
                "silhouette_p_permutation": p_perm, "n_shuffle": n_shuffle,
                "distance_metric": "correlation (1 - Pearson r) on RXRR full-trial per-unit "
                                  "traces, PSTH_BIN_MS bins",
                "n_per_class": {c: int((y == c).sum()) for c in order}}


def main():
    use_house_style()
    os.makedirs(FIG_DIR, exist_ok=True)
    df = load()
    df = attach_template_corr_oplusplus(df)

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
    ctr, mu, sem, ns5, n_no_omission, _unit_tr5 = compute_population_psth(
        d5, "class5", CLASS5_ORDER, PSTH_WIN, PSTH_BIN_MS, _pooled_omission_onsets)
    fig = panel_group_traces(ctr, mu, sem, ns5)
    made["h"] = save(fig, FIG_DIR, "fig03_h_group_traces"); plt.close(fig)

    # ---- 2026-08-06 REDESIGN: main figure is now 3 rows x 2 cols, 6 subplots --------------
    # A = composition8_by_area (unchanged, panel e above). B = O+-only zoom of the same
    # composition. C-F = grand average +- SEM per functional class (S+/S++, S-/S--, O+, O++),
    # RRRR/RXRR/RRXR/RRRX overlaid, replacing the single pooled RXRR template-trace panel.
    # Presence/stability, peak-rate, and UMAP embedding move to a supplement (see below) --
    # per direction, they no longer sit in the main assembled figure.
    df_stab, stable_table_n, presence_n = attach_stability(df)
    fig, presence_counts, presence_areas = panel_presence_by_area(df_stab)
    made["p1_supp"] = save(fig, FIG_DIR, "fig03_supp_presence_by_area"); plt.close(fig)

    peak_hz, n_no_peak_trials = compute_peak_rate_by_unit(df)
    df_peak = df.copy()
    df_peak["peak_hz"] = peak_hz
    fig, peak_counts, peak_areas = panel_peak_rate_by_area(df_peak)
    made["p2_supp"] = save(fig, FIG_DIR, "fig03_supp_peak_rate_by_area"); plt.close(fig)

    fig = panel_composition_oplusplus_by_area(df, comp8_areas)
    made["B"] = save(fig, FIG_DIR, "fig03_B_composition_oplusplus_by_area"); plt.close(fig)

    d8 = df_legacy[df_legacy.legacy_screened].copy()
    d8["class8"] = class8(d8)
    d8["class8_trace"] = d8["class8"].replace(S_MERGE)
    ns8 = d8.class8_trace.value_counts().to_dict()
    for _c in TRACE_ORDER_MERGED:
        ns8.setdefault(_c, 0)
    cond_data, unit_traces_grand, n_no_trials_grand = compute_population_psth_multi_condition(
        d8, "class8_trace", ["S+", "S-", "O+", "O++"], FULL_TRIAL_WIN, PSTH_BIN_MS,
        GRAND_AVG_CONDITIONS, trial_pooled_classes={"O+", "O++"})
    fig = panel_grand_average_by_condition(cond_data, "S+", "S+/S++ grand average",
                                           CLASS8_COLORS["S+"], smooth_sigma=S_SMOOTH_SIGMA)
    made["C"] = save(fig, FIG_DIR, "fig03_C_grand_avg_Splus"); plt.close(fig)
    fig = panel_grand_average_by_condition(cond_data, "S-", "S-/S-- grand average",
                                           CLASS8_COLORS["S-"], smooth_sigma=S_SMOOTH_SIGMA)
    made["D"] = save(fig, FIG_DIR, "fig03_D_grand_avg_Sminus"); plt.close(fig)
    fig = panel_grand_average_by_condition(cond_data, "O+", "O+ grand average",
                                           CLASS8_COLORS["O+"], smooth_sigma=O_SMOOTH_SIGMA)
    made["E"] = save(fig, FIG_DIR, "fig03_E_grand_avg_Oplus"); plt.close(fig)

    # F | O++, template-correlation population, r>=OPLUSPLUS_MIN_CORRELATION (0.65), causally
    # restricted to OPLUSPLUS_AREAS (V4/TEO/FEF/PFC) -- 2026-08-13, switched from
    # omission_class=="O++" (Q1 peak+ramp, 17 units) to the template-correlation classifier at
    # Hamm's direct request: the Q1-based grand trace did not resemble the manually-observed
    # FEF/PFC O++ template, root-caused to the Q1 classifier itself (near-zero-effect-size
    # units passing FDR significance), not a plotting artifact. Threshold raised 0.60->0.65 and
    # area-restricted 2026-08-17 (this session) after the row-count and S-/S-- contamination
    # findings -- see the OPLUSPLUS_MIN_CORRELATION comment near the top of this file. Same
    # splice pattern as before: independent of C/D/E's (still Q1-based, legacy-screened)
    # population, injected into cond_data's "O++" entries only. See attach_template_corr_
    # oplusplus and panel_composition_oplusplus_by_area for the classifier itself.
    df_opp_full = df[df.is_oplusplus_tc].copy()
    df_opp_full["class8_trace"] = "O++"
    cond_data_opp_full, unit_traces_opp_full, n_no_trials_opp_full = \
        compute_population_psth_multi_condition(
            df_opp_full, "class8_trace", ["O++"], FULL_TRIAL_WIN, PSTH_BIN_MS,
            GRAND_AVG_CONDITIONS, trial_pooled_classes={"O++"})
    for _cond in GRAND_AVG_CONDITIONS:
        _ctr, _mu, _sem, _ns, _n_trials, _sem_kind = cond_data[_cond]
        _, _mu2, _sem2, _ns2, _n_trials2, _sem_kind2 = cond_data_opp_full[_cond]
        _mu["O++"], _sem["O++"], _ns["O++"] = _mu2["O++"], _sem2["O++"], _ns2["O++"]
        _n_trials["O++"], _sem_kind["O++"] = _n_trials2["O++"], _sem_kind2["O++"]

    fig = panel_grand_average_by_condition(cond_data, "O++", "O++ grand average",
                                           CLASS8_COLORS["O++"], smooth_sigma=O_SMOOTH_SIGMA,
                                           log_y=True)
    made["F"] = save(fig, FIG_DIR, "fig03_F_grand_avg_Oplusplus"); plt.close(fig)

    # ---- supplement: matched-N bootstrap sensitivity for panels C-F ----------------------
    # 2026-08-18, Hamm: panels C-F's real bands differ partly because their N's genuinely
    # differ (S+ ~861 units vs O++ 52) -- this asks whether the SHAPES still look this
    # different once every class is resampled to the same nominal N. Explicitly a sensitivity
    # supplement, not a replacement -- see panel_grand_average_matched_n's own docstring.
    n_match = unit_traces_opp_full["RRRR"]["O++"].shape[0]
    matched_n_specs = {
        "S+/S++": ({cond: unit_traces_grand[cond]["S+"] for cond in GRAND_AVG_CONDITIONS},
                   CLASS8_COLORS["S+"]),
        "S-/S--": ({cond: unit_traces_grand[cond]["S-"] for cond in GRAND_AVG_CONDITIONS},
                   CLASS8_COLORS["S-"]),
        "O+": ({cond: unit_traces_grand[cond]["O+"] for cond in GRAND_AVG_CONDITIONS},
              CLASS8_COLORS["O+"]),
        "O++": ({cond: unit_traces_opp_full[cond]["O++"] for cond in GRAND_AVG_CONDITIONS},
               CLASS8_COLORS["O++"]),
    }
    fig = panel_grand_average_matched_n(matched_n_specs, n_match=n_match, n_boot=1000, seed=0)
    made["supp_matched_n"] = save(fig, FIG_DIR, "fig03_supp_matched_n_grand_average")
    plt.close(fig)

    # ---- UMAP: kept in main figure ONLY if it visibly clusters by supergroup (S/O/Other),
    # per direction ("unless we do UMAP in a way that O+/++ cluster together, S+/S++ cluster
    # together, S-/S-- cluster together, Others around") -- otherwise moves to the supplement
    # alongside p1/p2. See panel_class_embedding's supervised-silhouette check below.
    d_umap = df_legacy[df_legacy.legacy_screened].copy()
    d_umap["class_umap"] = class_umap(d_umap)
    _, _, _, _, _, unit_traces_umap = compute_population_psth(
        d_umap, "class_umap", UMAP_CLASS_ORDER, FULL_TRIAL_WIN, PSTH_BIN_MS,
        lambda on: np.asarray(on.get("RXRR", []), float))
    fig, embedding_receipt = panel_class_embedding(unit_traces_umap, UMAP_CLASS_ORDER)
    made["p4_supp"] = save(fig, FIG_DIR, "fig03_supp_class_embedding"); plt.close(fig)

    # ---- assemble main figure: 3 rows x 2 cols -----------------------------------------
    row1 = os.path.join(FIG_DIR, "fig03_row1.svg")
    row2 = os.path.join(FIG_DIR, "fig03_row2.svg")
    row3 = os.path.join(FIG_DIR, "fig03_row3.svg")
    # emit_lettered: standing convention 2026-08-18 (Hamm) -- copy each panel's own .svg/.png
    # to fig03<LETTER>.{svg,png} in HERE, named by the letter it's actually drawn as in the
    # assembled figure, not the panel function's internal name -- so finalizing one panel
    # means reading one clearly-named full-frame file, not decoding made["e"] -> "a".
    assemble([made["e"], made["B"]], row1, ncol=2, letters=True, letter_offset=0,
             emit_lettered=(HERE, "fig03"))
    assemble([made["C"], made["D"]], row2, ncol=2, letters=True, letter_offset=2,
             emit_lettered=(HERE, "fig03"))
    assemble([made["E"], made["F"]], row3, ncol=2, letters=True, letter_offset=4,
             emit_lettered=(HERE, "fig03"))
    out, w, h = assemble([row1, row2, row3], os.path.join(HERE, "fig03.svg"), ncol=1, gap=1.0,
                         label_inset=True, letters=False)
    print(f"assembled -> {out}  {w:.1f} x {h:.1f} pt")
    rasterize(out, os.path.join(HERE, "fig03.png"))
    print(f"rasterized -> {os.path.join(HERE, 'fig03.png')}")

    # ---- assemble supplement: presence/stability, peak-rate, UMAP embedding ---------------
    supp_row = os.path.join(FIG_DIR, "fig03_supp_row.svg")
    assemble([made["p1_supp"], made["p2_supp"]], supp_row, ncol=2, letters=True)
    supp_out, sw, sh = assemble([supp_row, made["p4_supp"]],
                                os.path.join(FIG_DIR, "fig03_supp_presence_peakrate_umap.svg"),
                                ncol=1, gap=1.0, label_inset=True, letters=False)
    print(f"assembled supplement -> {supp_out}  {sw:.1f} x {sh:.1f} pt")

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
    table8 = np.array([[comp8_counts[a].get(c, 0) for c in CLASS8_ORDER]
                       for a in comp8_areas])
    # g: was computed above (panel_stim_omission_correlation) but never reached this list until
    # 2026-07-30 -- the figure and its shuffle-null p_shuffle were drawn and shipped, but the
    # analytic/shuffle statistic never reached fig03_stats.md. Found during the inventory deep
    # review; fixed by appending it here instead of leaving it a dangling local variable.
    stats.append(corr_res)

    stats.append(contingency(table8, "fig03", "e", "area predicts S/O composition", "unit",
                             "fig03_composition", rows=comp8_areas, cols=CLASS8_ORDER,
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
                    "units so 'Other' means screened-negative, not never-tested"},
        "class8_priority": "O-- > O++ > O- > O+ > S-- > S++ > S- > S+ > Other (each a strictly "
                           "more specific claim about the same unit)",
        "class_embedding_panel_p4": embedding_receipt,
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
            "n_units_no_rxrr_trials": n_no_trials_grand,
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
    print("RXRR template trace n:", ns8, "no-RXRR units skipped:", n_no_trials_grand)


if __name__ == "__main__":
    main()
