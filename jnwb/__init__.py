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
Version: 2.0.0
"""

__version__ = '2.0.0'
__release_date__ = '2026-08-19'
__author__ = 'Claude Code'
__status__ = 'Stable - Public API Frozen (moved omission-specific pieces to omission/, 2026-08-19)'

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
]
