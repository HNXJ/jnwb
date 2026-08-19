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
Figure 4 v8: permutation null for the 2D omitted-identity decoders, 2026-08-07.

WHY
    v6 (flatten+PCA) and v7 (bilinear) both land near 0.36-0.39 BALANCED accuracy against a 1/3
    chance level. That gap is small enough that it cannot be called a decode without an empirical
    null, and neither run produced one. This script supplies it.

SCOPE -- deliberately narrow, because a null is ~N_PERM times the cost of the point estimate:
    - Windows: "px" (the ONLY window containing no differing physical stimulus -- see
      artifacts/.lab/p-d-px-d-window-stimulus-leak-20260807.json) and "d_px_d". p_d_px_d is
      EXCLUDED on purpose: it contains the preceding, physically different presentation, so its
      null would be testing stimulus decoding, not omission decoding.
    - Both modalities, all 7 areas, all 21 sessions.
    - Estimator: bilinear (jnwb/bilinear.py), matching v7, so the null tests the headline model.

STATISTIC
    BALANCED accuracy (mean of the row-normalized confusion diagonal), NOT raw accuracy: pooled
    n_R outnumbers n_A/n_B ~1.8:1, so raw accuracy's baseline is ~0.48, not 1/3.

NULL
    Labels are permuted WITHIN the pooled trial set before the same stratified 60/40 split and
    the same fit. p = (1 + #{null >= observed}) / (1 + n_perm), the add-one estimator -- never
    reports p = 0 for a finite number of shuffles.

OUTPUT
    outputs/classification/fig04_v8_permnull_{modality}.csv
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

import omission as oa  # noqa: E402
from jnwb.bilinear import BilinearLogisticRegression  # noqa: E402
from decode_fig04_v6_2d_population_5windows import AREAS, OUT_DIR, NWB_DIR, RANDOM_STATE  # noqa: E402
from decode_fig04_v7_bilinear_5windows import RANK, C_REG, build_pooled_3d  # noqa: E402

WINDOWS = ["px", "d_px_d"]
N_PERM = 100


def balanced_acc(y_true, y_pred):
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1, 2])
    return float(np.diag(cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)).mean())


def _fit_eval(X, y, tr, te, seed):
    clf = BilinearLogisticRegression(rank=RANK, C=C_REG, random_state=seed)
    clf.fit(X[tr], y[tr])
    return balanced_acc(y[te], clf.predict(X[te]))


def null_for_cell(session, stem, area, unit_ids, modality, window_name, n_perm):
    base = {"session": stem, "area": area, "modality": modality, "window": window_name,
            "n_units": len(unit_ids), "n_perm": n_perm}
    Xa, Xb, Xr = build_pooled_3d(session, stem, area, unit_ids, modality, window_name,
                                 log_lfp=(modality == "lfp"))
    if len(unit_ids) < 2 or len(Xa) < 6 or len(Xb) < 6 or len(Xr) < 6:
        return {**base, "status": "insufficient_data"}
    n_sp = min(x.shape[1] for x in (Xa, Xb, Xr))
    n_t = min(x.shape[2] for x in (Xa, Xb, Xr))
    if n_sp < 2 or n_t < 2:
        return {**base, "status": "degenerate_shape"}
    Xa, Xb, Xr = (x[:, :n_sp, :n_t] for x in (Xa, Xb, Xr))
    X = np.concatenate([Xa, Xb, Xr], axis=0)
    y = np.array([0] * len(Xa) + [1] * len(Xb) + [2] * len(Xr))
    base.update({"n_A": len(Xa), "n_B": len(Xb), "n_R": len(Xr),
                 "n_space": n_sp, "n_time": n_t})

    idx = np.arange(len(y))
    tr, te = train_test_split(idx, test_size=0.4, stratify=y, random_state=RANDOM_STATE)
    t_obs0 = time.time()
    obs = _fit_eval(X, y, tr, te, RANDOM_STATE)
    fit_sec = time.time() - t_obs0

    rng = np.random.default_rng(RANDOM_STATE)
    null = []
    for _ in range(n_perm):
        y_perm = rng.permutation(y)
        # re-split under the permuted labels so stratification stays valid
        tr_p, te_p = train_test_split(idx, test_size=0.4, stratify=y_perm,
                                      random_state=RANDOM_STATE)
        null.append(_fit_eval(X, y_perm, tr_p, te_p, RANDOM_STATE))
    null = np.asarray(null)
    p = (1.0 + np.sum(null >= obs)) / (1.0 + len(null))
    return {**base, "status": "success",
            "balanced_accuracy": obs, "chance_baseline": 1.0 / 3,
            "null_mean": float(null.mean()), "null_sd": float(null.std()),
            "null_p95": float(np.percentile(null, 95)),
            "p_value": float(p),
            "z_vs_null": float((obs - null.mean()) / null.std()) if null.std() > 0 else np.nan,
            "fit_seconds": round(fit_sec, 2)}


def main(limit=None, modalities=("spikes", "lfp"), n_perm=N_PERM):
    t0 = time.time()
    nwb_files = sorted(NWB_DIR.glob("*.nwb"))
    if limit:
        nwb_files = nwb_files[:limit]
    print(f"Permutation null: {len(nwb_files)} sessions, windows={WINDOWS}, "
          f"modalities={modalities}, n_perm={n_perm}, statistic=balanced accuracy", flush=True)

    rows = {m: [] for m in modalities}
    for f_idx, nwb_path in enumerate(nwb_files, 1):
        stem = nwb_path.stem.replace("_rec", "")
        print(f"[{f_idx}/{len(nwb_files)}] {stem}", flush=True)
        session = oa.read(nwb_path)
        for area in AREAS:
            unit_ids = session.get_units(area=area)["unit_id"].tolist()
            for modality in modalities:
                for window_name in WINDOWS:
                    rows[modality].append(null_for_cell(session, stem, area, unit_ids,
                                                        modality, window_name, n_perm))

    for modality in modalities:
        df = pd.DataFrame(rows[modality])
        out_path = OUT_DIR / f"fig04_v8_permnull_{modality}.csv"
        df.to_csv(out_path, index=False)
        ok = df[df.status == "success"] if "status" in df.columns else df.iloc[:0]
        print(f"\n=== {modality}: {len(ok)}/{len(df)} cells -> {out_path} ===")
        if len(ok):
            print(ok.groupby(["window", "area"])[["balanced_accuracy", "null_mean", "p_value"]]
                  .mean().round(3).to_string())
            print(f"\ncells with p<0.05: {(ok.p_value < 0.05).sum()}/{len(ok)}")
            print("by window:", ok.groupby("window").p_value.apply(lambda s: (s < 0.05).sum())
                  .to_dict())

    print(f"\nDone in {time.time()-t0:.1f}s.")


if __name__ == "__main__":
    _limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "-" else None
    _mods = tuple(sys.argv[2].split(",")) if len(sys.argv) > 2 else ("spikes", "lfp")
    _np = int(sys.argv[3]) if len(sys.argv) > 3 else N_PERM
    if len(sys.argv) > 4:
        WINDOWS = sys.argv[4].split(",")
    main(limit=_limit, modalities=_mods, n_perm=_np)
