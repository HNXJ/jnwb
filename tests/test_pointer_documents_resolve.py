"""`AGENTS.md` and the two stacks are registries, and a registry goes stale silently.

`tests/test_agents_md_recipes.py` already resolves the directory-prefixed paths AGENTS.md
cites and the todo item it names. What nothing resolved is the rest of what those documents
point at: their own section cross-references, the files they name without a directory, the
paths the fact stack carries, and the rule in AGENTS.md section 2 that says the todo stack
holds only work not yet done.

Each sweep is a function over text rather than a loop inside a test, so every one of them is
driven twice: once over the live document, where it must find nothing, and once over a
document built to carry the defect, where it must find it. A sweep only ever run over a
corpus that happens to be clean cannot show that it works -- that is how three `glob("*.md")`
calls read none of the nine pages under `docs/tutorials/` for as long as they did. Each sweep
also carries a floor on how much it matched, because a registry check that quietly stops
matching is the same defect one level up.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS = REPO_ROOT / "AGENTS.md"
TODO_STACK = REPO_ROOT / "artifacts" / "todo_stack.md"
FACT_STACK = REPO_ROOT / "artifacts" / "fact_stack.md"

#: A path written with one of the repository's own top-level directories in front of it.
PREFIXED_PATH = re.compile(r"`((?:jnwb|tests|docs|skills|scripts|examples|artifacts)/[\w./-]+)`")
#: A file named without a directory: `pyproject.toml`, `api.md`, `CHANGELOG.md`.
BARE_FILE = re.compile(r"`([A-Za-z][\w.-]*\.(?:toml|md|yml|yaml|cfg|ini|txt|in))`")
SECTION_HEADER = re.compile(r"^## (\d+)\. (.+)$", re.M)
SECTION_REF = re.compile(r"§ ?(\d+)")
DONE_MARKER = re.compile(r"\[(?:DONE|CLOSED|COMPLETE)\]|\((?:DONE|CLOSED|COMPLETE)\)|~~", re.I)
STATUS_COLUMN = re.compile(r"\|\s*(?:Status|Done|Closed|Complete)\s*\|", re.I)


def sections_defined(text: str) -> set[str]:
    return {number for number, _ in SECTION_HEADER.findall(text)}


def dangling_sections(text: str) -> list[str]:
    """Section numbers the document points at but does not define."""
    return sorted(set(SECTION_REF.findall(text)) - sections_defined(text), key=int)


def section_numbering_gaps(text: str) -> list[int]:
    """Section numbers missing from an otherwise contiguous run starting at zero.

    A gap is how a cross-reference survives the deletion of what it pointed at: renumber
    around a removed section and `§4` now names whatever moved into its place.
    """
    numbers = sorted(int(n) for n, _ in SECTION_HEADER.findall(text))
    if not numbers:
        return []
    return [n for n in range(numbers[0], numbers[-1] + 1) if n not in numbers]


def unmatched_filenames(text: str, tracked: set[str]) -> list[str]:
    """Bare filenames the document names that match no tracked file.

    Matched on the basename rather than a root-relative path: AGENTS.md's `docs/` table row
    names `api.md` and `common_mistakes.md` with the directory in the first cell, and both
    are real pages. A deleted file has no basename anywhere, which is the case that matters.
    """
    return sorted(name for name in set(BARE_FILE.findall(text)) if name not in tracked)


def unresolved_paths(text: str, root: Path, tracked: set[str]) -> list[str]:
    """Directory-prefixed and bare paths the document cites that resolve to nothing."""
    cited = set(PREFIXED_PATH.findall(text)) | set(BARE_FILE.findall(text))
    return sorted(
        p for p in cited if not (root / p).exists() and Path(p).name not in tracked
    )


def completed_work_markers(text: str) -> list[str]:
    """Lines by which a stack records finished work instead of deleting it.

    A heading marked done or struck through, or a table announcing a status column. Not a
    bare search for the word: the stack is also a record of findings, and a finding may say
    in prose that something was closed by an earlier item.
    """
    offenders = []
    for line in text.splitlines():
        if line.startswith("#") and DONE_MARKER.search(line):
            offenders.append(line)
        elif line.startswith("|") and STATUS_COLUMN.search(line):
            offenders.append(line)
    return offenders


def _tracked_basenames() -> set[str]:
    listing = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    assert len(listing) > 100, f"git ls-files returned {len(listing)} paths; the sweep is wrong"
    return {Path(name).name for name in listing}


@pytest.fixture(scope="module")
def agents_text() -> str:
    return AGENTS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tracked() -> "set[str]":
    return _tracked_basenames()


class TestAgentsMdResolvesItsOwnCrossReferences:
    """`§7` is a pointer like any other, and renumbering the document breaks it silently."""

    def test_the_live_document_has_none(self, agents_text: str):
        defined = sections_defined(agents_text)
        referenced = set(SECTION_REF.findall(agents_text))
        assert len(defined) >= 8, f"only {len(defined)} sections parsed; the header regex is wrong"
        assert len(referenced) >= 4, f"only {len(referenced)} references matched; the sweep is wrong"
        assert not dangling_sections(agents_text), (
            f"AGENTS.md points at sections {dangling_sections(agents_text)}, which it does not "
            f"define; it defines {sorted(defined, key=int)}"
        )

    def test_a_reference_to_a_deleted_section_is_found(self):
        doc = "## 0. Where things are\n\n## 1. Evidence\n\nSee §0, §1 and §4.\n"
        assert dangling_sections(doc) == ["4"]

    def test_the_section_numbers_are_contiguous_from_zero(self, agents_text: str):
        numbers = sorted(int(n) for n, _ in SECTION_HEADER.findall(agents_text))
        assert numbers and numbers[0] == 0, numbers
        assert section_numbering_gaps(agents_text) == [], section_numbering_gaps(agents_text)

    def test_a_removed_section_leaves_a_gap_that_is_found(self):
        doc = "## 0. A\n\n## 1. B\n\n## 3. D\n"
        assert section_numbering_gaps(doc) == [2]


class TestAgentsMdResolvesTheFilesItNames:
    """The existing sweep requires a directory prefix, so a bare filename is invisible to it.

    `docs/requirements.txt` was deleted while three documents still named it. That one was
    caught by reading, not by a check.
    """

    def test_the_live_document_names_nothing_that_is_gone(self, agents_text: str, tracked):
        cited = set(BARE_FILE.findall(agents_text))
        assert len(cited) >= 5, f"only {len(cited)} filenames matched; the sweep has stopped working"
        missing = unmatched_filenames(agents_text, tracked)
        assert not missing, f"AGENTS.md names files that no longer exist: {missing}"

    def test_a_deleted_file_is_found(self, tracked):
        doc = "Install with `pyproject.toml`, then read `requirements.txt`.\n"
        assert unmatched_filenames(doc, tracked) == ["requirements.txt"]

    def test_a_file_that_lives_in_a_subdirectory_is_not_reported(self, tracked):
        """`api.md` is `docs/api.md`, and naming it without its directory is not a defect."""
        assert unmatched_filenames("See `api.md` and `common_mistakes.md`.\n", tracked) == []

    def test_the_premise_holds(self, tracked):
        """`requirements.txt` really is absent, so the case above is not vacuous."""
        assert "requirements.txt" not in tracked
        assert "pyproject.toml" in tracked


class TestTheFactStackResolves:
    """The fact stack is human-authorized and never rewritten in passing, which is exactly
    why nothing notices when the tree moves out from under it."""

    def test_the_live_document_resolves(self, tracked):
        text = FACT_STACK.read_text(encoding="utf-8")
        cited = set(PREFIXED_PATH.findall(text)) | set(BARE_FILE.findall(text))
        assert cited, "the fact stack cites no path at all; the sweep is wrong"
        missing = unresolved_paths(text, REPO_ROOT, tracked)
        assert not missing, f"artifacts/fact_stack.md cites paths that do not exist: {missing}"

    def test_a_moved_path_is_found(self, tracked):
        doc = "Ruled against `artifacts/todo_stack.md` and `artifacts/deleted_stack.md`.\n"
        assert unresolved_paths(doc, REPO_ROOT, tracked) == ["artifacts/deleted_stack.md"]

    def test_a_bare_filename_is_resolved_too(self, tracked):
        """Not only directory-prefixed paths: the fact stack names `pyproject.toml` bare."""
        doc = "Pinned in `pyproject.toml`, superseding `requirements.txt`.\n"
        assert unresolved_paths(doc, REPO_ROOT, tracked) == ["requirements.txt"]


class TestTheTodoStackHoldsOnlyUnresolvedWork:
    """AGENTS.md section 2: "delete finished items; add only unresolved work".

    The stack had accumulated a completed-work table, which is the failure this checks for.
    It does not check that every path in the stack resolves: the stack is also a record of
    findings, and a record correctly names a file that the finding caused to be deleted --
    eight of the paths it cites today are of exactly that kind.
    """

    def test_the_rule_is_where_this_test_says_it_is(self, agents_text: str):
        """If the rule moves or softens, this test is measuring nothing."""
        assert "delete finished items; add only unresolved work" in agents_text

    def test_the_stack_says_so_itself(self):
        assert "Items are deleted when done" in TODO_STACK.read_text(encoding="utf-8")

    def test_the_live_stack_records_no_finished_work(self):
        text = TODO_STACK.read_text(encoding="utf-8")
        headings = [ln for ln in text.splitlines() if ln.startswith("#")]
        # Parsed means the version heading and at least one item were found; a count floor would
        # tie the check to the size of one cycle's stack.
        assert headings and re.match(r"# \d+\.\d+\.\d+$", headings[0]), headings[:1]
        assert any(h.startswith("### ") for h in headings), "no item heading; the stack is not being parsed"
        assert completed_work_markers(text) == []

    def test_a_marked_heading_is_found(self):
        assert completed_work_markers("### 05-01 something [DONE]\n") == [
            "### 05-01 something [DONE]"
        ]

    def test_a_struck_through_heading_is_found(self):
        assert completed_work_markers("## ~~05-02 something~~\n") == ["## ~~05-02 something~~"]

    def test_a_completed_work_table_is_found(self):
        table = "| Item | Status |\n|---|---|\n| 05-01 | done |\n"
        # Both the header and the row: a cell that says only "done" is a status cell too.
        assert completed_work_markers(table) == ["| Item | Status |", "| 05-01 | done |"]

    def test_prose_about_closing_an_item_is_not_a_marker(self):
        """A finding may say an earlier item closed something; that is a record, not a status."""
        prose = "already closed by 05-26: `jrsa.py:22` imports from `._backend`\n"
        assert completed_work_markers(prose) == []
