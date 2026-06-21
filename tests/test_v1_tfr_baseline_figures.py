"""Tests for V1 baseline-relative TFR figure helpers."""

from __future__ import annotations

import numpy as np

from src.analysis.visualization.v1_tfr_baseline_figures import (
    BASELINE_WINDOW_MS,
    TIMES_MS,
    aggregate_trial_stats,
    channel_mean_baseline_db,
    discover_v1_session_pairs,
    load_matched_session_db,
    subsample_trials,
)


def test_discover_v1_session_pairs_nonempty():
    pairs = discover_v1_session_pairs()
    assert len(pairs) >= 1
    for pair in pairs:
        assert pair.n_matched == min(pair.n_aaab, pair.n_axab)
        assert pair.aaab_path.exists()
        assert pair.axab_path.exists()


def test_subsample_trials_equal_count():
    arr = np.arange(20 * 2 * 3 * 4, dtype=np.float32).reshape(20, 2, 3, 4)
    sub = subsample_trials(arr, 7, seed=0)
    assert sub.shape == (7, 2, 3, 4)
    sub2 = subsample_trials(arr, 7, seed=0)
    assert np.array_equal(sub, sub2)


def test_channel_mean_baseline_db_shape_and_finite():
    power = np.random.default_rng(0).random((5, 128, 99, 500), dtype=np.float32) + 1e-6
    db = channel_mean_baseline_db(power)
    assert db.shape == (5, 99, 500)
    assert db.dtype == np.float32
    assert np.all(np.isfinite(db))


def test_load_matched_session_db_equal_trials():
    pairs = discover_v1_session_pairs()
    if not pairs:
        return
    aaab_db, axab_db = load_matched_session_db(pairs[0], seed=0)
    assert aaab_db.shape == axab_db.shape
    assert aaab_db.shape[0] == pairs[0].n_matched
    assert aaab_db.shape[1:] == (99, 500)
    mean, sem = aggregate_trial_stats(aaab_db)
    assert mean.shape == (99, 500)
    assert sem.shape == (99, 500)
    assert TIMES_MS[0] == -1000.0
    assert BASELINE_WINDOW_MS == (-500, 0)
