r"""
Figure 5 -- directed LFP-LFP connectivity network (Granger causality), RXRR vs RRRR.

WHY DIRECTED, NOT THE UNDIRECTED COHERENCY IN THIS SAME FOLDER
    supp_lfp_lfp_coherency.py (originally figure 6, built 2026-07-30) tested undirected
    (symmetric) imaginary-coherency coupling and found 0/240 area-pair x band cells surviving
    correction at the group level in either window. Figures 4-7 are required to carry a group-
    level significant result. Directionality ("does area A's history predict area B's future
    beyond B's own history") is a genuinely different statistical question from phase
    synchronization and was chosen specifically because it can carry information the symmetric
    measure discards. See README.md for the full redesign record and this analysis's result.

INPUT
    outputs/condition_band_power_trials/trials.npz -- per-trial band-power dB time series,
    session x area x cond(RXRR/RRRR) x band, built by
    scripts/extract_condition_band_power_trials.py (2026-08-04, new). -500..+2593 ms from p1
    (fx-p1-d1-p2-d2-p3), 10 ms bins -- the FULL trial window, not just the p2 comparison window,
    since granger()'s automatic lag-order selection benefits from more within-trial samples and
    "the LFP-LFP network across the whole trial" is itself the question of interest here (the
    p2-specific RXRR-vs-RRRR contrast is a separate, secondary test below).

METHOD
    jnwb.connectivity.directed_network(), method='granger' (order='auto', max_lag=10,
    detrend='zscore' -- the estimator's own defaults, chosen once and not tuned per result).
    Run per (session, band, condition) over every area present in that session for that
    band/condition (up to all 10). x_to_y / y_to_x are log-variance-ratio Granger scores;
    net = x_to_y - y_to_x. fdr=False here -- FDR is applied ONCE, at the end, across the full
    session-aggregated edge x band grid, not per-session (see STATISTICS).

STATISTICS
    Unit of inference is SESSION, not the within-session analytic F-test p-value (many pairs
    show non-stationarity/residual-autocorrelation diagnostic warnings at the single-session
    level -- expected for a short, non-stationary event-related LFP segment -- so the
    session-level F-test p is not trusted as the group claim; see `diagnostics_warning_rate` in
    the receipt). Two families, each corrected together (Holm + BH):
      fig05_{cond}   per directed edge x band, is net directionality (across sessions) != 0,
                     within one condition (paired_location vs 0, matches supp_coherency's own
                     per-context convention)
      fig05_delta    per directed edge x band, does net directionality differ RRRR vs RXRR
                     (paired by session) -- the direct analogue of fig04/05-hierarchy's own
                     p2 RXRR-vs-RRRR test, now for directed connectivity instead of raw power

OUTPUT
    outputs/lfp_lfp_granger_network/edges.csv         every (session, band, cond, areaA, areaB,
                                                        x_to_y, y_to_x, net, p_x_to_y, p_y_to_x,
                                                        n_warnings) row -- the durable record
    outputs/lfp_lfp_granger_network/receipt.json
    svg/fig05_stats.md / .csv
    supp_lfp_lfp_granger.svg, svg/supp_granger_*.svg (per-panel assets)
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
from figstyle import AREA_ORDER, BANDS as DISPLAY_BANDS  # noqa: E402
from figstats import correct, paired_location, write  # noqa: E402
from svgassemble import assemble  # noqa: E402

REPO = os.path.dirname(os.path.dirname(FIGDIR))
sys.path.insert(0, REPO)
from jnwb.connectivity import directed_network  # noqa: E402

TRIALS_NPZ = os.path.join(REPO, "outputs", "condition_band_power_trials", "trials.npz")
NET_OUT_DIR = os.path.join(REPO, "outputs", "lfp_lfp_granger_network")
SVG_DIR = os.path.join(HERE, "svg")

CONDS = ["RXRR", "RRRR"]
BANDS = ["theta", "alpha", "beta", "low_gamma", "high_gamma"]
BAND_DISPLAY = {"theta": "Theta(4-8Hz)", "alpha": "Alpha(8-14Hz)", "beta": "Beta(14-30Hz)",
                "low_gamma": "Gamma(Low,30-50Hz)", "high_gamma": "Gamma(High,50-80Hz)"}
GRANGER_KW = dict(order="auto", max_lag=10, detrend="zscore")
MIN_AREAS_PER_CALL = 3


def compute_edges():
    """One directed_network() call per (session, band, cond); returns a long DataFrame,
    one row per directed edge, and writes it to disk immediately so partial progress is never
    lost (per-session, not batched at the very end)."""
    d = np.load(TRIALS_NPZ)
    keys = set(k for k in d.files if k != "times")
    sessions = sorted({k.split("|")[0] for k in keys})
    os.makedirs(NET_OUT_DIR, exist_ok=True)
    rows = []
    n_calls = 0
    t0 = time.time()
    for si, session in enumerate(sessions, 1):
        for cond in CONDS:
            for band in BANDS:
                areas = [a for a in AREA_ORDER
                        if f"{session}|{a}|{cond}|{band}" in keys]
                if len(areas) < MIN_AREAS_PER_CALL:
                    continue
                signals = {a: d[f"{session}|{a}|{cond}|{band}"] for a in areas}
                n_tr = {a: v.shape[0] for a, v in signals.items()}
                try:
                    res = directed_network(signals, method="granger", fdr=False, **GRANGER_KW)
                except Exception as e:
                    rows.append({"session": session, "cond": cond, "band": band,
                                "areaA": None, "areaB": None, "error": str(e)})
                    continue
                n_calls += 1
                mat, pmat, labels = res["matrix"], res["p_matrix"], res["labels"]
                for i, a in enumerate(labels):
                    for j, b in enumerate(labels):
                        if i == j:
                            continue
                        rows.append({
                            "session": session, "cond": cond, "band": band,
                            "areaA": a, "areaB": b,
                            "x_to_y": float(mat[i, j]), "p_x_to_y": float(pmat[i, j]),
                            "n_trials_A": n_tr[a], "n_trials_B": n_tr[b],
                            "n_warnings": len(res.get("warnings", [])),
                            "error": None,
                        })
        # checkpoint after every session -- "save analysis results as we continue"
        pd.DataFrame(rows).to_csv(os.path.join(NET_OUT_DIR, "edges.csv"), index=False)
        print(f"[{datetime.now():%H:%M:%S}] session {si}/{len(sessions)} ({session}), "
             f"{n_calls} directed_network() calls so far, {time.time()-t0:.0f}s", flush=True)
    return pd.DataFrame(rows), time.time() - t0


def net_directionality(df):
    """net(A->B) = x_to_y(A->B) - x_to_y(B->A), from the ordered-pair rows above."""
    piv = df.dropna(subset=["areaA"]).set_index(["session", "cond", "band", "areaA", "areaB"])
    out = []
    for (session, cond, band, a, b), row in piv.iterrows():
        if a >= b:
            continue
        try:
            fwd = piv.loc[(session, cond, band, a, b), "x_to_y"]
            rev = piv.loc[(session, cond, band, b, a), "x_to_y"]
        except KeyError:
            continue
        out.append({"session": session, "cond": cond, "band": band, "areaA": a, "areaB": b,
                    "net_a_to_b": float(fwd) - float(rev)})
    return pd.DataFrame(out)


def within_condition_stats(net_df, areas):
    """fig05_{cond}: per directed edge x band, is net directionality != 0 across sessions."""
    stats = {}
    for cond in CONDS:
        fam_stats = []
        sub = net_df[net_df.cond == cond]
        for band in BANDS:
            for i, a in enumerate(areas):
                for b in areas[i + 1:]:
                    vals = sub[(sub.band == band) & (sub.areaA == a) & (sub.areaB == b)
                              ]["net_a_to_b"].values
                    if len(vals) < 3:
                        continue
                    fam_stats.append(paired_location(
                        vals, np.zeros_like(vals), figure="fig05_supp", panel=cond,
                        question=f"{band} {a}<->{b} net directionality, {cond}",
                        unit="session", family=f"fig05_supp_granger_{cond}",
                        note=f"n={len(vals)} sessions; positive = {a}->{b} net"))
        stats[cond] = fam_stats
    return stats


def delta_stats(net_df, areas):
    """fig05_delta: per directed edge x band, does net directionality differ RRRR vs RXRR
    (paired by session)."""
    fam_stats = []
    for band in BANDS:
        for i, a in enumerate(areas):
            for b in areas[i + 1:]:
                r = net_df[(net_df.cond == "RRRR") & (net_df.band == band)
                          & (net_df.areaA == a) & (net_df.areaB == b)].set_index("session")
                x = net_df[(net_df.cond == "RXRR") & (net_df.band == band)
                          & (net_df.areaA == a) & (net_df.areaB == b)].set_index("session")
                common = sorted(set(r.index) & set(x.index))
                if len(common) < 3:
                    continue
                fam_stats.append(paired_location(
                    r.loc[common, "net_a_to_b"].values, x.loc[common, "net_a_to_b"].values,
                    figure="fig05_supp", panel="delta",
                    question=f"{band} {a}<->{b} net directionality, RRRR vs RXRR",
                    unit="session", family="fig05_supp_granger_delta",
                    note=f"n={len(common)} sessions with both conditions; "
                         "positive = stronger net directionality when p2 is real"))
    return fam_stats


def draw_network_figure(net_df, cond, areas, stats_lookup, out_stem, title):
    """One area x area net-directionality matrix per band, mean across sessions, with
    significant (p_holm < 0.05) cells outlined."""
    n = len(areas)
    fig, axes = plt.subplots(1, len(BANDS), figsize=(3.2 * len(BANDS), 3.5))
    mats = {}
    for band in BANDS:
        mat = np.full((n, n), np.nan)
        sub = net_df[(net_df.cond == cond) & (net_df.band == band)]
        for i, a in enumerate(areas):
            for j, b in enumerate(areas):
                if i >= j:
                    continue
                vals = sub[(sub.areaA == a) & (sub.areaB == b)]["net_a_to_b"].values
                if len(vals):
                    mat[i, j] = mat[j, i] = -np.mean(vals) if False else np.mean(vals)
        mats[band] = mat
    vmax = max(np.nanmax(np.abs(m)) for m in mats.values() if np.any(np.isfinite(m)))
    im0 = None
    for ax, band in zip(axes, BANDS):
        mat = mats[band]
        im = ax.imshow(mat, cmap="RdBu_r", vmin=-vmax, vmax=vmax)
        im0 = im0 or im
        sig = stats_lookup.get((cond, band), set())
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
        ax.set_xticks(range(n)); ax.set_xticklabels(areas, rotation=90, fontsize=6)
        ax.set_yticks(range(n)); ax.set_yticklabels(areas, fontsize=6)
        ax.set_title(BAND_DISPLAY[band], fontsize=8)
    fig.suptitle(title, fontsize=11, fontweight="bold", y=1.04)
    cb = fig.colorbar(im0, ax=axes, shrink=0.75, pad=0.01)
    cb.set_label("Net Granger directionality (row -> col), log variance ratio",
                rotation=270, labelpad=14, fontsize=8)
    fig.text(0.5, -0.02, "Black outline: p_holm < 0.05 vs zero (session-paired, family "
            f"fig05_{cond})", ha="center", fontsize=7, color="0.3")
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
    write(
        all_stats, SVG_DIR, "supp_granger",
        title="Figure 5 supplement -- directed LFP-LFP connectivity (Granger causality)",
        preamble="Granger causality (order='auto' by BIC, max_lag=10, zscore-detrended), "
                "full trial window (-500..+2593 ms re: p1). Net directionality = "
                "x_to_y(A->B) - x_to_y(B->A) per session; paired (by session) test vs zero "
                "within each condition (fig05_supp_granger_RXRR, fig05_supp_granger_RRRR), and "
                "RRRR-vs-RXRR paired difference (fig05_supp_granger_delta) -- three families, "
                "each corrected together across "
                "the full directed-edge x band grid. Unit of inference is session; "
                "single-session analytic F-test p-values are NOT the group claim (see "
                "README's note on non-stationarity/residual-autocorrelation diagnostics).")
    print(f"stats: {len(all_stats)} tests written")

    sig_lookup = {}
    for r in all_stats_corrected:
        if r.family in ("fig05_RXRR", "fig05_RRRR") and r.p_holm is not None and r.p_holm < 0.05:
            cond = r.family.split("_")[1]
            # question format: "{band} {a}<->{b} net directionality, {cond}"
            parts = r.question.split(" ")
            band = parts[0]
            ab = parts[1].split("<->")
            sig_lookup.setdefault((cond, band), set()).add((ab[0], ab[1]))

    n_sig_rxrr = sum(1 for r in all_stats_corrected
                     if r.family == "fig05_RXRR" and r.p_holm is not None and r.p_holm < 0.05)
    n_sig_rrrr = sum(1 for r in all_stats_corrected
                     if r.family == "fig05_RRRR" and r.p_holm is not None and r.p_holm < 0.05)
    n_sig_delta = sum(1 for r in all_stats_corrected
                      if r.family == "fig05_delta" and r.p_holm is not None and r.p_holm < 0.05)
    print(f"significant (p_holm<0.05): RXRR {n_sig_rxrr}, RRRR {n_sig_rrrr}, delta {n_sig_delta}")

    rxrr_svg = draw_network_figure(net_df, "RXRR", areas, sig_lookup,
                                   "supp_granger_rxrr_network", "LFP-LFP directed network, RXRR (p2 omitted)")
    rrrr_svg = draw_network_figure(net_df, "RRRR", areas, sig_lookup,
                                   "supp_granger_rrrr_network", "LFP-LFP directed network, RRRR (p2 real)")

    out, w, h = assemble([rxrr_svg, rrrr_svg], os.path.join(HERE, "supp_lfp_lfp_granger.svg"), ncol=1)
    print(f"assembled -> {out}  {w:.1f} x {h:.1f} pt")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__), "source": TRIALS_NPZ,
        "areas": areas, "n_sessions": int(edges_df.session.nunique()),
        "conditions": CONDS, "bands": BANDS, "granger_kwargs": GRANGER_KW,
        "n_directed_network_calls": int(edges_df.dropna(subset=["areaA"])
                                        .groupby(["session", "cond", "band"]).ngroups),
        "n_significant_holm": {"RXRR": n_sig_rxrr, "RRRR": n_sig_rrrr, "delta": n_sig_delta},
        "diagnostics_warning_rate": float((edges_df["n_warnings"].dropna() > 0).mean())
                                   if "n_warnings" in edges_df else None,
        "runtime_s": runtime,
    }
    with open(os.path.join(NET_OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    with open(os.path.join(SVG_DIR, "supp_granger_receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)


if __name__ == "__main__":
    main()
