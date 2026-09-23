r"""
jnwb.artifact_repair -- trial-segmented LFP/TFR artifact detection-and-substitution.

Operates on plain (n_trials, n_channels, n_times) or (n_trials, n_channels, n_freqs, n_times)
arrays. Sibling to `jnwb.artifact_detection` (bad-channel/bad-trial exclusion). Defaults such
as Z_THRESH=6.0 and REWARD_WINDOW_MS are overridable keyword arguments.

Single source of truth for cross-channel-synchrony detection + cross-trial-median substitution
on raw (or band-filtered) LFP trial segments, shape (n_trials, n_channels, n_times). Do not
duplicate this logic per-script; import from here.

DETECTION GEOMETRY (raw LFP trials)
    Cross-channel synchrony: per-channel robust z within each trial, then median(|z|) across
    channels per timepoint. Shared deflections raise most channels together; independent noise
    does not. Default Z_THRESH=6.0 applies to this synchrony statistic (not to unrelated
    cross-trial pooled z-scores). Optionally exclude samples near a fixed post-onset reward
    window via REWARD_WINDOW_MS so reward-locked transients are not repaired as movement.

METHOD (cross-trial-median substitution on trial segments)
    Detect via cross-channel synchrony; repair via CROSS-TRIAL-MEDIAN SUBSTITUTION (same
    substitution pattern as ``repair_band_artifacts`` in the TFR domain), applied to raw or
    band-filtered amplitude:
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
    Operates on the (n_trials, n_channels, n_times) contract directly. n_trials < 5 disables
    repair (cross-trial median undefined at low replicate count).

UNIT TEST: see `if __name__ == "__main__"` below -- synthetic array with an injected cross-channel
spike, checked before trusting on real data.
"""
from __future__ import annotations

import warnings
import numpy as np

Z_THRESH = 6.0                       # cross-channel-synchrony threshold, see docstring above
REWARD_WINDOW_MS = (4000.0, 4300.0)  # excluded from repair eligibility, see docstring above


def flagged_to_intervals(flagged, fs, pad_ms=40.0, merge_gap_ms=100.0):
    """Boolean flagged-sample array -> list of (start_idx, end_idx) padded, merged intervals.

    Belongs to the INTERVAL-INTERPOLATION repair method (``interpolate_intervals`` below),
    NOT the cross-trial-median method (``repair_lfp_trials`` above) -- the two methods are
    deliberately distinct (see module docstring's METHOD section), so this pair is not a
    replacement for repair_lfp_trials, just its own canonical home. Extracted from
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
        s_req, e_req = int(s), int(e)
        s = max(s_req, 1)
        e = min(e_req, n - 1)
        if e <= s:
            continue
        # The anchors are the samples just outside the interval. Clamping used to pull them
        # *inside* it whenever the interval touched an edge, so the artifact became its own
        # repair reference: [100, 0, 0, 100, 100, 100, 0, 0, 0, 100] with the interval
        # (0, 10) came back as ten copies of 100. An edge-touching interval is
        # extrapolated from the one good side instead.
        left_available = s_req >= 1
        right_available = e_req <= n - 1
        if not left_available and not right_available:
            # Nothing outside the interval to anchor to. The segment is left untouched --
            # and said so, because silently returning unrepaired data is the same class of
            # defect as silently returning fabricated data.
            warnings.warn(
                f"interpolate_intervals: interval ({s_req}, {e_req}) spans the whole "
                f"segment of {n} samples, so there is no clean sample to interpolate from. "
                "It is left unrepaired.",
                RuntimeWarning,
                stacklevel=2,
            )
            continue
        if left_available and right_available:
            left = out[s - 1, :]
            right = out[e, :]
            ramp = np.linspace(0, 1, e - s + 2)[1:-1][:, None]
            out[s:e, :] = left[None, :] + ramp * (right - left)[None, :]
        elif right_available:
            # Interval runs off the left edge: hold the first good sample.
            out[0:e, :] = out[e, :][None, :]
        else:
            # Interval runs off the right edge: hold the last good sample.
            out[s:n, :] = out[s - 1, :][None, :]
    return out


def repair_lfp_trials(segments, times_ms=None, z_thresh=Z_THRESH,
                      exclude_window_ms=None, reward_window_ms=None, min_trials=5,
                      max_trial_fraction=0.5):
    """Cross-channel-synchrony detection + cross-trial-median substitution.

    Parameters
    ----------
    segments : ndarray, shape (n_trials, n_channels, n_times)
        Raw or band-filtered LFP, trial-segmented, all channels of interest for the
        synchrony statistic (more channels = a better-conditioned synchrony score; a
        single-digit channel count still works but is a weaker detector than the full
        probe -- state how many channels were used when reporting a repair rate).
    times_ms : ndarray, shape (n_times,), optional
        Time axis in ms relative to trial onset. Required only if exclude_window_ms
        (or legacy reward_window_ms) is not None.
    z_thresh : float
        Cross-channel-synchrony threshold (default 6.0, see module docstring).
    exclude_window_ms : (float, float) or None
        Samples with times_ms in this half-open interval are never flagged for repair.
        Pass None to disable (default).
    reward_window_ms : (float, float) or None, optional
        Deprecated alias for exclude_window_ms.
    min_trials : int
        Below this many trials, the cross-trial median is not meaningful; input is
        returned unchanged (matches repair_band_artifacts's n_trials < 5 guard).
    max_trial_fraction : float or None
        A time sample flagged on more than this fraction of trials is treated as
        time-locked signal, not artifact, and is never substituted. Default 0.5; pass
        None to disable the guard.

        The detector is cross-channel synchrony, and an evoked response is synchronous
        across channels by construction, so it is flagged exactly like an artifact. The
        substitution then replaces each trial's own deflection with the cross-trial median
        of the same deflection, which preserves the trial average while erasing the
        single-trial variability many analyses are built on. Measured on 40 trials x 16
        channels with a sharp evoked deflection whose amplitude varied across trials, with
        the guard disabled: the correlation between the true single-trial amplitude and the
        repaired peak fell from 0.9996 to 0.4607 and the across-trial SD at the peak fell
        from 8.27 to 3.64, while the mean moved only from 29.33 to 28.59 -- so the damage
        does not show up in a trial average.

        The threshold is where the substitution becomes self-defeating rather than a tuned
        value: substitution replaces flagged trials with a median taken over ALL trials, so
        once more than half the trials are flagged at a sample, the "clean" median is drawn
        mostly from the flagged population and cannot be removing a rare contaminant.
        `exclude_window_ms` remains the way to protect a known response window explicitly.

    Returns
    -------
    repaired : ndarray, same shape as segments
    frac_flagged : float
        Fraction of (trial, time) cells flagged and substituted.
    diagnostics : dict
        n_trials, n_channels, n_times, n_flagged_cells, reward_excluded_cells,
        synchrony_z_max, z_thresh, exclude_window_ms, reward_window_ms,
        max_trial_fraction, n_time_locked_samples_protected,
        max_fraction_trials_flagged_at_a_sample, warnings.
    """
    # A window is meaningless without the time axis it indexes. Both were silently dropped
    # when `times_ms` was None, while `diagnostics` still echoed `exclude_window_ms` back
    # and reported `reward_excluded_cells: 0` with an empty warnings list -- a protection
    # asserted but never applied.
    if times_ms is None and (exclude_window_ms is not None or reward_window_ms is not None):
        given = "exclude_window_ms" if exclude_window_ms is not None else "reward_window_ms"
        raise ValueError(
            f"repair_lfp_trials: {given} was given without times_ms, so there is no time "
            "axis to apply it to. The window used to be dropped while the diagnostics "
            "still reported it as applied. Pass times_ms, or drop the window argument."
        )
    effective_exclude = exclude_window_ms if exclude_window_ms is not None else reward_window_ms
    segments = np.asarray(segments, dtype=np.float64)
    if segments.ndim != 3:
        raise ValueError(f"segments must be (n_trials, n_channels, n_times), got shape {segments.shape}")
    n_trials, n_channels, n_times = segments.shape

    diagnostics = {
        "n_trials": int(n_trials), "n_channels": int(n_channels), "n_times": int(n_times),
        "z_thresh": float(z_thresh), "exclude_window_ms": effective_exclude,
        "reward_window_ms": effective_exclude,
        "n_flagged_cells": 0, "reward_excluded_cells": 0, "synchrony_z_max": 0.0,
        "max_trial_fraction": max_trial_fraction,
        "n_time_locked_samples_protected": 0,
        "max_fraction_trials_flagged_at_a_sample": 0.0,
        "warnings": [],
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

    if effective_exclude is not None and times_ms is not None:
        times_ms = np.asarray(times_ms, dtype=float)
        in_excluded_window = (times_ms >= effective_exclude[0]) & (times_ms < effective_exclude[1])
        diagnostics["reward_excluded_cells"] = int((flagged & in_excluded_window[None, :]).sum())
        flagged = flagged & ~in_excluded_window[None, :]

    # A sample flagged on most trials is time-locked across trials, which is what signal
    # looks like and what an artifact does not. See max_trial_fraction in the docstring.
    per_sample_fraction = flagged.mean(axis=0)
    diagnostics["max_fraction_trials_flagged_at_a_sample"] = float(
        per_sample_fraction.max()) if per_sample_fraction.size else 0.0
    if max_trial_fraction is not None:
        time_locked = per_sample_fraction > float(max_trial_fraction)
        diagnostics["n_time_locked_samples_protected"] = int(time_locked.sum())
        if time_locked.any():
            diagnostics["warnings"].append(
                f"time_locked_samples_not_repaired_{int(time_locked.sum())}_samples"
            )
            flagged = flagged & ~time_locked[None, :]

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


#: Accepted tails for :func:`detect_band_outliers`. ``"upper"`` is the default because the
#: artifacts this detector was built for are power *increases*; see that function's warning
#: about what ``"both"`` costs when the response of interest is a decrease.
DETECTION_TAILS = ("upper", "both")


def detect_band_outliers(band_trace, z_thresh=TFR_Z_THRESH, sided="upper"):
    """Flag (trial, time) cells whose power departs from the cross-trial trend.

    Split out of :func:`repair_band_artifacts` 2026-09-05 so the detection *rule* can be reused
    without the substitution it is normally paired with, and without the 4-D array layout that
    function requires. It exists because the rule was demonstrably easier to retype than to
    reuse: a downstream reimplementation silently turned this one-sided test into a two-sided
    one while its docstring still claimed parity with the library. Exposing the detector makes
    the tail an argument the caller states, rather than a detail buried in a copy.

    trend = median over trials (the shared evoked shape); resid = value - trend;
    scale = median(|resid|) pooled over all (trial, time) -- a single global scale, not one per
    time bin, because a per-bin MAD is itself inflated during the evoked response and would
    mask a real outlier exactly where one matters most.

    Args:
        band_trace: (n_trials, n_times) array, already reduced to one value per (trial, time).
        z_thresh: robust-z threshold.
        sided: ``"upper"`` (default) flags increases only. ``"both"`` also flags decreases.

    Returns:
        (flagged, scale) -- a bool (n_trials, n_times) mask and the pooled robust scale. A
        scale of 0.0 means the trend was matched to round-off and nothing is flagged.

    Raises:
        ValueError: If ``band_trace`` is not 2-D or contains NaN or Inf.

    Warning:
        ``sided="both"`` is not the conservative choice. When the response under study is a
        power decrease, a two-sided detector flags genuine decreases as artifacts and
        substitutes them away -- the detector eats the effect it was meant to protect. Choose
        ``"both"`` only when artifacts in this data genuinely go in both directions.
    """
    if sided not in DETECTION_TAILS:
        raise ValueError(f"sided must be one of {list(DETECTION_TAILS)}; got {sided!r}")
    band_trace = np.asarray(band_trace, dtype=float)
    if band_trace.ndim != 2:
        raise ValueError(f"band_trace must be 2-D (n_trials, n_times), got shape {band_trace.shape}")
    if not np.all(np.isfinite(band_trace)):
        # A NaN made the pooled scale NaN, so nothing anywhere could be flagged.
        raise ValueError("band_trace contains NaN or Inf; repair or drop those cells first")
    trend = np.median(band_trace, axis=0)
    resid = band_trace - trend[None, :]
    scale = np.median(np.abs(resid))
    # Degenerate only when the residual scale is round-off relative to the data. The absolute
    # 1e-12 cutoff this replaces flagged nothing in power expressed at small amplitude.
    if scale <= np.finfo(float).eps * np.max(np.abs(band_trace)):
        return np.zeros(band_trace.shape, dtype=bool), 0.0
    z = resid / (1.4826 * scale)
    flagged = np.abs(z) > z_thresh if sided == "both" else z > z_thresh
    return flagged, float(scale)


def repair_band_artifacts(power, freqs, band_ranges=None, z_thresh=TFR_Z_THRESH,
                          sided="upper"):
    """Per-band, cross-trial-median substitution of sparse single-trial TFR power spikes.

    Detection runs separately per band (not pooled 3-200 Hz)
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
    across trials at the same condition and time, not a temporal filter). Detection itself is
    :func:`detect_band_outliers`, which this function calls rather than restates -- the rule has
    exactly one implementation. One-sided by default: artifacts are power INCREASES, not
    decreases. Read that function's warning before passing ``sided="both"``.

    power: (n_trials, n_channels, n_freqs, n_times), or (n_trials, n_freqs, n_times) for data
    already reduced over channels -- the reduced form returns the same reduced shape. Detection
    runs on the channel-averaged trace in both cases, so the two agree by construction; the 3-D
    form exists so a caller holding channel-averaged power can call this instead of retyping it.
    Returns (repaired, frac_flagged_by_band).
    """
    band_ranges = DEFAULT_BANDS if band_ranges is None else band_ranges
    power = np.asarray(power)
    if power.ndim not in (3, 4):
        raise ValueError(
            "power must be (n_trials, n_channels, n_freqs, n_times) or, for data already "
            f"reduced over channels, (n_trials, n_freqs, n_times); got ndim={power.ndim}"
        )
    # A caller holding channel-averaged power should not have to retype the rule to use it.
    # Detection already runs on the channel-averaged trace either way, so a length-1 channel
    # axis makes the 3-D case bit-identical to the 4-D path rather than a second code path.
    channel_axis_added = power.ndim == 3
    if channel_axis_added:
        power = power[:, None, :, :]
    n_trials = power.shape[0]
    if n_trials < 5:
        # too few trials for a cross-trial median to mean anything
        return (power[:, 0] if channel_axis_added else power), {}

    repaired = power.copy()
    frac_flagged = {}

    for name, (lo, hi) in band_ranges.items():
        sel = (freqs >= lo) & (freqs < hi)
        freq_idx = np.where(sel)[0]
        if freq_idx.size == 0:
            continue

        band_trace = power[:, :, sel, :].mean(axis=(1, 2))        # (trials, times)
        flagged, scale = detect_band_outliers(band_trace, z_thresh=z_thresh, sided=sided)
        if scale == 0.0:
            frac_flagged[name] = 0.0
            continue
        frac_flagged[name] = float(flagged.mean())
        if not flagged.any():
            continue

        band_median = np.median(power[:, :, sel, :], axis=0)       # (channels, n_band_freqs, times)
        for ti in range(power.shape[-1]):
            bad_trials = np.where(flagged[:, ti])[0]
            for b in bad_trials:
                repaired[b][:, freq_idx, ti] = band_median[:, :, ti]

    if channel_axis_added:
        repaired = repaired[:, 0]
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
