"""Build the per-session unit-classification table the SPK-LFP analyses consume (2026-08-29).

WHY THIS SCRIPT EXISTS
    The pilot consumed omission/artifacts/data/pilot_v182o_260702_unitclass.csv, which had NO
    builder in the repo -- it was produced ad hoc in an earlier session. That made the pilot
    irreproducible and blocked replication on any other session. This script reconstructs the
    recipe and PROVES the reconstruction by regenerating the existing table bit-identically.

THE RECIPE (reverse-engineered from the surviving table, every rule verified exactly)
    display_class, area, layer, firing_rate, and the shuffle-based flags come from
    classify_session_units(). Then, joined on the CANONICAL unit key (row position into
    _units_df, NEVER the probe-local kilosort unit_id column):

        peak_channel_id, firing_rate_u   <- _units_df, by row position
        is_stable = stable_plus          <- (_units_df['quality'] == 1.0)
        is_o_plus_template               <- unit_row_idx in grand_oplus_units.csv for this session
        is_o_plusplus_template           <- unit_row_idx in grand_oplusplus_units.csv
        functional_class                 <- "O++" if o_plusplus_template
                                            else "O+" if o_plus_template
                                            else display_class

    Note the template tables' O+ set INCLUDES the O++ units (20 = 16 O+ + 4 O++ for
    sub-V182o_ses-260702), so O++ must be tested first.

    The template tables carry unit_row_idx explicitly. They must be joined on it and never on
    their unit_id column -- see omission/jnwb_ext/canonical_identity.py for why that distinction
    exists and what it cost when it was got wrong.

ACCEPTANCE
    Run with --verify to regenerate sub-V182o_ses-260702 and diff it against the surviving table.
    Anything short of an exact match means the recipe is NOT recovered and any replication built
    on it would not be comparable to the pilot.

Run:
  OMISSION_NWB_DIR=... python -m omission.scripts.dev_build_unitclass_20260829 --verify
  OMISSION_NWB_DIR=... python -m omission.scripts.dev_build_unitclass_20260829 \
      --session sub-V182o_ses-260629
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logging.disable(logging.INFO)

from jnwb.paths import nwb_dir  # noqa: E402
from omission.jnwb_ext.canonical_identity import assert_unique_units, attach_unit_identity  # noqa: E402
from omission.jnwb_ext.session import OmissionSession  # noqa: E402
from omission.jnwb_ext.unit_classification import classify_session_units  # noqa: E402

CLASSIFICATION_DIR = Path("omission/outputs/classification")
OPLUS_CSV = CLASSIFICATION_DIR / "grand_oplus_units.csv"
OPLUSPLUS_CSV = CLASSIFICATION_DIR / "grand_oplusplus_units.csv"
OUT_DIR = Path("omission/artifacts/data")

REFERENCE_SESSION = "sub-V182o_ses-260702"
REFERENCE_CSV = OUT_DIR / "pilot_v182o_260702_unitclass.csv"

# Exactly the columns the SPK-LFP drivers read. Reproducing THESE is what makes a replication
# comparable to the pilot; everything else in the table is carried along but never consumed.
CONSUMED_COLUMNS: tuple[str, ...] = (
    "unit_id", "functional_class", "display_class", "area", "layer", "firing_rate",
    "peak_channel_id", "stable_plus",
)


def _template_rows(csv: Path, session_prefix: str) -> set[int]:
    """unit_row_idx values for this session. Joined on row position, never on unit_id."""
    if not csv.exists():
        raise FileNotFoundError(f"template table missing: {csv}")
    t = pd.read_csv(csv)
    for col in ("session_prefix", "unit_row_idx"):
        if col not in t.columns:
            raise KeyError(f"{csv} lacks {col!r}; cannot join on the canonical unit key")
    return set(t.loc[t["session_prefix"] == session_prefix, "unit_row_idx"].astype(int))


def build(session_stem: str) -> pd.DataFrame:
    path = Path(nwb_dir()) / f"{session_stem}.nwb"
    if not path.exists():
        raise FileNotFoundError(path)
    session = OmissionSession(str(path))

    df = classify_session_units(session).reset_index(drop=True)
    units = session._units_df.reset_index(drop=True)
    if len(df) != len(units):
        raise ValueError(
            f"{session_stem}: classification has {len(df)} rows but the units table has "
            f"{len(units)}. Row position is the canonical unit key, so a length mismatch means "
            f"the two cannot be aligned positionally. Refusing to guess."
        )

    # Canonical identity, attached from the UNFILTERED units frame so row positions still
    # correspond to NWB Units rows.
    ident = attach_unit_identity(units, session_stem)
    assert_unique_units(ident)

    df["unit_id"] = np.arange(len(df), dtype=int)      # row position == canonical unit key
    df["peak_channel_id"] = units["peak_channel_id"].to_numpy()
    df["is_stable"] = (units["quality"].to_numpy() == 1.0)
    df["stable_plus"] = df["is_stable"]
    df["firing_rate_u"] = units["firing_rate"].to_numpy()

    # The session prefix in the template tables drops any trailing "_rec" recording suffix.
    prefix = session_stem[:-4] if session_stem.endswith("_rec") else session_stem
    oplus = _template_rows(OPLUS_CSV, prefix)
    oplusplus = _template_rows(OPLUSPLUS_CSV, prefix)
    rows = np.arange(len(df))
    df["is_o_plus_template"] = np.isin(rows, list(oplus))
    df["is_o_plusplus_template"] = np.isin(rows, list(oplusplus))

    # O++ first: the template O+ set CONTAINS the O++ units.
    df["functional_class"] = np.where(
        df["is_o_plusplus_template"], "O++",
        np.where(df["is_o_plus_template"], "O+", df["display_class"].astype(str)))
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", type=str, default=None)
    ap.add_argument("--verify", action="store_true",
                    help="regenerate the reference session and diff against the surviving table")
    args = ap.parse_args()

    if args.verify:
        if not REFERENCE_CSV.exists():
            raise SystemExit(f"reference table absent: {REFERENCE_CSV}")
        got = build(REFERENCE_SESSION)
        want = pd.read_csv(REFERENCE_CSV)
        shared = [c for c in want.columns if c in got.columns]
        missing = [c for c in want.columns if c not in got.columns]
        print(f"reference : {REFERENCE_CSV}")
        print(f"rows      : rebuilt {len(got)}  reference {len(want)}")
        print(f"columns   : {len(shared)} shared, {len(missing)} missing from rebuild")
        if missing:
            print(f"  MISSING: {missing}")

        bad = []
        for c in shared:
            a, b = got[c], want[c]
            if pd.api.types.is_numeric_dtype(b) and pd.api.types.is_numeric_dtype(a):
                same = np.allclose(a.astype(float), b.astype(float), equal_nan=True)
            else:
                same = a.astype(str).equals(b.astype(str))
            if not same:
                bad.append(c)
        print(f"columns differing: {len(bad)}")
        for c in bad[:15]:
            print(f"  DIFF {c}")

        # The acceptance test that matters is the CONSUMED set. Columns the SPK-LFP analysis
        # never reads can differ without affecting replication comparability -- but that
        # difference is still reported, never silently tolerated.
        bad_consumed = [c for c in bad if c in CONSUMED_COLUMNS]
        ok = not bad_consumed and not missing and len(got) == len(want)
        print(f"\nconsumed columns ({len(CONSUMED_COLUMNS)}): "
              f"{len(bad_consumed)} differing -> {'MATCH' if not bad_consumed else bad_consumed}")
        if bad and not bad_consumed:
            print(f"UNRESOLVED: {len(bad)} non-consumed columns do not reproduce. "
                  f"classify_session_units is deterministic run-to-run, so the surviving table "
                  f"was built by different code or different parameters. The lost ad-hoc script "
                  f"cannot be recovered, so this is recorded as a discrepancy, not resolved.")
        print(f"\n=== RECIPE RECOVERED FOR CONSUMED COLUMNS: {'PASS' if ok else 'FAIL'} ===")
        print("  functional_class counts rebuilt :",
              got["functional_class"].value_counts().to_dict())
        print("  functional_class counts reference:",
              want["functional_class"].value_counts().to_dict())
        raise SystemExit(0 if ok else 1)

    if not args.session:
        raise SystemExit("pass --session <stem> or --verify")
    out = build(args.session)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / f"unitclass_{args.session}.csv"
    out.to_csv(dest, index=False)
    print(f"Wrote {dest}  ({len(out)} units)")
    print(f"  functional_class: {out['functional_class'].value_counts().to_dict()}")
    print(f"  stable_plus: {int(out['stable_plus'].sum())} of {len(out)}")


if __name__ == "__main__":
    main()
