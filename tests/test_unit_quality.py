"""Waveform and spike-train quality measures recover planted values and refuse undefined input.

Each planted unit comes from a generator below whose receipt derives the expected value of
every measure from the generator's parameters rather than from the waveform, so a test here
compares two independent computations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pytest

import jnwb


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
    return _UnitReceipt(
        waveform=waveform,
        fs=fs,
        channel_positions=pitch * np.arange(n_channels, dtype=float),
        peak_channel=peak_channel,
        amplitude=hi + lo,
        trough_to_peak_ms=(t_hi - t_lo) * 1000.0 / fs,
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


def test_an_inverted_unit_reads_positive_with_the_peak_before_the_trough():
    receipt = synth_unit_waveform(invert=True)
    assert receipt.polarity == 1.0 and receipt.trough_to_peak_ms < 0
    _features_match(receipt)


def test_a_positive_dominant_unit_rises_more_than_it_falls():
    receipt = synth_unit_waveform(trough_amplitude=60.0, peak_amplitude=150.0)
    assert receipt.peak_trough_ratio == 2.5 and receipt.trough_to_peak_ms > 0
    _features_match(receipt)


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


def test_isi_cv_recovers_the_planted_value_and_is_the_quality_metrics_rule():
    # Alternating intervals a, b: mean (a + b) / 2, SD |a - b| / 2, CV |a - b| / (a + b).
    spikes = np.concatenate([[0.0], np.cumsum(np.tile([0.01, 0.03], 20))])  # 40 intervals
    assert jnwb.isi_cv(spikes) == pytest.approx(0.5, rel=1e-9)
    assert jnwb.isi_cv(spikes) == jnwb.UnitAnalyzer.quality_metrics(spikes, 1.0, 1.0)["cv_isi"]


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


def test_refractory_contamination_follows_the_equation_with_censoring():
    # 10000 spikes 100 ms apart plus one 0.8 ms after the first: one violation.
    spikes = np.concatenate([np.arange(10000) * 0.1, [0.0008]])
    n, t_c, t_r_full = spikes.size, 0.0005, 0.001
    total = 1000.0 - 2 * n * t_c                                   # T = T' - 2 N t_c
    expected = 0.5 * (1 - np.sqrt(1 - 2 * 1 * total / (n ** 2 * (t_r_full - t_c))))
    got = jnwb.refractory_contamination(spikes, duration_s=1000.0, refractory_ms=1.0,
                                        censored_ms=0.5)
    assert got["n_violations"] == 1
    assert got["contamination"] == pytest.approx(expected, rel=1e-12)
    # A pair closer than the censored period is not a violation.
    assert jnwb.refractory_contamination(spikes, duration_s=1000.0, refractory_ms=1.0,
                                         censored_ms=0.9)["n_violations"] == 0


# --- undefined input -----------------------------------------------------------------------

def test_one_channel_has_no_spatial_derivative():
    receipt = synth_unit_waveform(n_channels=1, peak_channel=0)
    with pytest.raises(ValueError, match="at least two channels"):
        jnwb.spatial_derivative_sharpness(receipt.waveform, [0.0], threshold=0.01)


def test_no_spikes_is_nan_for_the_spike_train_measures():
    blocks = np.array([[0.0, 1.0], [1.0, 2.0]])
    assert np.isnan(jnwb.presence_ratio(np.zeros(0), blocks))
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
    outside = run([0.0, 0.0005, 10.0, 20.0])          # 2 n_v T / (N^2 t_r) = 12500
    assert np.isnan(outside["contamination"]) and "no real solution" in outside["reason"]
    with pytest.raises(TypeError):
        jnwb.refractory_contamination(np.zeros(3), duration_s=1.0)
    with pytest.raises(ValueError, match="larger than censored_ms"):
        jnwb.refractory_contamination(np.zeros(3), duration_s=1.0, refractory_ms=1.0,
                                      censored_ms=1.0)


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
