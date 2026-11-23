"""Every exception a public function raises in its own body is named in its Raises section.

The walk covers each function in `jnwb.__all__`: the `raise` statements in the function's own
body (nested functions, lambdas and classes excluded; a bare re-raise skipped) against the
words of its docstring's Raises section, Google (`Raises:`) or NumPy (`Raises` / `------`)
form. A raised call to a helper whose return annotation names a class counts as that class.
Exceptions raised inside called helpers are out of scope.
"""
from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

import pytest

import jnwb

_SECTION = re.compile(
    r"^\s*(Args|Arguments|Parameters|Returns|Return|Yields|Raises|Warns|Warnings|Example|"
    r"Examples|Notes|Note|References|See Also|Attributes|Todo)\s*:?\s*$")

#: Excluded with the reason; an entry that stops being flagged fails `test_exclusions_are_live`.
EXCLUDED = {
    # Not routed by any skill (`INTERNAL` in tests/test_skill_symbol_coverage.py); a documented
    # contract for it needs a skill row first.
    "assert_mergeable": ("KeyError", "ValueError"),
}


def raises_section(doc: str | None) -> str:
    """The text of the docstring's Raises section, or '' when it has none."""
    out: list[str] = []
    inside = False
    for line in (doc or "").splitlines():
        match = _SECTION.match(line)
        if match:
            if inside:
                break
            inside = match.group(1) == "Raises"
            continue
        if inside:
            out.append(line)
    return "\n".join(out)


def _own_raises(node: ast.AST):
    stack = list(ast.iter_child_nodes(node))
    while stack:
        sub = stack.pop()
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(sub, ast.Raise):
            yield sub
        stack.extend(ast.iter_child_nodes(sub))


def _factories(scopes) -> dict[str, str]:
    """Functions in `scopes` whose return annotation names a class: name -> that class."""
    out: dict[str, str] = {}
    for scope in scopes:
        for sub in ast.walk(scope):
            if (isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and isinstance(sub.returns, ast.Name)):
                out[sub.name] = sub.returns.id
    return out


def _exception_name(raise_node: ast.Raise, factories: dict[str, str]) -> str | None:
    exc = raise_node.exc
    if isinstance(exc, ast.Call):
        exc = exc.func
        if isinstance(exc, ast.Name) and exc.id in factories:
            return factories[exc.id]
    if isinstance(exc, ast.Attribute):
        return exc.attr
    if isinstance(exc, ast.Name):
        return exc.id
    return None


def _def_node(func):
    path = inspect.getsourcefile(func)
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    scope, node = tree.body, None
    for part in [p for p in func.__qualname__.split(".") if p != "<locals>"]:
        matches = [s for s in scope
                   if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                   and s.name == part]
        if not matches:
            return path, None, tree
        node = matches[-1]
        scope = node.body
    return path, node, tree


def audit(module=jnwb):
    """(missing, unresolved, examined) over the functions in ``module.__all__``.

    missing: {name: (path, line, sorted undocumented exception names)};
    unresolved: [(name, path, line, why)] for raises whose class the walk cannot name;
    examined: the names of the functions walked.
    """
    missing, unresolved, examined = {}, [], []
    for name in sorted(module.__all__):
        obj = inspect.unwrap(getattr(module, name))
        if not inspect.isfunction(obj):
            continue
        examined.append(name)
        path, node, tree = _def_node(obj)
        if node is None:
            unresolved.append((name, path, 0, "definition not found"))
            continue
        top = [s for s in tree.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))]
        factories = {**_factories(top), **_factories([node])}
        documented = set(re.findall(r"\b\w+\b", raises_section(ast.get_docstring(node))))
        undocumented: dict[str, int] = {}
        for raise_node in _own_raises(node):
            if raise_node.exc is None:
                continue
            exc = _exception_name(raise_node, factories)
            if exc is None or not exc[:1].isupper():
                unresolved.append((name, path, raise_node.lineno, f"raises a value: {exc}"))
            elif exc not in documented:
                undocumented.setdefault(exc, raise_node.lineno)
        if undocumented:
            missing[name] = (path, node.lineno, tuple(sorted(undocumented)))
    return missing, unresolved, examined


@pytest.fixture(scope="module")
def result():
    return audit()


def test_every_public_raise_is_documented(result):
    missing, _, examined = result
    assert len(examined) > 100, f"fixture must walk the public functions, walked {len(examined)}"
    offending = {n: v for n, v in missing.items() if n not in EXCLUDED}
    assert not offending, "\n".join(
        f"{path}:{line} {name}: Raises omits {', '.join(excs)}"
        for name, (path, line, excs) in sorted(offending.items()))


def test_every_raise_names_a_class(result):
    _, unresolved, _ = result
    assert not unresolved, unresolved


def test_exclusions_are_live(result):
    missing, _, _ = result
    for name, excs in EXCLUDED.items():
        assert name in jnwb.__all__, f"{name} is no longer public; drop its exclusion"
        assert name in missing and missing[name][2] == excs, (
            f"{name}: exclusion records {excs}, the walk finds "
            f"{missing.get(name, (None, None, ()))[2]}; update or drop it")


def test_the_walk_flags_a_planted_undocumented_raise():
    source = (
        "def f(x):\n"
        "    '''Doc.\n\n    Raises:\n        ValueError: If x is negative.\n    '''\n"
        "    if x < 0:\n        raise ValueError(x)\n"
        "    if x > 9:\n        raise TypeError(x)\n"
        "    def g():\n        raise KeyError(x)\n"
        "    raise\n")
    node = ast.parse(source).body[0]
    documented = set(re.findall(r"\b\w+\b", raises_section(ast.get_docstring(node))))
    raised = {_exception_name(r, {}) for r in _own_raises(node) if r.exc is not None}
    assert raised == {"ValueError", "TypeError"}, raised
    assert raised - documented == {"TypeError"}
