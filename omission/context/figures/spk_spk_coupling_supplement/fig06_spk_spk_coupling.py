r"""
Figure 6 -- SPK-SPK lead/lag correlation (headline, redesigned 2026-08-06), directed Granger
causality (supplement).

REDESIGN (2026-08-06)
    Per explicit direction ("keep Granger for LFP, use sliding correlation for SPK-SPK"):
    Granger causality remains fig05's LFP-LFP method, unchanged. For SPK-SPK, the headline is
    now scripts/extract_population_spk_spk_lag_corr.py's trial-matched lead/lag correlation
    between (area, functional_type) population-rate nodes -- same engine (trial-mismatch
    shuffle null) as the LFP-LFP sliding-window work, generalized from "slide the window
    position" to "slide the lag between two nodes." Granger's fully-null result (0/27, unchanged
    from the 2026-08-04/05 build) is retained as a supplement, not discarded.

HEADLINE FAMILY SIZE -- WHY THIS FIGURE DOESN'T USE figstats.write() FOR THE MAIN RESULT
    The corrected family for the lead/lag result is 12,033 cells (scope x node-pair x lag x
    condition-group, every cell with >=3 sessions) -- two orders of magnitude larger than any
    other family in this project (fig05's biggest is 225). figstats.write() lists every family
    member in its markdown table; forced through it, that would be an unreadable ~12,000-row
    file. Instead, outputs/population_spk_spk_lag_corr/lag_hit_rates.csv (written by
    aggregate_population_spk_spk_lag_corr.py) is the authoritative, already-corrected full-family
    record, and this script's own svg/fig06_lag_corr_summary.md carries only the Holm/BH
    survivors with a pointer back to the full table -- correction happens once, in the
    aggregation script, never re-derived on a truncated subset here.

RESULT
    4/12,033 Holm-Bonferroni, 35/12,033 BH-FDR. All 4 Holm survivors and most BH survivors sit
    at lag 0 or within +-30ms -- no corrected evidence of a substantial lead/lag delay; what
    survives is near-simultaneous population coupling in a few specific (area, functional_type)
    pairs (V4 Other/S-, V4 S+/S-, FEF Other/S-), all within-area. See
    outputs/population_spk_spk_lag_corr/README.md for the full result and caveats.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.dirname(HERE)
sys.path.insert(0, FIGDIR)
from figstyle import AREA_ORDER  # noqa: E402
from figstats import correct, paired_location, write  # noqa: E402
from svgassemble import assemble  # noqa: E402

REPO = os.path.dirname(os.path.dirname(FIGDIR))
sys.path.insert(0, REPO)
from jnwb.connectivity import directed_network  # noqa: E402

TRIALS_NPZ = os.path.join(REPO, "outputs", "condition_spike_trials", "trials.npz")
NET_OUT_DIR = os.path.join(REPO, "outputs", "spk_spk_granger_network")
LAG_DIR = os.path.join(REPO, "outputs", "population_spk_spk_lag_corr")
RATERATIO_DIR = os.path.join(REPO, "outputs", "population_spk_spk_rateratio_nb")
SVG_DIR = os.path.join(HERE, "svg")

CONDS = ["RXRR", "RRRR"]
GRANGER_KW = dict(order="auto", max_lag=10, detrend="zscore")
MIN_AREAS_PER_CALL = 3
CG_ORDER = ["baseline", "stim", "omission"]
Z_THRESH = 1.96
MIN_SESSIONS = 3
FUNC_GROUP_ORDER = ["Other", "S+", "S-", "O+", "O++"]
FUNC_GROUP_COLORS = {"Other": "#BDBDBD", "S+": "#1B9E5A", "S-": "#B5651D",
                     "O+": "#C51B8A", "O++": "#7A0177"}
FLAT_FRAC_THRESH = 0.70   # BH-significant at >=70% of tested lags -> "flat" (shared-context-like)


# ============================================================ headline: lead/lag correlation
def load_lag_hit_rates():
    df = pd.read_csv(os.path.join(LAG_DIR, "lag_hit_rates.csv"))
    df["node1"] = df.node1_area + "/" + df.node1_func
    df["node2"] = df.node2_area + "/" + df.node2_func
    df["pair"] = df.node1 + " - " + df.node2
    return df


def draw_lag_panel(df, cg, pairs_order, ax):
    sub = df[df.condition_group == cg]
    lags = sorted(sub.lag_ms.unique())
    mat = np.full((len(pairs_order), len(lags)), np.nan)
    holm_mask = np.zeros_like(mat, dtype=bool)
    bh_mask = np.zeros_like(mat, dtype=bool)
    for i, pair in enumerate(pairs_order):
        prow = sub[sub.pair == pair]
        for _, r in prow.iterrows():
            j = lags.index(r.lag_ms)
            mat[i, j] = r.hit_rate
            if bool(r.sig_holm) if pd.notna(r.sig_holm) else False:
                holm_mask[i, j] = True
            elif bool(r.sig_bh_fdr) if pd.notna(r.sig_bh_fdr) else False:
                bh_mask[i, j] = True
    im = ax.imshow(mat, cmap="viridis", vmin=0, vmax=1, aspect="auto")
    m = 0.09
    for i in range(len(pairs_order)):
        for j in range(len(lags)):
            if holm_mask[i, j]:
                ax.add_patch(plt.Rectangle((j - 0.5 + m, i - 0.5 + m), 1 - 2 * m, 1 - 2 * m,
                                           fill=False, edgecolor="red", lw=1.8))
            elif bh_mask[i, j]:
                ax.add_patch(plt.Rectangle((j - 0.5 + m, i - 0.5 + m), 1 - 2 * m, 1 - 2 * m,
                                           fill=False, edgecolor="red", lw=1.0, linestyle="--"))
    ax.set_xticks(range(len(lags)))
    ax.set_xticklabels([f"{int(l)}" for l in lags], rotation=90, fontsize=5.5)
    ax.set_yticks(range(len(pairs_order)))
    ax.set_yticklabels(pairs_order, fontsize=6)
    ax.set_title(cg, fontsize=9)
    ax.set_xlabel("lag (ms)", fontsize=7)
    ax.axvline(lags.index(0.0), color="white", lw=0.6, ls=":")
    return im


def draw_lag_headline(df, out_stem):
    sig = df[df.sig_bh_fdr.fillna(False).infer_objects(copy=False)]
    pairs_order = sorted(sig.pair.unique())
    if not pairs_order:
        pairs_order = ["(none survive BH-FDR)"]

    fig, axes = plt.subplots(1, len(CG_ORDER), figsize=(4.2 * len(CG_ORDER), 0.35 *
                             len(pairs_order) + 1.8), sharey=True)
    im0 = None
    for ax, cg in zip(axes, CG_ORDER):
        if pairs_order[0] == "(none survive BH-FDR)":
            ax.text(0.5, 0.5, "no pairs survive BH-FDR", ha="center", va="center",
                   transform=ax.transAxes, fontsize=8)
            ax.set_title(cg, fontsize=9)
            continue
        im0 = draw_lag_panel(df, cg, pairs_order, ax)
    if im0 is not None:
        cb = fig.colorbar(im0, ax=axes, shrink=0.7, pad=0.01)
        cb.set_label("cross-session hit rate (|Z|>=1.96)", rotation=270, labelpad=14, fontsize=8)
    fig.suptitle("SPK-SPK lead/lag population correlation -- (area, functional_type) pairs "
                "surviving BH-FDR in any condition group", fontsize=10, y=1.02)
    fig.text(0.5, -0.01, "Red solid: p_holm<0.05 (family of 12,033). Red dashed: q_BH<0.05 "
            "only. Dotted white line: lag=0. Positive lag: node1 leads node2.",
            ha="center", fontsize=7, color="0.2")
    out = os.path.join(SVG_DIR, out_stem)
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)
    return out + ".svg"


def write_lag_summary(df):
    """NOT figstats.write() -- see module docstring for why (12,033-cell family). Correction
    already happened in aggregate_population_spk_spk_lag_corr.py; this only reports the
    survivors, pointing back to lag_hit_rates.csv as the full, already-corrected family."""
    holm = df[df.sig_holm.fillna(False).infer_objects(copy=False)] \
        .sort_values("bh_q")
    bh = df[df.sig_bh_fdr.fillna(False).infer_objects(copy=False)] \
        .sort_values("bh_q")
    lines = [
        "# Figure 6 headline -- SPK-SPK lead/lag correlation, corrected-family summary", "",
        "Full family (12,033 cells: scope x node-pair x lag x condition-group, all cells with "
        ">=3 sessions) is corrected in `aggregate_population_spk_spk_lag_corr.py` and recorded "
        "in full at `outputs/population_spk_spk_lag_corr/lag_hit_rates.csv` -- THIS file lists "
        "only the survivors and is not itself a separate correction pass.", "",
        f"**{len(holm)}/12033 survive Holm-Bonferroni (FWER). {len(bh)}/12033 survive BH-FDR.**",
        "",
        "## Holm-Bonferroni survivors", "",
        "| condition_group | scope | node1 | node2 | lag_ms | n_sessions | hit_rate | holm_p | bh_q |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for _, r in holm.iterrows():
        lines.append(f"| {r.condition_group} | {r.scope} | {r.node1} | {r.node2} | "
                     f"{r.lag_ms:.0f} | {int(r.n_sessions)} | {r.hit_rate:.3f} | "
                     f"{r.holm_p:.2e} | {r.bh_q:.2e} |")
    lines += ["", "## BH-FDR survivors (superset of the above)", "",
             "| condition_group | scope | node1 | node2 | lag_ms | n_sessions | hit_rate | "
             "holm_p | bh_q |",
             "|---|---|---|---|---|---|---|---|---|"]
    for _, r in bh.iterrows():
        lines.append(f"| {r.condition_group} | {r.scope} | {r.node1} | {r.node2} | "
                     f"{r.lag_ms:.0f} | {int(r.n_sessions)} | {r.hit_rate:.3f} | "
                     f"{r.holm_p:.2e} | {r.bh_q:.2e} |")
    with open(os.path.join(SVG_DIR, "fig06_lag_corr_summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return len(holm), len(bh)


# ============================================================ supplement: directed Granger
def compute_edges():
    d = np.load(TRIALS_NPZ)
    keys = set(k for k in d.files if k != "times")
    sessions = sorted({k.split("|")[0] for k in keys})
    os.makedirs(NET_OUT_DIR, exist_ok=True)
    rows = []
    n_calls = 0
    t0 = time.time()
    for si, session in enumerate(sessions, 1):
        for cond in CONDS:
            areas = [a for a in AREA_ORDER if f"{session}|{a}|{cond}" in keys]
            if len(areas) < MIN_AREAS_PER_CALL:
                continue
            signals = {a: d[f"{session}|{a}|{cond}"] for a in areas}
            n_tr = {a: v.shape[0] for a, v in signals.items()}
            try:
                res = directed_network(signals, method="granger", fdr=False, **GRANGER_KW)
            except Exception as e:
                rows.append({"session": session, "cond": cond,
                            "areaA": None, "areaB": None, "error": str(e)})
                continue
            n_calls += 1
            mat, pmat, labels = res["matrix"], res["p_matrix"], res["labels"]
            for i, a in enumerate(labels):
                for j, b in enumerate(labels):
                    if i == j:
                        continue
                    rows.append({
                        "session": session, "cond": cond, "areaA": a, "areaB": b,
                        "x_to_y": float(mat[i, j]), "p_x_to_y": float(pmat[i, j]),
                        "n_trials_A": n_tr[a], "n_trials_B": n_tr[b],
                        "n_warnings": len(res.get("warnings", [])), "error": None,
                    })
        pd.DataFrame(rows).to_csv(os.path.join(NET_OUT_DIR, "edges.csv"), index=False)
        print(f"[{datetime.now():%H:%M:%S}] session {si}/{len(sessions)} ({session}), "
             f"{n_calls} directed_network() calls so far, {time.time()-t0:.0f}s", flush=True)
    return pd.DataFrame(rows), time.time() - t0


def net_directionality(df):
    piv = df.dropna(subset=["areaA"]).set_index(["session", "cond", "areaA", "areaB"])
    out = []
    for (session, cond, a, b), row in piv.iterrows():
        if a >= b:
            continue
        try:
            fwd = piv.loc[(session, cond, a, b), "x_to_y"]
            rev = piv.loc[(session, cond, b, a), "x_to_y"]
        except KeyError:
            continue
        out.append({"session": session, "cond": cond, "areaA": a, "areaB": b,
                    "net_a_to_b": float(fwd) - float(rev)})
    return pd.DataFrame(out)


def within_condition_stats(net_df, areas):
    stats = {}
    for cond in CONDS:
        fam_stats = []
        sub = net_df[net_df.cond == cond]
        for i, a in enumerate(areas):
            for b in areas[i + 1:]:
                vals = sub[(sub.areaA == a) & (sub.areaB == b)]["net_a_to_b"].values
                if len(vals) < 3:
                    continue
                fam_stats.append(paired_location(
                    vals, np.zeros_like(vals), figure="fig06_supp", panel=cond,
                    question=f"{a}<->{b} net directionality, {cond}",
                    unit="session", family=f"fig06_supp_{cond}",
                    note=f"n={len(vals)} sessions; positive = {a}->{b} net"))
        stats[cond] = fam_stats
    return stats


def delta_stats(net_df, areas):
    fam_stats = []
    for i, a in enumerate(areas):
        for b in areas[i + 1:]:
            r = net_df[(net_df.cond == "RRRR") & (net_df.areaA == a)
                      & (net_df.areaB == b)].set_index("session")
            x = net_df[(net_df.cond == "RXRR") & (net_df.areaA == a)
                      & (net_df.areaB == b)].set_index("session")
            common = sorted(set(r.index) & set(x.index))
            if len(common) < 3:
                continue
            fam_stats.append(paired_location(
                r.loc[common, "net_a_to_b"].values, x.loc[common, "net_a_to_b"].values,
                figure="fig06_supp", panel="delta",
                question=f"{a}<->{b} net directionality, RRRR vs RXRR",
                unit="session", family="fig06_supp_delta",
                note=f"n={len(common)} sessions with both conditions"))
    return fam_stats


def build_delta_df(net_df):
    r = net_df[net_df.cond == "RRRR"].set_index(["session", "areaA", "areaB"])
    x = net_df[net_df.cond == "RXRR"].set_index(["session", "areaA", "areaB"])
    common = r.index.intersection(x.index)
    out = r.loc[common].copy()
    out["net_a_to_b"] = r.loc[common, "net_a_to_b"].values - x.loc[common, "net_a_to_b"].values
    out["cond"] = "delta"
    return out.reset_index()


def draw_network_figure(net_df, cond, areas, sig_lookup, out_stem, title):
    n = len(areas)
    fig, ax = plt.subplots(figsize=(5.0, 4.6))
    mat = np.full((n, n), np.nan)
    sub = net_df[net_df.cond == cond]
    for i, a in enumerate(areas):
        for j, b in enumerate(areas):
            if i >= j:
                continue
            vals = sub[(sub.areaA == a) & (sub.areaB == b)]["net_a_to_b"].values
            if len(vals):
                mat[i, j] = mat[j, i] = np.mean(vals)
    vmax = np.nanmax(np.abs(mat)) if np.any(np.isfinite(mat)) else 1.0
    im = ax.imshow(mat, cmap="RdBu_r", vmin=-vmax, vmax=vmax)
    sig = sig_lookup.get(cond, set())
    for i, a in enumerate(areas):
        for j, b in enumerate(areas):
            if i >= j:
                continue
            key = (a, b) if (a, b) in sig or (b, a) not in sig else (b, a)
            if key in sig:
                ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False,
                                           edgecolor="black", lw=1.6))
                ax.add_patch(plt.Rectangle((i - 0.5, j - 0.5), 1, 1, fill=False,
                                           edgecolor="black", lw=1.6))
    ax.set_xticks(range(n)); ax.set_xticklabels(areas, rotation=90, fontsize=8)
    ax.set_yticks(range(n)); ax.set_yticklabels(areas, fontsize=8)
    ax.set_title(title, fontsize=10)
    cb = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cb.set_label("Net Granger directionality (row -> col)", rotation=270, labelpad=14, fontsize=8)
    fig.text(0.5, -0.02, f"Black outline: p_holm < 0.05 vs zero (session-paired, "
            f"fig06_supp_{cond})", ha="center", fontsize=7, color="0.3")
    out = os.path.join(SVG_DIR, out_stem)
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)
    return out + ".svg"


# ============================================================ supplement: rate-ratio (NB)
def load_rateratio_hit_rates():
    """outputs/population_spk_spk_rateratio_nb/rateratio_hit_rates.csv, already corrected
    (Holm + BH-FDR) by aggregate_population_spk_spk_rateratio_nb.py over the full 13,790-cell
    family (scope x node-pair x lag x condition_group, cells with >=3 sessions). This script
    draws from that already-corrected table; it does not re-run any test."""
    df = pd.read_csv(os.path.join(RATERATIO_DIR, "rateratio_hit_rates.csv"), low_memory=False)
    df = df[df.n_sessions >= MIN_SESSIONS].copy()
    df["node1"] = df.node1_area + "/" + df.node1_func
    df["node2"] = df.node2_area + "/" + df.node2_func
    df["pair"] = df.node1 + " - " + df.node2
    df["holm"] = df.sig_holm.fillna(False).infer_objects(copy=False)
    df["bh"] = df.sig_bh_fdr.fillna(False).infer_objects(copy=False)
    return df


def draw_rateratio_lag_profile(df, out_stem):
    """Panel: rate ratio vs lag for each Holm-Bonferroni-surviving pair, one subplot per pair.
    Distinguishes visually the two patterns the aggregate README already names in words: a pair
    significant across nearly the whole +-200 ms range (shared external drive, not lag-specific
    coupling) versus a pair significant only at the extreme lags (may reflect a real peak sitting
    outside the tested window, or an edge artefact -- reported as ambiguous either way)."""
    holm = df[df.holm]
    pair_keys = sorted(set(zip(holm.condition_group, holm.node1, holm.node2)))
    if not pair_keys:
        pair_keys = [("(none)", "-", "-")]

    fig, axes = plt.subplots(1, len(pair_keys), figsize=(4.0 * len(pair_keys), 3.0),
                             squeeze=False)
    axes = axes[0]
    for ax, (cg, n1, n2) in zip(axes, pair_keys):
        sub = df[(df.condition_group == cg) & (df.node1 == n1) & (df.node2 == n2)] \
            .sort_values("lag_ms")
        if sub.empty:
            ax.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax.transAxes)
            continue
        n_lags = len(sub)
        frac_bh = sub.bh.mean()
        ax.plot(sub.lag_ms, sub.median_rate_ratio, color="0.35", lw=1.0, zorder=1)
        ns = sub[~sub.bh]
        bh_only = sub[sub.bh & ~sub.holm]
        holm_pts = sub[sub.holm]
        ax.scatter(ns.lag_ms, ns.median_rate_ratio, s=10, color="0.75", zorder=2)
        ax.scatter(bh_only.lag_ms, bh_only.median_rate_ratio, s=20, color="#FF7F0E",
                   zorder=3, label="BH-FDR only")
        ax.scatter(holm_pts.lag_ms, holm_pts.median_rate_ratio, s=30, color="#D62728",
                   zorder=4, label="Holm-Bonferroni")
        ax.axhline(1.0, color="black", lw=0.6, ls=":")
        ax.axvline(0, color="black", lw=0.5, ls=":")
        pattern = "flat" if frac_bh >= FLAT_FRAC_THRESH else "boundary-clipped"
        ax.set_title(f"{n1} $\\rightarrow$ {n2}\n{cg}, BH at {frac_bh:.0%} of {n_lags} lags "
                    f"({pattern})", fontsize=7.5)
        ax.set_xlabel("lag (ms)", fontsize=7)
        ax.tick_params(labelsize=6)
    axes[0].set_ylabel("median rate ratio (session-pooled)", fontsize=7)
    axes[0].legend(fontsize=6, frameon=False, loc="best")
    fig.suptitle("Rate-ratio lag profile, negative-binomial model -- Holm-Bonferroni survivor "
                "pairs", fontsize=9, y=1.06)
    fig.text(0.5, -0.06, "A pair significant at most tested lags is more consistent with both "
            "populations tracking a shared, slowly-varying context (fixation, stimulus "
            "presence) than with a lag-specific coupling, which should instead peak near a "
            "small number of adjacent lags.", ha="center", fontsize=6.5, color="0.3", wrap=True)
    out = os.path.join(SVG_DIR, out_stem)
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)
    return out + ".svg"


def _node_positions(nodes):
    """Evenly spaced points on a circle, nodes ordered by (AREA_ORDER, FUNC_GROUP_ORDER)."""
    def sort_key(n):
        area, func = n.rsplit("/", 1)   # "V3a/d" itself contains "/", so split from the right
        ai = AREA_ORDER.index(area) if area in AREA_ORDER else len(AREA_ORDER)
        fi = FUNC_GROUP_ORDER.index(func) if func in FUNC_GROUP_ORDER else len(FUNC_GROUP_ORDER)
        return (ai, fi)
    ordered = sorted(nodes, key=sort_key)
    n = len(ordered)
    pos = {}
    for i, node in enumerate(ordered):
        theta = 2 * np.pi * i / max(n, 1)
        pos[node] = (np.cos(theta), np.sin(theta))
    return pos, ordered


def draw_rateratio_network(df, cg, out_stem, title):
    """One condition group's BH-significant (area, functional_type) pairs as a circular graph.
    Edge width = fraction of tested lags reaching BH-FDR significance for that pair (wide =
    flat = shared-context-like, per draw_rateratio_lag_profile's same logic). Edge colour =
    mean rate ratio at the significant lags (RdBu_r, matching the Granger network's sign
    convention: red = facilitative, blue = suppressive)."""
    sub = df[df.condition_group == cg]
    edges = []
    for (n1, n2), g in sub.groupby(["node1", "node2"]):
        frac_bh = g.bh.mean()
        if not g.bh.any():
            continue
        mean_rr = g.loc[g.bh, "median_rate_ratio"].mean()
        edges.append((n1, n2, frac_bh, mean_rr, bool(g.holm.any())))
    nodes = sorted(set(n for e in edges for n in e[:2]))
    fig, ax = plt.subplots(figsize=(5.2, 5.2))
    if not nodes:
        ax.text(0.5, 0.5, f"no BH-FDR-significant pairs\n({cg})", ha="center", va="center",
               transform=ax.transAxes, fontsize=9)
        ax.set_axis_off()
        ax.set_title(title, fontsize=10)
        out = os.path.join(SVG_DIR, out_stem)
        fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
        fig.savefig(out + ".svg", bbox_inches="tight")
        plt.close(fig)
        return out + ".svg"

    pos, ordered = _node_positions(nodes)
    vmax = max(abs(e[3]) for e in edges) if edges else 1.0
    vmax = max(vmax - 1.0, 0.05)
    for n1, n2, frac_bh, mean_rr, is_holm in edges:
        x1, y1 = pos[n1]; x2, y2 = pos[n2]
        color = plt.cm.RdBu_r(0.5 + 0.5 * np.clip((mean_rr - 1.0) / vmax, -1, 1))
        ax.plot([x1, x2], [y1, y2], color=color, lw=0.6 + 4.0 * frac_bh,
               alpha=0.55 if not is_holm else 0.9,
               solid_capstyle="round", zorder=2 if not is_holm else 3)
        if is_holm:
            xm, ym = (x1 + x2) / 2, (y1 + y2) / 2
            ax.scatter([xm], [ym], s=14, color="black", zorder=4, marker="D")
    for node in ordered:
        x, y = pos[node]
        area, func = node.rsplit("/", 1)
        ax.scatter([x], [y], s=60, color=FUNC_GROUP_COLORS.get(func, "0.5"),
                  edgecolor="black", linewidth=0.5, zorder=5)
        ax.text(x * 1.14, y * 1.14, node, ha="center", va="center", fontsize=5.5, zorder=6)
    ax.set_xlim(-1.35, 1.35); ax.set_ylim(-1.35, 1.35)
    ax.set_aspect("equal"); ax.set_axis_off()
    ax.set_title(f"{title}\n{len(nodes)} nodes, {len(edges)} BH-significant edges", fontsize=9)
    fig.text(0.5, 0.01, "Edge width: fraction of tested lags BH-significant (wide = flat = "
            "shared-context-like). Black diamond: Holm-Bonferroni survivor. "
            "Red/blue: facilitative/suppressive.", ha="center", fontsize=6.5, color="0.3",
            wrap=True)
    out = os.path.join(SVG_DIR, out_stem)
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)
    return out + ".svg"


def draw_rateratio_heatmap(df, cg, out_stem, title):
    """Full-family view for one condition group: every pair with >=1 BH-significant lag, all
    tested lags on the x-axis. Same visual grammar as the headline's draw_lag_panel (viridis
    hit-rate-style fill, red boxes for Holm, dashed red for BH-only) so the two headline/
    supplement panels read the same way despite different underlying tests."""
    sub = df[df.condition_group == cg]
    sig_pairs = sorted(sub.loc[sub.bh, "pair"].unique())
    lags = sorted(sub.lag_ms.unique())
    if not sig_pairs:
        fig, ax = plt.subplots(figsize=(6, 1.6))
        ax.text(0.5, 0.5, f"no BH-FDR-significant pairs ({cg})", ha="center", va="center",
               transform=ax.transAxes, fontsize=9)
        ax.set_axis_off()
        out = os.path.join(SVG_DIR, out_stem)
        fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
        fig.savefig(out + ".svg", bbox_inches="tight")
        plt.close(fig)
        return out + ".svg"

    mat = np.full((len(sig_pairs), len(lags)), np.nan)
    holm_mask = np.zeros_like(mat, dtype=bool)
    bh_mask = np.zeros_like(mat, dtype=bool)
    for i, pair in enumerate(sig_pairs):
        prow = sub[sub.pair == pair]
        for _, r in prow.iterrows():
            j = lags.index(r.lag_ms)
            mat[i, j] = r.hit_rate
            if r.holm:
                holm_mask[i, j] = True
            elif r.bh:
                bh_mask[i, j] = True

    fig, ax = plt.subplots(figsize=(8.5, 0.16 * len(sig_pairs) + 1.6))
    im = ax.imshow(mat, cmap="viridis", vmin=0, vmax=1, aspect="auto")
    m = 0.09
    for i in range(len(sig_pairs)):
        for j in range(len(lags)):
            if holm_mask[i, j]:
                ax.add_patch(plt.Rectangle((j - 0.5 + m, i - 0.5 + m), 1 - 2 * m, 1 - 2 * m,
                                           fill=False, edgecolor="red", lw=1.4))
            elif bh_mask[i, j]:
                ax.add_patch(plt.Rectangle((j - 0.5 + m, i - 0.5 + m), 1 - 2 * m, 1 - 2 * m,
                                           fill=False, edgecolor="red", lw=0.7, linestyle="--"))
    ax.set_xticks(range(len(lags)))
    ax.set_xticklabels([f"{int(l)}" for l in lags], rotation=90, fontsize=5)
    ax.set_yticks(range(len(sig_pairs)))
    ax.set_yticklabels(sig_pairs, fontsize=5)
    ax.axvline(lags.index(0.0), color="white", lw=0.6, ls=":")
    ax.set_xlabel("lag (ms)", fontsize=7)
    ax.set_title(f"{title} -- {len(sig_pairs)} pairs with >=1 BH-FDR-significant lag "
                f"(of {sub.pair.nunique()} tested)", fontsize=8.5)
    cb = fig.colorbar(im, ax=ax, shrink=0.7, pad=0.01)
    cb.set_label("cross-session hit rate (p<0.05)", rotation=270, labelpad=12, fontsize=7)
    out = os.path.join(SVG_DIR, out_stem)
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)
    return out + ".svg"


def write_rateratio_summary(df):
    """NOT figstats.write() -- same rationale as write_lag_summary: this is a 13,790-cell
    family, already corrected by aggregate_population_spk_spk_rateratio_nb.py. This sidecar
    lists only the survivors and points back to the full table."""
    holm = df[df.holm].sort_values("bh_q")
    bh = df[df.bh].sort_values("bh_q")
    lines = [
        "# Figure 6 rate-ratio supplement -- corrected-family summary", "",
        "Full family (13,790 cells: scope x node-pair x lag x condition_group, cells with "
        ">=3 sessions) is corrected in `aggregate_population_spk_spk_rateratio_nb.py` and "
        "recorded in full at `outputs/population_spk_spk_rateratio_nb/rateratio_hit_rates.csv` "
        "-- THIS file lists only the survivors.", "",
        f"**{len(holm)}/13790 survive Holm-Bonferroni (FWER). {len(bh)}/13790 survive "
        "BH-FDR.**", "",
        "## Holm-Bonferroni survivors", "",
        "| condition_group | scope | node1 | node2 | lag_ms | n_sessions | rate_ratio | "
        "holm_p | bh_q |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for _, r in holm.iterrows():
        lines.append(f"| {r.condition_group} | {r.scope} | {r.node1} | {r.node2} | "
                     f"{r.lag_ms:.0f} | {int(r.n_sessions)} | {r.median_rate_ratio:.3f} | "
                     f"{r.holm_p:.2e} | {r.bh_q:.2e} |")
    with open(os.path.join(SVG_DIR, "fig06_rateratio_summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return len(holm), len(bh)


def main():
    os.makedirs(SVG_DIR, exist_ok=True)
    os.makedirs(NET_OUT_DIR, exist_ok=True)

    # ---- headline: SPK-SPK lead/lag correlation ------------------------------------------
    lag_df = load_lag_hit_rates()
    lag_svg = draw_lag_headline(lag_df, "fig06_lag_headline")
    n_holm, n_bh = write_lag_summary(lag_df)
    print(f"lead/lag headline: {n_holm}/12033 Holm, {n_bh}/12033 BH-FDR "
         f"(full family: outputs/population_spk_spk_lag_corr/lag_hit_rates.csv)")

    # ---- supplement: directed Granger (unchanged result, 2026-08-04/05 build) -------------
    edges_path = os.path.join(NET_OUT_DIR, "edges.csv")
    if os.path.exists(edges_path):
        print(f"reusing existing {edges_path} (delete it to recompute)")
        edges_df = pd.read_csv(edges_path)
        runtime = None
    else:
        edges_df, runtime = compute_edges()

    net_df = net_directionality(edges_df)
    net_df.to_csv(os.path.join(NET_OUT_DIR, "net_directionality.csv"), index=False)
    areas = [a for a in AREA_ORDER if a in set(net_df.areaA) | set(net_df.areaB)]
    print(f"Granger supplement -- areas present: {areas}, sessions: {edges_df.session.nunique()}")

    within_stats = within_condition_stats(net_df, areas)
    delta = delta_stats(net_df, areas)
    all_stats = within_stats["RXRR"] + within_stats["RRRR"] + delta
    all_stats_corrected = correct(list(all_stats))
    write(all_stats, SVG_DIR, "fig06",
         title="Figure 6 supplement -- directed SPK-SPK connectivity (Granger causality)",
         preamble="Granger causality (order='auto' by BIC, max_lag=10, zscore-detrended), "
                  "population-pooled spike rate per area10, full trial window "
                  "(-500..+2593 ms re: p1). Net directionality = x_to_y(A->B) - x_to_y(B->A) "
                  "per session; paired (by session) test vs zero within each condition, and "
                  "RRRR-vs-RXRR paired difference -- three families, corrected together across "
                  "the full directed-edge grid. Unit of inference is session. Demoted to "
                  "supplement 2026-08-06 -- SPK-SPK lead/lag correlation is now the headline.")

    sig_lookup = {}
    for r in all_stats_corrected:
        if r.family in ("fig06_supp_RXRR", "fig06_supp_RRRR", "fig06_supp_delta") \
           and r.p_holm is not None and r.p_holm < 0.05:
            cond = r.family.split("_")[-1]
            ab = r.question.split(" ")[0].split("<->")
            sig_lookup.setdefault(cond, set()).add((ab[0], ab[1]))

    n_sig = {fam: sum(1 for r in all_stats_corrected
                      if r.family == f"fig06_supp_{fam}" and r.p_holm is not None
                      and r.p_holm < 0.05) for fam in ("RXRR", "RRRR", "delta")}
    print(f"Granger supplement significant (p_holm<0.05): RXRR {n_sig['RXRR']}, "
         f"RRRR {n_sig['RRRR']}, delta {n_sig['delta']}")

    delta_df = build_delta_df(net_df)
    net_df_with_delta = pd.concat([net_df, delta_df], ignore_index=True)
    rxrr_svg = draw_network_figure(net_df_with_delta, "RXRR", areas, sig_lookup,
                                   "fig06_rxrr_network", "SPK-SPK directed network, RXRR (p2 omitted)")
    rrrr_svg = draw_network_figure(net_df_with_delta, "RRRR", areas, sig_lookup,
                                   "fig06_rrrr_network", "SPK-SPK directed network, RRRR (p2 real)")
    delta_svg = draw_network_figure(net_df_with_delta, "delta", areas, sig_lookup,
                                    "fig06_delta_network",
                                    "SPK-SPK directed network, RRRR minus RXRR")
    supp_out, sw, sh = assemble([rxrr_svg, rrrr_svg, delta_svg],
                               os.path.join(HERE, "fig06_supp_granger.svg"), ncol=3)
    print(f"assembled Granger supplement -> {supp_out}  {sw:.1f} x {sh:.1f} pt")

    # ---- supplement: rate-ratio (NB), added 2026-08-06 -------------------------------------
    rr_df = load_rateratio_hit_rates()
    rr_n_holm, rr_n_bh = write_rateratio_summary(rr_df)
    print(f"rate-ratio supplement: {rr_n_holm}/13790 Holm, {rr_n_bh}/13790 BH-FDR "
         f"(full family: outputs/population_spk_spk_rateratio_nb/rateratio_hit_rates.csv)")

    profile_svg = draw_rateratio_lag_profile(rr_df, "fig06_rateratio_lag_profile")
    net_svgs, heat_svgs = [], []
    for cg in CG_ORDER:
        net_svgs.append(draw_rateratio_network(rr_df, cg, f"fig06_rateratio_network_{cg}",
                                               f"Rate-ratio network, {cg}"))
        heat_svgs.append(draw_rateratio_heatmap(rr_df, cg, f"fig06_rateratio_heatmap_{cg}",
                                                f"Rate-ratio full family, {cg}"))
    net_row, _, _ = assemble(net_svgs, os.path.join(SVG_DIR, "fig06_rateratio_network_row.svg"),
                             ncol=3)
    heat_stack, _, _ = assemble(heat_svgs,
                                os.path.join(SVG_DIR, "fig06_rateratio_heatmap_stack.svg"),
                                ncol=1)
    rr_supp_out, rrw, rrh = assemble([profile_svg, net_row, heat_stack],
                                     os.path.join(HERE, "fig06_supp_rateratio.svg"), ncol=1)
    print(f"assembled rate-ratio supplement -> {rr_supp_out}  {rrw:.1f} x {rrh:.1f} pt")

    # ---- main figure: headline (row 1) + rate-ratio network + lag profile (row 2), --------
    # ---- added 2026-08-06 per explicit direction: "rate-ratio network is good; and lag ----
    # ---- profile, to be added in the second row of figure 6" ------------------------------
    out, w, h = assemble([lag_svg, net_row, profile_svg], os.path.join(HERE, "fig06.svg"),
                         ncol=1)
    print(f"assembled -> {out}  {w:.1f} x {h:.1f} pt")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "headline_source": os.path.join(LAG_DIR, "lag_hit_rates.csv"),
        "headline_n_holm": n_holm, "headline_n_bh": n_bh, "headline_family_size": 12033,
        "granger_supplement_source": TRIALS_NPZ,
        "granger_areas": areas, "granger_n_sessions": int(edges_df.session.nunique()),
        "granger_conditions": CONDS, "granger_kwargs": GRANGER_KW,
        "granger_n_significant_holm": n_sig,
        "rateratio_supplement_source": os.path.join(RATERATIO_DIR, "rateratio_hit_rates.csv"),
        "rateratio_n_holm": rr_n_holm, "rateratio_n_bh": rr_n_bh,
        "rateratio_family_size": 13790,
        "redesign_note": "2026-08-06: SPK-SPK lead/lag correlation promoted to headline "
                        "(replacing directed Granger, which is fully null); Granger demoted "
                        "to fig06_supp_granger.svg, per user direction. Rate-ratio (NB) "
                        "supplement (fig06_supp_rateratio.svg) added same day, alongside the "
                        "correlation-based headline, not replacing it.",
    }
    with open(os.path.join(NET_OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    with open(os.path.join(SVG_DIR, "fig06_receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)


if __name__ == "__main__":
    main()
