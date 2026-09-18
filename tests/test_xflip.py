"""Tests for jnwb.laminar: Cross-Channel Laminar Correlation Profile (xFLIP)."""
from __future__ import annotations

import numpy as np
import pytest

import jnwb
from jnwb.laminar import XFlipResult, xflip
from jnwb.testing import synth_ar_noise, synth_correlation_blocks, synth_white_noise


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
        rng = np.random.default_rng(0)
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


class TestTheContiguousPartitionIsStillTheArgmax:
    """05-47: `interval_w` answered its off-diagonal term from a 2-D prefix sum in
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
    def _objective(corr, cuts, gamma):
        """The quantity the DP maximises, summed directly from `corr`.

        An oracle written from the docstring -- "S(u, v) is sum of off-diagonal
        correlations in [u, v), P(u, v) is (v-u)(v-u-1)/2" -- rather than from either
        implementation, so it cannot inherit a mistake from the code under test.
        """
        total = 0.0
        for u, v in cuts:
            s = 0.0
            for i in range(u, v):
                for j in range(i + 1, v):
                    s += corr[i, j]
            total += s - gamma * (0.5 * (v - u) * (v - u - 1))
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
            triu = np.triu_indices(n, k=1)
            gamma = float(np.mean(corr[triu]))

            bounds, _, _, _ = _optimal_contiguous_partition(corr, n_blocks, min_size)
            got = self._objective(corr, bounds, gamma)
            best = max(self._objective(corr, p, gamma)
                       for p in self._all_contiguous_partitions(n, n_blocks, min_size))

            assert got == pytest.approx(best, rel=1e-12), (
                f"seed={seed}: DP scored {got}, the best partition scores {best}")

    def test_the_brute_force_oracle_can_tell_partitions_apart(self):
        """Without this, the test above passes if every partition scores the same."""
        rng = np.random.default_rng(0)
        m = rng.uniform(-1.0, 1.0, (12, 12))
        corr = np.clip(0.5 * (m + m.T), -1.0, 1.0)
        np.fill_diagonal(corr, 1.0)
        gamma = float(np.mean(corr[np.triu_indices(12, k=1)]))

        scores = {self._objective(corr, p, gamma)
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
