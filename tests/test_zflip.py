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

The sign, units, identifiability and inference section after the body is marked by a comment.
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

    rng = np.random.default_rng(4)
    x = rng.standard_normal(500)
    y = rng.standard_normal(500)
    res = jnwb.wpli(x, y, sampling_rate=1000.0)
    assert "wpli" in res
    assert res["n_segments"] > 0


def test_zflip_input_validation():
    """zflip validates shapes, channel counts, and sampling rate."""
    rng = np.random.default_rng(5)
    # 1D array
    with pytest.raises(ValueError, match="2D array"):
        jnwb.zflip(rng.standard_normal(100), orientation="superficial_to_deep", fs=1000.0)

    # 3D array (e.g. pre-averaged C x C x F tensor)
    with pytest.raises(ValueError, match="2D array"):
        jnwb.zflip(rng.standard_normal((8, 8, 50)), orientation="superficial_to_deep", fs=1000.0)

    # Fewer than 3 channels
    with pytest.raises(ValueError, match="at least 3 channels"):
        jnwb.zflip(rng.standard_normal((2, 1000)), orientation="superficial_to_deep", fs=1000.0)

    # Invalid fs
    with pytest.raises(ValueError, match="fs must be strictly positive"):
        jnwb.zflip(rng.standard_normal((8, 1000)), orientation="superficial_to_deep", fs=-10.0)

    # Invalid pitch
    with pytest.raises(ValueError, match="pitch_um must be strictly positive"):
        jnwb.zflip(rng.standard_normal((8, 1000)), orientation="superficial_to_deep", fs=1000.0, pitch_um=-50.0)


def test_zflip_insufficient_freq_bins():
    """Narrow band with < 3 bins fails gracefully with unidentifiable status."""
    rng = np.random.default_rng(6)
    data = rng.standard_normal((8, 1000))
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
    kwargs = dict(orientation="superficial_to_deep", fs=1000.0, n_surrogates=50, rng=0,
                  pitch_um=50.0)
    assert jnwb.zflip(data, **kwargs).accepted
    data[4] = 1.0
    res = jnwb.zflip(data, **kwargs)
    # The pairs the constant contact touches have no wPLI and no null; the others draw theirs.
    assert res.adjacent_identifiable.tolist() == [True, True, True, False, False]
    assert "Contact(s) [4] constant" in res.rejection_reason
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
    kwargs = dict(fs=1000.0, orientation="superficial_to_deep", n_surrogates=50, rng=0)
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
    res = jnwb.zflip(data, fs=1000.0, orientation="superficial_to_deep", n_surrogates=50,
                     rng=0)
    assert res.adjacent_identifiable.all() and res.delay_identifiable
    assert res.tau_per_channel_s == pytest.approx(0.002, rel=0.05)


def test_zflip_a_linear_drift_does_not_lower_the_in_band_fraction():
    """A clean wave on a drift of 0 to 500 SD keeps its delay, and its fraction stays high.

    A per-segment mean removal leaves each segment's slope, whose power brings the fraction
    to 0.075; a linear detrend keeps it at 0.74. Undetrended, it is below the default.
    """
    data = _wave_with_contact_4(0.0, wave_scale=1.0)
    data += np.linspace(0.0, 500.0 * np.std(data[0]), data.shape[1])
    kwargs = dict(fs=1000.0, orientation="superficial_to_deep", n_surrogates=50, rng=0)
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
    res = jnwb.zflip(data, fs=1000.0, orientation="superficial_to_deep", n_surrogates=50,
                     rng=0)
    assert res.adjacent_identifiable[:3].all()
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
                     orientation="superficial_to_deep", n_surrogates=50, rng=0)
    assert res.adjacent_identifiable.all() and not res.delay_identifiable
    assert np.isnan(res.tau_per_channel_s)
    assert "Cumulative delay not linear in contact index" in res.rejection_reason
    assert "Phase-frequency relation failed" not in res.rejection_reason


def test_zflip_shared_slow_power_does_not_bias_the_delay():
    """A 2 Hz component at 30 SD shared by every contact leaves the delay within 5%.

    Undetrended, its window leakage into the band biased the phase slope and raised the delay
    by 12%. What would pass while it leaks: checking only that the delay is identifiable,
    which it stays.
    """
    rows = _lagged_rows([0, 2, 4, 6, 8])
    kwargs = dict(fs=1000.0, orientation="superficial_to_deep", n_surrogates=50, rng=0)
    clean = jnwb.zflip(rows, **kwargs).tau_per_channel_s
    t = np.arange(rows.shape[1]) / 1000.0
    slow = 30.0 * np.std(rows[0]) * np.sin(2 * np.pi * 2.0 * t)
    res = jnwb.zflip(rows + slow, **kwargs)
    assert res.delay_identifiable
    assert res.tau_per_channel_s == pytest.approx(clean, rel=0.05)


def _unit_sd_lagged_rows(n, seed, lags=(0, 2, 4, 6, 8)):
    sos = signal.butter(4, (10, 40), btype="band", fs=1000.0, output="sos")
    src = signal.sosfiltfilt(sos, np.random.default_rng(seed).standard_normal(n + 400))
    src /= src.std()
    return np.stack([src[400 - lag: 400 - lag + n] for lag in lags])


def test_zflip_shared_slow_power_does_not_inflate_the_surrogate_null():
    """A weak wave in noise stays significant with a shared 2 Hz component at 30 SD.

    The surrogates randomise each contact's phases, so a shared slow component becomes five
    independent ones whose leakage raises the null's wPLI. Undetrended, p was 0.49 here.
    What would pass while the null is inflated: a test with ``n_surrogates=0``, or one
    whose observed statistic is also undetrended.
    """
    rows = _unit_sd_lagged_rows(4000, 5)
    t = np.arange(rows.shape[1]) / 1000.0
    data = (0.2 * rows + np.random.default_rng(99).standard_normal(rows.shape)
            + 30.0 * np.sin(2 * np.pi * 2.0 * t))
    res = jnwb.zflip(data, fs=1000.0, orientation="superficial_to_deep", n_surrogates=50,
                     rng=0, min_wpli=0.0)
    assert res.p_value <= 0.05


def test_zflip_a_contact_that_is_an_exact_ramp_is_refused_like_a_constant_one():
    """A contact that is a straight line in time gives its pairs no wPLI and no delay.

    The per-segment linear detrend reduces it to round-off residue, which is not constant
    to ``is_constant`` and here fitted a delay five times the true one and was accepted.
    What would pass while the residue still counts: a ramp small enough to be refused by the
    in-band fraction anyway, which this one, at an offset of 75, is not.
    """
    rows = _unit_sd_lagged_rows(8000, 11)
    rows[4] = 74.80228477667097 + 0.006342194754924158 * np.arange(8000) / 8000
    res = jnwb.zflip(rows, fs=1000.0, orientation="superficial_to_deep", pitch_um=100.0,
                     n_surrogates=50, rng=0)
    assert np.isnan(res.adjacent_wpli[3]) and not res.adjacent_identifiable[3]
    assert not res.delay_identifiable and not res.accepted
    assert "Contact(s) [4] linear in time to round-off" in res.rejection_reason


def test_zflip_a_cumsum_built_ramp_is_refused_as_linear_in_time():
    """A ramp built by cumulative summation is refused although its round-off is not exact."""
    rows = _unit_sd_lagged_rows(8000, 11)
    rows[4] = 3.0 + np.cumsum(np.full(8000, 0.1))
    res = jnwb.zflip(rows, fs=1000.0, orientation="superficial_to_deep", n_surrogates=0)
    assert np.isnan(res.adjacent_wpli[3]) and not res.adjacent_identifiable[3]
    assert "Contact(s) [4] linear in time to round-off" in res.rejection_reason


def test_zflip_a_long_cumsum_ramp_is_refused_as_linear_in_time():
    """At 1e5 samples a cumulative-sum ramp left a line-fit residual of about 3400 eps,
    beyond the old 1000-eps width, so it was measured as a contact. Its second difference
    stays at the round-off of single samples."""
    rows = np.random.default_rng(0).normal(size=(5, 100_000))
    rows[2] = 3.0 + np.cumsum(np.full(100_000, 1e-3))
    res = jnwb.zflip(rows, fs=1000.0, orientation="superficial_to_deep", n_surrogates=0)
    assert "Contact(s) [2] linear in time to round-off" in res.rejection_reason


@pytest.mark.parametrize("n", [16, 1000, 100_000])
def test_the_ramp_rule_flags_every_ramp_construction(n):
    from jnwb.laminar._zflip import _linear_to_roundoff

    ramps = np.array([3.0 + np.cumsum(np.full(n, 1e-3)), -1e6 + 7.0 * np.arange(n),
                      np.linspace(1e11, 1e11 + 5.0 * n, n)])
    assert _linear_to_roundoff(ramps).all()


def test_the_ramp_rule_flags_the_worst_ramps_measured():
    """The ramps above reach only 0.58 eps, so a threshold anywhere above that passed them.
    These are the worst constructions measured: a short linspace at 1.0 eps, a long cumsum at
    0.86, and a ramp at the bottom of a binade moved by -1, 0 or +1 ulp per sample at 2.2."""
    from jnwb.laminar._zflip import _linear_to_roundoff

    base = 1.0 + 1e-12 * np.arange(10_000)
    steps = np.random.default_rng(0).integers(-1, 2, size=base.size)
    rows = [np.linspace(1.0, 1.0 + 1.6e-5, 16),
            1.0 + np.cumsum(np.full(100_000, 1e-9)),
            base + steps * np.spacing(base)]
    eps = np.finfo(float).eps
    measured = [np.sqrt(np.mean(np.diff(r, 2) ** 2)) / (eps * np.max(np.abs(r))) for r in rows]
    assert measured[0] > 0.99 and measured[1] > 0.8 and measured[2] > 2.1, measured
    for row in rows:
        assert _linear_to_roundoff(row[None])[0]


def test_the_ramp_rule_keeps_a_signal_with_real_curvature():
    """A unit 15 Hz sine on an offset of 1e12 has a second difference of about 28 eps of its
    magnitude: kept at the threshold of 4, flagged by a threshold of 30 or more. A parabola
    is curved everywhere and is kept at any threshold near it."""
    from jnwb.laminar._zflip import _linear_to_roundoff

    t = np.arange(8000) / 1000.0
    rows = np.array([1e12 + np.sin(2 * np.pi * 15.0 * t), (t - 4.0) ** 2])
    assert _linear_to_roundoff(rows).tolist() == [False, False]


def test_zflip_a_signal_on_a_large_offset_is_not_refused_as_linear_in_time():
    """A unit-SD contact on an offset of 1e11 keeps its delay.

    Its residual measures about 4.5e4 eps of its magnitude. A width widened towards that
    refuses a real signal as a straight line.
    """
    rows = _unit_sd_lagged_rows(8000, 11)
    kwargs = dict(fs=1000.0, orientation="superficial_to_deep", n_surrogates=50, rng=0)
    clean = jnwb.zflip(rows, **kwargs).tau_per_channel_s
    rows[4] = rows[4] + 1e11
    res = jnwb.zflip(rows, **kwargs)
    assert "linear in time" not in (res.rejection_reason or "")
    assert res.adjacent_identifiable.all() and res.delay_identifiable and res.accepted
    assert res.tau_per_channel_s == pytest.approx(clean, rel=1e-3)


def test_zflip_a_contact_independent_of_the_others_is_refused_by_its_pair_surrogates():
    """An end contact carrying independent noise blocks the delay through its own pair's test.

    Contact 0 of a 2-sample-per-contact wave is replaced by independent 10-40 Hz noise. Its
    pair still fits R^2 0.84 and wPLI 0.20, above both thresholds, and the three coupled
    pairs carry the mean past its surrogate test, so without a per-pair test the shaft was
    accepted with a delay 5 times the true one. What would pass while the pair still counts:
    checking ``accepted`` on a case the mean test or the pair thresholds already refuse,
    which is why those are asserted to pass here.
    """
    rows = _unit_sd_lagged_rows(8000, 11)
    sos = signal.butter(4, (10, 40), btype="band", fs=1000.0, output="sos")
    x = signal.sosfiltfilt(sos, np.random.default_rng(10035).standard_normal(8000))
    rows[0] = x / x.std()
    res = jnwb.zflip(rows, fs=1000.0, orientation="superficial_to_deep", pitch_um=100.0,
                     n_surrogates=50, rng=0)
    assert res.adjacent_wpli[0] >= 0.15 and res.adjacent_linearity_r2[0] >= 0.70
    assert res.p_value <= 0.05 and res.mean_wpli >= 0.15
    assert res.adjacent_identifiable.tolist() == [False, True, True, True]
    assert not res.delay_identifiable and not res.accepted
    assert np.isnan(res.tau_per_channel_s) and res.apparent_velocity_m_s is None
    assert "[(0, 1)] wPLI not significant against its own phase surrogates" in (
        res.rejection_reason)


def test_zflip_identical_contacts_give_no_direction():
    """Identical contacts have no delay gradient: phase residue near 1e-21 s is not a sign.

    With both pair thresholds at 0.0 their pairs have wPLI exactly 0.0, which every surrogate
    ties, so each pair fails its own surrogate test before the depth fit is reached.
    """
    res = jnwb.zflip(_lagged_rows([0, 0, 0, 0, 0]), fs=1000.0,
                     orientation="superficial_to_deep", n_surrogates=50, rng=0, min_wpli=0.0,
                     min_linearity_r2=0.0)
    assert np.all(res.adjacent_wpli == 0.0) and not res.adjacent_identifiable.any()
    assert not res.delay_identifiable and np.isnan(res.tau_per_channel_s)
    assert res.directionality == "unidentifiable"
    assert "wPLI not significant against its own phase surrogates" in res.rejection_reason


def test_zflip_a_pair_wpli_equal_to_min_wpli_passes_the_pair_gate():
    """The pair gate is ``wPLI >= min_wpli``, inclusive at the threshold.

    Four contacts lagged 2 samples each; contact 3 carries independent noise at its own SD,
    so pair (2, 3) is the weakest and still passes its surrogate test. With ``min_wpli`` set
    to that pair's wPLI every pair passes, and one ulp above it that pair is refused. A strict
    ``>`` refuses it at equality; a reversed ``<=`` refuses the stronger pairs.
    """
    rng = np.random.default_rng(0)
    b, a = signal.butter(4, [10.0, 40.0], btype="band", fs=1000.0)
    src = signal.filtfilt(b, a, rng.normal(size=4100))
    data = np.stack([src[100 - 2 * k: 100 - 2 * k + 4000] for k in range(4)])
    data[3] += np.std(src) * np.random.default_rng(5).normal(size=4000)
    kwargs = dict(orientation="superficial_to_deep", fs=1000.0, n_surrogates=50, rng=0)
    w = jnwb.zflip(data, min_wpli=0.0, **kwargs).adjacent_wpli
    assert np.argmin(w) == 2 and w[2] < w[:2].min()
    res = jnwb.zflip(data, min_wpli=float(w[2]), **kwargs)
    assert res.adjacent_identifiable.tolist() == [True, True, True]
    assert "wPLI below min_wpli" not in (res.rejection_reason or "")
    over = jnwb.zflip(data, min_wpli=float(np.nextafter(w[2], 1.0)), **kwargs)
    assert over.adjacent_identifiable.tolist() == [True, True, False]


def test_zflip_a_contact_of_tiny_amplitude_is_not_constant():
    """Constancy is exact: a contact scaled by 1e-9 is measured, not dropped as flat.

    wPLI and the cross-spectral phase are unchanged by scaling one contact, so the scaled
    run must match the unscaled one. A tolerance on the peak-to-peak range (``ptp < 1e-6``)
    calls this 2e-9 contact constant and turns its two pairs NaN.
    """
    kwargs = dict(orientation="superficial_to_deep", fs=1000.0, n_surrogates=50, rng=0)
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
    rng = np.random.default_rng(7)
    data = rng.standard_normal((5, 1000))
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
    # Equal p-values prove nothing unless the seed moves p: two fixed seeds give
    # different p, and fresh draws record different seeds.
    assert _zflip_noise(0).p_value != _zflip_noise(1).p_value
    assert _zflip_noise(None).surrogate_seed_entropy != first.surrogate_seed_entropy


def test_zflip_an_int_seed_is_recorded_and_keeps_its_stream(monkeypatch):
    """An int seed draws `default_rng(seed)`, the stream a Generator consumed in place drew
    before the child seed."""
    import jnwb._rng
    from jnwb.laminar import _zflip

    res = _zflip_noise(123)
    assert res.surrogate_seed_entropy == 123
    monkeypatch.setattr(_zflip, "recorded_rng", jnwb._rng.surrogate_rng)
    assert res.p_value == _zflip_noise(np.random.default_rng(123)).p_value


def test_zflip_a_generator_records_the_child_seed_that_reproduces_p():
    """A `Generator` recorded None; one child draw now seeds the surrogates and is recorded."""
    first = _zflip_noise(np.random.default_rng(1))
    assert isinstance(first.surrogate_seed_entropy, int)
    assert _zflip_noise(first.surrogate_seed_entropy).p_value == first.p_value
    assert first.surrogate_seed_entropy == int(
        np.random.default_rng(1).integers(0, 2**63 - 1))


def _delayed_copies(n_contacts, tau_s=1e-3, fs=1000.0, n=4000):
    """One broadband signal on every contact, delayed by `tau_s` more at each."""
    spectrum = np.fft.rfft(np.random.default_rng(0).normal(size=n))
    f = np.fft.rfftfreq(n, 1.0 / fs)
    return np.array([np.fft.irfft(spectrum * np.exp(-2j * np.pi * f * k * tau_s), n=n)
                     for k in range(n_contacts)])


def test_zflip_pairs_a_flat_contact_does_not_touch_draw_their_own_nulls():
    """A flat contact skipped the surrogates for the whole shaft, so pairs it does not
    touch were refused for want of a null they could have drawn."""
    lfp = np.vstack([_delayed_copies(4), np.full((1, 4000), 3.0)])
    res = jnwb.zflip(lfp, 1000.0, orientation="superficial_to_deep", n_surrogates=30, rng=0)
    assert res.adjacent_identifiable.tolist() == [True, True, True, False]
    assert np.allclose(res.adjacent_delays_s[:3], 1e-3, rtol=0.05)
    assert np.isnan(res.adjacent_delays_s[3]) and np.isnan(res.p_value)
    assert not res.accepted and res.surrogate_seed_entropy == 0


def test_zflip_a_zero_delay_gradient_has_no_direction_and_no_velocity(monkeypatch):
    """No input is known to reach the zero-gradient guard, so the spatial fit is patched to
    return a zero slope on a recording whose every pair is identifiable."""
    from jnwb.laminar import _zflip

    real = _zflip.stats.linregress

    def spatial_slope_zero(x, y):
        res = real(x, y)
        if np.array_equal(x, np.arange(len(x), dtype=float)):
            return type("Fit", (), {"slope": 0.0, "rvalue": 1.0})()
        return res

    monkeypatch.setattr(_zflip.stats, "linregress", spatial_slope_zero)
    res = jnwb.zflip(_delayed_copies(4), 1000.0, orientation="superficial_to_deep",
                     pitch_um=50.0, n_surrogates=30, rng=0)
    assert res.adjacent_identifiable.all()
    assert res.directionality == "unidentifiable" and res.apparent_velocity_m_s is None
    assert "zero to round-off" in res.rejection_reason


def test_zflip_an_untested_fit_records_none():
    assert _zflip_noise(3, n_surrogates=0).surrogate_seed_entropy is None


@pytest.mark.parametrize("bad", [2.7, True, np.random.SeedSequence(3), [1, 2]])
def test_zflip_refuses_an_rng_outside_int_generator_none(bad):
    with pytest.raises(TypeError, match="rng"):
        _zflip_noise(bad, n_surrogates=5)


# Sign, units, identifiability and inference against constructed truth
#
# zFLIP sign, units, identifiability and inference against constructed truth.
#
# Contact ``c`` is a band-limited source delayed by ``c * dt`` through an exact
# frequency-domain shift, so the per-contact delay ``dt`` and the apparent velocity
# ``pitch / dt`` are known by construction, independently of the implementation.
#
# Failures these tests discriminate:
#
# - a non-identifiable pair's delay entered the spatial fit (one incoherent contact
#   biased the estimate by ~16%; on 3 contacts a wrong-sign delay was accepted);
# - ``n_surrogates=0`` accepted without any test, and ``alpha`` was unchecked;
# - NaN input was processed, and a rejected result reported wPLI 0.0;
# - a single STFT segment saturated adjacent wPLI at 1.0 for any input;
# - an absolute cutoff made acceptance depend on amplitude units.



FS = 1000.0
N = 40000
DT = 0.001
PITCH_UM = 50.0
BAND = (15.0, 35.0)
FREQS = np.fft.rfftfreq(N, d=1.0 / FS)


def _source(seed, n=N):
    rng = np.random.default_rng(seed)
    b, a = signal.butter(4, [5.0 / (FS / 2), 60.0 / (FS / 2)], btype="band")
    return signal.filtfilt(b, a, rng.normal(size=n))


def _shift(x, delay_s):
    return np.fft.irfft(np.fft.rfft(x) * np.exp(-2j * np.pi * FREQS * delay_s), n=N)


def _wave(n_channels=12, dt=DT, seed=0, noise=0.05):
    rng = np.random.default_rng(seed + 1000)
    s = _source(seed)
    return np.array([_shift(s, c * dt) + noise * rng.normal(size=N) for c in range(n_channels)])


def _zflip(lfp, **kwargs):
    params = dict(orientation="superficial_to_deep", fs=FS, pitch_um=PITCH_UM, freq_range=BAND, n_surrogates=19, seed=1)
    params.update(kwargs)
    return jnwb.zflip(lfp, **params)


@pytest.fixture(scope="module")
def wave():
    return _wave()


class TestGroundTruth:
    def test_delay_and_velocity_units(self, wave):
        res = _zflip(wave)
        assert res.accepted
        assert res.tau_per_channel_s == pytest.approx(DT, rel=0.03)
        assert res.apparent_velocity_m_s == pytest.approx(PITCH_UM * 1e-6 / DT, rel=0.03)
        # Single pairs scatter (observed up to ~9%); the spatial slope is the estimate.
        assert np.allclose(res.adjacent_delays_s, DT, rtol=0.15)

    def test_reversed_contact_order_negates_delay_and_direction(self, wave):
        fwd, rev = _zflip(wave), _zflip(wave[::-1])
        assert fwd.directionality == "superficial_to_deep"
        assert rev.directionality == "deep_to_superficial"
        assert rev.tau_per_channel_s == pytest.approx(-fwd.tau_per_channel_s, rel=1e-9)
        assert rev.apparent_velocity_m_s == pytest.approx(fwd.apparent_velocity_m_s, rel=1e-9)

    def test_a_tip_first_table_names_the_same_anatomical_direction(self, wave):
        """`wave` runs from row 0, so with row 0 superficial the superficial end leads. The
        same recording read from a tip-first electrode table has its rows reversed; the
        direction was named from row order alone, so that table was reported as
        deep-to-superficial and accepted."""
        tip_first = _zflip(wave[::-1], orientation="deep_to_superficial")
        assert tip_first.accepted
        assert tip_first.directionality == "superficial_to_deep"
        assert tip_first.orientation == "deep_to_superficial"
        assert tip_first.to_dict()["orientation"] == "deep_to_superficial"

    @pytest.mark.parametrize("orientation", [None, "auto", "tip_first"])
    def test_a_direction_in_depth_needs_the_contact_order(self, wave, orientation):
        with pytest.raises(ValueError, match="row 0 is the most superficial"):
            _zflip(wave, orientation=orientation)

    def test_the_contact_order_has_no_default(self, wave):
        with pytest.raises(TypeError, match="orientation"):
            jnwb.zflip(wave, fs=FS, freq_range=BAND, n_surrogates=0)

    def test_pitch_scales_velocity_not_delay(self, wave):
        a, b = _zflip(wave), _zflip(wave, pitch_um=2 * PITCH_UM)
        assert b.tau_per_channel_s == a.tau_per_channel_s
        assert b.apparent_velocity_m_s == pytest.approx(2 * a.apparent_velocity_m_s, rel=1e-12)

    @pytest.mark.parametrize("scale", [1e-6, 1e3])
    def test_amplitude_units_do_not_change_the_result(self, wave, scale):
        a, b = _zflip(wave), _zflip(wave * scale)
        assert b.accepted == a.accepted
        assert b.mean_wpli == pytest.approx(a.mean_wpli, rel=1e-9)
        assert b.tau_per_channel_s == pytest.approx(a.tau_per_channel_s, rel=1e-9)


class TestDocumentedEstimatorLimits:
    """The docstring states what the delay measures; these check those statements."""

    def test_equal_power_zero_lag_mixing_halves_the_delay(self):
        rng = np.random.default_rng([7, 1])
        s, common = _source(0), _source(7)
        lfp = np.array([_shift(s, c * DT) + common + 0.05 * rng.normal(size=N) for c in range(12)])
        res = _zflip(lfp)
        assert res.tau_per_channel_s == pytest.approx(DT / 2, rel=0.15)

    def test_frequency_dependent_delay_reports_the_group_delay(self):
        rng = np.random.default_rng(8)
        s = np.fft.rfft(_source(0))
        dt_f = DT * (1 + 0.03 * (FREQS - 25.0))  # phase delay 1.0 ms at 25 Hz
        lfp = np.array([
            np.fft.irfft(s * np.exp(-2j * np.pi * FREQS * c * dt_f), n=N) + 0.05 * rng.normal(size=N)
            for c in range(12)
        ])
        # d/df [f * dt(f)] averaged over 15-35 Hz is 1.75 ms.
        assert _zflip(lfp).tau_per_channel_s == pytest.approx(1.75e-3, rel=0.10)


class TestIdentifiability:
    def test_one_incoherent_contact_makes_delay_unavailable(self, wave):
        lfp = wave.copy()
        lfp[4] = _source(104)
        res = _zflip(lfp)
        assert not res.adjacent_identifiable[3] or not res.adjacent_identifiable[4]
        assert not res.delay_identifiable
        assert not res.accepted
        assert np.isnan(res.tau_per_channel_s)
        assert res.apparent_velocity_m_s is None

    def test_three_contacts_with_one_incoherent_pair_are_not_accepted(self, wave):
        lfp = wave[:3].copy()
        lfp[2] = _source(55)
        res = _zflip(lfp)
        assert not res.accepted
        assert np.isnan(res.tau_per_channel_s)
        assert res.directionality == "unidentifiable"

    def test_constant_phase_offset_has_high_wpli_but_no_delay(self):
        rng = np.random.default_rng(9)
        s = np.fft.rfft(_source(0))
        lfp = np.array([
            np.fft.irfft(s * np.exp(-1j * np.deg2rad(60) * c), n=N) + 0.05 * rng.normal(size=N)
            for c in range(12)
        ])
        res = _zflip(lfp)
        assert res.mean_wpli > 0.9
        assert not res.delay_identifiable
        assert not res.accepted

    def test_delay_beyond_the_unambiguous_interval_is_not_accepted(self):
        assert not _zflip(_wave(dt=0.200)).accepted


class TestInference:
    def test_no_surrogate_test_means_no_acceptance(self, wave):
        """Without surrogates no pair has its null, so no delay is reported at all."""
        assert _zflip(wave).accepted
        res = _zflip(wave, n_surrogates=0)
        assert np.isnan(res.p_value)
        assert not res.adjacent_identifiable.any() and not res.delay_identifiable
        assert np.isnan(res.tau_per_channel_s) and res.apparent_velocity_m_s is None
        assert res.directionality == "unidentifiable"
        assert not res.accepted
        assert "not performed" in res.rejection_reason
        assert "surrogates are needed to establish a delay" in res.rejection_reason

    @pytest.mark.parametrize("n_surrogates", [-1, 2.5])
    def test_invalid_surrogate_count_is_rejected(self, wave, n_surrogates):
        with pytest.raises(ValueError, match="n_surrogates"):
            _zflip(wave, n_surrogates=n_surrogates)

    @pytest.mark.parametrize("alpha", [0.0, 1.0, 2.0, -0.1])
    def test_alpha_outside_the_unit_interval_is_rejected(self, wave, alpha):
        with pytest.raises(ValueError, match="alpha"):
            _zflip(wave, alpha=alpha)

    @pytest.mark.parametrize("name", ["min_linearity_r2", "min_wpli"])
    def test_threshold_outside_the_unit_interval_is_rejected(self, wave, name):
        with pytest.raises(ValueError, match=name):
            _zflip(wave, **{name: 1.5})

    def test_independent_contacts_are_not_accepted(self):
        lfp = np.array([_source(200 + c) for c in range(12)])
        assert not _zflip(lfp).accepted

    def test_seeded_result_is_reproducible_without_touching_global_rng(self, wave):
        state = np.random.get_state()[1][:8].copy()
        a, b = _zflip(wave, seed=3), _zflip(wave, seed=3)
        assert a.p_value == b.p_value
        assert np.array_equal(state, np.random.get_state()[1][:8])


class TestUnavailableStates:
    def test_non_finite_input_is_rejected(self, wave):
        lfp = wave.copy()
        lfp[2, 10] = np.nan
        with pytest.raises(ValueError, match="finite"):
            _zflip(lfp)

    @pytest.mark.parametrize("freq_range", [(35.0, 15.0), (-5.0, 10.0), (15.0, np.inf)])
    def test_malformed_band_is_rejected(self, wave, freq_range):
        with pytest.raises(ValueError, match="freq_range"):
            _zflip(wave, freq_range=freq_range)

    def test_too_few_bins_reports_nan_not_zero(self, wave):
        res = _zflip(wave, freq_range=(20.0, 20.02))
        assert not res.accepted
        assert np.isnan(res.mean_wpli)
        assert np.all(np.isnan(res.adjacent_wpli))
        assert "Insufficient frequency bins" in res.rejection_reason

    def test_single_segment_is_rejected(self):
        with pytest.raises(ValueError, match=r"not identifiable from 1 Welch segment"):
            jnwb.zflip(np.random.default_rng(0).normal(size=(6, 2048)), orientation="superficial_to_deep", fs=FS, nperseg=2048)

    @pytest.mark.parametrize("n_samples", [256, 511])
    def test_short_default_segmentation_does_not_saturate_wpli(self, n_samples):
        lfp = np.random.default_rng(1).normal(size=(6, n_samples))
        res = jnwb.zflip(lfp, orientation="superficial_to_deep", fs=FS, freq_range=BAND, n_surrogates=19, seed=0)
        assert res.mean_wpli < 0.999
        assert not res.accepted


class TestSignConventionFromGroundTruth:
    """The sign convention is established from constructed truth, not from the code.

    Every test above survives a globally inverted convention: reversing the contact
    order flips the label either way, and the velocity magnitude is unsigned. These
    pin the absolute direction, the slope formula, and the fact that a wPLI magnitude
    never decides a signed direction.
    """

    @staticmethod
    def _variable_length_wave(n_samples, dt=DT, n_channels=6, seed=0, noise=0.05):
        rng = np.random.default_rng(seed + 2000)
        source = _source(seed, n=n_samples)
        spectrum = np.fft.rfft(source)
        freqs = np.fft.rfftfreq(n_samples, d=1.0 / FS)
        return np.array([
            np.fft.irfft(spectrum * np.exp(-2j * np.pi * freqs * (c * dt)), n=n_samples)
            + noise * rng.normal(size=n_samples)
            for c in range(n_channels)
        ])

    def test_reported_direction_matches_the_constructed_direction(self, wave):
        """Contact c lags c-1 by dt > 0, so the wave runs toward increasing index."""
        result = _zflip(wave)
        assert result.delay_identifiable
        assert result.tau_per_channel_s > 0
        assert result.directionality == "superficial_to_deep"

    def test_phase_slope_convention_matches_an_independent_oracle(self, wave):
        """tau = -(1/2pi) d(phase)/df for the cross-spectrum conj(X_c) X_{c+1}."""
        freqs, _, spectra = signal.stft(
            wave, fs=FS, nperseg=256, noverlap=128, boundary=None, padded=False, axis=-1
        )
        band = (freqs >= BAND[0]) & (freqs <= BAND[1])
        cross = (np.conj(spectra[0]) * spectra[1]).mean(axis=-1)[band]
        slope = np.polyfit(freqs[band], np.unwrap(np.angle(cross)), 1)[0]
        oracle_tau = -slope / (2.0 * np.pi)

        assert oracle_tau == pytest.approx(DT, rel=0.10)
        assert float(np.asarray(_zflip(wave).adjacent_delays_s)[0]) == pytest.approx(
            oracle_tau, rel=0.10
        )

    @pytest.mark.parametrize("dt_ms", [0.25, 0.5, 1.0, 2.0])
    def test_the_estimate_tracks_the_constructed_delay_across_its_range(self, dt_ms):
        """A constant scale error passes a single-delay check; this does not."""
        result = _zflip(_wave(dt=dt_ms / 1000.0))
        assert result.tau_per_channel_s * 1e3 == pytest.approx(dt_ms, rel=0.08)
        assert result.apparent_velocity_m_s == pytest.approx(
            (PITCH_UM * 1e-6) / (dt_ms / 1000.0), rel=0.08
        )

    def test_velocity_is_unsigned_while_the_delay_carries_the_sign(self, wave):
        forward, reverse = _zflip(wave), _zflip(wave[::-1])
        assert forward.apparent_velocity_m_s == pytest.approx(
            reverse.apparent_velocity_m_s, rel=1e-6
        )
        assert np.sign(forward.tau_per_channel_s) == -np.sign(reverse.tau_per_channel_s)

    def test_wpli_magnitude_does_not_decide_the_direction(self, wave):
        """Same coupling strength, opposite travel: only the phase slope may differ."""
        forward, reverse = _zflip(wave), _zflip(wave[::-1])
        assert forward.mean_wpli == pytest.approx(reverse.mean_wpli, rel=1e-6)
        assert forward.directionality != reverse.directionality
        assert {forward.directionality, reverse.directionality} == {
            "superficial_to_deep",
            "deep_to_superficial",
        }

    @pytest.mark.parametrize("n_samples", [512, 2048, 40000])
    def test_a_clean_wave_is_detected_at_every_supported_length(self, n_samples):
        """The N // 2 default keeps enough bins in the fit band at short lengths.

        Under the coherence family's N // 8 the same wave is rejected at N = 256 and
        N = 512 (32 and 64 samples per segment leave under three bins in 15-35 Hz);
        at N >= 1024 the two rules agree. That is why zflip does not share it. 199
        surrogates: at 512 samples 19 left the pair test passing in 14 of 20 seeds.
        """
        result = _zflip(self._variable_length_wave(n_samples, noise=0.005), n_surrogates=199)
        assert result.accepted
        assert result.tau_per_channel_s > 0
        assert result.directionality == "superficial_to_deep"

    def test_three_in_band_bins_at_256_samples_cannot_show_a_pair_coupled(self):
        """At N = 256 the default band holds 3 bins, where about 10% of independent-phase
        surrogates tie a pair wPLI of 1.0, so no pair passes its own surrogate test.

        The segmentation still leaves enough bins for the phase fit: the refusal is the
        pair test's, not the frequency-support check's.
        """
        wave = self._variable_length_wave(256, noise=0.005)
        for n_surrogates in (19, 199):
            result = _zflip(wave, n_surrogates=n_surrogates)
            assert np.all(result.adjacent_wpli == 1.0) and not result.accepted
            assert np.all(result.adjacent_linearity_r2 >= 0.70)
            assert "Insufficient frequency bins" not in result.rejection_reason
            assert "wPLI not significant against its own phase surrogates" in (
                result.rejection_reason)

    @pytest.mark.parametrize("n_samples", [256, 512])
    def test_a_short_noisy_wave_is_declined_rather_than_mis_directed(self, n_samples):
        """0.25-0.5 s at 5% noise does not support a linear phase fit: adjacent R^2
        scatters from 0.05 to 0.98. The estimator must decline, not guess a sign."""
        result = _zflip(self._variable_length_wave(n_samples, noise=0.05))
        assert not result.accepted
        assert result.directionality == "unidentifiable"
        assert np.isnan(result.tau_per_channel_s)

    def test_a_constant_recording_is_not_given_a_direction(self):
        result = _zflip(np.zeros((6, 8192)))
        assert not result.accepted
        assert result.directionality == "unidentifiable"
