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
