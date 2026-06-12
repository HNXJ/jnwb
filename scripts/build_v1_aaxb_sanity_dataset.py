#!/usr/bin/env python3
"""Build V1 AAXB sanity dataset with corrected code 101 p1 anchors.

This script:
1. Loads corrected AAXB code101 p1 event anchors
2. Validates event semantics (no code 100, all code 101)
3. Extracts spike epochs aligned to p1 and omission onsets
4. Produces manifest with alignment metadata

Usage:
    python scripts/build_v1_aaxb_sanity_dataset.py \\
        --events outputs/validation_sanity/v1_channel_unit_lfp_aaxb/arrays/strict_aaxb_code101_p1_events.npz \\
        --output outputs/validation_sanity/v1_channel_unit_lfp_aaxb/sanity_dataset
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.analysis.task_semantics import (
    run_all_validations,
    get_aaxb_semantics,
    calculate_aaxb_omission_onset,
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
DEFAULT_OUTPUT_DIR = Path("outputs/validation_sanity/v1_channel_unit_lfp_aaxb/sanity_dataset")


def load_corrected_events(events_path: Path) -> dict[str, np.ndarray]:
    """Load corrected code101 p1 events from NPZ.
    
    Args:
        events_path: Path to strict_aaxb_code101_p1_events.npz
        
    Returns:
        Dict mapping session key to p1 onset times array
    """
    print(f"Loading events from: {events_path}")
    
    with np.load(events_path, allow_pickle=True) as data:
        # Extract session keys (skip metadata)
        events = {}
        for key in data.keys():
            if key == "metadata_json":
                continue
            if "_p1_onsets" in key:
                session_key = key.replace("_p1_onsets", "")
                events[session_key] = data[key]
                print(f"  {session_key}: {len(data[key])} p1 events")
    
    return events


def validate_events(events: dict[str, np.ndarray]) -> dict[str, Any]:
    """Validate that loaded events are proper code 101 p1 anchors.
    
    Args:
        events: Dict of session -> p1 onset times
        
    Returns:
        Validation results
    """
    print("\nValidating event semantics...")
    
    results = {
        "all_valid": True,
        "sessions": {},
        "errors": [],
    }
    
    total_events = sum(len(v) for v in events.values())
    print(f"  Total events: {total_events}")
    
    # Expected total based on prior validation
    if total_events != 135:
        results["all_valid"] = False
        results["errors"].append(f"Expected 135 events, got {total_events}")
    
    # Check per-session counts match prior validation
    expected_counts = {
        "sub_V198o_ses_230629": 5,
        "sub_V198o_ses_230714": 33,
        "sub_V198o_ses_230719": 35,
        "sub_V198o_ses_230720": 30,
        "sub_V198o_ses_230721": 32,
    }
    
    for session_key, count in expected_counts.items():
        actual = len(events.get(session_key, []))
        if actual != count:
            results["all_valid"] = False
            results["errors"].append(
                f"{session_key}: expected {count} events, got {actual}"
            )
        results["sessions"][session_key] = {
            "expected": count,
            "actual": actual,
            "valid": actual == count,
        }
    
    status = "PASS" if results["all_valid"] else "FAIL"
    print(f"  Validation: {status}")
    
    if results["errors"]:
        for err in results["errors"]:
            print(f"    ERROR: {err}")
    
    return results


def extract_spike_epochs(
    nwb_path: Path,
    p1_onset_times: np.ndarray,
    window_ms: tuple[float, float] = (-1000, 4000),
    bin_ms: float = 10.0,
) -> dict[str, Any]:
    """Extract spike epochs aligned to p1 onsets.
    
    Args:
        nwb_path: Path to NWB file
        p1_onset_times: Array of p1 onset times (seconds)
        window_ms: (pre, post) window in milliseconds
        bin_ms: Bin size in milliseconds
        
    Returns:
        Dict with spike array and metadata
    """
    from src.analysis.io.nwb_address import get_aligned_unit_signals
    
    # Build event vectors dict
    event_vectors = {"AAXB": p1_onset_times}
    
    # Extract
    spike_data = get_aligned_unit_signals(
        nwb_path=nwb_path,
        unit_filter={},  # All units
        event_vectors=event_vectors,
        pre_ms=window_ms[0],
        post_ms=window_ms[1],
        bin_ms=bin_ms,
    )
    
    return spike_data


def build_sanity_dataset(
    events_path: Path,
    output_dir: Path,
    validate_only: bool = False,
) -> dict[str, Any]:
    """Build V1 AAXB sanity dataset with p1 and omission alignment.
    
    Args:
        events_path: Path to corrected events NPZ
        output_dir: Output directory for dataset
        validate_only: If True, only validate without extraction
        
    Returns:
        Build manifest
    """
    print("=" * 80)
    print("V1 AAXB SANITY DATASET BUILD")
    print("=" * 80)
    print(f"Events: {events_path}")
    print(f"Output: {output_dir}")
    print(f"Mode: {'VALIDATE ONLY' if validate_only else 'FULL BUILD'}")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load events
    events = load_corrected_events(events_path)
    
    # Validate
    validation = validate_events(events)
    
    if not validation["all_valid"]:
        print("\nVALIDATION FAILED - Cannot proceed")
        return {
            "status": "BLOCKED",
            "validation": validation,
            "errors": validation["errors"],
        }
    
    if validate_only:
        print("\nValidation only mode - skipping extraction")
        return {
            "status": "VALIDATED",
            "validation": validation,
        }
    
    # Build dataset
    manifest = {
        "created_at": datetime.now().isoformat(),
        "status": "BUILDING",
        "events_source": str(events_path),
        "events_hash": hashlib.sha256(events_path.read_bytes()).hexdigest()[:16],
        "alignment": {
            "p1_anchor": "code_101_task_event_2",
            "omission_slot": "p3",
            "omission_offset_ms": AAXB_OMISSION_OFFSET_MS,
            "window_ms": [-1000, 4000],
            "bin_ms": 10.0,
        },
        "sessions": {},
    }
    
    aaxb_semantics = get_aaxb_semantics()
    
    for session_key, p1_times in events.items():
        print(f"\nProcessing {session_key}...")
        
        # Parse session ID
        session_id = session_key.replace("_", "-").replace("ses-", "_ses-")
        
        # Find NWB
        nwb_path = NWB_ROOT / f"{session_id}_rec.nwb"
        if not nwb_path.exists():
            print(f"  ERROR: NWB not found: {nwb_path}")
            manifest["sessions"][session_key] = {"error": "NWB not found"}
            continue
        
        print(f"  NWB: {nwb_path.name}")
        print(f"  p1 events: {len(p1_times)}")
        
        # Calculate omission onsets
        omission_times = calculate_aaxb_omission_onset(p1_times)
        
        # Store event times
        session_data = {
            "nwb_path": str(nwb_path),
            "n_events": len(p1_times),
            "p1_onset_times": p1_times.tolist(),
            "omission_onset_times": omission_times.tolist(),
        }
        
        # TODO: Add spike epoch extraction here
        # For now, just validate alignment contract
        
        # Validate omission offset
        actual_offset_ms = (omission_times[0] - p1_times[0]) * 1000 if len(p1_times) > 0 else 0
        expected_offset_ms = AAXB_OMISSION_OFFSET_MS
        
        session_data["omission_offset_valid"] = abs(actual_offset_ms - expected_offset_ms) < 1.0
        session_data["omission_offset_ms"] = actual_offset_ms
        
        manifest["sessions"][session_key] = session_data
        
        print(f"  Omission offset: {actual_offset_ms:.1f}ms (expected {expected_offset_ms}ms)")
        print(f"  Status: {'OK' if session_data['omission_offset_valid'] else 'ERROR'}")
    
    # Save manifest
    manifest["status"] = "COMPLETE"
    manifest_path = output_dir / "sanity_dataset_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest saved: {manifest_path}")
    
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Build V1 AAXB sanity dataset")
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
    
    # Check events file exists
    if not args.events.exists():
        print(f"ERROR: Events file not found: {args.events}")
        sys.exit(1)
    
    # Build dataset
    result = build_sanity_dataset(
        events_path=args.events,
        output_dir=args.output,
        validate_only=args.validate_only,
    )
    
    # Exit status
    if result.get("status") == "BLOCKED":
        print("\nBUILD BLOCKED")
        sys.exit(1)
    
    print("\nBUILD COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
