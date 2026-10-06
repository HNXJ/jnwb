"""Layer labels for each contact from a vFLIP crossover."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import numpy as np
from ._vflip import VFlipResult, _depth_anchored_order


#: Half-width, in contacts, of the tolerance band around the granular layer boundary used
#: by :func:`label_layers`. The granular interval is closed, so without a tolerance a
#: contact sitting exactly on the boundary -- which is the ordinary case on real hardware,
#: see :func:`label_layers` -- has its layer decided by the last bit of the pitch.
#: 1e-6 contacts is a millionth of a contact spacing and some four orders of magnitude
#: above the float error a realistic pitch and crossover carry.
LAYER_BOUNDARY_TOL_CONTACTS: float = 1e-6


def label_layers(
    vflip_result: VFlipResult,
    probe_geometry: Any,
    *,
    granular_thickness_um: float = 400.0,
    bad_channel_mask: Optional[np.ndarray] = None,
    depth_range_um: Optional[Tuple[float, float]] = None,
    contact_range: Optional[Tuple[float, float]] = None,
    depth_axis: Optional[str] = None,
    shallow_end: Optional[str] = None,
) -> Dict[Any, str]:
    """Assign cortical layer labels (superficial, input, deep) to probe contacts.

    Maps contacts along a linear probe shaft into canonical cortical compartments:
    - ``"superficial"``: Supragranular layers (L1–L3), characterized by gamma dominance.
    - ``"input"``: Granular layer 4 (L4), centered at the spectrolaminar crossover point,
      extending across a zone of width `granular_thickness_um`. The zone is **closed**:
      a contact exactly `granular_thickness_um / 2` from the crossover is ``"input"``,
      and the comparison carries a tolerance of
      :data:`LAYER_BOUNDARY_TOL_CONTACTS` contacts so that convention is decided by the
      stated rule rather than by the last bit of the pitch. Exact equality is the
      ordinary case, not an edge case: at the default 400 um thickness the half-span is
      exactly 10 contacts on a 20 um Neuropixels 1.0, 4 on a 50 um V-probe and 2 on a
      100 um laminar array.
    - ``"deep"``: Infragranular layers (L5–L6), characterized by alpha/beta dominance.
    - ``"na"``: Assigned to all channels whenever `vflip_result.accepted` is `False`, or to
      invalid, bad, or out-of-bounds contacts.

    Critical Invariant:
    Rejected or non-identifiable fits (`vflip_result.accepted is False`) strictly map
    **all** channels to ``"na"``. Never guesses or imputes layers on failed fits. On accepted
    fits, bad contacts (from `bad_channel_mask` or `vflip_result.bad_channel_mask`), contacts
    with non-finite coordinates, and contacts outside `depth_range_um` or `contact_range`
    strictly receive ``"na"``.

    Args:
        vflip_result: :class:`VFlipResult` container from :func:`vflip` or :func:`vflip_from_lfp`.
        probe_geometry: :class:`jnwb.ProbeGeometry` describing the physical contact positions
            and ordering along the linear probe shaft. Must satisfy `is_linear=True`.
        granular_thickness_um: Thickness of the granular layer (input zone) in micrometers (um).
            Must be strictly positive and finite (default: 400.0 um).
        bad_channel_mask: Optional boolean array matching `probe_geometry.channel_ids`. Contacts
            flagged True receive ``"na"``. If omitted, defaults to `vflip_result.bad_channel_mask`.
        depth_range_um: Optional (min_depth_um, max_depth_um) tuple bounding valid cortical depth
            along the shaft, in the frame of `vflip_result.crossover_depth_um`: shaft rank
            times `probe_geometry.nominal_pitch`, from the first contact. Contacts outside this
            range receive ``"na"``.
        contact_range: Optional (min_contact, max_contact) tuple bounding valid contact indices
            along the ordered linear shaft. Contacts outside this range receive ``"na"``.
        depth_axis, shallow_end: The depth declaration `vflip_result` was fitted with (see
            :func:`vflip`). With it, contacts are ranked from the declared shallow end, the
            frame the result's ``crossover_contact`` and ``crossover_depth_um`` are anchored
            in; without it, by `probe_geometry.linear_order` as given. A declaration that
            differs from the result's, including one on either side only, raises rather than
            placing the crossover in the other frame.

    Returns:
        Dictionary mapping channel identifier (from `probe_geometry.channel_ids`) to layer label
        string: ``"superficial"``, ``"input"``, ``"deep"``, or ``"na"``.

    Index space:
        Contacts are placed by their rank along `probe_geometry.linear_order`, so
        `vflip_result.crossover_contact` must be a shaft rank too. A result carrying
        ``index_space='channel'`` was fitted on unreordered PSD rows; it is accepted only
        when this geometry's `linear_order` is the identity, where the two axes coincide,
        and raises otherwise.

    Raises:
        ValueError: If `granular_thickness_um` is non-positive or non-finite, `probe_geometry`
            is not linear, channel count does not match `vflip_result.n_channels`, range bounds
            are invalid, `vflip_result.index_space` is not the shaft rank this geometry
            requires, the depth declaration is invalid (as in :func:`vflip`), or it differs
            from the one `vflip_result` records.

    References:
        Mendoza-Halliday, D., et al. (2024). A ubiquitous spectrolaminar motif of local field
        potential power across the primate cortex. Nature Neuroscience.
        doi:10.1038/s41593-023-01554-7 -- the alpha-beta/gamma crossover as the layer 4
        marker. The paper places layers 2/3 at the gamma peak and 5/6 at the alpha-beta
        peak; the fixed-width input zone of `granular_thickness_um` is this function's rule.
    """
    # 1. Parameter validation
    #
    # The result type is checked first, and structurally rather than by class, because this
    # function is duck-typed on `crossover_contact`. Handed an `XFlipResult` or `ZFlipResult`,
    # which do not carry that field, it used to raise a bare `AttributeError` when
    # `accepted=True` -- and when `accepted=False`, the ordinary case, `or` short-circuits
    # before the field is ever read, so it took the all-"na" path and returned a full-length
    # label array with no error and no warning. A wrong-type result then reads as an honest
    # negative result, which is the failure direction that does not get noticed.
    #
    # Structural and not `isinstance`: any result that genuinely carries this geometry's
    # fields is usable, so the requirement is the fields, not the class.
    _required = ("accepted", "crossover_contact", "n_channels", "index_space")
    _missing = [f for f in _required if not hasattr(vflip_result, f)]
    if _missing:
        raise TypeError(
            f"label_layers requires a vflip-style result carrying {list(_required)}; "
            f"{type(vflip_result).__name__} is missing {_missing}. Layer labelling is defined "
            "against the spectrolaminar crossover along a linear shaft, so a result from a "
            "different flip axis cannot be relabelled into it."
        )

    granular_thickness_um = float(granular_thickness_um)
    if granular_thickness_um <= 0 or not np.isfinite(granular_thickness_um):
        raise ValueError(
            f"granular_thickness_um must be strictly positive and finite (um), got {granular_thickness_um}"
        )

    if depth_range_um is not None:
        if len(depth_range_um) != 2:
            raise ValueError(f"depth_range_um must be a 2-tuple (min_depth, max_depth), got {depth_range_um}")
        min_d, max_d = float(depth_range_um[0]), float(depth_range_um[1])
        if min_d > max_d or not (np.isfinite(min_d) and np.isfinite(max_d)):
            raise ValueError(f"depth_range_um bounds must be finite with min <= max, got {depth_range_um}")

    if contact_range is not None:
        if len(contact_range) != 2:
            raise ValueError(f"contact_range must be a 2-tuple (min_contact, max_contact), got {contact_range}")
        min_c, max_c = float(contact_range[0]), float(contact_range[1])
        if min_c > max_c or not (np.isfinite(min_c) and np.isfinite(max_c)):
            raise ValueError(f"contact_range bounds must be finite with min <= max, got {contact_range}")

    if probe_geometry is None or not getattr(probe_geometry, "is_linear", False):
        raise ValueError("probe_geometry must describe a linear electrode shaft (is_linear=True)")

    channel_ids = list(probe_geometry.channel_ids)
    n_geom_channels = len(channel_ids)
    if n_geom_channels != vflip_result.n_channels:
        raise ValueError(
            f"probe_geometry channel count ({n_geom_channels}) does not match "
            f"vflip_result.n_channels ({vflip_result.n_channels})"
        )

    # The depth frame. The declaration is validated here, before the rejection path, so an
    # invalid one raises whatever the fit; and it must be the one the fit was made with,
    # because a crossover anchored at one end cannot be placed from the other.
    anchored_order, depth_anchor = _depth_anchored_order(
        probe_geometry, getattr(probe_geometry, "linear_order", None),
        depth_axis, shallow_end, "label_layers",
    )
    fitted_with = (
        str(getattr(vflip_result, "depth_anchor", "row_order")),
        getattr(vflip_result, "depth_axis", None),
        getattr(vflip_result, "shallow_end", None),
    )
    if fitted_with != (depth_anchor, depth_axis, shallow_end):
        raise ValueError(
            "label_layers: vflip_result was fitted with depth_anchor="
            f"{fitted_with[0]!r}, depth_axis={fitted_with[1]!r}, shallow_end={fitted_with[2]!r}, "
            f"but label_layers was given depth_axis={depth_axis!r}, shallow_end={shallow_end!r}. "
            "Pass the same depth declaration to both, so the crossover and the contacts share "
            "one frame."
        )

    # 2. Strict rejection invariant: unaccepted fits yield all "na"
    if not vflip_result.accepted or vflip_result.crossover_contact is None:
        return {ch_id: "na" for ch_id in channel_ids}

    # 3. Determine contact positions along shaft
    nominal_pitch = getattr(probe_geometry, "nominal_pitch", None)
    if nominal_pitch is None or nominal_pitch <= 0:
        raise ValueError(
            "probe_geometry.nominal_pitch must be strictly positive to compute layer boundaries in um"
        )
    pitch = float(nominal_pitch)

    # Resolve bad channel mask
    if bad_channel_mask is not None:
        effective_bad = np.asarray(bad_channel_mask, dtype=bool).ravel()
        if len(effective_bad) != n_geom_channels:
            raise ValueError(
                f"bad_channel_mask length ({len(effective_bad)}) does not match "
                f"probe_geometry channel count ({n_geom_channels})"
            )
    else:
        res_bad = getattr(vflip_result, "bad_channel_mask", None)
        if res_bad is not None and len(res_bad) == n_geom_channels:
            effective_bad = np.asarray(res_bad, dtype=bool).ravel()
        else:
            effective_bad = None

    # Number of channels spanning granular layer
    mid_half_span = (granular_thickness_um / 2.0) / pitch
    crossover = float(vflip_result.crossover_contact)

    # Granular (input) boundary interval in contact coordinate space.
    #
    # The interval is CLOSED: a contact lying exactly `granular_thickness_um / 2` from the
    # crossover is `input`. Compared exactly, that convention is decided by float noise
    # rather than by anatomy, because the half-span is an exact integer on the pitches
    # most used in the field -- at the default 400 um thickness, 10.0 contacts on a
    # Neuropixels 1.0 (20 um), 4.0 on a 50 um V-probe, 2.0 on a 100 um laminar array --
    # and one ulp of `pitch` then moves the boundary contact to `superficial` or `deep`.
    # A non-round pitch such as 23.7 um gives 8.43882 and never sits on the edge.
    #
    # The comparison therefore carries an explicit tolerance. It is far below one contact
    # spacing, so it can never pull in a contact that is genuinely a different contact,
    # and far above the float error a realistic pitch carries.
    input_start = crossover - mid_half_span
    input_end = crossover + mid_half_span
    boundary_tol = LAYER_BOUNDARY_TOL_CONTACTS * max(1.0, abs(mid_half_span), abs(crossover))

    # Orientation mapping:
    # Under 'superficial_to_deep': lower contact indices are superficial, higher are deep.
    # Under 'deep_to_superficial': lower contact indices are deep, higher are superficial.
    is_sup_to_deep = (vflip_result.orientation == "superficial_to_deep")

    # Map each channel in channel_ids to its position index along the ordered linear shaft,
    # from the shallow end when a depth axis was declared.
    order = anchored_order
    if order is not None and len(order) == n_geom_channels:
        rank = np.empty(n_geom_channels, dtype=float)
        rank[order] = np.arange(n_geom_channels, dtype=float)
    else:
        rank = np.arange(n_geom_channels, dtype=float)

    # Index-space boundary. `rank` above is shaft rank, and the crossover is compared
    # against it, so a crossover measured on unreordered PSD rows is only meaningful when
    # this table is already ordered along the shaft. Refuse rather than mix the two axes:
    # a rotated or two-bank table returns a full set of confident layer labels for the
    # wrong contacts, with `accepted=True` and nothing to read as a warning.
    #
    # A permutation cannot be pushed through a continuous sub-contact coordinate, and the
    # profile it came from was fitted on contacts that were not neighbours on the shaft,
    # so there is no correction to apply here -- only a refusal.
    result_space = str(getattr(vflip_result, "index_space", "channel"))
    if result_space != "shaft_rank" and not np.array_equal(
        rank, np.arange(n_geom_channels, dtype=float)
    ):
        raise ValueError(
            "vflip_result.crossover_contact is indexed on "
            f"{result_space!r} (raw PSD row order) but probe_geometry has a non-identity "
            "linear_order, so label_layers would read it as a shaft rank and label the "
            "wrong contacts. Pass the same probe_geometry to vflip (or vflip_from_lfp) "
            "so the fit is computed in shaft-rank space."
        )

    labels: Dict[Any, str] = {}
    has_positions = hasattr(probe_geometry, "contact_positions") and probe_geometry.contact_positions is not None

    for idx, ch_id in enumerate(channel_ids):
        # Bad / masked channel exclusion
        if effective_bad is not None and effective_bad[idx]:
            labels[ch_id] = "na"
            continue

        # Contact geometry validity check
        if has_positions:
            pos = probe_geometry.contact_positions[idx]
            if not np.all(np.isfinite(pos)):
                labels[ch_id] = "na"
                continue

        c_pos = float(rank[idx])

        # Shaft support bounds
        if c_pos < 0 or c_pos >= n_geom_channels:
            labels[ch_id] = "na"
            continue

        # Contact index range check
        if contact_range is not None:
            if not (min_c <= c_pos <= max_c):
                labels[ch_id] = "na"
                continue

        # Physical depth range check
        if depth_range_um is not None:
            c_depth = c_pos * pitch
            if not (min_d <= c_depth <= max_d):
                labels[ch_id] = "na"
                continue

        # In-bounds cortical layer assignment, on the closed interval documented above
        if (input_start - boundary_tol) <= c_pos <= (input_end + boundary_tol):
            labels[ch_id] = "input"
        elif c_pos < input_start:
            labels[ch_id] = "superficial" if is_sup_to_deep else "deep"
        else:  # c_pos > input_end
            labels[ch_id] = "deep" if is_sup_to_deep else "superficial"

    return labels
