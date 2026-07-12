"""Generate TFR heatmap grid figures from joined pipeline outputs.

Uses the Omission canonical palette (indices 0..12) for bands and area traces.
Does not invent one-off hex values outside that ordered list.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import ttest_1samp, wilcoxon

# Canonical Omission palette (source: .cursor/rules/omission-palette.mdc).
# src/analysis/lfp/lfp_constants.py is absent in this checkout; keep in sync.
OMISSION_PALETTE = (
    "#CFB87C",  # 0 GOLD
    "#2563EB",  # 1 BLUE
    "#8F00FF",  # 2 VIOLET
    "#DC2626",  # 3 RED
    "#16A34A",  # 4 GREEN
    "#000000",  # 5 BLACK
    "#FF1493",  # 6 PINK
    "#8B4513",  # 7 BROWN
    "#00FFCC",  # 8 TEAL
    "#FF5E00",  # 9 ORANGE
    "#C9A88A",  # 10 RED_BEIGE
    "#D3D3D3",  # 11 GRAY
    "#FFFFFF",  # 12 WHITE
)

# Canonical band mapping: Theta..Gamma_H -> palette index 0..5
BANDS_TFR = {
    "Theta": (3.0, 7.0),
    "Alpha": (8.0, 12.0),
    "l-beta": (12.0, 20.0),
    "h-beta": (20.0, 30.0),
    "Gamma_L": (32.0, 50.0),
    "Gamma_H": (50.0, 90.0),
}
BAND_COLORS = {
    "Theta": OMISSION_PALETTE[0],
    "Alpha": OMISSION_PALETTE[1],
    "l-beta": OMISSION_PALETTE[2],
    "h-beta": OMISSION_PALETTE[3],
    "Gamma_L": OMISSION_PALETTE[4],
    "Gamma_H": OMISSION_PALETTE[5],
}

# Area traces: palette indices (not invented hex)
AREA_COLORS = {
    "V1": OMISSION_PALETTE[1],   # BLUE
    "V3a": OMISSION_PALETTE[4],  # GREEN
    "MST": OMISSION_PALETTE[9],  # ORANGE
    "PFC": OMISSION_PALETTE[6],  # PINK
}

FREQS_HZ = np.arange(3, 201, 2)
TIMES_MS = -1000.0 + np.arange(500) * 10.0
RELATIVE_TIME_MS = np.arange(-156, 192) * 10.0

SLOT_CONDITIONS = {
    2: ["AXAB", "BXBA", "RXRR", "AAAB", "BBBA", "RRRR"],
    3: ["AAXB", "BBXA", "RRXR", "AAAB", "BBBA", "RRRR"],
    4: ["AAAX", "BBBX", "RRRX"],
}

COND_GROUPS = {
    "control_p2": ["AAAB", "BBBA", "RRRR"],
    "control_p3": ["AAAB", "BBBA", "RRRR"],
    "omission_p2": ["AXAB", "BXBA", "RXRR"],
    "omission_p3": ["AAXB", "BBXA", "RRXR"],
}

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tfr-dir",
        type=Path,
        default=Path(os.environ.get("OMISSION_TFR_DIR", "D:/workspace/data/tfr_arrays")),
        help="Directory of *.npy TFR arrays",
    )
    parser.add_argument(
        "--layer-masks",
        type=Path,
        default=REPO_ROOT
        / "outputs/publication_visual_review/area_layer_tfr/layer_masks.json",
        help="JSON layer-mask cache",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("outputs/figures"),
        help="Output directory for SVG/PNG",
    )
    parser.add_argument(
        "--session",
        default=None,
        help="Optional session-prefix substring filter (e.g. 'sub-C31o_ses-230823') to "
             "restrict which .npy files are scanned - much faster than the default "
             "full-directory scan when only one session is needed.",
    )
    return parser.parse_args()


def get_probe_layer_masks(layer_masks_cache, session_id, probe_letter):
    target = f"{session_id}|{probe_letter}"
    for key, entry in layer_masks_cache.items():
        if target in key or key in target:
            return np.array(entry["superficial_mask"])
    return None


def run(tfr_dir: Path, layer_masks_path: Path, out_dir: Path, session: str = None) -> None:
    if not layer_masks_path.is_file():
        raise FileNotFoundError(f"Layer masks not found: {layer_masks_path}")
    if not tfr_dir.is_dir():
        raise FileNotFoundError(f"TFR directory not found: {tfr_dir}")

    with layer_masks_path.open("r", encoding="utf-8") as f:
        layer_masks_cache = json.load(f).get("by_key", {})

    areas = ["V1", "V3a", "MST", "PFC"]
    fig, axes = plt.subplots(5, 2, figsize=(14, 22), facecolor="white")

    broadband_traces = {
        "control": {area: None for area in areas},
        "omission": {area: None for area in areas},
    }

    im_c = None
    for row_idx, area in enumerate(areas):
        print(f"Processing area {area}...")
        glob_pattern = f"{session}*.npy" if session else "*.npy"
        files = []
        for path in tfr_dir.glob(glob_pattern):
            m = re.match(r"^(.+)-([ABC])-([A-Za-z0-9]+)-([A-Z0-9]+)\.npy$", path.name)
            if not m:
                continue
            sess, probe, file_area, cond = m.groups()
            if file_area != area:
                continue
            for slot, conds in SLOT_CONDITIONS.items():
                if cond in conds:
                    files.append(
                        {
                            "path": path,
                            "session": sess,
                            "probe": probe,
                            "condition": cond,
                            "slot": slot,
                        }
                    )
        print(f"  {area}: {len(files)} matching files")

        if not files:
            print(f"No files for {area}")
            continue

        group_trials = {g: [] for g in COND_GROUPS}
        idx_d1 = (TIMES_MS >= 531.0) & (TIMES_MS <= 1031.0)
        idx_d2 = (TIMES_MS >= 1562.0) & (TIMES_MS <= 2062.0)

        for f_info in files:
            mask = get_probe_layer_masks(
                layer_masks_cache, f_info["session"], f_info["probe"]
            )
            if mask is None or not np.any(mask):
                continue
            try:
                power = np.load(f_info["path"], mmap_mode="r")
            except Exception:
                continue

            layer_power = np.mean(power[:, mask, :, :], axis=1)
            cond = f_info["condition"]

            for g, conditions in COND_GROUPS.items():
                if cond not in conditions:
                    continue
                align_shift = 1031.0 if "p2" in g else 2062.0
                baseline_mask = idx_d1 if "p2" in g else idx_d2

                baseline = np.mean(layer_power[..., baseline_mask], axis=-1, keepdims=True)
                power_db = 10.0 * np.log10(
                    np.maximum(layer_power, 1e-12) / np.maximum(baseline, 1e-12)
                )
                power_db = np.nan_to_num(power_db, nan=0.0)

                onset_idx = int(round((align_shift - (-1000.0)) / 10.0))
                start_idx, end_idx = onset_idx - 156, onset_idx + 192

                aligned = np.full(
                    (power.shape[0], len(FREQS_HZ), len(RELATIVE_TIME_MS)),
                    np.nan,
                    dtype=np.float32,
                )
                src_start, src_end = max(0, start_idx), min(500, end_idx)
                dest_start = src_start - start_idx
                dest_end = dest_start + (src_end - src_start)
                aligned[:, :, dest_start:dest_end] = power_db[:, :, src_start:src_end]
                group_trials[g].append(aligned)

        group_data = {}
        for g in COND_GROUPS:
            if group_trials[g]:
                group_data[g] = np.concatenate(group_trials[g], axis=0)
            else:
                group_data[g] = np.empty((0, len(FREQS_HZ), len(RELATIVE_TIME_MS)))

        active_groups = ["control_p2", "control_p3", "omission_p2", "omission_p3"]
        ns = [group_data[g].shape[0] for g in active_groups]
        if min(ns) == 0:
            print(f"Skipping {area} due to 0 trials.")
            continue

        N = min(ns)
        rng = np.random.default_rng(42)
        subsampled = {
            g: group_data[g][rng.choice(group_data[g].shape[0], size=N, replace=False)]
            for g in active_groups
        }

        control_trials = np.concatenate(
            [subsampled["control_p2"], subsampled["control_p3"]], axis=0
        )
        omission_trials = np.concatenate(
            [subsampled["omission_p2"], subsampled["omission_p3"]], axis=0
        )

        control_heatmap = np.nanmean(control_trials, axis=0)
        omission_heatmap = np.nanmean(omission_trials, axis=0)

        c_broadband = np.nanmean(control_trials, axis=1)
        o_broadband = np.nanmean(omission_trials, axis=1)

        broadband_traces["control"][area] = np.nanmean(c_broadband, axis=0)
        broadband_traces["omission"][area] = np.nanmean(o_broadband, axis=0)

        n_times = len(RELATIVE_TIME_MS)
        alpha_corrected = 0.01 / n_times

        c_sig_inc = np.zeros(n_times, dtype=bool)
        c_sig_dec = np.zeros(n_times, dtype=bool)
        o_sig_inc = np.zeros(n_times, dtype=bool)
        o_sig_dec = np.zeros(n_times, dtype=bool)

        for t in range(n_times):
            c_vals = c_broadband[:, t]
            if len(c_vals) > 2 and not np.all(c_vals == c_vals[0]):
                _, t_p = ttest_1samp(c_vals, 0.0)
                try:
                    _, w_p = wilcoxon(c_vals)
                except Exception:
                    w_p = 1.0
                if t_p < alpha_corrected and w_p < alpha_corrected:
                    if np.mean(c_vals) > 0:
                        c_sig_inc[t] = True
                    else:
                        c_sig_dec[t] = True

            o_vals = o_broadband[:, t]
            if len(o_vals) > 2 and not np.all(o_vals == o_vals[0]):
                _, t_p = ttest_1samp(o_vals, 0.0)
                try:
                    _, w_p = wilcoxon(o_vals)
                except Exception:
                    w_p = 1.0
                if t_p < alpha_corrected and w_p < alpha_corrected:
                    if np.mean(o_vals) > 0:
                        o_sig_inc[t] = True
                    else:
                        o_sig_dec[t] = True

        ax_c = axes[row_idx, 0]
        im_c = ax_c.imshow(
            control_heatmap,
            aspect="auto",
            origin="lower",
            extent=[RELATIVE_TIME_MS[0], RELATIVE_TIME_MS[-1], FREQS_HZ[0], FREQS_HZ[-1]],
            cmap="viridis",
            vmin=-1.5,
            vmax=1.5,
        )
        ax_c.set_title(f"{area} Control", fontsize=12, fontweight="bold")

        ax_o = axes[row_idx, 1]
        ax_o.imshow(
            omission_heatmap,
            aspect="auto",
            origin="lower",
            extent=[RELATIVE_TIME_MS[0], RELATIVE_TIME_MS[-1], FREQS_HZ[0], FREQS_HZ[-1]],
            cmap="viridis",
            vmin=-1.5,
            vmax=1.5,
        )
        ax_o.set_title(f"{area} Omission", fontsize=12, fontweight="bold")

        for ax in [ax_c, ax_o]:
            ax.axvspan(-1000, -500, color=OMISSION_PALETTE[11], alpha=0.25)  # GRAY delay
            ax.axvspan(0, 500, color=OMISSION_PALETTE[0], alpha=0.12)  # GOLD p1-ish
            ax.axvspan(1031, 1531, color=OMISSION_PALETTE[2], alpha=0.12)  # VIOLET p2
            for band_name, (fmin, fmax) in BANDS_TFR.items():
                rect = patches.Rectangle(
                    (0.0, fmin),
                    500.0,
                    fmax - fmin,
                    linewidth=1.0,
                    edgecolor=BAND_COLORS[band_name],
                    facecolor="none",
                    linestyle="--",
                )
                ax.add_patch(rect)

        sig_y = 175.0
        for t in range(n_times):
            t_ms = RELATIVE_TIME_MS[t]
            if c_sig_inc[t]:
                ax_c.plot(
                    [t_ms, t_ms + 10.0],
                    [sig_y, sig_y],
                    color=OMISSION_PALETTE[1],
                    linewidth=3.5,
                    solid_capstyle="butt",
                )
            elif c_sig_dec[t]:
                ax_c.plot(
                    [t_ms, t_ms + 10.0],
                    [sig_y, sig_y],
                    color=OMISSION_PALETTE[3],
                    linewidth=3.5,
                    solid_capstyle="butt",
                )
            if o_sig_inc[t]:
                ax_o.plot(
                    [t_ms, t_ms + 10.0],
                    [sig_y, sig_y],
                    color=OMISSION_PALETTE[1],
                    linewidth=3.5,
                    solid_capstyle="butt",
                )
            elif o_sig_dec[t]:
                ax_o.plot(
                    [t_ms, t_ms + 10.0],
                    [sig_y, sig_y],
                    color=OMISSION_PALETTE[3],
                    linewidth=3.5,
                    solid_capstyle="butt",
                )

        for ax in [ax_c, ax_o]:
            ax.set_xlim(-1000, 1920)
            ax.set_ylim(3, 200)
            ax.set_yscale("log")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.set_ylabel("Frequency (Hz)", fontsize=9)

    ax_t_c = axes[4, 0]
    ax_t_o = axes[4, 1]

    for area in areas:
        color = AREA_COLORS[area]
        c_tr = broadband_traces["control"][area]
        if c_tr is not None:
            ax_t_c.plot(RELATIVE_TIME_MS, c_tr, color=color, linewidth=2.0, label=area)
        o_tr = broadband_traces["omission"][area]
        if o_tr is not None:
            ax_t_o.plot(RELATIVE_TIME_MS, o_tr, color=color, linewidth=2.0, label=area)

    for ax in [ax_t_c, ax_t_o]:
        ax.axvspan(-1000, -500, color=OMISSION_PALETTE[11], alpha=0.25)
        ax.axvspan(0, 500, color=OMISSION_PALETTE[0], alpha=0.12)
        ax.axvspan(1031, 1531, color=OMISSION_PALETTE[2], alpha=0.12)
        ax.axhline(0.0, color=OMISSION_PALETTE[5], linestyle=":", linewidth=1.0)
        ax.set_xlim(-1000, 1920)
        ax.set_ylim(-1.0, 1.0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_ylabel("Broadband Power (dB)", fontsize=9)
        ax.set_xlabel("Time from omission onset (ms)", fontsize=9)
        ax.legend(
            loc="upper right",
            frameon=True,
            facecolor="white",
            edgecolor=OMISSION_PALETTE[11],
        )

    ax_t_c.set_title("Control Broadband Power Traces", fontsize=11, fontweight="bold")
    ax_t_o.set_title("Omission Broadband Power Traces", fontsize=11, fontweight="bold")

    legend_elements = [
        patches.Patch(
            facecolor="none",
            edgecolor=OMISSION_PALETTE[5],
            linestyle="--",
            label="Dashed Rectangle: Extraction Bands",
        ),
        plt.Line2D(
            [0],
            [0],
            color=OMISSION_PALETTE[1],
            linewidth=3.5,
            label="Top Bar (Blue): Significant Increase (p<0.01)",
        ),
        plt.Line2D(
            [0],
            [0],
            color=OMISSION_PALETTE[3],
            linewidth=3.5,
            label="Top Bar (Red): Significant Decrease (p<0.01)",
        ),
    ]
    fig.legend(
        handles=legend_elements,
        loc="upper right",
        bbox_to_anchor=(0.95, 0.96),
        frameon=True,
        facecolor="white",
        edgecolor=OMISSION_PALETTE[11],
        fontsize=10,
    )

    fig.subplots_adjust(right=0.88, top=0.92)
    if im_c is not None:
        cbar_ax = fig.add_axes([0.91, 0.25, 0.02, 0.6])
        fig.colorbar(im_c, cax=cbar_ax, label="Relative Power (dB)")

    plt.suptitle(
        "LFP TFR Heatmaps & Broadband Traces (V1, V3a, MST, PFC)\n"
        "Dashed Rectangles: Canonical Bands (Theta..Gamma_H)\n"
        "Solid Top Line: Significant Power Modulation "
        "(p < 0.01 Bonferroni, Blue=Inc, Red=Dec)",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "04_tfr_heatmap_traces.svg", format="svg", bbox_inches="tight")
    fig.savefig(
        out_dir / "04_tfr_heatmap_traces.png",
        format="png",
        bbox_inches="tight",
        dpi=150,
    )
    plt.close(fig)
    print(f"Saved figures to {out_dir}")


def main() -> None:
    args = parse_args()
    run(args.tfr_dir, args.layer_masks, args.out_dir, session=args.session)


if __name__ == "__main__":
    main()
