#!/usr/bin/env python3
# scripts/build_dataset_census.py
"""
Phase A3 Descriptive Dataset Census.
Scans D:\\workspace\\data safely to generate session-level inventory tables.
"""

import os
import re
import csv
import json
import sys
import argparse
import warnings as py_warnings
from pathlib import Path
import numpy as np

# Set truth status constant
TRUTH_SAFE_UNVERIFIED = "truth_safe_unverified"

# Standard 12 condition codes
CONDITIONS = ["AAAB", "AXAB", "AAXB", "AAAX", "BBBA", "BXBA", "BBXA", "BBBX", "RRRR", "RXRR", "RRXR", "RRRX"]

def parse_args():
    parser = argparse.ArgumentParser(description="Phase A3 Descriptive Dataset Census")
    parser.add_argument("--data-root", required=True, help="Path to raw/derived data root directory")
    parser.add_argument("--out-dir", default="reports/analysis_A3_dataset_census", help="Output reports directory")
    parser.add_argument("--max-shape-files", type=int, default=1000, help="Maximum number of .npy files to shape-inspect")
    parser.add_argument("--format", default="csv,json,md", help="Comma-separated output format list")
    return parser.parse_args()

def discover_session(name):
    """Finds 6-digit session identifier in file or folder name."""
    # Try finding 'ses' followed by optional separators and 6 digits
    session_match = re.search(r"ses[_-]?(\d{6})", name, re.IGNORECASE)
    if session_match:
        return session_match.group(1)
    # Or just search for any 6 digits that start with 23
    session_match_23 = re.search(r"\b(23\d{4})\b", name)
    if session_match_23:
        return session_match_23.group(1)
    # Also support general 6 digits if word boundary
    session_match_any = re.search(r"\b(\d{6})\b", name)
    if session_match_any:
        return session_match_any.group(1)
    return None

def detect_condition(name):
    """Detects standard condition token in the file name."""
    for c in CONDITIONS:
        if c in name:
            return c
    for c in CONDITIONS:
        if c.lower() in name.lower():
            return c
    return None

def get_condition_family(cond):
    if not cond:
        return "Unknown"
    first_char = cond[0].upper()
    if first_char == 'A':
        return "A-family"
    elif first_char == 'B':
        return "B-family"
    elif first_char == 'R':
        return "R-family"
    return "Unknown"

def get_omission_position(cond):
    if not cond:
        return "None"
    if cond in ["AXAB", "BXBA", "RXRR"]:
        return "p2"
    elif cond in ["AAXB", "BBXA", "RRXR"]:
        return "p3"
    elif cond in ["AAAX", "BBBX", "RRRX"]:
        return "p4"
    return "None"

def get_matched_control(cond):
    if not cond:
        return "None"
    family = get_condition_family(cond)
    if family == "A-family":
        return "AAAB"
    elif family == "B-family":
        return "BBBA"
    elif family == "R-family":
        return "RRRR"
    return "None"

def infer_signal_class(name):
    name_lower = name.lower()
    if any(tok in name_lower for tok in ["spk", "spike", "unit", "units", "sua"]):
        return "SPK"
    elif any(tok in name_lower for tok in ["mua", "muae"]):
        return "MUAe"
    elif "lfp" in name_lower:
        return "LFP"
    elif any(tok in name_lower for tok in ["behavior", "eye", "fixation", "trial"]):
        return "behavior"
    elif any(tok in name_lower for tok in ["metadata", "manifest", "session", "probe", "channel", "unit"]):
        return "metadata"
    return "unknown"

def inspect_npy_shape(path):
    """Inspects shape of .npy array file strictly using memory mapping (no full load)."""
    try:
        # Load with mmap_mode to prevent loading into memory
        arr = np.load(path, mmap_mode="r")
        return str(arr.shape)
    except Exception as e:
        return f"error: {str(e)}"

def inspect_metadata_file(path, ext):
    cols_or_keys = []
    has_area = False
    has_cond = False
    has_trial = False
    has_unit = False
    has_chan = False
    warnings = []
    
    try:
        if ext == ".csv":
            import pandas as pd
            df = pd.read_csv(path, nrows=0)
            cols_or_keys = list(df.columns)
        elif ext == ".tsv":
            import pandas as pd
            df = pd.read_csv(path, sep="\t", nrows=0)
            cols_or_keys = list(df.columns)
        elif ext == ".json":
            with open(path, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cols_or_keys = list(data.keys())
                elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                    cols_or_keys = list(data[0].keys())
        # Check for column/key matches
        for c in cols_or_keys:
            c_low = str(c).lower()
            if any(tok in c_low for tok in ["area", "location", "region", "brain_area"]):
                has_area = True
            if any(tok in c_low for tok in ["cond", "condition", "family", "omission"]):
                has_cond = True
            if any(tok in c_low for tok in ["trial", "time", "onset", "milestone"]):
                has_trial = True
            if any(tok in c_low for tok in ["unit", "neuron", "cell", "uid", "sua"]):
                has_unit = True
            if any(tok in c_low for tok in ["channel", "chan", "ch", "electrode", "peak_channel"]):
                has_chan = True
    except Exception as e:
        warnings.append(f"light inspection failed: {str(e)}")
        
    return cols_or_keys, has_area, has_cond, has_trial, has_unit, has_chan, warnings

def parse_session_area_mapping(mapping_path):
    records = []
    if not mapping_path.exists():
        return records
    with open(mapping_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("|") and not line.startswith("|:---") and not "| Session |" in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    session = parts[0]
                    if session.isdigit() and len(session) == 6:
                        records.append({
                            "session": session,
                            "probe": parts[1],
                            "areas": parts[2],
                            "channels": parts[3]
                        })
    return records

def main():
    args = parse_args()
    data_root = Path(args.data_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    if not data_root.exists():
        print(f"Error: Data root {data_root} does not exist.")
        sys.exit(1)
        
    # Discover files recursively or shallow in data_root
    all_files = []
    known_subdirs = ["manifests", "metadata", "session_manifests", "behavior", "arrays", "nwb"]
    
    # Check data_root root
    for entry in os.scandir(data_root):
        if entry.is_file():
            all_files.append(Path(entry.path))
            
    # Check known subdirectories
    for sd in known_subdirs:
        sd_path = data_root / sd
        if sd_path.exists() and sd_path.is_dir():
            for root, _, files in os.walk(sd_path):
                for f in files:
                    all_files.append(Path(root) / f)
                    
    # Filter files
    valid_files = []
    for p in all_files:
        ext = p.suffix.lower()
        if ext in [".npy", ".nwb", ".mat", ".h5", ".hdf5", ".npz", ".json", ".csv", ".tsv", ".yaml", ".yml", ".txt", ".md"]:
            valid_files.append(p)
            
    # Parse files
    shape_checked_count = 0
    signal_records = []
    metadata_records = []
    session_files = {} # session_id -> list of file records
    
    # Find mapping path
    project_root = Path(__file__).resolve().parent.parent
    mapping_file = project_root / "context" / "overview" / "session-area-mapping.md"
    mapping_entries = parse_session_area_mapping(mapping_file)
    
    # Build area warning index
    area_warnings_list = []
    for entry in mapping_entries:
        session = entry["session"]
        probe = entry["probe"]
        areas = entry["areas"]
        
        # Unresolved V3 warning
        if "V3" in [a.strip() for a in areas.split(",")]:
            area_warnings_list.append({
                "session_id": session,
                "source_basename": "session-area-mapping.md",
                "warning_type": "unresolved_v3",
                "detail": f"Probe {probe} uses generic V3. This area remains UNRESOLVED (not split into V3d/V3a).",
                "truth_status": TRUTH_SAFE_UNVERIFIED
            })
        # DP -> V4 alias warning
        if "DP" in areas:
            area_warnings_list.append({
                "session_id": session,
                "source_basename": "session-area-mapping.md",
                "warning_type": "dp_to_v4",
                "detail": f"Probe {probe} uses DP alias, normalized to V4.",
                "truth_status": TRUTH_SAFE_UNVERIFIED
            })
            
    for p in valid_files:
        basename = p.name
        ext = p.suffix.lower()
        size_bytes = p.stat().st_size
        
        # 1. Session Discovery
        session_id = discover_session(basename)
        if not session_id:
            # Skip if we can't associate with any session
            continue
            
        if session_id not in session_files:
            session_files[session_id] = []
            
        # 2. Determine Role and Class
        role = "unknown"
        if "manifest" in basename.lower():
            role = "manifest"
        elif ext in [".json", ".csv", ".tsv", ".yaml", ".yml", ".txt", ".md"] and any(x in p.parts for x in ["metadata", "manifests", "session_manifests"]):
            role = "metadata"
        elif any(x in basename.lower() for x in ["behavior", "eye", "fixation", "trial"]) or "behavior" in p.parts:
            role = "behavior"
        elif ext in [".nwb", ".mat", ".h5", ".hdf5", ".npy", ".npz"]:
            role = "raw_neural_array"
            
        sig_class = infer_signal_class(basename)
        cond = detect_condition(basename)
        
        # Build file-level entry
        file_rec = {
            "session_id": session_id,
            "path": p,
            "basename": basename,
            "ext": ext,
            "size_bytes": size_bytes,
            "role": role,
            "sig_class": sig_class,
            "cond": cond
        }
        session_files[session_id].append(file_rec)
        
        # Handle specific roles
        if role == "raw_neural_array":
            shape_if_safe = "not_inspected"
            raw_payload_read = "False"
            semantic_warnings = ""
            
            # Check shape if .npy
            if ext == ".npy":
                if shape_checked_count < args.max_shape_files:
                    shape_if_safe = inspect_npy_shape(p)
                    shape_checked_count += 1
                else:
                    shape_if_safe = "skipped_over_limit"
            else:
                shape_if_safe = "blocked_format"
                
            # Cross-signal semantic mismatch warning check
            if sig_class == "LFP" and any(x in basename.lower() for x in ["spk", "spike", "unit", "sua"]):
                semantic_warnings = "Semantic Mismatch: file contains spike units but is categorized as LFP"
                
            signal_records.append({
                "session_id": session_id,
                "basename": basename,
                "extension": ext,
                "size_bytes": size_bytes,
                "signal_class_inferred": sig_class,
                "condition_inferred": cond or "None",
                "shape_if_safe": shape_if_safe,
                "raw_payload_read": raw_payload_read,
                "semantic_warnings": semantic_warnings,
                "truth_status": TRUTH_SAFE_UNVERIFIED
            })
            
        elif role == "metadata":
            cols, h_area, h_cond, h_trial, h_unit, h_chan, m_warns = inspect_metadata_file(p, ext)
            cols_str = ",".join(cols) if cols else "None"
            metadata_records.append({
                "session_id": session_id,
                "basename": basename,
                "extension": ext,
                "detected_metadata_role": "metadata",
                "detected_columns_or_keys": cols_str,
                "has_area_tokens": str(h_area),
                "has_condition_tokens": str(h_cond),
                "has_trial_tokens": str(h_trial),
                "has_unit_tokens": str(h_unit),
                "has_channel_tokens": str(h_chan),
                "warnings": ";".join(m_warns) if m_warns else "None",
                "truth_status": TRUTH_SAFE_UNVERIFIED
            })

    # Prepare outputs
    # 1. session_inventory.csv
    session_inventory = []
    # Sort session IDs numerically
    sorted_sessions = sorted(list(session_files.keys()))
    
    for sid in sorted_sessions:
        files = session_files[sid]
        n_files = len(files)
        n_meta = len([f for f in files if f["role"] == "metadata"])
        n_array = len([f for f in files if f["role"] == "raw_neural_array"])
        
        has_spk = any(f["sig_class"] == "SPK" for f in files)
        has_muae = any(f["sig_class"] == "MUAe" for f in files)
        has_lfp = any(f["sig_class"] == "LFP" for f in files)
        has_behavior = any(f["role"] == "behavior" for f in files)
        has_manifest = any(f["role"] == "manifest" for f in files)
        
        # Check if has metadata files that contain condition tokens
        has_cond_metadata = False
        for f in files:
            if f["role"] == "metadata":
                _, _, h_cond, _, _, _, _ = inspect_metadata_file(f["path"], f["ext"])
                if h_cond:
                    has_cond_metadata = True
                    break
                    
        # Parse unique conditions detected
        conds_detected = sorted(list(set([f["cond"] for f in files if f["cond"] is not None])))
        conds_detected_str = ",".join(conds_detected) if conds_detected else "None"
        
        # Missing conditions check
        missing_core = [c for c in CONDITIONS if c not in conds_detected]
        missing_core_str = ",".join(missing_core) if missing_core else "None"
        
        # Warnings
        session_warns = []
        if missing_core:
            session_warns.append(f"Missing {len(missing_core)} core conditions")
            
        # Check area mapping mappings for this session
        sess_mapping_warns = [w["detail"] for w in area_warnings_list if w["session_id"] == sid]
        session_warns.extend(sess_mapping_warns)
        
        session_inventory.append({
            "session_id": sid,
            "n_files": n_files,
            "n_metadata_files": n_meta,
            "n_array_files": n_array,
            "has_spk": str(has_spk),
            "has_muae": str(has_muae),
            "has_lfp": str(has_lfp),
            "has_behavior": str(has_behavior),
            "has_manifest": str(has_manifest),
            "has_condition_metadata": str(has_cond_metadata),
            "conditions_detected": conds_detected_str,
            "missing_core_conditions": missing_core_str,
            "warnings": ";".join(session_warns) if session_warns else "None",
            "truth_status": TRUTH_SAFE_UNVERIFIED
        })

    # 2. condition_inventory.csv
    condition_inventory = []
    for sid in sorted_sessions:
        files = session_files[sid]
        # Group files by condition detected
        cond_groups = {}
        for f in files:
            if f["cond"]:
                if f["cond"] not in cond_groups:
                    cond_groups[f["cond"]] = []
                cond_groups[f["cond"]].append(f)
                
        for cond, c_files in cond_groups.items():
            classes_detected = sorted(list(set([f["sig_class"] for f in c_files])))
            classes_str = ",".join(classes_detected)
            basenames = sorted([f["basename"] for f in c_files])
            basenames_str = ",".join(basenames)
            
            condition_inventory.append({
                "session_id": sid,
                "condition": cond,
                "family": get_condition_family(cond),
                "omission_position": get_omission_position(cond),
                "matched_control": get_matched_control(cond),
                "n_files": len(c_files),
                "signal_classes_detected": classes_str,
                "source_basenames": basenames_str,
                "warnings": "None",
                "truth_status": TRUTH_SAFE_UNVERIFIED
            })

    # Output CSV Files
    def write_csv(filename, fieldnames, rows):
        filepath = out_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        print(f"[success] Wrote {filepath}")

    write_csv("session_inventory.csv", [
        "session_id", "n_files", "n_metadata_files", "n_array_files",
        "has_spk", "has_muae", "has_lfp", "has_behavior", "has_manifest",
        "has_condition_metadata", "conditions_detected", "missing_core_conditions",
        "warnings", "truth_status"
    ], session_inventory)

    write_csv("condition_inventory.csv", [
        "session_id", "condition", "family", "omission_position", "matched_control",
        "n_files", "signal_classes_detected", "source_basenames", "warnings", "truth_status"
    ], condition_inventory)

    write_csv("signal_file_inventory.csv", [
        "session_id", "basename", "extension", "size_bytes", "signal_class_inferred",
        "condition_inferred", "shape_if_safe", "raw_payload_read", "semantic_warnings", "truth_status"
    ], signal_records)

    write_csv("metadata_inventory.csv", [
        "session_id", "basename", "extension", "detected_metadata_role",
        "detected_columns_or_keys", "has_area_tokens", "has_condition_tokens",
        "has_trial_tokens", "has_unit_tokens", "has_channel_tokens", "warnings", "truth_status"
    ], metadata_records)

    write_csv("area_mapping_warnings.csv", [
        "session_id", "source_basename", "warning_type", "detail", "truth_status"
    ], area_warnings_list)

    # 3. Create dataset_census_summary.md
    total_sessions = len(sorted_sessions)
    total_files = len(valid_files)
    
    # Calculate summary counts
    spk_sessions = len([s for s in session_inventory if s["has_spk"] == "True"])
    muae_sessions = len([s for s in session_inventory if s["has_muae"] == "True"])
    lfp_sessions = len([s for s in session_inventory if s["has_lfp"] == "True"])
    
    unresolved_v3_count = len([w for w in area_warnings_list if w["warning_type"] == "unresolved_v3"])
    dp_to_v4_count = len([w for w in area_warnings_list if w["warning_type"] == "dp_to_v4"])
    
    # Identify candidate sessions suitable for A4 trial-count validation
    # Candidate sessions must have both SPK and LFP signals, and condition metadata files
    candidates = []
    for s in session_inventory:
        if s["has_spk"] == "True" and s["has_lfp"] == "True" and s["has_condition_metadata"] == "True":
            candidates.append(s["session_id"])
            
    md_lines = [
        "# Omission Dataset Census & Taxonomy Summary Report",
        f"**Date**: 2026-05-21",
        f"**Truth Status**: `{TRUTH_SAFE_UNVERIFIED}`",
        "",
        "## Summary Metrics",
        f"- **Total Recorded Sessions**: {total_sessions}",
        f"- **Total Files Indexed**: {total_files}",
        f"- **SPK Availability**: {spk_sessions} sessions",
        f"- **MUAe Availability**: {muae_sessions} sessions",
        f"- **LFP Availability**: {lfp_sessions} sessions",
        "",
        "## Signal-Class Availability Table",
        "| Session ID | SPK Availability | MUAe Availability | LFP Availability | Behavior Availability | Manifest Availability |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |"
    ]
    
    for s in session_inventory:
        md_lines.append(
            f"| `{s['session_id']}` | `{s['has_spk']}` | `{s['has_muae']}` | "
            f"`{s['has_lfp']}` | `{s['has_behavior']}` | `{s['has_manifest']}` |"
        )
        
    md_lines.extend([
        "",
        "## Condition Coverage Table",
        "| Session ID | Conditions Detected | Missing Core Conditions |",
        "| :--- | :--- | :--- |"
    ])
    
    for s in session_inventory:
        md_lines.append(
            f"| `{s['session_id']}` | `{s['conditions_detected']}` | `{s['missing_core_conditions']}` |"
        )
        
    md_lines.extend([
        "",
        "## Missing Conditions by Session",
        "The following sessions are missing standard condition families or timing sequences:"
    ])
    
    missing_any = False
    for s in session_inventory:
        if s["missing_core_conditions"] != "None":
            missing_any = True
            md_lines.append(f"- **Session `{s['session_id']}`**: Missing `{s['missing_core_conditions']}`")
    if not missing_any:
        md_lines.append("- None. All sessions have complete condition coverage.")
        
    md_lines.extend([
        "",
        "## Candidate Sessions for A4 Trial-Count Validation",
        "Sessions that meet basic signal class and metadata completeness criteria to enter the next trial-level parsing phase:",
        f"Candidates: `{', '.join(candidates) if candidates else 'None'}`",
        "",
        "## Unresolved V3 Warnings",
        f"Total occurrences: {unresolved_v3_count}",
        "The following sessions contain generic `V3` mappings on Probe 2 (unresolved to `V3d`/`V3a` laminar boundaries):"
    ])
    
    for w in area_warnings_list:
        if w["warning_type"] == "unresolved_v3":
            md_lines.append(f"- **Session `{w['session_id']}`**: {w['detail']}")
            
    md_lines.extend([
        "",
        "## DP->V4 Warnings",
        f"Total occurrences: {dp_to_v4_count}",
        "The following sessions contain `DP` alias labels normalized to `V4`:"
    ])
    
    for w in area_warnings_list:
        if w["warning_type"] == "dp_to_v4":
            md_lines.append(f"- **Session `{w['session_id']}`**: {w['detail']}")
            
    md_lines.extend([
        "",
        "## Bounding & Payload Read Guard Verification Note",
        "> [!IMPORTANT]",
        "> Under the Phase 2/3 contracts, no high-density raw array payloads were loaded into local memory.",
        "> `.npy` files were lightly shape-inspected strictly using numpy memory mapping (`mmap_mode='r'`).",
        "> Non-npy formats (e.g. `.nwb`, `.mat`, `.h5`) were logged via file existence and size metadata only.",
        "",
        "## No Biological Claims Note",
        "This is a contract-level structural census and descriptive summary only. No average neural effect sizes, response latencies, tuning curves, or biological interpretations are proposed.",
        "",
        "---",
        f"Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: descriptive-census / Repo or Workspace: D:\\workspace\\omission / Date: 2026-05-21"
    ])
    
    md_path = out_dir / "dataset_census_summary.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"[success] Wrote {md_path}")
    
    # 4. Create dataset_census_summary.json
    json_summary = {
        "total_sessions": total_sessions,
        "total_files_indexed": total_files,
        "spk_sessions": spk_sessions,
        "muae_sessions": muae_sessions,
        "lfp_sessions": lfp_sessions,
        "unresolved_v3_count": unresolved_v3_count,
        "dp_to_v4_count": dp_to_v4_count,
        "candidates_suitable_for_a4": candidates,
        "warnings": [w["detail"] for w in area_warnings_list],
        "truth_status": TRUTH_SAFE_UNVERIFIED
    }
    
    json_path = out_dir / "dataset_census_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_summary, f, indent=2)
    print(f"[success] Wrote {json_path}")
    
    print("\nDataset census built successfully under: reports/analysis_A3_dataset_census")

if __name__ == "__main__":
    main()
