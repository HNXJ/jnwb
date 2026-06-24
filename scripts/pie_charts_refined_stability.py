#!/usr/bin/env python3
"""
Generate refined pie charts with new stability classification:
- Stable-Plus (stable_plus == True)
- Stable (is_stable == True, stable_plus == False)
- Stable-Partial (quality==1.0 OR SNR>0.5, but is_stable==False)
- MUA (FR > 10Hz, is_stable==False, quality==0.0)
- Unstable (everything else)
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable
import logging
import glob

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pynwb import NWBHDF5IO

ROOT = Path("D:/workspace/omission")
DEFAULT_GDB = ROOT / "outputs/publication_figures/grand_database_6040_units.csv"
DEFAULT_OUT_DIR = ROOT / "outputs/publication_visual_review"
NWB_DIR = "D:/analysis/nwb"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

PALETTE = {
    "gold": "#CFB87C",
    "violet": "#8F00FF",
    "blue": "#2563EB",
    "orange": "#FF5E00",
    "green": "#16A34A",
    "gray": "#D3D3D3",
    "black": "#000000",
    "teal": "#00FFCC",
    "red": "#DC2626",
    "red_beige": "#C9A88A",
    "brown": "#8B4513",
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


def get_nwb_map(nwb_dir: str = NWB_DIR) -> dict[str, str]:
    """Return {session_id: path} for all NWB files."""
    import os
    m = {}
    for f in sorted(glob.glob(f"{nwb_dir}/*.nwb")):
        bn = os.path.basename(f)
        sid = bn.split("ses-")[1].split("_")[0] if "ses-" in bn else bn.split("_")[0]
        m[sid] = f
    return m


def get_quality_snr_from_nwb(gdb: pd.DataFrame) -> dict:
    """Extract quality and SNR from NWB for each unit.
    Keys: (session_id, unit_id)
    """
    nwb_map = get_nwb_map()
    data = {}

    for session_id, nwb_file in nwb_map.items():
        try:
            with NWBHDF5IO(nwb_file, "r", load_namespaces=True) as io:
                nwb = io.read()
                units_df = nwb.units.to_dataframe()

                snr = pd.to_numeric(units_df['snr'], errors='coerce')
                quality = pd.to_numeric(units_df['quality'], errors='coerce')
                cluster_id = pd.to_numeric(units_df['cluster_id'], errors='coerce')

                for idx, row in units_df.iterrows():
                    unit_id = int(cluster_id.iloc[idx])
                    snr_val = snr.iloc[idx]
                    quality_val = quality.iloc[idx]

                    # Replace inf with NaN
                    if np.isinf(snr_val):
                        snr_val = np.nan

                    key = (int(session_id), unit_id)
                    data[key] = {
                        'snr': snr_val,
                        'quality': quality_val,
                    }
        except Exception as e:
            log.warning(f"Error reading {nwb_file}: {e}")

    log.info(f"Extracted SNR/quality for {len(data)} units from NWB")
    return data


def classify_unit(row: pd.Series, nwb_data: dict) -> str:
    """
    Classify unit into stability category.

    Categories:
    - Stable-Plus: stable_plus == True
    - Stable: is_stable == True AND stable_plus == False
    - Stable-Partial: is_quality_good==True OR SNR>0.5, but is_stable==False
    - MUA: FR > 10Hz AND is_stable==False AND is_quality_good==False
    - Unstable: everything else

    Note: Uses is_quality_good from grand database as proxy for NWB quality==1.0
    """

    if row['stable_plus']:
        return 'Stable-Plus'

    if row['is_stable']:
        return 'Stable'

    # Use is_quality_good from grand database (proxy for NWB quality==1.0)
    is_quality_good = (row['is_quality_good'] == True)

    # Try to get SNR from NWB if available
    unit_id = int(row['unit_id'])
    session_id = int(row['session_id'])
    key = (session_id, unit_id)
    nwb_info = nwb_data.get(key, {})
    snr = nwb_info.get('snr', np.nan)
    is_snr_good = (snr > 0.5) if not np.isnan(snr) else False

    # Stable-Partial: (is_quality_good OR SNR>0.5) AND is_stable==False
    if (is_quality_good or is_snr_good):
        return 'Stable-Partial'

    # MUA: FR > 10Hz AND is_quality_good==False
    if row['firing_rate'] > 10.0 and not is_quality_good:
        return 'MUA'

    # Unstable: everything else
    return 'Unstable'


def build_summary(gdb: pd.DataFrame, nwb_data: dict) -> tuple[pd.DataFrame, dict]:
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

    total_all = len(gdb)

    # Classify all units
    log.info("Classifying units...")
    gdb['stability_class'] = gdb.apply(lambda r: classify_unit(r, nwb_data), axis=1)

    # Count by class
    counts = gdb['stability_class'].value_counts().to_dict()

    log.info(f"\nStability classification:")
    for cat in ['Stable-Plus', 'Stable', 'Stable-Partial', 'MUA', 'Unstable']:
        cnt = counts.get(cat, 0)
        log.info(f"  {cat}: {cnt} ({pct(cnt, total_all):.1f}%)")

    # Total stable (including partial)
    total_stable = counts.get('Stable-Plus', 0) + counts.get('Stable', 0) + counts.get('Stable-Partial', 0)
    log.info(f"\nTotal 'stable-like' (Plus + Stable + Partial): {total_stable}")

    # Panel: Stability Classification
    add("A", "all_units", "Stable-Plus", counts.get('Stable-Plus', 0), total_all,
        "grand_database_6040_units.csv", "stable_plus == True")
    add("A", "all_units", "Stable", counts.get('Stable', 0), total_all,
        "grand_database_6040_units.csv", "is_stable == True, stable_plus == False")
    add("A", "all_units", "Stable-Partial", counts.get('Stable-Partial', 0), total_all,
        "grand_database_6040_units.csv", "quality==1.0 OR SNR>0.5, is_stable==False")
    add("A", "all_units", "MUA", counts.get('MUA', 0), total_all,
        "grand_database_6040_units.csv", "FR>10Hz, is_stable==False, quality==0.0")
    add("A", "all_units", "Unstable", counts.get('Unstable', 0), total_all,
        "grand_database_6040_units.csv", "everything else")

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
    labels = sub["label"].tolist()
    counts = sub["count"].tolist()

    # Color scheme: Stable-Plus (gold), Stable (blue), Stable-Partial (violet),
    # MUA (orange), Unstable (gray)
    colors = [PALETTE["gold"], PALETTE["blue"], PALETTE["violet"], PALETTE["orange"], PALETTE["gray"]]
    colors = colors[:len(labels)]

    denom = int(sub["denominator"].iloc[0]) if len(sub) else 0
    total_count = int(sum(counts))

    subtitle = "All 6,040 units"
    total_label = f"Total N = {denom:,}"

    pie(ax, labels, counts, colors, "A. Refined Stability Classification", subtitle, total_label)

    fig.suptitle(
        "Refined Stability Classification: Separating MUA by Firing Rate",
        fontsize=14,
        y=0.98,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_svg, format="svg", facecolor="white", bbox_inches="tight")
    log.info(f"Saved figure: {out_svg}")
    plt.close(fig)


def write_report(summary: pd.DataFrame, stats: dict, out_md: Path) -> None:
    """Write markdown summary."""
    lines = [
        "# Refined Stability Classification",
        "",
        "Classification with separated MUA based on firing rate.",
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
        f"- **Stable-Plus**: {stats['stable_plus']} units",
        f"- **Stable**: {stats['stable']} units",
        f"- **Stable-Partial**: {stats['stable_partial']} units",
        f"- **Total 'stable-like'**: {stats['total_stable_like']} units ({pct(stats['total_stable_like'], stats['total_all']):.1f}%)",
        "",
        f"- **MUA**: {stats['mua']} units (FR>10Hz, unstable, low quality)",
        f"- **Unstable**: {stats['unstable']} units (other unstable)",
        f"- **Total unstable-like**: {stats['mua'] + stats['unstable']} units ({pct(stats['mua'] + stats['unstable'], stats['total_all']):.1f}%)",
    ])

    out_md.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Saved report: {out_md}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate refined stability pie charts")
    parser.add_argument("--gdb", type=Path, default=DEFAULT_GDB, help="Grand database CSV path")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR, help="Output directory")
    args = parser.parse_args()

    log.info("=" * 70)
    log.info("Refined Stability Classification Generator")
    log.info("=" * 70)

    # Load grand database
    log.info(f"Loading grand database: {args.gdb}")
    gdb = pd.read_csv(args.gdb)
    log.info(f"Loaded {len(gdb)} units")

    # Extract SNR and quality from NWB
    log.info("\nExtracting SNR and quality from NWB files...")
    nwb_data = get_quality_snr_from_nwb(gdb)

    # Build summary
    log.info("\nBuilding summary table...")
    summary, stats = build_summary(gdb, nwb_data)

    # Ensure output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Render figure
    log.info("\nRendering figure...")
    out_svg = args.output_dir / "pie_charts_refined_stability.svg"
    render_figure(summary, out_svg)

    # Write CSV and MD
    out_csv = args.output_dir / "pie_charts_refined_stability.csv"
    summary.to_csv(out_csv, index=False)
    log.info(f"Saved counts: {out_csv}")

    out_md = args.output_dir / "pie_charts_refined_stability.md"
    write_report(summary, stats, out_md)

    log.info("\n" + "=" * 70)
    log.info("Done!")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
