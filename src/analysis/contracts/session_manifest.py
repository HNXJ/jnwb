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
    subject: str = ""
    subject_id: str = ""
    recording_date: Optional[str] = None
    task: Optional[str] = None
    manifest_version: str = "1.0"
    
    # Condition structure
    condition_code_map: Dict[str, Any] = field(default_factory=dict)
    trial_counts_by_condition: Dict[str, int] = field(default_factory=dict)
    
    # Anatomy structure
    probe_ids: List[str] = field(default_factory=list)
    area_by_probe_channel_range: Dict[str, Any] = field(default_factory=dict)
    channel_counts_by_area: Dict[str, int] = field(default_factory=dict)
    unit_counts_by_area: Dict[str, int] = field(default_factory=dict)
    unit_peak_or_anchor_channels: Optional[Dict[str, int]] = None
    area_resolution_status: Dict[str, str] = field(default_factory=dict)
    exclusions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Signals
    signal_availability: Dict[str, bool] = field(default_factory=dict)
    has_spk: bool = False
    has_muae: bool = False
    has_lfp: bool = False
    has_behavior: bool = False
    sampling_rates: Dict[str, float] = field(default_factory=dict)
    
    # Legacy structure for compatibility
    conditions: List[ConditionInfo] = field(default_factory=list)
    p1_epoch_ms: List[float] = field(default_factory=lambda: [-1000.0, 5000.0])
    omission_onsets_ms: Dict[int, float] = field(default_factory=lambda: {
        2: 1031.0,
        3: 2062.0,
        4: 3093.0
    })
    tfr_baseline_ms: List[float] = field(default_factory=lambda: [-500.0, 0.0])
    area_mappings: List[AreaMapping] = field(default_factory=list)
    units: List[UnitMetadata] = field(default_factory=list)
    
    # Provenance
    source_files: List[str] = field(default_factory=list)
    hashes: Dict[str, str] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    generated_by: str = "build_session_manifest.py"
    git_commit: Optional[str] = None
    truth_status: str = "truth_safe_unverified"
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.subject and self.subject_id:
            self.subject = self.subject_id
        if not self.subject_id and self.subject:
            self.subject_id = self.subject

        # Backfill signal_availability from has_* if empty
        if not self.signal_availability:
            self.signal_availability = {
                "SPK": self.has_spk,
                "MUAe": self.has_muae,
                "LFP": self.has_lfp
            }

        # Backfill has_* from signal_availability if empty
        if self.signal_availability:
            self.has_spk = self.signal_availability.get("SPK", self.has_spk)
            self.has_muae = self.signal_availability.get("MUAe", self.has_muae)
            self.has_lfp = self.signal_availability.get("LFP", self.has_lfp)

    @staticmethod
    def normalize_area(area: str) -> str:
        area = area.strip()
        if area in ["DP", "DP (V4)"]:
            return "V4"
        return area

    def is_fixture(self) -> bool:
        return self.subject == "FixtureSubject" or self.session_id in ["230630_fixture", "230719_fixture"]

    def is_real_metadata_derived(self) -> bool:
        if self.is_fixture():
            return False
        return len(self.source_files) > 0 and len(self.hashes) > 0

    def validate(self) -> List[str]:
        errors = []
        
        # 1. subject and session_id required
        if not self.subject:
            errors.append("Subject is required.")
        if not self.session_id:
            errors.append("Session ID is required.")
            
        # 2. truth_status must exist
        if not self.truth_status:
            errors.append("Truth status must be specified.")
        elif self.truth_status != "truth_safe_unverified":
            errors.append("Truth status must remain 'truth_safe_unverified' under Phase 2 doctrine.")

        # 3. generic V3 must produce a warning unless explicitly resolved
        has_generic_v3 = False
        for area in self.channel_counts_by_area.keys():
            if self.normalize_area(area) == "V3" and self.area_resolution_status.get(area) != "resolved":
                has_generic_v3 = True
        
        # Check area mappings for generic V3
        for m in self.area_mappings:
            if self.normalize_area(m.area) == "V3" and m.resolution_status != "resolved":
                has_generic_v3 = True

        if has_generic_v3:
            msg = "Area V3 is UNRESOLVED generic V3."
            if msg not in self.warnings:
                self.warnings.append(msg)

        # 4. signal_availability keys should include SPK, MUAe, LFP where known
        for sig in ["SPK", "MUAe", "LFP"]:
            if sig not in self.signal_availability:
                errors.append(f"Signal class '{sig}' must be declared in signal_availability.")

        # 5. no fixture manifest should claim real_metadata_derived
        if self.is_fixture() and (len(self.source_files) > 0 or len(self.hashes) > 0):
            errors.append("Fixture manifest cannot claim real_metadata_derived.")

        # 6. no manifest should silently accept empty condition maps without warning
        if not self.condition_code_map and not self.conditions:
            msg = "Condition map is empty."
            if msg not in self.warnings:
                self.warnings.append(msg)

        return errors

    def to_dict(self) -> dict:
        import dataclasses
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'SessionManifest':
        # Safely parse dict into dataclass
        conditions_data = d.get("conditions", [])
        area_mappings_data = d.get("area_mappings", [])
        units_data = d.get("units", [])

        # Create clean dict copy
        kwargs = {k: v for k, v in d.items() if k not in ["conditions", "area_mappings", "units"]}

        # Resolve subject/subject_id
        if "subject" not in kwargs and "subject_id" in kwargs:
            kwargs["subject"] = kwargs["subject_id"]

        manifest = cls(**kwargs)

        # Parse nested dataclasses
        manifest.conditions = [ConditionInfo(**c) for c in conditions_data]
        manifest.area_mappings = [AreaMapping(**a) for a in area_mappings_data]
        manifest.units = [UnitMetadata(**u) for u in units_data]

        return manifest
