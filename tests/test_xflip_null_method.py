"""XFlipResult.null_method: the surrogate null that produced `p_values`."""
from __future__ import annotations

import numpy as np
import pytest

from jnwb.laminar import xflip
from jnwb.testing import synth_correlation_blocks


def _raw():
    data, _, _ = synth_correlation_blocks([4, 4], n_samples=300, rng=0)
    return data


def _matrix():
    return np.array([
        [1.0, 0.6, 0.1, 0.1],
        [0.6, 1.0, 0.1, 0.1],
        [0.1, 0.1, 1.0, 0.7],
        [0.1, 0.1, 0.7, 1.0],
    ])


def test_auto_raw_data_resolves_homogeneous():
    res = xflip(_raw(), n_surrogates=10, rng=11)
    assert res.null_method == "homogeneous"


def test_auto_matrix_with_n_samples_resolves_homogeneous():
    res = xflip(_matrix(), is_corr_matrix=True, n_samples=300, n_surrogates=10, rng=11)
    assert res.null_method == "homogeneous"


def test_auto_matrix_without_n_samples_falls_back_to_permute_channels():
    with pytest.warns(UserWarning, match="n_samples"):
        res = xflip(_matrix(), is_corr_matrix=True, n_surrogates=10, rng=42)
    assert res.null_method == "permute_channels"


@pytest.mark.parametrize(
    "method", ["homogeneous", "autocorr_preserving", "permute_channels"]
)
def test_explicit_method_records_itself(method):
    res = xflip(_raw(), n_surrogates=10, surrogate_method=method, rng=11)
    assert res.null_method == method


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [("phase_randomize", "autocorr_preserving"), ("channel_permute", "permute_channels")],
)
def test_alias_records_canonical_name(alias, canonical):
    res = xflip(_raw(), n_surrogates=10, surrogate_method=alias, rng=11)
    assert res.null_method == canonical


def test_n_surrogates_zero_records_none():
    res = xflip(_raw(), n_surrogates=0, rng=11)
    assert res.null_method is None


def test_zero_variance_refusal_records_none():
    raw = _raw()
    raw[0, :] = 1.0
    res = xflip(raw, n_surrogates=10, rng=11)
    assert res.accepted is False
    assert "Zero-variance" in (res.rejection_reason or "")
    assert res.null_method is None


def test_structural_refusal_records_none():
    res = xflip(_raw()[:4], n_blocks=3, n_surrogates=10, rng=11)
    assert res.accepted is False
    assert "insufficient" in (res.rejection_reason or "")
    assert res.null_method is None


def test_to_dict_carries_null_method():
    res = xflip(_raw(), n_surrogates=10, rng=11)
    assert res.to_dict()["null_method"] == "homogeneous"
    res_none = xflip(_raw(), n_surrogates=0, rng=11)
    assert res_none.to_dict()["null_method"] is None


def test_p_values_match_baseline():
    raw = _raw()
    res = xflip(raw, n_surrogates=10, rng=11)
    np.testing.assert_allclose(res.p_values["omnibus"], 1 / 11, rtol=1e-12)
    np.testing.assert_allclose(res.p_values["boundary_4"], 1 / 11, rtol=1e-12)
    res_perm = xflip(raw, n_surrogates=10, surrogate_method="permute_channels", rng=11)
    np.testing.assert_allclose(res_perm.p_values["omnibus"], 1 / 11, rtol=1e-12)
    np.testing.assert_allclose(res_perm.p_values["boundary_4"], 1 / 11, rtol=1e-12)
    res_mat = xflip(_matrix(), is_corr_matrix=True, n_samples=300, n_surrogates=10, rng=11)
    np.testing.assert_allclose(res_mat.p_values["omnibus"], 1 / 11, rtol=1e-12)
    np.testing.assert_allclose(res_mat.p_values["boundary_2"], 1 / 11, rtol=1e-12)
