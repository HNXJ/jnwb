"""0.2.4-04: zFLIP sign, units, identifiability and inference against constructed truth.

Contact ``c`` is a band-limited source delayed by ``c * dt`` through an exact
frequency-domain shift, so the per-contact delay ``dt`` and the apparent velocity
``pitch / dt`` are known by construction, independently of the implementation.

Failures these tests discriminate:

- a non-identifiable pair's delay entered the spatial fit (one incoherent contact
  biased the estimate by ~16%; on 3 contacts a wrong-sign delay was accepted);
- ``n_surrogates=0`` accepted without any test, and ``alpha`` was unchecked;
- NaN input was processed, and a rejected result reported wPLI 0.0;
- a single STFT segment saturated adjacent wPLI at 1.0 for any input;
- an absolute cutoff made acceptance depend on amplitude units.
"""

import numpy as np
import pytest
from scipy import signal

import jnwb

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
        rng = np.random.default_rng(7)
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
        res = _zflip(wave, n_surrogates=0)
        assert np.isnan(res.p_value)
        assert res.delay_identifiable
        assert not res.accepted
        assert "not performed" in res.rejection_reason

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

    @pytest.mark.parametrize("n_samples", [256, 512, 2048, 40000])
    def test_a_clean_wave_is_detected_at_every_supported_length(self, n_samples):
        """The N // 2 default keeps enough bins in the fit band at short lengths.

        Under the coherence family's N // 8 the same wave is rejected at N = 256 and
        N = 512 (32 and 64 samples per segment leave under three bins in 15-35 Hz);
        at N >= 1024 the two rules agree. That is why zflip does not share it.
        """
        result = _zflip(self._variable_length_wave(n_samples, noise=0.005))
        assert result.accepted
        assert result.tau_per_channel_s > 0
        assert result.directionality == "superficial_to_deep"

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
