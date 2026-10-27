"""Internal markdown link integrity for the MkDocs corpus."""
from __future__ import annotations

import re
from pathlib import Path

from markdown import Markdown

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"
GITHUB_DIR = Path(__file__).resolve().parents[1] / ".github"


LINK = re.compile(r"\]\(([^)#]+)(?:#[^)]*)?\)")
ANCHOR_LINK = re.compile(r"\]\(([^)\s#]*)#([^)\s]+)\)")

# The mkdocs.yml extensions that decide what a heading is and what its text is. The snippet
# includes in docs/tutorials/ sit inside fenced blocks, so `snippets` adds no heading.
HEADING_EXTENSIONS = [
    "admonition",
    "toc",
    "pymdownx.details",
    "pymdownx.tabbed",
    "pymdownx.superfences",
    "pymdownx.arithmatex",
]
HEADING_CONFIGS = {
    "toc": {"permalink": True},
    "pymdownx.tabbed": {"alternate_style": True},
    "pymdownx.superfences": {"custom_fences": [{"name": "mermaid", "class": "mermaid"}]},
    "pymdownx.arithmatex": {
        "generic": True,
        "smart_dollar": False,
        "tex_inline_wrap": ["\\(", "\\)"],
        "tex_block_wrap": ["\\[", "\\]"],
    },
}


def broken_links(docs_dir: Path, pages: "list[Path] | None" = None) -> "list[str]":
    """Every internal markdown link under `docs_dir` that does not resolve.

    A function rather than an inline loop so that the recursion can be driven over a
    constructed tree. The recursion is the whole point of this check and nothing could
    observe it: reverting rglob to glob left the suite green, because the only thing
    exercising the scan was the scan itself over a corpus that happens to be intact.
    """
    offenders = []
    # rglob: docs/tutorials/ holds nine live pages, and a non-recursive glob checked none of
    # their links. Gate 5 and Gate 10 in scripts/harness_gate.py had the same blind spot.
    for path in pages if pages is not None else sorted(docs_dir.rglob("*.md")):
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


def test_the_github_pages_links_resolve():
    """`.github/*.md` resolves its links from `.github/`, not from the repository root, so a
    link written from the root lands on a path that is not there."""
    pages = sorted(GITHUB_DIR.glob("*.md"))
    assert pages, "fixture must find .github pages"
    offenders = broken_links(GITHUB_DIR, pages)
    assert offenders == [], "broken links in .github pages: " + "; ".join(offenders)


def test_the_agent_entry_page_links_resolve(tmp_path):
    """`artifacts/agents.md` is where the README sends an agent; every link on it must land."""
    artifacts = DOCS_DIR.parent / "artifacts"
    offenders = broken_links(artifacts, [artifacts / "agents.md"])
    assert offenders == [], "broken links on the agent entry page: " + "; ".join(offenders)

    page = tmp_path / "agents.md"
    page.write_text("[ok](agents.md) [gone](../skills/jnwb-absent/SKILL.md)", encoding="utf-8")
    assert broken_links(tmp_path, [page]) == ["agents.md -> ../skills/jnwb-absent/SKILL.md"]


def heading_ids(page_text: str) -> set[str]:
    """The id MkDocs gives each heading of a page, read from Python-Markdown's toc tokens."""
    md = Markdown(extensions=HEADING_EXTENSIONS, extension_configs=HEADING_CONFIGS)
    md.convert(page_text)
    ids, pending = set(), list(md.toc_tokens)
    while pending:
        token = pending.pop()
        ids.add(token["id"])
        pending.extend(token["children"])
    return ids


def anchor_links(docs_dir: Path, pages: "list[Path] | None" = None):
    """Yield (page, line, target, anchor) for every `](page.md#anchor)` and `](#anchor)` link."""
    for path in pages if pages is not None else sorted(docs_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for match in ANCHOR_LINK.finditer(text):
            target, anchor = match.groups()
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            yield path, text.count("\n", 0, match.start()) + 1, target, anchor


def dead_anchors(docs_dir: Path, pages: "list[Path] | None" = None) -> "list[str]":
    """Every anchor link whose page defines no heading with that id.

    The target check in `broken_links` ignores the fragment, so a link to a heading that was
    renamed still lands on its page. A missing page is `broken_links`' finding, not this one.
    """
    ids_by_page: dict[Path, set[str]] = {}
    offenders = []
    for path, line, target, anchor in anchor_links(docs_dir, pages):
        page = (path.parent / target).resolve() if target else path.resolve()
        if page.suffix != ".md" or not page.exists():
            continue
        if page not in ids_by_page:
            ids_by_page[page] = heading_ids(page.read_text(encoding="utf-8"))
        if anchor not in ids_by_page[page]:
            offenders.append(f"{path.relative_to(docs_dir).as_posix()}:{line} -> {target}#{anchor}")
    return offenders


def test_every_anchor_link_names_an_id_its_page_defines():
    assert list(anchor_links(DOCS_DIR)), "fixture must find anchor links"
    offenders = dead_anchors(DOCS_DIR)
    assert offenders == [], "dead anchors in doc links: " + "; ".join(offenders)


def test_the_anchor_check_reports_only_the_dead_anchor(tmp_path):
    assert heading_ids("## Gamma\n\n## Gamma\n") == {"gamma", "gamma_1"}
    (tmp_path / "target.md").write_text("# Imaginary Coherency & `wpli`\n\n## Gamma\n", encoding="utf-8")
    page = tmp_path / "source.md"
    page.write_text(
        "## Gamma\n\n"
        "[ok](target.md#imaginary-coherency-wpli) [here](#gamma) [gone](target.md#imaginary-coherency--wpli)",
        encoding="utf-8",
    )
    assert dead_anchors(tmp_path, [page]) == ["source.md:3 -> target.md#imaginary-coherency--wpli"]
