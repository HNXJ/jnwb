"""List the probe LFP assets of 000253 in both versions, with ids and sizes (metadata only).

Usage: python scripts/list_probe_assets.py OUT_JSON
"""
import json
import sys

import requests

API = "https://api.dandiarchive.org/api/dandisets/000253/versions"
VERSIONS = ("0.240503.0152", "0.240923.1441")


def assets(version):
    out, url = [], f"{API}/{version}/assets/?page_size=1000"
    while url:
        r = requests.get(url, timeout=120).json()
        out += [{"path": a["path"], "asset_id": a["asset_id"], "size": a["size"]} for a in r["results"] if "probe" in a["path"]]
        url = r.get("next")
    return out


rec = {v: assets(v) for v in VERSIONS}
json.dump(rec, open(sys.argv[1], "w"), indent=1)
for v, a in rec.items():
    print(v, len(a), "probe assets", round(sum(x["size"] for x in a) / 1e9, 1), "GB")
