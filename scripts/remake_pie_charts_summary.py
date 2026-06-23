#!/usr/bin/env python3
"""
Rebuild the pie chart summary figure from the authoritative unit tables.

This remake keeps the original 8-panel layout, but makes the first panel
explicitly stable-plus-centric instead of using the opaque "Present / Low
Presence" split from the legacy SVG.

Inputs
------
- outputs/publication_figures/grand_database_6040_units.csv
- outputs/publication_figures/stable_units_calculated_metrics.csv

Outputs
-------
- outputs/publication_visual_review/pie_charts_summary_revised.svg
- outputs/publication_visual_review/pie_charts_summary_revised.csv
- outputs/publication_visual_review/pie_charts_summary_revised.md
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path("D:/workspace/omission")
DEFAULT_GDB = ROOT / "outputs/publication_figures/grand_database_6040_units.csv"
DEFAULT_STABLE_METRICS = ROOT / "outputs/publication_figures/stable_units_calculated_metrics.csv"
DEFAULT_OUT_DIR = ROOT / "outputs/publication_visual_review"


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


def build_summary(gdb: pd.DataFrame, stable_metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []

    def add(panel: str, scope: str, label: str, count: int, denom: int, source: str, notes: str = ""):
        rows.append(
            {
                "panel": panel,
                "scope": scope,
                "label": label,
                "count": int(count),
                "denominator": int(denom),
                "pct": pct(int(count), int(denom)),
                "source": source,
                "notes": notes,
            }
        )

    total_all = len(gdb)
    total_stable = int(gdb["is_stable"].sum())
    total_stable_plus = int(gdb["stable_plus"].sum())

    # A. Stable-plus gate
    add("A", "all_units", "Stable-Plus", total_stable_plus, total_all, "grand_database_6040_units.csv",
        "Revised criterion: vetted analysis-ready subset")
    add("A", "all_units", "Other", total_all - total_stable_plus, total_all, "grand_database_6040_units.csv",
        "Complement of stable-plus")

    # B. Stability gate
    add("B", "all_units", "Stable", total_stable, total_all, "grand_database_6040_units.csv")
    add("B", "all_units", "Unstable/MUA", total_all - total_stable, total_all, "grand_database_6040_units.csv")

    # C. Stimulus modulation
    s_plus = int(gdb["sig_s_plus"].sum())
    s_minus = int(gdb["sig_s_minus"].sum())
    other = total_all - s_plus - s_minus
    add("C", "all_units", "S+ (p<0.2)", s_plus, total_all, "grand_database_6040_units.csv")
    add("C", "all_units", "S- (p<0.2)", s_minus, total_all, "grand_database_6040_units.csv")
    add("C", "all_units", "Other", other, total_all, "grand_database_6040_units.csv")

    # D. Laminar assignment
    layer_counts = {
        "Superficial": int(gdb["layer"].astype(str).str.contains("Superficial", case=False, na=False).sum()),
        "Deep": int(gdb["layer"].astype(str).str.contains("Deep", case=False, na=False).sum()),
    }
    layer_counts["Other/Unresolved"] = total_all - layer_counts["Superficial"] - layer_counts["Deep"]
    for label in ["Superficial", "Deep", "Other/Unresolved"]:
        add("D", "all_units", label, layer_counts[label], total_all, "grand_database_6040_units.csv")

    # Stable-only metrics table.
    stable_df = stable_metrics.copy()
    stable_total = len(stable_df)
    if stable_total != 3071:
        raise RuntimeError(f"Stable metrics table size changed: expected 3071, got {stable_total}")

    fr_col = "firing_rate"
    wf_col = "waveform_duration"
    ff_col = "fano_factor"
    burst_col = "bursty"

    fr_specs = [
        ("Very Slow (<1Hz)", stable_df[fr_col] < 1.0),
        ("Slow (1-2.5Hz)", (stable_df[fr_col] >= 1.0) & (stable_df[fr_col] < 2.5)),
        ("Moderate (2.5-10Hz)", (stable_df[fr_col] >= 2.5) & (stable_df[fr_col] < 10.0)),
        ("Fast (10-20Hz)", (stable_df[fr_col] >= 10.0) & (stable_df[fr_col] < 20.0)),
        ("Very Fast (20Hz+)", stable_df[fr_col] >= 20.0),
    ]
    for label, mask in fr_specs:
        add("E", "stable_units", label, int(mask.sum()), stable_total, "stable_units_calculated_metrics.csv")

    # F. Waveform tiers
    wf_specs = [
        ("Narrow (<0.4ms)", stable_df[wf_col] < 0.4),
        ("Mid (0.4-0.8ms)", (stable_df[wf_col] >= 0.4) & (stable_df[wf_col] < 0.8)),
        ("Wide (0.8-1.2ms)", (stable_df[wf_col] >= 0.8) & (stable_df[wf_col] < 1.2)),
        ("Very Wide (1.2ms+)", stable_df[wf_col] >= 1.2),
    ]
    for label, mask in wf_specs:
        add("F", "stable_units", label, int(mask.sum()), stable_total, "stable_units_calculated_metrics.csv")

    # G. Bursty flag
    add("G", "stable_units", "Bursty", int(stable_df[burst_col].sum()), stable_total, "stable_units_calculated_metrics.csv")
    add("G", "stable_units", "Non-Bursty", int((~stable_df[burst_col].astype(bool)).sum()), stable_total,
        "stable_units_calculated_metrics.csv")

    # H. Fano tiers
    ff_specs = [
        ("Low (<2.5)", stable_df[ff_col] < 2.5),
        ("Mid (2.5-7.0)", (stable_df[ff_col] >= 2.5) & (stable_df[ff_col] < 7.0)),
        ("High (>=7.0)", stable_df[ff_col] >= 7.0),
    ]
    for label, mask in ff_specs:
        add("H", "stable_units", label, int(mask.sum()), stable_total, "stable_units_calculated_metrics.csv")

    return pd.DataFrame(rows)


def render_figure(summary: pd.DataFrame, out_svg: Path) -> None:
    fig, axes = plt.subplots(4, 2, figsize=(10.2, 17.2), facecolor="white")
    axes = axes.flatten()

    panel_order = ["A", "B", "C", "D", "E", "F", "G", "H"]
    panel_titles = {
        "A": "Stable-Plus Gate",
        "B": "Stability Gate",
        "C": "Stimulus Modulation",
        "D": "Putative Laminar Assignment",
        "E": "Firing Rate Tiers",
        "F": "Waveform Durations",
        "G": "Bursty Units",
        "H": "Fano Factor Tiers",
    }
    panel_scope = {
        "A": "All units",
        "B": "All units",
        "C": "All units",
        "D": "All units",
        "E": "Stable units",
        "F": "Stable units",
        "G": "Stable units",
        "H": "Stable units",
    }
    panel_colors = {
        "A": [PALETTE["gold"], PALETTE["gray"]],
        "B": [PALETTE["gold"], PALETTE["gray"]],
        "C": [PALETTE["blue"], PALETTE["violet"], PALETTE["gray"]],
        "D": [PALETTE["gold"], PALETTE["violet"], PALETTE["gray"]],
        "E": [PALETTE["gold"], PALETTE["red_beige"], PALETTE["violet"], PALETTE["orange"], PALETTE["gray"]],
        "F": [PALETTE["violet"], PALETTE["gold"], PALETTE["orange"], PALETTE["gray"]],
        "G": [PALETTE["gold"], PALETTE["gray"]],
        "H": [PALETTE["gold"], PALETTE["violet"], PALETTE["gray"]],
    }

    for ax, panel in zip(axes, panel_order):
        sub = summary[summary["panel"] == panel].copy()
        labels = sub["label"].tolist()
        counts = sub["count"].tolist()
        colors = panel_colors[panel][:len(labels)]
        denom = int(sub["denominator"].iloc[0]) if len(sub) else 0
        total_count = int(sum(counts))
        subtitle = panel_scope[panel]
        total_label = f"Total N = {denom:,} | Shown N = {total_count:,}"
        pie(ax, labels, counts, colors, f"{panel}. {panel_titles[panel]}", subtitle, total_label)

    for ax in axes[len(panel_order):]:
        ax.axis("off")

    fig.suptitle(
        "Pie Chart Summary Rebuilt from Authoritative Tables",
        fontsize=14,
        y=0.995,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.985])
    fig.savefig(out_svg, format="svg", facecolor="white", bbox_inches="tight")
    plt.close(fig)


def write_report(summary: pd.DataFrame, out_md: Path) -> None:
    lines = [
        "# Pie Charts Summary Rebuild",
        "",
        "This rebuild uses explicit repository tables instead of the legacy opaque SVG.",
        "",
        "## Scope",
        "- `grand_database_6040_units.csv` for all-unit panels",
        "- `stable_units_calculated_metrics.csv` for stable-only panels",
        "",
        "## Key change",
        "- Panel A now uses a stable-plus gate instead of the legacy `Present / Low Presence` split.",
        "",
        "## Panel counts",
        "",
    ]

    for panel in ["A", "B", "C", "D", "E", "F", "G", "H"]:
        sub = summary[summary["panel"] == panel].copy()
        sub = sub.sort_values("count", ascending=False)
        denom = int(sub["denominator"].iloc[0]) if len(sub) else 0
        lines.append(f"### {panel}")
        lines.append("")
        lines.append(f"Denominator: {denom:,}")
        lines.append("")
        lines.append("| Label | Count | Percent | Source | Notes |")
        lines.append("| --- | ---: | ---: | --- | --- |")
        for _, row in sub.iterrows():
            lines.append(
                f"| {row['label']} | {int(row['count'])} | {row['pct']:.1f}% | {row['source']} | {row['notes']} |"
            )
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gdb", type=Path, default=DEFAULT_GDB)
    parser.add_argument("--stable-metrics", type=Path, default=DEFAULT_STABLE_METRICS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    gdb = pd.read_csv(args.gdb)
    stable_metrics = pd.read_csv(args.stable_metrics)

    summary = build_summary(gdb, stable_metrics)
    out_csv = args.out_dir / "pie_charts_summary_revised.csv"
    out_svg = args.out_dir / "pie_charts_summary_revised.svg"
    out_md = args.out_dir / "pie_charts_summary_revised.md"

    summary.to_csv(out_csv, index=False)
    write_report(summary, out_md)
    render_figure(summary, out_svg)

    print(f"Wrote {out_svg}")
    print(f"Wrote {out_csv}")
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
