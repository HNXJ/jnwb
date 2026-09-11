"""Generate docs/api.md from the runtime public surface (jnwb.__all__)."""
from __future__ import annotations

import inspect
import types
import typing
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple, get_args, get_origin

REPO_ROOT = Path(__file__).resolve().parents[1]


def _first_doc_line(obj: Any) -> str:
    doc = inspect.getdoc(obj) or ""
    if not doc:
        return ""
    return doc.strip().split("\n\n")[0].replace("\n", " ").strip()


def _format_default(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, bool):
        return "True" if value else "False"
    return repr(value)


def _format_annotation(annotation: Any) -> str:
    """Render annotations in a Python-version-stable canonical form."""
    if annotation is inspect.Parameter.empty:
        return ""
    if isinstance(annotation, str):
        return repr(annotation)
    if annotation is type(None):
        return "None"
    if isinstance(annotation, types.UnionType):
        return " | ".join(_format_annotation(arg) for arg in get_args(annotation))

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is typing.Union:
        non_none = [arg for arg in args if arg is not type(None)]
        has_none = type(None) in args
        rendered = " | ".join(_format_annotation(arg) for arg in non_none)
        if has_none:
            rendered = f"{rendered} | None" if rendered else "None"
        return rendered

    if origin is typing.Literal:
        return f"Literal[{', '.join(repr(arg) for arg in args)}]"

    if origin in (list, typing.List):
        inner = _format_annotation(args[0]) if args else "Any"
        return f"List[{inner}]"

    if origin in (tuple, typing.Tuple):
        if not args:
            return "Tuple"
        if len(args) == 2 and args[1] is Ellipsis:
            return f"Tuple[{_format_annotation(args[0])}, ...]"
        return "Tuple[" + ", ".join(_format_annotation(arg) for arg in args) + "]"

    if origin in (dict, typing.Dict):
        if len(args) == 2:
            return f"Dict[{_format_annotation(args[0])}, {_format_annotation(args[1])}]"
        return "Dict"

    if isinstance(annotation, type):
        module = annotation.__module__
        qualname = annotation.__qualname__
        if module in ("builtins",):
            return qualname
        return f"{module}.{qualname}"

    module = getattr(annotation, "__module__", "")
    qualname = getattr(annotation, "__qualname__", None) or getattr(annotation, "_name", "")
    if module and qualname:
        if module == "builtins":
            return qualname
        return f"{module}.{qualname}"

    text = str(annotation).replace("typing.", "")
    if text.startswith("<class '") and text.endswith("'>"):
        return text[len("<class '") : -len("'>")]
    return text


def _format_parameter(param: inspect.Parameter) -> str:
    if param.annotation is inspect.Parameter.empty:
        rendered = param.name
    else:
        rendered = f"{param.name}: {_format_annotation(param.annotation)}"
    if param.default is not inspect.Parameter.empty:
        rendered = f"{rendered} = {_format_default(param.default)}"
    return rendered


def _format_signature(obj: Any) -> str:
    if inspect.isclass(obj):
        line = _first_doc_line(obj)
        return f"*{line}*" if line else "*"
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        line = _first_doc_line(obj)
        return f"*{line}*" if line else "*"
    params = [_format_parameter(param) for param in sig.parameters.values()]
    suffix = ""
    if sig.return_annotation is not inspect.Signature.empty:
        suffix = f" -> {_format_annotation(sig.return_annotation)}"
    return f"({', '.join(params)}){suffix}"


def _object_type_name(obj: Any) -> str:
    if inspect.isclass(obj):
        return "class"
    if inspect.ismodule(obj):
        return "module"
    if isinstance(obj, (dict, tuple, frozenset, list)):
        return "constant"
    return "function"


def _module_for_symbol(jnwb: Any, name: str) -> str:
    obj = getattr(jnwb, name)
    mod = getattr(obj, "__module__", "jnwb") or "jnwb"
    if mod == "jnwb":
        return "jnwb"
    if mod.startswith("jnwb."):
        return mod.split(".", 1)[0] + "." + mod.split(".", 1)[1].split(".")[0]
    return "jnwb"


def generate_api_markdown(repo_root: Path | None = None) -> str:
    root = repo_root or REPO_ROOT
    import sys

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import jnwb

    grouped: Dict[str, List[str]] = defaultdict(list)
    for name in jnwb.__all__:
        grouped[_module_for_symbol(jnwb, name)].append(name)

    lines = [
        "# Complete API Reference",
        "",
        f"All {len(jnwb.__all__)} core functions, classes, and constants exported in the "
        "top-level jnwb namespace.",
        "",
        "> Generated from `jnwb.__all__`, `inspect.signature`, and runtime docstrings. "
        "Do not edit by hand — run `python scripts/generate_api_md.py --write`.",
        "",
    ]

    for module_name in sorted(grouped):
        lines.append(f"## Module: {module_name}")
        lines.append("")
        lines.append("| Symbol | Type | Signature / Description |")
        lines.append("|---|---|---|")
        for symbol in sorted(grouped[module_name]):
            obj = getattr(jnwb, symbol)
            typ = _object_type_name(obj)
            sig = _format_signature(obj)
            desc = _first_doc_line(obj)
            cell = sig
            if desc and not sig.startswith("*"):
                cell = f"{sig}<br>*{desc}*"
            lines.append(f"| jnwb.{symbol} | {typ} | {cell} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def check_api_md_is_generated(repo_root: Path | None = None) -> List[str]:
    """Return violations when committed docs/api.md differs from generator output."""
    root = repo_root or REPO_ROOT
    api_path = root / "docs" / "api.md"
    if not api_path.exists():
        return ["MISSING_API_DOC: docs/api.md not found"]

    generated = generate_api_markdown(root)
    committed = api_path.read_text(encoding="utf-8")
    if generated != committed:
        return [
            "API_MD_DRIFT: docs/api.md does not match scripts/generate_api_md.py output; "
            "run python scripts/generate_api_md.py --write"
        ]
    return []


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate or check docs/api.md")
    parser.add_argument("--write", action="store_true", help="Write docs/api.md")
    parser.add_argument("--check", action="store_true", help="Exit 1 if drift detected")
    args = parser.parse_args()

    text = generate_api_markdown()
    if args.write:
        out = REPO_ROOT / "docs" / "api.md"
        out.write_text(text, encoding="utf-8")
        print(f"Wrote {out}")
    elif args.check:
        violations = check_api_md_is_generated()
        if violations:
            for v in violations:
                print(v)
            raise SystemExit(1)
        print("PASS: docs/api.md matches generator")
    else:
        print(text)


if __name__ == "__main__":
    main()
