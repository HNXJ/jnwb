#!/usr/bin/env python3
"""
Figure 6: R-Family SPK Controls
================================
Random-control omission timing SPK response figure.

Status: SMOKE/PLANNED - Not fully executed
"""

import datetime
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(r"D:/workspace/omission")
OUTPUT_ROOT = REPO_ROOT / "outputs/publication_figures/fig04_09_reconstruction/figure_06"

def get_git_info():
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
        return {"sha": sha, "branch": branch}
    except Exception:
        return {"sha": "unknown", "branch": "unknown"}

def main():
    print("=" * 70)
    print("FIGURE 6: R-Family SPK Controls")
    print("=" * 70)
    print("\nStatus: SMOKE/PLANNED")
    print("Scope: R-family control conditions (RRRR, RXRR, RRXR, RRRX)")
    print("\nRule: Do not pool R-family with structured sequence conditions")
    
    git_info = get_git_info()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "arrays").mkdir(exist_ok=True)
    (OUTPUT_ROOT / "tables").mkdir(exist_ok=True)
    (OUTPUT_ROOT / "figures").mkdir(exist_ok=True)
    
    html_content = f"""<!DOCTYPE html>
<html><head><link rel="stylesheet" href="../shared/style.css"></head><body>
<h1>Figure 6: R-Family SPK Controls</h1>
<p><strong>Status:</strong> <span class="status-pending">SMOKE/PLANNED</span></p>
<div class="claim-box">
R-family controls for timing and expectation effects.<br>
Conditions: RRRR, RXRR, RRXR, RRRX
</div>
<div class="warning-box">
Important: R-family is analyzed separately from structured sequences.<br>
No pooling with AAAB/AXAB/AAXB/AAAX.
</div>
<hr><p><small>Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()}</small></p>
</body></html>
"""
    html_path = OUTPUT_ROOT / "figures/fig06_r_family_spk.html"
    html_path.write_text(html_content, encoding="utf-8")
    
    manifest = {
        "figure_id": "figure_06",
        "figure_name": "R-Family SPK Controls",
        "repo_sha": git_info["sha"],
        "conditions": ["RRRR", "RXRR", "RRXR", "RRRX"],
        "validation_status": "SMOKE_PLANNED",
        "warnings": ["Not executed - R-family separate from structured sequences"],
        "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    manifest_path = OUTPUT_ROOT / "fig06_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\nOutputs: {html_path}, {manifest_path}")
    return manifest

if __name__ == "__main__":
    main()
    sys.exit(0)
