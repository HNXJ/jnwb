"""
jnwb.unit_quality -- waveform and spike-train quality measures of one sorted unit.

Each function takes one unit: a mean waveform ``(n_channels, n_samples)`` with its sampling
rate and, for the spatial measure, the channel positions; the unit's individual waveforms on
one channel; or its spike times in seconds. None of them decides whether a unit is kept. A
measure with a published definition cites it. ``is_flat`` of `waveform_flatness` and
``is_sharp`` of `spatial_derivative_sharpness` are verdicts against a threshold the caller
gives; neither check has a published source. Duplicate spike times are the caller's to
remove: a duplicate is an interval of 0.

Undefined input is NaN, ``None`` for a verdict, or a ``ValueError`` naming the reason; it is
never read as 0.
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np


#: Two durations closer than this compare as equal: below one sample at any rate under
#: 1 GHz, and above the rounding error of an interval between spike times stored as
#: sample index over rate.
_BOUNDARY_TOLERANCE_S = 1e-9


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


def _peak_channel(w: np.ndarray, func_name: str, *, flat_ok: bool = False):
    """``(peak channel, per-channel amplitudes)``: the channel of largest peak-to-trough
    amplitude ``max - min``, the first of tied channels. Non-finite samples are left out of a
    channel's extremes, so a channel with no finite sample has amplitude -inf and never wins. A
    waveform of zero amplitude on every channel has no peak channel and raises, unless `flat_ok`
    (a drawing), which takes the first channel."""
    finite = np.isfinite(w)
    amplitudes = (np.where(finite, w, -np.inf).max(axis=1)
                  - np.where(finite, w, np.inf).min(axis=1))
    peak = int(np.argmax(amplitudes))
    if amplitudes[peak] <= 0 and not flat_ok:
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

    * ``trough_to_peak_ms`` is the waveform duration of Siegle et al. (2021), in ms, at the
      resolution of one sample ``1000 / fs``, computed as the code behind that paper computes
      it (``calculate_waveform_duration`` of ``ecephys_spike_sorting``): from the dominant extremum (the maximum when it exceeds ``|min|``, else the minimum)
      to the first occurrence of the opposite extremum at or after it. It is never negative.
      A downstream curation pipeline's redefinition differs: it reads the channel of the
      deepest trough, scales that trace by its range, subtracts a linear ramp from 0 to 1 over
      the 56 samples from the trough on, ends at the first strict local maximum of the result
      and adds two samples at an assumed 30 kHz, so the two durations need not agree.
    * ``peak_trough_ratio`` is the peak amplitude over the trough amplitude, ``max / |min|``,
      unitless (Jia et al. 2019, "PT ratio"). Above 1 the waveform rises more than it falls.
      It assumes a baseline of zero (an offset changes it), and is NaN unless the peak is
      above zero and the trough below it.
    * ``polarity`` is ``sign(max - |min|)``, the side of 1 on which the peak-trough ratio
      falls where that ratio is defined, and NaN on a tie. It has no published source of its
      own.

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
    if hi > -lo:  # dominant peak: to the first minimum of the trace from it on
        start = int(np.argmax(trace))
        stop = start + int(np.argmin(trace[start:]))
    else:         # dominant trough: to the first maximum of the trace from it on
        start = int(np.argmin(trace))
        stop = start + int(np.argmax(trace[start:]))
    duration_ms = (stop - start) * 1000.0 / fs
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


#: The defaults below are those of ``ecephys_spike_sorting`` (AllenInstitute) at commit
#: 919992748a5324724ba87169ecdcf9eb6e3b9973; each cites the file and line that fixes it.
#: Upsampling factor of the peak-channel trace before the 1-D measures
#: (``modules/mean_waveforms/_schemas.py:11``).
_UPSAMPLING_FACTOR = 200 / 82


def _upsampled_peak_trace(waveform, fs, upsampling_factor, func_name):
    """The peak-channel trace Fourier-resampled by `upsampling_factor` to
    ``m = int(n_samples * upsampling_factor)`` samples, and the interval in ms of the time axis
    ``linspace(0, n_samples / fs, m)`` that ``ecephys_spike_sorting`` gives it
    (``waveform_metrics.py:63-69``): ``n_samples / (fs * (m - 1))``, longer than the resampled
    trace's own ``n_samples / (fs * m)`` by ``m / (m - 1)``, kept to match the source."""
    from scipy.signal import resample

    fs = _positive_finite(fs, "fs", func_name)
    factor = _positive_finite(upsampling_factor, "upsampling_factor", func_name)
    if factor < 1:
        raise ValueError(f"{func_name}: upsampling_factor must be 1 or more; got {upsampling_factor!r}.")
    w = _mean_waveform(waveform, func_name)
    peak, _ = _peak_channel(w, func_name)
    trace = w[peak]
    n = trace.size
    m = int(n * factor)
    if m != n:
        trace = resample(trace, m)
    return trace, n * 1000.0 / (fs * (m - 1))


def waveform_halfwidth(waveform, fs: float, *,
                       upsampling_factor: float = _UPSAMPLING_FACTOR) -> float:
    """Width of the largest deflection at half its height, in ms (Jia et al. 2019).

    Input class: the unit's mean waveform ``(n_channels, n_samples)``, baseline zero, in any
    voltage unit, sampled at `fs` Hz. The measure is read on the peak channel of
    `waveform_features`, Fourier-resampled to ``int(n_samples * upsampling_factor)`` samples
    over the same span, in the form ``calculate_waveform_halfwidth`` of
    ``ecephys_spike_sorting`` computes it (``modules/mean_waveforms/waveform_metrics.py:154-193``
    at commit 919992748a53). The extremum is the maximum when it exceeds ``|min|``, else the
    minimum (the minimum on a tie), and the half level is half its value. The width runs from
    the first sample before the extremum that lies beyond the half level (above it for a
    maximum, below it for a minimum) to the first sample at or after the extremum that lies
    back within it, strictly in both cases. Time is the source's axis
    ``linspace(0, n_samples / fs, m)`` with ``m = int(n_samples * upsampling_factor)``, so the
    width is a whole number of intervals ``n_samples / (fs * (m - 1))``: longer than the
    resampled trace's own interval by ``m / (m - 1)`` (0.5 % at 82 samples), as in the source.
    ``upsampling_factor=1`` reads the trace as given, on the same axis. The peak channel is
    the mean waveform's channel of largest amplitude; the source takes it from the sorter's
    template (``extract_waveforms.py:89``), so the two can differ where template and mean
    disagree. A NaN sample or a waveform flat on every channel is refused, where the source
    returns a number or NaN.

    Args:
        waveform: Mean waveform ``(n_channels, n_samples)``; rows are channels.
        fs: Sampling rate in Hz.
        upsampling_factor: Resampling factor, 1 or more; 200/82 in the source.

    Returns:
        The half-width in ms. NaN when no sample before the extremum lies beyond the half
        level, or none after it returns within it, as for an extremum on the first sample.

    Raises:
        ValueError: If the waveform is not 2-D with at least one channel and two samples,
            holds a NaN or an infinity, or has zero amplitude on every channel; or if `fs` is
            not finite and positive or `upsampling_factor` is below 1 or not finite.

    References:
        Jia, X., et al. (2019). High-density extracellular probes reveal dendritic
        backpropagation and facilitate neuron classification. Journal of Neurophysiology
        121(5), 1831-1847. doi:10.1152/jn.00680.2018
    """
    trace, dt_ms = _upsampled_peak_trace(waveform, fs, upsampling_factor, "waveform_halfwidth")
    hi_i, lo_i = int(np.argmax(trace)), int(np.argmin(trace))
    if trace[hi_i] > -trace[lo_i]:
        ext, sign = hi_i, 1.0
    else:
        ext, sign = lo_i, -1.0
    half = 0.5 * trace[ext]
    before = np.flatnonzero(sign * trace[:ext] > sign * half)
    after = np.flatnonzero(sign * trace[ext:] < sign * half)
    if before.size == 0 or after.size == 0:
        return float("nan")
    return float((ext + after[0] - before[0]) * dt_ms)


def repolarization_slope(waveform, fs: float, *,
                         upsampling_factor: float = _UPSAMPLING_FACTOR,
                         window_samples: int = 20) -> float:
    """Slope of the return towards baseline after the largest deflection (Jia et al. 2019).

    Input class: as `waveform_halfwidth`; the peak channel, chosen and resampled the same way,
    and the refusals are as there. The
    form is that of ``calculate_waveform_repolarization_slope`` of ``ecephys_spike_sorting``
    (``modules/mean_waveforms/waveform_metrics.py:220-244`` at commit 919992748a53): the
    extremum is the first sample of largest ``|w|``; the trace is negated when that sample is
    positive, so the extremum is always a trough; the slope is the least-squares line through
    the `window_samples` resampled samples from the extremum on (fewer at the trace's end),
    against time. It is in the waveform's unit per ms: µV/ms for a waveform in µV, which is
    1000 times the V/s the source reports for the same waveform. Time is the source's axis, as
    in `waveform_halfwidth`, which makes the slope lower than on the resampled trace's own
    interval by ``(m - 1) / m``. On an exact tie of ``max``
    and ``|min|`` the extremum is whichever comes first, unlike `waveform_halfwidth`. The
    window is a number of resampled samples, so its duration changes with `fs` and
    `upsampling_factor`: 20 samples of a 30 kHz trace resampled by 200/82 last 0.27 ms.

    Args:
        waveform: Mean waveform ``(n_channels, n_samples)``; rows are channels.
        fs: Sampling rate in Hz.
        upsampling_factor: Resampling factor, 1 or more; 200/82 in the source.
        window_samples: Samples in the fit, 2 or more; 20 in the source
            (``waveform_metrics.py:220``).

    Returns:
        The slope in the waveform's unit per ms; positive for a return towards baseline. NaN
        when fewer than two samples remain from the extremum on.

    Raises:
        ValueError: As `waveform_halfwidth`, and if `window_samples` is not an integer of 2
            or more.

    References:
        Jia, X., et al. (2019). High-density extracellular probes reveal dendritic
        backpropagation and facilitate neuron classification. Journal of Neurophysiology
        121(5), 1831-1847. doi:10.1152/jn.00680.2018
    """
    name = "repolarization_slope"
    if isinstance(window_samples, bool) or not isinstance(window_samples, (int, np.integer)) \
            or window_samples < 2:
        raise ValueError(f"{name}: window_samples must be an integer of 2 or more; got "
                         f"{window_samples!r}.")
    trace, dt_ms = _upsampled_peak_trace(waveform, fs, upsampling_factor, name)
    ext = int(np.argmax(np.abs(trace)))
    y = -np.sign(trace[ext]) * trace[ext:ext + int(window_samples)]
    if y.size < 2:
        return float("nan")
    t = np.arange(y.size) * dt_ms
    tc = t - t.mean()
    return float(np.dot(tc, y - y.mean()) / np.dot(tc, tc))


def waveform_spread(waveform, *, site_spacing_um: float, threshold: float = 0.12,
                    site_range: int = 16, site_step: int = 2,
                    outlier_z: float = 1.5) -> float:
    """Extent along the probe of the channels that carry the unit, in µm (Jia et al. 2019).

    Input class: the unit's mean waveform ``(n_channels, n_samples)`` in any voltage unit,
    rows in the probe's channel order, and the vertical distance `site_spacing_um` that one
    step of `site_step` channels covers. The form is that of ``calculate_2D_features`` of
    ``ecephys_spike_sorting`` (``modules/mean_waveforms/waveform_metrics.py:284-346`` at commit
    919992748a53). The sites are every `site_step`-th channel within `site_range` channels of
    the peak channel of `waveform_features`, on the probe, leaving out channel 0 as the source
    does (``sites_to_sample > 0``, line 311). A site carries the unit when its amplitude
    (maximum minus minimum) exceeds `threshold` times the largest site amplitude, strictly;
    that is the peak channel's unless channel 0 is the peak. When more than one site does, a
    site is dropped as an outlier when the modified z-score of its position,
    ``0.6745 |x - median| / MAD`` (``isnot_outlier``, lines 397-433), exceeds `outlier_z`. The
    spread is the number of sites kept times `site_spacing_um`; the source multiplies a spacing
    in metres by 1e6, so the two agree to rounding (about 3e-14 µm), not bit for bit. The
    source's spacing is the probe's vertical site spacing, 20 µm by default
    (``common/schemas.py:11``), with two channels per row. The peak channel is the mean
    waveform's channel of largest amplitude; the source takes it from the sorter's template
    (``extract_waveforms.py:89``). A NaN sample or a waveform flat on every channel is
    refused, where the source returns a number or NaN.

    Args:
        waveform: Mean waveform ``(n_channels, n_samples)``; rows in probe order.
        site_spacing_um: Distance in µm between consecutive sites; required, finite, positive.
        threshold: Fraction of the peak amplitude a site must exceed; 0.12 in the source
            (line 284).
        site_range: Channels on each side of the peak channel; 16 in the source (line 284).
        site_step: Channels between sites; 2 in the source (line 309).
        outlier_z: Modified z-score above which a site is an outlier; 1.5 in the source
            (line 397).

    Returns:
        The spread in µm, at least `site_spacing_um` (the site of largest amplitude always
        carries the unit).

    Raises:
        ValueError: If the waveform is not 2-D with at least one channel and two samples,
            holds a NaN or an infinity, or has zero amplitude on every channel; no site
            above channel 0 is in range;
            `site_spacing_um` is not finite and positive; `threshold` is not in ``[0, 1)``;
            `site_step` is not a positive integer; `site_range` is not a non-negative
            multiple of `site_step`; or `outlier_z` is not finite and positive.

    References:
        Jia, X., et al. (2019). High-density extracellular probes reveal dendritic
        backpropagation and facilitate neuron classification. Journal of Neurophysiology
        121(5), 1831-1847. doi:10.1152/jn.00680.2018
    """
    name = "waveform_spread"
    spacing = _positive_finite(site_spacing_um, "site_spacing_um", name)
    z_max = _positive_finite(outlier_z, "outlier_z", name)
    thr = float(threshold)
    if not (np.isfinite(thr) and 0 <= thr < 1):
        raise ValueError(f"{name}: threshold must be a fraction in [0, 1); got {threshold!r}.")
    for label, value in (("site_step", site_step), ("site_range", site_range)):
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
            raise ValueError(f"{name}: {label} must be an integer; got {value!r}.")
    if site_step < 1 or site_range < 0 or site_range % site_step:
        raise ValueError(
            f"{name}: site_step must be positive and site_range a non-negative multiple of it; "
            f"got site_step={site_step!r}, site_range={site_range!r}."
        )
    w = _mean_waveform(waveform, name)
    peak, amplitudes = _peak_channel(w, name)
    sites = peak + np.arange(-site_range, site_range + 1, site_step)
    sites = sites[(sites > 0) & (sites < w.shape[0])]  # the source's `> 0` drops channel 0
    if sites.size == 0:
        raise ValueError(f"{name}: no site is left once channel 0 is dropped, as the source "
                         "drops it; the waveform needs a channel above 0 within site_range.")
    site_amplitudes = amplitudes[sites]
    carrying = np.flatnonzero(site_amplitudes > thr * site_amplitudes.max())
    if carrying.size > 1:
        deviation = np.abs(carrying - np.median(carrying))
        carrying = carrying[0.6745 * deviation / np.median(deviation) <= z_max]
    return float(carrying.size * spacing)


def waveform_snr(spike_waveforms) -> float:
    """Signal-to-noise ratio of one unit on one channel (Siegle et al. 2021, Methods).

    Input class: the unit's individual spike waveforms on one channel, normally its peak
    channel (`waveform_features`), ``(n_spikes, n_samples)``. The mean waveform is
    subtracted from every spike; the SNR is the mean waveform's amplitude (maximum minus
    minimum) over twice the standard deviation of those residuals, taken over every sample
    of every residual with ``ddof=0`` as the code behind the source computes it. Unitless.
    Residuals from a mean of ``n`` spikes have variance ``(n - 1) / n`` times the noise
    variance, so the SNR is biased high by about ``sqrt(n / (n - 1))``, which matters only at
    small ``n``. Which spikes, and how many, are the caller's choice; the source used 1,000.

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
        The presence ratio: 0 for an empty spike train or one whose spikes all fall outside
        the blocks, since no block holds a spike.

    Raises:
        ValueError: If there is no block, a block is not a finite ``(start, stop)`` pair with
            start before stop (a zero-length block has no time to hold a spike), or a spike
            time is not finite.

    References:
        Siegle, J. H., et al. (2021). Survey of spiking in the mouse visual system reveals
        functional hierarchy. Nature 592, 86-92. doi:10.1038/s41586-020-03171-x
    """
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
    if not np.all(np.isfinite(st)):
        raise ValueError("presence_ratio: spike_times holds a NaN or an infinity.")
    # The half-open count of `fires_in_window`, one binary search per block edge rather than
    # one call per block, which re-validates the whole train each time: O((S + B) log S).
    counts = np.searchsorted(st, b[:, 1], side="left") - np.searchsorted(st, b[:, 0], side="left")
    return float(np.mean(counts > 0))


def isi_cv(spike_times) -> float:
    """Coefficient of variation of the inter-spike intervals (Shinomoto et al. 2009, eq. 1).

    Input class: one unit's spike times in seconds, any order. The CV is the standard
    deviation of the intervals over their mean, unitless. The standard deviation is the
    unbiased one (``ddof=1``), the variance rule of `jnwb.fano_factor`; the ``cv_isi`` of
    `UnitAnalyzer.quality_metrics` is this function. It is 0 for a perfectly regular train and near 1 for a Poisson train.

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
    st = np.asarray(spike_times, dtype=float)
    if st.ndim != 1:
        raise ValueError(f"isi_cv: spike_times must be one 1-D train; got shape {st.shape}.")
    if not np.all(np.isfinite(st)):
        raise ValueError("isi_cv: spike_times holds a NaN or an infinity.")
    if st.size < 3:
        return float("nan")
    isi = np.diff(np.sort(st))
    mean = float(isi.mean())
    if mean == 0:
        return float("nan")
    return float(isi.std(ddof=1) / mean)


def refractory_contamination(spike_times, *, duration_s: float, refractory_ms: float,
                             censored_ms: float) -> Dict[str, Any]:
    """Fraction of a unit's spikes that come from a contaminating source (Hill et al. 2011).

    Input class: one unit's spike times in seconds, any order, from a recording of
    `duration_s` seconds. The estimate assumes stationary firing and contaminating spikes that
    fire independently of the unit's own and violate only the unit's refractory period. With
    ``N`` spikes, refractory period ``tau_R`` (`refractory_ms`), censored period ``tau_C``
    (`censored_ms`), recording duration ``T`` (`duration_s`) and ``r`` violations, the source
    writes the expected count as

        r = 2 (tau_R - tau_C) N^2 (1 - f) f / T          (Hill et al. 2011)

    and ``f`` is its smaller root, ``(1 - sqrt(1 - 2 r T / ((tau_R - tau_C) N^2))) / 2``. A
    violation is an inter-spike interval between consecutive spikes shorter than ``tau_R``;
    an interval within 1 ns of ``tau_R`` counts as equal to it, so spike times on a sample grid
    compare exactly. Llobet et al. (2022) derive the same count (their eq. 1) and root (their
    eq. 4, ``C'``) for a single contaminating unit, with ``T`` less the censored time. For
    contamination from many units or noise they add contaminant-to-contaminant violations and
    use their eq. 3 instead, which gives a lower contamination for the same ``r``; this
    function computes Hill's. The result is unitless, between 0 and 1/2.

    Args:
        spike_times: 1-D spike times in seconds. Duplicate spike times are the caller's to
            remove; each is an interval of 0 and counts as a violation.
        duration_s: Recording duration ``T`` in seconds; required.
        refractory_ms: Refractory period ``tau_R`` in ms; required, larger than `censored_ms`.
        censored_ms: Censored period ``tau_C`` in ms after each detected spike, within which
            the detector cannot report a second one; required, 0 or more.

    Returns:
        Dict with ``contamination`` (``f``), ``n_violations`` (``r``), ``n_spikes`` (``N``)
        and ``reason``. ``contamination`` is NaN, and ``reason`` names why, for an empty
        train, a duration of 0, and when ``2 r T / ((tau_R - tau_C) N^2)`` exceeds 1, so that
        the equation has no real root; ``reason`` is ``None`` otherwise. A NaN drops out of a
        ``nanmean`` over units and fails a ``c < threshold`` check.

    Raises:
        ValueError: If `spike_times` is not 1-D or holds a NaN or an infinity, its span
            exceeds `duration_s`, `duration_s` is negative or not finite, `censored_ms` is
            negative, or `refractory_ms` is not larger than `censored_ms`.

    References:
        Hill, D. N., Mehta, S. B., & Kleinfeld, D. (2011). Quality metrics to accompany spike
        sorting of extracellular signals. Journal of Neuroscience 31(24), 8699-8705.
        doi:10.1523/JNEUROSCI.0971-11.2011

        Llobet, V., Wyngaard, A., & Barbour, B. (2022). Automatic post-processing and merging
        of multiple spike-sorting analyses with Lussac. bioRxiv preprint, version 1.
        doi:10.1101/2022.02.08.479192
    """
    name = "refractory_contamination"
    for label, value in (("duration_s", duration_s), ("refractory_ms", refractory_ms),
                         ("censored_ms", censored_ms)):
        v = float(value)  # a value that is not a number raises here, naming its type
        if not (np.isfinite(v) and v >= 0):
            raise ValueError(f"{name}: {label} must be a finite number, 0 or more; got {value!r}.")
    tau_r, tau_c = float(refractory_ms) / 1000.0, float(censored_ms) / 1000.0
    if not tau_r > tau_c:
        raise ValueError(
            f"{name}: refractory_ms ({refractory_ms!r}) must be larger than censored_ms "
            f"({censored_ms!r}); the window tau_R - tau_C would not be positive."
        )
    st = np.asarray(spike_times, dtype=float)
    if st.ndim != 1:
        raise ValueError(f"{name}: spike_times must be one 1-D train; got shape {st.shape}.")
    if not np.all(np.isfinite(st)):
        raise ValueError(f"{name}: spike_times holds a NaN or an infinity.")
    st = np.sort(st)
    n = int(st.size)
    total = float(duration_s)
    if n and st[-1] - st[0] > total:
        raise ValueError(
            f"{name}: the spikes span {st[-1] - st[0]!r} s, longer than duration_s="
            f"{duration_s!r}."
        )
    result = {"contamination": float("nan"), "n_violations": 0, "n_spikes": n, "reason": None}
    if n == 0:
        result["reason"] = "no spikes: the train carries no unit to measure"
        return result
    n_v = int(np.sum(np.diff(st) < tau_r - _BOUNDARY_TOLERANCE_S))
    result["n_violations"] = n_v
    if total == 0:
        result["reason"] = "the duration T is not positive"
        return result
    discriminant = 1.0 - 2.0 * n_v * total / ((tau_r - tau_c) * n * n)
    if discriminant < 0:
        result["reason"] = (f"2 r T / ((tau_R - tau_C) N^2) = {1.0 - discriminant!r} exceeds 1: "
                            "too many violations for the model, whose equation has no real root")
        return result
    result["contamination"] = 0.5 * (1.0 - float(np.sqrt(discriminant)))
    return result


def amplitude_cutoff(amplitudes, *, num_histogram_bins: int = 500,
                     histogram_smoothing_value: float = 3.0) -> float:
    """Fraction of a unit's spikes missing below the detection threshold, from its amplitudes.

    The form of ``amplitude_cutoff`` in ``ecephys_spike_sorting`` (AllenInstitute,
    ``modules/quality_metrics/metrics.py:712-747`` at commit 919992748a53), after Hill et al.
    (2011). Input class: one unit's spike amplitudes, any unit. It assumes the amplitude
    distribution is symmetric about its mode and that detection cut off its lower tail, so
    the missing lower tail equals the observed upper tail beyond the amplitude whose density
    matches that of the lowest amplitudes; drift breaks the assumption. Steps: a histogram of
    `num_histogram_bins` equal bins over the amplitudes' range, normalized to unit area;
    smoothed by a Gaussian of `histogram_smoothing_value` bins (``scipy.ndimage.gaussian_filter1d``
    with its defaults, reflecting edges and a kernel truncated at 4 standard deviations); from
    its peak bin on, the first bin whose smoothed density is closest to the first bin's; the
    sum of the smoothed density from that bin on, times the bin width. The result is unitless,
    capped at 0.5, the most a symmetric distribution can hide.

    Args:
        amplitudes: 1-D spike amplitudes; at least one, all finite.
        num_histogram_bins: Histogram bins; 500 in the source (line 712).
        histogram_smoothing_value: Standard deviation of the smoothing Gaussian in bins; 3 in
            the source (line 712).

    Returns:
        The missing fraction, between 0 and 0.5.

    Raises:
        ValueError: If `amplitudes` is not 1-D, is empty or holds a NaN or an infinity; if
            `num_histogram_bins` is not an integer of 2 or more (one bin has no width in
            the source); or if
            `histogram_smoothing_value` is not finite and positive.

    References:
        Hill, D. N., Mehta, S. B., & Kleinfeld, D. (2011). Quality metrics to accompany spike
        sorting of extracellular signals. Journal of Neuroscience 31(24), 8699-8705.
        doi:10.1523/JNEUROSCI.0971-11.2011
    """
    from scipy.ndimage import gaussian_filter1d

    name = "amplitude_cutoff"
    if isinstance(num_histogram_bins, bool) or not isinstance(num_histogram_bins, (int, np.integer)) \
            or num_histogram_bins < 2:
        raise ValueError(f"{name}: num_histogram_bins must be an integer of 2 or more; got "
                         f"{num_histogram_bins!r}.")
    sigma = _positive_finite(histogram_smoothing_value, "histogram_smoothing_value", name)
    a = np.asarray(amplitudes, dtype=float)
    if a.ndim != 1 or a.size == 0:
        raise ValueError(f"{name}: amplitudes must be a non-empty 1-D array; got shape {a.shape}.")
    if not np.all(np.isfinite(a)):
        raise ValueError(f"{name}: amplitudes holds {int(np.sum(~np.isfinite(a)))} NaN or "
                         "infinite value(s).")
    density, edges = np.histogram(a, int(num_histogram_bins), density=True)
    smoothed = gaussian_filter1d(density, sigma)
    mode = int(np.argmax(smoothed))
    match = mode + int(np.argmin(np.abs(smoothed[mode:] - smoothed[0])))
    width = float(np.mean(np.diff(edges[:-1])))  # the source's mean step of the left edges
    return float(min(float(np.sum(smoothed[match:])) * width, 0.5))
