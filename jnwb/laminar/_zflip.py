"""zFLIP: the laminar phase-delay gradient from pairwise wPLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple
import numpy as np
from .._dictlike import DictAccessMixin
from .._rng import Default, RNGLike, recorded_rng, resolve_seed_alias
from scipy import signal, stats
from .._spread import is_constant
from ..permutation import _count_at_least_as_extreme
from ..spectral import (
    MIN_COHERENCE_NPERSEG,
    _require_identifiable_segmentation,
    _wpli_from_cross_spectra,
)
from ._xflip import _surrogate_phase_randomize


@dataclass(frozen=True)
class ZFlipResult(DictAccessMixin):
    """Container for zFLIP Cortical Depth Phase-Gradient & Delay Estimation results.

    zFLIP estimates laminar phase slope and, where the identifiability gate passes, an
    apparent per-contact phase delay across ordered
    electrode contacts along a linear probe shaft.

    Attributes:
        adjacent_wpli: 1D array of shape (n_channels - 1,) containing the weighted
            Phase Lag Index between adjacent contacts; NaN when not computed, and for a
            pair with a constant contact (all-zero included). Here and in every
            ``adjacent_*`` field, a contact is constant only when every sample of the whole
            record equals every other, compared exactly; a contact of tiny but nonzero
            amplitude is measured. A contact that is a straight line in time over the whole
            record, to within round-off (rms second difference at most 4 eps of its
            largest magnitude), is refused the same way, because the
            segments' linear detrend leaves only round-off of it.
        adjacent_delays_s: 1D array of shape (n_channels - 1,) of pairwise delay
            estimates Delta tau in seconds between adjacent contacts (contact i to i+1).
            Positive indicates contact i leads contact i+1. Non-identifiable pairs
            are reported as NaN.
        adjacent_linearity_r2: 1D array of shape (n_channels - 1,) containing the
            coefficient of determination R^2 of the unwrapped phase-frequency linear fit;
            NaN for a pair with a constant contact.
        adjacent_identifiable: 1D boolean array of shape (n_channels - 1,) indicating
            which adjacent pairs satisfy all identifiability criteria (linearity, frequency support,
            unwrapping unambiguous interval, pair wPLI at least ``min_wpli``, pair wPLI
            significant against its own phase surrogates at ``alpha``, both contacts'
            in-band power fraction at least ``min_band_power_fraction``); False for every
            pair when no surrogates were drawn (``n_surrogates=0``, or a constant contact).
        mean_wpli: Average wPLI across adjacent contacts; NaN when not computed or when
            any contact is constant.
        apparent_velocity_m_s: Apparent phase-delay velocity along the shaft in m/s
            under the fitted linear model (v = pitch_m / tau_per_channel), or None if
            unidentifiable or pitch_um was not provided.
        tau_per_channel_s: Spatial delay gradient in seconds per contact, in input row
            order: positive means the lower-index contact leads. NaN if unidentifiable.
        directionality: Which end of the shaft leads in phase, named from the sign of
            ``tau_per_channel_s`` and the ``orientation`` the caller stated:
            - "superficial_to_deep" (the superficial end leads)
            - "deep_to_superficial" (the deep end leads)
            - "unidentifiable" (delay identifiability criteria not satisfied)
        delay_identifiable: Boolean indicating whether the phase-frequency relationship
            satisfies the identifiability gate across contacts.
        p_value: Surrogate p-value against the per-channel phase-randomised null, or NaN
            when the test was not performed (``n_surrogates=0``, or a contact is constant).
        accepted: True only if the surrogate test was performed and significant
            (p <= alpha), coupling is sufficient (mean_wpli >= min_wpli), and the delay
            is identifiable, which requires every adjacent pair's wPLI >= min_wpli and every
            contact's in-band power fraction >= min_band_power_fraction.
        rejection_reason: Diagnostic string explaining rejection, or None if accepted.
        n_channels: Number of channels evaluated.
        pitch_um: Inter-contact spacing in micrometers, if supplied.
        orientation: The contact order the caller stated: ``'superficial_to_deep'`` (row 0
            superficial) or ``'deep_to_superficial'`` (row 0 deep).
        surrogate_seed_entropy: The entropy the surrogate generator was built from: the
            seed for an int `rng`, the fresh OS entropy drawn for `rng=None`, and the child
            seed drawn from a `Generator`. Passing it back as `rng` reproduces `p_value`.
            None when no surrogates were drawn.
    """

    adjacent_wpli: np.ndarray
    adjacent_delays_s: np.ndarray
    adjacent_linearity_r2: np.ndarray
    adjacent_identifiable: np.ndarray
    mean_wpli: float
    apparent_velocity_m_s: Optional[float]
    tau_per_channel_s: float
    directionality: str
    delay_identifiable: bool
    p_value: float
    accepted: bool
    rejection_reason: Optional[str]
    n_channels: int
    pitch_um: Optional[float] = None
    orientation: Optional[str] = None
    surrogate_seed_entropy: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result container to dictionary for serialization."""
        return {
            "adjacent_wpli": self.adjacent_wpli.copy(),
            "adjacent_delays_s": self.adjacent_delays_s.copy(),
            "adjacent_linearity_r2": self.adjacent_linearity_r2.copy(),
            "adjacent_identifiable": self.adjacent_identifiable.copy(),
            "mean_wpli": float(self.mean_wpli),
            "apparent_velocity_m_s": float(self.apparent_velocity_m_s) if self.apparent_velocity_m_s is not None else None,
            "tau_per_channel_s": float(self.tau_per_channel_s) if np.isfinite(self.tau_per_channel_s) else np.nan,
            "directionality": str(self.directionality),
            "delay_identifiable": bool(self.delay_identifiable),
            "p_value": float(self.p_value) if np.isfinite(self.p_value) else np.nan,
            "accepted": bool(self.accepted),
            "rejection_reason": self.rejection_reason,
            "n_channels": int(self.n_channels),
            "pitch_um": float(self.pitch_um) if self.pitch_um is not None else None,
            "orientation": self.orientation,
            "surrogate_seed_entropy": self.surrogate_seed_entropy,
        }


_ZFLIP_ORIENTATIONS = ("superficial_to_deep", "deep_to_superficial")

# A row counts as linear in time when the rms of its second difference is at most this many
# eps of its largest magnitude. The second difference of a ramp is the round-off of single
# samples, so it does not grow with length, as the residual of a fitted line does (a
# cumulative-sum ramp left that residual at 3400 eps at n=1e5). Measured over 756 ramps
# (exact, cumulative-sum and linspace; n 16 to 1e5; slope 1e-9 to 1e9; offset 0 to 1e11),
# the largest was 1.0; a ramp moved by -1, 0 or +1 ulp per sample reaches 2.2 at the bottom of
# a binade, so 4 leaves a factor of 1.8 over that. A unit-SD signal stays above it up to an
# offset of about 7e12 for a 15 Hz sine (2.9 at 1e13) and about 2.8e15 for white noise
# (sqrt(6)/(4 eps)).
_LINEAR_ROUNDOFF_EPS = 4.0


def _linear_to_roundoff(rows: np.ndarray) -> np.ndarray:
    """True for each row of ``rows`` (2D, time last) that is a straight line to round-off."""
    rms = np.sqrt(np.mean(np.diff(rows, 2, axis=-1) ** 2, axis=-1))
    scale = np.max(np.abs(rows), axis=-1)
    return rms <= _LINEAR_ROUNDOFF_EPS * np.finfo(float).eps * scale


def zflip(
    lfp_matrix: np.ndarray,
    fs: float,
    *,
    orientation: str,
    freq_range: Tuple[float, float] = (15.0, 35.0),
    pitch_um: Optional[float] = None,
    nperseg: Optional[int] = None,
    noverlap: Optional[int] = None,
    min_linearity_r2: float = 0.70,
    min_wpli: float = 0.15,
    min_band_power_fraction: float = 0.01,
    n_surrogates: int = 50,
    alpha: float = 0.05,
    rng: RNGLike = Default(0),
    seed: Any = Default(0),
) -> ZFlipResult:
    r"""Estimate depth phase gradients, and an apparent phase delay and velocity only where phase is linear in frequency.

    Evaluates phase slopes across ordered laminar contacts. For a true physical delay
    :math:`\Delta \tau` between contacts :math:`c` and :math:`c+1`, the phase difference
    is linear across frequency:

    .. math::
        \Delta \phi(f) = -2\pi \Delta \tau \cdot f

    where :math:`\Delta \tau = -\frac{1}{2\pi} \frac{d\Delta \phi}{df}`.

    Important Epistemic Invariants & Identifiability Gates:
    1. **Coupling vs. Direction**: wPLI evaluates coupling consistency with reduced
       sensitivity to zero-phase-lag mixing, but is strictly unsigned (:math:`\ge 0`).
       Directionality and delay are derived from the signed phase slope, not wPLI magnitude.
    2. **Identifiability Criteria**: Delay and apparent velocity are defined only when
       every adjacent contact pair satisfies:
       - Linear goodness of fit :math:`R^2 \ge \text{min\_linearity\_r2}` (default 0.70).
       - Frequency support :math:`|F| \ge 3` bins within `freq_range`.
       - Estimated delay within the unambiguous interval :math:`|\Delta \tau| < 1 / (2 \Delta f)`.
         This bounds the estimate, not the true delay: a true delay beyond the interval
         aliases to a smaller estimate that passes, so this check alone cannot detect
         wrapping.
       - Pair wPLI at least `min_wpli`, the threshold `mean_wpli` is also held to. A weakly
         coupled pair can still fit a linear phase, and its delay would enter the spatial fit
         while a well-coupled mean hides it.
       - Each contact of the pair carries at least `min_band_power_fraction` of its power
         inside `freq_range`. wPLI alone does not show this: a contact carrying only an
         out-of-band sinusoid reached pair wPLI 0.16 to 0.31 through leakage. Leakage into
         the band edge can still pass this check (see `min_band_power_fraction`).
       - Pair wPLI significant against its own phase-randomised surrogates: at least as
         large as in all but a fraction `alpha` of them, the same draws the mean is tested
         against (p = (1 + k) / (1 + n_surrogates), k the surrogates at least as large). A
         contact independent of the others can pass the three checks above: with 5 bins
         in band a random phase often fits R^2 0.7, and over about 60 segments two
         independent signals often reach wPLI 0.15. Each pair is tested at `alpha`
         without a multiplicity correction; every pair must pass, so the shaft is accepted
         only when the least coupled pair passes. A pair without its null is not
         identifiable: with `n_surrogates=0` no pair is, and no delay is reported. A
         constant or linear-in-time contact has no wPLI, so its two pairs draw no null and
         are not identifiable; every other pair draws its own. With few
         in-band bins a surrogate can match a wPLI of 1.0: at the default band, 256
         samples leave 3 bins and about 10% of surrogates tie 1.0, so no pair passes; 512
         samples (5 bins) tie in 0.4-0.8% of surrogates for a broadband wave and about 4%
         for a sinusoid.
       and the cumulative delay along the shaft is linear in contact index
       (:math:`R^2 \ge 0.5`). If any pair or the spatial fit fails, delay and velocity
       are returned as `NaN` / `None`, and `delay_identifiable = False`. The thresholds
       (0.70, 0.5) are model choices, not derived constants.
    3. **Apparent Velocity**: Reported strictly as *apparent phase-delay velocity under the
       fitted linear model* (:math:`v = \Delta z / \Delta \tau`), not unconditional physical velocity.
    4. **What the delay measures**: :math:`\Delta \tau` is the slope of the phase of the
       cross-spectrum averaged over linearly detrended segments, which is a group delay;
       detrending keeps a DC offset, drift or strong shared slow power from leaking into the
       band (a shared 2 Hz component at 30 SD biased it by 12% without detrending, 1.3%
       with). Broadband background that is independent at each contact is not removed: an
       independent 1/f^2 background at about three times the wave's amplitude biased the
       delay by about +7%. It equals the phase delay
       only when the delay does not vary with frequency. Unlike wPLI, that phase is NOT
       insensitive to zero-lag mixing: a zero-lag component shared by adjacent contacts
       pulls the estimate toward 0 (equal-power mixing halves it), and superposed waves
       travelling in opposite directions pull it toward the stronger one. Either can
       still pass every gate, so an accepted delay is an apparent delay under the
       single-wave model.

    Args:
        lfp_matrix: 2D array of shape `(n_channels, n_samples)` ordered along the probe shaft,
            in the direction `orientation` names. Minimum 3 channels required. Pre-averaged :math:`C \times C \times F` tensors
            are rejected with ValueError because segment information is required for wPLI.
        fs: Sampling frequency in Hz (must be strictly positive).
        orientation: Required. Which end of the shaft row 0 is: ``'superficial_to_deep'``
            (row 0 is the most superficial contact) or ``'deep_to_superficial'`` (row 0 is
            the deepest, as in a tip-first electrode table). ``directionality`` names an
            anatomical direction from this and the sign of the row-order delay gradient,
            so the wrong value reverses it; nothing in the LFP can detect that. It has no
            default, because the row order alone says nothing about depth; any other value
            raises ValueError.
        freq_range: `(min_freq, max_freq)` in Hz over which the linear phase slope is fitted.
        pitch_um: Inter-contact spacing along the shaft in micrometers (optional).
        nperseg: Welch segment length for STFT; defaults to ``min(max(N // 2, 8), 256)``,
            which keeps at least 2 segments so adjacent wPLI is identifiable.
        noverlap: Segment overlap; defaults to `nperseg // 2`.
        min_linearity_r2: Minimum :math:`R^2` threshold for unwrapped phase linearity (default 0.70).
        min_wpli: Minimum wPLI required of the adjacent average for acceptance and of each
            adjacent pair for its delay to be identifiable (default 0.15).
        min_band_power_fraction: Minimum fraction of a contact's power that must lie inside
            `freq_range` for the delays of its two adjacent pairs to be identifiable
            (default 0.01). The power is summed over the linearly detrended segment spectra
            the phase slope uses, so a DC offset or slow drift does not lower it. A contact
            whose power lies outside the band has only window leakage there, which can fit a
            linear phase. Measured on the default band and segment length, the default
            refuses sinusoids at or below 9 Hz or at or above 40 Hz (fractions below 5e-3)
            and keeps broadband white noise, whose 15-35 Hz fraction is about 0.04 (5 of 129
            bins; a single 2000-sample record measured 0.030). It does not refuse power
            leaking into either band edge: a sinusoid from about 9.5 Hz up to the lower edge,
            or from the upper edge to about 38 Hz, i.e. within the main lobe of an edge bin,
            can carry 0.01 to 0.7 of its power in the band and still pass and yield a delay.
        n_surrogates: Number of per-channel Fourier phase-randomised surrogates (default 50).
            ``0`` skips the test: ``p_value`` is NaN, no adjacent pair is identifiable,
            ``tau_per_channel_s`` is NaN and ``accepted`` is False, because a pair's delay
            needs its surrogate null. The smallest attainable p-value is
            ``1 / (n_surrogates + 1)``.
        alpha: Significance threshold in (0, 1) for rejecting the independent-phase null
            (default 0.05).
        rng: An int seed, a NumPy Generator, or None for fresh OS entropy, for surrogate
            evaluation (``seed`` is the old spelling and still works). A `Generator` gives
            up one draw, a child seed the surrogates run on. The seed used is returned as
            `surrogate_seed_entropy`.

    Returns:
        :class:`ZFlipResult` container with full diagnostic fields and acceptance flag.

    Raises:
        TypeError: If `orientation` is not given, or `rng` is not an int, a Generator or
            None.
        ValueError: If `orientation` is not one of the two orders, input is not
            a finite 2D array of at least 3 channels, `fs <= 0`,
            `freq_range` is not an increasing non-negative pair, `alpha` is outside (0, 1),
            `n_surrogates < 0`, a threshold is outside [0, 1], or the segmentation yields
            fewer than 2 segments.

    References:
        Vinck, M., et al. (2011). An improved index of phase-synchronization for
        electrophysiological data in the presence of volume-conduction, noise and
        sample-size bias. NeuroImage. doi:10.1016/j.neuroimage.2011.01.055 -- the weighted
        phase lag index of each adjacent contact pair, as in :func:`jnwb.wpli`.
    """
    seed = resolve_seed_alias(rng, seed, alias_name='seed', func_name='zflip')
    gen, seed_entropy = recorded_rng(seed, "zflip")
    if orientation not in _ZFLIP_ORIENTATIONS:
        raise ValueError(
            f"zflip needs orientation='superficial_to_deep' (row 0 is the most superficial "
            f"contact) or 'deep_to_superficial' (row 0 is the deepest); got {orientation!r}. "
            "directionality names a direction in depth from row order, and the row order of "
            "an electrode table can run either way."
        )
    lfp = np.asarray(lfp_matrix, dtype=float)
    if lfp.ndim != 2:
        raise ValueError(
            f"zflip requires a 2D array of shape (n_channels, n_samples); got shape {lfp.shape}."
        )
    n_channels, n_samples = lfp.shape
    if n_channels < 3:
        raise ValueError(f"zflip requires at least 3 channels along the probe shaft; got {n_channels}.")
    if fs <= 0 or not np.isfinite(fs):
        raise ValueError(f"fs must be strictly positive and finite; got {fs}.")
    if pitch_um is not None and (pitch_um <= 0 or not np.isfinite(pitch_um)):
        raise ValueError(f"pitch_um must be strictly positive if provided; got {pitch_um}.")
    if not np.all(np.isfinite(lfp)):
        raise ValueError(
            "zflip requires finite input; NaN or Inf in any contact propagates into every "
            "segment that contains it. Remove or repair those samples first."
        )
    lo, hi = float(freq_range[0]), float(freq_range[1])
    if not (np.isfinite(lo) and np.isfinite(hi) and 0.0 <= lo < hi):
        raise ValueError(f"freq_range must be an increasing non-negative pair; got {freq_range}.")
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must lie in (0, 1); got {alpha}.")
    if int(n_surrogates) != n_surrogates or n_surrogates < 0:
        raise ValueError(f"n_surrogates must be a non-negative integer; got {n_surrogates}.")
    n_surrogates = int(n_surrogates)
    for name, value in (("min_linearity_r2", min_linearity_r2), ("min_wpli", min_wpli),
                        ("min_band_power_fraction", min_band_power_fraction)):
        if not (0.0 <= value <= 1.0):
            raise ValueError(f"{name} must lie in [0, 1]; got {value}.")

    if nperseg is None:
        # n // 2 rather than the coherence family's n // 8: the phase slope needs >= 3 bins
        # inside a narrow band, so segment length is kept. Unchanged for n >= 512.
        nperseg = min(max(n_samples // 2, MIN_COHERENCE_NPERSEG), 256)
    if noverlap is None:
        noverlap = nperseg // 2
    # One segment saturates wPLI at 1.0 for any input, which would make min_wpli inert.
    _require_identifiable_segmentation(n_samples, nperseg, noverlap, "zflip", "adjacent wPLI")

    # Multi-channel STFT: (n_channels, n_freqs, n_segments). Each segment's linear trend is
    # removed first: shared slow power or drift otherwise leaks into the band through the
    # window and biases the phase slope (a shared 2 Hz component at 30 SD raised the delay
    # by 12%, and a 1 Hz one at 100 SD by 34%).
    freqs, _, Z = signal.stft(
        lfp, fs=fs, nperseg=nperseg, noverlap=noverlap, boundary=None, padded=False, axis=-1,
        detrend="linear",
    )

    mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    n_freq_bins = int(np.sum(mask))
    if n_freq_bins < 3:
        return ZFlipResult(
            adjacent_wpli=np.full(n_channels - 1, np.nan),
            adjacent_delays_s=np.full(n_channels - 1, np.nan),
            adjacent_linearity_r2=np.full(n_channels - 1, np.nan),
            adjacent_identifiable=np.zeros(n_channels - 1, dtype=bool),
            mean_wpli=float("nan"),
            apparent_velocity_m_s=None,
            tau_per_channel_s=float("nan"),
            directionality="unidentifiable",
            delay_identifiable=False,
            p_value=float("nan"),
            accepted=False,
            rejection_reason=f"Insufficient frequency bins in freq_range {freq_range} (got {n_freq_bins} bins, need >= 3)",
            n_channels=n_channels,
            pitch_um=pitch_um,
            orientation=orientation,
        )

    f_band = freqs[mask]
    df = float(freqs[1] - freqs[0]) if len(freqs) > 1 else 1.0
    max_tau_unambiguous = 1.0 / (2.0 * df) if df > 0 else np.inf

    adj_wpli = np.zeros(n_channels - 1, dtype=float)
    adj_delays = np.zeros(n_channels - 1, dtype=float)
    adj_r2 = np.zeros(n_channels - 1, dtype=float)
    adj_identifiable = np.zeros(n_channels - 1, dtype=bool)
    # A pair with a constant contact has no phase lag to weigh; its wPLI, linearity and
    # delay are NaN and it is not identifiable, as in jnwb.wpli, so rounding residue in the
    # constant contact's spectrum enters neither mean_wpli nor the delay fit. A contact that is
    # an exact linear ramp is flat in the same sense: the per-segment linear detrend reduces
    # it to round-off residue, which could otherwise fit a phase and a delay.
    constant_contacts = np.flatnonzero(is_constant(lfp, axis=1)).tolist()
    ramp_contacts = [c for c in np.flatnonzero(_linear_to_roundoff(lfp)).tolist()
                     if c not in constant_contacts]
    flat_contacts = sorted(constant_contacts + ramp_contacts)
    # A contact whose power lies outside freq_range has no in-band phase to measure: its
    # in-band cross-spectrum is window leakage, which can fit a linear phase and a delay.
    # The fraction is read from the detrended segment spectra the phase slope uses, so a DC
    # offset or slow drift does not fill the denominator; a contact with no power in any
    # segment has no fraction and fails the gate.
    seg_power = np.mean(np.abs(Z) ** 2, axis=-1)  # (n_channels, n_freqs)
    with np.errstate(invalid="ignore", divide="ignore"):
        band_fraction = seg_power[:, mask].sum(axis=1) / seg_power.sum(axis=1)
    out_of_band_contacts = [c for c in range(n_channels) if c not in flat_contacts
                            and not band_fraction[c] >= min_band_power_fraction]
    phase_failed_pairs: List[int] = []

    for i in range(n_channels - 1):
        if i in flat_contacts or i + 1 in flat_contacts:
            adj_wpli[i] = adj_r2[i] = adj_delays[i] = np.nan
            continue
        # S_{i, i+1, k} = conj(Z[i]) * Z[i+1]
        Sxy = np.conj(Z[i]) * Z[i + 1]  # (n_freqs, n_segments)
        w_f, _ = _wpli_from_cross_spectra(Sxy)
        adj_wpli[i] = float(np.mean(w_f[mask]))

        # Phase slope from average cross-spectrum across segments
        Sxy_mean = np.mean(Sxy, axis=1)
        phi = np.unwrap(np.angle(Sxy_mean[mask]))
        res = stats.linregress(f_band, phi)
        r2 = float(res.rvalue ** 2) if np.isfinite(res.rvalue) else 0.0
        adj_r2[i] = r2

        slope = float(res.slope)
        tau = -slope / (2.0 * np.pi)
        adj_delays[i] = tau

        phase_ok = r2 >= min_linearity_r2 and abs(tau) < max_tau_unambiguous
        if not phase_ok:
            phase_failed_pairs.append(i)
        if (phase_ok and adj_wpli[i] >= min_wpli
                and i not in out_of_band_contacts and i + 1 not in out_of_band_contacts):
            adj_identifiable[i] = True

    mean_wpli_val = float(np.mean(adj_wpli))

    # Monte Carlo surrogate null test. Each surrogate's pair wPLI values also form each
    # pair's own null, so one set of draws tests the mean and every pair. The pair test runs
    # before the depth fit: a contact independent of the others still fits a linear phase
    # (R^2 0.7 from 5 in-band bins) and a pair wPLI near 0.15 often enough that the coupled
    # pairs carried the mean past its test, and the depth fit took the outlier.
    p_val = float("nan")
    pair_p = np.full(n_channels - 1, np.nan)
    # A pair with a flat contact has no wPLI to test, and the mean over pairs is then NaN, so
    # neither draws a null; every other pair still draws its own.
    tested_pairs = [i for i in range(n_channels - 1)
                    if i not in flat_contacts and i + 1 not in flat_contacts]
    surrogates_run = n_surrogates > 0 and bool(tested_pairs)
    if surrogates_run:
        exceed_count = 0
        pair_exceed = np.zeros(n_channels - 1, dtype=int)
        for _ in range(n_surrogates):
            surr_lfp = _surrogate_phase_randomize(lfp, gen)
            _, _, Z_surr = signal.stft(
                surr_lfp, fs=fs, nperseg=nperseg, noverlap=noverlap, boundary=None, padded=False,
                axis=-1, detrend="linear",
            )
            surr_adj_wpli = np.zeros(n_channels - 1, dtype=float)
            for i in tested_pairs:
                w_s, _ = _wpli_from_cross_spectra(np.conj(Z_surr[i]) * Z_surr[i + 1])
                surr_adj_wpli[i] = float(np.mean(w_s[mask]))
                pair_exceed[i] += _count_at_least_as_extreme(
                    [surr_adj_wpli[i]], adj_wpli[i], "greater"
                )
            exceed_count += _count_at_least_as_extreme(
                [np.mean(surr_adj_wpli)], mean_wpli_val, "greater"
            )
        if not flat_contacts:
            p_val = float((1 + exceed_count) / (1 + n_surrogates))
        pair_p[tested_pairs] = (1 + pair_exceed[tested_pairs]) / (1 + n_surrogates)
    uncoupled_pairs = [(i, i + 1) for i in range(n_channels - 1) if pair_p[i] > alpha]
    # No pair is identifiable without its null: a pair whose surrogates were not drawn
    # (n_surrogates=0, or a flat contact in the pair) has a NaN p and fails.
    adj_identifiable &= pair_p <= alpha

    # Every adjacent pair must be identifiable. The cumulative delay sums all pairs, so a
    # non-identifiable pair's delay would enter the spatial fit: one incoherent contact
    # biased 12-contact estimates by ~16%, and on 3 contacts a single identifiable pair
    # was accepted with the wrong sign.
    delay_identifiable = bool(np.all(adj_identifiable))
    depth_fit_reason: Optional[str] = None

    if delay_identifiable:
        # Cumulative phase delay along the array
        cum_delay = np.zeros(n_channels, dtype=float)
        cum_delay[1:] = np.cumsum(adj_delays)
        coords = np.arange(n_channels, dtype=float)
        reg_spatial = stats.linregress(coords, cum_delay)
        tau_per_channel = float(reg_spatial.slope)
        spatial_r2 = float(reg_spatial.rvalue ** 2) if np.isfinite(reg_spatial.rvalue) else 0.0

        if spatial_r2 < 0.50:
            depth_fit_reason = (f"Cumulative delay not linear in contact index "
                                f"(R^2 = {spatial_r2:.4f} < 0.5)")
            delay_identifiable = False
            tau_per_channel = float("nan")
            apparent_velocity = None
            directionality = "unidentifiable"
        else:
            # tau_per_channel > 0: the lower-index contact leads, so the wave runs in row
            # order, which is the anatomical direction the caller named for row order. A
            # gradient within round-off of zero, relative to the largest delay the fit can
            # represent, has no sign and no velocity. No input is known to reach this: a pair
            # whose phase lag is below the wPLI zero-lag tolerance has wPLI 0 and fails its
            # pair test first, so the branch is a backstop against a zero division.
            zero_width = 8.0 * np.finfo(float).eps * max_tau_unambiguous
            if abs(tau_per_channel) > zero_width:
                row_order_leads = tau_per_channel > 0
                if orientation == "superficial_to_deep":
                    directionality = ("superficial_to_deep" if row_order_leads
                                      else "deep_to_superficial")
                else:
                    directionality = ("deep_to_superficial" if row_order_leads
                                      else "superficial_to_deep")
            else:
                depth_fit_reason = "Delay gradient across contacts is zero to round-off"
                delay_identifiable = False
                tau_per_channel = float("nan")
                directionality = "unidentifiable"

            if pitch_um is not None and np.isfinite(tau_per_channel):
                pitch_m = float(pitch_um) * 1e-6
                apparent_velocity = float(abs(pitch_m / tau_per_channel))
            else:
                apparent_velocity = None
    else:
        tau_per_channel = float("nan")
        apparent_velocity = None
        directionality = "unidentifiable"

    # No test performed means no inferential acceptance.
    is_sig = bool(np.isfinite(p_val) and p_val <= alpha)
    has_coupling = (mean_wpli_val >= min_wpli)
    accepted = bool(is_sig and has_coupling and delay_identifiable)

    reasons: List[str] = []
    if flat_contacts:
        if constant_contacts:
            reasons.append(f"Contact(s) {constant_contacts} constant: adjacent wPLI and delay "
                           "undefined, mean wPLI not tested")
        if ramp_contacts:
            reasons.append(f"Contact(s) {ramp_contacts} linear in time to round-off: adjacent "
                           "wPLI and delay undefined, mean wPLI not tested")
    elif n_surrogates == 0:
        reasons.append("Surrogate test not performed (n_surrogates=0): surrogates are needed "
                       "to establish a delay, so no adjacent pair is identifiable")
    elif not is_sig:
        reasons.append(f"Non-significant coupling vs phase surrogates (p = {p_val:.4f} > {alpha})")
    if not has_coupling and not flat_contacts:
        reasons.append(f"Mean adjacent wPLI ({mean_wpli_val:.4f}) below min_wpli ({min_wpli:.4f})")
    weak_pairs = [(i, i + 1) for i in range(n_channels - 1) if adj_wpli[i] < min_wpli]
    if weak_pairs:
        reasons.append(f"Adjacent pair(s) {weak_pairs} wPLI below min_wpli ({min_wpli:.4f}): "
                       "delay not identified")
    if uncoupled_pairs:
        reasons.append(f"Adjacent pair(s) {uncoupled_pairs} wPLI not significant against "
                       f"its own phase surrogates (p > {alpha}): delay not identified")
    if out_of_band_contacts:
        reasons.append(f"Contact(s) {out_of_band_contacts} carry less than "
                       f"{min_band_power_fraction:.4f} of their power inside freq_range "
                       f"{freq_range}: delay not identified")
    if phase_failed_pairs:
        reasons.append("Phase-frequency relation failed linear identifiability gate")
    if depth_fit_reason is not None:
        reasons.append(depth_fit_reason)

    rejection_reason = "; ".join(reasons) if not accepted else None

    # Replace non-identifiable individual adjacent delays with NaN
    cleaned_delays = adj_delays.copy()
    cleaned_delays[~adj_identifiable] = np.nan

    return ZFlipResult(
        adjacent_wpli=adj_wpli,
        adjacent_delays_s=cleaned_delays,
        adjacent_linearity_r2=adj_r2,
        adjacent_identifiable=adj_identifiable,
        mean_wpli=mean_wpli_val,
        apparent_velocity_m_s=apparent_velocity,
        tau_per_channel_s=tau_per_channel,
        directionality=directionality,
        delay_identifiable=delay_identifiable,
        p_value=p_val,
        accepted=accepted,
        rejection_reason=rejection_reason,
        n_channels=n_channels,
        pitch_um=pitch_um,
        orientation=orientation,
        surrogate_seed_entropy=seed_entropy if surrogates_run else None,
    )
