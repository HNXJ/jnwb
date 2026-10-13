"""Gate 18 (API member types): docs/api.md against the runtime objects."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]


#: `| jnwb.NAME | type | cell |`. The description cell admits pipes of its own -- a rendered union
#: such as `-> str | None` -- so the `$` anchor is what makes the closing pipe unambiguous.
#: Shared with `tests/test_api_md_member_types.py`, which imports it from here.
API_MD_ROW = re.compile(
    r"^\|\s*jnwb\.([A-Za-z_][A-Za-z0-9_]*)\s*\|([^|]*)\|(.*)\|\s*$",
    re.MULTILINE,
)


def api_member_kind(obj: Any) -> str:
    """What an export is, asked of the object itself.

    A property rather than a list of known types. The defect this answers existed because the
    generator asked ``isinstance(obj, (dict, tuple, frozenset, list))``: an enumeration has to be
    maintained, and the one scalar constant in `__all__` was missing from it.
    """
    import inspect

    if inspect.isclass(obj):
        return "class"
    if inspect.ismodule(obj):
        return "module"
    if callable(obj):
        return "function"
    return "constant"


def api_md_parameter_kinds(cell: str) -> Optional[List[Tuple[str, str]]]:
    """``(name, kind)`` for each parameter a rendered ``(...)`` signature cell declares.

    ``kind`` is the lower-cased ``inspect.Parameter`` kind name. The ``/`` and ``*`` markers,
    ``*args`` and ``**kwargs`` decide it, as they do in Python source. Returns None when the
    cell does not open with a signature (a class, or a callable ``inspect`` cannot sign).

    Parsed here rather than taken from ``scripts.generate_api_md``, for the reason gate 18 gives:
    a generator that drops a marker would otherwise write the same wrong kinds on both sides.
    """
    # The page renders a signature as a Markdown code span; the backticks are markup.
    text = cell.strip().lstrip("`")
    if not text.startswith("("):
        return None
    depth, quote, end = 0, "", -1
    tokens: List[str] = []
    start = 1
    for index, char in enumerate(text):
        if quote:
            if char == quote and text[index - 1] != "\\":
                quote = ""
        elif char in "'\"":
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth == 0:
                end = index
                break
        elif char == "," and depth == 1:
            tokens.append(text[start:index])
            start = index + 1
    if end < 0:
        return None
    tokens.append(text[start:end])

    parsed: List[Tuple[str, str]] = []
    keyword_only = False
    for token in (t.strip() for t in tokens):
        if not token:
            continue
        if token == "/":
            parsed = [(name, "positional_only") for name, _ in parsed]
        elif token == "*":
            keyword_only = True
        elif token.startswith("**"):
            parsed.append((re.match(r"\*\*(\w+)", token).group(1), "var_keyword"))
        elif token.startswith("*"):
            parsed.append((re.match(r"\*(\w+)", token).group(1), "var_positional"))
            keyword_only = True
        else:
            name = re.match(r"\w+", token)
            parsed.append((name.group(0) if name else token,
                           "keyword_only" if keyword_only else "positional_or_keyword"))
    return parsed


def check_api_md_member_types(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 18 (API Member Types): each `docs/api.md` Type cell is true of the runtime object.

    **Gate 9 is a fixed point and this is the way out of it.** Its two checks are
    `check_documented_api_matches_all`, which matches the first column only and compares that set
    of names to `jnwb.__all__`, and `check_api_md_is_generated`, which regenerates the page and
    compares it to the committed copy. The first never looks at the Type column; the second
    asserts that the page agrees with the generator, never that either agrees with the runtime. A
    wrong answer produced inside the generator is written into both sides of that comparison,
    where it cancels.

    P-151 proved it rather than arguing it: with `_object_type_name` returning the literal
    ``"BLINDSPOT"`` for every export and the page regenerated from it, all 156 rows declared a
    type true of nothing and the harness still reported ``ALL HARNESS GATES PASSED. 16 of 16``.

    So the oracle is `api_member_kind`, stated here and asked of the live object. It is
    deliberately **not** imported from `scripts.generate_api_md`: importing the generator's own
    classifier would rebuild the fixed point inside the gate that exists to break it.

    Each function row's parameter names and kinds are compared the same way, parsed from the
    rendered cell by `api_md_parameter_kinds` and asked of `inspect.signature`, so a dropped `*`
    or `/` marker fails here even when the generator and the page agree.

    **What this gate cannot see:** annotations, defaults and the description. A row whose
    parameters are right and whose defaults are wrong passes here;
    `tests/test_docs_call_shapes.py` is what covers documented calls, and P-84 records where it
    does not.
    """
    root = repo_root or REPO_ROOT
    page = root / "docs" / "api.md"
    if not page.is_file():
        return [f"API_TYPE: {page} is missing; the sweep is broken, not the tree"]

    import jnwb

    rows = [
        (m.group(1), m.group(2).strip(), m.group(3))
        for m in API_MD_ROW.finditer(page.read_text(encoding="utf-8"))
    ]
    violations: List[str] = []

    # The vacuity guard comes first and is not optional. Every check below iterates `rows`, so a
    # regex that matches nothing satisfies all of them while asserting nothing -- and a Type
    # column nobody parses is exactly the hole this gate was added to close.
    names = [name for name, _, _ in rows]
    exported = sorted(jnwb.__all__)
    if sorted(names) != exported:
        violations.append(
            f"API_TYPE: parsed {len(names)} rows against {len(exported)} exports; "
            f"missing={sorted(set(exported) - set(names))}, "
            f"extra={sorted(set(names) - set(exported))}, "
            f"duplicated={sorted({n for n in names if names.count(n) > 1})}. "
            "Until the parse covers every export, the type comparison below is not a check."
        )
        return violations

    from jnwb._lazy_exports import OPTIONAL_SUBMODULES

    import inspect

    signed = 0
    for name, declared, cell in rows:
        try:
            obj = getattr(jnwb, name)
        except ImportError:
            # An optional submodule whose extra is not installed here. Its import spec is
            # what can be asked without the extra: an importable spec is a module.
            if name not in OPTIONAL_SUBMODULES:
                raise
            import importlib.util

            spec = importlib.util.find_spec(f"jnwb.{name}")
            if spec is None:
                violations.append(f"API_TYPE: jnwb.{name} has no importable source")
                continue
            # Built from the spec and never executed, so nothing it imports is needed.
            obj = importlib.util.module_from_spec(spec)
        expected = api_member_kind(obj)
        if not declared:
            violations.append(f"API_TYPE: jnwb.{name} has an empty Type cell")
        elif declared != expected:
            violations.append(
                f"API_TYPE: jnwb.{name}: docs/api.md says '{declared}', the runtime object is "
                f"'{expected}' (type {type(obj).__name__}). Gate 9 cannot see this: it compares "
                "the page to the generator, and a wrong answer inside the generator is on both "
                "sides of that comparison."
            )
        if expected != "function":
            continue
        try:
            live = [(p.name, p.kind.name.lower()) for p in inspect.signature(obj).parameters.values()]
        except (TypeError, ValueError):
            live = None
        shown = api_md_parameter_kinds(cell)
        if live is None and shown is None:
            continue
        signed += 1
        if shown != live:
            violations.append(
                f"API_KIND: jnwb.{name}: docs/api.md shows parameters {shown}, inspect.signature "
                f"gives {live}. A keyword-only parameter shown without its `*` reads as "
                "positional, so the page documents a call that raises."
            )
    if not signed:
        violations.append("API_KIND: no function row carried a signature, so the parameter-kind "
                          "comparison checked nothing")
    return violations
