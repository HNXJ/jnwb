# src/analysis/contracts/signal_block_adapters.py
"""
Phase 2H SignalBlock adapter utilities.
Provides dependency-light, import-safe methods to validate, read, and summarize SignalBlocks.
"""

import numpy as np
from typing import Tuple, Dict, Any
from src.analysis.contracts.signal_block import SignalBlock

def as_array(signal_block: SignalBlock) -> np.ndarray:
    """
    Validates the SignalBlock and returns its raw underlying numpy array data.
    Does not copy unless necessary.
    """
    errors = signal_block.validate()
    if errors:
        raise ValueError(f"SignalBlock validation failed: {errors}")
    return signal_block.data

def assert_signal_dims(signal_block: SignalBlock, expected_dims: Tuple[str, ...]) -> None:
    """
    Asserts that the SignalBlock has the expected dimensions list.
    Raises ValueError on mismatch.
    """
    if tuple(signal_block.dims) != tuple(expected_dims):
        raise ValueError(f"SignalBlock dimensions {signal_block.dims} do not match expected {expected_dims}.")

def summarize_signal_block(signal_block: SignalBlock) -> Dict[str, Any]:
    """
    Summarizes the metadata and shape properties of a SignalBlock.
    Does not make any biological interpretation.
    """
    errors = signal_block.validate()
    if errors:
        raise ValueError(f"SignalBlock validation failed: {errors}")
        
    shape = signal_block.data.shape if hasattr(signal_block.data, "shape") else (0, 0, 0)
    n_trials = shape[0] if len(shape) >= 1 else 0
    n_units_or_channels = shape[1] if len(shape) >= 2 else 0
    n_time = shape[2] if len(shape) >= 3 else 0
    
    return {
        "signal_class": signal_block.signal_class,
        "session_id": signal_block.session_id,
        "condition": signal_block.condition,
        "dims": tuple(signal_block.dims),
        "shape": shape,
        "time_base": signal_block.time_base,
        "alignment_event": signal_block.alignment_event,
        "window_ms": signal_block.window_ms,
        "baseline_ms": signal_block.baseline_ms,
        "sampling_rate": signal_block.sampling_rate,
        "n_trials": n_trials,
        "n_units_or_channels": n_units_or_channels,
        "n_time": n_time,
        "area_labels": list(signal_block.area_labels),
        "warnings": list(signal_block.warnings),
        "truth_status": signal_block.truth_status
    }

def split_signal_axis(signal_block: SignalBlock) -> Dict[str, int]:
    """
    Returns axis indices for trial/unit-or-channel/time by explicitly parsing the dims.
    Explicitly distinguishes between unit and channel axes.
    """
    dims = signal_block.dims
    res = {
        "trial_axis": -1,
        "unit_axis": -1,
        "channel_axis": -1,
        "time_axis": -1
    }
    for idx, dim in enumerate(dims):
        if dim == "trial":
            res["trial_axis"] = idx
        elif dim == "unit":
            res["unit_axis"] = idx
        elif dim == "channel":
            res["channel_axis"] = idx
        elif dim == "time":
            res["time_axis"] = idx
            
    return res
