"""`jrsa(sliding=True)`: one value per window, a raw p per window and a family-wise q.

The windows share one label shuffle per permutation. Each window's raw p is the p of a single-window
call with the same rng, and the family-wise q is taken against the maximum over windows (the minimum
for ``alternative='less'``).
"""

import numpy as np
import pytest

import jnwb


def _pair(seed, shape):
    rng = np.random.default_rng(seed)
    return rng.normal(size=shape), rng.normal(size=shape)


def test_disjoint_windows_match_single_window_calls_for_pearson():
    x1, x2 = _pair(1, (4, 60))
    width = 15
    res = jnwb.jrsa(x1, x2, metric="pearson", window=width, step=width, sliding=True,
                    null="iid", permutations=99, rng=7)
    starts = list(range(0, 60 - width + 1, width))
    assert len(starts) == 4, "fixture must give four disjoint windows"
    assert res.execution["windows"] == [(s, s + width) for s in starts]
    for k, s in enumerate(starts):
        single = jnwb.jrsa(x1, x2, metric="pearson", window=(s, s + width), null="iid",
                           permutations=99, rng=7)
        np.testing.assert_allclose(res.value[k], single.value, rtol=1e-12)
        assert float(res.p[k]) == float(single.p), (s, res.p[k], single.p)


def test_disjoint_windows_match_single_window_calls_for_cka():
    x1, x2 = _pair(2, (60, 5))
    width = 12
    res = jnwb.jrsa(x1, x2, metric="cka", window=width, step=width, sliding=True,
                    null="iid", permutations=99, rng=8)
    starts = list(range(0, 60 - width + 1, width))
    assert len(starts) == 5, "fixture must give five disjoint windows"
    assert res.execution["windows"] == [(s, s + width) for s in starts]
    for k, s in enumerate(starts):
        single = jnwb.jrsa(x1, x2, metric="cka", window=(s, s + width), null="iid",
                           permutations=99, rng=8)
        np.testing.assert_allclose(res.value[k], single.value, rtol=1e-12)
        assert float(res.p[k]) == float(single.p), (s, res.p[k], single.p)


def _by_counting(null, obs):
    """Raw and family-wise p for each tail, counted directly; no library helper is used."""
    n = null.shape[0]
    upper, lower = null.max(axis=1), null.min(axis=1)
    raw_g = np.array([(1 + np.count_nonzero(null[:, j] >= obs[j])) / (n + 1)
                      for j in range(obs.size)])
    raw_l = np.array([(1 + np.count_nonzero(null[:, j] <= obs[j])) / (n + 1)
                      for j in range(obs.size)])
    fw_g = np.array([(1 + np.count_nonzero(upper >= o)) / (n + 1) for o in obs])
    fw_l = np.array([(1 + np.count_nonzero(lower <= o)) / (n + 1) for o in obs])
    return {"greater": (raw_g, fw_g),
            "less": (raw_l, fw_l),
            "two-sided": (np.minimum(1.0, 2 * np.minimum(raw_g, raw_l)),
                          np.minimum(1.0, 2 * np.minimum(fw_g, fw_l)))}


@pytest.mark.parametrize("alternative", ["greater", "less", "two-sided"])
def test_family_wise_p_is_taken_against_the_maximum_over_windows(alternative):
    x1, x2 = _pair(3, (4, 60))
    res = jnwb.jrsa(x1, x2, metric="pearson", window=15, step=15, sliding=True, null="iid",
                    permutations=199, rng=9, alternative=alternative, return_null=True)
    null = np.asarray(res.null_distribution)
    obs = np.asarray(res.value, dtype=float)
    assert null.shape[0] == 199, null.shape
    assert null.shape[1] == obs.size == 4, (null.shape, obs.shape)
    raw, fw = _by_counting(null, obs)[alternative]
    np.testing.assert_allclose(res.p, raw, rtol=1e-12)
    np.testing.assert_allclose(res.q, fw, rtol=1e-12)
    assert np.all(res.q >= res.p), (res.p, res.q)
    assert res.execution["correction"] == "max_statistic"
    assert res.parameters["correction"] == "max_statistic"


def test_family_wise_q_over_white_noise_pairs_is_calibrated_and_raw_p_is_not():
    """100 seeds of independent white-noise pairs, 8 windows, 199 permutations, pearson, iid.

    The family-wise q flags at most 10% of seeds (its nominal rate is 5%), and any raw p flags
    more seeds than q does.
    """
    width, n_windows, n_seeds = 20, 8, 100
    seeds_q = seeds_p = 0
    for seed in range(n_seeds):
        rng = np.random.default_rng(1000 + seed)
        x1 = rng.normal(size=(4, width * n_windows))
        x2 = rng.normal(size=(4, width * n_windows))
        res = jnwb.jrsa(x1, x2, metric="pearson", window=width, step=width, sliding=True,
                        null="iid", permutations=199, rng=seed)
        assert res.p.shape == (n_windows,), "fixture must give eight windows"
        seeds_q += bool(np.any(res.q <= 0.05))
        seeds_p += bool(np.any(res.p <= 0.05))
    print(f"seeds with any q <= 0.05: {seeds_q}/{n_seeds}; any raw p <= 0.05: {seeds_p}/{n_seeds}")
    assert seeds_q / n_seeds <= 0.10, seeds_q
    assert seeds_p > seeds_q, (seeds_p, seeds_q)


@pytest.mark.parametrize("override, message", [
    ({"window": (10, 30)}, r"sliding=True needs window to be an int"),
    ({"window": None}, r"sliding=True needs window to be an int"),
    ({"window": 0}, r"sliding=True needs window to be an int"),
    ({"window": 61}, r"window=61 is longer than the 60-sample"),
    ({"step": None}, r"sliding=True needs step to be an int"),
    ({"step": 0}, r"sliding=True needs step to be an int"),
    ({"lag": [0, 1]}, r"sliding=True takes one lag or none"),
    ({"bootstrap": 10}, r"sliding=True does not take bootstrap"),
    ({"correction": "fdr_bh"}, r"sliding=True takes correction='max_statistic'"),
    ({"permutations": 0}, r"sliding=True needs a permutation null"),
    ({"stats": False}, r"sliding=True needs a permutation null"),
])
def test_each_sliding_refusal_names_its_argument(override, message):
    x1, x2 = _pair(6, (4, 60))
    base = dict(metric="pearson", window=15, step=15, sliding=True, null="iid",
                permutations=99, rng=1)
    with pytest.raises(ValueError, match=message):
        jnwb.jrsa(x1, x2, **{**base, **override})


def test_step_without_sliding_and_max_statistic_without_sliding_are_refused():
    x1, x2 = _pair(6, (4, 60))
    with pytest.raises(ValueError, match=r"step=5 applies only to sliding=True"):
        jnwb.jrsa(x1, x2, metric="pearson", step=5, null="iid", permutations=99, rng=1)
    with pytest.raises(ValueError, match=r"correction='max_statistic' needs sliding=True"):
        jnwb.jrsa(x1, x2, metric="pearson", correction="max_statistic", null="iid",
                  permutations=99, rng=1)


def test_windows_must_cut_the_permuted_axis():
    """With adim=-1 on cka the windows cut the 20 features, but the null permutes the 60
    observations on axis 0. One index of the window length cannot serve both."""
    x1, x2 = _pair(5, (60, 20))
    with pytest.raises(ValueError, match=r"adim=-1.*sliding=True cuts windows on axis 1"):
        jnwb.jrsa(x1, x2, metric="cka", adim=-1, window=5, step=5, sliding=True,
                  null="iid", permutations=99, rng=1)


def test_a_default_call_keeps_its_value_p_and_q():
    """Pinned on the unmodified code before the sliding path existed: sliding=False is unchanged."""
    x1 = np.random.default_rng(11).normal(size=(6, 40))
    x2 = 0.5 * x1 + np.random.default_rng(12).normal(size=(6, 40))
    res = jnwb.jrsa(x1, x2, metric="pearson", rng=3)
    assert res.execution["null"] == "circular_shift"
    assert res.parameters["correction"] == "fdr_bh"
    np.testing.assert_allclose(float(res.value), 0.5296818739944763, rtol=1e-12)
    np.testing.assert_allclose(float(res.p), 0.053946053946053944, rtol=1e-12)
    np.testing.assert_allclose(float(res.q), 0.053946053946053944, rtol=1e-12)


def test_a_single_lag_is_applied_inside_each_window():
    x1, x2 = _pair(7, (4, 60))
    res = jnwb.jrsa(x1, x2, metric="pearson", window=15, step=15, sliding=True, null="iid",
                    permutations=99, rng=4, lag=2)
    assert res.value.shape == (4,), res.value.shape
    assert res.execution["n_overlap"] == 13
    for k, s in enumerate([0, 15, 30, 45]):
        single = jnwb.jrsa(x1, x2, metric="pearson", window=(s, s + 15), null="iid",
                           permutations=99, rng=4, lag=2)
        assert single.execution["n_overlap"] == 13
        np.testing.assert_allclose(res.value[k], single.value, rtol=1e-12)
        assert float(res.p[k]) == float(single.p), (s, res.p[k], single.p)


def test_a_window_with_a_non_finite_value_has_nan_p_and_q_and_the_others_stay_finite():
    rng = np.random.default_rng(4)
    x1 = rng.normal(size=(60, 5))
    x2 = rng.normal(size=(60, 5))
    x1[12:24] = 1.0  # window 1 holds one repeated row, so its CKA is 0 over 0
    res = jnwb.jrsa(x1, x2, metric="cka", window=12, step=12, sliding=True, null="iid",
                    permutations=99, rng=2)
    assert not np.isfinite(res.value[1]), "precondition: window 1 has a non-finite value"
    assert np.isnan(res.p[1]) and np.isnan(res.q[1])
    others = [0, 2, 3, 4]
    assert np.all(np.isfinite(res.p[others])) and np.all(np.isfinite(res.q[others]))
