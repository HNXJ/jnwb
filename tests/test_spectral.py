"""Unit tests for jnwb.spectral -- generic spectral/oscillatory analysis (band power,
cross-area coherence, 1/f tilt, imaginary coherency, re-referencing).
"""
from __future__ import annotations

import numpy as np
import pytest

from jnwb.spectral import (
    to_db,
    aggregate_to_db,
    DB_AGGREGATIONS,
    harmonic_analysis,
    cross_area_coherence,
    spectral_tilt,
    band_power,
    imaginary_coherency,
    bipolar_reference,
    laplacian_reference,
    CANONICAL_BANDS,
    compute_psd,
    compute_multitaper_psd,
    voltage_curvature_1d,
    current_source_density_1d,
)


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        import jnwb
        assert jnwb.to_db is to_db
        assert jnwb.harmonic_analysis is harmonic_analysis
        assert jnwb.cross_area_coherence is cross_area_coherence
        assert jnwb.spectral_tilt is spectral_tilt
        assert jnwb.band_power is band_power
        assert jnwb.imaginary_coherency is imaginary_coherency
        assert jnwb.bipolar_reference is bipolar_reference
        assert jnwb.laplacian_reference is laplacian_reference
        assert jnwb.CANONICAL_BANDS is CANONICAL_BANDS
        assert jnwb.compute_psd is compute_psd
        assert jnwb.compute_multitaper_psd is compute_multitaper_psd
        assert jnwb.voltage_curvature_1d is voltage_curvature_1d
        assert jnwb.current_source_density_1d is current_source_density_1d

    def test_listed_in_jnwb_all(self):
        import jnwb
        for name in ("compute_psd", "compute_multitaper_psd", "voltage_curvature_1d", "current_source_density_1d"):
            assert name in jnwb.__all__


class TestComputePsd:
    def test_returns_freqs_and_psd_arrays(self):
        fs = 1000.0
        t = np.arange(0, 2.0, 1.0 / fs)
        x = np.sin(2 * np.pi * 40.0 * t)
        freqs, psd = compute_psd(x, fs)
        assert freqs.shape == psd.shape
        assert freqs[0] == pytest.approx(0.0)

    def test_peak_frequency_recovered(self):
        fs = 1000.0
        t = np.arange(0, 2.0, 1.0 / fs)
        x = np.sin(2 * np.pi * 40.0 * t)
        freqs, psd = compute_psd(x, fs)
        peak = freqs[np.argmax(psd)]
        assert abs(peak - 40.0) < 2.0

    def test_listed_in_jnwb_all(self):
        import jnwb
        for name in ("to_db", "harmonic_analysis", "cross_area_coherence", "spectral_tilt",
                     "band_power", "imaginary_coherency", "bipolar_reference",
                     "laplacian_reference", "CANONICAL_BANDS"):
            assert name in jnwb.__all__


class TestCanonicalBands:
    def test_expected_band_edges(self):
        assert CANONICAL_BANDS["theta"] == (4.0, 8.0)
        assert CANONICAL_BANDS["alpha"] == (8.0, 14.0)
        assert CANONICAL_BANDS["beta"] == (14.0, 30.0)
        assert CANONICAL_BANDS["low_gamma"] == (30.0, 50.0)
        assert CANONICAL_BANDS["high_gamma"] == (50.0, 80.0)


class TestToDb:
    def test_unity_ratio_is_zero_db(self):
        assert to_db(1.0) == pytest.approx(0.0)

    def test_ten_x_ratio_is_ten_db(self):
        assert to_db(10.0) == pytest.approx(10.0)


def _sine(freq_hz, sampling_rate=1000.0, duration_s=2.0, amplitude=1.0, phase=0.0):
    t = np.arange(0, duration_s, 1.0 / sampling_rate)
    return amplitude * np.sin(2 * np.pi * freq_hz * t + phase), t


class TestHarmonicAnalysis:
    def test_empty_input_returns_zeroed_result(self):
        result = harmonic_analysis(np.array([]), sampling_rate=1000.0)
        assert result["fundamental_freq"] == 0.0
        assert result["harmonics"] == {}

    def test_finds_fundamental_frequency_of_pure_tone(self):
        trace, _ = _sine(10.0, sampling_rate=1000.0, duration_s=4.0)
        result = harmonic_analysis(trace, sampling_rate=1000.0, freq_range=(1.0, 90.0))
        assert result["fundamental_freq"] == pytest.approx(10.0, abs=1.0)


class TestCrossAreaCoherence:
    def test_identical_signals_have_high_coherence(self):
        trace, _ = _sine(10.0, sampling_rate=1000.0, duration_s=4.0)
        result = cross_area_coherence(trace, trace, sampling_rate=1000.0, freq_bands="canonical")
        assert result["band_coherence"]["theta"] > 0.9

    def test_mismatched_lengths_return_empty_result(self):
        result = cross_area_coherence(np.zeros(100), np.zeros(50), sampling_rate=1000.0, freq_bands="canonical")
        assert result["coherence_spectrum"].size == 0

    def test_default_freq_bands_is_canonical_bands(self):
        trace, _ = _sine(10.0, sampling_rate=1000.0, duration_s=4.0)
        result = cross_area_coherence(trace, trace, sampling_rate=1000.0, freq_bands="canonical")
        assert set(result["band_coherence"].keys()) == set(CANONICAL_BANDS.keys())


class TestSpectralTilt:
    def test_empty_input_returns_zeroed_result(self):
        result = spectral_tilt(np.array([]), sampling_rate=1000.0)
        assert result["exponent"] == 0.0

    def test_pink_noise_has_negative_exponent(self):
        rng = np.random.default_rng(0)
        white = rng.standard_normal(20000)
        # crude 1/f pink noise via cumulative sum (integrated white noise)
        pink = np.cumsum(white)
        pink -= pink.mean()
        result = spectral_tilt(pink, sampling_rate=1000.0, freq_range=(1.0, 100.0))
        assert result["exponent"] < 0

    def test_flat_zero_signal_returns_clean_finite_result_without_warning(self):
        # Degenerate input: all-zero LFP trace must not throw RuntimeWarning or return NaNs
        import warnings
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            result = spectral_tilt(np.zeros(1000), sampling_rate=1000.0)
            assert len(record) == 0, f"Expected zero warnings, got: {[r.message for r in record]}"
        assert result["exponent"] == 0.0
        assert result["offset"] == 0.0
        assert result["fit_quality"] == 0.0
        assert np.isfinite(result["exponent"])
        assert np.isfinite(result["offset"])
        assert np.isfinite(result["fit_quality"])

    def test_constant_signal_returns_clean_finite_result(self):
        result = spectral_tilt(np.full(1000, 5.0), sampling_rate=1000.0)
        assert result["exponent"] == 0.0
        assert result["offset"] == 0.0
        assert result["fit_quality"] == 0.0


class TestBandPower:
    def test_empty_input_returns_zero(self):
        assert band_power(np.array([]), sampling_rate=1000.0, freq_range=(4, 8)) == 0.0

    def test_tone_in_band_has_higher_power_than_out_of_band(self):
        trace, _ = _sine(10.0, sampling_rate=1000.0, duration_s=4.0, amplitude=5.0)
        in_band = band_power(trace, fs=1000.0, freq_range=(8, 12), normalize=False)
        out_of_band = band_power(trace, fs=1000.0, freq_range=(60, 80), normalize=False)
        assert in_band > out_of_band


class TestImaginaryCoherency:
    def test_zero_lag_mixed_source_has_near_zero_icoh(self):
        rng = np.random.default_rng(1)
        source = rng.standard_normal(5000)
        x = source + 0.01 * rng.standard_normal(5000)
        y = source + 0.01 * rng.standard_normal(5000)
        result = imaginary_coherency(x, y, sampling_rate=1000.0, freq_range=(1, 100))
        assert result["coh_mag_mean"] > 0.5
        assert abs(result["icoh_mean"]) < 0.1

    def test_empty_input_returns_zeroed_result(self):
        result = imaginary_coherency(np.array([]), np.array([]), sampling_rate=1000.0, freq_range=(1, 100))
        assert result["n_freqs"] == 0


class TestBipolarReference:
    def test_drops_one_channel(self):
        data = np.arange(12, dtype=float).reshape(4, 3)
        out = bipolar_reference(data)
        assert out.shape == (3, 3)

    def test_common_signal_cancels(self):
        common = np.array([1.0, 2.0, 3.0])
        data = np.stack([common, common, common])
        out = bipolar_reference(data)
        assert np.allclose(out, 0.0)

    def test_rejects_non_2d_input(self):
        with pytest.raises(ValueError):
            bipolar_reference(np.zeros(5))


class TestLaplacianReference:
    def test_preserves_channel_count(self):
        data = np.arange(12, dtype=float).reshape(4, 3)
        out = laplacian_reference(data)
        assert out.shape == (4, 3)

    def test_common_signal_cancels_on_interior_channels(self):
        common = np.array([1.0, 2.0, 3.0])
        data = np.stack([common, common, common, common])
        out = laplacian_reference(data)
        assert np.allclose(out[1:-1], 0.0)


class TestAggregateToDb:
    """The log-last contract: aggregate ratios, take 10*log10 exactly once.

    These tests pin the *defect* the function exists to prevent, not just its happy path --
    averaging decibels is a Jensen error, and the whole point of the primitive is that the
    wrong order is unreachable through it.
    """

    def test_matches_hand_computed_log_last(self):
        power = np.array([[2.0, 4.0]])
        baseline = np.array([[1.0, 2.0]])
        # ratios 2.0 and 2.0 -> mean 2.0 -> 10*log10(2.0)
        got = aggregate_to_db(power, baseline, how="mean_of_ratios", aggregate_over=1)
        np.testing.assert_allclose(got, 10.0 * np.log10(2.0))

    def test_differs_from_averaging_decibels(self):
        """The Jensen gap is real and non-zero for any non-degenerate ratio spread."""
        power = np.array([[1.0, 100.0]])
        baseline = np.ones((1, 2))
        log_last = aggregate_to_db(power, baseline, how="mean_of_ratios", aggregate_over=1)
        log_first = np.mean(to_db(power / baseline), axis=1)
        assert not np.allclose(log_last, log_first)
        # log-last is the larger: mean(log x) <= log(mean x) by Jensen.
        assert log_last[0] > log_first[0]

    def test_two_estimands_actually_differ_when_baseline_varies(self):
        power = np.array([[1.0, 10.0]])
        baseline = np.array([[1.0, 100.0]])
        mor = aggregate_to_db(power, baseline, how="mean_of_ratios", aggregate_over=1)
        rom = aggregate_to_db(power, baseline, how="ratio_of_means", aggregate_over=1)
        assert not np.allclose(mor, rom)

    def test_estimands_coincide_when_baseline_constant(self):
        power = np.array([[2.0, 6.0]])
        baseline = np.full((1, 2), 2.0)
        mor = aggregate_to_db(power, baseline, how="mean_of_ratios", aggregate_over=1)
        rom = aggregate_to_db(power, baseline, how="ratio_of_means", aggregate_over=1)
        np.testing.assert_allclose(mor, rom)

    def test_how_is_required_keyword(self):
        with pytest.raises(TypeError):
            aggregate_to_db(np.ones(3), np.ones(3))

    def test_geometric_mean_rejected_with_reason(self):
        """geomean is mean-of-dB identically, so offering it would ship the bug."""
        r = np.array([1.0, 4.0, 16.0])
        np.testing.assert_allclose(to_db(float(np.exp(np.mean(np.log(r))))), np.mean(to_db(r)))
        with pytest.raises(ValueError, match="deliberately unsupported"):
            aggregate_to_db(np.ones(3), np.ones(3), how="geomean")

    def test_unknown_how_and_nan_policy_rejected(self):
        with pytest.raises(ValueError, match="how must be one of"):
            aggregate_to_db(np.ones(3), np.ones(3), how="median_of_ratios")
        with pytest.raises(ValueError, match="nan_policy"):
            aggregate_to_db(np.ones(3), np.ones(3), how="mean_of_ratios", nan_policy="drop")

    def test_negative_input_raises_as_db_tripwire(self):
        db_like = np.array([-3.0, 1.0, -0.5])
        with pytest.raises(ValueError, match="not ratio-scale power"):
            aggregate_to_db(db_like, np.ones(3), how="mean_of_ratios")
        with pytest.raises(ValueError, match="baseline contains negative"):
            aggregate_to_db(np.ones(3), -np.ones(3), how="mean_of_ratios")

    def test_nan_policy_propagate_vs_omit(self):
        power = np.array([[2.0, np.nan]])
        baseline = np.ones((1, 2))
        assert np.isnan(aggregate_to_db(power, baseline, how="mean_of_ratios",
                                        aggregate_over=1)[0])
        omitted = aggregate_to_db(power, baseline, how="mean_of_ratios",
                                  aggregate_over=1, nan_policy="omit")
        np.testing.assert_allclose(omitted, to_db(2.0))

    def test_no_aggregation_is_elementwise_and_logs_once(self):
        power = np.array([[2.0, 4.0]])
        baseline = np.ones((1, 2))
        np.testing.assert_allclose(
            aggregate_to_db(power, baseline, how="mean_of_ratios"), to_db(power / baseline))

    def test_broadcasts_baseline_against_power(self):
        power = np.array([[2.0, 4.0], [8.0, 16.0]])
        baseline = np.array([2.0, 4.0])
        np.testing.assert_allclose(
            aggregate_to_db(power, baseline, how="mean_of_ratios"), to_db(power / baseline))

    def test_aggregations_constant_is_the_documented_pair(self):
        assert DB_AGGREGATIONS == ("mean_of_ratios", "ratio_of_means")

    def test_importable_from_top_level(self):
        import jnwb
        assert jnwb.aggregate_to_db is aggregate_to_db
        assert jnwb.DB_AGGREGATIONS is DB_AGGREGATIONS


class TestSpectralSamplingRateResolution:
    """Verify that spectral routines accept both canonical `fs` and backwards-compatible `sampling_rate`."""

    def test_fs_and_sampling_rate_equivalence(self):
        fs = 1000.0
        t = np.arange(0, 1.0, 1.0 / fs)
        sig1 = np.sin(2 * np.pi * 10 * t)
        sig2 = np.sin(2 * np.pi * 10 * t + 0.5)

        # 1. harmonic_analysis
        res_fs = harmonic_analysis(sig1, fs=fs)
        res_sr = harmonic_analysis(sig1, sampling_rate=fs)
        assert res_fs["fundamental_freq"] == pytest.approx(res_sr["fundamental_freq"])

        # 2. cross_area_coherence
        res_coh_fs = cross_area_coherence(sig1, sig2, fs=fs, freq_bands="canonical")
        res_coh_sr = cross_area_coherence(sig1, sig2, sampling_rate=fs, freq_bands="canonical")
        np.testing.assert_allclose(res_coh_fs["frequencies"], res_coh_sr["frequencies"])
        np.testing.assert_allclose(res_coh_fs["coherence_spectrum"], res_coh_sr["coherence_spectrum"])

        # 3. spectral_tilt
        res_tilt_fs = spectral_tilt(sig1, fs=fs)
        res_tilt_sr = spectral_tilt(sig1, sampling_rate=fs)
        assert res_tilt_fs["exponent"] == pytest.approx(res_tilt_sr["exponent"])
        assert res_tilt_fs["fit_quality"] == pytest.approx(res_tilt_sr["fit_quality"])

        # 4. band_power
        bp_fs = band_power(sig1, fs=fs, freq_range=(8.0, 14.0), normalize=False)
        bp_sr = band_power(sig1, sampling_rate=fs, freq_range=(8.0, 14.0), normalize=False)
        assert bp_fs == pytest.approx(bp_sr)

        # 5. imaginary_coherency
        res_icoh_fs = imaginary_coherency(sig1, sig2, fs=fs)
        res_icoh_sr = imaginary_coherency(sig1, sig2, sampling_rate=fs)
        assert res_icoh_fs["icoh_mean"] == pytest.approx(res_icoh_sr["icoh_mean"])
        assert res_icoh_fs["coh_mag_mean"] == pytest.approx(res_icoh_sr["coh_mag_mean"])

    def test_conflicting_fs_and_sampling_rate_raises(self):
        sig = np.ones(100)
        with pytest.raises(ValueError, match="Conflicting"):
            harmonic_analysis(sig, fs=1000.0, sampling_rate=2000.0)

        with pytest.raises(ValueError, match="Conflicting"):
            cross_area_coherence(sig, sig, fs=1000.0, sampling_rate=2000.0, freq_bands="canonical")

        with pytest.raises(ValueError, match="Conflicting"):
            spectral_tilt(sig, fs=1000.0, sampling_rate=2000.0)

        with pytest.raises(ValueError, match="Conflicting"):
            band_power(sig, fs=1000.0, sampling_rate=2000.0)

        with pytest.raises(ValueError, match="Conflicting"):
            imaginary_coherency(sig, sig, fs=1000.0, sampling_rate=2000.0)

    def test_missing_both_fs_and_sampling_rate_raises(self):
        sig = np.ones(100)
        with pytest.raises(ValueError, match="requires sampling rate `fs`"):
            harmonic_analysis(sig)

        with pytest.raises(ValueError, match="requires sampling rate `fs`"):
            cross_area_coherence(sig, sig, freq_bands="canonical")

        with pytest.raises(ValueError, match="requires sampling rate `fs`"):
            spectral_tilt(sig)

        with pytest.raises(ValueError, match="requires sampling rate `fs`"):
            band_power(sig)

        with pytest.raises(ValueError, match="requires sampling rate `fs`"):
            imaginary_coherency(sig, sig)


class TestComputeMultitaperPsd:
    def test_parseval_power_recovery_white_noise(self):
        rng = np.random.default_rng(100)
        fs = 1000.0
        n_samples = 2000
        x = rng.standard_normal(n_samples)
        freqs, psd = compute_multitaper_psd(x, fs=fs, nw=3.0, k_tapers=5)
        df = freqs[1] - freqs[0]
        integrated_pwr = np.sum(psd) * df
        empirical_var = np.var(x, ddof=0)
        assert integrated_pwr == pytest.approx(empirical_var, rel=0.08)

    def test_sinusoid_frequency_recovery(self):
        fs = 1000.0
        t = np.arange(0, 2.0, 1.0 / fs)
        f0 = 35.0
        x = np.sin(2 * np.pi * f0 * t)
        freqs, psd = compute_multitaper_psd(x, fs=fs, nw=2.5)
        peak_freq = freqs[np.argmax(psd)]
        assert abs(peak_freq - f0) < 1.0

    def test_multidimensional_axes(self):
        rng = np.random.default_rng(101)
        data = rng.standard_normal((3, 500))
        freqs1, psd1 = compute_multitaper_psd(data, fs=500.0, axis=-1)
        freqs0, psd0 = compute_multitaper_psd(data.T, fs=500.0, axis=0)
        np.testing.assert_allclose(freqs1, freqs0)
        np.testing.assert_allclose(psd1, psd0.T)

    def test_zero_signal_returns_zeros(self):
        zeros = np.zeros(200)
        freqs, psd = compute_multitaper_psd(zeros, fs=100.0)
        np.testing.assert_allclose(psd, 0.0)

    def test_invalid_parameters_raise(self):
        x = np.ones(100)
        with pytest.raises(ValueError, match="strictly positive"):
            compute_multitaper_psd(x, fs=0.0)
        with pytest.raises(ValueError, match="strictly positive"):
            compute_multitaper_psd(x, fs=1000.0, nw=-1.0)
        with pytest.raises(ValueError, match="between 1 and signal length"):
            compute_multitaper_psd(x, fs=1000.0, k_tapers=0)
        with pytest.raises(ValueError, match="between 1 and signal length"):
            compute_multitaper_psd(x, fs=1000.0, k_tapers=200)

    def test_nan_raises(self):
        x = np.ones(100)
        x[10] = np.nan
        with pytest.raises(ValueError, match="NaN"):
            compute_multitaper_psd(x, fs=1000.0)


class TestVoltageCurvatureAndCSD:
    def test_known_quadratic_potential_curvature(self):
        # Full quadratic potential: V(z) = a * z^2 + b * z + c (in Volts)
        # Analytical 1st derivative: dV/dz = 2*a*z + b (in V/m)
        # Analytical 2nd derivative: d^2V/dz^2 = 2*a (in V/m^2, constant across all z)
        # Physical CSD: CSD(z) = -sigma * d^2V/dz^2 = -2 * a * sigma (in A/m^3)
        a = 3.5    # V / m^2
        b = -1.2   # V / m
        c = 0.05   # V
        pitch_um = 50.0  # 50 micrometers inter-contact spacing
        pitch_m = pitch_um * 1e-6  # 5e-5 m
        n_contacts = 12
        z_m = np.arange(n_contacts) * pitch_m  # depth in meters
        v_profile = a * (z_m ** 2) + b * z_m + c  # potential in Volts
        # Broadcast across 100 time samples
        lfp = np.tile(v_profile[:, None], (1, 100))

        # Discrete second spatial derivative: curvature in V/m^2
        curvature = voltage_curvature_1d(lfp, pitch_um=pitch_um, axis=0)
        assert curvature.shape == (n_contacts - 2, 100)
        # For any quadratic polynomial, the second central difference is exact:
        # (V(z+h) - 2*V(z) + V(z-h)) / h^2 = 2*a
        np.testing.assert_allclose(curvature, 2.0 * a, rtol=1e-6)

        # Physical CSD with physiological conductivity sigma = 0.3 S/m
        sigma = 0.3  # S/m = A / (V * m)
        csd = current_source_density_1d(lfp, pitch_um=pitch_um, conductivity_s_per_m=sigma, axis=0)
        assert csd.shape == (n_contacts - 2, 100)
        expected_csd = -sigma * (2.0 * a)  # A/m^3
        np.testing.assert_allclose(csd, expected_csd, rtol=1e-6)

    def test_pitch_squared_scaling(self):
        lfp = np.tile(np.array([1.0, 3.0, 2.0, 4.0, 1.0])[:, None], (1, 10))
        curv_50 = voltage_curvature_1d(lfp, pitch_um=50.0)
        curv_100 = voltage_curvature_1d(lfp, pitch_um=100.0)
        # Doubling pitch must reduce curvature by factor of 4 (1/delta_z^2)
        np.testing.assert_allclose(curv_50, curv_100 * 4.0)

    def test_csd_requires_positive_conductivity(self):
        lfp = np.ones((5, 10))
        with pytest.raises(ValueError, match="strictly positive"):
            current_source_density_1d(lfp, pitch_um=50.0, conductivity_s_per_m=0.0)
        with pytest.raises(ValueError, match="strictly positive"):
            current_source_density_1d(lfp, pitch_um=50.0, conductivity_s_per_m=-0.3)

    def test_too_few_channels_raises(self):
        lfp = np.ones((2, 10))
        with pytest.raises(ValueError, match="at least 3 channels"):
            voltage_curvature_1d(lfp, pitch_um=50.0)




class TestCrossAreaCoherenceSurrogateContract:
    """JNWB-003/004/005/006: the surrogate null must be seedable, single-estimator,
    of a caller-chosen size, and honestly described."""

    @staticmethod
    def _signals(n=2048, seed=7):
        rng = np.random.default_rng(seed)
        base = rng.normal(size=n)
        return base + 0.3 * rng.normal(size=n), base + 0.3 * rng.normal(size=n)

    def test_rng_is_accepted_and_changes_the_null(self):
        """JNWB-003: the null used to be unseedable, so every caller got one null."""
        x, y = self._signals()
        a = cross_area_coherence(x, y, fs=1000.0, rng=np.random.default_rng(1), freq_bands="canonical")
        b = cross_area_coherence(x, y, fs=1000.0, rng=np.random.default_rng(2), freq_bands="canonical")
        assert a['band_coherence'] == b['band_coherence'], "observed value must not depend on the RNG"
        assert a['band_significance'] != b['band_significance'], (
            "two independent nulls produced identical p-values across every band"
        )

    def test_default_rng_is_reproducible_and_reports_its_seed(self):
        x, y = self._signals()
        a = cross_area_coherence(x, y, fs=1000.0, freq_bands="canonical")
        b = cross_area_coherence(x, y, fs=1000.0, freq_bands="canonical")
        assert a['band_significance'] == b['band_significance']
        assert a['surrogate_seed_entropy'] == 42, "the default seed must be recordable in a receipt"

    def test_caller_supplied_rng_reports_no_seed(self):
        """A receipt must not claim a seed jnwb did not choose."""
        x, y = self._signals()
        out = cross_area_coherence(x, y, fs=1000.0, rng=np.random.default_rng(99), freq_bands="canonical")
        assert out['surrogate_seed_entropy'] is None

    def test_n_surrogates_sets_the_p_value_floor(self):
        """JNWB-005: the floor used to depend on input length, undisclosed."""
        x, y = self._signals()
        out = cross_area_coherence(x, y, fs=1000.0, n_surrogates=10, freq_bands="canonical")
        assert out['n_surrogates_used'] == 10
        assert out['p_value_floor'] == pytest.approx(1 / 11)
        assert min(out['band_significance'].values()) >= out['p_value_floor'] - 1e-12

    def test_default_floor_permits_rejection_at_alpha_05(self):
        """The old long-signal branch gave a floor of 1/11 = 0.0909, above alpha."""
        x, y = self._signals()
        out = cross_area_coherence(x, y, fs=1000.0, freq_bands="canonical")
        assert out['n_surrogates_used'] == 50
        assert out['p_value_floor'] == pytest.approx(1 / 51)
        assert out['p_value_floor'] < 0.05

    def test_surrogate_count_no_longer_depends_on_signal_length(self):
        """JNWB-005: len > 50000 used to silently drop 50 surrogates to 10."""
        short_x, short_y = self._signals(n=2048)
        long_x, long_y = self._signals(n=60000)
        short = cross_area_coherence(short_x, short_y, fs=1000.0, freq_bands="canonical")
        long = cross_area_coherence(long_x, long_y, fs=1000.0, freq_bands="canonical")
        assert short['n_surrogates_used'] == long['n_surrogates_used'] == 50
        assert short['p_value_floor'] == long['p_value_floor'], (
            "the smallest attainable p-value must not be a function of input length"
        )

    def test_invalid_n_surrogates_rejected(self):
        x, y = self._signals()
        with pytest.raises(ValueError, match="n_surrogates"):
            cross_area_coherence(x, y, fs=1000.0, n_surrogates=0, freq_bands="canonical")

    def test_device_used_is_reported_and_cpu_request_is_honoured(self):
        """JNWB-004: nothing in the result used to say which estimator produced it."""
        x, y = self._signals()
        out = cross_area_coherence(x, y, fs=1000.0, device='cpu', freq_bands="canonical")
        assert out['device_used'] == 'cpu'

    def test_cuda_failure_falls_back_wholesale_and_warns(self, monkeypatch):
        """A GPU failure must not yield a null that mixes two estimators."""
        import jnwb._backend as backend
        import jnwb.spectral as spectral_module

        def always_fails(*args, **kwargs):
            raise RuntimeError("simulated GPU out-of-memory")

        # Claim a GPU so the cuda branch is entered on machines without one, then fail
        # inside it -- the mid-computation failure this fallback exists for.
        monkeypatch.setattr(backend, "gpu_available", lambda prefer=None: True)
        monkeypatch.setattr(spectral_module, "_welch_csd_gpu", always_fails)
        x, y = self._signals()
        with pytest.warns(RuntimeWarning, match="recomputing"):
            out = cross_area_coherence(x, y, fs=1000.0, device='cuda', freq_bands="canonical")
        assert out['device_used'] == 'cpu', "the result must name the estimator that produced it"
        cpu = cross_area_coherence(x, y, fs=1000.0, device='cpu', freq_bands="canonical")
        assert out['band_coherence'] == cpu['band_coherence']
        assert out['band_significance'] == cpu['band_significance'], (
            "after a wholesale fallback the null must be identical to a pure CPU run"
        )

    def test_docstring_names_the_surrogate_it_actually_implements(self):
        """JNWB-006: it called a circular shift 'phase-randomized'."""
        doc = " ".join(cross_area_coherence.__doc__.lower().split())
        assert "circularly shifting" in doc or "circular shift" in doc
        assert "different null hypothesis" in doc, (
            "the docstring must say the old 'phase randomization' wording named a "
            "different null, since callers may have relied on it"
        )

    def test_band_dependence_is_documented_not_hidden(self):
        """Sharing surrogates across bands is correct, but must be stated."""
        doc = " ".join(cross_area_coherence.__doc__.lower().split())
        assert "dependent by construction" in doc
        assert "same set of surrogate signals" in doc

    def test_surrogate_spectra_are_computed_once_not_once_per_band(self, monkeypatch):
        """The old loop recomputed every surrogate spectrum inside each band.

        Identical shifts were drawn per band, so those recomputations produced
        identical spectra -- n_surrogates x n_bands estimator calls to obtain
        n_surrogates distinct results.
        """
        import jnwb.spectral as spectral_module

        calls = {"n": 0}
        real = spectral_module.signal.coherence

        def counting(*args, **kwargs):
            calls["n"] += 1
            return real(*args, **kwargs)

        monkeypatch.setattr(spectral_module.signal, "coherence", counting)
        x, y = self._signals()
        n_surr = 20
        out = cross_area_coherence(x, y, fs=1000.0, n_surrogates=n_surr, freq_bands="canonical")
        n_bands = len(out['band_coherence'])
        assert n_bands >= 2, "need several bands for this to mean anything"
        assert calls["n"] == n_surr + 1, (
            f"expected 1 observed + {n_surr} surrogate estimator calls, got {calls['n']}; "
            f"the per-band recomputation would be {1 + n_surr * n_bands}"
        )


class TestCrossAreaCoherenceBandsAreExplicit:
    """The band taxonomy decides every band p-value, so the caller names it (0.1.4)."""

    @staticmethod
    def _pair():
        gen = np.random.default_rng(5)
        base = gen.normal(size=2048)
        return base + 0.3 * gen.normal(size=2048), base + 0.3 * gen.normal(size=2048)

    def test_missing_bands_raises(self):
        x, y = self._pair()
        with pytest.raises(ValueError, match="needs freq_bands"):
            cross_area_coherence(x, y, fs=1000.0)

    def test_unknown_band_string_raises(self):
        x, y = self._pair()
        with pytest.raises(ValueError, match="'canonical'"):
            cross_area_coherence(x, y, fs=1000.0, freq_bands="standard")

    def test_canonical_equals_the_explicit_dict(self):
        from jnwb.spectral import CANONICAL_BANDS

        x, y = self._pair()
        a = cross_area_coherence(x, y, fs=1000.0, freq_bands="canonical", n_surrogates=8)
        b = cross_area_coherence(x, y, fs=1000.0, freq_bands=dict(CANONICAL_BANDS), n_surrogates=8)
        assert a["band_coherence"] == b["band_coherence"]
        assert a["band_significance"] == b["band_significance"]

    def test_custom_bands_are_used_as_given(self):
        x, y = self._pair()
        out = cross_area_coherence(x, y, fs=1000.0, freq_bands={"slow": (2.0, 6.0)}, n_surrogates=8)
        assert set(out["band_coherence"]) == {"slow"}
