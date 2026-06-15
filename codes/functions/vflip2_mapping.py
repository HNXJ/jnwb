"""vFLIP2: mask-aware, area-aware, segment-aware laminar putative estimation.

This module provides the vFLIP2 class for estimating laminar compartments
(superficial, middle, deep) from PSD/power matrix data, with support for:
- Channel validity masking (manual and automatic)
- Area/region-aware segmentation
- Bad channel detection (zig-zag PSD outliers)
- Adaptive crossover refinement
- Multi-segment fitting for mixed-area probes
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
from scipy import ndimage


@dataclass
class FlipResults:
    """Container for vFLIP2 fitting results."""

    goodnessvalue: float | None = None
    startinglowfreq: float | None = None
    endinglowfreq: float | None = None
    startinghighfreq: float | None = None
    endinghighfreq: float | None = None
    proximalchannel: int | None = None
    distalchannel: int | None = None
    lowfreqmaxchannel: int | None = None
    highfreqmaxchannel: int | None = None
    crossoverchannel: float | None = None
    omega: float | None = None
    orientation: int | None = None
    segment_startchannel: int | None = None
    segment_endchannel: int | None = None
    segment_area: str | None = None


class vFLIP2:
    """
    Vectorized FLIP (Frequency-based Laminar Identity Profile) v2.

    Mask-aware, area-aware, segment-aware laminar putative estimation
    for multi-contact probes with potential bad channels, mixed areas,
    or white matter/out-of-brain contacts.
    """

    def __init__(
        self,
        data: np.ndarray,
        intdist: float = np.nan,
        freqbinsize: float = 1.0,
        DataType: str = "psd",
        fsample: float = np.nan,
        orientation: str = "both",
        layer4Thickness: float = np.nan,
        plot_result: bool = False,
        omega_cut: float = 6.0,
        n_channels_total: int = 128,
        valid_channel_mask: np.ndarray | list | None = None,
        bad_channel_mask: np.ndarray | list | None = None,
        area_labels: np.ndarray | list | None = None,
        allow_cross_area: bool = False,
        auto_bad_channels: bool = False,
        bad_zscore_cut: float = 6.0,
        min_segment_channels: int | None = None,
        adaptive_crossover: bool = True,
        crossover_search_radius: int = 4,
        mid_width_channels: int | None = None,
        na_area_labels: tuple[str, ...] = (
            "na",
            "bad",
            "out",
            "out_of_brain",
            "white_matter",
            "wm",
        ),
    ):
        """
        Initialize vFLIP2 with mask-aware, area-aware configuration.

        Parameters
        ----------
        data : np.ndarray
            Power spectral density matrix (channels x frequencies)
        intdist : float
            Inter-contact distance in mm (default: np.nan)
        freqbinsize : float
            Frequency bin size in Hz (default: 1.0)
        DataType : str
            Type of data ('psd', 'power', 'amplitude')
        fsample : float
            Sampling frequency
        orientation : str
            Expected orientation ('superficial', 'deep', 'both')
        layer4Thickness : float
            Layer 4 thickness in mm for mid-zone estimation
        plot_result : bool
            Whether to plot fitting results
        omega_cut : float
            Minimum omega threshold for accepting fit
        n_channels_total : int
            Total number of channels in output label vector (default: 128)
        valid_channel_mask : np.ndarray | list | None
            Boolean mask for manually valid channels
        bad_channel_mask : np.ndarray | list | None
            Boolean mask for known bad/out-of-brain contacts
        area_labels : np.ndarray | list | None
            String labels for anatomical area per channel
        allow_cross_area : bool
            Allow fitting across area boundaries (default: False)
        auto_bad_channels : bool
            Enable automatic zig-zag bad channel detection
        bad_zscore_cut : float
            Z-score threshold for auto bad channel detection
        min_segment_channels : int | None
            Minimum channels required per segment (default: max(minrange+2, 8))
        adaptive_crossover : bool
            Refine crossover in neighborhood of initial estimate
        crossover_search_radius : int
            Channel radius for adaptive crossover search
        mid_width_channels : int | None
            Width of middle zone in channels (default: ~layer4 thickness)
        na_area_labels : tuple
            Labels considered invalid/unknown areas
        """
        self.powerData = np.asarray(data, dtype=float)
        self.intdist = float(intdist) if np.isfinite(intdist) else 0.05
        self.freqbinsize = float(freqbinsize)
        self.DataType = str(DataType)
        self.fsample = float(fsample) if np.isfinite(fsample) else 1000.0
        self.orientation = str(orientation)
        self.layer4 = float(layer4Thickness) if np.isfinite(layer4Thickness) else 0.4
        self.plot_result = bool(plot_result)
        self.omega_cut = float(omega_cut)

        # Spectral parameters
        self.SpectralProfile = np.array([
            [0, 4, 8, 12, 30, 50, 100],
            [0, 4, 8, 12, 30, 50, 150],
            [0, 4, 8, 12, 30, 70, 150],
            [0, 4, 8, 12, 30, 90, 150],
        ])
        self.powchange = np.array([0, 0.2, 0.3, 0.4, 0.5])
        self.freq_change_steps = 4
        self.minrange = 8
        self.step = 1
        self.layer4 = self.layer4 if np.isfinite(self.layer4) else 0.4

        # Orientation encoding
        if self.orientation == "superficial":
            self.orientation1 = 1
        elif self.orientation == "deep":
            self.orientation1 = -1
        else:
            self.orientation1 = 0

        # Initialize power matrix
        self._initialize_power_matrix()

        # Setup mask-aware, area-aware configuration
        self.n_channels_total = int(n_channels_total)
        self.allow_cross_area = bool(allow_cross_area)
        self.auto_bad_channels = bool(auto_bad_channels)
        self.bad_zscore_cut = float(bad_zscore_cut)
        self.adaptive_crossover = bool(adaptive_crossover)
        self.crossover_search_radius = int(crossover_search_radius)
        self.mid_width_channels = mid_width_channels
        self.na_area_labels = {str(x).lower() for x in na_area_labels}

        # Coerce and validate masks
        n_chan = self.nonnormpowmat.shape[0]
        self.valid_channel_mask_input = self._coerce_bool_mask(
            valid_channel_mask, n_chan, default=True
        )
        self.bad_channel_mask_input = self._coerce_bool_mask(
            bad_channel_mask, n_chan, default=False
        )
        self.area_labels = self._coerce_area_labels(area_labels, n_chan)

        # Auto-detect bad channels if requested
        self.auto_bad_channel_mask = (
            self._detect_zigzag_bad_channels(self.nonnormpowmat)
            if self.auto_bad_channels
            else np.zeros(n_chan, dtype=bool)
        )

        # Build final validity mask
        finite_mask = np.mean(np.isfinite(self.nonnormpowmat), axis=1) >= 0.95
        area_mask = np.array(
            [str(a).lower() not in self.na_area_labels for a in self.area_labels],
            dtype=bool,
        )

        self.valid_channel_mask = (
            self.valid_channel_mask_input
            & finite_mask
            & area_mask
            & ~self.bad_channel_mask_input
            & ~self.auto_bad_channel_mask
        )

        if not np.any(self.valid_channel_mask):
            raise ValueError("No valid channels after mask/area/finite filtering.")

        valid_indices = np.where(self.valid_channel_mask)[0]
        self.startrow = int(valid_indices[0])
        self.endrow = int(valid_indices[-1])

        # Build candidate segments for fitting
        self.min_segment_channels = min_segment_channels
        self.candidate_segments = self._candidate_segments()
        if len(self.candidate_segments) == 0:
            raise ValueError(
                "No clean contiguous segment is long enough for vFLIP2 fitting."
            )

        # Run fitting
        self.Results: FlipResults | None = None
        self.flip_it()

    def _coerce_bool_mask(
        self, mask: np.ndarray | list | None, n_chan: int, default: bool
    ) -> np.ndarray:
        """Coerce input to boolean mask of correct length."""
        if mask is None:
            return np.full(n_chan, bool(default), dtype=bool)
        mask_arr = np.asarray(mask, dtype=bool)
        if mask_arr.size < n_chan:
            raise ValueError(f"Mask length {mask_arr.size} < n_channels {n_chan}.")
        return mask_arr[:n_chan].copy()

    def _coerce_area_labels(
        self, area_labels: np.ndarray | list | None, n_chan: int
    ) -> np.ndarray:
        """Coerce area labels to object array of correct length."""
        if area_labels is None:
            return np.array(["unknown"] * n_chan, dtype=object)
        labels_arr = np.asarray(area_labels, dtype=object)
        if labels_arr.size < n_chan:
            raise ValueError(
                f"area_labels length {labels_arr.size} < n_channels {n_chan}."
            )
        return labels_arr[:n_chan].copy()

    def _detect_zigzag_bad_channels(self, powmat: np.ndarray) -> np.ndarray:
        """
        Conservative PSD-row outlier detector.

        Flags channels whose log-power spectrum is an isolated outlier
        relative to nearby channels. Use as QC assistance; manual masks
        remain authority for known bad/out-of-brain/white-matter contacts.
        """
        x = np.asarray(powmat, dtype=float)

        finite = np.isfinite(x)
        if not np.any(finite):
            return np.ones(x.shape[0], dtype=bool)

        floor = np.nanpercentile(x[finite], 1)
        floor = max(float(floor), 1e-12)

        with np.errstate(invalid="ignore", divide="ignore"):
            x_log = np.log10(np.maximum(x, floor))

        n_chan = x_log.shape[0]
        if n_chan < 5:
            return np.zeros(n_chan, dtype=bool)

        # Neighbor deviation score
        neighbor_score = np.zeros(n_chan, dtype=float)
        for ch in range(n_chan):
            lo = max(0, ch - 2)
            hi = min(n_chan, ch + 3)
            neighbors = [i for i in range(lo, hi) if i != ch]
            if len(neighbors) == 0:
                neighbor_score[ch] = 0
                continue
            local_median = np.nanmedian(x_log[neighbors, :], axis=0)
            neighbor_score[ch] = np.nanmedian(np.abs(x_log[ch, :] - local_median))

        # Second derivative score
        second_score = np.zeros(n_chan, dtype=float)
        second = np.abs(x_log[:-2, :] - 2 * x_log[1:-1, :] + x_log[2:, :])
        second_score[1:-1] = np.nanmedian(second, axis=1)
        second_score[0] = second_score[1]
        second_score[-1] = second_score[-2]

        score = neighbor_score + second_score
        med = np.nanmedian(score)
        mad = np.nanmedian(np.abs(score - med))

        self.zigzag_score = score
        self.zigzag_robust_z = np.zeros_like(score)

        if not np.isfinite(mad) or mad == 0:
            return np.zeros(n_chan, dtype=bool)

        robust_z = 0.6745 * (score - med) / mad
        self.zigzag_robust_z = robust_z

        return robust_z > self.bad_zscore_cut

    def _candidate_segments(self) -> list[tuple[int, int, str]]:
        """
        Return clean contiguous fit segments.

        Each segment is (start_channel, end_channel, area_label).
        Segments are split at area boundaries unless allow_cross_area=True.
        """
        segments = []
        n = len(self.valid_channel_mask)
        start = None

        for i in range(n + 1):
            ok = bool(self.valid_channel_mask[i]) if i < n else False

            if ok and start is None:
                start = i

            if (not ok) and start is not None:
                end = i - 1
                segments.extend(self._split_segment_by_area(start, end))
                start = None

        min_len = (
            int(self.min_segment_channels)
            if self.min_segment_channels is not None
            else max(self.minrange + 2, 8)
        )

        return [seg for seg in segments if (seg[1] - seg[0] + 1) >= min_len]

    def _split_segment_by_area(
        self, start: int, end: int
    ) -> list[tuple[int, int, str]]:
        """Split segment at area boundaries if needed."""
        if self.allow_cross_area:
            labels = set(str(x) for x in self.area_labels[start : end + 1])
            area = "multi" if len(labels) > 1 else str(self.area_labels[start])
            return [(int(start), int(end), area)]

        out = []
        seg_start = start
        current = str(self.area_labels[start])

        for ch in range(start + 1, end + 1):
            label = str(self.area_labels[ch])
            if label != current:
                out.append((int(seg_start), int(ch - 1), current))
                seg_start = ch
                current = label

        out.append((int(seg_start), int(end), current))
        return out

    def _initialize_power_matrix(self) -> None:
        """Initialize and normalize power matrix."""
        if self.DataType == "power":
            self.nonnormpowmat = self.powerData.copy()
        elif self.DataType == "amplitude":
            self.nonnormpowmat = self.powerData.copy() ** 2
        elif self.DataType == "psd":
            self.nonnormpowmat = self.powerData.copy()
        else:
            warnings.warn(f"Unknown DataType '{self.DataType}', assuming PSD.")
            self.nonnormpowmat = self.powerData.copy()

        self.powermat = self._normalize_power_matrix(self.nonnormpowmat)
        self.n_channels = self.powermat.shape[0]
        self.n_freqs = self.powermat.shape[1]
        self.freqaxis = np.arange(self.n_freqs) * self.freqbinsize

    def _normalize_power_matrix(
        self, powmat: np.ndarray, epsilon: float = 1e-12
    ) -> np.ndarray:
        """Z-score normalize power matrix per frequency."""
        normed = np.zeros_like(powmat)
        for f in range(powmat.shape[1]):
            col = powmat[:, f]
            finite = col[np.isfinite(col)]
            if len(finite) == 0:
                normed[:, f] = np.nan
                continue
            m = np.mean(finite)
            s = np.std(finite) + epsilon
            normed[:, f] = (col - m) / s
        return normed

    def _get_Window(
        self, proximalchannel: int, distalchannel: int
    ) -> np.ndarray:
        """Extract normalized power window between channels."""
        lo = min(proximalchannel, distalchannel)
        hi = max(proximalchannel, distalchannel)
        lo = max(lo, 0)
        hi = min(hi, self.n_channels - 1)
        return self.powermat[lo : hi + 1, :].copy()

    def _get_freqbands(
        self, S1: np.ndarray, S2: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, int]:
        """Determine frequency bands and orientation from PSD profiles."""
        euc_distance = lambda g1, g2: np.sqrt(np.nansum((g1 - g2) ** 2))

        best_diff = -np.inf
        best_orientation = 0
        best_deep_f: np.ndarray = np.array([])
        best_sup_f: np.ndarray = np.array([])

        for o in [1, -1]:
            if self.orientation1 != 0 and o != self.orientation1:
                continue

            for low_start in range(self.SpectralProfile.shape[0]):
                for low_end in range(
                    low_start + 1, self.SpectralProfile.shape[1]
                ):
                    for high_start in range(self.SpectralProfile.shape[0]):
                        for high_end in range(
                            high_start + 1, self.SpectralProfile.shape[1]
                        ):
                            l_start = self.SpectralProfile[low_start, 0]
                            l_end = self.SpectralProfile[low_start, low_end]
                            h_start = self.SpectralProfile[high_start, 3]
                            h_end = self.SpectralProfile[high_start, high_end]

                            deep_f = np.arange(l_start, l_end, self.freqbinsize)
                            sup_f = np.arange(h_start, h_end, self.freqbinsize)

                            if len(deep_f) == 0 or len(sup_f) == 0:
                                continue

                            deep_mask = np.isin(self.freqaxis, deep_f)
                            sup_mask = np.isin(self.freqaxis, sup_f)

                            if not np.any(deep_mask) or not np.any(sup_mask):
                                continue

                            deep_pow = np.nanmean(S1[deep_mask])
                            sup_pow = np.nanmean(S1[sup_mask])

                            # Euclidean distance over concatenated bands (handle different sizes)
                            g1_full = np.concatenate([S1[deep_mask], S1[sup_mask]])
                            g2_full = np.concatenate([S2[deep_mask], S2[sup_mask]])
                            band_dist = euc_distance(g1_full, g2_full)

                            diff = abs(deep_pow - sup_pow) * band_dist

                            if diff > best_diff:
                                best_diff = diff
                                best_orientation = o
                                best_deep_f = deep_f
                                best_sup_f = sup_f

        return best_deep_f, best_sup_f, best_orientation

    def _crossover_channels(
        self,
        lowband: np.ndarray,
        highband: np.ndarray,
        proximalchannel: int,
        orientation: int,
    ) -> float:
        """Find crossover point between low and high frequency bands."""
        signed = np.asarray(highband, dtype=float) - np.asarray(
            lowband, dtype=float
        )
        absdiff = np.abs(signed)

        if orientation == -1:
            search = signed
        else:
            search = -signed

        candidates = np.where(search > 0)[0]
        if len(candidates) == 0:
            return float(np.nan)

        best = candidates[np.argmin(absdiff[candidates])]
        return float(best + proximalchannel)

    def _crossover_channels_adaptive(
        self,
        lowband: np.ndarray,
        highband: np.ndarray,
        proximalchannel: int,
        orientation: int,
    ) -> float:
        """
        Refine crossover within neighborhood around initial FLIP cross.

        Preferred cross has:
        1. Small absolute high-low difference
        2. Large local slope (actual transition)
        """
        base_cross = self._crossover_channels(
            lowband, highband, proximalchannel, orientation
        )

        if np.isnan(base_cross) or not self.adaptive_crossover:
            return base_cross

        rel_base = int(round(base_cross - proximalchannel))
        signed = np.asarray(highband, dtype=float) - np.asarray(
            lowband, dtype=float
        )
        signed = ndimage.uniform_filter1d(signed, size=3, mode="nearest")

        absdiff = np.abs(signed)
        slope = np.abs(np.gradient(signed))

        n = len(signed)
        lo = max(0, rel_base - self.crossover_search_radius)
        hi = min(n - 1, rel_base + self.crossover_search_radius)
        candidates = np.arange(lo, hi + 1)

        if len(candidates) == 0:
            return base_cross

        score = -absdiff[candidates] + 0.25 * slope[candidates]
        refined_rel = int(candidates[np.nanargmax(score)])

        return float(refined_rel + proximalchannel)

    def _peak_check(
        self, psd_slice: np.ndarray, proximal: int, distal: int
    ) -> bool:
        """Check if PSD slice has valid peaks."""
        return np.any(np.isfinite(psd_slice)) and len(psd_slice) >= 2

    def _evaluate_individual_goodness(
        self, lowband: np.ndarray, highband: np.ndarray
    ) -> float:
        """Evaluate goodness of fit from low/high band profiles."""
        l_finite = lowband[np.isfinite(lowband)]
        h_finite = highband[np.isfinite(highband)]
        if len(l_finite) == 0 or len(h_finite) == 0:
            return 0.0
        return float(np.mean(h_finite) - np.mean(l_finite))

    def omega_fun(self) -> tuple[float, list]:
        """
        Main fitting function with segment-aware search.

        Searches over candidate segments rather than whole probe,
        respecting area boundaries and validity masks.
        """
        euc_distance = lambda g1, g2: np.sqrt(np.nansum((g1 - g2) ** 2))

        best_split: list[Any] = [np.nan] * 15
        best_omega = -np.inf

        for seg_start, seg_end, seg_area in self.candidate_segments:
            self._active_startrow = seg_start
            self._active_endrow = seg_end

            prox_start = seg_start
            prox_end = seg_end - self.minrange + 1

            for proximalchannel in range(prox_start, prox_end + 1, self.step):
                dist_start = proximalchannel + self.minrange
                dist_end = seg_end

                for distalchannel in range(dist_start, dist_end + 1, self.step):
                    psd_normalized = self._get_Window(
                        proximalchannel, distalchannel
                    )

                    self.minrange_s = int(
                        np.floor(abs(proximalchannel - distalchannel) / 2)
                    )
                    if self.minrange_s < 1:
                        continue

                    group1 = psd_normalized[: self.minrange_s, :]
                    group2 = psd_normalized[-self.minrange_s :, :]

                    S1_meanpow = ndimage.uniform_filter1d(
                        np.nanmean(group1, axis=0), size=5
                    )
                    S2_meanpow = ndimage.uniform_filter1d(
                        np.nanmean(group2, axis=0), size=5
                    )

                    Ps_dist = euc_distance(S1_meanpow, S2_meanpow)

                    deep_f, sup_f, orientation = self._get_freqbands(
                        S1_meanpow, S2_meanpow
                    )
                    if len(deep_f) == 0 or len(sup_f) == 0:
                        continue

                    deep_mask = np.isin(self.freqaxis, deep_f)
                    sup_mask = np.isin(self.freqaxis, sup_f)

                    lowband = np.nanmean(psd_normalized[:, deep_mask], axis=1)
                    highband = np.nanmean(psd_normalized[:, sup_mask], axis=1)

                    if np.any(~np.isfinite(lowband)) or np.any(
                        ~np.isfinite(highband)
                    ):
                        continue

                    band_dist = euc_distance(lowband, highband)
                    goodness = self._evaluate_individual_goodness(
                        lowband, highband
                    )

                    if self.orientation1 == -1 and goodness > 0:
                        goodness = 0
                    elif self.orientation1 == 1 and goodness < 0:
                        goodness = 0

                    metric = (
                        Ps_dist
                        * band_dist
                        * abs(goodness)
                        * abs(proximalchannel - distalchannel)
                        * len(deep_f)
                        * len(sup_f)
                    )

                    if metric <= 0 or not np.isfinite(metric):
                        continue

                    omega = np.log(metric)

                    highfreqmaxchannel = int(
                        np.nanargmax(highband) + proximalchannel
                    )
                    lowfreqmaxchannel = int(
                        np.nanargmax(lowband) + proximalchannel
                    )

                    crossover_point = self._crossover_channels_adaptive(
                        lowband, highband, proximalchannel, orientation
                    )

                    valid_crossover = np.isfinite(crossover_point)
                    adequate_difference = np.isfinite(omega) and omega != 0
                    check_lowpeak = self._peak_check(
                        lowband, proximalchannel, distalchannel
                    )
                    check_highpeak = self._peak_check(
                        highband, proximalchannel, distalchannel
                    )
                    check_peak_dist = (
                        abs(highfreqmaxchannel - lowfreqmaxchannel)
                        >= self.minrange
                    )

                    good_arrangement = valid_crossover and (
                        (
                            lowfreqmaxchannel < crossover_point < highfreqmaxchannel
                        )
                        or (
                            lowfreqmaxchannel > crossover_point > highfreqmaxchannel
                        )
                    )

                    non_overlap = valid_crossover and (
                        lowfreqmaxchannel != crossover_point
                        and crossover_point != highfreqmaxchannel
                        and lowfreqmaxchannel != highfreqmaxchannel
                    )

                    good_fit = (
                        adequate_difference
                        and check_lowpeak
                        and check_highpeak
                        and valid_crossover
                        and good_arrangement
                        and non_overlap
                        and check_peak_dist
                    )

                    if good_fit and omega > best_omega:
                        best_split = [
                            float(goodness),
                            float(deep_f[0]) if len(deep_f) else np.nan,
                            float(deep_f[-1]) if len(deep_f) else np.nan,
                            float(sup_f[0]) if len(sup_f) else np.nan,
                            float(sup_f[-1]) if len(sup_f) else np.nan,
                            int(proximalchannel),
                            int(distalchannel),
                            int(lowfreqmaxchannel),
                            int(highfreqmaxchannel),
                            float(crossover_point),
                            float(omega),
                            int(orientation),
                            int(seg_start),
                            int(seg_end),
                            str(seg_area),
                        ]
                        best_omega = float(omega)

        return best_omega, best_split

    def flip_it(self) -> None:
        """Run FLIP fitting and populate Results."""
        omega, split = self.omega_fun()

        if omega < self.omega_cut:
            self.Results = None
            return

        fields = [
            "goodnessvalue",
            "startinglowfreq",
            "endinglowfreq",
            "startinghighfreq",
            "endinghighfreq",
            "proximalchannel",
            "distalchannel",
            "lowfreqmaxchannel",
            "highfreqmaxchannel",
            "crossoverchannel",
            "omega",
            "orientation",
            "segment_startchannel",
            "segment_endchannel",
            "segment_area",
        ]

        result_dict: dict[str, Any] = {}
        for i, field in enumerate(fields):
            if i < len(split):
                result_dict[field] = split[i]
            else:
                result_dict[field] = None

        self.Results = FlipResults(**result_dict)

    def get_laminar_label_vector(
        self,
        n_channels_total: int | None = None,
        fill_value: str = "na",
        mid_width_channels: int | None = None,
    ) -> np.ndarray:
        """
        Return channel labels: 'sup', 'mid', 'deep', or 'na'.

        Labels assigned only inside fitted clean segment.
        Middle zone centered on adaptive crossover.
        """
        n = self.n_channels_total if n_channels_total is None else int(n_channels_total)
        labels = np.full(n, fill_value, dtype=object)

        if self.Results is None:
            return labels

        start = int(self.Results.segment_startchannel)
        end = int(self.Results.segment_endchannel)
        cross = float(self.Results.crossoverchannel)

        low_peak = float(self.Results.lowfreqmaxchannel)
        high_peak = float(self.Results.highfreqmaxchannel)

        if mid_width_channels is None:
            mid_width_channels = self.mid_width_channels

        if mid_width_channels is None:
            mid_width_channels = max(1, int(np.ceil(self.layer4 / self.intdist)))

        mid_half = max(0, int(np.floor(mid_width_channels / 2)))

        mid_start = max(start, int(np.floor(cross)) - mid_half)
        mid_end = min(end, int(np.ceil(cross)) + mid_half)

        high_is_above_cross = high_peak < cross

        for ch in range(start, end + 1):
            if ch >= len(labels):
                continue

            if ch < len(self.valid_channel_mask) and not self.valid_channel_mask[ch]:
                labels[ch] = fill_value
                continue

            if mid_start <= ch <= mid_end:
                labels[ch] = "mid"
            elif high_is_above_cross:
                labels[ch] = "sup" if ch < mid_start else "deep"
            else:
                labels[ch] = "sup" if ch > mid_end else "deep"

        return labels

    def get_laminar_labels128(self, **kwargs: Any) -> np.ndarray:
        """Return 128-channel laminar label vector."""
        return self.get_laminar_label_vector(n_channels_total=128, **kwargs)

    def get_segment_info(self) -> dict[str, Any]:
        """Return information about fitted segment."""
        if self.Results is None:
            return {"fitted": False}
        return {
            "fitted": True,
            "start": self.Results.segment_startchannel,
            "end": self.Results.segment_endchannel,
            "area": self.Results.segment_area,
            "crossover": self.Results.crossoverchannel,
            "omega": self.Results.omega,
            "n_valid_channels": int(np.sum(self.valid_channel_mask)),
            "n_candidate_segments": len(self.candidate_segments),
        }


# Legacy alias for backward compatibility
FlipFunctions = vFLIP2
