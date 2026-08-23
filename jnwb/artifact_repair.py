r"""
jnwb.artifact_repair -- generic trial-segmented LFP/TFR artifact detection-and-substitution.

PROMOTED 2026-08-23 from omission.jnwb_ext.artifact_repair (99%-jnwb-sufficiency normalization):
the method here is fully generic -- it operates on plain (n_trials, n_channels, n_times) /
(n_trials, n_channels, n_freqs, n_times) arrays with no omission-task conditions, classes, or
windows baked in. `jnwb.artifact_detection` (bad-channel/bad-trial EXCLUSION) already
cross-referenced this module by name as its natural sibling before the promotion -- see that
module's own docstring. The two example numbers below (Z_THRESH=6.0, REWARD_WINDOW_MS) are
defaults tuned on the omission corpus during development, not omission-specific logic: both are
ordinary keyword arguments, fully overridable (pass `reward_window_ms=None` to disable that
default entirely) by any caller on any corpus.

Single source of truth for cross-channel-synchrony detection + cross-trial-median substitution
on raw (or band-filtered) LFP trial segments, shape (n_trials, n_channels, n_times). Do not
duplicate this logic per-script; import from here.

WHY THIS EXISTS / RECEIPT (historical record from the omission corpus that motivated this method)
    artifacts/.lab/lfp-movement-artifact-v198o-v182o-20260806.json documents, on this corpus,
    synchronous broadband impulses in raw LFP for subjects V198o and V182o (not C31o), confirmed
    two independent ways:
      (1) a cross-channel-synchrony detector: per-channel robust z-score via
          (x - median) / (1.4826*MAD), then median(|z|) ACROSS CHANNELS per timepoint -- a
          genuine shared deflection pushes most channels' |z| up together, independent
          per-channel noise does not. Validated threshold Z_THRESH=6.0 (lowered from an initial
          8 per user direction 2026-08-06). This is the detector geometry used here: raw-LFP
          movement artifacts are synchronous ACROSS CHANNELS WITHIN A TRIAL, a different
          geometry from the TFR-domain fix below (which is synchronous ACROSS TRIALS at a given
          band/time, within one channel-averaged trace).
      (2) a cross-trial-median detector (median/MAD computed per-channel, POOLED across trials
          and timepoints, not per-instant -- a per-instant MAD is itself inflated during a real
          evoked response and was shown to mask the single largest event in the reference
          dataset). That detector's own validated threshold is z=15, NOT reusable here -- it is
          a differently-scaled statistic (heavy-tailed, 99.9th pctile |z|~8.3) built to catch
          non-time-locked single-trial spikes, and is a documented example in the same lab
          record of a threshold that does NOT transfer between differently-constructed z-scores.
          This module's Z_THRESH=6.0 default is the (1) cross-channel-synchrony threshold, not
          the (2) cross-trial-median one -- do not conflate the two numbers.
    A critical confound was also found and fixed in the same record: reward is delivered at an
    essentially fixed post-p1 latency (V182o 4139-4142ms, V198o 4120-4138ms, <20ms jitter across
    trials, measured directly from the reward_1_tracking channel). Lowering the synchrony
    threshold started catching this reward-locked transient, which is a distinct phenomenon the
    user explicitly separated from "movement artifact in correct trials". This module excludes
    samples within REWARD_WINDOW_MS=(4000, 4300) ms of trial (p1) onset from repair eligibility,
    by default, mirroring `repair_lfp_movement_artifacts.py::reward_adjacent_mask`.

METHOD (this module -- a THIRD variant, built 2026-08-13, not identical to either prior script)
    Prior scripts (`scripts/repair_lfp_movement_artifacts.py`) detected via cross-channel
    synchrony but repaired via per-channel linear interpolation flanking each detected interval.
    Per direct instruction, this module instead repairs via CROSS-TRIAL-MEDIAN SUBSTITUTION --
    the same pattern as `context/figures/fig_v1_omission_band_dynamics/band_power_dynamics.py
    ::repair_band_artifacts` (TFR-domain), applied here to raw/band-filtered amplitude:
      1. Per trial, per channel: robust z of that channel's own within-trial values,
         z[trial, ch, t] = (x - median_t(x)) / (1.4826 * MAD_t(x)).
      2. synchrony[trial, t] = median over channels of |z[trial, :, t]| -- one non-negative
         statistic per (trial, time), large exactly when most channels move together at that
         instant (the movement-artifact signature; independent per-channel noise does not
         produce this).
      3. Flag (trial, time) where synchrony > z_thresh AND the timepoint is not within
         reward_window_ms of trial onset (excluded from repair eligibility entirely, not
         silently repaired).
      4. cross_trial_median[time, channel] = median over trials, at that channel, of the RAW
         (unflagged-and-flagged alike) input -- the same "2 11 2 -> 2 2 2" substitution used by
         repair_band_artifacts, not a temporal interpolation. For every flagged (trial, time),
         ALL channels at that time index are replaced by this cross-trial median. Substitution,
         not exclusion: the trial is kept.
    This trades detection power (per-trial local channel-count and per-trial MAD, vs the
    session-wide continuous scan in repair_lfp_movement_artifacts.py) for operating directly on
    the (n_trials, n_channels, n_times) contract every downstream extraction script already
    uses, avoiding a second raw-session h5py pass. n_trials < 5 disables repair (cross-trial
    median undefined / meaningless at that replicate count), matching repair_band_artifacts.

UNIT TEST: see `if __name__ == "__main__"` below -- synthetic (n_trials, n_channels, n_times)
array with one obvious injected cross-channel spike, checked before trusting this on real data
(per omission-signal skill: "verify a new spectral [here: repair] implementation against a
synthetic signal of known ... before running it on data").
"""
from __future__ import annotations

import numpy as np

Z_THRESH = 6.0                       # cross-channel-synchrony threshold, see docstring above
REWARD_WINDOW_MS = (4000.0, 4300.0)  # excluded from repair eligibility, see docstring above


def flagged_to_intervals(flagged, fs, pad_ms=40.0, merge_gap_ms=100.0):
    """Boolean flagged-sample array -> list of (start_idx, end_idx) padded, merged intervals.

    Belongs to the INTERVAL-INTERPOLATION repair method (``interpolate_intervals`` below),
    NOT the cross-trial-median method (``repair_lfp_trials`` above) -- the two methods are
    deliberately distinct (see module docstring's METHOD section), so this pair is not a
    replacement for repair_lfp_trials, just its own canonical home. Promoted 2026-08-14 from
    byte-identical copies in ``scripts/repair_lfp_movement_artifacts.py`` and
    ``scripts/check_lfp_movement_artifacts.py`` (the latter's own docstring already flagged
    itself as an intentional, self-acknowledged duplicate: "duplicated here (not imported) to
    keep this diagnostic script self-contained; keep the two in sync if either changes").
    """
    d = np.diff(flagged.astype(np.int8))
    starts = list(np.where(d == 1)[0] + 1)
    ends = list(np.where(d == -1)[0] + 1)
    if flagged[0]:
        starts = [0] + starts
    if flagged[-1]:
        ends = ends + [len(flagged)]
    pad = int(round(pad_ms / 1000.0 * fs))
    raw = [(max(0, s - pad), min(len(flagged), e + pad)) for s, e in zip(starts, ends)]
    raw.sort()
    gap = int(round(merge_gap_ms / 1000.0 * fs))
    merged = []
    for s, e in raw:
        if merged and s <= merged[-1][1] + gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def interpolate_intervals(seg, intervals):
    """Repair a (samples x channels) segment: per-channel linear interpolation across each
    (start_idx, end_idx) interval (indices local to ``seg``), using the single sample
    immediately before/after as the two anchors. Intervals partly or fully outside the segment
    are clipped and skipped if degenerate.

    See :func:`flagged_to_intervals` docstring -- same promotion, same "distinct from
    repair_lfp_trials" caveat.
    """
    out = seg.copy()
    n = seg.shape[0]
    for s, e in intervals:
        s = max(s, 1)
        e = min(e, n - 1)
        if e <= s:
            continue
        left = out[s - 1, :]
        right = out[e, :]
        ramp = np.linspace(0, 1, e - s + 2)[1:-1][:, None]
        out[s:e, :] = left[None, :] + ramp * (right - left)[None, :]
    return out


def repair_lfp_trials(segments, times_ms=None, z_thresh=Z_THRESH,
                      reward_window_ms=REWARD_WINDOW_MS, min_trials=5):
    """Cross-channel-synchrony detection + cross-trial-median substitution.

    Parameters
    ----------
    segments : ndarray, shape (n_trials, n_channels, n_times)
        Raw or band-filtered LFP, trial-segmented, all channels of interest for the
        synchrony statistic (more channels = a better-conditioned synchrony score; a
        single-digit channel count still works but is a weaker detector than the full
        probe -- state how many channels were used when reporting a repair rate).
    times_ms : ndarray, shape (n_times,), optional
        Time axis in ms relative to trial (p1) onset. Required only if reward_window_ms
        is not None (to exclude the reward-adjacent samples from repair eligibility).
    z_thresh : float
        Cross-channel-synchrony threshold (default 6.0, see module docstring).
    reward_window_ms : (float, float) or None
        Samples with times_ms in this half-open interval are never flagged for repair.
        Pass None to disable (e.g. if the input window doesn't reach the reward latency).
    min_trials : int
        Below this many trials, the cross-trial median is not meaningful; input is
        returned unchanged (matches repair_band_artifacts's n_trials < 5 guard).

    Returns
    -------
    repaired : ndarray, same shape as segments
    frac_flagged : float
        Fraction of (trial, time) cells flagged and substituted.
    diagnostics : dict
        n_trials, n_channels, n_times, n_flagged_cells, reward_excluded_cells,
        synchrony_z_max, z_thresh, reward_window_ms.
    """
    segments = np.asarray(segments, dtype=np.float64)
    if segments.ndim != 3:
        raise ValueError(f"segments must be (n_trials, n_channels, n_times), got shape {segments.shape}")
    n_trials, n_channels, n_times = segments.shape

    diagnostics = {
        "n_trials": int(n_trials), "n_channels": int(n_channels), "n_times": int(n_times),
        "z_thresh": float(z_thresh), "reward_window_ms": reward_window_ms,
        "n_flagged_cells": 0, "reward_excluded_cells": 0, "synchrony_z_max": 0.0,
    }
    if n_trials < min_trials:
        diagnostics["skipped_reason"] = f"n_trials < min_trials ({n_trials} < {min_trials})"
        return segments.copy(), 0.0, diagnostics

    # ---- per-trial, per-channel robust z over time -------------------------------------------
    med_t = np.median(segments, axis=2, keepdims=True)                       # (trials, ch, 1)
    mad_t = np.median(np.abs(segments - med_t), axis=2, keepdims=True) * 1.4826
    mad_t = np.where(mad_t < 1e-9, 1e-9, mad_t)
    z = (segments - med_t) / mad_t                                          # (trials, ch, times)

    # ---- cross-channel synchrony statistic per (trial, time) ---------------------------------
    synchrony = np.median(np.abs(z), axis=1)                                # (trials, times)
    diagnostics["synchrony_z_max"] = float(np.max(synchrony)) if synchrony.size else 0.0

    flagged = synchrony > z_thresh                                         # (trials, times)

    if reward_window_ms is not None and times_ms is not None:
        times_ms = np.asarray(times_ms, dtype=float)
        reward_mask = (times_ms >= reward_window_ms[0]) & (times_ms < reward_window_ms[1])
        diagnostics["reward_excluded_cells"] = int((flagged & reward_mask[None, :]).sum())
        flagged = flagged & ~reward_mask[None, :]

    diagnostics["n_flagged_cells"] = int(flagged.sum())
    frac_flagged = float(flagged.mean())
    if not flagged.any():
        return segments.copy(), frac_flagged, diagnostics

    # ---- cross-trial median substitution (repair_band_artifacts pattern) ---------------------
    cross_trial_median = np.median(segments, axis=0)                        # (channels, times)
    repaired = segments.copy()
    for ti in range(n_times):
        bad_trials = np.where(flagged[:, ti])[0]
        if bad_trials.size == 0:
            continue
        repaired[bad_trials, :, ti] = cross_trial_median[:, ti]

    return repaired, frac_flagged, diagnostics


DEFAULT_BANDS = {"Theta(4-8Hz)": (4, 8), "Alpha(8-14Hz)": (8, 14), "Beta(14-30Hz)": (14, 30),
                  "Gamma(Low,30-50Hz)": (30, 50), "Gamma(High,50-80Hz)": (50, 80)}
TFR_Z_THRESH = 6.0


def repair_band_artifacts(power, freqs, band_ranges=None, z_thresh=TFR_Z_THRESH):
    """Per-band, cross-trial-median substitution of sparse single-trial TFR power spikes.

    Promoted 2026-08-14 from ``context/figures/fig_v1_omission_band_dynamics/
    band_power_dynamics.py::repair_band_artifacts`` (byte-identical logic) into this module's
    "single source of truth" home, per the 2026-08-14 finding that TFR condition-map extraction
    (``scripts/extract_condition_tfr_maps_v2.py``) had no artifact rejection at all -- every
    trial's power was averaged into the session mean regardless of whether it carried a sharp,
    single-trial power spike absent from the other trials of the same condition. The original
    copy in band_power_dynamics.py is left as-is (out of scope to edit a live figure script for
    this promotion); keep the two in sync if either changes, same caveat already carried by this
    module's ``flagged_to_intervals``/``interpolate_intervals`` promotion above.

    2026-08-13 revision (carried over): detection runs separately per band (not pooled 3-200 Hz)
    so a spike confined to one band cannot be diluted below threshold by ~99 mostly-unaffected
    frequency rows.

    Per band: channel-mean power within that band's frequency rows, per trial x time.
    trend[time] = median over trials (the shared evoked shape); resid = value - trend;
    scale = median(|resid|) POOLED over all (trial, time) in that band (a single global scale,
    not one per time bin -- a per-time-bin MAD is itself inflated during the evoked response and
    would mask a real outlier there, the same fix validated for the raw-LFP cross-trial-median
    detector in artifacts/.lab/lfp-movement-artifact-v198o-v182o-20260806.json). Any (trial,
    time) with resid/scale beyond z_thresh has ALL channels and ALL of that band's frequency
    rows, at that time index only, replaced by the cross-trial median ("2 11 2 -> 2 2 2": median
    across trials at the same condition and time, not a temporal filter). One-sided: artifacts
    are power INCREASES, not decreases.

    power: (n_trials, n_channels, n_freqs, n_times). Returns (repaired, frac_flagged_by_band).
    """
    band_ranges = DEFAULT_BANDS if band_ranges is None else band_ranges
    n_trials = power.shape[0]
    if n_trials < 5:
        return power, {}   # too few trials for a cross-trial median to mean anything

    repaired = power.copy()
    frac_flagged = {}

    for name, (lo, hi) in band_ranges.items():
        sel = (freqs >= lo) & (freqs < hi)
        freq_idx = np.where(sel)[0]
        if freq_idx.size == 0:
            continue

        band_trace = power[:, :, sel, :].mean(axis=(1, 2))        # (trials, times)
        trend = np.median(band_trace, axis=0)                      # (times,)
        resid = band_trace - trend[None, :]
        scale = np.median(np.abs(resid))                           # single pooled robust scale
        if scale < 1e-12:
            frac_flagged[name] = 0.0
            continue
        z = resid / (1.4826 * scale)
        flagged = z > z_thresh                                     # one-sided: artifacts are increases
        frac_flagged[name] = float(flagged.mean())
        if not flagged.any():
            continue

        band_median = np.median(power[:, :, sel, :], axis=0)       # (channels, n_band_freqs, times)
        for ti in range(power.shape[-1]):
            bad_trials = np.where(flagged[:, ti])[0]
            for b in bad_trials:
                repaired[b][:, freq_idx, ti] = band_median[:, :, ti]

    return repaired, frac_flagged


if __name__ == "__main__":
    # Synthetic self-test: 20 trials, 8 channels, 200 samples (1kHz => 200ms), all channels
    # sharing a common slow evoked shape (so the detector must not simply flag "any deviation
    # from flat"), one trial (index 7) with a large, cross-channel-synchronous spike injected at
    # sample 100 -- the textbook movement-artifact signature this detector targets.
    rng = np.random.default_rng(0)
    n_trials, n_channels, n_times = 20, 8, 200
    t = np.arange(n_times)
    evoked = 5.0 * np.exp(-((t - 60) ** 2) / (2 * 15.0 ** 2))               # shared shape, uV
    base = evoked[None, None, :] + rng.normal(0, 1.0, size=(n_trials, n_channels, n_times))
    base[7, :, 100] += 40.0   # cross-channel synchronous spike, ~40x the noise SD, all channels

    repaired, frac, diag = repair_lfp_trials(base, times_ms=None, reward_window_ms=None)
    assert diag["n_flagged_cells"] >= 1, "self-test FAILED: injected spike not flagged"
    assert (7, ) or True
    flagged_here = np.abs(repaired[7, :, 100] - base[7, :, 100]).max() > 1.0
    assert flagged_here, "self-test FAILED: flagged cell was not substituted"
    untouched = np.allclose(repaired[0], base[0])
    assert untouched, "self-test FAILED: an unflagged trial was modified"
    print("jnwb.artifact_repair self-test PASSED:", diag)

    # Reward-window exclusion self-test: same spike, but now placed inside a declared reward
    # window -- must NOT be repaired.
    times_ms = np.linspace(0, 199, n_times)  # 0..199 ms
    base2 = evoked[None, None, :] + rng.normal(0, 1.0, size=(n_trials, n_channels, n_times))
    base2[7, :, 100] += 40.0
    repaired2, frac2, diag2 = repair_lfp_trials(
        base2, times_ms=times_ms, reward_window_ms=(90.0, 110.0), z_thresh=Z_THRESH)
    assert np.allclose(repaired2[7, :, 100], base2[7, :, 100]), \
        "self-test FAILED: reward-window sample was repaired despite exclusion"
    print("jnwb.artifact_repair reward-exclusion self-test PASSED:", diag2)

    # repair_band_artifacts self-test: 20 trials, 4 channels, 99 freq rows (3-201Hz step 2),
    # 50 time samples, all trials sharing a common band-power evoked shape in Alpha; one trial
    # gets a sharp Alpha-only power spike absent from the other 19 trials of the same condition
    # -- the exact "sharp increase across trials, not present in the rest" signature the user
    # asked to exclude 2026-08-14.
    freqs = np.arange(3, 201, 2, dtype=float)
    n_trials, n_channels, n_freqs, n_times = 20, 4, freqs.size, 50
    alpha_sel = (freqs >= 8) & (freqs < 14)
    evoked_t = 2.0 + 1.0 * np.exp(-((np.arange(n_times) - 25) ** 2) / (2 * 6.0 ** 2))
    power = 5.0 + rng.normal(0, 0.3, size=(n_trials, n_channels, n_freqs, n_times))
    power[:, :, alpha_sel, :] += evoked_t[None, None, None, :]
    power[3, :, alpha_sel, 30] += 30.0   # single-trial, single-band, single-timepoint spike

    repaired3, frac3 = repair_band_artifacts(power, freqs, band_ranges=DEFAULT_BANDS)
    assert frac3.get("Alpha(8-14Hz)", 0.0) > 0, "self-test FAILED: band spike not flagged"
    assert np.abs(repaired3[3, :, alpha_sel, 30] - power[3, :, alpha_sel, 30]).max() > 1.0, \
        "self-test FAILED: flagged band cell was not substituted"
    assert np.allclose(repaired3[0], power[0]), \
        "self-test FAILED: an unflagged trial/band was modified"
    assert np.allclose(repaired3[3, :, ~alpha_sel, :], power[3, :, ~alpha_sel, :]), \
        "self-test FAILED: a different band on the flagged trial was modified"
    print("jnwb.artifact_repair.repair_band_artifacts self-test PASSED:", frac3)
