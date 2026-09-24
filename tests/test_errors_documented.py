"""The errors a first-time reader meets were explained nowhere but the generated
reference.

`docs/api.md` is generated from `jnwb.__all__`, so it contains every export by
construction. Gate 5 searched every `docs/*.md`, `api.md` included, and therefore asserted
that every export appears in a file guaranteed to contain every export. It passed while
twelve symbols appeared on no page a person had written:

    NWBInspectError  AmbiguousAcquisitionError  AcquisitionNotFoundError
    ChannelIndexError  UnitNotFoundError  NWBEventError  IntervalTableNotFoundError
    resolve_acquisition  resolve_interval_table  EventTable  InvalidOnsetValueError
    DETECTION_TAILS

Nine of the twelve are the NWB resolvers and the error types they raise -- which is to say,
everything a reader meets on their first unfamiliar file.

`docs/errors.md` is the repair, and this file is what keeps it true. `AmbiguousIntervalTableError`
is the model it follows: explained in three places before it can fire.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import jnwb
from jnwb._lazy_exports import OPTIONAL_SUBMODULES

DOCS = Path(__file__).resolve().parents[1] / "docs"
GENERATED = "api.md"


def _hand_written_pages():
    return sorted(p for p in DOCS.rglob("*.md") if p.name != GENERATED)


def _hand_written_text():
    return "\n".join(p.read_text(encoding="utf-8") for p in _hand_written_pages())


def _exported_errors():
    out = []
    for name in jnwb.__all__:
        if name in OPTIONAL_SUBMODULES:
            # A submodule, so never an error class; importing it needs its optional extra.
            continue
        obj = getattr(jnwb, name, None)
        if isinstance(obj, type) and issubclass(obj, BaseException):
            out.append(name)
    return sorted(out)


def _mentions(text, name):
    return re.search(rf"\b{re.escape(name)}\b", text) is not None


class TestEveryErrorClassIsExplained:
    """The discriminator for 05-41."""

    @pytest.mark.parametrize("name", _exported_errors())
    def test_the_error_appears_on_a_hand_written_page(self, name):
        assert _mentions(_hand_written_text(), name), (
            f"jnwb.{name} appears only in the generated docs/{GENERATED}")

    @pytest.mark.parametrize("name", _exported_errors())
    def test_the_error_appears_on_the_errors_page_specifically(self, name):
        """Scattered mentions are not an index. One page lists them all."""
        page = (DOCS / "errors.md").read_text(encoding="utf-8")
        assert _mentions(page, name)

    def test_there_are_thirteen_of_them(self):
        """A count that fails when an error class is added without a paragraph. If this
        fails, add the class to docs/errors.md and change the number here."""
        assert len(_exported_errors()) == 13, _exported_errors()

    def test_both_base_classes_are_named_so_a_caller_can_catch_a_family(self):
        page = (DOCS / "errors.md").read_text(encoding="utf-8")
        assert "except jnwb.NWBInspectError" in page
        assert _mentions(page, "NWBEventError")


class TestTheResolversAreExplained:
    """They are how a caller finds the name the errors ask for, and both were undocumented."""

    @pytest.mark.parametrize("name", ["resolve_acquisition", "resolve_interval_table"])
    def test_the_resolver_is_on_the_errors_page(self, name):
        assert _mentions((DOCS / "errors.md").read_text(encoding="utf-8"), name)


class TestTheErrorsPageIsReachable:

    def test_the_index_links_to_it(self):
        index = (DOCS / "index.md").read_text(encoding="utf-8")
        assert "errors.md" in index

    def test_it_is_in_the_mkdocs_nav(self):
        """A page outside the nav is not on the built site, whatever the index links."""
        nav = (DOCS.parent / "mkdocs.yml").read_text(encoding="utf-8")
        assert "errors.md" in nav

    def test_every_hand_written_page_is_in_the_nav(self):
        """The same failure generalized: a page nobody navigates to is not documentation.
        `api.md` is listed twice on purpose, under Getting started and API Reference."""
        nav = (DOCS.parent / "mkdocs.yml").read_text(encoding="utf-8")
        missing = [p.relative_to(DOCS).as_posix() for p in DOCS.rglob("*.md")
                   if p.relative_to(DOCS).as_posix() not in nav]
        assert missing == [], missing

    def test_the_page_exists_and_is_not_a_stub(self):
        page = DOCS / "errors.md"
        assert page.exists()
        assert len(page.read_text(encoding="utf-8")) > 2000


class TestEveryExportIsWrittenAboutSomewhere:
    """05-41's accept condition: the Gate 5 check, exercised here so a `pytest` run sees
    it too, not only a gate invocation."""

    def test_no_export_lives_only_in_the_generated_reference(self):
        text = "\n".join(
            p.read_text(encoding="utf-8")
            for p in sorted(DOCS.glob("*.md")) if p.name != GENERATED
        )
        missing = [s for s in jnwb.__all__ if not _mentions(text, s)]
        assert missing == [], missing

    def test_the_gate_agrees(self):
        import sys

        sys.path.insert(0, str(DOCS.parent / "scripts"))
        from harness_gate import check_public_symbols_documented

        assert check_public_symbols_documented(DOCS.parent) == []

    def test_the_gate_would_fail_if_the_generated_reference_were_counted(self):
        """The reason the old gate was vacuous: api.md alone satisfies it. This pins that
        the exclusion is what makes the check mean anything -- remove it and the check
        cannot fail, whatever the hand-written pages say."""
        generated = (DOCS / GENERATED).read_text(encoding="utf-8")
        assert all(_mentions(generated, s) for s in jnwb.__all__)


class TestTheMessagesOnThePageAreTheRealOnes:
    """A troubleshooting page whose messages have drifted is worse than none: a reader
    greps for what they saw and finds nothing."""

    QUOTED = [
        "Several continuous series present:",
        "Pass name=<series> explicitly.",
        "not found. Available:",
        "out of range for series",
        "Cannot tell which axis of series",
        "out of range for",
        "Several interval tables and none named 'trials':",
        "Pass table=<name> explicitly.",
        "not found. Columns:",
        "Non-finite onset at index",
        "Missing onset in column",
        "jnwb does not synthesize required metadata",
    ]

    @staticmethod
    def _page_text():
        page = (DOCS / "errors.md").read_text(encoding="utf-8")
        return page.replace("&lt;", "<").replace("&gt;", ">")

    @staticmethod
    def _source_text():
        source_dir = DOCS.parent / "jnwb"
        return "\n".join(p.read_text(encoding="utf-8")
                         for p in sorted(source_dir.glob("*.py")))

    @pytest.mark.parametrize("fragment", QUOTED)
    def test_each_quoted_fragment_is_in_the_source(self, fragment):
        """A page that quotes a message the code no longer produces is worse than no
        page: the reader greps for what they saw and finds nothing."""
        assert fragment in self._source_text(), fragment

    @pytest.mark.parametrize("fragment", QUOTED)
    def test_each_quoted_fragment_is_on_the_page(self, fragment):
        assert fragment in self._page_text(), fragment

    def test_detection_tails_is_quoted_correctly(self):
        """The page states the accepted values; they must be the ones the code accepts."""
        page = (DOCS / "05_artifact_detection_and_repair.md").read_text(encoding="utf-8")
        normalized = page.replace('"', "'")
        assert str(jnwb.DETECTION_TAILS) in normalized, jnwb.DETECTION_TAILS


class TestTheGateWouldNoticeAMissingPage:
    """Gate 5 was vacuous, not absent. A gate that cannot fail is the defect, so the
    discriminator is that it *does* fail on docs that are genuinely missing a symbol --
    which it cannot do while the generated reference counts."""

    @staticmethod
    def _root_with_only_the_generated_reference(tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / GENERATED).write_text(
            (DOCS / GENERATED).read_text(encoding="utf-8"), encoding="utf-8")
        return tmp_path

    def test_docs_containing_only_the_generated_reference_are_rejected(self, tmp_path):
        import sys

        sys.path.insert(0, str(DOCS.parent / "scripts"))
        from harness_gate import check_public_symbols_documented

        root = self._root_with_only_the_generated_reference(tmp_path)
        violations = check_public_symbols_documented(root)
        assert len(violations) == len(jnwb.__all__), len(violations)
        assert all("UNDOCUMENTED_PUBLIC_SYMBOL" in v for v in violations)

    def test_a_page_that_covers_everything_is_accepted(self, tmp_path):
        """The complement: the gate is not simply always-failing now."""
        import sys

        sys.path.insert(0, str(DOCS.parent / "scripts"))
        from harness_gate import check_public_symbols_documented

        root = self._root_with_only_the_generated_reference(tmp_path)
        (root / "docs" / "everything.md").write_text(
            "\n".join(jnwb.__all__), encoding="utf-8")
        assert check_public_symbols_documented(root) == []

    def test_a_substring_of_another_symbol_is_not_credited_to_it(self, tmp_path):
        """`Dataset` is a substring of `AlignedDataset`, and `rdm` of `rdm_similarity`.
        Under a plain `in` test a page that documents only the longer name is credited
        with the shorter one, which is how a symbol goes undocumented while the gate is
        green. The match is whole-word for exactly this reason."""
        import sys

        sys.path.insert(0, str(DOCS.parent / "scripts"))
        from harness_gate import check_public_symbols_documented

        shadowed = ["Dataset", "rdm"]
        for short in shadowed:
            assert any(short in other and short != other for other in jnwb.__all__), short

        root = self._root_with_only_the_generated_reference(tmp_path)
        (root / "docs" / "everything.md").write_text(
            "\n".join(s for s in jnwb.__all__ if s not in shadowed), encoding="utf-8")
        violations = check_public_symbols_documented(root)
        assert len(violations) == len(shadowed), violations
        for short in shadowed:
            assert any(f"'jnwb.{short}'" in v for v in violations), short

    def test_one_missing_symbol_is_reported_by_name(self, tmp_path):
        import sys

        sys.path.insert(0, str(DOCS.parent / "scripts"))
        from harness_gate import check_public_symbols_documented

        root = self._root_with_only_the_generated_reference(tmp_path)
        (root / "docs" / "everything.md").write_text(
            "\n".join(s for s in jnwb.__all__ if s != "ChannelIndexError"),
            encoding="utf-8")
        violations = check_public_symbols_documented(root)
        assert len(violations) == 1
        assert "ChannelIndexError" in violations[0]
