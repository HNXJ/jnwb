import io
import tempfile
import tracemalloc
import zipfile
from pathlib import Path

import numpy as np
import pytest

import jnwb
from jnwb.io import stream_npz_array


class TestPublicImports:
    def test_importable_from_top_level(self):
        assert hasattr(jnwb, "stream_npz_array")
        assert jnwb.stream_npz_array is stream_npz_array

    def test_importable_from_submodule(self):
        assert hasattr(jnwb, "io")
        assert hasattr(jnwb.io, "stream_npz_array")
        assert jnwb.io.stream_npz_array is stream_npz_array

    def test_in_all(self):
        assert "stream_npz_array" in jnwb.__all__
        assert "io" in jnwb.__all__


class TestStreamNPZArrayParity:
    @pytest.mark.parametrize("compress", [False, True])
    @pytest.mark.parametrize("order", ["C", "F"])
    @pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int16, np.int32, np.complex64])
    def test_full_load_parity(self, tmp_path: Path, compress: bool, order: str, dtype: np.dtype):
        npz_file = tmp_path / f"test_full_{compress}_{order}_{dtype.__name__}.npz"
        shape = (10, 12, 15)
        raw = np.arange(np.prod(shape), dtype=dtype).reshape(shape)
        arr = np.asfortranarray(raw) if order == "F" else np.ascontiguousarray(raw)

        if compress:
            np.savez_compressed(npz_file, test_data=arr)
        else:
            np.savez(npz_file, test_data=arr)

        with np.load(npz_file) as loaded:
            expected = loaded["test_data"]

        result = stream_npz_array(npz_file, "test_data")
        np.testing.assert_array_equal(result, expected)
        assert result.dtype == arr.dtype
        assert result.shape == arr.shape
        assert result.flags.f_contiguous == (order == "F")
        assert result.flags.c_contiguous == (order == "C")

    @pytest.mark.parametrize("compress", [False, True])
    def test_chunk_boundary_and_sub_slices(self, tmp_path: Path, compress: bool):
        npz_file = tmp_path / f"test_slices_{compress}.npz"
        arr = np.arange(240, dtype=np.float64).reshape(4, 5, 12)
        if compress:
            np.savez_compressed(npz_file, matrix=arr)
        else:
            np.savez(npz_file, matrix=arr)

        s1 = (slice(1, 3), slice(2, 4), slice(3, 10))
        r1 = stream_npz_array(npz_file, "matrix", slice_tuple=s1)
        np.testing.assert_array_equal(r1, arr[s1])

        s2 = (slice(0, 4, 2), slice(1, 5, 2), slice(1, 12, 3))
        r2 = stream_npz_array(npz_file, "matrix", slice_tuple=s2)
        np.testing.assert_array_equal(r2, arr[s2])

        r3 = stream_npz_array(npz_file, "matrix", slice_tuple=(2,))
        np.testing.assert_array_equal(r3, arr[2:3, :, :])

        r4 = stream_npz_array(npz_file, "matrix", slice_tuple=(slice(1, 3),))
        np.testing.assert_array_equal(r4, arr[1:3, :, :])

        r5 = stream_npz_array(npz_file, "matrix", slice_tuple=(slice(2, 2), slice(None)))
        assert r5.shape == (0, 5, 12)
        assert r5.dtype == arr.dtype

    def test_negative_step_slices(self, tmp_path: Path):
        npz_file = tmp_path / "test_negative.npz"
        arr = np.arange(60, dtype=np.float32).reshape(3, 4, 5)
        np.savez_compressed(npz_file, data=arr)

        s = (slice(2, None, -1), slice(None), slice(4, 0, -2))
        res = stream_npz_array(npz_file, "data", slice_tuple=s)
        np.testing.assert_array_equal(res, arr[s])


class TestStreamNPZErrorConditions:
    def test_missing_file_raises_filenotfound(self, tmp_path: Path):
        non_existent = tmp_path / "does_not_exist.npz"
        with pytest.raises(FileNotFoundError, match="NPZ archive not found"):
            stream_npz_array(non_existent, "key")

    def test_missing_key_raises_keyerror(self, tmp_path: Path):
        npz_file = tmp_path / "valid.npz"
        np.savez(npz_file, good_key=np.arange(10))
        with pytest.raises(KeyError, match="not found in archive"):
            stream_npz_array(npz_file, "wrong_key")

    def test_corrupt_archive_raises_valueerror(self, tmp_path: Path):
        corrupt_file = tmp_path / "corrupt.npz"
        corrupt_file.write_bytes(b"PK\x03\x04not_a_valid_zip_archive")
        with pytest.raises(ValueError, match="Corrupt or invalid NPZ archive"):
            stream_npz_array(corrupt_file, "any_key")

    def test_corrupt_stream_bytes_raises_valueerror(self, tmp_path: Path):
        npz_file = tmp_path / "truncated.npz"
        np.savez_compressed(npz_file, data=np.ones((100, 100)))
        raw = npz_file.read_bytes()
        npz_file.write_bytes(raw[: len(raw) // 2])
        with pytest.raises(ValueError, match="corrupt"):
            stream_npz_array(npz_file, "data")

    def test_unsupported_compression_raises_valueerror(self, tmp_path: Path):
        npz_file = tmp_path / "bzip2.npz"
        with zipfile.ZipFile(npz_file, mode="w", compression=zipfile.ZIP_BZIP2) as zf:
            buf = io.BytesIO()
            np.save(buf, np.arange(20))
            zf.writestr("data.npy", buf.getvalue())

        with pytest.raises(ValueError, match="Unsupported compression method"):
            stream_npz_array(npz_file, "data")

    def test_object_dtype_raises_valueerror(self, tmp_path: Path):
        npz_file = tmp_path / "object_dtype.npz"
        arr = np.array([{"alpha": 1}, {"beta": 2}], dtype=object)
        np.savez(npz_file, obj_arr=arr)

        with pytest.raises(ValueError, match="Unsupported array layout: object dtype"):
            stream_npz_array(npz_file, "obj_arr")

    def test_too_many_indices_raises_valueerror(self, tmp_path: Path):
        npz_file = tmp_path / "2d.npz"
        np.savez(npz_file, arr=np.ones((5, 5)))
        with pytest.raises(ValueError, match="Too many indices"):
            stream_npz_array(npz_file, "arr", slice_tuple=(slice(None), slice(None), slice(None)))


class TestStreamNPZMemoryBounded:
    def test_bounded_peak_memory_on_compressed_npz(self, tmp_path: Path):
        npz_file = tmp_path / "large_matrix.npz"
        shape = (2500, 1000)
        arr = np.arange(np.prod(shape), dtype=np.float64).reshape(shape)
        np.savez_compressed(npz_file, large_matrix=arr)

        tracemalloc.start()
        with np.load(npz_file) as loaded:
            full = loaded["large_matrix"]
            _ = full[500:505, :]
        _, full_load_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        tracemalloc.start()
        sliced = stream_npz_array(npz_file, "large_matrix", slice_tuple=(slice(500, 505), slice(None)))
        _, stream_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        np.testing.assert_array_equal(sliced, arr[500:505, :])
        assert stream_peak < full_load_peak / 5
