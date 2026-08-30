"""V4 -- does any outcome value reach a behavioural nuisance covariate?

Three independent probes, none of which requires copying the multi-GB electrophysiology arrays:

  P1 READ-TRACE (dynamic, exhaustive): monkeypatch ``h5py.Dataset.__getitem__`` to record the
     full HDF5 path of EVERY dataset actually read while behavioral_covariates extracts pupil
     and gaze features end to end. If no ``*_lfp`` / ``*_muae`` / ``units/*`` dataset appears in
     the trace, no outcome value can have reached a feature -- this is stronger than reading the
     source, because it also covers anything the helper chain does.

  P2 GARBAGE-SUBSTITUTION (on a slim rebuilt file): construct a small NWB carrying ONLY the
     pupil/gaze/intervals groups copied verbatim plus DELIBERATELY GARBAGE ``probe_0_lfp`` /
     ``probe_0_muae`` / ``units/spike_times`` datasets, and require the extracted features to be
     bit-identical to those from the real file.

  P3 POSITIVE CONTROL: the same slim file with every trial's PRE-onset pupil window shifted by
     +0.5; features MUST change. Without this, P1/P2 passing could just mean the probe is blind.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import h5py
import numpy as np


def _find(grp, leaf):
    found = []
    grp.visititems(lambda n, o: found.append((n, o))
                   if isinstance(o, h5py.Dataset) and n.rsplit("/", 1)[-1] == leaf else None)
    found.sort(key=lambda t: (len(t[0].split("/")), t[0]))
    return found[0][1] if found else None


def frames_identical(a, b):
    cols = [c for c in a.columns if a[c].dtype.kind in "fib"]
    return {c: bool(np.array_equal(a[c].to_numpy(), b[c].to_numpy(),
                                   equal_nan=(a[c].dtype.kind == "f")))
            for c in cols}


def build_slim(src_path, dst_path, rng, pre_onset_shift=None, anchors=None):
    """Slim NWB: real pupil/gaze/intervals + garbage outcome channels."""
    with h5py.File(src_path, "r") as src, h5py.File(dst_path, "w") as d:
        acq = d.create_group("acquisition")
        for key in ("pupil_1_tracking", "eye_1_tracking"):
            src.copy(f"acquisition/{key}", acq, name=key)
        src.copy("intervals", d)
        # garbage outcome channels, plausible shape, pure noise
        n = 200_000
        for key in ("probe_0_lfp", "probe_0_muae"):
            g = acq.create_group(key)
            ds = g.create_dataset("data", data=rng.normal(0, 1000, (n, 128)).astype("f4"))
            ds.attrs["unit"] = "garbage"
            st = g.create_dataset("starting_time", data=0.0)
            st.attrs["rate"] = 1000.0
            st.attrs["unit"] = "seconds"
            g.create_dataset("electrodes", data=np.arange(128))
        u = d.create_group("units")
        u.create_dataset("id", data=np.arange(10))
        u.create_dataset("spike_times", data=rng.uniform(0, 1e4, 5000))
        u.create_dataset("spike_times_index", data=np.arange(500, 5001, 500).astype("u4"))
        if pre_onset_shift is not None:
            grp = d["acquisition/pupil_1_tracking"]
            ds = _find(grp, "data")
            stds = _find(grp, "starting_time")
            rate, start_s = float(stds.attrs["rate"]), float(stds[()])
            arr = np.asarray(ds[:], dtype=np.float64)
            for t in anchors:
                i0 = int(round((float(t) - start_s) * rate))
                arr[max(0, i0 - 500):i0] += pre_onset_shift
            ds[...] = arr.astype(ds.dtype)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work-dir", required=True)
    args = ap.parse_args()

    import omission as oa
    from omission.jnwb_ext import behavioral_covariates as bc

    nwb_dir = oa.paths.nwb_dir()
    work = Path(args.work_dir)
    work.mkdir(parents=True, exist_ok=True)
    out = {"sessions": []}

    for stem in args.sessions:
        src_path = nwb_dir / f"{stem}.nwb"
        rec = {"session": stem}

        # ---------------- P1: read trace ----------------
        reads: list[str] = []
        orig = h5py.Dataset.__getitem__

        def traced(self, key, _o=orig, _r=reads):
            _r.append(self.name)
            return _o(self, key)

        h5py.Dataset.__getitem__ = traced
        try:
            pb0 = bc.load_pupil_epochs(src_path, alignment="p1", window_ms=(-500.0, 0.0),
                                       missing_data="drop", max_trials=150)
            gb0 = bc.load_gaze_epochs(src_path, alignment="p1", window_ms=(-500.0, 0.0),
                                      missing_data="drop", max_trials=150)
            pf0 = bc.extract_pupil_features(pb0)
            gf0 = bc.extract_gaze_features(gb0)
        finally:
            h5py.Dataset.__getitem__ = orig
        uniq = sorted(set(reads))
        outcome_hits = [p for p in uniq
                        if "_lfp" in p or "_muae" in p or p.startswith("/units")]
        rec["p1_read_trace"] = {
            "n_read_calls": len(reads),
            "unique_datasets_read": uniq,
            "outcome_datasets_read": outcome_hits,
            "NO_OUTCOME_DATASET_READ": len(outcome_hits) == 0,
        }

        # ---------------- P2 / P3 ----------------
        rng = np.random.default_rng(20260828)
        slim = work / f"{stem}__slim_garbage.nwb"
        build_slim(src_path, slim, rng)
        pf1 = bc.extract_pupil_features(
            bc.load_pupil_epochs(slim, alignment="p1", window_ms=(-500.0, 0.0),
                                 missing_data="drop", max_trials=150))
        gf1 = bc.extract_gaze_features(
            bc.load_gaze_epochs(slim, alignment="p1", window_ms=(-500.0, 0.0),
                                missing_data="drop", max_trials=150))
        ps, gs = frames_identical(pf0, pf1), frames_identical(gf0, gf1)
        rec["p2_garbage_outcome"] = {
            "n_trials": int(len(pf0)),
            "pupil_features_identical": ps,
            "gaze_features_identical": gs,
            "ALL_IDENTICAL": bool(all(ps.values()) and all(gs.values())),
        }

        slim2 = work / f"{stem}__slim_preonset.nwb"
        build_slim(src_path, slim2, np.random.default_rng(20260828),
                   pre_onset_shift=0.5,
                   anchors=pb0.trial_metadata["anchor_onset_s"].to_numpy())
        pf2 = bc.extract_pupil_features(
            bc.load_pupil_epochs(slim2, alignment="p1", window_ms=(-500.0, 0.0),
                                 missing_data="drop", max_trials=150))
        ch = {c: (not v) for c, v in frames_identical(pf0, pf2).items()}
        rec["p3_positive_control"] = {
            "columns_changed": ch,
            "mean_changed": bool(ch.get("mean", False)),
            "median_changed": bool(ch.get("median", False)),
            "PROBE_IS_SENSITIVE": bool(ch.get("mean", False) and ch.get("median", False)),
            "mean_delta_example": float(np.nanmean(pf2["mean"].to_numpy() - pf0["mean"].to_numpy())),
        }
        slim.unlink(missing_ok=True)
        slim2.unlink(missing_ok=True)
        out["sessions"].append(rec)
        print("done", stem, flush=True)

    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
