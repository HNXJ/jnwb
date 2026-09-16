import tempfile
import pathlib
import pytest
import numpy as np
import h5py

import jnwb


def test_compress_fp32_missing_src_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        jnwb.compress_fp32("non_existent_file_path_12345.nwb")


def test_compress_fp32_dst_exists_raises_file_exists(tmp_path):
    src = tmp_path / "test_src.nwb"
    dst = tmp_path / "test_dst.nwb"
    src.write_bytes(b"dummy")
    dst.write_bytes(b"dummy")

    with pytest.raises(FileExistsError):
        jnwb.compress_fp32(src, dst, overwrite=False)


def test_compress_fp32_unrecognized_processing_raises_key_error(tmp_path):
    src = tmp_path / "unrecognized.nwb"
    dst = tmp_path / "unrecognized.fp32.nwb"

    with h5py.File(src, "w") as f:
        proc = f.create_group("processing")
        proc.create_group("unknown_module")

    with pytest.raises(KeyError, match="not found in unrecognized.nwb"):
        jnwb.compress_fp32(src, dst, verify=False, overwrite=True)


def test_compress_fp32_synthetic_hdf5_conversion(tmp_path):
    src = tmp_path / "synthetic.nwb"
    dst = tmp_path / "synthetic.fp32.nwb"

    rng = np.random.default_rng(42)
    n_samples = 1000
    n_channels = 8
    raw_lfp = rng.normal(loc=0.0, scale=50.0, size=(n_samples, n_channels)).astype(np.float64)
    timestamps = np.linspace(0.0, 10.0, n_samples, dtype=np.float64)

    with h5py.File(src, "w") as f:
        # Acquisition group with probe_0_lfp/data
        acq = f.create_group("acquisition")
        p0 = acq.create_group("probe_0_lfp")
        p0.create_dataset("data", data=raw_lfp)
        p0.create_dataset("timestamps", data=timestamps)

        # Processing group with standard spike_train and convolved_spike_train
        proc = f.create_group("processing")
        st_group = proc.create_group("spike_train").create_group("spike_train_data")
        st_group.create_dataset("data", data=rng.integers(0, 5, size=(n_samples, 4), dtype=np.int16))

        conv_group = proc.create_group("convolved_spike_train").create_group("convolved_spike_train_data")
        conv_group.create_dataset("data", data=rng.normal(0, 1, size=(n_samples, 4)).astype(np.float64))

    stats = jnwb.compress_fp32(src, dst, verify=False, overwrite=True)

    assert dst.exists()
    assert stats["src_bytes"] > 0
    assert stats["dst_bytes"] > 0
    assert stats["ratio"] > 0.0

    with h5py.File(dst, "r") as f_dst, h5py.File(src, "r") as f_src:
        dst_lfp = f_dst["acquisition/probe_0_lfp/data"][:]
        src_lfp = f_src["acquisition/probe_0_lfp/data"][:]

        assert dst_lfp.dtype == np.float32
        assert src_lfp.dtype == np.float64

        # Numerical error check (float64 -> float32 precision loss bounded by machine eps)
        abs_err = np.abs(src_lfp - dst_lfp)
        rel_err = abs_err / (np.abs(src_lfp) + 1e-12)
        assert np.max(rel_err) < 1e-6, f"Max relative error {np.max(rel_err)} exceeds float32 bounds"

        # Timestamp collapsing check (regular timestamps collapsed to starting_time dataset + rate attr)
        assert "starting_time" in f_dst["acquisition/probe_0_lfp"]
        assert f_dst["acquisition/probe_0_lfp/starting_time"].attrs["rate"] > 0


class TestTimestampRegularityGate:
    """05-14: `_is_regular` gated on relative jitter, a proxy insensitive to slow drift,
    and then the source timestamps were deleted. The assertion that licenses the deletion
    is the reconstruction error, so that is what must be gated."""

    @staticmethod
    def _drifting(n, base=1e-3, ramp=2e-6):
        """A linearly ramping sample interval: tiny relative jitter, unbounded drift."""
        dt = base * (1.0 + np.linspace(0.0, ramp, n - 1))
        return np.concatenate([[0.0], np.cumsum(dt)])

    @pytest.mark.parametrize("n", [10_000, 100_000, 1_000_000])
    def test_a_drifting_array_is_refused_at_every_length(self, n):
        from jnwb.compression import _is_regular

        ts = self._drifting(n)
        d = np.diff(ts)
        relative_jitter = float(np.std(d) / np.mean(d))
        assert relative_jitter < 1e-6, "the old gate passed this array by construction"

        regular, rate = _is_regular(ts)
        assert not regular, (
            f"N={n}: relative jitter {relative_jitter:.3e} passes the old proxy, but the "
            "reconstruction error does not meet the 1e-6 s bar this function declares"
        )
        assert rate == 0.0

    def test_the_refusal_tracks_the_error_the_function_declares(self):
        from jnwb.compression import _is_regular

        ts = self._drifting(1_000_000)
        regular, _ = _is_regular(ts)
        rate = (len(ts) - 1) / (ts[-1] - ts[0])
        err = float(np.max(np.abs(ts - (ts[0] + np.arange(len(ts)) / rate))))
        assert err > 1e-6
        assert not regular

    @pytest.mark.parametrize("n", [2, 1000, 200_000])
    def test_a_genuinely_regular_array_is_still_collapsed(self, n):
        from jnwb.compression import _is_regular

        ts = np.arange(n) / 1000.0
        regular, rate = _is_regular(ts)
        assert regular
        assert rate == pytest.approx(1000.0)

    def test_degenerate_arrays_are_refused(self):
        from jnwb.compression import _is_regular

        for bad in (np.array([]), np.array([1.0]), np.zeros(10), np.array([0.0, np.nan, 2.0])):
            regular, rate = _is_regular(bad)
            assert not regular and rate == 0.0

    def test_a_blockwise_and_whole_array_gate_agree(self):
        """The check is chunked at 1 << 20; a defect must not hide on a block boundary."""
        from jnwb.compression import _is_regular

        n = (1 << 20) + 5000
        ts = np.arange(n) / 1000.0
        ts[(1 << 20) + 10] += 1e-3  # one displaced sample, past the first block
        regular, _ = _is_regular(ts)
        assert not regular


class TestVerifyRoundtripDoesNotDisableWarnings:
    """05-22: `warnings.filterwarnings("ignore")` at function scope, unscoped and never
    restored, on the default path of `compress_fp32` (`verify: bool = True`)."""

    def test_the_interpreter_warning_filters_survive_a_verify(self, tmp_path):
        import warnings

        from jnwb.compression import verify_roundtrip

        src = tmp_path / "a.h5"
        dst = tmp_path / "b.h5"
        for p in (src, dst):
            with h5py.File(p, "w") as f:
                f.create_dataset("units/id", data=np.arange(3))

        before = list(warnings.filters)
        verify_roundtrip(src, dst)
        assert warnings.filters == before, "verify_roundtrip mutated the global filter state"

    def test_a_warning_still_fires_after_a_verify(self, tmp_path):
        import warnings

        from jnwb.compression import verify_roundtrip

        src = tmp_path / "a.h5"
        dst = tmp_path / "b.h5"
        for p in (src, dst):
            with h5py.File(p, "w") as f:
                f.create_dataset("units/id", data=np.arange(3))

        verify_roundtrip(src, dst)
        with pytest.warns(RuntimeWarning, match="still audible"):
            warnings.warn("still audible", RuntimeWarning)
