"""Decibel formation: ratio to dB, aggregation before the logarithm, relative and band power."""

import warnings
from typing import Optional, Tuple, Union
import numpy as np
from scipy import signal
from .._backend import CPU, resolve_device
from ._common import (
    _require_finite_nonempty_trace,
    _require_two_samples,
    _flat_as_zero,
    _resolve_fs,
)


def _ratio_to_db(ratio):
    """``10*log10(ratio)`` under the caller's floating-point error state.

    :func:`to_db` silences the divide and invalid warnings around it; ``band_power`` calls
    this directly, so a zero band still warns as it did before it shared the conversion.
    """
    return 10.0 * np.log10(ratio)


def to_db(ratio):
    """``10*log10(ratio)`` with divide and invalid warnings silenced — average power, divide
    by baseline, then take the logarithm exactly once.

    The formula itself is :func:`_ratio_to_db`, shared with ``band_power``, which calls it
    directly so a zero band still warns.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        return _ratio_to_db(ratio)


#: Accepted aggregation estimands for :func:`aggregate_to_db`. These are genuinely different
#: estimands, not implementation details, which is why the caller must name one:
#: ``sum_c P_c / sum_c P0_c == sum_c w_c (P_c / P0_c)`` with ``w_c = P0_c / sum_j P0_j`` --
#: i.e. "ratio_of_means" is a baseline-power-weighted average of the very same per-unit ratios
#: that "mean_of_ratios" weights equally. A quiet default would silently pick one for the caller.
DB_AGGREGATIONS = ("mean_of_ratios", "ratio_of_means")

#: Accepted estimand models for :func:`relative_power`.
#: - "mean_of_ratios": Arithmetic mean of per-unit ratios E[P / P0] (equal weighting per unit/channel).
#: - "ratio_of_means": Ratio of aggregated means E[P] / E[P0] (baseline-power-weighted average).
#: - "log_ratio": 10 * log10(P / P0) in decibels (no spatial/trial aggregation, preserving exact ratio-to-dB).
RELATIVE_POWER_MODELS = ("mean_of_ratios", "ratio_of_means", "log_ratio")


def aggregate_to_db(
    power,
    baseline,
    *,
    how: str,
    aggregate_over=None,
    nan_policy: str = "propagate",
):
    """Form a power ratio, aggregate on the RATIO scale, and take ``10*log10`` exactly once.

    This is the enforcing form of :func:`to_db`. ``to_db`` is a bare conversion: it cannot stop
    a caller who already holds decibels from averaging them. Averaging decibels is a Jensen
    error -- ``mean(log x) != log(mean x)`` -- and it biases every unit by its own noisiness,
    which is the failure the "take the logarithm last" rule exists to prevent.
    Stating the rule did not prevent it; this function makes the correct order the only order
    reachable through the API.

    Args:
        power: signal-interval power, ratio-scale and non-negative. Any shape.
        baseline: baseline power for the same units, a scalar or an array with ``power``'s
            number of dimensions that broadcasts against it: a per-frequency baseline for
            ``(n_freqs, n_times)`` power is ``baseline[:, None]``.
        how: which estimand to form, named explicitly -- no default. ``"mean_of_ratios"``
            weights every unit equally; ``"ratio_of_means"`` weights each unit by its own
            baseline power (see :data:`DB_AGGREGATIONS`). Geometric mean is deliberately not
            offered: ``10*log10(geomean(r)) == mean(10*log10(r))`` identically, so it is
            mean-of-decibels -- the defect itself -- under a respectable name.
        aggregate_over: axis or tuple of axes to aggregate the ratios over. ``None`` performs
            no aggregation and simply converts the elementwise ratio, still logging once.
        nan_policy: ``"propagate"`` (default) or ``"omit"`` to aggregate over non-NaN entries
            only. Artifact repair legitimately leaves NaNs behind, so omitting is a real
            choice -- but it is never the silent one.

    Returns:
        Decibel array, reduced along ``aggregate_over``.

    Raises:
        ValueError: if ``how`` or ``nan_policy`` is not recognised, if ``baseline`` is
            neither a scalar nor of ``power``'s number of dimensions (numpy would align a
            shorter one with the trailing axes, which puts a per-frequency baseline on the
            time axis whenever the two counts are equal), if ``baseline`` contains a zero
            or an infinity that reaches a ratio (the ratio would be infinite or 0;
            :func:`relative_power` refuses both) -- under ``nan_policy="omit"`` one where
            ``power`` is NaN is omitted with its cell and not refused -- if a ratio formed
            from finite power, or its mean, overflows to inf (a baseline small enough that
            the ratio overflows), if under ``"ratio_of_means"`` the summed baseline or the
            summed finite power overflows to inf, or if any
            input is negative. The negativity check is the dB-input tripwire: a ratio-scale power is
            non-negative by definition, whereas decibel arrays routinely carry negative
            values, so passing decibels in here fails loudly instead of computing a plausible
            wrong number. It is a guard, not a proof -- an all-positive dB array cannot be
            distinguished from power by inspection, so the contract remains: pass power.
            Also raised for ``how="mean_of_ratios"`` on ``TFRAccumulator`` trial-mean power
            (``power()``, ``mean``, any array sharing their memory -- a view, including one
            through ``memoryview`` or ``as_strided`` -- numpy results and ``tolist()``), which has
            already averaged over trials and so can only give a ratio of means. A copy made
            by ``np.array``, by assignment into another array, or read back from
            ``TFRAccumulator.write`` carries no mark and is not refused. The streaming form of
            this estimand is ``to_db(acc.mean_of_ratios())`` after every trial was added with
            ``add_trial(..., baseline=...)``.

    Example:
        >>> import numpy as np
        >>> p = np.array([[2.0, 4.0], [8.0, 4.0]])   # (units, trials)
        >>> b = np.array([[1.0, 1.0], [2.0, 2.0]])
        >>> float(aggregate_to_db(p, b, how="mean_of_ratios", aggregate_over=None)[0, 0])
        3.0102999566398116
    """
    if how not in DB_AGGREGATIONS:
        if str(how).lower() in ("geometric", "geomean", "geometric_mean"):
            raise ValueError(
                "how='geometric' is deliberately unsupported: 10*log10(geomean(r)) is "
                "identically mean(10*log10(r)), i.e. averaging decibels -- the exact defect "
                f"this function exists to prevent. Choose one of {list(DB_AGGREGATIONS)}."
            )
        raise ValueError(f"how must be one of {list(DB_AGGREGATIONS)}; got {how!r}")
    if nan_policy not in ("propagate", "omit"):
        raise ValueError(f"nan_policy must be 'propagate' or 'omit'; got {nan_policy!r}")

    from ..tfr_accumulator import (
        _is_trial_averaged,
        _refuse_baseline_ndim,
        _refuse_infinite_baseline,
        _refuse_ratio_overflow,
        _refuse_sum_overflow,
    )

    if how == "mean_of_ratios" and any(_is_trial_averaged(arr) for arr in (power, baseline)):
        raise ValueError(
            "how='mean_of_ratios' needs per-trial power, and TFRAccumulator.power() has already "
            "averaged over trials, so a ratio of its output is ratio_of_means whatever `how` "
            "names. Stack per-trial power (abs(tfr.z) ** 2) along a trial axis and pass that "
            "axis as aggregate_over; or stream it: add each trial with "
            "TFRAccumulator.add_trial(z, valid, baseline=...) and take "
            "to_db(acc.mean_of_ratios()); or name how='ratio_of_means'."
        )
    p = np.asarray(power, dtype=float)
    b = np.asarray(baseline, dtype=float)
    _refuse_baseline_ndim(b.ndim, p.ndim, "power")
    for name, arr in (("power", p), ("baseline", b)):
        if arr.size and np.any(arr < 0):
            raise ValueError(
                f"{name} contains negative values, so it is not ratio-scale power. If these "
                "are already decibels, do not aggregate them: pass the underlying power and "
                "baseline and let this function take the logarithm last."
            )
    zero = b == 0
    infinite = np.isinf(b)
    if nan_policy == "omit":
        # A cell whose power is NaN is omitted, so its baseline never reaches a ratio.
        zero = zero & ~np.isnan(p)
        infinite = infinite & ~np.isnan(p)
    if np.any(zero):
        raise ValueError(
            "baseline contains zero values, so the ratio is infinite there; relative_power "
            "refuses the same input. Exclude those units, or set their power to NaN and pass "
            "nan_policy='omit'."
        )
    _refuse_infinite_baseline(infinite)

    mean = np.nanmean if nan_policy == "omit" else np.mean
    total = np.nansum if nan_policy == "omit" else np.sum

    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        if aggregate_over is None or how == "mean_of_ratios":
            _refuse_ratio_overflow(np.isinf(p / b) & np.isfinite(p))
        if aggregate_over is None:
            aggregated = p / b
        elif how == "mean_of_ratios":
            aggregated = mean(p / b, axis=aggregate_over)
            # Finite ratios can still sum past the float64 range inside the mean; an
            # infinite power is the input's and is not an overflow.
            power_inf = np.any(
                np.isinf(np.broadcast_to(p, np.broadcast_shapes(p.shape, b.shape))),
                axis=aggregate_over,
            )
            _refuse_ratio_overflow(np.isposinf(aggregated) & ~power_inf)
        else:
            b_bc = np.broadcast_to(b, p.shape)
            if nan_policy == "omit":
                valid = np.isfinite(p) & np.isfinite(b_bc)
                num = np.sum(np.where(valid, p, 0.0), axis=aggregate_over)
                den = np.sum(np.where(valid, b_bc, 0.0), axis=aggregate_over)
                count = np.sum(valid, axis=aggregate_over)
                aggregated = np.where(count > 0, num / den, np.nan)
            else:
                num = total(p, axis=aggregate_over)
                den = total(b_bc, axis=aggregate_over)
                aggregated = num / den
            # Infinite baselines were refused above and omit drops infinite power, so an
            # infinite sum here is an overflow of finite values -- except a power sum that
            # contains an infinite power under propagate, which is the input's.
            power_inf = (
                np.zeros(np.shape(aggregated), dtype=bool)
                if nan_policy == "omit"
                else np.any(np.isinf(p), axis=aggregate_over)
            )
            _refuse_sum_overflow(np.isposinf(den), "baseline")
            _refuse_sum_overflow(np.isposinf(num) & ~power_inf, "power")
            _refuse_ratio_overflow(np.isposinf(aggregated) & ~power_inf)
        return to_db(aggregated)


def relative_power(
    power: np.ndarray,
    baseline: np.ndarray,
    *,
    model: str = "mean_of_ratios",
    axis: Optional[Union[int, Tuple[int, ...]]] = None,
    device: str = "cpu",
) -> np.ndarray:
    """
    Compute relative power of a signal against baseline under an explicit mathematical estimand.

    Mathematical Estimands:
        - ``"mean_of_ratios"``:
          Computes :math:`\\frac{1}{N} \\sum_{c=1}^{N} \\frac{P_c}{B_c}` across the specified ``axis``.
          Treats every unit/channel with equal weight. Returns linear dimensionless ratio.
        - ``"ratio_of_means"``:
          Computes :math:`\\frac{\\sum_c P_c}{\\sum_c B_c}` across the specified ``axis``.
          Equivalent to a baseline-power-weighted average of per-unit ratios:
          :math:`\\sum_c w_c (P_c / B_c)` where :math:`w_c = B_c / \\sum_j B_j`.
          Returns linear dimensionless ratio.
        - ``"log_ratio"``:
          Computes :math:`10 \\log_{10}(P / B)` elementwise in decibels (dB).
          Preserves the log-last principle without spatial or trial aggregation.

    Important Scientific Invariants:
        - The three models represent mathematically distinct estimands. They coincide only when
          baseline power is strictly identical across the aggregation axis. Under unequal baselines,
          they diverge. The requested model is returned exactly as specified; the library never
          silently converts among them.
        - Preserves linear scale when ``"mean_of_ratios"`` or ``"ratio_of_means"`` is requested.
          Conversion to decibels occurs only when ``model="log_ratio"`` is explicitly chosen,
          preventing premature logarithmic transforms before aggregation (Jensen's inequality).
        - Negative or non-finite inputs, zero baseline values, and mismatched non-broadcastable
          shapes fail loudly by raising :class:`ValueError`.

    Args:
        power: Power array in :math:`(U_{\\text{in}})^2` or :math:`(U_{\\text{in}})^2/\\text{Hz}`.
            Must be finite and strictly non-negative. Any shape.
        baseline: Baseline power array in the same physical units as ``power``, broadcastable against ``power``.
            Must be finite, strictly non-negative, and contain non-zero values where division occurs.
            A scalar or an array with ``power``'s number of dimensions; a per-frequency baseline
            against ``(n_freqs, n_times)`` power is ``baseline[:, None]``. A baseline with fewer
            dimensions aligns with ``power``'s trailing axes: it is broadcast with a
            ``FutureWarning`` this release and raises ``ValueError`` in the next.
        model: Estimand model, strictly one of ``"mean_of_ratios"``, ``"ratio_of_means"``, or ``"log_ratio"``.
            Default is ``"mean_of_ratios"``.
        axis: Axis or tuple of axes to reduce along when using ``"mean_of_ratios"`` or ``"ratio_of_means"``.
            If ``None`` and ``model="mean_of_ratios"``, computes elementwise ratio :math:`P / B` without reduction.
            If ``None`` and ``model="ratio_of_means"``, reduces across all elements (:math:`\\sum P / \\sum B`).
            For ``model="log_ratio"``, ``axis`` must be ``None`` (elementwise dB transform).
        device: ``"cpu"`` (default). ``"cuda"`` and ``"metal"`` are accepted and computed on the
            CPU with a RuntimeWarning: the return is a bare array, which has nowhere to record the
            device that produced it.

    Returns:
        :class:`numpy.ndarray` of relative power values matching broadcast/reduced shape.
        Linear scale (dimensionless) for ``"mean_of_ratios"`` and ``"ratio_of_means"``;
        decibels (:math:`\\text{dB}`) for ``"log_ratio"``.

    Raises:
        ValueError: If ``model`` is unrecognized; if any input is empty; if ``power`` or ``baseline``
            contains negative or non-finite (NaN/Inf) values; if ``baseline`` contains zeros causing
            division by zero; if the ratio or its mean overflows to inf (a baseline small enough that the ratio overflows); if the summed baseline or summed power overflows under ``"ratio_of_means"``; if shapes cannot broadcast; or if ``axis`` is provided with ``model="log_ratio"``.

    Examples:
        >>> import numpy as np
        >>> p = np.array([2.0, 8.0])
        >>> b = np.array([1.0, 2.0])
        >>> # Mean of ratios: (2/1 + 8/2) / 2 = (2 + 4) / 2 = 3.0
        >>> float(relative_power(p, b, model="mean_of_ratios", axis=0))
        3.0
        >>> # Ratio of means: (2 + 8) / (1 + 2) = 10 / 3 = 3.333...
        >>> float(relative_power(p, b, model="ratio_of_means", axis=0))
        3.3333333333333335
        >>> # Log ratio: [10*log10(2), 10*log10(4)] = [3.010..., 6.020...]
        >>> relative_power(p, b, model="log_ratio")
        array([3.01029996, 6.02059991])
    """
    if model not in RELATIVE_POWER_MODELS:
        raise ValueError(f"model must be one of {list(RELATIVE_POWER_MODELS)}; got {model!r}")

    if model == "log_ratio" and axis is not None:
        raise ValueError(
            f"model='log_ratio' computes elementwise decibels without aggregation; "
            f"got axis={axis!r}. For aggregated decibels, use jnwb.aggregate_to_db."
        )

    resolve_device(device, context="relative_power", stacklevel=3, supports=(CPU,))

    p_arr = np.asarray(power, dtype=np.float64)
    b_arr = np.asarray(baseline, dtype=np.float64)

    if p_arr.size == 0 or b_arr.size == 0:
        raise ValueError("power and baseline inputs must not be empty.")

    if not (np.all(np.isfinite(p_arr)) and np.all(np.isfinite(b_arr))):
        raise ValueError("power and baseline inputs must contain finite values (no NaN or Inf).")

    if np.any(p_arr < 0):
        raise ValueError("power contains negative values. Power must be non-negative ratio-scale.")

    if np.any(b_arr < 0):
        raise ValueError("baseline contains negative values. Baseline must be non-negative ratio-scale.")

    # Broadcast check
    try:
        b_broadcast = np.broadcast_to(b_arr, p_arr.shape)
    except ValueError as e:
        raise ValueError(
            f"baseline shape {b_arr.shape} cannot broadcast to power shape {p_arr.shape}."
        ) from e

    from ..tfr_accumulator import _baseline_ndim_problem

    problem = _baseline_ndim_problem(b_arr.ndim, p_arr.ndim, "power")
    if problem is not None:
        warnings.warn(
            f"relative_power: {problem} It is broadcast this release, as before; the next "
            "release raises ValueError, as aggregate_to_db and TFRAccumulator.add_trial do.",
            FutureWarning,
            stacklevel=2,
        )

    if np.any(b_broadcast == 0):
        raise ValueError("baseline contains zero values resulting in division by zero.")

    from ..tfr_accumulator import _refuse_ratio_overflow, _refuse_sum_overflow

    # Inputs are finite here, so an infinite ratio, mean or sum is an overflow.
    with np.errstate(over="ignore"):
        if model == "mean_of_ratios":
            quotient = p_arr / b_broadcast
            _refuse_ratio_overflow(np.isinf(quotient))
            if axis is None:
                return quotient
            averaged = np.mean(quotient, axis=axis)
            _refuse_ratio_overflow(np.isinf(averaged))
            return averaged
        elif model == "ratio_of_means":
            num = np.sum(p_arr, axis=axis)
            den = np.sum(b_broadcast, axis=axis)
            _refuse_sum_overflow(np.isinf(den), "baseline")
            _refuse_sum_overflow(np.isinf(num), "power")
            quotient = num / den
            _refuse_ratio_overflow(np.isinf(quotient))
            return quotient
        else:  # log_ratio
            quotient = p_arr / b_broadcast
            _refuse_ratio_overflow(np.isinf(quotient))
            return to_db(quotient)


def band_power(
    lfp_trace: np.ndarray,
    fs: Optional[float] = None,
    sampling_rate: Optional[float] = None,
    freq_range: Tuple[float, float] = (1.0, 90.0),
    normalize: bool = True,
    baseline: Optional[np.ndarray] = None,
    device: str = 'cpu'
) -> float:
    """
    Mean power spectral density over a frequency band.

    The estimand is ``mean(PSD[f0 <= f <= f1])`` over the Welch bins inside the band --
    a spectral *density*, in input-units^2/Hz, not an integrated power in
    input-units^2. It is therefore independent of the bandwidth: on white noise a 2 Hz
    band and a 30 Hz band return nearly the same value. Two bands of different widths are
    comparable as densities and are *not* comparable as powers; for a power, integrate the
    PSD over the band yourself (``np.trapezoid(psd[mask], freqs[mask])`` from
    ``compute_psd``), which is a larger number by roughly the bandwidth.

    Args:
        lfp_trace: Time series data
        fs: Sampling frequency in Hz (canonical).
        sampling_rate: Supported alias for `fs` in Hz.
        freq_range: (min_freq, max_freq) in Hz, inclusive at both ends
        normalize: If True, return as dB relative to baseline
        baseline: Baseline time series for normalization (optional)
        device: 'cpu' (default). 'cuda' and 'metal' are accepted and computed on the CPU
            with a RuntimeWarning: the return is a bare float, which has nowhere to record
            the device that produced it.

    Returns:
        Mean PSD over the band in input-units^2/Hz, or, with ``normalize=True``,
        ``10 * log10(band / baseline_band)`` in dB -- a ratio of two densities over the
        same band, so the per-Hz normalization cancels. A constant trace, whatever its level,
        has band power 0.0; a constant baseline has no power and raises.

    Raises:
        ValueError: If ``lfp_trace`` (or, with ``normalize=True``, ``baseline``) is empty,
            non-finite or a single sample, ``freq_range`` contains no Welch bin, the
            baseline has no power in ``freq_range``, or ``device`` is not a recognised device name.

    Example:
        >>> theta_power = band_power(lfp_data, fs=1000.0, freq_range=(4, 8), normalize=False)
        >>> baseline_power = band_power(baseline_lfp, fs=1000.0, freq_range=(4, 8), normalize=False)
        >>> normalized_power = band_power(lfp_data, fs=1000.0, freq_range=(4, 8), baseline=baseline_lfp)

    References:
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
        -- the spectrum as the average of windowed periodograms over overlapping segments.
    """
    fs = _resolve_fs(fs, sampling_rate, "band_power")
    lfp_trace = _flat_as_zero(_require_two_samples(
        _require_finite_nonempty_trace(lfp_trace, "band_power"), "band_power"))
    if normalize:
        if baseline is None or np.size(baseline) == 0:
            raise ValueError(
                "band_power(normalize=True) requires a non-empty baseline trace for dB normalization"
            )
        baseline = _flat_as_zero(_require_two_samples(
            _require_finite_nonempty_trace(baseline, "band_power", name="baseline"),
            "band_power", name="baseline"))
    resolve_device(device, context="band_power", stacklevel=3, supports=(CPU,))

    def _welch(trace):
        nperseg = min(len(trace), 4096)
        return signal.welch(trace, fs=fs, nperseg=nperseg)

    frequencies, pxx = _welch(lfp_trace)

    # Extract band
    mask = (frequencies >= freq_range[0]) & (frequencies <= freq_range[1])
    if not np.any(mask):
        raise ValueError(
            f"band_power found no Welch bins in freq_range={freq_range}; "
            f"grid spans [{frequencies[0]:.4g}, {frequencies[-1]:.4g}] Hz"
        )
    band_power_val = float(np.mean(pxx[mask]))

    if normalize:
        # The baseline has its own Welch grid when its length differs from the trace's; the
        # trace's mask applied to it raised IndexError.
        baseline_freqs, baseline_pxx = _welch(baseline)
        baseline_mask = (baseline_freqs >= freq_range[0]) & (baseline_freqs <= freq_range[1])
        if not np.any(baseline_mask):
            raise ValueError(
                f"band_power found no Welch bins of the baseline in freq_range={freq_range}; "
                f"baseline grid spans [{baseline_freqs[0]:.4g}, {baseline_freqs[-1]:.4g}] Hz"
            )
        baseline_power_val = float(np.mean(baseline_pxx[baseline_mask]))
        if not baseline_power_val > 0:
            # This returned the linear power, not a dB value, with no indication.
            raise ValueError(
                "band_power: the baseline has no power in freq_range, so the dB ratio is undefined"
            )
        band_power_val = _ratio_to_db(band_power_val / baseline_power_val)

    return float(band_power_val)
