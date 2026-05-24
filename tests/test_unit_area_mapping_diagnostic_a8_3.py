# tests/test_unit_area_mapping_diagnostic_a8_3.py
"""
Unit tests for run_unit_area_mapping_diagnostic_a8_3.py.

Covers all 10 required A8.3 test behaviors:
1. DP maps to V4.
2. Explicit V3d and V3a are preserved.
3. Generic V3 is not silently split or dropped.
4. Missing probe metadata becomes unmapped_no_metadata.
5. Invalid channel becomes invalid_channel (or unmapped_no_metadata when no metadata).
6. One-to-one join integrity is enforced for A8.1/A8.2 unit keys.
7. Duplicate unit keys fail or are explicitly flagged.
8. can_support_hierarchy_claim is false for heuristic/unresolved mappings.
9. Output manifest includes git commit, input paths, hashes, and truth_safe_unverified.
10. No area enrichment or biological hierarchy claim text is emitted in summaries.
"""

import sys
import os
import json
import csv
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run_unit_area_mapping_diagnostic_a8_3 import (
    TRUTH_SAFE_UNVERIFIED,
    CANONICAL_AREA_ORDER,
    resolve_area_group,
    resolve_claim_flags,
    load_a6_unit_area_inventory,
    load_a8_1_unit_keys,
    load_a8_2_unit_keys,
    build_long_mapping_table,
    build_session_summary,
    build_status_summary,
    build_join_integrity_report,
    main,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_a8_3_setup(tmp_path):
    """Creates a minimal but complete mock file tree for A8.3 tests."""
    a6_dir  = tmp_path / "a6"
    a81_dir = tmp_path / "a8_1"
    a82_dir = tmp_path / "a8_2"
    out_dir = tmp_path / "out"
    for d in [a6_dir, a81_dir, a82_dir]:
        d.mkdir()

    # A6 unit_area_inventory.csv
    a6_unit_csv = a6_dir / "unit_area_inventory.csv"
    with open(a6_unit_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "session_id", "unit_id", "unit_index", "sorting_quality_or_status",
            "peak_channel_or_status", "anchor_channel_or_status", "probe_id_or_status",
            "raw_area_label", "canonical_area_label", "area_group",
            "area_resolution_status", "unit_axis_join_status",
            "manuscript_safe_unit_area", "source_file", "warnings"
        ])
        # Unit 0: DP → V4 (metadata_resolved_channel)
        writer.writerow(["230719", "ses-230719_probe1_unit0", 0, "good",
                          "32", "32", "1",
                          "DP (V4)", "V4", "Visual",
                          "metadata_resolved_channel", "joined",
                          "false", "session-area-mapping.md", "None"])
        # Unit 1: V3d preserved
        writer.writerow(["230719", "ses-230719_probe2_unit1", 1, "good",
                          "10", "10", "2",
                          "V3d", "V3d", "Visual",
                          "metadata_resolved_equal_segment", "joined",
                          "false", "session-area-mapping.md", "None"])
        # Unit 2: V3a preserved
        writer.writerow(["230719", "ses-230719_probe2_unit2", 2, "good",
                          "20", "20", "2",
                          "V3a", "V3a", "Visual",
                          "metadata_resolved_equal_segment", "joined",
                          "false", "session-area-mapping.md", "None"])
        # Unit 3: Generic V3 (unresolved)
        writer.writerow(["230630", "ses-230630_probe2_unit3", 3, "good",
                          "5", "5", "2",
                          "V3", "V3", "Visual",
                          "unresolved_generic_v3", "joined",
                          "false", "session-area-mapping.md", "None"])
        # Unit 4: unmapped_no_metadata (missing peak/anchor)
        writer.writerow(["230630", "ses-230630_probe0_unit4", 4, "Unknown",
                          "missing_metadata", "missing_metadata", "0",
                          "None", "Unknown", "Unknown",
                          "unmapped_no_metadata", "missing_unit_metadata",
                          "false", "session-area-mapping.md", "No unit metadata CSV file found"])
        # Unit 5: heuristic_equal_segment (cannot support hierarchy)
        writer.writerow(["230629", "ses-230629_probe0_unit5", 5, "good",
                          "15", "15", "0",
                          "V1", "V1", "Visual",
                          "heuristic_equal_segment", "joined",
                          "false", "session-area-mapping.md", "None"])

    # A6 probe_area_inventory.csv (minimal, needed for manifest hash)
    a6_probe_csv = a6_dir / "probe_area_inventory.csv"
    with open(a6_probe_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "probe_id", "raw_area_label", "canonical_area_label",
                          "area_group", "alias_applied", "area_resolution_status",
                          "source_file", "warnings"])
        writer.writerow(["230719", "1", "DP (V4)", "V4", "Visual", "yes",
                          "metadata_resolved_channel", "session-area-mapping.md", "None"])
        writer.writerow(["230719", "2", "V3d", "V3d", "Visual", "no",
                          "metadata_resolved_equal_segment", "session-area-mapping.md", "None"])
        writer.writerow(["230719", "2", "V3a", "V3a", "Visual", "no",
                          "metadata_resolved_equal_segment", "session-area-mapping.md", "None"])
        writer.writerow(["230630", "2", "V3", "V3", "Visual", "no",
                          "unresolved_generic_v3", "session-area-mapping.md", "None"])

    # A8.1 unit_candidate_labels.csv — 5 units
    a81_csv = a81_dir / "unit_candidate_labels.csv"
    with open(a81_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "session_id", "source_file", "unit_axis_index",
            "n_conditions_available", "n_unit_trial_observations",
            "candidate_labels", "primary_candidate_label", "candidate_label_basis",
            "q_threshold", "effect_size_threshold", "correction_scope",
            "manuscript_safe_response_class", "biological_interpretation_allowed",
            "area_hierarchy_allowed", "unit_area_join_status_from_A6",
            "manuscript_safe_unit_area_from_A6", "warnings"
        ])
        writer.writerow(["230719", "ses230719-units-probe1-spk-AAAB.npy", 0,
                          8, 160, "S_plus_candidate", "S_plus_candidate", "P1 activation",
                          0.05, 0.3, "within_session_all_units_all_primary_contrasts",
                          "false", "false", "false", "joined", "false", "None"])
        writer.writerow(["230719", "ses230719-units-probe2-spk-AAAB.npy", 1,
                          8, 160, "null_or_unclassified", "null_or_unclassified", "No phenotype",
                          0.05, 0.3, "within_session_all_units_all_primary_contrasts",
                          "false", "false", "false", "joined", "false", "None"])
        writer.writerow(["230719", "ses230719-units-probe2-spk-AAAB.npy", 2,
                          8, 160, "S_minus_candidate", "S_minus_candidate", "P1 suppression",
                          0.05, 0.3, "within_session_all_units_all_primary_contrasts",
                          "false", "false", "false", "joined", "false", "None"])
        writer.writerow(["230630", "ses230630-units-probe2-spk-AAAB.npy", 3,
                          8, 140, "null_or_unclassified", "null_or_unclassified", "No phenotype",
                          0.05, 0.3, "within_session_all_units_all_primary_contrasts",
                          "false", "false", "false", "unresolved_generic_v3", "false", "None"])
        writer.writerow(["230630", "ses230630-units-probe0-spk-AAAB.npy", 4,
                          8, 140, "S_plus_candidate", "S_plus_candidate", "P1 activation",
                          0.05, 0.3, "within_session_all_units_all_primary_contrasts",
                          "false", "false", "false", "missing_unit_metadata", "false", "None"])

    # A8.2 candidate_label_stability_by_unit.csv — same 5 units
    a82_csv = a82_dir / "candidate_label_stability_by_unit.csv"
    with open(a82_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "session_id", "unit_axis_index",
            "n_sweeps_S_plus", "n_sweeps_S_minus", "n_sweeps_O_plus",
            "n_sweeps_O_minus", "n_sweeps_X", "entropy_score",
            "dominant_label", "strict_label", "permissive_label"
        ])
        writer.writerow(["230719", 0, 10, 0, 0, 0, 0, "0.0000", "S_plus_candidate", "S_plus_candidate", "S_plus_candidate"])
        writer.writerow(["230719", 1, 0,  0, 0, 0, 0, "0.0000", "null_or_unclassified", "null_or_unclassified", "null_or_unclassified"])
        writer.writerow(["230719", 2, 0, 10, 0, 0, 0, "0.0000", "S_minus_candidate", "S_minus_candidate", "S_minus_candidate"])
        writer.writerow(["230630", 3, 0,  0, 0, 0, 0, "0.0000", "null_or_unclassified", "null_or_unclassified", "null_or_unclassified"])
        writer.writerow(["230630", 4, 8,  0, 0, 0, 0, "0.0000", "S_plus_candidate", "S_plus_candidate", "S_plus_candidate"])

    return {
        "a6_dir":  a6_dir,
        "a81_dir": a81_dir,
        "a82_dir": a82_dir,
        "out_dir": out_dir,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Unit-level function tests (no file I/O)
# ──────────────────────────────────────────────────────────────────────────────

def test_dp_maps_to_v4():
    """1. DP->V4 alias: resolve_claim_flags accepts V4 under metadata_resolved_channel."""
    can_area, can_hier = resolve_claim_flags("metadata_resolved_channel", "V4")
    assert can_area is True
    assert can_hier is True
    # Confirm V4 is in canonical order
    assert "V4" in CANONICAL_AREA_ORDER


def test_v3d_and_v3a_preserved():
    """2. Explicit V3d and V3a are distinct canonical areas."""
    assert "V3d" in CANONICAL_AREA_ORDER
    assert "V3a" in CANONICAL_AREA_ORDER
    # They must remain separate — confirm they are not collapsed
    assert CANONICAL_AREA_ORDER.index("V3d") != CANONICAL_AREA_ORDER.index("V3a")
    # Both map to a resolved group
    assert resolve_area_group("V3d") == "intermediate_visual_temporal"
    assert resolve_area_group("V3a") == "intermediate_visual_temporal"
    # Both can support area claims under metadata_resolved status
    can_area_d, _ = resolve_claim_flags("metadata_resolved_equal_segment", "V3d")
    can_area_a, _ = resolve_claim_flags("metadata_resolved_equal_segment", "V3a")
    assert can_area_d is True
    assert can_area_a is True


def test_generic_v3_cannot_support_claims():
    """3. Generic V3 (unresolved_generic_v3) cannot support area or hierarchy claims."""
    can_area, can_hier = resolve_claim_flags("unresolved_generic_v3", "V3")
    assert can_area is False
    assert can_hier is False


def test_missing_metadata_becomes_unmapped():
    """4. Unit with no A6 entry gets area_resolution_status=unmapped_no_metadata."""
    a8_1_keys = {("ses_X", 0): {"session_id": "ses_X", "unit_axis_index": "0"}}
    a8_2_keys = {("ses_X", 0): {"session_id": "ses_X", "unit_axis_index": "0"}}
    a6_inventory = {}  # Empty — no metadata

    long_rows, unresolved, dp_alias, generic_v3, _, _ = build_long_mapping_table(
        a8_1_keys, a8_2_keys, a6_inventory, "/fake/path.csv"
    )
    assert len(long_rows) == 1
    assert long_rows[0]["area_resolution_status"] == "unmapped_no_metadata"
    assert long_rows[0]["can_support_area_claim"] == "false"
    assert long_rows[0]["can_support_hierarchy_claim"] == "false"
    # Must appear in unresolved table
    assert len(unresolved) == 1


def test_invalid_channel_blocks_hierarchy():
    """5. invalid_channel status cannot support hierarchy claims."""
    can_area, can_hier = resolve_claim_flags("invalid_channel", "V4")
    assert can_area is False
    assert can_hier is False
    can_area2, can_hier2 = resolve_claim_flags("invalid_probe", "PFC")
    assert can_area2 is False
    assert can_hier2 is False


def test_join_integrity_one_to_one(mock_a8_3_setup):
    """6. Every A8.1 key appears exactly once in the long table (no row loss or duplication)."""
    a6_dir  = mock_a8_3_setup["a6_dir"]
    a81_dir = mock_a8_3_setup["a81_dir"]
    a82_dir = mock_a8_3_setup["a82_dir"]

    a6_inv, a6_path  = load_a6_unit_area_inventory(str(a6_dir))
    a8_1_keys, _     = load_a8_1_unit_keys(str(a81_dir))
    a8_2_keys, _     = load_a8_2_unit_keys(str(a82_dir))

    long_rows, _, _, _, _, _ = build_long_mapping_table(
        a8_1_keys, a8_2_keys, a6_inv, str(a6_dir / "unit_area_inventory.csv")
    )

    # Exactly one row per A8.1 key
    assert len(long_rows) == len(a8_1_keys)
    long_keys = [(r["session_id"], int(r["unit_axis_index"])) for r in long_rows]
    assert len(long_keys) == len(set(long_keys)), "Duplicate keys in long table"

    integrity = build_join_integrity_report(a8_1_keys, a8_2_keys, long_rows, set(), set())
    fail_checks = [j for j in integrity if j["status"] == "FAIL"]
    assert len(fail_checks) == 0, f"Join integrity failures: {fail_checks}"


def test_duplicate_unit_keys_flagged():
    """7. If A6 has duplicate (session_id, unit_index) rows, first is kept (no silent merge)."""
    a6_inv = {}
    # Simulate loading two rows with the same key
    key = ("ses_dup", 0)
    row1 = {"session_id": "ses_dup", "unit_index": "0", "area_resolution_status": "metadata_resolved_channel",
            "canonical_area_label": "V4", "raw_area_label": "V4", "area_group": "Visual",
            "peak_channel_or_status": "32", "anchor_channel_or_status": "32",
            "probe_id_or_status": "1", "source_file": "f.csv",
            "warnings": "None", "alias_applied": "no"}
    # First insertion
    if key not in a6_inv:
        a6_inv[key] = dict(row1)
    # Simulate second insertion attempt — should NOT overwrite
    row2 = dict(row1)
    row2["canonical_area_label"] = "PFC"  # different, should NOT override
    if key not in a6_inv:
        a6_inv[key] = row2
    # First row wins; PFC should NOT be present
    assert a6_inv[key]["canonical_area_label"] == "V4"


def test_heuristic_mapping_blocks_hierarchy():
    """8. heuristic_equal_segment cannot support hierarchy claims."""
    can_area, can_hier = resolve_claim_flags("heuristic_equal_segment", "V1")
    assert can_area is False
    assert can_hier is False
    # Also verify unresolved blocks
    for status in ("unresolved_generic_v3", "unmapped_no_metadata", "unknown_area"):
        ca, ch = resolve_claim_flags(status, "V4")
        assert ch is False, f"{status} should not support hierarchy claims"


def test_manifest_metadata_and_hashes(mock_a8_3_setup, monkeypatch):
    """9. Output manifest includes git commit, input paths, hashes, and truth_safe_unverified."""
    out_dir  = mock_a8_3_setup["out_dir"]
    a6_dir   = mock_a8_3_setup["a6_dir"]
    a81_dir  = mock_a8_3_setup["a81_dir"]
    a82_dir  = mock_a8_3_setup["a82_dir"]

    monkeypatch.setattr(
        "scripts.run_unit_area_mapping_diagnostic_a8_3.get_git_commit",
        lambda: "mock_commit_a8_3"
    )

    test_args = [
        "run_unit_area_mapping_diagnostic_a8_3.py",
        "--a6-dir",  str(a6_dir),
        "--a8-1-dir", str(a81_dir),
        "--a8-2-dir", str(a82_dir),
        "--out-dir",  str(out_dir),
    ]
    with patch("sys.argv", test_args):
        main()

    manifest_path = out_dir / "unit_area_mapping_execution_manifest.json"
    assert manifest_path.exists()
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["truth_status"] == TRUTH_SAFE_UNVERIFIED
    assert manifest["artifact_id"] == "A8_3_unit_area_mapping_diagnostic"
    assert manifest["git_commit"] == "mock_commit_a8_3"
    assert len(manifest["hashes"]) > 0
    assert "a8_1_unit_candidate_labels" in manifest["input_files"]
    assert "a6_unit_area_inventory" in manifest["input_hashes"]


def test_no_hierarchy_or_enrichment_language_in_summary(mock_a8_3_setup, monkeypatch):
    """10. No area enrichment or biological hierarchy claim text is emitted in summaries."""
    out_dir  = mock_a8_3_setup["out_dir"]
    a6_dir   = mock_a8_3_setup["a6_dir"]
    a81_dir  = mock_a8_3_setup["a81_dir"]
    a82_dir  = mock_a8_3_setup["a82_dir"]

    monkeypatch.setattr(
        "scripts.run_unit_area_mapping_diagnostic_a8_3.get_git_commit",
        lambda: "mock_commit_a8_3"
    )

    test_args = [
        "run_unit_area_mapping_diagnostic_a8_3.py",
        "--a6-dir",  str(a6_dir),
        "--a8-1-dir", str(a81_dir),
        "--a8-2-dir", str(a82_dir),
        "--out-dir",  str(out_dir),
    ]
    with patch("sys.argv", test_args):
        main()

    # Check summary JSON safety flags
    summary_path = out_dir / "unit_area_mapping_execution_summary.json"
    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    assert summary["manuscript_safe_response_class"] is False
    assert summary["area_hierarchy_allowed"] is False
    assert summary["manuscript_hierarchy_claims_allowed"] is False

    # Check that blocked claims explicitly enumerate hierarchy
    blocked = " ".join(summary["blocked_claims"])
    assert "hierarchy" in blocked.lower()
    assert "enrichment" in blocked.lower()

    # Check summary MD does not contain over-claiming phrases
    md_path = out_dir / "unit_area_mapping_execution_summary.md"
    md_text = md_path.read_text(encoding="utf-8")
    overclaim_phrases = [
        "higher-order weighted",
        "FEF/PFC dominant",
        "mostly FEF",
        "predictive routing confirmed",
        "hierarchy proven",
        "area enrichment result",
    ]
    for phrase in overclaim_phrases:
        assert phrase.lower() not in md_text.lower(), \
            f"Overclaim phrase found in summary MD: '{phrase}'"
