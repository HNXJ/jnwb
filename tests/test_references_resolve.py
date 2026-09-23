"""Every citation on the references page resolves, and each docstring cites what the page says.

`docs/references.md` lists, per published source, the result jnwb implements and the functions
that implement it. The page and the docstrings are two copies of one claim, and nothing else
keeps them in step, so this module holds them to each other in both directions:

* every DOI on the page is well formed, and its link text and link target name the same DOI;
* every row names a result, not only a source;
* every function a row lists exists and cites that row's DOI in its docstring;
* every DOI cited anywhere in `jnwb/` is on the page;
* every public function whose docstring cites a DOI is listed on that DOI's row.

Whether a DOI is registered needs the network, which the suite does not use. The page states
the date its DOIs were resolved; this module checks that what it lists is shaped like a DOI and
that the docstrings agree with it.
"""

from __future__ import annotations

import inspect
import re
import urllib.parse
from pathlib import Path

import pytest

import jnwb

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "references.md"
PACKAGE = ROOT / "jnwb"

#: Crossref's pattern for modern DOIs, widened by ``<`` and ``>``, which the SICI-style DOI of
#: Torrence & Compo (1998) carries.
DOI_SHAPE = re.compile(r"^10\.\d{4,9}/[-._;()/:<>A-Za-z0-9]+$")
#: The target may hold one level of balanced parentheses, as Markdown allows and the SICI DOI needs.
PAGE_LINK = re.compile(r"\[doi:([^\]]+)\]\(https://doi\.org/((?:[^()\s]|\([^()\s]*\))+)\)")
SOURCE_DOI = re.compile(r"doi:(10\.[^\s`'\"]+)")
CODE_SPAN = re.compile(r"`([^`]+)`")


def _norm(doi: str) -> str:
    """DOIs compare case-insensitively; a sentence may end right after one."""
    return doi.rstrip(".,").lower()


def _rows(text: str) -> list[tuple[str, str, str]]:
    """``(reference, result, functions)`` for every body row of every references table."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line) <= set("|- "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and cells[0] == "Reference":
            continue
        assert len(cells) == 3, f"a references row does not have three cells: {line[:80]}"
        rows.append((cells[0], cells[1], cells[2]))
    return rows


def _row_doi(reference_cell: str) -> str:
    links = PAGE_LINK.findall(reference_cell)
    assert len(links) == 1, f"a row must carry exactly one DOI link: {reference_cell[:80]}"
    return _norm(links[0][0])


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


def test_the_page_parses_into_rows(rows):
    # A parser that silently matched nothing would make every test below vacuous.
    assert len(rows) >= 20, f"only {len(rows)} reference rows parsed; the table parser is wrong"


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


def test_every_listed_function_cites_its_row(rows):
    for reference, _, functions in rows:
        doi = _row_doi(reference)
        names = CODE_SPAN.findall(functions)
        assert names, f"the row for doi:{doi} lists no function"
        for name in names:
            try:
                obj = _resolve(name)
            except AttributeError:
                pytest.fail(f"the row for doi:{doi} lists `{name}`, which jnwb does not have")
            assert doi in _doc_dois(obj), (
                f"the row for doi:{doi} lists `{name}`, whose docstring does not cite that DOI"
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
        listed[_row_doi(reference)] = set(CODE_SPAN.findall(functions))
    checked = 0
    for name, obj in _public_callables():
        for doi in _doc_dois(obj):
            checked += 1
            assert name in listed.get(doi, set()), (
                f"`{name}` cites doi:{doi}, but docs/references.md does not list it there"
            )
    assert checked >= 20, f"only {checked} citations found in public docstrings; the walk is wrong"


def test_a_malformed_doi_is_rejected():
    assert not DOI_SHAPE.match("10.1016 /j.jneumeth.2007.03.024")
    assert not DOI_SHAPE.match("doi:10.1016/j.jneumeth.2007.03.024")
    assert DOI_SHAPE.match("10.1175/1520-0477(1998)079<0061:APGTWA>2.0.CO;2")
