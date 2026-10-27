"""The CHANGELOG half of gate 14: the entry template, on the live file and on planted text."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# Appended, not prepended, as in the adversarial probes: the checkout's scripts/ must not shadow an
# installed copy.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # needed: the installed-wheel run clears pythonpath

from scripts.harness_gate import (  # noqa: E402
    CHANGELOG_ENTRY_LIMIT,
    CHANGELOG_KINDS,
    CHANGELOG_RELEASES_KEPT,
    _internal_vocabulary_checks,
    check_changelog_form,
)

HEADER = "# Changelog\n\n## [Unreleased]\n\n"
GOOD_ENTRY = "- `widget()` returns 2 for an int seed (tests/test_widget.py)."
LONG_ENTRY = "- " + "`widget()` changes " * 8 + "(tests/test_widget.py)."


def _tree(root, changelog):
    """A planted tree: the CHANGELOG and the one test file the good entries name."""
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "test_widget.py").write_text("", encoding="utf-8")
    (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8", newline="\n")
    return root


def _release(version, body):
    return f"## [{version}] - 2026-10-11\n\n{body}"


def test_the_live_changelog_meets_the_template():
    violations = check_changelog_form()
    assert violations == [], f"{len(violations)} violations; first: {violations[:1]}"


def test_gate_14_reports_no_changelog_failure_on_the_live_tree():
    headers = [header for header, _ in _internal_vocabulary_checks()]
    assert not any("CHANGELOG.md" in header for header in headers), headers


def test_a_conforming_changelog_passes(tmp_path):
    root = _tree(tmp_path, HEADER + _release("0.2.12", "### Added\n\n" + GOOD_ENTRY + "\n"))
    assert check_changelog_form(root) == []


def test_the_template_applies_from_0_2_12(tmp_path):
    """One entry under the 0.2.12 heading passes, one fails: the fail is named by its line."""
    body = "### Added\n\n" + GOOD_ENTRY + "\n" + LONG_ENTRY + "\n"
    root = _tree(tmp_path, HEADER + _release("0.2.12", body))
    violations = check_changelog_form(root)
    assert len(violations) == 1, violations
    assert f"CHANGELOG.md:10 is {len(LONG_ENTRY)} characters" in violations[0], violations


def test_an_earlier_release_is_not_held_to_length_naming_or_seed_rules(tmp_path):
    loose = "\n".join([
        LONG_ENTRY,
        "- `widget()` returns 2.",
        "- [results change] `widget()` draws differently.",
        GOOD_ENTRY + "\n  - a wrapped second line",
    ])
    assert len(LONG_ENTRY) > CHANGELOG_ENTRY_LIMIT, "the fixture must be over the limit"
    body = "### Added\n\n" + loose + "\n"
    root = _tree(tmp_path, HEADER + _release("0.2.6.1", body) + _release("0.2.5", body))
    assert check_changelog_form(root) == []


def test_an_earlier_release_still_refuses_a_process_term(tmp_path):
    root = _tree(tmp_path, HEADER + _release("0.2.11", "### Added\n\n- `widget()` drops the receipt.\n"))
    violations = check_changelog_form(root)
    assert len(violations) == 1 and "'receipt'" in violations[0], violations


def test_unreleased_is_held_to_the_template(tmp_path):
    root = _tree(
        tmp_path,
        "# Changelog\n\n## [Unreleased]\n\n### Added\n\n" + LONG_ENTRY + "\n\n"
        + _release("0.2.11", "### Added\n\n" + GOOD_ENTRY + "\n"),
    )
    violations = check_changelog_form(root)
    assert len(violations) == 1 and "characters" in violations[0], violations


def test_a_long_entry_under_0_2_12_is_refused(tmp_path):
    assert len(LONG_ENTRY) > CHANGELOG_ENTRY_LIMIT, "the fixture must be over the limit"
    root = _tree(tmp_path, HEADER + _release("0.2.12", "### Added\n\n" + LONG_ENTRY + "\n"))
    violations = check_changelog_form(root)
    assert len(violations) == 1 and f"is {len(LONG_ENTRY)} characters" in violations[0], violations


def test_a_heading_outside_the_six_kinds_is_refused(tmp_path):
    root = _tree(tmp_path, HEADER + _release("0.2.11", "### Documentation\n\n" + GOOD_ENTRY + "\n"))
    violations = check_changelog_form(root)
    assert len(violations) == 1 and "'### Documentation'" in violations[0], violations


def test_each_of_the_six_kinds_passes(tmp_path):
    body = "".join(f"### {kind}\n\n{GOOD_ENTRY}\n\n" for kind in CHANGELOG_KINDS)
    assert len(CHANGELOG_KINDS) == 6, CHANGELOG_KINDS
    root = _tree(tmp_path, HEADER + _release("0.2.12", body))
    assert check_changelog_form(root) == []


def test_an_entry_naming_no_file_is_refused(tmp_path):
    root = _tree(tmp_path, HEADER + _release("0.2.12", "### Added\n\n- `widget()` returns 2.\n"))
    violations = check_changelog_form(root)
    assert len(violations) == 1 and "names no test or file" in violations[0], violations


def test_a_named_path_must_exist(tmp_path):
    entry = "- `widget()` returns 2 (tests/test_gone.py)."
    root = _tree(tmp_path, HEADER + _release("0.2.12", "### Added\n\n" + entry + "\n"))
    violations = check_changelog_form(root)
    assert len(violations) == 1 and "tests/test_gone.py" in violations[0], violations


def test_results_change_names_the_seed_kind(tmp_path):
    bare = "- [results change] `widget()` draws differently (tests/test_widget.py)."
    root = _tree(tmp_path / "bare", HEADER + _release("0.2.12", "### Changed\n\n" + bare + "\n"))
    violations = check_changelog_form(root)
    assert len(violations) == 1 and "neither 'int seed', 'Generator' nor 'deterministic'" in violations[0], violations
    for seed in ("with an int seed", "with a Generator", "deterministic, it", "(deterministic)",
                 "is deterministic."):
        named = f"- [results change] `widget()` {seed} draws differently (tests/test_widget.py)."
        root = _tree(tmp_path / seed.replace(" ", "_"),
                     HEADER + _release("0.2.12", "### Changed\n\n" + named + "\n"))
        assert check_changelog_form(root) == [], seed
    for i, inside in enumerate(("is nondeterministic", "with an int seeded draw", "Generators")):
        line = f"- [results change] `widget()` {inside} (tests/test_widget.py)."
        root = _tree(tmp_path / f"inside{i}", HEADER + _release("0.2.12", "### Changed\n\n" + line + "\n"))
        assert len(check_changelog_form(root)) == 1, f"a kind inside another word is not named: {inside}"


def test_a_process_term_is_refused(tmp_path):
    flagged = [
        "- `widget()` drops the receipt of the run (tests/test_widget.py).",
        "- `widget()` cites `AGENTS.md` (tests/test_widget.py).",
        "- `widget()` fixes the audit RG finding (tests/test_widget.py).",
        "- `widget()` closes with a closure pass (tests/test_widget.py).",
        "- `widget()` is a subagent output (tests/test_widget.py).",
    ]
    root = _tree(tmp_path, HEADER + _release("0.2.11", "### Added\n\n" + "\n".join(flagged) + "\n"))
    violations = check_changelog_form(root)
    assert len(violations) == len(flagged), violations


def test_public_words_are_not_refused(tmp_path):
    public = [
        "- `widget()` names the agent page of the docs (tests/test_widget.py).",
        "- `widget()` starts a worker before any pool job begins (tests/test_widget.py).",
        "- `widget()` fills a gestalt closure contour (tests/test_widget.py).",
        "- `widget()` documents the three tools in docs/agents.md (tests/test_widget.py).",
    ]
    root = _tree(tmp_path, HEADER + _release("0.2.11", "### Added\n\n" + "\n".join(public) + "\n"))
    assert check_changelog_form(root) == []


def test_more_than_the_kept_releases_is_refused(tmp_path):
    def blocks(count):
        return "".join(
            _release(f"0.{n}.0", "### Added\n\n" + GOOD_ENTRY + "\n\n") for n in range(1, count + 1)
        )

    root = _tree(tmp_path / "over", HEADER + blocks(CHANGELOG_RELEASES_KEPT + 1))
    violations = check_changelog_form(root)
    assert len(violations) == 1 and f"holds {CHANGELOG_RELEASES_KEPT + 1} release" in violations[0], violations
    root = _tree(tmp_path / "kept", HEADER + blocks(CHANGELOG_RELEASES_KEPT))
    assert check_changelog_form(root) == []


def test_an_entry_wrapped_onto_a_second_line_is_refused(tmp_path):
    wrapped = GOOD_ENTRY + "\n  - a second line of the same change\n"
    root = _tree(tmp_path, HEADER + _release("0.2.12", "### Added\n\n" + wrapped))
    violations = check_changelog_form(root)
    assert len(violations) == 1 and "second line" in violations[0], violations


def test_a_changelog_with_no_release_block_is_not_a_pass(tmp_path):
    root = _tree(tmp_path, HEADER)
    violations = check_changelog_form(root)
    assert len(violations) == 1 and "no release block" in violations[0], violations


def test_agents_md_passes_on_a_line_that_names_the_sdist(tmp_path):
    entry = "- The sdist ships `AGENTS.md` and `skills/` (tests/test_widget.py)."
    root = _tree(tmp_path, HEADER + _release("0.2.12", "### Changed\n\n" + entry + "\n"))
    assert check_changelog_form(root) == []


def test_agents_md_fails_on_a_line_that_names_no_package_content(tmp_path):
    entry = "- `widget()` cites `AGENTS.md` for the rule (tests/test_widget.py)."
    root = _tree(tmp_path, HEADER + _release("0.2.12", "### Changed\n\n" + entry + "\n"))
    violations = check_changelog_form(root)
    assert len(violations) == 1 and "'AGENTS.md'" in violations[0], violations


def test_agents_md_passes_in_a_bullet_that_names_the_sdist_on_another_line(tmp_path):
    bullet = (
        "- The rules file now ships in the sdist, beside `skills/`\n"
        "  and it names `AGENTS.md` (tests/test_widget.py)."
    )
    root = _tree(tmp_path, HEADER + _release("0.2.11", "### Changed\n\n" + bullet + "\n"))
    assert check_changelog_form(root) == []


def test_agents_md_fails_in_a_bullet_that_names_no_package_content_though_the_next_does(tmp_path):
    bullet = (
        "- `widget()` now cites the rule in one place\n"
        "  as `AGENTS.md` (tests/test_widget.py).\n"
        "- The sdist ships `skills/` (tests/test_widget.py)."
    )
    root = _tree(tmp_path, HEADER + _release("0.2.11", "### Changed\n\n" + bullet + "\n"))
    violations = check_changelog_form(root)
    assert len(violations) == 1 and "'AGENTS.md'" in violations[0], violations


def test_a_patch_is_counted_with_its_release(tmp_path):
    kept = ["0.2.11", "0.2.10", "0.2.7", "0.2.6.1", "0.2.6", "0.2.5"]
    assert len(kept) == CHANGELOG_RELEASES_KEPT + 1, kept
    assert len({".".join(v.split(".")[:3]) for v in kept}) == CHANGELOG_RELEASES_KEPT, kept
    body = "### Added\n\n" + GOOD_ENTRY + "\n\n"
    root = _tree(tmp_path, HEADER + "".join(_release(v, body) for v in kept))
    assert check_changelog_form(root) == []
