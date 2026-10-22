"""Generate the canonical figures for jnwb documentation.

Each figure draws results of public jnwb calls on synthetic test signals with known ground
truth, producing reproducible figures for docs/assets/figures/. Figure 21 is the one empirical
figure: it draws the open-data tutorial's analysis of its DANDI 000253 excerpt. The palette, fonts, size tiers,
line widths and the figure width come from docs/figure_style.py.

Regenerate with the Matplotlib release the compared CI leg pins (`matplotlib==` in
.github/workflows/workflow.yml; each PNG records the one that wrote it) and with the figure font:
set JNWB_FIGURE_FONT_DIR to the directory holding LiberationSans-Regular.ttf and
LiberationSans-Bold.ttf from the 2.1.5 release tarball named in that workflow.

Usage:
    python docs/generate_figures.py                     # rewrite docs/assets/figures/
    python docs/generate_figures.py --out-dir DIR       # write elsewhere, e.g. to compare
    python docs/generate_figures.py --only fig07_population_decoding.png
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

# The repository root, for jnwb, and this folder, for the style module. Guarded: the suite
# executes this module in-process, and an unconditional prepend there puts the checkout ahead
# of an installed jnwb. Under JNWB_EXPECTED_PACKAGE_ROOT the checkout goes last, so the copy it
# names wins.
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT"):
    if str(REPO_ROOT) not in sys.path:
        sys.path.append(str(REPO_ROOT))
elif str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import figure_style as style
import jnwb
from jnwb import StatisticalAnalysis
from jnwb.laminar import CANONICAL_VFLIP_BANDS
from jnwb.testing import synth_correlation_blocks, synth_laminar_motif
from jnwb.testing.nwb_fixtures import (
    CODE_LABEL_A,
    CODE_LABEL_B,
    TASK_TABLE,
    canonical_co_resident_options,
    write_synth_nwb,
)

FIGURE_DIR = REPO_ROOT / "docs" / "assets" / "figures"
OUT_DIR = FIGURE_DIR

# Every figure is drawn twice on a transparent background, in the light theme as NAME.png and in
# the dark theme as NAME.dark.png; a page shows the one matching its palette scheme through
# Material's `#only-light` and `#only-dark`. No figure paints its own background.
# Colours, text sizes and line widths come from docs/figure_style.py; this table holds only the
# ink each theme draws text, edges and faint marks with.
THEMES = {
    "light": {"fg": "#2d2d2d", "edge": "#8a8a8a", "faint": "#8a8a8a", "suffix": ".png"},
    "dark": {"fg": "#e0e0e0", "edge": "#707070", "faint": "#707070", "suffix": ".dark.png"},
}
C_DARK = THEMES["light"]["fg"]
C_LIGHT_GRAY = THEMES["light"]["faint"]
SUFFIX = THEMES["light"]["suffix"]
#: The highlight of the theme being drawn, from the style module.
C_HIGHLIGHT = style.HIGHLIGHT["light"]

#: The exit status of a run that stopped because the figure font is absent.
FONT_MISSING_EXIT = 3

style.apply()


def apply_theme(name):
    """Set the foreground colours every figure draws with; the background stays transparent."""
    global C_DARK, C_LIGHT_GRAY, SUFFIX, C_HIGHLIGHT
    theme = THEMES[name]
    C_DARK, C_LIGHT_GRAY, SUFFIX = theme["fg"], theme["faint"], theme["suffix"]
    C_HIGHLIGHT = style.HIGHLIGHT[name]
    plt.rcParams.update({
        "text.color": theme["fg"],
        "axes.labelcolor": theme["fg"],
        "axes.titlecolor": theme["fg"],
        "xtick.color": theme["fg"],
        "ytick.color": theme["fg"],
        "axes.edgecolor": theme["edge"],
        "legend.labelcolor": theme["fg"],
    })


def _save(fig, name):
    fig.savefig(OUT_DIR / name.replace(".png", SUFFIX))


AREA_COLOURS = style.AREA


def class_colours():
    """The depth class colours of fig01 panel B: the highlight for superficial, a series for deep."""
    return {"Superficial": C_HIGHLIGHT, "Deep": style.SERIES[3]}


#: The depth fig01 classifies at, passed to the classifier and drawn from the same name.
DEPTH_THRESHOLD_UM = 1000.0


def fig01_addressing():
    """Figure 1: Channel addressing & geometric depth classification."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(style.WIDTH, 3.4), dpi=style.DPI,
                                   gridspec_kw={"width_ratios": [1, 1.25]})

    n_ch = 24
    elec_df = pd.DataFrame({
        "channel_id": np.arange(n_ch),
        "location": ["V1, V2, V3"] * n_ch,
        "group_name": ["probeA"] * n_ch,
        "z": np.linspace(200.0, 1800.0, n_ch),
        "depth_unit": ["um"] * n_ch,
    })

    mapped_areas = [jnwb.map_peak_channel_to_area(ch, elec_df) for ch in range(n_ch)]
    depth_classes = [jnwb.classify_layer_from_depth(ch, elec_df, threshold=DEPTH_THRESHOLD_UM)
                     for ch in range(n_ch)]

    # Panel A: one area per block of contacts, each named beside its own dots
    ax1.plot(np.zeros(n_ch), range(n_ch), color=style.NEUTRAL, lw=style.LW, zorder=2)
    ax1.scatter(np.zeros(n_ch), range(n_ch), c=[AREA_COLOURS[a] for a in mapped_areas], s=45,
                edgecolors=C_DARK, linewidths=style.EDGE, zorder=3)
    ax1.set_yticks(range(0, n_ch, 4))
    ax1.set_xlim(-0.25, 1.0)
    ax1.set_xticks([])
    for i in (0, 8, 16):
        area = mapped_areas[i]
        ax1.annotate(f"Channels {i}-{i + 7}: {area}", xy=(0.12, i + 3.5), va="center",
                     fontsize=style.SMALL, color=C_DARK)
    ax1.set_ylabel("Channel index")
    style.panel_title(ax1, "A", "Area per contact\n(jnwb.map_peak_channel_to_area)")
    ax1.invert_yaxis()

    # Panel B: the class of each contact, keyed, with the threshold it was classified at
    z_coords = elec_df["z"].values
    class_colour = class_colours()
    colours = [class_colour[c] for c in depth_classes]
    ax2.barh(range(n_ch), z_coords, color=colours, edgecolor="none", height=0.7)
    ax2.axvline(DEPTH_THRESHOLD_UM, color=C_DARK, ls="--", lw=style.LW_THIN)
    ax2.set_xlim(0.0, 2800.0)
    ax2.set_yticks(range(0, n_ch, 4))
    ax2.set_xlabel("Depth z (µm)")
    ax2.set_ylabel("Channel index")
    style.panel_title(ax2, "B", "Geometric depth class\n(jnwb.classify_layer_from_depth)")
    ax2.invert_yaxis()
    ax2.legend(handles=[
        Patch(color=class_colour["Superficial"], label="Superficial (z ≤ threshold)"),
        Patch(color=class_colour["Deep"], label="Deep (z > threshold)"),
        Line2D([], [], color=C_DARK, ls="--", lw=style.LW_THIN,
               label=f"threshold = {DEPTH_THRESHOLD_UM:.0f} µm"),
    ], frameon=False, loc="upper right")

    fig.tight_layout()
    _save(fig, "fig01_addressing_laminar.png")
    plt.close(fig)


#: The window and bin width of fig02's PSTH, in ms relative to onset.
PSTH_WINDOW_MS = (-300.0, 600.0)
PSTH_BIN_MS = 15.0


def fig02_spikes_psth():
    """Figure 2: Spiking raster and PSTH with right-open time bins."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(style.WIDTH, 3.9), sharex=True, dpi=style.DPI,
                                   gridspec_kw={"height_ratios": [1.2, 1]})

    rng = np.random.default_rng(42)
    n_trials = 30
    trial_starts = np.arange(n_trials) * 1.5
    all_spikes = []

    for t_idx, t_start in enumerate(trial_starts):
        # Baseline: ~5 Hz; Response (0.0 to 0.25s): ~35 Hz
        t_base = rng.uniform(-0.3, 0.0, rng.poisson(0.3 * 5.0))
        t_resp = rng.uniform(0.04, 0.25, rng.poisson(0.21 * 35.0))
        t_post = rng.uniform(0.25, 0.6, rng.poisson(0.35 * 8.0))
        spk_rel = np.sort(np.concatenate([t_base, t_resp, t_post]))
        all_spikes.extend(spk_rel + t_start)
        ax1.vlines(spk_rel * 1000, t_idx, t_idx + 0.8, color=C_DARK, lw=style.LW_THIN)

    ax1.axvline(0, color=style.NEUTRAL, ls=":", lw=style.LW_THIN)
    ax1.set_ylabel("Trial index")
    style.panel_title(ax1, "A", f"Spike raster ({n_trials} trials)")
    ax1.set_ylim(-0.5, n_trials + 0.5)

    centers_ms, mean_rate, sem_rate = jnwb.raster_psth(
        np.asarray(all_spikes), trial_starts, win_ms=PSTH_WINDOW_MS, bin_ms=PSTH_BIN_MS)

    ax2.plot(centers_ms, mean_rate, color=style.SERIES[0], lw=style.LW, label="Mean rate")
    ax2.fill_between(centers_ms, mean_rate - sem_rate, mean_rate + sem_rate, color=style.SERIES[0],
                     alpha=0.35, lw=0, label="±1 SEM")
    ax2.axvline(0, color=style.NEUTRAL, ls=":", lw=style.LW_THIN)
    ax2.set_ylim(0, float(np.max(mean_rate + sem_rate)) * 1.45)
    ax2.set_xlabel("Time relative to onset (ms)")
    ax2.set_ylabel("Firing rate (Hz)")
    style.panel_title(ax2, "B", f"PSTH (jnwb.raster_psth, Δ = {PSTH_BIN_MS:.0f} ms, right-open bins)")
    ax2.legend(frameon=False, loc="upper right", ncol=2)

    fig.tight_layout()
    _save(fig, "fig02_raster_psth.png")
    plt.close(fig)


def fig03_onset():
    """Figure 3: Causal exponential smoothing and bounded onset latency fit."""
    fig, ax = plt.subplots(figsize=(style.WIDTH, 4.0), dpi=style.DPI)

    rng = np.random.default_rng(7)
    bin_ms = 5.0
    smooth_tau_ms = 25.0
    t = np.arange(-150.0, 400.0, bin_ms)
    t0_true = 85.0
    tau_true = 30.0
    true_rate = 6.0 + 24.0 * np.where(t >= t0_true, 1.0 - np.exp(-(t - t0_true) / tau_true), 0.0)
    noisy_rate = np.maximum(0, true_rate + rng.normal(0, 3.0, len(t)))

    smoothed = jnwb.causal_exp_smooth(noisy_rate, bin_ms=bin_ms, tau_ms=smooth_tau_ms)
    fit = jnwb.fit_exponential_onset(t, smoothed, t0_bounds_ms=(0.0, 250.0))
    pred = jnwb.onset_model(t, fit["t0"], fit["tau"], fit["amplitude"], fit["baseline"])

    ax.scatter(t, noisy_rate, color=C_LIGHT_GRAY, s=10, label="Simulated noisy rate", zorder=2)
    ax.plot(t, smoothed, color=style.VARIABLE["smoothed"], lw=style.LW,
            label=f"Causal filter (tau = {smooth_tau_ms:.0f} ms, no backward leakage)", zorder=3)
    ax.plot(t, pred, color=style.VARIABLE["fitted"], lw=style.LW_THICK,
            label=f"Bounded fit: t0 = {fit['t0']:.1f} ms, tau = {fit['tau']:.1f} ms "
                  f"(R² = {fit['r2']:.2f})", zorder=4)
    # The two onsets differ by line style as well as color (long dashes against dots), and each
    # is named beside its line, so neither the color nor the legend is needed to tell them apart.
    ax.axvline(fit["t0"], color=style.VARIABLE["fitted"], ls=(0, (6, 3)), lw=style.LW_THIN, zorder=1)
    ax.axvline(t0_true, color=style.VARIABLE["truth"], ls=":", lw=style.LW,
               label=f"Ground truth (t0 = {t0_true:.0f} ms, tau = {tau_true:.0f} ms)", zorder=1)
    top = ax.get_xaxis_transform()
    ax.text(t0_true - 6.0, 0.97, f"true onset\n{t0_true:.0f} ms", transform=top,
            ha="right", va="top", fontsize=style.SMALL, color=C_DARK)
    ax.text(fit["t0"] + 6.0, 0.97, f"fitted onset\n{fit['t0']:.1f} ms", transform=top,
            ha="left", va="top", fontsize=style.SMALL, color=C_DARK)

    ax.set_ylim(0, float(np.max(noisy_rate)) * 1.02)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Firing rate (Hz)")
    ax.set_title("Causality-bounded onset latency fit (jnwb.fit_exponential_onset)", pad=8)
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0.0, -0.2), ncol=1)

    fig.tight_layout()
    _save(fig, "fig03_onset_fitting.png")
    plt.close(fig)


#: The rhythm fig04 adds to its aperiodic background.
FIG04_RHYTHM_HZ = 10.0
#: The highest frequency fig04 draws its spectrum to.
FIG04_SHOWN_HZ = 119.0


def fig04_spectral_tilt():
    """Figure 4: Power Spectral Density and aperiodic spectral tilt."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(style.WIDTH, 3.1), dpi=style.DPI)

    fs = 1000.0
    duration = 5.0
    t = np.arange(int(fs * duration)) / fs
    rng = np.random.default_rng(12)

    # Random-walk noise, whose spectrum falls as 1/f squared, + 10 Hz rhythm
    white = rng.standard_normal(len(t))
    pink = np.cumsum(white)
    pink -= pink.mean()
    pink /= pink.std()
    lfp = pink + 0.8 * np.sin(2 * np.pi * FIG04_RHYTHM_HZ * t)

    # Panel A: Time trace
    ax1.plot(t[:1000] * 1000, lfp[:1000], color=C_DARK, lw=style.LW_THIN)
    ax1.set_xlabel("Time (ms)")
    ax1.set_ylabel("LFP (a.u.)")
    style.panel_title(ax1, "A", f"Raw LFP time series\n(random-walk background + "
                                f"{FIG04_RHYTHM_HZ:.0f} Hz rhythm)")

    # Panel B: PSD + power-law fit to that same PSD. spectral_tilt fits its own Welch
    # spectrum, on a different grid, so its line cannot be drawn over this one.
    freqs, psd = jnwb.compute_psd(lfp, fs=fs)
    freqs, psd = freqs[1:], psd[1:]  # aperiodic_fit takes positive frequencies only; drop DC
    # aperiodic_fit removes no peaks, so the range starts above the rhythm's.
    fit_range = (15.0, 90.0)
    fit = jnwb.aperiodic_fit(freqs, psd, freq_range=fit_range)

    mask = (freqs >= fit_range[0]) & (freqs <= fit_range[1])
    f_fit = freqs[mask]
    fitted_psd = 10.0 ** (fit.offset - fit.exponent * np.log10(f_fit))

    shown = freqs <= FIG04_SHOWN_HZ
    ax2.loglog(freqs[shown], psd[shown], color=style.NEUTRAL, lw=style.LW_THIN, label="Welch PSD")
    ax2.loglog(f_fit, fitted_psd, color=style.VARIABLE["fitted"], lw=style.LW_THICK,
               label=f"Power-law fit: slope = {style.num(-fit.exponent)}\n"
                     f"(R² = {fit.r_squared:.2f})")
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("Power spectral density (a.u.²/Hz)")
    style.panel_title(ax2, "B", "Aperiodic fit (jnwb.aperiodic_fit)")
    ax2.legend(frameon=False, loc="lower left")

    fig.tight_layout()
    _save(fig, "fig04_psd_spectral_tilt.png")
    plt.close(fig)


#: fig05's injected burst: its frequency and its window in ms.
BURST_HZ = 30.0
BURST_MS = (200.0, 400.0)


def fig05_complex_tfr():
    """Figure 5: Complex Morlet Wavelet TFR and Cone of Influence (COI)."""
    fig = plt.figure(figsize=(style.WIDTH, 4.6), dpi=style.DPI)
    # The colorbar takes a column of its own, so the two time axes keep one width.
    grid = fig.add_gridspec(2, 2, height_ratios=[1, 2], width_ratios=[1, 0.025])
    ax1 = fig.add_subplot(grid[0, 0])
    ax2 = fig.add_subplot(grid[1, 0], sharex=ax1)
    cax = fig.add_subplot(grid[1, 1])

    fs = 1000.0
    t = np.arange(700) / fs
    t_ms = t * 1000.0
    rng = np.random.default_rng(3)
    sig = rng.normal(0, 0.4, len(t))
    burst_mask = (t_ms >= BURST_MS[0]) & (t_ms <= BURST_MS[1])
    sig[burst_mask] += 2.0 * np.sin(2 * np.pi * BURST_HZ * t[burst_mask])

    ax1.plot(t_ms, sig, color=C_DARK, lw=style.LW_THIN)
    ax1.axvspan(*BURST_MS, color=C_HIGHLIGHT, alpha=0.4, lw=0)
    ax1.set_ylabel("LFP (a.u.)")
    style.panel_title(ax1, "A", "LFP signal with a transient oscillatory burst")
    ax1.tick_params(labelbottom=False)

    freqs = np.linspace(8.0, 60.0, 50)
    tfr = jnwb.complex_tfr(sig, fs=fs, freqs=freqs, n_cycles=5.0, normalization="amplitude")

    im = ax2.pcolormesh(t_ms, freqs, tfr.power, cmap="magma", shading="auto")
    cbar = fig.colorbar(im, cax=cax)
    cbar.set_label("Power (a.u.²)")

    # coi_mask is True where a coefficient is free of edge effects; the rest is veiled.
    excluded = (~tfr.coi_mask).astype(float)
    ax2.contourf(t_ms, freqs, excluded, levels=[0.5, 1.5], colors=[style.NEUTRAL], alpha=0.6)
    ax2.contour(t_ms, freqs, tfr.coi_mask.astype(float), levels=[0.5], colors=[style.SERIES[2]],
                linewidths=style.LW_THIN, linestyles="--")
    ax2.set_xlabel("Time (ms)")
    ax2.set_ylabel("Frequency (Hz)")
    style.panel_title(ax2, "B", "Complex Morlet TFR and cone of influence (jnwb.complex_tfr)")
    ax2.legend(handles=[
        Patch(color=C_HIGHLIGHT, alpha=0.4, label=f"Injected {BURST_HZ:.0f} Hz burst (panel A)"),
        Line2D([], [], color=style.SERIES[2], ls="--", lw=style.LW_THIN,
               label="Cone of influence (tfr.coi_mask)"),
        Patch(color=style.NEUTRAL, alpha=0.6, label="Edge-affected, excluded"),
    ], frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=3)

    fig.tight_layout()
    # tight_layout spaces the colorbar column like a panel; close it up to the TFR it keys.
    tfr_box = ax2.get_position()
    cax.set_position([tfr_box.x1 + 0.012, tfr_box.y0, 0.018, tfr_box.height])
    _save(fig, "fig05_complex_tfr_coi.png")
    plt.close(fig)


def fig06_aggregate_db():
    """Figure 6: Power ratio aggregation and the Log-Last rule."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(style.WIDTH, 3.2), dpi=style.DPI)

    rng = np.random.default_rng(99)
    n_units = 40
    baseline_power = rng.uniform(2.0, 15.0, n_units)
    # Per-unit modulation around 2.5x with the right-skewed spread of real power ratios
    power = baseline_power * rng.lognormal(np.log(2.5), 0.8, n_units)

    ratios = power / baseline_power
    db_individual = jnwb.to_db(ratios)

    # Method 1: mean of ratios (equal weight)
    db_mean_ratios = jnwb.aggregate_to_db(power, baseline_power, how="mean_of_ratios", aggregate_over=0)
    # Method 2: ratio of means (weighted by baseline power)
    db_ratio_means = jnwb.aggregate_to_db(power, baseline_power, how="ratio_of_means", aggregate_over=0)
    # Wrong: mean of decibels (Jensen inequality error)
    db_wrong_mean = float(np.mean(db_individual))

    # Panel A: Distribution of individual unit power ratios
    ax1.hist(ratios, bins=16, color=style.SERIES[0], edgecolor=C_DARK, lw=style.EDGE)
    ax1.axvline(np.mean(ratios), color=style.SERIES[3], lw=style.LW,
                label=f"Mean ratio ({np.mean(ratios):.2f})")
    ax1.set_xlabel("Power ratio (target / baseline)")
    ax1.set_ylabel("Unit count")
    style.panel_title(ax1, "A", "Per-unit power ratios")
    ax1.legend(frameon=False, loc="upper right")

    # Panel B: Aggregated Decibel Estimands
    labels = ["Mean of\nratios", "Ratio of\nmeans", "Mean of dB\n(Jensen error)"]
    values = [float(db_mean_ratios), float(db_ratio_means), db_wrong_mean]
    bars = ax2.bar(range(3), values, color=[style.SERIES[0], style.SERIES[2], style.SERIES[3]], width=0.55,
                   edgecolor=C_DARK, lw=style.EDGE)
    ax2.set_xticks(range(3))
    ax2.set_xticklabels(labels)
    for b, val in zip(bars, values):
        ax2.annotate(f"{style.num(val)} dB", (b.get_x() + b.get_width() / 2, val), xytext=(0, 3),
                     textcoords="offset points", ha="center", va="bottom", fontsize=style.SMALL,
                     fontweight="bold")
    ax2.set_ylim(0, max(values) * 1.2)
    ax2.set_ylabel("Aggregate (dB)")
    style.panel_title(ax2, "B", "Decibel aggregation\n(jnwb.aggregate_to_db)")

    fig.tight_layout()
    _save(fig, "fig06_aggregate_to_db.png")
    plt.close(fig)


#: Chance AUC: an uninformative score ranks a random positive above a random negative half the
#: time. F1 has no such constant, so no chance line is drawn for it.
AUC_CHANCE = 0.5


def fig07_decoding():
    """Figure 7: Population decoding with nested CV and majority baseline."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(style.WIDTH, 3.3), dpi=style.DPI)

    rng = np.random.default_rng(21)
    n_trials = 80
    n_feat = 10
    n_splits = 5
    labels = np.array([0] * 40 + [1] * 40)
    # Signal in feature 0 and 1
    X = rng.normal(0, 1.0, (n_trials, n_feat))
    X[labels == 1, :2] += 0.95

    res = jnwb.nested_cv_linear_svm(X, labels, n_splits=n_splits)
    fold_accs = res["fold_accuracies"]
    mean_acc = res["accuracy"]
    base_acc = res["majority_baseline_accuracy"]

    # Panel A: Fold Accuracies vs Baseline
    ax1.bar(range(1, len(fold_accs) + 1), fold_accs * 100, color=style.SERIES[0], width=0.5,
            edgecolor=C_DARK, lw=style.EDGE)
    ax1.axhline(mean_acc * 100, color=style.SERIES[3], ls="-", lw=style.LW,
                label=f"Outer-CV mean ({mean_acc * 100:.1f}%)")
    ax1.axhline(base_acc * 100, color=style.VARIABLE["baseline"], ls="--", lw=style.LW_THIN,
                label=f"Majority baseline ({base_acc * 100:.1f}%)")
    ax1.set_xlabel("Outer CV fold")
    ax1.set_ylabel("Decoding accuracy (%)")
    # Accuracy cannot pass 100%, so the band above it is free for the legend.
    ax1.set_ylim(0, 135)
    ax1.set_yticks(range(0, 101, 20))
    style.panel_title(ax1, "A", "Outer-fold accuracy\n(jnwb.nested_cv_linear_svm)")
    ax1.legend(frameon=False, loc="upper right")

    # Panel B: the out-of-fold AUC and F1 the decoder returns. The result carries no decision
    # scores, so no ROC curve can be drawn from it.
    scores = [res["auc"], res["f1"]]
    ax2.bar([0, 1], scores, color=style.SERIES[0], width=0.5, edgecolor=C_DARK,
            lw=style.EDGE)
    for i, value in enumerate(scores):
        ax2.annotate(f"{value:.2f}", (i, value), xytext=(0, 3), textcoords="offset points",
                     ha="center", va="bottom", fontsize=style.SMALL)
    ax2.hlines(AUC_CHANCE, -0.4, 0.4, color=style.NEUTRAL, ls=":", lw=style.LW_THIN,
               label=f"Chance AUC ({AUC_CHANCE:.2f})")
    ax2.set_xticks([0, 1])
    ax2.set_xticklabels(["AUC", "F1"])
    ax2.set_ylim(0, 1.3)
    ax2.set_yticks(np.linspace(0.0, 1.0, 6))
    ax2.set_ylabel("Out-of-fold score")
    style.panel_title(ax2, "B", "Out-of-fold AUC and F1\n(pooled over the outer folds)")
    ax2.legend(frameon=False, loc="upper right")

    fig.tight_layout()
    _save(fig, "fig07_population_decoding.png")
    plt.close(fig)


#: fig08's number of sign-flip draws, for the drawn null and for the p-value.
N_DRAWS = 2000
NULL_QUANTILE = 95.0


def fig08_permutation():
    """Figure 8: Within-pair sign-flip null distribution and a one-sided p-value."""
    fig, ax = plt.subplots(figsize=(style.WIDTH, 3.3), dpi=style.DPI)

    rng = np.random.default_rng(101)
    n = 60
    # Paired firing rates (Hz) under two conditions, with a true positive difference
    effect = rng.normal(0.18, 0.45, n)
    rate_b = rng.normal(10.0, 2.0, n)
    rate_a = rate_b + effect
    diffs = rate_a - rate_b

    # The null: condition labels exchanged within each pair, which flips that pair's sign
    values = np.concatenate([rate_a, rate_b])
    labels = np.repeat([1, 0], n)
    pairs = np.tile(np.arange(n), 2)
    null = np.empty(N_DRAWS)
    for i in range(N_DRAWS):
        swapped = jnwb.permute_labels(labels, groups=pairs, scheme="within_group", rng=rng)
        null[i] = np.where(swapped == 1, 1.0, -1.0) @ values / n
    observed, p_value, _ = jnwb.exact_sign_flip(diffs, alternative="greater", n_mc=N_DRAWS, rng=rng)

    ax.hist(null, bins=35, color=C_LIGHT_GRAY, edgecolor="none", density=True,
            label="Sign-flip null (labels exchanged within pairs)")
    ax.axvline(observed, color=style.VARIABLE["observed"], lw=style.LW_THICK,
               label=f"Observed mean difference ({style.num(observed, '.3f')} Hz)")
    ax.axvline(np.percentile(null, NULL_QUANTILE), color=style.SERIES[0], ls="--", lw=style.LW_THIN,
               label=f"{NULL_QUANTILE:.0f}th percentile of the null")
    top = ax.get_ylim()[1]
    ax.set_ylim(0, top * 1.45)
    ax.annotate(f"one-sided\nMonte Carlo\np = {p_value:.4f}", xy=(observed, top * 1.2),
                xytext=(-6, 0), textcoords="offset points", ha="right", va="center",
                fontsize=style.SMALL, fontweight="bold", color=C_DARK)

    ax.set_xlabel("Mean paired difference (Hz)")
    ax.set_ylabel("Probability density (1/Hz)")
    ax.set_title("Paired sign-flip null (jnwb.exact_sign_flip, jnwb.permute_labels)", pad=8)
    ax.legend(frameon=False, loc="upper left")

    fig.tight_layout()
    _save(fig, "fig08_permutation_null.png")
    plt.close(fig)


#: fig09's Granger order and the band its net PSI sums.
GC_ORDER = 15
PSI_BAND = (10.0, 45.0)


def fig09_directed_connectivity():
    """Figure 9: Directed Functional Connectivity (Granger causality & Phase Slope Index)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(style.WIDTH, 3.4), dpi=style.DPI)

    fs = 1000.0
    n_trials = 30
    n_t = 600
    rng = np.random.default_rng(55)

    # Simulate true directional lead X -> Y with delay = 10ms (10 samples)
    lag = 10
    x_trials = rng.normal(0, 1, (n_trials, n_t))
    # Filter to broadband 10-40 Hz
    from scipy.signal import butter, filtfilt
    b, a = butter(3, [12.0 / (fs / 2), 35.0 / (fs / 2)], btype="bandpass")
    x_filt = filtfilt(b, a, x_trials, axis=-1)

    y_trials = rng.normal(0, 0.6, (n_trials, n_t))
    y_trials[:, lag:] += 0.8 * x_filt[:, :-lag]

    # Panel A: Granger causality
    gc = jnwb.granger(x_filt, y_trials, order=GC_ORDER)
    bars = ax1.bar(["X → Y\n(simulated lead)", "Y → X\n(none simulated)"], [gc.x_to_y, gc.y_to_x],
                   color=[style.SERIES[0], style.NEUTRAL], width=0.5, edgecolor=C_DARK,
                   lw=style.EDGE)
    for b_item, val, p_val in zip(bars, [gc.x_to_y, gc.y_to_x], [gc.p_x_to_y, gc.p_y_to_x]):
        p_str = "p < 0.001" if p_val < 0.001 else f"p = {p_val:.3f}"
        ax1.annotate(f"{style.num(val, '.3f')}\n({p_str})", (b_item.get_x() + b_item.get_width() / 2, val),
                     xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                     fontsize=style.SMALL)
    ax1.set_ylabel("Log variance ratio")
    ax1.set_ylim(0, max(gc.x_to_y, gc.y_to_x) * 1.4)
    style.panel_title(ax1, "A", f"Bivariate Granger causality\n(jnwb.granger, order={GC_ORDER})")

    # Panel B: Phase Slope Index, per frequency bin, with the band the net value sums
    psi = jnwb.phase_slope_index(x_filt, y_trials, fs=fs, bands=PSI_BAND)
    psi_freqs = psi.spectrum["psi_freqs"]
    psi_spec = psi.spectrum["psi_per_freq"]
    mask = (psi_freqs >= 5.0) & (psi_freqs <= 50.0)
    # The net value sums the slope terms between adjacent spectral bins inside the band, so the
    # shading spans the first to the last of those bins, not the band's nominal edges.
    f_lo, f_hi = psi.per_band["band"]["band_hz"]
    freqs = psi.spectrum["freqs"]
    summed = freqs[(freqs >= f_lo) & (freqs <= f_hi)]
    ax2.axvspan(summed[0], summed[-1], color=C_HIGHLIGHT, alpha=0.4, lw=0,
                label=f"Summed bins ({summed[0]:.1f}–{summed[-1]:.1f} Hz)")
    ax2.plot(psi_freqs[mask], psi_spec[mask], color=style.SERIES[0], lw=style.LW, marker="o",
             ms=3.5, label=f"Net PSI = {style.num(psi.x_to_y, '+.3f')} (positive: X leads Y)")
    ax2.axhline(0, color=style.NEUTRAL, ls="--", lw=style.LW_THIN)
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("PSI per frequency bin (dimensionless)")
    style.panel_title(ax2, "B", "Phase slope index spectrum\n(jnwb.phase_slope_index)")
    ax2.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2))

    fig.tight_layout()
    _save(fig, "fig09_directed_connectivity.png")
    plt.close(fig)


#: fig10's detection threshold and contaminated trial.
Z_THRESH = 5.0
HIT_TRIAL = 5
#: Length of fig10's amplitude scale bar.
SCALE_AU = 30.0


def fig10_artifact_repair():
    """Figure 10: Multichannel trial-segmented LFP artifact detection and repair."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(style.WIDTH, 3.2), dpi=style.DPI)

    rng = np.random.default_rng(88)
    n_trials, n_ch, n_t = 30, 8, 500
    t = np.arange(n_t)
    seg = rng.normal(0, 1.0, (n_trials, n_ch, n_t))
    seg += 1.8 * np.sin(2 * np.pi * 12.0 * t / 1000.0)

    # Inject massive synchronous transient
    seg[HIT_TRIAL, :, 180:240] += 35.0

    repaired, frac, diag = jnwb.repair_lfp_trials(seg, times_ms=t, z_thresh=Z_THRESH)
    raw = seg[HIT_TRIAL, 0]
    # Both legends sit below their axes, so the traces keep the full height.
    y_lo, y_hi = float(raw.min()), float(raw.max())
    y_lim = (y_lo - 2.0, y_hi + 0.08 * (y_hi - y_lo))
    y_ticks = np.arange(0.0, y_hi, 10.0)

    # Panel A: every channel of the contaminated trial, stacked, so the artifact reads as
    # synchronous across channels, which is what the detector scores. Channel 0 is on top, as
    # in the addressing figure; each trace keeps its polarity (positive up).
    spacing = 1.2 * (y_hi - y_lo)
    offsets = -np.arange(n_ch) * spacing
    for ch in range(n_ch):
        ax1.plot(t, seg[HIT_TRIAL, ch] + offsets[ch], color=style.VARIABLE["observed"],
                 lw=style.LW_THIN,
                 label="Raw (contaminated), one trace per channel" if ch == 0 else None)
    ax1.set_xlabel("Time (ms)")
    ax1.set_ylabel("Channel index")
    ax1.set_yticks(offsets, [str(ch) for ch in range(n_ch)])
    # Amplitude scale: one bar of SCALE_AU rising from the last channel's baseline
    x_bar = t[-1] + 25
    ax1.plot([x_bar, x_bar], [offsets[-1], offsets[-1] + SCALE_AU], color=C_DARK, lw=style.LW)
    ax1.annotate(f"{SCALE_AU:.0f} a.u.", xy=(x_bar, offsets[-1] + SCALE_AU / 2), xytext=(4, 0),
                 textcoords="offset points", va="center", fontsize=style.SMALL, color=C_DARK)
    ax1.set_xlim(-10, t[-1] + 110)
    ax1.set_xticks(np.arange(0, t[-1] + 1, 100))
    style.panel_title(ax1, "A", f"Injected synchronous artifact\n(trial {HIT_TRIAL}, "
                                f"peak z = {diag['synchrony_z_max']:.0f})")
    ax1.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2))

    # Panel B: the same channel before and after repair
    ax2.plot(t, raw, color=style.VARIABLE["observed"], lw=style.LW_THIN,
             label="Raw (contaminated), channel 0")
    ax2.plot(t, repaired[HIT_TRIAL, 0], color=style.SERIES[0], lw=style.LW_THIN,
             label="Repaired (median substitution)")
    # The shaded samples are the detector's output: every sample the repair changed on any channel.
    replaced = np.any(repaired[HIT_TRIAL] != seg[HIT_TRIAL], axis=0)
    ax2.fill_between(t, y_lo, y_hi, where=replaced, step="mid", color=C_HIGHLIGHT,
                     alpha=0.4, lw=0, label=f"Samples replaced (z_thresh = {Z_THRESH:.1f})")
    ax2.set_ylim(*y_lim)
    ax2.set_yticks(y_ticks)
    ax2.set_xlabel("Time (ms)")
    ax2.set_ylabel("LFP (a.u.)")
    style.panel_title(ax2, "B", "Repaired signal overlay\n(jnwb.repair_lfp_trials)")
    ax2.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)

    fig.tight_layout()
    _save(fig, "fig10_artifact_repair.png")
    plt.close(fig)


def _band_label(name: str) -> str:
    """A canonical band's name as the figure writes it: `low_gamma` is `low γ`."""
    return name.replace("_", " ").replace("gamma", "γ")


def fig11_spectra_bands():
    """Figure 11: Welch and multitaper PSDs of one synthetic signal, with the canonical bands shaded."""
    fig, ax = plt.subplots(figsize=(style.WIDTH, 3.4), dpi=style.DPI)

    fs = 1000.0
    rng = np.random.default_rng(31)
    t = np.arange(int(10.0 * fs)) / fs
    # Random-walk background, whose spectrum falls as 1/f squared, + 10, 22 and 40 Hz rhythms
    pink = np.cumsum(rng.standard_normal(len(t)))
    pink -= pink.mean()
    pink /= pink.std()
    lfp = (pink + 0.8 * np.sin(2 * np.pi * 10.0 * t) + 0.5 * np.sin(2 * np.pi * 22.0 * t)
           + 0.3 * np.sin(2 * np.pi * 40.0 * t))

    freqs, psd = jnwb.compute_psd(lfp, fs=fs)
    freqs_mt, psd_mt = jnwb.compute_multitaper_psd(lfp, fs=fs, nw=3.0, k_tapers=5)
    shown, shown_mt = (freqs >= 1.0) & (freqs <= 100.0), (freqs_mt >= 1.0) & (freqs_mt <= 100.0)

    ax.set_xscale("log")
    ax.set_yscale("log")
    for index, (name, (low, high)) in enumerate(jnwb.CANONICAL_BANDS.items()):
        # Alternate bands are shaded, so every boundary between two bands is an edge of shading.
        if index % 2 == 0:
            ax.axvspan(low, high, color=style.NEUTRAL, alpha=0.2, lw=0)
        # Each band is named above the axes, over its span, so no name sits on a band or a spectrum.
        ax.text(np.sqrt(low * high), 1.01, _band_label(name), transform=ax.get_xaxis_transform(),
                ha="center", va="bottom", fontsize=style.SMALL, color=C_DARK)
    ax.plot(freqs[shown], psd[shown], color=style.SERIES[0], lw=style.LW_THIN, label="Welch")
    ax.plot(freqs_mt[shown_mt], psd_mt[shown_mt], color=style.SERIES[1], lw=style.LW,
            label="Multitaper")
    top = max(float(psd[shown].max()), float(psd_mt[shown_mt].max()))
    bottom = min(float(psd[shown].min()), float(psd_mt[shown_mt].min()))
    ax.set_ylim(bottom / 2.0, top * 10.0 ** 0.3)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Power spectral density (a.u.²/Hz)")
    ax.set_title("Welch (jnwb.compute_psd) and multitaper (jnwb.compute_multitaper_psd) PSDs",
                 pad=16)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)

    fig.tight_layout()
    _save(fig, "fig11_spectra_canonical_bands.png")
    plt.close(fig)


#: fig12's record length and Welch segment length, in seconds and samples at 1000 Hz, and the lag
#: of channel y in panel B, in samples. 60 s (119 segments) keeps this step under 30 s; the wPLI of
#: two independent channels is biased upward at few segments.
FIG12_SECONDS = 60
FIG12_NPERSEG = 1000
FIG12_LAG_SAMPLES = 5
#: The frequencies fig12 draws, in Hz.
FIG12_BAND_HZ = (2.0, 60.0)


def _fig12_pair(lagged: bool):
    """Two channels that share two rhythms. Both panels draw the same source and the same noise;
    panel B delays channel y by a fixed lag, and panel A does not."""
    fs = 1000.0
    rng = np.random.default_rng(64)
    t = np.arange(int(FIG12_SECONDS * fs)) / fs
    source = np.sin(2 * np.pi * 12.0 * t) + np.sin(2 * np.pi * 22.0 * t)
    x = source + 0.8 * rng.standard_normal(len(t))
    noise_y = 0.8 * rng.standard_normal(len(t))
    shared = np.roll(source, FIG12_LAG_SAMPLES) if lagged else source
    return x, 0.7 * shared + noise_y


def _fig12_panel(ax, letter: str, lagged: bool, title: str):
    """Coherence, |imaginary coherency| and wPLI against frequency for one condition."""
    fs = 1000.0
    x, y = _fig12_pair(lagged)
    coherence = jnwb.cross_area_coherence(x, y, fs=fs, freq_bands=jnwb.CANONICAL_BANDS,
                                          nperseg=FIG12_NPERSEG)
    wpli = jnwb.wpli(x, y, fs=fs, freq_range=FIG12_BAND_HZ, nperseg=FIG12_NPERSEG)
    coh_f, coh = coherence["frequencies"], coherence["coherence_spectrum"]
    shown_coh = (coh_f >= FIG12_BAND_HZ[0]) & (coh_f <= FIG12_BAND_HZ[1])
    freqs = wpli["freqs"]
    shown = (freqs >= FIG12_BAND_HZ[0]) & (freqs <= FIG12_BAND_HZ[1])
    # One frequency bin per window: imaginary_coherency returns a mean over its band, so a
    # window of one bin gives the value at that bin.
    icoh = [jnwb.imaginary_coherency(x, y, fs=fs, freq_range=(f - 0.5, f + 0.5),
                                     nperseg=FIG12_NPERSEG)["icoh_abs_mean"] for f in freqs[shown]]

    ax.plot(coh_f[shown_coh], coh[shown_coh], color=style.SERIES[0], lw=style.LW)
    ax.plot(freqs[shown], icoh, color=style.SERIES[1], lw=style.LW)
    ax.plot(freqs[shown], wpli["wpli_spectrum"][shown], color=style.SERIES[2], lw=style.LW)
    ax.set_xlim(*FIG12_BAND_HZ)
    ax.set_ylim(0.0, 1.05)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Estimate (dimensionless)")
    style.panel_title(ax, letter, title.format(segments=wpli["n_segments"]))


def fig12_coherence_zero_lag():
    """Figure 12: Coherence, |imaginary coherency| and wPLI against frequency, for two channels
    that share a rhythm at zero lag (A) and with a fixed lag on one channel (B)."""
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(style.WIDTH, 3.6), dpi=style.DPI, sharey=True)

    _fig12_panel(ax_a, "A", False, "Zero lag ({segments} Welch segments)")
    _fig12_panel(ax_b, "B", True, "Fixed lag on channel y ({segments} segments)")
    fig.legend(handles=[
        Line2D([], [], color=style.SERIES[0], lw=style.LW, label="Coherence"),
        Line2D([], [], color=style.SERIES[1], lw=style.LW, label="|Imaginary coherency|"),
        Line2D([], [], color=style.SERIES[2], lw=style.LW, label="wPLI"),
    ], frameon=False, loc="lower center", ncol=3)

    fig.tight_layout(rect=(0.0, 0.1, 1.0, 1.0))
    _save(fig, "fig12_coherence_zero_lag.png")
    plt.close(fig)


#: fig13's synthetic motif: the seed it is drawn with, and the contact spacing in micrometres. The
#: motif is drawn at the regime vFLIP is calibrated for: 5000 samples at 1000 Hz and SNR 20.
FIG13_SEED = 7
FIG13_PITCH_UM = 50.0


def _band_profiles(psd: np.ndarray, freqs: np.ndarray, bands) -> list:
    """The band depth profiles vflip forms before it locates the crossover: each frequency column
    of the PSD is min-max normalized across contacts, then averaged over the bins of each band."""
    scaled = psd / np.max(np.abs(psd))
    lowest = scaled.min(axis=0)
    span = scaled.max(axis=0) - lowest
    span[span < 1e-12] = 1e-12
    normed = (scaled - lowest) / span
    return [normed[:, (freqs >= lo) & (freqs <= hi)].mean(axis=1) for lo, hi in bands]


def fig13_vflip_band_profiles():
    """Figure 13: The low-band and high-band depth profiles that vflip_from_lfp locates its crossover
    on, with the true crossover and the vFLIP estimate of it, for a synthetic laminar motif."""
    fig, ax = plt.subplots(figsize=(style.WIDTH, 3.6), dpi=style.DPI)

    fs = 1000.0
    motif = synth_laminar_motif(n_channels=24, n_samples=5000, fs=fs, pitch_um=FIG13_PITCH_UM,
                                snr=20.0, rng=FIG13_SEED)
    lfp = motif.lfp
    vflip = jnwb.vflip_from_lfp(lfp, fs, orientation=motif.orientation,
                                contact_spacing=FIG13_PITCH_UM)
    assert vflip.accepted, vflip.rejection_reason

    # The PSD vflip_from_lfp computes: the same Welch length, overlap, window and detrend. The
    # bands are the constant its defaults are taken from.
    freqs, psd = jnwb.compute_psd(lfp, fs=fs, axis=1)
    bands = (CANONICAL_VFLIP_BANDS["low"], CANONICAL_VFLIP_BANDS["high"])
    low, high = _band_profiles(psd, freqs, bands)

    depth_um = np.arange(lfp.shape[0]) * FIG13_PITCH_UM
    ax.plot(low, depth_um, color=style.SERIES[0], lw=style.LW,
            label=f"low band, {bands[0][0]:g}-{bands[0][1]:g} Hz")
    ax.plot(high, depth_um, color=style.SERIES[3], lw=style.LW,
            label=f"high band, {bands[1][0]:g}-{bands[1][1]:g} Hz")
    ax.axhline(motif.crossover_depth_um, color=style.VARIABLE["truth"], ls=":", lw=style.LW,
               label="true")
    ax.axhline(vflip.crossover_depth_um, color=C_DARK, ls="--", lw=style.LW_THIN,
               label="vFLIP estimate")
    ax.invert_yaxis()
    ax.set_xlim(0.0, 1.0)
    ax.set_xlabel("Normalized band power (dimensionless)")
    ax.set_ylabel("Depth (µm)")
    ax.set_title("Band power by depth (jnwb.vflip_from_lfp)", pad=8)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)

    fig.tight_layout()
    _save(fig, "fig13_vflip_band_profiles.png")
    plt.close(fig)


#: fig14's rate step: the bin width, the onset, the baseline and plateau rates in Hz, and the causal
#: filter's tau and the Gaussian's sigma, in ms.
FIG14_BIN_MS = 1.0
FIG14_ONSET_MS = 100.0
FIG14_BASE_HZ = 5.0
FIG14_PLATEAU_HZ = 40.0
FIG14_TAU_MS = 50.0
FIG14_SIGMA_MS = 20.0


def _first_rise(t, y, level):
    """The time a rising trace first reaches `level`, interpolated between the two bins it crosses."""
    i = int(np.argmax(y >= level))
    assert i > 0 and y[i] >= level, "the trace never rises to the level"
    return float(np.interp(level, y[i - 1:i + 1], t[i - 1:i + 1]))


def fig14_causal_vs_gaussian_step():
    """Figure 14: A noiseless rate step smoothed causally and with a symmetric Gaussian kernel."""
    fig, ax = plt.subplots(figsize=(style.WIDTH, 3.8), dpi=style.DPI)

    t = np.arange(-200.0, 400.0, FIG14_BIN_MS)
    rate = np.where(t >= FIG14_ONSET_MS, FIG14_PLATEAU_HZ, FIG14_BASE_HZ)
    causal = jnwb.causal_exp_smooth(rate, bin_ms=FIG14_BIN_MS, tau_ms=FIG14_TAU_MS)
    gauss = jnwb.gaussian_smooth_rate(rate, bin_ms=FIG14_BIN_MS, sigma_ms=FIG14_SIGMA_MS)

    step = FIG14_PLATEAU_HZ - FIG14_BASE_HZ
    half, tenth = FIG14_BASE_HZ + 0.5 * step, FIG14_BASE_HZ + 0.1 * step
    causal_half = _first_rise(t, causal, half)
    gauss_half = _first_rise(t, gauss, half)
    gauss_tenth = _first_rise(t, gauss, tenth)
    causal_delay = causal_half - FIG14_ONSET_MS
    gauss_lead = FIG14_ONSET_MS - gauss_tenth

    ax.plot(t, rate, color=style.VARIABLE["truth"], ls=":", lw=style.LW,
            label=f"Noiseless step, onset {FIG14_ONSET_MS:.0f} ms")
    ax.plot(t, causal, color=style.VARIABLE["smoothed"], lw=style.LW,
            label=f"Causal, tau = {FIG14_TAU_MS:.0f} ms: 50% crossing "
                  f"{style.num(causal_delay, '+.1f')} ms after onset")
    ax.plot(t, gauss, color=style.SERIES[0], ls="--", lw=style.LW,
            label=f"Gaussian, sigma = {FIG14_SIGMA_MS:.0f} ms: 10% rise "
                  f"{gauss_lead:.1f} ms before onset")
    # The 50% crossings and the Gaussian's 10% rise, marked on their curves, against the onset.
    ax.axvline(FIG14_ONSET_MS, color=style.NEUTRAL, lw=style.LW_THIN)
    ax.scatter([causal_half, gauss_half, gauss_tenth], [half, half, tenth], s=24, zorder=4,
               c=[style.VARIABLE["smoothed"], style.SERIES[0], style.SERIES[0]],
               edgecolors=C_DARK, linewidths=style.EDGE)
    ax.text(FIG14_ONSET_MS + 3.0, 0.97, "true onset", transform=ax.get_xaxis_transform(),
            ha="left", va="top", fontsize=style.SMALL, color=C_DARK)

    ax.set_ylim(0.0, FIG14_PLATEAU_HZ * 1.45)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Firing rate (Hz)")
    ax.set_title("Smoothing a noiseless rate step\n"
                 "(jnwb.causal_exp_smooth, jnwb.gaussian_smooth_rate)", pad=8)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2))

    fig.tight_layout()
    _save(fig, "fig14_causal_vs_gaussian_step.png")
    plt.close(fig)


#: fig15's LFP: its frequency, duration and sampling rate. The locked unit's preferred phase in
#: radians, its concentration and its spike count; the uniform control has the same spike count.
FIG15_LFP_HZ = 10.0
FIG15_SECONDS = 60.0
FIG15_FS = 1000.0
FIG15_MU = np.pi / 4
FIG15_KAPPA = 2.0
FIG15_N_SPIKES = 400
FIG15_BINS = 18
FIG15_SEED = 15


def _spike_phases(spike_times, lfp_phase, lfp_timestamps):
    """The LFP phase at each spike, interpolated through its unit vector as phase_locking_index does."""
    cos_phase = np.interp(spike_times, lfp_timestamps, np.cos(lfp_phase))
    sin_phase = np.interp(spike_times, lfp_timestamps, np.sin(lfp_phase))
    return np.arctan2(sin_phase, cos_phase)


def _phase_panel(ax, letter: str, name: str, result: dict, ppc: float):
    """A polar histogram of spike phases, with the preferred phase and the statistics its result returns."""
    edges = np.linspace(-np.pi, np.pi, FIG15_BINS + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    counts = result["phase_hist"]
    top = float(counts.max()) * 1.2
    ax.bar(centers, counts, width=2 * np.pi / FIG15_BINS, color=style.SERIES[0], edgecolor=C_DARK,
           lw=style.EDGE)
    ax.plot([result["preferred_phase"]] * 2, [0.0, top], color=style.SERIES[1], ls="--", lw=style.LW)
    ax.set_rlim(0.0, top)
    ax.set_yticklabels([])  # the radius is the spike count of one 20-degree bin; no radial scale
    ax.grid(True, color=style.NEUTRAL, linewidth=style.EDGE)
    style.panel_title(ax, letter, f"{name}, {result['n_spikes']} spikes\n(jnwb.phase_locking_index)")
    ax.legend(handles=[
        Line2D([], [], color=style.SERIES[1], ls="--", lw=style.LW,
               label=f"Preferred phase {style.num(result['preferred_phase'], '.2f')} rad"),
        Patch(visible=False, label=f"Rayleigh z = {style.num(result['rayleigh_z'], '.1f')}"),
        Patch(visible=False, label=f"PPC = {style.num(ppc, '.3f')} (jnwb.pairwise_phase_consistency)"),
    ], frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12))


def fig15_spike_phase_locking():
    """Figure 15: Spike phases against a 10 Hz LFP, for a phase-locked unit and a uniform control."""
    fig = plt.figure(figsize=(style.WIDTH, 4.8), dpi=style.DPI)
    ax1 = fig.add_subplot(1, 2, 1, projection="polar")
    ax2 = fig.add_subplot(1, 2, 2, projection="polar")

    rng = np.random.default_rng(FIG15_SEED)
    n_cycles = int(FIG15_SECONDS * FIG15_LFP_HZ)
    # A spike in cycle k at LFP phase phi sits at (k + phi / 2 pi) / f, so its LFP phase is phi.
    cycle = rng.integers(0, n_cycles, FIG15_N_SPIKES)
    phi = np.mod(rng.vonmises(FIG15_MU, FIG15_KAPPA, FIG15_N_SPIKES), 2 * np.pi)
    locked_times = np.sort((cycle + phi / (2 * np.pi)) / FIG15_LFP_HZ)
    uniform_cycle = rng.integers(0, n_cycles, FIG15_N_SPIKES)
    uniform_times = np.sort((uniform_cycle + rng.uniform(0.0, 1.0, FIG15_N_SPIKES)) / FIG15_LFP_HZ)

    lfp_timestamps = np.arange(int(FIG15_SECONDS * FIG15_FS)) / FIG15_FS
    lfp_phase = np.angle(np.exp(2j * np.pi * FIG15_LFP_HZ * lfp_timestamps))
    locked = jnwb.phase_locking_index(locked_times, lfp_phase, lfp_timestamps, n_bins=FIG15_BINS)
    control = jnwb.phase_locking_index(uniform_times, lfp_phase, lfp_timestamps, n_bins=FIG15_BINS)
    ppc_locked = jnwb.pairwise_phase_consistency(_spike_phases(locked_times, lfp_phase, lfp_timestamps))
    ppc_control = jnwb.pairwise_phase_consistency(_spike_phases(uniform_times, lfp_phase, lfp_timestamps))
    # PPC must read the phases phase_locking_index binned; a drift in either copy fails here.
    for times, result in ((locked_times, locked), (uniform_times, control)):
        phases = _spike_phases(times, lfp_phase, lfp_timestamps)
        hist = np.histogram(phases, bins=FIG15_BINS, range=(-np.pi, np.pi))[0]
        assert np.array_equal(hist, result["phase_hist"]), "fig15's phases differ from the library's"

    _phase_panel(ax1, "A", "Phase-locked unit", locked, ppc_locked)
    _phase_panel(ax2, "B", "Uniform-phase control", control, ppc_control)

    fig.tight_layout()
    _save(fig, "fig15_spike_phase_locking.png")
    plt.close(fig)


#: fig16's simulated conditions: the sampling rate, the epoch start in ms, the sample count, the
#: frequency grid and the trials per condition. Condition B alone carries a 30 Hz burst from 200 to
#: 400 ms. The caption names the permutation count and alpha.
FIG16_FS = 500.0
FIG16_START_MS = -200.0
FIG16_N = 500
FIG16_FREQS = np.arange(8.0, 61.0, 2.0)
FIG16_TRIALS = 20
FIG16_CYCLES = 5.0
FIG16_TAIL = "both"
FIG16_PLANT_HZ = 30.0
FIG16_PLANT_MS = (200.0, 400.0)
FIG16_PLANT_AMP = 1.2
FIG16_THRESHOLD = 2.5
FIG16_PERMUTATIONS = 1000
FIG16_ALPHA = 0.05
FIG16_SEED = 16
FIG16_PERM_SEED = 160


def fig16_cluster_permutation():
    """Figure 16: A planted time-frequency difference and the significant cluster that tests it."""
    fig, ax = plt.subplots(figsize=(style.WIDTH, 3.6), dpi=style.DPI)

    rng = np.random.default_rng(FIG16_SEED)
    t_ms = FIG16_START_MS + np.arange(FIG16_N) * 1000.0 / FIG16_FS
    burst = (t_ms >= FIG16_PLANT_MS[0]) & (t_ms <= FIG16_PLANT_MS[1])
    cond_a = rng.normal(0.0, 1.0, (FIG16_TRIALS, FIG16_N))
    cond_b = rng.normal(0.0, 1.0, (FIG16_TRIALS, FIG16_N))
    cond_b[:, burst] += FIG16_PLANT_AMP * np.sin(2 * np.pi * FIG16_PLANT_HZ * t_ms[burst] / 1000.0)
    power_a = jnwb.complex_tfr(cond_a, fs=FIG16_FS, freqs=FIG16_FREQS, n_cycles=FIG16_CYCLES).power
    power_b = jnwb.complex_tfr(cond_b, fs=FIG16_FS, freqs=FIG16_FREQS, n_cycles=FIG16_CYCLES).power

    result = jnwb.cluster_permutation_test(
        power_b, power_a, paired=False, threshold=FIG16_THRESHOLD, n_permutations=FIG16_PERMUTATIONS,
        tail=FIG16_TAIL, rng=np.random.default_rng(FIG16_PERM_SEED))
    significant = [c for c in result["clusters"] if c["p_value"] < FIG16_ALPHA]
    assert len(significant) == 1, f"fig16 must hold one significant cluster; it holds {len(significant)}"
    cluster = significant[0]

    diff = power_b.mean(axis=0) - power_a.mean(axis=0)
    limit = float(np.abs(diff).max())
    mesh = ax.pcolormesh(t_ms, FIG16_FREQS, diff, cmap="RdBu_r", vmin=-limit, vmax=limit, shading="auto")
    ax.contour(t_ms, FIG16_FREQS, cluster["mask"].astype(float), levels=[0.5],
               colors=[style.SERIES[2]], linewidths=style.LW_THIN)
    cbar = fig.colorbar(mesh, ax=ax, pad=0.02)
    cbar.set_label("Power difference, B minus A (a.u.²)")

    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title("Cluster-based permutation test (jnwb.cluster_permutation_test)", pad=8)
    ax.legend(handles=[
        Line2D([], [], color=style.SERIES[2], lw=style.LW_THIN,
               label=f"Significant cluster, p = {cluster['p_value']:.3f} "
                     f"({FIG16_PERMUTATIONS} permutations)"),
        Patch(visible=False, label=f"Planted effect: {FIG16_PLANT_HZ:.0f} Hz in B, "
                                   f"{FIG16_PLANT_MS[0]:.0f}–{FIG16_PLANT_MS[1]:.0f} ms"),
    ], frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2))

    fig.tight_layout()
    _save(fig, "fig16_cluster_permutation.png")
    plt.close(fig)


#: fig17's pair: the sampling rate, the length in samples, X's resonance frequency and pole radius,
#: the band summarized, the lag of X's drive on Y, its gain, the noise on Y, the highest frequency
#: drawn and the seed.
FIG17_FS = 1000.0
FIG17_N = 4000
FIG17_PEAK_HZ = 22.0
FIG17_POLE_RADIUS = 0.97
FIG17_BAND_HZ = (14.0, 30.0)
FIG17_LAG_MS = 8.0
FIG17_GAIN = 0.8
FIG17_NOISE = 0.6
FIG17_SHOWN_HZ = 100.0
FIG17_SEED = 17


def fig17_spectral_granger():
    """Figure 17: Spectral Granger causality in both directions for a pair in which X drives Y."""
    from scipy.signal import lfilter

    fig, ax = plt.subplots(figsize=(style.WIDTH, 3.6), dpi=style.DPI)

    rng = np.random.default_rng(FIG17_SEED)
    # X is a causal AR(2) resonance and Y a lagged copy plus noise, so the pair is itself a VAR of
    # low order, which the model behind granger_spectral can fit without reaching max_lag.
    theta = 2.0 * np.pi * FIG17_PEAK_HZ / FIG17_FS
    poles = [1.0, -2.0 * FIG17_POLE_RADIUS * np.cos(theta), FIG17_POLE_RADIUS ** 2]
    x = lfilter([1.0], poles, rng.normal(0.0, 1.0, FIG17_N))
    x /= np.std(x)
    lag = int(round(FIG17_LAG_MS * FIG17_FS / 1000.0))
    y = rng.normal(0.0, FIG17_NOISE, FIG17_N)
    y[lag:] += FIG17_GAIN * x[:-lag]

    result = jnwb.granger_spectral(x, y, fs=FIG17_FS, bands={"beta": FIG17_BAND_HZ})
    assert result.diagnostics["ok_for_interpretation"], result.diagnostics["warnings"]
    freqs = result.spectrum["freqs"]
    shown = freqs <= FIG17_SHOWN_HZ
    beta = result.per_band["beta"]
    ax.axvspan(*FIG17_BAND_HZ, color=C_HIGHLIGHT, alpha=0.4, lw=0,
               label=f"Band summarized, {FIG17_BAND_HZ[0]:.0f}–{FIG17_BAND_HZ[1]:.0f} Hz "
                     f"(X resonates at {FIG17_PEAK_HZ:.0f} Hz)")
    ax.plot(freqs[shown], result.spectrum["gc_x_to_y"][shown], color=style.SERIES[0], lw=style.LW,
            label=f"X → Y, band mean {style.num(beta['value'], '.3f')}")
    ax.plot(freqs[shown], result.spectrum["gc_y_to_x"][shown], color=style.SERIES[1], lw=style.LW,
            ls="--", label=f"Y → X, band mean {style.num(beta['value_reverse'], '.3f')}")

    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Log variance ratio (spectral Granger)")
    ax.set_title("Spectral Granger causality (jnwb.granger_spectral)", pad=8)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2))

    fig.tight_layout()
    _save(fig, "fig17_spectral_granger.png")
    plt.close(fig)


#: fig18's pair: the sampling rate, the length in samples, the delay of Y behind X in ms, the noise
#: on Y, the narrow and broad bands, the frequency range drawn and the seed.
FIG18_FS = 1000.0
FIG18_N = 2000
FIG18_DELAY_MS = 10.0
FIG18_NOISE = 0.3
FIG18_NARROW_HZ = (18.0, 24.0)
FIG18_BROAD_HZ = (15.0, 30.0)
FIG18_SHOWN_HZ = (5.0, 50.0)
FIG18_SEED = 42


def _psi_panel(ax, letter: str, name: str, band, result, ylim):
    """PSI per frequency bin, the bins its net value sums, and the net value and z that band gave."""
    freqs = result.spectrum["psi_freqs"]
    shown = (freqs >= FIG18_SHOWN_HZ[0]) & (freqs <= FIG18_SHOWN_HZ[1])
    stats = result.per_band["band"]
    # Each PSI point sits between two adjacent FFT bins, and the net sums only the points whose
    # two bins both lie in the band, so the marking spans the band's bins, not its nominal edges.
    bins = result.spectrum["freqs"]
    summed = bins[(bins >= band[0]) & (bins <= band[1])]
    if summed.size == 1:
        ax.axvline(summed[0], color=C_HIGHLIGHT, lw=style.LW_THICK,
                   label=f"One bin in band, {summed[0]:.2f} Hz: no slope term")
    else:
        ax.axvspan(summed[0], summed[-1], color=C_HIGHLIGHT, alpha=0.4, lw=0,
                   label=f"Summed bins, {summed[0]:.1f}–{summed[-1]:.1f} Hz ({summed.size} bins)")
    ax.plot(freqs[shown], result.spectrum["psi_per_freq"][shown], color=style.SERIES[0], lw=style.LW,
            marker="o", ms=3.5,
            label=f"Net PSI = {style.num(result.net, '.3f')}, z = {style.num(stats['z'], '.2f')}")
    ax.axhline(0, color=style.NEUTRAL, ls="--", lw=style.LW_THIN)
    ax.set_ylim(*ylim)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("PSI per frequency bin (dimensionless)")
    style.panel_title(ax, letter, f"{name}, {band[0]:.0f}–{band[1]:.0f} Hz\n(jnwb.phase_slope_index)")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2))


def fig18_psi_narrowband_trap():
    """Figure 18: Phase slope index over a narrowband and a broadband band of one delayed pair."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(style.WIDTH, 3.6), dpi=style.DPI)

    rng = np.random.default_rng(FIG18_SEED)
    x = rng.normal(size=FIG18_N)
    lag = int(round(FIG18_DELAY_MS * FIG18_FS / 1000.0))
    y = np.roll(x, lag) + FIG18_NOISE * rng.normal(size=FIG18_N)
    narrow = jnwb.phase_slope_index(x, y, fs=FIG18_FS, bands=FIG18_NARROW_HZ)
    broad = jnwb.phase_slope_index(x, y, fs=FIG18_FS, bands=FIG18_BROAD_HZ)
    assert narrow.per_band["band"]["n_freq_bins"] == 1, "fig18's narrow band must hold one bin"

    # One vertical scale for both panels, read from the two drawn spectra, so the bands compare by eye.
    lo_hi = FIG18_SHOWN_HZ
    values = np.concatenate([
        r.spectrum["psi_per_freq"][(r.spectrum["psi_freqs"] >= lo_hi[0]) & (r.spectrum["psi_freqs"] <= lo_hi[1])]
        for r in (narrow, broad)])
    pad = 0.15 * (float(values.max()) - float(values.min()))
    ylim = (float(values.min()) - pad, float(values.max()) + pad)

    _psi_panel(ax1, "A", "Narrowband", FIG18_NARROW_HZ, narrow, ylim)
    _psi_panel(ax2, "B", "Broadband", FIG18_BROAD_HZ, broad, ylim)

    fig.tight_layout()
    _save(fig, "fig18_psi_narrowband_trap.png")
    plt.close(fig)


#: fig19's two populations: conditions, units and samples; the shared pattern rides on a Gaussian
#: envelope, and each population also carries a private pattern and noise.
FIG19_SEED = 19
FIG19_N_COND = 12
FIG19_N_UNITS = 40
FIG19_N_SHARED = 2
FIG19_N_PRIVATE = 2
FIG19_N_SAMPLES = 120
FIG19_PEAK = 60
FIG19_ENVELOPE_SD = 12.0
FIG19_NOISE = 0.5
FIG19_PRIVATE_GAIN = 0.5
#: fig19's jRSA trace: the window and step in samples, the permutations per window, and the
#: percentiles that bound the null band.
FIG19_WINDOW = 20
FIG19_STEP = 10
FIG19_PERMUTATIONS = 1000
FIG19_BAND_PCT = (2.5, 97.5)


def _fig19_populations():
    """Two (conditions, units, samples) populations sharing one condition pattern while the envelope is up."""
    rng = np.random.default_rng(FIG19_SEED)
    t = np.arange(FIG19_N_SAMPLES)
    envelope = np.exp(-0.5 * ((t - FIG19_PEAK) / FIG19_ENVELOPE_SD) ** 2)
    shared = rng.standard_normal((FIG19_N_COND, FIG19_N_SHARED))
    populations = []
    for _ in range(2):
        private = rng.standard_normal((FIG19_N_COND, FIG19_N_PRIVATE))
        units_shared = rng.standard_normal((FIG19_N_UNITS, FIG19_N_SHARED))
        units_private = rng.standard_normal((FIG19_N_UNITS, FIG19_N_PRIVATE))
        drive = ((shared @ units_shared.T)[:, :, None] * envelope
                 + FIG19_PRIVATE_GAIN * (private @ units_private.T)[:, :, None])
        populations.append(drive + FIG19_NOISE * rng.standard_normal(drive.shape))
    return rng, populations


def _fig19_trace(populations, rng):
    """jrsa(metric='rsa') on each window, with the percentile band of its own permutation null."""
    starts = np.arange(0, FIG19_N_SAMPLES - FIG19_WINDOW + 1, FIG19_STEP)
    values, bands = [], []
    for start in starts:
        result = jnwb.jrsa(populations[0], populations[1], adim=-1, metric="rsa", null="iid",
                           window=(int(start), int(start) + FIG19_WINDOW),
                           permutations=FIG19_PERMUTATIONS, rng=rng, return_null=True)
        values.append(float(result.value))
        bands.append(np.percentile(result.null_distribution, FIG19_BAND_PCT))
    return starts, np.asarray(values), np.asarray(bands)


def fig19_rdms_and_jrsa():
    """Figure 19: RDMs of two synthetic populations that share a condition pattern, and a windowed jrsa trace against its null band."""
    fig = plt.figure(figsize=(style.WIDTH, 6.0), dpi=style.DPI)
    grid = fig.add_gridspec(2, 3, height_ratios=[1.0, 0.9], width_ratios=[1.0, 1.0, 0.05])
    ax_a, ax_b = fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1])
    cax = fig.add_subplot(grid[0, 2])
    ax_c = fig.add_subplot(grid[1, :])

    rng, populations = _fig19_populations()
    starts, values, bands = _fig19_trace(populations, rng)
    peak = int(np.argmax(values))
    start, stop = int(starts[peak]), int(starts[peak]) + FIG19_WINDOW
    windowed = [pop[:, :, start:stop].reshape(FIG19_N_COND, -1) for pop in populations]
    squares = [jnwb.rdm(x, metric="correlation", condensed=False) for x in windowed]
    vectors = [jnwb.rdm(x, metric="correlation", condensed=True) for x in windowed]
    rho, _ = jnwb.rdm_similarity(vectors[0], vectors[1], metric="spearman")
    # The trace's value at the peak window is the same comparison of the same two RDMs.
    assert np.isclose(rho, values[peak], rtol=1e-12, atol=0.0), (rho, values[peak])

    limit = max(float(square.max()) for square in squares)
    for ax, square, letter, name in zip((ax_a, ax_b), squares, ("A", "B"),
                                        ("Population 1", "Population 2")):
        image = ax.imshow(square, cmap="magma", vmin=0.0, vmax=limit, interpolation="nearest")
        ax.set_xlabel("Condition index")
        ax.set_ylabel("Condition index")
        ax.set_xticks(range(0, FIG19_N_COND, 2))
        ax.set_yticks(range(0, FIG19_N_COND, 2))
        style.panel_title(ax, letter, f"{name} RDM, samples {start}-{stop}\n(jnwb.rdm)")
    fig.colorbar(image, cax=cax).set_label("Correlation distance (dimensionless)")

    centers = starts + FIG19_WINDOW / 2
    width = FIG19_BAND_PCT[1] - FIG19_BAND_PCT[0]
    ax_c.fill_between(centers, bands[:, 0], bands[:, 1], color=style.NEUTRAL, alpha=0.35, lw=0,
                      label=f"{width:.0f}% null band, {FIG19_PERMUTATIONS} permutations")
    ax_c.axhline(0.0, color=style.NEUTRAL, ls=":", lw=style.LW_THIN)
    ax_c.plot(centers, values, color=style.SERIES[0], marker="o", lw=style.LW,
              label=f"jRSA value, peak rho = {style.num(values[peak], '.2f')}")
    ax_c.set_xlabel("Window center (sample index)")
    ax_c.set_ylabel("Spearman rho (dimensionless)")
    style.panel_title(ax_c, "C", "Windowed jRSA (metric 'rsa', null 'iid') against its null band\n(jnwb.jrsa)")
    ax_c.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)

    fig.tight_layout()
    _save(fig, "fig19_rdms_and_jrsa.png")
    plt.close(fig)


#: fig20's probe: channels, the planted bad channels, the samples of the continuous recording, the
#: width of its common-mode smoothing, and the independent noise each good channel adds to it.
FIG20_SEED = 20
FIG20_N_CH = 32
FIG20_BAD_CHANNELS = (4, 13, 22)
FIG20_N_SAMPLES = 6000
FIG20_SMOOTH = 20
FIG20_CH_NOISE = 0.6
FIG20_Z_THRESH = 5.0
#: The one labelled tick below the threshold on fig20's z axis, which is logarithmic there.
FIG20_Z_TICK = 100.0
#: fig20's trials: count, samples, the evoked deflection, the noise, and the transient artifact with
#: the trials that carry it on every channel (consensus) and on one channel (single).
FIG20_N_TRIALS = 40
FIG20_N_TIMES = 200
FIG20_EVOKED_AT = 100
FIG20_EVOKED_SD = 25.0
FIG20_NOISE = 0.5
FIG20_ARTIFACT_AT = 150
FIG20_ARTIFACT_SD = 6.0
FIG20_ARTIFACT_AMP = 12.0
FIG20_CONSENSUS_TRIALS = (7, 23)
FIG20_SINGLE_ARTIFACT = (15, 10)
FIG20_MIN_FRAC = 0.5


def _fig20_probe():
    """Continuous (channels, samples) data and (channels, trials, samples) trials. Good channels share a
    common mode; the planted bad channels carry independent noise only."""
    rng = np.random.default_rng(FIG20_SEED)
    common = np.convolve(rng.standard_normal(FIG20_N_SAMPLES), np.ones(FIG20_SMOOTH) / FIG20_SMOOTH,
                         mode="same")
    common = (common - common.mean()) / common.std()
    continuous = common[None, :] + FIG20_CH_NOISE * rng.standard_normal((FIG20_N_CH, FIG20_N_SAMPLES))
    bad = list(FIG20_BAD_CHANNELS)
    continuous[bad] = rng.standard_normal((len(bad), FIG20_N_SAMPLES))
    t = np.arange(FIG20_N_TIMES)
    evoked = np.exp(-0.5 * ((t - FIG20_EVOKED_AT) / FIG20_EVOKED_SD) ** 2)
    trials = evoked + FIG20_NOISE * rng.standard_normal((FIG20_N_CH, FIG20_N_TRIALS, FIG20_N_TIMES))
    transient = FIG20_ARTIFACT_AMP * np.exp(-0.5 * ((t - FIG20_ARTIFACT_AT) / FIG20_ARTIFACT_SD) ** 2)
    for trial in FIG20_CONSENSUS_TRIALS:
        trials[:, trial, :] += transient
    trial, channel = FIG20_SINGLE_ARTIFACT
    trials[channel, trial, :] += transient
    return continuous, trials


def fig20_bad_channels_and_trials():
    """Figure 20: Channel correlation and consensus bad trials of a synthetic probe with planted bad channels and artifacts."""
    fig = plt.figure(figsize=(style.WIDTH, 6.4), dpi=style.DPI)
    grid = fig.add_gridspec(2, 2)
    ax_a, ax_b = fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1])
    ax_c, ax_d = fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1])

    continuous, trials = _fig20_probe()
    corr = jnwb.channel_correlation_matrix(continuous)
    bad, summary, z = jnwb.bad_channels_from_correlation(corr, z_thresh=FIG20_Z_THRESH)
    flagged = np.flatnonzero(bad)
    assert flagged.tolist() == list(FIG20_BAD_CHANNELS), flagged.tolist()
    good = np.flatnonzero(~bad)
    per_channel = np.stack([jnwb.bad_trials_single_channel(trials[c])[0] for c in good])
    consensus, fraction = jnwb.consensus_bad_trials(per_channel, min_frac_channels=FIG20_MIN_FRAC)
    assert np.flatnonzero(consensus).tolist() == list(FIG20_CONSENSUS_TRIALS), np.flatnonzero(consensus).tolist()
    trial, channel = FIG20_SINGLE_ARTIFACT
    assert per_channel[good.tolist().index(channel), trial], "the single-channel artifact is not flagged"

    channels = np.arange(FIG20_N_CH)
    image = ax_a.imshow(corr, cmap="magma", vmin=float(corr.min()), vmax=float(corr.max()),
                        interpolation="nearest")
    for index in flagged:
        ax_a.axhline(index, color=style.SERIES[1], ls="--", lw=style.LW_THIN)
        ax_a.axvline(index, color=style.SERIES[1], ls="--", lw=style.LW_THIN)
    ax_a.set_xticks(channels[::8])
    ax_a.set_yticks(channels[::8])
    ax_a.set_xlabel("Channel index")
    ax_a.set_ylabel("Channel index")
    fig.colorbar(image, ax=ax_a).set_label("Pearson r (dimensionless)")
    ax_a.legend(handles=[Line2D([], [], color=style.SERIES[1], ls="--", lw=style.LW_THIN,
                                label=f"flagged channel, {len(flagged)} of {FIG20_N_CH}")],
                frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2))
    style.panel_title(ax_a, "A", "Channel correlation\n(jnwb.channel_correlation_matrix)")

    kept = ~bad
    ax_b.bar(channels[kept], z[kept], color=style.NEUTRAL, width=0.7)
    ax_b.bar(channels[bad], z[bad], color=style.SERIES[3], edgecolor=C_DARK, hatch="//", lw=style.EDGE,
             width=0.7)
    ax_b.axhline(-FIG20_Z_THRESH, color=C_DARK, ls="--", lw=style.LW_THIN)
    # Linear within the threshold and logarithmic beyond it: the bad channels' z sits near -280.
    ax_b.set_yscale("symlog", linthresh=FIG20_Z_THRESH)
    z_ticks = [-FIG20_Z_TICK, -FIG20_Z_THRESH, 0.0, FIG20_Z_THRESH]
    ax_b.set_yticks(z_ticks)
    # The symlog formatter labels decades only, so the threshold tick is labelled here.
    ax_b.set_yticklabels([style.num(tick, ".0f") for tick in z_ticks])
    ax_b.set_xticks(channels[::8])
    ax_b.set_xlabel("Channel index")
    ax_b.set_ylabel("Robust z (dimensionless)")
    ax_b.legend(handles=[
        Patch(facecolor=style.NEUTRAL, label="kept"),
        Patch(facecolor=style.SERIES[3], edgecolor=C_DARK, hatch="//",
              label=f"flagged, z below {style.num(-FIG20_Z_THRESH, '.1f')}"),
    ], frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    style.panel_title(ax_b, "B", "Each channel's median correlation\n(jnwb.bad_channels_from_correlation)")

    image_c = ax_c.imshow(per_channel.astype(float), cmap="cividis", vmin=0.0, vmax=1.0, aspect="auto",
                          interpolation="nearest")
    cbar = fig.colorbar(image_c, ax=ax_c)
    cbar.set_ticks([0.0, 1.0])
    cbar.set_ticklabels(["kept", "flagged"])
    ax_c.set_yticks(np.arange(0, len(good), 4))
    ax_c.set_yticklabels(good[::4])
    ax_c.set_xticks(np.arange(0, FIG20_N_TRIALS, 8))
    ax_c.set_xlabel("Trial index")
    ax_c.set_ylabel("Channel index (good channels)")
    style.panel_title(ax_c, "C", "Single-channel trial flags on good channels\n(jnwb.bad_trials_single_channel)")

    trial_index = np.arange(FIG20_N_TRIALS)
    ax_d.bar(trial_index[~consensus], fraction[~consensus], color=style.NEUTRAL, width=0.7)
    ax_d.bar(trial_index[consensus], fraction[consensus], color=style.SERIES[3], edgecolor=C_DARK,
             hatch="//", lw=style.EDGE, width=0.7)
    ax_d.axhline(FIG20_MIN_FRAC, color=C_DARK, ls="--", lw=style.LW_THIN)
    ax_d.set_ylim(0.0, 1.0)
    ax_d.set_xticks(np.arange(0, FIG20_N_TRIALS, 8))
    ax_d.set_xlabel("Trial index")
    ax_d.set_ylabel("Fraction of good channels flagged")
    ax_d.legend(handles=[
        Patch(facecolor=style.NEUTRAL, label="not consensus"),
        Patch(facecolor=style.SERIES[3], edgecolor=C_DARK, hatch="//",
              label=f"consensus bad, {len(FIG20_CONSENSUS_TRIALS)} trials, fraction at least "
                    f"{style.num(FIG20_MIN_FRAC, '.2f')}"),
    ], frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
    style.panel_title(ax_d, "D", "Consensus bad trials across good channels\n(jnwb.consensus_bad_trials)")

    fig.tight_layout()
    _save(fig, "fig20_bad_channels_and_trials.png")
    plt.close(fig)


#: fig21 reads the open-data tutorial's analysis: the script's `analyze()`, loaded by path because its
#: name starts with a digit. The figure and the page show one analysis, not two.
OPEN_DATA_SCRIPT = REPO_ROOT / "examples" / "tutorials" / "09_open_data.py"


def _open_data_run():
    """The tutorial's analysis, run through this module's `jnwb`, so the figure records the calls it makes."""
    spec = importlib.util.spec_from_file_location("_open_data_tutorial", OPEN_DATA_SCRIPT)
    tutorial = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = tutorial  # the script's dataclass looks its module up while it loads
    spec.loader.exec_module(tutorial)
    tutorial.jnwb = jnwb
    return tutorial, tutorial.analyze(tutorial.EXCERPT)


def fig21_open_data_psth_db():
    """Figure 21: Empirical. PSTH of good cortical units by layer and high-gamma power by depth, from the DANDI 000253 excerpt."""
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(style.WIDTH, 3.6), dpi=style.DPI)

    tutorial, res = _open_data_run()
    t_ms = res["psth"]["t_ms"]
    for color, (where, layer) in zip(style.SERIES, res["psth"]["layers"].items()):
        ax_a.plot(t_ms, layer["rate_hz"], color=color, lw=style.LW, label=f"{where} (n={layer['n_units']})")
        ax_a.annotate(where, (t_ms[-1], layer["rate_hz"][-1]), xytext=(4, 0), textcoords="offset points",
                      va="center", fontsize=style.SMALL, color=C_DARK)
    lo_ms, hi_ms = 1e3 * np.asarray(tutorial.POST_S)  # the grating on screen, as the tutorial names it
    ax_a.axvspan(lo_ms, hi_ms, color=C_HIGHLIGHT, alpha=0.4, zorder=0, lw=0)
    ax_a.set(xlabel="Time from grating onset (ms)", ylabel="Rate (Hz)")
    style.panel_title(ax_a, "A", "PSTH of good units by layer\n(jnwb.raster_psth)")
    ax_a.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)

    lf = res["lfp"]
    ax_b.plot(lf["db"], lf["depth_um"], color=style.SERIES[0], linestyle="none", marker="o", ms=5)
    for db, depth, where in zip(lf["db"], lf["depth_um"], lf["location"]):
        ax_b.annotate(where, (db, depth), xytext=(6, 0), textcoords="offset points", va="center",
                      fontsize=style.SMALL, color=C_DARK)
    ax_b.axvline(0.0, color=style.NEUTRAL, lw=style.LW_THIN)
    low, high = jnwb.CANONICAL_BANDS["high_gamma"]
    ax_b.set(xlabel=f"{low:.0f}–{high:.0f} Hz power, grating vs gray (dB)", ylabel="Contact position on probe (µm)")
    style.panel_title(ax_b, "B", "LFP band power by depth\n(jnwb.aggregate_to_db)")

    fig.tight_layout()
    _save(fig, "fig21_open_data_psth_db.png")
    plt.close(fig)


#: fig24 to fig26 draw the seeded inputs of tutorials 05 to 07, in the order each script draws them,
#: and call the same public functions. Each figure's numbers are printed from its own results.
FIG24_PERMUTATIONS = 100


def fig24_statistics_groups_cluster():
    """Figure 24: Synthetic. Two groups of trial rates with the bootstrap interval of their difference, and a cluster permutation test over time bins, from the statistics tutorial."""
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(style.WIDTH, 3.6), dpi=style.DPI)

    rng = np.random.default_rng(42)
    group_a = rng.normal(loc=12.0, scale=2.5, size=30)
    group_b = rng.normal(loc=15.0, scale=2.5, size=30)
    comp = StatisticalAnalysis.exploratory_compare(group_a, group_b)
    StatisticalAnalysis.bootstrap_ci(group_b, n_bootstrap=1000, rng=rng)
    jnwb.permute_labels(np.array(["condA"] * 30 + ["condB"] * 30), scheme="global", rng=rng)
    time_a = rng.normal(loc=0.0, size=(15, 50))
    time_b = rng.normal(loc=0.0, size=(15, 50))
    time_b[:, 20:30] += 1.5
    clust = jnwb.cluster_permutation_test(time_a, time_b, n_permutations=FIG24_PERMUTATIONS, rng=rng)
    assert clust["clusters"], "fig24 must hold the injected cluster"
    best = clust["clusters"][0]

    diff = float(np.mean(group_a) - np.mean(group_b))
    ci_lo, ci_hi = comp["mean_diff_ci"]["bootstrap_ci"]
    assert ci_lo <= diff <= ci_hi, "the library's interval must cover A minus B, its sign convention"
    for x, values, color in ((0, group_a, style.SERIES[0]), (1, group_b, style.SERIES[1])):
        ax_a.scatter(np.full(values.size, x), values, s=12, color=color, alpha=0.7, edgecolors="none")
        ax_a.hlines(values.mean(), x - 0.25, x + 0.25, color=color, lw=style.LW)
    ax_a.set_xticks([0, 1], ["Group A", "Group B"])
    ax_a.set_ylabel("Trial rate (Hz)")
    style.panel_title(ax_a, "A", "Trial rates by group, with the difference\nand its bootstrap interval")
    ax_a.legend(handles=[Patch(visible=False, label=f"Difference A − B = {style.num(diff, '.2f')} Hz; 95% "
                                                    f"bootstrap interval [{style.num(ci_lo, '.2f')}, "
                                                    f"{style.num(ci_hi, '.2f')}] Hz")],
                frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2))

    bins = np.arange(time_a.shape[1])
    ax_b.plot(bins, time_a.mean(axis=0), color=style.SERIES[0], lw=style.LW, label="Condition A mean")
    ax_b.plot(bins, time_b.mean(axis=0), color=style.SERIES[1], lw=style.LW, label="Condition B mean")
    low, high = ax_b.get_ylim()
    ax_b.fill_between(bins, low, high, where=np.asarray(best["mask"], dtype=bool), color=C_HIGHLIGHT,
                      alpha=0.4, lw=0, label=f"Cluster, p = {best['p_value']:.3f} "
                                             f"({FIG24_PERMUTATIONS} permutations)")
    ax_b.set_xlabel("Time bin (index)")
    ax_b.set_ylabel("Mean value (a.u.)")
    style.panel_title(ax_b, "B", "Cluster permutation test\n(jnwb.cluster_permutation_test)")
    ax_b.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)

    fig.tight_layout()
    _save(fig, "fig24_statistics_groups_cluster.png")
    plt.close(fig)


FIG25_FS = 1000.0
FIG25_N_CH = 16
FIG25_N_SAMPLES = 2000
FIG25_PITCH_UM = 100.0
FIG25_BLOCK = 8


def fig25_laminar_csd_flips():
    """Figure 25: Synthetic. The current source density, vFLIP band profiles, zFLIP adjacent-contact wPLI and xFLIP contact correlations of the laminar tutorial's signals."""
    fig = plt.figure(figsize=(style.WIDTH, 6.2), dpi=style.DPI)
    ax_a, ax_b = fig.add_subplot(2, 2, 1), fig.add_subplot(2, 2, 2)
    ax_c, ax_d = fig.add_subplot(2, 2, 3), fig.add_subplot(2, 2, 4)

    rng = np.random.default_rng(42)
    times = np.arange(FIG25_N_SAMPLES) / FIG25_FS
    lfp = np.zeros((FIG25_N_CH, FIG25_N_SAMPLES))
    for ch in range(FIG25_N_CH):
        signal = np.sin(2.0 * np.pi * 20.0 * times - ch * 0.15)
        lfp[ch] = signal + 0.2 * rng.normal(size=FIG25_N_SAMPLES)
    blocks = np.empty((2 * FIG25_BLOCK, FIG25_N_SAMPLES))
    for b in range(2):
        source = rng.normal(size=FIG25_N_SAMPLES)
        rows = slice(b * FIG25_BLOCK, (b + 1) * FIG25_BLOCK)
        blocks[rows] = 0.8 * source + 0.6 * rng.normal(size=(FIG25_BLOCK, FIG25_N_SAMPLES))

    # A: current source density over depth and time
    csd = jnwb.current_source_density_1d(lfp, pitch_um=FIG25_PITCH_UM, conductivity_s_per_m=0.3)
    csd = csd / float(np.abs(csd).max())  # normalized to its peak, so the colorbar needs no offset
    t_ms = times * 1e3
    limit = float(np.abs(csd).max())
    image = ax_a.imshow(csd, aspect="auto", cmap="RdBu_r", vmin=-limit, vmax=limit, interpolation="nearest",
                        extent=(t_ms[0], t_ms[-1], csd.shape[0] - 0.5, -0.5))
    fig.colorbar(image, ax=ax_a).set_label("Normalized CSD (a.u.)")
    ax_a.set_xlabel("Time (ms)")
    ax_a.set_ylabel("Depth site (index)")
    style.panel_title(ax_a, "A", "Current source density\n(jnwb.current_source_density_1d)")

    # B: the vFLIP band profiles and the crossover the estimator returns
    vflip = jnwb.vflip_from_lfp(lfp, FIG25_FS, min_support_score=0.0, orientation="auto")
    freqs, psd = jnwb.compute_psd(lfp, fs=FIG25_FS, axis=1)
    low, high = _band_profiles(psd, freqs, (CANONICAL_VFLIP_BANDS["low"], CANONICAL_VFLIP_BANDS["high"]))
    depth = np.arange(FIG25_N_CH)
    ax_b.plot(low, depth, color=style.SERIES[0], lw=style.LW, label="Low band")
    ax_b.plot(high, depth, color=style.SERIES[3], lw=style.LW, label="High band")
    if vflip.accepted:
        ax_b.axhline(vflip.crossover_contact, color=C_DARK, ls="--", lw=style.LW_THIN,
                     label=f"Crossover, contact {vflip.crossover_contact} (jnwb.vflip)")
    else:
        ax_b.plot([], [], " ", label=f"Not accepted: {vflip.rejection_reason} (jnwb.vflip)")
    ax_b.invert_yaxis()
    ax_b.set_xlabel("Normalized band power (dimensionless)")
    ax_b.set_ylabel("Contact index (dimensionless)")
    style.panel_title(ax_b, "B", "vFLIP band profiles and its verdict\n(jnwb.vflip)")
    ax_b.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)

    # C: zFLIP's wPLI between adjacent contacts, with the pairs whose delay is identifiable marked
    zflip = jnwb.zflip(lfp, FIG25_FS, orientation="superficial_to_deep", pitch_um=FIG25_PITCH_UM,
                       freq_range=(15.0, 25.0), n_surrogates=20, seed=42)
    pairs = np.arange(FIG25_N_CH - 1)
    identifiable = np.asarray(zflip.adjacent_identifiable, dtype=bool)
    ax_c.plot(pairs, zflip.adjacent_wpli, color=style.SERIES[0], lw=style.LW, label="Adjacent-contact wPLI")
    ax_c.scatter(pairs[identifiable], np.asarray(zflip.adjacent_wpli)[identifiable], color=style.SERIES[0],
                 s=24, zorder=3, label="Delay identifiable")
    ax_c.set_xlabel("Adjacent contact pair (index)")
    ax_c.set_ylabel("wPLI (dimensionless)")
    ax_c.set_ylim(0.0, 1.05)  # wPLI's full range: a near-constant profile must look flat
    style.panel_title(ax_c, "C", "Traveling wave between adjacent contacts\n(jnwb.zflip)")
    velocity = zflip.apparent_velocity_m_s
    velocity_text = "not identifiable" if velocity is None else f"{velocity:.2f} m/s"
    ax_c.legend(handles=[Patch(visible=False, label=f"Apparent velocity {velocity_text}, "
                                                    f"surrogate p = {zflip.p_value:.3f}")],
                frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2))

    # D: xFLIP's two blocks as the correlation between contacts, with the boundary it tests
    xflip = jnwb.xflip(blocks, n_blocks=2, min_block_size=3, n_surrogates=200, rng=0)
    assert xflip.accepted, xflip.rejection_reason
    corr = np.corrcoef(blocks)
    boundary = FIG25_BLOCK - 0.5
    image_d = ax_d.imshow(corr, cmap="magma", vmin=float(corr.min()), vmax=float(corr.max()),
                          interpolation="nearest")
    ax_d.axhline(boundary, color=style.SERIES[1], ls="--", lw=style.LW_THIN)
    ax_d.axvline(boundary, color=style.SERIES[1], ls="--", lw=style.LW_THIN)
    fig.colorbar(image_d, ax=ax_d).set_label("Pearson r (dimensionless)")
    ax_d.set_xlabel("Contact index (dimensionless)")
    ax_d.set_ylabel("Contact index (dimensionless)")
    style.panel_title(ax_d, "D", "Contact correlation\n(jnwb.xflip)")
    ax_d.legend(handles=[Patch(visible=False, label=f"Omnibus p = {xflip.p_values['omnibus']:.4f}")],
                frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.3))

    fig.tight_layout()
    _save(fig, "fig25_laminar_csd_flips.png")
    plt.close(fig)


def fig26_ensembles_rdm_decoding():
    """Figure 26: Synthetic. An RDM, the second-order similarity of two RDMs, and nested cross-validated decoding, from the ensembles tutorial's patterns."""
    fig, (ax_a, ax_b, ax_c) = plt.subplots(1, 3, figsize=(style.WIDTH, 3.6), dpi=style.DPI,
                                           gridspec_kw={"width_ratios": [0.95, 1.0, 1.5]})

    rng = np.random.default_rng(42)
    n_conditions, n_units = 6, 30
    patterns_v1 = rng.normal(loc=1.0, scale=0.5, size=(n_conditions, n_units))
    patterns_v2 = patterns_v1 + 0.3 * rng.normal(size=(n_conditions, n_units))
    time_series_1 = rng.normal(size=(n_conditions, n_units, 10))
    time_series_2 = time_series_1 + 0.2 * rng.normal(size=(n_conditions, n_units, 10))
    X = rng.normal(size=(40, n_units))
    X[:20, :5] += 0.8
    y = np.array([0] * 20 + [1] * 20)

    square = jnwb.rdm(patterns_v1, metric="correlation", condensed=False)
    vec1 = jnwb.rdm(patterns_v1, metric="correlation", condensed=True)
    vec2 = jnwb.rdm(patterns_v2, metric="correlation", condensed=True)
    rho, _ = jnwb.rdm_similarity(vec1, vec2, metric="spearman")
    cv = jnwb.nested_cv_linear_svm(X, y, n_splits=3)

    image = ax_a.imshow(square, cmap="magma", vmin=0.0, vmax=float(square.max()), interpolation="nearest")
    ax_a.set_xlabel("Condition index")
    ax_a.set_ylabel("Condition index")
    fig.colorbar(image, ax=ax_a, fraction=0.046).set_label("Distance (dimensionless)")
    style.panel_title(ax_a, "A", "RDM, pattern set 1\n(jnwb.rdm)")

    ax_b.scatter(vec1, vec2, color=style.SERIES[0], s=14, edgecolors="none")
    ax_b.set_xlabel("Pair distance, set 1 (dimensionless)")
    ax_b.set_ylabel("Pair distance, set 2 (dimensionless)")
    style.panel_title(ax_b, "B", "Second-order similarity\n(jnwb.rdm_similarity)")
    ax_b.legend(handles=[Patch(visible=False, label=f"Spearman rho = {rho:.2f}")],
                frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2))

    folds = np.asarray(cv["fold_accuracies"]) * 100
    ax_c.bar(range(1, folds.size + 1), folds, color=style.SERIES[0], width=0.5, edgecolor=C_DARK, lw=style.EDGE)
    ax_c.axhline(cv["accuracy"] * 100, color=style.SERIES[3], lw=style.LW,
                 label=f"Outer-CV mean ({cv['accuracy'] * 100:.1f}%)")
    ax_c.axhline(cv["majority_baseline_accuracy"] * 100, color=style.VARIABLE["baseline"], ls="--",
                 lw=style.LW_THIN, label=f"Majority baseline ({cv['majority_baseline_accuracy'] * 100:.1f}%)")
    ax_c.set_ylim(0, 135)
    ax_c.set_yticks(range(0, 101, 20))
    ax_c.set_xlabel("Outer CV fold")
    ax_c.set_ylabel("Decoding accuracy (%)")
    style.panel_title(ax_c, "C", "Outer-fold accuracy\n(jnwb.nested_cv_linear_svm)")
    ax_c.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)

    fig.tight_layout()
    _save(fig, "fig26_ensembles_rdm_decoding.png")
    plt.close(fig)


#: fig27's planted rate step: the seed, the trial count, the baseline and response rates in Hz,
#: the onset in ms, and the fit guards. The step is sustained to the window's end, so the trace
#: matches the plateau the onset model fits; the tolerance and R² floor sit far from the measured
#: error (3.1 ms) and R² (0.99).
FIG27_SEED = 11
FIG27_N_TRIALS = 80
FIG27_BASE_HZ = 6.0
FIG27_RESP_HZ = 60.0
FIG27_T0_MS = 80.0
FIG27_TOL_MS = 15.0
FIG27_MIN_R2 = 0.8


def fig27_spiking_psth_onset():
    """Figure 27: Synthetic. The raster and PSTH of Poisson spikes with a planted rate step, the
    causal smoothing and the exponential onset fit of the spiking tutorial, with the fit over the
    data."""
    fig, (ax_a, ax_b) = plt.subplots(2, 1, figsize=(style.WIDTH, 4.2), sharex=True, dpi=style.DPI,
                                     gridspec_kw={"height_ratios": [1.2, 1]})

    rng = np.random.default_rng(FIG27_SEED)
    onsets = np.arange(FIG27_N_TRIALS) * 1.5
    t0_s = FIG27_T0_MS / 1000.0
    relatives, trains = [], []
    for start in onsets:
        base = rng.uniform(-0.1, t0_s, rng.poisson(FIG27_BASE_HZ * (t0_s + 0.1)))
        resp = rng.uniform(t0_s, 0.4, rng.poisson(FIG27_RESP_HZ * (0.4 - t0_s)))
        rel = np.sort(np.concatenate([base, resp]))
        relatives.append(rel)
        trains.extend(rel + start)
    trains = np.asarray(trains)

    for idx, rel in enumerate(relatives):
        ax_a.vlines(rel * 1000, idx, idx + 0.8, color=C_DARK, lw=style.LW_THIN)
    ax_a.axvline(0, color=style.NEUTRAL, ls=":", lw=style.LW_THIN)
    ax_a.set_ylim(-0.5, FIG27_N_TRIALS + 0.5)
    ax_a.set_ylabel("Trial index")
    style.panel_title(ax_a, "A", f"Spike raster ({FIG27_N_TRIALS} trials)")

    # The PSTH, smoothing and fit are the calls the spiking tutorial draws with, on its window
    # and bin width.
    t_ms, rate_hz, sem_hz = jnwb.raster_psth(trains, onsets, win_ms=(-100.0, 400.0), bin_ms=10.0)
    smooth_hz = jnwb.causal_exp_smooth(rate_hz, bin_ms=10.0, tau_ms=25.0)
    fit = jnwb.fit_exponential_onset(t_ms, smooth_hz, t0_bounds_ms=(0.0, 200.0))
    assert abs(fit["t0"] - FIG27_T0_MS) <= FIG27_TOL_MS, "fig27 must recover the planted onset"
    assert fit["r2"] > FIG27_MIN_R2, "fig27 must hold a non-degenerate onset fit"
    pred = jnwb.onset_model(t_ms, fit["t0"], fit["tau"], fit["amplitude"], fit["baseline"])

    ax_b.plot(t_ms, rate_hz, color=style.VARIABLE["observed"], lw=style.LW, label="Mean rate")
    ax_b.fill_between(t_ms, rate_hz - sem_hz, rate_hz + sem_hz, color=style.VARIABLE["observed"],
                      alpha=0.35, lw=0, label="±1 SEM")
    ax_b.plot(t_ms, smooth_hz, color=style.VARIABLE["smoothed"], lw=style.LW,
              label="Causal smoothing (jnwb.causal_exp_smooth)")
    ax_b.plot(t_ms, pred, color=style.VARIABLE["fitted"], lw=style.LW_THICK,
              label=f"Onset fit: t0 = {style.num(fit['t0'], '.1f')} ms "
                    f"(R² = {style.num(fit['r2'], '.2f')})")
    ax_b.axvline(fit["t0"], color=style.VARIABLE["fitted"], ls=(0, (6, 3)), lw=style.LW_THIN)
    ax_b.axvline(FIG27_T0_MS, color=style.VARIABLE["truth"], ls=":", lw=style.LW,
                 label=f"Ground truth (t0 = {FIG27_T0_MS:.0f} ms)")
    ax_b.set_ylim(0, float(np.max(rate_hz + sem_hz)) * 1.3)
    ax_b.set_xlabel("Time relative to onset (ms)")
    ax_b.set_ylabel("Firing rate (Hz)")
    style.panel_title(ax_b, "B", "PSTH and onset fit (jnwb.raster_psth, jnwb.fit_exponential_onset)")
    ax_b.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=2)

    fig.tight_layout()
    _save(fig, "fig27_spiking_psth_onset.png")
    plt.close(fig)


#: fig28's planted coupling: the shared rhythm, its lag on channel 1 in samples at 1000 Hz, the
#: record length, and the band the coupling is read in with its off-band control. The lag is a
#: fraction of a cycle, so the coupling is non-zero-lag; the margins below sit far from the
#: measured band-power ratio (39.7) and wPLI values (0.75 coupled, 0.05 control).
FIG28_SEED = 23
FIG28_FS = 1000.0
FIG28_SECONDS = 30.0
FIG28_RHYTHM_HZ = 20.0
FIG28_LAG_SAMPLES = 8
FIG28_BAND_HZ = (15.0, 30.0)
FIG28_OFFBAND_HZ = (40.0, 55.0)
FIG28_MIN_POWER_RATIO = 5.0
FIG28_MIN_WPLI_GAP = 0.3


def fig28_lfp_spectral_wpli():
    """Figure 28: Synthetic. The Welch spectrum and the wPLI of two LFP channels sharing a rhythm
    with a fixed lag on one channel, against an independent-noise control."""
    fig, (ax_a, ax_b) = plt.subplots(2, 1, figsize=(style.WIDTH, 4.2), sharex=True, dpi=style.DPI,
                                     gridspec_kw={"height_ratios": [1, 1]})

    rng = np.random.default_rng(FIG28_SEED)
    t = np.arange(int(FIG28_SECONDS * FIG28_FS)) / FIG28_FS
    shared = 1.5 * np.sin(2.0 * np.pi * FIG28_RHYTHM_HZ * t)
    ch0 = shared + rng.standard_normal(len(t))
    ch1 = np.roll(shared, FIG28_LAG_SAMPLES) + rng.standard_normal(len(t))
    control = rng.standard_normal(len(t))

    # The spectrum and band powers are the calls the LFP tutorial draws with.
    freqs, psd = jnwb.compute_psd(ch0, fs=FIG28_FS)
    beta = jnwb.band_power(ch0, fs=FIG28_FS, freq_range=FIG28_BAND_HZ, normalize=False)
    off = jnwb.band_power(ch0, fs=FIG28_FS, freq_range=FIG28_OFFBAND_HZ, normalize=False)
    assert beta / off > FIG28_MIN_POWER_RATIO, "fig28 must hold band power above the noise"
    coupled = jnwb.wpli(ch0, ch1, fs=FIG28_FS, freq_range=FIG28_BAND_HZ)
    independent = jnwb.wpli(ch0, control, fs=FIG28_FS, freq_range=FIG28_BAND_HZ)
    assert independent["wpli"] < coupled["wpli"] < 1.0, "fig28 must order the wPLI below one"
    assert coupled["wpli"] - independent["wpli"] > FIG28_MIN_WPLI_GAP, \
        "fig28 must hold the coupling clear of the control"

    ax_a.plot(freqs, psd, color=style.NEUTRAL, lw=style.LW_THIN)
    ax_a.axvspan(FIG28_BAND_HZ[0], FIG28_BAND_HZ[1], color=C_HIGHLIGHT, alpha=0.4, lw=0)
    ax_a.set_xlim(0.0, 60.0)
    ax_a.set_ylabel("Power spectral density\n(a.u.²/Hz)")
    style.panel_title(ax_a, "A", "Welch spectrum (jnwb.compute_psd)")
    ax_a.legend(handles=[
        Line2D([], [], color=style.NEUTRAL, lw=style.LW_THIN, label="Welch PSD"),
        Patch(color=C_HIGHLIGHT, alpha=0.4,
              label=f"{FIG28_BAND_HZ[0]:.0f}−{FIG28_BAND_HZ[1]:.0f} Hz band"),
    ], frameon=False, loc="upper right")

    band = (coupled["freqs"] >= FIG28_BAND_HZ[0]) & (coupled["freqs"] <= FIG28_BAND_HZ[1])
    coupled_mean = float(np.mean(coupled["wpli_spectrum"][band]))
    control_mean = float(np.mean(independent["wpli_spectrum"][band]))
    ax_b.plot(coupled["freqs"], coupled["wpli_spectrum"], color=style.SERIES[0], lw=style.LW)
    ax_b.plot(independent["freqs"], independent["wpli_spectrum"], color=style.SERIES[1], lw=style.LW)
    ax_b.set_xlim(0.0, 60.0)
    ax_b.set_ylim(0.0, 1.05)  # wPLI's full range: the control must read as low against it
    ax_b.set_xlabel("Frequency (Hz)")
    ax_b.set_ylabel("wPLI (dimensionless)")
    style.panel_title(ax_b, "B", "wPLI against an independent-noise control (jnwb.wpli)")
    ax_b.legend(handles=[
        Line2D([], [], color=style.SERIES[0], lw=style.LW,
               label=f"Lagged shared rhythm, band mean {style.num(coupled_mean, '.2f')}"),
        Line2D([], [], color=style.SERIES[1], lw=style.LW,
               label=f"Independent-noise control, band mean {style.num(control_mean, '.2f')}"),
        Patch(visible=False, label=f"{coupled['n_segments']} Welch segments"),
    ], frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=1)

    fig.tight_layout()
    _save(fig, "fig28_lfp_spectral_wpli.png")
    plt.close(fig)


def _hz_range(band) -> str:
    """A frequency band as `lo−hi Hz`, with the true minus sign used as the range dash."""
    return f"{band[0]:g}−{band[1]:g} Hz"


#: fig29's probe: 24 contacts at 100 µm, the motif's crossover at contact 11.5 and its SNR, as in
#: the one-call example of the laminar page.
FIG29_FS = 1000.0
FIG29_N_CONTACTS = 24
FIG29_N_SAMPLES = 5000
FIG29_PITCH_UM = 100.0
FIG29_CROSSOVER = 11.5
FIG29_SNR = 20.0


def _inches_axes(fig, left, top, width, height):
    """An axes whose box starts `left` inches from the figure's left edge and `top` inches below
    its top edge, and is `width` by `height` inches."""
    w, h = fig.get_size_inches()
    return fig.add_axes([left / w, 1 - (top + height) / h, width / w, height / h])


#: fig29's layout, in inches. Panels A and C span the column from one left edge; panel B is a
#: square heatmap on that edge, its colorbar inside the column width. Each gap between panels is
#: the blank band between one panel's content and the next panel's title.
FIG29_LEFT_IN = 0.72
FIG29_RIGHT_IN = 4.08
FIG29_HEATMAP_IN = 2.5
FIG29_CBAR_GAP_IN = 0.14
FIG29_CBAR_W_IN = 0.14
FIG29_TOP_IN = 0.5
FIG29_A_H_IN = 2.6
FIG29_C_H_IN = 2.0
FIG29_A_BELOW_IN = 1.1  # measured ink: A's x label and its legend, below its axes
FIG29_BELOW_IN = 0.38  # measured ink: tick labels and x label, below B's and C's axes
FIG29_TITLE_IN = 0.37  # measured ink: a two-line panel title, above its axes
FIG29_GAP_IN = 0.3
FIG29_MARGIN_IN = 0.1  # blank space below C's x label, so the label stays on the canvas


def fig29_laminar_one_call():
    """Figure 29: Synthetic. The one-call example of the laminar page on its seeded motif probe:
    the vFLIP band profiles with the crossover and the layer labels, the xFLIP correlation of two
    contact blocks, and the zFLIP wPLI between adjacent contacts of a delayed wave."""
    a_top = FIG29_TOP_IN
    b_top = a_top + FIG29_A_H_IN + FIG29_A_BELOW_IN + FIG29_GAP_IN + FIG29_TITLE_IN
    c_top = b_top + FIG29_HEATMAP_IN + FIG29_BELOW_IN + FIG29_GAP_IN + FIG29_TITLE_IN
    height = c_top + FIG29_C_H_IN + FIG29_BELOW_IN + FIG29_MARGIN_IN
    fig = plt.figure(figsize=(style.NARROW_WIDTH, height), dpi=style.DPI)
    column = FIG29_RIGHT_IN - FIG29_LEFT_IN
    ax_a = _inches_axes(fig, FIG29_LEFT_IN, a_top, column, FIG29_A_H_IN)
    ax_b = _inches_axes(fig, FIG29_LEFT_IN, b_top, FIG29_HEATMAP_IN, FIG29_HEATMAP_IN)
    cax = _inches_axes(fig, FIG29_LEFT_IN + FIG29_HEATMAP_IN + FIG29_CBAR_GAP_IN, b_top,
                       FIG29_CBAR_W_IN, FIG29_HEATMAP_IN)
    ax_c = _inches_axes(fig, FIG29_LEFT_IN, c_top, column, FIG29_C_H_IN)

    rec = synth_laminar_motif(FIG29_N_CONTACTS, FIG29_N_SAMPLES, FIG29_FS, c_crossover=FIG29_CROSSOVER,
                              pitch_um=FIG29_PITCH_UM, snr=FIG29_SNR, rng=0)
    electrodes = pd.DataFrame({"x": 0.0, "y": 0.0, "z": FIG29_PITCH_UM * np.arange(FIG29_N_CONTACTS),
                               "channel_id": [f"ch{k}" for k in range(FIG29_N_CONTACTS)]})
    geom = jnwb.probe_geometry(electrodes, units="um")
    freqs, psd = jnwb.compute_psd(rec.lfp, FIG29_FS, axis=-1)
    fit = jnwb.vflip(psd, freqs, probe_geometry=geom, depth_axis="z", shallow_end="min")
    layers = jnwb.label_layers(fit, geom, depth_axis="z", shallow_end="min")
    assert fit.accepted and layers["ch0"] == "superficial" and layers["ch23"] == "deep", \
        "fig29 must place the crossover and both layers"

    # A: the two band profiles the estimator compares, by depth, with each contact's layer label
    depth_um = FIG29_PITCH_UM * np.arange(FIG29_N_CONTACTS)
    low, high = _band_profiles(psd, freqs, (CANONICAL_VFLIP_BANDS["low"], CANONICAL_VFLIP_BANDS["high"]))
    colour = {"superficial": style.SERIES[0], "input": style.SERIES[2], "deep": style.SERIES[3],
              "na": style.NEUTRAL}
    ax_a.plot(low, depth_um, color=style.SERIES[0], lw=style.LW, label=f"Low band {_hz_range(CANONICAL_VFLIP_BANDS['low'])}")
    ax_a.plot(high, depth_um, color=style.SERIES[3], lw=style.LW, label=f"High band {_hz_range(CANONICAL_VFLIP_BANDS['high'])}")
    for label in ("superficial", "input", "deep"):
        rows = [k for k in range(FIG29_N_CONTACTS) if layers[f"ch{k}"] == label]
        if rows:
            ax_a.axhspan(depth_um[rows].min() - 50.0, depth_um[rows].max() + 50.0, color=colour[label],
                         alpha=0.18, lw=0, label=label.capitalize())
    ax_a.axhline(FIG29_PITCH_UM * float(fit.crossover_contact), color=C_DARK, ls="--", lw=style.LW_THIN,
                 label=f"Crossover, contact {style.num(float(fit.crossover_contact), '.1f')}")
    ax_a.invert_yaxis()
    ax_a.set_xlabel("Normalized band power (dimensionless)")
    ax_a.set_ylabel("Depth from shallow end (µm)")
    style.panel_title(ax_a, "A", "vFLIP profiles and layers\n(jnwb.vflip, jnwb.label_layers)")
    ax_a.legend(frameon=False, fontsize=style.SMALL, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2,
                columnspacing=1.0, handlelength=1.5)

    # B: xFLIP's two contact blocks as the correlation between contacts, with the boundary it finds
    data, _, _ = synth_correlation_blocks((8, 16), n_samples=400, rng=0)
    blocks = jnwb.xflip(data, rng=0)
    assert blocks.accepted and blocks.boundaries == (8,), "fig29 must find the 8-contact boundary"
    image = ax_b.imshow(np.corrcoef(data), cmap="RdBu_r", vmin=-1.0, vmax=1.0, interpolation="nearest")
    edge = blocks.boundaries[0] - 0.5  # between the last contact of the first block and the next
    ax_b.axhline(edge, color=style.SERIES[1], ls="--", lw=style.LW_THIN)
    ax_b.axvline(edge, color=style.SERIES[1], ls="--", lw=style.LW_THIN)
    fig.colorbar(image, cax=cax).set_label("Pearson r (dimensionless)")
    ax_b.set_xlabel("Contact index (dimensionless)")
    ax_b.set_ylabel("Contact index (dimensionless)")
    style.panel_title(ax_b, "B", "Contact blocks\n(jnwb.xflip)")

    # C: zFLIP's wPLI between adjacent contacts of a wave that reaches each deeper contact 5 ms later
    noise = np.random.default_rng(0)
    spectrum = np.fft.rfft(noise.normal(size=4000))
    f = np.fft.rfftfreq(4000, 1 / FIG29_FS)
    wave = np.array([np.fft.irfft(spectrum * np.exp(-2j * np.pi * f * 0.005 * k), n=4000)
                     for k in range(6)]) + 0.1 * noise.normal(size=(6, 4000))
    delay = jnwb.zflip(wave, FIG29_FS, orientation="superficial_to_deep", pitch_um=FIG29_PITCH_UM, rng=0)
    assert delay.accepted and delay.directionality == "superficial_to_deep", "fig29 must find the delay"
    pairs = np.arange(wave.shape[0] - 1)
    identifiable = np.asarray(delay.adjacent_identifiable, dtype=bool)
    ax_c.plot(pairs, delay.adjacent_wpli, color=style.SERIES[0], lw=style.LW, label="Adjacent-contact wPLI")
    ax_c.scatter(pairs[identifiable], np.asarray(delay.adjacent_wpli)[identifiable], color=style.SERIES[0],
                 s=24, zorder=3, label="Delay identifiable")
    ax_c.set_xticks(pairs)  # one tick per adjacent pair: integer indices only
    ax_c.set_ylim(0.0, 1.05)  # wPLI's full range: a near-constant profile must look flat
    ax_c.set_xlabel("Adjacent contact pair (index)")
    ax_c.set_ylabel("wPLI (dimensionless)")
    style.panel_title(ax_c, "C", "Delay between contacts\n(jnwb.zflip)")
    velocity = delay.apparent_velocity_m_s
    velocity_text = "not identifiable" if velocity is None else f"{velocity:.2f} m/s"
    ax_c.legend(handles=[Patch(visible=False, label=f"Apparent velocity {velocity_text}")],
                frameon=False, loc="lower right", fontsize=style.SMALL)

    _save(fig, "fig29_laminar_one_call.png")
    plt.close(fig)


#: fig30's recording: five made-up units on an eight-contact probe at 30 kHz, sampled for ten
#: 60 s blocks. A unit built to drift stops firing after 240 s; a contaminated unit carries 0.3 Hz of
#: spikes from a second source on top of its own; a flat unit has a trough of 4 µV.
FIG30_SEED = 3
FIG30_FS = 30000.0
FIG30_N_CONTACTS = 8
FIG30_N_SAMPLES = 82
FIG30_TROUGH_SAMPLE = 30
FIG30_SECONDS = 600.0
FIG30_BLOCK_S = 60.0
FIG30_REFRACTORY_MS = 2.0
FIG30_CENSORED_MS = 0.25
#: (peak contact, trough in µV, rate in Hz, kind) for each unit.
FIG30_UNITS = (
    (2, -90.0, 8.0, "clean"),
    (5, -60.0, 3.0, "clean"),
    (6, -40.0, 12.0, "drifts"),
    (3, -75.0, 6.0, "contaminated"),
    (4, -4.0, 5.0, "flat"),
)


def _unit_waveform(peak: int, trough_uv: float) -> np.ndarray:
    """A mean waveform, contacts by samples, in µV: a trough on the peak contact that spreads
    down the probe over 1.5 contacts, with a small positive hump after it."""
    t_ms = (np.arange(FIG30_N_SAMPLES) - FIG30_TROUGH_SAMPLE) / FIG30_FS * 1e3
    shape = -np.exp(-0.5 * (t_ms / 0.25) ** 2) + 0.35 * np.exp(-0.5 * ((t_ms - 0.8) / 0.4) ** 2)
    spread = np.exp(-np.abs(np.arange(FIG30_N_CONTACTS) - peak) / 1.5)
    return np.outer(spread, -shape) * trough_uv


def _refractory_train(rng, rate_hz: float, span_s: float) -> np.ndarray:
    """A Poisson spike train with a dead time of FIG30_REFRACTORY_MS after each spike, so that the
    train holds no violation of its own refractory period."""
    candidates = np.sort(rng.uniform(0.0, span_s, rng.poisson(1.5 * rate_hz * span_s)))
    kept, last = [], -np.inf
    for t in candidates:
        if t - last >= FIG30_REFRACTORY_MS / 1e3:
            kept.append(t)
            last = t
    return np.asarray(kept)


def fig30_unit_quality_waveforms():
    """Figure 30: Synthetic. Five made-up units: their mean waveforms down an eight-contact probe
    (A), and the presence ratio against the refractory contamination of each unit's spike train (B),
    from the unit-quality measures of the unit-quality example."""
    rng = np.random.default_rng(FIG30_SEED)
    waves = [_unit_waveform(peak, trough) for peak, trough, _, _ in FIG30_UNITS]
    trains = []
    for _, _, rate, kind in FIG30_UNITS:
        span = 240.0 if kind == "drifts" else FIG30_SECONDS
        times = _refractory_train(rng, rate, span)
        if kind == "contaminated":
            other = np.sort(rng.uniform(0.0, span, rng.poisson(0.3 * span)))
            times = np.sort(np.concatenate([times, other]))
        trains.append(times)
    blocks = np.column_stack([np.arange(0.0, FIG30_SECONDS, FIG30_BLOCK_S),
                              np.arange(FIG30_BLOCK_S, FIG30_SECONDS + FIG30_BLOCK_S, FIG30_BLOCK_S)])

    features = [jnwb.waveform_features(w, FIG30_FS) for w in waves]
    presence = [jnwb.presence_ratio(t, blocks) for t in trains]
    contamination = [jnwb.refractory_contamination(t, duration_s=FIG30_SECONDS,
                                                   refractory_ms=FIG30_REFRACTORY_MS,
                                                   censored_ms=FIG30_CENSORED_MS)["contamination"]
                     for t in trains]
    assert [f["peak_channel"] for f in features] == [p for p, _, _, _ in FIG30_UNITS], \
        "fig30 must find each unit's peak contact"
    assert presence[0] == 1.0 and presence[2] < 1.0, "fig30 must hold the drifting unit below full presence"
    assert np.isfinite(contamination[3]) and contamination[3] > contamination[0], \
        "fig30 must hold the contaminated unit above the clean one"

    fig = plt.figure(figsize=(style.NARROW_WIDTH, 7.6), dpi=style.DPI)
    grid = fig.add_gridspec(3, 1, height_ratios=[1.7, 1, 1])
    ax_a = fig.add_subplot(grid[0])
    ax_b1, ax_b2 = fig.add_subplot(grid[1]), fig.add_subplot(grid[2])
    colours = [style.SERIES[0], style.SERIES[2], style.SERIES[1], style.SERIES[3], style.NEUTRAL]

    # A: each unit's waveform on its own 2.7 ms window, contacts stacked 100 µV apart, shallow at top
    t_ms = (np.arange(FIG30_N_SAMPLES) - FIG30_TROUGH_SAMPLE) / FIG30_FS * 1e3
    for u, wave in enumerate(waves):
        x0 = 2.9 * u
        for c in range(FIG30_N_CONTACTS):
            ax_a.plot(x0 + t_ms, -100.0 * c + wave[c], color=colours[u], lw=style.LW_THIN)
        peak = FIG30_UNITS[u][0]
        ax_a.plot(x0 + t_ms, -100.0 * peak + wave[peak], color=colours[u], lw=style.LW)
        ax_a.text(x0, 180.0, f"Unit {u}", ha="center", color=C_DARK, fontsize=style.SMALL)
    ax_a.set_yticks([-100.0 * c for c in range(FIG30_N_CONTACTS)])
    ax_a.set_yticklabels([str(c) for c in range(FIG30_N_CONTACTS)])
    ax_a.set_ylim(-750.0, 260.0)
    ax_a.set_xticks([])
    ax_a.set_ylabel("Contact (0 shallowest)")
    style.panel_title(ax_a, "A", "Mean waveforms down the probe, 100 µV per row\n"
                                 "(jnwb.waveform_features)")

    # B and C: the two spike-train measures, one point per unit
    units = np.arange(len(FIG30_UNITS))
    for ax, values in ((ax_b1, presence), (ax_b2, contamination)):
        for u in units:
            ax.scatter(u, values[u], s=36, color=colours[u], zorder=3)
        ax.set_xticks(units)
        ax.set_xlim(-0.6, len(FIG30_UNITS) - 0.4)
        ax.set_xlabel("Unit")
    ax_b1.set_ylim(0.0, 1.1)
    ax_b1.set_ylabel("Presence ratio (dimensionless)")
    ax_b2.set_ylim(0.0, max(contamination) * 1.3)
    ax_b2.set_ylabel("Contamination (dimensionless)")
    style.panel_title(ax_b1, "B", "Presence over 60 s blocks\n(jnwb.presence_ratio)")
    style.panel_title(ax_b2, "C", "Refractory contamination\n(jnwb.refractory_contamination)")

    fig.tight_layout()
    _save(fig, "fig30_unit_quality_waveforms.png")
    plt.close(fig)


#: The fixture's interval table that holds the photodiode changes, by the name it is written under.
FIG31_CHANGE_TABLE = "photodiode_1_detected_changes"


def fig31_table_alignment():
    """Figure 31: Synthetic. One unit of the synthetic NWB fixture aligned to its task table (A) and
    to its photodiode table (B). The unit fires 10 ms after each task onset, so only the task table
    shows a response, and the mean rate on the photodiode table is zero."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "synthetic_recording.nwb"
        write_synth_nwb(path, canonical_co_resident_options(seed=42))
        spikes = jnwb.unit_spike_times(path, unit_index=0)
        psths = []
        for table in (TASK_TABLE, FIG31_CHANGE_TABLE):
            onsets = jnwb.event_onsets(path, table=table, code_column=None)
            t_ms, rate, sem = jnwb.raster_psth(spikes, onsets, win_ms=(-100.0, 300.0), bin_ms=10.0)
            psths.append((table, onsets.size, t_ms, rate, sem))
    top = max(float(np.max(rate + sem)) for _, _, _, rate, sem in psths)
    assert psths[0][3].max() > 0.0, "fig31 must show a response on the task table"

    fig, (ax_a, ax_b) = plt.subplots(2, 1, figsize=(style.NARROW_WIDTH, 5.6), dpi=style.DPI, sharey=True)
    for ax, letter, (table, n_onsets, t_ms, rate, sem) in zip((ax_a, ax_b), "AB", psths):
        ax.fill_between(t_ms, rate - sem, rate + sem, color=style.VARIABLE["observed"], alpha=0.35, lw=0)
        ax.plot(t_ms, rate, color=style.VARIABLE["observed"], lw=style.LW,
                label=f"Mean rate {style.num(float(np.mean(rate)), '.2f')} Hz")
        ax.axvline(0.0, color=style.NEUTRAL, ls=":", lw=style.LW_THIN)
        ax.set_ylim(0.0, top * 1.3 if top > 0 else 1.0)
        ax.set_xlabel("Time from onset (ms)")
        ax.legend(frameon=False, loc="upper right")
        style.panel_title(ax, letter, f"Aligned to {table}\n({n_onsets} onsets)")
        ax.set_ylabel("Firing rate (Hz)")

    fig.tight_layout()
    _save(fig, "fig31_table_alignment.png")
    plt.close(fig)


def fig32_interval_tables():
    """Figure 32: Synthetic. Every interval table of the synthetic NWB fixture, as jnwb.inspect lists
    them, with the onsets of each table in seconds (A) and the spacing between them (B)."""
    fig, (ax_a, ax_b) = plt.subplots(2, 1, figsize=(style.NARROW_WIDTH, 5.6), dpi=style.DPI,
                                     gridspec_kw={"height_ratios": [1.5, 1]})
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "synthetic_recording.nwb"
        write_synth_nwb(path, canonical_co_resident_options(seed=42))
        names = [t["name"] for t in jnwb.inspect(path)["interval_tables"]]
        assert len(names) == 5, f"fig32 must list all five interval tables, found {names}"
        for row, name in enumerate(names):
            onsets = jnwb.event_onsets(path, table=name, code_column=None)
            spacing = np.diff(onsets)
            ax_a.scatter(onsets, np.full(onsets.size, row), s=16, color=style.SERIES[0], zorder=3)
            ax_b.scatter(spacing, np.full(spacing.size, row), s=16, color=style.SERIES[2], zorder=3)
    for ax in (ax_a, ax_b):
        ax.set_yticks(range(len(names)))
        ax.set_ylim(-0.6, len(names) - 0.4)
    ax_a.set_yticklabels(names)
    ax_b.set_yticklabels(names)
    ax_a.set_xlabel("Onset time in the session (s)")
    ax_b.set_xlabel("Spacing between onsets (s)")
    style.panel_title(ax_a, "A", "Interval tables\n(jnwb.inspect,\njnwb.event_onsets)")
    style.panel_title(ax_b, "B", "Onset spacing\n(jnwb.event_onsets)")

    fig.tight_layout()
    _save(fig, "fig32_interval_tables.png")
    plt.close(fig)


def fig33_addressing_contacts():
    """Figure 33: Synthetic. The ten contacts of the synthetic NWB fixture's probe, from
    jnwb.electrode_inventory, colored by their location label (A), and the onsets of the fixture's
    two condition codes in seconds (B)."""
    fig, (ax_a, ax_b) = plt.subplots(2, 1, figsize=(style.NARROW_WIDTH, 5.6), dpi=style.DPI,
                                     gridspec_kw={"height_ratios": [1, 1]})
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "synthetic_recording.nwb"
        write_synth_nwb(path, canonical_co_resident_options(seed=42))
        inventory = jnwb.electrode_inventory(path)
        layer = inventory["location"].str.split("/").str[-1]
        for name, colour in (("layer-0", style.SERIES[0]), ("layer-1", style.SERIES[2]),
                             ("layer-2", style.SERIES[3])):
            rows = inventory[layer == name]
            ax_a.scatter(rows["x"], rows["z"], s=30, color=colour, zorder=3, label=name)
        ax_a.set_xlabel("x (as stored)")
        ax_a.set_ylabel("z (as stored)")
        ax_a.legend(frameon=False, loc="upper left")
        for row, (code, colour) in enumerate(((CODE_LABEL_A, style.SERIES[0]),
                                              (CODE_LABEL_B, style.SERIES[1]))):
            onsets = jnwb.event_onsets(path, table=TASK_TABLE, codes=[code])
            ax_b.scatter(onsets, np.full(onsets.size, row), s=20, color=colour, zorder=3)
    ax_b.set_yticks([0, 1])
    ax_b.set_yticklabels([CODE_LABEL_A, CODE_LABEL_B])
    ax_b.set_ylim(-0.6, 1.6)
    ax_b.set_xlabel("Onset time in the session (s)")
    style.panel_title(ax_a, "A", "Contacts and their layers\n(jnwb.electrode_inventory)")
    style.panel_title(ax_b, "B", "Condition onsets in seconds\n(jnwb.event_onsets)")

    fig.tight_layout()
    _save(fig, "fig33_addressing_contacts.png")
    plt.close(fig)


#: fig34's synthetic session: 40 trials alternating two conditions 1.5 s apart, a 20 Hz rhythm at
#: amplitude 0.3 that rises to 1.0 for the 0.3 s after each condition A onset, and a unit that fires
#: 4 Hz with an extra 12 Hz in those same bursts after condition A onsets.
FIG34_SEED = 8
FIG34_FS = 1000.0
FIG34_RHYTHM_HZ = 20.0
FIG34_BURST_S = 0.3
FIG34_N_TRIALS = 40
FIG34_SPACING_S = 1.5


def fig34_end_to_end_synthetic():
    """Figure 34: Synthetic, not the tutorial's fixture. The PSTH of one unit by condition (A), and the
    beta power of condition A trials before and after onset (B), from the calls of the end-to-end
    pipeline on a planted beta increase."""
    rng = np.random.default_rng(FIG34_SEED)
    onsets = 2.0 + FIG34_SPACING_S * np.arange(FIG34_N_TRIALS)
    is_a = np.arange(FIG34_N_TRIALS) % 2 == 0
    onsets_a, onsets_b = onsets[is_a], onsets[~is_a]
    n = int(np.ceil((onsets[-1] + 1.0) * FIG34_FS))
    t = np.arange(n) / FIG34_FS
    amplitude = np.full(n, 0.3)
    for onset in onsets_a:
        amplitude[int(round(onset * FIG34_FS)):int(round((onset + FIG34_BURST_S) * FIG34_FS))] = 1.0
    lfp = amplitude * np.sin(2.0 * np.pi * FIG34_RHYTHM_HZ * t) + 0.5 * rng.standard_normal(n)
    background = rng.uniform(0.0, n / FIG34_FS, rng.poisson(4.0 * n / FIG34_FS))
    bursts = np.concatenate([rng.uniform(onset, onset + FIG34_BURST_S, rng.poisson(12.0 * FIG34_BURST_S))
                             for onset in onsets_a])
    spikes = np.sort(np.concatenate([background, bursts]))

    # A: the PSTH of each condition, with the calls the pipeline uses
    t_ms, rate_a, sem_a = jnwb.raster_psth(spikes, onsets_a, win_ms=(-100.0, 300.0), bin_ms=10.0)
    _, rate_b, sem_b = jnwb.raster_psth(spikes, onsets_b, win_ms=(-100.0, 300.0), bin_ms=10.0)

    # B: the beta power before and after each condition A onset, and its baseline-normalized response
    beta = jnwb.CANONICAL_BANDS["beta"]
    post_epochs, _ = jnwb.epoch_continuous(lfp, onsets_a, win_s=(0.0, FIG34_BURST_S), fs=FIG34_FS)
    base_epochs, _ = jnwb.epoch_continuous(lfp, onsets_a, win_s=(-0.2, -0.05), fs=FIG34_FS)
    post = np.array([jnwb.band_power(ep, fs=FIG34_FS, freq_range=beta, normalize=False) for ep in post_epochs])
    base = np.array([jnwb.band_power(ep, fs=FIG34_FS, freq_range=beta, normalize=False) for ep in base_epochs])
    db = float(jnwb.aggregate_to_db(post, base, how="mean_of_ratios", aggregate_over=0))
    assert db > 0.0, "fig34 must hold the planted beta increase above baseline"

    fig, (ax_a, ax_b) = plt.subplots(2, 1, figsize=(style.NARROW_WIDTH, 5.6), dpi=style.DPI,
                                     gridspec_kw={"height_ratios": [1.3, 1]})
    for rate, sem, colour, label in ((rate_a, sem_a, style.SERIES[0], "Condition A"),
                                     (rate_b, sem_b, style.SERIES[1], "Condition B")):
        ax_a.fill_between(t_ms, rate - sem, rate + sem, color=colour, alpha=0.3, lw=0)
        ax_a.plot(t_ms, rate, color=colour, lw=style.LW, label=label)
    ax_a.axvline(0.0, color=style.NEUTRAL, ls=":", lw=style.LW_THIN)
    ax_a.set_xlabel("Time from onset (ms)")
    ax_a.set_ylabel("Firing rate (Hz)")
    style.panel_title(ax_a, "A", "PSTH by condition\n(jnwb.raster_psth)")
    ax_a.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2)

    for i in range(post.size):
        ax_b.plot([0, 1], [base[i], post[i]], color=C_LIGHT_GRAY, lw=style.LW_THIN, zorder=1)
    ax_b.scatter(np.zeros(base.size), base, s=20, color=C_DARK, zorder=3)
    ax_b.scatter(np.ones(post.size), post, s=20, color=C_DARK, zorder=3)
    ax_b.set_xticks([0, 1])
    ax_b.set_xticklabels(["Baseline", "0 to 0.3 s"])
    ax_b.set_xlim(-0.3, 1.3)
    ax_b.set_ylim(0.0, float(max(base.max(), post.max())) * 1.15)
    ax_b.set_ylabel("Beta band power (a.u.)")
    style.panel_title(ax_b, "B", "Beta power, condition A\n(jnwb.band_power)")
    ax_b.plot([], [], " ", label=f"Response {style.num(db, '.1f')} dB (jnwb.aggregate_to_db)")
    ax_b.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2))

    fig.tight_layout()
    _save(fig, "fig34_end_to_end_synthetic.png")
    plt.close(fig)


#: fig35's recording: nine made-up units on three probes. The first probe's rows hold 4, 3 and 5
#: samples, the second probe's 2, 4 and 3, the third's 5, 2 and 4.
FIG35_ROW_SIZES = (4, 3, 5, 2, 4, 3, 5, 2, 4)
FIG35_PROBE_STARTS = (0, 3, 6)


def _defect_index(sizes, starts):
    """The index the defect writes: the first row of each probe after the first ends at the first
    element of the index plus its own length, and the rows after it carry on from there."""
    index = np.zeros(len(sizes), dtype=np.int64)
    for i, size in enumerate(sizes):
        if i == 0:
            index[i] = size
        elif i in starts[1:]:
            index[i] = index[0] + size
        else:
            index[i] = index[i - 1] + size
    return index


def _write_defect_units(path, sizes, defect):
    """Write a units table of synthetic spike trains, one row per unit, then overwrite its
    spike_times index with the defect's values. pynwb writes the correct running total first."""
    from datetime import datetime

    import h5py
    from dateutil.tz import tzlocal
    from pynwb import NWBFile, NWBHDF5IO

    nwb = NWBFile(session_description="synthetic offset-defect fixture", identifier="fig35",
                  session_start_time=datetime(2026, 1, 1, tzinfo=tzlocal()))
    rng = np.random.default_rng(0)
    for n in sizes:
        nwb.add_unit(spike_times=np.sort(rng.uniform(0.0, 10.0, int(n))))
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    with h5py.File(path, "r+") as f:
        index = f["units"]["spike_times_index"]
        index[...] = defect.astype(index.dtype)


def fig35_ragged_index_defect():
    """Figure 35: Synthetic. Nine made-up units on three probes, written to a file with the offset
    defect and checked by jnwb.check_ragged_indices: the index entries the defect leaves, against the
    corrected running total the check returns (A), and the span of flat data each row reads under each
    (B), with the correct span outlined."""
    sizes = np.asarray(FIG35_ROW_SIZES)
    defect = _defect_index(sizes, FIG35_PROBE_STARTS)
    assert np.any(np.diff(defect) < 0), "fig35 must show the decrease the defect causes"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "defect_recording.nwb"
        _write_defect_units(path, sizes, defect)
        report = jnwb.check_ragged_indices(path, probe_starts=list(FIG35_PROBE_STARTS))
    check = next(c for c in report.columns if c.column == "spike_times")
    assert check.offset_bug == "detected" and check.corrected_index is not None, \
        "fig35 must be detected as the offset defect"
    correct = np.asarray(check.corrected_index)
    assert np.array_equal(correct, np.cumsum(sizes)), "fig35 corrected index must be the running total"
    rows = np.arange(sizes.size)
    probe_of_row = np.searchsorted(FIG35_PROBE_STARTS, rows, side="right") - 1
    fig, (ax_a, ax_b) = plt.subplots(2, 1, figsize=(style.NARROW_WIDTH, 5.6), dpi=style.DPI,
                                     gridspec_kw={"height_ratios": [1, 1.2]})

    ax_a.plot(rows, correct, color=C_LIGHT_GRAY, lw=style.LW, marker="o", ms=4, label="Running total")
    ax_a.plot(rows, defect, color=style.SERIES[3], lw=style.LW_THIN, marker="o", ms=4, label="Defect")
    for start in FIG35_PROBE_STARTS[1:]:
        ax_a.axvline(start - 0.5, color=style.NEUTRAL, ls=":", lw=style.LW_THIN)
    ax_a.set_xlabel("Row (unit)")
    ax_a.set_ylabel("Index entry (exclusive end)")
    style.panel_title(ax_a, "A", "Index entries by row\n(correct and defective)")
    ax_a.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=2, fontsize=style.SMALL)

    read_start = np.concatenate(([0], defect[:-1]))
    read_end = np.maximum(defect, read_start)  # an end before its start reads nothing
    correct_start = np.concatenate(([0], correct[:-1]))
    for r in rows:
        ax_b.barh(r, correct[r] - correct_start[r], left=correct_start[r], height=0.7,
                  facecolor="none", edgecolor=C_LIGHT_GRAY, lw=style.LW_THIN, zorder=2)
        if read_end[r] > read_start[r]:
            ax_b.barh(r, read_end[r] - read_start[r], left=read_start[r], height=0.36,
                      color=style.SERIES[probe_of_row[r]], zorder=3)
        else:
            ax_b.plot(read_start[r], r, marker="x", color=style.SERIES[3], ms=6, mew=1.5, zorder=4)
    ax_b.invert_yaxis()
    ax_b.set_yticks(rows)
    ax_b.set_xlabel("Position in the flat data (element)")
    ax_b.set_ylabel("Row (unit)")
    style.panel_title(ax_b, "B", "Data each row reads\n(defective and correct spans)")
    ax_b.legend(handles=[
        Patch(facecolor="none", edgecolor=C_LIGHT_GRAY, label="Correct span"),
        Line2D([], [], color=style.SERIES[3], marker="x", ls="", label="Reads nothing"),
    ], frameon=False, loc="upper right", fontsize=style.SMALL)

    fig.tight_layout()
    _save(fig, "fig35_ragged_index_defect.png")
    plt.close(fig)


#: fig36's recording: twelve made-up units, six with a narrow trough and six with a broad one, each
#: trough a few samples from sample 30 at 30 kHz.
FIG36_SEED = 9
FIG36_FS = 30000.0
FIG36_N_SAMPLES = 82
FIG36_TROUGH_SAMPLE = 30
FIG36_JITTER = 4
FIG36_WIDTH_MS = (0.2, 0.45)


def fig36_wavemap_steps():
    """Figure 36: Synthetic. Twelve made-up mean waveforms in two trough widths, as recorded (A), and
    after the align and normalize steps of the WaveMAP page (B)."""
    rng = np.random.default_rng(FIG36_SEED)
    t_ms = (np.arange(FIG36_N_SAMPLES) - FIG36_TROUGH_SAMPLE) / FIG36_FS * 1e3
    raw = []
    for k in range(12):
        width = FIG36_WIDTH_MS[k // 6]
        shift = rng.integers(-FIG36_JITTER, FIG36_JITTER + 1) / FIG36_FS * 1e3
        amplitude = rng.uniform(60.0, 120.0)
        shape = (-np.exp(-0.5 * ((t_ms - shift) / width) ** 2)
                 + 0.35 * np.exp(-0.5 * ((t_ms - shift - 0.8) / 0.4) ** 2))
        raw.append(amplitude * shape)
    raw = np.asarray(raw)
    aligned, valid = jnwb.align_waveforms(raw, fs=FIG36_FS)
    assert valid.all(), "fig36 must align every unit"
    normalized = jnwb.normalize_waveforms(aligned)
    assert np.allclose(np.abs(normalized).max(axis=1), 1.0), "fig36 rows must reach unit amplitude"
    t_aligned = (np.arange(aligned.shape[1]) - int(np.argmin(aligned[0]))) / FIG36_FS * 1e3

    fig, (ax_a, ax_b) = plt.subplots(2, 1, figsize=(style.NARROW_WIDTH, 5.6), dpi=style.DPI)
    for k in range(12):
        colour = style.SERIES[0] if k < 6 else style.SERIES[1]
        ax_a.plot(t_ms, raw[k], color=colour, lw=style.LW_THIN, alpha=0.85)
        ax_b.plot(t_aligned, normalized[k], color=colour, lw=style.LW_THIN, alpha=0.85)
    for lo, hi, colour in ((0, 6, style.SERIES[0]), (6, 12, style.SERIES[1])):
        ax_b.plot(t_aligned, normalized[lo:hi].mean(axis=0), color=colour, lw=style.LW_THICK)
    ax_a.set_xlabel("Time from nominal trough (ms)")
    ax_a.set_ylabel("Voltage (µV)")
    style.panel_title(ax_a, "A", "Mean waveforms, as recorded\n(synthetic units)")
    ax_a.legend(handles=[
        Line2D([], [], color=style.SERIES[0], lw=style.LW_THIN, label="Narrow trough"),
        Line2D([], [], color=style.SERIES[1], lw=style.LW_THIN, label="Broad trough"),
    ], frameon=False, loc="lower right")
    ax_b.axvline(0, color=style.NEUTRAL, ls=":", lw=style.LW_THIN)
    ax_b.set_xlabel("Time from trough (ms)")
    ax_b.set_ylabel("Normalized amplitude (dimensionless)")
    style.panel_title(ax_b, "B", "Aligned, then normalized\n(jnwb.normalize_waveforms)")

    fig.tight_layout()
    _save(fig, "fig36_wavemap_steps.png")
    plt.close(fig)


#: fig37's fixture: one written copy recast from float64 to float32 on a single dataset.
FIG37_CAST_PATH = "acquisition/raw/data"


def _write_verify_nwb(path):
    """A minimal writable NWB file for the verify figure: one series and one unit."""
    from datetime import datetime, timezone

    from pynwb import NWBFile, NWBHDF5IO
    from pynwb.ecephys import ElectricalSeries

    nwb = NWBFile(session_description="synthetic verify fixture", identifier="fig37",
                  session_start_time=datetime(2026, 1, 1, tzinfo=timezone.utc))
    dev = nwb.create_device(name="probe_dev", description="d", manufacturer="m")
    grp = nwb.create_electrode_group(name="probeA", description="g", location="V1",
                                     device=dev)
    for i in range(4):
        nwb.add_electrode(x=0.0, y=float(i), z=0.0, imp=1.0, location="V1",
                          filtering="none", group=grp, group_name="probeA")
    region = nwb.create_electrode_table_region(region=[0, 1, 2, 3], description="all")
    nwb.add_acquisition(ElectricalSeries(
        name="raw", data=np.arange(80, dtype="f8").reshape(20, 4),
        electrodes=region, rate=1000.0, conversion=1.0, starting_time=0.0))
    nwb.add_unit(spike_times=np.array([0.1, 0.4, 0.9]))
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)


def fig37_verify_written_nwb():
    """Figure 37: Synthetic. A written copy re-read by jnwb.verify_nwb: the four standalone
    checks on the copy (A), and the comparison of the recast copy against its source, the
    byte-identical datasets beside the one declared cast (B)."""
    import h5py

    from jnwb.nwb_write import AppliedOperation, MutationReport
    from jnwb.ontology import Lineage, Provenance

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "src.nwb"
        dst = Path(tmp) / "dst.nwb"
        _write_verify_nwb(src)
        shutil.copy(src, dst)
        standalone = jnwb.verify_nwb(dst)
        with h5py.File(dst, "r+") as handle:
            data = handle[FIG37_CAST_PATH]
            attrs = {k: data.attrs[k] for k in data.attrs}
            values = data[:].astype("f4")
            del handle[FIG37_CAST_PATH]
            recast = handle.create_dataset(FIG37_CAST_PATH, data=values)
            for k, v in attrs.items():
                recast.attrs[k] = v
        report = MutationReport(
            category="copy or transform", src=str(src), dst=str(dst),
            src_sha256=None, dst_sha256=None,
            applied=(AppliedOperation(name="cast", changed=(FIG37_CAST_PATH,)),),
            checks=(), issues=(), waived=(),
            provenance=Provenance(software_version=jnwb.__version__, backend="numpy"),
            lineage=Lineage(source_type="NWBFile", source_id="hand-built",
                            operation="copy or transform"),
            ok=True)
        against = jnwb.verify_nwb(dst, against=src, report=report)
    assert [c.name for c in standalone.checks] == [
        "pynwb read", "pynwb schema validation",
        "soft and external links resolve", "object references resolve"], \
        "fig37 plots the four standalone checks"
    assert standalone.ok and all(c.ok for c in standalone.checks), \
        "fig37 needs a copy that passes on its own"
    assert against.ok, "fig37 needs a recast the declared cast explains"
    cast = [c for c in against.checks if "cast of the source" in c.name]
    identical = [c for c in against.checks
                 if "matches the source as declared" in c.name and c.ok]
    assert len(cast) == 1 and identical, \
        "fig37 needs one declared cast beside byte-identical datasets"
    passed = [int(c.ok) for c in standalone.checks]
    counts = [len(identical), len(cast)]

    fig, (ax_a, ax_b) = plt.subplots(2, 1, figsize=(style.NARROW_WIDTH, 5.6), dpi=style.DPI)
    ax_a.bar(np.arange(len(passed)), passed,
             color=[style.SERIES[0] if p else style.SERIES[3] for p in passed], zorder=3)
    ax_a.set_xticks(np.arange(len(passed)), ["Read", "Schema", "Links", "References"])
    ax_a.set_ylim(0, 1.2)
    ax_a.set_xlabel("Check (standalone run)")
    ax_a.set_ylabel("Result (pass = 1)")
    style.panel_title(ax_a, "A", "Standalone checks\n(jnwb.verify_nwb)")
    ax_a.legend(handles=[
        Patch(facecolor=style.SERIES[0], label="Pass"),
        Patch(facecolor=style.SERIES[3], label="Fail"),
    ], frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=2,
        fontsize=style.SMALL)

    ax_b.bar(["Identical", "Cast"], counts,
             color=[style.SERIES[0], style.SERIES[1]], zorder=3)
    ax_b.set_xlabel("Comparison outcome")
    ax_b.set_ylabel("Datasets (count)")
    style.panel_title(ax_b, "B", "Against the source\n(jnwb.verify_nwb)")

    fig.tight_layout()
    _save(fig, "fig37_verify_written_nwb.png")
    plt.close(fig)


#: The plotting page's sorted-heatmap example, reproduced exactly: seeded normal draws, 40 units by
#: 70 time bins, sorted by the bin of each unit's peak.
VIS_BASENAME = "sorted_heatmap"


def write_vis_example(out_dir: Path) -> Path:
    """Export the plotting page's sorted-heatmap example with jnwb.vis, sealed with its argument
    sidecar, and copy its PNG to `out_dir`. Synthetic: seeded normal draws, not recorded data. The
    PNG is a Plotly export, so it is kept out of FIGURE_DIR, whose PNGs are all Matplotlib's."""
    from jnwb import vis

    rng = np.random.default_rng(0)
    time_ms = np.arange(-200.0, 500.0, 10.0)
    rates = rng.normal(size=(40, time_ms.size))
    order = np.argsort(np.argmax(rates[:, time_ms >= 0], axis=1))
    canvas = vis.PlotlyPublicationCanvas(layout="1col", height_mm=70.0, rows=1, cols=1, tags=[["A"]])
    vis.plot_sorted_heatmap(canvas, 0, 0, rates, time_ms, sort_idx=order,
                            title="Synthetic units sorted by peak time", colorbar_title="Rate",
                            value_unit="z")
    argument = vis.EpistemicArgumentObject(
        QUESTION="Does the heatmap render units sorted by peak time?",
        DATA="Synthetic normal draws, 40 units x 70 bins, seed 0",
        ESTIMAND="None: a rendering example",
        INFERENCE_UNIT="None",
        RESULT="A sorted heatmap",
        LICENSED_CLAIM="The canvas renders a supplied matrix",
        BARRED_CLAIM="Any claim about neural data",
        SOURCE_ARTIFACTS=["generated in this script, seed 0"],
    )
    with tempfile.TemporaryDirectory() as tmp:
        paths = canvas.save_and_seal(tmp, VIS_BASENAME, argument)
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / f"{VIS_BASENAME}.png"
        shutil.copyfile(paths["png"], target)
    return target


#: Every committed figure and the function that writes it. A PNG in FIGURE_DIR that is not a
#: key here has no generator, and the maintenance test fails on it.
FIGURES = {
    "fig01_addressing_laminar.png": fig01_addressing,
    "fig02_raster_psth.png": fig02_spikes_psth,
    "fig03_onset_fitting.png": fig03_onset,
    "fig04_psd_spectral_tilt.png": fig04_spectral_tilt,
    "fig05_complex_tfr_coi.png": fig05_complex_tfr,
    "fig06_aggregate_to_db.png": fig06_aggregate_db,
    "fig07_population_decoding.png": fig07_decoding,
    "fig08_permutation_null.png": fig08_permutation,
    "fig09_directed_connectivity.png": fig09_directed_connectivity,
    "fig10_artifact_repair.png": fig10_artifact_repair,
    "fig11_spectra_canonical_bands.png": fig11_spectra_bands,
    "fig12_coherence_zero_lag.png": fig12_coherence_zero_lag,
    "fig13_vflip_band_profiles.png": fig13_vflip_band_profiles,
    "fig14_causal_vs_gaussian_step.png": fig14_causal_vs_gaussian_step,
    "fig15_spike_phase_locking.png": fig15_spike_phase_locking,
    "fig16_cluster_permutation.png": fig16_cluster_permutation,
    "fig17_spectral_granger.png": fig17_spectral_granger,
    "fig18_psi_narrowband_trap.png": fig18_psi_narrowband_trap,
    "fig19_rdms_and_jrsa.png": fig19_rdms_and_jrsa,
    "fig20_bad_channels_and_trials.png": fig20_bad_channels_and_trials,
    "fig21_open_data_psth_db.png": fig21_open_data_psth_db,
    "fig24_statistics_groups_cluster.png": fig24_statistics_groups_cluster,
    "fig25_laminar_csd_flips.png": fig25_laminar_csd_flips,
    "fig26_ensembles_rdm_decoding.png": fig26_ensembles_rdm_decoding,
    "fig27_spiking_psth_onset.png": fig27_spiking_psth_onset,
    "fig28_lfp_spectral_wpli.png": fig28_lfp_spectral_wpli,
    "fig29_laminar_one_call.png": fig29_laminar_one_call,
    "fig30_unit_quality_waveforms.png": fig30_unit_quality_waveforms,
    "fig31_table_alignment.png": fig31_table_alignment,
    "fig32_interval_tables.png": fig32_interval_tables,
    "fig33_addressing_contacts.png": fig33_addressing_contacts,
    "fig34_end_to_end_synthetic.png": fig34_end_to_end_synthetic,
    "fig35_ragged_index_defect.png": fig35_ragged_index_defect,
    "fig36_wavemap_steps.png": fig36_wavemap_steps,
    "fig37_verify_written_nwb.png": fig37_verify_written_nwb,
}


def main(argv=None):
    global OUT_DIR
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=FIGURE_DIR)
    parser.add_argument("--only", nargs="+", choices=sorted(FIGURES), default=sorted(FIGURES))
    parser.add_argument("--vis", action="store_true",
                        help="write the plotting page's sealed jnwb.vis example, and no figure")
    args = parser.parse_args(argv)
    try:
        style.check_font()
    except style.FontMissing as exc:
        print(f"generate_figures: {exc}", file=sys.stderr)
        raise SystemExit(FONT_MISSING_EXIT)
    if args.vis:
        print(f"  [OK] {write_vis_example(args.out_dir.parent / 'vis')}")
        return
    OUT_DIR = args.out_dir
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        apply_theme(theme)
        for name in args.only:
            FIGURES[name]()
            plt.close("all")
            print(f"  [OK] {name.replace('.png', SUFFIX)}")
    print(f"{len(args.only)} figure(s) in {len(THEMES)} themes written to {OUT_DIR}")


if __name__ == "__main__":
    main()
