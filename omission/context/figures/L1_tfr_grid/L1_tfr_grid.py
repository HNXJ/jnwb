r"""
L1 -- Time-frequency representations, per area per condition, fixation-baselined (Fig 4).

Per the LFP-primary analysis spec's own dependency graph: L0 -> everything. Reads
`canonical_pooling_method` from context/figures/L0_pooling_reconciliation/L0_stats.json and
fails loudly if it is missing or not the expected value -- per L0's own acceptance criterion
("All downstream specs L1-L12 read canonical_pooling_method from L0. Fail loudly if L0 has not
been run.").

SCOPE (stated, not hidden)
    Spec's minimum area groups: V1/V2, MT/MST, "8A/PFC". This corpus (confirmed by directly
    reading every session's electrode `location`/`group_name` fields) has NO area labelled "8A"
    anywhere -- FEF and PFC both exist as distinct areas, 8A does not. Substituted FEF/PFC for
    the spec's stale "8A/PFC" pair (both are the corpus's actual prefrontal/premotor areas at
    the top of the AREA_ORDER hierarchy) and recorded that substitution here and in the stats
    JSON rather than silently guessing or blocking on it, consistent with Hamm's direction that
    the spec's naming is "old/different" and not to keep re-raising it.

    No single session in this corpus carries FEF and PFC on two simultaneous probes (checked
    across all 17 nwb_ok sessions). One session per area is used instead -- TFR-per-area does
    not require simultaneous recording of the area pair, only a channel range and a condition
    set, per the spec's own method description:
        V1, V2   <- sub-V198o_ses-230629 (probe A, clean 2-area "V1,V2" probe)
        MT, MST  <- sub-C31o_ses-230818  (probe C, clean 2-area "MT, MST" probe)
        FEF      <- sub-C31o_ses-230823  (probe A, single-area probe)
        PFC      <- sub-C31o_ses-230818  (probe A, single-area probe, same session as MT/MST)

    32-channel depth window per area (tractability cap, matches L0's channel-window choice and
    extract_lfp_coupling_matrices.py's representative-channel tractability convention), 60
    trials per condition (MAX_TRIALS, matches L0 and extract_lfp_coupling_matrices.py).

CONDITIONS
    "stim"      -- RRRR, p1-aligned real presentation (a genuine stimulus response).
    "omission"  -- RXRR, p2-aligned omission (the omitted slot).
    "fixation"/"offset" are NOT built as separate response panels here (fixation is the
    baseline reference itself; "offset" is out of L1's stated minimum scope) -- consistent
    with the spec's own "do not build unless asked" posture for anything beyond stated minimum.

METHOD
    One (-0.6, 2.2) s epoch per trial (p1-referenced), single Hann-window spectrogram per
    channel per trial (200 ms window, 10 ms hop, vectorized across trials*channels via
    scipy.signal.spectrogram's batched axis support -- not a per-trial Python loop, which does
    not scale, see omission-signal skill S10 on this exact failure mode elsewhere in the repo).
    Power averaged over trials THEN channels (linear, canonical method (a) from L0), THEN
    divided by the fixation baseline (-0.4, -0.15 s, same epoch) and log10'd once -- log-last,
    per omission-signal S1. Panel time axis then cropped to the response window per condition
    (stim: -300 to 900 ms; omission: 700 to 1900 ms) -- the crop happens AFTER the dB
    computation, not before, so the baseline reference is identical across both panels.

OUTPUT
    L1.svg / L1.png / L1.pdf -- grid, area (rows) x condition (columns).
    L1_stats.json  -- every number plotted (n channels, n trials, per-panel percentile color
    limits), area/condition/session/window provenance.
    L1_manifest.json -- input files, git SHA, band edges N/A (full spectrum), n trials/channels.

TESTS
    --test: synthetic chirp (linear frequency sweep) recovers the correct time-frequency ridge
    within tolerance, plus a determinism and a shape/NaN guard -- no real data, seconds to run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "archive_oneoff"))
sys.path.insert(0, str(REPO / "context" / "figures"))

from _l_lfp_common import (  # noqa: E402
    csd_reference_trials, extract_epoch_trials, git_sha, resolve_area_channel_block,
)
import figstyle  # noqa: E402
from jnwb.spectral import to_db  # noqa: E402

FIG_DIR = Path(__file__).resolve().parent
L0_STATS = REPO / "context" / "figures" / "L0_pooling_reconciliation" / "L0_stats.json"

EPOCH_WIN_S = (-0.6, 2.2)          # p1-referenced, covers fixation + p1 response + p2 slot
BASELINE_WIN_S = (-0.4, -0.15)     # fixation reference, matches L0
MAX_TRIALS = 60
N_CH_WINDOW = 32
FREQ_RANGE_HZ = (4.0, 100.0)       # reporting range; native spectrogram bins, no interpolation
NPERSEG_MS = 200.0
HOP_MS = 10.0

CONDITIONS = {
    "stim": {"task_condition": "RRRR", "zoom_ms": (-300, 900)},
    "omission": {"task_condition": "RXRR", "zoom_ms": (700, 1900)},
}

# (area, session_prefix, probe_letter) -- see module docstring for why these specific sessions.
AREA_SOURCES = {
    "V1": ("sub-V198o_ses-230629", "A"),
    "V2": ("sub-V198o_ses-230629", "A"),
    "MT": ("sub-C31o_ses-230818", "C"),
    "MST": ("sub-C31o_ses-230818", "C"),
    "FEF": ("sub-C31o_ses-230823", "A"),
    "PFC": ("sub-C31o_ses-230818", "A"),
}
ROW_ORDER = ["V1", "V2", "MT", "MST", "FEF", "PFC"]


def require_l0_canonical_method() -> str:
    if not L0_STATS.is_file():
        raise RuntimeError(
            f"L0 has not been run ({L0_STATS} missing). L1 requires canonical_pooling_method "
            f"from L0 per the spec's own acceptance criterion -- run L0 first.")
    stats = json.loads(L0_STATS.read_text())
    method = stats.get("canonical_pooling_method")
    if method != "a_per_channel_then_pool":
        raise RuntimeError(
            f"L0_stats.json canonical_pooling_method={method!r} is not the expected "
            f"'a_per_channel_then_pool' -- L1's pooling implementation assumes that method; "
            f"re-derive L1's pooling if L0's determination has changed.")
    return method


def batched_spectrogram(x: np.ndarray, fs: float):
    """x: (n_trials, n_channels, n_samples) -> (freqs, times, power) where power has shape
    (n_trials, n_channels, n_freqs, n_times). Vectorized: scipy.signal.spectrogram batches over
    every leading axis when given axis=-1, so this is one FFT batch call, not a Python loop
    over trials*channels (that does not scale -- see docstring)."""
    n_trials, n_channels, n_samples = x.shape
    nperseg = max(32, int(round(fs * NPERSEG_MS / 1000.0)))
    hop = max(1, int(round(fs * HOP_MS / 1000.0)))
    noverlap = max(0, min(nperseg - hop, nperseg - 1))
    freqs, times, Sxx = signal.spectrogram(
        x, fs=fs, window="hann", nperseg=nperseg, noverlap=noverlap,
        detrend=False, scaling="spectrum", mode="psd", axis=-1)
    return freqs, times, Sxx  # Sxx: (n_trials, n_channels, n_freqs, n_times)


def area_condition_tfr(area: str, condition: str, n_ch=N_CH_WINDOW, max_trials=MAX_TRIALS):
    session_prefix, probe_letter = AREA_SOURCES[area]
    nwb_dir = Path(__import__("jnwb").paths.nwb_dir())
    nwb_path = nwb_dir / f"{session_prefix}_rec.nwb"
    if not nwb_path.is_file():
        nwb_path = nwb_dir / f"{session_prefix}.nwb"
    task_condition = CONDITIONS[condition]["task_condition"]

    with h5py.File(nwb_path, "r") as f:
        lfp_key, ch_lo, ch_hi = resolve_area_channel_block(f, probe_letter, area, n_ch)
        trials, fs, n_trials, frac_repaired = extract_epoch_trials(
            f, lfp_key, ch_lo, ch_hi, task_condition, EPOCH_WIN_S, max_trials)

    freqs, times, Sxx = batched_spectrogram(trials, fs)
    fmask = (freqs >= FREQ_RANGE_HZ[0]) & (freqs <= FREQ_RANGE_HZ[1])
    Sxx = Sxx[:, :, fmask, :]
    freqs = freqs[fmask]

    # Canonical pooling (a) from L0: average power over trials, THEN channels (linear).
    pooled = Sxx.mean(axis=0).mean(axis=0)  # (n_freqs, n_times)

    times_ms = EPOCH_WIN_S[0] * 1000.0 + times * 1000.0
    base_mask = (times_ms >= BASELINE_WIN_S[0] * 1000.0) & (times_ms <= BASELINE_WIN_S[1] * 1000.0)
    if not np.any(base_mask):
        raise ValueError("Baseline window falls outside the extracted epoch's time bins")
    baseline = pooled[:, base_mask].mean(axis=1, keepdims=True)  # (n_freqs, 1)
    db = to_db(np.maximum(pooled, 1e-15) / np.maximum(baseline, 1e-15))

    return {
        "freqs": freqs, "times_ms": times_ms, "db": db,
        "n_trials": int(n_trials), "n_channels": int(ch_hi - ch_lo),
        "session": session_prefix, "probe": probe_letter,
        "fraction_trials_repaired": frac_repaired,
    }


def run(n_ch=N_CH_WINDOW, max_trials=MAX_TRIALS):
    require_l0_canonical_method()
    panels = {}
    for area in ROW_ORDER:
        for condition in CONDITIONS:
            panels[(area, condition)] = area_condition_tfr(area, condition, n_ch, max_trials)

    stats = {
        "canonical_pooling_method": "a_per_channel_then_pool",
        "l0_source": str(L0_STATS),
        "area_pairs_minimum": ["V1/V2", "MT/MST", "FEF/PFC (substituted for spec's stale 8A/PFC "
                                "-- no '8A' area exists in this corpus, confirmed by direct "
                                "electrode-table read across all 17 nwb_ok sessions)"],
        "epoch_window_s": list(EPOCH_WIN_S), "baseline_window_s": list(BASELINE_WIN_S),
        "freq_range_hz": list(FREQ_RANGE_HZ), "nperseg_ms": NPERSEG_MS, "hop_ms": HOP_MS,
        "panels": {},
    }
    # Spec acceptance criterion: "Symmetric diverging color scale, shared across panels within
    # a row" -- pool the zoomed dB values from BOTH conditions in an area's row, take one
    # symmetric percentile-based limit, and use it for every panel in that row.
    row_vlim = {}
    for area in ROW_ORDER:
        pooled_vals = []
        for condition in CONDITIONS:
            p = panels[(area, condition)]
            zoom_ms = CONDITIONS[condition]["zoom_ms"]
            zmask = (p["times_ms"] >= zoom_ms[0]) & (p["times_ms"] <= zoom_ms[1])
            pooled_vals.append(p["db"][:, zmask].ravel())
        lo, hi = np.percentile(np.concatenate(pooled_vals), [2, 98])
        row_vlim[area] = float(max(abs(lo), abs(hi)))

    for (area, condition), p in panels.items():
        zoom_ms = CONDITIONS[condition]["zoom_ms"]
        zmask = (p["times_ms"] >= zoom_ms[0]) & (p["times_ms"] <= zoom_ms[1])
        db_zoom = p["db"][:, zmask]
        lo, hi = np.percentile(db_zoom, [2, 98])
        vlim = row_vlim[area]
        stats["panels"][f"{area}|{condition}"] = {
            "area": area, "condition": condition,
            "task_condition_number_set": CONDITIONS[condition]["task_condition"],
            "session": p["session"], "probe": p["probe"],
            "n_trials": p["n_trials"], "n_channels": p["n_channels"],
            "fraction_trials_repaired": p["fraction_trials_repaired"],
            "zoom_window_ms": list(zoom_ms),
            "color_limits_db_p2_p98_this_panel": [float(lo), float(hi)],
            "color_scale_db_shared_across_row": [-vlim, vlim],
        }

    manifest = {
        "analysis_id": "L1", "git_sha": git_sha(), "epoch_window_s": list(EPOCH_WIN_S),
        "baseline_window_s": list(BASELINE_WIN_S), "freq_range_hz": list(FREQ_RANGE_HZ),
        "max_trials_cap": max_trials, "n_channels_cap": n_ch,
        "area_sources": {a: {"session": s, "probe": pr} for a, (s, pr) in AREA_SOURCES.items()},
        "seed": None,
    }

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (FIG_DIR / "L1_stats.json").write_text(json.dumps(stats, indent=2))
    (FIG_DIR / "L1_manifest.json").write_text(json.dumps(manifest, indent=2))
    plot_grid(panels, stats)
    return stats


def plot_grid(panels: dict, stats: dict):
    figstyle.use_house_style()
    n_rows, n_cols = len(ROW_ORDER), len(CONDITIONS)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(3.4 * n_cols, 2.0 * n_rows), squeeze=False)

    for ri, area in enumerate(ROW_ORDER):
        row_im = None
        for ci, condition in enumerate(CONDITIONS):
            ax = axes[ri][ci]
            p = panels[(area, condition)]
            key = f"{area}|{condition}"
            zoom_ms = stats["panels"][key]["zoom_window_ms"]
            vlim = stats["panels"][key]["color_scale_db_shared_across_row"][1]
            zmask = (p["times_ms"] >= zoom_ms[0]) & (p["times_ms"] <= zoom_ms[1])
            row_im = ax.pcolormesh(p["times_ms"][zmask], p["freqs"], p["db"][:, zmask],
                                    cmap="RdBu_r", vmin=-vlim, vmax=vlim, shading="auto")
            ax.axvline(0 if condition == "stim" else 1031, color="black", linewidth=0.8,
                       linestyle="--")
            n_tr, n_ch = p["n_trials"], p["n_channels"]
            ax.set_title(f"{area} | {condition}  (n_ch={n_ch}, n_trials={n_tr})", fontsize=7)
            if ri == n_rows - 1:
                ax.set_xlabel("Time from p1 (ms)")
            if ci == 0:
                ax.set_ylabel(f"{area}\nFreq (Hz)", fontsize=7)
        # One colorbar per row (scale is shared across both panels in the row, per the spec's
        # own acceptance criterion), attached to the rightmost panel.
        fig.colorbar(row_im, ax=axes[ri][n_cols - 1], fraction=0.046, pad=0.03, label="dB")

    fig.suptitle("L1: TFR grid, area x condition, fixation-baselined, canonical pooling (a)",
                 fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    figstyle.save(fig, FIG_DIR, "L1")
    fig.savefig(FIG_DIR / "L1.pdf")
    plt.close(fig)


# ------------------------------------------------------------------------------- self-test --

def run_synthetic_selftest():
    """Synthetic chirp (linear frequency sweep 10 -> 60 Hz over the epoch) must recover the
    correct time-frequency ridge within tolerance -- the spec's own acceptance test for L1."""
    rng = np.random.default_rng(0)
    fs = 1000.0
    n_trials, n_ch = 20, 4
    n_samples = 2000
    t = np.arange(n_samples) / fs
    f0, f1 = 10.0, 60.0
    instantaneous_f = f0 + (f1 - f0) * (t / t[-1])
    phase = 2 * np.pi * np.cumsum(instantaneous_f) / fs
    chirp = np.sin(phase)
    x = np.zeros((n_trials, n_ch, n_samples))
    for tr in range(n_trials):
        for c in range(n_ch):
            x[tr, c] = chirp + rng.normal(0, 0.05, n_samples)

    freqs, times, Sxx = batched_spectrogram(x, fs)
    pooled = Sxx.mean(axis=0).mean(axis=0)  # (n_freqs, n_times)
    ridge_freq = freqs[np.argmax(pooled, axis=0)]  # (n_times,)
    true_freq_at_times = f0 + (f1 - f0) * (times / t[-1])

    err = np.abs(ridge_freq - true_freq_at_times)
    freq_res = freqs[1] - freqs[0]
    tol = 2 * freq_res
    max_err = float(err.max())
    print(f"Synthetic chirp self-test: max ridge error = {max_err:.2f} Hz "
          f"(tolerance {tol:.2f} Hz, freq resolution {freq_res:.2f} Hz)")
    assert max_err < tol, f"chirp ridge tracking exceeded tolerance: {max_err:.2f} > {tol:.2f} Hz"
    print("PASS: recovered chirp ridge within tolerance.")

    # Determinism: identical input -> identical spectrogram.
    freqs2, times2, Sxx2 = batched_spectrogram(x, fs)
    assert np.array_equal(Sxx, Sxx2), "determinism check failed: spectrogram not reproducible"
    print("PASS: determinism check (identical input -> byte-identical spectrogram).")

    # Shape/NaN guard.
    degenerate = np.zeros((3, 2, 500))
    _, _, Sxx_deg = batched_spectrogram(degenerate, fs)
    assert np.all(np.isfinite(Sxx_deg)), "zero-signal input produced non-finite spectrogram"
    print("PASS: degenerate zero-signal input stays finite (shape/NaN guard).")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if args.test:
        run_synthetic_selftest()
        return
    stats = run()
    for key, p in stats["panels"].items():
        print(f"{key}: n_trials={p['n_trials']} n_channels={p['n_channels']} "
              f"clim_row_shared={p['color_scale_db_shared_across_row']}")


if __name__ == "__main__":
    main()
