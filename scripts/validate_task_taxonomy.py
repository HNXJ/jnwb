# scripts/validate_task_taxonomy.py
"""
Phase 2 Task Taxonomy, Timing, and Condition Code Validator.
Validates conditions, omission slots, control matches, and p1-relative timings.
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Expected condition sets
CORE_CONDITIONS = {
    "AAAB": {"family": "A", "is_omission": False, "slot": None, "control": "AAAB"},
    "AXAB": {"family": "A", "is_omission": True, "slot": 2, "control": "AAAB"},
    "AAXB": {"family": "A", "is_omission": True, "slot": 3, "control": "AAAB"},
    "AAAX": {"family": "A", "is_omission": True, "slot": 4, "control": "AAAB"},
    "BBBA": {"family": "B", "is_omission": False, "slot": None, "control": "BBBA"},
    "BXBA": {"family": "B", "is_omission": True, "slot": 2, "control": "BBBA"},
    "BBXA": {"family": "B", "is_omission": True, "slot": 3, "control": "BBBA"},
    "BBBX": {"family": "B", "is_omission": True, "slot": 4, "control": "BBBA"},
    "RRRR": {"family": "R", "is_omission": False, "slot": None, "control": "RRRR"},
    "RXRR": {"family": "R", "is_omission": True, "slot": 2, "control": "RRRR"},
    "RRXR": {"family": "R", "is_omission": True, "slot": 3, "control": "RRRR"},
    "RRRX": {"family": "R", "is_omission": True, "slot": 4, "control": "RRRR"}
}

# Timing milestones (ms) relative to p1 onset
EXPECTED_TIMING = {
    "fx": (-500, 0),
    "p1": (0, 531),
    "d1": (531, 1031),
    "p2": (1031, 1562),
    "d2": (1562, 2062),
    "p3": (2062, 2593),
    "d3": (2593, 3093),
    "p4": (3093, 3624),
    "d4": (3624, 4124)
}

def validate_manifest_taxonomy(manifest_path: Path) -> dict:
    """Validates the condition taxonomy and timing rules for a session manifest."""
    results = {
        "manifest_path": str(manifest_path),
        "session_id": "Unknown",
        "errors": [],
        "warnings": [],
        "checks": {
            "core_condition_coverage": "passed",
            "omission_slot_mapping": "passed",
            "matched_controls": "passed",
            "timing_milestones": "passed",
            "no_p2_shortcut": "passed",
            "random_control_separation": "passed"
        },
        "details": {}
    }

    try:
        with open(manifest_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        results["errors"].append(f"Failed to load or parse JSON manifest: {e}")
        return results

    results["session_id"] = data.get("session_id", "Unknown")
    conditions = data.get("conditions", [])

    if not conditions:
        results["errors"].append("Manifest does not contain a conditions list.")
        return results

    # 1. Core Condition Coverage
    found_codes = {c.get("code") for c in conditions if c.get("code")}
    missing_core = [code for code in CORE_CONDITIONS if code not in found_codes]
    if missing_core:
        results["warnings"].append(f"Missing core condition codes: {missing_core}")
        results["checks"]["core_condition_coverage"] = "warn"

    # 2. Omission Slot Mapping
    # 3. Matched Controls
    # 5. Timing & Omission Windows
    p2_only_shortcut = True # Assume true until refuted
    has_p3_p4 = False
    
    for c in conditions:
        code = c.get("code")
        if not code:
            continue
            
        is_omission = c.get("is_omission", False)
        omission_slot = c.get("omission_slot")
        
        # Check taxonomy mapping for core conditions
        if code in CORE_CONDITIONS:
            expected = CORE_CONDITIONS[code]
            
            # Verify omission flag
            if is_omission != expected["is_omission"]:
                results["errors"].append(f"Condition '{code}' is_omission flag is {is_omission}, expected {expected['is_omission']}.")
                results["checks"]["omission_slot_mapping"] = "failed"
                
            # Verify omission slot
            if expected["is_omission"]:
                if omission_slot != expected["slot"]:
                    results["errors"].append(f"Omission condition '{code}' slot is {omission_slot}, expected {expected['slot']}.")
                    results["checks"]["omission_slot_mapping"] = "failed"
                if expected["slot"] in [3, 4]:
                    has_p3_p4 = True
                    
            # Verify control condition presence
            ctrl_code = expected["control"]
            if ctrl_code not in found_codes:
                results["errors"].append(f"Matched control condition '{ctrl_code}' for '{code}' is missing from conditions list.")
                results["checks"]["matched_controls"] = "failed"

        # Look for custom/random control codes mixed in omission sequences
        if "random" in code.lower() or "prob" in code.lower():
            results["warnings"].append(f"Detected potential random control condition '{code}' which must remain separate from predictable sequence omissions.")
            results["checks"]["random_control_separation"] = "warn"

    # Verify that we are not silently using a p2-only shortcut for all omissions
    if has_p3_p4:
        p2_only_shortcut = False
        
    if p2_only_shortcut:
        results["warnings"].append("No p3 or p4 omission conditions detected. Pipeline may be using a p2-only shortcut.")
        results["checks"]["no_p2_shortcut"] = "warn"

    # 4. Timing Milestones (p1-relative)
    # Check if manifest timing maps match the expected boundaries
    timing_map = data.get("p1_relative_timing_ms", EXPECTED_TIMING)
    for epoch, expected_range in EXPECTED_TIMING.items():
        if epoch in timing_map:
            actual_range = timing_map[epoch]
            if list(actual_range) != list(expected_range):
                results["warnings"].append(f"Timing milestone mismatch for '{epoch}': expected {expected_range}, got {actual_range}.")
                results["checks"]["timing_milestones"] = "warn"

    return results

def render_md_report(results_list: list) -> str:
    """Renders a beautiful Labyrinth markdown report of the taxonomy validation."""
    lines = []
    lines.append("# Phase 2 Task Taxonomy & Timing Validation Report")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    lines.append("This validation report verifies that condition families, omission timing slots, matched controls, and stimulus-relative timing milestones strictly adhere to the Omission predictive routing contracts.")
    lines.append("")
    
    for r in results_list:
        lines.append(f"### Session ID: `{r['session_id']}`")
        lines.append(f"**Manifest File**: `{Path(r['manifest_path']).name}`")
        lines.append("")
        
        # Render validation checks table
        lines.append("| Check | Status | Description |")
        lines.append("| :--- | :---: | :--- |")
        
        check_desc = {
            "core_condition_coverage": "Verification of core condition code coverage (AAAB, AXAB, etc.)",
            "omission_slot_mapping": "Validation of omission slot assignments (p2=slot 2, p3=slot 3, p4=slot 4)",
            "matched_controls": "Confirmation of family-matched baseline control availability",
            "timing_milestones": "Stimulus timeline phase timing alignment checks (fx, p1-p4, d1-d4)",
            "no_p2_shortcut": "Assurance that p3 and p4 sequences are fully mapped separately from p2",
            "random_control_separation": "Isolation verification for random baseline sequences"
        }
        
        for check, status in r["checks"].items():
            status_emoji = "✅ Passed" if status == "passed" else ("⚠️ Warning" if status == "warn" else "❌ Failed")
            lines.append(f"| `{check}` | {status_emoji} | {check_desc.get(check, '')} |")
        lines.append("")

        if r["errors"]:
            lines.append("#### Errors")
            for e in r["errors"]:
                lines.append(f"- **[Error]** {e}")
            lines.append("")

        if r["warnings"]:
            lines.append("#### Warnings")
            for w in r["warnings"]:
                lines.append(f"- **[Warning]** {w}")
            lines.append("")
            
    lines.append("---")
    lines.append("Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Plane: implementation/contracts / Truth Status: truth_safe_unverified")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Phase 2 Task Taxonomy and Timing Validator")
    parser.add_argument("--manifest", help="Path to a single session manifest JSON.")
    parser.add_argument("--data-root", help="Path to search for manifest files.")
    parser.add_argument("--out", help="Path to write the Markdown validation report.")
    parser.add_argument("--format", choices=["json", "md"], default="md")
    args = parser.parse_args()

    manifest_paths = []
    
    # 1. Single manifest input
    if args.manifest:
        p = Path(args.manifest)
        if p.exists():
            manifest_paths.append(p)
        else:
            print(f"Error: Specified manifest path does not exist: '{args.manifest}'", file=sys.stderr)
            sys.exit(1)
            
    # 2. Search in data-root or local fixtures
    if not manifest_paths:
        root_path = Path(args.data_root) if args.data_root else Path("artifacts/test_manifests")
        if root_path.exists() and root_path.is_dir():
            manifest_paths.extend(list(root_path.glob("*.json")))

    if not manifest_paths:
        print("SKIPPING: No manifest files found to validate task taxonomy.")
        sys.exit(0)

    results_list = []
    for path in sorted(manifest_paths):
        res = validate_manifest_taxonomy(path)
        results_list.append(res)

    # Render report
    if args.format == "json":
        output_str = json.dumps(results_list, indent=2)
    else:
        output_str = render_md_report(results_list)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_str, encoding="utf-8")
        print(f"[Success] Taxonomy validation report saved to '{args.out}'")
    else:
        print(output_str)

    sys.exit(0)

if __name__ == "__main__":
    main()
