#!/usr/bin/env python3
"""Build Figure 6 (random-control omission SPK slot-local PSTHs)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.analysis.visualization.fig05_slotwise_spk import Fig05Params
from src.analysis.visualization.fig06_slotwise_spk import build_fig06_slotwise_spk_figure


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
        "D:/workspace/omission/outputs/publication_visual_review/figures_04_10/fig06_slotwise_spk_revised"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    cls = pd.read_csv(classification_path)
    class_counts = cls["display_class"].value_counts().to_dict()
    print("Figure 6 build: classification counts:", class_counts)

    res = build_fig06_slotwise_spk_figure(
        epochs_path=epochs_path,
        classification_path=classification_path,
        output_png=out_dir / "fig06_revised.png",
        output_svg=out_dir / "fig06_revised.svg",
        output_html=out_dir / "fig06_revised.html",
        params=Fig05Params(),
    )
    print("Figure 6 outputs:", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

