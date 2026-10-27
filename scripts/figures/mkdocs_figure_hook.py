"""MkDocs hook: a documentation figure gets its state line and a Still and an Interactive tab.

The page sources keep each figure embed as written, a light and a dark image line. At build time
this hook wraps each pair in two tabs, puts the state line from the figure registry above them,
and points the Interactive tab at the figure's HTML on the figures site. A figure with a panel the
converter cannot draw shows its still in the Interactive tab. An embed with no registry entry, or
with no dark twin on the next line, fails the build.

`iframe_violations` is the allowlist gate: an iframe may point only at the figures site.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import figure_registry  # noqa: E402

ALLOWLIST = "https://hnxj.github.io/jnwb/figures/"
LIGHT = re.compile(r"^(?P<indent>[ \t]*)!\[[^\]]*\]\((?:\.\./)*assets/figures/"
                   r"(?P<stem>[^)\s]+?)\.png#only-light\)[ \t]*$")
DARK = re.compile(r"^[ \t]*!\[[^\]]*\]\((?:\.\./)*assets/figures/"
                  r"(?P<stem>[^)\s]+?)\.dark\.png#only-dark\)[ \t]*$")
IFRAME = re.compile(r"<iframe\b[^>]*?\bsrc=\"([^\"]*)\"", re.IGNORECASE)


class FigureError(ValueError):
    """A figure embed the hook cannot tab: no registry entry, or no dark twin."""


def transform(markdown: str, entries: Dict[str, Dict[str, Any]]) -> str:
    lines = markdown.split("\n")
    out: List[str] = []
    index = 0
    while index < len(lines):
        light = LIGHT.match(lines[index])
        if light is None:
            out.append(lines[index])
            index += 1
            continue
        stem = light.group("stem")
        dark = DARK.match(lines[index + 1]) if index + 1 < len(lines) else None
        if dark is None or dark.group("stem") != stem:
            raise FigureError(f"{stem}.png has no dark twin on the next line")
        if f"{stem}.png" not in entries:
            raise FigureError(f"{stem}.png has no entry in the figure registry")
        entry = entries[f"{stem}.png"]
        indent = light.group("indent")
        still = [f"{indent}    {lines[index].strip()}", f"{indent}    {lines[index + 1].strip()}"]
        if out and out[-1].strip():
            out.append("")
        out.append(f"{indent}{figure_registry.state_line(entry)}")
        out.append("")
        out.append(f'{indent}=== "Still"')
        out.append("")
        out.extend(still)
        out.append("")
        out.append(f'{indent}=== "Interactive"')
        out.append("")
        if entry["unconvertible"]:
            out.extend(still)
        else:
            out.append(f'{indent}    <iframe src="{ALLOWLIST}{stem}.html" title="{stem}, interactive" '
                       f'width="100%" height="{entry["height_px"]}" loading="lazy" '
                       f'style="border: 0"></iframe>')
        out.append("")
        index += 2
    return "\n".join(out)


def iframe_violations(markdown: str) -> List[str]:
    return [f"iframe src {src!r} is outside {ALLOWLIST}"
            for src in IFRAME.findall(markdown) if not src.startswith(ALLOWLIST)]


_ENTRIES: Optional[Dict[str, Dict[str, Any]]] = None


def on_page_markdown(markdown, page=None, config=None, files=None, **kwargs):
    global _ENTRIES
    if _ENTRIES is None:
        _ENTRIES = figure_registry.loads(figure_registry.REGISTRY.read_text(encoding="utf-8"))
    return transform(markdown, _ENTRIES)
