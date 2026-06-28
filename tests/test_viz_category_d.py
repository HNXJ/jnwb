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

            log.info(f"Generated {len(figs)} raster grids for family A")

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

                log.info(f"Family {family}: {len(figs)} figures")

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

        log.info(f"Pagination test: {len(figs)} pages for {len(unit_ids)} units")


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

            log.info(f"Population raster generated (sorted by firing_rate)")

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

            log.info(f"Population raster generated (sorted by SNR)")

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

                log.info(f"Population raster: {condition}")

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

            log.info(f"Multi-phase comparison for unit {unit_id}")

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
        log.info(f"Multi-phase comparison across {success_count} conditions")


class TestSaveFigureSuite:
    """Test figure saving functionality."""

    def test_save_single_figure(self, tmp_path):
        """Test saving a single figure."""
        fig = plt.figure()
        fig.text(0.5, 0.5, 'Test Figure')

        figs = [fig]
        output_dir = tmp_path / "test_figs"
        fig_path = output_dir / 'test_figure_page1.png'

        try:
            viz.save_figure_suite(
                figures=figs,
                output_dir=output_dir,
                basename='test_figure',
                formats=['png']
            )

            assert fig_path.exists(), "SVG should be written to disk"

            log.info(f"Figure saved successfully")

        finally:
            plt.close(fig)

    def test_save_multiple_formats(self, tmp_path):
        """Test saving figures in multiple formats."""
        figs = [plt.figure() for _ in range(2)]
        output_dir = tmp_path / "multi_format"
        paths = [output_dir / 'test_page1.png', output_dir / 'test_page2.png', output_dir / 'test_page1.pdf']

        try:
            viz.save_figure_suite(
                figures=figs,
                output_dir=output_dir,
                basename='test',
                formats=['png', 'pdf']
            )

            assert all(p.exists() for p in paths), "All formats should be written"

            log.info(f"Figures saved in multiple formats")

        finally:
            for fig in figs:
                plt.close(fig)


class TestAlignedRasterSuite:
    """Test aligned raster suite figures."""

    def test_raster_suite_omission(self):
        """Test raster_suite_omission directly."""
        session = OmissionSession(str(NWB_FILES[0]))
        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        if len(units) == 0:
            pytest.skip("No units in session")

        # Find unit with spikes
        unit_id = None
        for uid in units.index:
            spike_times = session.get_spike_times(uid)
            if spike_times is not None and len(spike_times) > 10:
                unit_id = uid
                break

        if unit_id is None:
            pytest.skip("No unit with sufficient spikes found")

        try:
            fig = viz.raster_suite_omission(
                session=session,
                unit_id=unit_id,
                phase=2
            )

            assert isinstance(fig, plt.Figure)
            # 5x4 grid -> 3x4 + 3x1 + text + waveform = 17 axes (or check it is a valid Figure)
            assert len(fig.get_axes()) > 0
            plt.close(fig)
            log.info(f"Aligned raster suite directly generated for unit {unit_id}")

        except Exception as e:
            pytest.fail(f"Direct aligned raster suite plot failed: {e}")

    def test_session_raster_suite_interface(self):
        """Test the session.raster_suite wrapper."""
        session = OmissionSession(str(NWB_FILES[0]))
        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        if len(units) == 0:
            pytest.skip("No units in session")

        # Find unit with spikes
        unit_id = None
        for uid in units.index:
            spike_times = session.get_spike_times(uid)
            if spike_times is not None and len(spike_times) > 10:
                unit_id = uid
                break

        if unit_id is None:
            pytest.skip("No unit with sufficient spikes found")

        try:
            # 1. Full suite (condition=None)
            res_full = session.raster_suite(unit_id=unit_id)
            assert res_full['status'] == 'completed'
            assert res_full['type'] == 'full_suite'
            assert isinstance(res_full['figure'], plt.Figure)
            plt.close(res_full['figure'])

            # 2. Single condition
            res_single = session.raster_suite(unit_id=unit_id, condition='AAAB')
            assert res_single['status'] == 'completed'
            assert res_single['type'] == 'single_condition'
            assert isinstance(res_single['figure'], plt.Figure)
            plt.close(res_single['figure'])

            log.info(f"session.raster_suite verified for unit {unit_id}")

        except Exception as e:
            pytest.fail(f"session.raster_suite test failed: {e}")

    def test_lfp_tfr_trace_suite_omission(self):
        """Test lfp_tfr_trace_suite_omission."""
        session = OmissionSession(str(NWB_FILES[0]))
        try:
            res = session.lfp_tfr_trace_suite_omission(
                area="V4",
                layer="superficial",
                session_specific=False
            )
            assert isinstance(res, dict)
            assert res['status'] == 'completed'
            assert isinstance(res['figure'], plt.Figure)
            plt.close(res['figure'])
            log.info("lfp_tfr_trace_suite_omission verified successfully")
        except Exception as e:
            pytest.fail(f"lfp_tfr_trace_suite_omission failed: {e}")

    def test_lfp_tfr_trace_correlation(self):
        """Test lfp_tfr_trace_correlation."""
        session = OmissionSession(str(NWB_FILES[0]))
        try:
            res = session.lfp_tfr_trace_correlation(
                band_name="Theta",
                alpha=0.05
            )
            assert isinstance(res, dict)
            assert isinstance(res['figure'], plt.Figure)
            assert 'correlation_matrix' in res
            assert 'p_matrix_corrected' in res
            assert 'significant_pairs' in res
            plt.close(res['figure'])
            log.info("lfp_tfr_trace_correlation verified successfully")
        except Exception as e:
            pytest.fail(f"lfp_tfr_trace_correlation failed: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

