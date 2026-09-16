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
        with pytest.warns(RuntimeWarning, match="computes in NumPy"):
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
