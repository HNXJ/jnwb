"""Milestone 2A SPK R0/R1 decoding primitives.

This module contains only the approved validation/baseline path for Structured Identity v1.1:
real spike-rate raster extraction, nested grouped linear decoding, reversal scoring, and
exchangeability-matched label nulls.  It deliberately contains no nonlinear or structured model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score

from jnwb.permutation import permute_labels

LABEL_TO_INT = {"A": 0, "B": 1}
WINDOWS_MS = {
    "p1": (0.0, 531.0),
    "p2": (1031.0, 1562.0),
    "p3": (2062.0, 2593.0),
    "p4": (3093.0, 3624.0),
}
BIN_SIZE_MS = 9.0
C_GRID = (0.01, 0.1, 1.0, 10.0)


@dataclass(frozen=True)
class OuterFold:
    fold: int
    held_out_group: int
    train_idx: np.ndarray
    test_idx: np.ndarray
    inner_groups: tuple[int, ...]


def extract_rate_raster(
    session,
    area: str,
    rows: pd.DataFrame,
    *,
    bin_size_ms: float = BIN_SIZE_MS,
) -> tuple[np.ndarray, list[int]]:
    """Extract `(trial, unit, time_bin)` firing rates in Hz from row-indexed spike trains."""
    required = {"start_time", "slot_key"}
    missing = required.difference(rows.columns)
    if missing:
        raise ValueError(f"feature rows missing {sorted(missing)}")
    if bin_size_ms <= 0:
        raise ValueError("bin_size_ms must be positive")
    if rows.empty:
        return np.zeros((0, 0, 0), dtype=np.float64), []
    durations = {
        float(hi - lo) for lo, hi in (WINDOWS_MS[str(slot)] for slot in rows["slot_key"])
    }
    if len(durations) != 1:
        raise ValueError("all feature windows must have the same duration")
    duration_ms = durations.pop()
    n_bins_float = duration_ms / float(bin_size_ms)
    n_bins = int(round(n_bins_float))
    if not np.isclose(n_bins_float, n_bins):
        raise ValueError("bin_size_ms must divide the selected window exactly")
    units = session.get_units(area=area)
    row_indices = list(units.index)
    onsets = pd.to_numeric(rows["start_time"], errors="coerce").to_numpy(float)
    if not np.isfinite(onsets).all():
        raise ValueError(f"non-finite onset in {area}")
    X = np.zeros((len(rows), len(row_indices), n_bins), dtype=np.float64)
    slot_values = rows["slot_key"].astype(str).to_numpy()
    for col, row_index in enumerate(row_indices):
        spikes = session.get_spike_times(row_index)
        if spikes is None or len(spikes) == 0:
            continue
        spikes = np.sort(np.asarray(spikes, dtype=float))
        for row_number, (onset, slot) in enumerate(zip(onsets, slot_values)):
            if slot not in WINDOWS_MS:
                raise ValueError(f"unsupported feature slot {slot!r}")
            lo_ms, hi_ms = WINDOWS_MS[slot]
            edges = np.linspace(lo_ms / 1000.0, hi_ms / 1000.0, n_bins + 1)
            X[row_number, col], _ = np.histogram(spikes - onset, bins=edges)
    return X / (bin_size_ms / 1000.0), row_indices


def representation_pair(
    raster_hz: np.ndarray,
) -> dict[str, np.ndarray]:
    """Return R0 mean rate and R1 vectorized rate from identical raster samples."""
    raster = np.asarray(raster_hz, dtype=np.float64)
    if raster.ndim != 3 or not np.isfinite(raster).all():
        raise ValueError("raster_hz must be finite with shape (trial, unit, time)")
    r0 = raster.mean(axis=2, dtype=np.float64)
    r1 = raster.reshape(raster.shape[0], -1)
    reconstructed = r1.reshape(raster.shape)
    np.testing.assert_array_equal(reconstructed, raster)
    return {"R0": r0, "R1": r1}


def _ridge_scores(
    X_train: np.ndarray,
    labels: np.ndarray,
    X_eval: np.ndarray,
    C: float,
) -> np.ndarray:
    """Fast dual-form balanced ridge scores for the approved linear baseline."""
    if C <= 0:
        raise ValueError("C must be positive")
    X_train = np.asarray(X_train, dtype=np.float64)
    X_eval = np.asarray(X_eval, dtype=np.float64)
    labels = np.asarray(labels, dtype=int)
    mean = X_train.mean(axis=0)
    scale = X_train.std(axis=0)
    scale[scale == 0.0] = 1.0
    train = (X_train - mean) / scale
    eval_ = (X_eval - mean) / scale
    y_pm = 2.0 * labels - 1.0
    counts = np.bincount(labels, minlength=2).astype(float)
    weights = np.sqrt(len(labels) / (2.0 * counts[labels]))
    weighted_train = train * weights[:, None]
    weighted_y = y_pm * weights
    gram = weighted_train @ weighted_train.T
    gram.flat[:: len(gram) + 1] += 1.0 / float(C)
    dual = np.linalg.solve(gram, weighted_y)
    coefficients = weighted_train.T @ dual
    return eval_ @ coefficients


def _has_both_classes(labels: np.ndarray, indices: np.ndarray) -> bool:
    return set(np.asarray(labels)[indices].tolist()) == {0, 1}


def _metric_bundle(
    y_expected: np.ndarray,
    y_previous: np.ndarray | None,
    prediction: np.ndarray,
    score: np.ndarray,
) -> dict[str, float]:
    expected = np.asarray(y_expected, dtype=int)
    pred = np.asarray(prediction, dtype=int)
    result = {
        "accuracy_expected": float(accuracy_score(expected, pred)),
        "balanced_accuracy_expected": float(balanced_accuracy_score(expected, pred)),
        "auc_expected": float(roc_auc_score(expected, score)),
    }
    if y_previous is not None:
        previous = np.asarray(y_previous, dtype=int)
        result.update(
            {
                "accuracy_previous": float(accuracy_score(previous, pred)),
                "balanced_accuracy_previous": float(
                    balanced_accuracy_score(previous, pred)
                ),
                "auc_previous": float(roc_auc_score(previous, score)),
            }
        )
        result["G_accuracy"] = result["accuracy_expected"] - result["accuracy_previous"]
        result["G_balanced"] = (
            result["balanced_accuracy_expected"]
            - result["balanced_accuracy_previous"]
        )
        result["G_auc"] = result["auc_expected"] - result["auc_previous"]
    return result


def build_outer_folds(
    groups: np.ndarray,
    labels: np.ndarray,
    *,
    train_mask: np.ndarray | None = None,
    test_mask: np.ndarray | None = None,
    min_train_groups: int = 2,
) -> list[OuterFold]:
    """Build explicit held-out-group folds without fallback behavior."""
    groups = np.asarray(groups, dtype=int)
    labels = np.asarray(labels, dtype=int)
    if train_mask is None:
        train_mask = np.ones(len(groups), dtype=bool)
    if test_mask is None:
        test_mask = np.ones(len(groups), dtype=bool)
    folds = []
    candidate_groups = sorted(np.unique(groups[test_mask]).tolist())
    for fold, held_out in enumerate(candidate_groups):
        train = train_mask & (groups != held_out)
        test = test_mask & (groups == held_out)
        train_groups = sorted(np.unique(groups[train]).tolist())
        if (
            len(train_groups) < min_train_groups
            or not _has_both_classes(labels, np.flatnonzero(train))
            or not _has_both_classes(labels, np.flatnonzero(test))
        ):
            continue
        folds.append(
            OuterFold(
                fold=fold,
                held_out_group=int(held_out),
                train_idx=np.flatnonzero(train),
                test_idx=np.flatnonzero(test),
                inner_groups=tuple(train_groups),
            )
        )
    return folds


def _select_c(
    X: np.ndarray,
    labels: np.ndarray,
    groups: np.ndarray,
    train_idx: np.ndarray,
    inner_groups: Sequence[int],
    *,
    seed: int,
    c_grid: Iterable[float] = C_GRID,
) -> tuple[float, float, int]:
    """Select C using only outer-training cycles and return validation score and N."""
    scores = []
    for C in c_grid:
        fold_scores = []
        for inner_group in inner_groups:
            validation = train_idx[groups[train_idx] == inner_group]
            inner_train = train_idx[groups[train_idx] != inner_group]
            if not _has_both_classes(labels, inner_train) or not _has_both_classes(
                labels, validation
            ):
                continue
            validation_score = _ridge_scores(
                X[inner_train], labels[inner_train], X[validation], C
            )
            fold_scores.append(
                balanced_accuracy_score(
                    labels[validation], (validation_score >= 0.0).astype(int)
                )
            )
        if fold_scores:
            scores.append((float(np.mean(fold_scores)), float(C), len(fold_scores)))
    if not scores:
        raise ValueError("no valid inner validation partitions")
    # Deterministic tie-break: best validation score, then smaller C.
    scores.sort(key=lambda item: (-item[0], item[1]))
    best_score, best_C, n_inner = scores[0]
    return best_C, best_score, n_inner


def fit_nested_linear(
    X: np.ndarray,
    y_expected: np.ndarray,
    y_previous: np.ndarray | None,
    groups: np.ndarray,
    folds: Sequence[OuterFold],
    *,
    trial_ids: Sequence[int],
    seed: int,
    c_grid: Iterable[float] = C_GRID,
    selected_C_by_fold: dict[int, float] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit the approved nested linear baseline and return OOF and fold diagnostics."""
    X = np.asarray(X, dtype=np.float64)
    y_expected = np.asarray(y_expected, dtype=int)
    groups = np.asarray(groups, dtype=int)
    if X.ndim != 2 or X.shape[0] != len(y_expected) or len(groups) != len(y_expected):
        raise ValueError("X, labels, and groups have incompatible shapes")
    oof_rows = []
    fold_rows = []
    for fold_spec in folds:
        if selected_C_by_fold is None:
            selected_C, inner_score, n_inner = _select_c(
                X,
                y_expected,
                groups,
                fold_spec.train_idx,
                fold_spec.inner_groups,
                seed=seed + fold_spec.fold * 1000,
                c_grid=c_grid,
            )
        else:
            if fold_spec.fold not in selected_C_by_fold:
                raise ValueError(
                    f"missing frozen C for null fold {fold_spec.fold}"
                )
            selected_C = float(selected_C_by_fold[fold_spec.fold])
            inner_score = float("nan")
            n_inner = 0
        train_score = _ridge_scores(
            X[fold_spec.train_idx],
            y_expected[fold_spec.train_idx],
            X[fold_spec.train_idx],
            selected_C,
        )
        test_score = _ridge_scores(
            X[fold_spec.train_idx],
            y_expected[fold_spec.train_idx],
            X[fold_spec.test_idx],
            selected_C,
        )
        train_pred = (train_score >= 0.0).astype(int)
        test_pred = (test_score >= 0.0).astype(int)
        outer_metrics = _metric_bundle(
            y_expected[fold_spec.test_idx],
            y_previous[fold_spec.test_idx] if y_previous is not None else None,
            test_pred,
            test_score,
        )
        train_metrics = _metric_bundle(
            y_expected[fold_spec.train_idx],
            None,
            train_pred,
            train_score,
        )
        fold_rows.append(
            {
                "fold": fold_spec.fold,
                "held_out_group": fold_spec.held_out_group,
                "n_train": len(fold_spec.train_idx),
                "n_test": len(fold_spec.test_idx),
                "n_inner_partitions": n_inner,
                "selected_C": selected_C,
                "inner_balanced_accuracy": inner_score,
                "train_balanced_accuracy": train_metrics[
                    "balanced_accuracy_expected"
                ],
                "outer_balanced_accuracy_expected": outer_metrics[
                    "balanced_accuracy_expected"
                ],
                "outer_balanced_accuracy_previous": outer_metrics.get(
                    "balanced_accuracy_previous", np.nan
                ),
                "generalization_gap_expected": inner_score
                - outer_metrics["balanced_accuracy_expected"],
                **{
                    key: value
                    for key, value in outer_metrics.items()
                    if key.startswith("G_")
                },
            }
        )
        for index, prediction, score in zip(
            fold_spec.test_idx, test_pred, test_score
        ):
            row = {
                "row_index": int(index),
                "trial_id": int(trial_ids[index]),
                "fold": int(fold_spec.fold),
                "held_out_group": int(fold_spec.held_out_group),
                "y_expected": int(y_expected[index]),
                "prediction": int(prediction),
                "decision_score": float(score),
            }
            if y_previous is not None:
                row["y_previous"] = int(y_previous[index])
            oof_rows.append(row)
    return (
        pd.DataFrame(oof_rows).sort_values("row_index").reset_index(drop=True),
        pd.DataFrame(fold_rows),
    )


def null_metric_distribution(
    X: np.ndarray,
    y_expected: np.ndarray,
    y_previous: np.ndarray | None,
    slots: Sequence[str],
    groups: np.ndarray,
    folds: Sequence[OuterFold],
    selected_C_by_fold: dict[int, float],
    *,
    n_permutations: int,
    seed: int,
    primary: bool,
) -> np.ndarray:
    """Compute grouped null metrics with vectorized ridge refits per outer fold.

    The permutation exchangeability is identical to ``permute_reversal_labels`` /
    ``permute_positive_labels``.  The observed-fold C values are frozen for the null, so inner
    model selection is not repeated on each draw and cannot dominate the null runtime.
    """
    X = np.asarray(X, dtype=np.float64)
    y_expected = np.asarray(y_expected, dtype=int)
    groups = np.asarray(groups, dtype=int)
    n = len(y_expected)
    if n_permutations < 1:
        raise ValueError("n_permutations must be positive")
    expected_parts = []
    previous_parts = []
    score_parts = []
    prediction_parts = []
    for fold_spec in folds:
        train_idx = fold_spec.train_idx
        test_idx = fold_spec.test_idx
        train_base = y_expected[train_idx]
        train_mean = X[train_idx].mean(axis=0)
        train_scale = X[train_idx].std(axis=0)
        train_scale[train_scale == 0.0] = 1.0
        X_train = (X[train_idx] - train_mean) / train_scale
        X_test = (X[test_idx] - train_mean) / train_scale
        counts = np.bincount(train_base, minlength=2).astype(float)
        weights = np.sqrt(len(train_base) / (2.0 * counts[train_base]))
        weighted_train = X_train * weights[:, None]
        gram = weighted_train @ weighted_train.T
        gram.flat[:: len(gram) + 1] += 1.0 / float(
            selected_C_by_fold[fold_spec.fold]
        )
        perm_expected = np.empty((n, n_permutations), dtype=int)
        perm_previous = np.empty((n, n_permutations), dtype=int) if primary else None
        for permutation in range(n_permutations):
            if primary:
                expected, previous = permute_reversal_labels(
                    y_expected,
                    slots,
                    groups,
                    seed=seed + 100_000 + permutation,
                )
                perm_previous[:, permutation] = previous
            else:
                expected = permute_positive_labels(
                    y_expected,
                    groups,
                    seed=seed + 100_000 + permutation,
                )
            perm_expected[:, permutation] = expected
        rhs = (2.0 * perm_expected[train_idx] - 1.0) * weights[:, None]
        coefficients = weighted_train.T @ np.linalg.solve(gram, rhs)
        scores = X_test @ coefficients
        prediction = (scores >= 0.0).astype(int)
        expected_parts.append(perm_expected[test_idx])
        if primary:
            previous_parts.append(perm_previous[test_idx])
        score_parts.append(scores)
        prediction_parts.append(prediction)
    expected = np.concatenate(expected_parts, axis=0)
    prediction = np.concatenate(prediction_parts, axis=0)
    if primary:
        previous = np.concatenate(previous_parts, axis=0)

    def balanced_accuracy_matrix(labels: np.ndarray) -> np.ndarray:
        result = np.zeros(n_permutations, dtype=float)
        for value in (0, 1):
            mask = labels == value
            denominator = mask.sum(axis=0)
            numerator = np.sum((prediction == value) & mask, axis=0)
            result += np.divide(
                numerator,
                denominator,
                out=np.zeros(n_permutations, dtype=float),
                where=denominator > 0,
            )
        return result / 2.0

    expected_balanced = balanced_accuracy_matrix(expected)
    if primary:
        return expected_balanced - balanced_accuracy_matrix(previous)
    return expected_balanced


def permute_reversal_labels(
    y_expected: np.ndarray,
    slots: Sequence[str],
    groups: np.ndarray,
    *,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Permute labels within cycle/slot groups while preserving p4 complementarity."""
    y_expected = np.asarray(y_expected, dtype=int)
    groups = np.asarray(groups, dtype=int)
    slot_groups = np.asarray(
        [f"{int(group)}:{slot}" for group, slot in zip(groups, slots)],
        dtype=object,
    )
    permuted_expected = permute_labels(
        y_expected,
        groups=slot_groups,
        scheme="within_group",
        rng=np.random.default_rng(seed),
    )
    permuted_previous = permuted_expected.copy()
    p4 = np.asarray(slots, dtype=str) == "p4"
    permuted_previous[p4] = 1 - permuted_expected[p4]
    return permuted_expected, permuted_previous


def permute_positive_labels(
    labels: np.ndarray,
    groups: np.ndarray,
    *,
    seed: int,
) -> np.ndarray:
    """Permute presented-identity labels within p1 cycles."""
    return permute_labels(
        np.asarray(labels, dtype=int),
        groups=np.asarray(groups, dtype=int),
        scheme="within_group",
        rng=np.random.default_rng(seed),
    )
