from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any

@dataclass
class SignalBlock:
    data: Any
    dims: Tuple[str, ...]
    signal_class: str
    session_id: str
    condition: str
    time_base: str
    alignment_event: str
    window_ms: Tuple[int, int]
    sampling_rate: float
    unit_or_channel_ids: List[str]
    area_labels: List[str]
    baseline_ms: Optional[Tuple[int, int]] = None
    area_resolution_status: Dict[str, str] = field(default_factory=dict)
    source_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    truth_status: str = "truth_safe_unverified"

    def validate(self) -> List[str]:
        errors = []
        
        # 1. signal_class allowed values: SPK, SUA, MUAe, LFP, behavior, metadata, model
        allowed_signals = {"SPK", "SUA", "MUAe", "LFP", "behavior", "metadata", "model"}
        if self.signal_class not in allowed_signals:
            errors.append(f"Invalid signal_class '{self.signal_class}'. Must be one of {allowed_signals}.")
            
        # 2. time_base allowed values: p1_relative, omission_relative, other_declared
        allowed_time_bases = {"p1_relative", "omission_relative", "other_declared"}
        if self.time_base not in allowed_time_bases:
            errors.append(f"Invalid time_base '{self.time_base}'. Must be one of {allowed_time_bases}.")
            
        # 3. dims must match signal_class expectation when data has shape:
        # SPK/SUA -> trial, unit, time
        # MUAe/LFP -> trial, channel, time
        if hasattr(self.data, "shape"):
            shape = self.data.shape
            if len(self.dims) != len(shape):
                errors.append(f"Dimension length {len(self.dims)} must match data shape rank {len(shape)}.")
            
            if self.signal_class in ["SPK", "SUA"]:
                expected_dims = ("trial", "unit", "time")
                if tuple(self.dims) != expected_dims:
                    errors.append(f"Expected dims {expected_dims} for signal_class '{self.signal_class}', got {self.dims}.")
            elif self.signal_class in ["MUAe", "LFP"]:
                expected_dims = ("trial", "channel", "time")
                if tuple(self.dims) != expected_dims:
                    errors.append(f"Expected dims {expected_dims} for signal_class '{self.signal_class}', got {self.dims}.")
                    
        # 4. area_labels length must match unit/channel axis when applicable
        # The unit/channel axis is the 2nd axis (index 1) in trial x unit/channel x time
        if hasattr(self.data, "shape") and len(self.data.shape) >= 2:
            expected_length = self.data.shape[1]
            if len(self.area_labels) != expected_length:
                errors.append(f"area_labels length ({len(self.area_labels)}) must match unit/channel axis size ({expected_length}).")
        
        # 5. warnings required if area labels contain generic V3
        has_generic_v3 = False
        for area in self.area_labels:
            if area.strip() == "V3":
                has_generic_v3 = True
                break
        if has_generic_v3:
            msg = "Area labels contain generic unresolved V3."
            if msg not in self.warnings:
                self.warnings.append(msg)
                
        # 6. truth_status must remain truth_safe_unverified unless explicitly validated later
        if not self.truth_status:
            errors.append("Truth status must be specified.")
        elif self.truth_status != "truth_safe_unverified":
            errors.append("Truth status must remain 'truth_safe_unverified'.")
            
        return errors


def make_signal_block(
    data: Any,
    dims: Tuple[str, ...],
    signal_class: str,
    session_id: str,
    condition: str,
    time_base: str,
    alignment_event: str,
    window_ms: Tuple[int, int],
    sampling_rate: float,
    unit_or_channel_ids: List[str],
    area_labels: List[str],
    baseline_ms: Optional[Tuple[int, int]] = None,
    area_resolution_status: Optional[Dict[str, str]] = None,
    source_files: Optional[List[str]] = None,
    provenance: Optional[Dict[str, Any]] = None,
    truth_status: str = "truth_safe_unverified"
) -> SignalBlock:
    block = SignalBlock(
        data=data,
        dims=dims,
        signal_class=signal_class,
        session_id=session_id,
        condition=condition,
        time_base=time_base,
        alignment_event=alignment_event,
        window_ms=window_ms,
        sampling_rate=sampling_rate,
        unit_or_channel_ids=unit_or_channel_ids,
        area_labels=area_labels,
        baseline_ms=baseline_ms,
        area_resolution_status=area_resolution_status or {},
        source_files=source_files or [],
        provenance=provenance or {},
        truth_status=truth_status
    )
    errors = block.validate()
    if errors:
        raise ValueError(f"SignalBlock validation failed: {errors}")
    return block
