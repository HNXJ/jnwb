from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
from src.analysis.contracts.base import ContractMixin
from src.analysis.contracts.constants import (
    TRUTH_SAFE_UNVERIFIED,
    ALLOWED_SIGNAL_CLASSES,
    ALLOWED_TIME_BASES,
    GENERIC_UNRESOLVED_AREAS,
    SIGNAL_CLASS_DIMS,
    REQUIRED_SIGNAL_BLOCK_FIELDS
)

@dataclass
class SignalBlock(ContractMixin):
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
    truth_status: str = TRUTH_SAFE_UNVERIFIED

    def validate(self) -> List[str]:
        errors = []
        
        # 0. Check required fields
        errors.extend(self._validate_required_fields(REQUIRED_SIGNAL_BLOCK_FIELDS))
        
        # 1. signal_class allowed values
        if self.signal_class and self.signal_class not in ALLOWED_SIGNAL_CLASSES:
            errors.append(f"Invalid signal_class '{self.signal_class}'. Must be one of {ALLOWED_SIGNAL_CLASSES}.")
            
        # 2. time_base allowed values
        if self.time_base and self.time_base not in ALLOWED_TIME_BASES:
            errors.append(f"Invalid time_base '{self.time_base}'. Must be one of {ALLOWED_TIME_BASES}.")
            
        # 3. dims must match signal_class expectation when data has shape:
        # SPK/SUA -> trial, unit, time
        # MUAe/LFP -> trial, channel, time
        if hasattr(self.data, "shape"):
            shape = self.data.shape
            if len(self.dims) != len(shape):
                errors.append(f"Dimension length {len(self.dims)} must match data shape rank {len(shape)}.")
            
            if self.signal_class in SIGNAL_CLASS_DIMS:
                expected_dims = SIGNAL_CLASS_DIMS[self.signal_class]
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
            if area.strip() in GENERIC_UNRESOLVED_AREAS:
                has_generic_v3 = True
                break
        if has_generic_v3:
            msg = "Area labels contain generic unresolved V3."
            if msg not in self.warnings:
                self.warnings.append(msg)
                
        # 6. truth_status must remain truth_safe_unverified unless explicitly validated later
        errors.extend(self._validate_truth_status())
            
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
