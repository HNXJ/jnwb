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

    def test_directed_network_is_invariant_to_n_jobs(self):
        """P-113: this asserted the invariance of a constant.

        It left ``n_surrogates`` at its default of 0, so ``p_matrix`` was analytic F-test
        output with no randomness drawn at all -- measured, ``rng=7`` and ``rng=99`` returned
        identical matrices. An ``n_jobs`` invariance assertion over that cannot fail whatever
        the parallel path does, because there are no per-worker random streams to get wrong,
        which is the only thing ``n_jobs`` could plausibly change here.

        Surrogates are now requested, so the quantity under test carries drawn randomness.
        The seed-sensitivity leg below is not decoration: it is what stops this test silently
        reverting to asserting a constant if a future default, or a change in how surrogate
        kwargs are threaded, makes the draws inert again. Without it the repair would swap one
        vacuous assertion for another.
        """
        from jnwb.connectivity import directed_network

        gen = np.random.default_rng(4)
        sig = gen.normal(size=(4, 6, 400))
        sig[1, :, 3:] += 0.6 * sig[0, :, :-3]

        def run(n_jobs, seed=7):
            out = directed_network(
                sig, method="granger", n_jobs=n_jobs, n_surrogates=32, rng=seed
            )
            return out["matrix"], out["p_matrix"]

        m1, p1 = run(1)
        m4, p4 = run(4)
        np.testing.assert_array_equal(m4, m1)
        np.testing.assert_array_equal(p4, p1)

        # The randomness is load-bearing: a different seed must move `p_matrix`. `matrix` is
        # the Granger statistic and stays deterministic, so only the surrogate-derived half
        # can carry this, and comparing the wrong half would restore the original defect.
        _, p_other = run(1, seed=99)
        assert not np.array_equal(p1, p_other, equal_nan=True), (
            "p_matrix did not move when the seed changed, so no randomness is being drawn "
            "and the n_jobs assertions above cannot fail -- the exact defect P-113 recorded"
        )

    def test_defaults_are_serial(self):
        """A library that saturates every core by default fights the caller's own pool."""
        import inspect

        from jnwb.connectivity import directed_network
        from jnwb.spectral import cross_area_coherence
        from jnwb.statistics import cluster_permutation_test

        for fn in (cluster_permutation_test, cross_area_coherence, directed_network):
            default = inspect.signature(fn).parameters["n_jobs"].default
            assert default == 1, f"{fn.__name__} defaults to n_jobs={default}"


class TestTheDefaultIsSerialEverywhere:
    """`jrsa` defaulted to `n_jobs=-1`, the only public function in the package
    that did, and it made an unqualified call slower rather than faster.

    The first parallel call in a process costs about 4.5 s. Only 0.77 s of that is
    joblib starting 24 workers; the rest is each worker running `import jnwb` -- 1.79 s
    in a fresh interpreter -- before it can unpickle the callable. Every parallel call
    site in this library passes such a callable, so no small input can repay it. A
    40x6 input with the default 1000 permutations took 0.47 s serial and 4.87 s on all
    cores, measured one call per interpreter.

    A benchmark that calls twice in one process hides this: the second call reuses the
    pool and costs 0.04 s. That is why the ratio has to be measured cold.
    """

    @staticmethod
    def _public_n_jobs_defaults():
        import inspect

        import jnwb

        found = {}
        for name in jnwb.__all__:
            obj = getattr(jnwb, name, None)
            if not callable(obj):
                continue
            try:
                sig = inspect.signature(obj)
            except (TypeError, ValueError):
                continue
            param = sig.parameters.get("n_jobs")
            if param is not None and param.default is not inspect.Parameter.empty:
                found[name] = param.default
        return found

    def test_every_public_n_jobs_default_is_serial(self):
        """Discovered from `jnwb.__all__` rather than listed, so a new function that
        reintroduces `-1` fails here instead of being found by a user."""
        defaults = self._public_n_jobs_defaults()

        assert defaults, "no public function exposes n_jobs; the scan found nothing"
        offenders = {name: default for name, default in defaults.items()
                     if resolve_n_jobs(default) != 1}
        assert not offenders, f"public defaults that start a pool: {offenders}"

    def test_the_scan_actually_reaches_jrsa(self):
        """Without this, the test above passes if the scan silently finds nothing
        interesting -- `jrsa` is the function 05-46 was about."""
        assert "jrsa" in self._public_n_jobs_defaults()

    def test_a_default_call_does_not_start_a_process_pool(self, monkeypatch):
        """The discriminator. `parallel_map` imports joblib only when it has decided to
        parallelise, so a `Parallel` that refuses to be constructed is enough."""
        import joblib

        class _Refuses:
            def __init__(self, *args, **kwargs):
                raise AssertionError(f"a process pool was started: {args}, {kwargs}")

        monkeypatch.setattr(joblib, "Parallel", _Refuses)

        from jnwb import jrsa

        rng = np.random.default_rng(0)
        res = jrsa(rng.standard_normal((20, 4)), rng.standard_normal((20, 4)),
                   metric="cka", permutations=20, rng=np.random.default_rng(0))

        assert np.isfinite(np.asarray(res.statistic)).all()

    def test_a_bootstrap_without_workers_does_not_start_one_either(self, monkeypatch):
        """`bootstrap` defaults to 0, so the default call above never reaches the
        bootstrap's own `parallel_map`. Asking for a confidence interval is not asking
        for workers."""
        import joblib

        class _Refuses:
            def __init__(self, *args, **kwargs):
                raise AssertionError(f"a process pool was started: {args}, {kwargs}")

        monkeypatch.setattr(joblib, "Parallel", _Refuses)

        from jnwb import jrsa

        rng = np.random.default_rng(0)
        res = jrsa(rng.standard_normal((20, 4)), rng.standard_normal((20, 4)),
                   metric="cka", permutations=0, bootstrap=20,
                   rng=np.random.default_rng(0))

        assert np.isfinite(np.asarray(res.statistic)).all()

    def test_asking_for_workers_still_parallelises(self, monkeypatch):
        """The guard against fixing the default by breaking the knob."""
        import joblib

        built = []
        original = joblib.Parallel

        class _Recording(original):
            def __init__(self, *args, **kwargs):
                built.append(kwargs.get("n_jobs"))
                super().__init__(*args, **kwargs)

        monkeypatch.setattr(joblib, "Parallel", _Recording)

        out = parallel_map(_square, list(range(50)), n_jobs=2)

        assert out == [_square(i) for i in range(50)]
        assert built == [2], f"expected one pool for two workers, got {built}"

    def test_jrsa_gives_the_same_numbers_with_and_without_workers(self):
        """`n_jobs` is a speed knob and never changes a number. This is the invariant that lets the
        default change at all, and it was not covered anywhere before."""
        from jnwb import jrsa

        rng = np.random.default_rng(0)
        x1, x2 = rng.standard_normal((30, 5)), rng.standard_normal((30, 5))

        serial = jrsa(x1, x2, metric="cka", permutations=100, n_jobs=1,
                      rng=np.random.default_rng(7))
        workers = jrsa(x1, x2, metric="cka", permutations=100, n_jobs=2,
                       rng=np.random.default_rng(7))

        assert np.array_equal(np.asarray(serial.statistic),
                              np.asarray(workers.statistic))
        assert np.array_equal(np.asarray(serial.p), np.asarray(workers.p))
