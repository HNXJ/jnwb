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

import ast
import json
import os
import shutil
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


# ============================================================================
# P-44: a version string is a literal, so it cannot identify a copy
# ============================================================================
#
# The tests above assert *which* package was imported, by path. They are the scanners, and
# they work. What was unprotected is the probe that takes the shortcut: an installed jnwb and
# this checkout both answered `0.2.5` while their `read_nwb` signatures differed, so anything
# that identified a copy by `__version__` read two different packages as one.
#
# `jnwb.__package_id__` is the answer to "which copy", computed from the copy's own sources
# instead of declared. Three ways it could pass while the invariant is violated, each with the
# test below that closes it:
#
#   1. computing the digest from a directory that is not the loaded module's own -- the
#      installed copy would hash the checkout's files and agree with it.
#      -> test_the_live_pair_p44_describes_is_separated_by_the_identifier
#   2. digesting an empty file set -- every copy hashes to one constant and all copies agree,
#      having measured none of them.
#      -> test_the_identifier_refuses_rather_than_answering_from_an_empty_scan
#   3. digesting the absolute path -- every pair separates, including two identical
#      installations, so "different" would mean "elsewhere" and not "different code".
#      -> test_two_identical_copies_in_different_directories_get_the_same_id

IDENTITY_PROBE = "\n".join([
    "import json, pathlib",
    "import jnwb",
    "print(json.dumps({",
    "    'file': str(pathlib.Path(jnwb.__file__).resolve()),",
    "    'version': jnwb.__version__,",
    "    'id': getattr(jnwb, '__package_id__', None),",
    "}))",
])

#: Exactly what a caller has to write to get the answer. Asserted as source, not as prose.
PUBLIC_ACCESS_PROBE = "import jnwb\nprint(jnwb.__package_id__)\n"


def package_dir_under_test() -> Path:
    """The loaded package's own directory. Not the checkout's -- these differ for an
    installed run, which is the mode this module exists to support."""
    return Path(jnwb.__file__).resolve().parent


def _ask_a_copy_who_it_is(copy_root: Path, cwd: Path) -> dict:
    """Import the `jnwb` under `copy_root` in a child and report what it says about itself.

    The child selects its own installation through `PYTHONPATH`, which is the excluded case in
    `test_no_test_module_rebinds_the_front_of_sys_path`: this session's imports are untouched.
    `cwd` must hold no importable `jnwb`, so `copy_root` beats site-packages and the checkout.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(copy_root)
    env.pop("JNWB_EXPECTED_PACKAGE_ROOT", None)
    result = subprocess.run(
        [sys.executable, "-c", IDENTITY_PROBE],
        cwd=cwd, capture_output=True, text=True, timeout=300, env=env,
    )
    assert result.returncode == 0, f"probe under {copy_root} failed: {result.stderr[-600:]}"
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    expected = copy_root / package_dir_under_test().name
    assert Path(payload["file"]).parent == expected, (
        f"the child imported {payload['file']}, not the copy at {expected}, so this "
        f"measurement describes the wrong package"
    )
    return payload


@pytest.fixture(scope="module")
def divergent_copies(tmp_path_factory) -> dict[str, dict]:
    """Three copies of the package under test: `a` and `c` identical, `b` changed by one line.

    `b` differs from `a` by an appended comment in `nwb_io.py` and by nothing else. That is
    the smallest difference a copy can have, and it changes no behaviour -- P-44's real pair
    differed in `read_nwb`'s signature, so an identifier that separates a comment separates a
    signature too.

    `__version__` is never touched. All three report the same version, which is the condition
    P-44 describes: the string is identical and the code is not.
    """
    root = tmp_path_factory.mktemp("copies")
    source = package_dir_under_test()
    for name in ("a", "b", "c"):
        shutil.copytree(source, root / name / source.name,
                        ignore=shutil.ignore_patterns("__pycache__"))
    changed = root / "b" / source.name / "nwb_io.py"
    assert changed.is_file(), f"the fixture did not copy the package: {changed} is missing"
    before = changed.read_bytes()
    changed.write_bytes(before + b"\n# one appended comment; no behaviour changes\n")
    assert changed.read_bytes() != before, "the fixture failed to make the copies differ"
    return {name: _ask_a_copy_who_it_is(root / name, root) for name in ("a", "b", "c")}


def test_the_three_copies_are_indistinguishable_by_version(divergent_copies) -> None:
    """The premise. If this fails, the fixture is not building the case it is named after."""
    versions = {name: payload["version"] for name, payload in divergent_copies.items()}
    assert set(versions.values()) == {jnwb.__version__}, (
        f"the copies do not all report {jnwb.__version__}, so they were already separable by "
        f"version and the tests below prove nothing: {versions}"
    )


def test_two_copies_that_differ_in_source_get_different_ids(divergent_copies) -> None:
    a, b = divergent_copies["a"], divergent_copies["b"]
    assert a["id"] is not None, "the copy under test has no __package_id__"
    assert a["id"] != b["id"], (
        "one line of source changed and the identifier did not, so it is another declared "
        f"literal like __version__ rather than a measurement: both say {a['id']}"
    )


def test_two_identical_copies_in_different_directories_get_the_same_id(divergent_copies) -> None:
    """The discriminator. Without it, the test above is explained by the path alone.

    An identifier that merely encoded `__file__` would separate every pair, this one included,
    and would report two identical installations as different copies while still being unable
    to notice that a copy's code had changed underneath a fixed path.
    """
    a, c = divergent_copies["a"], divergent_copies["c"]
    assert a["file"] != c["file"], "the fixture put both copies in one directory"
    assert a["id"] == c["id"], (
        "two byte-identical copies got different ids, so the identifier measures where the "
        f"package sits rather than what is in it: {a['id']} vs {c['id']}"
    )


def _other_importable_package_dirs() -> list[Path]:
    under_test = package_dir_under_test()
    others = []
    for entry in sys.path:
        if not entry:
            continue
        candidate = Path(entry).resolve() / under_test.name
        if (candidate / "__init__.py").is_file() and candidate != under_test:
            others.append(candidate)
    return others


def _sources_relative_to(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    }


def test_the_live_pair_p44_describes_is_separated_by_the_identifier(tmp_path, monkeypatch) -> None:
    """P-44 as it stands on this machine, not as a synthetic reconstruction.

    The other copy predates this attribute, so its id is computed here by pointing the same
    function at its directory. That substitution is the mechanism itself: the function takes
    the package root from `__file__` and hashes what it finds there, so what it reports for
    another copy does not depend on this checkout -- which is what makes a copy unable to
    borrow another's identity.

    The assertion is that the id agrees with the sources, in both directions, rather than
    that the two copies always differ: `pip install .` from this checkout would make them
    genuinely identical, and demanding a difference there would be demanding a wrong answer.
    Ground truth is a direct byte comparison, which shares no code with the digest.
    """
    others = _other_importable_package_dirs()
    if not others:
        pytest.skip("only one importable jnwb on sys.path; there is no pair to separate")
    ours = jnwb._compute_package_id()
    our_sources = _sources_relative_to(package_dir_under_test())
    p44_shaped = []
    for other in others:
        payload = _ask_a_copy_who_it_is(other.parent, tmp_path)
        monkeypatch.setattr(jnwb, "__file__", str(other / "__init__.py"))
        try:
            theirs = jnwb._compute_package_id()
        finally:
            monkeypatch.undo()
        identical = _sources_relative_to(other) == our_sources
        if identical:
            assert theirs == ours, (
                f"{other} has byte-identical sources to {package_dir_under_test()} and got a "
                f"different id, so the identifier is reporting something other than the code"
            )
            continue
        assert theirs != ours, (
            f"{other} and {package_dir_under_test()} hold different sources and both report "
            f"id {ours}, so the identifier cannot tell them apart"
        )
        if payload["version"] == jnwb.__version__:
            p44_shaped.append(other)
    if not p44_shaped:
        pytest.skip(
            f"no second copy is P-44 shaped here (same version {jnwb.__version__}, different "
            f"sources); the identifier was still checked against ground truth for: {others}"
        )


def test_the_identifier_refuses_rather_than_answering_from_an_empty_scan(
    tmp_path, monkeypatch
) -> None:
    """Hashing no files yields one constant for every copy, so it would report every pair
    identical exactly when it had read neither of them."""
    empty = tmp_path / "nothing-here"
    empty.mkdir()
    monkeypatch.setattr(jnwb, "__file__", str(empty / "__init__.py"))
    with pytest.raises(RuntimeError, match="cannot be fingerprinted"):
        jnwb._compute_package_id()


def test_the_identifier_is_reachable_without_importing_a_private_name(tmp_path) -> None:
    """`import jnwb; jnwb.__package_id__` and nothing else.

    The probe is read from its own syntax tree rather than eyeballed, so relaxing it into
    `from jnwb._something import ...` fails here instead of quietly redefining "reachable".
    """
    for node in ast.walk(ast.parse(PUBLIC_ACCESS_PROBE)):
        if isinstance(node, ast.ImportFrom):
            imported = [node.module or ""] + [alias.name for alias in node.names]
        elif isinstance(node, ast.Import):
            imported = [alias.name for alias in node.names]
        else:
            continue
        for name in imported:
            assert not any(part.startswith("_") for part in name.split(".")), (
                f"the probe reaches the identifier through a private name: {ast.unparse(node)}"
            )

    env = dict(os.environ)
    env["PYTHONPATH"] = str(package_dir_under_test().parent)
    result = subprocess.run(
        [sys.executable, "-c", PUBLIC_ACCESS_PROBE],
        cwd=tmp_path, capture_output=True, text=True, timeout=300, env=env,
    )
    assert result.returncode == 0, result.stderr[-600:]
    value = result.stdout.strip()
    assert len(value) == 64 and all(c in "0123456789abcdef" for c in value), (
        f"the identifier is not a sha256 digest: {value!r}"
    )
    assert "__package_id__" in dir(jnwb), (
        "the identifier is resolved lazily and is not named in __dir__, so nothing discovers "
        "it without being told it exists"
    )
