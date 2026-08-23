r"""
Shared LFP data-access helpers for the L0-L12 spec scripts (context/figures/L*).

Factored out of L0_pooling_reconciliation.py once L1 needed the same probe/area/channel
resolution and trial-window extraction it already built -- avoids re-deriving the
V182o-vs-C31o/V198o layout differences and the position-aware area resolution a second time.
Not a general-purpose jnwb module: this is spec-script-specific plumbing (h5py direct access,
same as extract_lfp_coupling_matrices.py and precompute_tfr_arrays.py use, for the documented
reason that a full PyNWB build blocks on some sessions).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]

PROBE_LETTER_TO_KEY = {"A": "probe_0_lfp", "B": "probe_1_lfp", "C": "probe_2_lfp", "D": "probe_3_lfp"}


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    except Exception:
        return "unknown"


def _dec(a) -> np.ndarray:
    return np.array([x.decode() if isinstance(x, bytes) else x for x in a[:]])


def _probe_column(et) -> np.ndarray:
    """Electrode-table probe-group labels. C31o/V198o use a 'group_name' string column;
    V182o has no 'group_name' at all (uses 'group', HDF5 object references, plus a plain
    bytes 'probe' column that carries the same 'probeA'/'probeB'/... labels) -- confirmed by
    direct read 2026-08-17. Prefer 'group_name' when present, fall back to 'probe'."""
    if "group_name" in et:
        return _dec(et["group_name"])
    return _dec(et["probe"])


def probe_channel_areas(f: h5py.File, group_name: str) -> np.ndarray:
    """Area label per LOCAL channel index (0-based within this probe), depth order = index
    order, resolved via jnwb.addressing.map_peak_channel_to_area (position-aware for
    multi-area probes -- NOT a naive location.split(',')[0], which mislabeled 1,965/6,655 rows
    once, see omission-data skill)."""
    from jnwb.addressing import map_peak_channel_to_area

    et = f["general/extracellular_ephys/electrodes"]
    loc, grp = _dec(et["location"]), _probe_column(et)
    edf = pd.DataFrame({"location": loc, "group_name": grp})
    probe_rows = np.sort(edf.index[edf["group_name"] == group_name].to_numpy())
    return np.array([map_peak_channel_to_area(float(idx), edf) for idx in probe_rows])


def resolve_area_channel_block(f: h5py.File, probe_letter: str, area: str, n_ch: int | None = None):
    """Contiguous local-index channel block for `area` on this probe. If n_ch is given, returns
    a block of exactly that width centered in the area's contiguous run (tractability cap for
    CSD/per-channel work); if n_ch is None, returns the area's FULL contiguous channel range.
    Returns (lfp_key, lo, hi)."""
    key = PROBE_LETTER_TO_KEY[probe_letter]
    et = f["general/extracellular_ephys/electrodes"]
    grp = _probe_column(et)
    group_name = f"probe{probe_letter}"
    if group_name not in grp:
        raise ValueError(f"No electrode group {group_name!r} in this session")
    areas = probe_channel_areas(f, group_name)
    idx = np.where(areas == area)[0]
    if len(idx) == 0:
        raise ValueError(f"Area {area!r} not found on probe {probe_letter}; areas present: "
                          f"{sorted(set(areas))}")
    lo_area, hi_area = int(idx.min()), int(idx.max()) + 1
    if n_ch is None:
        return key, lo_area, hi_area
    if len(idx) < n_ch:
        raise ValueError(f"Area {area!r} only has {len(idx)} channels on probe {probe_letter}, "
                          f"need {n_ch}")
    mid = (lo_area + hi_area) // 2
    lo = max(lo_area, mid - n_ch // 2)
    hi = min(hi_area, lo + n_ch)
    lo = hi - n_ch
    return key, lo, hi


def extract_epoch_trials(f: h5py.File, lfp_key: str, ch_lo: int, ch_hi: int, condition: str,
                          window_s, max_trials: int, repair: bool = True):
    """Pull ONE window per trial for `condition`, all channels in [ch_lo, ch_hi).
    Returns (trials, fs, n_trials, frac_repaired). trials: (n_trials, n_channels, n_samples)."""
    from precompute_tfr_arrays import p1_onsets_s
    from jnwb.artifact_repair import repair_lfp_trials  # promoted 2026-08-23 from omission.jnwb_ext.artifact_repair

    data, ts, fs = resolve_lfp_datasets(f, lfp_key)
    onsets = p1_onsets_s(f, condition)[:max_trials]
    if len(onsets) == 0:
        raise ValueError(f"No {condition} trials found")

    need = int(round((window_s[1] - window_s[0]) * fs))
    out = []
    for onset in onsets:
        t0, t1 = onset + window_s[0], onset + window_s[1]
        if ts is not None:
            i0, i1 = int(np.searchsorted(ts, t0)), int(np.searchsorted(ts, t1))
        else:
            i0, i1 = int(round(t0 * fs)), int(round(t1 * fs))
        i0, i1 = max(0, i0), min(data.shape[0], i1)
        if i1 - i0 < need // 2:
            continue
        raw = np.asarray(data[i0:i1, ch_lo:ch_hi], dtype=np.float64)
        if raw.shape[0] < need:
            raw = np.pad(raw, ((0, need - raw.shape[0]), (0, 0)), mode="edge")
        elif raw.shape[0] > need:
            raw = raw[:need]
        out.append(raw.T)  # (n_channels, n_samples)
    if not out:
        raise ValueError("No usable trials after window extraction")
    trials = np.stack(out)
    n = trials.shape[0]
    frac_repaired = 0.0
    if repair:
        trials, frac_repaired, _ = repair_lfp_trials(trials, times_ms=None, reward_window_ms=None)
    return trials, fs, n, float(frac_repaired)


def resolve_lfp_datasets(f: h5py.File, lfp_key: str):
    """Re-exported from precompute_tfr_arrays for callers that only need this one function."""
    from precompute_tfr_arrays import resolve_lfp_datasets as _r
    return _r(f, lfp_key)


def csd_reference_trials(x_trials: np.ndarray) -> np.ndarray:
    """omission.jnwb_ext.spectral.laplacian_reference per trial (CSD estimator for a depth-ordered probe)."""
    from omission.jnwb_ext.spectral import laplacian_reference
    return np.stack([laplacian_reference(x_trials[t]) for t in range(x_trials.shape[0])])


def batched_spectrogram(x: np.ndarray, fs: float, nperseg_ms: float = 200.0, hop_ms: float = 10.0):
    """x: (n_trials, n_channels, n_samples) -> (freqs, times, power) where power has shape
    (n_trials, n_channels, n_freqs, n_times). Vectorized: scipy.signal.spectrogram batches over
    every leading axis when given axis=-1, so this is one FFT batch call, not a Python loop over
    trials*channels (that does not scale -- confirmed elsewhere in the repo, see omission-signal
    skill S10 on the analogous per-shuffle-Welch failure mode)."""
    from scipy import signal
    n_trials, n_channels, n_samples = x.shape
    nperseg = max(32, int(round(fs * nperseg_ms / 1000.0)))
    hop = max(1, int(round(fs * hop_ms / 1000.0)))
    noverlap = max(0, min(nperseg - hop, nperseg - 1))
    freqs, times, Sxx = signal.spectrogram(
        x, fs=fs, window="hann", nperseg=nperseg, noverlap=noverlap,
        detrend=False, scaling="spectrum", mode="psd", axis=-1)
    return freqs, times, Sxx


def find_probe_for_area(f: h5py.File, area: str) -> str | None:
    """Which probe letter (A/B/C/D) on THIS session carries `area`, resolved fresh per session
    -- probe -> area assignment is NOT fixed across sessions on this corpus (confirmed 2026-08-17:
    V182o alone puts FEF on probe A in one session and probe B in the next), so this must never
    be hardcoded or cached across sessions."""
    et = f["general/extracellular_ephys/electrodes"]
    loc, grp = _dec(et["location"]), _probe_column(et)
    for letter in "ABCD":
        group_name = f"probe{letter}"
        if group_name not in grp:
            continue
        mask = grp == group_name
        if np.any(np.char.find(loc[mask].astype(str), area) >= 0):
            return letter
    return None
