r"""
Step 2 of 2: generalize within-session SPK-LFP sliding-correlation results
(extract_within_session_spk_lfp_sliding_corr.py) across sessions -- POOLING HAPPENS AFTER
TESTING, same design as aggregate_within_session_lfp_lfp.py (imports its clopper_pearson/
Z_THRESH/ALPHA rather than reimplementing a fourth Clopper-Pearson).

DESIGN (mirrors aggregate_within_session_lfp_lfp.py, adapted for unit-channel pairs instead of
channel-channel pairs)
    1. Per session, per (area, band, window): average the Z-scores of that session's own
       qualifying unit-channel pairs in that area (a unit's spike rate vs its own probe's band
       power) -- a WITHIN-SESSION summary, not a cross-session pool.
    2. That gives one Z per (session, area, band, window) -- a session counts as "significant"
       for that cell if |Z| >= Z_THRESH (1.96, same threshold/sidedness as the LFP-LFP
       aggregator, for direct comparability).
    3. Pool across sessions: among sessions with that area recorded (partial coverage
       expected), count how many were significant; exact Clopper-Pearson interval vs ALPHA.

OUTPUT
    outputs/within_session_spk_lfp_sliding_corr/area_hit_rates.csv
"""
from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from aggregate_within_session_lfp_lfp import clopper_pearson, Z_THRESH, ALPHA  # noqa: E402
from jnwb import paths as _P

IN_DIR = _P.REPO_ROOT / "outputs/within_session_spk_lfp_sliding_corr"


def load_session(path):
    d = np.load(path, allow_pickle=True)
    pairs = [p.split("|") for p in d["pairs"]]  # (unit_row, area, channel)
    return {
        "real": d["real"], "null_mean": d["null_mean"], "null_std": d["null_std"],
        "n_trials": d["n_trials"], "centers_ms": d["centers_ms"], "bands": list(d["bands"]),
        "pairs": pairs,
    }


def session_area_z(sess):
    """Returns dict[(area, band_idx, window_idx)] -> list of per-unit-channel-pair Z."""
    z = np.divide(sess["real"] - sess["null_mean"], sess["null_std"],
                 out=np.full_like(sess["real"], np.nan), where=sess["null_std"] > 0)
    out = {}
    for pi, (unit_row, area, ch) in enumerate(sess["pairs"]):
        for bi in range(z.shape[1]):
            for wi in range(z.shape[2]):
                out.setdefault((area, bi, wi), []).append(z[pi, bi, wi])
    return out


def main():
    files = sorted(glob.glob(os.path.join(IN_DIR, "*.npz")))
    print(f"{len(files)} session files found")
    if not files:
        raise SystemExit("no session .npz files -- run extract_within_session_spk_lfp_"
                         "sliding_corr.py first")

    session_hits = {}   # (area, band_idx, window_idx) -> list of bool (one per session)
    bands = None
    centers_ms = None
    for f in files:
        sess = load_session(f)
        bands = bands or sess["bands"]
        centers_ms = centers_ms if centers_ms is not None else sess["centers_ms"]
        az = session_area_z(sess)
        for key, zlist in az.items():
            zlist = [z for z in zlist if np.isfinite(z)]
            if not zlist:
                continue
            sess_z = float(np.mean(zlist))
            session_hits.setdefault(key, []).append(abs(sess_z) >= Z_THRESH)

    rows = []
    for (area, bi, wi), hits in session_hits.items():
        n = len(hits)
        k = int(sum(hits))
        lo, hi = clopper_pearson(k, n)
        rows.append({
            "area": area, "band": bands[bi], "window_ms": float(centers_ms[wi]),
            "n_sessions": n, "n_significant_sessions": k,
            "hit_rate": k / n if n else np.nan,
            "ci95_lo": lo, "ci95_hi": hi,
            "above_chance": lo > ALPHA if np.isfinite(lo) else False,
            "z_thresh": Z_THRESH, "alpha": ALPHA,
        })

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(IN_DIR, "area_hit_rates.csv"), index=False)
    n_above = int(out.above_chance.sum()) if len(out) else 0
    print(f"WROTE {IN_DIR}/area_hit_rates.csv ({len(out)} area x band x window cells, "
         f"{n_above} with hit-rate CI lower bound above alpha={ALPHA})")
    if len(out):
        top = out.sort_values("hit_rate", ascending=False).head(15)
        print(top[["area", "band", "window_ms", "n_sessions",
                   "n_significant_sessions", "hit_rate", "ci95_lo", "above_chance"]]
             .to_string())


if __name__ == "__main__":
    main()
