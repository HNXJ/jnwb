"""
Session Diagnostics and Quality Control

Consolidates logic from archived X-files:
- check_*.py (10+ diagnostic scripts)
- analyze_comprehensive.py
- analyze_data.py (selected methods)
- audit_figure_registry.py (selected methods)

Provides comprehensive audit functions for validating session integrity,
checking data completeness, and generating QC reports.

_audit_units and _audit_electrodes were promoted 2026-08-23 to jnwb.metadata.audit_units /
audit_electrodes (99%-jnwb-sufficiency normalization) -- they operate on plain units/electrodes
DataFrames with no omission-task coupling. audit_session and _audit_intervals stay here:
_audit_intervals hardcodes the 'stimulus_number' / 'task_condition_number' interval-table
column names, which are this task's paradigm-specific schema, and audit_session hardcodes the
'omission_glo_passive' interval table name.

Author: Migrated from archived scripts
Date: 2026-06-25
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Union
import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO

from jnwb.metadata import audit_units as _audit_units
from jnwb.metadata import audit_electrodes as _audit_electrodes

log = logging.getLogger(__name__)


def audit_session(nwb_path: Union[str, Path]) -> Dict:
    """
    Comprehensive session audit and QC report.

    Validates:
    - Interval completeness (trials per phase/condition)
    - Unit quality distribution
    - SNR statistics
    - Electrode mapping validity
    - Spike time ranges

    Args:
        nwb_path: Path to .nwb file

    Returns:
        Dict with audit results:
        - session_info: Metadata
        - intervals: Coverage by phase/condition
        - units: Quality distribution
        - electrodes: Mapping validation
        - warnings: List of issues found
        - passed: bool (all checks passed)

    Example:
        >>> audit = audit_session('sub-C31o_ses-230823_rec.nwb')
        >>> if not audit['passed']:
        ...     print("Issues found:", audit['warnings'])
    """
    nwb_path = Path(nwb_path)
    report = {
        'nwb_file': nwb_path.name,
        'session_id': nwb_path.stem.split('ses-')[1].split('_')[0] if 'ses-' in nwb_path.stem else 'unknown',
        'passed': True,
        'warnings': [],
        'errors': [],
        'session_info': {},
        'intervals': {},
        'units': {},
        'electrodes': {},
    }

    try:
        with NWBHDF5IO(str(nwb_path), 'r', load_namespaces=True) as io:
            nwb = io.read()

            # Session info
            report['session_info'] = {
                'subject_id': nwb.subject.subject_id if nwb.subject else 'unknown',
                'session_start': str(nwb.session_start_time),
                'session_description': nwb.session_description,
            }

            # Check intervals
            if 'omission_glo_passive' in nwb.intervals:
                intervals_df = nwb.intervals['omission_glo_passive'].to_dataframe()
                report['intervals'] = _audit_intervals(intervals_df)
            else:
                report['warnings'].append("Missing 'omission_glo_passive' interval table")

            # Check units
            if nwb.units is not None:
                units_df = nwb.units.to_dataframe()
                report['units'] = _audit_units(units_df)
            else:
                report['warnings'].append("No units found in session")

            # Check electrodes
            if nwb.electrodes is not None:
                elec_df = nwb.electrodes.to_dataframe()
                report['electrodes'] = _audit_electrodes(elec_df, units_df if nwb.units else None)
            else:
                report['warnings'].append("No electrodes found in session")

    except Exception as e:
        report['errors'].append(str(e))
        report['passed'] = False
        log.error(f"Audit failed for {nwb_path.name}: {e}")
        return report

    # Summary: mark as failed if warnings exist (strict QC)
    report['passed'] = len(report['warnings']) == 0 and len(report['errors']) == 0

    return report


def _audit_intervals(intervals_df: pd.DataFrame) -> Dict:
    """Audit interval table completeness."""
    result = {
        'total_intervals': len(intervals_df),
        'correct_count': 0,
        'by_phase': {},
        'by_condition': {},
    }

    if 'correct' in intervals_df.columns:
        result['correct_count'] = (pd.to_numeric(intervals_df['correct'], errors='coerce') == 1.0).sum()

    # By phase
    if 'stimulus_number' in intervals_df.columns:
        phases = pd.to_numeric(intervals_df['stimulus_number'], errors='coerce').dropna().unique()
        for phase in sorted([int(p) for p in phases if not np.isnan(p)]):
            count = (pd.to_numeric(intervals_df['stimulus_number'], errors='coerce') == float(phase)).sum()
            result['by_phase'][f'phase_{int(phase)}'] = int(count)

    # By condition
    if 'task_condition_number' in intervals_df.columns:
        conditions = pd.to_numeric(intervals_df['task_condition_number'], errors='coerce').dropna().unique()
        for cond in sorted([int(c) for c in conditions if not np.isnan(c)]):
            count = (pd.to_numeric(intervals_df['task_condition_number'], errors='coerce') == float(cond)).sum()
            result['by_condition'][f'condition_{int(cond)}'] = int(count)

    return result


def compare_sessions(nwb_paths: list) -> pd.DataFrame:
    """
    Compare audit results across multiple sessions.

    Args:
        nwb_paths: List of NWB file paths

    Returns:
        DataFrame with one row per session, columns with audit metrics

    Example:
        >>> comparison = compare_sessions(['session1.nwb', 'session2.nwb', ...])
        >>> print(comparison[['session_id', 'total_units', 'snr_mean']])
    """
    rows = []

    for nwb_path in nwb_paths:
        audit = audit_session(nwb_path)

        row = {
            'session_id': audit['session_id'],
            'nwb_file': audit['nwb_file'],
            'total_intervals': audit['intervals'].get('total_intervals', 0),
            'correct_intervals': audit['intervals'].get('correct_count', 0),
            'total_units': audit['units'].get('total_units', 0),
            'units_with_spikes': audit['units'].get('units_with_spike_times', 0),
            'quality_mean': audit['units'].get('quality_distribution', {}).get('mean', np.nan),
            'snr_mean': audit['units'].get('snr_stats', {}).get('mean', np.nan),
            'snr_good_rate': audit['units'].get('snr_stats', {}).get('good_rate', np.nan),
            'firing_rate_mean': audit['units'].get('firing_rate_stats', {}).get('mean', np.nan),
            'total_electrodes': audit['electrodes'].get('total_electrodes', 0),
            'units_assigned': audit['electrodes'].get('units_assigned', 0),
            'passed': audit['passed'],
        }

        rows.append(row)

    return pd.DataFrame(rows)


def print_audit_report(audit: Dict, verbose: bool = False) -> None:
    """
    Pretty-print audit report.

    Args:
        audit: Dict from audit_session()
        verbose: If True, print detailed statistics

    Example:
        >>> audit = audit_session('nwb_path')
        >>> print_audit_report(audit)
    """
    print(f"\n{'='*60}")
    print(f"Audit Report: {audit['nwb_file']}")
    print(f"{'='*60}")

    print(f"\nSession ID: {audit['session_id']}")
    print(f"Status: {'✓ PASSED' if audit['passed'] else '✗ FAILED'}")

    if audit['warnings']:
        print(f"\nWarnings ({len(audit['warnings'])}):")
        for w in audit['warnings']:
            print(f"  • {w}")

    if audit['errors']:
        print(f"\nErrors ({len(audit['errors'])}):")
        for e in audit['errors']:
            print(f"  ✗ {e}")

    if verbose:
        print(f"\nIntervals: {audit['intervals'].get('total_intervals', 'N/A')} total")
        print(f"  Correct trials: {audit['intervals'].get('correct_count', 0)}")

        print(f"\nUnits: {audit['units'].get('total_units', 'N/A')} total")
        if audit['units'].get('quality_distribution'):
            qc = audit['units']['quality_distribution']
            print(f"  Quality: mean={qc['mean']:.2f}, good={qc['good_count']}")

        if audit['units'].get('snr_stats'):
            snr = audit['units']['snr_stats']
            print(f"  SNR: mean={snr['mean']:.2f}, good_rate={snr['good_rate']:.1%}")

        print(f"\nElectrodes: {audit['electrodes'].get('total_electrodes', 'N/A')} total")
        if audit['electrodes'].get('areas_represented'):
            areas = audit['electrodes']['areas_represented']
            print(f"  Areas: {', '.join(f'{a}({c})' for a, c in areas.items())}")
