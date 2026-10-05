"""Generate 10 canonical figures for jnwb documentation.

Each figure draws results of public jnwb calls on synthetic test signals with known ground
truth, producing reproducible figures for docs/assets/figures/. The palette, fonts, size tiers,
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
import sys
from pathlib import Path

# The repository root, for jnwb, and this folder, for the style module. Guarded: the suite
# executes this module in-process, and an unconditional prepend there puts the checkout ahead
# of an installed jnwb.
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
for _path in (REPO_ROOT, HERE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import figure_style as style
import jnwb

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
}


def main(argv=None):
    global OUT_DIR
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=FIGURE_DIR)
    parser.add_argument("--only", nargs="+", choices=sorted(FIGURES), default=sorted(FIGURES))
    args = parser.parse_args(argv)
    try:
        style.check_font()
    except style.FontMissing as exc:
        print(f"generate_figures: {exc}", file=sys.stderr)
        raise SystemExit(FONT_MISSING_EXIT)
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
