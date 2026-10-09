"""
jnwb.metadata -- unit and electrode metadata extraction, QC classification, and census
reporting for NWB electrophysiology datasets.

Functions operate on standard NWB units/electrodes table columns (snr, firing_rate, quality,
peak_channel_id, ...) exposed by any file.
"""

import datetime
import logging
import operator
import warnings
from pathlib import Path
from typing import Collection, Literal, Optional, List, Dict, Sequence, Tuple, Union
import numpy as np
import pandas as pd
from pynwb import NWBFile
from jnwb.addressing import (
    _STABLE_QUALITY_LABELS, _finite_cutoff, _passes_cutoff, _quality_is_stable,
    _refuse_repeated_columns, _stable_label_set,
)
from jnwb.nwb_io import WAIVED_REQUIREMENTS_ATTR, _normalise_allow_missing, nwb_read_io

log = logging.getLogger(__name__)

_NWB_READ_ERRORS = (OSError, ValueError, KeyError, TypeError, RuntimeError)

#: Values `assign_quality_tier` does not read as a quality code: a boolean is no code 0 or 1,
#: and a time is no code at all, though `pd.to_numeric` turns each into a number.
_NOT_A_QUALITY_CODE = (bool, np.bool_, datetime.date, datetime.timedelta, np.datetime64,
                       np.timedelta64)


def _session_id_from_path(nwb_path: Path):
    """Session id from the filename, as an int when it parses and the stem otherwise.

    `electrode_inventory` used to call `int(...)` on this unconditionally, so a perfectly
    readable file named `mm_depth.nwb` raised ValueError -- which the broad read-error
    tuple then swallowed as a failed read. `get_all_units_metadata` already had this
    fallback; both readers now share it.
    """
    raw = (
        nwb_path.stem.split("ses-")[1].split("_")[0]
        if "ses-" in nwb_path.stem
        else nwb_path.stem
    )
    try:
        return int(raw), raw
    except ValueError:
        return raw, raw


def _check_paths_exist(nwb_paths, caller: str) -> None:
    """A path that is not there is not an empty cohort.

    `on_read_error='skip'` plus a broad exception tuple made a nonexistent file, an
    unreadable file and a genuinely empty table indistinguishable: all three returned an
    empty DataFrame, reported only through `log.error`, which `warnings`, `pytest.warns`
    and `-W error` cannot see. `inspect`, `events` and `unit_spike_times` all raise
    `FileNotFoundError` on the same path, and these two readers now agree with them.
    """
    missing = [str(p) for p in nwb_paths if not Path(p).exists()]
    if missing:
        raise FileNotFoundError(
            f"{caller}: NWB file not found: {', '.join(missing)}"
        )


def _object_identity(nwb):
    """(input name, session_id, raw_session) for an already-open ``NWBFile``.

    A handle read from a file answers like the path form: its ``container_source``
    names that file while it exists, so the same file read by path or by handle
    carries the same session id. A handle with no file behind it is named by the
    file's own ``identifier``.
    """
    source = getattr(nwb, "container_source", None)
    if source:
        src = Path(str(source))
        if src.exists():
            return str(src), *_session_id_from_path(src)
    ident = getattr(nwb, "identifier", None)
    ident = str(ident) if ident else "NWBFile"
    return ident, ident, ident


def _note_waiver(waived_by_input, name, waived) -> None:
    """Record the waivers one input's read actually used, merged under its name."""
    for field in dict.fromkeys(waived):
        known = waived_by_input.setdefault(name, ())
        if field not in known:
            waived_by_input[name] = known + (field,)


def _extract_units_frame(nwb, *, session_id, raw_session, filter_quality,
                         quality_threshold, stable_threshold, stable_labels):
    """One input's enriched units frame, or ``None`` when it has no units table.

    Returns ``(frame_or_None, waived)``, where ``waived`` is what this object's read
    actually used. The quality-filter warning is raised one level above this helper,
    so it still points at the caller.
    """
    if nwb.units is None:
        log.warning(f"{raw_session}: No units found")
        return None, ()

    raw_units = nwb.units.to_dataframe().copy()
    elec_df = nwb.electrodes.to_dataframe().copy() if nwb.electrodes is not None else None

    from jnwb.addressing import enrich_units_dataframe
    units_df = enrich_units_dataframe(raw_units, elec_df,
                                      stable_threshold=stable_threshold,
                                      stable_labels=stable_labels)
    units_df['session_id'] = session_id

    log.info(f"{session_id}: {len(units_df)} units extracted")

    if filter_quality:
        has_quality = 'quality' in units_df.columns
        q_num = (pd.to_numeric(units_df['quality'], errors='coerce') if has_quality
                 else pd.Series(np.nan, index=units_df.index))
        if q_num.notna().any():
            # An infinite quality is no quality code, so it does not pass.
            finite = np.isfinite(q_num.astype(float))
            units_df = units_df[(q_num >= quality_threshold) & finite]
        elif 'is_stable' in units_df.columns:
            units_df = units_df[units_df['is_stable']]
        else:
            reason = ("the 'quality' column holds no usable value" if has_quality
                      else "the units table has no 'quality' column")
            warnings.warn(
                f"{session_id}: filter_quality=True, but {reason}, so none of "
                f"its {len(units_df)} units can pass the filter and all are "
                f"excluded.",
                RuntimeWarning,
                stacklevel=3,
            )
            units_df = units_df.iloc[0:0]
        log.info(f"  Filtered to {len(units_df)} units with quality >= {quality_threshold}")

    return units_df, tuple(getattr(nwb, WAIVED_REQUIREMENTS_ATTR, ()) or ())


def get_all_units_metadata(
    nwb_paths: Union[str, Path, NWBFile, List[Union[str, Path, NWBFile]]],
    filter_quality: bool = False,
    quality_threshold: float = 1.0,
    on_read_error: Literal["skip", "raise"] = "skip",
    *,
    stable_threshold: float = 1.0,
    stable_labels: Collection[str] = _STABLE_QUALITY_LABELS,
    allow_missing: Union[Sequence[str], str, None] = None,
) -> pd.DataFrame:
    """
    Extract all units and metadata from one or more NWB files.

    Args:
        nwb_paths: Single NWB path, open :class:`pynwb.NWBFile`, or list mixing
            both. An open handle is used as is and is not closed here; it must stay
            readable (its file open, or built in memory), since a closed file's
            tables cannot be read back.
        filter_quality: If True, filter to units with a finite quality >= quality_threshold,
            or, when a file's quality holds text labels, to units whose label is in
            ``stable_labels``.
        quality_threshold: numeric quality cut-off. The default 1.0 is a convention with no
            cited source: pass the cut-off your sorter's codes follow.
        on_read_error: ``"skip"`` logs and continues on per-file read failures (default);
            ``"raise"`` re-raises the first read/processing error.
        stable_threshold, stable_labels: the ``is_stable`` rule, passed to
            :func:`jnwb.enrich_units_dataframe`, whose default convention they share.
            ``quality_threshold`` decides the numeric filter and ``stable_threshold`` the
            ``is_stable`` column; a bare-string ``stable_labels`` raises ``TypeError``.
        allow_missing: required fields tolerated when opening path inputs, with
            :func:`jnwb.read_nwb`'s semantics -- today only ``"session_description"``,
            which then reads ``""``. Validated on every call, so an unknown field raises
            ``ValueError`` even when every input is an open handle, for which there is no
            file to open and the argument otherwise has no effect. A handle carries the
            waivers its own read used, and those are recorded below.

    Returns:
        DataFrame with all unit metadata across sessions
        Columns: unit_id, session_id, cluster_id, area, depth_class, quality, snr,
                 firing_rate, waveform_duration, is_stable, ...

        ``depth_class`` is the geometric class of
        :func:`jnwb.addressing.enrich_units_dataframe`, which is called with no depth unit,
        so it reads 'Unknown' unless the electrodes table declares one.

        The frame's ``attrs["jnwb_waived_requirements"]`` maps each input name (the path
        string, or the handle's source path or identifier) to the tuple of fields its read
        actually waived. The key is present only when at least one input waived something,
        so a default call reads exactly as before; a waived field and a genuinely empty
        one differ by this record alone, and no value is fabricated for either.

    Example:
        >>> units = get_all_units_metadata('/path/to/nwb')
        >>> stable_units = get_all_units_metadata('/path/to/nwbs', filter_quality=True, quality_threshold=1.0)
        >>> waived = get_all_units_metadata('incomplete.nwb', allow_missing=("session_description",))
        >>> waived.attrs["jnwb_waived_requirements"]
        {'incomplete.nwb': ('session_description',)}
    """
    _stable_label_set(stable_labels, "get_all_units_metadata")
    # Validated up front so a typo raises even when every input is an open handle,
    # for which there is no file to open.
    _normalise_allow_missing(allow_missing)
    if isinstance(nwb_paths, (str, Path, NWBFile)):
        nwb_paths = [nwb_paths]

    nwb_paths = list(nwb_paths)
    _check_paths_exist([p for p in nwb_paths if not isinstance(p, NWBFile)],
                       "get_all_units_metadata")

    all_units = []
    n_failed = 0
    waived_by_input: Dict[str, Tuple[str, ...]] = {}

    for item in nwb_paths:
        if isinstance(item, NWBFile):
            name, session_id, raw_session = _object_identity(item)
            try:
                units_df, waived = _extract_units_frame(
                    item, session_id=session_id, raw_session=raw_session,
                    filter_quality=filter_quality, quality_threshold=quality_threshold,
                    stable_threshold=stable_threshold, stable_labels=stable_labels)
            except _NWB_READ_ERRORS as e:
                log.error(f"{name}: {e}")
                if on_read_error == "raise":
                    raise
                n_failed += 1
                continue
            if units_df is None:
                continue
            _note_waiver(waived_by_input, name, waived)
            all_units.append(units_df)
            continue
        nwb_path = Path(item)
        session_id, raw_session = _session_id_from_path(nwb_path)

        try:
            with nwb_read_io(str(nwb_path), load_namespaces=True,
                             allow_missing=allow_missing) as io:
                units_df, waived = _extract_units_frame(
                    io.read(), session_id=session_id, raw_session=raw_session,
                    filter_quality=filter_quality, quality_threshold=quality_threshold,
                    stable_threshold=stable_threshold, stable_labels=stable_labels)
        except _NWB_READ_ERRORS as e:
            log.error(f"{nwb_path.name}: {e}")
            if on_read_error == "raise":
                raise
            n_failed += 1
            continue
        if units_df is None:
            continue
        _note_waiver(waived_by_input, str(nwb_path), waived)
        all_units.append(units_df)

    if not all_units:
        # Per-file skipping is the point of on_read_error='skip' in a multi-file call, but
        # when *nothing* was read there is no partial result to carry on with, and an empty
        # frame claims an empty cohort rather than a failed read.
        if n_failed:
            raise RuntimeError(
                f"get_all_units_metadata: all {n_failed} of {len(nwb_paths)} path(s) "
                "failed to read; no units were extracted. See the log for the per-file "
                "errors, or pass on_read_error='raise' to surface the first one."
            )
        log.warning("No units extracted from any files")
        return pd.DataFrame()

    result = pd.concat(all_units, ignore_index=True)
    log.info(f"Total: {len(result)} units across {len(nwb_paths)} sessions")
    if waived_by_input:
        # Visible in the result, and only when a read waived something: a default call
        # carries no such key, exactly as before. `pd.concat` drops `.attrs`, so this is
        # set on the returned frame rather than inherited.
        result.attrs["jnwb_waived_requirements"] = dict(waived_by_input)

    return result


def filter_by_criteria(
    df: pd.DataFrame,
    criteria: Dict,
    *,
    unknown: Literal["ignore", "raise"] = "ignore",
) -> pd.DataFrame:
    """
    Apply a criteria dict to a DataFrame (units, electrodes, or any other table).

    Generic pandas filtering on any table schema.

    Supports:
    - scalar equality  : {'area': 'V1'}
    - range tuple      : {'firing_rate': (10, 100)}
    - list membership  : {'area': ['V1', 'V4']}

    Parameters
    ----------
    unknown
        How to handle criteria keys absent from ``df`` columns. ``"ignore"`` (default)
        skips them so one criteria dict can be reused across schemas. ``"raise"`` fails
        on typos or stale column names.
    """
    if unknown == "raise":
        missing = [k for k in criteria if k not in df.columns]
        if missing:
            raise ValueError(
                f"filter_by_criteria: unknown column(s) {missing!r}; "
                "pass unknown='ignore' to skip absent keys"
            )

    out = df.copy()
    for k, v in criteria.items():
        if k not in out.columns:
            continue
        if isinstance(v, tuple) and len(v) == 2:
            col = pd.to_numeric(out[k], errors='coerce')
            out = out[(col >= v[0]) & (col <= v[1])]
        elif isinstance(v, (list, set)):
            out = out[out[k].isin(v)]
        else:
            out = out[out[k] == v]
    return out


def classify_unit_quality(
    units_df: pd.DataFrame,
    thresholds: Optional[Dict[str, float]] = None
) -> pd.DataFrame:
    """
    Classify units by quality based on metrics.

    Args:
        units_df: DataFrame with unit metrics (from get_all_units_metadata or NWB directly)
        thresholds: Dict of {'metric': threshold_value}; a unit is flagged when
                   ``metric < threshold_value``.
                   Default: {'quality': 1.0, 'snr': 1.0, 'firing_rate': 0.1}. These values,
                   and the rule that a ``quality`` or ``snr`` failure makes a unit 'Poor', are
                   a convention with no cited source: pass the cut-offs your study justifies.

    Returns:
        DataFrame with added classification columns:
        - quality_class: 'Good', 'Fair', 'Poor' or 'Unknown'
        - is_valid: bool (every threshold column present, defined and passed)
        - issue_flags: list of failed or undefined criteria

        A metric that cannot be compared is not a pass. A value that is missing, infinite or
        not a number (NaN, ``inf``, ``None``, a label such as ``'mua'``) is flagged
        ``'<metric> undefined'``,
        and a threshold whose column the frame lacks flags every unit ``'<metric> absent'``.
        Such a unit is 'Unknown' unless a measured ``quality`` or ``snr`` failure makes it
        'Poor', and its ``is_valid`` is False.

    Raises:
        ValueError: ``thresholds`` is empty, which would pass every unit as 'Good' with no
            criterion; a threshold is NaN, infinite or too large for a float, which passes or
            fails every unit alike; or a threshold's column occurs more than once in
            ``units_df``.
        TypeError: a threshold is ``None``, a boolean, or not a real number (a torch tensor,
            for instance). Any other real number is accepted, including a ``Fraction``, a
            ``Decimal`` and a 0-d numpy or JAX array.

    Example:
        >>> classified = classify_unit_quality(units_df)
        >>> good_units = classified[classified['is_valid']]
    """
    if thresholds is None:
        thresholds = {
            'quality': 1.0,
            'snr': 1.0,
            'firing_rate': 0.1
        }
    if len(thresholds) == 0:  # a dict or a Series; `not` is ambiguous for a Series
        raise ValueError(
            "classify_unit_quality: thresholds is empty, so every unit would pass as 'Good' "
            "with no criterion; pass at least one {'metric': cut-off}, or None for the defaults."
        )
    # Compared at the caller's exact value; the flag text shows it as given.
    cut_offs = {col: _finite_cutoff(thresh, f"thresholds[{col!r}]", "classify_unit_quality")
                for col, thresh in thresholds.items()}
    _refuse_repeated_columns(units_df, list(cut_offs), "classify_unit_quality")

    units_df = units_df.copy()
    flags = [[] for _ in range(len(units_df))]
    undefined = np.zeros(len(units_df), dtype=bool)
    critical_failure = np.zeros(len(units_df), dtype=bool)
    critical_cols = {'quality', 'snr'}

    for col, thresh in thresholds.items():
        if col not in units_df.columns:
            for row_flags in flags:
                row_flags.append(f'{col} absent')
            undefined[:] = True
            continue
        values = pd.to_numeric(units_df[col], errors='coerce').to_numpy(dtype=float)
        is_undefined = ~np.isfinite(values)  # an infinite measure is undefined, as NaN is
        fails = ~is_undefined & _passes_cutoff(values, cut_offs[col], operator.lt)
        for i in np.flatnonzero(is_undefined):
            flags[i].append(f'{col} undefined')
        for i in np.flatnonzero(fails):
            flags[i].append(f'{col}<{thresh}')
        undefined |= is_undefined
        if col in critical_cols:
            critical_failure |= fails

    units_df['issue_flags'] = pd.Series(flags, index=units_df.index, dtype=object)
    has_flag = np.array([len(f) > 0 for f in flags], dtype=bool)
    quality_class = np.where(has_flag, 'Fair', 'Good').astype(object)
    quality_class[undefined] = 'Unknown'
    quality_class[critical_failure] = 'Poor'
    units_df['quality_class'] = quality_class
    units_df['is_valid'] = ~has_flag

    return units_df


def unit_census_report(
    units_df: pd.DataFrame,
    group_by: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Generate a census/summary report of units grouped by session, area and depth class.

    Args:
        units_df: DataFrame from get_all_units_metadata
        group_by: Columns to group by (default: ['session_id', 'area', 'depth_class'],
            the geometric depth class from ``enrich_units_dataframe``; a ``layer`` column is
            not read, and a default call on a frame that has ``layer`` but no ``depth_class``
            emits a ``UserWarning``). A column the frame lacks, default or explicit, is
            dropped with a ``UserWarning``.

    Returns:
        Summary DataFrame with counts and statistics

    Example:
        >>> census = unit_census_report(all_units)
        >>> by_area = unit_census_report(all_units, group_by=['area'])
    """
    if group_by is not None:
        absent = [col for col in group_by if col not in units_df.columns]
        if absent:
            warnings.warn(
                f"unit_census_report: group_by names {absent}, which units_df does not "
                "have; the census is grouped by the remaining columns only.",
                UserWarning,
                stacklevel=2,
            )
    else:
        group_by = ['session_id', 'area', 'depth_class']
        absent = [col for col in group_by if col not in units_df.columns]
        if 'depth_class' in absent and 'layer' in units_df.columns:
            absent.remove('depth_class')
            warnings.warn(
                "unit_census_report: units_df has no 'depth_class' column, so the census is "
                "not split by depth. Its 'layer' column is not read. 'depth_class' comes "
                "from enrich_units_dataframe (get_all_units_metadata runs it); rebuild the "
                "frame with either, or pass group_by explicitly.",
                UserWarning,
                stacklevel=2,
            )
        if absent:
            warnings.warn(
                f"unit_census_report: units_df has no {absent} column, so the default census "
                "is not split by it; the census is grouped by the remaining default columns "
                "only. Pass group_by explicitly to choose the grouping.",
                UserWarning,
                stacklevel=2,
            )

    # Filter to available columns
    group_by = [col for col in group_by if col in units_df.columns]

    if not group_by:
        return units_df.describe()

    # Count column: enrich_units_dataframe (run by get_all_units_metadata) always
    # renames the raw NWB 'cluster_id' column to 'unit_id', so 'cluster_id' is
    # never present on the DataFrame this function actually receives.
    count_col = 'unit_id' if 'unit_id' in units_df.columns else 'cluster_id'

    census = units_df.groupby(group_by, dropna=False).agg({
        count_col: 'count',
        'firing_rate': ['mean', 'median', 'std'],
        'waveform_duration': ['mean', 'median'],
        'snr': ['mean', 'median']
    }).round(2)

    census.columns = ['_'.join(col).strip() for col in census.columns.values]
    census = census.rename(columns={f'{count_col}_count': 'n_units'})

    return census.reset_index()


def get_snr_analysis(
    units_df: pd.DataFrame,
    snr_threshold: float = 1.0,
    detail: bool = False
) -> Dict:
    """
    Analyze SNR distribution and quality.

    Args:
        units_df: DataFrame with SNR values
        snr_threshold: Cut-off for 'good' SNR; a unit passes when ``snr >= snr_threshold``.
            The default 1.0 is a convention with no cited source: pass the cut-off your
            study justifies.
        detail: If True, return per-session breakdown

    Returns:
        Dict with SNR statistics and pass rates over the units whose SNR is a finite number;
        a missing, non-numeric or infinite SNR is undefined and left out of every entry.

    Raises:
        ValueError: ``snr``, or with ``detail=True`` ``session_id``, occurs more than once in
            ``units_df``.

    Example:
        >>> snr_stats = get_snr_analysis(units_df, snr_threshold=1.0)
        >>> print(f"Units with SNR>=1.0: {snr_stats['pass_rate']:.1%}")
    """
    _refuse_repeated_columns(units_df, ("snr", "session_id") if detail else ("snr",),
                             "get_snr_analysis")
    if 'snr' not in units_df.columns:
        log.warning("No SNR column found")
        return {}

    snr_vals = _finite_measure(units_df['snr'])

    result = {
        'n_units_with_snr': len(snr_vals),
        'snr_mean': snr_vals.mean(),
        'snr_median': snr_vals.median(),
        'snr_std': snr_vals.std(),
        'snr_min': snr_vals.min(),
        'snr_max': snr_vals.max(),
        'pass_count': (snr_vals >= snr_threshold).sum(),
        'pass_rate': (snr_vals >= snr_threshold).mean()
    }

    if detail and 'session_id' in units_df.columns:
        result['by_session'] = {}
        for session in units_df['session_id'].unique():
            sess_snr = _finite_measure(units_df[units_df['session_id'] == session]['snr'])
            result['by_session'][session] = {
                'n': len(sess_snr),
                'mean': sess_snr.mean(),
                'pass_rate': (sess_snr >= snr_threshold).mean()
            }

    return result


def electrode_inventory(
    nwb_paths: Union[str, Path, List[Union[str, Path]]],
    on_read_error: Literal["skip", "raise"] = "skip",
) -> pd.DataFrame:
    """
    Build inventory of electrodes, mapping to units and areas.

    Args:
        nwb_paths: Single or list of NWB file paths
        on_read_error: ``"skip"`` logs and continues on per-file read failures (default);
            ``"raise"`` re-raises the first read/processing error.

    Returns:
        DataFrame with electrode metadata and unit assignments

    Example:
        >>> inv = electrode_inventory('/path/to/nwbs')
        >>> fef_channels = inv[inv['area'] == 'FEF']
    """
    if isinstance(nwb_paths, (str, Path)):
        nwb_paths = [nwb_paths]

    nwb_paths = list(nwb_paths)
    _check_paths_exist(nwb_paths, "electrode_inventory")

    all_elecs = []
    n_failed = 0

    for nwb_path in nwb_paths:
        nwb_path = Path(nwb_path)
        session_id, _raw_session = _session_id_from_path(nwb_path)

        try:
            with nwb_read_io(str(nwb_path), load_namespaces=True) as io:
                nwb = io.read()

                if nwb.electrodes is None:
                    continue

                elec_df = nwb.electrodes.to_dataframe().copy()
                elec_df['session_id'] = session_id
                elec_df['elec_id'] = elec_df.index

                # Add unit assignment info
                if nwb.units is not None:
                    units_df = nwb.units.to_dataframe()
                    if 'peak_channel_id' in units_df.columns:
                        # Count units per channel
                        unit_counts = units_df['peak_channel_id'].value_counts()
                        elec_df['n_units_on_channel'] = elec_df.index.map(
                            lambda x: unit_counts.get(float(x), 0)
                        )
                    else:
                        elec_df['n_units_on_channel'] = 0
                else:
                    elec_df['n_units_on_channel'] = 0

                all_elecs.append(elec_df)

        except _NWB_READ_ERRORS as e:
            log.error(f"{nwb_path.name}: {e}")
            if on_read_error == "raise":
                raise
            n_failed += 1
            continue

    if not all_elecs:
        if n_failed:
            raise RuntimeError(
                f"electrode_inventory: all {n_failed} of {len(nwb_paths)} path(s) failed "
                "to read; no electrodes were extracted. See the log for the per-file "
                "errors, or pass on_read_error='raise' to surface the first one."
            )
        log.warning("No electrode data extracted")
        return pd.DataFrame()

    return pd.concat(all_elecs, ignore_index=False)


def audit_units(
    units_df: pd.DataFrame,
    *,
    quality_threshold: float = 1.0,
    snr_threshold: float = 1.0,
    stable_labels: Collection[str] = ("good",),
) -> Dict:
    """
    Audit unit quality and completeness: spike-time coverage, and quality/SNR/firing-rate
    summary statistics.

    Operates on standard NWB units-table columns (spike_times, quality, snr, firing_rate).

    Args:
        units_df: units DataFrame, e.g. from :func:`get_all_units_metadata`.
        quality_threshold: a numeric quality counts toward ``good_count`` when
            ``quality >= quality_threshold``.
        snr_threshold: an SNR counts toward ``good_count`` and ``good_rate`` when
            ``snr >= snr_threshold``. Both defaults, 1.0, are a convention with no cited
            source: pass the cut-offs your study justifies.
        stable_labels: when no quality is numeric, a text label counts toward
            ``good_count`` when, lower-cased, it is one of these. Unlike
            :func:`jnwb.enrich_units_dataframe`, the label is not stripped of whitespace
            (``' good'`` does not count), as this count has always read it, and the default
            is ``("good",)``, narrower than enrich's
            ``("good", "sua", "single", "stable", "clean")``. A bare string raises
            ``TypeError`` and an empty collection ``ValueError``.

    Returns:
        Dict with total_units, units_with_spike_times, quality_distribution,
        snr_stats, firing_rate_stats (each a sub-dict of mean/median/std/... or
        ``{}`` when the source column is absent). A missing, non-numeric or infinite
        quality, SNR or firing rate is undefined and left out of every statistic and count;
        a quality column whose numbers are all infinite reports NaN statistics and a
        ``good_count`` of 0. A standard deviation of one value is
        NaN, not 0.0, and a text-only quality column gives NaN for its mean, median, std, min
        and max. The dict can therefore hold the float NaN, which ``json.dumps`` writes as
        the bare token ``NaN``: valid Python and JavaScript, but not strict JSON. Serialize
        with ``json.dumps(..., allow_nan=False)`` to catch it, or map NaN to ``None`` first.

    Raises:
        TypeError: a ``spike_times`` entry is neither ``None`` nor a sequence (a NaN, for
            instance), the message naming the unit; or a cut-off is ``None`` or not a number.
        ValueError: ``quality_threshold`` or ``snr_threshold`` is NaN or infinite, which
            would count every unit or none, or a column this function reads occurs more than
            once (``spike_times``, ``quality``, ``snr`` or ``firing_rate``).
    """
    labels = _stable_label_set(stable_labels, "audit_units")
    _refuse_repeated_columns(units_df, ["spike_times", "quality", "snr", "firing_rate"],
                             "audit_units")
    quality_threshold = _finite_cutoff(quality_threshold, "quality_threshold", "audit_units")
    snr_threshold = _finite_cutoff(snr_threshold, "snr_threshold", "audit_units")
    result = {
        'total_units': len(units_df),
        'units_with_spike_times': 0,
        'quality_distribution': {},
        'snr_stats': {},
        'firing_rate_stats': {},
    }

    # Check spike times
    if 'spike_times' in units_df.columns:
        # unit_id only names a unit in the message below; a repeated unit_id column, which
        # 0.2.8 never read, names it by its index label instead of being refused.
        by_unit_id = (units_df.columns == 'unit_id').sum() == 1
        unit_ids = (units_df['unit_id'] if by_unit_id
                    else pd.Series(units_df.index, index=units_df.index))
        n_with = 0
        for unit, st in zip(unit_ids, units_df['spike_times']):
            if st is None:
                continue
            try:
                n_spikes = len(st)
            except TypeError:
                named = (f"unit {unit!r}" if by_unit_id
                         else f"the unit at index label {unit!r} (no single unit_id column)")
                raise TypeError(
                    f"audit_units: {named} has spike_times {st!r}, which is not a "
                    "sequence of spike times; use an empty array for a unit with no spikes."
                ) from None
            n_with += n_spikes > 0
        result['units_with_spike_times'] = int(n_with)

    # Quality distribution
    if 'quality' in units_df.columns:
        is_numeric = pd.to_numeric(units_df['quality'], errors='coerce').notna().any()
        quality_values = _finite_measure(units_df['quality'])
        if is_numeric:
            result['quality_distribution'] = {
                'mean': float(quality_values.mean()),
                'median': float(quality_values.median()),
                'std': float(quality_values.std()),
                'min': float(quality_values.min()),
                'max': float(quality_values.max()),
                'good_count': int(_passes_cutoff(quality_values, quality_threshold,
                                                 operator.ge).sum()),
            }
        else:
            # The released matching: lower-cased, not stripped, so ' good' is not 'good'.
            good_count = int(units_df['quality'].astype(str).str.lower().isin(labels).sum())
            result['quality_distribution'] = {
                'mean': float('nan'),
                'median': float('nan'),
                'std': float('nan'),
                'min': float('nan'),
                'max': float('nan'),
                'good_count': good_count,
            }

    # SNR statistics
    if 'snr' in units_df.columns:
        snr_values = _finite_measure(units_df['snr'])
        if len(snr_values) > 0:
            result['snr_stats'] = {
                'mean': float(snr_values.mean()),
                'median': float(snr_values.median()),
                'std': float(snr_values.std()),
                'good_count': int(_passes_cutoff(snr_values, snr_threshold,
                                                 operator.ge).sum()),
                'good_rate': float(_passes_cutoff(snr_values, snr_threshold,
                                                  operator.ge).mean())
            }

    # Firing rate statistics
    if 'firing_rate' in units_df.columns:
        fr_values = _finite_measure(units_df['firing_rate'])
        if len(fr_values) > 0:
            result['firing_rate_stats'] = {
                'mean': float(fr_values.mean()),
                'median': float(fr_values.median()),
                'min': float(fr_values.min()),
                'max': float(fr_values.max()),
            }

    return result


def audit_electrodes(elec_df: pd.DataFrame, units_df: Optional[pd.DataFrame] = None) -> Dict:
    """
    Audit electrode configuration and unit-to-electrode mapping coverage.

    Operates on electrodes-table ``location`` and units-table ``peak_channel_id`` when present.

    Args:
        elec_df: electrodes DataFrame.
        units_df: optional units DataFrame, to compute unit-assignment coverage.

    Returns:
        Dict with total_electrodes, areas_represented, units_assigned, assignment_rate.
    """
    result = {
        'total_electrodes': len(elec_df),
        'areas_represented': {},
        'units_assigned': 0,
    }

    # Area representation
    if 'location' in elec_df.columns:
        areas = elec_df['location'].apply(lambda x: str(x).split(',')[0].strip() if pd.notna(x) else 'Unknown')
        area_counts = areas.value_counts()
        result['areas_represented'] = area_counts.to_dict()

    # Unit assignments
    if units_df is not None and 'peak_channel_id' in units_df.columns:
        assigned = units_df['peak_channel_id'].notna().sum()
        result['units_assigned'] = int(assigned)
        result['assignment_rate'] = float(assigned / len(units_df))
    else:
        result['units_assigned'] = 0
        result['assignment_rate'] = 0.0

    return result


def assign_quality_tier(
    quality: pd.Series,
    trial_presence_fraction: pd.Series,
    snr: pd.Series,
    presence_threshold: float = 0.98,
    snr_threshold: float = 0.5,
    *,
    stable_threshold: float = 1.0,
    stable_labels: Collection[str] = _STABLE_QUALITY_LABELS,
) -> pd.Series:
    """Tier units 'mua' / 'stable' / 'unstable' / 'unknown' from quality, presence and SNR.

    Three plain Series and the thresholds in; a tier Series out. Column names are not looked up
    internally -- callers pass Series explicitly.

    The quality rule is :func:`jnwb.enrich_units_dataframe`'s ``is_stable`` rule, computed by
    the same code with the same defaults: when any quality is numeric, a unit is a single-unit
    candidate when ``quality >= stable_threshold``; otherwise when its label, stripped and
    lower-cased, is one of ``stable_labels``.

    - candidate & presence>presence_threshold & snr>snr_threshold -> 'stable'.
    - candidate & (presence<=presence_threshold or snr<=snr_threshold or either missing)
      -> 'unstable'. A presence or SNR that is not a number or is infinite counts as missing.
    - not a candidate and declared multi-unit -- the code 0, or the label 'mua' after
      stripping and lower-casing -> 'mua'.
    - every other unit -> 'unknown': a missing quality, a value that is not a number in a
      numeric column, any other non-candidate code (-1, 0.5) and any other label ('noise',
      'unsorted'). Not being a single unit does not make a unit multi-unit activity.
    - a boolean quality (``False`` is not the code 0, ``True`` not the code 1), a date,
      datetime or timedelta, or an infinite value, is no quality code -> 'unknown'.

    Args:
        quality: per-unit quality Series: codes (0 = MUA, 1 = single-unit candidate) or labels.
        trial_presence_fraction: per-unit fraction of trials the unit was present for.
        snr: per-unit signal-to-noise ratio. Each of the two is a Series or an array of
            ``len(quality)`` values. A Series is aligned to ``quality`` by unit label, in any
            order, and may carry labels ``quality`` lacks, which are ignored, as when it was
            computed on the full units table and ``quality`` is a filtered subset; a label of
            ``quality`` missing from it, or a repeated label, raises ``ValueError``. Extra
            labels also raise ``ValueError`` when ``quality`` has the index ``0..n-1``,
            which pandas gives a filter followed by ``reset_index``, ``head()``
            and ``iloc[:k]`` alike; those labels may be positions rather than unit labels, so
            aligning could pair the wrong units. Pass presence and SNR selected the same way
            as ``quality``. An array
            is read by position; a scalar raises ``ValueError``, and so does a numpy masked
            array with a masked entry, whose mask would otherwise be dropped and the masked
            value read: fill it (``values.filled(np.nan)`` reads as missing) or unmask it.
        presence_threshold: minimum presence fraction (exclusive) for 'stable'.
        snr_threshold: minimum SNR (exclusive) for 'stable'. Both defaults, 0.98 and 0.5,
            are a convention with no cited source: pass the cut-offs your study justifies
            and state them wherever the tier is reported.
        stable_threshold, stable_labels: the candidate rule above; their defaults, 1.0 and
            ``("good", "sua", "single", "stable", "clean")``, are a convention with no cited
            source. A bare-string ``stable_labels`` raises ``TypeError`` and an empty one
            ``ValueError``. Each of the three cut-offs raises ``ValueError`` when NaN or
            infinite and ``TypeError`` when ``None``, a boolean or not a real number.

    Returns:
        Series of {'mua', 'stable', 'unstable', 'unknown'}, same index as ``quality``.
    """
    labels = _stable_label_set(stable_labels, "assign_quality_tier")
    stable_threshold = _finite_cutoff(stable_threshold, "stable_threshold", "assign_quality_tier")
    presence_threshold = _finite_cutoff(presence_threshold, "presence_threshold",
                                        "assign_quality_tier")
    snr_threshold = _finite_cutoff(snr_threshold, "snr_threshold", "assign_quality_tier")
    # A boolean, date or duration is no quality code: False is not the code 0. Iterating a
    # bool, boolean, datetime64 or timedelta64 Series yields these types, so one check covers
    # each dtype and an object column alike.
    not_a_code = np.array([isinstance(v, _NOT_A_QUALITY_CODE) for v in quality], dtype=bool)
    candidate = _quality_is_stable(quality, stable_threshold, labels)
    known = candidate.notna().to_numpy() & ~not_a_code
    is_candidate = candidate.fillna(False).to_numpy(dtype=bool) & ~not_a_code
    declared_mua = ((pd.to_numeric(quality, errors="coerce") == 0).fillna(False)
                    | (quality.astype(str).str.strip().str.lower() == "mua")
                    ).to_numpy(dtype=bool) & ~not_a_code

    def _aligned(values, name):
        if isinstance(values, pd.Series):
            if not values.index.equals(quality.index):
                missing = quality.index.difference(values.index)
                duplicated = values.index[values.index.duplicated()].unique()
                if len(missing) or len(duplicated) or not quality.index.is_unique:
                    raise ValueError(
                        f"assign_quality_tier: {name} is not on the units of quality: "
                        f"missing {list(missing[:5])}, duplicated {list(duplicated[:5])}"
                        + ("" if quality.index.is_unique else "; quality's index repeats")
                        + ". Pass Series covering the unit labels of quality, or arrays read "
                        "by position."
                    )
                extra = values.index.difference(quality.index)
                if len(extra) and _is_default_range_index(quality.index):
                    # Positions 0..n-1 may not be unit labels, so aligning a full-table
                    # Series to them can pair the wrong units.
                    raise ValueError(
                        f"assign_quality_tier: {name} has labels quality lacks "
                        f"({list(extra[:5])}) and quality has the index 0..n-1, "
                        "which pandas gives a filter followed by reset_index, head() and "
                        "iloc[:k] alike; those labels may be positions rather than unit "
                        "labels, so aligning could pair the wrong units. Pass presence and SNR "
                        "selected the same way as quality."
                    )
                # Same labels in another order, or a superset: labels quality lacks drop out.
                values = values.reindex(quality.index)
            values = values.to_numpy()
        if np.ma.isMaskedArray(values) and np.ma.getmaskarray(values).any():
            raise ValueError(
                f"assign_quality_tier: {name} is a masked array with masked entries, whose "
                "mask np.asarray would drop; pass values.filled(np.nan) to read them as "
                "missing, or an unmasked array."
            )
        values = np.asarray(values)
        if values.shape != (len(quality),):
            raise ValueError(
                f"assign_quality_tier: {name} has shape {values.shape}, quality has "
                f"{len(quality)} units."
            )
        out = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
        # An infinite presence or SNR is undefined, as NaN is; np.where never writes in place.
        return np.where(np.isinf(out), np.nan, out)

    presence = _aligned(trial_presence_fraction, "trial_presence_fraction")
    snr_num = _aligned(snr, "snr")
    passes = (_passes_cutoff(presence, presence_threshold, operator.gt)
              & _passes_cutoff(snr_num, snr_threshold, operator.gt))
    tier = pd.Series("unknown", index=quality.index, dtype=object)
    tier[known & ~is_candidate & declared_mua] = "mua"
    tier[is_candidate & ~passes] = "unstable"
    tier[is_candidate & passes] = "stable"
    return tier


def compare_old_new_criteria(
    new_df: pd.DataFrame,
    old_df: pd.DataFrame,
    class_col_new: str,
    class_col_old: str,
    new_key: Tuple[str, str],
    old_key: Tuple[str, str],
) -> pd.DataFrame:
    """Diff two boolean unit-classification columns across two DataFrames on a join key.

    Retained in metadata.py for module-level compatibility with downstream unit inclusion
    curation pipelines. Not exported in top-level jnwb namespace.

    ``transition`` is ``gained``, ``lost``, ``unchanged_included`` or
    ``unchanged_excluded``; a unit with no old row counts as not screened (``old_screened``
    False) and as previously excluded. A class that is missing (NaN, ``None``, ``pd.NA``) on
    either side has no transition: it reads ``unknown``, and an old row whose class is missing
    has ``old_screened`` False. A class value is ``True``, ``False``, or the number 1 or 0;
    anything else, such as the strings ``"False"`` or ``"no"`` (which ``bool`` reads as true)
    or the number 2, raises ``ValueError`` naming the column and the value. A key that
    occurs twice in either frame raises ``ValueError``, because the merge would duplicate the
    unit with conflicting transitions, and so does a ``new_df`` column named ``old_screened``
    or ``transition``, which the output would overwrite.

    INTENTIONAL BREAK. ``class_col_new`` and ``class_col_old`` are required and precede
    the key arguments. When this function was promoted into the package they had study-
    specific defaults, which named one corpus's columns and do not belong in a neutral
    library; removing them made an existing two-positional call raise
    ``TypeError: missing 2 required positional arguments``. Name the two columns
    explicitly.

    INTENTIONAL BREAK. ``new_key`` and ``old_key`` are required. Their defaults,
    ``("session", "unit_row")`` and ``("session_prefix", "unit_row_idx")``, named one
    downstream corpus's columns; a call that relied on them raises ``TypeError`` and now
    passes those two tuples explicitly.
    """
    new_s, new_u = new_key
    old_s, old_u = old_key
    for frame, cols, name in ((new_df, [new_s, new_u], "new_df"),
                              (old_df, [old_s, old_u], "old_df")):
        duplicated = frame.duplicated(subset=cols, keep=False)
        if duplicated.any():
            keys = frame.loc[duplicated, cols].drop_duplicates().to_records(index=False).tolist()
            raise ValueError(
                f"compare_old_new_criteria: {name} has more than one row for key {cols} "
                f"{keys}; each unit must occur once on each side."
            )
    taken_outputs = [col for col in ("old_screened", "transition") if col in new_df.columns]
    if taken_outputs:
        raise ValueError(
            f"compare_old_new_criteria: new_df already has column(s) {taken_outputs}, which "
            "this function writes; rename or drop them first, for instance when comparing a "
            "frame this function returned."
        )
    # The two working columns get names no column of new_df has, so they never collide with
    # or overwrite a caller's column.
    taken = set(new_df.columns) | {new_s, new_u}
    old_class_col, indicator = "_old_class", "_old_row"
    while old_class_col in taken:
        old_class_col += "_"
    taken.add(old_class_col)
    while indicator in taken:
        indicator += "_"
    old_small = old_df[[old_s, old_u, class_col_old]].rename(
        columns={old_s: new_s, old_u: new_u, class_col_old: old_class_col}
    )
    merged = new_df.merge(old_small, on=[new_s, new_u], how="left", indicator=indicator)
    has_old_row = (merged[indicator] == "both").tolist()
    merged["old_screened"] = merged[old_class_col].notna()
    new_class = [_boolean_class(v, class_col_new, "new_df") for v in merged[class_col_new]]
    old_class = [_boolean_class(v, class_col_old, "old_df") for v in merged[old_class_col]]
    new_defined = [v is not None for v in new_class]
    # An old row whose class is missing is undefined, not "not screened".
    old_defined = [c is not None or not row for c, row in zip(old_class, has_old_row)]
    new_class = [bool(v) for v in new_class]
    old_class = [bool(v) for v in old_class]

    def _transition(row_new: bool, row_old: bool, screened: bool) -> str:
        if not screened:
            return "gained" if row_new else "unchanged_excluded"
        if row_new and not row_old:
            return "gained"
        if row_old and not row_new:
            return "lost"
        if row_new and row_old:
            return "unchanged_included"
        return "unchanged_excluded"

    merged["transition"] = [
        _transition(n, o, bool(s)) if d and od else "unknown"
        for n, o, s, d, od in zip(new_class, old_class, merged["old_screened"], new_defined,
                                  old_defined)
    ]
    merged = merged.drop(columns=[old_class_col, indicator])
    return merged


def _finite_measure(column: pd.Series) -> pd.Series:
    """The numeric values of a measure column, without the missing, non-numeric and infinite
    ones: an infinite SNR, firing rate or quality is undefined, as a NaN is."""
    values = pd.to_numeric(column, errors='coerce').dropna()
    return values[np.isfinite(values.to_numpy(dtype=float))]


def _is_default_range_index(index: pd.Index) -> bool:
    """The index pandas gives a frame with no labels of its own: ``RangeIndex(0, n, 1)``."""
    return isinstance(index, pd.RangeIndex) and index.start == 0 and index.step == 1


def _boolean_class(value, column: str, frame: str):
    """One inclusion class as True, False or None (missing). Only a boolean or the number 1 or
    0 is a class: ``bool("False")`` is True, so a string or another number is refused."""
    if value is None or value is pd.NA or (isinstance(value, (float, np.floating))
                                           and np.isnan(value)):
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, float, np.integer, np.floating)) and value in (0, 1):
        return bool(value)
    raise ValueError(
        f"compare_old_new_criteria: {frame} column {column!r} holds {value!r}, which is not a "
        "boolean class; use True, False, 1 or 0, and NaN or None for a missing class."
    )


def old_new_summary_table(
    compared: pd.DataFrame,
    group_cols: Tuple[str, ...] = ("area", "quality_tier"),
) -> pd.DataFrame:
    """Explicit gained/lost/unchanged counts per class per grouping column.

    Retained in metadata.py for module-level compatibility with downstream unit inclusion
    curation pipelines. Not exported in top-level jnwb namespace.
    """
    cols = list(group_cols) + ["transition"]
    summary = compared.groupby(cols).size().reset_index(name="n_units")
    return summary


