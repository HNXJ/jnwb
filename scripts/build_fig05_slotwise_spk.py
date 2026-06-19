#!/usr/bin/env python3
"""Build Figure 5 (predictable omission SPK slot-local PSTHs).

This is an intentionally bounded reconstruction step after full-sequence
epoch recovery and Figure 4 classification lock.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.analysis.visualization.fig05_slotwise_spk import Fig05Params, build_fig05_slotwise_spk_figure


def main() -> int:
    epochs_path = Path("D:/analysis/nwb/f005_fullseq_p1_spk_epochs_230816.npz")
    classification_path = Path(
        "D:/workspace/omission/outputs/publication_visual_review/figures_04_10/fig04_classification_lock/fig04_unit_classification_table.csv"
    )
    if not epochs_path.exists():
        raise FileNotFoundError(str(epochs_path))
    if not classification_path.exists():
        raise FileNotFoundError(str(classification_path))

    out_dir = Path(
        "D:/workspace/omission/outputs/publication_visual_review/figures_04_10/fig05_slotwise_spk_revised"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    # Quick manifest sanity: classification CSV must match Figure 4.
    cls = pd.read_csv(classification_path)
    if "display_class" not in cls.columns:
        raise ValueError("Classification CSV missing display_class column")
    class_counts = cls["display_class"].value_counts().to_dict()
    print("Figure 5 build: classification counts:", class_counts)

    result = build_fig05_slotwise_spk_figure(
        epochs_path=epochs_path,
        classification_path=classification_path,
        output_png=out_dir / "fig05_revised.png",
        output_svg=out_dir / "fig05_revised.svg",
        output_html=out_dir / "fig05_revised.html",
        params=Fig05Params(),
    )
    print("Figure 5 output:", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

