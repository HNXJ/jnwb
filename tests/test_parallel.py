"""Tests for jnwb._parallel: n_jobs is a speed knob that never changes a number."""
from __future__ import annotations

import os

import numpy as np
import pytest

from jnwb._parallel import parallel_map, resolve_n_jobs, spawn_seeds


def _square(x):
    return x * x


class TestResolveNJobs:
    def test_none_and_one_are_serial(self):
        assert resolve_n_jobs(None) == 1
        assert resolve_n_jobs(1) == 1

    def test_negative_one_is_all_cpus(self):
        assert resolve_n_jobs(-1) == (os.cpu_count() or 1)

    def test_negative_two_leaves_one_core(self):
        assert resolve_n_jobs(-2) == max(1, (os.cpu_count() or 1) - 1)

    def test_zero_rejected(self):
        with pytest.raises(ValueError, match="n_jobs=0"):
            resolve_n_jobs(0)

    def test_absurd_negative_clamps_to_serial(self):
        assert resolve_n_jobs(-10_000) == 1


class TestParallelMap:
    def test_serial_and_parallel_agree_and_preserve_order(self):
        items = list(range(50))
        expected = [_square(i) for i in items]
        assert parallel_map(_square, items, n_jobs=1) == expected
        assert parallel_map(_square, items, n_jobs=4) == expected

    def test_empty_and_single_item(self):
        assert parallel_map(_square, [], n_jobs=4) == []
        assert parallel_map(_square, [7], n_jobs=4) == [49]

    def test_chunking_covers_every_item_exactly_once(self):
        """Chunk boundaries must not drop or duplicate work."""
        for n in (1, 2, 3, 7, 8, 9, 33, 100):
            items = list(range(n))
            assert parallel_map(_square, items, n_jobs=8) == [i * i for i in items]

    def test_more_workers_than_items(self):
        assert parallel_map(_square, [1, 2], n_jobs=32) == [1, 4]


class TestSpawnSeeds:
    def test_returns_requested_count(self):
        assert len(spawn_seeds(np.random.default_rng(0), 5)) == 5

    def test_same_parent_seed_gives_same_children(self):
        a = spawn_seeds(np.random.default_rng(3), 4)
        b = spawn_seeds(np.random.default_rng(3), 4)
        assert [s.entropy for s in a] == [s.entropy for s in b]
        assert [s.spawn_key for s in a] == [s.spawn_key for s in b]

    def test_different_parent_seeds_give_different_children(self):
        a = spawn_seeds(np.random.default_rng(3), 4)
        b = spawn_seeds(np.random.default_rng(4), 4)
        assert [s.entropy for s in a] != [s.entropy for s in b]

    def test_children_are_independent_of_each_other(self):
        seeds = spawn_seeds(np.random.default_rng(0), 6)
        draws = [np.random.default_rng(s).integers(0, 2**31, size=4).tolist() for s in seeds]
        assert len({tuple(d) for d in draws}) == len(draws)


class TestNJobsDoesNotChangeResults:
    """The contract that makes n_jobs safe to expose at all."""

    def test_cluster_permutation_test_is_invariant_to_n_jobs(self):
        from jnwb.statistics import cluster_permutation_test

        gen = np.random.default_rng(3)
        X = gen.normal(size=(30, 40))
        Y = gen.normal(size=(30, 40))
        Y[:, 10:18] += 1.0

        def run(n_jobs):
            out = cluster_permutation_test(
                X, Y, n_permutations=64, rng=np.random.default_rng(11), n_jobs=n_jobs
            )
            return [c["p_value"] for c in out["clusters"]]

        serial = run(1)
        assert serial, "need at least one cluster for this to test anything"
        assert run(4) == serial

    def test_cross_area_coherence_is_invariant_to_n_jobs(self):
        from jnwb.spectral import cross_area_coherence

        gen = np.random.default_rng(7)
        base = gen.normal(size=4096)
        x = base + 0.3 * gen.normal(size=4096)
        y = base + 0.3 * gen.normal(size=4096)

        def run(n_jobs):
            return cross_area_coherence(
                x, y, fs=1000.0, n_surrogates=32, n_jobs=n_jobs, freq_bands="canonical"
            )["band_significance"]

        assert run(4) == run(1)

    def test_defaults_are_serial(self):
        """A library that saturates every core by default fights the caller's own pool."""
        import inspect

        from jnwb.spectral import cross_area_coherence
        from jnwb.statistics import cluster_permutation_test

        for fn in (cluster_permutation_test, cross_area_coherence):
            default = inspect.signature(fn).parameters["n_jobs"].default
            assert default == 1, f"{fn.__name__} defaults to n_jobs={default}"
