"""A caller-fixed Granger order is an integer >= 1, or the call raises.

`int(order)` alone let `order=0` fit a model with no history and return zero causality in both
directions -- a plausible "no coupling" -- truncated `2.5` to `2`, and read `True` as `1`.
"""
import numpy as np
import pytest

import jnwb

RNG = np.random.default_rng(0)
# Drawn and discarded: the trial arrays below keep the draws they were pinned with.
RNG.normal(size=400)
RNG.normal(size=400)
XT = RNG.normal(size=(4, 200))
YT = np.roll(XT, 2, axis=1) + 0.5 * RNG.normal(size=(4, 200))

BAD_ORDERS = [0, -1, 2.5, True, float("nan"), "aic"]


CALLS = {
    "granger": lambda order: jnwb.granger(XT, YT, order=order, n_surrogates=0),
    "granger_spectral": lambda order: jnwb.granger_spectral(XT, YT, fs=100.0, order=order),
}


@pytest.mark.parametrize("name", sorted(CALLS))
@pytest.mark.parametrize("order", BAD_ORDERS, ids=repr)
def test_an_invalid_order_raises(name, order):
    with pytest.raises(ValueError, match="order must be 'auto' or an integer >= 1"):
        CALLS[name](order)


@pytest.mark.parametrize("name", sorted(CALLS))
def test_an_integral_order_is_accepted_in_every_spelling(name):
    results = [CALLS[name](order) for order in (3, np.int64(3), 3.0)]
    assert all(r is not None for r in results)


def test_order_zero_no_longer_reads_as_no_coupling():
    fitted = CALLS["granger"](2)
    assert fitted.x_to_y > 0.1


class TestGrangerAutoOrder:
    def test_auto_order_matches_select_optimal_lag(self):
        from jnwb.connectivity import select_optimal_lag

        rng = np.random.default_rng(1)
        x = rng.normal(size=400)
        y = rng.normal(size=400)
        lag_xy = select_optimal_lag(x, y, max_lag=8, criterion="bic")
        res = jnwb.granger(
            x, y, order="auto", max_lag=8, criterion="bic", n_surrogates=0, detrend=None
        )
        assert res.params["order_x_to_y"] == lag_xy


class TestFinalAuditRecurrence:

    def test_granger_accepts_minimal_dof_order(self):
        rng = np.random.default_rng(1)
        x = rng.normal(size=20)
        y = rng.normal(size=20)
        res = jnwb.granger(x[None, :], y[None, :], order=6, n_surrogates=0, detrend=None)
        assert res.params["order_x_to_y"] == 6
