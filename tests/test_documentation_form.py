"""Guards for the readers behind the documentation form rules, and the Length section's counts.

The rules (F1, F5, N1, N2, N3, N5, G2 and the others a machine can settle) are implemented once,
in `scripts/docs_form_gate.py`, and `tests/test_docs_form_gate.py` runs them on the live tree and
on seeded fixtures. This module holds what the gate cannot say about itself: that each reader it
rules through reaches what it claims to read. Each assertion is paired with the bypass it is
written against, because this module's whole failure mode is a green check over an unread corpus:

- The vocabulary table stops parsing, yielding zero rows, and every page trivially conforms.
  Held by `test_the_vocabulary_list_parses`, which requires rows and requires named concepts.
- The corpus collapses to nothing, or to the generated page only, and there is no prose to find
  a violation in. Held by `test_the_corpus_reaches_the_authored_pages` and
  `test_the_corpus_reaches_the_three_surfaces_it_used_to_exclude`.
- `prose` strips too much, the whole page and not just its code, and the scan runs over an empty
  string. Held by `test_stripping_code_leaves_the_prose_behind`.
- The matcher never matches anything, because of a word-boundary, escaping or case bug, so no
  row can ever fire. Held by `test_every_preferred_term_occurs_in_the_prose`: each row's
  *preferred* form must be findable by the same matcher that hunts its superseded ones.
- The checker finds violations but reports them without saying where. Held by
  `test_a_reintroduced_superseded_term_is_named_with_its_page`: seed one page with a superseded
  term and require the page and the term back.
- The navigation reader returns no groups, and N1 and N2 hold over an empty list. Held by
  `test_the_nav_is_parsed_at_all`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts import docs_form_gate as gate  # noqa: E402

DOCS = REPO_ROOT / "docs"
MKDOCS = REPO_ROOT / "mkdocs.yml"
GENERATED = gate.GENERATED
VOCABULARY_HEADING = gate.VOCABULARY_HEADING
vocabulary_violations = gate.vocabulary_violations
_prose = gate.prose
_word = gate.word


def _corpus() -> list[tuple[str, str]]:
    return gate.corpus(REPO_ROOT)


def _vocabulary() -> list[gate.VocabularyRow]:
    return gate.parse_vocabulary((REPO_ROOT / gate.CONTRACT).read_text(encoding="utf-8"))


VOCABULARY = _vocabulary()


# ------------------------------------------------------------------- corpus guards


def test_the_corpus_reaches_the_authored_pages():
    """Bypass this is written against: the corpus is empty, or is the generated page
    alone, so every scan below passes over nothing."""
    names = {name for name, _ in _corpus()}
    assert GENERATED not in names, (
        "the generated reference is scanned under its full path `docs/api.md`, never under "
        "its bare name -- the distinction is what says the fix goes to the generator"
    )
    tutorials = {n for n in names if n.startswith("tutorials/")}
    assert len(tutorials) >= 9, (
        f"the tutorial pages fell out of the corpus: {sorted(tutorials)}; their own prose is "
        "read, and the script each includes is read as its own surface"
    )
    for expected in ("index.md", "common_mistakes.md", "errors.md", "quickstart.md",
                     "10_operation_specifications.md", "documentation_form.md",
                     "README.md"):
        assert expected in names, f"{expected} fell out of the corpus"
    assert len(names) >= 18, f"only {len(names)} pages collected: {sorted(names)}"

    words = sum(len(_prose(text).split()) for _, text in _corpus())
    assert words > 8000, f"only {words} words of prose; the corpus has collapsed"


def test_the_corpus_reaches_the_three_surfaces_it_used_to_exclude():
    """P-95: a widening that silently globs nothing looks exactly like a clean tree.

    Each of the three additions is asserted to be present and non-trivial, because an empty
    glob returns an empty list and every scan above then passes over it without a word.
    """
    corpus = _corpus()
    names = {name for name, _ in corpus}

    skills = [n for n in names if n.startswith("skills/")]
    tutorials = [n for n in names if n.startswith("examples/tutorials/")]
    comments = [n for n in names if n.endswith("(code comments)")]

    assert len(skills) >= 8, f"the skill corpus collapsed to {sorted(skills)}"
    assert len(tutorials) >= 9, f"the tutorial corpus collapsed to {sorted(tutorials)}"
    assert comments, "no fenced code comments collected from any page"
    assert f"docs/{GENERATED}" in names, "the generated reference fell out of the corpus"

    for surface, prefix in (("skills", "skills/"),
                            ("tutorials", "examples/tutorials/"),
                            ("generated reference", f"docs/{GENERATED}")):
        words = sum(len(_prose(text).split())
                    for name, text in corpus if name.startswith(prefix))
        assert words > 100, f"the {surface} surface contributes only {words} words"


@pytest.mark.parametrize(
    "label, text",
    [
        ("skills/jnwb-fake/SKILL.md", "This normalises the array before use.\n"),
        ("examples/tutorials/99_fake.py", "# Uses the neighbouring channel.\n"),
        ("docs/api.md", "Returns the colour of the trace.\n"),
        ("fake.md (code comments)", " honours the declared unit\n"),
    ],
)
def test_a_superseded_form_on_each_widened_surface_is_caught(label: str, text: str):
    """The discriminator for the widening: each surface is scanned, not merely listed.

    Driven through `vocabulary_violations` with a constructed page rather than by editing a
    real one, so the test proves the rule applies to that surface without depending on a
    violation existing there -- and the four live ones have been repaired, so none does.
    """
    violations = vocabulary_violations([(label, text)], _vocabulary())
    assert violations, f"a superseded form on {label} was not caught"


REFERENCE_TABLE = (
    "| Reference | Result implemented | Functions |\n"
    "|---|---|---|\n"
    "| Doe, J. (2002). Analysing flows. *J* 1, 1-2. | {claim} | `f` |\n"
)


def test_a_cited_title_keeps_its_spelling_and_the_claim_cell_does_not():
    # The citation cell is the source's wording; the claim cell beside it is jnwb's prose.
    assert "analysing" in str(_vocabulary()).lower(), "the planted form must be a superseded one"
    title_only = REFERENCE_TABLE.format(claim="The estimate as written")
    assert vocabulary_violations([("references.md", title_only)], _vocabulary()) == []
    in_claim = REFERENCE_TABLE.format(claim="Analysing the estimate")
    assert vocabulary_violations([("references.md", in_claim)], _vocabulary())
    other_table = title_only.replace("| Reference |", "| Source |", 1)
    assert vocabulary_violations([("references.md", other_table)], _vocabulary())


def test_stripping_code_leaves_the_prose_behind():
    """Bypass: `_prose` eats the page, and there is nothing left to violate a rule in."""
    text = (DOCS / "common_mistakes.md").read_text(encoding="utf-8")
    prose = _prose(text)
    assert "Jensen" in prose, "_prose removed ordinary body text"
    assert "np.mean" not in prose, "_prose left a fenced code block behind"
    assert "aggregate_to_db" not in prose, "_prose left an inline code span behind"
    assert len(prose.split()) > 400, "_prose stripped almost everything"


# --------------------------------------------------------------- F5: one surface form


def test_the_vocabulary_list_parses():
    """Bypass: the table stops parsing, zero rows come back, and F5 cannot fail."""
    assert VOCABULARY, (
        f"no vocabulary rows parsed from docs/documentation_form.md under "
        f"{VOCABULARY_HEADING!r}; F5 has nothing to check against")
    assert len(VOCABULARY) >= 6, f"only {len(VOCABULARY)} rows: {VOCABULARY}"
    accepted = {term.lower() for row in VOCABULARY for term in row.preferred}
    forbidden = {term.lower() for row in VOCABULARY for term in row.superseded}
    for required in ("artifact", "normalized", "layer"):
        assert required in accepted, (
            f"the vocabulary list lost the row accepting {required!r}: {sorted(accepted)}")
    for required in ("artefact", "normalised", "lamina"):
        assert required in forbidden, (
            f"the vocabulary list stopped forbidding {required!r}: {sorted(forbidden)}")


def test_every_vocabulary_term_is_backticked():
    """The contract names superseded forms. If they were bare, `_prose` would keep them
    and the contract page would report itself as violating its own rule."""
    section = gate.vocabulary_section(
        (DOCS / "documentation_form.md").read_text(encoding="utf-8"))
    assert section is not None, (
        f"docs/documentation_form.md carries no {VOCABULARY_HEADING!r} section")
    stray = [row.concept for row in VOCABULARY
             for term in (*row.preferred, *row.superseded)
             if f"`{term}`" not in section]
    assert not stray, f"vocabulary terms written without backticks: {stray}"


def test_no_vocabulary_term_collides_with_another_rows_preferred_form():
    """A superseded form that is a whole word inside another row's preferred form would
    make that row's correct usage unreportable, or report it forever."""
    collisions = []
    for row in VOCABULARY:
        for other in VOCABULARY:
            if other is row:
                continue
            for bad in row.superseded:
                for good in other.preferred:
                    if _word(bad).search(good):
                        collisions.append(f"{row.concept}:{bad} inside "
                                          f"{other.concept}:{good}")
    assert not collisions, collisions


def test_every_preferred_term_occurs_in_the_prose():
    """Bypass, and the strongest one: the matcher is broken and finds nothing at all, so
    no superseded form is ever reported and F5 passes vacuously.

    Each row's preferred form is hunted with the same matcher used against its superseded
    forms. A row whose preferred form cannot be found anywhere is untestable -- either the
    concept is not actually discussed, or the matcher does not work -- and either way the
    row is not evidence of anything.
    """
    prose = "\n".join(_prose(text) for _, text in _corpus())
    unfindable = [f"{row.concept}: {row.preferred!r}" for row in VOCABULARY
                  if not any(_word(good).search(prose) for good in row.preferred)]
    assert not unfindable, (
        "vocabulary rows where no accepted form appears anywhere, so the row proves "
        f"nothing: {unfindable}")


@pytest.mark.parametrize("row", VOCABULARY, ids=lambda r: r.concept)
def test_a_reintroduced_superseded_term_is_named_with_its_page(row):
    """06-49's discriminator, per row: reintroduce a superseded term on one page and
    require the check to name the page and the term.

    Seeded in memory rather than on disk -- a test that writes into `docs/` and restores
    it leaves the tree mutated when it fails.
    """
    seeded = [("seeded_page.md", f"A sentence using {row.superseded[0]} in prose.")]
    reported = vocabulary_violations(seeded, VOCABULARY)
    assert any("seeded_page.md" in r and row.superseded[0] in r for r in reported), (
        f"seeding {row.superseded[0]!r} produced {reported}")


def test_the_discriminator_would_not_fire_on_the_preferred_form():
    """The other half: the seeded check must be sensitive to the superseded form, not to
    any sentence at all."""
    assert VOCABULARY, "the vocabulary contract parsed to no rows"
    for row in VOCABULARY:
        for good in row.preferred:
            clean = [("clean_page.md", f"A sentence using {good} in prose.")]
            assert not vocabulary_violations(clean, VOCABULARY), (
                f"the accepted form {good!r} was reported as a violation")


# ---------------------------------------------------------------------- F1: headings


def test_the_heading_check_can_see_a_heading_at_all():
    """Bypass: the fence stripper removes the whole page and F1 counts zero of
    everything. A real page must still show its real headings."""
    text = (DOCS / "common_mistakes.md").read_text(encoding="utf-8")
    headings = [line for _, line in gate.unfenced_lines(text) if line.startswith("### ")]
    assert len(headings) > 5, f"only {len(headings)} third-level headings survived"


# ---------------------------------------------------------------------- N1, N2: reader


def test_the_nav_is_parsed_at_all():
    """Bypass: `nav:` fails to parse, no groups come back, and N1 and N2 hold over an
    empty list."""
    groups = gate.nav_groups(MKDOCS)
    assert len(groups) >= 4, f"only {len(groups)} nav groups parsed"
    pages = [p for _, children in groups for p in gate.pages_under(children)]
    assert len(pages) >= 25, f"only {len(pages)} nav pages parsed"


# ------------------------------------------------------------------------ Length

_NUMBER_WORDS = {w: n for n, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen".split())}
_KIND_ROW = re.compile(r"^\| (.+?) \| (\d+) words \| (.+?) \|$", re.M)
_EXCESS_ROW = re.compile(r"^\| `(\w+)` \| (\d+) \|", re.M)
_PAGE_RANGE = re.compile(r"`(\d\d)`–`(\d\d)`")


def _wc_words(path: Path) -> int:
    """The `wc -w` count the Length section says it measured: runs between ASCII whitespace."""
    return len(path.read_bytes().split())


def _kind_pages(cell: str, docs: Path) -> list[Path]:
    pages = [page for lo, hi in _PAGE_RANGE.findall(cell) for n in range(int(lo), int(hi) + 1)
             for page in sorted(docs.glob(f"{n:02d}_*.md"))]
    for name in re.findall(r"`([^`]+)`", _PAGE_RANGE.sub("", cell)):
        pages.append(docs / (name if name.endswith(".md") else f"{name}.md"))
    return pages


def length_claim_mismatches(docs: Path) -> list[str]:
    """Every word count and page tally the Length section states, recomputed from the pages."""
    text = (docs / "documentation_form.md").read_text(encoding="utf-8")
    section = text.split("\n## Length\n", 1)[1].split("\n## ", 1)[0]
    kinds, wrong, over = _KIND_ROW.findall(section), [], {}
    assert len(kinds) >= 3, f"only {len(kinds)} ceiling rows parsed; the parser is wrong"
    for kind, ceiling, why in kinds:
        pages = _kind_pages(kind, docs)
        assert pages and all(p.is_file() for p in pages), f"{kind} names a missing page"
        counts = {p.stem: _wc_words(p) for p in pages}
        over.update({name: n for name, n in counts.items() if n > int(ceiling)})
        for name, stated in re.findall(r"`(\w+)` at (\d+)", why):
            if counts[name] != int(stated):
                wrong.append(f"`{name}` is stated at {stated} words and measures {counts[name]}")
        tally = re.search(r"(\w+) of the (\w+) sit under it", why)
        under = sum(n <= int(ceiling) for n in counts.values())
        if tally and (_NUMBER_WORDS[tally[1]], _NUMBER_WORDS[tally[2]]) != (under, len(counts)):
            wrong.append(f"'{tally[0]}': {under} of {len(counts)} sit under {ceiling}")
    table = {name: int(n) for name, n in _EXCESS_ROW.findall(section)}
    if set(table) != set(over):
        wrong.append(f"over their ceiling: {sorted(over)}; the table lists {sorted(table)}")
    wrong += [f"`{name}` is tabled at {n} words and measures {over[name]}"
              for name, n in table.items() if name in over and over[name] != n]
    stated = re.search(r"(\w+) pages sit over their ceiling", section)
    if not stated or _NUMBER_WORDS.get(stated[1].lower()) != len(over):
        wrong.append(f"{len(over)} pages sit over their ceiling; the section says otherwise")
    return wrong


def test_the_length_section_states_what_the_pages_measure():
    """Counts in prose go stale silently; these are recomputed on every run."""
    assert length_claim_mismatches(DOCS) == []


# ------------------------------------------- figures embedded in the page, not linked

#: A markdown link: a `[` not preceded by `!`, so an image (`![alt](file)`) is not one.
_MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\s]+)\)")
_FIGURE_FILE = re.compile(r"\.(?:png|svg|html)$", re.IGNORECASE)


def linked_figures(pages: list[Path], root: Path) -> list[str]:
    """`page -> target` for each markdown link in `pages` whose target names a PNG, SVG or HTML
    file. The fragment and the query are stripped before the suffix is read; fenced code is not
    rendered, so it is not read."""
    found = []
    for page in pages:
        for _, line in gate.unfenced_lines(page.read_text(encoding="utf-8")):
            for target in _MARKDOWN_LINK.findall(line):
                if _FIGURE_FILE.search(re.split(r"[#?]", target, maxsplit=1)[0]):
                    found.append(f"{page.relative_to(root).as_posix()} -> {target}")
    return found


def html_in_assets(assets: Path) -> list[str]:
    """The HTML files under `assets`, by path relative to it. An interactive output is published
    on the dashboard, not kept among a page's assets."""
    return [p.relative_to(assets).as_posix() for p in sorted(assets.rglob("*.html"))]


def test_figures_are_embedded_not_linked():
    """Bypass: a page links to a figure file, and the reader leaves the page to open it. The page
    count guards an empty scan."""
    pages = sorted(DOCS.rglob("*.md"))
    assert len(pages) >= 20, f"only {len(pages)} pages under docs/; the scan read nothing"
    linked = linked_figures(pages, DOCS)
    html = html_in_assets(DOCS / "assets")
    assert not linked, f"links to figure files, to embed as images instead: {linked}"
    assert not html, f"HTML files under docs/assets/, to publish on the dashboard: {html}"


def test_the_link_check_reports_a_linked_png_and_html_and_not_an_embedded_figure(tmp_path):
    """Bypass: an image is read as a link, the fragment defeats the suffix test, or a fenced
    example is reported. One planted page holds each case."""
    page = tmp_path / "planted.md"
    page.write_text(
        "![embedded](assets/fig.png#only-light)\n"
        "[linked png](assets/fig.png)\n"
        "[linked html](assets/wavemap.html#top)\n"
        "```\n[quoted](assets/fig.png)\n```\n",
        encoding="utf-8")
    assert linked_figures([page], tmp_path) == [
        "planted.md -> assets/fig.png", "planted.md -> assets/wavemap.html#top"]
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "wavemap.html").write_text("<html></html>", encoding="utf-8")
    assert html_in_assets(tmp_path / "assets") == ["wavemap.html"]


# ---------------------------------- an inline figure on every demonstration page

#: Pages that hold reference or contract text rather than a computation, by name.
FIGURE_EXEMPT = frozenset({
    "api.md", "glossary.md", "references.md", "errors.md", "install.md", "recipes.md",
    "agents.md", "documentation_form.md", "10_operation_specifications.md", "architecture.md",
    "01_architecture_and_philosophy.md", "execution.md",
})
#: A light figure as written in a page: a markdown image or an `<img>` tag, `#only-light` after it.
_LIGHT_FIGURE = re.compile(r"([^\s\"'()]+\.png)#only-light")
#: Pages that show one PNG with no dark twin. The gate owns the map and its quoted lines.
LIGHT_ONLY_PAGES = gate.LIGHT_ONLY_PAGES


def dark_twin(light: str) -> str:
    """The dark PNG that replaces a light one: `name.png` -> `name.dark.png`."""
    return light[: -len(".png")] + ".dark.png"


def demonstration_pages(docs: Path) -> list[Path]:
    return sorted([*docs.glob("*.md"), *(docs / "tutorials").glob("*.md")])


def figure_gaps(docs: Path) -> tuple[list[str], list[str]]:
    """(pages outside `FIGURE_EXEMPT` that embed no light PNG with its dark twin, and the light
    PNGs whose dark twin is not on disk beside the page)."""
    bare, orphans = [], []
    for page in demonstration_pages(docs):
        text = page.read_text(encoding="utf-8")
        name = page.relative_to(docs).as_posix()
        lights = _LIGHT_FIGURE.findall(text)
        orphans += [f"{name} -> {dark_twin(light)}" for light in lights
                    if not (page.parent / dark_twin(light)).is_file()]
        paired = [light for light in lights if f"{dark_twin(light)}#only-dark" in text]
        if page.name not in FIGURE_EXEMPT and page.name not in LIGHT_ONLY_PAGES and not paired:
            bare.append(name)
    return bare, orphans


def test_every_demonstration_page_embeds_a_figure_pair():
    """Bypass: a computation page with no figure passes, or a light PNG whose dark twin is not
    on disk passes. The page count guards an empty scan."""
    pages = demonstration_pages(DOCS)
    assert len(pages) >= 30, f"only {len(pages)} pages read; the scan has nothing to check"
    bare, orphans = figure_gaps(DOCS)
    assert not bare, f"pages with no light and dark figure pair: {bare}"
    assert not orphans, f"light figures with no dark twin on disk: {orphans}"


def test_a_light_only_page_states_its_theme():
    """Bypass: the exemption outlives the line that justifies it, so a page with one dark-less
    figure passes unexplained. The quoted line is the page's own statement of its light theme."""
    for name, line in LIGHT_ONLY_PAGES.items():
        text = (DOCS / name).read_text(encoding="utf-8")
        assert line in text, f"{name} is exempt from the figure pair but does not state: {line!r}"


def test_the_figure_pair_check_names_the_bare_page_and_the_missing_twin(tmp_path):
    (tmp_path / "assets").mkdir()
    for name in ("fig.png", "fig.dark.png", "lone.png"):
        (tmp_path / "assets" / name).write_bytes(b"")
    (tmp_path / "paired.md").write_text(
        "![a](assets/fig.png#only-light)\n![a](assets/fig.dark.png#only-dark)\n", encoding="utf-8")
    (tmp_path / "bare.md").write_text("Prose, no figure.\n", encoding="utf-8")
    (tmp_path / "api.md").write_text("Reference, exempt.\n", encoding="utf-8")
    (tmp_path / "orphan.md").write_text(
        "![a](assets/lone.png#only-light)\n![a](assets/lone.dark.png#only-dark)\n", encoding="utf-8")
    assert figure_gaps(tmp_path) == (["bare.md"], ["orphan.md -> assets/lone.dark.png"])


# ------------------------------------------------------- F9: validation detail


def _write_docs_page(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("prefix", ["artifacts/evidence/", "artifacts/benchmarks/"])
def test_a_bare_validation_path_outside_references_fails(tmp_path, prefix):
    """Bypass: the matcher never fires, and F9 passes over any tree. One bare path on a
    planted page must fail named with its file and line."""
    _write_docs_page(tmp_path / "docs" / "planted.md",
                     f"# Planted\n\nThe receipt sits at {prefix}x.json.\n")
    violations, _ = gate.check_evidence_paths(tmp_path)
    assert any(v.startswith("planted.md:3:") and prefix in v for v in violations), violations


@pytest.mark.parametrize("prefix", ["artifacts/evidence/", "artifacts/benchmarks/"])
def test_the_same_path_in_references_passes(tmp_path, prefix):
    """The exemption: `references.md` may cite the evidence its rows rest on."""
    _write_docs_page(tmp_path / "docs" / "references.md",
                     f"# References\n\nThe receipt sits at {prefix}x.json.\n")
    _write_docs_page(tmp_path / "docs" / "planted.md", "# Planted\n\nProse, no paths.\n")
    assert gate.check_evidence_paths(tmp_path)[0] == []


def test_a_validation_path_in_a_code_span_fails_too(tmp_path):
    """A receipt path in backticks is still a path a reader follows."""
    _write_docs_page(tmp_path / "docs" / "planted.md",
                     "# Planted\n\nSee `artifacts/evidence/x.json`.\n")
    assert gate.check_evidence_paths(tmp_path)[0], "a backticked path must fail"


def test_the_live_tree_carries_no_validation_paths():
    """The live-tree leg: no page outside `references.md` names a validation path."""
    assert len(list((REPO_ROOT / "docs").rglob("*.md"))) >= 25, "the scan read almost nothing"
    violations, _ = gate.check_evidence_paths(REPO_ROOT)
    assert violations == [], violations
