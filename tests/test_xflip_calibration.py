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

    def test_acceptance_requires_the_surrogate_test_to_pass(self):
        """The gate these tests are named for, asserted rather than assumed.

        Removing the significance decision entirely -- `is_sig` unconditionally true
        whenever surrogates ran -- leaves `test_white_noise_fpr_controlled`,
        `test_periodic_common_response_fpr_controlled`,
        `test_smooth_spatial_gradient_rejected` and all nine tests in
        `TestXFlipGradientGateOnBothPaths` passing, because the contrast and
        boundary-drop gates reject those nulls on their own. Only the AR-noise case
        above notices, and only as a rate.

        Correlated noise is where the distinction is visible: the other gates open and
        the surrogate test is the sole reason for rejection on 14 of 25 seeds, with
        omnibus p running to 0.56. Acceptance must therefore imply significance.
        """
        alpha = 0.05
        sole_surrogate = 0
        for s in range(25):
            ar = synth_ar_noise(600, n_channels=16, fs=1000.0, tau_s=0.030, rng=s + 700)
            res = xflip(
                ar,
                n_blocks=2,
                min_block_size=3,
                n_surrogates=40,
                surrogate_method="autocorr_preserving",
                rng=s + 600,
                alpha=alpha,
            )
            p = float(res.p_values["omnibus"])
            if res.accepted:
                assert p <= alpha, (
                    f"seed {s} accepted with omnibus p = {p:.4f} > alpha = {alpha}; "
                    "acceptance is not gated on the surrogate significance test"
                )
                continue
            reasons = [
                r.strip() for r in (res.rejection_reason or "").split(";") if r.strip()
            ]
            if len(reasons) == 1 and reasons[0].startswith("Non-significant modularity"):
                sole_surrogate += 1
        assert sole_surrogate >= 8, (
            f"only {sole_surrogate} of 25 seeds were rejected by the surrogate test "
            "alone; without them this test cannot tell that gate from the ones beside it"
        )

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


def _smooth_gradient_null(seed, n_ch=16, n_t=400):
    """Exponentially decaying spatial correlation: no boundary anywhere."""
    rng = np.random.default_rng(seed + 1100)
    dists = np.abs(np.arange(n_ch)[:, None] - np.arange(n_ch)[None, :])
    return np.linalg.cholesky(np.exp(-dists / 4.0)) @ rng.normal(size=(n_ch, n_t))


class TestXFlipGradientGateOnBothPaths:
    """05-07: `has_drop` was initialised True and the drop test ran only under
    `contiguous`, so the unrestricted path *skipped* the gate rather than failing it.
    Same data, same rngs: contiguous=True accepted 0/15, contiguous=False accepted 15/15."""

    @pytest.mark.parametrize("contiguous", [True, False])
    def test_smooth_spatial_gradient_rejected_on_both_paths(self, contiguous):
        n_seeds = 15
        accepted = sum(
            bool(
                xflip(
                    _smooth_gradient_null(s),
                    contiguous=contiguous,
                    n_blocks=2,
                    min_block_size=3,
                    n_surrogates=40,
                    rng=s + 1200,
                ).accepted
            )
            for s in range(n_seeds)
        )
        assert accepted / n_seeds <= 0.05

    @pytest.mark.parametrize("contiguous", [True, False])
    def test_the_gradient_is_rejected_by_the_drop_gate_not_by_accident(self, contiguous):
        res = xflip(
            _smooth_gradient_null(0),
            contiguous=contiguous,
            n_blocks=2,
            min_block_size=3,
            n_surrogates=40,
            rng=1200,
        )
        assert not res.accepted
        assert "min_boundary_drop" in (res.rejection_reason or "")

    @pytest.mark.parametrize("contiguous", [True, False])
    @pytest.mark.parametrize("within_corr", [0.6, 0.4])
    def test_true_block_structure_is_still_detected_on_both_paths(self, contiguous, within_corr):
        """The gate must reject gradients without costing the estimator its sensitivity."""
        accepted = 0
        for seed in range(10):
            data, _, _ = synth_correlation_blocks(
                block_sizes=(8, 8),
                within_corr=within_corr,
                between_corr=0.05,
                n_samples=500,
                rng=2000 + seed,
            )
            accepted += bool(
                xflip(
                    data,
                    contiguous=contiguous,
                    n_blocks=2,
                    min_block_size=3,
                    n_surrogates=200,
                    rng=seed,
                ).accepted
            )
        assert accepted == 10

    def test_an_interleaved_partition_is_not_subject_to_the_gradient_gate(self):
        """A spatial gradient cannot produce an interleaved partition, so the local-drop
        statistic does not apply there -- and the cluster-level alternative cannot stand in
        for it: within-minus-between is 0.3285 on the gradient null, far above the 0.05 bar."""
        inter = np.array([
            [1.0, 0.1, 0.8, 0.1, 0.8, 0.1],
            [0.1, 1.0, 0.1, 0.8, 0.1, 0.8],
            [0.8, 0.1, 1.0, 0.1, 0.8, 0.1],
            [0.1, 0.8, 0.1, 1.0, 0.1, 0.8],
            [0.8, 0.1, 0.8, 0.1, 1.0, 0.1],
            [0.1, 0.8, 0.1, 0.8, 0.1, 1.0],
        ])
        res = xflip(
            inter,
            contiguous=False,
            n_blocks=2,
            min_block_size=2,
            n_surrogates=200,
            rng=0,
            is_corr_matrix=True,
        )
        assert res.accepted
        assert list(res.labels) == [0, 1, 0, 1, 0, 1]


class TestXFlipValidatesItsThresholds:
    """05-08: `is_sig = p <= alpha` is vacuously true for alpha >= 1. alpha=5.0 with
    min_boundary_drop=0.0 accepted the gradient null in 15 of 15 seeds, while `zflip`
    range-checks the identical parameter."""

    @pytest.mark.parametrize(
        "kwargs, match",
        [
            ({"alpha": 5.0}, "alpha must lie in"),
            ({"alpha": 1.0}, "alpha must lie in"),
            ({"alpha": 0.0}, "alpha must lie in"),
            ({"alpha": float("nan")}, "alpha must lie in"),
            ({"min_contrast": -1.0}, "min_contrast"),
            ({"min_contrast": float("inf")}, "min_contrast"),
            ({"min_boundary_drop": -0.5}, "min_boundary_drop"),
            ({"min_boundary_drop": float("nan")}, "min_boundary_drop"),
            ({"min_block_size": 0}, "min_block_size"),
        ],
    )
    def test_invalid_thresholds_raise(self, kwargs, match):
        data = np.random.default_rng(0).normal(size=(16, 400))
        with pytest.raises(ValueError, match=match):
            xflip(data, n_surrogates=5, **kwargs)

    def test_valid_thresholds_still_run(self):
        data = np.random.default_rng(0).normal(size=(16, 400))
        res = xflip(data, n_surrogates=20, alpha=0.01, min_contrast=0.1, rng=1)
        assert res.accepted in (True, False)
