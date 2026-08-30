"""P2 regression tests (2026-08-29): a mismatched seed between estimate_timing_nested and
fit_nuisance_tier must FAIL LOUDLY, not silently void the cross-fitting guarantee.

Independent verification (2026-08-28) raised this as a CONCERN: the cross-fit guarantee depends
on both functions receiving the same n_splits/seed, all 5 call sites were correct, but nothing
enforced it -- a mismatched seed would produce a non-cross-fit result with no error and no
visible symptom. estimate_timing_nested now tags its output with a fingerprint of the CV
partition it used, and fit_nuisance_tier rejects a pairing whose partition differs.
"""
import numpy as np
import pytest

from omission.jnwb_ext.distributed_lag_model import (
    build_trial_level_dataset, estimate_timing_nested, fit_nuisance_tier, folds_fingerprint,
)
from omission.jnwb_ext.realized_coupling_generator import synthesize_realized_coupling_pair

N_TRIALS = 120
TIER = "Zhat-2_plus_timing_gain"


def _data(seed: int = 0):
    P, R, true_jitter, true_gain, _ = synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, jitter_sd_ms=8.0, amp_gain=0.0, rho=0.5, beta=0.0,
        z_seed=seed, private_seed=seed + 111,
    )
    return P, R, build_trial_level_dataset(P, R, seed=seed)


def test_matching_seeds_are_accepted():
    P, R, dataset = _data()
    timing_hat = estimate_timing_nested(P, n_splits=5, seed=0)
    fit = fit_nuisance_tier(dataset, TIER, timing_hat=timing_hat, n_splits=5, seed=0)
    assert np.isfinite(fit["delta"])


def test_mismatched_seed_raises_instead_of_silently_voiding_cross_fitting():
    P, R, dataset = _data()
    timing_hat = estimate_timing_nested(P, n_splits=5, seed=0)
    with pytest.raises(ValueError, match="different CV partition"):
        fit_nuisance_tier(dataset, TIER, timing_hat=timing_hat, n_splits=5, seed=1)


def test_mismatched_n_splits_raises():
    P, R, dataset = _data()
    timing_hat = estimate_timing_nested(P, n_splits=5, seed=0)
    with pytest.raises(ValueError, match="different CV partition"):
        fit_nuisance_tier(dataset, TIER, timing_hat=timing_hat, n_splits=10, seed=0)


def test_untagged_plain_ndarray_is_still_accepted_for_backward_compatibility():
    """The enforcement is additive: a caller supplying a plain ndarray (no fingerprint) is not
    blocked, since nothing can be verified about it either way."""
    P, R, dataset = _data()
    timing_hat = np.asarray(estimate_timing_nested(P, n_splits=5, seed=0)).copy()
    assert getattr(timing_hat, "folds_fingerprint", None) is None
    fit = fit_nuisance_tier(dataset, TIER, timing_hat=timing_hat, n_splits=5, seed=1)
    assert np.isfinite(fit["delta"])


def test_timing_estimate_behaves_as_a_plain_ndarray():
    """The ndarray subclass must not perturb any existing numeric use."""
    P, _, _ = _data()
    timing_hat = estimate_timing_nested(P, n_splits=5, seed=0)
    plain = np.asarray(timing_hat)
    assert isinstance(timing_hat, np.ndarray)
    assert timing_hat.shape == (N_TRIALS,)
    assert np.allclose(timing_hat + 1.0, plain + 1.0)
    assert np.allclose(timing_hat.reshape(-1, 1).ravel(), plain)
    assert float(timing_hat.mean()) == pytest.approx(float(plain.mean()))


def test_fingerprint_is_deterministic_and_discriminating():
    a = folds_fingerprint(100, 5, 0)
    b = folds_fingerprint(100, 5, 0)
    c = folds_fingerprint(100, 5, 1)
    d = folds_fingerprint(100, 10, 0)
    e = folds_fingerprint(101, 5, 0)
    assert a == b
    assert len({a, c, d, e}) == 4, "fingerprint must distinguish seed, n_splits and n_samples"
