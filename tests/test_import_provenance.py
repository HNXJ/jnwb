"""The suite asserts which `jnwb` it is testing, instead of assuming.

`python examples/quickstart_jnwb.py` puts the script's own directory on `sys.path`, not the
repository root, so `import jnwb` resolves to whatever is installed. During this audit that
ran the quickstart against an installed `jnwb==0.1.8` from inside a `0.2.4` checkout: the
figure rendered, every panel said CORRECT, and the defect under investigation appeared not to
reproduce. A standing rule to check `jnwb.__file__` in every probe did not prevent it, which
makes it a harness defect rather than an operator lapse -- so it is asserted here.

A green suite proves nothing about this checkout unless the package it imported came from
this checkout. `JNWB_EXPECTED_PACKAGE_ROOT` names a different root for a run that is
qualifying a built wheel or an installed copy; unset, the expectation is the working tree.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import jnwb

REPO_ROOT = Path(__file__).resolve().parents[1]


def expected_package_dir() -> Path:
    override = os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT")
    root = Path(override).resolve() if override else REPO_ROOT
    return (root / "jnwb").resolve()


def test_the_jnwb_under_test_is_the_one_the_harness_intends() -> None:
    actual = Path(jnwb.__file__).resolve().parent
    expected = expected_package_dir()
    assert actual == expected, (
        f"the suite imported jnwb {jnwb.__version__} from {actual}, but this run is supposed "
        f"to be testing {expected}. Every result in this session describes the wrong package. "
        f"Set JNWB_EXPECTED_PACKAGE_ROOT if a different copy is deliberately under test."
    )


def test_no_second_jnwb_shadows_the_one_under_test() -> None:
    """A second importable copy earlier on `sys.path` is the mechanism, not bad luck."""
    found = []
    for entry in sys.path:
        if not entry:
            continue
        candidate = Path(entry).resolve() / "jnwb" / "__init__.py"
        if candidate.exists():
            found.append(candidate.parent)
    assert found, "no importable jnwb was found on sys.path at all"
    assert found[0] == expected_package_dir(), (
        f"the first importable jnwb on sys.path is {found[0]}, which shadows "
        f"{expected_package_dir()}"
    )


EXAMPLES = sorted(
    list((REPO_ROOT / "examples").glob("*.py"))
    + list((REPO_ROOT / "examples" / "tutorials").glob("*.py"))
)

PROBE = "\n".join([
    "import sys, pathlib",
    "src = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')",
    # The line, not the phrase: the guard's own comment mentions `import jnwb` too.
    "head = src.replace('\\r\\n', '\\n').split('\\nimport jnwb')[0] + '\\nimport jnwb'",
    "ns = {'__file__': sys.argv[1], '__name__': '__provenance__'}",
    "exec(compile(head, sys.argv[1], 'exec'), ns)",
    "print(pathlib.Path(ns['jnwb'].__file__).resolve().parent)",
])


@pytest.mark.parametrize("script", EXAMPLES, ids=lambda p: p.name)
def test_an_example_run_as_documented_imports_the_package_under_test(script: Path) -> None:
    """The two tests above describe the interpreter pytest runs in. An example is another.

    The probe runs from the script's own directory, so `sys.path[0]` is what running the
    script gives it, and it executes the script's real prologue up to and including its
    `import jnwb` -- the checkout guard included. Everything after that import, which is
    where the figures and the NWB fixtures are, is not run.
    """
    result = subprocess.run(
        [sys.executable, "-c", PROBE, str(script)],
        cwd=script.parent,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"probe failed from {script.parent}: {result.stderr[-400:]}"
    imported = Path(result.stdout.strip()).resolve()
    assert imported == expected_package_dir(), (
        f"run from {script.parent.relative_to(REPO_ROOT).as_posix()}, as {script.name} is "
        f"documented to be, `import jnwb` resolves to {imported}, not "
        f"{expected_package_dir()}"
    )


def test_the_quickstart_prints_its_provenance_before_anything_else() -> None:
    """The example a reader actually runs has to say which package produced the figure."""
    source = (REPO_ROOT / "examples" / "quickstart_jnwb.py").read_text(encoding="utf-8")
    body = source.partition("def main(")[2]
    assert body, "quickstart_jnwb.py has no main()"
    first_print = body.find("print(")
    assert first_print != -1, "main() prints nothing"
    line = body[first_print : body.index(")", first_print) + 1]
    assert "__version__" in line and "__file__" in line, (
        f"the first thing main() prints is not the provenance line: {line!r}"
    )
