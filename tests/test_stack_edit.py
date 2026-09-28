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
    p = _write(tmp_path, nl)
    se.edit(p, [lambda d: se.delete(d, "- ZZ-3"), lambda d: se.delete(d, "- ZZ-4")])
    assert p.read_bytes() == _expect(nl, _without(9, 16))


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
