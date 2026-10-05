"""
jnwb.laminar_curation -- curation of a laminar LFP recording and layer labels from it.

Composable parts and one orchestrator:

- :func:`detect_bad_channels`: contacts whose broadband signal decorrelates from their
  neighbors or whose power is an outlier along the shaft.
- :func:`interpolate_channel_runs`: linear interpolation across short runs of bad contacts.
- :func:`evoked_csd_sink`: the evoked current-source-density sink along the shaft.
- :func:`fuse_laminar_anchors`: one anchor and a grade from the vFLIP, spectral-motif,
  xFLIP and CSD estimates and from their stability across trial windows.
- :func:`curate_and_label`: the parts in order, returning a :class:`LaminarCurationResult`
  with a label for every contact: ``"superficial"``, ``"input"``, ``"deep"``, ``"WM"``
  (white matter), ``"outside_cortex"`` or ``"na"``.

Every width is in micrometers (um) and needs the contact pitch. The numeric defaults are
working values from 25 and 40 um laminar probes in macaque cortex, not values from the
literature; each is a parameter. Positions are measured from the first contact of the
channel order supplied, the frame of ``VFlipResult.crossover_depth_um``.

References:
    Mendoza-Halliday, D., et al. (2024). A ubiquitous spectrolaminar motif of local field
    potential power across the primate cortex. Nature Neuroscience.
    doi:10.1038/s41593-023-01554-7 -- the 10-19 Hz and 75-150 Hz bands of the spectral
    motif.
    Mitzdorf, U. (1985). Current source-density method and application in cat cerebral
    cortex: investigation of evoked potentials and EEG phenomena. Physiological Reviews
    65(1), 37-100. doi:10.1152/physrev.1985.65.1.37 -- the CSD as the negative second
    spatial derivative of the potential, a sink being a negative CSD.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import signal
from scipy.ndimage import gaussian_filter1d

from ._dictlike import DictAccessMixin
from ._rng import DEFAULT_SEED, RNGLike, resolve_rng
from .laminar import VFlipResult, vflip, xflip

LABELS: Tuple[str, ...] = ("superficial", "input", "deep", "WM", "outside_cortex", "na")

#: Bands of the spectral motif (alpha-beta deep, gamma superficial), Hz; Mendoza-Halliday 2024.
MOTIF_BAND_LOW_HZ: Tuple[float, float] = (10.0, 19.0)
MOTIF_BAND_HIGH_HZ: Tuple[float, float] = (75.0, 150.0)

def _robust_z(values: np.ndarray) -> np.ndarray:
    """Median/MAD z-score; the standard deviation stands in for a zero MAD."""
    values = np.asarray(values, dtype=float)
    med = np.nanmedian(values)
    mad = np.nanmedian(np.abs(values - med)) * 1.4826
    scale = mad if mad > 0 else (np.nanstd(values) or 1.0)
    return (values - med) / scale


def _runs(mask: np.ndarray) -> List[Tuple[int, int]]:
    """Half-open ``(start, stop)`` index runs where ``mask`` is True."""
    d = np.diff(np.r_[0, np.asarray(mask, dtype=int), 0])
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist()))


def _check_pitch(pitch_um: float) -> float:
    pitch = float(pitch_um)
    if not np.isfinite(pitch) or pitch <= 0:
        raise ValueError(f"pitch_um must be positive and finite, got {pitch_um!r}")
    return pitch


def _check_channels_first(data: np.ndarray, name: str, ndim: Tuple[int, ...]) -> np.ndarray:
    arr = np.asarray(data, dtype=float)
    if arr.ndim not in ndim:
        raise ValueError(f"{name} must have {' or '.join(map(str, ndim))} dimensions "
                         f"(channels first), got {arr.ndim}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} holds non-finite values; mark the contact bad or drop it first")
    return arr


def _local_neighbor_correlation(corr: np.ndarray, bad: np.ndarray, window: int) -> np.ndarray:
    """Median correlation of each contact with the good contacts within ``window`` of it."""
    n = len(corr)
    out = np.full(n, np.nan)
    for i in range(n):
        lo, hi = max(0, i - window), min(n, i + window + 1)
        if hi - lo < 2 * window + 1:  # near an end: take the nearest 2*window+1 contacts
            lo, hi = (0, min(n, 2 * window + 1)) if lo == 0 else (max(0, n - 2 * window - 1), n)
        picks = [m for m in range(lo, hi) if m != i and not bad[m]]
        out[i] = np.median(corr[i, picks]) if picks else np.nan
    return out


def detect_bad_channels(
    data: np.ndarray,
    fs: float,
    *,
    neighbor_contacts: int = 2,
    min_neighbor_corr_z: float = -4.0,
    max_power_z: float = 5.0,
    power_band_hz: Tuple[float, float] = (1.0, 150.0),
    correlation_fs_hz: float = 100.0,
    max_iterations: int = 4,
) -> Dict[str, Any]:
    """Flag contacts that decorrelate from their neighbors or have outlying power.

    A contact is bad when its robust z-score (median/MAD) of the median correlation with
    its good neighbors is below ``min_neighbor_corr_z``, when the robust z-score of its
    log10 mean power in ``power_band_hz`` exceeds ``max_power_z`` in magnitude, or when its
    neighbor correlation is undefined. The neighbor set excludes contacts already flagged,
    and the flag set is iterated until it stops changing or ``max_iterations`` is reached.

    Correlation is computed on the signal decimated to about ``correlation_fs_hz``
    (epochs concatenated); power is the mean Welch PSD over epochs, averaged on the
    linear scale before the logarithm.

    Args:
        data: ``(n_channels, n_samples)`` or ``(n_channels, n_epochs, n_samples)`` LFP,
            channels in shaft order. Every value finite.
        fs: Sampling rate in Hz.
        neighbor_contacts: Contacts on each side that form the neighborhood (a count of
            adjacent contacts, not a distance).
        min_neighbor_corr_z: Robust z below which the neighbor correlation flags a contact.
        max_power_z: Robust z above which the absolute log power flags a contact.
        power_band_hz: ``(low, high)`` band of the power criterion, Hz; ``high`` must be
            below ``fs / 2``.
        correlation_fs_hz: Target rate for the correlation, Hz; the integer decimation
            factor is ``round(fs / correlation_fs_hz)``, at least 1.
        max_iterations: Most refinement passes.

    Returns:
        Dict with ``bad_mask`` (``(n_channels,)`` bool), ``neighbor_correlation`` (the last
        pass, ``(n_channels,)``) and ``log_power`` (``(n_channels,)``, log10 of the mean
        PSD in the band, in the units of ``data`` squared per Hz).

    Raises:
        ValueError: On a non-finite input, an invalid band or fewer than 3 contacts.
    """
    arr = _check_channels_first(data, "data", (2, 3))
    fs = float(fs)
    if not np.isfinite(fs) or fs <= 0:
        raise ValueError(f"fs must be positive and finite, got {fs!r}")
    lo_hz, hi_hz = float(power_band_hz[0]), float(power_band_hz[1])
    if not (0 <= lo_hz < hi_hz < fs / 2):
        raise ValueError(f"power_band_hz must satisfy 0 <= low < high < fs/2, got {power_band_hz!r}")
    if neighbor_contacts < 1 or max_iterations < 1:
        raise ValueError("neighbor_contacts and max_iterations must be at least 1")
    n = arr.shape[0]
    if n < 3:
        raise ValueError(f"need at least 3 contacts, got {n}")
    epochs = arr if arr.ndim == 3 else arr[:, None, :]
    freqs, psd = signal.welch(epochs, fs=fs, nperseg=min(512, epochs.shape[-1]), axis=-1)
    psd = psd.mean(axis=1)
    sel = (freqs >= lo_hz) & (freqs <= hi_hz)
    if not sel.any():
        raise ValueError("no PSD bin falls in power_band_hz; lengthen the epochs or widen the band")
    log_power = np.log10(psd[:, sel].mean(axis=1))
    q = max(1, int(round(fs / float(correlation_fs_hz))))
    reduced = signal.decimate(epochs, q, axis=-1) if q > 1 else epochs
    corr = np.corrcoef(reduced.reshape(n, -1))
    bad = np.zeros(n, dtype=bool)
    local = np.full(n, np.nan)
    for _ in range(int(max_iterations)):
        local = _local_neighbor_correlation(corr, bad, int(neighbor_contacts))
        new = (_robust_z(local) < min_neighbor_corr_z) | (np.abs(_robust_z(log_power)) > max_power_z) \
            | ~np.isfinite(local)
        if np.array_equal(new, bad):
            break
        bad = new
    return {"bad_mask": bad, "neighbor_correlation": local, "log_power": log_power}


def interpolate_channel_runs(
    data: np.ndarray,
    bad_mask: np.ndarray,
    *,
    max_run: int = 3,
    blocked_mask: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Linearly interpolate runs of at most ``max_run`` adjacent bad contacts.

    A run is interpolated between the contacts just outside it, which must exist, must not
    be bad and must not be in ``blocked_mask``. Any other bad run is left unchanged and
    reported in ``unresolved_mask``.

    Args:
        data: ``(n_channels, ...)`` array, channels first; any trailing shape.
        bad_mask: ``(n_channels,)`` bool, True for a bad contact.
        max_run: Longest run, in adjacent contacts, that is interpolated.
        blocked_mask: Optional ``(n_channels,)`` bool of contacts that may not serve as an
            interpolation end point (for example a zone judged unusable).

    Returns:
        Dict with ``data`` (a copy, float), ``interpolated_mask`` and ``unresolved_mask``
        (each ``(n_channels,)`` bool).

    Raises:
        ValueError: If ``bad_mask`` or ``blocked_mask`` does not match ``data.shape[0]``.
    """
    arr = np.array(data, dtype=float, copy=True)
    n = arr.shape[0]
    bad = np.asarray(bad_mask, dtype=bool)
    block = np.zeros(n, dtype=bool) if blocked_mask is None else np.asarray(blocked_mask, dtype=bool)
    if bad.shape != (n,) or block.shape != (n,):
        raise ValueError(f"masks must have shape ({n},), got {bad.shape} and {block.shape}")
    if max_run < 1:
        raise ValueError("max_run must be at least 1")
    done = np.zeros(n, dtype=bool)
    unresolved = np.zeros(n, dtype=bool)
    for a, b in _runs(bad):
        if b - a <= max_run and a > 0 and b < n and not (bad[a - 1] or bad[b] or block[a - 1] or block[b]):
            w = ((np.arange(a, b) - (a - 1)) / (b - (a - 1))).reshape((-1,) + (1,) * (arr.ndim - 1))
            arr[a:b] = (1 - w) * arr[a - 1] + w * arr[b]
            done[a:b] = True
        else:
            unresolved[a:b] = True
    return {"data": arr, "interpolated_mask": done, "unresolved_mask": unresolved}


def _csd(erp: np.ndarray, times_ms: np.ndarray, usable: np.ndarray, sigma: float
         ) -> Tuple[np.ndarray, np.ndarray, float]:
    """Smoothed, baseline-subtracted CSD of the usable contacts, its indices and baseline SD."""
    base = times_ms < 0
    v = erp - erp[:, base].mean(axis=1, keepdims=True)
    idx = np.flatnonzero(usable)
    vu = gaussian_filter1d(v[idx], sigma, axis=0)
    vp = np.vstack([vu[:1], vu, vu[-1:]])
    c = -(vp[2:] - 2 * vp[1:-1] + vp[:-2])
    return c, idx, float(c[:, base].std() or 1.0)


def evoked_csd_sink(
    erp: np.ndarray,
    times_ms: np.ndarray,
    *,
    pitch_um: float,
    usable_mask: Optional[np.ndarray] = None,
    smooth_um: float = 50.0,
    sink_window_ms: Tuple[float, float] = (40.0, 150.0),
    min_sink_z: float = 3.0,
    onset_z: float = 3.0,
    onset_min_duration_ms: float = 5.0,
    onset_earliest_ms: float = 25.0,
    min_contacts: int = 8,
) -> Dict[str, Any]:
    """Locate the evoked current-source-density sink along the shaft.

    The baseline (``times_ms < 0``) is subtracted from every contact, the potential is
    smoothed along the shaft with a Gaussian of SD ``smooth_um``, and the CSD is the
    negative second difference (Mitzdorf 1985), in units of the potential per contact
    spacing squared. Only usable contacts enter, so the difference spans a gap where a
    contact was removed. Two estimates are returned, both z-scored against the SD of the
    baseline CSD:

    - the *strongest* sink: the contact with the deepest CSD minimum in ``sink_window_ms``,
      reported when its z is at least ``min_sink_z``;
    - the *earliest* sink: per contact, the first time at or after ``onset_earliest_ms`` at
      which the CSD stays below ``-onset_z`` for ``onset_min_duration_ms``; the contact with
      the earliest onset, ties to the deeper minimum.

    ``erp`` must be aligned to the stimulus onset itself. A reference event that precedes the
    stimulus by a variable delay smears the sink and moves it later.

    Args:
        erp: ``(n_channels, n_times)`` trial-averaged potential, channels in shaft order.
        times_ms: ``(n_times,)`` times in ms relative to the stimulus, with samples before 0.
        pitch_um: Contact pitch, um.
        usable_mask: Optional ``(n_channels,)`` bool of contacts to use; default all.
        smooth_um: SD of the Gaussian smoothing along the shaft, um.
        sink_window_ms: ``(start, stop)`` window of the strongest-sink search, ms.
        min_sink_z: Smallest z accepted as a strongest sink.
        onset_z: CSD threshold of the earliest-sink onset, in baseline SDs.
        onset_min_duration_ms: How long the CSD must stay below threshold, ms.
        onset_earliest_ms: Earliest admissible onset, ms.
        min_contacts: Fewest usable contacts the estimate needs.

    Returns:
        Dict with ``strongest_contact`` (index into the full shaft, NaN when below
        ``min_sink_z`` or too few contacts), ``strongest_z``, ``strongest_position_um``,
        ``earliest_contact``, ``earliest_onset_ms`` and ``earliest_position_um``; NaN where
        undefined.

    Raises:
        ValueError: If the shapes disagree, no sample precedes 0 ms, or ``pitch_um`` is invalid.

    References:
        Mitzdorf, U. (1985). Current source-density method and application in cat cerebral
        cortex: investigation of evoked potentials and EEG phenomena. Physiological Reviews
        65(1), 37-100. doi:10.1152/physrev.1985.65.1.37
    """
    pitch = _check_pitch(pitch_um)
    e = _check_channels_first(erp, "erp", (2,))
    t = np.asarray(times_ms, dtype=float)
    if t.shape != (e.shape[1],):
        raise ValueError(f"times_ms must have shape ({e.shape[1]},), got {t.shape}")
    if not (t < 0).any():
        raise ValueError("times_ms needs samples before 0 ms for the baseline")
    usable = np.ones(e.shape[0], dtype=bool) if usable_mask is None else np.asarray(usable_mask, dtype=bool)
    if usable.shape != (e.shape[0],):
        raise ValueError(f"usable_mask must have shape ({e.shape[0]},), got {usable.shape}")
    nan = float("nan")
    out = {"strongest_contact": nan, "strongest_z": nan, "strongest_position_um": nan,
           "earliest_contact": nan, "earliest_onset_ms": nan, "earliest_position_um": nan}
    if usable.sum() < int(min_contacts):
        return out
    c, idx, base = _csd(e, t, usable, float(smooth_um) / pitch)
    win = (t >= sink_window_ms[0]) & (t < sink_window_ms[1])
    zc = c[:, win].min(axis=1) / base
    k = int(np.argmin(zc))
    out["strongest_z"] = float(-zc[k])
    if out["strongest_z"] >= min_sink_z:
        out["strongest_contact"] = float(idx[k])
        out["strongest_position_um"] = float(idx[k]) * pitch
    dt = float(np.median(np.diff(t)))
    need = max(1, int(round(onset_min_duration_ms / dt)))
    below = (c / base < -onset_z) & (t >= onset_earliest_ms)[None, :]
    onset = np.full(len(idx), np.inf)
    for i in range(len(idx)):
        hit = np.flatnonzero(np.convolve(below[i].astype(int), np.ones(need, dtype=int), "valid") == need)
        if len(hit):
            onset[i] = t[hit[0]]
    if np.isfinite(onset).any():
        first = np.flatnonzero(onset == onset.min())
        j = first[np.argmin(c[first].min(axis=1))]
        out["earliest_contact"] = float(idx[j])
        out["earliest_onset_ms"] = float(onset[j])
        out["earliest_position_um"] = float(idx[j]) * pitch
    return out


def fuse_laminar_anchors(
    *,
    vflip_um: Optional[float] = None,
    motif_um: Optional[float] = None,
    xflip_um: Optional[float] = None,
    csd_um: Optional[float] = None,
    window_um: Optional[np.ndarray] = None,
    consistency_deep: float = float("nan"),
    consistency_superficial: float = float("nan"),
    stable_sd_um: float = 75.0,
    min_ok_windows: int = 3,
    consistency_a: float = 0.75,
    consistency_b: float = 0.60,
) -> Dict[str, Any]:
    """Choose the laminar anchor and grade it; report how the other estimates sit against it.

    The anchor is the vFLIP crossover when there is one, otherwise the spectral-motif
    crossing. The xFLIP boundary and the CSD sink are reported as distances to the anchor
    and never enter it. The grade rests on stability across trial windows and spectral
    consistency:

    - *stable*: at least ``min_ok_windows`` windows have an estimate and their SD is at most
      ``stable_sd_um``; the per-window estimates are ``window_um``.
    - *consistency*: the fraction of deep contacts with alpha-beta above gamma and of
      superficial contacts with gamma above alpha-beta; the lower of the two is compared
      with ``consistency_a`` and ``consistency_b``.
    - with a vFLIP anchor, ``"A"`` is stable with consistency at least ``consistency_a``
      and at least ``min_ok_windows`` windows; ``"B"`` is stable with consistency at least
      ``consistency_b``; ``"C"`` otherwise;
    - with only a motif anchor, ``"D"`` is stable with consistency at least
      ``consistency_a``, otherwise ``"F"``; with no anchor, ``"F"``.

    A and B carry a laminar claim; C is a sensitivity check.

    Args:
        vflip_um: vFLIP crossover position, um, NaN or None if rejected.
        motif_um: Spectral-motif crossing position, um, NaN or None.
        xflip_um: xFLIP boundary nearest the anchor, um, reported only.
        csd_um: CSD sink position, um, reported only.
        window_um: Per-window anchor estimates, um, NaN where a window gave none.
        consistency_deep: Fraction of deep contacts that are alpha-beta dominant.
        consistency_superficial: Fraction of superficial contacts that are gamma dominant.
        stable_sd_um: Largest window SD, um, that counts as stable.
        min_ok_windows: Fewest windows with an estimate.
        consistency_a: Consistency needed for grades A and D.
        consistency_b: Consistency needed for grade B.

    Returns:
        Dict with ``anchor_um``, ``anchor_source`` (``"vflip"``, ``"motif"`` or ``None``),
        ``grade``, ``stable``, ``window_sd_um``, ``n_windows_ok``, ``consistency`` and
        ``distance_um`` (a dict with ``xflip`` and ``csd``, NaN where an estimate or the
        anchor is missing).
    """
    def fin(x: Optional[float]) -> bool:
        return x is not None and bool(np.isfinite(x))

    w = np.asarray([] if window_um is None else window_um, dtype=float)
    n_ok = int(np.isfinite(w).sum())
    sd = float(np.nanstd(w)) if n_ok >= 2 else float("nan")
    stable = n_ok >= min_ok_windows and np.isfinite(sd) and sd <= stable_sd_um
    parts = [c for c in (consistency_deep, consistency_superficial) if np.isfinite(c)]
    cmin = float(min(parts)) if parts else float("nan")
    if fin(vflip_um):
        anchor, source = float(vflip_um), "vflip"
        grade = "A" if stable and cmin >= consistency_a else "B" if stable and cmin >= consistency_b else "C"
    elif fin(motif_um):
        anchor, source = float(motif_um), "motif"
        grade = "D" if stable and cmin >= consistency_a else "F"
    else:
        anchor, source, grade = float("nan"), None, "F"
    dist = {k: (abs(float(v) - anchor) if fin(v) and np.isfinite(anchor) else float("nan"))
            for k, v in (("xflip", xflip_um), ("csd", csd_um))}
    return {"anchor_um": anchor, "anchor_source": source, "grade": grade, "stable": bool(stable),
            "window_sd_um": sd, "n_windows_ok": n_ok, "consistency": cmin, "distance_um": dist}


# ------------------------------------------------------------------- spectral profiles


def _band_profiles(psd: np.ndarray, freqs: np.ndarray, use: np.ndarray,
                   low: Tuple[float, float], high: Tuple[float, float]) -> Tuple[np.ndarray, np.ndarray]:
    """Per-band depth profiles rescaled to [0, 1] over the usable contacts; NaN elsewhere."""
    sel = (freqs >= 1) & (freqs <= 150)
    q, f = psd[:, sel], freqs[sel]
    rel = (q - q[use].min(axis=0)) / np.maximum(np.ptp(q[use], axis=0), 1e-30)
    out = []
    for a, b in (low, high):
        p = rel[:, (f >= a) & (f <= b)].mean(axis=1)
        p = (p - p[use].min()) / max(float(np.ptp(p[use])), 1e-30)
        p[~use] = np.nan
        out.append(p)
    return out[0], out[1]


def _motif_crossings(lo: np.ndarray, hi: np.ndarray, use: np.ndarray, smooth_ch: float,
                     lobe_min_ch: int, lobe_min_amp: float) -> List[Tuple[float, bool]]:
    """Zeros of the smoothed ``hi - lo`` with a real lobe each side: ``(contact, sup_up)``.

    ``sup_up`` is True when the gamma (superficial) side is at the higher contact index.
    """
    idx = np.flatnonzero(use)
    if len(idx) < 2 * lobe_min_ch:
        return []
    d = gaussian_filter1d((hi - lo)[idx], smooth_ch)
    sgn = np.sign(d)
    lobes = sorted(_runs(sgn > 0) + _runs(sgn < 0))
    out: List[Tuple[float, bool]] = []
    for (a1, b1), (a2, b2) in zip(lobes[:-1], lobes[1:]):
        if b1 != a2:
            continue
        if not all((b - a) >= lobe_min_ch and np.max(np.abs(d[a:b])) >= lobe_min_amp
                   for a, b in ((a1, b1), (a2, b2))):
            continue
        k = b1 - 1
        frac = d[k] / (d[k] - d[k + 1])
        out.append((float(np.interp(k + frac, np.arange(len(idx)), idx)), bool(d[k] < 0)))
    return out


def _vflip_on(psd: np.ndarray, freqs: np.ndarray, use: np.ndarray) -> Tuple[float, VFlipResult]:
    v = vflip(psd, freqs, bad_channel_mask=~use)
    ok = bool(v.accepted and v.crossover_contact is not None)
    return (float(v.crossover_contact) if ok else float("nan")), v


# ------------------------------------------------------------------- result and orchestrator


@dataclass(frozen=True)
class LaminarCurationResult(DictAccessMixin):
    """Result of :func:`curate_and_label`.

    Attributes:
        labels: ``(n_channels,)`` array of str from :data:`LABELS`, in the channel order given.
        grade: ``"A"``..``"D"`` or ``"F"`` from :func:`fuse_laminar_anchors`; every label is
            ``"na"`` for ``"F"``.
        anchor_um: Anchor position from the first contact, um; NaN for grade F.
        anchor_source: ``"vflip"``, ``"motif"`` or None.
        superficial_at_high_index: True when the superficial side is at the higher contact
            index; None when no anchor.
        pitch_um: Contact pitch used, um.
        bad_mask: Contacts :func:`detect_bad_channels` flagged.
        interpolated_mask: Bad contacts that were interpolated.
        unusable_mask: Contacts excluded from every estimate: unresolved bad contacts, bad-dense
            zones and silent runs at either end of the shaft.
        window_anchor_um: ``(n_windows,)`` per-window anchor estimates, um.
        window_sd_um: SD of ``window_anchor_um`` over windows with an estimate.
        consistency_deep: Fraction of deep contacts that are alpha-beta dominant.
        consistency_superficial: Fraction of superficial contacts that are gamma dominant.
        n_crossings: Spectral-motif crossings found on the whole shaft. More than one means
            the shaft may sample more than one cortical sheet, which this function does not split.
        crossings_um: Positions of those crossings, um.
        vflip: The :class:`~jnwb.laminar.VFlipResult` on the pooled spectrum, or None when too
            few contacts were usable.
        xflip_distance_um, csd_distance_um: Distance of the xFLIP boundary and of the CSD
            strongest sink from the anchor, um; NaN when absent. Reported only.
        csd: The :func:`evoked_csd_sink` result, or None without ``erp``.
        parameters: The thresholds the call used.
    """

    labels: np.ndarray
    grade: str
    anchor_um: float
    anchor_source: Optional[str]
    superficial_at_high_index: Optional[bool]
    pitch_um: float
    bad_mask: np.ndarray
    interpolated_mask: np.ndarray
    unusable_mask: np.ndarray
    window_anchor_um: np.ndarray
    window_sd_um: float
    consistency_deep: float
    consistency_superficial: float
    n_crossings: int
    crossings_um: Tuple[float, ...]
    vflip: Optional[VFlipResult]
    xflip_distance_um: float
    csd_distance_um: float
    csd: Optional[Dict[str, Any]]
    parameters: Dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert the result to a dict; arrays are copied."""
        return {
            "labels": self.labels.copy(), "grade": self.grade, "anchor_um": float(self.anchor_um),
            "anchor_source": self.anchor_source,
            "superficial_at_high_index": self.superficial_at_high_index,
            "pitch_um": float(self.pitch_um), "bad_mask": self.bad_mask.copy(),
            "interpolated_mask": self.interpolated_mask.copy(),
            "unusable_mask": self.unusable_mask.copy(),
            "window_anchor_um": self.window_anchor_um.copy(), "window_sd_um": float(self.window_sd_um),
            "consistency_deep": float(self.consistency_deep),
            "consistency_superficial": float(self.consistency_superficial),
            "n_crossings": int(self.n_crossings), "crossings_um": tuple(self.crossings_um),
            "vflip": None if self.vflip is None else self.vflip.to_dict(),
            "xflip_distance_um": float(self.xflip_distance_um),
            "csd_distance_um": float(self.csd_distance_um),
            "csd": None if self.csd is None else dict(self.csd),
            "parameters": dict(self.parameters),
        }


def curate_and_label(
    lfp: np.ndarray,
    fs: float,
    *,
    pitch_um: float,
    erp: Optional[np.ndarray] = None,
    erp_times_ms: Optional[np.ndarray] = None,
    n_windows: int = 4,
    band_low_hz: Tuple[float, float] = MOTIF_BAND_LOW_HZ,
    band_high_hz: Tuple[float, float] = MOTIF_BAND_HIGH_HZ,
    granular_thickness_um: float = 400.0,
    max_superficial_um: float = 1200.0,
    max_deep_um: float = 1600.0,
    silent_threshold: float = 0.12,
    smooth_um: float = 50.0,
    min_lobe_um: float = 150.0,
    min_lobe_amplitude: float = 0.20,
    bad_zone_contacts: int = 6,
    bad_zone_fraction: float = 0.60,
    edge_fraction: float = 0.10,
    edge_jump_z: float = 6.0,
    stable_sd_um: float = 75.0,
    min_ok_windows: int = 3,
    consistency_a: float = 0.75,
    consistency_b: float = 0.60,
    compute_xflip: bool = True,
    xflip_n_surrogates: int = 50,
    rng: RNGLike = DEFAULT_SEED,
    **bad_channel_kwargs: Any,
) -> LaminarCurationResult:
    """Curate a laminar LFP recording and label every contact by cortical compartment.

    Order: :func:`detect_bad_channels`; bad-dense zones of ``bad_zone_contacts`` contacts with
    at least ``bad_zone_fraction`` bad become unusable; short bad runs are interpolated
    (:func:`interpolate_channel_runs`), the rest are unusable; silent runs at either end of
    the shaft (both band profiles below ``silent_threshold``) become unusable. The spectral
    anchor is the vFLIP crossover of the pooled spectrum, else the spectral-motif crossing;
    the same estimates on ``n_windows`` consecutive blocks of epochs give the stability
    that :func:`fuse_laminar_anchors` grades. xFLIP and the evoked CSD
    (:func:`evoked_csd_sink`, with ``erp``) are reported as distances to the anchor and
    never move it.

    Labels, from the anchor: contacts within ``granular_thickness_um / 2`` of it are
    ``"input"``; the rest on the gamma side are ``"superficial"`` and on the alpha-beta
    side ``"deep"``. A silent run at the deep end of the shaft is ``"WM"``, one at the
    superficial end ``"outside_cortex"``. A jump in neighbor decorrelation (robust z above ``edge_jump_z``) in the outer
    ``edge_fraction`` of the shaft at the superficial end marks ``"outside_cortex"`` from
    the jump outward. Contacts farther than ``max_superficial_um`` or ``max_deep_um`` from
    the anchor, and every unusable contact, are ``"na"``. Grade ``"F"`` sets every label to
    ``"na"``; labels are never imputed onto a fit that does not hold.

    One cortical sheet is assumed. A shaft whose spectral profile crosses more than once
    reports ``n_crossings`` and is not split: pass one contiguous range of contacts per
    sheet. The unit of inference is the probe, not the contact: contacts on one shaft are
    not independent. Trials within ``n_windows`` blocks are taken in the order given, so
    pass them in recording order for the windows to test stability across the session.

    Args:
        lfp: ``(n_channels, n_epochs, n_samples)`` LFP in the units the PSD is taken in,
            channels in shaft order (either direction), epochs in recording order.
        fs: Sampling rate, Hz.
        pitch_um: Contact pitch, um.
        erp: Optional ``(n_channels, n_times)`` trial-averaged potential for the CSD.
        erp_times_ms: Times of ``erp``, ms, relative to the stimulus; required with ``erp``.
        n_windows: Consecutive blocks of epochs used for stability.
        band_low_hz, band_high_hz: Alpha-beta and gamma bands of the motif.
        granular_thickness_um: Width of the ``"input"`` zone, um, as in :func:`label_layers`.
        max_superficial_um, max_deep_um: Thickness prior: distance from the anchor beyond
            which a contact is ``"na"``, um.
        silent_threshold: Both rescaled band profiles below this marks a silent contact.
        smooth_um: Gaussian SD along the shaft for the motif profile, um.
        min_lobe_um, min_lobe_amplitude: Smallest extent (um) and peak height of each lobe
            either side of a motif crossing.
        bad_zone_contacts, bad_zone_fraction: Bad-dense zone rule, in adjacent contacts.
        edge_fraction, edge_jump_z: Outer fraction of the shaft searched for the cortical edge
            and the robust z of the decorrelation jump that marks it.
        stable_sd_um, min_ok_windows, consistency_a, consistency_b: See
            :func:`fuse_laminar_anchors`.
        compute_xflip: Compute the xFLIP boundary for the report; False skips it.
        xflip_n_surrogates: Phase surrogates of the xFLIP null.
        rng: Seed or generator of the xFLIP surrogates.
        **bad_channel_kwargs: Passed to :func:`detect_bad_channels`.

    Returns:
        A :class:`LaminarCurationResult`.

    Raises:
        ValueError: On invalid shapes, non-finite data, ``pitch_um``, ``n_windows`` larger
            than the epoch count, or ``erp`` without ``erp_times_ms``.

    References:
        Mendoza-Halliday, D., et al. (2024). A ubiquitous spectrolaminar motif of local field
        potential power across the primate cortex. Nature Neuroscience.
        doi:10.1038/s41593-023-01554-7 -- the 10-19 Hz and 75-150 Hz bands of the motif.
        :func:`evoked_csd_sink` cites the CSD reference.
    """
    pitch = _check_pitch(pitch_um)
    x = _check_channels_first(lfp, "lfp", (3,))
    n, n_ep, _ = x.shape
    if not (1 <= n_windows <= n_ep):
        raise ValueError(f"n_windows must be in [1, n_epochs={n_ep}], got {n_windows}")
    if erp is not None and erp_times_ms is None:
        raise ValueError("erp needs erp_times_ms")
    gen = resolve_rng(rng, func_name="curate_and_label")
    ch = lambda um: um / pitch  # um -> contacts  # noqa: E731
    params = {k: v for k, v in locals().items()
              if k not in ("lfp", "fs", "erp", "erp_times_ms", "x", "pitch", "gen", "ch", "n", "n_ep",
                           "bad_channel_kwargs", "rng")}
    params["bad_channel_kwargs"] = dict(bad_channel_kwargs)
    x = x - x.mean(axis=2, keepdims=True)
    idx = np.arange(n)
    nan = float("nan")

    # curation
    det = detect_bad_channels(x, fs, **bad_channel_kwargs)
    bad = det["bad_mask"]
    dens = np.convolve(bad, np.ones(bad_zone_contacts) / bad_zone_contacts, "same")
    unusable = np.zeros(n, dtype=bool)
    for a, b in _runs(dens >= bad_zone_fraction):
        if b - a >= bad_zone_contacts:
            unusable[a:b] = True
    fixed = interpolate_channel_runs(x, bad & ~unusable, blocked_mask=unusable)
    x = fixed["data"]
    interp = fixed["interpolated_mask"]
    unusable |= fixed["unresolved_mask"]
    if erp is not None:
        erp_c = interpolate_channel_runs(np.asarray(erp, dtype=float), interp, blocked_mask=unusable)["data"]
    else:
        erp_c = None

    nperseg = min(512, x.shape[-1])
    freqs, pooled = signal.welch(x, fs=fs, nperseg=nperseg, axis=-1)
    pooled = pooled.mean(axis=1)
    win_id = np.minimum((np.arange(n_ep) * n_windows) // n_ep, n_windows - 1)
    win_psd = [signal.welch(x[:, win_id == k], fs=fs, nperseg=nperseg, axis=-1)[1].mean(axis=1)
               for k in range(n_windows)]
    q = max(1, int(round(fs / bad_channel_kwargs.get("correlation_fs_hz", 100.0))))
    reduced = (signal.decimate(x, q, axis=-1) if q > 1 else x).reshape(n, -1)

    smooth_ch, lobe_ch = ch(smooth_um), max(2, int(round(ch(min_lobe_um))))
    use = ~unusable
    labels = np.full(n, "na", dtype=object)
    empty = dict(labels=labels.astype(str), bad_mask=bad, interpolated_mask=interp, parameters=params)

    def finish(grade: str, **kw: Any) -> LaminarCurationResult:
        base = dict(grade=grade, anchor_um=nan, anchor_source=None, superficial_at_high_index=None,
                    pitch_um=pitch, unusable_mask=~use, window_anchor_um=np.full(n_windows, nan),
                    window_sd_um=nan, consistency_deep=nan, consistency_superficial=nan, n_crossings=0,
                    crossings_um=(), vflip=None, xflip_distance_um=nan, csd_distance_um=nan, csd=None)
        base.update(empty)
        base.update(kw)
        return LaminarCurationResult(**base)

    if use.sum() < 2 * lobe_ch:
        return finish("F")

    # silent runs at both ends are not cortex and enter no estimate
    lo, hi = _band_profiles(pooled, freqs, use, band_low_hz, band_high_hz)
    silent = (np.nan_to_num(lo) < silent_threshold) & (np.nan_to_num(hi) < silent_threshold)
    stripped = np.zeros(n, dtype=bool)
    for seq in (idx, idx[::-1]):
        for i in seq:
            if unusable[i]:
                continue
            if silent[i]:
                use[i] = False
                stripped[i] = True
            else:
                break
    if use.sum() < 2 * lobe_ch:
        return finish("F")
    lo, hi = _band_profiles(pooled, freqs, use, band_low_hz, band_high_hz)
    crossings = _motif_crossings(lo, hi, use, smooth_ch, lobe_ch, min_lobe_amplitude)

    c_v, v = _vflip_on(pooled, freqs, use)
    c_m, up_m = crossings[0] if crossings else (nan, None)
    have_v = np.isfinite(c_v) and v.high_peak_contact is not None
    sup_up = bool(v.high_peak_contact > v.low_peak_contact) if have_v else up_m
    anchor = c_v if np.isfinite(c_v) else c_m

    wv, wm = [], []
    for k in range(n_windows):
        wv.append(_vflip_on(win_psd[k], freqs, use)[0])
        lo_k, hi_k = _band_profiles(win_psd[k], freqs, use, band_low_hz, band_high_hz)
        ck = _motif_crossings(lo_k, hi_k, use, smooth_ch, lobe_ch, min_lobe_amplitude)
        wm.append(min((c for c, _ in ck), key=lambda c: abs(c - anchor)) if (ck and np.isfinite(anchor)) else nan)
    win = np.asarray(wv if np.isfinite(c_v) else wm, dtype=float)

    consist_d = consist_s = nan
    if np.isfinite(anchor) and sup_up is not None:
        deep_side = (idx < anchor) if sup_up else (idx > anchor)
        is_input = np.abs(idx - anchor) * pitch <= granular_thickness_um / 2.0
        cortex = use.copy()
        for i in (idx if sup_up else idx[::-1]):  # silent run from the deep end is white matter
            if not use[i]:
                continue
            if not deep_side[i]:
                break
            if lo[i] < silent_threshold and hi[i] < silent_threshold:
                cortex[i] = False
                labels[i] = "WM"
            else:
                break
        edge = np.zeros(n, dtype=bool)
        ci = np.flatnonzero(cortex)
        if len(ci) > 10:
            r = np.corrcoef(reduced[ci])
            dd = np.full(n, np.nan)
            dd[ci[:-1]] = 1 - np.diag(r, 1)
            zj = _robust_z(dd)
            top = idx[::-1] if sup_up else idx
            outer = top[: max(1, int(edge_fraction * n))]
            jumps = [i for i in outer if np.isfinite(zj[i]) and zj[i] > edge_jump_z]
            if jumps:
                j = jumps[-1]
                edge = (idx > j) if sup_up else (idx <= j)
                edge &= cortex
                cortex &= ~edge
                labels[edge] = "outside_cortex"
        dist = np.abs(idx - anchor) * pitch
        cortex &= ~((~deep_side) & (dist > max_superficial_um))
        cortex &= ~(deep_side & (dist > max_deep_um))
        labels[stripped & deep_side] = "WM"
        labels[stripped & ~deep_side] = "outside_cortex"
        labels[cortex & is_input] = "input"
        labels[cortex & ~is_input & ~deep_side] = "superficial"
        labels[cortex & ~is_input & deep_side] = "deep"
        delta = hi - lo
        if (labels == "deep").any():
            consist_d = float(np.nanmean(delta[labels == "deep"] < 0))
        if (labels == "superficial").any():
            consist_s = float(np.nanmean(delta[labels == "superficial"] > 0))

    xf = nan
    if compute_xflip and use.sum() >= 8 and np.isfinite(anchor):
        xr = xflip(reduced[use], n_blocks=None, n_surrogates=int(xflip_n_surrogates), rng=gen)
        bounds = idx[use][np.flatnonzero(np.diff(xr.labels)) + 1]
        if len(bounds):
            xf = float(bounds[np.argmin(np.abs(bounds - anchor))]) * pitch
    csd = None
    if erp_c is not None:
        csd = evoked_csd_sink(erp_c, np.asarray(erp_times_ms, dtype=float), pitch_um=pitch,
                              usable_mask=use, smooth_um=smooth_um)
    fused = fuse_laminar_anchors(
        vflip_um=c_v * pitch, motif_um=c_m * pitch, xflip_um=xf,
        csd_um=nan if csd is None else csd["strongest_position_um"],
        window_um=win * pitch, consistency_deep=consist_d, consistency_superficial=consist_s,
        stable_sd_um=stable_sd_um, min_ok_windows=min_ok_windows,
        consistency_a=consistency_a, consistency_b=consistency_b)
    if fused["grade"] == "F":
        labels[:] = "na"
    return finish(
        fused["grade"], labels=labels.astype(str), anchor_um=fused["anchor_um"],
        anchor_source=fused["anchor_source"], superficial_at_high_index=sup_up,
        window_anchor_um=win * pitch, window_sd_um=fused["window_sd_um"],
        consistency_deep=consist_d, consistency_superficial=consist_s, n_crossings=len(crossings),
        crossings_um=tuple(c * pitch for c, _ in crossings), vflip=v,
        xflip_distance_um=fused["distance_um"]["xflip"], csd_distance_um=fused["distance_um"]["csd"], csd=csd)
