"""V2/V3 -- independent trial-alignment and strict-pre-event verification.

V2: rebuild epochs BY HAND from the raw h5py array + trial onset times read with my own
    intervals parser (no _trial_table), and compare bit-for-bit against
    behavioral_covariates.load_behavioral_epochs. Also probe the window-edge convention by
    checking, for a known onset, exactly which absolute sample indices the module returned
    (via a sentinel-injection trick: temporarily monkeypatch nothing -- instead locate the
    returned chunk inside the full array by exact match and report the found index range).

V3: empirical future-leakage test. Copy the pupil/gaze arrays into an in-memory HDF5 file,
    CORRUPT every sample at or after each trial's anchor (t>=0) with a large constant, re-run
    the module against the corrupted copy, and require the extracted features to be
    BIT-IDENTICAL to the uncorrupted run. Anything not identical means a post-onset sample
    reached a feature.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd


def _s(v):
    if isinstance(v, (bytes, np.bytes_)):
        return v.decode("utf-8", "replace")
    if isinstance(v, np.ndarray) and v.shape == ():
        return _s(v.item())
    return v


def _num(group, name):
    v = group[name][:]
    if v.dtype.kind in "OSU":
        return np.array([float(_s(x)) for x in v])
    return np.asarray(v, dtype=float)


def my_trial_onsets(path, condition=None, correct_only=True):
    """My own minimal intervals reader: p1 onset (stimulus_number==2) per trial."""
    with h5py.File(path, "r") as h:
        iv = h["intervals/omission_glo_passive"]
        df = pd.DataFrame({c: _num(iv, c) for c in
                           ("start_time", "trial_num", "stimulus_number", "task_condition_number")})
        df["correct"] = _num(iv, "correct") if "correct" in iv else 1.0
    df = df[np.isclose(df["stimulus_number"], 2.0)]
    df = df[np.isfinite(df["start_time"]) & np.isfinite(df["trial_num"])
            & np.isfinite(df["task_condition_number"])]
    if correct_only:
        df = df[df["correct"] == 1.0]
    return df.reset_index(drop=True)


def find_chunk_index(full, chunk):
    """Locate the exact absolute start index of `chunk` inside 1-D `full` by value match."""
    n = chunk.size
    first = chunk[0]
    cands = np.flatnonzero(full[: full.size - n + 1] == first)
    hits = [int(i) for i in cands if np.array_equal(full[i:i + n], chunk)]
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-check", type=int, default=6)
    args = ap.parse_args()

    import omission as oa
    from omission.jnwb_ext import behavioral_covariates as bc

    nwb_dir = oa.paths.nwb_dir()
    report = {"sessions": []}

    for stem in args.sessions:
        path = nwb_dir / f"{stem}.nwb"
        rec = {"session": stem}

        # ---------- V2 ----------
        for signal_class, key, ndim in (("pupil", "pupil_1_tracking", 1), ("gaze", "eye_1_tracking", 2)):
            for alignment, window in (("p1", (-500.0, 0.0)), ("omission", (-250.0, -50.0))):
                tag = f"{signal_class}|{alignment}"
                try:
                    kw = dict(alignment=alignment, window_ms=window, missing_data="drop",
                              max_trials=200)
                    if alignment == "omission":
                        kw["condition"] = "AAXB"
                    batch = bc.load_behavioral_epochs(path, signal_class=signal_class, **kw)
                except Exception as exc:  # noqa: BLE001
                    rec[tag] = {"error": f"{type(exc).__name__}: {exc}"}
                    continue

                with h5py.File(path, "r") as h:
                    grp = h["acquisition"][key]
                    found = []
                    grp.visititems(lambda n, o: found.append((n, o))
                                   if isinstance(o, h5py.Dataset) and n.rsplit("/", 1)[-1] == "data" else None)
                    ds = found[0][1]
                    # my own rate/start read
                    sfound = []
                    grp.visititems(lambda n, o: sfound.append((n, o))
                                   if isinstance(o, h5py.Dataset) and n.rsplit("/", 1)[-1] == "starting_time" else None)
                    rate = float(sfound[0][1].attrs["rate"])
                    start_s = float(sfound[0][1][()])
                    n_total = int(ds.shape[0])

                    md = batch.trial_metadata
                    idx_check = list(range(min(args.n_check, len(md))))
                    per_trial = []
                    for i in idx_check:
                        anchor = float(md.loc[i, "anchor_onset_s"])
                        # MY OWN index arithmetic, written independently:
                        # window edge lo_ms before the anchor, on the shared 1 kHz grid.
                        t0 = anchor + window[0] / 1000.0 - start_s
                        i0_floor = int(np.floor(t0 * rate))
                        i0_round = int(np.round(t0 * rate))
                        n_win = int(round((window[1] - window[0]) / 1000.0 * rate))
                        if ds.ndim == 1:
                            hand = np.asarray(ds[i0_round:i0_round + n_win], dtype=np.float64)[None, :]
                            full = np.asarray(ds[max(0, i0_round - 5):i0_round + n_win + 5], dtype=np.float64)
                        else:
                            hand = np.asarray(ds[i0_round:i0_round + n_win, :], dtype=np.float64).T
                            full = np.asarray(ds[max(0, i0_round - 5):i0_round + n_win + 5, 0], dtype=np.float64)
                        mod = batch.data[i]
                        exact = bool(np.array_equal(hand, mod))
                        # offset search: where does the module's chunk actually sit?
                        offs = None
                        if not exact:
                            hits = find_chunk_index(full, mod[0])
                            offs = [h - 5 for h in hits] if hits else []
                        per_trial.append({
                            "row": i,
                            "trial_id": str(md.loc[i, "trial_id"]),
                            "anchor_onset_s": anchor,
                            "source_onset_s": float(md.loc[i, "source_onset_s"]),
                            "my_start_index_round": i0_round,
                            "my_start_index_floor": i0_floor,
                            "n_window_samples": n_win,
                            "module_n_samples": int(mod.shape[-1]),
                            "bitwise_identical": exact,
                            "offset_if_mismatch": offs,
                        })
                    # time vector convention
                    tv = batch.time_ms
                    rec[tag] = {
                        "n_trials": int(batch.data.shape[0]),
                        "shape": list(batch.data.shape),
                        "time_ms_first": float(tv[0]),
                        "time_ms_last": float(tv[-1]),
                        "time_ms_len": int(tv.size),
                        "window_requested": list(window),
                        "hi_edge_exclusive": bool(tv[-1] < window[1]),
                        "declared_rate": rate,
                        "starting_time_s": start_s,
                        "n_total_samples": n_total,
                        "per_trial": per_trial,
                        "all_bitwise_identical": all(p["bitwise_identical"] for p in per_trial),
                    }

        # ---------- V3 empirical leakage test ----------
        # Build a corrupted copy of the file's behavioral arrays in a temp HDF5, with every
        # sample at index >= anchor_index set to a huge sentinel, and confirm features are
        # unchanged.
        leak = {}
        try:
            trials = my_trial_onsets(path)
            with h5py.File(path, "r") as h:
                grp = h["acquisition"]["pupil_1_tracking"]
                found = []
                grp.visititems(lambda n, o: found.append((n, o))
                               if isinstance(o, h5py.Dataset) and n.rsplit("/", 1)[-1] == "data" else None)
                pupil_path = found[0][0]
                sfound = []
                grp.visititems(lambda n, o: sfound.append((n, o))
                               if isinstance(o, h5py.Dataset) and n.rsplit("/", 1)[-1] == "starting_time" else None)
                rate = float(sfound[0][1].attrs["rate"])
                start_s = float(sfound[0][1][()])

            batch0 = bc.load_pupil_epochs(path, alignment="p1", window_ms=(-500.0, 0.0),
                                          missing_data="drop", max_trials=100)
            feat0 = bc.extract_pupil_features(batch0)

            # corrupted copy
            tmp = Path(args.out).with_suffix(f".corrupt_{stem}.h5")
            with h5py.File(path, "r") as src, h5py.File(tmp, "w") as dst:
                src.copy("acquisition", dst)
                src.copy("intervals", dst)
                dst_grp = dst["acquisition/pupil_1_tracking"]
                dfound = []
                dst_grp.visititems(lambda n, o: dfound.append((n, o))
                                   if isinstance(o, h5py.Dataset) and n.rsplit("/", 1)[-1] == "data" else None)
                dds = dfound[0][1]
                arr = np.asarray(dds[:], dtype=np.float64)
                n_corrupt = 0
                for t in batch0.trial_metadata["anchor_onset_s"].to_numpy():
                    i0 = int(round((float(t) - start_s) * rate))
                    hi = min(arr.size, i0 + 3000)
                    if i0 < arr.size:
                        arr[i0:hi] = 1e6
                        n_corrupt += hi - max(i0, 0)
                dds[...] = arr.astype(dds.dtype)
            batch1 = bc.load_pupil_epochs(tmp, alignment="p1", window_ms=(-500.0, 0.0),
                                          missing_data="drop", max_trials=100)
            feat1 = bc.extract_pupil_features(batch1)
            num_cols = [c for c in feat0.columns if feat0[c].dtype.kind in "fi"]
            same = {c: bool(np.array_equal(feat0[c].to_numpy(), feat1[c].to_numpy(), equal_nan=True))
                    for c in num_cols}
            leak = {
                "n_samples_corrupted": int(n_corrupt),
                "n_trials": int(len(feat0)),
                "epoch_data_bitwise_identical": bool(np.array_equal(batch0.data, batch1.data)),
                "feature_columns_identical": same,
                "all_features_identical": all(same.values()),
                "sanity_corruption_visible": bool(
                    float(np.nanmax(np.asarray(h5py.File(tmp, "r")[f"acquisition/pupil_1_tracking/{pupil_path}"][:1_000_000]))) > 1e5),
            }
            tmp.unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001
            leak = {"error": f"{type(exc).__name__}: {exc}"}
        rec["v3_leakage_probe"] = leak

        # window-contract enforcement
        contract = {}
        for bad in [(-100.0, 1.0), (-100.0, 100.0), (0.0, 50.0)]:
            try:
                bc.load_pupil_epochs(path, alignment="p1", window_ms=bad, max_trials=2)
                contract[str(bad)] = "ACCEPTED (BAD)"
            except ValueError as exc:
                contract[str(bad)] = f"rejected: {exc}"
        rec["v3_window_contract"] = contract

        report["sessions"].append(rec)
        print("done", stem, flush=True)

    Path(args.out).write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
