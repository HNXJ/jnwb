"""Tests for jnwb.laminar: Cross-Channel Laminar Correlation Profile (xFLIP).

The sections after the class-based body are marked by comments. The homogeneous-null section is
slow, roughly three minutes: test_false_positive_rate_on_boundary_free_probes runs 200 probes and
takes about 160 s of it. The suite has no slow marker, so the note stands in for one.
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
import time
import warnings

import numpy as np
import pytest

import jnwb
from jnwb.laminar import XFlipResult, xflip
from jnwb.testing import synth_ar_noise, synth_correlation_blocks, synth_white_noise

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))  # needed: the installed-wheel run clears pythonpath
from scripts import calibrate_xflip as receipt  # noqa: E402
from scripts import xflip_nuisance as nuisance  # noqa: E402


class TestXFlipInputs:
    """Test shape handling, input validation, and fail-loud error paths in xflip."""

    def test_raw_time_series_default_axis(self):
        rng = np.random.default_rng(42)
        raw = rng.normal(size=(8, 200))
        res = xflip(raw, n_surrogates=10, rng=42)
        assert isinstance(res, XFlipResult)
        assert res.n_channels == 8
        assert res.corr_matrix.shape == (8, 8)
        assert res.method == "pearson"

    def test_raw_time_series_transposed_axis(self):
        rng = np.random.default_rng(42)
        raw_t = rng.normal(size=(200, 8))
        res = xflip(raw_t, channel_axis=1, n_surrogates=10, rng=42)
        assert res.n_channels == 8
        assert res.corr_matrix.shape == (8, 8)

    def test_precomputed_correlation_matrix(self):
        corr = np.array([
            [1.0, 0.6, 0.1, 0.1],
            [0.6, 1.0, 0.1, 0.1],
            [0.1, 0.1, 1.0, 0.7],
            [0.1, 0.1, 0.7, 1.0],
        ])
        res = xflip(corr, is_corr_matrix=True, n_surrogates=20, rng=42)
        assert isinstance(res, XFlipResult)
        assert res.n_channels == 4
        assert res.method == "precomputed"
        assert res.block_bounds == ((0, 2), (2, 4))
        assert res.boundaries == (2,)

    def test_auto_detect_precomputed_correlation_matrix(self):
        corr = np.array([
            [1.0, 0.5, 0.0, 0.0],
            [0.5, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.5],
            [0.0, 0.0, 0.5, 1.0],
        ])
        res = xflip(corr, n_surrogates=10, rng=42)
        assert res.method == "precomputed"
        assert res.n_channels == 4

    def test_invalid_dimensions_fail(self):
        with pytest.raises(ValueError, match="2D array"):
            xflip(np.ones(10))
        with pytest.raises(ValueError, match="2D array"):
            xflip(np.ones((4, 4, 4)))

    def test_non_finite_inputs_fail(self):
        data = np.ones((8, 100))
        data[0, 5] = np.nan
        with pytest.raises(ValueError, match="non-finite"):
            xflip(data)

        data[0, 5] = np.inf
        with pytest.raises(ValueError, match="non-finite"):
            xflip(data)

    def test_non_square_precomputed_fails(self):
        with pytest.raises(ValueError, match="square"):
            xflip(np.ones((4, 6)), is_corr_matrix=True)

    def test_asymmetric_precomputed_fails(self):
        corr = np.eye(4)
        corr[0, 1] = 0.5
        corr[1, 0] = 0.2
        with pytest.raises(ValueError, match="symmetric"):
            xflip(corr, is_corr_matrix=True)

    def test_invalid_diagonal_precomputed_fails(self):
        corr = np.eye(4)
        corr[0, 0] = 0.8
        with pytest.raises(ValueError, match="diagonal"):
            xflip(corr, is_corr_matrix=True)

    def test_out_of_range_precomputed_fails(self):
        corr = np.eye(4)
        corr[0, 1] = 1.5
        corr[1, 0] = 1.5
        with pytest.raises(ValueError, match=r"\[-1, 1\]"):
            xflip(corr, is_corr_matrix=True)

    def test_invalid_method_fails(self):
        with pytest.raises(ValueError, match="Unknown correlation method"):
            xflip(np.ones((4, 50)), method="kendall")

    def test_invalid_min_block_size_fails(self):
        with pytest.raises(ValueError, match="min_block_size must be >= 1"):
            xflip(np.ones((8, 50)), min_block_size=0)

    def test_invalid_n_blocks_fails(self):
        with pytest.raises(ValueError, match="n_blocks must be >= 1"):
            xflip(np.ones((8, 50)), n_blocks=0)

    @pytest.mark.parametrize("n_surrogates", [float("nan"), float("inf"), 2.5, -1])
    def test_invalid_n_surrogates_fails(self, n_surrogates):
        # NaN passed `n_surrogates < 0` as False, so it reached the surrogate loop.
        with pytest.raises(ValueError, match="n_surrogates"):
            xflip(np.ones((8, 50)), n_surrogates=n_surrogates)

    def test_integral_float_n_surrogates_is_accepted(self):
        rng = np.random.default_rng(42)
        raw = rng.normal(size=(8, 200))
        res = xflip(raw, n_surrogates=3.0, rng=42)
        assert isinstance(res, XFlipResult)
        assert res.n_channels == 8

    def test_autocorr_preserving_surrogate_with_precomputed_matrix_fails(self):
        corr = np.eye(4)
        with pytest.raises(ValueError, match="requires raw time-series"):
            xflip(corr, is_corr_matrix=True, surrogate_method="autocorr_preserving")


class TestXFlipMethods:
    """Test correlation methods: Pearson, Spearman, and partial correlation."""

    def test_pearson_parity_with_corrcoef(self):
        rng = np.random.default_rng(10)
        data = rng.normal(size=(6, 150))
        expected_corr = np.corrcoef(data)
        res = xflip(data, method="pearson", n_surrogates=0)
        assert np.allclose(res.corr_matrix, expected_corr, atol=1e-10)

    def test_spearman_rank_correlation(self):
        from scipy.stats import rankdata
        rng = np.random.default_rng(11)
        data = rng.normal(size=(6, 150))
        expected_corr = np.corrcoef(rankdata(data, axis=1))
        res = xflip(data, method="spearman", n_surrogates=0)
        assert np.allclose(res.corr_matrix, expected_corr, atol=1e-10)

    def test_partial_correlation(self):
        rng = np.random.default_rng(12)
        b = rng.normal(size=500)
        a = 0.8 * b + 0.2 * rng.normal(size=500)
        c = 0.8 * b + 0.2 * rng.normal(size=500)
        data = np.stack([a, b, c], axis=0)

        res_pearson = xflip(data, method="pearson", n_surrogates=0)
        res_partial = xflip(data, method="partial", n_surrogates=0)

        assert res_pearson.corr_matrix[0, 2] > 0.8
        assert abs(res_partial.corr_matrix[0, 2]) < 0.2
        assert np.allclose(np.diag(res_partial.corr_matrix), 1.0)


class TestXFlipContiguousPartitioning:
    """Test exact 1D dynamic programming contiguous block recovery."""

    def test_two_block_exact_recovery(self):
        data, true_labels, _ = synth_correlation_blocks(
            block_sizes=(8, 8),
            within_corr=0.8,
            between_corr=0.05,
            n_samples=600,
            rng=100,
        )
        res = xflip(data, n_blocks=2, min_block_size=3, n_surrogates=50, rng=100)
        assert res.accepted is True
        assert res.boundaries == (8,)
        assert res.block_bounds == ((0, 8), (8, 16))
        assert np.array_equal(res.labels, true_labels)
        assert res.modularity > 0.5
        assert res.p_values["omnibus"] <= 0.05

    def test_three_block_exact_recovery(self):
        data, true_labels, _ = synth_correlation_blocks(
            block_sizes=(6, 6, 6),
            within_corr=0.75,
            between_corr=0.05,
            n_samples=800,
            rng=200,
        )
        res = xflip(data, n_blocks=3, min_block_size=3, n_surrogates=50, rng=200)
        assert res.accepted is True
        assert res.boundaries == (6, 12)
        assert res.block_bounds == ((0, 6), (6, 12), (12, 18))
        assert np.array_equal(res.labels, true_labels)
        assert res.n_blocks == 3

    def test_minimum_block_size_enforcement(self):
        data, _, _ = synth_correlation_blocks(
            block_sizes=(7, 7),
            within_corr=0.7,
            between_corr=0.1,
            n_samples=400,
            rng=300,
        )
        res = xflip(data, n_blocks=2, min_block_size=5, n_surrogates=0)
        assert len(res.block_bounds) >= 2, res.block_bounds
        for st, en in res.block_bounds:
            assert (en - st) >= 5

    def test_auto_block_detection(self):
        data, true_labels, _ = synth_correlation_blocks(
            block_sizes=(8, 8),
            within_corr=0.8,
            between_corr=0.0,
            n_samples=500,
            rng=400,
        )
        res = xflip(data, n_blocks=None, min_block_size=4, n_surrogates=40, rng=400)
        assert res.accepted is True
        assert res.n_blocks == 2
        assert res.boundaries == (8,)

    def test_auto_block_count_recovers_blocks_that_share_a_background(self):
        # Four blocks sharing a background correlation of 0.3: a selector that scores only
        # within-block pairs merges them.
        data, _, _ = synth_correlation_blocks(
            (4, 4, 4, 4), within_corr=0.8, between_corr=0.3, n_samples=400, rng=7
        )
        res = xflip(data, n_blocks=None, min_block_size=3, n_surrogates=40, rng=107)
        assert res.accepted is True
        assert res.boundaries == (4, 8, 12)

    def test_auto_block_count_p_accounts_for_the_choice(self):
        # Every surrogate repeats the choice of count, so the reported p is never below the
        # chosen count's own p on the same surrogates, and exceeds it when another count
        # would have been chosen on some surrogate.
        strictly_above = 0
        for seed in range(6):
            data = synth_white_noise(shape=(16, 400), rng=seed + 40)
            auto = xflip(data, n_blocks=None, min_block_size=3, n_surrogates=40, rng=seed)
            k = len(auto.block_bounds)
            fixed = xflip(data, n_blocks=k, min_block_size=3, n_surrogates=40, rng=seed)
            assert fixed.boundaries == auto.boundaries
            assert auto.p_values["omnibus"] >= fixed.p_values["omnibus"]
            strictly_above += auto.p_values["omnibus"] > fixed.p_values["omnibus"]
        assert strictly_above > 0

    def test_auto_block_count_tie_goes_to_the_smallest_count(self):
        # All off-diagonal correlations equal: every count has p = 1 and no contrast above its
        # surrogates, so the tie-break alone decides, and it takes the least structure.
        corr = np.full((12, 12), 0.5)
        np.fill_diagonal(corr, 1.0)
        res = xflip(corr, n_blocks=None, min_block_size=3, n_surrogates=20, rng=0,
                    is_corr_matrix=True)
        assert len(res.boundaries) == 1
        assert res.p_values["omnibus"] == 1.0


class TestXFlipSurrogatesAndInference:
    """Test autocorrelation preservation, p-value resolution, and determinism."""

    def test_fourier_phase_surrogate_preserves_temporal_autocorrelation(self):
        from jnwb.laminar import _surrogate_phase_randomize

        fs = 1000.0
        n_channels = 4
        n_samples = 2000
        ar_data = synth_ar_noise(n_samples, n_channels=n_channels, fs=fs, tau_s=0.030, rng=50)

        rng = np.random.default_rng(123)
        surr = _surrogate_phase_randomize(ar_data, rng)

        assert surr.shape == ar_data.shape

        # Verify each channel's empirical power spectrum is preserved
        orig_fft = np.abs(np.fft.rfft(ar_data, axis=1))
        surr_fft = np.abs(np.fft.rfft(surr, axis=1))
        assert np.allclose(orig_fft, surr_fft, atol=1e-10)

        # By the discrete Wiener-Khinchin theorem, the circular autocorrelation function
        # is the inverse Fourier transform of the power spectrum and is identically preserved
        for ch in range(n_channels):
            circ_orig = np.fft.irfft(orig_fft[ch] ** 2, n=n_samples)
            circ_surr = np.fft.irfft(surr_fft[ch] ** 2, n=n_samples)
            assert np.allclose(circ_orig, circ_surr, atol=1e-10)

    def test_p_value_resolution_floor(self):
        data, _, _ = synth_correlation_blocks(
            block_sizes=(6, 6),
            within_corr=0.9,
            between_corr=0.0,
            n_samples=500,
            rng=60,
        )
        res = xflip(data, n_blocks=2, n_surrogates=49, rng=60)
        p_omni = res.p_values["omnibus"]
        assert p_omni >= 1.0 / 50.0
        assert p_omni != 0.0

    def test_determinism_across_same_and_different_seeds(self):
        data, _, _ = synth_correlation_blocks(
            block_sizes=(6, 6),
            within_corr=0.6,
            between_corr=0.1,
            n_samples=400,
            rng=70,
        )
        res1 = xflip(data, n_surrogates=50, rng=12345)
        res2 = xflip(data, n_surrogates=50, rng=12345)
        res3 = xflip(data, n_surrogates=50, rng=99999)

        assert res1.modularity == res2.modularity
        assert res1.boundaries == res2.boundaries
        assert res1.p_values["omnibus"] == res2.p_values["omnibus"]

        assert res3.modularity == res1.modularity
        assert isinstance(res3.p_values["omnibus"], float)

    def test_zero_surrogates_returns_nan_p_value_and_withholds_acceptance(self):
        """Not running the test is not the same as passing it.

        This used to assert `accepted is True` with `n_surrogates=0`. On genuinely blocky
        data that looks harmless, but the same rule accepted pure noise in 119 of 120
        seeds, and the surrogate test would have rejected 113 of those with omnibus p up
        to 0.87 -- while the reported p was NaN. `zflip` documents the opposite contract.
        """
        data, _, _ = synth_correlation_blocks(
            block_sizes=(5, 5),
            within_corr=0.8,
            between_corr=0.0,
            n_samples=300,
            rng=80,
        )
        res = xflip(data, n_surrogates=0)
        assert np.isnan(res.p_values["omnibus"])
        assert res.accepted is False
        assert "not performed" in res.rejection_reason

        # The very same data is accepted once the test actually runs.
        tested = xflip(data, n_surrogates=200, rng=0)
        assert tested.accepted is True
        assert tested.p_values["omnibus"] <= 0.05

    def test_untested_noise_is_not_accepted(self):
        """The case the old assertion licensed."""
        accepted = sum(
            xflip(
                np.random.default_rng(seed).standard_normal((16, 2000)),
                n_surrogates=0,
                rng=seed,
                min_contrast=0.0,
                min_boundary_drop=0.0,
            ).accepted
            for seed in range(20)
        )
        assert accepted == 0


class TestXFlipNullRejection:
    """Test false-positive control under null models (white noise and AR noise)."""

    def test_white_noise_rejected(self):
        white = synth_white_noise(shape=(12, 500), rng=90)
        res = xflip(white, n_blocks=2, n_surrogates=50, rng=90)
        assert res.accepted is False
        assert res.rejection_reason is not None

    def test_homogeneous_ar_noise_rejected_under_autocorr_surrogates(self):
        ar = synth_ar_noise(800, n_channels=12, fs=1000.0, tau_s=0.040, rng=91)
        res = xflip(ar, n_blocks=2, n_surrogates=50, surrogate_method="autocorr_preserving", rng=91)
        assert res.accepted is False
        assert res.rejection_reason is not None


class TestXFlipUnrestricted:
    """Test contiguous=False (unrestricted grouping)."""

    def test_unrestricted_grouping(self):
        corr = np.array([
            [1.0, 0.1, 0.8, 0.1, 0.8, 0.1],
            [0.1, 1.0, 0.1, 0.8, 0.1, 0.8],
            [0.8, 0.1, 1.0, 0.1, 0.8, 0.1],
            [0.1, 0.8, 0.1, 1.0, 0.1, 0.8],
            [0.8, 0.1, 0.8, 0.1, 1.0, 0.1],
            [0.1, 0.8, 0.1, 0.8, 0.1, 1.0],
        ])
        res = xflip(corr, contiguous=False, n_blocks=2, n_surrogates=30, rng=42)
        assert res.accepted is True
        assert res.labels[0] == res.labels[2] == res.labels[4]
        assert res.labels[1] == res.labels[3] == res.labels[5]
        assert res.labels[0] != res.labels[1]


TIE = 100 * np.finfo(float).eps


def _at_least(a, b):
    """``a`` is at least ``b`` to within the width every jnwb null uses for a correlation
    contrast: 100 machine epsilons of ``b``, and of 1."""
    return a >= b - TIE * max(1.0, abs(b))


def _min_p_by_brute_force(obs, surr):
    """The count-selection p written out as counts over every pair of draws, a draw counting
    another within round-off of its own contrast."""
    draws = np.vstack([obs[None], surr])
    n, k = draws.shape
    at_least = np.array([[sum(_at_least(draws[l, i], draws[j, i]) for l in range(n))
                          for i in range(k)]
                         for j in range(n)])
    smallest = at_least.min(axis=1)
    return at_least, smallest, [sum(smallest <= smallest[j]) / n for j in range(n)]


class TestTheCountSelectionTest:
    """`_select_count_by_min_p` on draws built to be exchangeable, away from any partition."""

    def test_size_is_at_most_alpha_on_exchangeable_draws(self):
        from scipy import stats

        from jnwb.laminar import _select_count_by_min_p

        # The observation and 40 surrogates drawn alike, three correlated counts, half the
        # draws rounded so that ties occur. Under exchangeability p <= alpha has probability
        # at most alpha; the bound is the one-sided 99.9% binomial quantile at alpha.
        rng = np.random.default_rng(0)
        n_trials, n_surr, alpha = 20000, 40, 0.05
        chol = np.linalg.cholesky(
            np.array([[1.0, 0.6, 0.4], [0.6, 1.0, 0.6], [0.4, 0.6, 1.0]])
        )
        significant = 0
        for _ in range(n_trials):
            draws = rng.normal(size=(n_surr + 1, 3)) @ chol.T
            if rng.random() < 0.5:
                draws = np.round(draws, 1)
            significant += _select_count_by_min_p(draws[0], draws[1:])[1] <= alpha
        assert significant <= int(stats.binom.ppf(0.999, n_trials, alpha)), significant

    def test_matches_brute_force_and_treats_the_observation_as_one_draw(self):
        from jnwb.laminar import _select_count_by_min_p

        rng = np.random.default_rng(1)
        for trial in range(400):
            k = int(rng.integers(1, 4))
            s = int(rng.integers(1, 30))
            if trial % 2:
                draws = rng.integers(0, 4, size=(s + 1, k)).astype(float)
            else:
                draws = rng.normal(size=(s + 1, k))
            at_least, smallest, p_brute = _min_p_by_brute_force(draws[0], draws[1:])
            chosen, p = _select_count_by_min_p(draws[0], draws[1:])
            assert p == p_brute[0]
            assert at_least[0, chosen] == smallest[0]
            # Swapping a surrogate into the observation's place gives that draw's p on the
            # same pool: the observation is ranked as one of the draws, not apart from them.
            j = int(rng.integers(1, s + 1))
            swapped = draws.copy()
            swapped[[0, j]] = swapped[[j, 0]]
            assert _select_count_by_min_p(swapped[0], swapped[1:])[1] == p_brute[j]
            if k == 1:
                assert p == (1 + np.sum(_at_least(draws[1:, 0], draws[0, 0]))) / (1 + s)

    def test_draws_that_tie_to_round_off_count_each_other(self):
        """A surrogate an ulp below the observation reproduces it; a bare comparison ranked
        the observation alone at the top."""
        from jnwb.laminar import _select_count_by_min_p

        obs = np.array([0.3])
        surr = np.array([[np.nextafter(0.3, 0.0)], [0.1], [0.2]])
        chosen, p = _select_count_by_min_p(obs, surr)
        assert (chosen, p) == (0, 0.5)
        assert p == _min_p_by_brute_force(obs, surr)[2][0]


class TestXFlipContainer:
    """Test XFlipResult dataclass accessors and serialization."""

    def test_container_accessors_and_serialization(self):
        corr = np.eye(4)
        res = xflip(corr, n_surrogates=0)
        assert res["n_channels"] == 4
        assert res.get("n_channels") == 4
        assert res.get("nonexistent", 42) == 42

        d = res.to_dict()
        assert isinstance(d, dict)
        assert d["n_channels"] == 4
        assert "corr_matrix" in d
        assert "modularity" in d
        assert "p_values" in d
        assert "accepted" in d

    def test_boundaries_are_plain_ints_and_survive_json(self):
        import json

        data, _, _ = synth_correlation_blocks([4, 4, 4], n_samples=400, rng=2)
        res = xflip(data, n_blocks=3, n_surrogates=5, rng=0)
        assert len(res.boundaries) == 2
        assert all(type(b) is int for b in res.boundaries)
        assert all(type(v) is int for pair in res.block_bounds for v in pair)

        # Arrays are encoded explicitly; any NumPy scalar left in the result raises.
        def arrays_only(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            raise TypeError(type(obj).__name__)

        back = json.loads(json.dumps(res.to_dict(), default=arrays_only))
        assert back["boundaries"] == list(res.boundaries)
        assert back["block_bounds"] == [list(pair) for pair in res.block_bounds]
        assert back["boundary_drops"] == {str(b): v for b, v in res.boundary_drops.items()}


class TestTheContiguousPartitionIsStillTheArgmax:
    """`interval_w` answered its off-diagonal term from a 2-D prefix sum in
    constant time, then re-summed `np.diag(corr)[u:v]` on every call. `np.diag` returns
    a view so nothing was copied, but the call, slice and reduction cost 4.82 of the
    5.56 microseconds a call took -- 87% -- and the DP makes about 93000 calls at
    n=256. `xflip` pays it `n_surrogates + 1` times.

    The item predicted this made an O(K n^2) DP into O(K n^3), "about n^2.9". It did
    not: measured 2.01, 2.03 and 2.06 at n = 128, 256 and 512, and 1.98 to 2.16 after
    the repair. numpy's fixed per-call overhead swamps the per-element work at these
    sizes, so the re-sum behaves as a constant. The item's own figures say the same
    thing -- 19.86 / 60.76 / 275.84 ms gives exponents of 1.61 and 2.18, not 2.9. The
    repair is worth 3.6x to 3.9x, and it is a constant, not an order.

    Prefix-summing the diagonal is not bit-identical to re-summing it: a difference of
    two running totals is a different floating-point operation from a pairwise
    reduction. Inside the reachable domain the difference is at most 4e-15 on a term of
    order 1 and reached no decision in 315 configurations; it changes the answer only
    for matrices no caller can supply, such as a 1e12 diagonal against 1e-6
    off-diagonals. These tests therefore pin the objective, not the arithmetic.
    """

    @staticmethod
    def _objective(corr, cuts):
        """The quantity the DP maximises, summed directly from `corr`.

        An oracle written from the docstring -- "S(u, v) is the sum of off-diagonal
        correlations within [u, v), P(u, v) = (v-u)(v-u-1)/2", each block scoring
        S**2 / P -- rather than from either implementation, so it cannot inherit a
        mistake from the code under test.
        """
        total = 0.0
        for u, v in cuts:
            s = 0.0
            for i in range(u, v):
                for j in range(i + 1, v):
                    s += corr[i, j]
            pairs = 0.5 * (v - u) * (v - u - 1)
            total += s * s / pairs if pairs > 0 else 0.0
        return total

    @staticmethod
    def _all_contiguous_partitions(n, k, min_size):
        """Every way to cut 0..n into k contiguous blocks of at least min_size."""
        if k == 1:
            if n >= min_size:
                yield [(0, n)]
            return

        def rec(start, remaining, acc):
            if remaining == 1:
                if n - start >= min_size:
                    yield acc + [(start, n)]
                return
            for end in range(start + min_size, n - (remaining - 1) * min_size + 1):
                yield from rec(end, remaining - 1, acc + [(start, end)])

        yield from rec(0, k, [])

    @pytest.mark.parametrize("n_blocks", [2, 3])
    def test_the_dp_finds_the_true_maximum(self, n_blocks):
        """Exhaustive check against brute force. Small n, so every partition can be
        enumerated and scored from the definition."""
        from jnwb.laminar import _optimal_contiguous_partition

        n, min_size = 12, 2
        for seed in range(6):
            rng = np.random.default_rng(seed)
            m = rng.uniform(-1.0, 1.0, (n, n))
            corr = np.clip(0.5 * (m + m.T), -1.0, 1.0)
            np.fill_diagonal(corr, 1.0)

            bounds, _, _, _ = _optimal_contiguous_partition(corr, n_blocks, min_size)
            got = self._objective(corr, bounds)
            best = max(self._objective(corr, p)
                       for p in self._all_contiguous_partitions(n, n_blocks, min_size))

            assert got == pytest.approx(best, rel=1e-12), (
                f"seed={seed}: DP scored {got}, the best partition scores {best}")

    def test_the_brute_force_oracle_can_tell_partitions_apart(self):
        """Without this, the test above passes if every partition scores the same."""
        rng = np.random.default_rng(0)
        m = rng.uniform(-1.0, 1.0, (12, 12))
        corr = np.clip(0.5 * (m + m.T), -1.0, 1.0)
        np.fill_diagonal(corr, 1.0)

        scores = {self._objective(corr, p)
                  for p in self._all_contiguous_partitions(12, 2, 2)}

        assert len(scores) > 1, "the oracle gives every partition the same score"

    def test_the_diagonal_is_read_once_per_call_not_once_per_interval(self, monkeypatch):
        """The discriminator, without a stopwatch. Before the repair `np.diag` was
        called once for every `interval_w` that passed the size check -- about 4900
        times at n=64. It is now called once, to build the prefix sum."""
        from jnwb.laminar import _optimal_contiguous_partition

        counts = {}
        original = np.diag

        def counting(*args, **kwargs):
            counts["n"] = counts.get("n", 0) + 1
            return original(*args, **kwargs)

        monkeypatch.setattr(np, "diag", counting)

        rng = np.random.default_rng(0)
        for n in (32, 64):
            m = rng.uniform(-1.0, 1.0, (n, n))
            corr = np.clip(0.5 * (m + m.T), -1.0, 1.0)
            np.fill_diagonal(corr, 1.0)
            counts["n"] = 0

            _optimal_contiguous_partition(corr, 3, 2)

            assert counts["n"] <= 2, (
                f"np.diag called {counts['n']} times at n={n}; the diagonal is being "
                f"re-read inside the loop")

    @pytest.mark.parametrize("n_blocks", [2, 3, 4])
    def test_a_matrix_of_exact_ties_still_partitions(self, n_blocks):
        """Every off-diagonal equal means every partition of a given shape scores
        identically, so the argmax is decided entirely by the tie-break. A change in
        the last bits of the score would be maximally visible here."""
        from jnwb.laminar import _optimal_contiguous_partition

        n = 24
        corr = np.full((n, n), 0.5)
        np.fill_diagonal(corr, 1.0)

        bounds, boundaries, _, labels = _optimal_contiguous_partition(corr, n_blocks, 2)

        assert len(bounds) == n_blocks
        assert bounds[0][0] == 0 and bounds[-1][1] == n
        assert len(set(labels.tolist())) == n_blocks

    @pytest.mark.parametrize("spike_at", [3, 11, 19])
    def test_one_large_diagonal_entry_does_not_attract_a_cut(self, spike_at):
        """The objective is defined on off-diagonal entries, so the diagonal must not
        influence where the cuts fall -- at all, not merely by little.

        A unit diagonal cannot show this: the per-block diagonal sums then differ
        between candidate partitions only by a constant, so a diagonal term that is
        subtly wrong still gives the right answer. Here every off-diagonal is equal, so
        the true objective ties every partition of a given shape, and the diagonal is
        flat except for one spike. Anything that lets the diagonal leak into the score
        pulls the cut to the spike.
        """
        from jnwb.laminar import _optimal_contiguous_partition

        n = 24
        corr = np.full((n, n), 0.5)

        flat = corr.copy()
        np.fill_diagonal(flat, 1.0)
        spiked = corr.copy()
        d = np.full(n, -1.0)
        d[spike_at] = 1.0
        np.fill_diagonal(spiked, d)

        a = _optimal_contiguous_partition(flat, 2, 2)
        b = _optimal_contiguous_partition(spiked, 2, 2)

        assert a[1] == b[1], (
            f"the cut moved from {a[1]} to {b[1]} when only the diagonal changed")
        assert np.array_equal(a[3], b[3])

    @pytest.mark.parametrize("seed", [0, 1, 2, 3])
    def test_the_partition_ignores_the_diagonal_on_a_structured_matrix(self, seed):
        """The same invariant where there is real structure to find, so a cut that is
        pinned by the off-diagonal signal still must not drift with the diagonal."""
        from jnwb.laminar import _optimal_contiguous_partition

        rng = np.random.default_rng(seed)
        n = 32
        lab = (np.arange(n) >= 13).astype(float)
        m = (lab[:, None] == lab[None, :]) * 0.6 + 0.2
        m = np.clip(0.5 * (m + m.T) + 0.05 * rng.standard_normal((n, n)), -1.0, 1.0)

        unit = m.copy()
        np.fill_diagonal(unit, 1.0)
        varied = m.copy()
        np.fill_diagonal(varied, rng.uniform(-1.0, 1.0, n))

        a = _optimal_contiguous_partition(unit, 3, 2)
        b = _optimal_contiguous_partition(varied, 3, 2)

        assert a[0] == b[0]
        assert a[1] == b[1]
        assert np.array_equal(a[3], b[3])

    def test_a_non_unit_diagonal_does_not_change_the_partition(self):
        """`np.corrcoef` does not always return an exactly unit diagonal -- 0.999...978
        occurs -- and the partial-correlation path and a clipped user matrix can differ
        further. The objective ignores the diagonal, so the partition must not depend
        on it."""
        from jnwb.laminar import _optimal_contiguous_partition

        rng = np.random.default_rng(0)
        m = rng.uniform(-1.0, 1.0, (40, 40))
        corr = np.clip(0.5 * (m + m.T), -1.0, 1.0)
        np.fill_diagonal(corr, 1.0)

        perturbed = corr.copy()
        np.fill_diagonal(perturbed, rng.uniform(-1.0, 1.0, 40))

        a = _optimal_contiguous_partition(corr, 3, 2)
        b = _optimal_contiguous_partition(perturbed, 3, 2)

        assert a[0] == b[0]
        assert a[1] == b[1]
        assert np.array_equal(a[3], b[3])


def _scalar_partition_cuts(corr, n_blocks, min_block_size):
    """The partition search as a scalar loop over (k, j, u), kept as the reference.

    The search scores all split points of one block count as an array. This loop scores
    them one at a time with the same arithmetic and keeps the first strictly greater
    value, so the two must agree cut for cut, ties included.
    """
    n = corr.shape[0]
    prefix = np.zeros((n + 1, n + 1))
    prefix[1:, 1:] = np.cumsum(np.cumsum(corr, axis=0), axis=1)
    diag_cum = np.concatenate(([0.0], np.cumsum(np.diag(corr))))

    def w(u, v):
        sz = v - u
        total = prefix[v, v] - prefix[u, v] - prefix[v, u] + prefix[u, u]
        s = 0.5 * (total - (diag_cum[v] - diag_cum[u]))
        pairs = 0.5 * sz * (sz - 1)
        return float(s * s / pairs) if pairs > 0 else 0.0

    dp = np.full((n_blocks + 1, n + 1), -np.inf)
    parent = np.full((n_blocks + 1, n + 1), -1, dtype=int)
    for j in range(min_block_size, n + 1):
        dp[1, j] = w(0, j)
    for k in range(2, n_blocks + 1):
        for j in range(k * min_block_size, n + 1):
            best_val, best_u = -np.inf, -1
            for u in range((k - 1) * min_block_size, j - min_block_size + 1):
                if dp[k - 1, u] == -np.inf:
                    continue
                val = dp[k - 1, u] + w(u, j)
                if val > best_val:
                    best_val, best_u = val, u
            dp[k, j], parent[k, j] = best_val, best_u
    if dp[n_blocks, n] == -np.inf:
        return ()
    cuts, j = [], n
    for k in range(n_blocks, 1, -1):
        j = int(parent[k, j])
        cuts.append(j)
    return tuple(reversed(cuts))


class TestThePartitionSearchMatchesTheScalarLoop:
    """The array form of the search must return the cuts a scalar loop returns.

    Exact ties are included on purpose: every off-diagonal equal makes the answer depend
    on the tie-break alone, which is where an argmax and a loop can part company.
    """

    @staticmethod
    def _matrices():
        rng = np.random.default_rng(7)
        for n in (6, 13, 24, 40):
            m = rng.uniform(-1.0, 1.0, (n, n))
            corr = np.clip(0.5 * (m + m.T), -1.0, 1.0)
            np.fill_diagonal(corr, 1.0)
            yield corr
            yield np.corrcoef(rng.standard_normal((n, 60))
                              + np.cumsum(rng.standard_normal((n, 1)), axis=0))
            tie = np.full((n, n), 0.5)
            np.fill_diagonal(tie, 1.0)
            yield tie
        # Mirror-symmetric with non-dyadic values: 0.7 on two equal end blocks, 0.3
        # elsewhere. Mirrored partitions tie in exact arithmetic, so the answer rests on the
        # last bits of each score, and summing the prefix terms in another order moves the
        # cut (9 channels did not show it; 10 do). The 0.5 matrix above is exact in binary
        # and cannot.
        mirror = np.full((10, 10), 0.3)
        mirror[:3, :3] = 0.7
        mirror[7:, 7:] = 0.7
        np.fill_diagonal(mirror, 1.0)
        yield mirror

    @pytest.mark.parametrize("n_blocks", [2, 3, 4])
    @pytest.mark.parametrize("min_block_size", [1, 2, 3])
    def test_identical_cuts(self, n_blocks, min_block_size):
        from jnwb.laminar import _optimal_contiguous_partition

        for corr in self._matrices():
            want = _scalar_partition_cuts(corr, n_blocks, min_block_size)
            got = _optimal_contiguous_partition(corr, n_blocks, min_block_size)[1]
            assert tuple(int(c) for c in got) == want, (
                f"n={corr.shape[0]}: array search cut at {got}, scalar loop at {want}")

    def test_an_infeasible_request_returns_one_block(self):
        from jnwb.laminar import _optimal_contiguous_partition

        bounds, boundaries, _, labels = _optimal_contiguous_partition(np.eye(5), 3, 2)
        assert bounds == ((0, 5),) and boundaries == ()
        assert not labels.any()


class TestXFlipRecordsItsSeed:
    """The result alone must reproduce its p-values: `rng=None` draws fresh entropy, and
    unless the result records it, a run cannot be repeated."""

    @staticmethod
    def _data():
        # White noise, so the p-values sit away from the 1/(n_surrogates+1) floor and a
        # different surrogate stream gives a different p.
        return synth_white_noise(shape=(12, 300), rng=5)

    def test_the_entropy_recorded_for_rng_none_reproduces_p(self):
        data = self._data()
        first = xflip(data, n_surrogates=40, rng=None)
        again = xflip(data, n_surrogates=40, rng=first.surrogate_seed_entropy)

        assert isinstance(first.surrogate_seed_entropy, int)
        assert again.p_values == first.p_values
        assert again.surrogate_seed_entropy == first.surrogate_seed_entropy
        assert first.to_dict()["surrogate_seed_entropy"] == first.surrogate_seed_entropy

    def test_the_reproduction_is_not_vacuous(self):
        """Two fresh draws must disagree somewhere, or equal p-values prove nothing."""
        data = self._data()
        draws = {tuple(sorted(xflip(data, n_surrogates=40, rng=None).p_values.items()))
                 for _ in range(4)}
        assert len(draws) > 1

    def test_an_int_seed_is_recorded_and_keeps_its_stream(self, monkeypatch):
        """An int seed draws `default_rng(seed)`, the stream a Generator consumed in place
        drew before the child seed."""
        import jnwb._rng
        from jnwb.laminar import _xflip

        data = self._data()
        res = xflip(data, n_surrogates=40, rng=123)
        assert res.surrogate_seed_entropy == 123
        monkeypatch.setattr(_xflip, "recorded_rng", jnwb._rng.surrogate_rng)
        assert res.p_values == xflip(data, n_surrogates=40,
                                     rng=np.random.default_rng(123)).p_values

    def test_a_generator_records_the_child_seed_that_reproduces_p(self):
        """A `Generator` recorded None, so its p-values could not be reproduced from the
        result; one child draw now seeds the surrogates and is recorded."""
        data = self._data()
        caller = np.random.default_rng(1)
        first = xflip(data, n_surrogates=40, rng=caller)
        assert isinstance(first.surrogate_seed_entropy, int)
        assert xflip(data, n_surrogates=40,
                     rng=first.surrogate_seed_entropy).p_values == first.p_values
        # The caller's stream advanced by exactly the one child draw.
        replay = np.random.default_rng(1)
        assert int(replay.integers(0, 2**63 - 1)) == first.surrogate_seed_entropy
        assert caller.random() == replay.random()

    def test_an_untested_partition_records_none(self):
        assert xflip(self._data(), n_surrogates=0, rng=3).surrogate_seed_entropy is None

    @pytest.mark.parametrize("bad", [2.7, True])
    def test_a_float_or_bool_seed_is_refused(self, bad):
        with pytest.raises(TypeError, match="rng"):
            xflip(self._data(), n_surrogates=5, rng=bad)


def _one_block_beside_background(seed, edge=6, n=16, rho=0.8, n_samples=1000):
    """Contacts 0..edge-1 share one source; contacts edge..n-1 are independent noise."""
    rng = np.random.default_rng(seed)
    common = rng.standard_normal(n_samples)
    data = rng.standard_normal((n, n_samples))
    data[:edge] = np.sqrt(rho) * common + np.sqrt(1.0 - rho) * data[:edge]
    return data


class TestOneBlockBesideAnUncorrelatedBackground:
    """The true boundary is the edge of the correlated block.

    An objective that penalises every within-block pair by the probe-wide mean
    correlation favours blocks of equal size, and cut this case at 7 to 9 in every seed.
    """

    def test_the_boundary_is_found_at_the_block_edge(self):
        for seed in range(3):
            res = xflip(_one_block_beside_background(seed), n_blocks=2, min_block_size=2,
                        n_surrogates=50, rng=seed)
            assert res.boundaries == (6,), f"seed={seed}: cut at {res.boundaries}"

    def test_an_accepted_boundary_is_the_block_edge(self):
        """Worse than missing the edge: a cut inside the background was accepted in 3 of
        these 10 seeds, because the omnibus test answers whether any structure exists,
        not where it is."""
        accepted = 0
        for seed in range(10):
            res = xflip(_one_block_beside_background(seed), n_blocks=2, min_block_size=2,
                        n_surrogates=50, rng=seed)
            if res.accepted:
                accepted += 1
                assert res.boundaries == (6,), f"seed={seed}: accepted a cut at {res.boundaries}"
        # The block is real, so rejecting everything would pass the loop above vacuously.
        assert accepted >= 8, f"only {accepted} of 10 seeds accepted the block"


# Homogeneous null on boundary-free and two-block probes
#
# xFLIP's default null against probes with no boundary and against a two-block probe.
#
# Phase-randomized surrogates make channels independent, so a volume-conducted probe with no
# boundary sits at the omnibus p floor. The homogeneous null keeps the probe's lag-averaged
# correlation, so a partition is significant only beyond smooth spatial decay.
#
# This module is slow, roughly three minutes: test_false_positive_rate_on_boundary_free_probes
# runs 200 probes and takes about 160 s of it. The suite has no slow marker, so the note stands
# in for one.



N_T = 4000
ALPHA = 0.05
N_SURROGATES = 100


def _volume_conducted(seed, n_ch=24, n_t=N_T, scale=3.0):
    """Every contact sees the same sources through one smooth kernel; nothing changes along the shaft."""
    rng = np.random.default_rng(seed)
    sources = rng.standard_normal((n_ch * 3, n_t))
    pos_src = np.linspace(-6, n_ch + 6, n_ch * 3)
    pos_ch = np.arange(n_ch)
    kernel = np.exp(-np.abs(pos_ch[:, None] - pos_src[None, :]) / scale)
    return kernel @ sources + 0.2 * rng.standard_normal((n_ch, n_t))


def _two_blocks(seed, n_t=N_T):
    """Contacts 0-11 and 12-23, each driven by its own disjoint sources through the same kernel."""
    rng = np.random.default_rng(seed)
    lfp = np.empty((24, n_t))
    for first in (0, 12):
        contacts = np.arange(first, first + 12)
        sources = rng.standard_normal((36, n_t))
        pos_src = np.linspace(first - 6, first + 17, 36)
        kernel = np.exp(-np.abs(contacts[:, None] - pos_src[None, :]) / 3.0)
        lfp[first:first + 12] = kernel @ sources
    return lfp + 0.2 * rng.standard_normal((24, n_t))


def test_a_volume_conducted_probe_is_not_significant_under_the_default_null():
    """24 contacts, kernel scale 3, seeds 0-9, 100 surrogates."""
    old_p, new_p = [], []
    for seed in range(10):
        lfp = _volume_conducted(seed)
        corr = np.corrcoef(lfp)
        assert corr[0, 1] > corr[0, 5] > corr[0, 12] > 0.0, "fixture must decay with distance"
        old = jnwb.xflip(lfp, n_surrogates=N_SURROGATES, rng=seed,
                         surrogate_method="autocorr_preserving")
        new = jnwb.xflip(lfp, n_surrogates=N_SURROGATES, rng=seed)
        old_p.append(old.p_values["omnibus"])
        new_p.append(new.p_values["omnibus"])
    floor = 1 / (N_SURROGATES + 1)
    assert sum(math.isclose(p, floor) for p in old_p) >= 9, (
        f"the fixture must be the independent-channel case: old-null p per seed {old_p}"
    )
    assert sum(p > ALPHA for p in new_p) >= 9, (
        f"default-null omnibus p per seed {new_p}; need p > {ALPHA} on at least 9 of 10"
    )


def test_b_two_blocks_with_disjoint_sources_are_accepted_at_the_boundary():
    """Contacts 0-11 and 12-23, disjoint sources per block, seeds 0-9, 100 surrogates."""
    accepted_boundaries = []
    n_accepted = 0
    for seed in range(10):
        lfp = _two_blocks(seed)
        corr = np.corrcoef(lfp)
        within = corr[:12, :12][~np.eye(12, dtype=bool)].mean()
        across = corr[:12, 12:].mean()
        assert within > across + 0.3, "fixture must have two blocks"
        res = jnwb.xflip(lfp, n_surrogates=N_SURROGATES, rng=seed)
        if res.accepted:
            n_accepted += 1
            accepted_boundaries.append(res.boundaries)
    assert n_accepted >= 9, f"accepted on {n_accepted} of 10 seeds; need at least 9"
    assert all(len(b) == 1 and abs(b[0] - 12) <= 1 for b in accepted_boundaries), (
        f"boundaries of the accepted seeds {accepted_boundaries}; each must be 12 +- 1"
    )


def test_false_positive_rate_on_boundary_free_probes_is_at_the_nominal_level():
    """200 boundary-free probes, seeds 0-199, 100 surrogates, omnibus p at alpha 0.05."""
    n = 200
    hits = 0
    for seed in range(n):
        lfp = _volume_conducted(seed)
        corr = np.corrcoef(lfp)
        assert corr[0, 1] > corr[0, 12], "fixture must decay with distance"
        res = jnwb.xflip(lfp, n_surrogates=N_SURROGATES, rng=seed)
        hits += int(res.p_values["omnibus"] <= ALPHA)
    bound = ALPHA + 2 * math.sqrt(ALPHA * (1 - ALPHA) / n)
    assert hits / n <= bound, (
        f"{hits} of {n} boundary-free probes have omnibus p <= {ALPHA}; bound {bound:.4f}"
    )


def test_correlation_matrix_with_n_samples_is_not_significant_on_a_boundary_free_probe():
    """Five boundary-free seeds, passed as correlation matrices with n_samples."""
    n_above = 0
    for seed in range(5):
        corr = np.corrcoef(_volume_conducted(seed))
        assert np.allclose(np.diag(corr), 1.0), "fixture must be a correlation matrix"
        res = jnwb.xflip(corr, n_surrogates=N_SURROGATES, rng=seed, n_samples=N_T)
        assert res.method == "precomputed"
        n_above += int(res.p_values["omnibus"] > ALPHA)
    assert n_above >= 4, f"omnibus p > {ALPHA} on {n_above} of 5 seeds; need at least 4"


def test_correlation_matrix_with_n_samples_accepts_two_blocks():
    """The Wishart null must still reject a real boundary: five two-block seeds as matrices."""
    n_accepted = 0
    for seed in range(5):
        corr = np.corrcoef(_two_blocks(seed))
        assert corr[:12, :12][~np.eye(12, dtype=bool)].mean() > corr[:12, 12:].mean() + 0.3, (
            "fixture must have two blocks")
        res = jnwb.xflip(corr, n_surrogates=N_SURROGATES, rng=seed, n_samples=N_T)
        assert res.method == "precomputed"
        n_accepted += int(res.accepted and abs(res.boundaries[0] - 12) <= 1)
    assert n_accepted >= 4, f"accepted at 12 +- 1 on {n_accepted} of 5 seeds; need at least 4"


def test_correlation_matrix_without_n_samples_warns_once_and_names_the_limit():
    corr = np.corrcoef(_volume_conducted(0))
    assert np.allclose(np.diag(corr), 1.0), "fixture must be a correlation matrix"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        res = jnwb.xflip(corr, n_surrogates=N_SURROGATES, rng=0)
    assert res.method == "precomputed"
    notes = [w for w in caught
             if issubclass(w.category, UserWarning) and "n_samples" in str(w.message)]
    assert len(notes) == 1, [str(w.message) for w in caught]
    assert "independent channels" in str(notes[0].message)


def test_n_samples_is_refused_for_raw_data_and_homogeneous_needs_it_for_a_matrix():
    lfp = _volume_conducted(0)
    with pytest.raises(ValueError, match="n_samples"):
        jnwb.xflip(lfp, n_surrogates=5, rng=0, n_samples=N_T)
    corr = np.corrcoef(lfp)
    assert np.allclose(np.diag(corr), 1.0), "fixture must be a correlation matrix"
    with pytest.raises(ValueError, match="n_samples"):
        jnwb.xflip(corr, n_surrogates=5, rng=0, surrogate_method="homogeneous")


# Null under nuisance structure (receipt operating point)
#
# xFLIP's null under nuisance structure: the operating point and the length-4 generator are the
# receipt's, the interval is the library's exact Clopper-Pearson, the planted average-reference cell
# is referenced to its channel average, and a smoke run on two seeds puts every count inside its
# interval.



RAW = ROOT / "artifacts" / "benchmarks" / "calibration" / "xflip_calibration_0.2.5_raw.json"


def test_the_operating_point_is_the_receipts():
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    assert nuisance.N_SURROGATES == raw["n_surrogates"]
    assert nuisance.N_SAMPLES == raw["n_samples"]
    assert nuisance.MIN_BLOCK_SIZE == raw["min_block_size"]
    assert nuisance.ALPHA == raw["alpha"]


def test_length_four_draws_the_receipts_smooth_gradient_cell():
    for seed in (0, 7):
        mine = nuisance.toeplitz_null(seed, 4.0)
        theirs, _ = receipt._smooth_spatial_gradient(seed)
        assert mine.shape == (16, nuisance.N_SAMPLES)
        assert np.array_equal(mine, theirs), f"seed {seed}: length 4 must draw the receipt's cell"


def test_clopper_pearson_with_no_successes_has_its_exact_upper_bound():
    low, high = jnwb.clopper_pearson(0, 30, alpha=0.05)
    assert low == 0.0
    assert abs(high - (1.0 - 0.025 ** (1.0 / 30))) < 1e-9


def test_unit_power_scales_a_component_to_unit_mean_power():
    x = nuisance.toeplitz_null(5, 4.0)
    assert abs(float(np.mean(np.var(nuisance._unit_power(x), axis=1))) - 1.0) < 1e-12


def test_the_average_reference_planted_cell_is_referenced_to_its_channel_average():
    data = nuisance.planted_average_reference(3)
    assert data.shape == (16, nuisance.N_SAMPLES)
    assert np.allclose(data.mean(axis=0), 0.0, atol=1e-12)


def test_smoke_path_on_one_null_cell_counts_sit_inside_their_intervals():
    started = time.perf_counter()
    rows = nuisance.run_cell(lambda seed: nuisance.toeplitz_null(seed, 4.0), n_seeds=2,
                             n_surrogates=nuisance.N_SURROGATES)
    elapsed = time.perf_counter() - started
    assert len(rows) == 2, "the cell must run both seeds"
    assert all(np.isfinite(row[key]["p_omnibus"]) for row in rows for key in nuisance.BLOCK_COUNTS)
    for key in nuisance.BLOCK_COUNTS:
        summary = nuisance.null_summary(rows, key)
        for entry in summary.values():
            assert entry["n"] == 2
            low, high = entry["ci"]
            assert low <= entry["k"] / entry["n"] <= high
    assert elapsed < 20, f"the smoke path took {elapsed:.1f} s"


# XFlipResult.null_method: the surrogate null that produced p_values
#
# XFlipResult.null_method: the surrogate null that produced `p_values`.




def _raw():
    data, _, _ = synth_correlation_blocks([4, 4], n_samples=300, rng=0)
    return data


def _matrix():
    return np.array([
        [1.0, 0.6, 0.1, 0.1],
        [0.6, 1.0, 0.1, 0.1],
        [0.1, 0.1, 1.0, 0.7],
        [0.1, 0.1, 0.7, 1.0],
    ])


def test_auto_raw_data_resolves_homogeneous():
    res = xflip(_raw(), n_surrogates=10, rng=11)
    assert res.null_method == "homogeneous"


def test_auto_matrix_with_n_samples_resolves_homogeneous():
    res = xflip(_matrix(), is_corr_matrix=True, n_samples=300, n_surrogates=10, rng=11)
    assert res.null_method == "homogeneous"


def test_auto_matrix_without_n_samples_falls_back_to_permute_channels():
    with pytest.warns(UserWarning, match="n_samples"):
        res = xflip(_matrix(), is_corr_matrix=True, n_surrogates=10, rng=42)
    assert res.null_method == "permute_channels"


@pytest.mark.parametrize(
    "method", ["homogeneous", "autocorr_preserving", "permute_channels"]
)
def test_explicit_method_records_itself(method):
    res = xflip(_raw(), n_surrogates=10, surrogate_method=method, rng=11)
    assert res.null_method == method


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [("phase_randomize", "autocorr_preserving"), ("channel_permute", "permute_channels")],
)
def test_alias_records_canonical_name(alias, canonical):
    res = xflip(_raw(), n_surrogates=10, surrogate_method=alias, rng=11)
    assert res.null_method == canonical


def test_n_surrogates_zero_records_none():
    res = xflip(_raw(), n_surrogates=0, rng=11)
    assert res.null_method is None


def test_zero_variance_refusal_records_none():
    raw = _raw()
    raw[0, :] = 1.0
    res = xflip(raw, n_surrogates=10, rng=11)
    assert res.accepted is False
    assert "Zero-variance" in (res.rejection_reason or "")
    assert res.null_method is None


def test_structural_refusal_records_none():
    res = xflip(_raw()[:4], n_blocks=3, n_surrogates=10, rng=11)
    assert res.accepted is False
    assert "insufficient" in (res.rejection_reason or "")
    assert res.null_method is None


def test_to_dict_carries_null_method():
    res = xflip(_raw(), n_surrogates=10, rng=11)
    assert res.to_dict()["null_method"] == "homogeneous"
    res_none = xflip(_raw(), n_surrogates=0, rng=11)
    assert res_none.to_dict()["null_method"] is None


def test_p_values_match_baseline():
    raw = _raw()
    res = xflip(raw, n_surrogates=10, rng=11)
    np.testing.assert_allclose(res.p_values["omnibus"], 1 / 11, rtol=1e-12)
    np.testing.assert_allclose(res.p_values["boundary_4"], 1 / 11, rtol=1e-12)
    res_perm = xflip(raw, n_surrogates=10, surrogate_method="permute_channels", rng=11)
    np.testing.assert_allclose(res_perm.p_values["omnibus"], 1 / 11, rtol=1e-12)
    np.testing.assert_allclose(res_perm.p_values["boundary_4"], 1 / 11, rtol=1e-12)
    res_mat = xflip(_matrix(), is_corr_matrix=True, n_samples=300, n_surrogates=10, rng=11)
    np.testing.assert_allclose(res_mat.p_values["omnibus"], 1 / 11, rtol=1e-12)
    np.testing.assert_allclose(res_mat.p_values["boundary_2"], 1 / 11, rtol=1e-12)
