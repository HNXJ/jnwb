"""Event timing extraction and storage for analysis recipes.

Refined API for event vectors: function-first, NPZ primary storage, JSON sidecar, CSV optional.

Runtime: dict[str, np.ndarray]
Disk cache: .npz (compressed binary)
Debug/provenance: .json (human-readable)
CSV: optional export only (long-table format)
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from src.analysis.io.nwb_address import (
    get_event_timing_vectors as _get_event_timing_vectors,
    CANONICAL_CONDITIONS,
)


def get_event_timing_vectors(
    nwb_path: str | Path,
    event: str = "p1",
    conditions: Sequence[str] | None = None,
) -> dict[str, np.ndarray]:
    """Extract event timing vectors from NWB.
    
    This is the PRIMARY runtime API. Returns in-memory ndarrays.
    No file is written unless explicitly requested via save functions.
    
    Parameters
    ----------
    nwb_path : Path to NWB file
    event : Event marker to align to ("p1" or "flash")
    conditions : Condition codes to extract (default: all 12 canonical)
    
    Returns
    -------
    dict[str, np.ndarray]
        Mapping condition -> onset times (float64, seconds, NWB time base)
        Each array is 1D with shape (n_trials,)
    
    Shape expectations:
    - Output: {condition: np.ndarray(trials,) for condition in conditions}
    - Dtype: float64
    - Unit: seconds
    - Time base: NWB (typically relative to trial or session start)
    
    Trial structure:
    - Event order preserved from NWB intervals table
    - No trial averaging
    - Empty conditions return empty arrays (not omitted)
    
    Typed blockers:
    - RuntimeError with "BLOCKED_EVENTS_TABLE_MISSING"
    - RuntimeError with "BLOCKED_CONDITION_LABELS_MISSING"
    - RuntimeError with "BLOCKED_P1_ONSETS_MISSING"
    - RuntimeError with "BLOCKED_FLASH_ONSETS_MISSING"
    
    Example
    -------
    >>> events = get_event_timing_vectors("sub-C31o.nwb", event="p1")
    >>> events["AAAB"].shape
    (605,)
    >>> events["AAAB"][:3]
    array([11.796033, 16.678667, 16.688267])
    """
    return _get_event_timing_vectors(nwb_path, event=event, conditions=conditions)


def save_event_timing_vectors_npz(
    event_vectors: dict[str, np.ndarray],
    out_path: str | Path,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Save event timing vectors to NPZ format (compressed binary storage).
    
    This is the PRIMARY disk storage format. Fast, compact, preserves dtypes.
    
    NPZ structure:
        AAAB_          -> np.ndarray([t1, t2, ...], dtype=float64)
        AXAB_          -> np.ndarray([...])
        ...
        RRRX_          -> np.ndarray([...])
        metadata_json  -> np.array(json_string, dtype=str)
    
    Metadata JSON contents:
    {
        "time_unit": "seconds",
        "time_base": "NWB",
        "conditions": ["AAAB", "AXAB", ...],
        "counts_by_condition": {"AAAB": 605, ...},
        "nwb_file": "...",
        "subject_id": "...",
        "session_id": "...",
        "event": "p1",
        "saved_at_utc": "2026-06-08T..."
    }
    
    Parameters
    ----------
    event_vectors : dict[str, np.ndarray]
        Event vectors from get_event_timing_vectors()
    out_path : Destination path (should end in .npz)
    metadata : Optional additional metadata to embed
    
    Output spec
    -----------
    Preferred path format:
        outputs/data_index/event_timing_vectors_<subject>_<session>.npz
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build save dict: one array per condition
    save_dict: dict[str, np.ndarray] = {}
    
    # Store each condition vector
    for cond, times in event_vectors.items():
        # Sanitize key for NPZ (replace non-alphanumeric with underscore)
        safe_key = "".join(c if c.isalnum() else "_" for c in cond)
        # Ensure float64 dtype
        save_dict[safe_key] = np.asarray(times, dtype=np.float64)
    
    # Build metadata
    meta = dict(metadata) if metadata else {}
    
    # Auto-compute counts_by_condition if not provided
    if "counts_by_condition" not in meta:
        meta["counts_by_condition"] = {
            cond: len(times) for cond, times in event_vectors.items()
        }
    
    # Add standard fields
    meta["time_unit"] = meta.get("time_unit", "seconds")
    meta["time_base"] = meta.get("time_base", "NWB")
    meta["conditions"] = list(event_vectors.keys())
    meta["saved_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Embed metadata as JSON-serialized string
    meta_json = json.dumps(meta, indent=2)
    save_dict["metadata_json"] = np.array(meta_json, dtype=np.str_)
    
    # Save compressed
    np.savez_compressed(out_path, **save_dict)


def load_event_timing_vectors_npz(
    path: str | Path,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Load event timing vectors from NPZ format.
    
    Parameters
    ----------
    path : Path to .npz file
    
    Returns
    -------
    (event_vectors, metadata) where:
    - event_vectors: dict[str, np.ndarray] with original condition keys restored
    - metadata: dict with provenance information
    
    Restoration:
    - Original condition keys recovered from metadata["conditions"]
    - Sanitized keys mapped back (e.g., "AAAB_" -> "AAAB")
    """
    path = Path(path)
    
    with np.load(path, allow_pickle=False) as data:
        # Extract metadata
        metadata_json = str(data["metadata_json"])
        metadata = json.loads(metadata_json)
        
        # Extract event vectors (skip metadata_json key)
        event_vectors: dict[str, np.ndarray] = {}
        
        # Build reverse mapping from sanitized -> original
        conditions = metadata.get("conditions", [])
        sanitized_map = {
            "".join(c if c.isalnum() else "_" for c in cond): cond
            for cond in conditions
        }
        
        for key in data.files:
            if key == "metadata_json":
                continue
            # Restore original condition key
            original_key = sanitized_map.get(key, key)
            event_vectors[original_key] = data[key]
        
        return event_vectors, metadata


def save_event_timing_vectors_json(
    event_vectors: dict[str, np.ndarray],
    out_path: str | Path,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Save event timing vectors to JSON (human-readable, for debugging/provenance).
    
    This is for DEBUGGING and PROVENANCE, not primary storage.
    Use NPZ for normal analysis - this is slower and larger but human-readable.
    
    JSON structure:
    {
        "time_unit": "seconds",
        "time_base": "NWB",
        "conditions": ["AAAB", "AXAB", ...],
        "counts_by_condition": {"AAAB": 605, ...},
        "event_vectors": {
            "AAAB": [11.796033, 16.678667, ...],
            "AXAB": [...],
            ...
        },
        "metadata": {...},
        "saved_at_utc": "..."
    }
    
    Parameters
    ----------
    event_vectors : Event vectors from get_event_timing_vectors()
    out_path : Destination path (should end in .json)
    metadata : Optional additional metadata
    
    Use case:
    - Audit and inspection
    - Version control diffs (small files only)
    - Provenance documentation
    - Debugging
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    payload: dict[str, Any] = {
        "time_unit": "seconds",
        "time_base": "NWB",
        "conditions": list(event_vectors.keys()),
        "counts_by_condition": {
            cond: len(times) for cond, times in event_vectors.items()
        },
        "event_vectors": {
            cond: times.tolist() for cond, times in event_vectors.items()
        },
        "metadata": dict(metadata) if metadata else {},
        "saved_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def export_event_timing_vectors_csv(
    event_vectors: dict[str, np.ndarray],
    out_path: str | Path,
    event_name: str = "p1",
) -> None:
    """Export event timing vectors to CSV long-table format (for interoperability only).
    
    This is OPTIONAL and should NOT be used by downstream analysis code.
    Use NPZ for normal storage - CSV is only for external tool compatibility.
    
    CSV format (long-table):
        condition,event,onset_s,trial_index
        AAAB,p1,11.796033,0
        AAAB,p1,16.678667,1
        AXAB,p1,10.123456,0
        ...
    
    Why long-table:
    - Each row is one event occurrence
    - Unequal trial counts per condition are handled naturally
    - Standard format for pandas, R, Excel, etc.
    
    Parameters
    ----------
    event_vectors : Event vectors from get_event_timing_vectors()
    out_path : Destination path (should end in .csv)
    event_name : Event marker name for the event column
    
    Warning:
    - This creates redundant data (condition strings repeated)
    - Larger file size than NPZ
    - Slower to read/write
    - Only use for external tool export, not internal analysis
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    rows: list[dict[str, Any]] = []
    for cond, times in event_vectors.items():
        for trial_idx, onset_s in enumerate(times):
            rows.append({
                "condition": cond,
                "event": event_name,
                "onset_s": float(onset_s),
                "trial_index": trial_idx,
            })
    
    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
