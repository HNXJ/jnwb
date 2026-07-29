"""
Publication TFR suite aligned to the omission sequence presentation layout.

For one NWB session (via its TFR .npy inventory):
  - TFR spectrograms: canonical 11 areas × {RRRR, RXRR, RRXR, RRRX}
  - TFR band traces: same areas × conditions, 7 bands, ±2 SEM, black sig bars

Background is Plotly vector shapes from jnwb.sequence_layout (not a raster image).

Dual-area probes (\"Y, Z\" / \"Y/Z\" / bare \"V3\"):
  channels 1–64 → first area, channels 65–128 → second area.
  Bare V3 → V3d (1–64) then V3a (65–128).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from jnwb.sequence_layout import (  # noqa: E402
    BANDS_7,
    BAND_COLORS_7,
    CANONICAL_AREAS_11,
    FULL_SEQUENCE_END_MS,
    FULL_SEQUENCE_START_MS,
    OMISSION_PALETTE,
    R_FAMILY_CONDITIONS,
    apply_sequence_layout,
    channel_slice_for_area,
    export_figure_html,
    export_figure_svg,
    layout_template_svgs,
    make_sequence_figure,
    omission_window_ms,
    parse_probe_areas,
)

# Preprocessed TFR time axis used across the repo (ms relative to p1)
TFR_TIMES_MS = -1000.0 + np.arange(500) * 10.0
TFR_FREQS_HZ = np.arange(3, 201, 2)  # 99 bins — matches stored arrays


def _split_csv_tokens(values: Optional[Sequence[str]]) -> List[str]:
    """Accept space-separated and/or comma-separated CLI tokens."""
    if not values:
        return []
    out: List[str] = []
    for raw in values:
        for part in str(raw).split(","):
            token = part.strip()
            if token:
                out.append(token)
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--session",
        default=os.environ.get("OMISSION_SESSION", "sub-C31o_ses-230823"),
        help="Session id prefix matching TFR filenames",
    )
    p.add_argument(
        "--tfr-dir",
        type=Path,
        default=Path(os.environ.get("OMISSION_TFR_DIR", "D:/workspace/data/tfr_arrays")),
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("outputs/figures/sequence_tfr_suite"),
    )
    p.add_argument(
        "--areas",
        nargs="*",
        default=None,
        help="Areas to plot (default: canonical 11). Comma or space separated.",
    )
    p.add_argument(
        "--conditions",
        nargs="*",
        default=None,
        help="Conditions (default: RRRR RXRR RRXR RRRX). Comma or space separated.",
    )
    p.add_argument(
        "--max-areas",
        type=int,
        default=None,
        help="Optional cap for smoke runs",
    )
    p.add_argument(
        "--layout-only",
        action="store_true",
        help="Only export sequence layout SVG templates (no TFR load)",
    )
    p.add_argument(
        "--no-svg",
        action="store_true",
        help="Skip kaleido SVG export (HTML only)",
    )
    args = p.parse_args()
    raw_areas = _split_csv_tokens(args.areas) or list(CANONICAL_AREAS_11)
    # Expand dual labels (V3 → V3d,V3a); preserve order, drop duplicates
    seen = set()
    areas: List[str] = []
    for a in raw_areas:
        for name in parse_probe_areas(a):
            if name not in seen:
                seen.add(name)
                areas.append(name)
    args.areas = areas
    args.conditions = _split_csv_tokens(args.conditions) or list(R_FAMILY_CONDITIONS)
    return args


def index_tfr_files(
    tfr_dir: Path, session: str
) -> Dict[Tuple[str, str], Tuple[Path, slice]]:
    """Map (canonical_area, condition) → (npy path, channel slice).

    Dual-area file tokens (V3, \"Y/Z\", \"Y,Z\") expand to two area keys with
    ch 1–64 / 65–128 slices. First matching probe wins per (area, condition).
    """
    out: Dict[Tuple[str, str], Tuple[Path, slice]] = {}
    pat = re.compile(
        rf"^{re.escape(session)}-([ABC])-([A-Za-z0-9,/]+)-([A-Z0-9]+)\.npy$"
    )
    for path in sorted(tfr_dir.glob(f"{session}-*.npy")):
        m = pat.match(path.name)
        if not m:
            continue
        _probe, area_raw, cond = m.groups()
        probe_areas = parse_probe_areas(area_raw)
        if not probe_areas:
            continue
        for area in probe_areas:
            ch = channel_slice_for_area(probe_areas, area)
            if ch is None:
                continue
            key = (area, cond)
            if key not in out:
                out[key] = (path, ch)
    return out


def _tfr_as_trials_ch_f_t(power: np.ndarray) -> np.ndarray:
    """Normalize TFR array to (trials, channels, freqs, times)."""
    if power.ndim != 4:
        raise ValueError(f"Expected 4-D TFR, got {power.shape}")
    if power.shape[-1] == len(TFR_TIMES_MS):
        return power  # (trials, ch, f, t)
    if power.shape[2] == len(TFR_TIMES_MS):
        # (ch, f, t, trials) → (trials, ch, f, t)
        return np.transpose(power, (3, 0, 1, 2))
    raise ValueError(f"Unrecognized TFR shape {power.shape}")


def load_trial_avg_db(
    path: Path,
    channel_slice: slice = slice(None),
    *,
    baseline_start_ms: float = -500.0,
    baseline_end_ms: float = 0.0,
) -> np.ndarray:
    """
    Load TFR npy → mean dB (freqs, times) over trials and selected channels,
    relative to fx baseline.
    """
    power = _tfr_as_trials_ch_f_t(np.load(path, mmap_mode="r"))
    trial_mean = np.nanmean(power[:, channel_slice, :, :], axis=(0, 1))  # (f, t)

    base_mask = (TFR_TIMES_MS >= baseline_start_ms) & (TFR_TIMES_MS < baseline_end_ms)
    baseline = np.nanmean(trial_mean[:, base_mask], axis=1, keepdims=True)
    db = 10.0 * np.log10(np.maximum(trial_mean, 1e-12) / np.maximum(baseline, 1e-12))
    return np.nan_to_num(db, nan=0.0)


def load_band_traces(
    path: Path,
    channel_slice: slice = slice(None),
    *,
    baseline_start_ms: float = -500.0,
    baseline_end_ms: float = 0.0,
) -> Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """
    Per-band trial means over selected channels → (mean, sem, sig_mask).

    sig_mask: True where |mean| exceeds ~2 SEM (descriptive marker).
    """
    power = _tfr_as_trials_ch_f_t(np.load(path, mmap_mode="r"))
    arr = np.nanmean(power[:, channel_slice, :, :], axis=1)  # (trials, f, t)

    base_mask = (TFR_TIMES_MS >= baseline_start_ms) & (TFR_TIMES_MS < baseline_end_ms)
    baseline = np.nanmean(arr[:, :, base_mask], axis=2, keepdims=True)
    db = 10.0 * np.log10(np.maximum(arr, 1e-12) / np.maximum(baseline, 1e-12))
    db = np.nan_to_num(db, nan=0.0)

    out: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for name, (fmin, fmax) in BANDS_7.items():
        fmask = (TFR_FREQS_HZ >= fmin) & (TFR_FREQS_HZ <= fmax)
        if not np.any(fmask):
            continue
        band = np.nanmean(db[:, fmask, :], axis=1)  # (trials, t)
        mean = np.nanmean(band, axis=0)
        sem = np.nanstd(band, axis=0) / np.sqrt(max(band.shape[0], 1))
        sig = np.abs(mean) > (2.0 * sem + 1e-12)
        out[name] = (mean, sem, sig)
    return out

def full_sequence_time_mask() -> np.ndarray:
    return (TFR_TIMES_MS >= FULL_SEQUENCE_START_MS) & (TFR_TIMES_MS <= FULL_SEQUENCE_END_MS)


def figure_spectrogram_grid(
    session: str,
    condition: str,
    areas: Sequence[str],
    index: Dict[Tuple[str, str], Tuple[Path, slice]],
) -> "object":
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    n = len(areas)
    cols = 1
    rows = n
    fig = make_subplots(
        rows=rows,
        cols=cols,
        shared_xaxes=True,
        vertical_spacing=0.01,
        subplot_titles=list(areas),
    )
    tmask = full_sequence_time_mask()
    times = TFR_TIMES_MS[tmask]
    omit = condition if omission_window_ms(condition) else None

    for i, area in enumerate(areas):
        r = i + 1
        key = (area, condition)
        if key not in index:
            fig.add_annotation(
                text=f"{area}: no TFR file",
                xref="x domain",
                yref="y domain",
                x=0.5,
                y=0.5,
                showarrow=False,
                row=r,
                col=1,
            )
            continue
        path, ch = index[key]
        db = load_trial_avg_db(path, ch)
        z = db[:, tmask]
        fig.add_trace(
            go.Heatmap(
                x=times,
                y=TFR_FREQS_HZ,
                z=z,
                colorscale="RdBu_r",
                zmid=0.0,
                zmin=-3.0,
                zmax=3.0,
                colorbar=dict(title="dB", len=0.3) if i == 0 else dict(len=0),
                showscale=(i == 0),
                hoverinfo="skip",
            ),
            row=r,
            col=1,
        )
        # y range in data coords for shapes
        apply_sequence_layout(
            fig,
            y0=float(TFR_FREQS_HZ[0]),
            y1=float(TFR_FREQS_HZ[-1]),
            highlight_omission=omit,
            opacity=0.12,
            row=r,
            col=1,
        )
        fig.update_yaxes(type="log", title_text="Hz" if i == n - 1 else "", row=r, col=1)

    fig.update_xaxes(
        title_text="Time from p1 onset (ms)",
        range=[FULL_SEQUENCE_START_MS, FULL_SEQUENCE_END_MS],
        row=n,
        col=1,
    )
    fig.update_layout(
        title=dict(
            text=f"{session} · TFR spectrograms · {condition} · full sequence fx→d4",
            x=0.01,
            xanchor="left",
        ),
        height=max(240, 140 * n),
        width=1100,
        plot_bgcolor=OMISSION_PALETTE[12],
        paper_bgcolor=OMISSION_PALETTE[12],
        margin=dict(l=60, r=40, t=60, b=50),
    )
    return fig


def figure_band_traces_grid(
    session: str,
    condition: str,
    areas: Sequence[str],
    index: Dict[Tuple[str, str], Tuple[Path, slice]],
) -> "object":
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    n = len(areas)
    fig = make_subplots(
        rows=n,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.015,
        subplot_titles=list(areas),
    )
    tmask = full_sequence_time_mask()
    times = TFR_TIMES_MS[tmask]
    omit = condition if omission_window_ms(condition) else None

    for i, area in enumerate(areas):
        r = i + 1
        key = (area, condition)
        if key not in index:
            continue
        path, ch = index[key]
        bands = load_band_traces(path, ch)
        y_min, y_max = -2.5, 2.5
        for bname, (mean, sem, sig) in bands.items():
            m = mean[tmask]
            s = sem[tmask]
            color = BAND_COLORS_7[bname]
            fig.add_trace(
                go.Scatter(
                    x=np.concatenate([times, times[::-1]]),
                    y=np.concatenate([m + 2 * s, (m - 2 * s)[::-1]]),
                    fill="toself",
                    fillcolor=color,
                    opacity=0.15,
                    line=dict(width=0),
                    showlegend=(i == 0),
                    name=f"{bname} ±2SEM" if i == 0 else None,
                    hoverinfo="skip",
                ),
                row=r,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=times,
                    y=m,
                    mode="lines",
                    line=dict(color=color, width=1.5),
                    name=bname if i == 0 else None,
                    showlegend=(i == 0),
                    hoverinfo="skip",
                ),
                row=r,
                col=1,
            )
            # Significance ticks near top of panel
            sig_t = times[sig[tmask]]
            if len(sig_t):
                fig.add_trace(
                    go.Scatter(
                        x=sig_t,
                        y=np.full(len(sig_t), y_max - 0.08),
                        mode="markers",
                        marker=dict(symbol="line-ns", size=6, color=OMISSION_PALETTE[5], line=dict(width=1)),
                        showlegend=False,
                        hoverinfo="skip",
                    ),
                    row=r,
                    col=1,
                )

        apply_sequence_layout(
            fig,
            y0=y_min,
            y1=y_max,
            highlight_omission=omit,
            opacity=0.14,
            row=r,
            col=1,
        )
        fig.update_yaxes(range=[y_min, y_max], title_text="dB" if i == n - 1 else "", row=r, col=1)

    fig.update_xaxes(
        title_text="Time from p1 onset (ms)",
        range=[FULL_SEQUENCE_START_MS, FULL_SEQUENCE_END_MS],
        row=n,
        col=1,
    )
    fig.update_layout(
        title=dict(
            text=(
                f"{session} · TFR band traces (7 bands, ±2SEM, black sig ticks) · "
                f"{condition} · full sequence"
            ),
            x=0.01,
            xanchor="left",
        ),
        height=max(260, 150 * n),
        width=1100,
        plot_bgcolor=OMISSION_PALETTE[12],
        paper_bgcolor=OMISSION_PALETTE[12],
        legend=dict(orientation="h", y=1.02),
        margin=dict(l=60, r=40, t=80, b=50),
    )
    return fig


def main() -> None:
    args = parse_args()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    # Always emit editable layout SVGs first (Plotly objects → SVG)
    layout_dir = out / "layout_templates"
    written = layout_template_svgs(layout_dir, conditions=args.conditions)
    print("layout SVGs:", {k: str(v) for k, v in written.items()})

    if args.layout_only:
        return

    index = index_tfr_files(args.tfr_dir, args.session)
    if not index:
        raise FileNotFoundError(
            f"No TFR files for session={args.session} in {args.tfr_dir}"
        )

    areas = [a for a in args.areas if any((a, c) in index for c in args.conditions)]
    if args.max_areas is not None:
        areas = areas[: args.max_areas]
    if not areas:
        # fall back to whatever areas exist for RRRR
        areas = sorted({a for (a, c) in index if c == "RRRR"})
        if args.max_areas is not None:
            areas = areas[: args.max_areas]
    print(f"session={args.session} areas={areas} n_index={len(index)}")

    for cond in args.conditions:
        spec = figure_spectrogram_grid(args.session, cond, areas, index)
        html_p = out / f"tfr_spectrogram_{cond}.html"
        export_figure_html(spec, html_p)
        print("wrote", html_p)
        if not args.no_svg:
            svg_p = out / f"tfr_spectrogram_{cond}.svg"
            try:
                export_figure_svg(spec, svg_p)
                print("wrote", svg_p)
            except Exception as exc:
                print(f"SVG export failed for spectrogram {cond}: {exc}")

        tr = figure_band_traces_grid(args.session, cond, areas, index)
        html_t = out / f"tfr_traces_{cond}.html"
        export_figure_html(tr, html_t)
        print("wrote", html_t)
        if not args.no_svg:
            svg_t = out / f"tfr_traces_{cond}.svg"
            try:
                export_figure_svg(tr, svg_t)
                print("wrote", svg_t)
            except Exception as exc:
                print(f"SVG export failed for traces {cond}: {exc}")


if __name__ == "__main__":
    main()
