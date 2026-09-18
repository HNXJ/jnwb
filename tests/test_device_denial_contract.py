"""05-44: with a GPU present, two `device='cuda'` requests were denied in silence.

`jnwb/_backend.py` exists so that a caller who asks for an accelerator and does not get
one is told. It covered two denial reasons and missed the third:

* :func:`resolve_device` warns when no usable device is found.
* :func:`warn_device_fallback` warns when a device failed part-way through.
* Nothing warned when the device was fine and the code path simply had no GPU branch.

Measured on a live RTX A4000 by counting `cupy.asarray` / `cupy.asnumpy` calls:

    vflip(..., device='cuda')                    h2d=0  d2h=0  warnings=0
    fit_var_bivariate(..., ridge=0.0)            h2d=4  d2h=0  warnings=0
    fit_var_bivariate(..., ridge=0.1)            h2d=0  d2h=0  warnings=0
    granger_causality(..., ridge=0.1)            h2d=0  d2h=0  warnings=0
    rdm(..., device='cuda')                      h2d=0  d2h=0  warnings=1

`laminar.py` contains no cupy or torch call anywhere, so `vflip` could never honour the
request; its resolver result was assigned to `_`. `fit_var_bivariate` gated its GPU
branch on `... == CUDA and ridge <= 0`, after resolving. In both cases the caller *with*
a GPU was denied silently while the caller *without* one was warned -- the better the
hardware, the quieter the denial. `rdm` already did the right thing inline, and is the
shape the other two now follow.

Two further defects found while reproducing, neither in the audit:

* `select_optimal_lag` called `fit_var_bivariate` inside its lag loop, so each iteration
  re-resolved the device. One `select_optimal_lag(max_lag=6, device='cuda')` on a
  machine with no GPU emitted **six** identical warnings; `granger_causality(order='auto')`
  reaches it up to `2 * max_lag + 2` times. `_backend.py`'s own docstring says to resolve
  once, before any computation.
* Every one of those warnings named `fit_var_bivariate`, which is not exported -- a
  reader of the warning is sent to code they did not call.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

import jnwb._backend as backend
from jnwb._backend import CUDA, warn_no_gpu_path
from jnwb.connectivity import fit_var_bivariate, granger_causality, select_optimal_lag
from jnwb.laminar import vflip
from jnwb.rsa import rdm

requires_cuda = pytest.mark.skipif(
    not backend.torch_cuda_available(), reason="no CUDA device on this machine"
)


@pytest.fixture
def pretend_gpu(monkeypatch):
    """A usable device, without needing one. This is the case that was silent: with no
    GPU every one of these calls warns from `resolve_device` instead, which is why the
    defect was invisible in CI."""
    monkeypatch.setattr(backend, "gpu_available", lambda prefer=None: True)


def _runtime_warnings(fn):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fn()
    return [str(w.message) for w in caught
            if issubclass(w.category, RuntimeWarning)]


@pytest.fixture
def signals():
    rng = np.random.default_rng(0)
    x = rng.standard_normal(600)
    return x, np.roll(x, 3) + 0.3 * rng.standard_normal(600)


@pytest.fixture
def psd_and_freqs():
    rng = np.random.default_rng(0)
    return rng.random((16, 128)) + 1.0, np.linspace(1.0, 200.0, 128)


class TestTheThirdDenialReasonExists:

    def test_it_names_the_context_and_the_reason(self):
        messages = _runtime_warnings(
            lambda: warn_no_gpu_path("f", "f has no GPU implementation"))

        assert messages == [
            "f: device='cuda' was requested, but f has no GPU implementation; "
            "computing on CPU."
        ]

    def test_it_is_a_runtime_warning_like_the_other_two(self):
        with pytest.warns(RuntimeWarning):
            warn_no_gpu_path("f", "reason")

    def test_it_is_exported_from_the_backend(self):
        assert "warn_no_gpu_path" in backend.__all__


class TestEveryDeniedRequestSaysSo:
    """05-44's accept condition: every `device='cuda'` call either reaches the GPU or
    warns. These run with a pretended GPU, so a denial cannot hide behind
    `resolve_device`'s own no-device warning."""

    def test_vflip_says_it_has_no_gpu_implementation(self, pretend_gpu, psd_and_freqs):
        psd, freqs = psd_and_freqs
        messages = _runtime_warnings(
            lambda: vflip(psd, freqs, contact_spacing=100.0, device="cuda"))

        assert len(messages) == 1
        assert "vflip: device='cuda' was requested" in messages[0]
        assert "no GPU implementation" in messages[0]

    def test_vflip_is_silent_when_the_caller_asked_for_cpu(self, pretend_gpu,
                                                           psd_and_freqs):
        """Nothing was denied a CPU caller, so nothing should be said to one."""
        psd, freqs = psd_and_freqs

        assert _runtime_warnings(
            lambda: vflip(psd, freqs, contact_spacing=100.0, device="cpu")) == []

    def test_the_ridge_solver_says_which_argument_denied_the_gpu(self, pretend_gpu,
                                                                 signals):
        x, y = signals
        messages = _runtime_warnings(
            lambda: fit_var_bivariate(x, y, 5, device="cuda", ridge=0.1))

        assert len(messages) == 1
        assert "ridge" in messages[0]
        assert "pass ridge=0" in messages[0]

    def test_granger_causality_says_so_too(self, pretend_gpu, signals):
        x, y = signals
        messages = _runtime_warnings(
            lambda: granger_causality(x, y, order=5, device="cuda", ridge=0.1))

        assert len(messages) == 1
        assert messages[0].startswith("granger_causality: device='cuda'")

    def test_select_optimal_lag_says_so_too(self, pretend_gpu, signals):
        x, y = signals
        messages = _runtime_warnings(
            lambda: select_optimal_lag(x, y, max_lag=4, device="cuda", ridge=0.1))

        assert len(messages) == 1
        assert messages[0].startswith("select_optimal_lag: device='cuda'")

    def test_rdm_still_says_so(self, pretend_gpu):
        """It was already correct; it now goes through the shared helper, so the
        message must not have drifted."""
        rng = np.random.default_rng(0)
        messages = _runtime_warnings(
            lambda: rdm(rng.standard_normal((12, 40)), metric="correlation",
                        device="cuda"))

        assert messages == [
            "rdm: device='cuda' was requested, but rdm has no GPU implementation; "
            "computing on CPU."
        ]


class TestTheWarningNamesTheFunctionTheCallerInvoked:
    """`fit_var_bivariate` is not in `jnwb.__all__`. A warning naming it sends the
    reader to code they did not call."""

    def test_granger_causality_never_names_its_private_helper(self, pretend_gpu,
                                                              signals):
        x, y = signals
        messages = _runtime_warnings(
            lambda: granger_causality(x, y, order=5, device="cuda", ridge=0.1))

        assert all("fit_var_bivariate" not in m for m in messages)

    def test_select_optimal_lag_never_names_it_either(self, pretend_gpu, signals):
        x, y = signals
        messages = _runtime_warnings(
            lambda: select_optimal_lag(x, y, max_lag=4, device="cuda", ridge=0.1))

        assert all("fit_var_bivariate" not in m for m in messages)

    def test_a_gpu_failure_mid_computation_names_it_too(self, pretend_gpu, monkeypatch,
                                                        signals):
        """The reachable half of `context`. With `ridge=0` the GPU branch is entered,
        so a failure inside it reaches `warn_device_fallback` -- the one place the
        threaded name survives all the way from `granger_causality` to a warning the
        caller sees."""
        import sys

        class _Exploding:
            @staticmethod
            def asarray(*args, **kwargs):
                raise RuntimeError("out of memory")

        monkeypatch.setitem(sys.modules, "cupy", _Exploding)
        x, y = signals
        messages = _runtime_warnings(
            lambda: granger_causality(x, y, order=5, device="cuda", ridge=0.0))

        assert any("granger_causality: GPU computation failed" in m for m in messages)
        assert all("fit_var_bivariate" not in m for m in messages)

    def test_a_direct_call_still_names_itself(self, pretend_gpu, signals):
        """The default context. Someone who really did call it should see its name."""
        x, y = signals
        messages = _runtime_warnings(
            lambda: fit_var_bivariate(x, y, 5, device="cuda", ridge=0.1))

        assert messages[0].startswith("fit_var_bivariate: ")


class TestTheDeviceIsResolvedOncePerCall:
    """`_backend.py`: "Call this once, before any computation." A resolver inside a loop
    warns once per iteration."""

    @pytest.fixture
    def no_gpu(self, monkeypatch):
        monkeypatch.setattr(backend, "gpu_available", lambda prefer=None: False)

    @pytest.mark.parametrize("max_lag", [2, 6, 9])
    def test_select_optimal_lag_warns_once_not_once_per_lag(self, no_gpu, signals,
                                                            max_lag):
        x, y = signals
        messages = _runtime_warnings(
            lambda: select_optimal_lag(x, y, max_lag=max_lag, device="cuda"))

        assert len(messages) == 1, f"{len(messages)} warnings for max_lag={max_lag}"

    def test_granger_causality_warns_once_with_an_explicit_order(self, no_gpu, signals):
        x, y = signals

        assert len(_runtime_warnings(
            lambda: granger_causality(x, y, order=5, device="cuda"))) == 1

    def test_granger_causality_warns_once_even_when_it_selects_the_order(self, no_gpu,
                                                                         signals):
        """order='auto' reaches `fit_var_bivariate` up to 2*max_lag + 2 times."""
        x, y = signals

        assert len(_runtime_warnings(
            lambda: granger_causality(x, y, order="auto", device="cuda"))) == 1


@requires_cuda
class TestARequestThatCanBeHonouredStillIs:
    """The other half of the contract: warning about everything would be just as
    useless. Counting `cupy.asarray` is the only way to tell a real GPU call from a
    quiet CPU one."""

    @staticmethod
    def _count_transfers(fn):
        import cupy as cp

        calls = []
        original = cp.asarray

        def counting(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        cp.asarray = counting
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                fn()
        finally:
            cp.asarray = original
        return len(calls), [str(w.message) for w in caught
                            if issubclass(w.category, RuntimeWarning)]

    def test_the_lstsq_solver_reaches_the_gpu_without_complaint(self, signals):
        x, y = signals
        transfers, messages = self._count_transfers(
            lambda: fit_var_bivariate(x, y, 5, device="cuda", ridge=0.0))

        assert transfers > 0
        assert messages == []

    def test_granger_causality_reaches_it_too(self, signals):
        x, y = signals
        transfers, messages = self._count_transfers(
            lambda: granger_causality(x, y, order=5, device="cuda", ridge=0.0))

        assert transfers > 0
        assert messages == []


class TestTheBackendDocstringCountsItsOwnCallSites:
    """The docstring opened with "Fifteen call sites across seven modules" while the
    package had sixteen across nine. A number in prose drifts the moment anyone adds a
    site, and nothing here noticed for five releases."""

    WORDS = {"Five": 5, "Six": 6, "Seven": 7, "Eight": 8, "Nine": 9, "Ten": 10,
             "Eleven": 11, "Twelve": 12, "Thirteen": 13, "Fourteen": 14,
             "Fifteen": 15, "Sixteen": 16, "Seventeen": 17, "Eighteen": 18,
             "Nineteen": 19, "Twenty": 20, "seven": 7, "eight": 8, "nine": 9,
             "ten": 10, "eleven": 11, "twelve": 12}

    @staticmethod
    def _measure():
        import pathlib
        import re

        root = pathlib.Path(backend.__file__).parent
        sites, modules = 0, set()
        for path in sorted(root.glob("*.py")):
            if path.name == "_backend.py":
                continue
            found = len(re.findall(r"\bresolve_device\s*\(", path.read_text("utf-8")))
            if found:
                sites += found
                modules.add(path.stem)
        return sites, len(modules)

    def test_the_stated_numbers_are_the_real_ones(self):
        import re

        claim = re.search(r"(\w+) call sites across (\w+) modules", backend.__doc__)
        assert claim is not None, "the docstring no longer states a count"
        stated = (self.WORDS[claim.group(1)], self.WORDS[claim.group(2)])

        assert stated == self._measure(), (
            f"jnwb/_backend.py says {claim.group(0)}; the package has "
            f"{self._measure()[0]} across {self._measure()[1]}")
