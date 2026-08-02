r"""
Omission unit classification by CONDITION CONTRAST, two-sided, with a ramp test.

WHY NOT THE JITTER NULL
    The temporal-jitter test (classify_omission_units_jitter.py) displaces the analysis
    window by +/-200 ms, which leaves 81 per cent of the window overlapping the original.
    It therefore detects sharp transients and is blind to sustained responses: of 29 units
    whose omission-versus-control effect exceeds 5 Hz, only one reaches p = 0.05 under it,
    and their median jitter effect is 0.00 Hz. The units that carry the omission signal ramp
    over several hundred milliseconds and stay elevated, so a small displacement samples the
    same elevation.

THE CONTRAST USED HERE
    The omitted slot is compared with THE TWO DELAYS THAT FLANK IT, within the same trials.
    All three are a gray screen carrying only the fixation point, so stimulus presence is
    matched and only expectation differs, and the windows do not overlap.

    The matched full-sequence control at the same slot was tried first and rejected: that
    slot CONTAINS a stimulus, so the contrast becomes stimulus-present versus stimulus-absent
    and any visually driven unit is classified as suppressed. On one session it labelled 53
    per cent of units, with O- and O-- as numerous as O+ and O++, which is a sensory response
    and not an omission response.

NULL
    Trial labels are permuted between omission and control trials, 1,000 times, and the
    difference in mean rate recomputed. The test is TWO-SIDED: p comes from the absolute
    difference and the direction from the sign of the observed effect. The previously used
    tests were one-sided and could not report a suppressed unit at all.

CLASSES  (all units, any quality; Benjamini-Hochberg across units, q <= 0.025)
    O+    omitted slot fires above the matched control slot
    O-    below
    O++   O+ and a significant positive linear trend across the slot, same permutation null
    O--   O- and a significant negative trend

OUTPUT
    outputs/classification/omission_condition_units.csv
    outputs/classification/omission_condition_by_area.csv
    outputs/classification/omission_condition_by_area_animal.csv
    outputs/classification/omission_condition_by_session.csv
    outputs/classification/omission_condition_receipt.json
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import stats as sst

sys.path.insert(0, r"D:/workspace/omission")

import jnwb as oa
from jnwb.unit_classification import (EPOCH_ONSETS_MS, PRESENTATION_DUR_MS,
                                      precompute_condition_onsets)

NWB_DIR = r"D:/analysis/nwb"
OUT_DIR = r"D:/workspace/omission/outputs/classification"

N_SHUFFLES = 1000
ALPHA = 0.025
N_RAMP_BINS = 6
MIN_TRIALS = 6
POOL = {"V3": "V3a/d", "V3a": "V3a/d", "V3d": "V3a/d"}

# (omission condition, slot, matched full-sequence control of the same family)
PAIRS = [("AXAB", 2, "AAAB"), ("AAXB", 3, "AAAB"), ("AAAX", 4, "AAAB"),
         ("BXBA", 2, "BBBA"), ("BBXA", 3, "BBBA"), ("BBBX", 4, "BBBA"),
         ("RXRR", 2, "RRRR"), ("RRXR", 3, "RRRR"), ("RRRX", 4, "RRRR")]


def bh(p):
    p = np.asarray(p, float)
    ok = np.isfinite(p)
    q = np.full(p.shape, np.nan)
    v = p[ok]
    n = v.size
    if n == 0:
        return q
    o = np.argsort(v)
    adj = np.minimum.accumulate((v[o] * n / np.arange(n, 0, -1))[::-1])[::-1]
    r = np.empty(n)
    r[o] = np.clip(adj, 0, 1)
    q[ok] = r
    return q


def analyse_session(path, rng):
    sess = oa.read(str(path))
    onsets = precompute_condition_onsets(sess, correct_only=True)
    try:
        udf = sess.get_units()
    except Exception:
        udf = getattr(sess, "units", None)
    if udf is None or len(udf) == 0:
        return []

    om_t, ct_t = [], []
    for cond, slot, _ in PAIRS:
        a = onsets.get(cond)
        if a is None or len(a) == 0:
            continue
        a = np.asarray(a, float)
        p_on = EPOCH_ONSETS_MS[f"p{slot}"] / 1000.0
        pre = EPOCH_ONSETS_MS[f"d{slot - 1}"] / 1000.0     # delay before the omitted slot
        post = EPOCH_ONSETS_MS[f"d{slot}"] / 1000.0        # delay after it
        om_t.append(a + p_on)
        # both flanks enter as control observations; they are the same screen as the slot
        ct_t.append(a + pre)
        ct_t.append(a + post)
    if not om_t:
        return []
    om_t, ct_t = np.concatenate(om_t), np.concatenate(ct_t)
    if om_t.size < MIN_TRIALS or ct_t.size < MIN_TRIALS:
        return []

    dur = PRESENTATION_DUR_MS / 1000.0
    edges = np.linspace(0.0, dur, N_RAMP_BINS + 1)
    centres = (edges[:-1] + edges[1:]) / 2.0
    x = centres - centres.mean()
    denom = (x ** 2).sum()

    n_om, n_ct = om_t.size, ct_t.size
    allt = np.concatenate([om_t, ct_t])
    # one permutation of trial labels per shuffle, shared across units
    perm = np.array([rng.permutation(n_om + n_ct) for _ in range(N_SHUFFLES)])

    stem = os.path.basename(path).replace("_rec.nwb", "").replace(".nwb", "")
    rows = []
    for ridx in range(len(udf)):
        try:
            st = np.sort(np.asarray(sess.get_spike_times(ridx), float))
        except Exception:
            continue
        if st.size < 2:
            continue
        meta = udf.iloc[ridx]

        e = allt[:, None] + edges[None, :]
        c = np.diff(np.searchsorted(st, e.ravel()).reshape(e.shape), axis=1).astype(float)
        rate = c.sum(axis=1) / dur                       # per trial
        slope = ((c - c.mean(axis=1, keepdims=True)) @ x) / denom if denom > 0 else np.zeros(len(c))

        obs_r = rate[:n_om].mean() - rate[n_om:].mean()
        obs_s = slope[:n_om].mean() - slope[n_om:].mean()
        pr = rate[perm]
        ps = slope[perm]
        null_r = pr[:, :n_om].mean(axis=1) - pr[:, n_om:].mean(axis=1)
        null_s = ps[:, :n_om].mean(axis=1) - ps[:, n_om:].mean(axis=1)
        p_rate = (1.0 + np.sum(np.abs(null_r) >= abs(obs_r))) / (N_SHUFFLES + 1.0)
        p_ramp = (1.0 + np.sum(np.abs(null_s) >= abs(obs_s))) / (N_SHUFFLES + 1.0)

        rows.append({
            "session": stem, "unit_row": ridx, "unit_id": meta.get("unit_id", ridx),
            "area": meta.get("area"), "quality": meta.get("quality"),
            "firing_rate": meta.get("firing_rate"),
            "waveform_duration": meta.get("waveform_duration"),
            "peak_channel_id": meta.get("peak_channel_id"),
            "local_channel": meta.get("local_channel"), "probe_id": meta.get("probe_id"),
            "n_omission_trials": int(n_om), "n_control_trials": int(n_ct),
            "rate_omission_hz": float(rate[:n_om].mean()),
            "rate_control_hz": float(rate[n_om:].mean()),
            "effect_hz": float(obs_r), "p_rate": float(p_rate),
            "slope_omission": float(slope[:n_om].mean()),
            "slope_control": float(slope[n_om:].mean()),
            "slope_effect": float(obs_s), "p_ramp": float(p_ramp),
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sessions", default=None)
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    rng = np.random.default_rng(42)

    files = sorted(f for f in os.listdir(NWB_DIR) if f.endswith(".nwb"))
    if args.sessions:
        w = [s.strip() for s in args.sessions.split(",")]
        files = [f for f in files if any(x in f for x in w)]
    if args.limit:
        files = files[: args.limit]

    t0 = time.time()
    rows, failed = [], []
    for i, f in enumerate(files, 1):
        try:
            r = analyse_session(os.path.join(NWB_DIR, f), rng)
            rows += r
            print(f"[{datetime.now():%H:%M:%S}] {i}/{len(files)} {f}: {len(r)} units "
                  f"({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            failed.append({"file": f, "error": f"{type(e).__name__}: {e}"})
            print(f"[{datetime.now():%H:%M:%S}] {i}/{len(files)} {f}: FAILED {e}", flush=True)

    df = pd.DataFrame(rows)
    if df.empty:
        print("no units analysed")
        return
    df["q_rate"] = bh(df.p_rate.values)
    df["q_ramp"] = bh(df.p_ramp.values)
    df["area10"] = df.area.replace(POOL)
    df["animal"] = df.session.str.split("_").str[0].str.replace("sub-", "", regex=False)
    up = (df.q_rate <= ALPHA) & (df.effect_hz > 0)
    dn = (df.q_rate <= ALPHA) & (df.effect_hz < 0)
    rup = (df.q_ramp <= ALPHA) & (df.slope_effect > 0)
    rdn = (df.q_ramp <= ALPHA) & (df.slope_effect < 0)
    df["omission_class"] = np.where(up & rup, "O++",
                            np.where(dn & rdn, "O--",
                            np.where(up, "O+", np.where(dn, "O-", "ns"))))
    df.to_csv(os.path.join(OUT_DIR, "omission_condition_units.csv"), index=False)

    def tab(keys, name):
        out = []
        for k, g in df.groupby(keys):
            n = len(g)
            rec = dict(zip(keys, k if isinstance(k, tuple) else (k,)))
            rec["screened"] = n
            for cls in ["O++", "O+", "O-", "O--"]:
                kk = int((g.omission_class == cls).sum())
                lo = 0.0 if kk == 0 else sst.beta.ppf(.025, kk, n - kk + 1)
                hi = 1.0 if kk == n else sst.beta.ppf(.975, kk + 1, n - kk)
                rec[cls] = kk
                rec[f"{cls}_%"] = round(100 * kk / n, 2)
                rec[f"{cls}_ci95"] = f"{100*lo:.2f}-{100*hi:.2f}"
            out.append(rec)
        t = pd.DataFrame(out)
        t.to_csv(os.path.join(OUT_DIR, name), index=False)
        return t

    by_area = tab(["area10"], "omission_condition_by_area.csv")
    tab(["area10", "animal"], "omission_condition_by_area_animal.csv")
    tab(["session"], "omission_condition_by_session.csv")

    counts = {k: int(v) for k, v in df.omission_class.value_counts().items()}
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "contrast": "omitted slot vs the two delays flanking it in the same trials; all "
                    "three are the same gray screen, so stimulus presence is matched and the "
                    "windows do not overlap",
        "pairs": [[c, s, k] for c, s, k in PAIRS],
        "null": "permutation of trial labels between omission and control, two-sided",
        "n_shuffles": N_SHUFFLES, "seed": 42, "alpha_fdr": ALPHA,
        "ramp": f"least-squares slope across {N_RAMP_BINS} bins of the slot, same null",
        "classes": {"O+": "above control", "O-": "below control",
                    "O++": "O+ with a significant positive ramp",
                    "O--": "O- with a significant negative ramp"},
        "supersedes": "the temporal-jitter classifier (81 per cent window overlap, blind to "
                      "sustained responses) and the control-slot contrast (confounded by "
                      "stimulus presence)",
        "n_units": int(len(df)), "counts": counts,
        "n_sessions_ok": len(files) - len(failed), "failures": failed[:10],
        "sessions_contributing": {c: int(df[df.omission_class == c].session.nunique())
                                  for c in ["O++", "O+", "O-", "O--"]},
        "runtime_s": round(time.time() - t0, 1),
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__},
    }
    json.dump(receipt, open(os.path.join(OUT_DIR, "omission_condition_receipt.json"), "w",
                            encoding="utf-8"), indent=2)
    print(f"\nunits {len(df):,} | " + " ".join(f"{k}={v}" for k, v in counts.items()))
    print(f"sessions per class: {receipt['sessions_contributing']}")
    print(by_area[["area10", "screened", "O++", "O+", "O-", "O--"]].to_string(index=False))


if __name__ == "__main__":
    main()
