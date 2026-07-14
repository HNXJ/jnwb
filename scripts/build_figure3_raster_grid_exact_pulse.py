"""
scripts/build_figure3_raster_grid_exact_pulse.py

Generates a version of the Figure 3 Raster Grid using exact-pulse matched units:
- S+ Unit: 161 (unit_id column 5 in MT, ~11.7 Hz overall rate, r_S+ = 0.93)
- S- Unit: 352 (unit_id column 183 in V2, ~11.1 Hz overall rate, r_S- = 0.93)
- O+ Unit: 51 (unit_id column 52 in FEF, ~13.6 Hz overall rate, r_O+ = 0.58)

For each subplot, it displays:
1. The 40-trial raster plot (aligned to the full sequence epoch timing).
2. A separate 1D PSTH trace plot directly underneath showing the Average Firing Rate (AFR)
   smoothed with a causal exponential window (tau = 30ms).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.ticker import MaxNLocator, FuncFormatter
import matplotlib
import matplotlib.gridspec as gridspec

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import jnwb as oa
from jnwb.sequence_layout import EPOCH_ONSETS_MS

NWB_PATH = "D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb"
SESSION_PREFIX = "sub-C31o_ses-230823"
CONDITIONS = ["RRRR", "RXRR", "RRXR", "RRRX"]
WINDOW_MS = (-500.0, 4124.0)
N_TRIALS_SHOWN = 40
MIN_TRIALS = 40

EPOCH_LABELS = list(EPOCH_ONSETS_MS.keys()) + ["end"]
EPOCH_TIMES_MS = list(EPOCH_ONSETS_MS.values()) + [WINDOW_MS[1]]

CLASS_COLORS = {"S+": "#1D9E75", "S-": "#993C1D", "O+": "#185FA5"}
EPOCH_SHADE_COLORS = {"p1": "#fcee21", "p2": "#93278f", "p3": "#019147", "p4": "#000bd4"}
EPOCH_SHADE_ALPHA = 0.18

OUT_DIR = REPO_ROOT / "outputs/publication_figures/figure2_raster_4x3"


def causal_exponential_smoothing(spike_times_rel: list[float], n_trials: int, window_ms: tuple[float, float], tau_ms: float = 30.0, bin_ms: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Computes causally smoothed Average Firing Rate (AFR) in Hz."""
    t_start, t_stop = window_ms
    bins = np.arange(t_start, t_stop + bin_ms, bin_ms)
    counts, edges = np.histogram(spike_times_rel, bins=bins)
    bin_centers = (edges[:-1] + edges[1:]) / 2

    # Firing rate per trial per bin (Hz)
    raw_rate = counts / (n_trials * (bin_ms / 1000.0))

    # Causal exponential filter: h(t) = exp(-t/tau) for t >= 0
    t_filter = np.arange(0, 5 * tau_ms, bin_ms)
    h = np.exp(-t_filter / tau_ms)
    h /= h.sum()  # normalize to integrate to 1

    padded_rate = np.concatenate([np.zeros(len(h) - 1), raw_rate])
    smoothed = np.convolve(padded_rate, h, mode="valid")

    return bin_centers, smoothed


def plot_raster_subplot(ax_raster, ax_psth, spike_times: np.ndarray, onsets: np.ndarray, color: str, condition: str):
    # Shade stimulus epochs
    for label, t_start in EPOCH_ONSETS_MS.items():
        if label in EPOCH_SHADE_COLORS:
            idx = EPOCH_LABELS.index(label)
            t_stop = EPOCH_TIMES_MS[idx + 1]
            ax_raster.axvspan(t_start, t_stop, color=EPOCH_SHADE_COLORS[label], alpha=EPOCH_SHADE_ALPHA, zorder=0, linewidth=0)
            ax_psth.axvspan(t_start, t_stop, color=EPOCH_SHADE_COLORS[label], alpha=EPOCH_SHADE_ALPHA, zorder=0, linewidth=0)

    # Plot spikes
    win_s = (WINDOW_MS[0] / 1000.0, WINDOW_MS[1] / 1000.0)
    all_spike_times_rel = []
    trial_idx = 0
    for onset in onsets[:N_TRIALS_SHOWN]:
        lo, hi = onset + win_s[0], onset + win_s[1]
        mask = (spike_times >= lo) & (spike_times < hi)
        rel_ms = (spike_times[mask] - onset) * 1000.0
        all_spike_times_rel.extend(rel_ms)
        ax_raster.vlines(rel_ms, trial_idx + 0.05, trial_idx + 0.95, color="black", linewidth=0.6, zorder=2)
        trial_idx += 1

    # Causal Exponential PSTH Underneath
    if len(onsets) > 0 and len(all_spike_times_rel) > 0:
        bin_centers, afr = causal_exponential_smoothing(all_spike_times_rel, len(onsets[:N_TRIALS_SHOWN]), WINDOW_MS, tau_ms=30.0)
        ax_psth.plot(bin_centers, afr, color=color, linewidth=1.2, zorder=3)
        ax_psth.fill_between(bin_centers, 0, afr, color=color, alpha=0.15, zorder=2)

    # Styling raster
    ax_raster.set_xlim(WINDOW_MS[0], WINDOW_MS[1])
    ax_raster.set_ylim(0, N_TRIALS_SHOWN)
    ax_raster.invert_yaxis()
    ax_raster.xaxis.set_tick_params(labelbottom=False)
    ax_raster.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=4))
    ax_raster.grid(True, which="both", axis="x", linestyle=":", linewidth=0.5, alpha=0.5)

    # Styling PSTH
    ax_psth.set_xlim(WINDOW_MS[0], WINDOW_MS[1])
    ax_psth.set_ylim(0, 45)
    ax_psth.yaxis.set_major_locator(MaxNLocator(nbins=3))
    ax_psth.grid(True, which="both", axis="x", linestyle=":", linewidth=0.5, alpha=0.5)

    # Mark epoch borders
    for t_ms in EPOCH_TIMES_MS:
        ax_raster.axvline(t_ms, color="gray", linestyle=":", linewidth=0.5, alpha=0.6, zorder=1)
        ax_psth.axvline(t_ms, color="gray", linestyle=":", linewidth=0.5, alpha=0.6, zorder=1)

    # Mark omitted slot
    omit_slots = {"RXRR": "p2", "RRXR": "p3", "RRRX": "p4"}
    if condition in omit_slots:
        omit_label = omit_slots[condition]
        idx = EPOCH_LABELS.index(omit_label)
        t_start = EPOCH_TIMES_MS[idx]
        t_stop = EPOCH_TIMES_MS[idx + 1]
        t_mid = (t_start + t_stop) / 2
        ax_raster.axvline(t_mid, color="red", linestyle="--", linewidth=0.8, alpha=0.7, zorder=2)
        ax_psth.axvline(t_mid, color="red", linestyle="--", linewidth=0.8, alpha=0.7, zorder=2)
        ax_raster.text(t_mid, N_TRIALS_SHOWN * 0.05, "Omit", color="red", fontsize=6, ha="center", va="top", zorder=3)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sess = oa.read(NWB_PATH)

    # Firing rate matched S+, S-, O+ units (best matches to exact pulse patterns)
    units = {"S+": 161, "S-": 352, "O+": 51}

    onsets_by_cond = {}
    for cond in CONDITIONS:
        epochs = sess.get_epochs(phase=2, condition=cond, correct_only=True)
        onsets_by_cond[cond] = epochs["start_time"].values

    # Setup 4 rows (conditions) x 3 columns (units) grid
    fig = plt.figure(figsize=(14, 16))
    outer_gs = gridspec.GridSpec(4, 3, figure=fig, hspace=0.35, wspace=0.25)

    panel_letters = "ABCDEFGHIJKL"
    panel_i = 0

    for row_i, cond in enumerate(CONDITIONS):
        for col_i, cls in enumerate(["S+", "S-", "O+"]):
            inner_gs = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=outer_gs[row_i, col_i], height_ratios=[3, 1], hspace=0.08)
            ax_raster = fig.add_subplot(inner_gs[0])
            ax_psth = fig.add_subplot(inner_gs[1], sharex=ax_raster)

            uid = units[cls]
            spike_times = sess.get_spike_times(uid)
            onsets = onsets_by_cond[cond]

            plot_raster_subplot(ax_raster, ax_psth, spike_times, onsets, CLASS_COLORS[cls], cond)

            # Panel Label
            letter = panel_letters[panel_i]
            ax_raster.text(0.01, 1.06, f"{letter} (unit {uid})", transform=ax_raster.transAxes, fontsize=10, fontweight="bold", va="bottom")
            panel_i += 1

            if row_i == 0:
                ax_raster.set_title(f"{cls} Candidate", fontsize=11, fontweight="bold", color=CLASS_COLORS[cls], pad=15)
                # Dual time axis top
                top_ax = ax_raster.secondary_xaxis("top")
                top_ax.set_xticks(EPOCH_TIMES_MS)
                top_ax.set_xticklabels(
                    [f"{int(round(t))}ms - {lab}" for lab, t in zip(EPOCH_LABELS, EPOCH_TIMES_MS)],
                    rotation=30, ha="left", fontsize=6,
                )
            if col_i == 0:
                ax_raster.set_ylabel(f"COND {cond}\nTrials", fontsize=8, fontweight="bold")
                ax_psth.set_ylabel("Hz", fontsize=8)
            if row_i == 3:
                ax_psth.set_xlabel("Time from trial onset (ms)", fontsize=8)

    fig.suptitle(f"Figure 2: Exact-Pulse Matched Raster Grid (O+/S+/S- @ ~11-13.6 Hz)\nCausally Exponential-Smoothed Average Firing Rate (AFR) Profiles", fontsize=13, fontweight="bold", y=0.97)

    svg_path = OUT_DIR / "figure2_raster_grid_exact_pulse.svg"
    png_path = OUT_DIR / "figure2_raster_grid_exact_pulse.png"
    fig.savefig(svg_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=150, bbox_inches="tight")

    print(f"Wrote {svg_path.name}")
    print(f"Wrote {png_path.name}")


if __name__ == "__main__":
    main()
