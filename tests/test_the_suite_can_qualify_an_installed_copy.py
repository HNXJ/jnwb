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
import re
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


_REPO_DIRS = ("skills", "docs", "examples", "scripts", "artifacts", "tests", "jnwb")


def _cwd_relative_paths(source: str, name: str) -> list[str]:
    """`Path("scripts/x")` and `Path("scripts") / "x"` alike: a bare directory name is the root."""
    offenders = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "Path" or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            head = first.value.replace("\\", "/").split("/", 1)[0]
            if head in _REPO_DIRS:
                offenders.append(f"{name}:{node.lineno} opens {first.value!r}")
    return offenders


def test_no_test_reads_a_repository_file_through_the_current_directory() -> None:
    """`Path("skills/x/SKILL.md")` resolves only when pytest is run from the root."""
    offenders = []
    for module in _test_modules():
        offenders += _cwd_relative_paths(module.read_text(encoding="utf-8"), module.name)
    assert not offenders, (
        f"these paths depend on the working directory; derive them from __file__: {offenders}"
    )


def test_every_example_guard_stands_aside_for_a_deliberate_installed_run() -> None:
    """Read from the syntax tree of all eleven, so a new example cannot be added without it.

    Not a text search for the variable name: the comment above the guard names it too, so a
    guard stripped back to `if (_CHECKOUT / "jnwb").exists()` would still match the string.
    """
    assert len(EXAMPLES) == 11, f"{len(EXAMPLES)} examples found, expected 11"
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

    # The scanners themselves, not a copy of their logic. The second path and the aliased
    # assertion are the two spellings that reached the installed-wheel CI leg on 2026-09-22.
    for source in (
        'from pathlib import Path\nPath("skills/jnwb-fact-action/SKILL.md")\n',
        'from pathlib import Path\ngate = Path("scripts") / "harness_gate.py"\n',
    ):
        assert _cwd_relative_paths(source, "old.py"), f"not seen: {source!r}"
    assert not _cwd_relative_paths('Path(__file__).parent / "scripts"\n', "ok.py")

    for source in (
        "import jnwb\nassert REPO_ROOT in Path(jnwb.__file__).parents\n",
        "import jnwb.connectivity as C\n"
        "assert os.path.abspath(C.__file__).startswith(here)\n",
        "import jnwb\nPACKAGE_ROOT = pathlib.Path(jnwb.__file__).resolve().parent\n"
        "def test():\n    here = pathlib.Path(__file__).resolve().parent.parent\n"
        "    assert PACKAGE_ROOT == (here / 'jnwb').resolve()\n",
    ):
        assert _checkout_provenance_asserts(source, "old.py"), f"not seen: {source!r}"
    for source in (
        "import jnwb\nassert record.path == jnwb.__file__\n",
        "from jnwb import paths\n"
        "assert paths.PACKAGE_ROOT == Path(paths.__file__).resolve().parent.parent\n",
    ):
        assert not _checkout_provenance_asserts(source, "ok.py"), (
            f"a comparison that holds for an installed copy too was flagged: {source!r}"
        )


#: The one module allowed to assert which `jnwb` is under test. It is the designated outer
#: harness: it reads `JNWB_EXPECTED_PACKAGE_ROOT`, so it qualifies an installed copy as readily
#: as the working tree. Any other module asserting provenance pins the suite to the checkout.
PROVENANCE_HARNESS = "test_import_provenance.py"

#: How an assertion places a module under a directory. Equality is left out on purpose: the
#: quickstart prints the jnwb it ran and a Provenance record carries the path it observed, and
#: both compare `__file__` against another runtime value that holds for an installed copy too.
#: Root names match as whole identifiers, so `PACKAGE_ROOT` -- the package's own location, which
#: moves with an installed copy -- is not read as the checkout.
_CONTAINMENT = re.compile(
    r"\b(REPO_ROOT|ROOT|ROOT_DIR|_ROOT)\b|show-toplevel|\.startswith\(|\.is_relative_to\(|\.parents\b"
)


def _jnwb_bound_names(tree: ast.Module) -> set[str]:
    """Every local name an import binds to jnwb or one of its submodules."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "jnwb" or alias.name.startswith("jnwb."):
                    names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module == "jnwb" or node.module.startswith("jnwb."):
                names.update(alias.asname or alias.name for alias in node.names)
    return names


#: The test module's own location: `__file__` not preceded by a name and a dot.
_OWN_FILE = re.compile(r"(?<![\w.])__file__")


def _names_pattern(names: set[str]) -> "re.Pattern[str] | None":
    return re.compile(r"\b(" + "|".join(map(re.escape, sorted(names))) + r")\b") if names else None


def _checkout_provenance_asserts(source: str, name: str) -> list[str]:
    """Asserts that a jnwb module's `__file__` sits under a directory, however it is spelled.

    Names are followed one assignment deep in both directions: a name bound from a jnwb
    `__file__` stands for it, and a name bound from the test's own `__file__` stands for the
    checkout. `PACKAGE_ROOT = Path(jnwb.__file__)...` compared with `here / "jnwb"` reached the
    installed-wheel CI leg on 2026-09-23 through exactly that indirection.
    """
    tree = ast.parse(source)
    watched = {f"{bound}.__file__" for bound in _jnwb_bound_names(tree) | {"jnwb"}}
    aliases: set[str] = set()
    checkout: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = ast.unparse(node.value)
            names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if any(w in value for w in watched):
                aliases |= names
            elif _OWN_FILE.search(value):
                checkout |= names
    alias_re, checkout_re = _names_pattern(aliases), _names_pattern(checkout)
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        rendered = ast.unparse(node.test)
        mentions = any(w in rendered for w in watched) or bool(alias_re and alias_re.search(rendered))
        pinned = (
            _CONTAINMENT.search(rendered)
            or _OWN_FILE.search(rendered)
            or (checkout_re and checkout_re.search(rendered))
        )
        if mentions and pinned:
            offenders.append(f"{name}:{node.lineno} asserts jnwb resolves under the checkout root")
    return offenders


def test_no_test_module_rebinds_the_front_of_sys_path() -> None:
    """`sys.path.insert(0, ...)` is one spelling of forcing the import; these are the others.

    Ruled 2026-09-19. The rule is not "append rather than prepend" -- that is a proxy. The
    invariant is that a test inspects the installation it was pointed at and does not choose one:

        tests inspect the selected installation; tests do not select the installation

    Subprocess environments are deliberately excluded. Six modules set `PYTHONPATH` when spawning
    a child, and that is the child choosing what to measure, which is the point of those probes.
    What is forbidden is changing what *this* session imports.
    """
    offenders = []
    for module in _test_modules():
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            # sys.path[0] = something
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Subscript)
                        and ast.unparse(target.value) == "sys.path"
                        and ast.unparse(target.slice) == "0"
                    ):
                        offenders.append(f"{module.name}:{node.lineno} assigns sys.path[0]")
                    # sys.path = [...] + sys.path
                    if ast.unparse(target) == "sys.path" and isinstance(node.value, ast.BinOp):
                        offenders.append(
                            f"{module.name}:{node.lineno} rebinds sys.path by concatenation"
                        )
    assert not offenders, (
        "these modules choose the installation instead of inspecting the selected one: "
        f"{offenders}"
    )


def test_only_the_designated_harness_asserts_which_jnwb_is_under_test() -> None:
    """A module-level `assert ... in jnwb.__file__.parents` makes an installed run impossible.

    This is the defect that produced the rule: two modules written on 2026-09-19 asserted the
    package resolved to the working tree, which is true of a checkout run and false of exactly
    the run the suite exists to support. Provenance belongs in one place that knows both modes.
    """
    offenders = []
    for module in _test_modules():
        if module.name == PROVENANCE_HARNESS:
            continue
        offenders += _checkout_provenance_asserts(module.read_text(encoding="utf-8"), module.name)
    assert not offenders, (
        f"only {PROVENANCE_HARNESS} may assert which jnwb is under test, because it is the one "
        f"module that honours JNWB_EXPECTED_PACKAGE_ROOT and so works in both modes: {offenders}"
    )


def test_the_designated_harness_still_exists_and_supports_both_modes() -> None:
    """The two rules above point at one module. A pointer file goes stale without erroring."""
    harness = TESTS / PROVENANCE_HARNESS
    assert harness.is_file(), f"{PROVENANCE_HARNESS} is named as the provenance harness and is gone"
    source = harness.read_text(encoding="utf-8")
    assert "JNWB_EXPECTED_PACKAGE_ROOT" in source, (
        f"{PROVENANCE_HARNESS} no longer reads JNWB_EXPECTED_PACKAGE_ROOT, so it can no longer "
        "qualify an installed copy, and the exemption above has nothing behind it"
    )
