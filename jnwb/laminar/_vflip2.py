"""vFLIP2: the published spectrolaminar estimator, ported from its MATLAB release."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional, Tuple

import numpy as np
from scipy import stats

from .._dictlike import DictAccessMixin

#: Layer IVA, IVB and IVC of macaque area 17 in mm (O'Kusky and Colonnier 1982), summed by
#: vFLIP2.m into the shortest channel window it searches. Summed as vFLIP2.m sums them, each
#: divided by 1000 first: the result is 1 ulp above 0.586, which moves ceil(layer4 / spacing)
#: at spacings such as 146.5 um.
LAYER4_THICKNESS_MM = 127.1 / 1000 + 211.4 / 1000 + 247.5 / 1000

#: vFLIP2.m's `omega_cut`: a best window with omega at or below it returns no result.
OMEGA_CUT = 6.0

_ORIENTATIONS = {"both": 0, "upright": 1, "inverted": -1}


@dataclass(frozen=True)
class VFlip2Result(DictAccessMixin):
    """The best channel window vFLIP2 found, and whether its omega clears the cut.

    Channel indices are 0-based rows of the PSD; vFLIP2.m reports the same rows 1-based.
    Every field except `accepted` and `omega_cut` is None when no window passed vFLIP2's
    peak, crossover and arrangement checks.

    Attributes:
        accepted: True when `omega` exceeds `omega_cut`. vFLIP2.m returns NaN otherwise;
            this result keeps the best window's values so a rejection can be read.
        omega: Natural log of G * S_d * B_d * channel span * band widths for the best window.
        goodness: G, the product of the two band profiles' R-squared under a second-degree
            fit, zero unless both fits have p < 0.05, signed positive when the low band rises
            and the high band falls with channel index.
        orientation: ``"upright"`` when the distal half of the window is the deep group
            (alpha/beta power higher there), ``"inverted"`` when the proximal half is.
        low_band_hz, high_band_hz: First and last frequency of each searched band.
        proximal_channel, distal_channel: The window's first and last row.
        low_peak_channel, high_peak_channel: Rows of the low-band and high-band maxima.
        crossover_channel: Row where the band profiles cross.
        omega_cut: The cut `accepted` was decided against.
        motif_quality: vFLIP2's reading of omega (vFLIP2_Description.pdf, section 8):
            ``"absent"`` at or below 6, ``"medium"`` above 6 up to 12, ``"strong"`` above 12,
            or None when no window passed. These tiers are fixed; `omega_cut` does not
            move them.
    """

    accepted: bool
    omega: Optional[float]
    goodness: Optional[float]
    orientation: Optional[str]
    low_band_hz: Optional[Tuple[float, float]]
    high_band_hz: Optional[Tuple[float, float]]
    proximal_channel: Optional[int]
    distal_channel: Optional[int]
    low_peak_channel: Optional[int]
    high_peak_channel: Optional[int]
    crossover_channel: Optional[int]
    omega_cut: float
    motif_quality: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


def _matlab_round(x: float) -> int:
    """MATLAB's round: halves go away from zero."""
    return int(math.floor(abs(x) + 0.5)) * (1 if x >= 0 else -1)


def _movmean5(x: np.ndarray) -> np.ndarray:
    """`smoothdata(x, 'movmean', 5)`: centred window of 5, shrunk at the ends, NaN omitted."""
    out = np.full(x.shape, np.nan)
    n = x.size
    for i in range(n):
        window = x[max(0, i - 2):min(n, i + 3)]
        window = window[~np.isnan(window)]
        if window.size:
            out[i] = window.mean()
    return out


def _first_max(x: np.ndarray) -> Optional[int]:
    """`find(x == max(x), 1)` with MATLAB's max, which skips NaN; None when all are NaN."""
    if np.all(np.isnan(x)):
        return None
    return int(np.nanargmax(x))


def _longest_true_run(mask: np.ndarray) -> np.ndarray:
    """Indices of the first longest run of True, as vFLIP2.m's find_longest_true_run."""
    edges = np.diff(np.concatenate(([0], mask.astype(int), [0])))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1) - 1
    if starts.size == 0:
        return np.array([], dtype=int)
    k = int(np.argmax(ends - starts + 1))
    return np.arange(starts[k], ends[k] + 1)


def _freqbands(freqs: np.ndarray, s1: np.ndarray, s2: np.ndarray):
    """vFLIP2.m's get_freqbands: (deep band, superficial band, orientation)."""
    low = (freqs > 4) & (freqs < 70)
    high = (freqs > 40) & (freqs < 150)
    run1 = _longest_true_run((s1 > s2) & low)
    run2 = _longest_true_run((s1 < s2) & low)
    deep, sup, orientation = np.array([]), np.array([]), 0
    if run1.size >= 5 and run2.size >= 5:
        if freqs[run1].min() < freqs[run2].min():
            deep, orientation, ind_high = freqs[run1], -1, (s1 < s2) & high
        else:
            deep, orientation, ind_high = freqs[run2], 1, (s1 > s2) & high
    elif run1.size >= 5:
        deep, orientation, ind_high = freqs[run1], -1, (s1 < s2) & high
    elif run2.size >= 5:
        deep, orientation, ind_high = freqs[run2], 1, (s1 > s2) & high
    if orientation != 0:
        sup = freqs[_longest_true_run(ind_high)]
        if sup.size < 20 or sup[-1] < 70:
            sup = np.array([])
    return deep, sup, orientation


def _band_regress(band: np.ndarray) -> Tuple[float, float, float]:
    """(slope at the midpoint, R-squared, p) of `regress(band, [x.^2, x, 1])`, x = 1..n."""
    n_all = band.size
    x = np.arange(1, n_all + 1, dtype=float)
    design = np.column_stack((x ** 2, x, np.ones(n_all)))
    keep = ~np.isnan(band)
    y, design = band[keep], design[keep]
    n = y.size
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    rank = int(np.linalg.matrix_rank(design))
    yhat = design @ coef
    sse = float(np.sum((y - yhat) ** 2))
    rss = float(np.sum((yhat - y.mean()) ** 2))
    tss = float(np.sum((y - y.mean()) ** 2))
    with np.errstate(divide="ignore", invalid="ignore"):
        r2 = 1.0 - sse / tss if tss else (np.nan if sse == 0 else -np.inf)
        nu = max(0, n - rank)
        s2 = sse / nu if nu else np.nan
        f = (rss / (rank - 1)) / s2 if rank > 1 else np.nan
    p = float(stats.f.sf(f, rank - 1, nu)) if np.isfinite(f) and nu > 0 else np.nan
    midpoint = _matlab_round(n_all / 2)
    slope = 2 * coef[0] * midpoint + coef[1]
    return float(slope), float(r2), p


def _goodness(lowband: np.ndarray, highband: np.ndarray) -> float:
    """vFLIP2.m's evaluate_individual_goodness."""
    low_slope, low_r2, low_p = _band_regress(lowband)
    high_slope, high_r2, high_p = _band_regress(highband)
    significant = bool(low_p < 0.05 and high_p < 0.05)
    if low_slope > 0 and high_slope < 0:
        sign = 1
    elif low_slope < 0 and high_slope > 0:
        sign = -1
    else:
        sign = 0
    return high_r2 * low_r2 * significant * sign


def _peak_check(band, proximal, distal, startrow, endrow, half) -> bool:
    """vFLIP2.m's peak_check; rows are 1-based as there."""
    n = band.size
    top = np.nanmax(band)
    locations = np.flatnonzero(band == top) + 1
    peak = int(locations.max()) if locations.mean() > n / 2 else int(locations.min())
    if peak == 1:
        ok = proximal == startrow and band[0] > band[1]
    elif peak == n:
        ok = distal == endrow and band[n - 1] > band[n - 2]
    else:
        ok = band[peak - 1] > band[peak] and band[peak - 1] > band[peak - 2]
    idx = int(np.nanargmax(band)) + 1
    return bool(ok and (idx <= half or idx >= n - (half - 1)))


def _crossover(lowband, highband, proximal, orientation) -> float:
    """vFLIP2.m's crossover_channels; returns a 1-based row or NaN."""
    diff = np.abs(highband - lowband)
    n = lowband.size

    def cross(i, b1, b2):  # i is 1-based
        if b1[i - 1] > b2[i - 1] and b2[i] > b1[i]:
            return i if abs(diff[i - 1]) <= abs(diff[i]) else i + 1
        if b1[i - 1] > b2[i - 1] and b1[i] == b2[i] and b2[i + 1] > b1[i + 1]:
            return i + 1
        return None

    found = []
    for i in range(1, n - 1):
        c = cross(i, highband, lowband) if orientation > 0 else cross(i, lowband, highband)
        if c is not None:
            found.append(c)
    if not found:
        return np.nan
    if len(found) == 1:
        return found[0] + proximal - 1
    ratings = [diff[:c].sum() - diff[c - 1:].sum() for c in found]
    return found[int(np.argmax(ratings))] + proximal - 1


def vflip2(
    psd: np.ndarray,
    freqs: np.ndarray,
    *,
    contact_spacing: float,
    orientation: str = "both",
    layer4_thickness_mm: Optional[float] = None,
    omega_cut: float = OMEGA_CUT,
) -> VFlip2Result:
    """vFLIP2, the spectrolaminar estimator of Major et al. (2025), ported from vFLIP2.m.

    Searches every channel window at least one layer 4 thick for the one whose relative
    power best shows the spectrolaminar motif, scores it by omega and accepts it when omega
    exceeds `omega_cut`. Each step is vFLIP2.m's (Dryad doi:10.5061/dryad.9w0vt4bnp,
    version of 2025-11-04, CC0), in the order the MATLAB runs it:

    1. Windows: proximal row from the first non-NaN row in steps of round(0.1 mm /
       spacing), distal row at least ceil(layer 4 / spacing) rows further.
    2. Relative power: each frequency divided by its maximum across the window's rows.
    3. Groups: the first and last floor(span / 2) rows; their mean spectra S1 and S2 are
       smoothed by a centred 5-bin moving mean.
    4. Bands: the longest run of S1 > S2 or S1 < S2 between 4 and 70 Hz (at least 5 bins)
       is the low band, its group the deep one; the longest run of the opposite sign
       between 40 and 150 Hz is the high band, kept when it has at least 20 bins and ends
       at or above 70 Hz.
    5. Omega: ln(G * S_d * B_d * span * 0.1 mm-units * n_low * n_high * bin^2), with
       S_d = |S1 - S2|, B_d = |L - H| over rows, G as `VFlip2Result.goodness`.
    6. Checks: a peak in each band profile on its half of the window, peaks at least one
       layer 4 apart, a crossover between them, and no two of the three on one row.

    Sensitivity at these defaults, measured on the Dryad power example (omega 13.28): omega
    moves by +0.37 with 0.5 Hz bins and -0.32 with 2 Hz bins, by -0.42 when the PSD ends at
    150 Hz, by +0.29 at 50 um and -0.31 at 200 um spacing, and by -2.42 with
    orientation="inverted"; the layer-4 thickness leaves it unchanged. On 50 seeded
    synthetic probes acceptance flips in 12 with 2 Hz bins, in 22 at 200 um spacing and in
    11 at omega_cut=8. With the bands on the same columns, scaling the bin width by r moves
    omega by exactly 2 ln(r).

    Known differences from the vFLIP2 description (vFLIP2_Description.pdf). The port
    reproduces each as published and does not fix it:

    - The high band is rejected when its upper end is below 70 Hz (vFLIP2.m line 264). The
      description requires its lower end to be at least 70 Hz.
    - The crossover rating is a signed left-minus-right sum that counts row c on both sides
      (line 327).
    - Omega, and the 5-bin, 20-bin and moving-mean-5 limits, count frequency bins, so they
      change with the bin width and range (lines 238, 264, 454, 475-476).
    - vFLIP2.m takes column k to be k times the bin width (line 130). This port uses
      `freqs` as given, so the two agree only when `freqs` is that grid; for a PSD whose
      first column is 0 Hz, vFLIP2.m shifts every band by one bin and this port does not.
    - Peak ties go to the last peak when their mean index is past the middle, else to the
      first (lines 271-288). The reported peak channels take the first (lines 479-480).

    Args:
        psd: (n_channels, n_freqs) power, rows ordered along the shaft. Rows that are NaN at
            the first frequency are excluded when they lead or trail, as in vFLIP2.m.
        freqs: (n_freqs,) frequencies in Hz, uniformly spaced, used as given. vFLIP2.m takes
            column k to be k * freqbinsize Hz; pass that grid to reproduce its output.
        contact_spacing: Inter-contact distance in micrometers (vFLIP2.m's `intdist` in mm).
        orientation: ``"both"`` (default), ``"upright"`` or ``"inverted"``; the last two
            zero the goodness of windows with the other sign, as vFLIP2.m does.
        layer4_thickness_mm: Shortest window, in mm; default `LAYER4_THICKNESS_MM`.
        omega_cut: The cut on omega, finite; vFLIP2.m fixes it at 6.

    Returns:
        :class:`VFlip2Result`.

    Raises:
        ValueError: `psd` not 2-D, `freqs` not matching or not uniform, a spacing or
            thickness that is not finite and positive, an unknown orientation, a NaN row
            inside the non-NaN rows, a non-NaN row with a non-finite or negative value, a
            non-finite `omega_cut`, or a window whose low or high band falls only on
            frequencies where every row in the window has zero power.

    References:
        Major, A. J., et al. (2025). A. J. Major et al. reply. Nature Neuroscience 29(2),
        284-286. doi:10.1038/s41593-025-02168-x -- vFLIP2 and omega.
        Mendoza-Halliday, D., et al. Code: vFLIP2.m, Dryad doi:10.5061/dryad.9w0vt4bnp,
        version 8 (2025-11-04, CC0).
        This port matches vFLIP2.m's output on the same input (tests/test_vflip2.py).
    """
    psd = np.asarray(psd, dtype=float)
    freqs = np.asarray(freqs, dtype=float)
    if psd.ndim != 2:
        raise ValueError(f"psd must be 2-D (n_channels, n_freqs), got shape {psd.shape}")
    if freqs.ndim != 1 or freqs.size != psd.shape[1] or freqs.size < 2:
        raise ValueError(f"freqs must be 1-D with {psd.shape[1]} entries, got shape {freqs.shape}")
    binsize = float(freqs[1] - freqs[0])
    if not (binsize > 0 and np.allclose(np.diff(freqs), binsize, rtol=1e-9, atol=0)):
        raise ValueError("freqs must be uniformly spaced and increasing")
    if not (np.isfinite(contact_spacing) and contact_spacing > 0):
        raise ValueError(f"contact_spacing must be finite and positive, got {contact_spacing}")
    layer4 = LAYER4_THICKNESS_MM if layer4_thickness_mm is None else float(layer4_thickness_mm)
    if not (np.isfinite(layer4) and layer4 > 0):
        raise ValueError(f"layer4_thickness_mm must be finite and positive, got {layer4}")
    if not np.isfinite(omega_cut):
        raise ValueError(f"omega_cut must be finite, got {omega_cut}")
    if orientation not in _ORIENTATIONS:
        raise ValueError(f"orientation must be one of {sorted(_ORIENTATIONS)}, got {orientation!r}")
    present = np.flatnonzero(~np.isnan(psd[:, 0]))
    if present.size == 0:
        raise ValueError("psd has no row that is not NaN at the first frequency")
    startrow, endrow = int(present[0]) + 1, int(present[-1]) + 1
    if present.size != endrow - startrow + 1:
        raise ValueError("psd has a NaN row between its first and last non-NaN rows")
    body = psd[startrow - 1:endrow]
    if not np.all(np.isfinite(body)) or np.any(body < 0):
        raise ValueError("psd rows must be finite and non-negative")

    intdist = contact_spacing / 1000.0
    step = _matlab_round(0.1 / intdist)
    minrange = int(math.ceil(layer4 / intdist))
    want = _ORIENTATIONS[orientation]

    best_omega, best = -np.inf, None
    proximals = range(startrow, endrow - minrange + 2, step) if step > 0 else range(0)
    for proximal in proximals:
        for distal in range(proximal + minrange, endrow + 1, step):
            window = psd[proximal - 1:distal]
            with np.errstate(divide="ignore", invalid="ignore"):
                rel = window / window.max(axis=0)
            half = (distal - proximal) // 2
            if half == 0:
                s1 = s2 = np.full(freqs.size, np.nan)
            else:
                s1 = _movmean5(rel[:half].mean(axis=0))
                s2 = _movmean5(rel[-half:].mean(axis=0))
            ps_dist = float(np.sqrt(np.sum((s1 - s2) ** 2)))
            deep, sup, orient = _freqbands(freqs, s1, s2)
            if deep.size == 0 or sup.size == 0:
                continue
            lowband = rel[:, np.isin(freqs, deep)].mean(axis=1)
            highband = rel[:, np.isin(freqs, sup)].mean(axis=1)
            band_dist = float(np.sqrt(np.sum((lowband - highband) ** 2)))
            goodness = _goodness(lowband, highband)
            if (want == -1 and goodness > 0) or (want == 1 and goodness < 0):
                goodness = 0.0
            ch_span = abs(proximal - distal) * (intdist / 0.1)
            f_span = deep.size * sup.size * binsize ** 2
            with np.errstate(divide="ignore", invalid="ignore"):
                omega = float(np.log(ps_dist * band_dist * abs(goodness) * ch_span * f_span))
            high_first, low_first = _first_max(highband), _first_max(lowband)
            if high_first is None or low_first is None:
                raise ValueError("a window's band profile is all NaN")
            high_peak = high_first + proximal
            low_peak = low_first + proximal
            cross = _crossover(lowband, highband, proximal, orient)
            good_fit = (
                omega != 0
                and _peak_check(lowband, proximal, distal, startrow, endrow, half)
                and _peak_check(highband, proximal, distal, startrow, endrow, half)
                and not np.isnan(cross)
                and ((low_peak < cross < high_peak) or (low_peak > cross > high_peak))
                and low_peak != cross and cross != high_peak and low_peak != high_peak
                and abs(high_peak - low_peak) >= minrange
            )
            if good_fit and omega > best_omega:
                best_omega = omega
                best = (goodness, deep[0], deep[-1], sup[0], sup[-1], proximal, distal,
                        low_peak, high_peak, int(cross), omega, orient)

    if best is None:
        return VFlip2Result(False, None, None, None, None, None, None, None, None, None, None,
                            float(omega_cut), None)
    goodness, lo0, lo1, hi0, hi1, proximal, distal, low_peak, high_peak, cross, omega, orient = best
    quality = "absent" if omega <= 6 else ("medium" if omega <= 12 else "strong")
    return VFlip2Result(
        accepted=bool(omega > omega_cut),
        omega=float(omega),
        goodness=float(goodness),
        orientation="upright" if orient == 1 else "inverted",
        low_band_hz=(float(lo0), float(lo1)),
        high_band_hz=(float(hi0), float(hi1)),
        proximal_channel=proximal - 1,
        distal_channel=distal - 1,
        low_peak_channel=low_peak - 1,
        high_peak_channel=high_peak - 1,
        crossover_channel=cross - 1,
        omega_cut=float(omega_cut),
        motif_quality=quality,
    )


#: vFLIP2.m's `foi`, the frequencies its PSD is computed at before they are moved to the
#: padded FFT grid (line 531).
_FOI_HZ = np.arange(1, 151, dtype=float)

#: Bytes of complex FFT output held at once while the trial periodograms are computed.
_FFT_CHUNK_BYTES = 1 << 28


def _matlab_round_array(x: np.ndarray) -> np.ndarray:
    """MATLAB's round on non-negative values: halves go up, unlike numpy's half-to-even."""
    whole = np.trunc(x)
    return whole + (x - whole >= 0.5)


def _matlab_hanning(n: int) -> np.ndarray:
    """MATLAB's `hanning(n)`: the symmetric Hann window without its zero end points."""
    half = n // 2 if n % 2 == 0 else (n + 1) // 2
    w = 0.5 * (1.0 - np.cos(2.0 * np.pi * np.arange(1, half + 1) / (n + 1)))
    return np.concatenate((w, w[::-1] if n % 2 == 0 else w[-2::-1]))


def _psd_hanning(trials, fs: float) -> np.ndarray:
    """vFLIP2.m's compute_psd_hanning (lines 530-610): (n_channels, n_freqs) mean power.

    `trials` is an (n_channels, n_samples, n_trials) array or a list of (n_channels,
    n_samples_k) arrays, as vFLIP2.m's numeric and cell `raw_cut` inputs.
    """
    if isinstance(trials, np.ndarray):
        lengths = [trials.shape[1]] * trials.shape[2]
        groups = [np.moveaxis(trials, 2, 0)]
    else:
        lengths = [t.shape[1] for t in trials]
        groups = [t[None] for t in trials]
    padding = 1 << (max(lengths) - 1).bit_length()  # 2^nextpow2 (line 544)
    pad = padding / fs
    endnsample = int(_matlab_round_array(np.array(pad * fs)))
    fboi = _matlab_round_array(_FOI_HZ * pad) + 1
    foi = (fboi - 1) / pad
    freqboi = np.unique(_matlab_round_array(foi / (fs / endnsample)) + 1).astype(int)
    if freqboi[-1] > endnsample:
        raise ValueError(
            f"fs={fs} puts 150 Hz past the padded FFT length {endnsample}; vFLIP2.m indexes "
            "out of range there")
    columns = freqboi - 1
    power = []
    for group in groups:
        n = group.shape[2]
        tap = _matlab_hanning(n)
        tap = tap / np.linalg.norm(tap)
        chunk = max(1, _FFT_CHUNK_BYTES // (16 * group.shape[1] * endnsample))
        for start in range(0, group.shape[0], chunk):
            dat = np.asarray(group[start:start + chunk], dtype=float)
            dat = dat - dat.sum(axis=2, keepdims=True) * (1.0 / n)  # dat*x'*pinv(x*x')
            spectrum = np.fft.fft(dat * tap, n=endnsample, axis=2)[:, :, columns]
            power.append(np.abs(spectrum * np.sqrt(2.0 / endnsample)) ** 2)
    return np.concatenate(power, axis=0).mean(axis=0)


def vflip2_from_lfp(
    lfp,
    fs: float,
    *,
    contact_spacing: float,
    orientation: str = "both",
    layer4_thickness_mm: Optional[float] = None,
    omega_cut: float = OMEGA_CUT,
) -> VFlip2Result:
    """vFLIP2 on LFP: vFLIP2.m's Hanning-window PSD, then :func:`vflip2` on it.

    Ports vFLIP2.m's `raw` and `raw_cut` DataTypes (lines 104-118). The PSD is
    compute_psd_hanning (lines 530-610), step by step:

    1. Continuous `lfp` is cut into consecutive 1 s trials, the remainder dropped
       (split_into_trials, lines 612-619).
    2. FFT length: the next power of two at or above the longest trial (lines 544-546).
    3. Frequencies: 1 to 150 Hz, each moved to the nearest bin of the padded FFT, duplicates
       dropped (lines 531, 548-552).
    4. Each trial and channel: mean removed, a Hanning window (MATLAB's `hanning`, no zero
       end points) divided by its norm, zero padding, FFT, scaled by sqrt(2 / FFT length)
       and squared (lines 583-604). vFLIP2.m also rotates the phase by one sample (lines
       570-580, 598-600); power does not change, so the port skips it.
    5. Power averaged over trials (line 609).

    vFLIP2.m then sets the bin width to 1 Hz (line 118) and labels PSD column k as k Hz
    (line 130). Column k holds the FFT bin nearest k Hz (step 3), within half a bin: with
    1 s trials at 1000 Hz the FFT has 1024 points and every column lies within 0.49 Hz of
    its label. This port passes the same labels to :func:`vflip2`, so its bands are those
    labels.

    Args:
        lfp: (n_channels, n_samples) continuous voltage, vFLIP2.m's `raw`; or
            (n_channels, n_samples, n_trials), or a list of (n_channels, n_samples_k)
            trials, its `raw_cut`.
        fs: Sampling rate in Hz, finite and positive. A non-integer rate is accepted for
            trial-cut input. Continuous input needs an integer rate: vFLIP2.m reshapes it
            into trials of `fs` samples (line 618).
        contact_spacing, orientation, layer4_thickness_mm, omega_cut: As :func:`vflip2`.

    Returns:
        :class:`VFlip2Result`, as :func:`vflip2` on the PSD.

    Raises:
        ValueError: `fs` not finite and positive, or not an integer for continuous input;
            `lfp` not 2-D, 3-D or a non-empty list of 2-D trials with one channel count;
            continuous `lfp` shorter than one trial; an `fs` low enough that 150 Hz falls
            past the FFT length; and every error :func:`vflip2` raises.

    References:
        Mendoza-Halliday, D., et al. Code: vFLIP2.m, Dryad doi:10.5061/dryad.9w0vt4bnp,
        version 8 (2025-11-04, CC0).
        This port matches vFLIP2.m's PSD and output on the same input
        (tests/test_vflip2_from_lfp.py).
    """
    if isinstance(fs, bool) or not isinstance(fs, (int, float, np.integer, np.floating)):
        raise ValueError(f"fs must be a real number, got {fs!r}")
    fs = float(fs)
    if not (np.isfinite(fs) and fs > 0):
        raise ValueError(f"fs must be finite and positive, got {fs}")
    if isinstance(lfp, (list, tuple)):
        trials = [np.asarray(t, dtype=float) for t in lfp]
        if not trials or any(t.ndim != 2 for t in trials):
            raise ValueError("a list lfp must hold one or more (n_channels, n_samples) trials")
        if len({t.shape[0] for t in trials}) != 1 or min(t.shape[1] for t in trials) < 1:
            raise ValueError("every trial must have the same channel count and a sample")
    else:
        lfp = np.asarray(lfp, dtype=float)
        if lfp.ndim == 3:
            if min(lfp.shape) < 1:
                raise ValueError(f"lfp has an empty axis, shape {lfp.shape}")
            trials = lfp
        elif lfp.ndim == 2:
            if not fs.is_integer():
                raise ValueError(
                    f"continuous lfp needs an integer fs, got {fs}: vFLIP2.m cuts it into "
                    "trials of fs samples")
            per_trial = int(fs)
            n_trials = lfp.shape[1] // per_trial
            if lfp.shape[0] < 1 or n_trials < 1:
                raise ValueError(
                    f"continuous lfp needs at least one {per_trial}-sample trial, got shape "
                    f"{lfp.shape}")
            trials = lfp[:, :n_trials * per_trial].reshape(lfp.shape[0], n_trials, per_trial)
            trials = trials.transpose(0, 2, 1)
        else:
            raise ValueError(
                "lfp must be (n_channels, n_samples) or (n_channels, n_samples, n_trials), "
                f"got shape {lfp.shape}")
    psd = _psd_hanning(trials, fs)
    freqs = np.arange(1, psd.shape[1] + 1, dtype=float)
    return vflip2(psd, freqs, contact_spacing=contact_spacing, orientation=orientation,
                  layer4_thickness_mm=layer4_thickness_mm, omega_cut=omega_cut)
