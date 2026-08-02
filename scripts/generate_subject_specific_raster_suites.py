#!/usr/bin/env python3
"""
Generate 4x4 raster suite PNG figures for top FEF Unit 51 similar units in subjects V182o and V198o.

Output Directories:
  outputs/raster_suites/v182o_fef51_similar/
  outputs/raster_suites/v198o_fef51_similar/
"""

from __future__ import annotations

import os
import sys
import pathlib
import pandas as pd

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from generate_oplusplus_raster_suites import render_unit_raster_suite

CSV_PATH = REPO_ROOT / "outputs" / "classification" / "omission_fef51_similar_units.csv"

OUT_DIR_V182 = REPO_ROOT / "outputs" / "raster_suites" / "v182o_fef51_similar"
OUT_DIR_V198 = REPO_ROOT / "outputs" / "raster_suites" / "v198o_fef51_similar"

OUT_DIR_V182.mkdir(parents=True, exist_ok=True)
OUT_DIR_V198.mkdir(parents=True, exist_ok=True)

def main():
    df = pd.read_csv(CSV_PATH)
    
    # 1. Process V182o
    v182 = df[df["session"].str.startswith("sub-V182o")].sort_values("fef51_corr_r", ascending=False).reset_index(drop=True)
    top_v182 = v182.head(10)
    print(f"Generating top {len(top_v182)} V182o raster suites...")
    for idx, row in top_v182.iterrows():
        rank = idx + 1
        stem = str(row["session"]).replace("_rec", "")
        u_row = int(row["unit_row"])
        area = str(row["area"])
        r_val = float(row["fef51_corr_r"])
        
        filename = f"v182o_fef51_similar_rank{rank:02d}_{stem}_row{u_row}_{area}_r{r_val:.3f}.png"
        out_path = OUT_DIR_V182 / filename
        render_unit_raster_suite(rank, row, out_path)
        
    # 2. Process V198o
    v198 = df[df["session"].str.startswith("sub-V198o")].sort_values("fef51_corr_r", ascending=False).reset_index(drop=True)
    top_v198 = v198.head(10)
    print(f"\nGenerating top {len(top_v198)} V198o raster suites...")
    for idx, row in top_v198.iterrows():
        rank = idx + 1
        stem = str(row["session"]).replace("_rec", "")
        u_row = int(row["unit_row"])
        area = str(row["area"])
        r_val = float(row["fef51_corr_r"])
        
        filename = f"v198o_fef51_similar_rank{rank:02d}_{stem}_row{u_row}_{area}_r{r_val:.3f}.png"
        out_path = OUT_DIR_V198 / filename
        render_unit_raster_suite(rank, row, out_path)

    print(f"\nAll V182o and V198o raster suites generated cleanly.")

if __name__ == "__main__":
    main()
