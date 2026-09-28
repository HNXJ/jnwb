"""`scripts/stack_edit.py` edits a stack file by bullet and refuses anything it cannot verify.

Every test runs on a temporary copy, in both CRLF and LF where the convention matters, and
compares exact bytes: a check that decoded and re-split the text would pass a rewrite of the
line endings.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stack_edit.py"
_spec = importlib.util.spec_from_file_location("_stack_edit", SCRIPT)
se = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = se  # dataclasses resolve their module through sys.modules
_spec.loader.exec_module(se)

LINES = [
    "# 9.9.1",
    "",
    "Intro paragraph.",
    "",
    "### ZZ-00 First group",
    "",
    "- ZZ-1: alpha bullet — one line.",
    "- ZZ-2: beta bullet with continuation.",
    "  deferred-9.9.2: beta waits.",
    "- ZZ-3: gamma bullet.",
    "",
    "# 9.9.2",
    "",
    "### ZZ-01 Second group",
    "",
    "- ZZ-1: alpha again, in the later section.",
    "- ZZ-4: delta bullet.",
    "",
]

NL = {"crlf": "\r\n", "lf": "\n"}


def _write(tmp_path, nl, lines=LINES, name="stack.md"):
    p = tmp_path / name
    p.write_bytes(nl.join(lines).encode("utf-8"))
    return p


def _expect(nl, lines):
    return nl.join(lines).encode("utf-8")


def _without(*drop):
    return [ln for i, ln in enumerate(LINES) if i not in drop]


def _text(tmp_path, *lines):
    p = tmp_path / "new.txt"
    p.write_bytes("\n".join(lines).encode("utf-8") + b"\n")
    return p


@pytest.fixture(params=["crlf", "lf"])
def nl(request):
    return NL[request.param]


def test_delete_preserves_every_other_byte(tmp_path, nl):
    p = _write(tmp_path, nl)
    se.edit(p, [lambda d: se.delete(d, "- ZZ-3", "9.9.1")])
    assert p.read_bytes() == _expect(nl, _without(9))


def test_delete_takes_continuation_lines_with_the_bullet(tmp_path, nl):
    p = _write(tmp_path, nl)
    se.edit(p, [lambda d: se.delete(d, "- ZZ-2")])
    assert p.read_bytes() == _expect(nl, _without(7, 8))


def test_delete_several_prefixes(tmp_path, nl):
    # The earlier bullet has a continuation line, so deleting front to back would shift the
    # later span onto the wrong lines.
    p = _write(tmp_path, nl)
    se.edit(p, [lambda d: se.delete_many(d, ["- ZZ-4", "- ZZ-2"])])
    assert p.read_bytes() == _expect(nl, _without(7, 8, 16))


def test_chained_deletes_resolve_against_the_original(tmp_path):
    p = _write(tmp_path, "\r\n")
    before = p.read_bytes()
    with pytest.raises(se.StackEditError, match="matches 2 bullets"):
        se.edit(p, [lambda d: se.delete(d, "- ZZ-1: alpha bullet"), lambda d: se.delete(d, "- ZZ-1: alpha")])
    assert p.read_bytes() == before


def test_refuses_deleting_a_bullet_that_holds_a_fence(tmp_path):
    raw = b"- ZZ-1: real\n  ```\n- ZZ-1: example in a fence\n```\n"
    p = tmp_path / "fence.md"
    p.write_bytes(raw)
    with pytest.raises(se.StackEditError, match="holds a code fence"):
        se.edit(p, [lambda d: se.delete_many(d, ["- ZZ-1:"])])
    assert p.read_bytes() == raw


def test_a_heading_inside_a_fence_is_not_a_section():
    lines = ["```", "# 9.9.1", "```", "# 9.9.1", "- ZZ-1: x", ""]
    assert se.section_range(lines, "9.9.1") == (4, 6)


def test_replace_refuses_lines_that_are_not_bullets():
    doc = se.parse(_expect("\n", LINES))
    with pytest.raises(se.StackEditError, match="not a bullet"):
        se.replace(doc, "- ZZ-3", ["plain text"])


def test_the_file_is_replaced_rather_than_rewritten_in_place(tmp_path):
    p = _write(tmp_path, "\r\n")
    ino = p.stat().st_ino
    se.edit(p, [lambda d: se.delete(d, "- ZZ-3")])
    assert p.stat().st_ino != ino


def test_refuses_when_the_temporary_file_does_not_hold_the_bytes(tmp_path, monkeypatch):
    p = _write(tmp_path, "\r\n")
    before = p.read_bytes()
    real = se.os.fdopen

    class Short:
        def __init__(self, fh):
            self.fh = fh

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.fh.close()

        def write(self, data):
            self.fh.write(data[:-1])

    monkeypatch.setattr(se.os, "fdopen", lambda fd, mode: Short(real(fd, mode)))
    with pytest.raises(se.StackEditError, match="differ"):
        se.edit(p, [lambda d: se.delete(d, "- ZZ-3")])
    assert p.read_bytes() == before
    assert sorted(x.name for x in tmp_path.iterdir()) == ["stack.md"]


def test_a_hash_led_continuation_stays_in_its_bullet():
    lines = ["- ZZ-3: gamma.", "  #45 is the ref", "- ZZ-4: delta.", ""]
    assert se.find(lines, "- ZZ-3") == (0, 2)


@pytest.mark.parametrize("prefix", ["- ZZ-", "- ZZ"], ids=["ends-in-hyphen", "hyphen-follows"])
def test_a_hyphen_continues_a_token(prefix):
    with pytest.raises(se.StackEditError, match="stops inside a token"):
        se.find(["- ZZ-10: x", ""], prefix)


def test_replace_from_file(tmp_path, nl):
    p = _write(tmp_path, nl)
    new = se.read_bullets(_text(tmp_path, "- ZZ-2: beta rewritten.", "  deferred-9.9.2: still."))
    se.edit(p, [lambda d: se.replace(d, "- ZZ-2", new)])
    want = LINES[:7] + ["- ZZ-2: beta rewritten.", "  deferred-9.9.2: still."] + LINES[9:]
    assert p.read_bytes() == _expect(nl, want)


def test_insert_after_lands_after_the_anchors_continuation(tmp_path, nl):
    p = _write(tmp_path, nl)
    new = se.read_bullets(_text(tmp_path, "- ZZ-9: new bullet."))
    se.edit(p, [lambda d: se.insert_after(d, "- ZZ-2", new)])
    want = LINES[:9] + ["- ZZ-9: new bullet."] + LINES[9:]
    assert p.read_bytes() == _expect(nl, want)


def test_sub_replaces_exactly_one_occurrence(tmp_path, nl):
    p = _write(tmp_path, nl)
    se.edit(p, [lambda d: se.sub(d, "- ZZ-2", "beta waits", "beta is held")])
    want = list(LINES)
    want[8] = "  deferred-9.9.2: beta is held."
    assert p.read_bytes() == _expect(nl, want)


@pytest.mark.parametrize("old", ["absent", "beta"])
def test_sub_refuses_zero_or_repeated_occurrence(tmp_path, old):
    p = _write(tmp_path, "\r\n")
    before = p.read_bytes()
    with pytest.raises(se.StackEditError, match="need exactly 1"):
        se.edit(p, [lambda d: se.sub(d, "- ZZ-2", old, "x")])
    assert p.read_bytes() == before


def test_refuses_a_prefix_matching_no_bullet(tmp_path):
    p = _write(tmp_path, "\r\n")
    with pytest.raises(se.StackEditError, match="matches 0 bullets"):
        se.edit(p, [lambda d: se.delete(d, "- ZZ-404")])


@pytest.mark.parametrize(
    "op",
    [lambda d: se.delete(d, "- ZZ-1"), lambda d: se.sub(d, "- ZZ-1", "alpha", "omega")],
    ids=["delete", "sub"],
)
def test_refuses_a_prefix_matching_two_bullets(tmp_path, op):
    p = _write(tmp_path, "\r\n")
    before = p.read_bytes()
    with pytest.raises(se.StackEditError, match="matches 2 bullets"):
        se.edit(p, [op])
    assert p.read_bytes() == before


def test_refuses_a_prefix_matching_a_continuation_line(tmp_path):
    p = _write(tmp_path, "\r\n")
    with pytest.raises(se.StackEditError, match="continuation line"):
        se.edit(p, [lambda d: se.delete(d, "  deferred-9.9.2")])


@pytest.mark.parametrize("raw", [b"- a\r\n- b\n", b"- a\r- b\r\n"])
def test_refuses_mixed_line_endings(tmp_path, raw):
    p = tmp_path / "mixed.md"
    p.write_bytes(raw)
    with pytest.raises(se.StackEditError, match="mixed|bare CR"):
        se.edit(p, [lambda d: se.delete(d, "- a")])
    assert p.read_bytes() == raw


def test_section_selects_one_of_two_same_prefix_bullets(tmp_path, nl):
    p = _write(tmp_path, nl)
    se.edit(p, [lambda d: se.delete(d, "- ZZ-1", "# 9.9.2")])
    assert p.read_bytes() == _expect(nl, _without(15))


def test_section_ends_at_the_next_heading_of_its_level_or_higher(tmp_path):
    lo, hi = se.section_range(LINES, "ZZ-00 First group")
    assert (lo, hi) == (5, 11)
    lo, hi = se.section_range(LINES, "9.9.1")
    assert (lo, hi) == (1, 11)
    with pytest.raises(se.StackEditError, match="matches 0 bullets"):
        se.find(LINES, "- ZZ-4", "ZZ-00 First group")


def test_section_compares_heading_level():
    assert se.section_range(LINES, "# 9.9.2") == (12, 18)
    with pytest.raises(se.StackEditError, match="matches 0 headings"):
        se.section_range(LINES, "## 9.9.2")


def test_refuses_a_section_heading_that_appears_twice():
    lines = LINES + ["### ZZ-00 First group", "", "- ZZ-7: late.", ""]
    with pytest.raises(se.StackEditError, match="matches 2 headings"):
        se.find(lines, "- ZZ-3", "ZZ-00 First group")


def test_refuses_a_prefix_that_stops_inside_a_token(tmp_path):
    # The shorter id is gone and a longer one that extends it remains: the stale prefix must
    # refuse rather than delete the longer id's bullet.
    lines = ["# 9.9.1", "", "- ZZ-10: ten.", "- ZZ-2: two.", ""]
    p = _write(tmp_path, "\r\n", lines)
    before = p.read_bytes()
    with pytest.raises(se.StackEditError, match="stops inside a token"):
        se.edit(p, [lambda d: se.delete(d, "- ZZ-1")])
    assert p.read_bytes() == before
    se.edit(p, [lambda d: se.delete(d, "- ZZ-10:")])
    assert p.read_bytes() == _expect("\r\n", ["# 9.9.1", "", "- ZZ-2: two.", ""])


@pytest.mark.parametrize(
    "prefixes, message",
    [
        (["- ZZ-1: alpha bullet", "- ZZ-1: alpha"], "matches 2 bullets"),
        (["- ZZ-2:", "- ZZ-2: beta"], "same bullet"),
    ],
    ids=["later-prefix-ambiguous-in-original", "two-prefixes-one-bullet"],
)
def test_several_prefixes_resolve_against_the_original(tmp_path, prefixes, message):
    p = _write(tmp_path, "\r\n")
    before = p.read_bytes()
    with pytest.raises(se.StackEditError, match=message):
        se.edit(p, [lambda d: se.delete_many(d, prefixes)])
    assert p.read_bytes() == before


def test_bullets_inside_a_code_fence_are_not_matched(tmp_path, nl):
    lines = ["# 9.9.1", "", "```", "- ZZ-3: an example", "```", "", "- ZZ-3: real.", ""]
    p = _write(tmp_path, nl, lines)
    se.edit(p, [lambda d: se.delete(d, "- ZZ-3:")])
    assert p.read_bytes() == _expect(nl, lines[:6] + lines[7:])


def test_refuses_when_the_file_changes_during_the_edit(tmp_path):
    p = _write(tmp_path, "\r\n")
    other = b"- written by someone else\r\n"

    def op(doc):
        se.delete(doc, "- ZZ-3")
        p.write_bytes(other)

    with pytest.raises(se.StackEditError, match="changed on disk"):
        se.edit(p, [op])
    assert p.read_bytes() == other
    assert sorted(x.name for x in tmp_path.iterdir()) == ["stack.md"]


def test_success_leaves_no_temporary_file(tmp_path):
    p = _write(tmp_path, "\r\n")
    se.edit(p, [lambda d: se.delete(d, "- ZZ-3")])
    assert sorted(x.name for x in tmp_path.iterdir()) == ["stack.md"]


@pytest.mark.parametrize(
    "tail",
    [["", "  stray"], ["", "", "  stray"], ["", "\tstray"], ["\tstray"], [" stray"]],
    ids=["blank-two-space", "two-blanks", "blank-tab", "tab", "one-space"],
)
def test_refuses_a_blank_line_followed_by_an_indented_line(tmp_path, tail):
    lines = ["# 9.9.1", "", "- ZZ-3: gamma."] + tail + [""]
    p = _write(tmp_path, "\r\n", lines)
    with pytest.raises(se.StackEditError, match="ambiguous"):
        se.edit(p, [lambda d: se.delete(d, "- ZZ-3")])


def test_a_heading_ends_a_bullet():
    lines = ["- ZZ-3: gamma.", "  ## not a continuation", ""]
    assert se.find(lines, "- ZZ-3") == (0, 1)


def test_a_thematic_break_is_not_a_bullet():
    with pytest.raises(se.StackEditError, match="non-bullet line"):
        se.find(["- - -", ""], "- -")


@pytest.mark.parametrize(
    "prefix, old, new",
    [("- ZZ-3", "- ZZ-3", "ZZ-3"), ("- ZZ-2", "deferred", "```deferred")],
    ids=["first-line-no-longer-a-bullet", "fence-inside-bullet"],
)
def test_sub_refuses_an_edit_that_breaks_the_bullet(tmp_path, prefix, old, new):
    p = _write(tmp_path, "\r\n")
    before = p.read_bytes()
    with pytest.raises(se.StackEditError, match="not a bullet|code fence"):
        se.edit(p, [lambda d: se.sub(d, prefix, old, new)])
    assert p.read_bytes() == before


def test_a_failing_later_op_writes_nothing(tmp_path):
    p = _write(tmp_path, "\r\n")
    before = p.read_bytes()
    with pytest.raises(se.StackEditError):
        se.edit(p, [lambda d: se.delete(d, "- ZZ-3"), lambda d: se.delete(d, "- ZZ-404")])
    assert p.read_bytes() == before


def test_replacement_text_must_be_bullets(tmp_path):
    with pytest.raises(se.StackEditError, match="must start with"):
        se.read_bullets(_text(tmp_path, "not a bullet"))
    with pytest.raises(se.StackEditError, match="neither a bullet"):
        se.read_bullets(_text(tmp_path, "- ok", "unindented tail"))


def _cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, timeout=60
    )


def test_cli_dry_run_prints_a_diff_and_writes_nothing(tmp_path):
    p = _write(tmp_path, "\r\n")
    before = p.read_bytes()
    r = _cli("--file", str(p), "--dry-run", "delete", "- ZZ-3")
    assert r.returncode == 0, r.stderr
    assert b"-- ZZ-3: gamma bullet." in r.stdout
    assert p.read_bytes() == before


def test_cli_refusal_exits_2_and_writes_nothing(tmp_path):
    p = _write(tmp_path, "\r\n")
    before = p.read_bytes()
    r = _cli("--file", str(p), "delete", "- ZZ-3", "- ZZ-1")
    assert r.returncode == 2
    assert b"refused" in r.stderr and b"matches 2 bullets" in r.stderr
    assert p.read_bytes() == before


def test_cli_insert_after_writes_the_file(tmp_path):
    p = _write(tmp_path, "\r\n")
    new = _text(tmp_path, "- ZZ-9: new.")
    r = _cli("--file", str(p), "--section", "9.9.2", "insert-after", "- ZZ-1", "--from-file", str(new))
    assert r.returncode == 0, r.stderr
    assert p.read_bytes() == _expect("\r\n", LINES[:16] + ["- ZZ-9: new."] + LINES[16:])
