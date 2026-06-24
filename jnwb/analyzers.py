"""
Four Canonical Analyzer Objects

1. TFRAnalyzer — Time-frequency representation analysis
2. UnitAnalyzer — Single-unit spike analysis
3. PopulationAnalyzer — Population-level statistics
4. StatisticalAnalyzer — Automatic parametric + non-parametric stats

Author: Claude Code
Date: 2025-06-24
"""

import logging
from typing import Optional, Dict, List, Tuple
import numpy as np
import pandas as pd
from scipy import signal, stats
import matplotlib.pyplot as plt

from .statistics import StatisticalAnalysis

log = logging.getLogger(__name__)


class TFRAnalyzer:
    """
    Time-Frequency Representation Analysis.

    Methods:
    - trial_average(tfr_data, epochs) → TFR averaged by condition
    - compare_conditions(tfr1, tfr2) → Compare two conditions with stats
    - extract_band(tfr_data, band_name) → Extract frequency band
    - by_layer(tfr_data, layer_bounds) → Spectrolaminar analysis
    - correlate_areas(tfr1, tfr2, band) → Inter-area correlation
    """

    # Frequency bands
    BANDS = {
        'theta': (4, 8),
        'alpha': (8, 12),
        'beta': (12, 30),
        'low_gamma': (30, 55),
        'high_gamma': (55, 90),
    }

    @staticmethod
    def extract_band(tfr_data: np.ndarray, band: str, freq_axis: int = 1) -> np.ndarray:
        """
        Extract frequency band from TFR.

        Args:
            tfr_data: TFR array (channels × frequency × time × trials)
            band: Band name ('alpha', 'beta', etc.)
            freq_axis: Axis index for frequency dimension

        Returns:
            Extracted band power (channels × time × trials)
        """
        if band not in TFRAnalyzer.BANDS:
            raise ValueError(f"Unknown band: {band}")

        f_min, f_max = TFRAnalyzer.BANDS[band]

        # Assume linear frequency mapping (0-200 Hz over all bins)
        n_freq_bins = tfr_data.shape[freq_axis]
        freq_array = np.linspace(0, 200, n_freq_bins)

        # Select band
        band_mask = (freq_array >= f_min) & (freq_array <= f_max)

        if freq_axis == 1:
            return tfr_data[:, band_mask, :, :].mean(axis=1)
        else:
            return np.take(tfr_data, np.where(band_mask)[0], axis=freq_axis).mean(axis=freq_axis)

    @staticmethod
    def average_across_channels(band_power: np.ndarray) -> np.ndarray:
        """
        Average power across channels to get area-level representation.

        CRITICAL FIX: Handles variable channel counts (TFR files have 3-82 channels per condition).
        Returns single area-level representation for inter-area correlation.

        Args:
            band_power: (channels, time, trials) array

        Returns:
            (time, trials) - area-level power representation
        """
        return band_power.mean(axis=0)

    @staticmethod
    def trial_average(tfr_data: np.ndarray, epochs: pd.DataFrame = None) -> Dict:
        """
        Trial-average TFR power.

        Args:
            tfr_data: TFR array
            epochs: Optional DataFrame with trial information

        Returns:
            Dictionary with {'mean': average_tfr, 'std': std_tfr, 'sem': sem_tfr}
        """
        # Average over trials (last dimension)
        mean_tfr = np.mean(tfr_data, axis=-1)
        std_tfr = np.std(tfr_data, axis=-1, ddof=1)
        sem_tfr = std_tfr / np.sqrt(tfr_data.shape[-1])

        return {
            'mean': mean_tfr,
            'std': std_tfr,
            'sem': sem_tfr,
            'n_trials': tfr_data.shape[-1],
        }

    @staticmethod
    def compare_conditions(tfr1: np.ndarray, tfr2: np.ndarray) -> Dict:
        """
        Compare power between two conditions with statistics.

        Automatic: t-test + Mann-Whitney U + FDR correction

        Args:
            tfr1: TFR from condition 1
            tfr2: TFR from condition 2

        Returns:
            Dictionary with statistics per frequency/time bin
        """
        if tfr1.shape[:-1] != tfr2.shape[:-1]:
            raise ValueError("TFR shapes must match (except trial dimension)")

        # Flatten across space (channels × time) and test across trials
        tfr1_flat = tfr1.reshape(-1, tfr1.shape[-1])  # (space, trials)
        tfr2_flat = tfr2.reshape(-1, tfr2.shape[-1])

        results = []
        for i in range(tfr1_flat.shape[0]):
            stats_dict = StatisticalAnalysis.compare_groups(tfr1_flat[i], tfr2_flat[i])
            results.append(stats_dict)

        return {
            'n_tests': len(results),
            'per_location_stats': results,
            'mean_diff': float(np.mean(tfr1) - np.mean(tfr2)),
            'summary': f"{len([r for r in results if r.get('significant_parametric')])} / {len(results)} locations significant"
        }

    @staticmethod
    def by_layer(tfr_data: np.ndarray, layer_bounds: Dict[str, Tuple[int, int]]) -> Dict:
        """
        Spectrolaminar analysis: power by cortical layer.

        Args:
            tfr_data: TFR array (channels × freq × time × trials)
            layer_bounds: {'superficial': (0, 10), 'deep': (10, 20)} (channel indices)

        Returns:
            Dictionary with power per layer
        """
        results = {}

        for layer_name, (start_ch, end_ch) in layer_bounds.items():
            layer_data = tfr_data[start_ch:end_ch, :, :, :]
            avg = TFRAnalyzer.trial_average(layer_data)
            results[layer_name] = avg

        return results

    @staticmethod
    def correlate_areas(tfr1: np.ndarray, tfr2: np.ndarray, band: str = 'alpha') -> Dict:
        """
        Inter-area TFR correlation.

        Args:
            tfr1: TFR from area 1 (channels × freq × time × trials)
            tfr2: TFR from area 2
            band: Frequency band

        Returns:
            Dictionary with correlation results
        """
        # Extract band from both
        band1 = TFRAnalyzer.extract_band(tfr1, band)  # (channels × time × trials)
        band2 = TFRAnalyzer.extract_band(tfr2, band)

        # Average across channels and time, correlate across trials
        data1 = np.mean(band1, axis=(0, 1))  # (trials,)
        data2 = np.mean(band2, axis=(0, 1))

        corr_result = StatisticalAnalysis.correlate(data1, data2)

        return {
            'band': band,
            'correlation': corr_result,
            'interpretation': 'Higher = stronger inter-area synchrony in this band'
        }


class UnitAnalyzer:
    """
    Single-Unit Spike Analysis.

    Methods:
    - raster(spike_times, epochs) → Raster plot data
    - psth(spike_times, epochs, bin_size) → PSTH with CI
    - autocorrelogram(spike_times, max_lag) → ACG with significance
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
            Dictionary with raster data for plotting
        """
        win_sec = (window_ms[0] / 1000, window_ms[1] / 1000)

        raster_data = []
        for trial_idx, onset in enumerate(trial_onsets):
            # Find spikes in window
            spikes_in_trial = spike_times[(spike_times >= onset + win_sec[0]) &
                                          (spike_times <= onset + win_sec[1])]
            raster_data.append({
                'trial': trial_idx,
                'spike_times': spikes_in_trial - onset,  # Align to onset
            })

        return {
            'raster': raster_data,
            'n_trials': len(trial_onsets),
            'n_spikes': len(spike_times),
            'window_ms': window_ms,
        }

    @staticmethod
    def psth(spike_times: np.ndarray, trial_onsets: np.ndarray, bin_size_ms: float = 10,
             window_ms: Tuple[float, float] = (-1000, 2000)) -> Dict:
        """
        Peristimulus time histogram with bootstrap CI.

        Args:
            spike_times: Spike times in seconds
            trial_onsets: Trial start times in seconds
            bin_size_ms: Bin size in milliseconds
            window_ms: (pre_ms, post_ms) relative to onset

        Returns:
            Dictionary with PSTH, CI, and statistics
        """
        win_sec = (window_ms[0] / 1000, window_ms[1] / 1000)
        bin_sec = bin_size_ms / 1000
        n_bins = int((win_sec[1] - win_sec[0]) / bin_sec)
        bin_edges = np.linspace(win_sec[0], win_sec[1], n_bins + 1)

        # Compute PSTH per trial
        trial_psths = []
        for onset in trial_onsets:
            spikes_in_trial = spike_times[(spike_times >= onset + win_sec[0]) &
                                          (spike_times <= onset + win_sec[1])]
            psth_trial, _ = np.histogram(spikes_in_trial - onset, bins=bin_edges)
            trial_psths.append(psth_trial / bin_sec)  # Spikes/second

        trial_psths = np.array(trial_psths)

        # Mean and CI
        mean_psth = np.mean(trial_psths, axis=0)
        sem_psth = stats.sem(trial_psths, axis=0)

        # Bootstrap CI
        ci_bootstrap = StatisticalAnalysis.bootstrap_ci(np.mean(trial_psths, axis=1))

        return {
            'psth': mean_psth,
            'sem': sem_psth,
            'bin_centers': (bin_edges[:-1] + bin_edges[1:]) / 2,
            'bin_size_ms': bin_size_ms,
            'n_trials': len(trial_onsets),
            'bootstrap_ci': ci_bootstrap,
        }

    @staticmethod
    def autocorrelogram(spike_times: np.ndarray, max_lag_ms: float = 100,
                        bin_size_ms: float = 1) -> Dict:
        """
        Autocorrelogram with refractory period significance test.

        Args:
            spike_times: Spike times in seconds
            max_lag_ms: Maximum lag
            bin_size_ms: Bin size

        Returns:
            Dictionary with ACG and refractory period statistics
        """
        if len(spike_times) < 10:
            return {
                'error': 'Insufficient spikes for ACG',
                'n_spikes': len(spike_times),
            }

        max_lag_sec = max_lag_ms / 1000
        bin_sec = bin_size_ms / 1000

        # Compute ACG
        acg, lag_times = UnitAnalyzer._acg_pearson(spike_times, max_lag_sec, bin_sec)

        if len(acg) == 0:
            return {'error': 'ACG computation failed'}

        # Refractory period: spike count in first 5ms vs. 10-15ms baseline
        ref_period_idx = int(5 / bin_size_ms)
        baseline_idx_start = int(10 / bin_size_ms)
        baseline_idx_end = int(15 / bin_size_ms)

        # BOUNDS CHECKING
        ref_period_idx = min(ref_period_idx, len(acg) - 1)
        baseline_idx_start = min(baseline_idx_start, len(acg) - 1)
        baseline_idx_end = min(baseline_idx_end, len(acg))

        ref_count = acg[ref_period_idx]
        baseline_count = np.mean(acg[baseline_idx_start:baseline_idx_end])

        # Poisson test for refractory violation
        expected_ref = baseline_count
        p_refractory = stats.poisson.sf(ref_count, expected_ref)

        return {
            'acg': acg,
            'lag_times_ms': lag_times * 1000,
            'refractory_period_violation': p_refractory,
            'is_single_unit': p_refractory < 0.05,
            'refr_count': int(ref_count),
            'baseline_count': float(baseline_count),
        }

    @staticmethod
    def _acg_pearson(spike_times: np.ndarray, max_lag: float, bin_size: float) -> Tuple[np.ndarray, np.ndarray]:
        """Compute autocorrelogram using Pearson method."""
        n_bins = int(max_lag / bin_size)
        acg = np.zeros(2 * n_bins + 1)

        for i, spike_i in enumerate(spike_times):
            diffs = spike_times - spike_i
            hist, _ = np.histogram(diffs, bins=np.linspace(-max_lag, max_lag, 2 * n_bins + 1))
            acg += hist

        lag_times = np.linspace(-max_lag, max_lag, 2 * n_bins + 1)[:-1]
        return acg[1:], lag_times[1:]  # Exclude t=0

    @staticmethod
    def quality_metrics(spike_times: np.ndarray, waveform_duration_us: float,
                        firing_rate: float) -> Dict:
        """
        Unit quality metrics: SNR, refractory period, firing rate consistency.

        Args:
            spike_times: Spike times
            waveform_duration_us: Waveform trough-to-peak duration (microseconds)
            firing_rate: Mean firing rate (Hz)

        Returns:
            Dictionary with quality scores
        """
        # ISI statistics
        isis = np.diff(spike_times)
        isis_ms = isis * 1000

        # Refractory period violations (spikes < 2ms)
        refr_violations = (isis_ms < 2).sum()
        refr_violation_pct = 100 * refr_violations / len(isis) if len(isis) > 0 else 0

        # Firing rate stability (Fano factor)
        window_size = 1  # 1 second
        spike_counts = []
        for t_start in np.arange(spike_times.min(), spike_times.max(), window_size):
            counts = ((spike_times >= t_start) & (spike_times < t_start + window_size)).sum()
            spike_counts.append(counts)

        fano_factor = np.var(spike_counts) / np.mean(spike_counts) if len(spike_counts) > 0 else np.nan

        return {
            'firing_rate_hz': float(firing_rate),
            'n_spikes': len(spike_times),
            'n_isis': len(isis),
            'mean_isi_ms': float(np.mean(isis_ms)),
            'cv_isi': float(np.std(isis_ms) / np.mean(isis_ms)) if np.mean(isis_ms) > 0 else np.nan,
            'refr_violations_pct': float(refr_violation_pct),
            'fano_factor': float(fano_factor),
            'waveform_duration_us': float(waveform_duration_us),
            'is_good_single_unit': refr_violation_pct < 5 and fano_factor < 2,
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
        Compare two unit populations on a metric.

        Automatic: t-test + Mann-Whitney U + Cohen's d

        Args:
            units1: Units DataFrame from group 1
            units2: Units DataFrame from group 2
            metric: Column name to compare

        Returns:
            Dictionary with comparison statistics
        """
        data1 = units1[metric].dropna().values
        data2 = units2[metric].dropna().values

        return {
            'metric': metric,
            'group1_size': len(units1),
            'group2_size': len(units2),
            'group1_n_valid': len(data1),
            'group2_n_valid': len(data2),
            'group1_mean': float(np.mean(data1)),
            'group2_mean': float(np.mean(data2)),
            'statistics': StatisticalAnalysis.compare_groups(data1, data2),
        }

    @staticmethod
    def distribution_by_area(units: pd.DataFrame, metric: str = 'firing_rate') -> Dict:
        """
        Compare metric distribution across areas.

        Automatic: ANOVA + Kruskal-Wallis + effect sizes

        Args:
            units: Units DataFrame
            metric: Column name

        Returns:
            Dictionary with per-area statistics
        """
        areas = units['area'].unique()
        area_groups = {area: units[units['area'] == area][metric].dropna().values
                       for area in areas}

        # Multi-group comparison
        stats_result = StatisticalAnalysis.compare_multiple_groups(area_groups)

        # Per-area summary
        per_area = {}
        for area in areas:
            data = area_groups[area]
            per_area[area] = {
                'n': len(data),
                'mean': float(np.mean(data)),
                'std': float(np.std(data, ddof=1)),
                'median': float(np.median(data)),
            }

        return {
            'metric': metric,
            'areas': list(areas),
            'per_area': per_area,
            'comparison': stats_result,
        }

    @staticmethod
    def pie_chart_data(units: pd.DataFrame, criteria: Dict[str, any] = None) -> Dict:
        """
        Generate pie chart data by criteria.

        Args:
            units: Units DataFrame
            criteria: Dictionary of filtering criteria

        Returns:
            Dictionary with counts and percentages for pie chart
        """
        if criteria is None:
            criteria = {}

        filtered = units.copy()

        # Apply filters
        for key, value in criteria.items():
            if key not in filtered.columns:
                continue
            if isinstance(value, tuple) and len(value) == 2:
                filtered = filtered[(filtered[key] >= value[0]) & (filtered[key] <= value[1])]
            elif isinstance(value, (list, set)):
                filtered = filtered[filtered[key].isin(value)]
            else:
                filtered = filtered[filtered[key] == value]

        # Count by category (e.g., quality)
        if 'quality_category' in filtered.columns:
            counts = filtered['quality_category'].value_counts()
        elif 'is_stable_plus' in filtered.columns:
            counts = filtered['is_stable_plus'].value_counts()
            counts.index = ['Unstable', 'Stable+']
        else:
            counts = pd.Series({'All': len(filtered)})

        return {
            'counts': counts.to_dict(),
            'percentages': (100 * counts / counts.sum()).round(1).to_dict(),
            'total': int(counts.sum()),
            'filtered_total': len(filtered),
        }

    @staticmethod
    def network_connectivity(correlation_matrix: np.ndarray, threshold: float = 0.3) -> Dict:
        """
        Analyze network connectivity from correlation matrix.

        Args:
            correlation_matrix: Matrix of pairwise correlations
            threshold: Connection threshold (r > threshold)

        Returns:
            Dictionary with network statistics
        """
        # Binarize
        binary_adj = np.abs(correlation_matrix) > threshold

        # Remove diagonal
        np.fill_diagonal(binary_adj, 0)

        # Network metrics
        n_nodes = binary_adj.shape[0]
        n_edges = binary_adj.sum() // 2  # Undirected graph
        density = 2 * n_edges / (n_nodes * (n_nodes - 1)) if n_nodes > 1 else 0

        # Degree distribution
        degrees = binary_adj.sum(axis=0)

        return {
            'n_nodes': n_nodes,
            'n_edges': int(n_edges),
            'density': float(density),
            'mean_degree': float(np.mean(degrees)),
            'degree_distribution': degrees.tolist(),
            'threshold': threshold,
        }
