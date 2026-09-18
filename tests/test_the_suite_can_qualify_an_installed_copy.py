"""The suite has to be able to test the built artifact, not only the tree that built it.

The four CI matrix legs run `pytest tests/` from the repository root. `pythonpath = ["."]` and
`tests/__init__.py` both put the checkout ahead of site-packages, so those legs test the source
tree, which merely also has the package installed. Only the smoke step touched the wheel, and
the tutorial step stopped touching it the moment the examples gained a guard that prefers their
own checkout.

Running the suite against an installed copy found three things that made the claim impossible
rather than merely untested: five test modules prepended the repository root to `sys.path` and
so re-shadowed whatever package was under test; two tests opened `skills/...` relative to the
current directory; and one derived the repository from `jnwb.__file__`, which is site-packages
for an installed copy. These tests keep all of that from coming back.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
EXAMPLES = sorted(
    list((ROOT / "examples").glob("*.py"))
    + list((ROOT / "examples" / "tutorials").glob("*.py"))
)

#: Directories that exist only in a checkout. Inserting one of these at the front of
#: `sys.path` cannot shadow an installed `jnwb`, so it is the one permitted prepend.
CHECKOUT_ONLY = ("scripts",)


def _test_modules() -> list[Path]:
    modules = sorted(TESTS.glob("test_*.py"))
    assert len(modules) > 50, f"only {len(modules)} test modules found; the glob is wrong"
    return modules


def test_no_test_module_puts_the_checkout_ahead_of_the_package_under_test() -> None:
    """`sys.path.insert(0, REPO_ROOT)` re-shadows the installed copy for the whole session.

    Read from the syntax tree, not by text search: `test_connectivity.py` builds the same
    call as a string for a subprocess probe, and a grep would read that as a call.
    """
    offenders = []
    for module in _test_modules():
        source = module.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "insert"):
                continue
            if ast.unparse(func.value) != "sys.path":
                continue
            if not node.args or ast.unparse(node.args[0]) != "0":
                continue
            inserted = ast.unparse(node.args[1]) if len(node.args) > 1 else ""
            if not any(name in inserted for name in CHECKOUT_ONLY):
                offenders.append(f"{module.name}:{node.lineno} inserts {inserted} at sys.path[0]")
    assert not offenders, (
        "these modules prepend a directory that can shadow the package under test; append "
        f"instead: {offenders}"
    )


def test_no_test_reads_a_repository_file_through_the_current_directory() -> None:
    """`Path("skills/x/SKILL.md")` resolves only when pytest is run from the root."""
    prefixes = ("skills/", "docs/", "examples/", "scripts/", "artifacts/", "tests/", "jnwb/")
    offenders = []
    for module in _test_modules():
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "Path" or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                if first.value.startswith(prefixes):
                    offenders.append(f"{module.name}:{node.lineno} opens {first.value!r}")
    assert not offenders, (
        f"these paths depend on the working directory; derive them from __file__: {offenders}"
    )


def test_every_example_guard_stands_aside_for_a_deliberate_installed_run() -> None:
    """Read from the syntax tree of all ten, so a new example cannot be added without it.

    Not a text search for the variable name: the comment above the guard names it too, so a
    guard stripped back to `if (_CHECKOUT / "jnwb").exists()` would still match the string.
    """
    assert len(EXAMPLES) == 10, f"{len(EXAMPLES)} examples found, expected 10"
    for example in EXAMPLES:
        tree = ast.parse(example.read_text(encoding="utf-8"))
        guards = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.If) and "sys.path.insert" in ast.unparse(node.body)
        ]
        assert guards, f"{example.name} lost its checkout guard entirely"
        for guard in guards:
            assert "JNWB_EXPECTED_PACKAGE_ROOT" in ast.unparse(guard.test), (
                f"{example.name}'s guard condition has no opt-out, so a run qualifying an "
                f"installed copy is silently redirected to the checkout: "
                f"{ast.unparse(guard.test)}"
            )


def test_the_guard_actually_stands_aside_when_the_variable_is_set(tmp_path: Path) -> None:
    """The source check above proves the string is present. This proves the branch works."""
    example = ROOT / "examples" / "tutorials" / "03_spiking.py"
    # The guard reads `__file__`, so the prologue is executed under the example's own name
    # rather than copied elsewhere -- a copy in tmp_path finds no sibling package and would
    # make this test pass for the wrong reason.
    probe = tmp_path / "probe.py"
    probe.write_text(
        "\n".join([
            "import sys, pathlib",
            "src = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')",
            "head = src.replace('\\r\\n', '\\n').split('\\nimport jnwb')[0]",
            "ns = {'__file__': sys.argv[1], '__name__': '__probe__'}",
            "exec(compile(head, sys.argv[1], 'exec'), ns)",
            "print(sys.path[0])",
        ]),
        encoding="utf-8",
    )

    def first_entry(env_value: str | None) -> str:
        env = dict(os.environ)
        env.pop("JNWB_EXPECTED_PACKAGE_ROOT", None)
        if env_value is not None:
            env["JNWB_EXPECTED_PACKAGE_ROOT"] = env_value
        result = subprocess.run(
            [sys.executable, str(probe), str(example)],
            cwd=example.parent,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        assert result.returncode == 0, result.stderr[-400:]
        return result.stdout.strip()

    assert Path(first_entry(None)).resolve() == ROOT, (
        "unset, the guard must still prefer the checkout the example ships in"
    )
    assert Path(first_entry(str(tmp_path))).resolve() != ROOT, (
        "set, the guard must stand aside so the installed copy wins"
    )


def _build_steps() -> list[dict]:
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "workflow.yml").read_text(encoding="utf-8")
    )
    return workflow["jobs"]["build"]["steps"]


def _step(fragment: str) -> dict:
    matches = [s for s in _build_steps() if fragment in str(s.get("name", ""))]
    assert len(matches) == 1, f"{len(matches)} build steps match {fragment!r}"
    return matches[0]


def _commands(fragment: str) -> str:
    """The step's shell commands with its comments removed.

    These steps explain themselves at length, and every term asserted below appears in that
    prose. Asserting against the raw body would pass on a step whose commands had been
    gutted and whose comments still described what it used to do.
    """
    body = str(_step(fragment)["run"])
    return "\n".join(
        line for line in body.splitlines() if not line.lstrip().startswith("#")
    )


def test_ci_runs_the_suite_against_the_installed_wheel() -> None:
    """Each clause is load-bearing: drop one and the leg silently tests the checkout again."""
    body = _commands("test suite against the installed wheel")
    assert "-m pytest" in body, "the step does not run pytest"
    assert "--import-mode=importlib" in body, (
        "without importlib mode pytest inserts the rootdir, because tests/ is a package"
    )
    assert "-o pythonpath=" in body, "pythonpath = ['.'] is still in force"
    assert "JNWB_EXPECTED_PACKAGE_ROOT" in body, (
        "nothing asserts which package the leg imported, so a fallback to the checkout passes"
    )
    assert "cd /tmp" in body, "the step still runs from inside the repository"
    assert "clean_env" in body, "the step does not use the environment the wheel was installed in"


def test_that_leg_runs_after_the_wheel_is_installed() -> None:
    names = [str(step.get("name", "")) for step in _build_steps()]
    install = next(i for i, name in enumerate(names) if "clean virtualenv" in name)
    suite = next(i for i, name in enumerate(names) if "test suite against the installed" in name)
    assert install < suite, "the suite leg runs before the wheel is installed"


def test_the_leg_does_not_reinstall_jnwb_from_source() -> None:
    """`pip install .[test]` would replace the wheel under test with the checkout."""
    body = _commands("test suite against the installed wheel")
    for forbidden in ["pip install .", "pip install -e", 'pip install "."', "pip install $GITHUB_WORKSPACE"]:
        assert forbidden not in body, f"the step reinstalls jnwb from source: {forbidden!r}"


def test_the_test_tooling_is_read_from_pyproject_rather_than_listed_again() -> None:
    """A second copy of the test extra would drift from the first."""
    body = _commands("test suite against the installed wheel")
    assert "optional-dependencies" in body, "the step does not read the extras from pyproject"
    assert "requirements.txt" in body


def test_the_tutorial_step_tells_the_guard_to_stand_aside() -> None:
    """Without this the tutorials run against the checkout while the step's name says wheel."""
    body = _commands("tutorials against the installed wheel")
    assert "JNWB_EXPECTED_PACKAGE_ROOT" in body, (
        "the tutorials' own checkout guard sends this step back to the source tree"
    )
    assert "export JNWB_EXPECTED_PACKAGE_ROOT" in body, (
        "the variable has to reach the tutorial subprocesses, not just this shell"
    )


@pytest.mark.parametrize("snippet", ["import-mode", "pythonpath"])
def test_the_matrix_legs_still_test_the_checkout(snippet: str) -> None:
    """The new leg is additional. The matrix legs are what makes a source change fail fast."""
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "workflow.yml").read_text(encoding="utf-8")
    )
    body = "\n".join(
        str(step.get("run", "")) for step in workflow["jobs"]["test"]["steps"]
    )
    assert "pytest" in body, "the matrix legs no longer run the suite"
    assert snippet not in body, (
        f"a matrix leg now overrides {snippet}; those legs are supposed to test the checkout"
    )


def test_this_file_would_have_caught_the_defects_it_documents() -> None:
    """A guard written after the fact should fail on the code as it was.

    Runs the two scanners over a reconstruction of the old lines rather than trusting that
    they would have fired.
    """
    old_prepend = textwrap.dedent(
        """
        import sys
        from pathlib import Path
        REPO_ROOT = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(REPO_ROOT))
        """
    )
    tree = ast.parse(old_prepend)
    inserts = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "insert"
        and ast.unparse(node.func.value) == "sys.path"
        and ast.unparse(node.args[0]) == "0"
    ]
    assert inserts, "the scanner would not have seen the prepend it was written for"
    assert not any("scripts" in ast.unparse(node.args[1]) for node in inserts)

    old_relative = 'from pathlib import Path\nPath("skills/jnwb-fact-action/SKILL.md")\n'
    tree = ast.parse(old_relative)
    hits = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Path"
        and isinstance(node.args[0], ast.Constant)
        and str(node.args[0].value).startswith("skills/")
    ]
    assert hits, "the scanner would not have seen the working-directory path"
