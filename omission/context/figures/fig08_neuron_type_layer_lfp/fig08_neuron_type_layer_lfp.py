r"""
fig08 -- Supplemental: neuron functional class x layer x firing rate x LFP band-power/phase-
locking relationships during omission. Built for goal-neuron-type-layer-lfp-relationships-20260815
(see artifacts/.lab/ for the underlying analyses -- this script only draws them).

FOUR PANELS, each a DIFFERENT pre-registered confirmatory family (Part 3 of the approved plan) --
population scope stated per panel (omission-figures skill), never pooled across panels:
  A. Layer enrichment (sup-rate vs area/animal baseline) by class -- family1_layer_enrichment.csv,
     within animal x within area (never a pooled laminar coefficient).
  B. Firing rate by class vs the rest of that area's units -- family2_firing_rate_by_class.csv.
  C. Corrected-design PPC spike-LFP phase-locking hit-rate, class x band, FEF/PFC/TEO
     (n_sessions>=5 subset only -- V4's n=3 hits are real but excluded from this panel as
     too fragile to draw at the same visual weight; see class_hit_rates_v2.csv for the full
     table) -- evidence-corrected-ppc-spike-lfp-coupling-by-class-20260815.
  D. LFP band-power onset of divergence (real stimulus vs omitted p2 slot), continuous fit at
     native 10ms TFR resolution, by area x band -- lfp_band_onset_latency/area_band_summary.csv.

Panel E is the exploratory sweep -- deliberately NOT drawn as a headline panel (labelled
non-confirmatory, see outputs/relationship_search/README.md); its top descriptive correlations
are listed in a caption note instead of a plotted panel, so a reader cannot mistake an
uncorrected exploratory scan for one of the four confirmatory results above.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "context" / "figures"))

import figstyle  # noqa: E402

FIG_DIR = Path(__file__).parent
SVG_DIR = FIG_DIR / "svg"

FAMILY1 = REPO / "outputs/relationship_search/family1_layer_enrichment.csv"
FAMILY2 = REPO / "outputs/relationship_search/family2_firing_rate_by_class.csv"
PPC_HIT_RATES = REPO / "outputs/spike_lfp_coupling/class_hit_rates_v2.csv"
LFP_ONSET = REPO / "outputs/classification/lfp_band_onset_latency/area_band_summary.csv"
EXPLORATORY = REPO / "outputs/relationship_search/exploratory_sweep_all_pairs.csv"

# Class palette: reuses figstyle.CLASS_COLORS' O-tier hues for the O-classes (consistent with
# every other figure in this project); the S-tiers have no existing figstyle convention (this
# project's figures have not previously needed an S+/S++/S-/S-- palette side-by-side with
# O-classes in one panel), so a parallel green/orange pair is added HERE, scoped to this figure
# only -- not written into figstyle.py, since a single new figure's local need is not grounds to
# expand a shared style module (CLAUDE.md: "change only what the task requires").
CLASS_COLORS = {
    "is_Splus": "#238B45", "is_Splus_double": "#00441B",
    "is_Sminus": "#F16913", "is_Sminus_double": "#7F2704",
    "is_Oplus": figstyle.CLASS_COLORS["O+"], "is_Oplus_double": figstyle.CLASS_COLORS["O++"],
    "is_Ominus": figstyle.CLASS_COLORS["O-"], "is_Ominus_double": figstyle.CLASS_COLORS["O--"],
}
CLASS_LABELS = {
    "is_Splus": "S+", "is_Splus_double": "S++", "is_Sminus": "S-", "is_Sminus_double": "S--",
    "is_Oplus": "O+", "is_Oplus_double": "O++", "is_Ominus": "O-", "is_Ominus_double": "O--",
}
CLASS_ORDER8 = ["is_Splus", "is_Splus_double", "is_Sminus", "is_Sminus_double",
               "is_Oplus", "is_Oplus_double", "is_Ominus", "is_Ominus_double"]


def panel_a_layer_enrichment(ax, used_placeholder_flags):
    df = pd.read_csv(FAMILY1)
    if df.empty:
        ax.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax.transAxes)
        used_placeholder_flags.append("A")
        return
    df["log2_enrichment"] = np.log2(
        np.clip(df.class_sup_rate, 1e-6, None) / np.clip(df.stratum_baseline_sup_rate, 1e-6, None))
    sig = df[df.p_holm < 0.05]
    for i, cls in enumerate(CLASS_ORDER8):
        sub = sig[sig["class"] == cls]
        if sub.empty:
            continue
        y = np.full(len(sub), i) + np.linspace(-0.15, 0.15, len(sub)) if len(sub) > 1 else [i]
        ax.scatter(sub.log2_enrichment, y, color=CLASS_COLORS[cls], s=60,
                  edgecolor="black", linewidth=0.5, zorder=3)
        for (_, row), yy in zip(sub.iterrows(), y):
            ax.annotate(f"{row.animal}/{row.area}", (row.log2_enrichment, yy),
                       fontsize=6, xytext=(4, 0), textcoords="offset points", va="center")
    ax.axvline(0, color="black", lw=0.8, ls="--")
    ax.set_yticks(range(len(CLASS_ORDER8)))
    ax.set_yticklabels([CLASS_LABELS[c] for c in CLASS_ORDER8], fontsize=9)
    ax.set_xlabel("log2(class sup-rate / area x animal baseline sup-rate)", fontsize=9)
    ax.set_title("A. Layer enrichment, Holm-significant cells only\n"
                 "(within animal x within area; population = layer-informative units, N/A pooled)",
                 fontsize=9)
    ax.invert_yaxis()


def panel_b_firing_rate(ax, used_placeholder_flags):
    df = pd.read_csv(FAMILY2)
    if df.empty:
        ax.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax.transAxes)
        used_placeholder_flags.append("B")
        return
    sig = df[df.p_holm < 0.05].copy()
    sig["log2_ratio"] = np.log2(sig.median_class_hz / sig.median_other_hz)
    for i, cls in enumerate(CLASS_ORDER8):
        sub = sig[sig["class"] == cls]
        if sub.empty:
            continue
        y = np.full(len(sub), i) + np.linspace(-0.15, 0.15, len(sub)) if len(sub) > 1 else [i]
        ax.scatter(sub.log2_ratio, y, color=CLASS_COLORS[cls], s=60,
                  edgecolor="black", linewidth=0.5, zorder=3)
        for (_, row), yy in zip(sub.iterrows(), y):
            ax.annotate(row.area, (row.log2_ratio, yy), fontsize=6,
                       xytext=(4, 0), textcoords="offset points", va="center")
    ax.axvline(0, color="black", lw=0.8, ls="--")
    ax.set_yticks(range(len(CLASS_ORDER8)))
    ax.set_yticklabels([CLASS_LABELS[c] for c in CLASS_ORDER8], fontsize=9)
    ax.set_xlabel("log2(class median Hz / same-area other-units median Hz)", fontsize=9)
    ax.set_title("B. Firing rate vs area's other units, Holm-significant cells only\n"
                 "(population = SUA units per area, Mann-Whitney)", fontsize=9)
    ax.invert_yaxis()


def panel_c_ppc_hit_rate(ax, used_placeholder_flags):
    if not PPC_HIT_RATES.exists():
        ax.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax.transAxes)
        used_placeholder_flags.append("C")
        return
    df = pd.read_csv(PPC_HIT_RATES)
    sub = df[(df.above_chance) & (df.n_sessions >= 5)].copy()
    if sub.empty:
        ax.text(0.5, 0.5, "no cell with n>=5 sessions above chance",
               ha="center", va="center", transform=ax.transAxes, fontsize=8)
        return
    bands = sorted(sub.band.unique())
    areas = sorted(sub.area.unique())
    grid = np.full((len(CLASS_ORDER8), len(bands) * len(areas)), np.nan)
    col_labels = [f"{a}\n{b}" for b in bands for a in areas]
    for _, row in sub.iterrows():
        ci = CLASS_ORDER8.index(row["class"]) if row["class"] in CLASS_ORDER8 else None
        if ci is None:
            continue
        bj = bands.index(row.band)
        aj = areas.index(row.area)
        grid[ci, bj * len(areas) + aj] = row.hit_rate
    im = ax.imshow(grid, cmap="viridis", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, fontsize=6)
    ax.set_yticks(range(len(CLASS_ORDER8)))
    ax.set_yticklabels([CLASS_LABELS[c] for c in CLASS_ORDER8], fontsize=9)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="hit rate")
    ax.set_title("C. Corrected PPC hit-rate, class x band x area\n"
                 "(n_sessions>=5 cells with CI lower bound above chance only; omission context)",
                 fontsize=9)


def panel_d_lfp_onset(ax, used_placeholder_flags):
    if not LFP_ONSET.exists():
        ax.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax.transAxes)
        used_placeholder_flags.append("D")
        return
    df = pd.read_csv(LFP_ONSET)
    bands = list(figstyle.BANDS.keys())
    for band, color in zip(bands, figstyle.BAND_COLORS):
        sub = df[df.band == band].copy()
        sub["area_rank"] = sub.area.apply(
            lambda a: figstyle.AREA_ORDER.index(a) if a in figstyle.AREA_ORDER else np.nan)
        sub = sub.dropna(subset=["area_rank"]).sort_values("area_rank")
        if sub.empty:
            continue
        ax.errorbar(sub.area_rank, sub.onset_ms,
                   yerr=[sub.onset_ms - sub.ci_lo_ms, sub.ci_hi_ms - sub.onset_ms],
                   fmt="o-", color=color, label=band.split(" (")[0], markersize=4, lw=1.2,
                   capsize=2)
    ax.axhline(10.0, color="red", ls=":", lw=1, label="10ms general floor")
    ax.axhline(40.0, color="0.4", ls=":", lw=1, label="40ms visual floor")
    ax.set_xticks(range(len(figstyle.AREA_ORDER)))
    ax.set_xticklabels(figstyle.AREA_ORDER, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("onset of stimulus-vs-omission LFP divergence (ms post p2 onset)", fontsize=8)
    ax.legend(fontsize=6, ncol=2, loc="upper left")
    ax.set_title("D. LFP band-power onset latency, native 10ms resolution\n"
                 "(continuous exponential-rise fit, session-bootstrap CI; 0/38 cells violate "
                 "the 10ms floor)", fontsize=9)


def main():
    figstyle.use_house_style()
    fig, axes = plt.subplots(2, 2, figsize=(13, 11))
    used_placeholder_flags = []

    panel_a_layer_enrichment(axes[0, 0], used_placeholder_flags)
    panel_b_firing_rate(axes[0, 1], used_placeholder_flags)
    panel_c_ppc_hit_rate(axes[1, 0], used_placeholder_flags)
    panel_d_lfp_onset(axes[1, 1], used_placeholder_flags)

    fig.suptitle(
        "Fig 08 (supplement) -- Neuron functional class x layer x firing rate x LFP "
        "band-power/phase-locking, during omission\n"
        "Each panel is its own pre-registered, Holm/BH-corrected family (see caption); "
        "the broader exploratory sweep is reported separately, not drawn here.",
        fontsize=11, y=1.00)
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    if used_placeholder_flags:
        fig.text(0.5, 0.5, "PLACEHOLDER-DUMMY", fontsize=60, color="red", alpha=0.5,
                 ha="center", va="center", rotation=30, zorder=100)

    path = figstyle.save(fig, SVG_DIR, "fig08_neuron_type_layer_lfp")
    print(f"WROTE {path}")
    if used_placeholder_flags:
        print(f"PLACEHOLDER-DUMMY panels: {used_placeholder_flags}")

    # Caption note: top exploratory-sweep correlations (Part 4), reported as text, not drawn --
    # the omission-figures skill's per-panel-scope rule applies just as much to what a caption
    # implies as to what an axis plots, so these are explicitly labelled non-confirmatory here.
    if EXPLORATORY.exists():
        ex = pd.read_csv(EXPLORATORY)
        top = ex.reindex(ex.spearman_rho.abs().sort_values(ascending=False).index).head(5)
        note_lines = ["EXPLORATORY SWEEP -- NOT CORRECTED, NOT CONFIRMATORY -- top 5 by |rho|:"]
        for _, r in top.iterrows():
            note_lines.append(f"  {r.relation}: rho={r.spearman_rho:.2f}, p={r.p:.3f}, n={int(r.n)}")
        (SVG_DIR / "fig08_caption_exploratory_note.txt").write_text(
            "\n".join(note_lines), encoding="utf-8")
        print("\n".join(note_lines))


if __name__ == "__main__":
    main()
