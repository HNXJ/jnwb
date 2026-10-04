"""
jnwb.unit_quality -- waveform and spike-train quality measures of one sorted unit.

Each function takes one unit: a mean waveform ``(n_channels, n_samples)`` with its sampling
rate and, for the spatial measure, the channel positions; the unit's individual waveforms on
one channel; or its spike times in seconds. None of them decides whether a unit is kept. A
measure with a published definition cites it; the two threshold checks,
`waveform_flatness` and `spatial_derivative_sharpness`, have no published source and take
their threshold from the caller.

Undefined input is NaN, ``None`` for a verdict, or a ``ValueError`` naming the reason; it is
never read as 0.
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np


def _mean_waveform(waveform, func_name: str) -> np.ndarray:
    """``waveform`` as a finite float ``(n_channels, n_samples)`` array, or ValueError."""
    w = np.asarray(waveform, dtype=float)
    if w.ndim != 2 or w.shape[0] < 1 or w.shape[1] < 2:
        raise ValueError(
            f"{func_name}: waveform must be a mean waveform (n_channels, n_samples) with at "
            f"least one channel and two samples; got shape {w.shape}."
        )
    if not np.all(np.isfinite(w)):
        raise ValueError(
            f"{func_name}: waveform holds {int(np.sum(~np.isfinite(w)))} NaN or infinite "
            "value(s); a mean waveform with missing samples has no defined extremum."
        )
    return w


def _positive_finite(value, name: str, func_name: str) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{func_name}: {name} must be a finite positive number; got {value!r}.")
    if not (np.isfinite(v) and v > 0):
        raise ValueError(f"{func_name}: {name} must be a finite positive number; got {value!r}.")
    return v


def _peak_channel(w: np.ndarray, func_name: str):
    """``(peak channel, per-channel amplitudes)``: the channel of largest peak-to-trough
    amplitude ``max - min``, the first of tied channels. A waveform of zero amplitude on every
    channel has no peak channel and raises."""
    amplitudes = w.max(axis=1) - w.min(axis=1)
    peak = int(np.argmax(amplitudes))
    if amplitudes[peak] <= 0:
        raise ValueError(
            f"{func_name}: the waveform has zero amplitude on every channel, so it has no "
            "peak channel."
        )
    return peak, amplitudes


def waveform_features(waveform, fs: float) -> Dict[str, Any]:
    """Peak channel, amplitude, trough-to-peak duration, peak-trough ratio and polarity.

    Input class: the unit's mean extracellular waveform ``(n_channels, n_samples)``, high-pass
    filtered so its baseline is zero, in any voltage unit, sampled at `fs` Hz. Every feature
    is read on the **peak channel**, the channel of largest amplitude, where a channel's
    amplitude is the difference between its maximum (the peak) and its minimum (the trough)
    (Siegle et al. 2021, Methods; Jia et al. 2019).

    * ``trough_to_peak_ms`` is the time of the peak minus the time of the trough on the peak
      channel, in ms, at the resolution of one sample ``1000 / fs`` (Siegle et al. 2021,
      "waveform duration"). The peak is the channel's maximum wherever it falls, so the value
      is negative when the maximum precedes the minimum, as in an inverted waveform.
    * ``peak_trough_ratio`` is the peak amplitude over the trough amplitude, ``max / |min|``,
      unitless (Jia et al. 2019, "PT ratio"). Above 1 the waveform rises more than it falls.
      It is NaN unless the peak is above zero and the trough below it.
    * ``polarity`` is ``+1.0`` when the positive peak is larger in magnitude than the negative
      one, ``-1.0`` when the negative one is, and NaN when they are equal.

    Args:
        waveform: Mean waveform ``(n_channels, n_samples)``; rows are channels.
        fs: Sampling rate in Hz.

    Returns:
        Dict with ``peak_channel`` (row index, 0-based), ``amplitude`` (the waveform's unit),
        ``trough_to_peak_ms``, ``peak_trough_ratio`` and ``polarity``.

    Raises:
        ValueError: If the waveform is not 2-D with at least one channel and two samples,
            holds a NaN or an infinity, or has zero amplitude on every channel (no peak
            channel); or if `fs` is not finite and positive.

    References:
        Siegle, J. H., et al. (2021). Survey of spiking in the mouse visual system reveals
        functional hierarchy. Nature 592, 86-92. doi:10.1038/s41586-020-03171-x

        Jia, X., et al. (2019). High-density extracellular probes reveal dendritic
        backpropagation and facilitate neuron classification. Journal of Neurophysiology
        121(5), 1831-1847. doi:10.1152/jn.00680.2018
    """
    name = "waveform_features"
    fs = _positive_finite(fs, "fs", name)
    w = _mean_waveform(waveform, name)
    peak, amplitudes = _peak_channel(w, name)
    trace = w[peak]
    hi, lo = float(trace.max()), float(trace.min())
    duration_ms = (int(np.argmax(trace)) - int(np.argmin(trace))) * 1000.0 / fs
    ratio = hi / -lo if (hi > 0 and lo < 0) else float("nan")
    if hi > -lo:
        polarity = 1.0
    elif hi < -lo:
        polarity = -1.0
    else:
        polarity = float("nan")
    return {
        "peak_channel": peak,
        "amplitude": float(amplitudes[peak]),
        "trough_to_peak_ms": float(duration_ms),
        "peak_trough_ratio": float(ratio),
        "polarity": polarity,
    }


def waveform_snr(spike_waveforms) -> float:
    """Signal-to-noise ratio of one unit on one channel (Siegle et al. 2021, Methods).

    Input class: the unit's individual spike waveforms on one channel, normally its peak
    channel (`waveform_features`), ``(n_spikes, n_samples)``. The mean waveform is
    subtracted from every spike; the SNR is the mean waveform's amplitude (maximum minus
    minimum) over twice the standard deviation of those residuals, taken over every sample
    of every residual (``ddof=0``). Unitless. Which spikes, and how many, are the caller's
    choice; the source used 1,000.

    Args:
        spike_waveforms: ``(n_spikes, n_samples)`` array of individual waveforms.

    Returns:
        The SNR as a float. NaN when the residuals have zero standard deviation (a single
        spike, or identical spikes): a zero noise estimate gives no finite ratio.

    Raises:
        ValueError: If the array is not 2-D with at least one spike and two samples, or holds
            a NaN or an infinity.

    References:
        Siegle, J. H., et al. (2021). Survey of spiking in the mouse visual system reveals
        functional hierarchy. Nature 592, 86-92. doi:10.1038/s41586-020-03171-x
    """
    w = np.asarray(spike_waveforms, dtype=float)
    if w.ndim != 2 or w.shape[0] < 1 or w.shape[1] < 2:
        raise ValueError(
            "waveform_snr: spike_waveforms must be (n_spikes, n_samples) with at least one "
            f"spike and two samples; got shape {w.shape}."
        )
    if not np.all(np.isfinite(w)):
        raise ValueError(
            f"waveform_snr: spike_waveforms holds {int(np.sum(~np.isfinite(w)))} NaN or "
            "infinite value(s)."
        )
    mean = w.mean(axis=0)
    noise = float(np.std(w - mean))
    if noise == 0:
        return float("nan")
    return float((mean.max() - mean.min()) / (2.0 * noise))


def waveform_flatness(waveform, *, threshold: float) -> Dict[str, Any]:
    """Whether a mean waveform is flat: its peak-channel amplitude is below `threshold`.

    Input class: a mean waveform ``(n_channels, n_samples)`` in any voltage unit. The
    amplitude is the largest over channels of maximum minus minimum, the peak-channel
    amplitude of `waveform_features`, in the waveform's unit; `threshold` is in the same
    unit. This check has no published source: the threshold is the caller's and has no
    default. A waveform of zero amplitude is flat, not undefined.

    Args:
        waveform: Mean waveform ``(n_channels, n_samples)``.
        threshold: Amplitude below which the waveform is flat; finite and positive.

    Returns:
        Dict with ``amplitude`` (float) and ``is_flat`` (``bool``).

    Raises:
        ValueError: If the waveform is not 2-D with at least one channel and two samples or
            holds a NaN or an infinity, or if `threshold` is not finite and positive.
    """
    name = "waveform_flatness"
    threshold = _positive_finite(threshold, "threshold", name)
    w = _mean_waveform(waveform, name)
    amplitude = float((w.max(axis=1) - w.min(axis=1)).max())
    return {"amplitude": amplitude, "is_flat": bool(amplitude < threshold)}


def spatial_derivative_sharpness(waveform, channel_positions, *, threshold: float) -> Dict[str, Any]:
    """How sharply amplitude falls from the peak channel to its nearest channels.

    Input class: a mean waveform ``(n_channels, n_samples)`` and the position of each channel,
    ``(n_channels,)`` or ``(n_channels, n_dims)``, in one length unit (for example µm). With
    ``a`` the per-channel amplitude (maximum minus minimum) and ``p`` the peak channel of
    `waveform_features`, the sharpness is the mean over the channels nearest to ``p`` (all
    at the smallest nonzero Euclidean distance ``d``) of ``(a[p] - a[j]) / (a[p] * d)``: the
    fractional drop in amplitude per unit length, in the inverse of the position unit. A unit
    seen on one channel alone scores ``1 / d``; a deflection equal on every channel scores 0.

    This measure has no published source: the threshold is the caller's and has no default.

    Args:
        waveform: Mean waveform ``(n_channels, n_samples)``; at least two channels.
        channel_positions: Channel positions, one row per waveform row.
        threshold: Sharpness, in the inverse of the position unit, at or above which the
            unit is sharp; finite and positive.

    Returns:
        Dict with ``sharpness`` (float), ``is_sharp`` (``bool``), ``peak_channel`` and
        ``neighbour_channels`` (the channels at distance ``d``).

    Raises:
        ValueError: If the waveform has one channel (a spatial derivative needs two), is not
            2-D or holds a NaN or an infinity, or has zero amplitude on every channel (no peak
            channel); if the positions do not match the channels, are not finite, or put
            another channel at the peak channel's position; or if `threshold` is not finite
            and positive.
    """
    name = "spatial_derivative_sharpness"
    threshold = _positive_finite(threshold, "threshold", name)
    w = _mean_waveform(waveform, name)
    if w.shape[0] < 2:
        raise ValueError(
            f"{name}: a spatial derivative needs at least two channels; got {w.shape[0]}."
        )
    pos = np.asarray(channel_positions, dtype=float)
    if pos.ndim == 1:
        pos = pos[:, None]
    if pos.ndim != 2 or pos.shape[0] != w.shape[0]:
        raise ValueError(
            f"{name}: channel_positions must have one row per channel ({w.shape[0]}); got "
            f"shape {np.shape(channel_positions)}."
        )
    if not np.all(np.isfinite(pos)):
        raise ValueError(f"{name}: channel_positions holds a NaN or an infinity.")
    peak, amplitudes = _peak_channel(w, name)
    dist = np.sqrt(((pos - pos[peak]) ** 2).sum(axis=1))
    others = np.arange(w.shape[0]) != peak
    if np.any(dist[others] == 0):
        raise ValueError(
            f"{name}: channel(s) {np.flatnonzero(others & (dist == 0)).tolist()} share the "
            f"peak channel's position; distance to them is zero."
        )
    d = float(dist[others].min())
    nearest = np.flatnonzero(others & np.isclose(dist, d, rtol=1e-9, atol=0.0))
    drops = (amplitudes[peak] - amplitudes[nearest]) / (amplitudes[peak] * d)
    sharpness = float(drops.mean())
    return {
        "sharpness": sharpness,
        "is_sharp": bool(sharpness >= threshold),
        "peak_channel": peak,
        "neighbour_channels": nearest,
    }


def presence_ratio(spike_times, blocks) -> float:
    """Fraction of caller-given blocks that hold at least one spike (Siegle et al. 2021).

    Input class: one unit's spike times in seconds and the blocks, an array ``(n_blocks, 2)``
    of ``[start, stop)`` times in seconds. The source divided the session into 100 equal
    blocks; here the blocks are the caller's, of any length, and a block's membership is the
    half-open window of `jnwb.fires_in_window`. Unitless, between 0 and 1.

    Args:
        spike_times: 1-D spike times in seconds, any order.
        blocks: ``(n_blocks, 2)`` start and stop of each block in seconds.

    Returns:
        The presence ratio. NaN for an empty spike train, which carries no unit to measure; a
        unit whose spikes all fall outside the blocks has ratio 0.

    Raises:
        ValueError: If there is no block, a block is not a finite ``(start, stop)`` pair with
            start before stop (a zero-length block has no time to hold a spike), or a spike
            time is not finite.

    References:
        Siegle, J. H., et al. (2021). Survey of spiking in the mouse visual system reveals
        functional hierarchy. Nature 592, 86-92. doi:10.1038/s41586-020-03171-x
    """
    from .statistics import fires_in_window

    b = np.asarray(blocks, dtype=float)
    if b.ndim != 2 or b.shape[1] != 2 or b.shape[0] < 1:
        raise ValueError(
            f"presence_ratio: blocks must be (n_blocks, 2) with at least one block; got shape "
            f"{b.shape}."
        )
    bad = ~(np.isfinite(b).all(axis=1) & (b[:, 1] > b[:, 0]))
    if bad.any():
        raise ValueError(
            f"presence_ratio: block(s) {np.flatnonzero(bad).tolist()} are not a finite "
            "(start, stop) with start before stop; a zero-length block has no time to hold "
            "a spike."
        )
    st = np.sort(np.asarray(spike_times, dtype=float).ravel())
    if st.size == 0:
        return float("nan")
    present = [fires_in_window(st, start, (0.0, (stop - start) * 1000.0)) for start, stop in b]
    return float(np.mean(present))


def isi_cv(spike_times) -> float:
    """Coefficient of variation of the inter-spike intervals (Shinomoto et al. 2009, eq. 1).

    Input class: one unit's spike times in seconds, any order. The CV is the standard
    deviation of the intervals (``ddof=0``) over their mean, unitless, computed by the rule of
    `UnitAnalyzer.quality_metrics`. It is 0 for a perfectly regular train and near 1 for a
    Poisson train.

    Args:
        spike_times: 1-D spike times in seconds.

    Returns:
        The CV. NaN with fewer than three spikes (fewer than two intervals) or a zero mean
        interval.

    Raises:
        ValueError: If `spike_times` is not 1-D or holds a NaN or an infinity.

    References:
        Shinomoto, S., et al. (2009). Relating neuronal firing patterns to functional
        differentiation of cerebral cortex. PLoS Computational Biology 5(7), e1000433.
        doi:10.1371/journal.pcbi.1000433
    """
    from .analyzers import UnitAnalyzer

    return float(UnitAnalyzer.quality_metrics(spike_times, float("nan"), float("nan"))["cv_isi"])
