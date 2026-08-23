"""
jnwb: generic NWB analysis library

Dataset-agnostic NWB access, addressing, JRSA, and statistics. Task-specific
functionality (condition codes, unit classification, decoding, connectivity,
figure suites, etc.) lives in the ``omission`` project package, which depends
on this library and re-exports these generic pieces under its own flat
``import omission as oa`` surface for drop-in compatibility with the
pre-2026-08-19 ``import jnwb as oa`` API.

Quick Start:
    >>> import jnwb
    >>> result = jnwb.jrsa(x1, x2, metric='rsa', stats=True)
    >>> result.summary()
    >>> result.plot()
    >>> jnwb.paths.describe()

Author: Claude Code
Date: 2025-06-24
Restructured: 2026-08-19 -- split into this generic library + omission/ project package.
Version: 0.1.0

Versioning note: this package was carved out of a single project repo (previously versioned
2.0.0 as part of that project's own history) into a standalone generic library on 2026-08-19.
It restarts at 0.1.0 under standard pre-1.0 semver -- the API surface has not yet been exercised
by a second consumer, so nothing here should be treated as stable/frozen until 1.0.0.
"""

__version__ = '0.1.0'
__release_date__ = '2026-08-19'
__author__ = 'Claude Code'
__status__ = 'Alpha -- pre-1.0, API not yet frozen'

import logging
from pathlib import Path
from typing import Union, Optional, List
import glob

# Apply NWB/HDMF repair monkeypatches for sessions with builder anomalies
try:
    from hdmf.build.manager import BuildManager
    import numpy as np

    orig_construct = BuildManager.construct

    def patched_manager_construct(self, *args, **kwargs):
        if args:
            builder = args[0]
        else:
            builder = kwargs.get('builder')

        if builder is not None:
            b_name = getattr(builder, 'name', None)

            # 1. Device string attributes check
            if hasattr(builder, 'attributes'):
                for k, v in builder.attributes.items():
                    if isinstance(v, np.ndarray) and v.ndim == 1 and len(v) == 1:
                        val = v[0]
                        if isinstance(val, (bytes, str)):
                            if isinstance(val, bytes):
                                builder.attributes[k] = val.decode('utf-8', errors='replace')
                            else:
                                builder.attributes[k] = str(val)

            # 2. Check if this is the NWBFile builder (top-level)
            if hasattr(builder, 'attributes') and builder.attributes.get('neurodata_type') == 'NWBFile':
                if 'session_description' not in builder.datasets:
                    from hdmf.build.builders import DatasetBuilder
                    session_desc = DatasetBuilder(
                        name='session_description',
                        data='NWB session',
                        attributes={}
                    )
                    session_desc.parent = builder
                    builder.datasets['session_description'] = session_desc

            # 3. Check if this is the units builder
            if b_name == 'units':
                colnames = list(builder.attributes.get('colnames', []))
                # Remove index column names from colnames
                for index_col in ['spike_times_index', 'waveform_mean_index', 'spike_amplitudes_index']:
                    if index_col in colnames:
                        colnames.remove(index_col)
                # Add target column names to colnames
                for col in ['spike_times', 'waveform_mean', 'spike_amplitudes']:
                    if hasattr(builder, 'datasets') and col in builder.datasets and col not in colnames:
                        colnames.append(col)
                builder.attributes['colnames'] = np.array(colnames, dtype=object)

            # 4. Check for index vector data anomalies
            if b_name in ['waveform_mean_index', 'spike_amplitudes_index']:
                if hasattr(builder, 'attributes'):
                    builder.attributes['neurodata_type'] = 'VectorIndex'
                    target_name = b_name.replace('_index', '')
                    if builder.parent and target_name in builder.parent:
                        builder.attributes['target'] = builder.parent[target_name]

                if b_name == 'waveform_mean_index' and 'data' in builder:
                    builder['data'] = np.array(builder['data'], dtype=np.int64)

        return orig_construct(self, *args, **kwargs)

    BuildManager.construct = patched_manager_construct
except Exception as e:
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# ============================================================================
# Ontology objects (frozen public API)
# ============================================================================
from .ontology import (
    Query,
    Dataset,
    AlignedDataset,
    Alignment,
    EpochCollection,
    Question,
    Result,
    Interpretation,
    Figure,
    Provenance,
    Lineage,
)

# ============================================================================
# JRSA: Unified Representational Similarity Analysis
# ============================================================================
from .jrsa import jrsa, JRSAResult

# Central path resolution (2026-08-08). `jnwb.paths.describe()` reports every root
# and whether it currently resolves -- run it first after any drive remap.
from . import paths

# Poolable TFR summary statistics (2026-08-08), per nwb_tfr_storage_spec.md Part 2/3.
from .tfr_accumulator import TFRAccumulator, assert_mergeable

# NWB fp32 compression (2026-08-09), per nwb_tfr_storage_spec.md Part 1.
from .compression import compress_fp32
from .addressing import (
    map_peak_channel_to_area,
    classify_layer_from_depth,
    enrich_units_dataframe,
)

# Analyzers (3 canonical objects)
from .analyzers import (
    TFRAnalyzer,
    UnitAnalyzer,
    PopulationAnalyzer,
)
from .statistics import StatisticalAnalysis

from . import visual_qc

from .trajectory import (
    build_time_resolved_matrix,
    compute_population_trajectory,
)

# Canonical label-permutation primitive for null construction (2026-08-10; see
# jnwb/permutation.py's module docstring for the exchangeability bug it fixed).
from .permutation import permute_labels

# Generic trial-segmented artifact detection-and-substitution (promoted 2026-08-23 from
# omission.jnwb_ext.artifact_repair; see jnwb/artifact_repair.py's module docstring).
from .artifact_repair import repair_lfp_trials, repair_band_artifacts

# Causal PSTH smoothing + causality-bounded onset-latency fit (promoted 2026-08-23 from
# omission.jnwb_ext.onset_fitting; see jnwb/onset_fitting.py's module docstring).
from .onset_fitting import causal_exp_smooth, fit_exponential_onset, onset_model

# Generic unit/electrode metadata extraction, QC classification, census reporting (promoted
# 2026-08-23 from omission.jnwb_ext.metadata; see jnwb/metadata.py's module docstring).
from .metadata import (
    get_all_units_metadata,
    classify_unit_quality,
    unit_census_report,
    get_snr_analysis,
    electrode_inventory,
)

# Generic spectral analysis: band-limited power, cross-area coherence, 1/f tilt, imaginary
# coherency, re-referencing (promoted 2026-08-23 from omission.jnwb_ext.spectral; see
# jnwb/spectral.py's module docstring).
from .spectral import (
    to_db,
    harmonic_analysis,
    cross_area_coherence,
    spectral_tilt,
    band_power,
    imaginary_coherency,
    bipolar_reference,
    laplacian_reference,
    CANONICAL_BANDS,
)

# Modality-agnostic functional connectivity: mutual information, Granger causality, phase
# slope index, transfer entropy (promoted 2026-08-23 from omission.jnwb_ext.connectivity; see
# jnwb/connectivity.py's module docstring).
from .connectivity import (
    spike_mutual_information,
    binary_occupancy_mutual_information,
    spike_count_mutual_information,
    granger_causality,
    network_topology,
    DirectedResult,
    as_trials,
    bin_spikes,
    granger,
    granger_spectral,
    phase_slope_index,
    transfer_entropy,
    directed_connectivity,
    directed_network,
)

# Generic nested-CV linear-SVM population decoding: plain (X, labels) arrays in, no session
# object or condition semantics (promoted 2026-08-23 from omission.jnwb_ext.decoding; see
# jnwb/decoding.py's module docstring).
from .decoding import (
    majority_baseline,
    fold_majority_baseline,
    nested_cv_linear_svm,
)

# Generic spike-response metrics: firing rate/latency/z-score relative to behavioral epochs,
# significance classification, spike-LFP phase locking (promoted 2026-08-23 from
# omission.jnwb_ext.spiking; see jnwb/spiking.py's module docstring).
from .spiking import (
    compute_response_metrics,
    classify_response_significance,
    phase_locking_index,
)

# Export main classes and functions
__all__ = [
    # JRSA: Unified RSA API
    'jrsa',
    'JRSAResult',

    # Core ontology objects (immutable, stable)
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

    # Path resolution
    'paths',

    # TFR accumulation / compression
    'TFRAccumulator',
    'assert_mergeable',
    'compress_fp32',

    # Addressing
    'map_peak_channel_to_area',
    'classify_layer_from_depth',
    'enrich_units_dataframe',

    # Analyzers
    'TFRAnalyzer',
    'UnitAnalyzer',
    'PopulationAnalyzer',
    'StatisticalAnalysis',

    # Visual QC
    'visual_qc',

    # Trajectory
    'build_time_resolved_matrix',
    'compute_population_trajectory',

    # Permutation / null construction
    'permute_labels',

    # Artifact detection/repair
    'repair_lfp_trials',
    'repair_band_artifacts',

    # Onset-latency fitting
    'causal_exp_smooth',
    'fit_exponential_onset',
    'onset_model',

    # Unit/electrode metadata, QC, census
    'get_all_units_metadata',
    'classify_unit_quality',
    'unit_census_report',
    'get_snr_analysis',
    'electrode_inventory',

    # Spectral analysis
    'to_db',
    'harmonic_analysis',
    'cross_area_coherence',
    'spectral_tilt',
    'band_power',
    'imaginary_coherency',
    'bipolar_reference',
    'laplacian_reference',
    'CANONICAL_BANDS',

    # Functional connectivity
    'spike_mutual_information',
    'binary_occupancy_mutual_information',
    'spike_count_mutual_information',
    'granger_causality',
    'network_topology',
    'DirectedResult',
    'as_trials',
    'bin_spikes',
    'granger',
    'granger_spectral',
    'phase_slope_index',
    'transfer_entropy',
    'directed_connectivity',
    'directed_network',

    # Population decoding
    'majority_baseline',
    'fold_majority_baseline',
    'nested_cv_linear_svm',

    # Spiking response metrics
    'compute_response_metrics',
    'classify_response_significance',
    'phase_locking_index',
]
