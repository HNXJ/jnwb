"""The documentation form gate fails on each seeded violation and passes on the live tree.

Each check runs on a fixture tree written to ``tmp_path``, never by editing ``docs/``. The clean
fixture carries a control for every seed -- a table and a list of the facts the prose detector
hunts, a deep heading inside a fence, a theme-neutral image, an inline SVG drawn in
``currentColor`` -- so a check that failed everything fails the clean-tree test, and a seed is
required to fail its own check and no other.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Callable, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts import docs_form_gate as gate  # noqa: E402
from tests import test_documentation_form as form  # noqa: E402

CONTRACT = """# Documentation form

## Vocabulary

| Concept | Use | Not |
|---|---|---|
| A rendered color | `color`, `colors` | `colour`, `colours` |
| Scaling to a common range | `normalize`, `normalized` | `normalise`, `normalised` |

## Length

Prose after the table.
"""

PAGE = """# Page A

The trace color is normalized before plotting.

| Function | Returns |
|---|---|
| `alpha` | Scalar. `alpha` returns a float. |
| `beta` | Vector. `beta` returns an array. |
| `gamma` | Frame. `gamma` returns a table. |

- Scalar. `alpha` returns a float.
- Vector. `beta` returns an array.
- Frame. `gamma` returns a table.

!!! note
    Scalar. `alpha` returns a float. Vector. `beta` returns an array. Frame. `gamma` returns a
    table.

`alpha` returns a float, and `beta` returns an array; a third is not named here.

```python
#### a comment, not a heading

`alpha` is one, `beta` is two, `gamma` is three.
```

![A figure](assets/figures/fig.png#only-light)
![A figure](assets/figures/fig.dark.png#only-dark)

<img src="assets/jnwb-logo.png" alt="jnwb" width="180">

<svg viewBox="0 0 10 10"><rect fill="currentColor" stroke="none"/></svg>

```mermaid
graph TD
  A --> B
```
"""

GENERATOR = """THEMES = {"light": {"fg": "#000000"}, "dark": {"fg": "#ffffff"}}


def fig(ax, x):
    ax.plot(x, color="#888888")
"""

MKDOCS = """site_name: fixture
nav:
  - Start:
      - A: a.md
      - B: b.md
  - More:
      - C: c.md
      - D: d.md
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    _write(tmp_path / "docs" / "documentation_form.md", CONTRACT)
    _write(tmp_path / "docs" / "a.md", PAGE)
    for name in ("b", "c", "d"):
        _write(tmp_path / "docs" / f"{name}.md", f"# Page {name.upper()}\n\nA short page.\n")
    _write(tmp_path / "README.md", "# Fixture\n\nA readme.\n")
    for asset in ("figures/fig.png", "figures/fig.dark.png", "jnwb-logo.png"):
        (tmp_path / "docs" / "assets" / asset).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs" / "assets" / asset).write_bytes(b"\x89PNG")
    _write(tmp_path / "docs" / "generate_figures.py", GENERATOR)
    _write(tmp_path / "examples" / "quickstart_jnwb.py", GENERATOR)
    _write(tmp_path / "mkdocs.yml", MKDOCS)
    return tmp_path


def _results(root: Path) -> Dict[str, list]:
    return {name: violations for name, violations, _ in gate.run_checks(root)}


def _append(rel: str, text: str) -> Callable[[Path], None]:
    def seed(root: Path) -> None:
        path = root / rel
        _write(path, path.read_text(encoding="utf-8") + text)
    return seed


def _replace(rel: str, old: str, new: str) -> Callable[[Path], None]:
    def seed(root: Path) -> None:
        path = root / rel
        text = path.read_text(encoding="utf-8")
        assert text.count(old) == 1, f"seed anchor {old!r} not unique in {rel}"
        _write(path, text.replace(old, new))
    return seed


def _then(*seeds: Callable[[Path], None]) -> Callable[[Path], None]:
    def seed(root: Path) -> None:
        for s in seeds:
            s(root)
    return seed


def _unlink(rel: str) -> Callable[[Path], None]:
    return lambda root: (root / rel).unlink()


NAV = "mkdocs.yml"
PAGE_A = "docs/a.md"

SEEDS = {
    "superseded form": ("vocabulary", _append(PAGE_A, "\nThe trace colour is fixed.\n"),
                        "'colour'"),
    "fourth-level heading": ("heading depth", _append(PAGE_A, "\n#### Too deep\n"), "Too deep"),
    "fifth-level heading": ("heading depth", _append(PAGE_A, "\n##### Deeper\n"), "Deeper"),
    "nested group": ("navigation", _replace(NAV, "      - D: d.md\n",
                                            "      - D: d.md\n      - Sub:\n          - E: b.md\n"),
                     "N1"),
    "single-page group": ("navigation", _replace(NAV, "      - D: d.md\n", ""), "N2"),
    "page outside a group": ("navigation", _append(NAV, "  - Loose: b.md\n"), "N3"),
    "dead target": ("navigation", _replace(NAV, "D: d.md", "D: missing.md"), "N5"),
    "light variant only": ("figure theme independence",
                           _then(_append(PAGE_A, "\n![New](assets/figures/new.png#only-light)\n"),
                                 lambda root: _write(root / "docs/assets/figures/new.png", "")),
                           "shown only under"),
    "dark file missing": ("figure theme independence", _unlink("docs/assets/figures/fig.dark.png"),
                          "fig.dark.png is missing"),
    "variant under the wrong scheme": (
        "figure theme independence",
        _replace(PAGE_A, "fig.dark.png#only-dark", "fig.dark.png#only-light"),
        "under #only-light"),
    "image shown under both schemes": ("figure theme independence",
                                       _append(PAGE_A, "\n![Bare](assets/figures/fig.png)\n"),
                                       "same under both schemes"),
    "themed image the pairing cannot read": (
        "figure theme independence",
        _append(PAGE_A, "\nSee ![inline](assets/figures/fig.png#only-light) here.\n"),
        "cannot be confirmed"),
    "inline svg with a fixed color": (
        "figure theme independence",
        _append(PAGE_A, '\n<svg viewBox="0 0 1 1"><rect fill="#000000"/></svg>\n'),
        "#000000"),
    "fixed color outside the theme table": (
        "figure theme independence",
        _append("docs/generate_figures.py", '\n\ndef bad(ax, x):\n    ax.plot(x, color="#000000")\n'),
        "docs/generate_figures.py"),
    "three parallel facts in a paragraph": (
        "parallel facts",
        _append(PAGE_A, "\n`alpha` returns a float, `beta` returns an array, and `gamma` "
                        "returns a table.\n"),
        "a.md:"),
}


def test_the_clean_fixture_passes_every_check(tree):
    """The control for every seed below. A check that fails everything fails here."""
    assert _results(tree) == {name: [] for name, _ in gate.CHECKS}


@pytest.mark.parametrize("seed_name", sorted(SEEDS))
def test_each_check_fails_on_its_own_seeded_violation(tree, seed_name):
    check, seed, expected = SEEDS[seed_name]
    seed(tree)
    results = _results(tree)
    assert any(expected in v for v in results[check]), (seed_name, results[check])
    others = {name: v for name, v in results.items() if name != check and v}
    assert not others, f"{seed_name} also failed {others}"


def test_a_check_that_raises_is_reported_and_the_others_still_run(tree):
    (tree / NAV).unlink()
    results = _results(tree)
    assert results["navigation"][0].startswith("ERROR: FileNotFoundError"), results["navigation"]
    assert all(v == [] for name, v in results.items() if name != "navigation"), results


def test_the_command_line_exit_code_follows_the_checks(tree, capsys):
    assert gate.main(tree) == 0
    assert "ALL DOCUMENTATION FORM CHECKS PASSED. 5 of 5" in capsys.readouterr().out
    SEEDS["three parallel facts in a paragraph"][1](tree)
    assert gate.main(tree) == 1
    out = capsys.readouterr().out
    assert "FAIL: parallel facts:" in out and "OVERALL: FAIL" in out


# ----------------------------------------------------------------------------- live tree


def test_the_live_tree():
    results = gate.run_checks(REPO_ROOT)
    assert {name: v for name, v, _ in results} == {name: [] for name, _ in gate.CHECKS}

    # Reach: each pass line reports what it read, and a collapsed reader reads almost nothing.
    text = " ".join(line for _, _, line in results)

    def count(pattern: str) -> int:
        match = re.search(pattern, text)
        assert match, f"{pattern!r} not in {text}"
        return int(match.group(1))

    assert count(r"of (\d+) concepts") >= 6
    assert count(r"concepts in (\d+) pages") >= 18
    assert count(r"(\d+) targets") >= 25
    assert count(r"(\d+) figures shown as light/dark pairs") >= 10
    assert count(r"(\d+) paragraphs") >= 200


def test_the_gate_reads_the_corpus_and_vocabulary_the_suite_reads():
    """The gate re-reads files to take a root; on the live tree it must read what the suite reads."""
    assert gate.corpus(REPO_ROOT) == form._corpus()
    parsed = gate.parse_vocabulary((REPO_ROOT / gate.CONTRACT).read_text(encoding="utf-8"))
    as_tuples = [(r.concept, r.preferred, r.superseded) for r in parsed]
    assert as_tuples == [(r.concept, r.preferred, r.superseded) for r in form.VOCABULARY]


def test_the_prose_detector_sees_clauses_in_live_prose():
    """Bypass: the clause pattern matches nothing, so no paragraph can reach the threshold.
    Live prose holds paragraphs with two parallel facts, one short of it."""
    near = [(name, number) for name, text in gate.f2_pages(REPO_ROOT)
            for number, paragraph in gate.paragraphs(text)
            if len(gate.parallel_fact_subjects(paragraph)) == gate.PARALLEL_FACTS - 1]
    assert len(near) >= 3, near
