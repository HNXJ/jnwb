"""
Test Figure Generation Functions on Real NWB Data

Validates jnwb raster_plot() and psth_analysis() against real spike times.
Prepares for Category D integration and spectral pipeline coordination.
"""

import logging
from pathlib import Path
import numpy as np
import pytest
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for testing
import matplotlib.pyplot as plt

from omission import OmissionSession, raster_plot, psth_analysis
from omission.jnwb_ext import metadata

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

NWB_DIR = Path("D:/analysis/nwb")
NWB_FILES = sorted(list(NWB_DIR.glob("*.nwb")))


class TestRasterPlot:
    """Test raster_plot on real spike data."""

    def test_raster_plot_single_unit_single_condition(self):
        """Plot raster for single unit, single condition."""
        session = OmissionSession(str(NWB_FILES[0]))
        epochs = session.get_epochs(phase=2, condition='AAAB', correct_only=True)

        if len(epochs) == 0:
            pytest.skip("No AAAB epochs")

        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))
        if len(units) == 0:
            pytest.skip("No units")

        unit_id = units.iloc[0]['cluster_id'] if 'cluster_id' in units.columns else units.iloc[0]['unit_id']
        spike_times = session.get_spike_times(unit_id)

        if spike_times is None or len(spike_times) == 0:
            pytest.skip(f"Unit {unit_id} has no spikes")

        # Generate raster using jnwb API
        try:
            result = raster_plot(
                session=session,
                unit_id=unit_id,
                condition='AAAB',
                phase=2,
                window_ms=(-500, 1000)
            )

            assert isinstance(result, dict)
            assert 'error' not in result or result['error'] is None

            log.info(f"✓ Raster plot generated for unit {unit_id}")
            log.info(f"  Data keys: {list(result.keys())}")

        except Exception as e:
            pytest.fail(f"Raster plot failed: {e}")

    def test_raster_plot_multiple_units(self):
        """Plot rasters for multiple units."""
        session = OmissionSession(str(NWB_FILES[0]))
        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        unit_count = 0
        for idx, unit_row in units.head(5).iterrows():
            unit_id = unit_row['cluster_id'] if 'cluster_id' in unit_row.index else unit_row['unit_id']
            spike_times = session.get_spike_times(unit_id)

            if spike_times is None or len(spike_times) == 0:
                continue

            try:
                result = raster_plot(
                    session=session,
                    unit_id=unit_id,
                    condition='AAAB',
                    phase=2
                )

                assert isinstance(result, dict)
                if 'error' not in result or result['error'] is None:
                    unit_count += 1

            except Exception as e:
                log.warning(f"Failed for unit {unit_id}: {e}")

        assert unit_count >= 2, "Should generate rasters for at least 2 units"
        log.info(f"✓ Generated rasters for {unit_count} units")

    def test_raster_plot_all_conditions(self):
        """Test raster across different conditions."""
        session = OmissionSession(str(NWB_FILES[0]))
        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        if len(units) == 0:
            pytest.skip("No units")

        unit_id = units.iloc[0]['cluster_id'] if 'cluster_id' in units.columns else units.iloc[0]['unit_id']

        conditions = ['AAAB', 'AAXB', 'AAAX', 'BBBA']
        success_count = 0

        for condition in conditions:
            try:
                result = raster_plot(
                    session=session,
                    unit_id=unit_id,
                    condition=condition,
                    phase=2
                )

                if isinstance(result, dict) and ('error' not in result or result['error'] is None):
                    success_count += 1

            except Exception as e:
                log.warning(f"Failed for {condition}: {e}")

        log.info(f"✓ Raster plots generated for {success_count}/{len(conditions)} conditions")
        assert success_count >= 2, "Should work for at least 2 conditions"


class TestPSTHAnalysis:
    """Test psth_analysis on real spike data."""

    def test_psth_single_unit_single_condition(self):
        """Generate PSTH for single unit, single condition."""
        session = OmissionSession(str(NWB_FILES[0]))
        epochs = session.get_epochs(phase=2, condition='AAAB', correct_only=True)

        if len(epochs) == 0:
            pytest.skip("No AAAB epochs")

        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))
        if len(units) == 0:
            pytest.skip("No units")

        unit_id = units.iloc[0]['cluster_id'] if 'cluster_id' in units.columns else units.iloc[0]['unit_id']
        spike_times = session.get_spike_times(unit_id)

        if spike_times is None or len(spike_times) == 0:
            pytest.skip("No spikes")

        # Generate PSTH using jnwb API
        try:
            result = psth_analysis(
                session=session,
                unit_id=unit_id,
                condition='AAAB',
                phase=2,
                bin_size_ms=50
            )

            assert isinstance(result, dict)
            assert 'error' not in result or result['error'] is None

            log.info(f"✓ PSTH generated for unit {unit_id}")
            log.info(f"  Data keys: {list(result.keys())}")

        except Exception as e:
            pytest.fail(f"PSTH analysis failed: {e}")

    def test_psth_multiple_units(self):
        """Generate PSTHs for multiple units."""
        session = OmissionSession(str(NWB_FILES[0]))
        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        unit_count = 0
        for idx, unit_row in units.head(5).iterrows():
            unit_id = unit_row['cluster_id'] if 'cluster_id' in unit_row.index else unit_row['unit_id']
            spike_times = session.get_spike_times(unit_id)

            if spike_times is None or len(spike_times) == 0:
                continue

            try:
                result = psth_analysis(
                    session=session,
                    unit_id=unit_id,
                    condition='AAAB',
                    phase=2
                )

                assert isinstance(result, dict)
                if 'error' not in result or result['error'] is None:
                    unit_count += 1

            except Exception as e:
                log.warning(f"Failed for unit {unit_id}: {e}")

        assert unit_count >= 2, "Should generate PSTHs for at least 2 units"
        log.info(f"✓ Generated PSTHs for {unit_count} units")

    def test_psth_all_conditions(self):
        """Test PSTH across different conditions."""
        session = OmissionSession(str(NWB_FILES[0]))
        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        if len(units) == 0:
            pytest.skip("No units")

        unit_id = units.iloc[0]['cluster_id'] if 'cluster_id' in units.columns else units.iloc[0]['unit_id']

        conditions = ['AAAB', 'AAXB', 'AAAX', 'BBBA']
        success_count = 0

        for condition in conditions:
            try:
                result = psth_analysis(
                    session=session,
                    unit_id=unit_id,
                    condition=condition,
                    phase=2
                )

                if isinstance(result, dict) and ('error' not in result or result['error'] is None):
                    success_count += 1

            except Exception as e:
                log.warning(f"Failed for {condition}: {e}")

        log.info(f"✓ PSTH generated for {success_count}/{len(conditions)} conditions")
        assert success_count >= 2, "Should work for at least 2 conditions"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
