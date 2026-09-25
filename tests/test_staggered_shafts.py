"""Staggered electrode shafts are linear shafts, and their pitch is the axial step.

Item 06-47. A shaft whose contacts advance by a constant 25 um along z while alternating
40 um laterally in x was reported as ``is_linear=False`` with ``nominal_pitch=47.17``.
47.17 is ``sqrt(25**2 + 40**2)``: the lateral stagger was being measured as advance along
the shaft, and ``label_layers`` then refused the shaft outright.

Every fixture here is built by handing coordinates to ``jnwb.probe_geometry``. Nothing
pins ``is_linear`` or ``nominal_pitch`` onto an object by hand -- a fixture that asserted
its own answer would satisfy the guard without being a shaft.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import jnwb
from jnwb.laminar import VFlipResult, label_layers

Z_STEP_UM = 25.0
X_STAGGER_UM = 40.0
HYPOTENUSE_UM = float(np.hypot(Z_STEP_UM, X_STAGGER_UM))  # 47.1699...


def _frame(x, y, z, name="probeA"):
    n = len(z)
    return pd.DataFrame(
        {
            "x": np.asarray(x, dtype=float),
            "y": np.asarray(y, dtype=float),
            "z": np.asarray(z, dtype=float),
            "channel_id": [f"ch_{i}" for i in range(n)],
            "group_name": [name] * n,
        }
    )


def staggered_frame(n=32, z_step=Z_STEP_UM, x_stagger=X_STAGGER_UM):
    """The reported geometry: constant axial advance, alternating lateral offset."""
    z = np.arange(n) * z_step
    x = np.where(np.arange(n) % 2 == 0, 0.0, x_stagger)
    return _frame(x, np.zeros(n), z)


def single_column_frame(n=32, z_step=40.0):
    z = np.arange(n) * z_step
    return _frame(np.zeros(n), np.zeros(n), z)


def _vflip_result(n_channels, crossover, pitch_um, orientation="superficial_to_deep"):
    return VFlipResult(
        crossover_contact=float(crossover),
        crossover_depth_um=float(crossover) * pitch_um,
        support_score=10.0,
        profile=np.zeros(n_channels),
        low_peak_contact=n_channels - 4,
        high_peak_contact=2,
        orientation=orientation,
        accepted=True,
        rejection_reason=None,
        n_channels=n_channels,
        n_missing=0,
    )


class TestStaggeredPitchIsAxial:
    """The reported arithmetic, not merely ``is_linear=False``."""

    def test_nominal_pitch_is_the_axial_step_not_the_hypotenuse(self):
        geom = jnwb.probe_geometry(staggered_frame(), probe_name="probeA", units="um")

        # The defect was this exact number. Name it, so a different bug cannot pass.
        assert HYPOTENUSE_UM == pytest.approx(47.16990566, abs=1e-6)
        assert geom.nominal_pitch != pytest.approx(HYPOTENUSE_UM, abs=1e-3), (
            "nominal_pitch is still the contact-to-contact chord: the lateral stagger "
            "is being measured as advance along the shaft"
        )
        assert geom.nominal_pitch == pytest.approx(Z_STEP_UM, abs=1e-6)

    def test_pitch_is_reported_in_input_units_scaled_to_um(self):
        """The consumer calls this with units='mm'; the answer is still 25 um."""
        df = staggered_frame()
        df[["x", "y", "z"]] = df[["x", "y", "z"]] / 1000.0
        geom = jnwb.probe_geometry(df, probe_name="probeA", units="mm")
        assert geom.nominal_pitch == pytest.approx(Z_STEP_UM, abs=1e-6)
        assert geom.stagger_um == pytest.approx(X_STAGGER_UM, abs=1e-6)

    def test_staggered_shaft_is_linear_and_records_the_stagger(self):
        geom = jnwb.probe_geometry(staggered_frame(), probe_name="probeA", units="um")
        assert geom.is_linear is True
        assert geom.is_staggered is True
        assert geom.stagger_um == pytest.approx(X_STAGGER_UM, abs=1e-6)
        # The stagger is recorded as a lateral offset, so the shaft axis stays axial.
        assert np.allclose(geom.orientation, [0.0, 0.0, 1.0], atol=1e-9)

    def test_ordering_follows_depth_not_the_stagger(self):
        geom = jnwb.probe_geometry(staggered_frame(), probe_name="probeA", units="um")
        ordered_z = geom.contact_positions[geom.linear_order][:, 2]
        assert np.all(np.diff(ordered_z) > 0)

    def test_short_staggered_shaft_also_reports_the_axial_step(self):
        """A 4-contact shaft has too little length for a raw principal axis to survive."""
        geom = jnwb.probe_geometry(
            staggered_frame(n=4), probe_name="probeA", units="um"
        )
        assert geom.is_linear is True
        assert geom.nominal_pitch == pytest.approx(Z_STEP_UM, abs=1e-6)

    def test_four_column_staggered_shaft(self):
        n = 32
        z = np.arange(n) * 20.0
        x = np.tile([0.0, 25.0, 50.0, 75.0], n // 4)
        geom = jnwb.probe_geometry(
            _frame(x, np.zeros(n), z), probe_name="probeA", units="um"
        )
        assert geom.is_linear is True
        assert geom.is_staggered is True
        assert geom.nominal_pitch == pytest.approx(20.0, abs=1e-6)
        assert geom.stagger_um == pytest.approx(75.0, abs=1e-6)


class TestNonLinearStillRefused:
    """The other direction: widening linearity must not accept what is not a shaft."""

    def _geom(self, df):
        return jnwb.probe_geometry(df, probe_name="probeA", units="um")

    def test_planar_grid_is_not_a_shaft(self):
        """Contacts share a depth, so there is no monotone advance to order them by."""
        zz, xx = np.meshgrid(np.arange(8) * 40.0, np.arange(4) * 40.0, indexing="ij")
        df = _frame(xx.ravel(), np.zeros(zz.size), zz.ravel())
        assert self._geom(df).is_linear is False

    def test_paired_ladder_with_tied_depths_is_not_a_shaft(self):
        """Two columns at *identical* depths: lateral extent is a legal 40 um, but the
        contacts do not advance one at a time, so this is not a shaft."""
        z = np.repeat(np.arange(16) * 25.0, 2)
        x = np.tile([0.0, 40.0], 16)
        df = _frame(x, np.zeros(32), z)
        geom = self._geom(df)
        assert geom.stagger_um <= 100.0, "the ladder is inside the stagger tolerance"
        assert geom.is_linear is False, (
            "tied depths must be refused by monotone advance, not by lateral extent"
        )

    def test_three_dimensional_scatter_is_not_a_shaft(self):
        rng = np.random.default_rng(0)
        pts = rng.normal(0.0, 300.0, size=(32, 3))
        df = _frame(pts[:, 0], pts[:, 1], pts[:, 2])
        assert self._geom(df).is_linear is False

    def test_wide_short_array_is_not_a_shaft(self):
        """Monotone in z by 1 um, but 70 um wide: an array, not a shaft."""
        df = _frame(
            [0, 50, 0, 50] * 4,
            [0, 0, 50, 50] * 4,
            np.arange(16, dtype=float),
        )
        assert self._geom(df).is_linear is False

    def test_stagger_beyond_tolerance_is_refused(self):
        df = staggered_frame(x_stagger=400.0)
        assert self._geom(df).is_linear is False

    def test_stagger_tolerance_is_tunable(self):
        """A 150 um stagger is outside the default bound but a caller may allow it."""
        df = staggered_frame(x_stagger=150.0)
        assert self._geom(df).is_linear is False
        geom = jnwb.probe_geometry(
            df, probe_name="probeA", units="um", stagger_tolerance_um=200.0
        )
        assert geom.is_linear is True
        assert geom.nominal_pitch == pytest.approx(Z_STEP_UM, abs=1e-6)
        assert geom.stagger_um == pytest.approx(150.0, abs=1e-6)

    def test_axial_pitch_is_exact_while_the_stagger_stays_below_the_span(self):
        """Pins the envelope of the shaft-axis estimate.

        The axis is recovered from the ordered contacts, so it is exact while the
        lateral stagger stays well under the axial span. At 12x the axial step the
        pitch is still exact; far beyond that the initial ordering is no longer by
        depth and the estimate degrades. Every such case is already refused by the
        default stagger tolerance of 100 um, so this bounds a tunable, not the
        default path.
        """
        for stagger in (40.0, 100.0, 150.0, 200.0, 300.0):
            geom = jnwb.probe_geometry(
                staggered_frame(x_stagger=stagger),
                probe_name="probeA",
                units="um",
                stagger_tolerance_um=1000.0,
            )
            assert geom.nominal_pitch == pytest.approx(Z_STEP_UM, abs=1e-9), (
                f"axial pitch degraded at stagger={stagger} um"
            )
            assert geom.stagger_um == pytest.approx(stagger, abs=1e-9)

    def test_strict_linear_still_raises_on_a_grid(self):
        zz, xx = np.meshgrid(np.arange(8) * 40.0, np.arange(4) * 40.0, indexing="ij")
        df = _frame(xx.ravel(), np.zeros(zz.size), zz.ravel())
        with pytest.raises(ValueError, match="non-linear"):
            jnwb.probe_geometry(
                df, probe_name="probeA", units="um", strict_linear=True
            )

    def test_strict_linear_does_not_raise_on_a_staggered_shaft(self):
        geom = jnwb.probe_geometry(
            staggered_frame(), probe_name="probeA", units="um", strict_linear=True
        )
        assert geom.is_linear is True


class TestUnchangedShafts:
    """Shafts that already worked must not move."""

    def test_single_column_shaft_is_untouched(self):
        geom = jnwb.probe_geometry(
            single_column_frame(), probe_name="probeA", units="um"
        )
        assert geom.is_linear is True
        assert geom.is_uniform is True
        assert geom.is_staggered is False
        assert geom.stagger_um == pytest.approx(0.0, abs=1e-9)
        assert geom.nominal_pitch == pytest.approx(40.0, abs=1e-9)

    def test_obliquely_inserted_shaft_keeps_its_true_pitch(self):
        """The pitch is advance along the shaft, not the projection onto a coordinate
        axis: a shaft tilted 30 degrees still has a 25 um pitch, not 25*cos(30)."""
        t = np.arange(24)
        ang = np.deg2rad(30.0)
        geom = jnwb.probe_geometry(
            _frame(t * 25.0 * np.sin(ang), np.zeros(24), t * 25.0 * np.cos(ang)),
            probe_name="probeA",
            units="um",
        )
        assert geom.is_linear is True
        assert geom.is_staggered is False
        assert geom.nominal_pitch == pytest.approx(25.0, abs=1e-9)
        assert geom.nominal_pitch != pytest.approx(25.0 * np.cos(ang), abs=1e-3)

    def test_irregularly_spaced_collinear_shaft_keeps_median_pitch(self):
        z = np.array([0.0, 50.0, 100.0, 250.0, 300.0])
        geom = jnwb.probe_geometry(
            _frame(np.zeros(5), np.zeros(5), z), probe_name="probeA", units="um"
        )
        assert geom.is_linear is True
        assert geom.is_uniform is False
        assert geom.nominal_pitch == pytest.approx(50.0, abs=1e-9)


class TestLabelLayersOverAStaggeredShaft:
    """Acceptance: the labels themselves, not their count."""

    N = 32
    CROSSOVER = 16.0
    GRANULAR_UM = 200.0

    def _labels(self):
        geom = jnwb.probe_geometry(
            staggered_frame(n=self.N), probe_name="probeA", units="um"
        )
        res = _vflip_result(self.N, self.CROSSOVER, geom.nominal_pitch)
        return geom, label_layers(res, geom, granular_thickness_um=self.GRANULAR_UM)

    def test_label_layers_no_longer_refuses_the_shaft(self):
        geom, labels = self._labels()
        assert geom.is_staggered is True
        assert len(labels) == self.N
        assert set(labels.values()) == {"superficial", "input", "deep"}

    def test_every_label_is_the_one_the_axial_pitch_implies(self):
        """half-span = (200/2)/25 = 4 contacts, so input spans [12, 20] inclusive.

        Computed from the axial pitch of 25. Under the old chord pitch of 47.17 the
        half-span would have been 2.12 contacts and the input band [13.88, 18.12] --
        a different label on six contacts. Widening which contacts are labelled is
        exactly what changes what each label is computed over.
        """
        _, labels = self._labels()
        expected = {}
        for i in range(self.N):
            if i < 12:
                expected[f"ch_{i}"] = "superficial"
            elif i <= 20:
                expected[f"ch_{i}"] = "input"
            else:
                expected[f"ch_{i}"] = "deep"
        assert labels == expected

    def test_deep_to_superficial_inverts_the_same_band(self):
        geom = jnwb.probe_geometry(
            staggered_frame(n=self.N), probe_name="probeA", units="um"
        )
        res = _vflip_result(
            self.N, self.CROSSOVER, geom.nominal_pitch, orientation="deep_to_superficial"
        )
        labels = label_layers(res, geom, granular_thickness_um=self.GRANULAR_UM)
        expected = {}
        for i in range(self.N):
            if i < 12:
                expected[f"ch_{i}"] = "deep"
            elif i <= 20:
                expected[f"ch_{i}"] = "input"
            else:
                expected[f"ch_{i}"] = "superficial"
        assert labels == expected

    def test_labels_on_an_already_working_shaft_do_not_move(self):
        """Stop-condition guard: a collinear shaft must produce the labels it always did."""
        geom = jnwb.probe_geometry(
            single_column_frame(n=24, z_step=50.0), probe_name="probeA", units="um"
        )
        assert geom.nominal_pitch == pytest.approx(50.0, abs=1e-9)
        res = _vflip_result(24, 10.0, 50.0)
        labels = label_layers(res, geom, granular_thickness_um=400.0)
        expected = {}
        for i in range(24):
            if i < 6:
                expected[f"ch_{i}"] = "superficial"
            elif i <= 14:
                expected[f"ch_{i}"] = "input"
            else:
                expected[f"ch_{i}"] = "deep"
        assert labels == expected

    def test_a_genuinely_non_linear_geometry_is_still_refused_by_label_layers(self):
        zz, xx = np.meshgrid(np.arange(8) * 40.0, np.arange(4) * 40.0, indexing="ij")
        geom = jnwb.probe_geometry(
            _frame(xx.ravel(), np.zeros(zz.size), zz.ravel()),
            probe_name="probeA",
            units="um",
        )
        res = _vflip_result(32, 16.0, 40.0)
        with pytest.raises(ValueError, match="linear electrode shaft"):
            label_layers(res, geom)
