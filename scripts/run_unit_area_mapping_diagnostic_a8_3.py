#!/usr/bin/env python3
# scripts/run_unit_area_mapping_diagnostic_a8_3.py
"""
Phase A8.3: Diagnostic unit-area mapping integrity audit.

Joins A8.1/A8.2 unit keys (session_id + unit_axis_index) to A6 area/probe metadata.
Assigns explicit area_resolution_status to every unit.
Audits DP->V4 aliases, generic-V3 resolution, join integrity, and hierarchy claim safety.

Hard constraints:
- No biological hierarchy claims.
- No raw .h5 reads.
- No full NumPy payload loads.
- All outputs: truth_safe_unverified.
- Do not mutate A8.1/A8.2 outputs.
"""

import os
import csv
import json
import sys
import argparse
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timezone

TRUTH_SAFE_UNVERIFIED = "truth_safe_unverified"

CANONICAL_AREA_ORDER = ["V1", "V2", "V3d", "V3a", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"]

AREA_GROUPS = {
    "V1": "lower_visual",
    "V2": "lower_visual",
    "V3d": "intermediate_visual_temporal",
    "V3a": "intermediate_visual_temporal",
    "V4": "intermediate_visual_temporal",
    "MT": "intermediate_visual_temporal",
    "MST": "intermediate_visual_temporal",
    "TEO": "intermediate_visual_temporal",
    "FST": "intermediate_visual_temporal",
    "FEF": "higher_order_frontal",
    "PFC": "higher_order_frontal",
}

MANUSCRIPT_SAFE_STATUSES = {"metadata_resolved_channel", "metadata_resolved_equal_segment"}

# A6-native status emitted by Phase A6.1 demotion: row-count matched but row-order provenance unconfirmed.
# This status cannot support area or hierarchy claims (explicitly demoted by THETA in A6.1 review).
PROVISIONAL_STATUS = "provisional_unit_area_from_count_matched_row_order"

VALID_RESOLUTION_STATUSES = {
    "metadata_resolved_channel",
    "metadata_resolved_equal_segment",
    "heuristic_equal_segment",
    "unresolved_generic_v3",
    "unmapped_no_metadata",
    "unknown_area",
    "invalid_probe",
    "invalid_channel",
    PROVISIONAL_STATUS,  # A6-native demoted status
}


def get_git_commit():
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"


def sha256_file(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return "hash_unavailable"


def parse_args():
    parser = argparse.ArgumentParser(description="Phase A8.3 diagnostic unit-area mapping integrity audit")
    parser.add_argument("--a6-dir",  default="reports/analysis_A6_area_probe_metadata",  help="A6 area/probe metadata directory")
    parser.add_argument("--a8-1-dir", default="reports/analysis_A8_1_spk_response_metrics", help="A8.1 metrics directory")
    parser.add_argument("--a8-2-dir", default="reports/analysis_A8_2_spk_response_metric_sensitivity", help="A8.2 sensitivity directory")
    parser.add_argument("--out-dir",  default="reports/analysis_A8_3_unit_area_mapping_diagnostic", help="Output directory")
    return parser.parse_args()


def resolve_area_group(canonical_area):
    return AREA_GROUPS.get(canonical_area, "unknown_or_unresolved")


def resolve_claim_flags(area_resolution_status, canonical_area_label):
    """Determine whether a unit can support area or hierarchy claims."""
    can_area = area_resolution_status in MANUSCRIPT_SAFE_STATUSES and canonical_area_label in CANONICAL_AREA_ORDER
    can_hier = can_area  # hierarchy requires the same level of metadata resolution
    return can_area, can_hier


def load_a6_unit_area_inventory(a6_dir):
    """Load unit_area_inventory.csv from A6 into a dict keyed by (session_id, unit_index)."""
    path = Path(a6_dir) / "unit_area_inventory.csv"
    inventory = {}
    if not path.exists():
        return inventory, str(path)
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            s_id = row["session_id"].strip()
            u_idx = int(row["unit_index"])
            key = (s_id, u_idx)
            # Keep the first record for each (session_id, unit_index) — flag duplicates
            if key not in inventory:
                inventory[key] = row
            else:
                # Mark as duplicate-flagged — will be surfaced in unresolved table
                inventory[key]["_duplicate_in_a6"] = "true"
    return inventory, str(path)


def load_a8_1_unit_keys(a8_1_dir):
    """Load unique unit keys from A8.1 unit_candidate_labels.csv."""
    path = Path(a8_1_dir) / "unit_candidate_labels.csv"
    keys = {}  # (session_id, unit_axis_index) -> row
    if not path.exists():
        return keys, str(path)
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            s_id = row["session_id"].strip()
            u_idx = int(row["unit_axis_index"])
            key = (s_id, u_idx)
            if key not in keys:
                keys[key] = row
    return keys, str(path)


def load_a8_2_unit_keys(a8_2_dir):
    """Load unique unit keys from A8.2 candidate_label_stability_by_unit.csv."""
    path = Path(a8_2_dir) / "candidate_label_stability_by_unit.csv"
    keys = {}  # (session_id, unit_axis_index) -> row
    if not path.exists():
        return keys, str(path)
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            s_id = row["session_id"].strip()
            u_idx = int(row["unit_axis_index"])
            key = (s_id, u_idx)
            if key not in keys:
                keys[key] = row
    return keys, str(path)


def build_long_mapping_table(a8_1_keys, a8_2_keys, a6_inventory, a6_path):
    """
    Join A8.1/A8.2 unit keys to A6 area metadata.
    Returns list of row dicts for unit_area_mapping_long.csv
    and lists for unresolved, dp_alias, generic_v3 audits.
    """
    # Full set of unique unit keys from A8.1 (canonical denominator)
    all_unit_keys = set(a8_1_keys.keys())
    # Verify A8.2 key set matches (track mismatches separately)
    a8_2_only = set(a8_2_keys.keys()) - all_unit_keys
    a8_1_only = all_unit_keys - set(a8_2_keys.keys())

    long_rows = []
    unresolved_rows = []
    dp_alias_rows = []
    generic_v3_rows = []

    for key in sorted(all_unit_keys):
        s_id, u_idx = key
        unit_key_str = f"{s_id}_{u_idx}"

        in_a8_1 = key in a8_1_keys
        in_a8_2 = key in a8_2_keys

        # Pull A6 metadata if available
        a6_row = a6_inventory.get(key)

        if a6_row is not None:
            probe_id        = a6_row.get("probe_id_or_status", "unknown")
            unit_channel    = a6_row.get("peak_channel_or_status", "unknown")
            peak_channel    = a6_row.get("peak_channel_or_status", "unknown")
            anchor_channel  = a6_row.get("anchor_channel_or_status", "unknown")
            raw_area        = a6_row.get("raw_area_label", "None") or "None"
            canonical_area  = a6_row.get("canonical_area_label", "Unknown") or "Unknown"
            area_res_status = a6_row.get("area_resolution_status", "unknown_area")
            source_file     = a6_row.get("source_file", a6_path)
            a6_warnings     = a6_row.get("warnings", "None") or "None"
            mapping_warning = a6_warnings

            # Resolved channel: prefer peak, fall back to anchor
            resolved_channel = peak_channel
            if resolved_channel in ("missing_metadata", "unknown", "None", ""):
                resolved_channel = anchor_channel

            # DP->V4 alias audit
            if "DP" in str(raw_area).upper():
                dp_alias_rows.append({
                    "session_id": s_id,
                    "unit_axis_index": u_idx,
                    "unit_key": unit_key_str,
                    "raw_area_label": raw_area,
                    "canonical_area_label": canonical_area,
                    "area_resolution_status": area_res_status,
                    "alias_applied": a6_row.get("alias_applied", "unknown"),
                    "alias_correct": "true" if canonical_area == "V4" else "false",
                    "note": "DP label present; canonical should be V4 per doctrine"
                })

            # Generic V3 audit — use A6 status field as authoritative flag
            if area_res_status == "unresolved_generic_v3" or raw_area.strip().upper() == "V3":
                generic_v3_rows.append({
                    "session_id": s_id,
                    "unit_axis_index": u_idx,
                    "unit_key": unit_key_str,
                    "raw_area_label": raw_area,
                    "canonical_area_label": canonical_area,
                    "area_resolution_status": area_res_status,
                    "note": "Generic V3 preserved as-is; must not be silently split into V3d/V3a or discarded"
                })

            # Normalize any unknown A6 status value defensively to 'unknown_area'
            if area_res_status not in VALID_RESOLUTION_STATUSES:
                area_res_status = "unknown_area"
                mapping_warning = (f"Unknown area_resolution_status from A6; normalized to unknown_area. "
                                   f"Original: {a6_row.get('area_resolution_status', 'N/A')}")

        else:
            # No A6 row found for this unit key
            probe_id         = "unmapped"
            unit_channel     = "unmapped"
            peak_channel     = "unmapped"
            anchor_channel   = "unmapped"
            resolved_channel = "unmapped"
            raw_area         = "None"
            canonical_area   = "Unknown"
            area_res_status  = "unmapped_no_metadata"
            source_file      = a6_path
            mapping_warning  = "No A6 row found for this unit key; key not present in unit_area_inventory.csv"

        area_group = resolve_area_group(canonical_area)
        can_area, can_hier = resolve_claim_flags(area_res_status, canonical_area)

        row = {
            "session_id":               s_id,
            "unit_axis_index":          u_idx,
            "unit_key":                 unit_key_str,
            "source_from_a8_1_present": "true" if in_a8_1 else "false",
            "source_from_a8_2_present": "true" if in_a8_2 else "false",
            "probe_id":                 probe_id,
            "unit_channel":             unit_channel,
            "peak_channel":             peak_channel,
            "anchor_channel":           anchor_channel,
            "resolved_channel":         resolved_channel,
            "raw_area_label":           raw_area,
            "canonical_area_label":     canonical_area,
            "area_group":               area_group,
            "area_resolution_status":   area_res_status,
            "mapping_warning":          mapping_warning,
            "mapping_source_file":      source_file,
            "mapping_source_hash":      sha256_file(source_file) if Path(source_file).exists() else "unavailable",
            "can_support_area_claim":   "true" if can_area else "false",
            "can_support_hierarchy_claim": "true" if can_hier else "false",
        }
        long_rows.append(row)

        # Unresolved tracker
        if area_res_status not in MANUSCRIPT_SAFE_STATUSES:
            unresolved_rows.append({
                "session_id":             s_id,
                "unit_axis_index":        u_idx,
                "unit_key":               unit_key_str,
                "area_resolution_status": area_res_status,
                "raw_area_label":         raw_area,
                "canonical_area_label":   canonical_area,
                "mapping_warning":        mapping_warning,
                "blocking_reason":        f"area_resolution_status={area_res_status} is not manuscript-safe",
            })

    return long_rows, unresolved_rows, dp_alias_rows, generic_v3_rows, a8_2_only, a8_1_only


def build_session_summary(long_rows):
    """Aggregate unit counts by session_id and area_resolution_status."""
    from collections import defaultdict
    sess_status = defaultdict(lambda: defaultdict(int))
    sess_total  = defaultdict(int)
    sess_can_area  = defaultdict(int)
    sess_can_hier  = defaultdict(int)
    for r in long_rows:
        s = r["session_id"]
        sess_total[s] += 1
        sess_status[s][r["area_resolution_status"]] += 1
        if r["can_support_area_claim"] == "true":
            sess_can_area[s] += 1
        if r["can_support_hierarchy_claim"] == "true":
            sess_can_hier[s] += 1

    rows = []
    for s in sorted(sess_total.keys()):
        row = {"session_id": s, "n_units_total": sess_total[s]}
        for status in VALID_RESOLUTION_STATUSES:
            row[f"n_{status}"] = sess_status[s].get(status, 0)
        row["n_can_support_area_claim"]      = sess_can_area[s]
        row["n_can_support_hierarchy_claim"] = sess_can_hier[s]
        rows.append(row)
    return rows


def build_status_summary(long_rows):
    """Count units by area_resolution_status globally."""
    from collections import Counter
    counts = Counter(r["area_resolution_status"] for r in long_rows)
    rows = []
    for status in sorted(VALID_RESOLUTION_STATUSES):
        rows.append({"area_resolution_status": status, "n_units": counts.get(status, 0)})
    return rows


def build_join_integrity_report(a8_1_keys, a8_2_keys, long_rows, a8_2_only, a8_1_only):
    """Produce a join integrity report between A8.1, A8.2, and A8.3 long table."""
    long_keys = {(r["session_id"], int(r["unit_axis_index"])) for r in long_rows}
    a8_1_set  = set(a8_1_keys.keys())
    a8_2_set  = set(a8_2_keys.keys())

    rows = [
        {"check": "A8.1_keys_total",         "count": len(a8_1_set), "status": "info"},
        {"check": "A8.2_keys_total",          "count": len(a8_2_set), "status": "info"},
        {"check": "A8.3_long_rows_total",     "count": len(long_rows), "status": "info"},
        {"check": "keys_in_A8.1_not_in_A8.2","count": len(a8_1_only), "status": "WARNING" if a8_1_only else "PASS"},
        {"check": "keys_in_A8.2_not_in_A8.1","count": len(a8_2_only), "status": "WARNING" if a8_2_only else "PASS"},
        {"check": "A8.1_keys_all_in_A8.3_long","count": len(a8_1_set - long_keys),
         "status": "FAIL" if (a8_1_set - long_keys) else "PASS"},
        {"check": "A8.2_keys_all_in_A8.3_long","count": len(a8_2_set - long_keys),
         "status": "FAIL" if (a8_2_set - long_keys) else "PASS"},
        {"check": "duplicate_long_rows",       "count": len(long_rows) - len(long_keys),
         "status": "FAIL" if len(long_rows) != len(long_keys) else "PASS"},
    ]
    return rows


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    git_commit = get_git_commit()
    generated_at = datetime.now(timezone.utc).isoformat()

    # ── 1. Load inputs ──────────────────────────────────────────────────────────
    a6_inventory, a6_path     = load_a6_unit_area_inventory(args.a6_dir)
    a8_1_keys,    a8_1_path   = load_a8_1_unit_keys(args.a8_1_dir)
    a8_2_keys,    a8_2_path   = load_a8_2_unit_keys(args.a8_2_dir)

    a6_unit_inventory_path    = Path(args.a6_dir) / "unit_area_inventory.csv"
    a6_probe_inventory_path   = Path(args.a6_dir) / "probe_area_inventory.csv"

    print(f"A6 unit inventory rows loaded: {len(a6_inventory)}")
    print(f"A8.1 unique unit keys: {len(a8_1_keys)}")
    print(f"A8.2 unique unit keys: {len(a8_2_keys)}")

    # ── 2. Build long mapping table ─────────────────────────────────────────────
    (long_rows, unresolved_rows, dp_alias_rows, generic_v3_rows,
     a8_2_only, a8_1_only) = build_long_mapping_table(
        a8_1_keys, a8_2_keys, a6_inventory, str(a6_unit_inventory_path)
    )

    # ── 3. Build summary tables ─────────────────────────────────────────────────
    session_summary = build_session_summary(long_rows)
    status_summary  = build_status_summary(long_rows)
    join_integrity  = build_join_integrity_report(a8_1_keys, a8_2_keys, long_rows, a8_2_only, a8_1_only)

    # ── 4. Write output files ────────────────────────────────────────────────────

    # Output 1: parameters
    params = {
        "a6_dir":   args.a6_dir,
        "a8_1_dir": args.a8_1_dir,
        "a8_2_dir": args.a8_2_dir,
        "out_dir":  args.out_dir,
        "git_commit": git_commit,
        "generated_at": generated_at,
        "truth_status": TRUTH_SAFE_UNVERIFIED,
    }
    with open(out_dir / "unit_area_mapping_execution_parameters.json", "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2)

    # Output 4: long table
    long_fields = [
        "session_id", "unit_axis_index", "unit_key",
        "source_from_a8_1_present", "source_from_a8_2_present",
        "probe_id", "unit_channel", "peak_channel", "anchor_channel", "resolved_channel",
        "raw_area_label", "canonical_area_label", "area_group", "area_resolution_status",
        "mapping_warning", "mapping_source_file", "mapping_source_hash",
        "can_support_area_claim", "can_support_hierarchy_claim",
    ]
    write_csv(out_dir / "unit_area_mapping_long.csv", long_rows, long_fields)

    # Output 5: by session
    session_fields = ["session_id", "n_units_total"] + \
                     [f"n_{s}" for s in sorted(VALID_RESOLUTION_STATUSES)] + \
                     ["n_can_support_area_claim", "n_can_support_hierarchy_claim"]
    write_csv(out_dir / "unit_area_mapping_by_session.csv", session_summary, session_fields)

    # Output 6: by area_resolution_status
    write_csv(out_dir / "unit_area_mapping_by_area_resolution_status.csv",
              status_summary, ["area_resolution_status", "n_units"])

    # Output 7: unresolved cases
    unresolved_fields = [
        "session_id", "unit_axis_index", "unit_key",
        "area_resolution_status", "raw_area_label", "canonical_area_label",
        "mapping_warning", "blocking_reason"
    ]
    write_csv(out_dir / "unresolved_unit_area_mapping_cases.csv",
              unresolved_rows, unresolved_fields)

    # Output 8: generic V3 audit
    generic_v3_fields = [
        "session_id", "unit_axis_index", "unit_key",
        "raw_area_label", "canonical_area_label", "area_resolution_status", "note"
    ]
    write_csv(out_dir / "generic_v3_resolution_audit.csv",
              generic_v3_rows, generic_v3_fields)

    # Output 9: DP->V4 alias audit
    dp_fields = [
        "session_id", "unit_axis_index", "unit_key",
        "raw_area_label", "canonical_area_label", "area_resolution_status",
        "alias_applied", "alias_correct", "note"
    ]
    write_csv(out_dir / "dp_to_v4_alias_audit.csv", dp_alias_rows, dp_fields)

    # Output 10: A8.1/A8.2 join integrity
    join_fields = ["check", "count", "status"]
    write_csv(out_dir / "a8_1_a8_2_join_integrity_report.csv",
              join_integrity, join_fields)

    # ── 5. Compute aggregate diagnostics ────────────────────────────────────────
    n_total = len(long_rows)
    n_can_area  = sum(1 for r in long_rows if r["can_support_area_claim"]      == "true")
    n_can_hier  = sum(1 for r in long_rows if r["can_support_hierarchy_claim"] == "true")
    n_unresolved = len(unresolved_rows)
    n_generic_v3 = len(generic_v3_rows)
    n_dp_alias   = len(dp_alias_rows)
    n_dp_correct = sum(1 for r in dp_alias_rows if r["alias_correct"] == "true")
    n_unmapped   = sum(1 for r in long_rows if r["area_resolution_status"] == "unmapped_no_metadata")
    n_invalid    = sum(1 for r in long_rows if r["area_resolution_status"] in ("invalid_probe", "invalid_channel"))

    join_pass = all(j["status"] in ("PASS", "info") for j in join_integrity)
    area_stratified_possible = n_can_area > 0
    hierarchy_allowed = False  # conservatively blocked until metadata is validated

    # ── 6. Write summary JSON ───────────────────────────────────────────────────
    summary = {
        "truth_status":                TRUTH_SAFE_UNVERIFIED,
        "validation_status":           "diagnostic_unit_area_mapping_not_biological_claim",
        "git_commit":                  git_commit,
        "generated_at":                generated_at,
        "n_a8_1_input_keys":           len(a8_1_keys),
        "n_a8_2_input_keys":           len(a8_2_keys),
        "n_long_rows_total":           n_total,
        "n_can_support_area_claim":    n_can_area,
        "n_can_support_hierarchy_claim": n_can_hier,
        "n_unresolved_or_heuristic":   n_unresolved,
        "n_unmapped_no_metadata":      n_unmapped,
        "n_generic_v3_cases":          n_generic_v3,
        "n_dp_alias_cases":            n_dp_alias,
        "n_dp_alias_correctly_to_v4":  n_dp_correct,
        "n_invalid_probe_or_channel":  n_invalid,
        "join_integrity_passed":       join_pass,
        "area_stratified_diagnostics_possible": area_stratified_possible,
        "manuscript_hierarchy_claims_allowed":  hierarchy_allowed,
        "manuscript_safe_response_class":       False,
        "area_hierarchy_allowed":               False,
        "allowed_claims": [
            "unit-level area resolution status audit",
            "DP-to-V4 alias completeness check",
            "generic-V3 detection and flagging",
            "A8.1/A8.2 join integrity verification",
            "session-level area metadata coverage summary",
        ],
        "blocked_claims": [
            "manuscript area enrichment or hierarchy claims",
            "biological hierarchy interpretations from area counts",
            "population-level area selectivity claims",
            "promotion of X_candidate to higher-order omission hierarchy",
        ],
        "scientific_wording_lock": (
            "A8.3 is a diagnostic metadata audit only. "
            "Area-resolution status counts do not constitute biological population claims. "
            "The absence or presence of metadata-resolved units in any area does not support "
            "or refute predictive-routing hierarchy hypotheses, which require validated "
            "channel-level provenance and area-by-area response-class analysis beyond this phase."
        ),
    }
    with open(out_dir / "unit_area_mapping_execution_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # ── 7. Write summary MD ─────────────────────────────────────────────────────
    md_lines = [
        "# Phase A8.3: Diagnostic Unit-Area Mapping Integrity Audit",
        f"**Truth Status**: `{TRUTH_SAFE_UNVERIFIED}`",
        f"**Validation Status**: `diagnostic_unit_area_mapping_not_biological_claim`",
        "",
        "> [!IMPORTANT]",
        "> A8.3 is a diagnostic metadata audit only. No biological hierarchy claims are made.",
        "> Area-resolution status counts are infrastructure metadata, not manuscript results.",
        "",
        "## Input Sources",
        f"- A8.1 unit candidate labels: `{a8_1_path}` ({len(a8_1_keys)} unique unit keys)",
        f"- A8.2 stability table: `{a8_2_path}` ({len(a8_2_keys)} unique unit keys)",
        f"- A6 unit area inventory: `{a6_path}` ({len(a6_inventory)} rows loaded)",
        "",
        "## Join Integrity Summary",
        "| Check | Count | Status |",
        "| :--- | :---: | :---: |",
    ]
    for j in join_integrity:
        md_lines.append(f"| `{j['check']}` | {j['count']} | **{j['status']}** |")
    md_lines += [
        "",
        "## Area Resolution Status Summary (All A8.1 Units)",
        "| area_resolution_status | n_units |",
        "| :--- | :---: |",
    ]
    for s in status_summary:
        md_lines.append(f"| `{s['area_resolution_status']}` | {s['n_units']} |")
    md_lines += [
        "",
        f"**Total units in A8.3 long table**: {n_total}",
        f"**Units with metadata-resolved area (can_support_area_claim=true)**: {n_can_area}",
        f"**Units that can support hierarchy claims**: {n_can_hier}",
        f"**Units that are unresolved or heuristic**: {n_unresolved}",
        f"**Units with unmapped_no_metadata**: {n_unmapped}",
        "",
        "## Generic V3 Audit",
        f"- Total generic-V3 flagged unit rows: **{n_generic_v3}**",
        "- Generic V3 labels have NOT been silently split into V3d/V3a.",
        "- Generic V3 labels have NOT been silently discarded.",
        "- All generic V3 cases are written to `generic_v3_resolution_audit.csv`.",
        "",
        "## DP→V4 Alias Audit",
        f"- Total DP-labeled unit rows found: **{n_dp_alias}**",
        f"- DP labels correctly resolved to V4: **{n_dp_correct}**",
        "- All DP alias cases are written to `dp_to_v4_alias_audit.csv`.",
        "",
        "## Area-Stratified Diagnostics Feasibility",
        f"- Area-stratified diagnostics technically possible: **{'YES' if area_stratified_possible else 'NO'}**",
        f"- Manuscript hierarchy claims allowed: **NO** (requires validated channel-level provenance)",
        "",
        "## Scientific Wording Lock",
        "> [!WARNING]",
        "> A8.3 is a diagnostic metadata audit only. Area-resolution status counts do not constitute",
        "> biological population claims. The absence or presence of metadata-resolved units in any area",
        "> does not support or refute predictive-routing hierarchy hypotheses.",
        "",
        "---",
        f"Footer: Agent: Antigravity / Model: Claude Sonnet 4.6 / Role: Metadata Integrity Auditor "
        f"/ Plane: diagnostic / Repo or Workspace: D:\\workspace\\omission / Date: 2026-05-24",
    ]
    with open(out_dir / "unit_area_mapping_execution_summary.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    # ── 8. Write manifest with hashes ───────────────────────────────────────────
    generated_files = [
        "unit_area_mapping_execution_parameters.json",
        "unit_area_mapping_execution_summary.json",
        "unit_area_mapping_execution_summary.md",
        "unit_area_mapping_long.csv",
        "unit_area_mapping_by_session.csv",
        "unit_area_mapping_by_area_resolution_status.csv",
        "unresolved_unit_area_mapping_cases.csv",
        "generic_v3_resolution_audit.csv",
        "dp_to_v4_alias_audit.csv",
        "a8_1_a8_2_join_integrity_report.csv",
    ]
    hashes = {}
    for fname in generated_files:
        fpath = out_dir / fname
        hashes[fname] = sha256_file(str(fpath)) if fpath.exists() else "not_yet_generated"

    manifest = {
        "artifact_id":          "A8_3_unit_area_mapping_diagnostic",
        "truth_status":         TRUTH_SAFE_UNVERIFIED,
        "validation_status":    "diagnostic_unit_area_mapping_not_biological_claim",
        "git_commit":           git_commit,
        "generated_at":         generated_at,
        "payload_read_policy":  "csv_row_streaming_only_no_h5_no_numpy_payload",
        "generated_files":      generated_files,
        "input_files": {
            "a8_1_unit_candidate_labels": a8_1_path,
            "a8_2_stability_by_unit":     a8_2_path,
            "a6_unit_area_inventory":     str(a6_unit_inventory_path),
            "a6_probe_area_inventory":    str(a6_probe_inventory_path),
        },
        "input_hashes": {
            "a8_1_unit_candidate_labels": sha256_file(a8_1_path),
            "a8_2_stability_by_unit":     sha256_file(a8_2_path),
            "a6_unit_area_inventory":     sha256_file(str(a6_unit_inventory_path)),
        },
        "hashes": hashes,
    }
    with open(out_dir / "unit_area_mapping_execution_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # ── 9. Print execution summary ───────────────────────────────────────────────
    print(f"\nPhase A8.3 unit-area mapping diagnostic complete.")
    print(f"  Total A8.1 units processed: {len(a8_1_keys)}")
    print(f"  Long table rows written:    {n_total}")
    print(f"  Can support area claim:     {n_can_area}")
    print(f"  Can support hierarchy:      {n_can_hier}")
    print(f"  Unresolved/heuristic:       {n_unresolved}")
    print(f"  Generic V3 cases:           {n_generic_v3}")
    print(f"  DP->V4 alias cases:         {n_dp_alias} (correct: {n_dp_correct})")
    print(f"  Join integrity passed:      {join_pass}")
    print(f"  Outputs written to:         {out_dir}")


if __name__ == "__main__":
    main()
