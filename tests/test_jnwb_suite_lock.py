"""scripts/jnwb_suite.sh runs its pytest command through the machine suite lock when the lock exists, and says which."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "jnwb_suite.sh"

FAKE_LOCK = """\
import json, os, subprocess, sys
argv = sys.argv[1:]
with open(os.environ["FAKE_LOCK_RECORD"], "w", encoding="utf-8") as fh:
    json.dump(argv, fh)
cmd = argv[argv.index("--") + 1:]
sys.exit(subprocess.call(cmd))
"""


def _bash():
    """Git for Windows bash; a bare `bash` can resolve to the WSL launcher."""
    if sys.platform != "win32":
        return "bash"
    git_bash = Path("C:/Program Files/Git/usr/bin/bash.exe")
    if not git_bash.exists():
        pytest.skip("Git for Windows bash not found")
    return git_bash.as_posix()


def _git(repo, *args):
    return subprocess.run(
        ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", *args],
        cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()


DOC_FORM_TESTS = ("test_changelog_fragments.py", "test_docs_form_gate.py", "test_documentation_form.py")


def _fixture_repo(root, passes, doc_form_failing=None):
    """A committed repo: the files jnwb_suite.sh calls, the three doc-form test files, and one test
    that passes or fails. `doc_form_failing` names the doc-form file whose test fails."""
    repo = root / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "scripts" / "reconstruct_state.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    verdict = "assert True" if passes else "assert False"
    (repo / "tests" / "test_tiny.py").write_text(f"def test_tiny():\n    {verdict}\n", encoding="utf-8")
    for name in DOC_FORM_TESTS:
        verdict = "assert False" if name == doc_form_failing else "assert True"
        (repo / "tests" / name).write_text(f"def test_doc_form():\n    {verdict}\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "scripts", "tests")
    _git(repo, "commit", "-q", "-m", "fixture")
    return repo


def _run(tmp_path, repo, lock, home=None):
    """Run jnwb_suite.sh on the fixture repo; `lock` None leaves JNWB_SUITE_LOCK unset."""
    record = tmp_path / "lock_argv.json"
    log = tmp_path / "suite.log"
    env = dict(os.environ, FAKE_LOCK_RECORD=record.as_posix())
    # The script's `git` calls must resolve under bash. A non-login Git bash inherits Windows
    # PATH and drops the profile's /mingw64/bin; Git\bin also maps to /bin under MSYS and is not
    # a working git there, so prefer mingw64\bin and cmd ahead of bin.
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not on PATH")
    git_dirs = []
    for root in Path(git).resolve().parents:
        for sub in ("mingw64/bin", "cmd", "bin"):
            d = root / Path(sub)
            if (d / "git.exe").is_file() and str(d) not in git_dirs:
                git_dirs.append(str(d))
    path_key = next((k for k in env if k.upper() == "PATH"), "PATH")
    env[path_key] = os.pathsep.join([*git_dirs, env.get(path_key, "")])
    env.pop("JNWB_SUITE_LOCK", None)
    if lock is not None:
        env["JNWB_SUITE_LOCK"] = lock
    if home is not None:
        env["HOME"] = home
    proc = subprocess.run(
        [_bash(), SCRIPT.as_posix(), repo.as_posix(), log.as_posix()],
        env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
        stdin=subprocess.DEVNULL, timeout=900,
    )
    record_argv = json.loads(record.read_text(encoding="utf-8")) if record.exists() else None
    return proc, log, record_argv


def _lock_line(stdout):
    lines = [line for line in stdout.splitlines() if line.startswith("suite lock: ")]
    assert len(lines) == 1, f"expected one 'suite lock:' line, got {lines!r}"
    return lines[0]


def test_missing_lock_runs_pytest_directly_and_says_so(tmp_path):
    repo = _fixture_repo(tmp_path, passes=True)
    lock = (tmp_path / "absent" / "suite_lock.py").as_posix()
    proc, log, record = _run(tmp_path, repo, lock)

    assert _lock_line(proc.stdout) == f"suite lock: none ({lock} not found)", proc.stdout
    assert record is None, "no lock exists, so no lock may be called"
    assert "4 passed" in log.read_text(encoding="utf-8")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_present_lock_runs_the_pytest_command_through_it(tmp_path):
    repo = _fixture_repo(tmp_path, passes=True)
    lock_file = tmp_path / "suite_lock.py"
    lock_file.write_text(FAKE_LOCK, encoding="utf-8")
    lock = lock_file.as_posix()
    proc, log, record = _run(tmp_path, repo, lock)

    assert _lock_line(proc.stdout) == f"suite lock: {lock}", proc.stdout
    assert record is not None, "the lock was not called"
    assert record[:3] == ["--label", "jnwb", "--"], record
    pytest_cmd = record[3:]
    assert pytest_cmd[:3] == ["python", "-m", "pytest"], pytest_cmd
    assert "tests/" in pytest_cmd, pytest_cmd
    assert "4 passed" in log.read_text(encoding="utf-8")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    head = _git(repo, "rev-parse", "HEAD")
    stamp = Path(_git(repo, "rev-parse", "--git-dir")) / "jnwb_suite_ok"
    assert (repo / stamp).read_text(encoding="utf-8").strip() == head, "stamp must hold HEAD on a pass"


def test_failing_tests_pass_through_the_lock_and_a_doc_form_failure_stops_before_it(tmp_path):
    repo = _fixture_repo(tmp_path, passes=False)
    lock_file = tmp_path / "suite_lock.py"
    lock_file.write_text(FAKE_LOCK, encoding="utf-8")
    proc, log, record = _run(tmp_path, repo, lock_file.as_posix())

    assert _lock_line(proc.stdout).startswith("suite lock: "), proc.stdout
    assert record is not None and record[:3] == ["--label", "jnwb", "--"], record
    assert "1 failed" in log.read_text(encoding="utf-8")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    stamp = repo / _git(repo, "rev-parse", "--git-dir") / "jnwb_suite_ok"
    assert not stamp.exists(), "a failing run must not write the push stamp"

    # A planted bad changelog fragment fails the doc-form stage, so the full suite never starts.
    planted_dir = tmp_path / "planted"
    planted_dir.mkdir()
    planted = _fixture_repo(planted_dir, passes=True, doc_form_failing="test_changelog_fragments.py")
    proc, _, record = _run(planted_dir, planted, lock_file.as_posix())
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "doc-form tests failed; the full suite did not run" in proc.stdout, proc.stdout
    assert record is None, "the full suite started after a doc-form failure"
    assert not (planted / ".git" / "jnwb_suite_ok").exists(), "a failed doc-form run must not stamp"


def test_default_lock_is_the_home_lock_when_the_variable_is_unset(tmp_path):
    repo = _fixture_repo(tmp_path, passes=True)
    home = tmp_path / "home"
    lock_file = home / ".claude" / "bin" / "suite_lock.py"
    lock_file.parent.mkdir(parents=True)
    lock_file.write_text(FAKE_LOCK, encoding="utf-8")
    proc, log, record = _run(tmp_path, repo, None, home=home.as_posix())

    # bash expands $HOME as /c/... for the same file, so compare the tail and the lock's own record.
    assert _lock_line(proc.stdout).endswith("/.claude/bin/suite_lock.py"), proc.stdout
    assert record is not None and record[:3] == ["--label", "jnwb", "--"], record
    assert proc.returncode == 0, proc.stdout + proc.stderr
