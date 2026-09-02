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
