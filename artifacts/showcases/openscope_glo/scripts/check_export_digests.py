"""Check every replication's report_sha256 and receipt sha256 in export/openscope_glo.json against tracked files.

Usage: python scripts/check_export_digests.py
For each digest, hashes the committed blob (git show HEAD:<path>) of every tracked file in the
verification folders and the named receipts, and prints MATCH or FAIL per digest.
"""
import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def blob(path):
    return subprocess.run(["git", "-C", str(REPO), "show", f"HEAD:{path}"], capture_output=True, check=True).stdout


tracked = subprocess.run(["git", "-C", str(REPO), "ls-files", "_verify_xhigh", "_verify_rev2", "_verify_clock", "_verify_s2v2"],
                         capture_output=True, text=True, check=True).stdout.split()
by_digest = {hashlib.sha256(blob(p)).hexdigest(): p for p in tracked}
rec = json.load(open(REPO / "export" / "openscope_glo.json", encoding="utf-8"))
bad = 0
for e in rec["entries"]:
    for rep in e["replications"]:
        p = by_digest.get(rep["report_sha256"])
        print(e["id"], "replication", rep["seed"], "MATCH " + p if p else "FAIL")
        bad += p is None
    for r in e["receipts"]:
        ok = hashlib.sha256(blob(r["name"])).hexdigest() == r["sha256"]
        print("   ", r["name"], "MATCH" if ok else "FAIL")
        bad += not ok
print("failures", bad, "of", sum(len(e["replications"]) + len(e["receipts"]) for e in rec["entries"]))
