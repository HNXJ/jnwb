"""Internal markdown link integrity for the MkDocs corpus."""
from __future__ import annotations

import re
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"


def test_mkdocs_markdown_internal_links_resolve():
    pattern = re.compile(r"\]\(([^)#]+)(?:#[^)]*)?\)")
    offenders = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for target in pattern.findall(text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                offenders.append(f"{path.name} -> {target}")
    assert offenders == [], "broken internal doc links: " + "; ".join(offenders)
