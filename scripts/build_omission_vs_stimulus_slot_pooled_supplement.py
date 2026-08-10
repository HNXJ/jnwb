r"""
Slot-pooled omission-vs-stimulus supplement: for each of the ten areas, does band power
change from baseline differently when a stimulus is omitted than when it actually occurs?

WHY THIS EXISTS (separate from fig04)
    fig04 itself compares RXRR against RRRR, both p1-aligned, both only at the p2 slot
    position. That is deliberately a narrow, clean comparison. A further request asked to
    also pool ALL omission slot positions (p2, p3, p4; AXAB/BXBA/RXRR, AAXB/BBXA/RRXR,
    AAAX/BBBX/RRRX) against a matched "real stimulus" pool, purely to gain statistical power
    for a band-power-change-from-baseline comparison. Pooling across slot positions only
    makes sense if every trial is re-aligned to the event itself (omission or stimulus onset)
    rather than to a fixed p1-relative time, which is exactly what
    outputs/omission_tfr_maps_w1500 (pre-existing) and
    outputs/stimulus_pooled_tfr_maps_w1500 (built 2026-08-04,
    scripts/extract_stimulus_pooled_tfr_maps.py) provide. This script is a SEPARATE
    supplement, not a change to fig04.svg's own p1-aligned, p2-only design.

INPUTS (identical measure and window on both sides -- see each extraction script)
    outputs/omission_tfr_maps_w1500/maps.npz         9 omission conditions pooled, aligned to
                                                      the omitted slot
    outputs/stimulus_pooled_tfr_maps_w1500/maps.npz  9 matched real-stimulus (condition, slot)
                                                      pairs pooled, aligned to that slot's onset
    Both: dB(f,t) = 10*log10(power(f,t) / baseline(f)), baseline = -250..-50 ms pre-onset,
    trial-mean power first then the ratio then the logarithm once. Window -1500..+1500 ms.
    Session is the unit of inference; both datasets are already trial-pooled per session.

LAYOUT per area
    2x2: top row = spectrograms (omission-pooled | stimulus-pooled), sharing one area-specific
    colour scale; bottom row = one band-trace panel per side, precision-weighted mean +- SEM
    across sessions (see fig04_v1_pfc_condition_tfr.weighted_band_mean_sem -- reused directly,
    not reimplemented).

STATISTICS
    Paired-by-session test (Wilcoxon or paired t, chosen by Shapiro-Wilk on the differences)
    of omitted-slot-window (0-531 ms) mean band power, stimulus-pooled minus omission-pooled,
    per area x band (50 tests, 10 areas x 5 bands), corrected together as one family.

OUTPUT
    context/figures/fig04_v1_pfc_condition_tfr/svg/fig04_supp_slotpooled_<area>.svg/.png
    context/figures/fig04_v1_pfc_condition_tfr/svg/fig04_supp_slotpooled_stats.csv/.md
    context/figures/fig04_v1_pfc_condition_tfr/svg/fig04_supp_slotpooled.receipt.json
"""
from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.ticker
import matplotlib.pyplot as plt
import numpy as np

_FIG_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_FIG_DIR)
sys.path.insert(0, os.path.join(_ROOT, "context", "figures"))
sys.path.insert(0, _ROOT)

from figstats import paired_location, write
from figstyle import AREA_ORDER

FIG04_DIR = os.path.join(_ROOT, "context", "figures", "fig04_v1_pfc_condition_tfr")
sys.path.insert(0, FIG04_DIR)
import fig04_v1_pfc_condition_tfr as fig04  # noqa: E402
from jnwb import paths as _P

OMISSION_MAPS = _P.REPO_ROOT / "outputs/omission_tfr_maps_w1500/maps.npz"
STIMULUS_MAPS = _P.REPO_ROOT / "outputs/stimulus_pooled_tfr_maps_w1500/maps.npz"
OUT_SVG_DIR = os.path.join(FIG04_DIR, "svg")

BANDS = fig04.BANDSETS["manuscript"]
BAND_COLORS = fig04.BAND_COLORS
WIN = fig04.WIN                       # (-1500, 1500)
PREV_STIM = fig04.PREV_STIM
OMISSION_SPAN = fig04.OMISSION        # (0, 531): the omitted / matched-stimulus slot itself
NEXT_STIM = fig04.NEXT_STIM
SLOT4_END = fig04.SLOT4_END
COVERAGE_MIN = fig04.COVERAGE_MIN
OMITTED_WINDOW = (0, 531)             # the window used for the headline stat, matches OMISSION
# Areas with 2 sessions (FST) are still plotted, matching the precedent set by
# build_area_condition_supplements() in fig04_v1_pfc_condition_tfr.py ("FST has only 2
# sessions; read its panels as illustrative, not a population estimate") -- flagged on the
# panel itself, not silently dropped. The paired stats below keep their own n>=3 floor.
MIN_SESSIONS = 2


def load_with_counts(path):
    """Same convention as fig04.load()/load_condition_maps(), but for the session|area|layer
    (no cond dimension) key scheme both slot-pooled datasets use."""
    z = np.load(path, allow_pickle=True)
    keys = [str(k) for k in z["keys"]]
    sums, counts, freqs, times = z["sums"], z["counts"], z["freqs"], z["times"]
    maps, count_maps = {}, {}
    for i, k in enumerate(keys):
        with np.errstate(invalid="ignore", divide="ignore"):
            m = np.where(counts[i] > 0, sums[i] / np.maximum(counts[i], 1), np.nan)
        per_bin = np.nanmax(counts[i], axis=0)
        mx = np.nanmax(per_bin) if per_bin.size else 0
        keep = per_bin >= COVERAGE_MIN * mx if mx > 0 else per_bin > 0
        m[:, ~keep] = np.nan
        c = counts[i].copy()
        c[:, ~keep] = 0.0
        maps[k] = m
        count_maps[k] = c
    return maps, count_maps, freqs, times


def area_sessions(maps, area, layer="all"):
    return {k.split("|")[0]: m for k, m in maps.items()
            if k.split("|")[1] == area and k.split("|")[2] == layer}


def draw_spectrogram(ax, area, label, sess, freqs, times, vlim, bottom):
    sess, dropped = fig04.drop_outlier_sessions(sess)
    grand = fig04.to_db(np.nanmean(np.stack(list(sess.values())), axis=0))
    im = ax.pcolormesh(times, freqs, grand, cmap="viridis", shading="nearest",
                       vmin=vlim[0], vmax=vlim[1])
    for e in sorted({e for v in BANDS.values() for e in v if e <= freqs[-1]}):
        ax.axhline(e, color="red", lw=0.7, alpha=0.85)
    ax.axvline(0, color="green", ls="--", lw=1.4)
    ax.axvline(SLOT4_END, color="0.25", ls=":", lw=1.0)
    ax.axvspan(*PREV_STIM, color="#F8C6C6", alpha=0.40, zorder=0)
    ax.axvspan(*OMISSION_SPAN, color="#E7D3F0", alpha=0.50, zorder=0)
    ax.axvspan(NEXT_STIM[0], min(NEXT_STIM[1], WIN[1]), color="#F8C6C6", alpha=0.20, zorder=0)
    ax.set_xlim(*WIN)
    ax.set_yscale("log")
    ax.set_ylim(freqs[0], freqs[-1])
    ax.set_yticks([4, 8, 14, 30, 50, 80, 150])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_title(f"{label}  n={len(sess)} sessions", fontsize=9)
    ax.tick_params(labelsize=7, labelbottom=False)
    if dropped:
        ax.text(0.01, 1.10, f"{len(dropped)} session(s) excluded (out of scale)",
               transform=ax.transAxes, fontsize=6, color="0.35", va="bottom")
    cb = plt.colorbar(im, ax=ax, pad=0.012, fraction=0.030)
    cb.set_label("dB", fontsize=7, rotation=270, labelpad=10)
    cb.ax.tick_params(labelsize=7)
    return len(sess)


def draw_trace(ax, label, sess, counts_sess, freqs, times, bottom):
    sess, dropped = fig04.drop_outlier_sessions(sess)
    counts_sess = {k: v for k, v in counts_sess.items() if k in sess}
    for (name, (lo, hi)), col in zip(BANDS.items(), BAND_COLORS):
        mu, sem = fig04.weighted_band_mean_sem(sess, counts_sess, freqs, lo, hi)
        ax.plot(times, fig04.to_db(mu), color=col, lw=1.6, label=name, zorder=3)
        ax.fill_between(times, fig04.to_db(np.maximum(mu - sem, 1e-12)), fig04.to_db(mu + sem),
                        color=col, alpha=0.28, lw=0, zorder=2)
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(0, color="green", ls="--", lw=1.4)
    ax.axvline(SLOT4_END, color="0.25", ls=":", lw=1.0)
    ax.axvspan(*PREV_STIM, color="#F8C6C6", alpha=0.40, zorder=0)
    ax.axvspan(*OMISSION_SPAN, color="#E7D3F0", alpha=0.50, zorder=0)
    ax.axvspan(NEXT_STIM[0], min(NEXT_STIM[1], WIN[1]), color="#F8C6C6", alpha=0.20, zorder=0)
    ax.set_xlim(*WIN)
    ax.set_ylabel("Power change (dB)", fontsize=9)
    ax.set_title(label, fontsize=9)
    ax.tick_params(labelsize=7)
    ax.set_xticks([-1500, -1000, -500, 0, 500, 1000, 1500])
    if bottom:
        ax.set_xticklabels(["-1500", "-1000", "-500", "0", "+500", "+1000", "+1500"],
                           color="green", fontsize=9)
        ax.set_xlabel("Time from omitted / matched-stimulus slot onset (ms)", color="green",
                      fontsize=10)
    else:
        ax.tick_params(labelbottom=False)


def build_area_panel(area, om_maps, om_counts, st_maps, st_counts, freqs, times, vlim):
    om_sess = area_sessions(om_maps, area)
    st_sess = area_sessions(st_maps, area)
    om_counts_sess = {k.split("|")[0]: v for k, v in om_counts.items()
                      if k.split("|")[1] == area and k.split("|")[2] == "all"}
    st_counts_sess = {k.split("|")[0]: v for k, v in st_counts.items()
                      if k.split("|")[1] == area and k.split("|")[2] == "all"}
    if len(om_sess) < MIN_SESSIONS or len(st_sess) < MIN_SESSIONS:
        return None
    illustrative = len(om_sess) < 3 or len(st_sess) < 3

    fig = plt.figure(figsize=(11.5, 7.2))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.35, 1.0], hspace=0.32, wspace=0.30,
                          left=0.075, right=0.93, top=0.87 if illustrative else 0.90,
                          bottom=0.10)
    ax_om_spec = fig.add_subplot(gs[0, 0])
    ax_st_spec = fig.add_subplot(gs[0, 1])
    ax_om_tr = fig.add_subplot(gs[1, 0])
    ax_st_tr = fig.add_subplot(gs[1, 1], sharey=ax_om_tr)

    n_om = draw_spectrogram(ax_om_spec, area, f"{area}, omission-pooled (9 slot conditions)",
                            om_sess, freqs, times, vlim, False)
    n_st = draw_spectrogram(ax_st_spec, area, f"{area}, stimulus-pooled (9 matched slots)",
                            st_sess, freqs, times, vlim, False)
    draw_trace(ax_om_tr, "Omission-pooled", om_sess, om_counts_sess, freqs, times, True)
    draw_trace(ax_st_tr, "Stimulus-pooled", st_sess, st_counts_sess, freqs, times, True)
    ax_st_tr.tick_params(labelleft=False)
    ax_st_tr.set_ylabel("")
    leg = ax_om_tr.legend(fontsize=7, loc="upper right", framealpha=0.9, fancybox=False)
    leg.get_frame().set_edgecolor("black")

    title = (f"{area} — slot-pooled omission vs. matched real stimulus, power change from "
             f"each channel's own -250..-50 ms pre-onset baseline")
    if illustrative:
        title += f"\n[n={min(n_om, n_st)} sessions -- illustrative, not a population estimate]"
    fig.suptitle(title, fontsize=11)
    stem = os.path.join(OUT_SVG_DIR, f"fig04_supp_slotpooled_{area.replace('/', '')}")
    fig.savefig(stem + ".svg")
    fig.savefig(stem + ".png", dpi=170)
    plt.close(fig)
    return {"area": area, "n_sessions_omission": n_om, "n_sessions_stimulus": n_st}


def omitted_window_band_stats(om_maps, st_maps, freqs, times):
    tmask = (times >= OMITTED_WINDOW[0]) & (times < OMITTED_WINDOW[1])
    results = []
    for area in AREA_ORDER:
        om_sess = area_sessions(om_maps, area)
        st_sess = area_sessions(st_maps, area)
        common = sorted(set(om_sess) & set(st_sess))
        if len(common) < 3:
            continue
        for band, (lo, hi) in BANDS.items():
            om_vals, st_vals = [], []
            for s in common:
                ro = fig04.band_ratio(om_sess[s], freqs, lo, hi)[tmask]
                rs = fig04.band_ratio(st_sess[s], freqs, lo, hi)[tmask]
                if np.any(np.isfinite(ro)) and np.any(np.isfinite(rs)):
                    om_vals.append(fig04.to_db(np.nanmean(ro)))
                    st_vals.append(fig04.to_db(np.nanmean(rs)))
            results.append(paired_location(
                st_vals, om_vals,  # stimulus - omission: positive means real stimulus drives more power
                figure="fig04_supp_slotpooled", panel="omitted_window", question=f"{area} {band} stimulus vs omission (slot-pooled, 0-531ms)",
                unit="session", family="fig04_supp_slotpooled",
                note=f"n={len(common)} sessions with both pooled datasets"))
    return results


def main():
    os.makedirs(OUT_SVG_DIR, exist_ok=True)
    om_maps, om_counts, freqs, times = load_with_counts(OMISSION_MAPS)
    st_maps, st_counts, freqs2, times2 = load_with_counts(STIMULUS_MAPS)
    assert np.array_equal(freqs, freqs2) and np.array_equal(times, times2), \
        "omission and stimulus-pooled maps must share the same freq/time axes"

    present = [a for a in AREA_ORDER
              if len(area_sessions(om_maps, a)) >= MIN_SESSIONS
              and len(area_sessions(st_maps, a)) >= MIN_SESSIONS]
    allv = []
    for a in present:
        for maps_ in (om_maps, st_maps):
            sess, _ = fig04.drop_outlier_sessions(area_sessions(maps_, a))
            allv.append(fig04.to_db(np.nanmean(np.stack(list(sess.values())), axis=0)))
    lim = float(np.nanpercentile(np.abs(np.concatenate([v.ravel() for v in allv])), 99))
    vlim = (-round(lim, 1), round(lim, 1))

    made = []
    for area in present:
        r = build_area_panel(area, om_maps, om_counts, st_maps, st_counts, freqs, times, vlim)
        if r:
            made.append(r)

    results = omitted_window_band_stats(om_maps, st_maps, freqs, times)
    write(results, OUT_SVG_DIR, "fig04_supp_slotpooled",
         "Fig 4 supplement: slot-pooled omission vs. matched real-stimulus band power",
         preamble="Paired-by-session (Wilcoxon or paired t, chosen by Shapiro-Wilk on the "
                  "differences) test of the omitted/matched-stimulus-slot window (0-531 ms) "
                  "mean band power, stimulus-pooled minus omission-pooled, per area x band. "
                  "Family = all area x band pairs with >=3 common sessions, corrected together.")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "omission_maps": OMISSION_MAPS, "stimulus_maps": STIMULUS_MAPS,
        "areas_plotted": [m["area"] for m in made],
        "sessions_per_area": made,
        "colour_scale_db": list(vlim),
        "colour_scale_rule": "common across all areas and both sides, symmetric, 99th "
                            "percentile of |dB|",
        "trace_sem": "precision-weighted across sessions via "
                    "fig04_v1_pfc_condition_tfr.weighted_band_mean_sem (Kish effective n)",
        "stats_family": "fig04_supp_slotpooled", "stats_rows": len(results),
        "window_used_for_stats_ms": list(OMITTED_WINDOW),
        "env": {"python": platform.python_version(), "numpy": np.__version__,
               "matplotlib": matplotlib.__version__, "platform": platform.platform()},
    }
    with open(os.path.join(OUT_SVG_DIR, "fig04_supp_slotpooled.receipt.json"), "w",
             encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"areas plotted: {[m['area'] for m in made]}")
    print(f"colour scale: {vlim} dB")
    print(f"stats rows: {len(results)}")
    print(f"WROTE {OUT_SVG_DIR}/fig04_supp_slotpooled_*.svg/.png, stats, receipt")


if __name__ == "__main__":
    main()
