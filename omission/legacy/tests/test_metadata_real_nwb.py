"""
Test Unit Metadata Extraction on Real NWB Files

Validates the new omission.jnwb_ext.metadata module functions against all 13 NWB sessions.
Tests: get_all_units_metadata, classify_unit_quality, unit_census_report, get_snr_analysis, electrode_inventory

Migrates X-file tests:
- build_comprehensive_grand_table.py
- build_dataset_census.py
- classify_units_s_s_o.py
- check_quality_*.py
- check_snr*.py
"""

import logging
from pathlib import Path
import pandas as pd
import pytest

from omission.jnwb_ext import metadata

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

NWB_DIR = Path("D:/analysis/nwb")
NWB_FILES = sorted(list(NWB_DIR.glob("*.nwb")))

log.info(f"Found {len(NWB_FILES)} NWB files for testing")


class TestMetadataExtraction:
    """Test get_all_units_metadata on real NWB data."""

    def test_get_all_units_metadata_single_session(self):
        """Extract units from a single session."""
        nwb_path = NWB_FILES[0]
        units = metadata.get_all_units_metadata(nwb_path)

        assert len(units) > 0, "No units extracted"
        assert 'session_id' in units.columns
        assert 'cluster_id' in units.columns or 'unit_id' in units.columns
        assert 'area' in units.columns
        assert 'layer' in units.columns

        log.info(f"  {nwb_path.name}: {len(units)} units")
        log.info(f"  Areas: {units['area'].unique()}")
        log.info(f"  Layers: {units['layer'].unique()}")

    def test_get_all_units_metadata_all_sessions(self):
        """Extract units from all 13 sessions."""
        units = metadata.get_all_units_metadata(NWB_FILES)

        assert len(units) > 0, "No units extracted from any session"
        assert len(units['session_id'].unique()) == 13, "Not all 13 sessions loaded"

        # Expected: ~6,040 total units across all sessions
        assert len(units) >= 5000, f"Expected ~6000 units, got {len(units)}"

        log.info(f"Total units: {len(units)}")
        log.info(f"Units per session: min={units.groupby('session_id').size().min()}, " +
                 f"max={units.groupby('session_id').size().max()}")

    def test_get_all_units_metadata_with_quality_filter(self):
        """Extract only high-quality units."""
        all_units = metadata.get_all_units_metadata(NWB_FILES)
        filtered_units = metadata.get_all_units_metadata(
            NWB_FILES,
            filter_quality=True,
            quality_threshold=1.0
        )

        assert len(filtered_units) <= len(all_units)
        assert len(filtered_units) > 0, "No units passed quality filter"

        log.info(f"All units: {len(all_units)}")
        log.info(f"Quality >= 1.0: {len(filtered_units)} ({len(filtered_units)/len(all_units):.1%})")

    def test_area_enrichment(self):
        """Verify area information is correctly enriched from electrodes."""
        units = metadata.get_all_units_metadata(NWB_FILES[0])

        # Should have area assignments for most units
        units_with_area = units[units['area'].notna()].shape[0]
        assert units_with_area > 0, "No units have area assignment"

        log.info(f"Units with area: {units_with_area}/{len(units)} ({units_with_area/len(units):.1%})")
        log.info(f"Areas found: {sorted(units['area'].dropna().unique())}")


class TestUnitClassification:
    """Test classify_unit_quality."""

    def test_classify_unit_quality_basic(self):
        """Classify units by quality metrics."""
        units = metadata.get_all_units_metadata(NWB_FILES[0])
        classified = metadata.classify_unit_quality(units)

        assert 'quality_class' in classified.columns
        assert 'is_valid' in classified.columns
        assert 'issue_flags' in classified.columns

        log.info(f"Quality distribution:")
        for qc in ['Good', 'Fair', 'Poor']:
            count = (classified['quality_class'] == qc).sum()
            log.info(f"  {qc}: {count}")

    def test_classify_unit_quality_custom_thresholds(self):
        """Classify with custom thresholds."""
        units = metadata.get_all_units_metadata(NWB_FILES[0])
        thresholds = {'quality': 0.5, 'snr': 0.5}

        classified = metadata.classify_unit_quality(units, thresholds=thresholds)

        # More units should pass with lower thresholds
        good_count = (classified['quality_class'] == 'Good').sum()
        assert good_count > 0

        log.info(f"Units passing custom thresholds: {good_count}")


class TestCensusReport:
    """Test unit_census_report."""

    def test_census_by_session_area(self):
        """Generate census grouped by session and area."""
        units = metadata.get_all_units_metadata(NWB_FILES)
        census = metadata.unit_census_report(units, group_by=['session_id', 'area'])

        assert len(census) > 0, "No census entries"
        assert 'n_units' in census.columns
        assert 'firing_rate_mean' in census.columns

        log.info(f"Census entries: {len(census)}")
        log.info(f"Sample census:\n{census.head(10)}")

    def test_census_by_area_only(self):
        """Generate census grouped by area only."""
        units = metadata.get_all_units_metadata(NWB_FILES)
        census = metadata.unit_census_report(units, group_by=['area'])

        assert len(census) > 0
        total_units = census['n_units'].sum()
        assert total_units == len(units), "Census units don't match total"

        log.info(f"Units by area:\n{census}")


class TestSNRAnalysis:
    """Test get_snr_analysis."""

    def test_snr_analysis_basic(self):
        """Analyze SNR distribution."""
        units = metadata.get_all_units_metadata(NWB_FILES)
        snr_stats = metadata.get_snr_analysis(units, snr_threshold=1.0)

        assert 'snr_mean' in snr_stats
        assert 'pass_rate' in snr_stats

        log.info(f"SNR statistics:")
        log.info(f"  Mean: {snr_stats.get('snr_mean', 'N/A'):.3f}")
        log.info(f"  Median: {snr_stats.get('snr_median', 'N/A'):.3f}")
        log.info(f"  Pass rate (SNR>1.0): {snr_stats.get('pass_rate', 0):.1%}")

    def test_snr_analysis_by_session(self):
        """Analyze SNR with per-session breakdown."""
        units = metadata.get_all_units_metadata(NWB_FILES)
        snr_stats = metadata.get_snr_analysis(units, detail=True)

        assert 'by_session' in snr_stats

        for session, sess_stats in snr_stats.get('by_session', {}).items():
            log.info(f"  Session {session}: {sess_stats['n']} units, " +
                    f"pass_rate={sess_stats['pass_rate']:.1%}")


class TestElectrodeInventory:
    """Test electrode_inventory."""

    def test_electrode_inventory_single_session(self):
        """Build electrode inventory from a single session."""
        inv = metadata.electrode_inventory(NWB_FILES[0])

        assert len(inv) > 0, "No electrodes in inventory"
        assert 'session_id' in inv.columns
        assert 'n_units_on_channel' in inv.columns

        log.info(f"Electrodes: {len(inv)}")
        log.info(f"Channels with units: {(inv['n_units_on_channel'] > 0).sum()}")

    def test_electrode_inventory_all_sessions(self):
        """Build electrode inventory from all sessions."""
        inv = metadata.electrode_inventory(NWB_FILES)

        assert len(inv) > 0
        assert len(inv['session_id'].unique()) == 13

        # Check unit assignments
        total_unit_slots = inv['n_units_on_channel'].sum()
        log.info(f"Total channels: {len(inv)}")
        log.info(f"Total unit assignments: {total_unit_slots}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
