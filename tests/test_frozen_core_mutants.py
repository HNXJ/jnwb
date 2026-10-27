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
from jnwb.laminar import label_layers
from jnwb.spectral import harmonic_analysis
from jnwb.statistics import cluster_permutation_test


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
