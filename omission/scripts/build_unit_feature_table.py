r"""
Per-unit master feature table for the neuron-type x layer x firing-rate x LFP supplemental
analysis (goal-neuron-type-layer-lfp-relationships-20260815).

One row per unit in outputs/classification/omission_grand_units.csv, joined against:
  - grand_s_and_o_units.csv for S++/S-- (is_Splus_double/is_Sminus_double -- subsets of
    is_Splus/is_Sminus, NOT independent tiers)
  - outputs/layers/unit_layers.csv for vFLIP layer (sup/mid/deep/na)
via the EXACT join keys and folding logic already implemented and reviewed in
context/figures/fig03_unit_census/fig03_unit_census.py (attach_legacy, attach_layer) -- reused
directly, not re-derived, per "do not reinvent" in the approved plan.

WHY NOT grand_s_and_o_units.csv's OWN 'layer' COLUMN
    That column is constant ('Superficial' for all 2921 rows) -- see
    artifacts/.lab/note-grand-s-and-o-layer-constant-20260815.json for the root cause
    (jnwb.addressing.classify_layer_from_depth's hardcoded z>1000um threshold never fires on
    this corpus's electrode z-coordinate scale, 4.42-16.0). unit_layers.csv (vFLIP-derived) is
    the only trustworthy layer source and is what fig03_unit_census.py::attach_layer uses.

WAVEFORM FEATURES DROPPED
    Per artifacts/.lab/bug-nwb-waveform-metrics-uninterpretable-20260815.json and Hamm's direct
    decision (2026-08-15): waveform_duration/PT_ratio/waveform_halfwidth in the raw NWB units
    table (and therefore in omission_grand_units.csv, which passes them through) do not
    reproduce a physically plausible trough-to-peak duration or amplitude ratio -- not used as
    features here.

OMISSION TIER
    omission_grand_units.csv's own `omission_class` column already carries the full
    O++/O+/ns/O-/O-- tiers (mutually exclusive) -- no separate join needed for the O side,
    unlike S+/S++ which needs grand_s_and_o_units.csv's legacy classifier.

Output: outputs/classification/unit_master_features.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from jnwb import paths as _P  # noqa: E402

GRAND_UNITS = _P.outputs_dir("classification", "omission_grand_units.csv")
LEGACY_TABLE = _P.outputs_dir("classification", "grand_s_and_o_units.csv")
LAYER_TABLE = _P.outputs_dir("layers", "unit_layers.csv")
OUT_CSV = REPO / "outputs/classification/unit_master_features.csv"

STABLE_KEEP_THRESHOLD = 0.98  # fig03_unit_census.py's own constant, reused for consistency


def attach_legacy(df: pd.DataFrame) -> pd.DataFrame:
    """Byte-identical join logic to fig03_unit_census.py::attach_legacy (S++/S-- source)."""
    legacy = pd.read_csv(LEGACY_TABLE)
    m = df.merge(legacy[["session_prefix", "unit_row_idx", "is_Splus", "is_Splus_double",
                         "is_Sminus", "is_Sminus_double"]],
                 left_on=["session", "unit_row"], right_on=["session_prefix", "unit_row_idx"],
                 how="left")
    m["legacy_screened"] = m.is_Splus.notna()
    return m


def attach_layer(df: pd.DataFrame) -> pd.DataFrame:
    """Byte-identical join logic to fig03_unit_census.py::attach_layer (vFLIP layer source)."""
    layer = pd.read_csv(LAYER_TABLE)
    m = df.merge(layer[["session_prefix", "unit_index", "unit_layer"]],
                 left_on=["session", "unit_row"], right_on=["session_prefix", "unit_index"],
                 how="left")
    m["layer3"] = np.where(m.unit_layer == "sup", "sup",
                    np.where(m.unit_layer == "deep", "deep", "Null"))
    return m


def build() -> pd.DataFrame:
    df = pd.read_csv(GRAND_UNITS)
    df["area10"] = df["area10"].fillna(df["area"])
    df = attach_legacy(df)
    df = attach_layer(df)

    # Functional class flags -- S++/S-- pooled into S+/S- (subset, per grand_s_and_o_units.csv's
    # own is_Splus_double semantics: stricter p<0.01 vs p<0.05 at the same r>0.3 threshold).
    df["is_Splus"] = df["is_Splus"].infer_objects(copy=False).fillna(False).astype(bool)
    df["is_Splus_double"] = df["is_Splus_double"].infer_objects(copy=False).fillna(False).astype(bool)
    df["is_Sminus"] = df["is_Sminus"].infer_objects(copy=False).fillna(False).astype(bool)
    df["is_Sminus_double"] = df["is_Sminus_double"].infer_objects(copy=False).fillna(False).astype(bool)
    df["is_Oplus"] = df["omission_class"].isin(["O+", "O++"])
    df["is_Oplus_double"] = df["omission_class"] == "O++"
    df["is_Ominus"] = df["omission_class"].isin(["O-", "O--"])
    df["is_Ominus_double"] = df["omission_class"] == "O--"

    df["layer_informative"] = df["layer3"].isin(["sup", "deep"])

    return df


def main():
    df = build()
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    n = len(df)
    n_layer = int(df.layer_informative.sum())
    n_legacy = int(df.legacy_screened.sum())
    print(f"WROTE {OUT_CSV} ({n} units)")
    print(f"  layer-informative (sup/deep): {n_layer}/{n} ({100*n_layer/n:.1f}%)")
    print(f"  legacy-screened (S+/S- eligible): {n_legacy}/{n} ({100*n_legacy/n:.1f}%)")
    for col in ["is_Splus", "is_Splus_double", "is_Sminus", "is_Sminus_double",
               "is_Oplus", "is_Oplus_double", "is_Ominus", "is_Ominus_double"]:
        print(f"  {col}: {int(df[col].sum())}")


if __name__ == "__main__":
    main()
