# src/analysis/contracts/manifest_scaffold.py
"""
Phase 2K session manifest production validator/scaffold contract.
Defines ManifestScaffoldCandidate and ManifestScaffoldReport dataclasses.
All statuses and validations remain gated under TRUTH_SAFE_UNVERIFIED.
"""

from dataclasses import dataclass, field
import dataclasses
from typing import List, Dict, Optional, Any
from src.analysis.contracts.constants import TRUTH_SAFE_UNVERIFIED

@dataclass
class ManifestScaffoldCandidate:
    session_id: Optional[str]
    source_files: List[str] = field(default_factory=list)
    detected_fields: Dict[str, bool] = field(default_factory=dict)
    inferred_subject: Optional[str] = None
    inferred_recording_date: Optional[str] = None
    signal_availability: Dict[str, bool] = field(default_factory=dict)
    trial_count_sources: List[str] = field(default_factory=list)
    unit_count_sources: List[str] = field(default_factory=list)
    channel_count_sources: List[str] = field(default_factory=list)
    area_mapping_sources: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    truth_status: str = TRUTH_SAFE_UNVERIFIED

    def validate(self) -> List[str]:
        val_errors = list(self.errors)
        if self.truth_status != TRUTH_SAFE_UNVERIFIED:
            val_errors.append(f"Truth status must remain '{TRUTH_SAFE_UNVERIFIED}', got '{self.truth_status}'.")
        return val_errors

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'ManifestScaffoldCandidate':
        return cls(**d)

@dataclass
class ManifestScaffoldReport:
    data_root: Optional[str]
    candidates: List[ManifestScaffoldCandidate] = field(default_factory=list)
    skipped: bool = False
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    truth_status: str = TRUTH_SAFE_UNVERIFIED

    def validate(self) -> List[str]:
        val_errors = list(self.errors)
        if self.truth_status != TRUTH_SAFE_UNVERIFIED:
            val_errors.append(f"Truth status must remain '{TRUTH_SAFE_UNVERIFIED}', got '{self.truth_status}'.")
        for c in self.candidates:
            val_errors.extend(c.validate())
        return val_errors

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'ManifestScaffoldReport':
        candidates_data = d.get("candidates", [])
        kwargs = {k: v for k, v in d.items() if k != "candidates"}
        report = cls(**kwargs)
        report.candidates = [ManifestScaffoldCandidate(**c) for c in candidates_data]
        return report
