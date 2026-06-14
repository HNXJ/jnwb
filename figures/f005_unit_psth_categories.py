#!/usr/bin/env python3
"""f005 single-unit PSTH category figure — artifact-only thin wrapper.

Loads pre-built SPK epoch artifacts and unit classification tables.
Does not perform NWB extraction, event filtering, or classification.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.visualization.f005 import run_f005_figure


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plot f005 single-unit PSTH categories from saved artifacts"
    )
    parser.add_argument(
        "--epochs",
        default="outputs/f005/afamily_spk_p1_epochs.npz",
        help="SPK epoch artifact NPZ",
    )
    parser.add_argument(
        "--classification",
        default="outputs/f005/classification/unit_classification.csv",
        help="Unit classification CSV",
    )
    parser.add_argument(
        "--output",
        default="figures/output/f005_unit_psth_categories.png",
    )
    parser.add_argument(
        "--svg",
        default="figures/output/f005_unit_psth_categories.svg",
    )
    parser.add_argument(
        "--html",
        default="figures/output/f005_unit_psth_categories.html",
    )
    parser.add_argument(
        "--manifest",
        default="figures/output/f005_unit_psth_categories_manifest.json",
    )
    parser.add_argument(
        "--qa-csv",
        default="figures/output/f005_unit_psth_categories_qa.csv",
    )
    parser.add_argument(
        "--allow-unknown-area",
        action="store_true",
        help="Skip area distribution bars when area metadata are unknown",
    )
    args = parser.parse_args()

    manifest = run_f005_figure(
        args.epochs,
        args.classification,
        output_png=args.output,
        output_svg=args.svg,
        output_html=args.html,
        manifest_path=args.manifest,
        qa_csv_path=args.qa_csv,
        allow_unknown_area=args.allow_unknown_area,
    )
    print(f"Wrote figure manifest: {args.manifest}")
    print(f"Class counts: {manifest.get('class_counts')}")
    print(f"HTML: {args.html}")
    if not manifest.get("png_written"):
        print("Note: PNG/SVG static export skipped (kaleido unavailable); HTML written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
