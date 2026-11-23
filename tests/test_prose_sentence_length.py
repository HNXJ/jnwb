"""No prose sentence in the contributor and user entry pages runs past 40 words.

The splitter lives in `artifacts/evidence/0.2.17/sentence_length_17-129.py`; its docstring says
which Markdown it skips and where a sentence ends. The controls below show it flags a long
sentence, keeps an abbreviation inside its sentence, and skips code and tables, so a pass here
means the pages were read.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "artifacts" / "evidence" / "0.2.17" / "sentence_length_17-129.py"
PAGES = (".github/CONTRIBUTING.md", "README.md", "docs/quickstart.md")


def _load():
    spec = importlib.util.spec_from_file_location("sentence_length", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SL = _load()


@pytest.mark.parametrize("page", PAGES)
def test_no_sentence_over_the_limit(page):
    path = REPO_ROOT / page
    read = SL.sentences(path.read_text(encoding="utf-8"))
    assert len(read) >= 20, f"{page}: only {len(read)} sentences read"
    hits = SL.long_sentences(path)
    assert not hits, "\n".join(f"{page}:{ln}: {n} words: {s[:80]}" for ln, n, s in hits)


def test_a_41_word_sentence_is_flagged_and_a_40_word_one_is_not(tmp_path):
    page = tmp_path / "page.md"
    page.write_text(" ".join(["word"] * 40) + ".\n\n" + " ".join(["word"] * 41) + ".\n",
                    encoding="utf-8")
    assert [(ln, n) for ln, n, _ in SL.long_sentences(page)] == [(3, 41)]


def test_a_sentence_across_wrapped_lines_is_one_sentence(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("- " + " ".join(["a"] * 30) + "\n  " + " ".join(["b"] * 15) + ".\n",
                    encoding="utf-8")
    assert [(ln, n) for ln, n, _ in SL.long_sentences(page)] == [(1, 45)]


def test_abbreviations_do_not_end_a_sentence_and_periods_do():
    text = "Use a seed, e.g. 42, or i.e. none here. Next one. lower case starts."
    assert [s for _, s in SL.sentences(text)] == [
        "Use a seed, e.g. 42, or i.e. none here.", "Next one.", "lower case starts."]


def test_code_tables_headings_and_front_matter_are_skipped(tmp_path):
    long = " ".join(["word"] * 50)
    page = tmp_path / "page.md"
    page.write_text(f"---\ntitle: {long}\n---\n# {long}\n\n| {long} |\n\n```\n{long}\n```\n\n"
                    f"Text with `{long}` code.\n", encoding="utf-8")
    assert SL.long_sentences(page) == []
    assert [s for _, s in SL.sentences(page.read_text(encoding="utf-8"))] == [
        "Text with § code."]
