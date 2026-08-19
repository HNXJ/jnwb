"""
scripts/build_unified_class_census.py

Single accountable pipeline for the S+/S-/O+/O++/O-/O-- class-count table reported to Hamm
on 2026-08-17. Does NOT re-scan NWB itself -- the NWB scans already exist as three separate,
expensive (tens of minutes each), already-run pipelines, and Hamm's instruction was to assemble
the accounting, not redo the scans:

  1. S+/S- (local-baseline, likelihood-of-firing): scripts/classify_units_omission_inclusion_v1.py
     -> outputs/classification/unit_inclusion_v1.csv. This IS the NWB-scanning step for S+/S-;
     see jnwb/unit_inclusion.py for the classifier itself.
  2. O+/O++ (template-correlation) candidate pool: scripts/archive_oneoff/find_all_oplus_units.py
     -> outputs/classification/grand_oplus_units.csv. This IS the NWB-scanning step for O+/O++.
  3. O-/O-- (Q1 peak+ramp): scripts/classify_omission_units_grand.py
     -> outputs/classification/omission_grand_units.csv. This IS the NWB-scanning step for O-/O--.

This script is the aggregation/threshold/report layer on top of those three already-NWB-derived
tables -- it applies the corrected, Hamm-confirmed decisions from the 2026-08-17 fig03 handout
(artifacts/.lab/handout-fig03-oplusplus-threshold-20260817.md) and produces one final table.
No number below is computed by this script from a literal; every one traces to one of the three
input CSVs above, whose own provenance traces to NWB.

Known open items, NOT resolved by this script (see artifacts/.lab/*.json for the receipts):
  - O+/O++ candidate pool is contaminated by suppressed (S-/S--) units at a 55-71% rate
    (bug-oplus-candidate-pool-suppressed-unit-contamination-20260817.json). Not fixed here --
    that requires an upstream change to find_all_oplus_units.py's candidate gate.
  - No S++/S-- (double-criterion) tier exists in the new S1 local-baseline source, and no
    S1-style (likelihood-of-firing) equivalent exists yet for O-/O-- (that pipeline is still the
    old Q1 peak+ramp method) -- these three class-families are NOT on a common population or
    a common criterion design. "Other" is therefore not reported: these are three different
    screened populations, not five slices of one population, and summing/subtracting against a
    single grand total would misstate rather than round.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from jnwb import paths as _P
from omission.jnwb_ext.unit_classification import _git_sha  # private but stable; Conservation: not copied

REPO_ROOT = Path(__file__).resolve().parents[1]

S1_TABLE = Path(_P.outputs_dir("classification", "unit_inclusion_v1.csv"))
OPLUS_CANDIDATES = Path(_P.outputs_dir("classification", "grand_oplus_units.csv"))
OMISSION_GRAND = Path(_P.outputs_dir("classification", "omission_grand_units.csv"))

OUT_CSV = Path(_P.outputs_dir("classification", "unified_class_census_v1.csv"))
OUT_JSON = Path(_P.outputs_dir("classification", "unified_class_census_v1_summary.json"))

# Corrected, Hamm-confirmed 2026-08-17 (O++ boundary corrected same day after a row-vs-unit
# double-counting bug was caught -- see bug-oplus-row-vs-unit-count-inflation-20260817.json).
OPLUSPLUS_MIN_CORRELATION = 0.65
OPLUSPLUS_MAX_PVAL = 0.05
OPLUSPLUS_AREAS = ("V4", "TEO", "FEF", "PFC")

# S+/S- population filter: Hamm's "~1200+ / ~650+" matched quality_tier excluding mua, not the
# full corpus. See artifacts/.lab/handout-fig03-oplusplus-threshold-20260817.md.
S_QUALITY_TIERS = ("stable", "unstable")


def compute_s_plus_minus() -> dict:
    df = pd.read_csv(S1_TABLE)
    sub = df[df["quality_tier"].isin(S_QUALITY_TIERS)]
    return {
        "s_plus": int(sub["is_s_plus"].sum()),
        "s_minus": int(sub["is_s_minus"].sum()),
        "n_screened": int(len(sub)),
        "source": str(S1_TABLE),
        "population": f"unit_inclusion_v1.csv, quality_tier in {S_QUALITY_TIERS}",
    }


def compute_o_plus_plusplus() -> dict:
    df = pd.read_csv(OPLUS_CANDIDATES)
    # Dedup happens AFTER the threshold mask below, not on the raw table here -- a unit's O+ and
    # O*+ pattern_type rows carry independent (r, p) pairs, and the 2026-08-17 fix was specifically
    # to stop double-counting a unit that clears the mask under both pattern types.
    total_unique = df[["session_prefix", "unit_row_idx"]].drop_duplicates().shape[0]

    oppp_mask = (
        df["area"].isin(OPLUSPLUS_AREAS)
        & (df["mean_correlation"] >= OPLUSPLUS_MIN_CORRELATION)
        & (df["permutation_pval"] <= OPLUSPLUS_MAX_PVAL)
    )
    oppp_units = df.loc[oppp_mask, ["session_prefix", "unit_row_idx"]].drop_duplicates()
    n_oppp = int(len(oppp_units))
    n_oplus_only = int(total_unique - n_oppp)

    return {
        "o_plusplus": n_oppp,
        "o_plus_excl_plusplus": n_oplus_only,
        "o_plus_plus_total_candidates": int(total_unique),
        "source": str(OPLUS_CANDIDATES),
        "population": (
            f"grand_oplus_units.csv, deduplicated on (session_prefix, unit_row_idx); "
            f"O++ = area in {OPLUSPLUS_AREAS} & mean_correlation>={OPLUSPLUS_MIN_CORRELATION} "
            f"& permutation_pval<={OPLUSPLUS_MAX_PVAL}; O+ = all other unique candidates, "
            f"corpus-wide, unrestricted by area"
        ),
        "caveat": (
            "CONTAMINATED: 55-71%% of this candidate pool overlaps with legacy S-/S-- flags "
            "(scale/sign-invariant Pearson-correlation gate in find_all_oplus_units.py does not "
            "check the omission-slot rate against the unit's own baseline). See "
            "artifacts/.lab/bug-oplus-candidate-pool-suppressed-unit-contamination-20260817.json."
        ),
    }


def compute_o_minus_minusminus() -> dict:
    df = pd.read_csv(OMISSION_GRAND)
    counts = df["omission_class"].value_counts()
    return {
        "o_minus": int(counts.get("O-", 0)),
        "o_minus_minus": int(counts.get("O--", 0)),
        "n_screened": int(len(df)),
        "source": str(OMISSION_GRAND),
        "population": "omission_grand_units.csv, omission_class (Q1 peak+ramp), full corpus",
        "caveat": (
            "Different pipeline/criterion design than S+/S- (S1 likelihood-of-firing) and "
            "O+/O++ (template-correlation) above -- no S1-style equivalent has been built for "
            "the suppression side of the omission response yet."
        ),
    }


def main():
    s = compute_s_plus_minus()
    o_pos = compute_o_plus_plusplus()
    o_neg = compute_o_minus_minusminus()

    rows = [
        {"class": "O++", "n": o_pos["o_plusplus"], "population": o_pos["population"], "caveat": o_pos["caveat"]},
        {"class": "O+ (excl. O++)", "n": o_pos["o_plus_excl_plusplus"], "population": o_pos["population"], "caveat": o_pos["caveat"]},
        {"class": "S+", "n": s["s_plus"], "population": s["population"], "caveat": "no S++ sub-tier exists in this source"},
        {"class": "S-", "n": s["s_minus"], "population": s["population"], "caveat": "no S-- sub-tier exists in this source"},
        {"class": "O-", "n": o_neg["o_minus"], "population": o_neg["population"], "caveat": o_neg["caveat"]},
        {"class": "O--", "n": o_neg["o_minus_minus"], "population": o_neg["population"], "caveat": o_neg["caveat"]},
    ]
    out_df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_CSV, index=False)

    summary = {
        "method": "unified_class_census_v1",
        "git_sha": _git_sha(REPO_ROOT),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "s_plus_minus": s,
            "o_plus_plusplus": o_pos,
            "o_minus_minusminus": o_neg,
        },
        "not_computed": {
            "Other": (
                "Not reported: the three class-families above come from three different "
                "screened populations with three different inclusion criteria, not five slices "
                "of one population -- summing/subtracting against a single grand total would "
                "misstate, not just round. See script docstring."
            )
        },
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2))

    print(out_df.to_string(index=False))
    print(f"\nWrote {OUT_CSV}")
    print(f"Wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
