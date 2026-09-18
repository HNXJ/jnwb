"""The release gate must be able to see what a wheel actually carries.

The check looked for the substring ``/tests/``. A wheel entry has no leading distribution
directory, so ``"/tests/" in "tests/__init__.py"`` is False: a wheel shipping the entire test
suite and ``scripts/`` passed both the local gate and the identical copy of the rule in CI.
The sdist was caught only by the accident of its layout, whose entries are
``jnwb-0.2.5/tests/...``.

These tests drive the matcher over constructed manifests, and build one real wheel-shaped zip
so the archive path is exercised rather than only the list comprehension.
"""

from __future__ import annotations

import re
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.release_gate import (  # noqa: E402
    FORBIDDEN_COMPONENTS,
    FORBIDDEN_SUBSTRINGS,
    forbidden_entries,
)

CLEAN_WHEEL = [
    "jnwb/__init__.py",
    "jnwb/lfp.py",
    "jnwb/backends/numpy_backend.py",
    "jnwb-0.2.5.dist-info/METADATA",
    "jnwb-0.2.5.dist-info/RECORD",
    "jnwb-0.2.5.dist-info/WHEEL",
]


def test_a_wheel_carrying_the_test_suite_is_rejected() -> None:
    """The reproduction. This manifest passed before the repair."""
    problems = forbidden_entries(CLEAN_WHEEL + ["tests/__init__.py", "tests/test_lfp.py"])
    assert len(problems) == 2, problems
    assert all("tests" in problem for problem in problems)


def test_a_wheel_carrying_scripts_is_rejected() -> None:
    problems = forbidden_entries(CLEAN_WHEEL + ["scripts/release_gate.py"])
    assert problems and "scripts" in problems[0]


def test_the_sdist_layout_is_still_rejected() -> None:
    """The one case the old rule did catch must keep being caught."""
    problems = forbidden_entries([
        "jnwb-0.2.5/jnwb/__init__.py",
        "jnwb-0.2.5/tests/test_lfp.py",
        "jnwb-0.2.5/scripts/release_gate.py",
    ])
    assert len(problems) == 2, problems


def test_a_clean_manifest_is_accepted() -> None:
    assert forbidden_entries(CLEAN_WHEEL) == []
    assert forbidden_entries([f"jnwb-0.2.5/{name}" for name in CLEAN_WHEEL]) == []


def test_the_grafted_agent_surface_is_not_rejected() -> None:
    """MANIFEST.in grafts `skills` and includes AGENTS.md on purpose; the gate must allow it."""
    assert forbidden_entries([
        "jnwb-0.2.5/AGENTS.md",
        "jnwb-0.2.5/skills/jnwb/SKILL.md",
        "jnwb-0.2.5/skills/jnwb-lfp-spectral/SKILL.md",
    ]) == []


def test_a_backslash_separated_entry_is_split_the_same_way() -> None:
    """Splitting on "/" alone would read this as one component and accept it."""
    assert forbidden_entries([r"tests\test_lfp.py"])


def test_pollution_tokens_are_caught_inside_a_file_name() -> None:
    """These are markers, not directories, so the component rule would be the weaker one."""
    for name in ["jnwb/omission_helper.py", "jnwb/_unused_thing.py"]:
        assert forbidden_entries([name]), name


def test_a_module_named_after_a_forbidden_directory_is_not_rejected() -> None:
    """The deliberate narrowing: `artifacts` names a directory, not a banned word.

    Under the old substring rule a module called `foo_artifacts.py` would have failed the
    release, which is a different defect in the same check.
    """
    assert forbidden_entries(["jnwb/lfp_artifacts.py", "jnwb/outputs_writer.py"]) == []


def test_every_manifest_prune_target_is_rejected_by_the_gate() -> None:
    """The two lists drifted once. MANIFEST.in is the authority; the gate must cover it.

    Derived from the file rather than restated: adding a `prune` line without teaching the
    gate about it fails here.
    """
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    pruned = re.findall(r"^prune\s+(\S+)\s*$", manifest, flags=re.M)
    assert len(pruned) >= 5, f"only {len(pruned)} prune targets parsed from MANIFEST.in"
    for target in pruned:
        assert forbidden_entries([f"{target}/x.py"]), f"a wheel may carry {target}/"
        assert forbidden_entries([f"jnwb-0.2.5/{target}/x.py"]), f"an sdist may carry {target}/"


def test_no_forbidden_component_is_a_directory_this_package_ships() -> None:
    """A rule that rejects `jnwb` itself would be caught here rather than at release."""
    assert "jnwb" not in FORBIDDEN_COMPONENTS
    assert "skills" not in FORBIDDEN_COMPONENTS, "MANIFEST.in grafts skills into the sdist"
    for token in FORBIDDEN_SUBSTRINGS:
        assert token not in "jnwb/__init__.py"


def test_the_matcher_reads_a_real_archive(tmp_path: Path) -> None:
    """Exercises the zip path, not only the list comprehension."""
    whl = tmp_path / "polluted-0.2.5-py3-none-any.whl"
    with zipfile.ZipFile(whl, "w") as archive:
        for name in CLEAN_WHEEL + ["tests/test_lfp.py"]:
            archive.writestr(name, "x = 1\n")
    with zipfile.ZipFile(whl) as archive:
        problems = forbidden_entries(archive.namelist())
    assert problems and "tests" in problems[0]


def test_the_release_gate_inspects_both_archives_with_this_function() -> None:
    """A matcher nothing calls is the defect it was written to prevent."""
    import ast

    tree = ast.parse((ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = [
        node.lineno for node in ast.walk(main)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "forbidden_entries"
    ]
    assert len(calls) == 2, f"main() calls forbidden_entries {len(calls)} times, not twice"


def test_ci_calls_the_same_matcher_instead_of_keeping_its_own_list() -> None:
    """CI carried a byte-identical copy of the defective list. One rule, one place."""
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "workflow.yml").read_text(encoding="utf-8")
    )
    steps = [
        step
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if "manifest" in str(step.get("name", "")).lower()
    ]
    assert steps, "no manifest-inspection step in the workflow"
    body = "\n".join(str(step.get("run", "")) for step in steps)
    assert "forbidden_entries" in body, "CI does not call the gate's matcher"
    assert "/tests/" not in body, "CI still carries the substring rule that cannot match"


def test_the_ci_snippet_runs_and_fails_on_a_polluted_wheel(tmp_path: Path) -> None:
    """The workflow body is a string inside YAML; nothing else checks that it parses.

    Runs the step's own Python against a constructed `dist/`, so a syntax error or a bad
    import in the snippet fails here rather than on a release branch.
    """
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "workflow.yml").read_text(encoding="utf-8")
    )
    body = next(
        str(step["run"])
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if "manifest" in str(step.get("name", "")).lower()
    )
    match = re.search(r'python -c "\n(.*?)\n\s*"', body, flags=re.S)
    assert match, "the manifest step is no longer a python -c block; this test is stale"
    source = textwrap.dedent(match.group(1))

    dist = tmp_path / "dist"
    dist.mkdir()
    import tarfile

    for entries, name in [
        (CLEAN_WHEEL + ["tests/test_lfp.py"], "jnwb-0.2.5-py3-none-any.whl"),
    ]:
        with zipfile.ZipFile(dist / name, "w") as archive:
            for entry in entries:
                archive.writestr(entry, "x = 1\n")
    with tarfile.open(dist / "jnwb-0.2.5.tar.gz", "w:gz") as archive:
        info = tarfile.TarInfo("jnwb-0.2.5/PKG-INFO")
        info.size = 0
        archive.addfile(info, __import__("io").BytesIO(b""))

    script = tmp_path / "step.py"
    script.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT)},
    )
    assert result.returncode == 1, f"the CI step accepted a polluted wheel:\n{result.stdout}"
    assert "tests/test_lfp.py" in result.stdout, result.stdout + result.stderr


@pytest.mark.skipif(not (ROOT / "dist").exists(), reason="no dist/ built in this checkout")
def test_any_distribution_present_in_this_checkout_is_clean() -> None:
    """Opportunistic: if a build is lying around, it must satisfy the repaired rule."""
    for whl in (ROOT / "dist").glob("*.whl"):
        with zipfile.ZipFile(whl) as archive:
            assert forbidden_entries(archive.namelist()) == [], whl.name
