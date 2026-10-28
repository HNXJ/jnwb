"""Continuous time-series operations and alignment primitives for jnwb."""

from __future__ import annotations

from dataclasses import dataclass
import warnings
from typing import Literal, Sequence

import numpy as np
from scipy import signal


BoundaryPolicy = Literal["nan", "error", "drop"]
OnsetUnit = Literal["seconds", "samples"]


def _containment_sample(t_s: float, fs: float) -> int:
    """Index of the first sample at or after `t_s` seconds, allowing for rounding in the product.

    The tolerance is relative, so a product a few ulps above an integer gives that integer:
    0.07 * 100 is 7.000000000000001, and the window (0, 0.07) s at 100 Hz holds 7 samples.
    """
    x = t_s * fs
    eps = 1e-9 * max(1.0, abs(x))
    return int(np.ceil(x - eps))


def epoch_continuous(
    data: np.ndarray,
    onsets: np.ndarray | Sequence[float],
    *,
    win_s: tuple[float, float],
    fs: float,
    start_s: float = 0.0,
    onset_unit: OnsetUnit = "seconds",
    boundary_policy: BoundaryPolicy = "nan",
    return_indices: bool = False,
) -> tuple[np.ndarray, np.ndarray] | tuple[np.ndarray, np.ndarray, np.ndarray]:
    r"""Extract fixed-duration epochs from a continuous signal aligned to event onsets.

    Time-to-Sample Mapping
    ----------------------
    The window edges are containment bounds: the window holds exactly the samples whose
    times fall in the right-open interval :math:`[t_{\mathrm{pre}}, t_{\mathrm{post}})`.
    Each edge is the first sample at or after its time:

    .. math::
        n_{\mathrm{pre}} = \lceil t_{\mathrm{pre}} \cdot f_s \rceil \\
        n_{\mathrm{post}} = \lceil t_{\mathrm{post}} \cdot f_s \rceil

    A product within a relative tolerance of 1e-9 of an integer counts as that integer. At
    10 Hz the window ``(-0.25, 0.25)`` s gives :math:`n_{\mathrm{pre}} = -2` and
    :math:`n_{\mathrm{post}} = 3`, five samples. The onset sample index is computed from
    continuous timestamps, with :math:`t_{\mathrm{start}}` the time of sample 0 (``start_s``),
    using IEEE 754 round-half-to-even (banker's rounding):

    .. math::
        n_{\mathrm{center}} = \operatorname{round}((t_{\mathrm{onset}} - t_{\mathrm{start}}) \cdot f_s)

    The extraction window for each event spans the half-open sample interval:

    .. math::
        [n_{\mathrm{center}} + n_{\mathrm{pre}}, \, n_{\mathrm{center}} + n_{\mathrm{post}})

    containing :math:`n_{\mathrm{win}} = n_{\mathrm{post}} - n_{\mathrm{pre}}` samples.
    The returned ``time_axis_s`` is defined as:

    .. math::
        t_k = \frac{n_{\mathrm{pre}} + k}{f_s}, \quad k \in \{0, 1, \dots, n_{\mathrm{win}} - 1\}

    Parameters
    ----------
    data:
        1D array of shape ``(n_samples,)`` or 2D array of shape ``(n_samples, n_channels)``.
    onsets:
        1D array or sequence of event onset timestamps.
    win_s:
        Tuple ``(t_pre_s, t_post_s)`` specifying the window relative to each onset
        in seconds. ``t_pre_s`` must be strictly less than ``t_post_s``. Negative
        windows (e.g. ``(-0.5, -0.1)``) and asymmetric windows are fully supported.
    fs:
        Continuous signal sampling rate in Hz (must be positive).
    start_s:
        Time in seconds of sample 0 of ``data`` on the onset clock, the series' ``starting_time``
        in NWB. ``0.0`` (default) keeps sample 0 at t = 0. It applies to onsets in seconds;
        onsets in samples already index ``data``, and a non-zero ``start_s`` with them raises
        ``ValueError``, as does a non-finite value.
    onset_unit:
        Unit of ``onsets``. ``"seconds"`` (default) converts onsets to samples using
        ``fs``; ``"samples"`` treats onsets as integer sample indices.

        A non-finite onset raises :class:`~jnwb.nwb_events.InvalidOnsetValueError`,
        the same refusal ``events`` and ``event_onsets`` give. Under
        ``boundary_policy="nan"``, a warning is issued when most epochs fall entirely
        outside ``[0, n_samples)`` and are therefore all-NaN: that is what onsets on a
        different clock look like -- milliseconds read as seconds, most often -- and it
        is otherwise indistinguishable from a correctly shaped result. Individual
        epochs overhanging either edge are ordinary and do not warn.
    boundary_policy:
        Policy for epoch windows extending beyond continuous signal boundaries
        ``[0, n_samples)``:
        - ``"nan"`` (default): pads out-of-bounds segments with ``np.nan``.
        - ``"error"``: raises :class:`ValueError` if any window extends beyond boundaries.
        - ``"drop"``: drops out-of-bounds events from the output array.
    return_indices:
        If ``True``, also returns an integer array of the 0-based indices of the
        events retained from ``onsets``. When ``boundary_policy="drop"``, this
        preserves exact identity correspondence to input events and metadata.

    Returns
    -------
    epochs:
        Array of extracted epochs. Shape is ``(n_events, n_window_samples)`` for
        1D input, or ``(n_events, n_window_samples, n_channels)`` for 2D input.
        If ``boundary_policy="drop"``, ``n_events`` may be less than ``len(onsets)``.
    time_axis_s:
        1D array of time offsets relative to onset in seconds, shape ``(n_window_samples,)``.
    retained_indices:
        1D array of int64 indices of retained events in ``onsets``, shape ``(n_events,)``.
        Only returned if ``return_indices=True``.

    Raises
    ------
    ValueError
        If ``start_s`` is not finite, or is non-zero with ``onset_unit="samples"``.
    """
    arr = np.asarray(data)
    if arr.ndim not in (1, 2):
        raise ValueError(f"Continuous data must be 1D or 2D, got shape {arr.shape}")
    if fs <= 0.0:
        raise ValueError(f"Sampling rate fs must be positive, got {fs}")
    start_s = float(start_s)
    if not np.isfinite(start_s):
        raise ValueError(f"start_s must be finite, got {start_s}")
    if len(win_s) != 2:
        raise ValueError(f"win_s must be a 2-tuple (t_pre_s, t_post_s), got {win_s}")
    t_pre, t_post = float(win_s[0]), float(win_s[1])
    if t_pre >= t_post:
        raise ValueError(f"win_s[0] must be strictly less than win_s[1], got {win_s}")

    n_pre = _containment_sample(t_pre, fs)
    n_post = _containment_sample(t_post, fs)
    n_win = n_post - n_pre
    if n_win <= 0:
        raise ValueError(f"Window duration produced non-positive sample count: {n_win}")

    time_axis_s = np.arange(n_pre, n_post, dtype=np.float64) / fs
    n_samples = arr.shape[0]

    # Checked before the empty-onsets return: a bad unit or policy is refused with no onsets too.
    if onset_unit not in ("seconds", "samples"):
        raise ValueError(f"Unknown onset_unit: '{onset_unit}'. Expected 'seconds' or 'samples'")
    if onset_unit == "samples" and start_s != 0.0:
        raise ValueError(
            f"start_s={start_s} applies to onsets in seconds; onsets in samples already index "
            "data, so pass start_s=0.0 or onsets in seconds"
        )
    if boundary_policy not in ("nan", "error", "drop"):
        raise ValueError(f"Unknown boundary_policy: '{boundary_policy}'. Expected 'nan', 'error', or 'drop'")

    onsets_arr = np.asarray(onsets)
    if onsets_arr.size == 0:
        empty_ret = np.empty((0,), dtype=np.int64)
        if arr.ndim == 1:
            empty_epochs = np.empty((0, n_win), dtype=arr.dtype)
        else:
            empty_epochs = np.empty((0, n_win, arr.shape[1]), dtype=arr.dtype)
        return (empty_epochs, time_axis_s, empty_ret) if return_indices else (empty_epochs, time_axis_s)

    onsets_f = onsets_arr.astype(np.float64)
    # A non-finite onset used to be cast to int64, which makes NaN INT64_MIN, and
    # `idx + n_pre` then overflowed to a large positive start with a large negative end.
    # `0 <= start and end <= n_samples` is true of that pair, so the window took the
    # in-bounds branch and `arr[start:end]` returned an empty slice: one epoch of shape
    # (0,) reported as a clean extraction, against a `time_axis_s` of 800 samples. Mixed
    # with one valid onset it reached `np.stack` and died there on mismatched shapes.
    # `events` and `event_onsets` already refuse a non-finite onset; this is the third
    # entry point, and it now refuses the same way.
    bad = np.flatnonzero(~np.isfinite(onsets_f))
    if bad.size:
        from jnwb.nwb_events import InvalidOnsetValueError

        first = int(bad[0])
        extra = (f" ({bad.size} of {onsets_f.size} onsets are non-finite)"
                 if bad.size > 1 else "")
        raise InvalidOnsetValueError(
            f"Non-finite onset at index {first}: {onsets_arr[first]!r}{extra}"
        )

    if onset_unit == "seconds":
        center_indices = np.round((onsets_f - start_s) * fs).astype(np.int64)
    else:
        center_indices = np.round(onsets_f).astype(np.int64)

    if boundary_policy == "nan":
        starts = center_indices + n_pre
        # An epoch that does not overlap [0, n_samples) at all is nothing but NaN. One or
        # two of those is ordinary. A majority means the onsets and the data are not on
        # the same clock, and the common cause is milliseconds read as seconds -- which
        # otherwise returns a full-sized, correctly-shaped, entirely-NaN array in silence.
        outside = int(np.count_nonzero((starts + n_win <= 0) | (starts >= n_samples)))
        if outside * 2 > onsets_f.size:
            unit = "s" if onset_unit == "seconds" else "samples"
            span = n_samples / fs if onset_unit == "seconds" else float(n_samples)
            warnings.warn(
                f"{outside} of {onsets_f.size} epochs fall entirely outside the data and "
                f"are all-NaN: onsets span {onsets_f.min():g} to {onsets_f.max():g} "
                f"{unit} while the data covers 0 to {span:g} {unit}. Check the onset "
                f"unit; onsets in milliseconds read as seconds land here.",
                UserWarning,
                stacklevel=2,
            )

    epochs_list: list[np.ndarray] = []
    retained_list: list[int] = []
    out_dtype = np.float64 if (boundary_policy == "nan" and np.issubdtype(arr.dtype, np.integer)) else arr.dtype

    for event_idx, (idx, onset_val) in enumerate(zip(center_indices, onsets_arr)):
        start = idx + n_pre
        end = idx + n_post

        if 0 <= start and end <= n_samples:
            epochs_list.append(arr[start:end].astype(out_dtype, copy=False))
            retained_list.append(event_idx)
        else:
            if boundary_policy == "error":
                raise ValueError(
                    f"Epoch window [{start}, {end}) for onset {onset_val} extends outside data [0, {n_samples})"
                )
            elif boundary_policy == "drop":
                continue
            else:  # "nan"
                target_dtype = np.float64 if not np.issubdtype(arr.dtype, np.floating) else arr.dtype
                if arr.ndim == 1:
                    epoch = np.full((n_win,), np.nan, dtype=target_dtype)
                    valid_start = max(0, start)
                    valid_end = min(n_samples, end)
                    if valid_start < valid_end:
                        target_start = valid_start - start
                        target_end = target_start + (valid_end - valid_start)
                        epoch[target_start:target_end] = arr[valid_start:valid_end]
                    epochs_list.append(epoch)
                    retained_list.append(event_idx)
                else:
                    n_ch = arr.shape[1]
                    epoch = np.full((n_win, n_ch), np.nan, dtype=target_dtype)
                    valid_start = max(0, start)
                    valid_end = min(n_samples, end)
                    if valid_start < valid_end:
                        target_start = valid_start - start
                        target_end = target_start + (valid_end - valid_start)
                        epoch[target_start:target_end, :] = arr[valid_start:valid_end, :]
                    epochs_list.append(epoch)
                    retained_list.append(event_idx)

    retained_arr = np.array(retained_list, dtype=np.int64)
    if not epochs_list:
        if arr.ndim == 1:
            empty_epochs = np.empty((0, n_win), dtype=out_dtype)
        else:
            empty_epochs = np.empty((0, n_win, arr.shape[1]), dtype=out_dtype)
        return (empty_epochs, time_axis_s, retained_arr) if return_indices else (empty_epochs, time_axis_s)

    epochs_arr = np.stack(epochs_list, axis=0)
    return (epochs_arr, time_axis_s, retained_arr) if return_indices else (epochs_arr, time_axis_s)


@dataclass(frozen=True)
class TickClock:
    """Map from timestamp ticks to seconds on a spike clock, built by `derive_tick_clock`.

    ``tick_step`` is the number of ticks between consecutive samples, ``tick_rate`` the ticks
    per second on the spike clock, ``first_tick`` the timestamp of the first sample, and
    ``offset_s`` that sample's time on the spike clock.
    """

    tick_step: float
    tick_rate: float
    first_tick: float
    offset_s: float

    @property
    def fs_hz(self) -> float:
        """Sampling rate of the series on the spike clock, in hertz."""
        return self.tick_rate / self.tick_step

    def seconds(self, ticks) -> np.ndarray:
        """Spike-clock seconds of the tick timestamps `ticks`."""
        ticks = np.asarray(ticks, dtype=np.float64)
        return self.offset_s + (ticks - self.first_tick) / self.tick_rate


def _spike_trains(spike_times) -> list[np.ndarray]:
    """One spike train, or a sequence of them, as a list of float arrays."""
    items = list(spike_times)
    if items and np.ndim(items[0]) == 0:
        items = [spike_times]
    return [np.asarray(train, dtype=np.float64) for train in items]


def derive_tick_clock(tick_segments: Sequence[np.ndarray], spike_times) -> TickClock:
    """Derive the map from acquisition ticks to spike-clock seconds from one recording.

    Use it for timestamps labelled seconds that hold integer acquisition ticks. The tick step
    comes from the timestamps; the tick rate comes from the spans of both clocks.

    Parameters
    ----------
    tick_segments:
        1-D tick arrays in recording order. The first starts at the recording's first sample
        and the last ends at its last, so the segments span the whole recording. Within each
        segment consecutive ticks differ by one positive step, the same in every segment; the
        gaps between segments are not checked.
    spike_times:
        One 1-D array of spike times in seconds, or a sequence of them. Their span must cover
        the same recording as the tick segments.

    Returns
    -------
    TickClock
        ``tick_rate`` is the tick span over the spike span, ``first_tick`` the first tick of the
        first segment, and ``offset_s`` the first spike. Placing the first sample at the first
        spike is an assumption, not a measurement. The caller checks the offset against an
        independent measure, such as spike-LFP coupling, before relying on it.

    Raises
    ------
    ValueError
        If there are no segments, a segment is empty or not 1-D, the tick step is not one
        positive value across the segments, a tick or spike is not finite, there are fewer than two spikes, or
        the spikes have zero span.
    """
    segments = list(tick_segments)
    if not segments:
        raise ValueError(
            "derive_tick_clock: tick_segments is empty; pass the tick arrays in recording order"
        )
    ticks = []
    for k, seg in enumerate(segments):
        arr = np.asarray(seg, dtype=np.float64)
        if arr.ndim != 1:
            raise ValueError(
                f"derive_tick_clock: tick_segments[{k}] must be 1-D, got shape {arr.shape}"
            )
        if arr.size == 0:
            raise ValueError(f"derive_tick_clock: tick_segments[{k}] is empty")
        bad = np.flatnonzero(~np.isfinite(arr))
        if bad.size:
            raise ValueError(
                f"derive_tick_clock: tick_segments[{k}] holds {bad.size} non-finite tick(s); "
                f"first at index {int(bad[0])}: {float(arr[bad[0]])!r}"
            )
        ticks.append(arr)
    steps = {float(step) for arr in ticks for step in np.unique(np.diff(arr))}
    if len(steps) != 1:
        raise ValueError(
            "derive_tick_clock: tick_segments do not share one uniform tick step; "
            f"steps found (first five): {sorted(steps)[:5]}"
        )
    tick_step = steps.pop()
    if tick_step <= 0:
        raise ValueError(
            f"derive_tick_clock: the tick step is {tick_step!r}; ticks must increase within "
            "each segment"
        )

    trains = _spike_trains(spike_times)
    for k, train in enumerate(trains):
        if train.ndim != 1:
            raise ValueError(
                f"derive_tick_clock: spike_times[{k}] must be 1-D, got shape {train.shape}"
            )
    spikes = np.concatenate(trains) if trains else np.empty(0, dtype=np.float64)
    if spikes.size < 2:
        raise ValueError(
            f"derive_tick_clock: spike_times holds {spikes.size} spike(s); "
            "at least two are needed to set the tick rate"
        )
    bad = np.flatnonzero(~np.isfinite(spikes))
    if bad.size:
        raise ValueError(
            f"derive_tick_clock: spike_times holds {bad.size} non-finite value(s); "
            f"first at index {int(bad[0])}: {float(spikes[bad[0]])!r}"
        )
    first_spike, last_spike = float(spikes.min()), float(spikes.max())
    if last_spike == first_spike:
        raise ValueError(
            f"derive_tick_clock: spike_times has zero span (every spike at {first_spike!r} s); "
            "the tick rate is undefined"
        )
    first_tick = float(ticks[0][0])
    tick_span = float(ticks[-1][-1]) - first_tick
    return TickClock(
        tick_step=tick_step,
        tick_rate=tick_span / (last_spike - first_spike),
        first_tick=first_tick,
        offset_s=first_spike,
    )


# `effective_rate` holds a series when at least this share of its consecutive samples repeat
# exactly. A hold to twice the source rate repeats half of them; a native continuous series
# repeats none. The value is set from those two cases and has not been checked on recorded data.
HELD_MIN_REPEAT_FRACTION = 0.25


@dataclass(frozen=True)
class EffectiveRate:
    """Evidence on the rate a stream was sampled at, returned by `effective_rate`.

    ``repeat_fraction`` is the share of consecutive sample pairs that are exactly equal.
    ``repeat_runs`` maps each run length, in samples, to the number of runs of identical
    consecutive samples at least two long: a hold to twice the source rate gives ``{2: n}``.
    ``power_above_quarter`` is the share of the Welch power spectrum above ``rate / 4``; it is
    NaN when the series has no power. ``held`` is True when ``repeat_fraction`` is at least
    `HELD_MIN_REPEAT_FRACTION`.
    """

    repeat_fraction: float
    repeat_runs: dict[int, int]
    power_above_quarter: float
    held: bool


def effective_rate(data: np.ndarray | Sequence[float], rate: float) -> EffectiveRate:
    """Measure whether a stream repeats samples as if it were held from a lower rate.

    A stream held from a lower source rate repeats each source sample, so its consecutive
    samples repeat exactly and its power above ``rate / 4`` is reduced. ``held`` is True when
    the repeat fraction is at least ``HELD_MIN_REPEAT_FRACTION`` (0.25, a module constant, not
    a parameter). The power fraction is returned as evidence and does not enter the decision.
    A constant series repeats every sample and is reported as held.

    Parameters
    ----------
    data:
        1-D array of shape ``(n_samples,)`` with ``n_samples >= 2``, all finite.
    rate:
        Stored sampling rate in Hz, positive and finite.

    Returns
    -------
    EffectiveRate

    Raises
    ------
    ValueError
        If ``data`` is not 1-D with at least two samples, holds a NaN or infinite value, or
        ``rate`` is not a positive finite number.
    """
    x = np.asarray(data, dtype=np.float64)
    if x.ndim != 1 or x.size < 2:
        raise ValueError(
            f"effective_rate: data must be 1-D with at least two samples, got shape {x.shape}"
        )
    if not np.all(np.isfinite(x)):
        bad = int(np.flatnonzero(~np.isfinite(x))[0])
        raise ValueError(f"effective_rate: data must be finite; index {bad} is {x[bad]!r}")
    if not (np.isfinite(rate) and rate > 0):
        raise ValueError(f"effective_rate: rate must be positive and finite in Hz, got {rate!r}")

    same = x[1:] == x[:-1]
    repeat_fraction = float(np.mean(same))
    # Pad with False so every run of repeats has a start and an end in `edges`.
    edges = np.diff(np.concatenate(([0], same.astype(np.int64), [0])))
    run_starts = np.flatnonzero(edges == 1)
    run_ends = np.flatnonzero(edges == -1)
    # A run of r repeats spans r + 1 identical samples.
    lengths, counts = np.unique((run_ends - run_starts) + 1, return_counts=True)
    repeat_runs = {int(length): int(count) for length, count in zip(lengths, counts)}

    freqs, psd = signal.welch(x, fs=float(rate))
    total = float(np.sum(psd))
    power_above_quarter = (
        float(np.sum(psd[freqs > rate / 4.0])) / total if total > 0 else float("nan")
    )
    return EffectiveRate(
        repeat_fraction=repeat_fraction,
        repeat_runs=repeat_runs,
        power_above_quarter=power_above_quarter,
        held=bool(repeat_fraction >= HELD_MIN_REPEAT_FRACTION),
    )


def gaze_departure_onsets(
    gaze: np.ndarray | Sequence[float],
    rate: float,
    trial_starts: np.ndarray | Sequence[float],
    *,
    baseline_window_s: tuple[float, float],
    reference_trials: np.ndarray | Sequence[int],
    envelope_percentile: float = 99.5,
    hold_s: float = 0.025,
    walkback_fraction: float = 0.5,
) -> np.ndarray:
    """Find, per trial, the time the gaze leaves its baseline position.

    Per trial, the deviation of each sample is its distance from the median gaze over
    ``baseline_window_s``. The envelope is the ``envelope_percentile`` of the deviation pooled over
    ``reference_trials``. The departure is the first sample from which the deviation stays above
    the envelope for ``hold_s``. The onset then walks back to the last sample before it at or
    below ``walkback_fraction`` times the envelope; if no such sample exists, the onset is the
    departure sample.

    Each trial's search runs from its start to the next trial's start, or to the end of the
    data for the last trial. The baseline window may lie outside that span (a pre-trial
    fixation), but not outside the data.

    Parameters
    ----------
    gaze:
        Gaze position of shape ``(n_samples,)`` or ``(n_samples, n_axes)``. NaN marks a
        sample that breaks a run; infinite values are refused.
    rate:
        Sampling rate of ``gaze`` in Hz, positive and finite.
    trial_starts:
        1-D array of trial start times in seconds on the gaze clock, where sample 0 is t = 0.
    baseline_window_s:
        ``(start_s, stop_s)`` in seconds relative to each trial start, with ``start_s < stop_s``.
    reference_trials:
        Integer indices into ``trial_starts`` whose deviations set the envelope.
    envelope_percentile:
        Percentile of the reference deviations that sets the envelope, in ``[0, 100]``.
    hold_s:
        Duration in seconds the deviation must stay above the envelope, positive and finite.
    walkback_fraction:
        Fraction of the envelope, in ``[0, 1]``, that the walk back must reach.

    Returns
    -------
    numpy.ndarray
        Float array of shape ``(n_trials,)``: each onset in seconds on the gaze clock, NaN for a
        trial with no departure.

    Raises
    ------
    ValueError
        On a malformed argument, an empty ``reference_trials``, a baseline that is empty or
        outside the data, or reference deviations that are all NaN.
    """
    g = np.asarray(gaze, dtype=np.float64)
    if g.ndim not in (1, 2) or g.shape[0] == 0:
        raise ValueError(
            f"gaze_departure_onsets: gaze must be 1-D or (n_samples, n_axes), got shape {g.shape}"
        )
    if np.isinf(g).any():
        raise ValueError("gaze_departure_onsets: gaze holds an infinite value; NaN is allowed")
    g = g.reshape(g.shape[0], -1)
    n = g.shape[0]
    if not (np.isfinite(rate) and rate > 0):
        raise ValueError(f"gaze_departure_onsets: rate must be positive and finite, got {rate!r}")
    starts_s = np.asarray(trial_starts, dtype=np.float64)
    if starts_s.ndim != 1 or starts_s.size == 0 or not np.all(np.isfinite(starts_s)):
        raise ValueError(
            "gaze_departure_onsets: trial_starts must be a non-empty 1-D array of finite seconds"
        )
    refs = np.asarray(reference_trials)
    if refs.size == 0:
        raise ValueError(
            "gaze_departure_onsets: reference_trials is empty; name at least one trial "
            "to set the envelope"
        )
    if refs.dtype.kind not in "iu" or refs.min() < 0 or refs.max() >= starts_s.size:
        raise ValueError(
            f"gaze_departure_onsets: reference_trials must hold trial indices in "
            f"[0, {starts_s.size}), got {refs.tolist()}"
        )
    base_lo_s, base_hi_s = (float(baseline_window_s[0]), float(baseline_window_s[1]))
    if not (np.isfinite(base_lo_s) and np.isfinite(base_hi_s) and base_lo_s < base_hi_s):
        raise ValueError(
            f"gaze_departure_onsets: baseline_window_s must be (start_s, stop_s) with start_s "
            f"< stop_s, got {baseline_window_s}"
        )
    if not 0.0 <= envelope_percentile <= 100.0:
        raise ValueError(
            f"gaze_departure_onsets: envelope_percentile must be in [0, 100], got "
            f"{envelope_percentile}"
        )
    if not (np.isfinite(hold_s) and hold_s > 0):
        raise ValueError(f"gaze_departure_onsets: hold_s must be positive and finite, got {hold_s}")
    if not 0.0 <= walkback_fraction <= 1.0:
        raise ValueError(
            f"gaze_departure_onsets: walkback_fraction must be in [0, 1], got {walkback_fraction}"
        )
    # Sample counts as `epoch_continuous` takes them: a trial start rounds to a sample, and the
    # window and hold edges are containment bounds.
    hold = max(1, _containment_sample(hold_s, rate))

    first = np.round(starts_s * rate).astype(np.int64)
    spans = []
    for k in range(starts_s.size):
        stop = int(first[k + 1]) if k + 1 < starts_s.size else n
        spans.append((min(max(int(first[k]), 0), n), min(max(stop, 0), n)))

    devs = []
    for k in range(starts_s.size):
        b0 = int(first[k]) + _containment_sample(base_lo_s, rate)
        b1 = int(first[k]) + _containment_sample(base_hi_s, rate)
        if b0 < 0 or b1 > n or b1 <= b0:
            raise ValueError(
                f"gaze_departure_onsets: baseline_window_s {baseline_window_s} for trial {k} is "
                f"empty or outside the gaze samples [0, {n})"
            )
        centre = np.nanmedian(g[b0:b1], axis=0)
        lo, hi = spans[k]
        devs.append(np.sqrt(np.sum((g[lo:hi] - centre) ** 2, axis=1)))

    pooled = np.concatenate([devs[k] for k in refs.tolist()])
    finite = pooled[np.isfinite(pooled)]
    if finite.size == 0:
        raise ValueError(
            "gaze_departure_onsets: no finite deviation in reference_trials; the envelope "
            "is undefined"
        )
    envelope = float(np.percentile(finite, envelope_percentile))
    walk_threshold = walkback_fraction * envelope

    onsets = np.full(starts_s.size, np.nan)
    for k, dev in enumerate(devs):
        if dev.size < hold:
            continue
        # A NaN deviation compares False, so it breaks a run.
        above = (dev > envelope).astype(np.int64)
        cumulative = np.concatenate(([0], np.cumsum(above)))
        sustained = cumulative[hold:] - cumulative[:-hold] == hold
        if not sustained.any():
            continue
        departure = int(np.argmax(sustained))
        at_or_below = np.flatnonzero(dev[:departure] <= walk_threshold)
        onset = int(at_or_below[-1]) if at_or_below.size else departure
        onsets[k] = (spans[k][0] + onset) / rate
    return onsets
