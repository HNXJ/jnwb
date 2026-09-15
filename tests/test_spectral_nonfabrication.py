"""0.2.4-04: wPLI and imaginary coherency report unavailable states, not zero.

Each test fails against the pre-repair implementation:

- NaN/Inf, empty input, and a band with no frequency bin returned 0.0.
- An absolute 1e-12 cutoff on the imaginary cross-spectrum zeroed every term of
  volt-scaled input, so wPLI of a coupled pair depended on the amplitude units.
- The CuPy wPLI path raised on every call (``cupy.divide`` has no ``where``) and
  fell back to CPU through a log message only.
"""

import sys

import numpy as np
import pytest

import jnwb
from jnwb import _backend

FS = 1000.0


def _lagged_pair(n=8000, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    return x, np.roll(x, 3) + 0.5 * rng.normal(size=n)


class TestUnavailableStatesRaise:
    @pytest.mark.parametrize("func", [jnwb.wpli, jnwb.imaginary_coherency])
    @pytest.mark.parametrize("bad", [np.nan, np.inf])
    def test_non_finite_sample_is_rejected(self, func, bad):
        x, y = _lagged_pair()
        x[100] = bad
        with pytest.raises(ValueError, match="must be finite"):
            func(x, y, fs=FS)

    @pytest.mark.parametrize("func", [jnwb.wpli, jnwb.imaginary_coherency])
    def test_empty_pair_is_rejected(self, func):
        with pytest.raises(ValueError, match="empty"):
            func([], [], fs=FS)

    @pytest.mark.parametrize("func", [jnwb.wpli, jnwb.imaginary_coherency])
    @pytest.mark.parametrize("freq_range", [(600.0, 700.0), (40.0, 10.0)])
    def test_band_without_bins_is_rejected(self, func, freq_range):
        x, y = _lagged_pair()
        with pytest.raises(ValueError, match="contains no bin"):
            func(x, y, fs=FS, freq_range=freq_range)

    def test_identical_signals_still_report_zero_lag_zero(self):
        """Zero is kept where it is the observed result: every imaginary term is 0."""
        x, _ = _lagged_pair()
        out = jnwb.wpli(x, x, fs=FS)
        assert out["wpli"] == 0.0
        assert out["wpli_debiased_sq"] == 0.0


class TestAmplitudeUnitInvariance:
    @pytest.mark.parametrize("scale", [1e-9, 1e-6, 1e-4, 1e-3, 1e3])
    def test_wpli_does_not_depend_on_amplitude_units(self, scale):
        x, y = _lagged_pair()
        ref = jnwb.wpli(x, y, fs=FS, freq_range=(10.0, 40.0))
        out = jnwb.wpli(x * scale, y * scale, fs=FS, freq_range=(10.0, 40.0))
        assert ref["wpli"] > 0.8
        assert out["wpli"] == pytest.approx(ref["wpli"], rel=1e-9)
        assert out["wpli_debiased_sq"] == pytest.approx(ref["wpli_debiased_sq"], rel=1e-9)
        assert np.allclose(out["wpli_spectrum"], ref["wpli_spectrum"], rtol=1e-9, atol=1e-12)


class TestWpliDevice:
    @pytest.mark.skipif(not _backend.cupy_available(), reason="requires a CUDA device with CuPy")
    @pytest.mark.parametrize("offset, nperseg", [(0.0, 256), (5.0, 256), (5.0, 255)])
    def test_cuda_executes_and_matches_cpu(self, offset, nperseg):
        import warnings

        x, y = _lagged_pair()
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            gpu = jnwb.wpli(x + offset, y, fs=FS, nperseg=nperseg, freq_range=(1.0, 90.0), device="cuda")
        cpu = jnwb.wpli(x + offset, y, fs=FS, nperseg=nperseg, freq_range=(1.0, 90.0))
        assert gpu["n_segments"] == cpu["n_segments"]
        assert np.array_equal(gpu["freqs"], cpu["freqs"])
        assert np.allclose(gpu["wpli_spectrum"], cpu["wpli_spectrum"], rtol=0, atol=1e-10)
        assert gpu["wpli_debiased_sq"] == pytest.approx(cpu["wpli_debiased_sq"], abs=1e-10)

    def test_gpu_failure_warns_and_returns_the_cpu_result(self, monkeypatch):
        x, y = _lagged_pair()
        cpu = jnwb.wpli(x, y, fs=FS, freq_range=(10.0, 40.0))
        monkeypatch.setattr(jnwb.spectral, "resolve_device", lambda *a, **k: "cuda")
        monkeypatch.setitem(sys.modules, "cupy", None)  # `import cupy` now raises
        with pytest.warns(RuntimeWarning, match="wpli: GPU computation failed"):
            out = jnwb.wpli(x, y, fs=FS, freq_range=(10.0, 40.0), device="cuda")
        assert out["wpli"] == cpu["wpli"]

    def test_imaginary_coherency_gpu_failure_warns(self, monkeypatch):
        x, y = _lagged_pair()
        monkeypatch.setattr(jnwb.spectral, "resolve_device", lambda *a, **k: "cuda")

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated device failure")

        monkeypatch.setattr(jnwb.spectral, "_welch_csd_gpu", _boom)
        with pytest.warns(RuntimeWarning, match="imaginary_coherency: GPU computation failed"):
            jnwb.imaginary_coherency(x, y, fs=FS, device="cuda")

    @pytest.mark.parametrize("func", [jnwb.wpli, jnwb.imaginary_coherency])
    def test_unrecognised_device_is_rejected(self, func):
        x, y = _lagged_pair()
        with pytest.raises(ValueError, match="unrecognised device"):
            func(x, y, fs=FS, device="gpu0")
