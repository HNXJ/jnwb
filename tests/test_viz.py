"""Unit tests for jnwb.viz -- generic plotting utilities (vector-graphics setup, tight
auto-scaled axes, multi-page/format figure export, trial-onset resampling, array-in PSTH),
promoted 2026-08-23 from omission.jnwb_ext.viz (99%-jnwb-sufficiency normalization).
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pytest

from jnwb.viz import (
    setup_vector_graphics,
    apply_tight_auto_axis,
    save_figure_suite,
    resample_onsets,
    raster_psth,
)


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        import jnwb
        assert jnwb.setup_vector_graphics is setup_vector_graphics
        assert jnwb.apply_tight_auto_axis is apply_tight_auto_axis
        assert jnwb.save_figure_suite is save_figure_suite
        assert jnwb.resample_onsets is resample_onsets
        assert jnwb.raster_psth is raster_psth

    def test_listed_in_jnwb_all(self):
        import jnwb
        for name in ("setup_vector_graphics", "apply_tight_auto_axis", "save_figure_suite",
                     "resample_onsets", "raster_psth"):
            assert name in jnwb.__all__

    def test_omission_viz_delegates_to_jnwb(self):
        viz = pytest.importorskip("omission.jnwb_ext.viz")
        assert viz.setup_vector_graphics is setup_vector_graphics
        assert viz.apply_tight_auto_axis is apply_tight_auto_axis
        assert viz.save_figure_suite is save_figure_suite
        assert viz.resample_onsets is resample_onsets
        assert viz.raster_psth is raster_psth


class TestSetupVectorGraphics:
    def test_sets_editable_svg_fonttype(self):
        plt.rcParams['svg.fonttype'] = 'path'
        setup_vector_graphics()
        assert plt.rcParams['svg.fonttype'] == 'none'


class TestApplyTightAutoAxis:
    def test_sets_xlim_to_span(self):
        fig, ax = plt.subplots()
        ax.plot([0, 1, 2], [1.0, 2.0, 3.0])
        apply_tight_auto_axis(ax, x_span=(-100, 100))
        assert ax.get_xlim() == (-100, 100)
        plt.close(fig)

    def test_ylim_expands_with_margin_and_stays_nonnegative(self):
        fig, ax = plt.subplots()
        ax.plot([0, 1], [2.0, 4.0])
        apply_tight_auto_axis(ax, y_margin=0.1)
        ymin, ymax = ax.get_ylim()
        assert ymin >= 0
        assert ymax > 4.0
        plt.close(fig)


class TestSaveFigureSuite:
    def test_writes_one_file_per_page_and_format(self, tmp_path):
        figs = [plt.figure() for _ in range(2)]
        output_dir = tmp_path / "multi_format"
        expected = [
            output_dir / "test_page1.png",
            output_dir / "test_page2.png",
            output_dir / "test_page1.pdf",
            output_dir / "test_page2.pdf",
        ]
        try:
            save_figure_suite(figures=figs, output_dir=output_dir, basename="test", formats=["png", "pdf"])
            assert all(p.exists() for p in expected)
        finally:
            for fig in figs:
                plt.close(fig)


class TestResampleOnsets:
    def test_empty_input_returns_empty(self):
        assert resample_onsets(np.array([])).size == 0

    def test_downsamples_without_replacement(self):
        onsets = np.arange(200.0)
        out = resample_onsets(onsets, target_n=50, random_state=0)
        assert len(out) == 50
        assert len(np.unique(out)) == 50  # no replacement when oversupplied

    def test_upsamples_with_replacement(self):
        onsets = np.array([1.0, 2.0, 3.0])
        out = resample_onsets(onsets, target_n=10, random_state=0)
        assert len(out) == 10
        assert set(out.tolist()) <= {1.0, 2.0, 3.0}

    def test_deterministic_given_seed(self):
        onsets = np.arange(50.0)
        a = resample_onsets(onsets, target_n=20, random_state=7)
        b = resample_onsets(onsets, target_n=20, random_state=7)
        assert np.array_equal(a, b)


class TestRasterPsth:
    def test_empty_onsets_returns_zeroed_curve(self):
        centers, mean, sem = raster_psth(np.array([]), np.array([]), (-100, 100), bin_ms=10.0)
        assert np.all(mean == 0)
        assert np.all(sem == 0)
        assert len(centers) == len(mean)

    def test_known_rate_recovered(self):
        # 2 trials, each with a spike exactly 20ms after onset -> counted in one bin.
        onsets = np.array([0.0, 1.0])
        st = np.array([0.02, 1.02])
        centers, mean, sem = raster_psth(st, onsets, (0, 100), bin_ms=10.0)
        assert mean.sum() > 0
        peak_bin = np.argmax(mean)
        assert abs(centers[peak_bin] - 25.0) < 15.0
