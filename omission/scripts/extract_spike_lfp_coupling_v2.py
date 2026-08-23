r"""
Corpus-scale spike-LFP phase coupling extraction for figure 7 -- v2, 2026-08-15.

WHY A NEW FILE, NOT AN EDIT TO extract_spike_lfp_coupling.py
    That script's probe/area resolution calls `load_probe_areas(META_ROOT, stem)`, which reads
    D:/analysis/metadata/{stem}/probe_areas.json -- a metadata sidecar directory that does not
    exist on this machine (context/PROJECT_STATE.md, "Still open -- sidecar_ok /
    suite_tfr_ready", 2026-08-14: "no metadata sidecar directory was found anywhere on disk in
    a shallow search"). This blocks the script outright, not just its trustworthiness -- it was
    only ever able to run because its one existing output (outputs/spike_lfp_coupling/
    coupling.npz) predates this gap (dated 2026-07-30, before the sidecars went missing).
    scripts/precompute_tfr_arrays.py (renamed 2026-08-22 from precompute_tfr_arrays_v2.py) -- the script behind fig04's now-accepted v3 corpus --
    already solved exactly this problem for its own area/channel resolution by reading
    outputs/channel_area_vector/channel_area_vector.csv instead of the sidecar (22/22 sessions
    covered, confirmed). This file reuses that same sidecar-free source; every other piece of
    extract_spike_lfp_coupling.py (PPC formula, per-trial phase extraction, vectorized
    shuffle null, same-electrode exclusion) is copied unchanged.

ONLY CHANGE: `cells_for_session()` replaces the original's
    `load_probe_areas(META_ROOT, stem)` + `cells_for_probe(...)` (extract_lfp_coupling_matrices)
    pipeline. channel_area_vector.csv's `seg_start`/`seg_stop` per (session_prefix,
    probe_letter, area) is exactly probe_areas.json's `channel_slices[area] = {start, stop}` --
    confirmed by inspecting scripts/precompute_tfr_arrays.py (renamed 2026-08-22 from precompute_tfr_arrays_v2.py)'s own AREA_VEC_PATH usage.
    Layer masks still come from outputs/layers/channel_layers_all.csv via
    extract_lfp_coupling_matrices.load_layer_masks (unaffected by the sidecar gap; reused as-is).

OUTPUT: outputs/spike_lfp_coupling/coupling_v2.npz (kept separate from the stale v1 output
   rather than overwriting it -- "preserve originals"), same key/value schema as v1:
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

from precompute_tfr_arrays import resolve_lfp_datasets, PROBE_LETTER  # noqa: E402  (renamed 2026-08-22 from precompute_tfr_arrays_v2)
from extract_lfp_coupling_matrices import (  # noqa: E402
    BANDS, CONTEXTS, load_layer_masks, LAYERS, p1_onsets_and_conditions_s,
)
from jnwb import paths as _P

READINESS = REPO / "artifacts/data/session_readiness.csv"
GRAND_UNITS = REPO / "outputs/classification/omission_grand_units.csv"
AREA_VEC_PATH = REPO / "outputs/channel_area_vector/channel_area_vector.csv"
OUT_DIR = REPO / "outputs/spike_lfp_coupling"

N_SHUFFLE = 500
MAX_TRIALS_PER_CONDITION = 60
EXCLUDE_RADIUS = 2      # channels; same-electrode contamination control
MIN_SPIKES = 30         # PPC needs a reasonable spike count to be interpretable

LETTER_TO_PROBE_NUM = {"A": 0, "B": 1, "C": 2, "D": 3}


def read_spike_times(f, unit_row):
    idx = f["units/spike_times_index"]
    start = 0 if unit_row == 0 else int(idx[unit_row - 1])
    stop = int(idx[unit_row])
    return np.asarray(f["units/spike_times"][start:stop], dtype=float)


def ppc(phases):
    """Pairwise phase consistency (Vinck et al. 2010): bias-free alternative to vector
    strength / Rayleigh z, does not grow spuriously with spike count."""
    n = len(phases)
    if n < 2:
        return np.nan
    z = np.exp(1j * phases)
    s = np.sum(z)
    return float((np.abs(s) ** 2 - n) / (n * (n - 1)))


def ppc_batch(phases_2d):
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


def cells_for_session(av_session, session_prefix, layer_masks):
    """Sidecar-free replacement for load_probe_areas + cells_for_probe: builds
    (area, layer, lfp_key, representative_channel, probe_num) tuples directly from
    channel_area_vector.csv's per-(probe_letter, area) seg_start/seg_stop (channel_slices'
    exact equivalent) and channel_layers_all.csv's per-channel layer call."""
    out = []
    for probe_letter, g in av_session.groupby("probe_letter"):
        probe_num = LETTER_TO_PROBE_NUM.get(probe_letter)
        if probe_num is None:
            continue
        lfp_key = f"probe_{probe_num}_lfp"
        ch_layer = layer_masks.get((session_prefix, lfp_key))
        if not ch_layer:
            continue
        for area, gg in g.groupby("area"):
            lo, hi = int(gg.seg_start.iloc[0]), int(gg.seg_stop.iloc[0])
            for layer in LAYERS:
                idx = sorted(ch for ch, lyr in ch_layer.items()
                            if lyr == layer and lo <= ch < hi)
                if not idx:
                    continue
                rep = int(idx[len(idx) // 2])
                out.append((area, layer, lfp_key, rep, probe_num))
    return out


def main(limit_sessions=None, sessions_filter=None):
    t_start = time.time()
    readiness = pd.read_csv(READINESS)
    ready = readiness[readiness.nwb_ok]
    if sessions_filter:
        ready = ready[ready.session_prefix.isin(sessions_filter)]
    if limit_sessions:
        ready = ready.head(limit_sessions)

    grand = pd.read_csv(GRAND_UNITS)
    grand = grand[grand.quality == 1]  # SUA only

    av = pd.read_csv(AREA_VEC_PATH)
    layer_masks = load_layer_masks()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    rng = np.random.default_rng(0)
    n_excluded_same_electrode = 0

    for _, row in ready.iterrows():
        session_prefix = row.session_prefix
        nwb_path = row.nwb_path
        av_session = av[av.session_prefix == session_prefix]
        if av_session.empty:
            print(f"  skip {session_prefix}: no channel_area_vector rows")
            continue

        cells = cells_for_session(av_session, session_prefix, layer_masks)
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
                                phases_per_trial = []
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
              f"{time.time() - t_start:.0f}s elapsed", flush=True)

    np.savez(OUT_DIR / "coupling_v2.npz",
            keys=np.array(list(results.keys())),
            values=np.array(list(results.values())))
    with open(OUT_DIR / "receipt_v2.json", "w", encoding="utf-8") as fh:
        json.dump({
            "n_sessions_attempted": int(len(ready)), "n_results": len(results),
            "n_excluded_same_electrode": n_excluded_same_electrode,
            "exclude_radius_channels": EXCLUDE_RADIUS, "min_spikes": MIN_SPIKES,
            "bands_hz": {k: list(v) for k, v in BANDS.items()},
            "contexts": {k: {"window_s": v["window_s"], "conditions": v["conditions"]}
                        for k, v in CONTEXTS.items()},
            "n_shuffle": N_SHUFFLE, "elapsed_s": time.time() - t_start,
            "area_source": "outputs/channel_area_vector/channel_area_vector.csv (sidecar-free)",
        }, fh, indent=2)
    print(f"WROTE {OUT_DIR / 'coupling_v2.npz'} ({len(results)} results, "
          f"{n_excluded_same_electrode} same-electrode exclusions, "
          f"{time.time() - t_start:.0f}s)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-sessions", type=int, default=None)
    ap.add_argument("--sessions", default=None)
    args = ap.parse_args()
    sf = args.sessions.split(",") if args.sessions else None
    main(limit_sessions=args.limit_sessions, sessions_filter=sf)
