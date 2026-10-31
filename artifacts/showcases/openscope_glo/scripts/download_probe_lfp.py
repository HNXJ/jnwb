"""Download the two probe files authorised on 2026-10-12 (DECISIONS.md (b)), SHA-256 checked.

Usage: python scripts/download_probe_lfp.py
Version 0.240923.1441: probe 1 of sessions 1232959154 and 1203581890. Asset id, size and digest
come from the DANDI API; stops before any download if a file is over 10 GB. Writes new files only
into E:/dandi/000253_lfp_replaced/ and one JSON line per asset to
receipts/download_000253_probe_lfp.jsonl.
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests

API = "https://api.dandiarchive.org/api"
VERSION = "0.240923.1441"
PATHS = ("sub-649323/sub-649323_ses-1232959154_probe-1_ecephys.nwb",
         "sub-632485/sub-632485_ses-1203581890_probe-1_ecephys.nwb")
DEST = Path("E:/dandi/000253_lfp_replaced")
RECEIPT = Path(__file__).resolve().parents[1] / "receipts" / "download_000253_probe_lfp.jsonl"
CHUNK = 8 * 1024 * 1024
LIMIT = 10e9


def lookup(path):
    r = requests.get(f"{API}/dandisets/000253/versions/{VERSION}/assets/", params={"path": path}, timeout=120)
    r.raise_for_status()
    hits = [a for a in r.json()["results"] if a["path"] == path]
    assert len(hits) == 1, (path, hits)
    a = hits[0]
    meta = requests.get(f"{API}/assets/{a['asset_id']}/", timeout=120)
    meta.raise_for_status()
    return {"asset_id": a["asset_id"], "path": path, "size": a["size"], "dandi_sha256": meta.json()["digest"]["dandi:sha2-256"]}


def main():
    recs = [lookup(p) for p in PATHS]
    for r in recs:
        print(r["path"], r["asset_id"], r["size"], flush=True)
    if any(r["size"] > LIMIT for r in recs):
        sys.exit("a file is over 10 GB; nothing downloaded")
    DEST.mkdir(parents=True, exist_ok=True)
    for rec in recs:
        out = DEST / Path(rec["path"]).name
        assert not out.exists(), out
        part = out.with_name(out.name + ".part")
        h, n, t0 = hashlib.sha256(), 0, time.time()
        with requests.get(f"{API}/assets/{rec['asset_id']}/download/", stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(part, "wb") as f:
                for b in r.iter_content(CHUNK):
                    f.write(b)
                    h.update(b)
                    n += len(b)
                f.flush()
                os.fsync(f.fileno())
        local = h.hexdigest()
        ok = local == rec["dandi_sha256"] and n == rec["size"]
        if ok:
            part.rename(out)
        rec.update(version=VERSION, dest=str(out), local_sha256=local, local_size=n, match=ok,
                   action="downloaded" if ok else "mismatch_kept_as_part", seconds=round(time.time() - t0, 1),
                   utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        with open(RECEIPT, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(rec, flush=True)


if __name__ == "__main__":
    main()
