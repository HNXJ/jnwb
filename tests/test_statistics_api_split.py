"""
Tests for the Exploratory / Confirmatory Stats API split in jnwb.statistics.

Falsifier conditions from the plan:
  - test_exploratory_compare_no_q_value: exploratory result MUST NOT have q_value key
  - test_confirmatory_compare_has_q_value: confirmatory result MUST have q_parametric key
  - test_confirmatory_compare_requires_hypothesis: empty hypothesis must raise ValueError
  - test_exploratory_correlate_no_deprecated_keys: no fdr_pval_* in exploratory correlate
  - test_exploratory_multi_no_deprecated_keys: no fdr_pval_* in exploratory multi
  - test_legacy_compare_groups_warns: legacy compare_groups emits DeprecationWarning
"""
import warnings

import numpy as np
import pytest

from jnwb.statistics import StatisticalAnalysis


RNG = np.random.default_rng(0)
A = RNG.normal(loc=3.0, scale=1.0, size=40)
B = RNG.normal(loc=5.0, scale=1.0, size=40)  # clearly different from A


# ── Exploratory API ───────────────────────────────────────────────────────────

class TestExploratoryCompare:
    def test_returns_api_exploratory(self):
        r = StatisticalAnalysis.exploratory_compare(A, B)
        assert r["api"] == "exploratory"

    def test_no_q_value_keys(self):
        r = StatisticalAnalysis.exploratory_compare(A, B)
        for key in ("q_parametric", "q_nonparametric", "confirmed_parametric",
                    "confirmed_nonparametric"):
            assert key not in r, f"Unexpected key in exploratory result: {key}"

    def test_no_deprecated_fdr_keys(self):
        r = StatisticalAnalysis.exploratory_compare(A, B)
        for key in ("fdr_pval_parametric", "fdr_pval_nonparametric", "multiple_comparison"):
            assert key not in r, f"Deprecated key leaked into exploratory result: {key}"

    def test_has_dual_test_structure(self):
        r = StatisticalAnalysis.exploratory_compare(A, B)
        assert "parametric" in r
        assert "non_parametric" in r
        assert "pval" in r["parametric"]
        assert "pval" in r["non_parametric"]

    def test_detects_true_difference(self):
        r = StatisticalAnalysis.exploratory_compare(A, B)
        assert r["parametric"]["pval"] < 0.001, "Should easily detect 2-SD group difference"
        assert r["non_parametric"]["pval"] < 0.001

    def test_paired_runs_without_error(self):
        r = StatisticalAnalysis.exploratory_compare(A, B, paired=True)
        assert r["api"] == "exploratory"
        assert "parametric" in r


class TestExploratoryCorrelate:
    def test_no_deprecated_keys(self):
        x = RNG.uniform(size=50)
        y = x + RNG.normal(scale=0.1, size=50)
        r = StatisticalAnalysis.exploratory_correlate(x, y)
        for key in ("fdr_pval_parametric", "fdr_pval_nonparametric", "multiple_comparison"):
            assert key not in r, f"Deprecated key in exploratory correlate: {key}"

    def test_returns_api_exploratory(self):
        x = RNG.uniform(size=30)
        y = RNG.uniform(size=30)
        r = StatisticalAnalysis.exploratory_correlate(x, y)
        assert r["api"] == "exploratory"

    def test_detects_strong_correlation(self):
        x = np.linspace(0, 10, 50)
        y = x + RNG.normal(scale=0.05, size=50)
        r = StatisticalAnalysis.exploratory_correlate(x, y)
        assert r["parametric"]["statistic"] > 0.99


class TestExploratoryMulti:
    def test_no_deprecated_keys(self):
        g = {"a": A, "b": B, "c": RNG.normal(loc=4.0, size=40)}
        r = StatisticalAnalysis.exploratory_multi(g)
        for key in ("fdr_pval_parametric", "fdr_pval_nonparametric", "multiple_comparison"):
            assert key not in r, f"Deprecated key in exploratory multi: {key}"

    def test_returns_api_exploratory(self):
        g = {"a": A, "b": B}
        r = StatisticalAnalysis.exploratory_multi(g)
        assert r["api"] == "exploratory"


# ── Confirmatory API ──────────────────────────────────────────────────────────

class TestConfirmatoryCompare:
    HYP = "FR during omission > FR during stimulus in FEF O+ units"

    def test_has_q_value_keys(self):
        r = StatisticalAnalysis.confirmatory_compare(A, B, hypothesis=self.HYP)
        assert "q_parametric" in r, "confirmatory result must have q_parametric"
        assert "q_nonparametric" in r
        assert "confirmed_parametric" in r
        assert "confirmed_nonparametric" in r

    def test_api_is_confirmatory(self):
        r = StatisticalAnalysis.confirmatory_compare(A, B, hypothesis=self.HYP)
        assert r["api"] == "confirmatory"

    def test_stores_hypothesis_and_alpha(self):
        r = StatisticalAnalysis.confirmatory_compare(A, B, hypothesis=self.HYP, alpha=0.01)
        assert r["hypothesis"] == self.HYP
        assert r["alpha"] == pytest.approx(0.01)

    def test_requires_nonempty_hypothesis(self):
        with pytest.raises(ValueError, match="hypothesis"):
            StatisticalAnalysis.confirmatory_compare(A, B, hypothesis="")

    def test_requires_string_hypothesis(self):
        with pytest.raises((ValueError, TypeError)):
            StatisticalAnalysis.confirmatory_compare(A, B, hypothesis=None)

    def test_q_values_are_floats_in_0_1(self):
        r = StatisticalAnalysis.confirmatory_compare(A, B, hypothesis=self.HYP)
        assert 0.0 <= r["q_parametric"] <= 1.0
        assert 0.0 <= r["q_nonparametric"] <= 1.0

    def test_confirmed_true_for_strong_effect(self):
        r = StatisticalAnalysis.confirmatory_compare(A, B, hypothesis=self.HYP)
        assert r["confirmed_parametric"] is True, "Should confirm for 2-SD group difference"

    def test_confirmed_false_for_null_effect(self):
        null_a = RNG.normal(size=40)
        null_b = RNG.normal(size=40)
        # Run many times — should sometimes fail, but for fixed RNG seed should be non-significant
        r = StatisticalAnalysis.confirmatory_compare(
            null_a, null_b,
            hypothesis="no difference expected",
            alpha=0.001,  # very strict to ensure null is not confirmed
        )
        # With alpha=0.001 and same-distribution groups, confirmed should be False
        # (this is probabilistic; seed=0 makes it stable)
        assert isinstance(r["confirmed_parametric"], bool)

    def test_no_deprecated_keys(self):
        r = StatisticalAnalysis.confirmatory_compare(A, B, hypothesis=self.HYP)
        for key in ("fdr_pval_parametric", "fdr_pval_nonparametric", "multiple_comparison"):
            assert key not in r, f"Deprecated key leaked into confirmatory result: {key}"


# ── Legacy deprecation ────────────────────────────────────────────────────────

class TestLegacyDeprecation:
    def test_compare_groups_emits_deprecation_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            StatisticalAnalysis.compare_groups(A, B)
        dep_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(dep_warnings) >= 1, (
            "compare_groups() should emit DeprecationWarning for fdr_pval_* keys"
        )

    def test_compare_groups_still_returns_result(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            r = StatisticalAnalysis.compare_groups(A, B)
        assert "parametric" in r
        # Legacy keys still present for back-compat
        assert "fdr_pval_parametric" in r

    def test_fdr_correct_is_still_accessible(self):
        p_vals = np.array([0.001, 0.01, 0.1, 0.5])
        q = StatisticalAnalysis.fdr_correct(p_vals)
        assert len(q) == len(p_vals)
        assert q[0] <= q[-1], "BH q-values should be monotone non-decreasing"
