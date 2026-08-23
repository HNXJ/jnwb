r"""
Figure 5: one panel per band, all ten areas overlaid, across the omission window.

WHY THIS ARRANGEMENT
    The stacked per-area figures answer "what does this area do in every band". This one
    transposes that: within a band, how do the areas order themselves, and does that order
    look like the visual hierarchy? Putting ten area traces in one axis makes the ordering
    directly readable, which it is not when the same data are split across ten panels.

MEASURE
    Ratio of expected power: power averaged over trials, divided by that channel's own
    -250 to -50 ms pre-omission baseline, with 10*log10 applied once after averaging over
    channels, band frequencies and sessions. Never average decibels
    (artifacts/.lab/db_averaging_bias_finding_20260728.json).

AGGREGATION
    Unweighted mean of per-session traces, so a session contributing many channels does not
    dominate. Ribbons are the SEM across sessions, mapped through the same logarithm.
    Sessions whose map is grossly out of scale for their area are dropped from the display
    and reported.

WINDOW
    -1500 to +1500 ms from omission onset. Two boundaries are marked because what
    contributes changes at them: fourth-position omissions end the trial at +897 ms, and in
    the remaining conditions a new stimulus begins at +1031 ms. Nothing to the right of
    +897 ms is omission-only.

OUTPUT
    context/figures/fig05_band_power_hierarchy/svg/fig05_band_hierarchy.{png,svg}
    context/figures/fig05_band_power_hierarchy/svg/fig05_band_hierarchy.receipt.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from svgassemble import assemble
from figstats import correlation, group_location, paired_location, write
from jnwb.spectral import to_db

MAPS = r"D:/workspace/omission/outputs/omission_tfr_maps_w1500/maps.npz"
FIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "svg")

AREA_ORDER = ["V1", "V2", "V3a/d", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"]
BANDS = {"Theta (4-8 Hz)": (4, 8), "Alpha (8-14 Hz)": (8, 14), "Beta (14-30 Hz)": (14, 30),
         "Low gamma (30-50 Hz)": (30, 50), "High gamma (50-80 Hz)": (50, 80)}
# hierarchy-ordered colours: cool for early visual, warm for frontal
AREA_COLORS = {"V1": "#08306B", "V2": "#2171B5", "V3a/d": "#4292C6", "V4": "#6BAED6",
               "MT": "#41AB5D", "MST": "#238B45", "TEO": "#FDAE6B", "FST": "#F16913",
               "FEF": "#D94801", "PFC": "#A63603"}

WIN = (-1500, 1500)
PREV_STIM = (-1031, -500)
OMISSION = (0, 531)
NEXT_STIM = (1031, 1562)
SLOT4_END = 897
COVERAGE_MIN = 0.55
OUTLIER_FACTOR = 5.0


def load():
    z = np.load(MAPS, allow_pickle=True)
    keys = [str(k) for k in z["keys"]]
    sums, counts, freqs, times = z["sums"], z["counts"], z["freqs"], z["times"]
    maps = {}
    for i, k in enumerate(keys):
        with np.errstate(invalid="ignore", divide="ignore"):
            m = np.where(counts[i] > 0, sums[i] / np.maximum(counts[i], 1), np.nan)
        per_bin = np.nanmax(counts[i], axis=0)
        mx = np.nanmax(per_bin) if per_bin.size else 0
        keep = per_bin >= COVERAGE_MIN * mx if mx > 0 else per_bin > 0
        m[:, ~keep] = np.nan
        maps[k] = m
    return maps, freqs, times


def area_sessions(maps, area, layer="all"):
    return {k.split("|")[0]: m for k, m in maps.items()
            if k.split("|")[1] == area and k.split("|")[2] == layer}


def drop_outliers(sess):
    if len(sess) < 3:
        return sess, []
    names = list(sess)
    mx = np.array([np.nanmax(np.abs(to_db(sess[n]))) for n in names])
    med = float(np.median(mx))
    keep = {n: sess[n] for n, v in zip(names, mx) if v <= OUTLIER_FACTOR * med}
    dropped = [n for n, v in zip(names, mx) if v > OUTLIER_FACTOR * med]
    return (keep, dropped) if keep else (sess, [])


def run(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", default="all", help="all, sup, deep or mid")
    ap.add_argument("--out", default=None)
    ap.add_argument("--sem", action="store_true", help="draw SEM ribbons (busy with 10 areas)")
    args = ap.parse_args(argv)
    os.makedirs(FIG_DIR, exist_ok=True)
    maps, freqs, times = load()

    present = [a for a in AREA_ORDER if area_sessions(maps, a, args.layer)]
    nrow = len(BANDS)
    fig = plt.figure(figsize=(11.5, 2.55 * nrow))
    gs = fig.add_gridspec(nrow, 1, hspace=0.16, left=0.085, right=0.80,
                          top=0.955, bottom=0.075)

    twin = (times >= OMISSION[0]) & (times < OMISSION[1])
    stats = []
    counts, dropped_all = {}, {}
    for bi, (bname, (lo, hi)) in enumerate(BANDS.items()):
        ax = fig.add_subplot(gs[bi])
        fsel = (freqs >= lo) & (freqs < hi)
        per_area_omission_db = {}
        for area in present:
            sess = area_sessions(maps, area, args.layer)
            kept, dropped = drop_outliers(sess)
            if dropped:
                dropped_all.setdefault(area, dropped)
            counts[area] = len(kept)
            r = np.stack([np.nanmean(m[fsel], axis=0) for m in kept.values()])
            mu = np.nanmean(r, axis=0)
            # One scalar per session: average power over the omission window, THEN log --
            # never log before averaging (db_averaging_bias_finding_20260728.json). This is
            # the value the stats below compare across areas; the traces above are unaffected.
            per_area_omission_db[area] = to_db(np.nanmean(r[:, twin], axis=1))
            ax.plot(times, to_db(mu), color=AREA_COLORS.get(area, "0.4"), lw=1.9,
                    label=f"{area} (n={len(kept)})", zorder=3)
            if args.sem:
                n = np.sum(np.isfinite(r), axis=0)
                sem = np.nanstd(r, axis=0, ddof=1) / np.sqrt(np.maximum(n, 1))
                ax.fill_between(times, to_db(np.maximum(mu - sem, 1e-12)), to_db(mu + sem),
                                color=AREA_COLORS.get(area, "0.4"), alpha=0.15, lw=0, zorder=2)

        multi = [per_area_omission_db[a] for a in present if per_area_omission_db[a].size >= 2]
        multi_labels = [a for a in present if per_area_omission_db[a].size >= 2]
        if len(multi) >= 2:
            stats.append(group_location(
                multi, multi_labels, "fig05", bname, "omission-window dB differs across areas",
                "session", "fig05_area_by_band",
                note="proper unit of inference: one value per session, averaged over the "
                     "omission window (0-531 ms), power averaged then logged once"))
        rank_x, rank_y = [], []
        for a in present:
            v = per_area_omission_db[a]
            if v.size:
                rank_x.append(AREA_ORDER.index(a) + 1)
                rank_y.append(float(np.nanmean(v)))
        if len(rank_x) >= 4:
            stats.append(correlation(
                rank_x, rank_y, "fig05", bname, "area mean dB vs hierarchy rank", "area",
                "fig05_area_by_band", method="spearman",
                note=f"descriptive: {len(rank_x)} non-independent area aggregates carry "
                     "almost no inferential weight on their own"))

        ax.axhline(0, color="black", lw=0.8)
        ax.axvline(0, color="green", ls="--", lw=1.5)
        ax.axvline(SLOT4_END, color="0.25", ls=":", lw=1.1)
        ax.axvspan(*PREV_STIM, color="#F8C6C6", alpha=0.40, zorder=0)
        ax.axvspan(*OMISSION, color="#E7D3F0", alpha=0.50, zorder=0)
        ax.axvspan(NEXT_STIM[0], min(NEXT_STIM[1], WIN[1]), color="#F8C6C6",
                   alpha=0.20, zorder=0)
        ax.set_xlim(*WIN)
        ax.set_ylabel("Power change (dB)", fontsize=9)
        ax.text(0.012, 0.90, bname, transform=ax.transAxes, fontsize=12, fontweight="bold",
                va="top")
        ax.set_xticks([-1500, -1000, -500, 0, 500, 1000, 1500])
        if bi == 0:
            ax.legend(fontsize=8, loc="center left", bbox_to_anchor=(1.005, -1.6),
                      frameon=False, title="Area", title_fontsize=9)
        if bi == nrow - 1:
            ax.set_xticklabels(["-1500", "-1000", "-500", "0", "+500", "+1000", "+1500"],
                               color="green", fontsize=11)
            ax.set_xlabel("Time from omission onset (ms)", color="green", fontsize=13)
            ax.text(0.5, -0.42, "* right of the dotted line: p2/p3 omissions only; a new "
                    "stimulus begins at +1031 ms", transform=ax.transAxes, ha="center",
                    va="top", fontsize=8, color="0.35")
        else:
            ax.tick_params(labelbottom=False)

    base = args.out or f"fig05_band_hierarchy{'' if args.layer == 'all' else '_' + args.layer}"
    out = os.path.join(FIG_DIR, base + ".png")
    fig.savefig(out, dpi=185)
    fig.savefig(out.replace(".png", ".svg"))
    plt.close(fig)

    json.dump({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__), "maps": MAPS,
        "arrangement": "one panel per band, all areas overlaid",
        "layer": args.layer, "areas": present, "sessions_per_area": counts,
        "sessions_dropped_from_display": dropped_all,
        "bands_hz": {k: list(v) for k, v in BANDS.items()},
        "window_ms": list(WIN),
        "measure": "ratio of expected power vs each channel's own -250..-50 ms pre-omission "
                   "baseline; 10*log10 applied once after averaging",
        "aggregation": "unweighted mean of per-session traces",
        "composition_caveat": "fourth-position omissions end the trial at +897 ms; a new "
                              "stimulus begins at +1031 ms in the remaining conditions",
    }, open(os.path.join(FIG_DIR, base + ".receipt.json"), "w", encoding="utf-8"), indent=2)

    write(stats, FIG_DIR, base, f"Figure 5 ({args.layer}) -- band-power hierarchy: statistics",
         preamble="Scalar tested: mean power over the omission window (0-531 ms), averaged "
                  "over trials and channels within a session first, then divided by that "
                  "session's baseline and logged once -- never averaging in dB. `session` is "
                  "the unit of inference for the across-area comparison; the hierarchy-rank "
                  "correlation is a descriptive effect size over at most ten area aggregates.")

    print(f"areas: {present}")
    print(f"sessions per area: {counts}")
    if dropped_all:
        print(f"dropped from display: {dropped_all}")
    print("WROTE", out, "and", out.replace(".png", ".svg"))


# ============================================================================================
# Main figure: 5 bands x 2 conditions (RXRR, RRRR), all areas overlaid per panel, from
# extract_condition_tfr_maps.py. This is what fig05.svg is assembled from. The omission-pooled
# hierarchy panels above (run(), PANEL_SET) are unchanged and still feed the supplements from
# this same svg/ folder; they are simply no longer what "figure 5" itself shows.
# ============================================================================================
CONDITION_MAPS = r"D:/workspace/omission/outputs/condition_tfr_maps_p1d1p2d2p3/maps.npz"
CONDITIONS = ["RXRR", "RRRR"]
CONDITION_WIN = (-500, 2593)
COND_OMIT_SLOT = {"RXRR": 2, "RRRR": None}
COND_LABEL = {"RXRR": "RXRR (p2 omitted)", "RRRR": "RRRR (p2 real)"}


def load_condition_maps():
    z = np.load(CONDITION_MAPS, allow_pickle=True)
    keys = [str(k) for k in z["keys"]]
    sums, counts, freqs, times = z["sums"], z["counts"], z["freqs"], z["times"]
    maps = {}
    for i, k in enumerate(keys):
        with np.errstate(invalid="ignore", divide="ignore"):
            m = np.where(counts[i] > 0, sums[i] / np.maximum(counts[i], 1), np.nan)
        per_bin = np.nanmax(counts[i], axis=0)
        mx = np.nanmax(per_bin) if per_bin.size else 0
        keep = per_bin >= COVERAGE_MIN * mx if mx > 0 else per_bin > 0
        m[:, ~keep] = np.nan
        maps[k] = m
    return maps, freqs, times


def area_cond_sessions(maps, area, cond, layer="all"):
    return {k.split("|")[0]: m for k, m in maps.items()
            if k.split("|")[1] == area and k.split("|")[2] == layer and k.split("|")[3] == cond}


P2_WINDOW_MS = (1031, 1562)  # p2 onset to d2 onset, per omission.jnwb_ext.sequence_layout.EPOCH_ONSETS_MS


def condition_p2_band_stats(maps, freqs, times, present):
    """Is p2-window band power different between RXRR (p2 omitted) and RRRR (p2 real)?

    Same construction as fig04's condition_p2_band_stats: paired by session (maps.npz is
    already trial-pooled within session, so session is the unit of inference), Wilcoxon or
    paired t chosen by Shapiro-Wilk on the differences. Family = the full area x band grid
    (all ten areas here, not just V1/PFC), corrected together.
    """
    tmask = (times >= P2_WINDOW_MS[0]) & (times < P2_WINDOW_MS[1])
    results = []
    for area in present:
        sess_a = area_cond_sessions(maps, area, "RXRR")
        sess_b = area_cond_sessions(maps, area, "RRRR")
        common = sorted(set(sess_a) & set(sess_b))
        for bname, (lo, hi) in BANDS.items():
            fsel = (freqs >= lo) & (freqs < hi)
            a_vals, b_vals = [], []
            for s in common:
                ra = np.nanmean(sess_a[s][fsel], axis=0)[tmask]
                rb = np.nanmean(sess_b[s][fsel], axis=0)[tmask]
                if np.any(np.isfinite(ra)) and np.any(np.isfinite(rb)):
                    a_vals.append(to_db(np.nanmean(ra)))
                    b_vals.append(to_db(np.nanmean(rb)))
            results.append(paired_location(
                b_vals, a_vals, figure="fig05", panel="condition_p2",
                question=f"{area} {bname} p2 RRRR vs RXRR", unit="session",
                family="fig05_condition_p2",
                note=f"n={len(common)} sessions with both conditions"))
    return results


def build_rxrr_rrrr_hierarchy_figure():
    """5 rows (bands) x 2 columns (RXRR, RRRR), all areas overlaid per panel."""
    from figstyle import mark_full_trial_axis
    maps, freqs, times = load_condition_maps()
    present = [a for a in AREA_ORDER
              if any(area_cond_sessions(maps, a, c) for c in CONDITIONS)]

    # subplots_adjust, not tight_layout: this axes configuration trips matplotlib's
    # tight_layout compatibility check (it warns and silently no-ops), which is what left a
    # large blank band between the suptitle and the first row in two earlier attempts.
    fig, axes = plt.subplots(len(BANDS), 2, figsize=(13.0, 2.55 * len(BANDS)),
                             gridspec_kw={"hspace": 0.16, "wspace": 0.08, "top": 0.92,
                                          "bottom": 0.055, "left": 0.055, "right": 0.885})
    counts, dropped_all = {}, {}
    legend_handles = []
    for bi, (bname, (lo, hi)) in enumerate(BANDS.items()):
        fsel = (freqs >= lo) & (freqs < hi)
        for ci, cond in enumerate(CONDITIONS):
            ax = axes[bi, ci]
            for area in present:
                sess = area_cond_sessions(maps, area, cond)
                kept, dropped = drop_outliers(sess)
                if dropped:
                    dropped_all.setdefault(f"{area}_{cond}", dropped)
                counts[f"{area}_{cond}"] = len(kept)
                if not kept:
                    continue
                r = np.stack([np.nanmean(m[fsel], axis=0) for m in kept.values()])
                mu = np.nanmean(r, axis=0)
                line, = ax.plot(times, to_db(mu), color=AREA_COLORS.get(area, "0.4"), lw=1.7,
                                label=f"{area} (n={len(kept)})", zorder=3)
                if bi == 0 and ci == 0:
                    legend_handles.append(line)
            ax.axhline(0, color="black", lw=0.8)
            mark_full_trial_axis(ax, CONDITION_WIN, omit_slot=COND_OMIT_SLOT[cond])
            if ci == 0:
                ax.set_ylabel("Power change (dB)", fontsize=9)
            else:
                ax.tick_params(labelleft=False)
            if bi == 0:
                ax.set_title(COND_LABEL[cond], fontsize=11, fontweight="bold")
            ax.text(0.012, 0.90, bname, transform=ax.transAxes, fontsize=10,
                   fontweight="bold", va="top")
            if bi == len(BANDS) - 1:
                ax.set_xlabel("Time from p1 onset (ms)", fontsize=9)
            else:
                ax.tick_params(labelbottom=False)

    fig.legend(legend_handles, [h.get_label() for h in legend_handles], fontsize=7,
              loc="center left", bbox_to_anchor=(0.895, 0.5), frameon=False, title="Area",
              title_fontsize=8)
    fig.suptitle("Band-power hierarchy, RXRR vs RRRR, p1-d1-p2-d2-p3; baseline = middle of d1",
                fontsize=13, fontweight="bold", y=0.985)
    out = os.path.join(FIG_DIR, "fig05_rxrr_rrrr_hierarchy")
    fig.savefig(out + ".png", dpi=180)
    fig.savefig(out + ".svg")
    plt.close(fig)

    with open(out + ".receipt.json", "w", encoding="utf-8") as fh:
        json.dump({
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "script": os.path.abspath(__file__), "maps": CONDITION_MAPS,
            "arrangement": "5 rows (bands) x 2 columns (RXRR, RRRR), all areas overlaid per "
                           "panel", "areas": present, "conditions": CONDITIONS,
            "window_ms_re_p1": list(CONDITION_WIN),
            "baseline": "middle third of d1 (706-856 ms from p1), not a pre-trial fixation "
                       "baseline -- see extract_condition_tfr_maps.py",
            "sessions_per_area_condition": counts,
            "sessions_dropped_from_display": dropped_all,
            "bands_hz": {k: list(v) for k, v in BANDS.items()},
        }, fh, indent=2)
    print("areas:", present)
    print("sessions per area/condition:", counts)
    if dropped_all:
        print("dropped from display:", dropped_all)

    stats_results = condition_p2_band_stats(maps, freqs, times, present)
    write(stats_results, FIG_DIR, "fig05_condition",
          title="Figure 5 -- band-power hierarchy, p2-window RXRR vs RRRR",
          preamble="Paired (by session) test of p2-window mean band power, RRRR (p2 real) "
                   "minus RXRR (p2 omitted), per area x band across all ten areas. Positive "
                   "effect = more power when p2 is a real stimulus. Family = full area x band "
                   "grid (Holm and BH-FDR both reported). Unit of inference is session.")
    print(f"condition_p2 stats: {len(stats_results)} tests written to "
          f"{os.path.join(FIG_DIR, 'fig05_condition_stats.md')}")
    return out + ".svg"


# A bare run emits every panel: the pooled figure plus one per laminar compartment. The
# pooled one is the main figure; the three laminar ones are supplementary stock.
PANEL_SET = ["all", "sup", "mid", "deep"]


def main():
    argv = sys.argv[1:]
    if argv:
        run(argv)
        return
    for layer in PANEL_SET:
        print("--- layer", layer)
        run(["--layer", layer])
    panel_svg = build_rxrr_rrrr_hierarchy_figure()
    here = os.path.dirname(os.path.abspath(__file__))
    out, w, h = assemble([panel_svg], os.path.join(here, "fig05.svg"), ncol=1, letters=False)
    print(f"assembled -> {out}  {w:.1f} x {h:.1f} pt")


if __name__ == "__main__":
    main()
