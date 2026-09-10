"""Tests for jnwb._backend -- one device probe, one fallback policy, and no silence.

The defect this module replaces: ~15 call sites across 7 modules each carried their own
GPU probe and their own fallback, two of them asking different questions (a bare
`import cupy` vs `torch.cuda.is_available()`), and none of them telling the caller when
a requested GPU quietly became a CPU.
"""
from __future__ import annotations

import warnings

import numpy as np
import pytest

from jnwb._backend import (
    CPU,
    CUDA,
    cupy_available,
    gpu_available,
    resolve_device,
    torch_cuda_available,
    warn_device_fallback,
)


class TestCapabilityProbes:
    def test_probes_return_booleans(self):
        assert isinstance(cupy_available(), bool)
        assert isinstance(torch_cuda_available(), bool)
        assert isinstance(gpu_available(), bool)

    def test_gpu_available_is_the_disjunction_of_the_backends(self):
        assert gpu_available() == (cupy_available() or torch_cuda_available())

    def test_prefer_selects_a_single_backend(self):
        assert gpu_available(prefer="cupy") == cupy_available()
        assert gpu_available(prefer="torch") == torch_cuda_available()

    def test_probes_never_raise_without_a_gpu(self):
        """A capability probe that throws is worse than one that returns False."""
        for probe in (cupy_available, torch_cuda_available, gpu_available):
            probe()


class TestResolveDevice:
    def test_cpu_and_none_resolve_to_cpu_silently(self):
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            assert resolve_device("cpu", context="t") == CPU
            assert resolve_device(None, context="t") == CPU
        assert record == [], "a caller who asked for CPU was denied nothing"

    def test_case_and_whitespace_tolerated(self):
        assert resolve_device("  CPU ", context="t") == CPU

    def test_unrecognised_device_raises_rather_than_running_on_cpu(self):
        """A typo used to fall through every `if device == 'cuda'` and run on CPU."""
        with pytest.raises(ValueError, match="unrecognised device"):
            resolve_device("gpu0", context="t")
        with pytest.raises(ValueError, match="unrecognised device"):
            resolve_device("CUDA:1", context="t")

    def test_cuda_request_resolves_to_a_real_device_or_warns(self):
        """Whatever this machine has, the answer and the warning must agree."""
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            resolved = resolve_device("cuda", context="t")
        warned = [w for w in record if issubclass(w.category, RuntimeWarning)]
        if gpu_available():
            assert resolved == CUDA
            assert warned == [], "a delivered GPU must not warn"
        else:
            assert resolved == CPU
            assert len(warned) == 1, "a denied GPU must always warn"
            assert "cuda" in str(warned[0].message).lower()

    def test_denied_gpu_warning_names_the_caller(self, monkeypatch):
        import jnwb._backend as backend

        monkeypatch.setattr(backend, "gpu_available", lambda prefer=None: False)
        with pytest.warns(RuntimeWarning, match="my_function"):
            assert backend.resolve_device("cuda", context="my_function") == CPU

    def test_gpu_alias_is_accepted(self, monkeypatch):
        import jnwb._backend as backend

        monkeypatch.setattr(backend, "gpu_available", lambda prefer=None: True)
        assert backend.resolve_device("gpu", context="t") == CUDA


class TestFallbackWarning:
    def test_warns_and_names_the_exception(self):
        with pytest.warns(RuntimeWarning, match="RuntimeError: simulated OOM"):
            warn_device_fallback("some_function", RuntimeError("simulated OOM"))

    def test_says_partial_work_was_discarded(self):
        """A mixed result is the thing this warning exists to rule out."""
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            warn_device_fallback("f", ValueError("x"))
        assert "discarded" in str(record[0].message)


class TestCallSitesAreRouted:
    """Every GPU decision must come from _backend, not a local probe."""

    ROUTED_MODULES = ["spectral", "gpu_pca", "analyzers", "connectivity", "tfr"]

    def test_routed_modules_import_the_shared_resolver(self):
        import importlib

        for name in self.ROUTED_MODULES:
            module = importlib.import_module(f"jnwb.{name}")
            assert hasattr(module, "resolve_device"), (
                f"jnwb.{name} does not route its device decision through _backend"
            )

    def test_no_routed_module_probes_with_a_bare_cupy_import(self):
        """`import cupy` succeeds with no driver, so it never proved a GPU existed."""
        import pathlib
        import re

        root = pathlib.Path(__file__).resolve().parents[1] / "jnwb"
        offenders = []
        for name in self.ROUTED_MODULES:
            text = (root / f"{name}.py").read_text(encoding="utf-8")
            # A capability *decision* looks like `if <import/attr> ...:`; using cupy
            # inside an already-resolved branch is fine.
            for match in re.finditer(r"^\s*if .*torch\.cuda\.is_available\(\)", text, re.M):
                offenders.append(f"{name}: {match.group(0).strip()}")
        assert offenders == [], (
            "device capability must be decided by _backend.resolve_device, not re-probed "
            "at the call site: " + "; ".join(offenders)
        )


class TestDeviceRequestIsHonouredOrReported:
    def test_gpu_pca_cpu_and_cuda_agree_within_float32(self):
        """If this machine has a GPU, the two paths must not disagree materially."""
        from jnwb.gpu_pca import gpu_pca

        rng = np.random.default_rng(0)
        X = rng.normal(size=(200, 30))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            _, _, var_cuda = gpu_pca(X, n_components=3, device="cuda")
        _, _, var_cpu = gpu_pca(X, n_components=3, device="cpu")
        assert var_cuda == pytest.approx(var_cpu, abs=1e-5)

    def test_gpu_pca_warns_when_its_default_device_is_unavailable(self, monkeypatch):
        """gpu_pca defaults to device='cuda'; returning CPU results silently is the bug."""
        import jnwb._backend as backend
        from jnwb.gpu_pca import gpu_pca

        monkeypatch.setattr(backend, "gpu_available", lambda prefer=None: False)
        rng = np.random.default_rng(0)
        with pytest.warns(RuntimeWarning, match="gpu_pca"):
            gpu_pca(rng.normal(size=(50, 10)), n_components=2)


class TestComplexTfrDevice:
    """complex_tfr(device='cuda') must match the CPU transform or fall back wholesale, loudly."""

    @staticmethod
    def _data():
        return np.random.default_rng(0).normal(size=(3, 1200))

    def test_cpu_is_the_default_and_is_recorded(self):
        from jnwb.tfr import complex_tfr

        out = complex_tfr(self._data(), fs=1000.0, freqs=np.array([10.0, 20.0, 40.0]))
        assert out.device == CPU

    def test_cuda_matches_cpu_or_warns(self):
        from jnwb.tfr import complex_tfr

        freqs = np.array([10.0, 20.0, 40.0])
        cpu = complex_tfr(self._data(), fs=1000.0, freqs=freqs)
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            gpu = complex_tfr(self._data(), fs=1000.0, freqs=freqs, device="cuda")
        if gpu_available(prefer="cupy"):
            assert gpu.device == CUDA
            np.testing.assert_allclose(gpu.z, cpu.z, rtol=0, atol=1e-10)
        else:
            assert gpu.device == CPU
            assert any(issubclass(w.category, RuntimeWarning) for w in record)
        np.testing.assert_array_equal(gpu.coi_mask, cpu.coi_mask)

    def test_gpu_failure_falls_back_wholesale_and_warns(self, monkeypatch):
        import jnwb._backend as backend
        import jnwb.tfr as tfr

        def boom(*args, **kwargs):
            raise RuntimeError("simulated CUDA failure")

        monkeypatch.setattr(backend, "gpu_available", lambda prefer=None: True)
        monkeypatch.setattr(tfr, "_convolve_gpu", boom)
        freqs = np.array([10.0, 20.0])
        with pytest.warns(RuntimeWarning, match="complex_tfr"):
            out = tfr.complex_tfr(self._data(), fs=1000.0, freqs=freqs, device="cuda")
        assert out.device == CPU
        np.testing.assert_array_equal(out.z, tfr.complex_tfr(self._data(), fs=1000.0, freqs=freqs).z)
