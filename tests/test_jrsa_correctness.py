import numpy as np
import pytest
import warnings
import jnwb as oa

def test_jrsa_nan_omission_paired():
    """Verify that nan_policy='omit' performs joint listwise exclusion of NaNs."""
    x = np.array([1.0, 2.0, np.nan, 4.0, 5.0])
    y = np.array([10.0, np.nan, 30.0, 40.0, 50.0])
    
    # Hand-computed pearson correlation between valid pairs (1, 10), (4, 40), (5, 50) is exactly 1.0
    res = oa.jrsa(x, y, metric="pearson", nan_policy="omit", stats=False, return_input=True)
    
    # Assert correlation value is exactly 1.0 (or very close)
    assert np.isclose(res.value, 1.0)
    
    # Independently verify that the NaN-omitted inputs used for calculation match the hand-computed valid elements
    assert np.allclose(res.aligned_x1, np.array([1.0, 4.0, 5.0]))
    assert np.allclose(res.aligned_x2, np.array([10.0, 40.0, 50.0]))


def test_jrsa_preprocessing_conflict_warning():
    """Verify that simultaneous normalize=True and standardize=True raises a warning."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    
    with pytest.warns(UserWarning, match="Both normalize=True and standardize=True are enabled simultaneously"):
        oa.jrsa(x, y, metric="pearson", normalize=True, standardize=True, stats=False)


def test_jrsa_multilag_stacking():
    """Verify that passing multiple lags returns a stacked tensor of shape (n_lags, ...)."""
    rng = np.random.default_rng(42)
    x = rng.normal(0, 1, 100)
    y = rng.normal(0, 1, 100)
    
    # A single lag should work as normal (scalar similarity output)
    res_single = oa.jrsa(x, y, lag=2, stats=False)
    assert res_single.value is not None
    assert res_single.value.ndim == 0
    
    # Multi-lag should stack and compute metric over stacked dimensions
    # resulting in a 1D array of shape (3,) corresponding to the 3 lags
    res_multi = oa.jrsa(x, y, lag=[-2, 0, 3], stats=False)
    assert res_multi.value is not None
    assert res_multi.value.shape == (3,)

class TestHsicInputShapes:
    """_hsic flattened only x1, so every input that was not 2-D failed on x2 inside cdist."""

    @staticmethod
    def _hsic(u, v):
        from jnwb.jrsa import _hsic

        out = _hsic(u, v)
        return float(out[0] if isinstance(out, tuple) else out)

    def test_three_dimensional_inputs_are_flattened_per_sample(self):
        rng = np.random.default_rng(0)
        a = rng.normal(size=(20, 5, 6))
        b = rng.normal(size=(20, 5, 6))
        assert self._hsic(a, b) == pytest.approx(
            self._hsic(a.reshape(20, -1), b.reshape(20, -1))
        )

    def test_one_dimensional_inputs_are_accepted(self):
        rng = np.random.default_rng(1)
        a = rng.normal(size=20)
        assert np.isfinite(self._hsic(a, a + 0.1 * rng.normal(size=20)))

    def test_mixed_dimensionality_matches_the_flattened_pair(self):
        rng = np.random.default_rng(2)
        a = rng.normal(size=(20, 30))
        b = rng.normal(size=(20, 5, 6))
        assert self._hsic(a, b) == pytest.approx(self._hsic(a, b.reshape(20, -1)))
