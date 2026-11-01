"""Follow-up to lfp_clock_check.py: sample lag between versions, and VEP timing early vs late.

Usage: python scripts/lfp_clock_check2.py OGEN_PATH OLD_PROBE_PATH NEW_ASSET_ID OUT_JSON

(1) Cross-correlates the same channel (VISpm4, local_index 274) between the paper-version file
and the replaced file over 20 s to find their sample lag. (2) Computes the VEP to P1 onsets of
early main-block sequences (blocks 3-11) and late ones (blocks 87-97) under three time axes:
old ticks / 30 kHz; the replaced file's timestamps; and the replaced file's timestamps minus
their first value. The peak latency of the dominant positive deflection and the first time
the mean exceeds 5 SD of the pre-onset mean give the alignment of each axis to the stimulus
table, and its change from early to late gives the drift.
"""
import json
import sys
import time

import fsspec
import h5py
import numpy as np
import requests

API = "https://api.dandiarchive.org/api"
LFP = "acquisition/probe_1_lfp/probe_1_lfp_data"
LOCAL_INDEX = 274
FS = 1250.0
PRE, POST = 0.2, 0.3


def p1_onsets(ogen, blocks):
    with h5py.File(ogen, "r") as f:
        g = f["intervals/init_grating_presentations"]
        st, ori, blk = g["start_time"][()], g["orientation"][()], g["stimulus_block"][()]
    prev_nan = np.r_[True, ~np.isfinite(ori[:-1])]
    keep = np.isfinite(ori) & prev_nan & np.isin(blk, blocks)
    return st[keep]


def vep(read, axis, ons):
    n_pre, n_post = int(PRE * FS), int(POST * FS)
    segs = []
    for t in ons:
        i = int(np.searchsorted(axis, t))
        if n_pre <= i < len(axis) - n_post:
            segs.append(read(i - n_pre, i + n_post))
    x = np.asarray(segs, dtype=float)
    x -= x[:, :n_pre].mean(axis=1, keepdims=True)
    m = x.mean(axis=0) * 1e6
    lag = np.arange(-n_pre, n_post) / FS * 1000
    sd = m[lag < 0].std()
    post = lag > 0
    above = np.flatnonzero(post & (np.abs(m) > 5 * sd))
    k = int(np.argmax(m * post))
    return {"n": len(segs), "onset_5sd_ms": float(lag[above[0]]) if len(above) else None,
            "peak_pos_ms": float(lag[k]), "peak_pos_uV": float(m[k]), "pre_sd_uV": float(sd)}


def main():
    ogen, old_path, new_id, out = sys.argv[1:5]
    url = requests.get(f"{API}/assets/{new_id}/download/", allow_redirects=False, timeout=120).headers["Location"]
    early = p1_onsets(ogen, list(range(3, 12)))
    late = p1_onsets(ogen, list(range(87, 98)))
    rec = {"n_early": len(early), "n_late": len(late), "early_span_s": [float(early[0]), float(early[-1])],
           "late_span_s": [float(late[0]), float(late[-1])]}
    fs = fsspec.filesystem("http")
    with h5py.File(old_path, "r") as fo, fs.open(url, "rb", block_size=4 * 1024 * 1024, cache_type="blockcache") as fh, h5py.File(fh, "r") as fn:
        jo = int(np.flatnonzero(fo["general/extracellular_ephys/electrodes/local_index"][()] == LOCAL_INDEX)[0])
        jn = int(np.flatnonzero(fn["general/extracellular_ephys/electrodes/local_index"][()] == LOCAL_INDEX)[0])
        do, dn = fo[f"{LFP}/data"], fn[f"{LFP}/data"]
        a = do[2_000_000:2_025_000, jo].astype(float)
        b = dn[2_000_000:2_025_000, jn].astype(float)
        a -= a.mean(); b -= b.mean()
        lags = np.arange(-50, 51)
        cc = [np.dot(a[60:-60], np.roll(b, L)[60:-60]) / (np.linalg.norm(a[60:-60]) * np.linalg.norm(np.roll(b, L)[60:-60])) for L in lags]
        rec["xcorr_best_lag_samples"] = int(lags[int(np.argmax(cc))])
        rec["xcorr_peak_r"] = float(np.max(cc))
        rec["rms_old_uV"] = float(a.std() * 1e6)
        rec["rms_diff_uV"] = float((a - b).std() * 1e6)
        t_old = fo[f"{LFP}/timestamps"][()] / 30000.0
        t_new = fn[f"{LFP}/timestamps"][()]
        axes = {"old_ticks_over_30k": (lambda i, j: do[i:j, jo], t_old),
                "new_timestamps": (lambda i, j: dn[i:j, jn], t_new),
                "new_timestamps_minus_first": (lambda i, j: dn[i:j, jn], t_new - t_new[0])}
        for name, (read, ax) in axes.items():
            rec[name] = {"early": vep(read, ax, early), "late": vep(read, ax, late)}
            print(name, rec[name], flush=True)
    rec["utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(rec, open(out, "w"), indent=1)
    print({k: rec[k] for k in ("xcorr_best_lag_samples", "xcorr_peak_r", "rms_old_uV", "rms_diff_uV")})


if __name__ == "__main__":
    main()
