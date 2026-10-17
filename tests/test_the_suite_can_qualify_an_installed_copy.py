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


def _sys_aliases(tree: ast.Module) -> set[str]:
    """Local names bound to the `sys` module (`import sys as _s`)."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sys":
                    names.add(alias.asname or "sys")
    return names


def _sys_path_from_names(tree: ast.Module) -> set[str]:
    """Local names bound to `sys.path` itself (`from sys import path`)."""
    names = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module == "sys"
        ):
            for alias in node.names:
                if alias.name == "path":
                    names.add(alias.asname or "path")
    return names


def _is_sys_path_target(expr: ast.AST, sys_names: set[str], from_names: set[str]) -> bool:
    """`sys.path` however the module spells it: attribute or from-imported name."""
    return _is_sys_path(expr, sys_names) or (
        isinstance(expr, ast.Name) and expr.id in from_names
    )


def _inserted_target_ok(inserted: ast.AST) -> bool:
    """The one permitted prepend: a checkout-only directory with no parent traversal.

    Read from the syntax tree, not the text: a variable merely named `ROOT_scripts_dir`
    reads as a scripts prepend while resolving to the checkout, so a `..` forfeits the
    exemption. Only a string literal `"scripts"` joined as a path component qualifies.
    """
    segments = []
    for node in ast.walk(inserted):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            segments += node.value.replace("\\", "/").split("/")
    return any(name in segments for name in CHECKOUT_ONLY) and not any(
        ".." in s for s in segments
    )


def _is_sys_path(value: ast.AST, sys_names: set[str]) -> bool:
    """`sys.path` however the module spells `sys`."""
    return (
        isinstance(value, ast.Attribute)
        and value.attr == "path"
        and isinstance(value.value, ast.Name)
        and value.value.id in sys_names
    )


def _checkout_prepend_inserts(source: str, name: str) -> list[str]:
    """Every `sys.path.insert(i, X)` that can shadow the package under test.

    Any index, not only zero, through a `sys` alias or a `from sys import path` name,
    and past the `scripts/..` evasion.
    """
    tree = ast.parse(source)
    sys_names = _sys_aliases(tree) | {"sys"}
    from_names = _sys_path_from_names(tree)
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "insert"):
            continue
        if not _is_sys_path_target(func.value, sys_names, from_names):
            continue
        if len(node.args) > 1 and _inserted_target_ok(node.args[1]):
            continue
        inserted = ast.unparse(node.args[1]) if len(node.args) > 1 else ""
        at = ast.unparse(node.args[0]) if node.args else "?"
        offenders.append(f"{name}:{node.lineno} inserts {inserted} at sys.path[{at}]")
    return offenders


def _sys_path_rebinds(source: str, name: str) -> list[str]:
    """The other spellings of choosing the installation.

    Slice assignment (`sys.path[:0] = [ROOT]`, `sys.path[0:0] = ...`), rebinding
    (`sys.path = [ROOT] + sys.path`), in-place extension (`sys.path += [ROOT]`),
    and each through a `sys` alias or a `from sys import path` name. An assignment
    to a subscript of `sys.path` with any slice, and any rebinding of `sys.path`
    itself, puts a chosen directory ahead of the package under test.
    """
    tree = ast.parse(source)
    sys_names = _sys_aliases(tree) | {"sys"}
    from_names = _sys_path_from_names(tree)
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AugAssign) and _is_sys_path_target(
            node.target, sys_names, from_names
        ):
            offenders.append(f"{name}:{node.lineno} aug-assigns {ast.unparse(node.target)}")
            continue
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Subscript) and _is_sys_path_target(
                target.value, sys_names, from_names
            ):
                offenders.append(f"{name}:{node.lineno} assigns {ast.unparse(target)}")
            elif (
                isinstance(target, ast.Attribute)
                and _is_sys_path_target(target, sys_names, from_names)
            ):
                # A bare `path = [...]` on a from-imported name rebinds only the
                # local, leaving `sys.path` itself alone, so only the attribute
                # form counts as rebinding the installation.
                offenders.append(f"{name}:{node.lineno} rebinds {ast.unparse(target)}")
    return offenders


def _test_modules() -> list[Path]:
    modules = sorted(TESTS.glob("test_*.py"))
    assert len(modules) > 50, f"only {len(modules)} test modules found; the glob is wrong"
    init = TESTS / "__init__.py"
    if init.is_file() and init not in modules:
        # A plant here runs at every collection before any test module; the glob above
        # does not reach it.
        modules = sorted(modules + [init])
    return modules


def test_no_test_module_puts_the_checkout_ahead_of_the_package_under_test() -> None:
    """`sys.path.insert(0, REPO_ROOT)` re-shadows the installed copy for the whole session.

    Read from the syntax tree, not by text search: `test_connectivity.py` builds the same
    call as a string for a subprocess probe, and a grep would read that as a call.
    """
    offenders = []
    for module in _test_modules():
        source = module.read_text(encoding="utf-8")
        offenders += _checkout_prepend_inserts(source, module.name)
    assert not offenders, (
        "these modules prepend a directory that can shadow the package under test; append "
        f"instead: {offenders}"
    )


def _unguarded_prepends(source: str, name: str) -> list[str]:
    """`sys.path.insert(0, X)` not directly under `if X not in sys.path:`.

    A script prepends the checkout so that its command line measures the checkout's jnwb. The
    suite imports those scripts and calls their functions in-process, and there an unguarded
    prepend re-shadows the installed copy for every test that runs after it, in that worker
    only: `reconstruct_state.build()` did exactly that on the installed-wheel CI leg of
    2026-09-28. Guarded, the prepend is a no-op inside the suite, whose test modules have
    already appended the root before importing anything from `scripts`.
    """
    tree = ast.parse(source)
    sys_names = _sys_aliases(tree) | {"sys"}
    from_names = _sys_path_from_names(tree)
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (
            isinstance(test, ast.Compare)
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.NotIn)
            and (
                ast.unparse(test.comparators[0]) == "sys.path"
                or (
                    isinstance(test.comparators[0], ast.Name)
                    and test.comparators[0].id in from_names
                )
            )
        ):
            continue
        for stmt in node.body:
            call = stmt.value if isinstance(stmt, ast.Expr) else None
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            if not _is_sys_path_target(call.func.value, sys_names, from_names):
                continue
            wanted = ast.unparse(test.left)
            args = [ast.unparse(a) for a in call.args]
            if call.func.attr == "insert" and len(args) == 2 and args[1] == wanted:
                guarded.add(id(call))
            elif call.func.attr == "append" and args == [wanted]:
                guarded.add(id(call))
            elif call.func.attr == "extend" and args in ([wanted], [f"[{wanted}]"]):
                guarded.add(id(call))
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if not _is_sys_path_target(node.func.value, sys_names, from_names):
                continue
            if id(node) in guarded:
                continue
            if node.func.attr == "insert" and len(node.args) > 1:
                if _inserted_target_ok(node.args[1]):
                    continue
                at = ast.unparse(node.args[0]) if node.args else "?"
                offenders.append(
                    f"{name}:{node.lineno} prepends {ast.unparse(node.args[1])} "
                    f"at [{at}] unconditionally"
                )
                continue
            if node.func.attr in ("append", "extend") and node.args:
                if _inserted_target_ok(node.args[0]):
                    continue
                offenders.append(
                    f"{name}:{node.lineno} {node.func.attr}s "
                    f"{ast.unparse(node.args[0])} unconditionally"
                )
                continue
            continue
        if isinstance(node, ast.AugAssign) and _is_sys_path_target(
            node.target, sys_names, from_names
        ):
            offenders.append(
                f"{name}:{node.lineno} aug-assigns {ast.unparse(node.target)} unconditionally"
            )
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and _is_sys_path_target(
                    target.value, sys_names, from_names
                ):
                    offenders.append(
                        f"{name}:{node.lineno} assigns {ast.unparse(target)} unconditionally"
                    )
    return offenders


#: Trees whose Python files the suite imports or executes in-process. `docs/` is here because
#: `test_figure_form.py` executes `docs/generate_figures.py`, whose unconditional prepend was the
#: route by which the checkout still reached the front of `sys.path` on the installed-wheel leg
#: after `reconstruct_state.build()` was guarded. `examples/` has its own opt-out guard, pinned
#: by `test_every_example_guard_stands_aside_for_a_deliberate_installed_run`.
IN_PROCESS_TREES = ("scripts", "docs")


def test_no_script_prepends_the_checkout_unconditionally() -> None:
    """Every Python file in those trees, because any of them can be loaded by a test."""
    scripts = sorted(p for tree in IN_PROCESS_TREES for p in (ROOT / tree).rglob("*.py"))
    assert len(scripts) > 10, f"only {len(scripts)} scripts found; the glob is wrong"
    assert (ROOT / "docs" / "generate_figures.py") in scripts, "docs/ is no longer scanned"
    offenders = []
    for script in scripts:
        offenders += _unguarded_prepends(
            script.read_text(encoding="utf-8"), script.relative_to(ROOT).as_posix()
        )
    assert not offenders, (
        "these prepend to sys.path even when the directory is already on it, which inside "
        f"the suite puts the checkout ahead of the package under test: {offenders}"
    )


_REPO_DIRS = ("skills", "docs", "examples", "scripts", "artifacts", "tests", "jnwb")


def _cwd_relative_paths(source: str, name: str) -> list[str]:
    """A repository directory named as a string where a path is built.

    `Path("skills/x")` and `Path("skills") / "x"` alike: a bare directory name is the
    root. So are `open("docs/x")`, `os.path.join("scripts", ...)`, `pathlib.Path(...)`
    spelled through the module, and a `./` prefix (`Path("./skills")`), which still
    resolves only when pytest runs from the root.
    """
    offenders = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and node.args):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            kind = func.id
        elif isinstance(func, ast.Attribute):
            kind = func.attr
        else:
            continue
        if kind not in ("Path", "open", "join"):
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            parts = [p for p in first.value.replace("\\", "/").split("/") if p not in ("", ".")]
            while parts and parts[0] == "..":
                parts.pop(0)
            if parts and parts[0] in _REPO_DIRS:
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
    assert len(EXAMPLES) == 12, f"{len(EXAMPLES)} examples found, expected 12"
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


def _scripts_the_tests_import() -> list[str]:
    """`scripts.x` modules any test module imports, however it spells the import."""
    names: set[str] = set()
    for module in _test_modules():
        source = module.read_text(encoding="utf-8")
        names.update(re.findall(r"\bimport scripts\.([\w.]+)", source))
        for group in re.findall(r"\bfrom scripts import ([\w ,]+)", source):
            names.update(part.split()[0] for part in group.split(",") if part.strip())
    return sorted(names)


def test_every_script_a_test_imports_accepts_the_installed_copy(tmp_path: Path) -> None:
    """The wheel leg's condition: jnwb is already imported from elsewhere, the variable names it.

    A script whose guard compares `jnwb.__file__` with the checkout alone refuses there, and a
    refusal at import time is a collection error that stops the whole leg
    (`scripts/vflip2_sensitivity.py` on bafcbbca, `scripts/vflip2_recovery.py` on c761b2ff).
    `_checkout_jnwb()`, where a script defines it, is called too.
    """
    import shutil

    site = tmp_path / "site"
    shutil.copytree(ROOT / "jnwb", site / "jnwb", ignore=shutil.ignore_patterns("__pycache__"))
    names = _scripts_the_tests_import()
    assert "vflip2_recovery" in names, names
    probe = textwrap.dedent(f"""
        import importlib, pathlib, sys
        import jnwb
        site = pathlib.Path({str(site)!r}).resolve()
        assert site in pathlib.Path(jnwb.__file__).resolve().parents, jnwb.__file__
        sys.path.append({str(ROOT)!r})
        failed = []
        for name in {names!r}:
            try:
                module = importlib.import_module("scripts." + name)
                if hasattr(module, "_checkout_jnwb"):
                    module._checkout_jnwb()
            except BaseException as exc:
                failed.append(f"{{name}}: {{type(exc).__name__}}: {{exc}}")
        print("\\n".join(failed))
    """)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(site)
    env["JNWB_EXPECTED_PACKAGE_ROOT"] = str(site)
    result = subprocess.run([sys.executable, "-c", probe], cwd=tmp_path, capture_output=True,
                            text=True, timeout=600, env=env)
    assert result.returncode == 0, result.stderr[-2000:]
    failed = result.stdout.strip()
    assert not failed, f"these scripts refuse the copy JNWB_EXPECTED_PACKAGE_ROOT names:\n{failed}"

    # Run by path, as a test's subprocess does, with nothing imported yet: a script that still
    # prepends the checkout imports it and refuses it (test_vflip2_recovery's caller test on
    # 15b4b5aa), or worse, measures it while the variable names the installed copy.
    paths = {n: ROOT / "scripts" / (n.replace(".", "/") + ".py") for n in names}
    guarded = [n for n in names if "jnwb.__file__" in paths[n].read_text(encoding="utf-8")]
    assert "vflip2_recovery" in guarded, guarded
    by_path = []
    for name in guarded:
        script = paths[name]
        run = textwrap.dedent(f"""
            import pathlib, runpy, sys
            ns = runpy.run_path({str(script)!r}, run_name="_probe_")
            if "_checkout_jnwb" in ns:
                ns["_checkout_jnwb"]()
            import jnwb
            site = pathlib.Path({str(site)!r}).resolve()
            assert site in pathlib.Path(jnwb.__file__).resolve().parents, jnwb.__file__
        """)
        result = subprocess.run([sys.executable, "-c", run], cwd=tmp_path, capture_output=True,
                                text=True, timeout=600, env=env)
        if result.returncode != 0:
            by_path.append(f"{name}: {(result.stderr.strip().splitlines() or ['?'])[-1]}")
    assert not by_path, "run by path, these scripts do not use the named copy:\n" + "\n".join(by_path)


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

    # The prepend `reconstruct_state.build()` carried until 2026-09-28, and the guarded form.
    old_build = "import sys\ndef build():\n    sys.path.insert(0, str(REPO_ROOT))\n"
    assert _unguarded_prepends(old_build, "old.py"), "the unguarded prepend was not seen"
    assert _unguarded_prepends(
        "import sys\nsys.path.append(str(REPO_ROOT))\n", "old.py"
    ), "an unguarded append chooses the installation just as an unguarded prepend does"
    for source in (
        "import sys\nif str(REPO_ROOT) not in sys.path:\n    sys.path.insert(0, str(REPO_ROOT))\n",
        "import sys\nif str(REPO_ROOT) not in sys.path:\n    sys.path.append(str(REPO_ROOT))\n",
    ):
        assert not _unguarded_prepends(source, "ok.py"), f"flagged: {source!r}"
    # A guard on one directory does not license a prepend of another.
    assert _unguarded_prepends(
        "import sys\nif str(A) not in sys.path:\n    sys.path.insert(0, str(B))\n", "old.py"
    ), "a mismatched guard was accepted"

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
#: moves with an installed copy -- is not read as the checkout. `cwd`/`getcwd` pin the run to
#: the directory pytest started in.
_CONTAINMENT = re.compile(
    r"\b(REPO_ROOT|ROOT|ROOT_DIR|_ROOT|cwd|getcwd)\b|show-toplevel|\.startswith\(|\.is_relative_to\(|\.parents\b"
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
    bound = _jnwb_bound_names(tree) | {"jnwb"}
    watched = {f"{name}.__file__" for name in bound} | {f"{name}.__path__" for name in bound}
    jnwb_re = _names_pattern(bound)
    aliases: set[str] = set()
    checkout: set[str] = set()
    # One pass per indirection level: `b = a` after `a = jnwb.__file__` needs two,
    # so iterate to a fixpoint rather than reading each assignment once.
    for _ in range(10):
        alias_re, checkout_re = _names_pattern(aliases), _names_pattern(checkout)
        grown = False
        for node in ast.walk(tree):
            targets: list[str] = []
            value = ""
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        targets.append(target.id)
                    elif isinstance(target, ast.Tuple):
                        targets.extend(
                            e.id for e in target.elts if isinstance(e, ast.Name))
                value = ast.unparse(node.value)
            elif (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.value is not None
            ):
                targets = [node.target.id]
                value = ast.unparse(node.value)
            else:
                continue
            if not targets or not value:
                continue
            mentions = (
                any(w in value for w in watched)
                or bool(alias_re and alias_re.search(value))
                or bool(jnwb_re and "getfile(" in value and jnwb_re.search(value))
            )
            if mentions and not set(targets) <= aliases:
                aliases |= set(targets)
                grown = True
            elif _OWN_FILE.search(value) and not set(targets) <= checkout:
                checkout |= set(targets)
                grown = True
        if not grown:
            break
    alias_re, checkout_re = _names_pattern(aliases), _names_pattern(checkout)
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        rendered = ast.unparse(node.test)
        mentions = (
            any(w in rendered for w in watched)
            or bool(alias_re and alias_re.search(rendered))
            or bool(jnwb_re and "getfile(" in rendered and jnwb_re.search(rendered))
        )
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
        offenders += _sys_path_rebinds(module.read_text(encoding="utf-8"), module.name)
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


@pytest.fixture(scope="session", autouse=True)
def _path_order_holds_at_session_end():
    """The path-order assertion also runs at session end (prepend-reach).

    `test_import_provenance.py::test_no_second_jnwb_shadows_the_one_under_test` catches a
    prepend only when it runs after it in the same worker. A module that re-shadows the
    package under test partway through the session would pass that test by running
    earlier, so the same order is asserted again after the last test. It reads `sys.path`
    entries, never the imported package, so it holds for an installed copy too.
    """
    yield
    override = os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT")
    expected = (Path(override).resolve() / "jnwb" if override else (ROOT / "jnwb")).resolve()
    found = []
    for entry in sys.path:
        if not entry:
            continue
        candidate = Path(entry).resolve() / "jnwb" / "__init__.py"
        if candidate.is_file():
            found.append(candidate.parent)
    assert found, "no importable jnwb was found on sys.path at all"
    assert found[0] == expected, (
        f"the first importable jnwb on sys.path at session end is {found[0]}, which shadows "
        f"{expected}: a module re-shadowed the package under test mid-session"
    )


def test_the_module_glob_reaches_the_package_init() -> None:
    """A plant in `tests/__init__.py` runs at every collection before any test module, and
    the `test_*.py` glob does not reach it."""
    assert (TESTS / "__init__.py") in _test_modules()


#: Every archived spelling the scanners missed, and every equivalent form added since.
#: Each is a fixture the scanner must flag, read as source the way
#: the live scans read their files. Snippets live in string literals, which the scanners
#: do not parse as code.
ARCHIVED_PREPEND_FORMS = [
    "import sys\nsys.path[:0] = [str(ROOT)]\n",
    "import sys\nsys.path.insert(1, str(ROOT))\n",
    "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path('x') / 'scripts' / '..'))\n",
    "import sys as _s\n_s.path.insert(0, str(ROOT))\n",
    "import sys\nsys.path[0:0] = [str(ROOT)]\n",
    "import sys\nsys.path = [str(ROOT)] + sys.path\n",
    "import sys as s\ns.path.insert(0, str(ROOT))\n",
    "import sys\nsys.path.insert(2, str(ROOT))\n",
    "import sys\nsys.path.insert(0, str(ROOT_scripts_dir))\n",
    "from sys import path\npath.insert(0, str(ROOT))\n",
    "import sys\nsys.path += [str(ROOT)]\n",
    "import sys\nsys.path.extend([str(ROOT)])\n",
    "import sys\nsys.path.append(str(ROOT))\n",
]

ARCHIVED_PROVENANCE_FORMS = [
    "import jnwb\nfrom pathlib import Path\nroot: Path = Path(jnwb.__file__).parent\n"
    "def t():\n    assert root == Path(__file__).parent\n",
    "import jnwb\na = jnwb.__file__\nb = a\ndef t():\n    assert str(b).startswith('/x')\n",
    "import jnwb\ndef t():\n    assert str(ROOT) in str(list(jnwb.__path__))\n",
    "import inspect\nimport jnwb\ndef t():\n    assert str(ROOT) in inspect.getfile(jnwb)\n",
    "import jnwb\nfrom pathlib import Path\n"
    "def t():\n    assert Path(jnwb.__file__).parent == Path.cwd()\n",
    "import jnwb\na, b = jnwb.__file__, 1\ndef t():\n    assert str(a).startswith('/x')\n",
]

ARCHIVED_CWD_FORMS = [
    "import pathlib\npathlib.Path('skills/..').exists()\n",
    "open('docs/index.md').read()\n",
    "from pathlib import Path\nPath('./skills').exists()\n",
    "import os\nos.path.join('scripts', 'x').upper()\n",
]


@pytest.mark.parametrize("source", ARCHIVED_PREPEND_FORMS)
def test_every_archived_prepend_form_is_flagged(source: str) -> None:
    """Each equivalent form of forcing the import is refused, not only `insert(0, ...)`."""
    assert _checkout_prepend_inserts(source, "probe.py") or _sys_path_rebinds(
        source, "probe.py") or _unguarded_prepends(source, "probe.py"), (
        f"no scanner flagged this prepend form: {source!r}")


@pytest.mark.parametrize("source", [
    "import sys\nsys.path.insert(0, str(ROOT / 'scripts'))\n",
    "import sys\nsys.path.insert(0, str(ROOT / \"scripts\"))\n",
])
def test_the_checkout_only_directory_prepend_is_left_alone(source: str) -> None:
    """The one permitted prepend: a checkout-only directory joined as a literal path
    component. No scanner may flag it, or the scripts' own imports fail the suite."""
    assert not _checkout_prepend_inserts(source, "ok.py"), f"flagged: {source!r}"
    assert not _sys_path_rebinds(source, "ok.py"), f"flagged: {source!r}"
    assert not _unguarded_prepends(source, "ok.py"), f"flagged: {source!r}"


@pytest.mark.parametrize("source", ARCHIVED_PROVENANCE_FORMS)
def test_every_archived_provenance_spelling_is_flagged(source: str) -> None:
    """Each spelling of asserting the checkout from a `jnwb` path is refused."""
    assert _checkout_provenance_asserts(source, "probe.py"), (
        f"the provenance scanner missed this spelling: {source!r}")


@pytest.mark.parametrize("source", ARCHIVED_CWD_FORMS)
def test_every_archived_cwd_relative_spelling_is_flagged(source: str) -> None:
    """Each spelling of reading the repository through the working directory is refused."""
    assert _cwd_relative_paths(source, "probe.py"), (
        f"the working-directory scanner missed this spelling: {source!r}")
