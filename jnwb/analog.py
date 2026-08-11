"""Canonical trial-aligned analog epochs for LFP and MUAe.

The accessor is intentionally additive and read-only.  It uses h5py because several omission
sessions contain PyNWB Device metadata that blocks a full object construction.  Raw datasets are
``(time, channel)``; returned epochs are always ``(trial, channel, time)``.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import h5py
import numpy as np
import pandas as pd

from .paths import REPO_ROOT
from .sequence_layout import EPOCH_ONSETS_MS, channel_slice_for_area, parse_probe_areas
from .session import condition_map_for_stem
from .trial_ontology import CONDITION_ONTOLOGY


@dataclass(frozen=True)
class EpochBatch:
    """Trial-aligned analog data and its explicit provenance."""

    data: np.ndarray
    time_ms: np.ndarray
    trial_metadata: pd.DataFrame
    signal_metadata: pd.DataFrame
    manifest: dict[str, Any]


@dataclass(frozen=True)
class _Series:
    signal_class: str
    probe: str
    object_path: str
    dataset_path: str
    electrode_path: str | None
    n_samples: int
    n_channels: int
    sampling_rate_hz: float
    starting_time_s: float
    units: str
    data: h5py.Dataset
    channel_ids: tuple[int, ...]
    areas: tuple[str | None, ...]
    local_indices: tuple[int, ...]


def _scalar(value: Any) -> Any:
    if isinstance(value, (bytes, np.bytes_)):
        return value.decode("utf-8", "replace")
    if isinstance(value, np.ndarray) and value.shape == ():
        return _scalar(value.item())
    return value


def _float(value: Any) -> float:
    try:
        return float(_scalar(value))
    except (TypeError, ValueError):
        return float("nan")


def _numeric(group: h5py.Group, name: str) -> np.ndarray:
    values = group[name][:]
    if values.dtype.kind in ("O", "S", "U"):
        return np.asarray([_float(value) for value in values], dtype=float)
    return np.asarray(values, dtype=float)


def _dataset(group: h5py.Group, leaf: str) -> tuple[str | None, h5py.Dataset | None]:
    found: list[tuple[str, h5py.Dataset]] = []

    def visit(name: str, obj: h5py.Dataset | h5py.Group) -> None:
        if isinstance(obj, h5py.Dataset) and name.rsplit("/", 1)[-1] == leaf:
            found.append((name, obj))

    group.visititems(visit)
    found.sort(key=lambda item: (len(item[0].split("/")), item[0]))
    return found[0] if found else (None, None)


def _rate_and_start(group: h5py.Group, data: h5py.Dataset) -> tuple[float, float, str]:
    candidates: list[h5py.Group | h5py.Dataset] = []

    def visit(name: str, obj: h5py.Dataset | h5py.Group) -> None:
        candidates.append(obj)

    group.visititems(visit)
    rate = float("nan")
    start = 0.0
    time_base = "unknown"
    for obj in candidates:
        for key in ("rate", "sampling_rate", "sample_rate"):
            if key in obj.attrs and not np.isfinite(rate):
                rate = _float(obj.attrs[key])
        if "starting_time" in obj.attrs:
            start = _float(obj.attrs["starting_time"])
        if isinstance(obj, h5py.Dataset) and obj.name.rsplit("/", 1)[-1] == "starting_time":
            if obj.shape == ():
                start = _float(obj[()])
            if "rate" in obj.attrs and not np.isfinite(rate):
                rate = _float(obj.attrs["rate"])
            if np.isfinite(rate):
                time_base = "starting_time_plus_uniform_rate"
    if not np.isfinite(rate) or rate <= 0:
        raise ValueError(f"analog series has no positive sampling rate: {group.name}")
    if not np.isfinite(start):
        raise ValueError(f"analog series has non-finite starting_time: {group.name}")
    return float(rate), float(start), time_base


def _electrode_metadata(
    handle: h5py.File,
) -> dict[str, dict[int, dict[str, Any]]]:
    table = handle.get("general/extracellular_ephys/electrodes")
    if table is None:
        return {}
    ids = _numeric(table, "id")
    locations = [str(_scalar(value)).strip() for value in table["location"][:]]
    if "group_name" in table:
        probes = [str(_scalar(value)) for value in table["group_name"][:]]
    elif "probe" in table:
        probes = [str(_scalar(value)) for value in table["probe"][:]]
    else:
        probes = ["unknown"] * len(ids)
    local_counter: dict[str, int] = {}
    result: dict[str, dict[int, dict[str, Any]]] = {}
    for channel_id, location, probe in zip(ids, locations, probes):
        local_index = local_counter.get(probe, 0)
        local_counter[probe] = local_index + 1
        parsed = parse_probe_areas(location)
        area = None
        for candidate in parsed:
            channel_slice = channel_slice_for_area(parsed, candidate, n_channels=128)
            if channel_slice is not None and channel_slice.start <= local_index < channel_slice.stop:
                area = candidate
                break
        if area is None and parsed:
            area = parsed[min(local_index * len(parsed) // 128, len(parsed) - 1)]
        result.setdefault(probe, {})[local_index] = {
            "channel_id": int(channel_id),
            "area": area,
            "location_raw": location,
        }
    return result


def _resolve_source(source: Any) -> Path:
    path = Path(source) if isinstance(source, (str, Path)) else Path(source.nwb_path)
    if not path.is_file():
        raise FileNotFoundError(f"NWB source not found: {path}")
    return path.resolve()


def _subject_from_stem(stem: str) -> str:
    return stem.split("_", 1)[0].removeprefix("sub-")


def _trial_table(
    handle: h5py.File,
    stem: str,
    condition: str | Sequence[str] | None,
    slot_keys: Sequence[str] | None,
    correct_only: bool,
) -> pd.DataFrame:
    intervals = handle.get("intervals/omission_glo_passive")
    required = ("start_time", "trial_num", "stimulus_number", "task_condition_number")
    if intervals is None or any(name not in intervals for name in required):
        raise ValueError("omission intervals lack required trial columns")
    frame = pd.DataFrame({name: _numeric(intervals, name) for name in required})
    if "correct" in intervals:
        frame["correct"] = _numeric(intervals, "correct")
    else:
        frame["correct"] = 1.0
    frame = frame[
        np.isclose(frame["stimulus_number"], 2.0, equal_nan=False)
        & np.isfinite(frame["start_time"])
        & np.isfinite(frame["trial_num"])
        & np.isfinite(frame["task_condition_number"])
    ].copy()
    if correct_only:
        frame = frame[frame["correct"].eq(1.0)]
    mapping = condition_map_for_stem(stem)
    inverse = {int(code): name for name, codes in mapping.items() for code in codes}
    frame["condition"] = (
        frame["task_condition_number"].round().astype(int).map(inverse)
    )
    frame = frame.dropna(subset=["condition"]).drop_duplicates(
        ["trial_num", "condition"], keep="first"
    )
    if condition is not None:
        wanted = [condition] if isinstance(condition, str) else list(condition)
        frame = frame[frame["condition"].isin(wanted)]
    onto = frame["condition"].map(CONDITION_ONTOLOGY)
    frame["sequence_family"] = onto.map(lambda item: item["sequence_family"])
    frame["omission_position"] = onto.map(lambda item: item["omission_position"])
    frame["expected_identity"] = onto.map(lambda item: item["expected_identity"])
    frame["preceding_identity"] = onto.map(lambda item: item["preceding_identity"])
    frame["presented_identity"] = onto.map(lambda item: item["presented_identity"])
    if slot_keys is not None:
        frame = frame[frame["omission_position"].isin(slot_keys)]
    frame = frame.reset_index(drop=True)
    if frame.empty:
        raise ValueError("no trials passed the requested canonical condition/slot filters")
    frame["trial_num"] = frame["trial_num"].round().astype(int)
    frame["condition_number"] = frame["task_condition_number"].round().astype(int)
    frame["trial_id"] = frame.apply(
        lambda row: f"{stem}|trial={row['trial_num']}|condition={row['condition']}",
        axis=1,
    )
    frame["subject"] = _subject_from_stem(stem)
    frame["session"] = stem
    return frame


def _series(
    handle: h5py.File,
    signal_class: str,
) -> list[_Series]:
    acquisition = handle.get("acquisition")
    if acquisition is None:
        raise ValueError("NWB has no acquisition group")
    suffix = f"_{signal_class.lower()}"
    electrode_metadata = _electrode_metadata(handle)
    result: list[_Series] = []
    for key in sorted(acquisition.keys()):
        if not key.endswith(suffix):
            continue
        root = acquisition[key]
        data_path, data = _dataset(root, "data")
        if data is None or data.ndim != 2:
            raise ValueError(f"{key} does not expose a 2-D (time, channel) data dataset")
        rate, start, time_base = _rate_and_start(root, data)
        electrode_path, electrode_dataset = _dataset(root, "electrodes")
        if electrode_dataset is None:
            channel_ids = tuple(range(data.shape[1]))
        else:
            channel_ids = tuple(int(_float(value)) for value in electrode_dataset[:])
        probe_match = key.split("_", 2)[1]
        probe_name = f"probe{chr(ord('A') + int(probe_match))}"
        probe_meta = electrode_metadata.get(probe_name, {})
        areas = tuple(probe_meta.get(i, {}).get("area") for i in range(data.shape[1]))
        if len(channel_ids) != data.shape[1]:
            raise ValueError(f"{key} electrode reference length does not match data channels")
        result.append(
            _Series(
                signal_class=signal_class,
                probe=probe_name,
                object_path=f"acquisition/{key}",
                dataset_path=f"acquisition/{key}/{data_path}",
                electrode_path=(
                    f"acquisition/{key}/{electrode_path}" if electrode_path else None
                ),
                n_samples=int(data.shape[0]),
                n_channels=int(data.shape[1]),
                sampling_rate_hz=rate,
                starting_time_s=start,
                units=str(_scalar(data.attrs.get("unit", "unknown"))),
                data=data,
                channel_ids=channel_ids,
                areas=areas,
                local_indices=tuple(range(data.shape[1])),
            )
        )
    if not result:
        raise ValueError(f"no acquisition series found for signal class {signal_class}")
    rates = {round(item.sampling_rate_hz, 9) for item in result}
    if len(rates) != 1:
        raise ValueError(f"selected analog series have incompatible sampling rates: {rates}")
    return result


def _select_channels(
    series: Sequence[_Series],
    areas: Sequence[str] | None,
    channel_ids: Sequence[int] | None,
) -> list[tuple[_Series, list[int]]]:
    if channel_ids is not None and len(series) > 1:
        raise ValueError("channel_ids are ambiguous across multiple probes; select one area/probe")
    selected: list[tuple[_Series, list[int]]] = []
    area_set = set(areas) if areas is not None else None
    for item in series:
        indices = list(range(item.n_channels))
        if area_set is not None:
            indices = [index for index in indices if item.areas[index] in area_set]
        if channel_ids is not None:
            wanted = set(int(value) for value in channel_ids)
            indices = [index for index in indices if item.channel_ids[index] in wanted]
        if indices:
            selected.append((item, indices))
    if not selected:
        raise ValueError("no analog channels passed the requested area/channel filters")
    return selected


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_analog_epochs(
    source: Any,
    *,
    signal_class: str,
    condition: str | Sequence[str] | None = None,
    slot_keys: Sequence[str] | None = None,
    window_ms: tuple[float, float] = (-100.0, 100.0),
    alignment: str = "p1",
    correct_only: bool = True,
    areas: Sequence[str] | None = None,
    channel_ids: Sequence[int] | None = None,
    missing_data: str = "raise",
    max_trials: int | None = None,
) -> EpochBatch:
    """Load trial-aligned LFP/MUAe epochs with explicit provenance.

    ``alignment='p1'`` anchors to the p1 event.  ``alignment='omission'`` anchors each
    omission trial to its canonical local missing-item onset.  The returned array is always
    ``(trial, channel, time)`` and the returned time vector is relative to that anchor.
    """
    signal_class = str(signal_class).upper()
    if signal_class not in {"LFP", "MUAE"}:
        raise ValueError("signal_class must be 'LFP' or 'MUAe'")
    signal_label = "MUAe" if signal_class == "MUAE" else "LFP"
    if alignment not in {"p1", "omission"}:
        raise ValueError("alignment must be 'p1' or 'omission'")
    if missing_data not in {"raise", "drop"}:
        raise ValueError("missing_data must be 'raise' or 'drop'")
    lo_ms, hi_ms = map(float, window_ms)
    if not hi_ms > lo_ms:
        raise ValueError("window_ms must have hi > lo")
    path = _resolve_source(source)
    stem = path.stem
    with h5py.File(path, "r") as handle:
        trials = _trial_table(handle, stem, condition, slot_keys, correct_only)
        if alignment == "omission":
            trials = trials[trials["omission_position"].notna()].copy()
            if trials.empty:
                raise ValueError("omission alignment requires omission trials")
        if max_trials is not None:
            if max_trials < 1:
                raise ValueError("max_trials must be positive")
            trials = trials.iloc[:max_trials].copy()
        selected = _select_channels(_series(handle, signal_class), areas, channel_ids)
        rate = selected[0][0].sampling_rate_hz
        n_samples_float = (hi_ms - lo_ms) / 1000.0 * rate
        n_samples = int(round(n_samples_float))
        if not np.isclose(n_samples_float, n_samples):
            raise ValueError("window duration does not map to an integral sample count")
        time_ms = lo_ms + np.arange(n_samples, dtype=float) * 1000.0 / rate
        t0_indices = np.flatnonzero(np.isclose(time_ms, 0.0, atol=1e-9))
        if len(t0_indices) != 1:
            raise ValueError("window must contain exactly one sample at relative t=0")

        epoch_parts: list[np.ndarray] = []
        kept_rows: list[dict[str, Any]] = []
        dropped: list[dict[str, Any]] = []
        for _, row in trials.iterrows():
            if alignment == "p1":
                anchor_s = float(row["start_time"])
            else:
                anchor_s = float(row["start_time"]) + (
                    EPOCH_ONSETS_MS[str(row["omission_position"])] / 1000.0
                )
            trial_parts: list[np.ndarray] = []
            trial_failed = False
            failure_reason = ""
            for item, indices in selected:
                start_index = int(
                    round((anchor_s + lo_ms / 1000.0 - item.starting_time_s) * rate)
                )
                stop_index = start_index + n_samples
                if start_index < 0 or stop_index > item.n_samples:
                    trial_failed = True
                    failure_reason = (
                        f"OUT_OF_BOUNDS:{item.object_path}:"
                        f"{start_index}:{stop_index}/{item.n_samples}"
                    )
                    break
                chunk = np.asarray(item.data[start_index:stop_index, indices], dtype=np.float32)
                if chunk.shape != (n_samples, len(indices)):
                    trial_failed = True
                    failure_reason = f"SHAPE_MISMATCH:{chunk.shape}"
                    break
                trial_parts.append(chunk.T)
            if trial_failed:
                dropped.append({"trial_id": row["trial_id"], "reason": failure_reason})
                if missing_data == "raise":
                    raise ValueError(f"analog epoch extraction blocked: {failure_reason}")
                continue
            epoch_parts.append(np.concatenate(trial_parts, axis=0))
            kept = row.to_dict()
            kept.update(
                {
                    "anchor": alignment,
                    "anchor_onset_s": anchor_s,
                    "source_onset_s": float(row["start_time"]),
                    "local_alignment_origin_s": anchor_s,
                    "t0_sample_index": int(t0_indices[0]),
                }
            )
            kept_rows.append(kept)
        if not epoch_parts:
            raise ValueError("all requested analog epochs were unavailable")
        data = np.stack(epoch_parts, axis=0).astype(np.float32, copy=False)
        channel_rows: list[dict[str, Any]] = []
        for item, indices in selected:
            for index in indices:
                channel_rows.append(
                    {
                        "session": stem,
                        "subject": _subject_from_stem(stem),
                        "signal_class": signal_label,
                        "probe": item.probe,
                        "channel_id": item.channel_ids[index],
                        "local_index": index,
                        "area": item.areas[index],
                        "units": item.units,
                        "sampling_rate_hz": item.sampling_rate_hz,
                        "source_object_path": item.object_path,
                        "source_dataset_path": item.dataset_path,
                    }
                )
        kept_metadata = pd.DataFrame(kept_rows)
        manifest = {
            "artifact_schema_version": 1,
            "signal_class": signal_label,
            "source_nwb": str(path),
            "source_nwb_sha256": "not_computed_by_accessor",
            "source_nwb_size_bytes": int(path.stat().st_size),
            "source_nwb_mtime_ns": int(path.stat().st_mtime_ns),
            "source_series": [
                {
                    "object_path": item.object_path,
                    "dataset_path": item.dataset_path,
                    "electrode_path": item.electrode_path,
                    "shape": [item.n_samples, item.n_channels],
                    "dtype": str(item.data.dtype),
                    "sampling_rate_hz": item.sampling_rate_hz,
                    "starting_time_s": item.starting_time_s,
                    "units": item.units,
                }
                for item, _ in selected
            ],
            "alignment_event": alignment,
            "window_ms": [lo_ms, hi_ms],
            "time_base": "relative_uniform_rate",
            "time_vector_ms": time_ms.tolist(),
            "shape": list(data.shape),
            "dtype": str(data.dtype),
            "missing_data_policy": missing_data,
            "dropped_trials": dropped,
            "preprocessing": (
                "source MUAe envelope; no additional filtering/resampling"
                if signal_class == "MUAE"
                else "source LFP; no additional filtering/resampling"
            ),
            "trial_id_join_key": "trial_id",
            "repo_sha": _git_sha(),
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "training_performed": False,
        }
    return EpochBatch(
        data=data,
        time_ms=time_ms,
        trial_metadata=kept_metadata.reset_index(drop=True),
        signal_metadata=pd.DataFrame(channel_rows),
        manifest=manifest,
    )


def load_muae_epochs(source: Any, **kwargs: Any) -> EpochBatch:
    """Load MUAe epochs under the canonical analog contract."""
    return load_analog_epochs(source, signal_class="MUAE", **kwargs)


def load_lfp_epochs(source: Any, **kwargs: Any) -> EpochBatch:
    """Load raw LFP epochs under the same canonical analog contract."""
    return load_analog_epochs(source, signal_class="LFP", **kwargs)


__all__ = ["EpochBatch", "load_analog_epochs", "load_muae_epochs", "load_lfp_epochs"]
