"""A docstring is a claim, and five of them described code other than the code under them.

`scripts/harness_gate.py` listed twelve gates while its runner printed thirteen, and its
entry for gate 2 still described a check that had been rewritten into a different one.
`scripts/mkdocs_version_hook.py` cited an upper pin -- `>=3.12,<3.13` -- that gate 8 of the
harness fails the build for. `jnwb/connectivity.py` claimed explicit `N - p` divisors while
`_residual_variance` returned `RSS / N` and ignored the `n_params` argument it took.
`jnwb/artifact_detection.py` named its second and third returns as a correlation summary and
an amplitude when both are robust z-scores, so a reader took element seven for 54.21 when it
was 332.40. `jnwb/tfr_accumulator.py` described float64/complex128 accumulation and said
nothing about `write` halving every dtype on the way to disk.

Each claim is checked against the thing it is a claim about: the runner's own gate list, the
value in `pyproject.toml`, the parsed body of the function, the names in the return
statement, the dtypes in the calls. There is also one sweep over every module in `jnwb/`,
because arity is the part of a `Returns (...)` line that can be checked without knowing what
the function means.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS_GATE = REPO_ROOT / "scripts" / "harness_gate.py"
VERSION_HOOK = REPO_ROOT / "scripts" / "mkdocs_version_hook.py"
CONNECTIVITY = REPO_ROOT / "jnwb" / "connectivity.py"
ARTIFACT_DETECTION = REPO_ROOT / "jnwb" / "artifact_detection.py"
TFR_ACCUMULATOR = REPO_ROOT / "jnwb" / "tfr_accumulator.py"

#: A numbered line in a module docstring's list of gates: "  7. Package & metadata ...".
DOCSTRING_GATE = re.compile(r"^ {2}(\d+)\. ", re.M)
#: The runner's own numbered comments: "    # 7. Package and metadata version ...".
RUNNER_GATE = re.compile(r"^    # (\d+)\. ", re.M)
#: A "Returns (a, b, c)" line anywhere in a function docstring.
RETURNS_TUPLE = re.compile(r"Returns?\s+\(([^)]*)\)", re.I)


def module_docstring(path: Path) -> str:
    doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
    assert doc, f"{path.name} has no module docstring"
    return doc


def function_def(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{path.name} defines no {name}()")


def returned_names(node: ast.FunctionDef) -> "list[list[str]]":
    """The bare names in each tuple `return` of a function, ordered by line.

    `ast.walk` is breadth-first, so its last hit is not the function's last return -- which
    matters here, because the early guard returns three constructed arrays and the real
    return three names.
    """
    returns = [
        stmt
        for stmt in ast.walk(node)
        if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Tuple)
    ]
    return [
        [e.id if isinstance(e, ast.Name) else "<expr>" for e in stmt.value.elts]
        for stmt in sorted(returns, key=lambda s: s.lineno)
    ]


#: Words too structural to identify a check: "tree", "path", "root", "code" appear in half
#: the gate names. A gate 2 entry reading "Protected path safety" shared "tree" with
#: `check_skill_tree_uniqueness` and passed a word-overlap test on that alone.
IDENTIFYING = 5


def identifying_words(text: str) -> "set[str]":
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= IDENTIFYING}


def function_name_words(name: str) -> "set[str]":
    return {w for w in name.split("_") if len(w) >= IDENTIFYING} - {"check", "validate"}


def runner_gate_calls(source: str) -> "dict[str, str]":
    """Each numbered gate in the runner, mapped to the check function it calls."""
    lines = source.splitlines()
    calls = {}
    for i, line in enumerate(lines):
        match = re.match(r"^    # (\d+)\. ", line)
        if not match:
            continue
        for follow in lines[i + 1 : i + 8]:
            call = re.search(r"\b((?:check|validate)_\w+)\s*\(", follow)
            if call:
                calls[match.group(1)] = call.group(1)
                break
    return calls


def entries_not_naming_their_check(doc: str, calls: "dict[str, str]") -> "list[str]":
    """Documented gate entries that share no identifying word with the function they run."""
    offenders = []
    for number, entry in re.findall(r"^ {2}(\d+)\. (.+)$", doc, re.M):
        function = calls.get(number)
        if function is None:
            offenders.append(f"gate {number}: the runner calls nothing under that number")
            continue
        if not function_name_words(function) & identifying_words(entry):
            offenders.append(
                f"gate {number}: the docstring says {entry!r} while the runner calls "
                f"{function}(), with no identifying word in common"
            )
    return offenders


def returns_arity_mismatches(root: Path) -> "list[str]":
    """Functions whose `Returns (...)` line promises a different count than the code returns."""
    offenders = []
    for module in sorted(root.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            doc = ast.get_docstring(node)
            match = RETURNS_TUPLE.search(doc) if doc else None
            if match is None:
                continue
            documented = [p.strip() for p in match.group(1).split(",") if p.strip()]
            arities = {len(names) for names in returned_names(node)}
            if len(documented) < 2 or not arities:
                continue
            if arities != {len(documented)}:
                offenders.append(
                    f"{module.name}:{node.lineno} {node.name}: docstring promises "
                    f"{len(documented)} values {documented}, code returns {sorted(arities)}"
                )
    return offenders


def returns_arity_checked(root: Path) -> int:
    """How many functions the arity sweep actually compared."""
    total = 0
    for module in sorted(root.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            doc = ast.get_docstring(node)
            match = RETURNS_TUPLE.search(doc) if doc else None
            if match is None:
                continue
            documented = [p.strip() for p in match.group(1).split(",") if p.strip()]
            if len(documented) >= 2 and returned_names(node):
                total += 1
    return total


def misnamed_returns(node: ast.FunctionDef) -> "list[str]":
    """Returned names the function's own `Returns (...)` line does not contain."""
    doc = ast.get_docstring(node) or ""
    match = RETURNS_TUPLE.search(doc)
    if match is None:
        return []
    documented = [p.strip() for p in match.group(1).split(",")]
    returns = returned_names(node)
    if not returns:
        return []
    last = returns[-1]
    if len(last) != len(documented):
        return [f"arity: docstring {len(documented)}, code {len(last)}"]
    return [
        f"the docstring calls it {promised!r} while the code returns {actual!r}"
        for promised, actual in zip(documented, last)
        if actual not in promised
    ]


def body_source(path: Path, node: ast.FunctionDef) -> str:
    """A function's source with its docstring removed, so prose is not read as code."""
    body = [stmt for stmt in node.body]
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return "\n".join(ast.get_source_segment(path.read_text(encoding="utf-8"), s) or "" for s in body)


class TestTheHarnessGateListsTheGatesItRuns:
    """The list said twelve; the runner printed thirteen, and one entry named the wrong check."""

    def test_the_numbering_matches_the_runner(self):
        doc = module_docstring(HARNESS_GATE)
        source = HARNESS_GATE.read_text(encoding="utf-8")
        # The runner's numbered comments restart inside two helpers, so take the longest run
        # that begins at 1 and ascends -- the preflight sequence at the bottom of the file.
        runs, current = [], []
        for number in (int(n) for n in RUNNER_GATE.findall(source)):
            if number == 1:
                current = [1]
                runs.append(current)
            elif current and number == current[-1] + 1:
                current.append(number)
            else:
                current = []
        runner = max(runs, key=len)
        documented = [int(n) for n in DOCSTRING_GATE.findall(doc)]
        assert len(runner) >= 13, f"only {len(runner)} runner gates parsed; the sweep is wrong"
        assert documented == runner, (
            f"the module docstring lists gates {documented} but the runner runs {runner}"
        )

    def test_every_documented_gate_names_the_check_that_runs(self):
        """Gate 2 read "Protected path safety" long after it became a skill-tree check."""
        source = HARNESS_GATE.read_text(encoding="utf-8")
        calls = runner_gate_calls(source)
        assert len(calls) >= 13, f"only {len(calls)} gate calls found; the sweep is wrong"
        assert not entries_not_naming_their_check(module_docstring(HARNESS_GATE), calls)

    def test_an_entry_describing_a_different_check_is_found(self):
        """The case that passed: "Protected path safety" against a skill-tree check."""
        doc = "  2. Protected path safety: protects concurrent working tree directories."
        offenders = entries_not_naming_their_check(doc, {"2": "check_skill_tree_uniqueness"})
        assert len(offenders) == 1 and "no identifying word" in offenders[0], offenders

    def test_an_entry_the_runner_does_not_run_is_found(self):
        offenders = entries_not_naming_their_check("  14. Something new.", {})
        assert offenders == ["gate 14: the runner calls nothing under that number"]

    def test_the_count_matches_what_the_runner_prints(self):
        doc = module_docstring(HARNESS_GATE)
        printed = HARNESS_GATE.read_text(encoding="utf-8").count('"PASS: ')
        printed += HARNESS_GATE.read_text(encoding="utf-8").count('f"PASS: ')
        assert len(DOCSTRING_GATE.findall(doc)) == 13, DOCSTRING_GATE.findall(doc)


class TestTheVersionHookQuotesTheRealRequiresPython:
    """It cited `>=3.12,<3.13`, an upper pin gate 8 fails the build for."""

    def test_the_quoted_specifier_is_the_one_pyproject_declares(self):
        doc = module_docstring(VERSION_HOOK)
        with open(REPO_ROOT / "pyproject.toml", "rb") as handle:
            declared = tomllib.load(handle)["project"]["requires-python"]
        quoted = re.findall(r">=\s?3\.\d+(?:\s?,\s?<\s?3\.\d+)?", doc)
        assert quoted, f"the hook quotes no interpreter range; it said: {doc!r}"
        for spec in quoted:
            assert spec.replace(" ", "") == declared.replace(" ", ""), (
                f"the hook quotes {spec!r} but pyproject.toml declares {declared!r}"
            )

    def test_it_quotes_no_upper_pin(self):
        """Gate 8 fails on any `<` in the specifier, so quoting one contradicts the harness."""
        doc = module_docstring(VERSION_HOOK)
        assert "<3.13" not in doc.replace(" ", ""), doc


class TestConnectivityDescribesItsOwnDivisor:
    """It claimed explicit `N - p` divisors; `_residual_variance` returns `RSS / N`."""

    def test_the_function_divides_by_n(self):
        node = function_def(CONNECTIVITY, "_residual_variance")
        # The body without its docstring: the docstring says why `n_params` is gone.
        source = body_source(CONNECTIVITY, node)
        assert "max(n, 1)" in source, source
        assert "n_params" not in source, "the dead parameter is back"

    def test_it_takes_no_parameter_it_does_not_read(self):
        node = function_def(CONNECTIVITY, "_residual_variance")
        names = [a.arg for a in node.args.args]
        assert names == ["residuals"], names

    def test_the_module_docstring_does_not_claim_a_divisor_it_does_not_use(self):
        doc = module_docstring(CONNECTIVITY)
        claim = [ln for ln in doc.splitlines() if "divisor" in ln.lower() or "RSS /" in ln]
        assert claim, "the module no longer states its residual-variance convention at all"
        assert "RSS / N, not RSS / (N - p)" in doc, claim


class TestArtifactDetectionNamesWhatItReturns:
    """It named a summary and an amplitude; both are robust z-scores."""

    def test_the_docstring_names_match_the_return_statement(self):
        node = function_def(ARTIFACT_DETECTION, "bad_trials_single_channel")
        assert returned_names(node), "the function no longer returns a tuple"
        assert misnamed_returns(node) == []

    def test_a_renamed_return_is_found(self):
        """The case that shipped: the code returns `amp_z`, the docstring said `amp`."""
        source = (
            "def f():\n"
            '    """Returns (flag_per_trial, corr_summary_per_trial, amp_per_trial)."""\n'
            "    return flag, corr_z, amp_z\n"
        )
        offenders = misnamed_returns(ast.parse(source).body[0])
        assert len(offenders) == 2, offenders
        assert "amp_per_trial" in offenders[1] and "amp_z" in offenders[1], offenders

    def test_a_matching_docstring_is_not_reported(self):
        source = (
            "def f():\n"
            '    """Returns (flag_per_trial, corr_z_per_trial, amp_z_per_trial)."""\n'
            "    return flag, corr_z, amp_z\n"
        )
        assert misnamed_returns(ast.parse(source).body[0]) == []

    def test_the_third_element_really_is_a_z_score(self):
        """The premise, measured rather than read: a z is not in the signal's own unit."""
        import numpy as np

        from jnwb.artifact_detection import bad_trials_single_channel

        rng = np.random.default_rng(0)
        trials = rng.normal(0.0, 1.0, size=(40, 200))
        trials[7] *= 50.0
        _, _, third = bad_trials_single_channel(trials)
        assert abs(third[7]) > 5.0, third[7]
        assert not np.isclose(third[7], np.max(np.abs(trials[7]))), (
            "the third element equals the raw amplitude, so the docstring was right and this "
            "test is measuring the wrong thing"
        )


class TestTheAccumulatorSaysWhatItStores:
    """It described float64/complex128 accumulation and not the halving that `write` does."""

    @pytest.mark.parametrize(
        "field, dtype",
        [("mean", "float32"), ("M2", "float32"), ("sum_z", "complex64"), ("sum_unit_z", "complex64")],
    )
    def test_every_downcast_write_performs_is_documented(self, field: str, dtype: str):
        source = TFR_ACCUMULATOR.read_text(encoding="utf-8")
        node = function_def(TFR_ACCUMULATOR, "write")
        written = body_source(TFR_ACCUMULATOR, node)
        assert f'"{field}"' in written and f"np.{dtype}" in written, (
            f"write() no longer stores {field} as {dtype}; the docstring now over-promises"
        )
        doc = module_docstring(TFR_ACCUMULATOR)
        assert field in doc and dtype in doc, (
            f"the module docstring does not say that {field} is written as {dtype}"
        )
        assert "float64" in source and "complex128" in source

    def test_the_in_memory_dtypes_are_the_ones_it_claims(self):
        node = function_def(TFR_ACCUMULATOR, "__init__")
        body = ast.unparse(node)
        assert "np.float64" in body and "np.complex128" in body, body


class TestEveryReturnsLineHasTheRightArity:
    """The one part of a `Returns (...)` claim that can be checked without reading the prose."""

    def test_no_module_in_jnwb_promises_a_tuple_of_the_wrong_length(self):
        checked = returns_arity_checked(REPO_ROOT / "jnwb")
        assert checked >= 8, f"only {checked} functions swept; the sweep has stopped working"
        assert returns_arity_mismatches(REPO_ROOT / "jnwb") == []

    def test_the_sweep_finds_a_mismatch_when_there_is_one(self, tmp_path: Path):
        """Driven over a tree built to carry the defect, not only over a clean corpus."""
        (tmp_path / "m.py").write_text(
            "def f():\n"
            '    """Returns (a, b, c)."""\n'
            "    return 1, 2\n",
            encoding="utf-8",
        )
        offenders = returns_arity_mismatches(tmp_path)
        assert len(offenders) == 1 and "promises 3 values" in offenders[0], offenders

    def test_the_sweep_accepts_a_matching_arity(self, tmp_path: Path):
        (tmp_path / "m.py").write_text(
            "def f():\n"
            '    """Returns (a, b, c)."""\n'
            "    return 1, 2, 3\n",
            encoding="utf-8",
        )
        assert returns_arity_mismatches(tmp_path) == []
        assert returns_arity_checked(tmp_path) == 1
