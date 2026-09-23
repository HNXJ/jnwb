"""One execution switch: every backend argument selects a device or says what ran instead.

``device=`` resolves through ``jnwb._backend.resolve_device`` and ``n_jobs=`` through
``jnwb._parallel.parallel_map``. This module holds every public export that takes either to
that contract, and measures the CUDA paths against the CPU on this machine.

Tolerances, stated before anything was measured:

* **CUDA against CPU**, float64 paths: ``max|cuda - cpu| <= 1e-9 * max|cpu|`` per output
  array. The two use different FFT and solver libraries and different reduction orders, so
  bit equality is not the claim. float64 rounding over the sizes here is about 1e-13; 1e-9
  leaves four orders of margin and is still 100x tighter than a float32 cast (about 1e-7),
  so an estimator swap or a silent downcast fails.
* **Metal against CPU**, 32-bit output requested: ``1e-5 * max|cpu|``. float32 epsilon is
  1.2e-7 and an FFT of these lengths accumulates about ``log2(n)`` of it.
* **Parallel CPU against serial**: bit equality, held by ``tests/test_parallel.py`` for every
  export that takes ``n_jobs``. Seeds are drawn before the loop, so worker count cannot change
  a number.

Measured on an RTX A4000 the worst CUDA disagreement across the subset below was 1.2e-13
(``granger_causality``). No machine here has Metal, so the JAX code path is exercised on
JAX's CPU platform and the Metal device itself is unverified.
"""

from __future__ import annotations

import inspect
import sys
import warnings
from dataclasses import fields, is_dataclass

import numpy as np
import pandas as pd
import pytest

import jnwb
import jnwb._backend as backend
from jnwb import tfr as tfr_module
from jnwb._parallel import parallel_map
from jnwb.trajectory import compute_population_trajectory

CUDA_RTOL = 1e-9
METAL_RTOL = 1e-5

FS = 1000.0
_rng = np.random.default_rng(0)
_T = np.arange(4000) / FS
X = np.sin(2 * np.pi * 20 * _T) + 0.5 * _rng.standard_normal(_T.size)
Y = np.roll(X, 7) + 0.5 * _rng.standard_normal(_T.size)
P = _rng.random((20, 10)) + 0.1
B = _rng.random((20, 10)) + 0.1
SPIKES = np.sort(_rng.uniform(0.0, 50.0, 1500))
POP = _rng.standard_normal((200, 12))
LAMINAR = _rng.standard_normal((16, 2000))


class _Session:
    """Row-index lookup, the convention of ``build_time_resolved_matrix``."""

    def __init__(self, n_units=12):
        r = np.random.default_rng(1)
        self._df = pd.DataFrame({"unit_id": list(range(n_units)), "area": ["V1"] * n_units,
                                 "quality": ["stable"] * n_units})
        self._spikes = {i: np.sort(r.uniform(0.0, 30.0, 200)) for i in range(n_units)}

    def get_units(self, quality=None, area=None):
        return self._df

    def get_spike_times(self, unit_id):
        return self._spikes.get(unit_id, np.array([]))


_EPOCHS = pd.DataFrame({"start_time": np.arange(2.0, 26.0, 1.5)})

#: Every public export with a ``device`` argument, and a small call that exercises it.
DEVICE_CALLS = {
    "band_power": lambda d: jnwb.band_power(X, fs=FS, freq_range=(13, 30), normalize=False, device=d),
    "relative_power": lambda d: jnwb.relative_power(P, B, axis=0, device=d),
    "spectral_tilt": lambda d: jnwb.spectral_tilt(X, fs=FS, device=d),
    "harmonic_analysis": lambda d: jnwb.harmonic_analysis(X, fs=FS, device=d),
    "imaginary_coherency": lambda d: jnwb.imaginary_coherency(X, Y, fs=FS, device=d),
    "wpli": lambda d: jnwb.wpli(X, Y, fs=FS, device=d),
    "cross_area_coherence": lambda d: jnwb.cross_area_coherence(
        X, Y, fs=FS, freq_bands="canonical", n_surrogates=5, device=d),
    "complex_tfr": lambda d: jnwb.complex_tfr(np.stack([X, Y]), FS, np.linspace(5, 80, 6), device=d),
    "granger_causality": lambda d: jnwb.granger_causality(X[:1500], Y[:1500], order=4, device=d),
    "UnitAnalyzer.autocorrelogram": lambda d: jnwb.UnitAnalyzer.autocorrelogram(SPIKES, device=d),
    "PopulationAnalyzer.population_trajectory":
        lambda d: jnwb.PopulationAnalyzer.population_trajectory(POP, device=d),
    "compute_population_trajectory":
        lambda d: compute_population_trajectory(_Session(), "V1", _EPOCHS, device=d),
    "rdm": lambda d: jnwb.rdm(POP[:30], device=d),
    "vflip": lambda d: jnwb.vflip(np.abs(LAMINAR[:, :64]) + 1.0, np.linspace(1, 200, 64), device=d),
    "vflip_from_lfp": lambda d: jnwb.vflip_from_lfp(LAMINAR, FS, device=d),
    "jrsa": lambda d: jnwb.jrsa(POP[:30], POP[30:60], permutations=10, rng=0, device=d),
}

#: Exports whose ``device`` is a record of what ran, not a request; they select nothing.
DEVICE_RECORDS = {"ComplexTFR"}

#: Exports whose ``backend`` is a record, likewise.
BACKEND_RECORDS = {"Provenance"}

#: Exports with a CUDA path, for the agreement measurement. rdm, vflip and jrsa have none
#: and say so; compute_population_trajectory reaches CUDA only through PyTorch.
CUDA_CAPABLE = sorted(set(DEVICE_CALLS) - {"rdm", "vflip", "vflip_from_lfp", "jrsa"})

#: Where each result records the device, for the exports that record one. band_power and
#: relative_power return a bare float and array, which have nowhere to carry it.
RECORD = {
    "complex_tfr": lambda r: r.device,
    "jrsa": lambda r: r.execution["device"],
}
for _name in ("spectral_tilt", "harmonic_analysis", "imaginary_coherency", "wpli",
              "cross_area_coherence", "granger_causality", "UnitAnalyzer.autocorrelogram",
              "PopulationAnalyzer.population_trajectory", "compute_population_trajectory"):
    RECORD[_name] = lambda r: r["device_used"]


def _public_callables():
    for name in jnwb.__all__:
        obj = getattr(jnwb, name, None)
        if inspect.isclass(obj):
            yield name, obj
            for member, fn in vars(obj).items():
                if not member.startswith("_"):
                    fn = getattr(obj, member)
                    if callable(fn):
                        yield f"{name}.{member}", fn
        elif callable(obj):
            yield name, obj


def _exports_with(param):
    found = set()
    for name, obj in _public_callables():
        try:
            params = inspect.signature(obj).parameters
        except (TypeError, ValueError):
            continue
        if param in params:
            found.add(name)
    return found


def _runtime_messages(fn):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = fn()
    return result, [str(w.message) for w in caught if issubclass(w.category, RuntimeWarning)]


def _arrays(obj, prefix=""):
    """Numeric leaves of a result, keyed by path. Device records are not numbers."""
    if is_dataclass(obj):
        obj = {f.name: getattr(obj, f.name) for f in fields(obj)}
    elif hasattr(obj, "execution") and hasattr(obj, "to_dict"):
        obj = {k: v for k, v in obj.to_dict().items() if k not in ("execution", "parameters")}
    out = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            out.update(_arrays(value, f"{prefix}.{key}"))
    elif isinstance(obj, (list, tuple)):
        for i, value in enumerate(obj):
            out.update(_arrays(value, f"{prefix}[{i}]"))
    elif isinstance(obj, (np.ndarray, float, int, np.number)) and not isinstance(obj, (bool, np.bool_)):
        arr = np.asarray(obj)
        if arr.dtype.kind in "fciu":
            out[prefix or "."] = arr
    return out


def _worst_relative_gap(ref, got):
    a, b = _arrays(ref), _arrays(got)
    assert a.keys() == b.keys()
    worst = 0.0
    for key in a:
        assert a[key].shape == b[key].shape, key
        assert np.array_equal(np.isfinite(a[key]), np.isfinite(b[key])), key
        finite = np.isfinite(a[key])
        if finite.any():
            scale = float(np.max(np.abs(a[key][finite]))) or 1.0
            worst = max(worst, float(np.max(np.abs(a[key][finite] - b[key][finite]))) / scale)
    return worst


@pytest.fixture
def no_cuda(monkeypatch):
    monkeypatch.setattr(backend, "gpu_available", lambda prefer=None: False)


@pytest.fixture
def failing_gpu(monkeypatch):
    """A device that probes as present and fails at the first upload, where an
    out-of-memory surfaces. Without CuPy the GPU branch's own import fails instead."""
    monkeypatch.setattr(backend, "gpu_available", lambda prefer=None: True)
    monkeypatch.setattr(backend, "torch_cuda_available", lambda: False)

    def out_of_memory(*args, **kwargs):
        raise MemoryError("simulated")

    for module, attr in (("cupy", "asarray"), ("torch", "as_tensor")):
        try:
            monkeypatch.setattr(__import__(module), attr, out_of_memory)
        except ImportError:
            pass


@pytest.fixture
def jax_cpu_as_metal(monkeypatch):
    """The Metal code path, run on JAX's CPU platform: what can be verified here."""
    jax = pytest.importorskip("jax")
    monkeypatch.setattr(backend, "jax_metal_device", lambda: jax.devices("cpu")[0])


class TestEveryBackendArgumentIsCovered:

    def test_the_device_table_is_every_export_that_takes_device(self):
        assert _exports_with("device") == set(DEVICE_CALLS) | DEVICE_RECORDS

    def test_the_backend_records_are_every_other_backend_argument(self):
        assert _exports_with("backend") == {"jrsa"} | BACKEND_RECORDS


class TestAnUnavailableDeviceIsAnnounced:

    @pytest.mark.parametrize("name", sorted(DEVICE_CALLS))
    def test_an_unrecognised_device_raises(self, name):
        with pytest.raises(ValueError, match="unrecognised device"):
            DEVICE_CALLS[name]("tpu")

    @pytest.mark.parametrize("metal_present", [False, True], ids=["no-metal", "metal"])
    @pytest.mark.parametrize("name", sorted(DEVICE_CALLS))
    def test_metal_warns_and_names_the_cpu_unless_the_function_runs_there(
            self, name, metal_present, monkeypatch):
        # With a Metal device present, every function but complex_tfr has no Metal path,
        # and complex_tfr's default dtype is 64-bit, which Metal cannot compute.
        monkeypatch.setattr(backend, "jax_metal_available", lambda: metal_present)
        result, messages = _runtime_messages(lambda: DEVICE_CALLS[name]("metal"))
        assert any("device='metal'" in m and "CPU" in m for m in messages), messages
        if name in RECORD:
            assert RECORD[name](result) == "cpu"

    @pytest.mark.parametrize("name", CUDA_CAPABLE)
    def test_a_cuda_failure_midway_is_announced_and_recorded(self, name, failing_gpu):
        result, messages = _runtime_messages(lambda: DEVICE_CALLS[name]("cuda"))
        assert any("GPU computation failed" in m for m in messages), messages
        if name in RECORD:
            assert RECORD[name](result) == "cpu"

    @pytest.mark.parametrize("name", sorted(DEVICE_CALLS))
    def test_cuda_without_a_device_warns_and_names_the_cpu(self, name, no_cuda):
        result, messages = _runtime_messages(lambda: DEVICE_CALLS[name]("cuda"))
        assert any("device='cuda'" in m and "CPU" in m for m in messages), messages
        if name in RECORD:
            assert RECORD[name](result) == "cpu"

    def test_jrsa_says_an_accelerator_backend_was_not_used(self):
        result, messages = _runtime_messages(
            lambda: jnwb.jrsa(POP[:30], POP[30:60], permutations=10, rng=0, backend="cupy"))
        assert any("backend='cupy'" in m and "CPU" in m for m in messages), messages
        assert result.execution["backend"] == "numpy"

    def test_jrsa_is_silent_about_a_cpu_backend(self):
        _, messages = _runtime_messages(
            lambda: jnwb.jrsa(POP[:30], POP[30:60], permutations=10, rng=0, backend="numpy"))
        assert not [m for m in messages if "backend=" in m]

    def test_parallel_map_says_it_ran_serially_without_joblib(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "joblib", None)
        result, messages = _runtime_messages(lambda: parallel_map(abs, [-1, -2, -3], n_jobs=2))
        assert result == [1, 2, 3]
        assert any("joblib" in m and "serially" in m for m in messages), messages


class TestTheResultRecordsTheDevice:

    @pytest.mark.parametrize("name", sorted(RECORD))
    def test_a_cpu_run_records_the_cpu(self, name):
        result, _ = _runtime_messages(lambda: DEVICE_CALLS[name]("cpu"))
        assert RECORD[name](result) == "cpu"

    def test_covariance_pca_pins_each_component_sign_on_the_cpu(self):
        components = jnwb.PopulationAnalyzer.population_trajectory(POP, device="cpu")["components"]
        pivots = components[np.arange(components.shape[0]), np.argmax(np.abs(components), axis=1)]
        assert np.all(pivots > 0)


@pytest.mark.skipif(not backend.cupy_available(), reason="no CUDA device through CuPy")
class TestCudaAgreesWithTheCpu:

    @pytest.mark.parametrize("name", CUDA_CAPABLE)
    def test_within_tolerance_and_recorded(self, name):
        if name == "compute_population_trajectory" and not backend.torch_cuda_available():
            pytest.skip("its CUDA path is PyTorch's, and PyTorch has no CUDA device here")
        cpu, _ = _runtime_messages(lambda: DEVICE_CALLS[name]("cpu"))
        cuda, messages = _runtime_messages(lambda: DEVICE_CALLS[name]("cuda"))
        assert not [m for m in messages if "device" in m or "GPU" in m], messages
        assert _worst_relative_gap(cpu, cuda) <= CUDA_RTOL
        if name in RECORD:
            assert RECORD[name](cuda) == "cuda"

    def test_a_granger_fit_that_fails_midway_recomputes_the_whole_call_on_the_cpu(self, monkeypatch):
        import cupy

        real, calls = cupy.linalg.lstsq, []

        def fail_on_the_third(*args, **kwargs):
            calls.append(1)
            if len(calls) == 3:
                raise MemoryError("simulated")
            return real(*args, **kwargs)

        cpu = jnwb.granger_causality(X[:1500], Y[:1500], order="auto", device="cpu")
        monkeypatch.setattr(cupy.linalg, "lstsq", fail_on_the_third)
        got, messages = _runtime_messages(
            lambda: jnwb.granger_causality(X[:1500], Y[:1500], order="auto", device="cuda"))
        assert any("GPU computation failed" in m for m in messages), messages
        assert got["device_used"] == "cpu"
        assert got["F_1_to_2"] == cpu["F_1_to_2"] and got["F_2_to_1"] == cpu["F_2_to_1"]
        assert got["order_1_to_2"] == cpu["order_1_to_2"]


class TestMetal:
    """Implemented and unverified on Metal hardware; the JAX path is verified here."""

    def _tfr(self, device, dtype=np.complex64):
        return jnwb.complex_tfr(np.stack([X, Y]), FS, np.linspace(5, 80, 6), dtype=dtype, device=device)

    def test_complex_tfr_runs_its_jax_path_and_agrees_with_the_cpu(self, jax_cpu_as_metal, monkeypatch):
        ran = []
        real = tfr_module._convolve_jax
        monkeypatch.setattr(tfr_module, "_convolve_jax", lambda *a: ran.append(1) or real(*a))
        cpu = self._tfr("cpu")
        metal, messages = _runtime_messages(lambda: self._tfr("metal"))
        assert ran and not messages
        assert metal.device == "metal" and metal.z.dtype == np.complex64
        assert np.max(np.abs(metal.z - cpu.z)) <= METAL_RTOL * np.max(np.abs(cpu.z))

    def test_a_64_bit_request_is_computed_on_the_cpu_and_says_why(self, jax_cpu_as_metal):
        result, messages = _runtime_messages(lambda: self._tfr("metal", dtype=np.complex128))
        assert any("64-bit" in m and "CPU" in m for m in messages), messages
        assert result.device == "cpu"

    def test_a_metal_failure_recomputes_on_the_cpu(self, jax_cpu_as_metal, monkeypatch):
        def broken(*args):
            raise RuntimeError("simulated")

        monkeypatch.setattr(tfr_module, "_convolve_jax", broken)
        result, messages = _runtime_messages(lambda: self._tfr("metal"))
        assert any("GPU computation failed" in m for m in messages), messages
        assert result.device == "cpu"
        assert np.array_equal(result.z, self._tfr("cpu").z)
