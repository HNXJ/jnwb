"""Gate 16's second rule: a file whose line endings were converted wholesale.

P-159. Gate 16 fails a file that **mixes** CRLF and bare LF. It cannot see a file whose
convention was **converted**, and the conversion is the failure that actually happens: the
dispatcher inserted a 13-line notice into `artifacts/evidence/0.2.6/compress_fp32_policy.md` with
`pathlib.Path.write_text`, which opens with ``newline=None`` and translates ``\\n`` to
``os.linesep`` on Windows. The file went from 206 LF lines and 0 CRLF to 0 LF and 219 CRLF --
every line rewritten, a 425-line diff for a 13-line insertion, and the real change buried in
it. Gate 16 passed, because the result is perfectly uniform.

`.gitattributes` marks the tree ``-text``, so the committed bytes are the convention. The
mixed-file rule is a proxy for that, and the gap between the two is exactly where the
conversion lives -- P-37's shape, and the seventh measured instance this cycle of a check that
passes for the wrong reason.

Every test here builds a **real repository** and converts a file in it. The live tree is clean,
so the check finds nothing there, and a zero that nothing can distinguish from a broken check
is what this file exists to prevent. The fixtures write bytes explicitly rather than through
`write_text`, because `write_text` is the thing under test and using it to build the fixture
would make the fixture agree with the defect.
"""

import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # never insert(0): pyproject sets pythonpath = ["."]

from scripts.harness_gate import (  # noqa: E402
    _convention,
    _wholesale_conversions,
    check_line_ending_consistency,
)

LF_BODY = b"first line\nsecond line\nthird line\n"
CRLF_BODY = b"first line\r\nsecond line\r\nthird line\r\n"


def _git(root: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A real repository with one committed LF file, checked out clean."""
    root = tmp_path / "tree"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "test")
    (root / ".gitattributes").write_bytes(b"* -text\n")
    (root / "policy.md").write_bytes(LF_BODY)
    _git(root, "add", ".gitattributes", "policy.md")
    _git(root, "commit", "-q", "-m", "seed")
    return root


class TestTheConversionIsSeen:
    def test_a_clean_tree_reports_nothing(self, repo: pathlib.Path):
        """The selector must pass pristine before any failure of it can be read as a kill."""
        assert _wholesale_conversions(repo) == []

    def test_lf_converted_to_crlf_is_reported(self, repo: pathlib.Path):
        (repo / "policy.md").write_bytes(CRLF_BODY)
        found = _wholesale_conversions(repo)
        assert len(found) == 1, found
        assert "policy.md" in found[0]
        assert "committed as LF and is now CRLF" in found[0]

    def test_crlf_converted_to_lf_is_reported(self, tmp_path: pathlib.Path):
        root = tmp_path / "crlf"
        root.mkdir()
        _git(root, "init", "-q")
        _git(root, "config", "user.email", "test@example.invalid")
        _git(root, "config", "user.name", "test")
        # Without `-text`, a host with core.autocrlf=true (the Windows runners) stores the CRLF
        # file as LF, and the LF rewrite below is then no conversion at all.
        (root / ".gitattributes").write_bytes(b"* -text\n")
        (root / "skill.md").write_bytes(CRLF_BODY)
        _git(root, "add", ".gitattributes", "skill.md")
        _git(root, "commit", "-q", "-m", "seed")

        (root / "skill.md").write_bytes(LF_BODY)
        found = _wholesale_conversions(root)
        assert len(found) == 1, found
        assert "committed as CRLF and is now LF" in found[0]

    def test_an_edit_that_keeps_the_convention_is_not_reported(self, repo: pathlib.Path):
        """The discriminator that stops this from firing on every modified file."""
        (repo / "policy.md").write_bytes(LF_BODY + b"a fourth line\n")
        assert _wholesale_conversions(repo) == []

    def test_the_real_mechanism_is_caught(self, repo: pathlib.Path):
        """`Path.write_text` on Windows, which is how the incident happened.

        Skipped where `os.linesep` is `\\n`, because there the call does not convert and a
        pass would mean nothing. Asserting the conversion happened before asserting it is
        caught keeps the test from agreeing with a platform that cannot reproduce it.
        """
        import os

        if os.linesep != "\r\n":
            pytest.skip("write_text only rewrites line endings where os.linesep is CRLF")
        body = (repo / "policy.md").read_bytes().decode()
        (repo / "policy.md").write_text(body + "a fourth line\n", encoding="utf-8")
        assert _convention((repo / "policy.md").read_bytes()) == "CRLF", (
            "write_text did not convert, so this test is not exercising the mechanism"
        )
        assert _wholesale_conversions(repo), "the conversion write_text performs was not seen"

    def test_writing_bytes_is_the_repair(self, repo: pathlib.Path):
        """The advice the violation gives has to actually work."""
        body = (repo / "policy.md").read_bytes()
        (repo / "policy.md").write_bytes(body + b"a fourth line\n")
        assert _wholesale_conversions(repo) == []

    def test_a_new_file_has_no_committed_convention(self, repo: pathlib.Path):
        (repo / "fresh.md").write_bytes(CRLF_BODY)
        _git(repo, "add", "fresh.md")
        assert _wholesale_conversions(repo) == [], (
            "a file with no HEAD blob has no convention to have departed from"
        )

    def test_a_binary_file_is_skipped(self, repo: pathlib.Path):
        (repo / "blob.bin").write_bytes(b"\x00\x01\x02\r\n")
        _git(repo, "add", "blob.bin")
        _git(repo, "commit", "-q", "-m", "binary")
        (repo / "blob.bin").write_bytes(b"\x00\x01\x02\n")
        assert _wholesale_conversions(repo) == []

    def test_a_deleted_file_is_skipped(self, repo: pathlib.Path):
        (repo / "policy.md").unlink()
        assert _wholesale_conversions(repo) == []


class TestTheConventionHelper:
    @pytest.mark.parametrize(
        "data, expected",
        [
            (LF_BODY, "LF"),
            (CRLF_BODY, "CRLF"),
            (b"one\r\ntwo\n", "mixed"),
            (b"no line endings at all", None),
            (b"", None),
        ],
    )
    def test_each_case(self, data: bytes, expected):
        assert _convention(data) == expected

    def test_a_mixed_file_is_left_to_the_other_rule(self, repo: pathlib.Path):
        """Both rules firing on one file would report the same defect twice, under two names.

        Gate 16's original rule owns the mixed case; this one owns the conversion. A file that
        became mixed is reported once, by the rule whose message explains it.
        """
        (repo / "policy.md").write_bytes(b"first line\r\nsecond line\nthird line\n")
        assert _wholesale_conversions(repo) == []
        violations = check_line_ending_consistency(repo)
        assert len(violations) == 1, violations
        assert "mixes conventions" in violations[0]


def test_the_live_tree_passes():
    """Both rules, against the repository this file lives in."""
    assert check_line_ending_consistency() == []
