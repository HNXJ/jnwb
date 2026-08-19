"""Tests for area × layer × condition TFR band figure helpers."""

from __future__ import annotations

import numpy as np

from src.analysis.lfp.lfp_constants import ALL_CONDITIONS, CANONICAL_AREAS
from src.analysis.lfp.lfp_layer_masks import LAYER_NAMES
from src.analysis.visualization.area_layer_tfr_figures import (
    area_search_tokens,
    compute_band_epoch_stats,
    discover_tfr_sources,
    layer_mean_baseline_db,
)


def test_area_search_tokens_includes_aliases():
    tokens = area_search_tokens("V4")
    assert "V4" in tokens
    assert "DP" in tokens


def test_discover_tfr_sources_v1_aaab():
    sources = discover_tfr_sources("V1", "AAAB")
    assert len(sources) >= 1
    for src in sources:
        assert src.path.exists()
        assert src.n_trials > 0


def test_layer_mean_baseline_db_shape():
    power = np.random.default_rng(0).random((3, 128, 99, 500), dtype=np.float32) + 1e-6
    mask = np.zeros(128, dtype=bool)
    mask[:20] = True
    db = layer_mean_baseline_db(power, mask)
    assert db.shape == (3, 99, 500)
    assert np.all(np.isfinite(db))


def test_compute_band_epoch_stats_has_all_bands():
    trials = np.random.default_rng(1).standard_normal((12, 99, 500)).astype(np.float32)
    rows = compute_band_epoch_stats(trials)
    assert len(rows) == 5 * 6  # 5 epochs × 6 bands
    bands = {r["band"] for r in rows}
    assert len(bands) == 6


def test_requested_grid_size():
    assert len(CANONICAL_AREAS) == 11
    assert len(LAYER_NAMES) == 2
    assert len(ALL_CONDITIONS) == 12
    assert 11 * 2 * 12 == 264
