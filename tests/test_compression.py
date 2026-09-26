import importlib
import re
import tempfile
import pathlib
import pytest
import numpy as np
import h5py

import jnwb

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

LFP = "acquisition/probe_0_lfp/data"

# No `assert jnwb.__file__ is under REPO_ROOT` here, deliberately. Import provenance is real --
# a by-path probe silently imports the INSTALLED jnwb from site-packages -- but asserting it in
# this module makes an installed run impossible, and `tests/test_the_suite_can_qualify_an_
# installed_copy.py` enforces that only `tests/test_import_provenance.py` may make that claim,
# because it is the one module that honours JNWB_EXPECTED_PACKAGE_ROOT and so works in both
# modes. REPO_ROOT below is used to resolve stamped provenance strings, not to qualify the
# package under test.


def test_compress_fp32_missing_src_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        jnwb.compress_fp32("non_existent_file_path_12345.nwb", select=[])


def test_compress_fp32_dst_exists_raises_file_exists(tmp_path):
    src = tmp_path / "test_src.nwb"
    dst = tmp_path / "test_dst.nwb"
    src.write_bytes(b"dummy")
    dst.write_bytes(b"dummy")

    with pytest.raises(FileExistsError):
        jnwb.compress_fp32(src, dst, overwrite=False, select=[])


def test_compress_fp32_unrecognized_processing_raises_key_error(tmp_path):
    src = tmp_path / "unrecognized.nwb"
    dst = tmp_path / "unrecognized.fp32.nwb"

    with h5py.File(src, "w") as f:
        proc = f.create_group("processing")
        proc.create_group("unknown_module")

    with pytest.raises(KeyError, match="not found in unrecognized.nwb"):
        jnwb.compress_fp32(src, dst, verify=False, overwrite=True, select=[])


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

    stats = jnwb.compress_fp32(src, dst, verify=False, overwrite=True, select=[LFP])

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
    """`_is_regular` gated on relative jitter, a proxy insensitive to slow drift,
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
    """`warnings.filterwarnings("ignore")` at function scope, unscoped and never
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
        verify_roundtrip(src, dst, collapsed=[], cast=[])
        assert warnings.filters == before, "verify_roundtrip mutated the global filter state"

    def test_a_warning_still_fires_after_a_verify(self, tmp_path):
        import warnings

        from jnwb.compression import verify_roundtrip

        src = tmp_path / "a.h5"
        dst = tmp_path / "b.h5"
        for p in (src, dst):
            with h5py.File(p, "w") as f:
                f.create_dataset("units/id", data=np.arange(3))

        verify_roundtrip(src, dst, collapsed=[], cast=[])
        with pytest.warns(RuntimeWarning, match="still audible"):
            warnings.warn("still audible", RuntimeWarning)

    def test_the_cast_set_is_required(self, tmp_path):
        """A default would verify some other set than the one cast and report it as checked."""
        from jnwb.compression import verify_roundtrip

        with pytest.raises(TypeError, match="cast"):
            verify_roundtrip(tmp_path / "a.h5", tmp_path / "b.h5")


def _cast_pair(tmp_path, src_data, dst_data):
    """A source holding ``src_data`` at LFP and a destination holding ``dst_data`` there."""
    src = tmp_path / "src.h5"
    dst = tmp_path / "dst.h5"
    with h5py.File(src, "w") as f:
        f.create_dataset(LFP, data=src_data)
    with h5py.File(dst, "w") as f:
        f.create_dataset(LFP, data=dst_data)
    return src, dst


def _cast_checks(result):
    return [c for c in result["checks"] if c["name"].startswith(LFP)]


class TestVerifyRoundtripChecksTheCast:
    """A float32 cast is deterministic, so the destination must equal ``source.astype(float32)``.

    An absolute tolerance passes whatever lies inside it: at volt scale a zeroed destination is
    within 1e-3 of every sample, and near 5e4 the float32 spacing is 3.9e-3, so a correct cast
    exceeds it.
    """

    def test_a_zeroed_destination_at_volt_scale_fails(self, tmp_path):
        from jnwb.compression import verify_roundtrip

        raw = np.random.default_rng(5).normal(0.0, 1e-4, size=(500, 3))
        assert np.max(np.abs(raw)) < 1e-3, "the fixture must sit inside the old tolerance"
        src, dst = _cast_pair(tmp_path, raw, np.zeros_like(raw, dtype=np.float32))
        checks = _cast_checks(verify_roundtrip(src, dst, collapsed=[], cast=[LFP]))
        assert len(checks) == 1 and checks[0]["ok"] is False, checks

    def test_a_correct_cast_near_5e4_passes(self, tmp_path):
        from jnwb.compression import verify_roundtrip

        raw = 5e4 + np.random.default_rng(6).uniform(0.0, 1.0, size=(500, 3))
        cast = raw.astype(np.float32)
        assert np.max(np.abs(raw - cast)) > 1e-3, "the fixture must exceed the old tolerance"
        src, dst = _cast_pair(tmp_path, raw, cast)
        checks = _cast_checks(verify_roundtrip(src, dst, collapsed=[], cast=[LFP]))
        assert len(checks) == 1 and checks[0]["ok"] is True, checks

    def test_a_cast_path_absent_from_the_destination_fails(self, tmp_path):
        from jnwb.compression import verify_roundtrip

        raw = np.random.default_rng(7).normal(0.0, 1.0, size=(50, 2))
        src, dst = _cast_pair(tmp_path, raw, raw.astype(np.float32))
        with h5py.File(dst, "a") as f:
            del f[LFP]
        result = verify_roundtrip(src, dst, collapsed=[], cast=[LFP])
        checks = _cast_checks(result)
        assert len(checks) == 1 and checks[0]["ok"] is False, checks
        assert result["ok"] is False

    def test_the_collapsed_set_is_required_and_keyword_only(self, tmp_path):
        """A default checked two hardcoded groups and reported the collapsed arrays as verified."""
        import inspect

        from jnwb.compression import verify_roundtrip

        param = inspect.signature(verify_roundtrip).parameters["collapsed"]
        assert param.default is inspect.Parameter.empty
        assert param.kind is inspect.Parameter.KEYWORD_ONLY
        with pytest.raises(TypeError, match="collapsed"):
            verify_roundtrip(tmp_path / "a.h5", tmp_path / "b.h5", cast=[])


# --------------------------------------------------------------------------------------------
# 06-79 / P-47: the chunk shape must follow the dataset's rank.
# --------------------------------------------------------------------------------------------


def _lfp_only_file(path, shape, dtype=np.float64, seed=0):
    """A file whose only convertible dataset is one LFP array of the given shape.

    `processing/` is omitted entirely, not left empty: convert() distinguishes a legitimately
    absent spike train from an unrecognised convention, and only the absent case proceeds.
    """
    rng = np.random.default_rng(seed)
    with h5py.File(path, "w") as f:
        grp = f.create_group("acquisition").create_group("probe_0_lfp")
        grp.create_dataset("data", data=rng.normal(0.0, 50.0, size=shape).astype(dtype))
    return path


class TestChunkShapeFollowsTheDatasetRank:
    """P-47. All three call sites built `(min(cap, shape[0]), n)` unconditionally, so anything
    that was not rank 2 raised `ValueError: 'chunks' must have same rank as dataset shape`.

    The proxy to avoid: "a 1-D file compresses without raising" passes if the repair hands
    `chunks=None` to h5py, which auto-guesses a chunk shape -- and would silently re-baseline the
    2-D corpus chunking that this item's Stop condition forbids changing. So the rank cases assert
    the chunk shape actually written, and the 2-D case is pinned to the pre-change expression.
    """

    CAP = 16384

    @pytest.mark.parametrize("shape", [(500,), (500, 4), (500, 4, 2), (40000,), (40000, 3)])
    def test_a_dataset_of_any_rank_compresses(self, tmp_path, shape):
        src = _lfp_only_file(tmp_path / "r.nwb", shape)
        dst = tmp_path / "r.fp32.nwb"

        jnwb.compress_fp32(src, dst, verify=False, overwrite=True, select=[LFP])

        with h5py.File(dst, "r") as f:
            ds = f["acquisition/probe_0_lfp/data"]
            assert ds.shape == shape
            assert ds.dtype == np.float32
            assert ds.chunks is not None, "compression requires chunked storage"
            assert len(ds.chunks) == len(shape), (
                f"chunk rank {len(ds.chunks)} does not match dataset rank {len(shape)}"
            )

    @pytest.mark.parametrize("shape", [(1, 1), (500, 4), (16384, 8), (16385, 8), (40000, 3)])
    def test_the_2d_chunk_shape_is_exactly_what_it_was_before(self, shape):
        """The Stop condition on 06-79 is that corpus 2-D chunking must not change at all.

        This is the pre-change expression, verbatim: `n` was `shape[1]` whenever `ndim == 2`,
        so the derived tuple must equal it for every 2-D shape, not merely for one fixture.
        """
        from jnwb.compression import _chunk_shape

        assert _chunk_shape(shape, self.CAP) == (min(self.CAP, shape[0]), shape[1])

    def test_the_first_axis_is_capped_and_the_others_are_kept_whole(self):
        from jnwb.compression import _chunk_shape

        assert _chunk_shape((40000,), self.CAP) == (self.CAP,)
        assert _chunk_shape((500,), self.CAP) == (500,)
        assert _chunk_shape((40000, 4, 2), self.CAP) == (self.CAP, 4, 2)

    def test_a_scalar_dataset_is_refused_with_a_reason(self):
        """Rank 0 has no chunk shape, and gzip+shuffle cannot apply to unchunked storage.
        Failing here names the cause; letting it through produces h5py's own opaque message."""
        from jnwb.compression import _chunk_shape

        with pytest.raises(ValueError, match="rank-0"):
            _chunk_shape((), self.CAP)

    # P-47 names THREE call sites -- LFP, spike_train and convolved_spike_train. A mutation run
    # showed the tests above cover only the LFP one: reverting either of the other two to the
    # rank-2 tuple was not caught, because no fixture gave those datasets a rank but 2.
    ALL_THREE = [
        "acquisition/probe_0_lfp/data",
        "processing/spike_train/spike_train_data/data",
        "processing/convolved_spike_train/convolved_spike_train_data/data",
    ]

    @pytest.mark.parametrize("shape", [(300,), (300, 2, 2)])
    def test_every_call_site_follows_the_rank(self, tmp_path, shape):
        rng = np.random.default_rng(5)
        src = tmp_path / "three.nwb"
        dst = tmp_path / "three.fp32.nwb"
        with h5py.File(src, "w") as f:
            for path in self.ALL_THREE:
                f.create_dataset(path, data=rng.normal(0, 1, size=shape).astype(np.float64))

        jnwb.compress_fp32(src, dst, verify=False, overwrite=True, select=[LFP])

        with h5py.File(dst, "r") as f:
            for path in self.ALL_THREE:
                ds = f[path]
                assert ds.shape == shape, path
                assert ds.chunks is not None, path
                assert len(ds.chunks) == len(shape), (
                    f"{path}: chunk rank {len(ds.chunks)} != dataset rank {len(shape)}"
                )

    def test_the_2d_data_survives_the_roundtrip_unchanged_in_value(self, tmp_path):
        """Deriving the chunk shape must not disturb what is written, only how it is stored."""
        src = _lfp_only_file(tmp_path / "v.nwb", (2000, 6), seed=7)
        dst = tmp_path / "v.fp32.nwb"

        jnwb.compress_fp32(src, dst, verify=False, overwrite=True, select=[LFP])

        with h5py.File(src, "r") as s, h5py.File(dst, "r") as d:
            expected = s["acquisition/probe_0_lfp/data"][:].astype(np.float32)
            assert np.array_equal(d["acquisition/probe_0_lfp/data"][:], expected)


# --------------------------------------------------------------------------------------------
# 06-78 / P-48: the preserved series needs a dtype test before anything can claim it survives.
# --------------------------------------------------------------------------------------------


def _file_with_convolved(path, conv_dtype, n=200, n_units=4, seed=3):
    rng = np.random.default_rng(seed)
    with h5py.File(path, "w") as f:
        f.create_group("acquisition").create_group("probe_0_lfp").create_dataset(
            "data", data=rng.normal(0.0, 50.0, size=(n, 2)).astype(np.float64)
        )
        f.create_dataset(
            "processing/spike_train/spike_train_data/data",
            data=rng.integers(0, 5, size=(n, n_units), dtype=np.int16),
        )
        f.create_dataset(
            "processing/convolved_spike_train/convolved_spike_train_data/data",
            data=(rng.normal(0.0, 1.0, size=(n, n_units))).astype(conv_dtype),
        )
    return path


class TestConvolvedSpikeTrainIsPreservedExactly:
    """P-48. `convolved_spike_train` appeared twice in this file, both times in fixture
    construction, with nothing asserted about it. Three candidate policies downcast it while
    passing all 15 tests, so "the contract survives" was a claim about an unenforced rule.

    The contract, from module docstring point 7 and from `convert()` passing `src_ds.dtype`
    straight through: the array is recompressed IN PLACE with the data fully intact. The required
    dtype is therefore the source's own, whatever that is -- not a fixed type.

    The proxy to avoid: `assert dst.dtype == np.float64` passes if the code hardcodes float64,
    and it would keep passing while a float32 source was silently promoted. So the dtype cases are
    parametrised and each asserts preservation of *its own* input dtype.
    """

    @pytest.mark.parametrize("conv_dtype", [np.float64, np.float32, np.int16])
    def test_the_dtype_is_the_source_dtype(self, tmp_path, conv_dtype):
        from jnwb.compression import CONVOLVED_PATH

        src = _file_with_convolved(tmp_path / "c.nwb", conv_dtype)
        dst = tmp_path / "c.fp32.nwb"

        jnwb.compress_fp32(src, dst, verify=False, overwrite=True, select=[LFP])

        with h5py.File(src, "r") as s, h5py.File(dst, "r") as d:
            assert d[CONVOLVED_PATH].dtype == s[CONVOLVED_PATH].dtype == np.dtype(conv_dtype), (
                f"convolved_spike_train was written as {d[CONVOLVED_PATH].dtype}, but the "
                f"contract preserves the source dtype {np.dtype(conv_dtype)}"
            )

    @pytest.mark.parametrize("conv_dtype", [np.float64, np.float32, np.int16])
    def test_every_value_is_bit_identical(self, tmp_path, conv_dtype):
        """Recompression is lossless by contract: "smaller on disk, nothing lost". A dtype
        assertion alone would pass a policy that kept the dtype and perturbed the values."""
        from jnwb.compression import CONVOLVED_PATH

        src = _file_with_convolved(tmp_path / "c.nwb", conv_dtype)
        dst = tmp_path / "c.fp32.nwb"

        jnwb.compress_fp32(src, dst, verify=False, overwrite=True, select=[LFP])

        with h5py.File(src, "r") as s, h5py.File(dst, "r") as d:
            assert np.array_equal(s[CONVOLVED_PATH][:], d[CONVOLVED_PATH][:])

    def test_the_spike_train_counts_keep_their_integer_dtype(self, tmp_path):
        """The same unenforced-contract shape one dataset over: `spike_train` is int16 counts,
        and a float32 policy that reached it would be silent data conversion."""
        from jnwb.compression import SPIKE_TRAIN_PATH

        src = _file_with_convolved(tmp_path / "c.nwb", np.float64)
        dst = tmp_path / "c.fp32.nwb"

        jnwb.compress_fp32(src, dst, verify=False, overwrite=True, select=[LFP])

        with h5py.File(src, "r") as s, h5py.File(dst, "r") as d:
            assert d[SPIKE_TRAIN_PATH].dtype == s[SPIKE_TRAIN_PATH].dtype == np.int16
            assert np.array_equal(s[SPIKE_TRAIN_PATH][:], d[SPIKE_TRAIN_PATH][:])


# --------------------------------------------------------------------------------------------
# 06-65 / P-29: the corpus pattern must select the group it names, not any path ending in it.
# --------------------------------------------------------------------------------------------


class TestTheSelectorIsAnchored:
    """P-29. An unanchored `.search()` selected 6 of 6 adversarial names for the IRREVERSIBLE
    float32 downcast, including a path under `scratch/`.

    The proxy to avoid: "none of the six is selected" passes for a selector that selects nothing
    at all. Both halves are asserted in every direction -- the six are rejected AND the corpus
    paths are still chosen, in the same file, from one call.
    """

    ADVERSARIAL = [
        "stimulus/probe_0_lfp/data",
        "analysis/probe_0_lfp/data",
        "scratch/backup_probe_0_lfp/data",
        "acquisition/my_probe_0_lfp/data",
        "general/extra/probe_0_lfp/data",
        "scratch/probe_0_muae/data",
        # Beyond the six recorded in P-29. A mutation run showed the six above are all rejected
        # by the literal `acquisition/` text alone, so they pass a selector that is not actually
        # anchored -- they could not tell `fullmatch` from `search`. These three can: each embeds
        # the exact corpus path inside a longer one, at the head or the tail.
        "scratch/acquisition/probe_0_lfp/data",
        "my_acquisition/probe_0_lfp/data",
        "acquisition/probe_0_lfp/datastore",
    ]
    CORPUS = [
        "acquisition/probe_0_lfp/data",
        "acquisition/probe_1_muae/data",
        "acquisition/probe_0_lfp/probe_0_lfp_data/data",
    ]

    @pytest.fixture
    def selected(self, tmp_path):
        from jnwb.compression import _find_lfp_muae_paths

        path = tmp_path / "sel.nwb"
        with h5py.File(path, "w") as f:
            for p in self.ADVERSARIAL + self.CORPUS:
                f.create_dataset(p, data=np.zeros((8, 2), dtype=np.float64))
        with h5py.File(path, "r") as f:
            return set(_find_lfp_muae_paths(f))

    @pytest.mark.parametrize("path", ADVERSARIAL)
    def test_a_path_outside_the_named_group_is_rejected(self, selected, path):
        assert "/" + path not in selected, (
            f"{path} is selected for an irreversible float32 downcast, but it is not the group "
            "the corpus pattern names"
        )

    @pytest.mark.parametrize("path", CORPUS)
    def test_the_corpus_paths_are_still_selected(self, selected, path):
        assert "/" + path in selected, (
            f"{path} stopped being selected; anchoring must not change the corpus selection"
        )

    def test_the_selector_selects_exactly_the_corpus_set(self, selected):
        assert selected == {"/" + p for p in self.CORPUS}

    def test_a_renamed_acquisition_group_is_not_reached_by_a_tail_match(self, tmp_path):
        """`my_probe_0_lfp` is the specific shape of the defect: the corpus name as the TAIL of a
        longer segment, in the right parent group. A head anchor alone would not reject it."""
        from jnwb.compression import _find_lfp_muae_paths

        path = tmp_path / "tail.nwb"
        with h5py.File(path, "w") as f:
            f.create_dataset("acquisition/my_probe_0_lfp/data", data=np.zeros((4, 2)))
            f.create_dataset("acquisition/probe_0_lfp_extra/data", data=np.zeros((4, 2)))
        with h5py.File(path, "r") as f:
            assert _find_lfp_muae_paths(f) == []

    def test_an_adversarial_file_writes_its_non_corpus_arrays_through_untouched(self, tmp_path):
        """End to end, not just the selector: the float64 array under `scratch/` must still be
        float64 in the output, because selection is what licenses the cast."""
        src = tmp_path / "adv.nwb"
        dst = tmp_path / "adv.fp32.nwb"
        rng = np.random.default_rng(11)
        with h5py.File(src, "w") as f:
            f.create_dataset("acquisition/probe_0_lfp/data",
                             data=rng.normal(0, 50, size=(300, 4)).astype(np.float64))
            f.create_dataset("scratch/backup_probe_0_lfp/data",
                             data=rng.normal(0, 50, size=(300, 4)).astype(np.float64))

        jnwb.compress_fp32(src, dst, verify=False, overwrite=True, select=[LFP])

        with h5py.File(src, "r") as s, h5py.File(dst, "r") as d:
            assert d["acquisition/probe_0_lfp/data"].dtype == np.float32
            assert d["scratch/backup_probe_0_lfp/data"].dtype == np.float64
            assert np.array_equal(s["scratch/backup_probe_0_lfp/data"][:],
                                  d["scratch/backup_probe_0_lfp/data"][:])


# --------------------------------------------------------------------------------------------
# 06-66 / P-30: the provenance stamp must name something that exists.
# --------------------------------------------------------------------------------------------

_DOTTED = re.compile(r"^[A-Za-z_][\w.]*$")
_SCRIPT_LIKE = re.compile(r"[\w./\\-]+\.py\b")


def _resolves_in_this_tree(value: str) -> bool:
    """Does `value` name something a reader of a converted file could actually reach?

    Two admissible forms: a repository-relative file path, resolved against the tree, and a
    dotted attribute path, resolved by importing the longest importable prefix and walking the
    rest. Anything else does not resolve. This is the check whose ABSENCE let P-30 survive a
    release -- nothing ever resolved the stamp.
    """
    value = value.strip()
    if not value:
        return False
    if "/" in value or "\\" in value or value.endswith(".py"):
        return (REPO_ROOT / value).exists()
    if not _DOTTED.match(value):
        return False
    parts = value.split(".")
    for i in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:i]))
        except ImportError:
            continue
        for attr in parts[i:]:
            if not hasattr(obj, attr):
                return False
            obj = getattr(obj, attr)
        return True
    return False


class TestTheResolverDiscriminates:
    """Establish that the check can fail before trusting it to pass. A resolver that returned
    True unconditionally would make every test below vacuous."""

    def test_the_stamp_this_item_exists_to_remove_does_not_resolve(self):
        assert not _resolves_in_this_tree("scripts/convert_nwb_compressed.py")

    def test_a_missing_dotted_attribute_does_not_resolve(self):
        assert not _resolves_in_this_tree("jnwb.no_such_entry_point_12345")

    def test_a_missing_module_does_not_resolve(self):
        assert not _resolves_in_this_tree("no_such_module_12345.thing")

    def test_a_real_file_and_a_real_attribute_both_resolve(self):
        # This module's own repo-relative path, so the positive case holds wherever the suite
        # runs from rather than assuming a `scripts/` directory sits beside it.
        own = pathlib.Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()
        assert _resolves_in_this_tree(own)
        assert _resolves_in_this_tree("jnwb.compress_fp32")


class TestWrittenProvenanceResolves:
    """P-30. 22 of 22 real sessions stamp a script that is not in the repository, and newly
    written files still minted it.

    The proxy to avoid, twice over. (1) `assert stamp == "jnwb.compress_fp32"` pins a spelling,
    not the property -- it would pass unchanged after the entry point was renamed away. So the
    stamp is resolved, not compared. (2) Checking only `conversion_script` passes while the
    per-dataset `stored_dtype_note` still names the dead script, which it did: fixing one attr
    and leaving the other is a partial repair that a single-attr check cannot see. So every
    string attribute in the written file is swept.
    """

    @pytest.fixture
    def written(self, tmp_path):
        src = _file_with_convolved(tmp_path / "prov.nwb", np.float64)
        dst = tmp_path / "prov.fp32.nwb"
        jnwb.compress_fp32(src, dst, verify=False, overwrite=True, select=[LFP])
        return dst

    def test_the_conversion_script_stamp_resolves(self, written):
        with h5py.File(written, "r") as f:
            stamp = f.attrs["conversion_script"]
        assert _resolves_in_this_tree(str(stamp)), (
            f"conversion_script = {stamp!r} does not resolve against this tree; provenance "
            "sends the reader somewhere that does not exist"
        )

    def test_the_stamp_names_a_callable_entry_point(self, written):
        with h5py.File(written, "r") as f:
            stamp = str(f.attrs["conversion_script"])
        module_name, _, attr = stamp.rpartition(".")
        entry = getattr(importlib.import_module(module_name), attr)
        assert callable(entry)
        assert entry is jnwb.compress_fp32

    def test_no_stamped_string_names_a_script_that_is_absent(self, written):
        """The sweep that makes a partial repair visible: every `.py` token in every string
        attribute, anywhere in the file, must resolve."""
        offenders = []

        def check(where, attrs):
            for key, value in attrs.items():
                if not isinstance(value, (str, bytes, np.bytes_, np.str_)):
                    continue
                text = value.decode() if isinstance(value, (bytes, np.bytes_)) else str(value)
                for token in _SCRIPT_LIKE.findall(text):
                    if not _resolves_in_this_tree(token):
                        offenders.append(f"{where}:{key} -> {token}")

        with h5py.File(written, "r") as f:
            check("/", f.attrs)
            f.visititems(lambda name, obj: check(name, obj.attrs))

        assert offenders == [], f"provenance names scripts that do not exist: {offenders}"

    def test_the_per_dataset_note_names_the_same_entry_point(self, written):
        """Binds the two stamps together so they cannot drift apart again."""
        with h5py.File(written, "r") as f:
            stamp = str(f.attrs["conversion_script"])
            note = str(f["acquisition/probe_0_lfp/data"].attrs["stored_dtype_note"])
        assert stamp in note, f"stored_dtype_note does not name {stamp}: {note!r}"

    def test_the_stamped_version_is_the_version_of_what_the_stamp_names(self, written):
        with h5py.File(written, "r") as f:
            version = str(f.attrs["conversion_script_version"])
        assert version == jnwb.__version__


# --------------------------------------------------------------------------------------------
# The float32 cast is selected by the caller: `select=` names the datasets to cast.
# --------------------------------------------------------------------------------------------

PRESET = ["acquisition/probe_0_lfp/data", "acquisition/probe_1_muae/probe_1_muae_data/data"]
OTHER = "scratch/extra/data"
COUNTS = "scratch/counts/data"
MASK = "scratch/mask/data"
HALF = "scratch/half/data"


def _selectable_file(path, seed=13):
    """The two preset shapes, both guarded datasets, and arrays outside the preset: two
    floating (float64, float16), one integer, one boolean and one string."""
    from jnwb.compression import CONVOLVED_PATH, SPIKE_TRAIN_PATH

    rng = np.random.default_rng(seed)
    with h5py.File(path, "w") as f:
        f.create_dataset(PRESET[0], data=rng.normal(0.0, 50.0, size=(400, 3)))
        f.create_dataset(PRESET[1], data=rng.normal(0.0, 5.0, size=(400, 2)))
        f.create_dataset(OTHER, data=rng.normal(0.0, 1.0, size=(400, 2)))
        f.create_dataset(COUNTS, data=rng.integers(0, 9, size=(400, 2), dtype=np.int16))
        f.create_dataset("scratch/labels", data=np.array([b"a", b"b"]))
        f.create_dataset(SPIKE_TRAIN_PATH, data=rng.integers(0, 5, size=(400, 4), dtype=np.int16))
        f.create_dataset(CONVOLVED_PATH, data=rng.normal(0.0, 1.0, size=(400, 4)))
        f.create_dataset(MASK, data=rng.integers(0, 2, size=(400, 2)).astype(bool))
        f.create_dataset(HALF, data=rng.normal(0.0, 1.0, size=(400, 2)).astype(np.float16))
    return path


def _cast_notes(path):
    """{dataset path: dtype} for every dataset that carries a cast note."""
    out = {}
    with h5py.File(path, "r") as f:
        f.visititems(
            lambda name, obj: out.__setitem__(name, obj.dtype)
            if isinstance(obj, h5py.Dataset) and "stored_dtype_note" in obj.attrs
            else None
        )
    return out


class TestTheSelectionIsExplicit:
    """A call that names no selection raises before anything is written; `select=` casts exactly
    the paths it names; a path the conversion rewrites at its source dtype afterwards is refused.

    The proxy to avoid: "the output has a float32 dataset with a cast note" passes while the note
    sits on a dataset that was restored to float64 -- the false receipt this repair removes. So the
    note is swept over the whole file and every note-bearing dataset must actually be float32.
    """

    @pytest.fixture
    def src(self, tmp_path):
        return _selectable_file(tmp_path / "sel.nwb")

    @pytest.fixture(autouse=True)
    def _fixed_date(self, monkeypatch):
        # The stamps carry the date; pinning it keeps two conversions comparable in bytes even
        # across midnight.
        from jnwb import compression

        monkeypatch.setattr(compression.time, "strftime", lambda fmt, *a: "2000-01-01")

    @pytest.mark.parametrize("how", ["omitted", "None"])
    @pytest.mark.parametrize("entry", ["compress_fp32", "convert"])
    def test_a_call_without_select_raises_before_anything_is_written(
        self, src, tmp_path, how, entry
    ):
        """What would pass while the rule is broken: a raise after the destination directory or
        the temporary file exists, or a raise that does not name the parameter. So the output
        sits in a directory that does not exist yet, and nothing may appear under `tmp_path`."""
        from jnwb.compression import convert

        before = sorted(tmp_path.rglob("*"))
        out = tmp_path / "out" / "none.nwb"
        kwargs = {} if how == "omitted" else {"select": None}
        with pytest.raises(TypeError, match="select"):
            if entry == "convert":
                convert(src, out, **kwargs)
            else:
                jnwb.compress_fp32(src, out, verify=False, **kwargs)
        assert sorted(tmp_path.rglob("*")) == before

    def test_select_has_no_default(self):
        import inspect

        from jnwb.compression import convert

        for fn in (jnwb.compress_fp32, convert):
            param = inspect.signature(fn).parameters["select"]
            assert param.default is inspect.Parameter.empty, fn.__name__
            assert param.kind is inspect.Parameter.KEYWORD_ONLY, fn.__name__

    def test_the_refusal_names_a_route_for_an_integer_lfp(self, tmp_path):
        """An int16 LFP cannot be cast, so the advice given for `select=None` must not be to name
        it; `select=[]` compresses the file and leaves the array at its source dtype and values."""
        src = _lfp_only_file(tmp_path / "i.nwb", (300, 2))
        with h5py.File(src, "a") as f:
            del f[LFP]
            f.create_dataset(LFP, data=np.arange(600, dtype=np.int16).reshape(300, 2))
        with pytest.raises(TypeError, match=r"select=\[\] to cast nothing"):
            jnwb.compress_fp32(src, tmp_path / "i.fp32.nwb", verify=False, select=None)
        stats = jnwb.compress_fp32(src, tmp_path / "i.fp32.nwb", verify=False, select=[])
        assert stats["cast_paths"] == []
        with h5py.File(src, "r") as s, h5py.File(tmp_path / "i.fp32.nwb", "r") as d:
            assert d[LFP].dtype == np.int16
            assert np.array_equal(s[LFP][:], d[LFP][:])

    def test_select_casts_exactly_what_it_names(self, src, tmp_path):
        dst = tmp_path / "other.nwb"
        stats = jnwb.compress_fp32(src, dst, verify=False, select=["/" + OTHER])
        assert stats["cast_paths"] == ["/" + OTHER]
        assert _cast_notes(dst) == {OTHER: np.dtype(np.float32)}
        with h5py.File(src, "r") as s, h5py.File(dst, "r") as d:
            for path in PRESET:
                assert d[path].dtype == np.float64, f"{path} was cast without being named"
                assert np.array_equal(s[path][:], d[path][:])

    def test_an_empty_selection_casts_nothing_and_does_not_warn(self, src, tmp_path):
        import warnings

        dst = tmp_path / "none.nwb"
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            jnwb.compress_fp32(src, dst, verify=False, select=[])
        assert _cast_notes(dst) == {}

    @pytest.mark.parametrize("which", ["spike_train", "convolved"])
    @pytest.mark.parametrize("drop_convolved", [False, True])
    def test_a_guarded_path_is_refused_before_anything_is_written(
        self, src, tmp_path, which, drop_convolved
    ):
        from jnwb.compression import CONVOLVED_PATH, SPIKE_TRAIN_PATH

        guarded = SPIKE_TRAIN_PATH if which == "spike_train" else CONVOLVED_PATH
        dst = tmp_path / "guarded.nwb"
        with pytest.raises(ValueError, match="source dtype"):
            jnwb.compress_fp32(src, dst, verify=False, select=[PRESET[0], guarded],
                               drop_convolved=drop_convolved)
        assert list(tmp_path.glob("guarded*")) == []

    @pytest.mark.parametrize(
        "select, error",
        [
            (["scratch/absent/data"], KeyError),
            (["scratch/extra"], TypeError),
            (["scratch/labels"], TypeError),
            (PRESET[0], TypeError),
        ],
        ids=["absent", "group", "string-dtype", "bare-string"],
    )
    def test_a_selection_that_cannot_be_cast_is_refused(self, src, tmp_path, select, error):
        with pytest.raises(error, match="select="):
            jnwb.compress_fp32(src, tmp_path / "bad.nwb", verify=False, select=select)

    @pytest.mark.parametrize(
        "select, error",
        [(["scratch/absent/data"], KeyError), ([COUNTS], TypeError), (5, TypeError)],
        ids=["absent", "integer", "not-iterable"],
    )
    def test_a_refused_selection_creates_no_directory(self, src, tmp_path, select, error):
        """What would pass while the rule is broken: the raise itself. The destination directory
        does not exist yet, so a refusal after it is created leaves it behind."""
        before = sorted(tmp_path.rglob("*"))
        with pytest.raises(error):
            jnwb.compress_fp32(src, tmp_path / "new" / "bad.nwb", verify=False, select=select)
        assert sorted(tmp_path.rglob("*")) == before

    @pytest.mark.parametrize("path", [COUNTS, MASK], ids=["integer", "boolean"])
    @pytest.mark.parametrize("entry", ["compress_fp32", "convert"])
    def test_a_non_floating_dataset_is_refused_before_anything_is_written(
        self, src, tmp_path, path, entry
    ):
        from jnwb.compression import convert

        dst = tmp_path / "bad.nwb"
        with pytest.raises(TypeError, match="select= casts floating-point datasets only"):
            if entry == "convert":
                convert(src, dst, select=[OTHER, path])
            else:
                jnwb.compress_fp32(src, dst, verify=False, select=[OTHER, path])
        assert list(tmp_path.glob("bad*")) == []

    def test_the_note_names_the_dtype_that_was_cast(self, src, tmp_path):
        dst = tmp_path / "half.nwb"
        jnwb.compress_fp32(src, dst, verify=False, select=[HALF, OTHER])
        with h5py.File(dst, "r") as d:
            assert str(d[HALF].attrs["stored_dtype_note"]).startswith("cast from float16 to float32")
            assert str(d[OTHER].attrs["stored_dtype_note"]).startswith("cast from float64 to float32")

    def test_every_cast_note_sits_on_a_float32_dataset(self, src, tmp_path):
        for i, select in enumerate([PRESET, [OTHER, HALF]]):
            dst = tmp_path / f"sweep{i}.nwb"
            jnwb.compress_fp32(src, dst, verify=False, select=select)
            notes = _cast_notes(dst)
            assert notes, "the sweep must see at least one note to mean anything"
            assert all(dt == np.float32 for dt in notes.values()), notes

    def test_verification_checks_the_datasets_that_were_cast(self, src, tmp_path):
        stats = jnwb.compress_fp32(src, tmp_path / "v.nwb", select=[OTHER])
        names = [c["name"] for c in stats["verification"]["checks"]]
        assert any(n.startswith("/" + OTHER) for n in names), names
        assert not any(n.startswith("/" + p) for p in PRESET for n in names), names

    def test_convert_takes_the_same_selection(self, src, tmp_path):
        from jnwb.compression import convert

        stats = convert(src, tmp_path / "c2.nwb", select=[OTHER])
        assert stats["cast_paths"] == ["/" + OTHER]
        with pytest.raises(ValueError, match="source dtype"):
            from jnwb.compression import CONVOLVED_PATH

            convert(src, tmp_path / "c3.nwb", select=[CONVOLVED_PATH])


REGULAR_TS = "acquisition/regular/timestamps"
REDUNDANT_TS = "acquisition/redundant/timestamps"
IRREGULAR_TS = "acquisition/irregular/timestamps"
SCALAR = "scratch/scalar"


def _file_with_timestamps(path, n=400):
    """`_selectable_file` plus three timestamps arrays the conversion treats differently -- one
    it collapses, one it drops beside a matching `starting_time`, one it keeps -- and a scalar
    float dataset."""
    _selectable_file(path)
    rng = np.random.default_rng(5)
    with h5py.File(path, "a") as f:
        f.create_dataset(REGULAR_TS, data=np.arange(n) / 1000.0)
        f.create_dataset(REDUNDANT_TS, data=2.0 + np.arange(n) / 500.0)
        start = f["acquisition/redundant"].create_dataset("starting_time", data=2.0)
        start.attrs["rate"] = 500.0
        f.create_dataset(IRREGULAR_TS, data=np.sort(rng.uniform(0.0, 1.0, n)))
        f.create_dataset(SCALAR, data=np.float64(1.5))
    return path


class TestASelectionTheConversionDropsIsRefused:
    """`select=` naming a dataset absent from the output, or one that cannot be cast, is refused
    before anything is written, like the guarded paths.

    The proxy to avoid: the call raising at all. A raise after the temporary file is created
    leaves `*.bloated.tmp.nwb` behind, so every refusal also asserts the directory is empty; and
    the kept timestamps array must still be castable, or refusing every `timestamps` would pass.
    """

    @pytest.fixture
    def src(self, tmp_path):
        return _file_with_timestamps(tmp_path / "ts.nwb")

    @pytest.mark.parametrize("path", [REGULAR_TS, REDUNDANT_TS], ids=["collapsed", "redundant"])
    @pytest.mark.parametrize("entry", ["compress_fp32", "convert"])
    def test_a_timestamps_array_the_conversion_drops_is_refused(self, src, tmp_path, path, entry):
        from jnwb.compression import convert

        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError, match="starting_time and rate"):
            if entry == "convert":
                convert(src, out / "bad.nwb", select=[OTHER, path])
            else:
                jnwb.compress_fp32(src, out / "bad.nwb", verify=False, select=[OTHER, path])
        assert list(out.iterdir()) == []

    def test_without_the_selection_both_arrays_are_absent_from_the_output(self, src, tmp_path):
        """The premise of the refusal: the conversion does drop both arrays."""
        dst = tmp_path / "plain.nwb"
        stats = jnwb.compress_fp32(src, dst, verify=False, select=[OTHER])
        with h5py.File(dst, "r") as d:
            assert REGULAR_TS not in d and REDUNDANT_TS not in d
            assert IRREGULAR_TS in d
        assert [p for p, _ in stats["timestamps_collapsed"]] == [REGULAR_TS]
        assert [p for p, _ in stats["timestamps_redundant_dropped"]] == [REDUNDANT_TS]

    def test_a_kept_timestamps_array_is_still_cast(self, src, tmp_path):
        dst = tmp_path / "kept.nwb"
        stats = jnwb.compress_fp32(src, dst, verify=False, select=[IRREGULAR_TS])
        assert stats["cast_paths"] == ["/" + IRREGULAR_TS]
        assert _cast_notes(dst) == {IRREGULAR_TS: np.dtype(np.float32)}

    @pytest.mark.parametrize("entry", ["compress_fp32", "convert"])
    def test_a_scalar_dataset_is_refused_before_anything_is_written(self, src, tmp_path, entry):
        from jnwb.compression import convert

        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError, match="select= names scratch/scalar, a scalar"):
            if entry == "convert":
                convert(src, out / "bad.nwb", select=[SCALAR])
            else:
                jnwb.compress_fp32(src, out / "bad.nwb", verify=False, select=[SCALAR])
        assert list(out.iterdir()) == []


def _respell(path, how):
    """Another spelling HDF5 resolves to the same object as ``path``."""
    head, _, tail = path.partition("/")
    return {"double": f"{head}//{tail}", "dot": f"{head}/./{tail}", "trailing": path + "/"}[how]


SPELLINGS = ["double", "dot", "trailing"]


class TestASelectionIsResolvedBeforeItIsCompared:
    """Every `select=` entry is compared as the object HDF5 resolves it to, not as the string the
    caller typed.

    The proxy to avoid: guards that hold for the one spelling each test types. A guarded path
    written `a//b` or `a/./b` used to pass the guard and stamp a float32 cast note on a dataset
    that stayed float64, and a trailing `/` raised only after the temporary file existed. So each
    refusal runs under every spelling and asserts the output directory is empty, and a respelled
    castable path must be cast exactly once under its own name.
    """

    @pytest.fixture
    def src(self, tmp_path):
        return _file_with_timestamps(tmp_path / "ts.nwb")

    @pytest.mark.parametrize("how", SPELLINGS)
    def test_a_respelled_guarded_path_is_refused_before_anything_is_written(
        self, src, tmp_path, how
    ):
        # `convolved_spike_train` is float64 here, so only the guard can refuse it; the integer
        # `spike_train` would also be refused by the dtype check and could not tell them apart.
        from jnwb.compression import CONVOLVED_PATH

        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError, match="source dtype"):
            jnwb.compress_fp32(src, out / "bad.nwb", verify=False,
                               select=[OTHER, _respell(CONVOLVED_PATH, how)])
        assert list(out.iterdir()) == []

    @pytest.mark.parametrize("how", SPELLINGS)
    def test_a_respelled_dropped_timestamps_array_is_refused(self, src, tmp_path, how):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError, match="starting_time and rate"):
            jnwb.compress_fp32(src, out / "bad.nwb", verify=False,
                               select=[OTHER, _respell(REGULAR_TS, how)])
        assert list(out.iterdir()) == []

    @pytest.mark.parametrize("how", SPELLINGS)
    def test_a_respelled_castable_path_is_cast_once_under_its_own_name(self, src, tmp_path, how):
        dst = tmp_path / "cast.nwb"
        stats = jnwb.compress_fp32(src, dst, verify=False, select=[OTHER, _respell(OTHER, how)])
        assert stats["cast_paths"] == ["/" + OTHER]
        assert _cast_notes(dst) == {OTHER: np.dtype(np.float32)}
        assert list(tmp_path.glob("*.tmp*")) == []


def _file_with_aliases(path):
    """`_file_with_timestamps` plus a hard and a soft link to `convolved_spike_train`, to the
    regular timestamps array and to a castable array, each under a name of its own."""
    from jnwb.compression import CONVOLVED_PATH

    _file_with_timestamps(path)
    with h5py.File(path, "a") as f:
        for target, stem in ((CONVOLVED_PATH, "conv"), (REGULAR_TS, "ts"), (OTHER, "other")):
            f[f"aliases/hard_{stem}"] = f[target]
            f[f"aliases/soft_{stem}"] = h5py.SoftLink("/" + target)
    return path


class TestALinkAliasIsTheDatasetItNames:
    """A hard or soft link names the same object as its target, so it meets the target's refusal.

    The proxy to avoid: a fixture whose links do not resolve to the target, which would let a
    guard on names alone pass. Each test first asserts the alias is the link kind it is named
    after and compares equal to its target; a castable alias must still be cast, or refusing
    every link would pass.
    """

    @pytest.fixture
    def src(self, tmp_path):
        return _file_with_aliases(tmp_path / "alias.nwb")

    @staticmethod
    def _assert_alias(src, alias, target):
        kind = h5py.HardLink if alias.startswith("aliases/hard_") else h5py.SoftLink
        with h5py.File(src, "r") as f:
            assert isinstance(f.get(alias, getlink=True), kind), alias
            assert f[alias] == f[target] and f[alias].name != f[target].name
            assert f[alias] != f[OTHER if target != OTHER else REGULAR_TS]

    @pytest.mark.parametrize("link", ["hard", "soft"])
    @pytest.mark.parametrize(
        "stem, match",
        [("conv", "source dtype"), ("ts", "starting_time and rate")],
        ids=["convolved", "regular-timestamps"],
    )
    def test_an_alias_of_a_refused_dataset_is_refused_before_anything_is_written(
        self, src, tmp_path, link, stem, match
    ):
        from jnwb.compression import CONVOLVED_PATH

        alias = f"aliases/{link}_{stem}"
        self._assert_alias(src, alias, CONVOLVED_PATH if stem == "conv" else REGULAR_TS)
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError, match=match):
            jnwb.compress_fp32(src, out / "bad.nwb", verify=False, select=[OTHER, alias])
        assert list(out.iterdir()) == []

    def test_an_external_link_is_refused_before_anything_is_written(self, src, tmp_path):
        """An external link opens a dataset in another file, whose name is a path in that file;
        resolving it by name cast the source's own dataset at that path, which nobody named."""
        other = tmp_path / "other.h5"
        with h5py.File(other, "w") as f:
            f.create_dataset(OTHER, data=np.zeros(4))
        with h5py.File(src, "a") as f:
            f["aliases/ext_other"] = h5py.ExternalLink(str(other), "/" + OTHER)
        with h5py.File(src, "r") as f:
            assert isinstance(f.get("aliases/ext_other", getlink=True), h5py.ExternalLink)
            assert f["aliases/ext_other"].name == "/" + OTHER
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError, match="another file"):
            jnwb.compress_fp32(src, out / "bad.nwb", verify=False, select=["aliases/ext_other"])
        assert list(out.iterdir()) == []

    def test_an_external_link_into_the_same_file_is_cast_as_an_alias(self, src, tmp_path):
        """The refusal is for another file; refusing every external link would pass the test
        above. A link back into the source opens a dataset of the source, and that is cast."""
        with h5py.File(src, "a") as f:
            f["aliases/ext_self"] = h5py.ExternalLink(str(src), "/" + OTHER)
        with h5py.File(src, "r") as f:
            assert isinstance(f.get("aliases/ext_self", getlink=True), h5py.ExternalLink)
            assert f["aliases/ext_self"] == f[OTHER]
        stats = jnwb.compress_fp32(src, tmp_path / "ok.nwb", verify=False,
                                   select=["aliases/ext_self"])
        assert stats["cast_paths"] == ["/" + OTHER]
        assert _cast_notes(tmp_path / "ok.nwb") == {OTHER: np.dtype(np.float32)}

    @pytest.mark.parametrize("link", ["hard", "soft"])
    def test_an_alias_of_a_castable_dataset_is_still_cast(self, src, tmp_path, link):
        alias = f"aliases/{link}_other"
        self._assert_alias(src, alias, OTHER)
        stats = jnwb.compress_fp32(src, tmp_path / "ok.nwb", verify=False, select=[alias])
        assert stats["cast_paths"] == ["/" + alias]
        assert _cast_notes(tmp_path / "ok.nwb") == {alias: np.dtype(np.float32)}

    @pytest.mark.parametrize("link", ["hard", "soft"])
    def test_a_regular_timestamps_array_another_link_opens_is_kept(self, src, tmp_path, link):
        """Collapsing it would delete what the alias opens; each link kind is tested alone."""
        with h5py.File(src, "a") as f:
            del f["aliases/" + ("soft_ts" if link == "hard" else "hard_ts")]
            expected = f[REGULAR_TS][:]
        stats = jnwb.compress_fp32(src, tmp_path / "ok.nwb", verify=False, select=[OTHER])
        assert stats["timestamps_kept_linked"] == [REGULAR_TS], stats
        with h5py.File(tmp_path / "ok.nwb", "r") as f:
            np.testing.assert_array_equal(f[f"aliases/{link}_ts"][:], expected)
            np.testing.assert_array_equal(f[REGULAR_TS][:], expected)


class TestSharedTimestampsSurvive:
    """pynwb writes a series' shared ``timestamps`` as a soft link to another series' array.

    Collapsing that array deleted the link's target: the output failed to read in pynwb and the
    only signal was ``ok=False`` in the returned dict. What would pass while the link dangles:
    checking only that the link object exists, or reading the output with h5py alone.
    """

    @pytest.fixture
    def src(self, tmp_path):
        from datetime import datetime, timezone
        from pynwb import NWBFile, NWBHDF5IO, TimeSeries

        path = tmp_path / "shared_ts.nwb"
        nwb = NWBFile(session_description="shared", identifier="shared",
                      session_start_time=datetime(2026, 1, 1, tzinfo=timezone.utc))
        a = TimeSeries(name="A", data=np.arange(500.0), unit="V",
                       timestamps=10.0 + np.arange(500) / 1000.0)   # regular
        nwb.add_acquisition(a)
        nwb.add_acquisition(TimeSeries(name="B", data=np.arange(500.0), unit="V", timestamps=a))
        nwb.add_acquisition(TimeSeries(name="C", data=np.arange(500.0), unit="V", rate=1000.0))
        with NWBHDF5IO(str(path), "w") as io:
            io.write(nwb)
        with h5py.File(path, "r") as f:
            assert isinstance(f["acquisition/B"].get("timestamps", getlink=True), h5py.SoftLink)
        return path

    def test_a_linked_timestamps_array_is_kept_and_the_output_reads(self, src, tmp_path):
        dst = tmp_path / "out.nwb"
        stats = jnwb.compress_fp32(src, dst, select=["acquisition/C/data"])
        assert stats["timestamps_kept_linked"] == ["acquisition/A/timestamps"]
        assert stats["timestamps_collapsed"] == []
        assert stats["verification"]["ok"] is True
        with jnwb.nwb_read_io(str(dst)) as io:
            np.testing.assert_array_equal(io.read().acquisition["B"].timestamps[:],
                                          10.0 + np.arange(500) / 1000.0)

    def test_a_failed_verification_raises(self, src, tmp_path, monkeypatch):
        """The same file with the link guard switched off reproduces the dangling link, and the
        call must raise rather than hand back ``ok=False``."""
        import jnwb.compression as compression
        monkeypatch.setattr(compression, "_is_link_target", lambda f, path, soft_targets: False)
        with pytest.raises(RuntimeError, match="verification check"):
            jnwb.compress_fp32(src, tmp_path / "out.nwb", select=["acquisition/C/data"])

    def test_the_link_scan_is_linear_in_the_number_of_series(self, tmp_path, monkeypatch):
        """Finding which ``timestamps`` arrays a link opens scans the file once, not once per array.

        Counted as group walks (``visit*`` and member iteration, on source and output alike)
        rather than timed. Any cost ``a + b*n`` satisfies ``f(4n) <= 4 f(n)``; a scan per array
        adds ``c*n**2`` and breaks it. What would pass while the scan stays quadratic: a rescan
        that reaches the groups by some route other than these four methods.
        """
        from datetime import datetime, timezone
        from pynwb import NWBFile, NWBHDF5IO, TimeSeries

        walks = [0]
        for name in ("visit", "visititems", "visit_links", "visititems_links", "__iter__"):
            original = getattr(h5py.Group, name)

            def counted(self, *args, _original=original, **kwargs):
                walks[0] += 1
                return _original(self, *args, **kwargs)

            monkeypatch.setattr(h5py.Group, name, counted)

        def cost(n):
            nwb = NWBFile(session_description="n", identifier=f"n{n}",
                          session_start_time=datetime(2026, 1, 1, tzinfo=timezone.utc))
            for i in range(n):
                nwb.add_acquisition(TimeSeries(name=f"s{i}", data=np.zeros(20), unit="V",
                                               timestamps=1.0 + np.arange(20) / 100.0))
            src = tmp_path / f"many_{n}.nwb"
            with NWBHDF5IO(str(src), "w") as io:
                io.write(nwb)
            walks[0] = 0
            stats = jnwb.compress_fp32(src, tmp_path / f"out_{n}.nwb", verify=False,
                                       select=["acquisition/s0/data"])
            assert len(stats["timestamps_collapsed"]) == n
            return walks[0]

        small, large = cost(6), cost(24)
        assert large <= 4 * small, (small, large)
