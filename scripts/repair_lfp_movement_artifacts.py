r"""
Session-wise movement-artifact detection and in-place-of-rejection repair for V198o/V182o LFP.

WHY SESSION-WISE, NOT PROBE-BY-PROBE
    All probes within one session share an identical sample clock (verified: same n_samples,
    same ts[0]/ts[-1] on every probe of both V198o and V182o). A genuine movement/mechanical
    artifact should therefore appear at the same sample index on every probe at once, which is
    corroborating evidence the earlier single-probe check couldn't provide. Detection here
    pools the per-probe synchrony statistic across all of a session's probes before flagging an
    interval, and reports how many probes corroborate each event.

WHY REPAIR, NOT REJECT
    Per explicit direction: do not drop trials. Detected intervals (padded to cover the onset/
    decay ramp, not just the peak) are repaired by per-channel linear interpolation between the
    samples immediately flanking the padded window -- standard practice for isolated,
    short-duration artifacts (the analogous fix to blink interpolation in EEG). This leaves
    every sample outside a detected interval completely untouched, unlike a temporal filter
    applied blindly across the whole trace.

DETECTOR (same statistic as check_lfp_movement_artifacts.py)
    Per channel: robust z-score via (x - median) / (1.4826 * MAD), so one channel's own noise
    floor doesn't distort the others. Per timepoint: median(|z|) across a probe's 128 channels.
    A genuine shared deflection pushes most channels' |z| up together; independent per-channel
    noise does not. Threshold Z_THRESH, flagged samples merged into intervals with PAD_MS on
    each side, adjacent intervals within MERGE_GAP_MS coalesced into one.

OUTPUT
    outputs/lfp_artifact_repair/<session>_intervals.csv -- one row per detected, session-level
    interval: start_time, end_time, n_probes_corroborating, peak_z_per_probe.
    outputs/qc_lfp_artifacts/<session>_repair_before_after.png -- visual proof on the same
    reference window used in the original check.

NOT DONE HERE: no NWB file is modified. This produces an interval table plus a reusable
`interpolate_intervals()` repair function; a downstream extraction script applies it to
whatever window it pulls, on the fly -- materializing a repaired copy of a ~16M-sample x
128-channel x N-probe session would cost tens of GB per session for no benefit over repairing
on demand at trial-extraction time.
"""
from __future__ import annotations

import os
import sys
import time

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(REPO))
sys.path.insert(0, os.path.join(os.path.dirname(REPO), "scripts", "archive_oneoff"))
from precompute_tfr_arrays import resolve_lfp_datasets  # noqa: E402
from jnwb import paths as _P
from jnwb.artifact_repair import (interpolate_intervals as _jnwb_interpolate_intervals,
                                  flagged_to_intervals as _jnwb_flagged_to_intervals)

OUT_DIR = _P.REPO_ROOT / "outputs/lfp_artifact_repair"
QC_DIR = _P.REPO_ROOT / "outputs/qc_lfp_artifacts"
Z_THRESH = 6.0
PAD_MS = 40.0          # padding on each side of a flagged run, to cover onset/decay ramp
MERGE_GAP_MS = 100.0   # adjacent padded intervals closer than this are coalesced
BLOCK = 1_000_000      # samples per chunk when scanning a full session


def probe_synchrony_z(data, block=BLOCK):
    """Chunked per-timepoint synchrony statistic for one probe's (samples x channels) dataset,
    without loading the whole array into memory."""
    n = data.shape[0]
    out = np.empty(n, dtype=np.float32)
    for start in range(0, n, block):
        end = min(start + block, n)
        seg = data[start:end, :]
        med = np.median(seg, axis=0, keepdims=True)
        mad = np.median(np.abs(seg - med), axis=0, keepdims=True) * 1.4826
        mad = np.where(mad < 1e-9, 1e-9, mad)
        z = np.abs((seg - med) / mad)
        out[start:end] = np.median(z, axis=1)
    return out


def _to_numeric(arr):
    if arr.dtype.kind in ("O", "S", "U"):
        return np.array([float(x.decode() if isinstance(x, bytes) else x) for x in arr], dtype=float)
    return arr.astype(float)


REWARD_WINDOW_MS = (4000.0, 4300.0)   # generous margin around the measured ~4120-4142ms latency


def reward_adjacent_mask(f, n_samples, fs, window_ms=REWARD_WINDOW_MS):
    """True for every sample within `window_ms` of ANY correct trial's p1 onset (any condition,
    not just AAAB) -- reward is delivered at an essentially fixed latency post-p1 (measured:
    V182o 4139-4142ms, V198o 4120-4138ms, <20ms jitter across trials), confirmed directly
    against the reward_1_tracking channel, not assumed. Per explicit direction, reward-locked
    events are a separate category from movement artifact and must not be repaired by this
    detector -- excluding this window keeps the two apart instead of silently conflating them."""
    g = f["intervals/omission_glo_passive"]
    sn = _to_numeric(g["stimulus_number"][:])
    corr = _to_numeric(g["correct"][:])
    st = _to_numeric(g["start_time"][:])
    onsets = np.sort(st[(sn == 2) & (corr == 1) & np.isfinite(st)])
    mask = np.zeros(n_samples, dtype=bool)
    lo = int(round(window_ms[0] / 1000.0 * fs))
    hi = int(round(window_ms[1] / 1000.0 * fs))
    for onset in onsets:
        c = int(round(onset * fs))
        s, e = max(0, c + lo), min(n_samples, c + hi)
        if e > s:
            mask[s:e] = True
    return mask


def flagged_to_intervals(flagged, fs, pad_ms=PAD_MS, merge_gap_ms=MERGE_GAP_MS):
    return _jnwb_flagged_to_intervals(flagged, fs, pad_ms=pad_ms, merge_gap_ms=merge_gap_ms)


def detect_session(nwb_path, session_label, probe_names):
    """Returns (union_df, per_probe_intervals, fs). union_df is for REPORTING/corroboration
    only -- e.g. probe_0 in V182o turned out to carry 302 of 382 single-probe events with the
    other 3 probes sitting at background z (median ~2-3, well under the z=8 threshold) at those
    same timestamps, confirmed by direct inspection, not assumed -- so those are probe_0-local
    events, not a session-wide artifact at sub-threshold amplitude elsewhere. Repair MUST use
    per_probe_intervals (each probe's own crossings only), not the union, or it would
    interpolate real, uncontaminated signal on probes 1-3 at probe_0-only event times."""
    os.makedirs(OUT_DIR, exist_ok=True)
    per_probe_z = {}
    fs_ref = None
    with h5py.File(nwb_path, "r") as f:
        for pname in probe_names:
            cache_path = os.path.join(OUT_DIR, f"{session_label}_{pname}_synchrony_z.npy")
            if os.path.exists(cache_path):
                z = np.load(cache_path)
                per_probe_z[pname] = z
                _, _, fs_ref = resolve_lfp_datasets(f, pname)
                print(f"[{session_label}] {pname}: loaded cached synchrony-z ({cache_path}), "
                     f"max z={z.max():.1f}, {(z > Z_THRESH).mean()*100:.4f}% flagged at "
                     f"z>{Z_THRESH}")
                continue
            data, ts, fs = resolve_lfp_datasets(f, pname)
            fs_ref = fs
            t0 = time.time()
            z = probe_synchrony_z(data)
            per_probe_z[pname] = z
            np.save(cache_path, z)
            print(f"[{session_label}] {pname}: scanned {len(z)} samples in {time.time()-t0:.0f}s, "
                 f"max z={z.max():.1f}, {(z > Z_THRESH).mean()*100:.4f}% flagged at z>{Z_THRESH} "
                 f"(cached -> {cache_path})")

    n = len(next(iter(per_probe_z.values())))
    with h5py.File(nwb_path, "r") as f:
        reward_mask = reward_adjacent_mask(f, n, fs_ref)
    print(f"[{session_label}] reward-adjacent mask ({REWARD_WINDOW_MS[0]:.0f}-"
         f"{REWARD_WINDOW_MS[1]:.0f}ms post any correct p1): "
         f"{reward_mask.mean()*100:.3f}% of session excluded from repair eligibility")

    per_probe_intervals = {}
    per_probe_reward_excluded = {}
    for p, z in per_probe_z.items():
        raw_flag = z > Z_THRESH
        keep_flag = raw_flag & ~reward_mask
        per_probe_intervals[p] = flagged_to_intervals(keep_flag, fs_ref)
        per_probe_reward_excluded[p] = flagged_to_intervals(raw_flag & reward_mask, fs_ref)
    for p, ivs in per_probe_intervals.items():
        pd.DataFrame(ivs, columns=["start_idx", "end_idx"]).assign(
            start_time=lambda d: d.start_idx / fs_ref, end_time=lambda d: d.end_idx / fs_ref
        ).to_csv(os.path.join(OUT_DIR, f"{session_label}_{p}_intervals.csv"), index=False)
    for p, ivs in per_probe_reward_excluded.items():
        pd.DataFrame(ivs, columns=["start_idx", "end_idx"]).assign(
            start_time=lambda d: d.start_idx / fs_ref, end_time=lambda d: d.end_idx / fs_ref
        ).to_csv(os.path.join(OUT_DIR, f"{session_label}_{p}_reward_excluded.csv"), index=False)
    print(f"[{session_label}] per-probe interval counts (movement-eligible, reward window "
         f"excluded): {{{', '.join(f'{p}: {len(v)}' for p, v in per_probe_intervals.items())}}}")
    print(f"[{session_label}] per-probe reward-adjacent counts (NOT repaired, separate "
         f"category): {{{', '.join(f'{p}: {len(v)}' for p, v in per_probe_reward_excluded.items())}}}")

    # session-level union, for corroboration REPORTING only (not used for repair)
    any_flag = np.zeros(n, dtype=bool)
    for z in per_probe_z.values():
        any_flag |= z > Z_THRESH
    intervals = flagged_to_intervals(any_flag, fs_ref)

    rows = []
    for s, e in intervals:
        n_corrob = sum(1 for z in per_probe_z.values() if (z[s:e] > Z_THRESH).any())
        peak_by_probe = {pname: float(z[s:e].max()) for pname, z in per_probe_z.items()}
        rows.append({
            "session": session_label, "start_idx": s, "end_idx": e,
            "start_time": s / fs_ref, "end_time": e / fs_ref,
            "duration_ms": (e - s) / fs_ref * 1000,
            "n_probes_total": len(probe_names),
            "n_probes_corroborating": n_corrob,
            **{f"peak_z_{p}": v for p, v in peak_by_probe.items()},
        })
    df = pd.DataFrame(rows)
    out_csv = os.path.join(OUT_DIR, f"{session_label}_intervals.csv")
    df.to_csv(out_csv, index=False)
    print(f"[{session_label}] {len(df)} session-level (union, reporting-only) intervals -> {out_csv}")
    if len(df):
        corrob_counts = df.n_probes_corroborating.value_counts().sort_index()
        print(f"[{session_label}] corroboration (n_probes agreeing) histogram:\n{corrob_counts}")
    return df, per_probe_intervals, fs_ref


def interpolate_intervals(seg, fs, intervals_local):
    """Thin wrapper over jnwb.artifact_repair.interpolate_intervals, keeping this file's
    original 3-arg call signature (``fs`` was always unused in the body -- dead param, kept
    only so the one call site below doesn't need to change)."""
    return _jnwb_interpolate_intervals(seg, intervals_local)


def demo_before_after(nwb_path, session_label, probe_name, probe_intervals, zoom_t0, zoom_dur):
    """probe_intervals: this probe's OWN (start_idx, end_idx) list (session-global indices),
    not the cross-probe union -- see detect_session docstring for why that distinction matters."""
    with h5py.File(nwb_path, "r") as f:
        data, ts, fs = resolve_lfp_datasets(f, probe_name)
        i0, i1 = int(zoom_t0 * fs), int((zoom_t0 + zoom_dur) * fs)
        seg = data[i0:i1, :]
        local_intervals = []
        for s, e in probe_intervals:
            s, e = s - i0, e - i0
            if e > 0 and s < seg.shape[0]:
                local_intervals.append((s, e))
        repaired = interpolate_intervals(seg, fs, local_intervals)

        t_axis = np.arange(i0, i1) / fs - zoom_t0
        n_ch = seg.shape[1]
        offset_step = np.percentile(np.abs(seg), 99) * 2.2
        fig, axes = plt.subplots(1, 2, figsize=(16, 12), sharey=True)
        for ch in range(n_ch):
            axes[0].plot(t_axis, seg[:, ch] + ch * offset_step, color="black", lw=0.4)
            axes[1].plot(t_axis, repaired[:, ch] + ch * offset_step, color="black", lw=0.4)
        for s, e in local_intervals:
            axes[1].axvspan(t_axis[max(s, 0)], t_axis[min(e, len(t_axis) - 1)],
                           color="red", alpha=0.15)
        axes[0].set_title("before: raw", fontsize=10)
        axes[1].set_title("after: interpolated over detected intervals "
                          "(shaded = repaired span)", fontsize=10)
        for ax in axes:
            ax.set_yticks([]); ax.set_xlabel("time (s)")
        fig.suptitle(f"{session_label} -- {probe_name}, session-wise detection, "
                    f"linear-interpolation repair", fontsize=11)
        fig.tight_layout()
        out = os.path.join(QC_DIR, f"{session_label}_{probe_name}_repair_before_after.png")
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(f"[{session_label}] wrote {out}, amp before [{seg.min():.0f},{seg.max():.0f}] "
             f"after [{repaired.min():.0f},{repaired.max():.0f}]")


if __name__ == "__main__":
    v198_probes = ["probe_0_lfp", "probe_1_lfp"]
    v182_probes = ["probe_0_lfp", "probe_1_lfp", "probe_2_lfp", "probe_3_lfp"]

    df198, pp198, fs198 = detect_session(_P.nwb_dir() / "sub-V198o_ses-230714_rec.nwb",
                                         "V198o_230714", v198_probes)
    df182, pp182, fs182 = detect_session(_P.nwb_dir() / "sub-V182o_ses-260629.nwb",
                                         "V182o_260629", v182_probes)

    demo_before_after(_P.nwb_dir() / "sub-V198o_ses-230714_rec.nwb", "V198o_230714",
                      "probe_0_lfp", pp198["probe_0_lfp"], zoom_t0=5938.37 + 160, zoom_dur=25)
    demo_before_after(_P.nwb_dir() / "sub-V182o_ses-260629.nwb", "V182o_260629",
                      "probe_0_lfp", pp182["probe_0_lfp"], zoom_t0=4960.77 + 118, zoom_dur=20)
