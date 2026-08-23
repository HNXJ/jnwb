"""
jnwb.viz -- generic plotting utilities: vector-graphics setup, tight auto-scaled axes,
multi-page/multi-format figure export, trial-onset resampling, and array-in PSTH computation.

PROMOTED 2026-08-23 from omission.jnwb_ext.viz (99%-jnwb-sufficiency normalization):
setup_vector_graphics, apply_tight_auto_axis, save_figure_suite, resample_onsets, and
raster_psth take plain matplotlib objects / numpy arrays with no session object, condition
code, or omission-task coupling. The rest of omission.jnwb_ext.viz (raster_grid_by_family,
raster_suite_omission, lfp_tfr_trace_suite_omission, CONDITION_FAMILIES, sequence-epoch
overlays, ...) stays there: it is built on OmissionSession and this task's condition/phase
semantics.

Author: Consolidated from archived figure scripts
Date: 2026-06-25
"""

import logging
from pathlib import Path
from typing import List, Tuple, Union

import numpy as np
import matplotlib.pyplot as plt

log = logging.getLogger(__name__)


def setup_vector_graphics():
    """Enforce editable vector SVG font rendering in Adobe Illustrator / Inkscape."""
    plt.rcParams['svg.fonttype'] = 'none'
    plt.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
    plt.rcParams['font.family'] = 'sans-serif'


def apply_tight_auto_axis(ax, x_span: Tuple[float, float] = (-500, 4124), y_margin: float = 0.12):
    """Apply tight temporal bounds and auto-scale y-axis without empty margins."""
    ax.set_xlim(x_span)
    lines = ax.get_lines()
    if lines:
        all_y = []
        for line in lines:
            ydata = line.get_ydata()
            if len(ydata) > 0 and not np.all(np.isnan(ydata)):
                all_y.extend(ydata[~np.isnan(ydata)])
        if all_y:
            ymin, ymax = np.min(all_y), np.max(all_y)
            rng = max(ymax - ymin, 1e-3)
            ax.set_ylim(max(0, ymin - y_margin * rng), ymax + y_margin * rng)


def save_figure_suite(
    figures: List[plt.Figure],
    output_dir: Union[str, Path],
    basename: str,
    dpi: int = 300,
    formats: List[str] = ['png', 'pdf']
) -> None:
    """
    Save a suite of figures to disk with consistent naming.

    Args:
        figures: List of matplotlib figures
        output_dir: Output directory
        basename: Base filename (will add page numbers and format)
        dpi: Resolution for raster formats
        formats: List of formats to save ('png', 'pdf', 'svg')

    Example:
        >>> figs = [plt.figure(), plt.figure()]
        >>> save_figure_suite(figs, 'outputs/figures', 'raster_family_a')
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for fig_idx, fig in enumerate(figures):
        for fmt in formats:
            filename = f"{basename}_page{fig_idx+1}.{fmt}"
            filepath = output_dir / filename

            if fmt == 'pdf':
                fig.savefig(filepath, format='pdf', bbox_inches='tight')
            else:
                fig.savefig(filepath, format=fmt, dpi=dpi, bbox_inches='tight')

            log.info(f"Saved: {filepath}")


def resample_onsets(onsets: np.ndarray, target_n: int = 100, random_state: int = 42) -> np.ndarray:
    """Resample a trial-onset array to exactly ``target_n`` onsets (with replacement if there
    are fewer than ``target_n`` available), for a consistent raster trial count across units
    with different trial counts.
    """
    if len(onsets) == 0:
        return np.array([])
    rng = np.random.default_rng(random_state)
    if len(onsets) >= target_n:
        idx = rng.choice(len(onsets), size=target_n, replace=False)
    else:
        idx = rng.choice(len(onsets), size=target_n, replace=True)
    return onsets[idx]


def raster_psth(st, onsets, win_ms, bin_ms: float = 10.0):
    """Trial-averaged PSTH (mean + SEM firing rate per bin) for a raw spike-time array against
    an explicit onset array -- raw arrays in, no session/unit_id lookup. Distinct from
    :func:`jnwb.spiking.compute_response_metrics`'s single-response-window-scalar contract:
    this returns the full time-binned PSTH curve.

    Args:
        st: 1D array of spike times (seconds).
        onsets: 1D array of trial onset times (seconds).
        win_ms: (start_ms, end_ms) window relative to each onset.
        bin_ms: bin width in ms.

    Returns:
        (bin_centers_ms, mean_rate_hz, sem_rate_hz)
    """
    edges = np.arange(win_ms[0], win_ms[1] + bin_ms, bin_ms)
    centers = edges[:-1] + bin_ms / 2.0
    if onsets.size == 0:
        return centers, np.zeros_like(centers), np.zeros_like(centers)
    counts = np.zeros((onsets.size, edges.size - 1))
    for i, t0 in enumerate(onsets):
        s = (st[(st >= t0 + win_ms[0] / 1000.0) & (st < t0 + win_ms[1] / 1000.0)] - t0) * 1000.0
        counts[i], _ = np.histogram(s, bins=edges)
    rate = counts / (bin_ms / 1000.0)
    mean = rate.mean(axis=0)
    sem = rate.std(axis=0, ddof=1) / np.sqrt(rate.shape[0]) if rate.shape[0] > 1 else np.zeros_like(mean)
    return centers, mean, sem
