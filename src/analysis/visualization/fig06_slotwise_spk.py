"""Figure 6: random-control omission SPK, slot-specific (p2/p3/p4).

Uses the same full-sequence p1-relative SPK epochs and rebases slot-local
time windows by subtracting the slot omission-onset offset.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import numpy as np

import jnwb

from src.analysis.visualization.fig05_slotwise_spk import (
    AFAMILY_CONDITIONS,
    Fig05Params,
    _compute_class_psths,
    _get_slot_conditions,
    _slice_rebase_time,
    SLOT_ONSET_MS,
    _slice_rebase_time,
    Fig05Params,
)


RAMILY_SLOTS: dict[str, tuple[str, str]] = {
    # omission_cond, control_cond
    "p2": ("RXRR", "RRRR"),
    "p3": ("RRXR", "RRRR"),
    "p4": ("RRRX", "RRRR"),
}


def build_fig06_slotwise_spk_figure(
    *,
    epochs_path: str | Path,
    classification_path: str | Path,
    output_png: str | Path,
    output_svg: str | Path,
    output_html: str | Path,
    params: Fig05Params = Fig05Params(),
) -> dict[str, Any]:
    """Generate Figure 6 (random-control omission SPK) slot-wise."""
    epochs_path = Path(epochs_path)
    classification_path = Path(classification_path)

    cls_table = pd.read_csv(classification_path)
    if "display_class" not in cls_table.columns:
        raise ValueError("classification CSV missing 'display_class'")

    loaded = jnwb.load_epoch_artifact(epochs_path, load_all_sessions=True)
    batches = loaded if isinstance(loaded, list) else [loaded]
    if len(batches) != 1:
        raise ValueError(f"Expected 1 batch, got {len(batches)}")
    batch = batches[0]

    counts = np.asarray(batch.data, dtype=np.float32)
    time_ms_p1 = np.asarray(batch.time_ms, dtype=float)
    trial_meta = batch.trial_metadata.copy()
    if "condition" not in trial_meta.columns:
        raise ValueError("Epoch artifact trial_metadata missing 'condition'")

    bin_ms = float(batch.manifest.get("bin_ms") or 1.0)

    slot_list = ["p2", "p3", "p4"]

    omission_color = "#1F77B4"  # blue
    control_color = "#F0E442"  # yellow

    fig = make_subplots(
        rows=len(params.classes),
        cols=len(slot_list),
        shared_xaxes="all",
        shared_yaxes=False,
        subplot_titles=[f"{slot.upper()} omission" for slot in slot_list],
        vertical_spacing=0.10,
        horizontal_spacing=0.06,
    )

    for col, slot in enumerate(slot_list, start=1):
        omission_cond, control_cond = RAMILY_SLOTS[slot]
        psths = _compute_class_psths(
            counts=counts,
            time_ms_p1=time_ms_p1,
            trial_meta=trial_meta,
            unit_class_table=cls_table,
            omission_condition=omission_cond,
            control_condition=control_cond,
            slot=slot,
            bin_ms=bin_ms,
            sigma_ms=params.sigma_ms,
            classes=params.classes,
            window_ms=params.window_ms,
            baseline_ms=params.baseline_ms,
        )
        for row, cls in enumerate(params.classes, start=1):
            cur = psths[cls]
            time_rel = cur["omission"]["time_rel"]
            om_mean = cur["omission"]["mean"]
            om_sem = cur["omission"]["sem"]
            ctrl_mean = cur["control"]["mean"]
            ctrl_sem = cur["control"]["sem"]
            if om_mean.size == 0:
                continue

            # SEM ribbons
            fig.add_trace(
                go.Scatter(
                    x=time_rel,
                    y=om_mean + om_sem,
                    mode="lines",
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip",
                ),
                row=row,
                col=col,
            )
            fig.add_trace(
                go.Scatter(
                    x=time_rel,
                    y=om_mean - om_sem,
                    fill="tonexty",
                    mode="lines",
                    line=dict(width=0),
                    fillcolor="rgba(31,119,180,0.18)",
                    showlegend=False,
                    hoverinfo="skip",
                ),
                row=row,
                col=col,
            )
            fig.add_trace(
                go.Scatter(
                    x=time_rel,
                    y=om_mean,
                    mode="lines",
                    line=dict(color=omission_color, width=2),
                    name="Omission",
                    showlegend=(row == 1),
                    legendgroup="omission",
                ),
                row=row,
                col=col,
            )

            fig.add_trace(
                go.Scatter(
                    x=time_rel,
                    y=ctrl_mean + ctrl_sem,
                    mode="lines",
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip",
                ),
                row=row,
                col=col,
            )
            fig.add_trace(
                go.Scatter(
                    x=time_rel,
                    y=ctrl_mean - ctrl_sem,
                    fill="tonexty",
                    mode="lines",
                    line=dict(width=0),
                    fillcolor="rgba(240,228,66,0.18)",
                    showlegend=False,
                    hoverinfo="skip",
                ),
                row=row,
                col=col,
            )
            fig.add_trace(
                go.Scatter(
                    x=time_rel,
                    y=ctrl_mean,
                    mode="lines",
                    line=dict(color=control_color, width=2),
                    name="Control",
                    showlegend=(row == 1),
                    legendgroup="control",
                ),
                row=row,
                col=col,
            )

            # Slot-local markers at omission onset.
            fig.add_vline(x=0, line_dash="dash", line_color="black", line_width=1, row=row, col=col)
            fig.update_yaxes(title_text=f"{cls} ΔFR (Hz)", row=row, col=col)

    fig.update_xaxes(
        title_text="Time relative to expected omission onset (ms)",
        row=len(params.classes),
        col=1,
    )
    fig.update_layout(
        title="Figure 6: Random-control omission SPK (slot-local windows)",
        template="plotly_white",
        height=350 * len(params.classes),
        width=340 * len(slot_list),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.5, xanchor="center"),
        margin=dict(l=60, r=20, t=80, b=60),
    )

    out_png = Path(output_png)
    out_svg = Path(output_svg)
    out_html = Path(output_html)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_html.parent.mkdir(parents=True, exist_ok=True)

    fig.write_html(str(out_html), include_plotlyjs="cdn")
    # Best-effort static export.
    try:
        fig.write_image(str(out_png), format="png", scale=2)
        png_ok = True
    except Exception:
        png_ok = False
    try:
        fig.write_image(str(out_svg), format="svg", scale=2)
        svg_ok = True
    except Exception:
        svg_ok = False

    return {
        "output_png": str(out_png),
        "output_svg": str(out_svg),
        "output_html": str(out_html),
        "png_written": png_ok,
        "svg_written": svg_ok,
    }

