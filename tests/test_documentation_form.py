"""The rules of `docs/documentation_form.md` that are machine-checkable, checked.

The contract's "How it is checked" column names five rules a machine can settle: F1 by
counting, F5 against a vocabulary list, and N1, N2 and N5 by parsing `mkdocs.yml`. N5 is
already held by `test_docs_user_navigation.py::test_no_nav_entry_is_dead`, so it is not
re-implemented here; a claim with two homes drifts in one of them.

F5 is this module's substance. A concept with two surface forms is not a typo -- a reader
who greps the documentation for the phrase they were taught finds half the pages, and the
half they miss is invisible rather than empty.

**What would make each check below pass while the rule it names is violated.** This
module's whole failure mode is a green check over an unread corpus, so every assertion
here is paired with the bypass it is written against, and the bypasses are themselves
tested:

- The vocabulary table stops parsing, yielding zero rows, and every page trivially
  conforms. Held by `test_the_vocabulary_list_parses`, which requires rows and requires
  named concepts among them.
- The corpus collapses to nothing, or to the generated page only, and there is no prose
  to find a violation in. Held by `test_the_corpus_reaches_the_authored_pages`.
- `_prose` strips too much -- the whole page, not just its code -- and the scan runs over
  an empty string. Held by `test_stripping_code_leaves_the_prose_behind`, which requires
  a known sentence to survive and a known code token to be gone.
- The matcher never matches anything, because of a word-boundary, escaping or case bug,
  so no row can ever fire. Held by `test_every_preferred_term_occurs_in_the_prose`: each
  row's *preferred* form must be findable by the same matcher that hunts its superseded
  ones. A row whose preferred form cannot be found is an untestable row, and fails.
- The checker finds violations but reports them without saying where. Held by
  `test_a_reintroduced_superseded_term_is_named_with_its_page`, the discriminator 06-49
  asks for: seed one page with a superseded term and require the page and the term back.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
MKDOCS = REPO_ROOT / "mkdocs.yml"

#: Generated from `jnwb.__all__` by `scripts/generate_api_md.py`. An edit to it is
#: discarded by the next build, so it is governed through the generator.
GENERATED = "api.md"

#: The heading the vocabulary table sits under in the contract. Matched as a whole line:
#: a substring match lets `## Vocabulary Removed` go on satisfying it, which a seeded
#: mutant demonstrated it did.
VOCABULARY_HEADING = "## Vocabulary"
_VOCABULARY_HEADING_LINE = re.compile(rf"^{re.escape(VOCABULARY_HEADING)}\s*$", re.M)


# --------------------------------------------------------------------------- corpus


_FENCE_BLOCK = re.compile(r"^```[^\n]*\n(.*?)^```", re.S | re.M)
#: A whole-line or trailing `#` comment inside a fenced block. A `#` inside a string literal is
#: not excluded; that imprecision was measured rather than argued about, and across the 277
#: comment lines in `docs/*.md` it produces no false positive.
_FENCE_COMMENT = re.compile(r"#(.*)$", re.M)


def _fenced_comments(text: str) -> str:
    """The comment text inside fenced code blocks, which `_prose` strips along with the code."""
    return "\n".join(
        comment
        for block in _FENCE_BLOCK.findall(text)
        for comment in _FENCE_COMMENT.findall(block)
    )


def _corpus() -> list[tuple[str, str]]:
    """The pages a vocabulary rule can actually be applied to, as (name, text).

    Top-level `docs/*.md`, plus `README.md`, plus three surfaces this corpus used to exclude
    (P-95). The nine `docs/tutorials/*.md` wrappers are still excluded, but for the reason
    that names their replacement: each is a `--8<--` wrapper around a script in
    `examples/tutorials/`, so the words a reader sees are in the script and an edit to the
    wrapper is discarded by the next build. The scripts are therefore scanned instead.

    The three additions, and why each is published prose rather than internal text:

    | Surface | Read by | Fix goes to |
    |---|---|---|
    | `skills/*/SKILL.md` | agents routing to the library | the skill file |
    | `docs/api.md` | readers of the reference | the generator or a jnwb docstring |
    | `examples/tutorials/*.py` | readers of the tutorials | the script |

    `docs/api.md` is generated, so it cannot be corrected in place -- but a superseded form
    reaching it is still a defect on a published page, and the gate naming it is what sends
    the fix to the generator instead of to the page.
    """
    pages = [(p.name, p.read_text(encoding="utf-8"))
             for p in sorted(DOCS.glob("*.md")) if p.name != GENERATED]
    pages.append(("README.md", (REPO_ROOT / "README.md").read_text(encoding="utf-8")))

    # Code comments inside fenced blocks are prose a reader reads, and `_prose` strips fences
    # whole, so they were invisible. Two in `docs/05` were corrected by hand with no guard, and
    # a hand fix with no guard is the shape that comes back (P-95). Measured before adding:
    # 277 comment lines across `docs/*.md`, 0 superseded forms and 0 false positives, so this
    # costs nothing and closes the gap those two corrections sat in.
    for page in sorted(DOCS.glob("*.md")):
        comments = _fenced_comments(page.read_text(encoding="utf-8"))
        if comments.strip():
            pages.append((f"{page.name} (code comments)", comments))

    generated = DOCS / GENERATED
    if generated.is_file():
        pages.append((f"docs/{GENERATED}", generated.read_text(encoding="utf-8")))
    for skill in sorted((REPO_ROOT / "skills").glob("*/SKILL.md")):
        pages.append((f"skills/{skill.parent.name}/SKILL.md",
                      skill.read_text(encoding="utf-8")))
    for script in sorted((REPO_ROOT / "examples" / "tutorials").glob("*.py")):
        pages.append((f"examples/tutorials/{script.name}",
                      script.read_text(encoding="utf-8")))
    return pages


_FENCE = re.compile(r"^```.*?^```", re.S | re.M)
_HTML = re.compile(r"<[^>]+>")
_MATH_BLOCK = re.compile(r"\$\$.*?\$\$", re.S)
_MATH_INLINE = re.compile(r"\$[^$\n]+\$")
_LINK_TARGET = re.compile(r"\]\([^)]*\)")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_SNIPPET = re.compile(r"^--8<--.*$", re.M)


def _prose(text: str) -> str:
    """Everything on a page that a reader reads as English.

    Code is not prose and is not renameable: a parameter called `n_times` is the API's
    word, not the documentation's. Stripped, in order: fenced blocks, HTML tags and their
    attributes, display and inline math, markdown link *targets* (the text survives),
    inline code spans, and snippet includes.
    """
    text = _FENCE.sub(" ", text)
    text = _SNIPPET.sub(" ", text)
    text = _HTML.sub(" ", text)
    text = _MATH_BLOCK.sub(" ", text)
    text = _MATH_INLINE.sub(" ", text)
    text = _LINK_TARGET.sub("]", text)
    text = _INLINE_CODE.sub(" ", text)
    return text


# ----------------------------------------------------------------- vocabulary list


class VocabularyRow:
    """One concept: the surface forms to use, and the ones that are superseded.

    `preferred` is a tuple because English inflects. The concept "scaling to a common
    range" is written `normalize`, `normalized` and `normalization` in different
    sentences, and all three are the same surface form for F5's purposes; what F5 forbids
    is `normalise`. A row is satisfied when any accepted inflection appears.
    """

    def __init__(self, concept: str, preferred: tuple[str, ...],
                 superseded: tuple[str, ...]):
        self.concept = concept
        self.preferred = preferred
        self.superseded = superseded

    @property
    def head(self) -> str:
        """The form named first, used in the message a violation prints."""
        return self.preferred[0]

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return f"VocabularyRow({self.concept!r}, {self.preferred!r}, {self.superseded!r})"


_BACKTICKED = re.compile(r"`([^`]+)`")


def _vocabulary() -> list[VocabularyRow]:
    """Parse the contract's vocabulary table.

    Every term is backticked in the source table. That is not decoration: `_prose` strips
    inline code, so the contract can name a superseded form without the scanner reading
    the contract as a page that uses it. `test_every_vocabulary_term_is_backticked` holds
    that property rather than trusting it.
    """
    text = (DOCS / "documentation_form.md").read_text(encoding="utf-8")
    match = _VOCABULARY_HEADING_LINE.search(text)
    if match is None:
        return []
    section = text[match.end():].split("\n## ", 1)[0]

    rows: list[VocabularyRow] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|--") or "|---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 3 or cells[0].lower() == "concept":
            continue
        concept, use, avoid = cells
        preferred = _BACKTICKED.findall(use)
        superseded = _BACKTICKED.findall(avoid)
        if not preferred or not superseded:
            continue
        rows.append(VocabularyRow(concept, tuple(preferred), tuple(superseded)))
    return rows


VOCABULARY = _vocabulary()


def _word(term: str) -> re.Pattern[str]:
    """Match `term` as a whole word, case-insensitively.

    `\\b` treats `_` as a word character, so `n_times` inside `fig_n_times_plot` does not
    match -- which is what we want, since those are identifiers rather than prose.
    """
    return re.compile(rf"\b{re.escape(term)}\b", re.I)


#: Every superseded form is matched exactly, and the inflections are listed in the contract
#: rather than derived here.
#:
#: A draft of the P-95 repair tolerated a trailing `s` on the superseded side, reasoning that a
#: plural of a forbidden word is forbidden too. **That reasoning is wrong, and the corpus said
#: so immediately**: `analyse` is superseded, and `analyse` + `s` is "analyses", the ordinary
#: plural of "analysis", which is correct American English. It fired on
#: `docs/01_architecture_and_philosophy.md:61` and `:83` -- two pages already inside the gated
#: corpus, and correct as written.
#:
#: So the rule stays exact. An unlisted inflection is closed by adding it to the table in
#: `docs/documentation_form.md`, where a human reads it, and not by a matcher that guesses at
#: English. The same argument was already being made here about `-ing` and `-ation`; it applies
#: to `-s` and the draft failed to apply it.
_superseded_word = _word


def vocabulary_violations(pages: list[tuple[str, str]],
                          rows: list[VocabularyRow]) -> list[str]:
    """Every superseded surface form still in the prose, named with its page.

    The row's preferred form is removed from the text before its superseded forms are
    hunted. Without that, a row whose superseded form is a substring of its preferred one
    -- `unit` inside `single unit` -- reports every correct use as a violation.
    """
    found: list[str] = []
    for name, text in pages:
        prose = _prose(text)
        for row in rows:
            scrubbed = prose
            for good in row.preferred:
                scrubbed = _word(good).sub(" ", scrubbed)
            for bad in row.superseded:
                if _superseded_word(bad).search(scrubbed):
                    found.append(f"{name}: {bad!r} -- {row.concept} is written "
                                 f"{row.head!r}")
    return sorted(set(found))


# ------------------------------------------------------------------- corpus guards


def test_the_corpus_reaches_the_authored_pages():
    """Bypass this is written against: the corpus is empty, or is the generated page
    alone, so every scan below passes over nothing."""
    names = {name for name, _ in _corpus()}
    assert GENERATED not in names, (
        "the generated reference is scanned under its full path `docs/api.md`, never under "
        "its bare name -- the distinction is what says the fix goes to the generator"
    )
    assert not any(n.startswith("tutorials") for n in names), (
        "the nine `--8<--` wrapper pages stay excluded; the scripts they include are scanned "
        "in their place, because an edit to a wrapper is discarded by the next build"
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
    text = (DOCS / "documentation_form.md").read_text(encoding="utf-8")
    match = _VOCABULARY_HEADING_LINE.search(text)
    assert match is not None, (
        f"docs/documentation_form.md carries no {VOCABULARY_HEADING!r} section")
    section = text[match.end():].split("\n## ", 1)[0]
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


def test_no_superseded_surface_form_survives_in_the_prose():
    """F5. One surface form per concept, taken from the vocabulary list."""
    violations = vocabulary_violations(_corpus(), VOCABULARY)
    assert not violations, (
        "superseded surface forms still in the documentation:\n  "
        + "\n  ".join(violations))


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
    for row in VOCABULARY:
        for good in row.preferred:
            clean = [("clean_page.md", f"A sentence using {good} in prose.")]
            assert not vocabulary_violations(clean, VOCABULARY), (
                f"the accepted form {good!r} was reported as a violation")


# ---------------------------------------------------------------------- F1: headings


def test_no_authored_page_uses_a_fourth_level_heading():
    """F1: headings stop at `###`. Counted outside fenced code, so a `#### ` comment in a
    Python block is not a false positive."""
    deep = []
    for name, text in _corpus():
        in_fence = False
        for number, line in enumerate(text.splitlines(), start=1):
            if line.startswith("```"):
                in_fence = not in_fence
            elif not in_fence and line.startswith("#### "):
                deep.append(f"{name}:{number}: {line.strip()}")
    assert not deep, "F1 violations -- these become `###` or a table row:\n  " + \
        "\n  ".join(deep)


def test_the_heading_check_can_see_a_heading_at_all():
    """Bypass: the fence stripper removes the whole page and F1 counts zero of
    everything. A real page must still show its real headings."""
    text = _FENCE.sub("", (DOCS / "common_mistakes.md").read_text(encoding="utf-8"))
    headings = [l for l in text.splitlines() if l.startswith("### ")]
    assert len(headings) > 5, f"only {len(headings)} third-level headings survived"


# ------------------------------------------------------------------ N1, N2: the nav


def _nav_groups() -> list[tuple[str, list]]:
    config = yaml.safe_load(MKDOCS.read_text(encoding="utf-8")) or {}
    groups = []
    for entry in config.get("nav", []):
        if isinstance(entry, dict):
            for title, children in entry.items():
                groups.append((title, children))
    return groups


def _pages_under(node) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [p for value in node.values() for p in _pages_under(value)]
    if isinstance(node, list):
        return [p for item in node for p in _pages_under(item)]
    return []


def test_the_nav_is_parsed_at_all():
    """Bypass: `nav:` fails to parse, no groups come back, and N1 and N2 hold over an
    empty list."""
    groups = _nav_groups()
    assert len(groups) >= 4, f"only {len(groups)} nav groups parsed"
    pages = [p for _, children in groups for p in _pages_under(children)]
    assert len(pages) >= 25, f"only {len(pages)} nav pages parsed"


def test_group_depth_is_two():
    """N1. A group holds pages, not further groups."""
    nested = [f"{title} -> {list(child)}"
              for title, children in _nav_groups()
              for child in children
              if isinstance(child, dict) and not all(
                  isinstance(v, str) for v in child.values())]
    assert not nested, f"nav groups nested deeper than two: {nested}"


def test_no_group_holds_a_single_page():
    """N2. A group of one is a page wearing a heading."""
    thin = [f"{title} ({len(_pages_under(children))})"
            for title, children in _nav_groups()
            if len(_pages_under(children)) < 2]
    assert not thin, f"nav groups holding fewer than two pages: {thin}"


# ------------------------------------------------------------------------ Length

_NUMBER_WORDS = {w: n for n, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve".split())}
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
