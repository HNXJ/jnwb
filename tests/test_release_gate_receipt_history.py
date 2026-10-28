"""The receipt's history read follows the move to artifacts/process/.

The closure receipt was committed at its old path, and the commit that recorded its finished row
deleted that item from the todo stack. Moving the file must not hide that commit from the gate:
a read that starts at the move sees only the move, so the recording commit is never checked.
"""
from __future__ import annotations

import ast
import os
import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # needed: the installed-wheel run clears pythonpath

from scripts.release_gate import _finished_row_history  # noqa: E402
from tests.test_release_requires_an_empty_open_stack import (  # noqa: E402
    DEFERRED, _RECEIPT, _commit, _git, _item, _repository)

OLD = "artifacts/blocker_fixpoint_receipt.md"
NEW = "artifacts/process/blocker_fixpoint_receipt.md"


def test_the_recording_commit_before_the_move_is_read(tmp_path):
    root, passed = _repository(tmp_path)
    (root / OLD).write_text(_RECEIPT.format(commit=passed, found=0)
                            + "| finished after the pass | 99-921 |\n", encoding="utf-8")
    todo = root / "artifacts" / "todo_stack.md"
    todo.write_text(todo.read_text(encoding="utf-8").replace(_item("99-921", DEFERRED), ""),
                    encoding="utf-8")
    _commit(root, "record the closure pass and delete 99-921")
    (root / "artifacts" / "process").mkdir(parents=True)
    _git(root, "mv", OLD, NEW)
    head = _commit(root, "move the receipt to artifacts/process/")
    assert _finished_row_history(root, passed, head, {"99-921"}, {"99-921"}) == []


def test_a_row_extended_after_the_move_is_a_second_write(tmp_path):
    root, passed = _repository(tmp_path)
    (root / OLD).write_text(_RECEIPT.format(commit=passed, found=0)
                            + "| finished after the pass | 99-921 |\n", encoding="utf-8")
    todo = root / "artifacts" / "todo_stack.md"
    todo.write_text(todo.read_text(encoding="utf-8").replace(_item("99-921", DEFERRED), ""),
                    encoding="utf-8")
    _commit(root, "record the closure pass and delete 99-921")
    (root / "artifacts" / "process").mkdir(parents=True)
    _git(root, "mv", OLD, NEW)
    _commit(root, "move the receipt to artifacts/process/")
    moved = root / NEW
    moved.write_text(moved.read_text(encoding="utf-8").replace("99-921 |", "99-921, 99-922 |"),
                     encoding="utf-8")
    assert "99-922" in moved.read_text(encoding="utf-8"), "fixture must extend the row"
    head = _commit(root, "extend the finished row after the move")
    found = _finished_row_history(root, passed, head, {"99-921", "99-922"}, {"99-921"})
    assert any("changed in 2 commit(s)" in v for v in found), found


RELEASE_GATE = REPO_ROOT / "scripts" / "release_gate.py"


def _stub_venv(monkeypatch, tmp_path, *, with_jnwb: bool) -> list:
    """Stub subprocess.run for the venv steps. The site-packages it reports holds jnwb only if asked."""
    purelib = tmp_path / "isolated_venv" / "Lib" / "site-packages"
    if with_jnwb:
        (purelib / "jnwb").mkdir(parents=True)
        (purelib / "jnwb" / "__init__.py").write_text("", encoding="utf-8")
    calls = []

    def fake_run(args, **kwargs):
        calls.append((list(args), kwargs))
        stdout = str(purelib) if "sysconfig" in " ".join(args) else ""
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_the_isolated_venv_install_runs_without_pythonpath(tmp_path, monkeypatch):
    from scripts.release_gate import install_wheel_in_venv

    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    assert os.environ["PYTHONPATH"] == str(REPO_ROOT), "fixture must set PYTHONPATH"
    calls = _stub_venv(monkeypatch, tmp_path, with_jnwb=True)
    venv_python, _ = install_wheel_in_venv(tmp_path / "isolated_venv", tmp_path / "jnwb.whl")
    inside = [(args, kwargs) for args, kwargs in calls if args[0] == venv_python]
    assert len(inside) >= 4, inside
    for args, kwargs in inside:
        assert kwargs.get("env") is not None and "PYTHONPATH" not in kwargs["env"], args


def test_the_install_refuses_when_the_venv_has_no_jnwb(tmp_path, monkeypatch):
    from scripts.release_gate import install_wheel_in_venv

    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    _stub_venv(monkeypatch, tmp_path, with_jnwb=False)
    with pytest.raises(SystemExit, match="jnwb is not installed"):
        install_wheel_in_venv(tmp_path / "isolated_venv", tmp_path / "jnwb.whl")


def test_every_subprocess_run_on_the_venv_python_names_its_environment():
    tree = ast.parse(RELEASE_GATE.read_text(encoding="utf-8"))
    venv_calls = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and node.args and ast.unparse(node.func) == "subprocess.run"):
            continue
        argv = node.args[0]
        if isinstance(argv, ast.List) and any(isinstance(e, ast.Name) and e.id == "venv_python"
                                              for e in argv.elts):
            venv_calls.append(node)
    assert len(venv_calls) >= 6, f"found {len(venv_calls)} venv_python calls"
    for node in venv_calls:
        env = {kw.arg: ast.unparse(kw.value) for kw in node.keywords}.get("env")
        assert env in {"isolated_env()", "smoke_env", "tutorial_env", "env"}, (node.lineno, env)
