"""docs/api.md must render the same bytes on every interpreter in the CI matrix.

Six legs run `python scripts/generate_api_md.py --check` against one committed file, so a
generator whose output depends on the interpreter can be green on at most one of them. It
was green on none: CPython 3.13 split `pathlib` into a package, making
`pathlib.Path.__module__` read `pathlib._local` there and `pathlib` on 3.12 and 3.14, and
three signature cells rendered `pathlib._local.Path`. Both 3.13 legs failed; 3.12 and 3.14
passed on both operating systems, which is what identified the interpreter rather than the
OS as the variable.

The invariant under test is not "3.13 agrees with the committed file" -- that would be
satisfied by regenerating on 3.13 and turning the other four legs red. It is that the
rendered module path of a class does not depend on which interpreter rendered it.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json.decoder
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# `scripts/` is excluded from the wheel, and the leg that qualifies the built artifact runs this
# suite from outside the checkout, so nothing puts the repository on `sys.path` there. A
# module-scope `from scripts...` raises ModuleNotFoundError -- a collection *error*, which pytest
# reports as `Interrupted` and which can take unrelated modules down with it.
# `append`, never `insert(0, ...)`: prepending the checkout re-shadows the installed package for
# the whole session, which tests/test_the_suite_can_qualify_an_installed_copy.py forbids -- and
# this module's whole subject is which copy an interpreter resolves, so the shadow would have
# been measuring the checkout while claiming to measure the wheel.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts.generate_api_md import (  # noqa: E402
    _canonical_type_name,
    _format_annotation,
    generate_api_markdown,
)

MATRIX = ("3.12", "3.13", "3.14")


class TestPrivateSubmoduleCollapse:
    """Unit-level proof of the mechanism, on whatever interpreter is running."""

    def test_private_stdlib_submodule_collapses_when_parent_reexports(self):
        """Fails pristine on every interpreter, so no CI leg can miss the regression.

        ``concurrent.futures.Future.__module__`` is ``concurrent.futures._base`` on 3.12,
        3.13 and 3.14 alike, and the package re-exports it. Anchoring the discriminator
        here rather than on ``pathlib`` means the test does not depend on running under
        the one interpreter that happens to expose the defect.
        """
        assert _format_annotation(concurrent.futures.Future) == "concurrent.futures.Future"

    def test_public_submodule_is_left_alone(self):
        """Only a private (underscore-led) segment is collapsed.

        ``json.decoder`` is a documented public submodule; collapsing it would lose the
        module a reader needs to import from.
        """
        assert _format_annotation(json.decoder.JSONDecoder) == "json.decoder.JSONDecoder"

    def test_a_name_the_parent_does_not_reexport_is_kept(self):
        """The collapse never invents a name that does not resolve.

        ``pathlib`` does not export a ``PurePosixPath`` sourced from a module called
        ``pathlib._nonexistent``, so the private path must survive unchanged rather than
        being shortened to a ``pathlib.Nope`` that no reader could import.
        """
        assert _canonical_type_name("pathlib._nonexistent", "Nope") == "pathlib._nonexistent.Nope"

    def test_third_party_module_paths_are_untouched(self):
        """Dependency internals vary with the dependency version, not the interpreter.

        numpy's private module path is stable across the matrix and is deliberately out of
        scope, so this asserts the normalisation did not widen into it.
        """
        import numpy as np

        assert _format_annotation(np.random.Generator) == "numpy.random._generator.Generator"

    def test_pathlib_path_renders_without_a_private_submodule(self):
        """The defect itself. Fails pristine under 3.13; a guard under 3.12 and 3.14."""
        assert _format_annotation(pathlib.Path) == "pathlib.Path"
        assert "_local" not in generate_api_markdown(REPO_ROOT)


def _matrix_interpreters() -> dict[str, str]:
    """Locate a dependency-equipped interpreter for each matrix version, if present.

    ``JNWB_MATRIX_PYTHONS`` (os.pathsep-separated interpreter paths) is honoured first.
    Without it this discovers only what the machine happens to have installed with the
    dependencies present, which on a developer box is typically not the interpreter that
    exposes an interpreter-dependent defect -- so the comparison can silently narrow to a
    pair that already agrees and pass for the wrong reason.
    """
    found: dict[str, str] = {}
    override = [p for p in os.environ.get("JNWB_MATRIX_PYTHONS", "").split(os.pathsep) if p]
    for version in MATRIX:
        candidates = []
        for path in override:
            probe = subprocess.run(
                [path, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
                cwd=REPO_ROOT, capture_output=True, text=True,
            )
            if probe.returncode == 0 and probe.stdout.strip() == version:
                candidates.append(path)
        if f"{sys.version_info.major}.{sys.version_info.minor}" == version:
            candidates.append(sys.executable)
        launcher = shutil.which("py")
        if launcher:
            candidates.append(f"{launcher}|-{version}")
        uv = shutil.which("uv")
        if uv:
            probe = subprocess.run(
                [uv, "python", "find", version],
                cwd=REPO_ROOT, capture_output=True, text=True,
            )
            if probe.returncode == 0 and probe.stdout.strip():
                candidates.append(probe.stdout.strip())
        for candidate in candidates:
            argv = candidate.split("|")
            check = subprocess.run(
                [*argv, "-c", "import numpy, pandas, jnwb"],
                cwd=REPO_ROOT, capture_output=True, text=True,
            )
            if check.returncode == 0:
                found[version] = candidate
                break
    return found


class TestAcrossTheMatrix:
    """End-to-end: the committed page is what every available interpreter generates."""

    def test_generated_bytes_are_identical_across_available_interpreters(self):
        interpreters = _matrix_interpreters()
        if len(interpreters) < 2:
            pytest.skip(
                "need two dependency-equipped matrix interpreters to compare; "
                f"found {sorted(interpreters)}"
            )
        committed = (REPO_ROOT / "docs" / "api.md").read_bytes()
        digests = {}
        for version, candidate in sorted(interpreters.items()):
            res = subprocess.run(
                [*candidate.split("|"), "scripts/generate_api_md.py", "--check"],
                cwd=REPO_ROOT, capture_output=True, text=True,
            )
            digests[version] = (res.returncode, res.stdout.strip())
        failed = {v: d for v, d in digests.items() if d[0] != 0}
        assert not failed, (
            "docs/api.md is not what every interpreter generates; "
            f"committed sha256={hashlib.sha256(committed).hexdigest()} results={digests}"
        )

    def test_committed_page_has_lf_endings_in_bytes(self):
        """A text-mode rewrite of a generated file reintroduces CRLF invisibly.

        ``--check`` compares ``read_text`` output, which normalises endings, so it cannot
        see this; only a byte-level assertion can.
        """
        raw = (REPO_ROOT / "docs" / "api.md").read_bytes()
        assert raw.count(b"\r") == 0, "docs/api.md contains CR bytes; it must be LF-only"
        assert raw.endswith(b"\n")
