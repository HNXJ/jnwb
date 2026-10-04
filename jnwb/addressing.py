"""
Anatomical addressing and geometric depth classes for NWB electrode tables.

Maps units/channels to areas and depth classes from electrode metadata, and standardizes
units DataFrame fields (unit_id, area, depth_class, quality flags). Probe labels are
split on comma or slash only, keeping a slash inside an atlas layer label; this module
carries no area vocabulary and does not normalize spelling or aliases.
"""

from dataclasses import dataclass
import logging
from typing import Any, Collection, Dict, List, Optional, Sequence, Union
import pandas as pd
import numpy as np

log = logging.getLogger(__name__)

# The strings pandas' own readers parse as missing by default. The set is a private pandas name,
# so the copy below, taken from pandas 3.0.5, stands in if it moves.
_PANDAS_NA_FALLBACK = frozenset({
    "", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan", "1.#IND", "1.#QNAN",
    "<NA>", "N/A", "NA", "NULL", "NaN", "None", "n/a", "nan", "null",
})
try:
    from pandas._libs.parsers import STR_NA_VALUES as _PANDAS_NA_STRINGS
except ImportError:
    _PANDAS_NA_STRINGS = _PANDAS_NA_FALLBACK

# Compared after strip() and lower(); "nat" is how a missing datetime prints.
_MISSING_TEXT = frozenset(s.lower() for s in _PANDAS_NA_STRINGS) | {"nat"}

# The text quality labels `enrich_units_dataframe` reads as stable by default; a convention
# with no cited source, which the caller replaces through `stable_labels`.
_STABLE_QUALITY_LABELS = ("good", "sua", "single", "stable", "clean")


def _stable_label_set(stable_labels, caller: str) -> frozenset:
    """``stable_labels`` as compared: stripped and lower-cased. A bare string is refused,
    because iterating it would accept each of its characters as a label."""
    if isinstance(stable_labels, (str, bytes)):
        raise TypeError(
            f"{caller}: stable_labels must be a collection of labels, not the string "
            f"{stable_labels!r}; pass ({stable_labels!r},) for one label."
        )
    labels = frozenset(str(label).strip().lower() for label in stable_labels)
    if not labels:
        raise ValueError(
            f"{caller}: stable_labels is empty, so no text label could be stable; pass at "
            "least one label."
        )
    return labels


def _finite_cutoff(value, name: str, caller: str) -> float:
    """A cut-off as compared: a finite real number. ``None`` or a non-number raises
    ``TypeError``; NaN or an infinity raises ``ValueError``, because every comparison with it
    passes or fails every unit alike."""
    if value is None or isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, float, np.integer, np.floating)):
        raise TypeError(f"{caller}: {name} must be a finite number, not {value!r}.")
    if not np.isfinite(value):
        raise ValueError(
            f"{caller}: {name} is {value!r}; a non-finite cut-off passes or fails every unit "
            "alike. Pass a finite number."
        )
    return float(value)


def _quality_is_stable(quality: pd.Series, stable_threshold: float,
                       labels: frozenset) -> pd.Series:
    """The one quality rule: nullable-boolean stability per unit.

    When any value is numeric the column is read as codes, stable when
    ``quality >= stable_threshold``; otherwise as text labels, stable when the stripped,
    lower-cased label is in ``labels``. A unit whose quality is missing, the text of a missing
    value, not a number in a numeric column, or infinite is ``<NA>``: unknown, not unstable.
    """
    # Numeric columns arrive as `str` on some sessions, so a missing value can be the text of
    # one (any string pandas reads as missing, or "NaT") rather than a real NaN.
    text = quality.astype(str).str.strip().str.lower()
    present = quality.notna() & ~text.isin(_MISSING_TEXT)
    q_num = pd.to_numeric(quality, errors='coerce')
    if q_num.notna().any():
        # An infinite quality is no quality code: undefined, as a NaN is.
        finite = pd.Series(np.isfinite(q_num.to_numpy(dtype=float, na_value=np.nan)),
                           index=q_num.index)
        usable, stable = finite, q_num >= stable_threshold
    else:
        usable, stable = present, text.isin(labels)
    return stable.astype('boolean').mask(~usable)


def parse_probe_areas(label: str) -> tuple:
    """Split a multi-area probe label into ordered area names.

    Splits on comma or slash, trims surrounding whitespace, drops empty fields, and
    otherwise returns each label exactly as the NWB file wrote it. This resolves only
    SEPARATION; which channels fall in which area is decided afterwards, by position
    along the probe.

    A slash followed by a field that does not start with a letter continues the label
    before it rather than starting a new area, because atlas layer labels use a slash
    inside one name: ``VISpm2/3`` is layer 2/3 of one area, not the two areas ``VISpm2``
    and ``3``. A slash between two names that start with letters still separates areas.

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
        >>> parse_probe_areas("VISpm2/3")
        ('VISpm2/3',)
        >>> parse_probe_areas("VISp2/3, VISp4")
        ('VISp2/3', 'VISp4')

    Self-contained by design: jnwb must give identical scientific behaviour whether or not
    any project package is importable, so nothing here may depend on one being installed.
    """
    fields: list[str] = []
    for part in str(label).split(","):
        merged: list[str] = []
        for piece in (p.strip() for p in part.split("/")):
            if not piece:
                continue
            if merged and not piece[0].isalpha():
                merged[-1] = f"{merged[-1]}/{piece}"
            else:
                merged.append(piece)
        fields.extend(merged)
    return tuple(fields)


def _resolve_electrode_row(peak_channel_id: float, electrodes_df: pd.DataFrame):
    """Resolve an electrode row from electrodes_df by channel ID.

    The ID is looked up in the first identifier column present, in the order 'channel_id',
    'id', 'electrode_id', so a reset or non-default DataFrame index is never read as a channel
    ID. Only that column is searched: the columns can number channels differently, so an ID
    missing from it resolves to nothing rather than to a row of another numbering. The
    DataFrame index is used only when no identifier column exists.

    Returns:
        (row_index, row_series) or (None, None) if not found.
    """
    if pd.isna(peak_channel_id) or electrodes_df is None or len(electrodes_df) == 0:
        return None, None

    try:
        val = int(float(peak_channel_id))
    except (ValueError, TypeError, OverflowError):
        return None, None

    id_col = _identifier_column(electrodes_df)
    if id_col is not None:
        matches = electrodes_df.index[electrodes_df[id_col] == val]
        if len(matches) > 0:
            idx = matches[0]
            return idx, electrodes_df.loc[idx]
        return None, None

    if val in electrodes_df.index:
        return val, electrodes_df.loc[val]

    return None, None


def _identifier_column(electrodes_df: pd.DataFrame) -> Optional[str]:
    """The channel identifier column :func:`_resolve_electrode_row` searches, or None."""
    for id_col in ('channel_id', 'id', 'electrode_id'):
        if id_col in electrodes_df.columns:
            return id_col
    return None


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
    return _area_from_row(peak_channel_id, idx, row, electrodes_df, {})


_MISSING = object()


def _electrode_row_resolver(electrodes_df: pd.DataFrame):
    """Return ``val -> (row_index, row)`` agreeing with :func:`_resolve_electrode_row`.

    ``val`` is the integer channel ID that function derives. When the identifier column it
    searches has a NumPy integer, unsigned, boolean or float64 dtype, one pass over the column
    builds a first-match table, so a lookup is O(1) rather than a comparison over the whole
    table; a float64 column is keyed with ``float(val)``, the conversion ``==`` applies. A
    narrower float column is excluded because ``==`` rounds ``val`` to that float's mantissa
    (16777217 equals a float32 16777216), which a table keyed on exact values would miss. Any
    other identifier column, or none, falls back to :func:`_resolve_electrode_row` per call.
    """
    id_col = _identifier_column(electrodes_df)
    fast = id_col is not None and (
        isinstance(electrodes_df[id_col], pd.Series)
        and isinstance(electrodes_df[id_col].dtype, np.dtype)
        and (electrodes_df[id_col].dtype.kind in 'iub'
             or electrodes_df[id_col].dtype == np.float64)
    )
    if not fast:
        return lambda val: _resolve_electrode_row(val, electrodes_df)

    col = electrodes_df[id_col]
    first: dict = {}
    for key, idx in zip(col.to_numpy().tolist(), electrodes_df.index):
        first.setdefault(key, idx)
    is_float = col.dtype.kind == 'f'

    def resolve(val):
        idx = first.get(float(val) if is_float else val, _MISSING)
        if idx is not _MISSING:
            return idx, electrodes_df.loc[idx]
        return None, None

    return resolve


def _channel_key(peak_channel_id):
    """The integer :func:`_resolve_electrode_row` looks up, or None where it finds nothing."""
    if pd.isna(peak_channel_id):
        return None
    try:
        return int(float(peak_channel_id))
    except (ValueError, TypeError, OverflowError):
        return None


def _area_from_row(peak_channel_id, idx, row, electrodes_df: pd.DataFrame,
                   probe_cache: dict) -> Optional[str]:
    """The area of an already resolved electrode row; ``probe_cache`` holds each probe's rows."""
    if row is None:
        return None

    try:
        # Check location or area columns in electrodes_df
        col_to_check = None
        # `group_name` is the probe/shank label, not an anatomical area. Including it
        # meant an electrode table with no location column returned 'probeA' as the brain
        # area of channel 0 -- a fabricated label indistinguishable from a real one.
        for col in ['location', 'area']:
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
            # Only plain scalar keys are cached, so every cache key hashes.
            cacheable = probe_key is None or isinstance(probe_key, (str, int, float, np.number))
            probe_indices = probe_cache.get((group_col, probe_key)) if cacheable else None
            if probe_indices is None:
                probe_rows = electrodes_df[electrodes_df[group_col] == probe_key]
                probe_indices = list(probe_rows.index)
                if cacheable:
                    probe_cache[(group_col, probe_key)] = probe_indices
            n_channels_on_probe = len(probe_indices)
            if n_channels_on_probe == 0:
                return loc_str.split(',')[0].strip()

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
    """Classify a unit's geometric depth class from electrode z depth.

    Thresholds electrode z depth ('Superficial' for <= threshold,
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
        electrophysiological laminar identification, see ``jnwb.laminar``.

    Args:
        peak_channel_id: Channel identifier
        electrodes_df: NWB electrodes DataFrame
        depth_unit: Optional unit of electrode z coordinates (e.g. 'um', 'mm', 'm').
            If None, inspected from electrodes_df metadata.
        threshold: Optional classification threshold. Default is 1000.0 µm.
            If threshold_unit is None, interpreted in ``depth_unit`` units.
        threshold_unit: Optional unit of threshold (e.g. 'um', 'mm').

    Returns:
        Geometric depth class ('Deep', 'Superficial', or 'Unknown'), not a cortical layer
    """
    if pd.isna(peak_channel_id) or electrodes_df is None or len(electrodes_df) == 0:
        return "Unknown"

    _, row = _resolve_electrode_row(peak_channel_id, electrodes_df)
    return _depth_class_from_row(peak_channel_id, row, electrodes_df, depth_unit, threshold,
                                 threshold_unit)


def _depth_class_from_row(peak_channel_id, row, electrodes_df: pd.DataFrame,
                          depth_unit: Optional[str], threshold: Optional[float],
                          threshold_unit: Optional[str]) -> str:
    """The depth class of an already resolved electrode row."""
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
    stable_threshold: float = 1.0,
    stable_labels: Collection[str] = _STABLE_QUALITY_LABELS,
) -> pd.DataFrame:
    """Enrich units DataFrame with standardized area, depth class, and quality flags.

    Enforces SC-002: Terminology alignment (using unit_id and standard quality flags).

    The geometric class from :func:`classify_layer_from_depth` ('Deep', 'Superficial' or
    'Unknown') is written to ``depth_class``. It is a threshold on electrode depth, not a
    cortical layer; the electrophysiological laminar identity is ``jnwb.label_layers``.

    No ``layer`` column is written. One already on ``units_df`` is returned as supplied.

    ``is_stable`` is derived from a ``quality`` column -- ``quality >= stable_threshold`` when
    it is numeric, membership in ``stable_labels`` (compared lower-cased and stripped)
    otherwise -- and is not added when ``units_df``
    has no ``quality`` column, or one holding only NaN, None, blank strings or the text of a
    missing value, because there is nothing to derive it from. The text of a missing value is
    any string ``pandas.read_csv`` reads as missing by default (``"nan"``, ``"n/a"``, ``"<NA>"``,
    ``"#N/A"``, ``"-1.#IND"``, ...) or ``"NaT"``, compared case-insensitively after stripping
    whitespace. When it is added, ``is_stable`` has pandas' nullable ``"boolean"`` dtype, and a
    unit whose own quality is missing, is not a number in a numeric column, or is infinite
    (no quality code) is ``<NA>``: its stability is unknown, not ``False``.

    Args:
        units_df: Raw NWB units DataFrame
        electrodes_df: Raw NWB electrodes DataFrame
        depth_unit: Optional unit for electrode depth coordinates (e.g. 'um', 'mm').
        threshold: Optional depth threshold for the depth class.
        threshold_unit: Optional unit for threshold.
        stable_threshold: numeric quality at or above which a unit is stable.
        stable_labels: text quality labels read as stable, a collection; a bare string
            raises ``TypeError`` and an empty one ``ValueError``, as does a
            ``stable_threshold`` that is NaN or infinite (``None`` raises ``TypeError``).
            Both defaults, 1.0 and
            ``("good", "sua", "single", "stable", "clean")``, are a convention with no cited
            source: pass the rule your sorter's codes follow.
            :func:`jnwb.assign_quality_tier` applies the same rule through the same code.

    Returns:
        Standardized and enriched DataFrame
    """
    labels = _stable_label_set(stable_labels, "enrich_units_dataframe")
    stable_threshold = _finite_cutoff(stable_threshold, "stable_threshold",
                                      "enrich_units_dataframe")
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
        # Units share channels, so each channel is resolved and classified once and every
        # unit on it reads the cached answer: the per-unit step is a dict lookup instead of
        # three comparisons over the whole electrode table.
        col_group = 'group_name' if 'group_name' in electrodes_df.columns else ('probe' if 'probe' in electrodes_df.columns else None)
        resolve = _electrode_row_resolver(electrodes_df)
        probe_cache: dict = {}
        per_channel: dict = {}

        def _enrich(x):
            key = _channel_key(x)
            try:
                return per_channel[key]
            except KeyError:
                pass
            idx, row = (None, None) if key is None else resolve(key)
            per_channel[key] = (
                _area_from_row(x, idx, row, electrodes_df, probe_cache),
                _depth_class_from_row(x, row, electrodes_df, depth_unit, threshold,
                                      threshold_unit),
                row.get(col_group) if row is not None and col_group is not None else None,
            )
            return per_channel[key]

        df['area'] = df['peak_channel_id'].apply(lambda x: _enrich(x)[0])
        df['depth_class'] = df['peak_channel_id'].apply(lambda x: _enrich(x)[1])
        if col_group is not None:
            df['group_name'] = df['peak_channel_id'].apply(lambda x: _enrich(x)[2])
        else:
            df['group_name'] = None
    else:
        if 'area' not in df.columns:
            df['area'] = None
        if 'depth_class' not in df.columns:
            df['depth_class'] = 'Unknown'
        if 'group_name' not in df.columns:
            df['group_name'] = None

    # 3. Handle quality and stable flags: quality >= stable_threshold for numeric codes,
    # membership in stable_labels for text labels; both are the caller's to set.
    if 'quality' in df.columns:
        stable = _quality_is_stable(df['quality'], stable_threshold, labels)
        if stable.notna().any():
            df['is_stable'] = stable
    # With no quality column, or one holding only NaN, None or blank strings, there is nothing
    # to derive stability from, so no `is_stable` is added: an all-<NA> column would be a
    # label with no data behind it.

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


# Smallest advance along the shaft axis, as a fraction of the mean advance, that still
# counts as two contacts sitting at distinct depths. Contacts that share a depth (a planar
# grid, a paired ladder) fall far below this and do not describe a shaft.
_MIN_AXIAL_STEP_FRACTION = 0.2


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
        A staggered (zig-zag / multi-column) shaft is linear: what matters is that
        contacts advance monotonically along the shaft axis, not that they are collinear.
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
    stagger_um : float
        Lateral extent of the contacts perpendicular to the shaft axis, in micrometers
        (:math:`\\mu\\mathrm{m}`). ``0.0`` for a single-column (collinear) shaft; for a
        staggered two-column shaft this is the separation between the columns.
    is_staggered : bool
        Whether the contacts carry a lateral offset from the shaft axis large enough
        that the shaft is not collinear. A staggered shaft is still ``is_linear=True``.
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
    stagger_um: float = 0.0
    is_staggered: bool = False


def probe_geometry(
    electrodes_table: Any,
    *,
    probe_name: Optional[str] = None,
    units: str = "um",
    nominal_pitch: Optional[float] = None,
    pitch_tolerance: float = 0.1,
    strict_linear: bool = False,
    stagger_tolerance_um: float = 100.0,
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
        median *advance along the shaft axis* between adjacent ordered contacts. On a
        staggered shaft this is the axial step, not the contact-to-contact chord: a shaft
        advancing 25 :math:`\\mu\\mathrm{m}` per contact with a 40 :math:`\\mu\\mathrm{m}`
        lateral stagger has a pitch of 25, not :math:`\\sqrt{25^2 + 40^2}`.
    pitch_tolerance : float, default 0.1
        Allowable relative deviation from nominal pitch:
        :math:`|\\Delta d - d_{\\mathrm{nom}}| \\le \\epsilon \\cdot d_{\\mathrm{nom}}`.
        Must be non-negative.
    strict_linear : bool, default False
        If ``True``, raises :class:`ValueError` if the probe contacts do not conform to a
        linear geometry within tolerance.
    stagger_tolerance_um : float, default 100.0
        Maximum lateral extent, in micrometers (:math:`\\mu\\mathrm{m}`), that contacts may
        span perpendicular to the shaft axis while still counting as a single linear shaft.
        Standard staggered / zig-zag multi-column shafts sit well inside this bound; a
        planar grid or a scattered arrangement does not. Must be non-negative and finite.

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

    if stagger_tolerance_um < 0.0 or not np.isfinite(stagger_tolerance_um):
        raise ValueError(
            f"stagger_tolerance_um must be a non-negative finite float, got {stagger_tolerance_um}"
        )

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

    if coords is None or channel_ids is None:
        # This was `assert coords is not None` with no message, so a wrong type raised a
        # bare AssertionError('') -- and under `python -O` the assert vanished entirely and
        # the next line ran `coords.shape` on None.
        raise TypeError(
            f"probe_geometry: expected an NWB electrodes table, a pandas DataFrame, or an "
            f"(n_channels, 3) coordinate array; got {type(electrodes_table).__name__}."
        )

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
            stagger_um=0.0,
            is_staggered=False,
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

    # Pin the sign of the principal axis to electrode-table row order.
    #
    # A singular vector's sign is arbitrary -- `v` and `-v` describe the same axis -- and which
    # one LAPACK returns can change under a perturbation far below any physical tolerance. When
    # it changes, `linear_order` reverses end to end. Measured on the unrepaired module: a
    # straight 24-contact shaft at 100 um pitch with `z` scaled by `1 - 1e-9` reversed
    # `linear_order` from `[0..23]` to `[23..0]` and `orientation` from `[0, 0, 1]` to
    # `[0, 0, -1]`.
    #
    # The guard here used to read `if (sorted_proj[-1] - sorted_proj[0]) < 0:`. That branch was
    # unreachable: `sorted_proj = projections[np.argsort(projections)]` is ascending by
    # construction, so the difference is non-negative for every possible input. It could not
    # correct anything, and while it stood the returned ordering was whichever sign LAPACK
    # happened to produce.
    #
    # The informative comparison is against row order, not against the sorted projections.
    # `jnwb.laminar.vflip` documents `orientation` as being relative to channel indexing, so the
    # axis must advance with the electrode table.
    row_index = np.arange(n_channels, dtype=np.float64)
    row_covariance = float(
        np.dot(projections - projections.mean(), row_index - row_index.mean())
    )
    if row_covariance < 0.0:
        principal_dir = -principal_dir
    elif row_covariance == 0.0:
        # The axis is orthogonal to row order, so row order carries no direction to follow and
        # the arbitrary LAPACK sign would show through. Fall back to a convention that depends
        # only on the vector itself: its first non-zero component is positive.
        nonzero = np.flatnonzero(principal_dir)
        if nonzero.size and principal_dir[nonzero[0]] < 0.0:
            principal_dir = -principal_dir

    # Recomputed unconditionally rather than inside each branch: one dot product, and no path
    # can leave `projections` disagreeing with the `principal_dir` that is returned.
    projections = np.dot(centered, principal_dir)
    linear_order = np.argsort(projections)
    sorted_proj = projections[linear_order]
    sorted_coords = coords_um[linear_order]

    mean_pos = np.mean(coords_um, axis=0)

    # 6b. Refine the shaft axis so a lateral stagger cannot tilt it.
    # On a zig-zag shaft the alternating lateral offset is correlated with the contact
    # index, which pulls the raw principal component off the true shaft axis and leaks
    # part of the stagger into the measured advance. Averaging each half of the ordered
    # contacts cancels any repeating lateral pattern, leaving pure advance along the shaft.
    # This relies on the initial ordering already being by depth, which holds while the
    # lateral extent stays well under the axial span -- comfortably true for any stagger
    # inside stagger_tolerance_um, and the geometry is refused as non-linear before the
    # estimate would degrade.
    half = n_channels // 2
    if half >= 1:
        lo_centroid = np.mean(sorted_coords[:half], axis=0)
        hi_centroid = np.mean(sorted_coords[n_channels - half:], axis=0)
        delta = hi_centroid - lo_centroid
        delta_norm = float(np.linalg.norm(delta))
        if delta_norm > 0.0:
            principal_dir = delta / delta_norm
            projections = np.dot(coords_um - mean_pos, principal_dir)
            linear_order = np.argsort(projections)
            sorted_proj = projections[linear_order]
            sorted_coords = coords_um[linear_order]

    unit_orientation = principal_dir / np.linalg.norm(principal_dir)

    # Reconstructed positions along the linear axis: mean + proj * unit_orientation
    reconstructed = mean_pos + np.outer(projections, unit_orientation)
    lateral_offsets = coords_um - reconstructed
    residuals = np.linalg.norm(lateral_offsets, axis=1)
    max_residual = np.max(residuals)

    # Lateral extent: how wide the shaft is, measured across its dominant lateral
    # direction. A single-column shaft is 0; a staggered two-column shaft is the
    # column separation. This is a stagger, not a departure from linearity.
    _, _, lateral_vt = np.linalg.svd(lateral_offsets, full_matrices=False)
    stagger_um = float(np.ptp(np.dot(lateral_offsets, lateral_vt[0])))

    # Advance along the shaft axis between adjacent ordered contacts. Deliberately not
    # the 3D chord between contacts: on a staggered shaft the chord is the hypotenuse of
    # (axial step, lateral stagger) and would report the stagger as advance.
    axial_steps = np.diff(sorted_proj)
    axial_span = float(sorted_proj[-1] - sorted_proj[0])

    # Derived or explicit nominal pitch in micrometers
    if nominal_pitch is not None:
        nom_pitch_um = float(nominal_pitch) * scale
        if nom_pitch_um <= 0.0 or not np.isfinite(nom_pitch_um):
            raise ValueError(f"nominal_pitch must be positive and finite, got {nominal_pitch}")
    else:
        nom_pitch_um = float(np.median(axial_steps))

    # Linearity condition, in the sense the laminar path needs: contacts must sit at
    # distinct, monotonically advancing depths along one axis, and their lateral offset
    # must be a bounded stagger rather than open scatter. Collinearity is not required.
    mean_axial_step = axial_span / (n_channels - 1)
    if mean_axial_step > 0.0:
        advances_monotonically = bool(
            np.all(axial_steps >= _MIN_AXIAL_STEP_FRACTION * mean_axial_step)
        )
    else:
        advances_monotonically = False
    stagger_within_tolerance = bool(stagger_um <= stagger_tolerance_um)
    is_linear = bool(advances_monotonically and stagger_within_tolerance)

    if strict_linear and not is_linear:
        if not advances_monotonically:
            reason = (
                f"contacts do not advance monotonically along the shaft axis "
                f"(smallest axial step {float(np.min(axial_steps)):.3f} um against a mean of "
                f"{mean_axial_step:.3f} um)"
            )
        else:
            reason = (
                f"lateral extent {stagger_um:.3f} um exceeds stagger tolerance "
                f"{float(stagger_tolerance_um):.3f} um"
            )
        raise ValueError(f"Probe geometry is non-linear: {reason}")

    # A shaft is staggered when its lateral extent puts it outside collinearity.
    collinear_tol = max(pitch_tolerance * nom_pitch_um, 1e-4) if nom_pitch_um > 0 else 1e-4
    is_staggered = bool(stagger_um > collinear_tol)

    # Uniformity condition: axial steps within pitch_tolerance of nominal pitch
    pitch_err = np.abs(axial_steps - nom_pitch_um)
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
        stagger_um=stagger_um,
        is_staggered=is_staggered,
    )


