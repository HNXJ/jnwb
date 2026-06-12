#!/usr/bin/env python3
"""Regenerate strict AAXB code101 p1 event anchors from NWB event tables.

This script regenerates the corrected event artifact that was missing:
- Filters for AAXB condition (task_condition_number == 4)
- Filters for p1 stimulus onset (codes == 101)
- Filters for correct trials (correct == 1)
- Calculates omission onset: p1_onset + 2.062 seconds
- Validates no code100/fixation cue events are retained
- Saves deterministic outputs

Usage:
    python scripts/extract_strict_aaxb_code101_p1_events.py --validate
    python scripts/extract_strict_aaxb_code101_p1_events.py
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
    validate_no_code100_in_p1_events,
    validate_all_code101,
    validate_stimulus_number_2_for_code101,
    validate_not_stimulus_number_1,
    get_aaxb_semantics,
    calculate_aaxb_omission_onset,
    BLOCKED_CODE100_AS_P1,
)
from src.analysis.contracts.constants import (
    EVENT_CODE_P1_STIMULUS,
    EVENT_CODE_FIXATION_CUE,
    AAXB_CONDITION_NUMBER,
    AAXB_OMISSION_OFFSET_MS,
)


# ============================================================================
# Configuration
# ============================================================================

NWB_ROOT = Path(r"D:/analysis/nwb")
OUTPUT_ROOT = Path("outputs/validation_sanity/v1_channel_unit_lfp_aaxb")

# Expected sessions for AAXB code101 events
EXPECTED_SESSIONS = [
    ("sub-V198o", "ses-230629"),
    ("sub-V198o", "ses-230714"),
    ("sub-V198o", "ses-230719"),
    ("sub-V198o", "ses-230720"),
    ("sub-V198o", "ses-230721"),
]

# Typed blockers
BLOCKED_NWB_NOT_FOUND = "BLOCKED_NWB_NOT_FOUND"
BLOCKED_EVENTS_TABLE_MISSING = "BLOCKED_EVENTS_TABLE_MISSING"
BLOCKED_NO_AAXB_EVENTS = "BLOCKED_NO_AAXB_EVENTS"
BLOCKED_MISSING_NWB_EVENT_SOURCE = "BLOCKED_MISSING_NWB_EVENT_SOURCE"


# ============================================================================
# NWB Event Table Loading
# ============================================================================

def load_omission_events_from_nwb(nwb_path: Path) -> pd.DataFrame | None:
    """Load omission_glo_passive event table from NWB.
    
    Returns:
        DataFrame with event rows, or None if table missing
    """
    try:
        io = NWBHDF5IO(str(nwb_path), "r", load_namespaces=True)
        nwbfile = io.read()
    except Exception as e:
        print(f"  ERROR: Cannot open NWB: {e}")
        return None
    
    try:
        intervals = getattr(nwbfile, "intervals", None)
        if intervals is None:
            print(f"  ERROR: No intervals table in NWB")
            return None
        
        # Find omission_glo_passive table
        table_name = None
        for name in intervals.keys():
            if "omission" in name.lower():
                table_name = name
                break
        
        if table_name is None:
            print(f"  ERROR: No omission table found in intervals: {list(intervals.keys())}")
            return None
        
        table = intervals[table_name]
        
        # Convert to DataFrame
        data = {}
        for col in table.colnames:
            try:
                data[col] = table[col][:]
            except Exception as e:
                print(f"  WARNING: Could not read column {col}: {e}")
                data[col] = [None] * len(table)
        
        df = pd.DataFrame(data)
        df["_nwb_source"] = str(nwb_path)
        df["_table_name"] = table_name
        
        return df
        
    finally:
        io.close()


# ============================================================================
# Event Filtering and Validation
# ============================================================================

def filter_strict_aaxb_code101_events(df: pd.DataFrame) -> pd.DataFrame:
    """Filter DataFrame for strict AAXB code101 p1 events.
    
    Filters:
    - task_condition_number == 4 (AAXB)
    - codes == 101 (p1 stimulus onset)
    - correct == 1 (correct trials)
    
    Args:
        df: Raw event DataFrame from NWB
        
    Returns:
        Filtered DataFrame with only valid code101 p1 events
    """
    original_count = len(df)
    print(f"    Raw events: {original_count}")
    
    # Find condition column
    cond_col = None
    for col in ["task_condition_number", "condition", "condition_number"]:
        if col in df.columns:
            cond_col = col
            break
    
    if cond_col is None:
        raise ValueError("No condition column found in event table")
    
    print(f"    Using condition column: {cond_col}")
    
    # Find code column
    code_col = None
    for col in ["codes", "code", "event_code"]:
        if col in df.columns:
            code_col = col
            break
    
    if code_col is None:
        raise ValueError("No code column found in event table")
    
    print(f"    Using code column: {code_col}")
    
    # Find correct column
    correct_col = None
    for col in ["correct", "is_correct", "trial_correct"]:
        if col in df.columns:
            correct_col = col
            break
    
    if correct_col is None:
        raise ValueError("No correct column found in event table")
    
    print(f"    Using correct column: {correct_col}")
    
    # Filter condition 4 (AAXB)
    df[cond_col] = pd.to_numeric(df[cond_col], errors="coerce")
    cond_mask = df[cond_col] == AAXB_CONDITION_NUMBER
    df_cond4 = df[cond_mask].copy()
    print(f"    After AAXB (condition 4) filter: {len(df_cond4)}")
    
    if len(df_cond4) == 0:
        print(f"    WARNING: No condition 4 events found")
        return pd.DataFrame()
    
    # Filter code 101 (p1 stimulus onset)
    df_cond4[code_col] = pd.to_numeric(df_cond4[code_col], errors="coerce")
    code_mask = df_cond4[code_col] == EVENT_CODE_P1_STIMULUS
    df_p1 = df_cond4[code_mask].copy()
    print(f"    After code 101 (p1) filter: {len(df_p1)}")
    
    if len(df_p1) == 0:
        print(f"    WARNING: No code 101 events found in condition 4")
        return pd.DataFrame()
    
    # Filter correct trials
    df_p1[correct_col] = pd.to_numeric(df_p1[correct_col], errors="coerce")
    correct_mask = df_p1[correct_col] == 1
    df_strict = df_p1[correct_mask].copy()
    print(f"    After correct==1 filter: {len(df_strict)}")
    
    return df_strict


def validate_extracted_events(df: pd.DataFrame, session_id: str) -> dict[str, Any]:
    """Validate that extracted events have correct code101 semantics.
    
    Args:
        df: Filtered DataFrame with extracted events
        session_id: Session identifier for reporting
        
    Returns:
        Validation results dict
    """
    print(f"\n  Validating extracted events for {session_id}...")
    
    results = {
        "session": session_id,
        "n_events": len(df),
        "passed": True,
        "errors": [],
        "code_checks": {},
    }
    
    if len(df) == 0:
        results["passed"] = False
        results["errors"].append("No events extracted")
        return results
    
    # Check all codes are 101
    code_col = "codes" if "codes" in df.columns else "code"
    if code_col in df.columns:
        codes = df[code_col].unique()
        results["code_checks"]["unique_codes"] = codes.tolist()
        results["code_checks"]["all_code101"] = all(c == EVENT_CODE_P1_STIMULUS for c in codes)
        
        if not results["code_checks"]["all_code101"]:
            results["passed"] = False
            results["errors"].append(f"Not all codes are 101: {codes}")
        
        # Check no code 100
        n_code100 = (df[code_col] == EVENT_CODE_FIXATION_CUE).sum()
        results["code_checks"]["n_code100"] = int(n_code100)
        
        if n_code100 > 0:
            results["passed"] = False
            results["errors"].append(f"Found {n_code100} code 100 events - REJECTED")
    
    # Check stimulus_number == 2 for code101 events
    if "stimulus_number" in df.columns:
        stim_nums = pd.to_numeric(df["stimulus_number"], errors="coerce")
        results["code_checks"]["stimulus_numbers"] = stim_nums.dropna().unique().tolist()

        # stimulus_number should be 2 for p1 (code 101)
        if not np.allclose(stim_nums.dropna().values, 2.0):
            results["passed"] = False
            bad = stim_nums.dropna().unique().tolist()
            results["errors"].append(f"Unexpected stimulus_number values: {bad} (expected all 2)")
    
    # Check event_code_type
    if "event_code_type" in df.columns:
        types = df["event_code_type"].unique()
        results["code_checks"]["event_code_types"] = types.tolist()
        
        # Should not contain "fix cue"
        fix_cue_mask = df["event_code_type"].str.contains("fix cue", case=False, na=False)
        n_fix_cue = fix_cue_mask.sum()
        
        if n_fix_cue > 0:
            results["passed"] = False
            results["errors"].append(f"Found {n_fix_cue} 'fix cue' events - REJECTED")
    
    print(f"    Validation: {'PASS' if results['passed'] else 'FAIL'}")
    if results["errors"]:
        for err in results["errors"]:
            print(f"    ERROR: {err}")
    
    return results


# ============================================================================
# Omission Onset Calculation
# ============================================================================

def calculate_omission_onsets(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate omission onset times from p1 onsets.
    
    omission_onset = p1_onset + 2.062 seconds
    
    Args:
        df: DataFrame with p1 onset times
        
    Returns:
        DataFrame with added omission_onset_time column
    """
    # Find p1 onset column
    p1_col = None
    for col in ["start_time", "p1_onset", "onset", "p1_onset_time"]:
        if col in df.columns:
            p1_col = col
            break
    
    if p1_col is None:
        raise ValueError("No p1 onset time column found")
    
    print(f"    Using p1 onset column: {p1_col}")
    
    # Convert to numeric
    df[p1_col] = pd.to_numeric(df[p1_col], errors="coerce")
    
    # Calculate omission onset
    offset_s = AAXB_OMISSION_OFFSET_MS / 1000.0  # 2.062 seconds
    df["p1_onset_time"] = df[p1_col]
    df["omission_onset_time"] = df[p1_col] + offset_s
    df["omission_offset_ms"] = AAXB_OMISSION_OFFSET_MS
    
    return df


# ============================================================================
# Main Extraction Pipeline
# ============================================================================

def extract_session_events(
    subject_id: str,
    session_id: str,
    validate_only: bool = False,
) -> dict[str, Any]:
    """Extract strict AAXB code101 events for a single session.
    
    Args:
        subject_id: e.g., "sub-V198o"
        session_id: e.g., "ses-230629"
        validate_only: If True, only validate without extraction
        
    Returns:
        Extraction results dict
    """
    result = {
        "subject": subject_id,
        "session": session_id,
        "status": "PENDING",
        "n_events": 0,
        "errors": [],
    }
    
    # Build NWB path
    nwb_filename = f"{subject_id}_{session_id}_rec.nwb"
    nwb_path = NWB_ROOT / nwb_filename
    
    print(f"\nProcessing {subject_id} {session_id}...")
    print(f"  NWB path: {nwb_path}")
    
    if not nwb_path.exists():
        result["status"] = "BLOCKED"
        result["errors"].append(f"{BLOCKED_NWB_NOT_FOUND}: {nwb_path}")
        print(f"  ERROR: NWB file not found")
        return result
    
    # Load events
    df_raw = load_omission_events_from_nwb(nwb_path)
    if df_raw is None:
        result["status"] = "BLOCKED"
        result["errors"].append(f"{BLOCKED_EVENTS_TABLE_MISSING}")
        return result
    
    if validate_only:
        result["status"] = "VALIDATED"
        result["n_raw_events"] = len(df_raw)
        print(f"  Validation only - {len(df_raw)} raw events found")
        return result
    
    # Filter events
    try:
        df_filtered = filter_strict_aaxb_code101_events(df_raw)
    except Exception as e:
        result["status"] = "ERROR"
        result["errors"].append(f"Filtering error: {e}")
        return result
    
    if len(df_filtered) == 0:
        result["status"] = "BLOCKED"
        result["errors"].append(f"{BLOCKED_NO_AAXB_EVENTS}")
        return result
    
    # Validate extracted events
    validation = validate_extracted_events(df_filtered, session_id)
    result["validation"] = validation
    
    if not validation["passed"]:
        result["status"] = "REJECTED"
        return result
    
    # Calculate omission onsets
    try:
        df_final = calculate_omission_onsets(df_filtered)
    except Exception as e:
        result["status"] = "ERROR"
        result["errors"].append(f"Omission calculation error: {e}")
        return result
    
    # Build result
    result["status"] = "SUCCESS"
    result["n_events"] = len(df_final)
    result["events"] = df_final
    result["p1_onset_times"] = df_final["p1_onset_time"].values
    result["omission_onset_times"] = df_final["omission_onset_time"].values
    
    print(f"  SUCCESS: {len(df_final)} validated code101 p1 events")
    
    return result


def regenerate_aaxb_code101_events(
    validate_only: bool = False,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Regenerate strict AAXB code101 p1 event artifact from NWB tables.
    
    Args:
        validate_only: If True, only validate without saving
        output_dir: Output directory for artifacts
        
    Returns:
        Manifest of regeneration results
    """
    print("=" * 80)
    print("AAXB CODE101 P1 EVENT REGENERATION")
    print("=" * 80)
    print(f"NWB root: {NWB_ROOT}")
    print(f"Mode: {'VALIDATE ONLY' if validate_only else 'FULL REGENERATION'}")
    
    if output_dir is None:
        output_dir = OUTPUT_ROOT
    
    if not validate_only:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "arrays").mkdir(exist_ok=True)
        (output_dir / "tables").mkdir(exist_ok=True)
        (output_dir / "manifests").mkdir(exist_ok=True)
        (output_dir / "reports").mkdir(exist_ok=True)
    
    # Process each expected session
    all_results = []
    all_events = []
    session_onsets = {}
    
    for subject_id, session_id in EXPECTED_SESSIONS:
        result = extract_session_events(subject_id, session_id, validate_only)
        all_results.append(result)
        
        if result["status"] == "SUCCESS" and "events" in result:
            df = result["events"]
            df["session"] = session_id
            all_events.append(df)
            
            session_key = f"{subject_id.replace('-', '_')}_{session_id.replace('-', '_')}"
            session_onsets[session_key] = result["p1_onset_times"]
    
    # Build manifest
    manifest = {
        "created_at": datetime.now().isoformat(),
        "status": "INCOMPLETE",
        "mode": "validate_only" if validate_only else "full_regeneration",
        "n_sessions_attempted": len(EXPECTED_SESSIONS),
        "n_sessions_success": len([r for r in all_results if r["status"] == "SUCCESS"]),
        "n_total_events": sum(r.get("n_events", 0) for r in all_results),
        "expected_total_events": 135,
        "aaxb_condition_number": AAXB_CONDITION_NUMBER,
        "p1_event_code": EVENT_CODE_P1_STIMULUS,
        "omission_offset_ms": AAXB_OMISSION_OFFSET_MS,
        "sessions": {
            r["session"]: {
                k: (v.tolist() if isinstance(v, np.ndarray) else v)
                for k, v in r.items()
                if k not in ("events",)
            }
            for r in all_results
        },
    }
    
    # Check total event count
    total_events = manifest["n_total_events"]
    print(f"\n{'=' * 80}")
    print(f"REGENERATION SUMMARY")
    print(f"{'=' * 80}")
    print(f"Sessions attempted: {manifest['n_sessions_attempted']}")
    print(f"Sessions successful: {manifest['n_sessions_success']}")
    print(f"Total events extracted: {total_events}")
    print(f"Expected events: 135")
    
    if total_events != 135:
        print(f"WARNING: Event count mismatch!")
        manifest["event_count_warning"] = f"Expected 135, got {total_events}"
    
    # Save outputs (if not validate_only)
    if not validate_only and all_events:
        # Save NPZ with per-session arrays
        npz_path = output_dir / "arrays" / "strict_aaxb_code101_p1_events.npz"
        npz_data = {}
        for session_key, onsets in session_onsets.items():
            npz_data[f"{session_key}_p1_onsets"] = onsets
        np.savez(npz_path, **npz_data)
        print(f"\nSaved NPZ: {npz_path}")
        manifest["npz_path"] = str(npz_path)
        
        # Save combined CSV
        combined_df = pd.concat(all_events, ignore_index=True)
        csv_cols = [
            "session", "p1_onset_time", "omission_onset_time",
            "omission_offset_ms", "correct"
        ]
        # Add available columns
        available_cols = [c for c in csv_cols if c in combined_df.columns]
        csv_path = output_dir / "tables" / "strict_aaxb_code101_p1_and_omission_times.csv"
        combined_df[available_cols].to_csv(csv_path, index=False)
        print(f"Saved CSV: {csv_path}")
        manifest["csv_path"] = str(csv_path)
        
        # Save audit CSV
        audit_rows = []
        for r in all_results:
            audit_rows.append({
                "session": r["session"],
                "status": r["status"],
                "n_events": r.get("n_events", 0),
                "errors": "; ".join(r.get("errors", [])),
            })
        audit_df = pd.DataFrame(audit_rows)
        audit_path = output_dir / "tables" / "strict_aaxb_code101_event_extraction_audit.csv"
        audit_df.to_csv(audit_path, index=False)
        print(f"Saved audit: {audit_path}")
        manifest["audit_path"] = str(audit_path)
        
        # Save manifest JSON
        manifest_path = output_dir / "manifests" / "strict_aaxb_code101_event_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"Saved manifest: {manifest_path}")
        
        # Generate report
        report_path = output_dir / "reports" / "THETA_STRICT_AAXB_CODE101_REGENERATION_REPORT.md"
        generate_report(report_path, manifest, all_results)
        print(f"Saved report: {report_path}")
    
    manifest["status"] = "COMPLETE" if manifest["n_sessions_success"] == len(EXPECTED_SESSIONS) else "PARTIAL"
    
    return manifest


def generate_report(
    report_path: Path,
    manifest: dict[str, Any],
    results: list[dict[str, Any]],
) -> None:
    """Generate THETA regeneration report."""
    
    lines = [
        "# THETA REPORT: Strict AAXB Code101 Event Regeneration",
        "",
        f"**Generated:** {manifest['created_at']}",
        f"**Status:** {manifest['status']}",
        "",
        "## Summary",
        "",
        f"- Sessions attempted: {manifest['n_sessions_attempted']}",
        f"- Sessions successful: {manifest['n_sessions_success']}",
        f"- Total events: {manifest['n_total_events']} (expected: 135)",
        "",
        "## Session Results",
        "",
        "| Session | Status | Events | Notes |",
        "|---------|--------|--------|-------|",
    ]
    
    for r in results:
        notes = "; ".join(r.get("errors", [])) if r.get("errors") else "OK"
        lines.append(f"| {r['session']} | {r['status']} | {r.get('n_events', 0)} | {notes} |")
    
    lines.extend([
        "",
        "## Semantic Validation",
        "",
        f"- AAXB condition number: {manifest['aaxb_condition_number']}",
        f"- P1 event code: {manifest['p1_event_code']} (101 = task_event_2)",
        f"- Omission offset: {manifest['omission_offset_ms']} ms (2.062 s)",
        "",
        "## Output Artifacts",
        "",
        f"- NPZ: `{manifest.get('npz_path', 'N/A')}`",
        f"- CSV: `{manifest.get('csv_path', 'N/A')}`",
        f"- Audit: `{manifest.get('audit_path', 'N/A')}`",
        "",
    ])
    
    if manifest.get("event_count_warning"):
        lines.extend([
            "## Warnings",
            "",
            f"- **{manifest['event_count_warning']}**",
            "",
        ])
    
    lines.extend([
        "## Conclusion",
        "",
        "Event regeneration " + ("completed successfully" if manifest['status'] == "COMPLETE" else "completed with warnings"),
        "",
    ])
    
    report_path.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate strict AAXB code101 p1 event artifacts from NWB"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Only validate NWB sources without extraction",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_ROOT,
        help="Output directory for artifacts",
    )
    
    args = parser.parse_args()
    
    # Run regeneration
    manifest = regenerate_aaxb_code101_events(
        validate_only=args.validate,
        output_dir=args.output,
    )
    
    # Exit status
    if manifest["n_sessions_success"] == 0:
        print("\nREGENERATION FAILED - No sessions processed successfully")
        sys.exit(1)
    
    if manifest["n_total_events"] != 135:
        print(f"\nREGENERATION WARNING - Event count mismatch: {manifest['n_total_events']} != 135")
    
    print(f"\nREGENERATION {manifest['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
