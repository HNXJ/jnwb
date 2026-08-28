#!/usr/bin/env python3
"""Figure 4 extension: positive-control, baseline, and softmax decoding + an SSA mechanistic panel.

Extends ``compute_omission_identity_leakage_safe.py`` (unedited except for the 2026-08-20
sidecar-gate relaxation) rather than duplicating its cycle-safe machinery. Imports
``assign_temporal_cycles``, ``_spike_count_matrix``, ``_balanced_training_indices``,
``_within_cycle_permutation``, ``_trial_table``, ``_resolve_sessions``, ``decode_binary_cycle_safe``,
``AREAS``/``SLOTS``/``LABELS`` directly from that module.

Four new analyses, all leave-one-temporal-cycle-out (LOCO), all with a within-cycle-permutation
null -- no new CV design except where noted:

1. **real_stim** (Panel B, positive control) -- decode the REAL presented A/B identity at p1
   (AAAB/BBBA trials, never omitted), same accuracy metric as the omission decode so the two are
   directly comparable. Trial table comes from ``omission.jnwb_ext.structured_identity
   .build_canonical_trial_table``'s POSITIVE_CONTROL rows (``presented_identity``), not a new
   trial-selection rule.
2. **fixation** (Panel D, baseline control) -- the SAME trial set and labels as the omission-slot
   decode (``_trial_table`` from the leakage-safe script, A/B/R at p2/p3/p4), but with spike
   counts drawn from the pre-trial fixation window (fx: -500..0ms relative to P1) instead of the
   omission slot. Expected to sit at chance everywhere -- this is the literal "is the omission
   decode doing anything beyond what this pipeline gives on pure noise" negative control.
3. **softmax_p4** (Panel F) -- 3-way [p_A, p_B, p_R] decode via multinomial logistic regression,
   restricted to p4 ONLY. p2/p3 are excluded here because the omitted identity is deterministically
   recoverable from the preceding real stimulus at those two slots (Milestone 1 finding, cited in
   ``docs/handout_3_..._reversal_design.md`` and in ``decode_identity_sliding_window.py``'s own
   ``reversal_generalization`` docstring) -- a pooled p2+p3+p4 fit would partly be reading out that
   trivial confound rather than a genuine representation of the CURRENTLY missing identity. R is
   unaffected (never has a deterministic identity to leak) but is restricted to p4 too here for one
   consistent CV design across the whole panel, per Hamm's 2026-08-20 direction.
4. **ssa_index** (Panel H) -- per unit, per session/area, regress the unit's own omission-slot
   spike count (pooled across p2/p3/p4 -- fine here since the regression target is the PRECEDING
   identity, not the current expected identity, so the p2/p3 degeneracy above does not apply) on
   the identity of the immediately preceding REAL stimulus, within-cycle mean-centered to remove
   generic level/gain drift (same centering pattern as
   ``omission_identity.decode_identity_cycle_deconfound``, not that function itself). Correlated,
   per area/slot cell, against that unit's |coefficient| in a linear A/B decoder fit on ALL trials
   in that cell (not LOCO-restricted -- this is a descriptive feature-importance read, not an
   accuracy claim, so held-out folds are not required). Explicitly descriptive/exploratory: few,
   non-independent units per cell (``omission-statistics``'s standing rule on small aggregate-unit
   correlations).

Outputs, all under ``--output-dir`` (default matches the leakage-safe script's OA_ROOT-relative
default):

* ``omission_identity_extended_cells.csv`` -- one row per (session, area, slot_key, analysis) for
  real_stim/fixation/softmax_p4;
* ``omission_identity_extended_softmax_oof.csv`` -- held-out [p_A, p_B, p_R] per trial;
* ``omission_identity_extended_ssa.csv`` -- one row per (session, area, slot_key, unit) SSA index
  and matched decoder-coefficient magnitude;
* ``omission_identity_extended_receipt.json`` -- provenance, same conventions as the leakage-safe
  script's receipt.

Spike-only. No LFP claim.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT))
OA_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))

import omission as oa  # noqa: E402
from omission.jnwb_ext.omission_identity import OMISSION_IDENTITY_CONDITIONS  # noqa: E402
from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS  # noqa: E402
from omission.jnwb_ext.structured_identity import (  # noqa: E402
    build_canonical_trial_table,
    POSITIVE_CONTROL,
    MAIN_ANALYSIS,
)
from jnwb import paths  # noqa: E402
from jnwb.paths import sha256_file as _sha256  # noqa: E402

from compute_omission_identity_leakage_safe import (  # noqa: E402
    AREAS,
    SLOTS,
    LABELS,
    DEFAULT_SEED,
    DEFAULT_PERMUTATIONS,
    ESTIMATOR,
    assign_temporal_cycles,
    _spike_count_matrix,
    _balanced_training_indices,
    _within_cycle_permutation,
    _trial_table,
    _resolve_sessions,
    decode_binary_cycle_safe,
)

REAL_STIM_WINDOW_MS = (EPOCH_ONSETS_MS["p1"], EPOCH_ONSETS_MS["d1"])  # 0..531ms, real A/B stim
FIXATION_WINDOW_MS = (EPOCH_ONSETS_MS["fx"], EPOCH_ONSETS_MS["p1"])  # -500..0ms, pre-trial

SOFTMAX_ESTIMATOR = {
    "model": "sklearn.linear_model.LogisticRegression",
    "multi_class": "multinomial",
    "C": 1.0,
    "scaler": "StandardScaler",
}


# ---- Panel B: real presented-stimulus positive control -------------------------------------

def _real_stim_trial_table(session) -> pd.DataFrame:
    """POSITIVE_CONTROL rows (AAAB/BBBA at p1, always real) from the shared trial ontology."""
    table = build_canonical_trial_table(session, slot_keys=("p2", "p3", "p4"))
    if table.empty:
        return pd.DataFrame()
    pc = table[(table["analysis"] == POSITIVE_CONTROL) & table["eligible"]].copy()
    if pc.empty:
        return pd.DataFrame()
    pc["label_int"] = (pc["presented_identity"] == "A").astype(int)
    pc["cycle_id"] = pc["cycle"].astype(int)
    pc["start_time"] = pd.to_numeric(pc["start_time"], errors="coerce")
    return pc.dropna(subset=["start_time"]).reset_index(drop=True)


def _epochs_from(table: pd.DataFrame, label_int: int) -> pd.DataFrame:
    sub = table[table["label_int"] == label_int]
    return sub[["start_time"]].rename(columns={"start_time": "start_time"})


# ---- Panel F: p4-only 3-way softmax ----------------------------------------------------------

def _softmax_pipeline(seed: int) -> Pipeline:
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "classifier",
                # sklearn >=1.7 removed multi_class= -- lbfgs (the default solver) already fits a
                # multinomial (softmax) model automatically whenever y has >2 classes.
                LogisticRegression(
                    C=SOFTMAX_ESTIMATOR["C"],
                    max_iter=2000,
                    random_state=seed,
                ),
            ),
        ]
    )


def decode_softmax_p4_cycle_safe(
    X: np.ndarray, labels: np.ndarray, cycles: np.ndarray, *, seed: int = DEFAULT_SEED,
    n_permutations: int = DEFAULT_PERMUTATIONS,
) -> dict:
    """3-way [p_A, p_B, p_R] softmax, LOCO folds, cross-entropy vs a within-cycle-permutation null.

    Same leakage-safety design as ``decode_binary_cycle_safe`` (fixed cycle folds, per-fold
    training-class balance, within-cycle label permutation for the null) but evaluated on
    cross-entropy (log-loss) of the held-out softmax output instead of balanced accuracy, since a
    hard-label accuracy would discard the calibrated-probability information this panel exists to
    report.
    """
    X = np.asarray(X, dtype=float)
    labels = np.asarray(labels, dtype=int)
    cycles = np.asarray(cycles, dtype=int)
    classes = (0, 1, 2)
    unique_cycles = np.unique(cycles)
    if len(unique_cycles) < 2 or len(set(np.unique(labels)) & set(classes)) < 3:
        return {"status": "insufficient_cycles_or_classes", "n_folds": 0}

    rng = np.random.default_rng(seed)
    oof_rows: list[dict] = []
    fold_assignments = np.full(len(labels), -1, dtype=int)

    for fold, cycle in enumerate(unique_cycles):
        test = cycles == cycle
        train = ~test
        train_idx = _balanced_training_indices(train.nonzero()[0], labels, classes, rng)
        if len(train_idx) == 0 or len(np.unique(labels[test])) < 1:
            continue
        model = _softmax_pipeline(seed + fold)
        model.fit(X[train_idx], labels[train_idx])
        proba = model.predict_proba(X[test])
        # LogisticRegression orders predict_proba columns by model.classes_ -- realign to (A,B,R).
        col_for = {cls: i for i, cls in enumerate(model.named_steps["classifier"].classes_)}
        proba_abr = np.stack([proba[:, col_for[c]] if c in col_for else np.zeros(len(proba))
                               for c in classes], axis=1)
        fold_assignments[test] = fold
        for row_idx, y, p in zip(np.flatnonzero(test), labels[test], proba_abr):
            oof_rows.append(
                {
                    "row_index": int(row_idx), "fold": int(fold), "cycle_id": int(cycle),
                    "y_true": int(y), "p_a": float(p[0]), "p_b": float(p[1]), "p_r": float(p[2]),
                }
            )

    if not oof_rows:
        return {"status": "no_valid_folds", "n_folds": 0}

    oof = pd.DataFrame(oof_rows).sort_values("row_index").reset_index(drop=True)
    proba_matrix = oof[["p_a", "p_b", "p_r"]].to_numpy()
    observed_loss = float(log_loss(oof.y_true, proba_matrix, labels=list(classes)))

    null_losses: list[float] = []
    for perm_idx in range(int(n_permutations)):
        perm_rng = np.random.default_rng(seed + 200_000 + perm_idx)
        perm_labels = _within_cycle_permutation(labels, cycles, perm_rng)
        perm_true: list[int] = []
        perm_proba: list[np.ndarray] = []
        for fold, cycle in enumerate(unique_cycles):
            test = cycles == cycle
            train = ~test
            train_idx = _balanced_training_indices(train.nonzero()[0], perm_labels, classes, perm_rng)
            if len(train_idx) == 0 or len(np.unique(perm_labels[test])) < 1:
                continue
            model = _softmax_pipeline(seed + fold)
            model.fit(X[train_idx], perm_labels[train_idx])
            proba = model.predict_proba(X[test])
            col_for = {cls: i for i, cls in enumerate(model.named_steps["classifier"].classes_)}
            proba_abr = np.stack([proba[:, col_for[c]] if c in col_for else np.zeros(len(proba))
                                   for c in classes], axis=1)
            perm_proba.append(proba_abr)
            perm_true.extend(perm_labels[test].tolist())
        if perm_true:
            null_losses.append(
                float(log_loss(perm_true, np.concatenate(perm_proba, axis=0), labels=list(classes)))
            )

    null = np.asarray(null_losses, dtype=float)
    # Lower cross-entropy is better, so the null-exceedance test is one-sided in the other
    # direction from accuracy: p = fraction of null draws AT LEAST AS GOOD (<=) as observed.
    p_value = (
        float((np.sum(null <= observed_loss) + 1) / (len(null) + 1)) if len(null) else float("nan")
    )
    return {
        "status": "success",
        "cross_entropy": observed_loss,
        "p_permutation": p_value,
        "null_mean": float(np.mean(null)) if len(null) else float("nan"),
        "null_sd": float(np.std(null, ddof=1)) if len(null) > 1 else float("nan"),
        "n_permutations": int(len(null)),
        "n_folds": int(len(np.unique(oof.fold))),
        "oof": oof,
    }


# ---- Panel H: stimulus-specific-adaptation (SSA) index ---------------------------------------

def _ssa_trial_table(session) -> pd.DataFrame:
    """MAIN_ANALYSIS eligible A/B rows (p2/p3/p4) carrying ``preceding_identity`` -- the 1-back
    real-stimulus label the SSA index regresses on. Not subject to the p2/p3 degeneracy that
    blocks the softmax panel: the target here is the PRECEDING identity, not the current expected
    one, so p2/p3/p4 can be pooled freely.
    """
    table = build_canonical_trial_table(session, slot_keys=("p2", "p3", "p4"))
    if table.empty:
        return pd.DataFrame()
    main = table[(table["analysis"] == MAIN_ANALYSIS) & table["eligible"]].copy()
    main = main.dropna(subset=["preceding_identity"])
    if main.empty:
        return pd.DataFrame()
    main["preceding_int"] = (main["preceding_identity"] == "A").astype(int)
    main["cycle_id"] = main["cycle"].astype(int)
    main["start_time"] = pd.to_numeric(main["start_time"], errors="coerce")
    return main.dropna(subset=["start_time"]).reset_index(drop=True)


def compute_ssa_index(session, area: str, table: pd.DataFrame) -> pd.DataFrame:
    """Per-unit SSA index: within-cycle-centered omission-slot rate, regressed on 1-back real
    identity, reported as (mean rate | preceding=A) - (mean rate | preceding=B) after centering.
    """
    if table.empty:
        return pd.DataFrame()
    rows = []
    for slot_key, part in table.groupby("slot_key"):
        window = (
            OMISSION_IDENTITY_CONDITIONS[slot_key]["slot_onset_ms"],
            OMISSION_IDENTITY_CONDITIONS[slot_key]["slot_end_ms"],
        )
        X, units = _spike_count_matrix(session, area, part, window)
        if X.shape[1] == 0 or len(part) < 4:
            continue
        cycles = part["cycle_id"].to_numpy(int)
        preceding = part["preceding_int"].to_numpy(int)
        centered = X.copy()
        for cycle in np.unique(cycles):
            mask = cycles == cycle
            centered[mask] -= centered[mask].mean(axis=0, keepdims=True)
        for col, row_index in enumerate(units.index):
            a_vals = centered[preceding == 1, col]
            b_vals = centered[preceding == 0, col]
            if len(a_vals) < 2 or len(b_vals) < 2:
                continue
            rows.append(
                {
                    "slot_key": slot_key,
                    "unit_row": int(row_index),
                    "ssa_index": float(np.mean(a_vals) - np.mean(b_vals)),
                    "n_preceding_a": int(len(a_vals)),
                    "n_preceding_b": int(len(b_vals)),
                }
            )
    return pd.DataFrame(rows)


def fit_full_linear_coefficients(X: np.ndarray, labels: np.ndarray, seed: int) -> np.ndarray | None:
    """Coefficient magnitude per unit from ONE model fit on all trials in a cell -- a descriptive
    feature-importance read for the SSA correlation, not an accuracy claim, so no LOCO restriction.
    """
    if X.shape[1] == 0 or len(np.unique(labels)) < 2:
        return None
    model = Pipeline(
        [("scaler", StandardScaler()),
         ("classifier", SVC(kernel="linear", C=ESTIMATOR["C"], random_state=seed))]
    )
    model.fit(X, labels)
    return np.abs(model.named_steps["classifier"].coef_).ravel()


# ---- driver ------------------------------------------------------------------------------

def run(*, readiness_csv: Path, nwb_dir: Path, output_dir: Path, seed: int = DEFAULT_SEED,
        n_permutations: int = DEFAULT_PERMUTATIONS, limit: int | None = None) -> dict:
    started = time.time()
    included, excluded = _resolve_sessions(readiness_csv, nwb_dir)
    if limit is not None:
        included = included[:limit]
    if not included:
        raise RuntimeError("no eligible NWB sessions resolved from the readiness gate")

    cell_rows: list[dict] = []
    softmax_oof_rows: list[dict] = []
    ssa_rows: list[dict] = []
    errors: list[dict] = []

    for session_number, meta in enumerate(included, start=1):
        print(f"[{session_number}/{len(included)}] {meta['stem']}", flush=True)
        try:
            session = oa.read(meta["path"])

            # -- Panel B: real_stim positive control (p1, AAAB/BBBA) --
            real_stim_table = _real_stim_trial_table(session)
            for area in AREAS:
                if real_stim_table.empty:
                    cell_rows.append({"session": meta["stem"], "subject": meta["subject"],
                                       "area": area, "slot_key": "p1", "analysis": "real_stim",
                                       "status": "insufficient_units"})
                    continue
                matrices = [
                    _spike_count_matrix(session, area, _epochs_from(real_stim_table, li),
                                         REAL_STIM_WINDOW_MS)[0]
                    for li in (0, 1)
                ]
                units = _spike_count_matrix(session, area, real_stim_table.iloc[:1],
                                             REAL_STIM_WINDOW_MS)[1]
                if any(m.shape[1] == 0 for m in matrices):
                    cell_rows.append({"session": meta["stem"], "subject": meta["subject"],
                                       "area": area, "slot_key": "p1", "analysis": "real_stim",
                                       "status": "insufficient_units"})
                    continue
                X = np.concatenate(matrices, axis=0)
                labels_sorted = np.concatenate(
                    [np.zeros(matrices[0].shape[0], int), np.ones(matrices[1].shape[0], int)]
                )
                order = np.concatenate(
                    [real_stim_table.index[real_stim_table.label_int == 0].to_numpy(),
                     real_stim_table.index[real_stim_table.label_int == 1].to_numpy()]
                )
                cycles_sorted = real_stim_table.loc[order, "cycle_id"].to_numpy(int)
                result = decode_binary_cycle_safe(X, labels_sorted, cycles_sorted, seed=seed,
                                                   n_permutations=n_permutations)
                cell_rows.append({
                    "session": meta["stem"], "subject": meta["subject"], "area": area,
                    "slot_key": "p1", "analysis": "real_stim",
                    "status": result.get("status", "unknown"),
                    "n_units": int(X.shape[1]),
                    "accuracy_loco_balanced": result.get("accuracy_loco_balanced", np.nan),
                    "auc_loco": result.get("auc_loco", np.nan),
                    "p_permutation": result.get("p_permutation", np.nan),
                    "null_mean": result.get("null_mean", np.nan),
                    "null_sd": result.get("null_sd", np.nan),
                    "n_permutations": result.get("n_permutations", 0),
                    "n_folds": result.get("n_folds", 0),
                    "feature_window_ms": json.dumps(list(REAL_STIM_WINDOW_MS)),
                    "seed": seed,
                })

            # -- Panel D: fixation baseline vs the omission-slot decode --
            for slot_key in SLOTS:
                trial_table = _trial_table(session, slot_key)
                if trial_table.empty or trial_table["cycle_id"].nunique() < 2:
                    continue
                for area in AREAS:
                    X_fix, units_fix = _spike_count_matrix(session, area, trial_table,
                                                             FIXATION_WINDOW_MS)
                    if X_fix.shape[1] == 0:
                        continue
                    labels = trial_table["label_int"].to_numpy(int)
                    cycles = trial_table["cycle_id"].to_numpy(int)
                    binary_mask = labels < 2
                    result = decode_binary_cycle_safe(
                        X_fix[binary_mask], labels[binary_mask], cycles[binary_mask],
                        seed=seed, n_permutations=n_permutations,
                    )
                    cell_rows.append({
                        "session": meta["stem"], "subject": meta["subject"], "area": area,
                        "slot_key": slot_key, "analysis": "fixation",
                        "status": result.get("status", "unknown"),
                        "n_units": int(X_fix.shape[1]),
                        "accuracy_loco_balanced": result.get("accuracy_loco_balanced", np.nan),
                        "auc_loco": result.get("auc_loco", np.nan),
                        "p_permutation": result.get("p_permutation", np.nan),
                        "null_mean": result.get("null_mean", np.nan),
                        "null_sd": result.get("null_sd", np.nan),
                        "n_permutations": result.get("n_permutations", 0),
                        "n_folds": result.get("n_folds", 0),
                        "feature_window_ms": json.dumps(list(FIXATION_WINDOW_MS)),
                        "seed": seed,
                    })

            # -- Panel F: p4-only 3-way softmax --
            p4_table = _trial_table(session, "p4")
            if not p4_table.empty and p4_table["cycle_id"].nunique() >= 2:
                for area in AREAS:
                    X_p4, units_p4 = _spike_count_matrix(
                        session, area, p4_table,
                        (OMISSION_IDENTITY_CONDITIONS["p4"]["slot_onset_ms"],
                         OMISSION_IDENTITY_CONDITIONS["p4"]["slot_end_ms"]),
                    )
                    if X_p4.shape[1] == 0:
                        continue
                    labels = p4_table["label_int"].to_numpy(int)
                    cycles = p4_table["cycle_id"].to_numpy(int)
                    result = decode_softmax_p4_cycle_safe(
                        X_p4, labels, cycles, seed=seed, n_permutations=n_permutations,
                    )
                    cell_rows.append({
                        "session": meta["stem"], "subject": meta["subject"], "area": area,
                        "slot_key": "p4", "analysis": "softmax_p4",
                        "status": result.get("status", "unknown"),
                        "n_units": int(X_p4.shape[1]),
                        "cross_entropy": result.get("cross_entropy", np.nan),
                        "p_permutation": result.get("p_permutation", np.nan),
                        "null_mean": result.get("null_mean", np.nan),
                        "null_sd": result.get("null_sd", np.nan),
                        "n_permutations": result.get("n_permutations", 0),
                        "n_folds": result.get("n_folds", 0),
                        "seed": seed,
                    })
                    if result.get("status") == "success":
                        for row in result["oof"].to_dict("records"):
                            softmax_oof_rows.append({
                                "session": meta["stem"], "subject": meta["subject"],
                                "area": area, "slot_key": "p4", **row,
                            })

                    # -- Panel H: SSA index for this (session, area), correlated against this
                    # cell's full-fit |coefficient| (binary A/B, all p2/p3/p4 trials pooled) --
                    ssa_table = _ssa_trial_table(session)
                    ssa_here = compute_ssa_index(session, area, ssa_table)
                    if not ssa_here.empty:
                        all_slots_table = pd.concat(
                            [_trial_table(session, s) for s in SLOTS], ignore_index=True
                        )
                        ab = all_slots_table[all_slots_table.label_int < 2]
                        X_ab, units_ab = _spike_count_matrix(
                            session, area, ab, (
                                OMISSION_IDENTITY_CONDITIONS["p2"]["slot_onset_ms"],
                                OMISSION_IDENTITY_CONDITIONS["p2"]["slot_end_ms"],
                            ),
                        ) if not ab.empty else (np.zeros((0, 0)), None)
                        coefs = fit_full_linear_coefficients(
                            X_ab, ab["label_int"].to_numpy(int), seed
                        ) if X_ab.shape[1] else None
                        if coefs is not None and units_ab is not None:
                            coef_by_unit = dict(zip(units_ab.index, coefs))
                            ssa_here["abs_coef"] = ssa_here["unit_row"].map(coef_by_unit)
                        ssa_here.insert(0, "area", area)
                        ssa_here.insert(0, "subject", meta["subject"])
                        ssa_here.insert(0, "session", meta["stem"])
                        ssa_rows.extend(ssa_here.to_dict("records"))

        except Exception as exc:
            errors.append({"session": meta["stem"], "reason": type(exc).__name__, "detail": str(exc)})
            print(f"  ERROR {type(exc).__name__}: {exc}", flush=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "cells": output_dir / "omission_identity_extended_cells.csv",
        "softmax_oof": output_dir / "omission_identity_extended_softmax_oof.csv",
        "ssa": output_dir / "omission_identity_extended_ssa.csv",
    }
    pd.DataFrame(cell_rows).to_csv(outputs["cells"], index=False)
    pd.DataFrame(softmax_oof_rows).to_csv(outputs["softmax_oof"], index=False)
    pd.DataFrame(ssa_rows).to_csv(outputs["ssa"], index=False)

    receipt = {
        "analysis_status": "complete" if not errors else "failed_with_errors",
        "generated_utc": pd.Timestamp.utcnow().isoformat(),
        "git_sha": __import__("subprocess").check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "nwb_dir": str(nwb_dir),
        "readiness_csv": str(readiness_csv),
        "eligible_sessions": included,
        "excluded_sessions": excluded,
        "seed": seed,
        "n_permutations_requested": n_permutations,
        "estimator_binary": ESTIMATOR,
        "estimator_softmax": SOFTMAX_ESTIMATOR,
        "fold_scheme": "leave_one_temporal_cycle_out",
        "softmax_scope": "p4 only -- p2/p3 excluded (preceding-identity degeneracy, see docstring)",
        "real_stim_window_ms": list(REAL_STIM_WINDOW_MS),
        "fixation_window_ms": list(FIXATION_WINDOW_MS),
        "ssa_definition": "within-cycle-centered omission-slot rate, (preceding=A mean) - "
                           "(preceding=B mean); descriptive, not inferential",
        "signal": "SPK/SUA only",
        "errors": errors,
        "runtime_seconds": time.time() - started,
        "output_hashes": {key: _sha256(path) for key, path in outputs.items()},
        "output_paths": {key: str(path) for key, path in outputs.items()},
    }
    receipt_path = output_dir / "omission_identity_extended_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(
        f"Completed {len(included)} eligible sessions, {len(cell_rows)} cells, "
        f"{len(ssa_rows)} SSA rows in {receipt['runtime_seconds']:.1f}s.",
        flush=True,
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readiness", type=Path,
                        default=OA_ROOT / "artifacts" / "data" / "session_readiness.csv")
    parser.add_argument("--nwb-dir", type=Path, default=paths.nwb_dir())
    parser.add_argument("--output-dir", type=Path, default=OA_ROOT / "outputs" / "classification")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--permutations", type=int, default=DEFAULT_PERMUTATIONS)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    if not args.nwb_dir.exists():
        raise FileNotFoundError(
            f"NWB directory not found: {args.nwb_dir}; pass --nwb-dir or set OMISSION_NWB_DIR"
        )
    run(readiness_csv=args.readiness, nwb_dir=args.nwb_dir, output_dir=args.output_dir,
        seed=args.seed, n_permutations=args.permutations, limit=args.limit)


if __name__ == "__main__":
    main()
