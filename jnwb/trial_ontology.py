"""Canonical omission-paradigm trial ontology.

Added 2026-08-10 per Sol/Hamm's Handout 2 (artifacts/.lab/agent-harness-audit-20260810.json,
P1 item "materialize experimental semantics"): `preceding_identity`, `expected_identity`,
`sequence_family`, and `omission_position` were previously re-derived ad hoc, by parsing
condition-code strings like "AXAB" inline, in at least three separate places (the v2
block-number confound diagnosis, the v3 cycle-detection fix, and the 2026-08-06 p4 A/B
label-swap bug -- see jnwb/omission_identity.py:37-44, "every p4-specific number computed
before this fix... must be treated as unreliable until rerun"). This module is the one place
that parsing happens now.

THE PARADIGM
    Every trial belongs to one of three 4-slot parent sequences:
      "A" family -> AAAB (p1=A, p2=A, p3=A, p4=B)
      "B" family -> BBBA (p1=B, p2=B, p3=B, p4=A)
      "R" family -> RRRR (no fixed identity at any slot -- the random-control family; "R" is a
                    family label, not a stimulus identity the way A/B are)
    A trial either presents the parent sequence in full (condition code == the parent string,
    e.g. "AAAB" itself), or omits exactly one slot, marked 'X' in the condition code (e.g.
    "AXAB" omits p2). There are exactly 12 condition codes in this design: 3 families x
    4 variants each (the full sequence + one omission variant per slot p2/p3/p4 -- p1 is never
    omitted in this paradigm).

    The parent-sequence family is fully determined by which letter (A/B/R) makes up the
    non-omitted characters of the code -- this is why `parse_condition` needs no session data
    and is exhaustively unit-testable (tests/test_trial_ontology.py checks all 12 codes
    explicitly, matching them against jnwb.omission_identity.OMISSION_IDENTITY_CONDITIONS as an
    independent cross-check, especially the p4 A/B pair that was previously swapped).
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

PARENT_SEQUENCES: Dict[str, str] = {
    "A": "AAAB",
    "B": "BBBA",
    "R": "RRRR",
}

CONDITION_CODES: List[str] = [
    "AAAB", "AXAB", "AAXB", "AAAX",
    "BBBA", "BXBA", "BBXA", "BBBX",
    "RRRR", "RXRR", "RRXR", "RRRX",
]

SLOT_INDEX: Dict[str, int] = {"p1": 0, "p2": 1, "p3": 2, "p4": 3}
INDEX_SLOT: Dict[int, str] = {v: k for k, v in SLOT_INDEX.items()}


def parse_condition(code: str) -> Dict[str, object]:
    """Decompose a 4-character condition code into its ontology fields.

    Pure string logic, no session/NWB access required -- see module docstring for the paradigm
    this encodes. Raises ValueError on anything that isn't one of the 12 recognized codes.
    """
    code = code.strip().upper()
    if code not in CONDITION_CODES:
        raise ValueError(
            f"not one of the 12 recognized paradigm condition codes: {code!r}. "
            f"Valid codes: {CONDITION_CODES}"
        )

    # A code is either its family's parent sequence verbatim (full/non-omission trial), or
    # that parent with exactly one slot replaced by 'X'. Checking against the parent directly
    # (rather than counting repeated letters) handles both cases uniformly -- letter-counting
    # alone misclassifies "AAAB" itself, whose closing B is a real, different, non-omitted
    # character, not a stand-in for a missing A.
    family_letter = None
    parent = None
    for letter, seq in PARENT_SEQUENCES.items():
        if code == seq:
            family_letter, parent = letter, seq
            break
        diffs = [i for i in range(4) if code[i] != seq[i]]
        if len(diffs) == 1 and code[diffs[0]] == "X":
            family_letter, parent = letter, seq
            break
    if family_letter is None:
        raise ValueError(f"condition code {code!r} does not match any known parent sequence")

    x_positions = [i for i, c in enumerate(code) if c == "X"]
    if len(x_positions) > 1:
        raise ValueError(f"condition code {code!r} has more than one omitted slot")
    is_omission = bool(x_positions)
    omission_idx = x_positions[0] if is_omission else None
    omission_position = INDEX_SLOT[omission_idx] if is_omission else None

    # "R" is a family label, not a stimulus identity -- expected/preceding/presented identity
    # are only meaningful for the A/B families, which have a real, fixed per-slot identity.
    has_real_identity = family_letter in ("A", "B")

    if is_omission:
        expected_identity = parent[omission_idx] if has_real_identity else None
        preceding_identity = (
            parent[omission_idx - 1] if (has_real_identity and omission_idx > 0) else None
        )
        presented_identity = None  # nothing was presented at the slot of interest
    else:
        expected_identity = None
        preceding_identity = None
        presented_identity = family_letter if has_real_identity else None

    return {
        "condition": code,
        "sequence_family": family_letter,
        "parent_sequence": parent,
        "is_omission": is_omission,
        "omission_position": omission_position,
        "expected_identity": expected_identity,
        "preceding_identity": preceding_identity,
        "presented_identity": presented_identity,
    }


# Precomputed for every known code -- import this instead of re-parsing in a hot loop.
CONDITION_ONTOLOGY: Dict[str, Dict[str, object]] = {c: parse_condition(c) for c in CONDITION_CODES}


def build_trial_ontology(
    session,
    slot_keys: tuple = ("p2", "p3", "p4"),
    phase: int = 2,
    families: tuple = ("A", "B", "R"),
) -> pd.DataFrame:
    """Build the canonical per-trial ontology table for one session.

    One row per (slot_key, family, trial) triple that exists in this session, with columns:
    trial_id, subject, session, cycle, condition, sequence_family, omission_position,
    preceding_identity, expected_identity, presented_identity, is_omission, correct_trial.

    `cycle` uses the same temporal-cycle detection as the leakage-safe decoding pipeline
    (jnwb.omission_identity.detect_trial_cycles) -- computed per slot_key, since cycle
    membership is with respect to that slot's own set of A/B/R trials, matching
    scripts/compute_omission_identity_leakage_safe.py's _trial_table().
    """
    from jnwb.omission_identity import OMISSION_IDENTITY_CONDITIONS, detect_trial_cycles

    metadata = getattr(session, "_metadata", None) or {}
    subject = metadata.get("subject_id") if isinstance(metadata, dict) else None
    session_name = session.nwb_path.stem if getattr(session, "nwb_path", None) else None
    if not subject and session_name and session_name.startswith("sub-"):
        # NWB subject_id is not always populated upstream (confirmed None on real converted
        # files) -- fall back to the project's own sub-<SUBJECT>_ses-<SESSION> filename
        # convention rather than leaving a required ontology column empty.
        subject = session_name.split("_")[0].removeprefix("sub-")

    rows: List[dict] = []
    trial_counter = 0
    for slot_key in slot_keys:
        cfg = OMISSION_IDENTITY_CONDITIONS[slot_key]
        pieces = []
        for fam in families:
            code = cfg.get(fam)
            if code is None:
                continue
            epochs = session.get_epochs(phase=phase, condition=code, correct_only=False)
            if len(epochs) == 0:
                continue
            part = epochs[["start_time"]].copy()
            part["condition"] = code
            if "correct" in epochs.columns:
                part["correct_trial"] = epochs["correct"].astype(bool).to_numpy()
            else:
                part["correct_trial"] = np.nan
            pieces.append(part)
        if not pieces:
            continue
        table = pd.concat(pieces, ignore_index=True)
        table["start_time"] = pd.to_numeric(table["start_time"], errors="coerce")
        table = table.dropna(subset=["start_time"]).reset_index(drop=True)
        table["cycle"] = detect_trial_cycles(table)

        for _, r in table.iterrows():
            onto = CONDITION_ONTOLOGY[r["condition"]]
            trial_counter += 1
            rows.append({
                "trial_id": trial_counter,
                "subject": subject,
                "session": session_name,
                "cycle": int(r["cycle"]),
                "slot_key": slot_key,
                "condition": r["condition"],
                "sequence_family": onto["sequence_family"],
                "omission_position": onto["omission_position"],
                "preceding_identity": onto["preceding_identity"],
                "expected_identity": onto["expected_identity"],
                "presented_identity": onto["presented_identity"],
                "is_omission": onto["is_omission"],
                "correct_trial": bool(r["correct_trial"]) if pd.notna(r["correct_trial"]) else None,
                "start_time": float(r["start_time"]),
            })

    return pd.DataFrame(rows)
