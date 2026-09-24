"""
jnwb.viz -- plotting utilities: vector-graphics setup, tight auto-scaled axes, multi-format
figure export, trial-onset resampling, and array-in PSTH computation.

All exported helpers take plain matplotlib objects or numpy arrays. Session-specific figure
suites belong in downstream project code.
"""

import logging
from pathlib import Path
from typing import Any, List, Tuple, Union

import numpy as np
import matplotlib.pyplot as plt

from ._rng import Default, RNGLike, resolve_rng, resolve_seed_alias

log = logging.getLogger(__name__)


def _whole_bin_count(win_ms, bin_ms, func_name: str, param: str = "win_ms") -> int:
    """Number of ``bin_ms`` bins spanning ``win_ms``, refusing a span that is not whole bins.

    A partial last bin holds less than ``bin_ms`` of data but its rate is still divided by
    the full ``bin_ms``; a window stretched or shrunk to whole bins divides every bin by a
    width it does not have. The error names the nearest valid windows with the same start.
    """
    start, end = float(win_ms[0]), float(win_ms[1])
    n = (end - start) / float(bin_ms)
    n_whole = int(round(n))
    if abs(n - n_whole) > 1e-9 or n_whole < 1:
        nearest = [(start, start + k * bin_ms) for k in (int(np.floor(n)), int(np.ceil(n))) if k >= 1]
        raise ValueError(
            f"{func_name}: {param}={(start, end)} spans {end - start:g} ms, which is {n:g} "
            f"bins of {bin_ms:g} ms, so not every bin would be {bin_ms:g} ms wide and the "
            "rates would be wrong. Use "
            + " or ".join(f"{param}=({a:g}, {b:g})" for a, b in nearest)
            + ", or a bin width that divides the span."
        )
    return n_whole


def setup_vector_graphics():
    """Enforce editable vector SVG font rendering in Adobe Illustrator / Inkscape."""
    plt.rcParams['svg.fonttype'] = 'none'
    plt.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
    plt.rcParams['font.family'] = 'sans-serif'


def apply_tight_auto_axis(ax, x_span: Tuple[float, float] = (-500, 4124), y_margin: float = 0.12):
    """Pin the x-axis to ``x_span`` and fit the y-axis to the plotted lines.

    The y lower limit is floored at 0, so negative values in the lines are drawn outside the
    axes and not shown. Do not use it on signed data such as z-scores or LFP.
    """
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


def resample_onsets(
    onsets: np.ndarray,
    target_n: int = 100,
    rng: RNGLike = Default(42),
    *,
    random_state: Any = Default(42),
) -> np.ndarray:
    """Resample a trial-onset array to exactly ``target_n`` onsets (with replacement if there
    are fewer than ``target_n`` available), for a consistent raster trial count across units
    with different trial counts.

    ``random_state`` is the old spelling of ``rng`` and still works; passing both
    different values raises.
    """
    if len(onsets) == 0:
        return np.array([])
    gen = resolve_rng(
        resolve_seed_alias(rng, random_state, alias_name="random_state",
                           func_name="resample_onsets"),
        func_name="resample_onsets",
    )
    if len(onsets) >= target_n:
        idx = gen.choice(len(onsets), size=target_n, replace=False)
    else:
        idx = gen.choice(len(onsets), size=target_n, replace=True)
    return onsets[idx]


def raster_psth(st, onsets, win_ms, bin_ms: float = 10.0):
    """Trial-averaged PSTH (mean + SEM firing rate per bin) for a raw spike-time array against
    an explicit onset array -- raw arrays in, no session/unit_id lookup. Distinct from
    :func:`jnwb.spiking.compute_response_metrics`'s single-response-window-scalar contract:
    this returns the full time-binned PSTH curve.

    Also distinct from :meth:`jnwb.analyzers.UnitAnalyzer.psth`, which is not a redundant
    duplicate but a different contract: SEM here uses ``ddof=1`` ("real" SEM) vs.
    ``UnitAnalyzer.psth``'s bootstrap CI, bins are ms/right-open (``<``) here vs.
    seconds/inclusive (``<=``) there, and the return shape is a plain tuple here vs. a dict
    there. Prefer this function for a quick trial-averaged rate curve with a plain-tuple
    return; prefer ``UnitAnalyzer.psth`` when you want a bootstrap CI or the analyzer's dict
    contract (e.g. alongside ``UnitAnalyzer.raster``). Both are retained deliberately.

    Args:
        st: 1D array of spike times (seconds).
        onsets: 1D array of trial onset times (seconds).
        win_ms: (start_ms, end_ms) window relative to each onset. Its span must be a whole
            number of ``bin_ms`` bins.
        bin_ms: bin width in ms.

    Returns:
        (bin_centers_ms, mean_rate_hz, sem_rate_hz). With no onsets the mean and SEM are NaN.

    Raises:
        ValueError: If ``win_ms`` is not finite with end > start, ``bin_ms`` is not positive,
            or the span of ``win_ms`` is not a whole multiple of ``bin_ms``; the message names
            the nearest valid windows.
    """
    if not (np.all(np.isfinite(win_ms)) and win_ms[1] > win_ms[0]):
        raise ValueError(f"raster_psth: win_ms={tuple(win_ms)} must be finite with end > start")
    if not (np.isfinite(bin_ms) and bin_ms > 0):
        raise ValueError(f"raster_psth: bin_ms must be positive and finite, got {bin_ms}")
    n_bins = _whole_bin_count(win_ms, bin_ms, "raster_psth")
    onsets = np.asarray(onsets, dtype=float)
    edges = win_ms[0] + bin_ms * np.arange(n_bins + 1)
    centers = edges[:-1] + bin_ms / 2.0
    if onsets.size == 0:
        # No trials, so no trial average. This returned zeros, which reads as a silent unit.
        return centers, np.full_like(centers, np.nan), np.full_like(centers, np.nan)
    counts = np.zeros((onsets.size, edges.size - 1))
    for i, t0 in enumerate(onsets):
        s = (st[(st >= t0 + win_ms[0] / 1000.0) & (st < t0 + win_ms[1] / 1000.0)] - t0) * 1000.0
        counts[i], _ = np.histogram(s, bins=edges)
    rate = counts / (bin_ms / 1000.0)
    mean = rate.mean(axis=0)
    # NaN, not zeros. One trial has no dispersion to measure, and a returned 0.0 reads as
    # a measured absence of variability -- error bars of exactly zero on a single trial.
    # `UnitAnalyzer.psth` already returns NaN for this case.
    sem = (
        rate.std(axis=0, ddof=1) / np.sqrt(rate.shape[0])
        if rate.shape[0] > 1
        else np.full_like(mean, np.nan)
    )
    return centers, mean, sem
