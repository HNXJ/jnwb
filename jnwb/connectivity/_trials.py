"""Signals as trials: `as_trials`, trial pairing and detrending, and `bin_spikes`."""

from __future__ import annotations

import logging
import warnings
from typing import Optional, Sequence, Tuple
import numpy as np
from .._spread import zscore
from .._units import resolve_unit_alias
from .._bins import bin_edges, right_open_counts, whole_bin_count

log = logging.getLogger(__package__)


def as_trials(
    X,
    time_axis: int = -1,
    name: str = "X",
    allow_ragged: bool = True,
) -> np.ndarray:
    """
    Normalize any supported signal container to a ``(n_trials, n_times)`` float array.

    Args:
        X: 1-D array, 2-D array, or list/tuple of 1-D arrays (one per trial)
        time_axis: which axis of a 2-D input is time (default last)
        name: label used in error messages
        allow_ragged: if False, unequal trial lengths raise instead of truncating

    Raises:
        ValueError: on 3-D+ input, empty input, or non-finite samples. NaNs are
            never silently dropped — a series containing them is a hard error.
    """
    if isinstance(X, (list, tuple)):
        arrs = [np.asarray(a, dtype=float).ravel() for a in X]
        if not arrs:
            raise ValueError(f"{name}: empty trial list")
        lengths = {a.size for a in arrs}
        if len(lengths) > 1:
            if not allow_ragged:
                raise ValueError(f"{name}: ragged trial lengths {sorted(lengths)}")
            n_min = min(lengths)
            # Both channels. `log.warning` is invisible to `warnings.simplefilter`,
            # `pytest.warns` and `-W error`, so a caller who had asked to be told about
            # silent data loss was not told: the truncation reached the estimator with an
            # empty warning list. The log line stays for operators; the warning is what
            # the caller can actually act on.
            log.warning(
                "%s: ragged trials %s -> truncated to %d samples", name,
                sorted(lengths), n_min,
            )
            warnings.warn(
                f"{name}: ragged trial lengths {sorted(lengths)} truncated to {n_min} "
                f"samples, discarding {sum(lengths) - n_min * len(arrs)} sample(s). Pass "
                "allow_ragged=False to make this an error.",
                RuntimeWarning,
                stacklevel=3,
            )
            arrs = [a[:n_min] for a in arrs]
        arr = np.stack(arrs, axis=0)
    else:
        arr = np.asarray(X, dtype=float)
        if arr.ndim == 1:
            arr = arr[None, :]
        elif arr.ndim == 2:
            if time_axis in (0,):
                arr = arr.T
            elif time_axis not in (-1, 1):
                raise ValueError(f"{name}: time_axis must be 0, 1 or -1; got {time_axis}")
        else:
            raise ValueError(
                f"{name}: expected 1-D or 2-D (n_trials, n_times); got shape {arr.shape}. "
                "Reduce channels first (select or average) — this layer will not "
                "guess which axis is a channel."
            )

    if arr.size == 0:
        raise ValueError(f"{name}: empty signal")
    if not np.all(np.isfinite(arr)):
        n_bad = int(np.sum(~np.isfinite(arr)))
        raise ValueError(
            f"{name}: {n_bad} non-finite sample(s) of {arr.size}. Interpolate or drop "
            "the affected trials explicitly; connectivity will not impute them."
        )
    return arr


def _pair_trials(X, Y, time_axis: int = -1) -> Tuple[np.ndarray, np.ndarray]:
    """Normalize an X/Y pair and assert matching shape."""
    x = as_trials(X, time_axis=time_axis, name="X")
    y = as_trials(Y, time_axis=time_axis, name="Y")
    if x.shape != y.shape:
        raise ValueError(
            f"X and Y must have identical (n_trials, n_times); got {x.shape} vs {y.shape}"
        )
    return x, y


def _detrend_trials(a: np.ndarray, mode: Optional[str]) -> np.ndarray:
    """Per-trial detrending. ``None`` leaves the data untouched."""
    if mode in (None, "none", False):
        return a
    if mode == "demean":
        return a - a.mean(axis=1, keepdims=True)
    if mode == "zscore":
        return zscore(a, axis=1)
    if mode == "linear":
        n = a.shape[1]
        t = np.linspace(-1.0, 1.0, n)
        design = np.column_stack([np.ones(n), t])
        beta = np.linalg.lstsq(design, a.T, rcond=None)[0]
        return a - (design @ beta).T
    raise ValueError(f"Unknown detrend={mode!r}; use None|'demean'|'zscore'|'linear'")


def _count_nonfinite_spikes(spike_times, trial_starts) -> int:
    """Number of non-finite entries in `spike_times`, whatever nesting it arrived in."""
    if trial_starts is None and isinstance(spike_times, (list, tuple)) and (
        len(spike_times) == 0 or np.ndim(spike_times[0]) >= 1
    ):
        trains = [np.asarray(s, dtype=float).ravel() for s in spike_times]
    else:
        trains = [np.asarray(spike_times, dtype=float).ravel()]
    return int(sum(int(np.sum(~np.isfinite(s))) for s in trains))


def bin_spikes(
    spike_times,
    window_s: Optional[Tuple[float, float]] = None,
    bin_size_ms: float = 10.0,
    trial_starts: Optional[Sequence[float]] = None,
    output: str = "count",
    return_centers: bool = False,
    *,
    window: Optional[Tuple[float, float]] = None,
):
    r"""Bridge spike data into the ``(n_trials, n_bins)`` contract used by every estimator.

    Temporal Axis Contract
    ----------------------
    - **Bins**: $K = (t_1 - t_0) / \Delta$ intervals, where
      $t_0, t_1 = \text{window}$ (seconds) and $\Delta = \text{bin\_size\_ms} / 1000$ (seconds).
      $K$ must be a whole number, so every bin is $\Delta$ wide.
      Each bin $k \in \{0, \dots, K-1\}$ covers the right-open interval:
      $$[t_k, t_{k+1}) = [t_0 + k\Delta,\; t_0 + (k+1)\Delta)$$
    - **Boundary Exclusion**: Spikes strictly prior to $t_0$ ($t < t_0$) or at/beyond
      the terminal boundary ($t \ge t_1$) are excluded. This enforces uniform right-open
      semantics $[t_k, t_{k+1})$ across all bins, avoiding the default NumPy histogram
      right-closed boundary artifact on the last bin.
    - **Coordinates / Bin Centers**: When ``return_centers=True``, returns the bin centers
      $c_k = t_0 + (k + 0.5)\Delta$ (seconds, aligned to the trial or window time origin).

    Args:
        spike_times: 1-D array of absolute spike times (seconds) if ``trial_starts``
            is provided; or a list/tuple of per-trial 1-D arrays relative to window.
        window: ``(start, end)`` in seconds. Relative to trial start if
            ``trial_starts`` is given, else absolute.
        bin_size_ms: Bin width in milliseconds ($\Delta \times 1000$).
        trial_starts: Optional trial-aligned event times (seconds) to epoch a single
            continuous spike train into trials.
        output: ``'count'`` (integer spike count per bin) or ``'rate'`` (spikes / sec = Hz).
        return_centers: If True, also return 1-D array of bin center coordinates.

    Returns:
        ``(n_trials, n_bins)`` float array, or ``(array, centers)`` if ``return_centers=True``.

    Raises:
        ValueError: If the span of ``window_s`` is not a whole multiple of ``bin_size_ms``;
            the message names the nearest valid windows.
    """
    # `window` named no unit while its neighbour `bin_size_ms` did, in the same call.
    # Both are times, one in seconds and one in milliseconds, and only one said so.
    window_s = resolve_unit_alias(
        window_s, window, canonical_name="window_s", alias_name="window",
        func_name="bin_spikes",
    )
    if output not in ("count", "rate"):
        raise ValueError(f"output must be 'count' or 'rate'; got {output!r}")
    t0, t1 = float(window_s[0]), float(window_s[1])
    if not t1 > t0:
        raise ValueError(f"window_s must satisfy end > start; got {window_s}")
    bin_sec = float(bin_size_ms) / 1000.0
    n_bins = whole_bin_count((t0, t1), bin_sec, "bin_spikes", "window_s", unit="s")
    if n_bins < 2:
        raise ValueError(
            f"window_s {window_s} at bin_size_ms={bin_size_ms} yields {n_bins} bins; need >= 2"
        )
    edges = bin_edges(t0, bin_sec, n_bins)

    n_nonfinite = _count_nonfinite_spikes(spike_times, trial_starts)
    if n_nonfinite:
        # These were dropped by the `(s >= t0) & (s < t1)` comparison, which is False for
        # NaN, so a train of NaN spike times produced a confident all-zero rate with no
        # indication that anything had been discarded.
        warnings.warn(
            f"bin_spikes: {n_nonfinite} non-finite spike time(s) dropped. They cannot be "
            "assigned to a bin; the returned counts are over the finite spikes only.",
            RuntimeWarning,
            stacklevel=2,
        )

    if trial_starts is not None:
        st = np.asarray(spike_times, dtype=float).ravel()
        trains = (st - float(start) for start in np.asarray(trial_starts, dtype=float).ravel())
    elif isinstance(spike_times, (list, tuple)) and (
        len(spike_times) == 0 or np.ndim(spike_times[0]) >= 1
    ):
        trains = [np.asarray(s, dtype=float).ravel() for s in spike_times]
    else:
        trains = [np.asarray(spike_times, dtype=float).ravel()]

    counts = right_open_counts(trains, t0, t1, bin_sec, n_bins)
    if counts.size == 0:
        raise ValueError("bin_spikes produced no trials")
    out = counts / bin_sec if output == "rate" else counts
    if return_centers:
        return out, edges[:-1] + bin_sec / 2.0
    return out
