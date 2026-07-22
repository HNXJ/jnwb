"""
build_all_manuscript_figures.py — Master Manuscript Figure Suite Runner
Sequentially executes all 7 publication figure build scripts:
  1. suite_01_raster_s_om.py (Figure 1: S+, S-, O+ Exemplar Rasters)
  2. suite_02_raster_s2_om2.py (Figure 2: Secondary Omission Rasters)
  3. build_figure3_spectral_4x2.py (Figure 3: Exemplar TFR Panel)
  4. build_manuscript_figure4.py (Figure 4: 2D Group TFR Spectrogram Heatmaps)
  5. build_manuscript_figure5.py (Figure 5: 1D Group Band Power Traces +/- SEM)
  6. build_manuscript_figure6.py (Figure 6: 4x4 Spectral Harmony Matrix Grid)
  7. build_manuscript_figure7.py (Figure 7: Spike-LFP Polar Phase Locking)
"""

from __future__ import annotations
import os
import sys
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

FIGURE_SCRIPTS = [
    ("Figure 1", "scripts/suite_01_raster_s_om.py"),
    ("Figure 2", "scripts/suite_02_raster_s2_om2.py"),
    ("Figure 3", "scripts/build_figure3_spectral_4x2.py"),
    ("Figure 4", "scripts/build_manuscript_figure4.py"),
    ("Figure 5", "scripts/build_manuscript_figure5.py"),
    ("Figure 6", "scripts/build_manuscript_figure6.py"),
    ("Figure 7", "scripts/build_manuscript_figure7.py"),
    ("LFP Suite", "scripts/build_suite_lfp_power_traces.py"),
]

def main():
    print("==========================================================")
    print("      OMISSION MANUSCRIPT MASTER FIGURE BUILDER           ")
    print("==========================================================")
    
    start_all = time.time()
    results = {}
    
    for label, script_rel in FIGURE_SCRIPTS:
        script_path = REPO_ROOT / script_rel
        if not script_path.exists():
            print(f"[{label}] SKIP: Script not found at {script_rel}")
            results[label] = "MISSING"
            continue
            
        print(f"\n---> Building {label} ({script_rel})...")
        t0 = time.time()
        
        try:
            cmd = [sys.executable, str(script_path)]
            res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
            elapsed = time.time() - t0
            
            if res.returncode == 0:
                print(f"[{label}] SUCCESS ({elapsed:.2f}s)")
                results[label] = f"SUCCESS ({elapsed:.2f}s)"
            else:
                print(f"[{label}] FAILED ({elapsed:.2f}s)")
                print(f"STDERR output:\n{res.stderr}")
                results[label] = "FAILED"
        except Exception as e:
            print(f"[{label}] ERROR: {e}")
            results[label] = f"ERROR: {e}"
            
    total_elapsed = time.time() - start_all
    print("\n==========================================================")
    print("                  BUILD SUMMARY RECEIPTS                  ")
    print("==========================================================")
    for label, status in results.items():
        print(f"  {label:<12}: {status}")
    print(f"\nTotal Build Time: {total_elapsed:.2f}s")
    print("==========================================================")

if __name__ == "__main__":
    main()
