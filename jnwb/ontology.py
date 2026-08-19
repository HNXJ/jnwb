"""
jnwb Ontology: Core Scientific Objects

Frozen public API. These objects define the scientific data model.
All are immutable unless otherwise specified.

Core objects:
- Query: data selection rules
- Dataset: aggregated query result
- Alignment: reference frame for epochs
- EpochCollection: filtered trials
- Question: scientific hypothesis
- Result: analysis output with statistics
- Interpretation: meaning and claims
- Figure: visualization

Author: Claude Code
Date: 2026-06-25
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
import logging
import json
from datetime import datetime, timezone
import hashlib
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Provenance:
    """
    Execution context and metadata.

    Captures: software version, backend, timestamp, seed, parameters.
    Part of every Result. Immutable.
    """
    software_version: str
    backend: str  # "numpy", "jax", "dask", etc.
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    random_seed: Optional[int] = None
    git_commit: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'software_version': self.software_version,
            'backend': self.backend,
            'timestamp': self.timestamp,
            'random_seed': self.random_seed,
            'git_commit': self.git_commit,
            'parameters': self.parameters,
            'environment': self.environment,
        }


@dataclass(frozen=True)
class Lineage:
    """
    Artifact dependencies: where did this come from?

    Traces: Session → Dataset → EpochCollection → Result
    Immutable. Every transform creates a new lineage node.
    """
    source_type: str  # "Session", "Dataset", "EpochCollection", etc.
    source_id: str    # session ID, dataset hash, etc.
    parents: List[str] = field(default_factory=list)  # IDs of parent artifacts
    operation: str = ""  # "filter", "extract_epochs", "compute_psth", etc.

    def to_dict(self) -> Dict:
        return {
            'source_type': self.source_type,
            'source_id': self.source_id,
            'parents': self.parents,
            'operation': self.operation,
        }


@dataclass(frozen=True)
class Query:
    """
    Data selection rules: what subset of data?

    Declarative specification of which sessions, areas, conditions.
    Does NOT execute itself. Immutable.

    Scientific Contracts:
    - SC-001: Query never modifies Sessions
    - SC-005: Trial identity preserved in Query result
    """
    sessions: Union[str, List[str]] = "all"
    areas: Optional[List[str]] = None
    units: Optional[List[int]] = None
    """Unit IDs to select - matched against the raw units-table row position
    (dataset_from_session's implementation), the same identity convention
    used by omission.jnwb_ext.unit_classification.classify_session_units and
    scripts/classify_units_shuffle_sso.py. Not the 'unit_id' DataFrame
    column (a per-probe-local kilosort id renamed from cluster_id, which is
    not globally unique within a session)."""
    correct_only: bool = True
    exclude_overlap: bool = False

    def __hash__(self):
        """Enable Query as dict key (e.g., for caching)."""
        sessions_str = str(self.sessions) if isinstance(self.sessions, str) else tuple(self.sessions)
        areas_str = tuple(self.areas) if self.areas else ()
        units_str = tuple(self.units) if self.units else ()
        return hash((sessions_str, areas_str, units_str, self.correct_only, self.exclude_overlap))

    def to_dict(self) -> Dict:
        return {
            'sessions': self.sessions,
            'areas': self.areas,
            'units': self.units,
            'correct_only': self.correct_only,
            'exclude_overlap': self.exclude_overlap,
        }


@dataclass(frozen=True)
class Alignment:
    """
    Reference frame for time-series data.

    Semantic labeling: where is time=0?
    Examples: p1_relative, omission_relative, reward_aligned, fixation_aligned

    Scientific Contracts:
    - SC-003: Alignment never modifies timestamps
    - Alignment only relabels origin; data is unchanged
    """
    name: str  # e.g., "p1_relative", "omission_slot", "reward"
    reference_event: str  # e.g., "stimulus_onset", "trial_start"
    phase_number: Optional[int] = None  # for stimulus-phase-relative alignment

    def __hash__(self):
        return hash((self.name, self.reference_event, self.phase_number))

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'reference_event': self.reference_event,
            'phase_number': self.phase_number,
        }


@dataclass(frozen=True)
class Dataset:
    """
    Aggregated query result: immutable collection of data.

    Created from: Query.execute(sessions)
    Contains: spike times, LFP, metadata, aggregated across sessions

    Scientific Contracts:
    - SC-001: Raw data immutable (Dataset never modifies signals)
    - SC-005: Trial identity preserved

    Software Contracts:
    - SW-001: Dataset immutable (filtering returns new Dataset)
    - SW-002: Backend-independent (users don't see NumPy/JAX)
    """
    query: Query
    sessions: List[str]
    units: pd.DataFrame
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        """Enable Dataset as dict key."""
        return hash((self.query, tuple(self.sessions)))

    def with_alignment(self, alignment: Alignment) -> "AlignedDataset":
        """Return new AlignedDataset pairing this Dataset with an Alignment (pure relabeling,
        no data modification)."""
        return AlignedDataset(dataset=self, alignment=alignment)


@dataclass(frozen=True)
class AlignedDataset:
    """
    Dataset with explicit Alignment.

    Separates: what data (Dataset) from how-to-interpret-time (Alignment)
    Immutable. Created by Dataset.with_alignment().
    """
    dataset: Dataset
    alignment: Alignment


@dataclass(frozen=True)
class EpochCollection:
    """
    Filtered set of trials: immutable.

    Created by: a project-specific factory that filters trial-level epoch data by condition
    and phase (e.g. omission.jnwb_ext.factories.epochs_from_aligned_dataset) -- constructing
    this requires a real trial-timing source (a session/recording object), which the generic
    ontology objects above intentionally do not carry.
    Contains: epoch times, condition metadata, trial indices

    Scientific Contracts:
    - SC-002: Inferential unit explicit (knows what was filtered)
    - SC-005: Trial identity preserved (can trace back to source)
    """
    aligned_dataset: AlignedDataset
    condition: str
    phase: Optional[int]
    correct_only: bool
    epochs_df: pd.DataFrame  # start_time, stop_time, trial_num, etc.

    def __len__(self):
        return len(self.epochs_df)

    def to_dict(self) -> Dict:
        return {
            'condition': self.condition,
            'phase': self.phase,
            'correct_only': self.correct_only,
            'n_epochs': len(self.epochs_df),
        }


@dataclass(frozen=True)
class Question:
    """
    Scientific hypothesis: what are we asking?

    Pure data. No methods. No execution.
    Frozen dataclass: immutable, serializable, hashable.

    Scientific Contracts:
    - SC-002: Inferential unit must be explicit
    """
    hypothesis: str
    signals: List[str]  # e.g., ["spike_times"], ["lfp"], ["spike_times", "lfp"]
    contrast: str  # e.g., "baseline vs response", "AAAB vs AAXB"
    inference_unit: str  # "unit", "session", "subject"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        """Enable Question as cache key."""
        return hash((
            self.hypothesis,
            tuple(self.signals),
            self.contrast,
            self.inference_unit,
        ))

    def to_dict(self) -> Dict:
        return {
            'hypothesis': self.hypothesis,
            'signals': self.signals,
            'contrast': self.contrast,
            'inference_unit': self.inference_unit,
            'metadata': self.metadata,
        }


@dataclass(frozen=True)
class Result:
    """
    Analysis output: statistics, provenance, lineage.

    Created by: Analysis.compute(AnalysisPlan)
    Immutable. Results are facts.

    Software Contracts:
    - SW-001: Result immutable (statistics don't change)
    - SW-004: Result serializable
    """
    question: Question
    statistics: Dict[str, Any]
    provenance: Provenance
    lineage: Lineage

    def to_dict(self) -> Dict:
        return {
            'question': self.question.to_dict(),
            'statistics': self.statistics,
            'provenance': self.provenance.to_dict(),
            'lineage': self.lineage.to_dict(),
        }


@dataclass(frozen=True)
class Interpretation:
    """
    Meaning and claims: what does the result mean?

    Separates: measured evidence (Result) from scientific argument (Interpretation)
    Immutable. Created by user or AI system after inspecting Result.

    Scientific Contracts:
    - SC-004: Interpretation never modifies Result
    """
    claim: str
    confidence: str  # "high", "moderate", "low"
    alternative_explanations: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'claim': self.claim,
            'confidence': self.confidence,
            'alternative_explanations': self.alternative_explanations,
            'limitations': self.limitations,
            'metadata': self.metadata,
        }


@dataclass
class Figure:
    """
    Visualization: rendering of Result + Interpretation.

    MUTABLE (only public API object that is mutable).
    Styling and layout can change; underlying data cannot.

    This object carries figure metadata (title, axes_data, layout) as plain dicts, not a bound
    renderer -- it has nothing to draw with. Actual PNG/PDF/SVG rendering happens where the plot
    is built (e.g. matplotlib calls in a project's factory functions, which call `fig.savefig`
    directly); this object is what gets attached to that Result afterward, not what does the
    rendering.

    Software Contracts:
    - SW-004: Figure serializable (`to_dict()` -- JSON-style metadata export)
    """
    result: Result
    interpretation: Interpretation
    title: str = ""
    axes_data: Dict[str, Any] = field(default_factory=dict)
    layout: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'result': self.result.to_dict(),
            'interpretation': self.interpretation.to_dict(),
            'title': self.title,
        }


# Factory functions (internal, not frozen)
#
# create_dataset_from_query and create_epochs are intentionally absent here: both need a real
# NWB/trial-timing data source (an open session/recording object) that these generic ontology
# objects do not carry, so a generic implementation would have nothing to read from. Projects
# provide their own equivalents once they have a concrete data source to wire in -- e.g.
# omission.jnwb_ext.factories.dataset_from_session and .epochs_from_aligned_dataset.

def create_aligned_dataset(dataset: Dataset, alignment: Alignment) -> AlignedDataset:
    """Create aligned Dataset with semantic labeling."""
    return AlignedDataset(dataset=dataset, alignment=alignment)


def create_result(question: Question, statistics: Dict[str, Any],
                  provenance: Provenance, lineage: Lineage) -> Result:
    """Create immutable Result."""
    return Result(
        question=question,
        statistics=statistics,
        provenance=provenance,
        lineage=lineage,
    )


def create_figure(result: Result, interpretation: Interpretation,
                  title: str = "") -> Figure:
    """Create mutable Figure from Result and Interpretation."""
    return Figure(
        result=result,
        interpretation=interpretation,
        title=title,
    )


__all__ = [
    'Query',
    'Dataset',
    'AlignedDataset',
    'Alignment',
    'EpochCollection',
    'Question',
    'Result',
    'Interpretation',
    'Figure',
    'Provenance',
    'Lineage',
]
