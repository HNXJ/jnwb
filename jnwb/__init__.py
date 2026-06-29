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

Core Classes:
    - OmissionSession: Main interface for all analysis
      Methods: trial_averaged_plot, channel_averaged_plot, spectrolaminar_motif,
               find_single_units, channel_unit_mapping, lfp_channel_areas,
               tfr_from_preprocessed, plot_tfr, raster_suite, pie_charts,
               get_units, get_electrodes, get_epochs

Functions:
    - read(nwb_path, context): Load NWB file as OmissionSession
    - batch_read(nwb_dir, pattern): Load multiple sessions

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
        >>> sessions = oa.batch_read('D:/analysis/nwb')
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
)

# Y-files: New orthogonal jnwb modules (spectral and visualization)
from . import spectral
from . import visual_qc
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

# Export main classes and functions
__all__ = [
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
    # Spectral analysis (Y-file: new orthogonal module)
    'spectral',
    # Visual QC (Y-file: new orthogonal module)
    'visual_qc',
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
    'summary_report',
    'noise_vs_signal',
    'cross_modal_comparison',
    'map_peak_channel_to_area',
    'classify_layer_from_depth',
    'enrich_units_dataframe',
]
