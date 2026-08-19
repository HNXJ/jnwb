#!/usr/bin/env python3
r"""
Precompute trial-aligned TFR .npz arrays from NWB LFP via h5py.

SUPERSEDES scripts/archive_oneoff/precompute_tfr_arrays.py for regeneration of the
TFR-array product corpus after the 2026-08-08 D:-drive migration (D:/workspace/data/tfr_arrays
-> D:/nwb/omission + D:/analysis; see artifacts/.lab/data-volume-layout-and-tfr-spec-transfer
-20260808.json). Three material changes, all requested 2026-08-11 (Main-Figure Sprint,
Fig05/Fig06 shared TFR-corpus rebuild):

1. CHANNEL SCREEN + REAL PER-AREA SUBSET (not "all 128, padded"). The old script wrote every
   probe's full 128-channel array, padded with zeros where the probe had fewer, once PER AREA
   TOKEN on dual-area probes -- i.e. a dual-area probe wrote the SAME full 128-channel array
   twice, and every channel outside the file's own area was carried anyway. Measured on 4
   existing files: 0.9-3.5 GB EACH for one session/probe/area/condition. The historical full
   corpus (23 sessions, ~1,236 files, same contract) would need on this order of 2+ TB, which
   does not fit the 931 GiB free on D: (data-volume-layout-and-tfr-spec-transfer-20260808.json,
   claim-corpus-fits-the-budget -- that budget was sized for a DIFFERENT, per-group-summary
   format, not this per-trial array format). This version writes ONLY the channels the
   per-channel area vector (outputs/channel_area_vector/channel_area_vector.csv) assigns to
   the file's area token, AND only channels passing the 1/f quality screen below -- both
   reductions are real, not padding removal alone (median 64-of-128 real channels per area
   group; quality screen removes some fraction of those). The array's channel axis no longer
   maps directly to raw probe-channel index 0-127; the ORIGINAL indices actually included are
   saved alongside as the "channels" array in the same .npz, sorted ascending, so any consumer
   can recover which physical channel each column is.

2. CHANNEL-QUALITY (1/f) SCREEN. Per candidate channel, omission.jnwb_ext.spectral.spectral_tilt() is run
   once on a representative raw-LFP segment (the full session, subsampled) to fit the aperiodic
   exponent and R^2. A channel is KEPT only if exponent < 0 (power decreasing with frequency,
   the expected LFP aperiodic shape) and fit_quality (R^2) >= MIN_FIT_R2. This is a real,
   per-channel exclusion of electrodes with a flat, positive, or noise-dominated spectrum
   (broken/saturated/line-noise-dominated contacts), not a cosmetic filter -- excluded channels
   never enter the spectrogram computation (so this also cuts compute, not just storage).

3. COMPRESSED OUTPUT, GPU SPECTROGRAM WHERE VALIDATED. Saved via np.savez_compressed (gzip
   deflate) instead of raw np.save; the array itself is float32 throughout (unchanged from the
   old script -- it already avoided the float64 overflow/size cost at the save step, though the
   old script summed in float64 up to that point, which this version keeps). A cupy-accelerated
   batched STFT-power path is used ONLY if cupy successfully imports, a CUDA device is visible,
   AND its output is numerically validated against scipy.signal.spectrogram on a synthetic
   multi-tone test signal at startup (max relative error < GPU_VALIDATION_TOL). If any of those
   fail, the original per-channel scipy.signal.spectrogram CPU path runs unchanged and a
   warning is printed naming which check failed -- GPU availability is a property of the
   machine, not the repo, and this path must never run unvalidated (numerical-computing skill;
   CLAUDE.md "every accelerated path needs a working CPU path").

CONSUMERS MUST BE UPDATED to read this format (glob "*.npz", not "*.npy"; load "power" and
"channels" keys; map channel indices through "channels" rather than treating the array's
channel axis as raw probe index 0-127). scripts/compute_channel_band_power_census_v2.py was
updated to support both formats as part of this same change (2026-08-11); any other consumer
(e.g. scripts/extract_condition_tfr_maps.py, used by Figure 06) needs the same update before
it can read output written by this script -- tracked separately under the Figure 06 task.

Output contract:
  {session_prefix}-{A|B|C|D}-{area}-{CONDITION}.npz, keys:
    power:    (n_trials, n_channels_kept, 99, 500) float32
    channels: (n_channels_kept,) int32 -- original probe-channel indices, ascending
    fit_exponent: (n_channels_kept,) float32 -- 1/f exponent for each kept channel
    fit_r2:       (n_channels_kept,) float32 -- 1/f fit R^2 for each kept channel
  freqs = arange(3, 201, 2); times = -1000 + arange(500)*10 ms (p1-aligned)

V182o LFP nesting: acquisition/{key}/{key}_data/data
C31o/V198o nesting: acquisition/{key}/data
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import h5py
import numpy as np
import pandas as pd
from scipy import signal

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from jnwb import paths as oa_paths
from omission.jnwb_ext.spectral import spectral_tilt

FREQS_HZ = np.arange(3, 201, 2)  # 99
N_TIMES = 500
PRE_MS = 1000.0
POST_MS = 4000.0  # total window 5000 ms -> 500 bins @ 10 ms
BIN_MS = 10.0

MIN_FIT_R2 = 0.4          # 1/f fit quality floor
QUALITY_SEGMENT_S = 60.0  # seconds of raw LFP used per channel for the 1/f screen
GPU_VALIDATION_TOL = 1e-4  # max relative error vs scipy before the GPU path is trusted

AREA_VEC_PATH = oa_paths.REPO_ROOT / "outputs" / "channel_area_vector" / "channel_area_vector.csv"

# Same crosswalk as archive_oneoff/precompute_tfr_arrays.py -- unchanged, not part of this fix.
CONDITION_NUMBERS: Dict[str, Tuple[int, ...]] = {
    "AAAB": tuple(range(1, 3)),
    "AXAB": (3,),
    "AAXB": (4,),
    "AAAX": (5,),
    "BBBA": tuple(range(6, 8)),
    "BXBA": (8,),
    "BBXA": (9,),
    "BBBX": (10,),
    "RRRR": tuple(range(11, 27)),
    "RXRR": tuple(range(27, 35)),
    "RRXR": (35, 37, 39, 41),
    "RRRX": (36, 38, 40, *range(42, 51)),
}
CONDITION_NUMBERS_V182O: Dict[str, Tuple[int, ...]] = dict(CONDITION_NUMBERS, **{
    "RRXR": tuple(range(35, 43)),
    "RRRX": tuple(range(43, 51)),
})


def condition_numbers_for(filename: str) -> Dict[str, Tuple[int, ...]]:
    return CONDITION_NUMBERS_V182O if "V182o" in str(filename) else CONDITION_NUMBERS


PROBE_LETTER = {"probe_0_lfp": "A", "probe_1_lfp": "B", "probe_2_lfp": "C", "probe_3_lfp": "D"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--nwb", type=Path, required=True, help="Path to .nwb")
    p.add_argument("--out-dir", type=Path, default=oa_paths.tfr_dir())
    p.add_argument("--meta-root", type=Path, default=oa_paths.meta_dir())
    p.add_argument("--conditions", default="RRRR,RXRR,RRXR,RRRX",
                   help="Comma-separated condition codes")
    p.add_argument("--areas", default=None, help="Optional comma-separated area filter")
    p.add_argument("--max-trials", type=int, default=None, help="Cap trials (smoke)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--gpu", choices=["auto", "cpu", "cuda"], default="auto")
    return p.parse_args()


def session_prefix_from_nwb(nwb: Path) -> str:
    stem = nwb.stem
    return stem[: -len("_rec")] if stem.endswith("_rec") else stem


def resolve_lfp_datasets(f: h5py.File, lfp_key: str):
    root = f[f"acquisition/{lfp_key}"]
    if "data" in root:
        data = root["data"]
        ts = root["timestamps"][:] if "timestamps" in root else None
    else:
        nested = f"{lfp_key}_data"
        if nested not in root:
            raise KeyError(f"No data under acquisition/{lfp_key}")
        g = root[nested]
        data = g["data"]
        ts = g["timestamps"][:] if "timestamps" in g else None
    if ts is not None and len(ts) > 1:
        fs = float(1.0 / np.median(np.diff(ts)))
    else:
        fs = 1000.0
    return data, ts, fs


def _to_numeric(arr: np.ndarray) -> np.ndarray:
    if arr.dtype.kind in ("O", "S", "U"):
        return np.array([float(x.decode() if isinstance(x, bytes) else x) for x in arr], dtype=float)
    return arr.astype(float)


def p1_onsets_s(f: h5py.File, condition: str) -> np.ndarray:
    g = f["intervals/omission_glo_passive"]
    sn = _to_numeric(g["stimulus_number"][:])
    corr = _to_numeric(g["correct"][:])
    tc = _to_numeric(g["task_condition_number"][:])
    st = _to_numeric(g["start_time"][:])
    nums = condition_numbers_for(f.filename)[condition]
    mask = (sn == 2) & (corr == 1) & np.isin(tc, nums)
    mask = mask & np.isfinite(sn) & np.isfinite(st)
    return np.asarray(st[mask], dtype=float)


# ---------------------------------------------------------------------------------------
# Channel-quality (1/f) screen
# ---------------------------------------------------------------------------------------

def screen_channels(data, fs: float, candidate_channels: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Run spectral_tilt() on a representative raw segment per candidate channel.

    Returns (kept_channels, exponents_for_kept, r2_for_kept), all sorted ascending by channel.
    """
    n_samp = min(int(QUALITY_SEGMENT_S * fs), data.shape[0])
    seg = np.asarray(data[:n_samp, :], dtype=np.float64)
    kept, exps, r2s = [], [], []
    for ch in candidate_channels:
        ch = int(ch)
        if ch >= seg.shape[1]:
            continue
        tilt = spectral_tilt(seg[:, ch], sampling_rate=fs)
        if tilt["exponent"] < 0.0 and tilt["fit_quality"] >= MIN_FIT_R2:
            kept.append(ch)
            exps.append(tilt["exponent"])
            r2s.append(tilt["fit_quality"])
    order = np.argsort(kept)
    kept = np.asarray(kept, dtype=np.int32)[order]
    exps = np.asarray(exps, dtype=np.float32)[order]
    r2s = np.asarray(r2s, dtype=np.float32)[order]
    return kept, exps, r2s


# ---------------------------------------------------------------------------------------
# Spectrogram: CPU reference (unchanged math from archive_oneoff/precompute_tfr_arrays.py)
# and an optional GPU batched path, numerically validated against it before use.
# ---------------------------------------------------------------------------------------

def _spectrogram_params(fs: float):
    nperseg = max(64, int(round(fs * 0.2)))  # 200 ms
    noverlap = nperseg - int(round(fs * BIN_MS / 1000.0))
    noverlap = max(0, min(noverlap, nperseg - 1))
    return nperseg, noverlap


def spectrogram_trial_cpu(seg: np.ndarray, fs: float) -> np.ndarray:
    """seg: (n_samples, n_channels_kept) -> (n_channels_kept, 99, 500) power, float32."""
    nperseg, noverlap = _spectrogram_params(fs)
    f_sg, t_sg, _ = signal.spectrogram(seg[:, 0], fs=fs, window="hann", nperseg=nperseg,
                                       noverlap=noverlap, detrend=False, scaling="spectrum",
                                       mode="psd")
    t_ms = t_sg * 1000.0 - PRE_MS
    out_t = -PRE_MS + np.arange(N_TIMES) * BIN_MS
    n_ch = seg.shape[1]
    out = np.zeros((n_ch, len(FREQS_HZ), N_TIMES), dtype=np.float32)
    from_f = np.asarray(f_sg, dtype=float)
    for c in range(n_ch):
        _, _, Sxx = signal.spectrogram(seg[:, c], fs=fs, window="hann", nperseg=nperseg,
                                       noverlap=noverlap, detrend=False, scaling="spectrum",
                                       mode="psd")
        S_f = np.vstack([np.interp(FREQS_HZ, from_f, Sxx[:, j]) for j in range(Sxx.shape[1])]).T
        for fi in range(len(FREQS_HZ)):
            out[c, fi, :] = np.interp(out_t, t_ms, S_f[fi]).astype(np.float32)
    return out


def _gpu_backend():
    """Return the cupy module if import + CUDA + numerical-validation all succeed, else None.

    Never trust an accelerated path without a working CPU fallback and a validation receipt
    (CLAUDE.md, numerical-computing skill). Imported lazily -- never a bare `import cupy` at
    module scope, since cupy is an optional extra and this script must still run CPU-only.
    """
    try:
        import cupy as cp
        if not cp.cuda.is_available():
            return None
    except Exception as e:
        print(f"[gpu] cupy unavailable ({e}); using CPU spectrogram path", flush=True)
        return None

    rng = np.random.default_rng(0)
    fs_test = 1000.0
    t = np.arange(int(fs_test * 2.0)) / fs_test
    test_sig = (np.sin(2 * np.pi * 8 * t) + 0.5 * np.sin(2 * np.pi * 40 * t)
               + 0.1 * rng.standard_normal(t.size))
    seg = np.stack([test_sig, test_sig], axis=1)  # 2 identical channels
    ref = spectrogram_trial_cpu(seg, fs_test)
    try:
        gpu = spectrogram_trial_gpu(seg, fs_test, cp)
    except Exception as e:
        print(f"[gpu] GPU spectrogram path raised ({e}); using CPU path", flush=True)
        return None
    denom = np.maximum(np.abs(ref), 1e-12)
    rel_err = float(np.max(np.abs(gpu - ref) / denom))
    if rel_err >= GPU_VALIDATION_TOL:
        print(f"[gpu] GPU spectrogram failed validation (max rel err {rel_err:.3e} >= "
              f"{GPU_VALIDATION_TOL:.1e}); using CPU path", flush=True)
        return None
    print(f"[gpu] GPU spectrogram validated against scipy (max rel err {rel_err:.3e}); using CUDA", flush=True)
    return cp


def spectrogram_trial_gpu(seg: np.ndarray, fs: float, cp) -> np.ndarray:
    """Batched Hann-window PSD spectrogram on GPU, matching scipy's scaling='spectrum',
    mode='psd' definition: PSD = |STFT|^2 / (fs * sum(window)^2 / fs) ... implemented by
    mirroring scipy's own normalization (win / win.sum(), then |X|^2), computed batched
    across all channels via one rfft call instead of a per-channel Python loop.
    """
    nperseg, noverlap = _spectrogram_params(fs)
    step = nperseg - noverlap
    n_samples, n_ch = seg.shape
    n_frames = 1 + (n_samples - nperseg) // step
    if n_frames < 1:
        raise ValueError("segment too short for one frame")

    win = cp.asarray(signal.get_window("hann", nperseg), dtype=cp.float64)
    win_sum = float(cp.asnumpy(win.sum()))
    seg_gpu = cp.asarray(seg, dtype=cp.float64)

    idx = cp.arange(nperseg)[None, :] + step * cp.arange(n_frames)[:, None]  # (n_frames, nperseg)
    frames = seg_gpu[idx, :]                                                 # (n_frames, nperseg, n_ch)
    frames = frames * win[None, :, None]
    spec = cp.fft.rfft(frames, axis=1)                                       # (n_frames, n_freq, n_ch)
    psd = (cp.abs(spec) ** 2) / (win_sum ** 2)
    psd[:, 1:-1, :] *= 2.0  # one-sided spectrum, scipy convention (Nyquist/DC not doubled)
    psd = cp.transpose(psd, (2, 1, 0))                                       # (n_ch, n_freq, n_frames)

    freqs_sg = cp.fft.rfftfreq(nperseg, d=1.0 / fs)
    t_sg = (cp.arange(n_frames) * step + nperseg / 2.0) / fs
    t_ms = cp.asnumpy(t_sg) * 1000.0 - PRE_MS
    out_t = -PRE_MS + np.arange(N_TIMES) * BIN_MS
    from_f = cp.asnumpy(freqs_sg)

    psd_np = cp.asnumpy(psd)  # (n_ch, n_freq_native, n_frames)
    out = np.zeros((n_ch, len(FREQS_HZ), N_TIMES), dtype=np.float32)
    for c in range(n_ch):
        S_f = np.vstack([np.interp(FREQS_HZ, from_f, psd_np[c, :, j]) for j in range(n_frames)]).T
        for fi in range(len(FREQS_HZ)):
            out[c, fi, :] = np.interp(out_t, t_ms, S_f[fi]).astype(np.float32)
    return out


def load_probe_areas(meta_root: Path, stem: str) -> Dict:
    path = meta_root / stem / "probe_areas.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing sidecar {path}; run build_session_sidecars.py")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    nwb = args.nwb
    if not nwb.is_file():
        raise FileNotFoundError(nwb)
    prefix = session_prefix_from_nwb(nwb)
    stem = nwb.stem
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    area_filter = {a.strip() for a in args.areas.split(",")} if args.areas else None

    probe_meta = load_probe_areas(args.meta_root, stem)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if not AREA_VEC_PATH.is_file():
        sys.exit(f"missing {AREA_VEC_PATH} -- run scripts/build_channel_area_vector.py first")
    av = pd.read_csv(AREA_VEC_PATH)
    av_session = av[av.session_prefix == prefix]

    gpu = None
    if args.gpu != "cpu":
        gpu = _gpu_backend()
        if args.gpu == "cuda" and gpu is None:
            sys.exit("--gpu cuda requested but the GPU path failed validation; see log above")

    with h5py.File(nwb, "r") as f:
        for probe_name, meta in probe_meta.items():
            lfp_key = meta["lfp_key"]
            areas = list(meta["areas"])
            if area_filter:
                areas = [a for a in areas if a in area_filter]
            if not areas:
                continue
            letter = PROBE_LETTER.get(lfp_key, "X")
            data, ts, fs = resolve_lfp_datasets(f, lfp_key)
            print(f"{lfp_key}: fs={fs:.3f} shape={data.shape} areas={areas}", flush=True)

            for area in areas:
                area_rows = av_session[(av_session.probe_letter == letter) & (av_session.area == area)]
                if area_rows.empty:
                    print(f"  skip {area}: no channel_area_vector rows for "
                          f"{prefix}/{letter}", flush=True)
                    continue
                candidates = area_rows["channel"].to_numpy()
                kept, exps, r2s = screen_channels(data, fs, candidates)
                if kept.size == 0:
                    print(f"  skip {area}: 0/{candidates.size} channels passed the 1/f "
                          f"quality screen", flush=True)
                    continue
                print(f"  {area}: {kept.size}/{candidates.size} channels passed 1/f screen "
                      f"(median exponent {np.median(exps):.2f}, median R^2 {np.median(r2s):.2f})",
                      flush=True)

                for cond in conditions:
                    onsets = p1_onsets_s(f, cond)
                    if args.max_trials is not None:
                        onsets = onsets[: args.max_trials]
                    if len(onsets) == 0:
                        print(f"    skip {cond}: 0 p1 onsets", flush=True)
                        continue
                    if args.dry_run:
                        print(f"    {cond}: n_trials={len(onsets)} (dry-run)", flush=True)
                        continue

                    trial_stack = []
                    need = int(round((PRE_MS + POST_MS) / 1000.0 * fs))
                    for onset in onsets:
                        t0 = onset - PRE_MS / 1000.0
                        t1 = onset + POST_MS / 1000.0
                        if ts is not None:
                            i0, i1 = int(np.searchsorted(ts, t0)), int(np.searchsorted(ts, t1))
                        else:
                            i0, i1 = int(round(t0 * fs)), int(round(t1 * fs))
                        i0, i1 = max(0, i0), min(data.shape[0], i1)
                        if i1 - i0 < need // 2:
                            continue
                        seg = np.asarray(data[i0:i1, :][:, kept], dtype=np.float64)
                        if seg.shape[0] < need:
                            seg = np.pad(seg, ((0, need - seg.shape[0]), (0, 0)), mode="edge")
                        elif seg.shape[0] > need:
                            seg = seg[:need]
                        if gpu is not None:
                            trial_stack.append(spectrogram_trial_gpu(seg, fs, gpu))
                        else:
                            trial_stack.append(spectrogram_trial_cpu(seg, fs))

                    if not trial_stack:
                        print(f"    skip {cond}: no valid segments", flush=True)
                        continue
                    power = np.stack(trial_stack, axis=0).astype(np.float32)
                    out_name = f"{prefix}-{letter}-{area}-{cond}.npz"
                    out_path = args.out_dir / out_name
                    np.savez_compressed(out_path, power=power, channels=kept,
                                        fit_exponent=exps, fit_r2=r2s)
                    print(f"    wrote {out_path.name} power={power.shape} "
                          f"({out_path.stat().st_size / 1e6:.1f} MB)", flush=True)


if __name__ == "__main__":
    main()
