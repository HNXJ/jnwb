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


def _clean_wave_with_contact_2(scale=None, level=None):
    """Five contacts of a noiseless 25 Hz wave, 2 ms per contact; contact 2 scaled or held."""
    t = np.arange(4000) / 1000.0
    data = np.stack([np.sin(2 * np.pi * 25 * (t - 0.002 * k)) for k in range(5)])
    if scale is not None:
        data[2] *= scale
    if level is not None:
        data[2] = level
    return data


def test_zflip_a_constant_contact_gives_its_pairs_no_delay():
    """A pair with a constant contact is not identifiable and reports no delay or linearity.

    Held at 1.0, contact 2's spectrum is rounding residue whose phase happens to be linear
    in frequency: pair (2, 3) fitted R^2 = 0.997 and a 0.11 s delay, and was marked
    identifiable. What would pass while the residue still counts: checking ``accepted`` or
    ``tau_per_channel_s``, which the other pairs' failed gate already makes False and NaN.
    """
    res = jnwb.zflip(_clean_wave_with_contact_2(level=1.0), orientation="superficial_to_deep",
                     fs=1000.0, n_surrogates=0)
    assert not res.adjacent_identifiable[1] and not res.adjacent_identifiable[2]
    assert np.all(np.isnan(res.adjacent_delays_s[1:3]))
    assert np.all(np.isnan(res.adjacent_linearity_r2[1:3]))
    assert np.all(np.isfinite(res.adjacent_linearity_r2[[0, 3]]))


def test_zflip_a_constant_contact_leaves_the_shaft_without_a_delay():
    """With every other pair identifiable, a constant contact still blocks the shaft estimate.

    On 10-40 Hz noise lagged 2 samples per contact every clean pair fits R^2 ~ 0.999, so the
    aggregate is refused by the constant contact alone. What would pass while it leaks:
    exempting the constant pairs from the all-pairs gate and summing the rest, which fits
    the remaining pairs and names a direction.
    """
    rng = np.random.default_rng(0)
    b, a = signal.butter(4, [10.0, 40.0], btype="band", fs=1000.0)
    src = signal.filtfilt(b, a, rng.normal(size=4100))
    data = np.stack([src[100 - 2 * k: 100 - 2 * k + 4000] for k in range(6)])
    kwargs = dict(orientation="superficial_to_deep", fs=1000.0, n_surrogates=0, pitch_um=50.0)
    assert jnwb.zflip(data, **kwargs).adjacent_identifiable.all()
    data[4] = 1.0
    res = jnwb.zflip(data, **kwargs)
    assert res.adjacent_identifiable[:3].all()
    assert not res.delay_identifiable
    assert np.isnan(res.tau_per_channel_s)
    assert res.apparent_velocity_m_s is None
    assert res.directionality == "unidentifiable"


def test_zflip_a_weakly_coupled_pair_is_not_identifiable():
    """Each pair's wPLI must reach ``min_wpli``, not only their mean.

    Contact 4 carries the wave under independent noise at twice its SD: both of its pairs
    still fit a linear phase, but their wPLI (0.84) is below ``min_wpli=0.9`` while the mean
    (0.94) is above it. What would pass while the pair still counts: checking only
    ``mean_wpli`` or ``has_coupling``, which the mean satisfies. Every pair passes the
    phase-frequency gate, so the reason must not claim that it failed.
    """
    rng = np.random.default_rng(0)
    b, a = signal.butter(4, [10.0, 40.0], btype="band", fs=1000.0)
    src = signal.filtfilt(b, a, rng.normal(size=4100))
    data = np.stack([src[100 - 2 * k: 100 - 2 * k + 4000] for k in range(6)])
    data[4] += 2.0 * np.std(src) * np.random.default_rng(102).normal(size=4000)
    res = jnwb.zflip(data, orientation="superficial_to_deep", fs=1000.0, pitch_um=100.0,
                     min_wpli=0.9, n_surrogates=50, rng=0)
    assert res.mean_wpli >= 0.9 and np.all(res.adjacent_wpli[3:] < 0.9)
    assert np.all(res.adjacent_linearity_r2[3:] >= 0.70)
    assert not res.adjacent_identifiable[3] and not res.adjacent_identifiable[4]
    assert np.isnan(res.tau_per_channel_s)
    assert res.apparent_velocity_m_s is None
    assert not res.accepted
    assert "[(3, 4), (4, 5)] wPLI below min_wpli" in res.rejection_reason
    assert "Phase-frequency relation failed" not in res.rejection_reason


def _wave_with_contact_4(sine_hz, contact=4, wave_scale=0.0):
    """Five contacts of 10-40 Hz noise lagged 2 samples each; one carries a sinusoid.

    The chosen contact keeps ``wave_scale`` times its own lagged wave, plus a unit sinusoid.
    """
    fs, n = 1000.0, 6000
    b, a = signal.butter(4, [10, 40], btype="band", fs=fs)
    src = signal.filtfilt(b, a, np.random.default_rng(7).standard_normal(n + 50))
    t = np.arange(n) / fs
    data = np.stack([src[50 - 2 * k: 50 - 2 * k + n] for k in range(5)])
    data[contact] = wave_scale * data[contact] + np.sin(2 * np.pi * sine_hz * t)
    return data


def _in_band_fraction(data, band=(15.0, 35.0)):
    """Each contact's share of power inside ``band``, from zflip's default segmentation with
    each segment linearly detrended."""
    nperseg = min(max(data.shape[1] // 2, 8), 256)
    f, _, Z = signal.stft(data, fs=1000.0, nperseg=nperseg, noverlap=nperseg // 2,
                          boundary=None, padded=False, axis=-1, detrend="linear")
    power = np.mean(np.abs(Z) ** 2, axis=-1)
    mask = (f >= band[0]) & (f <= band[1])
    with np.errstate(invalid="ignore", divide="ignore"):
        return power[:, mask].sum(axis=1) / power.sum(axis=1)


@pytest.mark.parametrize("contact, sine_hz", [(4, 7.8), (4, 5.7), (0, 55.0)])
def test_zflip_a_contact_with_only_out_of_band_power_gives_no_delay(contact, sine_hz):
    """A contact carrying only an out-of-band sinusoid blocks the delay of its two pairs.

    Its in-band spectrum is window leakage: with 7.8 Hz on contact 4 the pair wPLI was 0.22
    and the fit accepted a delay 13 times the true 2 ms per contact, with no rejection reason. What would pass
    while the leakage still counts: checking ``adjacent_wpli`` against ``min_wpli``, which
    the leakage clears.
    """
    res = jnwb.zflip(_wave_with_contact_4(sine_hz, contact), fs=1000.0,
                     orientation="superficial_to_deep", pitch_um=100.0, n_surrogates=50, rng=0)
    pairs = [p for p in (contact - 1, contact) if 0 <= p < 4]
    assert not res.adjacent_identifiable[pairs].any()
    assert np.isnan(res.tau_per_channel_s) and res.apparent_velocity_m_s is None
    assert not res.accepted
    assert f"Contact(s) [{contact}] carry less than 0.0100" in res.rejection_reason


def test_zflip_the_in_band_fraction_gate_is_inclusive_at_its_threshold():
    """A contact is kept at a fraction equal to ``min_band_power_fraction`` and refused below.

    Contact 4 mixes a unit 7.8 Hz sinusoid with a scaled copy of its own lagged wave, so its
    in-band fraction sits just below (0.0095) or just above (0.0105) the 0.01 default. A
    dropped check keeps the lower one; a strict comparison refuses the exact threshold.
    """
    kwargs = dict(fs=1000.0, orientation="superficial_to_deep", n_surrogates=0)
    below, above = _wave_with_contact_4(7.8, wave_scale=0.3636), _wave_with_contact_4(
        7.8, wave_scale=0.3825)
    f_below, f_above = _in_band_fraction(below)[4], _in_band_fraction(above)[4]
    assert 0.009 < f_below < 0.01 < f_above < 0.011
    refused = jnwb.zflip(below, **kwargs)
    assert not refused.adjacent_identifiable[3] and np.isnan(refused.tau_per_channel_s)
    assert "Contact(s) [4] carry less than" in refused.rejection_reason
    kept = jnwb.zflip(above, **kwargs)
    assert kept.adjacent_identifiable.all() and np.isfinite(kept.tau_per_channel_s)
    at_threshold = jnwb.zflip(above, min_band_power_fraction=float(f_above), **kwargs)
    assert at_threshold.adjacent_identifiable.all()
    just_over = jnwb.zflip(above, min_band_power_fraction=float(np.nextafter(f_above, 1.0)),
                           **kwargs)
    assert not just_over.adjacent_identifiable[3]


def test_zflip_a_dc_offset_does_not_lower_the_in_band_fraction():
    """A clean wave on a DC offset of 10 SD keeps its delay.

    Undetrended, the offset's power fills the fraction's denominator and drops it to 0.0045,
    below the 0.01 default. What would pass while the offset still counts: a wave with no
    offset, which is how every other fixture here is built.
    """
    data = _wave_with_contact_4(0.0, wave_scale=1.0)
    data += 10.0 * np.std(data[0])
    res = jnwb.zflip(data, fs=1000.0, orientation="superficial_to_deep", n_surrogates=0)
    assert res.adjacent_identifiable.all() and res.delay_identifiable
    assert res.tau_per_channel_s == pytest.approx(0.002, rel=0.05)


def test_zflip_a_linear_drift_does_not_lower_the_in_band_fraction():
    """A clean wave on a drift of 0 to 500 SD keeps its delay, and its fraction stays high.

    A per-segment mean removal leaves each segment's slope, whose power brings the fraction
    to 0.075; a linear detrend keeps it at 0.74. Undetrended, it is below the default.
    """
    data = _wave_with_contact_4(0.0, wave_scale=1.0)
    data += np.linspace(0.0, 500.0 * np.std(data[0]), data.shape[1])
    kwargs = dict(fs=1000.0, orientation="superficial_to_deep", n_surrogates=0)
    res = jnwb.zflip(data, **kwargs)
    assert res.delay_identifiable
    assert res.tau_per_channel_s == pytest.approx(0.002, rel=0.05)
    assert jnwb.zflip(data, min_band_power_fraction=0.5, **kwargs).delay_identifiable


def test_zflip_a_contact_with_no_power_in_any_segment_is_refused():
    """A contact whose only nonzero samples fall after the last segment has no fraction.

    6000 samples in 256-sample segments at a 128-sample hop end at sample 5888, so a single
    nonzero sample at 5990 is not constant yet leaves every segment spectrum zero: 0 / 0.
    What would pass while it is kept: a ``fraction < threshold`` test, false for NaN.
    """
    data = _wave_with_contact_4(0.0, wave_scale=1.0)
    data[4] = 0.0
    data[4, 5990] = 1.0
    res = jnwb.zflip(data, fs=1000.0, orientation="superficial_to_deep", n_surrogates=0)
    assert np.isnan(_in_band_fraction(data)[4])
    assert not res.adjacent_identifiable[3]
    assert "Contact(s) [4] carry less than" in res.rejection_reason


def _lagged_rows(lags, n=8000):
    sos = signal.butter(4, (10, 40), btype="band", fs=1000.0, output="sos")
    src = signal.sosfiltfilt(sos, np.random.default_rng(11).standard_normal(n + 400))
    return np.stack([src[400 - lag: 400 - lag + n] for lag in lags])


def test_zflip_a_zig_zag_delay_is_refused_by_the_depth_fit():
    """Lags 0, 2, 0, 2, 0 give four identifiable pairs whose cumulative delay is not linear.

    The refusal is the depth fit's alone, so the reason names it and not the pair gates.
    """
    res = jnwb.zflip(_lagged_rows([0, 2, 0, 2, 0]), fs=1000.0,
                     orientation="superficial_to_deep", n_surrogates=0)
    assert res.adjacent_identifiable.all() and not res.delay_identifiable
    assert np.isnan(res.tau_per_channel_s)
    assert "Cumulative delay not linear in contact index" in res.rejection_reason
    assert "Phase-frequency relation failed" not in res.rejection_reason


def test_zflip_shared_slow_power_does_not_bias_the_delay():
    """A 2 Hz component at 30 SD shared by every contact leaves the delay within 5%.

    Undetrended, its window leakage into the band pulled the phase slope toward zero lag and
    raised the delay by 12%. What would pass while it leaks: checking only that the delay is
    identifiable, which it stays.
    """
    rows = _lagged_rows([0, 2, 4, 6, 8])
    kwargs = dict(fs=1000.0, orientation="superficial_to_deep", n_surrogates=0)
    clean = jnwb.zflip(rows, **kwargs).tau_per_channel_s
    t = np.arange(rows.shape[1]) / 1000.0
    slow = 30.0 * np.std(rows[0]) * np.sin(2 * np.pi * 2.0 * t)
    res = jnwb.zflip(rows + slow, **kwargs)
    assert res.delay_identifiable
    assert res.tau_per_channel_s == pytest.approx(clean, rel=0.05)


def test_zflip_identical_contacts_give_no_direction():
    """Identical contacts have no delay gradient: phase residue near 1e-21 s is not a sign.

    With both pair gates at 0.0, every pair passes and the cumulative delay is exactly linear,
    so only the zero-gradient check can refuse. Without a round-off width, the residue named
    a direction.
    """
    res = jnwb.zflip(_lagged_rows([0, 0, 0, 0, 0]), fs=1000.0,
                     orientation="superficial_to_deep", n_surrogates=0, min_wpli=0.0,
                     min_linearity_r2=0.0)
    assert res.adjacent_identifiable.all()
    assert not res.delay_identifiable and np.isnan(res.tau_per_channel_s)
    assert res.directionality == "unidentifiable"
    assert "Delay gradient across contacts is zero to round-off" in res.rejection_reason


def test_zflip_a_pair_wpli_equal_to_min_wpli_passes_the_pair_gate():
    """The pair gate is ``wPLI >= min_wpli``, inclusive at the threshold.

    Contacts 0 and 1 are identical, so pair (0, 1) has wPLI exactly 0.0; pairs (1, 2) and
    (2, 3) are lagged 2 samples and have wPLI near 1. With ``min_wpli=0.0`` and the linearity
    threshold at 0.0, every pair passes. A strict ``>`` refuses pair (0, 1); a reversed
    ``<=`` refuses the lagged pairs.
    """
    rng = np.random.default_rng(0)
    b, a = signal.butter(4, [10.0, 40.0], btype="band", fs=1000.0)
    src = signal.filtfilt(b, a, rng.normal(size=4100))
    lagged = [src[100 - 2 * k: 100 - 2 * k + 4000] for k in range(3)]
    data = np.stack([lagged[0], lagged[0], lagged[1], lagged[2]])
    res = jnwb.zflip(data, orientation="superficial_to_deep", fs=1000.0, min_wpli=0.0,
                     min_linearity_r2=0.0, n_surrogates=0)
    assert res.adjacent_wpli[0] == 0.0 and np.all(res.adjacent_wpli[1:] > 0.9)
    assert res.adjacent_identifiable.tolist() == [True, True, True]
    assert "wPLI below min_wpli" not in res.rejection_reason


def test_zflip_a_contact_of_tiny_amplitude_is_not_constant():
    """Constancy is exact: a contact scaled by 1e-9 is measured, not dropped as flat.

    wPLI and the cross-spectral phase are unchanged by scaling one contact, so the scaled
    run must match the unscaled one. A tolerance on the peak-to-peak range (``ptp < 1e-6``)
    calls this 2e-9 contact constant and turns its two pairs NaN.
    """
    kwargs = dict(orientation="superficial_to_deep", fs=1000.0, n_surrogates=0)
    ref = jnwb.zflip(_clean_wave_with_contact_2(), **kwargs)
    tiny = jnwb.zflip(_clean_wave_with_contact_2(scale=1e-9), **kwargs)
    assert np.ptp(_clean_wave_with_contact_2(scale=1e-9)[2]) < 1e-6
    np.testing.assert_allclose(tiny.adjacent_wpli, ref.adjacent_wpli, rtol=1e-6)
    np.testing.assert_allclose(tiny.adjacent_linearity_r2, ref.adjacent_linearity_r2,
                               rtol=1e-6)
    np.testing.assert_array_equal(tiny.adjacent_identifiable, ref.adjacent_identifiable)
    assert "constant" not in (tiny.rejection_reason or "")


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


def _zflip_noise(rng, n_surrogates=30):
    # White noise, so the p-value sits away from the 1/(n_surrogates+1) floor and a
    # different surrogate stream gives a different p.
    data = np.random.default_rng(8).normal(size=(4, 2000))
    return jnwb.zflip(data, 1000.0, orientation="superficial_to_deep",
                      n_surrogates=n_surrogates, rng=rng)


def test_zflip_the_entropy_recorded_for_rng_none_reproduces_p():
    first = _zflip_noise(None)
    assert isinstance(first.surrogate_seed_entropy, int)
    again = _zflip_noise(first.surrogate_seed_entropy)
    assert again.p_value == first.p_value
    assert again.surrogate_seed_entropy == first.surrogate_seed_entropy
    assert first.to_dict()["surrogate_seed_entropy"] == first.surrogate_seed_entropy
    # Fresh draws must disagree somewhere, or equal p-values prove nothing.
    assert len({_zflip_noise(None).p_value for _ in range(4)} | {first.p_value}) > 1


def test_zflip_an_int_seed_is_recorded_as_given_and_draws_the_same_stream():
    res = _zflip_noise(123)
    assert res.surrogate_seed_entropy == 123
    assert res.p_value == _zflip_noise(np.random.default_rng(123)).p_value


def test_zflip_a_generator_and_an_untested_fit_record_none():
    assert _zflip_noise(np.random.default_rng(1)).surrogate_seed_entropy is None
    assert _zflip_noise(3, n_surrogates=0).surrogate_seed_entropy is None


@pytest.mark.parametrize("bad", [2.7, True, np.random.SeedSequence(3), [1, 2]])
def test_zflip_refuses_an_rng_outside_int_generator_none(bad):
    with pytest.raises(TypeError, match="rng"):
        _zflip_noise(bad, n_surrogates=5)
