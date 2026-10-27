"""Gate 19: a frozen-validated function fails the harness as soon as its body changes."""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
# `scripts/` ships in no wheel, so appending is enough to import the gate.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # needed: the installed-wheel run clears pythonpath

from scripts.harness_gate import check_frozen_validated, frozen_body_hash  # noqa: E402

BODY = '''
class Box:
    def width(self, n):
        """Docstring."""
        # A comment.
        return n + 1
'''


def _repo(tmp_path, source=BODY, digest=None, killed_by=("tests/test_box.py::test_width",)):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "box.py").write_text(source, encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_box.py").write_text("def test_width():\n    pass\n",
                                                   encoding="utf-8")
    (tmp_path / "artifacts").mkdir()
    entry = {
        "file": "pkg/box.py",
        "qualname": "Box.width",
        "sha256": digest or frozen_body_hash(BODY, "Box.width"),
        "verified_at": "0" * 40,
        "killed_by": list(killed_by),
    }
    (tmp_path / "artifacts" / "process").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts" / "process" / "frozen_validated.json").write_text(
        json.dumps({"functions": [entry]}), encoding="utf-8")
    return tmp_path


def test_the_register_on_this_tree_passes():
    assert check_frozen_validated() == []


def test_an_unchanged_body_passes(tmp_path):
    assert check_frozen_validated(_repo(tmp_path)) == []


def test_a_changed_body_fails(tmp_path):
    violations = check_frozen_validated(_repo(tmp_path, BODY.replace("n + 1", "n + 2")))
    assert len(violations) == 1 and "body changed" in violations[0], violations


def test_docstrings_comments_and_layout_do_not_count(tmp_path):
    edited = (BODY.replace('"""Docstring."""', '"""Another docstring."""')
              .replace("# A comment.", "# Another comment.")
              .replace("return n + 1", "return (n\n                + 1)"))
    assert frozen_body_hash(edited, "Box.width") == frozen_body_hash(BODY, "Box.width")


def test_a_missing_function_or_killing_test_fails(tmp_path):
    violations = check_frozen_validated(_repo(
        tmp_path, BODY.replace("def width", "def height"),
        killed_by=("tests/test_box.py::test_gone",)))
    assert any("no such function" in v for v in violations), violations
    assert any("test_gone does not exist" in v for v in violations), violations


REBOUND = BODY + "\nclass Box:\n    def width(self, n):\n        return n + 2\n"


def test_a_rebound_name_hashes_the_binding_that_runs(tmp_path):
    """The import binds the last definition; hashing the first verifies code that never runs."""
    digest = frozen_body_hash(BODY, "Box.width")
    violations = check_frozen_validated(_repo(tmp_path, REBOUND, digest=digest))
    assert len(violations) == 1 and "body changed" in violations[0], violations


@pytest.mark.parametrize(
    "node_id",
    [
        "tests/test_box.py::WrongClass::test_width",
        "tests/test_box.py::WrongClass::test_width[param]",
    ],
)
def test_a_killing_test_naming_the_wrong_class_fails(tmp_path, node_id):
    """A leaf-name match is not the test: it names one that was never collected."""
    violations = check_frozen_validated(_repo(tmp_path, killed_by=(node_id,)))
    assert len(violations) == 1 and "does not exist" in violations[0], violations


def test_an_empty_register_fails(tmp_path):
    repo = _repo(tmp_path)
    for empty in ('{"functions": []}', '{"functions": {}}'):
        (repo / "artifacts" / "process" / "frozen_validated.json").write_text(empty, encoding="utf-8")
        assert check_frozen_validated(repo) != [], empty
