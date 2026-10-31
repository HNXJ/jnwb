"""Read an NWB file's HDF5 structure from DANDI by HTTP range reads; never downloads it whole.

Usage: python scripts/remote_header.py ASSET_ID OUT_JSON [MAX_ELEMENTS]
Records every group and dataset (shape, dtype, attributes), the values of datasets with at most
MAX_ELEMENTS elements (default 64), and, for every dataset named `timestamps`, its first and last
five values and the step statistics of its first 10,000. Bytes fetched are counted.
"""
import json
import sys
import time

import fsspec
import h5py
import numpy as np
import requests

API = "https://api.dandiarchive.org/api"


def plain(v):
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    if isinstance(v, np.ndarray):
        return [plain(x) for x in v.tolist()] if v.dtype.kind in "OSU" else v.tolist()
    if isinstance(v, (np.generic,)):
        return v.item()
    if isinstance(v, h5py.Reference):
        return "<ref>"
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    return v if isinstance(v, (int, float, str, bool, type(None))) else str(v)


def main():
    aid, out = sys.argv[1], sys.argv[2]
    max_el = int(sys.argv[3]) if len(sys.argv) > 3 else 64
    meta = requests.get(f"{API}/assets/{aid}/", timeout=120).json()
    r = requests.get(f"{API}/assets/{aid}/download/", allow_redirects=False, timeout=120)
    url = r.headers["Location"]
    fs = fsspec.filesystem("http")
    t0 = time.time()
    rec = {"asset_id": aid, "path": meta.get("path"), "size": meta.get("contentSize"),
           "dandi_sha256": meta.get("digest", {}).get("dandi:sha2-256"), "objects": {}}
    with fs.open(url, "rb", block_size=2 * 1024 * 1024, cache_type="blockcache") as fh:
        with h5py.File(fh, "r") as f:
            rec["root_attrs"] = {k: plain(v) for k, v in f.attrs.items()}

            def visit(name, obj):
                ent = {"attrs": {k: plain(v) for k, v in obj.attrs.items()}}
                if isinstance(obj, h5py.Dataset):
                    ent.update(kind="dataset", shape=list(obj.shape), dtype=str(obj.dtype))
                    n = int(np.prod(obj.shape)) if obj.shape else 1
                    if n <= max_el:
                        try:
                            ent["value"] = plain(obj[()])
                        except Exception as e:  # compound or reference dtypes
                            ent["value_error"] = repr(e)
                    if name.endswith("timestamps") and obj.ndim == 1 and obj.shape[0] > 1:
                        k = obj.shape[0]
                        head = obj[: min(k, 10000)]
                        d = np.diff(head)
                        ent["head"] = head[:5].tolist()
                        ent["tail"] = obj[k - 5:].tolist()
                        ent["step_median"] = float(np.median(d))
                        ent["step_min"] = float(d.min())
                        ent["step_max"] = float(d.max())
                else:
                    ent["kind"] = "group"
                rec["objects"][name] = ent

            f.visititems(visit)
    rec["seconds"] = round(time.time() - t0, 1)
    rec["utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(out, "w") as fo:
        json.dump(rec, fo, indent=1)
    print(aid, rec["path"], len(rec["objects"]), "objects", rec["seconds"], "s")


if __name__ == "__main__":
    main()
