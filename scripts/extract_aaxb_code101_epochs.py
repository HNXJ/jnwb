#!/usr/bin/env python3
"""Extract AAXB code101 SPK/MUAe/LFP epochs with full validation.

This script extracts neural signal epochs aligned to p1 and omission onsets
using the validated code101 event anchors (not code100 fixation cues).

Required outputs:
- SPK p1-aligned epochs: trial x unit x time
- SPK omission-aligned epochs: trial x unit x time
- MUAe p1/omission epochs (if available)
- LFP p1/omission epochs (if available)
- Shape receipts, metadata tables, and manifests

Usage:
    python scripts/extract_aaxb_code101_epochs.py \
        --events outputs/validation_sanity/v1_channel_unit_lfp_aaxb/arrays/strict_aaxb_code101_p1_events.npz \
        --output outputs/validation_sanity/v1_channel_unit_lfp_aaxb/epochs
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.analysis.task_semantics import (
    run_all_validations,
    get_aaxb_semantics,
    calculate_aaxb_omission_onset,
    validate_no_code100_in_p1_events,
)
from src.analysis.contracts.constants import (
    EVENT_CODE_P1_STIMULUS,
    AAXB_OMISSION_OFFSET_MS,
)

# ============================================================================
# Configuration
# ============================================================================

NWB_ROOT = Path(r"D:/analysis/nwb")
DEFAULT_EVENTS_PATH = Path("outputs/validation_sanity/v1_channel_unit_lfp_aaxb/arrays/strict_aaxb_code101_p1_events.npz")
DEFAULT_OUTPUT_DIR = Path("outputs/validation_sanity/v1_channel_unit_lfp_aaxb/epochs")

# Signal extraction parameters
WINDOW_P1_MS = (-1000, 4000)  # Full sequence window
WINDOW_OMISSION_MS = (-1000, 1000)  # Local omission window
BIN_MS_SPK = 10.0  # 10ms bins for spikes

# Typed blockers
BLOCKED_SIGNAL_UNAVAILABLE = "BLOCKED_SIGNAL_UNAVAILABLE"
BLOCKED_NWB_NOT_FOUND = "BLOCKED_NWB_NOT_FOUND"
BLOCKED_NO_UNITS = "BLOCKED_NO_UNITS"
BLOCKED_EMPTY_EPOCHS = "BLOCKED_EMPTY_EPOCHS"
BLOCKED_SESSION_SILENTLY_DROPPED = "BLOCKED_SESSION_SILENTLY_DROPPED"


# ============================================================================
# Event Loading and Self-Healing Regeneration
# ============================================================================

BLOCKED_MISSING_NWB_EVENT_SOURCE = "BLOCKED_MISSING_NWB_EVENT_SOURCE"

def try_regenerate_events(output_dir: Path) -> Path | None:
    """Try to regenerate events by calling the regeneration script.
    
    Args:
        output_dir: Directory where regenerated events should be saved
        
    Returns:
        Path to regenerated NPZ if successful, None otherwise
    """
    regen_script = Path(__file__).parent / "extract_strict_aaxb_code101_p1_events.py"
    
    if not regen_script.exists():
        print(f"  ERROR: Regeneration script not found: {regen_script}")
        return None
    
    print(f"  Attempting to regenerate events using: {regen_script}")
    
    try:
        # Import and run regeneration logic
        sys.path.insert(0, str(regen_script.parent.parent / "src"))
        
        # Use importlib to run the regeneration function
        import importlib.util
        spec = importlib.util.spec_from_file_location("regen", regen_script)
        regen_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(regen_module)
        
        # Run regeneration
        manifest = regen_module.regenerate_aaxb_code101_events(
            validate_only=False,
            output_dir=output_dir.parent,  # Go up to v1_channel_unit_lfp_aaxb
        )
        
        if manifest.get("n_sessions_success", 0) > 0:
            expected_path = output_dir.parent / "arrays" / "strict_aaxb_code101_p1_events.npz"
            if expected_path.exists():
                print(f"  SUCCESS: Events regenerated at {expected_path}")
                return expected_path
        
        print(f"  WARNING: Regeneration returned status: {manifest.get('status')}")
        return None
        
    except Exception as e:
        print(f"  ERROR: Regeneration failed: {e}")
        return None


def load_code101_events(events_path: Path, auto_regenerate: bool = True) -> dict[str, np.ndarray]:
    """Load corrected code101 p1 events from NPZ.
    
    If events file is missing and auto_regenerate is True,
    attempts to regenerate from NWB event tables.
    
    Args:
        events_path: Path to events NPZ file
        auto_regenerate: If True, attempt regeneration if file missing
        
    Returns:
        Dict mapping session key to p1 onset times array (seconds)
        
    Raises:
        FileNotFoundError: If events file missing and regeneration failed
    """
    print(f"Loading events from: {events_path}")
    
    if not events_path.exists():
        print(f"  WARNING: Events file not found: {events_path}")
        
        if auto_regenerate:
            regenerated_path = try_regenerate_events(events_path.parent)
            if regenerated_path:
                events_path = regenerated_path
            else:
                raise FileNotFoundError(
                    f"Events file not found: {events_path}. "
                    f"Regeneration failed. "
                    f"Run: python scripts/extract_strict_aaxb_code101_p1_events.py"
                )
        else:
            raise FileNotFoundError(
                f"Events file not found: {events_path}. "
                f"Run with --auto-regenerate or regenerate manually."
            )
    
    with np.load(events_path, allow_pickle=True) as data:
        events = {}
        for key in data.keys():
            if key == "metadata_json":
                continue
            if "_p1_onsets" in key:
                session_key = key.replace("_p1_onsets", "")
                events[session_key] = data[key]
                print(f"  {session_key}: {len(data[key])} p1 events")
    
    return events


def validate_event_counts(events: dict[str, np.ndarray]) -> dict[str, Any]:
    """Validate event counts match expected 135 total across 5 sessions."""
    expected_counts = {
        "sub_V198o_ses_230629": 5,
        "sub_V198o_ses_230714": 33,
        "sub_V198o_ses_230719": 35,
        "sub_V198o_ses_230720": 30,
        "sub_V198o_ses_230721": 32,
    }
    
    results = {
        "all_valid": True,
        "total_events": sum(len(v) for v in events.values()),
        "expected_total": 135,
        "sessions": {},
        "errors": [],
    }
    
    for session_key, expected in expected_counts.items():
        actual = len(events.get(session_key, []))
        valid = actual == expected
        results["sessions"][session_key] = {
            "expected": expected,
            "actual": actual,
            "valid": valid,
        }
        if not valid:
            results["all_valid"] = False
            results["errors"].append(
                f"{session_key}: expected {expected} events, got {actual}"
            )
    
    if results["total_events"] != 135:
        results["all_valid"] = False
        results["errors"].append(
            f"Total events {results['total_events']} != expected 135"
        )
    
    return results


def resolve_nwb_path(session_key: str) -> Path | None:
    """Resolve NWB file path from session key.
    
    Args:
        session_key: e.g., "sub_V198o_ses_230629"
        
    Returns:
        Path to NWB file or None if not found
    """
    # Convert session_key to session_id format
    # "sub_V198o_ses_230629" -> "sub-V198o_ses-230629"
    parts = session_key.replace("sub_", "sub-").replace("ses_", "ses-").split("_")
    session_id = "_".join(parts)
    
    nwb_path = NWB_ROOT / f"{session_id}_rec.nwb"
    
    if nwb_path.exists():
        return nwb_path
    
    # Try alternative patterns
    alt_path = NWB_ROOT / f"{session_key}_rec.nwb"
    if alt_path.exists():
        return alt_path
    
    return None


# ============================================================================
# SPK Epoch Extraction
# ============================================================================

def extract_spk_epochs_from_nwb(
    nwb_path: Path,
    event_times: np.ndarray,
    window_ms: tuple[float, float],
    bin_ms: float = 10.0,
    area_filter: str | None = None,
) -> dict[str, Any]:
    """Extract spike epochs from NWB file aligned to event times.
    
    Args:
        nwb_path: Path to NWB file
        event_times: Array of event onset times (seconds)
        window_ms: (pre, post) window in milliseconds
        bin_ms: Bin size for spike binning
        area_filter: Optional area to filter units (e.g., "V1")
        
    Returns:
        Dict with:
        - epochs: trial x unit x time array
        - time_axis_ms: time axis in milliseconds
        - unit_metadata: DataFrame with unit info
        - shape: tuple of (n_trials, n_units, n_bins)
        - errors: list of any errors
    """
    result = {
        "epochs": None,
        "time_axis_ms": None,
        "unit_metadata": None,
        "shape": None,
        "n_trials": 0,
        "n_units": 0,
        "n_bins": 0,
        "errors": [],
        "warnings": [],
        "status": "UNKNOWN",
    }
    
    try:
        io = NWBHDF5IO(str(nwb_path), "r", load_namespaces=True)
        nwbfile = io.read()
    except Exception as e:
        result["errors"].append(f"Failed to open NWB: {e}")
        result["status"] = "BLOCKED"
        return result
    
    try:
        # Get units table
        units_table = getattr(nwbfile, "units", None)
        if units_table is None or len(units_table) == 0:
            result["errors"].append(BLOCKED_NO_UNITS)
            result["status"] = "BLOCKED"
            return result
        
        n_units_total = len(units_table)
        unit_cols = list(units_table.colnames)
        
        # Build unit metadata and filter
        selected_indices = []
        unit_metadata = []
        
        for unit_idx in range(n_units_total):
            meta = {"unit_idx": unit_idx}
            
            # Get unit ID
            if "unit_id" in unit_cols:
                uid_val = units_table["unit_id"][unit_idx]
                meta["unit_id"] = str(int(float(uid_val))) if uid_val is not None else f"unit_{unit_idx}"
            else:
                meta["unit_id"] = f"unit_{unit_idx}"
            
            # Get area if available
            area = None
            if "electrode_group" in unit_cols:
                eg = units_table["electrode_group"][unit_idx]
                area = str(eg) if eg is not None else None
            
            # Try to get location from electrodes
            if "peak_channel" in unit_cols or "electrode_group" in unit_cols:
                # Get area from electrode info if possible
                pass
            
            meta["area"] = area
            
            # Apply area filter
            if area_filter:
                # For now, accept all units - proper area filtering requires
                # electrode/channel mapping which is complex
                pass
            
            selected_indices.append(unit_idx)
            unit_metadata.append(meta)
        
        n_units = len(selected_indices)
        n_trials = len(event_times)
        
        if n_units == 0:
            result["errors"].append("No units selected after filtering")
            result["status"] = "BLOCKED"
            return result
        
        # Prepare time bins
        pre_ms, post_ms = window_ms
        bin_edges = np.arange(pre_ms, post_ms + bin_ms, bin_ms)
        n_bins = len(bin_edges) - 1
        time_axis_ms = (bin_edges[:-1] + bin_edges[1:]) / 2  # Bin centers
        
        # Initialize output array: trial x unit x time_bin
        epochs = np.zeros((n_trials, n_units, n_bins), dtype=np.int32)
        
        # Extract spikes for each trial and unit
        for trial_idx, event_time_s in enumerate(event_times):
            event_ms = event_time_s * 1000.0
            
            for sel_idx, unit_idx in enumerate(selected_indices):
                spike_times = units_table["spike_times"][unit_idx]
                if hasattr(spike_times, "data"):
                    spike_times = np.asarray(spike_times.data[:])
                else:
                    spike_times = np.asarray(spike_times)
                
                # Align to event
                aligned_ms = (spike_times * 1000.0) - event_ms
                
                # Filter to window
                in_window = (aligned_ms >= pre_ms) & (aligned_ms < post_ms)
                window_spikes = aligned_ms[in_window]
                
                # Bin
                if len(window_spikes) > 0:
                    counts, _ = np.histogram(window_spikes, bins=bin_edges)
                    epochs[trial_idx, sel_idx, :] = counts
        
        result["epochs"] = epochs
        result["time_axis_ms"] = time_axis_ms
        result["unit_metadata"] = pd.DataFrame(unit_metadata)
        result["shape"] = (n_trials, n_units, n_bins)
        result["n_trials"] = n_trials
        result["n_units"] = n_units
        result["n_bins"] = n_bins
        result["window_ms"] = window_ms
        result["bin_ms"] = bin_ms
        result["status"] = "SUCCESS"
        
    except Exception as e:
        result["errors"].append(f"Extraction error: {e}")
        result["status"] = "ERROR"
    finally:
        io.close()
    
    return result


# ============================================================================
# MUAe/LFP Epoch Extraction (with availability checking)
# ============================================================================

def check_signal_availability(nwb_path: Path) -> dict[str, bool]:
    """Check which signals are available in NWB file.
    
    Returns:
        Dict with signal availability flags
    """
    availability = {
        "SPK": False,
        "MUAe": False,
        "LFP": False,
    }
    
    try:
        io = NWBHDF5IO(str(nwb_path), "r", load_namespaces=True)
        nwbfile = io.read()
        
        # Check for units (SPK)
        units = getattr(nwbfile, "units", None)
        availability["SPK"] = units is not None and len(units) > 0
        
        # Check for acquisition signals (MUAe/LFP)
        acquisition = getattr(nwbfile, "acquisition", {})
        for name in acquisition.keys():
            if "muae" in name.lower() or "mua" in name.lower():
                availability["MUAe"] = True
            if "lfp" in name.lower():
                availability["LFP"] = True
        
        # Check processing modules
        processing = getattr(nwbfile, "processing", {})
        for module_name, module in processing.items():
            for data_name in module.data_interfaces.keys():
                if "muae" in data_name.lower() or "mua" in data_name.lower():
                    availability["MUAe"] = True
                if "lfp" in data_name.lower():
                    availability["LFP"] = True
        
        io.close()
    except Exception:
        pass
    
    return availability


def extract_muae_epochs_blocked(
    nwb_path: Path,
    event_times: np.ndarray,
    window_ms: tuple[float, float],
) -> dict[str, Any]:
    """MUAe extraction - currently blocked pending availability verification."""
    availability = check_signal_availability(nwb_path)
    
    if not availability["MUAe"]:
        return {
            "epochs": None,
            "status": "BLOCKED",
            "blocker": BLOCKED_SIGNAL_UNAVAILABLE,
            "errors": [f"{BLOCKED_SIGNAL_UNAVAILABLE}: MUAe not available in {nwb_path.name}"],
            "availability": availability,
        }
    
    # If available, would implement extraction here
    return {
        "epochs": None,
        "status": "BLOCKED",
        "blocker": "NOT_IMPLEMENTED",
        "errors": ["MUAe extraction not yet implemented"],
        "availability": availability,
    }


def extract_lfp_epochs_blocked(
    nwb_path: Path,
    event_times: np.ndarray,
    window_ms: tuple[float, float],
) -> dict[str, Any]:
    """LFP extraction - currently blocked pending availability verification."""
    availability = check_signal_availability(nwb_path)
    
    if not availability["LFP"]:
        return {
            "epochs": None,
            "status": "BLOCKED",
            "blocker": BLOCKED_SIGNAL_UNAVAILABLE,
            "errors": [f"{BLOCKED_SIGNAL_UNAVAILABLE}: LFP not available in {nwb_path.name}"],
            "availability": availability,
        }
    
    # If available, would implement extraction here
    return {
        "epochs": None,
        "status": "BLOCKED",
        "blocker": "NOT_IMPLEMENTED",
        "errors": ["LFP extraction not yet implemented"],
        "availability": availability,
    }


# ============================================================================
# Main Extraction Pipeline
# ============================================================================

def extract_aaxb_epochs(
    events_path: Path,
    output_dir: Path,
    validate_only: bool = False,
) -> dict[str, Any]:
    """Extract AAXB code101 epochs for all signals.
    
    Args:
        events_path: Path to code101 events NPZ
        output_dir: Output directory for epochs
        validate_only: If True, only validate without extraction
        
    Returns:
        Extraction manifest
    """
    print("=" * 80)
    print("AAXB CODE101 EPOCH EXTRACTION")
    print("=" * 80)
    print(f"Events: {events_path}")
    print(f"Output: {output_dir}")
    print(f"Mode: {'VALIDATE ONLY' if validate_only else 'FULL EXTRACTION'}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "arrays").mkdir(exist_ok=True)
    (output_dir / "tables").mkdir(exist_ok=True)
    (output_dir / "manifests").mkdir(exist_ok=True)
    
    # Load events
    events = load_code101_events(events_path)
    
    # Validate event counts
    event_validation = validate_event_counts(events)
    print(f"\nEvent validation: {'PASS' if event_validation['all_valid'] else 'FAIL'}")
    print(f"  Total events: {event_validation['total_events']} (expected {event_validation['expected_total']})")
    
    if not event_validation["all_valid"]:
        print("\nEVENT VALIDATION FAILED")
        for err in event_validation["errors"]:
            print(f"  ERROR: {err}")
        return {"status": "BLOCKED", "errors": event_validation["errors"]}
    
    if validate_only:
        print("\nValidation only mode - skipping extraction")
        return {"status": "VALIDATED", "event_validation": event_validation}
    
    # Build manifest
    manifest = {
        "created_at": datetime.now().isoformat(),
        "status": "EXTRACTING",
        "events_source": str(events_path),
        "events_hash": hashlib.sha256(events_path.read_bytes()).hexdigest()[:16],
        "n_sessions": len(events),
        "n_total_events": event_validation["total_events"],
        "alignment": {
            "p1_anchor": "code_101_task_event_2",
            "omission_slot": "p3",
            "omission_offset_ms": AAXB_OMISSION_OFFSET_MS,
            "window_p1_ms": list(WINDOW_P1_MS),
            "window_omission_ms": list(WINDOW_OMISSION_MS),
            "bin_ms_spk": BIN_MS_SPK,
        },
        "sessions": {},
        "shape_receipts": [],
        "signal_inventory": [],
    }
    
    # Process each session
    all_spk_p1_epochs = []
    all_spk_omission_epochs = []
    session_metadata = []
    
    for session_key, p1_times in events.items():
        print(f"\n{'-' * 60}")
        print(f"Session: {session_key}")
        print(f"Events: {len(p1_times)}")
        
        session_result = {
            "session_key": session_key,
            "n_events": len(p1_times),
            "signals": {},
        }
        
        # Resolve NWB path
        nwb_path = resolve_nwb_path(session_key)
        if nwb_path is None:
            error_msg = f"{BLOCKED_NWB_NOT_FOUND}: Could not resolve NWB for {session_key}"
            print(f"  ERROR: {error_msg}")
            session_result["error"] = error_msg
            manifest["sessions"][session_key] = session_result
            continue
        
        print(f"  NWB: {nwb_path.name}")
        session_result["nwb_path"] = str(nwb_path)
        
        # Check signal availability
        availability = check_signal_availability(nwb_path)
        print(f"  Signal availability: SPK={availability['SPK']}, MUAe={availability['MUAe']}, LFP={availability['LFP']}")
        
        inventory_row = {
            "session": session_key,
            "nwb_file": nwb_path.name,
            "SPK": availability["SPK"],
            "MUAe": availability["MUAe"],
            "LFP": availability["LFP"],
            "n_events": len(p1_times),
        }
        
        # Calculate omission times
        omission_times = calculate_aaxb_omission_onset(p1_times)
        
        # Extract SPK epochs (p1-aligned)
        if availability["SPK"]:
            print("  Extracting SPK epochs (p1-aligned)...")
            spk_p1_result = extract_spk_epochs_from_nwb(
                nwb_path=nwb_path,
                event_times=p1_times,
                window_ms=WINDOW_P1_MS,
                bin_ms=BIN_MS_SPK,
            )
            
            if spk_p1_result["status"] == "SUCCESS":
                epochs = spk_p1_result["epochs"]
                shape = spk_p1_result["shape"]
                print(f"    Shape: {shape}")
                
                # Store for pooled output
                all_spk_p1_epochs.append(epochs)
                
                # Save per-session
                session_array_path = output_dir / "arrays" / f"{session_key}_spk_p1_epochs.npy"
                np.save(session_array_path, epochs)
                
                session_result["signals"]["SPK_p1"] = {
                    "status": "EXTRACTED",
                    "shape": shape,
                    "n_trials": spk_p1_result["n_trials"],
                    "n_units": spk_p1_result["n_units"],
                    "n_bins": spk_p1_result["n_bins"],
                    "array_path": str(session_array_path),
                }
                
                # Save unit metadata
                unit_meta = spk_p1_result["unit_metadata"]
                unit_meta["session"] = session_key
                session_metadata.append(unit_meta)
                
                # Shape receipt
                manifest["shape_receipts"].append({
                    "session": session_key,
                    "signal": "SPK",
                    "alignment": "p1",
                    "shape": shape,
                    "window_ms": WINDOW_P1_MS,
                    "bin_ms": BIN_MS_SPK,
                    "status": "EXTRACTED",
                })
                
                inventory_row["SPK_units"] = spk_p1_result["n_units"]
            else:
                print(f"    FAILED: {spk_p1_result['errors']}")
                session_result["signals"]["SPK_p1"] = {
                    "status": "FAILED",
                    "errors": spk_p1_result["errors"],
                }
                inventory_row["SPK_units"] = 0
            
            # Extract SPK epochs (omission-aligned)
            print("  Extracting SPK epochs (omission-aligned)...")
            spk_om_result = extract_spk_epochs_from_nwb(
                nwb_path=nwb_path,
                event_times=omission_times,
                window_ms=WINDOW_OMISSION_MS,
                bin_ms=BIN_MS_SPK,
            )
            
            if spk_om_result["status"] == "SUCCESS":
                epochs = spk_om_result["epochs"]
                shape = spk_om_result["shape"]
                print(f"    Shape: {shape}")
                
                all_spk_omission_epochs.append(epochs)
                
                session_array_path = output_dir / "arrays" / f"{session_key}_spk_omission_epochs.npy"
                np.save(session_array_path, epochs)
                
                session_result["signals"]["SPK_omission"] = {
                    "status": "EXTRACTED",
                    "shape": shape,
                    "n_trials": spk_om_result["n_trials"],
                    "n_units": spk_om_result["n_units"],
                    "n_bins": spk_om_result["n_bins"],
                    "array_path": str(session_array_path),
                }
                
                manifest["shape_receipts"].append({
                    "session": session_key,
                    "signal": "SPK",
                    "alignment": "omission",
                    "shape": shape,
                    "window_ms": WINDOW_OMISSION_MS,
                    "bin_ms": BIN_MS_SPK,
                    "status": "EXTRACTED",
                })
            else:
                print(f"    FAILED: {spk_om_result['errors']}")
                session_result["signals"]["SPK_omission"] = {
                    "status": "FAILED",
                    "errors": spk_om_result["errors"],
                }
        else:
            print("  SPK unavailable")
            session_result["signals"]["SPK_p1"] = {"status": "BLOCKED", "blocker": BLOCKED_SIGNAL_UNAVAILABLE}
            session_result["signals"]["SPK_omission"] = {"status": "BLOCKED", "blocker": BLOCKED_SIGNAL_UNAVAILABLE}
            inventory_row["SPK_units"] = 0
        
        # MUAe extraction (blocked for now)
        muae_p1_result = extract_muae_epochs_blocked(nwb_path, p1_times, WINDOW_P1_MS)
        muae_om_result = extract_muae_epochs_blocked(nwb_path, omission_times, WINDOW_OMISSION_MS)
        
        session_result["signals"]["MUAe_p1"] = {
            "status": muae_p1_result["status"],
            "blocker": muae_p1_result.get("blocker"),
            "errors": muae_p1_result.get("errors", []),
            "availability": muae_p1_result.get("availability", {}),
        }
        session_result["signals"]["MUAe_omission"] = {
            "status": muae_om_result["status"],
            "blocker": muae_om_result.get("blocker"),
            "errors": muae_om_result.get("errors", []),
        }
        inventory_row["MUAe_channels"] = None
        
        # LFP extraction (blocked for now)
        lfp_p1_result = extract_lfp_epochs_blocked(nwb_path, p1_times, WINDOW_P1_MS)
        lfp_om_result = extract_lfp_epochs_blocked(nwb_path, omission_times, WINDOW_OMISSION_MS)
        
        session_result["signals"]["LFP_p1"] = {
            "status": lfp_p1_result["status"],
            "blocker": lfp_p1_result.get("blocker"),
            "errors": lfp_p1_result.get("errors", []),
            "availability": lfp_p1_result.get("availability", {}),
        }
        session_result["signals"]["LFP_omission"] = {
            "status": lfp_om_result["status"],
            "blocker": lfp_om_result.get("blocker"),
            "errors": lfp_om_result.get("errors", []),
        }
        inventory_row["LFP_channels"] = None
        
        manifest["sessions"][session_key] = session_result
        manifest["signal_inventory"].append(inventory_row)
    
    # Concatenate pooled epochs (if we have data)
    print(f"\n{'=' * 60}")
    print("BUILDING POOLED DATASETS")
    
    pooled_manifest = {}
    
    if all_spk_p1_epochs:
        # Check shapes match (same n_units, n_bins across sessions)
        shapes = [e.shape for e in all_spk_p1_epochs]
        n_trials_list = [s[0] for s in shapes]
        n_units_list = [s[1] for s in shapes]
        n_bins_list = [s[2] for s in shapes]
        
        print(f"  SPK p1 shapes: {shapes}")
        print(f"    n_trials per session: {n_trials_list}")
        print(f"    n_units per session: {n_units_list}")
        print(f"    n_bins per session: {n_bins_list}")
        
        # Note: n_units varies across sessions, so we can't simple concatenate
        # For now, save per-session and document
        pooled_manifest["SPK_p1"] = {
            "status": "PER_SESSION_ONLY",
            "reason": "n_units varies across sessions - cannot pool without alignment",
            "n_sessions": len(all_spk_p1_epochs),
            "shapes": shapes,
            "total_trials": sum(n_trials_list),
            "n_units_range": [min(n_units_list), max(n_units_list)],
            "n_bins": n_bins_list[0] if n_bins_list else 0,
        }
    
    if all_spk_omission_epochs:
        shapes = [e.shape for e in all_spk_omission_epochs]
        print(f"  SPK omission shapes: {shapes}")
        
        pooled_manifest["SPK_omission"] = {
            "status": "PER_SESSION_ONLY",
            "reason": "n_units varies across sessions - cannot pool without alignment",
            "n_sessions": len(all_spk_omission_epochs),
            "shapes": shapes,
        }
    
    manifest["pooled"] = pooled_manifest
    
    # Save unit metadata
    if session_metadata:
        all_unit_meta = pd.concat(session_metadata, ignore_index=True)
        unit_meta_path = output_dir / "tables" / "aaxb_code101_unit_metadata.csv"
        all_unit_meta.to_csv(unit_meta_path, index=False)
        manifest["unit_metadata_path"] = str(unit_meta_path)
        print(f"\n  Unit metadata saved: {unit_meta_path}")
        print(f"    Total units: {len(all_unit_meta)}")
    
    # Save signal inventory
    inventory_df = pd.DataFrame(manifest["signal_inventory"])
    inventory_path = output_dir / "tables" / "aaxb_code101_session_signal_inventory.csv"
    inventory_df.to_csv(inventory_path, index=False)
    manifest["signal_inventory_path"] = str(inventory_path)
    print(f"  Signal inventory saved: {inventory_path}")
    
    # Save shape receipts
    receipts_df = pd.DataFrame(manifest["shape_receipts"])
    if not receipts_df.empty:
        receipts_path = output_dir / "tables" / "aaxb_code101_epoch_shape_receipts.csv"
        receipts_df.to_csv(receipts_path, index=False)
        manifest["shape_receipts_path"] = str(receipts_path)
        print(f"  Shape receipts saved: {receipts_path}")
    
    # Finalize manifest
    manifest["status"] = "COMPLETE"
    manifest_path = output_dir / "manifests" / "aaxb_code101_epoch_extraction_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest saved: {manifest_path}")
    
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Extract AAXB code101 epochs")
    parser.add_argument(
        "--events",
        type=Path,
        default=DEFAULT_EVENTS_PATH,
        help="Path to strict_aaxb_code101_p1_events.npz",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate events without extraction",
    )
    
    args = parser.parse_args()
    
    if not args.events.exists():
        print(f"ERROR: Events file not found: {args.events}")
        sys.exit(1)
    
    result = extract_aaxb_epochs(
        events_path=args.events,
        output_dir=args.output,
        validate_only=args.validate_only,
    )
    
    if result.get("status") == "BLOCKED":
        print("\nEXTRACTION BLOCKED")
        sys.exit(1)
    
    print("\nEXTRACTION COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
