"""Unit tests for jnwb.spectral -- generic spectral/oscillatory analysis (band power,
cross-area coherence, 1/f tilt, imaginary coherency, re-referencing).
"""
from __future__ import annotations

import jnwb
import numpy as np
import pytest

from jnwb.spectral import (
    to_db,
    aggregate_to_db,
    DB_AGGREGATIONS,
    harmonic_analysis,
    cross_area_coherence,
    spectral_tilt,
    AperiodicFitResult,
    aperiodic_fit,
    band_power,
    relative_power,
    RELATIVE_POWER_MODELS,
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
        assert jnwb.AperiodicFitResult is AperiodicFitResult
        assert jnwb.aperiodic_fit is aperiodic_fit
        assert jnwb.band_power is band_power
        assert jnwb.relative_power is relative_power
        assert jnwb.RELATIVE_POWER_MODELS is RELATIVE_POWER_MODELS
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
    def test_empty_input_is_rejected(self):
        """INTENTIONAL BREAK (0.2.4): returned fundamental_freq 0.0, a valid-looking frequency."""
        with pytest.raises(ValueError, match="empty"):
            harmonic_analysis(np.array([]), sampling_rate=1000.0)

    def test_constant_trace_has_no_fundamental(self):
        result = harmonic_analysis(np.full(4000, 3.0), sampling_rate=1000.0)
        assert np.isnan(result["fundamental_freq"])
        assert np.isnan(result["harmonic_ratio"])
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

    def test_mismatched_lengths_raise_rather_than_returning_zeros(self):
        """INTENTIONAL BREAK (0.2.4).

        This returned a dict of zeros with a log warning. A caller reading
        `peak_coherence_value` got 0.0, which is exactly what a genuine measurement of
        no coupling looks like, and no key in the result marked it as absent.
        """
        with pytest.raises(ValueError, match=r"must have the same length"):
            cross_area_coherence(
                np.zeros(100), np.zeros(50), sampling_rate=1000.0, freq_bands="canonical"
            )

    def test_mismatched_length_error_names_both_lengths(self):
        with pytest.raises(ValueError) as excinfo:
            cross_area_coherence(
                np.zeros(4096), np.zeros(2048), sampling_rate=1000.0, freq_bands="canonical"
            )
        message = str(excinfo.value)
        assert "4096" in message and "2048" in message

    def test_equal_lengths_are_unaffected(self):
        rng = np.random.default_rng(0)
        out = cross_area_coherence(
            rng.normal(size=4096), rng.normal(size=4096),
            sampling_rate=1000.0, freq_bands="canonical", n_surrogates=3,
        )
        assert np.asarray(out["coherence_spectrum"]).size > 0

    def test_default_freq_bands_is_canonical_bands(self):
        trace, _ = _sine(10.0, sampling_rate=1000.0, duration_s=4.0)
        result = cross_area_coherence(trace, trace, sampling_rate=1000.0, freq_bands="canonical")
        assert set(result["band_coherence"].keys()) == set(CANONICAL_BANDS.keys())


class TestSpectralTilt:
    def test_empty_input_is_rejected(self):
        with pytest.raises(ValueError, match="empty"):
            spectral_tilt(np.array([]), sampling_rate=1000.0)

    def test_pink_noise_has_negative_exponent(self):
        rng = np.random.default_rng(0)
        white = rng.standard_normal(20000)
        # crude 1/f pink noise via cumulative sum (integrated white noise)
        pink = np.cumsum(white)
        pink -= pink.mean()
        result = spectral_tilt(pink, sampling_rate=1000.0, freq_range=(1.0, 100.0))
        assert result["exponent"] < 0

    def test_flat_zero_signal_has_undefined_tilt_without_warning(self):
        """INTENTIONAL BREAK (0.2.4).

        An all-zero trace reported exponent, offset and fit quality of 0.0, which reads as a
        measured flat spectrum. It has no positive power to fit, so all three are NaN.
        """
        import warnings
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            result = spectral_tilt(np.zeros(1000), sampling_rate=1000.0)
            assert len(record) == 0, f"Expected zero warnings, got: {[r.message for r in record]}"
        assert np.isnan(result["exponent"])
        assert np.isnan(result["offset"])
        assert np.isnan(result["fit_quality"])

    def test_constant_signal_has_undefined_tilt(self):
        result = spectral_tilt(np.full(1000, 5.0), sampling_rate=1000.0)
        assert np.isnan(result["exponent"])
        assert np.isnan(result["offset"])
        assert np.isnan(result["fit_quality"])


class TestBandPower:
    def test_empty_input_is_rejected(self):
        """INTENTIONAL BREAK (0.2.4): returned 0.0, a measured absence of power."""
        with pytest.raises(ValueError, match="empty"):
            band_power(np.array([]), sampling_rate=1000.0, freq_range=(4, 8), normalize=False)

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

    def test_empty_input_is_rejected(self):
        with pytest.raises(ValueError, match="empty"):
            imaginary_coherency(np.array([]), np.array([]), sampling_rate=1000.0, freq_range=(1, 100))


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

    def test_ratio_of_means_nan_policy_omit_joint_masking(self):
        """Under ratio_of_means with nan_policy='omit', missing samples in power must not
        cause denominator to sum across samples excluded from numerator."""
        p = np.array([10.0, np.nan])
        b = np.array([10.0, 10.0])
        # Only index 0 is valid for both (10.0 / 10.0 = 1.0 -> 0.0 dB)
        omitted = aggregate_to_db(p, b, how="ratio_of_means", aggregate_over=0, nan_policy="omit")
        np.testing.assert_allclose(omitted, 0.0)

        # 2D array test with broadcasting
        p2 = np.array([[10.0, np.nan], [20.0, 30.0]])
        b2 = np.array([10.0, 10.0])
        # For column 1, row 0 is NaN in p2, so only row 1 is valid (30.0 / 10.0 = 3.0)
        omitted2 = aggregate_to_db(p2, b2, how="ratio_of_means", aggregate_over=0, nan_policy="omit")
        # col 0: (10 + 20) / (10 + 10) = 30 / 20 = 1.5 -> to_db(1.5)
        # col 1: (30) / (10) = 3.0 -> to_db(3.0)
        np.testing.assert_allclose(omitted2, [to_db(1.5), to_db(3.0)])


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

    @staticmethod
    def _uncoupled_signals(n=2048, seed=11):
        """Independent traces, so the surrogate null is not saturated.

        The coupled `_signals` pair drives every band to the p-value floor 1/(n+1)
        under the repaired estimator, which makes two different nulls indistinguishable
        for the wrong reason. Before 0.2.4 this test discriminated only because a
        single Welch segment pinned observed AND surrogate coherence at 1.0, so the
        p-values differed by tie-counting noise alone.
        """
        rng = np.random.default_rng(seed)
        return rng.normal(size=n), rng.normal(size=n)

    def test_rng_is_accepted_and_changes_the_null(self):
        """JNWB-003: the null used to be unseedable, so every caller got one null."""
        x, y = self._uncoupled_signals()
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


class TestAperiodicFit:
    def test_fixed_mode_analytic_recovery(self):
        """Verify exact parameter recovery on noise-free analytic fixed spectrum."""
        freqs = np.linspace(2.0, 100.0, 99)
        b_true = 2.5
        chi_true = 1.75
        psd = 10 ** (b_true - chi_true * np.log10(freqs))

        res = aperiodic_fit(freqs, psd, freq_range=(2.0, 100.0), mode="fixed")
        assert isinstance(res, AperiodicFitResult)
        assert res.accepted is True
        assert res.mode == "fixed"
        assert res.knee is None
        assert res.offset == pytest.approx(b_true, abs=1e-5)
        assert res.exponent == pytest.approx(chi_true, abs=1e-5)
        assert res.r_squared == pytest.approx(1.0, abs=1e-5)
        assert res.freq_range == (2.0, 100.0)

    def test_knee_mode_analytic_recovery(self):
        """Verify exact parameter recovery on noise-free analytic knee spectrum."""
        freqs = np.linspace(1.0, 150.0, 300)
        b_true = 3.0
        chi_true = 2.0
        k_true = 25.0
        psd = 10 ** (b_true - np.log10(k_true + freqs ** chi_true))

        res = aperiodic_fit(freqs, psd, freq_range=(1.0, 150.0), mode="knee")
        assert isinstance(res, AperiodicFitResult)
        assert res.accepted is True
        assert res.mode == "knee"
        assert res.offset == pytest.approx(b_true, rel=1e-3)
        assert res.exponent == pytest.approx(chi_true, rel=1e-3)
        assert res.knee == pytest.approx(k_true, rel=1e-2)
        assert res.r_squared == pytest.approx(1.0, abs=1e-3)

    def test_amplitude_scaling_changes_offset_not_exponent(self):
        """Scaling PSD by factor S increases offset by log10(S) while leaving exponent unchanged."""
        freqs = np.linspace(5.0, 80.0, 76)
        b_true = 1.2
        chi_true = 1.4
        psd = 10 ** (b_true - chi_true * np.log10(freqs))

        scale_factor = 100.0
        res_orig = aperiodic_fit(freqs, psd, freq_range=(5.0, 80.0), mode="fixed")
        res_scaled = aperiodic_fit(freqs, psd * scale_factor, freq_range=(5.0, 80.0), mode="fixed")

        assert res_scaled.exponent == pytest.approx(res_orig.exponent, abs=1e-6)
        assert res_scaled.offset == pytest.approx(res_orig.offset + np.log10(scale_factor), abs=1e-6)
        assert res_scaled.r_squared == pytest.approx(res_orig.r_squared, abs=1e-6)

    def test_mathematical_agreement_with_spectral_tilt_fitting_stage(self):
        """Verify identical regression values between aperiodic_fit (fixed) and spectral_tilt fitting math on the same PSD."""
        freqs = np.linspace(2.0, 80.0, 79)
        psd = 10 ** (2.0 - 1.5 * np.log10(freqs))

        # Directly run linear regression as implemented in spectral_tilt
        log_freqs = np.log10(freqs)
        log_power = np.log10(psd)
        tilt_coeffs = np.polyfit(log_freqs, log_power, 1)
        tilt_exponent = float(tilt_coeffs[0])
        tilt_offset_log = float(tilt_coeffs[1])

        res = aperiodic_fit(freqs, psd, freq_range=(2.0, 80.0), mode="fixed")

        # In aperiodic_fit: exponent = -slope, offset = intercept
        assert res.exponent == pytest.approx(-tilt_exponent, abs=1e-7)
        assert res.offset == pytest.approx(tilt_offset_log, abs=1e-7)

    def test_multidimensional_batch_support(self):
        """Multi-channel PSD arrays (n_channels, n_freqs) return structured list of AperiodicFitResult."""
        freqs = np.linspace(2.0, 60.0, 59)
        b_vals = [1.0, 2.0, 3.0]
        chi_vals = [1.2, 1.5, 1.8]
        psd_multi = np.array([
            10 ** (b - chi * np.log10(freqs))
            for b, chi in zip(b_vals, chi_vals)
        ])  # shape: (3, 59)

        results = aperiodic_fit(freqs, psd_multi, freq_range=(2.0, 60.0), mode="fixed")
        assert len(results) == 3
        for i, res in enumerate(results):
            assert isinstance(res, AperiodicFitResult)
            assert res.offset == pytest.approx(b_vals[i], abs=1e-5)
            assert res.exponent == pytest.approx(chi_vals[i], abs=1e-5)

    def test_dict_and_mapping_interface(self):
        """Verify mapping access and serialization methods on AperiodicFitResult."""
        freqs = np.linspace(2.0, 50.0, 49)
        psd = 10 ** (1.5 - 1.2 * np.log10(freqs))
        res = aperiodic_fit(freqs, psd, freq_range=(2.0, 50.0), mode="fixed")

        assert res["offset"] == res.offset
        assert res["exponent"] == res.exponent
        assert res.get("mode") == "fixed"
        assert res.get("unknown_key", "default_val") == "default_val"

        d = res.to_dict()
        assert isinstance(d, dict)
        assert d["offset"] == res.offset
        assert d["exponent"] == res.exponent
        assert d["accepted"] is True

    def test_determinism_repeated_calls(self):
        """Repeated evaluation yields identical numerical results."""
        freqs = np.linspace(2.0, 80.0, 80)
        psd = 10 ** (2.0 - 1.5 * np.log10(freqs))
        r1 = aperiodic_fit(freqs, psd, freq_range=(2.0, 80.0), mode="fixed")
        r2 = aperiodic_fit(freqs, psd, freq_range=(2.0, 80.0), mode="fixed")
        assert r1.offset == r2.offset
        assert r1.exponent == r2.exponent
        assert r1.r_squared == r2.r_squared

    def test_invalid_mode_raises(self):
        freqs = np.linspace(2.0, 50.0, 49)
        psd = np.ones_like(freqs)
        with pytest.raises(ValueError, match="Invalid mode 'unsupported'"):
            aperiodic_fit(freqs, psd, freq_range=(2.0, 50.0), mode="unsupported")

    def test_nonmonotonic_or_invalid_freqs_raise(self):
        freqs_non_monotonic = np.array([1.0, 5.0, 3.0, 10.0])
        psd = np.ones(4)
        with pytest.raises(ValueError, match="strictly increasing"):
            aperiodic_fit(freqs_non_monotonic, psd, freq_range=(1.0, 10.0))

        freqs_negative = np.array([-1.0, 2.0, 5.0, 10.0])
        with pytest.raises(ValueError, match="strictly positive"):
            aperiodic_fit(freqs_negative, psd, freq_range=(1.0, 10.0))

        freqs_nan = np.array([1.0, np.nan, 5.0, 10.0])
        with pytest.raises(ValueError, match="NaN or infinite"):
            aperiodic_fit(freqs_nan, psd, freq_range=(1.0, 10.0))

    def test_invalid_psd_raises(self):
        freqs = np.linspace(2.0, 50.0, 49)
        psd_zero = np.ones_like(freqs)
        psd_zero[10] = 0.0
        with pytest.raises(ValueError, match="non-positive"):
            aperiodic_fit(freqs, psd_zero, freq_range=(2.0, 50.0))

        psd_negative = np.ones_like(freqs)
        psd_negative[5] = -0.5
        with pytest.raises(ValueError, match="non-positive"):
            aperiodic_fit(freqs, psd_negative, freq_range=(2.0, 50.0))

        psd_nan = np.ones_like(freqs)
        psd_nan[3] = np.nan
        with pytest.raises(ValueError, match="NaN or infinite"):
            aperiodic_fit(freqs, psd_nan, freq_range=(2.0, 50.0))

        psd_mismatched = np.ones(20)
        with pytest.raises(ValueError, match="Trailing dimension"):
            aperiodic_fit(freqs, psd_mismatched, freq_range=(2.0, 50.0))

    def test_invalid_freq_range_raises(self):
        freqs = np.linspace(2.0, 50.0, 49)
        psd = np.ones_like(freqs)
        with pytest.raises(ValueError, match="strictly less than"):
            aperiodic_fit(freqs, psd, freq_range=(30.0, 10.0))

        with pytest.raises(ValueError, match="strictly positive"):
            aperiodic_fit(freqs, psd, freq_range=(-5.0, 20.0))

    def test_insufficient_points_raises(self):
        """Fewer than 4 bins inside freq_range raises ValueError."""
        freqs = np.array([1.0, 10.0, 20.0, 30.0, 40.0, 50.0])
        psd = np.ones_like(freqs)
        # Bins inside (15.0, 35.0) are [20.0, 30.0], i.e., 2 bins < 4
        with pytest.raises(ValueError, match="Insufficient frequency bins"):
            aperiodic_fit(freqs, psd, freq_range=(15.0, 35.0))

    def test_rejected_fit_returns_unavailable_parameters_never_zeros(self, monkeypatch):
        """When optimization fails to converge, accepted=False and parameters are None, never plausible numerical zeros."""
        freqs = np.linspace(2.0, 50.0, 49)
        psd = 10 ** (1.5 - 1.2 * np.log10(freqs))

        # 1. Fixed mode optimization failure simulation
        def _mock_polyfit_fail(*args, **kwargs):
            raise RuntimeError("Linear regression divergence")

        monkeypatch.setattr(np, "polyfit", _mock_polyfit_fail)
        res_fixed_fail = aperiodic_fit(freqs, psd, freq_range=(2.0, 50.0), mode="fixed")
        assert isinstance(res_fixed_fail, AperiodicFitResult)
        assert res_fixed_fail.accepted is False
        assert res_fixed_fail.offset is None
        assert res_fixed_fail.exponent is None
        assert res_fixed_fail.knee is None
        assert res_fixed_fail.r_squared is None
        assert res_fixed_fail.mode == "fixed"
        assert res_fixed_fail.freq_range == (2.0, 50.0)

        # 2. Knee mode optimization failure simulation
        from scipy import optimize

        def _mock_curve_fit_fail(*args, **kwargs):
            raise RuntimeError("Optimal parameters not found: maxfev reached")

        monkeypatch.setattr(optimize, "curve_fit", _mock_curve_fit_fail)
        res_knee_fail = aperiodic_fit(freqs, psd, freq_range=(2.0, 50.0), mode="knee")
        assert isinstance(res_knee_fail, AperiodicFitResult)
        assert res_knee_fail.accepted is False
        assert res_knee_fail.offset is None
        assert res_knee_fail.exponent is None
        assert res_knee_fail.knee is None
        assert res_knee_fail.r_squared is None
        assert res_knee_fail.mode == "knee"
        assert res_knee_fail.freq_range == (2.0, 50.0)


class TestRelativePower:
    def test_numerical_distinction_under_unequal_baselines(self):
        """Under unequal baselines, mean of ratios, ratio of means, and mean dB strictly diverge."""
        power = np.array([2.0, 8.0])
        baseline = np.array([1.0, 2.0])

        # 1. Linear mean of ratios: (2/1 + 8/2) / 2 = (2 + 4) / 2 = 3.0
        r_mean_of_ratios = relative_power(power, baseline, model="mean_of_ratios", axis=0)
        assert r_mean_of_ratios == pytest.approx(3.0)

        # 2. Linear ratio of means: (2 + 8) / (1 + 2) = 10 / 3 = 3.3333333333333335
        r_ratio_of_means = relative_power(power, baseline, model="ratio_of_means", axis=0)
        assert r_ratio_of_means == pytest.approx(10.0 / 3.0)

        # 3. Log ratio (elementwise dB): [10*log10(2), 10*log10(4)]
        r_log_ratio = relative_power(power, baseline, model="log_ratio")
        expected_db = np.array([10.0 * np.log10(2.0), 10.0 * np.log10(4.0)])
        np.testing.assert_allclose(r_log_ratio, expected_db)

        # Mean of decibels (the Jensen inequality defect)
        mean_db = float(np.mean(r_log_ratio))

        # 10*log10(mean of ratios) = 10*log10(3.0) = 4.7712 dB
        db_from_mean_of_ratios = float(10.0 * np.log10(r_mean_of_ratios))

        # 10*log10(ratio of means) = 10*log10(3.333) = 5.2288 dB
        db_from_ratio_of_means = float(10.0 * np.log10(r_ratio_of_means))

        # Verify all four quantities are strictly distinct
        assert r_mean_of_ratios != pytest.approx(r_ratio_of_means)
        assert db_from_mean_of_ratios != pytest.approx(db_from_ratio_of_means)
        assert mean_db != pytest.approx(db_from_mean_of_ratios)
        assert mean_db != pytest.approx(db_from_ratio_of_means)

    def test_coincidence_under_equal_baselines(self):
        """Under strictly equal baselines, mean of ratios and ratio of means coincide exactly."""
        power = np.array([4.0, 10.0])
        baseline = np.array([2.0, 2.0])

        # (4/2 + 10/2) / 2 = 7 / 2 = 3.5
        r_mor = relative_power(power, baseline, model="mean_of_ratios", axis=0)
        # (4 + 10) / (2 + 2) = 14 / 4 = 3.5
        r_rom = relative_power(power, baseline, model="ratio_of_means", axis=0)

        assert r_mor == pytest.approx(3.5)
        assert r_rom == pytest.approx(3.5)
        assert r_mor == pytest.approx(r_rom)

    def test_elementwise_mean_of_ratios_when_axis_is_none(self):
        """model='mean_of_ratios' with axis=None returns elementwise linear ratios without reduction."""
        power = np.array([[2.0, 4.0], [6.0, 8.0]])
        baseline = np.array([[1.0, 2.0], [3.0, 4.0]])
        res = relative_power(power, baseline, model="mean_of_ratios", axis=None)
        expected = np.array([[2.0, 2.0], [2.0, 2.0]])
        np.testing.assert_allclose(res, expected)

    def test_ratio_of_means_reduces_all_elements_when_axis_is_none(self):
        """model='ratio_of_means' with axis=None reduces all elements."""
        power = np.array([[2.0, 4.0], [6.0, 8.0]])
        baseline = np.array([[1.0, 2.0], [3.0, 4.0]])
        res = relative_power(power, baseline, model="ratio_of_means", axis=None)
        expected = (2.0 + 4.0 + 6.0 + 8.0) / (1.0 + 2.0 + 3.0 + 4.0)  # 20 / 10 = 2.0
        assert res == pytest.approx(expected)

    def test_broadcasting_scalar_and_array_baselines(self):
        """Scalar baseline broadcasts across multidimensional power tensor."""
        power = np.array([[2.0, 4.0], [8.0, 16.0]])
        res_scalar = relative_power(power, 2.0, model="mean_of_ratios", axis=None)
        expected = np.array([[1.0, 2.0], [4.0, 8.0]])
        np.testing.assert_allclose(res_scalar, expected)

        # 1D baseline broadcasting along axis 0
        baseline_1d = np.array([2.0, 4.0])
        res_broadcast = relative_power(power, baseline_1d, model="mean_of_ratios", axis=None)
        expected_bc = np.array([[1.0, 1.0], [4.0, 4.0]])
        np.testing.assert_allclose(res_broadcast, expected_bc)

    def test_preservation_of_linear_scale(self):
        """Linear ratios are never converted to decibels unless model='log_ratio'."""
        power = np.array([10.0, 100.0])
        baseline = np.array([1.0, 1.0])
        r_linear = relative_power(power, baseline, model="mean_of_ratios", axis=0)
        assert r_linear == pytest.approx(55.0)  # (10 + 100) / 2 = 55.0 != 10*log10(55)

        r_db = relative_power(power, baseline, model="log_ratio")
        expected_db = np.array([10.0, 20.0])
        np.testing.assert_allclose(r_db, expected_db)

    def test_axis_with_log_ratio_raises(self):
        """Passing axis to model='log_ratio' raises ValueError (use aggregate_to_db for aggregated dB)."""
        power = np.array([2.0, 4.0])
        baseline = np.array([1.0, 2.0])
        with pytest.raises(ValueError, match="model='log_ratio' computes elementwise decibels"):
            relative_power(power, baseline, model="log_ratio", axis=0)

    def test_invalid_model_raises(self):
        power = np.array([2.0, 4.0])
        baseline = np.array([1.0, 2.0])
        with pytest.raises(ValueError, match="model must be one of"):
            relative_power(power, baseline, model="unsupported_model")

    def test_empty_inputs_raise(self):
        with pytest.raises(ValueError, match="must not be empty"):
            relative_power(np.array([]), np.array([]))

    def test_negative_inputs_raise(self):
        with pytest.raises(ValueError, match="power contains negative values"):
            relative_power(np.array([-1.0, 2.0]), np.array([1.0, 2.0]))

        with pytest.raises(ValueError, match="baseline contains negative values"):
            relative_power(np.array([1.0, 2.0]), np.array([-1.0, 2.0]))

    def test_nonfinite_inputs_raise(self):
        with pytest.raises(ValueError, match="finite values"):
            relative_power(np.array([np.nan, 2.0]), np.array([1.0, 2.0]))

        with pytest.raises(ValueError, match="finite values"):
            relative_power(np.array([1.0, 2.0]), np.array([np.inf, 2.0]))

    def test_zero_baseline_division_raises(self):
        with pytest.raises(ValueError, match="baseline contains zero values"):
            relative_power(np.array([1.0, 2.0]), np.array([0.0, 2.0]))

    def test_mismatched_nonbroadcastable_shapes_raise(self):
        power = np.ones((3, 4))
        baseline = np.ones((2, 5))
        with pytest.raises(ValueError, match="cannot broadcast"):
            relative_power(power, baseline)

    def test_device_fallback_warning_on_cuda_unavailability(self):
        """Requesting device='cuda' when unavailable emits RuntimeWarning and computes on CPU."""
        import warnings
        import jnwb._backend as backend
        power = np.array([2.0, 4.0])
        baseline = np.array([1.0, 2.0])
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            res = relative_power(power, baseline, model="mean_of_ratios", axis=0, device="cuda")
            # If CUDA is unavailable, RuntimeWarning is emitted by resolve_device
            cuda_warnings = [r for r in record if issubclass(r.category, RuntimeWarning)]
            if not backend.gpu_available():
                assert len(cuda_warnings) >= 1
                assert "device='cuda' was requested" in str(cuda_warnings[0].message)
        assert res == pytest.approx(2.0)


class TestWelchCsdGpuParity:
    """Test _welch_csd_gpu numerical parity with SciPy (0.2.3-REV-06)."""

    def _gpu_available(self):
        try:
            import cupy as cp
            return cp.cuda.runtime.getDeviceCount() > 0
        except Exception:
            return False

    def test_welch_csd_gpu_parity_even_nperseg(self):
        if not self._gpu_available():
            pytest.skip("CUDA GPU not available")
        from scipy import signal
        from jnwb.spectral import _welch_csd_gpu

        rng = np.random.default_rng(42)
        x = rng.standard_normal(2048) + 15.0  # non-zero mean to verify detrend='constant'
        y = rng.standard_normal(2048) - 8.0
        fs = 1000.0
        nperseg = 256
        noverlap = 128

        f_cpu, p_cpu = signal.welch(x, fs=fs, nperseg=nperseg, noverlap=noverlap)
        _, csd_cpu = signal.csd(x, y, fs=fs, nperseg=nperseg, noverlap=noverlap)

        f_gpu, p_gpu, _, csd_gpu = _welch_csd_gpu(x, y, fs=fs, nperseg=nperseg, noverlap=noverlap)

        assert np.allclose(f_cpu, f_gpu)
        assert np.allclose(p_cpu, p_gpu, rtol=1e-10, atol=1e-10)
        assert np.allclose(csd_cpu, csd_gpu, rtol=1e-10, atol=1e-10)

    def test_welch_csd_gpu_parity_odd_nperseg(self):
        if not self._gpu_available():
            pytest.skip("CUDA GPU not available")
        from scipy import signal
        from jnwb.spectral import _welch_csd_gpu

        rng = np.random.default_rng(101)
        x = rng.standard_normal(2048) + 5.0
        y = rng.standard_normal(2048) + 2.0
        fs = 1000.0
        nperseg = 255  # odd nperseg
        noverlap = 128

        f_cpu, p_cpu = signal.welch(x, fs=fs, nperseg=nperseg, noverlap=noverlap)
        _, csd_cpu = signal.csd(x, y, fs=fs, nperseg=nperseg, noverlap=noverlap)

        f_gpu, p_gpu, _, csd_gpu = _welch_csd_gpu(x, y, fs=fs, nperseg=nperseg, noverlap=noverlap)

        assert np.allclose(f_cpu, f_gpu)
        # Verifies that positive frequencies including the last bin are doubled properly
        assert np.allclose(p_cpu, p_gpu, rtol=1e-10, atol=1e-10)
        assert np.allclose(csd_cpu, csd_gpu, rtol=1e-10, atol=1e-10)

    def test_welch_csd_gpu_short_segment_padding(self):
        if not self._gpu_available():
            pytest.skip("CUDA GPU not available")
        from jnwb.spectral import _welch_csd_gpu

        x = np.random.randn(50)
        f_gpu, p_gpu, py_gpu, csd_gpu = _welch_csd_gpu(x, x, fs=100.0, nperseg=64)
        assert len(f_gpu) == len(p_gpu) == 33
        assert np.all(np.isfinite(p_gpu))
        assert np.all(p_gpu >= 0)


class TestCoherenceIdentifiability:
    """0.2.4: coherence must never be reported from a non-identifiable segmentation.

    With K = 1 Welch segment, |X Y*|^2 = |X|^2 |Y|^2 exactly, so magnitude-squared
    coherence is 1.0 at every frequency for any two signals. Before this repair the
    default nperseg = min(N, 4096) put every input up to ~8192 samples in that regime,
    and independent Gaussian noise reported perfect coherence with no warning.
    """

    FS = 1000.0
    BANDS = {"beta": (15.0, 30.0)}

    @staticmethod
    def _independent(n, seed=0):
        rng = np.random.default_rng(seed)
        return rng.normal(size=n), rng.normal(size=n)

    @staticmethod
    def _shared_oscillation(n, fs=1000.0, f0=20.0, phase=0.0, seed=3, amp=1.0):
        rng = np.random.default_rng(seed)
        t = np.arange(n) / fs
        x = amp * np.sin(2 * np.pi * f0 * t) + rng.normal(size=n)
        y = amp * np.sin(2 * np.pi * f0 * t + phase) + rng.normal(size=n)
        return x, y

    # -- segment counting ------------------------------------------------------
    @pytest.mark.parametrize(
        "n_samples,nperseg,noverlap,expected",
        [(1024, 1024, 512, 1), (1024, 512, 256, 3), (1024, 256, 128, 7),
         (1024, 128, 0, 8), (100, 256, 128, 0), (8192, 1024, 512, 15)],
    )
    def test_welch_segment_count_matches_scipy(self, n_samples, nperseg, noverlap, expected):
        from scipy.signal import spectrogram

        from jnwb.spectral import welch_segment_count

        assert welch_segment_count(n_samples, nperseg, noverlap) == expected
        if expected:
            _, _, spec = spectrogram(
                np.zeros(n_samples), fs=self.FS, nperseg=nperseg,
                noverlap=noverlap, mode="complex",
            )
            assert spec.shape[-1] == expected

    # -- the defect itself -----------------------------------------------------
    @pytest.mark.parametrize("n_samples", [1024, 2048, 4096, 5000])
    def test_independent_signals_do_not_report_perfect_coherence(self, n_samples):
        """The regression. Every one of these returned 1.0 before the repair."""
        x, y = self._independent(n_samples)
        out = cross_area_coherence(
            x, y, fs=self.FS, freq_bands=self.BANDS, n_surrogates=10
        )
        spectrum = np.asarray(out["coherence_spectrum"])
        assert out["n_segments_used"] >= 2
        assert spectrum.mean() < 0.35, (
            f"independent signals report mean coherence {spectrum.mean():.3f} from "
            f"{out['n_segments_used']} segments"
        )
        assert out["band_coherence"]["beta"] < 0.5

    @pytest.mark.parametrize("n_samples", [1024, 4096])
    def test_single_segment_is_rejected_not_reported(self, n_samples):
        x, y = self._independent(n_samples)
        with pytest.raises(ValueError, match=r"not identifiable from 1 Welch segment"):
            cross_area_coherence(
                x, y, fs=self.FS, freq_bands=self.BANDS,
                nperseg=n_samples, n_surrogates=3,
            )

    def test_the_rejected_configuration_would_have_returned_exactly_one(self):
        """Proves the rejection guards a real degeneracy, not a hypothetical one."""
        from scipy import signal as sp_signal

        x, y = self._independent(2048)
        _, coherency = sp_signal.coherence(x, y, fs=self.FS, nperseg=2048, noverlap=1024)
        assert np.allclose(coherency, 1.0), "K=1 coherence should be identically 1.0"

    def test_minimum_accepted_segment_count_is_two(self):
        from jnwb.spectral import MIN_IDENTIFIABLE_SEGMENTS, welch_segment_count

        assert MIN_IDENTIFIABLE_SEGMENTS == 2
        x, y = self._independent(1536)
        out = cross_area_coherence(
            x, y, fs=self.FS, freq_bands=self.BANDS,
            nperseg=1024, noverlap=512, n_surrogates=3,
        )
        assert welch_segment_count(1536, 1024, 512) == 2
        assert out["n_segments_used"] == 2

    # -- known-answer behaviour ------------------------------------------------
    def test_identical_signals_still_report_high_coherence(self):
        rng = np.random.default_rng(5)
        x = rng.normal(size=8192)
        out = cross_area_coherence(
            x, x, fs=self.FS, freq_bands=self.BANDS, n_surrogates=10
        )
        assert out["band_coherence"]["beta"] > 0.99

    def test_shared_oscillation_separates_from_independent_noise(self):
        n = 8192
        coupled_x, coupled_y = self._shared_oscillation(n)
        indep_x, indep_y = self._independent(n, seed=9)
        bands = {"beta": (18.0, 22.0)}
        coupled = cross_area_coherence(
            coupled_x, coupled_y, fs=self.FS, freq_bands=bands, n_surrogates=20
        )
        null = cross_area_coherence(
            indep_x, indep_y, fs=self.FS, freq_bands=bands, n_surrogates=20
        )
        assert coupled["band_coherence"]["beta"] > 0.8
        assert null["band_coherence"]["beta"] < 0.3
        assert coupled["band_significance"]["beta"] < null["band_significance"]["beta"]

    @pytest.mark.parametrize("phase", [0.0, np.pi / 4, np.pi / 2, np.pi])
    def test_coherence_magnitude_is_insensitive_to_a_constant_phase_shift(self, phase):
        """Coherence is a magnitude: a fixed lag changes phase, not |C|."""
        x, y = self._shared_oscillation(8192, phase=phase)
        out = cross_area_coherence(
            x, y, fs=self.FS, freq_bands={"beta": (18.0, 22.0)}, n_surrogates=5
        )
        assert out["band_coherence"]["beta"] > 0.8

    # -- parameter surface -----------------------------------------------------
    def test_explicit_nperseg_and_noverlap_are_honoured_and_reported(self):
        x, y = self._independent(8192)
        out = cross_area_coherence(
            x, y, fs=self.FS, freq_bands=self.BANDS,
            nperseg=512, noverlap=128, n_surrogates=3,
        )
        assert out["nperseg"] == 512
        assert out["noverlap"] == 128
        assert out["n_segments_used"] == 1 + (8192 - 512) // (512 - 128)

    def test_default_segmentation_is_reported(self):
        x, y = self._independent(8192)
        out = cross_area_coherence(
            x, y, fs=self.FS, freq_bands=self.BANDS, n_surrogates=3
        )
        assert out["nperseg"] == 1024
        assert out["noverlap"] == 512
        assert out["n_segments_used"] == 15

    @pytest.mark.parametrize("noverlap", [-1, 512, 999])
    def test_invalid_noverlap_is_rejected(self, noverlap):
        x, y = self._independent(8192)
        with pytest.raises(ValueError, match=r"noverlap"):
            cross_area_coherence(
                x, y, fs=self.FS, freq_bands=self.BANDS,
                nperseg=512, noverlap=noverlap, n_surrogates=3,
            )

    def test_null_coherence_falls_as_segment_count_rises(self):
        """E[C] ~ 1/K: measured, and the trend is what makes K interpretable."""
        x, y = self._independent(16384, seed=21)
        means = []
        for nperseg in (4096, 2048, 1024, 512):
            out = cross_area_coherence(
                x, y, fs=self.FS, freq_bands=self.BANDS,
                nperseg=nperseg, n_surrogates=3,
            )
            means.append((out["n_segments_used"], np.asarray(out["coherence_spectrum"]).mean()))
        counts = [k for k, _ in means]
        values = [m for _, m in means]
        assert counts == sorted(counts), "segment count should rise as nperseg falls"
        assert values == sorted(values, reverse=True), (
            f"null coherence should fall as K rises, got {means}"
        )

    # -- surrogates share the segmentation -------------------------------------
    def test_surrogates_use_the_same_segmentation_as_the_observed_statistic(self):
        """A surrogate null built at a different K belongs to a different estimator."""
        import jnwb.spectral as spectral_module

        seen = []
        original = spectral_module.signal.coherence

        def recording_coherence(x, y, **kwargs):
            seen.append((kwargs.get("nperseg"), kwargs.get("noverlap")))
            return original(x, y, **kwargs)

        x, y = self._independent(8192)
        try:
            spectral_module.signal.coherence = recording_coherence
            cross_area_coherence(
                x, y, fs=self.FS, freq_bands=self.BANDS,
                nperseg=512, noverlap=256, n_surrogates=4,
            )
        finally:
            spectral_module.signal.coherence = original

        assert len(seen) == 5, "one observed spectrum plus one per surrogate"
        assert set(seen) == {(512, 256)}, f"surrogates used other segmentations: {set(seen)}"

    def test_surrogate_null_is_not_saturated_under_the_default(self):
        x, y = self._independent(8192, seed=31)
        out = cross_area_coherence(
            x, y, fs=self.FS, freq_bands=self.BANDS, n_surrogates=30
        )
        assert 0.0 < out["band_significance"]["beta"] < 1.0

    def test_deterministic_for_a_given_surrogate_seed(self):
        x, y = self._independent(8192)
        kwargs = dict(fs=self.FS, freq_bands=self.BANDS, n_surrogates=8)
        a = cross_area_coherence(x, y, rng=np.random.default_rng(4), **kwargs)
        b = cross_area_coherence(x, y, rng=np.random.default_rng(4), **kwargs)
        assert a["band_significance"] == b["band_significance"]
        assert a["n_segments_used"] == b["n_segments_used"]


class TestCrossSpectralRatioFamilyIdentifiability:
    """The K=1 degeneracy is a property of the ratio, so every ratio estimator has it.

    `cross_area_coherence` was found first; `imaginary_coherency` (coh_mag_mean = 1.0 at
    N <= 1024) and `wpli` (wpli = 1.0 at N <= 256) had the same defect under their own
    defaults. Plain PSD estimators are deliberately excluded: a one-segment periodogram
    is noisy but not degenerate.
    """

    FS = 1000.0

    @staticmethod
    def _independent(n, seed=0):
        rng = np.random.default_rng(seed)
        return rng.normal(size=n), rng.normal(size=n)

    @pytest.mark.parametrize("n_samples", [512, 1024, 4096])
    def test_imaginary_coherency_does_not_report_unit_magnitude(self, n_samples):
        x, y = self._independent(n_samples)
        out = jnwb.imaginary_coherency(x, y, fs=self.FS)
        assert out["coh_mag_mean"] < 0.5, (
            f"independent signals report coh_mag_mean={out['coh_mag_mean']:.3f}"
        )

    def test_wpli_band_without_bins_is_rejected_not_zero(self):
        """n=128 gives nperseg=16 (62.5 Hz bins): no bin in 10-40 Hz. This returned 0.0."""
        x, y = self._independent(128)
        with pytest.raises(ValueError, match="contains no bin"):
            jnwb.wpli(x, y, fs=self.FS, freq_range=(10.0, 40.0))

    @pytest.mark.parametrize("n_samples", [256, 1024])
    def test_wpli_does_not_report_unity_for_independent_signals(self, n_samples):
        x, y = self._independent(n_samples)
        out = jnwb.wpli(x, y, fs=self.FS, freq_range=(10.0, 40.0))
        assert out["n_segments"] >= 2
        assert float(np.nanmean(out["wpli"])) < 0.95

    def test_imaginary_coherency_rejects_a_single_segment(self):
        x, y = self._independent(1024)
        with pytest.raises(ValueError, match=r"not identifiable from 1 Welch segment"):
            jnwb.imaginary_coherency(x, y, fs=self.FS, nperseg=1024)

    def test_wpli_rejects_a_single_segment(self):
        x, y = self._independent(1024)
        with pytest.raises(ValueError, match=r"not identifiable from 1 Welch segment"):
            jnwb.wpli(x, y, fs=self.FS, freq_range=(10.0, 40.0), nperseg=1024)

    def test_rejection_names_the_function_and_the_quantity(self):
        x, y = self._independent(1024)
        with pytest.raises(ValueError) as excinfo:
            jnwb.wpli(x, y, fs=self.FS, freq_range=(10.0, 40.0), nperseg=1024)
        message = str(excinfo.value)
        assert "wpli" in message
        assert "nperseg=1024" in message

    def test_debiased_wpli_is_approximately_unbiased_under_the_null(self):
        """The debiased estimator is what makes wPLI usable near zero coupling."""
        values = []
        for seed in range(25):
            x, y = self._independent(8192, seed=seed)
            out = jnwb.wpli(x, y, fs=self.FS, freq_range=(10.0, 40.0))
            values.append(np.nanmean(out["wpli_debiased_sq"]))
        mean_null = float(np.mean(values))
        assert abs(mean_null) < 0.05, f"debiased wPLI null mean {mean_null:.4f}"

    def test_plain_wpli_null_bias_falls_as_segment_count_rises(self):
        means = []
        for n_samples in (1024, 4096, 16384):
            values = [
                np.nanmean(
                    jnwb.wpli(
                        *self._independent(n_samples, seed=s),
                        fs=self.FS,
                        freq_range=(10.0, 40.0),
                    )["wpli"]
                )
                for s in range(10)
            ]
            means.append(float(np.mean(values)))
        assert means == sorted(means, reverse=True), (
            f"plain wPLI null bias should fall with more segments, got {means}"
        )

    def test_plain_psd_estimators_are_not_gated(self):
        """A one-segment periodogram is legitimate; the guard must not overreach."""
        rng = np.random.default_rng(0)
        trace = rng.normal(size=256)
        freqs, psd = jnwb.compute_multitaper_psd(trace, fs=self.FS)
        assert len(freqs) == len(psd)
        assert np.all(np.isfinite(psd))


class TestPairedTraceContract:
    """0.2.4-04: unpaired traces must be refused, not silently truncated.

    `wpli` and `imaginary_coherency` took n = min(len(x), len(y)) and discarded the tail
    of the longer trace. The two traces then no longer describe the same interval, and
    nothing in the result said so. `cross_area_coherence` had the sibling form of this
    defect (returning zeros) and was repaired in the same release.
    """

    FS = 1000.0

    @staticmethod
    def _pair(n_x, n_y, seed=0):
        rng = np.random.default_rng(seed)
        return rng.normal(size=n_x), rng.normal(size=n_y)

    def test_wpli_rejects_unpaired_traces(self):
        x, y = self._pair(8192, 4096)
        with pytest.raises(ValueError, match=r"must have the same length"):
            jnwb.wpli(x, y, fs=self.FS, freq_range=(10.0, 40.0))

    def test_imaginary_coherency_rejects_unpaired_traces(self):
        x, y = self._pair(8192, 4096)
        with pytest.raises(ValueError, match=r"must have the same length"):
            jnwb.imaginary_coherency(x, y, fs=self.FS)

    def test_error_names_the_function_and_both_lengths(self):
        x, y = self._pair(8192, 4096)
        with pytest.raises(ValueError) as excinfo:
            jnwb.wpli(x, y, fs=self.FS, freq_range=(10.0, 40.0))
        message = str(excinfo.value)
        assert "wpli" in message
        assert "8192" in message and "4096" in message

    @pytest.mark.parametrize("n_samples", [2048, 8192])
    def test_equal_lengths_are_unaffected(self, n_samples):
        x, y = self._pair(n_samples, n_samples)
        out = jnwb.wpli(x, y, fs=self.FS, freq_range=(10.0, 40.0))
        assert out["n_segments"] >= 2
        assert np.isfinite(out["wpli"])

    def test_documented_defaults_match_the_implementation(self):
        """The segmentation repair silently invalidated both docstrings once."""
        for func in (jnwb.wpli, jnwb.imaginary_coherency):
            doc = func.__doc__
            assert "min(len(x), 256)" not in doc
            assert "min(len(x), 1024)" not in doc
            assert "N // 8" in doc

    def test_wpli_matches_an_independent_oracle(self):
        """wPLI recomputed from first principles: segment, window, detrend, rFFT.

        Deliberately does not reuse any jnwb helper, so a shared bug cannot cancel.
        """
        from scipy import signal as sp_signal

        fs, n_samples = self.FS, 8192
        rng = np.random.default_rng(7)
        t = np.arange(n_samples) / fs
        x = np.sin(2 * np.pi * 20 * t) + 0.5 * rng.normal(size=n_samples)
        y = np.sin(2 * np.pi * 20 * t + np.pi / 3) + 0.5 * rng.normal(size=n_samples)

        nperseg = min(max(n_samples // 8, 8), 256)
        noverlap = nperseg // 2
        step = nperseg - noverlap
        window = sp_signal.get_window("hann", nperseg)

        cross = []
        start = 0
        while start + nperseg <= n_samples:
            seg_x = x[start:start + nperseg]
            seg_y = y[start:start + nperseg]
            spec_x = np.fft.rfft((seg_x - seg_x.mean()) * window)
            spec_y = np.fft.rfft((seg_y - seg_y.mean()) * window)
            cross.append(np.conj(spec_x) * spec_y)
            start += step
        imag = np.imag(np.array(cross))
        numerator = np.abs(imag.sum(axis=0))
        denominator = np.abs(imag).sum(axis=0)
        spectrum = np.divide(
            numerator, denominator, out=np.zeros_like(numerator), where=denominator > 0
        )
        freqs = np.fft.rfftfreq(nperseg, d=1.0 / fs)
        band = (freqs >= 18.0) & (freqs <= 22.0)
        expected = float(np.mean(spectrum[band]))

        out = jnwb.wpli(x, y, fs=fs, freq_range=(18.0, 22.0))
        assert out["n_segments"] == len(cross)
        assert out["wpli"] == pytest.approx(expected, abs=1e-12)

    def test_wpli_is_insensitive_to_zero_lag_coupling(self):
        """The defining property: wPLI weights the imaginary cross-spectrum only."""
        fs, n_samples = self.FS, 8192
        rng = np.random.default_rng(7)
        t = np.arange(n_samples) / fs
        base = np.sin(2 * np.pi * 20 * t)
        x = base + 0.5 * rng.normal(size=n_samples)
        zero_lag = base + 0.5 * rng.normal(size=n_samples)
        lagged = np.sin(2 * np.pi * 20 * t + np.pi / 3) + 0.5 * rng.normal(size=n_samples)

        low = jnwb.wpli(x, zero_lag, fs=fs, freq_range=(18.0, 22.0))["wpli"]
        high = jnwb.wpli(x, lagged, fs=fs, freq_range=(18.0, 22.0))["wpli"]
        assert low < 0.3, f"zero-lag coupling gave wPLI {low:.3f}"
        assert high > 0.8, f"lagged coupling gave wPLI {high:.3f}"

    def test_wpli_magnitude_is_unsigned_and_argument_symmetric(self):
        fs, n_samples = self.FS, 8192
        rng = np.random.default_rng(7)
        t = np.arange(n_samples) / fs
        x = np.sin(2 * np.pi * 20 * t) + 0.5 * rng.normal(size=n_samples)
        y = np.sin(2 * np.pi * 20 * t + np.pi / 3) + 0.5 * rng.normal(size=n_samples)
        forward = jnwb.wpli(x, y, fs=fs, freq_range=(18.0, 22.0))["wpli"]
        reverse = jnwb.wpli(y, x, fs=fs, freq_range=(18.0, 22.0))["wpli"]
        assert forward >= 0.0 and reverse >= 0.0
        assert forward == pytest.approx(reverse, abs=1e-12)
