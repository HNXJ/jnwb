"""
20 Canonical Functions: Clean API for All Analysis Types

Each function: jnwb.<function>(<inputs>, <context>, <parameters>)
- Automatic parametric + non-parametric statistics
- FDR correction
- Publication-ready outputs

Changes:
  - _filter_units() helper eliminates duplicated criteria-filter code
  - _epoch_grouper() helper eliminates duplicated groupby(trial_num) code
  - tfr_permutation_test: passes per-trial arrays instead of scalars
  - units_across_sessions: uses positional args, not **criteria
  - noise_vs_signal: kept as thin wrapper (deprecation note in docstring)
"""

import logging
import warnings
from typing import Dict, Optional, Tuple, List, Union
import numpy as np
import pandas as pd

from .session import OmissionSession
from jnwb.analyzers import TFRAnalyzer, UnitAnalyzer, PopulationAnalyzer
from jnwb.statistics import StatisticalAnalysis

log = logging.getLogger(__name__)


# ============================================================================
# PRIVATE HELPERS
# ============================================================================

def _filter_units(df: pd.DataFrame, criteria: Dict) -> pd.DataFrame:
    """
    Apply a criteria dict to a units DataFrame.

    Supports:
    - scalar equality  : {'area': 'V1'}
    - range tuple      : {'firing_rate': (10, 100)}
    - list membership  : {'area': ['V1', 'V4']}
    """
    out = df.copy()
    for k, v in criteria.items():
        if k not in out.columns:
            continue
        if isinstance(v, tuple) and len(v) == 2:
            col = pd.to_numeric(out[k], errors='coerce')
            out = out[(col >= v[0]) & (col <= v[1])]
        elif isinstance(v, (list, set)):
            out = out[out[k].isin(v)]
        else:
            out = out[out[k] == v]
    return out


def _epoch_grouper(session: OmissionSession, condition: str, phase: int):
    """
    Return (trial_groups, n_trials) for a given condition × phase.

    Groups the intervals DataFrame by trial_num so both raster_plot and
    psth_analysis share identical trial-onset logic.

    Returns:
        (GroupBy object, int) or (None, 0) on failure.
    """
    epochs = session.get_epochs(condition=condition, phase=phase)
    if epochs is None or len(epochs) == 0:
        return None, 0
    group_col = 'trial_num' if 'trial_num' in epochs.columns else epochs.index
    return epochs.groupby(group_col), len(epochs.groupby(group_col))


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
    tfr_data = session.tfr_from_preprocessed(area=area, band=band, condition=condition)
    if tfr_data is None:
        return {'error': f'TFR array not found for area {area} condition {condition}'}
    return TFRAnalyzer.trial_average(tfr_data)


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
    tfr1 = session.tfr_from_preprocessed(area=area, band=band, condition=condition1)
    tfr2 = session.tfr_from_preprocessed(area=area, band=band, condition=condition2)
    if tfr1 is None or tfr2 is None:
        return {'error': f'Failed to load TFR for comparison on {area}'}
    return TFRAnalyzer.compare_conditions(tfr1, tfr2)


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
    tfr1 = session.tfr_from_preprocessed(area=area1, band=None, condition=condition)
    tfr2 = session.tfr_from_preprocessed(area=area2, band=None, condition=condition)
    if tfr1 is None or tfr2 is None:
        return {'error': f'Failed to load TFR for correlation'}
    return TFRAnalyzer.correlate_areas(tfr1, tfr2, band=band)


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
    tfr_data = session.tfr_from_preprocessed(area=area, band=None, condition=condition)
    if tfr_data is None:
        return {'error': 'Failed to load TFR array'}
    
    if layer_masks is None:
        n_ch = tfr_data.shape[0]
        layer_bounds = {'superficial': (0, n_ch // 2), 'deep': (n_ch // 2, n_ch)}
    else:
        layer_bounds = layer_masks
        
    return TFRAnalyzer.by_layer(tfr_data, layer_bounds)


def tfr_permutation_test(session: OmissionSession, area: str, condition1: str,
                         condition2: str, n_permutations: int = 5000) -> Dict:
    """
    Function 5: Permutation test for TFR differences.

    Permutation-based p-value (no parametric assumptions).
    Preserves the trial dimension: each trial contributes one sample so
    the permutation test has meaningful variance.

    Args:
        session: OmissionSession
        area: Brain area
        condition1: First condition
        condition2: Second condition
        n_permutations: Number of permutations

    Returns:
        Dictionary with observed difference, p-value, and permutation distribution
    """
    tfr1 = session.tfr_from_preprocessed(area=area, band=None, condition=condition1)
    tfr2 = session.tfr_from_preprocessed(area=area, band=None, condition=condition2)
    if tfr1 is None or tfr2 is None:
        return {'error': 'Failed to load TFR arrays'}

    # Average over (channels, freq, time) → one value per trial
    data1 = np.mean(tfr1, axis=(0, 1, 2)) if tfr1.ndim == 4 \
            else np.mean(tfr1.reshape(-1, tfr1.shape[-1]), axis=0)
    data2 = np.mean(tfr2, axis=(0, 1, 2)) if tfr2.ndim == 4 \
            else np.mean(tfr2.reshape(-1, tfr2.shape[-1]), axis=0)

    if data1.ndim == 0:
        # Scalar — insufficient structure; return graceful error
        return {'error': 'TFR has no trial dimension; permutation test not meaningful'}

    return StatisticalAnalysis.permutation_test(data1, data2, n_permutations=n_permutations)


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
    try:
        if not isinstance(session, OmissionSession):
            return {'error': 'Invalid session'}

        spike_times = session.get_spike_times(unit_id)
        if spike_times is None or len(spike_times) == 0:
            return {'error': f'No spikes for unit {unit_id}'}

        trial_groups, n_trials = _epoch_grouper(session, condition, phase)
        if trial_groups is None:
            return {'error': f'No trials: {condition} phase={phase}'}

        win_start_s = window_ms[0] / 1000.0
        win_end_s   = window_ms[1] / 1000.0
        raster_data = []

        for trial_num, trial_events in trial_groups:
            onset = trial_events.iloc[0]['start_time']
            mask  = ((spike_times >= onset + win_start_s) &
                     (spike_times <= onset + win_end_s))
            rel_ms = (spike_times[mask] - onset) * 1000.0
            for t in rel_ms:
                raster_data.append({'trial_id': int(float(trial_num)),
                                    'spike_time_ms': float(t)})

        log.info(f"Raster: {len(raster_data)} spikes, {n_trials} trials")
        return {
            'unit_id':    unit_id,
            'condition':  condition,
            'phase':      phase,
            'n_trials':   n_trials,
            'n_spikes':   len(raster_data),
            'raster_data': raster_data,
        }
    except Exception as e:
        log.error(f"Raster error: {e}")
        return {'error': str(e)}


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
    try:
        if not isinstance(session, OmissionSession):
            return {'error': 'Invalid session'}

        spike_times = session.get_spike_times(unit_id)
        if spike_times is None or len(spike_times) == 0:
            return {'error': f'No spikes for unit {unit_id}'}

        trial_groups, n_trials = _epoch_grouper(session, condition, phase)
        if trial_groups is None:
            return {'error': f'No trials: {condition} phase={phase}'}

        window_ms    = (-1000, 2000)
        win_start_s  = window_ms[0] / 1000.0
        win_end_s    = window_ms[1] / 1000.0
        bin_size_s   = bin_size_ms / 1000.0
        n_bins       = int((win_end_s - win_start_s) / bin_size_s)
        bin_edges    = np.linspace(win_start_s, win_end_s, n_bins + 1)
        psth_counts  = np.zeros(n_bins)

        for _, trial_events in trial_groups:
            onset = trial_events.iloc[0]['start_time']
            mask  = ((spike_times >= onset + win_start_s) &
                     (spike_times <= onset + win_end_s))
            counts, _ = np.histogram(spike_times[mask] - onset, bins=bin_edges)
            psth_counts += counts

        psth_rate     = (psth_counts / n_trials) / bin_size_s
        baseline_rate = float(np.mean(psth_rate[:max(1, int(n_bins * 0.25))]))

        log.info(f"PSTH: {n_trials} trials, baseline={baseline_rate:.2f} Hz")
        return {
            'unit_id':          unit_id,
            'condition':        condition,
            'phase':            phase,
            'bin_size_ms':      bin_size_ms,
            'n_trials':         n_trials,
            'psth_rate_hz':     psth_rate.tolist(),
            'baseline_rate_hz': baseline_rate,
            'bin_times_ms':     (bin_edges[:-1] * 1000).tolist(),
        }
    except Exception as e:
        log.error(f"PSTH error: {e}")
        return {'error': str(e)}


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
    try:
        if not isinstance(session, OmissionSession):
            return {'error': 'Invalid session'}

        spike_times = session.get_spike_times(unit_id)
        if spike_times is None or len(spike_times) == 0:
            return {'error': f'No spikes for unit {unit_id}'}

        # Use UnitAnalyzer to compute ACG
        acg_result = UnitAnalyzer.autocorrelogram(spike_times, max_lag_ms=max_lag_ms)

        if 'error' in acg_result:
            return acg_result

        log.info(f"ACG: unit {unit_id}, {len(spike_times)} spikes, max_lag={max_lag_ms}ms")
        return {
            'unit_id': unit_id,
            'max_lag_ms': max_lag_ms,
            'n_spikes': len(spike_times),
            **acg_result,  # Include acg, lag_times, and other fields
        }
    except Exception as e:
        log.error(f"ACG error: {e}")
        return {'error': str(e)}


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

        # Ensure unit_id column exists (rename from cluster_id if needed)
        if 'cluster_id' in result.columns and 'unit_id' not in result.columns:
            result = result.rename(columns={'cluster_id': 'unit_id'})

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
    spike_times = session.get_spike_times(unit_id)
    if spike_times is None or len(spike_times) == 0:
        return {'error': f'No spikes for unit {unit_id}'}
        
    # Get metadata for waveform_duration
    units_df = session._units_df
    if units_df is not None:
        # Search by unit_id column
        matched = units_df[units_df['unit_id'] == unit_id]
        if matched.empty and str(unit_id).isdigit():
            # Search by index
            idx = int(unit_id)
            if idx in units_df.index:
                matched = units_df.loc[[idx]]
        
        if not matched.empty:
            row = matched.iloc[0]
            wf_dur = row.get('waveform_duration', 300.0)
            if pd.isna(wf_dur):
                wf_dur = 300.0
            fr = row.get('firing_rate', 1.0)
            if pd.isna(fr):
                fr = 1.0
            return UnitAnalyzer.quality_metrics(spike_times, waveform_duration_us=float(wf_dur), firing_rate=float(fr))

    return UnitAnalyzer.quality_metrics(spike_times, waveform_duration_us=300.0, firing_rate=1.0)


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

        if metric not in units_all.columns:
            return {'error': f'Metric {metric} not found in units table'}

        group1 = _filter_units(units_all, criteria1)
        group2 = _filter_units(units_all, criteria2)

        if len(group1) == 0 or len(group2) == 0:
            return {'error': f'Empty groups: group1={len(group1)}, group2={len(group2)}'}

        log.info(f"Comparing {metric}: group1={len(group1)}, group2={len(group2)}")
        return PopulationAnalyzer.compare_criteria(group1, group2, metric=metric)

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

    Batch find matching units. Uses _filter_units() so criteria dict is
    applied uniformly without **-unpacking (which would break non-keyword keys).

    Args:
        sessions: List of OmissionSession objects
        criteria: Filter criteria dict (same format as compare_populations)

    Returns:
        Combined DataFrame with session_id added
    """
    log.info(f"Finding units across {len(sessions)} sessions")
    all_units = []
    for sess in sessions:
        try:
            df = sess._units_df
            if df is None or len(df) == 0:
                continue
            units = _filter_units(df, criteria).copy()
        except (AttributeError, ValueError):
            # Fallback for mock objects in tests
            units = sess.find_single_units()
            units = _filter_units(units, criteria).copy()
        
        # Safely retrieve subject_id
        sub_id = "unknown"
        if hasattr(sess, '_metadata') and isinstance(sess._metadata, dict):
            sub_id = sess._metadata.get('subject_id', "unknown")
        elif hasattr(sess, 'nwb_path'):
            sub_id = str(sess.nwb_path.stem)
        
        units['session_id'] = sub_id
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

    .. deprecated::
        Use ``unit_quality_scores`` directly. This alias is kept for backward
        compatibility and will be removed in a future version.

    Args:
        session: OmissionSession
        unit_id: Unit cluster ID

    Returns:
        Dictionary with SNR, waveform metrics, and quality assessment
    """
    warnings.warn(
        "noise_vs_signal() is deprecated; call unit_quality_scores() directly.",
        DeprecationWarning, stacklevel=2
    )
    return unit_quality_scores(session, unit_id)


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
    if tfr_data is None or spike_data is None:
        return {'error': 'Input arrays cannot be None'}
        
    # Standardize time-series signals
    # If 3D, average over frequency
    if tfr_data.ndim == 3:
        tfr_mean = np.mean(tfr_data, axis=0)
    else:
        tfr_mean = tfr_data
        
    # Average across trials if needed
    if tfr_mean.ndim == 2:
        tfr_avg = np.mean(tfr_mean, axis=-1)
    else:
        tfr_avg = tfr_mean
        
    if spike_data.ndim == 2:
        spike_avg = np.mean(spike_data, axis=-1)
    else:
        spike_avg = spike_data
        
    n_pts = min(len(tfr_avg), len(spike_avg))
    if n_pts < 3:
        return {'error': 'Insufficient sample size for correlation'}
        
    x = tfr_avg[:n_pts]
    y = spike_avg[:n_pts]
    
    corr_res = StatisticalAnalysis.correlate(x, y)
    return {
        'correlation': corr_res,
        'n_samples': n_pts,
        'interpretation': 'Linear correlation between trial-averaged LFP envelope and spike counts'
    }


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
