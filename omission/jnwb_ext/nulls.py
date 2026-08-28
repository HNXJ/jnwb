"""omission.jnwb_ext.nulls -- shared null/permutation primitives for temporal-coupling analyses.

P1 of the 2026-08-27 causal SPK-LFP coupling + omission-vs-matched-empty-time work (Hamm). Both
analysis families need exchangeable nulls beyond plain label permutation
(``jnwb.permutation.permute_labels``, which only handles "global"/"within_group" label shuffles,
not time-series shifts or spike-time jitter -- confirmed missing by the 2026-08-27 prepare-phase
audit). These are pure-array primitives with no omission condition/session coupling baked in --
candidates for later jnwb promotion (see module docstring bottom), but implemented and validated
here first per Hamm's explicit "prototype in omission, promote later" sequencing.

Do NOT copy these into individual figure/analysis scripts. Import from here.

Three primitives:
  - ``circular_shift``: temporal circular shift, per trial/segment, with a configurable
    zero-lag exclusion zone, for continuous signals (LFP/band-power).
  - ``spike_jitter``: independent per-spike time jitter, count-preserving, trial-bounded.
  - ``trial_permutation``: thin, explicitly-documented wrapper over
    ``jnwb.permutation.permute_labels(scheme="within_group")`` for condition/position-matched
    trial-label permutation -- reuses the existing validated primitive rather than
    reimplementing it (per Hamm's explicit "reuse existing grouped permutation machinery"
    instruction), it exists here only to name the omission-relevant grouping key explicitly.
"""
from __future__ import annotations

import numpy as np

from jnwb.permutation import permute_labels


def circular_shift(
    signal: np.ndarray,
    *,
    fs: float,
    exclusion_zone_ms: float = 0.0,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Circularly shift each trial/segment independently, excluding a zero-lag zone.

    Args:
        signal: shape (n_trials, n_times) -- one continuous segment per row. A 1-D (n_times,)
            input is treated as a single trial and returned with a length-1 leading axis
            preserved on the shift-amount output only (signal shape is returned unchanged).
        fs: sampling rate in Hz, used to convert ``exclusion_zone_ms`` to samples.
        exclusion_zone_ms: minimum |shift| in ms. Shifts are drawn uniformly from the allowed
            integer-sample range EXCLUDING (-exclusion_samples, +exclusion_samples), so the null
            never includes a near-identity (trivially non-informative) shift. 0.0 disables this
            (any nonzero shift, including small ones, is eligible).
        rng: explicit ``numpy.random.Generator`` -- no implicit global RNG state.

    Returns:
        (shifted, shift_samples): ``shifted`` has the same shape/dtype as ``signal``.
        ``shift_samples`` has shape (n_trials,), the actual integer sample shift applied to each
        trial (signed; positive = rolled forward). Report this alongside any null result so the
        realized shift is auditable, not just the requested policy.

    Each trial is shifted independently via ``np.roll`` -- a true circular wrap WITHIN that
    trial's own samples only. Trials are never concatenated or shifted across each other's
    boundaries (the exact invalid-wrap failure mode the caller must avoid), so autocorrelation
    and spectral content within each trial are exactly preserved (a circular shift is a pure
    reindexing, not a resampling) and no cross-trial/cross-event contamination is possible.
    """
    was_1d = signal.ndim == 1
    x = signal[None, :] if was_1d else signal
    if x.ndim != 2:
        raise ValueError(f"signal must be 1-D or 2-D (n_trials, n_times), got shape {signal.shape}")
    n_trials, n_times = x.shape
    if n_times < 2:
        raise ValueError(f"circular_shift requires at least 2 samples per trial, got n_times={n_times}")
    excl = int(round(exclusion_zone_ms * fs / 1000.0))
    if excl * 2 >= n_times:
        raise ValueError(
            f"exclusion_zone_ms={exclusion_zone_ms} (±{excl} samples) leaves no valid shift "
            f"within a {n_times}-sample trial"
        )

    shifts = np.empty(n_trials, dtype=int)
    out = np.empty_like(x)
    for i in range(n_trials):
        if excl == 0:
            # any nonzero shift is valid; 0 itself excluded (identity shift is never a "shift")
            candidates_lo, candidates_hi = 1, n_times
        else:
            candidates_lo, candidates_hi = excl, n_times - excl
        # draw uniformly from the valid magnitude range, then a random sign, then re-check
        # against the exclusion zone (handles the excl==0 half-open case above cleanly)
        while True:
            s = int(rng.integers(candidates_lo, candidates_hi))
            if rng.integers(0, 2):
                s = -s
            s_mod = s % n_times
            if s_mod == 0:
                continue
            wrapped = min(s_mod, n_times - s_mod)
            if wrapped >= max(excl, 1):
                break
        shifts[i] = s
        out[i] = np.roll(x[i], s)

    return (out[0] if was_1d else out), shifts


def spike_jitter(
    spike_times: np.ndarray,
    *,
    trial_start: float,
    trial_end: float,
    jitter_range: tuple[float, float],
    rng: np.random.Generator,
    boundary: str = "reflect",
) -> np.ndarray:
    """Independently jitter each spike time within one trial, preserving spike count exactly.

    Args:
        spike_times: 1-D array of spike times (same units as trial_start/trial_end, e.g.
            seconds), all required to already lie within [trial_start, trial_end).
        trial_start, trial_end: this trial's own bounds. A spike is NEVER moved into a different
            trial -- boundary handling (below) is applied strictly within [trial_start, trial_end).
        jitter_range: (lo, hi) in the same units as spike_times; each spike's offset is drawn
            uniformly from [lo, hi] independently (pass a symmetric range like (-0.010, 0.010)
            for ±10 ms jitter). Not a Gaussian SD -- explicit bounded support, so the maximum
            possible excursion is always known exactly.
        rng: explicit ``numpy.random.Generator``.
        boundary: one of:
            "reflect" (default) -- a jittered time outside [trial_start, trial_end) is reflected
                back in (e.g. trial_end + d -> trial_end - d), preserving spike count and never
                crossing the boundary; the standard choice, since it neither drops nor duplicates
                a spike near the edge.
            "clip" -- clamp to the nearest boundary (introduces a small pileup at the edges for
                spikes that would have jittered past it; use only if reflection is scientifically
                undesirable for a specific check).

    Returns:
        1-D array, same shape/dtype as ``spike_times``, exactly one jittered time per input spike
        (count-preserving by construction -- no spike is ever added or dropped).
    """
    if boundary not in ("reflect", "clip"):
        raise ValueError(f"boundary must be 'reflect' or 'clip', got {boundary!r}")
    spike_times = np.asarray(spike_times)
    out_dtype = spike_times.dtype if np.issubdtype(spike_times.dtype, np.floating) else np.float64
    spike_times = spike_times.astype(np.float64)
    if spike_times.size and (spike_times.min() < trial_start or spike_times.max() >= trial_end):
        raise ValueError("all spike_times must lie within [trial_start, trial_end) before jitter")

    lo, hi = jitter_range
    offsets = rng.uniform(lo, hi, size=spike_times.shape)
    jittered = spike_times + offsets

    if boundary == "clip":
        jittered = np.clip(jittered, trial_start, np.nextafter(trial_end, trial_start))
    else:  # reflect, possibly more than once for large offsets near a narrow trial
        span = trial_end - trial_start
        for _ in range(8):  # bounded iterations; a single reflection suffices unless span is tiny
            too_low = jittered < trial_start
            too_high = jittered >= trial_end
            if not (too_low.any() or too_high.any()):
                break
            jittered[too_low] = 2 * trial_start - jittered[too_low]
            jittered[too_high] = 2 * trial_end - jittered[too_high]
        jittered = np.clip(jittered, trial_start, np.nextafter(trial_end, trial_start))

    return jittered.astype(out_dtype, copy=False)


def trial_permutation(
    labels: np.ndarray,
    *,
    condition_position_group: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Permute trial labels within condition x position groups -- explicit reuse wrapper.

    Thin, documented wrapper over the existing, validated
    ``jnwb.permutation.permute_labels(scheme="within_group")`` (not a reimplementation, per
    Hamm's explicit "reuse existing grouped permutation machinery where valid" instruction). This
    function exists only to name the grouping key an omission analysis actually needs
    (condition x position composite, so exchangeability holds within scientifically matched
    trials) rather than requiring every call site to remember to build that key correctly.

    Args:
        labels: label array to permute, shape (n,).
        condition_position_group: composite group id per trial (e.g. a string or int encoding
            condition x omission-position), shape (n,). Permutation is exchangeable only within
            each distinct value of this group.
        rng: explicit ``numpy.random.Generator``.

    Returns:
        Permuted copy of ``labels``, same shape/dtype.
    """
    return permute_labels(labels, groups=condition_position_group, scheme="within_group", rng=rng)
