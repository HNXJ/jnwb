r"""
L8 -- Cross-area coherence: magnitude-squared coherence and phase, all area x layer node pairs,
per band, stim vs omission separately. Reports imaginary coherency ALONGSIDE standard coherence
per spec's own "Critical" instruction: standard coherence is inflated by volume conduction, the
imaginary part is not -- if the two disagree, the effect is conducted, not interacting.

Reads `canonical_pooling_method` from L0, same gate as L1-L7.

NODE DEFINITION -- SAME AS L7, DIFFERENT SIGNAL DOMAIN
    Node = (area, layer) with layer in {sup, deep}, same channel_layers_all.csv restriction L3/L7
    already document. Node inventory (per-session area x layer coverage) is rediscovered here
    rather than imported from L7 because L8 needs RAW time-domain LFP (for coherence), not the
    precomputed power arrays L7's node infrastructure was built around -- TFR .npz files carry
    power only, not the complex/raw signal a cross-spectrum needs.

REPRESENTATIVE CHANNEL -- SAME LIMITATION L6 ALREADY STATES
    One representative channel per node (the MIDDLE of that node's labelled channel_idx list),
    not full-node coverage. Same simplification L6 uses for its area-level representative
    channels, extended here to node (area x layer) granularity. A channel-resolved or
    node-averaged version is a stated, not-yet-built extension -- averaging raw voltage across
    a node's channels before the cross-spectrum was considered and rejected for this pass: even
    within one sup/deep group, per-channel amplitude/phase differences are not accounted for by
    a naive mean, and L0's own dipole-cancellation caution applies to any raw-voltage averaging
    across channels, not only across a full area's depth.

METHOD
    jnwb.spectral.imaginary_coherency reused verbatim for coh_mag_mean (standard,
    magnitude-squared coherence) and icoh_mean / icoh_abs_mean (the volume-conduction-insensitive
    control, per L6). Band-mean PHASE (new, not in imaginary_coherency's return) computed locally
    via the band-averaged complex coherency's own angle -- same Welch/CSD estimator, no new
    signal-processing primitive, just one more read of an intermediate quantity
    imaginary_coherency already computes internally but does not expose.

SCOPE (stated, not hidden)
    Stim (RRRR) and omission (RXRR) separately, per house band. Up to 3 sessions, ranked by node
    coverage (same ranking L7 uses). All node PAIRS within a session (not just adjacent-area
    pairs) -- pair x band coherence matrices per spec's "Output: Pair x band coherence matrices."

DO NOT CONCLUDE: reports coherence, imaginary coherency, and phase per pair per band per
condition. Whether a given pair's coupling is "conducted, not interacting" (spec's own framing)
is left to the manuscript text reading coh_mag vs icoh_abs together, not decided in code.

OUTPUT
    L8.svg / L8.png / L8.pdf, L8_stats.json, L8_manifest.json.

TESTS
    --test: spec's own explicit acceptance test -- a synthetic common (zero-lag) source signal
    must show HIGH standard coherence and NEAR-ZERO imaginary coherency. Plus a genuinely lagged
    common source (both high), independent noise (both low), and a determinism check.
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
from scipy import signal

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "archive_oneoff"))
sys.path.insert(0, str(REPO / "context" / "figures"))

from _l_lfp_common import PROBE_LETTER_TO_KEY, extract_epoch_trials, git_sha  # noqa: E402
from jnwb.spectral import imaginary_coherency, CANONICAL_BANDS  # noqa: E402
import figstyle  # noqa: E402

FIG_DIR = Path(__file__).resolve().parent
L0_STATS = REPO / "context" / "figures" / "L0_pooling_reconciliation" / "L0_stats.json"
LAYER_CSV = REPO / "outputs" / "layers" / "channel_layers_all.csv"

SEED = 42
EPOCH_WIN_S = (-0.6, 2.2)
MAX_TRIALS = 40
MAX_SESSIONS = 3
FREQ_TOLERANCE_BANDS = CANONICAL_BANDS
CONDITIONS = {"stim": "RRRR", "omission": "RXRR"}
AREAS = ["V1", "V2", "MT", "MST", "FEF", "PFC"]


def require_l0_canonical_method():
    if not L0_STATS.is_file():
        raise RuntimeError(f"L0 has not been run ({L0_STATS} missing) -- run L0 first.")
    stats = json.loads(L0_STATS.read_text())
    if stats.get("canonical_pooling_method") != "a_per_channel_then_pool":
        raise RuntimeError(f"Unexpected canonical_pooling_method in {L0_STATS}")


def load_layer_table() -> pd.DataFrame:
    df = pd.read_csv(LAYER_CSV)
    return df[df.labelled & df.putative_layer.isin(["sup", "deep"])]


def sessions_with_nodes(layer_df: pd.DataFrame, cap=MAX_SESSIONS):
    """session -> [(area, layer, probe, representative_channel_idx), ...], ranked by node count,
    restricted to sessions with a real .nwb file (raw LFP needed, unlike L7's TFR-only nodes).

    NODE KEY COLLISION FIX (found on the required visual-inspection pass): the same area can
    appear on TWO DIFFERENT PROBES within one session (confirmed real on sub-V182o_ses-260702,
    which independently records FEF on two probes) -- a bare f"{area}{layer}" key silently
    collided into duplicate node labels with no way to tell which probe's data a matrix row/
    column actually came from. node_key is therefore ALWAYS probe-qualified
    (f"{area}{layer}_{probe}"), never just f"{area}{layer}", even when only one probe covers an
    area in a given session (so keys are consistent across sessions, not conditionally shaped)."""
    import jnwb.paths as P
    nwb_dir = Path(P.nwb_dir())
    by_session: dict[str, list] = {}
    for (session, probe, area), g in layer_df.groupby(["session_prefix", "probe", "area10"]):
        if area not in AREAS:
            continue
        cand = list(nwb_dir.glob(session + "*.nwb"))
        if not cand:
            continue
        for layer in ("sup", "deep"):
            idx = sorted(g.loc[g.putative_layer == layer, "channel_idx"].to_numpy().tolist())
            if not idx:
                continue
            mid = idx[len(idx) // 2]
            by_session.setdefault(session, []).append((area, layer, probe, int(mid)))
    ranked = sorted(by_session.items(), key=lambda kv: -len(kv[1]))
    return [(s, nodes) for s, nodes in ranked if len(nodes) >= 2][:cap]


def node_key(area: str, layer: str, probe: str) -> str:
    return f"{area}{layer}_{probe}"


def band_phase_deg(x: np.ndarray, y: np.ndarray, fs: float, freq_range) -> float:
    """Band-averaged phase of coherency (degrees), from the same Welch/CSD estimator
    imaginary_coherency uses internally -- reads a quantity it already computes but does not
    expose, rather than a new estimator."""
    n = min(len(x), len(y))
    x, y = x[:n], y[:n]
    nperseg = min(n, 1024)
    noverlap = nperseg // 2
    freqs, pxx = signal.welch(x, fs=fs, nperseg=nperseg, noverlap=noverlap)
    _, pyy = signal.welch(y, fs=fs, nperseg=nperseg, noverlap=noverlap)
    _, sxy = signal.csd(x, y, fs=fs, nperseg=nperseg, noverlap=noverlap)
    mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    if not np.any(mask):
        return 0.0
    denom = np.sqrt(np.clip(pxx[mask] * pyy[mask], 1e-30, None))
    coherency = sxy[mask] / denom
    return float(np.degrees(np.angle(np.mean(coherency))))


def node_signal(nwb_path: Path, probe_letter: str, channel_idx: int, condition_code: str):
    with h5py.File(nwb_path, "r") as f:
        lfp_key = PROBE_LETTER_TO_KEY[probe_letter]
        trials, fs, n_trials, frac_repaired = extract_epoch_trials(
            f, lfp_key, channel_idx, channel_idx + 1, condition_code, EPOCH_WIN_S, MAX_TRIALS)
    sig_1d = trials[:, 0, :].reshape(-1)
    return sig_1d, fs, n_trials, frac_repaired


def run():
    require_l0_canonical_method()
    import jnwb.paths as P
    nwb_dir = Path(P.nwb_dir())
    layer_df = load_layer_table()
    sess_nodes = sessions_with_nodes(layer_df)

    stats = {
        "canonical_pooling_method": "a_per_channel_then_pool",
        "l0_source": str(L0_STATS), "layer_source": str(LAYER_CSV),
        "method": "jnwb.spectral.imaginary_coherency (standard coh_mag_mean + imaginary "
                  "icoh_mean/icoh_abs_mean) plus a locally-computed band-averaged phase, on ONE "
                  "representative channel per (area, layer) node, per session, per band, stim "
                  "and omission NEVER pooled. Standard coherence inflated by volume conduction; "
                  "imaginary part is not -- report both, do not conclude in code.",
        "bands_hz": FREQ_TOLERANCE_BANDS, "epoch_window_s": list(EPOCH_WIN_S),
        "max_trials_per_session": MAX_TRIALS, "sessions": {},
    }
    manifest = {"analysis_id": "L8", "git_sha": git_sha(), "seed": SEED,
                "bands_hz": FREQ_TOLERANCE_BANDS, "epoch_window_s": list(EPOCH_WIN_S),
                "max_trials_per_session": MAX_TRIALS, "sessions_used": {}}

    plot_data = {}
    for session, nodes in sess_nodes:
        node_desc = [{"area": a, "layer": l, "probe": p, "representative_channel_idx": c}
                     for a, l, p, c in nodes]
        manifest["sessions_used"][session] = node_desc
        node_keys = [node_key(a, l, p) for a, l, p, c in nodes]

        nwb_path = nwb_dir / f"{session}_rec.nwb"
        if not nwb_path.is_file():
            nwb_path = nwb_dir / f"{session}.nwb"

        cond_out = {}
        for condition, code in CONDITIONS.items():
            sigs, fss, ns, exclusions = {}, {}, {}, []
            for (a, l, p, c), key in zip(nodes, node_keys):
                try:
                    sig, fs, n_trials, frac_rep = node_signal(nwb_path, p, c, code)
                except Exception as e:
                    exclusions.append({"node": key, "reason": str(e)})
                    continue
                sigs[key] = sig
                fss[key] = fs
                ns[key] = n_trials

            n = len(node_keys)
            coh_mag = {b: np.full((n, n), np.nan) for b in FREQ_TOLERANCE_BANDS}
            icoh_abs = {b: np.full((n, n), np.nan) for b in FREQ_TOLERANCE_BANDS}
            icoh_signed = {b: np.full((n, n), np.nan) for b in FREQ_TOLERANCE_BANDS}
            phase_deg = {b: np.full((n, n), np.nan) for b in FREQ_TOLERANCE_BANDS}
            for i in range(n):
                for j in range(i + 1, n):
                    ki, kj = node_keys[i], node_keys[j]
                    if ki not in sigs or kj not in sigs:
                        continue
                    xi, xj, fs = sigs[ki], sigs[kj], fss[ki]
                    m = min(len(xi), len(xj))
                    for band, frange in FREQ_TOLERANCE_BANDS.items():
                        r = imaginary_coherency(xi[:m], xj[:m], fs, frange)
                        coh_mag[band][i, j] = coh_mag[band][j, i] = r["coh_mag_mean"]
                        icoh_abs[band][i, j] = icoh_abs[band][j, i] = r["icoh_abs_mean"]
                        icoh_signed[band][i, j] = icoh_signed[band][j, i] = r["icoh_mean"]
                        ph = band_phase_deg(xi[:m], xj[:m], fs, frange)
                        phase_deg[band][i, j] = phase_deg[band][j, i] = ph

            cond_out[condition] = {
                "node_keys": node_keys, "excluded_nodes": exclusions,
                "n_trials_by_node": ns,
                "bands": {b: {"coh_mag_matrix": coh_mag[b].tolist(),
                               "icoh_abs_matrix": icoh_abs[b].tolist(),
                               "icoh_signed_matrix": icoh_signed[b].tolist(),
                               "phase_deg_matrix": phase_deg[b].tolist()}
                          for b in FREQ_TOLERANCE_BANDS},
            }

        stats["sessions"][session] = {"nodes": node_desc, "node_keys": node_keys,
                                       "conditions": cond_out}
        plot_data[session] = {"node_keys": node_keys, "conditions": cond_out}

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (FIG_DIR / "L8_stats.json").write_text(json.dumps(stats, indent=2, default=str))
    (FIG_DIR / "L8_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    plot_figure(plot_data)
    return stats


def plot_figure(plot_data: dict):
    figstyle.use_house_style()
    sessions = list(plot_data.keys())
    if not sessions:
        fig, ax = plt.subplots(figsize=(5, 3))
        ax.text(0.5, 0.5, "no sessions with >=2 nodes", ha="center", va="center")
        figstyle.save(fig, FIG_DIR, "L8")
        fig.savefig(FIG_DIR / "L8.pdf", bbox_inches="tight")
        plt.close(fig)
        return

    band = "alpha"  # one representative band shown in the grid; all bands are in stats JSON
    n_rows = len(sessions)
    fig = plt.figure(figsize=(9.5, 2.7 * n_rows + 0.6))
    gs = fig.add_gridspec(n_rows, 4, width_ratios=[1, 1, 0.08, 0.08], wspace=0.5, hspace=0.5)

    for ri, session in enumerate(sessions):
        d = plot_data[session]
        keys = d["node_keys"]
        ax_std = fig.add_subplot(gs[ri, 0])
        ax_icoh = fig.add_subplot(gs[ri, 1])
        stim = d["conditions"].get("stim", {}).get("bands", {}).get(band)
        if stim is None:
            continue
        coh = np.array(stim["coh_mag_matrix"])
        icoh = np.array(stim["icoh_abs_matrix"])
        im1 = ax_std.imshow(coh, cmap="viridis", vmin=0, vmax=1)
        im2 = ax_icoh.imshow(icoh, cmap="viridis", vmin=0, vmax=1)
        for ax in (ax_std, ax_icoh):
            ax.set_xticks(range(len(keys))); ax.set_xticklabels(keys, rotation=90, fontsize=5)
            ax.set_yticks(range(len(keys))); ax.set_yticklabels(keys, fontsize=5)
        ax_std.set_ylabel(session.replace("sub-", ""), fontsize=6.5)
        if ri == 0:
            ax_std.set_title(f"{band}\nstandard coh_mag (stim)", fontsize=7)
            ax_icoh.set_title(f"{band}\nicoh_abs_mean (stim)", fontsize=7)

    cax = fig.add_subplot(gs[:, 2])
    fig.colorbar(im1, cax=cax, label="coherence")
    fig.suptitle("L8: cross-area coherence, standard (left) vs imaginary (right), alpha, stim\n"
                 "per session (rows). Gap between the two = zero-lag/volume-conducted "
                 "contribution (see L6).\nDo not conclude in-code.", fontsize=8, y=0.99, va="top")
    fig.subplots_adjust(top=0.82, bottom=0.06)
    figstyle.save(fig, FIG_DIR, "L8")
    fig.savefig(FIG_DIR / "L8.pdf", bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------------------- self-test --

def run_synthetic_selftest():
    """Spec's own explicit acceptance test: a synthetic COMMON SOURCE signal (zero-lag) must
    show HIGH standard coherence and NEAR-ZERO imaginary coherency."""
    rng = np.random.default_rng(SEED)
    fs = 1000.0
    n = 60_000
    freq_range = (8.0, 14.0)

    shared = rng.normal(0, 1.0, n)
    shared = np.convolve(shared, np.ones(5) / 5, mode="same")
    noise_a = rng.normal(0, 0.3, n)
    noise_b = rng.normal(0, 0.3, n)

    # (a) common source, zero lag.
    x_common = shared + noise_a
    y_common = shared + noise_b
    r_common = imaginary_coherency(x_common, y_common, fs, freq_range)
    ph_common = band_phase_deg(x_common, y_common, fs, freq_range)
    print(f"(a) common source: coh_mag={r_common['coh_mag_mean']:.3f} (want high) "
          f"icoh_abs={r_common['icoh_abs_mean']:.4f} (want near-zero) phase={ph_common:.1f} deg")
    assert r_common["coh_mag_mean"] > 0.3, "common-source case should show high standard coherence"
    assert r_common["icoh_abs_mean"] < 0.05, (
        f"common-source (zero-lag) case should show NEAR-ZERO imaginary coherency, "
        f"got {r_common['icoh_abs_mean']:.4f} -- spec's own explicit acceptance test")
    print("PASS: spec's acceptance test (common source -> high coh, near-zero icoh).")

    # (b) genuinely lagged common source -- both should be substantial.
    delay = 15
    x_lag = shared + noise_a
    y_lag = np.roll(shared, delay) + noise_b
    r_lag = imaginary_coherency(x_lag[delay:], y_lag[delay:], fs, freq_range)
    print(f"(b) lagged source: coh_mag={r_lag['coh_mag_mean']:.3f} icoh_abs={r_lag['icoh_abs_mean']:.4f}")
    assert r_lag["coh_mag_mean"] > 0.3 and r_lag["icoh_abs_mean"] > 0.1, (
        "genuinely lagged common source should show both high coherence AND non-trivial "
        "imaginary coherency")
    print("PASS: lagged common source shows non-trivial imaginary coherency (as expected).")

    # (c) independent noise -- both low.
    ia, ib = rng.normal(0, 1, n), rng.normal(0, 1, n)
    r_indep = imaginary_coherency(ia, ib, fs, freq_range)
    print(f"(c) independent: coh_mag={r_indep['coh_mag_mean']:.3f}")
    assert r_indep["coh_mag_mean"] < 0.15, "independent noise should show low standard coherence"
    print("PASS: independent noise shows low coherence.")

    # Determinism.
    r_common2 = imaginary_coherency(x_common, y_common, fs, freq_range)
    ph_common2 = band_phase_deg(x_common, y_common, fs, freq_range)
    assert r_common2 == r_common and ph_common2 == ph_common, "determinism check failed"
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
        print(f"{session}: nodes={d['node_keys']}")


if __name__ == "__main__":
    main()
