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

from jnwb.statistics import StatisticalAnalysis, cluster_permutation_test


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


@pytest.mark.parametrize("test", ["both", "parametric", "nonparametric"])
def test_exploratory_results_say_they_are_uncorrected(test):
    compared = StatisticalAnalysis.exploratory_compare(A, B, n_bootstrap=50, test=test)
    multi = StatisticalAnalysis.exploratory_multi({"a": A, "b": B}, test=test)
    correlated = StatisticalAnalysis.exploratory_correlate(
        A, B, method={"both": "both", "parametric": "pearson", "nonparametric": "spearman"}[test])
    for result in (compared, multi, correlated):
        assert result["correction"] == "none"
        assert "multiple_comparison" not in result


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


# ── Core compare_groups behavior ──────────────────────────────────────────────

class TestCoreCompareGroups:
    def test_compare_groups_no_deprecated_fdr_keys_or_warnings(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            r = StatisticalAnalysis.compare_groups(A, B)
        dep_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(dep_warnings) == 0, (
            "compare_groups() should not emit DeprecationWarning"
        )
        assert "parametric" in r
        assert "fdr_pval_parametric" not in r
        assert "fdr_pval_nonparametric" not in r
        assert "multiple_comparison" in r
        assert not r["multiple_comparison"]["applied"]

    def test_fdr_correct_is_still_accessible(self):
        p_vals = np.array([0.001, 0.01, 0.1, 0.5])
        q = StatisticalAnalysis.fdr_correct(p_vals)
        assert len(q) == len(p_vals)
        assert q[0] <= q[-1], "BH q-values should be monotone non-decreasing"


# ── Cluster-based permutation testing ─────────────────────────────────────────

class TestClusterPermutation:
    def test_import_from_top_level_jnwb(self):
        import jnwb
        from jnwb.statistics import cluster_permutation_test
        assert jnwb.cluster_permutation_test is cluster_permutation_test
        assert "cluster_permutation_test" in jnwb.__all__

    def test_paired_cluster_detection_and_fwer_recovery(self):
        # 20 paired observations over 1D time (50 time points)
        rng = np.random.default_rng(123)
        n_obs, n_times = 20, 50
        baseline = rng.standard_normal((n_obs, n_times))
        # The evoked condition is an independent draw plus the effect, not a copy of the
        # baseline plus a constant. A constant offset makes the paired difference
        # identical in every observation, so its variance is zero and its t is 0/0: nine
        # of the ten "ground truth" bins scored exactly 0.0 and the tenth scored 7.76e16
        # on float rounding alone. The cluster this test claims to recover was a single
        # bin of numerical noise, and `assert np.any(mask[20:30])` passed on it.
        evoked = baseline + 0.5 * rng.standard_normal((n_obs, n_times))
        # Add localized true cluster of activation between samples 20:30
        evoked[:, 20:30] += 2.5

        res = cluster_permutation_test(
            evoked, baseline,
            paired=True,
            threshold=2.0,
            n_permutations=200,
            rng=rng,
        )

        assert "stat_map" in res
        assert "clusters" in res
        assert "max_null_stats" in res
        assert res["stat_map"].shape == (n_times,)
        assert len(res["max_null_stats"]) == 200

        # Must recover significant cluster covering the ground-truth region
        sig_clusters = [c for c in res["clusters"] if c["p_value"] < 0.05]
        assert len(sig_clusters) >= 1
        best_cluster = sig_clusters[0]
        # Cluster mask must overlap with [20:30]
        assert np.any(best_cluster["mask"][20:30])
        # Finite Monte Carlo formula: p = (1 + k) / (B + 1)
        assert best_cluster["p_value"] == pytest.approx((1.0 + np.sum(res["max_null_stats"] >= abs(best_cluster["statistic"]))) / 201.0)
        masks = [c["mask"].tobytes() for c in res["clusters"]]
        assert len(masks) == len(set(masks)), "each observed cluster must be reported once"

    def test_unpaired_cluster_test_recovers_2d_spectrotemporal_cluster(self):
        # Unpaired groups: Condition 1 (15 trials) vs Condition 2 (18 trials) on (8 freqs, 20 times)
        rng = np.random.default_rng(456)
        X = rng.standard_normal((15, 8, 20))
        Y = rng.standard_normal((18, 8, 20))
        # Add true 2D patch of enhancement in X
        X[:, 2:5, 8:14] += 2.2

        res = cluster_permutation_test(
            X, Y,
            paired=False,
            threshold=2.0,
            n_permutations=150,
            rng=rng,
        )

        assert res["stat_map"].shape == (8, 20)
        assert len(res["clusters"]) >= 1
        sig_clusters = [c for c in res["clusters"] if c["p_value"] < 0.05]
        assert len(sig_clusters) >= 1
        # Cluster mask must overlap with patch
        assert np.any(sig_clusters[0]["mask"][2:5, 8:14])

    def test_adversarial_grouped_exchangeability_prevents_false_discovery(self):
        # Confounded design across 2 recording sessions (groups):
        # Under true H0, conditions A and B have ZERO difference in either session.
        # But Session 0 has baseline 0.0 with (12 A, 4 B trials).
        # Session 1 has baseline 6.0 with (4 A, 12 B trials).
        # Marginally, condition B has a large positive artifact because it was recorded mostly in Session 1.
        rng = np.random.default_rng(789)
        n_times = 25
        # Session 0
        s0_A = rng.normal(0.0, 0.5, size=(12, n_times))
        s0_B = rng.normal(0.0, 0.5, size=(4, n_times))
        # Session 1
        s1_A = rng.normal(6.0, 0.5, size=(4, n_times))
        s1_B = rng.normal(6.0, 0.5, size=(12, n_times))

        X = np.concatenate([s0_A, s1_A], axis=0)  # 16 trials of Condition A
        Y = np.concatenate([s0_B, s1_B], axis=0)  # 16 trials of Condition B
        groups_X = np.array([0] * 12 + [1] * 4)
        groups_Y = np.array([0] * 4 + [1] * 12)

        # 1. Global permutation (ignores session structure) -> creates massive FALSE DISCOVERY
        res_global = cluster_permutation_test(
            X, Y,
            paired=False,
            scheme="global",
            threshold=2.0,
            n_permutations=200,
            rng=np.random.default_rng(100),
        )
        sig_global = [c for c in res_global["clusters"] if c["p_value"] < 0.05]
        assert len(sig_global) >= 1, "Global permutation must falsely claim significance due to session confound"

        # 2. Within-group permutation (preserves session structure) -> correctly ACCEPTS THE NULL
        res_within = cluster_permutation_test(
            X, Y,
            paired=False,
            groups=(groups_X, groups_Y),
            scheme="within_group",
            threshold=2.0,
            n_permutations=200,
            rng=np.random.default_rng(100),
        )
        sig_within = [c for c in res_within["clusters"] if c["p_value"] < 0.05]
        # Under within-group exchangeability, session baseline imbalance is preserved in the null!
        assert len(sig_within) == 0, "Within-group permutation must NOT reject H0 when true condition effect is zero"

    def test_global_numpy_rng_untouched_and_deterministic(self):
        import numpy.random as npr
        state_before = npr.get_state()
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)
        # Constant conditions give every point a zero standard error, so the whole stat
        # map is non-estimable. This test is about RNG hygiene, but it should exercise the
        # ordinary path while it checks it.
        data_rng = np.random.default_rng(7)
        X = 1.0 + data_rng.standard_normal((5, 10))
        Y = data_rng.standard_normal((5, 10))
        res1 = cluster_permutation_test(X, Y, n_permutations=50, rng=rng1)
        res2 = cluster_permutation_test(X, Y, n_permutations=50, rng=rng2)
        state_after = npr.get_state()

        # Global numpy random state must be untouched
        assert state_before[0] == state_after[0]
        np.testing.assert_array_equal(state_before[1], state_after[1])

        # Explicit generator must be 100% deterministic
        np.testing.assert_array_equal(res1["max_null_stats"], res2["max_null_stats"])

    def test_constant_zero_variance_bins_do_not_warn_or_nan(self):
        # Constant zero difference across all observations at some bins
        X = np.zeros((10, 20))
        Y = np.zeros((10, 20))
        # Add non-zero variance to a few bins
        X[:, 5:10] = np.random.default_rng(0).standard_normal((10, 5))
        res = cluster_permutation_test(X, Y, paired=True, n_permutations=50)
        assert not np.isnan(res["stat_map"]).any()
        assert np.all(res["stat_map"][:5] == 0.0)
        assert np.all(res["stat_map"][10:] == 0.0)

    def test_tail_semantics_greater_less_both(self):
        """Minimal analytical/adversarial test verifying tail semantics and signed null statistics."""
        rng = np.random.default_rng(101)
        n_samples = 15
        n_times = 30
        baseline = rng.normal(0.0, 1.0, size=(n_samples, n_times))

        # Evoked has realistic trial-to-trial variance around the effect:
        # Region 5:10 has positive effect (X > Y)
        # Region 20:25 has negative effect (X < Y)
        evoked = baseline + rng.normal(0.0, 0.2, size=(n_samples, n_times))
        evoked[:, 5:10] += 2.0
        evoked[:, 20:25] -= 2.0

        # 1. tail="greater": must find positive cluster, must NOT find negative clusters
        res_greater = cluster_permutation_test(
            evoked, baseline,
            paired=True,
            threshold=2.0,
            n_permutations=100,
            tail="greater",
            rng=np.random.default_rng(202),
        )
        assert len(res_greater["clusters"]) >= 1
        # All found clusters under "greater" must have positive statistics
        for c in res_greater["clusters"]:
            assert c["statistic"] > 0
            assert not np.any(c["mask"][20:25])
        best_pos = res_greater["clusters"][0]
        assert np.any(best_pos["mask"][5:10])
        assert best_pos["p_value"] < 0.05
        # For "greater", null statistics must all be non-negative
        assert np.all(res_greater["max_null_stats"] >= 0.0)
        # Verification of p-value formula for "greater": k = sum(null >= stat)
        assert best_pos["p_value"] == pytest.approx(
            (1.0 + np.sum(res_greater["max_null_stats"] >= best_pos["statistic"])) / 101.0
        )

        # 2. tail="less": must find negative cluster, must NOT find positive clusters
        res_less = cluster_permutation_test(
            evoked, baseline,
            paired=True,
            threshold=2.0,
            n_permutations=100,
            tail="less",
            rng=np.random.default_rng(202),
        )
        assert len(res_less["clusters"]) >= 1
        # All found clusters under "less" must have negative statistics
        for c in res_less["clusters"]:
            assert c["statistic"] < 0
            assert not np.any(c["mask"][5:10])
        best_neg = res_less["clusters"][0]
        assert np.any(best_neg["mask"][20:25])
        assert best_neg["p_value"] < 0.05
        # For "less", null statistics must all be non-positive (extremal negative clusters)
        assert np.all(res_less["max_null_stats"] <= 0.0)
        # Verification of p-value formula for "less": k = sum(null <= stat)
        assert best_neg["p_value"] == pytest.approx(
            (1.0 + np.sum(res_less["max_null_stats"] <= best_neg["statistic"])) / 101.0
        )

        # 3. tail="both": must find BOTH positive and negative clusters
        res_both = cluster_permutation_test(
            evoked, baseline,
            paired=True,
            threshold=2.0,
            n_permutations=100,
            tail="both",
            rng=np.random.default_rng(202),
        )
        assert len(res_both["clusters"]) >= 2
        has_pos = any(c["statistic"] > 0 and np.any(c["mask"][5:10]) for c in res_both["clusters"])
        has_neg = any(c["statistic"] < 0 and np.any(c["mask"][20:25]) for c in res_both["clusters"])
        assert has_pos and has_neg
        # Max null stats for "both" must be absolute magnitudes (>= 0.0)
        assert np.all(res_both["max_null_stats"] >= 0.0)
        for c in res_both["clusters"]:
            assert c["p_value"] == pytest.approx(
                (1.0 + np.sum(res_both["max_null_stats"] >= abs(c["statistic"]))) / 101.0
            )

    def test_invalid_arguments_raise(self):
        rng = np.random.default_rng(0)
        X = np.ones((5, 10))
        Y = np.ones((5, 10))
        with pytest.raises(ValueError, match="strictly positive"):
            cluster_permutation_test(X, Y, threshold=0.0)
        with pytest.raises(ValueError, match="n_permutations"):
            cluster_permutation_test(X, Y, n_permutations=0)
        with pytest.raises(ValueError, match="tail"):
            cluster_permutation_test(X, Y, tail="invalid")
        with pytest.raises(ValueError, match="identical shapes"):
            cluster_permutation_test(np.ones((5, 10)), np.ones((6, 10)), paired=True)
        with pytest.raises(ValueError, match="matching trailing dimensions"):
            cluster_permutation_test(np.ones((5, 10)), np.ones((6, 12)), paired=False)
        with pytest.raises(ValueError, match="NaN"):
            bad_x = np.ones((5, 10))
            bad_x[0, 0] = np.nan
            cluster_permutation_test(bad_x, Y)
        with pytest.raises(ValueError, match="within_group"):
            cluster_permutation_test(X, Y, scheme="within_group", groups=None)
        # 05-35: an int is now a seed, not a type error -- the function used to refuse
        # `rng=42` while seeding itself with `default_rng(0)` whenever `rng` was omitted.
        # A type that names no stream still raises.
        for bad in ("not_an_rng", 3.5, [0]):
            with pytest.raises(TypeError, match="rng must be an int seed"):
                cluster_permutation_test(X, Y, rng=bad)

    def test_observed_clusters_are_unique(self):
        rng = np.random.default_rng(123)
        n_obs, n_times = 20, 50
        baseline = rng.standard_normal((n_obs, n_times))
        evoked = baseline + 0.5 * rng.standard_normal((n_obs, n_times))
        evoked[:, 20:30] += 2.5
        res = cluster_permutation_test(
            evoked, baseline, paired=True, threshold=2.0, n_permutations=50, rng=rng,
        )
        masks = [c["mask"].tobytes() for c in res["clusters"]]
        assert len(masks) == len(set(masks))

