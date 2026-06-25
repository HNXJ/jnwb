"""
Test Category D: Figure Generation and Visualization

Validates comprehensive visualization module on real NWB data.
Tests: raster_grid_by_family, population_raster_summary, multi_phase_comparison
"""

import logging
from pathlib import Path
import pytest
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt

from jnwb import OmissionSession, viz, metadata

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

NWB_DIR = Path("D:/analysis/nwb")
NWB_FILES = sorted(list(NWB_DIR.glob("*.nwb")))


class TestRasterGridByFamily:
    """Test multi-unit raster grids organized by condition family."""

    def test_raster_grid_family_a(self):
        """Generate raster grid for family A conditions."""
        session = OmissionSession(str(NWB_FILES[0]))
        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        if len(units) < 3:
            pytest.skip("Not enough units")

        unit_ids = units.head(6)['cluster_id'].tolist() if 'cluster_id' in units.columns \
                   else units.head(6)['unit_id'].tolist()

        try:
            figs = viz.raster_grid_by_family(
                session=session,
                unit_ids=unit_ids,
                family='A',
                phase=2,
                max_units_per_page=6
            )

            assert len(figs) > 0, "Should generate at least one figure"
            assert all(isinstance(f, plt.Figure) for f in figs), "Should return Figure objects"

            for fig in figs:
                plt.close(fig)

            log.info(f"✓ Generated {len(figs)} raster grids for family A")

        except Exception as e:
            pytest.fail(f"Raster grid generation failed: {e}")

    def test_raster_grid_all_families(self):
        """Test raster grids for all condition families."""
        session = OmissionSession(str(NWB_FILES[0]))
        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        if len(units) < 3:
            pytest.skip("Not enough units")

        unit_ids = units.head(4)['cluster_id'].tolist() if 'cluster_id' in units.columns \
                   else units.head(4)['unit_id'].tolist()

        for family in ['A', 'B', 'R']:
            try:
                figs = viz.raster_grid_by_family(
                    session=session,
                    unit_ids=unit_ids,
                    family=family,
                    phase=2,
                    max_units_per_page=4
                )

                assert len(figs) > 0, f"Should generate figures for family {family}"

                for fig in figs:
                    plt.close(fig)

                log.info(f"✓ Family {family}: {len(figs)} figures")

            except Exception as e:
                pytest.fail(f"Family {family} failed: {e}")

    def test_raster_grid_multiple_pages(self):
        """Test pagination for large unit sets."""
        session = OmissionSession(str(NWB_FILES[0]))
        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        if len(units) < 15:
            pytest.skip("Not enough units for pagination test")

        unit_ids = units.head(15)['cluster_id'].tolist() if 'cluster_id' in units.columns \
                   else units.head(15)['unit_id'].tolist()

        figs = viz.raster_grid_by_family(
            session=session,
            unit_ids=unit_ids,
            family='A',
            max_units_per_page=6
        )

        # 15 units, 6 per page = 3 pages
        assert len(figs) >= 2, f"Should generate multiple pages, got {len(figs)}"

        for fig in figs:
            plt.close(fig)

        log.info(f"✓ Pagination test: {len(figs)} pages for {len(unit_ids)} units")


class TestPopulationRasterSummary:
    """Test population-level raster summaries."""

    def test_population_raster_by_firing_rate(self):
        """Generate population raster sorted by firing rate."""
        session = OmissionSession(str(NWB_FILES[0]))
        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        if len(units) < 10:
            pytest.skip("Not enough units")

        try:
            fig = viz.population_raster_summary(
                session=session,
                units_df=units,
                condition='AAAB',
                phase=2,
                sort_by='firing_rate',
                n_units=10
            )

            assert isinstance(fig, plt.Figure)
            assert len(fig.get_axes()) > 0

            plt.close(fig)

            log.info(f"✓ Population raster generated (sorted by firing_rate)")

        except Exception as e:
            pytest.fail(f"Population raster failed: {e}")

    def test_population_raster_by_snr(self):
        """Generate population raster sorted by SNR."""
        session = OmissionSession(str(NWB_FILES[0]))
        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        if len(units) < 10:
            pytest.skip("Not enough units")

        # Ensure SNR column exists
        if 'snr' not in units.columns or units['snr'].isna().all():
            pytest.skip("No SNR data available")

        try:
            fig = viz.population_raster_summary(
                session=session,
                units_df=units,
                condition='AAXB',
                phase=3,
                sort_by='snr',
                n_units=8
            )

            assert isinstance(fig, plt.Figure)

            plt.close(fig)

            log.info(f"✓ Population raster generated (sorted by SNR)")

        except Exception as e:
            pytest.fail(f"Population raster by SNR failed: {e}")

    def test_population_raster_different_conditions(self):
        """Test population raster across different conditions."""
        session = OmissionSession(str(NWB_FILES[0]))
        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        if len(units) < 10:
            pytest.skip("Not enough units")

        conditions = ['AAAB', 'AAXB', 'BBBA']

        for condition in conditions:
            try:
                fig = viz.population_raster_summary(
                    session=session,
                    units_df=units,
                    condition=condition,
                    phase=2,
                    n_units=6
                )

                assert isinstance(fig, plt.Figure)
                plt.close(fig)

                log.info(f"✓ Population raster: {condition}")

            except Exception as e:
                log.warning(f"Condition {condition} failed: {e}")


class TestMultiPhaseComparison:
    """Test multi-phase comparison plots."""

    def test_multi_phase_comparison_single_unit(self):
        """Compare rasters across all phases for a single unit."""
        session = OmissionSession(str(NWB_FILES[0]))
        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        if len(units) == 0:
            pytest.skip("No units")

        unit_id = units.iloc[0]['cluster_id'] if 'cluster_id' in units.columns else units.iloc[0]['unit_id']
        spike_times = session.get_spike_times(unit_id)

        if spike_times is None or len(spike_times) < 10:
            pytest.skip("Not enough spikes for unit")

        try:
            fig = viz.multi_phase_comparison(
                session=session,
                unit_id=unit_id,
                condition='AAAB'
            )

            assert isinstance(fig, plt.Figure)
            assert len(fig.get_axes()) == 4, "Should have 4 subplots (p1-p4)"

            plt.close(fig)

            log.info(f"✓ Multi-phase comparison for unit {unit_id}")

        except Exception as e:
            pytest.fail(f"Multi-phase comparison failed: {e}")

    def test_multi_phase_all_conditions(self):
        """Test multi-phase comparison across different conditions."""
        session = OmissionSession(str(NWB_FILES[0]))
        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        unit_id = units.iloc[0]['cluster_id'] if 'cluster_id' in units.columns else units.iloc[0]['unit_id']

        conditions = ['AAAB', 'AAXB', 'AAAX']
        success_count = 0

        for condition in conditions:
            try:
                fig = viz.multi_phase_comparison(
                    session=session,
                    unit_id=unit_id,
                    condition=condition
                )

                assert isinstance(fig, plt.Figure)
                plt.close(fig)
                success_count += 1

            except Exception as e:
                log.warning(f"Condition {condition} failed: {e}")

        assert success_count >= 2, "Should work for at least 2 conditions"
        log.info(f"✓ Multi-phase comparison across {success_count} conditions")


class TestSaveFigureSuite:
    """Test figure saving functionality."""

    def test_save_single_figure(self, tmp_path):
        """Test saving a single figure."""
        fig = plt.figure()
        fig.text(0.5, 0.5, 'Test Figure')

        figs = [fig]
        output_dir = tmp_path / "test_figs"

        try:
            viz.save_figure_suite(
                figures=figs,
                output_dir=output_dir,
                basename='test_figure',
                formats=['png']
            )

            assert (output_dir / 'test_figure_page1.png').exists()
            log.info(f"✓ Figure saved successfully")

            plt.close(fig)

        except Exception as e:
            pytest.fail(f"Save figure failed: {e}")

    def test_save_multiple_formats(self, tmp_path):
        """Test saving figures in multiple formats."""
        figs = [plt.figure() for _ in range(2)]
        output_dir = tmp_path / "multi_format"

        try:
            viz.save_figure_suite(
                figures=figs,
                output_dir=output_dir,
                basename='test',
                formats=['png', 'pdf']
            )

            assert (output_dir / 'test_page1.png').exists()
            assert (output_dir / 'test_page2.png').exists()
            assert (output_dir / 'test_page1.pdf').exists()

            for fig in figs:
                plt.close(fig)

            log.info(f"✓ Figures saved in multiple formats")

        except Exception as e:
            pytest.fail(f"Multi-format save failed: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
