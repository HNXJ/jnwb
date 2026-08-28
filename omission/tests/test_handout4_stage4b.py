from __future__ import annotations

import numpy as np
import pandas as pd

from omission.scripts.run_handout4_stage4b_linear_map import (
    _cell,
    _feature_matrix,
    _folds,
)


def _frame(n_groups=4):
    rows = []
    for group in range(n_groups):
        for label in (0, 1):
            rows.append(
                {
                    "trial_id": f"trial-{group}-{label}",
                    "group_for_task": group,
                    "omission_position": "p4",
                }
            )
    return pd.DataFrame(rows)


def test_stage4b_grouped_linear_cell_has_exchangeable_null():
    rng = np.random.default_rng(0)
    frame = _frame()
    labels = np.asarray([0, 1] * 4)
    X = rng.normal(size=(len(frame), 6))
    X[:, 0] += labels
    folds, fold_rows, n_inner = _folds(
        labels,
        frame["group_for_task"].to_numpy(),
        np.ones(len(frame), dtype=bool),
        np.ones(len(frame), dtype=bool),
    )
    assert len(folds) == 4
    assert n_inner >= 2
    result, oof, fold_df, null_df, manifest = _cell(
        task="W2_context_p4",
        role="confirmatory",
        signal="SUA",
        representation="R0",
        window="full_omission",
        subject="S",
        session_name="ses",
        area="V1",
        frame=frame,
        train_mask=np.ones(len(frame), dtype=bool),
        test_mask=np.ones(len(frame), dtype=bool),
        labels=labels,
        class_names=["predictable", "random"],
        X=X,
        feature_meta={"units": "Hz"},
        n_permutations=5,
        seed=42,
    )
    assert result["status"] == "SUCCESS"
    assert result["null_scheme"] == "within_cycle"
    assert len(null_df) == 5
    assert len(oof) == len(frame)
    assert len(fold_df) == len(folds)
    assert manifest["train_mask"] == [True] * len(frame)


def test_stage4b_vector_representation_is_trial_by_feature():
    tensor = np.zeros((3, 2, 4), dtype=np.float32)
    vector = _feature_matrix(tensor, "LFP1")
    collapsed = _feature_matrix(tensor, "LFP0")
    assert vector.shape == (3, 8)
    assert collapsed.shape == (3, 2)
