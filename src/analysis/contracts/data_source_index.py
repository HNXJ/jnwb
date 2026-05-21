# src/analysis/contracts/data_source_index.py
"""
Phase 2F DataSourceIndex and raw-array boundary scaffolds.
Enforces metadata constraints, directory-only size inspection, and no-read policy.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any
from src.analysis.contracts.constants import TRUTH_SAFE_UNVERIFIED

ALLOWED_SOURCE_STATUSES = (
    "unavailable",
    "discovered_metadata",
    "discovered_manifest",
    "discovered_raw_blocked",
    "skipped_large_or_raw",
    "invalid",
    "ambiguous"
)

ALLOWED_ROLES = (
    "manifest",
    "metadata",
    "raw_neural_array",
    "behavior",
    "unknown"
)

@dataclass
class DataSourceRecord:
    path: str
    session_id: Optional[str]
    signal_class: Optional[str]
    file_type: str
    size_bytes: Optional[int]
    role: str
    readable_for_phase2: bool
    reason_not_read: Optional[str]
    source_status: str
    warnings: List[str] = field(default_factory=list)
    truth_status: str = TRUTH_SAFE_UNVERIFIED

    def validate(self) -> List[str]:
        errors = []
        if self.source_status not in ALLOWED_SOURCE_STATUSES:
            errors.append(f"Invalid source_status '{self.source_status}'.")
        if self.role not in ALLOWED_ROLES:
            errors.append(f"Invalid role '{self.role}'.")
        if self.truth_status != TRUTH_SAFE_UNVERIFIED:
            errors.append(f"Truth status must remain '{TRUTH_SAFE_UNVERIFIED}' under Phase 2 doctrine.")
        return errors

@dataclass
class DataSourceIndex:
    data_root: Optional[str]
    records: List[DataSourceRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    truth_status: str = TRUTH_SAFE_UNVERIFIED

    def validate(self) -> List[str]:
        all_errors = list(self.errors)
        if self.truth_status != TRUTH_SAFE_UNVERIFIED:
            all_errors.append(f"Truth status must remain '{TRUTH_SAFE_UNVERIFIED}' under Phase 2 doctrine.")
        for r in self.records:
            all_errors.extend(r.validate())
        return all_errors

    def to_dict(self) -> dict:
        import dataclasses
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'DataSourceIndex':
        records_data = d.get("records", [])
        kwargs = {k: v for k, v in d.items() if k != "records"}
        index = cls(**kwargs)
        index.records = [DataSourceRecord(**r) for r in records_data]
        return index
