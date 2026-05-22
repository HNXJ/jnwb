#!/usr/bin/env python3
# scripts/build_trial_count_validation.py
"""
Phase A4 session x condition trial-count validation from metadata and filename inventories.
Generates comprehensive trial-count matrices, balance summaries, and completeness reports.
Declares truth_status: truth_safe_unverified on all outputs.
"""

import os
import csv
import json
import sys
import argparse
from pathlib import Path

# Standard constants
TRUTH_SAFE_UNVERIFIED = "truth_safe_unverified"
CONDITIONS = ["AAAB", "AXAB", "AAXB", "AAAX", "BBBA", "BXBA", "BBXA", "BBBX", "RRRR", "RXRR", "RRXR", "RRRX"]

def parse_args():
    parser = argparse.ArgumentParser(description="Phase A4 Trial-Count Validation")
    parser.add_argument("--data-root", required=True, help="Path to raw/derived data root directory")
    parser.add_argument("--a3-dir", default="reports/analysis_A3_dataset_census", help="A3 dataset census directory")
    parser.add_argument("--out-dir", default="reports/analysis_A4_trial_count_validation", help="Output directory")
    return parser.parse_args()

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

def find_trial_count_sources(session_id, data_root, a3_dir):
    """Finds all JSON/CSV metadata files containing trial counts for a session."""
    sources = []
    # Search data_root, a3_dir, and test fixtures folders
    search_dirs = [Path(data_root), Path(a3_dir), Path("tests/fixtures/manifests")]
    
    seen_paths = set()
    for s_dir in search_dirs:
        if not s_dir.exists() or not s_dir.is_dir():
            continue
        for p in s_dir.rglob("*"):
            if not p.is_file():
                continue
            path_resolved = p.resolve()
            if path_resolved in seen_paths:
                continue
            
            name_lower = p.name.lower()
            # Must match session_id and not contain raw signals
            if session_id in p.name:
                if p.suffix == ".json" and ("manifest" in name_lower or p.name.startswith(session_id)):
                    sources.append((p, "json"))
                    seen_paths.add(path_resolved)
                elif p.suffix == ".csv" and ("trial_count" in name_lower or "manifest" in name_lower or p.name.startswith(session_id)):
                    sources.append((p, "csv"))
                    seen_paths.add(path_resolved)
    return sources

def extract_trial_counts(path, file_type, session_id):
    """Parses JSON or CSV metadata to extract condition-level trial counts."""
    counts = {}
    try:
        if file_type == "json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Check session_id if present to prevent cross-session pollution
            if "session_id" in data and str(data["session_id"]).strip() != str(session_id):
                return {}
                
            # Try parsing conditions list
            if "conditions" in data and isinstance(data["conditions"], list):
                for item in data["conditions"]:
                    if isinstance(item, dict):
                        code = item.get("code") or item.get("condition")
                        count = item.get("trial_count")
                        if code and count is not None:
                            counts[str(code).upper()] = int(count)
            # Try parsing trial_counts dictionary
            elif "trial_counts" in data and isinstance(data["trial_counts"], dict):
                for k, v in data["trial_counts"].items():
                    counts[str(k).upper()] = int(v)
                    
        elif file_type == "csv":
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                headers = [h.lower() for h in reader.fieldnames] if reader.fieldnames else []
                
                cond_col = None
                for col in ["condition", "code", "condition_code"]:
                    if col in headers:
                        cond_col = reader.fieldnames[headers.index(col)]
                        break
                
                count_col = None
                for col in ["trial_count", "trials", "n_trials", "count"]:
                    if col in headers:
                        count_col = reader.fieldnames[headers.index(col)]
                        break
                        
                session_col = None
                for col in ["session_id", "session"]:
                    if col in headers:
                        session_col = reader.fieldnames[headers.index(col)]
                        break
                
                if cond_col and count_col:
                    for row in reader:
                        if session_col and str(row[session_col]).strip() != str(session_id):
                            continue
                        c = str(row[cond_col]).strip().upper()
                        val = row[count_col]
                        if val:
                            counts[c] = int(val)
    except Exception:
        pass
    return counts

def main():
    args = parse_args()
    
    # Ensure output directory exists
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Load session inventory
    session_ids = []
    session_warnings = {}
    session_inventory_path = Path(args.a3_dir) / "session_inventory.csv"
    if not session_inventory_path.exists():
        print(f"Error: A3 session inventory not found at {session_inventory_path}", file=sys.stderr)
        sys.exit(1)
        
    with open(session_inventory_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            s_id = row["session_id"].strip()
            session_ids.append(s_id)
            session_warnings[s_id] = row.get("warnings") or ""
            
    # Load condition inventory
    condition_inventory_path = Path(args.a3_dir) / "condition_inventory.csv"
    file_presence = {}
    if condition_inventory_path.exists():
        with open(condition_inventory_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                s_id = row["session_id"].strip()
                cond = row["condition"].strip().upper()
                file_presence[(s_id, cond)] = {
                    "signal_classes": row.get("signal_classes_detected") or "",
                    "source_basenames": row.get("source_basenames") or "",
                }
                
    # Parse area warnings from area_mapping_warnings.csv
    area_warnings = {}
    area_mapping_warnings_path = Path(args.a3_dir) / "area_mapping_warnings.csv"
    if area_mapping_warnings_path.exists():
        with open(area_mapping_warnings_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                s_id = row["session_id"].strip()
                warn_text = row.get("warning_detail") or row.get("warning") or ""
                if warn_text:
                    if s_id not in area_warnings:
                        area_warnings[s_id] = []
                    area_warnings[s_id].append(warn_text)

    # Initialize data structures for A4 output
    matrix_records = []
    balance_records = []
    completeness_records = []
    warning_records = []
    
    # Process each session
    for s_id in session_ids:
        # Find explicit sources for trial counts
        sources = find_trial_count_sources(s_id, args.data_root, args.a3_dir)
        source_counts = {}
        for path, file_type in sources:
            counts = extract_trial_counts(path, file_type, s_id)
            if counts:
                source_counts[path.name] = counts
                
        # Gather general session alerts from A3
        s_warn_str = session_warnings.get(s_id, "")
        s_alerts = []
        if s_warn_str and s_warn_str != "None":
            s_alerts.append(s_warn_str)
        if s_id in area_warnings:
            s_alerts.extend(area_warnings[s_id])
            
        # Log session level warnings for unresolved V3 and DP alias
        for alert in s_alerts:
            w_type = "unspecified_warning"
            if "unresolved" in alert.lower() or "v3" in alert.lower():
                w_type = "unresolved_v3_area"
            elif "dp" in alert.lower() or "v4" in alert.lower():
                w_type = "normalized_dp_area"
                
            warning_records.append({
                "session_id": s_id,
                "warning_type": w_type,
                "condition": "None",
                "detail": alert,
                "source_basename": "",
                "truth_status": TRUTH_SAFE_UNVERIFIED
            })

        # Process standard 12 conditions
        session_conditions_detected = []
        session_condition_trial_counts = {} # Maps cond -> count (int or None)
        session_condition_statuses = {} # Maps cond -> status string
        
        for cond in CONDITIONS:
            family = get_condition_family(cond)
            om_pos = get_omission_position(cond)
            ctrl = get_matched_control(cond)
            
            # Collect counts for this condition from all sources
            counts_list = []
            for src_name, counts in source_counts.items():
                if cond in counts:
                    counts_list.append(counts[cond])
                    
            # Check presence from file inventories
            presence = file_presence.get((s_id, cond))
            has_files = presence is not None
            source_files = presence["source_basenames"] if has_files else ""
            sig_classes = presence["signal_classes"] if has_files else ""
            
            # Resolve count and status
            trial_count = None
            status = "missing"
            warnings_list = []
            
            if not counts_list:
                if has_files:
                    trial_count = None
                    status = "inferred_from_file_inventory"
                    warnings_list.append(f"Trial count inferred from file inventory; no explicit metadata found")
                    warning_records.append({
                        "session_id": s_id,
                        "warning_type": "inferred_trial_count",
                        "condition": cond,
                        "detail": f"Condition {cond} trial count inferred from file inventory presence; no explicit metadata found",
                        "source_basename": source_files,
                        "truth_status": TRUTH_SAFE_UNVERIFIED
                    })
                else:
                    trial_count = None
                    status = "missing"
                    warnings_list.append(f"Condition {cond} is missing from session inventories")
                    warning_records.append({
                        "session_id": s_id,
                        "warning_type": "missing_condition",
                        "condition": cond,
                        "detail": f"Condition {cond} is missing from session {s_id} inventories",
                        "source_basename": "",
                        "truth_status": TRUTH_SAFE_UNVERIFIED
                    })
            else:
                unique_counts = list(set(counts_list))
                if len(unique_counts) == 1:
                    trial_count = unique_counts[0]
                    status = "observed"
                else:
                    trial_count = None
                    status = "ambiguous"
                    src_list_str = "; ".join(source_counts.keys())
                    detail_str = f"Multiple conflicting trial count sources found for {cond} (counts: {counts_list})"
                    warnings_list.append(detail_str)
                    warning_records.append({
                        "session_id": s_id,
                        "warning_type": "inconsistent_trial_counts",
                        "condition": cond,
                        "detail": detail_str,
                        "source_basename": src_list_str,
                        "truth_status": TRUTH_SAFE_UNVERIFIED
                    })
                    
            if has_files or status == "observed" or status == "ambiguous":
                session_conditions_detected.append(cond)
                
            session_condition_trial_counts[cond] = trial_count
            session_condition_statuses[cond] = status
            
            # Record in matrix list
            matrix_records.append({
                "session_id": s_id,
                "condition": cond,
                "family": family,
                "omission_position": om_pos,
                "matched_control": ctrl,
                "n_trial_count_sources": len(counts_list),
                "trial_count": trial_count if trial_count is not None else "",
                "trial_count_status": status,
                "source_basenames": source_files,
                "signal_classes_with_condition": sig_classes,
                "warnings": "; ".join(warnings_list) if warnings_list else "None",
                "truth_status": TRUTH_SAFE_UNVERIFIED
            })

        # Calculate balance summaries (omissions vs controls)
        omissions = [c for c in CONDITIONS if get_omission_position(c) != "None"]
        for om_cond in omissions:
            family = get_condition_family(om_cond)
            om_pos = get_omission_position(om_cond)
            ctrl = get_matched_control(om_cond)
            
            om_count = session_condition_trial_counts[om_cond]
            ctrl_count = session_condition_trial_counts[ctrl]
            
            om_status = session_condition_statuses[om_cond]
            ctrl_status = session_condition_statuses[ctrl]
            
            balance_status = "unknown"
            ratio = ""
            b_warns = []
            
            if om_status == "missing" or ctrl_status == "missing":
                balance_status = "missing"
                if om_status == "missing":
                    b_warns.append(f"Omission condition {om_cond} is missing")
                if ctrl_status == "missing":
                    b_warns.append(f"Control condition {ctrl} is missing")
            elif om_count is not None and ctrl_count is not None:
                ratio = round(float(om_count) / float(ctrl_count), 3)
                if om_count == ctrl_count:
                    balance_status = "balanced"
                else:
                    balance_status = "imbalanced"
                    detail_str = f"Trial count imbalanced: omission {om_cond} has {om_count} trials while control {ctrl} has {ctrl_count} trials"
                    b_warns.append(detail_str)
                    warning_records.append({
                        "session_id": s_id,
                        "warning_type": "imbalanced_condition",
                        "condition": om_cond,
                        "detail": detail_str,
                        "source_basename": "",
                        "truth_status": TRUTH_SAFE_UNVERIFIED
                    })
            else:
                balance_status = "unknown"
                b_warns.append("Explicit trial counts unavailable; balance cannot be verified")
                
            balance_records.append({
                "session_id": s_id,
                "family": family,
                "omission_position": om_pos,
                "omission_condition": om_cond,
                "matched_control": ctrl,
                "omission_trial_count": om_count if om_count is not None else "",
                "control_trial_count": ctrl_count if ctrl_count is not None else "",
                "balance_status": balance_status,
                "ratio_omission_to_control": ratio,
                "warnings": "; ".join(b_warns) if b_warns else "None",
                "truth_status": TRUTH_SAFE_UNVERIFIED
            })

        # Calculate completeness
        n_detected = len(session_conditions_detected)
        missing_conds = [c for c in CONDITIONS if c not in session_conditions_detected]
        
        has_A = all(c in session_conditions_detected for c in ["AAAB", "AXAB", "AAXB", "AAAX"])
        has_B = all(c in session_conditions_detected for c in ["BBBA", "BXBA", "BBXA", "BBBX"])
        has_R = all(c in session_conditions_detected for c in ["RRRR", "RXRR", "RRXR", "RRRX"])
        
        has_p2 = all(c in session_conditions_detected for c in ["AXAB", "BXBA", "RXRR"])
        has_p3 = all(c in session_conditions_detected for c in ["AAXB", "BBXA", "RRXR"])
        has_p4 = all(c in session_conditions_detected for c in ["AAAX", "BBBX", "RRRX"])
        
        readiness = "yes" if n_detected == 12 else "no"
        c_warns = []
        if n_detected < 12:
            c_warns.append(f"Missing {12 - n_detected} conditions: {', '.join(missing_conds)}")
            
        completeness_records.append({
            "session_id": s_id,
            "n_conditions_detected": n_detected,
            "conditions_detected": ",".join(sorted(session_conditions_detected)),
            "missing_conditions": ",".join(sorted(missing_conds)) if missing_conds else "None",
            "has_all_A_family": "yes" if has_A else "no",
            "has_all_B_family": "yes" if has_B else "no",
            "has_all_R_family": "yes" if has_R else "no",
            "has_all_p2_omissions": "yes" if has_p2 else "no",
            "has_all_p3_omissions": "yes" if has_p3 else "no",
            "has_all_p4_omissions": "yes" if has_p4 else "no",
            "readiness_for_A5": readiness,
            "warnings": "; ".join(c_warns) if c_warns else "None",
            "truth_status": TRUTH_SAFE_UNVERIFIED
        })

    # Save outputs as CSV files
    def save_csv(path, fields, records):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in records:
                writer.writerow(r)
                
    save_csv(out_dir / "trial_count_matrix.csv", [
        "session_id", "condition", "family", "omission_position", "matched_control",
        "n_trial_count_sources", "trial_count", "trial_count_status",
        "source_basenames", "signal_classes_with_condition", "warnings", "truth_status"
    ], matrix_records)
    
    save_csv(out_dir / "condition_balance_summary.csv", [
        "session_id", "family", "omission_position", "omission_condition", "matched_control",
        "omission_trial_count", "control_trial_count", "balance_status",
        "ratio_omission_to_control", "warnings", "truth_status"
    ], balance_records)
    
    save_csv(out_dir / "session_condition_completeness.csv", [
        "session_id", "n_conditions_detected", "conditions_detected", "missing_conditions",
        "has_all_A_family", "has_all_B_family", "has_all_R_family",
        "has_all_p2_omissions", "has_all_p3_omissions", "has_all_p4_omissions",
        "readiness_for_A5", "warnings", "truth_status"
    ], completeness_records)
    
    save_csv(out_dir / "trial_count_warnings.csv", [
        "session_id", "warning_type", "condition", "detail", "source_basename", "truth_status"
    ], warning_records)

    # Save JSON summary
    summary_json = {
        "truth_status": TRUTH_SAFE_UNVERIFIED,
        "total_sessions": len(session_ids),
        "sessions": session_ids,
        "completeness": completeness_records,
        "warnings_count": len(warning_records),
        "inferred_count": len([r for r in matrix_records if r["trial_count_status"] == "inferred_from_file_inventory"]),
        "observed_count": len([r for r in matrix_records if r["trial_count_status"] == "observed"]),
        "missing_count": len([r for r in matrix_records if r["trial_count_status"] == "missing"]),
        "ambiguous_count": len([r for r in matrix_records if r["trial_count_status"] == "ambiguous"])
    }
    
    with open(out_dir / "trial_count_validation_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2)

    # Generate trial_count_validation_summary.md
    summary_md_path = out_dir / "trial_count_validation_summary.md"
    
    completeness_rows = []
    for r in completeness_records:
        completeness_rows.append(
            f"| `{r['session_id']}` | {r['n_conditions_detected']} | {r['readiness_for_A5']} | {r['has_all_A_family']} | {r['has_all_B_family']} | {r['has_all_R_family']} |"
        )
        
    warnings_summary_rows = []
    # Deduplicate alerts in the MD summary
    shown_alerts = set()
    for w in warning_records:
        alert_key = (w["session_id"], w["warning_type"], w["condition"])
        if alert_key in shown_alerts:
            continue
        shown_alerts.add(alert_key)
        warnings_summary_rows.append(
            f"| `{w['session_id']}` | `{w['warning_type']}` | `{w['condition']}` | {w['detail']} |"
        )
        
    md_content = f"""# Omission Phase A4 Trial-Count Validation Report
**Truth Status**: `{TRUTH_SAFE_UNVERIFIED}`

This analytical command center report verifies the structural completeness, trial count balances, and matched-control ratios across recording sessions using metadata inventories and filename maps.

## Summary Analytics
- **Total Sessions Analyzed**: {len(session_ids)}
- **Metadata Sources Available**: {len(sources)} explicit files
- **Observed Trial Counts**: {summary_json['observed_count']} session-condition entries
- **Inferred (File-Only) Conditions**: {summary_json['inferred_count']} session-condition entries
- **Missing Conditions**: {summary_json['missing_count']} entries
- **Ambiguous Configurations**: {summary_json['ambiguous_count']} entries
- **Total Diagnostic Warnings**: {summary_json['warnings_count']}

## Session Completeness & Readiness
| Session ID | Conditions Detected (out of 12) | Ready for A5 | All A Family | All B Family | All R Family |
| :--- | :---: | :---: | :---: | :---: | :---: |
{chr(10).join(completeness_rows)}

## Condition Balance & Control Match Status
For all sessions, condition trial-counts are descriptive filename-derived or explicit.
No neural effect sizes have been computed.

## Diagnostic Warnings & Alerts
| Session ID | Warning Type | Condition | Detail |
| :--- | :--- | :--- | :--- |
{chr(10).join(warnings_summary_rows) if warnings_summary_rows else "| None | - | - | All validations passed completely |"}

## Light Metadata Bounding Note
> [!IMPORTANT]
> Under predictive routing execution guidelines, no high-density neural array payloads were loaded.
> Trial counts are parsed purely from high-level metadata catalogs and file naming schemas.

## No Biological Claims Note
This validation table is generated strictly for structural checks and matched balance reporting. No physiological hypotheses or empirical conclusions are drawn.

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: descriptive-trial-counts / Repo or Workspace: D:\\workspace\\omission / Date: 2026-05-22
"""

    with open(summary_md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"A4 Trial-Count Validation complete. Outputs written to {args.out_dir}")

if __name__ == "__main__":
    main()
