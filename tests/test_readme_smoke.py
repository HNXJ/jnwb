"""Executable closure probes for the root README quickstart blocks."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import jnwb

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
#: Where a repository-relative path has to be written so that it also resolves from PyPI.
BLOB = "https://github.com/HNXJ/jnwb/blob/main/"


def _self_contained_python_blocks(text):
    """Fenced ``python`` blocks that need nothing but the package.

    Blocks that open a recording are excluded by the file they name, not by position,
    so inserting a block above them does not silently change what is executed.
    """
    blocks = re.findall(r"^```python\n(.*?)^```", text, re.M | re.S)
    return [b for b in blocks if ".nwb" not in b]


def test_readme_quickstart_blocks_execute():
    """Executes the README's own text.

    This used to hold a hand-copied transcription of the quickstart and never opened
    `README.md` at all -- the module-level `README` constant was unused in the body --
    so the two drifted: the README passed `t0_bounds=(0.0, 200.0)` while the copy here
    asserted `(0.0, 250.0)`. A second copy of a code sample cannot be kept honest by
    reading it, so there is no longer a second copy.
    """
    text = README.read_text(encoding="utf-8")
    blocks = _self_contained_python_blocks(text)
    assert blocks, "no self-contained ```python block found; this test checks nothing"

    for block in blocks:
        namespace = {"__name__": "__readme__"}
        exec(compile(block, "README.md", "exec"), namespace)  # noqa: S102 - the point


def test_readme_arrays_quickstart_recovers_the_onset_it_prints():
    """Executing a block does not check what it prints.

    The block above ran green for the whole of 0.2.x while printing an onset of 180.0 ms
    with an R^2 of 0.00, fitted to `rng.uniform(0.0, 10.0, 300)` -- homogeneous noise over
    four events, containing no onset for the fit to find. An R^2 of 0.00 is the fit
    reporting that it explains none of the variance; the number beside it was whatever the
    optimiser landed on, printed on the front page as a result.

    The block now injects a real onset and names it, so the fit can be held to it.
    """
    text = README.read_text(encoding="utf-8")
    section = text.split("## Quickstart (arrays)", 1)[1]
    blocks = _self_contained_python_blocks(section)
    assert blocks, "the arrays quickstart block was not found; this test checks nothing"

    block = blocks[0]
    truth = re.search(r"of a true (\d+\.\d+)", block)
    assert truth, "the block no longer states the onset it is recovering"
    t0_true = float(truth.group(1))

    namespace = {"__name__": "__readme__"}
    exec(compile(block, "README.md", "exec"), namespace)  # noqa: S102 - the point
    fit = namespace["fit"]
    assert fit["r2"] > 0.9, (
        f"R^2 = {fit['r2']:.2f}: the block prints a t0 the fit cannot support"
    )
    assert abs(fit["t0"] - t0_true) < 15.0, (
        f"recovered t0 = {fit['t0']:.1f} ms against a stated truth of {t0_true} ms"
    )
    assert fit["bound_status"] is None, (
        f"the fit finished pinned at its {fit['bound_status']} bound, so t0_bounds, not "
        "the data, chose the printed number"
    )


def test_readme_links_resolve_from_the_page_that_renders_it():
    """`readme = "README.md"` makes this file the PyPI long description.

    PyPI renders it verbatim and does not rewrite relative links, so
    `[CONTRIBUTING.md](CONTRIBUTING.md)` resolved against pypi.org and 404'd.

    An absolute link can be wrong in the other direction -- a URL that looks right and
    points at nothing -- so each `blob/main` target is resolved against the checkout.
    """
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["readme"] == "README.md", (
        "README.md is no longer the long description; this test guards the wrong file"
    )

    links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", README.read_text(encoding="utf-8"))
    assert len(links) >= 7, f"only {len(links)} links found; the sweep has stopped working"
    for label, target in links:
        assert target.startswith(("http://", "https://")), (
            f"README link {label!r} -> {target!r} is relative, so it is dead on the PyPI "
            "page this file is rendered on"
        )
        if target.startswith(BLOB):
            rel = target[len(BLOB):]
            assert (REPO_ROOT / rel).exists(), (
                f"README link {label!r} points at {rel}, which is not in the repository"
            )


def test_readme_capability_table_symbols_exist():
    text = README.read_text(encoding="utf-8")
    table_section = text.split("## Capabilities", 1)[1].split("## Installation", 1)[0]
    symbols = re.findall(r"`([a-zA-Z_][a-zA-Z0-9_]*)`", table_section)
    for symbol in symbols:
        assert hasattr(jnwb, symbol), f"README capability table references missing jnwb.{symbol}"


def test_readme_does_not_hardcode_public_symbol_count():
    text = README.read_text(encoding="utf-8")
    assert not re.search(r"\b\d{2,4}\s+public\s+symbols\b", text, re.I)


def test_readme_python_version_matches_policy():
    """Compares the README against the files that define the policy.

    Asserting the literals `"3.12"` and `"3.14"` appear somewhere in the README cannot
    detect the drift it is named for: both strings survive any change to
    `requires-python` or to the CI matrix, and neither file was read.
    """
    text = README.read_text(encoding="utf-8")
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github" / "workflows" / "workflow.yml").read_text(
        encoding="utf-8"
    )

    declared_min = re.search(r'requires-python\s*=\s*">=([\d.]+)"', pyproject)
    assert declared_min, "pyproject.toml has no requires-python to compare against"
    minimum = declared_min.group(1)
    assert re.search(rf"Requires Python \*\*{re.escape(minimum)} or newer\*\*", text), (
        f"README does not state the minimum {minimum} declared by requires-python"
    )

    ci_versions = re.search(r"python-version:\s*\[([^\]]*)\]", workflow)
    assert ci_versions, "workflow.yml has no python-version matrix to compare against"
    tested = re.findall(r"\d+\.\d+", ci_versions.group(1))
    assert tested, "the CI matrix parsed empty; this assertion would be vacuous"
    stated = re.search(r"Tested in CI on ([^\n]+)", text)
    assert stated, "README does not state which versions CI tests"
    assert re.findall(r"\d+\.\d+", stated.group(1)) == tested, (
        f"README claims CI tests {stated.group(1).strip()}, workflow.yml runs {tested}"
    )

    classifiers = re.findall(r"Programming Language :: Python :: (\d+\.\d+)", pyproject)
    assert set(tested) <= set(classifiers), (
        f"CI tests {tested} but pyproject classifies only {classifiers} as supported"
    )
