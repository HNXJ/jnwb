"""Tests for jnwb task/event addressing."""

from __future__ import annotations

import pandas as pd
import pytest

from src.analysis.contracts.constants import (
    EVENT_CODE_FIXATION_CUE,
    EVENT_CODE_P1_STIMULUS,
)
from src.jnwb.task import (
    OMISSION_OFFSET_MS,
    _filter_p1_events,
    condition_numbers_for_labels,
    omission_offset_ms,
)


def test_afamily_omission_offsets():
    assert omission_offset_ms("AXAB") == 1031
    assert omission_offset_ms("AAXB") == 2062
    assert omission_offset_ms("AAAX") == 3093
    assert OMISSION_OFFSET_MS["AXAB"] == 1031


def test_condition_numbers_for_afamily():
    nums = condition_numbers_for_labels(["AAAB", "AXAB", "AAXB", "AAAX"])
    assert nums == [1, 2, 3, 4, 5]


def test_condition_numbers_for_rfamily():
    from src.analysis.contracts.constants import CONDITION_NUMBER_MAP

    nums = condition_numbers_for_labels(["RRRR", "RXRR", "RRXR", "RRRX"])
    assert 11 in nums and 26 in nums
    assert 27 in nums and 34 in nums
    assert 35 in nums and 41 in nums
    assert 50 in nums
    assert CONDITION_NUMBER_MAP[50] == "RRRX"
    assert CONDITION_NUMBER_MAP[35] == "RRXR"


def test_filter_p1_events_uses_code101():
    df = pd.DataFrame(
        {
            "task_condition_number": [4, 4, 4],
            "codes": [EVENT_CODE_P1_STIMULUS, EVENT_CODE_FIXATION_CUE, EVENT_CODE_P1_STIMULUS],
            "correct": [1, 1, 1],
            "stimulus_number": [2, 1, 2],
            "start_time": [1.0, 2.0, 3.0],
        }
    )
    out = _filter_p1_events(df, [4], correct_only=True, validate=False)
    assert len(out) == 2
    assert (out["codes"] == EVENT_CODE_P1_STIMULUS).all()


def test_filter_p1_rejects_code100_with_validate():
    df = pd.DataFrame(
        {
            "task_condition_number": [4],
            "codes": [EVENT_CODE_FIXATION_CUE],
            "correct": [1],
            "stimulus_number": [1],
            "start_time": [1.0],
        }
    )
    out = _filter_p1_events(df, [4], correct_only=True, validate=False)
    assert len(out) == 0


def test_filter_p1_rejects_stimulus_number_1_with_validate():
    df = pd.DataFrame(
        {
            "task_condition_number": [4],
            "codes": [EVENT_CODE_P1_STIMULUS],
            "correct": [1],
            "stimulus_number": [1],
            "start_time": [1.0],
        }
    )
    with pytest.raises(Exception):
        _filter_p1_events(df, [4], correct_only=True, validate=True)


@pytest.mark.skipif(
    not __import__("pathlib").Path(r"D:/analysis/nwb").exists(),
    reason="NWB root unavailable",
)
def test_address_events_live_afamily():
    import omission

    files = jnwb.list_nwb_files(r"D:/analysis/nwb")
    ev = jnwb.address_events(
        files,
        task="omission_glo_passive",
        conditions=["AAAB", "AXAB", "AAXB", "AAAX"],
        anchor="p1",
        correct=True,
    )
    assert ev.p1_code == EVENT_CODE_P1_STIMULUS
    assert len(ev.sessions) > 0
    for events in ev.events_by_session.values():
        for e in events:
            assert e["code"] == EVENT_CODE_P1_STIMULUS
            assert e["code"] != EVENT_CODE_FIXATION_CUE
