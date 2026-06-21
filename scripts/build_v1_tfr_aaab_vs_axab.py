#!/usr/bin/env python3
"""Build V1 baseline-relative TFR figures: AAAB vs AXAB with trial matching."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.analysis.visualization.v1_tfr_baseline_figures import (
    DEFAULT_OUT_DIR,
    TFR_DIR,
    build_v1_aaab_vs_axab_figures,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="V1 AAAB vs AXAB baseline TFR figures")
    parser.add_argument("--tfr-dir", type=Path, default=TFR_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    result = build_v1_aaab_vs_axab_figures(
        tfr_dir=args.tfr_dir,
        out_dir=args.out_dir,
        seed=args.seed,
    )

    manifest_path = args.out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("=== V1 AAAB vs AXAB TFR Figures ===")
    print(f"Sessions: {result['n_sessions']}")
    print(f"Matched trials pooled: AAAB={result['n_trials_aaab']}, AXAB={result['n_trials_axab']}")
    print(f"Heatmap: {result['output_heatmap_html']}")
    print(f"Bands:   {result['output_band_html']}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
