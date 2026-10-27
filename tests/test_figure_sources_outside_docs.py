"""The figure generators and their style module are scripts, so they live outside `docs/`.

MkDocs copies every file under `docs/` into the built site, so a generator kept there is published
beside the pages it draws. The generators are `scripts/figures/generate_figures.py` and
`scripts/figures/figure_style.py`.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
FIGURE_SCRIPTS = REPO_ROOT / "scripts" / "figures"
MODULES = ("generate_figures.py", "figure_style.py")


def test_docs_holds_no_python_source() -> None:
    """Every file under docs/ is published, so none may be Python source."""
    examined = [p for p in DOCS.rglob("*") if p.is_file()]
    assert len(examined) > 50, f"only {len(examined)} files under docs/; the walk is wrong"
    sources = [p.relative_to(REPO_ROOT).as_posix() for p in examined if p.suffix == ".py"]
    assert sources == [], f"Python source under docs/ is published with the site: {sources}"


def test_the_figure_modules_live_in_scripts_figures() -> None:
    for name in MODULES:
        assert (FIGURE_SCRIPTS / name).is_file(), f"scripts/figures/{name} is missing"
