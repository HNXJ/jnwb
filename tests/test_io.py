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
        np.testing.assert_array_equal(r3, arr[2], strict=True)

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

    def test_too_many_indices_raises_indexerror_as_numpy_does(self, tmp_path: Path):
        npz_file = tmp_path / "2d.npz"
        np.savez(npz_file, arr=np.ones((5, 5)))
        with pytest.raises(IndexError, match="too many indices"):
            stream_npz_array(npz_file, "arr", slice_tuple=(slice(None), slice(None), slice(None)))


NUMPY_SHAPE = (5, 6, 7)

# Indices NumPy accepts, each compared in value, shape and dtype against NumPy itself.
VALID_INDICES = {
    "empty-tuple": (),
    "int-first": (0,),
    "int-last": (-1,),
    "int-positive-last": (4,),
    "slice-then-negative-int": (slice(1, 4), -1),
    "int-slice-int": (2, slice(None), 3),
    "all-ints": (-1, -1, -1),
    "reversed": (slice(None, None, -1),),
    "slice-past-end": (slice(10, 20),),
    "clamped-slice-then-int": (slice(-100, 100), 2),
    "numpy-integer": (np.int64(2),),
    "bare-int": 3,
    "bare-slice": slice(1, 3),
    "reversed-step-then-int": (slice(None), slice(None, None, -2), -7),
    "int-then-reversed": (1, slice(5, 1, -2)),
    "empty-slice-then-int": (slice(2, 2), 3),
}

# Indices NumPy refuses, with the exception NumPy raises for each.
INVALID_INDICES = {
    "int-past-end": ((5,), IndexError),
    "int-before-start": ((-6,), IndexError),
    "too-many": ((0, 0, 0, 0), IndexError),
    "float-in-tuple": ((1.0,), IndexError),
    "int-out-of-range-on-axis-1": ((slice(None), 7), IndexError),
    "bare-float": (1.5, IndexError),
    "zero-step": ((slice(None, None, 0),), ValueError),
}


@pytest.fixture(scope="module")
def numpy_reference_archives(tmp_path_factory):
    """One array, stored and compressed, in C and Fortran order."""
    root = tmp_path_factory.mktemp("numpy_indexing")
    arr = np.arange(np.prod(NUMPY_SHAPE), dtype=np.float64).reshape(NUMPY_SHAPE)
    archives = []
    for order in ("C", "F"):
        data = np.asarray(arr, order=order)
        for save in (np.savez, np.savez_compressed):
            path = root / f"{order}_{save.__name__}.npz"
            save(path, a=data)
            archives.append((path, data))
    return archives


class TestIndexingFollowsNumPy:
    """The result of every index is what NumPy returns for it, including which axes remain.

    The proxy to avoid: comparing values alone. `assert_array_equal` without `strict` broadcasts
    a kept length-1 axis against a dropped one, which is how a kept axis goes unseen.
    """

    @pytest.mark.parametrize("index", list(VALID_INDICES.values()), ids=list(VALID_INDICES))
    def test_the_result_is_what_numpy_returns(self, numpy_reference_archives, index):
        for path, data in numpy_reference_archives:
            got = stream_npz_array(path, "a", slice_tuple=index)
            np.testing.assert_array_equal(got, data[index], strict=True, err_msg=str(path))

    @pytest.mark.parametrize(
        "index, error", list(INVALID_INDICES.values()), ids=list(INVALID_INDICES)
    )
    def test_an_index_numpy_refuses_raises_the_error_numpy_raises(
        self, numpy_reference_archives, index, error
    ):
        _, data = numpy_reference_archives[0]
        with pytest.raises(error):
            data[index]
        for path, _ in numpy_reference_archives:
            with pytest.raises(error):
                stream_npz_array(path, "a", slice_tuple=index)

    @pytest.mark.parametrize(
        "index",
        [(Ellipsis,), (None,), (True,), [1, 2], (np.array([1, 2]),)],
        ids=["ellipsis", "newaxis", "boolean", "list", "integer-array"],
    )
    def test_an_index_kind_it_does_not_stream_is_refused(self, numpy_reference_archives, index):
        """NumPy reads each of these as something other than integers and slices; answering
        with the integer reading would return a different array under the same call."""
        path, _ = numpy_reference_archives[0]
        with pytest.raises(TypeError, match="integers and slices only"):
            stream_npz_array(path, "a", slice_tuple=index)

    def test_a_zero_dimensional_array_reads_as_numpy_reads_it(self, tmp_path: Path):
        path = tmp_path / "scalar.npz"
        np.savez(path, a=np.float32(2.5))
        np.testing.assert_array_equal(
            stream_npz_array(path, "a", slice_tuple=()), np.asarray(np.float32(2.5)), strict=True
        )
        with pytest.raises(IndexError):
            stream_npz_array(path, "a")


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
