# scripts/scaffold_session_manifests.py
"""
Phase 2K Session Manifest Scaffolding and Validation Report CLI.
Scans metadata-like files to discover session structures without opening raw array payloads.
"""

import sys
import os
import argparse
import json
from pathlib import Path
from src.analysis.io.loader import DataLoader

def render_md_report(report) -> str:
    """Renders a beautiful Markdown report from a ManifestScaffoldReport."""
    lines = []
    lines.append("# Session Manifest Production Scaffold Validation Report")
    lines.append("")
    lines.append(f"**Data Root**: `{report.data_root}`")
    lines.append(f"**Skipped**: `{report.skipped}`")
    lines.append(f"**Truth Status**: `{report.truth_status}`")
    lines.append("")
    
    if report.warnings:
        lines.append("## Global Warnings")
        for w in report.warnings:
            lines.append(f"- **[Warning]** {w}")
        lines.append("")

    if report.errors:
        lines.append("## Global Errors")
        for e in report.errors:
            lines.append(f"- **[Error]** {e}")
        lines.append("")

    lines.append(f"## Discovered Session Candidates ({len(report.candidates)})")
    lines.append("")

    for c in report.candidates:
        lines.append(f"### Session ID: `{c.session_id}`")
        lines.append(f"- **Inferred Subject**: `{c.inferred_subject or 'Unknown'}`")
        lines.append(f"- **Inferred Recording Date**: `{c.inferred_recording_date or 'Unknown'}`")
        lines.append("- **Signal Availability**:")
        for sig, avail in c.signal_availability.items():
            lines.append(f"  - `{sig}`: {'**Available**' if avail else 'Unavailable'}")
            
        lines.append("- **Detected Fields**:")
        for field_name, detected in c.detected_fields.items():
            lines.append(f"  - `{field_name}`: {'Present' if detected else '**Missing**'}")

        lines.append("- **Source Files**:")
        if c.source_files:
            for sf in c.source_files:
                lines.append(f"  - `{sf}`")
        else:
            lines.append("  - *None discovered*")

        if c.warnings:
            lines.append("- **Warnings**:")
            for w in c.warnings:
                lines.append(f"  - **[Warning]** {w}")

        if c.errors:
            lines.append("- **Errors**:")
            for e in c.errors:
                lines.append(f"  - **[Error]** {e}")
        lines.append("")

    lines.append("---")
    lines.append("Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Plane: implementation/contracts / Truth Status: truth_safe_unverified")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Phase 2K Session Manifest Scaffolding Validator")
    parser.add_argument("--data-root", help="Path to data directory. Optional.")
    parser.add_argument("--session", help="Optional Session ID filter.")
    parser.add_argument("--out", help="Optional output report path.")
    parser.add_argument("--format", choices=["json", "md"], default="md", help="Output format (default: md).")
    args = parser.parse_args()

    # Load loader to check data root
    loader = DataLoader()
    data_root = args.data_root or os.environ.get("OMISSION_DATA_ROOT")

    if not data_root:
        print("SKIPPING: Data root directory not specified via --data-root or OMISSION_DATA_ROOT env variable.")
        report = loader.scaffold_session_manifests(data_root=None, session_id=args.session)
    else:
        root_path = Path(data_root)
        if not root_path.exists():
            print(f"SKIPPING: Specified data root does not exist: '{data_root}'")
            report = loader.scaffold_session_manifests(data_root=str(root_path), session_id=args.session)
        else:
            report = loader.scaffold_session_manifests(data_root=str(root_path), session_id=args.session)

    # Perform contract validation on the report
    val_errors = report.validate()
    if val_errors:
        print(f"[Contract Violation] Report validation failed: {val_errors}", file=sys.stderr)

    # Format the report output
    if args.format == "json":
        output_str = json.dumps(report.to_dict(), indent=2)
    else:
        output_str = render_md_report(report)

    # Write report if requested
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_str, encoding="utf-8")
        print(f"[Success] Scaffold report saved to '{args.out}'")
    else:
        print(output_str)

    sys.exit(0)

if __name__ == "__main__":
    main()
