#!/usr/bin/env python3
"""
Figure 9: H Harmony from Y
===========================
Cross-area spectral-state similarity/harmony derived from Y.

Status: SMOKE/PLANNED (depends on Figure 8 Y tensor)
"""

import datetime
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(r"D:/workspace/omission")
OUTPUT_ROOT = REPO_ROOT / "outputs/publication_figures/fig04_09_reconstruction/figure_09"

def get_git_info():
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
        return {"sha": sha, "branch": branch}
    except Exception:
        return {"sha": "unknown", "branch": "unknown"}

def main():
    print("=" * 70)
    print("FIGURE 9: H Harmony from Y")
    print("=" * 70)
    print("\nStatus: SMOKE/PLANNED")
    print("\nH-Harmony: H(B, P, L, A, A)")
    print("  Cross-area spectral-state similarity derived from Y-tensor")
    print("\nConstraints:")
    print("  - H is similarity/correlation only (NOT directionality)")
    print("  - No causality claims without further validation")
    print("  - Beta/gamma harmony matrices as primary visualization")
    
    git_info = get_git_info()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "arrays").mkdir(exist_ok=True)
    (OUTPUT_ROOT / "tables").mkdir(exist_ok=True)
    (OUTPUT_ROOT / "figures").mkdir(exist_ok=True)
    
    # Prototype H tensor dimensions
    BANDS = ["beta", "gamma"]  # Primary bands for harmony
    EPOCHS = ["p1_relative", "omission_local"]
    LAYERS = ["superficial", "deep", "unresolved"]
    AREAS = ["V1", "V2", "V3d", "V3a", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"]
    
    H_shape = (len(BANDS), len(EPOCHS), len(LAYERS), len(AREAS), len(AREAS))
    print(f"\nPrototype H-harmony shape: {H_shape}")
    print(f"  B={len(BANDS)}, P={len(EPOCHS)}, L={len(LAYERS)}, A={len(AREAS)}, A={len(AREAS)}")
    
    # Symmetric A x A for each B, P, L
    H_prototype = np.zeros(H_shape)
    
    html_content = f"""<!DOCTYPE html>
<html><head><link rel="stylesheet" href="../shared/style.css"></head><body>
<h1>Figure 9: H Harmony from Y</h1>
<p><strong>Status:</strong> <span class="status-pending">SMOKE/PLANNED</span></p>
<div class="claim-box">
H-Harmony: H(B, P, L, A, A)<br>
Cross-area spectral-state similarity from Y-tensor
</div>
<h2>Canonical Dimensions</h2>
<table>
<tr><th>Axis</th><th>Size</th><th>Description</th></tr>
<tr><td>B (bands)</td><td>{len(BANDS)}</td><td>beta, gamma (harmony-relevant)</td></tr>
<tr><td>P (epochs)</td><td>{len(EPOCHS)}</td><td>Temporal epochs</td></tr>
<tr><td>L (layers)</td><td>{len(LAYERS)}</td><td>Laminar position</td></tr>
<tr><td>A x A</td><td>{len(AREAS)}x{len(AREAS)}</td><td>Cross-area similarity (symmetric)</td></tr>
</table>
<div class="warning-box">
<strong>Critical constraints:</strong><br>
- H is similarity/correlation only<br>
- NO directionality proven<br>
- NO causality proven<br>
- SFC/PPC relegated to optional supplement<br>
- If Y is smoke/prototype, H is METHOD_PENDING
</div>
<hr><p><small>Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()}</small></p>
</body></html>
"""
    html_path = OUTPUT_ROOT / "figures/fig09_h_harmony.html"
    html_path.write_text(html_content, encoding="utf-8")
    
    # Save prototype
    np.savez(OUTPUT_ROOT / "arrays/fig09_H_harmony_prototype.npz",
             H_prototype=H_prototype,
             bands=BANDS,
             epochs=EPOCHS,
             layers=LAYERS,
             areas=AREAS,
             H_shape=H_shape)
    
    manifest = {
        "figure_id": "figure_09",
        "figure_name": "H Harmony from Y",
        "repo_sha": git_info["sha"],
        "H_tensor_shape": list(H_shape),
        "bands": BANDS,
        "harmony_bands": ["beta", "gamma"],
        "epochs": EPOCHS,
        "layers": LAYERS,
        "areas": AREAS,
        "is_similarity": True,
        "directionality_proven": False,
        "causality_proven": False,
        "sfc_ppc_status": "optional_supplement_only",
        "validation_status": "SMOKE_PROTOTYPE",
        "warnings": [
            "Prototype only - zeros array",
            "Requires Figure 8 Y-tensor outputs",
            "H is correlation/similarity only",
            "No directionality or causality claims",
            "SFC/PPC is optional supplement"
        ],
        "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    manifest_path = OUTPUT_ROOT / "fig09_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\nOutputs created:")
    print(f"  HTML: {html_path}")
    print(f"  Manifest: {manifest_path}")
    print(f"\nFigure 9 prototype complete.")
    return manifest

if __name__ == "__main__":
    main()
    sys.exit(0)
