#!/usr/bin/env python3
"""Ensure finalized renders (both figxx_finalized.png and figxx_finalized.svg)
exist in each fig01 to fig07 folder inside omission/outputs/draft-01/.
"""
from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve()
OA_ROOT = HERE.parents[1]
DRAFT01 = OA_ROOT / "outputs" / "draft-01"
FINALIZED_SRC = OA_ROOT / "context" / "figures" / "finalized"
FIG_SRC = OA_ROOT / "context" / "figures"


def main():
    print(f"Ensuring finalized renders in {DRAFT01}...")
    
    for fig_num in ["01", "02", "03", "04", "05", "06", "07"]:
        fig_dir = DRAFT01 / f"fig{fig_num}"
        assets_dir = fig_dir / "assets"
        fig_dir.mkdir(parents=True, exist_ok=True)
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        target_png = f"fig{fig_num}_finalized.png"
        target_svg = f"fig{fig_num}_finalized.svg"
        
        # Look in finalized/ first
        src_png = FINALIZED_SRC / target_png
        src_svg = FINALIZED_SRC / target_svg
        
        # If not in finalized/, check the fig source folder for figXX.png/svg
        if not src_png.exists():
            fig_folders = list(FIG_SRC.glob(f"fig{fig_num}_*"))
            if fig_folders:
                alt_png = fig_folders[0] / f"fig{fig_num}.png"
                if alt_png.exists():
                    src_png = alt_png
                    
        if not src_svg.exists():
            fig_folders = list(FIG_SRC.glob(f"fig{fig_num}_*"))
            if fig_folders:
                alt_svg = fig_folders[0] / f"fig{fig_num}.svg"
                if alt_svg.exists():
                    src_svg = alt_svg
                    
        if src_png.exists():
            shutil.copy2(src_png, fig_dir / target_png)
            shutil.copy2(src_png, assets_dir / target_png)
            shutil.copy2(src_png, fig_dir / f"fig{fig_num}.png")
            shutil.copy2(src_png, assets_dir / f"fig{fig_num}.png")
            print(f"  [fig{fig_num}] Copied {src_png.name} -> {target_png} ({src_png.stat().st_size} bytes)")
        else:
            print(f"  [fig{fig_num}] ERROR: PNG not found!")
            
        if src_svg.exists():
            shutil.copy2(src_svg, fig_dir / target_svg)
            shutil.copy2(src_svg, assets_dir / target_svg)
            shutil.copy2(src_svg, fig_dir / f"fig{fig_num}.svg")
            shutil.copy2(src_svg, assets_dir / f"fig{fig_num}.svg")
            print(f"  [fig{fig_num}] Copied {src_svg.name} -> {target_svg} ({src_svg.stat().st_size} bytes)")
        else:
            print(f"  [fig{fig_num}] ERROR: SVG not found!")


if __name__ == "__main__":
    main()
