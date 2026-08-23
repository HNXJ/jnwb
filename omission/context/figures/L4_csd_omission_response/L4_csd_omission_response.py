r"""
L4 -- Current source density (CSD) response to omission, sensory areas V1/V2/V4, stim vs
omission side by side.

Per the spec: "This is the most anatomically direct FF/FB discriminator available. If the
latency analysis (L5/S5) returns an ambiguous 'simultaneous' result, this becomes the primary
evidence -- build it to publication quality, not exploratory quality."

HONEST SCOPE STATEMENT -- read before treating this as done
    This build is a correct, real, end-to-end CSD pipeline with a passing sign/localization
    self-test and real corpus data -- but "publication quality" is a bar this project's own
    conventions (context/figures README, omission-figures skill) treat as something that gets
    reached through iteration with Hamm looking at rendered output, not something a single
    autonomous pass can certify on its own. L5 has not been run yet either, so whether L4 needs
    to carry primary-evidence weight is not yet known. Treat this as a solid first build, not a
    final one.

    This corpus's layer labels (outputs/layers/channel_layers_all.csv) resolve to
    superficial/mid/deep only -- NOT the classical 6-layer histological scheme the spec's
    "L1 + L5/6 sink vs L4 sink" language refers to. This script overlays the sup/mid/deep
    boundary (where available for the plotted session) on the depth axis for visual reference,
    but does NOT claim to have localized literal cytoarchitectonic layer 4 -- that would need
    laminar alignment this corpus does not currently carry at that resolution. Stated here and
    in the stats JSON, not left for a reader to assume.

METHOD
    Per area, one representative session (full channel range, not the 32-channel tractability
    cap L0-L2 used -- CSD needs full depth resolution). Raw LFP epoch trials
    ((-0.6, 2.2) s, p1-referenced, same window as L1/L2), artifact-repaired, THEN
    jnwb.spectral.laplacian_reference applied per trial (the same CSD estimator L0 validated
    and used for its own method (d) -- reused, not reimplemented). Trial-averaged (linear mean
    of the signed CSD trace -- no log, CSD is a signed physical quantity, not power). Baseline
    (-0.4, -0.15 s) mean SUBTRACTED (not divided) per channel, removing DC offset without
    discarding sign. Two conditions (stim = RRRR p1-aligned, omission = RXRR p2-aligned) plotted
    side by side per area, same depth axis, diverging colormap with sign labelled explicitly in
    the colorbar (source/red = positive = current leaving the extracellular space; sink/blue =
    negative = current entering it, the standard CSD sign convention).

OUTPUT
    L4.svg / L4.png / L4.pdf, L4_stats.json, L4_manifest.json.

TESTS
    --test: synthetic multi-channel voltage data with a KNOWN sink (negative deflection) injected
    at a specific depth and time -- laplacian_reference must recover a negative CSD deflection
    localized at that channel and time, not smeared or sign-flipped. Plus determinism and a
    shape/NaN guard.
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

from _l_lfp_common import (  # noqa: E402
    csd_reference_trials, extract_epoch_trials, find_probe_for_area, git_sha,
    resolve_area_channel_block,
)
import figstyle  # noqa: E402

FIG_DIR = Path(__file__).resolve().parent
L0_STATS = REPO / "context" / "figures" / "L0_pooling_reconciliation" / "L0_stats.json"
LAYER_CSV = REPO / "outputs" / "layers" / "channel_layers_all.csv"

EPOCH_WIN_S = (-0.6, 2.2)
BASELINE_WIN_S = (-0.4, -0.15)
MAX_TRIALS = 60
CONDITIONS = {"stim": {"code": "RRRR", "zoom_ms": (-300, 900)},
              "omission": {"code": "RXRR", "zoom_ms": (700, 1900)}}
AREAS = ["V1", "V2", "V4"]

# One representative session per area -- see module docstring for why (clean single-area probes,
# full channel range, no cross-area splitting needed for these three).
AREA_SOURCES = {
    "V1": "sub-V198o_ses-230629",
    "V2": "sub-V198o_ses-230629",
    "V4": "sub-V182o_ses-260706",
}


def require_l0_canonical_method():
    if not L0_STATS.is_file():
        raise RuntimeError(f"L0 has not been run ({L0_STATS} missing) -- run L0 first.")
    stats = json.loads(L0_STATS.read_text())
    if stats.get("canonical_pooling_method") != "a_per_channel_then_pool":
        raise RuntimeError(f"Unexpected canonical_pooling_method in {L0_STATS}")


def layer_boundaries(session_prefix: str, probe_letter: str, area: str, ch_lo: int):
    """Approximate sup/mid/deep boundary channel indices (relative to ch_lo) for this
    session/area, if labelled coverage exists -- for visual reference only (see docstring)."""
    if not LAYER_CSV.is_file():
        return {}
    df = pd.read_csv(LAYER_CSV)
    probe_map = {"A": "probe_0_lfp", "B": "probe_1_lfp", "C": "probe_2_lfp", "D": "probe_3_lfp"}
    sub = df[(df.session_prefix == session_prefix) & (df.lfp_key == probe_map[probe_letter]) &
             (df.area10 == area) & df.labelled]
    out = {}
    for layer in ["sup", "mid", "deep"]:
        idx = sub.loc[sub.putative_layer == layer, "channel_idx"]
        if len(idx):
            out[layer] = (int(idx.min()) - ch_lo, int(idx.max()) - ch_lo)
    return out


def area_csd(area: str, max_trials=MAX_TRIALS):
    session_prefix = AREA_SOURCES[area]
    import jnwb.paths as P
    nwb_dir = Path(P.nwb_dir())
    nwb_path = nwb_dir / f"{session_prefix}_rec.nwb"
    if not nwb_path.is_file():
        nwb_path = nwb_dir / f"{session_prefix}.nwb"

    with h5py.File(nwb_path, "r") as f:
        probe_letter = find_probe_for_area(f, area)
        if probe_letter is None:
            raise ValueError(f"Area {area!r} not found in {session_prefix}")
        lfp_key, ch_lo, ch_hi = resolve_area_channel_block(f, probe_letter, area, n_ch=None)
        panels = {}
        for condition, spec in CONDITIONS.items():
            trials, fs, n_trials, frac_repaired = extract_epoch_trials(
                f, lfp_key, ch_lo, ch_hi, spec["code"], EPOCH_WIN_S, max_trials)
            csd = csd_reference_trials(trials)          # (n_trials, n_channels, n_samples)
            mean_csd = csd.mean(axis=0)                  # (n_channels, n_samples), signed, linear
            times_ms = EPOCH_WIN_S[0] * 1000.0 + np.arange(mean_csd.shape[1]) / fs * 1000.0
            base_mask = (times_ms >= BASELINE_WIN_S[0] * 1000.0) & (times_ms <= BASELINE_WIN_S[1] * 1000.0)
            baseline = mean_csd[:, base_mask].mean(axis=1, keepdims=True)
            mean_csd_bs = mean_csd - baseline             # DC-subtract, sign preserved (NOT log)
            panels[condition] = {
                "csd": mean_csd_bs, "times_ms": times_ms, "n_trials": n_trials,
                "n_channels": int(ch_hi - ch_lo), "fraction_repaired": frac_repaired,
            }
        layers = layer_boundaries(session_prefix, probe_letter, area, ch_lo)
    return panels, session_prefix, probe_letter, layers


def run(max_trials=MAX_TRIALS):
    require_l0_canonical_method()
    stats = {
        "publication_quality_disclaimer": (
            "Correct, real CSD pipeline with a passing sign/localization self-test -- NOT yet "
            "reviewed/iterated with Hamm as this project's own figure convention requires "
            "before calling any figure publication-quality. Layer overlay resolves to "
            "superficial/mid/deep only, not literal cytoarchitectonic layer 4."
        ),
        "l0_source": str(L0_STATS), "epoch_window_s": list(EPOCH_WIN_S),
        "baseline_window_s": list(BASELINE_WIN_S), "csd_method": "jnwb.spectral.laplacian_reference "
        "per trial (same estimator validated in L0 method (d)), baseline mean-subtracted (not "
        "logged -- CSD is a signed physical quantity).",
        "panels": {},
    }
    manifest = {"analysis_id": "L4", "git_sha": git_sha(), "epoch_window_s": list(EPOCH_WIN_S),
                "baseline_window_s": list(BASELINE_WIN_S), "max_trials_cap": max_trials,
                "area_sources": AREA_SOURCES}

    all_panels = {}
    layer_info = {}
    for area in AREAS:
        panels, session_prefix, probe_letter, layers = area_csd(area, max_trials)
        all_panels[area] = panels
        layer_info[area] = layers
        for condition, p in panels.items():
            zoom_ms = CONDITIONS[condition]["zoom_ms"]
            zmask = (p["times_ms"] >= zoom_ms[0]) & (p["times_ms"] <= zoom_ms[1])
            csd_zoom = p["csd"][:, zmask]
            lo, hi = np.percentile(csd_zoom, [2, 98])
            stats["panels"][f"{area}|{condition}"] = {
                "area": area, "condition": condition, "session": session_prefix,
                "probe": probe_letter, "n_trials": p["n_trials"], "n_channels": p["n_channels"],
                "fraction_trials_repaired": p["fraction_repaired"],
                "zoom_window_ms": list(zoom_ms),
                "color_limits_p2_p98": [float(lo), float(hi)],
                "layer_boundaries_local_idx": layers,
            }

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (FIG_DIR / "L4_stats.json").write_text(json.dumps(stats, indent=2, default=str))
    (FIG_DIR / "L4_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    plot_grid(all_panels, stats, layer_info)
    return stats


def plot_grid(all_panels: dict, stats: dict, layer_info: dict):
    figstyle.use_house_style()
    n_rows, n_cols = len(AREAS), len(CONDITIONS)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(4.2 * n_cols, 2.6 * n_rows), squeeze=False)

    for ri, area in enumerate(AREAS):
        row_vals = []
        for condition in CONDITIONS:
            p = all_panels[area][condition]
            zoom_ms = CONDITIONS[condition]["zoom_ms"]
            zmask = (p["times_ms"] >= zoom_ms[0]) & (p["times_ms"] <= zoom_ms[1])
            row_vals.append(p["csd"][:, zmask].ravel())
        vlim = float(max(abs(v) for v in np.percentile(np.concatenate(row_vals), [2, 98])))

        for ci, condition in enumerate(CONDITIONS):
            ax = axes[ri][ci]
            p = all_panels[area][condition]
            zoom_ms = CONDITIONS[condition]["zoom_ms"]
            zmask = (p["times_ms"] >= zoom_ms[0]) & (p["times_ms"] <= zoom_ms[1])
            n_ch = p["csd"].shape[0]
            im = ax.pcolormesh(p["times_ms"][zmask], np.arange(n_ch), p["csd"][:, zmask],
                                cmap="RdBu_r", vmin=-vlim, vmax=vlim, shading="auto")
            ax.axvline(0 if condition == "stim" else 1031, color="black", linewidth=0.8,
                       linestyle="--")
            for layer, (lo_ch, hi_ch) in layer_info[area].items():
                ax.axhline(lo_ch, color="#444444", linewidth=0.5, linestyle=":")
                if layer != "deep":
                    ax.text(zoom_ms[0], hi_ch, layer, fontsize=5, va="bottom", color="#444444")
            ax.set_title(f"{area} | {condition}  (n_ch={n_ch}, n_trials={p['n_trials']})",
                         fontsize=7)
            if ri == n_rows - 1:
                ax.set_xlabel("Time from p1 (ms)")
            if ci == 0:
                ax.set_ylabel(f"{area}\nChannel (depth)", fontsize=7)
            if ci == n_cols - 1:
                cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
                cb.set_label("CSD (a.u., baseline-subtracted)\nred=source, blue=sink", fontsize=6)

    fig.suptitle("L4: CSD response, sensory areas, stim vs omission (Laplacian-referenced, "
                 "baseline mean-subtracted -- NOT publication-reviewed yet, see stats JSON)",
                 fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    figstyle.save(fig, FIG_DIR, "L4")
    fig.savefig(FIG_DIR / "L4.pdf")
    plt.close(fig)


# ------------------------------------------------------------------------------- self-test --

def run_synthetic_selftest():
    """Synthetic multi-channel voltage with a KNOWN sink (negative deflection) injected at one
    depth and one time window -- laplacian_reference must recover a negative CSD deflection
    localized at that channel/time, not smeared across depth or sign-flipped."""
    from jnwb.spectral import laplacian_reference
    rng = np.random.default_rng(0)
    n_ch, n_samples = 16, 300
    sink_ch = 8
    sink_t0, sink_t1 = 100, 150

    v = rng.normal(0, 0.02, size=(n_ch, n_samples))
    # A genuine current sink at depth sink_ch: local negative deflection on that channel only,
    # small/no deflection on distant channels (a physically localized sink, not a shared
    # volume-conducted signal -- that distinction is exactly what laplacian_reference tests for).
    v[sink_ch, sink_t0:sink_t1] -= 1.0

    csd = laplacian_reference(v)
    csd_at_sink = csd[sink_ch, sink_t0:sink_t1].mean()
    csd_far = csd[sink_ch - 4, sink_t0:sink_t1].mean()   # 4 channels away -- should be near zero
    print(f"CSD at injected sink channel: {csd_at_sink:.3f} (want << 0)")
    print(f"CSD 4 channels away: {csd_far:.3f} (want ~0, localized not smeared)")
    assert csd_at_sink < -0.3, f"expected a clear negative (sink) CSD deflection, got {csd_at_sink:.3f}"
    assert abs(csd_far) < 0.1, f"sink leaked to a distant channel: {csd_far:.3f}"
    print("PASS: sink recovered with correct sign and localized to the injected depth.")

    # Determinism.
    csd2 = laplacian_reference(v)
    assert np.array_equal(csd, csd2), "determinism check failed"
    print("PASS: determinism check.")

    # Shape/NaN guard.
    degenerate = np.zeros((5, 50))
    csd_deg = laplacian_reference(degenerate)
    assert np.all(np.isfinite(csd_deg)) and csd_deg.shape == degenerate.shape
    print("PASS: degenerate zero-signal input stays finite, shape preserved.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if args.test:
        run_synthetic_selftest()
        return
    stats = run()
    for key, p in stats["panels"].items():
        print(f"{key}: n_trials={p['n_trials']} n_channels={p['n_channels']} "
              f"clim={p['color_limits_p2_p98']}")


if __name__ == "__main__":
    main()
