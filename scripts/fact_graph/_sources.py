"""One read, one parse and one walk per source in a build.

``shared_sources`` opens a cache that ``read_source``, ``parse_source``, ``function_tree`` and
``walk_tree`` fill, so every scan of one build reads each file once and parses each source text
once; outside it each call reads, parses or walks afresh. A tree is shared between scans, so no
scan may change one.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

_cache: Optional[Dict[str, Dict[Any, Any]]] = None


@contextmanager
def shared_sources() -> Iterator[None]:
    """Share reads, parses and walks until the block ends; a nested block joins the outer one."""
    global _cache
    outer = _cache
    if outer is None:
        _cache = {"text": {}, "tree": {}, "function": {}, "walk": {}}
    try:
        yield
    finally:
        _cache = outer


def read_source(path: Path) -> str:
    """The text of ``path``, read as UTF-8 with universal newlines."""
    if _cache is None:
        return path.read_text(encoding="utf-8")
    texts = _cache["text"]
    key = str(path)
    if key not in texts:
        texts[key] = path.read_text(encoding="utf-8")
    return texts[key]


def parse_source(source: str) -> ast.Module:
    """The parsed ``source``; a text that does not parse raises each time it is asked for."""
    if _cache is None:
        return ast.parse(source)
    trees = _cache["tree"]
    if source not in trees:
        trees[source] = ast.parse(source)
    return trees[source]


def function_tree(fn: Any) -> Tuple[ast.Module, int]:
    """The parsed, dedented source of ``fn`` with its first line number in its file. Raises
    OSError when the source cannot be read and SyntaxError when it does not parse."""
    functions = _cache["function"] if _cache is not None else None
    try:
        known = functions is not None and fn in functions
    except TypeError:  # an unhashable callable is read afresh
        functions, known = None, False
    if known:
        lines, first = functions[fn]
    else:
        lines, first = inspect.getsourcelines(fn)
        if functions is not None:
            functions[fn] = lines, first
    return parse_source(textwrap.dedent("".join(lines))), first


def walk_tree(tree: ast.AST) -> List[ast.AST]:
    """Every node of ``tree`` in ``ast.walk`` order."""
    if _cache is None:
        return list(ast.walk(tree))
    walks = _cache["walk"]
    entry = walks.get(id(tree))
    if entry is None or entry[0] is not tree:
        entry = walks[id(tree)] = (tree, list(ast.walk(tree)))
    return entry[1]
