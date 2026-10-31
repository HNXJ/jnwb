"""Figure for showcase 1: per-area context contrasts, drift bound and the positive control.

Usage: python scripts/fig_s1.py
Reads results/s1/*.csv; writes figures/s1_contexts.png.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from glo_common import AREAS, REPO, RESULTS  # noqa: E402

S1 = RESULTS / "s1"
conf = pd.read_csv(S1 / "confirmatory.csv")
drift = pd.read_csv(S1 / "drift.csv").assign(contrast="D_main1_vs_main2_xxxx")
pc = pd.read_csv(S1 / "exploratory_positive_control_SSA.csv")
rows = [("C1_main_vs_random_xxxx", "C1 xxxx main − random"), ("C2_main_vs_seq_xxxx", "C2 xxxx main − sequenced"),
        ("C3_random_vs_seq_xxxx", "C3 xxxx random − sequenced"), ("C4_random_vs_seq_yyyy", "C4 yyyy random − sequenced"),
        ("D_main1_vs_main2_xxxx", "D drift: main 1 − main 2"),
        ("PC_SSA_x_random_yyyx_vs_xxxx_P4", "Positive control: x after yyy − x after xxx")]
tab = pd.concat([conf, drift, pc])
colors = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#7f7f7f", "#ff7f0e"]
fig, ax = plt.subplots(figsize=(9, 4.2))
w = 0.13
for j, ((key, label), c) in enumerate(zip(rows, colors)):
    for i, a in enumerate(AREAS):
        r = tab[(tab.contrast == key) & (tab.area == a)]
        if r.empty or pd.isna(r.iloc[0].get("mean_hz")):
            continue
        r = r.iloc[0]
        x = i + (j - 2.5) * w
        ax.errorbar(x, r.mean_hz, yerr=[[r.mean_hz - r.ci_lo], [r.ci_hi - r.mean_hz]], fmt="o", color=c, ms=4,
                    capsize=2, label=label if i == 0 else None)
ax.axhline(0, color="k", lw=0.8)
labels = []
for a in AREAS:
    n = conf[(conf.area == a) & (conf.contrast == rows[0][0])].n_mice.iloc[0]
    labels.append(f"{a}\n{n} mice" + ("" if n >= 6 else " (not tested)"))
ax.set_xticks(range(len(AREAS)), labels)
ax.set_ylabel("Mean over mice of per-mouse median (Hz)\n95 % bootstrap CI over mice")
ax.set_title("DANDI 000253, responsive units: P4 − P3 rate (50–250 ms) contrasts across contexts", fontsize=10)
ax.legend(fontsize=7, ncol=2, frameon=False, loc="upper left")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
out = REPO / "figures"
out.mkdir(exist_ok=True)
fig.savefig(out / "s1_contexts.png", dpi=150)
print(out / "s1_contexts.png")
