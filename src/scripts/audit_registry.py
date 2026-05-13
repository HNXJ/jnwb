import os
import json
import re
from datetime import datetime
import sys
from pathlib import Path

# Ensure repo root is in path
ROOT = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(ROOT))

from src.analysis.registry import FigureRegistry

# Configuration
OUTPUTS_DIR = ROOT / "outputs" / "oglo-8figs"
ARTIFACTS_DIR = ROOT / "artifacts"
DASHBOARD_MANIFEST = ROOT / "dashboard" / "src" / "data" / "manifest.json" # Adjust if needed

class RegistryReconciler:
    def __init__(self):
        self.registry_data = FigureRegistry.get_all()
        self.mismatches = []
        self.report_lines = []

    def run_audit(self, check_only=False, no_meta=False):
        print(f"[RECONCILE] Starting Figure Registry Audit... (CheckOnly: {check_only}, NoMeta: {no_meta})")
        
        # 1. Collect actual directories
        src_dir = ROOT / "src"
        actual_f_folders = sorted([d.name for d in src_dir.iterdir() if d.is_dir() and d.name.startswith("f0")])
        
        # 2. Collect registry folders
        registry_folders = [os.path.basename(f['module']) for f in self.registry_data]
        
        # 3. Find Orphans (Folders not in registry)
        orphans = [f for f in actual_f_folders if f not in registry_folders]
        
        # 4. Find Missing (Registry entries without folders)
        missing = [f for f in registry_folders if not (src_dir / f).exists()]
        
        # 5. Check ID Multiplicity
        id_to_folders = {}
        for f in actual_f_folders:
            fid = f.split('_')[0]
            if fid not in id_to_folders: id_to_folders[fid] = []
            id_to_folders[fid].append(f)
        
        multiplicity = {fid: folders for fid, folders in id_to_folders.items() if len(folders) > 1}

        # Build Report
        timestamp_str = "2026-01-01 00:00" if no_meta else datetime.now().strftime('%Y-%m-%d %H:%M')
        iso_timestamp = "2026-01-01T00:00:00" if no_meta else datetime.now().isoformat()

        self.report_lines.append("# FigureRegistry Mismatch Report")
        self.report_lines.append(f"- Generated: {timestamp_str}")
        self.report_lines.append(f"- Total Registry Entries: {len(self.registry_data)}")
        self.report_lines.append(f"- Total f* Folders in src/: {len(actual_f_folders)}")
        self.report_lines.append("")
        
        self.report_lines.append("## Unregistered Folders (Orphans)")
        if orphans:
            for o in orphans: self.report_lines.append(f"- `{o}`")
        else:
            self.report_lines.append("None")
        self.report_lines.append("")
        
        self.report_lines.append("## Missing Folders (Registry points to non-existent src/)")
        if missing:
            for m in missing: self.report_lines.append(f"- `{m}`")
        else:
            self.report_lines.append("None")
        self.report_lines.append("")
        
        self.report_lines.append("## ID Multiplicity (Multiple folders for one ID)")
        if multiplicity:
            for fid, folders in multiplicity.items():
                self.report_lines.append(f"### {fid}")
                for f in folders:
                    is_primary = " (Primary)" if any(fig['id'] == fid and os.path.basename(fig['module']) == f for fig in self.registry_data) else ""
                    self.report_lines.append(f"- `{f}`{is_primary}")
        else:
            self.report_lines.append("None")
        self.report_lines.append("")

        if check_only:
            print(f"[RECONCILE] Audit complete (READ-ONLY).")
            if orphans or missing or multiplicity:
                print("  [!] Mismatches detected!")
            return

        # Save Artifacts
        if not ARTIFACTS_DIR.exists(): ARTIFACTS_DIR.mkdir()
        
        with open(ARTIFACTS_DIR / "registry_mismatch_report.md", "w") as f:
            f.write("\n".join(self.report_lines))
            
        audit_json = {
            "timestamp": iso_timestamp,
            "registry_count": len(self.registry_data),
            "folder_count": len(actual_f_folders),
            "orphans": orphans,
            "missing": missing,
            "multiplicity": multiplicity
        }
        
        with open(ARTIFACTS_DIR / "registry_audit.json", "w") as f:
            json.dump(audit_json, f, indent=2)
            
        print(f"[RECONCILE] Audit complete. Reports saved to artifacts/")
        print(f"  Orphans: {len(orphans)}")
        print(f"  Missing: {len(missing)}")
        print(f"  Multiplicity: {len(multiplicity)}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true", help="Run audit without writing reports")
    parser.add_argument("--no-meta", action="store_true", help="Use fixed timestamps for idempotency")
    args = parser.parse_args()

    reconciler = RegistryReconciler()
    reconciler.run_audit(check_only=args.check_only, no_meta=args.no_meta)
