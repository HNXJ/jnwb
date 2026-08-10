#!/usr/bin/env python3
r"""
Figure 4 v4: per-area ranking, 2026-08-06.

Two analyses, all units per area (not S+-restricted -- this is the general area-comparison
design, distinct from the earlier S+-PFC-only sanity checks):

PART 1 -- real-stimulus positive control (must be decodable; what matters now is which area
decodes it best). AAAB vs BBBA, one decode per slot (p2/p3/p4, each its own d-p-d window, same
trials reused at each window per direction -- NOT pooled across slots, since it's the same
physical trials read 3 times, pooling would be pseudo-replication). 5-fold CV + 100-shuffle
label-permutation null, per (session, area, slot).

PART 2 -- omitted identity, POOLED across all three slots' condition codes (these ARE
independent trials per slot, pooling is legitimate) using the CORRECTED mapping (p4's A/B were
swapped in jnwb/omission_identity.py before this script was written -- see that file's 2026-08-06
fix note):
    X|A = AXAB (p2) + AAXB (p3) + BBBX (p4)
    X|B = BXBA (p2) + BBXA (p3) + AAAX (p4)
    X|R = RXRR (p2) + RRXR (p3) + RRRX (p4)
Two validation schemes, both directions each:
    - CHRONOLOGICAL half-split: sort pooled A+B trials by absolute start_time, train on the
      first half, test on the second, and vice versa.
    - RANDOM half-split: same pooled trials, shuffled 50/50 (StratifiedKFold(2)).
For X|R: the classifier trained under EACH scheme (using whichever half serves as "train" in
that run) is applied to the pooled R trials; reports the fraction predicted "A" vs "B" (hard
labels, not calibrated probabilities -- cheaper, and matches the spirit of "should report
[0.5, 0.5]" as an expected fraction, not a literal softmax output).

Both parts report a per-area ranking (best/worst) even where accuracy sits near chance, since
that ranking is itself the requested output.

OUTPUT
    outputs/classification/fig04_v4_stim_by_area.csv
    outputs/classification/fig04_v4_omission_by_area.csv
"""
from __future__ import annotations

import pathlib
import sys
import time

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import jnwb as oa  # noqa: E402
from jnwb.omission_identity import OMISSION_IDENTITY_CONDITIONS  # noqa: E402
from jnwb import paths as _P

OUT_DIR = REPO_ROOT / "outputs" / "classification"
NWB_DIR = pathlib.Path(_P.nwb_dir())
AREAS = ["FEF", "PFC", "TEO", "V4", "V3", "V2", "V1"]
RANDOM_STATE = 42

STIM_SLOTS = {
    "p2": {"A": "AAAB", "B": "BBBA", "window_ms": (531.0, 2062.0)},
    "p3": {"A": "AAAB", "B": "BBBA", "window_ms": (1562.0, 3093.0)},
    "p4": {"A": "BBBA", "B": "AAAB", "window_ms": (2593.0, 4124.0)},  # real p4 content flips
}


def spikemat(session, unit_ids, onsets, win_ms):
    win_sec = (win_ms[0] / 1000.0, win_ms[1] / 1000.0)
    X = np.zeros((len(onsets), len(unit_ids)))
    for j, u_id in enumerate(unit_ids):
        st = session.get_spike_times(u_id)
        st = np.sort(st) if st is not None and len(st) else np.array([])
        for i, onset in enumerate(onsets):
            lo = np.searchsorted(st, onset + win_sec[0], side="left")
            hi = np.searchsorted(st, onset + win_sec[1], side="right")
            X[i, j] = hi - lo
    return X


def decode_stim_positive_control(session, unit_ids, stem, area):
    rows = []
    for slot_key, cfg in STIM_SLOTS.items():
        ea = session.get_epochs(phase=2, condition=cfg["A"])
        eb = session.get_epochs(phase=2, condition=cfg["B"])
        if len(unit_ids) < 2 or len(ea) < 6 or len(eb) < 6:
            rows.append({"session": stem, "area": area, "slot": slot_key,
                        "status": "insufficient_data"})
            continue
        n_min = min(len(ea), len(eb))
        rng = np.random.default_rng(RANDOM_STATE)
        ia = rng.choice(len(ea), n_min, replace=False)
        ib = rng.choice(len(eb), n_min, replace=False)
        onsets = np.concatenate([ea["start_time"].values[ia], eb["start_time"].values[ib]])
        y = np.array([0] * n_min + [1] * n_min)
        X = spikemat(session, unit_ids, onsets, cfg["window_ms"])

        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
        accs = []
        for tr, te in cv.split(X, y):
            p = Pipeline([("sc", StandardScaler()), ("clf", SVC(kernel="linear", C=1.0, random_state=RANDOM_STATE))])
            p.fit(X[tr], y[tr]); accs.append(p.score(X[te], y[te]))
        acc = float(np.mean(accs))

        rng2 = np.random.default_rng(RANDOM_STATE + 1)
        perm_accs = []
        for _ in range(100):
            y_perm = rng2.permutation(y)
            p_accs = []
            for tr, te in cv.split(X, y_perm):
                p = Pipeline([("sc", StandardScaler()), ("clf", SVC(kernel="linear", C=1.0, random_state=RANDOM_STATE))])
                p.fit(X[tr], y_perm[tr]); p_accs.append(p.score(X[te], y_perm[te]))
            perm_accs.append(np.mean(p_accs))
        p_val = float(np.mean(np.array(perm_accs) >= acc))
        p_val = p_val if p_val > 0 else 1.0 / 101

        rows.append({"session": stem, "area": area, "slot": slot_key, "status": "success",
                    "n_units": len(unit_ids), "n_per_class": n_min, "accuracy": acc,
                    "perm_null_mean": float(np.mean(perm_accs)), "p_val": p_val})
    return rows


def decode_omission_pooled(session, unit_ids, stem, area):
    cfg2, cfg3, cfg4 = (OMISSION_IDENTITY_CONDITIONS["p2"], OMISSION_IDENTITY_CONDITIONS["p3"],
                        OMISSION_IDENTITY_CONDITIONS["p4"])
    wins = {"p2": (1031.0, 1562.0), "p3": (2062.0, 2593.0), "p4": (3093.0, 3624.0)}

    def pooled(cls_key):
        onsets, times = [], []
        for slot_key, cfg in (("p2", cfg2), ("p3", cfg3), ("p4", cfg4)):
            e = session.get_epochs(phase=2, condition=cfg[cls_key])
            if len(e) == 0:
                continue
            w = wins[slot_key]
            onsets.append((e["start_time"].values, w))
        return onsets

    onsets_a, onsets_b, onsets_r = pooled("A"), pooled("B"), pooled("R")
    n_a, n_b, n_r = sum(len(o) for o, _ in onsets_a), sum(len(o) for o, _ in onsets_b), sum(len(o) for o, _ in onsets_r)
    base = {"session": stem, "area": area, "n_units": len(unit_ids), "n_A": n_a, "n_B": n_b, "n_R": n_r}
    if len(unit_ids) < 2 or n_a < 6 or n_b < 6:
        return {**base, "status": "insufficient_data"}

    def build_X_t(onset_groups):
        Xs, ts = [], []
        for onsets, win in onset_groups:
            if len(onsets) == 0:
                continue
            Xs.append(spikemat(session, unit_ids, onsets, win))
            ts.append(onsets)
        return (np.concatenate(Xs, axis=0), np.concatenate(ts)) if Xs else (np.zeros((0, len(unit_ids))), np.array([]))

    Xa, ta = build_X_t(onsets_a)
    Xb, tb = build_X_t(onsets_b)
    Xr, tr_ = build_X_t(onsets_r)
    X = np.concatenate([Xa, Xb], axis=0)
    y = np.array([0] * len(Xa) + [1] * len(Xb))
    t = np.concatenate([ta, tb])

    def fit_score(train_idx, test_idx):
        p = Pipeline([("sc", StandardScaler()), ("clf", SVC(kernel="linear", C=1.0, random_state=RANDOM_STATE))])
        p.fit(X[train_idx], y[train_idx])
        acc = p.score(X[test_idx], y[test_idx])
        return p, acc

    result = {**base, "status": "success"}

    # -- chronological half-split, both directions --
    order = np.argsort(t)
    mid = len(order) // 2
    first_half, second_half = order[:mid], order[mid:]
    if len(set(y[first_half])) == 2 and len(set(y[second_half])) == 2:
        p_fwd, acc_fwd = fit_score(first_half, second_half)
        p_bwd, acc_bwd = fit_score(second_half, first_half)
        result["acc_chrono_train1st_test2nd"] = acc_fwd
        result["acc_chrono_train2nd_test1st"] = acc_bwd
        result["acc_chrono_mean"] = float(np.mean([acc_fwd, acc_bwd]))
        if len(Xr):
            for name, p in (("fwd", p_fwd), ("bwd", p_bwd)):
                preds = p.predict(Xr)
                result[f"R_frac_pred_B_chrono_{name}"] = float(np.mean(preds == 1))
    else:
        result["acc_chrono_mean"] = float("nan")

    # -- random half-split, both directions --
    cv = StratifiedKFold(n_splits=2, shuffle=True, random_state=RANDOM_STATE)
    accs, r_fracs = [], []
    for tr_idx, te_idx in cv.split(X, y):
        p, acc = fit_score(tr_idx, te_idx)
        accs.append(acc)
        if len(Xr):
            r_fracs.append(float(np.mean(p.predict(Xr) == 1)))
    result["acc_random_mean"] = float(np.mean(accs))
    if r_fracs:
        result["R_frac_pred_B_random_mean"] = float(np.mean(r_fracs))

    return result


def main(limit=None):
    t0 = time.time()
    nwb_files = sorted(NWB_DIR.glob("*.nwb"))
    if limit:
        nwb_files = nwb_files[:limit]
    print(f"Found {len(nwb_files)} NWB files.")

    stim_rows, omission_rows = [], []
    for f_idx, nwb_path in enumerate(nwb_files, 1):
        stem = nwb_path.stem.replace("_rec", "")
        print(f"[{f_idx}/{len(nwb_files)}] {stem}")
        session = oa.read(nwb_path)
        for area in AREAS:
            unit_ids = session.get_units(area=area)["unit_id"].tolist()
            stim_rows.extend(decode_stim_positive_control(session, unit_ids, stem, area))
            omission_rows.append(decode_omission_pooled(session, unit_ids, stem, area))

    df_stim = pd.DataFrame(stim_rows)
    df_stim.to_csv(OUT_DIR / "fig04_v4_stim_by_area.csv", index=False)
    df_om = pd.DataFrame(omission_rows)
    df_om.to_csv(OUT_DIR / "fig04_v4_omission_by_area.csv", index=False)

    print(f"\nDone in {time.time()-t0:.1f}s.")
    ok_stim = df_stim[df_stim.status == "success"]
    if len(ok_stim):
        print("\n=== STIM positive control, mean accuracy by area (pooled over slots/sessions) ===")
        print(ok_stim.groupby("area").accuracy.agg(["mean", "count"]).sort_values("mean", ascending=False).round(3))
    ok_om = df_om[df_om.status == "success"]
    if len(ok_om):
        print("\n=== OMISSION pooled, mean accuracy by area ===")
        print(ok_om.groupby("area")[["acc_chrono_mean", "acc_random_mean"]].mean().sort_values("acc_chrono_mean", ascending=False).round(3))


if __name__ == "__main__":
    _limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit=_limit)
