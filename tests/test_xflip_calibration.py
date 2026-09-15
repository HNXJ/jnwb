"""Calibration tests for jnwb.laminar xFLIP operating characteristics (0.2.3-03)."""
from __future__ import annotations

import numpy as np
import pytest

import jnwb
from jnwb.laminar import xflip
from jnwb.testing import (
    synth_ar_noise,
    synth_correlation_blocks,
    synth_periodic_response,
    synth_white_noise,
)


class TestXFlipNullCalibration:
    """Verify false-positive rate control across null ensembles."""

    def test_white_noise_fpr_controlled(self):
        n_seeds = 15
        accepted = 0
        for s in range(n_seeds):
            white = synth_white_noise(shape=(16, 400), rng=s + 500)
            res = xflip(white, n_blocks=2, min_block_size=3, n_surrogates=40, rng=s + 600)
            if res.accepted:
                accepted += 1
        fpr = accepted / n_seeds
        assert fpr <= 0.05

    def test_ar_noise_fpr_controlled(self):
        n_seeds = 15
        accepted = 0
        for s in range(n_seeds):
            ar = synth_ar_noise(600, n_channels=16, fs=1000.0, tau_s=0.030, rng=s + 700)
            res = xflip(
                ar,
                n_blocks=2,
                min_block_size=3,
                n_surrogates=40,
                surrogate_method="autocorr_preserving",
                rng=s + 800,
            )
            if res.accepted:
                accepted += 1
        fpr = accepted / n_seeds
        assert fpr <= 0.07  # Poisson / binomial sampling bound for n=15 at alpha=0.05

    def test_periodic_common_response_fpr_controlled(self):
        n_seeds = 15
        accepted = 0
        for s in range(n_seeds):
            ch_data = synth_periodic_response(
                n_trials=1,
                n_samples=400,
                fs=1000.0,
                freq_hz=25.0,
                n_channels=16,
                noise_std=0.5,
                rng=s + 900,
            )[0]
            res = xflip(ch_data, n_blocks=2, min_block_size=3, n_surrogates=40, rng=s + 1000)
            if res.accepted:
                accepted += 1
        fpr = accepted / n_seeds
        assert fpr <= 0.05

    def test_smooth_spatial_gradient_rejected(self):
        n_seeds = 15
        accepted = 0
        n_ch = 16
        for s in range(n_seeds):
            rng = np.random.default_rng(s + 1100)
            dists = np.abs(np.arange(n_ch)[:, None] - np.arange(n_ch)[None, :])
            corr_mat = np.exp(-dists / 4.0)
            L = np.linalg.cholesky(corr_mat)
            z = rng.normal(size=(n_ch, 400))
            data = L @ z
            res = xflip(data, n_blocks=2, min_block_size=3, n_surrogates=40, rng=s + 1200)
            if res.accepted:
                accepted += 1
        fpr = accepted / n_seeds
        assert fpr <= 0.05


class TestXFlipAlternativeRecovery:
    """Verify true positive detection and exact boundary localization."""

    def test_equal_blocks_exact_recovery(self):
        data, true_labels, _ = synth_correlation_blocks(
            block_sizes=(8, 8),
            within_corr=0.6,
            between_corr=0.05,
            n_samples=500,
            rng=2000,
        )
        res = xflip(data, n_blocks=2, min_block_size=3, n_surrogates=40, rng=2001)
        assert res.accepted is True
        assert res.boundaries == (8,)
        assert res.block_bounds == ((0, 8), (8, 16))
        assert np.array_equal(res.labels, true_labels)
        assert res.modularity > 0.4

    def test_unequal_blocks_recovery(self):
        # (4, 12)
        data, _, _ = synth_correlation_blocks(
            block_sizes=(4, 12),
            within_corr=0.7,
            between_corr=0.1,
            n_samples=500,
            rng=2100,
        )
        res = xflip(data, n_blocks=2, min_block_size=3, n_surrogates=40, rng=2101)
        assert res.accepted is True
        assert res.boundaries == (4,)

        # (6, 18)
        data2, _, _ = synth_correlation_blocks(
            block_sizes=(6, 18),
            within_corr=0.7,
            between_corr=0.1,
            n_samples=500,
            rng=2200,
        )
        res2 = xflip(data2, n_blocks=2, min_block_size=3, n_surrogates=40, rng=2201)
        assert res2.accepted is True
        assert res2.boundaries == (6,)

    def test_three_blocks_recovery(self):
        data, true_labels, _ = synth_correlation_blocks(
            block_sizes=(6, 6, 6),
            within_corr=0.75,
            between_corr=0.05,
            n_samples=600,
            rng=2300,
        )
        res = xflip(data, n_blocks=3, min_block_size=3, n_surrogates=40, rng=2301)
        assert res.accepted is True
        assert res.boundaries == (6, 12)
        assert res.block_bounds == ((0, 6), (6, 12), (12, 18))
        assert np.array_equal(res.labels, true_labels)

    @pytest.mark.parametrize("n_channels", [8, 16, 32, 64])
    def test_channel_count_scaling(self, n_channels):
        half = n_channels // 2
        data, _, _ = synth_correlation_blocks(
            block_sizes=(half, half),
            within_corr=0.7,
            between_corr=0.1,
            n_samples=500,
            rng=2400 + n_channels,
        )
        res = xflip(data, n_blocks=2, min_block_size=3 if n_channels >= 8 else 2, n_surrogates=30, rng=2500)
        assert res.accepted is True
        assert res.boundaries == (half,)
        assert res.modularity > 0.4
