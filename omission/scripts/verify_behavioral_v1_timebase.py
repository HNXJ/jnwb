"""V1 -- INDEPENDENT verification of pupil/gaze sampling rate and time-base synchronization.

Written fresh for the independent-verification pass (2026-08-28). Does NOT import
behavioral_covariates or analog; reads h5py directly with its own traversal so a shared bug
in the helper cannot hide here.

Checks, per session, for BOTH pupil_1_tracking and eye_1_tracking:
  - declared `rate` attribute and `starting_time`
  - free-text group `description`
  - n_samples
  - EFFECTIVE rate probe 1: implied span (n_samples / declared_rate) vs. LFP-implied session
    span (LFP n_samples / LFP rate) and vs. last trial onset from the intervals table.
  - EFFECTIVE rate probe 2: fraction of consecutive sample pairs that are EXACTLY equal
    (sample-and-hold signature of a 500 Hz signal stored at a declared 1000 Hz), and the
    even/odd-lag autocorrelation-of-diff signature.
  - time base: session_start_time, timestamps_reference_time, per-series starting_time across
    every acquisition group, and whether any explicit `timestamps` dataset exists.

Usage:
    python omission/scripts/verify_behavioral_v1_timebase.py --out <json>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import h5py
import numpy as np


def _s(v):
    if isinstance(v, (bytes, np.bytes_)):
        return v.decode("utf-8", "replace")
    if isinstance(v, np.ndarray):
        if v.shape == ():
            return _s(v.item())
        return [_s(x) for x in v.tolist()]
    return v


def find_all(group, leaf):
    """Every dataset whose basename == leaf, with full path (own traversal)."""
    out = []

    def visit(name, obj):
        if isinstance(obj, h5py.Dataset) and name.rsplit("/", 1)[-1] == leaf:
            out.append((name, obj))

    group.visititems(visit)
    return out


def series_meta(group):
    """Return dict of rate/starting_time/description/data-shape for a tracking group,
    resolved by MY OWN traversal (not analog._rate_and_start)."""
    m = {"group_description": _s(group.attrs.get("description", None)),
         "group_neurodata_type": _s(group.attrs.get("neurodata_type", None))}
    datas = find_all(group, "data")
    starts = find_all(group, "starting_time")
    tss = find_all(group, "timestamps")
    m["data_paths"] = [p for p, _ in datas]
    m["timestamps_paths"] = [p for p, _ in tss]
    if not datas:
        return m
    path, ds = datas[0]
    m["data_path"] = path
    m["shape"] = list(ds.shape)
    m["dtype"] = str(ds.dtype)
    m["unit_attr"] = _s(ds.attrs.get("unit", None))
    m["data_attr_rate"] = _s(ds.attrs.get("rate", None))
    if starts:
        sp, sds = starts[0]
        m["starting_time_path"] = sp
        m["starting_time"] = float(sds[()]) if sds.shape == () else None
        m["starting_time_rate_attr"] = float(sds.attrs["rate"]) if "rate" in sds.attrs else None
        m["starting_time_unit_attr"] = _s(sds.attrs.get("unit", None))
    return m


def repeat_signature(x, max_n=2_000_000):
    """Sample-and-hold diagnostics on a 1-D array.

    frac_zero_diff       : fraction of consecutive pairs exactly equal
    frac_zero_diff_even  : fraction among pairs starting at even index
    frac_zero_diff_odd   : fraction among pairs starting at odd index
    A 500 Hz signal written at a declared 1000 Hz by duplication gives ~0.5 overall and a
    near-1.0 / near-0.0 split between the two parities.
    """
    x = np.asarray(x[:max_n], dtype=np.float64)
    d = np.diff(x)
    if d.size < 10:
        return None
    z = d == 0.0
    return {
        "n_pairs": int(d.size),
        "frac_zero_diff": float(np.mean(z)),
        "frac_zero_diff_even_start": float(np.mean(z[0::2])),
        "frac_zero_diff_odd_start": float(np.mean(z[1::2])),
        "frac_nan": float(np.mean(~np.isfinite(x))),
        "min": float(np.nanmin(x)),
        "max": float(np.nanmax(x)),
        "mean": float(np.nanmean(x)),
        "std": float(np.nanstd(x)),
    }


def lfp_span(handle):
    """Longest acquisition-series implied span (s) among *_lfp groups, my own traversal."""
    acq = handle.get("acquisition")
    if acq is None:
        return None
    best = None
    for key in acq:
        if not key.endswith("_lfp"):
            continue
        grp = acq[key]
        datas = find_all(grp, "data")
        starts = find_all(grp, "starting_time")
        if not datas or not starts:
            continue
        n = datas[0][1].shape[0]
        sds = starts[0][1]
        rate = float(sds.attrs["rate"]) if "rate" in sds.attrs else None
        st = float(sds[()]) if sds.shape == () else 0.0
        if rate:
            span = {"probe": key, "n_samples": int(n), "rate": rate,
                    "starting_time": st, "end_time_s": st + n / rate}
            if best is None or span["end_time_s"] > best["end_time_s"]:
                best = span
    return best


def trial_span(handle):
    iv = handle.get("intervals/omission_glo_passive")
    if iv is None or "start_time" not in iv:
        return None
    st = iv["start_time"][:]
    if st.dtype.kind in "OSU":
        st = np.array([float(_s(v)) for v in st])
    st = np.asarray(st, dtype=float)
    st = st[np.isfinite(st)]
    if st.size == 0:
        return None
    return {"n_rows": int(st.size), "min_start_s": float(st.min()),
            "max_start_s": float(st.max())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nwb-dir", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--value-read", action="store_true",
                    help="also read full pupil/gaze arrays for the repeat signature")
    args = ap.parse_args()

    import omission as oa
    nwb_dir = Path(args.nwb_dir) if args.nwb_dir else oa.paths.nwb_dir()
    files = sorted(nwb_dir.glob("*.nwb"))
    out = {"nwb_dir": str(nwb_dir), "n_files": len(files), "sessions": []}

    for f in files:
        rec = {"session": f.stem, "subject": f.stem.split("_")[0].removeprefix("sub-")}
        try:
            with h5py.File(f, "r") as h:
                rec["session_start_time"] = _s(h["session_start_time"][()]) if "session_start_time" in h else None
                rec["timestamps_reference_time"] = (
                    _s(h["timestamps_reference_time"][()]) if "timestamps_reference_time" in h else None)
                acq = h.get("acquisition")
                rec["acquisition_keys"] = sorted(acq.keys()) if acq is not None else []
                for key, tag in (("pupil_1_tracking", "pupil"), ("eye_1_tracking", "gaze")):
                    if acq is not None and key in acq:
                        rec[tag] = series_meta(acq[key])
                    else:
                        rec[tag] = {"absent": True}
                rec["lfp_span"] = lfp_span(h)
                rec["trial_span"] = trial_span(h)
                # every acquisition series' starting_time, for shared-clock check
                clocks = {}
                if acq is not None:
                    for key in sorted(acq.keys()):
                        starts = find_all(acq[key], "starting_time")
                        if starts:
                            sds = starts[0][1]
                            clocks[key] = {
                                "starting_time": float(sds[()]) if sds.shape == () else None,
                                "rate": float(sds.attrs["rate"]) if "rate" in sds.attrs else None,
                            }
                rec["acquisition_clocks"] = clocks
                if args.value_read:
                    for key, tag in (("pupil_1_tracking", "pupil"), ("eye_1_tracking", "gaze")):
                        if acq is None or key not in acq:
                            continue
                        datas = find_all(acq[key], "data")
                        if not datas:
                            continue
                        ds = datas[0][1]
                        if ds.ndim == 1:
                            rec[tag]["repeat_signature"] = {"ch0": repeat_signature(ds[:])}
                        else:
                            arr = ds[:, :]
                            rec[tag]["repeat_signature"] = {
                                f"ch{c}": repeat_signature(arr[:, c]) for c in range(arr.shape[1])}
        except Exception as exc:  # noqa: BLE001
            rec["error"] = f"{type(exc).__name__}: {exc}"
        out["sessions"].append(rec)
        print(f"done {f.stem}", flush=True)

    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
