"""`scripts/bump_version.py` moves every surface the version tests read.

The 0.2.9 bump moved `__version__` by hand and left the release date, the checkout version in
`README.md`, the `SKILLS_URL` example and the import profile at 0.2.8. The script takes its
surface list from `scripts/version_surfaces.py`, which the tests import too; these tests run it
on a temporary copy and check the copy with that module's own `problems`.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# `append`, never `insert(0, ...)`: see tests/test_import_profile_receipt.py.
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from scripts import bump_version, version_surfaces as vs  # noqa: E402

NEW_VERSION, NEW_DATE = "9.8.7", "2031-02-03"
# Fixed before any seed patches the list, so a copy always carries every surface.
COPIED = {vs.INIT, vs.PROFILE, vs.BREAKDOWN, *(r for r, _ in vs.PINNED_CLAIMS)}


def _digest(root: Path) -> dict[str, str]:
    return {rel: hashlib.sha256((root / rel).read_bytes()).hexdigest() for rel in sorted(COPIED)}


def _copy(dest: Path) -> Path:
    keep = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(ROOT / "jnwb", dest / "jnwb", ignore=keep)
    shutil.copytree(ROOT / "scripts", dest / "scripts", ignore=keep)
    for rel in COPIED:
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dest / rel)
    return dest


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "scripts" / "bump_version.py"), "--root", str(root), *args],
        capture_output=True, text=True, cwd=root)


@pytest.fixture(scope="module")
def bumped(tmp_path_factory):
    """One real bump of a copy whose README is CRLF; the import profile is measured once."""
    before = _digest(ROOT)
    root = _copy(tmp_path_factory.mktemp("bump"))
    readme = root / "README.md"
    readme.write_bytes(readme.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert vs.problems(root) == [], "the copy must start consistent"
    done = _run(root, NEW_VERSION, "--date", NEW_DATE, "--import-runs", "1")
    yield root, done
    assert _digest(ROOT) == before, "the repository's own surfaces changed"


def test_the_bump_moves_every_surface(bumped):
    root, done = bumped
    assert done.returncode == 0, done.stdout + done.stderr
    assert vs.read_init(root) == (NEW_VERSION, NEW_DATE)
    assert vs.problems(root) == []
    assert NEW_VERSION in (root / vs.PROFILE).read_text(encoding="utf-8")


def test_line_endings_are_kept(bumped):
    root, _ = bumped
    data = (root / "README.md").read_bytes()
    assert data.count(b"\r\n") == data.count(b"\n") > 0, "a bare LF entered a CRLF file"
    assert b"\r" not in (root / vs.INIT).read_bytes()


def test_the_original_is_untouched_and_a_dry_run_writes_nothing(tmp_path):
    root = _copy(tmp_path)
    before = _digest(root)
    done = _run(root, NEW_VERSION, "--date", NEW_DATE, "--dry-run")
    assert done.returncode == 0, done.stderr
    assert "README.md" in done.stdout and "nothing written" in done.stdout
    assert _digest(root) == before


@pytest.mark.parametrize("version", ["1.2", "x.y.z", "1.2.3rc1", ""])
def test_a_version_that_does_not_parse_is_refused(tmp_path, version):
    root = _copy(tmp_path)
    before = _digest(root)
    done = _run(root, version, "--date", NEW_DATE, "--dry-run")
    assert done.returncode != 0 and "not a release version" in done.stderr
    assert _digest(root) == before


def test_a_lower_version_and_a_bad_date_are_refused(tmp_path):
    root = _copy(tmp_path)
    before = _digest(root)
    low = _run(root, "0.0.1", "--date", NEW_DATE, "--dry-run")
    assert low.returncode != 0 and "lower than" in low.stderr
    for date in ("2031-13-40", "20311005"):
        bad = _run(root, NEW_VERSION, "--date", date, "--dry-run")
        assert bad.returncode != 0 and "YYYY-MM-DD" in bad.stderr, date
    assert _digest(root) == before


def test_an_anchor_that_is_missing_is_refused(tmp_path):
    root = _copy(tmp_path)
    readme = root / "README.md"
    readme.write_bytes(readme.read_bytes().replace(b"This checkout is", b"This tree is"))
    done = _run(root, NEW_VERSION, "--date", NEW_DATE, "--dry-run")
    assert done.returncode != 0 and "expected 1 of" in done.stderr


def test_seed_a_surface_missing_from_the_list_is_caught(tmp_path, monkeypatch):
    """Drop `README.md` from the list the script uses: the unpatched check must say so.

    Pristine first: with the full list the same steps leave no README problem, so the failure
    below comes from the dropped entry and not from the harness around it.
    """
    full = list(vs.PINNED_CLAIMS)

    def run_plan(root: Path) -> list[str]:
        for path, data in bump_version.plan(root, NEW_VERSION, NEW_DATE).items():
            path.write_bytes(data)
        return [p for p in vs.problems(root) if p.startswith("README.md")]

    assert run_plan(_copy(tmp_path / "pristine")) == []
    before = _digest(ROOT)
    monkeypatch.setattr(vs, "PINNED_CLAIMS", [c for c in full if c[0] != "README.md"])
    seeded = _copy(tmp_path / "seeded")
    for path, data in bump_version.plan(seeded, NEW_VERSION, NEW_DATE).items():
        path.write_bytes(data)
    monkeypatch.setattr(vs, "PINNED_CLAIMS", full)
    left = [p for p in vs.problems(seeded) if p.startswith("README.md")]
    assert left, "a surface dropped from the list was not detected"
    assert vs.PINNED_CLAIMS == full and _digest(ROOT) == before
