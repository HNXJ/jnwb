#!/usr/bin/env python3
"""Documentation form gate: the rules of ``docs/documentation_form.md`` a machine can settle.

Six checks, each run against a repository root (the live tree from the command line, a seeded
fixture tree from the suite):

  1. Vocabulary (F5). No superseded surface form from the contract's vocabulary table survives
     in the prose of the documentation corpus.
  2. Heading depth (F1). No heading deeper than ``###`` outside fenced code, indented up to three
     spaces or not.
  3. Navigation (N1, N2, N3, N5). Every top-level ``nav`` entry of ``mkdocs.yml`` is a group,
     every group holds pages and no further groups, no group holds fewer than two pages, and
     every local target resolves to a file under ``docs/``. N3 is checked through its premise:
     the contract derives it from N1 "given every page is in a group", so a page outside a
     group fails. N4 is a review item.
  4. Figure theme independence (G2). Every image a page shows is a light/dark pair
     (``#only-light`` and ``#only-dark``, the dark file named ``<stem>.dark.png``, both on
     disk), or is listed in ``THEME_NEUTRAL`` with a reason. A figure file referenced without a
     scheme fragment is shown the same under both schemes. An inline ``<svg>`` passes only
     when every color it draws with comes from the theme (``currentColor``, ``var(...)``,
     ``none``, ``transparent``, ``inherit``). Every fixed color a figure generator writes
     outside its per-theme table reads on both page backgrounds. G1 (transparent corners) stays
     with ``tests/test_figure_form.py``, which reads the pixels.
  5. Parallel facts in prose (F2, partly). A paragraph in which three or more distinct inline
     code subjects each open a clause with the same kind of predicate ("`a` returns ...,
     `b` returns ..., `c` returns ...") states comparable facts that belong in a table.
  6. Slop lexicon (F8). No term of the contract's slop lexicon appears, as a whole word in any
     case, in the prose of the documentation corpus, the skills included.

**What check 5 does not see.** It is a detector for one shape, tuned to report nothing on the
live tree, and F2 stays a review item beyond it:

* Only inline-code subjects count. "The median is ..., the mean is ..., the mode is ..." is
  three comparable facts with plain-English subjects and is not reported.
* Only paragraphs are read. Lists, table cells, admonition bodies (indented), block quotes and
  HTML blocks are skipped, so a bulleted list of three "`x` returns ..." items is not reported.
* Only the predicates in ``_PREDICATES`` open a clause. "`a` gives ..." is not seen.
* Facts spread across paragraphs or sentences joined by other punctuation are not counted
  together.
* It cannot judge comparability. Three code subjects with a listed predicate in one paragraph
  are reported whether or not the facts are of one kind; the fix is a table or a rewrite.

**One implementation per rule.** This module holds the readers (the corpus, the vocabulary table,
the navigation, the themed-image patterns, the prose stripper, the fixed-color legibility test)
and the rule that uses each. The tests under ``tests/`` call these functions and add the guards
that show each reader reaches what it claims to read; they restate no rule. The root parameter
lets each rule be shown to fail on a seeded fixture tree.

Exit code 0 when every check passes, 1 otherwise. A check that raises is reported ERROR and
the others still run.
"""

from __future__ import annotations

import ast
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

CONTRACT = Path("docs") / "documentation_form.md"

#: Generated from `jnwb.__all__` by `scripts/generate_api_md.py`. An edit to it is discarded by
#: the next build, so the corpus carries it under its full path and the fix goes to the generator.
GENERATED = "api.md"

#: Images shown identically under both palette schemes, each with the reason that is safe.
THEME_NEUTRAL: Dict[str, str] = {
    "assets/jnwb-logo.png": "the project mark: transparent ground and a mid-tone mark, the same "
                            "file the theme header shows under both schemes",
}

#: The sources that write a figure colour, relative to the root: the figure generators and the
#: style module that holds the palette they draw with.
GENERATORS: Tuple[Path, ...] = (Path("docs") / "generate_figures.py",
                                Path("examples") / "quickstart_jnwb.py",
                                Path("docs") / "figure_style.py")

#: A themed figure on a page, as a Markdown image line or an `<img>` tag: (stem, ".dark", scheme).
IMAGE_LINE = re.compile(r"^!\[[^\]]*\]\((assets/[^)\s]+?)(\.dark)?\.png#only-(light|dark)\)$", re.M)
IMG_TAG = re.compile(r'<img src="(assets/[^"]+?)(\.dark)?\.png#only-(light|dark)"')
#: A figure file referenced with no scheme fragment, in a link, an image or an attribute.
BARE_FIGURE = re.compile(
    r"[(\"](assets/(?:figures/[^)\s\"#]+|jnwb_quickstart[^)\s\"#]*)\.png)[)\"]")

#: Page backgrounds of the built site (`docs/_theme_override.css`), by theme.
PAGE = {"light": "#ffffff", "dark": "#1b1b1b"}
MIN_FIXED_CONTRAST = 2.0

#: Colours drawn over a figure element rather than over the page, by generator function.
DRAWN_OVER_A_FIGURE: Dict[str, Dict[str, str]] = {}

Result = Tuple[List[str], str]


# ------------------------------------------------------------------------------- prose


_FENCE = re.compile(r"^```.*?^```", re.S | re.M)
_HTML = re.compile(r"<[^>]+>")
_MATH_BLOCK = re.compile(r"\$\$.*?\$\$", re.S)
_MATH_INLINE = re.compile(r"\$[^$\n]+\$")
_LINK_TARGET = re.compile(r"\]\([^)]*\)")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_SNIPPET = re.compile(r"^--8<--.*$", re.M)
_FENCE_BLOCK = re.compile(r"^```[^\n]*\n(.*?)^```", re.S | re.M)
#: A whole-line or trailing `#` comment inside a fenced block. A `#` inside a string literal is
#: not excluded; across the comment lines in `docs/*.md` that produces no false positive.
_FENCE_COMMENT = re.compile(r"#(.*)$", re.M)


def prose(text: str) -> str:
    """Everything on a page that a reader reads as English.

    Code is not prose and is not renameable: a parameter called `n_times` is the API's word, not
    the documentation's. Stripped, in order: fenced blocks, snippet includes, HTML tags and their
    attributes, display and inline math, markdown link *targets* (the text survives), and
    inline code spans.
    """
    text = _FENCE.sub(" ", text)
    text = _SNIPPET.sub(" ", text)
    text = _HTML.sub(" ", text)
    text = _MATH_BLOCK.sub(" ", text)
    text = _MATH_INLINE.sub(" ", text)
    text = _LINK_TARGET.sub("]", text)
    text = _INLINE_CODE.sub(" ", text)
    return text


def fenced_comments(text: str) -> str:
    """The comment text inside fenced code blocks, which `prose` strips along with the code."""
    return "\n".join(
        comment
        for block in _FENCE_BLOCK.findall(text)
        for comment in _FENCE_COMMENT.findall(block)
    )


_FENCE_LINE = re.compile(r"^ {0,3}(```|~~~)")


def unfenced_lines(text: str) -> Iterator[Tuple[int, str]]:
    """(line number, line) for every line outside fenced code, fence markers excluded."""
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if _FENCE_LINE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            yield number, line


# ------------------------------------------------------------------------------ corpus


def _authored_pages(docs: Path) -> List[Path]:
    """`docs/*.md` without the generated reference, then `docs/tutorials/*.md`."""
    return ([p for p in sorted(docs.glob("*.md")) if p.name != GENERATED]
            + sorted((docs / "tutorials").glob("*.md")))


def _page_name(docs: Path, page: Path) -> str:
    return page.relative_to(docs).as_posix()


def corpus(root: Path) -> List[Tuple[str, str]]:
    """The pages the vocabulary, heading and slop rules apply to, as (name, text).

    | Surface | Read by | Fix goes to |
    |---|---|---|
    | `docs/*.md` and `docs/tutorials/*.md` | readers of the site | the page |
    | `README.md` | readers of the repository | the page |
    | fenced code comments of those pages | readers copying the code | the page |
    | `docs/api.md` | readers of the reference | the generator or a docstring |
    | `skills/*/SKILL.md` | agents routing to the library | the skill file |
    | `examples/tutorials/*.py` | readers of the tutorials | the script |

    A tutorial page is its own prose around a ``--8<--`` include of the script; the include is
    stripped from the prose and the script is scanned as its own surface. The generated
    reference is named by its full path, never its bare name: the distinction is what sends a
    fix to the generator.
    """
    docs = root / "docs"
    authored = _authored_pages(docs)
    pages = [(_page_name(docs, p), p.read_text(encoding="utf-8")) for p in authored]
    readme = root / "README.md"
    if readme.is_file():
        pages.append(("README.md", readme.read_text(encoding="utf-8")))
    for page in authored:
        comments = fenced_comments(page.read_text(encoding="utf-8"))
        if comments.strip():
            pages.append((f"{_page_name(docs, page)} (code comments)", comments))
    generated = docs / GENERATED
    if generated.is_file():
        pages.append((f"docs/{GENERATED}", generated.read_text(encoding="utf-8")))
    for skill in sorted((root / "skills").glob("*/SKILL.md")):
        pages.append((f"skills/{skill.parent.name}/SKILL.md", skill.read_text(encoding="utf-8")))
    for script in sorted((root / "examples" / "tutorials").glob("*.py")):
        pages.append((f"examples/tutorials/{script.name}", script.read_text(encoding="utf-8")))
    return pages


# ------------------------------------------------------------------ vocabulary table


#: The heading the vocabulary table sits under in the contract, matched as a whole line.
VOCABULARY_HEADING = "## Vocabulary"
VOCABULARY_HEADING_LINE = re.compile(rf"^{re.escape(VOCABULARY_HEADING)}\s*$", re.M)
BACKTICKED = re.compile(r"`([^`]+)`")


class VocabularyRow:
    """One concept: the surface forms to use, and the ones that are superseded.

    `preferred` is a tuple because English inflects: `normalize`, `normalized` and
    `normalization` are one surface form for F5, and what F5 forbids is `normalise`.
    """

    def __init__(self, concept: str, preferred: Tuple[str, ...], superseded: Tuple[str, ...]):
        self.concept = concept
        self.preferred = preferred
        self.superseded = superseded

    @property
    def head(self) -> str:
        """The form named first, used in the message a violation prints."""
        return self.preferred[0]

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return f"VocabularyRow({self.concept!r}, {self.preferred!r}, {self.superseded!r})"


def vocabulary_section(contract_text: str) -> Optional[str]:
    """The text under the vocabulary heading, or None when the heading is absent."""
    match = VOCABULARY_HEADING_LINE.search(contract_text)
    if match is None:
        return None
    return contract_text[match.end():].split("\n## ", 1)[0]


def parse_vocabulary(contract_text: str) -> List[VocabularyRow]:
    """The rows of the contract's vocabulary table: concept, accepted forms, superseded forms."""
    section = vocabulary_section(contract_text)
    if section is None:
        return []
    rows = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or "|---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 3 or cells[0].lower() == "concept":
            continue
        preferred = BACKTICKED.findall(cells[1])
        superseded = BACKTICKED.findall(cells[2])
        if preferred and superseded:
            rows.append(VocabularyRow(cells[0], tuple(preferred), tuple(superseded)))
    return rows


def word(term: str) -> "re.Pattern[str]":
    """Match `term` as a whole word, case-insensitively.

    `\\b` treats `_` as a word character, so `n_times` inside `fig_n_times_plot` does not match,
    which is right: those are identifiers rather than prose. A superseded form is matched
    exactly; an unlisted inflection is closed by adding it to the contract's table, not by a
    matcher that guesses at English (`analyse` plus `s` is "analyses", the plural of "analysis").
    """
    return re.compile(rf"\b{re.escape(term)}\b", re.I)


def vocabulary_violations(pages: List[Tuple[str, str]], rows: List[VocabularyRow]) -> List[str]:
    """Every superseded surface form still in the prose, named with its page.

    The row's preferred form is removed from the text before its superseded forms are hunted;
    without that, a row whose superseded form is a substring of its preferred one (`unit` inside
    `single unit`) reports every correct use as a violation.
    """
    found: List[str] = []
    for name, text in pages:
        stripped = prose(text)
        for row in rows:
            scrubbed = stripped
            for good in row.preferred:
                scrubbed = word(good).sub(" ", scrubbed)
            for bad in row.superseded:
                if word(bad).search(scrubbed):
                    found.append(f"{name}: {bad!r} -- {row.concept} is written {row.head!r}")
    return sorted(set(found))


# ------------------------------------------------------------------------ 1. vocabulary


def check_vocabulary(root: Path) -> Result:
    rows = parse_vocabulary((root / CONTRACT).read_text(encoding="utf-8"))
    if not rows:
        return [f"no vocabulary rows parsed from {CONTRACT.as_posix()}; F5 has nothing to "
                "check against"], ""
    pages = corpus(root)
    return vocabulary_violations(pages, rows), (
        f"PASS: vocabulary (F5): no superseded form of {len(rows)} concepts in "
        f"{len(pages)} pages.")


# ---------------------------------------------------------------------- 2. heading depth


#: An ATX heading deeper than ``###``; up to three leading spaces still make a heading.
_DEEP_HEADING = re.compile(r"^ {0,3}#{4,}(?:\s|$)")


def check_heading_depth(root: Path) -> Result:
    pages = corpus(root)
    deep = [f"{name}:{number}: {line.strip()}"
            for name, text in pages
            for number, line in unfenced_lines(text)
            if _DEEP_HEADING.match(line)]
    return deep, f"PASS: heading depth (F1): no heading below ### in {len(pages)} pages."


# -------------------------------------------------------------------------- 3. navigation


def pages_under(node) -> List[str]:
    """Every string leaf of a ``nav`` node, in order: the targets, local or not."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [p for value in node.values() for p in pages_under(value)]
    if isinstance(node, list):
        return [p for item in node for p in pages_under(item)]
    return []


def is_external(target: str) -> bool:
    """A nav target that is a URL, not a file under ``docs/``."""
    return re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) is not None


def nav_entries(mkdocs: Path) -> list:
    """The parsed ``nav`` of ``mkdocs``. YAML drops comments, so a commented entry is not one."""
    config = yaml.safe_load(mkdocs.read_text(encoding="utf-8")) or {}
    return config.get("nav") or []


def nav_targets(mkdocs: Path) -> List[str]:
    """Every local ``.md`` file on the parsed nav of ``mkdocs``, in order, as written."""
    return [t for t in pages_under(nav_entries(mkdocs))
            if t.endswith(".md") and not is_external(t)]


def mkdocs_patterns(mkdocs: Path, key: str) -> List[str]:
    """The gitignore-style lines under ``key`` (``exclude_docs``, ``not_in_nav``), without
    comments and blanks."""
    config = yaml.safe_load(mkdocs.read_text(encoding="utf-8")) or {}
    return [line.strip() for line in (config.get(key) or "").splitlines()
            if line.strip() and not line.strip().startswith("#")]


def mkdocs_spec(mkdocs: Path, key: str):
    """The matcher MkDocs builds from ``key``: gitignore semantics, so ``*.md``, ``/top.md``,
    ``dir/`` and ``!keep.md`` all mean what they mean there. Needs ``pathspec``, which MkDocs
    brings with the ``docs`` extra."""
    import pathspec

    config = yaml.safe_load(mkdocs.read_text(encoding="utf-8")) or {}
    return pathspec.GitIgnoreSpec.from_lines((config.get(key) or "").splitlines())


def nav_groups(mkdocs: Path) -> List[Tuple[str, list]]:
    """The top-level ``{title: children}`` entries of the nav."""
    return [(title, children) for entry in nav_entries(mkdocs) if isinstance(entry, dict)
            for title, children in entry.items()]


def check_navigation(root: Path) -> Result:
    nav = nav_entries(root / "mkdocs.yml")
    if not nav:
        return ["mkdocs.yml has no nav entries"], ""
    violations: List[str] = []
    targets: List[str] = []
    groups = 0
    for entry in nav:
        if not (isinstance(entry, dict) and len(entry) == 1
                and isinstance(next(iter(entry.values())), list)):
            violations.append(f"N3: top-level entry outside a group: {entry!r}")
            targets.extend(pages_under(entry))
            continue
        (title, children), = entry.items()
        groups += 1
        pages = pages_under(children)
        targets.extend(pages)
        for child in children:
            if isinstance(child, dict) and not all(isinstance(v, str) for v in child.values()):
                violations.append(f"N1: group {title!r} nests a further group: {list(child)}")
            elif not isinstance(child, (str, dict)):
                violations.append(f"N1: group {title!r} holds an entry that is not a page: "
                                  f"{child!r}")
        if len(pages) < 2:
            violations.append(f"N2: group {title!r} holds {len(pages)} page(s)")
    local = [t for t in targets if not is_external(t)]
    for target in local:
        if not (root / "docs" / target).is_file():
            violations.append(f"N5: nav target docs/{target} does not exist")
    return violations, (
        f"PASS: navigation (N1, N2, N3, N5): {groups} groups, depth two, {len(local)} targets, "
        "all resolving, none holding one page.")


# ------------------------------------------------------------------------------ 4. figures


_MD_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
_IMG_SRC = re.compile(r"<img\b[^>]*\bsrc=\"([^\"]+)\"")
_SVG = re.compile(r"<svg\b.*?</svg>", re.S | re.I)
_SVG_COLOR = re.compile(r"\b(fill|stroke|stop-color|color)\s*[=:]\s*[\"']?\s*([^\"';>\s]+)", re.I)
_THEME_COLORS = {"none", "currentcolor", "transparent", "inherit"}


def _local(src: str) -> bool:
    return not is_external(src)


def hex_colour(value: str, in_colour_argument: bool = False) -> Optional[str]:
    """The colour a string literal names, or None. A one-letter name counts only as an argument
    named for a colour, where it cannot be anything else."""
    import matplotlib.colors as mcolors

    if re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", value):
        return mcolors.to_hex(value)
    if value.lower() in mcolors.CSS4_COLORS or value.startswith(("xkcd:", "tab:")):
        try:
            return mcolors.to_hex(value)
        except ValueError:
            return None
    if in_colour_argument and value in mcolors.BASE_COLORS:
        return mcolors.to_hex(value)
    return None


def luminance(colour: str) -> float:
    import matplotlib.colors as mcolors

    rgb = np.array(mcolors.to_rgb(colour))
    lin = np.where(rgb <= 0.03928, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    return float(0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2])


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


COLOUR_ARGUMENTS = {"color", "colors", "c", "facecolor", "edgecolor", "labelcolor", "fc", "ec",
                    "markerfacecolor", "markeredgecolor", "mfc", "mec"}


def themes_node(tree):
    """The value assigned to ``THEMES`` in a parsed generator, or None."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "THEMES"
                                                for t in node.targets):
            return node.value
    return None


def illegible_literals(source: str) -> List[str]:
    """Colour literals outside a `THEMES` table that fail contrast on either page."""
    tree = ast.parse(source)
    table = themes_node(tree)
    in_table = {id(n) for n in ast.walk(table)} if table is not None else set()
    owner, in_colour_argument = {}, set()
    for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
        for n in ast.walk(fn):
            owner.setdefault(id(n), fn.name)
    for kw in (n for n in ast.walk(tree) if isinstance(n, ast.keyword)):
        if kw.arg in COLOUR_ARGUMENTS:
            in_colour_argument.update(id(n) for n in ast.walk(kw.value))
    offenders = []
    for node in ast.walk(tree):
        if (not (isinstance(node, ast.Constant) and isinstance(node.value, str))
                or id(node) in in_table):
            continue
        colour = hex_colour(node.value, id(node) in in_colour_argument)
        if colour is None or node.value in DRAWN_OVER_A_FIGURE.get(owner.get(id(node)), {}):
            continue
        worst = min(contrast(colour, bg) for bg in PAGE.values())
        if worst < MIN_FIXED_CONTRAST:
            offenders.append(f"line {node.lineno}: {node.value} (contrast {worst:.2f})")
    return offenders


def check_figures(root: Path) -> Result:
    docs = root / "docs"
    violations: List[str] = []
    shown: Dict[Tuple[str, str], set] = {}
    for page in sorted(docs.rglob("*.md")):
        name = page.relative_to(docs).as_posix()
        text = page.read_text(encoding="utf-8")
        body = "\n".join(line for _, line in unfenced_lines(text))
        paired: Counter = Counter()
        for stem, dark, scheme in IMAGE_LINE.findall(body) + IMG_TAG.findall(body):
            if (scheme == "dark") != bool(dark):
                violations.append(f"{name}: {stem} shows the {'dark' if dark else 'light'} file "
                                  f"under #only-{scheme}")
            shown.setdefault((name, stem), set()).add(scheme)
            paired[f"{stem}{dark}.png#only-{scheme}"] += 1
        for src in _MD_IMAGE.findall(body) + _IMG_SRC.findall(body):
            path = src.split("#", 1)[0]
            themed = src.endswith(("#only-light", "#only-dark"))
            if not _local(src) or path in THEME_NEUTRAL:
                continue
            if paired[src] > 0:  # counted, so a second reference of one src is read on its own
                paired[src] -= 1
                continue
            if themed:
                # Shown under one scheme in a form the pairing above does not read (mid-line,
                # outside `assets/`, not a PNG), so its partner cannot be confirmed.
                violations.append(f"{name}: {src} is shown under one scheme in a form whose "
                                  "light/dark partner cannot be confirmed")
            else:
                violations.append(f"{name}: {path} is shown the same under both schemes and is "
                                  "not listed as theme-neutral")
        for bare in BARE_FIGURE.findall(text):  # the whole page: a fenced example is a reference
            violations.append(f"{name}: {bare} is referenced without #only-light or #only-dark, "
                              "so it reads the same under both schemes")
        for svg in _SVG.findall(body):
            fixed = sorted({value for _, value in _SVG_COLOR.findall(svg)
                            if value.lower() not in _THEME_COLORS
                            and not value.lower().startswith(("var(", "url("))})
            if fixed:
                violations.append(f"{name}: an inline <svg> draws with fixed colors {fixed}")
    for (name, stem), schemes in sorted(shown.items()):
        if schemes != {"light", "dark"}:
            violations.append(f"{name}: {stem} is shown only under {sorted(schemes)}")
        for suffix in (".png", ".dark.png"):
            if not (docs / f"{stem}{suffix}").is_file():
                violations.append(f"{name}: {stem}{suffix} is missing")
    generators = [root / g for g in GENERATORS]
    for generator in generators:
        label = generator.relative_to(root).as_posix()
        if not generator.is_file():
            violations.append(f"{label}: figure generator is missing")
            continue
        for offender in illegible_literals(generator.read_text(encoding="utf-8")):
            violations.append(f"{label}: {offender} is fixed outside THEMES and fails contrast "
                              "on a page background")
    return violations, (
        f"PASS: figure theme independence (G2): {len(shown)} figures shown as light/dark pairs, "
        f"{len(THEME_NEUTRAL)} listed theme-neutral, fixed colors legible in "
        f"{len(generators)} generators.")


# ------------------------------------------------------------------------ 5. parallel facts


_PARAGRAPH_SKIP = re.compile(r"^(\||#|[-*+]\s|>|!|<|\d+\.\s|--8<--|\$\$|\\\[)")
_CODE = r"`[^`\n]+`"
_PREDICATES = (r"is|are|returns|return|takes|take|means|computes|yields|reports|holds|accepts|"
               r"raises|measures|contains|controls|selects")
_CLAUSE = re.compile(rf"(?:^|[.;:!?]\s+|,\s+(?:and\s+|or\s+)?)({_CODE})\s+(?:{_PREDICATES})\b")
PARALLEL_FACTS = 3


def paragraphs(text: str) -> Iterator[Tuple[int, str]]:
    """(first line number, joined text) for every prose paragraph outside fenced code.

    A block is skipped when its first line opens a table, heading, list, block quote,
    admonition, HTML block, snippet include or display math, or is indented.
    """
    block: List[Tuple[int, str]] = []
    in_fence = False

    def flush() -> Optional[Tuple[int, str]]:
        if not block:
            return None
        number, first = block[0]
        joined = " ".join(line.strip() for _, line in block)
        block.clear()
        if first.startswith((" ", "\t")) or _PARAGRAPH_SKIP.match(first):
            return None
        return number, joined

    for number, line in enumerate(text.splitlines(), start=1):
        if _FENCE_LINE.match(line):
            in_fence = not in_fence
            done = flush()
            if done:
                yield done
            continue
        if in_fence:
            continue
        if line.strip():
            block.append((number, line))
        else:
            done = flush()
            if done:
                yield done
    done = flush()
    if done:
        yield done


def parallel_fact_subjects(paragraph: str) -> List[str]:
    """The distinct inline-code subjects that open a clause with a listed predicate."""
    return sorted(set(_CLAUSE.findall(paragraph)))


def f2_pages(root: Path) -> List[Tuple[str, str]]:
    """Authored and contract pages: ``docs/*.md`` and ``docs/tutorials/*.md``, without the
    generated reference."""
    docs = root / "docs"
    return [(_page_name(docs, p), p.read_text(encoding="utf-8")) for p in _authored_pages(docs)]


def check_parallel_facts(root: Path) -> Result:
    pages = f2_pages(root)
    violations: List[str] = []
    count = 0
    for name, text in pages:
        for number, paragraph in paragraphs(text):
            count += 1
            subjects = parallel_fact_subjects(paragraph)
            if len(subjects) >= PARALLEL_FACTS:
                violations.append(f"{name}:{number}: {len(subjects)} parallel facts in one "
                                  f"paragraph ({', '.join(subjects)}); a table carries them")
    return violations, (
        f"PASS: parallel facts (F2 detector): no paragraph states {PARALLEL_FACTS} or more "
        f"parallel facts, {count} paragraphs in {len(pages)} pages.")


# --------------------------------------------------------------------------- 6. slop lexicon


SLOP_HEADING = re.compile(r"^## Slop lexicon\s*$", re.M)


def parse_slop_lexicon(contract_text: str) -> List[str]:
    """Every backticked term in the table rows of the contract's slop lexicon section."""
    match = SLOP_HEADING.search(contract_text)
    if match is None:
        return []
    section = contract_text[match.end():].split("\n## ", 1)[0]
    terms: List[str] = []
    for line in section.splitlines():
        line = line.strip()
        if line.startswith("|") and "|---" not in line:
            terms.extend(BACKTICKED.findall(line))
    return list(dict.fromkeys(terms))


def check_slop(root: Path) -> Result:
    terms = parse_slop_lexicon((root / CONTRACT).read_text(encoding="utf-8"))
    if not terms:
        return [f"no slop lexicon parsed from {CONTRACT.as_posix()}; F8 has nothing to check "
                "against"], ""
    pages = corpus(root)
    patterns = [(term, re.compile(rf"(?<![\w-]){re.escape(term)}(?![\w-])", re.I))
                for term in terms]
    violations = sorted({f"{name}: {term!r} is in the slop lexicon (F8)"
                         for name, text in pages
                         for stripped in (prose(text),)
                         for term, pattern in patterns if pattern.search(stripped)})
    return violations, (
        f"PASS: slop lexicon (F8): none of {len(terms)} terms in {len(pages)} pages.")


# ---------------------------------------------------------------------------------- runner


CHECKS: Sequence[Tuple[str, Callable[[Path], Result]]] = (
    ("vocabulary", check_vocabulary),
    ("heading depth", check_heading_depth),
    ("navigation", check_navigation),
    ("figure theme independence", check_figures),
    ("parallel facts", check_parallel_facts),
    ("slop lexicon", check_slop),
)


def run_checks(root: Path = REPO_ROOT) -> List[Tuple[str, List[str], str]]:
    """Every check on ``root``, as (name, violations, pass line). A raise is caught."""
    results = []
    for name, check in CHECKS:
        try:
            violations, pass_line = check(Path(root))
            results.append((name, violations, pass_line))
        except Exception as exc:  # one broken check must not hide the others
            results.append((name, [f"ERROR: {type(exc).__name__}: {exc}"], "ERROR"))
    return results


def main(root: Path = REPO_ROOT) -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="backslashreplace")
    print("=== Documentation form ===")
    failed = []
    for name, violations, pass_line in run_checks(root):
        if not violations:
            print(pass_line)
            continue
        failed.append(name)
        errored = violations[0].startswith("ERROR:")
        print(f"{'ERROR' if errored else 'FAIL'}: {name}:")
        for violation in violations:
            print(f"  - {violation}")
    if failed:
        print(f"OVERALL: FAIL. failed: {', '.join(failed)}.")
        return 1
    print(f"ALL DOCUMENTATION FORM CHECKS PASSED. {len(CHECKS)} of {len(CHECKS)} checks executed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
