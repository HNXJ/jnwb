"""
Migrated from omission/legacy/tests/test_viz_category_d.py (2026-08-22).

Only the confirmed UNIQUE_REQUIREMENT assertions survive here — the ones exercising
omission.jnwb_ext.viz / session wrapper contracts that had zero other coverage
(omission/outputs/normalization/... legacy/tests audit, 2026-08-22). The rest of the
original 17-test file duplicated smoke coverage available elsewhere and was not ported.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from jnwb.paths import nwb_dir
from omission import OmissionSession, viz
from jnwb import metadata  # promoted 2026-08-23 from omission.jnwb_ext.metadata

try:
    NWB_PATH = nwb_dir() / "sub-C31o_ses-230823_rec.nwb"
except FileNotFoundError:
    # jnwb.paths.nwb_dir() raises when $OMISSION_NWB_DIR is unset (no machine-specific default
    # -- see jnwb/paths.py). Deferred to a per-test skip rather than failing collection, same as
    # the file-missing case below.
    NWB_PATH = None


def _skip_if_missing():
    if NWB_PATH is None or not Path(NWB_PATH).exists():
        pytest.skip(f"Real test-session NWB file {NWB_PATH} is missing or $OMISSION_NWB_DIR is unset.")


def _first_unit_with_spikes(session, units):
    for uid in units.index:
        spike_times = session.get_spike_times(uid)
        if spike_times is not None and len(spike_times) > 10:
            return uid
    return None


def test_raster_grid_by_family_paginates_across_multiple_figures():
    """15 units at max_units_per_page=6 must split into >=2 pages."""
    _skip_if_missing()
    session = OmissionSession(str(NWB_PATH))
    units = metadata.get_all_units_metadata(str(NWB_PATH))
    if len(units) < 15:
        pytest.skip("Not enough units for pagination test")

    id_col = "cluster_id" if "cluster_id" in units.columns else "unit_id"
    unit_ids = units.head(15)[id_col].tolist()

    figs = viz.raster_grid_by_family(
        session=session, unit_ids=unit_ids, family="A", max_units_per_page=6
    )
    try:
        assert len(figs) >= 2, f"Should paginate into multiple figures, got {len(figs)}"
    finally:
        for fig in figs:
            plt.close(fig)


def test_multi_phase_comparison_has_one_axis_per_phase():
    """multi_phase_comparison must return exactly 4 subplots, one per phase p1-p4."""
    _skip_if_missing()
    session = OmissionSession(str(NWB_PATH))
    units = metadata.get_all_units_metadata(str(NWB_PATH))
    if len(units) == 0:
        pytest.skip("No units")

    id_col = "cluster_id" if "cluster_id" in units.columns else "unit_id"
    unit_id = units.iloc[0][id_col]
    spike_times = session.get_spike_times(unit_id)
    if spike_times is None or len(spike_times) < 10:
        pytest.skip("Not enough spikes for unit")

    fig = viz.multi_phase_comparison(session=session, unit_id=unit_id, condition="AAAB")
    try:
        assert len(fig.get_axes()) == 4, "Should have 4 subplots (p1-p4)"
    finally:
        plt.close(fig)


def test_save_figure_suite_writes_one_file_per_page_and_format(tmp_path):
    """save_figure_suite(formats=[...]) must write one file per (page x format) pair."""
    figs = [plt.figure() for _ in range(2)]
    output_dir = tmp_path / "multi_format"
    expected = [
        output_dir / "test_page1.png",
        output_dir / "test_page2.png",
        output_dir / "test_page1.pdf",
        output_dir / "test_page2.pdf",
    ]
    try:
        viz.save_figure_suite(figures=figs, output_dir=output_dir, basename="test", formats=["png", "pdf"])
        assert all(p.exists() for p in expected), "All (page x format) combinations should be written"
    finally:
        for fig in figs:
            plt.close(fig)


def test_session_raster_suite_dict_shape_depends_on_condition():
    """session.raster_suite branches its return dict 'type' on whether condition is given."""
    _skip_if_missing()
    session = OmissionSession(str(NWB_PATH))
    units = metadata.get_all_units_metadata(str(NWB_PATH))
    if len(units) == 0:
        pytest.skip("No units in session")

    unit_id = _first_unit_with_spikes(session, units)
    if unit_id is None:
        pytest.skip("No unit with sufficient spikes found")

    res_full = session.raster_suite(unit_id=unit_id)
    try:
        assert res_full["status"] == "completed"
        assert res_full["type"] == "full_suite"
    finally:
        plt.close(res_full["figure"])

    res_single = session.raster_suite(unit_id=unit_id, condition="AAAB")
    try:
        assert res_single["status"] == "completed"
        assert res_single["type"] == "single_condition"
    finally:
        plt.close(res_single["figure"])


def test_lfp_tfr_trace_correlation_returns_multiplicity_corrected_fields():
    """lfp_tfr_trace_correlation's result dict must carry the multiple-comparison-correction contract."""
    pytest.importorskip("statsmodels", reason="statsmodels declared in pyproject.toml but not installed in this env")
    _skip_if_missing()
    session = OmissionSession(str(NWB_PATH))
    res = session.lfp_tfr_trace_correlation(band_name="Theta", alpha=0.05)
    try:
        assert "correlation_matrix" in res
        assert "p_matrix_corrected" in res
        assert "significant_pairs" in res
    finally:
        plt.close(res["figure"])
