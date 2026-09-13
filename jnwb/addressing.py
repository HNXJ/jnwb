"""
Anatomical addressing and cortical layer mapping for NWB electrode tables.

Maps units/channels to areas and layers from electrode metadata, and standardizes
units DataFrame fields (unit_id, area, layer, quality flags). Probe labels are
split on comma or slash only; this module carries no area vocabulary and does not
normalize spelling or aliases.
"""

from dataclasses import dataclass
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import pandas as pd
import numpy as np

log = logging.getLogger(__name__)


def parse_probe_areas(label: str) -> tuple:
    """Split a multi-area probe label into ordered area names.

    Splits on comma or slash, trims surrounding whitespace, drops empty fields, and
    otherwise returns each label exactly as the NWB file wrote it. This resolves only
    SEPARATION; which channels fall in which area is decided afterwards, by position
    along the probe.

    No vocabulary lives here, deliberately. Neither identity (is `DP` the same area as
    `V4`?) nor spelling (is `v3a` the same area as `V3a`?) is a question generic
    addressing can answer -- both depend on the recording convention of a particular
    corpus, and a library that answered them would silently impose one project's
    convention on every other. A project that knows its own convention normalizes before
    or after calling this; jnwb does not normalize on its behalf.

    Folding labels together here is also lossy in a way that is easy to miss: under a
    project convention treating DP as an alias of V4, a "DP/V4" probe resolved to
    ('V4', 'V4') -- both halves collapsing to one name, so a two-area probe stopped being
    distinguishable by area at all.

        >>> parse_probe_areas("V1, DP")
        ('V1', 'DP')
        >>> parse_probe_areas("DP/V4")
        ('DP', 'V4')
        >>> parse_probe_areas("V3A/V1")
        ('V3A', 'V1')
        >>> parse_probe_areas("v3d,V2")
        ('v3d', 'V2')

    Self-contained by design: jnwb must give identical scientific behaviour whether or not
    any project package is importable, so nothing here may depend on one being installed.
    """
    return tuple(t for t in (p.strip() for p in re.split(r"[,/]", str(label))) if t)


def _resolve_electrode_row(peak_channel_id: float, electrodes_df: pd.DataFrame):
    """Resolve an electrode row from electrodes_df by channel ID.

    Checks explicit identifier columns ('channel_id', 'id', 'electrode_id') first
    to avoid row index / channel ID substitution when DataFrame index is reset or non-default,
    falling back to DataFrame index lookup.

    Returns:
        (row_index, row_series) or (None, None) if not found.
    """
    if pd.isna(peak_channel_id) or electrodes_df is None or len(electrodes_df) == 0:
        return None, None

    try:
        val = int(float(peak_channel_id))
    except (ValueError, TypeError, OverflowError):
        return None, None

    # 1. Check explicit channel identifier columns first
    has_explicit_id_col = False
    for id_col in ['channel_id', 'id', 'electrode_id']:
        if id_col in electrodes_df.columns:
            has_explicit_id_col = True
            matches = electrodes_df.index[electrodes_df[id_col] == val]
            if len(matches) > 0:
                idx = matches[0]
                return idx, electrodes_df.loc[idx]

    # 2. Fall back to DataFrame index ONLY IF no explicit channel ID column was present
    if not has_explicit_id_col and val in electrodes_df.index:
        return val, electrodes_df.loc[val]

    return None, None


def map_peak_channel_to_area(peak_channel_id: float, electrodes_df: pd.DataFrame) -> Optional[str]:
    """
    Map peak channel ID to brain area location.

    Args:
        peak_channel_id: Channel identifier
        electrodes_df: NWB electrodes DataFrame

    Returns:
        Brain area name (e.g. 'V1', 'PFC', 'FEF') or None if unresolved
    """
    idx, row = _resolve_electrode_row(peak_channel_id, electrodes_df)
    if row is None:
        return None

    try:
        # Check location or area columns in electrodes_df
        col_to_check = None
        for col in ['location', 'area', 'group_name']:
            if col in electrodes_df.columns:
                col_to_check = col
                break

        if col_to_check is None:
            return None

        loc = row.get(col_to_check)
        if pd.notna(loc):
            loc_str = str(loc).strip()

            # Single-area probe: resolve directly, no channel-position logic needed.
            if ',' not in loc_str and '/' not in loc_str:
                return loc_str

            # Multi-area probe (e.g. "V1, V2, V3" on one 128-channel
            # probe): resolve by the channel's POSITION within the
            # probe, not just the first listed area.
            areas = parse_probe_areas(loc_str)

            if len(areas) <= 1:
                return loc_str.split(',')[0].strip()

            group_col = 'group_name' if 'group_name' in electrodes_df.columns else col_to_check
            probe_key = row.get(group_col)
            probe_rows = electrodes_df[electrodes_df[group_col] == probe_key]
            n_channels_on_probe = len(probe_rows)
            if n_channels_on_probe == 0:
                return loc_str.split(',')[0].strip()

            probe_indices = list(probe_rows.index)
            local_idx = probe_indices.index(idx)

            edges = np.linspace(0, n_channels_on_probe, len(areas) + 1)
            bin_idx = int(np.searchsorted(edges, local_idx, side='right')) - 1
            bin_idx = min(max(bin_idx, 0), len(areas) - 1)
            return areas[bin_idx]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        log.debug(f"Failed to map peak channel {peak_channel_id} to area: {e}")

    return None


_DEPTH_UNIT_SCALES: Dict[str, float] = {
    "um": 1.0,
    "µm": 1.0,
    "micron": 1.0,
    "microns": 1.0,
    "micrometer": 1.0,
    "micrometers": 1.0,
    "mm": 1000.0,
    "millimeter": 1000.0,
    "millimeters": 1000.0,
    "m": 1_000_000.0,
    "meter": 1_000_000.0,
    "meters": 1_000_000.0,
}


def _resolve_depth_unit(
    depth_unit: Optional[str],
    row: Optional[pd.Series],
    electrodes_df: Optional[pd.DataFrame],
) -> Optional[str]:
    """Resolve depth unit string from explicit parameter or DataFrame/Series metadata."""
    if depth_unit is not None:
        try:
            return str(depth_unit).strip().lower()
        except Exception:
            return None

    if row is not None:
        for col in ("depth_unit", "z_unit", "unit"):
            if col in row.index and pd.notna(row[col]):
                try:
                    return str(row[col]).strip().lower()
                except Exception:
                    pass

    if electrodes_df is not None:
        for attr_name in ("depth_unit", "z_unit", "unit"):
            val = electrodes_df.attrs.get(attr_name)
            if val is not None and pd.notna(val):
                try:
                    return str(val).strip().lower()
                except Exception:
                    pass
        if "z" in electrodes_df.columns:
            val = electrodes_df["z"].attrs.get("unit")
            if val is not None and pd.notna(val):
                try:
                    return str(val).strip().lower()
                except Exception:
                    pass

    return None


def classify_layer_from_depth(
    peak_channel_id: float,
    electrodes_df: pd.DataFrame,
    *,
    depth_unit: Optional[str] = None,
    threshold: Optional[float] = None,
    threshold_unit: Optional[str] = None,
) -> str:
    """Classify unit cortical layer using z depth coordinates.

    Classifies layer based on electrode z depth ('Superficial' for <= threshold,
    'Deep' for > threshold). To prevent scientific errors from unit ambiguity,
    depth units must be explicitly provided via ``depth_unit`` or declared in
    ``electrodes_df`` metadata/columns ('depth_unit', 'z_unit', 'unit').
    If depth units are unknown or unsupported, returns 'Unknown'.

    .. note::
        This function applies a simple geometric depth threshold along the
        cortical column. The default threshold (1000.0 µm) and physiological
        validity bounds (0.0 <= z <= 20,000.0 µm) are domain-specific model
        assumptions (e.g. primate linear array penetration from pia) rather than
        universal NWB standards. For preparations with different cortical
        thicknesses or orientations, supply ``threshold`` explicitly. For
        electrophysiological laminar identification, see ``jnwb.laminar`` (forthcoming).

    Args:
        peak_channel_id: Channel identifier
        electrodes_df: NWB electrodes DataFrame
        depth_unit: Optional unit of electrode z coordinates (e.g. 'um', 'mm', 'm').
            If None, inspected from electrodes_df metadata.
        threshold: Optional classification threshold. Default is 1000.0 µm.
            If threshold_unit is None, interpreted in ``depth_unit`` units.
        threshold_unit: Optional unit of threshold (e.g. 'um', 'mm').

    Returns:
        Cortical layer label ('Deep', 'Superficial', or 'Unknown')
    """
    if pd.isna(peak_channel_id) or electrodes_df is None or len(electrodes_df) == 0:
        return "Unknown"

    idx, row = _resolve_electrode_row(peak_channel_id, electrodes_df)
    if row is None:
        return "Unknown"

    resolved_unit = _resolve_depth_unit(depth_unit, row, electrodes_df)
    if resolved_unit is None or resolved_unit not in _DEPTH_UNIT_SCALES:
        # Invariant: unknown or incompatible depth units -> 'Unknown'
        return "Unknown"

    scale = _DEPTH_UNIT_SCALES[resolved_unit]

    try:
        if "z" not in electrodes_df.columns:
            return "Unknown"

        z_val = row.get("z")
        if pd.isna(z_val):
            return "Unknown"

        z_float = float(z_val)
        if not np.isfinite(z_float):
            return "Unknown"

        z_um = z_float * scale
        # Physiological sanity bounds: cortical depth from pia is non-negative
        # and bounded within primate brain coordinate bounds (< 20,000 µm)
        if z_um < 0.0 or z_um > 20000.0:
            return "Unknown"

        if threshold is not None:
            t_float = float(threshold)
            if not np.isfinite(t_float):
                return "Unknown"
            if threshold_unit is not None:
                t_unit_norm = str(threshold_unit).strip().lower()
                if t_unit_norm not in _DEPTH_UNIT_SCALES:
                    return "Unknown"
                thresh_um = t_float * _DEPTH_UNIT_SCALES[t_unit_norm]
            else:
                thresh_um = t_float * scale
        else:
            # Default canonical threshold: 1000.0 µm
            thresh_um = 1000.0

        if thresh_um <= 0.0 or thresh_um > 20000.0 or not np.isfinite(thresh_um):
            return "Unknown"

        return "Deep" if z_um > thresh_um else "Superficial"
    except (ValueError, TypeError, OverflowError) as e:
        log.debug(f"Failed to classify layer for channel {peak_channel_id}: {e}")

    return "Unknown"


def enrich_units_dataframe(
    units_df: pd.DataFrame,
    electrodes_df: Optional[pd.DataFrame],
    *,
    depth_unit: Optional[str] = None,
    threshold: Optional[float] = None,
    threshold_unit: Optional[str] = None,
) -> pd.DataFrame:
    """Enrich units DataFrame with standardized area, layer, and quality flags.

    Enforces SC-002: Terminology alignment (using unit_id and standard quality flags).

    Args:
        units_df: Raw NWB units DataFrame
        electrodes_df: Raw NWB electrodes DataFrame
        depth_unit: Optional unit for electrode depth coordinates (e.g. 'um', 'mm').
        threshold: Optional depth threshold for layer classification.
        threshold_unit: Optional unit for threshold.

    Returns:
        Standardized and enriched DataFrame
    """
    df = units_df.copy()

    # 1. Standardize unit_id column
    if 'cluster_id' in df.columns and 'unit_id' not in df.columns:
        df = df.rename(columns={'cluster_id': 'unit_id'})
    
    # If the index is 'id' or unnamed and representing unit indices, expose unit_id
    if 'unit_id' not in df.columns:
        if df.index.name == 'id' or df.index.name is None:
            df['unit_id'] = df.index
        else:
            df['unit_id'] = np.arange(len(df))

    # 2. Enrich anatomical mapping if electrodes_df is provided
    if electrodes_df is not None and len(electrodes_df) > 0 and 'peak_channel_id' in df.columns:
        df['area'] = df['peak_channel_id'].apply(lambda x: map_peak_channel_to_area(x, electrodes_df))
        df['layer'] = df['peak_channel_id'].apply(
            lambda x: classify_layer_from_depth(
                x,
                electrodes_df,
                depth_unit=depth_unit,
                threshold=threshold,
                threshold_unit=threshold_unit,
            )
        )
        
        # Resolve group_name/probe mapping
        col_group = 'group_name' if 'group_name' in electrodes_df.columns else ('probe' if 'probe' in electrodes_df.columns else None)
        if col_group is not None:
            def _get_group(x):
                _, r = _resolve_electrode_row(x, electrodes_df)
                return r.get(col_group) if r is not None else None
            df['group_name'] = df['peak_channel_id'].apply(_get_group)
        else:
            df['group_name'] = None
    else:
        if 'area' not in df.columns:
            df['area'] = None
        if 'layer' not in df.columns:
            df['layer'] = 'Unknown'
        if 'group_name' not in df.columns:
            df['group_name'] = None

    # 3. Handle quality and stable flags
    # Standard quality cutoff: quality >= 1.0 is stable for numeric metrics;
    # for categorical quality labels, standard accepted good labels are stable.
    if 'quality' in df.columns:
        q_num = pd.to_numeric(df['quality'], errors='coerce')
        if q_num.notna().any():
            df['is_stable'] = q_num >= 1.0
        else:
            _GOOD_LABELS = {"good", "sua", "single", "stable", "clean"}
            df['is_stable'] = df['quality'].astype(str).str.strip().str.lower().isin(_GOOD_LABELS)
    else:
        if 'is_stable' not in df.columns:
            df['is_stable'] = False

    # Force conversion of core types. snr/unit_id are stored as dtype=str
    # (object) on some sessions but float64 on others — the same cross-session dtype
    # inconsistency already worked around
    # for snr in scripts/filter_units.py. unit_id is used as an identity
    # key for equality/isin comparisons throughout the codebase (session.py
    # get_spike_times, factories.py dataset_from_session, etc.) - an
    # object-dtype string column silently fails every such comparison
    # (df['unit_id'] == 156 is always False if the stored value is the
    # string '156.0'), confirmed 2026-07-12. Coerced here at the source.
    for col in ['firing_rate', 'waveform_duration', 'snr', 'unit_id']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Ensure clean RangeIndex (0 to N-1) to guarantee row-position lookup in get_spike_times
    df = df.reset_index(drop=True)

    return df


@dataclass(frozen=True)
class ProbeGeometry:
    """Extracted contact geometry and spatial properties for an electrode array.

    Parameters
    ----------
    contact_positions : np.ndarray
        Array of shape ``(n_channels, 3)`` giving 3D Cartesian coordinates of each
        contact in micrometers (:math:`\\mu\\mathrm{m}`).
    channel_ids : np.ndarray
        Array of shape ``(n_channels,)`` giving original channel or electrode identifiers.
    nominal_pitch : float | None
        Nominal (median) inter-contact distance between adjacent ordered contacts in
        micrometers (:math:`\\mu\\mathrm{m}`), or ``None`` if ``n_channels < 2``.
    pitch_tolerance : float
        Fractional tolerance used to evaluate nominal pitch uniformity.
    is_linear : bool
        Whether contacts fall along a single linear probe shaft within tolerance.
    is_uniform : bool
        Whether inter-contact spacing along the ordered contacts is uniform within tolerance.
    linear_order : np.ndarray
        Array of shape ``(n_channels,)`` containing integer indices sorting contacts
        along the principal probe axis.
    orientation : np.ndarray | None
        Unit vector of shape ``(3,)`` giving the orientation of the principal linear axis
        (oriented from the first sorted contact toward the last), or ``None`` if ``n_channels < 2``.
    probe_name : str | None
        Name or identifier of the probe group/shank, or ``None``.
    units : str
        Spatial coordinate units, always ``"um"``.
    """

    contact_positions: np.ndarray
    channel_ids: np.ndarray
    nominal_pitch: Optional[float]
    pitch_tolerance: float
    is_linear: bool
    is_uniform: bool
    linear_order: np.ndarray
    orientation: Optional[np.ndarray]
    probe_name: Optional[str]
    units: str = "um"


def probe_geometry(
    electrodes_table: Any,
    *,
    probe_name: Optional[str] = None,
    units: str = "um",
    nominal_pitch: Optional[float] = None,
    pitch_tolerance: float = 0.1,
    strict_linear: bool = False,
) -> ProbeGeometry:
    """Extract contact geometry, linear ordering, and spacing from electrode coordinates.

    Extracts contact positions and spatial geometry from an NWB electrode table or coordinate
    array with explicit units. Converts coordinates to micrometers (:math:`\\mu\\mathrm{m}`),
    validates inter-contact pitch within tolerance, evaluates linearity, and determines
    ordered contact sequence along the probe shaft without inferring cortical layer identity.

    Parameters
    ----------
    electrodes_table : pandas.DataFrame, pynwb.ecephys.ElectrodeTable, or np.ndarray
        Electrode metadata source. Can be:
        - A pandas DataFrame containing Cartesian coordinate columns ('x', 'y', 'z') or ('rel_x', 'rel_y', 'rel_z').
        - A PyNWB ``ElectrodeTable`` instance.
        - A NumPy array of shape ``(n_channels, 3)`` giving coordinate positions.
    probe_name : str, optional
        Specific probe/group name to filter by when the table contains multiple probes.
        If ``None`` and multiple probes are present, raises :class:`ValueError`.
    units : str, default "um"
        Spatial unit of the input coordinates. Must be a supported length unit
        (e.g. ``"um"``, ``"mm"``, ``"m"``). Raises :class:`ValueError` if unsupported.
    nominal_pitch : float, optional
        Expected inter-contact spacing in input units. If omitted, estimated from the
        median Euclidean distance between adjacent ordered contacts.
    pitch_tolerance : float, default 0.1
        Allowable relative deviation from nominal pitch:
        :math:`|\\Delta d - d_{\\mathrm{nom}}| \\le \\epsilon \\cdot d_{\\mathrm{nom}}`.
        Must be non-negative.
    strict_linear : bool, default False
        If ``True``, raises :class:`ValueError` if the probe contacts do not conform to a
        linear geometry within tolerance.

    Returns
    -------
    ProbeGeometry
        Extracted contact geometry dataclass with positions in :math:`\\mu\\mathrm{m}`.

    Raises
    ------
    ValueError
        If units are unknown or unsupported, coordinates contain NaNs/infinities,
        duplicate coordinates are detected, table is empty, multiple probes are present
        without specifying ``probe_name``, the specified probe is not found, or
        ``strict_linear=True`` on non-linear geometry.
    """
    if pitch_tolerance < 0.0 or not np.isfinite(pitch_tolerance):
        raise ValueError(f"pitch_tolerance must be a non-negative finite float, got {pitch_tolerance}")

    units_norm = str(units).strip().lower()
    if units_norm not in _DEPTH_UNIT_SCALES:
        raise ValueError(
            f"Unsupported coordinate units '{units}'. Supported units: {sorted(_DEPTH_UNIT_SCALES.keys())}"
        )
    scale = _DEPTH_UNIT_SCALES[units_norm]

    # 1. Parse input table / coordinates
    df: Optional[pd.DataFrame] = None
    coords: Optional[np.ndarray] = None
    channel_ids: Optional[np.ndarray] = None

    if isinstance(electrodes_table, pd.DataFrame):
        df = electrodes_table.copy()
    elif hasattr(electrodes_table, "to_dataframe") and callable(electrodes_table.to_dataframe):
        df = electrodes_table.to_dataframe()
    elif isinstance(electrodes_table, (np.ndarray, list, tuple)):
        arr = np.asarray(electrodes_table, dtype=np.float64)
        if arr.ndim != 2 or arr.shape[1] != 3:
            raise ValueError(
                f"Array coordinates must have shape (n_channels, 3), got {arr.shape}"
            )
        coords = arr
        channel_ids = np.arange(len(arr))

    if df is not None:
        if len(df) == 0:
            raise ValueError("Electrodes table is empty")

        # Probe filtering across possible group columns
        group_col = None
        for cand in ("group_name", "group", "probe", "device"):
            if cand in df.columns:
                group_col = cand
                break

        resolved_probe_name = probe_name
        if group_col is not None:
            # Check if group values are PyNWB objects with name attributes
            group_vals = df[group_col].apply(
                lambda v: getattr(v, "name", str(v)) if pd.notna(v) else None
            )
            df["_probe_group_resolved"] = group_vals
            unique_probes = [p for p in df["_probe_group_resolved"].dropna().unique()]

            if probe_name is not None:
                df = df[df["_probe_group_resolved"] == probe_name]
                if len(df) == 0:
                    raise ValueError(
                        f"Probe '{probe_name}' not found in electrodes table. Available probes: {unique_probes}"
                    )
            else:
                if len(unique_probes) > 1:
                    raise ValueError(
                        f"Multiple probes found in electrodes table: {unique_probes}. "
                        "Pass probe_name=<name> explicitly to select one."
                    )
                if len(unique_probes) == 1:
                    resolved_probe_name = str(unique_probes[0])

        # Extract coordinate columns
        coord_cols = None
        for cand_triplet in [("x", "y", "z"), ("rel_x", "rel_y", "rel_z")]:
            if all(c in df.columns for c in cand_triplet):
                coord_cols = cand_triplet
                break

        if coord_cols is None:
            raise ValueError(
                f"Electrodes table must contain 3D coordinates ('x', 'y', 'z'). Columns present: {list(df.columns)}"
            )

        # Extract channel identifiers
        id_col = None
        for cand_id in ["channel_id", "id", "electrode_id"]:
            if cand_id in df.columns:
                id_col = cand_id
                break
        if id_col is not None:
            channel_ids = np.asarray(df[id_col].values)
        else:
            channel_ids = np.asarray(df.index.values)

        coords_raw = df[list(coord_cols)].to_numpy(dtype=np.float64)
        coords = coords_raw
    else:
        resolved_probe_name = probe_name

    assert coords is not None
    assert channel_ids is not None

    n_channels = coords.shape[0]
    if n_channels == 0:
        raise ValueError("Cannot extract probe geometry from zero contacts")

    # 2. Check finiteness
    if not np.all(np.isfinite(coords)):
        raise ValueError("Contact coordinates contain NaN or non-finite values")

    # 3. Scale to micrometers (um)
    coords_um = coords * scale

    # 4. Check duplicate coordinates
    # Rounded to 6 decimal places to detect exact or near-duplicate duplicates
    _, unique_indices = np.unique(np.round(coords_um, decimals=6), axis=0, return_index=True)
    if len(unique_indices) < n_channels:
        raise ValueError(
            f"Duplicate contact coordinates detected: {n_channels} channels but only {len(unique_indices)} unique locations"
        )

    # 5. Boundary case: n_channels == 1
    if n_channels == 1:
        return ProbeGeometry(
            contact_positions=coords_um,
            channel_ids=channel_ids,
            nominal_pitch=None,
            pitch_tolerance=pitch_tolerance,
            is_linear=True,
            is_uniform=True,
            linear_order=np.array([0], dtype=int),
            orientation=None,
            probe_name=resolved_probe_name,
            units="um",
        )

    # 6. Assess linearity via Principal Component Analysis (SVD)
    centered = coords_um - np.mean(coords_um, axis=0)
    # SVD of centered coordinates: U * S * Vt
    # coords shape (n, 3); Vt shape (3, 3) where Vt[0] is first principal component direction
    _, s, vt = np.linalg.svd(centered, full_matrices=False)
    principal_dir = vt[0]

    # Projections along principal component
    projections = np.dot(centered, principal_dir)

    # Sort contacts along principal direction
    linear_order = np.argsort(projections)
    sorted_proj = projections[linear_order]
    sorted_coords = coords_um[linear_order]

    # Ensure orientation points in the direction of sorted projections
    if (sorted_proj[-1] - sorted_proj[0]) < 0:
        principal_dir = -principal_dir
        projections = np.dot(centered, principal_dir)
        linear_order = np.argsort(projections)
        sorted_proj = projections[linear_order]
        sorted_coords = coords_um[linear_order]

    unit_orientation = principal_dir / np.linalg.norm(principal_dir)

    # Reconstructed positions along the linear axis: mean + proj * unit_orientation
    mean_pos = np.mean(coords_um, axis=0)
    reconstructed = mean_pos + np.outer(projections, unit_orientation)
    residuals = np.linalg.norm(coords_um - reconstructed, axis=1)
    max_residual = np.max(residuals)

    # Inter-contact distances along sorted order
    diffs = np.diff(sorted_coords, axis=0)
    step_distances = np.linalg.norm(diffs, axis=1)

    # Derived or explicit nominal pitch in micrometers
    if nominal_pitch is not None:
        nom_pitch_um = float(nominal_pitch) * scale
        if nom_pitch_um <= 0.0 or not np.isfinite(nom_pitch_um):
            raise ValueError(f"nominal_pitch must be positive and finite, got {nominal_pitch}")
    else:
        nom_pitch_um = float(np.median(step_distances))

    # Linearity condition: transverse residuals must be small compared to nominal pitch
    # Allow at most max(pitch_tolerance * nom_pitch_um, 1e-4) deviation from the line
    line_tol = max(pitch_tolerance * nom_pitch_um, 1e-4) if nom_pitch_um > 0 else 1e-4
    is_linear = bool(max_residual <= line_tol)

    if strict_linear and not is_linear:
        raise ValueError(
            f"Probe geometry is non-linear: maximum off-axis deviation {max_residual:.3f} um "
            f"exceeds tolerance {line_tol:.3f} um"
        )

    # Uniformity condition: step distances within pitch_tolerance of nominal pitch
    pitch_err = np.abs(step_distances - nom_pitch_um)
    is_uniform = bool(is_linear and np.all(pitch_err <= (pitch_tolerance * nom_pitch_um + 1e-6)))

    return ProbeGeometry(
        contact_positions=coords_um,
        channel_ids=channel_ids,
        nominal_pitch=nom_pitch_um,
        pitch_tolerance=pitch_tolerance,
        is_linear=is_linear,
        is_uniform=is_uniform,
        linear_order=linear_order,
        orientation=unit_orientation,
        probe_name=resolved_probe_name,
        units="um",
    )


