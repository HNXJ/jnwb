"""A dependency nothing invokes and a script nothing runs are both claims without a caller.

`pytest-cov` was declared in the `test` extra and pulled onto all four CI cells on every push.
There is no `addopts`, no `--cov` and no coverage configuration anywhere in the repository, so
it was installed and never invoked. `pytest-xdist` was in the same position until the
installed-wheel leg started passing `-n auto`; it stays, and this file is what would notice if
that caller went away.

`scripts/build_unified_review.py` and `scripts/reconcile_review_probes.py` were 625 lines with
zero references anywhere, and `harness_gate.py`'s root allowlist carried an exemption for
`jnwb-unified-rev.md`, the output of the first of them -- an artifact the changelog records as
having been removed from the root.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: What makes each declared test dependency true, as something a reader can check. The value
#: is the token that must appear in the repository for the declaration to have a caller --
#: the import name where it is imported, the flag where it is a plugin.
TEST_EXTRA_CALLERS = {
    "pytest": "import pytest",
    "pytest-xdist": "-n auto",
    "build": "-m build",
    "twine": '"twine", "check"',
    "pyyaml": "import yaml",
    "setuptools": "from setuptools import find_namespace_packages",
    "mcp": "from mcp",
    "nbclient": "nbclient",
    "nbformat": "nbformat",
    "ipykernel": "ipykernel",
}

#: Not searched for callers. The changelog and the todo stack describe work that was done,
#: including work that removed things; a mention there is history, not an invocation.
NOT_A_CALLER = ("CHANGELOG.md", "artifacts/")


def _tracked_text() -> str:
    """Every tracked text file's contents, concatenated once.

    Tracked rather than walked: a working checkout has a `.venv` with thousands of files that
    mention every one of these packages, and a caller inside one is not this repository's.
    """
    names = [
        name for name in subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.split()
        if not name.startswith(NOT_A_CALLER)
    ]
    assert len(names) > 100, f"git ls-files returned {len(names)} files; the search is empty"
    chunks = []
    for name in names:
        path = ROOT / name
        try:
            chunks.append(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    return "\n".join(chunks)


def _declared(extra: str) -> list[str]:
    with open(ROOT / "pyproject.toml", "rb") as handle:
        items = tomllib.load(handle)["project"]["optional-dependencies"][extra]
    return [item.split(">")[0].split("<")[0].split("[")[0].split("=")[0].strip() for item in items]


def test_every_declared_test_dependency_has_a_caller() -> None:
    declared = _declared("test")
    corpus = _tracked_text()
    uncalled = []
    for name in declared:
        token = TEST_EXTRA_CALLERS.get(name)
        assert token is not None, (
            f"{name} was added to the test extra without recording what invokes it; add it to "
            f"TEST_EXTRA_CALLERS with the token that proves the caller exists"
        )
        if token not in corpus:
            uncalled.append(f"{name} (looked for {token!r})")
    assert not uncalled, (
        f"declared and never invoked, so every CI cell installs them for nothing: {uncalled}"
    )


def test_the_caller_table_has_no_stale_entries() -> None:
    """A row for a dependency that is no longer declared would hide the next removal."""
    declared = set(_declared("test"))
    stale = sorted(set(TEST_EXTRA_CALLERS) - declared)
    assert not stale, f"TEST_EXTRA_CALLERS names packages the test extra no longer has: {stale}"


def test_coverage_is_not_declared_while_nothing_measures_it() -> None:
    """The specific defect. If coverage comes back, it comes back with an invocation."""
    declared = _declared("test")
    if "pytest-cov" not in declared:
        return
    corpus = _tracked_text()
    assert "--cov" in corpus or "addopts" in corpus, (
        "pytest-cov is declared again with nothing invoking it"
    )


def test_every_script_has_a_caller() -> None:
    """A script nothing runs is 625 lines of unexecuted claim; two of them were."""
    scripts = sorted(
        path for path in (ROOT / "scripts").glob("*.py") if path.name != "__init__.py"
    )
    assert len(scripts) >= 5, f"only {len(scripts)} scripts found; the glob is wrong"
    corpus = _tracked_text()
    orphans = []
    for script in scripts:
        stem = script.stem
        # Its own file mentions its name; a caller is a mention somewhere else.
        elsewhere = corpus.count(stem) - script.read_text(encoding="utf-8").count(stem)
        if elsewhere <= 0:
            orphans.append(script.name)
    assert not orphans, f"nothing in the repository refers to these scripts: {orphans}"


def test_the_root_allowlist_holds_no_exemption_for_a_deleted_artifact() -> None:
    """`jnwb-unified-rev.md` outlived the script that wrote it."""
    # The live set, not the file's text: the comment explaining the removal names the file.
    import sys

    if str(ROOT) not in sys.path:
        sys.path.append(str(ROOT))
    from scripts.harness_gate import ALLOWED_ROOT_FILES

    assert "jnwb-unified-rev.md" not in ALLOWED_ROOT_FILES, (
        "the root freeze still exempts an artifact nothing can produce"
    )
    assert "AGENTS.md" in ALLOWED_ROOT_FILES, "the allowlist was read from the wrong place"


def test_the_documentation_pins_have_one_source() -> None:
    """`docs/requirements.txt` held a byte-identical copy of the [docs] extra.

    `fail_on_warning: true` means a drift between them is a failed publish, and nothing
    compared them.
    """
    import yaml

    assert not (ROOT / "docs" / "requirements.txt").exists(), (
        "docs/requirements.txt is back; the [docs] extra is the source of truth"
    )
    config = yaml.safe_load((ROOT / ".readthedocs.yaml").read_text(encoding="utf-8"))
    installs = config["python"]["install"]
    assert not any("requirements" in entry for entry in installs), (
        f"Read the Docs installs a requirements file again: {installs}"
    )
    assert any(
        entry.get("extra_requirements") == ["docs"] for entry in installs
    ), f"Read the Docs no longer installs the docs extra: {installs}"
    assert config["mkdocs"]["fail_on_warning"] is True, (
        "fail_on_warning was turned off; that is what made the duplicate pins consequential"
    )


def test_the_docs_extra_still_covers_what_the_build_imports() -> None:
    """Removing the duplicate list must not remove the packages the build needs."""
    declared = set(_declared("docs"))
    for required in ["mkdocs", "mkdocs-material", "pymdown-extensions"]:
        assert required in declared, f"the docs extra lost {required}"
