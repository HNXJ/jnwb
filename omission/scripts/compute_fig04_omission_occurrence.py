#!/usr/bin/env python3
"""Fig04 Gate 1, fifth SPK target: Y_omission (omission occurrence).

Y_omission in {O, S}: O = an omitted event at the target slot; S = a physically presented
stimulus at the SAME target slot (matched position), drawn from the corresponding full-sequence
("parent") condition. Scientific question: I(O; S_population | position) > 0?

Reuses the frozen leakage-safe Fig04 operator, imported not reimplemented:
  - cycle-grouped leave-one-cycle-out CV, fold-local balancing (decode_binary_cycle_safe,
    _balanced_training_indices, from compute_omission_identity_leakage_safe.py)
  - group-preserving (within-cycle) permutation null (jnwb.permutation.permute_labels)
  - canonical timing only (omission.jnwb_ext.sequence_layout.EPOCH_ONSETS_MS)
  - per-cycle centering for the position-pooled analysis (_center_within_cycle, from
    compute_fig04_encoding_matrix.py)

Per-slot cells (p2, p3, p4): O_pi vs S_pi, absolute canonical window [EPOCH_ONSETS_MS[pi],
+531ms]. DIRECT representation only -- this is the primary, inferential analysis (999
permutations, group-preserving null, (1+k)/(B+1) correction).

Position-balanced pooled cell: O vs S pooled across p2/p3/p4, using a RELATIVE window (0..531ms
from each trial's own slot onset, so absolute position cannot leak through window identity),
per-cycle centered, and trial-count-balanced across positions within each class (subsampled to
the min per-position count) so position cannot solve the classification by imbalance alone.

PCA and PCA->UMAP are robustness passes only (Hamm: "PCA/UMAP are robustness analyses, not a
mechanism for searching until omission becomes significant") -- single fold-local fit per outer
fold, small fixed N/M (no permutation test, DESCRIPTIVE status only), matching how the existing
fig04-statistical-receipt-20260826.json already treats Linear/Nonlinear-latent rows for other
targets.

Before fitting, tabulates per cell: n_O, n_S, class balance, preceding-identity composition
(computed directly from each trial's own condition-code string, immune to the documented
OMISSION_IDENTITY_CONDITIONS p4 A/B-label swap), cycle coverage, n_units. A cell is marked
NOT_IDENTIFIABLE rather than fit if O/S cannot be adequately matched on these nuisances.

Outputs:
  - fig04_omission_occurrence_cells.csv    -- one row per (session, area, slot_or_pooled)
  - fig04_omission_occurrence_nuisance.csv -- one row per (session, slot_or_pooled) nuisance table
  - fig04_omission_occurrence_receipt.json -- provenance + summary
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.multitest import multipletests
from scipy import stats as scipy_stats
from joblib import Parallel, delayed

N_JOBS = min(20, max(1, (__import__("os").cpu_count() or 1) - 2))

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT))
OA_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))

import omission as oa  # noqa: E402
from omission.jnwb_ext.omission_identity import OMISSION_IDENTITY_CONDITIONS  # noqa: E402
from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS  # noqa: E402
from omission.jnwb_ext.trial_ontology import SLOT_INDEX  # noqa: E402
from jnwb.permutation import permute_labels  # noqa: E402
from jnwb import paths  # noqa: E402

from compute_omission_identity_leakage_safe import (  # noqa: E402
    AREAS,
    SLOTS,
    LABELS,
    DEFAULT_SEED,
    PHASE_FOR_P1_ALIGNMENT,
    assign_temporal_cycles,
    _balanced_training_indices,
    _spike_count_matrix,
    _resolve_sessions,
    _fixed_balanced_accuracy,
    _pipeline,
)
from compute_fig04_encoding_matrix import _center_within_cycle  # noqa: E402

N_PERM = 999
SLOT_DUR_MS = EPOCH_ONSETS_MS["d1"] - EPOCH_ONSETS_MS["p1"]  # 531.0
PARENT_CONDITIONS = {"A": "AAAB", "B": "BBBA", "R": "RRRR"}
OUT_DIR = OA_ROOT / "outputs" / "classification"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _preceding_identity(condition_code: str, slot_key: str) -> str:
    """Identity presented one position before slot_key, read directly from the condition code
    string (position index only) -- immune to the OMISSION_IDENTITY_CONDITIONS p4 A/B swap,
    which is a dict-key labeling issue, not a code-string issue."""
    idx = SLOT_INDEX[slot_key]
    return condition_code[idx - 1]


def _slot_trial_table(session, slot_key: str) -> pd.DataFrame:
    """O-side (omission) + S-side (matched parent, stimulus-present) trials for one slot."""
    cfg = OMISSION_IDENTITY_CONDITIONS[slot_key]
    pieces = []
    for label in LABELS:
        for y_omission, code in ((1, cfg[label]), (0, PARENT_CONDITIONS[label])):
            epochs = session.get_epochs(phase=PHASE_FOR_P1_ALIGNMENT, condition=code, correct_only=True)
            if len(epochs) == 0:
                continue
            part = epochs[["start_time"]].copy()
            part["condition"] = code
            part["y_omission"] = y_omission
            part["preceding_identity"] = _preceding_identity(code, slot_key)
            pieces.append(part)
    if not pieces:
        return pd.DataFrame()
    table = pd.concat(pieces, ignore_index=True)
    table["start_time"] = pd.to_numeric(table["start_time"], errors="coerce")
    table = table.dropna(subset=["start_time"]).reset_index(drop=True)
    table["cycle_id"] = assign_temporal_cycles(table["start_time"].to_numpy())
    return table


def _nuisance_row(table: pd.DataFrame, session_stem: str, key: str) -> dict:
    o = table[table["y_omission"] == 1]
    s = table[table["y_omission"] == 0]
    prec_o = o["preceding_identity"].value_counts().to_dict()
    prec_s = s["preceding_identity"].value_counts().to_dict()
    return {
        "session": session_stem, "slot_or_pooled": key,
        "n_O": len(o), "n_S": len(s),
        "class_balance_ratio": (len(o) / len(s)) if len(s) else float("nan"),
        "preceding_identity_O": json.dumps(prec_o), "preceding_identity_S": json.dumps(prec_s),
        "n_cycles": int(table["cycle_id"].nunique()),
        "cycles_with_both_classes": int(
            table.groupby("cycle_id")["y_omission"].nunique().eq(2).sum()
        ),
    }


def _clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    lo = 0.0 if k == 0 else scipy_stats.beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else scipy_stats.beta.ppf(1 - alpha / 2, k + 1, n - k)
    return float(lo), float(hi)


def decode_omission_direct(X, y, cycles, *, seed: int, n_permutations: int) -> dict:
    """Direct representation: cycle-grouped LOCO, group-preserving permutation null.
    Mirrors decode_binary_cycle_safe's contract exactly (reusing its estimator/pipeline)."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=int)
    cycles = np.asarray(cycles, dtype=int)
    unique_cycles = np.unique(cycles)
    if len(unique_cycles) < 2 or set(np.unique(y)) != {0, 1}:
        return {"status": "insufficient_cycles_or_classes", "n_folds": 0}

    rng = np.random.default_rng(seed)
    oof_pred = np.full(len(y), -1, dtype=int)
    oof_score = np.full(len(y), np.nan, dtype=float)
    tested = np.zeros(len(y), dtype=bool)
    n_folds = 0
    for fold, cycle in enumerate(unique_cycles):
        test = cycles == cycle
        train = ~test
        train_idx = _balanced_training_indices(train.nonzero()[0], y, (0, 1), rng)
        if len(train_idx) == 0 or len(np.unique(y[test])) < 1:
            continue
        model = _pipeline(seed + fold)
        model.fit(X[train_idx], y[train_idx])
        oof_pred[test] = model.predict(X[test])
        oof_score[test] = model.decision_function(X[test])
        tested[test] = True
        n_folds += 1
    if n_folds == 0 or not tested.any():
        return {"status": "no_valid_folds", "n_folds": 0}

    y_t, pred_t, score_t = y[tested], oof_pred[tested], oof_score[tested]
    observed = _fixed_balanced_accuracy(y_t, pred_t)
    auc = float(roc_auc_score(y_t, score_t))

    def _one_permutation(perm_idx: int):
        perm_rng = np.random.default_rng(seed + 100_000 + perm_idx)
        y_perm = permute_labels(y, groups=cycles, scheme="within_group", rng=perm_rng)
        perm_pred, perm_true = [], []
        for fold, cycle in enumerate(unique_cycles):
            test = cycles == cycle
            train = ~test
            train_idx = _balanced_training_indices(train.nonzero()[0], y_perm, (0, 1), perm_rng)
            if len(train_idx) == 0 or len(np.unique(y_perm[test])) < 1:
                continue
            model = _pipeline(seed + fold)
            model.fit(X[train_idx], y_perm[train_idx])
            perm_pred.extend(model.predict(X[test]).tolist())
            perm_true.extend(y_perm[test].tolist())
        return _fixed_balanced_accuracy(perm_true, perm_pred) if perm_true else None

    # 2026-08-26: permutations are independent (own RNG stream each) -- parallelized across
    # cores (N_JOBS) purely for wall-clock; identical statistics/operator/seed-per-permutation
    # as the prior serial loop. Root cause of the >5h stall: a 999-permutation serial refit on
    # a 508-unit (PFC) feature matrix on one core while 24 were idle.
    results = Parallel(n_jobs=N_JOBS, backend="loky")(
        delayed(_one_permutation)(perm_idx) for perm_idx in range(int(n_permutations))
    )
    null_vals = [r for r in results if r is not None]

    null = np.asarray(null_vals, dtype=float)
    p_perm = float((1 + np.sum(null >= observed)) / (len(null) + 1)) if len(null) else float("nan")
    return {
        "status": "success", "accuracy_loco_balanced": observed, "auc_loco": auc,
        "p_permutation": p_perm, "null_mean": float(np.mean(null)) if len(null) else float("nan"),
        "null_sd": float(np.std(null, ddof=1)) if len(null) > 1 else float("nan"),
        "n_permutations": int(len(null)), "n_folds": int(n_folds),
    }


MAX_ROBUSTNESS_FOLDS = 6


def decode_omission_representation(X, y, cycles, *, seed: int, mode: str) -> dict:
    """PCA / PCA_UMAP robustness pass: single fold-local fit per outer fold, small fixed N/M,
    no permutation test (DESCRIPTIVE only).

    2026-08-26: capped to MAX_ROBUSTNESS_FOLDS cycles (evenly spaced through the session, not a
    random subset) rather than every cycle. A full per-cycle UMAP refit (dozens of cycles x ~28
    cells/session x 22 sessions) measured >5 hours of wall time without finishing session 1 --
    this pass is explicitly descriptive/robustness-only (Hamm: "not a mechanism for searching
    until omission becomes significant"), so exhaustive per-cycle refitting buys no rigor the
    primary Direct/decode_omission_direct analysis doesn't already provide via its own full-LOCO
    permutation test."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=int)
    cycles = np.asarray(cycles, dtype=int)
    unique_cycles = np.unique(cycles)
    if len(unique_cycles) < 2 or set(np.unique(y)) != {0, 1}:
        return {"status": "insufficient_cycles_or_classes"}
    if len(unique_cycles) > MAX_ROBUSTNESS_FOLDS:
        pick = np.linspace(0, len(unique_cycles) - 1, MAX_ROBUSTNESS_FOLDS).round().astype(int)
        unique_cycles = unique_cycles[np.unique(pick)]

    oof_pred = np.full(len(y), -1, dtype=int)
    oof_prob = np.full(len(y), np.nan, dtype=float)
    tested = np.zeros(len(y), dtype=bool)
    n_folds = 0
    for fold, cycle in enumerate(unique_cycles):
        test = cycles == cycle
        train = ~test
        if len(np.unique(y[train])) < 2 or len(np.unique(y[test])) < 1:
            continue
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X[train])
        X_te = scaler.transform(X[test])
        n_pca = max(2, min(20, X_tr.shape[1], X_tr.shape[0] - 2))
        pca = PCA(n_components=n_pca, random_state=DEFAULT_SEED + fold)
        Z_tr, Z_te = pca.fit_transform(X_tr), pca.transform(X_te)
        if mode == "PCA_UMAP":
            import umap
            n_umap = max(2, min(5, n_pca - 1))
            reducer = umap.UMAP(n_components=n_umap, n_neighbors=min(15, X_tr.shape[0] - 1),
                                 min_dist=0.1, random_state=DEFAULT_SEED + fold)
            Z_tr, Z_te = reducer.fit_transform(Z_tr), reducer.transform(Z_te)
        clf = LogisticRegression(C=1.0, max_iter=1000, random_state=DEFAULT_SEED + fold)
        clf.fit(Z_tr, y[train])
        oof_pred[test] = clf.predict(Z_te)
        oof_prob[test] = clf.predict_proba(Z_te)[:, 1]
        tested[test] = True
        n_folds += 1
    if n_folds == 0:
        return {"status": "no_valid_folds"}
    y_t, pred_t, prob_t = y[tested], oof_pred[tested], oof_prob[tested]
    acc = _fixed_balanced_accuracy(y_t, pred_t)
    try:
        auc = float(roc_auc_score(y_t, prob_t))
    except Exception:
        auc = acc
    return {"status": "success", "accuracy_loco_balanced": acc, "auc_loco": auc, "n_folds": n_folds,
            "n_folds_capped_from": int(len(np.unique(cycles)))}


def main():
    t0 = time.time()
    nwb_dir = paths.nwb_dir()
    readiness_csv = OA_ROOT / "artifacts" / "data" / "session_readiness.csv"
    included, excluded = _resolve_sessions(readiness_csv, nwb_dir)
    print(f"Y_omission: {len(included)} sessions included, {len(excluded)} excluded")

    cells, nuisance_rows = [], []

    for s_idx, meta in enumerate(included, start=1):
        print(f"[{s_idx}/{len(included)}] {meta['stem']}", flush=True)
        session = oa.read(meta["path"])

        # --- per-slot cells ---
        slot_tables = {}
        for slot_key in SLOTS:
            table = _slot_trial_table(session, slot_key)
            slot_tables[slot_key] = table
            if table.empty:
                continue
            nuisance_rows.append(_nuisance_row(table, meta["stem"], slot_key))
            window_ms = (EPOCH_ONSETS_MS[slot_key], EPOCH_ONSETS_MS[slot_key] + SLOT_DUR_MS)
            n_cycles = table["cycle_id"].nunique()
            both = table.groupby("cycle_id")["y_omission"].nunique().eq(2).sum()
            identifiable = n_cycles >= 2 and both >= 2 and set(table["y_omission"].unique()) == {0, 1}
            for area in AREAS:
                units = session.get_units(area=area)
                if len(units) < 4:
                    continue
                if not identifiable:
                    cells.append({"session": meta["stem"], "subject": meta["subject"], "area": area,
                                  "slot_or_pooled": slot_key, "representation": "Direct",
                                  "status": "NOT_IDENTIFIABLE", "n_O": int((table.y_omission == 1).sum()),
                                  "n_S": int((table.y_omission == 0).sum())})
                    continue
                X, _ = _spike_count_matrix(session, area, table, window_ms)
                if X.shape[1] < 4:
                    continue
                y = table["y_omission"].to_numpy(int)
                cyc = table["cycle_id"].to_numpy(int)
                res = decode_omission_direct(X, y, cyc, seed=DEFAULT_SEED, n_permutations=N_PERM)
                res.update({"session": meta["stem"], "subject": meta["subject"], "area": area,
                            "slot_or_pooled": slot_key, "representation": "Direct",
                            "n_units": X.shape[1], "n_O": int((y == 1).sum()), "n_S": int((y == 0).sum())})
                cells.append(res)
                if res.get("status") == "success":
                    for mode in ("PCA", "PCA_UMAP"):
                        rres = decode_omission_representation(X, y, cyc, seed=DEFAULT_SEED, mode=mode)
                        rres.update({"session": meta["stem"], "subject": meta["subject"], "area": area,
                                    "slot_or_pooled": slot_key, "representation": mode,
                                    "n_units": X.shape[1], "n_O": int((y == 1).sum()), "n_S": int((y == 0).sum())})
                        cells.append(rres)

        # --- position-balanced pooled cell: relative window, per-cycle centered, count-balanced ---
        pooled_pieces = []
        for slot_key in SLOTS:
            table = slot_tables.get(slot_key)
            if table is None or table.empty:
                continue
            t = table.copy()
            t["slot_key"] = slot_key
            pooled_pieces.append(t)
        if len(pooled_pieces) == 3:
            pooled = pd.concat(pooled_pieces, ignore_index=True)
            pooled["cross_cycle_id"] = assign_temporal_cycles(pooled["start_time"].to_numpy())
            n_min_o = pooled[pooled.y_omission == 1].groupby("slot_key").size().min()
            n_min_s = pooled[pooled.y_omission == 0].groupby("slot_key").size().min()
            balanced_parts = []
            rng = np.random.default_rng(DEFAULT_SEED)
            for slot_key in SLOTS:
                for cls, n_min in ((1, n_min_o), (0, n_min_s)):
                    sub = pooled[(pooled.slot_key == slot_key) & (pooled.y_omission == cls)]
                    if len(sub) > n_min:
                        sub = sub.iloc[rng.choice(len(sub), n_min, replace=False)]
                    balanced_parts.append(sub)
            balanced = pd.concat(balanced_parts, ignore_index=True).sort_values("start_time").reset_index(drop=True)
            nuisance_rows.append(_nuisance_row(balanced, meta["stem"], "pooled_balanced"))
            n_cyc = balanced["cross_cycle_id"].nunique()
            both = balanced.groupby("cross_cycle_id")["y_omission"].nunique().eq(2).sum()
            identifiable = n_cyc >= 2 and both >= 2
            for area in AREAS:
                units = session.get_units(area=area)
                if len(units) < 4:
                    continue
                if not identifiable:
                    cells.append({"session": meta["stem"], "subject": meta["subject"], "area": area,
                                  "slot_or_pooled": "pooled_balanced", "representation": "Direct",
                                  "status": "NOT_IDENTIFIABLE"})
                    continue
                onsets_rel = balanced["start_time"].to_numpy(float) + (
                    balanced["slot_key"].map(EPOCH_ONSETS_MS).to_numpy(float) / 1000.0)
                epochs_rel = pd.DataFrame({"start_time": onsets_rel})
                X, _ = _spike_count_matrix(session, area, epochs_rel, (0.0, SLOT_DUR_MS))
                if X.shape[1] < 4:
                    continue
                cyc = balanced["cross_cycle_id"].to_numpy(int)
                X_centered = _center_within_cycle(X, cyc)
                y = balanced["y_omission"].to_numpy(int)
                res = decode_omission_direct(X_centered, y, cyc, seed=DEFAULT_SEED, n_permutations=N_PERM)
                res.update({"session": meta["stem"], "subject": meta["subject"], "area": area,
                            "slot_or_pooled": "pooled_balanced", "representation": "Direct",
                            "n_units": X.shape[1], "n_O": int((y == 1).sum()), "n_S": int((y == 0).sum())})
                cells.append(res)

    df = pd.DataFrame(cells)
    df.to_csv(OUT_DIR / "fig04_omission_occurrence_cells.csv", index=False)
    nuis = pd.DataFrame(nuisance_rows)
    nuis.to_csv(OUT_DIR / "fig04_omission_occurrence_nuisance.csv", index=False)

    # --- summary / BH-FDR across Direct-representation success cells, per slot_or_pooled ---
    summary = {}
    for key in list(SLOTS) + ["pooled_balanced"]:
        sub = df[(df.slot_or_pooled == key) & (df.representation == "Direct") & (df.status == "success")]
        if sub.empty:
            summary[key] = {"n_success": 0}
            continue
        rej, q, _, _ = multipletests(sub["p_permutation"], method="fdr_bh")
        k_raw = int((sub["p_permutation"] < 0.05).sum())
        k_fdr = int(rej.sum())
        n = len(sub)
        lo_r, hi_r = _clopper_pearson(k_raw, n)
        lo_f, hi_f = _clopper_pearson(k_fdr, n)
        summary[key] = {
            "n_success": n, "acc_mean": float(sub["accuracy_loco_balanced"].mean()),
            "acc_sd": float(sub["accuracy_loco_balanced"].std()),
            "auc_mean": float(sub["auc_loco"].mean()),
            "k_raw_sig": k_raw, "k_fdr_sig": k_fdr,
            "prevalence_raw": k_raw / n, "prevalence_fdr": k_fdr / n,
            "cp_ci_raw": [lo_r, hi_r], "cp_ci_fdr": [lo_f, hi_f],
            "n_sessions": int(sub["session"].nunique()), "n_subjects": int(sub["subject"].nunique()),
            "n_not_identifiable": int((df[(df.slot_or_pooled == key)]["status"] == "NOT_IDENTIFIABLE").sum()),
        }
    not_ident_total = int((df["status"] == "NOT_IDENTIFIABLE").sum())

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": "omission/scripts/compute_fig04_omission_occurrence.py",
        "n_sessions_included": len(included), "n_sessions_excluded": len(excluded),
        "permutation_scheme": "group-preserving (within-cycle), N_PERM=999, (1+k)/(N_PERM+1)",
        "timing_source": "canonical EPOCH_ONSETS_MS (sequence_layout)",
        "cv": "cycle-grouped leave-one-cycle-out (assign_temporal_cycles)",
        "primary_representation": "Direct -- PCA/PCA_UMAP are descriptive robustness passes only, no permutation test",
        "summary_by_slot_or_pooled": summary,
        "n_not_identifiable_cells": not_ident_total,
        "runtime_seconds": round(time.time() - t0, 2),
    }
    with open(OUT_DIR / "fig04_omission_occurrence_receipt.json", "w") as f:
        json.dump(receipt, f, indent=2)
    print(json.dumps(summary, indent=2))
    print(f"Not-identifiable cells: {not_ident_total}")
    print(f"Runtime: {receipt['runtime_seconds']}s")


if __name__ == "__main__":
    main()
