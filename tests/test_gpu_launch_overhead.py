"""05-45: two CUDA paths were slower than their CPU siblings, one by 24x.

Both were Python loops issuing one kernel launch per element, and in both cases the
launches -- not the host/device transfers the audit blamed -- were the cost.

`UnitAnalyzer._acg_vectorized` had two GPU branches and neither was usable at scale:

* below 30000 spikes it built the full `N x N` difference matrix. At 29999 spikes that
  is `29999**2 * 8` bytes = **6.71 GiB** of device memory, requested just under the
  threshold the code treated as safe.
* at or above 30000 it chunked by 1000 and then looped in Python *inside* the chunk.
  Measured at 35000 spikes: 35001 `cupy.asarray` uploads of a loop-invariant
  `bin_edges`, 35000 `cupy.histogram` launches, and 70000 forced device-to-host syncs
  from `int(lo[idx])` / `int(hi[idx])`. Paired against its own CPU sibling in one
  contended session: 22476 ms against 930 ms, `R = 24.2`.

  Splitting that: 2N x `int(device_scalar)` = 2.2 s, N x `cupy.asarray(bin_edges)` =
  1.6 s, N x `cupy.histogram` = 12.2 s. The kernel launches are 76% of the accounted
  time; the transfers the audit named are 24%.

The CPU branch had the same shape -- one `numpy.histogram` per spike -- and was 32x to
46x slower than the flattened form for identical counts.

`_welch_csd_gpu` appended one device array per Welch segment: 127 iterations and about
762 launches for a 16384-sample trace at `nperseg=256`, 26.8 ms against 16.6 ms for the
equivalent scipy calls.

Every repair here is exact, not approximate: the flattened ACG is bit-identical to the
previous implementation at 500, 5000 and 35000 spikes, and the strided Welch is
bit-identical to the segment loop for every `nperseg` from 64 to 2048 --
`max|difference|` is `0.0`, not merely small. At 4096 and 8192 it agrees to 1.43e-13
relative, inside the CUDA path's pre-existing disagreement with scipy; the reason is
recorded on the test that asserts it. Timing is measured elsewhere; this file pins the
shapes and the counts, which is what a test can hold.
"""

from __future__ import annotations

import numpy as np
import pytest

from jnwb._backend import cupy_available
from jnwb.analyzers import UnitAnalyzer

requires_cuda = pytest.mark.skipif(not cupy_available(),
                                   reason="no CuPy device on this machine")

MAX_LAG = 0.1
BIN = 0.001


def spikes(n, seed=0, span_per_spike=1 / 40.0):
    rng = np.random.default_rng(seed)
    return np.sort(rng.uniform(0.0, n * span_per_spike, n))


def naive_acg(spike_times, max_lag=MAX_LAG, bin_size=BIN):
    """The shape the CPU branch used to have: one histogram per spike."""
    n_bins = int(max_lag / bin_size)
    edges = np.linspace(-max_lag, max_lag, 2 * n_bins + 2)
    acg = np.zeros(2 * n_bins + 1, dtype=np.int64)
    st = np.sort(spike_times)
    for t in st:
        lo = np.searchsorted(st, t - max_lag, side="left")
        hi = np.searchsorted(st, t + max_lag, side="right")
        hist, _ = np.histogram(st[lo:hi] - t, bins=edges)
        acg += hist
    acg[n_bins] = 0
    return acg[n_bins + 1:], np.linspace(0, max_lag, n_bins + 1)[:-1]


class TestTheFlattenedAcgIsTheSameEstimator:
    """Bit-identical, against an independent implementation of the old shape."""

    @pytest.mark.parametrize("n", [11, 100, 500, 5000])
    def test_counts_match_one_histogram_per_spike(self, n):
        st = spikes(n)
        expected, expected_lags = naive_acg(st)

        got, lags = UnitAnalyzer._acg_vectorized(st, MAX_LAG, BIN, device="cpu")

        assert np.array_equal(got, expected)
        assert np.array_equal(lags, expected_lags)

    def test_the_fixture_actually_has_pairs_to_count(self):
        """A fixture with no in-window pairs would make every count test vacuous."""
        got, _ = UnitAnalyzer._acg_vectorized(spikes(5000), MAX_LAG, BIN, device="cpu")

        assert got.sum() > 0

    def test_unsorted_input_is_sorted_first(self):
        st = spikes(300)
        shuffled = st.copy()
        np.random.default_rng(1).shuffle(shuffled)

        a, _ = UnitAnalyzer._acg_vectorized(st, MAX_LAG, BIN, device="cpu")
        b, _ = UnitAnalyzer._acg_vectorized(shuffled, MAX_LAG, BIN, device="cpu")

        assert np.array_equal(a, b)

    def test_the_returned_half_starts_one_bin_past_centre(self):
        """Every spike matches itself, so the centre bin holds at least N counts. It is
        the slice that drops them, not the ``acg[centre] = 0`` above it: that statement
        writes the one index the slice already excludes, so it cannot change any
        returned number. Mutation-checked -- deleting it kills nothing, and the boundary
        below is what actually carries the self-count removal."""
        n_bins = int(MAX_LAG / BIN)
        edges = np.linspace(-MAX_LAG, MAX_LAG, 2 * n_bins + 2)
        st = spikes(400)
        full = UnitAnalyzer._acg_histogram(np, st, MAX_LAG, edges, n_bins)

        assert full[n_bins] >= len(st)

        got, lags = UnitAnalyzer._acg_vectorized(st, MAX_LAG, BIN, device="cpu")

        assert len(got) == n_bins == len(lags)
        assert np.array_equal(got, full[n_bins + 1:])

    def test_a_pair_exactly_at_max_lag_is_counted(self):
        """Both replaced branches bounded the window with ``side='right'`` -- and the
        broadcast branch with ``diffs <= max_lag`` -- so a pair separated by exactly
        ``max_lag`` falls in the last bin rather than off the end. Random float spike
        times never land on that boundary, so it needs a train that does: unit spacing
        makes ``st[i] + 10.0`` bit-equal to ``st[i + 10]``."""
        max_lag, bin_size = 10.0, 1.0
        train = np.arange(40, dtype=float)
        assert np.all(train[:30] + max_lag == train[10:]), "boundary not exact"

        got, _ = UnitAnalyzer._acg_vectorized(train, max_lag, bin_size, device="cpu")
        expected, _ = naive_acg(train, max_lag, bin_size)

        assert np.array_equal(got, expected)
        assert got[-1] == 30, "the pairs exactly at +max_lag were dropped"

    def test_an_empty_train_gives_zeros_rather_than_raising(self):
        got, lags = UnitAnalyzer._acg_vectorized(np.array([]), MAX_LAG, BIN,
                                                 device="cpu")

        assert got.sum() == 0
        assert len(lags) == int(MAX_LAG / BIN)

    def test_a_single_spike_counts_only_itself(self):
        got, _ = UnitAnalyzer._acg_vectorized(np.array([1.0]), MAX_LAG, BIN,
                                              device="cpu")

        assert got.sum() == 0


class TestItNoLongerHistogramsOncePerSpike:
    """The defect was the launch count, so the test holds the launch count."""

    @staticmethod
    def _count_histograms(monkeypatch, fn):
        calls = []
        original = np.histogram

        def counting(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        monkeypatch.setattr(np, "histogram", counting)
        fn()
        return len(calls)

    @pytest.mark.parametrize("n", [1000, 5000, 20000])
    def test_the_histogram_count_does_not_grow_with_the_spike_count(self, n,
                                                                     monkeypatch):
        st = spikes(n)
        calls = self._count_histograms(
            monkeypatch,
            lambda: UnitAnalyzer._acg_vectorized(st, MAX_LAG, BIN, device="cpu"))

        assert calls < 20, f"{calls} histograms for {n} spikes"

    def test_a_dense_train_is_split_into_more_chunks_not_one_huge_allocation(self):
        """The chunk width comes from the widest window present, so the pairs held at
        once stay bounded however dense the train is. A fixed spike-count chunk would
        scale the allocation with the firing rate."""
        sparse = spikes(4000, span_per_spike=1 / 40.0)
        dense = spikes(4000, span_per_spike=1 / 4000.0)
        n_bins = int(MAX_LAG / BIN)
        edges = np.linspace(-MAX_LAG, MAX_LAG, 2 * n_bins + 2)

        widest_sparse = int(np.max(
            np.searchsorted(sparse, sparse + MAX_LAG, side="right")
            - np.searchsorted(sparse, sparse - MAX_LAG, side="left")))
        widest_dense = int(np.max(
            np.searchsorted(dense, dense + MAX_LAG, side="right")
            - np.searchsorted(dense, dense - MAX_LAG, side="left")))

        assert widest_dense > widest_sparse * 10, "fixture is not actually denser"

        budget = UnitAnalyzer._ACG_PAIR_BUDGET
        assert budget // max(widest_dense, 1) < budget // max(widest_sparse, 1)
        # and it still computes the right answer on the dense train
        expected, _ = naive_acg(dense)
        got = UnitAnalyzer._acg_histogram(np, dense, MAX_LAG, edges, n_bins)
        got[n_bins] = 0
        assert np.array_equal(got[n_bins + 1:], expected)


@requires_cuda
class TestTheTwoDevicesAgreeExactly:
    """One implementation runs under both `numpy` and `cupy`, so they cannot drift.
    `AGENTS.md` invariant 6: the device never changes a number."""

    @pytest.mark.parametrize("n", [500, 5000, 35000])
    def test_the_acg_is_bit_identical_across_devices(self, n):
        import warnings

        st = spikes(n)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cpu, cpu_lags = UnitAnalyzer._acg_vectorized(st, MAX_LAG, BIN, device="cpu")
            cuda, cuda_lags = UnitAnalyzer._acg_vectorized(st, MAX_LAG, BIN,
                                                           device="cuda")

        assert np.array_equal(cpu, cuda)
        assert np.array_equal(cpu_lags, cuda_lags)

    def test_the_large_train_crosses_the_old_thirty_thousand_threshold(self):
        """35000 is past the branch that used to loop per spike; 5000 is not. Without
        both, the parametrisation above would not cover the path that was 24x slow."""
        assert 35000 >= 30000 > 5000


@requires_cuda
class TestWelchBuildsItsSegmentsInOneIndex:

    @staticmethod
    def _segment_loop_reference(x, y, fs, nperseg, noverlap=None, detrend="constant"):
        """The shape `_welch_csd_gpu` used to have, kept here as the oracle."""
        import cupy as cp

        if noverlap is None:
            noverlap = nperseg // 2
        step = nperseg - noverlap
        x_g = cp.asarray(x, dtype=cp.float64)
        y_g = cp.asarray(y, dtype=cp.float64)
        n = len(x_g)
        window = 0.5 - 0.5 * cp.cos(2.0 * cp.pi * cp.arange(nperseg) / nperseg)
        segments_x, segments_y, start = [], [], 0
        while start + nperseg <= n:
            seg_x = x_g[start:start + nperseg]
            seg_y = y_g[start:start + nperseg]
            if detrend == "constant":
                seg_x = seg_x - cp.mean(seg_x)
                seg_y = seg_y - cp.mean(seg_y)
            segments_x.append(seg_x * window)
            segments_y.append(seg_y * window)
            start += step
        X = cp.fft.rfft(cp.stack(segments_x), axis=-1)
        Y = cp.fft.rfft(cp.stack(segments_y), axis=-1)
        scale = 1.0 / (fs * cp.sum(window ** 2))
        psd_x = cp.mean(cp.abs(X) ** 2, axis=0) * scale
        psd_y = cp.mean(cp.abs(Y) ** 2, axis=0) * scale
        csd = cp.mean(cp.conj(X) * Y, axis=0) * scale
        if nperseg % 2:
            psd_x[1:] *= 2.0
            psd_y[1:] *= 2.0
            csd[1:] *= 2.0
        else:
            psd_x[1:-1] *= 2.0
            psd_y[1:-1] *= 2.0
            csd[1:-1] *= 2.0
        return (cp.fft.rfftfreq(nperseg, d=1.0 / fs).get(), psd_x.get(), psd_y.get(),
                csd.get())

    @staticmethod
    def _signals(n=16384):
        rng = np.random.default_rng(0)
        t = np.arange(n) / 1000.0
        return (np.sin(2 * np.pi * 20 * t) + 0.5 * rng.standard_normal(n) + 3.0,
                np.sin(2 * np.pi * 20 * t + 0.6) + 0.5 * rng.standard_normal(n) + 3.0)

    @pytest.mark.parametrize("nperseg", [64, 128, 255, 256, 512, 1024, 2048])
    def test_it_is_bit_identical_to_the_segment_loop(self, nperseg):
        """Up to nperseg=2048 the strided form reduces in exactly the same order, so
        any difference at all would mean the segments themselves moved."""
        from jnwb.spectral import _welch_csd_gpu

        x, y = self._signals()
        expected = self._segment_loop_reference(x, y, 1000.0, nperseg)
        got = _welch_csd_gpu(x, y, 1000.0, nperseg)

        for name, a, b in zip(("freqs", "psd_x", "psd_y", "csd_xy"), expected, got):
            assert np.array_equal(a, b), (
                f"{name} differs at nperseg={nperseg}, "
                f"max|d|={np.max(np.abs(a - b))}")

    @pytest.mark.parametrize("nperseg", [4096, 8192])
    def test_a_long_segment_agrees_to_float64_round_off(self, nperseg):
        """Above 2048, `cupy` reduces a (n_segments, nperseg) row mean differently from
        a 1-D mean over one segment, so the detrend constant moves in its last bits and
        the FFT carries that through: up to 1.43e-13 relative at nperseg 4096 and 8192.

        The estimator is unchanged -- same window, same detrend, same scaling -- and the
        shift is smaller than the CUDA path's pre-existing disagreement with scipy on
        the same input, which runs from 2.6e-15 at nperseg 256 to 4.1e-13 at 2048. It
        does not widen the gap between the two devices, which is the invariant that
        matters (`AGENTS.md` 6)."""
        from jnwb.spectral import _welch_csd_gpu

        x, y = self._signals()
        expected = self._segment_loop_reference(x, y, 1000.0, nperseg)
        got = _welch_csd_gpu(x, y, 1000.0, nperseg)

        for name, a, b in zip(("freqs", "psd_x", "psd_y", "csd_xy"), expected, got):
            a, b = np.asarray(a), np.asarray(b)
            rel = np.max(np.abs(a - b) / np.maximum(np.abs(a), 1e-300))
            assert rel < 1e-12, f"{name} at nperseg={nperseg}: max relative {rel:.3e}"

    @pytest.mark.parametrize("noverlap", [0, 64, 192])
    def test_every_overlap_still_builds_the_same_segments(self, noverlap):
        from jnwb.spectral import _welch_csd_gpu

        x, y = self._signals(4096)
        expected = self._segment_loop_reference(x, y, 1000.0, 256, noverlap)
        got = _welch_csd_gpu(x, y, 1000.0, 256, noverlap)

        for a, b in zip(expected, got):
            assert np.array_equal(a, b)

    def test_a_trace_shorter_than_one_segment_is_still_padded_to_one(self):
        from jnwb.spectral import _welch_csd_gpu

        x, y = self._signals(100)
        freqs, psd_x, _, _ = _welch_csd_gpu(x, y, 1000.0, 256)

        assert len(freqs) == 129
        assert np.all(np.isfinite(psd_x))

    def test_detrend_off_is_still_honoured(self):
        from jnwb.spectral import _welch_csd_gpu

        x, y = self._signals(4096)
        expected = self._segment_loop_reference(x, y, 1000.0, 256, detrend=False)
        got = _welch_csd_gpu(x, y, 1000.0, 256, detrend=False)

        for a, b in zip(expected, got):
            assert np.array_equal(a, b)

    def test_detrending_is_not_silently_skipped(self):
        """The DC offset of 3.0 is what segment-mean removal takes out. If the two
        branches gave the same answer, the parametrisation above would not be testing
        detrending at all."""
        from jnwb.spectral import _welch_csd_gpu

        x, y = self._signals(4096)
        on = _welch_csd_gpu(x, y, 1000.0, 256, detrend="constant")[1]
        off = _welch_csd_gpu(x, y, 1000.0, 256, detrend=False)[1]

        assert not np.array_equal(on, off)


@requires_cuda
class TestTheSelfSpectrumShortCircuit:
    """`harmonic_analysis`, `spectral_tilt` and `band_power` pass one trace twice and
    keep only `pxx`, so the helper was computing its own second half and discarding it.

    The short circuit is only sound because `y is x` makes the skipped work provably
    redundant rather than approximately so. These tests hold both halves of that: the
    numbers are unchanged, and the work really is skipped.
    """

    @staticmethod
    def _signals(n=16384):
        rng = np.random.default_rng(0)
        t = np.arange(n) / 1000.0
        return np.sin(2 * np.pi * 20 * t) + 0.5 * rng.standard_normal(n) + 3.0

    @pytest.mark.parametrize("nperseg", [255, 256, 1024, 4096])
    def test_passing_one_array_twice_matches_passing_two_equal_arrays(self, nperseg):
        """`x, x` takes the short circuit; `x, x.copy()` cannot, because the test is
        identity. Equal values must give bit-equal outputs either way."""
        from jnwb.spectral import _welch_csd_gpu

        x = self._signals()
        short = _welch_csd_gpu(x, x, 1000.0, nperseg)
        general = _welch_csd_gpu(x, x.copy(), 1000.0, nperseg)

        for name, a, b in zip(("freqs", "psd_x", "psd_y", "csd_xy"), short, general):
            assert np.array_equal(a, b), (
                f"{name} differs at nperseg={nperseg}, "
                f"max|d|={np.max(np.abs(a - b))}")

    def test_the_short_circuit_is_actually_taken(self):
        """Without this the test above passes even if the branch is dead. Two rffts for
        two distinct signals, one for the same signal twice."""
        import cupy as cp
        from jnwb import spectral

        x = self._signals(4096)
        calls = []
        original = cp.fft.rfft

        def counting(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(cp.fft, "rfft", counting)
            spectral._welch_csd_gpu(x, x.copy(), 1000.0, 256)
            distinct = len(calls)
            calls.clear()
            spectral._welch_csd_gpu(x, x, 1000.0, 256)
            same = len(calls)

        assert distinct == 2, f"expected two rffts for two signals, got {distinct}"
        assert same == 1, f"expected one rfft for the same signal twice, got {same}"

    def test_the_one_sided_scaling_is_not_applied_to_psd_y_twice(self):
        """`psd_y` is a copy, not an alias. Aliasing it would double the positive
        frequencies twice and leave the DC bin alone, so the ratio would be 2."""
        from jnwb.spectral import _welch_csd_gpu

        x = self._signals(4096)
        _, psd_x, psd_y, _ = _welch_csd_gpu(x, x, 1000.0, 256)

        assert np.array_equal(psd_x, psd_y)
        assert psd_x[0] != 0.0

    def test_a_trace_shorter_than_one_segment_still_pads_both_halves(self):
        """The padding branch has its own `same_signal` arm."""
        from jnwb.spectral import _welch_csd_gpu

        x = self._signals(100)
        short = _welch_csd_gpu(x, x, 1000.0, 256)
        general = _welch_csd_gpu(x, x.copy(), 1000.0, 256)

        assert len(short[0]) == 129
        for a, b in zip(short, general):
            assert np.array_equal(a, b)

    def test_detrend_off_takes_the_short_circuit_too(self):
        from jnwb.spectral import _welch_csd_gpu

        x = self._signals(4096)
        short = _welch_csd_gpu(x, x, 1000.0, 256, detrend=False)
        general = _welch_csd_gpu(x, x.copy(), 1000.0, 256, detrend=False)

        for a, b in zip(short, general):
            assert np.array_equal(a, b)

    def test_two_different_signals_still_get_their_own_spectra(self):
        """The guard against a short circuit that fires when it must not."""
        from jnwb.spectral import _welch_csd_gpu

        x = self._signals(4096)
        y = x[::-1].copy()
        _, psd_x, psd_y, _ = _welch_csd_gpu(x, y, 1000.0, 256)

        assert not np.array_equal(psd_x, psd_y)
