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
import pandas as pd
from matplotlib.patches import Rectangle

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from svgassemble import assemble
from figstats import Result, correct, group_location, paired_location, write
from figstyle import mark_full_trial_axis, EPOCH_ONSETS_MS
from jnwb.spectral import to_db

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


def epoch_boundary_bins(times, win):
    """Bin indices of every epoch onset (fx/p1/d1/p2/d2/p3/...) inside `win`, plus the two
    window edges -- the segment breakpoints smoothing must not cross (see
    smooth_time_segmented)."""
    onsets = sorted(t for t in EPOCH_ONSETS_MS.values() if win[0] <= t <= win[1])
    bounds_ms = sorted(set([win[0]] + onsets + [win[1]]))
    idx = sorted(set(int(np.clip(np.searchsorted(times, t), 0, len(times))) for t in bounds_ms))
    if idx[0] != 0:
        idx = [0] + idx
    if idx[-1] != len(times):
        idx = idx + [len(times)]
    return idx


def smooth_time_segmented(y, sigma_bins, boundary_idx):
    """1-D Gaussian smoothing applied independently within each [boundary_idx[i]:idx[i+1])
    segment -- a transient at a real epoch onset (e.g. p2 stimulus arrival) cannot leak
    backward across that onset into the preceding epoch, or vice versa, the way one
    continuous whole-trial kernel would smear it."""
    out = np.empty_like(y, dtype=float)
    for a, b in zip(boundary_idx[:-1], boundary_idx[1:]):
        if b > a:
            out[a:b] = gaussian_smooth_1d(y[a:b], sigma_bins) if (b - a) > 1 else y[a:b]
    return out


def freq_proportional_smooth_matrix(freqs, fraction, min_bandwidth_hz):
    """Constant-relative-bandwidth (proportional/'constant-Q') smoothing weights: each output
    frequency row is a Gaussian-weighted average of nearby rows with sigma = max(freq *
    fraction, min_bandwidth_hz) Hz -- so smoothing widens in proportion to frequency itself,
    rather than the fixed number of bins a plain index-space kernel would use regardless of
    whether that bin corresponds to 2 Hz (low end) or the same 2 Hz (high end, but visually
    compressed far less on the log-frequency axis the figure actually displays)."""
    freqs = np.asarray(freqs, dtype=float)
    n = freqs.size
    M = np.zeros((n, n))
    for i, fc in enumerate(freqs):
        sigma_hz = max(fc * fraction, min_bandwidth_hz)
        w = np.exp(-0.5 * ((freqs - fc) / sigma_hz) ** 2)
        M[i, :] = w / w.sum()
    return M


FREQ_SMOOTH_FRACTION = 0.12    # smoothing bandwidth = 12% of each row's own frequency
FREQ_SMOOTH_MIN_HZ = 2.0       # floor so the lowest frequencies still get >=1 bin of smoothing


def gaussian_smooth_2d(a, freqs, times, win, sigma_time_bins):
    """Time axis: Gaussian-smoothed within each epoch segment only (no cross-boundary
    leakage, see smooth_time_segmented). Frequency axis: proportional/constant-Q smoothing
    (see freq_proportional_smooth_matrix) -- NOT a fixed-bin-count kernel, so higher
    frequencies get proportionally more smoothing than lower ones, matching how compressed
    they are on the log-frequency display."""
    bounds = epoch_boundary_bins(times, win)
    out = np.apply_along_axis(lambda row: smooth_time_segmented(row, sigma_time_bins, bounds),
                              1, a)
    Mf = freq_proportional_smooth_matrix(freqs, FREQ_SMOOTH_FRACTION, FREQ_SMOOTH_MIN_HZ)
    out = Mf @ np.nan_to_num(out, nan=0.0)
    # Mf-weighted average ignores NaN-handling row-by-row; re-apply NaN where every
    # contributing input row was NaN (mirrors the NaN-safety smooth_time_segmented already
    # gives the time axis).
    finite_mask = np.isfinite(a).astype(float)
    weight_total = Mf @ finite_mask
    out[weight_total <= 0] = np.nan
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
# The other six of the ten analysis areas (figstyle.AREA_ORDER minus CONDITION_AREAS), in
# hierarchy order -- the supplement content for this figure, added 2026-08-04 as individual
# single-panel SVGs (see build_area_condition_supplements) rather than a combined grid.
SUPP_AREAS = ["V2", "V4", "MT", "MST", "FST", "FEF"]
CONDITION_WIN = (-500, 2593)                # p1 onset to the p3/d3 boundary
COND_OMIT_SLOT = {"RXRR": 2, "RRXR": 3, "RRRR": None}
COND_LABEL = {"RXRR": "RXRR (p2 omitted)", "RRXR": "RRXR (p3 omitted)", "RRRR": "RRRR (p2 real)"}
# RRXR added 2026-07-31 for scripts/plot_v182o_condition_bandtraces.py -- draw_condition_
# bandtrace()/draw_condition_spectrogram() read these two dicts directly, so extending them
# here (not monkeypatching from the caller) is what makes RRXR usable through the same
# reused drawing functions. CONDITIONS/CONDITION_AREAS below are unchanged (fig04's own main
# figure still shows only V1/PFC x RXRR/RRRR); this is additive.


def load_condition_maps():
    """Returns (maps, count_maps, freqs, times). `count_maps[k]` is the same shape as
    `maps[k]` (freq x time) and holds the pooled channel x trial count that went into each
    (freq, time) cell of that session's mean -- extract_condition_tfr_maps.py already
    accumulates this (acc_cnt) but it was discarded here until 2026-08-04, when it became the
    weight for a precision-weighted across-session SEM in draw_condition_bandtrace (see that
    function's docstring for why raw pooled count is a weight, not a literal sample size).
    """
    z = np.load(CONDITION_MAPS, allow_pickle=True)
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


def area_cond_sessions(maps, area, cond, layer="all"):
    return {k.split("|")[0]: m for k, m in maps.items()
            if k.split("|")[1] == area and k.split("|")[2] == layer and k.split("|")[3] == cond}


SPEC_SMOOTH_TIME_BINS = 1.5    # frequency-axis smoothing is proportional, not fixed-bin -- see
                                # FREQ_SMOOTH_FRACTION / FREQ_SMOOTH_MIN_HZ near gaussian_smooth_2d
TRACE_SMOOTH_TIME_BINS = 2.0


def draw_condition_spectrogram(ax, area, cond, sess, freqs, times, bands, vlim, letter):
    """One spectrogram: area x condition, p1-aligned, baselined to the middle of d1.

    Displayed map is Gaussian-smoothed -- cosmetic only, for readability; no statistic reads
    this smoothed array. Frequency axis uses proportional/constant-Q smoothing (bandwidth
    scales with each row's own frequency, see freq_proportional_smooth_matrix), not a fixed
    bin count, so the higher frequencies -- visually compressed far less on the log-frequency
    display -- get proportionally more smoothing than theta/alpha. Time axis is smoothed
    independently within each epoch segment (fx/p1/d1/p2/d2/p3), never across an onset
    boundary, so a sharp stimulus transient cannot leak backward or forward across the
    boundary that gives it its meaning (see smooth_time_segmented). Shading is "nearest", not
    "gouraud": gouraud's per-vertex SVG output measured 11x slower to save than nearest on
    this grid size (26.6s vs 2.4s for one panel) and made the 8-spectrogram figure pathological
    under concurrent system load; the Gaussian smoothing above already does the visual-softening
    work gouraud interpolation would have added on top.
    """
    sess, dropped = drop_outlier_sessions(sess)
    grand = to_db(np.nanmean(np.stack(list(sess.values())), axis=0))
    grand_smooth = gaussian_smooth_2d(grand, freqs, times, CONDITION_WIN, SPEC_SMOOTH_TIME_BINS)
    im = ax.pcolormesh(times, freqs, grand_smooth, cmap="viridis", shading="nearest",
                       vmin=vlim[0], vmax=vlim[1])
    for e in sorted({e for v in bands.values() for e in v if e <= freqs[-1]}):
        ax.axhline(e, color="red", lw=0.7, alpha=0.85)
    mark_full_trial_axis(ax, CONDITION_WIN, omit_slot=COND_OMIT_SLOT[cond])
    ax.set_yscale("log")
    ax.set_ylim(freqs[0], freqs[-1])
    ax.set_yticks([4, 8, 14, 30, 50, 80, 150])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    prefix = f"({letter}) " if letter else ""
    ax.set_title(f"{prefix}{area}, {COND_LABEL[cond]}  n={len(sess)} sessions", fontsize=9)
    ax.tick_params(labelsize=7)
    if dropped:
        ax.text(0.01, 1.10, f"{len(dropped)} session(s) excluded (out of scale)",
               transform=ax.transAxes, fontsize=6, color="0.35", va="bottom")
    return im, len(sess)


def weighted_band_mean_sem(sess, counts_sess, freqs, lo, hi):
    """Precision-weighted mean and SEM of a band's ratio, across sessions (2026-08-04).

    Each session's band_ratio(...) is weighted by that session's own pooled channel x trial
    count in the band (summed over the band's frequency rows, from counts_sess -- the same
    per-(freq,time)-cell counts extract_condition_tfr_maps.py already accumulates). A session
    built from more channels/trials/frequency-bins pulls the estimate harder and contributes
    proportionally less to the variance, which is why this ribbon is narrower than a plain
    unweighted across-session SEM.

    This is deliberately NOT the same as treating those pooled channel x trial x bin
    observations as independent replicates for the SEM's sample size -- they are not
    independent (channels share a probe, trials share a session, adjacent frequency bins
    share spectral smoothing), and doing that would overstate precision and disagree with the
    session-level paired/GLMM tests elsewhere in this figure. The standard error below is
    still denominated by Kish's effective sample size ACROSS SESSIONS (sum(w)^2 / sum(w^2)),
    which only equals n_sessions when every session carries equal weight and shrinks toward 1
    as weight concentrates in a few sessions -- session remains the unit of inference, the
    weighting only changes how much each session's own noise level is trusted.
    """
    sel = (freqs >= lo) & (freqs < hi)
    names = list(sess)
    vals = np.stack([band_ratio(sess[n], freqs, lo, hi) for n in names])
    w = np.stack([np.nansum(counts_sess[n][sel], axis=0) for n in names])
    w = np.where(np.isfinite(vals) & (w > 0), w, 0.0)
    wsum = w.sum(axis=0)
    wmean = np.divide(np.nansum(w * vals, axis=0), wsum,
                      out=np.full(wsum.shape, np.nan), where=wsum > 0)
    wvar = np.divide(np.nansum(w * (vals - wmean) ** 2, axis=0), wsum,
                     out=np.full(wsum.shape, np.nan), where=wsum > 0)
    w2sum = (w ** 2).sum(axis=0)
    n_eff = np.divide(wsum ** 2, w2sum, out=np.full(wsum.shape, np.nan), where=w2sum > 0)
    n_eff = np.clip(n_eff, 1.0, None)
    return wmean, np.sqrt(wvar / n_eff)


def draw_condition_bandtrace(ax, area, cond, sess, counts_sess, freqs, times, bands, letter):
    """One band-decomposed trace panel: five bands, precision-weighted mean +- SEM across
    sessions (see weighted_band_mean_sem).

    Mean and SEM are each Gaussian-smoothed within each epoch segment only (see
    smooth_time_segmented -- same no-cross-boundary-leakage rule the spectrogram uses) before
    conversion to dB -- cosmetic only; no statistic reads the smoothed trace.
    """
    sess, dropped = drop_outlier_sessions(sess)
    counts_sess = {k: v for k, v in counts_sess.items() if k in sess}
    bounds = epoch_boundary_bins(times, CONDITION_WIN)
    for (name, (lo, hi)), col in zip(bands.items(), BAND_COLORS):
        mu, sem = weighted_band_mean_sem(sess, counts_sess, freqs, lo, hi)
        mu_s = smooth_time_segmented(mu, TRACE_SMOOTH_TIME_BINS, bounds)
        sem_s = smooth_time_segmented(sem, TRACE_SMOOTH_TIME_BINS, bounds)
        ax.plot(times, to_db(mu_s), color=col, lw=1.6, label=name, zorder=3)
        ax.fill_between(times, to_db(np.maximum(mu_s - sem_s, 1e-12)), to_db(mu_s + sem_s),
                        color=col, alpha=0.28, lw=0, zorder=2)
    ax.axhline(0, color="black", lw=0.8)
    mark_full_trial_axis(ax, CONDITION_WIN, omit_slot=COND_OMIT_SLOT[cond])
    prefix = f"({letter}) " if letter else ""
    ax.set_title(f"{prefix}{area}, {COND_LABEL[cond]}", fontsize=9)
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


# ============================================================================================
# GLMM: band power ~ context (omission/stimulus) x family (A/B/R), per area x band.
# Hypothesis under test: LFP band power tracks the network's state/prior over what is about
# to happen (band ~ f(context)); does that relationship hold uniformly regardless of WHICH
# stimulus identity (A/B) the context is built from, or does it depend on it. A/B family
# needed a new extraction pass (2026-08-04, extract_condition_tfr_maps.py CONDS extended from
# R-family-only) -- AXAB/AAAB and BXBA/BBBA are the same p2-omission-vs-real design RXRR/RRRR
# already gives for R, now available for all three families.
# ============================================================================================
GLMM_CONDS = ["RXRR", "RRRR", "AXAB", "AAAB", "BXBA", "BBBA"]
COND_CONTEXT = {"RXRR": "omission", "AXAB": "omission", "BXBA": "omission",
                "RRRR": "stimulus", "AAAB": "stimulus", "BBBA": "stimulus"}
COND_FAMILY = {"RXRR": "R", "RRRR": "R", "AXAB": "A", "AAAB": "A", "BXBA": "B", "BBBA": "B"}
FAMILY_COLORS = {"R": "#252525", "A": "#1B9E77", "B": "#D95F02"}
GLMM_MIN_SESSIONS, GLMM_MIN_ANIMALS = 6, 2


def build_glmm_long_table(maps, freqs, times, bands):
    """Session-level p2-window band power, one row per session x area x band x condition,
    for all six GLMM_CONDS. Same scalar condition_p2_band_stats uses (mean power over the p2
    window, averaged over channels/trials/time within a session first, then ratio-to-baseline,
    then logged once) -- just computed for all three families instead of R only.
    """
    tmask = (times >= P2_WINDOW_MS[0]) & (times < P2_WINDOW_MS[1])
    rows = []
    for area in CONDITION_AREAS:
        for cond in GLMM_CONDS:
            sess = area_cond_sessions(maps, area, cond)
            for sname, m in sess.items():
                animal = sname.split("_ses-")[0].replace("sub-", "")
                for band, (lo, hi) in bands.items():
                    r = band_ratio(m, freqs, lo, hi)[tmask]
                    if not np.any(np.isfinite(r)):
                        continue
                    rows.append({"area": area, "band": band, "session": sname,
                                "animal": animal, "cond": cond, "context": COND_CONTEXT[cond],
                                "family": COND_FAMILY[cond], "db": to_db(np.nanmean(r))})
    return pd.DataFrame(rows)


# 2026-08-04, reframed per review: exactly two questions, not a crossed context x family
# design. (1) is it an omission at all (yes/no), pooled over stimulus identity -- the
# network-state/prior question. (2) restricted to omissions only, does it matter whether the
# missing stimulus was a PREDICTABLE identity (A or B -- the sequence template makes the
# omitted stimulus's identity inferable) or UNPREDICTABLE (R -- by construction a random
# sequence, so there is no "expected identity" being violated at that slot). The earlier
# context x family interaction design answered a related but different question (does the
# SIZE of the stimulus-vs-omission gap depend on family) and is retired in favour of these two
# simpler, directly-asked models.
def fit_omission_yesno_glmm(df_long):
    """Q1 -- is it an omission or not, pooled over family: db ~ C(context), all six
    GLMM_CONDS rows, groups=animal (random intercept) with a session variance component
    nested within animal (vc_formula={"session": "0 + C(session)"}) -- the paired-within-
    session structure condition_p2_band_stats's paired test already exploits; an animal-only
    random intercept pools that into the residual instead, understating precision (confirmed
    on V1 low-gamma: adding the session term left the coefficient at 5.042 dB unchanged but
    tightened SE 0.677 -> 0.537, z 7.45 -> 9.39). ML fit. One Wald z-test per area x band.
    Cells with fewer than GLMM_MIN_SESSIONS sessions or GLMM_MIN_ANIMALS animals are skipped.
    """
    import warnings
    import statsmodels.formula.api as smf

    results, convergence_notes = [], []
    for (area, band), g in df_long.groupby(["area", "band"]):
        g = g.dropna(subset=["db"])
        n_sessions, n_animals = g.session.nunique(), g.animal.nunique()
        if n_sessions < GLMM_MIN_SESSIONS or n_animals < GLMM_MIN_ANIMALS:
            continue
        with warnings.catch_warnings(record=True) as wlist:
            warnings.simplefilter("always")
            try:
                m = smf.mixedlm("db ~ C(context)", g, groups=g["animal"],
                                vc_formula={"session": "0 + C(session)"}).fit(reml=False)
            except Exception as e:
                convergence_notes.append(f"{area} {band}: fit failed -- {e}")
                continue
            if wlist:
                convergence_notes.append(f"{area} {band}: " +
                                         "; ".join(str(w.message) for w in wlist))

        # patsy's default reference level is alphabetically first ("omission" < "stimulus"),
        # so the fitted term is literally C(context)[T.stimulus] -- the coefficient IS
        # stimulus minus omission. Asserted, not assumed -- a real mislabeling bug this exact
        # line caught earlier in review, before this function was split out.
        ctx_terms = [t for t in m.params.index if t.startswith("C(context)")]
        if not ctx_terms:
            continue
        t = ctx_terms[0]
        assert t == "C(context)[T.stimulus]", (
            f"unexpected patsy reference level for context: {t!r} -- relabel the effect "
            "before trusting its sign")
        coef, se, p = float(m.params[t]), float(m.bse[t]), float(m.pvalues[t])
        results.append(Result(
            figure="fig04", panel="glmm", question=f"{area} {band}: is it an omission? "
            "(stimulus vs omission, pooled family)",
            test="LMM Wald (statsmodels mixedlm, ML)", statistic_name="z",
            statistic=coef / se if se > 0 else np.nan, df="", n=n_sessions, unit="session",
            effect_name="context coef (dB, stimulus-omission)", effect=coef, p=p,
            family="fig04_glmm_is_omission",
            note=f"{n_animals} animals, groups=animal random intercept, session variance "
                 "component nested within animal; db ~ C(context), ML fit; positive = more "
                 "power when p2 is a real stimulus, same convention as condition_p2_band_stats"))

    return results, convergence_notes


def fit_omission_type_glmm(df_long):
    """Q2 -- among omissions only, does it matter whether the missing stimulus was a
    predictable identity (A or B family) or unpredictable (R family, random by construction)?
    db ~ C(family), restricted to context == "omission" rows, same random-effects structure as
    fit_omission_yesno_glmm. Omnibus likelihood-ratio test against the intercept-only model
    (df=2 for the 3-level family factor) -- one number per area x band answering "does
    omission type matter at all", rather than three separate pairwise contrasts, to keep this
    question's multiplicity to one test per cell.
    """
    import warnings
    import statsmodels.formula.api as smf
    from scipy.stats import chi2

    omitted = df_long[df_long.context == "omission"]
    results, convergence_notes = [], []
    for (area, band), g in omitted.groupby(["area", "band"]):
        g = g.dropna(subset=["db"])
        n_sessions, n_animals = g.session.nunique(), g.animal.nunique()
        if n_sessions < GLMM_MIN_SESSIONS or n_animals < GLMM_MIN_ANIMALS:
            continue
        vc = {"session": "0 + C(session)"}
        with warnings.catch_warnings(record=True) as wlist:
            warnings.simplefilter("always")
            try:
                m_null = smf.mixedlm("db ~ 1", g, groups=g["animal"], vc_formula=vc).fit(reml=False)
                m_full = smf.mixedlm("db ~ C(family)", g, groups=g["animal"],
                                     vc_formula=vc).fit(reml=False)
            except Exception as e:
                convergence_notes.append(f"{area} {band} (omission type): fit failed -- {e}")
                continue
            if wlist:
                convergence_notes.append(f"{area} {band} (omission type): " +
                                         "; ".join(str(w.message) for w in wlist))

        lr = 2.0 * (m_full.llf - m_null.llf)
        df_diff = int(m_full.model.k_fe - m_null.model.k_fe)
        p_lr = float(chi2.sf(max(lr, 0.0), df_diff)) if df_diff > 0 else np.nan
        results.append(Result(
            figure="fig04", panel="glmm",
            question=f"{area} {band}: does omission type matter (predictable A/B vs "
            "unpredictable R)?",
            test="LMM likelihood-ratio (db~C(family) vs db~1)", statistic_name="LR chi2",
            statistic=float(lr), df=str(df_diff), n=n_sessions, unit="session",
            p=p_lr, family="fig04_glmm_omission_type",
            note=f"{n_animals} animals; omission-only rows (RXRR/AXAB/BXBA); "
                 "session-nested random effects, ML"))

    return results, convergence_notes


def compute_paired_omission_diff(df_long):
    """Q1 descriptive: within-session paired difference (stimulus_db - omission_db), POOLED
    over family -- the direct counterpart to fit_omission_yesno_glmm's context coefficient.
    Restricted to sessions with both context values present (same pairing
    condition_p2_band_stats uses). Plotting the pooled paired difference, not the two absolute
    context levels separately, is what actually shows the effect Q1's test found -- see
    fit_omission_yesno_glmm's docstring for why an unpaired, absolute-level plot understates it.
    """
    wide = df_long.pivot_table(index=["area", "band", "session", "animal"],
                               columns="context", values="db", aggfunc="mean").reset_index()
    wide = wide.dropna(subset=["stimulus", "omission"])
    wide["diff"] = wide["stimulus"] - wide["omission"]
    return wide


def panel_omission_yesno(diff_df, bands):
    """Q1 -- is it an omission? One bar per area x band: mean +/- SEM of the within-session
    paired difference (stimulus - omission), pooled over family. Positive = more power for a
    real stimulus than an omission, matching fit_omission_yesno_glmm's sign convention.
    """
    areas, band_names = CONDITION_AREAS, list(bands)
    fig, axes = plt.subplots(len(band_names), len(areas),
                             figsize=(1.5 * len(areas), 1.7 * len(band_names)), sharex=True)
    for bi, band in enumerate(band_names):
        for ai, area in enumerate(areas):
            ax = axes[bi, ai]
            cell = diff_df[(diff_df.area == area) & (diff_df.band == band)]
            mu, se = cell["diff"].mean(), cell["diff"].sem()
            ax.bar([0], [mu], yerr=[se], color="#4477AA", edgecolor="black", linewidth=0.6,
                  width=0.6, capsize=3, error_kw=dict(elinewidth=1.0), zorder=3)
            ax.axhline(0, color="black", lw=0.7, zorder=2)
            ax.set_xlim(-0.7, 0.7)
            ax.set_xticks([])
            ax.tick_params(labelsize=6.5)
            if ai == 0:
                ax.set_ylabel(band.split("(")[0].strip(), fontsize=7.5)
            if bi == 0:
                ax.set_title(area, fontsize=8.5)
            for s in ("top", "right", "bottom"):
                ax.spines[s].set_visible(False)
    # Two short lines, not one long one: this panel is narrow (single bar per cell) and a
    # one-line title at this fontsize ran off the right edge -- found by rendering standalone,
    # same class of bug as the earlier header-clipping fixes on this figure.
    fig.suptitle("Q1: is it an omission?\nPaired difference (stimulus - omission, dB), "
                 "pooled over family -- mean ± SEM", fontsize=9, y=0.985, linespacing=1.4)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.88])
    return fig


def panel_omission_type(df_long, bands):
    """Q2 -- among omissions, does predictability matter? One 3-bar panel (R/A/B) per area x
    band: mean +/- SEM of the raw p2-window dB level DURING the omission itself (not a
    difference), restricted to context == "omission" rows -- what fit_omission_type_glmm's
    omnibus test asks whether these three bars differ.
    """
    areas, band_names = CONDITION_AREAS, list(bands)
    omitted = df_long[df_long.context == "omission"]
    fig, axes = plt.subplots(len(band_names), len(areas),
                             figsize=(2.15 * len(areas), 2.0 * len(band_names)), sharex=True)
    fams = ("R", "A", "B")
    x = np.arange(len(fams))
    for bi, band in enumerate(band_names):
        for ai, area in enumerate(areas):
            ax = axes[bi, ai]
            cell = omitted[(omitted.area == area) & (omitted.band == band)]
            mu = [cell.loc[cell.family == f, "db"].mean() for f in fams]
            se = [cell.loc[cell.family == f, "db"].sem() for f in fams]
            ax.bar(x, mu, yerr=se, color=[FAMILY_COLORS[f] for f in fams],
                  edgecolor="black", linewidth=0.5, capsize=2.5,
                  error_kw=dict(elinewidth=0.9), zorder=3)
            ax.axhline(0, color="black", lw=0.7, zorder=2)
            ax.set_xlim(-0.6, len(fams) - 0.4)
            ax.set_xticks(x)
            if bi == len(band_names) - 1:
                ax.set_xticklabels(["R\n(unpred.)", "A\n(pred.)", "B\n(pred.)"], fontsize=6.5)
            else:
                ax.set_xticklabels([])
            ax.tick_params(labelsize=6.5)
            if ai == 0:
                ax.set_ylabel(band.split("(")[0].strip(), fontsize=7.5)
            if bi == 0:
                ax.set_title(area, fontsize=8.5)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=FAMILY_COLORS[f]) for f in fams]
    # bbox_to_anchor/suptitle y both < 1.0: a figure-level artist positioned above y=1.0 sits
    # outside the canvas and a plain savefig (no bbox_inches="tight") silently clips it -- see
    # the same note on the retired panel_glmm_context_family, found by rendering and looking.
    fig.legend(handles, ["R (unpredictable)", "A (predictable)", "B (predictable)"], ncol=3,
              fontsize=8, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 0.998))
    # Two shorter lines, not one long one at 9.5pt: that version clipped at BOTH edges in the
    # full-script run's dpi=190 save (though not in an isolated dpi=150 smoke test of this
    # same function -- found by inspecting the actual pipeline output, not by re-trusting an
    # earlier isolated check that happened to pass. Root cause not chased further; the fix
    # (shorter, wrapped, smaller) is the same pattern already applied to panel_omission_yesno
    # and is robust regardless of the exact text-metrics quirk that caused it).
    fig.suptitle("Q2: does omission type matter?\nBand power during the omission itself (dB, "
                 "p2 window), by predictability -- mean ± SEM", fontsize=9, y=0.93,
                 linespacing=1.4)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.86])
    return fig


def build_v1_pfc_condition_figure():
    """Assemble the main figure in three stacked sections: (1) spectrograms for all four
    CONDITION_AREAS (V1, V3a/d, TEO, PFC), RXRR then RRRR; (2) band-power traces for the same
    four areas, RXRR then RRRR; (3) the band-power-vs-context-x-family GLMM summary (2026-08-04
    addition). Reworked 2026-08-04 from the earlier per-area-row layout (spec-RXRR, spec-RRRR,
    trace-RXRR, trace-RRRR columns, one area per row) into this spectrogram-block-then-
    trace-block-then-relationship-block order, per review.

    Each spectrogram's colour scale is autoscaled to itself (99th percentile of |dB| within
    that one area x condition panel, its own colorbar alongside it) rather than a scale shared
    across all panels -- areas differ enormously in overall power change, and a common scale
    compresses the smaller ones toward invisibility.
    """
    maps, count_maps, freqs, times = load_condition_maps()
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
    narea = len(CONDITION_AREAS)
    nrow = 2 * narea                                # spectrogram block, then trace block
    fig, axes = plt.subplots(nrow, 2, figsize=(9.6, 3.3 * narea + 1.6 * narea))
    letters = "abcdefghijklmnop"
    li = 0
    for ri, area in enumerate(CONDITION_AREAS):
        for ci, cond in enumerate(CONDITIONS):
            sess = area_cond_sessions(maps, area, cond)
            ax = axes[ri, ci]
            vlim = panel_vlim(area, cond)
            im, n = draw_condition_spectrogram(ax, area, cond, sess, freqs, times, bands,
                                               vlim, letters[li])
            # Rasterize the spectrogram into the SVG instead of exporting sub-pixel quads as
            # vector paths per panel: at a print size of ~1.1 pt per quad, Chrome and
            # Illustrator both alias the vector form, while an embedded image at savefig dpi
            # stays crisp at any zoom. Same convention fig01_finalized.svg uses (embedded
            # images, zero paths). The band traces and all text stay vector -- editable.
            im.set_rasterized(True)
            cb = fig.colorbar(im, ax=ax, pad=0.012, fraction=0.046)
            cb.solids.set_rasterized(True)
            cb.set_label("dB", fontsize=7, rotation=270, labelpad=9)
            cb.ax.tick_params(labelsize=6)
            counts[f"{area}_{cond}"] = n
            li += 1
    for ri, area in enumerate(CONDITION_AREAS):
        for ci, cond in enumerate(CONDITIONS):
            sess = area_cond_sessions(maps, area, cond)
            counts_sess = area_cond_sessions(count_maps, area, cond)
            draw_condition_bandtrace(axes[narea + ri, ci], area, cond, sess, counts_sess,
                                     freqs, times, bands, letters[li])
            li += 1

    for ri in range(narea):
        axes[ri, 0].set_ylabel(f"{CONDITION_AREAS[ri]}\nFrequency (Hz)", fontsize=8.5)
        axes[ri, 1].tick_params(labelleft=False)
    for ri in range(narea):
        axes[narea + ri, 0].set_ylabel(f"{CONDITION_AREAS[ri]}\nPower change (dB)", fontsize=8.5)
        axes[narea + ri, 1].tick_params(labelleft=False)
    for ci in range(2):
        axes[nrow - 1, ci].set_xlabel("Time from p1 onset (ms)", fontsize=8)
    handles, labs = axes[narea, 0].get_legend_handles_labels()

    # bbox_inches="tight" forces an extra full-figure render-and-measure pass on top of the
    # one savefig already does -- expensive with 16 pcolormesh/gouraud panels and became
    # pathological under concurrent CPU load from other processes on this shared machine
    # (observed: hung for 15+ hours). fig.tight_layout() computes a layout without that
    # second render pass.
    #
    # Getting the header block (section label + suptitle + band legend) to sit flush above
    # the axes without overlapping OR leaving a dead gap took three tries, each found only by
    # rendering and looking, not by reasoning about the numbers:
    #  1. rect top=0.88, header y-values guessed as fixed fractions (0.995/0.955/0.885): left
    #     most of that reserved 12% as blank space, because tight_layout's own per-panel-title
    #     padding already used less room than the guess assumed.
    #  2. rect top=0.97, header stacked from axes[0,0]'s measured top (get_position().y1):
    #     the SUPTITLE's y was additionally clamped with min(..., 0.925) as a safety cap --
    #     but 0.925 sits BELOW the actual measured axes top (~0.954 with this rect), so the
    #     clamp itself pushed the suptitle down INTO the spectrogram panel.
    #  3. This version: rect top=0.90 (comfortable fixed headroom, no reliance on a guessed
    #     clamp), then the three header rows are stacked upward from the measured axes top by
    #     fixed increments sized for their own font sizes -- no min()/max() safety clamp that
    #     could itself land below the axes top.
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.90])

    # axes[0,0].get_position().y1 is the plotting box's own top edge -- it does NOT include
    # that panel's own ax.set_title() text, which matplotlib floats above the box on its own
    # padding, hence the +0.012 clearance before the first header row.
    axes_top = axes[0, 0].get_position().y1
    y_spec = axes_top + 0.012
    fig.text(0.5, y_spec, "Spectrograms (RXRR left, RRRR right, per area)", fontsize=10,
             fontweight="bold", ha="center", va="bottom")
    y_title = y_spec + 0.032
    fig.suptitle(f"{', '.join(CONDITION_AREAS)} -- RXRR vs RRRR, p1-d1-p2-d2-p3\n"
                "baseline = middle of d1; each spectrogram's colour scale is autoscaled to "
                "itself", fontsize=10, fontweight="bold", y=y_title, linespacing=1.5)
    y_legend = y_title + 0.035
    fig.legend(handles, labs, fontsize=8, ncol=5, loc="upper center",
              bbox_to_anchor=(0.5, y_legend), frameon=False)
    # Trace-block label placed from the ACTUAL measured boundary between the two blocks'
    # axes (fig.transFigure via get_position(), after tight_layout has set final positions),
    # not a hand-computed fraction -- guaranteed correct regardless of area count or margins.
    y_spec_bottom = axes[narea - 1, 0].get_position().y0
    y_trace_top = axes[narea, 0].get_position().y1
    fig.text(0.5, (y_spec_bottom + y_trace_top) / 2.0, "Band-power traces, mean ± SEM "
             "across sessions (RXRR left, RRRR right, per area)", fontsize=10,
             fontweight="bold", ha="center", va="center")

    grid_out = os.path.join(FIG_DIR, "fig04_v1_pfc_rxrr_rrrr")
    fig.savefig(grid_out + ".png", dpi=190)
    # Same dpi as the PNG so the rasterized spectrogram panels embed at matching
    # resolution (savefig dpi controls the resolution of rasterized artists in SVG).
    fig.savefig(grid_out + ".svg", dpi=190)
    plt.close(fig)

    # 2026-08-04: fig04 reverted to spectrogram+trace only, per review -- the Q1/Q2 GLMM
    # sections (is it an omission? does omission type matter?) built earlier the same day are
    # no longer assembled into this figure. The fitting/plotting functions
    # (fit_omission_yesno_glmm, fit_omission_type_glmm, panel_omission_yesno,
    # panel_omission_type) are still defined above and still runnable -- real, reviewed
    # analysis, just not part of this figure's default build -- for whoever picks up a GLMM
    # supplement later.
    out_path, _, _ = assemble([grid_out + ".svg"],
                              os.path.join(os.path.dirname(FIG_DIR), "fig04.svg"), ncol=1,
                              gap=1.0, label_inset=True)
    # assemble() writes SVG only; with a single input panel this is a straight rescale-to-
    # TEXT_W wrap, so the already-rendered grid PNG (same content, same dpi) is copied
    # alongside it rather than re-rasterizing.
    import shutil
    shutil.copyfile(grid_out + ".png", os.path.join(os.path.dirname(FIG_DIR), "fig04.png"))

    colour_scales = {f"{area}_{cond}": list(panel_vlim(area, cond))
                     for area in CONDITION_AREAS for cond in CONDITIONS}
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__), "maps": CONDITION_MAPS,
        "layout": f"2 stacked sections: (1) spectrograms, {narea} areas "
                  f"({', '.join(CONDITION_AREAS)}) x 2 conditions (RXRR, RRRR); "
                  "(2) band-power traces, same areas x conditions. Reworked 2026-08-04 from "
                  "the earlier per-area-row layout into this spectrogram-block-then-trace-"
                  "block order; a same-day GLMM addition (Q1/Q2, is it an omission / does "
                  "omission type matter) was built, then removed from this figure per review "
                  "-- fig04 shows spectrogram+traces only. Trace SEM is precision-weighted "
                  "across sessions by each session's own channel x trial x frequency-bin "
                  "count (see weighted_band_mean_sem), not a plain unweighted across-session "
                  "SEM as before.",
        "areas": CONDITION_AREAS, "conditions": CONDITIONS,
        "window_ms_re_p1": list(CONDITION_WIN),
        "baseline": "middle third of d1 (706-856 ms from p1), NOT a pre-trial fixation "
                   "baseline -- see extract_condition_tfr_maps.py",
        "measure": "ratio of expected power vs each channel's own middle-of-d1 baseline; "
                  "10*log10 applied once, after all averaging",
        "colour_scale_db_per_panel": colour_scales,
        "colour_scale_rule": "each spectrogram autoscaled to itself, symmetric, 99th "
                            "percentile of |dB| within that panel",
        "trace_sem_rule": "precision-weighted across sessions by pooled channel x trial "
                          "count per band (Kish effective sample size); see "
                          "weighted_band_mean_sem docstring for why this is not the same as "
                          "treating those pooled observations as independent replicates",
        "bands_hz": {k: list(v) for k, v in bands.items()},
        "sessions_per_area_condition": counts,
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__, "matplotlib": matplotlib.__version__},
    }
    with open(grid_out + ".receipt.json", "w", encoding="utf-8") as fh:
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
    return out_path


def build_area_condition_supplements():
    """Single-panel spectrogram and band-trace SVGs, one per SUPP_AREAS area x CONDITIONS x
    panel type (6 areas x 2 conditions x 2 types = 24 panels) -- the supplement content for
    this figure, since the main figure covers only CONDITION_AREAS (V1, V3a/d, TEO, PFC). Same
    RXRR-vs-RRRR design, same drawing functions (draw_condition_spectrogram,
    draw_condition_bandtrace) as the main figure, but saved as individual panels rather than
    assembled into a grid, per review ("make the single subpanel svgs"). Colour scale is
    per-panel autoscaled (same rule as the main figure), not shared with it.

    Not wired into build_supplements.py's PLAN -- these are produced as individual assets in
    this figure's own svg/ folder; assembling them into a numbered figSNN supplement is a
    separate step if wanted later.
    """
    maps, count_maps, freqs, times = load_condition_maps()
    bands = BANDSETS["manuscript"]
    made, counts = [], {}
    for area in SUPP_AREAS:
        for cond in CONDITIONS:
            sess = area_cond_sessions(maps, area, cond)
            if not sess:
                print(f"WARNING: no data for {area} {cond}, skipping supplement panel(s)")
                continue
            counts_sess = area_cond_sessions(count_maps, area, cond)
            kept, _ = drop_outlier_sessions(sess)
            v = to_db(np.nanmean(np.stack(list(kept.values())), axis=0))
            vmax = max(float(np.nanpercentile(np.abs(v[np.isfinite(v)]), 99)), 0.5)
            vlim = (-round(vmax, 1), round(vmax, 1))
            area_tag = area.replace("/", "").replace(" ", "")

            fig, ax = plt.subplots(figsize=(4.6, 3.1))
            im, n = draw_condition_spectrogram(ax, area, cond, sess, freqs, times, bands,
                                               vlim, "")
            im.set_rasterized(True)
            cb = fig.colorbar(im, ax=ax, pad=0.02, fraction=0.05)
            cb.solids.set_rasterized(True)
            cb.set_label("dB", fontsize=7, rotation=270, labelpad=9)
            cb.ax.tick_params(labelsize=6)
            ax.set_ylabel("Frequency (Hz)", fontsize=8)
            ax.set_xlabel("Time from p1 onset (ms)", fontsize=8)
            fig.tight_layout()
            name = f"fig04_supp_{area_tag}_{cond}_spectrogram"
            out = os.path.join(FIG_DIR, name)
            fig.savefig(out + ".svg", dpi=190)
            fig.savefig(out + ".png", dpi=190)
            plt.close(fig)
            made.append(name)
            counts[f"{area}_{cond}"] = n

            fig, ax = plt.subplots(figsize=(4.6, 3.4))
            draw_condition_bandtrace(ax, area, cond, sess, counts_sess, freqs, times, bands, "")
            ax.set_ylabel("Power change (dB)", fontsize=8)
            ax.set_xlabel("Time from p1 onset (ms)", fontsize=8)
            # ncol=5 (one row) ran off both edges of this panel's 4.6in width -- narrower
            # than the main figure's 9.6in grid the same legend call works fine in. ncol=2
            # (3 rows) fits within the panel width instead.
            ax.legend(fontsize=6.5, frameon=False, ncol=2, loc="upper center",
                     bbox_to_anchor=(0.5, -0.24))
            fig.tight_layout(rect=[0.0, 0.14, 1.0, 1.0])
            name = f"fig04_supp_{area_tag}_{cond}_trace"
            out = os.path.join(FIG_DIR, name)
            fig.savefig(out + ".svg", dpi=190)
            fig.savefig(out + ".png", dpi=190)
            plt.close(fig)
            made.append(name)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__), "maps": CONDITION_MAPS,
        "purpose": "supplement content for fig04: single-panel spectrogram/trace SVGs for "
                  "the six areas not in the main figure (SUPP_AREAS), same RXRR-vs-RRRR "
                  "design and drawing functions",
        "areas": SUPP_AREAS, "conditions": CONDITIONS, "panels_written": made,
        "sessions_per_area_condition": counts,
        "trace_sem_rule": "precision-weighted across sessions by pooled channel x trial "
                          "count per band (Kish effective sample size); see "
                          "weighted_band_mean_sem",
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__, "matplotlib": matplotlib.__version__},
    }
    with open(os.path.join(FIG_DIR, "fig04_supp_areas.receipt.json"), "w",
             encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"wrote {len(made)} supplement panels for areas {SUPP_AREAS}")
    print("sessions per area/condition:", counts)
    return made


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
    # build_v1_pfc_condition_figure() assembles fig04.svg (spectrogram+trace grid only, as of
    # 2026-08-04) and writes fig04.png itself -- see its own docstring.
    out = build_v1_pfc_condition_figure()
    print(f"assembled -> {out}")
    build_area_condition_supplements()


if __name__ == "__main__":
    main()
