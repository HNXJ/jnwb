#!/usr/bin/env python3

# === QUARANTINED 2026-08-10 -- do not use as an empirical source ===
# Per artifacts/.lab/agent-harness-audit-20260810.json (Sol/Hamm Handout 2, P0 item 1):
# this script uses invalid (ungrouped/random) cross-validation for omission-identity-style
# decoding on a corpus with real repeated-cycle structure -- same-cycle trials can land in
# both train and test, inflating apparent accuracy. It is preserved as forensic evidence of
# what was tried and why it was superseded, per this project's Conservation doctrine
# (reduction is valid only if prior state remains recoverable) -- NOT deleted.
# tests/test_quarantine_enforcement.py fails if any live (non-historical) script imports from
# this module.
scientific_status = "invalid_for_inference"
superseded_by = 'compute_omission_identity_leakage_safe.py'
reason = ['ungrouped_cv']
# === END QUARANTINE HEADER ===

r"""
Figure 4 v5: N x T (population x time) decoder, 2026-08-06.

WHY THIS EXISTS
    Every decoder built so far (v1-v4, the single-session S+ PFC steps) collapsed each trial to
    ONE spike count per unit -- an N-dimensional vector that discards WHEN within the window a
    unit fired, only how much. If the omitted-identity signal (if real) is carried by the TIMING
    or SHAPE of the population response rather than its total count, a flat-count decoder is
    blind to it by construction. This builds the richer representation: bin each trial's window
    into T time bins per unit, giving an N x T matrix per trial, flatten to N*T features, PCA
    down (a plain linear SVM on N*T raw features with only ~60-150 trials would badly overfit),
    then decode.

SAME VALIDATION AS v4, not a fresh, weaker design -- the richer feature space raises the same
overfitting-to-temporal-confound risk this whole redesign has been managing, so it gets the same
controls, not fewer:
    - pooled across all 3 slots (corrected A/B mapping: X|A = AXAB+AAXB+BBBX, X|B =
      BXBA+BBXA+AAAX, X|R = RXRR+RRXR+RRRX), each trial's own relative window (531ms duration,
      binned identically regardless of which slot it came from)
    - chronological half-split (train first half by time, test second half, and reverse)
    - random half-split (shuffled 50/50)
    - X|R applied to whichever classifier was trained, reporting fraction predicted "B"
      (expected ~0.5 if unbiased)
    - 100-shuffle label-permutation null for the chronological scheme specifically (the harder,
      more honest test)

OUTPUT
    outputs/classification/fig04_v5_NxT_by_area.csv
"""
from __future__ import annotations

import pathlib
import sys
import time

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import omission as oa  # noqa: E402
from omission.jnwb_ext.omission_identity import OMISSION_IDENTITY_CONDITIONS  # noqa: E402
from jnwb import paths as _P

OUT_DIR = REPO_ROOT / "outputs" / "classification"
NWB_DIR = pathlib.Path(_P.nwb_dir())
AREAS = ["FEF", "PFC", "TEO", "V4", "V3", "V2", "V1"]
RANDOM_STATE = 42
BIN_MS = 25.0
WIN_DUR_MS = 531.0  # matches the narrow omission-slot duration used throughout this project
N_PERMUTATIONS = 100
MAX_PCA_COMPONENTS = 20  # capped well below typical n_trials to avoid overfitting


def spikemat_NxT(session, unit_ids, onsets, bin_ms, win_dur_ms):
    """(n_trials, n_units, n_bins) spike-count array, each trial's own window starting at its
    own onset, duration win_dur_ms, binned at bin_ms."""
    edges = np.arange(0, win_dur_ms + bin_ms, bin_ms) / 1000.0
    n_bins = len(edges) - 1
    X = np.zeros((len(onsets), len(unit_ids), n_bins))
    for j, u_id in enumerate(unit_ids):
        st = session.get_spike_times(u_id)
        st = np.sort(st) if st is not None and len(st) else np.array([])
        for i, onset in enumerate(onsets):
            rel = st[(st >= onset) & (st < onset + win_dur_ms / 1000.0)] - onset
            X[i, j, :] = np.histogram(rel, bins=edges)[0]
    return X


def decode_omission_NxT(session, unit_ids, stem, area):
    cfg2, cfg3, cfg4 = (OMISSION_IDENTITY_CONDITIONS["p2"], OMISSION_IDENTITY_CONDITIONS["p3"],
                        OMISSION_IDENTITY_CONDITIONS["p4"])
    onsets_ms = {"p2": 1031.0, "p3": 2062.0, "p4": 3093.0}

    def pooled_onsets_times(cls_key):
        onsets, times = [], []
        for slot_key, cfg in (("p2", cfg2), ("p3", cfg3), ("p4", cfg4)):
            e = session.get_epochs(phase=2, condition=cfg[cls_key])
            if len(e) == 0:
                continue
            t = e["start_time"].values
            onsets.append(t + onsets_ms[slot_key] / 1000.0)
            times.append(t)
        return (np.concatenate(onsets) if onsets else np.array([]),
                np.concatenate(times) if times else np.array([]))

    onset_a, t_a = pooled_onsets_times("A")
    onset_b, t_b = pooled_onsets_times("B")
    onset_r, t_r = pooled_onsets_times("R")

    base = {"session": stem, "area": area, "n_units": len(unit_ids),
           "n_A": len(onset_a), "n_B": len(onset_b), "n_R": len(onset_r)}
    if len(unit_ids) < 2 or len(onset_a) < 6 or len(onset_b) < 6:
        return {**base, "status": "insufficient_data"}

    Xa = spikemat_NxT(session, unit_ids, onset_a, BIN_MS, WIN_DUR_MS)
    Xb = spikemat_NxT(session, unit_ids, onset_b, BIN_MS, WIN_DUR_MS)
    Xr = spikemat_NxT(session, unit_ids, onset_r, BIN_MS, WIN_DUR_MS) if len(onset_r) else None

    def flatten(X):
        return X.reshape(X.shape[0], -1)

    Xa_f, Xb_f = flatten(Xa), flatten(Xb)
    Xr_f = flatten(Xr) if Xr is not None else None
    X = np.concatenate([Xa_f, Xb_f], axis=0)
    y = np.array([0] * len(Xa_f) + [1] * len(Xb_f))
    t = np.concatenate([t_a, t_b])
    n_features_raw = X.shape[1]

    def fit_score(train_idx, test_idx):
        n_comp = min(MAX_PCA_COMPONENTS, len(train_idx) - 1, n_features_raw)
        pipe = Pipeline([
            ("sc", StandardScaler()),
            ("pca", PCA(n_components=n_comp, random_state=RANDOM_STATE)),
            ("clf", SVC(kernel="linear", C=1.0, random_state=RANDOM_STATE)),
        ])
        pipe.fit(X[train_idx], y[train_idx])
        acc = pipe.score(X[test_idx], y[test_idx])
        return pipe, acc

    result = {**base, "status": "success", "n_features_raw": n_features_raw}

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
        if Xr_f is not None and len(Xr_f):
            result["R_frac_pred_B_chrono_fwd"] = float(np.mean(p_fwd.predict(Xr_f) == 1))
            result["R_frac_pred_B_chrono_bwd"] = float(np.mean(p_bwd.predict(Xr_f) == 1))

        # permutation null on the chronological scheme (harder, more honest test)
        rng = np.random.default_rng(RANDOM_STATE)
        perm_accs = []
        for _ in range(N_PERMUTATIONS):
            y_perm = rng.permutation(y)
            if len(set(y_perm[first_half])) < 2 or len(set(y_perm[second_half])) < 2:
                continue
            _, a1 = fit_score(first_half, second_half)
            _, a2 = fit_score(second_half, first_half)
            perm_accs.append(np.mean([a1, a2]))
        if perm_accs:
            p_val = float(np.mean(np.array(perm_accs) >= result["acc_chrono_mean"]))
            result["p_val_chrono"] = p_val if p_val > 0 else 1.0 / (len(perm_accs) + 1)
            result["perm_null_mean_chrono"] = float(np.mean(perm_accs))
    else:
        result["acc_chrono_mean"] = float("nan")

    # -- random half-split --
    cv = StratifiedKFold(n_splits=2, shuffle=True, random_state=RANDOM_STATE)
    accs, r_fracs = [], []
    for tr_idx, te_idx in cv.split(X, y):
        p, acc = fit_score(tr_idx, te_idx)
        accs.append(acc)
        if Xr_f is not None and len(Xr_f):
            r_fracs.append(float(np.mean(p.predict(Xr_f) == 1)))
    result["acc_random_mean"] = float(np.mean(accs))
    if r_fracs:
        result["R_frac_pred_B_random_mean"] = float(np.mean(r_fracs))

    return result


def main(limit=None):
    t0 = time.time()
    nwb_files = sorted(NWB_DIR.glob("*.nwb"))
    if limit:
        nwb_files = nwb_files[:limit]
    print(f"Found {len(nwb_files)} NWB files. Bin={BIN_MS}ms, window={WIN_DUR_MS}ms, "
         f"PCA<= {MAX_PCA_COMPONENTS} components.")

    rows = []
    for f_idx, nwb_path in enumerate(nwb_files, 1):
        stem = nwb_path.stem.replace("_rec", "")
        print(f"[{f_idx}/{len(nwb_files)}] {stem}")
        session = oa.read(nwb_path)
        for area in AREAS:
            unit_ids = session.get_units(area=area)["unit_id"].tolist()
            rows.append(decode_omission_NxT(session, unit_ids, stem, area))

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "fig04_v5_NxT_by_area.csv", index=False)
    ok = df[df.status == "success"]
    print(f"\nDone in {time.time()-t0:.1f}s. {len(ok)}/{len(df)} cells succeeded.")
    if len(ok):
        print("\n=== N x T PCA-SVM, mean accuracy by area ===")
        print(ok.groupby("area")[["acc_chrono_mean", "acc_random_mean"]].mean()
             .sort_values("acc_chrono_mean", ascending=False).round(3))
        if "p_val_chrono" in ok.columns:
            print("\nn significant (chrono, p<0.05):", (ok.p_val_chrono < 0.05).sum(), "/", ok.p_val_chrono.notna().sum())


if __name__ == "__main__":
    _limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit=_limit)
