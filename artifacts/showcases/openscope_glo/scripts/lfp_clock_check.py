"""Gate B question 2: which 000253 probe-file version gives an LFP clock in session seconds.

Usage: python scripts/lfp_clock_check.py OGEN_PATH OLD_PROBE_PATH NEW_ASSET_ID OUT_JSON

Reads the replaced (0.240923.1441) probe file by HTTP range reads only, and the paper-version
(0.240503.0152) probe file from its local copy. For one visual-cortex channel present in both,
it compares (1) the raw samples (same signal or not), (2) the two time axes sample by sample,
and (3) the visual evoked potential to the first grating onsets of the main block under each
time axis, with grating start_time from the ogen file as the stimulus clock. Old ticks are
converted at the 30 kHz probe clock the step of 24 ticks implies (1,250 Hz LFP); that factor is
the hypothesis under test, not an assumption carried forward.
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
N_ONSETS = 150
PRE, POST = 0.1, 0.3  # seconds


def onsets(ogen):
    with h5py.File(ogen, "r") as f:
        g = f["intervals/init_grating_presentations"]
        st = g["start_time"][()]
        ori = g["orientation"][()]
        blk = g["stimulus_block"][()]
    keep = np.isfinite(ori) & (blk >= 3) & (blk <= 41)
    return st[keep][:: 4][:N_ONSETS]  # every 4th row: spaced 1 s apart, mostly P1 onsets


def vep(read_rows, t_axis, ons, fs):
    n_pre, n_post = int(round(PRE * fs)), int(round(POST * fs))
    segs = []
    for t in ons:
        i = int(np.searchsorted(t_axis, t))
        if i - n_pre < 0 or i + n_post > len(t_axis):
            continue
        segs.append(read_rows(i - n_pre, i + n_post))
    x = np.asarray(segs)
    x = x - x[:, :n_pre].mean(axis=1, keepdims=True)
    m = x.mean(axis=0)
    lag = (np.arange(-n_pre, n_post)) / fs * 1000.0
    post = lag > 0
    k = int(np.argmax(np.abs(m[post])))
    return {"n_epochs": len(segs), "peak_latency_ms": float(lag[post][k]),
            "peak_uV": float(m[post][k] * 1e6), "pre_sd_uV": float(m[~post].std() * 1e6),
            "mean_uV": (m * 1e6).round(2).tolist(), "lag_ms": lag.round(2).tolist()}


def main():
    ogen, old_path, new_id, out = sys.argv[1:5]
    url = requests.get(f"{API}/assets/{new_id}/download/", allow_redirects=False, timeout=120).headers["Location"]
    ons = onsets(ogen)
    rec = {"ogen": ogen, "old_probe": old_path, "new_asset_id": new_id, "n_onsets": len(ons),
           "onset_selection": "grating rows with orientation, blocks 3-41, every 4th row, first 150"}
    with h5py.File(old_path, "r") as fo:
        eo = fo["general/extracellular_ephys/electrodes"]
        old_loc = eo["location"][()].astype(str)
        old_li = eo["local_index"][()]
        old_ts = fo[f"{LFP}/timestamps"][()]
        fs = fsspec.filesystem("http")
        with fs.open(url, "rb", block_size=4 * 1024 * 1024, cache_type="blockcache") as fh, h5py.File(fh, "r") as fn:
            en = fn["general/extracellular_ephys/electrodes"]
            new_loc = en["location"][()].astype(str)
            new_li = en["local_index"][()]
            new_ts = fn[f"{LFP}/timestamps"][()]
            dn = fn[f"{LFP}/data"]
            rec["new_chunks"] = list(dn.chunks) if dn.chunks else None
            vis_old = [j for j, l in enumerate(old_loc) if l.startswith("VIS")]
            if not vis_old:
                sys.exit("no VIS channel on this probe")
            jo = vis_old[len(vis_old) // 2]
            jn = int(np.flatnonzero(new_li == old_li[jo])[0])
            rec.update(channel_location=old_loc[jo], local_index=int(old_li[jo]),
                       new_location=new_loc[jn], n_channels_old=len(old_loc), n_channels_new=len(new_loc))
            do = fo[f"{LFP}/data"]
            a = do[1_000_000:1_002_000, jo]
            b = dn[1_000_000:1_002_000, jn]
            rec["same_samples_2000"] = bool(np.array_equal(a, b))
            rec["max_abs_diff_2000_uV"] = float(np.max(np.abs(a - b)) * 1e6)
            t_old = old_ts / 30000.0
            d = new_ts - t_old
            rec["new_minus_old_over_30k_s"] = {"first": float(d[0]), "last": float(d[-1]),
                                               "drift_ms": float((d[-1] - d[0]) * 1000)}
            rec["new_rate_hz"] = float(1 / np.median(np.diff(new_ts[:10000])))
            rec["new_span_s"] = [float(new_ts[0]), float(new_ts[-1])]
            rec["stim_span_s"] = [float(ons[0]), float(ons[-1])]
            rec["vep_new_axis"] = vep(lambda i, j: dn[i:j, jn], new_ts, ons, 1250.0)
            rec["vep_old_axis_ticks_over_30k"] = vep(lambda i, j: do[i:j, jo], t_old, ons, 1250.0)
    rec["utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(rec, open(out, "w"), indent=1)
    for k in ("channel_location", "same_samples_2000", "max_abs_diff_2000_uV", "new_minus_old_over_30k_s", "new_rate_hz"):
        print(k, rec[k])
    for k in ("vep_new_axis", "vep_old_axis_ticks_over_30k"):
        v = rec[k]
        print(k, v["n_epochs"], v["peak_latency_ms"], round(v["peak_uV"], 1), round(v["pre_sd_uV"], 2))


if __name__ == "__main__":
    main()
