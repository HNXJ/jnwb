"""omission.jnwb_ext.canonical_identity -- deterministic identity gates (2026-08-29, Hamm).

WHY THIS MODULE EXISTS
    The same failure class has now been observed twice on this corpus, in two different
    namespaces, and in both cases a LOCAL COUNTER was silently used as a GLOBAL IDENTITY:

      trial_num   per-BLOCK trial counter. Deduplicating on (trial_num, condition) DELETED 63
                  real correct trials across 3 sessions, time-biased toward later trials by
                  keep="first".  -> trial-collision-forensics-20260829.json
      unit_id     per-PROBE kilosort cluster counter. In sub-V182o_ses-260702 it takes only 137
                  distinct values across 409 units (id 0 exists on all four probes, and for
                  probeA it is exactly equal to local_index). Joining template O+/O++ labels on
                  it MISLABELLED 6 units, changing their biological class and area.
                  -> bug-omission-identity-unit-id-column-vs-row-position-20260816.json

    Two independent occurrences meet this project's threshold for deterministic prevention
    rather than another agent instruction. Never infer identity semantics from a column name:
    verify uniqueness and scope before using any column as a join key.

CANONICAL KEYS

    trial   = (session_id, absolute trial onset)     realised as analog._trial_table's trial_id
    unit    = (session_id, unit_row_idx)             row position into OmissionSession._units_df
    channel = (session_id, probe, local_index)       equivalently (session_id, channel_id) where
                                                     channel_id is verified session-unique

    NWB's Units table is a DynamicTable whose row identity is positional; a project-specific
    kilosort cluster number that resets per probe is NOT the NWB unit identity. Likewise NWB
    represents electrodes as belonging to an ElectrodeGroup, so a bare channel index is not
    globally meaningful without its group.

FORBIDDEN JOIN KEYS
    Bare ``trial_num``, bare ``unit_id`` (probe-local kilosort column, unless ``probe`` is part
    of the key), and ambiguous ``trial_index``. ``forbid_identity_join`` raises on these.

USAGE
    Every intermediate SPK-LFP table should carry, at minimum:
        session_id, unit_row_idx, probe, raw_unit_id, area
    with ``unit_row_idx`` the join key and ``raw_unit_id`` explicitly named as LOCAL METADATA
    rather than identity.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Column names that are local counters, never global identities. Mapping: forbidden -> the
# canonical column that should be used instead.
FORBIDDEN_JOIN_KEYS: dict[str, str] = {
    "trial_num": "trial_id  (session, absolute onset)",
    "unit_id": "unit_row_idx  (session, row position into _units_df)",
    "trial_index": "trial_id  (session, absolute onset)",
}

# A probe-local column becomes admissible only when the probe is also part of the key.
PROBE_QUALIFIERS: frozenset[str] = frozenset({"probe", "group_name", "electrode_group"})

UNIT_IDENTITY_COLUMNS: tuple[str, ...] = (
    "session_id", "unit_row_idx", "probe", "raw_unit_id", "area",
)


def _as_key_list(on) -> list[str]:
    if on is None:
        return []
    return [on] if isinstance(on, str) else list(on)


def forbid_identity_join(on, *, context: str = "") -> None:
    """Raise if a join key set relies on a local counter as if it were a global identity.

    A probe-local column is permitted only when a probe qualifier is present in the same key,
    which is what makes the pair globally unique.
    """
    keys = _as_key_list(on)
    qualified = bool(PROBE_QUALIFIERS & set(keys))
    for key in keys:
        if key not in FORBIDDEN_JOIN_KEYS:
            continue
        if key == "unit_id" and qualified:
            continue  # (probe, unit_id) is a legitimate composite key
        where = f" in {context}" if context else ""
        raise ValueError(
            f"refusing to join on {key!r}{where}: it is a LOCAL COUNTER, not a session-unique "
            f"identity. Use {FORBIDDEN_JOIN_KEYS[key]} instead. See "
            f"omission.jnwb_ext.canonical_identity for why this gate exists."
        )


def assert_unique(frame: pd.DataFrame, key, *, what: str) -> None:
    """Assert ``key`` is one row per entity in ``frame``, reporting the actual collisions."""
    keys = _as_key_list(key)
    missing = [k for k in keys if k not in frame.columns]
    if missing:
        raise KeyError(f"{what}: missing identity column(s) {missing}; have {list(frame.columns)}")
    n_unique = len(frame.drop_duplicates(subset=keys))
    if n_unique != len(frame):
        dup = frame[frame.duplicated(subset=keys, keep=False)]
        example = dup[keys].head(5).to_dict("records")
        raise ValueError(
            f"{what}: {keys} is not unique -- {len(frame)} rows but {n_unique} distinct keys "
            f"({len(frame) - n_unique} collisions). Examples: {example}. A non-unique join key "
            f"fans out silently; refusing to proceed."
        )


def assert_unique_units(frame: pd.DataFrame) -> None:
    """(session_id, unit_row_idx) must identify exactly one unit."""
    assert_unique(frame, ["session_id", "unit_row_idx"], what="unit table")


def assert_unique_trials(frame: pd.DataFrame) -> None:
    """trial_id encodes (session, absolute onset) and must identify exactly one physical trial."""
    assert_unique(frame, ["trial_id"], what="trial table")


def assert_unique_channels(frame: pd.DataFrame) -> None:
    """(session, probe, local_index) must identify exactly one recording channel."""
    probe_col = next((c for c in ("probe", "group_name") if c in frame.columns), None)
    if probe_col is None:
        raise KeyError(
            "channel table: no probe/electrode-group column. A bare channel index is not "
            "globally meaningful; channel identity is (session, probe, local_index)."
        )
    session_col = "session_id" if "session_id" in frame.columns else "session"
    assert_unique(frame, [session_col, probe_col, "local_index"], what="channel table")


def attach_unit_identity(units_df: pd.DataFrame, session_id: str) -> pd.DataFrame:
    """Return ``units_df`` with the canonical unit identity columns attached.

    ``unit_row_idx`` is the POSITION of each row in the frame as given -- so this must be called
    on the unmodified ``OmissionSession._units_df``, before any filtering or sorting, or the row
    positions no longer correspond to the NWB Units table rows.

    The kilosort ``unit_id`` column is preserved as ``raw_unit_id`` and explicitly demoted to
    local metadata; it is not an identity.
    """
    out = units_df.reset_index(drop=True).copy()
    out["session_id"] = session_id
    out["unit_row_idx"] = np.arange(len(out), dtype=int)
    if "probe" not in out.columns:
        if "group_name" not in out.columns:
            raise KeyError(
                "units frame carries no probe/group_name column; cannot record which probe a "
                "probe-local unit_id belongs to."
            )
        out["probe"] = out["group_name"]
    if "unit_id" in out.columns:
        out["raw_unit_id"] = out["unit_id"]
    assert_unique_units(out)
    return out


def safe_merge(left: pd.DataFrame, right: pd.DataFrame, *, on, how: str = "inner",
               context: str = "", expect_one_to_one: bool = True) -> pd.DataFrame:
    """Merge with the identity gates applied: forbidden keys rejected, fan-out detected.

    ``expect_one_to_one`` asserts the key is unique on BOTH sides, which is what makes the row
    count of the result meaningful. Set it False only for a deliberate one-to-many join.
    """
    forbid_identity_join(on, context=context or "merge")
    keys = _as_key_list(on)
    what = context or "merge"
    if expect_one_to_one:
        assert_unique(left, keys, what=f"{what} (left)")
        assert_unique(right, keys, what=f"{what} (right)")
    merged = left.merge(right, on=keys, how=how)
    if expect_one_to_one and how == "inner":
        n_common = len(set(map(tuple, left[keys].to_numpy())) &
                       set(map(tuple, right[keys].to_numpy())))
        if len(merged) != n_common:
            raise ValueError(
                f"{what}: merge fanned out -- {len(merged)} rows from {n_common} common keys."
            )
    return merged
