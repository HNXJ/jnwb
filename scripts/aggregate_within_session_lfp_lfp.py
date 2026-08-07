r"""
Step 3 of 3: generalize within-session LFP-LFP sliding-correlation results across sessions --
POOLING HAPPENS AFTER TESTING, never before (feedback_pool_after_testing_not_before memory;
this exact corpus produced 0/45-0/240 significant results six separate times in one week when
raw session point estimates were pooled and tested directly, despite huge single-session
effects -- see that memory for the full incident record).

DESIGN
    Per session (already computed by extract_within_session_lfp_lfp_sliding_corr.py): every
    channel pair has a real correlation, a null mean/std, per band per sliding window. Convert
    to a per-pair Z-score. Step 3 here:
    1. Collapse channel pairs to AREA pairs within each session: for a given (areaA, areaB,
       band, window), average the Z-scores of that session's own qualifying channel pairs --
       this is a WITHIN-SESSION summary, not a cross-session pool.
    2. That gives one Z per (session, areaA, areaB, band, window) -- call a session
       "significant" for that (areaA, areaB, band, window) if |Z| >= Z_THRESH.
    3. ONLY NOW pool across sessions: for each (areaA, areaB, band, window), among the sessions
       that actually had that area pair recorded (partial coverage is expected and fine, per
       instruction), count how many were significant. Test the hit-rate against the nominal
       false-positive rate (ALPHA) with an exact binomial (Clopper-Pearson) interval -- the
       same interval this project already uses for every other proportion, not a t-test on the
       raw session Z-scores.

OUTPUT
    outputs/within_session_lfp_lfp_sliding_corr/area_pair_hit_rates.csv
"""
from __future__ import annotations

import glob
import os
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

IN_DIR = r"D:/workspace/omission/outputs/within_session_lfp_lfp_sliding_corr"
Z_THRESH = 1.96
ALPHA = 0.05


def clopper_pearson(k, n, alpha=ALPHA):
    if n == 0:
        return (np.nan, np.nan)
    lo = 0.0 if k == 0 else stats.beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else stats.beta.ppf(1 - alpha / 2, k + 1, n - k)
    return float(lo), float(hi)


def load_session(path):
    d = np.load(path, allow_pickle=True)
    pairs = [p.split("|") for p in d["pairs"]]
    return {
        "real": d["real"], "null_mean": d["null_mean"], "null_std": d["null_std"],
        "n_trials": d["n_trials"], "centers_ms": d["centers_ms"], "bands": list(d["bands"]),
        "pairs": pairs,  # (scope, areaA, chA, areaB, chB)
    }


def session_area_pair_z(sess, scope):
    """Returns dict[(areaA, areaB, band_idx, window_idx)] -> list of per-channel-pair Z."""
    z = np.divide(sess["real"] - sess["null_mean"], sess["null_std"],
                 out=np.full_like(sess["real"], np.nan), where=sess["null_std"] > 0)
    out = {}
    for pi, (sc, a1, c1, a2, c2) in enumerate(sess["pairs"]):
        if sc != scope:
            continue
        key_areas = tuple(sorted((a1, a2)))
        for bi in range(z.shape[1]):
            for wi in range(z.shape[2]):
                out.setdefault((key_areas, bi, wi), []).append(z[pi, bi, wi])
    return out


def main():
    files = sorted(glob.glob(os.path.join(IN_DIR, "*.npz")))
    print(f"{len(files)} session files found")
    if not files:
        raise SystemExit("no session .npz files -- run extract_within_session_lfp_lfp_"
                         "sliding_corr.py first")

    rows = []
    for scope in ("within_area", "between_area"):
        # session_hits[(areas, band_idx, window_idx)] -> list of bool (one per session)
        session_hits = {}
        bands = None
        centers_ms = None
        for f in files:
            sess = load_session(f)
            bands = bands or sess["bands"]
            centers_ms = centers_ms if centers_ms is not None else sess["centers_ms"]
            apz = session_area_pair_z(sess, scope)
            for key, zlist in apz.items():
                zlist = [z for z in zlist if np.isfinite(z)]
                if not zlist:
                    continue
                sess_z = float(np.mean(zlist))
                session_hits.setdefault(key, []).append(abs(sess_z) >= Z_THRESH)

        for (areas, bi, wi), hits in session_hits.items():
            n = len(hits)
            k = int(sum(hits))
            lo, hi = clopper_pearson(k, n)
            rows.append({
                "scope": scope, "areaA": areas[0], "areaB": areas[1],
                "band": bands[bi], "window_ms": float(centers_ms[wi]),
                "n_sessions": n, "n_significant_sessions": k,
                "hit_rate": k / n if n else np.nan,
                "ci95_lo": lo, "ci95_hi": hi,
                "above_chance": lo > ALPHA if np.isfinite(lo) else False,
            })

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(IN_DIR, "area_pair_hit_rates.csv"), index=False)
    print(f"WROTE {IN_DIR}/area_pair_hit_rates.csv ({len(out)} rows)")
    if len(out):
        top = out.sort_values("hit_rate", ascending=False).head(15)
        print(top[["scope", "areaA", "areaB", "band", "window_ms", "n_sessions",
                   "n_significant_sessions", "hit_rate", "ci95_lo"]].to_string())


if __name__ == "__main__":
    main()
