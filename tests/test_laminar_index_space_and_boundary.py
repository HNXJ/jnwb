"""The two index axes `vflip` can return on, and the granular boundary at exact equality.

Items P-49 and P-166.

P-49: ``vflip`` reorders the PSD rows along the shaft only when it is given a
``probe_geometry``; ``label_layers`` always places contacts by shaft rank. A caller who
omits geometry from one call and supplies it to the other crosses two index axes, and the
only check across that boundary was a channel *count*. Measured on the fixtures below
before the repair: ``accepted=True``, no warning, and 10 of 24 contacts labelled
differently on a two-bank table -- two of them a full superficial/deep swap.

P-166: the granular interval is closed, and its half-span is an exact integer number of
contacts on the pitches most used in the field, so one ulp of the pitch decided a
contact's layer.

Nothing here imports a symbol the repair introduced, and nothing constructs a result with
a field the repair introduced. The module therefore collects against the unrepaired
estimator, where each assertion fails on the behaviour it names rather than the whole
file erroring at import -- a collection error is indistinguishable from a real kill.

Every geometry is built by handing coordinates to ``jnwb.probe_geometry``; nothing pins
``linear_order`` or ``nominal_pitch`` by hand.
"""
from __future__ import annotations

import dataclasses
import math

import numpy as np
import pandas as pd
import pytest

import jnwb
from jnwb import laminar
from jnwb.laminar import VFlipResult, label_layers, vflip

N_CONTACTS = 24
PITCH_UM = 100.0
DEFAULT_GRANULAR_UM = 400.0


def _synthetic_motif(n_channels: int = N_CONTACTS, c_crossover: float = 11.5):
    """A spectrolaminar motif in depth order: gamma above the crossover, beta below."""
    freqs = np.linspace(2.0, 150.0, 100)
    psd = np.zeros((n_channels, len(freqs)), dtype=np.float64)
    for c in range(n_channels):
        gamma_w = max(0.0, 1.0 - (c - (c_crossover - 4.0)) ** 2 / 40.0)
        beta_w = max(0.0, 1.0 - (c - (c_crossover + 4.0)) ** 2 / 40.0)
        psd[c] = (
            0.05
            + 2.0 * gamma_w * np.exp(-((freqs - 75.0) ** 2) / 200.0)
            + 2.0 * beta_w * np.exp(-((freqs - 18.0) ** 2) / 50.0)
        )
    return freqs, psd


def _geometry(z_um, pitch_um=None):
    frame = pd.DataFrame(
        {
            "x": np.zeros(len(z_um)),
            "y": np.zeros(len(z_um)),
            "z": np.asarray(z_um, dtype=float),
            "channel_id": [f"ch_{i}" for i in range(len(z_um))],
        }
    )
    kwargs = {} if pitch_um is None else {"nominal_pitch": pitch_um}
    return jnwb.probe_geometry(frame, units="um", **kwargs)


def _shaft_orders():
    """Table row -> shaft position, for tables that are not ordered along the shaft."""
    return {
        "rotate_12": np.array([(r + 12) % N_CONTACTS for r in range(N_CONTACTS)]),
        "two_bank": np.concatenate(
            [np.arange(0, N_CONTACTS, 2), np.arange(1, N_CONTACTS, 2)]
        ),
    }


def _accepted_result(n_channels, crossover, index_space="shaft_rank"):
    """A hand-built accepted fit, tolerating a ``VFlipResult`` with no index space."""
    kwargs = dict(
        crossover_contact=float(crossover),
        crossover_depth_um=None,
        support_score=10.0,
        profile=np.zeros(n_channels),
        low_peak_contact=n_channels - 4,
        high_peak_contact=2,
        orientation="superficial_to_deep",
        accepted=True,
        rejection_reason=None,
        n_channels=n_channels,
        n_missing=0,
    )
    if any(f.name == "index_space" for f in dataclasses.fields(VFlipResult)):
        kwargs["index_space"] = index_space
    return VFlipResult(**kwargs)


class TestTheIndexSpaceIsRecordedAndChecked:
    """A result says which axis it is on, and the boundary refuses to mix the two."""

    def test_vflip_records_shaft_rank_only_when_it_actually_reordered(self):
        freqs, psd_depth = _synthetic_motif()
        shaft_of_row = _shaft_orders()["two_bank"]
        geom = _geometry(shaft_of_row * PITCH_UM, PITCH_UM)
        psd_table = psd_depth[shaft_of_row]

        assert not np.array_equal(geom.linear_order, np.arange(N_CONTACTS)), (
            "fixture is not exercising the defect: the table is already shaft-ordered"
        )

        with_geom = vflip(psd_table, freqs, probe_geometry=geom)
        without_geom = vflip(psd_table, freqs, contact_spacing=PITCH_UM)

        # Both are confident fits, so the mismatch must be visible in a field of its own.
        assert with_geom.accepted and without_geom.accepted
        assert with_geom.crossover_contact != pytest.approx(
            without_geom.crossover_contact, abs=1e-6
        ), "the fixture must place the two index spaces apart"

        assert getattr(with_geom, "index_space", None) == "shaft_rank", (
            "a result whose PSD rows were reordered along the shaft does not say so"
        )
        assert getattr(without_geom, "index_space", None) == "channel", (
            "a result fitted on unreordered PSD rows does not say so"
        )
        assert with_geom.to_dict().get("index_space") == "shaft_rank"
        assert without_geom.to_dict().get("index_space") == "channel"

    @pytest.mark.parametrize("case", sorted(_shaft_orders()))
    def test_label_layers_refuses_a_channel_space_result_on_a_reordered_table(self, case):
        """The defect, at the boundary where it was silent."""
        freqs, psd_depth = _synthetic_motif()
        shaft_of_row = _shaft_orders()[case]
        geom = _geometry(shaft_of_row * PITCH_UM, PITCH_UM)
        psd_table = psd_depth[shaft_of_row]

        without_geom = vflip(psd_table, freqs, contact_spacing=PITCH_UM)
        assert without_geom.accepted, "fixture must reach the labelling path, not a rejection"

        with pytest.raises(ValueError, match="indexed on 'channel'"):
            label_layers(without_geom, geom)

    @pytest.mark.parametrize("case", sorted(_shaft_orders()))
    def test_the_geometry_path_still_labels_the_shaft_by_depth(self, case):
        """The accepted route is unchanged and anatomically ordered along the shaft."""
        freqs, psd_depth = _synthetic_motif()
        shaft_of_row = _shaft_orders()[case]
        geom = _geometry(shaft_of_row * PITCH_UM, PITCH_UM)
        psd_table = psd_depth[shaft_of_row]

        result = vflip(psd_table, freqs, probe_geometry=geom)
        labels = label_layers(result, geom)
        assert len(labels) == N_CONTACTS

        # Read the labels back in depth order: superficial block, input block, deep block.
        by_depth = [labels[f"ch_{row}"] for row in np.argsort(shaft_of_row)]
        assert set(by_depth) <= {"superficial", "input", "deep", "na"}
        seen = [lab for i, lab in enumerate(by_depth) if i == 0 or lab != by_depth[i - 1]]
        assert seen == ["superficial", "input", "deep"], (
            f"layers are not contiguous along depth: {by_depth}"
        )

    def test_a_shaft_ordered_table_without_geometry_is_still_accepted(self):
        """The currently-correct case: the two axes coincide, so nothing is refused."""
        freqs, psd = _synthetic_motif()
        geom = _geometry(np.arange(N_CONTACTS) * PITCH_UM, PITCH_UM)
        assert np.array_equal(geom.linear_order, np.arange(N_CONTACTS))

        without_geom = vflip(psd, freqs, contact_spacing=PITCH_UM)
        with_geom = vflip(psd, freqs, probe_geometry=geom)

        assert label_layers(without_geom, geom) == label_layers(with_geom, geom)

    def test_a_rejected_fit_still_returns_all_na_rather_than_raising(self):
        """The rejection invariant outranks the index check: there is no crossover to misplace."""
        shaft_of_row = _shaft_orders()["two_bank"]
        geom = _geometry(shaft_of_row * PITCH_UM, PITCH_UM)
        rejected = dataclasses.replace(
            _accepted_result(N_CONTACTS, 11.5, index_space="channel"),
            crossover_contact=None,
            crossover_depth_um=None,
            support_score=-np.inf,
            profile=np.full(N_CONTACTS, np.nan),
            low_peak_contact=None,
            high_peak_contact=None,
            orientation="undetermined",
            accepted=False,
            rejection_reason="insufficient_support",
        )
        labels = label_layers(rejected, geom)
        assert len(labels) == N_CONTACTS
        assert set(labels.values()) == {"na"}


class TestTheGranularBoundaryIsPinnedNotEmergent:
    """P-166: the closed interval at exact equality, on real hardware pitches."""

    # (pitch um, n contacts, crossover contact, expected half-span in contacts)
    HARDWARE = [
        pytest.param(20.0, 40, 20.0, 10.0, id="neuropixels_1.0_20um"),
        pytest.param(50.0, 24, 12.0, 4.0, id="v_probe_50um"),
        pytest.param(100.0, 24, 12.0, 2.0, id="laminar_array_100um"),
    ]
    NON_ROUND = pytest.param(23.7, 24, 12.0, 200.0 / 23.7, id="non_round_23.7um")

    @pytest.mark.parametrize("pitch,n,crossover,half_span", HARDWARE)
    def test_the_half_span_really_is_integral_on_this_hardware(self, pitch, n, crossover, half_span):
        """Without this the stability tests below could pass for the wrong reason."""
        measured = (DEFAULT_GRANULAR_UM / 2.0) / pitch
        assert measured == pytest.approx(half_span, abs=0.0)
        assert float(measured).is_integer()

    @pytest.mark.parametrize("pitch,n,crossover,half_span", HARDWARE)
    def test_a_contact_exactly_on_the_boundary_is_input(self, pitch, n, crossover, half_span):
        """The documented convention: the granular interval is closed."""
        geom = _geometry(np.arange(n) * pitch, pitch)
        labels = label_layers(
            _accepted_result(n, crossover), geom, granular_thickness_um=DEFAULT_GRANULAR_UM
        )
        lower = int(crossover - half_span)
        upper = int(crossover + half_span)
        assert labels[f"ch_{lower}"] == "input"
        assert labels[f"ch_{upper}"] == "input"
        # And the contacts just outside are not, so the tolerance has not eaten a contact.
        assert labels[f"ch_{lower - 1}"] == "superficial"
        assert labels[f"ch_{upper + 1}"] == "deep"

    @pytest.mark.parametrize("pitch,n,crossover,half_span", HARDWARE + [NON_ROUND])
    def test_the_label_set_survives_an_ulp_and_a_1e_9_relative_pitch(
        self, pitch, n, crossover, half_span
    ):
        """The knife edge itself. Before the repair 1 to 2 contacts flipped on every
        integral half-span, and none on the non-round pitch."""
        z = np.arange(n) * pitch  # physical coordinates held fixed
        result = _accepted_result(n, crossover)
        baseline = label_layers(
            result, _geometry(z, pitch), granular_thickness_um=DEFAULT_GRANULAR_UM
        )
        perturbations = {
            "+1ulp": math.nextafter(pitch, math.inf),
            "-1ulp": math.nextafter(pitch, -math.inf),
            "+1e-9 rel": pitch * (1.0 + 1e-9),
            "-1e-9 rel": pitch * (1.0 - 1e-9),
        }
        for name, perturbed in perturbations.items():
            assert perturbed != pitch, f"{name} did not actually change the pitch"
            moved = label_layers(
                result, _geometry(z, perturbed), granular_thickness_um=DEFAULT_GRANULAR_UM
            )
            changed = sorted(c for c in baseline if baseline[c] != moved[c])
            assert not changed, (
                f"pitch {pitch} perturbed by {name} moved {len(changed)} contacts: {changed}"
            )

    def test_the_tolerance_is_declared_and_stays_far_below_one_contact(self):
        """A tolerance near a contact spacing would relabel real contacts, not noise."""
        tol = getattr(laminar, "LAYER_BOUNDARY_TOL_CONTACTS", None)
        assert tol is not None, "the boundary tolerance is not a declared, inspectable constant"
        assert 0.0 < tol <= 1e-4

    def test_a_contact_a_tenth_of_a_contact_outside_is_not_input(self):
        """The tolerance widens the interval by noise, not by anatomy."""
        n, pitch = 24, 100.0
        geom = _geometry(np.arange(n) * pitch, pitch)
        # crossover 11.9, half-span 2.0 -> input [9.9, 13.9]; contact 14 is 0.1 outside.
        labels = label_layers(
            _accepted_result(n, 11.9), geom, granular_thickness_um=DEFAULT_GRANULAR_UM
        )
        assert labels["ch_14"] == "deep"
        assert labels["ch_10"] == "input"
        assert labels["ch_13"] == "input"


class TestADeclaredDepthAxisAnchorsTheFrameAtTheShallowEnd:
    """With `depth_axis` and `shallow_end`, depth runs from the shallow contact into tissue.

    Without the declaration the frame follows the table's row order: the same probe listed
    shallow-first and deep-first gave depths of 400 and 350 um. The declaration anchors both
    `vflip` and `label_layers`; `ProbeGeometry` itself is left as it was.
    """

    DECLARED = {"depth_axis": "z", "shallow_end": "min"}

    @staticmethod
    def _table(perm, layout="rising"):
        """One probe listed in the row order `perm`; contact i is i pitches into tissue.

        rising: z increases into tissue (shallow end "min"); falling: z decreases into
        tissue (shallow end "max"); staggered: y decreases into tissue along the shaft and
        z alternates 0 / 30 um across it, so z is largest at the deep end of 24 contacts.
        """
        i = np.arange(N_CONTACTS)
        x, y, z = np.zeros(N_CONTACTS), np.zeros(N_CONTACTS), PITCH_UM * i
        if layout == "falling":
            z = PITCH_UM * (N_CONTACTS - 1 - i)
        elif layout == "staggered":
            y, z = -PITCH_UM * i, 30.0 * (i % 2)
        frame = pd.DataFrame({
            "x": x, "y": y, "z": z, "channel_id": [f"ch_{k}" for k in i],
        }).iloc[perm].reset_index(drop=True)
        return jnwb.probe_geometry(frame, units="um")

    def _fit(self, perm, layout="rising", accepted=True, **declared):
        freqs, psd = _synthetic_motif()  # row i of psd is the contact i pitches into tissue
        geom = self._table(perm, layout)
        res = vflip(psd[perm], freqs, probe_geometry=geom, **declared)
        assert res.accepted is accepted, res.rejection_reason
        return res, geom

    @staticmethod
    def _orders():
        return {
            "in_order": np.arange(N_CONTACTS),
            "reversed": np.arange(N_CONTACTS)[::-1],
            "permuted": np.random.default_rng(3).permutation(N_CONTACTS),
        }

    @pytest.mark.parametrize("layout, depth_axis, shallow_end", [
        ("rising", "z", "min"),
        ("falling", "z", "max"),
        ("staggered", "y", "max"),
    ])
    def test_the_same_probe_in_any_row_order_gives_one_depth_and_one_labelling(
        self, layout, depth_axis, shallow_end
    ):
        declared = {"depth_axis": depth_axis, "shallow_end": shallow_end}
        fits = {name: self._fit(perm, layout, **declared) for name, perm in self._orders().items()}
        depths = {name: res.crossover_depth_um for name, (res, _) in fits.items()}
        labels = {name: label_layers(res, geom, **declared) for name, (res, geom) in fits.items()}
        assert all(res.depth_anchor == "shallowest" for res, _ in fits.values())
        assert all((res.depth_axis, res.shallow_end) == (depth_axis, shallow_end)
                   for res, _ in fits.values())
        # Every declared fit is the shallow-first fit: the undeclared fit of the rising probe
        # listed shallow-first, crossover, peaks, profile and depth alike.
        reference, _ = self._fit(self._orders()["in_order"])
        for name, (res, _) in fits.items():
            assert res.crossover_contact == pytest.approx(reference.crossover_contact, abs=1e-9), name
            assert (res.low_peak_contact, res.high_peak_contact) == (
                reference.low_peak_contact, reference.high_peak_contact), name
            np.testing.assert_allclose(res.profile, reference.profile, atol=1e-12)
            assert depths[name] == pytest.approx(reference.crossover_depth_um, abs=1e-9), depths
            assert labels[name] == labels["in_order"], name
        if layout == "rising":  # anchored at z = 0, the depth is the crossover's z
            assert depths["in_order"] == pytest.approx(fits["in_order"][0].crossover_z_um, abs=1e-9)

    @pytest.mark.parametrize("layout, depth_axis, shallow_end", [
        ("rising", "z", "max"),     # the wrong end of the right axis
        ("falling", "z", "min"),
        ("staggered", "z", "max"),  # the stagger column: its largest value is at the deep end
    ])
    @pytest.mark.parametrize("order_name", ["in_order", "reversed", "permuted"])
    def test_a_declaration_the_motif_contradicts_rejects_the_fit(
        self, layout, depth_axis, shallow_end, order_name
    ):
        declared = {"depth_axis": depth_axis, "shallow_end": shallow_end}
        res, geom = self._fit(self._orders()[order_name], layout, accepted=False, **declared)
        assert res.rejection_reason == "declaration_contradicted"
        assert res.orientation == "deep_to_superficial" and res.depth_anchor == "shallowest"
        assert res.crossover_contact is None and res.crossover_depth_um is None
        assert res.crossover_z_um is None
        assert set(label_layers(res, geom, **declared).values()) == {"na"}

    def test_vflip_from_lfp_forwards_the_declaration(self):
        geom = self._table(self._orders()["reversed"])
        lfp = np.random.default_rng(11).standard_normal((N_CONTACTS, 4000))
        res = jnwb.vflip_from_lfp(lfp, 1000.0, probe_geometry=geom, **self.DECLARED)
        assert (res.depth_anchor, res.depth_axis, res.shallow_end) == ("shallowest", "z", "min")
        assert jnwb.vflip_from_lfp(lfp, 1000.0, probe_geometry=geom).depth_anchor == "row_order"

    def test_a_fit_rejected_for_too_few_channels_records_the_declaration(self):
        freqs, psd = _synthetic_motif()
        geom = self._table(self._orders()["reversed"])
        mask = np.ones(N_CONTACTS, dtype=bool)
        mask[:3] = False
        res = vflip(psd[::-1], freqs, probe_geometry=geom, bad_channel_mask=mask, **self.DECLARED)
        assert res.rejection_reason == "insufficient_channels"
        assert (res.depth_anchor, res.depth_axis, res.shallow_end) == ("shallowest", "z", "min")
        assert set(label_layers(res, geom, **self.DECLARED).values()) == {"na"}

    @pytest.mark.parametrize("order_name", ["in_order", "reversed", "permuted"])
    def test_depth_range_to_the_crossover_selects_exactly_the_contacts_above_it(self, order_name):
        res, geom = self._fit(self._orders()[order_name], **self.DECLARED)
        labels = label_layers(res, geom, depth_range_um=(0.0, res.crossover_depth_um), **self.DECLARED)
        selected = {ch for ch, lab in labels.items() if lab != "na"}
        above = {f"ch_{i}" for i in range(N_CONTACTS) if i * PITCH_UM <= res.crossover_depth_um}
        assert selected == above and 0 < len(above) < N_CONTACTS

    def test_without_a_declaration_the_row_order_frame_is_kept_and_recorded(self):
        res_in, _ = self._fit(self._orders()["in_order"])
        res_rev, _ = self._fit(self._orders()["reversed"])
        assert res_in.depth_anchor == res_rev.depth_anchor == "row_order"
        assert res_in.to_dict()["depth_anchor"] == "row_order"
        # Deep-first rows keep the frame measured from the deep end.
        assert res_rev.crossover_depth_um == pytest.approx(
            (N_CONTACTS - 1) * PITCH_UM - res_in.crossover_depth_um, abs=1e-6)

    def test_probe_geometry_is_not_reoriented(self):
        """linear_order and orientation stay in row order, byte for byte, through both calls."""
        geom = self._table(self._orders()["reversed"])
        before = (geom.linear_order.tobytes(), geom.orientation.tobytes(),
                  geom.contact_positions.tobytes())
        np.testing.assert_array_equal(geom.linear_order, np.arange(N_CONTACTS))
        np.testing.assert_array_equal(geom.orientation, [0.0, 0.0, -1.0])
        freqs, psd = _synthetic_motif()
        perm = self._orders()["reversed"]
        res = vflip(psd[perm], freqs, probe_geometry=geom, **self.DECLARED)
        label_layers(res, geom, **self.DECLARED)
        after = (geom.linear_order.tobytes(), geom.orientation.tobytes(),
                 geom.contact_positions.tobytes())
        assert after == before

    @pytest.mark.parametrize("declared, match", [
        ({"depth_axis": "w", "shallow_end": "min"}, "depth_axis must be one of"),
        ({"depth_axis": "z", "shallow_end": "top"}, "shallow_end must be one of"),
        ({"depth_axis": "z"}, "declared together"),
        ({"shallow_end": "min"}, "declared together"),
        ({"depth_axis": "x", "shallow_end": "min"}, "does not change"),
    ])
    def test_an_invalid_declaration_raises_in_both_functions(self, declared, match):
        freqs, psd = _synthetic_motif()
        geom = self._table(np.arange(N_CONTACTS))
        with pytest.raises(ValueError, match=match):
            vflip(psd, freqs, probe_geometry=geom, **declared)
        res = vflip(psd, freqs, probe_geometry=geom)
        with pytest.raises(ValueError, match=match):
            label_layers(res, geom, **declared)

    def test_a_declaration_without_a_geometry_raises(self):
        freqs, psd = _synthetic_motif()
        with pytest.raises(ValueError, match="needs a probe_geometry"):
            vflip(psd, freqs, contact_spacing=PITCH_UM, **self.DECLARED)

    def test_label_layers_refuses_a_declaration_the_fit_was_not_made_with(self):
        res_declared, geom = self._fit(self._orders()["reversed"], **self.DECLARED)
        res_plain, _ = self._fit(self._orders()["reversed"])
        with pytest.raises(ValueError, match="same depth declaration"):
            label_layers(res_declared, geom)
        with pytest.raises(ValueError, match="same depth declaration"):
            label_layers(res_plain, geom, **self.DECLARED)
        with pytest.raises(ValueError, match="same depth declaration"):
            label_layers(res_declared, geom, depth_axis="z", shallow_end="max")


class TestTheCrossoverDepthIsInTheLabellingFrame:
    """`crossover_depth_um` is shaft rank times pitch, the frame `label_layers` uses.

    On a shaft whose z falls along the shaft and carries an origin, the crossover's absolute z
    and its rank-times-pitch depth are different numbers; the depth used to be the absolute z
    whenever z varied, so it could not be passed back to `label_layers(depth_range_um=)`.
    """

    Z_TOP_UM = 5000.0

    def _fit(self):
        freqs, psd = _synthetic_motif()
        geom = _geometry(self.Z_TOP_UM - PITCH_UM * np.arange(N_CONTACTS))
        assert np.array_equal(geom.linear_order, np.arange(N_CONTACTS)), (
            "fixture must keep the table in shaft order so only the z direction differs"
        )
        res = vflip(psd, freqs, probe_geometry=geom)
        assert res.accepted
        return res, geom

    def test_depth_is_rank_times_pitch_and_absolute_z_is_its_own_field(self):
        res, geom = self._fit()
        c = res.crossover_contact
        assert res.crossover_depth_um == pytest.approx(c * geom.nominal_pitch, abs=1e-9)
        assert getattr(res, "crossover_z_um", None) == pytest.approx(
            self.Z_TOP_UM - PITCH_UM * c, abs=1e-9
        )
        record = res.to_dict()
        assert record["crossover_depth_um"] == res.crossover_depth_um
        assert record.get("crossover_z_um") == res.crossover_z_um

    @pytest.mark.parametrize("spacing", [None, PITCH_UM])
    def test_depth_range_up_to_the_crossover_selects_the_contacts_above_it(self, spacing):
        freqs, psd = _synthetic_motif()
        geom = _geometry(self.Z_TOP_UM - PITCH_UM * np.arange(N_CONTACTS))
        res = vflip(psd, freqs, probe_geometry=geom, contact_spacing=spacing)
        assert res.accepted and 11.0 < res.crossover_contact < 12.0
        labels = label_layers(res, geom, depth_range_um=(0.0, res.crossover_depth_um))
        selected = [i for i in range(N_CONTACTS) if labels[f"ch_{i}"] != "na"]
        assert selected == list(range(12))

    @pytest.mark.parametrize("entry", ["vflip", "vflip_from_lfp"])
    def test_a_contact_spacing_that_disagrees_with_the_geometry_raises(self, entry):
        """contact_spacing=50 on a 100 um geometry gave depth 575 for contact 11.5, and
        depth_range_um=(0, 575) then selected 6 contacts where 12 lie above the crossover."""
        geom = _geometry(PITCH_UM * np.arange(N_CONTACTS))
        assert geom.nominal_pitch == PITCH_UM
        if entry == "vflip":
            freqs, psd = _synthetic_motif()
            call = lambda: vflip(psd, freqs, probe_geometry=geom, contact_spacing=50.0)  # noqa: E731
        else:
            lfp = np.random.default_rng(0).normal(size=(N_CONTACTS, 2000))
            call = lambda: laminar.vflip_from_lfp(  # noqa: E731
                lfp, 1000.0, probe_geometry=geom, contact_spacing=50.0)
        with pytest.raises(ValueError, match="nominal_pitch"):
            call()

    def test_the_depth_bounds_label_layers_on_the_same_contacts(self):
        res, geom = self._fit()
        labels = label_layers(res, geom, depth_range_um=(0.0, res.crossover_depth_um))
        in_range = [i for i in range(N_CONTACTS) if i * geom.nominal_pitch <= res.crossover_depth_um]
        assert in_range and len(in_range) < N_CONTACTS
        for i in range(N_CONTACTS):
            assert (labels[f"ch_{i}"] != "na") == (i in in_range), i
