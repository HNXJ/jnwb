# src/analysis/contracts/tiny_readers.py
"""
Phase 2J Allowlisted Tiny Readers.
Provides a strictly bounded, opt-in tiny reader for allowlisted local .npy files.
"""

import os
from pathlib import Path
import numpy as np
from typing import Tuple, List

from src.analysis.contracts.bounded_slice import BoundedSliceRequest, BoundedSliceResult
from src.analysis.contracts.signal_block import SignalBlock
from src.analysis.contracts.constants import (
    TRUTH_SAFE_UNVERIFIED,
    CANONICAL_AREA_ORDER,
    DEFAULT_SAMPLING_RATES
)

def can_read_tiny_npy_slice(request: BoundedSliceRequest) -> Tuple[bool, List[str]]:
    """
    Checks if a request can be serviced by the tiny .npy slice reader.
    """
    errors = []
    if not request.allow_real_data:
        errors.append("Real-data access is not explicitly allowed (allow_real_data=False).")
    if not request.source_path:
        errors.append("Source path is missing.")
        return False, errors

    path = Path(request.source_path)
    if not path.exists():
        errors.append(f"Source path does not exist: {request.source_path}")
        return False, errors

    ext = path.suffix.lower()
    if ext != ".npy":
        errors.append(f"Extension '{ext}' is not allowlisted for partial-read. Only '.npy' is allowed.")

    try:
        size_bytes = path.stat().st_size
        if size_bytes > request.max_bytes:
            errors.append(f"File size {size_bytes} exceeds request limit of {request.max_bytes} bytes.")
    except Exception as e:
        errors.append(f"Failed to check file size: {e}")

    return len(errors) == 0, errors


def read_tiny_npy_slice(request: BoundedSliceRequest) -> BoundedSliceResult:
    """
    Reads a highly bounded slice from an allowlisted local .npy file.
    Utilizes memory mapping (mmap_mode="r") to avoid loading the full file.
    """
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

    # Run request validations first
    val_errors = request.validate()
    if val_errors:
        return BoundedSliceResult(
            status="invalid",
            request=req_dict,
            signal_block=None,
            errors=val_errors,
            warnings=[],
            bytes_read_estimate=0,
            source_path=request.source_path,
            raw_array_contents_read=False,
            truth_status=request.truth_status
        )

    # Check reading pre-requisites
    possible, check_errors = can_read_tiny_npy_slice(request)
    if not possible:
        # Determine appropriate status
        if not request.allow_real_data:
            return BoundedSliceResult(
                status="skipped",
                request=req_dict,
                signal_block=None,
                errors=[],
                warnings=check_errors,
                bytes_read_estimate=0,
                source_path=request.source_path,
                raw_array_contents_read=False,
                truth_status=request.truth_status
            )
        elif not request.source_path or "does not exist" in "".join(check_errors):
            return BoundedSliceResult(
                status="unavailable",
                request=req_dict,
                signal_block=None,
                errors=check_errors,
                warnings=[],
                bytes_read_estimate=0,
                source_path=request.source_path,
                raw_array_contents_read=False,
                truth_status=request.truth_status
            )
        else:
            return BoundedSliceResult(
                status="blocked",
                request=req_dict,
                signal_block=None,
                errors=check_errors,
                warnings=[],
                bytes_read_estimate=0,
                source_path=request.source_path,
                raw_array_contents_read=False,
                truth_status=request.truth_status
            )

    try:
        path = Path(request.source_path)
        # Use memory mapping to read only a slice
        arr = np.load(path, mmap_mode="r")
        
        if arr.ndim != 3:
            return BoundedSliceResult(
                status="blocked",
                request=req_dict,
                signal_block=None,
                errors=[f"NPY array must be rank 3, got rank {arr.ndim} with shape {arr.shape}."],
                warnings=[],
                bytes_read_estimate=0,
                source_path=request.source_path,
                raw_array_contents_read=False,
                truth_status=request.truth_status
            )

        # Slice bounded boundaries
        n_trials = min(arr.shape[0], request.max_trials)
        n_units_or_ch = min(arr.shape[1], request.max_units_or_channels)
        n_time = min(arr.shape[2], request.max_timepoints)

        # Extract only the bounded slice
        sliced_data = arr[:n_trials, :n_units_or_ch, :n_time]
        # Force materialization/load of the sliced subset into memory
        sliced_data_copy = np.array(sliced_data)

        # Dims setting based on signal class
        if request.signal_class == "SPK":
            dims = ("trial", "unit", "time")
        else:
            dims = ("trial", "channel", "time")

        # Estimate bytes read
        bytes_read = int(sliced_data_copy.nbytes)

        # Build clean provenance (basename only to avoid leaking full private paths)
        safe_path_name = path.name
        
        provenance = {
            "type": "bounded_tiny_npy_slice",
            "no_full_file_read_intended": True,
            "max_trials": request.max_trials,
            "max_units_or_channels": request.max_units_or_channels,
            "max_timepoints": request.max_timepoints,
            "source_file_basename": safe_path_name,
            "bytes_read_estimate": bytes_read
        }

        # Determine IDs and Area Labels
        if request.signal_class == "SPK":
            unit_or_channel_ids = [f"{request.session_id}_unit_{i}" for i in range(n_units_or_ch)]
        else:
            unit_or_channel_ids = [f"{request.session_id}_ch_{i}" for i in range(n_units_or_ch)]
        
        area_labels = [CANONICAL_AREA_ORDER[i % len(CANONICAL_AREA_ORDER)] for i in range(n_units_or_ch)]
        sampling_rate = DEFAULT_SAMPLING_RATES.get(request.signal_class, 1000.0)

        # Wrap into SignalBlock
        block = SignalBlock(
            data=sliced_data_copy,
            dims=dims,
            signal_class=request.signal_class,
            session_id=request.session_id,
            condition="unspecified",
            time_base="p1_relative",
            alignment_event="unspecified",
            window_ms=(0, n_time),
            sampling_rate=sampling_rate,
            unit_or_channel_ids=unit_or_channel_ids,
            area_labels=area_labels,
            baseline_ms=None,
            area_resolution_status={uid: "real_metadata_derived" for uid in unit_or_channel_ids},
            source_files=[path.name],
            warnings=[],
            provenance=provenance,
            truth_status=TRUTH_SAFE_UNVERIFIED
        )

        return BoundedSliceResult(
            status="loaded_bounded_slice",
            request=req_dict,
            signal_block=block,
            errors=[],
            warnings=[],
            bytes_read_estimate=bytes_read,
            source_path=request.source_path,
            raw_array_contents_read=True,
            truth_status=request.truth_status
        )

    except Exception as e:
        return BoundedSliceResult(
            status="invalid",
            request=req_dict,
            signal_block=None,
            errors=[f"Failed to read tiny NPY slice: {e}"],
            warnings=[],
            bytes_read_estimate=0,
            source_path=request.source_path,
            raw_array_contents_read=False,
            truth_status=request.truth_status
        )
