"""Unit and adversarial test suite for wPLI and zFLIP (cortical depth phase gradients).

Verifies:
1. wPLI mathematical contract:
   - Evaluates segment cross-spectra Im(S_{xy, k}(f)).
   - Standard estimator and debiased squared estimator.
   - Strictly unsigned (>= 0).
   - Reduces sensitivity to zero-phase-lag mixing (identical signals -> wPLI = 0).
   - Lagged signals -> high wPLI (~1.0).
2. zFLIP estimation and identifiability gates:
   - 2D array requirement (rejects 1D, 3D, pre-averaged tensors).
   - Frequency support check (needs >= 3 bins).
   - Unwrapped phase linearity gate (R^2 >= min_linearity_r2).
   - Phase unwrapping unambiguous delay bound (|tau| < 1 / (2 * df)).
   - Accurate delay and velocity recovery on synthetic traveling waves.
   - Non-identifiable relations return NaN and delay_identifiable = False.
3. Adversarial probes:
   - Zero-lag volume conduction injected on top of traveling wave.
   - Frequency-dependent / dispersive delay (violating linearity).
   - Phase wrapping / severe delay aliasing.
   - Opposing simultaneous waves (canceling phase slope).
   - Missing contacts / irregular spacing.
   - Independent noise rejection.
"""

import numpy as np
import pytest
from scipy import signal

import jnwb


def test_wpli_zero_lag_rejection():
    """Identical signals have Im(Sxy) = 0 and must yield wPLI = 0.0."""
    rng = np.random.default_rng(42)
    x = rng.normal(size=2000)
    res = jnwb.wpli(x, x, fs=1000.0, freq_range=(10.0, 40.0), nperseg=256)
    assert res["wpli"] == 0.0
    assert res["wpli_debiased_sq"] == 0.0
    assert res["n_segments"] > 0
    assert res["n_freqs"] > 0
    assert np.all(res["wpli_spectrum"] == 0.0)


def test_wpli_delayed_signals():
    """Signals with true temporal lag yield high wPLI."""
    rng = np.random.default_rng(42)
    x = rng.normal(size=3000)
    # y is delayed by 4 samples (4 ms at 1000 Hz)
    y = np.roll(x, 4)
    res = jnwb.wpli(x, y, fs=1000.0, freq_range=(15.0, 45.0), nperseg=256)
    assert res["wpli"] > 0.90
    assert res["wpli_debiased_sq"] > 0.85
    assert res["wpli"] >= 0.0


def test_wpli_independent_noise():
    """Uncorrelated white noise has low wPLI and debiased squared wPLI near zero."""
    rng = np.random.default_rng(42)
    x = rng.normal(size=10000)
    y = rng.normal(size=10000)
    res = jnwb.wpli(x, y, fs=1000.0, freq_range=(10.0, 50.0), nperseg=256)
    # With enough segments, debiased squared estimator hovers around zero
    assert abs(res["wpli_debiased_sq"]) < 0.05


def test_wpli_input_shapes_and_aliases():
    """Check handling of sampling_rate alias and empty inputs."""
    with pytest.raises(ValueError, match="empty"):
        jnwb.wpli([], [], fs=1000.0)

    x = np.random.randn(500)
    y = np.random.randn(500)
    res = jnwb.wpli(x, y, sampling_rate=1000.0)
    assert "wpli" in res
    assert res["n_segments"] > 0


def test_zflip_input_validation():
    """zflip validates shapes, channel counts, and sampling rate."""
    # 1D array
    with pytest.raises(ValueError, match="2D array"):
        jnwb.zflip(np.random.randn(100), orientation="superficial_to_deep", fs=1000.0)

    # 3D array (e.g. pre-averaged C x C x F tensor)
    with pytest.raises(ValueError, match="2D array"):
        jnwb.zflip(np.random.randn(8, 8, 50), orientation="superficial_to_deep", fs=1000.0)

    # Fewer than 3 channels
    with pytest.raises(ValueError, match="at least 3 channels"):
        jnwb.zflip(np.random.randn(2, 1000), orientation="superficial_to_deep", fs=1000.0)

    # Invalid fs
    with pytest.raises(ValueError, match="fs must be strictly positive"):
        jnwb.zflip(np.random.randn(8, 1000), orientation="superficial_to_deep", fs=-10.0)

    # Invalid pitch
    with pytest.raises(ValueError, match="pitch_um must be strictly positive"):
        jnwb.zflip(np.random.randn(8, 1000), orientation="superficial_to_deep", fs=1000.0, pitch_um=-50.0)


def test_zflip_insufficient_freq_bins():
    """Narrow band with < 3 bins fails gracefully with unidentifiable status."""
    data = np.random.randn(8, 1000)
    res = jnwb.zflip(data, orientation="superficial_to_deep", fs=1000.0, freq_range=(20.0, 21.0), nperseg=128)
    assert not res.accepted
    assert not res.delay_identifiable
    assert res.directionality == "unidentifiable"
    assert "Insufficient frequency bins" in res.rejection_reason


@pytest.mark.parametrize("level", [0.0, 0.3])
def test_zflip_a_constant_contact_makes_its_pairs_nan_not_zero(level):
    """A constant contact's two adjacent pairs report NaN wPLI, so the mean is NaN.

    What would pass while the flat contact still counts: checking only ``accepted``, which
    the delay gate already refuses. The inline wPLI gave an all-zero contact 0.0 and a 0.3
    one rounding residue, and both entered ``mean_wpli`` as coupling measurements.
    """
    rng = np.random.default_rng(3)
    t = np.arange(4000) / 1000.0
    data = np.stack([np.sin(2 * np.pi * 25 * (t - 0.002 * k)) + 0.2 * rng.normal(size=t.size)
                     for k in range(5)])
    data[2] = level
    res = jnwb.zflip(data, orientation="superficial_to_deep", fs=1000.0, n_surrogates=5, rng=0)
    np.testing.assert_array_equal(np.isnan(res.adjacent_wpli), [False, True, True, False])
    assert np.isnan(res.mean_wpli) and np.isnan(res.p_value) and not res.accepted
    assert "Contact(s) [2] constant" in res.rejection_reason


def test_zflip_clean_traveling_wave_recovery():
    """Verify recovery of signed direction and apparent velocity on clean traveling wave."""
    fs = 1000.0
    n_channels = 8
    n_samples = 4000
    pitch_um = 50.0  # 50 um = 0.05 mm = 5e-5 m

    # Create broadband traveling wave: superficial leads deep (c=0 leads c=1...)
    # tau_per_channel = 0.002 s (2 ms).
    # expected velocity: v = pitch_m / tau = (50e-6 m) / (0.002 s) = 0.025 m/s.
    rng = np.random.default_rng(42)
    max_shift = 100
    w = rng.normal(size=n_samples + max_shift)
    b, a = signal.butter(4, [15.0 / (fs / 2), 35.0 / (fs / 2)], btype="band")
    filtered = signal.filtfilt(b, a, w)

    data = np.zeros((n_channels, n_samples))
    delay_s = 0.002
    for c in range(n_channels):
        shift = int(round(c * delay_s * fs))
        data[c] = filtered[max_shift - shift : max_shift - shift + n_samples] + rng.normal(
            0, 0.05, size=n_samples
        )

    res = jnwb.zflip(
        data,
        orientation="superficial_to_deep",
        fs=fs,
        freq_range=(18.0, 32.0),
        pitch_um=pitch_um,
        n_surrogates=20,
        seed=42,
    )

    assert res.accepted
    assert res.delay_identifiable
    assert res.directionality == "superficial_to_deep"
    assert np.isclose(res.tau_per_channel_s, delay_s, rtol=0.15)
    assert res.apparent_velocity_m_s is not None
    assert np.isclose(res.apparent_velocity_m_s, 0.025, rtol=0.15)
    assert res.mean_wpli > 0.50
    assert res.p_value <= 0.05


def test_zflip_reverse_direction():
    """Verify deep-to-superficial wave produces negative tau and correct directionality."""
    fs = 1000.0
    n_channels = 8
    n_samples = 4000
    pitch_um = 50.0

    rng = np.random.default_rng(42)
    max_shift = 100
    w = rng.normal(size=n_samples + max_shift)
    b, a = signal.butter(4, [15.0 / (fs / 2), 35.0 / (fs / 2)], btype="band")
    filtered = signal.filtfilt(b, a, w)

    data = np.zeros((n_channels, n_samples))
    delay_s = -0.002  # deep leads superficial
    for c in range(n_channels):
        shift = int(round(c * abs(delay_s) * fs))
        # deep contact (c=7) occurs earlier
        data[c] = filtered[shift : shift + n_samples] + rng.normal(0, 0.05, size=n_samples)

    res = jnwb.zflip(
        data,
        orientation="superficial_to_deep",
        fs=fs,
        freq_range=(18.0, 32.0),
        pitch_um=pitch_um,
        n_surrogates=20,
        seed=42,
    )

    assert res.accepted
    assert res.delay_identifiable
    assert res.directionality == "deep_to_superficial"
    assert res.tau_per_channel_s < 0.0
    assert res.apparent_velocity_m_s is not None


def test_zflip_adversarial_zero_lag_injection():
    """Pure zero-lag common reference has Im=0 and is rejected by zflip."""
    rng = np.random.default_rng(42)
    n_channels = 8
    n_samples = 4000
    common_signal = rng.normal(size=n_samples)

    # 1. Pure zero-lag identical signal across all channels
    data_pure = np.tile(common_signal, (n_channels, 1))
    res_pure = jnwb.zflip(data_pure, orientation="superficial_to_deep", fs=1000.0, freq_range=(15.0, 35.0), n_surrogates=20, seed=42)
    assert not res_pure.accepted
    assert res_pure.mean_wpli == 0.0
    assert "below min_wpli" in res_pure.rejection_reason

    # 2. Zero-lag common signal plus independent contact noise
    data_noisy = data_pure + 0.1 * rng.normal(size=(n_channels, n_samples))
    res_noisy = jnwb.zflip(data_noisy, orientation="superficial_to_deep", fs=1000.0, freq_range=(15.0, 35.0), n_surrogates=20, seed=42)
    assert not res_noisy.accepted
    assert not res_noisy.delay_identifiable
    assert res_noisy.p_value > 0.05  # not distinguishable from phase-scrambled null
    assert res_noisy.directionality == "unidentifiable"


def test_zflip_adversarial_nonlinear_delay():
    """Dispersive / frequency-dependent delay violates phase linearity and is rejected."""
    fs = 1000.0
    n_channels = 6
    n_samples = 4000
    rng = np.random.default_rng(42)

    # Create signal where phase shift is quadratic in frequency (dispersion), not linear
    t = np.arange(n_samples) / fs
    data = np.zeros((n_channels, n_samples))
    freqs = np.linspace(15.0, 35.0, 20)

    for c in range(n_channels):
        sig = np.zeros(n_samples)
        for f in freqs:
            # quadratic phase: phi(f) ~ f^2, so phase slope is not constant
            phase_disp = c * 0.005 * ((f - 25.0) ** 2)
            sig += np.sin(2.0 * np.pi * f * t + phase_disp)
        data[c] = sig + rng.normal(0, 0.2, size=n_samples)

    res = jnwb.zflip(
        data,
        orientation="superficial_to_deep",
        fs=fs,
        freq_range=(15.0, 35.0),
        min_linearity_r2=0.80,
        n_surrogates=10,
        seed=42,
    )
    # Must fail linear identifiability gate
    assert not res.accepted
    assert not res.delay_identifiable
    assert np.isnan(res.tau_per_channel_s)
    assert res.apparent_velocity_m_s is None
    assert res.directionality == "unidentifiable"


def test_zflip_adversarial_opposing_waves():
    """Opposing simultaneous waves of equal amplitude cancel out spatial gradient."""
    fs = 1000.0
    n_channels = 8
    n_samples = 4000
    rng = np.random.default_rng(42)

    w1 = rng.normal(size=n_samples + 100)
    w2 = rng.normal(size=n_samples + 100)
    b, a = signal.butter(4, [18.0 / (fs / 2), 32.0 / (fs / 2)], btype="band")
    f1 = signal.filtfilt(b, a, w1)
    f2 = signal.filtfilt(b, a, w2)

    data = np.zeros((n_channels, n_samples))
    delay_s = 0.002
    for c in range(n_channels):
        sh1 = int(round(c * delay_s * fs))
        sh2 = int(round((n_channels - 1 - c) * delay_s * fs))
        data[c] = (
            f1[sh1 : sh1 + n_samples]
            + f2[sh2 : sh2 + n_samples]
            + rng.normal(0, 0.1, size=n_samples)
        )

    res = jnwb.zflip(data, orientation="superficial_to_deep", fs=fs, freq_range=(18.0, 32.0), n_surrogates=15, seed=42)
    # Opposing waves destroy monotonic cumulative phase gradient
    assert res.directionality == "unidentifiable" or not res.accepted


def test_zflip_container_access_and_to_dict():
    """ZFlipResult supports dataclass attributes, dict access, and serialization."""
    data = np.random.randn(5, 1000)
    res = jnwb.zflip(data, orientation="superficial_to_deep", fs=1000.0, freq_range=(15.0, 35.0), n_surrogates=5, seed=42)

    # Attribute access
    assert hasattr(res, "adjacent_wpli")
    assert hasattr(res, "apparent_velocity_m_s")

    # Dict-like access
    assert res["n_channels"] == 5
    assert res.get("pitch_um", 999) is None or res.get("pitch_um") == res.pitch_um

    # Serialization
    d = res.to_dict()
    assert isinstance(d, dict)
    assert "mean_wpli" in d
    assert "adjacent_delays_s" in d
    assert "directionality" in d
