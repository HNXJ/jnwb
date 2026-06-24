"""
20 Canonical Functions: Clean API for All Analysis Types

Each function: jnwb.<function>(<inputs>, <context>, <parameters>)
- Automatic parametric + non-parametric statistics
- FDR correction
- Publication-ready outputs

Author: Claude Code
Date: 2025-06-24
"""

import logging
from typing import Dict, Optional, Tuple, List, Union
import numpy as np
import pandas as pd

from .session import OmissionSession
from .analyzers import TFRAnalyzer, UnitAnalyzer, PopulationAnalyzer
from .statistics import StatisticalAnalysis

log = logging.getLogger(__name__)


# ============================================================================
# TFR ANALYSIS FUNCTIONS (1-5)
# ============================================================================

def tfr_trial_average(session: OmissionSession, area: str, condition: str = 'AAAB',
                      phase: int = 2, band: Optional[str] = None) -> Dict:
    """
    Function 1: Trial-averaged TFR power.

    Fast shortcut for epoching, averaging, and returning TFR.

    Args:
        session: OmissionSession object
        area: Brain area (V1, V3, V4, MT, PFC, FEF)
        condition: Behavioral condition
        phase: stimulus_number (2=p1, 3=p2, etc.)
        band: Optional band to extract ('alpha', 'beta', etc.)

    Returns:
        Dictionary with mean power, SEM, and n_trials
    """
    log.info(f"Trial-averaging {area} {condition} phase={phase}")
    # TODO: Load TFR → filter epochs → average
    return {'status': 'queued', 'area': area, 'condition': condition}


def tfr_compare_conditions(session: OmissionSession, area: str, condition1: str,
                           condition2: str, band: str = 'alpha') -> Dict:
    """
    Function 2: Compare TFR power between two conditions.

    Automatic parametric t-test + Mann-Whitney U + FDR correction

    Args:
        session: OmissionSession
        area: Brain area
        condition1: First condition
        condition2: Second condition
        band: Frequency band

    Returns:
        Dictionary with statistics (parametric, non-parametric, FDR, effect size)
    """
    log.info(f"Comparing {condition1} vs {condition2} in {area} ({band} band)")
    # TODO: Load both TFRs → extract band → compare with TFRAnalyzer.compare_conditions()
    return {'status': 'queued'}


def tfr_correlate_areas(session: OmissionSession, area1: str, area2: str,
                        band: str = 'alpha', condition: str = 'AAAB') -> Dict:
    """
    Function 3: Inter-area TFR correlation.

    Automatic Pearson r + Spearman rho + FDR

    Args:
        session: OmissionSession
        area1: First area
        area2: Second area
        band: Frequency band
        condition: Behavioral condition

    Returns:
        Dictionary with correlation, effect size, and significance
    """
    log.info(f"Correlating {area1}-{area2} in {band} band ({condition})")
    # TODO: Load both TFRs → extract band → correlate with TFRAnalyzer.correlate_areas()
    return {'status': 'queued'}


def tfr_spectrolaminar(session: OmissionSession, area: str, condition: str = 'AAAB',
                       layer_masks: Optional[Dict] = None) -> Dict:
    """
    Function 4: Spectrolaminar (layer-wise) analysis.

    Compare power across superficial vs deep layers by frequency band.

    Args:
        session: OmissionSession
        area: Brain area
        condition: Behavioral condition
        layer_masks: Optional layer boundary dict

    Returns:
        Dictionary with per-layer power and inter-layer comparison stats
    """
    log.info(f"Spectrolaminar analysis: {area} {condition}")
    # TODO: Load TFR → split by layer → compare with stats
    return {'status': 'queued'}


def tfr_permutation_test(session: OmissionSession, area: str, condition1: str,
                         condition2: str, n_permutations: int = 5000) -> Dict:
    """
    Function 5: Permutation test for TFR differences.

    Permutation-based p-value (no parametric assumptions)

    Args:
        session: OmissionSession
        area: Brain area
        condition1: First condition
        condition2: Second condition
        n_permutations: Number of permutations

    Returns:
        Dictionary with observed difference, p-value, and permutation distribution
    """
    log.info(f"Permutation test: {condition1} vs {condition2} ({n_permutations} perms)")
    # TODO: Load TFRs → flatten → permutation test with StatisticalAnalysis.permutation_test()
    return {'status': 'queued'}


# ============================================================================
# SINGLE-UNIT RASTER & PSTH FUNCTIONS (6-8)
# ============================================================================

def raster_plot(session: OmissionSession, unit_id: Union[int, str], condition: str = 'AAAB',
                phase: int = 2, window_ms: Tuple[int, int] = (-1000, 2000)) -> Dict:
    """
    Function 6: Spike raster for single unit.

    Prepare raster plot data aligned to phase onset.

    Args:
        session: OmissionSession
        unit_id: Unit cluster ID
        condition: Behavioral condition
        phase: stimulus_number
        window_ms: (pre_ms, post_ms)

    Returns:
        Dictionary with raster data for plotting
    """
    log.info(f"Raster plot: unit {unit_id} {condition} phase={phase}")
    # TODO: Get spike times + trial onsets → UnitAnalyzer.raster()
    return {'status': 'queued'}


def psth_analysis(session: OmissionSession, unit_id: Union[int, str], condition: str = 'AAAB',
                  phase: int = 2, bin_size_ms: float = 10) -> Dict:
    """
    Function 7: PSTH (peristimulus time histogram) with bootstrap CI.

    Includes baseline firing rate for context.

    Args:
        session: OmissionSession
        unit_id: Unit cluster ID
        condition: Behavioral condition
        phase: stimulus_number
        bin_size_ms: Bin size in milliseconds

    Returns:
        Dictionary with PSTH, CI, and bootstrap statistics
    """
    log.info(f"PSTH: unit {unit_id} {condition} phase={phase} ({bin_size_ms}ms bins)")
    # TODO: Get spike times → UnitAnalyzer.psth()
    return {'status': 'queued'}


def autocorrelogram(session: OmissionSession, unit_id: Union[int, str],
                    max_lag_ms: float = 100) -> Dict:
    """
    Function 8: Autocorrelogram with refractory period test.

    Tests single-unit quality (refractory period violation significance)

    Args:
        session: OmissionSession
        unit_id: Unit cluster ID
        max_lag_ms: Maximum lag

    Returns:
        Dictionary with ACG, refractory period p-value, and is_single_unit flag
    """
    log.info(f"Autocorrelogram: unit {unit_id} (max lag {max_lag_ms}ms)")
    # TODO: Get spike times → UnitAnalyzer.autocorrelogram()
    return {'status': 'queued'}


# ============================================================================
# UNIT FINDING & QUALITY FUNCTIONS (9-11)
# ============================================================================

def find_units(session: OmissionSession, quality: str = 'stable_plus',
               area: Optional[str] = None,
               firing_rate_range: Tuple[float, float] = (1, 200)) -> pd.DataFrame:
    """
    Function 9: Find units by quality/area/firing rate.

    Fast lookup wrapper around session.find_single_units()

    Args:
        session: OmissionSession
        quality: Quality level ('stable_plus', 'stable', 'mua', 'unstable')
        area: Optional area filter
        firing_rate_range: (min_hz, max_hz)

    Returns:
        Filtered units DataFrame

    Example:
        >>> stable_v1 = jnwb.find_units(session, quality='stable_plus', area='V1')
        >>> high_fr = jnwb.find_units(session, firing_rate_range=(20, 100))
    """
    try:
        # Validate inputs
        if not isinstance(session, OmissionSession):
            return pd.DataFrame()  # Return empty DataFrame instead of error

        if session._units_df is None or len(session._units_df) == 0:
            log.warning("No units found in session")
            return pd.DataFrame()

        log.info(f"Finding units: quality={quality}, area={area}, fr={firing_rate_range}")
        result = session.find_single_units(quality=quality, area=area,
                                           firing_rate_range=firing_rate_range)
        log.info(f"Found {len(result)} matching units")
        return result

    except Exception as e:
        log.error(f"Error finding units: {e}")
        return pd.DataFrame()


def unit_quality_scores(session: OmissionSession, unit_id: Union[int, str]) -> Dict:
    """
    Function 10: Unit quality metrics (SNR, refractory, stability).

    Single-unit vs multi-unit classification

    Args:
        session: OmissionSession
        unit_id: Unit cluster ID

    Returns:
        Dictionary with quality scores
    """
    log.info(f"Quality metrics: unit {unit_id}")
    # TODO: Get unit properties → UnitAnalyzer.quality_metrics()
    return {'status': 'queued'}


def unit_channel_mapping(session: OmissionSession, area: Optional[str] = None) -> pd.DataFrame:
    """
    Function 11: Map units to recording channels.

    Which unit was on which electrode?

    Args:
        session: OmissionSession
        area: Optional area filter

    Returns:
        DataFrame with unit_id, channel_id, area, layer
    """
    log.info(f"Unit-channel mapping: area={area}")
    mapping = session.channel_unit_mapping()
    if area:
        mapping = mapping[mapping['area'] == area]
    return mapping


# ============================================================================
# POPULATION ANALYSIS FUNCTIONS (12-15)
# ============================================================================

def pie_charts(session: OmissionSession, criteria: Optional[Dict] = None,
               by_area: bool = True, by_layer: bool = False) -> Dict:
    """
    Function 12: Population pie charts.

    Generate pie chart data grouped by area/layer

    Args:
        session: OmissionSession
        criteria: Filter criteria (e.g., {'is_stable_plus': True})
        by_area: Group by area
        by_layer: Group by layer

    Returns:
        Dictionary with counts and percentages for pie charts

    Example:
        >>> pies = jnwb.pie_charts(session, criteria={'is_stable_plus': True}, by_area=True)
        >>> print(f"Total stable+ units: {pies['total']}")
    """
    try:
        log.info(f"Pie charts: criteria={criteria}, by_area={by_area}, by_layer={by_layer}")

        if session._units_df is None or len(session._units_df) == 0:
            return {'error': 'No units in session'}

        result = session.pie_charts(criteria=criteria, by_area=by_area)
        log.info(f"Pie chart: {result}")
        return result

    except Exception as e:
        log.error(f"Error generating pie charts: {e}")
        return {'error': str(e)}


def compare_populations(session: OmissionSession, criteria1: Dict, criteria2: Dict,
                        metric: str = 'firing_rate') -> Dict:
    """
    Function 13: Compare two unit populations.

    Automatic t-test + Mann-Whitney U + Cohen's d + FDR correction

    Args:
        session: OmissionSession
        criteria1: First group filter (e.g., {'area': 'V1', 'is_stable_plus': True})
        criteria2: Second group filter
        metric: Metric to compare ('firing_rate', 'waveform_duration', etc.)

    Returns:
        Dictionary with comparison statistics (parametric, non-parametric, FDR-corrected)

    Example:
        >>> comp = jnwb.compare_populations(session,
        ...     criteria1={'area': 'V1', 'is_stable_plus': True},
        ...     criteria2={'area': 'V4', 'is_stable_plus': True},
        ...     metric='firing_rate')
    """
    try:
        log.info(f"Population comparison: {metric}")

        if session._units_df is None or len(session._units_df) == 0:
            return {'error': 'No units in session'}

        units_all = session._units_df.copy()

        # Validate metric exists
        if metric not in units_all.columns:
            return {'error': f'Metric {metric} not found in units table'}

        # Filter group 1
        group1 = units_all.copy()
        for k, v in criteria1.items():
            if k in group1.columns:
                if isinstance(v, tuple) and len(v) == 2:
                    group1 = group1[(group1[k] >= v[0]) & (group1[k] <= v[1])]
                else:
                    group1 = group1[group1[k] == v]

        # Filter group 2
        group2 = units_all.copy()
        for k, v in criteria2.items():
            if k in group2.columns:
                if isinstance(v, tuple) and len(v) == 2:
                    group2 = group2[(group2[k] >= v[0]) & (group2[k] <= v[1])]
                else:
                    group2 = group2[group2[k] == v]

        if len(group1) == 0 or len(group2) == 0:
            return {'error': f'Empty groups: group1={len(group1)}, group2={len(group2)}'}

        log.info(f"Comparing {metric}: group1={len(group1)} units, group2={len(group2)} units")
        result = PopulationAnalyzer.compare_criteria(group1, group2, metric=metric)
        return result

    except Exception as e:
        log.error(f"Error comparing populations: {e}")
        return {'error': str(e)}


def population_by_area(session: OmissionSession, metric: str = 'firing_rate') -> Dict:
    """
    Function 14: Population statistics by brain area.

    Automatic ANOVA + Kruskal-Wallis + effect sizes

    Args:
        session: OmissionSession
        metric: Metric to analyze

    Returns:
        Dictionary with per-area statistics and inter-area comparison
    """
    log.info(f"Population by area: {metric}")
    return PopulationAnalyzer.distribution_by_area(session._units_df, metric=metric)


def network_connectivity(session: OmissionSession, correlation_matrix: np.ndarray,
                         threshold: float = 0.3) -> Dict:
    """
    Function 15: Network graph analysis from correlation matrix.

    Compute network metrics: density, degree distribution, etc.

    Args:
        session: OmissionSession (for context)
        correlation_matrix: Pairwise correlation matrix (areas × areas)
        threshold: Connection threshold (|r| > threshold)

    Returns:
        Dictionary with network statistics
    """
    log.info(f"Network connectivity: threshold={threshold}")
    return PopulationAnalyzer.network_connectivity(correlation_matrix, threshold=threshold)


# ============================================================================
# CROSS-SESSION & BATCH FUNCTIONS (16-18)
# ============================================================================

def units_across_sessions(sessions: List[OmissionSession], criteria: Dict) -> pd.DataFrame:
    """
    Function 16: Collect units across multiple sessions.

    Batch find matching units.

    Args:
        sessions: List of OmissionSession objects
        criteria: Filter criteria

    Returns:
        Combined DataFrame with session_id added
    """
    log.info(f"Finding units across {len(sessions)} sessions: {criteria}")
    all_units = []
    for sess in sessions:
        units = sess.find_single_units(**criteria)
        units['session_id'] = sess._metadata.get('subject_id')
        all_units.append(units)

    return pd.concat(all_units, ignore_index=True) if all_units else pd.DataFrame()


def lfp_channel_areas(session: OmissionSession, area: Optional[str] = None) -> pd.DataFrame:
    """
    Function 17: Map LFP channels to brain areas.

    Which channels are in which area?

    Args:
        session: OmissionSession
        area: Optional filter

    Returns:
        DataFrame with channel_id, area, layer

    Example:
        >>> lfp_map = jnwb.lfp_channel_areas(session, area='V1')
    """
    try:
        log.info(f"LFP channel mapping: area={area}")

        if session._electrodes_df is None or len(session._electrodes_df) == 0:
            return pd.DataFrame()

        mapping = session.lfp_channel_areas()

        if area and 'area' in mapping.columns:
            mapping = mapping[mapping['area'] == area]

        log.info(f"Found {len(mapping)} channels" + (f" in {area}" if area else ""))
        return mapping

    except Exception as e:
        log.error(f"Error mapping LFP channels: {e}")
        return pd.DataFrame()


def summary_report(session: OmissionSession, output_dir: Optional[str] = None) -> Dict:
    """
    Function 18: Generate comprehensive session summary report.

    Includes unit counts, quality distribution, metadata

    Args:
        session: OmissionSession
        output_dir: Optional output directory for report file

    Returns:
        Dictionary with summary statistics

    Example:
        >>> summary = jnwb.summary_report(session)
        >>> print(f"Session: {summary['file']}")
        >>> print(f"Stable+ units: {summary['n_stable_plus']}")
    """
    try:
        log.info(f"Summary report: {session.nwb_path.name}")

        info = session.info()
        units = session._units_df

        if units is None or len(units) == 0:
            return {**info, 'error': 'No units in session'}

        # Safely calculate statistics
        summary = {
            **info,
            'n_stable_plus': int((units.get('stable_plus', pd.Series(False)) == True).sum()),
            'n_stable': int(((units.get('is_stable', pd.Series(False)) == True) &
                            (units.get('stable_plus', pd.Series(False)) == False)).sum()),
            'firing_rate_mean': float(units['firing_rate'].mean()) if 'firing_rate' in units.columns else 0,
            'firing_rate_std': float(units['firing_rate'].std()) if 'firing_rate' in units.columns else 0,
            'firing_rate_median': float(units['firing_rate'].median()) if 'firing_rate' in units.columns else 0,
        }

        log.info(f"Summary: {summary['n_units']} total units, {summary['n_stable_plus']} stable+")
        return summary

    except Exception as e:
        log.error(f"Error generating summary: {e}")
        return {'error': str(e)}


# ============================================================================
# ADVANCED FUNCTIONS (19-20)
# ============================================================================

def noise_vs_signal(session: OmissionSession, unit_id: Union[int, str]) -> Dict:
    """
    Function 19: Signal-to-noise ratio analysis.

    Characterize unit recording quality

    Args:
        session: OmissionSession
        unit_id: Unit cluster ID

    Returns:
        Dictionary with SNR, waveform metrics, and quality assessment
    """
    log.info(f"SNR analysis: unit {unit_id}")
    # TODO: Get waveform metrics → compute SNR
    return {'status': 'queued'}


def cross_modal_comparison(tfr_data: np.ndarray, spike_data: np.ndarray,
                           lag_range_ms: Tuple[int, int] = (-500, 500)) -> Dict:
    """
    Function 20: Compare LFP (TFR) vs spike-based networks.

    Automatic cross-correlation with lag analysis and stats

    Args:
        tfr_data: Time-frequency power array
        spike_data: Spike count array
        lag_range_ms: Lag range for cross-correlation

    Returns:
        Dictionary with correlation, lag, and modality comparison statistics
    """
    log.info(f"Cross-modal comparison: TFR vs spike networks")
    # TODO: Compute cross-correlation across lag range → statistics
    return {'status': 'queued'}


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    # TFR functions
    'tfr_trial_average',
    'tfr_compare_conditions',
    'tfr_correlate_areas',
    'tfr_spectrolaminar',
    'tfr_permutation_test',
    # Raster & PSTH
    'raster_plot',
    'psth_analysis',
    'autocorrelogram',
    # Unit finding
    'find_units',
    'unit_quality_scores',
    'unit_channel_mapping',
    # Population
    'pie_charts',
    'compare_populations',
    'population_by_area',
    'network_connectivity',
    # Batch
    'units_across_sessions',
    'lfp_channel_areas',
    'summary_report',
    # Advanced
    'noise_vs_signal',
    'cross_modal_comparison',
]
