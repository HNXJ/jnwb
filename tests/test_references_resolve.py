"""Every citation on the references page resolves, and each docstring cites what the page says.

`docs/references.md` lists, per published source, the result jnwb implements and the functions
that implement it. The page and the docstrings are two copies of one claim, and nothing else
keeps them in step, so this module holds them to each other in both directions:

* every DOI on the page is well formed, and its link text and link target name the same DOI;
* every row names a result, not only a source;
* every function a method row lists exists and cites that row's DOI in its docstring;
* every function a pitfall row lists exists, and nothing in `jnwb/` cites that row's DOI: a
  paper that states a pitfall is cited from the page, and a docstring citing it belongs on a
  method row;
* every DOI cited anywhere in `jnwb/` is on the page;
* every public function whose docstring cites a DOI is listed on that DOI's row;
* every author-year citation in a `jnwb/vis` docstring names a row of the page. Those
  modules cite by author and year rather than by DOI, and `jnwb.vis` is a module that the
  public-callable walk skips, so the DOI checks above cannot see them.
* every core-text row carries an ISBN-13 with a valid check digit and names jnwb functions that
  resolve;
* every study row is marked replicated or partially replicated, and its receipt names tests
  that exist and paths that exist.

Whether a DOI is registered needs the network, which the suite does not use. The page states
the date its DOIs were resolved; this module checks that what it lists is shaped like a DOI and
that the docstrings agree with it.
"""

from __future__ import annotations

import ast
import inspect
import re
import sys
import urllib.parse
from pathlib import Path

import pytest

import jnwb

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parents[1]))  # needed: wheel run clears pythonpath

from scripts.build_fact_graph import (  # noqa: E402
    CORE_HEADER,
    METHOD_HEADER,
    PAGE_LINK,
    PITFALL_HEADER,
    REPRODUCTION_HEADER,
    normalize_doi as _norm,
    reference_functions,
    reference_row_doi as _row_doi,
    reference_rows as _rows,
)

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "references.md"
PACKAGE = ROOT / "jnwb"

#: Crossref's pattern for modern DOIs, widened by ``<`` and ``>``, which the SICI-style DOI of
#: Torrence & Compo (1998) carries.
DOI_SHAPE = re.compile(r"^10\.\d{4,9}/[-._;()/:<>A-Za-z0-9]+$")
SOURCE_DOI = re.compile(r"doi:(10\.[^\s`'\"]+)")
#: A surname, optionally followed by "et al." or "& Coauthor", then a year.
AUTHOR_YEAR = re.compile(
    r"\b([A-Z][\w'-]+)(?:\s+et al\.?|\s+(?:&|and)\s+[A-Z][\w'-]+)?,?\s+\(?((?:19|20)\d{2})\b"
)
ROW_YEAR = re.compile(r"\(((?:19|20)\d{2})\)")


def _resolve(name: str):
    obj = jnwb
    for part in name.split("."):
        obj = getattr(obj, part)
    return obj


def _doc_dois(obj) -> set[str]:
    return {_norm(d) for d in SOURCE_DOI.findall(inspect.getdoc(obj) or "")}


def _public_callables():
    """``(qualified name, object)`` for public functions and public methods of public classes."""
    for name in jnwb.__all__:
        try:
            obj = getattr(jnwb, name)
        except ImportError:  # an optional extra that is not installed carries no citation
            continue
        if inspect.ismodule(obj):
            continue
        if inspect.isclass(obj):
            for attr, raw in vars(obj).items():
                if attr.startswith("_"):
                    continue
                member = getattr(obj, attr)
                if callable(member) or isinstance(raw, (staticmethod, classmethod)):
                    yield f"{name}.{attr}", member
        elif callable(obj):
            yield name, obj


@pytest.fixture(scope="module")
def page() -> str:
    return PAGE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rows(page):
    return _rows(page)


@pytest.fixture(scope="module")
def method_rows(page):
    return _rows(page, METHOD_HEADER)


@pytest.fixture(scope="module")
def pitfall_rows(page):
    return _rows(page, PITFALL_HEADER)


def test_the_page_parses_into_rows(rows, method_rows, pitfall_rows):
    # A parser that silently matched nothing would make every test below vacuous.
    assert len(rows) >= 20, f"only {len(rows)} reference rows parsed; the table parser is wrong"
    assert len(method_rows) >= 20, f"only {len(method_rows)} method rows parsed"
    assert pitfall_rows, "no pitfall row parsed; the header match is wrong"
    assert len(method_rows) + len(pitfall_rows) == len(rows)


def test_every_doi_is_well_formed_and_its_link_agrees(page):
    links = PAGE_LINK.findall(page)
    assert len(links) >= 20, f"only {len(links)} DOI links matched; the link regex is wrong"
    for text, target in links:
        assert DOI_SHAPE.match(text), f"not a well-formed DOI: {text!r}"
        assert urllib.parse.unquote(target) == text, (
            f"link text doi:{text} points at https://doi.org/{target}, a different DOI"
        )


def test_every_row_names_the_result_it_implements(rows):
    for reference, result, _ in rows:
        assert len(result.split()) >= 3, (
            f"{reference[:60]}... names no result; a row cites a result, not only a source"
        )


def test_every_listed_function_cites_its_row(method_rows):
    for reference, _, functions in method_rows:
        doi = _row_doi(reference)
        names = reference_functions(functions)
        assert names, f"the row for doi:{doi} lists no function"
        for name in names:
            try:
                obj = _resolve(name)
            except AttributeError:
                pytest.fail(f"the row for doi:{doi} lists `{name}`, which jnwb does not have")
            assert doi in _doc_dois(obj), (
                f"the row for doi:{doi} lists `{name}`, whose docstring does not cite that DOI"
            )


def test_a_pitfall_row_names_functions_and_no_source_cites_it(pitfall_rows):
    source = "\n".join(p.read_text(encoding="utf-8") for p in sorted(PACKAGE.rglob("*.py")))
    cited = {_norm(doi) for doi in SOURCE_DOI.findall(source)}
    for reference, _, functions in pitfall_rows:
        doi = _row_doi(reference)
        names = reference_functions(functions)
        assert names, f"the pitfall row for doi:{doi} lists no function"
        for name in names:
            try:
                _resolve(name)
            except AttributeError:
                pytest.fail(f"the pitfall row for doi:{doi} lists `{name}`, which jnwb does not have")
        assert doi not in cited, (
            f"jnwb/ cites doi:{doi}, a pitfall row; a cited paper's method belongs on a method row"
        )


def test_every_doi_in_the_package_is_on_the_page(page):
    on_page = {_norm(text) for text, _ in PAGE_LINK.findall(page)}
    cited = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        for doi in SOURCE_DOI.findall(path.read_text(encoding="utf-8")):
            cited.setdefault(_norm(doi), path.relative_to(ROOT).as_posix())
    assert len(cited) >= 20, f"only {len(cited)} DOIs found in jnwb/; the scan is wrong"
    missing = {doi: where for doi, where in cited.items() if doi not in on_page}
    assert not missing, f"cited in the package but absent from docs/references.md: {missing}"


def test_every_citing_function_is_listed_on_its_row(rows):
    listed: dict[str, set[str]] = {}
    for reference, _, functions in rows:
        listed[_row_doi(reference)] = set(reference_functions(functions))
    checked = 0
    for name, obj in _public_callables():
        for doi in _doc_dois(obj):
            checked += 1
            assert name in listed.get(doi, set()), (
                f"`{name}` cites doi:{doi}, but docs/references.md does not list it there"
            )
    assert checked >= 20, f"only {checked} citations found in public docstrings; the walk is wrong"


def test_every_author_year_citation_in_vis_is_on_the_page(rows):
    on_page = set()
    for reference, _, _ in rows:
        year = ROW_YEAR.search(reference)
        if year:
            on_page.add((reference.split(",")[0].strip().lower(), year.group(1)))
    cited = []
    for path in sorted((PACKAGE / "vis").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for surname, year in AUTHOR_YEAR.findall(ast.get_docstring(node) or ""):
                    cited.append((surname, year, path.relative_to(ROOT).as_posix()))
    assert cited, "no author-year citation found in jnwb/vis; the scan is wrong"
    missing = [c for c in cited if (c[0].lower(), c[1]) not in on_page]
    assert not missing, f"cited in jnwb/vis but absent from docs/references.md: {missing}"


def test_a_malformed_doi_is_rejected():
    assert not DOI_SHAPE.match("10.1016 /j.jneumeth.2007.03.024")
    assert not DOI_SHAPE.match("doi:10.1016/j.jneumeth.2007.03.024")
    assert DOI_SHAPE.match("10.1175/1520-0477(1998)079<0061:APGTWA>2.0.CO;2")


# ------------------------------------------------------------------ core texts and studies

#: An ISBN-13 in a core-text row's reference cell, hyphens and spaces allowed.
ISBN_CELL = re.compile(r"ISBN ((?:978|979)[\d -]*\d)")
#: The opening of a study row's result cell.
REPRODUCTION_MARKERS = ("**Replicated.** ", "**Partially replicated.** ")
#: A backticked span of a receipt cell: ``<file>.py::<name>``, a test of the suite under ``tests/``, or a repository path.
RECEIPT_SPAN = re.compile(r"`([^`]+)`")


def isbn13_is_valid(isbn: str) -> bool:
    digits = re.sub(r"[ -]", "", isbn)
    if not re.fullmatch(r"\d{13}", digits):
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12]))
    return (10 - total % 10) % 10 == int(digits[12])


def _function_problem(name: str) -> str | None:
    """Why a core-text function is not a jnwb name that imports, or None when it is one."""
    if not name.startswith("jnwb."):
        return f"`{name}` is not spelled jnwb.<name>"
    path = name[len("jnwb."):]
    if "." not in path and path not in jnwb.__all__:
        return f"`{name}` is not in jnwb.__all__"
    try:
        _resolve(path)
    except AttributeError:
        return f"`{name}` does not resolve through import"
    return None


def isbn_problems(core) -> list[str]:
    problems = []
    for reference, _, _ in core:
        found = ISBN_CELL.findall(reference)
        if len(found) != 1 or not isbn13_is_valid(found[0]):
            problems.append(f"no valid ISBN-13: {reference[:60]}")
    return problems


def core_function_problems(core) -> list[str]:
    problems = []
    for reference, _, functions in core:
        names = reference_functions(functions)
        if not names:
            problems.append(f"lists no function: {reference[:60]}")
        problems += [p for p in map(_function_problem, names) if p]
    return problems


def reproduction_marker_problems(studies) -> list[str]:
    return [f"no replicated marker: {reference[:60]}"
            for reference, result, _ in studies if not result.startswith(REPRODUCTION_MARKERS)]


def _test_defined(path: Path, name: str) -> bool:
    """Whether the file at ``path`` defines the test ``name`` or ``Class::name``, read by ast."""
    parts = name.split("::")
    scope = ast.parse(path.read_text(encoding="utf-8")).body
    for part in parts[:-1]:
        scope = next((node.body for node in scope
                      if isinstance(node, ast.ClassDef) and node.name == part), [])
    return parts[-1].startswith("test") and any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == parts[-1]
        for node in scope)


def receipt_problems(studies) -> list[str]:
    problems = []
    for reference, _, receipt in studies:
        spans = RECEIPT_SPAN.findall(receipt)
        if not spans:
            problems.append(f"names no receipt: {reference[:60]}")
        for span in spans:
            if "::" in span:
                file, _, name = span.partition("::")
                if not (ROOT / "tests" / file).is_file() or not _test_defined(ROOT / "tests" / file, name):
                    problems.append(f"no such test: `{span}`")
            elif "/" in span and not (ROOT / span).exists():
                problems.append(f"no such path: `{span}`")
    return problems


@pytest.fixture(scope="module")
def core_rows(page):
    return _rows(page, CORE_HEADER)


@pytest.fixture(scope="module")
def studies(page):
    return _rows(page, REPRODUCTION_HEADER)


def test_the_new_tables_parse_and_the_method_checks_do_not_read_them(page, core_rows, studies):
    # A parser that matched nothing would make the checks below vacuous.
    assert len(core_rows) >= 14, f"only {len(core_rows)} core-text rows parsed"
    assert len(studies) >= 4, f"only {len(studies)} study rows parsed"
    assert len(_rows(page)) == len(_rows(page, METHOD_HEADER)) + len(_rows(page, PITFALL_HEADER))


def test_every_core_text_row_carries_an_isbn13_with_a_valid_check_digit(core_rows):
    assert isbn_problems(core_rows) == []


def test_every_core_text_function_is_a_jnwb_name_that_resolves(core_rows):
    examined = sum(len(reference_functions(functions)) for _, _, functions in core_rows)
    assert examined >= 20, f"only {examined} core-text functions examined"
    assert core_function_problems(core_rows) == []


def test_every_study_is_marked_replicated_or_partially_replicated(studies):
    assert reproduction_marker_problems(studies) == []


def test_every_study_receipt_names_a_test_or_path_that_exists(studies):
    examined = sum(len(RECEIPT_SPAN.findall(receipt)) for _, _, receipt in studies)
    assert examined >= 6, f"only {examined} receipt spans examined"
    assert receipt_problems(studies) == []


@pytest.mark.parametrize("old, new, check", [
    ("ISBN 9780262019873", "ISBN 9780262019874", "isbn"),
    ("`jnwb.nested_cv_linear_svm`", "`jnwb.nested_cv_linear_svn`", "function"),
    ("**Partially replicated.** Overall kappa", "**Partly replicated.** Overall kappa", "marker"),
    ("test_no_window_returns_an_empty_result", "test_no_window_returns_nothing", "receipt"),
])
def test_the_new_checks_fail_on_a_planted_defect(page, old, new, check):
    # Each edit is applied to the live page text; the anchor must occur exactly once.
    assert page.count(old) == 1, f"the anchor {old!r} occurs {page.count(old)} times"
    planted = page.replace(old, new)
    checks = {
        "isbn": lambda text: isbn_problems(_rows(text, CORE_HEADER)),
        "function": lambda text: core_function_problems(_rows(text, CORE_HEADER)),
        "marker": lambda text: reproduction_marker_problems(_rows(text, REPRODUCTION_HEADER)),
        "receipt": lambda text: receipt_problems(_rows(text, REPRODUCTION_HEADER)),
    }
    assert checks[check](page) == [], "the live page must pass before a defect is planted"
    assert checks[check](planted), f"the {check} check missed a planted defect"
