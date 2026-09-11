"""Generate docs/api.md from the runtime public surface (jnwb.__all__)."""
from __future__ import annotations

import inspect
import re
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]


def _first_doc_line(obj: Any) -> str:
    doc = inspect.getdoc(obj) or ""
    if not doc:
        return ""
    return doc.strip().split("\n\n")[0].replace("\n", " ").strip()


def _format_signature(obj: Any) -> str:
    if inspect.isclass(obj):
        line = _first_doc_line(obj)
        return f"*{line}*" if line else "*"
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        line = _first_doc_line(obj)
        return f"*{line}*" if line else "*"
    return str(sig)


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
