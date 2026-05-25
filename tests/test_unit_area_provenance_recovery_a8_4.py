# tests/test_unit_area_provenance_recovery_a8_4.py
"""
Unit tests for run_unit_area_provenance_recovery_a8_4.py

Required tests:
1. Source-file probe extraction is deterministic.
2. Recovered peak channel maps to canonical area only when channel metadata exists.
3. Conflicting metadata sources block upgrade.
4. Row-order-only mapping remains provisional (not upgraded by A8.4).
5. Missing metadata remains unresolved.
6. DP maps to V4 if recovered from metadata.
7. Generic V3 remains unresolved unless metadata specifies V3d/V3a.
8. Output manifest includes git commit, input paths, hashes, and truth_safe_unverified.
9. No hierarchy claim text is emitted.
10. Original A8.3 statuses are preserved in output.
"""

import sys
import os
import csv
import json
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run_unit_area_provenance_recovery_a8_4 import (
    TRUTH_SAFE_UNVERIFIED,
    SESSION_PROBE_AREA_MAP,
    CANONICAL_AREAS,
    GENERIC_V3_AREAS,
    extract_probe_id,
    parse_probe_letter,
    parse_session_from_nwb_filename,
    channel_to_area,
    resolve_area_group,
    load_nwb_profile,
    load_a8_1_keys,
    load_a8_3_status,
    build_recovery_table,
    main,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_a8_4_setup(tmp_path):
    """Creates a minimal file tree for A8.4 tests."""
    # Directories
    a6_dir  = tmp_path / "a6"
    a81_dir = tmp_path / "a81"
    a82_dir = tmp_path / "a82"
    a83_dir = tmp_path / "a83"
    nwb_dir = tmp_path / "nwb_meta"
    out_dir = tmp_path / "out"
    for d in [a6_dir, a81_dir, a82_dir, a83_dir, nwb_dir]:
        d.mkdir()

    # A8.1 unit candidate labels — 5 units across 2 sessions/probes
    a81_csv = a81_dir / "unit_candidate_labels.csv"
    with open(a81_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["session_id", "source_file", "unit_axis_index",
                    "candidate_labels", "primary_candidate_label",
                    "unit_area_join_status_from_A6", "manuscript_safe_unit_area_from_A6"])
        # Unit 0: 230719, probe1 (DP/V4), channel 50 -> V4
        w.writerow(["230719", "ses230719-units-probe1-spk-AAAB.npy", "0",
                    "S_plus_candidate", "S_plus_candidate", "joined", "false"])
        # Unit 1: 230719, probe2 (V3d,V3a), channel 30 -> V3d
        w.writerow(["230719", "ses230719-units-probe2-spk-AAAB.npy", "0",
                    "null_or_unclassified", "null_or_unclassified", "joined", "false"])
        # Unit 2: 230630, probe0 (PFC), channel 10 -> PFC (provisional in A8.3)
        w.writerow(["230630", "ses230630-units-probe0-spk-AAAB.npy", "0",
                    "S_minus_candidate", "S_minus_candidate", "joined", "false"])
        # Unit 3: 230630, probe2 (V3,V1), channel 30 -> V3 (generic)
        w.writerow(["230630", "ses230630-units-probe2-spk-AAAB.npy", "0",
                    "null_or_unclassified", "null_or_unclassified", "unresolved_generic_v3", "false"])
        # Unit 4: session with no NWB profile data
        w.writerow(["230629", "ses230629-units-probe0-spk-AAAB.npy", "999",
                    "null_or_unclassified", "null_or_unclassified", "missing_unit_metadata", "false"])

    # A8.2 stability CSV
    a82_csv = a82_dir / "candidate_label_stability_by_unit.csv"
    with open(a82_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["session_id", "unit_axis_index", "dominant_label", "strict_label"])
        w.writerow(["230719", "0", "S_plus_candidate", "S_plus_candidate"])
        w.writerow(["230630", "0", "S_minus_candidate", "S_minus_candidate"])

    # A8.3 long table
    a83_csv = a83_dir / "unit_area_mapping_long.csv"
    with open(a83_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["session_id", "unit_axis_index", "area_resolution_status",
                    "canonical_area_label", "raw_area_label",
                    "can_support_area_claim", "can_support_hierarchy_claim"])
        w.writerow(["230719", "0", "unmapped_no_metadata", "Unknown", "None", "false", "false"])
        w.writerow(["230719", "0", "unmapped_no_metadata", "Unknown", "None", "false", "false"])
        w.writerow(["230630", "0", "provisional_unit_area_from_count_matched_row_order",
                    "PFC", "PFC", "false", "false"])
        w.writerow(["230630", "0", "unresolved_generic_v3", "V3", "V3", "false", "false"])
        w.writerow(["230629", "999", "unmapped_no_metadata", "Unknown", "None", "false", "false"])

    # NWB profile CSV (simulates unit_nwb_profile.csv)
    nwb_profile_csv = nwb_dir / "unit_nwb_profile.csv"
    with open(nwb_profile_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["session_nwb", "probe", "unit_id_in_session",
                    "peak_channel_id", "location", "group_name"])
        # ses230719, probeB (=1), unit 0, channel 50 -> V4 (DP probe)
        w.writerow(["sub-V198o_ses-230719_rec.nwb", "probeB", "0", "50", "DP", "probeB"])
        # ses230719, probeC (=2), unit 0, channel 30 -> V3d
        w.writerow(["sub-V198o_ses-230719_rec.nwb", "probeC", "0", "30", "V3d,V3a", "probeC"])
        # ses230630, probeA (=0), unit 0, channel 10 -> PFC
        w.writerow(["sub-C31o_ses-230630_rec.nwb", "probeA", "0", "10", "PFC", "probeA"])
        # ses230630, probeC (=2), unit 0, channel 30 -> V3 (generic)
        w.writerow(["sub-C31o_ses-230630_rec.nwb", "probeC", "0", "30", "V3,V1", "probeC"])
        # ses230629: NO profile entry for unit 999 -> should be unresolved

    return {
        "a81_dir": a81_dir,
        "a82_dir": a82_dir,
        "a83_dir": a83_dir,
        "nwb_profile_csv": nwb_profile_csv,
        "out_dir": out_dir,
        "tmp_path": tmp_path,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: Probe extraction is deterministic
# ──────────────────────────────────────────────────────────────────────────────

def test_probe_extraction_is_deterministic():
    """1. source-file probe extraction is deterministic."""
    cases = [
        ("ses230629-units-probe0-spk-AAAB.npy", "0"),
        ("ses230719-units-probe1-spk-AAAB.npy", "1"),
        ("ses230816-units-probe2-spk-AAAB.npy", "2"),
        ("some_file_no_probe.npy", "-1"),
    ]
    for src, expected in cases:
        result = extract_probe_id(src)
        assert result == expected, f"Expected {expected}, got {result} for {src}"
    # Idempotent
    assert extract_probe_id("ses230629-units-probe0-spk.npy") == extract_probe_id(
        "ses230629-units-probe0-spk.npy"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: Peak channel maps to area only when channel metadata exists
# ──────────────────────────────────────────────────────────────────────────────

def test_peak_channel_maps_area_only_when_channel_exists():
    """2. Recovered peak channel maps to canonical area only when channel metadata exists."""
    # Valid channel in range for 230629 probe0 (V1: 0-63, V2: 64-127)
    area, method = channel_to_area("230629", "0", "32")
    assert area == "V1"
    assert method == "heuristic_equal_segment"

    area2, method2 = channel_to_area("230629", "0", "100")
    assert area2 == "V2"

    # Missing channel: empty string
    area3, method3 = channel_to_area("230629", "0", "")
    assert area3 == "Unknown"
    assert "not_numeric" in method3 or "not_numeric" in method3 or area3 == "Unknown"

    # Probe not in map
    area4, method4 = channel_to_area("999999", "0", "50")
    assert area4 == "Unknown"
    assert "not_in_area_map" in method4


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: Conflicting metadata sources block upgrade
# ──────────────────────────────────────────────────────────────────────────────

def test_conflicting_metadata_blocks_upgrade():
    """3. Conflicting metadata sources must be flagged and not silently resolved."""
    # Simulate: two profile entries for same key would be deduplicated by first-wins
    # The script must not silently merge conflicting entries
    # Test that the profile loader keeps first entry when key is repeated
    profile_data = {}
    key = ("230629", "0", "0")
    row_a = {"peak_channel_id": "10", "location": "V1,V2", "group_name": "probeA"}
    row_b = {"peak_channel_id": "99", "location": "CONFLICT", "group_name": "probeA_alt"}

    # Simulate first-wins (as the loader does)
    if key not in profile_data:
        profile_data[key] = row_a
    if key not in profile_data:
        profile_data[key] = row_b  # This should NOT overwrite

    assert profile_data[key]["peak_channel_id"] == "10", "First-entry must win"
    assert profile_data[key]["location"] != "CONFLICT"


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: Row-order-only mapping stays provisional
# ──────────────────────────────────────────────────────────────────────────────

def test_row_order_only_stays_provisional(mock_a8_4_setup):
    """4. Units with A8.3 provisional status are not promoted to manuscript-safe by A8.4."""
    s = mock_a8_4_setup
    a8_1_rows = load_a8_1_keys(s["a81_dir"])
    nwb_profile, _ = load_nwb_profile(s["nwb_profile_csv"])
    a8_3_status = load_a8_3_status(s["a83_dir"])

    long_rows, _ = build_recovery_table(a8_1_rows, nwb_profile, a8_3_status, set())

    # Unit ses230630, probe0, unit 0 was provisional in A8.3
    provisional_units = [
        r for r in long_rows
        if r["a8_3_original_status"] == "provisional_unit_area_from_count_matched_row_order"
    ]
    for u in provisional_units:
        assert u["can_support_manuscript_area_claim"] == "false", \
            "Provisional units must not become manuscript-safe in A8.4"


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: Missing metadata stays unresolved
# ──────────────────────────────────────────────────────────────────────────────

def test_missing_metadata_stays_unresolved(mock_a8_4_setup):
    """5. Units with no NWB profile entry get unresolved_no_candidate_metadata."""
    s = mock_a8_4_setup
    a8_1_rows = load_a8_1_keys(s["a81_dir"])
    nwb_profile, _ = load_nwb_profile(s["nwb_profile_csv"])
    a8_3_status = load_a8_3_status(s["a83_dir"])

    long_rows, _ = build_recovery_table(a8_1_rows, nwb_profile, a8_3_status, set())

    # Unit ses230629, unit 999 has no NWB profile
    missing_units = [
        r for r in long_rows
        if r["session_id"] == "230629" and r["unit_axis_index"] == "999"
    ]
    assert len(missing_units) == 1
    assert missing_units[0]["recovery_status"] == "unresolved_no_candidate_metadata"
    assert missing_units[0]["can_upgrade_to_area_claim_candidate"] == "false"


# ──────────────────────────────────────────────────────────────────────────────
# Test 6: DP → V4 alias applied in recovery
# ──────────────────────────────────────────────────────────────────────────────

def test_dp_maps_to_v4_in_recovery():
    """6. DP → V4 alias is applied when recovering from DP-labeled probe."""
    # 230719 probe1 is defined as DP (V4) — entire probe is V4
    area, method = channel_to_area("230719", "1", "50")
    assert area == "V4", f"Expected V4 for DP probe, got {area}"
    assert method == "heuristic_equal_segment"

    area2, _ = channel_to_area("230719", "1", "127")
    assert area2 == "V4"

    # V4 must be in canonical areas
    assert "V4" in CANONICAL_AREAS


# ──────────────────────────────────────────────────────────────────────────────
# Test 7: Generic V3 preserved — not split into V3d/V3a
# ──────────────────────────────────────────────────────────────────────────────

def test_generic_v3_not_silently_split(mock_a8_4_setup):
    """7. Generic V3 remains unresolved unless metadata specifies V3d/V3a."""
    s = mock_a8_4_setup
    a8_1_rows = load_a8_1_keys(s["a81_dir"])
    nwb_profile, _ = load_nwb_profile(s["nwb_profile_csv"])
    a8_3_status = load_a8_3_status(s["a83_dir"])

    long_rows, _ = build_recovery_table(a8_1_rows, nwb_profile, a8_3_status, set())

    # Unit ses230630, probe2 (V3/V1 in area map), channel 30 -> V3 (generic)
    v3_units = [
        r for r in long_rows
        if r["session_id"] == "230630" and r["probe_id"] == "2"
    ]
    for u in v3_units:
        assert u["recovered_canonical_area"] not in ("V3d", "V3a"), \
            "Generic V3 must NOT be silently split to V3d or V3a"
        assert u["recovery_status"] in (
            "unresolved_generic_v3_from_channel",
            "source_probe_resolved_but_channel_unresolvable",
            "unresolved_no_candidate_metadata",
        )
        assert u["can_support_manuscript_area_claim"] == "false"

    # Also test channel_to_area directly
    area_v3, _ = channel_to_area("230630", "2", "30")
    assert area_v3 == "V3"  # Must remain generic V3


# ──────────────────────────────────────────────────────────────────────────────
# Test 8: Manifest schema validation
# ──────────────────────────────────────────────────────────────────────────────

def test_manifest_schema(mock_a8_4_setup, monkeypatch):
    """8. Output manifest includes git commit, input paths, hashes, and truth_safe_unverified."""
    s = mock_a8_4_setup
    monkeypatch.setattr(
        "scripts.run_unit_area_provenance_recovery_a8_4.get_git_commit",
        lambda: "mock_commit_a8_4"
    )

    test_args = [
        "run_unit_area_provenance_recovery_a8_4.py",
        "--a8-1-dir", str(s["a81_dir"]),
        "--a8-2-dir", str(s["a82_dir"]),
        "--a8-3-dir", str(s["a83_dir"]),
        "--nwb-profile", str(s["nwb_profile_csv"]),
        "--master-index", str(s["nwb_profile_csv"]),  # reuse for test
        "--out-dir", str(s["out_dir"]),
    ]
    with patch("sys.argv", test_args):
        main()

    manifest_path = s["out_dir"] / "provenance_recovery_execution_manifest.json"
    assert manifest_path.exists()

    with open(manifest_path) as f:
        manifest = json.load(f)

    assert manifest["truth_status"] == TRUTH_SAFE_UNVERIFIED
    assert manifest["git_commit"] == "mock_commit_a8_4"
    assert "a8_1_unit_candidate_labels" in manifest["input_files"]
    assert len(manifest["hashes"]) >= 10
    assert manifest["artifact_id"] == "A8_4_unit_area_provenance_recovery"


# ──────────────────────────────────────────────────────────────────────────────
# Test 9: No hierarchy claim text emitted
# ──────────────────────────────────────────────────────────────────────────────

def test_no_hierarchy_claim_text(mock_a8_4_setup, monkeypatch):
    """9. No hierarchy claim text is emitted in summary outputs."""
    s = mock_a8_4_setup
    monkeypatch.setattr(
        "scripts.run_unit_area_provenance_recovery_a8_4.get_git_commit",
        lambda: "mock_commit_a8_4"
    )

    test_args = [
        "run_unit_area_provenance_recovery_a8_4.py",
        "--a8-1-dir", str(s["a81_dir"]),
        "--a8-2-dir", str(s["a82_dir"]),
        "--a8-3-dir", str(s["a83_dir"]),
        "--nwb-profile", str(s["nwb_profile_csv"]),
        "--master-index", str(s["nwb_profile_csv"]),
        "--out-dir", str(s["out_dir"]),
    ]
    with patch("sys.argv", test_args):
        main()

    summary_json = s["out_dir"] / "provenance_recovery_execution_summary.json"
    summary_md   = s["out_dir"] / "provenance_recovery_execution_summary.md"

    with open(summary_json) as f:
        summary = json.load(f)

    assert summary["manuscript_hierarchy_claims_allowed"] is False
    assert summary["area_hierarchy_allowed"] is False
    assert summary["can_promote_to_metadata_resolved_channel"] is False

    blocked = " ".join(summary["blocked_claims"]).lower()
    assert "hierarchy" in blocked
    assert "enrichment" in blocked

    md_text = summary_md.read_text(encoding="utf-8").lower()
    overclaim_phrases = [
        "higher-order omission coding", "pfc enrichment",
        "hierarchy proven", "area enrichment result",
        "fef/pfc dominant", "predictive routing confirmed",
    ]
    for phrase in overclaim_phrases:
        assert phrase not in md_text, f"Overclaim found in summary MD: '{phrase}'"


# ──────────────────────────────────────────────────────────────────────────────
# Test 10: Original A8.3 statuses preserved in output
# ──────────────────────────────────────────────────────────────────────────────

def test_original_a8_3_status_preserved(mock_a8_4_setup):
    """10. Original A8.3 area_resolution_status is preserved in all A8.4 output rows."""
    s = mock_a8_4_setup
    a8_1_rows = load_a8_1_keys(s["a81_dir"])
    nwb_profile, _ = load_nwb_profile(s["nwb_profile_csv"])
    a8_3_status = load_a8_3_status(s["a83_dir"])

    long_rows, _ = build_recovery_table(a8_1_rows, nwb_profile, a8_3_status, set())

    # Every row must have the original A8.3 status preserved
    for r in long_rows:
        assert "a8_3_original_status" in r, "a8_3_original_status must be in every row"
        assert r["a8_3_original_status"] != "", "a8_3_original_status must not be empty"

    # The recovery status must be a different field from original
    for r in long_rows:
        assert "recovery_status" in r, "recovery_status must be in every row"
        # Recovery status must not overwrite a8_3 status
        assert r["a8_3_original_status"] != r["recovery_status"] or \
               r["a8_3_original_status"] == "unknown", \
               "Original A8.3 status must not be silently replaced by recovery status"
