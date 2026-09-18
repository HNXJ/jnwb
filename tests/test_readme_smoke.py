"""Executable closure probes for the root README quickstart blocks."""
from __future__ import annotations

import re
from pathlib import Path

import jnwb

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"


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
