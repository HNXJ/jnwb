#!/usr/bin/env python3
"""Documentation form gate: the rules of ``docs/documentation_form.md`` a machine can settle.

Five checks, each run against a repository root (the live tree from the command line, a seeded
fixture tree from the suite):

  1. Vocabulary (F5). No superseded surface form from the contract's vocabulary table survives
     in the prose of the documentation corpus.
  2. Heading depth (F1). No heading deeper than ``###`` outside fenced code.
  3. Navigation (N1, N2, N3, N5). Every top-level ``nav`` entry of ``mkdocs.yml`` is a group,
     every group holds pages and no further groups, no group holds fewer than two pages, and
     every target resolves to a file under ``docs/``. N3 is checked through its premise: the
     contract derives it from N1 "given every page is in a group", so a page outside a group
     fails. N4 is a review item.
  4. Figure theme independence (G2). Every image a page shows is a light/dark pair
     (``#only-light`` and ``#only-dark``, the dark file named ``<stem>.dark.png``, both on
     disk), or is listed in ``THEME_NEUTRAL`` with a reason. An inline ``<svg>`` passes only
     when every color it draws with comes from the theme (``currentColor``, ``var(...)``,
     ``none``, ``transparent``, ``inherit``). Every fixed color a figure generator writes
     outside its per-theme table reads on both page backgrounds. G1 (transparent corners) stays
     with ``tests/test_figure_form.py``, which reads the pixels.
  5. Parallel facts in prose (F2, partly). A paragraph in which three or more distinct inline
     code subjects each open a clause with the same kind of predicate ("`a` returns ...,
     `b` returns ..., `c` returns ...") states comparable facts that belong in a table.

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

**Where the matching semantics live.** Prose stripping, the vocabulary matcher and row type,
the themed-image patterns and the fixed-color legibility test are imported from
``tests/test_documentation_form.py`` and ``tests/test_figure_form.py``, which check the live
tree with the same semantics. This module adds the root parameter those tests do not have, so
each rule can be shown to fail on a seeded fixture tree. The two places that re-read files
(the corpus and the vocabulary table) are held equal to the tests' own readers on the live tree
by ``tests/test_docs_form_gate.py``.

Exit code 0 when every check passes, 1 otherwise. A check that raises is reported ERROR and
the others still run.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests import test_documentation_form as _form  # noqa: E402
from tests import test_figure_form as _figures  # noqa: E402

for _module in (_form, _figures):
    # An unrelated installed package named `tests` would supply different semantics silently.
    if REPO_ROOT.resolve() not in Path(_module.__file__).resolve().parents:
        raise ImportError(f"{_module.__name__} resolved to {_module.__file__}, outside {REPO_ROOT}")

CONTRACT = Path("docs") / "documentation_form.md"

#: Images shown identically under both palette schemes, each with the reason that is safe.
THEME_NEUTRAL: Dict[str, str] = {
    "assets/jnwb-logo.png": "the project mark: transparent ground and a mid-tone mark, the same "
                            "file the theme header shows under both schemes",
}

Result = Tuple[List[str], str]


# ------------------------------------------------------------------------------ corpus


def corpus(root: Path) -> List[Tuple[str, str]]:
    """The pages the vocabulary and heading rules apply to, as (name, text).

    The same surfaces, in the same order and under the same names, as the corpus
    ``tests/test_documentation_form.py`` reads from the live tree.
    """
    docs = root / "docs"
    pages = [(p.name, p.read_text(encoding="utf-8"))
             for p in sorted(docs.glob("*.md")) if p.name != _form.GENERATED]
    readme = root / "README.md"
    if readme.is_file():
        pages.append(("README.md", readme.read_text(encoding="utf-8")))
    for page in sorted(docs.glob("*.md")):
        comments = _form._fenced_comments(page.read_text(encoding="utf-8"))
        if comments.strip():
            pages.append((f"{page.name} (code comments)", comments))
    generated = docs / _form.GENERATED
    if generated.is_file():
        pages.append((f"docs/{_form.GENERATED}", generated.read_text(encoding="utf-8")))
    for skill in sorted((root / "skills").glob("*/SKILL.md")):
        pages.append((f"skills/{skill.parent.name}/SKILL.md", skill.read_text(encoding="utf-8")))
    for script in sorted((root / "examples" / "tutorials").glob("*.py")):
        pages.append((f"examples/tutorials/{script.name}", script.read_text(encoding="utf-8")))
    return pages


def parse_vocabulary(contract_text: str) -> List["_form.VocabularyRow"]:
    """The rows of the contract's vocabulary table: concept, accepted forms, superseded forms."""
    match = _form._VOCABULARY_HEADING_LINE.search(contract_text)
    if match is None:
        return []
    section = contract_text[match.end():].split("\n## ", 1)[0]
    rows = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or "|---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 3 or cells[0].lower() == "concept":
            continue
        preferred = _form._BACKTICKED.findall(cells[1])
        superseded = _form._BACKTICKED.findall(cells[2])
        if preferred and superseded:
            rows.append(_form.VocabularyRow(cells[0], tuple(preferred), tuple(superseded)))
    return rows


_FENCE_LINE = re.compile(r"^\s*(```|~~~)")


def _unfenced_lines(text: str) -> Iterator[Tuple[int, str]]:
    """(line number, line) for every line outside fenced code, fence markers excluded."""
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if _FENCE_LINE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            yield number, line


# ------------------------------------------------------------------------ 1. vocabulary


def check_vocabulary(root: Path) -> Result:
    rows = parse_vocabulary((root / CONTRACT).read_text(encoding="utf-8"))
    if not rows:
        return [f"no vocabulary rows parsed from {CONTRACT.as_posix()}; F5 has nothing to "
                "check against"], ""
    pages = corpus(root)
    return _form.vocabulary_violations(pages, rows), (
        f"PASS: vocabulary (F5): no superseded form of {len(rows)} concepts in "
        f"{len(pages)} pages.")


# ---------------------------------------------------------------------- 2. heading depth


_DEEP_HEADING = re.compile(r"^#{4,}\s")


def check_heading_depth(root: Path) -> Result:
    pages = corpus(root)
    deep = [f"{name}:{number}: {line.strip()}"
            for name, text in pages
            for number, line in _unfenced_lines(text)
            if _DEEP_HEADING.match(line)]
    return deep, f"PASS: heading depth (F1): no heading below ### in {len(pages)} pages."


# -------------------------------------------------------------------------- 3. navigation


def check_navigation(root: Path) -> Result:
    config = yaml.safe_load((root / "mkdocs.yml").read_text(encoding="utf-8")) or {}
    nav = config.get("nav") or []
    if not nav:
        return ["mkdocs.yml has no nav entries"], ""
    violations: List[str] = []
    targets: List[str] = []
    groups = 0
    for entry in nav:
        if not (isinstance(entry, dict) and len(entry) == 1
                and isinstance(next(iter(entry.values())), list)):
            violations.append(f"N3: top-level entry outside a group: {entry!r}")
            targets.extend(_form._pages_under(entry))
            continue
        (title, children), = entry.items()
        groups += 1
        pages = _form._pages_under(children)
        targets.extend(pages)
        for child in children:
            if isinstance(child, dict) and not all(isinstance(v, str) for v in child.values()):
                violations.append(f"N1: group {title!r} nests a further group: {list(child)}")
            elif not isinstance(child, (str, dict)):
                violations.append(f"N1: group {title!r} holds an entry that is not a page: "
                                  f"{child!r}")
        if len(pages) < 2:
            violations.append(f"N2: group {title!r} holds {len(pages)} page(s)")
    for target in targets:
        if "://" not in target and not (root / "docs" / target).is_file():
            violations.append(f"N5: nav target docs/{target} does not exist")
    return violations, (
        f"PASS: navigation (N1, N2, N3, N5): {groups} groups, depth two, {len(targets)} targets, "
        "all resolving, none holding one page.")


# ------------------------------------------------------------------------------ 4. figures


_MD_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
_IMG_SRC = re.compile(r"<img\b[^>]*\bsrc=\"([^\"]+)\"")
_SVG = re.compile(r"<svg\b.*?</svg>", re.S | re.I)
_SVG_COLOR = re.compile(r"\b(fill|stroke|stop-color|color)\s*[=:]\s*[\"']?\s*([^\"';>\s]+)", re.I)
_THEME_COLORS = {"none", "currentcolor", "transparent", "inherit"}


def _local(src: str) -> bool:
    return not re.match(r"^[a-z][a-z0-9+.-]*:", src, re.I)


def check_figures(root: Path) -> Result:
    docs = root / "docs"
    violations: List[str] = []
    shown: Dict[Tuple[str, str], set] = {}
    for page in sorted(docs.rglob("*.md")):
        name = page.relative_to(docs).as_posix()
        text = page.read_text(encoding="utf-8")
        prose = "\n".join(line for _, line in _unfenced_lines(text))
        paired: Counter = Counter()
        for stem, dark, scheme in (_figures.IMAGE_LINE.findall(prose)
                                   + _figures.IMG_TAG.findall(prose)):
            if (scheme == "dark") != bool(dark):
                violations.append(f"{name}: {stem} shows the {'dark' if dark else 'light'} file "
                                  f"under #only-{scheme}")
            shown.setdefault((name, stem), set()).add(scheme)
            paired[f"{stem}{dark}.png#only-{scheme}"] += 1
        for src in _MD_IMAGE.findall(prose) + _IMG_SRC.findall(prose):
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
        for svg in _SVG.findall(prose):
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
    generators = [root / g.relative_to(_figures.REPO_ROOT) for g in _figures.GENERATORS]
    for generator in generators:
        label = generator.relative_to(root).as_posix()
        if not generator.is_file():
            violations.append(f"{label}: figure generator is missing")
            continue
        for offender in _figures._illegible_literals(generator.read_text(encoding="utf-8")):
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
    """Authored and contract pages: ``docs/*.md`` without the generated reference."""
    return [(p.name, p.read_text(encoding="utf-8"))
            for p in sorted((root / "docs").glob("*.md")) if p.name != _form.GENERATED]


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


# ---------------------------------------------------------------------------------- runner


CHECKS: Sequence[Tuple[str, Callable[[Path], Result]]] = (
    ("vocabulary", check_vocabulary),
    ("heading depth", check_heading_depth),
    ("navigation", check_navigation),
    ("figure theme independence", check_figures),
    ("parallel facts", check_parallel_facts),
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
