#!/usr/bin/env python3
r"""
Figure 4 v9: Neural Additive Model with per-unit attribution and unit pruning, 2026-08-07.

ANSWERS THREE SPECIFIC POINTS
    (1) "each neuron contributes at some point, but low trial count might give it weights that
        make classification WORSE" -- tested directly: units are ranked by NAM attribution and
        the low-contribution tail is pruned, then the model is re-evaluated. If pruning helps,
        the discarded units were adding variance, not signal.
    (2) "train / traintest / test, 40-30-30" -- implemented exactly. TRAIN supplies gradients.
        VAL supplies NO gradient: it early-stops, restores best weights, and selects the prune
        threshold. TEST is touched ONCE, at the end, per configuration.

        This split discipline is what makes (1) a real test rather than a circular one: if the
        prune threshold were chosen on TEST, "pruning improves decoding" would be true by
        construction for any dataset, signal or none.
    (3) NAM itself -- jnwb/nam.py, N independent sub-networks, additive logits, S_i = trial-wise
        std of unit i's contribution.

STATISTIC is BALANCED accuracy throughout (pooled n_R outnumbers n_A/n_B ~1.8:1, so raw
accuracy's baseline is ~0.48, not 1/3). Class-weighted cross-entropy for the same reason.

SCOPE: "px" window only -- the one window containing no differing physical stimulus (see
artifacts/.lab/p-d-px-d-window-stimulus-leak-20260807.json). Both modalities.

OUTPUT
    outputs/classification/fig04_v9_nam_{modality}.csv
    outputs/classification/fig04_v9_nam_importance_{modality}.npz
"""
from __future__ import annotations

import pathlib
import sys
import time

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import jnwb as oa  # noqa: E402
from jnwb.nam import LaminarNAM, predict, train_nam, unit_importance  # noqa: E402
from decode_fig04_v6_2d_population_5windows import AREAS, OUT_DIR, NWB_DIR, RANDOM_STATE  # noqa: E402
from decode_fig04_v7_bilinear_5windows import build_pooled_3d  # noqa: E402

WINDOW = "px"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
KEEP_FRACTIONS = [1.0, 0.9, 0.75, 0.5, 0.25, 0.1]


def balanced_acc(y_true, y_pred):
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1, 2])
    return float(np.diag(cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)).mean())


def split_403030(y, seed):
    """40 train / 30 val / 30 test, stratified."""
    idx = np.arange(len(y))
    tr, rest = train_test_split(idx, train_size=0.4, stratify=y, random_state=seed)
    va, te = train_test_split(rest, train_size=0.5, stratify=y[rest], random_state=seed)
    return tr, va, te


def run_cell(session, stem, area, unit_ids, modality, seed=RANDOM_STATE):
    base = {"session": stem, "area": area, "modality": modality, "window": WINDOW,
            "n_units": len(unit_ids), "device": DEVICE}
    Xa, Xb, Xr = build_pooled_3d(session, stem, area, unit_ids, modality, WINDOW,
                                 log_lfp=(modality == "lfp"))
    if len(unit_ids) < 2 or min(len(Xa), len(Xb), len(Xr)) < 10:
        return {**base, "status": "insufficient_data"}, None
    n_sp = min(x.shape[1] for x in (Xa, Xb, Xr))
    n_t = min(x.shape[2] for x in (Xa, Xb, Xr))
    if n_sp < 2 or n_t < 4:
        return {**base, "status": "degenerate_shape"}, None
    Xa, Xb, Xr = (x[:, :n_sp, :n_t] for x in (Xa, Xb, Xr))
    X = np.concatenate([Xa, Xb, Xr], axis=0).astype(np.float32)
    y = np.array([0] * len(Xa) + [1] * len(Xb) + [2] * len(Xr))

    tr, va, te = split_403030(y, seed)
    mu, sd = X[tr].mean(axis=0), X[tr].std(axis=0)   # train-only scaling, no leakage
    sd[sd < 1e-9] = 1.0
    Xz = (X - mu) / sd

    counts = np.bincount(y, minlength=3).astype(float)
    class_weight = counts.sum() / (3.0 * np.maximum(counts, 1))

    model = LaminarNAM(num_units=n_sp, time_samples=n_t)
    hist = train_nam(model, Xz[tr], y[tr], Xz[va], y[va], device=DEVICE,
                     class_weight=class_weight, seed=seed)

    # attribution measured on VAL (never on test) so pruning selection stays honest
    S_val = unit_importance(model, Xz[va], device=DEVICE)
    order = np.argsort(-S_val)          # most important first

    rows = {}
    for frac in KEEP_FRACTIONS:
        k = max(1, int(round(frac * n_sp)))
        mask = np.zeros(n_sp, dtype=np.float32)
        mask[order[:k]] = 1.0
        mt = torch.as_tensor(mask, device=DEVICE)
        rows[f"bal_test_keep{int(frac*100)}"] = balanced_acc(
            y[te], predict(model, Xz[te], device=DEVICE, unit_mask=mt)[0])
        rows[f"bal_val_keep{int(frac*100)}"] = balanced_acc(
            y[va], predict(model, Xz[va], device=DEVICE, unit_mask=mt)[0])

    # the prune level is CHOSEN on val, then reported on test -- one selection, one readout
    val_keys = [f"bal_val_keep{int(f*100)}" for f in KEEP_FRACTIONS]
    best_i = int(np.argmax([rows[k] for k in val_keys]))
    best_frac = KEEP_FRACTIONS[best_i]

    row = {**base, "status": "success",
           "n_A": len(Xa), "n_B": len(Xb), "n_R": len(Xr),
           "n_space": n_sp, "n_time": n_t,
           "n_train": len(tr), "n_val": len(va), "n_test": len(te),
           "best_val_loss": hist["best_val_loss"], "best_epoch": hist["best_epoch"],
           "epochs_run": hist["epochs_run"],
           "chance_baseline": 1.0 / 3,
           "bal_test_all_units": rows["bal_test_keep100"],
           "selected_keep_fraction": best_frac,
           "bal_test_at_selected": rows[f"bal_test_keep{int(best_frac*100)}"],
           "prune_gain_test": rows[f"bal_test_keep{int(best_frac*100)}"] - rows["bal_test_keep100"],
           "importance_max": float(S_val.max()), "importance_median": float(np.median(S_val)),
           "importance_frac_near_zero": float(np.mean(S_val < 0.05 * S_val.max())),
           **rows}
    return row, {"S_val": S_val, "unit_ids": np.array(unit_ids[:n_sp], dtype=object)}


def main(limit=None, modalities=("spikes", "lfp")):
    t0 = time.time()
    nwb_files = sorted(NWB_DIR.glob("*.nwb"))
    if limit:
        nwb_files = nwb_files[:limit]
    print(f"NAM: {len(nwb_files)} sessions, window={WINDOW}, modalities={modalities}, "
          f"device={DEVICE}, split=40/30/30", flush=True)

    rows = {m: [] for m in modalities}
    imps = {m: {} for m in modalities}
    for f_idx, nwb_path in enumerate(nwb_files, 1):
        stem = nwb_path.stem.replace("_rec", "")
        print(f"[{f_idx}/{len(nwb_files)}] {stem}", flush=True)
        session = oa.read(nwb_path)
        for area in AREAS:
            unit_ids = session.get_units(area=area)["unit_id"].tolist()
            for modality in modalities:
                row, imp = run_cell(session, stem, area, unit_ids, modality)
                rows[modality].append(row)
                if imp is not None:
                    imps[modality][f"{stem}|{area}|S"] = imp["S_val"]

    for modality in modalities:
        df = pd.DataFrame(rows[modality])
        out = OUT_DIR / f"fig04_v9_nam_{modality}.csv"
        df.to_csv(out, index=False)
        if imps[modality]:
            np.savez_compressed(OUT_DIR / f"fig04_v9_nam_importance_{modality}.npz",
                                **imps[modality])
        ok = df[df.status == "success"] if "status" in df.columns else df.iloc[:0]
        print(f"\n=== {modality}: {len(ok)}/{len(df)} cells -> {out} ===")
        if len(ok):
            print("balanced acc, all units vs val-selected prune (chance 0.333):")
            print(ok.groupby("area")[["bal_test_all_units", "bal_test_at_selected",
                                      "prune_gain_test", "selected_keep_fraction"]]
                  .mean().round(3).sort_values("bal_test_at_selected", ascending=False)
                  .to_string())
            print(f"\nmean prune gain on TEST: {ok.prune_gain_test.mean():+.4f} "
                  f"(cells improved: {(ok.prune_gain_test > 0).sum()}/{len(ok)})")
            print(f"mean fraction of units with near-zero importance: "
                  f"{ok.importance_frac_near_zero.mean():.3f}")

    print(f"\nDone in {time.time()-t0:.1f}s.")


if __name__ == "__main__":
    _limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "-" else None
    _mods = tuple(sys.argv[2].split(",")) if len(sys.argv) > 2 else ("spikes", "lfp")
    main(limit=_limit, modalities=_mods)
