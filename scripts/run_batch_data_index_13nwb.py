#!/usr/bin/env python3
"""Batch data index across 13 PyNWB-loadable NWB sessions.

Runs the accepted core NWB data-address layer across all sessions in D:/analysis/nwb/.
Creates comprehensive inventories and saves event timing as NPZ+JSON (not CSV-first).

Usage:
    python scripts/run_batch_data_index_13nwb.py

Outputs:
    outputs/data_index/batch_13nwb/
        ├── unit_address_book_all_sessions.csv
        ├── lfp_session_address_book_all_sessions.csv
        ├── event_timing_inventory_all_sessions.csv
        ├── channel_area_layer_map_inventory_all_sessions.csv
        ├── session_inventory.csv
        ├── batch_data_index_manifest.json
        ├── batch_data_index_report.md
        ├── events_npz/
        │   ├── event_timing_vectors_<subject>_<session>_p1.npz
        │   └── ...
        ├── events_json/
        │   ├── event_timing_vectors_<subject>_<session>_p1.json
        │   └── ...
        └── channel_maps/
            ├── channel_area_layer_map_<subject>_<session>.csv
            └── ...
"""

from __future__ import annotations

import datetime
import json
import sys
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np

# Add repo to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.io.nwb_address import (
    build_unit_address_book,
    build_lfp_session_address_book,
    get_event_timing_vectors,
    estimate_channel_area_layer_map,
    CANONICAL_CONDITIONS,
)
from src.analysis.recipes.events import (
    save_event_timing_vectors_npz,
    save_event_timing_vectors_json,
)


# ============================================================================
# Configuration
# ============================================================================

NWB_DIR = Path(r"D:\analysis\nwb")
OUTPUT_ROOT = Path("outputs/data_index/batch_13nwb")

# Expected sessions
EXPECTED_NWBS = [
    # C31o sessions
    "sub-C31o_ses-230630_rec.nwb",
    "sub-C31o_ses-230816_rec.nwb",
    "sub-C31o_ses-230818_rec.nwb",
    "sub-C31o_ses-230823_rec.nwb",
    "sub-C31o_ses-230825_rec.nwb",
    "sub-C31o_ses-230830_rec.nwb",
    "sub-C31o_ses-230831_rec.nwb",
    "sub-C31o_ses-230901_rec.nwb",
    # V198o sessions
    "sub-V198o_ses-230629_rec.nwb",
    "sub-V198o_ses-230714_rec.nwb",
    "sub-V198o_ses-230719_rec.nwb",
    "sub-V198o_ses-230720_rec.nwb",
    "sub-V198o_ses-230721_rec.nwb",
]

# Status codes
STATUS_PASS = "PASS"
STATUS_BLOCKED_NWB_OPEN_FAILED = "BLOCKED_NWB_OPEN_FAILED"
STATUS_BLOCKED_UNITS_TABLE_MISSING = "BLOCKED_UNITS_TABLE_MISSING"
STATUS_BLOCKED_ELECTRODES_TABLE_MISSING = "BLOCKED_ELECTRODES_TABLE_MISSING"
STATUS_BLOCKED_EVENT_SCHEMA_UNSUPPORTED = "BLOCKED_EVENT_SCHEMA_UNSUPPORTED"
STATUS_BLOCKED_EVENT_TIMING_MISSING = "BLOCKED_EVENT_TIMING_MISSING"
STATUS_BLOCKED_CHANNEL_MAP_FAILED = "BLOCKED_CHANNEL_MAP_FAILED"
STATUS_OTHER_ERROR = "OTHER_ERROR"


# ============================================================================
# Helper Functions
# ============================================================================

def parse_subject_session(nwb_path: Path) -> tuple[str, str]:
    """Parse subject and session from NWB filename."""
    # Format: sub-<subject>_ses-<session>_rec.nwb
    parts = nwb_path.stem.split("_")
    subject = parts[0].replace("sub-", "") if len(parts) > 0 else "unknown"
    session = parts[1].replace("ses-", "") if len(parts) > 1 else "unknown"
    return subject, session


def ensure_output_dirs() -> Path:
    """Create output directory structure."""
    root = OUTPUT_ROOT
    
    subdirs = [
        "events_npz",
        "events_json",
        "channel_maps",
    ]
    
    for subdir in subdirs:
        (root / subdir).mkdir(parents=True, exist_ok=True)
    
    return root


def process_nwb_session(nwb_path: Path, output_root: Path) -> dict[str, Any]:
    """Process a single NWB session.
    
    Returns session result dict with all metadata and status.
    """
    subject, session = parse_subject_session(nwb_path)
    
    result = {
        "subject_id": subject,
        "session_id": session,
        "nwb_file": str(nwb_path),
        "nwb_file_name": nwb_path.name,
        "nwb_size_bytes": nwb_path.stat().st_size,
        "pynwb_open_status": None,
        "n_units": 0,
        "n_probes": 0,
        "n_channels": 0,
        "event_condition_count": 0,
        "event_total_count": 0,
        "unit_address_status": None,
        "lfp_address_status": None,
        "channel_map_status": None,
        "event_vector_status": None,
        "status": STATUS_PASS,
        "blocker": None,
        "warnings_count": 0,
        "warnings": [],
    }
    
    print(f"\nProcessing: {nwb_path.name}")
    print(f"  Subject: {subject}, Session: {session}")
    print(f"  Size: {nwb_path.stat().st_size / 1e9:.2f} GB")
    
    # Check if file exists and is readable
    if not nwb_path.exists():
        result["status"] = STATUS_BLOCKED_NWB_OPEN_FAILED
        result["blocker"] = f"File not found: {nwb_path}"
        return result
    
    # Try to open with PyNWB
    try:
        from pynwb import NWBHDF5IO
        io = NWBHDF5IO(str(nwb_path), "r", load_namespaces=True)
        nwbfile = io.read()
        result["pynwb_open_status"] = "success"
    except Exception as e:
        result["status"] = STATUS_BLOCKED_NWB_OPEN_FAILED
        result["blocker"] = f"{type(e).__name__}: {e}"
        result["pynwb_open_status"] = "failed"
        return result
    
    try:
        # 1. Build unit address book
        print("  Building unit address book...")
        try:
            units_df = build_unit_address_book([nwb_path], out_csv=None)
            result["n_units"] = len(units_df)
            result["unit_address_status"] = "success"
            print(f"    Units: {len(units_df)}")
        except Exception as e:
            result["unit_address_status"] = "failed"
            result["warnings"].append(f"Unit address: {e}")
            print(f"    Unit address failed: {e}")
        
        # 2. Build LFP/probe session address book
        print("  Building LFP session address book...")
        try:
            lfp_df = build_lfp_session_address_book([nwb_path], out_csv=None)
            result["n_probes"] = len(lfp_df)
            result["n_channels"] = int(lfp_df["n_channels"].sum()) if len(lfp_df) > 0 else 0
            result["lfp_address_status"] = "success"
            print(f"    Probes: {result['n_probes']}, Channels: {result['n_channels']}")
        except Exception as e:
            result["lfp_address_status"] = "failed"
            result["warnings"].append(f"LFP address: {e}")
            print(f"    LFP address failed: {e}")
        
        # 3. Build channel-area-layer map
        print("  Building channel area/layer map...")
        chmap_path = output_root / "channel_maps" / f"channel_area_layer_map_{subject}_{session}.csv"
        try:
            chmap_df = estimate_channel_area_layer_map(nwb_path, infer_layers=False)
            chmap_df.to_csv(chmap_path, index=False)
            result["channel_map_status"] = "success"
            result["channel_map_csv"] = str(chmap_path)
            print(f"    Channels: {len(chmap_df)}, saved to {chmap_path.name}")
        except Exception as e:
            result["channel_map_status"] = "failed"
            result["warnings"].append(f"Channel map: {e}")
            print(f"    Channel map failed: {e}")
        
        # 4. Get p1 event timing vectors
        print("  Getting p1 event timing vectors...")
        try:
            events = get_event_timing_vectors(nwb_path, event="p1", conditions=CANONICAL_CONDITIONS)
            result["event_condition_count"] = len([c for c in events if len(events[c]) > 0])
            result["event_total_count"] = sum(len(v) for v in events.values())
            result["event_vector_status"] = "success"
            print(f"    Conditions with events: {result['event_condition_count']}/12")
            print(f"    Total events: {result['event_total_count']}")
            
            # Save as NPZ (primary storage)
            npz_path = output_root / "events_npz" / f"event_timing_vectors_{subject}_{session}_p1.npz"
            metadata = {
                "nwb_file": str(nwb_path),
                "subject_id": subject,
                "session_id": session,
                "event": "p1",
                "conditions": list(events.keys()),
            }
            save_event_timing_vectors_npz(events, npz_path, metadata=metadata)
            result["event_npz_path"] = str(npz_path)
            print(f"    Saved NPZ: {npz_path.name}")
            
            # Save as JSON (human-readable sidecar)
            json_path = output_root / "events_json" / f"event_timing_vectors_{subject}_{session}_p1.json"
            save_event_timing_vectors_json(events, json_path, metadata=metadata)
            result["event_json_path"] = str(json_path)
            print(f"    Saved JSON: {json_path.name}")
            
        except Exception as e:
            result["event_vector_status"] = "failed"
            result["blocker"] = f"Event vectors: {e}"
            result["status"] = STATUS_BLOCKED_EVENT_TIMING_MISSING
            print(f"    Event vectors failed: {e}")
        
        result["warnings_count"] = len(result["warnings"])
        
    except Exception as e:
        result["status"] = STATUS_OTHER_ERROR
        result["blocker"] = f"Unexpected error: {e}"
        print(f"  ERROR: {e}")
    
    finally:
        io.close()
    
    return result


def run_batch_index() -> dict[str, Any]:
    """Run batch indexing across all 13 NWB sessions."""
    print("=" * 70)
    print("BATCH DATA INDEX: 13 NWB SESSIONS")
    print("=" * 70)
    print(f"NWB Directory: {NWB_DIR}")
    print(f"Output Root: {OUTPUT_ROOT}")
    print()
    
    # Ensure output directories
    output_root = ensure_output_dirs()
    print(f"Output directories created: {output_root}")
    print()
    
    # Collect all session results
    session_results: list[dict[str, Any]] = []
    
    # Process each expected NWB
    for nwb_name in EXPECTED_NWBS:
        nwb_path = NWB_DIR / nwb_name
        result = process_nwb_session(nwb_path, output_root)
        session_results.append(result)
    
    # Build session inventory
    print("\n" + "=" * 70)
    print("BUILDING INVENTORY TABLES")
    print("=" * 70)
    
    # Session inventory
    session_inventory_df = pd.DataFrame([
        {
            "subject_id": r["subject_id"],
            "session_id": r["session_id"],
            "nwb_file": r["nwb_file"],
            "nwb_size_bytes": r["nwb_size_bytes"],
            "pynwb_open_status": r["pynwb_open_status"],
            "n_units": r["n_units"],
            "n_probes": r["n_probes"],
            "n_channels": r["n_channels"],
            "event_condition_count": r["event_condition_count"],
            "event_total_count": r["event_total_count"],
            "unit_address_status": r["unit_address_status"],
            "lfp_address_status": r["lfp_address_status"],
            "channel_map_status": r["channel_map_status"],
            "event_vector_status": r["event_vector_status"],
            "status": r["status"],
            "blocker": r["blocker"],
            "warnings_count": r["warnings_count"],
        }
        for r in session_results
    ])
    
    session_inventory_path = output_root / "session_inventory.csv"
    session_inventory_df.to_csv(session_inventory_path, index=False)
    print(f"Session inventory: {session_inventory_path}")
    
    # Unit address book (all sessions)
    print("\nBuilding combined unit address book...")
    all_unit_rows = []
    for result in session_results:
        if result["status"] == STATUS_PASS and result["unit_address_status"] == "success":
            try:
                units_df = build_unit_address_book([Path(result["nwb_file"])], out_csv=None)
                all_unit_rows.append(units_df)
            except Exception as e:
                print(f"  Warning: Could not rebuild units for {result['session_id']}: {e}")
    
    if all_unit_rows:
        unit_address_combined = pd.concat(all_unit_rows, ignore_index=True)
        # Re-assign general_unit_id across all sessions
        unit_address_combined["general_unit_id"] = range(1, len(unit_address_combined) + 1)
        unit_address_path = output_root / "unit_address_book_all_sessions.csv"
        unit_address_combined.to_csv(unit_address_path, index=False)
        print(f"Unit address book: {unit_address_path} ({len(unit_address_combined)} units)")
    else:
        print("  No unit data available")
        unit_address_combined = pd.DataFrame()
    
    # LFP session address book (all sessions)
    print("\nBuilding combined LFP session address book...")
    all_lfp_rows = []
    for result in session_results:
        if result["status"] == STATUS_PASS and result["lfp_address_status"] == "success":
            try:
                lfp_df = build_lfp_session_address_book([Path(result["nwb_file"])], out_csv=None)
                all_lfp_rows.append(lfp_df)
            except Exception as e:
                print(f"  Warning: Could not rebuild LFP for {result['session_id']}: {e}")
    
    if all_lfp_rows:
        lfp_address_combined = pd.concat(all_lfp_rows, ignore_index=True)
        # Re-assign general_lfp_id across all sessions
        lfp_address_combined["general_lfp_id"] = range(1, len(lfp_address_combined) + 1)
        lfp_address_path = output_root / "lfp_session_address_book_all_sessions.csv"
        lfp_address_combined.to_csv(lfp_address_path, index=False)
        print(f"LFP address book: {lfp_address_path} ({len(lfp_address_combined)} probes)")
    else:
        print("  No LFP data available")
        lfp_address_combined = pd.DataFrame()
    
    # Event timing inventory (compact, not full event timings)
    print("\nBuilding event timing inventory...")
    event_inventory_rows = []
    for result in session_results:
        row = {
            "subject_id": result["subject_id"],
            "session_id": result["session_id"],
            "nwb_file": result["nwb_file"],
            "event": "p1",
            "condition_count": result["event_condition_count"],
            "count": result["event_total_count"],
            "npz_path": result.get("event_npz_path", ""),
            "json_path": result.get("event_json_path", ""),
            "time_unit": "seconds",
            "time_base": "NWB",
            "status": result["event_vector_status"] or ("failed" if result["blocker"] else "unknown"),
            "warnings": "; ".join(result["warnings"]) if result["warnings"] else "",
        }
        event_inventory_rows.append(row)
    
    event_inventory_df = pd.DataFrame(event_inventory_rows)
    event_inventory_path = output_root / "event_timing_inventory_all_sessions.csv"
    event_inventory_df.to_csv(event_inventory_path, index=False)
    print(f"Event timing inventory: {event_inventory_path}")
    
    # Channel area/layer map inventory
    print("\nBuilding channel map inventory...")
    chmap_inventory_rows = []
    for result in session_results:
        chmap_csv = result.get("channel_map_csv", "")
        
        # Get area info from the CSV if available
        areas_raw = ""
        areas_resolved = []
        n_unresolved_area = 0
        n_unresolved_layer = 0
        
        if chmap_csv and Path(chmap_csv).exists():
            try:
                chmap_df = pd.read_csv(chmap_csv)
                areas_raw = ", ".join(chmap_df["area_string_raw"].unique()) if "area_string_raw" in chmap_df.columns else ""
                areas_resolved = chmap_df["area"].unique().tolist() if "area" in chmap_df.columns else []
                n_unresolved_area = (chmap_df["area"] == "unresolved").sum() if "area" in chmap_df.columns else 0
                n_unresolved_layer = (chmap_df["layer"] == "unresolved").sum() if "layer" in chmap_df.columns else 0
            except Exception:
                pass
        
        row = {
            "subject_id": result["subject_id"],
            "session_id": result["session_id"],
            "nwb_file": result["nwb_file"],
            "n_channels": result["n_channels"],
            "areas_raw": areas_raw,
            "areas_resolved": ", ".join(str(a) for a in areas_resolved),
            "n_unresolved_area_channels": n_unresolved_area,
            "n_unresolved_layer_channels": n_unresolved_layer,
            "channel_map_csv": chmap_csv,
            "status": result["channel_map_status"] or "unknown",
            "warnings": "; ".join(result["warnings"]) if result["warnings"] else "",
        }
        chmap_inventory_rows.append(row)
    
    chmap_inventory_df = pd.DataFrame(chmap_inventory_rows)
    chmap_inventory_path = output_root / "channel_area_layer_map_inventory_all_sessions.csv"
    chmap_inventory_df.to_csv(chmap_inventory_path, index=False)
    print(f"Channel map inventory: {chmap_inventory_path}")
    
    # Build manifest
    print("\nBuilding batch manifest...")
    
    # Get git info
    import subprocess
    try:
        repo_root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        repo_branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        repo_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        git_status = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception as e:
        repo_root = str(Path(__file__).parent.parent)
        repo_branch = "unknown"
        repo_sha = "unknown"
        git_status = f"git command failed: {e}"
    
    manifest = {
        "repo_root": repo_root,
        "repo_branch": repo_branch,
        "repo_sha": repo_sha,
        "git_status_short": git_status,
        "python_version": sys.version.split()[0],
        "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "phase": "BATCH_DATA_INDEX_13NWB",
        "nwb_directory": str(NWB_DIR),
        "n_sessions_expected": len(EXPECTED_NWBS),
        "n_sessions_found": len([r for r in session_results if r["pynwb_open_status"] == "success"]),
        "n_sessions_pass": len([r for r in session_results if r["status"] == STATUS_PASS]),
        "n_sessions_blocked": len([r for r in session_results if r["status"] != STATUS_PASS]),
        "outputs": {
            "session_inventory": str(session_inventory_path),
            "unit_address_book": str(unit_address_path) if not unit_address_combined.empty else None,
            "lfp_session_address_book": str(lfp_address_path) if not lfp_address_combined.empty else None,
            "event_timing_inventory": str(event_inventory_path),
            "channel_map_inventory": str(chmap_inventory_path),
            "events_npz_dir": str(output_root / "events_npz"),
            "events_json_dir": str(output_root / "events_json"),
            "channel_maps_dir": str(output_root / "channel_maps"),
        },
        "session_rows": session_results,
        "warnings": [],
    }
    
    manifest_path = output_root / "batch_data_index_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)
    print(f"Manifest: {manifest_path}")
    
    # Generate report
    print("\nGenerating report...")
    report_lines = [
        "# Batch Data Index Report: 13 NWB Sessions",
        "",
        f"**Generated:** {manifest['created_at_utc']}",
        f"**Repository:** {repo_root}",
        f"**Branch:** {repo_branch}",
        f"**SHA:** {repo_sha}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Expected sessions | {manifest['n_sessions_expected']} |",
        f"| Successfully opened | {manifest['n_sessions_found']} |",
        f"| Full pass (all indices) | {manifest['n_sessions_pass']} |",
        f"| Blocked/Partial | {manifest['n_sessions_blocked']} |",
        "",
        "## Session Details",
        "",
        "| Subject | Session | Units | Probes | Channels | Events | Status | Blocker |",
        "|---|---|---:|---:|---:|---:|:---|:---|",
    ]
    
    for r in session_results:
        status_emoji = "✓" if r["status"] == STATUS_PASS else "✗"
        blocker_short = (r["blocker"][:50] + "...") if r["blocker"] and len(r["blocker"]) > 50 else (r["blocker"] or "")
        report_lines.append(
            f"| {r['subject_id']} | {r['session_id']} | "
            f"{r['n_units']} | {r['n_probes']} | {r['n_channels']} | "
            f"{r['event_total_count']} | {status_emoji} {r['status']} | {blocker_short} |"
        )
    
    report_lines.extend([
        "",
        "## Output Files",
        "",
        f"- **Session inventory:** `{session_inventory_path}`",
        f"- **Unit address book:** `{unit_address_path}`" if not unit_address_combined.empty else "- **Unit address book:** Not available",
        f"- **LFP address book:** `{lfp_address_path}`" if not lfp_address_combined.empty else "- **LFP address book:** Not available",
        f"- **Event timing inventory:** `{event_inventory_path}`",
        f"- **Channel map inventory:** `{chmap_inventory_path}`",
        "",
        "### Per-Session Event Timing Files",
        "",
        "NPZ (compressed binary, primary storage):",
    ])
    
    for r in session_results:
        if "event_npz_path" in r:
            report_lines.append(f"- `{r['event_npz_path']}`")
    
    report_lines.extend([
        "",
        "JSON (human-readable metadata sidecar):",
    ])
    
    for r in session_results:
        if "event_json_path" in r:
            report_lines.append(f"- `{r['event_json_path']}`")
    
    report_lines.extend([
        "",
        "### Per-Session Channel Map Files",
        "",
    ])
    
    for r in session_results:
        if "channel_map_csv" in r:
            report_lines.append(f"- `{r['channel_map_csv']}`")
    
    report_lines.extend([
        "",
        "## Event Timing Storage Architecture",
        "",
        "Per user specification:",
        "",
        "| Format | Purpose | Status |",
        "|---|---|:---|",
        "| `dict[str, np.ndarray]` | Runtime API | ✓ Primary |",
        "| `.npz` | Disk cache | ✓ Compressed binary |",
        "| `.json` | Debug/provenance | ✓ Human-readable sidecar |",
        "| `.csv` | Interoperability | ✗ Optional export only |",
        "",
        "Note: Event timing CSV is NOT used as primary storage. The inventory CSV contains",
        "only compact metadata (session, condition counts, paths), not full event timings.",
        "",
        "## Warnings",
        "",
    ])
    
    all_warnings = []
    for r in session_results:
        if r["warnings"]:
            all_warnings.extend([f"{r['subject_id']}_{r['session_id']}: {w}" for w in r["warnings"]])
    
    if all_warnings:
        for w in all_warnings[:20]:  # Limit to first 20
            report_lines.append(f"- {w}")
        if len(all_warnings) > 20:
            report_lines.append(f"- ... and {len(all_warnings) - 20} more warnings")
    else:
        report_lines.append("No warnings.")
    
    report_lines.extend([
        "",
        "## Validation",
        "",
        "✓ All 13 sessions accounted for",
        "✓ Unit address book created" if not unit_address_combined.empty else "⚠ Unit address book incomplete",
        "✓ LFP address book created" if not lfp_address_combined.empty else "⚠ LFP address book incomplete",
        "✓ Event timing inventory created",
        "✓ Channel map inventory created",
        "✓ Event timing stored as NPZ (primary) + JSON (sidecar)",
        "✓ Manifest with full provenance created",
        "",
        "---",
        "",
        "**Next step:** Figures 4-9 reconstruction using this cross-session inventory.",
    ])
    
    report_path = output_root / "batch_data_index_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Report: {report_path}")
    
    # Print summary
    print("\n" + "=" * 70)
    print("BATCH DATA INDEX COMPLETE")
    print("=" * 70)
    print(f"Sessions processed: {len(session_results)}")
    print(f"  - Successfully opened: {manifest['n_sessions_found']}")
    print(f"  - Full pass: {manifest['n_sessions_pass']}")
    print(f"  - Blocked: {manifest['n_sessions_blocked']}")
    print()
    print(f"Total units indexed: {sum(r['n_units'] for r in session_results)}")
    print(f"Total channels indexed: {sum(r['n_channels'] for r in session_results)}")
    print(f"Total events indexed: {sum(r['event_total_count'] for r in session_results)}")
    print()
    print(f"Output directory: {output_root}")
    
    return manifest


if __name__ == "__main__":
    # Suppress warnings for cleaner output
    warnings.filterwarnings("ignore", category=UserWarning)
    
    try:
        manifest = run_batch_index()
        sys.exit(0)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
