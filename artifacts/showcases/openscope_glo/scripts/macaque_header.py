"""Gate B question 4: one 001838 session's stimulus table, rates and areas; the duplicate C31 files.

Usage: python scripts/macaque_header.py ASSET_A ASSET_B OUT_JSON
HTTP range reads only. Reads the `passive_glo` and photodiode interval tables, the electrode
table and the subject fields of both assets, compares them column by column, and compares
five 1,000-sample slices of each MUAe series between the two assets.
"""
import json
import sys
import time

import fsspec
import h5py
import numpy as np
import requests

API = "https://api.dandiarchive.org/api"


def url_of(aid):
    return requests.get(f"{API}/assets/{aid}/download/", allow_redirects=False, timeout=120).headers["Location"]


def table(g):
    out = {}
    for k in g.keys():
        d = g[k]
        if isinstance(d, h5py.Dataset) and d.ndim == 1:
            v = d[()]
            out[k] = v.astype(str) if v.dtype.kind in "OS" else v
    return out


def summary(col):
    if col.dtype.kind in "U":
        vals, cnt = np.unique(col, return_counts=True)
        order = np.argsort(-cnt)[:25]
        return {"kind": "text", "n_unique": int(len(vals)), "top": {str(vals[i]): int(cnt[i]) for i in order}}
    fin = np.isfinite(col)
    vals, cnt = np.unique(col[fin], return_counts=True)
    s = {"kind": "num", "n_nan": int((~fin).sum()), "n_unique": int(len(vals))}
    if len(vals) <= 25:
        s["counts"] = {repr(float(v)): int(c) for v, c in zip(vals, cnt)}
    else:
        s["min"], s["max"] = float(vals[0]), float(vals[-1])
    return s


def main():
    a, b, out = sys.argv[1:4]
    fs = fsspec.filesystem("http")
    rec = {"assets": [a, b]}
    h = {}
    files = [fs.open(url_of(x), "rb", block_size=2 * 1024 * 1024, cache_type="blockcache") for x in (a, b)]
    try:
        H = [h5py.File(f, "r") for f in files]
        for x, f in zip((a, b), H):
            h[x] = {"glo": table(f["intervals/passive_glo"]),
                    "pd": table(f["intervals/photodiode_1_detected_changes"]),
                    "el": table(f["general/extracellular_ephys/electrodes"]),
                    "subject": {k: str(f[f"general/subject/{k}"][()]) for k in f["general/subject"].keys()}}
        A, B = h[a], h[b]
        rec["subject"] = {a: A["subject"], b: B["subject"]}
        rec["passive_glo_rows"] = len(A["glo"]["start_time"])
        rec["passive_glo_columns"] = {k: summary(v) for k, v in A["glo"].items() if k != "id"}
        rec["electrode_locations"] = summary(A["el"]["location"])
        rec["photodiode_changes"] = len(A["pd"]["start_time"])
        same = {}
        for part in ("glo", "pd", "el"):
            for k in A[part]:
                x, y = A[part][k], B[part].get(k)
                if y is None:
                    same[f"{part}/{k}"] = "missing_in_B"
                elif x.dtype.kind in "U":
                    same[f"{part}/{k}"] = bool(np.array_equal(x, y))
                else:
                    same[f"{part}/{k}"] = bool(np.array_equal(x, y, equal_nan=True))
        rec["tables_equal_A_vs_B"] = same
        n = H[0]["acquisition/probe_0_muae/probe_0_muae_data/data"].shape[0]
        slices = {}
        for p in ("probe_0_muae", "probe_1_muae"):
            for s in np.linspace(0, n - 1000, 5).astype(int):
                x = H[0][f"acquisition/{p}/{p}_data/data"][s:s + 1000]
                y = H[1][f"acquisition/{p}/{p}_data/data"][s:s + 1000]
                slices[f"{p}@{s}"] = bool(np.array_equal(x, y))
        rec["muae_slices_equal_A_vs_B"] = slices
        ts = H[0]["acquisition/probe_0_muae/probe_0_muae_data/timestamps"]
        rec["muae_rate_hz_from_step"] = float(1 / np.median(np.diff(ts[:10000])))
        rec["muae_rate_attr"] = float(H[0]["acquisition/probe_0_muae/probe_0_muae_data/starting_time"].attrs["rate"])
        g = A["glo"]
        rec["glo_start_span_s"] = [float(np.nanmin(g["start_time"])), float(np.nanmax(g["start_time"]))]
        d = np.diff(g["start_time"])
        rec["glo_start_step_median_s"] = float(np.median(d))
        for f in H:
            f.close()
    finally:
        for f in files:
            f.close()
    rec["utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(rec, open(out, "w"), indent=1, default=str)
    print(json.dumps({k: rec[k] for k in ("subject", "passive_glo_rows", "photodiode_changes", "muae_rate_hz_from_step", "muae_slices_equal_A_vs_B")}, indent=1, default=str))
    print("unequal tables:", [k for k, v in rec["tables_equal_A_vs_B"].items() if v is not True])


if __name__ == "__main__":
    main()
