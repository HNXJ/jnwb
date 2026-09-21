"""The derived cache is excluded by path, so no suffix can carry it into the index.

Recorded as P-10. ``artifacts/developer/.cache/`` held 6.7 GB across 88 files, excluded only by
the blanket extension rules: ``*.pkl`` matched 66 of those files and ``*.json`` the other 22. The
directory itself matched nothing. A cache file written with any other suffix -- a ``.tmp``, a
partial write, a lock -- was untracked and visible in ``git status``, one careless ``git add -A``
away from the index.

The repair must not be "add the missing extension". That is the same defect with a longer list,
and the next suffix escapes it again. So these tests pin the shape of the rule and not only its
effect: the cache is unreachable whatever the suffix, and the rule reaching it is a path rule. A
mutant that swaps the path rule for ``*.tmp`` satisfies "the probe is ignored" and is rejected
here, because satisfying that alone is what P-10 already was.

The extension rules stay, and are tested to stay: they cover ``*.pkl`` and ``*.json`` everywhere
else in the repository, which a rule anchored at the cache path cannot.

Nothing here writes inside the repository. The end-to-end ``git status`` check builds a throwaway
repository from this one's ``.gitignore`` bytes, because creating the cache directory in the real
worktree would make ``artifacts/developer/.cache/`` a write target of item 06-73, which declares
only ``.gitignore`` and this file.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# The directory P-10 names. A git pathspec, so forward slashes on every platform.
CACHE_DIR = "artifacts/developer/.cache"

# Suffixes that no extension rule in .gitignore covers; each was confirmed to escape before the
# path rule landed. ``probe`` is extensionless, which no ``*.ext`` rule can ever reach.
ESCAPING_NAMES = [
    "sub-PROBE_ses-000000_rec_units.tmp",
    "sub-PROBE_ses-000000_rec_units.dat",
    "sub-PROBE_ses-000000_rec_units.partial",
    "sub-PROBE_ses-000000_rec_units.lock",
    "probe",
]


def _git(*args: str, repo: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo or REPO_ROOT), *args],
        capture_output=True,
        text=True,
    )


def _check_ignore(path: str) -> tuple[bool, str]:
    """Return ``(is_ignored, matching_pattern)`` for ``path``.

    Two invocations on purpose. Plain ``check-ignore`` is the verdict: its output is exactly the
    subset of its input that is ignored. ``-v`` supplies only the explanation and cannot serve as
    the verdict, because the pattern it reports may be a negation (``!foo``) meaning the path is
    explicitly NOT ignored. Reading a ``-v`` hit as "ignored" reports every re-included file in
    this repository -- 22 of them, the docs figures and the benchmark JSON -- as excluded.
    """
    verdict = _git("check-ignore", "--no-index", path)
    is_ignored = verdict.returncode == 0
    explain = _git("check-ignore", "--no-index", "-v", path)
    pattern = ""
    if explain.returncode == 0 and explain.stdout.strip():
        # "<source>:<linenum>:<pattern>\t<path>"
        pattern = explain.stdout.split("\t")[0].split(":")[-1]
    return is_ignored, pattern


@pytest.fixture(scope="module", autouse=True)
def _requires_checkout() -> None:
    """These tests read the ignore rules of a real checkout; without one there is nothing to read."""
    # `.git` is a directory in a clone and a one-line file in a linked worktree, so test existence.
    if not (REPO_ROOT / ".git").exists():
        pytest.skip("not a git checkout: .gitignore semantics cannot be evaluated")
    if not (REPO_ROOT / ".gitignore").is_file():
        pytest.fail("the repository has no .gitignore, so P-10 cannot be pinned")


class TestCacheIsExcludedByPath:
    def test_the_cache_directory_itself_is_ignored(self) -> None:
        """No extension rule can match a directory; only a path rule can."""
        is_ignored, pattern = _check_ignore(CACHE_DIR + "/")
        assert is_ignored, (
            f"{CACHE_DIR}/ is not ignored, so the derived cache is reachable by "
            "`git add -A`. That is P-10 exactly."
        )
        assert not pattern.startswith("*."), (
            f"{CACHE_DIR}/ is ignored by {pattern!r}, an extension rule."
        )

    @pytest.mark.parametrize("name", ESCAPING_NAMES)
    def test_any_suffix_under_the_cache_is_ignored(self, name: str) -> None:
        """The property P-10 lacked: the suffix does not decide."""
        path = f"{CACHE_DIR}/{name}"
        is_ignored, _ = _check_ignore(path)
        assert is_ignored, (
            f"{path} is not ignored: a cache file with this suffix lands untracked and visible."
        )

    @pytest.mark.parametrize("name", ESCAPING_NAMES)
    def test_the_rule_that_excludes_it_is_a_path_rule(self, name: str) -> None:
        """Pins the shape of the fix, not only its effect.

        Adding ``*.tmp`` to .gitignore would make the ``.tmp`` probe ignored while leaving the
        defect intact for every other suffix. This assertion is what rejects that mutant.
        """
        path = f"{CACHE_DIR}/{name}"
        _, pattern = _check_ignore(path)
        assert not pattern.startswith("*."), (
            f"{path} is excluded by {pattern!r}, an extension rule. P-10 *is* the practice of "
            "excluding this cache by extension; a longer list of extensions is not a repair."
        )
        assert ".cache" in pattern or "artifacts/developer" in pattern, (
            f"{path} is excluded by {pattern!r}, which does not name the cache path. "
            "The exclusion must be anchored at the cache directory."
        )


class TestTheFixIsNotOverbroad:
    def test_no_tracked_file_becomes_ignored(self) -> None:
        """A .gitignore rule that hides a tracked file is silent and hard to reverse.

        Measured over every tracked path rather than argued from the shape of the pattern.
        """
        # NUL-separated, in bytes, both directions. Not decoration: with `text=True` the
        # subprocess stdin wrapper translates each "\n" to "\r\n" on Windows, git then sees
        # ".claude/agents/jnwb-actor.md\r", that no longer matches the "!.claude/agents/*.md"
        # re-inclusion, and this check reports two tracked files as ignored that are not.
        listing = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "-z"], capture_output=True
        )
        tracked = [p for p in listing.stdout.split(b"\0") if p]
        assert tracked, "git ls-files returned nothing, so this check would be vacuous"

        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "check-ignore", "--no-index", "-z", "--stdin"],
            input=b"\0".join(tracked),
            capture_output=True,
        )
        ignored = sorted(
            p.decode("utf-8", "replace") for p in proc.stdout.split(b"\0") if p
        )
        assert not ignored, (
            f"{len(ignored)} tracked file(s) are ignored by .gitignore: {ignored[:10]}"
        )

    @pytest.mark.parametrize("name", ESCAPING_NAMES)
    def test_the_same_suffix_elsewhere_is_unaffected(self, name: str) -> None:
        """The path rule must not have been implemented as a global suffix ban."""
        outside = f"jnwb/{name}"
        is_ignored, pattern = _check_ignore(outside)
        assert not is_ignored, (
            f"{outside} is ignored by {pattern!r}: the cache exclusion leaked into the rest "
            "of the repository."
        )

    def test_the_extension_rules_still_cover_the_rest_of_the_repository(self) -> None:
        """``*.pkl`` and ``*.json`` are kept: the path rule cannot reach outside the cache."""
        for outside in ("scratchdir/model.pkl", "jnwb/blob.pkl", "some/where/data.json"):
            is_ignored, _ = _check_ignore(outside)
            assert is_ignored, (
                f"{outside} is no longer ignored: the blanket extension rule covering the "
                "rest of the repository was dropped."
            )


class TestGitStatusCannotSeeTheCache:
    """06-73 states its discriminator in terms of `git status`, so one test says it that way.

    Built in a throwaway repository rather than this one: the real worktree must not gain an
    `artifacts/developer/.cache/` directory as a side effect of running the suite.
    """

    @staticmethod
    def _throwaway_repo(tmp_path: pathlib.Path) -> pathlib.Path:
        repo = tmp_path / "throwaway"
        repo.mkdir()
        # A global core.excludesFile would otherwise decide part of the answer.
        subprocess.run(
            ["git", "-c", f"core.excludesFile={tmp_path / 'no-such-global-ignore'}",
             "init", "-q", str(repo)],
            capture_output=True, text=True, check=True,
        )
        (repo / ".gitignore").write_bytes((REPO_ROOT / ".gitignore").read_bytes())
        return repo

    def test_a_cache_file_of_any_suffix_is_invisible_to_git_status(
        self, tmp_path: pathlib.Path
    ) -> None:
        repo = self._throwaway_repo(tmp_path)
        cache = repo / "artifacts" / "developer" / ".cache"
        cache.mkdir(parents=True)
        for name in ESCAPING_NAMES:
            (cache / name).write_text("derived cache probe\n", encoding="utf-8")

        # Positive control. Without it, a `git status` that reports nothing for an unrelated
        # reason -- a broken fixture, a repo that never initialised -- would pass this test
        # while proving nothing at all.
        control = repo / "artifacts" / "developer" / "stray.tmp"
        control.write_text("not part of the cache\n", encoding="utf-8")

        # -uall, not bare --porcelain: git collapses untracked directories to the shallowest
        # one, reporting "?? artifacts/" and naming no file inside it. Under that output the
        # ".cache" assertion below passes whether or not the cache is ignored, which is the
        # vacuous form of this test.
        status = _git("status", "--porcelain", "-uall", repo=repo)
        assert status.returncode == 0, status.stderr
        lines = [ln.replace("\\", "/") for ln in status.stdout.splitlines()]

        assert any("stray.tmp" in ln for ln in lines), (
            "the positive control is missing from `git status`, so this fixture cannot "
            f"detect a visible file and proves nothing. status was: {lines}"
        )
        assert not any(".cache" in ln for ln in lines), (
            f"the derived cache is visible to `git status`: {lines}. A `git add -A` would "
            "stage it."
        )
