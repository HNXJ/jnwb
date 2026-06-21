"""Tests for spectrolaminar layer mask helpers."""

from __future__ import annotations

import numpy as np

from src.analysis.lfp.lfp_layer_masks import (
    LAYER_NAMES,
    classify_probe_layers_from_lfp,
    layer_masks_from_crossover,
)


def test_layer_masks_from_crossover_normal_orientation():
    masks = layer_masks_from_crossover(128, crossover_idx=64.0, orientation="normal")
    assert set(masks) == set(LAYER_NAMES)
    assert np.sum(masks["superficial_putative"]) > 0
    assert np.sum(masks["deep_putative"]) > 0
    assert not np.any(masks["superficial_putative"] & masks["deep_putative"])


def test_layer_masks_unresolved_returns_empty():
    masks = layer_masks_from_crossover(128, crossover_idx=np.nan, orientation="unresolved")
    assert not np.any(masks["superficial_putative"])
    assert not np.any(masks["deep_putative"])


def test_classify_probe_layers_from_lfp_runs_on_synthetic():
    rng = np.random.default_rng(0)
    n_ch = 128
    # Superficial channels: more alpha/beta; deep: more gamma via synthetic gradient
    data = rng.standard_normal((4, n_ch, 5000)).astype(np.float32)
    for ch in range(n_ch):
        if ch < 60:
            data[:, ch, :] *= 1.0
        else:
            data[:, ch, 1000:3000] *= 3.0
    meta = classify_probe_layers_from_lfp(
        data,
        session_id="sub-test_ses-000000",
        probe_letter="A",
    )
    assert meta.n_channels == 128
    assert meta.method == "spectrolaminar_alpha_beta_gamma_crossover"
