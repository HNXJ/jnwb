import numpy as np

from jnwb.spiking import (
    compute_response_metrics,
    classify_response_significance,
    phase_locking_index,
)
from omission.jnwb_ext.spiking import classify_omission_response


def test_compute_response_metrics_known_rates():
    # Deterministic construction: exactly 2 spikes per trial in baseline
    # (-0.25, -0.05) and exactly 6 spikes per trial in response (0.0, 0.15),
    # across 20 trials at 1-second spacing, so per-trial windows never overlap.
    epoch_onsets = np.arange(20) * 1.0
    spike_times = []
    for onset in epoch_onsets:
        spike_times += [onset - 0.20, onset - 0.10]  # 2 baseline spikes
        spike_times += [onset + 0.02, onset + 0.05, onset + 0.07, onset + 0.09, onset + 0.11, onset + 0.13]  # 6 response spikes
    spike_times = np.array(spike_times)

    metrics = compute_response_metrics(spike_times, epoch_onsets)

    baseline_duration = 0.25 - 0.05
    response_duration = 0.15 - 0.0
    expected_baseline_rate = 2 / baseline_duration
    expected_response_rate = 6 / response_duration

    assert metrics["n_trials"] == 20
    assert metrics["response_count"] == 20 * 6
    assert np.isclose(metrics["baseline_rate"], expected_baseline_rate)
    assert np.isclose(metrics["response_rate"], expected_response_rate)
    # Every trial has an identical count -> zero within-condition variance ->
    # baseline_std == 0 -> z-score left at its 0.0 default (guarded, not a crash).
    assert metrics["response_zscore"] == 0.0
    # First response spike is 0.02s after response window start on every trial
    assert np.isclose(metrics["latency"], 0.02)


def test_compute_response_metrics_empty_inputs_returns_zeroed_defaults():
    metrics = compute_response_metrics(np.array([]), np.array([]))
    assert metrics["baseline_rate"] == 0.0
    assert metrics["response_rate"] == 0.0
    assert metrics["response_count"] == 0
    assert metrics["latency"] is None


def test_classify_response_significance_thresholds():
    strong = {"response_count": 10, "response_zscore": 4.0}
    result = classify_response_significance(strong)
    assert result["is_significant"] is True
    assert result["confidence"] == "high"

    weak = {"response_count": 10, "response_zscore": 0.5}
    result = classify_response_significance(weak)
    assert result["is_significant"] is False

    too_few_spikes = {"response_count": 2, "response_zscore": 5.0}
    result = classify_response_significance(too_few_spikes, min_spike_count=5)
    assert result["is_significant"] is False
    assert result["confidence"] == "low"


def test_classify_omission_response_detects_stimulus_vs_omission_difference():
    rng = np.random.default_rng(42)
    response_window = (0.0, 0.150)

    # Stimulus trials: strong, consistent response (5-9 spikes/trial in-window)
    stimulus_onsets = np.arange(30) * 1.0
    # Omission trials: weak/no response (0-1 spikes/trial in-window)
    omission_onsets = np.arange(30) * 1.0 + 500.0

    spikes = []
    for onset in stimulus_onsets:
        n_spikes = rng.integers(5, 10)
        spikes += list(onset + rng.uniform(0.01, 0.14, n_spikes))
    for onset in omission_onsets:
        n_spikes = rng.integers(0, 2)
        spikes += list(onset + rng.uniform(0.01, 0.14, n_spikes))
    spikes = np.array(sorted(spikes))

    result = classify_omission_response(spikes, stimulus_onsets, omission_onsets, response_window)

    assert result["stimulus_rate"] > result["omission_rate"]
    # sig_s/sig_o are numpy.bool_, not python bool - assert truthiness, not identity
    assert bool(result["sig_s"]) is True
    assert result["pvalue_stimulus"] < 0.05


def test_phase_locking_index_perfectly_locked_vs_uniform():
    lfp_timestamps = np.linspace(0, 10, 10000)
    lfp_phase = np.mod(lfp_timestamps * 2 * np.pi * 8, 2 * np.pi) - np.pi  # 8 Hz sawtooth phase

    # Spikes placed exactly where phase crosses ~0 -> perfectly locked
    locked_spike_times = np.arange(0.5, 9.5, 1.0 / 8.0)  # one spike per 8Hz cycle, near phase 0
    locked = phase_locking_index(locked_spike_times, lfp_phase, lfp_timestamps)

    # Uniform random spike times -> not phase-locked
    rng = np.random.default_rng(0)
    uniform_spike_times = np.sort(rng.uniform(0, 10, len(locked_spike_times)))
    uniform = phase_locking_index(uniform_spike_times, lfp_phase, lfp_timestamps)

    assert locked["pli"] > uniform["pli"]
    assert locked["rayleigh_z"] > uniform["rayleigh_z"]
    assert locked["rayleigh_pvalue"] < 0.05


def test_phase_locking_index_empty_spikes_returns_zeroed_defaults():
    result = phase_locking_index(np.array([]), np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    assert result["pli"] == 0.0
    assert result["rayleigh_pvalue"] == 1.0
    assert result["n_spikes"] == 0
