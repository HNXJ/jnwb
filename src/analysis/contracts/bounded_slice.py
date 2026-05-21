# src/analysis/contracts/bounded_slice.py
"""
Phase 2I Bounded Slice Contracts.
Provides BoundedSliceRequest, BoundedSliceResult, and safe opt-in execution wrappers.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any

from src.analysis.contracts.signal_block import SignalBlock
from src.analysis.contracts.fixture_signal_blocks import make_fixture_signal_block
from src.analysis.contracts.constants import ALLOWED_SIGNAL_CLASSES, TRUTH_SAFE_UNVERIFIED

@dataclass
class BoundedSliceRequest:
    session_id: str
    signal_class: str
    source_path: Optional[str] = None
    max_trials: int = 1
    max_units_or_channels: int = 2
    max_timepoints: int = 100
    max_bytes: int = 1048576  # 1 MB
    allow_real_data: bool = False
    truth_status: str = TRUTH_SAFE_UNVERIFIED

    def validate(self) -> List[str]:
        errors = []
        if self.allow_real_data is not False and self.allow_real_data is not True:
            errors.append("Field 'allow_real_data' must be a boolean.")
        
        if self.max_trials <= 0:
            errors.append(f"Field 'max_trials' must be positive, got {self.max_trials}.")
        if self.max_units_or_channels <= 0:
            errors.append(f"Field 'max_units_or_channels' must be positive, got {self.max_units_or_channels}.")
        if self.max_timepoints <= 0:
            errors.append(f"Field 'max_timepoints' must be positive, got {self.max_timepoints}.")
        if self.max_bytes <= 0:
            errors.append(f"Field 'max_bytes' must be positive, got {self.max_bytes}.")

        if self.signal_class not in ALLOWED_SIGNAL_CLASSES:
            errors.append(f"Invalid signal_class '{self.signal_class}'. Must be one of {ALLOWED_SIGNAL_CLASSES}.")

        if self.truth_status != TRUTH_SAFE_UNVERIFIED:
            errors.append(f"Truth status must remain '{TRUTH_SAFE_UNVERIFIED}', got '{self.truth_status}'.")

        return errors

@dataclass
class BoundedSliceResult:
    status: str  # skipped, unavailable, blocked, loaded_bounded_slice, invalid
    request: Dict[str, Any]
    signal_block: Optional[SignalBlock] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    bytes_read_estimate: int = 0
    source_path: Optional[str] = None
    raw_array_contents_read: bool = False
    truth_status: str = TRUTH_SAFE_UNVERIFIED

def make_bounded_fixture_slice(request: BoundedSliceRequest) -> BoundedSliceResult:
    """
    Produces a valid synthetic SignalBlock using existing fixture helpers and request bounds.
    """
    errors = request.validate()
    req_dict = {
        "session_id": request.session_id,
        "signal_class": request.signal_class,
        "source_path": request.source_path,
        "max_trials": request.max_trials,
        "max_units_or_channels": request.max_units_or_channels,
        "max_timepoints": request.max_timepoints,
        "max_bytes": request.max_bytes,
        "allow_real_data": request.allow_real_data,
        "truth_status": request.truth_status
    }

    if errors:
        return BoundedSliceResult(
            status="invalid",
            request=req_dict,
            signal_block=None,
            errors=errors,
            warnings=[],
            bytes_read_estimate=0,
            source_path=request.source_path,
            raw_array_contents_read=False,
            truth_status=request.truth_status
        )

    try:
        block = make_fixture_signal_block(
            signal_class=request.signal_class,
            session_id=request.session_id,
            n_trials=request.max_trials,
            n_units_or_channels=request.max_units_or_channels,
            n_time=request.max_timepoints
        )
        return BoundedSliceResult(
            status="loaded_bounded_slice",
            request=req_dict,
            signal_block=block,
            errors=[],
            warnings=[],
            bytes_read_estimate=0,
            source_path=request.source_path,
            raw_array_contents_read=False,
            truth_status=request.truth_status
        )
    except Exception as e:
        return BoundedSliceResult(
            status="invalid",
            request=req_dict,
            signal_block=None,
            errors=[f"Failed to generate fixture block: {e}"],
            warnings=[],
            bytes_read_estimate=0,
            source_path=request.source_path,
            raw_array_contents_read=False,
            truth_status=request.truth_status
        )

def load_bounded_real_slice(request: BoundedSliceRequest) -> BoundedSliceResult:
    """
    Opt-in real-data loader with strict safety gating.
    All high-density raw extensions (.npy, .nwb, etc.) are explicitly blocked
    in Phase 2I to guarantee zero raw data read.
    """
    errors = request.validate()
    req_dict = {
        "session_id": request.session_id,
        "signal_class": request.signal_class,
        "source_path": request.source_path,
        "max_trials": request.max_trials,
        "max_units_or_channels": request.max_units_or_channels,
        "max_timepoints": request.max_timepoints,
        "max_bytes": request.max_bytes,
        "allow_real_data": request.allow_real_data,
        "truth_status": request.truth_status
    }

    if errors:
        return BoundedSliceResult(
            status="invalid",
            request=req_dict,
            signal_block=None,
            errors=errors,
            warnings=[],
            bytes_read_estimate=0,
            source_path=request.source_path,
            raw_array_contents_read=False,
            truth_status=request.truth_status
        )

    if not request.allow_real_data:
        return BoundedSliceResult(
            status="skipped",
            request=req_dict,
            signal_block=None,
            errors=[],
            warnings=["Real-data slice skipped because allow_real_data is False."],
            bytes_read_estimate=0,
            source_path=request.source_path,
            raw_array_contents_read=False,
            truth_status=request.truth_status
        )

    if not request.source_path:
        return BoundedSliceResult(
            status="unavailable",
            request=req_dict,
            signal_block=None,
            errors=["Source path is missing."],
            warnings=[],
            bytes_read_estimate=0,
            source_path=None,
            raw_array_contents_read=False,
            truth_status=request.truth_status
        )

    path = Path(request.source_path)
    if not path.exists():
        return BoundedSliceResult(
            status="unavailable",
            request=req_dict,
            signal_block=None,
            errors=[f"Source path does not exist: {request.source_path}"],
            warnings=[],
            bytes_read_estimate=0,
            source_path=request.source_path,
            raw_array_contents_read=False,
            truth_status=request.truth_status
        )

    ext = path.suffix.lower()
    raw_extensions = [".nwb", ".mat", ".h5", ".hdf5", ".npy", ".npz"]
    allowlisted_extensions = raw_extensions + [".json", ".csv", ".tsv", ".txt"]

    if ext not in allowlisted_extensions:
        return BoundedSliceResult(
            status="blocked",
            request=req_dict,
            signal_block=None,
            errors=[f"Extension '{ext}' is not allowlisted."],
            warnings=[],
            bytes_read_estimate=0,
            source_path=request.source_path,
            raw_array_contents_read=False,
            truth_status=request.truth_status
        )

    try:
        size_bytes = path.stat().st_size
    except Exception as e:
        return BoundedSliceResult(
            status="unavailable",
            request=req_dict,
            signal_block=None,
            errors=[f"Failed to check file size: {e}"],
            warnings=[],
            bytes_read_estimate=0,
            source_path=request.source_path,
            raw_array_contents_read=False,
            truth_status=request.truth_status
        )

    if size_bytes > request.max_bytes:
        return BoundedSliceResult(
            status="blocked",
            request=req_dict,
            signal_block=None,
            errors=[f"File size {size_bytes} exceeds request limit of {request.max_bytes} bytes."],
            warnings=["File size limit exceeded. Safe partial reading not implemented."],
            bytes_read_estimate=0,
            source_path=request.source_path,
            raw_array_contents_read=False,
            truth_status=request.truth_status
        )

    if ext in raw_extensions:
        return BoundedSliceResult(
            status="blocked",
            request=req_dict,
            signal_block=None,
            errors=[],
            warnings=["Raw real-data slicing not implemented yet under Phase 2I doctrine."],
            bytes_read_estimate=0,
            source_path=request.source_path,
            raw_array_contents_read=False,
            truth_status=request.truth_status
        )

    # For tiny non-raw metadata text/JSON sources, if any are encountered, we still block real array read.
    return BoundedSliceResult(
        status="blocked",
        request=req_dict,
        signal_block=None,
        errors=[],
        warnings=["Non-raw text source encountered. Slicing not implemented."],
        bytes_read_estimate=0,
        source_path=request.source_path,
        raw_array_contents_read=False,
        truth_status=request.truth_status
    )
