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
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Appended, not prepended: prepending would also put the checkout's jnwb/ ahead of an
# installed copy and silently redirect a wheel-qualification run back to the source tree.
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

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
