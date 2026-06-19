"""Figure 7: Omission-local LFP TFR (slot-wise, predictable omissions).

Design constraints implemented:
- One omission-aligned LFP epoch (DataLoader align_to="omission")
- Multitaper TFR with band-dependent effective time support (lfp_tfr updates)
- Signed dB relative to a declared pre-omission baseline window
- Theta treated as low-frequency (repo BANDS starts at 4 Hz, no delta band yet)

This module computes *summary* TFR heatmaps by averaging LFP across trials/channels
to keep runtime bounded.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.analysis.lfp.lfp_pipeline import get_lfp_signal
from src.analysis.lfp.lfp_preproc import preprocess_lfp, baseline_normalize
from src.analysis.lfp.lfp_tfr import compute_multitaper_tfr
from src.analysis.lfp.lfp_constants import CANONICAL_AREAS, BANDS, FS_LFP
from src.analysis.visualization.lfp_plotting import create_tfr_figure


SLOT_TO_COND: dict[str, str] = {
    "p2": "AXAB",
    "p3": "AAXB",
    "p4": "AAAX",
}


@dataclass(frozen=True)
class Fig07Params:
    # Omission-aligned LFP extraction window parameters (ms)
    # Use the exact display geometry to avoid out-of-bounds in sessions
    # with shorter record lengths for p4 (AAAX) omissions.
    pre_ms: int = 1031
    post_ms: int = 1031
    # Desired display window around omission (ms, omission-relative)
    display_window_ms: tuple[int, int] = (-1031, 1031)
    # Baseline used for signed dB
    baseline_window_ms: tuple[int, int] = (-250, -50)

    # Multitaper defaults are from lfp_tfr (freqs 4..80 step 2)


def _slice_time_rebased(
    times_local_ms: np.ndarray,
    power_dB: np.ndarray,
    *,
    display_window_ms: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray]:
    """Slice time axis and power array to display_window_ms.

    power_dB expected shape: (n_freqs, n_times)
    """
    t0, t1 = display_window_ms
    mask = (times_local_ms >= t0) & (times_local_ms <= t1)
    if not np.any(mask):
        raise ValueError(
            f"No time points in display_window_ms={display_window_ms}. "
            f"times_local range={float(times_local_ms.min())}..{float(times_local_ms.max())}"
        )
    return times_local_ms[mask], power_dB[..., mask]


def compute_slotwise_tfr_summary(
    *,
    area: str,
    condition: str,
    params: Fig07Params,
    band_dependent: bool = True,
) -> dict[str, Any] | None:
    """Compute signed-dB summary TFR heatmap for one (area, condition)."""
    # Use canonical pipeline loader to concatenate session entries.
    try:
        lfp = get_lfp_signal(
            area=area,
            condition=condition,
            align_to="omission",
            pre_ms=params.pre_ms,
            post_ms=params.post_ms,
            allow_channel_trim=True,
        )
    except Exception as exc:
        # If coverage is insufficient for a subset of sessions, the pipeline may
        # yield empty/None or raise; we treat that cell as uncomputable.
        print(f"[fig07] Skipping cell area={area}, condition={condition}: {exc}")
        return None

    if lfp is None or (isinstance(lfp, np.ndarray) and lfp.size == 0):
        return None

    lfp_clean = preprocess_lfp(lfp, fs=FS_LFP)

    # Summary TFR: average across trials/channels first for bounded compute.
    avg_lfp = np.mean(lfp_clean, axis=(0, 1), keepdims=True)  # (1,1,time)
    freqs, times_ms, power = compute_multitaper_tfr(
        avg_lfp,
        fs=FS_LFP,
        use_band_dependent_n_cycles=band_dependent,
    )

    # power: (n_trials=1, n_channels=1, n_freqs, n_times)
    power_lin = power[0, 0]  # (n_freqs, n_times)

    # Rebase time axis so omission onset is at 0 ms.
    times_local_ms = times_ms - float(params.pre_ms)

    # Signed dB relative to a declared pre-omission baseline.
    power_db = baseline_normalize(
        power=power_lin,
        times=times_local_ms,
        baseline_window=params.baseline_window_ms,
    )  # same shape as power_lin

    # Slice to display window.
    times_disp, power_disp = _slice_time_rebased(
        times_local_ms, power_db, display_window_ms=params.display_window_ms
    )

    return {
        "area": area,
        "condition": condition,
        "freqs": freqs,
        "times_ms": times_disp,
        "power_db": power_disp,  # (n_freqs, n_times_disp)
    }


def build_fig07_slotwise_local_tfr(
    *,
    output_html: str | Path,
    output_png: str | Path | None = None,
    output_svg: str | Path | None = None,
    params: Fig07Params = Fig07Params(),
    areas: list[str] | None = None,
) -> dict[str, Any]:
    """Build a publication-style multi-area TFR panel for p2/p3/p4 predictable omissions."""
    if areas is None:
        areas = CANONICAL_AREAS

    # Create figures per slot+area using create_tfr_figure, then combine.
    # To keep runtime bounded, we compute per area per slot.
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go

    slots = ["p2", "p3", "p4"]
    conds = [SLOT_TO_COND[s] for s in slots]

    # Layout: rows=areas, cols=slots
    fig = make_subplots(
        rows=len(areas),
        cols=len(slots),
        shared_xaxes=False,
        shared_yaxes=False,
        subplot_titles=[f"{s.upper()} ({c})" for s, c in zip(slots, conds)],
        vertical_spacing=0.08,
        horizontal_spacing=0.04,
    )

    cache: dict[tuple[str, str], dict[str, Any]] = {}
    for r, area in enumerate(areas, start=1):
        for c, slot in enumerate(slots, start=1):
            condition = SLOT_TO_COND[slot]
            key = (area, condition)
            res = compute_slotwise_tfr_summary(area=area, condition=condition, params=params)
            cache[key] = res
            if res is None:
                fig.add_annotation(
                    text="insufficient<br>coverage",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=12, color="gray"),
                    row=r,
                    col=c,
                )
                continue

            # Heatmap trace directly (avoid OmissionPlotter object overhead).
            heatmap = go.Heatmap(
                z=res["power_db"],
                x=res["times_ms"],
                y=res["freqs"],
                colorscale="Viridis",
                zmin=-3,
                zmax=3,
                colorbar=dict(title="dB") if (r == 1 and c == len(slots)) else None,
                showscale=(r == 1 and c == len(slots)),
            )
            fig.add_trace(heatmap, row=r, col=c)
            fig.add_vline(x=0, line_color="white", line_dash="dash", row=r, col=c)

            # Axis labels minimally
            fig.update_yaxes(title_text=area if c == 1 else "", row=r, col=c)
            if r == len(areas):
                fig.update_xaxes(title_text="Time relative to omission onset (ms)", row=r, col=c)

    # Global styling
    fig.update_layout(
        title="Figure 7: Omission-local LFP TFR (predictable omissions, signed dB)",
        template="plotly_white",
        height=280 * len(areas),
        width=320 * len(slots),
        margin=dict(l=60, r=20, t=80, b=60),
    )

    out_html = Path(output_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out_html), include_plotlyjs="cdn")

    png_ok = None
    svg_ok = None
    if output_png is not None:
        out_png = Path(output_png)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        try:
            fig.write_image(str(out_png), format="png", scale=2)
            png_ok = True
        except Exception:
            png_ok = False
    if output_svg is not None:
        out_svg = Path(output_svg)
        out_svg.parent.mkdir(parents=True, exist_ok=True)
        try:
            fig.write_image(str(out_svg), format="svg", scale=2)
            svg_ok = True
        except Exception:
            svg_ok = False

    return {
        "output_html": str(out_html),
        "output_png": str(output_png) if output_png is not None else None,
        "output_svg": str(output_svg) if output_svg is not None else None,
        "png_written": png_ok,
        "svg_written": svg_ok,
        "params": params.__dict__,
        "areas": areas,
        "slots": slots,
    }

