#!/usr/bin/env python3
"""Leakage-safe Figure 4 omission-identity decoding.

This is a new analysis path.  It deliberately does not change
``jnwb.omission_identity`` or reuse the random-CV result as confirmatory evidence.

The leakage unit is the repeated temporal cycle in a session.  Cycles are detected from the
combined P1-aligned A/B/R trial timestamps, folds leave one complete cycle out, and training
classes are balanced inside each training fold only.  The permutation null keeps the same fold
assignments and permutes labels within cycle, preserving the temporal grouping and per-cycle
class counts.

Outputs are written only after the requested corpus has completed:

* ``omission_identity_leakage_safe_cells.csv`` -- one row per session/area/slot;
* ``omission_identity_leakage_safe_oof.csv`` -- persisted held-out predictions;
* ``omission_identity_leakage_safe_folds.csv`` -- persisted trial/cycle/fold assignments;
* ``omission_identity_leakage_safe_null.csv`` -- one row per cell/permutation;
* ``omission_identity_leakage_safe_receipt.json`` -- provenance and output hashes.

The script is spike-only.  It does not create an LFP decoding claim or an LFP null.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import jnwb as oa  # noqa: E402
from jnwb.omission_identity import OMISSION_IDENTITY_CONDITIONS  # noqa: E402
from jnwb.permutation import permute_labels  # noqa: E402
from jnwb import paths  # noqa: E402


AREAS = ["FEF", "PFC", "TEO", "V4", "V3", "V2", "V1"]
SLOTS = ("p2", "p3", "p4")
LABELS = ("A", "B", "R")
PHASE_FOR_P1_ALIGNMENT = 2
DEFAULT_SEED = 42
DEFAULT_PERMUTATIONS = 1000
ESTIMATOR = {
    "model": "sklearn.svm.SVC",
    "kernel": "linear",
    "C": 1.0,
    "scaler": "StandardScaler",
}


def assign_temporal_cycles(start_times_s: Iterable[float], gap_factor: float = 10.0) -> np.ndarray:
    """Return cycle ids in the original order, splitting only large temporal gaps.

    The median positive inter-trial gap is the within-cycle reference.  A cycle boundary is a
    gap greater than ``gap_factor`` times that reference.  This pure helper is tested separately
    because changing the leakage unit changes the estimand.
    """
    times = np.asarray(list(start_times_s), dtype=float)
    if times.size == 0:
        return np.array([], dtype=int)
    if not np.isfinite(times).all():
        raise ValueError("cycle assignment requires finite start times")
    order = np.argsort(times, kind="stable")
    sorted_times = times[order]
    gaps = np.diff(sorted_times)
    positive = gaps[gaps > 0]
    reference = float(np.median(positive)) if positive.size else np.inf
    threshold = gap_factor * reference
    sorted_cycles = np.zeros(times.size, dtype=int)
    if np.isfinite(threshold):
        for boundary in np.flatnonzero(gaps > threshold):
            sorted_cycles[boundary + 1 :] += 1
    cycles = np.empty(times.size, dtype=int)
    cycles[order] = sorted_cycles
    return cycles


def _pipeline(seed: int, multiclass: bool = False) -> Pipeline:
    # SVC's random_state is explicit even though the linear solver is deterministic here.
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "classifier",
                SVC(
                    kernel=ESTIMATOR["kernel"],
                    C=ESTIMATOR["C"],
                    probability=False,
                    decision_function_shape="ovr" if multiclass else "ovr",
                    random_state=seed,
                ),
            ),
        ]
    )


def _balanced_training_indices(
    indices: np.ndarray, labels: np.ndarray, classes: tuple[int, ...], rng: np.random.Generator
) -> np.ndarray:
    pools = [indices[labels[indices] == cls] for cls in classes]
    if any(len(pool) == 0 for pool in pools):
        return np.array([], dtype=int)
    n_each = min(len(pool) for pool in pools)
    selected = [
        pool if len(pool) == n_each else rng.choice(pool, n_each, replace=False) for pool in pools
    ]
    return np.concatenate(selected)


def _within_cycle_permutation(
    labels: np.ndarray, cycles: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """Permute labels within each cycle, preserving cycle-level class counts.

    Thin wrapper over the shared jnwb.permutation.permute_labels primitive (2026-08-10) --
    kept as a local name since every call site in this file already uses it, but the actual
    exchangeability logic lives in one place now, not duplicated per script.
    """
    return permute_labels(labels, groups=cycles, scheme="within_group", rng=rng)


def _fixed_balanced_accuracy(y_true: Iterable[int], y_pred: Iterable[int]) -> float:
    """Balanced accuracy with an explicit two-class denominator and no single-class warning."""
    matrix = confusion_matrix(y_true, y_pred, labels=[0, 1]).astype(float)
    denominators = matrix.sum(axis=1)
    recalls = np.divide(
        np.diag(matrix),
        denominators,
        out=np.full(2, np.nan, dtype=float),
        where=denominators > 0,
    )
    return float(np.nanmean(recalls))


def decode_binary_cycle_safe(
    X: np.ndarray,
    labels: np.ndarray,
    cycles: np.ndarray,
    *,
    seed: int = DEFAULT_SEED,
    n_permutations: int = DEFAULT_PERMUTATIONS,
) -> dict:
    """Decode A/B with fixed leave-one-cycle-out folds and an exchangeability-matched null."""
    X = np.asarray(X, dtype=float)
    labels = np.asarray(labels, dtype=int)
    cycles = np.asarray(cycles, dtype=int)
    if X.ndim != 2 or len(labels) != len(cycles) or X.shape[0] != len(labels):
        raise ValueError("X, labels, and cycles have incompatible shapes")
    if not np.isfinite(X).all():
        raise ValueError("spike-count features contain non-finite values")

    unique_cycles = np.unique(cycles)
    if len(unique_cycles) < 2 or set(np.unique(labels)) != {0, 1}:
        return {"status": "insufficient_cycles_or_classes", "n_folds": 0}

    rng = np.random.default_rng(seed)
    oof_rows: list[dict] = []
    fold_metrics: list[float] = []
    fold_assignments = np.full(len(labels), -1, dtype=int)

    for fold, cycle in enumerate(unique_cycles):
        test = cycles == cycle
        train = ~test
        train_idx = _balanced_training_indices(train.nonzero()[0], labels, (0, 1), rng)
        if len(train_idx) == 0 or len(np.unique(labels[test])) < 1:
            continue
        model = _pipeline(seed + fold)
        model.fit(X[train_idx], labels[train_idx])
        pred = model.predict(X[test])
        score = model.decision_function(X[test])
        fold_acc = _fixed_balanced_accuracy(labels[test], pred)
        fold_metrics.append(float(fold_acc))
        fold_assignments[test] = fold
        for row_idx, y, yhat, s in zip(np.flatnonzero(test), labels[test], pred, score):
            oof_rows.append(
                {
                    "row_index": int(row_idx),
                    "fold": int(fold),
                    "cycle_id": int(cycle),
                    "y_true": int(y),
                    "y_pred": int(yhat),
                    "decision_score": float(s),
                }
            )

    if not oof_rows:
        return {"status": "no_valid_folds", "n_folds": 0}

    oof = pd.DataFrame(oof_rows).sort_values("row_index").reset_index(drop=True)
    observed = _fixed_balanced_accuracy(oof.y_true, oof.y_pred)
    auc = float(roc_auc_score(oof.y_true, oof.decision_score))

    null_rows: list[float] = []
    for perm_idx in range(int(n_permutations)):
        perm_rng = np.random.default_rng(seed + 100_000 + perm_idx)
        perm_labels = _within_cycle_permutation(labels, cycles, perm_rng)
        perm_pred: list[int] = []
        perm_true: list[int] = []
        for fold, cycle in enumerate(unique_cycles):
            test = cycles == cycle
            train = ~test
            train_idx = _balanced_training_indices(
                train.nonzero()[0], perm_labels, (0, 1), perm_rng
            )
            if len(train_idx) == 0 or len(np.unique(perm_labels[test])) < 1:
                continue
            model = _pipeline(seed + fold)
            model.fit(X[train_idx], perm_labels[train_idx])
            perm_pred.extend(model.predict(X[test]).tolist())
            perm_true.extend(perm_labels[test].tolist())
        if perm_true:
            null_rows.append(_fixed_balanced_accuracy(perm_true, perm_pred))

    null = np.asarray(null_rows, dtype=float)
    p_value = (
        float((np.sum(null >= observed) + 1) / (len(null) + 1)) if len(null) else float("nan")
    )
    return {
        "status": "success",
        "accuracy_loco_balanced": observed,
        "auc_loco": auc,
        "p_permutation": p_value,
        "null_mean": float(np.mean(null)) if len(null) else float("nan"),
        "null_sd": float(np.std(null, ddof=1)) if len(null) > 1 else float("nan"),
        "n_permutations": int(len(null)),
        "n_folds": int(len(fold_metrics)),
        "fold_accuracy_mean": float(np.mean(fold_metrics)),
        "oof": oof,
        "null": null,
        "fold_assignments": fold_assignments,
    }


def decode_multiclass_cycle_safe(
    X: np.ndarray, labels: np.ndarray, cycles: np.ndarray, *, seed: int = DEFAULT_SEED
) -> tuple[pd.DataFrame, np.ndarray]:
    """Generate held-out A/B/R predictions using the same cycle folds."""
    labels = np.asarray(labels, dtype=int)
    cycles = np.asarray(cycles, dtype=int)
    rows: list[dict] = []
    pred_all = np.full(len(labels), -1, dtype=int)
    for fold, cycle in enumerate(np.unique(cycles)):
        test = cycles == cycle
        train = ~test
        train_idx = _balanced_training_indices(train.nonzero()[0], labels, (0, 1, 2),
                                                np.random.default_rng(seed + fold))
        if len(train_idx) == 0 or len(np.unique(labels[test])) < 1:
            continue
        model = _pipeline(seed + fold, multiclass=True)
        model.fit(X[train_idx], labels[train_idx])
        pred = model.predict(X[test])
        pred_all[test] = pred
        for row_idx, y, yhat in zip(np.flatnonzero(test), labels[test], pred):
            rows.append(
                {
                    "row_index": int(row_idx),
                    "fold": int(fold),
                    "cycle_id": int(cycle),
                    "y_true": int(y),
                    "y_pred": int(yhat),
                }
            )
    return pd.DataFrame(rows).sort_values("row_index").reset_index(drop=True), pred_all


def _spike_count_matrix(session, area: str, epochs: pd.DataFrame, window_ms: tuple[float, float]):
    units = session.get_units(area=area)
    row_indices = list(units.index)
    if len(row_indices) == 0 or len(epochs) == 0:
        return np.zeros((len(epochs), 0)), units
    onsets = pd.to_numeric(epochs["start_time"], errors="coerce").to_numpy(float)
    if not np.isfinite(onsets).all():
        raise ValueError(f"non-finite epoch onset in {area}")
    X = np.zeros((len(onsets), len(row_indices)), dtype=np.float64)
    lo_offset, hi_offset = np.asarray(window_ms, dtype=float) / 1000.0
    for col, row_index in enumerate(row_indices):
        spikes = session.get_spike_times(row_index)
        if spikes is None or len(spikes) == 0:
            continue
        spikes = np.sort(np.asarray(spikes, dtype=float))
        X[:, col] = np.searchsorted(spikes, onsets + hi_offset, side="right") - np.searchsorted(
            spikes, onsets + lo_offset, side="left"
        )
    return X, units


def _trial_table(session, slot_key: str) -> pd.DataFrame:
    cfg = OMISSION_IDENTITY_CONDITIONS[slot_key]
    pieces = []
    for label in LABELS:
        epochs = session.get_epochs(
            phase=PHASE_FOR_P1_ALIGNMENT, condition=cfg[label], correct_only=True
        )
        if len(epochs):
            part = epochs[["start_time"]].copy()
            part["label"] = label
            part["label_int"] = LABELS.index(label)
            part["condition"] = cfg[label]
            part["condition_trial_index"] = np.arange(len(part), dtype=int)
            pieces.append(part)
    if not pieces:
        return pd.DataFrame()
    table = pd.concat(pieces, ignore_index=True)
    table["start_time"] = pd.to_numeric(table["start_time"], errors="coerce")
    table = table.dropna(subset=["start_time"]).reset_index(drop=True)
    table["cycle_id"] = assign_temporal_cycles(table["start_time"].to_numpy())
    table["fold"] = table["cycle_id"]
    table["trial_index"] = np.arange(len(table), dtype=int)
    return table


def _resolve_sessions(readiness_csv: Path, nwb_dir: Path) -> tuple[list[dict], list[dict]]:
    readiness = pd.read_csv(readiness_csv)
    included, excluded = [], []
    for row in readiness.to_dict("records"):
        reason = None
        if not bool(row.get("nwb_ok", False)):
            reason = "nwb_not_ready"
        elif not bool(row.get("sidecar_ok", False)):
            reason = "sidecar_not_ready"
        candidates = [
            nwb_dir / Path(str(row.get("nwb_path", ""))).name,
            nwb_dir / f"{row['stem']}.nwb",
            nwb_dir / f"{str(row['stem']).replace('_rec', '')}.nwb",
        ]
        path = next((p for p in candidates if p.exists()), None)
        if reason is None and path is None:
            reason = "eligible_but_nwb_missing"
        if reason:
            excluded.append({"stem": row.get("stem"), "reason": reason})
        else:
            included.append(
                {
                    "stem": row["stem"],
                    "subject": row.get("subject", ""),
                    "session_id": row.get("session_id", ""),
                    "path": str(path),
                }
            )
    return included, excluded


from jnwb.paths import sha256_file as _sha256


def run(
    *,
    readiness_csv: Path,
    nwb_dir: Path,
    output_dir: Path,
    seed: int = DEFAULT_SEED,
    n_permutations: int = DEFAULT_PERMUTATIONS,
    limit: int | None = None,
) -> dict:
    started = time.time()
    included, excluded = _resolve_sessions(readiness_csv, nwb_dir)
    if limit is not None:
        included = included[:limit]
    if not included:
        raise RuntimeError("no eligible NWB sessions resolved from the readiness gate")

    cell_rows: list[dict] = []
    oof_rows: list[dict] = []
    fold_rows: list[dict] = []
    null_rows: list[dict] = []
    errors: list[dict] = []
    analysis_exclusions: list[dict] = []

    for session_number, meta in enumerate(included, start=1):
        print(f"[{session_number}/{len(included)}] {meta['stem']}", flush=True)
        try:
            session = oa.read(meta["path"])
            for slot_key in SLOTS:
                trial_table = _trial_table(session, slot_key)
                if trial_table.empty or trial_table["cycle_id"].nunique() < 2:
                    analysis_exclusions.append(
                        {
                            "session": meta["stem"],
                            "slot_key": slot_key,
                            "reason": "insufficient_trials_or_cycles",
                        }
                    )
                    continue
                for _, trial in trial_table.iterrows():
                    fold_rows.append(
                        {
                            "session": meta["stem"],
                            "subject": meta["subject"],
                            "slot_key": slot_key,
                            "trial_index": int(trial.trial_index),
                            "condition_trial_index": int(trial.condition_trial_index),
                            "condition": trial.condition,
                            "label": trial.label,
                            "label_int": int(trial.label_int),
                            "start_time_s": float(trial.start_time),
                            "cycle_id": int(trial.cycle_id),
                            "fold": int(trial.fold),
                        }
                    )
                for area in AREAS:
                    matrices = []
                    units = None
                    for label in LABELS:
                        epochs = trial_table[trial_table["label"] == label]
                        matrix, units = _spike_count_matrix(
                            session,
                            area,
                            epochs,
                            (
                                OMISSION_IDENTITY_CONDITIONS[slot_key]["slot_onset_ms"],
                                OMISSION_IDENTITY_CONDITIONS[slot_key]["slot_end_ms"],
                            ),
                        )
                        matrices.append(matrix)
                    if not matrices or any(matrix.shape[1] == 0 for matrix in matrices):
                        cell_rows.append(
                            {
                                "session": meta["stem"],
                                "subject": meta["subject"],
                                "area": area,
                                "slot_key": slot_key,
                                "status": "insufficient_units",
                            }
                        )
                        continue
                    X = np.concatenate(matrices, axis=0)
                    labels = trial_table["label_int"].to_numpy(int)
                    cycles = trial_table["cycle_id"].to_numpy(int)
                    binary_mask = labels < 2
                    binary = decode_binary_cycle_safe(
                        X[binary_mask],
                        labels[binary_mask],
                        cycles[binary_mask],
                        seed=seed,
                        n_permutations=n_permutations,
                    )
                    cell = {
                        "session": meta["stem"],
                        "subject": meta["subject"],
                        "area": area,
                        "slot_key": slot_key,
                        "status": binary.get("status", "unknown"),
                        "n_units": int(X.shape[1]),
                        "n_trials_a": int(np.sum(labels == 0)),
                        "n_trials_b": int(np.sum(labels == 1)),
                        "n_trials_r": int(np.sum(labels == 2)),
                        "n_cycles": int(len(np.unique(cycles))),
                        "n_folds": int(binary.get("n_folds", 0)),
                        "accuracy_loco_balanced": binary.get("accuracy_loco_balanced", np.nan),
                        "auc_loco": binary.get("auc_loco", np.nan),
                        "p_permutation": binary.get("p_permutation", np.nan),
                        "null_mean": binary.get("null_mean", np.nan),
                        "null_sd": binary.get("null_sd", np.nan),
                        "n_permutations": binary.get("n_permutations", 0),
                        "seed": seed,
                        "fold_scheme": "leave_one_temporal_cycle_out",
                        "null_scheme": "within_cycle_label_permutation",
                        "feature_window_ms": json.dumps(
                            [
                                OMISSION_IDENTITY_CONDITIONS[slot_key]["slot_onset_ms"],
                                OMISSION_IDENTITY_CONDITIONS[slot_key]["slot_end_ms"],
                            ]
                        ),
                        "estimator": json.dumps(ESTIMATOR, sort_keys=True),
                        "unit_identity": "session.get_units(area).index row position",
                    }
                    cell_rows.append(cell)
                    if binary.get("status") != "success":
                        continue
                    oof = binary["oof"]
                    for row in oof.to_dict("records"):
                        oof_rows.append(
                            {
                                "session": meta["stem"],
                                "subject": meta["subject"],
                                "area": area,
                                "slot_key": slot_key,
                                "analysis": "binary",
                                **row,
                            }
                        )
                    null = np.asarray(binary["null"], dtype=float)
                    for perm_idx, accuracy in enumerate(null):
                        null_rows.append(
                            {
                                "session": meta["stem"],
                                "subject": meta["subject"],
                                "area": area,
                                "slot_key": slot_key,
                                "permutation": int(perm_idx),
                                "accuracy_loco_balanced": float(accuracy),
                                "seed": int(seed + 100_000 + perm_idx),
                            }
                        )
                    abr_mask = np.ones(len(labels), dtype=bool)
                    oof_multi, _ = decode_multiclass_cycle_safe(
                        X[abr_mask], labels[abr_mask], cycles[abr_mask], seed=seed
                    )
                    for row in oof_multi.to_dict("records"):
                        oof_rows.append(
                            {
                                "session": meta["stem"],
                                "subject": meta["subject"],
                                "area": area,
                                "slot_key": slot_key,
                                "analysis": "multiclass",
                                "decision_score": np.nan,
                                **row,
                            }
                        )
        except Exception as exc:  # retain an explicit failure receipt, never a silent fallback
            errors.append({"session": meta["stem"], "reason": type(exc).__name__, "detail": str(exc)})
            print(f"  ERROR {type(exc).__name__}: {exc}", flush=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "cells": output_dir / "omission_identity_leakage_safe_cells.csv",
        "oof": output_dir / "omission_identity_leakage_safe_oof.csv",
        "folds": output_dir / "omission_identity_leakage_safe_folds.csv",
        "null": output_dir / "omission_identity_leakage_safe_null.csv",
    }
    pd.DataFrame(cell_rows).to_csv(outputs["cells"], index=False)
    pd.DataFrame(oof_rows).to_csv(outputs["oof"], index=False)
    pd.DataFrame(fold_rows).to_csv(outputs["folds"], index=False)
    pd.DataFrame(null_rows).to_csv(outputs["null"], index=False)

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
        "analysis_exclusions": analysis_exclusions,
        "runtime_seconds": time.time() - started,
        "seed": seed,
        "n_permutations_requested": n_permutations,
        "estimator": ESTIMATOR,
        "fold_scheme": "leave_one_temporal_cycle_out",
        "cycle_definition": "combined A/B/R P1-aligned start times; gap > 10 x median positive gap",
        "null_scheme": "within-cycle label permutation; fixed folds and per-cycle class counts",
        "feature": "spike counts by unit row position, omission-slot window relative to P1",
        "signal": "SPK/SUA only",
        "lfp_null": "not run; Figure 4 makes no LFP decoding claim",
        "errors": errors,
        "output_hashes": {key: _sha256(path) for key, path in outputs.items()},
        "output_paths": {key: str(path) for key, path in outputs.items()},
        "receipt_hash_scope": "receipt hash intentionally excludes this JSON file",
    }
    receipt_path = output_dir / "omission_identity_leakage_safe_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(
        f"Completed {len(included)} eligible sessions, {len(cell_rows)} cells, "
        f"{len(null_rows)} null draws in {receipt['runtime_seconds']:.1f}s.",
        flush=True,
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readiness", type=Path,
                        default=REPO_ROOT / "artifacts" / "data" / "session_readiness.csv")
    parser.add_argument("--nwb-dir", type=Path, default=paths.nwb_dir())
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "outputs" / "classification")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--permutations", type=int, default=DEFAULT_PERMUTATIONS)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    if not args.nwb_dir.exists():
        raise FileNotFoundError(
            f"NWB directory not found: {args.nwb_dir}; pass --nwb-dir or set OMISSION_NWB_DIR"
        )
    run(
        readiness_csv=args.readiness,
        nwb_dir=args.nwb_dir,
        output_dir=args.output_dir,
        seed=args.seed,
        n_permutations=args.permutations,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
