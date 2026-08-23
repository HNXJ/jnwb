r"""
Corpus-wide LFP bad-channel / bad-trial DETECTION (Hamm, 2026-08-17 -- "quickly implement").

Method: see jnwb/artifact_detection.py docstring. Channel QC = channel x channel correlation
outlier detection on a continuous raw segment; trial QC = per-good-channel trial x trial
correlation + max-amplitude outlier detection, with a trial excluded only by cross-channel
consensus (a real artifact is a shared event, seen on multiple good channels; a flag on one
channel alone more likely means that channel wasn't fully screened).

Per session, per probe present: loads raw continuous LFP (jnwb.paths-resolved NWB, h5py direct
per omission-data skill's documented per-subject layout differences), runs channel QC on a
CHANNEL_QC_SEGMENT_S continuous segment, then trial QC (TRIAL_WINDOW_MS around p1 onset, all
correct trials pooled across every GLO condition) on the surviving good channels.

Outputs:
    outputs/artifact_qc/lfp_bad_channels_trials_per_session.csv  (one row per session x probe)
    outputs/artifact_qc/lfp_bad_channels_trials_stats.json        (per-monkey/per-session summary)
    outputs/artifact_qc/lfp_bad_channels_trials_manifest.json

Run self-tests first: python -m pytest tests/test_artifact_detection.py
Then: python scripts/detect_lfp_bad_channels_trials.py [--max-sessions N] [--max-trials N]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "context" / "figures"))

from jnwb import paths as P
from jnwb.artifact_detection import (
    bad_channels_from_correlation,
    bad_trials_single_channel,
    channel_correlation_matrix,
    consensus_bad_trials,
)
from precompute_tfr_arrays import resolve_lfp_datasets  # renamed 2026-08-22 from precompute_tfr_arrays_v2
from _l_lfp_common import _probe_column, _dec, PROBE_LETTER_TO_KEY

OUT_DIR = REPO / "outputs" / "artifact_qc"
READINESS_CSV = REPO / "artifacts" / "data" / "session_readiness.csv"

CHANNEL_QC_SEGMENT_S = 120.0     # continuous segment used for channel-channel correlation
TRIAL_WINDOW_MS = (-200.0, 800.0)  # relative to p1 onset, used for trial-trial correlation
CHANNEL_Z_THRESH = 5.0
TRIAL_CORR_Z_THRESH = 5.0
TRIAL_AMP_Z_THRESH = 5.0
CONSENSUS_MIN_FRAC = 0.5
ANIMAL_ALIAS = {"V182o": "Ivan", "C31o": "Cajal", "V198o": "Joule"}


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO), stderr=subprocess.DEVNULL, text=True
        )
        return out.strip()
    except Exception:
        return "unknown"


def probes_present(f: h5py.File) -> list:
    et = f["general/extracellular_ephys/electrodes"]
    grp = _probe_column(et)
    present = sorted(set(grp))
    out = []
    for letter, key in PROBE_LETTER_TO_KEY.items():
        if f"probe{letter}" in present and key in f.get("acquisition", {}):
            out.append((letter, key))
    return out


def probe_channel_range(f: h5py.File, probe_letter: str) -> tuple:
    """Channel count for this probe, as a (0, n_channels) range LOCAL to that probe's own LFP
    dataset -- each probe_N_lfp array has its own independent 0-based column indexing, NOT a
    slice of one global electrode-table row range (confirmed: probe_0/1/2_lfp are each their
    own (n_samples, 128) array here, not a shared (n_samples, 384) array sliced by global
    electrode-table position). Using electrode-table row indices directly as LFP-array column
    indices silently produced out-of-bounds, empty-shape slices for every non-first probe."""
    et = f["general/extracellular_ephys/electrodes"]
    grp = _probe_column(et)
    idx = np.where(grp == f"probe{probe_letter}")[0]
    if len(idx) == 0:
        return None
    return 0, len(idx)


def all_correct_p1_onsets_s(f: h5py.File) -> np.ndarray:
    g = f["intervals/omission_glo_passive"]
    sn = np.asarray(g["stimulus_number"][:], dtype=float)
    corr = np.asarray(g["correct"][:], dtype=float)
    st = np.asarray(g["start_time"][:], dtype=float)
    mask = (sn == 2) & (corr == 1) & np.isfinite(sn) & np.isfinite(st)
    return np.sort(st[mask])


def run_session_probe(f: h5py.File, lfp_key: str, ch_lo: int, ch_hi: int, max_trials: int = None) -> dict:
    data, ts, fs = resolve_lfp_datasets(f, lfp_key)
    n_channels = ch_hi - ch_lo

    # --- channel QC on a continuous segment ---
    n_seg = min(int(CHANNEL_QC_SEGMENT_S * fs), data.shape[0])
    seg = np.asarray(data[:n_seg, ch_lo:ch_hi], dtype=np.float64).T  # (n_channels, n_samples)
    seg = np.nan_to_num(seg, nan=0.0, posinf=0.0, neginf=0.0)
    corr = channel_correlation_matrix(seg)
    bad_ch_mask, ch_summary, ch_z = bad_channels_from_correlation(corr, z_thresh=CHANNEL_Z_THRESH)
    good_local_idx = np.where(~bad_ch_mask)[0]

    # --- trial QC on good channels ---
    onsets = all_correct_p1_onsets_s(f)
    if max_trials is not None:
        onsets = onsets[:max_trials]
    n_trials = len(onsets)

    if n_trials == 0 or len(good_local_idx) == 0:
        return {
            "n_channels": n_channels, "n_bad_channels": int(bad_ch_mask.sum()),
            "bad_channel_local_idx": bad_ch_mask.nonzero()[0].tolist(),
            "n_trials": n_trials, "n_bad_trials_consensus": 0,
            "consensus_bad_trial_idx": [], "fs": fs,
        }

    win0_s, win1_s = TRIAL_WINDOW_MS[0] / 1000.0, TRIAL_WINDOW_MS[1] / 1000.0
    need = int(round((win1_s - win0_s) * fs))

    # This HDF5 dataset is chunked across the FULL channel width per time-chunk (confirmed by
    # direct profiling: reading one channel's entire trace takes ~30s because every chunk read
    # must decompress all 128 channels just to extract 1 column, vs. a same-sized ALL-channel
    # slice which is ~1000x faster). So read ALL channels at once per trial (one 2D read per
    # trial, matching _l_lfp_common.extract_epoch_trials' pattern), not one channel at a time.
    trial_stack = np.empty((n_trials, ch_hi - ch_lo, need))  # (n_trials, n_channels, n_times)
    for ti, onset in enumerate(onsets):
        t0, t1 = onset + win0_s, onset + win1_s
        if ts is not None:
            i0, i1 = int(np.searchsorted(ts, t0)), int(np.searchsorted(ts, t1))
        else:
            i0, i1 = int(round(t0 * fs)), int(round(t1 * fs))
        i0c, i1c = max(0, i0), min(data.shape[0], i1)
        raw = np.asarray(data[i0c:i1c, ch_lo:ch_hi], dtype=np.float64)  # (n_times, n_channels)
        raw = np.nan_to_num(raw, nan=0.0, posinf=0.0, neginf=0.0)
        if raw.shape[0] < need:
            raw = np.pad(raw, ((0, need - raw.shape[0]), (0, 0)), mode="edge") if raw.shape[0] > 0 \
                else np.zeros((need, ch_hi - ch_lo))
        elif raw.shape[0] > need:
            raw = raw[:need]
        trial_stack[ti] = raw.T  # (n_channels, n_times)

    per_channel_flags = []
    for local_ch in good_local_idx:
        trial_wave = trial_stack[:, int(local_ch), :]  # (n_trials, n_times)
        flag, _, _ = bad_trials_single_channel(
            trial_wave, corr_z_thresh=TRIAL_CORR_Z_THRESH, amp_z_thresh=TRIAL_AMP_Z_THRESH
        )
        per_channel_flags.append(flag)

    per_channel_flags = np.vstack(per_channel_flags)
    consensus, frac = consensus_bad_trials(per_channel_flags, min_frac_channels=CONSENSUS_MIN_FRAC)

    return {
        "n_channels": n_channels, "n_bad_channels": int(bad_ch_mask.sum()),
        "bad_channel_local_idx": bad_ch_mask.nonzero()[0].tolist(),
        "n_trials": n_trials, "n_bad_trials_consensus": int(consensus.sum()),
        "consensus_bad_trial_idx": consensus.nonzero()[0].tolist(), "fs": fs,
        "n_good_channels_used_for_trial_qc": len(good_local_idx),
    }


def run(max_sessions: int = None, max_trials: int = None) -> pd.DataFrame:
    readiness = pd.read_csv(READINESS_CSV)
    ready = readiness[readiness["nwb_ok"] == True].copy()
    if max_sessions is not None:
        ready = ready.head(max_sessions)

    rows = []
    t0 = time.time()
    for si, row in enumerate(ready.itertuples(index=False), start=1):
        prefix = row.session_prefix
        subject = row.subject
        path = P.resolve_nwb_path(prefix)
        if not path.exists():
            print(f"  [{si}/{len(ready)}] MISSING nwb for {prefix}, skipping")
            continue
        try:
            with h5py.File(str(path), "r") as f:
                probes = probes_present(f)
                for letter, key in probes:
                    ch_range = probe_channel_range(f, letter)
                    if ch_range is None:
                        continue
                    ch_lo, ch_hi = ch_range
                    res = run_session_probe(f, key, ch_lo, ch_hi, max_trials=max_trials)
                    rows.append({
                        "session": prefix, "subject": subject,
                        "animal_alias": ANIMAL_ALIAS.get(subject, subject),
                        "probe": letter, **res,
                    })
        except Exception as e:
            print(f"  [{si}/{len(ready)}] FAILED {prefix}: {e}")
            continue
        elapsed = time.time() - t0
        print(f"  [{si}/{len(ready)}] {prefix}: {len(probes)} probes, {elapsed:.0f}s elapsed")

    return pd.DataFrame(rows)


def build_stats(df: pd.DataFrame) -> dict:
    df = df.copy()
    df["pct_bad_channels"] = 100.0 * df["n_bad_channels"] / df["n_channels"].replace(0, np.nan)
    df["pct_bad_trials"] = 100.0 * df["n_bad_trials_consensus"] / df["n_trials"].replace(0, np.nan)

    per_session = (
        df.groupby(["session", "animal_alias"])
        .agg(n_channels_total=("n_channels", "sum"), n_bad_channels_total=("n_bad_channels", "sum"),
             n_trials_total=("n_trials", "max"),  # trials are session-level, not per-probe -- max not sum
             n_bad_trials_consensus_max=("n_bad_trials_consensus", "max"))
        .reset_index()
    )
    per_session["pct_bad_channels"] = 100.0 * per_session["n_bad_channels_total"] / per_session["n_channels_total"]
    per_session["pct_bad_trials"] = 100.0 * per_session["n_bad_trials_consensus_max"] / per_session["n_trials_total"]

    per_animal = (
        per_session.groupby("animal_alias")
        .agg(n_sessions=("session", "nunique"),
             mean_pct_bad_channels=("pct_bad_channels", "mean"),
             mean_pct_bad_trials=("pct_bad_trials", "mean"),
             total_channels=("n_channels_total", "sum"),
             total_bad_channels=("n_bad_channels_total", "sum"))
        .reset_index()
    )

    return {
        "id": "lfp_bad_channels_trials_detection",
        "method_source": "jnwb/artifact_detection.py",
        "channel_qc_segment_s": CHANNEL_QC_SEGMENT_S,
        "trial_window_ms": list(TRIAL_WINDOW_MS),
        "channel_z_thresh": CHANNEL_Z_THRESH,
        "trial_corr_z_thresh": TRIAL_CORR_Z_THRESH,
        "trial_amp_z_thresh": TRIAL_AMP_Z_THRESH,
        "consensus_min_frac_channels": CONSENSUS_MIN_FRAC,
        "per_session_probe": json.loads(df.to_json(orient="records")),
        "per_session": json.loads(per_session.to_json(orient="records")),
        "per_animal": json.loads(per_animal.to_json(orient="records")),
        "corpus_pct_bad_channels": float(per_session["n_bad_channels_total"].sum() / per_session["n_channels_total"].sum() * 100.0),
        "corpus_pct_bad_trials_mean_of_sessions": float(per_session["pct_bad_trials"].mean()),
        "git_sha": _git_sha(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-sessions", type=int, default=None)
    ap.add_argument("--max-trials", type=int, default=None)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = run(max_sessions=args.max_sessions, max_trials=args.max_trials)
    df.to_csv(OUT_DIR / "lfp_bad_channels_trials_per_session.csv", index=False)
    stats = build_stats(df)
    (OUT_DIR / "lfp_bad_channels_trials_stats.json").write_text(json.dumps(stats, indent=2))
    manifest = {
        "method": "detect_lfp_bad_channels_trials", "git_sha": _git_sha(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_sessions": df["session"].nunique(), "n_session_probe_rows": len(df),
        "max_sessions_arg": args.max_sessions, "max_trials_arg": args.max_trials,
    }
    (OUT_DIR / "lfp_bad_channels_trials_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nDone. {df['session'].nunique()} sessions, {len(df)} session-probe rows written to {OUT_DIR}")
