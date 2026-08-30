"""V1b -- where does the '500 Hz' description live, and is there PHYSICAL evidence for it?

Two independent lines of evidence, neither relying on metadata text:
  A) exhaustive attribute dump at EVERY level under acquisition/{pupil_1_tracking,eye_1_tracking}
     (the outer group, any nested group, and the data/starting_time datasets), so a description
     string stored one level deeper cannot be missed.
  B) physical rate evidence from the samples themselves:
     - linear-interpolation signature: fraction of odd(/even)-index samples that equal the mean
       of their two neighbours to within tol (the signature of 500 Hz linearly upsampled to a
       declared 1000 Hz)
     - Welch PSD: fraction of total power above 250 Hz (the 500 Hz Nyquist). A genuine 500 Hz
       acquisition presented on a 1 kHz grid must have near-zero power in 250-500 Hz.
     Both are computed on the SAME contiguous mid-session chunk for pupil and both gaze channels.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import h5py
import numpy as np
from scipy import signal as sps


def _s(v):
    if isinstance(v, (bytes, np.bytes_)):
        return v.decode("utf-8", "replace")
    if isinstance(v, np.ndarray) and v.shape == ():
        return _s(v.item())
    if isinstance(v, np.ndarray):
        return [_s(x) for x in v.tolist()]
    if isinstance(v, (np.floating, np.integer)):
        return v.item()
    return v


def dump_attrs(group, prefix=""):
    out = {}
    out[prefix or "/"] = {k: _s(v) for k, v in group.attrs.items()}

    def visit(name, obj):
        out[f"{prefix}/{name}"] = {k: _s(v) for k, v in obj.attrs.items()}

    group.visititems(visit)
    return out


def interp_signature(x, tol_rel=1e-6):
    x = np.asarray(x, dtype=np.float64)
    if x.size < 100:
        return None
    mid = (x[:-2] + x[2:]) / 2.0
    err = np.abs(x[1:-1] - mid)
    scale = max(float(np.std(x)), 1e-12)
    hit = err < tol_rel * scale
    idx = np.arange(1, x.size - 1)
    return {
        "frac_equals_neighbour_mean_all": float(np.mean(hit)),
        "frac_equals_neighbour_mean_odd_index": float(np.mean(hit[idx % 2 == 1])),
        "frac_equals_neighbour_mean_even_index": float(np.mean(hit[idx % 2 == 0])),
        "tol_rel": tol_rel,
    }


def psd_highband(x, fs=1000.0):
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size < 4096:
        return None
    f, p = sps.welch(x - x.mean(), fs=fs, nperseg=4096, noverlap=2048)
    tot = float(np.trapezoid(p, f))
    def band(lo, hi):
        m = (f >= lo) & (f < hi)
        return float(np.trapezoid(p[m], f[m])) / tot if tot > 0 else float("nan")
    return {
        "frac_power_0_50": band(0, 50),
        "frac_power_50_250": band(50, 250),
        "frac_power_250_500": band(250, 500),
        "frac_power_450_500": band(450, 500),
        "ratio_250_500_over_50_250": (band(250, 500) / band(50, 250)) if band(50, 250) > 0 else float("nan"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--chunk", type=int, default=2_000_000)
    args = ap.parse_args()

    import omission as oa
    files = sorted(oa.paths.nwb_dir().glob("*.nwb"))
    out = {"sessions": []}
    for f in files:
        rec = {"session": f.stem}
        with h5py.File(f, "r") as h:
            acq = h["acquisition"]
            for key, tag in (("pupil_1_tracking", "pupil"), ("eye_1_tracking", "gaze")):
                if key not in acq:
                    rec[tag] = {"absent": True}
                    continue
                grp = acq[key]
                info = {"attrs_tree": dump_attrs(grp, prefix=f"acquisition/{key}")}
                # locate the data dataset (own traversal, deepest-first-name sort)
                found = []
                grp.visititems(lambda n, o: found.append((n, o))
                               if isinstance(o, h5py.Dataset) and n.rsplit("/", 1)[-1] == "data" else None)
                if found:
                    ds = found[0][1]
                    n = ds.shape[0]
                    lo = max(0, n // 2 - args.chunk // 2)
                    hi = min(n, lo + args.chunk)
                    if ds.ndim == 1:
                        chans = {"ch0": np.asarray(ds[lo:hi], dtype=np.float64)}
                    else:
                        arr = np.asarray(ds[lo:hi, :], dtype=np.float64)
                        chans = {f"ch{c}": arr[:, c] for c in range(arr.shape[1])}
                    info["chunk"] = [int(lo), int(hi)]
                    info["interp_signature"] = {c: interp_signature(v) for c, v in chans.items()}
                    info["psd"] = {c: psd_highband(v) for c, v in chans.items()}
                rec[tag] = info
        out["sessions"].append(rec)
        print("done", f.stem, flush=True)
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
