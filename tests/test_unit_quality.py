"""Waveform and spike-train quality measures recover planted values and refuse undefined input.

Each planted unit comes from a generator below whose receipt derives the expected value of
every measure from the generator's parameters rather than from the waveform, so a test here
compares two independent computations.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pytest

import jnwb
from jnwb.unit_quality import (amplitude_cutoff, repolarization_slope, waveform_halfwidth,
                               waveform_spread)


# --- planted-unit generators -----------------------------------------------------------------

@dataclass(frozen=True)
class _UnitReceipt:
    waveform: np.ndarray
    fs: float
    channel_positions: np.ndarray
    peak_channel: int
    amplitude: float
    trough_to_peak_ms: float
    peak_trough_ratio: float
    polarity: float
    sharpness: float


def synth_unit_waveform(n_channels=8, n_samples=60, fs=30000.0, *, peak_channel=3,
                        trough_sample=20, peak_sample=32, trough_amplitude=100.0,
                        peak_amplitude=40.0, spatial_decay=0.5, pitch=20.0, invert=False):
    """A mean waveform with known measures, derived from the parameters.

    On the peak channel: a negative unit-width Gaussian of height `trough_amplitude` on
    `trough_sample` plus a positive one of height `peak_amplitude` on `peak_sample`; `invert`
    negates it. Channel ``c`` carries it times ``spatial_decay ** |c - peak_channel|``, the
    channels `pitch` apart. The bumps are at least 8 samples apart, so each extremum is its
    bump's centre to within ``exp(-32)`` of its height.
    """
    assert abs(peak_sample - trough_sample) >= 8 and 0 <= spatial_decay < 1
    n = np.arange(n_samples)
    trace = (-trough_amplitude * np.exp(-0.5 * (n - trough_sample) ** 2)
             + peak_amplitude * np.exp(-0.5 * (n - peak_sample) ** 2))
    scale = spatial_decay ** np.abs(np.arange(n_channels) - peak_channel)
    waveform = (-1.0 if invert else 1.0) * scale[:, None] * trace[None, :]
    if invert:  # the maximum sits on the trough bump and the minimum on the peak bump
        hi, lo, t_hi, t_lo = trough_amplitude, peak_amplitude, trough_sample, peak_sample
    else:
        hi, lo, t_hi, t_lo = peak_amplitude, trough_amplitude, peak_sample, trough_sample
    # The duration runs from the larger extremum (the trough on a tie) to the other one, which
    # the parameters must put after it.
    t_dom, t_opp = (t_hi, t_lo) if hi > lo else (t_lo, t_hi)
    assert t_opp > t_dom
    return _UnitReceipt(
        waveform=waveform,
        fs=fs,
        channel_positions=pitch * np.arange(n_channels, dtype=float),
        peak_channel=peak_channel,
        amplitude=hi + lo,
        trough_to_peak_ms=(t_opp - t_dom) * 1000.0 / fs,
        peak_trough_ratio=hi / lo,
        polarity=float(np.sign(hi - lo)) if hi != lo else float("nan"),
        sharpness=(1.0 - spatial_decay) / pitch,
    )


def synth_unit_spike_waveforms(template, *, noise_rms, n_pairs):
    """``2 * n_pairs`` waveforms ``template +- e_k`` with every sample of ``e_k`` equal to
    ``+-noise_rms``: their mean is `template`, the residual SD is exactly `noise_rms`, and
    the planted SNR is ``(max - min) / (2 * noise_rms)``."""
    n = np.arange(template.size)
    rows = []
    for k in range(n_pairs):
        e = noise_rms * np.where(((n + k) // (k + 1)) % 2 == 0, 1.0, -1.0)
        rows.extend([template + e, template - e])
    return np.asarray(rows), float(template.max() - template.min()) / (2.0 * noise_rms)


def synth_block_train(n_blocks: int, block_s: float, present_blocks: Sequence[int]):
    """Spikes in the middle half of each block of `present_blocks` only; the blocks are
    ``[k * block_s, (k + 1) * block_s)``; the planted ratio is the share of present blocks."""
    starts = block_s * np.arange(n_blocks)
    present = sorted(set(present_blocks))
    spikes = np.concatenate([starts[b] + block_s * np.array([0.25, 0.5, 0.75]) for b in present])
    return spikes, np.column_stack([starts, starts + block_s]), len(present) / n_blocks


def _features_match(receipt):
    got = jnwb.waveform_features(receipt.waveform, receipt.fs)
    assert got["peak_channel"] == receipt.peak_channel
    assert got["amplitude"] == pytest.approx(receipt.amplitude, rel=1e-12)
    assert got["trough_to_peak_ms"] == pytest.approx(receipt.trough_to_peak_ms, rel=1e-12)
    assert got["peak_trough_ratio"] == pytest.approx(receipt.peak_trough_ratio, rel=1e-12)
    assert got["polarity"] == receipt.polarity


# --- planted units -------------------------------------------------------------------------

def test_a_negative_unit_recovers_every_waveform_feature():
    receipt = synth_unit_waveform(peak_channel=5)
    assert receipt.polarity == -1.0 and receipt.trough_to_peak_ms > 0
    _features_match(receipt)


def test_an_inverted_unit_reads_positive_and_its_duration_is_not_signed():
    receipt = synth_unit_waveform(invert=True)
    assert receipt.polarity == 1.0 and receipt.trough_to_peak_ms == pytest.approx(0.4)
    _features_match(receipt)


def test_a_positive_dominant_unit_rises_more_than_it_falls():
    receipt = synth_unit_waveform(trough_amplitude=60.0, peak_amplitude=150.0,
                                  peak_sample=20, trough_sample=32)
    assert receipt.peak_trough_ratio == 2.5 and receipt.trough_to_peak_ms > 0
    _features_match(receipt)


@pytest.mark.parametrize("points, expected_ms", [
    # A small positive bump before the dominant trough: the duration runs from the trough to
    # the maximum after it (sample 20 to 32), not from the earlier global maximum.
    ({5: 30.0, 20: -100.0, 32: 20.0}, 0.4),
    # A dominant peak: from it to the minimum after it (sample 20 to 30), not to the earlier
    # global minimum.
    ({5: -60.0, 20: 150.0, 30: -30.0}, 1.0 / 3.0),
])
def test_the_duration_runs_from_the_dominant_extremum_to_the_opposite_one_after_it(
        points, expected_ms):
    w = np.zeros((1, 60))
    for sample, value in points.items():
        w[0, sample] = value
    got = jnwb.waveform_features(w, 30000.0)["trough_to_peak_ms"]
    assert got == pytest.approx(expected_ms, rel=1e-12)


def test_a_tie_between_peak_and_trough_takes_the_trough_branch():
    # |max| == |min|: Allen's rule runs from the trough (sample 20) to the maximum after it
    # (sample 26), 0.2 ms; the peak branch would run from sample 10 to 20, 1/3 ms.
    w = np.zeros((1, 60))
    w[0, 10], w[0, 20], w[0, 26] = 100.0, -100.0, 50.0
    got = jnwb.waveform_features(w, 30000.0)
    assert np.isnan(got["polarity"])
    assert got["trough_to_peak_ms"] == pytest.approx(0.2, rel=1e-12)


def test_the_peak_channel_is_the_largest_amplitude_not_the_deepest_trough():
    w = np.zeros((2, 20))
    w[0, 5] = -50.0                      # deepest trough, amplitude 50
    w[1, 5], w[1, 12] = -40.0, 30.0      # shallower trough, amplitude 70
    got = jnwb.waveform_features(w, 1000.0)
    assert got["peak_channel"] == 1 and got["amplitude"] == 70.0
    assert got["trough_to_peak_ms"] == 7.0


def test_a_flat_waveform_is_flat_and_a_unit_is_not():
    flat = synth_unit_waveform(trough_amplitude=0.3, peak_amplitude=0.1)
    unit = synth_unit_waveform()
    got = jnwb.waveform_flatness(flat.waveform, threshold=5.0)
    assert got["amplitude"] == pytest.approx(flat.amplitude, rel=1e-12) and got["is_flat"]
    assert not jnwb.waveform_flatness(unit.waveform, threshold=5.0)["is_flat"]
    # The threshold is exclusive, and zero amplitude is flat rather than undefined.
    assert not jnwb.waveform_flatness(unit.waveform, threshold=unit.amplitude)["is_flat"]
    assert jnwb.waveform_flatness(np.zeros((3, 10)), threshold=1.0) == {
        "amplitude": 0.0, "is_flat": True}


def test_spatial_sharpness_recovers_the_planted_fall_off():
    receipt = synth_unit_waveform(spatial_decay=0.25, pitch=25.0)
    got = jnwb.spatial_derivative_sharpness(
        receipt.waveform, receipt.channel_positions, threshold=0.02)
    assert got["sharpness"] == pytest.approx(receipt.sharpness, rel=1e-12)
    assert got["sharpness"] == pytest.approx(0.03, rel=1e-12)
    assert got["is_sharp"] and got["peak_channel"] == receipt.peak_channel
    assert not jnwb.spatial_derivative_sharpness(
        receipt.waveform, receipt.channel_positions, threshold=0.05)["is_sharp"]


def test_spatial_sharpness_averages_unequal_neighbours():
    w = np.zeros((3, 10))
    w[0, 4], w[1, 4], w[2, 4] = -50.0, -100.0, -80.0
    got = jnwb.spatial_derivative_sharpness(w, [0.0, 10.0, 20.0], threshold=1.0)
    assert got["sharpness"] == pytest.approx((0.5 + 0.2) / 2 / 10.0, rel=1e-12)
    assert got["neighbour_channels"].tolist() == [0, 2]


def test_snr_recovers_the_planted_ratio():
    template = synth_unit_waveform().waveform[3]
    waveforms, snr = synth_unit_spike_waveforms(template, noise_rms=7.0, n_pairs=50)
    assert snr == pytest.approx(140.0 / 14.0, rel=1e-12)
    assert jnwb.waveform_snr(waveforms) == pytest.approx(snr, rel=1e-9)


def test_a_unit_absent_from_half_the_blocks_has_presence_one_half():
    spikes, blocks, planted = synth_block_train(10, 30.0, range(5))
    assert planted == 0.5
    assert jnwb.presence_ratio(spikes, blocks) == planted
    # Blocks are half-open, as in `fires_in_window`: a spike on a block's stop is outside it.
    assert jnwb.presence_ratio(np.array([30.0]), blocks) == 0.1


def test_presence_is_the_fires_in_window_rule_block_by_block():
    rng = np.random.default_rng(3)
    spikes = np.sort(np.concatenate([rng.uniform(0.0, 50.0, 40), [10.0, 20.0, 30.0]]))
    edges = np.sort(np.concatenate([rng.uniform(0.0, 60.0, 30), [10.0, 20.0, 30.0]]))
    for start, stop in zip(edges[:-1], edges[1:]):
        if stop > start:
            expected = jnwb.fires_in_window(spikes, start, (0.0, (stop - start) * 1000.0))
            assert jnwb.presence_ratio(spikes, [[start, stop]]) == float(expected)


def test_isi_cv_recovers_the_planted_value_with_the_unbiased_variance():
    # Alternating intervals a, b: mean (a + b) / 2 and sum of squared deviations
    # n (a - b)^2 / 4, so with ddof=1 the CV is |a - b| / (a + b) * sqrt(n / (n - 1)).
    spikes = np.concatenate([[0.0], np.cumsum(np.tile([0.01, 0.03], 20))])  # 40 intervals
    assert jnwb.isi_cv(spikes) == pytest.approx(0.5 * np.sqrt(40 / 39), rel=1e-9)
    # Three spikes, intervals 1 and 3: SD sqrt(2) with ddof=1, mean 2.
    assert jnwb.isi_cv(np.array([0.0, 1.0, 4.0])) == pytest.approx(np.sqrt(2) / 2, rel=1e-12)


def _dead_time_train(rng, rate_hz, dead_s, duration_s):
    """A renewal train whose intervals are `dead_s` plus an exponential: no interval is
    shorter than `dead_s`, so the train never violates a refractory period up to it."""
    n = int(rate_hz * duration_s * 1.5) + 100
    isi = dead_s + rng.exponential(1.0 / rate_hz - dead_s, n)
    t = np.cumsum(isi)
    return t[t < duration_s]


def test_refractory_contamination_recovers_a_planted_fraction():
    rng = np.random.default_rng(13)
    duration = 2000.0
    true = _dead_time_train(rng, 20.0, 0.002, duration)
    contaminant = _dead_time_train(rng, 4.0, 0.002, duration)
    planted = contaminant.size / (true.size + contaminant.size)
    assert true.size > 35000 and contaminant.size > 7000
    got = jnwb.refractory_contamination(np.concatenate([true, contaminant]), duration_s=duration,
                                        refractory_ms=1.5, censored_ms=0.0)
    assert got["reason"] is None and got["n_violations"] > 300
    assert got["contamination"] == pytest.approx(planted, rel=0.1)
    clean = jnwb.refractory_contamination(true, duration_s=duration, refractory_ms=1.5,
                                          censored_ms=0.0)
    assert clean["n_violations"] == 0 and clean["contamination"] == 0.0


def test_refractory_contamination_reproduces_the_worked_example_of_the_source():
    # Hill et al. 2011: N/T = 10 Hz, tau_R = 3 ms, tau_C = 1 ms, T = 1000 s and r = 20
    # violations give f = 0.05. Here 10000 spikes 100 ms apart, 20 of them moved to 2 ms after
    # the spike before them.
    spikes = np.arange(10000) * 0.1
    spikes[1:41:2] = spikes[0:40:2] + 0.002
    got = jnwb.refractory_contamination(spikes, duration_s=1000.0, refractory_ms=3.0,
                                        censored_ms=1.0)
    assert got["n_spikes"] == 10000 and got["n_violations"] == 20 and got["reason"] is None
    # r = 2 (tau_R - tau_C) N^2 (1 - f) f / T solved for its smaller root.
    assert got["contamination"] == pytest.approx((1 - np.sqrt(0.8)) / 2, rel=1e-12)
    assert round(got["contamination"], 2) == 0.05


def test_refractory_violations_are_consecutive_intervals():
    # A burst of three spikes 0.5 ms apart holds two short intervals, not three short pairs.
    spikes = np.array([1.0, 1.0005, 1.001, 5.0, 9.0])
    got = jnwb.refractory_contamination(spikes, duration_s=10.0, refractory_ms=2.0,
                                        censored_ms=0.0)
    assert got["n_violations"] == 2


def test_spike_times_on_a_sample_grid_compare_exactly_with_the_refractory_period():
    # Pairs 1 s apart at 30 kHz, the second spike 30 samples (1 ms) or 60 samples (2 ms)
    # after the first. With a 2 ms refractory period the 1 ms intervals are all violations
    # and the 2 ms intervals, equal to the period rather than shorter, are none.
    fs, first = 30000.0, np.arange(1, 801) * 30000 + 7
    for gap, expected in ((30, 800), (59, 800), (60, 0)):
        spikes = np.sort(np.concatenate([first, first + gap])) / fs
        got = jnwb.refractory_contamination(spikes, duration_s=1000.0, refractory_ms=2.0,
                                            censored_ms=1.0)
        assert got["n_violations"] == expected, gap


# --- undefined input -----------------------------------------------------------------------

def test_one_channel_has_no_spatial_derivative():
    receipt = synth_unit_waveform(n_channels=1, peak_channel=0)
    with pytest.raises(ValueError, match="at least two channels"):
        jnwb.spatial_derivative_sharpness(receipt.waveform, [0.0], threshold=0.01)


def test_no_spikes_is_absent_from_every_block_and_has_no_isi_cv():
    blocks = np.array([[0.0, 1.0], [1.0, 2.0]])
    assert jnwb.presence_ratio(np.zeros(0), blocks) == 0.0
    assert np.isnan(jnwb.isi_cv(np.zeros(0)))
    assert np.isnan(jnwb.isi_cv(np.array([0.1, 0.2])))


def test_refractory_contamination_undefined_input_is_nan_with_a_reason():
    def run(spikes, duration=100.0):
        return jnwb.refractory_contamination(np.asarray(spikes, dtype=float),
                                             duration_s=duration, refractory_ms=1.0,
                                             censored_ms=0.0)
    empty = run([])
    assert np.isnan(empty["contamination"]) and "no spikes" in empty["reason"]
    zero = run([0.0], duration=0.0)
    assert np.isnan(zero["contamination"]) and "not positive" in zero["reason"]
    outside = run([0.0, 0.0005, 10.0, 20.0])          # 2 r T / ((tau_R - tau_C) N^2) = 12500
    assert np.isnan(outside["contamination"]) and "no real root" in outside["reason"]
    with pytest.raises(TypeError):
        jnwb.refractory_contamination(np.zeros(3), duration_s=1.0)
    with pytest.raises(ValueError, match="larger than censored_ms"):
        jnwb.refractory_contamination(np.zeros(3), duration_s=1.0, refractory_ms=1.0,
                                      censored_ms=1.0)


def test_one_or_two_spikes_give_no_contamination_estimate():
    # One or two spikes leave at most one interval: there is no estimate, so the result is NaN
    # with a reason, not the 0.0 that an interval-free train gives. Three spikes are estimable.
    def run(spikes):
        return jnwb.refractory_contamination(np.asarray(spikes, dtype=float), duration_s=10.0,
                                             refractory_ms=2.0, censored_ms=0.0)
    for spikes in ([1.0], [1.0, 5.0]):
        assert len(spikes) < 3, "fixture must hold fewer than three spikes"
        got = run(spikes)
        assert got["n_spikes"] == len(spikes)
        assert np.isnan(got["contamination"]) and "fewer than three" in got["reason"], got
    three = run([1.0, 5.0, 9.0])
    assert three["contamination"] == 0.0 and three["reason"] is None


def test_a_zero_length_block_is_refused():
    with pytest.raises(ValueError, match="zero-length block"):
        jnwb.presence_ratio(np.array([0.5]), np.array([[0.0, 1.0], [1.0, 1.0]]))


def test_a_zero_noise_estimate_is_nan_not_an_snr():
    template = synth_unit_waveform().waveform[3]
    assert np.isnan(jnwb.waveform_snr(template[None, :]))


def test_a_waveform_without_amplitude_has_no_peak_channel():
    with pytest.raises(ValueError, match="no peak channel"):
        jnwb.waveform_features(np.zeros((4, 10)), 30000.0)
    with pytest.raises(ValueError, match="no peak channel"):
        jnwb.spatial_derivative_sharpness(np.zeros((4, 10)), np.arange(4.0), threshold=0.1)


def test_a_ratio_without_a_trough_and_a_polarity_tie_are_nan():
    no_trough = np.zeros((1, 10))
    no_trough[0, 3] = 5.0
    assert np.isnan(jnwb.waveform_features(no_trough, 1000.0)["peak_trough_ratio"])
    tie = np.zeros((1, 10))
    tie[0, 2], tie[0, 6] = -5.0, 5.0
    assert np.isnan(jnwb.waveform_features(tie, 1000.0)["polarity"])


@pytest.mark.parametrize("func", [jnwb.waveform_flatness, jnwb.spatial_derivative_sharpness])
def test_the_threshold_is_required_and_must_be_positive(func):
    args = (np.ones((2, 4)),) if func is jnwb.waveform_flatness else (np.ones((2, 4)), [0, 1])
    with pytest.raises(TypeError):
        func(*args)
    with pytest.raises(ValueError, match="threshold"):
        func(*args, threshold=0.0)


# --- half-width, repolarization slope and spread, in the form of ecephys_spike_sorting ----------

def _interval_ms(n_samples, m, fs):
    """The interval of ``linspace(0, n_samples / fs, m)`` in ms, the source's time axis."""
    return n_samples * 1000.0 / (fs * (m - 1))


def _trough_trace(n_samples, points):
    trace = np.zeros(n_samples)
    for sample, value in points.items():
        trace[sample] = value
    return trace


#: A trough at sample 10 with half level -50: the first sample before it below -50 is 9 and
#: the first from it on above -50 is 12, three intervals.
_HALF_WIDTH_POINTS = {8: -20.0, 9: -60.0, 10: -100.0, 11: -70.0, 12: -40.0, 13: -10.0}


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_half_width_counts_the_samples_beyond_half_the_extremum(sign):
    trace = sign * _trough_trace(30, _HALF_WIDTH_POINTS)
    assert int(np.argmax(np.abs(trace))) == 10 and np.abs(trace).max() == 100.0
    got = waveform_halfwidth(trace[None, :], 10000.0, upsampling_factor=1)
    # The source's axis linspace(0, 30 / fs, 30) has an interval of 30 / (fs * 29).
    np.testing.assert_allclose(got, 3 * _interval_ms(30, 30, 10000.0), rtol=1e-12)


def test_half_width_starts_at_the_first_sample_beyond_half_not_the_last_crossing():
    # An earlier excursion below the half level at sample 3 starts the width there, as the
    # source's `np.min(np.where(...))` does: 9 intervals, not 3.
    trace = _trough_trace(30, {**_HALF_WIDTH_POINTS, 3: -55.0})
    assert trace[3] < 0.5 * trace.min() and trace[4:9].max() > 0.5 * trace.min()
    got = waveform_halfwidth(trace[None, :], 10000.0, upsampling_factor=1)
    np.testing.assert_allclose(got, 9 * _interval_ms(30, 30, 10000.0), rtol=1e-12)


def test_half_width_on_a_tie_measures_the_trough():
    # max == |min|: the source measures the trough (2 intervals, samples 14 to 16), not the
    # peak (4 intervals, samples 4 to 8).
    trace = _trough_trace(30, {4: 60.0, 5: 100.0, 6: 70.0, 7: 60.0, 8: 40.0,
                               14: -60.0, 15: -100.0, 16: -40.0})
    assert trace.max() == -trace.min()
    got = waveform_halfwidth(trace[None, :], 10000.0, upsampling_factor=1)
    np.testing.assert_allclose(got, 2 * _interval_ms(30, 30, 10000.0), rtol=1e-12)


def test_half_width_on_the_default_resampling_matches_the_resampled_cosine():
    # -c + A cos(2 pi n / N) is one Fourier component plus a constant, so resampling it to M
    # samples gives -c + A cos(2 pi m / M) exactly. Its trough (m = M/2) is the extremum, with
    # half level -(A + c)/2, crossed where cos = (c - A) / (2 A), at phases alpha and
    # 2 pi - alpha: the width runs from sample floor(M alpha / 2 pi) + 1 to
    # floor(M (1 - alpha / 2 pi)) + 1, at the source's interval N / (fs (M - 1)).
    n, fs, a, c = 82, 30000.0, 1.0, 0.2
    m = int(n * 200 / 82)
    assert m == 200
    trace = -c + a * np.cos(2 * np.pi * np.arange(n) / n)
    assert -trace.min() > trace.max()
    edge = m * np.arccos((c - a) / (2 * a)) / (2 * np.pi)
    # Neither crossing is within 1e-3 of a sample, so rounding cannot move it.
    assert min(edge % 1, 1 - edge % 1, (m - edge) % 1, 1 - (m - edge) % 1) > 1e-3
    first, last = int(np.floor(edge)) + 1, int(np.floor(m - edge)) + 1
    assert (first, last) == (64, 137)
    got = waveform_halfwidth(trace[None, :], fs)
    np.testing.assert_allclose(got, (last - first) * _interval_ms(n, m, fs), rtol=1e-12)


def test_half_width_is_nan_without_a_sample_before_the_extremum_and_refuses_bad_input():
    trace = _trough_trace(30, {0: -100.0, 1: -60.0, 2: -20.0})
    assert int(np.argmin(trace)) == 0
    assert np.isnan(waveform_halfwidth(trace[None, :], 10000.0, upsampling_factor=1))
    with pytest.raises(ValueError, match="upsampling_factor"):
        waveform_halfwidth(trace[None, :], 10000.0, upsampling_factor=0.5)
    with pytest.raises(ValueError, match="fs"):
        waveform_halfwidth(trace[None, :], 0.0)


def _repolarizing_trace():
    """A trough of -100 at sample 10 rising 5 per sample for the 20 samples of the source's
    window, then flat at -5, so a window of any other length fits a different line."""
    trace = np.full(40, -5.0)
    trace[:10] = 0.0
    trace[10:30] = -100.0 + 5.0 * np.arange(20)
    return trace


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_repolarization_slope_is_the_line_through_the_window_after_the_extremum(sign):
    trace = sign * _repolarizing_trace()
    assert int(np.argmax(np.abs(trace))) == 10 and trace[29] == sign * -5.0
    got = repolarization_slope(trace[None, :], 20000.0, upsampling_factor=1)
    # 5 per interval of the source's axis, 40 / (20 kHz * 39), is 97.5 per ms, positive for a
    # trough and for a peak alike.
    expected = 5.0 / _interval_ms(40, 40, 20000.0)
    assert expected == pytest.approx(97.5, rel=1e-12)
    np.testing.assert_allclose(got, expected, rtol=1e-12)
    shorter = repolarization_slope(trace[None, :], 20000.0, upsampling_factor=1, window_samples=5)
    np.testing.assert_allclose(shorter, expected, rtol=1e-12)
    assert repolarization_slope(trace[None, :], 20000.0, upsampling_factor=1,
                                window_samples=25) < expected


def test_repolarization_slope_is_nan_at_the_last_sample_and_refuses_a_bad_window():
    trace = np.zeros(10)
    trace[-1] = -50.0
    assert int(np.argmax(np.abs(trace))) == trace.size - 1
    assert np.isnan(repolarization_slope(trace[None, :], 1000.0, upsampling_factor=1))
    for window in (1, 2.5, True):
        with pytest.raises(ValueError, match="window_samples"):
            repolarization_slope(trace[None, :], 1000.0, window_samples=window)


def _spread_waveform(amplitudes):
    """Channel c carries amplitude ``amplitudes[c]``: -a on sample 5, 0 elsewhere."""
    w = np.zeros((len(amplitudes), 12))
    w[:, 5] = -np.asarray(amplitudes, dtype=float)
    return w


def test_spread_counts_the_sites_above_twelve_percent_and_drops_an_outlier():
    # Sites are every second channel within 16 of the peak (20): 4, 6, ..., 36. Above 12 of
    # 100: 16 (13), 18, 20, 22 and 36 (30); 24 (12) is not above it, odd channels are not
    # sites. Site 36, at position 16 among the sites against a median of 8 and a median
    # absolute deviation of 1, has modified z 0.6745 * 8 > 1.5 and is dropped; site 16 has
    # 0.6745 * 2 <= 1.5 and stays. Four sites at 20 um.
    amp = np.full(40, 5.0)
    amp[[16, 18, 20, 22, 24, 36]] = [13.0, 50.0, 100.0, 50.0, 12.0, 30.0]
    amp[[19, 21]] = 90.0
    w = _spread_waveform(amp)
    assert jnwb.waveform_features(w, 30000.0)["peak_channel"] == 20
    np.testing.assert_allclose(waveform_spread(w, site_spacing_um=20.0), 80.0, rtol=1e-12)
    np.testing.assert_allclose(waveform_spread(w, site_spacing_um=20.0, outlier_z=10.0), 100.0,
                               rtol=1e-12)
    # A site whose modified z equals outlier_z is kept (`<=`, `isnot_outlier`).
    np.testing.assert_allclose(waveform_spread(w, site_spacing_um=20.0, outlier_z=0.6745 * 2.0),
                               80.0, rtol=1e-12)


def test_spread_drops_channel_zero_as_the_source_does():
    # The source's `sites_to_sample > 0` leaves channel 0 out though it carries the unit: of
    # channels 0, 2 and 4 only 2 and 4 count.
    amp = np.full(10, 1.0)
    amp[[0, 2, 4]] = [60.0, 100.0, 60.0]
    w = _spread_waveform(amp)
    assert jnwb.waveform_features(w, 30000.0)["peak_channel"] == 2
    np.testing.assert_allclose(waveform_spread(w, site_spacing_um=20.0), 40.0, rtol=1e-12)
    # A peak on channel 0 is dropped too; the threshold is then 12 % of the largest site left
    # (60 on channel 2), so channel 4 at 30 counts and channel 6 at 7 does not.
    amp = np.full(10, 1.0)
    amp[[0, 2, 4, 6]] = [100.0, 60.0, 30.0, 7.0]
    w = _spread_waveform(amp)
    assert jnwb.waveform_features(w, 30000.0)["peak_channel"] == 0 and 7.0 < 0.12 * 60.0
    np.testing.assert_allclose(waveform_spread(w, site_spacing_um=20.0), 40.0, rtol=1e-12)
    with pytest.raises(ValueError, match="channel 0"):
        waveform_spread(_spread_waveform([100.0]), site_spacing_um=20.0)


def test_spread_refuses_bad_geometry():
    w = _spread_waveform([10.0, 100.0, 10.0])
    with pytest.raises(TypeError):
        waveform_spread(w)
    with pytest.raises(ValueError, match="site_range"):
        waveform_spread(w, site_spacing_um=20.0, site_range=15)
    with pytest.raises(ValueError, match="threshold"):
        waveform_spread(w, site_spacing_um=20.0, threshold=1.0)
    with pytest.raises(ValueError, match="site_spacing_um"):
        waveform_spread(w, site_spacing_um=float("nan"))


def test_spread_takes_its_outlier_z_from_the_modified_z_owner():
    assert "_modified_z(deviation) <= z_max" in inspect.getsource(waveform_spread)


def test_waveform_spread_keeps_its_outlier_filter_on_a_fixed_input():
    amps = np.zeros(40)
    amps[18:23] = 1.0
    amps[34] = 0.5
    amps[27] = 0.4
    wave = np.outer(amps, np.linspace(0.0, 1.0, 30))
    wave = wave + 0.001 * np.random.default_rng(8).normal(size=wave.shape)
    np.testing.assert_allclose(waveform_spread(wave, site_spacing_um=25.0), 75.0, rtol=1e-12)
    np.testing.assert_allclose(waveform_spread(wave, site_spacing_um=25.0, outlier_z=1e9),
                               100.0, rtol=1e-12)
    np.testing.assert_allclose(waveform_spread(wave, site_spacing_um=25.0, outlier_z=0.5),
                               50.0, rtol=1e-12)


@pytest.mark.parametrize("call", [
    lambda w: waveform_halfwidth(w, 30000.0),
    lambda w: repolarization_slope(w, 30000.0),
    lambda w: waveform_spread(w, site_spacing_um=20.0),
])
def test_a_waveform_with_a_nan_sample_is_refused(call):
    w = _spread_waveform([10.0, 100.0, 10.0])
    w[0, 3] = np.nan
    assert np.isnan(w).sum() == 1
    with pytest.raises(ValueError, match="NaN"):
        call(w)


# --- agreement with ecephys_spike_sorting at 919992748a53 ----------------------------------------

def _allen_case_waveform():
    """24 channels of 82 samples at 30 kHz, peak channel 6, falling off by 0.8 per channel."""
    t = np.arange(82)
    trace = (-100.0 * np.exp(-0.5 * ((t - 30) / 2.0) ** 2)
             + 35.0 * np.exp(-0.5 * ((t - 42) / 4.0) ** 2))
    return np.array([0.8 ** abs(c - 6) * trace for c in range(24)])


def _allen_case_amplitudes():
    """The 4000 quantiles of N(100, 10), with every amplitude at or below 90 left out."""
    from statistics import NormalDist

    q = NormalDist(100.0, 10.0)
    full = np.array([q.inv_cdf((i + 0.5) / 4000) for i in range(4000)])
    return full[full > 90.0]


def test_the_waveform_measures_reproduce_the_source_on_a_fixed_unit():
    # The expected values are the source's own: `calculate_waveform_halfwidth`,
    # `calculate_waveform_repolarization_slope` (V/s from µV) and `calculate_2D_features`
    # (spread_threshold 0.12, site_range 16, site_spacing 20e-6 m) of
    # modules/mean_waveforms/waveform_metrics.py at commit 919992748a53, run on this waveform
    # resampled by 200/82 with peak channel 6 on 2026-10-11.
    w = _allen_case_waveform()
    assert jnwb.waveform_features(w, 30000.0)["peak_channel"] == 6
    np.testing.assert_allclose(waveform_halfwidth(w, 30000.0), 0.15108877721943048, rtol=1e-12)
    np.testing.assert_allclose(repolarization_slope(w, 30000.0) * 1e-3, 0.5064552069143894,
                               rtol=1e-12)
    np.testing.assert_allclose(waveform_spread(w, site_spacing_um=20.0), 140.00000000000003,
                               rtol=1e-12)


def test_the_amplitude_cutoff_reproduces_the_source_on_fixed_amplitudes():
    # `amplitude_cutoff` of modules/quality_metrics/metrics.py at commit 919992748a53 (500 bins,
    # smoothing 3) gives 0.20362567401249895 on these amplitudes. The fraction beyond the mirror
    # of the cut, P(X > 110) / P(X > 90) = 0.1587 / 0.8413 = 0.189, is what the symmetric
    # model estimates; the histogram and smoothing put it within 0.02 of that.
    amplitudes = _allen_case_amplitudes()
    assert amplitudes.size == 3365 and amplitudes.min() > 90.0
    got = amplitude_cutoff(amplitudes)
    np.testing.assert_allclose(got, 0.20362567401249895, rtol=1e-12)
    from statistics import NormalDist
    q = NormalDist(100.0, 10.0)
    assert abs(got - (1 - q.cdf(110.0)) / (1 - q.cdf(90.0))) < 0.02


def test_the_amplitude_cutoff_is_capped_at_one_half():
    # With the lowest bin the mode, the bin matching the lowest bin's density is the lowest
    # bin itself, so the sum covers the whole distribution (1) and the cap returns 0.5.
    amplitudes = np.array([0.0, 0.0, 0.0, 1.0])
    density, _ = np.histogram(amplitudes, 2, density=True)
    assert density[0] > density[1]
    assert amplitude_cutoff(amplitudes, num_histogram_bins=2) == 0.5


def test_the_amplitude_cutoff_refuses_undefined_input():
    for bad in (np.array([]), np.array([1.0, np.nan]), np.ones((2, 2))):
        with pytest.raises(ValueError, match="amplitudes"):
            amplitude_cutoff(bad)
    with pytest.raises(ValueError, match="num_histogram_bins"):
        amplitude_cutoff(np.arange(10.0), num_histogram_bins=1)
    with pytest.raises(ValueError, match="histogram_smoothing_value"):
        amplitude_cutoff(np.arange(10.0), histogram_smoothing_value=0.0)
