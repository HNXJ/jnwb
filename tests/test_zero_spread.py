"""Standardisation and scaling decide zero spread exactly.

The computed std of a constant 0.3 is rounding residue (about 1e-17), not 0, so a guard such as
``std == 0`` or ``sd > 0`` reads that constant as varying; its centred values are the same
residue, and dividing one by the other turned the constant into a column of +-1. Each test
compares a constant whose std computes to exactly 0 (0.5, 0.0, 50.0) with one whose std does not
(0.3, 1/0.03); the two must give the same result.
"""
from __future__ import annotations

import warnings

import numpy as np
import pytest

import jnwb
from jnwb._backend import torch_cuda_available

requires_cuda = pytest.mark.skipif(not torch_cuda_available(),
                                   reason="no CUDA device on this machine")
DEVICES = ["cpu", pytest.param("cuda", marks=requires_cuda)]


@pytest.fixture(autouse=True)
def _quiet():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        yield


@pytest.mark.parametrize("device", DEVICES)
def test_gpu_pca_gives_a_constant_column_no_loading(device):
    from jnwb.gpu_pca import gpu_pca

    rng = np.random.default_rng(0)
    out = {}
    for c in (0.5, 0.3):
        m = rng.normal(size=(40, 5)) if c == 0.5 else out["m"]
        m = m.copy()
        m[:, 2] = c
        out["m"] = m
        out[c] = gpu_pca(m, n_components=3, device=device)
    # A constant 0.3 column took a whole component (|loading| 1.0).
    assert np.all(np.abs(out[0.3][1][:, 2]) < 1e-12)
    np.testing.assert_array_equal(out[0.3][0], out[0.5][0])
    assert out[0.3][2] == out[0.5][2]


@pytest.mark.parametrize("device", DEVICES)
def test_trajectory_gives_a_constant_unit_no_weight(device, monkeypatch):
    import jnwb.trajectory as traj

    rng = np.random.default_rng(1)
    base = rng.poisson(5.0, size=(12, 6, 20)).astype(float) / 0.03
    results = {}
    for rate in (0.0, 1 / 0.03):              # silent, and a steady 33.3 Hz
        X = base.copy()
        X[:, 3, :] = rate
        monkeypatch.setattr(traj, "build_time_resolved_matrix",
                            lambda *a, _X=X, **k: (_X, list(range(6)), np.arange(20.0)))
        results[rate] = traj.compute_population_trajectory(None, "A", None, n_components=3,
                                                           device=device)
    np.testing.assert_array_equal(results[1 / 0.03]["trajectory"], results[0.0]["trajectory"])
    assert results[1 / 0.03]["explained_variance"] == results[0.0]["explained_variance"]


def test_jrsa_standardize_takes_a_constant_row_to_zero():
    rng = np.random.default_rng(2)
    x1, x2 = rng.normal(size=(6, 30)), rng.normal(size=(6, 30))
    values = {}
    for c in (0.5, 0.3):
        a = x1.copy()
        a[2] = c
        a[4, 5] = np.nan                       # NaN-aware: a NaN stays NaN, the rest scale
        values[c] = float(jnwb.jrsa(a, x2, metric="pearson", standardize=True,
                                    permutations=0).value)
    assert values[0.3] == values[0.5]
    # nan_policy='omit' drops the NaN's column from both inputs; the rest are z-scored.
    keep = np.arange(30) != 5
    manual = a[:, keep]
    manual = (manual - manual.mean(axis=1, keepdims=True)) / manual.std(axis=1, keepdims=True)
    manual[2] = 0.0
    b = x2[:, keep]
    x2z = (b - b.mean(axis=1, keepdims=True)) / b.std(axis=1, keepdims=True)
    assert values[0.3] == pytest.approx(
        float(jnwb.jrsa(manual, x2z, metric="pearson", permutations=0).value), rel=1e-12)


def test_zscore_rule():
    from jnwb._spread import is_constant, zscore

    np.testing.assert_array_equal(zscore(np.array([[0.3, np.nan, 0.3], [1.0, np.nan, 3.0]]),
                                         axis=1, ignore_nan=True),
                                  [[0.0, np.nan, 0.0], [-1.0, np.nan, 1.0]])
    assert is_constant(np.full(10, 0.3)) and np.std(np.full(10, 0.3)) > 0
    assert not is_constant(np.array([0.3, np.nextafter(0.3, 1.0)]))
    assert zscore(np.full((4, 2), 0.3, dtype=np.float32), axis=0).dtype == np.float32


def test_a_constant_baseline_rate_gives_no_response_z():
    onsets = np.arange(1.0, 21.0)
    rng = np.random.default_rng(3)
    spikes = []
    for t in onsets:                           # 7 baseline spikes in 0.15 s: 46.67 Hz each trial
        spikes += list(t - 0.15 + (np.arange(7) + 0.5) * 0.15 / 7)
        spikes += list(t + 0.01 + 0.01 * np.arange(int(rng.integers(3, 8))))
    res = jnwb.compute_response_metrics(np.sort(spikes), onsets, baseline_window_s=(-0.15, 0.0),
                                        response_window_s=(0.0, 0.15))
    # It read -2.1e15, which classify_response_significance takes as a strong response.
    assert np.isnan(res["response_zscore"])
    spikes.append(3.0 - 0.01)                   # one extra baseline spike: a defined z
    res = jnwb.compute_response_metrics(np.sort(spikes), onsets, baseline_window_s=(-0.15, 0.0),
                                        response_window_s=(0.0, 0.15))
    assert np.isfinite(res["response_zscore"])


def test_per_trial_zscore_takes_a_constant_trial_to_zero():
    from jnwb.connectivity import _detrend_trials

    rng = np.random.default_rng(4)
    a = rng.normal(size=(3, 50))
    a[1] = 0.3
    z = _detrend_trials(a, "zscore")
    assert np.all(z[1] == 0.0)                 # it read -1.0 throughout
    np.testing.assert_allclose(z[0], (a[0] - a[0].mean()) / a[0].std(), rtol=1e-12)


def test_deprecated_granger_causality_treats_constants_alike():
    from jnwb.connectivity import granger_causality

    s2 = np.random.default_rng(5).normal(size=400)
    out = {c: granger_causality(np.full(400, c), s2, order=3) for c in (0.5, 0.3)}
    np.testing.assert_equal(out[0.3], out[0.5])


def test_ljung_box_has_no_p_for_constant_residuals():
    from jnwb.connectivity import _ljung_box_pvalue

    assert np.isnan(_ljung_box_pvalue(np.full(200, 0.5)))
    assert np.isnan(_ljung_box_pvalue(np.full(200, 0.3)))    # it read 0.0


def _cupy_usable():
    from jnwb._backend import gpu_available
    return bool(gpu_available(prefer="cupy"))


@pytest.mark.skipif(not _cupy_usable(), reason="no usable CUDA device via CuPy")
def test_cupy_pearson_of_a_constant_is_nan_as_on_the_cpu():
    """cp.std of 100 values of 2.7 is 4.4e-16, and r read about 1e-16 where the CPU reads NaN.
    (The Spearman path ranks first; the ranks of a constant are all (n + 1) / 2, exact.)"""
    import importlib

    import cupy as cp
    jr = importlib.import_module("jnwb.jrsa")

    b = np.random.default_rng(7).normal(size=100)
    for c in (2.7, 0.5):
        a = np.full(100, c)
        assert np.isnan(float(jr._pearson(a, b)[0]))
        assert np.isnan(float(jr._pearson(cp.asarray(a), cp.asarray(b))[0]))
