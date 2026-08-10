r"""
Corpus-scale spike-LFP phase coupling extraction for figure 7.

For each SUA unit (quality==1 in omission_grand_units.csv) with enough spikes in a context
window, computes PPC (pairwise phase consistency, Vinck et al. 2010 -- bias-free across
different spike counts, unlike raw vector strength/Rayleigh z) between the unit's spike times
and the LFP phase of its OWN area's representative channel (band-pass + Hilbert), per band,
per context (same stimulus/omission windows as figure 6), with a trial-shuffle null.

SAME-ELECTRODE CONTROL: a unit's own spike waveform can leak into a nearby LFP channel and
inflate phase locking spuriously. Units whose `peak_channel_id` sits within +/-2 channels of
the area/layer cell's representative LFP channel are excluded from that cell's coupling
estimate rather than silently included -- see EXCLUDE_RADIUS below.

DATA ACCESS: reuses resolve_lfp_datasets/p1_onsets_and_conditions_s from
extract_lfp_coupling_matrices.py (fig06) and this session's cell/layer assignment logic, so
area/layer/representative-channel selection is identical across figures 6 and 7. Spike times
are read directly from the NWB units table's ragged VectorIndex arrays via h5py, not through
jnwb.session (avoids a full pynwb load per session across ~20 sessions x many units).

OUTPUT: outputs/spike_lfp_coupling/coupling.npz, keyed
  "{session_prefix}|{context}|{band}|{area}|{layer}|{unit_row}"
  -> array([ppc_observed, ppc_null_mean, ppc_null_std, n_shuffle, n_spikes])
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt, hilbert

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "archive_oneoff"))
sys.path.insert(0, str(REPO / "scripts"))

from precompute_tfr_arrays import load_probe_areas, resolve_lfp_datasets  # noqa: E402
from extract_lfp_coupling_matrices import (  # noqa: E402
    BANDS, CONTEXTS, load_layer_masks, cells_for_probe, p1_onsets_and_conditions_s,
)
from jnwb import paths as _P

READINESS = REPO / "artifacts/data/session_readiness.csv"
GRAND_UNITS = REPO / "outputs/classification/omission_grand_units.csv"
OUT_DIR = REPO / "outputs/spike_lfp_coupling"
META_ROOT = Path(os.environ.get("OMISSION_META_DIR", _P.meta_dir()))

N_SHUFFLE = 500
MAX_TRIALS_PER_CONDITION = 60
EXCLUDE_RADIUS = 2      # channels; same-electrode contamination control
MIN_SPIKES = 30         # PPC needs a reasonable spike count to be interpretable


def read_spike_times(f, unit_row):
    idx = f["units/spike_times_index"]
    start = 0 if unit_row == 0 else int(idx[unit_row - 1])
    stop = int(idx[unit_row])
    return np.asarray(f["units/spike_times"][start:stop], dtype=float)


def read_peak_channel(f, unit_row):
    return int(f["units/peak_channel_id"][unit_row])


def ppc(phases):
    """Pairwise phase consistency (Vinck et al. 2010): bias-free alternative to vector
    strength / Rayleigh z, does not grow spuriously with spike count."""
    n = len(phases)
    if n < 2:
        return np.nan
    z = np.exp(1j * phases)
    # PPC = (|sum z|^2 - n) / (n * (n - 1)), algebraically equivalent to averaging cos(phase_i - phase_j)
    # over all i != j pairs but O(n) instead of O(n^2).
    s = np.sum(z)
    return float((np.abs(s) ** 2 - n) / (n * (n - 1)))


def ppc_batch(phases_2d):
    """Same formula as ppc(), applied to every row of a (n_shuffle, n_spikes) array at once --
    the earlier per-shuffle python-loop design (500 calls to ppc() per unit-band-context) did
    not finish a single pilot session in over 5 minutes; this is the same fix fig06 needed
    (vectorize across shuffles, don't call the estimator fresh per shuffle)."""
    n = phases_2d.shape[1]
    if n < 2:
        return np.full(phases_2d.shape[0], np.nan)
    z = np.exp(1j * phases_2d)
    s = np.sum(z, axis=1)
    return (np.abs(s) ** 2 - n) / (n * (n - 1))


def band_phase(trace, fs, band):
    lo, hi = band
    b, a = butter(4, [lo / (fs / 2), hi / (fs / 2)], btype="band")
    filtered = filtfilt(b, a, trace)
    return np.angle(hilbert(filtered))


PAD_S = 0.15  # edge padding on each side of a trial window so filtfilt's transient decays
             # before/after the window of interest rather than corrupting it


def trial_windowed_phase(data, ts, fs, onsets_s, window_s, channel_idx, band, max_trials):
    """Band-phase, computed PER TRIAL WINDOW (with edge padding), not on one huge
    session-spanning slice. The first version of this script pulled one contiguous slice from
    the earliest to the latest onset and ran filtfilt/hilbert on it -- for trials spread across
    a session that slice can be most of the recording (confirmed: >1GB RAM, >3 min with no
    trial actually processed yet on a single session). Real spike-field coupling only needs
    the ~0.5-0.8 s around each trial, not everything between the first and last one.

    Returns: dict[trial_index] -> (window_times_abs, phase_array_for_window)."""
    need = int(round((window_s[1] - window_s[0]) * fs))
    pad = int(round(PAD_S * fs))
    out = {}
    for ti, onset in enumerate(onsets_s[:max_trials]):
        t0, t1 = onset + window_s[0] - PAD_S, onset + window_s[1] + PAD_S
        if ts is not None:
            i0, i1 = int(np.searchsorted(ts, t0)), int(np.searchsorted(ts, t1))
        else:
            i0, i1 = int(round(t0 * fs)), int(round(t1 * fs))
        i0, i1 = max(0, i0), min(data.shape[0], i1)
        if i1 - i0 < need:
            continue
        raw = np.asarray(data[i0:i1, channel_idx], dtype=np.float64)
        phase = band_phase(raw, fs, band)
        core = phase[pad: pad + need] if len(phase) >= pad + need else phase[-need:]
        t_start = (ts[i0] if ts is not None else i0 / fs) + PAD_S
        out[ti] = (t_start, core, fs)
    return out


def main(limit_sessions=None, sessions_filter=None):
    t_start = time.time()
    readiness = pd.read_csv(READINESS)
    ready = readiness[readiness.nwb_ok & readiness.sidecar_ok]
    if sessions_filter:
        ready = ready[ready.session_prefix.isin(sessions_filter)]
    if limit_sessions:
        ready = ready.head(limit_sessions)

    grand = pd.read_csv(GRAND_UNITS)
    grand = grand[grand.quality == 1]  # SUA only

    layer_masks = load_layer_masks()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    rng = np.random.default_rng(0)
    n_excluded_same_electrode = 0

    for _, row in ready.iterrows():
        session_prefix = row.session_prefix
        nwb_path = row.nwb_path
        stem = Path(nwb_path).stem
        try:
            probe_meta = load_probe_areas(META_ROOT, stem)
        except FileNotFoundError as e:
            print(f"  skip {session_prefix}: {e}")
            continue

        # peak_channel_id in omission_grand_units.csv is a GLOBAL index across all 4 probes
        # (probe_0_lfp=0-127, probe_1_lfp=128-255, ...) -- confirmed by range (0-511) far
        # exceeding one probe's 128 channels; `local_channel` is entirely NaN in this table
        # and unusable. Derive the probe-local index from the lfp_key's probe number instead.
        cells = []
        for probe_name, meta in probe_meta.items():
            probe_num = int(meta["lfp_key"].split("_")[1])
            for area, layer, rep in cells_for_probe(session_prefix, probe_name, meta, layer_masks):
                cells.append((area, layer, meta["lfp_key"], rep, probe_num))
        if not cells:
            continue

        session_units = grand[grand.session == session_prefix]
        if session_units.empty:
            continue

        try:
            with h5py.File(nwb_path, "r") as f:
                all_conds = sorted({c for ctx in CONTEXTS.values() for c in ctx["conditions"]})
                onsets_all = p1_onsets_and_conditions_s(f, all_conds)
                lfp_cache = {}
                for area, layer, lfp_key, rep, probe_num in cells:
                    if lfp_key not in lfp_cache:
                        lfp_cache[lfp_key] = resolve_lfp_datasets(f, lfp_key)
                    data, ts, fs = lfp_cache[lfp_key]
                    units_here = session_units[session_units.area10 == area]
                    if units_here.empty:
                        continue
                    for ctx_name, ctx in CONTEXTS.items():
                        conds = [c for c in ctx["conditions"] if len(onsets_all.get(c, [])) > 0]
                        if not conds:
                            continue
                        onsets = np.concatenate([onsets_all[c][:MAX_TRIALS_PER_CONDITION]
                                                 for c in conds])
                        for band_name, band in BANDS.items():
                            # Per-trial phase, padded to let filtfilt's edge transient decay
                            # outside the window of interest -- not one session-spanning slice
                            # (see trial_windowed_phase docstring for why that was 3+ min/session).
                            trial_phase = trial_windowed_phase(
                                data, ts, fs, onsets, ctx["window_s"], rep, band, len(onsets))
                            if not trial_phase:
                                continue
                            for _, urow in units_here.iterrows():
                                unit_probe_num = int(urow.peak_channel_id) // 128
                                unit_local_ch = int(urow.peak_channel_id) % 128
                                if unit_probe_num == probe_num and abs(unit_local_ch - rep) <= EXCLUDE_RADIUS:
                                    n_excluded_same_electrode += 1
                                    continue
                                spike_times = read_spike_times(f, int(urow.unit_row))
                                # Per trial: real spike phases, and how many spikes fell in
                                # that trial (needed to draw a matching-size null sample).
                                phases_per_trial = []   # list of (phase_win, real_phase_array)
                                for ti, (trial_t0, phase_win, fs_w) in trial_phase.items():
                                    t0 = onsets[ti] + ctx["window_s"][0]
                                    t1 = onsets[ti] + ctx["window_s"][1]
                                    sp = spike_times[(spike_times >= t0) & (spike_times < t1)]
                                    if len(sp) == 0:
                                        continue
                                    idx = np.clip(np.round((sp - trial_t0) * fs_w).astype(int),
                                                 0, len(phase_win) - 1)
                                    phases_per_trial.append((phase_win, phase_win[idx]))
                                if not phases_per_trial:
                                    continue
                                phases = np.concatenate([p for _, p in phases_per_trial])
                                if len(phases) < MIN_SPIKES:
                                    continue
                                obs = ppc(phases)
                                # Null: for each of N_SHUFFLE draws, resample each trial's
                                # spike-count-many phases at UNIFORMLY RANDOM times within that
                                # trial's own window instead of true spike times -- breaks
                                # spike-to-phase locking while preserving each trial's own phase
                                # content and the per-trial spike count. Fully vectorized: one
                                # (N_SHUFFLE, n_spikes_trial) index draw per trial, concatenated
                                # across trials, PPC computed on all N_SHUFFLE rows at once via
                                # ppc_batch -- no python-level loop over shuffles at all (the
                                # earlier per-shuffle-python-loop design did not finish one pilot
                                # session in 5+ minutes).
                                per_trial_draws = [
                                    pw[rng.integers(0, len(pw), size=(N_SHUFFLE, len(rp)))]
                                    for pw, rp in phases_per_trial
                                ]
                                null_phases_2d = np.concatenate(per_trial_draws, axis=1)
                                null_vals = ppc_batch(null_phases_2d)
                                key = (f"{session_prefix}|{ctx_name}|{band_name}|{area}|{layer}|"
                                      f"{int(urow.unit_row)}")
                                results[key] = np.array([obs, float(np.nanmean(null_vals)),
                                                        float(np.nanstd(null_vals)),
                                                        N_SHUFFLE, len(phases)], dtype=np.float64)
        except Exception as e:
            print(f"  ERROR {session_prefix}: {e}")
            continue
        print(f"{session_prefix}: {len(results)} cumulative results, "
              f"{time.time() - t_start:.0f}s elapsed")

    np.savez(OUT_DIR / "coupling.npz",
            keys=np.array(list(results.keys())),
            values=np.array(list(results.values())))
    with open(OUT_DIR / "receipt.json", "w", encoding="utf-8") as fh:
        json.dump({
            "n_sessions_attempted": int(len(ready)), "n_results": len(results),
            "n_excluded_same_electrode": n_excluded_same_electrode,
            "exclude_radius_channels": EXCLUDE_RADIUS, "min_spikes": MIN_SPIKES,
            "bands_hz": {k: list(v) for k, v in BANDS.items()},
            "contexts": {k: {"window_s": v["window_s"], "conditions": v["conditions"]}
                        for k, v in CONTEXTS.items()},
            "n_shuffle": N_SHUFFLE, "elapsed_s": time.time() - t_start,
        }, fh, indent=2)
    print(f"WROTE {OUT_DIR / 'coupling.npz'} ({len(results)} results, "
          f"{n_excluded_same_electrode} same-electrode exclusions, "
          f"{time.time() - t_start:.0f}s)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-sessions", type=int, default=None)
    ap.add_argument("--sessions", default=None)
    args = ap.parse_args()
    sf = args.sessions.split(",") if args.sessions else None
    main(limit_sessions=args.limit_sessions, sessions_filter=sf)
