#!/usr/bin/env python3
"""Build area × layer × condition TFR band figures (11 × 2 × 12 = 264)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.lfp.lfp_constants import ALL_CONDITIONS, CANONICAL_AREAS
from src.analysis.lfp.lfp_layer_masks import LAYER_NAMES
from src.analysis.visualization.area_layer_tfr_figures import build_all_area_layer_tfr_figures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build TFR band figures for all area × layer × condition cells."
    )
    parser.add_argument("--area", type=str, default=None, help="Single canonical area")
    parser.add_argument("--layer", type=str, default=None, choices=LAYER_NAMES)
    parser.add_argument("--condition", type=str, default=None, choices=ALL_CONDITIONS)
    parser.add_argument("--force", action="store_true", help="Rebuild even if HTML exists")
    parser.add_argument("--rebuild-masks", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="V1 superficial AAAB only")
    args = parser.parse_args()

    areas = [args.area] if args.area else list(CANONICAL_AREAS)
    layers = (args.layer,) if args.layer else LAYER_NAMES
    conditions = [args.condition] if args.condition else list(ALL_CONDITIONS)

    if args.smoke:
        areas = ["V1"]
        layers = ("superficial_putative",)
        conditions = ["AAAB"]

    manifest = build_all_area_layer_tfr_figures(
        areas=areas,
        layers=layers,
        conditions=conditions,
        rebuild_masks=args.rebuild_masks or args.smoke,
        skip_existing=not args.force,
    )
    print(json.dumps({k: v for k, v in manifest.items() if k != "figures"}, indent=2))
    print(f"Wrote manifest: {manifest['manifest_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
