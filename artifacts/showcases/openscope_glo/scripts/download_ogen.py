"""Download the 14 `_ogen.nwb` assets of DANDI 000253, pinned by asset id, SHA-256 checked.

Usage: python scripts/download_ogen.py
Writes new files only into E:/analysis/jnwb_data/dandi000253/; an existing file is hashed and
never overwritten. One JSON line per asset goes to receipts/download_000253_ogen.jsonl.
"""
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

API = "https://api.dandiarchive.org/api"
DANDISET = "000253"
VERSION = "0.240503.0152"
LATEST = "0.240923.1441"
DEST = Path("E:/analysis/jnwb_data/dandi000253")
REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / "receipts" / "download_000253_ogen.jsonl"
CHUNK = 8 * 1024 * 1024


def list_assets(version):
    url = f"{API}/dandisets/{DANDISET}/versions/{version}/assets/?page_size=1000&order=path"
    rows = []
    while url:
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        page = r.json()
        rows += page["results"]
        url = page.get("next")
    return rows


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(CHUNK):
            h.update(b)
    return h.hexdigest()


def fetch(asset):
    aid, path = asset["asset_id"], asset["path"]
    meta = requests.get(f"{API}/assets/{aid}/", timeout=120)
    meta.raise_for_status()
    digest = meta.json()["digest"]["dandi:sha2-256"]
    size = asset["size"]
    out = DEST / Path(path).name
    rec = {"asset_id": aid, "path": path, "size": size, "dandi_sha256": digest,
           "dest": str(out), "version": VERSION}
    if out.exists():
        local = sha256_file(out)
        rec.update(action="present_not_overwritten", local_sha256=local,
                   match=local == digest, local_size=out.stat().st_size)
        return rec
    part = out.with_name(out.name + ".part")
    h = hashlib.sha256()
    n = 0
    t0 = time.time()
    with requests.get(f"{API}/assets/{aid}/download/", stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(part, "wb") as f:
            for b in r.iter_content(CHUNK):
                f.write(b)
                h.update(b)
                n += len(b)
            f.flush()
            os.fsync(f.fileno())
    local = h.hexdigest()
    ok = local == digest and n == size
    if ok:
        part.rename(out)
    rec.update(action="downloaded" if ok else "mismatch_kept_as_part", local_sha256=local,
               match=ok, local_size=n, seconds=round(time.time() - t0, 1),
               utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    return rec


def main():
    pinned = [a for a in list_assets(VERSION) if a["path"].endswith("_ogen.nwb")]
    latest = {a["path"]: a["asset_id"] for a in list_assets(LATEST) if a["path"].endswith("_ogen.nwb")}
    if len(pinned) != 14:
        sys.exit(f"expected 14 ogen assets, found {len(pinned)}")
    same = [latest.get(a["path"]) == a["asset_id"] for a in pinned]
    print(f"{len(pinned)} ogen assets; identical asset id in {LATEST}: {sum(same)}/14", flush=True)
    RECEIPT.parent.mkdir(exist_ok=True)
    with ThreadPoolExecutor(4) as ex, open(RECEIPT, "a") as log:
        for rec in ex.map(fetch, pinned):
            rec["same_asset_id_in_latest"] = latest.get(rec["path"]) == rec["asset_id"]
            log.write(json.dumps(rec) + "\n")
            log.flush()
            print(rec["path"], rec["action"], rec["match"], flush=True)


if __name__ == "__main__":
    main()
