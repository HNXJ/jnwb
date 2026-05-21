# src/analysis/contracts/fixture_signal_blocks.py
"""
Phase 2G Pure Synthetic/Fixture SignalBlock Loader Scaffolds.
Provides pure in-memory fixture SignalBlock generation without raw neural file access.
"""

import numpy as np
from typing import Optional, List, Tuple, Dict, Any, Union
from src.analysis.contracts.signal_block import SignalBlock, make_signal_block
from src.analysis.contracts.constants import (
    TRUTH_SAFE_UNVERIFIED,
    DEFAULT_SAMPLING_RATES,
    SIGNAL_CLASS_DIMS,
    CANONICAL_AREA_ORDER
)

def _normalize_area(area: str) -> str:
    """Normalizes DP to V4 according to contract rules."""
    area = area.strip()
    if area in ["DP", "DP (V4)"]:
        return "V4"
    return area

def make_fixture_signal_block(
    signal_class: str,
    session_id: str = "fixture_session",
    condition: str = "AAAB",
    n_trials: int = 2,
    n_units_or_channels: int = 3,
    n_time: int = 10,
    time_base: str = "p1_relative",
    alignment_event: str = "p1_onset",
    window_ms: Tuple[int, int] = (-1000, 4000),
    baseline_ms: Optional[Tuple[int, int]] = None,
    sampling_rate: Optional[float] = None,
    area_labels: Optional[List[str]] = None,
    area_resolution_status: Optional[Union[List[str], Dict[str, str]]] = None,
    fill_value: float = 0.0
) -> SignalBlock:
    """
    Creates a pure synthetic SignalBlock for fixture testing without reading raw file arrays.
    """
    # 1. Determine Dimensions
    if signal_class in ["SPK", "SUA"]:
        dims = ("trial", "unit", "time")
    elif signal_class in ["MUAe", "LFP"]:
        dims = ("trial", "channel", "time")
    else:
        # Let it default or raise during SignalBlock.validate()
        dims = ("trial", "channel", "time")

    # 2. Allocate small constant array
    data = np.full((n_trials, n_units_or_channels, n_time), fill_value, dtype=np.float32)

    # 3. Generate Unit or Channel IDs
    if signal_class in ["SPK", "SUA"]:
        unit_or_channel_ids = [f"{session_id}_unit_{i}" for i in range(n_units_or_channels)]
    else:
        unit_or_channel_ids = [f"{session_id}_ch_{i}" for i in range(n_units_or_channels)]

    # 4. Generate & Normalize Area Labels
    if area_labels is None:
        area_labels = [CANONICAL_AREA_ORDER[i % len(CANONICAL_AREA_ORDER)] for i in range(n_units_or_channels)]
    else:
        area_labels = [_normalize_area(a) for a in area_labels]

    # 5. Resolve Area Resolution Status Dict
    resolved_status_dict = {}
    if area_resolution_status is not None:
        if isinstance(area_resolution_status, dict):
            resolved_status_dict = area_resolution_status
        elif isinstance(area_resolution_status, list):
            for i, uid in enumerate(unit_or_channel_ids):
                status = area_resolution_status[i % len(area_resolution_status)]
                resolved_status_dict[uid] = status
    else:
        resolved_status_dict = {uid: "fixture_synthetic" for uid in unit_or_channel_ids}

    # 6. Retrieve Default Sampling Rates
    if sampling_rate is None:
        if signal_class in ["SPK", "SUA"]:
            sampling_rate = 30000.0
        else:
            sampling_rate = 1000.0

    # 7. Establish Provenance
    provenance = {
        "type": "fixture_synthetic",
        "message": "no raw data read",
        "n_trials": n_trials,
        "n_time": n_time,
        "n_units_or_channels": n_units_or_channels
    }

    # 8. Create and validate the block
    block = make_signal_block(
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
        area_resolution_status=resolved_status_dict,
        source_files=[],
        provenance=provenance,
        truth_status=TRUTH_SAFE_UNVERIFIED
    )

    return block

def make_fixture_signal_blocks_for_all_signals(
    session_id: str = "fixture_session",
    condition: str = "AAAB",
    n_trials: int = 2,
    n_units_or_channels: int = 3,
    n_time: int = 10,
    time_base: str = "p1_relative",
    alignment_event: str = "p1_onset",
    window_ms: Tuple[int, int] = (-1000, 4000),
    baseline_ms: Optional[Tuple[int, int]] = None,
    area_labels: Optional[List[str]] = None,
    fill_value: float = 0.0
) -> Dict[str, SignalBlock]:
    """Helper to return SPK, MUAe, LFP fixture blocks."""
    blocks = {}
    for sig_class in ["SPK", "MUAe", "LFP"]:
        blocks[sig_class] = make_fixture_signal_block(
            signal_class=sig_class,
            session_id=session_id,
            condition=condition,
            n_trials=n_trials,
            n_units_or_channels=n_units_or_channels,
            n_time=n_time,
            time_base=time_base,
            alignment_event=alignment_event,
            window_ms=window_ms,
            baseline_ms=baseline_ms,
            area_labels=area_labels,
            fill_value=fill_value
        )
    return blocks
