"""The degenerate-input outputs that the skill prose states.

Each test builds its input, asserts the precondition it depends on, then pins the output the
skill text names. A test that only checked the sentence's keywords would pass for any output.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import jnwb
from jnwb import compute_psd
from jnwb.laminar._vflip import vflip_from_lfp
from jnwb.unit_quality import refractory_contamination


def _is_nan(value) -> bool:
    return value is not None and bool(np.isnan(value))


def test_unpaired_single_values_give_mann_whitney_u_zero_and_p_one():
    a = np.array([1.0])
    b = np.array([2.0])
    assert len(a) == 1 and len(b) == 1

    res = jnwb.StatisticalAnalysis.exploratory_compare(a, b)

    assert res["n1"] == 1 and res["n2"] == 1
    np.testing.assert_allclose(res["non_parametric"]["statistic"], 0.0, rtol=1e-12)
    np.testing.assert_allclose(res["non_parametric"]["pval"], 1.0, rtol=1e-12)
    assert _is_nan(res["parametric"]["statistic"])
    assert _is_nan(res["parametric"]["pval"])
    assert res["significant_parametric"] is False
    assert res["significant_nonparametric"] is False


def test_identical_constant_groups_give_mann_whitney_statistic_and_nan_p():
    a = np.full(3, 2.0)
    b = np.full(3, 2.0)
    assert len(a) == 3 and np.ptp(a) == 0 and np.ptp(b) == 0

    res = jnwb.StatisticalAnalysis.exploratory_compare(a, b)

    np.testing.assert_allclose(res["non_parametric"]["statistic"], 4.5, rtol=1e-12)
    assert _is_nan(res["non_parametric"]["pval"])
    assert _is_nan(res["parametric"]["statistic"])
    assert _is_nan(res["parametric"]["pval"])
    assert res["significant_parametric"] is False
    assert res["significant_nonparametric"] is False


def test_all_tied_groups_read_nan_p_whatever_scipy_returns(monkeypatch):
    """scipy 1.17 (the declared floor) returns p 1.0 for all-tied groups and 1.18 returns NaN."""
    from scipy import stats

    monkeypatch.setattr(stats, "mannwhitneyu", lambda x, y, **kwargs: (4.5, 1.0))
    a = np.full(3, 2.0)
    assert np.ptp(a) == 0

    res = jnwb.StatisticalAnalysis.exploratory_compare(a, a.copy())

    np.testing.assert_allclose(res["non_parametric"]["statistic"], 4.5, rtol=1e-12)
    assert _is_nan(res["non_parametric"]["pval"])


def test_empty_group_and_all_zero_paired_difference_give_nan_on_both_tests():
    empty = np.array([])
    three = np.array([1.0, 2.0, 3.0])
    assert len(empty) == 0

    res = jnwb.StatisticalAnalysis.exploratory_compare(empty, three)
    assert _is_nan(res["non_parametric"]["statistic"])
    assert _is_nan(res["non_parametric"]["pval"])
    assert _is_nan(res["parametric"]["pval"])

    res = jnwb.StatisticalAnalysis.exploratory_compare(three, three.copy(), paired=True)
    assert np.all(three - three.copy() == 0)
    assert _is_nan(res["non_parametric"]["statistic"])
    assert _is_nan(res["non_parametric"]["pval"])
    assert _is_nan(res["parametric"]["pval"])
    assert res["significant_parametric"] is False
    assert res["significant_nonparametric"] is False


def test_paired_group_of_one_value_raises():
    with pytest.raises(ValueError):
        jnwb.StatisticalAnalysis.exploratory_compare(
            np.array([1.0]), np.array([2.0]), paired=True
        )


def test_zero_duration_with_empty_train_is_nan_with_reason():
    empty = np.array([])
    assert empty.size == 0

    out = refractory_contamination(empty, duration_s=0.0, refractory_ms=2.0, censored_ms=0.0)

    assert _is_nan(out["contamination"])
    assert "no spikes" in out["reason"]


def test_zero_duration_with_spikes_spanning_longer_raises():
    spikes = np.array([0.0, 0.05, 0.1])
    assert spikes.max() - spikes.min() > 0.0

    with pytest.raises(ValueError, match="longer than duration_s"):
        refractory_contamination(spikes, duration_s=0.0, refractory_ms=2.0, censored_ms=0.0)


def test_measured_quality_failure_is_poor_even_when_another_metric_is_undefined():
    units = pd.DataFrame(
        {
            "quality": [0.5, np.nan, 2.0],
            "snr": [2.0, 2.0, 2.0],
            "firing_rate": [np.nan, np.nan, 1.0],
        }
    )
    assert units.loc[0, "quality"] < 1.0 and np.isnan(units.loc[0, "firing_rate"])
    assert np.isnan(units.loc[1, "quality"])

    out = jnwb.classify_unit_quality(units)

    assert list(out["quality_class"]) == ["Poor", "Unknown", "Good"]


def test_nan_input_makes_compute_psd_raise_while_vflip_from_lfp_rejects():
    rng = np.random.default_rng(0)
    lfp = rng.normal(size=(8, 2000))
    lfp[3, 10] = np.nan
    assert np.isnan(lfp).any()

    with pytest.raises(ValueError):
        compute_psd(lfp, 1000.0, axis=-1)

    fit = vflip_from_lfp(lfp, 1000.0)
    assert fit.accepted is False
    assert fit.crossover_contact is None
