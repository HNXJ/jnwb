"""Shared constants and helpers for the showcase scripts (study code, not jnwb)."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
JNWB_CHECKOUT = Path("C:/workspace/jnwb")
DATA = Path("E:/analysis/jnwb_data/dandi000253")
RESULTS = REPO / "results"
SEED = 20261012

# Import jnwb from the checkout, never the site-packages copy.
if str(JNWB_CHECKOUT) not in sys.path:
    sys.path.insert(0, str(JNWB_CHECKOUT))
import jnwb  # noqa: E402

if Path(jnwb.__file__).resolve().parents[1] != JNWB_CHECKOUT.resolve():
    raise SystemExit(f"jnwb imported from {jnwb.__file__}, not the checkout {JNWB_CHECKOUT}")

AREAS = ("VISp", "VISl", "VISrl", "VISal", "VISpm", "VISam")
AREA_RE = r"^(VISpm|VISp|VISl|VISrl|VISal|VISam)(?=[0-9]|$)"


def git_head(path):
    return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=True).stdout.strip()


def git_dirty(path):
    out = subprocess.run(["git", "-C", str(path), "status", "--porcelain"], capture_output=True,
                         text=True, check=True).stdout
    return [ln for ln in out.splitlines() if ln.strip()]


def software_identity():
    return {"jnwb_file": jnwb.__file__, "jnwb_version": jnwb.__version__,
            "jnwb_commit": git_head(JNWB_CHECKOUT), "jnwb_dirty": git_dirty(JNWB_CHECKOUT),
            "script_commit": git_head(REPO), "script_dirty": git_dirty(REPO),
            "python": sys.version.split()[0]}


def assets():
    """Pinned assets from the download receipt: {session_id: record}."""
    out = {}
    with open(REPO / "receipts" / "download_000253_ogen.jsonl") as f:
        for line in f:
            r = json.loads(line)
            ses = Path(r["path"]).name.split("_")[1].removeprefix("ses-")
            out[ses] = r
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(8 << 20):
            h.update(b)
    return h.hexdigest()


def receipt(extra):
    rec = dict(extra)
    rec.update(software_identity())
    rec["command"] = " ".join([os.path.basename(sys.executable)] + sys.argv)
    rec["seed"] = SEED
    return rec
