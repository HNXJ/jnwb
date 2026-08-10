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
Figure 4 v7: BILINEAR (rank-K matrix-factorized) 2D decoder, 5 windows, 3-way A/B/R, 2026-08-07.

WHAT CHANGED FROM v6, AND WHY
    v6 answered the same question by flattening each trial's (N x T) matrix into one N*T vector
    and PCA-ing it to <=20 components. Per direction, that is the wrong shape of model: it
    destroys the laminar/spatial topology and temporal continuity, and its PCA components have no
    interpretable spatial or temporal identity. v7 keeps the trial as a matrix and constrains the
    weights to be low rank (W = sum_k u_k v_k^T), so the fitted model hands back an explicit
    laminar/unit spatial profile u_k and an explicit temporal filter v_k per class, at
    O(K(N+T)) parameters instead of O(N*T). See jnwb/bilinear.py.

    v6 is NOT deleted or superseded by assertion -- it runs on the same cells with the same
    windows and splits, so the two are directly comparable and the comparison is the receipt.

EVERYTHING ELSE IS HELD FIXED so the estimator is the only thing that varies:
    same 5 windows (d_px_d, d_px, px_d, px, p_d_px_d), same pooled corrected mapping
    (X|A = AXAB+AAXB+BBBX, X|B = BXBA+BBXA+AAAX, X|R = RXRR+RRXR+RRRX), same modalities
    (spikes N x T at 25ms bins; LFP channels x T low-frequency power at native 10ms bins), same
    single stratified 60/40 split, same seed, same 3x3 row-normalized confusion matrix, same
    R-trial softmax renormalization (P(R) dropped, [P(A),P(B)] rescaled to sum to 1).

    Data-building helpers are IMPORTED from the v6 script rather than copied, so the two runs
    provably read identical features and any difference is attributable to the classifier alone.

ONE DELIBERATE ADDITION: log10 transform on LFP power (`--log-lfp`, default ON for lfp only).
    Power is strongly right-skewed; a linear decision boundary sits much more naturally on
    log power. This is a real change to the LFP feature, so it is a named flag and is recorded
    in the output, not silently baked in. Spike counts are untouched.

OUTPUT
    outputs/classification/fig04_v7_bilinear_{modality}_2d_5win.csv
    outputs/classification/fig04_v7_bilinear_filters_{modality}.npz   (u/v per successful cell)
"""
from __future__ import annotations

import pathlib
import sys
import time

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import jnwb as oa  # noqa: E402
from jnwb.bilinear import BilinearLogisticRegression  # noqa: E402
from jnwb.omission_identity import OMISSION_IDENTITY_CONDITIONS  # noqa: E402
from decode_fig04_v6_2d_population_5windows import (  # noqa: E402
    AREAS,
    OUT_DIR,
    NWB_DIR,
    RANDOM_STATE,
    SPIKE_BIN_MS,
    WINDOW_NAMES,
    channel_map_for_area,
    get_windows_ms,
    lfp_mat_channelsxT,
    spikemat_NxT,
)

RANK = 2
C_REG = 1.0


def build_pooled_3d(session, stem, area, unit_ids, modality, window_name, log_lfp):
    """Same features as v6's build_pooled_2d but WITHOUT the flatten -- returns
    (n_trials, N, T) per class, which is the whole point of this script."""
    cfgs = [(k, OMISSION_IDENTITY_CONDITIONS[k]) for k in ("p2", "p3", "p4")]
    chan_map = channel_map_for_area(session, unit_ids) if modality == "lfp" else None

    def pooled(cls_key):
        Xs = []
        for slot_key, cfg in cfgs:
            win_ms = get_windows_ms(slot_key)[window_name]
            e = session.get_epochs(phase=2, condition=cfg[cls_key])
            if len(e) == 0:
                continue
            if modality == "spikes":
                X = spikemat_NxT(session, unit_ids,
                                 e["start_time"].values + win_ms[0] / 1000.0,
                                 SPIKE_BIN_MS, win_ms[1] - win_ms[0])
            else:
                X = lfp_mat_channelsxT(stem, area, cfg[cls_key], chan_map, win_ms)
                if X is not None and log_lfp:
                    X = np.log10(np.maximum(np.asarray(X, dtype=np.float64), 1e-12))
            if X is not None and len(X):
                Xs.append(np.asarray(X, dtype=np.float64))
        if not Xs:
            return np.zeros((0, 0, 0))
        n_sp = min(x.shape[1] for x in Xs)
        n_t = min(x.shape[2] for x in Xs)  # guard clipped p4 windows
        return np.concatenate([x[:, :n_sp, :n_t] for x in Xs], axis=0)

    return pooled("A"), pooled("B"), pooled("R")


def decode_cell_bilinear(session, stem, area, unit_ids, modality, window_name, log_lfp):
    base = {"session": stem, "area": area, "modality": modality, "window": window_name,
            "n_units": len(unit_ids), "rank": RANK,
            "log_lfp": bool(log_lfp and modality == "lfp")}
    Xa, Xb, Xr = build_pooled_3d(session, stem, area, unit_ids, modality, window_name, log_lfp)
    if (len(unit_ids) < 2 or len(Xa) < 6 or len(Xb) < 6 or len(Xr) < 6):
        return {**base, "status": "insufficient_data",
                "n_A": len(Xa), "n_B": len(Xb), "n_R": len(Xr)}, None
    n_sp = min(x.shape[1] for x in (Xa, Xb, Xr))
    n_t = min(x.shape[2] for x in (Xa, Xb, Xr))
    if n_sp < 2 or n_t < 2:
        return {**base, "status": "degenerate_shape", "n_space": n_sp, "n_time": n_t}, None
    Xa, Xb, Xr = (x[:, :n_sp, :n_t] for x in (Xa, Xb, Xr))

    X = np.concatenate([Xa, Xb, Xr], axis=0)
    y = np.array([0] * len(Xa) + [1] * len(Xb) + [2] * len(Xr))
    base.update({"n_A": len(Xa), "n_B": len(Xb), "n_R": len(Xr),
                 "n_space": n_sp, "n_time": n_t})

    idx = np.arange(len(y))
    tr, te = train_test_split(idx, test_size=0.4, stratify=y, random_state=RANDOM_STATE)
    clf = BilinearLogisticRegression(rank=RANK, C=C_REG, random_state=RANDOM_STATE)
    clf.fit(X[tr], y[tr])
    preds = clf.predict(X[te])
    proba = clf.predict_proba(X[te])
    acc = float(np.mean(preds == y[te]))
    cm = confusion_matrix(y[te], preds, labels=[0, 1, 2])
    cm_norm = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)

    r_mask = y[te] == 2
    r_pa = float("nan")
    if r_mask.sum():
        p_ab = proba[r_mask][:, :2]
        r_pa = float((p_ab / np.maximum(p_ab.sum(axis=1, keepdims=True), 1e-9))[:, 0].mean())

    # Raw accuracy is NOT comparable to 1/3 here: pooled R trials outnumber A and B roughly
    # 1.8:1, so an all-R classifier already scores ~0.48. Balanced accuracy (mean of the
    # confusion matrix's row-normalized diagonal) is the number to read against 1/3.
    counts = np.array([len(Xa), len(Xb), len(Xr)], dtype=float)
    row = {**base, "status": "success", "n_train": len(tr), "n_test": len(te),
           "accuracy": acc,
           "balanced_accuracy": float(np.diag(cm_norm).mean()),
           "majority_class_baseline": float(counts.max() / counts.sum()),
           "chance_baseline": 1.0 / 3,
           "n_parameters": clf.n_parameters(),
           "n_parameters_if_flattened": int(3 * (n_sp * n_t + 1)),
           "alt_iters": ",".join(str(i) for i in clf.n_iter_run_),
           "confusion_A": cm_norm[0].tolist(), "confusion_B": cm_norm[1].tolist(),
           "confusion_R": cm_norm[2].tolist(), "R_mean_softmax_pA_renorm": r_pa}
    filt = {"U": clf.U_, "V": clf.V_}
    return row, filt


def main(limit=None, modalities=("spikes", "lfp"), log_lfp=True):
    t0 = time.time()
    nwb_files = sorted(NWB_DIR.glob("*.nwb"))
    if limit:
        nwb_files = nwb_files[:limit]
    print(f"Found {len(nwb_files)} NWB files. Bilinear rank={RANK}, C={C_REG}, "
          f"modalities={modalities}, log_lfp={log_lfp}")

    rows = {m: [] for m in modalities}
    filters = {m: {} for m in modalities}
    for f_idx, nwb_path in enumerate(nwb_files, 1):
        stem = nwb_path.stem.replace("_rec", "")
        print(f"[{f_idx}/{len(nwb_files)}] {stem}", flush=True)
        session = oa.read(nwb_path)
        for area in AREAS:
            unit_ids = session.get_units(area=area)["unit_id"].tolist()
            for modality in modalities:
                for window_name in WINDOW_NAMES:
                    row, filt = decode_cell_bilinear(session, stem, area, unit_ids,
                                                     modality, window_name, log_lfp)
                    rows[modality].append(row)
                    if filt is not None:
                        key = f"{stem}|{area}|{window_name}"
                        filters[modality][key + "|U"] = filt["U"]
                        filters[modality][key + "|V"] = filt["V"]

    for modality in modalities:
        df = pd.DataFrame(rows[modality])
        out_path = OUT_DIR / f"fig04_v7_bilinear_{modality}_2d_5win.csv"
        df.to_csv(out_path, index=False)
        if filters[modality]:
            np.savez_compressed(OUT_DIR / f"fig04_v7_bilinear_filters_{modality}.npz",
                                **filters[modality])
        ok = df[df.status == "success"] if "status" in df.columns else df.iloc[:0]
        print(f"\n=== {modality}: {len(ok)}/{len(df)} cells succeeded -> {out_path} ===")
        if len(ok):
            print("balanced accuracy (chance 0.333) by window x area:")
            print(ok.groupby(["window", "area"]).balanced_accuracy.mean()
                  .unstack("area").round(3))
            print("\nmean BALANCED accuracy by area (pooled over windows):")
            print(ok.groupby("area").balanced_accuracy.mean()
                  .sort_values(ascending=False).round(3))
            print(f"\nraw acc {ok.accuracy.mean():.3f} | majority-class baseline "
                  f"{ok.majority_class_baseline.mean():.3f} | balanced "
                  f"{ok.balanced_accuracy.mean():.3f} vs chance 0.333")

    print(f"\nDone in {time.time()-t0:.1f}s.")


if __name__ == "__main__":
    _limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "-" else None
    _mods = tuple(sys.argv[2].split(",")) if len(sys.argv) > 2 else ("spikes", "lfp")
    main(limit=_limit, modalities=_mods)
