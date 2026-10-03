"""
jnwb.metadata -- unit and electrode metadata extraction, QC classification, and census
reporting for NWB electrophysiology datasets.

Functions operate on standard NWB units/electrodes table columns (snr, firing_rate, quality,
peak_channel_id, ...) exposed by any file.
"""

import logging
import warnings
from pathlib import Path
from typing import Collection, Literal, Optional, List, Dict, Tuple, Union
import numpy as np
import pandas as pd
from jnwb.addressing import _STABLE_QUALITY_LABELS
from jnwb.nwb_io import nwb_read_io

log = logging.getLogger(__name__)

_NWB_READ_ERRORS = (OSError, ValueError, KeyError, TypeError, RuntimeError)


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


def get_all_units_metadata(
    nwb_paths: Union[str, Path, List[Union[str, Path]]],
    filter_quality: bool = False,
    quality_threshold: float = 1.0,
    on_read_error: Literal["skip", "raise"] = "skip",
    *,
    stable_labels: Collection[str] = _STABLE_QUALITY_LABELS,
) -> pd.DataFrame:
    """
    Extract all units and metadata from one or more NWB files.

    Args:
        nwb_paths: Single NWB path or list of paths
        filter_quality: If True, filter to units with quality >= quality_threshold, or,
            when a file's quality holds text labels, to units whose label is in
            ``stable_labels``.
        quality_threshold: numeric quality cut-off. The default 1.0 is a convention with no
            cited source: pass the cut-off your sorter's codes follow.
        on_read_error: ``"skip"`` logs and continues on per-file read failures (default);
            ``"raise"`` re-raises the first read/processing error.
        stable_labels: text quality labels read as stable, passed to
            :func:`jnwb.enrich_units_dataframe`, whose default convention it shares.

    Returns:
        DataFrame with all unit metadata across sessions
        Columns: unit_id, session_id, cluster_id, area, depth_class, quality, snr,
                 firing_rate, waveform_duration, is_stable, ...

        ``depth_class`` is the geometric class of
        :func:`jnwb.addressing.enrich_units_dataframe`, which is called with no depth unit,
        so it reads 'Unknown' unless the electrodes table declares one.

    Example:
        >>> units = get_all_units_metadata('/path/to/nwb')
        >>> stable_units = get_all_units_metadata('/path/to/nwbs', filter_quality=True, quality_threshold=1.0)
    """
    if isinstance(nwb_paths, (str, Path)):
        nwb_paths = [nwb_paths]

    nwb_paths = list(nwb_paths)
    _check_paths_exist(nwb_paths, "get_all_units_metadata")

    all_units = []
    n_failed = 0

    for nwb_path in nwb_paths:
        nwb_path = Path(nwb_path)
        session_id, raw_session = _session_id_from_path(nwb_path)

        try:
            with nwb_read_io(str(nwb_path), load_namespaces=True) as io:
                nwb = io.read()

                # Extract units
                if nwb.units is None:
                    log.warning(f"{raw_session}: No units found")
                    continue

                raw_units = nwb.units.to_dataframe().copy()
                elec_df = nwb.electrodes.to_dataframe().copy() if nwb.electrodes is not None else None

                from jnwb.addressing import enrich_units_dataframe
                units_df = enrich_units_dataframe(raw_units, elec_df,
                                                  stable_labels=stable_labels)
                units_df['session_id'] = session_id

                log.info(f"{session_id}: {len(units_df)} units extracted")

                if filter_quality:
                    q_num = pd.to_numeric(units_df['quality'], errors='coerce')
                    if q_num.notna().any():
                        units_df = units_df[q_num >= quality_threshold]
                    elif 'is_stable' in units_df.columns:
                        units_df = units_df[units_df['is_stable']]
                    else:
                        warnings.warn(
                            f"{session_id}: filter_quality=True, but the 'quality' column "
                            f"holds no usable value, so none of its {len(units_df)} units "
                            f"can pass the filter and all are excluded.",
                            RuntimeWarning,
                            stacklevel=2,
                        )
                        units_df = units_df.iloc[0:0]
                    log.info(f"  Filtered to {len(units_df)} units with quality >= {quality_threshold}")

                all_units.append(units_df)

        except _NWB_READ_ERRORS as e:
            log.error(f"{nwb_path.name}: {e}")
            if on_read_error == "raise":
                raise
            n_failed += 1
            continue

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

        A metric that cannot be compared is not a pass. A value that is missing or not a
        number (NaN, ``None``, a label such as ``'mua'``) is flagged ``'<metric> undefined'``,
        and a threshold whose column the frame lacks flags every unit ``'<metric> absent'``.
        Such a unit is 'Unknown' unless a measured ``quality`` or ``snr`` failure makes it
        'Poor', and its ``is_valid`` is False.

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
        is_undefined = np.isnan(values)
        with np.errstate(invalid='ignore'):
            fails = ~is_undefined & (values < thresh)
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
            emits a ``UserWarning``). An
            explicit column the frame lacks is dropped with a ``UserWarning``.

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
        if 'depth_class' not in units_df.columns and 'layer' in units_df.columns:
            warnings.warn(
                "unit_census_report: units_df has no 'depth_class' column, so the census is "
                "not split by depth. Its 'layer' column is not read. 'depth_class' comes "
                "from enrich_units_dataframe (get_all_units_metadata runs it); rebuild the "
                "frame with either, or pass group_by explicitly.",
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
        Dict with SNR statistics and pass rates

    Example:
        >>> snr_stats = get_snr_analysis(units_df, snr_threshold=1.0)
        >>> print(f"Units with SNR>=1.0: {snr_stats['pass_rate']:.1%}")
    """
    if 'snr' not in units_df.columns:
        log.warning("No SNR column found")
        return {}

    snr_vals = pd.to_numeric(units_df['snr'], errors='coerce').dropna()

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
            sess_snr = pd.to_numeric(
                units_df[units_df['session_id'] == session]['snr'],
                errors='coerce'
            ).dropna()
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

    Returns:
        Dict with total_units, units_with_spike_times, quality_distribution,
        snr_stats, firing_rate_stats (each a sub-dict of mean/median/std/... or
        ``{}`` when the source column is absent). A standard deviation of one value is
        NaN, not 0.0.

    Raises:
        TypeError: a ``spike_times`` entry is neither ``None`` nor a sequence (a NaN, for
            instance); the message names the unit.
    """
    result = {
        'total_units': len(units_df),
        'units_with_spike_times': 0,
        'quality_distribution': {},
        'snr_stats': {},
        'firing_rate_stats': {},
    }

    # Check spike times
    if 'spike_times' in units_df.columns:
        unit_ids = (units_df['unit_id'] if 'unit_id' in units_df.columns
                    else pd.Series(units_df.index, index=units_df.index))
        n_with = 0
        for unit, st in zip(unit_ids, units_df['spike_times']):
            if st is None:
                continue
            try:
                n_spikes = len(st)
            except TypeError:
                raise TypeError(
                    f"audit_units: unit {unit!r} has spike_times {st!r}, which is not a "
                    "sequence of spike times; use an empty array for a unit with no spikes."
                ) from None
            n_with += n_spikes > 0
        result['units_with_spike_times'] = int(n_with)

    # Quality distribution
    if 'quality' in units_df.columns:
        quality_values = pd.to_numeric(units_df['quality'], errors='coerce').dropna()
        if len(quality_values) > 0:
            result['quality_distribution'] = {
                'mean': float(quality_values.mean()),
                'median': float(quality_values.median()),
                'std': float(quality_values.std()),
                'min': float(quality_values.min()),
                'max': float(quality_values.max()),
                'good_count': int((quality_values >= quality_threshold).sum()),
            }
        else:
            good_count = int((units_df['quality'].astype(str).str.lower() == 'good').sum())
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
        snr_values = pd.to_numeric(units_df['snr'], errors='coerce').dropna()
        if len(snr_values) > 0:
            result['snr_stats'] = {
                'mean': float(snr_values.mean()),
                'median': float(snr_values.median()),
                'std': float(snr_values.std()),
                'good_count': int((snr_values >= snr_threshold).sum()),
                'good_rate': float((snr_values >= snr_threshold).mean())
            }

    # Firing rate statistics
    if 'firing_rate' in units_df.columns:
        fr_values = pd.to_numeric(units_df['firing_rate'], errors='coerce').dropna()
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
) -> pd.Series:
    """Tier units into 'mua' / 'stable' / 'unstable' from quality code, trial presence, and SNR.

    Three plain Series and two thresholds in; a tier Series out. Column names are not looked up
    internally -- callers pass Series explicitly.

    The quality rule is the one :func:`jnwb.enrich_units_dataframe` applies to the same
    codes: 1 is a single-unit candidate, 0 is not, and a missing quality is unknown. This
    function defines only the codes 0 and 1:

    - quality==0 -> 'mua'.
    - quality==1 & presence>presence_threshold & snr>snr_threshold -> 'stable'.
    - quality==1 & (presence<=presence_threshold or snr<=snr_threshold or either missing)
      -> 'unstable'.
    - any other quality -> 'unknown': a missing value, a code other than 0 or 1 (2, 0.5),
      or a label ('good', 'mua'). ``enrich_units_dataframe`` also reads a numeric quality
      above 1 and the labels it accepts as stable; this function does not guess what such a
      code means here.

    Args:
        quality: per-unit quality code Series (0 = MUA, 1 = single-unit candidate).
        trial_presence_fraction: per-unit fraction of trials the unit was present for.
        snr: per-unit signal-to-noise ratio.
        presence_threshold: minimum presence fraction (exclusive) for 'stable'.
        snr_threshold: minimum SNR (exclusive) for 'stable'. Both defaults, 0.98 and 0.5,
            are a convention with no cited source: pass the cut-offs your study justifies
            and state them wherever the tier is reported.

    Returns:
        Series of {'mua', 'stable', 'unstable', 'unknown'}, same index as ``quality``.
    """
    q = pd.to_numeric(quality, errors="coerce")
    presence = pd.to_numeric(trial_presence_fraction, errors="coerce")
    snr_num = pd.to_numeric(snr, errors="coerce")
    tier = pd.Series("unknown", index=quality.index, dtype=object)
    tier[q == 0] = "mua"
    stable_mask = (q == 1) & (presence > presence_threshold) & (snr_num > snr_threshold)
    tier[(q == 1) & ~stable_mask] = "unstable"
    tier[stable_mask] = "stable"
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
    ``unchanged_excluded``; a unit with no old row, or an old class that is missing, counts as
    not screened (``old_screened`` False) and as previously excluded. A new class that is
    missing (NaN, ``None``, ``pd.NA``) has no transition: it reads ``unknown``. A key that
    occurs twice in either frame raises ``ValueError``, because the merge would duplicate the
    unit with conflicting transitions.

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
    old_small = old_df[[old_s, old_u, class_col_old]].rename(
        columns={old_s: new_s, old_u: new_u, class_col_old: "_old_class"}
    )
    merged = new_df.merge(old_small, on=[new_s, new_u], how="left")
    merged["old_screened"] = merged["_old_class"].notna()
    old_class = merged["_old_class"].astype("boolean").fillna(False).astype(bool).tolist()
    new_defined = merged[class_col_new].notna().tolist()
    new_class = [bool(v) if d else False
                 for v, d in zip(merged[class_col_new], new_defined)]

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
        _transition(n, o, bool(s)) if d else "unknown"
        for n, o, s, d in zip(new_class, old_class, merged["old_screened"], new_defined)
    ]
    merged = merged.drop(columns=["_old_class"])
    return merged


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


