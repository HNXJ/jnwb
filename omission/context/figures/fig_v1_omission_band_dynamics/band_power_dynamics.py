r"""
Spectral band-power dynamics and TFR spectrograms around an omission, per area.

STATUS: built as a V1-only first pass, reviewed, fixed (per-band artifact repair,
2026-08-13), then generalized to all ten canonical analysis areas. Not wired into the
manuscript figure pipeline (no svgassemble/receipt-per-panel scaffolding) -- still a
standalone script, not yet a numbered fig0N_*.py.

WHAT THIS SHOWS
    Five band-power traces (dB re a pre-omission baseline) over time, for two condition
    families that put an omission at a different slot:
        p2-omission family (RXRR, AXAB, BXBA): fx-p1-d1-p2-d2
        p3-omission family (RRXR, AAXB, BBXA): d1-p2-d2-p3-d3
    Both windows are ASSUMED to run [-1531, +1031] ms relative to their own omission
    onset -- the user's note wrote "d1-p2-d2-p3-d2" for the second family, which does not
    parse (d2 appears twice, d3 not at all); read literally as "one delay of lead-in, the
    omitted slot, one delay after" the same shape as the first family, which requires
    ending at d3, not repeating d2. Ending at d3 also makes the two families' windows the
    same length and the same offset relative to their own omission onset, which is the
    only self-consistent reading. NOT independently confirmed with the user -- flagged
    here rather than silently resolved elsewhere.

DATA SOURCE
    Precomputed TFR arrays, D:/analysis/tfr_arrays (jnwb.paths.tfr_dir()), one .npz per
    (session, probe, area, condition): power (n_trials, n_channels, n_freqs, n_times)
    float32, freqs = arange(3, 201, 2) Hz, times = -1000 + arange(500)*10 ms, p1-aligned.
    Per direct instruction (2026-08-13, mid-task): use these as-is rather than
    recomputing from raw/repaired LFP -- known movement artifacts (see
    artifacts/.lab/lfp-movement-artifact-v198o-v182o-20260806.json) are handled here, in
    the TFR domain, not upstream.

ARTIFACT HANDLING (per direct instruction: "interpolate ... across trials since
artifacts are obvious if any"; revised 2026-08-13 to run PER BAND, not pooled broadband
-- see repair_band_artifacts docstring: a spike confined to one band, e.g. an isolated
high-gamma blip ("spindles" in the trace, caught by review), was diluted below threshold
when averaged against ~99 mostly-unaffected frequency rows in the first version)
    A movement artifact is a sparse, single-trial power spike that is not repeated by
    other trials at the same condition and time -- e.g. gamma power across trials at one
    instant reading 2 2 3 2 3 2 **11** 1 2 3 2; the 11 is not corroborated by any
    neighboring trial at that same latency, so it is treated as an artifact and replaced
    by the cross-trial median (2 11 2 -> 2 2 2), not by a temporal filter within the
    trial. Per session x condition x band:
      1. band_trace[trial, time] = mean over channel and that band's own frequency rows
         of power (band-restricted, not broadband -- see revision note above).
      2. trend[time] = median over trials of band_trace -- the shared evoked shape.
      3. resid = band_trace - trend; scale = robust MAD of resid POOLED over all
         (trial, time) in that band (a single global scale, not one estimated per time
         bin -- a per-time-bin MAD is itself inflated during the evoked response and masks
         real outliers there; the same fix already validated for the raw-LFP cross-trial-
         median detector in the linked lab record).
      4. Any (trial, time) cell with resid/scale beyond Z_THRESH is flagged.
      5. For a flagged trial, every channel and every frequency row WITHIN THAT BAND, at
         that time index only, is replaced by the cross-trial median at that same time
         index (all trials) -- other bands are untouched by this band's detection pass.
    This is substitution, not exclusion: the trial is kept, only the contaminated instants
    are replaced. Rare in a session (typically < 10% of trial x time cells per band -- see
    record) so this does not manufacture signal.

LOG-LAST (project doctrine, omission-signal skill #1)
    Power is averaged over trials and channels FIRST (linear), divided by baseline
    (linear ratio), frequency-band-averaged (linear), THEN 10*log10 exactly once, after
    the last average (across sessions x conditions). Never averaged in dB space.

UNIT OF INFERENCE
    Session x condition is the plotted replicate (SEM ribbons are across these, not
    across trials or channels) -- trials within a condition and channels within a probe
    are pooled, not independent replicates for the ribbon.
"""
from __future__ import annotations

import glob
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np

_FIGS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # context/figures
_REPO_ROOT = os.path.dirname(os.path.dirname(_FIGS_DIR))                  # repo root
sys.path.insert(0, _FIGS_DIR)
sys.path.insert(0, _REPO_ROOT)
from figstyle import EPOCH_ONSETS_MS, BANDS, BAND_COLORS, STIM_SHADE, OMIT_SHADE, ONSET_COLOR

from jnwb import paths as _P
from omission.jnwb_ext.spectral import to_db

TFR_DIR = _P.tfr_dir()
FIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "svg")
os.makedirs(FIG_DIR, exist_ok=True)

FREQS = np.arange(3, 201, 2, dtype=float)          # matches precompute_tfr_arrays_v2.py
TIMES_P1 = -1000.0 + np.arange(500, dtype=float) * 10.0   # p1-aligned, ms

BASELINE_WIN = (-250.0, -50.0)   # relative to omission onset -- reused from the fig06
                                  # per-channel pre-omission baseline convention

FAMILIES = {
    "p2_omission": {
        "conditions": ["RXRR", "AXAB", "BXBA"],
        "omission_onset_p1ms": EPOCH_ONSETS_MS["p2"],
        "window_p1ms": (EPOCH_ONSETS_MS["fx"], EPOCH_ONSETS_MS["p3"]),   # fx..d2 end == p3 start
        "epoch_order": ["fx", "p1", "d1", "p2", "d2"],
    },
    "p3_omission": {
        "conditions": ["RRXR", "AAXB", "BBXA"],
        "omission_onset_p1ms": EPOCH_ONSETS_MS["p3"],
        "window_p1ms": (EPOCH_ONSETS_MS["d1"], EPOCH_ONSETS_MS["p4"]),   # d1..d3 end == p4 start
        "epoch_order": ["d1", "p2", "d2", "p3", "d3"],
    },
}

Z_THRESH = 6.0

# Full-spectrum artifact repair, for the spectrogram (which shows every frequency row, not
# just the five named bands): BANDS only spans 4-80 Hz, leaving 3-4 Hz and 80-201 Hz
# unrepaired. Extend coverage with two extra ranges so no frequency row is left unchecked.
# The band traces keep using plain BANDS (unchanged from the already-reviewed version).
FULL_REPAIR_RANGES = dict(BANDS)
FULL_REPAIR_RANGES["Sub-theta (3-4 Hz)"] = (3.0, 4.0)
FULL_REPAIR_RANGES["Residual (80-201 Hz)"] = (80.0, 201.0)

# Ten canonical analysis areas (context/PROJECT_STATE.md:54-55, 111): "Ten analysis areas:
# V1, V2, V3, V4, MT, MST, TEO, FST, FEF, PFC. Eleven-to-twelve *labels* appear in
# filenames (V3, V3a, V3d separately); ten *analysis regions* is the correct count" and
# "V3a and V3d pool to V3" -- the raw "V3" filename token is included too (PROJECT_STATE
# flags a prior bug where an area-pooling dict omitted it). A separate "V3v" filename
# token (10 files) also exists on disk but is NOT one of the ten canonical areas and is
# NOT folded into this pool -- excluded here, not silently merged; see AREA_FILE_TOKENS.
AREAS = ["V1", "V2", "V3", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"]
AREA_FILE_TOKENS = {"V3": ["V3", "V3a", "V3d"]}   # default (area itself) used for every other area



def find_area_condition_files(area, condition):
    tokens = AREA_FILE_TOKENS.get(area, [area])
    files = []
    for tok in tokens:
        pattern = os.path.join(str(TFR_DIR), f"*-{tok}-{condition}.npz")
        files.extend(glob.glob(pattern))
    return sorted(files)


def repair_band_artifacts(power, freqs, band_ranges=None, z_thresh=Z_THRESH):
    """Per-band, cross-trial-median substitution of sparse single-trial power spikes.

    2026-08-13 revision: the first version pooled all 3-200 Hz frequency rows into one
    broadband detection statistic before flagging. A spike confined to one band (e.g. an
    isolated high-gamma blip -- "spindles" visible in the pooled trace, review finding)
    gets averaged against ~99 mostly-unaffected frequency rows and never crosses the
    z-threshold: diluted out of the very statistic meant to catch it. Detection now runs
    separately per band (BANDS' own frequency ranges), each restricted to its own rows, so
    an artifact confined to one band cannot hide behind the others.

    Per band: channel-mean power within that band's frequency rows, per trial x time.
    trend[time] = median over trials (the shared evoked shape); resid = value - trend;
    scale = median(|resid|) POOLED over all (trial, time) in that band (a single global
    scale, not one per time bin -- a per-time-bin MAD is itself inflated during the evoked
    response and would mask a real outlier there, the same fix already validated for the
    raw-LFP cross-trial-median detector in artifacts/.lab/lfp-movement-artifact-v198o-
    v182o-20260806.json). Any (trial, time) with resid/scale beyond z_thresh has ALL
    channels and ALL of that band's frequency rows, at that time index only, replaced by
    the cross-trial median (same instruction as the earlier version: "2 11 2 becomes 2 2
    2" -- median across trials at the same condition and time, not a temporal filter).

    power: (n_trials, n_channels, n_freqs, n_times). Returns (repaired, frac_flagged_by_band).
    """
    band_ranges = BANDS if band_ranges is None else band_ranges
    n_trials = power.shape[0]
    if n_trials < 5:
        return power, {}   # too few trials for a cross-trial median to mean anything

    repaired = power.copy()
    n_channels = power.shape[1]
    frac_flagged = {}

    for name, (lo, hi) in band_ranges.items():
        sel = (freqs >= lo) & (freqs < hi)
        freq_idx = np.where(sel)[0]
        if freq_idx.size == 0:
            continue

        band_trace = power[:, :, sel, :].mean(axis=(1, 2))        # (trials, times)
        trend = np.median(band_trace, axis=0)                      # (times,)
        resid = band_trace - trend[None, :]
        scale = np.median(np.abs(resid))                           # single pooled robust scale
        if scale < 1e-12:
            frac_flagged[name] = 0.0
            continue
        z = resid / (1.4826 * scale)
        flagged = z > z_thresh                                     # one-sided: artifacts are increases
        frac_flagged[name] = float(flagged.mean())
        if not flagged.any():
            continue

        band_median = np.median(power[:, :, sel, :], axis=0)       # (channels, n_band_freqs, times)
        for ti in range(power.shape[-1]):
            bad_trials = np.where(flagged[:, ti])[0]
            for b in bad_trials:
                repaired[b][:, freq_idx, ti] = band_median[:, :, ti]

    return repaired, frac_flagged


def load_session_condition(path, window_p1ms, band_ranges=None):
    z = np.load(path, allow_pickle=True)
    power = z["power"].astype(np.float64)                # (trials, channels, freqs, times)
    tmask = (TIMES_P1 >= window_p1ms[0]) & (TIMES_P1 < window_p1ms[1])
    power = power[:, :, :, tmask]
    power, frac_flagged_by_band = repair_band_artifacts(power, FREQS, band_ranges=band_ranges)
    return power, TIMES_P1[tmask], frac_flagged_by_band


def band_power_db_trace(power, times, omission_onset_p1ms):
    """power: (trials, channels, freqs, times_window) for ONE session x condition.

    Returns dict band_name -> (times_rel_to_omission_ms, ratio_per_band[len(times)]),
    still LINEAR (not yet in dB) -- log is taken once, after pooling across sessions.
    """
    mean_power = power.mean(axis=(0, 1))                  # trials, channels -> (freqs, times)
    t_rel = times - omission_onset_p1ms
    bmask = (t_rel >= BASELINE_WIN[0]) & (t_rel < BASELINE_WIN[1])
    if not bmask.any():
        raise ValueError("baseline window not covered by this session's loaded time slice")
    baseline = np.mean(mean_power[:, bmask], axis=1, keepdims=True)   # (freqs, 1)
    ratio = mean_power / np.maximum(baseline, 1e-12)                  # (freqs, times), linear

    out = {}
    for name, (lo, hi) in BANDS.items():
        sel = (FREQS >= lo) & (FREQS < hi)
        out[name] = np.nanmean(ratio[sel], axis=0) if sel.any() else np.full(ratio.shape[1], np.nan)
    return t_rel, out


def compute_family_band_dynamics(area, family_key):
    """Pools session x condition replicates for one area x family.

    Returns t_rel (ms, relative to omission onset), and per band: (mean_db, sem_db,
    n_replicates), plus a small receipt (files used, artifact-flagged fraction per file).
    """
    fam = FAMILIES[family_key]
    t_rel_ref = None
    per_band_reps = {name: [] for name in BANDS}
    receipt_rows = []

    for cond in fam["conditions"]:
        for path in find_area_condition_files(area, cond):
            power, times, frac_flagged_by_band = load_session_condition(path, fam["window_p1ms"])
            if power.shape[0] < 5:
                continue
            t_rel, band_ratios = band_power_db_trace(power, times, fam["omission_onset_p1ms"])
            if t_rel_ref is None:
                t_rel_ref = t_rel
            elif t_rel.shape != t_rel_ref.shape:
                continue   # a session missing time bins at this window edge -- skip rather than misalign
            for name, r in band_ratios.items():
                per_band_reps[name].append(r)
            receipt_rows.append({
                "file": os.path.basename(path), "condition": cond,
                "n_trials": int(power.shape[0]), "n_channels": int(power.shape[1]),
                "frac_trial_time_flagged_by_band": frac_flagged_by_band,
            })

    if t_rel_ref is None:
        raise ValueError(f"no usable {area} files found for family {family_key} "
                         f"(conditions {fam['conditions']}) -- zero sessions with >=5 trials")

    result = {}
    for name, reps in per_band_reps.items():
        arr = np.stack(reps, axis=0) if reps else np.zeros((0, t_rel_ref.size))
        mu = np.nanmean(arr, axis=0)
        n = max(arr.shape[0], 1)
        sem = np.nanstd(arr, axis=0, ddof=1) / np.sqrt(n) if arr.shape[0] > 1 else np.zeros_like(mu)
        result[name] = (to_db(mu), to_db(np.maximum(mu - sem, 1e-12)), to_db(mu + sem))
    return t_rel_ref, result, receipt_rows


def _epoch_strip(ax, fam, family_key):
    onsets = {k: EPOCH_ONSETS_MS[k] for k in fam["epoch_order"]}
    omission_onset = fam["omission_onset_p1ms"]
    order = fam["epoch_order"]
    win_end = EPOCH_ONSETS_MS[{"p2_omission": "p3", "p3_omission": "p4"}[family_key]]
    bounds = [onsets[k] for k in order] + [win_end]
    for i, name in enumerate(order):
        a, b = bounds[i] - omission_onset, bounds[i + 1] - omission_onset
        is_omit = onsets[name] == omission_onset
        color = OMIT_SHADE if is_omit else (STIM_SHADE if name.startswith("p") else "0.92")
        ax.axvspan(a, b, color=color, alpha=0.8, zorder=0)
        label = "Omission" if is_omit else ("Stim" if name.startswith("p") else "Delay")
        ax.text((a + b) / 2, 0.5, label, ha="center", va="center", fontsize=7, color="0.25")
    ax.set_xlim(bounds[0] - omission_onset, bounds[-1] - omission_onset)
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)


def plot_area_band_power_dynamics(area):
    fig, axes = plt.subplots(4, 1, figsize=(8.5, 8.0),
                             gridspec_kw={"height_ratios": [0.35, 2.2, 0.35, 2.2]})
    all_receipts = {}
    for row, family_key in enumerate(["p2_omission", "p3_omission"]):
        strip_ax, trace_ax = axes[2 * row], axes[2 * row + 1]
        fam = FAMILIES[family_key]
        t_rel, result, receipt_rows = compute_family_band_dynamics(area, family_key)
        all_receipts[family_key] = receipt_rows

        _epoch_strip(strip_ax, fam, family_key)
        for (name, (lo, hi)), col in zip(BANDS.items(), BAND_COLORS):
            mu_db, lo_db, hi_db = result[name]
            trace_ax.plot(t_rel, mu_db, color=col, lw=2.0, label=name, zorder=3)
            trace_ax.fill_between(t_rel, lo_db, hi_db, color=col, alpha=0.28, lw=0, zorder=2)
        trace_ax.axhline(0, color="black", lw=0.9)
        trace_ax.axvline(0, color=ONSET_COLOR, ls="--", lw=1.6)
        trace_ax.set_xlim(t_rel[0], t_rel[-1])
        trace_ax.set_ylabel("Power change (dB)", fontsize=10)
        n_reps = len(receipt_rows)
        cond_str = "/".join(fam["conditions"])
        trace_ax.set_title(f"{area}, {cond_str} (omission at {family_key.split('_')[0]}), "
                           f"n={n_reps} session x condition replicates", fontsize=9)
        if row == 0:
            leg = trace_ax.legend(fontsize=8, loc="upper right", framealpha=0.9)
        if row == 1:
            trace_ax.set_xlabel("Time from omission onset (ms)", fontsize=11)

    fig.suptitle(f"{area}: spectral band-power dynamics around omission",
                fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    slug = area.replace("/", "").lower()
    out_png = os.path.join(FIG_DIR, f"{slug}_band_power_dynamics.png")
    fig.savefig(out_png, dpi=170)
    plt.close(fig)

    import json
    with open(os.path.join(FIG_DIR, f"{slug}_band_power_dynamics.receipt.json"), "w") as fh:
        json.dump({
            "script": os.path.abspath(__file__),
            "area": area,
            "area_file_tokens": AREA_FILE_TOKENS.get(area, [area]),
            "families": {k: {"conditions": v["conditions"],
                             "window_p1ms": v["window_p1ms"],
                             "omission_onset_p1ms": v["omission_onset_p1ms"]}
                        for k, v in FAMILIES.items()},
            "baseline_win_rel_ms": BASELINE_WIN,
            "z_thresh_artifact": Z_THRESH,
            "replicates": all_receipts,
        }, fh, indent=2)
    print(f"Wrote {out_png}")
    return out_png


def plot_all_areas():
    out = {}
    for area in AREAS:
        try:
            out[area] = plot_area_band_power_dynamics(area)
        except Exception as e:
            print(f"FAILED {area}: {e}")
            out[area] = None
    return out


# ============================================================================================
# 2-D spectrograms (full 3-201 Hz TFR heatmaps), same areas/families/windows/artifact repair
# as the band traces above -- just not collapsed into the five named bands.
# ============================================================================================

def freq_ratio_trace(power, times, omission_onset_p1ms):
    """power: (trials, channels, freqs, times_window) for ONE session x condition.

    Returns (t_rel_ms, ratio[freqs, times]), still LINEAR -- log taken once, after pooling
    across sessions, same log-last rule as band_power_db_trace.
    """
    mean_power = power.mean(axis=(0, 1))                  # trials, channels -> (freqs, times)
    t_rel = times - omission_onset_p1ms
    bmask = (t_rel >= BASELINE_WIN[0]) & (t_rel < BASELINE_WIN[1])
    if not bmask.any():
        raise ValueError("baseline window not covered by this session's loaded time slice")
    baseline = np.mean(mean_power[:, bmask], axis=1, keepdims=True)   # (freqs, 1)
    ratio = mean_power / np.maximum(baseline, 1e-12)                  # (freqs, times), linear
    return t_rel, ratio


def compute_family_spectrogram(area, family_key):
    """Pools session x condition replicates for one area x family into one dB spectrogram.

    Same replicate pooling as compute_family_band_dynamics (mean of the LINEAR ratio across
    session x condition replicates, log taken once at the end) but keeps full frequency
    resolution instead of collapsing to the five named bands. Artifact repair uses
    FULL_REPAIR_RANGES (extends BANDS' 4-80 Hz coverage to the full 3-201 Hz the
    spectrogram displays -- see FULL_REPAIR_RANGES comment).
    """
    fam = FAMILIES[family_key]
    t_rel_ref = None
    reps = []
    receipt_rows = []

    for cond in fam["conditions"]:
        for path in find_area_condition_files(area, cond):
            power, times, frac_flagged_by_band = load_session_condition(
                path, fam["window_p1ms"], band_ranges=FULL_REPAIR_RANGES)
            if power.shape[0] < 5:
                continue
            t_rel, ratio = freq_ratio_trace(power, times, fam["omission_onset_p1ms"])
            if t_rel_ref is None:
                t_rel_ref = t_rel
            elif t_rel.shape != t_rel_ref.shape:
                continue
            reps.append(ratio)
            receipt_rows.append({
                "file": os.path.basename(path), "condition": cond,
                "n_trials": int(power.shape[0]), "n_channels": int(power.shape[1]),
                "frac_trial_time_flagged_by_band": frac_flagged_by_band,
            })

    if t_rel_ref is None:
        raise ValueError(f"no usable {area} files found for family {family_key} "
                         f"(conditions {fam['conditions']}) -- zero sessions with >=5 trials")

    mean_ratio = np.nanmean(np.stack(reps, axis=0), axis=0)   # (freqs, times), linear
    db = to_db(mean_ratio)
    return t_rel_ref, FREQS, db, receipt_rows


def draw_spectrogram(fig, ax, t_rel, freqs, db, vlim):
    """Diverging red-blue colormap ('RdBu_r'), symmetric about 0 dB -- per direct request.
    Log frequency axis, matching the fig06 convention (theta-beta occupy most of the panel
    on a linear axis otherwise). Band edges marked with thin black lines, not red, since red
    is now a data colour (positive dB) rather than a free annotation colour.
    """
    im = ax.pcolormesh(t_rel, freqs, db, cmap="RdBu_r", shading="nearest",
                       vmin=vlim[0], vmax=vlim[1])
    im.set_rasterized(True)   # vector per-quad paths are pathological at this grid size (fig06)
    for e in sorted({e for v in BANDS.values() for e in v if e <= freqs[-1]}):
        ax.axhline(e, color="black", lw=0.5, alpha=0.5)
    ax.axvline(0, color="black", ls="--", lw=1.4)
    ax.set_yscale("log")
    ax.set_ylim(freqs[0], freqs[-1])
    ax.set_yticks([4, 8, 14, 30, 50, 80, 150])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_ylabel("Frequency (Hz)", fontsize=10)
    cb = fig.colorbar(im, ax=ax, pad=0.012, fraction=0.030)
    cb.solids.set_rasterized(True)
    cb.set_label("Power change (dB)", fontsize=8, rotation=270, labelpad=12)
    cb.ax.tick_params(labelsize=8)
    return im


def plot_area_spectrograms(area):
    fig, axes = plt.subplots(4, 1, figsize=(8.5, 8.6),
                             gridspec_kw={"height_ratios": [0.35, 2.6, 0.35, 2.6]})
    all_receipts = {}
    for row, family_key in enumerate(["p2_omission", "p3_omission"]):
        strip_ax, spec_ax = axes[2 * row], axes[2 * row + 1]
        fam = FAMILIES[family_key]
        t_rel, freqs, db, receipt_rows = compute_family_spectrogram(area, family_key)
        all_receipts[family_key] = receipt_rows

        _epoch_strip(strip_ax, fam, family_key)
        vmax = max(float(np.nanpercentile(np.abs(db[np.isfinite(db)]), 99)), 0.5)
        draw_spectrogram(fig, spec_ax, t_rel, freqs, db, (-vmax, vmax))
        spec_ax.set_xlim(t_rel[0], t_rel[-1])
        n_reps = len(receipt_rows)
        cond_str = "/".join(fam["conditions"])
        spec_ax.set_title(f"{area}, {cond_str} (omission at {family_key.split('_')[0]}), "
                          f"n={n_reps} session x condition replicates", fontsize=9)
        if row == 1:
            spec_ax.set_xlabel("Time from omission onset (ms)", fontsize=11)

    fig.suptitle(f"{area}: TFR spectrogram around omission",
                fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    slug = area.replace("/", "").lower()
    out_png = os.path.join(FIG_DIR, f"{slug}_tfr_spectrogram.png")
    out_svg = os.path.join(FIG_DIR, f"{slug}_tfr_spectrogram.svg")
    fig.savefig(out_png, dpi=170)
    fig.savefig(out_svg)
    plt.close(fig)

    import json
    with open(os.path.join(FIG_DIR, f"{slug}_tfr_spectrogram.receipt.json"), "w") as fh:
        json.dump({
            "script": os.path.abspath(__file__),
            "area": area,
            "area_file_tokens": AREA_FILE_TOKENS.get(area, [area]),
            "colormap": "RdBu_r, symmetric about 0 dB (99th percentile |dB|, floor 0.5 dB)",
            "families": {k: {"conditions": v["conditions"],
                             "window_p1ms": v["window_p1ms"],
                             "omission_onset_p1ms": v["omission_onset_p1ms"]}
                        for k, v in FAMILIES.items()},
            "baseline_win_rel_ms": BASELINE_WIN,
            "z_thresh_artifact": Z_THRESH,
            "repair_freq_ranges": FULL_REPAIR_RANGES,
            "replicates": all_receipts,
        }, fh, indent=2)
    print(f"Wrote {out_png} and {out_svg}")
    return out_png, out_svg


def plot_all_areas_spectrograms():
    out = {}
    for area in AREAS:
        try:
            out[area] = plot_area_spectrograms(area)
        except Exception as e:
            print(f"FAILED {area}: {e}")
            out[area] = None
    return out


if __name__ == "__main__":
    plot_all_areas()
    plot_all_areas_spectrograms()
