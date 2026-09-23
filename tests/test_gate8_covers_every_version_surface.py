"""Gate 8 holds the prose install surfaces to the interpreter set the files declare.

`README.md` and `docs/install.md` state the Python floor and the tested interpreters, and the
gate once read neither: `docs/install.md` was corrected by hand because nothing mechanical
held it. Each case copies the five surfaces into a scratch root and skews exactly one.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts.harness_gate import check_python_floor_consistency  # noqa: E402

SURFACES = (
    "pyproject.toml",
    ".readthedocs.yaml",
    ".github/workflows/workflow.yml",
    "README.md",
    "docs/install.md",
)


@pytest.fixture
def scratch(tmp_path):
    for rel in SURFACES:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / rel, target)
    return tmp_path


def _skew(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (rel, old)
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_the_pristine_surfaces_agree(scratch):
    assert check_python_floor_consistency(scratch) == []


@pytest.mark.parametrize("rel", ["README.md", "docs/install.md"])
def test_a_skewed_floor_fails(scratch, rel):
    _skew(scratch, rel, "Requires Python **3.12 or newer**", "Requires Python **3.11 or newer**")
    violations = check_python_floor_consistency(scratch)
    assert any("PYTHON_DOC_FLOOR_SKEW" in v and rel in v for v in violations), violations


@pytest.mark.parametrize("rel", ["README.md", "docs/install.md"])
def test_a_skewed_tested_set_fails(scratch, rel):
    _skew(scratch, rel, "Tested in CI on 3.12, 3.13 and 3.14.", "Tested in CI on 3.12 and 3.14.")
    violations = check_python_floor_consistency(scratch)
    assert any("PYTHON_DOC_CI_SKEW" in v and rel in v for v in violations), violations


@pytest.mark.parametrize("rel", ["README.md", "docs/install.md"])
def test_a_surface_that_stops_stating_the_floor_fails(scratch, rel):
    _skew(scratch, rel, "Requires Python **3.12 or newer**", "Requires a recent Python")
    violations = check_python_floor_consistency(scratch)
    assert any("does not state the Python floor" in v and rel in v for v in violations), violations
