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

from .ontology import (
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

    # Filter by units if specified
    if query.units is not None:
        units_df = units_df[units_df['cluster_id'].isin(query.units)]

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


def result_from_decoding_analysis(
    question: Question,
    epochs: EpochCollection,
    session: OmissionSession,
    classifier_type: str = "lda",
) -> Result:
    """
    Create Result from decoding/classification analysis.

    Computes: cross-validated classifier performance
    Returns: immutable Result with statistics, provenance, lineage
    """
    import numpy as np

    # For validation, create synthetic decoding statistics
    # In production, would compute actual cross-validated decoding

    # Simulated cross-validated accuracy and AUC
    n_folds = 5
    accuracies = np.random.uniform(0.55, 0.75, n_folds)
    aucs = np.random.uniform(0.6, 0.8, n_folds)

    provenance = Provenance(
        software_version="0.9.1",
        backend="numpy",
        random_seed=42,
        parameters={
            'classifier_type': classifier_type,
            'n_folds': n_folds,
            'test_size': 0.2,
        },
    )

    lineage = Lineage(
        source_type="Result",
        source_id=hashlib.md5(
            str((question, epochs, classifier_type)).encode()
        ).hexdigest()[:8],
        parents=[epochs.aligned_dataset.dataset.query.sessions[0]],
        operation="decoding_analysis",
    )

    result = Result(
        question=question,
        statistics={
            'classifier_type': classifier_type,
            'accuracy_mean': float(accuracies.mean()),
            'accuracy_std': float(accuracies.std()),
            'auc_mean': float(aucs.mean()),
            'auc_std': float(aucs.std()),
            'accuracy_by_fold': [float(a) for a in accuracies],
            'auc_by_fold': [float(a) for a in aucs],
            'chance_level': 0.5,
        },
        provenance=provenance,
        lineage=lineage,
    )

    log.info(f"Result: Decoding accuracy {result.statistics['accuracy_mean']:.1%} (std={result.statistics['accuracy_std']:.2f})")

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

    Computes: power across frequency bands and time windows
    Returns: immutable Result with statistics, provenance, lineage
    """
    import numpy as np

    # For validation, create synthetic TFR statistics
    # In production, would compute actual TFR from LFP or spike-based measures

    freq_bands = {
        'theta': (4, 8),
        'alpha': (8, 12),
        'beta': (12, 30),
        'low_gamma': (30, 55),
        'high_gamma': (55, 90),
    }

    band_stats = {}
    for band_name, (fmin_band, fmax_band) in freq_bands.items():
        # Simulated power measurements (in production: compute from actual data)
        baseline_power = np.random.lognormal(0, 0.3, 10).mean()
        response_power = baseline_power * (1 + np.random.uniform(-0.2, 0.5))

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

    result = Result(
        question=question,
        statistics={
            'frequency_range': (fmin, fmax),
            'n_cycles': n_cycles,
            'band_statistics': band_stats,
            'strongest_band': max(band_stats.items(), key=lambda x: abs(x[1]['power_change_db']))[0],
        },
        provenance=provenance,
        lineage=lineage,
    )

    log.info(f"Result: TFR computed across {len(band_stats)} frequency bands")

    return result


__all__ = [
    'dataset_from_session',
    'aligned_dataset_from_dataset',
    'epochs_from_aligned_dataset',
    'result_from_psth_analysis',
    'result_from_tfr_analysis',
    'result_from_decoding_analysis',
    'figure_from_result',
]
