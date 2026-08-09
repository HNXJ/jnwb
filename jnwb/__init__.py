"""
jnwb: Object-Oriented Grammar for Omission NWB Analysis

Unified, clean interface for all omission experiment analysis.
Fast shortcuts for epoching, visualization, and statistics.

Quick Start:
    >>> import jnwb as oa
    >>> session = oa.read('sub-C31o_ses-230823_rec.nwb')
    >>> session.trial_averaged_plot(area='V1', condition='AAXB')
    >>> units = session.find_single_units(quality='stable_plus')
    >>> session.raster_suite(unit_id=42)

    # Representational similarity analysis
    >>> result = oa.jrsa(x1, x2, metric='rsa', stats=True)
    >>> result.summary()
    >>> result.plot()

Core Classes:
    - OmissionSession: Main interface for all analysis
      Methods: trial_averaged_plot, channel_averaged_plot, spectrolaminar_motif,
               find_single_units, channel_unit_mapping, lfp_channel_areas,
               tfr_from_preprocessed, plot_tfr, raster_suite, pie_charts,
               get_units, get_electrodes, get_epochs

Functions:
    - read(nwb_path, context): Load NWB file as OmissionSession
    - batch_read(nwb_dir, pattern): Load multiple sessions
    - jrsa(x1, x2, ...): Unified RSA / cross-area similarity analysis

Typical Workflow:
    1. Load:    session = oa.read(nwb_path)
    2. Explore: units = session.find_single_units(quality='stable_plus', area='V1')
    3. Analyze: session.trial_averaged_plot(area='V1', condition='omission')
    4. Visualize: session.raster_suite(unit_id=42)

Usage Philosophy:
    - Clean grammar: session.<method>(<args>) for every analysis type
    - Fast shortcuts: common analyses in 1-2 lines
    - Sensible defaults: works out-of-box
    - Extensible: base class for custom methods

Author: Claude Code
Date: 2025-06-24
Version: 1.0.0
"""

__version__ = '1.0.0'
__release_date__ = '2026-06-25'
__author__ = 'Claude Code'
__status__ = 'Stable - Public API Frozen'

import logging
from pathlib import Path
from typing import Union, Optional, List
import glob

# Apply NWB/HDMF repair monkeypatches for sub-V182o and other sessions with builder anomalies
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
                        data='Omission Passive GLO;',
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

from .session import OmissionSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
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

    log.info(f"✓ Loaded {len(sessions)} sessions from {nwb_dir}")
    return sessions


# ============================================================================
# v1.0.0 PUBLIC API (FROZEN)
# These 13 core objects are immutable and stable until v2.0
# ============================================================================

# Ontology objects (frozen public API)
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

# Factory functions (bridge to OmissionSession)
from .factories import (
    dataset_from_session,
    aligned_dataset_from_dataset,
    epochs_from_aligned_dataset,
    result_from_psth_analysis,
    result_from_tfr_analysis,
    result_from_decoding_analysis,
    figure_from_result,
)

# ============================================================================
# JRSA: Unified Representational Similarity Analysis
# Single public function, single public result type.
# ============================================================================
from .jrsa import jrsa, JRSAResult

# ============================================================================
# LEGACY API (for backwards compatibility)
# ============================================================================

# Import metadata, spiking, and diagnostics functions
from .metadata import (
    get_all_units_metadata,
    classify_unit_quality,
    unit_census_report,
    get_snr_analysis,
    electrode_inventory,
)
from .spiking import (
    compute_response_metrics,
    classify_response_significance,
    classify_omission_response,
    phase_locking_index,
)
from .diagnostics import (
    audit_session,
    compare_sessions,
    print_audit_report,
)

# Category D: Figure generation (comprehensive visualization)
from . import viz
from .viz import (
    raster_suite_omission,
    lfp_tfr_trace_suite_omission,
    lfp_tfr_trace_correlation,
    plot_granger_network_plotly,
)

from .sequence_layout import (
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

# Y-files: New orthogonal jnwb modules (spectral and visualization)
from . import spectral
from . import visual_qc

# Central path resolution (2026-08-08). `oa.paths.describe()` reports every root
# and whether it currently resolves -- run it first after any drive remap.
from . import paths
from .addressing import (
    map_peak_channel_to_area,
    classify_layer_from_depth,
    enrich_units_dataframe
)

# Import analyzers (4 canonical objects)
from .analyzers import (
    TFRAnalyzer,
    UnitAnalyzer,
    PopulationAnalyzer,
)
from .statistics import StatisticalAnalysis

# Import 20 canonical functions
from .functions import (
    # TFR functions (1-5)
    tfr_trial_average,
    tfr_compare_conditions,
    tfr_correlate_areas,
    tfr_spectrolaminar,
    tfr_permutation_test,
    # Raster & PSTH (6-8)
    raster_plot,
    psth_analysis,
    autocorrelogram,
    # Unit finding (9-11)
    find_units,
    unit_quality_scores,
    unit_channel_mapping,
    # Population (12-15)
    pie_charts,
    compare_populations,
    population_by_area,
    network_connectivity,
    # Batch (16-18)
    units_across_sessions,
    lfp_channel_areas,
    summary_report,
    # Advanced (19-20)
    noise_vs_signal,
    cross_modal_comparison,
)

# Import new decoding and connectivity functions
from .decoding import (
    decode_stimulus_identity,
    decode_omission_presence,
)
from .connectivity import (
    spike_mutual_information,
    binary_occupancy_mutual_information,
    spike_count_mutual_information,
    granger_causality,
    network_topology,
    # Generalized directed connectivity (modality-agnostic X/Y contract)
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
from .unit_classification import (
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
from .trajectory import (
    build_time_resolved_matrix,
    compute_population_trajectory,
)
from .report import generate_report

# Export main classes and functions
__all__ = [
    # ========================================================================
    # JRSA: Unified RSA API (new public surface)
    # ========================================================================
    'jrsa',
    'JRSAResult',

    # ========================================================================
    # v1.0.0 PUBLIC API (FROZEN)
    # ========================================================================
    # Core ontology objects (immutable, stable, part of v1.0 contract)
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
    # Factory functions (public interface to ontology)
    'dataset_from_session',
    'aligned_dataset_from_dataset',
    'epochs_from_aligned_dataset',
    'result_from_psth_analysis',
    'result_from_tfr_analysis',
    'result_from_decoding_analysis',
    'figure_from_result',

    # ========================================================================
    # LEGACY API (backwards compatibility)
    # ========================================================================
    # Core
    'read',
    'batch_read',
    'OmissionSession',
    # Metadata extraction (migrated from X-files)
    'get_all_units_metadata',
    'classify_unit_quality',
    'unit_census_report',
    'get_snr_analysis',
    'electrode_inventory',
    # Spiking metrics (migrated from X-files)
    'compute_response_metrics',
    'classify_response_significance',
    'classify_omission_response',
    'phase_locking_index',
    # Diagnostics and QC (migrated from X-files)
    'audit_session',
    'compare_sessions',
    'print_audit_report',
    # Figure generation (Category D: comprehensive visualization)
    'viz',
    'raster_suite_omission',
    'lfp_tfr_trace_suite_omission',
    'lfp_tfr_trace_correlation',
    'plot_granger_network_plotly',
    # Sequence presentation layout (Plotly vector shapes)
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
    # Spectral analysis (Y-file: new orthogonal module)
    'spectral',
    # Visual QC (Y-file: new orthogonal module)
    'visual_qc',
    # New Decoding & Connectivity modules
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
    # 4 Canonical Objects
    'TFRAnalyzer',
    'UnitAnalyzer',
    'PopulationAnalyzer',
    'StatisticalAnalysis',
    # 20 Canonical Functions
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
    'summary_report',
    'noise_vs_signal',
    'cross_modal_comparison',
    'map_peak_channel_to_area',
    'classify_layer_from_depth',
    'enrich_units_dataframe',
]
