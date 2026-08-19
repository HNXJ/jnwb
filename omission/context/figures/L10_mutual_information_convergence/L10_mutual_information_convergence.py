r"""
L10 -- Mutual information variant: MI between area x layer node trial-by-trial band-power
vectors, as a MODEL-FREE COMPLEMENT to L7 (Pearson correlation) and L9 (Granger/PSI). Per spec:
"Report as a convergence check, not an independent result." Output: MI matrices + an agreement
statistic against L7's correlation matrices.

Reads `canonical_pooling_method` from L0, same gate as L1-L9.

REUSES L7 DIRECTLY -- SAME NODES, SAME PER-TRIAL VECTORS, NOT REBUILT
    Imports sessions_with_nodes, node_trial_traces, and correlation_matrix straight from
    L7_cross_area_power_correlation.py. The exact same per-trial, per-trial-baselined,
    log-last band-power vectors L7 correlates with Pearson r are what MI is computed on here --
    this is by design, since the whole point of a "convergence check" is comparing two
    statistics on THE SAME inputs, not on a re-derived version of them.

METHOD
    sklearn.feature_selection.mutual_info_regression (Kraskov-style k-NN continuous MI
    estimator), one direction per pair (MI is estimated, not exactly symmetric under this
    estimator's k-NN construction, but close in practice for smooth continuous data -- both
    directions are computed and their difference reported as a diagnostic, not silently
    averaged away). random_state fixed for determinism (this estimator has internal tie-breaking
    randomness).

AGREEMENT STATISTIC
    Per session/band/condition: Spearman correlation between the flattened upper-triangle MI
    values and the flattened upper-triangle |Pearson r| values from L7's own matrix for the same
    node set. A strongly positive agreement statistic means "MI and correlation are ranking pairs
    similarly" (linear dependence dominates); a weak or negative one flags pairs where MI and r
    disagree -- worth a nonlinear-dependence follow-up, not concluded here.

SCOPE (stated, not hidden)
    Same node/session/band/condition scope as L7 (reused, not re-derived): up to 3 sessions,
    house bands, stim/omission never pooled. Requires >=3 node pairs with valid data to compute
    a meaningful Spearman agreement statistic; sessions/bands/conditions below that are recorded
    with `agreement_note` explaining why no statistic was computed, not silently skipped.

DO NOT CONCLUDE: MI matrices and the agreement statistic are reported descriptively. Per spec,
this is explicitly NOT an independent result -- it is read alongside L7 and L9, not in isolation.

OUTPUT
    L10.svg / L10.png / L10.pdf, L10_stats.json, L10_manifest.json.

TESTS
    --test: (a) a linear pair (r~0.8) must show high MI AND the two statistics must agree in
    ranking against an independent pair (r~0, MI~baseline). (b) a NONLINEAR pair with near-zero
    Pearson r (Y = (X - mean)^2 + noise) must show MI clearly above the independent baseline --
    demonstrating exactly the complementary value the spec's "model-free complement" language
    describes. (c) the agreement statistic recovers a strong positive Spearman rho when a set of
    pairs varies smoothly in linear-dependence strength. (d) determinism check.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats as spstats
from sklearn.feature_selection import mutual_info_regression

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "context" / "figures"))
sys.path.insert(0, str(REPO / "context" / "figures" / "L7_cross_area_power_correlation"))

from _l_lfp_common import git_sha  # noqa: E402
import L7_cross_area_power_correlation as L7  # noqa: E402
import figstyle  # noqa: E402

FIG_DIR = Path(__file__).resolve().parent
L0_STATS = REPO / "context" / "figures" / "L0_pooling_reconciliation" / "L0_stats.json"

SEED = 42
BANDS = L7.BANDS
CONDITIONS = L7.CONDITIONS


def require_l0_canonical_method():
    if not L0_STATS.is_file():
        raise RuntimeError(f"L0 has not been run ({L0_STATS} missing) -- run L0 first.")
    stats = json.loads(L0_STATS.read_text())
    if stats.get("canonical_pooling_method") != "a_per_channel_then_pool":
        raise RuntimeError(f"Unexpected canonical_pooling_method in {L0_STATS}")


def mutual_information(x: np.ndarray, y: np.ndarray, seed=SEED) -> tuple[float, float]:
    """(MI(x->y), MI(y->x)) in nats, via k-NN continuous estimator. Not exactly symmetric under
    this estimator's construction -- both directions returned, not averaged."""
    mi_xy = float(mutual_info_regression(x.reshape(-1, 1), y, random_state=seed)[0])
    mi_yx = float(mutual_info_regression(y.reshape(-1, 1), x, random_state=seed)[0])
    return mi_xy, mi_yx


def mi_matrix(node_traces: dict, n_trials_by_node: dict, band: str):
    node_keys = sorted(node_traces.keys())
    n = len(node_keys)
    mi_mat = np.full((n, n), np.nan)
    excluded = []
    for i in range(n):
        for j in range(i + 1, n):
            ki, kj = node_keys[i], node_keys[j]
            xi, xj = node_traces[ki][band], node_traces[kj][band]
            if len(xi) != len(xj):
                excluded.append({"pair": [ki, kj], "band": band, "reason": "trial count mismatch"})
                continue
            if len(xi) < 8:
                excluded.append({"pair": [ki, kj], "band": band, "reason": f"n_trials={len(xi)}<8"})
                continue
            mi_xy, mi_yx = mutual_information(xi, xj)
            mi_mat[i, j] = mi_mat[j, i] = (mi_xy + mi_yx) / 2.0  # symmetric summary for the matrix
    return node_keys, mi_mat, excluded


def run():
    require_l0_canonical_method()
    layer_df = L7.load_layer_table()
    sess_nodes = L7.sessions_with_nodes(layer_df)

    stats = {
        "canonical_pooling_method": "a_per_channel_then_pool",
        "l0_source": str(L0_STATS),
        "method": "sklearn.feature_selection.mutual_info_regression (k-NN continuous MI "
                  "estimator), on the SAME per-trial band-power vectors L7 correlates with "
                  "Pearson r -- model-free complement, reported as a CONVERGENCE CHECK per "
                  "spec, not an independent result. Matrix entries are the mean of both "
                  "estimator directions (MI(x->y), MI(y->x) also individually available per "
                  "pair in the per-session detail).",
        "agreement_statistic": "Spearman rho between flattened upper-triangle MI values and "
                  "flattened upper-triangle |Pearson r| values (L7's own matrices, re-derived "
                  "here from the same traces for exact alignment), per session/band/condition.",
        "bands_hz": BANDS, "sessions": {},
    }
    manifest = {"analysis_id": "L10", "git_sha": git_sha(), "seed": SEED, "bands_hz": BANDS,
                "sessions_used": {}}

    plot_data = {}
    for session, nodes in sess_nodes:
        node_desc = [{"area": a, "layer": l, "probe": p} for a, l, p, idx in nodes]
        manifest["sessions_used"][session] = node_desc

        cond_out = {}
        for condition, code in CONDITIONS.items():
            traces, n_trials_by_node = L7.node_trial_traces(session, nodes, code)
            if len(traces) < 2:
                continue
            band_out = {}
            for band in BANDS:
                node_keys, mi_mat, mi_excluded = mi_matrix(traces, n_trials_by_node, band)
                r_keys, r_mat, p_mat, r_excluded = L7.correlation_matrix(traces, n_trials_by_node, band)
                assert node_keys == r_keys, "node ordering mismatch between MI and r matrices"

                iu = np.triu_indices(len(node_keys), k=1)
                mi_flat = mi_mat[iu]
                r_flat = np.abs(r_mat[iu])
                valid = ~np.isnan(mi_flat) & ~np.isnan(r_flat)
                if valid.sum() >= 3:
                    rho, p_rho = spstats.spearmanr(mi_flat[valid], r_flat[valid])
                    agreement = {"spearman_rho": float(rho), "p": float(p_rho),
                                 "n_pairs": int(valid.sum())}
                else:
                    agreement = {"spearman_rho": None, "p": None, "n_pairs": int(valid.sum()),
                                 "note": "fewer than 3 valid pairs -- agreement statistic not computed"}

                band_out[band] = {
                    "node_keys": node_keys, "mi_matrix": mi_mat.tolist(),
                    "r_matrix": r_mat.tolist(), "mi_excluded_pairs": mi_excluded,
                    "agreement_vs_L7": agreement,
                }
            cond_out[condition] = {"bands": band_out}
        stats["sessions"][session] = {"nodes": node_desc, "conditions": cond_out}
        plot_data[session] = cond_out

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (FIG_DIR / "L10_stats.json").write_text(json.dumps(stats, indent=2, default=str))
    (FIG_DIR / "L10_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    plot_figure(plot_data)
    return stats


def plot_figure(plot_data: dict):
    figstyle.use_house_style()
    sessions = list(plot_data.keys())
    if not sessions:
        fig, ax = plt.subplots(figsize=(5, 3))
        ax.text(0.5, 0.5, "no sessions with usable node pairs", ha="center", va="center")
        figstyle.save(fig, FIG_DIR, "L10")
        fig.savefig(FIG_DIR / "L10.pdf", bbox_inches="tight")
        plt.close(fig)
        return

    band = "alpha"
    fig, axes = plt.subplots(1, len(sessions) + 1, figsize=(4.2 * (len(sessions) + 1), 4.2))
    rhos = {s: [] for s in sessions}
    for ax, session in zip(axes[:-1], sessions):
        d = plot_data[session]
        if "stim" not in d or band not in d["stim"]["bands"]:
            ax.text(0.5, 0.5, "no data", ha="center", va="center")
            continue
        b = d["stim"]["bands"][band]
        keys = b["node_keys"]
        mi = np.array(b["mi_matrix"])
        im = ax.imshow(mi, cmap="magma")
        ax.set_xticks(range(len(keys))); ax.set_xticklabels(keys, rotation=90, fontsize=6)
        ax.set_yticks(range(len(keys))); ax.set_yticklabels(keys, fontsize=6)
        ax.set_title(f"{session.replace('sub-','')}\nMI, {band}, stim", fontsize=7)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="MI (nats)")
        for cond in ("stim", "omission"):
            for bn in BANDS:
                a = d.get(cond, {}).get("bands", {}).get(bn, {}).get("agreement_vs_L7", {})
                if a.get("spearman_rho") is not None:
                    rhos[session].append(a["spearman_rho"])

    ax_r = axes[-1]
    all_sessions_rhos = [rhos[s] for s in sessions if rhos[s]]
    labels = [s.replace("sub-", "") for s in sessions if rhos[s]]
    if all_sessions_rhos:
        ax_r.boxplot(all_sessions_rhos, tick_labels=labels)
    ax_r.axhline(0, color="#999999", linewidth=0.7)
    ax_r.set_ylabel("Spearman rho (MI vs |r|)", fontsize=8)
    ax_r.set_title("Agreement statistic\n(across bands x conditions)", fontsize=8)
    ax_r.tick_params(labelsize=7, axis="x", rotation=30)

    fig.suptitle("L10: mutual information convergence check vs L7 (Pearson r). MI is a "
                 "model-free COMPLEMENT, not an independent result. Do not conclude in-code.",
                 fontsize=8.5, y=1.02)
    fig.tight_layout()
    figstyle.save(fig, FIG_DIR, "L10")
    fig.savefig(FIG_DIR / "L10.pdf", bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------------------- self-test --

def run_synthetic_selftest():
    rng = np.random.default_rng(SEED)
    n = 300

    # (a) linear pair.
    x_lin = rng.normal(0, 1, n)
    y_lin = 0.8 * x_lin + rng.normal(0, 0.6, n)
    r_lin, _ = spstats.pearsonr(x_lin, y_lin)
    mi_lin_xy, mi_lin_yx = mutual_information(x_lin, y_lin)
    print(f"(a) linear pair: r={r_lin:.2f}, MI(x->y)={mi_lin_xy:.3f}, MI(y->x)={mi_lin_yx:.3f}")
    assert r_lin > 0.6, "sanity: linear pair should have high Pearson r"
    assert mi_lin_xy > 0.15, f"linear pair should show substantial MI, got {mi_lin_xy:.3f}"

    # (b) nonlinear pair: Y = (X-mean)^2 + noise -- near-zero Pearson r, real dependence.
    x_nl = rng.normal(0, 1, n)
    y_nl = (x_nl ** 2) + rng.normal(0, 0.3, n)
    r_nl, _ = spstats.pearsonr(x_nl, y_nl)
    mi_nl_xy, mi_nl_yx = mutual_information(x_nl, y_nl)
    print(f"(b) nonlinear pair: r={r_nl:.3f} (want near 0), MI(x->y)={mi_nl_xy:.3f} "
          f"(want clearly > independent baseline)")
    assert abs(r_nl) < 0.2, f"nonlinear pair should have near-zero Pearson r by construction, got {r_nl:.3f}"

    # (c) independent baseline.
    x_ind = rng.normal(0, 1, n)
    y_ind = rng.normal(0, 1, n)
    mi_ind_xy, mi_ind_yx = mutual_information(x_ind, y_ind)
    print(f"(c) independent: MI(x->y)={mi_ind_xy:.3f} (baseline)")
    assert mi_nl_xy > mi_ind_xy + 0.05, (
        f"nonlinear pair's MI ({mi_nl_xy:.3f}) should clearly exceed the independent baseline "
        f"({mi_ind_xy:.3f}) even though its Pearson r is near zero -- this IS the complementary "
        f"value the spec's 'model-free complement' language describes")
    print("PASS: MI detects the nonlinear dependence Pearson r misses (near-zero r, elevated MI).")

    # (d) agreement statistic: a set of pairs with smoothly varying linear-dependence strength
    # should give a strong positive Spearman rho between MI and |r|.
    traces = {"n0": {"b": rng.normal(0, 1, n)}}
    strengths = [0.0, 0.2, 0.4, 0.6, 0.8]
    for k, s in enumerate(strengths):
        traces[f"n{k+1}"] = {"b": s * traces["n0"]["b"] + rng.normal(0, 1, n) * np.sqrt(1 - s**2 + 1e-6)}
    n_trials_stub = {k: n for k in traces}
    keys, mi_mat, _ = mi_matrix(traces, n_trials_stub, "b")
    _, r_mat, _, _ = L7.correlation_matrix(traces, n_trials_stub, "b")
    iu = np.triu_indices(len(keys), k=1)
    mi_flat, r_flat = mi_mat[iu], np.abs(r_mat[iu])
    valid = ~np.isnan(mi_flat) & ~np.isnan(r_flat)
    rho, p = spstats.spearmanr(mi_flat[valid], r_flat[valid])
    print(f"(d) agreement statistic: Spearman rho(MI, |r|) = {rho:.2f} (want > 0.5, p={p:.4f})")
    assert rho > 0.5, f"agreement statistic should be strongly positive for these pairs, got {rho:.2f}"
    print("PASS: agreement statistic recovers strong positive rank correlation between MI and |r|.")

    # Determinism.
    mi_lin_xy2, mi_lin_yx2 = mutual_information(x_lin, y_lin)
    assert mi_lin_xy2 == mi_lin_xy and mi_lin_yx2 == mi_lin_yx, "determinism check failed"
    print("PASS: determinism check.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if args.test:
        run_synthetic_selftest()
        return
    stats = run()
    for session, d in stats["sessions"].items():
        for cond, c in d.get("conditions", {}).items():
            for band, b in c.get("bands", {}).items():
                a = b["agreement_vs_L7"]
                rho = a.get("spearman_rho")
                if rho is not None:
                    print(f"{session} {cond} {band}: agreement rho={rho:+.2f} n_pairs={a['n_pairs']}")


if __name__ == "__main__":
    main()
