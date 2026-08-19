"""
Factory functions: wire ontology to existing OmissionSession.

These functions create ontology objects (Query, Dataset, Result, etc.)
from OmissionSession and analysis outputs.

Factories are INTERNAL. Users interact with ontology objects, not factories.

Author: Claude Code
Date: 2026-06-25
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import numpy as np
import pandas as pd
from datetime import datetime
import hashlib

from jnwb.ontology import (
    Query, Dataset, AlignedDataset, Alignment, EpochCollection,
    Question, Result, Interpretation, Figure,
    Provenance, Lineage,
)
from .session import OmissionSession

log = logging.getLogger(__name__)


def dataset_from_session(session: OmissionSession, query: Query) -> Dataset:
    """
    Create immutable Dataset from OmissionSession and Query.

    Implements: Query.sessions, Query.areas, Query.correct_only
    Returns: Dataset with aggregated units, metadata
    """
    units_df = session.get_units()

    # Filter by areas if specified
    if query.areas is not None:
        units_df = units_df[units_df['area'].isin(query.areas)]

    # Filter by units if specified. Previously hardcoded units_df['cluster_id'],
    # which crashed with KeyError since session.get_units() always runs
    # enrich_units_dataframe (renames cluster_id -> unit_id). Matches by raw
    # DataFrame row position (not the 'unit_id' column) for consistency with
    # the rest of the pipeline (omission.jnwb_ext.unit_classification.classify_session_units,
    # scripts/classify_units_shuffle_sso.py, etc. all use raw row position as
    # the actual unit identity - the 'unit_id' column is a separate,
    # per-probe-local kilosort id that is not globally unique within a session).
    if query.units is not None:
        units_df = units_df[units_df.index.isin(query.units)]

    log.info(f"Dataset: {len(units_df)} units from {session.nwb_path.name}")

    dataset = Dataset(
        query=query,
        sessions=[session.nwb_path.stem],
        units=units_df,
        metadata={
            'source_session': str(session.nwb_path),
            'context': session.context,
            'n_units': len(units_df),
        }
    )

    return dataset


def aligned_dataset_from_dataset(dataset: Dataset, alignment: Alignment) -> AlignedDataset:
    """
    Create AlignedDataset by pairing Dataset with Alignment.

    No data modification. Pure semantic labeling.
    """
    return AlignedDataset(
        dataset=dataset,
        alignment=alignment,
    )


def epochs_from_aligned_dataset(
    aligned_dataset: AlignedDataset,
    session: OmissionSession,
    condition: str,
    phase: Optional[int] = None,
    correct_only: bool = True,
) -> EpochCollection:
    """
    Create EpochCollection by filtering trials from AlignedDataset.

    Implements: condition filtering, phase filtering, correct_only
    Returns: EpochCollection with epoch_times and metadata
    """
    # Get epochs from session (OmissionSession.get_epochs already handles filtering)
    epochs_df = session.get_epochs(
        phase=phase,
        condition=condition,
        correct_only=correct_only
    )

    if len(epochs_df) == 0:
        log.warning(f"No epochs found: condition={condition}, phase={phase}, correct_only={correct_only}")

    log.info(f"EpochCollection: {len(epochs_df)} trials")

    epoch_collection = EpochCollection(
        aligned_dataset=aligned_dataset,
        condition=condition,
        phase=phase,
        correct_only=correct_only,
        epochs_df=epochs_df,
    )

    return epoch_collection


def result_from_psth_analysis(
    question: Question,
    epochs: EpochCollection,
    session: OmissionSession,
    unit_ids: List[int],
    baseline_window: tuple = (-0.5, 0.0),
    response_window: tuple = (0.0, 0.5),
) -> Result:
    """
    Create Result from PSTH analysis.

    Computes: firing rate, z-score, significance
    Returns: immutable Result with statistics, provenance, lineage
    """
    from .spiking import compute_response_metrics, classify_response_significance

    all_stats = []

    for unit_id in unit_ids:
        spike_times = session.get_spike_times(unit_id)
        if spike_times is None or len(spike_times) == 0:
            continue

        metrics = compute_response_metrics(
            spike_times,
            epochs.epochs_df['start_time'].values,
            baseline_window=baseline_window,
            response_window=response_window,
        )

        significance = classify_response_significance(metrics, zscore_threshold=1.96)

        all_stats.append({
            'unit_id': unit_id,
            'baseline_rate': metrics['baseline_rate'],
            'response_rate': metrics['response_rate'],
            'zscore': metrics['response_zscore'],
            'is_significant': significance['is_significant'],
            'pvalue': significance['pvalue'],
        })

    stats_df = pd.DataFrame(all_stats)

    provenance = Provenance(
        software_version="0.9.1",
        backend="numpy",
        random_seed=42,
        parameters={
            'baseline_window': baseline_window,
            'response_window': response_window,
            'zscore_threshold': 1.96,
        },
    )

    lineage = Lineage(
        source_type="Result",
        source_id=hashlib.md5(
            str((question, epochs, unit_ids)).encode()
        ).hexdigest()[:8],
        parents=[epochs.aligned_dataset.dataset.query.sessions[0]],
        operation="psth_analysis",
    )

    result = Result(
        question=question,
        statistics={
            'n_units': len(all_stats),
            'n_responsive': (stats_df['is_significant'] == True).sum(),
            'mean_baseline_rate': stats_df['baseline_rate'].mean(),
            'mean_response_rate': stats_df['response_rate'].mean(),
            'mean_zscore': stats_df['zscore'].mean(),
            'response_rate_std': stats_df['response_rate'].std(),
            'detailed_stats': stats_df.to_dict('records'),
        },
        provenance=provenance,
        lineage=lineage,
    )

    log.info(f"Result: {result.statistics['n_responsive']}/{result.statistics['n_units']} units responsive")

    return result


def figure_from_result(
    result: Result,
    interpretation: Optional[Interpretation] = None,
    title: str = "PSTH Analysis",
) -> Figure:
    """
    Create Figure from Result and optional Interpretation.

    Returns: mutable Figure (can be styled and saved)
    """
    if interpretation is None:
        interpretation = Interpretation(
            claim="See statistical results above",
            confidence="medium",
        )

    figure = Figure(
        result=result,
        interpretation=interpretation,
        title=title,
    )

    log.info(f"Figure created: {title}")

    return figure


def result_from_spike_lfp_correlation_analysis(
    question: Question,
    spike_times: np.ndarray,
    lfp_signal: np.ndarray,
    lfp_timestamps: np.ndarray,
    omission_trial_indices: List[int],
    control_trial_indices: List[int],
    fmin: float = 55.0,
    fmax: float = 90.0,
    moving_window_ms: float = 500.0,
) -> Result:
    """
    Create Result from spike-LFP moving correlation analysis.

    Computes: moving correlation between spike times and LFP across trials
    Returns: immutable Result with statistics, provenance, lineage

    Args:
        spike_times: spike times for unit (seconds)
        lfp_signal: LFP voltage signal (V)
        lfp_timestamps: LFP timestamps (seconds)
        omission_trial_indices: indices of omission trials
        control_trial_indices: indices of control trials
        fmin, fmax: frequency band (Hz)
        moving_window_ms: window size for moving correlation
    """
    from scipy import signal as scipy_signal
    from scipy.stats import wilcoxon

    # Filter LFP to frequency band
    # Simple approach: use frequency-domain filter
    nyquist = 1.0 / (lfp_timestamps[1] - lfp_timestamps[0]) / 2

    if fmax < nyquist:
        # Design bandpass filter
        sos = scipy_signal.butter(4, [fmin / nyquist, fmax / nyquist], btype='band', output='sos')
        lfp_filtered = scipy_signal.sosfilt(sos, lfp_signal)
    else:
        lfp_filtered = lfp_signal

    # Compute instantaneous amplitude (envelope)
    analytic_signal = scipy_signal.hilbert(lfp_filtered)
    lfp_amplitude = np.abs(analytic_signal)

    # Normalize
    lfp_amplitude = (lfp_amplitude - np.mean(lfp_amplitude)) / (np.std(lfp_amplitude) + 1e-8)

    window_samples = int(moving_window_ms * 1000 * (len(lfp_timestamps) / ((lfp_timestamps[-1] - lfp_timestamps[0]) * 1000)))
    window_samples = max(window_samples, 10)

    omission_correlations = []
    control_correlations = []

    # For each trial, compute correlation in moving window
    trial_duration_samples = len(lfp_signal) // max(len(omission_trial_indices) + len(control_trial_indices), 1)

    for trial_idx in omission_trial_indices:
        start_idx = trial_idx * trial_duration_samples
        end_idx = start_idx + trial_duration_samples

        if end_idx > len(lfp_amplitude):
            continue

        # Spike raster for this trial
        trial_start = lfp_timestamps[start_idx]
        trial_end = lfp_timestamps[min(end_idx - 1, len(lfp_timestamps) - 1)]
        spikes_in_trial = spike_times[(spike_times >= trial_start) & (spike_times < trial_end)]

        # Create spike raster
        spike_raster = np.zeros_like(lfp_amplitude[start_idx:end_idx])
        for spike in spikes_in_trial:
            spike_sample = int((spike - trial_start) * 1000 / (lfp_timestamps[1] - lfp_timestamps[0]))
            if 0 <= spike_sample < len(spike_raster):
                spike_raster[spike_sample] = 1

        # Smooth spike raster
        if len(spike_raster) > window_samples:
            spike_smooth = np.convolve(spike_raster, np.ones(window_samples) / window_samples, mode='same')
            # Compute correlation
            correlation = np.corrcoef(spike_smooth, lfp_amplitude[start_idx:end_idx])[0, 1]
            if not np.isnan(correlation):
                omission_correlations.append(correlation)

    for trial_idx in control_trial_indices:
        start_idx = trial_idx * trial_duration_samples
        end_idx = start_idx + trial_duration_samples

        if end_idx > len(lfp_amplitude):
            continue

        trial_start = lfp_timestamps[start_idx]
        trial_end = lfp_timestamps[min(end_idx - 1, len(lfp_timestamps) - 1)]
        spikes_in_trial = spike_times[(spike_times >= trial_start) & (spike_times < trial_end)]

        spike_raster = np.zeros_like(lfp_amplitude[start_idx:end_idx])
        for spike in spikes_in_trial:
            spike_sample = int((spike - trial_start) * 1000 / (lfp_timestamps[1] - lfp_timestamps[0]))
            if 0 <= spike_sample < len(spike_raster):
                spike_raster[spike_sample] = 1

        if len(spike_raster) > window_samples:
            spike_smooth = np.convolve(spike_raster, np.ones(window_samples) / window_samples, mode='same')
            correlation = np.corrcoef(spike_smooth, lfp_amplitude[start_idx:end_idx])[0, 1]
            if not np.isnan(correlation):
                control_correlations.append(correlation)

    # Statistics
    omission_correlations = np.array(omission_correlations)
    control_correlations = np.array(control_correlations)

    if len(omission_correlations) > 0 and len(control_correlations) > 0:
        stat, pval = wilcoxon(omission_correlations, control_correlations)
    else:
        stat, pval = np.nan, 1.0

    provenance = Provenance(
        software_version="1.0.0",
        backend="numpy",
        random_seed=42,
        parameters={
            'fmin': fmin,
            'fmax': fmax,
            'moving_window_ms': moving_window_ms,
        },
    )

    lineage = Lineage(
        source_type="Result",
        source_id=hashlib.md5(
            str((question, "spike_lfp_corr")).encode()
        ).hexdigest()[:8],
        parents=[],
        operation="spike_lfp_moving_correlation",
    )

    result = Result(
        question=question,
        statistics={
            'frequency_band': f"{fmin}-{fmax} Hz",
            'n_omission_trials': len(omission_correlations),
            'n_control_trials': len(control_correlations),
            'mean_omission_correlation': float(np.mean(omission_correlations)) if len(omission_correlations) > 0 else 0.0,
            'mean_control_correlation': float(np.mean(control_correlations)) if len(control_correlations) > 0 else 0.0,
            'std_omission_correlation': float(np.std(omission_correlations)) if len(omission_correlations) > 0 else 0.0,
            'std_control_correlation': float(np.std(control_correlations)) if len(control_correlations) > 0 else 0.0,
            'wilcoxon_statistic': float(stat) if not np.isnan(stat) else None,
            'wilcoxon_pvalue': float(pval) if not np.isnan(pval) else 1.0,
            'omission_correlations': omission_correlations.tolist() if len(omission_correlations) > 0 else [],
            'control_correlations': control_correlations.tolist() if len(control_correlations) > 0 else [],
        },
        provenance=provenance,
        lineage=lineage,
    )

    log.info(f"Result: Spike-LFP correlation computed ({len(omission_correlations)} omission, {len(control_correlations)} control trials)")

    return result


def result_from_decoding_analysis(
    question: Question,
    epochs: EpochCollection,
    session: OmissionSession,
    epochs_b: Optional[EpochCollection] = None,
    classifier_type: str = "lda",
) -> Result:
    """
    Create Result from decoding/classification analysis.

    Computes: real cross-validated SVM classifier performance via
    omission.jnwb_ext.decoding.decode_stimulus_identity (nested CV, real accuracy/f1/auc/
    majority_baseline_accuracy — never fabricated).

    Args:
        epochs: first condition's EpochCollection (its .condition is class A)
        epochs_b: second condition's EpochCollection (its .condition is class B).
            Required for a real two-class decode; if omitted, returns an
            honest 'insufficient_data' status rather than fabricating a result
            (classifier_type is accepted for backward-compat but SVM is used
            internally, matching omission.jnwb_ext.decoding's actual implementation).

    Returns: immutable Result with statistics, provenance, lineage
    """
    from .decoding import decode_stimulus_identity

    area_list = epochs.aligned_dataset.dataset.query.areas
    area = area_list[0] if area_list else None

    if epochs_b is None or area is None:
        log.warning(
            "result_from_decoding_analysis: epochs_b (second condition) or area "
            "not provided; cannot run a real two-class decode. Returning "
            "insufficient_data status rather than a fabricated result."
        )
        dec = {
            'status': 'insufficient_data',
            'accuracy': float('nan'), 'f1': float('nan'), 'auc': float('nan'),
            'majority_baseline_accuracy': float('nan'), 'fold_accuracies': [],
        }
    else:
        dec = decode_stimulus_identity(
            session=session,
            area=area,
            condition_pairs=(epochs.condition, epochs_b.condition),
        )

    provenance = Provenance(
        software_version="0.9.1",
        backend="numpy",
        random_seed=42,
        parameters={
            'classifier_type': 'svm',
            'condition_pairs': (epochs.condition, epochs_b.condition if epochs_b else None),
            'area': area,
        },
    )

    lineage = Lineage(
        source_type="Result",
        source_id=hashlib.md5(
            str((question, epochs, epochs_b, classifier_type)).encode()
        ).hexdigest()[:8],
        parents=[epochs.aligned_dataset.dataset.query.sessions[0]],
        operation="decoding_analysis",
    )

    result = Result(
        question=question,
        statistics={
            'classifier_type': 'svm',
            'status': dec.get('status', 'success' if not np.isnan(dec.get('accuracy', float('nan'))) else 'insufficient_data'),
            'accuracy_mean': dec.get('accuracy', float('nan')),
            'auc_mean': dec.get('auc', float('nan')),
            'f1_mean': dec.get('f1', float('nan')),
            'majority_baseline_accuracy': dec.get('majority_baseline_accuracy', float('nan')),
            'accuracy_by_fold': list(dec.get('fold_accuracies', [])),
            'chance_level': 0.5,
        },
        provenance=provenance,
        lineage=lineage,
    )

    log.info(f"Result: Decoding status={result.statistics['status']}, "
             f"accuracy={result.statistics['accuracy_mean']}")

    return result


def result_from_tfr_analysis(
    question: Question,
    epochs: EpochCollection,
    session: OmissionSession,
    fmin: float = 4.0,
    fmax: float = 150.0,
    n_cycles: float = 7.0,
) -> Result:
    """
    Create Result from TFR (Time-Frequency Representation) analysis.

    Computes: real baseline-vs-response band power from preprocessed TFR
    arrays via session.tfr_from_preprocessed (never fabricated). Returns an
    honest 'insufficient_data' status if no precomputed TFR array exists for
    this session/area/condition, rather than fabricating band statistics.

    Returns: immutable Result with statistics, provenance, lineage
    """
    area_list = epochs.aligned_dataset.dataset.query.areas
    area = area_list[0] if area_list else None

    # INTENTIONAL BREAK (2026-08-04): was the pre-correction set (alpha 8-12,
    # beta 12-30, low_gamma 30-55, high_gamma 55-90), contradicting the settled
    # band definitions in CLAUDE.md. Band names are unchanged so the band_stats
    # keys are stable; the power values move with the new edges.
    from .connectivity import CANONICAL_BANDS
    freq_bands = dict(CANONICAL_BANDS)

    tfr_array = session.tfr_from_preprocessed(area=area, band=None, condition=epochs.condition) \
        if area else None

    status = 'success'
    band_stats = {}

    if tfr_array is None:
        log.warning(
            f"result_from_tfr_analysis: no preprocessed TFR array found for "
            f"area={area}, condition={epochs.condition}. Returning "
            f"insufficient_data status rather than a fabricated result."
        )
        status = 'insufficient_data'
        for band_name in freq_bands:
            band_stats[band_name] = {
                'baseline_power_db': float('nan'),
                'response_power_db': float('nan'),
                'power_change_db': float('nan'),
            }
    else:
        # Contract (omission.jnwb_ext.session.tfr_from_preprocessed): (n_trials, n_channels, n_freqs, n_times)
        # freqs ~ arange(3, 201, 2); times ~ -1000 + arange(500)*10 ms
        freqs = np.arange(3, 201, 2)[: tfr_array.shape[2]]
        times_ms = -1000.0 + np.arange(tfr_array.shape[3]) * 10.0
        mean_power = np.mean(tfr_array, axis=(0, 1))  # (n_freqs, n_times)

        baseline_mask = times_ms < 0
        response_mask = (times_ms >= 0) & (times_ms <= 500)

        for band_name, (fmin_band, fmax_band) in freq_bands.items():
            freq_mask = (freqs >= fmin_band) & (freqs < fmax_band)
            if not np.any(freq_mask):
                band_stats[band_name] = {
                    'baseline_power_db': float('nan'),
                    'response_power_db': float('nan'),
                    'power_change_db': float('nan'),
                }
                continue
            baseline_power = float(np.mean(mean_power[freq_mask][:, baseline_mask]))
            response_power = float(np.mean(mean_power[freq_mask][:, response_mask]))
            baseline_power = max(baseline_power, 1e-12)
            response_power = max(response_power, 1e-12)

            band_stats[band_name] = {
                'baseline_power_db': float(10 * np.log10(baseline_power)),
                'response_power_db': float(10 * np.log10(response_power)),
                'power_change_db': float(10 * np.log10(response_power / baseline_power)),
            }

    provenance = Provenance(
        software_version="0.9.1",
        backend="numpy",
        random_seed=42,
        parameters={
            'fmin': fmin,
            'fmax': fmax,
            'n_cycles': n_cycles,
            'area': area,
            'condition': epochs.condition,
        },
    )

    lineage = Lineage(
        source_type="Result",
        source_id=hashlib.md5(
            str((question, epochs, fmin, fmax)).encode()
        ).hexdigest()[:8],
        parents=[epochs.aligned_dataset.dataset.query.sessions[0]],
        operation="tfr_analysis",
    )

    valid_bands = {k: v for k, v in band_stats.items() if not np.isnan(v['power_change_db'])}
    strongest_band = (
        max(valid_bands.items(), key=lambda x: abs(x[1]['power_change_db']))[0]
        if valid_bands else None
    )

    result = Result(
        question=question,
        statistics={
            'status': status,
            'frequency_range': (fmin, fmax),
            'n_cycles': n_cycles,
            'band_statistics': band_stats,
            'strongest_band': strongest_band,
        },
        provenance=provenance,
        lineage=lineage,
    )

    log.info(f"Result: TFR status={status}, {len(valid_bands)}/{len(band_stats)} bands with real data")

    return result


def visualize_spike_lfp_correlation(result: Result, output_path: Union[str, Path] = None) -> "Figure":
    """
    Create SVG visualization of spike-LFP correlation results.

    Plots moving correlation timecourse for omission vs control conditions.
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    fig, ax = plt.subplots(figsize=(10, 6))

    omission_corrs = result.statistics.get('omission_correlations', [])
    control_corrs = result.statistics.get('control_correlations', [])

    if omission_corrs:
        trials = np.arange(len(omission_corrs))
        ax.plot(trials, omission_corrs, 'o-', label='Omission', color='#d62728', alpha=0.7, linewidth=2, markersize=6)
        ax.fill_between(trials, omission_corrs, alpha=0.2, color='#d62728')

    if control_corrs:
        trials = np.arange(len(control_corrs))
        ax.plot(trials, control_corrs, 's-', label='Control', color='#1f77b4', alpha=0.7, linewidth=2, markersize=6)
        ax.fill_between(trials, control_corrs, alpha=0.2, color='#1f77b4')

    ax.axhline(y=0, color='k', linestyle='--', alpha=0.3, linewidth=0.8)
    ax.set_xlabel('Trial', fontsize=12, fontweight='bold')
    ax.set_ylabel('Spike-LFP Correlation', fontsize=12, fontweight='bold')
    ax.set_title(f'Spike-LFP Moving Correlation\n{result.question.hypothesis}', fontsize=13, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    # Add statistical annotation
    pval = result.statistics.get('wilcoxon_pvalue', 1.0)
    sig_text = f"p = {pval:.6f}"
    if pval < 0.05:
        sig_text += " *"
    if pval < 0.01:
        sig_text += "*"
    ax.text(0.98, 0.98, sig_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, format='svg', dpi=150)
        log.info(f"Figure saved: {output_path}")

    from jnwb.ontology import Figure, Interpretation
    figure = Figure(
        result=result,
        interpretation=Interpretation(claim="Visualization of spike-LFP correlation", confidence="high"),
        title=str(result.question.hypothesis),
    )

    return figure


__all__ = [
    'dataset_from_session',
    'aligned_dataset_from_dataset',
    'epochs_from_aligned_dataset',
    'result_from_psth_analysis',
    'result_from_tfr_analysis',
    'result_from_decoding_analysis',
    'result_from_spike_lfp_correlation_analysis',
    'figure_from_result',
    'visualize_spike_lfp_correlation',
]
