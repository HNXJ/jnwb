#!/usr/bin/env python3
"""Handout 4B continuation, Required Claude Procedure Step 3: validate the batched closed-form
ridge null solver in scripts/run_handout4_stage4b_linear_map.py's `_null_distribution` against
the reference (one sklearn RidgeClassifier fit per permutation) implementation, on a fixed
synthetic dataset.

Read-only with respect to the runner: imports it as a module, does not edit it. Per the
continuation handout: "If equivalence is not demonstrated, revert to the slower reference null
or mark the map NUMERICAL_FAILURE; never silently mix the two."

Comparison performed on a fixed synthetic dataset with the same folds, same preprocessing
(StandardScaler + optional PCA, reused via _prepare_features), same regularization (C selected
by the runner's own _select_c on the observed, non-permuted data -- both paths use that same C
per fold, matching the runner's actual behavior since _null_distribution reuses `selected_C`
from the observed fit rather than re-selecting per permutation), and the same permuted labels
(same seed, same permute_labels calls).

Usage:
    python scripts/validate_stage4b_batched_null.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import balanced_accuracy_score

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = REPO_ROOT / "scripts" / "run_handout4_stage4b_linear_map.py"

sys.path.insert(0, str(REPO_ROOT))


def _load_runner():
    spec = importlib.util.spec_from_file_location("stage4b_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass introspection needs this registered first
    spec.loader.exec_module(module)
    return module


def _make_synthetic(rng: np.random.Generator, n_groups: int = 6, per_group: int = 20, n_features: int = 12):
    """Fixed synthetic dataset: `n_groups` groups (cycles), `per_group` trials each, binary
    labels with a real (but modest, not saturating) linear signal plus noise, so the reference
    and batched fits have nontrivial coefficients to disagree about if they're going to."""
    n = n_groups * per_group
    groups = np.repeat(np.arange(n_groups), per_group)
    true_w = rng.normal(size=n_features)
    X = rng.normal(size=(n, n_features))
    logits = X @ true_w * 0.5
    labels = (logits + rng.normal(scale=1.5, size=n) > 0).astype(int)
    # Guarantee both classes present in every group (folds/inner-CV require it).
    for g in range(n_groups):
        idx = np.flatnonzero(groups == g)
        if len(set(labels[idx])) < 2:
            labels[idx[0]] = 0
            labels[idx[1]] = 1
    train_mask = np.ones(n, dtype=bool)
    test_mask = np.ones(n, dtype=bool)
    return X, labels, groups, train_mask, test_mask


def _reference_null(runner, prepared, labels, groups, n_classes, n_permutations, seed):
    """Slow reference: one real sklearn RidgeClassifier fit per permutation per fold, reusing
    the runner's own _fit_prepared (the exact function the OBSERVED fit uses) -- not a
    reimplementation, the same call, just looped instead of batched."""
    from jnwb.permutation import permute_labels

    rows = np.full(n_permutations, np.nan)
    for permutation in range(n_permutations):
        rng = np.random.default_rng(seed + permutation)
        shuffled = permute_labels(labels, groups=groups, scheme="within_group", rng=rng)
        fold_pred, fold_truth = [], []
        skip = False
        for item in prepared:
            fold = item["fold"]
            train_labels = shuffled[fold.train_idx]
            if len(np.unique(train_labels)) < n_classes:
                skip = True
                break
            pred, _ = runner._fit_prepared(
                item["X_train"], train_labels, item["X_test"], item["selected_C"]
            )
            fold_pred.append(pred)
            fold_truth.append(shuffled[fold.test_idx])
        if skip or not fold_pred:
            continue
        rows[permutation] = balanced_accuracy_score(
            np.concatenate(fold_truth), np.concatenate(fold_pred)
        )
    return rows


def main() -> int:
    runner = _load_runner()
    rng = np.random.default_rng(20260811)
    n_permutations = 50
    seed = 42

    X, labels, groups, train_mask, test_mask = _make_synthetic(rng)
    n_classes = len(set(labels.tolist()))

    folds, fold_rows, valid_inner = runner._folds(labels, groups, train_mask, test_mask)
    print(f"folds: {len(folds)} eligible, {valid_inner} valid inner partitions")
    if len(folds) < 2:
        print("SYNTHETIC_DATA_INSUFFICIENT: fewer than 2 eligible folds, cannot validate")
        return 2

    trial_ids = [f"synthetic-{i}" for i in range(len(labels))]
    oof, fold_summary, prepared = runner._observed_fit(
        X, labels, None, groups, folds, trial_ids
    )
    print("observed fold C selections:", fold_summary["selected_C"].tolist())

    batched_rows, batched_invalid = runner._null_distribution(
        labels, None, None, groups, prepared, n_classes, n_permutations, seed, reversal=False
    )
    reference_rows = _reference_null(
        runner, prepared, labels, groups, n_classes, n_permutations, seed
    )

    valid_mask = ~np.isnan(reference_rows)
    n_valid = int(valid_mask.sum())
    print(f"batched: {len(batched_rows)} values, {batched_invalid} invalid permutations")
    print(f"reference: {n_valid}/{n_permutations} valid permutations")

    if len(batched_rows) != n_permutations:
        print(f"NUMERICAL_FAILURE: batched null returned {len(batched_rows)} values, expected {n_permutations}")
        return 1

    diffs = np.abs(batched_rows[valid_mask] - reference_rows[valid_mask])
    max_diff = float(np.max(diffs)) if n_valid else float("nan")
    mean_diff = float(np.mean(diffs)) if n_valid else float("nan")
    print(f"max |batched - reference| balanced-accuracy diff: {max_diff:.10f}")
    print(f"mean |batched - reference| balanced-accuracy diff: {mean_diff:.10f}")

    tolerance = 1e-9
    equivalent = n_valid > 0 and max_diff < tolerance
    if equivalent:
        print(f"EQUIVALENT within tolerance {tolerance:g} -- batched null matches the reference sklearn fit exactly (numerical solver, not an approximation).")
        return 0
    else:
        print(f"NUMERICAL_FAILURE: batched null diverges from the reference sklearn fit by up to {max_diff:.6g} (tolerance {tolerance:g}). Do not use the batched null for production results.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
