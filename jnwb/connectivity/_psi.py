"""The phase slope index."""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from .._rng import Default, RNGLike, resolve_seed_alias
from scipy import stats
from ..spectral import CANONICAL_BANDS
from ._common import DirectedResult, _surrogate_p, _surrogate_rng, _surrogate_scheme, _surrogate_source
from ._trials import _detrend_trials, _pair_trials


# ---------------------------------------------------------------------------
# 2. Phase slope index (frequency-domain, volume-conduction robust)
# ---------------------------------------------------------------------------


def _welch_segments(a: np.ndarray, nperseg: int, noverlap: int) -> np.ndarray:
    """Slice (n_trials, n_times) into (n_segments, nperseg), never crossing trials."""
    step = max(1, nperseg - noverlap)
    segs = []
    n_times = a.shape[1]
    for tr in range(a.shape[0]):
        for start in range(0, n_times - nperseg + 1, step):
            segs.append(a[tr, start : start + nperseg])
    if not segs:
        raise ValueError(
            f"no segments: nperseg={nperseg} exceeds n_times={n_times}"
        )
    return np.asarray(segs, dtype=float)


#: Fewest trials for which the jackknife leaves out a trial rather than a segment.
_MIN_TRIALS_FOR_TRIAL_JACKKNIFE = 3

#: Fewest Welch segments the default ``nperseg`` leaves, pooled over trials, when the record
#: allows it.
_DEFAULT_MIN_SEGMENTS = 20


# INTENTIONAL BREAK (0.2.10): the default was ``n_times // 4`` alone, which leaves 7 segments
# on one trial, so the coherency and the jackknife were estimated from 7.
def _default_nperseg(n_trials: int, n_times: int) -> int:
    """``n_times // 4`` clipped to ``[16, n_times]``, shortened until the record holds
    ``_DEFAULT_MIN_SEGMENTS`` segments at half overlap, and never below 16 samples."""
    def n_segments(length: int) -> int:
        return n_trials * ((n_times - length) // (length - length // 2) + 1)

    length = int(np.clip(n_times // 4, 16, n_times))
    while length > 16 and n_segments(length) < _DEFAULT_MIN_SEGMENTS:
        length -= 1
    return length


def _psi_from_spectra(
    fx: np.ndarray, fy: np.ndarray, idx: np.ndarray, weights: Optional[np.ndarray] = None
) -> float:
    """PSI over the frequency indices ``idx`` from per-segment FFTs."""
    sxy = np.mean(fx * np.conj(fy), axis=0)
    sxx = np.mean(np.abs(fx) ** 2, axis=0)
    syy = np.mean(np.abs(fy) ** 2, axis=0)
    denom = np.sqrt(sxx * syy)
    coh = np.divide(sxy, denom, out=np.zeros_like(sxy), where=denom > 0)
    c = coh[idx]
    return float(np.sum(np.imag(np.conj(c[:-1]) * c[1:])))


def _psi_leave_one_out(
    fx: np.ndarray, fy: np.ndarray, idx: np.ndarray, n_units: Optional[int] = None
) -> np.ndarray:
    """PSI over ``idx`` with each unit left out in turn: one replicate per unit.

    A unit is ``n_seg // n_units`` consecutive segments, one trial's segments when
    ``n_units`` is the trial count; ``None`` makes each segment a unit. Replicate ``i`` is
    ``_psi_from_spectra`` on every segment outside unit ``i``. Its spectra are means over the
    remaining segments, and each such sum is a prefix sum plus a suffix sum over the unit
    sums, so all ``U`` replicates cost T(S * B) over the ``B`` bins in ``idx`` instead of
    T(U * S * B) for recomputing each from its segments. The two sums are added rather than
    one unit being subtracted from the total: a subtraction cancels when one unit holds most
    of a bin's power.
    """
    ax = fx[:, idx]
    ay = fy[:, idx]
    n_seg = ax.shape[0]
    n_units = n_seg if n_units is None else int(n_units)
    per_unit = n_seg // n_units

    def left_out_mean(v: np.ndarray) -> np.ndarray:
        if per_unit > 1:
            v = v.reshape(n_units, per_unit, -1).sum(axis=1)
        before = np.zeros_like(v)
        np.cumsum(v[:-1], axis=0, out=before[1:])
        after = np.zeros_like(v)
        after[:-1] = np.cumsum(v[:0:-1], axis=0)[::-1]
        return (before + after) / (n_seg - per_unit)

    sxy = left_out_mean(ax * np.conj(ay))
    sxx = left_out_mean(np.abs(ax) ** 2)
    syy = left_out_mean(np.abs(ay) ** 2)
    denom = np.sqrt(sxx * syy)
    coh = np.divide(sxy, denom, out=np.zeros_like(sxy), where=denom > 0)
    return np.sum(np.imag(np.conj(coh[:, :-1]) * coh[:, 1:]), axis=1)


#: k of the PSI round-off bound ``k * n * eps * scale`` (see `_psi_round_off`).
_PSI_ROUND_OFF_K = 4.0


def _psi_round_off(n_seg: int, n_pairs: int, n_units: int) -> float:
    """Largest jackknife standard deviation of PSI that rounding alone can produce:
    ``k * n * eps * scale`` with ``k = 4``, ``n = n_seg`` and
    ``scale = n_pairs * sqrt(n_units - 1)``.

    Derivation, with ``u = eps / 2`` and ``m <= n_seg`` the segments a spectrum averages. A
    sum of ``m`` products errs by at most ``m u`` times the sum of their magnitudes, which
    for the cross-spectrum is at most ``sqrt(S_xx S_yy)`` by Cauchy-Schwarz; so a coherency
    ``C = S_xy / sqrt(S_xx S_yy)``, ``|C| <= 1``, errs by at most ``(2m + 4) u`` and a term
    ``Im(conj(C_f) C_{f+1})`` by ``(4m + 11) u``. A replicate sums ``n_pairs`` terms, so it
    errs by at most ``n_pairs (4m + 12) u <= 4 n_seg n_pairs eps`` for ``m >= 3``. Replicates
    that are equal in exact arithmetic (identical segments, as from a periodic signal, or Y
    equal to X) then differ by errors ``e_i`` with ``|e_i| <= b``, and the jackknife standard
    deviation over ``U = n_units`` of them is at most ``sqrt((U - 1) / U * sum(e_i ** 2))
    <= sqrt(U - 1) b``. A spread within that bound has nothing to scale by.
    """
    eps = float(np.finfo(float).eps)
    scale = max(n_pairs, 1) * np.sqrt(max(n_units - 1, 1))
    return _PSI_ROUND_OFF_K * n_seg * eps * float(scale)


def _warn_psi_zero_spread(name: str, sd: float, warnings_all: List[str]) -> None:
    warnings_all.append(f"band_{name}_jackknife_spread_is_round_off_z_undefined")
    warnings.warn(
        f"phase_slope_index: the jackknife replicates of band {name!r} agree to "
        f"rounding (sd {sd:.3g}), so z = psi / sd and its p are undefined and reported as "
        "NaN/None. The segments carry no variation to test against: identical segments, "
        "such as a periodic signal, or Y equal to X.",
        RuntimeWarning,
        stacklevel=3,
    )


def phase_slope_index(
    X,
    Y,
    fs: float,
    bands: Union[str, Dict[str, Tuple[float, float]], Tuple[float, float], None] = None,
    nperseg: Optional[int] = None,
    noverlap: Optional[int] = None,
    window: str = "hann",
    detrend: Optional[str] = "demean",
    jackknife: bool = True,
    n_surrogates: int = 0,
    rng: RNGLike = Default(0),
    time_axis: int = -1,
    *,
    seed: Any = Default(0),
) -> DirectedResult:
    """
    Phase Slope Index (Nolte et al., 2008) — which signal leads in phase.

    PSI is antisymmetric: ``psi(X, Y) == -psi(Y, X)`` exactly. Positive means
    **X leads Y**. Because it uses the *slope* of the coherency phase rather than
    its value, a zero-lag common source (volume conduction, shared reference)
    contributes ~0 rather than a spurious direction.

    There is therefore **one** lead test here, not two. ``p_x_to_y``, ``p_y_to_x`` and
    ``p_net`` are deliberately the same number — the direction lives in the *sign*, and
    the p-value asks only whether the lead is distinguishable from zero. Reading them
    as independent per-direction tests (as GC and TE's are) will report a
    significant lead in both directions at once, which is not what happened.
    ``diagnostics['p_covers_both_directions']`` flags this.

    The lead p is the jackknife t test (``jackknife=True``) and nothing else. A surrogate
    test (``n_surrogates > 0``) is reported separately, as
    ``diagnostics['p_coupling_surrogate']`` and ``per_band[name]['p_surrogate']``: a
    shifted or re-paired Y removes every X-Y dependence, zero lag included, so that p
    tests coupling, not a lead. With ``jackknife=False`` there is no lead test and the
    three p fields are None.

    The jackknife leaves out one trial when there are at least three trials, and one Welch
    segment otherwise, with a ``RuntimeWarning``; ``params['jackknife_unit']`` records which.
    Measured on two noisy copies of one white source (no lead; band 5-100 Hz at fs 1000,
    default ``nperseg``, 2000 seeds), P(lead p < 0.05) was 0.049, 0.059, 0.059 and 0.040 on
    3, 5 and 10 trials of 400 and 30 of 200, where leaving out a segment instead gave 0.059
    to 0.068. On one 2000-sample trial the segment jackknife gave 0.059 to 0.064, 0.063 to
    0.078 and 0.057 to 0.058 at nperseg 50, 100 and 200 (runs of 1000 and 2000 seeds), while
    the surrogate p rejected in 0.15 to 0.17 at nperseg 100. On independent pairs the lead p
    rejected in at most 0.020, and a 5-sample lead under unit noise was detected in 0.91 of
    pairs on 3 trials of 400 and in all of them from 5 trials on.

    Coherency is estimated by averaging cross- and auto-spectra over Welch
    segments pooled across trials — a single-segment coherency has magnitude 1 by
    construction and its PSI is meaningless, so segmenting is not optional.

    PSI needs power spread across a *band*. A near-pure tone returns ~0 however
    large its delay, because at a single frequency a delay and a phase offset are
    indistinguishable and the neighbouring bins hold only window leakage carrying
    that same phase. Measured here: band-limited noise (14-30 Hz) delayed 10 ms
    gives z = 64, while a 20 Hz sinusoid with the identical delay gives z = 3.
    Low ``|z|`` on a narrowband signal is therefore not evidence of no lead.

    Args:
        X, Y: (n_times,), (n_trials, n_times), or list of 1-D trials
        fs: sampling rate in Hz (required — PSI is a frequency-domain measure)
        bands: ``None`` for one estimate over the whole spectrum except DC
            (``df``..``fs/2``); ``'canonical'`` for :data:`CANONICAL_BANDS`; a ``(fmin, fmax)``
            tuple; or a ``{name: (fmin, fmax)}`` dict
        nperseg: Welch segment length in samples. The default is n_times // 4, clipped
            to [16, n_times] and shortened until the trials hold at least 20 segments
            at the default overlap, but not below 16 samples: one trial of 2000 samples
            gets 190 (20 segments), 10 trials of 400 keep 100 (70 segments). Frequency
            resolution is ``fs / nperseg``.
        noverlap: segment overlap (default nperseg // 2)
        window: ``'hann'`` | ``'hamming'`` | ``'boxcar'``
        detrend: per-trial preprocessing, default ``'demean'``
        jackknife: estimate the standard deviation of PSI by leaving out one trial (three
            or more trials) or one segment (fewer) and report ``z = psi / sd``, the
            normalization Nolte et al. use for significance; the lead p is ``z`` against
            Student t with one degree of freedom fewer than the units left out.
        n_surrogates: optional surrogate test of coupling, reported as
            ``diagnostics['p_coupling_surrogate']``; it never sets the lead p. The scheme
            is as in :func:`granger` and is recorded in ``params['surrogate_scheme']``
        rng: surrogate randomness, as in :func:`granger`; passing
            ``params['surrogate_seed_entropy']`` back as ``rng`` reproduces the p-values

    Returns:
        DirectedResult with ``unit='psi'``, ``per_band[name] = {value, z, sd,
        n_freq_bins, band_hz}``, and ``spectrum = {freqs, psi_per_freq, coherence}``.
        ``x_to_y`` is the summed PSI over the whole requested range with
        ``y_to_x = -x_to_y``; ``net == x_to_y``. When no band holds the two frequency bins a
        slope needs, ``x_to_y``, ``y_to_x`` and ``net`` are NaN and
        ``diagnostics['ok_for_interpretation']`` is False. When only some bands hold two
        bins, ``net`` sums those bands alone and the others are left out of it, not counted
        as zero; ``ok_for_interpretation`` is False and ``per_band`` shows which were
        dropped. When the jackknife replicates
        agree to rounding (identical segments, as from a periodic signal, or Y equal to X),
        ``sd`` and ``z`` are NaN, the lead p is None, a ``RuntimeWarning`` says why and
        ``ok_for_interpretation`` is False. A surrogate p counts every draw within
        round-off of the observed value as reaching it, as :func:`granger` does.

    References:
        Nolte, G., et al. (2008). Robustly estimating the flow direction of information in
        complex physical systems. Phys. Rev. Lett. doi:10.1103/PhysRevLett.100.234101
        -- PSI, eq. 3, summed over the coherency of eq. 4 with the cross-spectrum
        ``S_xy = <X Y*>`` of eq. 2; ``z`` is the normalization of eq. 6. The paper's
        jackknife leaves out one epoch, a block of several segments, at a time; this one
        does so from three trials on, a trial being the epoch, and below that leaves out
        one Welch segment, adjacent segments overlapping by ``noverlap``.
    """
    seed = resolve_seed_alias(rng, seed, alias_name='seed', func_name='phase_slope_index')
    surrogate_rng, seed_entropy = _surrogate_rng(seed, "phase_slope_index")
    if fs is None or not np.isfinite(fs) or fs <= 0:
        raise ValueError(f"phase_slope_index requires a positive fs; got {fs!r}")

    x, y = _pair_trials(X, Y, time_axis=time_axis)
    x = _detrend_trials(x, detrend)
    y = _detrend_trials(y, detrend)
    n_trials, n_times = x.shape

    if nperseg is None:
        nperseg = _default_nperseg(n_trials, n_times)
    nperseg = int(min(nperseg, n_times))
    if nperseg < 8:
        raise ValueError(f"nperseg={nperseg} too small for a usable spectrum")
    if noverlap is None:
        noverlap = nperseg // 2
    noverlap = int(min(noverlap, nperseg - 1))

    win_fn = {"hann": np.hanning, "hamming": np.hamming, "boxcar": np.ones}
    if window not in win_fn:
        raise ValueError(f"window must be one of {sorted(win_fn)}; got {window!r}")
    taper = win_fn[window](nperseg)

    seg_x = _welch_segments(x, nperseg, noverlap)
    seg_y = _welch_segments(y, nperseg, noverlap)
    seg_x = (seg_x - seg_x.mean(axis=1, keepdims=True)) * taper
    seg_y = (seg_y - seg_y.mean(axis=1, keepdims=True)) * taper
    fx = np.fft.rfft(seg_x, axis=1)
    fy = np.fft.rfft(seg_y, axis=1)
    freqs = np.fft.rfftfreq(nperseg, d=1.0 / fs)
    n_seg = fx.shape[0]
    df = fs / nperseg

    # resolve band specification
    if bands is None:
        # everything except DC. A hard-coded lower edge in Hz would silently
        # empty the band for slowly sampled series (band-power time courses,
        # normalized-frequency use with fs=2).
        band_map = {"full": (df, fs / 2.0)}
    elif isinstance(bands, str):
        if bands != "canonical":
            raise ValueError(f"bands string must be 'canonical'; got {bands!r}")
        band_map = dict(CANONICAL_BANDS)
    elif isinstance(bands, dict):
        band_map = {k: (float(v[0]), float(v[1])) for k, v in bands.items()}
    else:
        band_map = {"band": (float(bands[0]), float(bands[1]))}

    warnings_all: List[str] = []
    if n_seg < 8:
        warnings_all.append(f"only_{n_seg}_welch_segments_coherency_poorly_estimated")

    # INTENTIONAL BREAK: the jackknife left out one Welch segment whatever the trial
    # count. Overlapping segments of one trial are dependent, and under zero-lag mixing the
    # segment jackknife rejected in 0.068 on 10 trials of 400 at the default nperseg (70
    # segments; 2000 seeds, se 0.006). It leaves out one
    # trial from three trials on (Nolte et al.'s epoch), and one segment below that.
    jackknife_unit = "trial" if n_trials >= _MIN_TRIALS_FOR_TRIAL_JACKKNIFE else "segment"
    n_units = n_trials if jackknife_unit == "trial" else n_seg
    if jackknife and jackknife_unit == "segment":
        warnings.warn(
            f"phase_slope_index: {n_trials} trial(s), so the jackknife leaves out one Welch "
            f"segment, not one trial; overlapping segments of one trial are dependent, and "
            f"this jackknife rejected in about 0.06 at a nominal 0.05 under zero-lag mixing. "
            f"Pass {_MIN_TRIALS_FOR_TRIAL_JACKKNIFE} or more trials to leave out trials.",
            RuntimeWarning,
            stacklevel=2,
        )

    # full-spectrum PSI per frequency (for the returned spectrum)
    sxy = np.mean(fx * np.conj(fy), axis=0)
    sxx = np.mean(np.abs(fx) ** 2, axis=0)
    syy = np.mean(np.abs(fy) ** 2, axis=0)
    denom = np.sqrt(sxx * syy)
    coh_full = np.divide(sxy, denom, out=np.zeros_like(sxy), where=denom > 0)
    psi_per_freq = np.imag(np.conj(coh_full[:-1]) * coh_full[1:])

    # The headline `net` is a raw sum over whatever band table the caller passed, so two
    # bands covering the same bins contribute that band twice: {'a': (14, 30), 'b':
    # (14, 30)} returned exactly 2x the estimate of {'beta': (14, 30)} on the same data.
    _band_bins: Dict[str, np.ndarray] = {
        _n: np.flatnonzero((freqs >= _lo) & (freqs <= _hi))
        for _n, (_lo, _hi) in band_map.items()
    }
    _overlaps = sorted(
        {
            tuple(sorted((_a, _b)))
            for _a in _band_bins
            for _b in _band_bins
            if _a != _b and np.intersect1d(_band_bins[_a], _band_bins[_b]).size
        }
    )
    if _overlaps:
        _pairs = ", ".join(f"{_a}/{_b}" for _a, _b in _overlaps)
        warnings_all.append(f"overlapping_bands_counted_more_than_once:{_pairs}")
        warnings.warn(
            "phase_slope_index: bands overlap on the frequency grid "
            f"({_pairs}); `net` sums the bands, so the shared bins are counted once per "
            "band. Use disjoint bands, or read `per_band` instead of `net`.",
            RuntimeWarning,
            stacklevel=2,
        )

    per_band: Dict[str, Dict[str, Any]] = {}
    jk_per_band: Dict[str, np.ndarray] = {}
    for name, (f_lo, f_hi) in band_map.items():
        idx = np.flatnonzero((freqs >= f_lo) & (freqs <= f_hi))
        if idx.size < 2:
            warnings_all.append(
                f"band_{name}_has_{idx.size}_bins_at_df={df:.3g}Hz_psi_undefined"
            )
            per_band[name] = {
                "value": float("nan"),
                "z": float("nan"),
                "sd": float("nan"),
                "n_freq_bins": int(idx.size),
                "band_hz": (f_lo, f_hi),
                "p_surrogate": None,
            }
            continue

        value = _psi_from_spectra(fx, fy, idx)

        sd = float("nan")
        if jackknife and n_units >= 3:
            jk = _psi_leave_one_out(fx, fy, idx, n_units)
            sd = float(np.sqrt((n_units - 1) / n_units * np.sum((jk - jk.mean()) ** 2)))
            jk_per_band[name] = jk
            if sd <= _psi_round_off(n_seg, idx.size - 1, n_units):
                _warn_psi_zero_spread(name, sd, warnings_all)
                sd = float("nan")
        elif jackknife:
            warnings_all.append(f"jackknife_needs_at_least_3_{jackknife_unit}s")

        per_band[name] = {
            "value": value,
            "z": float(value / sd) if sd and np.isfinite(sd) and sd > 0 else float("nan"),
            "sd": sd,
            "n_freq_bins": int(idx.size),
            "band_hz": (f_lo, f_hi),
            "p_surrogate": None,
        }

    if n_surrogates > 0:
        null = {name: np.empty(int(n_surrogates)) for name in per_band}
        for i in range(int(n_surrogates)):
            y_s = _surrogate_source(y, surrogate_rng)
            seg_ys = _welch_segments(y_s, nperseg, noverlap)
            seg_ys = (seg_ys - seg_ys.mean(axis=1, keepdims=True)) * taper
            fys = np.fft.rfft(seg_ys, axis=1)
            for name, vals in per_band.items():
                f_lo, f_hi = vals["band_hz"]
                idx = np.flatnonzero((freqs >= f_lo) & (freqs <= f_hi))
                null[name][i] = (
                    _psi_from_spectra(fx, fys, idx) if idx.size >= 2 else np.nan
                )
        for name, vals in per_band.items():
            obs = vals["value"]
            nl = null[name]
            nl = nl[np.isfinite(nl)]
            # Each of the band's n_freq_bins - 1 terms is at most 1, and they can cancel.
            vals["p_surrogate"] = (
                _surrogate_p(nl, obs, "two-sided", scale=vals["n_freq_bins"] - 1)
                if nl.size and np.isfinite(obs) else None
            )

    band_values = np.array([v["value"] for v in per_band.values()], dtype=float)
    # np.nansum of an all-NaN array is 0.0, which reads as "no lead" when no band had a slope.
    total = float(np.nansum(band_values)) if np.isfinite(band_values).any() else float("nan")

    # INTENTIONAL BREAK (0.2.7): the top-level p fields hold the jackknife lead test only.
    # They held the surrogate p whenever n_surrogates > 0, but a shifted or re-paired Y
    # removes all X-Y dependence, so that p tests coupling, not a non-zero lead: under
    # zero-lag mixing (a common white source, no lead) it rejected at 0.05 in 0.00-0.46 of
    # cases depending on segment length and band. The surrogate p is now reported as
    # diagnostics['p_coupling_surrogate'].
    p_top = None
    p_coupling = None
    if len(per_band) == 1:
        single = next(iter(per_band.values()))
        p_coupling = single.get("p_surrogate")
        if np.isfinite(single.get("z", np.nan)):
            # Student t, not a standard normal: the delete-one jackknife z is built from
            # `n_units` leave-one-out replicates and carries about `n_units - 1` degrees of
            # freedom. The Gaussian tail reported p = 0.0 from 10 segments, and
            # overstated moderate evidence by an order of magnitude (z = 3.29 gave
            # 0.001 against 0.0094 under t(9)).
            p_top = float(2 * stats.t.sf(abs(single["z"]), df=max(n_units - 1, 1)))
    else:
        if n_surrogates > 0 and null:
            valid = [k for k in null if np.all(np.isfinite(null[k]))]
            if valid and np.isfinite(total):
                null_tot = np.sum([null[k] for k in valid], axis=0)
                n_pairs = sum(int(per_band[k]["n_freq_bins"]) - 1 for k in valid)
                p_coupling = _surrogate_p(null_tot, total, "two-sided", scale=n_pairs)
        if jackknife and n_units >= 3 and jk_per_band:
            jk_tot = np.sum(list(jk_per_band.values()), axis=0)
            sd_tot = float(np.sqrt((n_units - 1) / n_units
                                   * np.sum((jk_tot - jk_tot.mean()) ** 2)))
            n_pairs = sum(int(v["n_freq_bins"]) - 1 for k, v in per_band.items() if k in jk_per_band)
            if sd_tot <= _psi_round_off(n_seg, n_pairs, n_units):
                _warn_psi_zero_spread("total", sd_tot, warnings_all)
            elif np.isfinite(sd_tot) and np.isfinite(total):
                z_tot = float(total / sd_tot)
                p_top = float(2 * stats.t.sf(abs(z_tot), df=max(n_units - 1, 1)))

    return DirectedResult(
        method="psi",
        x_to_y=total,
        y_to_x=-total,
        net=total,
        unit="psi",
        p_x_to_y=p_top,
        p_y_to_x=p_top,
        p_net=p_top,
        per_band=per_band,
        spectrum={
            "freqs": freqs,
            "psi_freqs": (freqs[:-1] + freqs[1:]) / 2.0,
            "psi_per_freq": psi_per_freq,
            "coherence": np.abs(coh_full),
        },
        n_trials=n_trials,
        n_times=n_times,
        fs=float(fs),
        params={
            "nperseg": int(nperseg),
            "noverlap": int(noverlap),
            "window": window,
            "freq_resolution_hz": float(df),
            "n_segments": int(n_seg),
            "bands": {k: list(v) for k, v in band_map.items()},
            "jackknife": bool(jackknife),
            "jackknife_unit": jackknife_unit if jackknife else None,
            "n_surrogates": int(n_surrogates),
            "detrend": detrend,
            "seed": None if isinstance(seed, np.random.Generator) else seed,
            "surrogate_seed_entropy": seed_entropy if n_surrogates > 0 else None,
            "surrogate_scheme": _surrogate_scheme(n_trials) if n_surrogates > 0 else None,
        },
        diagnostics={
            "n_segments": int(n_seg),
            "mean_coherence": float(np.mean(np.abs(coh_full))),
            "p_source": "jackknife_z" if p_top is not None else None,
            # Tests X-Y dependence of any lag, zero lag included; never a lead.
            "p_coupling_surrogate": p_coupling,
            # PSI is antisymmetric: one test, direction carried by the sign.
            "p_covers_both_directions": True,
            "p_is_omnibus": bool(len(per_band) > 1),
            "warnings": warnings_all,
            "ok_for_interpretation": len(warnings_all) == 0,
        },
    )
