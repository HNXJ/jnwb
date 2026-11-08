"""Two distributions can never share a version string.

`test_release_date_matches_the_changelog_entry_for_this_version` compares the declared
version to the changelog entry the same tree wrote. Those agree by construction, so the tree
passed it while `jnwb.__version__` said `0.2.4`, PyPI already served a `0.2.4` whose contents
were different, and `## [Unreleased]` held 1009 non-empty lines of shipped work. The audit
that found this measured 20 such lines and three fixes; the divergence grew while the check
that would have caught it did not exist.

The gate step this exercises reads the index. These tests do not: the network belongs in the
release gate, not in a unit suite that has to give the same answer offline, so every branch is
driven through the pure function the step calls.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Appended, not prepended: prepending would also put the checkout's jnwb/ ahead of an
# installed copy and silently redirect a wheel-qualification run back to the source tree.
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))  # needed: the installed-wheel run clears pythonpath

from scripts.release_gate import (  # noqa: E402
    SKIP_INDEX_ENV,
    check_version_is_not_already_published,
    jnwb_source_version,
    unreleased_entry_lines,
)


def test_a_version_the_index_already_serves_is_refused() -> None:
    problems = check_version_is_not_already_published("0.2.4", {"0.1.8", "0.2.4"}, ["- a fix"])
    assert problems, "building a second 0.2.4 was allowed"
    assert "already on the index" in problems[0]


def test_an_unpublished_version_is_allowed() -> None:
    assert check_version_is_not_already_published("0.2.5", {"0.1.8", "0.2.4"}, ["- a fix"]) == []


def test_a_first_release_is_not_a_collision() -> None:
    assert check_version_is_not_already_published("0.1.0", set(), []) == []


def test_a_collision_names_the_pending_changelog_when_there_is_one() -> None:
    with_pending = check_version_is_not_already_published("0.2.4", {"0.2.4"}, ["- a", "- b"])
    assert "2 non-empty lines under [Unreleased]" in with_pending[0]
    without = check_version_is_not_already_published("0.2.4", {"0.2.4"}, [])
    assert without, "a republish of an existing version is a collision with or without a diff"
    assert "non-empty lines" not in without[0], (
        f"a collision with nothing pending still claims pending entries: {without[0]}"
    )


def test_an_unreachable_index_is_unverified_not_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    """The failure mode that matters: the gate must not pass hardest when the network is down."""
    monkeypatch.delenv(SKIP_INDEX_ENV, raising=False)
    problems = check_version_is_not_already_published("0.2.4", None, [])
    assert problems and "could not be reached" in problems[0]
    assert SKIP_INDEX_ENV in problems[0], "the refusal does not say how to proceed offline"


def test_an_offline_build_has_one_named_way_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SKIP_INDEX_ENV, "1")
    assert check_version_is_not_already_published("0.2.4", None, []) == []


def test_the_override_does_not_excuse_a_known_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skipping the lookup is not skipping the rule: a known collision still fails."""
    monkeypatch.setenv(SKIP_INDEX_ENV, "1")
    assert check_version_is_not_already_published("0.2.4", {"0.2.4"}, [])


def test_the_unreleased_reader_stops_at_the_next_heading() -> None:
    changelog = (
        "# Changelog\n\n"
        "## [Unreleased]\n\n"
        "### Fixed\n\n"
        "- something\n\n"
        "## [0.2.4] - 2026-09-16\n\n"
        "- an older thing\n"
    )
    lines = unreleased_entry_lines(changelog)
    assert lines == ["### Fixed", "- something"], lines


def test_an_empty_unreleased_section_reads_as_empty() -> None:
    assert unreleased_entry_lines("# Changelog\n\n## [Unreleased]\n\n## [0.2.4]\n\n- old\n") == []


def _main_function() -> ast.FunctionDef:
    tree = ast.parse((ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError("release_gate.py has no main()")


def test_the_gate_actually_runs_the_check_before_it_builds_anything() -> None:
    """A check that exists and is never called is the defect it was written to prevent.

    Read off the syntax tree, not the text: commenting the call out leaves its name on the
    line, and a substring search reads that as a call.
    """
    main = _main_function()
    calls = [
        node for node in ast.walk(main)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    names = [node.func.id for node in calls]
    assert "check_version_is_not_already_published" in names, (
        "main() never calls the published-version check"
    )
    assert "published_versions" in names, "main() does not read the real index"

    checked_at = min(
        node.lineno for node in calls
        if node.func.id == "check_version_is_not_already_published"
    )
    built_at = [
        node.lineno for node in ast.walk(main)
        if isinstance(node, ast.Constant) and node.value == "build"
    ]
    assert built_at, "main() no longer builds a distribution; this test is stale"
    assert checked_at < min(built_at), (
        "the published-version check runs after the build, so a colliding distribution is "
        "produced before anything objects"
    )


def test_an_unreachable_index_reads_as_unknown_not_as_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wrapper's own fail-closed behaviour, which the pure function cannot express."""
    import scripts.release_gate as gate

    def explode(*args, **kwargs):
        raise OSError("network is down")

    monkeypatch.setattr(gate.urllib.request, "urlopen", explode)
    assert gate.published_versions() is None, (
        "a transport failure read as 'nothing is published', which clears every version"
    )


def test_a_package_the_index_has_never_seen_reads_as_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.release_gate as gate

    def not_found(*args, **kwargs):
        raise gate.urllib.error.HTTPError("u", 404, "Not Found", {}, None)

    monkeypatch.setattr(gate.urllib.request, "urlopen", not_found)
    assert gate.published_versions() == set()


def test_a_served_payload_is_read_as_its_release_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.release_gate as gate

    class _Response:
        def read(self):
            return json.dumps({"releases": {"0.1.0": [], "0.2.4": []}}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(gate.urllib.request, "urlopen", lambda *a, **k: _Response())
    assert gate.published_versions() == {"0.1.0", "0.2.4"}


def test_this_tree_would_be_refused_a_release_at_its_declared_version() -> None:
    """The discriminator the item asks for, stated against the real tree.

    The published set is supplied rather than fetched, so this says exactly one thing: *if*
    the index serves the version this tree declares, the gate refuses to build it. Whether
    the index does serve it is the release gate's question, asked over the network.
    """
    version = jnwb_source_version()
    pending = unreleased_entry_lines()
    refusal = check_version_is_not_already_published(version, {version}, pending)
    assert refusal, f"a rebuild at the already-published {version} would be allowed"
    if pending:
        assert f"{len(pending)} non-empty lines" in refusal[0]


# --- Post-publication mode: a version the index serves is accepted only as the same files. ---

WHEEL = "jnwb-0.2.15-py3-none-any.whl"
SDIST = "jnwb-0.2.15.tar.gz"
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def _gate():
    import scripts.release_gate as gate

    return gate


def _index(version: str, files: dict) -> dict:
    """The index's JSON shape: per-file entries carrying ``digests.sha256``."""
    return {
        "releases": {
            version: [
                {"filename": name, "digests": ({"sha256": sha} if sha is not None else {})}
                for name, sha in files.items()
            ]
        }
    }


def _built(files: dict):
    """A build stub that returns ``(digests, problems)`` as ``build_tag_digests`` does."""
    return lambda: (dict(files), [])


@pytest.fixture(autouse=True)
def _no_download(monkeypatch: pytest.MonkeyPatch) -> None:
    """A served file's content digest stands in as its index sha256: no test downloads."""
    gate = _gate()
    monkeypatch.setattr(gate, "fetch_served_content_digest",
                        lambda entry: (entry["digests"]["sha256"], None))


def _wheel(path: Path, members: dict) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, (data, stamp) in members.items():
            archive.writestr(zipfile.ZipInfo(name, date_time=stamp), data)
    return path


STAMP_1 = (2026, 10, 31, 12, 0, 0)
STAMP_2 = (2026, 11, 3, 8, 30, 0)


def test_two_builds_differing_in_timestamps_and_line_endings_share_a_content_digest(
    tmp_path: Path,
) -> None:
    gate = _gate()
    a = _wheel(tmp_path / "a.whl", {"jnwb/x.py": (b"X = 1\n", STAMP_1),
                                    "jnwb-1.dist-info/METADATA": (b"Name: jnwb\n", STAMP_1),
                                    "jnwb-1.dist-info/RECORD": (b"jnwb/x.py,sha256=aa\n", STAMP_1)})
    b = _wheel(tmp_path / "b.whl", {"jnwb/x.py": (b"X = 1\n", STAMP_2),
                                    "jnwb-1.dist-info/METADATA": (b"Name: jnwb\r\n", STAMP_2),
                                    "jnwb-1.dist-info/RECORD": (b"jnwb/x.py,sha256=bb\n", STAMP_2)})
    assert a.read_bytes() != b.read_bytes(), "fixture must differ in bytes"
    assert gate.archive_content_digest(a) == gate.archive_content_digest(b)


def test_a_changed_member_changes_the_content_digest(tmp_path: Path) -> None:
    gate = _gate()
    a = _wheel(tmp_path / "a.whl", {"jnwb/x.py": (b"X = 1\n", STAMP_1)})
    b = _wheel(tmp_path / "b.whl", {"jnwb/x.py": (b"X = 2\n", STAMP_1)})
    c = _wheel(tmp_path / "c.whl", {"jnwb/x.py": (b"X = 1\n", STAMP_1), "jnwb/y.py": (b"", STAMP_1)})
    digests = {gate.archive_content_digest(p) for p in (a, b, c)}
    assert len(digests) == 3


def test_an_sdist_is_read_by_member(tmp_path: Path) -> None:
    gate = _gate()
    paths = []
    for name, data in (("a.tar.gz", b"X = 1\n"), ("b.tar.gz", b"X = 1\r\n"), ("c.tar.gz", b"X = 2\n")):
        source = tmp_path / name.replace(".tar.gz", ".py")
        source.write_bytes(data)
        with tarfile.open(tmp_path / name, "w:gz") as archive:
            archive.add(source, arcname="jnwb-1/x.py")
        paths.append(tmp_path / name)
    a, b, c = (gate.archive_content_digest(p) for p in paths)
    assert a == b and a != c


def test_a_served_download_that_is_not_the_indexed_file_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = _gate()
    monkeypatch.undo()
    served = _wheel(tmp_path / WHEEL, {"jnwb/x.py": (b"X = 1\n", STAMP_1)})
    entry = {"filename": WHEEL, "url": served.as_uri(), "digests": {"sha256": DIGEST_A}}
    content, why = gate.fetch_served_content_digest(entry)
    assert content is None and "is not the index's" in why
    entry["digests"]["sha256"] = hashlib.sha256(served.read_bytes()).hexdigest()
    content, why = gate.fetch_served_content_digest(entry)
    assert why is None and content == gate.archive_content_digest(served)


def test_the_flag_is_named_and_read_by_main() -> None:
    gate = _gate()
    assert gate.POST_PUBLICATION_FLAG == "--published"
    main = _main_function()
    names = {node.id for node in ast.walk(main) if isinstance(node, ast.Name)}
    assert "POST_PUBLICATION_FLAG" in names, "main() does not read the post-publication flag"
    assert "check_index_matches_tag_build" in names, "main() never runs the flag's check"


def test_post_publication_an_unpublished_version_passes_without_a_build() -> None:
    gate = _gate()

    def never_built():
        raise AssertionError("an unpublished version was built")

    assert gate.check_index_matches_tag_build("0.2.16", _index("0.2.15", {WHEEL: DIGEST_A}),
                                              never_built) == []


def test_post_publication_a_matching_published_version_passes() -> None:
    gate = _gate()
    files = {WHEEL: DIGEST_A, SDIST: DIGEST_B}
    assert gate.check_index_matches_tag_build("0.2.15", _index("0.2.15", files), _built(files)) == []


def test_post_publication_a_mismatched_file_fails_by_name() -> None:
    gate = _gate()
    problems = gate.check_index_matches_tag_build(
        "0.2.15",
        _index("0.2.15", {WHEEL: DIGEST_A, SDIST: DIGEST_B}),
        _built({WHEEL: DIGEST_B, SDIST: DIGEST_B}),
    )
    assert len(problems) == 1, problems
    assert WHEEL in problems[0] and "differ from" in problems[0]
    assert DIGEST_A in problems[0] and DIGEST_B in problems[0]


def test_post_publication_a_file_the_build_lacks_fails_by_name() -> None:
    gate = _gate()
    problems = gate.check_index_matches_tag_build(
        "0.2.15", _index("0.2.15", {WHEEL: DIGEST_A, SDIST: DIGEST_B}), _built({WHEEL: DIGEST_A})
    )
    assert any(SDIST in p and "does not produce" in p for p in problems), problems


def test_post_publication_a_file_the_index_lacks_fails_by_name() -> None:
    gate = _gate()
    problems = gate.check_index_matches_tag_build(
        "0.2.15", _index("0.2.15", {WHEEL: DIGEST_A}), _built({WHEEL: DIGEST_A, SDIST: DIGEST_B})
    )
    assert any(SDIST in p and "does not serve" in p for p in problems), problems


def test_post_publication_an_index_file_without_a_sha256_fails_by_name() -> None:
    gate = _gate()
    problems = gate.check_index_matches_tag_build(
        "0.2.15", _index("0.2.15", {WHEEL: None}), _built({WHEEL: DIGEST_A})
    )
    assert any(WHEEL in p and "no sha256" in p for p in problems), problems


def test_post_publication_a_build_that_was_refused_fails() -> None:
    gate = _gate()
    refused = lambda: (None, ["HEAD abc is not the commit v0.2.15 names"])  # noqa: E731
    problems = gate.check_index_matches_tag_build(
        "0.2.15", _index("0.2.15", {WHEEL: DIGEST_A}), refused
    )
    assert problems == ["HEAD abc is not the commit v0.2.15 names"]


def test_post_publication_an_empty_build_cannot_match_anything() -> None:
    gate = _gate()
    problems = gate.check_index_matches_tag_build(
        "0.2.15", _index("0.2.15", {WHEEL: DIGEST_A}), _built({})
    )
    assert problems, "an empty build was read as a match"


def test_post_publication_an_unreachable_index_is_unverified_not_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = _gate()
    monkeypatch.delenv(SKIP_INDEX_ENV, raising=False)
    problems = gate.check_index_matches_tag_build("0.2.15", None, _built({WHEEL: DIGEST_A}))
    assert problems and "could not be reached" in problems[0]


def test_post_publication_an_offline_run_records_a_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    gate = _gate()
    monkeypatch.setenv(SKIP_INDEX_ENV, "1")
    monkeypatch.setattr(gate, "SKIPPED_CHECKS", [])
    assert gate.check_index_matches_tag_build("0.2.15", None, _built({WHEEL: DIGEST_A})) == []
    assert gate.SKIPPED_CHECKS == [gate.INDEX_SKIPPED]


class _Git:
    """A subprocess stub for ``build_tag_digests``: git answers, and the build writes files."""

    def __init__(self, head, tagged, files=None, build_rc=0):
        self.head, self.tagged, self.files, self.build_rc = head, tagged, files or {}, build_rc
        self.commands = []

    def __call__(self, cmd, **kwargs):
        self.commands.append(list(cmd))
        if cmd[1:2] == ["rev-parse"]:
            value = self.head if cmd[-1] == "HEAD" else self.tagged
            if value is None:
                return subprocess.CompletedProcess(cmd, 1, "", "unknown revision")
            return subprocess.CompletedProcess(cmd, 0, value + "\n", "")
        if cmd[1:3] == ["-m", "build"]:
            outdir = Path(cmd[cmd.index("--outdir") + 1])
            for name, data in self.files.items():
                (outdir / name).write_bytes(data)
            return subprocess.CompletedProcess(cmd, self.build_rc, "", "")
        raise AssertionError(f"unexpected command {cmd}")


def test_the_tag_build_refuses_a_head_that_is_not_the_tag(tmp_path: Path) -> None:
    gate = _gate()
    git = _Git(head="a" * 40, tagged="b" * 40)
    digests, problems = gate.build_tag_digests("0.2.15", root=tmp_path, runner=git)
    assert digests is None
    assert "v0.2.15" in problems[0] and "not the commit" in problems[0]
    assert not any(cmd[1:3] == ["-m", "build"] for cmd in git.commands), (
        "a build of HEAD ran although HEAD is not the tag"
    )


def test_the_tag_build_refuses_an_unresolvable_tag(tmp_path: Path) -> None:
    gate = _gate()
    digests, problems = gate.build_tag_digests(
        "0.2.15", root=tmp_path, runner=_Git(head="a" * 40, tagged=None)
    )
    assert digests is None and "v0.2.15" in problems[0] and "does not resolve" in problems[0]


def test_the_tag_build_digests_each_file_it_produces(tmp_path: Path) -> None:
    gate = _gate()
    wheel = _wheel(tmp_path / "w.whl", {"jnwb/x.py": (b"X = 1\n", STAMP_1)})
    git = _Git(head="a" * 40, tagged="a" * 40, files={WHEEL: wheel.read_bytes()})
    digests, problems = gate.build_tag_digests("0.2.15", root=tmp_path, runner=git)
    assert problems == []
    assert digests == {WHEEL: gate.archive_content_digest(wheel)}


def test_the_tag_build_refuses_an_unreadable_distribution(tmp_path: Path) -> None:
    gate = _gate()
    git = _Git(head="a" * 40, tagged="a" * 40, files={WHEEL: b"not a zip"})
    digests, problems = gate.build_tag_digests("0.2.15", root=tmp_path, runner=git)
    assert digests is None and "unreadable distribution" in problems[0]


def test_the_tag_build_reports_a_failed_build(tmp_path: Path) -> None:
    gate = _gate()
    digests, problems = gate.build_tag_digests(
        "0.2.15", root=tmp_path, runner=_Git(head="a" * 40, tagged="a" * 40, build_rc=1)
    )
    assert digests is None and "building v0.2.15 failed" in problems[0]
