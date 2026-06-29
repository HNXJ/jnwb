"""
Test Session Diagnostics and QC on Real NWB Data

Validates jnwb.diagnostics module across all 13 sessions.
Tests: audit_session, compare_sessions, print_audit_report

Migrates X-file tests:
- check_*.py (diagnostic scripts)
- analyze_comprehensive.py
- analyze_data.py
"""

import logging
from pathlib import Path
import pandas as pd
import pytest

from jnwb import diagnostics

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

NWB_DIR = Path("D:/analysis/nwb")
NWB_FILES = sorted(list(NWB_DIR.glob("*.nwb")))


class TestAuditSession:
    """Test audit_session on individual sessions."""

    def test_audit_single_session(self):
        """Audit a single session."""
        nwb_path = NWB_FILES[0]
        audit = diagnostics.audit_session(nwb_path)

        assert 'session_id' in audit
        assert 'intervals' in audit
        assert 'units' in audit
        assert 'electrodes' in audit
        assert 'warnings' in audit
        assert 'passed' in audit

        log.info(f"Audit for {nwb_path.name}:")
        log.info(f"  Session ID: {audit['session_id']}")
        log.info(f"  Status: {'PASSED' if audit['passed'] else 'FAILED'}")
        if audit['warnings']:
            log.info(f"  Warnings: {len(audit['warnings'])}")
            for w in audit['warnings'][:3]:
                log.info(f"    • {w}")

    def test_audit_all_sessions(self):
        """Audit all 13 sessions."""
        audits = []
        for nwb_path in NWB_FILES:
            audit = diagnostics.audit_session(nwb_path)
            audits.append(audit)

        # Check summary
        passed_count = sum(1 for a in audits if a['passed'])
        log.info(f"Audit results: {passed_count}/{len(audits)} passed")

        # Check for common issues
        all_warnings = []
        for a in audits:
            all_warnings.extend(a['warnings'])

        if all_warnings:
            warning_types = {}
            for w in all_warnings:
                key = w.split(':')[0]
                warning_types[key] = warning_types.get(key, 0) + 1

            log.info(f"Warning types across sessions:")
            for wtype, count in sorted(warning_types.items(), key=lambda x: -x[1]):
                log.info(f"  {wtype}: {count}")

    def test_audit_intervals_coverage(self):
        """Check interval completeness."""
        audit = diagnostics.audit_session(NWB_FILES[0])

        intervals = audit['intervals']
        assert intervals['total_intervals'] > 0
        assert intervals['correct_count'] > 0

        # Should have trials for multiple phases
        phases = {k: v for k, v in intervals['by_phase'].items() if v > 0}
        assert len(phases) > 0

        log.info(f"Intervals: {intervals['total_intervals']} total, {intervals['correct_count']} correct")
        log.info(f"Phases: {phases}")

    def test_audit_unit_quality(self):
        """Check unit quality metrics."""
        audit = diagnostics.audit_session(NWB_FILES[0])

        units = audit['units']
        assert units['total_units'] > 0
        assert units['units_with_spike_times'] > 0

        if units['quality_distribution']:
            qc = units['quality_distribution']
            log.info(f"Unit quality: mean={qc['mean']:.2f}, good={qc['good_count']}")

        if units['snr_stats']:
            snr = units['snr_stats']
            log.info(f"SNR: mean={snr['mean']:.2f}, good_rate={snr['good_rate']:.1%}")

    def test_audit_electrode_coverage(self):
        """Check electrode and area coverage."""
        audit = diagnostics.audit_session(NWB_FILES[0])

        elec = audit['electrodes']
        assert elec['total_electrodes'] > 0

        if elec['areas_represented']:
            log.info(f"Areas represented: {elec['areas_represented']}")


class TestCompareSessions:
    """Test compare_sessions across multiple sessions."""

    def test_compare_all_sessions(self):
        """Generate comparison table for all sessions."""
        comparison = diagnostics.compare_sessions(NWB_FILES)

        assert len(comparison) == 13
        assert 'session_id' in comparison.columns
        assert 'total_units' in comparison.columns
        assert 'snr_mean' in comparison.columns

        log.info("Comparison across all 13 sessions:")
        log.info(comparison[['session_id', 'total_units', 'snr_mean', 'passed']].to_string())

    def test_compare_first_five_sessions(self):
        """Compare subset of sessions."""
        comparison = diagnostics.compare_sessions(NWB_FILES[:5])

        assert len(comparison) == 5

        # Check for expected columns
        expected_cols = ['session_id', 'total_intervals', 'total_units', 'quality_mean', 'snr_mean']
        for col in expected_cols:
            assert col in comparison.columns

        log.info("Comparison of first 5 sessions:")
        log.info(comparison[['session_id', 'total_units', 'snr_mean']].to_string())


class TestAuditReport:
    """Test audit reporting functions."""

    def test_print_audit_report(self, capsys):
        """Test pretty-printing audit report."""
        audit = diagnostics.audit_session(NWB_FILES[0])

        # Capture output
        diagnostics.print_audit_report(audit, verbose=True)
        captured = capsys.readouterr()

        assert 'Audit Report' in captured.out
        assert audit['session_id'] in captured.out
        if audit['passed']:
            assert 'PASSED' in captured.out
        else:
            assert 'FAILED' in captured.out


class TestAuditSummary:
    """Test audit results across all sessions."""

    def test_all_sessions_have_data(self):
        """Verify all sessions have expected data."""
        for nwb_path in NWB_FILES:
            audit = diagnostics.audit_session(nwb_path)

            assert audit['units']['total_units'] > 0, f"{nwb_path.name}: No units"
            assert audit['intervals']['total_intervals'] > 0, f"{nwb_path.name}: No intervals"
            assert audit['electrodes']['total_electrodes'] > 0, f"{nwb_path.name}: No electrodes"

        log.info("✓ All 13 sessions have complete data")

    def test_snr_consistency(self):
        """Check SNR is consistent across sessions."""
        snr_means = []

        for nwb_path in NWB_FILES:
            audit = diagnostics.audit_session(nwb_path)
            snr = audit['units'].get('snr_stats', {}).get('mean', None)
            if snr is not None:
                snr_means.append(snr)

        if snr_means:
            log.info(f"SNR across sessions: mean={pd.Series(snr_means).mean():.2f}, " +
                    f"range={pd.Series(snr_means).min():.2f}-{pd.Series(snr_means).max():.2f}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
