"""
analyzers.py — Four Canonical Analyzer Objects

Changes vs. previous version:
  - Unified 7-band BANDS table (was 5; matches viz.py canonical bands)
  - TFRAnalyzer.compare_conditions: vectorized ttest_ind (no per-location Python loop)
  - TFRAnalyzer.average_across_channels: hard error on channel-count mismatch (was silent wrong)
  - UnitAnalyzer._acg_pearson: vectorized via np.searchsorted (O(N log N), was O(N²))
  - UnitAnalyzer.quality_metrics: np.histogram Fano factor (was Python window loop)
  - All public method signatures preserved.
"""

import logging
import warnings
from typing import Optional, Dict, List, Tuple
import numpy as np
from ._backend import CPU, CUDA, resolve_device, torch_cuda_available, warn_device_fallback
from ._bins import bins_within, whole_bin_count
from .gpu_pca import pin_component_signs
import pandas as pd
from scipy import signal, stats
import matplotlib.pyplot as plt

from .statistics import StatisticalAnalysis
from .spectral import CANONICAL_BANDS

log = logging.getLogger(__name__)


class TFRAnalyzer:
    """
    Time-Frequency Representation Analysis.

    Methods:
    - trial_average(tfr_data, epochs) → TFR averaged by condition
    - compare_conditions(tfr1, tfr2) → Compare two conditions with stats
    - extract_band(tfr_data, band, freqs, freq_axis=1) → Extract frequency band
    - by_layer(tfr_data, layer_bounds) → Spectrolaminar analysis
    - correlate_areas(tfr1, tfr2, freqs, band) → Inter-area correlation
    """

    # Authoritative band table: CANONICAL_BANDS consolidated with delta and broadband.
    BANDS = {
        'delta':      (1.0,   4.0),
        **CANONICAL_BANDS,
        'broadband':  (1.0, 150.0),
    }

    # Historical 7-band table preserved explicitly by name for legacy comparisons.
    LEGACY_VIZ_BANDS = {
        'delta':      (1.0,   4.0),
        'theta':      (4.0,   8.0),
        'alpha':      (8.0,  15.0),
        'beta':       (15.0,  30.0),
        'low_gamma':  (30.0,  60.0),
        'high_gamma': (60.0, 120.0),
        'broadband':  (1.0,  150.0),
    }

    @staticmethod
    def extract_band(
        tfr_data: np.ndarray,
        band: str,
        freqs: np.ndarray,
        freq_axis: int = 1,
        band_defs: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> np.ndarray:
        """
        Extract frequency band from TFR using explicit frequency coordinates.

        Args:
            tfr_data: TFR array with a frequency axis.
            band: Band name from BANDS dict (e.g. 'alpha', 'theta').
            freqs: 1D array of sampled frequency coordinates (Hz). Must match
                tfr_data.shape[freq_axis], be finite, and strictly increasing.
            freq_axis: Axis index for frequency dimension (default 1).
            band_defs: Optional custom band dictionary mapping band name to (f_min, f_max).
                Defaults to TFRAnalyzer.BANDS.

        Returns:
            Extracted band power array with frequency dimension reduced via mean.

        Raises:
            ValueError: If band is unknown, freqs is invalid (not 1D, length mismatch,
                non-finite, not strictly increasing), or if no sampled frequencies
                fall within the requested band.
        """
        bands_table = band_defs or TFRAnalyzer.BANDS
        if band not in bands_table:
            raise ValueError(f"Unknown band '{band}'. Valid: {list(bands_table.keys())}")

        f_min, f_max = bands_table[band]

        freqs_arr = np.asarray(freqs)
        if freqs_arr.ndim != 1:
            raise ValueError(f"freqs must be a 1D array, got shape {freqs_arr.shape}")

        n_freq_bins = tfr_data.shape[freq_axis]
        if len(freqs_arr) != n_freq_bins:
            raise ValueError(
                f"freqs length ({len(freqs_arr)}) must match tfr_data.shape[{freq_axis}] ({n_freq_bins})"
            )

        if not np.all(np.isfinite(freqs_arr)):
            raise ValueError("freqs must contain only finite values (no NaN or Inf)")

        if len(freqs_arr) > 1 and not np.all(np.diff(freqs_arr) > 0):
            raise ValueError("freqs must be strictly increasing")

        band_mask = (freqs_arr >= f_min) & (freqs_arr <= f_max)
        idx = np.where(band_mask)[0]
        if len(idx) == 0:
            raise ValueError(
                f"No sampled frequencies fall within requested band '{band}' ({f_min}-{f_max} Hz). "
                f"Available frequency range: [{freqs_arr[0]:.2f}, {freqs_arr[-1]:.2f}] Hz."
            )

        return np.take(tfr_data, idx, axis=freq_axis).mean(axis=freq_axis)

    @staticmethod
    def average_across_channels(band_power: np.ndarray,
                                layer_mask: Optional[Dict] = None) -> np.ndarray:
        """
        Average power across channels with optional layer preservation.

        Args:
            band_power: (channels, ...) array — any trailing dimensions
            layer_mask: Optional dict with 'superficial_mask' and 'deep_mask'
                        boolean arrays whose length must equal band_power.shape[0].

        Returns:
            Global average (shape: band_power.shape[1:]) if no layer_mask.
            Layer-stacked (shape: (2, *band_power.shape[1:])) if layer_mask given.

        Raises:
            ValueError: if layer_mask is provided but mask lengths mismatch channels.
        """
        if layer_mask is None:
            return band_power.mean(axis=0)

        n_channels = band_power.shape[0]
        sup_mask = np.asarray(layer_mask.get('superficial_mask', []), dtype=bool)
        deep_mask = np.asarray(layer_mask.get('deep_mask', []), dtype=bool)

        if len(sup_mask) != n_channels or len(deep_mask) != n_channels:
            raise ValueError(
                f"layer_mask length mismatch: band_power has {n_channels} channels, "
                f"but superficial_mask has {len(sup_mask)} and deep_mask has {len(deep_mask)}"
            )

        sup_avg = band_power[sup_mask].mean(axis=0) if sup_mask.any() \
                  else np.full(band_power.shape[1:], np.nan, dtype=band_power.dtype)
        deep_avg = band_power[deep_mask].mean(axis=0) if deep_mask.any() \
                   else np.full(band_power.shape[1:], np.nan, dtype=band_power.dtype)

        return np.stack([sup_avg, deep_avg], axis=0)

    @staticmethod
    def trial_average(tfr_data: np.ndarray, epochs: pd.DataFrame = None) -> Dict:
        """
        Trial-average TFR power.

        Args:
            tfr_data: TFR array (channels × freq × time × trials)
            epochs: Optional DataFrame with trial information (unused; kept for API compat)

        Returns:
            {'mean', 'std', 'sem', 'n_trials'}
        """
        mean_tfr = np.mean(tfr_data, axis=-1)
        std_tfr  = np.std(tfr_data, axis=-1, ddof=1)
        sem_tfr  = std_tfr / np.sqrt(tfr_data.shape[-1])

        return {
            'mean':     mean_tfr,
            'std':      std_tfr,
            'sem':      sem_tfr,
            'n_trials': tfr_data.shape[-1],
        }

    @staticmethod
    def compare_conditions(tfr1: np.ndarray, tfr2: np.ndarray) -> Dict:
        """
        Compare power between two conditions with statistics.

        Vectorized: runs ttest_ind across all (ch × freq × time) locations at once
        instead of a Python loop, ≈ 100× faster for large arrays.

        Args:
            tfr1: TFR from condition 1 (ch × freq × time × trials1)
            tfr2: TFR from condition 2 (ch × freq × time × trials2)

        Returns:
            Dict with mean_diff, n_significant, fraction_significant
        """
        if tfr1.shape[:-1] != tfr2.shape[:-1]:
            raise ValueError("TFR spatial shapes must match (ch × freq × time)")

        # Flatten spatial dims: (space, trials)
        t1 = tfr1.reshape(-1, tfr1.shape[-1])
        t2 = tfr2.reshape(-1, tfr2.shape[-1])

        # Vectorized independent t-test across all locations simultaneously
        t_stat, p_val = stats.ttest_ind(t1, t2, axis=1)

        n_sig = int((p_val < 0.05).sum())
        n_total = len(p_val)

        return {
            'n_tests':             n_total,
            'n_significant':       n_sig,
            'fraction_significant': n_sig / n_total if n_total > 0 else 0.0,
            'mean_diff':           float(np.mean(tfr1) - np.mean(tfr2)),
            'p_values':            p_val,          # (space,) array
            't_statistics':        t_stat,
            'summary': f"{n_sig} / {n_total} locations p < 0.05",
        }

    @staticmethod
    def by_layer(tfr_data: np.ndarray, layer_bounds: Dict) -> Dict:
        """
        Spectrolaminar analysis: power by cortical layer.

        Args:
            tfr_data: TFR array (channels × freq × time × trials)
            layer_bounds: {'superficial': (start_ch, end_ch), 'deep': (start_ch, end_ch)}
                          OR {'superficial_mask': bool_array, 'deep_mask': bool_array}

        Returns:
            Dict {layer_name: trial_average_dict}
        """
        results = {}
        for layer_name, bounds in layer_bounds.items():
            if isinstance(bounds, tuple) and len(bounds) == 2:
                start_ch, end_ch = int(bounds[0]), int(bounds[1])
                layer_data = tfr_data[start_ch:end_ch]
            else:
                # Boolean mask
                mask = np.asarray(bounds, dtype=bool)
                layer_data = tfr_data[mask]
            results[layer_name] = TFRAnalyzer.trial_average(layer_data)
        return results

    @staticmethod
    def correlate_areas(
        tfr1: np.ndarray,
        tfr2: np.ndarray,
        freqs: np.ndarray,
        band: str = 'alpha',
        freq_axis: int = 1,
        band_defs: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> Dict:
        """
        Inter-area TFR correlation (Pearson r + Spearman rho via StatisticalAnalysis).

        Args:
            tfr1: TFR from area 1 (ch x freq x time x trials)
            tfr2: TFR from area 2
            freqs: 1D array of frequency coordinates matching frequency axis
            band: Frequency band name (default 'alpha')
            freq_axis: Frequency dimension axis (default 1)
            band_defs: Optional custom band dictionary

        Returns:
            Dict with correlation results and interpretation
        """
        band1 = TFRAnalyzer.extract_band(tfr1, band, freqs=freqs, freq_axis=freq_axis, band_defs=band_defs)
        band2 = TFRAnalyzer.extract_band(tfr2, band, freqs=freqs, freq_axis=freq_axis, band_defs=band_defs)

        data1 = np.mean(band1, axis=(0, 1))  # (trials,)
        data2 = np.mean(band2, axis=(0, 1))

        return {
            'band':           band,
            'correlation':    StatisticalAnalysis.exploratory_correlate(data1, data2),
            'interpretation': 'Higher = stronger inter-area synchrony in this band',
        }


class UnitAnalyzer:
    """
    Single-Unit Spike Analysis.

    Methods:
    - raster(spike_times, epochs) → Raster plot data
    - psth(spike_times, epochs, bin_size) → PSTH with CI
    - autocorrelogram(spike_times, max_lag) → ACG
    - quality_metrics(spike_times, amplitudes) → Quality scores
    - firing_rate(spike_times, window) → FR over time
    """

    @staticmethod
    def raster(spike_times: np.ndarray, trial_onsets: np.ndarray,
               window_ms: Tuple[float, float] = (-1000, 2000)) -> Dict:
        """
        Prepare spike raster aligned to trial onsets.

        Args:
            spike_times: Spike times in seconds
            trial_onsets: Trial start times in seconds
            window_ms: (pre_ms, post_ms) relative to onset

        Returns:
            Dict with raster data for plotting
        """
        win_sec = (window_ms[0] / 1000, window_ms[1] / 1000)
        raster_data = []
        for trial_idx, onset in enumerate(trial_onsets):
            mask = ((spike_times >= onset + win_sec[0]) &
                    (spike_times <= onset + win_sec[1]))
            raster_data.append({
                'trial':       trial_idx,
                'spike_times': spike_times[mask] - onset,
            })

        return {
            'raster':   raster_data,
            'n_trials': len(trial_onsets),
            'n_spikes': int(sum(len(r['spike_times']) for r in raster_data)),
            'window_ms': window_ms,
        }

    @staticmethod
    def psth(spike_times: np.ndarray, trial_onsets: np.ndarray,
             bin_size_ms: float = 10,
             window_ms: Tuple[float, float] = (-1000, 2000)) -> Dict:
        """
        Peristimulus time histogram with bootstrap CI.

        Distinct from :func:`jnwb.viz.raster_psth`, which is not a redundant duplicate but a
        different contract: that function uses ``ddof=1`` SEM vs. this method's bootstrap CI,
        right-open ms bins (``<``) there vs. seconds/inclusive (``<=``) here, and a plain-tuple
        return there vs. this method's dict contract. Prefer this method when you want a
        bootstrap CI or the dict contract (e.g. alongside :meth:`UnitAnalyzer.raster`); prefer
        ``jnwb.viz.raster_psth`` for a quick trial-averaged rate curve as a plain tuple. Both
        are retained deliberately.

        Args:
            spike_times: Spike times in seconds
            trial_onsets: Trial start times in seconds
            bin_size_ms: Bin size in milliseconds
            window_ms: (pre_ms, post_ms) relative to onset. Its span must be a whole number
                of ``bin_size_ms`` bins.

        Returns:
            Dict with PSTH, CI, and statistics

        Raises:
            ValueError: If the span of ``window_ms`` is not a whole multiple of
                ``bin_size_ms``; the message names the nearest valid windows.
        """
        n_bins   = whole_bin_count(window_ms, bin_size_ms, "UnitAnalyzer.psth", "window_ms")
        win_sec  = (window_ms[0] / 1000, window_ms[1] / 1000)
        bin_sec  = bin_size_ms / 1000
        bin_edges = np.linspace(win_sec[0], win_sec[1], n_bins + 1)

        trial_psths = []
        for onset in trial_onsets:
            mask = ((spike_times >= onset + win_sec[0]) &
                    (spike_times <= onset + win_sec[1]))
            psth_trial, _ = np.histogram(spike_times[mask] - onset, bins=bin_edges)
            trial_psths.append(psth_trial / bin_sec)

        trial_psths = np.array(trial_psths)
        mean_psth = np.mean(trial_psths, axis=0)
        sem_psth  = stats.sem(trial_psths, axis=0)

        return {
            'psth':          mean_psth,
            'sem':           sem_psth,
            'bin_centers':   (bin_edges[:-1] + bin_edges[1:]) / 2,
            'bin_size_ms':   bin_size_ms,
            'n_trials':      len(trial_onsets),
            'bootstrap_ci':  StatisticalAnalysis.bootstrap_ci(np.mean(trial_psths, axis=1)),
        }

    @staticmethod
    def autocorrelogram(spike_times: np.ndarray, max_lag_ms: float = 100,
                        bin_size_ms: float = 1, device: str = 'cpu') -> Dict:
        """
        Autocorrelogram of one spike train.

        Bins are ``bin_size_ms`` wide and centred on multiples of it. With ``n`` the number
        of whole bins in ``max_lag_ms``, the histogram spans ``±(n + 1/2) * bin_size_ms``,
        and ``acg`` holds the ``n`` positive-lag bins centred on ``lag_times_ms``,
        ``bin_size_ms * (1, ..., n)``.

        The refractory test this returned is withdrawn: it took the Poisson upper tail of
        the bin covering about 5.5 to 6.5 ms (centre about 6 ms), so an over-filled
        refractory bin read as a single unit and a clean one did not. Its keys ``refractory_period_violation``, ``refr_count`` and
        ``baseline_count`` are ``NaN`` and ``is_single_unit`` is ``None``, with a
        ``FutureWarning``; they are removed in 0.2.7. The single-unit check is
        :meth:`quality_metrics`, from inter-spike intervals under 2 ms.

        Args:
            spike_times: Spike times in seconds
            max_lag_ms: Maximum lag in ms
            bin_size_ms: Bin size in ms
            device: 'cpu' or 'cuda' (GPU acceleration via CuPy)

        Returns:
            Dict with ``acg``, ``lag_times_ms``, ``device_used`` (the device that computed
            the histogram) and the four withdrawn keys above.
        """
        resolved = resolve_device(device, context='UnitAnalyzer.autocorrelogram', prefer='cupy')
        if len(spike_times) < 10:
            return {'error': 'Insufficient spikes for ACG', 'n_spikes': len(spike_times)}

        max_lag_sec = max_lag_ms / 1000
        bin_sec     = bin_size_ms / 1000

        ran_on = []
        acg, lag_times = UnitAnalyzer._acg_vectorized(
            spike_times, max_lag_sec, bin_sec, device=resolved,
            context='UnitAnalyzer.autocorrelogram', ran_on=ran_on)

        if len(acg) == 0:
            return {'error': 'ACG computation failed'}

        warnings.warn(
            "UnitAnalyzer.autocorrelogram: the refractory test is withdrawn because it was "
            "inverted (an over-filled refractory bin read as a single unit). "
            "'refractory_period_violation', 'refr_count' and 'baseline_count' are NaN and "
            "'is_single_unit' is None; these keys are removed in 0.2.7. Use "
            "UnitAnalyzer.quality_metrics (ISI < 2 ms) as the single-unit check.",
            FutureWarning,
            stacklevel=2,
        )
        return {
            'acg':                        acg,
            'lag_times_ms':               lag_times * 1000,
            'refractory_period_violation': float('nan'),
            'is_single_unit':             None,
            'refr_count':                 float('nan'),
            'baseline_count':             float('nan'),
            'device_used':                ran_on[0],
        }

    # Pairs held on the device at once. 4.19e6 float64 differences is 32 MiB, which
    # bounds the peak allocation whatever the firing rate: the chunk width is chosen
    # from the widest window actually present, not from a fixed spike count.
    _ACG_PAIR_BUDGET = 1 << 22

    @staticmethod
    def _acg_histogram(xp, spike_times, bin_edges):
        """Sum the in-window difference histogram, one histogram per chunk.

        The same source runs under ``numpy`` and ``cupy``. Each spike contributes the
        ragged window of spikes whose difference from it lies within the outer edges of
        ``bin_edges``, so the search window and the histogram cannot disagree; flattening the whole chunk's windows into one
        index array turns "a histogram per spike" into "a histogram per chunk".

        Both previous paths were pathological in different ways. The CPU loop
        called :func:`numpy.histogram` once per spike, which is 41x to 46x slower than
        this for the same counts. The CUDA path below 30000 spikes built the full
        ``N x N`` difference matrix -- 6.71 GiB of device memory at 29999 spikes, just
        under the threshold the code treated as safe -- and above 30000 it chunked but
        then looped in Python inside the chunk, launching one ``cupy.histogram`` per
        spike and re-uploading ``bin_edges`` every iteration. Measured at 35000 spikes:
        35001 uploads, 35000 kernel launches, 70000 forced device-to-host syncs, and
        22.4 s against 0.93 s on the CPU. The kernel launches, not the transfers, were
        76% of the accounted time.
        """
        lowest, highest = float(bin_edges[0]), float(bin_edges[-1])
        st = xp.sort(xp.asarray(spike_times))
        edges = xp.asarray(bin_edges)
        acg = xp.zeros(len(bin_edges) - 1, dtype=xp.int64)
        n = int(st.size)
        if n == 0:
            return acg

        lo_all = xp.searchsorted(st, st + lowest, side="left")
        hi_all = xp.searchsorted(st, st + highest, side="right")
        counts_all = hi_all - lo_all
        widest = int(counts_all.max())
        chunk = max(1, UnitAnalyzer._ACG_PAIR_BUDGET // max(widest, 1))

        for i in range(0, n, chunk):
            counts = counts_all[i:i + chunk]
            total = int(counts.sum())
            if total == 0:
                continue
            centre = st[i:i + chunk]
            starts = xp.cumsum(counts) - counts
            pos = xp.arange(total)
            owner = xp.searchsorted(starts, pos, side="right") - 1
            source = lo_all[i:i + chunk][owner] + (pos - starts[owner])
            hist, _ = xp.histogram(st[source] - centre[owner], bins=edges)
            acg += hist
        return acg

    @staticmethod
    def _acg_vectorized(spike_times: np.ndarray,
                        max_lag: float, bin_size: float, device: str = 'cpu',
                        context: str = 'UnitAnalyzer.acg',
                        ran_on: Optional[list] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Vectorized autocorrelogram via searchsorted — O(N log N) instead of O(N²).

        For each spike i, find all spikes j within the binned span using searchsorted,
        then histogram the differences.  Avoids the outer Python loop over all pairs.

        Bins are ``bin_size`` wide and centred on ``k * bin_size`` for
        ``k = -n, ..., n``, where ``n`` is the number of whole bins in ``max_lag``, so the
        histogram spans ``±(n + 1/2) * bin_size``. The zero-lag bin holds every spike's
        match with itself and is dropped. Returns the positive half, ``n`` counts, and
        their lags ``bin_size * (1, ..., n)``, the bin centres.

        One implementation serves both devices, so they cannot drift apart: the CPU and
        CUDA results are bit-identical.

        ``context`` names the public caller in device warnings; ``ran_on``, when given,
        receives the device that computed the histogram.
        """
        n_bins    = bins_within(max_lag, bin_size)
        bin_edges = bin_size * (np.arange(-n_bins, n_bins + 2) - 0.5)

        acg = None
        used = CPU
        if resolve_device(device, context=context, prefer='cupy') == CUDA:
            try:
                import cupy as cp
                acg = cp.asnumpy(UnitAnalyzer._acg_histogram(cp, spike_times, bin_edges))
                used = CUDA
            except Exception as e:
                warn_device_fallback(context, e)
                log.warning(f"CUDA ACG calculation failed: {e}. Falling back to CPU.")
                acg = None

        if acg is None:
            acg = UnitAnalyzer._acg_histogram(np, spike_times, bin_edges)
        if ran_on is not None:
            ran_on.append(used)

        # Positive-lag half only (the ACG is symmetric); index n_bins is the zero-lag bin.
        lag_times = bin_size * np.arange(1, n_bins + 1)
        return acg[n_bins + 1:], lag_times

    # Keep old name as alias for any existing call sites
    _acg_pearson = _acg_vectorized

    @staticmethod
    def quality_metrics(spike_times: np.ndarray, waveform_duration_us: float,
                        firing_rate: float) -> Dict:
        """
        Unit quality metrics: ISI, refractory period, Fano factor.

        Fano factor computed via np.histogram (no Python loop over 1-s windows).

        Args:
            spike_times: Spike times in seconds
            waveform_duration_us: Trough-to-peak duration (µs)
            firing_rate: Mean firing rate (Hz)

        Returns:
            Dict with quality scores
        """
        isis    = np.diff(spike_times)
        isis_ms = isis * 1000

        refr_violations    = int((isis_ms < 2).sum())
        refr_violation_pct = 100.0 * refr_violations / len(isis) if len(isis) > 0 else 0.0

        # Fano factor via histogram (vectorized)
        if len(spike_times) > 1:
            t_start, t_end = spike_times[0], spike_times[-1]
            duration = t_end - t_start
            if duration > 1.0:
                n_windows  = int(duration)          # 1-s windows
                bin_edges  = np.linspace(t_start, t_start + n_windows, n_windows + 1)
                counts, _  = np.histogram(spike_times, bins=bin_edges)
                fano_factor = float(np.var(counts) / np.mean(counts)) \
                              if np.mean(counts) > 0 else np.nan
            else:
                fano_factor = np.nan
        else:
            fano_factor = np.nan

        mean_isi = float(np.mean(isis_ms)) if len(isis_ms) > 0 else np.nan
        cv_isi   = float(np.std(isis_ms) / mean_isi) \
                   if (mean_isi > 0 and len(isis_ms) > 1) else np.nan

        return {
            'firing_rate_hz':       float(firing_rate),
            'n_spikes':             len(spike_times),
            'n_isis':               len(isis),
            'mean_isi_ms':          mean_isi,
            'cv_isi':               cv_isi,
            'refr_violations_pct':  refr_violation_pct,
            'fano_factor':          fano_factor,
            'waveform_duration_us': float(waveform_duration_us),
            'is_good_single_unit':  refr_violation_pct < 5 and
                                    (np.isnan(fano_factor) or fano_factor < 2),
        }


class PopulationAnalyzer:
    """
    Population-Level Statistics.

    Methods:
    - compare_criteria(units1, units2) → Population comparison with stats
    - distribution_by_area(units) → Population distribution
    - pie_chart_data(units, criteria) → Pie chart generation
    - network_connectivity(correlations, threshold) → Network analysis
    """

    @staticmethod
    def compare_criteria(units1: pd.DataFrame, units2: pd.DataFrame,
                         metric: str = 'firing_rate') -> Dict:
        """
        Compare two unit populations on a metric (t-test + Mann-Whitney U + Cohen's d).
        """
        data1 = pd.to_numeric(units1[metric], errors='coerce').dropna().values
        data2 = pd.to_numeric(units2[metric], errors='coerce').dropna().values

        return {
            'metric':          metric,
            'group1_size':     len(units1),
            'group2_size':     len(units2),
            'group1_n_valid':  len(data1),
            'group2_n_valid':  len(data2),
            'group1_mean':     float(np.mean(data1)) if len(data1) > 0 else np.nan,
            'group2_mean':     float(np.mean(data2)) if len(data2) > 0 else np.nan,
            'statistics':      StatisticalAnalysis.exploratory_compare(data1, data2),
        }

    @staticmethod
    def distribution_by_area(units: pd.DataFrame, metric: str = 'firing_rate') -> Dict:
        """
        Compare metric distribution across areas (ANOVA + Kruskal-Wallis + effect sizes).
        """
        areas       = units['area'].dropna().unique()
        area_groups = {
            area: pd.to_numeric(units.loc[units['area'] == area, metric],
                                errors='coerce').dropna().values
            for area in areas
        }

        per_area = {
            area: {
                'n':      len(d),
                'mean':   float(np.mean(d))   if len(d) > 0 else np.nan,
                'std':    float(np.std(d, ddof=1)) if len(d) > 1 else np.nan,
                'median': float(np.median(d)) if len(d) > 0 else np.nan,
            }
            for area, d in area_groups.items()
        }

        return {
            'metric':     metric,
            'areas':      list(areas),
            'per_area':   per_area,
            'comparison': StatisticalAnalysis.compare_multiple_groups(area_groups),
        }

    @staticmethod
    def pie_chart_data(units: pd.DataFrame, criteria: Dict = None) -> Dict:
        """
        Generate pie chart data by criteria.

        Args:
            units: Units DataFrame
            criteria: Dict of filtering criteria

        Returns:
            Dict with counts and percentages
        """
        filtered = units.copy()

        for key, value in (criteria or {}).items():
            if key not in filtered.columns:
                continue
            if isinstance(value, tuple) and len(value) == 2:
                filtered = filtered[
                    (pd.to_numeric(filtered[key], errors='coerce') >= value[0]) &
                    (pd.to_numeric(filtered[key], errors='coerce') <= value[1])
                ]
            elif isinstance(value, (list, set)):
                filtered = filtered[filtered[key].isin(value)]
            else:
                filtered = filtered[filtered[key] == value]

        found = False
        for col in ('quality_category', 'quality_label'):
            if col in filtered.columns:
                counts = filtered[col].value_counts()
                found = True
                break
        if not found:
            if 'is_stable_plus' in filtered.columns or 'stable_plus' in filtered.columns:
                sp_col = 'stable_plus' if 'stable_plus' in filtered.columns else 'is_stable_plus'
                counts = filtered[sp_col].map({True: 'Stable+', False: 'Other'}).value_counts()
            else:
                counts = pd.Series({'All': len(filtered)})

        total = int(counts.sum())
        return {
            'counts':      counts.to_dict(),
            'percentages': (100 * counts / total).round(1).to_dict() if total > 0 else {},
            'total':       total,
        }

    @staticmethod
    def network_connectivity(correlation_matrix: np.ndarray,
                             threshold: float = 0.3) -> Dict:
        """
        Analyse network connectivity from a correlation matrix.

        Args:
            correlation_matrix: Square pairwise correlation matrix
            threshold: |r| > threshold counts as a connection

        Returns:
            Dict with graph metrics (n_nodes, n_edges, density, degree distribution)
        """
        binary_adj = np.abs(correlation_matrix) > threshold
        np.fill_diagonal(binary_adj, False)

        n_nodes  = binary_adj.shape[0]
        n_edges  = int(binary_adj.sum()) // 2
        density  = 2 * n_edges / (n_nodes * (n_nodes - 1)) if n_nodes > 1 else 0.0
        degrees  = binary_adj.sum(axis=0)

        return {
            'n_nodes':              n_nodes,
            'n_edges':              n_edges,
            'density':              float(density),
            'mean_degree':          float(np.mean(degrees)),
            'degree_distribution':  degrees.tolist(),
            'threshold':            threshold,
        }

    @staticmethod
    def population_trajectory(
        X: np.ndarray,
        n_components: int = 3,
        device: str = 'cpu'
    ) -> Dict[str, np.ndarray]:
        """
        Compute population trajectories using covariance PCA (SVD on centered data).
        Supports GPU acceleration via PyTorch/CuPy or falls back to SciPy/NumPy SVD.

        .. note::
            This method computes unstandardized covariance PCA (centering only,
            ``X - mean(X)``). Units with larger spike count variances dominate
            the principal components. This contrasts with
            :func:`jnwb.compute_population_trajectory` which standardizes features
            (correlation PCA via z-scoring).

        Args:
            X: Data matrix of shape (n_time_bins, n_units)
            n_components: Number of principal components to extract
            device: 'cpu' or 'cuda' (GPU acceleration via torch or cupy)

        Returns:
            Dict containing:
                'projection': shape (n_time_bins, n_components)
                'components': shape (n_components, n_units)
                'explained_variance': shape (n_components,)
                'explained_variance_ratio': shape (n_components,)
                'device_used': 'cpu' or 'cuda' -- device that performed the SVD

            Each component's largest-magnitude loading is positive, the lowest-index one
            among loadings tied in magnitude
            (:func:`jnwb.gpu_pca.pin_component_signs`). An SVD fixes a component only up to
            sign, and cuSOLVER and LAPACK pick each component's sign independently, so
            without the pin a CUDA component and its projection could have the opposite sign
            to the CPU one.
        """
        X_mean = np.mean(X, axis=0)
        X_centered = X - X_mean
        n_samples = X.shape[0]

        device_used = CPU
        if resolve_device(device, context='population_trajectory', prefer=None) == CUDA:
            gpu_success = False
            last_exc = None
            try:
                import cupy as cp
                X_gpu = cp.asarray(X_centered)
                u, s, vt = cp.linalg.svd(X_gpu, full_matrices=False)

                u = cp.asnumpy(u)
                s = cp.asnumpy(s)
                vt = cp.asnumpy(vt)

                projection = X_centered @ vt.T[:, :n_components]
                vt, projection = pin_component_signs(vt[:n_components, :], projection[:, :n_components])
                explained_variance = (s ** 2) / (n_samples - 1)
                total_variance = np.sum(explained_variance)
                explained_variance_ratio = explained_variance / total_variance if total_variance > 0 else explained_variance

                device_used = CUDA
                gpu_success = True
                return {
                    'projection': projection[:, :n_components],
                    'components': vt[:n_components, :],
                    'explained_variance': explained_variance[:n_components],
                    'explained_variance_ratio': explained_variance_ratio[:n_components],
                    'device_used': device_used,
                }
            except Exception as e:
                last_exc = e
                log.warning(f"GPU trajectory SVD via cupy failed: {e}. Trying PyTorch...")
                try:
                    import torch
                    if torch_cuda_available():
                        X_gpu = torch.as_tensor(X_centered, device='cuda')
                        if not X_gpu.is_floating_point():
                            X_gpu = X_gpu.to(torch.float64)
                        u, s, v = torch.linalg.svd(X_gpu, full_matrices=False)

                        u = u.cpu().numpy()
                        s = s.cpu().numpy()
                        vt = v.cpu().numpy()

                        projection = X_centered @ vt.T[:, :n_components]
                        vt, projection = pin_component_signs(vt[:n_components, :], projection[:, :n_components])
                        explained_variance = (s ** 2) / (n_samples - 1)
                        total_variance = np.sum(explained_variance)
                        explained_variance_ratio = explained_variance / total_variance if total_variance > 0 else explained_variance

                        device_used = CUDA
                        gpu_success = True
                        return {
                            'projection': projection[:, :n_components],
                            'components': vt[:n_components, :],
                            'explained_variance': explained_variance[:n_components],
                            'explained_variance_ratio': explained_variance_ratio[:n_components],
                            'device_used': device_used,
                        }
                except Exception as e2:
                    last_exc = e2
                    log.warning(f"GPU trajectory SVD via PyTorch failed: {e2}. Falling back to CPU SVD.")

            if not gpu_success and last_exc is not None:
                warn_device_fallback("population_trajectory", last_exc)

        u, s, vt = np.linalg.svd(X_centered, full_matrices=False)
        projection = X_centered @ vt.T[:, :n_components]
        vt, projection = pin_component_signs(vt[:n_components, :], projection[:, :n_components])
        explained_variance = (s ** 2) / (n_samples - 1)
        total_variance = np.sum(explained_variance)
        explained_variance_ratio = explained_variance / total_variance if total_variance > 0 else explained_variance

        return {
            'projection': projection[:, :n_components],
            'components': vt[:n_components, :],
            'explained_variance': explained_variance[:n_components],
            'explained_variance_ratio': explained_variance_ratio[:n_components],
            'device_used': device_used,
        }
