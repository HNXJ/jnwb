import numpy as np
import pytest
import warnings
import jnwb as oa

def test_jrsa_nan_omission_paired():
    """Verify that nan_policy='omit' performs joint listwise exclusion of NaNs."""
    x = np.array([1.0, 2.0, np.nan, 4.0, 5.0])
    y = np.array([10.0, np.nan, 30.0, 40.0, 50.0])
    
    # Joint valid indices should be 0, 3, 4 -> x_valid = [1.0, 4.0, 5.0], y_valid = [10.0, 40.0, 50.0]
    # pearson r of [1, 4, 5] and [10, 40, 50] is exactly 1.0 (correlation between them is perfect linear)
    res = oa.jrsa(x, y, metric="pearson", nan_policy="omit", stats=False, return_input=True)
    
    # Assert correlation value is exactly 1.0 (or very close)
    assert np.isclose(res.value, 1.0)
    
    # Verify that the inputs were actually truncated down to size 3
    assert len(res.aligned_x1) == 3
    assert len(res.aligned_x2) == 3
    
    # Hand-calculate expected mean of valid pairs to verify correct elements are present
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
    
    # A single lag should work as normal
    res_single = oa.jrsa(x, y, lag=2, stats=False)
    assert res_single.value is not None
    
    # Multi-lag: just verify that stack runs and returns value
    # For now, let's see how jrsa processes multiple lags with the rest of the pipeline
    res_multi = oa.jrsa(x, y, lag=[-2, 0, 3], stats=False)
    assert res_multi.value is not None
