"""
omission: Object-Oriented Grammar for Omission NWB Analysis

Unified, clean interface for all omission experiment analysis. Depends on the generic
``jnwb`` library (repo-root ``jnwb/``) for NWB access, path resolution, addressing,
JRSA, and generic statistics; everything here is specific to this experiment's task
structure (conditions, slots, S+/S-/O+ classification, decoding, connectivity, viz).

This module is a drop-in replacement for the pre-2026-08-19 ``import jnwb as oa``
surface -- every name that used to resolve off ``jnwb`` still resolves the same way
off ``omission``, just re-sourced from either ``jnwb`` (generic) or
``omission.jnwb_ext`` (moved here during the restructure).

Quick Start:
    >>> import omission as oa
    >>> session = oa.read('sub-C31o_ses-230823_rec.nwb')
    >>> session.trial_averaged_plot(area='V1', condition='AAXB')
    >>> units = session.find_single_units(quality='stable_plus')
    >>> session.raster_suite(unit_id=42)

    # Representational similarity analysis (generic, from jnwb)
    >>> result = oa.jrsa(x1, x2, metric='rsa', stats=True)
    >>> result.summary()
    >>> result.plot()

Author: Claude Code
Date: 2025-06-24
Restructured: 2026-08-19 -- split out of jnwb/ into this dedicated project package.
Version: 2.0.0
"""

__version__ = '2.0.0'
__release_date__ = '2026-08-19'
__author__ = 'Claude Code'
__status__ = 'Stable - Public API Frozen (moved from jnwb, 2026-08-19)'

import logging
from pathlib import Path
from typing import Union, List

from .jnwb_ext.session import OmissionSession

log = logging.getLogger(__name__)


def read(nwb_path: Union[str, Path], context: str = 'omission_glo_passive') -> OmissionSession:
    """
    Load NWB file as OmissionSession.

    Main entry point. Provides object-oriented interface with clean methods for:
    - Epoched data extraction
    - Trial-averaged plots
    - Single-unit finding and analysis
    - Raster suites (raster + PSTH + autocorrelogram)
    - Pie chart generation by quality/area
    - TFR analysis
    - Spectrolaminar (layer-wise) analysis

    Args:
        nwb_path: Path to .nwb file (e.g., 'sub-C31o_ses-230823_rec.nwb')
        context: Interval name for epoching (default: 'omission_glo_passive')

    Returns:
        OmissionSession object with analysis methods

    Example:
        >>> session = oa.read('sub-C31o_ses-230823_rec.nwb')
        >>> session.info()
        >>> units = session.find_single_units(quality='stable_plus')
        >>> session.trial_averaged_plot(area='V1', condition='AAXB')
        >>> session.raster_suite(unit_id=42)
    """
    return OmissionSession(nwb_path, context=context)


def batch_read(nwb_dir: Union[str, Path], pattern: str = '*.nwb',
               context: str = 'omission_glo_passive') -> List[OmissionSession]:
    """
    Load multiple NWB files from directory.

    Convenience function for batch analysis across sessions.

    Args:
        nwb_dir: Directory containing .nwb files
        pattern: Glob pattern for files (default: '*.nwb')
        context: Interval name for epoching

    Returns:
        List of OmissionSession objects

    Example:
        >>> sessions = oa.batch_read(oa.paths.nwb_dir())
        >>> for sess in sessions:
        ...     units = sess.find_single_units(quality='stable_plus')
        ...     print(f"{sess}: {len(units)} stable+ units")
    """
    nwb_dir = Path(nwb_dir)
    nwb_files = sorted(nwb_dir.glob(pattern))

    sessions = []
    for nwb_file in nwb_files:
        try:
            session = OmissionSession(nwb_file, context=context)
            sessions.append(session)
        except Exception as e:
            log.warning(f"Failed to load {nwb_file.name}: {e}")

    log.info(f"Loaded {len(sessions)} sessions from {nwb_dir}")
    return sessions


# ============================================================================
# Generic pieces, re-exported from jnwb so `import omission as oa` matches the
# pre-restructure flat `import jnwb as oa` surface exactly.
# ============================================================================
from jnwb import (
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
    jrsa,
    JRSAResult,
    paths,
    TFRAccumulator,
    assert_mergeable,
    compress_fp32,
    map_peak_channel_to_area,
    classify_layer_from_depth,
    enrich_units_dataframe,
    TFRAnalyzer,
    UnitAnalyzer,
    PopulationAnalyzer,
    StatisticalAnalysis,
    visual_qc,
    build_time_resolved_matrix,
    compute_population_trajectory,
)

# ============================================================================
# Factory functions (bridge to OmissionSession)
# ============================================================================
from .jnwb_ext.factories import (
    dataset_from_session,
    aligned_dataset_from_dataset,
    epochs_from_aligned_dataset,
    result_from_psth_analysis,
    result_from_tfr_analysis,
    result_from_decoding_analysis,
    figure_from_result,
)

# ============================================================================
# LEGACY API (for backwards compatibility)
# ============================================================================

# Metadata, spiking, and diagnostics functions
# metadata.py promoted 2026-08-23 to jnwb.metadata (99%-jnwb-sufficiency normalization) --
# re-exported here unchanged for backwards compatibility with this legacy API block.
from jnwb.metadata import (
    get_all_units_metadata,
    classify_unit_quality,
    unit_census_report,
    get_snr_analysis,
    electrode_inventory,
)
from .jnwb_ext.spiking import (
    compute_response_metrics,
    classify_response_significance,
    classify_omission_response,
    phase_locking_index,
)
from .jnwb_ext.diagnostics import (
    audit_session,
    compare_sessions,
    print_audit_report,
)

# Figure generation (comprehensive visualization)
from .jnwb_ext import viz
from .jnwb_ext.viz import (
    raster_suite_omission,
    lfp_tfr_trace_suite_omission,
    lfp_tfr_trace_correlation,
    plot_granger_network_plotly,
)

from .jnwb_ext.sequence_layout import (
    FULL_SEQUENCE_DURATION_MS,
    apply_sequence_layout,
    channel_slice_for_area,
    epoch_intervals,
    layout_template_svgs,
    make_sequence_figure,
    normalize_area_name,
    omission_window_ms,
    parse_probe_areas,
    sequence_shapes,
)

# Spectral analysis: promoted 2026-08-23 to jnwb.spectral (99%-jnwb-sufficiency
# normalization) -- re-exported here as omission.spectral for backwards compatibility.
from jnwb import spectral

# Canonical functions (TFR, raster/PSTH, unit finding, population, batch, advanced)
from .jnwb_ext.functions import (
    tfr_trial_average,
    tfr_compare_conditions,
    tfr_correlate_areas,
    tfr_spectrolaminar,
    tfr_permutation_test,
    raster_plot,
    psth_analysis,
    autocorrelogram,
    find_units,
    unit_quality_scores,
    unit_channel_mapping,
    pie_charts,
    compare_populations,
    population_by_area,
    network_connectivity,
    units_across_sessions,
    lfp_channel_areas,
    summary_report,
    noise_vs_signal,
    cross_modal_comparison,
)

# Decoding and connectivity functions
from .jnwb_ext.decoding import (
    decode_stimulus_identity,
    decode_omission_presence,
)
# connectivity.py promoted 2026-08-23 to jnwb.connectivity (99%-jnwb-sufficiency
# normalization) -- re-exported here unchanged for backwards compatibility.
from jnwb.connectivity import (
    spike_mutual_information,
    binary_occupancy_mutual_information,
    spike_count_mutual_information,
    granger_causality,
    network_topology,
    DirectedResult,
    CANONICAL_BANDS,
    as_trials,
    bin_spikes,
    granger,
    granger_spectral,
    phase_slope_index,
    transfer_entropy,
    directed_connectivity,
    directed_network,
)

# Short aliases for the directed estimators
gc = granger
sgc = granger_spectral
psi = phase_slope_index
te = transfer_entropy

from .jnwb_ext.unit_classification import (
    ClassificationConfig,
    OPlusPlusTemplateConfig,
    assign_o_plusplus_from_template_table,
    oplusplus_census_summary,
    classify_session_units,
    classify_nwb_file,
    classify_all_nwbs,
    append_session_to_grand_table,
    prevalence_summary,
    stimulus_present_events,
    omission_events,
    config_to_dict,
    discover_nwb_paths,
)
from .jnwb_ext.report import generate_report
from .jnwb_ext.analog import EpochBatch, load_analog_epochs, load_muae_epochs, load_lfp_epochs

# Export main classes and functions
__all__ = [
    # JRSA (generic, from jnwb)
    'jrsa',
    'JRSAResult',
    'EpochBatch',
    'load_analog_epochs',
    'load_muae_epochs',
    'load_lfp_epochs',

    # Ontology objects (generic, from jnwb)
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
    # Factory functions
    'dataset_from_session',
    'aligned_dataset_from_dataset',
    'epochs_from_aligned_dataset',
    'result_from_psth_analysis',
    'result_from_tfr_analysis',
    'result_from_decoding_analysis',
    'figure_from_result',

    # Core
    'read',
    'batch_read',
    'OmissionSession',
    # Metadata extraction
    'get_all_units_metadata',
    'classify_unit_quality',
    'unit_census_report',
    'get_snr_analysis',
    'electrode_inventory',
    # Spiking metrics
    'compute_response_metrics',
    'classify_response_significance',
    'classify_omission_response',
    'phase_locking_index',
    # Diagnostics and QC
    'audit_session',
    'compare_sessions',
    'print_audit_report',
    # Figure generation
    'viz',
    'raster_suite_omission',
    'lfp_tfr_trace_suite_omission',
    'lfp_tfr_trace_correlation',
    'plot_granger_network_plotly',
    # Sequence presentation layout
    'FULL_SEQUENCE_DURATION_MS',
    'apply_sequence_layout',
    'channel_slice_for_area',
    'epoch_intervals',
    'layout_template_svgs',
    'make_sequence_figure',
    'normalize_area_name',
    'omission_window_ms',
    'parse_probe_areas',
    'sequence_shapes',
    # Spectral analysis
    'spectral',
    # Visual QC (generic, from jnwb)
    'visual_qc',
    # Decoding & Connectivity
    'decode_stimulus_identity',
    'decode_omission_presence',
    'spike_mutual_information',
    'binary_occupancy_mutual_information',
    'spike_count_mutual_information',
    'granger_causality',
    'network_topology',
    'DirectedResult',
    'CANONICAL_BANDS',
    'as_trials',
    'bin_spikes',
    'granger',
    'granger_spectral',
    'phase_slope_index',
    'transfer_entropy',
    'directed_connectivity',
    'directed_network',
    'gc',
    'sgc',
    'psi',
    'te',
    'ClassificationConfig',
    'OPlusPlusTemplateConfig',
    'assign_o_plusplus_from_template_table',
    'oplusplus_census_summary',
    'classify_session_units',
    'classify_nwb_file',
    'classify_all_nwbs',
    'append_session_to_grand_table',
    'prevalence_summary',
    'stimulus_present_events',
    'omission_events',
    'config_to_dict',
    'discover_nwb_paths',
    'build_time_resolved_matrix',
    'compute_population_trajectory',
    'generate_report',
    # Analyzer objects (generic, from jnwb)
    'TFRAnalyzer',
    'UnitAnalyzer',
    'PopulationAnalyzer',
    'StatisticalAnalysis',
    # Canonical functions
    'tfr_trial_average',
    'tfr_compare_conditions',
    'tfr_correlate_areas',
    'tfr_spectrolaminar',
    'tfr_permutation_test',
    'raster_plot',
    'psth_analysis',
    'autocorrelogram',
    'find_units',
    'unit_quality_scores',
    'unit_channel_mapping',
    'pie_charts',
    'compare_populations',
    'population_by_area',
    'network_connectivity',
    'units_across_sessions',
    'lfp_channel_areas',
    'paths',
    'TFRAccumulator',
    'assert_mergeable',
    'compress_fp32',
    'summary_report',
    'noise_vs_signal',
    'cross_modal_comparison',
    'map_peak_channel_to_area',
    'classify_layer_from_depth',
    'enrich_units_dataframe',
]
