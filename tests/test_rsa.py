"""Unit tests for standalone RDM and RSA primitives (jnwb.rsa).

Verifies:
1. rdm computation:
   - Output shapes (condensed 1D vector vs full 2D square matrix).
   - Invariants: diagonal == 0, symmetry (M == M.T).
   - Equivalence between condensed and squareform(M).
   - Multi-metric support: correlation, cosine, euclidean, cityblock.
   - Non-finite rejection and empty/1-condition checks.
2. rdm_similarity comparison:
   - Evaluates Spearman, Pearson, Kendall, and Cosine similarities.
   - Equivalence between comparing two condensed RDMs and two 2D square RDMs.
   - Returns valid correlation and p-value.
   - Self-similarity is 1.0.
   - Shape mismatch and non-finite rejection.
3. jrsa delegation parity:
   - Confirms that calling jrsa(x1, x2, metric='rsa') matches direct rdm + rdm_similarity.
"""

import numpy as np
import pytest
from scipy.spatial.distance import squareform

import jnwb


def test_rdm_shapes_and_invariants():
    """Verify condensed vs full matrix shapes, diagonal, and symmetry."""
    rng = np.random.default_rng(42)
    n_cond, n_feat = 10, 25
    X = rng.normal(size=(n_cond, n_feat))

    # Condensed
    v = jnwb.rdm(X, metric="correlation", condensed=True)
    expected_len = n_cond * (n_cond - 1) // 2
    assert v.shape == (expected_len,)
    assert v.dtype == np.float64

    # Full square
    M = jnwb.rdm(X, metric="correlation", condensed=False)
    assert M.shape == (n_cond, n_cond)
    assert np.allclose(np.diag(M), 0.0)
    assert np.allclose(M, M.T)
    assert np.allclose(squareform(M), v)


def test_rdm_metrics():
    """Verify various standard metrics produce expected values."""
    rng = np.random.default_rng(42)
    X = rng.normal(size=(8, 16))

    for m in ["correlation", "cosine", "euclidean", "cityblock"]:
        v = jnwb.rdm(X, metric=m, condensed=True)
        assert len(v) == 28
        assert np.all(np.isfinite(v))
        assert np.all(v >= 0.0)


def test_rdm_input_validation():
    """Verify exception handling for 1D, 1-condition, and non-finite inputs."""
    with pytest.raises(ValueError, match="at least a 2D array"):
        jnwb.rdm(np.array([1.0, 2.0, 3.0]))

    with pytest.raises(ValueError, match="at least 2 conditions"):
        jnwb.rdm(np.ones((1, 10)))

    with pytest.raises(ValueError, match="non-finite values"):
        X_nan = np.zeros((4, 5))
        X_nan[0, 0] = np.nan
        jnwb.rdm(X_nan)


def test_rdm_similarity_comparison():
    """Verify similarity computation across metrics and full/condensed representations."""
    rng = np.random.default_rng(42)
    X1 = rng.normal(size=(12, 20))
    X2 = X1 + 0.2 * rng.normal(size=(12, 20))  # closely related representation

    rdm1_cond = jnwb.rdm(X1, metric="correlation", condensed=True)
    rdm2_cond = jnwb.rdm(X2, metric="correlation", condensed=True)
    rdm1_full = squareform(rdm1_cond)
    rdm2_full = squareform(rdm2_cond)

    # Self similarity is 1.0
    rho_self, p_self = jnwb.rdm_similarity(rdm1_cond, rdm1_cond, metric="spearman")
    assert np.isclose(rho_self, 1.0)
    assert np.isclose(p_self, 0.0)

    # Condensed vs 2D full equivalence
    rho_cond, p_cond = jnwb.rdm_similarity(rdm1_cond, rdm2_cond, metric="spearman")
    rho_full, p_full = jnwb.rdm_similarity(rdm1_full, rdm2_full, metric="spearman")
    assert np.isclose(rho_cond, rho_full)
    assert np.isclose(p_cond, p_full)
    assert rho_cond > 0.70  # high second-order similarity

    # Pearson & Kendall
    r, p_r = jnwb.rdm_similarity(rdm1_cond, rdm2_cond, metric="pearson")
    tau, p_tau = jnwb.rdm_similarity(rdm1_cond, rdm2_cond, metric="kendall")
    assert 0.0 <= r <= 1.0
    assert 0.0 <= tau <= 1.0

    # Cosine
    cos_sim, cos_p = jnwb.rdm_similarity(rdm1_cond, rdm2_cond, metric="cosine")
    assert 0.0 <= cos_sim <= 1.0
    assert np.isnan(cos_p)


def test_rdm_similarity_validation():
    """Verify error checking on mismatched lengths or non-finite entries."""
    v1 = np.zeros(10)
    v2 = np.zeros(15)
    with pytest.raises(ValueError, match="length mismatch"):
        jnwb.rdm_similarity(v1, v2)

    with pytest.raises(ValueError, match="must be square if 2D"):
        jnwb.rdm_similarity(np.zeros((3, 4)), np.zeros((3, 4)))

    with pytest.raises(ValueError, match="non-finite values"):
        v_nan = np.zeros(10)
        v_nan[0] = np.nan
        jnwb.rdm_similarity(v_nan, np.zeros(10))

    with pytest.raises(ValueError, match="Unknown similarity metric"):
        jnwb.rdm_similarity(np.ones(10), np.ones(10), metric="unsupported")


def test_jrsa_delegation_parity():
    """Verify jrsa delegation reproduces identical results to direct rdm primitives."""
    rng = np.random.default_rng(42)
    # (n_trials, n_features)
    x1 = rng.normal(size=(30, 15))
    x2 = x1 + 0.3 * rng.normal(size=(30, 15))

    # jrsa with metric='rsa'
    res_jrsa = jnwb.jrsa(x1, x2, metric="rsa")

    # Direct rdm computation
    v1 = jnwb.rdm(x1, metric="correlation", condensed=True)
    v2 = jnwb.rdm(x2, metric="correlation", condensed=True)
    rho, p = jnwb.rdm_similarity(v1, v2, metric="spearman")

    assert np.isclose(res_jrsa.value, rho)
    assert np.isclose(res_jrsa.p, p)
