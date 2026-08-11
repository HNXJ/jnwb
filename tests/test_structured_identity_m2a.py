import numpy as np
import pandas as pd

from jnwb.structured_identity_m2a import (
    OuterFold,
    extract_rate_raster,
    fit_nested_linear,
    null_metric_distribution,
    permute_reversal_labels,
    representation_pair,
)


class _FakeSession:
    def get_units(self, area=None):
        return pd.DataFrame({"unit_id": [10]}, index=[0])

    def get_spike_times(self, row_index):
        assert row_index == 0
        return np.array([1.05, 1.10, 1.20])


def _rows():
    rows = []
    trial_id = 0
    for cycle in range(3):
        for slot in ("p2", "p3", "p4"):
            for label in ("A", "B"):
                previous = label
                expected = label if slot != "p4" else ("B" if label == "A" else "A")
                rows.append(
                    {
                        "trial_id": trial_id,
                        "start_time": 0.0,
                        "slot_key": slot,
                        "cross_position_cycle": cycle,
                        "expected_identity": expected,
                        "preceding_identity": previous,
                    }
                )
                trial_id += 1
    return pd.DataFrame(rows)


def test_rate_raster_uses_row_position_and_explicit_hz_units():
    rows = pd.DataFrame(
        [{"start_time": 0.0, "slot_key": "p2"}, {"start_time": 0.0, "slot_key": "p2"}]
    )
    raster, unit_indices = extract_rate_raster(_FakeSession(), "V1", rows)
    assert unit_indices == [0]
    assert raster.shape == (2, 1, 59)
    assert np.isfinite(raster).all()


def test_r0_r1_share_identical_samples():
    raster = np.arange(2 * 3 * 59, dtype=float).reshape(2, 3, 59)
    reps = representation_pair(raster)
    assert reps["R0"].shape == (2, 3)
    assert reps["R1"].shape == (2, 177)
    np.testing.assert_array_equal(reps["R1"].reshape(raster.shape), raster)


def test_reversal_null_preserves_p4_complementarity():
    rows = _rows()
    expected = rows["expected_identity"].map({"A": 0, "B": 1}).to_numpy()
    previous = rows["preceding_identity"].map({"A": 0, "B": 1}).to_numpy()
    perm_expected, perm_previous = permute_reversal_labels(
        expected,
        rows["slot_key"].tolist(),
        rows["cross_position_cycle"].to_numpy(),
        seed=42,
    )
    p4 = rows["slot_key"].eq("p4").to_numpy()
    assert np.array_equal(perm_previous[p4], 1 - perm_expected[p4])
    assert np.array_equal(previous[~p4], expected[~p4])


def test_nested_linear_returns_outer_and_inner_diagnostics():
    rows = _rows()
    labels = rows["expected_identity"].map({"A": 0, "B": 1}).to_numpy()
    previous = rows["preceding_identity"].map({"A": 0, "B": 1}).to_numpy()
    groups = rows["cross_position_cycle"].to_numpy()
    train = rows["slot_key"].isin(["p2", "p3"]).to_numpy()
    folds = []
    for fold, held in enumerate(sorted(rows.loc[rows["slot_key"].eq("p4"), "cross_position_cycle"].unique())):
        test = rows["slot_key"].eq("p4").to_numpy() & (groups == held)
        train_mask = train & (groups != held)
        folds.append(
            OuterFold(
                fold=fold,
                held_out_group=int(held),
                train_idx=np.flatnonzero(train_mask),
                test_idx=np.flatnonzero(test),
                inner_groups=tuple(sorted(np.unique(groups[train_mask]).tolist())),
            )
        )
    X = np.column_stack([labels, labels + 0.1, groups]).astype(float)
    oof, fold = fit_nested_linear(
        X,
        labels,
        previous,
        groups,
        folds,
        trial_ids=rows["trial_id"].to_numpy(),
        seed=42,
    )
    assert len(oof) == 6
    assert len(fold) == 3
    assert {"G_accuracy", "G_balanced"}.issubset(fold.columns)


def test_vectorized_null_returns_fixed_length_grouped_metrics():
    rows = _rows()
    labels = rows["expected_identity"].map({"A": 0, "B": 1}).to_numpy()
    previous = rows["preceding_identity"].map({"A": 0, "B": 1}).to_numpy()
    groups = rows["cross_position_cycle"].to_numpy()
    train = rows["slot_key"].isin(["p2", "p3"]).to_numpy()
    folds = []
    for fold, held in enumerate(sorted(rows.loc[rows["slot_key"].eq("p4"), "cross_position_cycle"].unique())):
        test = rows["slot_key"].eq("p4").to_numpy() & (groups == held)
        train_mask = train & (groups != held)
        folds.append(
            OuterFold(
                fold=fold,
                held_out_group=int(held),
                train_idx=np.flatnonzero(train_mask),
                test_idx=np.flatnonzero(test),
                inner_groups=tuple(sorted(np.unique(groups[train_mask]).tolist())),
            )
        )
    X = np.column_stack([labels, labels + 0.1, groups]).astype(float)
    null = null_metric_distribution(
        X,
        labels,
        previous,
        rows["slot_key"].tolist(),
        groups,
        folds,
        {0: 1.0, 1: 1.0, 2: 1.0},
        n_permutations=7,
        seed=42,
        primary=True,
    )
    assert null.shape == (7,)
    assert np.isfinite(null).all()
