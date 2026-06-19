#!/usr/bin/env python3
"""Build Figure 7: omission-local LFP TFR (slot-wise, predictable omissions)."""

from __future__ import annotations

from pathlib import Path

from src.analysis.visualization.fig07_slotwise_local_lfp_tfr import (
    Fig07Params,
    build_fig07_slotwise_local_tfr,
)


def main() -> int:
    params = Fig07Params(
        pre_ms=1031,
        post_ms=1031,
        display_window_ms=(-1031, 1031),
        baseline_window_ms=(-250, -50),
    )

    out_dir = Path(
        "D:/workspace/omission/outputs/publication_visual_review/figures_04_10/fig07_slotwise_local_lfp_tfr_revised"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    res = build_fig07_slotwise_local_tfr(
        output_html=out_dir / "fig07_revised.html",
        output_png=out_dir / "fig07_revised.png",
        output_svg=out_dir / "fig07_revised.svg",
        params=params,
    )
    print("Figure 7 outputs:", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

