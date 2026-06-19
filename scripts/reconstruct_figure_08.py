#!/usr/bin/env python3
"""
Figure 8: Y Tensor Band-Area-Layer Summary
===========================================
Y = D(B, A, P, L) tensor prototype.

Status: SMOKE/PLANNED (depends on Figure 7 band-power outputs)
"""

import datetime
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(r"D:/workspace/omission")
OUTPUT_ROOT = REPO_ROOT / "outputs/publication_figures/fig04_09_reconstruction/figure_08"

from src.analysis.io.utils import get_git_info

def main():
    print("=" * 70)
    print("FIGURE 8: Y Tensor Band-Area-Layer Summary")
    print("=" * 70)
    print("\nStatus: SMOKE/PLANNED")
    print("\nY-Tensor: Y = D(B, A, P, L)")
    print("  B = band (delta, theta, alpha, beta_L, beta_H, gamma_L, gamma_M, gamma_H)")
    print("  A = area (V1, V2, V3d, V3a, V4, MT, MST, TEO, FST, FEF, PFC)")
    print("  P = epoch (p1-relative or omission-local)")
    print("  L = layer (superficial_putative, deep_putative, unresolved)")
    print("\nD = band power / dB / omission-control contrast")
    
    git_info = get_git_info(cwd=REPO_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "arrays").mkdir(exist_ok=True)
    (OUTPUT_ROOT / "tables").mkdir(exist_ok=True)
    (OUTPUT_ROOT / "figures").mkdir(exist_ok=True)
    
    # Prototype Y tensor dimensions (without actual data)
    BANDS = ["delta", "theta", "alpha", "beta_L", "beta_H", "gamma_L", "gamma_M", "gamma_H"]
    AREAS = ["V1", "V2", "V3d", "V3a", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"]
    EPOCHS = ["p1_relative", "omission_local"]
    LAYERS = ["superficial_putative", "deep_putative", "unresolved"]
    
    # Create prototype shape
    Y_shape = (len(BANDS), len(AREAS), len(EPOCHS), len(LAYERS))
    print(f"\nPrototype Y tensor shape: {Y_shape}")
    print(f"  B={len(BANDS)}, A={len(AREAS)}, P={len(EPOCHS)}, L={len(LAYERS)}")
    
    # Prototype (zeros - no actual data without Figure 7)
    Y_prototype = np.zeros(Y_shape)
    
    html_content = f"""<!DOCTYPE html>
<html><head><link rel="stylesheet" href="../shared/style.css"></head><body>
<h1>Figure 8: Y Tensor Band-Area-Layer Summary</h1>
<p><strong>Status:</strong> <span class="status-pending">SMOKE/PLANNED</span></p>
<div class="claim-box">
Y-Tensor: Y = D(B, A, P, L)<br>
B: {len(BANDS)} bands | A: {len(AREAS)} areas | P: {len(EPOCHS)} epochs | L: {len(LAYERS)} layers
</div>
<h2>Canonical Dimensions</h2>
<table>
<tr><th>Axis</th><th>Size</th><th>Values</th></tr>
<tr><td>B (bands)</td><td>{len(BANDS)}</td><td>{', '.join(BANDS[:4])}...</td></tr>
<tr><td>A (areas)</td><td>{len(AREAS)}</td><td>{', '.join(AREAS[:5])}...</td></tr>
<tr><td>P (epochs)</td><td>{len(EPOCHS)}</td><td>{', '.join(EPOCHS)}</td></tr>
<tr><td>L (layers)</td><td>{len(LAYERS)}</td><td>{', '.join(LAYERS)}</td></tr>
</table>
<div class="warning-box">
Y-tensor requires Figure 7 band-power outputs.<br>
Layer assignments are putative/proxy unless validated.<br>
V3d/V3a are kept separate per canonical order.
</div>
<hr><p><small>Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()}</small></p>
</body></html>
"""
    html_path = OUTPUT_ROOT / "figures/fig08_y_tensor.html"
    html_path.write_text(html_content, encoding="utf-8")
    
    # Save prototype
    np.savez(OUTPUT_ROOT / "arrays/fig08_Y_tensor_prototype.npz",
             Y_prototype=Y_prototype,
             bands=BANDS,
             areas=AREAS,
             epochs=EPOCHS,
             layers=LAYERS,
             Y_shape=Y_shape)
    
    manifest = {
        "figure_id": "figure_08",
        "figure_name": "Y Tensor Band-Area-Layer Summary",
        "repo_sha": git_info["sha"],
        "signal_class": "LFP/band_power",
        "Y_tensor_shape": list(Y_shape),
        "bands": BANDS,
        "areas": AREAS,
        "epochs": EPOCHS,
        "layers": LAYERS,
        "layer_resolution": "putative_proxy_unvalidated",
        "v3d_v3a_separate": True,
        "validation_status": "SMOKE_PROTOTYPE",
        "warnings": [
            "Prototype only - zeros array",
            "Requires Figure 7 band-power outputs",
            "Layers are putative/proxy unless validated",
            "No DP->V4 aliasing (kept separate if present)"
        ],
        "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    manifest_path = OUTPUT_ROOT / "fig08_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\nOutputs created:")
    print(f"  HTML: {html_path}")
    print(f"  Manifest: {manifest_path}")
    print(f"\nFigure 8 prototype complete.")
    return manifest

if __name__ == "__main__":
    main()
    sys.exit(0)
