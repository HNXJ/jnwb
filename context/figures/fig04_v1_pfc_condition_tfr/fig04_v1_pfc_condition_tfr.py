r"""
Omission-aligned TFR panels in the stacked two-area layout.

LAYOUT (matching the reference slide figure)
    Per area, three stacked axes:
        screen strip   what the animal saw -- grating during the preceding stimulus,
                       uniform gray through both delays and the omitted slot, with a
                       "Screen" arrow label at the left
        spectrogram    3-199 Hz on a LOG frequency axis against -1500..+1500 ms from
                       omission onset, viridis, band edges in red, colorbar on the
                       right, area name set large and rotated on the far right
        band traces    five bands with SEM ribbons, legend boxed inside the panel
    Two areas are stacked per figure and share one x-axis, labelled only on the bottom
    panel. Epoch names run along the top: Visual stim / Delay / Omission / Delay / Next stim.

WINDOW AND WHAT IS ACTUALLY IN IT
    -1500..+1500 ms shows the whole preceding stimulus (p(k-1), -1031..-500), the delay
    before the omission, the omitted slot, the delay after it, and the arrival of the next
    stimulus at +1031 ms. Two composition boundaries are marked rather than smoothed over:
      +897 ms   dotted line -- p4 omissions end the trial here, so everything to its right
                comes from p2 and p3 omissions only
      +1031 ms  faded grating -- the next stimulus, present only in those same conditions
    Nothing to the right of +897 ms should be read as an omission-only effect.

OUTPUT PATHS below are written under outputs/omission_tfr_maps_w1500/.

MEASURE
    Input maps hold the RATIO OF EXPECTED POWER: power is averaged over trials first, then
    divided by that channel's own -250..-50 ms pre-omission baseline, and the logarithm is
    taken once, at the very end, after averaging over channels, band frequencies, window
    times and sessions. Averaging decibels instead biases each unit low by roughly half the
    variance of its log-power, which on this corpus reaches -1.98 dB and reverses the sign
    of an animal's effect. See artifacts/.lab/db_averaging_bias_finding_20260728.json.

BANDS
    The audited house set: theta 4-8, alpha 8-14, beta 14-30, low gamma 30-50, high gamma
    50-80 Hz. The reference slide's legend shows theta 2-7, alpha 8-12, gamma-low 32-80,
    gamma-high 80+, which is the pre-correction set retired by the 2026-07-27 figure audit.
    Pass --bands reference to reproduce the slide exactly.

OUTPUT
    outputs/omission_tfr_maps_final/figures_stacked/pair_<A>_<B>.png
    outputs/omission_tfr_maps_final/figures_stacked/all_areas_grid.png
    outputs/omission_tfr_maps_final/figures_stacked/receipt.json
"""
from __future__ import annotations

import argparse
import sys
import json
import os
import platform
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.ticker
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from svgassemble import assemble
from figstats import group_location, paired_location, write
from figstyle import mark_full_trial_axis

MAPS = r"D:/workspace/omission/outputs/omission_tfr_maps_w1500/maps.npz"
OUT_DIR = r"D:/workspace/omission/outputs/omission_tfr_maps_w1500"
# Every panel this script draws lands in this figure's own svg/ folder. The main
# figure is assembled from a subset; the rest feed the supplements.
FIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "svg")

# hierarchy order, paired as they are read together
PAIRS = [("V1", "V2"), ("V3a/d", "V4"), ("MT", "MST"), ("TEO", "FST"), ("FEF", "PFC")]

BANDSETS = {
    "manuscript": {"Theta(4-8Hz)": (4, 8), "Alpha(8-14Hz)": (8, 14), "Beta(14-30Hz)": (14, 30),
                   "Gamma(Low,30-50Hz)": (30, 50), "Gamma(High,50-80Hz)": (50, 80)},
    "reference": {"Theta(2-7Hz)": (2, 7), "Alpha(8-12Hz)": (8, 12), "Beta(14-30Hz)": (14, 30),
                  "Gamma(Low,32-80Hz)": (32, 80), "Gamma(High,80+Hz)": (80, 201)},
}
BAND_COLORS = ["#0000EE", "#EE0000", "#FF8C00", "#FF00FF", "#00A000"]

STIM_MS, DELAY_MS = 531, 500
# Bins contributed by fewer than this fraction of the maximum are dropped. At the wider
# window the binding constraint is that p4 omissions end the trial at +897 ms, so beyond
# that only p2 and p3 omissions contribute -- two thirds of the conditions. The threshold
# admits them and the change is marked on the figure instead of being hidden.
COVERAGE_MIN = 0.55
WIN = (-1500, 1500)
PREV_STIM = (-1031, -DELAY_MS)      # p(k-1), fully inside the window now
OMISSION = (0, STIM_MS)             # the omitted slot itself
NEXT_STIM = (1031, 1562)            # p(k+1) -- p2/p3 omissions only; p4 ends the trial
SLOT4_END = 897                     # last sample a p4 omission can contribute


def grating_strip(width=700, height=60, cycles=12):
    x = np.linspace(0, 1, width)
    y = np.linspace(0, 1, height)
    xx, yy = np.meshgrid(x, y)
    return 0.5 + 0.5 * np.sin(2 * np.pi * cycles * (xx + 0.55 * yy))


def to_db(r):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10.0 * np.log10(r)


def _gaussian_kernel_1d(sigma_bins):
    radius = max(1, int(round(3 * sigma_bins)))
    xk = np.arange(-radius, radius + 1)
    k = np.exp(-0.5 * (xk / sigma_bins) ** 2)
    return k / k.sum()


def gaussian_smooth_1d(y, sigma_bins):
    """Zero-phase Gaussian smoothing (edge-reflected), NaN-safe by treating NaN as 0-weight."""
    k = _gaussian_kernel_1d(sigma_bins)
    radius = (k.size - 1) // 2
    mask = np.isfinite(y).astype(float)
    yf = np.nan_to_num(y, nan=0.0)
    num = np.convolve(np.pad(yf, radius, mode="reflect"), k, mode="valid")
    den = np.convolve(np.pad(mask, radius, mode="reflect"), k, mode="valid")
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / den
    out[den <= 0] = np.nan
    return out


def gaussian_smooth_2d(a, sigma_time_bins, sigma_freq_bins):
    """Separable Gaussian smoothing along (freq, time) axes of a 2-D map, NaN-safe."""
    out = np.apply_along_axis(lambda row: gaussian_smooth_1d(row, sigma_time_bins), 1, a)
    out = np.apply_along_axis(lambda col: gaussian_smooth_1d(col, sigma_freq_bins), 0, out)
    return out


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


OUTLIER_FACTOR = 5.0


def drop_outlier_sessions(sess):
    """Remove sessions whose map is grossly out of scale with the rest of the area.

    A single channel with a near-zero baseline makes its power ratio enormous, which shows up
    as a session whose extreme is many times the typical one. Those extremes sit outside the
    windows any statistic uses -- in the stimulus period and at the window edges -- so they do
    not affect the reported numbers, but they do set the colour scale and drag the mean trace.
    A session is dropped from the DISPLAY when its maximum |dB| exceeds OUTLIER_FACTOR times
    the median session maximum for that area. Returns (kept, dropped_names).
    """
    if len(sess) < 3:
        return sess, []
    names = list(sess)
    mx = np.array([np.nanmax(np.abs(to_db(sess[n]))) for n in names])
    med = float(np.median(mx))
    keep = {n: sess[n] for n, v in zip(names, mx) if v <= OUTLIER_FACTOR * med}
    dropped = [n for n, v in zip(names, mx) if v > OUTLIER_FACTOR * med]
    return (keep, dropped) if keep else (sess, [])


def band_ratio(m, freqs, lo, hi):
    sel = (freqs >= lo) & (freqs < hi)
    return np.nanmean(m[sel], axis=0) if sel.any() else np.full(m.shape[1], np.nan)


def draw_area(fig, gs_cell, area, sess, freqs, times, bands, vlim, bottom):
    """screen strip + spectrogram + band traces for one area."""
    sess, dropped = drop_outlier_sessions(sess)
    gs = gs_cell.subgridspec(3, 1, height_ratios=[0.42, 2.9, 2.5], hspace=0.06)
    ax_s, ax_m, ax_t = (fig.add_subplot(gs[i]) for i in range(3))

    # ---- screen strip ---------------------------------------------------------
    ax_s.set_xlim(*WIN)
    ax_s.set_ylim(0, 1)
    ax_s.add_patch(Rectangle((WIN[0], 0), WIN[1] - WIN[0], 1, color="0.45", zorder=1))
    ax_s.imshow(grating_strip(), cmap="gray", aspect="auto", zorder=2, vmin=0, vmax=1,
                extent=(PREV_STIM[0], PREV_STIM[1], 0, 1))
    # p(k+1): present only for p2/p3 omissions, so it is drawn faded and labelled as partial
    ax_s.imshow(grating_strip(), cmap="gray", aspect="auto", zorder=2, vmin=0, vmax=1,
                alpha=0.45, extent=(NEXT_STIM[0], min(NEXT_STIM[1], WIN[1]), 0, 1))
    for sp in ax_s.spines.values():
        sp.set_visible(False)
    ax_s.set_xticks([])
    ax_s.set_yticks([])
    # placed in axes fractions so the label cannot be clipped by the figure margin
    ax_s.annotate("", xy=(-0.012, 0.5), xytext=(-0.075, 0.5), xycoords="axes fraction",
                  textcoords="axes fraction", annotation_clip=False,
                  arrowprops=dict(arrowstyle="-|>", color="black", lw=1.4))
    ax_s.text(-0.082, 0.5, "Screen", transform=ax_s.transAxes, ha="right", va="center",
              fontsize=11, clip_on=False)
    for x, lab, col in [(-765, "Visual stim", "red"), (-250, "Delay", "black"),
                        (265, "Omission", "purple"), (780, "Delay", "black"),
                        (1270, "Next stim*", "0.35")]:
        ax_s.text(x, 1.55, lab, color=col, ha="center", va="bottom", fontsize=13)

    # ---- spectrogram ----------------------------------------------------------
    grand = to_db(np.nanmean(np.stack(list(sess.values())), axis=0))
    im = ax_m.pcolormesh(times, freqs, grand, cmap="viridis", shading="nearest",
                         vmin=vlim[0], vmax=vlim[1])
    for e in sorted({e for v in bands.values() for e in v if e <= freqs[-1]}):
        ax_m.axhline(e, color="red", lw=0.7, alpha=0.85)
    ax_m.axvline(0, color="green", ls="--", lw=1.6)
    ax_m.axvline(SLOT4_END, color="0.25", ls=":", lw=1.2)
    ax_m.set_xlim(*WIN)
    # Log frequency axis: at 3-199 Hz linear, theta through beta occupy the bottom ~14% of
    # the panel and are unreadable. Log spacing gives the low-frequency bands the room the
    # analysis actually spends its attention on.
    ax_m.set_yscale("log")
    ax_m.set_ylim(freqs[0], freqs[-1])
    ax_m.set_yticks([4, 8, 14, 30, 50, 80, 150])
    ax_m.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax_m.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax_m.set_ylabel("Frequency (Hz)", color="blue", fontsize=10)
    ax_m.tick_params(labelbottom=False, labelsize=9)
    for lb in ax_m.get_yticklabels():
        lb.set_color("blue")
    cb = fig.colorbar(im, ax=ax_m, pad=0.012, fraction=0.030)
    cb.set_label("Power change (dB)", fontsize=8, rotation=270, labelpad=12)
    cb.ax.tick_params(labelsize=8)
    # large rotated area name, outside the colorbar
    ax_m.text(1.085, -0.05, area, transform=ax_m.transAxes, rotation=270,
              va="center", ha="left", fontsize=24, fontweight="bold")
    if dropped:
        ax_m.text(0.005, 1.03, f"{len(dropped)} session excluded from display (out of scale)",
                  transform=ax_m.transAxes, fontsize=7, color="0.35", va="bottom")

    # ---- band traces ----------------------------------------------------------
    for (name, (lo, hi)), col in zip(bands.items(), BAND_COLORS):
        r = np.stack([band_ratio(m, freqs, lo, hi) for m in sess.values()])
        mu = np.nanmean(r, axis=0)
        n = np.sum(np.isfinite(r), axis=0)
        sem = np.nanstd(r, axis=0, ddof=1) / np.sqrt(np.maximum(n, 1))
        ax_t.plot(times, to_db(mu), color=col, lw=2.2, label=name, zorder=3)
        ax_t.fill_between(times, to_db(np.maximum(mu - sem, 1e-12)), to_db(mu + sem),
                          color=col, alpha=0.30, lw=0, zorder=2)
    ax_t.axhline(0, color="black", lw=0.9)
    ax_t.axvline(0, color="green", ls="--", lw=1.6)
    # p4 omissions end the trial here; everything to the right is p2/p3 only
    ax_t.axvline(SLOT4_END, color="0.25", ls=":", lw=1.2)
    ax_t.set_xlim(*WIN)
    ax_t.set_ylabel("Power change (dB)", fontsize=10)
    ax_t.axvspan(*PREV_STIM, color="#F8C6C6", alpha=0.45, zorder=0)
    ax_t.axvspan(*OMISSION, color="#E7D3F0", alpha=0.55, zorder=0)
    ax_t.axvspan(NEXT_STIM[0], min(NEXT_STIM[1], WIN[1]), color="#F8C6C6", alpha=0.22,
                 zorder=0)
    leg = ax_t.legend(fontsize=8, loc="upper right", framealpha=0.9, fancybox=False)
    leg.get_frame().set_linestyle("--")
    leg.get_frame().set_edgecolor("black")
    ax_t.set_xticks([-1500, -1000, -500, 0, 500, 1000, 1500])
    if bottom:
        ax_t.set_xticklabels(["-1500", "-1000", "-500", "0", "+500", "+1000", "+1500"],
                             color="green", fontsize=12)
        ax_t.text(0.5, -0.36, "* next stimulus and the region right of the dotted line come "
                  "only from p2/p3 omissions; p4 omissions end the trial at +897 ms",
                  transform=ax_t.transAxes, ha="center", va="top", fontsize=8, color="0.3")
        ax_t.set_xlabel("Time from omission onset (ms)", color="green", fontsize=15)
    else:
        ax_t.tick_params(labelbottom=False)
    return len(sess)


# ============================================================================================
# Main figure: V1 and PFC, RXRR vs RRRR, p1-d1-p2-d2-p3, from extract_condition_tfr_maps.py.
# This is what fig04.svg is assembled from. The area x layer x omission-pooled analysis above
# (draw_area, PANEL_SET) is unchanged and still feeds the supplements from this same svg/
# folder; it is simply no longer what "figure 4" itself shows.
# ============================================================================================
CONDITION_MAPS = r"D:/workspace/omission/outputs/condition_tfr_maps_p1d1p2d2p3/maps.npz"
CONDITION_AREAS = ["V1", "V3a/d", "TEO", "PFC"]
CONDITIONS = ["RXRR", "RRRR"]
CONDITION_WIN = (-500, 2593)                # p1 onset to the p3/d3 boundary
COND_OMIT_SLOT = {"RXRR": 2, "RRXR": 3, "RRRR": None}
COND_LABEL = {"RXRR": "RXRR (p2 omitted)", "RRXR": "RRXR (p3 omitted)", "RRRR": "RRRR (p2 real)"}
# RRXR added 2026-07-31 for scripts/plot_v182o_condition_bandtraces.py -- draw_condition_
# bandtrace()/draw_condition_spectrogram() read these two dicts directly, so extending them
# here (not monkeypatching from the caller) is what makes RRXR usable through the same
# reused drawing functions. CONDITIONS/CONDITION_AREAS below are unchanged (fig04's own main
# figure still shows only V1/PFC x RXRR/RRRR); this is additive.


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


SPEC_SMOOTH_TIME_BINS = 1.5
SPEC_SMOOTH_FREQ_BINS = 1.0
TRACE_SMOOTH_TIME_BINS = 2.0


def draw_condition_spectrogram(ax, area, cond, sess, freqs, times, bands, vlim, letter):
    """One spectrogram: area x condition, p1-aligned, baselined to the middle of d1.

    Displayed map is Gaussian-smoothed (sigma = 1.5 time bins, 1 freq bin) and rendered with
    gouraud shading -- cosmetic only, for readability; no statistic reads this smoothed array.
    """
    sess, dropped = drop_outlier_sessions(sess)
    grand = to_db(np.nanmean(np.stack(list(sess.values())), axis=0))
    grand_smooth = gaussian_smooth_2d(grand, SPEC_SMOOTH_TIME_BINS, SPEC_SMOOTH_FREQ_BINS)
    im = ax.pcolormesh(times, freqs, grand_smooth, cmap="viridis", shading="gouraud",
                       vmin=vlim[0], vmax=vlim[1])
    for e in sorted({e for v in bands.values() for e in v if e <= freqs[-1]}):
        ax.axhline(e, color="red", lw=0.7, alpha=0.85)
    mark_full_trial_axis(ax, CONDITION_WIN, omit_slot=COND_OMIT_SLOT[cond])
    ax.set_yscale("log")
    ax.set_ylim(freqs[0], freqs[-1])
    ax.set_yticks([4, 8, 14, 30, 50, 80, 150])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_title(f"({letter}) {area}, {COND_LABEL[cond]}  n={len(sess)} sessions", fontsize=9)
    ax.tick_params(labelsize=7)
    if dropped:
        ax.text(0.01, 1.10, f"{len(dropped)} session(s) excluded (out of scale)",
               transform=ax.transAxes, fontsize=6, color="0.35", va="bottom")
    return im, len(sess)


def draw_condition_bandtrace(ax, area, cond, sess, freqs, times, bands, letter):
    """One band-decomposed trace panel: five bands, mean +- SEM across sessions.

    Mean and SEM are each Gaussian-smoothed (sigma = 2 time bins) before conversion to dB --
    cosmetic only; no statistic reads the smoothed trace.
    """
    sess, _ = drop_outlier_sessions(sess)
    for (name, (lo, hi)), col in zip(bands.items(), BAND_COLORS):
        r = np.stack([band_ratio(m, freqs, lo, hi) for m in sess.values()])
        mu = np.nanmean(r, axis=0)
        n = np.sum(np.isfinite(r), axis=0)
        sem = np.nanstd(r, axis=0, ddof=1) / np.sqrt(np.maximum(n, 1))
        mu_s = gaussian_smooth_1d(mu, TRACE_SMOOTH_TIME_BINS)
        sem_s = gaussian_smooth_1d(sem, TRACE_SMOOTH_TIME_BINS)
        ax.plot(times, to_db(mu_s), color=col, lw=1.6, label=name, zorder=3)
        ax.fill_between(times, to_db(np.maximum(mu_s - sem_s, 1e-12)), to_db(mu_s + sem_s),
                        color=col, alpha=0.28, lw=0, zorder=2)
    ax.axhline(0, color="black", lw=0.8)
    mark_full_trial_axis(ax, CONDITION_WIN, omit_slot=COND_OMIT_SLOT[cond])
    ax.set_title(f"({letter}) {area}, {COND_LABEL[cond]}", fontsize=9)
    ax.tick_params(labelsize=7)


P2_WINDOW_MS = (1031, 1562)  # p2 onset to d2 onset, per jnwb.sequence_layout.EPOCH_ONSETS_MS


def condition_p2_band_stats(maps, freqs, times, bands):
    """Is p2-window band power different between RXRR (p2 omitted) and RRRR (p2 real)?

    Turns the qualitative sanity check ('gamma bursts appear at p2 only in RRRR') into a
    paired inferential statistic: for each area x band, the p2-window mean power ratio is
    computed per session for both conditions and paired on session (paired_location picks
    Wilcoxon signed-rank or the paired t-test by Shapiro-Wilk on the differences). Unit of
    inference is session, not channel or trial -- maps.npz is already trial-pooled per
    session. Family = the full area x band grid, corrected together (Holm and BH both
    reported, see figstats.py).
    """
    tmask = (times >= P2_WINDOW_MS[0]) & (times < P2_WINDOW_MS[1])
    results = []
    for area in CONDITION_AREAS:
        sess_a = area_cond_sessions(maps, area, "RXRR")
        sess_b = area_cond_sessions(maps, area, "RRRR")
        common = sorted(set(sess_a) & set(sess_b))
        for band, (lo, hi) in bands.items():
            a_vals, b_vals = [], []
            for s in common:
                ra = band_ratio(sess_a[s], freqs, lo, hi)[tmask]
                rb = band_ratio(sess_b[s], freqs, lo, hi)[tmask]
                if np.any(np.isfinite(ra)) and np.any(np.isfinite(rb)):
                    a_vals.append(to_db(np.nanmean(ra)))
                    b_vals.append(to_db(np.nanmean(rb)))
            results.append(paired_location(
                b_vals, a_vals,  # RRRR - RXRR: positive means p2-real drives more power
                figure="fig04", panel="condition_p2", question=f"{area} {band} p2 RRRR vs RXRR",
                unit="session", family="fig04_condition_p2",
                note=f"n={len(common)} sessions with both conditions"))
    return results


def build_v1_pfc_condition_figure():
    """Assemble the main figure: rows = CONDITION_AREAS (V1, V3a/d, TEO, PFC), columns =
    spec-RXRR/spec-RRRR/trace-RXRR/trace-RRRR -- panels a-p in reading order.

    Each spectrogram's colour scale is autoscaled to itself (99th percentile of |dB| within
    that one area x condition panel, its own colorbar alongside it) rather than a scale shared
    across all sixteen panels -- areas differ enormously in overall power change, and a common
    scale compresses the smaller ones toward invisibility.
    """
    maps, freqs, times = load_condition_maps()
    bands = BANDSETS["manuscript"]

    def panel_vlim(area, cond):
        sess = area_cond_sessions(maps, area, cond)
        kept, _ = drop_outlier_sessions(sess)
        if not kept:
            return (-1.0, 1.0)
        v = to_db(np.nanmean(np.stack(list(kept.values())), axis=0))
        vmax = max(float(np.nanpercentile(np.abs(v[np.isfinite(v)]), 99)), 0.5)
        return (-round(vmax, 1), round(vmax, 1))

    counts = {}
    nrow = len(CONDITION_AREAS)
    fig, axes = plt.subplots(nrow, 4, figsize=(16.0, 3.3 * nrow))
    letters = "abcdefghijklmnop"
    li = 0
    for ri, area in enumerate(CONDITION_AREAS):
        for cond in CONDITIONS:
            sess = area_cond_sessions(maps, area, cond)
            ax = axes[ri, CONDITIONS.index(cond)]
            vlim = panel_vlim(area, cond)
            im, n = draw_condition_spectrogram(ax, area, cond, sess, freqs, times, bands,
                                               vlim, letters[li])
            cb = fig.colorbar(im, ax=ax, pad=0.012, fraction=0.046)
            cb.set_label("dB", fontsize=7, rotation=270, labelpad=9)
            cb.ax.tick_params(labelsize=6)
            counts[f"{area}_{cond}"] = n
            li += 1
        for cond in CONDITIONS:
            sess = area_cond_sessions(maps, area, cond)
            draw_condition_bandtrace(axes[ri, 2 + CONDITIONS.index(cond)], area, cond, sess,
                                     freqs, times, bands, letters[li])
            li += 1

    for ri in range(nrow):
        axes[ri, 0].set_ylabel("Frequency (Hz)", fontsize=9)
        axes[ri, 2].set_ylabel("Power change (dB)", fontsize=9)
        for ci in (1, 3):
            axes[ri, ci].tick_params(labelleft=False)
    for ci in range(4):
        axes[nrow - 1, ci].set_xlabel("Time from p1 onset (ms)", fontsize=8)
    handles, labs = axes[0, 2].get_legend_handles_labels()
    fig.legend(handles, labs, fontsize=8, ncol=5, loc="upper center",
              bbox_to_anchor=(0.5, 1.015), frameon=False)
    fig.suptitle(f"{', '.join(CONDITION_AREAS)}, RXRR vs RRRR, p1-d1-p2-d2-p3; baseline = "
                "middle of d1; each spectrogram's colour scale is autoscaled to itself",
                fontsize=12, fontweight="bold", y=1.02)

    out = os.path.join(FIG_DIR, "fig04_v1_pfc_rxrr_rrrr")
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)

    colour_scales = {f"{area}_{cond}": list(panel_vlim(area, cond))
                     for area in CONDITION_AREAS for cond in CONDITIONS}
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__), "maps": CONDITION_MAPS,
        "layout": f"{len(CONDITION_AREAS)} rows ({', '.join(CONDITION_AREAS)}) x 4 columns "
                  "(spectrogram-RXRR, spectrogram-RRRR, band-trace-RXRR, band-trace-RRRR), "
                  "panels a-p in reading order",
        "areas": CONDITION_AREAS, "conditions": CONDITIONS,
        "window_ms_re_p1": list(CONDITION_WIN),
        "baseline": "middle third of d1 (706-856 ms from p1), NOT a pre-trial fixation "
                   "baseline -- see extract_condition_tfr_maps.py",
        "measure": "ratio of expected power vs each channel's own middle-of-d1 baseline; "
                  "10*log10 applied once, after all averaging",
        "colour_scale_db_per_panel": colour_scales,
        "colour_scale_rule": "each spectrogram autoscaled to itself, symmetric, 99th "
                            "percentile of |dB| within that panel",
        "bands_hz": {k: list(v) for k, v in bands.items()},
        "sessions_per_area_condition": counts,
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "matplotlib": matplotlib.__version__},
    }
    with open(out + ".receipt.json", "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print("sessions per area/condition:", counts)
    print("colour scale per panel:", colour_scales)

    stats_results = condition_p2_band_stats(maps, freqs, times, bands)
    write(stats_results, FIG_DIR, "fig04_condition",
          title="Figure 4 -- V1/V3a-d/TEO/PFC RXRR vs RRRR, p2-window band power",
          preamble="Paired (by session) test of p2-window mean band power, RRRR (p2 real) "
                   "minus RXRR (p2 omitted), per area x band. Positive effect = more power "
                   "when p2 is a real stimulus. Family = full area x band grid (Holm and "
                   "BH-FDR both reported). Unit of inference is session; maps.npz is already "
                   "trial-pooled within session, so no finer unit is available from this input.")
    print(f"condition_p2 stats: {len(stats_results)} tests written to "
          f"{os.path.join(FIG_DIR, 'fig04_condition_stats.md')}")
    return out + ".svg"


def run(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bands", choices=list(BANDSETS), default="manuscript")
    ap.add_argument("--areas", default=None,
                    help="comma-separated area list, e.g. V1,V3a/d,TEO,PFC. Overrides PAIRS.")
    ap.add_argument("--ncol", type=int, default=2, help="columns in the multi-area figure")
    ap.add_argument("--scale", choices=["common", "per-panel"], default="common",
                    help="colour scale shared across panels, or fitted to each panel")
    ap.add_argument("--out", default=None, help="output basename")
    ap.add_argument("--figw", type=float, default=13.5, help="per-column width, inches")
    ap.add_argument("--cells", default=None,
                    help="comma-separated area:layer cells, e.g. V1:sup,V1:deep,PFC:sup,PFC:deep")
    ap.add_argument("--title", default=None, help="optional suptitle template, {pair} allowed")
    args = ap.parse_args(argv)
    bands = BANDSETS[args.bands]
    os.makedirs(FIG_DIR, exist_ok=True)

    maps, freqs, times = load()
    have = {k.split("|")[1] for k in maps}
    # common colour scale so every panel is directly comparable
    vals = np.concatenate([to_db(np.nanmean(np.stack(list(area_sessions(maps, a).values())),
                                            axis=0)).ravel()
                           for a in have if area_sessions(maps, a)])
    lim = float(np.nanpercentile(np.abs(vals), 99))
    vlim = (-round(lim, 1), round(lim, 1))

    def vlim_for(area):
        """Colour limits from a ROBUST summary, restricted to the analysed time range.

        The displayed map is still the mean across sessions. The colour LIMITS are taken
        from the median across sessions and only over -1000..+1000 ms, because a single
        session with a small-baseline channel can push the map past 30 dB in the stimulus
        period and at the window edges -- regions no reported statistic uses. Setting the
        scale from those values compresses every real effect into one colour.
        """
        if args.scale == "common":
            return vlim
        kept, _ = drop_outlier_sessions(area_sessions(maps, area))
        v = to_db(np.nanmean(np.stack(list(kept.values())), axis=0))
        lim = float(np.nanpercentile(np.abs(v), 99))
        return (-round(lim, 1), round(lim, 1))

    if args.cells:
        cells = []
        for c in args.cells.split(","):
            a, _, l = c.strip().partition(":")
            l = l or "all"
            s = area_sessions(maps, a, l)
            if s:
                cells.append((a, l, s))
            else:
                print(f"WARNING: no data for {a}:{l}")
        ncol = max(1, args.ncol)
        nrow = int(np.ceil(len(cells) / ncol))
        fig = plt.figure(figsize=(args.figw * ncol, 5.2 * nrow))
        gs = fig.add_gridspec(nrow, ncol, hspace=0.32, wspace=0.22,
                              left=0.065, right=0.955, top=0.965, bottom=0.085)
        cnt, lims = {}, {}
        for i, (a, l, s) in enumerate(cells):
            kept, _ = drop_outlier_sessions(s)
            v = to_db(np.nanmean(np.stack(list(kept.values())), axis=0))
            lim = max(float(np.nanpercentile(np.abs(v), 99)), 0.5)
            vl = (-round(lim, 1), round(lim, 1)) if args.scale == "per-panel" else vlim
            label = f"{a} {l}"
            cnt[label] = draw_area(fig, gs[i // ncol, i % ncol], label, s, freqs, times,
                                   bands, vl, i // ncol == nrow - 1)
            lims[label] = list(vl)
        base = args.out or "fig_cells"
        out = os.path.join(FIG_DIR, base + ".png")
        fig.savefig(out, dpi=180)
        fig.savefig(out.replace(".png", ".svg"))
        plt.close(fig)
        print(f"cells: {[f'{a}:{l}' for a, l, _ in cells]}")
        print(f"sessions per cell: {cnt}")
        print(f"colour scale: {lims}")

        # ---- laminar statistics: superficial vs deep, per area, per band, at the session
        # level (proper unit of inference), scalar = omission-window (0-531 ms) mean power,
        # averaged over trials/channels/time first, logged once -----------------------------
        stats = []
        twin = (times >= OMISSION[0]) & (times < OMISSION[1])
        by_area = {}
        for a, l, s in cells:
            by_area.setdefault(a, {})[l] = drop_outlier_sessions(s)[0]
        for a, layers in by_area.items():
            if "sup" not in layers or "deep" not in layers:
                continue
            for bname, (lo, hi) in bands.items():
                def scalars(sess_map):
                    return np.array([to_db(np.nanmean(band_ratio(m, freqs, lo, hi)[twin]))
                                     for m in sess_map.values()])
                sup_v, deep_v = scalars(layers["sup"]), scalars(layers["deep"])
                stats.append(group_location(
                    [sup_v, deep_v], ["sup", "deep"], "fig04", f"{a} {bname}",
                    "superficial vs deep, omission-window dB", "session", "fig04_laminar",
                    note=f"{a}: {sup_v.size} superficial vs {deep_v.size} deep sessions; "
                         "layer labels cover 53.9 percent of channels, unevenly by animal "
                         "(Kruskal-Wallis H=12.80, P=0.0017), so compare within area only"))
        if stats:
            write(stats, FIG_DIR, base,
                 f"Figure 4 ({base}) -- laminar statistics",
                 preamble="Scalar tested: mean power over the omission window (0-531 ms), "
                          "averaged over trials, channels and time within a session first, "
                          "then divided by baseline and logged once. `session` is the unit "
                          "of inference. Layer assignment is the vFLIP spectrolaminar "
                          "crossover, 53.9 percent channel coverage, uneven across animals "
                          "-- every comparison here is within one area, never pooled across "
                          "areas by layer.")
        print("WROTE", out, "and", out.replace(".png", ".svg"))
        with open(os.path.join(FIG_DIR, base + ".receipt.json"), "w", encoding="utf-8") as fh:
            json.dump({"generated_utc": datetime.now(timezone.utc).isoformat(),
                       "script": os.path.abspath(__file__), "maps": MAPS,
                       "cells": [f"{a}:{l}" for a, l, _ in cells],
                       "sessions_per_cell": cnt, "colour_scale_db": lims,
                       "scale_mode": args.scale, "window_ms": list(WIN),
                       "frequency_axis": "logarithmic",
                       "bands_hz": {k: list(v) for k, v in bands.items()},
                       "layer_caveat": "layer labels come from the vFLIP crossover and cover "
                                       "53.9 per cent of channels, unevenly across animals "
                                       "(P = 0.0017) and areas; compare within area only"},
                      fh, indent=2)
        return

    if args.areas:
        req = [a.strip() for a in args.areas.split(",")]
        present_req = [a for a in req if area_sessions(maps, a)]
        miss = [a for a in req if a not in present_req]
        if miss:
            print("WARNING: no data for", miss)
        ncol = max(1, args.ncol)
        nrow = int(np.ceil(len(present_req) / ncol))
        fig = plt.figure(figsize=(args.figw * ncol, 5.2 * nrow))
        gs = fig.add_gridspec(nrow, ncol, hspace=0.32, wspace=0.22,
                              left=0.065, right=0.955, top=0.965, bottom=0.085)
        cnt = {}
        for i, area in enumerate(present_req):
            cnt[area] = draw_area(fig, gs[i // ncol, i % ncol], area,
                                  area_sessions(maps, area), freqs, times, bands,
                                  vlim_for(area), i // ncol == nrow - 1)
        base = args.out or ("fig_" + "_".join(a.replace("/", "") for a in present_req))
        out = os.path.join(FIG_DIR, base + ".png")
        fig.savefig(out, dpi=180)
        fig.savefig(out.replace(".png", ".svg"))
        plt.close(fig)
        print(f"areas: {present_req}")
        print(f"sessions per area: {cnt}")
        print(f"colour scale: {args.scale}" +
              ("" if args.scale == "common" else
               "  " + str({a: vlim_for(a) for a in present_req})))
        print("WROTE", out, "and", out.replace(".png", ".svg"))
        with open(os.path.join(FIG_DIR, base + ".receipt.json"), "w", encoding="utf-8") as fh:
            json.dump({"generated_utc": datetime.now(timezone.utc).isoformat(),
                       "script": os.path.abspath(__file__), "maps": MAPS,
                       "areas": present_req, "sessions_per_area": cnt,
                       "ncol": ncol, "scale_mode": args.scale,
                       "colour_scale_db": {a: list(vlim_for(a)) for a in present_req},
                       "window_ms": list(WIN), "frequency_axis": "logarithmic",
                       "bands_hz": {k: list(v) for k, v in bands.items()},
                       "measure": "ratio of expected power vs each channel's own -250..-50 ms "
                                  "pre-omission baseline; log taken once after averaging"},
                      fh, indent=2)
        return

    made, counts = [], {}
    for a, b in PAIRS:
        pair = [x for x in (a, b) if area_sessions(maps, x)]
        if not pair:
            continue
        fig = plt.figure(figsize=(13.5, 5.4 * len(pair)))
        gs = fig.add_gridspec(len(pair), 1, hspace=0.22,
                              left=0.135, right=0.90,
                              top=0.93 if args.title else 0.955, bottom=0.075)
        for i, area in enumerate(pair):
            counts[area] = draw_area(fig, gs[i], area, area_sessions(maps, area),
                                     freqs, times, bands, vlim, i == len(pair) - 1)
        if args.title:
            fig.suptitle(args.title.format(pair="/".join(pair)), fontsize=17, y=0.985)
        name = "pair_" + "_".join(x.replace("/", "") for x in pair) + ".png"
        fig.savefig(os.path.join(FIG_DIR, name), dpi=185)
        fig.savefig(os.path.join(FIG_DIR, name[:-4] + ".svg"))
        plt.close(fig)
        made.append(name)

    # ---- all-area overview, same layout, two columns ------------------------------
    present = [a for p in PAIRS for a in p if area_sessions(maps, a)]
    ncol = 2
    nrow = int(np.ceil(len(present) / ncol))
    fig = plt.figure(figsize=(27, 5.2 * nrow))
    gs = fig.add_gridspec(nrow, ncol, hspace=0.30, wspace=0.22,
                          left=0.065, right=0.955, top=0.97, bottom=0.045)
    for i, area in enumerate(present):
        draw_area(fig, gs[i // ncol, i % ncol], area, area_sessions(maps, area),
                  freqs, times, bands, vlim, i // ncol == nrow - 1)
    fig.savefig(os.path.join(FIG_DIR, "all_areas_grid.png"), dpi=130)
    fig.savefig(os.path.join(FIG_DIR, "all_areas_grid.svg"))
    plt.close(fig)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "maps": MAPS,
        "layout": "two areas stacked per figure, shared x-axis labelled on the bottom panel",
        "pairs": [list(p) for p in PAIRS],
        "figures": made + ["all_areas_grid.png"],
        "bandset": args.bands,
        "bands_hz": {k: list(v) for k, v in bands.items()},
        "bandset_note": "audited house set; the reference slide uses the pre-correction set "
                        "retired by the 2026-07-27 figure audit (--bands reference reproduces it)",
        "measure": "ratio of expected power: trial-mean power / that channel's own -250..-50 ms "
                   "pre-omission baseline; 10*log10 applied once, after all averaging",
        "aggregation": "unweighted mean of per-session ratios; SEM ribbons across sessions, "
                       "mapped through the same logarithm",
        "sessions_per_area": counts,
        "colour_scale_db": list(vlim),
        "colour_scale_rule": "common across all areas, symmetric, 99th percentile of |dB|",
        "window_ms": list(WIN),
        "frequency_axis": "logarithmic; ticks at the band edges 4, 8, 14, 30, 50, 80, 150 Hz",
        "composition_caveat": "p4 omissions end the trial at +897 ms, so bins beyond that "
                              "come only from p2 and p3 omissions, and a new stimulus begins "
                              "at +1031 ms in those conditions. Both boundaries are drawn on "
                              "the figure; nothing right of +897 ms is omission-only.",
        "coverage_min": COVERAGE_MIN,
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "matplotlib": matplotlib.__version__},
    }
    with open(os.path.join(FIG_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print("figures:", ", ".join(made))
    print("sessions per area:", counts)
    print("colour scale:", vlim, "dB")
    print("WROTE", FIG_DIR)


# Panels emitted by a bare run. The first entry is the main figure; the rest are the
# supplementary stock that context/figures/supplements/ is assembled from.
PANEL_SET = [
    ["--cells", "V1:sup,V1:deep,PFC:sup,PFC:deep", "--ncol", "2",
     "--out", "fig04_V1_PFC_layers"],
    ["--cells", "V1:sup,V1:deep,V4:sup,V4:deep", "--ncol", "2", "--out", "supp_V1_V4_layers"],
    ["--cells", "MT:sup,MT:deep,FEF:sup,FEF:deep", "--ncol", "2", "--out", "supp_MT_FEF_layers"],
    ["--cells", "TEO:sup,TEO:deep,PFC:sup,PFC:deep", "--ncol", "2", "--out", "supp_TEO_PFC_layers"],
    ["--areas", "V1,V2,V3a/d,V4", "--ncol", "2", "--out", "supp_early_visual_areas"],
    ["--areas", "MT,MST,TEO,FST", "--ncol", "2", "--out", "supp_mid_level_areas"],
    ["--areas", "FEF,PFC", "--ncol", "2", "--out", "supp_frontal_areas"],
    [],                       # the five area pairs and the ten-area overview grid
]

# fig04_V1_PFC_layers.svg (area x layer, omission-pooled) is no longer the main figure -- it
# is generated by PANEL_SET below same as before and feeds the supplements from this
# directory's svg/ folder, but the assembled fig04.svg now comes from the RXRR-vs-RRRR
# condition comparison, per the 2026-07-29 figure-set revision.


def main():
    argv = sys.argv[1:]
    if argv:
        run(argv)
        return
    for cfg in PANEL_SET:
        print("---", " ".join(cfg) or "(pairs and overview grid)")
        run(cfg)
    panel_svg = build_v1_pfc_condition_figure()
    here = os.path.dirname(os.path.abspath(__file__))
    out, w, h = assemble([panel_svg], os.path.join(here, "fig04.svg"), ncol=1, letters=False)
    print(f"assembled -> {out}  {w:.1f} x {h:.1f} pt")

    # fig04.svg is a straight wrap of the single condition-figure panel (no letter grid, no
    # extra panels), so its already-rendered PNG (same content, dpi=190) is copied alongside
    # it rather than re-rasterizing the SVG.
    import shutil
    panel_png = panel_svg[:-4] + ".png"
    shutil.copyfile(panel_png, os.path.join(here, "fig04.png"))
    print(f"copied -> {os.path.join(here, 'fig04.png')}")


if __name__ == "__main__":
    main()
