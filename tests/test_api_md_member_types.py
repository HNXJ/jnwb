r"""The Type column of docs/api.md must be true of the runtime object; gate 9 cannot check it.

Gate 9 is two checks and neither constrains that column. `check_documented_api_matches_all`
matches `^\|\s*jnwb\.(NAME)\s*\|`, the first column only, and compares that set of names
against `jnwb.__all__`. `check_api_md_is_generated` regenerates the page and compares it to the
committed one, so it asserts that the page agrees with the generator, never that either agrees
with the runtime. A wrong answer produced inside the generator is a fixed point of gate 9: it
is written into both sides of the comparison, where it cancels.

Measured at 89e954a0 -- with `_object_type_name` returning the literal "BLINDSPOT" for every
export and the page regenerated from it, all 156 rows declared a type true of nothing and the
harness still reported `ALL HARNESS GATES PASSED. 16 of 16`.

The oracle below is written out here rather than imported from `scripts.generate_api_md`;
importing the generator's own classifier would rebuild that fixed point.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

import jnwb

# No `sys.path.insert(0, REPO_ROOT)` here, deliberately. Prepending the checkout re-shadows the
# installed copy for the whole session, which is what P-39 recorded and what
# `test_the_suite_can_qualify_an_installed_copy.py` fails the suite over. It is also redundant:
# `pyproject.toml` sets pytest's `pythonpath = ["."]`, so the checkout is already importable,
# and 63 other test modules import jnwb plainly. REPO_ROOT stays -- it locates the page on disk,
# which is a file lookup rather than an import path.
REPO_ROOT = Path(__file__).resolve().parents[1]

API_MD = REPO_ROOT / "docs" / "api.md"

#: `| jnwb.NAME | type | cell |`. The cell group admits pipes of its own: 37 of the 156 cells
#: contain one, from a rendered union such as `-> str | None`. The `$` anchor is what makes the
#: closing pipe unambiguous -- measured, a non-greedy cell group parses all 156 rows
#: identically, so the anchor carries this and the greediness does not.
ROW = re.compile(
    r"^\|\s*jnwb\.([A-Za-z_][A-Za-z0-9_]*)\s*\|([^|]*)\|(.*)\|\s*$",
    re.MULTILINE,
)


def parsed_rows() -> List[Tuple[str, str, str]]:
    """Every reference row as (symbol, declared type, description cell)."""
    text = API_MD.read_text(encoding="utf-8")
    return [(m.group(1), m.group(2).strip(), m.group(3).strip()) for m in ROW.finditer(text)]


def expected_kind(obj: Any) -> str:
    """What the object is, asked of the object.

    A property rather than a list of known constant types. The defect this file pins existed
    because the generator asked `isinstance(obj, (dict, tuple, frozenset, list))`: an
    enumeration has to be maintained, and the one scalar constant in `__all__` was missing
    from it.
    """
    if inspect.isclass(obj):
        return "class"
    if inspect.ismodule(obj):
        return "module"
    if callable(obj):
        return "function"
    return "constant"


def constant_rows() -> Iterator[Tuple[str, Any, str]]:
    for name, _declared, cell in parsed_rows():
        obj = getattr(jnwb, name)
        if expected_kind(obj) == "constant":
            yield name, obj, cell


class TestTheParseIsNotVacuous:
    """Every assertion below iterates parsed rows, so a parser matching nothing satisfies all
    of them while checking nothing. That is this repository's dominant failure shape, so the
    guard is a test rather than a comment."""

    def test_every_export_is_parsed_exactly_once(self):
        names = [name for name, _, _ in parsed_rows()]
        assert names, "the row regex matched nothing; every assertion below is vacuous"
        assert sorted(names) == sorted(jnwb.__all__), (
            f"{len(names)} rows parsed against {len(jnwb.__all__)} exports; "
            f"missing={sorted(set(jnwb.__all__) - set(names))}, "
            f"extra={sorted(set(names) - set(jnwb.__all__))}, "
            f"duplicated={sorted({n for n in names if names.count(n) > 1})}"
        )

    def test_every_type_cell_is_populated(self):
        blank = [name for name, declared, _ in parsed_rows() if not declared]
        assert blank == [], f"rows with an empty Type cell: {blank}"


class TestDeclaredTypeIsTrueOfTheRuntimeObject:
    def test_no_non_callable_export_is_typed_function(self):
        """`jnwb.SKILLS_URL` is a `str` built from `jnwb.__version__`. It was typed
        "function" and described by the `str` constructor signature, so the page told a
        reader to call a URL."""
        offenders = [
            f"jnwb.{name} is typed 'function' but callable() is False "
            f"(runtime type {type(getattr(jnwb, name)).__name__})"
            for name, declared, _ in parsed_rows()
            if declared == "function" and not callable(getattr(jnwb, name))
        ]
        assert offenders == [], "; ".join(offenders)

    def test_no_callable_export_is_typed_constant(self):
        """The other direction, so a generator emitting one label for everything is caught."""
        offenders = [
            f"jnwb.{name} is typed 'constant' but is callable"
            for name, declared, _ in parsed_rows()
            if declared == "constant" and callable(getattr(jnwb, name))
        ]
        assert offenders == [], "; ".join(offenders)

    def test_every_declared_type_agrees_with_the_object(self):
        """The biconditional over all four kinds. The two tests above each pass when the
        label is wrong in the direction the other covers."""
        offenders = []
        for name, declared, _ in parsed_rows():
            obj = getattr(jnwb, name)
            expected = expected_kind(obj)
            if declared != expected:
                offenders.append(
                    f"jnwb.{name}: page says '{declared}', runtime says '{expected}' "
                    f"(type {type(obj).__name__})"
                )
        assert offenders == [], "; ".join(offenders)


class TestConstantRowsDescribeTheValueAndNotItsType:
    """`inspect.getdoc(value)` falls back to `type(value).__doc__`.

    Asking a constant for its docstring returns the builtin type's, which is true of `str` or
    `dict` and false of the constant. At 89e954a0 all five constants carried exactly that,
    with `inspect.getdoc(obj) == inspect.getdoc(type(obj))` holding for every one.
    """

    def test_at_least_one_constant_is_exercised(self):
        """Guard: the tests below iterate a filtered subset, which an empty filter satisfies."""
        assert list(constant_rows()), "no constant rows found; the tests below are vacuous"

    def test_no_constant_row_carries_its_builtin_types_docstring(self):
        offenders = []
        for name, obj, cell in constant_rows():
            type_doc = inspect.getdoc(type(obj)) or ""
            if not type_doc:
                continue
            first = type_doc.strip().split("\n\n")[0].replace("\n", " ").strip()
            if first and first in cell:
                offenders.append(
                    f"jnwb.{name} is described by {type(obj).__name__}'s own docstring "
                    f"({first[:50]!r}...), which describes the type and not the value"
                )
        assert offenders == [], "; ".join(offenders)

    def test_every_constant_row_names_its_runtime_type(self):
        """`in` rather than `==`, so the cell may be elaborated later; what is forbidden is an
        empty cell or the wrong type."""
        offenders = [
            f"jnwb.{name}: cell {cell!r} does not name its runtime type "
            f"{type(obj).__qualname__!r}"
            for name, obj, cell in constant_rows()
            if type(obj).__qualname__ not in cell
        ]
        assert offenders == [], "; ".join(offenders)

    def test_no_constant_row_reproduces_the_constants_value(self):
        """`SKILLS_URL` interpolates `jnwb.__version__`. This page regenerates on demand, so a
        rendered value would freeze one release's version into a committed file."""
        offenders = [
            f"jnwb.{name}: the page reproduces the constant's value, which will go stale"
            for name, obj, cell in constant_rows()
            if isinstance(obj, str) and obj and obj in cell
        ]
        assert offenders == [], "; ".join(offenders)
