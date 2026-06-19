"""Figure 5: predictable omission SPK, slot-specific (p2/p3/p4).

This module uses the recovered full-sequence SPK epochs (p1-relative) and
re-bases time for slot-local omission windows by subtracting the slot
omission-onset offset (p2=1031ms, p3=2062ms, p4=3093ms).

It intentionally does *not* perform omission-relative re-epoching because
`jnwb.address_events(..., anchor=...)` is currently limited to `anchor="p1"`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import jnwb


AFAMILY_CONDITIONS = ["AAAB", "AXAB", "AAXB", "AAAX"]

SLOT_ONSET_MS: dict[str, int] = {
    "p2": 1031,
    "p3": 2062,
    "p4": 3093,
}

OMISSION_WINDOW_MS = (0, 531)  # missing expected stimulus epoch on slot-local axis


def _gaussian_smooth_1d(trace: np.ndarray, sigma_ms: float, bin_ms: float) -> np.ndarray:
    """Gaussian smoothing along the last axis.

    Note: σ is specified in milliseconds, kernel is converted to bins.
    """
    if sigma_ms <= 0:
        return trace
    sigma_bins = sigma_ms / float(bin_ms)
    # scipy is available in the repo; import locally to keep module import fast.
    from scipy.ndimage import convolve1d

    radius = int(np.ceil(3 * sigma_bins))
    if radius <= 0:
        return trace
    x = np.arange(-radius, radius + 1, dtype=float)
    kernel = np.exp(-0.5 * (x / sigma_bins) ** 2)
    kernel = kernel / kernel.sum()

    # convolve1d supports multi-d arrays if we provide axis. Here we always smooth 1D.
    return convolve1d(trace, kernel, mode="constant", cval=0.0)


def _smooth_counts_to_hz(
    counts: np.ndarray,
    bin_ms: float,
    sigma_ms: float,
) -> np.ndarray:
    """counts -> Hz -> Gaussian smoothing (along time axis)."""
    hz = counts / (bin_ms / 1000.0)
    if sigma_ms <= 0:
        return hz
    if hz.ndim != 3:
        raise ValueError(f"Expected counts shape (trials, units, time), got {hz.shape}")
    # (trials, units, time)
    out = np.empty_like(hz, dtype=np.float32)
    for tr in range(hz.shape[0]):
        for u in range(hz.shape[1]):
            out[tr, u, :] = _gaussian_smooth_1d(hz[tr, u, :], sigma_ms=sigma_ms, bin_ms=bin_ms)
    return out


def _get_slot_conditions(slot: str) -> tuple[str, str]:
    """Return (omission_condition, control_condition)."""
    if slot == "p2":
        return "AXAB", "AAAB"
    if slot == "p3":
        return "AAXB", "AAAB"
    if slot == "p4":
        return "AAAX", "AAAB"
    raise ValueError(f"Unknown slot: {slot}")


@dataclass(frozen=True)
class Fig05Params:
    window_ms: tuple[int, int] = (-1000, 1000)  # omission-relative
    baseline_ms: tuple[int, int] = (-250, -50)  # omission-relative
    sigma_ms: float = 25.0
    classes: tuple[str, ...] = ("S+", "S-", "O/X")
    allow_unknown_area: bool = True


def _slice_rebase_time(
    time_ms_p1: np.ndarray,
    *,
    slot_onset_ms: int,
    window_ms: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray]:
    """Slice time axis around a slot and rebase to omission-relative."""
    start_p1 = slot_onset_ms + window_ms[0]
    end_p1 = slot_onset_ms + window_ms[1]
    mask = (time_ms_p1 >= start_p1) & (time_ms_p1 < end_p1)
    if not np.any(mask):
        raise ValueError(
            f"Empty time slice for slot_onset_ms={slot_onset_ms}, window_ms={window_ms}. "
            f"p1-axis range: {float(time_ms_p1.min())}..{float(time_ms_p1.max())}"
        )
    time_slice_p1 = np.asarray(time_ms_p1[mask], dtype=float)
    time_slice_rel = time_slice_p1 - float(slot_onset_ms)
    return time_slice_rel, mask


def _compute_class_psths(
    *,
    counts: np.ndarray,
    time_ms_p1: np.ndarray,
    trial_meta: pd.DataFrame,
    unit_class_table: pd.DataFrame,
    omission_condition: str,
    control_condition: str,
    slot: str,
    bin_ms: float,
    sigma_ms: float,
    classes: tuple[str, ...],
    window_ms: tuple[int, int],
    baseline_ms: tuple[int, int],
) -> dict[str, dict[str, dict[str, np.ndarray]]]:
    """Compute mean±SEM PSTHs per class for omission vs control."""
    slot_onset_ms = SLOT_ONSET_MS[slot]
    time_rel, mask_t = _slice_rebase_time(
        time_ms_p1, slot_onset_ms=slot_onset_ms, window_ms=window_ms
    )

    # Baseline mask on the *re-based* axis.
    baseline_mask = (time_rel >= baseline_ms[0]) & (time_rel < baseline_ms[1])

    # Prepare smoothing once for each condition slice.
    # counts: (trials, units, time)
    data_t = counts[:, :, mask_t]

    def rates_for_condition(condition: str) -> np.ndarray:
        sel = trial_meta["condition"].astype(str).values == condition
        if not np.any(sel):
            raise ValueError(f"No trials for condition={condition}")
        cond_counts = data_t[sel, :, :]
        return _smooth_counts_to_hz(cond_counts, bin_ms=bin_ms, sigma_ms=sigma_ms)

    rates_om = rates_for_condition(omission_condition)
    rates_ctrl = rates_for_condition(control_condition)

    out: dict[str, dict[str, dict[str, np.ndarray]]] = {}
    for cls in classes:
        unit_mask = unit_class_table["display_class"].astype(str).values == cls
        unit_idx = np.where(unit_mask)[0]
        if unit_idx.size == 0:
            # Keep empty panels out by omission later.
            out[cls] = {
                "omission": {"mean": np.array([]), "sem": np.array([]), "time_rel": time_rel},
                "control": {"mean": np.array([]), "sem": np.array([]), "time_rel": time_rel},
            }
            continue

        def baseline_subtract(rates: np.ndarray) -> np.ndarray:
            # rates: (trials, units, time)
            if not np.any(baseline_mask):
                return rates[:, :, :]
            baseline = rates[:, :, baseline_mask].mean(axis=(0, 2), keepdims=True)
            return rates - baseline

        rates_om_sub = baseline_subtract(rates_om[:, unit_idx, :])
        rates_ctrl_sub = baseline_subtract(rates_ctrl[:, unit_idx, :])

        # Mean across trials -> (units, time), then aggregate units to mean and SEM.
        def mean_sem(rates: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            per_unit = rates.mean(axis=0)  # (units, time)
            mean = per_unit.mean(axis=0)  # (time,)
            n_units = per_unit.shape[0]
            sem = per_unit.std(axis=0, ddof=1) / np.sqrt(n_units) if n_units > 1 else np.zeros_like(mean)
            return mean, sem

        om_mean, om_sem = mean_sem(rates_om_sub)
        ctrl_mean, ctrl_sem = mean_sem(rates_ctrl_sub)

        out[cls] = {
            "omission": {"mean": om_mean, "sem": om_sem, "time_rel": time_rel},
            "control": {"mean": ctrl_mean, "sem": ctrl_sem, "time_rel": time_rel},
        }

    return out


def build_fig05_slotwise_spk_figure(
    *,
    epochs_path: str | Path,
    classification_path: str | Path,
    output_png: str | Path,
    output_svg: str | Path,
    output_html: str | Path,
    params: Fig05Params = Fig05Params(),
) -> dict[str, Any]:
    """Generate Figure 5 (predictable omission SPK) slot-wise."""
    epochs_path = Path(epochs_path)
    classification_path = Path(classification_path)

    cls_table = pd.read_csv(classification_path)
    if "display_class" not in cls_table.columns:
        raise ValueError("classification CSV missing 'display_class'")

    loaded = jnwb.load_epoch_artifact(epochs_path, load_all_sessions=True)
    batches = loaded if isinstance(loaded, list) else [loaded]
    if len(batches) != 1:
        # For this milestone we only support single-session artifacts.
        raise ValueError(f"Expected 1 batch, got {len(batches)}")
    batch = batches[0]

    counts = np.asarray(batch.data, dtype=np.float32)
    time_ms_p1 = np.asarray(batch.time_ms, dtype=float)
    trial_meta = batch.trial_metadata.copy()
    if "condition" not in trial_meta.columns:
        raise ValueError("Epoch artifact trial_metadata missing 'condition'")

    bin_ms = float(batch.manifest.get("bin_ms") or 1.0)

    slot_list = ["p2", "p3", "p4"]
    omission_color = "#8A2BE2"  # purple
    control_color = "#F0E442"  # yellow

    # Layout: rows = classes, cols = slots.
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
        omission_cond, control_cond = _get_slot_conditions(slot)
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

            # SEM ribbons first (omission then control).
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
                    fillcolor="rgba(138,43,226,0.18)",
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

            # Axis markers: omission expected stimulus (0..531 on slot-local axis).
            fig.add_vrect(
                x0=OMISSION_WINDOW_MS[0],
                x1=OMISSION_WINDOW_MS[1],
                fillcolor="rgba(180,180,180,0.25)",
                line_width=0,
                row=row,
                col=col,
            )
            fig.add_vline(x=0, line_dash="dash", line_color="black", line_width=1, row=row, col=col)
            fig.update_yaxes(title_text=f"{cls} ΔFR (Hz)", row=row, col=col)

    fig.update_xaxes(title_text="Time relative to expected omission onset (ms)", row=len(params.classes), col=1)
    fig.update_layout(
        title="Figure 5: Predictable omission SPK (slot-local windows)",
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
    # Static exports require kaleido; reuse repo helper semantics by best-effort.
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
        "params": params,
    }

