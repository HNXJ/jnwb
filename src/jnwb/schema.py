"""JSON-serializable address and batch schemas for jnwb."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass
class NWBFileRecord:
    path: str
    session_id: str
    subject: str | None
    date: str | None
    task_names: list[str]
    has_spk: bool
    has_lfp: bool
    has_muae: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SignalAddress:
    signal: Literal["SPK", "LFP", "MUAe"]
    sessions: list[str]
    source_paths: list[str]
    object_paths: dict[str, str]
    ids_by_session: dict[str, list[str | int]]
    area_by_id: dict[str, dict[str | int, str | None]]
    layer_by_id: dict[str, dict[str | int, str | None]]
    probe_by_id: dict[str, dict[str | int, str | None]]
    sampling_rate_by_session: dict[str, float | None]
    units: str | None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EventAddress:
    task: str
    conditions: list[str]
    condition_numbers: list[int]
    anchor: str
    sessions: list[str]
    events_by_session: dict[str, list[dict]]
    time_unit: Literal["s", "ms"]
    p1_code: int
    correct_only: bool
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EpochSpec:
    signal: str
    alignment: str
    window_ms: tuple[int, int]
    output_shape_contract: str
    bin_ms: float | None
    chunk_size: int
    backend: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EpochBatch:
    data: Any
    time_ms: Any
    trial_metadata: Any
    signal_metadata: Any
    manifest: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_shape": getattr(self.data, "shape", None),
            "time_ms_shape": getattr(self.time_ms, "shape", None),
            "manifest": self.manifest,
        }
