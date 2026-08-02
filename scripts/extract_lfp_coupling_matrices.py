r"""
Corpus-scale LFP band-power coupling extraction for figure 6.

Builds area x area imaginary-coherency matrices, per band, per context (stimulus window
present in every condition; omission window present only in RXRR), per session, with a
trial-shuffled null. See context/figures/fig06_band_power_coupling/README.md for the full
plan this implements and the open decisions it resolves.

DATA ACCESS: reuses the h5py trial-window pattern from
scripts/archive_oneoff/precompute_tfr_arrays.py (resolve_lfp_datasets, p1_onsets_s,
CONDITION_NUMBERS, load_probe_areas) rather than re-deriving it -- that script already solved
the V182o-vs-C31o/V198o LFP nesting difference and the bytes-encoded trial-column footgun.

TRACTABILITY DECISIONS (stated, not hidden -- see fig06 README's "open decisions"):
  - Representative channel per (area, layer) cell, not all-channel-pairs-averaged: an
    all-pairs construction is 30-100x more coupling computations per session for a benefit
    (better SNR) that a representative-channel choice already gets most of, since neighboring
    channels within one area x layer cell are highly correlated. The representative channel is
    the middle index of the (area slice) x (layer mask) intersection.
  - Trial-window concatenation, not per-trial CSD averaging: imaginary_coherency's underlying
    Welch/CSD segmenting chops naturally through concatenated trial windows once nperseg is
    well under one trial's length (256 samples at ~1 kHz => ~4 Hz resolution, matching the
    narrowest canonical band, theta 4-8 Hz). Documented here rather than silently assumed.
  - Layer groups: 3 (superficial/mid/deep), from outputs/layers/channel_layers_all.csv's
    `putative_layer` column -- corrected 2026-07-30. The original 2026-07-29 pass used
    outputs/publication_visual_review/area_layer_tfr/layer_masks.json, believing it to be the
    only channel-level layer source in the corpus; that was wrong (found via an unrelated
    background search) -- channel_layers_all.csv has a real 3-way split AND covers all 21
    sessions (layer_masks.json covered only 15 probe-sessions and entirely lacked every V182o
    session, which is why the first pass only reached 11/9 usable sessions for figures 6/7).

OUTPUT: outputs/lfp_coupling_matrices/coupling.npz, keyed
  "{session_prefix}|{context}|{band}|{areaA}|{layerA}|{areaB}|{layerB}"
  -> array([icoh_abs_mean_observed, icoh_abs_mean_null_mean, icoh_abs_mean_null_std, n_shuffle])
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

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "archive_oneoff"))
sys.path.insert(0, str(REPO / "context" / "figures"))

from precompute_tfr_arrays import (  # noqa: E402
    condition_numbers_for, load_probe_areas, resolve_lfp_datasets,
)
from jnwb.spectral import laplacian_reference  # noqa: E402

META_ROOT = Path(os.environ.get("OMISSION_META_DIR", "D:/workspace/data/metadata"))
CHANNEL_LAYERS_PATH = REPO / "outputs/layers/channel_layers_all.csv"
LAYERS = ("sup", "mid", "deep")
READINESS = REPO / "artifacts/data/session_readiness.csv"
OUT_DIR = REPO / "outputs/lfp_coupling_matrices"

BANDS = {"theta": (4, 8), "alpha": (8, 14), "beta": (14, 30),
         "low_gamma": (30, 50), "high_gamma": (50, 80)}

# Stimulus window: p1 onset to d1 onset (present, real, in every condition).
# Omission window: p2 onset to d2 onset, RXRR only (p2 is the omitted slot in RXRR).
CONTEXTS = {
    "stimulus": {"window_s": (0.0, 0.531), "conditions": ["RXRR", "RRRR"]},
    "omission": {"window_s": (1.031, 1.562), "conditions": ["RXRR"]},
    # A/B/R stimulus-identity question (phase 2, 2026-07-30): is coupling identity-specific,
    # not just condition/event-specific? AXAB and BXBA are the A- and B-family conditions with
    # their omission at the SAME slot position (2) as RXRR -- see scripts/classify_omission_
    # units_grand.py's OMISSIONS dict, which defines "A"/"B"/"R" as which stimulus-sequence
    # family a trial's condition belongs to (AAAB-rooted / BBBA-rooted / RRRR-rooted), not a
    # raw per-trial visual identity independent of condition. Same window as "omission" above
    # (1.031-1.562 s) so the three are directly comparable; "identity_R" is intentionally
    # identical to "omission" (RXRR, same window) and is not re-extracted, only re-labelled in
    # the stats/figure step, so it can serve as the third arm of the comparison for free.
    "identity_A": {"window_s": (1.031, 1.562), "conditions": ["AXAB"]},
    "identity_B": {"window_s": (1.031, 1.562), "conditions": ["BXBA"]},
}

N_SHUFFLE = 1000
MAX_TRIALS_PER_CONDITION = 60  # tractability cap; real trials, not synthetic, just bounded
NPERSEG = 256


def load_layer_masks():
    """Returns {(session_prefix, lfp_key): {channel_idx: putative_layer}} from
    channel_layers_all.csv, restricted to labelled channels with a real sup/mid/deep call
    (excludes 'na'). channel_idx here is probe-local (confirmed 0-127 per probe, same indexing
    as probe_areas.json's channel_slices) -- no translation needed against cells_for_probe."""
    df = pd.read_csv(CHANNEL_LAYERS_PATH)
    df = df[df.labelled & df.putative_layer.isin(LAYERS)]
    out = {}
    for (sess, key), g in df.groupby(["session_prefix", "lfp_key"]):
        out[(sess, key)] = dict(zip(g.channel_idx, g.putative_layer))
    return out


def cells_for_probe(session_prefix, probe_name, meta, layer_masks):
    """Yield (area, layer, representative_channel_idx) for every (area, layer) cell this
    probe covers, or nothing for a layer with no labelled channels in that area."""
    ch_layer = layer_masks.get((session_prefix, meta["lfp_key"]))
    if not ch_layer:
        return
    for area, sl in meta["channel_slices"].items():
        lo, hi = sl["start"], sl["stop"]
        for layer in LAYERS:
            idx = sorted(ch for ch, lyr in ch_layer.items() if lyr == layer and lo <= ch < hi)
            if not idx:
                continue
            rep = int(idx[len(idx) // 2])
            yield area, layer, rep


def p1_onsets_and_conditions_s(f, conditions):
    """Return {condition: onsets_s array} using the same event filter as precompute_tfr_arrays."""
    g = f["intervals/omission_glo_passive"]
    def numeric(a):
        if a.dtype.kind in ("O", "S", "U"):
            return np.array([float(x.decode() if isinstance(x, bytes) else x) for x in a], dtype=float)
        return a.astype(float)
    sn = numeric(g["stimulus_number"][:])
    corr = numeric(g["correct"][:])
    tc = numeric(g["task_condition_number"][:])
    st = numeric(g["start_time"][:])
    cond_numbers = condition_numbers_for(f.filename)
    out = {}
    for cond in conditions:
        nums = cond_numbers[cond]
        mask = (sn == 2) & (corr == 1) & np.isin(tc, nums) & np.isfinite(sn) & np.isfinite(st)
        out[cond] = np.asarray(st[mask], dtype=float)
    return out


def extract_channel_segments(data, ts, fs, onsets_s, window_s, ref_channel_idx, n_channels_probe,
                              max_trials):
    """For each onset, pull the probe's channels needed for Laplacian re-referencing (the
    representative channel plus its immediate depth neighbors), re-reference, and keep only
    the representative channel's re-referenced trace for the requested window. Returns a 1D
    array: trial windows concatenated back-to-back."""
    lo = max(0, ref_channel_idx - 1)
    hi = min(n_channels_probe, ref_channel_idx + 2)
    local_rep = ref_channel_idx - lo
    need = int(round((window_s[1] - window_s[0]) * fs))
    segs = []
    for onset in onsets_s[:max_trials]:
        t0, t1 = onset + window_s[0], onset + window_s[1]
        if ts is not None:
            i0, i1 = int(np.searchsorted(ts, t0)), int(np.searchsorted(ts, t1))
        else:
            i0, i1 = int(round(t0 * fs)), int(round(t1 * fs))
        i0, i1 = max(0, i0), min(data.shape[0], i1)
        if i1 - i0 < need // 2:
            continue
        raw = np.asarray(data[i0:i1, lo:hi], dtype=np.float64)
        if raw.shape[0] < 3:
            continue
        ref = laplacian_reference(raw.T)  # (n_local_ch, n_samples)
        seg = ref[local_rep]
        if seg.shape[0] < need:
            seg = np.pad(seg, (0, need - seg.shape[0]), mode="edge")
        elif seg.shape[0] > need:
            seg = seg[:need]
        segs.append(seg)
    if not segs:
        return None
    return np.stack(segs)  # (n_trials, n_samples_per_trial)


def trial_band_fft(x_trials, fs, band):
    """One Hann-windowed rFFT per trial, restricted to the band's frequency bins.

    Returns (n_trials, n_band_bins) complex array. Computed once per channel per context;
    every downstream shuffle reuses these instead of re-running Welch/CSD from scratch --
    the earlier per-shuffle-Welch design took 257s for 30 pair-band-context cells on a
    3-cell pilot session (confirmed 2026-07-30), which does not scale to the corpus. Pxx/Pyy
    are order-independent (each trial's own power, unaffected by which trial pairs with
    which on the other channel), so only the cross term Sxy needs re-pairing per shuffle --
    that reduces each shuffle to one broadcasted multiply instead of a full spectral estimate.
    """
    n_trials, trial_len = x_trials.shape
    window = np.hanning(trial_len)
    U = np.sum(window ** 2)
    freqs = np.fft.rfftfreq(trial_len, d=1.0 / fs)
    fmask = (freqs >= band[0]) & (freqs < band[1])
    X = np.fft.rfft(x_trials * window[None, :], axis=1)[:, fmask] * np.sqrt(2.0 / (fs * U))
    return X, freqs[fmask]


def coupling_with_null_vectorized(x_trials, y_trials, fs, band, n_shuffle, rng):
    """Trial-averaged imaginary coherency plus a fully vectorized trial-shuffle null.

    Standard trial-based construction: average the complex cross-spectrum across trials
    (not concatenate-then-Welch), which is the textbook estimator for event-related data and
    makes the null exact and cheap -- see trial_band_fft's docstring for why.
    """
    n_trials = min(x_trials.shape[0], y_trials.shape[0])
    if n_trials < 5:
        return None
    X, _ = trial_band_fft(x_trials[:n_trials], fs, band)
    Y, _ = trial_band_fft(y_trials[:n_trials], fs, band)

    pxx = np.mean(np.abs(X) ** 2, axis=0)   # (n_bins,)
    pyy = np.mean(np.abs(Y) ** 2, axis=0)
    denom = np.sqrt(np.clip(pxx * pyy, 1e-30, None))

    sxy_obs = np.mean(X * np.conj(Y), axis=0)
    icoh_obs = np.mean(np.abs(np.imag(sxy_obs / denom)))

    perms = np.array([rng.permutation(n_trials) for _ in range(n_shuffle)])  # (n_shuffle, n_trials)
    Y_perm = Y[perms]                                    # (n_shuffle, n_trials, n_bins)
    sxy_null = np.mean(X[None, :, :] * np.conj(Y_perm), axis=1)  # (n_shuffle, n_bins)
    icoh_null = np.mean(np.abs(np.imag(sxy_null / denom[None, :])), axis=1)  # (n_shuffle,)

    return float(icoh_obs), float(np.mean(icoh_null)), float(np.std(icoh_null)), n_trials


def main(limit_sessions=None, sessions_filter=None):
    t_start = time.time()
    readiness = pd.read_csv(READINESS)
    ready = readiness[readiness.nwb_ok & readiness.sidecar_ok]
    if sessions_filter:
        ready = ready[ready.session_prefix.isin(sessions_filter)]
    if limit_sessions:
        ready = ready.head(limit_sessions)

    layer_masks = load_layer_masks()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    rng = np.random.default_rng(0)

    for _, row in ready.iterrows():
        session_prefix = row.session_prefix
        nwb_path = row.nwb_path
        stem = Path(nwb_path).stem
        try:
            probe_meta = load_probe_areas(META_ROOT, stem)
        except FileNotFoundError as e:
            print(f"  skip {session_prefix}: {e}")
            continue

        cells = []  # (area, layer, probe_name, rep_idx)
        for probe_name, meta in probe_meta.items():
            for area, layer, rep in cells_for_probe(session_prefix, probe_name, meta, layer_masks):
                cells.append((area, layer, probe_name, meta["lfp_key"], meta["n_channels"], rep))
        if len(cells) < 2:
            print(f"  skip {session_prefix}: <2 area/layer cells with layer masks")
            continue

        print(f"{session_prefix}: {len(cells)} area/layer cells, opening NWB...")
        try:
            with h5py.File(nwb_path, "r") as f:
                all_conds = sorted({c for ctx in CONTEXTS.values() for c in ctx["conditions"]})
                onsets_all = p1_onsets_and_conditions_s(f, all_conds)
                # Cache each cell's re-referenced, per-context concatenated trace once.
                cell_traces = {}
                lfp_cache = {}
                for area, layer, probe_name, lfp_key, n_ch, rep in cells:
                    if lfp_key not in lfp_cache:
                        lfp_cache[lfp_key] = resolve_lfp_datasets(f, lfp_key)
                    data, ts, fs = lfp_cache[lfp_key]
                    for ctx_name, ctx in CONTEXTS.items():
                        conds = [c for c in ctx["conditions"] if len(onsets_all.get(c, [])) > 0]
                        if not conds:
                            continue
                        onsets = np.concatenate([onsets_all[c][:MAX_TRIALS_PER_CONDITION]
                                                 for c in conds])
                        trials = extract_channel_segments(
                            data, ts, fs, onsets, ctx["window_s"], rep, n_ch,
                            MAX_TRIALS_PER_CONDITION * len(conds))
                        if trials is None:
                            continue
                        cell_traces[(area, layer, ctx_name)] = (trials, fs)

                cell_keys = sorted(set((a, l) for (a, l, _) in cell_traces))
                for ctx_name in CONTEXTS:
                    present = [(a, l) for (a, l) in cell_keys if (a, l, ctx_name) in cell_traces]
                    for i in range(len(present)):
                        for j in range(i + 1, len(present)):
                            aA, lA = present[i]
                            aB, lB = present[j]
                            x_trials, fs = cell_traces[(aA, lA, ctx_name)]
                            y_trials, fs2 = cell_traces[(aB, lB, ctx_name)]
                            for band_name, band in BANDS.items():
                                out = coupling_with_null_vectorized(
                                    x_trials, y_trials, fs, band, N_SHUFFLE, rng)
                                if out is None:
                                    continue
                                obs, null_mu, null_sd, n_trials = out
                                key = (f"{session_prefix}|{ctx_name}|{band_name}|"
                                      f"{aA}|{lA}|{aB}|{lB}")
                                results[key] = np.array([obs, null_mu, null_sd, N_SHUFFLE,
                                                        n_trials], dtype=np.float64)
        except Exception as e:
            print(f"  ERROR {session_prefix}: {e}")
            continue
        print(f"  {session_prefix}: {len(results)} cumulative pair-band-context results, "
              f"{time.time() - t_start:.0f}s elapsed")

    np.savez(OUT_DIR / "coupling.npz",
            keys=np.array(list(results.keys())),
            values=np.array(list(results.values())))
    with open(OUT_DIR / "receipt.json", "w", encoding="utf-8") as fh:
        json.dump({
            "n_sessions_attempted": int(len(ready)),
            "n_results": len(results),
            "bands_hz": {k: list(v) for k, v in BANDS.items()},
            "contexts": {k: {"window_s": v["window_s"], "conditions": v["conditions"]}
                        for k, v in CONTEXTS.items()},
            "max_trials_per_condition": MAX_TRIALS_PER_CONDITION,
            "n_shuffle": N_SHUFFLE,
            "nperseg": NPERSEG,
            "elapsed_s": time.time() - t_start,
        }, fh, indent=2)
    print(f"WROTE {OUT_DIR / 'coupling.npz'}  ({len(results)} results, "
          f"{time.time() - t_start:.0f}s)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-sessions", type=int, default=None)
    ap.add_argument("--sessions", default=None, help="comma-separated session_prefix filter")
    args = ap.parse_args()
    sf = args.sessions.split(",") if args.sessions else None
    main(limit_sessions=args.limit_sessions, sessions_filter=sf)
