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


__all__ = [
    'dataset_from_session',
    'aligned_dataset_from_dataset',
    'epochs_from_aligned_dataset',
    'result_from_psth_analysis',
    'figure_from_result',
]
