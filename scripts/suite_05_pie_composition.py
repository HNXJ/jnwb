"""
suite_05_pie_composition.py — Pie chart of responsive neural categories
Generates composition breakdown pie charts for EACH individual session,
in addition to the grand total population pie chart.
Usage:
  python scripts/suite_05_pie_composition.py
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
import datetime
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import chisquare

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

GRAND_CLASSIFICATION_CSV = "outputs/classification/grand_template_classifications.csv"

def plot_pie_for_dataframe(df: pd.DataFrame, title: str, save_path: Path):
    counts = df['template_label'].value_counts()
    if len(counts) == 0:
        return
        
    obs = counts.values
    try:
        stat, p_val = chisquare(obs)
    except Exception:
        p_val = 1.0
        
    labels = counts.index.tolist()
    sizes = counts.values.tolist()
    colors = ["#888888" if l == "Null" else ("#1D9E75" if l == "S+" else ("#993C1D" if l == "S-" else "#185FA5")) for l in labels]
    
    fig, ax = plt.subplots(figsize=(8, 8))
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, colors=colors, textprops=dict(color="black"))
    
    for t in texts:
        t.set_fontsize(11)
        t.set_weight("bold")
    for at in autotexts:
        at.set_fontsize(10)
        at.set_color("white")
        at.set_weight("bold")
        
    ax.set_title(f"{title} (Chi2 p={p_val:.2e})", fontsize=13, fontweight="bold")
    fig.savefig(save_path, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {save_path}")

def main():
    if not os.path.exists(GRAND_CLASSIFICATION_CSV):
        GRAND_CLASSIFICATION_CSV_ALT = "outputs/classification/figure3_template_correlation_scan.csv"
        if not os.path.exists(GRAND_CLASSIFICATION_CSV_ALT):
            print(f"Classification file {GRAND_CLASSIFICATION_CSV_ALT} not found. Run classify scripts first.")
            return
        df = pd.read_csv(GRAND_CLASSIFICATION_CSV_ALT)
        df['template_label'] = df['prior_display_class']
        df['session_prefix'] = "sub-C31o_ses-230823"
    else:
        df = pd.read_csv(GRAND_CLASSIFICATION_CSV)
        
    out_dir = REPO_ROOT / "outputs/publication_figures/suite_composition"
    out_dir.mkdir(parents=True, exist_ok=True)
    dt_suffix = datetime.datetime.now().strftime("%y%m%d")

    # Generate Grand Pie Chart
    grand_path = out_dir / f"suite_05_pie_composition_grand_{dt_suffix}.svg"
    plot_pie_for_dataframe(df, "Suite 05: Firing Responsive Categories — Grand Total", grand_path)
    
    # Backwards compatibility symlink-style target name
    legacy_target = out_dir / f"suite_05_pie_composition_{dt_suffix}.svg"
    plot_pie_for_dataframe(df, "Suite 05: Firing Responsive Categories — Grand Total", legacy_target)

    # Generate Session-Specific Pie Charts
    for prefix in df['session_prefix'].unique():
        session_df = df[df['session_prefix'] == prefix]
        session_path = out_dir / f"{prefix}_suite_05_pie_composition_{dt_suffix}.svg"
        plot_pie_for_dataframe(session_df, f"Suite 05: Firing Responsive Categories — {prefix}", session_path)

if __name__ == "__main__":
    main()
