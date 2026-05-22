#!/usr/bin/env python3
# scripts/build_area_probe_metadata_inventory.py
"""
Phase A6 area/probe/unit/channel metadata inventory builder.
Links biological signals to session, probe, channel/unit axis anatomical mappings.
Enforces truth_status: truth_safe_unverified and no biological claims.
"""

import os
import csv
import json
import sys
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

TRUTH_SAFE_UNVERIFIED = "truth_safe_unverified"
CANONICAL_AREAS = ["V1", "V2", "V3d", "V3a", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"]

def parse_args():
    parser = argparse.ArgumentParser(description="Phase A6 Metadata Inventory Builder")
    parser.add_argument("--data-root", required=True, help="Path to raw/derived data root directory")
    parser.add_argument("--a5-dir", default="reports/analysis_A5_signal_shape_inventory", help="A5 signal shape inventory directory")
    parser.add_argument("--out-dir", default="reports/analysis_A6_area_probe_metadata", help="Output directory")
    parser.add_argument("--mapping-file", help="Path to master session-area-mapping.md")
    parser.add_argument("--subjects-file", help="Path to subjects.json")
    parser.add_argument("--allow-heuristic", action="store_true", help="Allow linear partition heuristic fallback when unit metadata CSV is missing")
    return parser.parse_args()

def normalize_area(area: str) -> str:
    area = area.strip()
    if area in ["DP", "DP (V4)"]:
        return "V4"
    return area

def get_area_group(area: str) -> str:
    norm = normalize_area(area)
    if norm in ["V1", "V2", "V3", "V3d", "V3a", "V4", "MT", "MST", "TEO", "FST"]:
        return "Visual"
    elif norm in ["FEF", "PFC"]:
        return "Frontal"
    return "Unknown"

def parse_mapping(mapping_file: Path):
    """
    Parses the canonical session-area-mapping.md markdown table.
    Returns: dict mapping session_id -> probe_id -> list of dict entries
    """
    if not mapping_file.exists():
        print(f"Error: Mapping file not found at {mapping_file}", file=sys.stderr)
        sys.exit(1)
        
    mapping = {}
    with open(mapping_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    table_started = False
    for line in lines:
        if "| Session |" in line:
            table_started = True
            continue
        if table_started and line.startswith("|") and not line.startswith("|:---"):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 4:
                session = parts[0]
                try:
                    probe = int(parts[1])
                    raw_areas_str = parts[2]
                    total_ch = int(parts[3])
                except ValueError:
                    continue
                    
                areas = [a.strip() for a in raw_areas_str.split(",")]
                n_areas = len(areas)
                boundaries = np.linspace(0, total_ch, n_areas + 1, dtype=int)
                
                if session not in mapping:
                    mapping[session] = {}
                    
                mapping[session][probe] = []
                for i, area_raw in enumerate(areas):
                    area_norm = normalize_area(area_raw)
                    start_ch = int(boundaries[i])
                    end_ch = int(boundaries[i+1])
                    
                    mapping[session][probe].append({
                        "raw_area": area_raw,
                        "area": area_norm,
                        "start_ch": start_ch,
                        "end_ch": end_ch,
                        "total_ch": total_ch
                    })
    return mapping

def main():
    args = parse_args()
    
    # Resolve output directory
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Resolve context paths
    script_dir = Path(__file__).parent.resolve()
    repo_root = script_dir.parent
    
    mapping_file = Path(args.mapping_file) if args.mapping_file else repo_root / "context" / "overview" / "session-area-mapping.md"
    subjects_file = Path(args.subjects_file) if args.subjects_file else repo_root / "context" / "overview" / "subjects.json"
    
    # Parse master mapping and subjects
    mapping_data = parse_mapping(mapping_file)
    
    subjects_data = {}
    if subjects_file.exists():
        with open(subjects_file, "r", encoding="utf-8") as f:
            subjects_data = json.load(f)
            
    # Load A5 report data
    a5_dir = Path(args.a5_dir)
    a5_inventory_path = a5_dir / "signal_shape_inventory.csv"
    a5_availability_path = a5_dir / "session_signal_availability.csv"
    
    if not a5_inventory_path.exists():
        print(f"Error: A5 shape inventory not found at {a5_inventory_path}", file=sys.stderr)
        sys.exit(1)
        
    a5_files = []
    with open(a5_inventory_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            a5_files.append(row)
            
    # Extract unique session list from A5
    session_ids = sorted(list(set(row["session_id"] for row in a5_files if row.get("session_id"))))
    
    # Track units count per (session, probe)
    # Formed from shape '(trials, units, time)' in A5 inventory for SPK files
    session_probe_units = {}
    for row in a5_files:
        if row["signal_class_inferred"] == "SPK" and row["extension"] == ".npy":
            s_id = row["session_id"]
            basename = row["basename"]
            shape_str = row["shape"]
            
            # Find probe number in basename, e.g. "ses230629-probe0-spk-AAAB.npy"
            import re
            m = re.search(r"probe(\d+)", basename)
            if not m:
                continue
            probe_id = int(m.group(1))
            
            # Parse shape (trials, units, time)
            if shape_str and shape_str.startswith("(") and shape_str.endswith(")"):
                try:
                    cleaned = shape_str.replace("(", "").replace(")", "").replace(" ", "")
                    parts = [int(x) for x in cleaned.split(",") if x]
                    if len(parts) == 3:
                        n_units = parts[1]
                        session_probe_units[(s_id, probe_id)] = n_units
                except ValueError:
                    pass
                    
    # Generate Output Tables structures
    session_inv_records = []
    probe_area_records = []
    channel_area_records = []
    unit_area_records = []
    signal_semantics_records = []
    warning_records = []
    
    # Counts for JSON summary
    sessions_lacking_metadata_count = 0
    sessions_resolved_metadata_count = 0
    probes_resolved_count = 0
    lfp_channels_resolved_count = 0
    lfp_channels_unresolved_count = 0
    spk_units_resolved_count = 0
    spk_units_unresolved_count = 0
    generic_v3_count = 0
    dp_v4_count = 0
    heuristic_used = False
    
    # Process each session
    for s_id in session_ids:
        subject_id = subjects_data.get(s_id, "Unknown")
        # Recording date parsed from session ID YYMMDD
        recording_date = f"20{s_id[:2]}-{s_id[2:4]}-{s_id[4:]}" if len(s_id) == 6 and s_id.isdigit() else "Unknown"
        
        spk_avail = "no"
        lfp_avail = "no"
        for row in a5_files:
            if row["session_id"] == s_id:
                if row["signal_class_inferred"] == "SPK":
                    spk_avail = "yes"
                elif row["signal_class_inferred"] == "LFP":
                    lfp_avail = "yes"
                    
        # Check metadata source availability
        csv_name = f"units_ses-{s_id}.csv"
        csv_path = Path(args.data_root) / "metadata" / csv_name
        
        has_mapping = s_id in mapping_data
        has_units_csv = csv_path.exists()
        
        meta_source = "None"
        meta_status = "unmapped_no_metadata"
        s_warns = []
        
        if has_mapping:
            meta_source = "session-area-mapping.md"
            meta_status = "partial_no_unit_metadata"
            if has_units_csv:
                meta_source += f" + {csv_name}"
                meta_status = "resolved"
                sessions_resolved_metadata_count += 1
            else:
                s_warns.append("No unit metadata CSV found; unit resolution unmapped")
                sessions_lacking_metadata_count += 1
        else:
            s_warns.append("No session-probe mapping found in session-area-mapping.md")
            sessions_lacking_metadata_count += 1
            
        session_inv_records.append({
            "session_id": s_id,
            "subject_id_or_status": subject_id,
            "recording_date_or_status": recording_date,
            "indexed_in_A5": "yes",
            "spk_available": spk_avail,
            "lfp_available": lfp_avail,
            "muae_available": "no",
            "metadata_source": meta_source,
            "metadata_status": meta_status,
            "warnings": "; ".join(s_warns) if s_warns else "None"
        })
        
        # If no mapping, we continue with unmapped for all signals
        if not has_mapping:
            continue
            
        # Parse active probes for this session
        session_probes = sorted(mapping_data[s_id].keys())
        
        # Compute SPK Probe unit cumulative offsets sequentially
        probe_offsets = {}
        cumulative = 0
        for p_id in sorted(list(set(p for (s, p) in session_probe_units.keys() if s == s_id))):
            n_u = session_probe_units.get((s_id, p_id), 0)
            if n_u > 0:
                probe_offsets[p_id] = cumulative
                cumulative += n_u
                
        # Load unit metadata DataFrame if available
        df_units = None
        if has_units_csv:
            try:
                df_units = pd.read_csv(csv_path)
            except Exception as e:
                print(f"Warning: Failed to load unit CSV {csv_path}: {e}", file=sys.stderr)
                
        # Process probes
        for p_id in session_probes:
            entries = mapping_data[s_id][p_id]
            
            # 1. Probe area inventory
            for entry in entries:
                raw_area = entry["raw_area"]
                canonical_area = entry["area"]
                area_group = get_area_group(canonical_area)
                
                alias = "yes" if "DP" in raw_area else "no"
                if alias == "yes":
                    dp_v4_count += 1
                    
                res_status = "metadata_resolved_equal_segment"
                if canonical_area == "V3":
                    res_status = "unresolved_generic_v3"
                    generic_v3_count += 1
                    
                probe_area_records.append({
                    "session_id": s_id,
                    "probe_id": str(p_id),
                    "raw_area_label": raw_area,
                    "canonical_area_label": canonical_area,
                    "area_group": area_group,
                    "alias_applied": alias,
                    "area_resolution_status": res_status,
                    "source_file": "session-area-mapping.md",
                    "warnings": "None"
                })
                probes_resolved_count += 1
                
            # 2. Channel area mapping (LFP/MUAe)
            for ch_idx in range(128):
                ch_id = p_id * 128 + ch_idx
                
                ch_area = None
                ch_raw = "None"
                ch_status = "unknown_area"
                
                for entry in entries:
                    if entry["start_ch"] <= ch_idx < entry["end_ch"]:
                        ch_area = entry["area"]
                        ch_raw = entry["raw_area"]
                        ch_status = "metadata_resolved_equal_segment"
                        if ch_area == "V3":
                            ch_status = "unresolved_generic_v3"
                        break
                        
                if ch_area:
                    lfp_channels_resolved_count += 1
                else:
                    lfp_channels_unresolved_count += 1
                    
                channel_area_records.append({
                    "session_id": s_id,
                    "signal_class": "LFP",
                    "probe_id": str(p_id),
                    "channel_id": str(ch_id),
                    "channel_index": str(ch_idx),
                    "raw_area_label": ch_raw,
                    "canonical_area_label": ch_area if ch_area else "Unknown",
                    "area_group": get_area_group(ch_area) if ch_area else "Unknown",
                    "area_resolution_status": ch_status,
                    "layer_or_depth_label": "estimated_from_channel",
                    "source_file": "session-area-mapping.md",
                    "warnings": "None"
                })
                
            # 3. Unit area mapping (SPK/SUA)
            n_units = session_probe_units.get((s_id, p_id), 0)
            for u_idx in range(n_units):
                unit_id = f"ses-{s_id}_probe{p_id}_unit{u_idx}"
                
                u_area = None
                u_raw = "None"
                u_status = "unmapped_no_metadata"
                u_warns = []
                snr = "Unknown"
                presence_ratio = "Unknown"
                peak_ch_val = "missing_metadata"
                
                if df_units is not None and p_id in probe_offsets:
                    offset = probe_offsets[p_id]
                    global_idx = offset + u_idx
                    
                    if global_idx < len(df_units):
                        row = df_units.iloc[global_idx]
                        peak_ch = row.get("peak_channel_id")
                        
                        if pd.notna(row.get("snr")):
                            snr = f"{row['snr']:.2f}"
                        if pd.notna(row.get("presence_ratio")):
                            presence_ratio = f"{row['presence_ratio']:.2f}"
                            
                        if pd.notna(peak_ch):
                            peak_ch_val = str(int(peak_ch))
                            peak_ch = int(peak_ch)
                            u_p_idx = int(peak_ch // 128)
                            u_local_ch = int(peak_ch % 128)
                            
                            if u_p_idx != p_id:
                                detail = f"Peak channel probe {u_p_idx} mismatch with unit data probe {p_id}"
                                u_warns.append(detail)
                                u_status = "invalid_probe"
                                warning_records.append({
                                    "session_id": s_id,
                                    "probe_id": str(p_id),
                                    "warning_type": "probe_mismatch",
                                    "detail": detail,
                                    "truth_status": TRUTH_SAFE_UNVERIFIED
                                })
                            else:
                                for entry in entries:
                                    if entry["start_ch"] <= u_local_ch < entry["end_ch"]:
                                        u_area = entry["area"]
                                        u_raw = entry["raw_area"]
                                        u_status = "metadata_resolved_equal_segment"
                                        if u_area == "V3":
                                            u_status = "unresolved_generic_v3"
                                        break
                                if not u_area:
                                    u_status = "unknown_area"
                                    u_warns.append(f"Channel {u_local_ch} does not map to any area segment on probe {p_id}")
                        else:
                            u_warns.append("peak_channel_id is NaN in metadata CSV")
                            u_status = "unmapped_no_metadata"
                    else:
                        u_warns.append("Unit global index out of bounds in metadata CSV")
                        u_status = "unmapped_no_metadata"
                else:
                    # Missing metadata CSV fallback
                    if args.allow_heuristic:
                        heuristic_used = True
                        # Apply linear segment heuristic partition
                        for entry in entries:
                            u_start = int(n_units * (entry["start_ch"] / entry["total_ch"]))
                            u_end = int(n_units * (entry["end_ch"] / entry["total_ch"]))
                            if u_start <= u_idx < u_end:
                                u_area = entry["area"]
                                u_raw = entry["raw_area"]
                                u_status = "heuristic_equal_segment"
                                if u_area == "V3":
                                    u_status = "unresolved_generic_v3"
                                u_warns.append("No unit metadata CSV found; used linear segment heuristic")
                                break
                    else:
                        u_status = "unmapped_no_metadata"
                        u_warns.append("No unit metadata CSV file found")
                        
                if u_area:
                    spk_units_resolved_count += 1
                else:
                    spk_units_unresolved_count += 1
                    
                unit_area_records.append({
                    "session_id": s_id,
                    "unit_id": unit_id,
                    "unit_index": str(u_idx),
                    "sorting_quality_or_status": f"snr={snr}, presence_ratio={presence_ratio}" if snr != "Unknown" else "Unknown",
                    "peak_channel_or_status": peak_ch_val,
                    "anchor_channel_or_status": peak_ch_val,
                    "probe_id_or_status": str(p_id),
                    "raw_area_label": u_raw,
                    "canonical_area_label": u_area if u_area else "Unknown",
                    "area_group": get_area_group(u_area) if u_area else "Unknown",
                    "area_resolution_status": u_status,
                    "source_file": csv_name if has_units_csv else "session-area-mapping.md",
                    "warnings": "; ".join(u_warns) if u_warns else "None"
                })
                
    # 4. Signal axis semantics mapping
    for row in a5_files:
        ext = row["extension"]
        if ext != ".npy":
            continue
            
        s_id = row["session_id"]
        basename = row["basename"]
        sig_class = row["signal_class_inferred"]
        cond = row["condition_inferred"]
        shape_str = row["shape"]
        
        # Parse dims semantics and sizes from shape
        n_trials = 0
        n_axis1 = 0
        n_timepoints = 0
        axis1_sem = "None"
        
        if shape_str and shape_str.startswith("(") and shape_str.endswith(")"):
            try:
                cleaned = shape_str.replace("(", "").replace(")", "").replace(" ", "")
                parts = [int(x) for x in cleaned.split(",") if x]
                if len(parts) == 3:
                    n_trials = parts[0]
                    n_axis1 = parts[1]
                    n_timepoints = parts[2]
            except ValueError:
                pass
                
        if sig_class == "SPK":
            axis1_sem = "unit"
            dims = "trial, unit, time"
        elif sig_class in ["LFP", "MUAe"]:
            axis1_sem = "channel"
            dims = "trial, channel, time"
        else:
            dims = "None"
            
        area_mapping_possible = "yes" if s_id in mapping_data else "no"
        
        signal_semantics_records.append({
            "session_id": s_id,
            "condition": cond if cond else "None",
            "signal_class": sig_class,
            "source_file": basename,
            "shape": shape_str,
            "dims": dims,
            "axis0_semantics": "trial",
            "axis1_semantics": axis1_sem,
            "axis2_semantics": "time",
            "n_trials": str(n_trials),
            "n_units_or_channels": str(n_axis1),
            "n_timepoints": str(n_timepoints),
            "time_base_status": "p1_relative",
            "area_mapping_possible": area_mapping_possible,
            "warnings": "None"
        })
        
    # Write Output Tables as CSV
    def save_csv(path, fields, records):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in records:
                writer.writerow(r)
                
    save_csv(out_dir / "session_metadata_inventory.csv", [
        "session_id", "subject_id_or_status", "recording_date_or_status", "indexed_in_A5",
        "spk_available", "lfp_available", "muae_available", "metadata_source", "metadata_status", "warnings"
    ], session_inv_records)
    
    save_csv(out_dir / "probe_area_inventory.csv", [
        "session_id", "probe_id", "raw_area_label", "canonical_area_label",
        "area_group", "alias_applied", "area_resolution_status", "source_file", "warnings"
    ], probe_area_records)
    
    save_csv(out_dir / "channel_area_inventory.csv", [
        "session_id", "signal_class", "probe_id", "channel_id", "channel_index",
        "raw_area_label", "canonical_area_label", "area_group", "area_resolution_status",
        "layer_or_depth_label", "source_file", "warnings"
    ], channel_area_records)
    
    save_csv(out_dir / "unit_area_inventory.csv", [
        "session_id", "unit_id", "unit_index", "sorting_quality_or_status",
        "peak_channel_or_status", "anchor_channel_or_status", "probe_id_or_status",
        "raw_area_label", "canonical_area_label", "area_group", "area_resolution_status",
        "source_file", "warnings"
    ], unit_area_records)
    
    save_csv(out_dir / "signal_axis_semantics_inventory.csv", [
        "session_id", "condition", "signal_class", "source_file", "shape", "dims",
        "axis0_semantics", "axis1_semantics", "axis2_semantics", "n_trials",
        "n_units_or_channels", "n_timepoints", "time_base_status", "area_mapping_possible", "warnings"
    ], signal_semantics_records)
    
    save_csv(out_dir / "area_mapping_warnings.csv", [
        "session_id", "probe_id", "warning_type", "detail", "truth_status"
    ], warning_records)
    
    # Save JSON summary
    summary_json = {
        "truth_status": TRUTH_SAFE_UNVERIFIED,
        "total_sessions": len(session_ids),
        "sessions_with_resolved_metadata": sessions_resolved_metadata_count,
        "sessions_lacking_metadata": sessions_lacking_metadata_count,
        "probes_resolved": probes_resolved_count,
        "lfp_channels_resolved": lfp_channels_resolved_count,
        "lfp_channels_unresolved": lfp_channels_unresolved_count,
        "spk_units_resolved": spk_units_resolved_count,
        "spk_units_unresolved": spk_units_unresolved_count,
        "generic_v3_labels_encountered": generic_v3_count,
        "dp_v4_aliases_applied": dp_v4_count,
        "one_probe_one_area_assumption_used": False,
        "equal_segment_heuristic_used": heuristic_used,
        "raw_payload_or_npy_payload_read": False
    }
    
    with open(out_dir / "area_probe_metadata_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2)
        
    # Generate area_probe_metadata_summary.md
    summary_rows = []
    for row in session_inv_records:
        summary_rows.append(
            f"| `{row['session_id']}` | `{row['subject_id_or_status']}` | `{row['recording_date_or_status']}` | `{row['metadata_status']}` | `{row['warnings']}` |"
        )
        
    md_content = f"""# Omission Phase A6 Area/Probe Metadata Inventory
**Truth Status**: `{TRUTH_SAFE_UNVERIFIED}`

This analytical command center report summarizes Phase A6 anatomical mappings linking indexed biological signals to session, probe, channel, and unit axis boundaries.

## Summary Analytics
- **Total Sessions Mapped**: {summary_json['total_sessions']}
- **Sessions with Fully Resolved Metadata**: {summary_json['sessions_with_resolved_metadata']}
- **Sessions Lacking Unit Metadata CSVs**: {summary_json['sessions_lacking_metadata']}
- **Probes Resolved deterministically**: {summary_json['probes_resolved']}
- **LFP Channels Mapped**: {summary_json['lfp_channels_resolved']} resolved (`{summary_json['lfp_channels_unresolved']}` unmapped)
- **SPK Units Mapped**: {summary_json['spk_units_resolved']} resolved (`{summary_json['spk_units_unresolved']}` unmapped)
- **Generic V3 Labels Encountered**: {summary_json['generic_v3_labels_encountered']} (retains `unresolved_generic_v3` status)
- **DP -> V4 Aliases Applied**: {summary_json['dp_v4_aliases_applied']} (aliased DP/DP (V4) -> V4)

## Session Metadata Inventory
| Session ID | Subject ID | Recording Date | Metadata Status | Warnings / Context |
| :--- | :--- | :--- | :--- | :--- |
{f"{chr(10)}".join(summary_rows)}

## Probe and Axis Semantics Note
- **SPK/SUA Axis Semantics**: Structured as expected rank-3 dimensions (`trial x unit x time`), with units mapped via metadata `peak_channel_id` where available.
- **LFP Axis Semantics**: Structured as expected rank-3 dimensions (`trial x channel x time`), with channels partitioned deterministically using probe equal-segment channel boundaries.
- **MUAe**: No files detected in A5, MUAe continues to receive `not_detected_in_current_index` status.

## Safety & Architectural Constraints
- **One-Probe-One-Area Assumption Used**: `{summary_json['one_probe_one_area_assumption_used']}` (probes can deterministically span multiple named visual/frontal areas).
- **Equal-Segment Heuristic Used**: `{summary_json['equal_segment_heuristic_used']}` (applied linear partitioning for unit index assignment only when specified).
- **Raw Payload or NPY Payload Read**: `{summary_json['raw_payload_or_npy_payload_read']}` (all mappings were resolved strictly utilizing metadata sheets, filenames, and shape descriptors).

## Blockers before Phase A7 Sanity Checks
- Verification and approval of A6 area mappings must be finalized.
- Target unit and channel mapping profiles must match baseline predictions. No empirical rasters/PSTHs can be constructed until this inventory gate is accepted.

---
Footer: Agent: Claude / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: descriptive-signal-shapes / Repo or Workspace: D:\\workspace\\omission / Date: 2026-05-22
"""

    with open(out_dir / "area_probe_metadata_summary.md", "w", encoding="utf-8") as f:
        f.write(md_content)
        
    print(f"A6 Metadata Inventory complete. Reports written to {args.out_dir}")

if __name__ == "__main__":
    main()
