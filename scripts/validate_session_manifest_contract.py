#!/usr/bin/env python3
# scripts/validate_session_manifest_contract.py
"""
Bounded Real-Data Session Manifest Validator (Phase 2D)
Guarded by OMISSION_DATA_ROOT or --data-root.
Strictly read-only, no secret exposure, no biological claims upgrade.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.analysis.contracts.session_manifest import SessionManifest
from src.analysis.contracts.constants import TRUTH_SAFE_UNVERIFIED

def generate_report(results: Dict[str, Any], out_path: Optional[Path] = None):
    lines = []
    lines.append("# Session Manifest Contract Validation Report")
    lines.append(f"**Status**: {'PASS' if results['success'] else 'FAIL'}")
    lines.append(f"**Total Manifests Checked**: {results['total_checked']}")
    lines.append(f"**Truth Status Enforced**: {TRUTH_SAFE_UNVERIFIED}")
    lines.append("")
    
    if results["manifests"]:
        lines.append("## Checked Manifests")
        for m in results["manifests"]:
            lines.append(f"### Session `{m['session_id']}`")
            lines.append(f"- **Path**: `{m['path']}`")
            lines.append(f"- **Is Fixture**: `{m['is_fixture']}`")
            lines.append(f"- **Real Metadata Derived**: `{m['real_metadata_derived']}`")
            lines.append(f"- **Valid**: {'Yes' if m['valid'] else 'No'}")
            
            if m["errors"]:
                lines.append("  - **Errors**:")
                for err in m["errors"]:
                    lines.append(f"    - [ERROR] {err}")
            if m["warnings"]:
                lines.append("  - **Warnings**:")
                for warn in m["warnings"]:
                    lines.append(f"    - [WARNING] {warn}")
            lines.append("")
            
    if results["errors"]:
        lines.append("## Global Errors")
        for err in results["errors"]:
            lines.append(f"- {err}")
        lines.append("")

    report_content = "\n".join(lines)
    print(report_content)
    
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report_content)
        print(f"\n[success] Report saved to {out_path}")

def validate_single_manifest_file(manifest_path: Path, expect_real: bool = False) -> Dict[str, Any]:
    res = {
        "path": str(manifest_path),
        "session_id": "unknown",
        "valid": False,
        "is_fixture": False,
        "real_metadata_derived": False,
        "errors": [],
        "warnings": []
    }
    
    try:
        with open(manifest_path, "r") as f:
            d = json.load(f)
    except Exception as e:
        res["errors"].append(f"Could not load or parse JSON: {e}")
        return res
        
    if "session_id" not in d:
        res["errors"].append("JSON missing required 'session_id' key.")
        return res
        
    res["session_id"] = d["session_id"]
    
    try:
        manifest = SessionManifest.from_dict(d)
        errors = manifest.validate()
        res["is_fixture"] = manifest.is_fixture()
        res["real_metadata_derived"] = manifest.is_real_metadata_derived()
        res["errors"].extend(errors)
        res["warnings"].extend(manifest.warnings)
        
        # Guard: check if fixture manifest is placed under real data root
        if expect_real and manifest.is_fixture():
            res["errors"].append("Fixture/Synthetic manifest found in real data directory.")
            
        # Contract: check DP -> V4 normalization mapping
        for m in manifest.area_mappings:
            if m.area in ["DP", "DP (V4)"]:
                res["errors"].append(f"Area {m.area} is not normalized to V4 in area_mappings.")
        for area in manifest.channel_counts_by_area.keys():
            if area in ["DP", "DP (V4)"]:
                res["errors"].append(f"Area {area} is not normalized to V4 in channel_counts_by_area.")
                
        # Check for unresolved generic V3
        has_v3 = False
        for m in manifest.area_mappings:
            if m.area == "V3" and m.resolution_status != "resolved":
                has_v3 = True
        for area in manifest.channel_counts_by_area.keys():
            if area == "V3" and manifest.area_resolution_status.get(area) != "resolved":
                has_v3 = True
        if has_v3:
            msg = "Area V3 is UNRESOLVED generic V3."
            if msg not in res["warnings"]:
                res["warnings"].append(msg)
                
        if not res["errors"]:
            res["valid"] = True
            
    except Exception as e:
        res["errors"].append(f"Dataclass reconstruction failed: {e}")
        
    return res

def main():
    parser = argparse.ArgumentParser(description="Bounded Real-Data Session Manifest Validator")
    parser.add_argument("--data-root", help="Path to raw/derived data root directory")
    parser.add_argument("--session", help="Session ID to validate specifically")
    parser.add_argument("--manifest", help="Direct path to session manifest JSON to validate")
    parser.add_argument("--out", help="Optional report file path to save validation output")
    
    args = parser.parse_args()
    
    data_root = args.data_root or os.environ.get("OMISSION_DATA_ROOT")
    manifest_path = args.manifest
    session_id = args.session
    out_path = Path(args.out) if args.out else None
    
    # 1. Skip check
    if not data_root and not manifest_path:
        print("No --manifest provided, and neither --data-root nor OMISSION_DATA_ROOT is set.")
        print("SKIPPING: Bounded manifest validation skipped safely.")
        sys.exit(0)
        
    results = {
        "success": True,
        "total_checked": 0,
        "manifests": [],
        "errors": []
    }
    
    # 2. Direct manifest validation
    if manifest_path:
        m_path = Path(manifest_path)
        if not m_path.exists():
            print(f"Error: Manifest file '{m_path}' does not exist.", file=sys.stderr)
            sys.exit(1)
        res = validate_single_manifest_file(m_path, expect_real=False)
        results["total_checked"] += 1
        results["manifests"].append(res)
        if not res["valid"]:
            results["success"] = False
            
    # 3. Data root scanning (read-only, config-like files only, no binary matrices)
    if data_root:
        d_root = Path(data_root)
        if not d_root.exists():
            print(f"Warning: Data root path '{d_root}' does not exist. Skipping scan.")
        else:
            # Look for JSON files. To remain bounded and fast, search manifests/ folder or files containing "manifest"
            candidate_files = []
            
            # Check manifests subdirectory first (canonical placement)
            manifests_dir = d_root / "manifests"
            if manifests_dir.exists() and manifests_dir.is_dir():
                candidate_files.extend(list(manifests_dir.glob("*.json")))
            else:
                # Fallback: glob files containing 'manifest' in name under the root (limit depth to 2 to avoid scanning massive subtrees)
                for p in d_root.glob("*.json"):
                    if "manifest" in p.name.lower():
                        candidate_files.append(p)
                for p in d_root.glob("*/*.json"):
                    if "manifest" in p.name.lower():
                        candidate_files.append(p)
            
            # Filter by session if specified
            if session_id:
                candidate_files = [p for p in candidate_files if session_id in p.name]
                
            for path in sorted(set(candidate_files)):
                res = validate_single_manifest_file(path, expect_real=True)
                results["total_checked"] += 1
                results["manifests"].append(res)
                if not res["valid"]:
                    results["success"] = False
                    
    # Generate report
    generate_report(results, out_path)
    
    if not results["success"]:
        # Return nonzero only for explicit contract failures when a manifest was intentionally provided
        sys.exit(1)
    
    sys.exit(0)

if __name__ == "__main__":
    main()
