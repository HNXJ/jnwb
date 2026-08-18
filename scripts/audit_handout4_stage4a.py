#!/usr/bin/env python3
"""Stage 4A design/corpus audit for Handout 4 WHAT x WHEN tasks.

This is an inventory and identifiability pass only.  It reads NWB metadata and event tables
through h5py, applies the canonical trial ontology, derives grouped fold geometry, and writes
receipts.  It does not materialize neural tensors, fit estimators, or generate permutation draws.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "context"
    / "figures"
    / "fig04_omission_identity_decoding"
    / "handout_4_stage4a"
)
READINESS = REPO_ROOT / "artifacts" / "data" / "session_readiness.csv"
CATALOG = REPO_ROOT / "artifacts" / "data" / "nwb_catalog.json"

sys.path.insert(0, str(REPO_ROOT))
from jnwb.omission_identity import detect_trial_cycles  # noqa: E402
from jnwb.paths import nwb_dir as canonical_nwb_dir  # noqa: E402
from jnwb.paths import tfr_dir as canonical_tfr_dir  # noqa: E402
from jnwb.sequence_layout import EPOCH_ONSETS_MS, channel_slice_for_area, parse_probe_areas  # noqa: E402
from jnwb.session import condition_map_for_stem  # noqa: E402
from jnwb.trial_ontology import CONDITION_ONTOLOGY  # noqa: E402


MIN_GROUPS = 3
MIN_VALID_OUTER = 2
MIN_VALID_INNER = 2
SIGNALS = ("SUA_SPK", "MUAe", "LFP")
OMISSION_SLOTS = ("p2", "p3", "p4")
FROZEN_W1_PRIMARY_SESSIONS = frozenset(
    {
        "sub-C31o_ses-230823_rec",
        "sub-V182o_ses-260702",
        "sub-V182o_ses-260706",
        "sub-V182o_ses-260708",
        "sub-V198o_ses-230714_rec",
    }
)


def _scalar(value: Any) -> Any:
    if isinstance(value, (bytes, np.bytes_)):
        return value.decode("utf-8", "replace")
    if isinstance(value, np.ndarray) and value.shape == ():
        return _scalar(value.item())
    return value


def _float(value: Any) -> float:
    value = _scalar(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


from jnwb.paths import sha256_file as _sha256


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "1.0", "true", "yes"}


def _int_or_zero(value: Any) -> int:
    number = _float(value)
    return int(number) if np.isfinite(number) else 0


def _area_inventory(f: h5py.File) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return electrode and unit inventories using canonical probe half-splitting."""
    elec = f.get("general/extracellular_ephys/electrodes")
    if elec is None or "id" not in elec or "location" not in elec:
        electrodes = pd.DataFrame(columns=["channel_id", "probe", "local_idx", "area"])
    else:
        ids = [_float(v) for v in elec["id"][:]]
        locations = [str(_scalar(v)).strip() for v in elec["location"][:]]
        if "group_name" in elec:
            probes = [str(_scalar(v)) for v in elec["group_name"][:]]
        elif "probe" in elec:
            probes = [str(_scalar(v)) for v in elec["probe"][:]]
        else:
            probes = ["unknown"] * len(ids)
        counters: Counter[str] = Counter()
        rows = []
        for channel_id, location, probe in zip(ids, locations, probes):
            local_idx = counters[probe]
            counters[probe] += 1
            areas = parse_probe_areas(location)
            area = None
            for candidate in areas:
                channel_slice = channel_slice_for_area(areas, candidate, n_channels=128)
                if channel_slice is not None and channel_slice.start <= local_idx < channel_slice.stop:
                    area = candidate
                    break
            if area is None and areas:
                area = areas[min(local_idx * len(areas) // 128, len(areas) - 1)]
            rows.append(
                {
                    "channel_id": int(channel_id) if np.isfinite(channel_id) else -1,
                    "probe": probe,
                    "local_idx": local_idx,
                    "location_raw": location,
                    "area": area,
                }
            )
        electrodes = pd.DataFrame(rows)

    units_group = f.get("units")
    unit_rows = []
    if units_group is not None and "id" in units_group:
        peak = units_group["peak_channel_id"][:] if "peak_channel_id" in units_group else [np.nan] * len(units_group["id"])
        quality = units_group["quality"][:] if "quality" in units_group else [""] * len(units_group["id"])
        channel_area = dict(zip(electrodes["channel_id"], electrodes["area"])) if not electrodes.empty else {}
        for unit_id, peak_channel, unit_quality in zip(
            units_group["id"][:], peak, quality
        ):
            peak_i = _float(peak_channel)
            quality_s = str(_scalar(unit_quality)).strip()
            unit_rows.append(
                {
                    "unit_id": int(_float(unit_id)),
                    "peak_channel_id": int(peak_i) if np.isfinite(peak_i) else -1,
                    "area": channel_area.get(int(peak_i)) if np.isfinite(peak_i) else None,
                    "quality": quality_s,
                }
            )
    units = pd.DataFrame(unit_rows)
    return electrodes, units


def _data_dataset(group: h5py.Group) -> tuple[str | None, h5py.Dataset | None]:
    candidates: list[tuple[str, h5py.Dataset]] = []

    def visit(name: str, obj: h5py.Dataset | h5py.Group) -> None:
        if isinstance(obj, h5py.Dataset) and name.rsplit("/", 1)[-1] == "data":
            candidates.append((name, obj))

    group.visititems(visit)
    if not candidates:
        return None, None
    candidates.sort(key=lambda item: (len(item[0].split("/")), item[0]))
    return candidates[0]


def _timestamp_dataset(group: h5py.Group) -> tuple[str | None, h5py.Dataset | None]:
    candidates: list[tuple[str, h5py.Dataset]] = []

    def visit(name: str, obj: h5py.Dataset | h5py.Group) -> None:
        if isinstance(obj, h5py.Dataset) and name.rsplit("/", 1)[-1] == "timestamps":
            candidates.append((name, obj))

    group.visititems(visit)
    candidates.sort(key=lambda item: (len(item[0].split("/")), item[0]))
    return candidates[0] if candidates else (None, None)


def _rate(group: h5py.Group, data: h5py.Dataset) -> float:
    objects: list[h5py.Group | h5py.Dataset] = [data, group]
    for name in group:
        objects.append(group[name])
    for obj in objects:
        for key in ("rate", "sampling_rate", "sample_rate"):
            if key in obj.attrs:
                value = _float(obj.attrs[key])
                if np.isfinite(value):
                    return value
    return float("nan")


def _signal_inventory(
    f: h5py.File, electrodes: pd.DataFrame, units: pd.DataFrame
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    acq = f.get("acquisition")
    signals: list[dict[str, Any]] = []
    areas: list[dict[str, Any]] = []
    if acq is None:
        return signals, areas
    channel_area = dict(zip(electrodes["channel_id"], electrodes["area"])) if not electrodes.empty else {}
    for key in sorted(acq.keys()):
        if key.endswith("_lfp"):
            signal = "LFP"
        elif key.endswith("_muae"):
            signal = "MUAe"
        else:
            continue
        group = acq[key]
        data_path, data = _data_dataset(group)
        if data is None or len(data.shape) != 2:
            signals.append(
                {
                    "signal": signal,
                    "acquisition_key": key,
                    "data_path": data_path or "",
                    "status": "missing_or_non_2d_data",
                    "n_samples": 0,
                    "n_channels": 0,
                    "sample_rate_hz": float("nan"),
                    "timestamp_path": "",
                }
            )
            continue
        timestamp_path, _timestamps = _timestamp_dataset(group)
        starting_time_s = float("nan")
        starting_time = group.get("starting_time")
        if isinstance(starting_time, h5py.Dataset) and starting_time.shape == ():
            starting_time_s = _float(starting_time[()])
        n_samples, n_channels = map(int, data.shape)
        signals.append(
            {
                "signal": signal,
                "acquisition_key": key,
                "data_path": data_path or "",
                "status": "metadata_available",
                "n_samples": n_samples,
                "n_channels": n_channels,
                "sample_rate_hz": _rate(group, data),
                "timestamp_path": timestamp_path or "",
                "starting_time_s": starting_time_s,
            }
        )
        electrode_ids = []
        found: list[tuple[str, h5py.Dataset]] = []

        def visit(name: str, obj: h5py.Dataset | h5py.Group) -> None:
            if isinstance(obj, h5py.Dataset) and name.rsplit("/", 1)[-1] == "electrodes":
                found.append((name, obj))

        group.visititems(visit)
        if found:
            electrode_ids = [_float(v) for v in found[0][1][:]]
        probe_match = re.search(r"probe_(\d+)_", key)
        probe_name = (
            f"probe{chr(ord('A') + int(probe_match.group(1)))}"
            if probe_match
            else ""
        )
        probe_area = {}
        if not electrodes.empty and "probe" in electrodes:
            probe_rows = electrodes[electrodes["probe"] == probe_name]
            probe_area = dict(zip(probe_rows["local_idx"], probe_rows["area"]))
        mapped = [probe_area.get(int(v)) for v in electrode_ids if np.isfinite(v)]
        for area, count in Counter(mapped).items():
            if area:
                areas.append(
                    {
                        "signal": signal,
                        "acquisition_key": key,
                        "area": area,
                        "n_channels": int(count),
                        "status": "metadata_available",
                    }
                )
    for area, count in units["area"].dropna().value_counts().items() if not units.empty and "area" in units else []:
        areas.append(
            {
                "signal": "SUA_SPK",
                "acquisition_key": "units",
                "area": area,
                "n_units": int(count),
                "status": "metadata_available",
            }
        )
    return signals, areas


def _events(f: h5py.File, stem: str) -> tuple[pd.DataFrame, list[str]]:
    reasons: list[str] = []
    group = f.get("intervals/omission_glo_passive")
    required = ("start_time", "trial_num", "stimulus_number", "task_condition_number")
    if group is None:
        return pd.DataFrame(), ["MISSING_OMISSION_INTERVALS"]
    missing = [key for key in required if key not in group]
    if missing:
        return pd.DataFrame(), [f"MISSING_EVENT_COLUMN_{key}" for key in missing]
    columns = {
        key: [_float(value) for value in group[key][:]]
        for key in required
    }
    if "correct" in group:
        columns["correct"] = [_float(value) for value in group["correct"][:]]
    else:
        reasons.append("MISSING_CORRECT_COLUMN")
        columns["correct"] = [float("nan")] * len(columns["start_time"])
    frame = pd.DataFrame(columns)
    frame = frame[
        np.isclose(frame["stimulus_number"], 2.0, equal_nan=False)
        & np.isfinite(frame["start_time"])
        & np.isfinite(frame["trial_num"])
        & np.isfinite(frame["task_condition_number"])
        & frame["correct"].eq(1.0)
    ].copy()
    condition_map = condition_map_for_stem(stem)
    inverse: dict[int, str] = {}
    for condition, codes in condition_map.items():
        for code in codes:
            inverse[int(code)] = condition
    frame["condition"] = frame["task_condition_number"].round().astype(int).map(inverse)
    frame = frame.dropna(subset=["condition"]).copy()
    frame["trial_num"] = frame["trial_num"].round().astype(int)
    frame = frame.drop_duplicates(["trial_num", "condition"], keep="first")
    onto = frame["condition"].map(CONDITION_ONTOLOGY)
    frame["sequence_family"] = onto.map(lambda x: x["sequence_family"])
    frame["omission_position"] = onto.map(lambda x: x["omission_position"])
    frame["expected_identity"] = onto.map(lambda x: x["expected_identity"])
    frame["preceding_identity"] = onto.map(lambda x: x["preceding_identity"])
    frame = frame[frame["omission_position"].isin(OMISSION_SLOTS)].copy()
    frame["local_omission_onset_ms"] = frame["omission_position"].map(
        lambda slot: EPOCH_ONSETS_MS[slot]
    )
    frame["local_omission_onset_s"] = (
        frame["start_time"] + frame["local_omission_onset_ms"] / 1000.0
    )
    frame["session"] = stem
    frame = frame.sort_values(["start_time", "trial_num", "condition"]).reset_index(drop=True)
    if frame.empty:
        return frame, reasons + ["NO_CORRECT_OMISSION_P1_ROWS"]
    frame["common_cycle"] = detect_trial_cycles(
        frame[["start_time"]].reset_index(drop=True)
    )
    frame["slot_cycle"] = -1
    for slot, index in frame.groupby("omission_position", sort=True).groups.items():
        ordered = frame.loc[index].sort_values(["start_time", "trial_num"])
        frame.loc[ordered.index, "slot_cycle"] = detect_trial_cycles(
            ordered[["start_time"]].reset_index(drop=True)
        )
    frame["ab_slot_cycle"] = -1
    for slot, group in frame[frame["sequence_family"].isin(["A", "B"])].groupby(
        "omission_position", sort=True
    ):
        ordered = group.sort_values(["start_time", "trial_num"])
        frame.loc[ordered.index, "ab_slot_cycle"] = detect_trial_cycles(
            ordered[["start_time"]].reset_index(drop=True)
        )
    valid_ab_slots = [
        slot
        for slot in OMISSION_SLOTS
        if frame[
            frame["sequence_family"].isin(["A", "B"])
            & frame["omission_position"].eq(slot)
        ]["ab_slot_cycle"].nunique()
        >= 2
    ]
    frame["frozen_common_cycle"] = -1
    frozen_rows = frame[
        frame["sequence_family"].isin(["A", "B"])
        & frame["omission_position"].isin(valid_ab_slots)
    ].copy()
    if not frozen_rows.empty:
        ordered = frozen_rows.sort_values(["start_time", "trial_num"])
        frame.loc[ordered.index, "frozen_common_cycle"] = detect_trial_cycles(
            ordered[["start_time"]].reset_index(drop=True)
        )
    frame["ab_common_cycle"] = -1
    ab_rows = frame[frame["sequence_family"].isin(["A", "B"])].copy()
    if not ab_rows.empty:
        ordered = ab_rows.sort_values(["start_time", "trial_num"])
        frame.loc[ordered.index, "ab_common_cycle"] = detect_trial_cycles(
            ordered[["start_time"]].reset_index(drop=True)
        )
    frame["trial_key"] = frame.apply(
        lambda row: f"{stem}|trial={int(row['trial_num'])}|condition={row['condition']}",
        axis=1,
    )
    return frame, reasons


def _target_values(frame: pd.DataFrame, target: str) -> pd.Series:
    if target == "context":
        return frame["sequence_family"].map(
            {"A": "predictable", "B": "predictable", "R": "random"}
        )
    if target == "family":
        return frame["sequence_family"]
    if target == "position":
        return frame["omission_position"]
    return frame[target]


def task_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = [
        {
            "task": "W1_reversal_primary",
            "family": "A_B_frozen_eligibility",
            "target": "expected_identity",
            "alternate_target": "preceding_identity",
            "train_slots": ["p2", "p3"],
            "test_slots": ["p4"],
            "train_families": ["A", "B"],
            "test_families": ["A", "B"],
            "group_col": "frozen_common_cycle",
            "geometry": "cross_position_reversal",
            "role": "confirmatory",
            "frozen_primary": True,
        },
        {
            "task": "W1_reversal_candidate_full_corpus",
            "family": "A_B_common_cycle",
            "target": "expected_identity",
            "alternate_target": "preceding_identity",
            "train_slots": ["p2", "p3"],
            "test_slots": ["p4"],
            "train_families": ["A", "B"],
            "test_families": ["A", "B"],
            "group_col": "ab_common_cycle",
            "geometry": "cross_position_reversal",
            "role": "exploratory_design_candidate",
        }
    ]
    for task_family in ("context", "family"):
        for slot in OMISSION_SLOTS:
            specs.append(
                {
                    "task": f"W2_context_{slot}" if task_family == "context" else f"W3_family_{slot}",
                    "family": "A_B_R",
                    "target": task_family,
                    "train_slots": [slot],
                    "test_slots": [slot],
                    "train_families": ["A", "B", "R"],
                    "test_families": ["A", "B", "R"],
                    "group_col": "common_cycle",
                    "geometry": "within_position",
                    "role": "confirmatory" if task_family == "context" else "exploratory",
                }
            )
    specs.append(
        {
            "task": "T1_position_all_families",
            "family": "A_B_R",
            "target": "position",
            "train_slots": list(OMISSION_SLOTS),
            "test_slots": list(OMISSION_SLOTS),
            "train_families": ["A", "B", "R"],
            "test_families": ["A", "B", "R"],
            "group_col": "common_cycle",
            "geometry": "within_position",
            "role": "confirmatory",
        }
    )
    for family, label in (("A", "A_only"), ("B", "B_only"), ("R", "R_only")):
        specs.append(
            {
                "task": f"T1_{label}",
                "family": family,
                "target": "position",
                "train_slots": list(OMISSION_SLOTS),
                "test_slots": list(OMISSION_SLOTS),
                "train_families": [family],
                "test_families": [family],
                "group_col": "common_cycle",
                "geometry": "within_position",
                "role": "confirmatory",
            }
        )
    for train_family, test_family, label in (
        ("A", "B", "A_to_B"),
        ("B", "A", "B_to_A"),
        ("A_B", "R", "predictable_to_random"),
    ):
        train_families = ["A", "B"] if train_family == "A_B" else [train_family]
        specs.append(
            {
                "task": f"T1d_cross_family_{label}",
                "family": f"{train_family}_to_{test_family}",
                "target": "position",
                "train_slots": list(OMISSION_SLOTS),
                "test_slots": list(OMISSION_SLOTS),
                "train_families": train_families,
                "test_families": [test_family],
                "group_col": "common_cycle",
                "geometry": "cross_family_generalization",
                "role": "exploratory",
            }
        )
    return specs


def _class_counts(frame: pd.DataFrame, target: str) -> dict[str, int]:
    values = _target_values(frame, target).dropna().astype(str)
    return {key: int(values.value_counts().get(key, 0)) for key in sorted(values.unique())}


def _both_classes(frame: pd.DataFrame, target: str) -> bool:
    return _target_values(frame, target).dropna().nunique() >= 2


def _geometry(frame: pd.DataFrame, spec: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    work_frame = frame
    if spec.get("frozen_w1"):
        work_frame = frame[frame["frozen_common_cycle"] >= 0].copy()
    selected = work_frame[
        work_frame["omission_position"].isin(spec["train_slots"])
        & work_frame["sequence_family"].isin(spec["train_families"])
    ].copy()
    test_selection = work_frame[
        work_frame["omission_position"].isin(spec["test_slots"])
        & work_frame["sequence_family"].isin(spec["test_families"])
    ].copy()
    group_col = spec["group_col"]
    group_values = sorted(
        set(selected[group_col].astype(int).unique())
        & set(test_selection[group_col].astype(int).unique())
    )
    reasons: list[str] = []
    if selected.empty:
        reasons.append("NO_TRAIN_TRIALS")
    if test_selection.empty:
        reasons.append("NO_TEST_TRIALS")
    if len(group_values) < MIN_GROUPS:
        reasons.append(f"COMMON_GROUPS_LT_{MIN_GROUPS}")
    outer_rows: list[dict[str, Any]] = []
    valid_outer = 0
    valid_inner = 0
    for fold, held_out in enumerate(group_values):
        train = selected[selected[group_col] != held_out]
        test = test_selection[test_selection[group_col] == held_out]
        fold_reasons: list[str] = []
        if not _both_classes(train, spec["target"]):
            fold_reasons.append("TRAIN_MISSING_CLASS")
        if not _both_classes(test, spec["target"]):
            fold_reasons.append("TEST_MISSING_CLASS")
        outer_valid = not fold_reasons and len(group_values) >= MIN_GROUPS
        if outer_valid:
            valid_outer += 1
            train_groups = sorted(train[group_col].astype(int).unique())
            for validation_group in train_groups:
                inner_train = train[train[group_col] != validation_group]
                inner_validation = train[train[group_col] == validation_group]
                if _both_classes(inner_train, spec["target"]) and _both_classes(
                    inner_validation, spec["target"]
                ):
                    valid_inner += 1
        outer_rows.append(
            {
                "task": spec["task"],
                "geometry": spec["geometry"],
                "group_col": group_col,
                "outer_fold": fold,
                "held_out_group": int(held_out),
                "n_train_trials": int(len(train)),
                "n_test_trials": int(len(test)),
                "train_class_counts": _json(_class_counts(train, spec["target"])),
                "test_class_counts": _json(_class_counts(test, spec["target"])),
                "status": "ELIGIBLE_OUTER" if outer_valid else "INELIGIBLE_DESIGN",
                "reason": ";".join(fold_reasons),
            }
        )
    if valid_outer < MIN_VALID_OUTER:
        reasons.append(f"VALID_OUTER_FOLDS_LT_{MIN_VALID_OUTER}")
    if valid_inner < MIN_VALID_INNER:
        reasons.append(f"VALID_INNER_PARTITIONS_LT_{MIN_VALID_INNER}")
    row = {
        "task": spec["task"],
        "role": spec["role"],
        "geometry": spec["geometry"],
        "target": spec["target"],
        "alternate_target": spec.get("alternate_target", ""),
        "family_scope": spec["family"],
        "train_slots": "+".join(spec["train_slots"]),
        "test_slots": "+".join(spec["test_slots"]),
        "train_families": "+".join(spec["train_families"]),
        "test_families": "+".join(spec["test_families"]),
        "group_col": group_col,
        "eligible_trials": int(len(selected) + len(test_selection))
        if spec["geometry"] == "cross_position_reversal"
        else int(len(selected)),
        "train_trials": int(len(selected)),
        "test_trials": int(len(test_selection)),
        "class_counts": _json(_class_counts(selected, spec["target"])),
        "test_class_counts": _json(_class_counts(test_selection, spec["target"])),
        "candidate_groups": int(len(group_values)),
        "valid_outer_folds": int(valid_outer),
        "valid_inner_partitions": int(valid_inner),
        "identifiable": not reasons,
        "exclusion_reason": ";".join(reasons) if reasons else "",
    }
    return row, outer_rows


def _tfr_inventory(tfr_dir: Path, session_prefix: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    pattern = re.compile(
        rf"^{re.escape(session_prefix)}-[A-Z]-([^-]+)-([A-Z0-9]+)\.npy$"
    )
    for path in tfr_dir.glob(f"{session_prefix}-*.npy"):
        match = pattern.match(path.name)
        if not match:
            continue
        area, condition = match.groups()
        result.setdefault(area, {"n_files": 0, "conditions": set()})
        result[area]["n_files"] += 1
        result[area]["conditions"].add(condition)
    for record in result.values():
        record["conditions"] = sorted(record["conditions"])
        record["all_12_conditions"] = len(record["conditions"]) == 12
    return result


def run(
    *,
    catalog_path: Path = CATALOG,
    readiness_path: Path = READINESS,
    output_dir: Path = DEFAULT_OUTPUT,
    nwb_dir: Path | None = None,
    tfr_dir: Path | None = None,
) -> dict[str, Any]:
    catalog_path = catalog_path.resolve()
    readiness_path = readiness_path.resolve()
    output_dir = output_dir.resolve()
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    readiness = pd.read_csv(readiness_path)
    readiness_by_stem = readiness.set_index("stem").to_dict("index")
    catalog_sessions = catalog["sessions"]
    if nwb_dir is None:
        nwb_dir = canonical_nwb_dir().resolve()
    if tfr_dir is None:
        tfr_dir = canonical_tfr_dir().resolve()
    nwb_dir = nwb_dir.resolve()
    tfr_dir = tfr_dir.resolve()

    session_rows: list[dict[str, Any]] = []
    trial_frames: dict[str, pd.DataFrame] = {}
    geometry_rows: list[dict[str, Any]] = []
    fold_rows: list[dict[str, Any]] = []
    signal_area_rows: list[dict[str, Any]] = []
    task_list = task_specs()
    label_proof_rows: list[dict[str, Any]] = []

    for session_meta in catalog_sessions:
        stem = str(session_meta["stem"])
        nwb_path = Path(str(session_meta["path"]))
        if not nwb_path.exists():
            nwb_path = nwb_dir / Path(str(session_meta["filename"])).name
        ready = readiness_by_stem.get(stem, {})
        session_status: list[str] = []
        if not nwb_path.exists():
            session_rows.append(
                {
                    "session": stem,
                    "subject": session_meta.get("subject"),
                    "status": "excluded",
                    "exclusion_reason": "NWB_MISSING",
                }
            )
            continue
        try:
            with h5py.File(nwb_path, "r") as handle:
                electrodes, units = _area_inventory(handle)
                signals, signal_areas = _signal_inventory(handle, electrodes, units)
                trial_frame, event_reasons = _events(handle, stem)
        except Exception as exc:
            session_rows.append(
                {
                    "session": stem,
                    "subject": session_meta.get("subject"),
                    "status": "excluded",
                    "exclusion_reason": f"H5_AUDIT_ERROR:{type(exc).__name__}:{exc}",
                }
            )
            continue
        if event_reasons:
            session_status.extend(event_reasons)
        trial_frame["subject"] = session_meta.get("subject")
        trial_frames[stem] = trial_frame
        tfr = _tfr_inventory(tfr_dir, str(session_meta.get("session_prefix", stem)))
        live_tfr_n_files = int(sum(record["n_files"] for record in tfr.values()))
        readiness_tfr_n_files = _int_or_zero(ready.get("tfr_n_files", 0))
        session_rows.append(
            {
                "session": stem,
                "subject": session_meta.get("subject"),
                "status": "audited",
                "n_omission_trials": int(len(trial_frame)),
                "n_common_cycles": int(trial_frame["common_cycle"].nunique())
                if not trial_frame.empty
                else 0,
                "n_sua_units": int(len(units)),
                "n_sua_areas": int(units["area"].nunique())
                if not units.empty and "area" in units
                else 0,
                "has_lfp": any(row["signal"] == "LFP" and row["status"] == "metadata_available" for row in signals),
                "has_muae": any(row["signal"] == "MUAe" and row["status"] == "metadata_available" for row in signals),
                "n_lfp_acquisitions": int(sum(row["signal"] == "LFP" for row in signals)),
                "n_muae_acquisitions": int(sum(row["signal"] == "MUAe" for row in signals)),
                "sidecar_ok": bool(ready.get("sidecar_ok", False)),
                "suite_tfr_ready": bool(ready.get("suite_tfr_ready", False)),
                "tfr_n_files": readiness_tfr_n_files,
                "tfr_n_files_live": live_tfr_n_files,
                "tfr_readiness_discrepancy": readiness_tfr_n_files != live_tfr_n_files,
                "event_audit_reasons": ";".join(session_status),
            }
        )
        signal_area_rows.extend(
            {
                "session": stem,
                "subject": session_meta.get("subject"),
                **row,
                "n_units": row.get("n_units", 0),
                "tfr_n_files": int(tfr.get(row["area"], {}).get("n_files", 0)),
                "tfr_all_12_conditions": bool(
                    tfr.get(row["area"], {}).get("all_12_conditions", False)
                ),
                "sidecar_ok": bool(ready.get("sidecar_ok", False)),
                "suite_tfr_ready": bool(ready.get("suite_tfr_ready", False)),
            }
            for row in signal_areas
        )
        for slot, group in trial_frame.groupby("omission_position", sort=True):
            proof = (
                group[group["sequence_family"].isin(["A", "B"])]
                .groupby(["preceding_identity", "expected_identity"], dropna=False)
                .size()
                .reset_index(name="n_trials")
            )
            for record in proof.to_dict("records"):
                label_proof_rows.append(
                    {
                        "session": stem,
                        "subject": session_meta.get("subject"),
                        "slot": slot,
                        "preceding_identity": record["preceding_identity"],
                        "expected_identity": record["expected_identity"],
                        "relation": "equal"
                        if record["preceding_identity"] == record["expected_identity"]
                        else "opposite",
                        "n_trials": int(record["n_trials"]),
                    }
                )
            random_count = int((group["sequence_family"] == "R").sum())
            if random_count:
                label_proof_rows.append(
                    {
                        "session": stem,
                        "subject": session_meta.get("subject"),
                        "slot": slot,
                        "preceding_identity": "",
                        "expected_identity": "",
                        "relation": "random_family_not_identity",
                        "n_trials": random_count,
                    }
                )
        for spec in task_list:
            geometry, folds = _geometry(trial_frame, spec)
            if spec.get("frozen_primary"):
                candidate_status = bool(geometry["identifiable"])
                geometry["candidate_geometry_identifiable"] = candidate_status
                geometry["eligibility_source"] = (
                    "frozen_milestone_1b_primary_corpus"
                )
                if stem not in FROZEN_W1_PRIMARY_SESSIONS:
                    geometry["identifiable"] = False
                    geometry["exclusion_reason"] = "FROZEN_PRIMARY_CORPUS_EXCLUDED"
                else:
                    geometry["identifiable"] = candidate_status
            geometry.update({"session": stem, "subject": session_meta.get("subject")})
            geometry_rows.append(geometry)
            fold_rows.extend(
                {
                    "session": stem,
                    "subject": session_meta.get("subject"),
                    **fold,
                }
                for fold in folds
            )

    geometry_df = pd.DataFrame(geometry_rows)
    signal_area_df = pd.DataFrame(signal_area_rows)
    corpus_rows: list[dict[str, Any]] = []
    for session in session_rows:
        stem = session["session"]
        session_areas = signal_area_df[signal_area_df["session"] == stem]
        session_geometry = geometry_df[geometry_df["session"] == stem]
        for signal in SIGNALS:
            signal_areas = session_areas[session_areas["signal"] == signal]
            if signal_areas.empty:
                area_records = [{"area": "__NO_AREA__"}]
            else:
                area_records = signal_areas.to_dict("records")
            for area_record in area_records:
                for _, geom in session_geometry.iterrows():
                    reasons = []
                    if area_record["area"] == "__NO_AREA__":
                        reasons.append("SIGNAL_AREA_UNAVAILABLE")
                    if not bool(geom.get("identifiable", False)):
                        reasons.append(str(geom.get("exclusion_reason", "TASK_GEOMETRY_INELIGIBLE")))
                    if signal == "MUAe":
                        reasons.append("MUAe_LOADER_NOT_IMPLEMENTED")
                    if signal == "LFP" and area_record.get("status") != "metadata_available":
                        reasons.append("LFP_METADATA_UNAVAILABLE")
                    corpus_rows.append(
                        {
                            "signal": signal,
                            "task": geom["task"],
                            "subject": session.get("subject"),
                            "session": stem,
                            "area": area_record["area"],
                            "eligible_trials": int(geom["eligible_trials"]),
                            "class_counts": geom["class_counts"],
                            "candidate_groups": int(geom["candidate_groups"]),
                            "outer_folds": int(geom["valid_outer_folds"]),
                            "inner_partitions": int(geom["valid_inner_partitions"]),
                            "n_units": _int_or_zero(area_record.get("n_units", 0)),
                            "n_channels": _int_or_zero(area_record.get("n_channels", 0)),
                            "tfr_n_files": _int_or_zero(area_record.get("tfr_n_files", 0)),
                            "tfr_all_12_conditions": bool(area_record.get("tfr_all_12_conditions", False)),
                            "design_status": "ELIGIBLE_DESIGN" if not reasons else "EXCLUDED_OR_GAP",
                            "exclusion_reason": ";".join(reasons),
                            "training_authorized": False,
                        }
                    )
    corpus_df = pd.DataFrame(corpus_rows)
    geometry_df = geometry_df.sort_values(["session", "task"]).reset_index(drop=True)
    signal_area_df = signal_area_df.sort_values(["session", "signal", "area"]).reset_index(drop=True)
    session_df = pd.DataFrame(session_rows).sort_values("session").reset_index(drop=True)
    fold_df = pd.DataFrame(fold_rows)
    proof_df = pd.DataFrame(label_proof_rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "session_inventory": output_dir / "session_inventory.csv",
        "signal_area_inventory": output_dir / "signal_area_inventory.csv",
        "task_session_geometry": output_dir / "task_session_geometry.csv",
        "fold_assignments": output_dir / "fold_assignments.csv",
        "corpus_table": output_dir / "corpus_table.csv",
        "label_nuisance_proof": output_dir / "label_nuisance_proof.csv",
        "task_support_summary": output_dir / "task_support_summary.csv",
        "local_alignment_contract": output_dir / "local_alignment_contract.json",
    }
    session_df.to_csv(outputs["session_inventory"], index=False)
    signal_area_df.to_csv(outputs["signal_area_inventory"], index=False)
    geometry_df.to_csv(outputs["task_session_geometry"], index=False)
    fold_df.to_csv(outputs["fold_assignments"], index=False)
    corpus_df.to_csv(outputs["corpus_table"], index=False)
    proof_df.to_csv(outputs["label_nuisance_proof"], index=False)

    support_rows = []
    for signal in SIGNALS:
        for task in [spec["task"] for spec in task_list]:
            rows = corpus_df[(corpus_df["signal"] == signal) & (corpus_df["task"] == task)]
            supported = rows[rows["design_status"] == "ELIGIBLE_DESIGN"]
            support_rows.append(
                {
                    "signal": signal,
                    "task": task,
                    "session_area_rows": int(len(rows)),
                    "eligible_session_area_rows": int(len(supported)),
                    "sessions_with_support": int(supported["session"].nunique()),
                    "subjects_with_support": int(supported["subject"].nunique()),
                    "note": "design support only; no feature extraction or training",
                }
            )
    support_df = pd.DataFrame(support_rows)
    support_df.to_csv(outputs["task_support_summary"], index=False)
    outputs["local_alignment_contract"].write_text(
        json.dumps(
            {
                "origin": "expected onset of the local missing stimulus",
                "anchor": "p1 start_time from stimulus_number=2 event",
                "p1_relative_onsets_ms": {
                    slot: EPOCH_ONSETS_MS[slot] for slot in OMISSION_SLOTS
                },
                "local_coordinate_transform": "t_local_ms = (t_signal - (p1_start_time + onset_ms/1000))*1000",
                "same_feature_coordinates_across_positions_required": True,
                "absolute_p1_relative_time_allowed_as_classifier_feature": False,
                "window_optimization_performed": False,
                "neural_feature_time_alignment_validated": False,
                "reason": "Stage 4A proves the canonical transform and records signal timebase metadata only; tensor-level alignment is a Stage 4B implementation gate.",
                "source": "jnwb.sequence_layout.EPOCH_ONSETS_MS",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    nuisance_proof = {
        "W1_expected_vs_previous": {
            "p2_p3": "preceding_identity == expected_identity",
            "p4": "preceding_identity != expected_identity; exact A/B reversal",
        },
        "W2_context": "context is deterministically derived from sequence_family: A/B=predictable, R=random; report as omission_context, not omitted_identity",
        "W3_family": "family target is identical to sequence_family; interpretation remains omission sequence-family information",
        "T1_position": "position is deterministically derived from omission_position; raw condition and absolute p1-relative time must be excluded from features",
        "T1_cross_family": "family is held out between train and test; common-cycle grouping remains required",
    }
    task_receipt = {
        spec["task"]: {
            "role": spec["role"],
            "target": spec["target"],
            "alternate_target": spec.get("alternate_target", ""),
            "geometry": spec["geometry"],
            "train_slots": spec["train_slots"],
            "test_slots": spec["test_slots"],
            "train_families": spec["train_families"],
            "test_families": spec["test_families"],
            "group_col": spec["group_col"],
            "local_alignment_required": True,
            "frozen_primary": bool(spec.get("frozen_primary", False)),
        }
        for spec in task_list
    }
    receipt = {
        "schema_version": 3,
        "experiment": "handout-4-full-corpus-what-when-omission-information",
        "stage": "4A_design_corpus_audit",
        "status": "complete",
        "authorization": {
            "SAFE_TO_AUDIT_FULL_WHAT_WHEN_DESIGN": True,
            "SAFE_TO_RUN_NEW_LINEAR_MODELS": False,
            "SAFE_TO_RUN_M2": False,
            "SAFE_TO_RUN_M3_M4": False,
        },
        "preserved_evidence_state": {
            "OLD_RANDOM_CV_0.601": "RETRACTED",
            "POOLED_A_B_EXPECTED_IDENTITY": "NON_IDENTIFIABLE",
            "R0_REVERSAL_G": "descriptive +0.040",
            "R1_REVERSAL_G": "descriptive -0.069",
            "existing_reversal_primary": "p2+p3 -> p4 remains confirmatory for expected-vs-previous A/B identity",
            "frozen_primary_sessions": sorted(FROZEN_W1_PRIMARY_SESSIONS),
            "frozen_primary_source": "context/figures/fig04_omission_identity_decoding/structured_identity_experiment_v1/milestone_1/reversal_design/reversal_contrast_session_eligibility.csv",
            "full_corpus_candidate_is_not_confirmatory": True,
        },
        "inputs": {
            "catalog": str(catalog_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "readiness": str(readiness_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "nwb_dir": str(nwb_dir),
            "tfr_dir": str(tfr_dir),
            "n_catalog_sessions": len(catalog_sessions),
            "tfr_files_live": int(len(list(tfr_dir.glob("*.npy")))),
            "tfr_files_reported_by_readiness": int(
                readiness["tfr_n_files"].fillna(0).map(_int_or_zero).sum()
            ),
        },
        "input_hashes": {
            "catalog": _sha256(catalog_path),
            "readiness": _sha256(readiness_path),
            "audit_script": _sha256(Path(__file__).resolve()),
        },
        "counts": {
            "sessions_in_catalog": int(len(catalog_sessions)),
            "sessions_audited": int((session_df["status"] == "audited").sum()),
            "sessions_excluded": int((session_df["status"] != "audited").sum()),
            "subjects_audited": int(session_df.loc[session_df["status"] == "audited", "subject"].nunique()),
            "trial_rows": int(sum(len(frame) for frame in trial_frames.values())),
            "task_session_geometry_rows": int(len(geometry_df)),
            "signal_area_rows": int(len(signal_area_df)),
            "corpus_rows": int(len(corpus_df)),
        },
        "task_definitions": task_receipt,
        "nuisance_determinism": nuisance_proof,
        "design_findings": [
            "W1_reversal_primary remains the frozen five-session confirmatory corpus; the 16-session common-cycle extension is a design candidate and is not promoted.",
            "W2 context and W3 family targets are identifiable as sequence-family/context tasks, but sequence_family is the target-defining nuisance and cannot support an omitted-stimulus-identity interpretation by itself.",
            "T1 position is identifiable only under the local omission-time contract; raw absolute p1-relative time and condition codes are prohibited classifier features.",
            "All 21 audited NWBs expose raw LFP and MUAe acquisition groups. MUAe has a loader gap, so no MUAe task is training-ready in Stage 4A.",
            "The resolved live TFR directory contains 4 files while session_readiness reports 792; TFR-backed LFP eligibility is therefore not trusted from readiness alone.",
        ],
        "modality_contracts": {
            "SUA_SPK": {
                "source": "NWB units.spike_times",
                "audit_status": "metadata_available",
                "representations": ["R0_collapsed_rate", "R1_temporally_resolved_vector"],
                "unit_topology": "unit rows are not spatial topology; no arbitrary adjacency claim",
            },
            "MUAe": {
                "source": "NWB acquisition probe_*_muae data datasets",
                "audit_status": "raw_groups_audited_loader_gap",
                "representations": ["collapsed_linear", "temporally_resolved_linear"],
                "training_status": "not_authorized",
            },
            "LFP": {
                "source": "NWB acquisition probe_*_lfp plus optional precomputed TFR arrays",
                "audit_status": "raw_groups_audited; live TFR directory independently inventoried because readiness metadata is stale relative to the resolved path",
                "representations": ["time_domain_channels", "band_power_or_temporally_resolved_band_power"],
                "baseline_rule": "raw power -> baseline ratio -> aggregate ratio -> 10log10 where TFR features are used",
            },
        },
        "local_alignment_contract": json.loads(
            outputs["local_alignment_contract"].read_text(encoding="utf-8")
        ),
        "outputs": {
            key: str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            for key, path in outputs.items()
        },
        "output_hashes": {key: _sha256(path) for key, path in outputs.items()},
        "git_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "training_performed": False,
        "neural_tensors_materialized": False,
        "permutation_draws_generated": False,
        "stop_rule": "STOP after Stage 4A; do not run new linear, M2, M3, or M4 models until this receipt is reviewed and Stage 4B is separately authorized.",
        "falsifier": "This design receipt is superseded if the live catalog/readiness inputs change, canonical condition mappings or timing contracts change, or a signed Handout 4 amendment replaces these task definitions.",
    }
    receipt_path = output_dir / "stage4a_design_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--readiness", type=Path, default=READINESS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--nwb-dir", type=Path, default=None)
    parser.add_argument("--tfr-dir", type=Path, default=None)
    args = parser.parse_args()
    result = run(
        catalog_path=args.catalog,
        readiness_path=args.readiness,
        output_dir=args.output_dir,
        nwb_dir=args.nwb_dir,
        tfr_dir=args.tfr_dir,
    )
    print(json.dumps(result["counts"], sort_keys=True), flush=True)
    print("Stage 4A complete: no neural tensors, models, or permutation draws.", flush=True)


if __name__ == "__main__":
    main()
