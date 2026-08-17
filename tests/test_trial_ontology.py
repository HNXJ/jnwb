"""Twelve-condition ontology test (Sol/Hamm Handout 2, acceptance test 3).

Asserts every expected/preceding identity and omission position for all 12 condition codes,
cross-checked against jnwb.omission_identity.OMISSION_IDENTITY_CONDITIONS -- the previously
existing, independently-maintained crosswalk -- as an agreement check between two different
representations of the same paradigm. Special attention to p4 A/B, which was swapped until the
2026-08-06 fix (jnwb/omission_identity.py:37-44): "Every p4-specific number computed before this
fix... must be treated as unreliable until rerun."
"""
from __future__ import annotations

import pytest

from jnwb.trial_ontology import (
    CONDITION_CODES,
    CONDITION_ONTOLOGY,
    PARENT_SEQUENCES,
    parse_condition,
)
from jnwb.omission_identity import OMISSION_IDENTITY_CONDITIONS


class TestAllTwelveConditions:
    def test_exactly_twelve_codes(self):
        assert len(CONDITION_CODES) == 12
        assert len(set(CONDITION_CODES)) == 12  # no duplicates

    def test_four_per_family(self):
        by_family = {"A": 0, "B": 0, "R": 0}
        for code in CONDITION_CODES:
            by_family[parse_condition(code)["sequence_family"]] += 1
        assert by_family == {"A": 4, "B": 4, "R": 4}

    @pytest.mark.parametrize("code", CONDITION_CODES)
    def test_parses_without_error(self, code):
        onto = parse_condition(code)
        assert onto["condition"] == code
        assert onto["sequence_family"] in ("A", "B", "R")
        assert onto["parent_sequence"] == PARENT_SEQUENCES[onto["sequence_family"]]

    # -- full (non-omission) sequences: AAAB, BBBA, RRRR --
    @pytest.mark.parametrize("code,family,presented", [
        ("AAAB", "A", "A"),
        ("BBBA", "B", "B"),
        ("RRRR", "R", None),
    ])
    def test_full_sequences(self, code, family, presented):
        onto = parse_condition(code)
        assert onto["is_omission"] is False
        assert onto["omission_position"] is None
        assert onto["sequence_family"] == family
        assert onto["presented_identity"] == presented
        assert onto["expected_identity"] is None
        assert onto["preceding_identity"] is None

    # -- p2 omissions --
    def test_p2_omission_A_family(self):
        onto = parse_condition("AXAB")
        assert onto["omission_position"] == "p2"
        assert onto["expected_identity"] == "A"
        assert onto["preceding_identity"] == "A"  # p1 = A in parent AAAB

    def test_p2_omission_B_family(self):
        onto = parse_condition("BXBA")
        assert onto["omission_position"] == "p2"
        assert onto["expected_identity"] == "B"
        assert onto["preceding_identity"] == "B"  # p1 = B in parent BBBA

    def test_p2_omission_R_family_has_no_identity(self):
        onto = parse_condition("RXRR")
        assert onto["omission_position"] == "p2"
        assert onto["expected_identity"] is None
        assert onto["preceding_identity"] is None

    # -- p3 omissions --
    def test_p3_omission_A_family(self):
        onto = parse_condition("AAXB")
        assert onto["omission_position"] == "p3"
        assert onto["expected_identity"] == "A"
        assert onto["preceding_identity"] == "A"  # p2 = A in parent AAAB

    def test_p3_omission_B_family(self):
        onto = parse_condition("BBXA")
        assert onto["omission_position"] == "p3"
        assert onto["expected_identity"] == "B"
        assert onto["preceding_identity"] == "B"  # p2 = B in parent BBBA

    def test_p3_omission_R_family_has_no_identity(self):
        onto = parse_condition("RRXR")
        assert onto["omission_position"] == "p3"
        assert onto["expected_identity"] is None
        assert onto["preceding_identity"] is None

    # -- p4 omissions: THE historically-buggy pair. Parent AAAB has p4=B, so omitting p4 from
    # the A-family parent means the omitted/expected identity is B, not A -- and the condition
    # code for that is AAAX (three A's then omitted-B). Symmetrically BBBX omits the A that
    # ends parent BBBA. Confirm both directions explicitly; this is exactly the swap that was
    # wrong before 2026-08-06. --
    def test_p4_omission_AAAX_expected_identity_is_B_not_A(self):
        onto = parse_condition("AAAX")
        assert onto["sequence_family"] == "A"  # three A's -> A-family parent (AAAB)
        assert onto["omission_position"] == "p4"
        assert onto["expected_identity"] == "B", (
            "AAAX's parent is AAAB (p1=A,p2=A,p3=A,p4=B) -- omitting p4 hides a B. "
            "This is the exact case that was swapped before the 2026-08-06 fix."
        )
        assert onto["preceding_identity"] == "A"  # p3 = A in parent AAAB

    def test_p4_omission_BBBX_expected_identity_is_A_not_B(self):
        onto = parse_condition("BBBX")
        assert onto["sequence_family"] == "B"  # three B's -> B-family parent (BBBA)
        assert onto["omission_position"] == "p4"
        assert onto["expected_identity"] == "A", (
            "BBBX's parent is BBBA (p1=B,p2=B,p3=B,p4=A) -- omitting p4 hides an A."
        )
        assert onto["preceding_identity"] == "B"  # p3 = B in parent BBBA

    def test_p4_omission_R_family_has_no_identity(self):
        onto = parse_condition("RRRX")
        assert onto["omission_position"] == "p4"
        assert onto["expected_identity"] is None
        assert onto["preceding_identity"] is None


class TestCrossCheckAgainstOmissionIdentityConditions:
    """The module docstring in jnwb/omission_identity.py already asserts this crosswalk from a
    2026-08-06 manual fix; this class independently re-derives it from pure string parsing and
    checks the two agree everywhere, especially p4."""

    @pytest.mark.parametrize("slot_key", ["p2", "p3", "p4"])
    @pytest.mark.parametrize("label", ["A", "B"])
    def test_expected_identity_matches_omission_identity_conditions_key(self, slot_key, label):
        code = OMISSION_IDENTITY_CONDITIONS[slot_key][label]
        onto = parse_condition(code)
        assert onto["expected_identity"] == label, (
            f"OMISSION_IDENTITY_CONDITIONS['{slot_key}']['{label}'] = {code!r}, but "
            f"parse_condition derives expected_identity={onto['expected_identity']!r} "
            f"independently from the code's own parent-sequence structure -- these must agree."
        )
        assert onto["omission_position"] == slot_key

    @pytest.mark.parametrize("slot_key", ["p2", "p3", "p4"])
    def test_R_condition_matches(self, slot_key):
        code = OMISSION_IDENTITY_CONDITIONS[slot_key]["R"]
        onto = parse_condition(code)
        assert onto["sequence_family"] == "R"
        assert onto["omission_position"] == slot_key


class TestInvalidCodesRejected:
    @pytest.mark.parametrize("bad_code", ["ABAB", "AAAA", "XXXX", "AXXB", "A", "AAABB", "aabc"])
    def test_rejects_non_paradigm_codes(self, bad_code):
        with pytest.raises(ValueError):
            parse_condition(bad_code)
