"""Task event addressing for omission analysis."""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd

from src.analysis.contracts.constants import (
    CONDITION_LABEL_TO_NUMBERS,
    EVENT_CODE_FIXATION_CUE,
    EVENT_CODE_P1_STIMULUS,
)
from src.analysis.task_semantics import (
    run_all_validations,
    validate_no_code100_in_p1_events,
    validate_not_stimulus_number_1,
)

from .errors import BLOCKED_EVENTS_TABLE_MISSING, BLOCKED_NO_EVENTS, JnwbBlockedError
from .files import NWBFileRecord, _require_pynwb, session_key_from_record
from .schema import EventAddress

# Omission offsets from p1 onset (ms) for position-specific omission conditions
OMISSION_OFFSET_MS: dict[str, int | None] = {
    "AAAB": None,
    "AXAB": 1031,
    "AAXB": 2062,
    "AAAX": 3093,
    "BBBA": None,
    "BXBA": 1031,
    "BBXA": 2062,
    "BBBX": 3093,
    "RRRR": None,
    "RXRR": 1031,
    "RRXR": 2062,
    "RRRX": 3093,
}

DEFAULT_TASK = "omission_glo_passive"


def condition_numbers_for_labels(conditions: list[str]) -> list[int]:
    nums: list[int] = []
    for label in conditions:
        nums.extend(CONDITION_LABEL_TO_NUMBERS.get(label, []))
    return sorted(set(nums))


def omission_offset_ms(condition: str) -> int | None:
    return OMISSION_OFFSET_MS.get(condition)


def _find_omission_table(nwbfile, task: str | None) -> tuple[str, Any]:
    intervals = getattr(nwbfile, "intervals", None)
    if intervals is None:
        raise JnwbBlockedError("No intervals table in NWB", code=BLOCKED_EVENTS_TABLE_MISSING)

    if task:
        for name in intervals.keys():
            if task.lower() in name.lower():
                return str(name), intervals[name]

    for name in intervals.keys():
        if "omission" in name.lower():
            return str(name), intervals[name]

    raise JnwbBlockedError(
        f"No omission task table found (task={task!r})",
        code=BLOCKED_EVENTS_TABLE_MISSING,
    )


def _table_to_dataframe(table) -> pd.DataFrame:
    data = {}
    for col in table.colnames:
        try:
            data[col] = table[col][:]
        except Exception:
            data[col] = [None] * len(table)
    return pd.DataFrame(data)


def _resolve_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _filter_p1_events(
    df: pd.DataFrame,
    condition_numbers: list[int],
    correct_only: bool,
    validate: bool,
) -> pd.DataFrame:
    cond_col = _resolve_column(df, ["task_condition_number", "condition", "condition_number"])
    code_col = _resolve_column(df, ["codes", "code", "event_code"])
    if cond_col is None or code_col is None:
        raise JnwbBlockedError("Event table missing condition or code columns")

    out = df.copy()
    out[cond_col] = pd.to_numeric(out[cond_col], errors="coerce")
    out[code_col] = pd.to_numeric(out[code_col], errors="coerce")

    mask = out[cond_col].isin(condition_numbers)
    mask &= out[code_col] == EVENT_CODE_P1_STIMULUS

    if correct_only:
        correct_col = _resolve_column(out, ["correct", "is_correct", "trial_correct"])
        if correct_col is None:
            raise JnwbBlockedError("correct_only=True but no correct column found")
        out[correct_col] = pd.to_numeric(out[correct_col], errors="coerce")
        mask &= out[correct_col] == 1

    filtered = out[mask].copy()

    if validate and len(filtered) > 0:
        val_df = filtered.rename(columns={code_col: "codes"}).copy()
        if "stimulus_number" in val_df.columns:
            val_df["stimulus_number"] = pd.to_numeric(val_df["stimulus_number"], errors="coerce")
            stim2 = np.isclose(val_df["stimulus_number"], 2.0)
            if not stim2.all():
                bad = val_df.loc[~stim2, "stimulus_number"].unique().tolist()
                raise JnwbBlockedError(
                    f"Code 101 events must have stimulus_number == 2, found {bad}"
                )
        results = run_all_validations(val_df, context="jnwb.address_events p1")
        if not results["all_passed"]:
            raise JnwbBlockedError("; ".join(results["errors"]))

        code100 = validate_no_code100_in_p1_events(val_df)
        if not code100["passed"]:
            raise JnwbBlockedError(code100["errors"][0])

        stim1 = validate_not_stimulus_number_1(val_df)
        if not stim1["passed"]:
            raise JnwbBlockedError(stim1["errors"][0])

    return filtered


def _onset_column(df: pd.DataFrame) -> str:
    col = _resolve_column(df, ["start_time", "onset", "timestamp", "start"])
    if col is None:
        raise JnwbBlockedError("No onset column found in event table")
    return col


def _condition_label(cond_num: int) -> str | None:
    from src.analysis.contracts.constants import CONDITION_NUMBER_MAP

    return CONDITION_NUMBER_MAP.get(int(cond_num))


def address_events(
    nwbfiles: Iterable[NWBFileRecord],
    task: str | None = None,
    conditions: list[str] | None = None,
    condition_numbers: list[int] | None = None,
    anchor: str = "p1",
    correct: bool = True,
    sessions: list[str] | None = None,
    validate: bool = True,
) -> EventAddress:
    """Address task events without loading neural signals."""
    if anchor != "p1":
        raise NotImplementedError(f"Anchor {anchor!r} not yet implemented; use p1")

    file_list = list(nwbfiles)
    if conditions is None:
        conditions = ["AAAB", "AXAB", "AAXB", "AAAX"]

    cond_nums = condition_numbers if condition_numbers is not None else condition_numbers_for_labels(conditions)
    task_name = task or DEFAULT_TASK

    NWBHDF5IO = _require_pynwb()
    events_by_session: dict[str, list[dict]] = {}
    session_ids: list[str] = []
    warnings: list[str] = []
    input_sessions = set(sessions) if sessions else None

    for rec in file_list:
        skey = session_key_from_record(rec)
        if input_sessions is not None and skey not in input_sessions:
            continue

        io = NWBHDF5IO(rec.path, "r", load_namespaces=True)
        try:
            nwbfile = io.read()
            table_name, table = _find_omission_table(nwbfile, task_name)
            df = _table_to_dataframe(table)
            filtered = _filter_p1_events(df, cond_nums, correct_only=correct, validate=validate)
            onset_col = _onset_column(filtered)
            cond_col = _resolve_column(filtered, ["task_condition_number", "condition", "condition_number"])

            events: list[dict] = []
            for _, row in filtered.iterrows():
                cond_num = int(float(row[cond_col]))
                label = _condition_label(cond_num)
                if label is None or label not in conditions:
                    continue
                onset_s = float(row[onset_col])
                omission_ms = omission_offset_ms(label)
                events.append(
                    {
                        "trial_index": len(events),
                        "condition": label,
                        "condition_number": cond_num,
                        "onset_s": onset_s,
                        "onset_ms": onset_s * 1000.0,
                        "anchor": anchor,
                        "code": int(EVENT_CODE_P1_STIMULUS),
                        "omission_offset_ms": omission_ms,
                        "table_name": table_name,
                        "nwb_path": rec.path,
                    }
                )

            if events:
                events_by_session[skey] = events
                session_ids.append(skey)
            else:
                warnings.append(f"No p1 events for session {skey}")

        finally:
            io.close()

    if not events_by_session:
        raise JnwbBlockedError(
            f"No events found for conditions={conditions}",
            code=BLOCKED_NO_EVENTS,
        )

    return EventAddress(
        task=task_name,
        conditions=conditions,
        condition_numbers=cond_nums,
        anchor=anchor,
        sessions=session_ids,
        events_by_session=events_by_session,
        time_unit="s",
        p1_code=EVENT_CODE_P1_STIMULUS,
        correct_only=correct,
        warnings=warnings,
    )
