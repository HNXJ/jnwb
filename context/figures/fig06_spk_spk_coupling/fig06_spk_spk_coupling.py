r"""
Figure 6 -- directed SPK-SPK connectivity network (Granger causality), RXRR vs RRRR.

Second of the three connectivity-modality figures (LFP-LFP fig05, SPK-SPK fig06, LFP-SPK
fig07), same directed-connectivity engine and design as fig05_lfp_lfp_coupling.py -- see that
script's own docstring for the shared statistical rationale (session as unit of inference,
three families per-condition-vs-zero + RRRR-vs-RXRR delta, Holm+BH corrected together).

INPUT
    outputs/condition_spike_trials/trials.npz -- per-trial, per-area10 population spike-rate
    (Hz) time series, session x area x cond(RXRR/RRRR), built by
    scripts/extract_condition_spike_trials.py (2026-08-04, new). Same window (-500..+2593 ms
    re: p1) and 10 ms bins as fig05's LFP input, so the two networks are directly comparable
    node-for-node. Population-pooled per area10 (all units in that area, not per-unit) to match
    fig05's area-level node granularity -- see that extraction script's own docstring.

METHOD
    jnwb.connectivity.directed_network(), method='granger' (order='auto' by BIC, max_lag=10,
    zscore-detrended -- identical settings to fig05, not re-tuned per result).

OUTPUT
    outputs/spk_spk_granger_network/edges.csv, receipt.json
    svg/fig06_stats.md / .csv
    fig06.svg, svg/fig06_*.svg
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
SVG_DIR = os.path.join(HERE, "svg")

CONDS = ["RXRR", "RRRR"]
GRANGER_KW = dict(order="auto", max_lag=10, detrend="zscore")
MIN_AREAS_PER_CALL = 3


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
                    vals, np.zeros_like(vals), figure="fig06", panel=cond,
                    question=f"{a}<->{b} net directionality, {cond}",
                    unit="session", family=f"fig06_{cond}",
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
                figure="fig06", panel="delta",
                question=f"{a}<->{b} net directionality, RRRR vs RXRR",
                unit="session", family="fig06_delta",
                note=f"n={len(common)} sessions with both conditions"))
    return fam_stats


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
    fig.text(0.5, -0.02, f"Black outline: p_holm < 0.05 vs zero (session-paired, fig06_{cond})",
            ha="center", fontsize=7, color="0.3")
    out = os.path.join(SVG_DIR, out_stem)
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)
    return out + ".svg"


def main():
    os.makedirs(SVG_DIR, exist_ok=True)
    os.makedirs(NET_OUT_DIR, exist_ok=True)

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
    print(f"areas present: {areas}")
    print(f"sessions present: {edges_df.session.nunique()}")

    within_stats = within_condition_stats(net_df, areas)
    delta = delta_stats(net_df, areas)
    all_stats = within_stats["RXRR"] + within_stats["RRRR"] + delta

    all_stats_corrected = correct(list(all_stats))
    write(all_stats, SVG_DIR, "fig06",
         title="Figure 6 -- directed SPK-SPK connectivity (Granger causality)",
         preamble="Granger causality (order='auto' by BIC, max_lag=10, zscore-detrended), "
                  "population-pooled spike rate per area10, full trial window "
                  "(-500..+2593 ms re: p1). Net directionality = x_to_y(A->B) - x_to_y(B->A) "
                  "per session; paired (by session) test vs zero within each condition "
                  "(fig06_RXRR, fig06_RRRR), and RRRR-vs-RXRR paired difference (fig06_delta) "
                  "-- three families, corrected together across the full directed-edge grid. "
                  "Unit of inference is session.")

    sig_lookup = {}
    for r in all_stats_corrected:
        if r.family in ("fig06_RXRR", "fig06_RRRR") and r.p_holm is not None and r.p_holm < 0.05:
            cond = r.family.split("_")[1]
            ab = r.question.split(" ")[0].split("<->")
            sig_lookup.setdefault(cond, set()).add((ab[0], ab[1]))

    n_sig = {fam: sum(1 for r in all_stats_corrected
                      if r.family == f"fig06_{fam}" and r.p_holm is not None and r.p_holm < 0.05)
            for fam in ("RXRR", "RRRR")}
    n_sig["delta"] = sum(1 for r in all_stats_corrected
                         if r.family == "fig06_delta" and r.p_holm is not None and r.p_holm < 0.05)
    print(f"significant (p_holm<0.05): RXRR {n_sig['RXRR']}, RRRR {n_sig['RRRR']}, "
         f"delta {n_sig['delta']}")

    rxrr_svg = draw_network_figure(net_df, "RXRR", areas, sig_lookup,
                                   "fig06_rxrr_network", "SPK-SPK directed network, RXRR (p2 omitted)")
    rrrr_svg = draw_network_figure(net_df, "RRRR", areas, sig_lookup,
                                   "fig06_rrrr_network", "SPK-SPK directed network, RRRR (p2 real)")
    out, w, h = assemble([rxrr_svg, rrrr_svg], os.path.join(HERE, "fig06.svg"), ncol=2)
    print(f"assembled -> {out}  {w:.1f} x {h:.1f} pt")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__), "source": TRIALS_NPZ,
        "areas": areas, "n_sessions": int(edges_df.session.nunique()),
        "conditions": CONDS, "granger_kwargs": GRANGER_KW,
        "n_significant_holm": n_sig,
        "diagnostics_warning_rate": float((edges_df["n_warnings"].dropna() > 0).mean())
                                   if "n_warnings" in edges_df else None,
        "runtime_s": runtime,
    }
    with open(os.path.join(NET_OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    with open(os.path.join(SVG_DIR, "fig06_receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)


if __name__ == "__main__":
    main()
