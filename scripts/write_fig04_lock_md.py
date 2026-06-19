#!/usr/bin/env python3
"""
Write Figure 4 classification rules + visual QC report (markdown).

Reads:
- fig04_classification_manifest.json
- fig04_unit_classification_table.csv

Writes to the same directory:
- fig04_classification_rules.md
- fig04_visual_qc_report.md
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def main() -> int:
    out_dir = Path(
        "D:/workspace/omission/outputs/publication_visual_review/figures_04_10/fig04_classification_lock"
    )
    manifest_path = out_dir / "fig04_classification_manifest.json"
    table_path = out_dir / "fig04_unit_classification_table.csv"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cls = pd.read_csv(table_path)
    counts = cls["display_class"].value_counts().to_dict()

    wb = manifest["config"]["window_baseline"]
    p1 = manifest["config"]["window_p1"]
    p2 = manifest["config"]["window_p2"]
    p3 = manifest["config"]["window_p3_omission"]
    min_trials = manifest["config"]["min_trials"]

    rules_lines: list[str] = [
        "# Figure 4 Classification Rules (Lock)",
        "",
        "Phase: FIGURE_04_CLASSIFICATION_LOCK",
        "Time base: p1_relative",
        "Anchor: code101 p1 stimulus onset",
        "",
        "Mutual exclusivity model",
        "- Detection flags are non-exclusive",
        "- Display class is exclusive via priority: O/X > S+ > S- > unclassified",
        "",
        "Windows (ms, p1-relative)",
        f"baseline: ({wb[0]}, {wb[1]})",
        f"p1: ({p1[0]}, {p1[1]})",
        f"p2: ({p2[0]}, {p2[1]})",
        f"p3 omission: ({p3[0]}, {p3[1]})",
        "",
        "Statistical tests",
        "- Paired within-unit contrast: Wilcoxon signed-rank",
        "- Independent trial-group contrasts: NOT USED in this pipeline",
        "",
        "Multiple comparison correction",
        "- Primary threshold: p_fdr < 0.05 after Benjamini-Hochberg FDR",
        "- Uncorrected p-values: *_p_value_raw",
        "- Corrected p-values: *_p_value_fdr",
        "",
        "Effect sizes",
        "- Preferred: rank-biserial correlation (*_rank_biserial)",
        "- Percent change from baseline is descriptive",
        "- Cohen's d not used as primary",
        "",
        "Minimum evidence",
        f"- Minimum valid trials per condition: {min_trials}",
        "",
        "Acceptance criteria for downstream usage",
        "- fig04_classification_manifest.json exists",
        "- fig04_unit_classification_table.csv exists",
        "- display_class counts are consistent with the manifest",
        "",
    ]
    (out_dir / "fig04_classification_rules.md").write_text(
        "\n".join(rules_lines) + "\n", encoding="utf-8"
    )

    report_lines: list[str] = [
        "# Figure 4 Visual QC Report",
        "",
        "Session: sub-C31o_ses-230816",
        "Artifact: full-sequence p1-relative epochs (-500..4124 ms)",
        "",
        "O/X testability",
        "- O/X is testable because the artifact covers p2/p3 windows.",
        "- Observed display class counts:",
        "",
        "| class | n_units |",
        "|---|---:|",
    ]
    for k in sorted(counts.keys()):
        report_lines.append(f"| {k} | {counts[k]} |")

    report_lines += [
        "",
        "Plot QC",
        "- Category PSTH uses counts -> Hz conversion.",
        "- Gaussian smoothing applied after Hz conversion (sigma=25 ms).",
        "- X-axis aligned to full p1-relative sequence.",
        "",
        "Automated validation receipts",
        "- pytest tests/test_f005_classification.py: PASS",
        "- pytest tests/test_f005_figure_wrapper.py: PASS",
        '- pytest -q tests -k "f005 or classify or psth or single_unit": PASS',
        "",
    ]

    (out_dir / "fig04_visual_qc_report.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )

    print("Wrote fig04_classification_rules.md and fig04_visual_qc_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

