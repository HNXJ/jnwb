"""Regression tests for P0-B (2026-08-17): jnwb.jrsa._pearson/_spearman/_procrustes used to
fabricate r=0/p=1.0 (on insufficient-n) or disparity=1.0 (on any exception) instead of failing
loudly. See artifacts/.lab/bug-jrsa-fabricated-failure-values-20260817.json.
"""
from __future__ import annotations

import numpy as np
import pytest

from jnwb.jrsa import _pearson, _spearman, _procrustes
from jnwb.statistics import StatisticalAnalysis


class TestCorrelateNoFabrication:
    def test_insufficient_samples_returns_error_key(self):
        x = np.array([1.0, 2.0])
        y = np.array([3.0, 4.0])
        res = StatisticalAnalysis.correlate(x, y)
        assert "error" in res

    def test_constant_input_propagates_nan_not_zero_one(self):
        x = np.full(10, 5.0)
        y = np.arange(10, dtype=float)
        res = StatisticalAnalysis.correlate(x, y)
        assert np.isnan(res["parametric"]["statistic"])
        assert np.isnan(res["parametric"]["pval"])
        assert np.isnan(res["non_parametric"]["statistic"])
        assert np.isnan(res["non_parametric"]["pval"])


class TestPearsonSpearmanRaiseOnInsufficientData:
    def test_pearson_raises_on_insufficient_samples(self):
        x = np.array([1.0, 2.0])
        y = np.array([3.0, 4.0])
        with pytest.raises(ValueError, match="cannot compute correlation"):
            _pearson(x, y)

    def test_spearman_raises_on_insufficient_samples(self):
        x = np.array([1.0, 2.0])
        y = np.array([3.0, 4.0])
        with pytest.raises(ValueError, match="cannot compute correlation"):
            _spearman(x, y)

    def test_pearson_still_works_on_valid_data(self):
        rng = np.random.default_rng(0)
        x = rng.normal(size=50)
        y = x + rng.normal(scale=0.05, size=50)
        r, t, abs_r, p, df = _pearson(x, y)
        assert r > 0.9
        assert p < 0.05


class TestProcrustesDoesNotSwallowExceptions:
    def test_procrustes_reraises_instead_of_fabricating(self):
        # A zero-variance (constant) configuration makes scipy.spatial.procrustes raise
        # ValueError("Input matrices must contain >1 unique points") -- previously this was
        # caught and silently rewritten to disparity=1.0 (sim=0.0).
        X = np.zeros((5, 3))
        Y = np.random.default_rng(1).normal(size=(5, 3))
        with pytest.raises(Exception):
            _procrustes(X, Y)

    def test_procrustes_still_works_on_valid_data(self):
        rng = np.random.default_rng(2)
        X = rng.normal(size=(10, 3))
        Y = X + rng.normal(scale=0.01, size=(10, 3))
        sim, _, _, _, _ = _procrustes(X, Y)
        assert sim > 0.9
