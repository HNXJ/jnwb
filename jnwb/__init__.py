"""
jnwb: dataset-agnostic NWB electrophysiology analysis library.

Provides composable operations for NWB addressing, spikes, LFP, spectral
analysis, statistics, population analysis, decoding, connectivity, laminar
CSD, filtering, QC/artifact handling, and visualization. Experiment-specific
condition codes and hypotheses belong in downstream project code, not here.

    >>> import jnwb
    >>> result = jnwb.jrsa(x1, x2, metric='rsa', stats=True)
    >>> jnwb.paths.describe()
"""

__version__ = '0.1.6'
__release_date__ = '2026-09-10'
__author__ = 'Hamed Nejat'
__status__ = 'Beta'

import importlib
import logging
from pathlib import Path
from typing import Union, Optional, List
import glob

from ._lazy_exports import EXPORT_MODULES, SUBMODULES

log = logging.getLogger(__name__)

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

def __getattr__(name: str):
    if name in SUBMODULES:
        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    if name in EXPORT_MODULES:
        module = importlib.import_module(f".{EXPORT_MODULES[name]}", __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


from .trajectory import (
    build_time_resolved_matrix,
    compute_population_trajectory,
)

# Canonical label-permutation primitive for null construction (2026-08-10; see
# jnwb/permutation.py's module docstring for the exchangeability bug it fixed).
from .permutation import permute_labels, build_permutation_plan

# Generic trial-segmented artifact detection-and-substitution (promoted 2026-08-23 from
# omission.jnwb_ext.artifact_repair; see jnwb/artifact_repair.py's module docstring).
from .artifact_repair import (
    repair_lfp_trials,
    repair_band_artifacts,
    detect_band_outliers,
    DETECTION_TAILS,
)
from .tfr import complex_tfr, morlet_wavelet, ComplexTFR
from .artifact_detection import (
    channel_correlation_matrix,
    bad_channels_from_correlation,
    trial_correlation_matrix,
    bad_trials_single_channel,
    consensus_bad_trials,
)

# Digital filtering (SOS Butterworth bandpass and IIR notch)
from .filtering import (
    bandpass_filter,
    notch_filter,
)

# Generic spectral analysis: band-limited power, cross-area coherence, 1/f tilt, imaginary
# coherency, re-referencing (promoted 2026-08-23 from omission.jnwb_ext.spectral; see
# jnwb/spectral.py's module docstring).
from .spectral import (
    to_db,
    aggregate_to_db,
    DB_AGGREGATIONS,
    harmonic_analysis,
    cross_area_coherence,
    spectral_tilt,
    band_power,
    imaginary_coherency,
    bipolar_reference,
    laplacian_reference,
    CANONICAL_BANDS,
    compute_psd,
    compute_multitaper_psd,
    voltage_curvature_1d,
    current_source_density_1d,
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

# Generic spike-response metrics: firing rate/latency/z-score relative to behavioral epochs,
# significance classification, spike-LFP phase locking (promoted 2026-08-23 from
# omission.jnwb_ext.spiking; see jnwb/spiking.py's module docstring).
from .spiking import (
    compute_response_metrics,
    classify_response_significance,
    phase_locking_index,
    pairwise_phase_consistency,
    gaussian_smooth_rate,
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
    'fires_in_window',
    'fire_indicator',
    'paired_fire_prob_test',
    'rate_in_window',
    'shuffle_pvalue_paired',
    'shuffle_pvalue_unpaired',
    'cluster_permutation_test',
    'detect_trial_cycles',
    'assign_subblock_quartiles',
    'shuffle_r2_ci',
    'cross_modal_comparison',

    # Visual QC
    'visual_qc',

    # Trajectory
    'build_time_resolved_matrix',
    'compute_population_trajectory',

    # Permutation / null construction
    'permute_labels',
    'build_permutation_plan',

    # Artifact detection/repair
    'repair_lfp_trials',
    'repair_band_artifacts',
    'detect_band_outliers',
    'DETECTION_TAILS',
    'channel_correlation_matrix',
    'bad_channels_from_correlation',
    'trial_correlation_matrix',
    'bad_trials_single_channel',
    'consensus_bad_trials',

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
    'filter_by_criteria',
    'audit_units',
    'audit_electrodes',
    'assign_quality_tier',

    # Digital filtering
    'bandpass_filter',
    'notch_filter',

    # Spectral analysis
    'to_db',
    'aggregate_to_db',
    'DB_AGGREGATIONS',
    'harmonic_analysis',
    'cross_area_coherence',
    'spectral_tilt',
    'band_power',
    'imaginary_coherency',
    'bipolar_reference',
    'laplacian_reference',
    'CANONICAL_BANDS',
    'compute_psd',
    'compute_multitaper_psd',
    'voltage_curvature_1d',
    'current_source_density_1d',
    'complex_tfr',
    'morlet_wavelet',
    'ComplexTFR',

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
    'assign_outer_folds',
    'build_inner_validation_partitions',
    'build_representation_ladder',

    # Spiking response metrics
    'compute_response_metrics',
    'classify_response_significance',
    'phase_locking_index',
    'pairwise_phase_consistency',
    'gaussian_smooth_rate',

    # Plotting utilities
    'setup_vector_graphics',
    'apply_tight_auto_axis',
    'save_figure_suite',
    'resample_onsets',
    'raster_psth',
]


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
