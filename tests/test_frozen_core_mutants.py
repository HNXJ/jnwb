"""Planted-case tests for frozen core functions that no existing test kills.

Each test builds a case whose answer the function's own body fixes, asserts the case's
precondition before it checks the answer, and therefore fails under a planted change to the
body it names. Tests that already kill a planted change live in their own modules and are
named in the register; these cover the gaps they leave.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import jnwb
import jnwb._backend as backend
import jnwb.spectral._coupling as coupling
from jnwb._rng import surrogate_rng
from jnwb.laminar import label_layers
from jnwb.permutation import permute_labels
from jnwb.spectral import cross_area_coherence, harmonic_analysis
from jnwb.statistics import cluster_permutation_test, shuffle_r2_ci


class TestLayerLabelsFollowTheShaftRank:
    """Labels on a shuffled table, against labels written out by depth, not computed."""

    #: Physical contact k sits at depth k * 100 um; the table lists them in this order.
    TABLE_ORDER = [3, 0, 6, 1, 7, 2, 5, 4]
    #: Crossover at contact 3 and a 200 um input zone on a 100 um pitch: contacts 2 to 4.
    BY_DEPTH = {
        "superficial_to_deep": ["superficial"] * 2 + ["input"] * 3 + ["deep"] * 3,
        "deep_to_superficial": ["deep"] * 2 + ["input"] * 3 + ["superficial"] * 3,
    }

    @pytest.mark.parametrize("orientation", sorted(BY_DEPTH))
    def test_each_contact_gets_the_label_of_its_depth(self, orientation):
        n = len(self.TABLE_ORDER)
        geometry = jnwb.probe_geometry(
            pd.DataFrame({
                "x": np.zeros(n),
                "y": np.zeros(n),
                "z": [100.0 * k for k in self.TABLE_ORDER],
                "channel_id": [f"c{k}" for k in self.TABLE_ORDER],
            }),
            units="um", nominal_pitch=100.0,
        )
        # Precondition: the table is out of depth order, so a wrong rank shows.
        assert not np.array_equal(np.asarray(geometry.linear_order), np.arange(n)), (
            "fixture must list contacts out of depth order")
        result = SimpleNamespace(
            accepted=True, crossover_contact=3.0, n_channels=n, index_space="shaft_rank",
            orientation=orientation, bad_channel_mask=None,
        )

        labels = label_layers(result, geometry, granular_thickness_um=200.0)

        assert labels == {f"c{k}": label for k, label in enumerate(self.BY_DEPTH[orientation])}


class TestHarmonicRatioCountsEveryHigherOrder:
    """harmonic_ratio is the fundamental's share of the fundamental plus every order from 2 up."""

    def test_the_second_harmonic_enters_the_ratio(self):
        fs, f0 = 1000.0, 10.0
        t = np.arange(8000) / fs
        x = np.sin(2 * np.pi * f0 * t) + 0.5 * np.sin(2 * np.pi * 2 * f0 * t)

        result = harmonic_analysis(x, fs=fs)
        harmonics = result["harmonics"]
        # Precondition: the fundamental and a second harmonic with power are both present, so
        # the ratio depends on the second harmonic and a sum that drops it is visible.
        assert 1 in harmonics and 2 in harmonics and harmonics[2]["power"] > 0, (
            "fixture must carry a fundamental and a second harmonic with power")

        fundamental = harmonics[1]["power"]
        higher = sum(h["power"] for order, h in harmonics.items() if order >= 2)
        assert result["harmonic_ratio"] == pytest.approx(
            fundamental / (fundamental + higher), rel=1e-12)


class TestClusterPValueIsTheFloorWhenNoPermutationReachesIt:
    """With no permutation reaching the observed cluster, its p-value is exactly 1 / (B + 1)."""

    def test_an_unreached_cluster_has_the_exact_floor(self):
        rng = np.random.default_rng(11)
        X = rng.normal(0.0, 1.0, size=(12, 6))
        Y = rng.normal(8.0, 1.0, size=(12, 6))
        n_permutations = 20

        result = cluster_permutation_test(X, Y, n_permutations=n_permutations, rng=0)
        assert result["clusters"], "fixture must form a cluster"
        top = result["clusters"][0]
        # Precondition: no permutation reaches the observed cluster, so the exceedance count is 0.
        assert np.max(result["max_null_stats"]) < abs(top["statistic"]), (
            "fixture must not be reached by any permutation")
        assert top["p_value"] == pytest.approx(1.0 / (n_permutations + 1.0), rel=1e-12)


def _shuffle_null(y, score, n_shuffle, seed):
    """The null that shuffle_r2_ci builds from the same seed: one global label shuffle each."""
    rng, _ = surrogate_rng(seed, "shuffle_r2_ci")
    null = np.empty(n_shuffle)
    for i in range(n_shuffle):
        y_perm = permute_labels(y, scheme="global", rng=rng)
        null[i] = np.corrcoef(y_perm, score)[0, 1] ** 2
    return null


class TestShuffleR2CiPercentilesAreTheNullsOwn:
    """The CI bounds are the 2.5th and 97.5th percentiles of the same null the draws build."""

    def test_the_ci_is_the_2_5_and_97_5_percentiles_of_the_null(self):
        rng = np.random.default_rng(5)
        y = (rng.random(60) < 0.5).astype(int)
        score = y + rng.normal(0.0, 1.0, size=60)
        n_shuffle = 200
        # Precondition: both labels occur, and the null spreads so its 95th and 97.5th
        # percentiles differ.
        assert 0 < y.sum() < y.size, "fixture must hold both labels"
        null = _shuffle_null(y, score, n_shuffle, seed=7)
        assert np.percentile(null, 97.5) - np.percentile(null, 95) > 1e-3, (
            "fixture's null must spread above its 95th percentile")

        out = shuffle_r2_ci(y, score, n_shuffle=n_shuffle, rng=7)

        assert out["r2_null_ci_lo"] == pytest.approx(np.percentile(null, 2.5), rel=1e-12)
        assert out["r2_null_ci_hi"] == pytest.approx(np.percentile(null, 97.5), rel=1e-12)


class TestShuffleR2CiPValueIsCountPlusOneOverDrawsPlusOne:
    """With no shuffled label reaching the observed R^2, p is exactly 1 / (B + 1)."""

    def test_the_p_value_is_the_count_plus_one_over_draws_plus_one(self):
        y = np.repeat([0, 1], 10)
        score = y.astype(float)  # a perfect score: observed R^2 is 1
        n_shuffle = 200
        out = shuffle_r2_ci(y, score, n_shuffle=n_shuffle, rng=7)
        null = _shuffle_null(y, score, n_shuffle, seed=7)
        # Precondition: the observed R^2 is 1 and no shuffle reaches it, so the count is 0.
        assert out["r2_observed"] > 0.999, "fixture must observe a perfect R^2"
        k = int(np.sum(null >= out["r2_observed"]))
        assert k == 0, "fixture must have no draw at least as extreme as the observed R^2"

        assert out["p_val"] == pytest.approx((k + 1.0) / (n_shuffle + 1.0), rel=1e-12)


class TestClusterTStatisticIsMeanOverItsStandardError:
    """Each t is the mean difference over its standard error, here (a + b) / |a - b|."""

    #: Two samples per condition at five points. X holds (a, b) per point, Y is zero, so the
    #: t at a point is (a + b) / |a - b|: 2.5 for (3.5, 1.5), 1.0 for (1, 0), 4.0 for (5, 3).
    X = np.array([[3.5, 3.5, 3.5, 1.0, 5.0],
                  [1.5, 1.5, 1.5, 0.0, 3.0]])
    Y = np.zeros((2, 5))
    T_VALUES = [2.5, 2.5, 2.5, 1.0, 4.0]

    @pytest.mark.parametrize("paired", [False, True])
    def test_the_t_statistic_is_the_mean_over_its_standard_error(self, paired):
        result = cluster_permutation_test(self.X, self.Y, paired=paired, n_permutations=1, rng=0)
        # Precondition: the hand-computed t values form two clusters, one of three points and
        # one of one point, separated by a point below the threshold.
        assert len(result["clusters"]) == 2, "fixture must form two clusters"

        np.testing.assert_allclose(result["stat_map"], self.T_VALUES, rtol=1e-12)


class TestClusterMaxNullStatisticIsTheLargestClusterMass:
    """Each draw's null statistic is the largest |cluster sum|, not a peak or a size."""

    def test_the_null_statistic_is_the_largest_cluster_mass(self):
        X = TestClusterTStatisticIsMeanOverItsStandardError.X
        Y = TestClusterTStatisticIsMeanOverItsStandardError.Y
        # One group per X and Y pair: a within-group shuffle swaps the two samples of each
        # group independently, so every draw is one of four relabellings of the observed map.
        groups = (np.array([0, 1]), np.array([0, 1]))

        result = cluster_permutation_test(
            X, Y, groups=groups, scheme="within_group", n_permutations=200, rng=0)

        # Precondition: the observed clusters have masses 7.5 and 4.0, and the draws reach the
        # relabelling that forms them (7.5), as well as the one with no cluster (0.0).
        assert [round(c["statistic"], 9) for c in result["clusters"]] == [7.5, 4.0], (
            "fixture must form clusters of mass 7.5 and 4.0")
        null = np.round(result["max_null_stats"], 9)
        assert 7.5 in null and 0.0 in null, "fixture's draws must reach both relabellings"

        assert set(null) == {0.0, 7.5}


class TestCrossAreaCoherenceUsesTheCpuWithoutAGpu:
    """With no usable GPU, device='cuda' warns, never enters the GPU branch, and equals CPU."""

    def test_no_gpu_means_the_cpu_path_and_its_values(self, monkeypatch):
        monkeypatch.setattr(backend, "gpu_available", lambda prefer=None: False)
        gpu_calls = []

        def _refuse_gpu(*args, **kwargs):
            gpu_calls.append(args)
            raise RuntimeError("the GPU path must not run without a usable GPU")

        monkeypatch.setattr(coupling, "_welch_csd_gpu", _refuse_gpu)
        rng = np.random.default_rng(3)
        x = rng.standard_normal(4096)
        y = 0.5 * x + rng.standard_normal(4096)
        kwargs = dict(fs=1000.0, freq_bands={"alpha": (8.0, 14.0), "beta": (14.0, 30.0)},
                      rng=7, n_surrogates=20)

        with pytest.warns(RuntimeWarning, match="device='cuda' was requested"):
            on_cuda = cross_area_coherence(x, y, device="cuda", **kwargs)
        on_cpu = cross_area_coherence(x, y, device="cpu", **kwargs)

        # Precondition: the CPU run is a finite, non-trivial coherence on the CPU estimator.
        assert on_cpu["device_used"] == "cpu"
        assert np.isfinite(on_cpu["peak_coherence_value"]) and on_cpu["peak_coherence_value"] > 0
        assert gpu_calls == [], "the GPU estimator must not be called without a usable GPU"
        assert on_cuda["device_used"] == "cpu"
        np.testing.assert_allclose(on_cuda["coherence_spectrum"], on_cpu["coherence_spectrum"],
                                   rtol=1e-12)
        assert on_cuda["band_coherence"] == pytest.approx(on_cpu["band_coherence"], rel=1e-12)
        assert on_cuda["band_significance"] == pytest.approx(on_cpu["band_significance"], rel=1e-12)
