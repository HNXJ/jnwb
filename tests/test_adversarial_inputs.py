"""Degenerate-input and amplitude-unit regressions from the 0.2.4 adversarial audit.

Each test pins a contract a public function violated: returning a valid-looking number (0.0,
p = 1/(n_shuffles+1), a fundamental at the first bin) where the quantity is undefined, or
returning a result that changed with the units of the input.
"""
import warnings

import numpy as np
import pytest
from scipy import signal

import jnwb
import jnwb.testing as jt
from jnwb import _backend, spectral
from jnwb.artifact_detection import bad_trials_single_channel

FS = 1000.0
TRACE = np.random.default_rng(915).normal(size=8192)
BAD_TRACES = [
    (np.array([]), "empty"),
    (np.r_[TRACE[:512], np.nan], "finite"),
    (np.r_[TRACE[:512], np.inf], "finite"),
]


class TestSpectralSummaries:
    @pytest.mark.parametrize("bad, match", BAD_TRACES)
    @pytest.mark.parametrize(
        "call",
        [
            lambda x: jnwb.spectral_tilt(x, fs=FS),
            lambda x: jnwb.harmonic_analysis(x, fs=FS),
            lambda x: jnwb.band_power(x, fs=FS, freq_range=(8.0, 30.0), normalize=False),
            lambda x: jnwb.band_power(TRACE, fs=FS, freq_range=(8.0, 30.0), baseline=x),
        ],
        ids=["spectral_tilt", "harmonic_analysis", "band_power", "band_power_baseline"],
    )
    def test_undefined_input_raises(self, call, bad, match):
        with pytest.raises(ValueError, match=match):
            call(bad)

    def test_constant_trace_has_no_tilt_and_no_fundamental(self):
        tilt = jnwb.spectral_tilt(np.full(4096, 2.0), fs=FS)
        assert all(np.isnan(tilt[k]) for k in ("exponent", "offset", "fit_quality"))
        harmonics = jnwb.harmonic_analysis(np.full(4096, 2.0), fs=FS)
        assert np.isnan(harmonics["fundamental_freq"]) and harmonics["harmonics"] == {}

    def test_harmonic_ratio_does_not_count_the_fundamental_twice(self):
        t = np.arange(4000) / FS
        result = jnwb.harmonic_analysis(np.sin(2 * np.pi * 10.0 * t), fs=FS, freq_range=(1.0, 90.0))
        assert result["fundamental_freq"] == pytest.approx(10.0, abs=0.5)
        # A pure tone has no power at its harmonics; the ratio was capped at 0.5.
        assert result["harmonic_ratio"] > 0.99

    def test_harmonic_band_without_bins_raises(self):
        with pytest.raises(ValueError, match="contains no bin"):
            jnwb.harmonic_analysis(TRACE[:64], fs=FS, freq_range=(1.0, 2.0))

    def test_baseline_of_different_length_uses_its_own_grid(self):
        base = np.random.default_rng(1).normal(size=2000)
        got = jnwb.band_power(TRACE, fs=FS, freq_range=(8.0, 30.0), baseline=base)
        f1, p1 = signal.welch(TRACE, fs=FS, nperseg=4096)
        f2, p2 = signal.welch(base, fs=FS, nperseg=2000)
        m1 = (f1 >= 8.0) & (f1 <= 30.0)
        m2 = (f2 >= 8.0) & (f2 <= 30.0)
        assert got == pytest.approx(10 * np.log10(p1[m1].mean() / p2[m2].mean()), rel=1e-12)

    def test_zero_power_baseline_raises_instead_of_returning_linear_power(self):
        with pytest.raises(ValueError, match="no power"):
            jnwb.band_power(TRACE, fs=FS, freq_range=(8.0, 30.0), baseline=np.zeros(8192))

    @pytest.mark.parametrize("func", ["band_power", "harmonic_analysis"])
    def test_unrecognised_device_raises(self, func):
        kwargs = {"normalize": False, "freq_range": (8.0, 30.0)} if func == "band_power" else {}
        with pytest.raises(ValueError):
            getattr(jnwb, func)(TRACE, fs=FS, device="gpu0", **kwargs)

    # band_power has no GPU path (it returns a bare float with nowhere to record a device);
    # tests/test_execution_switch.py holds it to computing on the CPU with a warning.
    def test_gpu_failure_warns_and_matches_cpu(self, monkeypatch):
        def boom(*args, **kwds):
            raise RuntimeError("simulated CUDA failure")

        cpu = jnwb.harmonic_analysis(TRACE, fs=FS)
        monkeypatch.setattr(spectral, "resolve_device", lambda *a, **k: spectral.CUDA)
        monkeypatch.setattr(spectral, "_welch_csd_gpu", boom)
        with pytest.warns(RuntimeWarning, match="simulated CUDA failure"):
            fallback = jnwb.harmonic_analysis(TRACE, fs=FS, device="cuda")
        assert fallback["fundamental_freq"] == cpu["fundamental_freq"]

    @pytest.mark.skipif(not _backend.cupy_available(), reason="needs CuPy with a CUDA device")
    def test_cuda_executes_and_matches_cpu(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            gpu_profile = jnwb.harmonic_analysis(TRACE, fs=FS, device="cuda")["spectral_profile"]
        np.testing.assert_allclose(
            np.asarray(gpu_profile), jnwb.harmonic_analysis(TRACE, fs=FS)["spectral_profile"], rtol=1e-10
        )


def test_laplacian_reference_rejects_a_single_channel():
    with pytest.raises(ValueError, match="at least 2 channels"):
        jnwb.laplacian_reference(np.ones((1, 50)))


class TestSpikeWindows:
    SPIKES = np.array([1.02, 1.05, 1.08, 2.5])

    @pytest.mark.parametrize("func", [jnwb.rate_in_window, jnwb.fires_in_window])
    @pytest.mark.parametrize(
        "spikes, onset, window, match",
        [
            (SPIKES, 1.0, (100.0, 0.0), "non-positive width"),
            (SPIKES, 1.0, (50.0, 50.0), "non-positive width"),
            (SPIKES, np.nan, (0.0, 100.0), "finite"),
            (SPIKES[::-1], 1.0, (0.0, 100.0), "sorted"),
            (np.r_[SPIKES, np.nan], 1.0, (0.0, 100.0), "finite"),
        ],
    )
    def test_undefined_query_raises(self, func, spikes, onset, window, match):
        with pytest.raises(ValueError, match=match):
            func(spikes, onset, window)

    def test_rate_counts_sorted_spikes(self):
        assert jnwb.rate_in_window(self.SPIKES, 1.0, (0.0, 100.0)) == pytest.approx(30.0)


class TestShufflePvalues:
    A = np.random.default_rng(2).normal(size=30)
    B = np.random.default_rng(3).normal(size=30) + 0.5

    @pytest.mark.parametrize("func", [jnwb.shuffle_pvalue_paired, jnwb.shuffle_pvalue_unpaired])
    def test_nan_raises_instead_of_minimum_p(self, func):
        a = self.A.copy()
        a[3] = np.nan
        with pytest.raises(ValueError, match="finite"):
            func(a, self.B, 200, np.random.default_rng(0))

    @pytest.mark.parametrize("func", [jnwb.shuffle_pvalue_paired, jnwb.shuffle_pvalue_unpaired])
    @pytest.mark.parametrize("n_shuffles", [0, -5, 10.0, True])
    def test_invalid_shuffle_count_raises(self, func, n_shuffles):
        with pytest.raises(ValueError, match="n_shuffles"):
            func(self.A, self.B, n_shuffles, np.random.default_rng(0))

    def test_paired_lengths_must_match(self):
        with pytest.raises(ValueError, match="equal length"):
            jnwb.shuffle_pvalue_paired(self.A, self.B[:-4], 200, np.random.default_rng(0))

    @pytest.mark.parametrize("func", [jnwb.shuffle_pvalue_paired, jnwb.shuffle_pvalue_unpaired])
    def test_empty_groups_are_undefined(self, func):
        obs, p = func(np.array([]), np.array([]), 200, np.random.default_rng(0))
        assert np.isnan(obs) and np.isnan(p)


class TestRasterPsth:
    def test_no_onsets_is_undefined(self):
        _, mean, sem = jnwb.raster_psth(np.array([0.1, 0.2]), np.array([]), (-100.0, 300.0), 10.0)
        assert np.all(np.isnan(mean)) and np.all(np.isnan(sem))

    @pytest.mark.parametrize("win, bin_ms", [((300.0, -100.0), 10.0), ((-100.0, 300.0), 0.0)])
    def test_malformed_window_raises(self, win, bin_ms):
        with pytest.raises(ValueError):
            jnwb.raster_psth(np.array([0.1]), np.array([0.0]), win, bin_ms)


class TestNetworkTopology:
    ADJ = np.abs(np.corrcoef(np.random.default_rng(4).normal(size=(8, 200))))

    def test_nan_off_diagonal_raises(self):
        adj = self.ADJ.copy()
        adj[0, 1] = adj[1, 0] = np.nan
        with pytest.raises(ValueError, match="NaN or Inf"):
            jnwb.network_topology(adj)

    def test_non_square_raises(self):
        with pytest.raises(ValueError, match="square"):
            jnwb.network_topology(self.ADJ[:, :5])

    def test_nan_diagonal_is_ignored(self):
        adj = self.ADJ.copy()
        np.fill_diagonal(adj, np.nan)
        assert jnwb.network_topology(adj) == jnwb.network_topology(self.ADJ)


class TestOutlierDetectionIsUnitFree:
    @staticmethod
    def _trace():
        trace = np.random.default_rng(5).lognormal(0.0, 0.3, size=(30, 200))
        trace[5, 50] *= 20.0
        return trace

    @pytest.mark.parametrize("scale", [1e-6, 1e-12, 1e-20])
    def test_detect_band_outliers(self, scale):
        ref, ref_scale = jnwb.detect_band_outliers(self._trace())
        got, got_scale = jnwb.detect_band_outliers(self._trace() * scale)
        assert ref[5, 50] and np.array_equal(got, ref)
        assert got_scale == pytest.approx(ref_scale * scale, rel=1e-12)

    @pytest.mark.parametrize("bad", [np.ones(10), np.array([[1.0, np.nan], [1.0, 2.0]])])
    def test_detect_band_outliers_rejects_malformed_input(self, bad):
        with pytest.raises(ValueError):
            jnwb.detect_band_outliers(bad)

    def test_bad_trials_amplitude_rule(self):
        rng = np.random.default_rng(6)
        waves = rng.normal(size=(40, 100))
        waves[7] *= 30.0
        ref = bad_trials_single_channel(waves)[0]
        got = bad_trials_single_channel(waves * 1e-14)[0]
        assert ref[7] and np.array_equal(got, ref)


def test_xflip_rejects_zero_variance_channel():
    data = np.random.default_rng(7).normal(size=(12, 2000))
    data[4] = 3.0
    result = jnwb.xflip(data, n_surrogates=10, rng=0)
    assert result.accepted is False
    assert "Zero-variance" in result.rejection_reason
    assert np.all(np.isnan(result.corr_matrix[4])) and np.all(np.isnan(result.corr_matrix[:, 4]))


class TestJrsaIsUnitFree:
    RNG = np.random.default_rng(8)
    X = RNG.normal(size=(40, 6))
    Y = X @ RNG.normal(size=(6, 6)) + 0.5 * RNG.normal(size=(40, 6))

    @staticmethod
    def _value(x, y, metric, **kwargs):
        return float(jnwb.jrsa(x, y, metric=metric, stats=False, **kwargs).value)

    @pytest.mark.parametrize("metric", ["cka", "rv", "distance_correlation", "cosine", "pearson", "spearman", "rsa"])
    @pytest.mark.parametrize("scale", [1e-3, 1e-6, 1e-9])
    def test_value_does_not_depend_on_amplitude(self, metric, scale):
        ref = self._value(self.X, self.Y, metric)
        assert self._value(self.X * scale, self.Y * scale, metric) == pytest.approx(ref, rel=1e-9)

    @pytest.mark.parametrize("metric", ["cka", "distance_correlation", "pearson", "spearman", "rsa"])
    def test_constant_input_is_undefined(self, metric):
        assert np.isnan(self._value(np.ones_like(self.X), self.Y, metric))

    @pytest.mark.parametrize("metric", ["cka", "rv", "cosine"])
    def test_zero_input_is_undefined(self, metric):
        assert np.isnan(self._value(np.zeros_like(self.X), self.Y, metric))

    @pytest.mark.skipif(not _backend.cupy_available(), reason="needs CuPy with a CUDA device")
    @pytest.mark.parametrize("metric", ["pearson", "spearman", "cosine"])
    def test_cuda_matches_cpu(self, metric):
        tied = np.repeat(self.RNG.normal(size=10), 4)[:, None] * np.ones((1, 3))
        cases = [
            (self.X, self.Y),
            (tied, self.RNG.normal(size=(40, 3))),
            (np.ones_like(self.X), self.Y),
            (self.X * 1e-7, self.Y * 1e-7),
        ]
        for x, y in cases:
            cpu = self._value(x, y, metric)
            gpu = self._value(x, y, metric, backend="cupy")
            if np.isnan(cpu):
                assert np.isnan(gpu)
            else:
                assert gpu == pytest.approx(cpu, rel=1e-9)


@pytest.mark.parametrize("scale", [1e-3, 1e-6, 1e-9])
def test_vflip_does_not_depend_on_amplitude_units(scale):
    # snr=20 rather than the generator default of 4: after the 0.2.4 recalibration a motif
    # at SNR 4 is below the acceptance threshold, so the default fixture would fail on
    # ref.accepted before the unit-invariance this test exists to check is ever exercised.
    lfp = np.asarray(jt.synth_laminar_motif(rng=0, snr=20.0).lfp, dtype=float)
    ref = jnwb.vflip_from_lfp(lfp, FS)
    got = jnwb.vflip_from_lfp(lfp * scale, FS)
    assert ref.accepted and got.accepted
    assert got.crossover_contact == pytest.approx(ref.crossover_contact, rel=1e-9)
    assert got.support_score == pytest.approx(ref.support_score, rel=1e-9)
