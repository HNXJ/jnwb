r"""
L7 -- Cross-area power correlation (Fig 6): trial-by-trial band-power correlation across all
area x layer nodes (V1sup, V1deep, ... PFCdeep), stim and omission computed SEPARATELY, never
pooled. Node x node correlation matrix per band per condition + difference matrix
(omission - stim), FDR-corrected significance.

Reads `canonical_pooling_method` from L0, same gate as L1-L6.

NODE DEFINITION AND WHY THIS REUSES L3's INFRASTRUCTURE
    Node = (area, layer) with layer in {sup, deep} -- same restriction L3 already documents
    (mid/unlabelled channels excluded; this corpus's layer labels resolve to sup/mid/deep only,
    not the spec's full sup/granular/deep, stated in L3's README and repeated here). Nodes and
    their per-trial band power reuse the exact same precomputed-TFR-array + channel_layers_all.csv
    infrastructure L3 built (load_tfr, layer_df) -- not rebuilt.

TRIAL-BY-TRIAL, NOT SESSION-POOLED -- AND PER-SESSION, NOT POOLED ACROSS SESSIONS EITHER
    The spec's correlation is explicitly trial-by-trial: each node gets one dB value PER TRIAL
    (log-last: channels-in-node pooled linear, band pooled linear, THEN divided by that trial's
    OWN baseline-window power and log10'd once -- a legitimate per-trial normalization, not an
    average of dB values). Pearson r is computed across the trial-paired vectors within ONE
    session, never across sessions or with sessions pooled together -- per omission-statistics
    ("test within session first, pool after") and because trial pairing across different
    sessions has no meaning. This script reports each qualifying session as ITS OWN node x node
    matrix (not averaged into a single cross-session matrix), consistent with the same
    non-pooling discipline L2/L3/L6 already apply.

MULTIPLICITY
    Per session, per condition: p-values from every node-pair x band correlation are flattened
    into ONE family and Benjamini-Hochberg corrected ONCE (jnwb.StatisticalAnalysis.fdr_correct),
    per omission-statistics ("flatten the whole grid, correct once across the entire family").
    alpha = 0.05, stated in stats JSON. The omission-vs-stim DIFFERENCE matrix reports the
    difference of independently-estimated r values per node pair per band; it does not carry
    its own FDR-corrected significance (no natural null/test for a correlation difference with
    unequal, non-independent samples across the two conditions from the same trials pool without
    a resampling procedure this script does not build) -- reported as a descriptive delta only,
    stated explicitly in the stats JSON, not silently implied significant.

SCOPE (stated, not hidden)
    House bands (theta, alpha, beta, low_gamma, high_gamma). Up to 3 sessions, ranked by node
    coverage (most area x layer nodes with a labelled sup/deep channel set AND a precomputed TFR
    file for both conditions). Node inventory is corpus-limited -- a single session rarely
    carries more than 2-4 areas simultaneously (multi-probe recording, not full 10-area coverage
    per session) -- exact per-session node list recorded in stats JSON, per the spec's own
    acceptance criterion ("Node inventory and any excluded nodes listed in stats JSON").
    Node pairs with mismatched trial counts between the two nodes' TFR files (can happen if
    per-channel repair drops a differing trial count) are excluded and listed, not silently
    truncated.

OUTPUT
    L7.svg / L7.png / L7.pdf, L7_stats.json, L7_manifest.json.

TESTS
    --test: synthetic 4-node trial-level dataset with KNOWN correlation structure (node1-node2
    correlated by construction, node3-node4 independent) -- the correlation matrix and its
    FDR-corrected q-values must recover the correct significant/non-significant pattern. Plus a
    known condition-dependent correlation difference recovered in the difference matrix, and a
    determinism check.
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
import pandas as pd
from scipy import stats as spstats

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "context" / "figures"))

from _l_lfp_common import git_sha  # noqa: E402
from jnwb import StatisticalAnalysis  # noqa: E402
import figstyle  # noqa: E402

FIG_DIR = Path(__file__).resolve().parent
L0_STATS = REPO / "context" / "figures" / "L0_pooling_reconciliation" / "L0_stats.json"
LAYER_CSV = REPO / "outputs" / "layers" / "channel_layers_all.csv"

import jnwb.paths as P  # noqa: E402
TFR_DIR = Path(P.tfr_dir())

FREQS_HZ = np.arange(3, 201, 2)
TIMES_MS = -1000.0 + np.arange(500) * 10.0
BASELINE_WIN_MS = (-400.0, -150.0)
RESPONSE_WIN_MS = {"stim": (0.0, 531.0), "omission": (1031.0, 1562.0)}
CONDITIONS = {"stim": "RRRR", "omission": "RXRR"}
BANDS = {"theta": (4.0, 8.0), "alpha": (8.0, 14.0), "beta": (14.0, 30.0),
          "low_gamma": (30.0, 50.0), "high_gamma": (50.0, 80.0)}
AREAS = ["V1", "V2", "MT", "MST", "FEF", "PFC"]
ALPHA = 0.05
MAX_SESSIONS = 3


def require_l0_canonical_method():
    if not L0_STATS.is_file():
        raise RuntimeError(f"L0 has not been run ({L0_STATS} missing) -- run L0 first.")
    stats = json.loads(L0_STATS.read_text())
    if stats.get("canonical_pooling_method") != "a_per_channel_then_pool":
        raise RuntimeError(f"Unexpected canonical_pooling_method in {L0_STATS}")


def load_layer_table() -> pd.DataFrame:
    df = pd.read_csv(LAYER_CSV)
    return df[df.labelled & df.putative_layer.isin(["sup", "deep"])]


def load_tfr(session: str, probe: str, area: str, condition_code: str):
    path = TFR_DIR / f"{session}-{probe}-{area}-{condition_code}.npz"
    if not path.is_file():
        return None, None
    d = np.load(path)
    return d["power"], d["channels"]


def sessions_with_nodes(layer_df: pd.DataFrame, cap=MAX_SESSIONS):
    """session_prefix -> list of (area, layer, probe, channel_idx array) nodes with both
    conditions' TFR files present. Ranked by node count, capped."""
    by_session: dict[str, list] = {}
    for (session, probe, area), g in layer_df.groupby(["session_prefix", "probe", "area10"]):
        if area not in AREAS:
            continue
        if not all((TFR_DIR / f"{session}-{probe}-{area}-{code}.npz").is_file()
                   for code in CONDITIONS.values()):
            continue
        for layer in ("sup", "deep"):
            idx = g.loc[g.putative_layer == layer, "channel_idx"].to_numpy()
            if len(idx) == 0:
                continue
            by_session.setdefault(session, []).append((area, layer, probe, idx))
    ranked = sorted(by_session.items(), key=lambda kv: -len(kv[1]))
    return [(s, nodes) for s, nodes in ranked if len(nodes) >= 2][:cap]


def node_trial_traces(session: str, nodes: list, condition_code: str):
    """{(area, layer): (n_trials,) per-trial dB array, dict of band -> array} for every node
    that has a loadable TFR file, per band. Returns {node_key: {band: trace}}; also returns
    per-node n_trials for the mismatched-trial-count exclusion check."""
    base_mask = (TIMES_MS >= BASELINE_WIN_MS[0]) & (TIMES_MS <= BASELINE_WIN_MS[1])
    out = {}
    n_trials_by_node = {}
    response_win = RESPONSE_WIN_MS["stim"] if condition_code == CONDITIONS["stim"] else RESPONSE_WIN_MS["omission"]
    resp_mask = (TIMES_MS >= response_win[0]) & (TIMES_MS <= response_win[1])
    for area, layer, probe, ch_idx in nodes:
        power, channels = load_tfr(session, probe, area, condition_code)
        if power is None:
            continue
        mask = np.isin(channels, ch_idx)
        if not np.any(mask):
            continue
        sub = power[:, mask, :, :].mean(axis=1)  # (n_trials, n_freqs, n_times), channel-pooled linear
        node_key = f"{area}{layer}_{probe}"
        n_trials_by_node[node_key] = sub.shape[0]
        band_traces = {}
        for band_name, (flo, fhi) in BANDS.items():
            fmask = (FREQS_HZ >= flo) & (FREQS_HZ < fhi)
            band_t = sub[:, fmask, :].mean(axis=1)  # (n_trials, n_times), band-pooled linear
            baseline = band_t[:, base_mask].mean(axis=1)  # (n_trials,) per-trial baseline
            response = band_t[:, resp_mask].mean(axis=1)  # (n_trials,) per-trial response
            trial_db = 10.0 * np.log10(np.maximum(response, 1e-15) / np.maximum(baseline, 1e-15))
            band_traces[band_name] = trial_db
        out[node_key] = band_traces
    return out, n_trials_by_node


def correlation_matrix(node_traces: dict, n_trials_by_node: dict, band: str):
    """Returns (node_keys, r_matrix, p_matrix, excluded_pairs) for one band, one
    session/condition. r/p are NaN off the computed pairs; diagonal is NaN (not self-tested)."""
    node_keys = sorted(node_traces.keys())
    n = len(node_keys)
    r_mat = np.full((n, n), np.nan)
    p_mat = np.full((n, n), np.nan)
    excluded = []
    for i in range(n):
        for j in range(i + 1, n):
            ki, kj = node_keys[i], node_keys[j]
            xi, xj = node_traces[ki][band], node_traces[kj][band]
            if len(xi) != len(xj):
                excluded.append({"pair": [ki, kj], "band": band,
                                  "reason": f"trial count mismatch ({len(xi)} vs {len(xj)})"})
                continue
            if len(xi) < 5:
                excluded.append({"pair": [ki, kj], "band": band, "reason": f"n_trials={len(xi)}<5"})
                continue
            r, p = spstats.pearsonr(xi, xj)
            r_mat[i, j] = r_mat[j, i] = r
            p_mat[i, j] = p_mat[j, i] = p
    return node_keys, r_mat, p_mat, excluded


def fdr_correct_matrix_family(p_mats_by_band: dict, node_keys: list):
    """Flatten every band's upper-triangle p-value into ONE family, BH-correct once, reshape
    back. per omission-statistics: 'flatten the whole grid, correct once across the entire
    family, then reshape -- correcting per-row/per-band is a different, undeclared family.'"""
    n = len(node_keys)
    iu = np.triu_indices(n, k=1)
    flat_p = []
    index_map = []  # (band, i, j)
    for band, p_mat in p_mats_by_band.items():
        vals = p_mat[iu]
        for (i, j), v in zip(zip(*iu), vals):
            if not np.isnan(v):
                flat_p.append(v)
                index_map.append((band, i, j))
    if not flat_p:
        return {band: np.full_like(p_mat, np.nan) for band, p_mat in p_mats_by_band.items()}
    q_flat = StatisticalAnalysis.fdr_correct(np.array(flat_p))
    q_mats = {band: np.full((n, n), np.nan) for band in p_mats_by_band}
    for (band, i, j), q in zip(index_map, q_flat):
        q_mats[band][i, j] = q_mats[band][j, i] = q
    return q_mats


def run():
    require_l0_canonical_method()
    layer_df = load_layer_table()
    sess_nodes = sessions_with_nodes(layer_df)

    stats = {
        "canonical_pooling_method": "a_per_channel_then_pool",
        "l0_source": str(L0_STATS), "layer_source": str(LAYER_CSV), "tfr_source_dir": str(TFR_DIR),
        "method": "Pearson r, trial-by-trial per-trial-baselined band power (log-last per trial), "
                  "one node x node matrix PER SESSION per condition per band -- never pooled "
                  "across sessions or trial-concatenated across sessions.",
        "correction": f"Benjamini-Hochberg FDR, flattened across the full node-pair x band "
                      f"family within one session/condition, alpha={ALPHA}.",
        "bands_hz": BANDS, "response_windows_ms": RESPONSE_WIN_MS,
        "baseline_window_ms": list(BASELINE_WIN_MS), "alpha": ALPHA,
        "sessions": {},
    }
    manifest = {"analysis_id": "L7", "git_sha": git_sha(), "max_sessions": MAX_SESSIONS,
                "bands_hz": BANDS, "sessions_used": {}}

    plot_data = {}
    for session, nodes in sess_nodes:
        node_desc = [{"area": a, "layer": l, "probe": p, "n_channels": int(len(idx))}
                     for a, l, p, idx in nodes]
        manifest["sessions_used"][session] = node_desc

        cond_results = {}
        for condition, code in CONDITIONS.items():
            traces, n_trials_by_node = node_trial_traces(session, nodes, code)
            if len(traces) < 2:
                continue
            r_mats, p_mats, excluded_all = {}, {}, []
            for band in BANDS:
                node_keys, r_mat, p_mat, excluded = correlation_matrix(traces, n_trials_by_node, band)
                r_mats[band] = r_mat
                p_mats[band] = p_mat
                excluded_all.extend(excluded)
            q_mats = fdr_correct_matrix_family(p_mats, node_keys)
            cond_results[condition] = {
                "node_keys": node_keys, "r": r_mats, "p": p_mats, "q": q_mats,
                "excluded_pairs": excluded_all,
                "n_trials_by_node": n_trials_by_node,
            }

        if "stim" not in cond_results or "omission" not in cond_results:
            stats["sessions"][session] = {"nodes": node_desc, "note": "insufficient node/trial coverage"}
            continue

        stim_keys = cond_results["stim"]["node_keys"]
        omit_keys = cond_results["omission"]["node_keys"]
        common_keys = [k for k in stim_keys if k in omit_keys]

        session_out = {"nodes": node_desc, "node_keys": common_keys, "conditions": {}}
        diff_out = {}
        for condition in ("stim", "omission"):
            cr = cond_results[condition]
            idx_map = [cr["node_keys"].index(k) for k in common_keys]
            cond_json = {"n_nodes": len(common_keys), "excluded_pairs": cr["excluded_pairs"],
                         "n_trials_by_node": cr["n_trials_by_node"], "bands": {}}
            for band in BANDS:
                r_sub = cr["r"][band][np.ix_(idx_map, idx_map)]
                q_sub = cr["q"][band][np.ix_(idx_map, idx_map)]
                n_sig = int(np.nansum(q_sub[np.triu_indices(len(common_keys), k=1)] < ALPHA))
                n_tested = int(np.sum(~np.isnan(q_sub[np.triu_indices(len(common_keys), k=1)])))
                cond_json["bands"][band] = {
                    "r_matrix": r_sub.tolist(), "q_matrix": q_sub.tolist(),
                    "n_pairs_tested": n_tested, "n_pairs_significant_q_lt_alpha": n_sig,
                }
            session_out["conditions"][condition] = cond_json

        for band in BANDS:
            r_stim = np.array(session_out["conditions"]["stim"]["bands"][band]["r_matrix"])
            r_omit = np.array(session_out["conditions"]["omission"]["bands"][band]["r_matrix"])
            diff_out[band] = (r_omit - r_stim).tolist()
        session_out["difference_matrix_omission_minus_stim"] = {
            "node_keys": common_keys, "bands": diff_out,
            "note": "descriptive delta of independently-estimated r values; NOT independently "
                    "FDR-corrected (no resampling null built for the difference itself) -- see "
                    "module docstring MULTIPLICITY section.",
        }
        stats["sessions"][session] = session_out
        plot_data[session] = session_out

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (FIG_DIR / "L7_stats.json").write_text(json.dumps(stats, indent=2, default=str))
    (FIG_DIR / "L7_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    plot_figure(plot_data)
    return stats


def plot_figure(plot_data: dict):
    figstyle.use_house_style()
    sessions = list(plot_data.keys())
    if not sessions:
        fig, ax = plt.subplots(figsize=(5, 3))
        ax.text(0.5, 0.5, "no sessions with >=2 nodes in both conditions", ha="center", va="center")
        figstyle.save(fig, FIG_DIR, "L7")
        fig.savefig(FIG_DIR / "L7.pdf", bbox_inches="tight")
        plt.close(fig)
        return

    band_names = list(BANDS.keys())
    n_rows = len(sessions)
    n_cols = len(band_names) + 1  # + one difference-matrix column (high_gamma band, as example)
    fig = plt.figure(figsize=(2.5 * n_cols + 1.0, 2.5 * n_rows + 0.6))
    gs = fig.add_gridspec(n_rows, n_cols + 2, width_ratios=[1] * n_cols + [0.08, 0.08],
                           wspace=0.55, hspace=0.5)
    axes = np.empty((n_rows, n_cols), dtype=object)
    for ri in range(n_rows):
        for ci in range(n_cols):
            axes[ri, ci] = fig.add_subplot(gs[ri, ci])

    for ri, session in enumerate(sessions):
        d = plot_data[session]
        keys = d["node_keys"]
        for ci, band in enumerate(band_names):
            ax = axes[ri][ci]
            r = np.array(d["conditions"]["stim"]["bands"][band]["r_matrix"])
            im = ax.imshow(r, cmap="RdBu_r", vmin=-1, vmax=1)
            ax.set_xticks(range(len(keys))); ax.set_xticklabels(keys, rotation=90, fontsize=5)
            ax.set_yticks(range(len(keys))); ax.set_yticklabels(keys, fontsize=5)
            if ri == 0:
                ax.set_title(f"{band}\n(stim r)", fontsize=7)
            if ci == 0:
                ax.set_ylabel(session.replace("sub-", ""), fontsize=6.5)
        ax_d = axes[ri][-1]
        diff = np.array(d["difference_matrix_omission_minus_stim"]["bands"]["high_gamma"])
        im2 = ax_d.imshow(diff, cmap="PuOr_r", vmin=-2, vmax=2)
        ax_d.set_xticks(range(len(keys))); ax_d.set_xticklabels(keys, rotation=90, fontsize=5)
        ax_d.set_yticks(range(len(keys))); ax_d.set_yticklabels(keys, fontsize=5)
        if ri == 0:
            ax_d.set_title("high_gamma\n(omission-stim r)", fontsize=7)

    cax1 = fig.add_subplot(gs[:, -2])
    cax2 = fig.add_subplot(gs[:, -1])
    fig.colorbar(im, cax=cax1, label="Pearson r (stim)")
    fig.colorbar(im2, cax=cax2, label="r delta (omission-stim)")
    fig.suptitle("L7: trial-by-trial cross-area power correlation, per session (rows) x band "
                 "(columns); last column = omission-stim delta at high_gamma. Do not conclude "
                 "in-code.", fontsize=9, y=0.995)
    fig.subplots_adjust(top=0.90)
    figstyle.save(fig, FIG_DIR, "L7")
    fig.savefig(FIG_DIR / "L7.pdf", bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------------------- self-test --

def run_synthetic_selftest():
    """4 synthetic nodes, 2 conditions, known trial-level correlation structure:
    node1-node2 strongly correlated in BOTH conditions (r~0.7), node3-node4 independent in both
    (r~0), and node1-node3 correlated ONLY in omission (r~0 stim, r~0.6 omission) -- the
    correlation matrix, its FDR-corrected q-values, and the difference matrix must all recover
    this."""
    rng = np.random.default_rng(0)
    n_trials = 200

    def make_traces(seed):
        r = np.random.default_rng(seed)
        base = r.normal(0, 1, n_trials)
        n1 = base + r.normal(0, 1.0, n_trials)
        n2 = base + r.normal(0, 1.0, n_trials)
        n3 = r.normal(0, 1, n_trials)
        n4 = r.normal(0, 1, n_trials)
        return {"n1": n1, "n2": n2, "n3": n3, "n4": n4}

    def make_traces_with_n1n3(seed, n1n3_corr: bool):
        r = np.random.default_rng(seed)
        base12 = r.normal(0, 1, n_trials)
        n1 = base12 + r.normal(0, 0.55, n_trials)
        n2 = base12 + r.normal(0, 0.55, n_trials)
        if n1n3_corr:
            n3 = n1 * 0.6 + r.normal(0, 0.8, n_trials)
        else:
            n3 = r.normal(0, 1, n_trials)
        n4 = r.normal(0, 1, n_trials)
        return {"n1": n1, "n2": n2, "n3": n3, "n4": n4}

    stim_traces = {k: {"theta": v} for k, v in make_traces_with_n1n3(1, n1n3_corr=False).items()}
    omit_traces = {k: {"theta": v} for k, v in make_traces_with_n1n3(2, n1n3_corr=True).items()}
    n_trials_stub = {k: n_trials for k in stim_traces}

    keys_s, r_stim, p_stim, excl_s = correlation_matrix(stim_traces, n_trials_stub, "theta")
    keys_o, r_omit, p_omit, excl_o = correlation_matrix(omit_traces, n_trials_stub, "theta")
    assert keys_s == keys_o == ["n1", "n2", "n3", "n4"]

    i1, i2, i3, i4 = [keys_s.index(k) for k in ("n1", "n2", "n3", "n4")]
    print(f"stim r(n1,n2)={r_stim[i1,i2]:.2f} r(n3,n4)={r_stim[i3,i4]:.2f} r(n1,n3)={r_stim[i1,i3]:.2f}")
    print(f"omit r(n1,n2)={r_omit[i1,i2]:.2f} r(n3,n4)={r_omit[i3,i4]:.2f} r(n1,n3)={r_omit[i1,i3]:.2f}")
    assert r_stim[i1, i2] > 0.5, "n1-n2 should be strongly correlated in stim"
    assert abs(r_stim[i3, i4]) < 0.25, "n3-n4 should be near-independent in stim"
    assert abs(r_stim[i1, i3]) < 0.25, "n1-n3 should be near-independent in stim (by construction)"
    assert r_omit[i1, i3] > 0.35, "n1-n3 should be correlated in omission (by construction)"

    q_mats = fdr_correct_matrix_family({"theta": p_stim}, keys_s)
    q_stim = q_mats["theta"]
    print(f"q(n1,n2) stim = {q_stim[i1,i2]:.4f} (want < 0.05)  q(n3,n4) stim = {q_stim[i3,i4]:.4f} (want >= 0.05)")
    assert q_stim[i1, i2] < 0.05, "n1-n2 should survive FDR correction in stim"
    assert q_stim[i3, i4] >= 0.05, "n3-n4 should NOT survive FDR correction in stim"
    print("PASS: correlation matrix + FDR correction recover the known significant/non-significant pattern.")

    diff_n1n3 = r_omit[i1, i3] - r_stim[i1, i3]
    print(f"difference (omission-stim) r(n1,n3) = {diff_n1n3:.2f} (want > 0.3, condition-specific coupling)")
    assert diff_n1n3 > 0.3, "difference matrix should recover the condition-specific n1-n3 coupling"
    print("PASS: difference matrix recovers the known condition-dependent correlation change.")

    # Determinism.
    keys_s2, r_stim2, p_stim2, _ = correlation_matrix(stim_traces, n_trials_stub, "theta")
    assert np.array_equal(r_stim, r_stim2, equal_nan=True), "determinism check failed"
    print("PASS: determinism check.")

    # Mismatched-trial-count exclusion guard.
    bad_traces = {"n1": {"theta": np.zeros(50)}, "n2": {"theta": np.zeros(60)}}
    bad_n_trials = {"n1": 50, "n2": 60}
    _, _, _, excl = correlation_matrix(bad_traces, bad_n_trials, "theta")
    assert len(excl) == 1 and "mismatch" in excl[0]["reason"]
    print("PASS: mismatched trial-count pair excluded and listed, not silently truncated.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if args.test:
        run_synthetic_selftest()
        return
    stats = run()
    for session, d in stats["sessions"].items():
        if "conditions" not in d:
            print(f"{session}: {d.get('note')}")
            continue
        n_nodes = len(d["node_keys"])
        n_sig_theta = d["conditions"]["stim"]["bands"]["theta"]["n_pairs_significant_q_lt_alpha"]
        print(f"{session}: n_nodes={n_nodes} nodes={d['node_keys']} "
              f"stim theta n_sig={n_sig_theta}")


if __name__ == "__main__":
    main()
