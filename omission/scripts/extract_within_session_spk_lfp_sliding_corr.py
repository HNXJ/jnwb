r"""
Within-session, trial-matched sliding-window SPIKE-LFP coupling -- replaces PPC (retired per
omission-signal skill: "PPC is retired as the spike-LFP method... trial-level correlation
between a channel's band power and a unit's spike rate in the same sliding window").

Splices together the two already-validated sliding-window engines exactly as directed:
  - scripts/extract_within_session_spk_spk_sliding_corr.py: good-unit selection
    (good_units_per_area), spike-rate trace via omission.jnwb_ext.connectivity.bin_spikes(output="rate").
  - scripts/extract_within_session_lfp_lfp_sliding_corr.py: good-channel selection
    (good_channels_per_area, from the existing channel_band_power_v2 census), band-power trace
    from the precomputed TFR .npy arrays (band_power_trace).
  - Both run through the shared engine in scripts/smoke_test_sliding_trial_correlation.py
    (sliding_corr_same_trial, _sliding_windows, _corr_and_null) -- same trial-matched vs
    trial-mismatch-shuffle null design, not reimplemented.

A unit's spike-rate trace is correlated against its OWN PROBE's (own area's) band-power trace,
same trial, sliding window -- per direct instruction. Same-electrode exclusion mirrors
extract_spike_lfp_coupling.py's EXCLUDE_RADIUS pattern: a unit's own spike waveform can leak
into a nearby LFP channel, so the chosen "good" channel for the unit's area is skipped if it
falls within EXCLUDE_RADIUS channels of that unit's own peak_channel_id, falling to the next-
best-ranked channel instead (not silently included).

ARTIFACT REPAIR: the TFR power array for each (session, probe, area, RXRR) file is passed
through context/figures/fig_v1_omission_band_dynamics/band_power_dynamics.py::
repair_band_artifacts BEFORE any band-power trace is extracted -- shape (n_trials, n_channels,
n_freqs, n_times) matches that function's contract directly (same TFR precompute pipeline,
same FREQS/TIMES_P1 convention), no shape adaptation needed. Per-band cross-trial-median
substitution, z_thresh=6.0 (that module's own default), same as tonight's TFR-domain fix.

OUTPUT
    outputs/within_session_spk_lfp_sliding_corr/<session>.npz -- real/null_mean/null_std,
        shape (n_pairs, n_bands, n_windows); pairs: "unit_row|area|channel"; centers_ms; bands.
    outputs/within_session_spk_lfp_sliding_corr/index.csv
    outputs/within_session_spk_lfp_sliding_corr/receipt.json
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from itertools import product

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "context", "figures", "fig_v1_omission_band_dynamics"))

import omission as oa  # noqa: E402
from omission.jnwb_ext.unit_classification import precompute_condition_onsets  # noqa: E402
from omission.jnwb_ext.connectivity import bin_spikes  # noqa: E402
from smoke_test_sliding_trial_correlation import (  # noqa: E402
    band_power_trace, sliding_corr_same_trial, WIN_HALF_MS, STEP_MS, BIN_MS,
)
from extract_within_session_spk_spk_sliding_corr import (  # noqa: E402
    good_units_per_area, N_GOOD_UNITS, MIN_FIRING_RATE_HZ, COND, WIN_S,
)
from extract_within_session_lfp_lfp_sliding_corr import (  # noqa: E402
    good_channels_per_area, BANDS, AREA_POOL, WIN_MS as LFP_WIN_MS,
)
from band_power_dynamics import repair_band_artifacts  # noqa: E402
from jnwb import paths as _P

NWB_DIR = _P.nwb_dir()
UNITS_CSV = _P.REPO_ROOT / "outputs/classification/omission_grand_units.csv"
CENSUS = _P.REPO_ROOT / "outputs/lfp_band_census_v2/channel_band_power.csv.gz"
TFR_DIR = _P.tfr_dir()
OUT_DIR = _P.REPO_ROOT / "outputs/within_session_spk_lfp_sliding_corr"

EXCLUDE_RADIUS = 2       # channels; same-electrode contamination control, matches
                         # extract_spike_lfp_coupling.py's convention
N_CHANNEL_CANDIDATES = 6  # how many top-ranked "good" channels to consider before giving up
                         # on finding one outside EXCLUDE_RADIUS of a given unit's peak channel

FNAME_RE = re.compile(r"^sub-(?P<subject>.+?)_ses-(?P<session>.+?)-(?P<probe>[A-Z])-"
                      r"(?P<area>.+)-(?P<cond>[A-Z]+)$")

FREQS = np.arange(3, 201, 2, dtype=float)   # matches band_power_dynamics.py / TFR precompute


def find_area_files(session_tag, cond):
    """Returns {area10: path} for this session's RXRR TFR files, one per (probe, area),
    area-pooled via AREA_POOL (V3/V3a/V3d -> V3a/d) -- same convention as the LFP-LFP script.

    NOTE: the on-disk TFR precompute pipeline writes .npz (keyed "power"), matching
    band_power_dynamics.py's find_area_condition_files/load_session_condition -- NOT .npy as
    smoke_test_sliding_trial_correlation.py and extract_within_session_lfp_lfp_sliding_corr.py
    assume (confirmed: 970 .npz files, 0 .npy files under jnwb.paths.tfr_dir() as of 2026-08-13).
    Those two scripts' own TFR-loading path is therefore currently broken against real data --
    flagged separately (not fixed here, out of this script's scope); this function uses the
    correct, verified-working .npz convention instead of copying the stale one."""
    out = {}
    for f in glob.glob(os.path.join(TFR_DIR, f"*{session_tag}*-{cond}.npz")):
        m = FNAME_RE.match(os.path.basename(f)[:-4])
        if not m:
            continue
        area10 = AREA_POOL.get(m["area"], m["area"])
        out[area10] = f  # last one wins if duplicate area token in one session
    return out


def choose_channel(ranked_channels, peak_channel_id, exclude_radius=EXCLUDE_RADIUS):
    """First of ranked_channels (best-first) that is NOT within exclude_radius of
    peak_channel_id; None if every candidate is excluded (unit skipped for this pass, not
    silently coupled to a possibly-contaminated channel)."""
    if peak_channel_id is None or not np.isfinite(peak_channel_id):
        return ranked_channels[0] if len(ranked_channels) else None
    for ch in ranked_channels:
        if abs(int(ch) - int(peak_channel_id)) > exclude_radius:
            return int(ch)
    return None


def main(limit_sessions=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    units_df = pd.read_csv(UNITS_CSV)
    census = pd.read_csv(CENSUS)
    sessions = sorted(units_df.session.unique())
    if limit_sessions:
        sessions = sessions[:limit_sessions]

    win_half_bins = int(round(WIN_HALF_MS / BIN_MS))
    step_bins = int(round(STEP_MS / BIN_MS))
    band_names = list(BANDS)

    index_rows = []
    receipt_repair = {}
    t0 = time.time()
    for si, session in enumerate(sessions, 1):
        candidates = [os.path.join(NWB_DIR, f"{session}_rec.nwb"),
                     os.path.join(NWB_DIR, f"{session}.nwb")]
        path = next((p for p in candidates if os.path.exists(p)), None)
        if path is None:
            continue
        try:
            sess = oa.read(path)
        except Exception:
            continue
        onsets = precompute_condition_onsets(sess, correct_only=True)
        trial_starts = onsets.get(COND, np.array([]))
        if len(trial_starts) < 5:
            continue

        good_u = good_units_per_area(units_df, session)
        good_c = good_channels_per_area(census, session)
        if not good_u:
            continue

        session_tag = session.split("sub-")[1] if "sub-" in session else session
        files = find_area_files(session_tag, COND)
        areas_present = [a for a in good_u if a in files and a in good_c]
        if not areas_present:
            continue

        i0 = int(round((LFP_WIN_MS[0] - (-1000.0)) / BIN_MS))
        i1 = int(round((LFP_WIN_MS[1] - (-1000.0)) / BIN_MS))

        pairs = []      # (unit_row, area, channel, local_pos)
        rate_traces = {}
        power_by_area = {}
        channel_pos_by_area = {}
        for a in areas_present:
            npz = np.load(files[a], allow_pickle=True)
            raw_power = npz["power"].astype(np.float64)
            # "channels" carries this file's PROBE-GLOBAL channel id per array position (e.g.
            # MT shares a probe with V1 at 64-127; V4/V3 sit at 0-63) -- census/peak_channel_id
            # are also probe-global, so array indexing must go through this map, never assume
            # the array position equals the probe-global channel number (confirmed by direct
            # check: V4's own channels happen to be 0-63, identical to array position by
            # coincidence, but MT's are 64-127 and indexing by raw channel id there is a
            # confirmed off-by-64 IndexError).
            channels = npz["channels"]
            channel_pos_by_area[a] = {int(c): i for i, c in enumerate(channels)}
            n0, n1 = max(0, i0), min(raw_power.shape[3], i1)
            window_power = raw_power[:, :, :, n0:n1]
            repaired, frac_flagged = repair_band_artifacts(window_power, FREQS)
            power_by_area[a] = repaired
            receipt_repair[f"{session}|{a}"] = frac_flagged

            for unit_row, _score in good_u[a]:
                row = units_df[(units_df.session == session) & (units_df.unit_row == unit_row)]
                peak_ch = float(row.peak_channel_id.iloc[0]) if len(row) else np.nan
                ch = choose_channel([c for c in good_c[a] if int(c) in channel_pos_by_area[a]],
                                    peak_ch)
                if ch is None:
                    continue
                try:
                    st = sess.get_spike_times(unit_row)
                except Exception:
                    continue
                if st is None or len(st) == 0:
                    continue
                rate = bin_spikes(st, window=WIN_S, bin_size_ms=BIN_MS,
                                  trial_starts=trial_starts, output="rate")
                rate_traces[unit_row] = rate
                pairs.append((unit_row, a, ch, channel_pos_by_area[a][int(ch)]))

        if not pairs:
            continue

        n_windows = len(np.arange(win_half_bins, (i1 - i0) - win_half_bins, step_bins))
        results = np.full((len(pairs), len(band_names), n_windows), np.nan, dtype=np.float32)
        null_mean = np.full((len(pairs), len(band_names), n_windows), np.nan, dtype=np.float32)
        null_std = np.full((len(pairs), len(band_names), n_windows), np.nan, dtype=np.float32)
        n_trials_used = np.zeros(len(pairs), dtype=np.int32)
        centers = None

        for pi, (unit_row, a, ch, local_pos) in enumerate(pairs):
            x = rate_traces[unit_row]                      # (n_trials, n_t)
            arr = power_by_area[a]                         # (n_trials, n_ch, n_freqs, n_t_win)
            n_tr = min(x.shape[0], arr.shape[0])
            n_t_common = min(x.shape[1], arr.shape[3])
            x_ = x[:n_tr, :n_t_common]
            for bi, (lo, hi) in enumerate(BANDS.values()):
                fmask = (FREQS >= lo) & (FREQS < hi)
                y_ = arr[:n_tr, local_pos, fmask, :n_t_common].mean(axis=1)  # (n_tr, n_t_common)
                real, null, c = sliding_corr_same_trial(x_, y_, win_half_bins, step_bins)
                centers = c
                nw = min(real.shape[1], n_windows)
                results[pi, bi, :nw] = np.nanmean(real[:, :nw], axis=0)
                null_mean[pi, bi, :nw] = null[:, :nw].mean(axis=0)
                null_std[pi, bi, :nw] = null[:, :nw].std(axis=0)
            n_trials_used[pi] = n_tr

        if centers is None:
            continue
        np.savez_compressed(
            os.path.join(OUT_DIR, f"{session}.npz"),
            real=results, null_mean=null_mean, null_std=null_std,
            n_trials=n_trials_used, centers_ms=centers.astype(np.float32) * BIN_MS,
            bands=np.array(band_names),
            pairs=np.array([f"{u}|{a}|{c}" for u, a, c, _lp in pairs]))
        index_rows.append({"session": session, "n_pairs": len(pairs),
                           "areas": areas_present, "n_windows": n_windows})
        print(f"[{datetime.now():%H:%M:%S}] session {si}/{len(sessions)} ({session}), "
             f"{len(pairs)} unit-channel pairs, {time.time()-t0:.0f}s total", flush=True)

    pd.DataFrame(index_rows).to_csv(os.path.join(OUT_DIR, "index.csv"), index=False)
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "purpose": "Within-session, trial-matched sliding-window SPK-LFP correlation "
                  "(replaces retired PPC method); unit spike-rate trace vs its own area's "
                  "artifact-repaired band-power trace, same-electrode exclusion.",
        "n_good_units_per_area": N_GOOD_UNITS, "min_firing_rate_hz": MIN_FIRING_RATE_HZ,
        "exclude_radius_channels": EXCLUDE_RADIUS, "condition": COND,
        "window_s_re_p1": list(WIN_S), "bin_ms": BIN_MS,
        "sliding_half_width_ms": WIN_HALF_MS, "sliding_step_ms": STEP_MS,
        "artifact_repair": "band_power_dynamics.repair_band_artifacts, per-band cross-trial-"
                          "median substitution, z_thresh=6.0",
        "n_sessions_processed": len(index_rows),
        "runtime_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"\nWROTE {OUT_DIR}/ ({len(index_rows)} sessions), index.csv, receipt.json")


if __name__ == "__main__":
    main(limit_sessions=int(sys.argv[1]) if len(sys.argv) > 1 else None)
