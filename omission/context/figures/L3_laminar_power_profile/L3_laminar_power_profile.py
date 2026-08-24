r"""
L3 -- Laminar power profile: depth x frequency heatmap per area, and a superficial/deep
contrast index per band per area (stim vs omission), with session-bootstrap CI.

Reads `canonical_pooling_method` from L0, same gate as L1/L2.

WHY THIS REUSES PRECOMPUTED TFR ARRAYS, NOT RAW h5py (unlike L0-L2)
    Discovered this run: oa.paths.tfr_dir() (D:/analysis/tfr_arrays) already holds 970
    precomputed per-(session, probe, area, condition) TFR .npz files
    ("{session}-{probe}-{area}-{condition}.npz", keys power (n_trials, n_channels, n_freqs,
    n_times), channels (local probe-index array, depth-ordered, same convention as
    resolve_area_channel_block's local indexing used in L0-L2)) -- same contract documented in
    scripts/archive_oneoff/precompute_tfr_arrays.py's own docstring (freqs = arange(3,201,2),
    times = -1000+arange(500)*10ms). L3 needs FULL per-channel depth resolution (not the
    32-channel tractability window L0-L2 used), so recomputing from raw LFP would be far more
    expensive than loading what already exists -- reuse-over-reinvention, per CLAUDE.md.

LAYER LABELS: outputs/layers/channel_layers_all.csv (session_prefix, lfp_key, channel_idx,
    area10, putative_layer in {sup, mid, deep, na}, labelled). channel_idx uses the same
    local-probe-index convention as the TFR files' `channels` array -- directly joinable, no
    translation needed (confirmed 2026-08-17). Only labelled sup/deep channels are used for the
    contrast index (mid and unlabelled channels excluded, per the project's own layer-coverage
    caveat -- see PROJECT_STATE.md section 5 and omission-signal's spectrolaminar guidance).

METHOD
    Depth x frequency heatmap: ONE representative session per area (most sup+deep-labelled
    channels available), per-CHANNEL (not pooled) log-last dB: power averaged over trials
    (linear) per channel, collapsed to the response-window time bins (linear), divided by that
    channel's own baseline-window power, log10'd once. Real depth resolution -- every channel
    is its own row, not a pooled group.

    Contrast index: per area, band, session with >=1 sup AND >=1 deep labelled channel: pool
    (log-last, L0's method a) the SUP group and the DEEP group separately -- trials then
    channels-within-group, linear, collapsed to the response window, divided by that group's
    baseline, log10 once -- then contrast = sup_dB - deep_dB (a difference of two independently
    log-last-computed group estimates, same construction as L0's own comparison). Session
    contrasts are then session-bootstrapped (same construction as L2 -- resample SESSIONS, not
    trials/channels) for stim and omission separately.

    Canonical FF/FB signature this feeds (per spec): gamma stronger superficial, alpha/beta
    stronger deep. This script reports the contrast index and its CI; it does NOT assert that
    signature is present -- read the numbers.

OUTPUT
    L3.svg / L3.png / L3.pdf, L3_stats.json, L3_manifest.json.

TESTS
    --test: synthetic laminar profile with a KNOWN superficial-gamma / deep-beta signature
    baked in -- the contrast index must recover the correct sign per band. Plus determinism and
    a shape/NaN guard.
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

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "context" / "figures"))

from _l_lfp_common import git_sha  # noqa: E402
import figstyle  # noqa: E402
from jnwb.spectral import CANONICAL_BANDS, to_db  # noqa: E402

FIG_DIR = Path(__file__).resolve().parent
L0_STATS = REPO / "context" / "figures" / "L0_pooling_reconciliation" / "L0_stats.json"
LAYER_CSV = REPO / "outputs" / "layers" / "channel_layers_all.csv"

import jnwb.paths as P  # noqa: E402
TFR_DIR = Path(P.tfr_dir())

FREQS_HZ = np.arange(3, 201, 2)   # matches precompute_tfr_arrays.py's contract
TIMES_MS = -1000.0 + np.arange(500) * 10.0
BASELINE_WIN_MS = (-400.0, -150.0)
RESPONSE_WIN_MS = {"stim": (0.0, 531.0), "omission": (1031.0, 1562.0)}
CONDITIONS = {"stim": "RRRR", "omission": "RXRR"}
BANDS = CANONICAL_BANDS
AREAS = ["V1", "V2", "MT", "MST", "FEF", "PFC"]
SEED = 42
N_BOOT = 2000
MAX_SESSIONS_PER_AREA = 6


def require_l0_canonical_method():
    if not L0_STATS.is_file():
        raise RuntimeError(f"L0 has not been run ({L0_STATS} missing) -- run L0 first.")
    stats = json.loads(L0_STATS.read_text())
    if stats.get("canonical_pooling_method") != "a_per_channel_then_pool":
        raise RuntimeError(f"Unexpected canonical_pooling_method in {L0_STATS}")


def load_layer_table() -> pd.DataFrame:
    df = pd.read_csv(LAYER_CSV)
    return df[df.labelled & df.putative_layer.isin(["sup", "deep"])]


def sessions_with_layers(layer_df: pd.DataFrame, area: str, cap=MAX_SESSIONS_PER_AREA):
    """(session_prefix, probe_letter, n_sup, n_deep) for sessions with >=1 sup AND >=1 deep
    labelled channel in this area AND a precomputed TFR file for both conditions."""
    sub = layer_df[layer_df.area10 == area]
    out = []
    for (session, probe), g in sub.groupby(["session_prefix", "probe"]):
        n_sup = int((g.putative_layer == "sup").sum())
        n_deep = int((g.putative_layer == "deep").sum())
        if n_sup == 0 or n_deep == 0:
            continue
        if not all((TFR_DIR / f"{session}-{probe}-{area}-{code}.npz").is_file()
                   for code in CONDITIONS.values()):
            continue
        out.append((session, probe, n_sup, n_deep))
    out.sort(key=lambda t: -(t[2] + t[3]))
    return out[:cap]


def load_tfr(session: str, probe: str, area: str, condition_code: str):
    path = TFR_DIR / f"{session}-{probe}-{area}-{condition_code}.npz"
    d = np.load(path)
    return d["power"], d["channels"]  # (n_trials, n_channels, n_freqs, n_times), (n_channels,)


def channel_db_grid(power: np.ndarray, response_win_ms):
    """(n_trials, n_channels, n_freqs, n_times) -> per-CHANNEL log-last dB(channel, freq),
    collapsed to response_win_ms. No cross-channel pooling -- this IS the depth axis."""
    pooled = power.mean(axis=0)  # (n_channels, n_freqs, n_times) -- trial pooling, linear
    base_mask = (TIMES_MS >= BASELINE_WIN_MS[0]) & (TIMES_MS <= BASELINE_WIN_MS[1])
    resp_mask = (TIMES_MS >= response_win_ms[0]) & (TIMES_MS <= response_win_ms[1])
    baseline = pooled[:, :, base_mask].mean(axis=2)   # (n_channels, n_freqs)
    response = pooled[:, :, resp_mask].mean(axis=2)   # (n_channels, n_freqs)
    return to_db(np.maximum(response, 1e-15) / np.maximum(baseline, 1e-15))


def group_band_db(power: np.ndarray, channels: np.ndarray, group_channel_idx: np.ndarray,
                   band_hz, response_win_ms):
    """Canonical method (a): trials then channels-within-group pooled (linear), then the
    band's frequency bins pooled (linear), THEN baseline-divided and log10'd once -- log-last
    at both pooling steps, same order as L2."""
    mask = np.isin(channels, group_channel_idx)
    if not np.any(mask):
        return None
    sub = power[:, mask, :, :]                      # (n_trials, n_group_ch, n_freqs, n_times)
    pooled = sub.mean(axis=0).mean(axis=0)           # trials then channels, linear -> (n_freqs, n_times)
    fmask = (FREQS_HZ >= band_hz[0]) & (FREQS_HZ < band_hz[1])
    if not np.any(fmask):
        return None
    band_t = pooled[fmask, :].mean(axis=0)           # band-frequency pooling, linear -> (n_times,)
    base_mask = (TIMES_MS >= BASELINE_WIN_MS[0]) & (TIMES_MS <= BASELINE_WIN_MS[1])
    resp_mask = (TIMES_MS >= response_win_ms[0]) & (TIMES_MS <= response_win_ms[1])
    baseline = band_t[base_mask].mean()
    response = band_t[resp_mask].mean()
    return float(to_db(max(response, 1e-15) / max(baseline, 1e-15)))


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
    layer_df = load_layer_table()

    stats = {
        "canonical_pooling_method": "a_per_channel_then_pool",
        "l0_source": str(L0_STATS), "tfr_source_dir": str(TFR_DIR),
        "layer_source": str(LAYER_CSV),
        "ci_method": "session-level bootstrap on the contrast index, same construction as L2 "
                      f"(n_boot={N_BOOT}, seed={SEED}, 95% percentile). Only sessions with "
                      ">=1 labelled superficial AND >=1 labelled deep channel are used.",
        "bands_hz": BANDS, "response_windows_ms": RESPONSE_WIN_MS,
        "baseline_window_ms": list(BASELINE_WIN_MS),
        "heatmaps": {}, "contrast_index": {},
    }
    manifest = {"analysis_id": "L3", "git_sha": git_sha(), "seed": SEED, "n_bootstrap": N_BOOT,
                "sessions_used": {}}

    heatmap_data = {}
    contrast_data = {}

    for area in AREAS:
        sess_list = sessions_with_layers(layer_df, area)
        manifest["sessions_used"][area] = [
            {"session": s, "probe": p, "n_sup": ns, "n_deep": nd} for s, p, ns, nd in sess_list]
        if not sess_list:
            continue

        # --- depth x frequency heatmap: representative (richest) session, stim condition ---
        rep_session, rep_probe, n_sup, n_deep = sess_list[0]
        power, channels = load_tfr(rep_session, rep_probe, area, CONDITIONS["stim"])
        db_grid = channel_db_grid(power, RESPONSE_WIN_MS["stim"])  # (n_channels, n_freqs)
        heatmap_data[area] = {"db_grid": db_grid, "channels": channels,
                                "session": rep_session, "probe": rep_probe}
        stats["heatmaps"][area] = {
            "session": rep_session, "probe": rep_probe, "condition": "stim",
            "n_channels": int(db_grid.shape[0]), "n_freqs": int(db_grid.shape[1]),
            "color_limits_db_p2_p98": [float(v) for v in np.percentile(db_grid, [2, 98])],
        }

        # --- contrast index per band, per condition, session-bootstrapped ---
        for condition, code in CONDITIONS.items():
            for band_name, band_hz in BANDS.items():
                per_session_contrast = []
                per_session_meta = []
                for session, probe, ns, nd in sess_list:
                    power_c, channels_c = load_tfr(session, probe, area, code)
                    g = layer_df[(layer_df.session_prefix == session) &
                                 (layer_df.probe == probe) & (layer_df.area10 == area)]
                    sup_idx = g.loc[g.putative_layer == "sup", "channel_idx"].to_numpy()
                    deep_idx = g.loc[g.putative_layer == "deep", "channel_idx"].to_numpy()
                    sup_db = group_band_db(power_c, channels_c, sup_idx, band_hz,
                                            RESPONSE_WIN_MS[condition])
                    deep_db = group_band_db(power_c, channels_c, deep_idx, band_hz,
                                             RESPONSE_WIN_MS[condition])
                    if sup_db is None or deep_db is None:
                        continue
                    per_session_contrast.append(sup_db - deep_db)
                    per_session_meta.append({"session": session, "sup_db": sup_db,
                                              "deep_db": deep_db, "n_sup_ch": ns, "n_deep_ch": nd})
                if not per_session_contrast:
                    continue
                vals = np.array(per_session_contrast)
                point, lo, hi = session_bootstrap_ci(vals)
                key = (area, band_name, condition)
                contrast_data[key] = {"point": point, "lo": lo, "hi": hi}
                stats["contrast_index"][f"{area}|{band_name}|{condition}"] = {
                    "area": area, "band": band_name, "condition": condition,
                    "n_sessions": len(per_session_contrast),
                    "sup_minus_deep_db": point, "ci95_lo": lo, "ci95_hi": hi,
                    "per_session": per_session_meta,
                }

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (FIG_DIR / "L3_stats.json").write_text(json.dumps(stats, indent=2, default=str))
    (FIG_DIR / "L3_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    plot_figure(heatmap_data, contrast_data)
    return stats


def plot_figure(heatmap_data: dict, contrast_data: dict):
    figstyle.use_house_style()
    n_areas = len(AREAS)
    fig = plt.figure(figsize=(16, 9))
    gs = fig.add_gridspec(2, n_areas, height_ratios=[1.1, 1.4], hspace=0.55, wspace=0.5)

    for ci, area in enumerate(AREAS):
        ax = fig.add_subplot(gs[0, ci])
        if area not in heatmap_data:
            ax.text(0.5, 0.5, "no layer-\nlabelled data", transform=ax.transAxes, ha="center",
                    va="center", fontsize=7, color="#999999")
            ax.set_title(area, fontsize=8)
            continue
        d = heatmap_data[area]
        grid = d["db_grid"]
        vlim = max(abs(v) for v in np.percentile(grid, [2, 98]))
        im = ax.pcolormesh(FREQS_HZ, np.arange(grid.shape[0]), grid, cmap="RdBu_r",
                            vmin=-vlim, vmax=vlim, shading="auto")
        ax.set_title(f"{area}\n{d['session'].replace('sub-', '')} probe{d['probe']}", fontsize=6.5)
        ax.set_xlabel("Freq (Hz)", fontsize=6)
        if ci == 0:
            ax.set_ylabel("Channel (depth)", fontsize=7)
        ax.tick_params(labelsize=6)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04).ax.tick_params(labelsize=5)

    band_names = list(BANDS.keys())
    ax2 = fig.add_subplot(gs[1, :])
    x = np.arange(len(AREAS))
    width = 0.8 / (len(band_names) * 2)
    for bi, band in enumerate(band_names):
        for cj, (condition, hatch) in enumerate([("stim", None), ("omission", "//")]):
            offset = (bi * 2 + cj - len(band_names)) * width
            vals, los, his = [], [], []
            for area in AREAS:
                key = (area, band, condition)
                if key in contrast_data:
                    d = contrast_data[key]
                    vals.append(d["point"]); los.append(d["point"] - d["lo"]); his.append(d["hi"] - d["point"])
                else:
                    vals.append(np.nan); los.append(0); his.append(0)
            color = figstyle.BAND_COLORS[bi % len(figstyle.BAND_COLORS)]
            ax2.bar(x + offset, vals, width=width, color=color, hatch=hatch,
                    edgecolor="black", linewidth=0.3,
                    label=f"{band} ({condition})" if False else None,
                    yerr=[los, his], error_kw={"linewidth": 0.6, "capsize": 1.5})
    ax2.axhline(0, color="#666666", linewidth=0.8)
    ax2.set_xticks(x); ax2.set_xticklabels(AREAS)
    ax2.set_ylabel("Sup - Deep contrast (dB)")
    ax2.set_title("Superficial - deep contrast index, per band per area "
                   "(solid edge = stim, hatched = omission), session-bootstrap 95% CI",
                   fontsize=9)
    band_handles = [plt.Rectangle((0, 0), 1, 1, color=figstyle.BAND_COLORS[i % len(figstyle.BAND_COLORS)])
                     for i in range(len(band_names))]
    cond_handles = [plt.Rectangle((0, 0), 1, 1, facecolor="white", edgecolor="black", hatch=h,
                                    label=c) for c, h in [("stim", None), ("omission", "//")]]
    ax2.legend(band_handles + cond_handles, band_names + ["stim", "omission"], fontsize=6.5,
               ncol=len(band_names) + 2, loc="upper center", bbox_to_anchor=(0.5, -0.15))

    fig.suptitle("L3: laminar power profile -- depth x frequency (top), "
                 "sup/deep contrast index (bottom)", fontsize=11)
    figstyle.save(fig, FIG_DIR, "L3")
    fig.savefig(FIG_DIR / "L3.pdf", bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------------------- self-test --

def run_synthetic_selftest():
    """Synthetic laminar profile with a known signature -- superficial channels carry MORE
    gamma power, deep channels carry MORE beta power (the canonical FF/FB motif the spec
    references) -- the contrast index must recover the correct SIGN per band."""
    rng = np.random.default_rng(0)
    fs = 100.0  # matches the 10ms-bin TFR time convention (100 Hz sample rate in "time bins")
    n_trials, n_ch = 30, 20
    n_freqs, n_times = len(FREQS_HZ), len(TIMES_MS)
    channels = np.arange(64, 64 + n_ch)
    sup_ch = channels[:n_ch // 2]
    deep_ch = channels[n_ch // 2:]

    power = np.abs(rng.normal(1.0, 0.1, size=(n_trials, n_ch, n_freqs, n_times))) + 0.5
    resp_mask = (TIMES_MS >= RESPONSE_WIN_MS["stim"][0]) & (TIMES_MS <= RESPONSE_WIN_MS["stim"][1])
    gamma_mask = (FREQS_HZ >= BANDS["high_gamma"][0]) & (FREQS_HZ < BANDS["high_gamma"][1])
    beta_mask = (FREQS_HZ >= BANDS["beta"][0]) & (FREQS_HZ < BANDS["beta"][1])
    ch_sup_mask = np.zeros(n_ch, dtype=bool); ch_sup_mask[:n_ch // 2] = True
    ch_deep_mask = ~ch_sup_mask

    # Build a single (n_ch, n_freqs, n_times) multiplier via broadcasting and apply it in one
    # elementwise multiply -- chained boolean-fancy indexing (power[a][b][c] *= x) silently
    # operates on a copy at each step past the first and does NOT mutate the original array;
    # this caught exactly that bug on the first run of this test (both contrasts came back 0.00).
    mult = np.ones((n_ch, n_freqs, n_times))
    mult += 3.0 * (ch_sup_mask[:, None, None] & gamma_mask[None, :, None] & resp_mask[None, None, :])
    mult += 3.0 * (ch_deep_mask[:, None, None] & beta_mask[None, :, None] & resp_mask[None, None, :])
    power = power * mult[None, :, :, :]

    sup_gamma_db = group_band_db(power, channels, sup_ch, BANDS["high_gamma"], RESPONSE_WIN_MS["stim"])
    deep_gamma_db = group_band_db(power, channels, deep_ch, BANDS["high_gamma"], RESPONSE_WIN_MS["stim"])
    sup_beta_db = group_band_db(power, channels, sup_ch, BANDS["beta"], RESPONSE_WIN_MS["stim"])
    deep_beta_db = group_band_db(power, channels, deep_ch, BANDS["beta"], RESPONSE_WIN_MS["stim"])

    gamma_contrast = sup_gamma_db - deep_gamma_db
    beta_contrast = sup_beta_db - deep_beta_db
    print(f"gamma contrast (sup-deep) = {gamma_contrast:.2f} dB (want > 0)")
    print(f"beta contrast (sup-deep) = {beta_contrast:.2f} dB (want < 0)")
    assert gamma_contrast > 1.0, f"expected positive (superficial) gamma contrast, got {gamma_contrast:.2f}"
    assert beta_contrast < -1.0, f"expected negative (deep) beta contrast, got {beta_contrast:.2f}"
    print("PASS: contrast index recovers the correct sign for both baked-in signatures.")

    # Determinism.
    gamma_contrast2 = (group_band_db(power, channels, sup_ch, BANDS["high_gamma"], RESPONSE_WIN_MS["stim"])
                        - group_band_db(power, channels, deep_ch, BANDS["high_gamma"], RESPONSE_WIN_MS["stim"]))
    assert gamma_contrast == gamma_contrast2, "determinism check failed"
    print("PASS: determinism check.")

    # Shape/NaN guard: empty group returns None, not a crash/NaN.
    assert group_band_db(power, channels, np.array([]), BANDS["theta"], RESPONSE_WIN_MS["stim"]) is None
    print("PASS: empty-group guard (returns None, not NaN/crash).")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if args.test:
        run_synthetic_selftest()
        return
    stats = run()
    for key, d in stats["contrast_index"].items():
        print(f"{key}: n_sessions={d['n_sessions']} sup-deep={d['sup_minus_deep_db']:+.2f} dB "
              f"[{d['ci95_lo']:+.2f}, {d['ci95_hi']:+.2f}]")


if __name__ == "__main__":
    main()
