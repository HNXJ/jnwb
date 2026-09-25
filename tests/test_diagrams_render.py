"""The documented diagrams reach the built site as diagrams, not as code listings.

Every assertion here reads built HTML. None reads ``mkdocs.yml``: a test that checks the
configuration passes the moment someone writes the key, whether or not the build renders
anything. That is the proxy class this repository keeps rediscovering (P-37).

Asserting that the substring ``mermaid`` occurs in the page would be the same mistake one
level down, because ``<code class="language-mermaid">graph TD</code>`` contains it and
still shows the reader a code listing. So the check is positional rather than textual:
every occurrence of a diagram's source must fall *inside* a ``pre.mermaid`` element -- the
selector mkdocs-material's bundle queries -- and a container must exist for each fence.

Stating it that way rather than as "the source must not be inside a highlight wrapper" is
deliberate, and mutation is what forced it. The wrapper-based form matched
``<div class="highlight">`` literally; turning on ``pygments_lang_class`` makes MkDocs emit
``<div class="language-text highlight">``, the pattern then matched nothing, and the test
passed while the page showed a code block. A check that can be switched off by a class
attribute is not a check. Containment in the element that must exist has no such hole.

The build goes to a temporary directory outside the repository. ``scripts/docs_build.py``
writes ``site/`` inside the tree (P-01), and a test that left build output behind would
dirty the working tree for every later reader.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("mkdocs", reason="docs extra not installed")
pytest.importorskip("material", reason="mkdocs-material not installed")

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"

FENCE_OPEN = re.compile(r"^```mermaid\s*$", re.MULTILINE)
FENCE_BODY = re.compile(r"^```mermaid\s*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)

# ``fence_code_format`` puts the configured class first, giving <pre class="mermaid"><code>.
# Matched by pattern, not literal, so an added attribute does not read as a missing diagram.
MERMAID_BLOCK = re.compile(
    r"<pre[^>]*\bclass=\"[^\"]*\bmermaid\b[^\"]*\"[^>]*>\s*<code[^>]*>(.*?)</code>\s*</pre>",
    re.DOTALL,
)


def _pages_with_mermaid() -> list[tuple[str, int]]:
    """(docs-relative page, fence count) for every page carrying a mermaid fence.

    Surveyed from disk rather than listed here: a hardcoded page list stops describing the
    tree the moment a diagram moves, and nothing errors when it does.
    """
    found = []
    for md in sorted(DOCS.rglob("*.md")):
        count = len(FENCE_OPEN.findall(md.read_text(encoding="utf-8")))
        if count:
            found.append((md.relative_to(DOCS).as_posix(), count))
    return found


def _directives(rel_md: str) -> list[str]:
    """The first meaningful line of each fence body, e.g. ``graph TD``."""
    text = (DOCS / rel_md).read_text(encoding="utf-8")
    directives = []
    for body in FENCE_BODY.findall(text):
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        if lines:
            directives.append(lines[0])
    return directives


def _built_page(site: Path, rel_md: str) -> Path:
    """Where MkDocs puts a page under the default ``use_directory_urls``."""
    if rel_md == "index.md":
        return site / "index.html"
    return site / rel_md[: -len(".md")] / "index.html"


def _outside_containers(html: str, directive: str) -> int:
    """How many times ``directive`` occurs outside every ``pre.mermaid`` element."""
    spans = [match.span() for match in MERMAID_BLOCK.finditer(html)]
    return sum(
        1
        for occurrence in re.finditer(re.escape(directive), html)
        if not any(start <= occurrence.start() < end for start, end in spans)
    )


@pytest.fixture(scope="module")
def built_site(tmp_path_factory) -> Path:
    """One strict build for the module; it takes ~2 s, so per-page builds are not worth it."""
    site = tmp_path_factory.mktemp("diagram-site") / "site"
    proc = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--strict", "--site-dir", str(site)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"strict docs build failed ({proc.returncode})\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )
    return site


def test_the_fence_survey_finds_pages():
    """Guard the parametrisation below against collecting nothing.

    If ``_pages_with_mermaid`` ever returns empty -- changed fence syntax, a moved docs
    directory -- pytest would generate zero cases and this file would report success while
    asserting nothing about the site.
    """
    pages = _pages_with_mermaid()
    assert pages, "no page under docs/ carries a mermaid fence; the survey below is vacuous"
    total = sum(count for _, count in pages)
    assert total >= 5, (
        f"{total} mermaid fence(s) found; five pages carried one when this check was "
        "written, so a smaller number means a diagram was dropped rather than rendered"
    )


@pytest.mark.parametrize(
    ("rel_md", "fence_count"),
    [pytest.param(rel, n, id=rel) for rel, n in _pages_with_mermaid()],
)
def test_each_fence_becomes_a_diagram_container(rel_md: str, fence_count: int, built_site: Path):
    page = _built_page(built_site, rel_md)
    assert page.is_file(), f"{rel_md} produced no built page at {page}"
    html = page.read_text(encoding="utf-8")

    bodies = MERMAID_BLOCK.findall(html)
    assert len(bodies) == fence_count, (
        f"{rel_md}: {fence_count} mermaid fence(s) in source but {len(bodies)} "
        'rendered <pre class="mermaid"> container(s) in the built page'
    )

    # An empty container would satisfy the count and still draw nothing.
    for directive in _directives(rel_md):
        assert any(directive in body for body in bodies), (
            f"{rel_md}: no mermaid container carries the diagram source {directive!r}"
        )


@pytest.mark.parametrize(
    ("rel_md", "fence_count"),
    [pytest.param(rel, n, id=rel) for rel, n in _pages_with_mermaid()],
)
def test_no_diagram_source_escapes_its_container(rel_md: str, fence_count: int, built_site: Path):
    """The failure a reader sees: the diagram's source as text instead of a picture.

    Any occurrence outside a container is one the browser will show verbatim, whatever
    markup happens to wrap it.
    """
    html = _built_page(built_site, rel_md).read_text(encoding="utf-8")

    directives = _directives(rel_md)
    assert len(directives) == fence_count, (
        f"{rel_md}: parsed {len(directives)} fence bodies but counted {fence_count} fences"
    )
    for directive in directives:
        loose = _outside_containers(html, directive)
        assert loose == 0, (
            f"{rel_md}: diagram source {directive!r} appears {loose} time(s) outside any "
            'mermaid container, so the page shows it as text where a diagram belongs'
        )


def test_no_built_page_anywhere_shows_diagram_source_as_text(built_site: Path):
    """The same rule over the whole site, not only the pages the survey found.

    ``pymdownx.snippets`` is configured with ``base_path: ["."]``, so a fence can reach a
    page from a file the ``docs/*.md`` survey never opens. This sweep would catch that.

    The ``language-mermaid`` clause is insurance against a neighbouring toolchain change
    rather than a state seen here: because no Pygments lexer is named ``mermaid``, a
    highlighted fence currently comes out labelled ``language-text``.
    """
    directives = {d for rel, _ in _pages_with_mermaid() for d in _directives(rel)}
    assert directives, "no fence directives parsed; this sweep would check nothing"

    offenders: list[str] = []
    for path in sorted(built_site.rglob("*.html")):
        html = path.read_text(encoding="utf-8", errors="ignore")
        name = path.relative_to(built_site).as_posix()
        if "language-mermaid" in html:
            offenders.append(f"{name}: highlighted fence labelled language-mermaid")
        for directive in directives:
            loose = _outside_containers(html, directive)
            if loose:
                offenders.append(f"{name}: {directive!r} outside a container x{loose}")
    assert not offenders, "diagram source rendered as text:\n  " + "\n  ".join(offenders)
