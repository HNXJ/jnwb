"""Internal markdown link integrity for the MkDocs corpus."""
from __future__ import annotations

import re
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"


LINK = re.compile(r"\]\(([^)#]+)(?:#[^)]*)?\)")


def broken_links(docs_dir: Path) -> "list[str]":
    """Every internal markdown link under `docs_dir` that does not resolve.

    A function rather than an inline loop so that the recursion can be driven over a
    constructed tree. The recursion is the whole point of this check and nothing could
    observe it: reverting rglob to glob left the suite green, because the only thing
    exercising the scan was the scan itself over a corpus that happens to be intact.
    """
    offenders = []
    # rglob: docs/tutorials/ holds nine live pages, and a non-recursive glob checked none of
    # their links. Gate 5 and Gate 10 in scripts/harness_gate.py had the same blind spot.
    for path in sorted(docs_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                offenders.append(f"{path.relative_to(docs_dir).as_posix()} -> {target}")
    return offenders


def test_mkdocs_markdown_internal_links_resolve():
    offenders = broken_links(DOCS_DIR)
    assert offenders == [], "broken internal doc links: " + "; ".join(offenders)
