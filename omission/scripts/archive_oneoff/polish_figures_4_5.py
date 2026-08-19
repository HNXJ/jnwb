"""
BioRxiv polish: redesign Figures 4 and 5 around one question each.

Figure 4 — How common are omission neurons, and where are they?
  a) population O+ composition (4.90%)
  b) area-wise O+ prevalence
  c) pooled higher-order GLMM OR callout (OR=3.08x)

Figure 5 — How does sparse spiking relate to broad field responses?
  a) area-wise O+ spiking %
  b) identical layout: LFP beta modulated channel %
  c) area-wise spike vs LFP relationship (Spearman from same census)

Data source: artifacts/data/empirical_response_census.json (receipted).
Palette: omission.jnwb_ext.sequence_layout.OMISSION_PALETTE.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from scipy import stats

REPO = Path(r"D:\workspace\omission")
CENSUS_PATH = REPO / "artifacts" / "data" / "empirical_response_census.json"
OUT_DIR = REPO / "context" / "figures"

from omission.jnwb_ext.sequence_layout import OMISSION_PALETTE

GOLD = OMISSION_PALETTE[0]
BLUE = OMISSION_PALETTE[1]
VIOLET = OMISSION_PALETTE[2]
RED = OMISSION_PALETTE[3]
GRAY = OMISSION_PALETTE[11]
WHITE = OMISSION_PALETTE[12]
BLACK = OMISSION_PALETTE[5]

ORDER = ["V1", "V2", "V3a-d-v", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"]
SHORT = ["V1", "V2", "V3", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"]

# Pooled primary-census GLMM (receipted; not per-area OR ladder)
GLMM_OR = 3.08
GLMM_CI = (2.51, 3.78)
GLMM_Z = 10.726
GLMM_P = 7.25e-27
O_PLUS_CI = (4.45, 5.37)


def _load_series():
    census = json.loads(CENSUS_PATH.read_text(encoding="utf-8"))
    ua = census["unit_census_per_area"]
    la = census["lfp_sig_channels_per_area"]
    grand_u = census["grand_unit_totals"]
    grand_l = census["grand_lfp_totals"]

    spk_pct, spk_sem, beta_pct, beta_sem = [], [], [], []
    for area in ORDER:
        u_tot = ua[area]["Total"]
        u_o = ua[area]["O+"]
        p_u = u_o / u_tot
        spk_pct.append(100.0 * p_u)
        spk_sem.append(100.0 * np.sqrt(p_u * (1 - p_u) / u_tot))

        l_tot = la[area]["Total"]
        l_b = la[area]["Beta_Sig"]
        p_l = l_b / l_tot
        beta_pct.append(100.0 * p_l)
        beta_sem.append(100.0 * np.sqrt(p_l * (1 - p_l) / l_tot))

    o_plus_n = int(grand_u["O+"])
    o_plus_tot = int(grand_u["Total"])
    beta_n = int(grand_l["Beta_Sig"])
    beta_tot = int(grand_l["Total"])
    return {
        "spk_pct": np.asarray(spk_pct),
        "spk_sem": np.asarray(spk_sem),
        "beta_pct": np.asarray(beta_pct),
        "beta_sem": np.asarray(beta_sem),
        "o_plus_n": o_plus_n,
        "o_plus_tot": o_plus_tot,
        "o_plus_pct": 100.0 * o_plus_n / o_plus_tot,
        "beta_n": beta_n,
        "beta_tot": beta_tot,
        "beta_pct_grand": 100.0 * beta_n / beta_tot,
    }


def _style_ax(ax, ylabel: str):
    ax.set_facecolor(WHITE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="both", labelsize=11, width=1.2, length=4)
    ax.set_ylabel(ylabel, fontsize=12, fontweight="bold")
    ax.grid(axis="y", linestyle=":", alpha=0.45, color=GRAY)


def build_figure4(data: dict, out_path: Path) -> Path:
    fig = plt.figure(figsize=(12.5, 4.2), dpi=300, facecolor=WHITE)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.05, 1.55, 1.15], wspace=0.32)

    # a) composition
    ax_a = fig.add_subplot(gs[0, 0])
    o = data["o_plus_pct"]
    rest = 100.0 - o
    wedges, texts, autotexts = ax_a.pie(
        [o, rest],
        labels=None,
        colors=[GOLD, GRAY],
        startangle=90,
        wedgeprops={"edgecolor": BLACK, "linewidth": 1.0, "width": 0.55},
        autopct=lambda pct: f"{pct:.1f}%" if pct > 5 else "",
        pctdistance=0.72,
        textprops={"fontsize": 11, "fontweight": "bold"},
    )
    for t in autotexts:
        t.set_color(BLACK)
    ax_a.text(
        0,
        0,
        f"{o:.2f}%\nO+",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
        color=BLACK,
    )
    ax_a.set_title("a", fontsize=14, fontweight="bold", loc="left", pad=8)
    ax_a.legend(
        handles=[
            mpatches.Patch(facecolor=GOLD, edgecolor=BLACK, label="O+ units"),
            mpatches.Patch(facecolor=GRAY, edgecolor=BLACK, label="Other units"),
        ],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.18),
        frameon=False,
        fontsize=10,
        ncol=2,
    )
    ax_a.text(
        0.5,
        -0.28,
        f"{data['o_plus_n']:,}/{data['o_plus_tot']:,} units\n"
        f"95% bootstrap CI [{O_PLUS_CI[0]:.2f}%, {O_PLUS_CI[1]:.2f}%]",
        transform=ax_a.transAxes,
        ha="center",
        va="top",
        fontsize=9,
        color=BLACK,
    )

    # b) area bars
    ax_b = fig.add_subplot(gs[0, 1])
    x = np.arange(len(ORDER))
    ax_b.bar(
        x,
        data["spk_pct"],
        yerr=data["spk_sem"],
        color=GOLD,
        edgecolor=BLACK,
        linewidth=0.8,
        width=0.72,
        capsize=3,
        ecolor=BLACK,
        error_kw={"elinewidth": 1.0},
    )
    ax_b.set_xticks(x)
    ax_b.set_xticklabels(SHORT, fontsize=10, fontweight="bold")
    _style_ax(ax_b, "O+ units (% ± SEM)")
    ax_b.set_ylim(0, max(12.0, float(data["spk_pct"].max()) + 2))
    ax_b.axhline(data["o_plus_pct"], color=RED, linestyle="--", linewidth=1.4, alpha=0.85)
    ax_b.text(
        0.02,
        0.95,
        f"grand {data['o_plus_pct']:.2f}%",
        transform=ax_b.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        color=RED,
        fontweight="bold",
    )
    ax_b.set_title("b", fontsize=14, fontweight="bold", loc="left", pad=8)

    # c) GLMM forest + nested O++ callout (decluttered)
    ax_c = fig.add_subplot(gs[0, 2])
    ax_c.set_facecolor(WHITE)
    ax_c.errorbar(
        [GLMM_OR],
        [1],
        xerr=[[GLMM_OR - GLMM_CI[0]], [GLMM_CI[1] - GLMM_OR]],
        fmt="o",
        markersize=12,
        color=VIOLET,
        ecolor=BLACK,
        elinewidth=2.4,
        capsize=7,
        markeredgecolor=BLACK,
        markeredgewidth=1.0,
        zorder=3,
    )
    ax_c.axvline(1.0, color=GRAY, linestyle="--", linewidth=1.5)
    ax_c.set_yticks([1])
    ax_c.set_yticklabels(["Higher-order\nenrichment"], fontsize=12, fontweight="bold")
    ax_c.set_xlabel("Odds ratio (O+)", fontsize=12, fontweight="bold")
    ax_c.set_xlim(0.4, 4.6)
    ax_c.set_ylim(0.2, 1.8)
    ax_c.spines["top"].set_visible(False)
    ax_c.spines["right"].set_visible(False)
    ax_c.tick_params(axis="x", labelsize=12)
    ax_c.set_title("c", fontsize=16, fontweight="bold", loc="left", pad=8)
    ax_c.text(
        GLMM_OR,
        1.35,
        f"OR = {GLMM_OR:.2f}×\n95% CI [{GLMM_CI[0]:.2f}, {GLMM_CI[1]:.2f}]",
        ha="center",
        va="bottom",
        fontsize=11,
        fontweight="bold",
        color=BLACK,
    )
    ax_c.text(
        0.02,
        0.08,
        "Nested O++ (random-control robust):\n"
        "n = 39 (21 PFC / 18 FEF)\n"
        "does not replace inclusive 4.90%",
        transform=ax_c.transAxes,
        ha="left",
        va="bottom",
        fontsize=9,
        color=BLACK,
        bbox=dict(boxstyle="round,pad=0.35", facecolor=WHITE, edgecolor=VIOLET, linewidth=1.2),
    )
    ax_c.grid(axis="x", linestyle=":", alpha=0.45, color=GRAY)

    fig.suptitle(
        "Omission-linked spiking is sparse and concentrated in higher-order cortex",
        fontsize=13,
        fontweight="bold",
        y=1.02,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight", facecolor=WHITE, edgecolor="none")
    plt.close(fig)
    return out_path


def build_figure5(data: dict, out_path: Path) -> Path:
    spk = data["spk_pct"]
    beta = data["beta_pct"]
    rs, ps = stats.spearmanr(spk, beta)

    fig = plt.figure(figsize=(12.8, 7.6), dpi=300, facecolor=WHITE)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.2, 1.05], hspace=0.42, wspace=0.30)

    x = np.arange(len(ORDER))

    ax_a = fig.add_subplot(gs[0, 0])
    ax_a.bar(
        x,
        spk,
        yerr=data["spk_sem"],
        color=GOLD,
        edgecolor=BLACK,
        linewidth=0.9,
        width=0.78,
        capsize=3.5,
        ecolor=BLACK,
    )
    _style_ax(ax_a, "O+ units (% ± SEM)")
    ax_a.tick_params(axis="both", labelsize=12)
    ax_a.set_xticks(x)
    ax_a.set_xticklabels(SHORT, fontsize=11, fontweight="bold")
    ax_a.set_ylim(0, 12)
    ax_a.set_title("a   Sparse higher-order spiking", fontsize=14, fontweight="bold", loc="left")
    ax_a.text(
        0.98,
        0.95,
        f"grand {data['o_plus_pct']:.2f}%\n({data['o_plus_n']:,}/{data['o_plus_tot']:,})",
        transform=ax_a.transAxes,
        ha="right",
        va="top",
        fontsize=11,
        fontweight="bold",
        color=BLACK,
    )

    ax_b = fig.add_subplot(gs[0, 1])
    ax_b.bar(
        x,
        beta,
        yerr=data["beta_sem"],
        color=VIOLET,
        edgecolor=BLACK,
        linewidth=0.9,
        width=0.78,
        capsize=3.5,
        ecolor=BLACK,
    )
    _style_ax(ax_b, "Beta-modulated channels (% ± SEM)")
    ax_b.tick_params(axis="both", labelsize=12)
    ax_b.set_xticks(x)
    ax_b.set_xticklabels(SHORT, fontsize=11, fontweight="bold")
    ax_b.set_ylim(0, 100)
    ax_b.set_title(
        "b   Broad low-frequency LFP perturbation (14–30 Hz)",
        fontsize=14,
        fontweight="bold",
        loc="left",
    )
    ax_b.text(
        0.98,
        0.95,
        f"grand {data['beta_pct_grand']:.2f}%\n({data['beta_n']:,}/{data['beta_tot']:,})",
        transform=ax_b.transAxes,
        ha="right",
        va="top",
        fontsize=11,
        fontweight="bold",
        color=BLACK,
    )

    ax_c = fig.add_subplot(gs[1, :])
    ax_c.scatter(
        spk,
        beta,
        s=120,
        c=GOLD,
        edgecolors=BLACK,
        linewidths=1.1,
        zorder=3,
    )
    for i, lab in enumerate(SHORT):
        ax_c.annotate(
            lab,
            (spk[i], beta[i]),
            textcoords="offset points",
            xytext=(7, 5),
            fontsize=11,
            fontweight="bold",
        )
    coef = np.polyfit(spk, beta, 1)
    xx = np.linspace(spk.min() * 0.9, spk.max() * 1.05, 50)
    ax_c.plot(xx, np.polyval(coef, xx), color=BLUE, linewidth=2.2, linestyle="-", alpha=0.9)
    _style_ax(ax_c, "Beta-modulated channels (%)")
    ax_c.tick_params(axis="both", labelsize=12)
    ax_c.set_xlabel("O+ units (%)", fontsize=13, fontweight="bold")
    ax_c.set_title(
        "c   Area-wise co-occurrence of sparse spiking and broad field modulation",
        fontsize=14,
        fontweight="bold",
        loc="left",
    )
    ax_c.text(
        0.02,
        0.95,
        f"Spearman r = {rs:.2f}, p = {ps:.1e}\n(n = 10 areas; same census)",
        transform=ax_c.transAxes,
        ha="left",
        va="top",
        fontsize=12,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.35", facecolor=WHITE, edgecolor=GRAY),
    )
    ax_c.set_xlim(0, max(10.5, spk.max() + 1))
    ax_c.set_ylim(70, 86)

    fig.suptitle(
        "Sparse higher-order spiking co-occurs with broad low-frequency cortical-state perturbation",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight", facecolor=WHITE, edgecolor="none")
    plt.close(fig)
    print(f"Figure 5 Spearman r={rs:.4f}, p={ps:.3e}")
    return out_path


def build_figure3(src_path: Path, out_path: Path) -> Path:
    """Restyle existing raster grid with larger panel lettering and whitespace."""
    img = plt.imread(src_path)
    fig = plt.figure(figsize=(12.5, 11.5), dpi=300, facecolor=WHITE)
    ax = fig.add_axes([0.04, 0.04, 0.92, 0.88])
    ax.imshow(img)
    ax.axis("off")
    for x, lab in zip([0.18, 0.50, 0.82], ["a  S+", "b  S−", "c  O++ exemplar"]):
        fig.text(
            x,
            0.955,
            lab,
            ha="center",
            va="top",
            fontsize=16,
            fontweight="bold",
            color=BLACK,
        )
    fig.suptitle(
        "Single-unit exemplars indicate selective task preference, not nonspecific rate elevation",
        fontsize=13,
        fontweight="bold",
        y=0.995,
    )
    fig.text(
        0.5,
        0.01,
        "O++ column prefers random-control robust omission units when available; otherwise best inclusive O+.",
        ha="center",
        va="bottom",
        fontsize=9,
        color=BLACK,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, facecolor=WHITE, edgecolor="none")
    plt.close(fig)
    return out_path


def main():
    data = _load_series()
    fig3 = OUT_DIR / "figure3_selective_coding_rasters.png"
    fig4 = OUT_DIR / "figure4_spiking_glmm_forest_plot.png"
    fig5 = OUT_DIR / "figure5_dissociation_contrast_centerpiece.png"
    raster_src = (
        REPO
        / "outputs"
        / "publication_figures"
        / "figure2_raster_4x3"
        / "figure2_raster_grid_mean_matched_better_O.png"
    )
    if not raster_src.exists():
        raise FileNotFoundError(raster_src)
    p3 = build_figure3(raster_src, fig3)
    p4 = build_figure4(data, fig4)
    p5 = build_figure5(data, fig5)
    alias = OUT_DIR / "figure5_stim_vs_omission_contrast.png"
    alias.write_bytes(p5.read_bytes())
    print("Wrote", p3, p3.stat().st_size)
    print("Wrote", p4, p4.stat().st_size)
    print("Wrote", p5, p5.stat().st_size)


if __name__ == "__main__":
    main()
