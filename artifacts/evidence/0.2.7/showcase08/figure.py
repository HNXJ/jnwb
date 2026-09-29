"""Summary figure from report.json: detection rates against ground truth, network recovery, spike MI."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).parent
r = json.loads((HERE / "report.json").read_text(encoding="utf-8"))
rates, expected = r["B_rates"], r["B_expected"]
scen = list(rates)
ests = ["granger", "granger_spectral", "phase_slope_index", "transfer_entropy", "granger | Z"]
short = ["Granger", "spectral\nGranger", "PSI", "TE", "Granger\n| Z"]

fig = plt.figure(figsize=(13, 7.2), layout="constrained")
gs = fig.add_gridspec(2, 3, width_ratios=[2.6, 1, 1], height_ratios=[1, 1])
ax = fig.add_subplot(gs[:, 0])
score = np.full((len(scen), len(ests)), np.nan)
for i, s in enumerate(scen):
    ex_xy, ex_yx = expected[s]
    for j, e in enumerate(ests):
        v = rates[s].get(e)
        if v is None:
            ax.text(j, i, "not run", ha="center", va="center", fontsize=8, color="#666666")
            continue
        want_xy, want_yx = ex_xy, ex_yx
        if e == "phase_slope_index" and ex_xy and ex_yx:
            want_xy = want_yx = False  # PSI measures net lead; symmetric coupling has none
        a = v["rate_x_to_y"] if want_xy else 1 - v["rate_x_to_y"]
        b = v["rate_y_to_x"] if want_yx else 1 - v["rate_y_to_x"]
        score[i, j] = (a + b) / 2
        ax.text(j, i, f"{v['rate_x_to_y']:.2f} / {v['rate_y_to_x']:.2f}", ha="center", va="center",
                fontsize=9, color="black")
im = ax.imshow(score, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
ax.set_xticks(range(len(ests)), short, fontsize=9)
labels = [f"{s}\n(truth: X→Y {'yes' if expected[s][0] else 'no'}, Y→X {'yes' if expected[s][1] else 'no'})"
          for s in scen]
ax.set_yticks(range(len(scen)), labels, fontsize=8)
ax.set_title(f"A. Fraction of {r['seeds']} seeds with p < {r['alpha']}  (X→Y / Y→X)\n"
             f"colour = agreement with ground truth; n = {r['N']} samples, {r['surrogates']} surrogates\n"
             "PSI: one two-sided test, direction = sign of net; bidirectional truth for PSI = no net lead",
             fontsize=10)
cb = fig.colorbar(im, ax=ax, shrink=0.6)
cb.set_label("agreement with truth (fraction of seeds)")

axc = fig.add_subplot(gs[0, 1:])
er = np.array(r["C"]["edge_rate"], dtype=float)
lab = r["C"]["labels"]
np.fill_diagonal(er, np.nan)
imc = axc.imshow(er, cmap="viridis", vmin=0, vmax=1)
for i in range(er.shape[0]):
    for j in range(er.shape[1]):
        if i != j:
            axc.text(j, i, f"{er[i, j]:.1f}", ha="center", va="center",
                     color="white" if er[i, j] < 0.5 else "black", fontsize=9)
axc.set_xticks(range(len(lab)), lab)
axc.set_yticks(range(len(lab)), lab)
axc.set_xlabel("target")
axc.set_ylabel("source")
axc.set_title("B. directed_network, chain A→B→C + bystander D\nfraction of 10 seeds with p < 0.05",
              fontsize=10)
fig.colorbar(imc, ax=axc, shrink=0.8).set_label("edge detection rate")

axd = fig.add_subplot(gs[1, 1:])
D = r["D"]
vals = [D["dependent"], D["independent"], D["count_dependent"], D["count_independent"]]
names = ["occupancy MI\n2 ms jitter copy", "occupancy MI\nindependent", "count MI\n2 ms jitter copy",
         "count MI\nindependent"]
axd.bar(range(4), vals, color=["#1b7837", "#999999", "#1b7837", "#999999"])
axd.set_xticks(range(4), names, fontsize=8)
axd.set_ylabel("mutual information (bits)")
axd.set_title(f"C. Spike MI, mean of 20 seeds; |MI(a,b) − MI(b,a)| ≤ {D['symmetry_max_abs_diff']:.0e}",
              fontsize=10)
fig.suptitle(f"jnwb {r['version']} @ {r['commit'][:8]}: docs page 08 estimators on synthetic ground truth",
             fontsize=11)
fig.savefig(HERE / "showcase08.png", dpi=150)
print("wrote", HERE / "showcase08.png")
