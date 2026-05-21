#!/usr/bin/env python3
# scripts/validate_data_source_index.py
"""
Guarded DataSourceIndex validator script.
Builds the index of available files without opening high-density neural array payloads.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.analysis.io.loader import DataLoader
from src.analysis.contracts.constants import TRUTH_SAFE_UNVERIFIED

def generate_report(results: Dict[str, Any], out_path: Optional[Path] = None):
    lines = []
    lines.append("# Data Source Index Contract Validation Report")
    lines.append(f"**Data Root**: `{results['data_root']}`")
    lines.append(f"**Total Records Discovered**: {results['total_records']}")
    lines.append(f"**Truth Status Enforced**: {TRUTH_SAFE_UNVERIFIED}")
    lines.append("")
    
    if results["records"]:
        lines.append("## Discovered Records")
        lines.append("| Path | Session ID | Signal Class | File Type | Role | Status | Readable |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for r in results["records"]:
            lines.append(
                f"| `{r['path']}` | `{r['session_id']}` | `{r['signal_class']}` | "
                f"`{r['file_type']}` | `{r['role']}` | `{r['source_status']}` | `{r['readable_for_phase2']}` |"
            )
        lines.append("")

    if results["errors"]:
        lines.append("## Global Errors")
        for err in results["errors"]:
            lines.append(f"- [ERROR] {err}")
        lines.append("")

    if results["warnings"]:
        lines.append("## Global Warnings")
        for warn in results["warnings"]:
            lines.append(f"- [WARNING] {warn}")
        lines.append("")

    report_content = "\n".join(lines)
    print(report_content)
    
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report_content)
        print(f"\n[success] Report saved to {out_path}")

def main():
    parser = argparse.ArgumentParser(description="Guarded DataSourceIndex validator script")
    parser.add_argument("--data-root", help="Path to raw/derived data root directory")
    parser.add_argument("--session", help="Session ID to validate specifically")
    parser.add_argument("--out", help="Optional report file path to save validation output")
    
    args = parser.parse_args()
    
    data_root = args.data_root or os.environ.get("OMISSION_DATA_ROOT")
    session_id = args.session
    out_path = Path(args.out) if args.out else None
    
    # 1. Skip check
    if not data_root:
        print("Neither --data-root nor OMISSION_DATA_ROOT is set.")
        print("SKIPPING: DataSourceIndex discovery validation skipped safely.")
        sys.exit(0)
        
    d_root = Path(data_root)
    if not d_root.exists():
        print(f"Warning: Data root path '{d_root}' does not exist. Skipping scan.")
        sys.exit(0)
        
    # 2. Build DataSourceIndex using DataLoader
    loader = DataLoader()
    index = loader.discover_data_sources(d_root, session_id=session_id)
    
    errors = index.validate()
    
    results = {
        "data_root": str(d_root),
        "total_records": len(index.records),
        "records": [r.to_dict() if hasattr(r, 'to_dict') else r.__dict__ for r in index.records],
        "errors": errors + index.errors,
        "warnings": index.warnings
    }
    
    # 3. Print JSON summary
    print("\n--- JSON Summary ---")
    print(json.dumps(results, indent=2))
    print("--------------------\n")
    
    # 4. Write report if out path is passed
    if out_path:
        generate_report(results, out_path)
        
    if results["errors"]:
        sys.exit(1)
        
    sys.exit(0)

if __name__ == "__main__":
    main()
