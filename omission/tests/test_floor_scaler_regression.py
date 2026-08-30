"""Permanent regression test for the _FloorScaler numerical failure class (2026-08-28).

Found during reverse-direction benchmarking: fit_translated_template_oracle's Ridge pipeline
originally used a bare sklearn.preprocessing.StandardScaler, which only guards against exactly-
zero-variance columns. A near-zero (but nonzero, e.g. ~5e-9) train-fold std escaped that guard;
dividing by it amplified ordinary train/test floating-point-level differences into held-out
predictions of order 1e6-1e8 -- a numerical artifact reported as if it were a real result.

Independent verification (independent-verification-pc2-reverse-20260828.json) reproduced the
exact failure mechanism directly: a block of trials with a distinct, much smaller noise floor
isolated entirely into one KFold(shuffle=False) fold's test set, leaving that fold's train-std at
~1e-14 for the affected column. Unpatched, max prediction reached 1.46e7; patched (_FloorScaler,
floor=1e-4), it stayed at 18.3. This test pins that exact reproduction as a permanent regression
guard.
"""
import numpy as np
from sklearn.model_selection import KFold

from omission.jnwb_ext.distributed_lag_model import _held_out_predict, StandardScaler


def test_near_zero_variance_column_does_not_blow_up_held_out_predictions():
    """Construct a feature matrix with one column whose train-fold variance is near machine
    epsilon in a KFold split, isolated exactly as in the historical failure: a block of trials
    with a distinct near-zero noise floor placed entirely in one fold. Require finite, bounded
    held-out predictions -- not merely 'no crash'."""
    rng = np.random.default_rng(0)
    n = 300
    n_features = 5

    X = rng.normal(0, 1, size=(n, n_features))
    # column 0: near-constant EXCEPT for a tiny amount of real signal -- mimics an analytic
    # oracle-template column whose true support barely reaches a given window.
    X[:, 0] = 5.0 + rng.normal(0, 1e-10, size=n)
    y = X[:, 1] * 2.0 + X[:, 2] * -1.5 + rng.normal(0, 0.1, size=n)

    # isolate an even-smaller-noise-floor block into what will become a single KFold(shuffle=False)
    # fold's test set, reproducing the exact independently-verified failure geometry.
    X[0:60, 0] = 5.0 + rng.normal(0, 1e-14, size=60)

    y_pred = _held_out_predict(X, y, n_splits=5, alpha=1.0, seed=0)

    assert np.all(np.isfinite(y_pred)), "held-out predictions contain non-finite values"
    assert np.abs(y_pred).max() < 100, (
        f"held-out predictions blew up (max abs = {np.abs(y_pred).max():.3e}); the near-zero-"
        f"variance column was not adequately floored"
    )


def test_floor_scaler_is_a_noop_on_well_conditioned_columns():
    """The fix must not change behavior on ordinary, well-conditioned features -- pins the
    no-op property that was confirmed by re-running the already-CONFIRMED PC1 oracle rerun
    bit-identically before/after the fix (see chat receipt), at a smaller scale here as a fast
    permanent check."""
    from omission.jnwb_ext.distributed_lag_model import _FloorScaler
    from sklearn.preprocessing import StandardScaler as SklearnStandardScaler

    rng = np.random.default_rng(1)
    X = rng.normal(0, 3.0, size=(200, 4)) + rng.normal(5, 1.0, size=4)

    floor_scaled = _FloorScaler().fit(X).transform(X)
    sklearn_scaled = SklearnStandardScaler().fit(X).transform(X)

    assert np.allclose(floor_scaled, sklearn_scaled, atol=1e-10), (
        "_FloorScaler must reproduce ordinary StandardScaler behavior exactly on well-"
        "conditioned (non-near-zero-variance) columns"
    )
