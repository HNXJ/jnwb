"""fp32 + chunk + compress an NWB file, losslessly except a documented float32 cast.

Public entry point: :func:`compress_fp32`.

    import jnwb as oa
    stats = oa.compress_fp32("D:/nwb/omission/sub-X_ses-Y.nwb")          # -> alongside, .fp32.nwb
    stats = oa.compress_fp32(src, dst)                                    # explicit destination
    stats = oa.compress_fp32(src, dst, verify=False)                      # skip verification

Implements nwb_tfr_storage_spec.md Part 1 -- float64->float32 for LFP/MUAE, chunking,
gzip1+shuffle everywhere, regular `timestamps` arrays collapsed to `starting_time`+`rate` --
and measures ~2.8x on this corpus (2.77-2.94x over four real sessions, 2026-08-08/09).

Everything below was learned the hard way; each paragraph is a bug that reached a real
multi-hour run before being caught. Read before modifying.

**1. Never hand-copy structure or attributes.** NWB encodes internal structure as HDF5 object
references (an `electrodes` attr pointing at the shared DynamicTable; 162 such reference-typed
objects/attrs in one real session). A raw `h5py.Reference` is only valid inside the file it was
read from -- copying its value into a new file yields a dangling address, and the failure is
INVISIBLE to byte-level array comparison. It only surfaces when the format's own reader runs:
`pynwb.NWBHDF5IO(...).read()` -> "Unable to open object by token". Structure is copied with
h5py's own machinery and references are then explicitly repaired by path lookup
(:func:`_resolve_references`), covering both attribute-valued references and dataset CONTENT of
reference dtype.

**2. h5py's atomic whole-tree copy does not survive real scale.** `Group.copy(src, dst,
expand_refs=True)` on the root object is the documented reference-safe approach and works on
fixtures up to ~2 GiB, but raises `RuntimeError: bad object header version number` on a real
post-churn 84 GiB file. :func:`_structural_copy` therefore copies per top-level group WITHOUT
expand_refs and repairs references afterward, sidestepping that code path entirely.

**3. HDF5 never reclaims space from deleted objects in the same file.** Steps that delete and
recreate a dataset leave the freed extent marked internally but do not truncate the file, and no
`h5repack` binary is assumed present. Without :func:`compact` -- a second copy into a brand-new
file, where nothing was ever deleted -- the output lands at roughly SOURCE size with every
transformation correctly applied and no visible saving. Measured 64-69% of the pre-compaction
file is reclaimed this way on real sessions. Compaction is mandatory, not an optimization.

**4. This corpus is not structurally uniform.** Probe count and LFP/MUAE path nesting vary
INDEPENDENTLY across subjects -- V198o: `probe_N_lfp/data`, 2 probes; V182o:
`probe_N_lfp/probe_N_lfp_data/data`, 3 probes; C31o: flat paths, 3 probes. Hardcoded paths
validated on one subject silently matched NOTHING on another, which would have shipped a
"successful" conversion that never compressed the dominant data type. LFP/MUAE paths are
DISCOVERED (:func:`_find_lfp_muae_paths`); the spike-train paths remain constants but raise
loudly if absent rather than skipping silently.

**5. Some sessions already carry `starting_time` alongside a redundant `timestamps` array.**
Creating a second one collides. The redundant array is dropped only after reconstructing
timestamps from the existing `starting_time`+`rate` and confirming they agree; on disagreement
BOTH are kept and the mismatch recorded, since which is authoritative is not knowable here.

**6. Verification bar is "no worse than the source", not "valid NWB".** At least one session
fails `pynwb` read on the UNTOUCHED original (Device description/manufacturer stored as
1-element arrays rather than scalar strings). Faithfully preserving a pre-existing defect is
correct behavior; demanding strict validity would block forever on data this tool did not break.

**7. `convolved_spike_train` is KEPT by default, deviating from the spec.** The spec says to
drop it and "store the kernel params instead" -- but no kernel parameters are recorded anywhere
in these files or this codebase, so dropping it is irreversible data loss of 17-21% of the file,
not compression. It is recompressed in place instead (the source stores it uncompressed), which
is a strict win. `drop_convolved=True` forces the spec behavior and warns loudly.
"""

from __future__ import annotations

import posixpath
import sys
import time
import re
from pathlib import Path

import h5py
import numpy as np

FILT = dict(compression="gzip", compression_opts=1, shuffle=True)

# LFP/MUAE paths are DISCOVERED, not hardcoded -- corrected 2026-08-09 after sub-V182o_ses-260724
# crashed and exposed that this corpus has (at least) three independent structural variants:
#   V198o: acquisition/probe_N_lfp/data                       (flat, 2 probes)
#   V182o: acquisition/probe_N_lfp/probe_N_lfp_data/data       (extra nesting, 3 probes)
#   C31o:  acquisition/probe_N_lfp/data                        (flat, 3 probes)
# Probe count and nesting convention are INDEPENDENT variables -- neither can be assumed from
# subject or from another file already checked. The prior hardcoded 4-path tuple (probe_0/1
# only, flat) silently matched NOTHING on V182o's nested paths: Step 2's `if path not in dst:
# continue` skipped every LFP/MUAE array with no warning, which would have shipped a "successful"
# conversion that never actually compressed the dominant data type. Caught before it was
# reported, by noticing the run crashed on an UNRELATED bug (the starting_time collision below)
# before reaching verification -- had that second bug not existed, the silent skip would have
# gone unnoticed. _find_lfp_muae_paths matches by REGEX on the path, tolerant of any nesting.
# Anchored to the TWO known nesting shapes only (flat, or one extra `<probe>_data` level via a
# backreference) -- a naive "contains probe_N_lfp anywhere" match also caught the small
# electrodes-region-index dataset nested INSIDE the LFP group
# (probe_0_lfp/probe_0_lfp_data/electrodes/data), which has a different rank/shape and crashed
# create_dataset on a chunk-rank mismatch. Caught in the synthetic fixture before it could repeat
# against a real 100+ GiB file.
_LFP_MUAE_RE = re.compile(r"(probe_\d+_(?:lfp|muae))(?:/\1_data)?/data$")


def _find_lfp_muae_paths(f: h5py.File) -> list[str]:
    paths: list[str] = []

    def w(name, obj):
        if isinstance(obj, h5py.Dataset) and _LFP_MUAE_RE.search(name):
            paths.append("/" + name)

    f.visititems(w)
    return sorted(set(paths))


SPIKE_TRAIN_PATH = "processing/spike_train/spike_train_data/data"
CONVOLVED_PATH = "processing/convolved_spike_train/convolved_spike_train_data/data"
# Verified identical across all 3 subjects checked (V198o, V182o, C31o) unlike LFP/MUAE above,
# so these stay as constants -- but convert() asserts they exist rather than silently skipping,
# so a fourth session with yet another convention fails LOUDLY instead of repeating the LFP bug.

# Every `timestamps` array in the source that is regular gets collapsed. Discovered by scan,
# not hardcoded, since a session can carry extra tracked signals (eye/pupil/reward/photodiode).


def _is_regular(ts: np.ndarray, tol: float = 1e-6) -> tuple[bool, float]:
    d = np.diff(ts)
    if len(d) == 0:
        return False, 0.0
    mean_dt = float(d.mean())
    std_dt = float(d.std())
    regular = mean_dt > 0 and (std_dt / mean_dt) < tol
    return regular, (1.0 / mean_dt if regular else 0.0)


def _find_timestamp_paths(f: h5py.File) -> list[str]:
    paths = []
    def w(name, obj):
        if isinstance(obj, h5py.Dataset) and Path(name).name == "timestamps" and obj.ndim == 1 and obj.dtype.kind == "f":
            paths.append(name)
    f.visititems(w)
    return paths


def _replace_dataset_data(dst: h5py.File, path: str, new_shape, new_dtype, chunks, filt,
                           fill_block) -> dict:
    """Delete dst[path], recreate with new storage params, stream in new content via
    fill_block(ds, start, stop), reapply the ORIGINAL attrs (already dst-native references
    by this point since step 1's expand_refs already ran)."""
    old_attrs = dict(dst[path].attrs)
    del dst[path]
    parent = dst[posixpath.dirname(path) or "/"]
    ds = parent.create_dataset(posixpath.basename(path), shape=new_shape, dtype=new_dtype, chunks=chunks, **filt)
    fill_block(ds)
    for k, v in old_attrs.items():
        ds.attrs[k] = v
    return dict(ds.attrs)


def _resolve_references(src: h5py.File, dst: h5py.File) -> int:
    """After a per-group structural copy (references copied as raw, source-only-valid
    addresses), repair every reference by resolving its TARGET PATH in `src` and reassigning a
    freshly-created, dst-native reference at the same location in `dst`. Handles both
    attribute-valued references (single or array-of) and dataset CONTENT of reference dtype
    (e.g. an NWB DynamicTable column of per-row object references). Returns count fixed.
    """
    n_fixed = 0

    def fix_attrs(path: str, src_obj, dst_obj) -> None:
        nonlocal n_fixed
        for k, v in src_obj.attrs.items():
            if isinstance(v, h5py.Reference):
                if not v:
                    continue
                target = src[v].name
                if target in dst:
                    dst_obj.attrs[k] = dst[target].ref
                    n_fixed += 1
            elif isinstance(v, np.ndarray) and v.dtype.kind == "O" and v.size and isinstance(
                np.asarray(v).flat[0], h5py.Reference
            ):
                fixed = np.empty_like(v)
                it = np.nditer(v, flags=["refs_ok", "multi_index"])
                for _ in it:
                    r = v[it.multi_index]
                    fixed[it.multi_index] = dst[src[r].name].ref if r and src[r].name in dst else r
                dst_obj.attrs[k] = fixed
                n_fixed += 1

    fix_attrs("/", src, dst)
    for name, src_obj in ((n, src[n]) for n in _all_paths(src)):
        full = "/" + name
        if full not in dst:
            continue
        fix_attrs(full, src_obj, dst[full])
        if isinstance(src_obj, h5py.Dataset) and h5py.check_dtype(ref=src_obj.dtype):
            raw = src_obj[:]
            fixed = np.empty_like(raw)
            for idx in np.ndindex(raw.shape):
                r = raw[idx]
                fixed[idx] = dst[src[r].name].ref if r and src[r].name in dst else r
            dst[full][...] = fixed
            n_fixed += 1
    return n_fixed


def _all_paths(f: h5py.File) -> list[str]:
    paths: list[str] = []
    f.visititems(lambda name, obj: paths.append(name))
    return paths


def _structural_copy(src: h5py.File, dst: h5py.File) -> None:
    """Copy every top-level object of `src` into `dst`, one group at a time, WITHOUT
    expand_refs. A single atomic root-object copy with expand_refs=True (h5py's documented
    approach for this) was tried first and rejected: it works on small/synthetic files but
    failed on the real, post-churn 84 GiB session file with
    `RuntimeError: Unable to synchronously copy object (bad object header version number)` --
    reproducible on the real file, NOT reproducible on fixtures up to ~2 GiB with the same
    structure, so this is a scale/internal-format boundary in HDF5's own H5Ocopy+expand_refs
    path, not a bug in this script's usage of it. Per-group copy without expand_refs sidesteps
    that code path entirely; references are repaired afterward by _resolve_references, which
    needs no bulk reference-expansion machinery -- just path lookups."""
    for k, v in src.attrs.items():
        if not isinstance(v, h5py.Reference):
            dst.attrs[k] = v
    for key in src.keys():
        src.copy(src[key], dst, name=key, expand_refs=False)
    n_fixed = _resolve_references(src, dst)
    return n_fixed


def compact(src_path: Path, dst_path: Path) -> int:
    """Re-implement h5repack's core operation with h5py alone (no h5repack binary available in
    this environment): copy the live object graph into a brand-new file. Nothing is ever
    deleted from `dst_path`, so no freed-but-unreclaimed space can accumulate in it -- unlike
    `src_path`, which may be padded from convert()'s delete+recreate steps."""
    with h5py.File(src_path, "r") as s, h5py.File(dst_path, "w") as d:
        return _structural_copy(s, d)


def convert(src_path: Path, dst_path: Path, drop_convolved: bool = False) -> dict:
    if drop_convolved:
        print("!! --drop-convolved-spike-train forces the spec's original behavior. "
              "No kernel parameters are recoverable for this array (checked 2026-08-08, see "
              "module docstring). This is DATA LOSS, not compression. Proceeding because you "
              "asked explicitly.", file=sys.stderr)

    stats = {"max_float32_err": 0.0, "timestamps_collapsed": [], "timestamps_kept_irregular": []}
    t0 = time.time()

    # Write to a temp path first -- this file WILL be padded with unreclaimed freed space from
    # the delete+recreate steps below (see module docstring). Compacted into dst_path at the end.
    bloated_path = dst_path.with_name(dst_path.stem + ".bloated.tmp" + dst_path.suffix)
    with h5py.File(src_path, "r") as src, h5py.File(bloated_path, "w") as dst:
        print("Step 1/3: full reference-safe copy (per-group + explicit reference repair) ...")
        t1 = time.time()
        n_fixed = _structural_copy(src, dst)
        print(f"  done in {time.time()-t1:.1f}s ({n_fixed} references repaired)")

        if drop_convolved and CONVOLVED_PATH in dst:
            n_bytes = dst[CONVOLVED_PATH].dtype.itemsize * int(np.prod(dst[CONVOLVED_PATH].shape))
            del dst[CONVOLVED_PATH]
            stats["convolved_dropped_bytes"] = n_bytes

        lfp_muae_paths = _find_lfp_muae_paths(src)
        print(f"Step 2/3: replacing LFP/MUAE ({len(lfp_muae_paths)} arrays found, "
              "float32+chunk+compress), spike_train and convolved_spike_train "
              "(rechunk+compress in place) ...")
        for path in lfp_muae_paths:
            print(f"    {path}")
            src_ds = src[path]
            n_ch = src_ds.shape[1] if src_ds.ndim == 2 else 1
            chunks = (min(16384, src_ds.shape[0]), n_ch)
            max_err = [0.0]

            def fill(ds, src_ds=src_ds, max_err=max_err):
                block = 1_000_000
                for start in range(0, src_ds.shape[0], block):
                    stop = min(start + block, src_ds.shape[0])
                    raw = src_ds[start:stop]
                    cast = raw.astype(np.float32)
                    err = float(np.max(np.abs(raw - cast.astype(np.float64)))) if raw.size else 0.0
                    max_err[0] = max(max_err[0], err)
                    ds[start:stop] = cast

            _replace_dataset_data(dst, path, src_ds.shape, np.float32, chunks, FILT, fill)
            dst[path].attrs["stored_dtype_note"] = (
                f"cast from float64 to float32 at write time by scripts/convert_nwb_compressed.py "
                f"v2 on {time.strftime('%Y-%m-%d')}; measured max abs round-trip err {max_err[0]:.6e}"
            )
            stats["max_float32_err"] = max(stats["max_float32_err"], max_err[0])

        # Distinguish LEGITIMATE ABSENCE from an UNKNOWN CONVENTION -- both look like "expected
        # path missing", but only one is a bug. Found 2026-08-09 on sub-V182o_ses-260713, whose
        # `processing/` group is entirely EMPTY: it stores spikes only as units/spike_times
        # (standard NWB ragged arrays), with no dense binned spike_train matrix at all. That is
        # a real structural variant of this corpus, not a path this tool failed to recognize,
        # so failing was wrong. But a NON-empty processing/ that lacks the expected paths WOULD
        # mean an unrecognized convention, and must still fail loudly rather than silently skip
        # -- which is the LFP/MUAE incident this guard exists to prevent recurring.
        processing_populated = "processing" in dst and len(dst["processing"].keys()) > 0
        for _p in (SPIKE_TRAIN_PATH, CONVOLVED_PATH):
            if _p in dst:
                continue
            if processing_populated:
                raise KeyError(
                    f"{_p} not found in {src_path.name}, but processing/ is non-empty "
                    f"(contains {sorted(dst['processing'].keys())}) -- this session appears to "
                    "use a structural convention this tool does not recognize. Failing loudly "
                    "rather than silently skipping, per the LFP/MUAE silent-skip incident."
                )
            stats.setdefault("absent_optional_datasets", []).append(_p)
            print(f"  NOTE: {_p} absent and processing/ is empty -- this session stores spikes "
                  "only as units/spike_times (ragged). Nothing to convert there; proceeding.")

        if SPIKE_TRAIN_PATH in dst:
            src_ds = src[SPIKE_TRAIN_PATH]
            n_units = src_ds.shape[1] if src_ds.ndim == 2 else 1
            chunks = (min(65536, src_ds.shape[0]), n_units)

            def fill_st(ds, src_ds=src_ds):
                block = 2_000_000
                for start in range(0, src_ds.shape[0], block):
                    stop = min(start + block, src_ds.shape[0])
                    ds[start:stop] = src_ds[start:stop]

            _replace_dataset_data(dst, SPIKE_TRAIN_PATH, src_ds.shape, src_ds.dtype, chunks, FILT, fill_st)

        if not drop_convolved and CONVOLVED_PATH in dst:
            # Source has NO compression on this array at all -- recompressing in place, with
            # the data fully intact, is a strict win: smaller on disk, nothing lost.
            src_ds = src[CONVOLVED_PATH]
            n_ch = src_ds.shape[1] if src_ds.ndim == 2 else 1
            chunks = (min(16384, src_ds.shape[0]), n_ch)

            def fill_cv(ds, src_ds=src_ds):
                block = 1_000_000
                for start in range(0, src_ds.shape[0], block):
                    stop = min(start + block, src_ds.shape[0])
                    ds[start:stop] = src_ds[start:stop]

            _replace_dataset_data(dst, CONVOLVED_PATH, src_ds.shape, src_ds.dtype, chunks, FILT, fill_cv)

        print("Step 3/3: collapsing regular timestamp arrays to starting_time+rate ...")
        stats["timestamps_redundant_dropped"] = []
        stats["timestamps_inconsistent_kept"] = []
        for ts_path in _find_timestamp_paths(src):
            full = "/" + ts_path
            data = src[ts_path][:]
            regular, rate = _is_regular(data)
            group_path = posixpath.dirname(full) or "/"
            if group_path not in dst:
                continue
            if not regular:
                stats["timestamps_kept_irregular"].append(ts_path)
                continue

            # Found 2026-08-09 on sub-V182o_ses-260724: some sessions ALREADY carry a
            # starting_time+rate dataset alongside an explicit (redundant) `timestamps` array
            # for the SAME TimeSeries, copied verbatim by Step 1. Creating a new starting_time
            # here collides. Verify the existing one is actually consistent with the timestamps
            # array being collapsed before treating the timestamps array as redundant and
            # dropping it -- do not assume, since a genuine mismatch would mean they encode
            # different things and neither should be silently discarded.
            if "starting_time" in dst[group_path]:
                existing = dst[group_path]["starting_time"]
                existing_rate = existing.attrs.get("rate")
                reconstructed = existing[()] + np.arange(len(data)) / existing_rate
                err = float(np.max(np.abs(reconstructed - data))) if len(data) else 0.0
                if existing_rate is not None and err < 1e-6:
                    del dst[ts_path]
                    stats["timestamps_redundant_dropped"].append((ts_path, err))
                else:
                    stats["timestamps_inconsistent_kept"].append((ts_path, err))
                continue

            del dst[ts_path]
            st_ds = dst[group_path].create_dataset("starting_time", data=np.float64(data[0]))
            st_ds.attrs["rate"] = np.float64(rate)
            st_ds.attrs["unit"] = src[ts_path].attrs.get("unit", "seconds")
            stats["timestamps_collapsed"].append((ts_path, rate))

        dst.attrs["conversion_script"] = "scripts/convert_nwb_compressed.py"
        dst.attrs["conversion_script_version"] = "v2"
        dst.attrs["conversion_date"] = time.strftime("%Y-%m-%d")
        dst.attrs["conversion_source_file"] = str(src_path)
        dst.attrs["conversion_kept_convolved_spike_train"] = not drop_convolved

    stats["bloated_bytes"] = bloated_path.stat().st_size

    print("Step 4/4: compacting (h5py-native h5repack equivalent -- see module docstring) ...")
    t2 = time.time()
    compact(bloated_path, dst_path)
    bloated_path.unlink()
    print(f"  done in {time.time()-t2:.1f}s")

    stats["elapsed_s"] = time.time() - t0
    stats["src_bytes"] = src_path.stat().st_size
    stats["dst_bytes"] = dst_path.stat().st_size
    stats["compaction_reclaimed_bytes"] = stats["bloated_bytes"] - stats["dst_bytes"]
    return stats


def verify_roundtrip(src_path: Path, dst_path: Path, n_check: int = 200_000) -> dict:
    """Byte-level sampling of the transformed datasets, PLUS a real pynwb parse -- v1's bug was
    invisible to byte comparison alone, so the pynwb read is not optional."""
    results = {"ok": True, "checks": []}

    def rec(name, ok, detail):
        results["checks"].append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            results["ok"] = False

    with h5py.File(src_path, "r") as s, h5py.File(dst_path, "r") as d:
        for path in _find_lfp_muae_paths(s):
            if path not in d:
                continue
            n = min(n_check, s[path].shape[0])
            raw = s[path][:n]
            conv = d[path][:n].astype(np.float64)
            err = float(np.max(np.abs(raw - conv)))
            rec(f"{path} first {n} rows max abs err", err < 1e-3, f"{err:.6e}")

        if SPIKE_TRAIN_PATH in s and SPIKE_TRAIN_PATH in d:
            n = min(n_check, s[SPIKE_TRAIN_PATH].shape[0])
            eq = np.array_equal(s[SPIKE_TRAIN_PATH][:n], d[SPIKE_TRAIN_PATH][:n])
            rec(f"{SPIKE_TRAIN_PATH} first {n} rows exact match", eq, "exact" if eq else "MISMATCH")

        if CONVOLVED_PATH in s and CONVOLVED_PATH in d:
            n = min(n_check, s[CONVOLVED_PATH].shape[0])
            eq = np.array_equal(s[CONVOLVED_PATH][:n], d[CONVOLVED_PATH][:n])
            rec(f"{CONVOLVED_PATH} first {n} rows exact match (kept, recompressed)", eq, "exact" if eq else "MISMATCH")

        for path in ["units/id", "electrodes/id"]:
            if path in s and path in d:
                eq = np.array_equal(s[path][:], d[path][:])
                rec(f"{path} full exact match", eq, "exact" if eq else "MISMATCH")

        for grp in ["acquisition/probe_0_lfp", "processing/spike_train/spike_train_data"]:
            if grp + "/starting_time" in d and grp + "/timestamps" in s:
                st = d[grp + "/starting_time"][()]
                rate = d[grp + "/starting_time"].attrs["rate"]
                orig = s[grp + "/timestamps"][:]
                n = min(n_check, len(orig))
                reconstructed = st + np.arange(n) / rate
                err = float(np.max(np.abs(reconstructed - orig[:n])))
                rec(f"{grp} timestamps reconstruction max abs err", err < 1e-6, f"{err:.6e}")

    # The check v1 lacked: does this actually parse as valid NWB. The bar is "does not parse
    # WORSE than the source", not "parses cleanly" -- found 2026-08-09 on sub-V182o_ses-260724,
    # whose SOURCE file already fails pynwb read (a pre-existing Device.description/manufacturer
    # attrs-stored-as-1-element-arrays defect, confirmed identical byte-for-byte in both files,
    # not introduced by this script). Requiring strict pynwb validity would block forever on any
    # session that was already non-conformant, and rejecting a faithfully-preserved defect is not
    # this script's job. What DOES matter: the destination must fail the SAME way, or not at all.
    import warnings
    warnings.filterwarnings("ignore")
    from pynwb import NWBHDF5IO

    def _try_pynwb_read(p):
        try:
            with NWBHDF5IO(str(p), "r") as io:
                nwbfile = io.read()
                n_units = len(nwbfile.units) if nwbfile.units is not None else 0
                return True, f"OK -- {len(nwbfile.acquisition)} acquisition series, {n_units} units"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    src_ok, src_detail = _try_pynwb_read(src_path)
    dst_ok, dst_detail = _try_pynwb_read(dst_path)
    if dst_ok:
        rec("pynwb NWBHDF5IO(...).read()", True, dst_detail)
    elif not src_ok and dst_detail == src_detail:
        rec("pynwb NWBHDF5IO(...).read()", True,
            f"source ALSO fails identically (pre-existing defect, faithfully preserved): {dst_detail}")
    else:
        rec("pynwb NWBHDF5IO(...).read()", False,
            f"dst: {dst_detail}" + (f"  |  src: {src_detail}" if src_ok else "  |  src fails DIFFERENTLY"))

    return results


def compress_fp32(
    src: "str | Path",
    dst: "str | Path | None" = None,
    *,
    drop_convolved: bool = False,
    verify: bool = True,
    n_check: int = 200_000,
    overwrite: bool = False,
) -> dict:
    """Compress one NWB file: float32 LFP/MUAE, chunking, gzip1+shuffle, compaction.

    Args:
        src: path to the NWB file to compress. Never modified.
        dst: output path. Defaults to ``<src stem>.fp32.nwb`` beside ``src``.
        drop_convolved: drop ``convolved_spike_train`` rather than recompressing it. This is
            IRREVERSIBLE DATA LOSS on this corpus (no kernel parameters are recorded anywhere
            to regenerate it from) -- see point 7 in the module docstring. Warns loudly.
        verify: run round-trip verification (byte samples + pynwb parse) after converting.
        n_check: rows sampled per array during verification.
        overwrite: allow writing over an existing ``dst``.

    Returns:
        dict of conversion stats -- ``src_bytes``, ``dst_bytes``, ``ratio``, ``elapsed_s``,
        ``max_float32_err``, ``compaction_reclaimed_bytes``, the timestamp dispositions, and
        (when ``verify``) ``verification`` with per-check results and an overall ``ok`` flag.

    Raises:
        FileNotFoundError: ``src`` does not exist.
        FileExistsError: ``dst`` exists and ``overwrite`` is False.
        KeyError: the file uses a structural convention this tool does not recognize -- raised
            rather than silently skipping the affected arrays.
    """
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(f"source NWB not found: {src}")
    dst = Path(dst) if dst is not None else src.with_suffix(".fp32.nwb")
    if dst.exists() and not overwrite:
        raise FileExistsError(f"destination exists (pass overwrite=True): {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)

    stats = convert(src, dst, drop_convolved=drop_convolved)
    stats["ratio"] = stats["src_bytes"] / stats["dst_bytes"] if stats["dst_bytes"] else float("nan")
    stats["src_path"] = str(src)
    stats["dst_path"] = str(dst)
    if verify:
        stats["verification"] = verify_roundtrip(src, dst, n_check=n_check)
    return stats
