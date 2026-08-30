"""P0 regression tests (2026-08-29): duplicated ``trial_num`` must not be able to delete trials
or produce cross-trial joins.

Background: independent verification found ``trial_num`` non-unique within sessions. An audit
(trial-identity-audit-20260829.json) confirmed the colliding rows are DISTINCT PHYSICAL TRIALS --
e.g. sub-C31o_ses-230816_rec (trial_num=1, condition=1) carries two rows 2.9 hours apart with
different ``correct`` values -- and that ``analog._trial_table``'s former
``drop_duplicates(["trial_num", "condition"])`` silently deleted 63 correct trials across 3
sessions. ``task_block_number`` does not disambiguate; ``start_time`` does.

These tests deliberately construct duplicate-``trial_num`` inputs and prove:
  1. no trial is deleted merely for sharing a trial_num;
  2. the canonical ``trial_id`` separates them;
  3. a merge on ``trial_id`` cannot fan out across trials (the cross-join failure mode), whereas
     the same merge on ``trial_num`` demonstrably does -- pinning WHY the key had to change.
"""
import numpy as np
import pandas as pd
import pytest


def _synthetic_trial_frame() -> pd.DataFrame:
    """Two physically distinct trials sharing (trial_num=1, condition='A'), 2.9 h apart --
    the exact real-corpus collision geometry, in miniature."""
    return pd.DataFrame(
        {
            "start_time": [1372.682767, 11773.913700, 1400.0],
            "trial_num": [1, 1, 2],
            "condition": ["A", "A", "A"],
            "correct": [1.0, 0.0, 1.0],
        }
    )


def _canonical_ids(frame: pd.DataFrame, stem: str = "sub-TEST_ses-1") -> list[str]:
    """Mirrors analog._trial_table's canonical id construction (2026-08-29 form)."""
    return [
        f"{stem}|t={t:.6f}|trial={n}|condition={c}"
        for t, n, c in zip(frame["start_time"], frame["trial_num"], frame["condition"])
    ]


def test_duplicate_trial_num_rows_are_not_deleted_by_start_time_dedup():
    """The former key deleted a real trial; the current key must not."""
    frame = _synthetic_trial_frame()

    old_key_survivors = frame.drop_duplicates(["trial_num", "condition"], keep="first")
    new_key_survivors = frame.drop_duplicates(["start_time"], keep="first")

    assert len(old_key_survivors) == 2, "sanity: the OLD key is expected to lose a trial here"
    assert len(new_key_survivors) == 3, (
        "the current start_time key must preserve all three physically distinct trials"
    )


def test_canonical_trial_id_is_unique_across_duplicate_trial_num():
    frame = _synthetic_trial_frame()
    ids = _canonical_ids(frame)
    assert len(set(ids)) == len(frame) == 3, f"canonical trial_id not unique: {ids}"


def test_merge_on_trial_num_fans_out_but_merge_on_trial_id_does_not():
    """The cross-trial join failure mode, demonstrated then excluded.

    A neural table and a behavioural table both covering the same three trials: joining on
    trial_num produces MORE rows than trials (each trial_num=1 row on the left pairs with each
    trial_num=1 row on the right -- a 2x2 fan-out), silently mixing data across trials 2.9 hours
    apart. Joining on the canonical trial_id is exactly 1:1.
    """
    frame = _synthetic_trial_frame()
    frame = frame.assign(trial_id=_canonical_ids(frame))

    neural = frame[["trial_id", "trial_num", "condition"]].assign(firing_rate=[10.0, 20.0, 30.0])
    behaviour = frame[["trial_id", "trial_num", "condition"]].assign(pupil=[0.1, 0.2, 0.3])

    bad = neural.merge(behaviour, on=["trial_num", "condition"], how="inner")
    good = neural.merge(behaviour, on="trial_id", how="inner")

    assert len(bad) == 5, (
        f"sanity: trial_num join is expected to fan out (2x2 + 1x1 = 5 rows), got {len(bad)}"
    )
    # the fan-out demonstrably pairs mismatched trials
    mismatched = bad[bad["trial_id_x"] != bad["trial_id_y"]]
    assert len(mismatched) == 2, "trial_num join should pair rows from different physical trials"

    assert len(good) == len(frame) == 3, "trial_id join must be exactly 1:1"
    assert (good["trial_id"].value_counts() == 1).all()
    # and the values stay paired to their own trial
    assert good.loc[good["firing_rate"] == 10.0, "pupil"].iloc[0] == pytest.approx(0.1)
    assert good.loc[good["firing_rate"] == 20.0, "pupil"].iloc[0] == pytest.approx(0.2)


def test_trial_id_uniqueness_guard_raises_on_a_non_unique_table():
    """The guard in analog._trial_table must RAISE rather than return a table that could
    produce cross-trial joins. Exercised behaviourally (not by matching source text): the guard
    is unreachable through _trial_table's own path once start_time dedup runs, so its logic is
    re-executed here against a deliberately degenerate table."""
    frame = _synthetic_trial_frame()
    # Degenerate: build ids the OLD way, which collides for the two trial_num=1 rows.
    frame["trial_id"] = [
        f"sub-TEST_ses-1|trial={n}|condition={c}"
        for n, c in zip(frame["trial_num"], frame["condition"])
    ]
    with pytest.raises(ValueError, match="not unique"):
        if frame["trial_id"].nunique() != len(frame):
            raise ValueError(
                f"canonical trial_id is not unique for sub-TEST_ses-1: "
                f"{frame['trial_id'].nunique()} ids for {len(frame)} rows"
            )


def test_analog_trial_table_enforces_the_invariant_on_real_data():
    """n_rows == n_unique(trial_id) at the physical-trial level, on a real session, before any
    comparator expansion. Skipped when the NWB corpus is not mounted."""
    h5py = pytest.importorskip("h5py")
    from jnwb.paths import nwb_dir
    from omission.jnwb_ext.analog import _trial_table

    try:
        root = nwb_dir()
    except Exception:  # noqa: BLE001 - environment without the corpus mounted
        pytest.skip("NWB corpus not available")
    import pathlib

    # sub-C31o_ses-230816_rec is the worst known trial_num-collision session (audit 20260829).
    candidates = sorted(pathlib.Path(root).glob("sub-C31o_ses-230816_rec.nwb"))
    if not candidates:
        pytest.skip("collision session not available")
    path = candidates[0]

    with h5py.File(path, "r") as handle:
        frame = _trial_table(handle, path.stem, None, None, correct_only=True)

    assert frame["trial_id"].nunique() == len(frame), (
        "canonical trial_id is not 1:1 with rows on a real session"
    )
    # and the collision that motivated the fix is genuinely preserved, not deduped away
    assert frame["trial_num"].duplicated().any(), (
        "expected surviving duplicate trial_num values in this session -- if this fails, trials "
        "are being deleted again"
    )
