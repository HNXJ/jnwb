"""Figure for showcase 2: accuracy at P4 against P3 per session and area, and time courses.

Usage: python scripts/fig_s2.py
Reads results/s2/per_session.csv and results/s2_allunits_exploratory/per_session.csv;
writes figures/s2_decoding.png.
"""
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from glo_common import AREAS, REPO, RESULTS  # noqa: E402

colors = dict(zip(AREAS, ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]))
fig, axes = plt.subplots(1, 3, figsize=(12, 4))
for ax, (name, sub) in zip(axes[:2], [("Preregistered: responsive units", "s2"),
                                      ("Exploratory: all quality units", "s2_allunits_exploratory")]):
    ps = pd.read_csv(RESULTS / sub / "per_session.csv").dropna(subset=["A4"])
    for a in AREAS:
        s = ps[ps.area == a]
        ax.scatter(s.A3, s.A4, s=18, color=colors[a], label=f"{a} ({len(s)})")
    ax.plot([0.5, 1], [0.5, 1], color="k", lw=0.8)
    ax.scatter(ps.base, ps.base, marker="_", color="0.5", s=40, label="majority baseline")
    ax.set_xlim(0.5, 1.0); ax.set_ylim(0.5, 1.0)
    ax.set_xlabel("Accuracy at P3 (50–250 ms)"); ax.set_ylabel("Accuracy at P4 (50–250 ms)")
    ax.set_title(f"{name}\nmain 2 vs sequenced, xxxx, one point per session × area", fontsize=9)
    ax.legend(fontsize=7, frameon=False, loc="lower right")
ax = axes[2]
ps = pd.read_csv(RESULTS / "s2_allunits_exploratory" / "per_session.csv").dropna(subset=["A4"])
t = 25 + 50 * np.arange(10)
for e, ls in (("tr_p4", "-"), ("tr_p3", "--")):
    m = np.array([json.loads(x) for x in ps[e]])
    ax.plot(t, m.mean(axis=0), ls, color="k", label=f"{e[3:].upper()} (mean of {len(m)} session × area)")
ax.plot(t, np.full(10, ps.base.mean()), ":", color="0.5", label="mean majority baseline")
ax.set_xlabel("Time after onset (ms, 50-ms bins)"); ax.set_ylabel("Accuracy")
ax.set_title("Exploratory: time-resolved accuracy, all quality units\n(no null)", fontsize=9)
ax.legend(fontsize=7, frameon=False)
for a in axes:
    for s in ("top", "right"):
        a.spines[s].set_visible(False)
fig.tight_layout()
out = REPO / "figures"
out.mkdir(exist_ok=True)
fig.savefig(out / "s2_decoding.png", dpi=150)
print(out / "s2_decoding.png")
