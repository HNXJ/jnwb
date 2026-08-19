r"""
One-off diagnostic: does raw, unfiltered LFP show impulse-like broadband artifacts (consistent
with movement/electrode artifact, not neural signal) in V198o / V182o sessions?

Reuses the corpus's own canonical LFP/trial-onset accessors (resolve_lfp_datasets,
the bytes-safe stimulus_number/correct/start_time coercion) rather than re-deriving them, per
this project's own footgun notes on raw h5py trial-table access.

Not part of any figure pipeline. Writes PNGs to outputs/qc_lfp_artifacts/ for visual review.
"""
from __future__ import annotations

import os
import sys

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(REPO))
sys.path.insert(0, os.path.join(os.path.dirname(REPO), "scripts", "archive_oneoff"))
from precompute_tfr_arrays import resolve_lfp_datasets  # noqa: E402
from jnwb import paths as _P
from omission.jnwb_ext.artifact_repair import interpolate_intervals, flagged_to_intervals

OUT_DIR = _P.REPO_ROOT / "outputs/qc_lfp_artifacts"
N_TRIALS = 20
PRE_S = 0.5
POST_TRIAL_S = 5.0   # generous pad after the 20th trial's onset


def _to_numeric(arr):
    if arr.dtype.kind in ("O", "S", "U"):
        return np.array([float(x.decode() if isinstance(x, bytes) else x) for x in arr], dtype=float)
    return arr.astype(float)


def correct_p1_onsets(f):
    """All correct-trial p1 onsets (stimulus_number==2, correct==1), any condition, time-sorted.
    Same filter convention as p1_onsets_and_conditions_s in extract_lfp_coupling_matrices.py,
    just not restricted to a named condition subset."""
    g = f["intervals/omission_glo_passive"]
    sn = _to_numeric(g["stimulus_number"][:])
    corr = _to_numeric(g["correct"][:])
    st = _to_numeric(g["start_time"][:])
    mask = (sn == 2) & (corr == 1) & np.isfinite(st)
    onsets = np.sort(st[mask])
    return onsets


def check_session(nwb_path, label, probe_key="probe_0_lfp", trial_start_idx=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    with h5py.File(nwb_path, "r") as f:
        onsets = correct_p1_onsets(f)
        print(f"[{label}] {len(onsets)} correct trials total")
        if trial_start_idx is None:
            trial_start_idx = len(onsets) // 3   # avoid the very start/end of the recording
        window_onsets = onsets[trial_start_idx: trial_start_idx + N_TRIALS]
        t0 = window_onsets[0] - PRE_S
        t1 = window_onsets[-1] + POST_TRIAL_S
        print(f"[{label}] trials {trial_start_idx}-{trial_start_idx + N_TRIALS - 1}, "
             f"window {t0:.2f}-{t1:.2f}s ({t1 - t0:.1f}s)")

        data, ts, fs = resolve_lfp_datasets(f, probe_key)
        if ts is not None:
            i0 = np.searchsorted(ts, t0)
            i1 = np.searchsorted(ts, t1)
            t_axis = ts[i0:i1]
        else:
            i0 = int(round(t0 * fs))
            i1 = int(round(t1 * fs))
            t_axis = np.arange(i0, i1) / fs
        seg = data[i0:i1, :]   # samples x channels
        print(f"[{label}] fs={fs:.1f} Hz, segment shape {seg.shape}, "
             f"raw amplitude range [{seg.min():.1f}, {seg.max():.1f}] uV")

        n_ch = seg.shape[1]
        offset_step = np.percentile(np.abs(seg), 99.5) * 1.6
        fig, ax = plt.subplots(figsize=(14, 20))
        for ch in range(n_ch):
            ax.plot(t_axis - t0, seg[:, ch] + ch * offset_step, color="black", lw=0.3)
        for k, onset in enumerate(window_onsets):
            ax.axvline(onset - t0, color="red", lw=0.5, alpha=0.5)
        ax.set_yticks([])
        ax.set_xlabel("time (s), red lines = correct-trial p1 onsets")
        ax.set_title(f"{label} -- {probe_key}, raw LFP, all {n_ch} channels, "
                    f"{N_TRIALS} consecutive correct trials (trials "
                    f"{trial_start_idx}-{trial_start_idx + N_TRIALS - 1})", fontsize=10)
        ax.set_xlim(0, t1 - t0)
        fig.tight_layout()
        out = os.path.join(OUT_DIR, f"{label}_{probe_key}_raw_stacked.png")
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(f"[{label}] wrote {out}")

        # Also a population-level summary: mean |LFP| across channels per sample, which turns
        # a synchronous broadband artifact (present on every channel at once) into a single
        # sharp spike, and a single noisy channel into a much smaller bump -- cheap way to tell
        # the two apart without eyeballing 128 stacked traces.
        pop = np.abs(seg).mean(axis=1)
        fig2, ax2 = plt.subplots(figsize=(14, 3))
        ax2.plot(t_axis - t0, pop, color="black", lw=0.6)
        for onset in window_onsets:
            ax2.axvline(onset - t0, color="red", lw=0.5, alpha=0.5)
        ax2.set_xlabel("time (s)")
        ax2.set_ylabel("mean |LFP| across channels (uV)")
        ax2.set_title(f"{label} -- {probe_key}, cross-channel mean |LFP| "
                     f"(spikes here = synchronous across-channel events)", fontsize=9)
        ax2.set_xlim(0, t1 - t0)
        fig2.tight_layout()
        out2 = os.path.join(OUT_DIR, f"{label}_{probe_key}_popmean.png")
        fig2.savefig(out2, dpi=150)
        plt.close(fig2)
        print(f"[{label}] wrote {out2}")
        return seg, t_axis, t0, window_onsets


def _to_numeric_arr(arr):
    return _to_numeric(arr)


AAAB_TASK_CONDITION_NUMBERS = (1, 2)   # scripts/archive_oneoff/precompute_tfr_arrays.py CONDITION_NUMBERS["AAAB"]
FULL_TRIAL_WIN_MS = (-600, 4200)       # matches context/figures/figstyle.py FULL_TRIAL_WIN


def condition_onsets(f, task_condition_numbers):
    g = f["intervals/omission_glo_passive"]
    sn = _to_numeric(g["stimulus_number"][:])
    corr = _to_numeric(g["correct"][:])
    tc = _to_numeric(g["task_condition_number"][:])
    st = _to_numeric(g["start_time"][:])
    mask = (sn == 2) & (corr == 1) & np.isin(tc, task_condition_numbers) & np.isfinite(st)
    return np.sort(st[mask])




def aaab_trial_average_before_after(nwb_path, session_label, probe_key, intervals_csv):
    """Trial-averaged raw LFP for all correct AAAB trials, one probe, all channels, before vs.
    after artifact repair. Each trial's own detected intervals (session-global sample indices,
    from `intervals_csv`) are mapped into that trial's local window and interpolated over;
    trials with no overlapping interval are unchanged. The two averages are then compared."""
    import pandas as pd
    ivs_df = pd.read_csv(intervals_csv) if os.path.exists(intervals_csv) else None

    with h5py.File(nwb_path, "r") as f:
        onsets = condition_onsets(f, AAAB_TASK_CONDITION_NUMBERS)
        data, ts, fs = resolve_lfp_datasets(f, probe_key)
        n_ch = data.shape[1]
        win_samp = (int(round(FULL_TRIAL_WIN_MS[0] / 1000.0 * fs)),
                   int(round(FULL_TRIAL_WIN_MS[1] / 1000.0 * fs)))
        n_win = win_samp[1] - win_samp[0]

        sum_before = np.zeros((n_win, n_ch), dtype=np.float64)
        sum_after = np.zeros((n_win, n_ch), dtype=np.float64)
        n_used = 0
        n_trials_repaired = 0
        for onset in onsets:
            onset_idx = int(round(onset * fs))
            i0, i1 = onset_idx + win_samp[0], onset_idx + win_samp[1]
            if i0 < 0 or i1 > data.shape[0]:
                continue
            seg = data[i0:i1, :]
            sum_before += seg
            local_intervals = []
            if ivs_df is not None and len(ivs_df):
                overlap = ivs_df[(ivs_df.end_idx > i0) & (ivs_df.start_idx < i1)]
                for _, r in overlap.iterrows():
                    local_intervals.append((int(r.start_idx) - i0, int(r.end_idx) - i0))
            if local_intervals:
                n_trials_repaired += 1
                seg_after = interpolate_intervals(seg, local_intervals)
            else:
                seg_after = seg
            sum_after += seg_after
            n_used += 1

        avg_before = sum_before / n_used
        avg_after = sum_after / n_used
        print(f"[{session_label}] AAAB trial average: {n_used} trials used, "
             f"{n_trials_repaired} had >=1 interval overlapping their window "
             f"({n_trials_repaired/n_used*100:.1f}%)")

        t_axis = np.arange(win_samp[0], win_samp[1]) / fs * 1000.0   # ms re p1
        fig, axes = plt.subplots(1, 2, figsize=(16, 12), sharey=True)
        offset_step = np.percentile(np.abs(avg_before), 99) * 2.5
        for ch in range(n_ch):
            axes[0].plot(t_axis, avg_before[:, ch] + ch * offset_step, color="black", lw=0.5)
            axes[1].plot(t_axis, avg_after[:, ch] + ch * offset_step, color="black", lw=0.5)
        for ax, title in zip(axes, ["before repair", "after repair"]):
            for onset_ms in (0, 531, 1031, 1562, 2062, 2593, 3093, 3624):
                ax.axvline(onset_ms, color="red", lw=0.4, alpha=0.3)
            ax.set_title(title, fontsize=10)
            ax.set_xlabel("ms re p1 onset")
            ax.set_yticks([])
        fig.suptitle(f"{session_label} -- {probe_key}, trial-averaged raw LFP, "
                    f"{n_used} correct AAAB trials, all {n_ch} channels\n"
                    f"(red lines: p1/d1/p2/d2/p3/d3/p4/d4 boundaries)", fontsize=10)
        fig.tight_layout()
        out = os.path.join(OUT_DIR, f"{session_label}_{probe_key}_AAAB_trial_avg_before_after.png")
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(f"[{session_label}] wrote {out}")

        # Also the difference, since a rare per-trial artifact contributes only ~1/n_used of
        # its own amplitude to the mean, and may not be visible by eye against the offset stack.
        diff = avg_before - avg_after
        fig2, ax2 = plt.subplots(figsize=(10, 12))
        for ch in range(n_ch):
            ax2.plot(t_axis, diff[:, ch] + ch * offset_step * 0.3, color="black", lw=0.5)
        for onset_ms in (0, 531, 1031, 1562, 2062, 2593, 3093, 3624):
            ax2.axvline(onset_ms, color="red", lw=0.4, alpha=0.3)
        ax2.set_yticks([])
        ax2.set_xlabel("ms re p1 onset")
        ax2.set_title(f"{session_label} -- {probe_key}, trial-average DIFFERENCE "
                     f"(before - after), what repair changed in the average", fontsize=10)
        fig2.tight_layout()
        out2 = os.path.join(OUT_DIR, f"{session_label}_{probe_key}_AAAB_trial_avg_diff.png")
        fig2.savefig(out2, dpi=150)
        plt.close(fig2)
        print(f"[{session_label}] wrote {out2}, max abs diff = {np.abs(diff).max():.2f} uV "
             f"(vs raw trial-avg amplitude range [{avg_before.min():.1f}, {avg_before.max():.1f}] uV)")
        return avg_before, avg_after


def aaab_single_trial_quality_before_after(nwb_path, session_label, probe_key, intervals_csv):
    """Trial-averaging (aaab_trial_average_before_after above) is blind to non-trial-locked
    contamination by construction -- a random-timing artifact in a minority of trials
    contributes only ~1/n_trials to the mean and mostly washes out. This instead looks at
    trial-to-trial VARIABILITY (cross-trial SD as a function of within-trial time) and
    per-trial outlier magnitude, neither of which averages away a non-phase-locked event: a
    real, consistent evoked response has LOW cross-trial SD (every trial does roughly the same
    thing); an artifact landing at a different random time in a different trial each time
    inflates cross-trial SD sharply wherever it happens to land, and inflates that trial's own
    peak |voltage| regardless of what any other trial did."""
    import pandas as pd
    ivs_df = pd.read_csv(intervals_csv) if os.path.exists(intervals_csv) else None

    with h5py.File(nwb_path, "r") as f:
        onsets = condition_onsets(f, AAAB_TASK_CONDITION_NUMBERS)
        data, ts, fs = resolve_lfp_datasets(f, probe_key)
        n_ch = data.shape[1]
        win_samp = (int(round(FULL_TRIAL_WIN_MS[0] / 1000.0 * fs)),
                   int(round(FULL_TRIAL_WIN_MS[1] / 1000.0 * fs)))
        n_win = win_samp[1] - win_samp[0]

        trials_before, trials_after = [], []
        for onset in onsets:
            onset_idx = int(round(onset * fs))
            i0, i1 = onset_idx + win_samp[0], onset_idx + win_samp[1]
            if i0 < 0 or i1 > data.shape[0]:
                continue
            seg = data[i0:i1, :]
            local_intervals = []
            if ivs_df is not None and len(ivs_df):
                overlap = ivs_df[(ivs_df.end_idx > i0) & (ivs_df.start_idx < i1)]
                for _, r in overlap.iterrows():
                    local_intervals.append((int(r.start_idx) - i0, int(r.end_idx) - i0))
            seg_after = interpolate_intervals(seg, local_intervals) if local_intervals else seg
            trials_before.append(seg)
            trials_after.append(seg_after)
        trials_before = np.stack(trials_before)   # (n_trials, n_win, n_ch)
        trials_after = np.stack(trials_after)
        n_trials = trials_before.shape[0]
        print(f"[{session_label}] single-trial quality: {n_trials} AAAB trials")

        # ---- cross-trial SD over time, averaged across channels -----------------------------
        sd_before = trials_before.std(axis=0).mean(axis=1)   # (n_win,)
        sd_after = trials_after.std(axis=0).mean(axis=1)
        t_axis = np.arange(win_samp[0], win_samp[1]) / fs * 1000.0

        # ---- per-trial peak |voltage| across all channels ------------------------------------
        peak_before = np.abs(trials_before).max(axis=(1, 2))   # (n_trials,)
        peak_after = np.abs(trials_after).max(axis=(1, 2))

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        axes[0].plot(t_axis, sd_before, color="0.2", lw=1.2, label="before repair")
        axes[0].plot(t_axis, sd_after, color="#D62728", lw=1.2, label="after repair")
        for onset_ms in (0, 531, 1031, 1562, 2062, 2593, 3093, 3624):
            axes[0].axvline(onset_ms, color="black", lw=0.3, alpha=0.2)
        axes[0].set_xlabel("ms re p1 onset")
        axes[0].set_ylabel("cross-trial SD (uV), mean over channels")
        axes[0].set_title(f"Cross-trial variability over time\n(low = trials agree; high = "
                          f"something non-repeatable happened)")
        axes[0].legend(fontsize=8)

        bins = np.logspace(np.log10(max(peak_before.min(), 1)), np.log10(peak_before.max()), 40)
        axes[1].hist(peak_before, bins=bins, color="0.6", alpha=0.6, label="before repair")
        axes[1].hist(peak_after, bins=bins, color="#D62728", alpha=0.6, label="after repair")
        axes[1].set_xscale("log")
        axes[1].set_xlabel("per-trial peak |LFP| across all channels (uV, log scale)")
        axes[1].set_ylabel("n trials")
        axes[1].set_title("Single-trial outlier magnitude")
        axes[1].legend(fontsize=8)
        fig.suptitle(f"{session_label} -- {probe_key}, {n_trials} correct AAAB trials, "
                    f"non-trial-locked signal quality", fontsize=10)
        fig.tight_layout()
        out = os.path.join(OUT_DIR, f"{session_label}_{probe_key}_AAAB_single_trial_quality.png")
        fig.savefig(out, dpi=150)
        plt.close(fig)

        mean_sd_reduction = 1 - sd_after.mean() / sd_before.mean()
        p99_before, p99_after = np.percentile(peak_before, 99), np.percentile(peak_after, 99)
        n_outlier_before = (peak_before > 5 * np.median(peak_before)).sum()
        n_outlier_after = (peak_after > 5 * np.median(peak_before)).sum()
        print(f"[{session_label}] wrote {out}")
        print(f"[{session_label}] mean cross-trial SD: before={sd_before.mean():.2f}uV "
             f"after={sd_after.mean():.2f}uV ({mean_sd_reduction*100:.1f}% reduction)")
        print(f"[{session_label}] peak cross-trial SD: before={sd_before.max():.2f}uV "
             f"after={sd_after.max():.2f}uV")
        print(f"[{session_label}] per-trial peak|LFP| p99: before={p99_before:.1f}uV "
             f"after={p99_after:.1f}uV; max: before={peak_before.max():.1f}uV "
             f"after={peak_after.max():.1f}uV")
        print(f"[{session_label}] trials with peak|LFP| > 5x median-before ({5*np.median(peak_before):.1f}uV): "
             f"before={n_outlier_before}/{n_trials} ({n_outlier_before/n_trials*100:.1f}%), "
             f"after={n_outlier_after}/{n_trials} ({n_outlier_after/n_trials*100:.1f}%)")
        return sd_before, sd_after, peak_before, peak_after


FAIR_WIN_MS = (-500.0, 4000.0)   # excludes the reward-onset transient (~4120-4142ms post-p1)
                                  # so the outlier-magnitude distribution isn't skewed by a
                                  # different, already-identified, non-movement phenomenon
CROSS_TRIAL_Z_THRESH = 6.0
CROSS_TRIAL_PAD_MS = 20.0
CROSS_TRIAL_MERGE_GAP_MS = 60.0


def _cross_trial_repair_core(nwb_path, session_label, probe_key, condition_task_numbers,
                             condition_label, win_ms=FAIR_WIN_MS, z_thresh=CROSS_TRIAL_Z_THRESH):
    """Detects and repairs 'non-time-trial-locked single spikes' -- per (channel, within-trial
    timepoint), compare EVERY trial's value against the cross-trial median/MAD at that exact
    timepoint. A genuine evoked response moves all trials together, so it does not trip this
    detector regardless of amplitude; a spike confined to one trial (or a small few) at a time
    other trials don't share does. This is a different, complementary detector to the
    cross-channel-synchrony one in repair_lfp_movement_artifacts.py -- that one catches events
    synchronous across channels within a trial; this one catches events that don't recur across
    trials at the same latency, independent of how many channels they hit.

    Repair replaces flagged (trial, channel, interval) spans with the cross-trial median trace
    at that (channel, time), crossfading in/out across CROSS_TRIAL_PAD_MS at each edge so the
    repaired trial rejoins its own actual signal smoothly rather than jumping onto the median.

    Returns dict with t_axis, sd_before, sd_after, peak_before, peak_after, n_trials,
    n_trials_touched, n_spikes -- core computation only, no plotting."""
    with h5py.File(nwb_path, "r") as f:
        onsets = condition_onsets(f, condition_task_numbers)
        data, ts, fs = resolve_lfp_datasets(f, probe_key)
        n_ch = data.shape[1]
        win_samp = (int(round(win_ms[0] / 1000.0 * fs)), int(round(win_ms[1] / 1000.0 * fs)))
        n_win = win_samp[1] - win_samp[0]

        trials = []
        for onset in onsets:
            oi = int(round(onset * fs))
            i0, i1 = oi + win_samp[0], oi + win_samp[1]
            if i0 < 0 or i1 > data.shape[0]:
                continue
            trials.append(data[i0:i1, :])
        trials = np.stack(trials)   # (n_trials, n_win, n_ch)
        n_trials = trials.shape[0]

        # Scale is per-CHANNEL only (pooled across all trials AND all timepoints), not
        # per-(timepoint,channel). A per-instant MAD is itself inflated at timepoints where
        # trials naturally vary a lot (e.g. during an evoked response), which masks genuine
        # large deviations exactly when they're most likely to matter -- confirmed directly:
        # at z_thresh=15 with a per-instant MAD, the single largest event in this dataset
        # (channel 88, 1388.5uV, 3.3x that channel's own median) was flagged in ZERO trials,
        # because the local MAD at that specific timepoint was itself large. A per-channel,
        # window-pooled MAD (n = n_trials*n_win samples, much more stable) does not have this
        # failure mode -- it does not adapt to the local variance at all, on purpose.
        med = np.median(trials, axis=0)                          # (n_win, n_ch)
        mad_per_channel = np.median(np.abs(trials - med[None]), axis=(0, 1)) * 1.4826  # (n_ch,)
        mad_per_channel = np.where(mad_per_channel < 1e-9, 1e-9, mad_per_channel)
        z = (trials - med[None]) / mad_per_channel[None, None, :]   # (n_trials, n_win, n_ch)

        pad = int(round(CROSS_TRIAL_PAD_MS / 1000.0 * fs))
        gap = int(round(CROSS_TRIAL_MERGE_GAP_MS / 1000.0 * fs))
        repaired = trials.copy()
        n_spikes = 0
        n_trials_touched = 0
        for ti in range(n_trials):
            trial_touched = False
            for ci in range(n_ch):
                flagged = np.abs(z[ti, :, ci]) > z_thresh
                if not flagged.any():
                    continue
                ivs = flagged_to_intervals(flagged, fs, pad_ms=CROSS_TRIAL_PAD_MS,
                                          merge_gap_ms=CROSS_TRIAL_MERGE_GAP_MS)
                for s, e in ivs:
                    s, e = max(s, 0), min(e, n_win)
                    if e <= s:
                        continue
                    n_spikes += 1
                    trial_touched = True
                    span = e - s
                    fade = np.ones(span)
                    edge = min(pad, span // 2)
                    if edge > 0:
                        fade[:edge] = np.linspace(1, 0, edge)
                        fade[-edge:] = np.linspace(0, 1, edge)
                        fade[edge:span - edge] = 0
                    repaired[ti, s:e, ci] = (fade * trials[ti, s:e, ci]
                                            + (1 - fade) * med[s:e, ci])
            if trial_touched:
                n_trials_touched += 1

        print(f"[{session_label}] cross-trial median repair ({condition_label}, "
             f"{win_ms[0]:.0f}..{win_ms[1]:.0f}ms, z>{z_thresh}): {n_trials} trials, "
             f"{n_spikes} (trial,channel) spikes flagged across "
             f"{n_trials_touched} trials ({n_trials_touched/n_trials*100:.1f}%)")

        peak_before = np.abs(trials).max(axis=(1, 2))
        peak_after = np.abs(repaired).max(axis=(1, 2))
        sd_before = trials.std(axis=0).mean(axis=1)
        sd_after = repaired.std(axis=0).mean(axis=1)
        t_axis = np.arange(win_samp[0], win_samp[1]) / fs * 1000.0

        return dict(t_axis=t_axis, sd_before=sd_before, sd_after=sd_after,
                   peak_before=peak_before, peak_after=peak_after, n_trials=n_trials,
                   n_trials_touched=n_trials_touched, n_spikes=n_spikes, win_ms=win_ms)


def cross_trial_median_repair(nwb_path, session_label, probe_key, condition_task_numbers,
                              condition_label, win_ms=FAIR_WIN_MS, z_thresh=CROSS_TRIAL_Z_THRESH):
    """Single-condition version: runs _cross_trial_repair_core and draws its own 2-panel figure
    (cross-trial SD over time + outlier magnitude histogram). See that function's docstring for
    the method. Kept separate from the multi-condition grid below so single-condition callers
    don't have to build a 1-row grid."""
    r = _cross_trial_repair_core(nwb_path, session_label, probe_key, condition_task_numbers,
                                 condition_label, win_ms, z_thresh)
    t_axis, sd_before, sd_after = r["t_axis"], r["sd_before"], r["sd_after"]
    peak_before, peak_after, n_trials = r["peak_before"], r["peak_after"], r["n_trials"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    if True:
        axes[0].plot(t_axis, sd_before, color="0.2", lw=1.0, label="before")
        axes[0].plot(t_axis, sd_after, color="#D62728", lw=1.0, label="after (cross-trial median repair)")
        axes[0].set_xlabel("ms re p1 onset"); axes[0].set_ylabel("cross-trial SD (uV)")
        axes[0].set_title("Cross-trial variability over time"); axes[0].legend(fontsize=8)

        bins = np.logspace(np.log10(max(peak_before.min(), 1)), np.log10(peak_before.max()), 40)
        axes[1].hist(peak_before, bins=bins, color="0.6", alpha=0.6, label="before")
        axes[1].hist(peak_after, bins=bins, color="#D62728", alpha=0.6, label="after")
        axes[1].set_xscale("log")
        axes[1].set_xlabel(f"per-trial peak |LFP| across all channels, {win_ms[0]:.0f}.."
                           f"{win_ms[1]:.0f}ms (uV, log scale)")
        axes[1].set_ylabel("n trials")
        axes[1].set_title("Single-trial outlier magnitude (fair window)")
        axes[1].legend(fontsize=8)
        fig.suptitle(f"{session_label} -- {probe_key}, {condition_label}, cross-trial-median "
                    f"spike repair, {n_trials} trials", fontsize=10)
        fig.tight_layout()
        out = os.path.join(OUT_DIR, f"{session_label}_{probe_key}_{condition_label}_"
                                    f"crosstrial_repair.png")
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(f"[{session_label}] wrote {out}")
        print(f"[{session_label}] peak|LFP| p50/p90/p99/max before: "
             f"{np.percentile(peak_before,50):.1f}/{np.percentile(peak_before,90):.1f}/"
             f"{np.percentile(peak_before,99):.1f}/{peak_before.max():.1f} uV")
        print(f"[{session_label}] peak|LFP| p50/p90/p99/max after:  "
             f"{np.percentile(peak_after,50):.1f}/{np.percentile(peak_after,90):.1f}/"
             f"{np.percentile(peak_after,99):.1f}/{peak_after.max():.1f} uV")
        return r


def multi_condition_noise_reduction_grid(nwb_path, session_label, probe_key, conditions,
                                         win_ms=FAIR_WIN_MS, z_thresh=CROSS_TRIAL_Z_THRESH):
    """Runs _cross_trial_repair_core independently per condition (each condition's own
    cross-trial median/MAD -- pooling conditions together would blur the trial-locked evoked
    shape, which differs by condition, e.g. RRRR has no consistent deviant position while AAAB/
    BBBA do) and assembles one grid: one row per condition, cross-trial SD over time + outlier
    magnitude histogram per row -- so the amount of between-trial noise removed can be compared
    directly across conditions in one figure, per explicit direction."""
    rows = {}
    for label, task_numbers in conditions.items():
        rows[label] = _cross_trial_repair_core(nwb_path, session_label, probe_key, task_numbers,
                                                label, win_ms, z_thresh)

    n = len(rows)
    fig, axes = plt.subplots(n, 2, figsize=(14, 4.2 * n))
    if n == 1:
        axes = axes[None, :]
    for i, (label, r) in enumerate(rows.items()):
        t_axis, sd_before, sd_after = r["t_axis"], r["sd_before"], r["sd_after"]
        peak_before, peak_after, n_trials = r["peak_before"], r["peak_after"], r["n_trials"]
        mean_reduction = 1 - sd_after.mean() / sd_before.mean()

        ax0 = axes[i, 0]
        ax0.plot(t_axis, sd_before, color="0.2", lw=1.0, label="before")
        ax0.plot(t_axis, sd_after, color="#D62728", lw=1.0, label="after")
        ax0.set_xlabel("ms re p1 onset"); ax0.set_ylabel("cross-trial SD (uV)")
        ax0.set_title(f"{label} (n={n_trials} trials) -- cross-trial SD over time, "
                      f"{mean_reduction*100:.1f}% mean reduction", fontsize=9)
        if i == 0:
            ax0.legend(fontsize=8)

        ax1 = axes[i, 1]
        bins = np.logspace(np.log10(max(peak_before.min(), 1)), np.log10(peak_before.max()), 40)
        ax1.hist(peak_before, bins=bins, color="0.6", alpha=0.6, label="before")
        ax1.hist(peak_after, bins=bins, color="#D62728", alpha=0.6, label="after")
        ax1.set_xscale("log")
        ax1.set_xlabel(f"per-trial peak |LFP|, {win_ms[0]:.0f}..{win_ms[1]:.0f}ms (uV, log)")
        ax1.set_ylabel("n trials")
        ax1.set_title(f"{label} -- outlier magnitude, p99 {np.percentile(peak_before,99):.0f}->"
                      f"{np.percentile(peak_after,99):.0f}uV, max {peak_before.max():.0f}->"
                      f"{peak_after.max():.0f}uV", fontsize=9)
        if i == 0:
            ax1.legend(fontsize=8)

    fig.suptitle(f"{session_label} -- {probe_key}, between-trial noise removed by condition "
                f"(cross-trial-median repair, z>{z_thresh}, {win_ms[0]:.0f}..{win_ms[1]:.0f}ms)",
                fontsize=11, y=1.0)
    fig.tight_layout()
    out = os.path.join(OUT_DIR, f"{session_label}_{probe_key}_multicond_noise_reduction.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[{session_label}] wrote {out}")
    for label, r in rows.items():
        red = 1 - r["sd_after"].mean() / r["sd_before"].mean()
        print(f"[{session_label}] {label}: {r['n_trials']} trials, "
             f"{r['n_trials_touched']} touched ({r['n_trials_touched']/r['n_trials']*100:.1f}%), "
             f"mean cross-trial SD reduction {red*100:.1f}%, "
             f"peak|LFP| max {r['peak_before'].max():.0f}->{r['peak_after'].max():.0f}uV")
    return rows


if __name__ == "__main__":
    check_session(_P.nwb_dir() / "sub-V198o_ses-230714_rec.nwb", "V198o_230714", "probe_0_lfp")
    check_session(_P.nwb_dir() / "sub-V182o_ses-260629.nwb", "V182o_260629", "probe_0_lfp")
    check_session(_P.nwb_dir() / "sub-C31o_ses-230823_rec.nwb", "C31o_230823_control", "probe_0_lfp")

    aaab_trial_average_before_after(
        _P.nwb_dir() / "sub-V198o_ses-230714_rec.nwb", "V198o_230714", "probe_0_lfp",
        _P.REPO_ROOT / "outputs/lfp_artifact_repair/V198o_230714_probe_0_lfp_intervals.csv")
    aaab_trial_average_before_after(
        _P.nwb_dir() / "sub-V182o_ses-260629.nwb", "V182o_260629", "probe_0_lfp",
        _P.REPO_ROOT / "outputs/lfp_artifact_repair/V182o_260629_probe_0_lfp_intervals.csv")
