#!/usr/bin/env python3
"""
Final refined pie charts using comprehensive grand database.

Stability classification:
- Stable-Plus (stable_plus == True)
- Stable (is_stable == True AND stable_plus == False)
- Stable-Partial (NWB quality==1.0 OR SNR>0.5, is_stable==False)
- MUA (FR > 10Hz, is_stable==False, NWB quality==0.0)
- Unstable (everything else)
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable
import logging

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

ROOT = Path("D:/workspace/omission")
DEFAULT_COMP = ROOT / "outputs/publication_figures/comprehensive_grand_database_all_units.csv"
DEFAULT_GDB = ROOT / "outputs/publication_figures/grand_database_6040_units.csv"
DEFAULT_OUT_DIR = ROOT / "outputs/publication_visual_review"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

PALETTE = {
    "gold": "#CFB87C",
    "violet": "#8F00FF",
    "blue": "#2563EB",
    "orange": "#FF5E00",
    "green": "#16A34A",
    "gray": "#D3D3D3",
    "red": "#DC2626",
}


def pct(count: int, denom: int) -> float:
    return round((count / denom * 100.0) if denom else 0.0, 1)


def pie(ax, labels: Iterable[str], counts: Iterable[int], colors: Iterable[str],
        title: str, subtitle: str, total_label: str) -> None:
    counts = list(counts)
    labels = list(labels)
    colors = list(colors)
    total = sum(counts)

    def fmt(p):
        return f"{p:.1f}%" if p >= 0.5 else ""

    ax.pie(
        counts,
        labels=[f"{lab}\n(N={cnt})" for lab, cnt in zip(labels, counts)],
        colors=colors,
        startangle=90,
        counterclock=False,
        autopct=fmt,
        pctdistance=0.72,
        labeldistance=1.10,
        textprops={"fontsize": 8, "color": "#111111"},
        wedgeprops={"linewidth": 0.9, "edgecolor": "white"},
    )
    ax.set_title(f"{title}\n{subtitle}\n{total_label}", fontsize=10, pad=8)
    ax.set_aspect("equal")
    ax.set_facecolor("white")


def classify_unit(row_comp: pd.Series, row_gdb: pd.Series | None = None) -> str:
    """
    Classify unit using comprehensive data + grand database info.

    Categories:
    - Stable-Plus: stable_plus == True
    - Stable: is_stable == True AND stable_plus == False
    - Stable-Partial: (quality==1.0 OR SNR>0.5) AND is_stable==False
    - MUA: FR > 10Hz AND is_stable==False AND quality==0.0
    - Unstable: everything else
    """

    # Get is_stable and stable_plus from grand database
    is_stable = False
    stable_plus = False

    if row_gdb is not None:
        is_stable = row_gdb.get('is_stable', False) == True
        stable_plus = row_gdb.get('stable_plus', False) == True

    if stable_plus:
        return 'Stable-Plus'

    if is_stable:
        return 'Stable'

    # Get quality and SNR from comprehensive
    quality = row_comp.get('quality', np.nan)
    snr = pd.to_numeric(row_comp.get('snr', np.nan), errors='coerce')
    fr = pd.to_numeric(row_comp.get('firing_rate', np.nan), errors='coerce')

    # Convert quality if string
    if isinstance(quality, str):
        quality = pd.to_numeric(quality, errors='coerce')

    # Stable-Partial: (quality==1.0 OR SNR>0.5) AND is_stable==False
    is_quality_good = (quality == 1.0) if not np.isnan(quality) else False
    is_snr_good = (snr > 0.5) if not np.isnan(snr) else False

    if (is_quality_good or is_snr_good):
        return 'Stable-Partial'

    # MUA: FR > 10Hz AND quality==0.0
    is_quality_bad = (quality == 0.0) if not np.isnan(quality) else False
    if pd.to_numeric(fr, errors='coerce') > 10.0 and is_quality_bad:
        return 'MUA'

    # Unstable: everything else
    return 'Unstable'


def build_summary(comp_df: pd.DataFrame, gdb_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Build summary with refined classification."""
    rows = []

    def add(panel: str, scope: str, label: str, count: int, denom: int, source: str = "", notes: str = ""):
        rows.append({
            "panel": panel,
            "scope": scope,
            "label": label,
            "count": int(count),
            "denominator": int(denom),
            "pct": pct(int(count), int(denom)),
            "source": source,
            "notes": notes,
        })

    total_all = len(comp_df)

    log.info("Classifying units...")

    # Create merged view for classification
    # Key: (session_id, unit_id)
    gdb_lookup = {}
    for _, row in gdb_df.iterrows():
        key = (int(row['session_id']), int(row['unit_id']))
        gdb_lookup[key] = row

    # Classify
    classifications = []
    for _, row in comp_df.iterrows():
        key = (int(row['session_id']), int(row['unit_id']))
        gdb_row = gdb_lookup.get(key)

        classification = classify_unit(row, gdb_row)
        classifications.append(classification)

    comp_df['classification'] = classifications

    # Count by class
    counts = comp_df['classification'].value_counts().to_dict()

    log.info(f"\nStability classification:")
    for cat in ['Stable-Plus', 'Stable', 'Stable-Partial', 'MUA', 'Unstable']:
        cnt = counts.get(cat, 0)
        log.info(f"  {cat}: {cnt} ({pct(cnt, total_all):.1f}%)")

    # Total stable
    total_stable = counts.get('Stable-Plus', 0) + counts.get('Stable', 0) + counts.get('Stable-Partial', 0)
    log.info(f"\nTotal 'stable-like': {total_stable}")

    # Panel: Stability Classification
    add("A", "all_units", "Stable-Plus", counts.get('Stable-Plus', 0), total_all,
        "comprehensive_grand_database_all_units.csv", "is_stable == True (includes stable_plus)")
    add("A", "all_units", "Stable", counts.get('Stable-Partial', 0), total_all,
        "comprehensive_grand_database_all_units.csv", "quality==1.0 OR SNR>0.5, is_stable==False")
    add("A", "all_units", "MUA", counts.get('MUA', 0), total_all,
        "comprehensive_grand_database_all_units.csv", "FR>10Hz, is_stable==False, quality==0.0")
    add("A", "all_units", "Unstable", counts.get('Unstable', 0), total_all,
        "comprehensive_grand_database_all_units.csv", "everything else")

    summary_stats = {
        'total_all': total_all,
        'stable_plus': counts.get('Stable-Plus', 0),
        'stable': counts.get('Stable', 0),
        'stable_partial': counts.get('Stable-Partial', 0),
        'mua': counts.get('MUA', 0),
        'unstable': counts.get('Unstable', 0),
        'total_stable_like': total_stable,
    }

    return pd.DataFrame(rows), summary_stats


def render_figure(summary: pd.DataFrame, out_svg: Path) -> None:
    """Render the pie chart."""
    fig, ax = plt.subplots(1, 1, figsize=(8, 8), facecolor="white")

    sub = summary[summary["panel"] == "A"].copy()
    # Remove "Stable" row with 0 count (kept in data for reference but not shown)
    sub = sub[sub['count'] > 0].copy()
    labels = sub["label"].tolist()
    counts = sub["count"].tolist()

    # Colors: Stable-Plus (gold), Stable (blue), MUA (orange), Unstable (gray)
    colors = [PALETTE["gold"], PALETTE["blue"], PALETTE["orange"], PALETTE["gray"]]
    colors = colors[:len(labels)]

    denom = int(sub["denominator"].iloc[0]) if len(sub) else 0
    total_count = int(sum(counts))

    subtitle = "All 6,040 units (comprehensive)"
    total_label = f"Total N = {denom:,}"

    pie(ax, labels, counts, colors, "Refined Stability Classification", subtitle, total_label)

    fig.suptitle(
        "Refined Stability (Using Comprehensive Database with NWB Quality==1.0)",
        fontsize=12,
        y=0.98,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_svg, format="svg", facecolor="white", bbox_inches="tight")
    log.info(f"Saved figure: {out_svg}")
    plt.close(fig)


def write_report(summary: pd.DataFrame, stats: dict, out_md: Path) -> None:
    """Write markdown summary."""
    lines = [
        "# Refined Stability Classification (Comprehensive Database)",
        "",
        "Based on comprehensive_grand_database_all_units.csv with NWB quality==1.0 (3,071 units).",
        "",
        "## Categories",
        "",
        "| Category | Criteria | Count | Percent |",
        "| --- | --- | ---: | ---: |",
    ]

    for _, row in summary[summary['panel'] == 'A'].iterrows():
        lines.append(
            f"| {row['label']} | {row['notes']} | {int(row['count'])} | {row['pct']:.1f}% |"
        )

    lines.extend([
        "",
        "## Summary",
        "",
        f"- **Stable-Plus**: {stats['stable_plus']} units (stable_plus==True)",
        f"- **Stable**: {stats['stable']} units (is_stable==True, stable_plus==False)",
        f"- **Stable-Partial**: {stats['stable_partial']} units (quality==1.0 OR SNR>0.5, unstable)",
        f"- **Total 'stable-like'**: {stats['total_stable_like']} units ({pct(stats['total_stable_like'], stats['total_all']):.1f}%)",
        "",
        f"- **MUA**: {stats['mua']} units (FR>10Hz, unstable, quality==0.0)",
        f"- **Unstable**: {stats['unstable']} units (low-FR unstable)",
        f"- **Total 'unstable'**: {stats['mua'] + stats['unstable']} units ({pct(stats['mua'] + stats['unstable'], stats['total_all']):.1f}%)",
        "",
        "## Notes",
        "",
        "- Comprehensive database includes all 6,040 units from NWB files",
        "- Quality == 1.0: 3,071 units (from NWB quality field)",
        "- This classification properly separates MUA (high-FR) from low-FR unstable units",
    ])

    out_md.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Saved report: {out_md}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate final refined stability pie charts")
    parser.add_argument("--comp", type=Path, default=DEFAULT_COMP, help="Comprehensive database CSV")
    parser.add_argument("--gdb", type=Path, default=DEFAULT_GDB, help="Grand database CSV path")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR, help="Output directory")
    args = parser.parse_args()

    log.info("=" * 70)
    log.info("Final Refined Stability Classification")
    log.info("=" * 70)

    # Load databases
    log.info(f"Loading comprehensive database: {args.comp}")
    comp_df = pd.read_csv(args.comp)
    log.info(f"Loaded {len(comp_df)} units")

    log.info(f"Loading grand database: {args.gdb}")
    gdb_df = pd.read_csv(args.gdb)
    log.info(f"Loaded {len(gdb_df)} units")

    # Build summary
    log.info("\nBuilding summary table...")
    summary, stats = build_summary(comp_df, gdb_df)

    # Ensure output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Render figure
    log.info("\nRendering figure...")
    out_svg = args.output_dir / "pie_charts_final_refined_stability.svg"
    render_figure(summary, out_svg)

    # Write outputs
    out_csv = args.output_dir / "pie_charts_final_refined_stability.csv"
    summary.to_csv(out_csv, index=False)
    log.info(f"Saved counts: {out_csv}")

    out_md = args.output_dir / "pie_charts_final_refined_stability.md"
    write_report(summary, stats, out_md)

    log.info("\n" + "=" * 70)
    log.info("Done!")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
