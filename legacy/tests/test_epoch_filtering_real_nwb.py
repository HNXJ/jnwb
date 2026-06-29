"""
Test epoch filtering on real NWB files (13 sessions).

Validates that get_epochs() correctly filters by phase/condition after type-mismatch fix.
"""

import logging
from pathlib import Path
import numpy as np
import pytest

from jnwb import OmissionSession

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

NWB_DIR = Path("D:/analysis/nwb")

# Get list of all NWB files
NWB_FILES = sorted(list(NWB_DIR.glob("*.nwb")))
SESSION_IDS = [f.stem.split("ses-")[1].split("_")[0] for f in NWB_FILES if "ses-" in f.stem]

log.info(f"Found {len(NWB_FILES)} NWB files: {SESSION_IDS}")


class TestEpochFiltering:
    """Test epoch filtering across all sessions."""

    def test_aaab_phase2_count(self):
        """AAAB condition, p1 (phase=2) should be filterable and non-zero for all sessions."""
        total_count = 0
        session_counts = {}

        for nwb_path in NWB_FILES:
            session = OmissionSession(str(nwb_path))
            epochs = session.get_epochs(phase=2, condition='AAAB', correct_only=True)
            count = len(epochs)
            session_id = nwb_path.stem.split("ses-")[1].split("_")[0]
            session_counts[session_id] = count
            total_count += count

            assert count > 0, f"Session {session_id}: AAAB phase=2 returned 0 rows!"
            log.info(f"  Session {session_id}: {count} AAAB p1 epochs")

        log.info(f"Total AAAB p1 epochs across 13 sessions: {total_count}")
        # AAAB (conditions 1 & 2) is a subset of all conditions
        # 10968 is the total for ALL conditions across all phases
        assert total_count > 0, f"Expected >0 total, got {total_count}"
        assert total_count >= 2500, f"Expected at least 2500, got {total_count}"
        assert all(count > 0 for count in session_counts.values()), f"Some sessions have zero: {session_counts}"
        log.info(f"  Per-session range: {min(session_counts.values())}-{max(session_counts.values())}")

    def test_all_conditions_phase2(self):
        """All conditions at p1 (phase=2) should exist and be countable."""
        conditions = ['AAAB', 'AXAB', 'AAXB', 'AAAX', 'BBBA', 'BXBA', 'BBXA', 'BBBX', 'RRRR', 'RXRR', 'RRXR', 'RRRX']

        for nwb_path in NWB_FILES[:1]:  # Test first session for speed
            session = OmissionSession(str(nwb_path))
            session_id = nwb_path.stem.split("ses-")[1].split("_")[0]

            for cond in conditions:
                epochs = session.get_epochs(phase=2, condition=cond, correct_only=True)
                assert len(epochs) > 0, f"Session {session_id}: {cond} phase=2 returned 0 rows!"
                log.info(f"  {cond}: {len(epochs)} epochs")

    def test_phase_distribution(self):
        """All phases (2-5 for p1-p4) should be filterable."""
        nwb_path = NWB_FILES[0]
        session = OmissionSession(str(nwb_path))

        phase_counts = {}
        for phase in [2, 3, 4, 5]:
            epochs = session.get_epochs(phase=phase, correct_only=True)
            count = len(epochs)
            phase_counts[phase] = count
            assert count > 0, f"Phase {phase} returned 0 rows!"
            log.info(f"  Phase {phase}: {count} epochs")

        # All phases should have similar counts
        counts = list(phase_counts.values())
        assert all(c >= counts[0] * 0.8 for c in counts), f"Uneven phase distribution: {phase_counts}"

    def test_correctness_filtering(self):
        """Correct trials should differ from all trials."""
        nwb_path = NWB_FILES[0]
        session = OmissionSession(str(nwb_path))

        all_epochs = session.get_epochs(phase=2, condition='AAAB', correct_only=False)
        correct_epochs = session.get_epochs(phase=2, condition='AAAB', correct_only=True)

        log.info(f"  All trials: {len(all_epochs)}")
        log.info(f"  Correct trials: {len(correct_epochs)}")

        assert len(correct_epochs) <= len(all_epochs)
        assert len(correct_epochs) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
