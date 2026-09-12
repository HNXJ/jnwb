"""Fixture setup for NWB workflow tutorials (not a data-access API)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from jnwb.testing.nwb_fixtures import (
    CODE_LABEL_A,
    CODE_LABEL_B,
    TASK_TABLE,
    canonical_co_resident_options,
    write_synth_nwb,
)


def build_canonical_fixture() -> tuple[Path, object]:
    """Write the co-resident synthetic NWB to a temp file; return path and receipt."""
    tmp = Path(tempfile.mkdtemp(prefix="jnwb_tutorial_"))
    path = tmp / "canonical.nwb"
    receipt = write_synth_nwb(path, canonical_co_resident_options())
    return path, receipt


__all__ = [
    "CODE_LABEL_A",
    "CODE_LABEL_B",
    "TASK_TABLE",
    "build_canonical_fixture",
]
