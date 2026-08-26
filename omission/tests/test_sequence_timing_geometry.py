"""P0 regression guard for the 2026-08-25 slot-timing defect.

Three Antigravity-authored F04 scripts (compute_predictable_vs_random_omission_decoding.py,
compute_sequence_rsa_and_multimodal_fusion.py, and a matched-contrast script that imported from
the first) locally duplicated a wrong SLOT_ONSETS_MS = {p2: 1062, p3: 1593, p4: 2124} -- 531ms
spacing, i.e. assuming presentations are back-to-back with no delay. The canonical timing
(sequence_layout.EPOCH_ONSETS_MS, used by the trusted leakage-safe pipeline) is 1031ms spacing
(531ms presentation + 500ms delay): p1=0, p2=1031, p3=2062, p4=3093.

The buggy p4 window [2124, 2655) sampled ~88% of the real p3 presentation, not the p4 omission
slot -- this is what produced the spurious near-1.0 "omission content" decoding accuracy that
triggered this investigation. See artifacts/.lab/fig04-timing-correction-20260825.json and
outputs/classification/fig04_timing_correction_receipt.json for the full incident record.

This test guards two things: (1) the canonical geometry itself never silently drifts, and
(2) no live script re-derives or duplicates slot timing instead of importing it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS

REPO_ROOT = Path(__file__).resolve().parents[2]
OA_ROOT = REPO_ROOT / "omission"

ALLOWED_DIRS = {
    "scripts/historical",
    "scripts/archive_oneoff",
    "context/archive",
    "legacy",
    "outputs",  # receipts documenting the incident itself, not live code
    "artifacts",  # .lab graph nodes documenting the incident
    "context/handoff",  # dated handoff snapshots, not live code
}

# The specific wrong literals from the defect, plus the tell-tale 531ms-spacing pattern.
BAD_LITERAL_PATTERNS = [
    re.compile(r"\b1062\.0\b"),
    re.compile(r"\b1593\.0\b"),
    re.compile(r"\b2124\.0\b"),
]

LIVE_SEARCH_DIRS = ["scripts", "jnwb_ext", "tests"]


def _is_allowed(path: Path) -> bool:
    rel = path.relative_to(OA_ROOT).as_posix()
    return any(rel.startswith(allowed) for allowed in ALLOWED_DIRS)


def _find_hits(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern in BAD_LITERAL_PATTERNS:
            if pattern.search(line):
                hits.append(f"{lineno}: {line.strip()}")
                break
    return hits


class TestCanonicalSequenceGeometry:
    def test_epoch_onsets_match_the_established_task_geometry(self):
        assert EPOCH_ONSETS_MS["p1"] == 0.0
        assert EPOCH_ONSETS_MS["p2"] == 1031.0
        assert EPOCH_ONSETS_MS["p3"] == 2062.0
        assert EPOCH_ONSETS_MS["p4"] == 3093.0

    def test_presentation_slots_are_evenly_spaced_by_a_full_presentation_plus_delay_cycle(self):
        spacing_p1_p2 = EPOCH_ONSETS_MS["p2"] - EPOCH_ONSETS_MS["p1"]
        spacing_p2_p3 = EPOCH_ONSETS_MS["p3"] - EPOCH_ONSETS_MS["p2"]
        spacing_p3_p4 = EPOCH_ONSETS_MS["p4"] - EPOCH_ONSETS_MS["p3"]
        assert spacing_p1_p2 == spacing_p2_p3 == spacing_p3_p4 == 1031.0

    def test_presentation_and_delay_durations(self):
        presentation_dur = EPOCH_ONSETS_MS["d1"] - EPOCH_ONSETS_MS["p1"]
        delay_dur = EPOCH_ONSETS_MS["p2"] - EPOCH_ONSETS_MS["d1"]
        assert presentation_dur == 531.0
        assert delay_dur == 500.0


class TestNoLocallyDuplicatedTimingConstants:
    def test_no_live_script_hardcodes_the_wrong_531ms_spaced_slot_onsets(self):
        violations: dict[str, list[str]] = {}
        for dirname in LIVE_SEARCH_DIRS:
            root = OA_ROOT / dirname
            if not root.is_dir():
                continue
            for path in root.rglob("*.py"):
                if _is_allowed(path):
                    continue
                hits = _find_hits(path)
                if hits:
                    violations[str(path.relative_to(REPO_ROOT))] = hits
        assert not violations, (
            f"live script(s) contain the retracted 1062/1593/2124ms slot-onset literals from the "
            f"2026-08-25 timing defect: {violations}"
        )

    @pytest.mark.parametrize("module_path,attr", [
        ("omission.scripts.compute_predictable_vs_random_omission_decoding", "SLOT_ONSETS_MS"),
        ("omission.scripts.compute_sequence_rsa_and_multimodal_fusion", "SLOT_ONSETS_MS"),
    ])
    def test_script_slot_onsets_match_canonical_source(self, module_path, attr):
        import importlib
        import sys

        scripts_dir = str(OA_ROOT / "scripts")
        added = scripts_dir not in sys.path
        if added:
            sys.path.insert(0, scripts_dir)
        try:
            mod = importlib.import_module(module_path.rsplit(".", 1)[-1])
        finally:
            if added:
                sys.path.remove(scripts_dir)
        onsets = getattr(mod, attr)
        for slot in ("p2", "p3", "p4"):
            assert onsets[slot] == EPOCH_ONSETS_MS[slot], (
                f"{module_path}.{attr}[{slot!r}] = {onsets[slot]} does not match canonical "
                f"EPOCH_ONSETS_MS[{slot!r}] = {EPOCH_ONSETS_MS[slot]}"
            )
