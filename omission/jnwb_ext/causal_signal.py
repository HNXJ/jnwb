"""omission.jnwb_ext.causal_signal -- one-sided (causal) LFP band filtering and envelope/power.

P2 of the 2026-08-27 causal SPK-LFP coupling work (Hamm). The 2026-08-27 prepare-phase audit
confirmed every existing filter/Hilbert/TFR pathway in this repo (``band_phase`` in
``omission/scripts/extract_spike_lfp_coupling.py``, ``jnwb.spectral.band_power``,
``jnwb.tfr_accumulator.TFRAccumulator``) is acausal (``scipy.signal.filtfilt`` and/or
``scipy.signal.hilbert``, both whole-signal/zero-phase by construction) -- none of it may be
used for a primary LFP<->SPK directional/lag claim. This module is the minimum causal
replacement, prototyped locally in ``omission`` per Hamm's explicit "prototype here first,
promote to jnwb only after synthetic validation" sequencing.

CAUSAL BY CONSTRUCTION, NOT BY CONVENTION: every function here uses ``scipy.signal.lfilter``
(a direct-form-II transposed one-sided IIR/FIR filter -- output sample y[n] is a function of
x[0..n] and y[0..n-1] ONLY, never x[n+1:]) and a linear-phase FIR design (via ``scipy.signal.
firwin``), never ``filtfilt`` and never ``scipy.signal.hilbert``. The causal amplitude/power
estimator below does NOT use the Hilbert transform at all -- it is bandpass -> rectify ->
causal exponential smoothing (reusing the already-causal, already-validated
``jnwb.onset_fitting.causal_exp_smooth``), a fully one-sided chain by construction, not an
acausal envelope relabeled as causal.

Two distinct latency quantities are reported for every band, and must never be conflated
(per Hamm's explicit instruction):
  - ``group_delay_ms``: the FIR filter's own constant group delay, i.e. how far "behind" the
    filter's output trails its input at each frequency (constant across frequency for a
    linear-phase FIR, unlike an IIR filter's frequency-dependent group delay -- this is why FIR,
    not IIR, was chosen here: a single reportable number per band, not a curve).
  - ``effective_latency_ms``: group_delay_ms PLUS the causal smoothing kernel's own centroid
    delay (from ``causal_exp_smooth``) -- the total lag between a true instantaneous change in
    the underlying signal and this estimator's amplitude/power output reflecting it. For
    theta/alpha in particular this is much larger than one sample period even though the output
    array is sampled every millisecond -- do not infer millisecond temporal precision from the
    sampling rate alone.

Startup transient: the first ``startup_transient_samples`` output samples of any call (no ``zi``
passed) reflect the filter's arbitrary zero initial state, not real filtered signal, and must be
excluded from any windowed analysis that starts near a trial's own onset. ``zi``/``zf`` support
is provided for explicit block-to-block state carry-over across trial boundaries where that is
scientifically appropriate (never carry state ACROSS unrelated trials by default -- each trial
must opt in explicitly).
"""
from __future__ import annotations

from typing import NamedTuple

import numpy as np
from scipy.signal import firwin, lfilter, lfilter_zi

from jnwb.onset_fitting import causal_exp_smooth

BANDS: dict[str, tuple[float, float]] = {
    "theta": (4.0, 8.0),
    "alpha": (8.0, 14.0),
    "beta": (14.0, 30.0),
    "low_gamma": (30.0, 50.0),
    "high_gamma": (50.0, 80.0),
}


class CausalFilterSpec(NamedTuple):
    band: str
    low_hz: float
    high_hz: float
    fs: float
    numtaps: int
    group_delay_ms: float
    startup_transient_samples: int
    startup_transient_ms: float


def _odd(n: int) -> int:
    return n if n % 2 == 1 else n + 1


def recommend_fir_length(low_hz: float, fs: float, n_cycles: float = 3.0) -> int:
    """FIR taps needed to resolve ``n_cycles`` of the band's lowest frequency.

    Standard FIR-bandpass rule of thumb: numtaps ~= n_cycles * fs / low_hz, rounded to the next
    odd integer (odd length -> integer-sample group delay = (numtaps-1)/2, exact, no
    fractional-sample ambiguity). Longer filters have sharper rejection but larger group delay --
    n_cycles=3.0 is a conservative default that trades some frequency selectivity for a shorter,
    more explicitly reportable delay; pass a larger value for sharper band isolation at the cost
    of more latency.
    """
    return _odd(max(int(np.ceil(n_cycles * fs / low_hz)), 3))


def filter_spec(band: str, fs: float, *, n_cycles: float = 3.0, numtaps: int | None = None) -> CausalFilterSpec:
    """Compute (without applying) the causal FIR filter's parameters and documented delay."""
    if band not in BANDS:
        raise ValueError(f"unknown band {band!r}; must be one of {list(BANDS)}")
    low_hz, high_hz = BANDS[band]
    if numtaps is None:
        numtaps = recommend_fir_length(low_hz, fs, n_cycles=n_cycles)
    else:
        numtaps = _odd(numtaps)
    group_delay_samples = (numtaps - 1) / 2.0
    group_delay_ms = group_delay_samples * 1000.0 / fs
    startup_samples = numtaps - 1
    return CausalFilterSpec(
        band=band, low_hz=low_hz, high_hz=high_hz, fs=fs, numtaps=numtaps,
        group_delay_ms=group_delay_ms,
        startup_transient_samples=startup_samples,
        startup_transient_ms=startup_samples * 1000.0 / fs,
    )


def _fir_taps(spec: CausalFilterSpec) -> np.ndarray:
    nyq = spec.fs / 2.0
    return firwin(spec.numtaps, [spec.low_hz / nyq, spec.high_hz / nyq], pass_zero=False)


def causal_bandpass(
    x: np.ndarray,
    fs: float,
    band: str,
    *,
    n_cycles: float = 3.0,
    numtaps: int | None = None,
    zi: np.ndarray | None = None,
    return_state: bool = False,
):
    """One-sided (causal) FIR bandpass. Output[n] depends only on x[0..n], never x[n+1:].

    Args:
        x: (n_times,) or (n_trials, n_times) real-valued LFP trace(s).
        fs: sampling rate, Hz.
        band: one of BANDS' keys.
        n_cycles, numtaps: filter-length control, see ``recommend_fir_length``.
        zi: optional initial filter state (from a prior call's ``zf``, same shape convention as
            ``scipy.signal.lfilter_zi``) for explicit block-to-block continuation WITHIN one
            trial/segment. None (default) starts from the filter's natural steady-state-seeking
            initial condition scaled by the first sample (``lfilter_zi`` scaled by x[...,0]) --
            NOT a hard zero, which would create a larger artificial transient; the first
            ``spec.startup_transient_samples`` are still not to be trusted, but this choice
            minimizes the transient's amplitude for a first call with no prior state.
        return_state: if True, also return the final filter state (for a subsequent call's
            ``zi``) and the ``CausalFilterSpec`` describing the filter actually used.

    Returns:
        filtered array, same shape as ``x``. If ``return_state``: (filtered, zf, spec).
    """
    spec = filter_spec(band, fs, n_cycles=n_cycles, numtaps=numtaps)
    taps = _fir_taps(spec)
    x = np.asarray(x, dtype=float)
    was_1d = x.ndim == 1
    x2 = x[None, :] if was_1d else x

    out = np.empty_like(x2)
    zf_out = np.empty((x2.shape[0], len(taps) - 1), dtype=float)
    zi_base = lfilter_zi(taps, [1.0])
    for i in range(x2.shape[0]):
        this_zi = zi[i] if zi is not None else zi_base * x2[i, 0]
        out[i], zf_out[i] = lfilter(taps, [1.0], x2[i], zi=this_zi)

    filtered = out[0] if was_1d else out
    if not return_state:
        return filtered
    return filtered, zf_out, spec


def causal_envelope(
    x: np.ndarray,
    fs: float,
    band: str,
    *,
    n_cycles: float = 3.0,
    numtaps: int | None = None,
    smoothing_tau_ms: float = 20.0,
    power: bool = True,
) -> tuple[np.ndarray, dict]:
    """Causal amplitude/power envelope: bandpass -> rectify -> causal exponential smoothing.

    Deliberately does NOT use the Hilbert transform (acausal by construction -- see module
    docstring). Chain: (1) ``causal_bandpass`` (one-sided FIR), (2) rectify (square if
    ``power=True`` for instantaneous power, else abs for amplitude), (3)
    ``jnwb.onset_fitting.causal_exp_smooth`` (already-causal, already-validated forward-only
    exponential kernel) to turn the rectified signal into a smooth envelope -- every stage is
    one-sided, so the composition is one-sided.

    Args:
        x, fs, band, n_cycles, numtaps: see ``causal_bandpass``.
        smoothing_tau_ms: exponential-smoothing time constant. This directly trades temporal
            resolution for envelope smoothness -- report it, do not treat the output sampling
            interval as the estimator's true resolution.
        power: True -> instantaneous power (rectify via square); False -> amplitude (rectify via
            abs).

    Returns:
        (envelope, report) where ``report`` has ``spec`` (the ``CausalFilterSpec``),
        ``smoothing_tau_ms``, ``smoothing_centroid_delay_ms`` (the exponential kernel's own
        discrete centroid, computed exactly rather than assumed equal to tau), and
        ``effective_latency_ms`` = group_delay_ms + smoothing_centroid_delay_ms -- the total
        estimator latency, kept explicitly separate from the filter's own group_delay_ms.
    """
    filtered, _, spec = causal_bandpass(x, fs, band, n_cycles=n_cycles, numtaps=numtaps, return_state=True)
    rectified = filtered ** 2 if power else np.abs(filtered)

    was_1d = rectified.ndim == 1
    r2 = rectified[None, :] if was_1d else rectified
    smoothed = np.stack([causal_exp_smooth(r2[i], bin_ms=1000.0 / fs, tau_ms=smoothing_tau_ms) for i in range(r2.shape[0])])
    envelope = smoothed[0] if was_1d else smoothed

    # exact discrete centroid of the causal_exp_smooth kernel, not an assumed value
    t_filter = np.arange(0, 5 * smoothing_tau_ms, 1000.0 / fs)
    if t_filter.size == 0:
        t_filter = np.array([0.0])
    h = np.exp(-t_filter / smoothing_tau_ms)
    h /= h.sum()
    smoothing_centroid_ms = float(np.sum(t_filter * h))

    report = {
        "spec": spec._asdict(),
        "smoothing_tau_ms": smoothing_tau_ms,
        "smoothing_centroid_delay_ms": smoothing_centroid_ms,
        "effective_latency_ms": spec.group_delay_ms + smoothing_centroid_ms,
        "startup_transient_ms": spec.startup_transient_ms,
        "quantity": "power" if power else "amplitude",
    }
    return envelope, report


def causal_filter_bank_report(fs: float, *, bands: dict = BANDS, n_cycles: float = 3.0, smoothing_tau_ms: float = 20.0) -> list[dict]:
    """Per-band table of filter length, group delay, and total effective envelope latency.

    Satisfies the explicit requirement to quantify, PER BAND, the estimator's effective temporal
    resolution/delay before any lag result is interpreted -- theta/alpha in particular will show
    a much larger effective_latency_ms than gamma bands despite identical output sample spacing.
    """
    rows = []
    for band in bands:
        spec = filter_spec(band, fs, n_cycles=n_cycles)
        t_filter = np.arange(0, 5 * smoothing_tau_ms, 1000.0 / fs)
        if t_filter.size == 0:
            t_filter = np.array([0.0])
        h = np.exp(-t_filter / smoothing_tau_ms)
        h /= h.sum()
        smoothing_centroid_ms = float(np.sum(t_filter * h))
        rows.append({
            "band": band, "low_hz": spec.low_hz, "high_hz": spec.high_hz,
            "numtaps": spec.numtaps, "group_delay_ms": spec.group_delay_ms,
            "startup_transient_ms": spec.startup_transient_ms,
            "smoothing_tau_ms": smoothing_tau_ms,
            "smoothing_centroid_delay_ms": smoothing_centroid_ms,
            "effective_latency_ms": spec.group_delay_ms + smoothing_centroid_ms,
        })
    return rows


def packet_response(
    fs: float,
    band: str,
    *,
    n_cycles: float = 3.0,
    numtaps: int | None = None,
    smoothing_tau_ms: float = 20.0,
    onset_ms: float = 500.0,
    total_ms: float = 3000.0,
) -> dict:
    """Empirical step/packet response of the FULL causal_envelope pipeline for one band.

    Rectification makes bandpass->rectify->smooth a NONLINEAR system -- its "impulse response"
    past the linear FIR stage is not a fixed, input-independent quantity the way the filter
    taps are. This function instead measures what actually matters operationally: given a
    band-limited sinusoidal packet that switches ON at ``onset_ms`` (0 amplitude before, unit
    amplitude at the band's center frequency after), how long does the causal_envelope output
    take to rise from 10% to 90% of its new steady state, and where does it peak? This is the
    empirical analogue of a step response for this specific nonlinear estimator, reported
    alongside (never in place of) the linear filter's own analytic group_delay_ms.

    Returns a dict with rise_time_10_90_ms, time_to_90pct_ms (from the true onset_ms, i.e.
    total observed latency including both group delay and smoothing), and the linear-stage
    group_delay_ms/smoothing_centroid_delay_ms for direct side-by-side comparison.
    """
    spec = filter_spec(band, fs, n_cycles=n_cycles, numtaps=numtaps)
    n = int(round(total_ms * fs / 1000.0))
    t_ms = np.arange(n) * 1000.0 / fs
    f0 = (spec.low_hz + spec.high_hz) / 2.0
    x = np.sin(2 * np.pi * f0 * t_ms / 1000.0)
    x[t_ms < onset_ms] = 0.0

    env, report = causal_envelope(x, fs, band, n_cycles=n_cycles, numtaps=numtaps,
                                   smoothing_tau_ms=smoothing_tau_ms, power=False)

    # steady-state reference: mean envelope over the last 20% of the trace (well past onset)
    steady = float(np.mean(env[int(0.8 * n):]))
    onset_idx = int(round(onset_ms * fs / 1000.0))
    post = env[onset_idx:]
    post_t = t_ms[onset_idx:] - onset_ms

    def _cross_time(frac: float) -> float | None:
        target = frac * steady
        above = post >= target
        if not above.any():
            return None
        return float(post_t[np.argmax(above)])

    t10 = _cross_time(0.10)
    t90 = _cross_time(0.90)
    rise_10_90 = (t90 - t10) if (t10 is not None and t90 is not None) else None
    # peak search restricted to a window near onset -- searching the whole post-onset trace
    # picks up abs(sin)'s residual even-harmonic ripple (imperfectly damped by exponential
    # smoothing, worse for slow bands whose ripple period exceeds smoothing_tau_ms) far later in
    # the trace, which is not the onset transient this metric is meant to characterize.
    near_onset_ms = 10 * spec.group_delay_ms + 10 * smoothing_tau_ms
    near_mask = post_t <= near_onset_ms
    search = post[near_mask] if near_mask.any() else post
    search_t = post_t[near_mask] if near_mask.any() else post_t
    peak_t = float(search_t[int(np.argmax(search))])

    return {
        "band": band, "fs": fs, "onset_ms": onset_ms,
        "steady_state_amplitude": steady,
        "time_to_10pct_ms": t10, "time_to_90pct_ms": t90,
        "rise_time_10_90_ms": rise_10_90,
        "time_to_peak_ms": peak_t,
        "group_delay_ms": spec.group_delay_ms,
        "smoothing_centroid_delay_ms": report["smoothing_centroid_delay_ms"],
        "effective_latency_ms": report["effective_latency_ms"],
    }


def temporal_resolution_receipt(
    fs: float,
    *,
    bands: dict = BANDS,
    n_cycles: float = 3.0,
    smoothing_tau_ms: float = 20.0,
) -> list[dict]:
    """The full per-band temporal-resolution receipt (Hamm, 2026-08-27, pre-P4 requirement).

    One row per band with every quantity required before any lag result may be interpreted:
    filter order/taps, sampling rate, passband, causal construction (fixed: one-sided FIR via
    lfilter, never filtfilt/hilbert), nominal group delay, envelope smoothing support/delay,
    total effective latency, an impulse-response summary of the linear FIR stage, its analytic
    step response (cumulative sum of the impulse response, exact for an FIR filter), and the
    empirical packet (step) response of the full nonlinear estimator, plus the startup
    exclusion interval. Two distinct scientific claims this receipt exists to keep apart, per
    Hamm's explicit instruction: causal support (how far back the estimator's memory extends,
    i.e. numtaps/startup_transient_ms) is not the same quantity as group delay (a single
    constant-shift number for a linear-phase FIR), which is not the same quantity as effective
    temporal resolution (how finely two nearby true delays can be told apart -- NOT computed
    here, see the frequency-specific identifiability test), which is not the same as a nominal
    lag reported by a downstream estimator, which is not itself a physiological transmission
    latency claim.
    """
    rows = []
    for band in bands:
        spec = filter_spec(band, fs, n_cycles=n_cycles)
        taps = _fir_taps(spec)
        step_response = np.cumsum(taps)  # exact FIR step response to a DC step
        pkt = packet_response(fs, band, n_cycles=n_cycles, smoothing_tau_ms=smoothing_tau_ms)
        rows.append({
            "band": band, "fs_hz": fs, "passband_hz": [spec.low_hz, spec.high_hz],
            "causal_construction": "one-sided FIR (scipy.signal.lfilter with firwin taps); "
                                    "never filtfilt/hilbert",
            "numtaps": spec.numtaps,
            "impulse_response_summary": {
                "n_taps": len(taps),
                "peak_tap_index": int(np.argmax(np.abs(taps))),
                "peak_tap_time_ms": float(np.argmax(np.abs(taps)) * 1000.0 / fs),
                "energy_centroid_ms": float(np.sum(np.arange(len(taps)) * taps**2) / np.sum(taps**2) * 1000.0 / fs),
            },
            "step_response_summary": {
                "note": "response to a DC step, not the packet onset below -- a bandpass filter "
                        "has ~0 DC gain by construction, so 'final_value' is near-zero and any "
                        "fractional-of-final-value crossing time is not a meaningful resolution "
                        "measure. Reported here only as the transient overshoot/ringing extent; "
                        "use packet_response for the physically relevant onset-response latency.",
                "final_value_dc_gain": float(step_response[-1]),
                "peak_abs_transient_value": float(np.max(np.abs(step_response))),
                "peak_abs_transient_time_ms": float(np.argmax(np.abs(step_response)) * 1000.0 / fs),
            },
            "group_delay_ms": spec.group_delay_ms,
            "startup_transient_samples": spec.startup_transient_samples,
            "startup_transient_ms": spec.startup_transient_ms,
            "smoothing_tau_ms": smoothing_tau_ms,
            "smoothing_centroid_delay_ms": pkt["smoothing_centroid_delay_ms"],
            "effective_latency_ms": pkt["effective_latency_ms"],
            "packet_response": pkt,
        })
    return rows
