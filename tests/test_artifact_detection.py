r"""Synthetic ground-truth tests for jnwb.artifact_detection. Small in-memory arrays, no NWB I/O,
per project convention (seconds not minutes)."""
import numpy as np

from jnwb.artifact_detection import (
    bad_channels_from_correlation,
    bad_trials_single_channel,
    channel_correlation_matrix,
    consensus_bad_trials,
    trial_correlation_matrix,
)


def test_bad_channels_detected_from_low_correlation():
    """20 good channels share a common component (plus channel-specific noise); 3 channels are
    pure independent noise (damaged/detached contact). The 3 must be flagged, the 20 must not."""
    rng = np.random.default_rng(0)
    n_samples = 5000
    shared = rng.normal(size=n_samples)
    good = np.array([shared + rng.normal(scale=0.5, size=n_samples) for _ in range(20)])
    bad = np.array([rng.normal(scale=1.0, size=n_samples) for _ in range(3)])
    data = np.vstack([good, bad])
    corr = channel_correlation_matrix(data)
    flagged, summary, z = bad_channels_from_correlation(corr, z_thresh=4.0)
    assert flagged[20:].all(), f"all 3 injected bad channels must be flagged, got {flagged[20:]}"
    assert not flagged[:20].any(), f"no good channel should be flagged, got {flagged[:20]}"
    print("PASS: bad channels separated from good channels by correlation outlier detection")


def test_no_false_positives_when_all_channels_good():
    rng = np.random.default_rng(1)
    n_samples = 5000
    shared = rng.normal(size=n_samples)
    good = np.array([shared + rng.normal(scale=0.5, size=n_samples) for _ in range(24)])
    corr = channel_correlation_matrix(good)
    flagged, _, _ = bad_channels_from_correlation(corr, z_thresh=5.0)
    assert not flagged.any(), f"expected zero false positives on an all-good probe, got {flagged.sum()}"
    print("PASS: no false-positive bad channels on an all-good synthetic probe")


def test_bad_trials_single_channel_detects_artifact_burst():
    """100 clean trials of a stereotyped waveform + noise; 5 trials carry an injected
    high-amplitude transient. The 5 must be flagged via the amplitude arm; ordinary trial-shape
    jitter must not trigger false positives."""
    rng = np.random.default_rng(2)
    n_trials, n_times = 100, 200
    t = np.linspace(0, 1, n_times)
    template = np.sin(2 * np.pi * 3 * t)
    trials = np.array([template + rng.normal(scale=0.1, size=n_times) for _ in range(n_trials)])
    artifact_idx = [10, 30, 50, 70, 90]
    for i in artifact_idx:
        trials[i, 80:100] += 15.0  # large synchronous-style deflection
    flag, corr_z, amp_z = bad_trials_single_channel(trials, corr_z_thresh=4.0, amp_z_thresh=4.0)
    assert all(flag[i] for i in artifact_idx), f"all 5 injected artifact trials must be flagged, got {flag[artifact_idx]}"
    n_false_pos = flag.sum() - len(artifact_idx)
    assert n_false_pos <= 2, f"expected near-zero false positives among 95 clean trials, got {n_false_pos}"
    print(f"PASS: single-channel bad-trial detection recovers 5/5 injected artifacts "
          f"({flag.sum()} total flagged of 100)")


def test_consensus_requires_multiple_channels():
    """A trial flagged on only 1 of 6 good channels (a single channel's own quirk) must NOT reach
    consensus; a trial flagged on 5 of 6 (a genuine shared artifact) must."""
    n_trials = 10
    flags = np.zeros((6, n_trials), dtype=bool)
    flags[0, 3] = True                      # single-channel quirk on trial 3
    flags[[0, 1, 2, 3, 4], 7] = True         # shared artifact on trial 7 (5 of 6 channels)
    consensus, frac = consensus_bad_trials(flags, min_frac_channels=0.5)
    assert not consensus[3], "single-channel flag alone must not reach consensus"
    assert consensus[7], "artifact flagged on 5/6 good channels must reach consensus"
    assert consensus.sum() == 1
    print("PASS: cross-channel consensus requires a shared artifact, not a single channel's flag")


def test_consensus_empty_input_shape():
    flags = np.zeros((0, 5), dtype=bool)
    consensus, frac = consensus_bad_trials(flags)
    assert consensus.shape == (5,) and not consensus.any()
    print("PASS: consensus handles zero-good-channel edge case without crashing")


def test_trial_correlation_matrix_shape_and_symmetry():
    rng = np.random.default_rng(3)
    trials = rng.normal(size=(15, 50))
    corr = trial_correlation_matrix(trials)
    assert corr.shape == (15, 15)
    assert np.allclose(corr, corr.T)
    assert np.allclose(np.diag(corr), 1.0)
    print("PASS: trial correlation matrix shape/symmetry/diagonal")


def test_determinism():
    rng = np.random.default_rng(4)
    data = rng.normal(size=(20, 1000))
    corr1 = channel_correlation_matrix(data)
    corr2 = channel_correlation_matrix(data)
    assert np.array_equal(corr1, corr2), "identical input must give byte-identical correlation matrix"
    f1, s1, z1 = bad_channels_from_correlation(corr1, z_thresh=5.0)
    f2, s2, z2 = bad_channels_from_correlation(corr1, z_thresh=5.0)
    assert np.array_equal(f1, f2) and np.array_equal(z1, z2)
    print("PASS: determinism (no RNG inside detection functions, pure function of input)")


if __name__ == "__main__":
    test_bad_channels_detected_from_low_correlation()
    test_no_false_positives_when_all_channels_good()
    test_bad_trials_single_channel_detects_artifact_burst()
    test_consensus_requires_multiple_channels()
    test_consensus_empty_input_shape()
    test_trial_correlation_matrix_shape_and_symmetry()
    test_determinism()
    print("\nAll artifact_detection self-tests PASSED")
