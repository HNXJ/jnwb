r"""
L9 -- Directed LFP-LFP influence: Granger causality and phase-slope index across area x layer
node pairs, per band, stim vs omission, both directions reported separately. This is where the
spec's top-down claim is tested at the field level: predicted alpha/beta feedback dominance
during omission, gamma feedforward during stim.

Reads `canonical_pooling_method` from L0, same gate as L1-L8. Depends on L7 (established the
node/pair framework this reuses) and L8 (established the node-key-collision fix this inherits
directly -- see both READMEs).

METHOD -- REUSES jnwb.connectivity VERBATIM, NOT REIMPLEMENTED
    jnwb.connectivity.granger_spectral: parametric frequency-resolved Granger causality
    (Geweke 1982), already validated elsewhere in this project (omission-signal S10). Its
    n_surrogates trial-shuffle null IS the within-session shuffle null omission-signal S10
    requires -- not built separately here.
    jnwb.connectivity.phase_slope_index: PSI (Nolte et al. 2008), volume-conduction-robust
    (antisymmetric, near-zero for a zero-lag common source), with a genuine per-band jackknife
    z-score (unlike granger_spectral's p_surrogate, which is broadband-derived and shared across
    all bands within one call -- STATED explicitly here and in stats JSON, not silently implied
    per-band, per the omission-signal S10 "state it, don't silently pick a fast setting" norm).

REPRESENTATIVE CHANNEL, NODE KEYS -- INHERITED FROM L8
    One representative channel per (area, layer) node (L6/L8's limitation, not rebuilt). Node
    keys are ALWAYS probe-qualified (f"{area}{layer}_{probe}") -- the same collision L8 found and
    fixed (a bare area+layer key silently collided when one area sits on two different probes in
    one session; in L7 the same bug caused a silent dict-overwrite data loss). Built with the fix
    in place from the start, not discovered again here.

SNR-MATCHED SUBSAMPLING CONTROL -- PER SPEC'S OWN "CAUTION"
    Spec: "GC is sensitive to differing SNR between conditions and areas. Include an SNR-matched
    subsampling control; without it a GC asymmetry is uninterpretable." Implemented literally:
    for each node pair, BOTH conditions are subsampled (without replacement, seeded) down to
    min(n_trials_stim, n_trials_omission) trials before either condition's GC/PSI is computed --
    so a stim-vs-omission difference in directed influence cannot be an artifact of stim having
    more trials (this corpus's conditions are not trial-count-balanced by construction).

DIRECTED ASYMMETRY INDEX
    net = x_to_y - y_to_x (GC, log variance ratio) or the PSI value itself (antisymmetric by
    construction, positive = X leads Y). Both directions (x_to_y, y_to_x) ALSO reported
    separately per spec's "Both directions reported separately," not collapsed into net alone.

CI -- SESSION-BOOTSTRAP WHERE A (area,layer) PAIR RECURS ACROSS SESSIONS, DEGENERATE OTHERWISE
    Node identity for CI purposes is (area, layer) x (area, layer) -- NOT probe-qualified --
    since probe assignment varies session to session (omission-data skill) and the spec's
    "with CI" instruction implies aggregation across replicates, which here means sessions where
    the SAME area-layer pair happens to recur. Same session-bootstrap construction as L2/L3
    (resample SESSION indices, not trials). Most pairs in this corpus's real node coverage will
    have n_sessions=1 for a given identity -- CI is then degenerate (point estimate, zero width),
    stated explicitly, not fabricated.

SCOPE (stated, not hidden)
    House bands. Up to 3 sessions (same node-discovery cap as L8). GC surrogate null uses
    n_surrogates=50 (disclosed, not silently a fast/slow default per omission-signal S10's
    transfer-entropy precedent).

DO NOT CONCLUDE: reports directed asymmetry indices and their significance/CI. Whether the
predicted alpha/beta-omission / gamma-stim feedback pattern holds is left to the manuscript text.

OUTPUT
    L9.svg / L9.png / L9.pdf, L9_stats.json, L9_manifest.json.

TESTS
    --test: synthetic bivariate AR system where X drives Y (Y[t] += 0.6*X[t-2]) but not the
    reverse -- GC and PSI must both recover the correct sign of asymmetry (X->Y > Y->X). A
    symmetric/independent control shows no reliable asymmetry. Plus the SNR-matched-subsampling
    function is checked to equalize trial counts exactly, and a determinism check.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "archive_oneoff"))
sys.path.insert(0, str(REPO / "context" / "figures"))

from _l_lfp_common import PROBE_LETTER_TO_KEY, extract_epoch_trials, git_sha  # noqa: E402
from jnwb.connectivity import granger_spectral, phase_slope_index  # noqa: E402
import figstyle  # noqa: E402

FIG_DIR = Path(__file__).resolve().parent
L0_STATS = REPO / "context" / "figures" / "L0_pooling_reconciliation" / "L0_stats.json"
LAYER_CSV = REPO / "outputs" / "layers" / "channel_layers_all.csv"

SEED = 42
EPOCH_WIN_S = (-0.6, 2.2)
MAX_TRIALS = 40
MAX_SESSIONS = 3
N_SURROGATES = 50
BANDS = {"theta": (4.0, 8.0), "alpha": (8.0, 14.0), "beta": (14.0, 30.0),
          "low_gamma": (30.0, 50.0), "high_gamma": (50.0, 80.0)}
CONDITIONS = {"stim": "RRRR", "omission": "RXRR"}
AREAS = ["V1", "V2", "MT", "MST", "FEF", "PFC"]
N_BOOT = 2000


def require_l0_canonical_method():
    if not L0_STATS.is_file():
        raise RuntimeError(f"L0 has not been run ({L0_STATS} missing) -- run L0 first.")
    stats = json.loads(L0_STATS.read_text())
    if stats.get("canonical_pooling_method") != "a_per_channel_then_pool":
        raise RuntimeError(f"Unexpected canonical_pooling_method in {L0_STATS}")


def load_layer_table() -> pd.DataFrame:
    df = pd.read_csv(LAYER_CSV)
    return df[df.labelled & df.putative_layer.isin(["sup", "deep"])]


def node_key(area: str, layer: str, probe: str) -> str:
    return f"{area}{layer}_{probe}"


def sessions_with_nodes(layer_df: pd.DataFrame, cap=MAX_SESSIONS):
    import jnwb.paths as P
    nwb_dir = Path(P.nwb_dir())
    by_session: dict[str, list] = {}
    for (session, probe, area), g in layer_df.groupby(["session_prefix", "probe", "area10"]):
        if area not in AREAS:
            continue
        if not list(nwb_dir.glob(session + "*.nwb")):
            continue
        for layer in ("sup", "deep"):
            idx = sorted(g.loc[g.putative_layer == layer, "channel_idx"].to_numpy().tolist())
            if not idx:
                continue
            mid = idx[len(idx) // 2]
            by_session.setdefault(session, []).append((area, layer, probe, int(mid)))
    ranked = sorted(by_session.items(), key=lambda kv: -len(kv[1]))
    return [(s, nodes) for s, nodes in ranked if len(nodes) >= 2][:cap]


def extract_node_trials(nwb_path: Path, probe_letter: str, channel_idx: int, condition_code: str):
    """(n_trials, n_samples) raw trials for one representative channel, fs."""
    with h5py.File(nwb_path, "r") as f:
        lfp_key = PROBE_LETTER_TO_KEY[probe_letter]
        trials, fs, n_trials, frac_repaired = extract_epoch_trials(
            f, lfp_key, channel_idx, channel_idx + 1, condition_code, EPOCH_WIN_S, MAX_TRIALS)
    return trials[:, 0, :], fs, frac_repaired


def subsample_to_n(x: np.ndarray, y: np.ndarray, n: int, seed: int):
    """Subsample a trial-paired (X, Y) set (without replacement, seeded, SAME indices for both
    so pairing is preserved) down to exactly n trials. n must be <= x.shape[0]."""
    if x.shape[0] <= n:
        return x, y
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(x.shape[0], size=n, replace=False))
    return x[idx], y[idx]


def snr_match(stim_x, stim_y, omit_x, omit_y, seed: int):
    """The spec's explicit SNR-matched subsampling control: subsample BOTH conditions (each
    condition's X/Y trial-pairing preserved) down to the SAME trial count,
    min(n_trials_stim, n_trials_omission), so a stim-vs-omission GC/PSI difference cannot be an
    artifact of unequal trial counts between conditions."""
    n_use = min(stim_x.shape[0], omit_x.shape[0])
    stim_x_m, stim_y_m = subsample_to_n(stim_x, stim_y, n_use, seed)
    omit_x_m, omit_y_m = subsample_to_n(omit_x, omit_y, n_use, seed + 1)
    return stim_x_m, stim_y_m, omit_x_m, omit_y_m, n_use


def session_bootstrap_ci(values: np.ndarray, n_boot=N_BOOT, seed=SEED):
    n = len(values)
    point = float(np.mean(values))
    if n < 2:
        return point, point, point
    rng = np.random.default_rng(seed)
    draws = np.array([values[rng.integers(0, n, size=n)].mean() for _ in range(n_boot)])
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return point, float(lo), float(hi)


def run():
    require_l0_canonical_method()
    import jnwb.paths as P
    nwb_dir = Path(P.nwb_dir())
    layer_df = load_layer_table()
    sess_nodes = sessions_with_nodes(layer_df)

    stats = {
        "canonical_pooling_method": "a_per_channel_then_pool",
        "l0_source": str(L0_STATS), "layer_source": str(LAYER_CSV),
        "method": "jnwb.connectivity.granger_spectral (Geweke GC, per band, n_surrogates="
                  f"{N_SURROGATES} trial-shuffle null) and jnwb.connectivity.phase_slope_index "
                  "(PSI, per-band jackknife z), on ONE representative channel per (area,layer) "
                  "node. SNR-matched subsampling: both conditions subsampled to equal trial "
                  "count before either is analyzed, per spec's own caution.",
        "caveat_gc_p_is_broadband": "granger_spectral's p_surrogate is derived from the FULL "
                  "broadband GC and is IDENTICAL across every band reported from one call -- it "
                  "is NOT an independent per-band significance test. PSI's per-band z (jackknife)"
                  " IS genuinely per-band. Stated here, not silently implied otherwise.",
        "bands_hz": BANDS, "n_surrogates": N_SURROGATES, "epoch_window_s": list(EPOCH_WIN_S),
        "sessions": {}, "pairs_across_sessions": {},
    }
    manifest = {"analysis_id": "L9", "git_sha": git_sha(), "seed": SEED,
                "n_surrogates": N_SURROGATES, "bands_hz": BANDS,
                "epoch_window_s": list(EPOCH_WIN_S), "sessions_used": {}}

    # pair_identity (area,layer)-(area,layer) -> [{session, band, condition, net, x_to_y, y_to_x}]
    pair_gc_records: dict[str, list] = {}
    plot_rows = []

    for session, nodes in sess_nodes:
        node_desc = [{"area": a, "layer": l, "probe": p, "representative_channel_idx": c}
                     for a, l, p, c in nodes]
        manifest["sessions_used"][session] = node_desc
        nwb_path = nwb_dir / f"{session}_rec.nwb"
        if not nwb_path.is_file():
            nwb_path = nwb_dir / f"{session}.nwb"

        session_pairs = {}
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a1, l1, p1, c1 = nodes[i]
                a2, l2, p2, c2 = nodes[j]
                key1, key2 = node_key(a1, l1, p1), node_key(a2, l2, p2)
                identity = f"{a1}{l1}-{a2}{l2}"

                try:
                    stim_x, fs, _ = extract_node_trials(nwb_path, p1, c1, CONDITIONS["stim"])
                    stim_y, _, _ = extract_node_trials(nwb_path, p2, c2, CONDITIONS["stim"])
                    omit_x, _, _ = extract_node_trials(nwb_path, p1, c1, CONDITIONS["omission"])
                    omit_y, _, _ = extract_node_trials(nwb_path, p2, c2, CONDITIONS["omission"])
                except Exception as e:
                    session_pairs[f"{key1}|{key2}"] = {"error": str(e)}
                    continue

                m = min(stim_x.shape[0], stim_y.shape[0])
                stim_x, stim_y = stim_x[:m], stim_y[:m]
                m2 = min(omit_x.shape[0], omit_y.shape[0])
                omit_x, omit_y = omit_x[:m2], omit_y[:m2]

                stim_x_f, stim_y_f, omit_x_f, omit_y_f, n_use = snr_match(
                    stim_x, stim_y, omit_x, omit_y, SEED)

                pair_out = {"identity": identity, "n_trials_matched": int(n_use),
                            "node_a": key1, "node_b": key2, "conditions": {}}
                for cond_name, (xx, yy) in [("stim", (stim_x_f, stim_y_f)),
                                              ("omission", (omit_x_f, omit_y_f))]:
                    if xx.shape[0] < 8:
                        pair_out["conditions"][cond_name] = {"error": f"n_trials={xx.shape[0]}<8"}
                        continue
                    gc = granger_spectral(xx, yy, fs, bands=BANDS, n_surrogates=N_SURROGATES,
                                           seed=SEED)
                    psi = phase_slope_index(xx, yy, fs, bands=BANDS, n_surrogates=N_SURROGATES,
                                             seed=SEED)
                    band_out = {}
                    for band in BANDS:
                        gb = gc.per_band[band]
                        pb = psi.per_band[band]
                        band_out[band] = {
                            "gc_x_to_y": gb["value"], "gc_y_to_x": gb["value_reverse"],
                            "gc_net": gb["value"] - gb["value_reverse"],
                            "gc_p_surrogate_broadband": gc.p_x_to_y,
                            "psi_value": pb["value"], "psi_z": pb["z"],
                        }
                        pair_gc_records.setdefault(f"{identity}|{band}|{cond_name}", []).append(
                            {"session": session, "gc_net": band_out[band]["gc_net"]})
                    pair_out["conditions"][cond_name] = {
                        "n_trials": int(xx.shape[0]),
                        "gc_diagnostics_warnings": gc.diagnostics["warnings"],
                        "psi_diagnostics_warnings": psi.diagnostics["warnings"],
                        "bands": band_out,
                    }
                    plot_rows.append({"session": session, "pair": identity, "condition": cond_name,
                                       "gc_net_alpha": band_out["alpha"]["gc_net"],
                                       "gc_net_beta": band_out["beta"]["gc_net"],
                                       "gc_net_high_gamma": band_out["high_gamma"]["gc_net"]})
                session_pairs[f"{key1}|{key2}"] = pair_out

        stats["sessions"][session] = {"nodes": node_desc, "pairs": session_pairs}

    for pkey, records in pair_gc_records.items():
        # A single session can contribute MULTIPLE node-pair instances to the same (area,layer)
        # identity (e.g. sub-V182o_ses-260702 records FEF on two probes, so both the within-probe
        # A pair and the within-probe B pair collapse to identity "FEFsup-FEFdeep"). Bootstrapping
        # over raw records would pseudoreplicate within-session pairs as if they were independent
        # SESSIONS -- exactly the channel-vs-session inflation omission-statistics warns against.
        # Collapse to ONE point estimate per session (mean of that session's own pair instances)
        # BEFORE bootstrapping over genuine session replicates.
        by_session: dict[str, list] = {}
        for r in records:
            by_session.setdefault(r["session"], []).append(r["gc_net"])
        session_means = {s: float(np.mean(v)) for s, v in by_session.items()}
        vals = np.array(list(session_means.values()))
        point, lo, hi = session_bootstrap_ci(vals)
        stats["pairs_across_sessions"][pkey] = {
            "n_sessions": len(session_means), "sessions": sorted(session_means.keys()),
            "n_pair_instances_total": len(records),
            "note_within_session_pooling": "n_pair_instances_total can exceed n_sessions when "
                "one session records the same area on multiple probes -- those instances are "
                "averaged to ONE per-session point estimate before bootstrapping, never treated "
                "as independent session replicates.",
            "gc_net_point": point, "gc_net_ci95_lo": lo, "gc_net_ci95_hi": hi,
            "ci_note": "degenerate (point==lo==hi) when n_sessions<2 -- not fabricated",
        }

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (FIG_DIR / "L9_stats.json").write_text(json.dumps(stats, indent=2, default=str))
    (FIG_DIR / "L9_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    plot_figure(plot_rows)
    return stats


def plot_figure(plot_rows: list):
    figstyle.use_house_style()
    if not plot_rows:
        fig, ax = plt.subplots(figsize=(5, 3))
        ax.text(0.5, 0.5, "no pairs computed", ha="center", va="center")
        figstyle.save(fig, FIG_DIR, "L9")
        fig.savefig(FIG_DIR / "L9.pdf", bbox_inches="tight")
        plt.close(fig)
        return

    df = pd.DataFrame(plot_rows)
    pairs = sorted(df["pair"].unique())
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    bands_shown = [("gc_net_alpha", "alpha"), ("gc_net_beta", "beta"),
                   ("gc_net_high_gamma", "high_gamma")]
    for ax, (col, band_label) in zip(axes, bands_shown):
        x = np.arange(len(pairs))
        width = 0.35
        for offset, cond, color in [(-width / 2, "stim", "#1B7837"), (width / 2, "omission", "#762A83")]:
            vals = []
            for p in pairs:
                sub = df[(df["pair"] == p) & (df["condition"] == cond)]
                vals.append(sub[col].mean() if len(sub) else np.nan)
            ax.bar(x + offset, vals, width=width, color=color, label=cond)
        ax.axhline(0, color="#666666", linewidth=0.7)
        ax.set_xticks(x); ax.set_xticklabels(pairs, rotation=75, fontsize=6, ha="right")
        ax.set_title(f"{band_label}\nGC net (x_to_y - y_to_x)", fontsize=8)
        ax.tick_params(labelsize=6)
    axes[0].legend(fontsize=7)
    axes[0].set_ylabel("GC net (log variance ratio)", fontsize=7)
    fig.suptitle("L9: directed LFP-LFP influence (Granger net asymmetry), SNR-matched trial\n"
                 "counts, per pair (area,layer identity) x band, stim vs omission. "
                 "Do not conclude in-code.", fontsize=8.5, y=0.99)
    fig.subplots_adjust(top=0.80, bottom=0.30)
    figstyle.save(fig, FIG_DIR, "L9")
    fig.savefig(FIG_DIR / "L9.pdf", bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------------------- self-test --

def run_synthetic_selftest():
    """Synthetic bivariate AR system: X is autonomous AR(1); Y is driven by X with a 2-sample
    lag PLUS its own AR(1) dynamics -- so X->Y should be strong, Y->X should be near-zero.
    GC and PSI must both recover the correct SIGN of asymmetry."""
    rng = np.random.default_rng(SEED)
    n_trials, n_times = 60, 800
    fs = 500.0

    def make_driven(seed):
        r = np.random.default_rng(seed)
        x = np.zeros((n_trials, n_times))
        y = np.zeros((n_trials, n_times))
        for t in range(n_trials):
            ex = r.normal(0, 1.0, n_times)
            ey = r.normal(0, 1.0, n_times)
            xs = np.zeros(n_times)
            ys = np.zeros(n_times)
            for k in range(2, n_times):
                xs[k] = 0.5 * xs[k - 1] + ex[k]
                ys[k] = 0.3 * ys[k - 1] + 0.6 * xs[k - 2] + ey[k]
            x[t], y[t] = xs, ys
        return x, y

    x, y = make_driven(1)
    gc = granger_spectral(x, y, fs, bands={"test": (5.0, 100.0)}, n_surrogates=0)
    psi = phase_slope_index(x, y, fs, bands={"test": (5.0, 100.0)}, n_surrogates=0)
    gc_net = gc.per_band["test"]["value"] - gc.per_band["test"]["value_reverse"]
    psi_val = psi.per_band["test"]["value"]
    print(f"driven system: GC x_to_y={gc.per_band['test']['value']:.3f} "
          f"y_to_x={gc.per_band['test']['value_reverse']:.3f} net={gc_net:.3f} "
          f"(want net > 0, X drives Y)")
    print(f"driven system: PSI={psi_val:.4f} (want > 0, X leads Y)")
    assert gc_net > 0.05, f"expected positive GC net asymmetry (X->Y > Y->X), got {gc_net:.3f}"
    assert psi_val > 0, f"expected positive PSI (X leads Y), got {psi_val:.4f}"
    print("PASS: GC and PSI both recover the correct direction of asymmetry for a driven system.")

    # Independent control: two unrelated AR(1) processes -- no reliable asymmetry expected.
    r = np.random.default_rng(2)
    xi = np.zeros((n_trials, n_times))
    yi = np.zeros((n_trials, n_times))
    for t in range(n_trials):
        for k in range(1, n_times):
            xi[t, k] = 0.5 * xi[t, k - 1] + r.normal()
            yi[t, k] = 0.5 * yi[t, k - 1] + r.normal()
    gc_i = granger_spectral(xi, yi, fs, bands={"test": (5.0, 100.0)}, n_surrogates=0)
    net_i = gc_i.per_band["test"]["value"] - gc_i.per_band["test"]["value_reverse"]
    print(f"independent control: GC net={net_i:.3f} (want small in magnitude, well below "
          f"the driven-system net of {gc_net:.3f})")
    assert abs(net_i) < abs(gc_net) * 0.5, (
        f"independent control's |net asymmetry| ({abs(net_i):.3f}) should be well below the "
        f"driven system's ({abs(gc_net):.3f})")
    print("PASS: independent control shows no comparable asymmetry.")

    # SNR-matched subsampling: must equalize trial counts exactly, preserving X/Y pairing.
    stim_a = np.arange(50 * 100).reshape(50, 100).astype(float)
    stim_b = stim_a * 2.0  # paired with stim_a by row index
    omit_a = np.arange(30 * 100).reshape(30, 100).astype(float)
    omit_b = omit_a * 3.0
    sa, sb, oa, ob, n = snr_match(stim_a, stim_b, omit_a, omit_b, SEED)
    assert sa.shape[0] == sb.shape[0] == oa.shape[0] == ob.shape[0] == n == 30, (
        "SNR-match must equalize both conditions to the smaller count")
    assert np.array_equal(sb, sa * 2.0), "SNR-match must preserve X/Y trial pairing within stim"
    assert np.array_equal(ob, oa * 3.0), "SNR-match must preserve X/Y trial pairing within omission"
    print(f"PASS: SNR-matched subsampling equalizes trial counts (50,30) -> ({n},{n}), "
          f"X/Y pairing preserved within each condition.")

    # Determinism.
    gc2 = granger_spectral(x, y, fs, bands={"test": (5.0, 100.0)}, n_surrogates=0)
    assert gc2.per_band["test"]["value"] == gc.per_band["test"]["value"], "determinism check failed"
    sa2, sb2, oa2, ob2, _ = snr_match(stim_a, stim_b, omit_a, omit_b, SEED)
    assert np.array_equal(sa, sa2) and np.array_equal(oa, oa2), "SNR-match determinism failed"
    print("PASS: determinism check.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if args.test:
        run_synthetic_selftest()
        return
    stats = run()
    for pkey, d in stats["pairs_across_sessions"].items():
        print(f"{pkey}: n_sessions={d['n_sessions']} gc_net={d['gc_net_point']:+.3f} "
              f"[{d['gc_net_ci95_lo']:+.3f}, {d['gc_net_ci95_hi']:+.3f}]")


if __name__ == "__main__":
    main()
