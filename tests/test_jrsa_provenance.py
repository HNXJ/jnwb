"""05-26 and 05-33: what `jrsa` records about a run must be what the run did.

`parameters` carries the request. `execution` carries what executed. They were the same
dict of echoes: a device name that never ran, a backend that was converted away on the
first line of every metric, a correction that was warned about and then recorded anyway,
and a "seed" that could not reseed anything.

Each test fails when its repair is reverted.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

import jnwb


@pytest.fixture
def xy():
    rng = np.random.default_rng(0)
    return rng.normal(size=(40, 6)), rng.normal(size=(40, 6))


def _cuda_refusal_pattern() -> str:
    """Which refusal `device='cuda'` earns here, and why there are two of them.

    Requesting CUDA is refused on every machine, but by whichever check gets there first.
    Where a usable device exists, `resolve_device` returns `cuda` and `jrsa` itself explains
    that its metrics compute in NumPy. Where none exists -- every CI runner, and any
    developer machine without CuPy -- `resolve_device` refuses earlier and `jrsa`'s branch is
    never reached.

    Matching only the first message asserted a string that a GPU-less machine cannot produce,
    so this test failed on all three CI legs while passing on a workstation with an RTX A4000.
    Each environment is still held to its own message rather than to a weakened alternation.
    """
    from jnwb._backend import CUDA, resolve_device

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        usable = resolve_device("cuda", context="probe", prefer="cupy") == CUDA
    return "computes in NumPy" if usable else "no usable CUDA device was found"


class TestExecutionRecordsWhatRan:
    """05-26. `AGENTS.md` invariant 6: the device never changes a number -- which also
    means the record of the device must not claim one that did not run it.
    """

    def test_an_unknown_device_is_refused_like_everywhere_else(self, xy):
        """It used to run and be recorded verbatim, while all 15 `resolve_device` sites
        raise for the same string.
        """
        x1, x2 = xy
        with pytest.raises(ValueError, match="unrecognised device"):
            jnwb.jrsa(x1, x2, metric="cka", permutations=0, device="bogus_device")

    def test_an_unknown_backend_is_refused(self, xy):
        x1, x2 = xy
        with pytest.raises(ValueError, match="unrecognised backend"):
            jnwb.jrsa(x1, x2, metric="cka", permutations=0, backend="bogus_backend")

    @pytest.mark.parametrize(
        "kwargs", [{}, {"device": "cpu"}, {"device": "auto", "backend": "auto"},
                   {"backend": "numpy"}]
    )
    def test_execution_reports_numpy_on_the_cpu(self, xy, kwargs):
        x1, x2 = xy
        res = jnwb.jrsa(x1, x2, metric="cka", permutations=0, **kwargs)
        assert res.execution["backend"] == "numpy"
        assert res.execution["device"] == "cpu"

    def test_requesting_cuda_says_it_will_not_be_used_and_records_cpu(self, xy):
        """`jrsa(device='cuda', backend='cupy')` recorded
        `{'backend': 'cupy', 'device': 'cuda'}` for arithmetic that ran on the CPU:
        `_prepare_inputs` uploaded to cupy and every metric's first line called
        `_ensure_np` and pulled it straight back.
        """
        x1, x2 = xy
        with pytest.warns(RuntimeWarning, match=_cuda_refusal_pattern()):
            res = jnwb.jrsa(
                x1, x2, metric="cka", permutations=0, device="cuda", backend="cupy"
            )
        assert res.execution["backend"] == "numpy"
        assert res.execution["device"] == "cpu"
        # The request is still on the record -- in `parameters`, where a request belongs.
        assert res.parameters["device"] == "cuda"
        assert res.parameters["backend"] == "cupy"

    def test_the_device_request_does_not_change_the_number(self, xy):
        x1, x2 = xy
        cpu = jnwb.jrsa(x1, x2, metric="cka", permutations=0, device="cpu")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cuda = jnwb.jrsa(x1, x2, metric="cka", permutations=0, device="cuda")
        assert float(cpu.statistic) == float(cuda.statistic)

    def test_an_unknown_correction_is_refused_not_recorded(self, xy):
        """It warned that it had fallen back to 'fdr_bh' and then recorded
        `parameters['correction'] == 'bonferoni'`, so the run was corrected one way and
        documented another.
        """
        x1, x2 = xy
        with pytest.raises(ValueError, match="[Uu]nrecognized correction"):
            jnwb.jrsa(x1, x2, metric="cka", permutations=20, correction="bonferoni")

    @pytest.mark.parametrize("correction", ["fdr_bh", "bonferroni", "holm", "none"])
    def test_known_corrections_still_run_and_are_recorded(self, xy, correction):
        x1, x2 = xy
        res = jnwb.jrsa(
            x1, x2, metric="cka", permutations=20, correction=correction, random_state=0
        )
        assert res.parameters["correction"] == correction

    @pytest.mark.parametrize("kernel", ["rbf", "nonsense_kernel", "poly"])
    def test_cka_refuses_a_kernel_it_does_not_implement(self, xy, kernel):
        """`linear`, `rbf` and `nonsense_kernel` all returned the same number: the closed
        form below is the linear identity, not a Gram matrix a kernel plugs into.
        """
        x1, x2 = xy
        with pytest.raises(NotImplementedError, match="linear kernel only"):
            jnwb.jrsa(x1, x2, metric="cka", permutations=0, kernel=kernel)

    def test_cka_linear_is_unchanged(self, xy):
        x1, x2 = xy
        assert float(
            jnwb.jrsa(x1, x2, metric="cka", permutations=0, kernel="linear").statistic
        ) == float(jnwb.jrsa(x1, x2, metric="cka", permutations=0).statistic)


class TestSeedRoundTrips:
    """05-33. `execution['seed']` was `rng.bit_generator.state['state']['state']` -- the
    128-bit internal counter. A faithful record of the generator's position, and useless
    for reproduction: feeding it back as `random_state` seeds a different stream.
    """

    def test_the_recorded_seed_is_the_random_state_that_was_used(self, xy):
        x1, x2 = xy
        res = jnwb.jrsa(x1, x2, metric="cka", permutations=50, random_state=7)
        assert res.execution["seed"] == 7

    def test_feeding_the_recorded_seed_back_reproduces_the_run(self, xy):
        x1, x2 = xy
        first = jnwb.jrsa(x1, x2, metric="cka", permutations=50, random_state=7)
        again = jnwb.jrsa(
            x1, x2, metric="cka", permutations=50, random_state=first.execution["seed"]
        )
        np.testing.assert_array_equal(np.asarray(first.p), np.asarray(again.p))
        np.testing.assert_array_equal(
            np.asarray(first.statistic), np.asarray(again.statistic)
        )

    def test_the_seed_alias_round_trips_too(self, xy):
        x1, x2 = xy
        res = jnwb.jrsa(x1, x2, metric="cka", permutations=20, seed=3)
        assert res.execution["seed"] == 3

    def test_an_unseeded_run_records_no_seed(self, xy):
        """None is the honest record for a run seeded from OS entropy. A 128-bit counter
        there looks exactly like a reproducible run and is not one.
        """
        x1, x2 = xy
        assert jnwb.jrsa(x1, x2, metric="cka", permutations=20).execution["seed"] is None


class TestBatchSizeIsRecordedAsWhatRan:
    """05-50. `batch_size` was accepted, documented as "Chunk size for large arrays",
    and copied into `parameters` -- and nothing chunked. The only chunking helper in the
    module had no callers, so a result could carry `batch_size=32` in its provenance for
    a run that made one pass. Same defect as the device and backend echoes above, and
    the same rule fixes it: `execution` says what happened.
    """

    def test_execution_reports_no_batching_however_much_was_asked_for(self, xy):
        x1, x2 = xy
        for asked in (None, 1, 4, 32, 10_000):
            res = jnwb.jrsa(x1, x2, metric="cka", permutations=20,
                            batch_size=asked, random_state=7)
            assert res.execution["batch_size"] is None, (
                f"execution claims batching for batch_size={asked!r}; jrsa does not chunk"
            )

    def test_the_request_is_still_kept_where_requests_go(self, xy):
        x1, x2 = xy
        res = jnwb.jrsa(x1, x2, metric="cka", permutations=20,
                        batch_size=32, random_state=7)
        assert res.parameters["batch_size"] == 32

    def test_asking_for_a_batch_size_changes_no_number(self, xy):
        """If this ever fails, something started chunking and `execution` must stop
        saying None -- the test is the pair to the one above, not a duplicate of it.
        """
        x1, x2 = xy
        base = jnwb.jrsa(x1, x2, metric="cka", permutations=50, bootstrap=50,
                         random_state=7)
        for asked in (1, 4, 32, 10_000):
            other = jnwb.jrsa(x1, x2, metric="cka", permutations=50, bootstrap=50,
                              batch_size=asked, random_state=7)
            np.testing.assert_array_equal(np.asarray(base.value), np.asarray(other.value))
            np.testing.assert_array_equal(np.asarray(base.p), np.asarray(other.p))
            np.testing.assert_array_equal(np.asarray(base.ci), np.asarray(other.ci))

    def test_the_helper_that_promised_chunking_is_gone(self):
        import importlib

        mod = importlib.import_module("jnwb.jrsa")
        assert not hasattr(mod, "_chunk_tensor"), (
            "the chunking helper is back; either wire it to batch_size or drop it, but "
            "do not leave it where it reads as an implementation"
        )

    def test_alpha_does_not_move_the_interval_it_does_not_set(self, xy):
        """The CI is a fixed 95% percentile bootstrap. That is now documented; this
        pins it, so a change to the level has to be deliberate.
        """
        x1, x2 = xy
        widths = set()
        for a in (0.5, 0.05, 0.01):
            res = jnwb.jrsa(x1, x2, metric="cka", permutations=20, bootstrap=100,
                            alpha=a, random_state=7)
            ci = np.asarray(res.ci).ravel()
            widths.add((float(ci[0]), float(ci[1])))
        assert len(widths) == 1, f"alpha changed the interval: {widths}"
