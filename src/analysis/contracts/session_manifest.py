from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

@dataclass
class ConditionInfo:
    code: str
    label: str
    trial_count: int
    is_omission: bool = False
    omission_slot: Optional[int] = None # 2, 3, or 4
    is_matched_control: bool = False

@dataclass
class AreaMapping:
    area: str
    probe: int
    start_ch: int
    end_ch: int
    resolution_status: str # 'validated', 'provisional', 'unresolved'

@dataclass
class UnitMetadata:
    unit_id: str
    probe: int
    local_idx: int
    peak_channel: int
    area: str
    resolution_status: str

@dataclass
class SessionManifest:
    session_id: str
    subject_id: str
    recording_date: Optional[str] = None
    manifest_version: str = "1.0"
    
    # Signals
    has_spk: bool = False
    has_muae: bool = False
    has_lfp: bool = False
    has_behavior: bool = False
    sampling_rates: Dict[str, float] = field(default_factory=dict)
    
    # Conditions
    conditions: List[ConditionInfo] = field(default_factory=list)
    
    # Timing (ms relative to p1 onset)
    p1_epoch_ms: List[float] = field(default_factory=lambda: [-1000.0, 5000.0])
    omission_onsets_ms: Dict[int, float] = field(default_factory=lambda: {
        2: 1031.0,
        3: 2062.0,
        4: 3093.0
    })
    tfr_baseline_ms: List[float] = field(default_factory=lambda: [-500.0, 0.0])
    
    # Anatomy
    area_mappings: List[AreaMapping] = field(default_factory=list)
    units: List[UnitMetadata] = field(default_factory=list)
    
    # Provenance
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    generated_by: str = "build_session_manifest.py"
    git_commit: Optional[str] = None
    truth_status: str = "truth_safe_unverified"
    warnings: List[str] = field(default_factory=list)

    def to_dict(self):
        import dataclasses
        return dataclasses.asdict(self)
