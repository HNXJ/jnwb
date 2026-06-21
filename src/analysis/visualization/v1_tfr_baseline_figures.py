"""V1 baseline-relative TFR figures with trial-matched subsampling."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis.lfp.lfp_constants import BANDS, SEQUENCE_TIMING_MS, colors_for_bands
from src.analysis.lfp.lfp_preproc import baseline_normalize
from src.analysis.visualization.plotting import OmissionPlotter

TFR_DIR = Path("D:/workspace/data/tfr_arrays")
DEFAULT_OUT_DIR = Path(
    "D:/workspace/omission/outputs/publication_visual_review/v1_tfr_aaab_vs_axab"
)

FREQS_HZ = np.arange(3, 201, 2)
N_TIME_BINS = 500
TIME_STEP_MS = 10.0
TIMES_MS = -1000.0 + np.arange(N_TIME_BINS) * TIME_STEP_MS
BASELINE_WINDOW_MS = (-500, 0)  # fixation window relative to P1 onset

V1_FILE_RE = re.compile(
    r"^(?P<session>.+)-(?P<probe>[ABC])-V1-(?P<condition>AAAB|AXAB)\.npy$"
)

BAND_COLORS = colors_for_bands(BANDS)

@dataclass(frozen=True)
class SessionV1Pair:
    session_id: str
    probe: str
    aaab_path: Path
    axab_path: Path
    n_aaab: int
    n_axab: int
    n_matched: int


def discover_v1_session_pairs(tfr_dir: Path = TFR_DIR) -> list[SessionV1Pair]:
    """Find sessions with both V1 AAAB and AXAB TFR arrays."""
    aaab_files = sorted(tfr_dir.glob("*-V1-AAAB.npy"))
    pairs: list[SessionV1Pair] = []
    for aaab_path in aaab_files:
        m = V1_FILE_RE.match(aaab_path.name)
        if m is None:
            continue
        session = m.group("session")
        probe = m.group("probe")
        axab_path = tfr_dir / f"{session}-{probe}-V1-AXAB.npy"
        if not axab_path.exists():
            continue
        n_aaab = int(np.load(aaab_path, mmap_mode="r").shape[0])
        n_axab = int(np.load(axab_path, mmap_mode="r").shape[0])
        pairs.append(
            SessionV1Pair(
                session_id=session,
                probe=probe,
                aaab_path=aaab_path,
                axab_path=axab_path,
                n_aaab=n_aaab,
                n_axab=n_axab,
                n_matched=min(n_aaab, n_axab),
            )
        )
    return pairs


def subsample_trials(arr: np.ndarray, n_trials: int, seed: int) -> np.ndarray:
    """Randomly subsample trials without replacement."""
    if arr.shape[0] < n_trials:
        raise ValueError(f"Requested {n_trials} trials but array has {arr.shape[0]}")
    if arr.shape[0] == n_trials:
        return np.asarray(arr)
    rng = np.random.default_rng(seed)
    idx = rng.choice(arr.shape[0], size=n_trials, replace=False)
    return np.asarray(arr[idx])


def channel_mean_baseline_db(
    power: np.ndarray,
    *,
    times_ms: np.ndarray = TIMES_MS,
    baseline_window_ms: tuple[float, float] = BASELINE_WINDOW_MS,
) -> np.ndarray:
    """Average all channels, then baseline-normalize each trial to dB.

    Parameters
    ----------
    power : ndarray
        Shape (trials, channels, freqs, times)

    Returns
    -------
    ndarray
        Shape (trials, freqs, times), float32 dB relative to baseline.
    """
    if power.ndim != 4:
        raise ValueError(f"Expected 4D power array, got shape {power.shape}")
    ch_mean = np.mean(power, axis=1)  # (trials, freqs, times)
    out = np.empty_like(ch_mean, dtype=np.float32)
    for i in range(ch_mean.shape[0]):
        out[i] = baseline_normalize(
            ch_mean[i], times_ms, baseline_window=baseline_window_ms
        ).astype(np.float32)
    return out


def load_matched_session_db(
    pair: SessionV1Pair,
    *,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Load AAAB/AXAB with equal trial counts for one session."""
    n = pair.n_matched
    aaab = np.load(pair.aaab_path, mmap_mode="r")
    axab = np.load(pair.axab_path, mmap_mode="r")
    aaab_sub = subsample_trials(aaab, n, seed=seed)
    axab_sub = subsample_trials(axab, n, seed=seed + 1)
    aaab_db = channel_mean_baseline_db(aaab_sub)
    axab_db = channel_mean_baseline_db(axab_sub)
    return aaab_db, axab_db


def aggregate_trial_stats(trials_db: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mean and SEM across trials. Input shape (trials, freqs, times)."""
    mean = np.mean(trials_db, axis=0)
    sem = np.std(trials_db, axis=0, ddof=1) / np.sqrt(trials_db.shape[0])
    return mean.astype(np.float32), sem.astype(np.float32)


def collapse_band(mean_db: np.ndarray, band_limits: tuple[int, int]) -> np.ndarray:
    """Average frequencies within a band. Input shape (freqs, times)."""
    fmin, fmax = band_limits
    mask = (FREQS_HZ >= fmin) & (FREQS_HZ <= fmax)
    if not np.any(mask):
        raise ValueError(f"No frequency bins in band {band_limits}")
    return np.mean(mean_db[mask], axis=0)


def _add_sequence_patches(fig: go.Figure, *, row: int = 1, col: int = 1) -> None:
    for name, info in SEQUENCE_TIMING_MS.items():
        fig.add_vrect(
            x0=info["start"],
            x1=info["end"],
            fillcolor=info["color"],
            opacity=0.08,
            line_width=0,
            row=row,
            col=col,
        )


def build_v1_tfr_heatmap_figure(
    aaab_mean: np.ndarray,
    axab_mean: np.ndarray,
) -> go.Figure:
    """Side-by-side V1 TFR heatmaps for AAAB vs AXAB."""
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("AAAB (predictable)", "AXAB (p2 omission)"),
        horizontal_spacing=0.08,
    )
    for col, data, title in (
        (1, aaab_mean, "AAAB"),
        (2, axab_mean, "AXAB"),
    ):
        fig.add_trace(
            go.Heatmap(
                z=data,
                x=TIMES_MS,
                y=FREQS_HZ,
                colorscale="Viridis",
                zmin=-3,
                zmax=3,
                colorbar=dict(title="dB") if col == 2 else None,
                showscale=(col == 2),
                name=title,
            ),
            row=1,
            col=col,
        )
        _add_sequence_patches(fig, row=1, col=col)
        fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="white", row=1, col=col)
        fig.update_xaxes(title_text="Time from P1 (ms)", range=[-1000, 4000], row=1, col=col)
        fig.update_yaxes(title_text="Frequency (Hz)", range=[3, 120], row=1, col=col)

    fig.update_layout(
        title=(
            "<b>V1 Relative Power (dB vs fixation baseline)</b><br>"
            "<sup>All 128 channels | trial-matched AAAB vs AXAB | pooled across sessions</sup>"
        ),
        template="plotly_white",
        height=520,
        width=1100,
        margin=dict(l=70, r=40, t=90, b=60),
    )
    return fig


def build_v1_band_trajectory_figure(
    aaab_mean: np.ndarray,
    aaab_sem: np.ndarray,
    axab_mean: np.ndarray,
    axab_sem: np.ndarray,
) -> go.Figure:
    """Band-resolved relative power trajectories for AAAB vs AXAB."""
    plotter = OmissionPlotter(
        title="V1 Band Power: AAAB vs AXAB",
        x_label="Time from P1",
        y_label="Relative power",
        subtitle="All V1 channels | fixation baseline (-500, 0) ms | trial-matched subsampling",
        x_unit="ms",
        y_unit="dB",
    )

    for band, limits in BANDS.items():
        aaab_band = collapse_band(aaab_mean, limits)
        axab_band = collapse_band(axab_mean, limits)
        aaab_sem_band = collapse_band(aaab_sem, limits)
        axab_sem_band = collapse_band(axab_sem, limits)
        color = BAND_COLORS.get(band, "#CFB87C")

        plotter.add_shaded_error_bar(
            TIMES_MS,
            aaab_band,
            aaab_sem_band,
            name=f"{band} AAAB",
            color=color,
        )
        plotter.add_trace(
            go.Scatter(
                x=TIMES_MS,
                y=axab_band,
                mode="lines",
                line=dict(color=color, width=2, dash="dash"),
                name=f"{band} AXAB",
            ),
            name=f"{band} AXAB",
        )

    for name, info in SEQUENCE_TIMING_MS.items():
        plotter.fig.add_vrect(
            x0=info["start"],
            x1=info["end"],
            fillcolor=info["color"],
            opacity=0.06,
            line_width=0,
        )
    plotter.add_xline(0, "P1", color="#CFB87C")
    plotter.fig.update_xaxes(range=[-1000, 4000])
    return plotter.fig


def build_v1_aaab_vs_axab_figures(
    *,
    tfr_dir: Path = TFR_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    seed: int = 0,
) -> dict[str, Any]:
    """Build grand-average V1 AAAB vs AXAB baseline-relative figures."""
    pairs = discover_v1_session_pairs(tfr_dir)
    if not pairs:
        raise FileNotFoundError(f"No V1 AAAB/AXAB pairs found in {tfr_dir}")

    aaab_trials: list[np.ndarray] = []
    axab_trials: list[np.ndarray] = []
    session_rows: list[dict[str, Any]] = []

    for i, pair in enumerate(pairs):
        aaab_db, axab_db = load_matched_session_db(pair, seed=seed + i * 10)
        aaab_trials.append(aaab_db)
        axab_trials.append(axab_db)
        session_rows.append(
            {
                "session_id": pair.session_id,
                "probe": pair.probe,
                "n_aaab": pair.n_aaab,
                "n_axab": pair.n_axab,
                "n_matched": pair.n_matched,
            }
        )

    aaab_pool = np.concatenate(aaab_trials, axis=0)
    axab_pool = np.concatenate(axab_trials, axis=0)
    aaab_mean, aaab_sem = aggregate_trial_stats(aaab_pool)
    axab_mean, axab_sem = aggregate_trial_stats(axab_pool)

    out_dir.mkdir(parents=True, exist_ok=True)
    heatmap_fig = build_v1_tfr_heatmap_figure(aaab_mean, axab_mean)
    band_fig = build_v1_band_trajectory_figure(aaab_mean, aaab_sem, axab_mean, axab_sem)

    heatmap_html = out_dir / "v1_tfr_aaab_vs_axab_heatmap.html"
    band_html = out_dir / "v1_tfr_aaab_vs_axab_bands.html"
    heatmap_fig.write_html(str(heatmap_html), include_plotlyjs="cdn")
    band_fig.write_html(str(band_html), include_plotlyjs="cdn")

    return {
        "n_sessions": len(pairs),
        "n_trials_aaab": int(aaab_pool.shape[0]),
        "n_trials_axab": int(axab_pool.shape[0]),
        "sessions": session_rows,
        "output_heatmap_html": str(heatmap_html),
        "output_band_html": str(band_html),
        "baseline_window_ms": BASELINE_WINDOW_MS,
        "seed": seed,
    }
