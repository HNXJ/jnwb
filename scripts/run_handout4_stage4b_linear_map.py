#!/usr/bin/env python3
"""Run the authorized Stage 4B full-corpus linear WHAT x WHEN map.

The runner consumes the Stage 4A task geometry and the live raw NWB corpus.  It never reads TFR
arrays, never uses the uncatalogued 22nd NWB, and writes explicit success/failure rows rather than
relaxing a task's eligibility.  All preprocessing is fit inside the outer training partition.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import h5py
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix
from sklearn.preprocessing import StandardScaler

REPO_ROOT = Path(__file__).resolve().parents[1]
STAGE4A_DIR = (
    REPO_ROOT
    / "context"
    / "figures"
    / "fig04_omission_identity_decoding"
    / "handout_4_stage4a"
)
DEFAULT_OUTPUT = (
    Path(os.environ.get("OMISSION_ANALYSIS_DIR", "D:/analysis"))
    / "handout4_stage4b_linear_map"
)
CATALOG_PATH = REPO_ROOT / "artifacts" / "data" / "nwb_catalog.json"
READINESS_PATH = REPO_ROOT / "artifacts" / "data" / "session_readiness.csv"
COARSE_WINDOWS = {
    "late_pre_omission": (-297.0, 0.0),
    "early_omission": (0.0, 180.0),
    "late_omission": (351.0, 531.0),
    "post_omission_delay": (531.0, 828.0),
}
MAIN_WINDOW = {"full_omission": (0.0, 531.0)}
ALL_WINDOWS = {**MAIN_WINDOW, **COARSE_WINDOWS}
BIN_SIZE_MS = 9.0
C_GRID = (0.01, 0.1, 1.0, 10.0)
MAX_PCA_FEATURES = 5000
PCA_COMPONENTS = 50
DEFAULT_PERMUTATIONS = 100
SEED = 42
SAMPLE_STATUS = "AVAILABLE_BUT_NOT_IN_FROZEN_CORPUS"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))
import audit_handout4_stage4a as stage4a  # noqa: E402
import jnwb as oa  # noqa: E402
from jnwb.analog import load_lfp_epochs, load_muae_epochs  # noqa: E402
from jnwb.omission_identity import detect_trial_cycles  # noqa: E402
from jnwb.permutation import permute_labels  # noqa: E402
from jnwb.paths import nwb_dir  # noqa: E402
from jnwb.sequence_layout import EPOCH_ONSETS_MS  # noqa: E402


@dataclass(frozen=True)
class Fold:
    fold: int
    held_out_group: int
    train_idx: np.ndarray
    test_idx: np.ndarray
    inner_groups: tuple[int, ...]


from jnwb.paths import sha256_file as _sha256


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _target_values(frame: pd.DataFrame, target: str) -> pd.Series:
    return stage4a._target_values(frame, target)


def _read_presented_events(path: Path) -> pd.DataFrame:
    with h5py.File(path, "r") as handle:
        group = handle["intervals/omission_glo_passive"]
        numeric = {
            name: np.asarray(
                [
                    stage4a._float(value)
                    for value in group[name][:]
                ],
                dtype=float,
            )
            for name in (
                "start_time",
                "trial_num",
                "stimulus_number",
                "task_condition_number",
            )
        }
        correct = (
            np.asarray([stage4a._float(value) for value in group["correct"][:]], dtype=float)
            if "correct" in group
            else np.ones(len(numeric["start_time"]))
        )
    frame = pd.DataFrame(numeric)
    frame["correct"] = correct
    frame = frame[
        np.isclose(frame["stimulus_number"], 2.0)
        & frame["correct"].eq(1.0)
        & np.isfinite(frame["start_time"])
    ].copy()
    inverse = {
        int(code): condition
        for condition, codes in stage4a.condition_map_for_stem(path.stem).items()
        for code in codes
    }
    frame["condition"] = frame["task_condition_number"].round().astype(int).map(inverse)
    frame = frame[frame["condition"].isin(["AAAB", "BBBA"])].copy()
    onto = frame["condition"].map(stage4a.CONDITION_ONTOLOGY)
    frame["sequence_family"] = onto.map(lambda value: value["sequence_family"])
    frame["presented_identity"] = onto.map(lambda value: value["presented_identity"])
    frame["slot_key"] = "p1"
    frame["trial_num"] = frame["trial_num"].round().astype(int)
    frame = frame.drop_duplicates(["trial_num", "condition"]).sort_values(
        ["start_time", "trial_num", "condition"]
    ).reset_index(drop=True)
    frame["cycle"] = detect_trial_cycles(frame[["start_time"]].reset_index(drop=True))
    frame["session"] = path.stem
    frame["subject"] = path.stem.split("_", 1)[0].removeprefix("sub-")
    frame["trial_key"] = frame.apply(
        lambda row: f"{path.stem}|trial={int(row['trial_num'])}|condition={row['condition']}",
        axis=1,
    )
    frame["anchor_onset_s"] = frame["start_time"].astype(float)
    return frame


def _events(path: Path) -> pd.DataFrame:
    with h5py.File(path, "r") as handle:
        frame, reasons = stage4a._events(handle, path.stem)
    if reasons:
        raise ValueError(";".join(reasons))
    frame = frame.copy()
    frame["trial_id"] = frame["trial_key"]
    frame["anchor_onset_s"] = frame["local_omission_onset_s"]
    return frame


def _spike_tensor(
    session,
    frame: pd.DataFrame,
    area: str,
    window_ms: tuple[float, float],
) -> tuple[np.ndarray, dict[str, Any]]:
    lo_ms, hi_ms = window_ms
    duration = hi_ms - lo_ms
    n_bins_float = duration / BIN_SIZE_MS
    n_bins = int(round(n_bins_float))
    if not np.isclose(n_bins_float, n_bins):
        raise ValueError(f"SUA window is not divisible by {BIN_SIZE_MS} ms: {window_ms}")
    units = session.get_units(area=area)
    if units.empty:
        raise ValueError("SIGNAL_AREA_UNAVAILABLE")
    rows = frame.reset_index(drop=True)
    onsets = rows["anchor_onset_s"].to_numpy(float)
    data = np.zeros((len(rows), len(units), n_bins), dtype=np.float32)
    for unit_col, row_index in enumerate(units.index):
        spikes = np.sort(np.asarray(session.get_spike_times(row_index), dtype=float))
        if len(spikes) == 0:
            continue
        for trial_index, onset in enumerate(onsets):
            edges = onset + np.arange(n_bins + 1) * BIN_SIZE_MS / 1000.0
            edges += lo_ms / 1000.0
            data[trial_index, unit_col], _ = np.histogram(spikes, bins=edges)
    data /= BIN_SIZE_MS / 1000.0
    return data, {
        "units": "Hz",
        "n_units": int(len(units)),
        "unit_row_indices": [int(value) for value in units.index],
        "source": "NWB units.spike_times; DataFrame row indices",
        "time_vector_ms": (lo_ms + np.arange(n_bins) * BIN_SIZE_MS).tolist(),
    }


def _analog_tensor(
    path: Path,
    signal: str,
    area: str,
    window_ms: tuple[float, float],
) -> tuple[np.ndarray, pd.DataFrame, dict[str, Any]]:
    loader: Callable[..., Any] = load_muae_epochs if signal == "MUAe" else load_lfp_epochs
    batch = loader(
        path,
        alignment="omission",
        areas=[area],
        window_ms=window_ms,
        missing_data="raise",
    )
    return batch.data, batch.trial_metadata, {
        "units": sorted(batch.signal_metadata["units"].astype(str).unique().tolist()),
        "n_channels": int(batch.data.shape[1]),
        "sampling_rate_hz": float(batch.signal_metadata["sampling_rate_hz"].iloc[0]),
        "source_object_paths": sorted(
            batch.signal_metadata["source_object_path"].astype(str).unique().tolist()
        ),
        "time_vector_ms": batch.time_ms.tolist(),
        "preprocessing": batch.manifest["preprocessing"],
    }


def _presented_analog_tensor(
    path: Path,
    signal: str,
    area: str,
    window_ms: tuple[float, float],
) -> tuple[np.ndarray, pd.DataFrame, dict[str, Any]]:
    loader: Callable[..., Any] = load_muae_epochs if signal == "MUAe" else load_lfp_epochs
    batch = loader(
        path,
        condition=["AAAB", "BBBA"],
        alignment="p1",
        areas=[area],
        window_ms=window_ms,
        missing_data="raise",
    )
    return batch.data, batch.trial_metadata, {
        "units": sorted(batch.signal_metadata["units"].astype(str).unique().tolist()),
        "n_channels": int(batch.data.shape[1]),
        "sampling_rate_hz": float(batch.signal_metadata["sampling_rate_hz"].iloc[0]),
        "source_object_paths": sorted(
            batch.signal_metadata["source_object_path"].astype(str).unique().tolist()
        ),
        "time_vector_ms": batch.time_ms.tolist(),
        "preprocessing": batch.manifest["preprocessing"],
    }


def _feature_matrix(
    tensor: np.ndarray,
    representation: str,
) -> np.ndarray:
    if tensor.ndim != 3 or not np.isfinite(tensor).all():
        raise ValueError("feature tensor must be finite trial x space x time")
    if representation.endswith("0"):
        return tensor.mean(axis=2, dtype=np.float64)
    return tensor.reshape(tensor.shape[0], -1).astype(np.float64, copy=False)


def _task_frame(
    events: pd.DataFrame,
    spec: dict[str, Any],
    geometry_row: pd.Series,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    if not bool(geometry_row["identifiable"]):
        raise ValueError(str(geometry_row.get("exclusion_reason") or "INELIGIBLE_DESIGN"))
    selected = (
        events["omission_position"].isin(spec["train_slots"])
        & events["sequence_family"].isin(spec["train_families"])
    )
    tested = (
        events["omission_position"].isin(spec["test_slots"])
        & events["sequence_family"].isin(spec["test_families"])
    )
    if spec["geometry"] == "cross_position_reversal" or spec["geometry"] == "cross_family_generalization":
        feature_mask = selected | tested
    else:
        feature_mask = selected
        tested = selected.copy()
    original_index = events.index[feature_mask]
    frame = events.loc[original_index].copy().reset_index(drop=True)
    train_mask = selected.loc[original_index].to_numpy(bool)
    test_mask = tested.loc[original_index].to_numpy(bool)
    values = _target_values(frame, spec["target"]).astype(str)
    if values.isna().any():
        raise ValueError("TARGET_JOIN_FAILURE")
    class_names = sorted(values.unique().tolist())
    class_map = {name: index for index, name in enumerate(class_names)}
    labels = values.map(class_map).to_numpy(int)
    return frame, train_mask, test_mask, labels, class_names


def _folds(
    labels: np.ndarray,
    groups: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
) -> tuple[list[Fold], list[dict[str, Any]], int]:
    candidate = sorted(
        set(groups[train_mask].astype(int).tolist())
        & set(groups[test_mask].astype(int).tolist())
        - {-1}
    )
    rows: list[dict[str, Any]] = []
    folds: list[Fold] = []
    valid_inner = 0
    for fold, held_out in enumerate(candidate):
        train_idx = np.flatnonzero(train_mask & (groups != held_out))
        test_idx = np.flatnonzero(test_mask & (groups == held_out))
        reasons = []
        if len(set(labels[train_idx])) < len(set(labels)):
            reasons.append("TRAIN_MISSING_CLASS")
        if len(set(labels[test_idx])) < len(set(labels)):
            reasons.append("TEST_MISSING_CLASS")
        train_groups = sorted(set(groups[train_idx].astype(int).tolist()) - {-1})
        if len(train_groups) < 2:
            reasons.append("INSUFFICIENT_TRAIN_GROUPS")
        valid = not reasons
        if valid:
            folds.append(Fold(fold, int(held_out), train_idx, test_idx, tuple(train_groups)))
            for inner_group in train_groups:
                inner_train = train_idx[groups[train_idx] != inner_group]
                inner_val = train_idx[groups[train_idx] == inner_group]
                if len(set(labels[inner_train])) == len(set(labels)) and len(
                    set(labels[inner_val])
                ) == len(set(labels)):
                    valid_inner += 1
        rows.append(
            {
                "outer_fold": fold,
                "held_out_group": int(held_out),
                "n_train_trials": int(len(train_idx)),
                "n_test_trials": int(len(test_idx)),
                "train_class_counts": _json(
                    pd.Series(labels[train_idx]).value_counts().sort_index().to_dict()
                ),
                "test_class_counts": _json(
                    pd.Series(labels[test_idx]).value_counts().sort_index().to_dict()
                ),
                "status": "ELIGIBLE_OUTER" if valid else "INELIGIBLE_DESIGN",
                "reason": ";".join(reasons),
            }
        )
    return folds, rows, valid_inner


def _fit_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_eval: np.ndarray,
    C: float,
    *,
    prep: dict[str, Any] | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    if prep is None:
        train_scaled, eval_scaled, prep = _prepare_features(X_train, X_eval)
    else:
        train_scaled = prep["X_train"]
        eval_scaled = prep["X_eval"]
    prediction, scalar = _fit_prepared(train_scaled, y_train, eval_scaled, C)
    prep["last_model"] = True
    return prediction, scalar, prep


def _prepare_features(
    X_train: np.ndarray, X_eval: np.ndarray
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    scaler = StandardScaler()
    train_scaled = scaler.fit_transform(X_train)
    eval_scaled = scaler.transform(X_eval)
    pca = None
    if train_scaled.shape[1] > MAX_PCA_FEATURES:
        components = min(PCA_COMPONENTS, train_scaled.shape[0] - 1, train_scaled.shape[1])
        if components >= 2:
            pca = PCA(n_components=components, random_state=SEED)
            train_scaled = pca.fit_transform(train_scaled)
            eval_scaled = pca.transform(eval_scaled)
    return train_scaled, eval_scaled, {"scaler": scaler, "pca": pca}


def _fit_prepared(
    train_scaled: np.ndarray,
    y_train: np.ndarray,
    eval_scaled: np.ndarray,
    C: float,
) -> tuple[np.ndarray, np.ndarray]:
    if len(np.unique(y_train)) < 2:
        raise ValueError("TRAIN_MISSING_CLASS")
    model = RidgeClassifier(alpha=1.0 / float(C), class_weight="balanced")
    model.fit(train_scaled, y_train)
    prediction = model.predict(eval_scaled).astype(int)
    decision = model.decision_function(eval_scaled)
    if np.ndim(decision) == 1:
        scalar = np.asarray(decision, dtype=float)
    else:
        scalar = np.max(np.asarray(decision, dtype=float), axis=1)
    return prediction, scalar


def _select_c(
    X: np.ndarray,
    labels: np.ndarray,
    groups: np.ndarray,
    fold: Fold,
) -> tuple[float, float, int]:
    scores = []
    prepared_inner = []
    for validation_group in fold.inner_groups:
        inner_train = fold.train_idx[groups[fold.train_idx] != validation_group]
        validation = fold.train_idx[groups[fold.train_idx] == validation_group]
        if len(set(labels[inner_train])) < len(set(labels)) or len(
            set(labels[validation])
        ) < len(set(labels)):
            continue
        xtr, xval, _ = _prepare_features(X[inner_train], X[validation])
        prepared_inner.append((inner_train, validation, xtr, xval))
    for C in C_GRID:
        inner_scores = []
        for inner_train, validation, xtr, xval in prepared_inner:
            pred, _ = _fit_prepared(xtr, labels[inner_train], xval, C)
            inner_scores.append(balanced_accuracy_score(labels[validation], pred))
        if inner_scores:
            scores.append((float(np.mean(inner_scores)), float(C), len(inner_scores)))
    if not scores:
        raise ValueError("INSUFFICIENT_INNER_VALIDATION")
    scores.sort(key=lambda item: (-item[0], item[1]))
    return scores[0]


def _observed_fit(
    X: np.ndarray,
    labels: np.ndarray,
    alternate: np.ndarray | None,
    groups: np.ndarray,
    folds: list[Fold],
    trial_ids: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    oof = []
    fold_rows = []
    prepared = []
    for fold in folds:
        # _select_c returns scores[0] = (mean_inner_balanced_accuracy, C, n_inner) -- confirmed
        # by direct call (artifacts/.lab/handout-4-stage4b-batched-null-validation-20260811.json).
        # This unpacking was previously reversed (selected_c, inner_score = score, C), so every
        # fold's ridge regularization used a balanced-accuracy score as if it were 1/alpha, and
        # every reported "inner_balanced_accuracy" was actually a C_GRID value. Fixed 2026-08-11.
        inner_score, selected_c, n_inner = _select_c(X, labels, groups, fold)
        xtr, xte, prep = _prepare_features(X[fold.train_idx], X[fold.test_idx])
        pred, scalar = _fit_prepared(xtr, labels[fold.train_idx], xte, selected_c)
        prepared.append(
            {
                "fold": fold,
                "X_train": xtr,
                "X_test": xte,
                "selected_C": selected_c,
                "n_pca_components": int(xtr.shape[1]) if prep["pca"] is not None else 0,
            }
        )
        fold_rows.append(
            {
                "outer_fold": fold.fold,
                "held_out_group": fold.held_out_group,
                "n_train": len(fold.train_idx),
                "n_test": len(fold.test_idx),
                "selected_C": selected_c,
                "inner_balanced_accuracy": inner_score,
                "n_inner_partitions": n_inner,
                "n_pca_components": int(xtr.shape[1]) if prep["pca"] is not None else 0,
                "outer_balanced_accuracy": balanced_accuracy_score(
                    labels[fold.test_idx], pred
                ),
            }
        )
        for index, prediction, score in zip(fold.test_idx, pred, scalar):
            row = {
                "row_index": int(index),
                "trial_id": trial_ids[index],
                "outer_fold": fold.fold,
                "held_out_group": fold.held_out_group,
                "label": int(labels[index]),
                "prediction": int(prediction),
                "decision_score": float(score),
            }
            if alternate is not None:
                row["alternate_label"] = int(alternate[index])
            oof.append(row)
    return (
        pd.DataFrame(oof).sort_values("row_index").reset_index(drop=True),
        pd.DataFrame(fold_rows),
        prepared,
    )


def _null_distribution(
    labels: np.ndarray,
    alternate: np.ndarray | None,
    slots: np.ndarray | None,
    groups: np.ndarray,
    prepared: list[dict[str, Any]],
    n_classes: int,
    n_permutations: int,
    seed: int,
    reversal: bool,
) -> tuple[np.ndarray, int]:
    invalid = 0
    permuted_labels = []
    permuted_alternate = []
    for permutation in range(n_permutations):
        if reversal:
            if slots is None:
                raise ValueError("NULL_INVALID: reversal requires slot labels")
            shuffled = permute_labels(
                labels,
                groups=np.asarray([f"{g}:{s}" for g, s in zip(groups, slots)]),
                scheme="within_group",
                rng=np.random.default_rng(seed + permutation),
            )
            shuffled_alt = shuffled.copy()
            shuffled_alt[slots == "p4"] = 1 - shuffled_alt[slots == "p4"]
        else:
            shuffled = permute_labels(
                labels,
                groups=groups,
                scheme="within_group",
                rng=np.random.default_rng(seed + permutation),
            )
            shuffled_alt = None
        permuted_labels.append(shuffled)
        if reversal:
            permuted_alternate.append(shuffled_alt)
    label_matrix = np.asarray(permuted_labels, dtype=int).T
    alternate_matrix = (
        np.asarray(permuted_alternate, dtype=int).T if reversal else None
    )
    fold_predictions = []
    fold_truth = []
    fold_alternate = []
    for item in prepared:
        fold = item["fold"]
        train_labels = label_matrix[fold.train_idx]
        if any(len(np.unique(train_labels[:, i])) < n_classes for i in range(n_permutations)):
            invalid += 1
            continue
        # Reverted 2026-08-11 to the reference implementation (one sklearn RidgeClassifier fit
        # per permutation, via the SAME _fit_prepared call the observed fit uses) after the
        # batched closed-form solve above was found NOT to numerically reproduce sklearn's
        # RidgeClassifier(alpha=1/C, class_weight='balanced') -- see
        # artifacts/.lab/handout-4-stage4b-batched-null-validation-20260811.json
        # (scripts/validate_stage4b_batched_null.py: max balanced-accuracy diff 0.068,
        # tolerance 1e-9). Per the continuation handout's own instruction: "If equivalence is
        # not demonstrated, revert to the slower reference null ... never silently mix the
        # two." Slower, but reuses code already trusted by the observed fit rather than a
        # closed-form reimplementation whose class-weighting/intercept parameterization could
        # not be independently confirmed to match sklearn's internal behavior.
        predictions_per_permutation = []
        for permutation in range(n_permutations):
            pred, _ = _fit_prepared(
                item["X_train"],
                train_labels[:, permutation],
                item["X_test"],
                item["selected_C"],
            )
            predictions_per_permutation.append(pred)
        predictions = np.stack(predictions_per_permutation, axis=1)
        fold_predictions.append(predictions)
        fold_truth.append(label_matrix[fold.test_idx])
        if reversal:
            fold_alternate.append(alternate_matrix[fold.test_idx])
    if not fold_predictions:
        raise ValueError("NULL_INVALID")
    rows = []
    for permutation in range(n_permutations):
        prediction = np.concatenate(
            [values[:, permutation] for values in fold_predictions]
        )
        truth = np.concatenate([values[:, permutation] for values in fold_truth])
        value = balanced_accuracy_score(truth, prediction)
        if reversal:
            alternate_truth = np.concatenate(
                [values[:, permutation] for values in fold_alternate]
            )
            value -= balanced_accuracy_score(alternate_truth, prediction)
        rows.append(float(value))
    if not rows:
        raise ValueError("NULL_INVALID")
    return np.asarray(rows, dtype=float), invalid


def _cell(
    *,
    task: str,
    role: str,
    signal: str,
    representation: str,
    window: str,
    subject: str,
    session_name: str,
    area: str,
    frame: pd.DataFrame,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
    labels: np.ndarray,
    class_names: list[str],
    X: np.ndarray,
    feature_meta: dict[str, Any],
    n_permutations: int,
    seed: int,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    groups = frame["group_for_task"].to_numpy(int)
    folds, fold_rows, valid_inner = _folds(labels, groups, train_mask, test_mask)
    if len(folds) < 2 or valid_inner < 2:
        raise ValueError("INSUFFICIENT_GROUPS")
    alternate = None
    reversal = task.startswith("W1_reversal")
    if reversal:
        alternate = _target_values(frame, "preceding_identity").map(
            {name: index for index, name in enumerate(class_names)}
        ).to_numpy(int)
    oof, fitted_folds, prepared = _observed_fit(
        X, labels, alternate, groups, folds, frame["trial_id"].astype(str).tolist()
    )
    prediction = oof["prediction"].to_numpy(int)
    observed_ba = float(balanced_accuracy_score(oof["label"], prediction))
    observed_accuracy = float(accuracy_score(oof["label"], prediction))
    confusion = confusion_matrix(
        oof["label"], prediction, labels=list(range(len(class_names)))
    ).tolist()
    alternate_ba = float("nan")
    gap = float("nan")
    if reversal:
        alternate_ba = float(
            balanced_accuracy_score(oof["alternate_label"], prediction)
        )
        gap = observed_ba - alternate_ba
    null, invalid_null = _null_distribution(
        labels,
        alternate,
        frame["omission_position"].astype(str).to_numpy()
        if "omission_position" in frame
        else None,
        groups,
        prepared,
        len(class_names),
        n_permutations,
        seed,
        reversal,
    )
    null_expectation = float(np.mean(null))
    observed_stat = gap if reversal else observed_ba
    null_effect = float(observed_stat - null_expectation)
    null_reference = 0.0 if reversal else 1.0 / len(class_names)
    p = float(
        (1 + np.sum(np.abs(null - null_reference) >= abs(observed_stat - null_reference)))
        / (len(null) + 1)
    )
    result = {
        "status": "SUCCESS",
        "task": task,
        "role": role,
        "signal": signal,
        "representation": representation,
        "window": window,
        "subject": subject,
        "session": session_name,
        "area": area,
        "eligible_N": int(len(frame)),
        "outer_fold_N": int(len(folds)),
        "class_names": _json(class_names),
        "class_counts": _json(
            pd.Series(labels).value_counts().sort_index().to_dict()
        ),
        "cycle_N": int(len(np.unique(groups))),
        "fold_N": int(len(folds)),
        "observed_accuracy": observed_accuracy,
        "observed_balanced_accuracy": observed_ba,
        "A_expected": observed_ba if reversal else np.nan,
        "A_previous": alternate_ba,
        "G": gap,
        "chance_or_null_expectation": null_expectation,
        "null_effect": null_effect,
        "permutation_p": p,
        "n_permutations_requested": int(n_permutations),
        "n_permutations_valid": int(len(null)),
        "n_null_invalid": int(invalid_null),
        "null_seed": int(seed),
        "null_scheme": "within_cycle_and_slot_reversal" if reversal else "within_cycle",
        "confusion_matrix": _json(confusion),
        "feature_shape": _json(list(X.shape)),
        "feature_units": _json(feature_meta.get("units")),
        "pca_feature_limit": MAX_PCA_FEATURES,
        "pca_components_limit": PCA_COMPONENTS,
        "preprocessing": _json(feature_meta),
        "continuous_signed_score_defined": bool(reversal),
    }
    fold_df = pd.DataFrame(fold_rows).merge(
        fitted_folds,
        on=["outer_fold", "held_out_group"],
        how="left",
        suffixes=("", "_fit"),
    )
    oof["task"] = task
    oof["signal"] = signal
    oof["representation"] = representation
    oof["window"] = window
    oof["subject"] = subject
    oof["session"] = session_name
    oof["area"] = area
    null_df = pd.DataFrame(
        {
            "task": task,
            "signal": signal,
            "representation": representation,
            "window": window,
            "subject": subject,
            "session": session_name,
            "area": area,
            "permutation": np.arange(len(null)),
            "statistic": null,
            "seed": seed + np.arange(len(null)),
        }
    )
    manifest = {
        "task": task,
        "signal": signal,
        "representation": representation,
        "window": window,
        "subject": subject,
        "session": session_name,
        "area": area,
        "trial_ids": frame["trial_id"].astype(str).tolist(),
        "classes": labels.tolist(),
        "class_names": class_names,
        "groups": groups.tolist(),
        "train_mask": train_mask.tolist(),
        "test_mask": test_mask.tolist(),
        "outer_folds": fold_rows,
        "feature_shape": list(X.shape),
    }
    return result, oof, fold_df, null_df, manifest


def _positive_task(
    frame: pd.DataFrame,
    geometry_group: np.ndarray,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    values = frame["presented_identity"].astype(str)
    names = sorted(values.unique().tolist())
    labels = values.map({name: i for i, name in enumerate(names)}).to_numpy(int)
    groups = frame["cycle"].to_numpy(int)
    candidate = sorted(set(groups) - {-1})
    if len(candidate) < 3:
        raise ValueError("INSUFFICIENT_GROUPS")
    mask = np.ones(len(frame), dtype=bool)
    return frame.copy(), mask, mask, labels, names


def _feature_rows(
    tensor: np.ndarray,
    metadata: pd.DataFrame,
    source_frame: pd.DataFrame,
    *,
    feature_meta: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    if "trial_id" not in metadata:
        raise ValueError("ACCESS_FAILURE: analog metadata lacks trial_id")
    lookup = {str(value): index for index, value in enumerate(metadata["trial_id"])}
    wanted = source_frame["trial_id"].astype(str).tolist()
    missing = [value for value in wanted if value not in lookup]
    if missing:
        raise ValueError(f"STAGE4A_TRIAL_GEOMETRY_MISMATCH:{len(missing)}")
    ordered = tensor[[lookup[value] for value in wanted]]
    return ordered, feature_meta


def _write_frame(rows: list[dict[str, Any]], path: Path) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def run(
    *,
    output_dir: Path = DEFAULT_OUTPUT,
    n_permutations: int = DEFAULT_PERMUTATIONS,
    seed: int = SEED,
    max_sessions: int | None = None,
    max_areas: int | None = None,
    task_filter: set[str] | None = None,
    window_filter: set[str] | None = None,
    signal_filter: set[str] | None = None,
    session_filter: set[str] | None = None,
) -> dict[str, Any]:
    if n_permutations < 1:
        raise ValueError("n_permutations must be positive")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    readiness = pd.read_csv(READINESS_PATH)
    geometry = pd.read_csv(STAGE4A_DIR / "task_session_geometry.csv")
    signal_area = pd.read_csv(STAGE4A_DIR / "signal_area_inventory.csv")
    specs = {spec["task"]: spec for spec in stage4a.task_specs()}
    actual_nwb = {path.name: path for path in sorted(nwb_dir().glob("*.nwb"))}
    catalog_sessions = [
        row for row in catalog["sessions"] if row["filename"] in actual_nwb
    ]
    if session_filter is not None:
        catalog_sessions = [
            row
            for row in catalog_sessions
            if Path(row["filename"]).stem in session_filter
        ]
    uncatalogued = sorted(set(actual_nwb) - {row["filename"] for row in catalog["sessions"]})
    sessions = catalog_sessions[:max_sessions] if max_sessions else catalog_sessions
    session_by_stem = {Path(row["filename"]).stem: actual_nwb[row["filename"]] for row in sessions}
    session_objects: dict[str, Any] = {}
    event_frames: dict[str, pd.DataFrame] = {}
    presented_frames: dict[str, pd.DataFrame] = {}
    results: list[dict[str, Any]] = []
    predictions: list[pd.DataFrame] = []
    folds: list[pd.DataFrame] = []
    nulls: list[pd.DataFrame] = []
    manifests: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    feature_manifests: list[dict[str, Any]] = []
    task_geometry = geometry.set_index(["session", "task"])
    signal_area = signal_area[signal_area["status"].eq("metadata_available")].copy()
    task_names = list(specs)
    if task_filter is not None:
        task_names = [task for task in task_names if task in task_filter]
    selected_windows = {
        name: value
        for name, value in ALL_WINDOWS.items()
        if window_filter is None or name in window_filter
    }
    selected_signals = {
        signal: label
        for signal, label in (("SUA_SPK", "SUA"), ("MUAe", "MUAe"), ("LFP", "LFP"))
        if signal_filter is None or signal in signal_filter
    }
    positive_task = "presented_AB_control"

    for session_number, (session_name, path) in enumerate(session_by_stem.items()):
        subject = session_name.split("_", 1)[0].removeprefix("sub-")
        try:
            session_objects[session_name] = oa.read(path)
            event_frames[session_name] = _events(path)
            presented_frames[session_name] = _read_presented_events(path)
        except Exception as exc:
            failures.append(
                {
                    "status": "ACCESS_FAILURE",
                    "session": session_name,
                    "subject": subject,
                    "reason": f"{type(exc).__name__}:{exc}",
                }
            )
            continue
        session_signals = signal_area[signal_area["session"].eq(session_name)]
        area_by_signal = {
            signal: sorted(session_signals.loc[session_signals["signal"].eq(signal), "area"].dropna().unique())
            for signal in ("SUA_SPK", "MUAe", "LFP")
        }
        areas = sorted(set().union(*area_by_signal.values()))
        if max_areas:
            areas = areas[:max_areas]
        for area in areas:
            for signal, signal_label in selected_signals.items():
                if area not in area_by_signal[signal]:
                    continue
                for window_name, window_ms in selected_windows.items():
                    print(
                        f"Stage4B extracting session={session_name} area={area} "
                        f"signal={signal} window={window_name}",
                        flush=True,
                    )
                    try:
                        if signal == "SUA_SPK":
                            base = event_frames[session_name]
                            tensor, feature_meta = _spike_tensor(
                                session_objects[session_name],
                                base.assign(anchor_onset_s=base["local_omission_onset_s"]),
                                area,
                                window_ms,
                            )
                            metadata = base[["trial_key"]].rename(columns={"trial_key": "trial_id"})
                        else:
                            tensor, metadata, feature_meta = _analog_tensor(
                                path, signal, area, window_ms
                            )
                            base = event_frames[session_name]
                        feature_map = {
                            str(trial_id): tensor[index]
                            for index, trial_id in enumerate(metadata["trial_id"])
                        }
                        stage_ids = set(base["trial_id"].astype(str))
                        if set(feature_map) != stage_ids:
                            raise ValueError(
                                f"STAGE4A_TRIAL_GEOMETRY_MISMATCH:{len(stage_ids)}:{len(feature_map)}"
                            )
                        presented_tensor = None
                        presented_meta = None
                        presented_feature_meta = None
                        if window_name in MAIN_WINDOW or True:
                            if signal == "SUA_SPK":
                                presented = presented_frames[session_name]
                                presented_tensor, presented_feature_meta = _spike_tensor(
                                    session_objects[session_name], presented, area, window_ms
                                )
                                presented_meta = presented[["trial_key"]].rename(
                                    columns={"trial_key": "trial_id"}
                                )
                            else:
                                presented_tensor, presented_meta, presented_feature_meta = (
                                    _presented_analog_tensor(path, signal, area, window_ms)
                                )
                    except Exception as exc:
                        reason = f"{type(exc).__name__}:{exc}"
                        tasks_for_window = (
                            task_names + [positive_task]
                            if window_name == "full_omission"
                            else task_names
                        )
                        for task in tasks_for_window:
                            reps = ["R0", "R1"] if signal == "SUA_SPK" else [
                                f"{signal_label}0",
                                f"{signal_label}1",
                            ]
                            for rep in reps:
                                failures.append(
                                    {
                                        "status": (
                                            "ALIGNMENT_FAILURE"
                                            if "STAGE4A" in str(exc)
                                            else "ACCESS_FAILURE"
                                        ),
                                        "task": task,
                                        "signal": signal_label,
                                        "representation": rep,
                                        "window": window_name,
                                        "subject": subject,
                                        "session": session_name,
                                        "area": area,
                                        "reason": reason,
                                    }
                                )
                        continue

                    tasks_for_window = (
                        task_names + [positive_task]
                        if window_name == "full_omission"
                        else task_names
                    )
                    for task in tasks_for_window:
                        if task == positive_task:
                            frame = presented_frames[session_name].copy()
                            try:
                                _, train_mask, test_mask, labels, class_names = _positive_task(
                                    frame, frame["cycle"].to_numpy(int)
                                )
                                frame["group_for_task"] = frame["cycle"].astype(int)
                                frame["trial_id"] = frame["trial_key"]
                                current_tensor = presented_tensor
                                current_meta = presented_feature_meta
                                if signal != "SUA_SPK":
                                    lookup = {
                                        str(value): index
                                        for index, value in enumerate(presented_meta["trial_id"])
                                    }
                                    current_tensor = np.stack(
                                        [
                                            presented_tensor[lookup[str(value)]]
                                            for value in frame["trial_id"]
                                        ],
                                        axis=0,
                                    )
                                role = "diagnostic_positive_control"
                            except Exception as exc:
                                failures.append(
                                    {
                                        "status": str(exc).split(":", 1)[0],
                                        "task": task,
                                        "signal": signal_label,
                                        "window": window_name,
                                        "subject": subject,
                                        "session": session_name,
                                        "area": area,
                                        "reason": str(exc),
                                    }
                                )
                                continue
                        else:
                            spec = specs[task]
                            key = (session_name, task)
                            if key not in task_geometry.index:
                                failures.append(
                                    {
                                        "status": "STAGE4A_GEOMETRY_MISSING",
                                        "task": task,
                                        "signal": signal_label,
                                        "window": window_name,
                                        "subject": subject,
                                        "session": session_name,
                                        "area": area,
                                        "reason": "no Stage 4A geometry row",
                                    }
                                )
                                continue
                            geometry_row = task_geometry.loc[key]
                            try:
                                frame, train_mask, test_mask, labels, class_names = _task_frame(
                                    event_frames[session_name], spec, geometry_row
                                )
                                frame["group_for_task"] = frame[spec["group_col"]].astype(int)
                                current_tensor = np.stack(
                                    [feature_map[str(value)] for value in frame["trial_id"]],
                                    axis=0,
                                )
                                current_meta = feature_meta
                                role = str(spec["role"])
                                expected_n = int(geometry_row["train_trials"])
                                expected_test_n = int(geometry_row["test_trials"])
                                if int(train_mask.sum()) != expected_n or int(
                                    test_mask.sum()
                                ) != expected_test_n:
                                    raise ValueError("STAGE4A_TRIAL_GEOMETRY_MISMATCH:train_test_counts")
                            except Exception as exc:
                                failures.append(
                                    {
                                        "status": (
                                            "INSUFFICIENT_GROUPS"
                                            if "INELIGIBLE" in str(exc)
                                            or "FROZEN" in str(exc)
                                            else "ALIGNMENT_FAILURE"
                                            if "STAGE4A" in str(exc)
                                            else "ACCESS_FAILURE"
                                        ),
                                        "task": task,
                                        "signal": signal_label,
                                        "window": window_name,
                                        "subject": subject,
                                        "session": session_name,
                                        "area": area,
                                        "reason": str(exc),
                                    }
                                )
                                continue
                        reps = ["R0", "R1"] if signal == "SUA_SPK" else [
                            f"{signal_label}0",
                            f"{signal_label}1",
                        ]
                        for rep in reps:
                            try:
                                X = _feature_matrix(current_tensor, rep)
                                feature_manifests.append(
                                    {
                                        "task": task,
                                        "signal": signal_label,
                                        "representation": rep,
                                        "window": window_name,
                                        "subject": subject,
                                        "session": session_name,
                                        "area": area,
                                        "tensor_shape": list(current_tensor.shape),
                                        "feature_shape": list(X.shape),
                                        "units": feature_meta.get("units"),
                                        "time_vector_ms": feature_meta.get("time_vector_ms"),
                                    }
                                )
                                result, oof, fold_df, null_df, manifest = _cell(
                                    task=task,
                                    role=role,
                                    signal=signal_label,
                                    representation=rep,
                                    window=window_name,
                                    subject=subject,
                                    session_name=session_name,
                                    area=area,
                                    frame=frame,
                                    train_mask=train_mask,
                                    test_mask=test_mask,
                                    labels=labels,
                                    class_names=class_names,
                                    X=X,
                                    feature_meta=feature_meta,
                                    n_permutations=n_permutations,
                                    seed=seed + session_number * 100000 + len(results),
                                )
                                results.append(result)
                                predictions.append(oof)
                                folds.append(fold_df)
                                nulls.append(null_df)
                                manifests.append(manifest)
                            except Exception as exc:
                                failures.append(
                                    {
                                        "status": (
                                            "NULL_INVALID"
                                            if "NULL" in str(exc)
                                            else "NUMERICAL_FAILURE"
                                        ),
                                        "task": task,
                                        "signal": signal_label,
                                        "representation": rep,
                                        "window": window_name,
                                        "subject": subject,
                                        "session": session_name,
                                        "area": area,
                                        "reason": f"{type(exc).__name__}:{exc}",
                                    }
                                )

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "cell_results": output_dir / "cell_results.csv",
        "predictions": output_dir / "predictions.csv",
        "folds": output_dir / "folds.csv",
        "null_distribution": output_dir / "null_distribution.csv",
        "feature_manifest": output_dir / "feature_manifest.csv",
        "trial_fold_manifest": output_dir / "trial_fold_manifest.json",
        "failures": output_dir / "failures.csv",
        "session_summary": output_dir / "session_summary.csv",
        "subject_summary": output_dir / "subject_summary.csv",
        "leave_one_session_out": output_dir / "leave_one_session_out.csv",
        "what_when_signal_matrix": output_dir / "what_when_signal_matrix.csv",
        "coarse_window_map": output_dir / "coarse_window_map.csv",
    }
    pd.DataFrame(results).to_csv(paths["cell_results"], index=False)
    pd.concat(predictions, ignore_index=True).to_csv(paths["predictions"], index=False) if predictions else pd.DataFrame().to_csv(paths["predictions"], index=False)
    pd.concat(folds, ignore_index=True).to_csv(paths["folds"], index=False) if folds else pd.DataFrame().to_csv(paths["folds"], index=False)
    pd.concat(nulls, ignore_index=True).to_csv(paths["null_distribution"], index=False) if nulls else pd.DataFrame().to_csv(paths["null_distribution"], index=False)
    pd.DataFrame(feature_manifests).to_csv(paths["feature_manifest"], index=False)
    paths["trial_fold_manifest"].write_text(json.dumps(manifests, indent=2), encoding="utf-8")
    pd.DataFrame(failures).to_csv(paths["failures"], index=False)

    cells = pd.DataFrame(results)
    if not cells.empty:
        cells["task_family"] = np.where(
            cells["task"].str.startswith(("W1", "W2", "W3")),
            "WHAT",
            "WHEN",
        )
        session_summary = (
            cells.groupby(["task", "signal", "representation", "window", "subject", "session"], dropna=False)
            .agg(
                observed_balanced_accuracy=("observed_balanced_accuracy", "mean"),
                null_effect=("null_effect", "mean"),
                permutation_p=("permutation_p", "median"),
                area_N=("area", "nunique"),
            )
            .reset_index()
        )
        subject_summary = (
            session_summary.groupby(["task", "signal", "representation", "window", "subject"], dropna=False)
            .agg(
                observed_balanced_accuracy=("observed_balanced_accuracy", "mean"),
                null_effect=("null_effect", "mean"),
                session_N=("session", "nunique"),
            )
            .reset_index()
        )
        loso = []
        for key, group in cells.groupby(["task", "signal", "representation", "window"], dropna=False):
            for omitted in sorted(group["session"].unique()):
                remaining = group[group["session"] != omitted]
                loso.append(
                    {
                        "task": key[0],
                        "signal": key[1],
                        "representation": key[2],
                        "window": key[3],
                        "omitted_session": omitted,
                        "session_N": int(remaining["session"].nunique()),
                        "observed_balanced_accuracy": float(remaining["observed_balanced_accuracy"].mean()),
                        "null_effect": float(remaining["null_effect"].mean()),
                    }
                )
        session_summary.to_csv(paths["session_summary"], index=False)
        subject_summary.to_csv(paths["subject_summary"], index=False)
        pd.DataFrame(loso).to_csv(paths["leave_one_session_out"], index=False)
        primary = cells[cells["window"].eq("full_omission")].copy()
        primary["effect_relative_to_null"] = np.where(
            primary["task"].str.startswith("W1_reversal"),
            primary["G"],
            primary["null_effect"],
        )
        matrix = (
            primary.groupby(["task", "signal", "representation"], dropna=False)
            .agg(
                observed_effect_relative_to_null=("effect_relative_to_null", "mean"),
                observed_balanced_accuracy=("observed_balanced_accuracy", "mean"),
                eligible_session_N=("session", "nunique"),
                successful_cell_N=("session", "size"),
            )
            .reset_index()
        )
        matrix["task_family"] = np.where(
            matrix["task"].str.startswith(("W1", "W2", "W3")),
            "WHAT",
            "WHEN",
        )
        matrix.to_csv(paths["what_when_signal_matrix"], index=False)
        cells[~cells["window"].eq("full_omission")].to_csv(
            paths["coarse_window_map"], index=False
        )
    else:
        for name in (
            "session_summary",
            "subject_summary",
            "leave_one_session_out",
            "what_when_signal_matrix",
            "coarse_window_map",
        ):
            pd.DataFrame().to_csv(paths[name], index=False)

    command_receipts = [
        {
            "command": "python scripts/run_handout4_stage4b_linear_map.py",
            "status": "executed",
            "n_permutations": n_permutations,
        }
    ]
    receipt = {
        "schema_version": 3,
        "experiment": "handout-4-full-corpus-what-when-omission-information",
        "stage": "4B_linear_map",
        "status": "complete",
        "authorization": {
            "SAFE_TO_RUN_STAGE4B_LINEAR": True,
            "SAFE_TO_RUN_M2": False,
            "SAFE_TO_RUN_M3": False,
            "SAFE_TO_RUN_M4": False,
            "TFR_BACKED_LFP": False,
        },
        "frozen_corpus": {
            "catalog_sessions_used": int(len(sessions)),
            "uncatalogued_live_sessions": uncatalogued,
            "uncatalogued_status": SAMPLE_STATUS,
            "session_filenames": [row["filename"] for row in sessions],
        },
        "tasks": {
            task: {
                "role": spec["role"],
                "target": spec["target"],
                "geometry": spec["geometry"],
                "train_slots": spec["train_slots"],
                "test_slots": spec["test_slots"],
                "train_families": spec["train_families"],
                "test_families": spec["test_families"],
                "group_col": spec["group_col"],
            }
            for task, spec in specs.items()
        },
        "representations": {
            "SUA": {"R0": "mean over 9 ms spike-rate bins", "R1": "C-order vectorized 9 ms spike-rate bins"},
            "MUAe": {"MUAe0": "mean over raw channel x time", "MUAe1": "C-order vectorized raw channel x time"},
            "LFP": {"LFP0": "mean over raw channel x time", "LFP1": "C-order vectorized raw channel x time"},
        },
        "coarse_windows_ms": ALL_WINDOWS,
        "filters": {
            "tasks": sorted(task_filter) if task_filter is not None else None,
            "windows": sorted(window_filter) if window_filter is not None else None,
            "signals": sorted(signal_filter) if signal_filter is not None else None,
            "sessions": sorted(session_filter) if session_filter is not None else None,
        },
        "model": {
            "estimator": "RidgeClassifier(class_weight='balanced')",
            "C_grid": C_GRID,
            "selection": "nested leave-one-group-out within outer training partition",
            "pca": {
                "trigger_feature_count": MAX_PCA_FEATURES,
                "max_components": PCA_COMPONENTS,
                "fit_scope": "outer training partition only; null freezes observed preprocessing",
            },
        },
        "null": {
            "primitive": "jnwb.permutation.permute_labels",
            "scheme": "within_cycle; W1 within cycle x slot with p4 complement",
            "n_permutations": n_permutations,
            "seed": seed,
            "observed_fold_geometry_fixed": True,
            "regularization_fixed_under_null": True,
        },
        "counts": {
            "successful_cells": int(len(results)),
            "failed_cells": int(len(failures)),
            "prediction_rows": int(sum(len(frame) for frame in predictions)),
            "null_rows": int(sum(len(frame) for frame in nulls)),
        },
        "outputs": {
            key: _display_path(path)
            for key, path in paths.items()
        },
        "output_hashes": {key: _sha256(path) for key, path in paths.items()},
        "input_hashes": {
            "catalog": _sha256(CATALOG_PATH),
            "readiness": _sha256(READINESS_PATH),
            "stage4a_geometry": _sha256(STAGE4A_DIR / "task_session_geometry.csv"),
            "stage4a_signal_area": _sha256(STAGE4A_DIR / "signal_area_inventory.csv"),
            "runner": _sha256(Path(__file__).resolve()),
        },
        "commands": command_receipts,
        "training_scope": {
            "nonlinear_flat_M2": False,
            "structured_M3": False,
            "ablation_M4": False,
            "architecture_search": False,
        },
        "git_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "stop_rule": "STOP after authorized linear map; do not train M2/M3/M4.",
        "falsifier": "This receipt is superseded if frozen corpus, Stage 4A geometry, Stage 4A.1 alignment, representation, null, or model contracts change.",
    }
    receipt_path = output_dir / "stage4b_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--n-permutations", type=int, default=DEFAULT_PERMUTATIONS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--max-sessions", type=int, default=None)
    parser.add_argument("--max-areas", type=int, default=None)
    parser.add_argument("--tasks", type=str, default=None)
    parser.add_argument("--windows", type=str, default=None)
    parser.add_argument("--signals", type=str, default=None)
    parser.add_argument("--sessions", type=str, default=None)
    args = parser.parse_args()
    result = run(
        output_dir=args.output_dir,
        n_permutations=args.n_permutations,
        seed=args.seed,
        max_sessions=args.max_sessions,
        max_areas=args.max_areas,
        task_filter=set(args.tasks.split(",")) if args.tasks else None,
        window_filter=set(args.windows.split(",")) if args.windows else None,
        signal_filter=set(args.signals.split(",")) if args.signals else None,
        session_filter=set(args.sessions.split(",")) if args.sessions else None,
    )
    print(json.dumps(result["counts"], sort_keys=True), flush=True)
    print("Stage 4B complete: linear map only; M2/M3/M4 not run.", flush=True)


if __name__ == "__main__":
    main()
