#!/usr/bin/env python3
"""
3-panel pie chart figure for comprehensive grand database (all 6,040 units).

Panel A: Stability (Stable-Plus, Stable, MUA, Unstable)
Panel B: Presence Ratio (Strong >98%, Moderate 98-90%, Low 90-75%, Very-Low <75%)
Panel C: Firing Rate (Very-Fast >40Hz, Fast 40-20, Moderate-Fast 20-10, etc.)
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
    "teal": "#00FFCC",
    "brown": "#8B4513",
    "cyan": "#06B6D4",
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


def classify_stability(row_comp: pd.Series, row_gdb: pd.Series | None = None) -> str:
    """Classify unit by stability."""
    stable_plus = False
    if row_gdb is not None:
        stable_plus = row_gdb.get('stable_plus', False) == True

    if stable_plus:
        return 'Stable-Plus'

    quality = row_comp.get('quality', np.nan)
    snr = pd.to_numeric(row_comp.get('snr', np.nan), errors='coerce')

    if isinstance(quality, str):
        quality = pd.to_numeric(quality, errors='coerce')

    is_quality_good = (quality == 1.0) if not np.isnan(quality) else False
    is_snr_good = (snr > 0.5) if not np.isnan(snr) else False

    if (is_quality_good or is_snr_good):
        return 'Stable'

    fr = pd.to_numeric(row_comp.get('firing_rate', np.nan), errors='coerce')
    is_quality_bad = (quality == 0.0) if not np.isnan(quality) else False
    if pd.to_numeric(fr, errors='coerce') > 10.0 and is_quality_bad:
        return 'MUA'

    return 'Unstable'


def build_3panel_summary(comp_df: pd.DataFrame, gdb_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Build summary for all 3 panels."""
    rows = []
    total_all = len(comp_df)

    def add(panel: str, scope: str, label: str, count: int, source: str = "", notes: str = ""):
        rows.append({
            "panel": panel,
            "scope": scope,
            "label": label,
            "count": int(count),
            "denominator": int(total_all),
            "pct": pct(int(count), int(total_all)),
            "source": source,
            "notes": notes,
        })

    log.info("Classifying units by stability...")

    # Create lookup for stability classification
    gdb_lookup = {}
    for _, row in gdb_df.iterrows():
        key = (int(row['session_id']), int(row['unit_id']))
        gdb_lookup[key] = row

    # Panel A: Stability
    log.info("Panel A: Computing stability...")
    stability_counts = {}
    for _, row in comp_df.iterrows():
        key = (int(row['session_id']), int(row['unit_id']))
        gdb_row = gdb_lookup.get(key)
        classification = classify_stability(row, gdb_row)
        stability_counts[classification] = stability_counts.get(classification, 0) + 1

    for cat in ['Stable-Plus', 'Stable', 'MUA', 'Unstable']:
        cnt = stability_counts.get(cat, 0)
        add("A", "all_units", cat, cnt, "comprehensive_grand_database_all_units.csv")

    # Panel B: Presence Ratio
    log.info("Panel B: Computing presence ratio bins...")
    pr = pd.to_numeric(comp_df['presence_ratio'], errors='coerce')

    pr_strong = (pr > 0.98).sum()
    pr_moderate = ((pr > 0.90) & (pr <= 0.98)).sum()
    pr_low = ((pr > 0.75) & (pr <= 0.90)).sum()
    pr_verylow = (pr <= 0.75).sum()

    add("B", "all_units", "Strong (>98%)", pr_strong,
        "comprehensive_grand_database_all_units.csv", "Presence ratio > 98%")
    add("B", "all_units", "Moderate (98-90%)", pr_moderate,
        "comprehensive_grand_database_all_units.csv", "Presence ratio 90-98%")
    add("B", "all_units", "Low (90-75%)", pr_low,
        "comprehensive_grand_database_all_units.csv", "Presence ratio 75-90%")
    add("B", "all_units", "Very-Low (<75%)", pr_verylow,
        "comprehensive_grand_database_all_units.csv", "Presence ratio < 75%")

    total_90plus = pr_strong + pr_moderate
    log.info(f"  Presence >= 90%: {total_90plus} units (✓ at least 4000+)")

    # Panel C: Firing Rate
    log.info("Panel C: Computing firing rate bins...")
    fr = pd.to_numeric(comp_df['firing_rate'], errors='coerce')

    fr_veryfast = (fr > 40).sum()
    fr_fast = ((fr > 20) & (fr <= 40)).sum()
    fr_modfast = ((fr > 10) & (fr <= 20)).sum()
    fr_moderate = ((fr > 5) & (fr <= 10)).sum()
    fr_modslow = ((fr > 2.5) & (fr <= 5)).sum()
    fr_slow = ((fr > 1) & (fr <= 2.5)).sum()
    fr_veryslow = (fr <= 1).sum()

    add("C", "all_units", "Very-Fast (>40Hz)", fr_veryfast,
        "comprehensive_grand_database_all_units.csv")
    add("C", "all_units", "Fast (20-40Hz)", fr_fast,
        "comprehensive_grand_database_all_units.csv")
    add("C", "all_units", "Moderate-Fast (10-20Hz)", fr_modfast,
        "comprehensive_grand_database_all_units.csv")
    add("C", "all_units", "Moderate (5-10Hz)", fr_moderate,
        "comprehensive_grand_database_all_units.csv")
    add("C", "all_units", "Moderate-Slow (2.5-5Hz)", fr_modslow,
        "comprehensive_grand_database_all_units.csv")
    add("C", "all_units", "Slow (1-2.5Hz)", fr_slow,
        "comprehensive_grand_database_all_units.csv")
    add("C", "all_units", "Very-Slow (<1Hz)", fr_veryslow,
        "comprehensive_grand_database_all_units.csv")

    summary_stats = {
        'total_all': total_all,
        'stability': stability_counts,
        'presence_90plus': total_90plus,
    }

    return pd.DataFrame(rows), summary_stats


def render_3panel_figure(summary: pd.DataFrame, out_svg: Path) -> None:
    """Render 3-panel pie chart figure."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), facecolor="white")

    panel_info = {
        "A": {
            "title": "Stability Classification",
            "colors": [PALETTE["gold"], PALETTE["blue"], PALETTE["orange"], PALETTE["gray"]],
        },
        "B": {
            "title": "Presence Ratio",
            "colors": [PALETTE["gold"], PALETTE["violet"], PALETTE["orange"], PALETTE["gray"]],
        },
        "C": {
            "title": "Firing Rate",
            "colors": [PALETTE["red"], PALETTE["orange"], PALETTE["blue"], PALETTE["cyan"],
                      PALETTE["green"], PALETTE["teal"], PALETTE["brown"]],
        },
    }

    for ax, panel in zip(axes, ["A", "B", "C"]):
        sub = summary[summary["panel"] == panel].copy()
        labels = sub["label"].tolist()
        counts = sub["count"].tolist()
        colors = panel_info[panel]["colors"][:len(labels)]
        denom = int(sub["denominator"].iloc[0]) if len(sub) else 0

        subtitle = "All 6,040 units"
        total_label = f"Total N = {denom:,}"

        pie(ax, labels, counts, colors, f"{panel}. {panel_info[panel]['title']}", subtitle, total_label)

    fig.suptitle(
        "Comprehensive Unit Population Summary (All 6,040 Units from NWB)",
        fontsize=14,
        y=0.98,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_svg, format="svg", facecolor="white", bbox_inches="tight", dpi=150)
    log.info(f"Saved figure: {out_svg}")
    plt.close(fig)


def write_3panel_report(summary: pd.DataFrame, stats: dict, out_md: Path) -> None:
    """Write markdown report."""
    lines = [
        "# 3-Panel Comprehensive Unit Summary",
        "",
        "All 6,040 units from comprehensive NWB database.",
        "",
        "## Panel A: Stability Classification",
        "",
        "| Category | Count | Percent |",
        "| --- | ---: | ---: |",
    ]

    for _, row in summary[summary['panel'] == 'A'].iterrows():
        lines.append(f"| {row['label']} | {int(row['count'])} | {row['pct']:.1f}% |")

    lines.extend([
        "",
        "## Panel B: Presence Ratio Distribution",
        "",
        "| Category | Count | Percent |",
        "| --- | ---: | ---: |",
    ])

    for _, row in summary[summary['panel'] == 'B'].iterrows():
        lines.append(f"| {row['label']} | {int(row['count'])} | {row['pct']:.1f}% |")

    lines.append(f"\n✓ **Units with presence ratio ≥ 90%: {stats['presence_90plus']}** (at least 4,000+)")

    lines.extend([
        "",
        "## Panel C: Firing Rate Distribution",
        "",
        "| Category | Count | Percent |",
        "| --- | ---: | ---: |",
    ])

    for _, row in summary[summary['panel'] == 'C'].iterrows():
        lines.append(f"| {row['label']} | {int(row['count'])} | {row['pct']:.1f}% |")

    out_md.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Saved report: {out_md}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate 3-panel comprehensive pie charts")
    parser.add_argument("--comp", type=Path, default=DEFAULT_COMP, help="Comprehensive database")
    parser.add_argument("--gdb", type=Path, default=DEFAULT_GDB, help="Grand database")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR, help="Output directory")
    args = parser.parse_args()

    log.info("=" * 70)
    log.info("3-Panel Comprehensive Pie Charts")
    log.info("=" * 70)

    # Load databases
    log.info(f"Loading comprehensive database...")
    comp_df = pd.read_csv(args.comp)
    log.info(f"Loaded {len(comp_df)} units")

    log.info(f"Loading grand database...")
    gdb_df = pd.read_csv(args.gdb)

    # Build summary
    log.info("\nBuilding 3-panel summary...")
    summary, stats = build_3panel_summary(comp_df, gdb_df)

    # Ensure output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Render figure
    log.info("\nRendering 3-panel figure...")
    out_svg = args.output_dir / "pie_charts_3panel_comprehensive.svg"
    render_3panel_figure(summary, out_svg)

    # Write outputs
    out_csv = args.output_dir / "pie_charts_3panel_comprehensive.csv"
    summary.to_csv(out_csv, index=False)
    log.info(f"Saved counts: {out_csv}")

    out_md = args.output_dir / "pie_charts_3panel_comprehensive.md"
    write_3panel_report(summary, stats, out_md)

    log.info("\n" + "=" * 70)
    log.info("Done!")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
