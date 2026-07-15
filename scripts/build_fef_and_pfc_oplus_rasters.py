"""
scripts/build_fef_and_pfc_oplus_rasters.py

Generates raster grids with causal-smoothed PSTHs for the two requested PFC O+ units:
1. sub-V182o_ses-260629 unit 35.0 (overall rate = 3.61 Hz)
2. sub-V182o_ses-260708 unit 43.0 (overall rate = 6.77 Hz)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.ticker import MaxNLocator
import matplotlib
import matplotlib.gridspec as gridspec

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import jnwb as oa
from jnwb.sequence_layout import EPOCH_ONSETS_MS

NWB_DIR = Path("D:/analysis/nwb")
CONDITIONS = ["RRRR", "RXRR", "RRXR", "RRRX"]
WINDOW_MS = (-500.0, 4124.0)
N_TRIALS_SHOWN = 40

EPOCH_LABELS = list(EPOCH_ONSETS_MS.keys()) + ["end"]
EPOCH_TIMES_MS = list(EPOCH_ONSETS_MS.values()) + [WINDOW_MS[1]]

CLASS_COLORS = {"S+": "#1D9E75", "S-": "#993C1D", "O+": "#185FA5"}
EPOCH_SHADE_COLORS = {"p1": "#fcee21", "p2": "#93278f", "p3": "#019147", "p4": "#000bd4"}
EPOCH_SHADE_ALPHA = 0.18

OUT_DIR = REPO_ROOT / "outputs/publication_figures/figure2_raster_4x3"


def causal_exponential_smoothing(spike_times_rel: list[float], n_trials: int, window_ms: tuple[float, float], tau_ms: float = 30.0, bin_ms: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    t_start, t_stop = window_ms
    bins = np.arange(t_start, t_stop + bin_ms, bin_ms)
    counts, edges = np.histogram(spike_times_rel, bins=bins)
    bin_centers = (edges[:-1] + edges[1:]) / 2

    raw_rate = counts / (n_trials * (bin_ms / 1000.0))

    t_filter = np.arange(0, 5 * tau_ms, bin_ms)
    h = np.exp(-t_filter / tau_ms)
    h /= h.sum()

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

    # Styling
    ax_raster.set_xlim(WINDOW_MS[0], WINDOW_MS[1])
    ax_raster.set_ylim(0, N_TRIALS_SHOWN)
    ax_raster.invert_yaxis()
    ax_raster.xaxis.set_tick_params(labelbottom=False)
    ax_raster.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=4))
    ax_raster.grid(True, which="both", axis="x", linestyle=":", linewidth=0.5, alpha=0.5)

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

    # Specific PFC O+ units
    targets = [
        {"prefix": "sub-V182o_ses-260629", "uid": 35, "area": "PFC", "rate": 3.61},
        {"prefix": "sub-V182o_ses-260708", "uid": 43, "area": "PFC", "rate": 6.77}
    ]

    for unit_info in targets:
        prefix = unit_info["prefix"]
        uid = unit_info["uid"]
        area = unit_info["area"]
        rate = unit_info["rate"]

        nwb_file = NWB_DIR / (prefix + "_rec.nwb")
        if not nwb_file.exists():
            nwb_file = NWB_DIR / (prefix + ".nwb")
        if not nwb_file.exists():
            print(f"File not found: {nwb_file}")
            continue

        sess = oa.read(str(nwb_file))
        spike_times = sess.get_spike_times(uid)
        
        onsets_by_cond = {}
        for cond in CONDITIONS:
            epochs = sess.get_epochs(phase=2, condition=cond, correct_only=True)
            onsets_by_cond[cond] = epochs["start_time"].values

        # Setup 4 rows (conditions) x 1 column figure
        fig = plt.figure(figsize=(6, 12))
        outer_gs = gridspec.GridSpec(4, 1, figure=fig, hspace=0.35)

        for row_i, cond in enumerate(CONDITIONS):
            inner_gs = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=outer_gs[row_i], height_ratios=[3, 1], hspace=0.08)
            ax_raster = fig.add_subplot(inner_gs[0])
            ax_psth = fig.add_subplot(inner_gs[1], sharex=ax_raster)

            onsets = onsets_by_cond[cond]
            plot_raster_subplot(ax_raster, ax_psth, spike_times, onsets, CLASS_COLORS["O+"], cond)

            ax_raster.text(0.01, 1.06, f"COND {cond}", transform=ax_raster.transAxes, fontsize=9, fontweight="bold", va="bottom")
            if row_i == 0:
                ax_raster.set_title(f"O+ Candidate ({area}, unit {uid}) in {prefix}\nRate: {rate} Hz", fontsize=11, fontweight="bold", pad=15)
                # Dual time axis top
                top_ax = ax_raster.secondary_xaxis("top")
                top_ax.set_xticks(EPOCH_TIMES_MS)
                top_ax.set_xticklabels(
                    [f"{int(round(t))}ms - {lab}" for lab, t in zip(EPOCH_LABELS, EPOCH_TIMES_MS)],
                    rotation=30, ha="left", fontsize=6,
                )
            ax_raster.set_ylabel("Trials", fontsize=8)
            ax_psth.set_ylabel("Hz", fontsize=8)
            if row_i == 3:
                ax_psth.set_xlabel("Time from trial onset (ms)", fontsize=8)

        svg_path = OUT_DIR / f"figure2_{prefix}_unit{uid}_oplus_raster.svg"
        png_path = OUT_DIR / f"figure2_{prefix}_unit{uid}_oplus_raster.png"
        fig.savefig(svg_path, bbox_inches="tight")
        fig.savefig(png_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        print(f"Wrote {svg_path.name}")
        print(f"Wrote {png_path.name}")


if __name__ == "__main__":
    main()
