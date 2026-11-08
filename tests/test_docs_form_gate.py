"""The documentation form gate fails on each seeded violation and passes on the live tree.

Each check runs on a fixture tree written to ``tmp_path``, never by editing ``docs/``. The clean
fixture carries a control for every seed -- a table and a list of the facts the prose detector
hunts, a deep heading inside a fence, a theme-neutral image, an inline SVG drawn in
``currentColor`` -- so a check that failed everything fails the clean-tree test, and a seed is
required to fail its own check and no other.
"""

from __future__ import annotations

import ast
import re
import shutil
import sys
import types
from pathlib import Path
from typing import Callable, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # needed: the installed-wheel run clears pythonpath

from scripts import docs_build  # noqa: E402
from scripts import docs_form_gate as gate  # noqa: E402
from scripts.gates.docs import check_nwb_onboarding_alignment  # noqa: E402

CONTRACT = """# Documentation form

## Vocabulary

| Concept | Use | Not |
|---|---|---|
| A rendered color | `color`, `colors` | `colour`, `colours` |
| Scaling to a common range | `normalize`, `normalized` | `normalise`, `normalised` |
| An exported function | `operation`, `operations` | `primitive`, `primitives` |

## Slop lexicon

| Kind | Terms |
|---|---|
| Inflated verbs | `delve`, `unlock` |
| Filler phrases | `it is worth noting` |

## Length

| Kind | Ceiling | Why this number |
|---|---|---|
| Concept (`02`–`09`, `architecture`, `reading_nwb`, `repairing_nwb`, `coherence_and_tfr`, `laminar`, `vis`) | 1200 words | fixture |

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

The file is unlocked after `delve` returns, and delve-rs is a crate name.

    #### an indented code block, not a heading

```python
#### a comment, not a heading
# depth 40 um, in a code block

`alpha` is one, `beta` is two, `gamma` is three.
```

The contact depth is stored as `depth_um`, in micrometers, and `pitch_um` is its spacing.

![A figure](assets/figures/fig.png#only-light)
![A figure](assets/figures/fig.dark.png#only-dark)

<img src="assets/jnwb-logo.png" alt="jnwb" width="180">

<svg viewBox="0 0 10 10"><rect fill="currentColor" stroke="none"/></svg>

```mermaid
graph TD
  A --> B
```
"""

#: The fourteen concept pages of the contract's Length table, the Concept row, by file name.
CONCEPT_NAMES = (
    "02_paths_addressing_metadata.md", "03_representational_similarity_jrsa.md",
    "04_spectral_analysis_and_tfr.md", "05_artifact_detection_and_repair.md",
    "06_spikes_psth_and_onset_dynamics.md", "07_statistical_inference_and_nulls.md",
    "08_directed_connectivity_and_information.md", "09_decoding_and_visual_qc.md",
    "architecture.md", "reading_nwb.md", "repairing_nwb.md", "coherence_and_tfr.md",
    "laminar.md", "vis.md",
)

CONCEPT = """# Concept

## 1. Section (`jnwb.connectivity`)

A paragraph.

### Operation (`granger`)

Text.
"""

CITED = """# Cited

The method follows Lee et al. (2021).

## References

- Lee et al. (2021)
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
      - Ext: https://example.org/guide.md
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
    _write(tmp_path / "docs" / "tutorials" / "t1.md", "# Tutorial\n\nA short tutorial.\n")
    _write(tmp_path / "docs" / "cited.md", CITED)
    for name in CONCEPT_NAMES:
        _write(tmp_path / "docs" / name, CONCEPT)
    _write(tmp_path / "README.md", "# Fixture\n\nA readme.\n")
    for asset in ("figures/fig.png", "figures/fig.dark.png", "jnwb-logo.png"):
        (tmp_path / "docs" / "assets" / asset).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs" / "assets" / asset).write_bytes(b"\x89PNG")
    _write(tmp_path / "scripts" / "figures" / "generate_figures.py", GENERATOR)
    _write(tmp_path / "examples" / "quickstart_jnwb.py", GENERATOR)
    _write(tmp_path / "scripts" / "figures" / "figure_style.py", GENERATOR)
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


def _unsuffixed_image(rel: str) -> Callable[[Path], None]:
    """Appends an unsuffixed PNG under `docs/assets/vis/` to the page `rel`."""
    return _then(
        lambda root: _write(root / "docs/assets/vis/sorted.png", ""),
        _append(rel, "\n![Sorted heatmap](assets/vis/sorted.png)\n"))


NAV = "mkdocs.yml"
PAGE_A = "docs/a.md"
TUTORIAL = "docs/tutorials/t1.md"
QUICKSTART = "examples/quickstart_jnwb.py"

SEEDS = {
    "superseded form": ("vocabulary", _append(PAGE_A, "\nThe trace colour is fixed.\n"),
                        "'colour'"),
    "fourth-level heading": ("heading depth", _append(PAGE_A, "\n#### Too deep\n"), "Too deep"),
    "fifth-level heading": ("heading depth", _append(PAGE_A, "\n##### Deeper\n"), "Deeper"),
    "indented fourth-level heading": ("heading depth", _append(PAGE_A, "\n   #### Indented\n"),
                                      "Indented"),
    "heading after a fence indented four spaces": (
        "heading depth", _append(PAGE_A, "\nText.\n\n    ```\n    code\n\n#### After\n"), "After"),
    "deep heading on a tutorial page": ("heading depth", _append(TUTORIAL, "\n#### Too deep\n"),
                                        "tutorials/t1.md:"),
    "superseded form on a tutorial page": (
        "vocabulary", _append(TUTORIAL, "\nThe trace colour is fixed.\n"), "tutorials/t1.md"),
    "three parallel facts on a tutorial page": (
        "parallel facts",
        _append(TUTORIAL, "\n`alpha` returns a float, `beta` returns an array, and `gamma` "
                          "returns a table.\n"),
        "tutorials/t1.md:"),
    "slop term on a tutorial page": ("slop lexicon", _append(TUTORIAL, "\nWe delve in.\n"),
                                     "tutorials/t1.md: 'delve'"),
    "figure file linked without a scheme": (
        "figure theme independence",
        _append(PAGE_A, "\nThe [raw file](assets/figures/fig.png) opens alone.\n"),
        "referenced without"),
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
    "tutorial figure whose dark file is missing": (
        "figure theme independence",
        _then(_append(TUTORIAL, "\n![New](../assets/figures/new.png#only-light)\n"
                                "![New](../assets/figures/new.dark.png#only-dark)\n"),
              lambda root: _write(root / "docs/assets/figures/new.png", "")),
        "../assets/figures/new.dark.png is missing"),
    "inline svg with a fixed color": (
        "figure theme independence",
        _append(PAGE_A, '\n<svg viewBox="0 0 1 1"><rect fill="#000000"/></svg>\n'),
        "#000000"),
    "fixed color outside the theme table": (
        "figure theme independence",
        _append("scripts/figures/generate_figures.py",
                '\n\ndef bad(ax, x):\n    ax.plot(x, color="#000000")\n'),
        "scripts/figures/generate_figures.py"),
    "fixed color outside the theme table of the style module": (
        "figure theme independence",
        _append("scripts/figures/figure_style.py", '\nHIGHLIGHT = "#cfb87c"\n'),
        "scripts/figures/figure_style.py"),
    "three parallel facts in a paragraph": (
        "parallel facts",
        _append(PAGE_A, "\n`alpha` returns a float, `beta` returns an array, and `gamma` "
                        "returns a table.\n"),
        "a.md:"),
    "slop term in page prose": ("slop lexicon",
                                _append(PAGE_A, "\nWe Delve into the traces.\n"), "'delve'"),
    "slop phrase in a skill": (
        "slop lexicon",
        lambda root: _write(root / "skills/demo/SKILL.md",
                            "# Demo\n\nIt is worth noting that the rate is in Hz.\n"),
        "skills/demo/SKILL.md: 'it is worth noting'"),
    "superseded form in the quickstart": (
        "vocabulary", _append(QUICKSTART, "\n# Six primitives from the library.\n"),
        "examples/quickstart_jnwb.py: 'primitives'"),
    "slop term in the quickstart": ("slop lexicon", _append(QUICKSTART, "\n# We delve in.\n"),
                                    "examples/quickstart_jnwb.py: 'delve'"),
    "slop lexicon missing": ("slop lexicon",
                             _replace("docs/documentation_form.md", "## Slop lexicon",
                                      "## Removed"),
                             "no slop lexicon parsed"),
    "concept H2 unnumbered": ("concept headings",
                              _replace("docs/architecture.md", "## 1. Section", "## Section"),
                              "architecture.md:3: H2 'Section"),
    "concept H3 numbered": ("concept headings",
                            _replace("docs/vis.md", "### Operation", "### 1. Operation"),
                            "vis.md:7: H3 '1. Operation (`granger`)' is numbered"),
    "concept H2 names a function": ("module headings",
                                    _replace("docs/laminar.md", "(`jnwb.connectivity`)",
                                             "(`granger`)"),
                                    "laminar.md:3: H2 '1. Section (`granger`)' names "
                                    "the function"),
    "table row repeated across two tables": (
        "repeated table rows",
        _append(PAGE_A, "\n| Refusal | Error |\n|---|---|\n"
                        "| `dst` exists | `FileExistsError` |\n"
                        "\n| Refusal | Error |\n|---|---|\n"
                        "| `dst` exists | `FileExistsError` |\n"),
        "a.md: the row '| `dst` exists | `FileExistsError` |' is in 2 tables"),
    "cited source without a References section": (
        "references", _append(PAGE_A, "\nThe method follows Lee et al. (2021).\n"),
        "a.md: cites 'Lee et al. (2021' and has no ## References section"),
    "References section on a page that cites none": (
        "references", _append(PAGE_A, "\n## References\n\nNone is cited on this page.\n"),
        "has a ## References section and cites no source"),
    "References section that is not the last": (
        "references",
        _append(PAGE_A, "\nThe method follows Lee et al. (2021).\n\n## References\n\n- Lee et al. (2021)\n"
                        "\n## Notes\n\nText.\n"),
        "## References is not the last section"),
    "micrometre unit in prose": ("micrometers", _append(PAGE_A, "\nThe probe is 40 um deep.\n"),
                                 "um is a unit in prose"),
    "micrometre symbol in math in prose": (
        "micrometers", _append(PAGE_A, "\nThe depth is $\\mu\\text{m}$ here.\n"),
        "\\mu\\text{m} is a unit in prose"),
}


def test_the_clean_fixture_passes_every_check(tree):
    """The control for every seed below. A check that fails everything fails here."""
    assert _results(tree) == {name: [] for name, _ in gate.CHECKS}


def test_a_tutorial_page_pairs_figures_through_a_parent_path(tree):
    """A page under docs/tutorials/ reaches the figures as ../assets/; its pair is read there."""
    _append(TUTORIAL, "\n![A figure](../assets/figures/fig.png#only-light)\n"
                      "![A figure](../assets/figures/fig.dark.png#only-dark)\n")(tree)
    assert (tree / "docs/tutorials/../assets/figures/fig.dark.png").is_file(), \
        "fixture must hold the pair the page names"
    assert _results(tree) == {name: [] for name, _ in gate.CHECKS}


@pytest.mark.parametrize("seed_name", sorted(SEEDS))
def test_each_check_fails_on_its_own_seeded_violation(tree, seed_name):
    check, seed, expected = SEEDS[seed_name]
    seed(tree)
    results = _results(tree)
    assert any(expected in v for v in results[check]), (seed_name, results[check])
    others = {name: v for name, v in results.items() if name != check and v}
    assert not others, f"{seed_name} also failed {others}"


VIS = "docs/vis.md"


def test_an_unsuffixed_image_is_light_only_on_a_map_page_that_states_it(tree):
    """G2 takes an unsuffixed image only on a page of `LIGHT_ONLY_PAGES` whose quoted line is on
    the page, and counts it as light-only. Bypass: every unsuffixed image fails, so the map is
    never read, or the map is read without its line."""
    _write(tree / VIS, f"# Plotting\n\n{gate.LIGHT_ONLY_PAGES['vis.md']}\n")
    _unsuffixed_image(VIS)(tree)
    report = {name: (violations, line) for name, violations, line in gate.run_checks(tree)}
    violations, line = report["figure theme independence"]
    assert violations == [], violations
    assert "1 light-only" in line, line


def test_an_unsuffixed_image_fails_on_a_page_outside_the_map(tree):
    _unsuffixed_image(PAGE_A)(tree)
    results = _results(tree)
    assert any("a.md: assets/vis/sorted.png is shown the same" in v
               for v in results["figure theme independence"]), results["figure theme independence"]
    others = {name: v for name, v in results.items() if name != "figure theme independence" and v}
    assert not others, f"the seeded image also failed {others}"


def test_an_unsuffixed_image_fails_on_a_map_page_without_its_line(tree):
    _write(tree / VIS, "# Plotting\n\nNo statement of the theme here.\n")
    _unsuffixed_image(VIS)(tree)
    results = _results(tree)
    assert any("vis.md: assets/vis/sorted.png" in v
               for v in results["figure theme independence"]), results["figure theme independence"]
    others = {name: v for name, v in results.items() if name != "figure theme independence" and v}
    assert not others, f"the seeded image also failed {others}"


def test_a_check_that_raises_is_reported_and_the_others_still_run(tree):
    (tree / NAV).unlink()
    results = _results(tree)
    assert results["navigation"][0].startswith("ERROR: FileNotFoundError"), results["navigation"]
    assert all(v == [] for name, v in results.items() if name != "navigation"), results


def test_the_command_line_exit_code_follows_the_checks(tree, capsys):
    assert gate.main(tree) == 0
    n = len(gate.CHECKS)
    assert f"ALL DOCUMENTATION FORM CHECKS PASSED. {n} of {n} checks executed" in \
        capsys.readouterr().out
    SEEDS["three parallel facts in a paragraph"][1](tree)
    assert gate.main(tree) == 1
    out = capsys.readouterr().out
    assert "FAIL: parallel facts:" in out and "OVERALL: FAIL" in out


def test_the_corpus_reads_the_quickstart_and_every_tutorial_script(tree):
    """Bypass: the corpus reads only the tutorial folder, so a superseded form in the quickstart
    passed the vocabulary and slop checks."""
    _write(tree / "examples/tutorials/07_extra.py", "# A tutorial.\n")
    names = {name for name, _ in gate.corpus(tree)}
    assert {QUICKSTART, "examples/tutorials/07_extra.py"} <= names, sorted(names)


# --------------------------------------------------------------------- tutorial scripts (gate 18)


def _nwb_tree(tmp_path: Path) -> Path:
    """A copy of what the tutorial gate reads: the scripts, their pages, the skills, the readme
    and the nav."""
    root = tmp_path / "tree"
    for rel in ("examples/tutorials", "docs/tutorials", "skills"):
        shutil.copytree(REPO_ROOT / rel, root / rel)
    for rel in ("README.md", "mkdocs.yml"):
        shutil.copy(REPO_ROOT / rel, root / rel)
    return root


def test_the_tutorial_gate_checks_a_script_added_to_the_folder(tmp_path):
    """Bypass: the gate's list is fixed at 00 to 08, so a script added to the folder is not read."""
    root = _nwb_tree(tmp_path)
    _write(root / "examples/tutorials/11_extra.py", "def run():\n    pass\n")
    violations = check_nwb_onboarding_alignment(root)
    assert any("11_extra.py defines no main()" in v for v in violations), violations


def test_the_tutorial_gate_checks_the_open_data_and_wavemap_scripts(tmp_path):
    """Bypass: 09 and 10 are outside the gate's list, so a module-level raise or a missing main()
    in either passes."""
    root = _nwb_tree(tmp_path)
    _write(root / "examples/tutorials/09_open_data.py", "raise SystemExit('nope')\n")
    _replace("examples/tutorials/10_wavemap.py", "def main() -> None:", "def run() -> None:")(root)
    violations = check_nwb_onboarding_alignment(root)
    assert any("09_open_data.py raises at module level" in v for v in violations), violations
    assert any("10_wavemap.py defines no main()" in v for v in violations), violations


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
    assert count(r"concepts in (\d+) pages") >= 28
    assert count(r"(\d+) groups") >= 4
    assert count(r"(\d+) targets") >= 25
    assert count(r"(\d+) figures shown as light/dark pairs") >= 10
    assert count(r"(\d+) light-only") >= 1
    assert count(r"(\d+) paragraphs") >= 300
    assert count(r"paragraphs in (\d+) pages") >= 28
    assert count(r"none of (\d+) terms") >= 40
    assert count(r"terms in (\d+) pages") >= 28


def test_the_concept_pages_are_the_fourteen_of_the_length_table():
    """Bypass: a concept page missing from the gate's list is not numbered-checked; the list is
    read from the live Length table's Concept row and pinned here."""
    names = gate.concept_page_names(REPO_ROOT)
    assert sorted(names) == sorted(CONCEPT_NAMES)
    assert all((REPO_ROOT / "docs" / name).is_file() for name in names)


def test_a_page_added_to_the_concept_row_is_checked(tree: Path):
    """Bypass: a hard-coded page list misses a new concept page. One added to the row is read."""
    contract = tree / "docs" / "documentation_form.md"
    contract.write_text(contract.read_text(encoding="utf-8").replace("`vis`)", "`vis`, `extra`)"),
                        encoding="utf-8")
    _write(tree / "docs" / "extra.md", "# Extra\n\n## Unnumbered\n\nText.\n")
    violations, _ = gate.check_concept_numbering(tree)
    assert any("extra.md" in v and "not numbered" in v for v in violations), violations


def test_a_contract_with_no_concept_row_reads_no_page_and_fails(tree: Path):
    _write(tree / "docs" / "documentation_form.md", CONTRACT.split("| Kind | Ceiling")[0])
    violations, _ = gate.check_concept_numbering(tree)
    assert any("nothing to check" in v for v in violations), violations


def test_the_live_concept_pages_are_read_and_their_h2_counted():
    """The F10 and F11 reads of the live tree, as counts: a silent empty read shows here."""
    pages, missing = gate.concept_pages(REPO_ROOT)
    assert not missing and len(pages) == len(CONCEPT_NAMES)
    h2 = sum(1 for _, text in pages for _, level, _ in gate.headings(text) if level == 2)
    assert h2 > 0, "no H2 read from the concept pages; the reader is wrong"


def test_the_prose_detector_sees_clauses_in_live_prose():
    """Bypass: the clause pattern matches nothing, so no paragraph can reach the threshold.
    Live prose holds paragraphs with two parallel facts, one short of it."""
    near = [(name, number) for name, text in gate.f2_pages(REPO_ROOT)
            for number, paragraph in gate.paragraphs(text)
            if len(gate.parallel_fact_subjects(paragraph)) == gate.PARALLEL_FACTS - 1]
    assert len(near) >= 3, near


def test_the_gate_reads_the_tutorial_pages():
    """Bypass: the tutorial pages leave the corpus, and F1, F2 and F5 pass over their prose."""
    for pages in (gate.corpus(REPO_ROOT), gate.f2_pages(REPO_ROOT)):
        tutorials = [name for name, _ in pages if name.startswith("tutorials/")]
        assert len(tutorials) >= 9, tutorials


def test_the_gate_imports_nothing_from_the_tests():
    """The tests call the gate. A gate that reads helpers out of a test module has two owners
    for one rule, and a change to either moves the other."""
    tree = ast.parse((REPO_ROOT / "scripts" / "docs_form_gate.py").read_text(encoding="utf-8"))
    imported = [node.module or "" if isinstance(node, ast.ImportFrom) else alias.name
                for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in (node.names if isinstance(node, ast.Import) else [None])]
    assert not [name for name in imported if name == "tests" or name.startswith("tests.")], imported


def test_the_docs_build_writes_outside_the_tree(monkeypatch, tmp_path):
    """The site goes to a temporary directory that is gone afterwards, or to the one named."""
    calls = []

    def fake_run(command, cwd):
        site = Path(command[command.index("--site-dir") + 1])
        site.mkdir(parents=True)
        (site / "index.html").write_text("built", encoding="utf-8")
        calls.append((site, Path(cwd), command))
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(docs_build.subprocess, "run", fake_run)
    assert docs_build.main([]) == 0
    site, cwd, command = calls[0]
    assert cwd == REPO_ROOT and command[-3:-2] == ["--strict"]
    assert REPO_ROOT not in site.resolve().parents, f"the site was written inside the tree: {site}"
    assert not site.exists(), "the temporary site was left behind"

    kept = tmp_path / "kept"
    assert docs_build.main(["--keep", str(kept)]) == 0
    assert calls[1][0] == kept.resolve() and (kept / "index.html").is_file()
    assert docs_build.main(["--bogus"]) == 2


# ------------------------------------------------------------ references and micrometers (F13, F14)


def test_a_citation_in_code_or_in_the_list_is_not_a_citation():
    """Bypass: a cite read from code, or from the References section, makes a page that cites none
    look like one that does. A bare link to the list is a pointer, not a citation."""
    assert gate.citation("Use `Lee et al. (2021)` as the key.\n\n```\nLee et al. (2021)\n```\n") is None
    assert gate.citation("## References\n\n- Lee et al. (2021)\n") is None
    assert gate.citation("The methods are in [References](references.md).\n") is None
    assert gate.citation("See [unit quality](references.md#unit-quality).\n") == \
        "references.md#unit-quality"


def test_each_author_year_form_the_pages_use_is_a_citation():
    """Bypass: a form the reader misses, such as two-author, initial-led or multi-line names, lets
    a page cite without its section."""
    for text in ("Maris & Oostenveld (2007).\n", "Schreiber (2000).\n",
                 "Nejat and Hajipour Sardouie (2021) normalize.\n",
                 "Westerberg, J., Durand, S., Cabasco, H., et al. (2024).\n",
                 "Friston\net al. 2014.\n", "Winkler et al., 2016.\n"):
        assert gate.citation(text) is not None, text


def test_a_unit_in_an_identifier_a_code_span_or_a_block_is_not_prose():
    """Bypass: a reader that matches `um` inside `depth_um`, a code span, a link target or a code
    block fails every page that names a column. A unit in prose is read."""
    assert gate.micrometre_units("The column `depth_um` and `um` are code; depth_um is a name.\n") == []
    assert gate.micrometre_units("A word like umbrella, and ![x](assets/um/plot.png).\n") == []
    assert gate.micrometre_units("```\n# 40 um\n```\n") == []
    assert gate.micrometre_units("Depth is 40 um.\n") == [(1, "um")]
    assert gate.micrometre_units("Depth is 40 µm.\n") == [(1, "µm")]
    assert gate.micrometre_units("Depth is $\\mu\\text{m}$.\n") == [(1, "\\mu\\text{m}")]


def test_the_references_and_micrometre_readers_reach_the_live_pages():
    """Bypass: a reader that sees no page passes every page. The citation reader reads the pages
    that cite; the micrometre reader reads every page under docs/."""
    citing = dict(gate.citing_pages(REPO_ROOT))
    assert "laminar.md" in citing and "06_spikes_psth_and_onset_dynamics.md" in citing, sorted(citing)
    assert len(gate.documents(REPO_ROOT)) >= 28
