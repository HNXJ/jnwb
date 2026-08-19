import pandas as pd

from scripts.inspect_structured_identity_reversal_design import (
    CONTRASTS,
    _contrast_geometry,
    _label_proof,
    _session_summary,
)


def _session_frame(include_p3=True):
    rows = []
    trial_id = 0
    for cycle in range(3):
        for slot in (["p2", "p3"] if include_p3 else ["p2"]):
            for identity in ("A", "B"):
                rows.append(
                    {
                        "session": "s1",
                        "subject": "sub1",
                        "slot_key": slot,
                        "cross_position_cycle": cycle,
                        "expected_identity": identity,
                        "preceding_identity": identity,
                        "trial_id": trial_id,
                    }
                )
                trial_id += 1
        rows.extend(
            [
                {
                    "session": "s1",
                    "subject": "sub1",
                    "slot_key": "p4",
                    "cross_position_cycle": cycle,
                    "expected_identity": "B" if cycle % 2 == 0 else "A",
                    "preceding_identity": "A" if cycle % 2 == 0 else "B",
                    "trial_id": trial_id,
                },
                {
                    "session": "s1",
                    "subject": "sub1",
                    "slot_key": "p4",
                    "cross_position_cycle": cycle,
                    "expected_identity": "A" if cycle % 2 == 0 else "B",
                    "preceding_identity": "B" if cycle % 2 == 0 else "A",
                    "trial_id": trial_id + 1,
                },
            ]
        )
        trial_id += 2
    return pd.DataFrame(rows)


def test_label_proof_records_equal_p2_p3_and_opposite_p4():
    proof = _label_proof(_session_frame())
    relation = proof.groupby("slot_key")["relation"].unique().to_dict()
    assert relation["p2"].tolist() == ["equal"]
    assert relation["p3"].tolist() == ["equal"]
    assert relation["p4"].tolist() == ["opposite"]


def test_primary_requires_both_p2_and_p3_when_pooled():
    summary, _ = _session_summary(_session_frame(include_p3=False))
    primary = summary[summary["contrast"] == "p2p3_to_p4"].iloc[0]
    assert primary["design_status"] == "INELIGIBLE_DESIGN"
    assert "TRAIN_SLOT_MISSING_p3" in primary["reason"]


def test_primary_geometry_has_cycle_held_out_outer_and_inner_partitions():
    config = CONTRASTS[0]
    outer, inner, n_common_cycles = _contrast_geometry(_session_frame(), config)
    assert n_common_cycles == 3
    assert len(outer) == 3
    assert (outer["status"] == "ELIGIBLE_OUTER").all()
    assert len(inner) == 6
    assert (inner["status"] == "ELIGIBLE_INNER").all()
    assert set(outer["held_out_cycle"]) == {0, 1, 2}
    assert set(inner["held_out_cycle"]) == {0, 1, 2}
