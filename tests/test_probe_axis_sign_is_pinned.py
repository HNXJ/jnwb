"""The principal probe axis must not reverse under a negligible coordinate change.

`probe_geometry` recovers the shaft axis from an SVD of the centred contact coordinates.
A singular vector carries an arbitrary sign -- `v` and `-v` describe the same axis -- and
which one LAPACK returns can change under a perturbation far below any physical
tolerance. When it changes, `linear_order` reverses end to end, and the sign that was
supposed to correct it could not: the guard at HEAD read

    if (sorted_proj[-1] - sorted_proj[0]) < 0:

where `sorted_proj = projections[np.argsort(projections)]` is ascending by construction,
so the difference is non-negative for every possible input and the branch was
unreachable.

Measured on the unrepaired module, a straight 24-contact shaft at 100 um pitch with `z`
scaled by `1 - 1e-9` reversed `linear_order` from `[0..23]` to `[23..0]` and `orientation`
from `[0, 0, 1]` to `[0, 0, -1]`. The same module ordered a 3-contact ascending-`z` shaft
`[2, 1, 0]` while ordering the geometrically identical 24-contact shaft `[0..23]`, so the
answer depended on the channel count.

Two properties are asserted separately here, because either one alone is a proxy:

* stability -- the same shaft must give the same ordering under a perturbation that
  cannot change the physics;
* absolute direction -- the ordering must run along increasing electrode-table row order,
  which is the convention `jnwb.laminar.vflip` already documents for its `orientation`
  argument ("relative to channel indexing"). A test that asserted stability alone would
  pass just as happily on a convention that was consistently reversed.
"""

import numpy as np
import pandas as pd
import pytest

from jnwb.addressing import probe_geometry

PITCH_UM = 100.0
N_CANONICAL = 24


def _frame(coords):
    """An electrode frame in the row order the caller supplied."""
    n = len(coords)
    return pd.DataFrame(
        {
            "x": coords[:, 0],
            "y": coords[:, 1],
            "z": coords[:, 2],
            "channel_id": [f"ch_{i}" for i in range(n)],
        }
    )


def _straight_shaft(n=N_CANONICAL, pitch=PITCH_UM, descending=False, stagger_um=0.0):
    """A shaft along z whose table rows advance monotonically along it."""
    i = np.arange(n, dtype=float)
    z = (n - 1 - i) * pitch if descending else i * pitch
    x = np.where(i % 2 == 0, -0.5 * stagger_um, 0.5 * stagger_um)
    return np.column_stack([x, np.zeros(n), z])


def _geom(coords):
    return probe_geometry(_frame(coords), units="um")


# Perturbations that no physical probe could distinguish: a relative rescale of z far
# below any manufacturing or measurement tolerance, in both directions.
RELATIVE_EPS = (1e-9, -1e-9, 1e-10, -1e-10, 1e-11, -1e-11, 1e-12, -1e-12)

SHAFTS = {
    "ascending": _straight_shaft(),
    "descending": _straight_shaft(descending=True),
    "ascending_offset": _straight_shaft() + np.array([0.0, 0.0, 3000.0]),
    "staggered": _straight_shaft(stagger_um=40.0),
    "staggered_descending": _straight_shaft(descending=True, stagger_um=40.0),
}


class TestAbsoluteDirection:
    """Which way is up, pinned -- not merely pinned consistently."""

    def test_ascending_table_orders_along_increasing_z(self):
        g = _geom(_straight_shaft())
        assert g.linear_order.tolist() == list(range(N_CANONICAL))
        np.testing.assert_allclose(g.orientation, [0.0, 0.0, 1.0], atol=1e-12)

    def test_descending_table_orders_along_decreasing_z(self):
        """The axis follows the table's row order, so a reversed table reverses the axis.

        `linear_order` stays the identity -- the rows already advance along the shaft --
        while `orientation` flips. Asserting both is what distinguishes "pinned to the
        table" from "pinned to +z", which are different claims that agree on the
        ascending case.
        """
        g = _geom(_straight_shaft(descending=True))
        assert g.linear_order.tolist() == list(range(N_CANONICAL))
        np.testing.assert_allclose(g.orientation, [0.0, 0.0, -1.0], atol=1e-12)

    def test_the_first_ordered_contact_is_the_first_table_row(self):
        """Stated as the invariant rather than as a literal, over every shaft shape."""
        for name, coords in SHAFTS.items():
            g = _geom(coords)
            assert g.linear_order[0] == 0, name
            assert g.linear_order[-1] == len(coords) - 1, name
            advance = float(
                np.dot(coords[-1] - coords[0], g.orientation)
            )
            assert advance > 0.0, f"{name}: axis points against the table order"

    # Channel counts measured to reverse on the unrepaired module (3, 5, 18, 20, 56,
    # 58, 59) alongside counts that did not, so the case list covers both sides of a
    # split that has no physical meaning. 18 and 20 matter most: they are ordinary
    # probe lengths, and the reversal there needs no perturbation at all.
    @pytest.mark.parametrize(
        "n", [3, 4, 5, 8, 12, 16, 18, 20, 24, 32, 48, 56, 58, 59, 64]
    )
    @pytest.mark.parametrize("pitch", [25.0, 100.0])
    def test_the_answer_does_not_depend_on_the_channel_count(self, n, pitch):
        """The same shaft shape must order the same way at every length.

        The unrepaired module ordered an ascending 18-contact shaft `[17, 16, ... 0]`
        and a geometrically identical 24-contact shaft `[0, 1, ... 23]`, because the
        sign LAPACK returned happened to differ with the matrix shape. Pitch is
        parametrized for the same reason: the split moved with it.
        """
        g = _geom(_straight_shaft(n=n, pitch=pitch))
        assert g.linear_order.tolist() == list(range(n))
        np.testing.assert_allclose(g.orientation, [0.0, 0.0, 1.0], atol=1e-12)


class TestStability:
    """A change below any physical tolerance must not change the ordering."""

    @pytest.mark.parametrize("name", sorted(SHAFTS))
    @pytest.mark.parametrize("eps", RELATIVE_EPS)
    def test_relative_rescale_of_z_preserves_the_ordering(self, name, eps):
        coords = SHAFTS[name]
        base = _geom(coords)
        moved = coords.copy()
        moved[:, 2] = moved[:, 2] * (1.0 + eps)
        got = _geom(moved)
        assert got.linear_order.tolist() == base.linear_order.tolist()
        np.testing.assert_allclose(got.orientation, base.orientation, atol=1e-6)

    @pytest.mark.parametrize("name", sorted(SHAFTS))
    @pytest.mark.parametrize("towards", [np.inf, -np.inf])
    def test_one_ulp_preserves_the_ordering(self, name, towards):
        """The smallest representable move in every coordinate at once."""
        coords = SHAFTS[name]
        base = _geom(coords)
        moved = np.nextafter(coords, towards)
        got = _geom(moved)
        assert got.linear_order.tolist() == base.linear_order.tolist()
        np.testing.assert_allclose(got.orientation, base.orientation, atol=1e-6)

    def test_the_perturbation_actually_moves_the_coordinates(self):
        """Without this, a no-op perturbation would make the stability tests vacuous."""
        coords = SHAFTS["ascending"]
        moved = coords.copy()
        moved[:, 2] = moved[:, 2] * (1.0 - 1e-9)
        assert not np.array_equal(coords, moved)
        changed = np.sum(moved[:, 2] != coords[:, 2])
        assert changed >= len(coords) - 1, f"only {changed} z values actually changed"

        ulp = np.nextafter(coords, np.inf)
        assert not np.array_equal(coords, ulp)


class TestLayerLabelsAreStable:
    """The reason the ordering matters: it decides which end of the shaft is superficial."""

    def test_labels_survive_a_negligible_coordinate_change(self):
        laminar = pytest.importorskip("jnwb.laminar")
        synth = pytest.importorskip("jnwb.testing.synth")

        rec = synth.synth_laminar_motif(
            n_channels=N_CANONICAL,
            pitch_um=PITCH_UM,
            c_crossover=17.0,
            orientation="superficial_to_deep",
            rng=7,
        )
        coords = rec.probe_geometry.contact_positions

        def labels_for(eps):
            moved = coords.copy()
            moved[:, 2] = moved[:, 2] * (1.0 + eps)
            g = probe_geometry(_frame(moved), units="um", nominal_pitch=PITCH_UM)
            v = laminar.vflip_from_lfp(
                rec.lfp,
                rec.fs,
                probe_geometry=g,
                orientation="auto",
                min_support_score=-1e9,
            )
            assert v.accepted, f"eps={eps}: fit rejected ({v.rejection_reason})"
            mapping = laminar.label_layers(v, g, granular_thickness_um=300.0)
            return [mapping[f"ch_{i}"] for i in range(N_CANONICAL)], v

        base, v_base = labels_for(0.0)
        assert "superficial" in base and "deep" in base, base
        # The shaft is declared superficial-to-deep, so the shallow end must be labelled
        # superficial. This is the absolute claim; the loop below is the stability claim.
        assert base[0] == "superficial", base
        assert base[-1] == "deep", base

        for eps in (1e-9, -1e-9, 1e-11, -1e-11):
            got, v_got = labels_for(eps)
            assert got == base, f"eps={eps}: labels changed\n{base}\n{got}"
            assert v_got.crossover_depth_um == pytest.approx(
                v_base.crossover_depth_um, rel=1e-6
            )
