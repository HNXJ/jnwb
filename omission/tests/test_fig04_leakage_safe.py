import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "compute_omission_identity_leakage_safe.py"
SPEC = importlib.util.spec_from_file_location("fig04_leakage_safe", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_assign_temporal_cycles_preserves_original_order():
    cycles = MODULE.assign_temporal_cycles([0.0, 1.0, 2.0, 100.0, 101.0, 102.0])
    np.testing.assert_array_equal(cycles, [0, 0, 0, 1, 1, 1])


def test_cycle_safe_decoder_persists_fixed_folds_and_null_draws():
    rng = np.random.default_rng(0)
    labels = np.tile([0, 1], 8)
    cycles = np.repeat(np.arange(8), 2)
    X = np.column_stack(
        [labels + rng.normal(0.0, 0.05, len(labels)), rng.normal(size=len(labels))]
    )

    result = MODULE.decode_binary_cycle_safe(
        X, labels, cycles, seed=42, n_permutations=7
    )

    assert result["status"] == "success"
    assert result["n_folds"] == 8
    assert result["n_permutations"] == 7
    assert result["accuracy_loco_balanced"] > 0.9
    assert len(result["oof"]) == len(labels)
    assert np.all(result["fold_assignments"] >= 0)


def test_within_cycle_permutation_preserves_cycle_class_counts():
    labels = np.array([0, 0, 1, 1, 0, 1])
    cycles = np.array([0, 0, 0, 0, 1, 1])
    permuted = MODULE._within_cycle_permutation(
        labels, cycles, np.random.default_rng(42)
    )

    for cycle in np.unique(cycles):
        mask = cycles == cycle
        np.testing.assert_array_equal(
            np.bincount(permuted[mask], minlength=2),
            np.bincount(labels[mask], minlength=2),
        )
