#!/usr/bin/env python3
"""
Figure 5: Local Omission SPK Contrast
=====================================
Omission-relative local PSTH/contrast: omission vs matched full-control.

Status: SMOKE/PLANNED - Not fully executed (bounded scope per THETA policy)
"""

import datetime
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(r"D:/workspace/omission")
OUTPUT_ROOT = REPO_ROOT / "outputs/publication_figures/fig04_09_reconstruction/figure_05"

def get_git_info():
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
        return {"sha": sha, "branch": branch}
    except Exception as e:
        return {"sha": "unknown", "branch": "unknown"}

def main():
    print("=" * 70)
    print("FIGURE 5: Local Omission SPK Contrast")
    print("=" * 70)
    print("\nStatus: SMOKE/PLANNED")
    print("Scope: Omission-relative local PSTH contrast")
    print("\nThis figure requires:")
    print("  - AAAB condition (omission at P4)")
    print("  - RRRR or Flash control (full stimulus)")
    print("  - Aligned comparison [-200, 400]ms around omission")
    print("\nImplementation plan:")
    print("  1. Load event vectors for AAAB and RRRR from batch index")
    print("  2. Extract spike epochs for both conditions")
    print("  3. Compute omission vs control contrast per unit")
    print("  4. Aggregate by area and cell type")
    
    git_info = get_git_info()
    
    # Create outputs
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "arrays").mkdir(exist_ok=True)
    (OUTPUT_ROOT / "tables").mkdir(exist_ok=True)
    (OUTPUT_ROOT / "figures").mkdir(exist_ok=True)
    
    # Placeholder HTML
    html_content = f"""<!DOCTYPE html>
<html><head><link rel="stylesheet" href="../shared/style.css"></head><body>
<h1>Figure 5: Local Omission SPK Contrast</h1>
<p><strong>Status:</strong> <span class="status-pending">SMOKE/PLANNED</span></p>
<div class="claim-box">
Claim Status: truth_safe_unverified (computational scaffold)<br>
Signal: SPK local omission contrast<br>
Comparison: AAAB omission vs RRRR/Flash control
</div>
<h2>Configuration</h2>
<table>
<tr><th>Parameter</th><th>Value</th></tr>
<tr><td>Time base</td><td>omission_relative_ms [-200, 400]</td></tr>
<tr><td>Conditions</td><td>AAAB (omission), RRRR (control)</td></tr>
<tr><td>Contrast</td><td>Omission minus control firing rate</td></tr>
</table>
<div class="warning-box">
This figure is planned but not yet executed pending full Figure 4 completion.
</div>
<hr><p><small>Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()}</small></p>
</body></html>
"""
    html_path = OUTPUT_ROOT / "figures/fig05_local_omission_spk.html"
    html_path.write_text(html_content, encoding="utf-8")
    
    # Manifest
    manifest = {
        "figure_id": "figure_05",
        "figure_name": "Local Omission SPK Contrast",
        "repo_sha": git_info["sha"],
        "repo_branch": git_info["branch"],
        "signal_class": "SPK",
        "time_base": "omission_relative_ms",
        "time_window_ms": [-200, 400],
        "conditions": ["AAAB", "RRRR"],
        "validation_status": "SMOKE_PLANNED",
        "warnings": ["Not executed - implementation pending"],
        "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    manifest_path = OUTPUT_ROOT / "fig05_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\nOutputs created:")
    print(f"  HTML: {html_path}")
    print(f"  Manifest: {manifest_path}")
    print("\nFigure 5 complete (planned).")
    return manifest

if __name__ == "__main__":
    main()
    sys.exit(0)
