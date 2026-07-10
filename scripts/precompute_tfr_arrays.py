#!/usr/bin/env python3
"""
Precompute trial-aligned TFR .npy arrays from NWB LFP via h5py.

Output contract (matches existing tfr_arrays):
  {session_prefix}-{A|B|C|D}-{area}-{CONDITION}.npy
  shape (n_trials, 128, 99, 500) float32
  freqs = arange(3, 201, 2); times = -1000 + arange(500)*10 ms (p1-aligned)

Uses scipy.signal.spectrogram (Hann). Dual-area probes write one file per area
token with the full 128-ch probe array (suite half-slices via sequence_layout).

V182o LFP nesting: acquisition/{key}/{key}_data/data
C31o/V198o nesting: acquisition/{key}/data
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import h5py
import numpy as np
from scipy import signal

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

FREQS_HZ = np.arange(3, 201, 2)  # 99
N_TIMES = 500
PRE_MS = 1000.0
POST_MS = 4000.0  # total window 5000 ms → 500 bins @ 10 ms
BIN_MS = 10.0

# Canonical condition → task_condition_number sets (from jnwb-core / legacy CLAUDE)
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

PROBE_LETTER = {"probe_0_lfp": "A", "probe_1_lfp": "B", "probe_2_lfp": "C", "probe_3_lfp": "D"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--nwb", type=Path, required=True, help="Path to .nwb")
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path(os.environ.get("OMISSION_TFR_DIR", "D:/workspace/data/tfr_arrays")),
    )
    p.add_argument(
        "--meta-root",
        type=Path,
        default=Path(os.environ.get("OMISSION_META_DIR", "D:/workspace/data/metadata")),
    )
    p.add_argument(
        "--conditions",
        default="RRRR,RXRR,RRXR,RRRX",
        help="Comma-separated condition codes",
    )
    p.add_argument("--areas", default=None, help="Optional comma-separated area filter")
    p.add_argument("--max-trials", type=int, default=None, help="Cap trials (smoke)")
    p.add_argument("--max-channels", type=int, default=None, help="Cap channels (smoke)")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def session_prefix_from_nwb(nwb: Path) -> str:
    stem = nwb.stem
    if stem.endswith("_rec"):
        return stem[: -len("_rec")]
    return stem


def resolve_lfp_datasets(f: h5py.File, lfp_key: str):
    """Return (data_dset, timestamps_array_or_None, fs)."""
    root = f[f"acquisition/{lfp_key}"]
    if "data" in root:
        data = root["data"]
        ts = root["timestamps"][:] if "timestamps" in root else None
    else:
        # V182o-style nested ElectricalSeries
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


def p1_onsets_s(
    f: h5py.File,
    condition: str,
) -> np.ndarray:
    g = f["intervals/omission_glo_passive"]
    sn = g["stimulus_number"][:]
    corr = g["correct"][:]
    tc = g["task_condition_number"][:]
    st = g["start_time"][:]
    nums = CONDITION_NUMBERS[condition]
    mask = (sn == 2) & (corr == 1) & np.isin(tc, nums)
    # drop nan stimulus_number rows
    mask = mask & np.isfinite(sn) & np.isfinite(st)
    return np.asarray(st[mask], dtype=float)


def spectrogram_trial(
    seg: np.ndarray,
    fs: float,
) -> np.ndarray:
    """
    seg: (n_samples, n_channels) → (n_channels, n_freqs, n_times=500) power
    """
    # Target 10 ms hop, ~window covering low freqs
    nperseg = max(64, int(round(fs * 0.2)))  # 200 ms
    noverlap = nperseg - int(round(fs * BIN_MS / 1000.0))
    noverlap = max(0, min(noverlap, nperseg - 1))

    # Compute on channel 0 to get time/freq grids, then loop channels
    f_sg, t_sg, _ = signal.spectrogram(
        seg[:, 0],
        fs=fs,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
        detrend=False,
        scaling="spectrum",
        mode="psd",
    )
    # Map to canonical freq/time grids via interpolation
    t_ms = t_sg * 1000.0 - PRE_MS
    out_t = -PRE_MS + np.arange(N_TIMES) * BIN_MS
    n_ch = seg.shape[1]
    out = np.zeros((n_ch, len(FREQS_HZ), N_TIMES), dtype=np.float32)
    for c in range(n_ch):
        _, _, Sxx = signal.spectrogram(
            seg[:, c],
            fs=fs,
            window="hann",
            nperseg=nperseg,
            noverlap=noverlap,
            detrend=False,
            scaling="spectrum",
            mode="psd",
        )
        # interp freqs then times
        # Sxx: (n_f_sg, n_t_sg)
        from_f = np.asarray(f_sg, dtype=float)
        # for each canonical freq, nearest or linear along freq
        S_f = np.vstack(
            [np.interp(FREQS_HZ, from_f, Sxx[:, j]) for j in range(Sxx.shape[1])]
        ).T  # (99, n_t_sg)
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
    area_filter = (
        {a.strip() for a in args.areas.split(",")} if args.areas else None
    )

    probe_meta = load_probe_areas(args.meta_root, stem)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    with h5py.File(nwb, "r") as f:
        for probe_name, meta in probe_meta.items():
            lfp_key = meta["lfp_key"]
            areas = list(meta["areas"])
            if area_filter:
                areas = [a for a in areas if a in area_filter]
            if not areas:
                continue
            data, ts, fs = resolve_lfp_datasets(f, lfp_key)
            n_ch_full = data.shape[1]
            n_ch = n_ch_full if args.max_channels is None else min(args.max_channels, n_ch_full)
            print(f"{lfp_key}: fs={fs:.3f} shape={data.shape} areas={areas}")

            for cond in conditions:
                onsets = p1_onsets_s(f, cond)
                if args.max_trials is not None:
                    onsets = onsets[: args.max_trials]
                if len(onsets) == 0:
                    print(f"  skip {cond}: 0 p1 onsets")
                    continue
                print(f"  {cond}: n_trials={len(onsets)}")
                if args.dry_run:
                    continue

                # Build full-probe TFR once per condition, then save per area label
                # (same array; naming uses each area token — matches historical V3 dual files)
                trial_stack = []
                for onset in onsets:
                    t0 = onset - PRE_MS / 1000.0
                    t1 = onset + POST_MS / 1000.0
                    if ts is not None:
                        i0 = int(np.searchsorted(ts, t0))
                        i1 = int(np.searchsorted(ts, t1))
                    else:
                        i0 = int(round(t0 * fs))
                        i1 = int(round(t1 * fs))
                    i0 = max(0, i0)
                    i1 = min(data.shape[0], i1)
                    need = int(round((PRE_MS + POST_MS) / 1000.0 * fs))
                    if i1 - i0 < need // 2:
                        continue
                    seg = np.asarray(data[i0:i1, :n_ch], dtype=np.float64)
                    if seg.shape[0] < need:
                        pad = need - seg.shape[0]
                        seg = np.pad(seg, ((0, pad), (0, 0)), mode="edge")
                    elif seg.shape[0] > need:
                        seg = seg[:need]
                    # pad channels to 128 for contract
                    if seg.shape[1] < 128:
                        seg = np.pad(
                            seg, ((0, 0), (0, 128 - seg.shape[1])), mode="constant"
                        )
                    elif seg.shape[1] > 128:
                        seg = seg[:, :128]
                    trial_stack.append(spectrogram_trial(seg, fs))

                if not trial_stack:
                    print(f"  skip {cond}: no valid segments")
                    continue
                arr = np.stack(trial_stack, axis=0).astype(np.float32)
                letter = PROBE_LETTER.get(lfp_key, "X")
                for area in areas:
                    out_name = f"{prefix}-{letter}-{area}-{cond}.npy"
                    out_path = args.out_dir / out_name
                    np.save(out_path, arr)
                    print(f"  wrote {out_path.name} {arr.shape}")


if __name__ == "__main__":
    main()
