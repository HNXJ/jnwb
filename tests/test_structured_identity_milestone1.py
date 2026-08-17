from pathlib import Path

import numpy as np
import pandas as pd

from jnwb.structured_identity import (
    MAIN_ANALYSIS,
    POSITIVE_CONTROL,
    assign_outer_folds,
    build_canonical_trial_table,
    build_inner_validation_partitions,
    build_permutation_plan,
    build_representation_ladder,
)
from jnwb.trial_ontology import parse_condition


class _FakeSession:
    nwb_path = Path("sub-C31o_ses-230823_rec.nwb")
    _metadata = {"subject_id": "C31o"}

    def get_epochs(self, phase=None, condition=None, correct_only=True):
        del phase
        n = 9
        times = np.array([0.0, 1.0, 2.0, 100.0, 101.0, 102.0, 200.0, 201.0, 202.0])
        table = pd.DataFrame({"start_time": times, "correct": np.ones(n)})
        return table if not correct_only else table[table["correct"] == 1.0]


def test_canonical_table_uses_ontology_and_keeps_positive_control_separate():
    table = build_canonical_trial_table(_FakeSession(), slot_keys=("p2", "p3", "p4"))

    assert set(table["analysis"]) == {MAIN_ANALYSIS, POSITIVE_CONTROL}
    p4 = table[(table["analysis"] == MAIN_ANALYSIS) & (table["slot_key"] == "p4")]
    assert set(p4[p4["condition"] == "AAAX"]["expected_identity"]) == {"B"}
    assert set(p4[p4["condition"] == "BBBX"]["expected_identity"]) == {"A"}
    presented = table[table["analysis"] == POSITIVE_CONTROL]
    assert set(presented["presented_identity"]) == {"A", "B"}
    assert table[
        (table["analysis"] == POSITIVE_CONTROL)
        | ((table["analysis"] == MAIN_ANALYSIS) & table["sequence_family"].isin(["A", "B"]))
    ]["eligible"].all()
    assert not table[
        (table["analysis"] == MAIN_ANALYSIS) & (table["sequence_family"] == "R")
    ]["eligible"].any()


def test_outer_and_inner_fold_geometry_is_deterministic_and_grouped():
    table = build_canonical_trial_table(_FakeSession(), slot_keys=("p2",))
    eligible = table[table["eligible"]].copy()

    first = assign_outer_folds(eligible)
    second = assign_outer_folds(eligible)
    assert first[["trial_id", "outer_fold"]].equals(second[["trial_id", "outer_fold"]])
    assert first.groupby(["session", "analysis", "slot_key"])["outer_fold"].nunique().min() >= 2

    inner = build_inner_validation_partitions(first)
    usable = inner[inner["inner_role"].isin(["inner_train", "inner_validation"])]
    assert not usable.empty
    for _, group in usable.groupby(["session", "analysis", "slot_key", "outer_fold", "inner_fold"]):
        assert set(group.loc[group["inner_role"] == "inner_train", "trial_group"]).isdisjoint(
            set(group.loc[group["inner_role"] == "inner_validation", "trial_group"])
        )


def test_single_cycle_is_explicitly_marked_ineligible_for_grouped_outer_inference():
    trials = pd.DataFrame(
        {
            "trial_id": [1, 2],
            "session": ["s", "s"],
            "analysis": [MAIN_ANALYSIS, MAIN_ANALYSIS],
            "slot_key": ["p2", "p2"],
            "cycle": [0, 0],
            "eligible": [True, True],
        }
    )
    plan = assign_outer_folds(trials)
    assert (plan["outer_fold_status"] == "insufficient_groups").all()
    assert (plan["outer_fold"] == -1).all()


def test_representation_ladder_preserves_raster_for_r1_and_r2():
    raster = np.arange(2 * 3 * 4, dtype=np.float64).reshape(2, 3, 4)
    ladder = build_representation_ladder(raster, modality="SPK")

    np.testing.assert_allclose(ladder["X_rate"], raster.mean(axis=2))
    np.testing.assert_array_equal(
        ladder["X_vec"].reshape(raster.shape), raster
    )
    np.testing.assert_array_equal(ladder["X_structured"], raster)
    assert ladder["contract"]["space_axis_topology"].startswith("unordered_units")


def test_permutation_plan_preserves_each_group_class_composition():
    labels = np.array(["A", "B", "A", "B", "A", "B"])
    groups = np.array([0, 0, 1, 1, 2, 2])
    plan = build_permutation_plan(labels, groups, n_permutations=5, seed=42)

    assert plan["scheme"] == "within_group"
    assert plan["group_composition_preserved"] is True
    assert len(plan["draw_manifest"]) == 5
    # Independent draws are represented by deterministic digests, not hidden RNG state.
    assert plan["draw_manifest"]["label_digest"].nunique() >= 1


def test_p4_ontology_direction_is_explicit():
    assert parse_condition("AAAX")["expected_identity"] == "B"
    assert parse_condition("BBBX")["expected_identity"] == "A"
