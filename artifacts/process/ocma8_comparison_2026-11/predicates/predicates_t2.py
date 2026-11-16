r"""Predicates for experiment task t2: one markdown table cell splitter under scripts/ (jnwb item 17-95).

Usage: python predicates_t2.py <tree> <baseline tree>

Prints one line per check (D1, D2, P3, P4, C1..C5), then `PRIMARY automated k/2 CONSTRAINTS j/5 STRUCTURE
adjudicated`. Exit 0 when it runs to the end, 2 on a usage error. Standard library only (P3, P4 and C5 run
subprocesses); every subprocess runs with cwd=<tree>. History: t2_amendment/AMENDMENT.md.

Primary measures of t2 (amendment 3, Hamm 2026-11-16): S, structural consolidation, judged by independent
blind adjudication against `t2_structure_rubric.md` and recorded in the ledger, never computed here; P3 and
P4, behaviour, computed here.

D1  diagnostic, unscored: what `t2_structure.py` reads from the AST about consolidation (PASS, FAIL or
D2  AMBIGUOUS) and about removal. Review 3 showed these accept unconsolidated trees: they are an observation
    for the record, they enter no score, and no adjudicator sees them.
P3  behaviour through every affected reader: `t2_differential.py` (beside this script) generates table rows
    from DIFF_SEED and compares what each reader's entry point returns in <tree> and in <baseline tree>:
    preserved mode (rows without an escaped pipe; the tree must equal the baseline) and corrected mode (rows
    with escaped pipes; the tree must equal the declared contract). PASS when it exits 0 with DIFF_READERS
    readers, more than 0 inputs and 0 mismatches in both modes, and no reader whose baseline results are all
    empty (a WARN line). Generator revision 2 adds header escape, blockquote lead, long row, whitespace
    padding and wide table. The exploratory bucket (any header or row ending in an escaped pipe, open or
    tight) is printed, unscored.
    Every mismatching input is written to the file named in the line.
P4  the corrected behaviour holds at each reader's entry point: pytest on `t2_corrected_test.py` (beside
    this script) exits 0 with exactly CORRECTED_TESTS passed (an escaped pipe inside a cell changes neither
    the rows nor the cells read). Independent of the refactor's structure; FAIL at the baseline.
C5  the preserved behaviour holds: pytest on `../accept/t2_preserved_test.py` exits 0 with exactly
    PRESERVED_TESTS passed. PASS at the baseline and on a valid refactor.
C1  `python scripts/harness_gate.py` exits 0 and its last line reads `ALL HARNESS GATES PASSED. N of M gates
    executed.` with N == M, and no FAIL, ERROR, NOT RUN or OVERALL line.
C2  `python -m compileall -q scripts` exits 0, and no file under scripts/ loads a BASELINE_NAMES name that
    the file neither defines nor imports (ast; scope-insensitive: any binding in the file counts).
C3  the C1 gate run changes no tracked non-.py file: no non-.py entry is new in `git status --porcelain`
    (listing before and after the run; entries already listed before are not blamed on the gate), and the
    sha256 of every tracked non-.py file is unchanged across the run.
C4  every file that differs from the baseline commit (tracked diff plus untracked, not ignored) lies under
    scripts/ or tests/. An empty set of differing files is FAIL: nothing was examined.
"""

import ast
import hashlib
import os
import pathlib
import re
import subprocess
import sys

SELF = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(SELF.parent))
import t2_structure  # noqa: E402

#: Names of the baseline splitter definitions (C2).
BASELINE_NAMES = frozenset(name for _, name in t2_structure.DEF_SITES)
GATE_PASS = re.compile(r"ALL HARNESS GATES PASSED\. (\d+) of (\d+) gates executed\.")
GATE_TIMEOUT_S = 540
#: Behavioural tests: file and the exact number of tests that must pass.
CORRECTED = (SELF.parent / "t2_corrected_test.py", 6)
PRESERVED = (SELF.parent.parent / "accept" / "t2_preserved_test.py", 56)
PYTEST_SUMMARY = re.compile(r"(\d+) (passed|failed|error|errors|skipped|xfailed|xpassed|deselected)\b")
PYTEST_TIMEOUT_S = 300
#: Differential test (P3): script, generation seed, number of reader entry points it must exercise.
DIFFERENTIAL = SELF.parent / "t2_differential.py"
DIFF_SEED = 2026111600
DIFF_READERS = 13
DIFF_LINE = re.compile(r"^DIFF (preserved|corrected) readers=(\d+) inputs=(\d+) mismatches=(\d+)\s*$", re.M)
DIFF_EXPLORATORY = re.compile(r"^DIFF exploratory inputs=(\d+) mismatches=(\d+)\s*$", re.M)
DIFF_TIMEOUT_S = 600
CHILD_ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")


def text(data):
    return data.decode("utf-8", errors="replace")


def run(cmd, cwd, timeout, env=None):
    return subprocess.run(cmd, cwd=str(cwd), env=env or CHILD_ENV, stdin=subprocess.DEVNULL,
                          capture_output=True, timeout=timeout)


def git(path, *args):
    return run(["git", "-C", str(path), *args], path, 120)


def script_files(tree):
    return sorted(p for p in (tree / "scripts").rglob("*.py") if "__pycache__" not in p.parts)


def tracked_entries(tree):
    """Tracked entries of `git status --porcelain` as (status, path); untracked files excluded."""
    proc = git(tree, "status", "--porcelain", "-z", "--untracked-files=no")
    if proc.returncode != 0:
        raise RuntimeError(f"git status rc={proc.returncode}")
    tokens = text(proc.stdout).split("\0")
    entries, i = set(), 0
    while i < len(tokens):
        token = tokens[i]
        i += 1
        if len(token) < 4:
            continue
        status, path = token[:2], token[3:]
        if "R" in status or "C" in status:
            i += 1  # a rename or copy is followed by its original path
        entries.add((status, path))
    return entries


def tracked_non_python(tree):
    proc = git(tree, "ls-files", "-z")
    if proc.returncode != 0:
        raise RuntimeError(f"git ls-files rc={proc.returncode}")
    return [p for p in text(proc.stdout).split("\0") if p and not p.endswith(".py")]


def digests(tree, paths):
    out = {}
    for rel in paths:
        try:
            out[rel] = hashlib.sha256((tree / rel).read_bytes()).hexdigest()
        except OSError:
            out[rel] = None  # deleted or unreadable: compared as None
    return out


def gate_run(tree):
    """One run of the harness gate, with the tracked-file state taken before and after it."""
    before_entries = tracked_entries(tree)
    paths = tracked_non_python(tree)
    before = digests(tree, paths)
    proc = run([sys.executable, "scripts/harness_gate.py"], tree, GATE_TIMEOUT_S)
    return {"proc": proc, "before_entries": before_entries, "after_entries": tracked_entries(tree),
            "paths": paths, "before": before, "after": digests(tree, paths)}


def check_structure(tree, base):
    """P1 and P2 as (verdict, line); a tree the AST cannot read is AMBIGUOUS, never a rejection."""
    try:
        p1, p2, n_sites, n_anchors = t2_structure.evaluate(t2_structure.Tree(tree), t2_structure.Tree(base))
    except Exception as exc:  # not evaluated: to adjudication
        why = f"cannot evaluate: {type(exc).__name__}: {exc}"
        return ("AMBIGUOUS", f"P1 AMBIGUOUS {why}"), ("AMBIGUOUS", f"P2 AMBIGUOUS {why}")
    return ((p1[0], f"P1 {p1[0]} {p1[1]} [{n_sites} sites, {n_anchors} anchors]"),
            (p2[0], f"P2 {p2[0]} {p2[1]}"))


def check_p3(tree, base):
    out = pathlib.Path(f"D:/pytest_temp/exp_t2_pred_{tree.name}_p3_mismatches.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = run([sys.executable, str(DIFFERENTIAL), str(tree), str(base), "--seed", str(DIFF_SEED),
                "--out", str(out)], tree, DIFF_TIMEOUT_S)
    stdout = text(proc.stdout)
    modes = {mode: (int(r), int(n), int(m)) for mode, r, n, m in DIFF_LINE.findall(stdout)}
    explore = DIFF_EXPLORATORY.search(stdout)
    warned = sum(1 for line in stdout.splitlines() if line.startswith("WARN "))  # a reader with nothing examined
    passed = (proc.returncode == 0 and set(modes) == {"preserved", "corrected"} and warned == 0
              and all(r == DIFF_READERS and n > 0 and m == 0 for r, n, m in modes.values()))
    shown = "; ".join(f"{mode} readers={r} inputs={n} mismatches={m}" for mode, (r, n, m) in sorted(modes.items()))
    last = (text(proc.stderr).strip().splitlines() or [""])[-1] if proc.returncode else ""
    detail = (f"differential rc={proc.returncode} seed={DIFF_SEED}; {shown or 'no DIFF lines'}; "
              f"readers with an empty examined set {warned}; "
              f"exploratory (unscored) {explore.group(0).strip() if explore else 'absent'}; "
              f"mismatching inputs in {out.as_posix()}" + (f"; stderr {last!r}" if last else ""))
    return passed, detail


def check_c1(gate):
    proc = gate["proc"]
    lines = [line.strip() for line in text(proc.stdout).splitlines() if line.strip()]
    last = lines[-1] if lines else ""
    match = GATE_PASS.fullmatch(last)
    bad = [line for line in lines if line.startswith(("FAIL", "ERROR", "NOT RUN", "OVERALL"))]
    passed = (proc.returncode == 0 and match is not None and match.group(1) == match.group(2)
              and int(match.group(2)) > 0 and not bad)
    executed = f"{match.group(1)} of {match.group(2)}" if match else "unparsed"
    detail = (f"harness_gate rc={proc.returncode}; gates executed {executed}; "
              f"PASS lines {sum(1 for l in lines if l.startswith('PASS:'))}; "
              f"bad lines {len(bad)}; last line {last!r}")
    return passed, detail


def check_c2(tree):
    comp = run([sys.executable, "-m", "compileall", "-q", "scripts"], tree, 600)
    problems, checked, loads = [], 0, 0
    for path in script_files(tree):
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        checked += 1
        defined, used = set(), []
        for node in ast.walk(module):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined.add(node.name)
            elif isinstance(node, ast.arg):
                defined.add(node.arg)
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    if node.id in BASELINE_NAMES:
                        used.append((node.id, node.lineno))
                else:
                    defined.add(node.id)
            elif isinstance(node, ast.Import):
                defined.update(a.asname or a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                defined.update(a.asname or a.name for a in node.names)
        rel = path.relative_to(tree).as_posix()
        for name, line in used:
            loads += 1
            if name not in defined:
                problems.append(f"{rel}:{line} {name}")
    passed = comp.returncode == 0 and not problems and checked > 0
    detail = (f"compileall rc={comp.returncode}; {checked} files; {loads} loads of "
              f"{sorted(BASELINE_NAMES)}; unresolved {problems or 'none'}")
    return passed, detail


def check_c3(gate):
    new = sorted(e for e in gate["after_entries"] - gate["before_entries"] if not e[1].endswith(".py"))
    changed = [p for p in gate["paths"] if gate["before"][p] != gate["after"][p]]
    passed = not new and not changed and len(gate["paths"]) > 0
    detail = (f"{len(gate['paths'])} tracked non-.py files hashed before and after the gate; "
              f"new non-.py status entries {new or 'none'}; bytes changed {changed or 'none'}")
    return passed, detail


def check_c4(tree, base):
    base_sha = text(git(base, "rev-parse", "HEAD").stdout).strip()
    diff = git(tree, "diff", "--name-only", "--no-renames", "-z", base_sha)
    if diff.returncode != 0:
        raise RuntimeError(f"git diff rc={diff.returncode}")
    others = git(tree, "ls-files", "--others", "--exclude-standard", "-z")
    if others.returncode != 0:
        raise RuntimeError(f"git ls-files rc={others.returncode}")
    differing = sorted({p for p in text(diff.stdout).split("\0") if p}
                       | {p for p in text(others.stdout).split("\0") if p})
    outside = [p for p in differing if not p.startswith(("scripts/", "tests/"))]
    passed = bool(differing) and not outside
    detail = (f"against {base_sha[:12]}: {len(differing)} differing files; outside scripts/ and tests/ "
              f"{outside or 'none'}" + ("; empty set is not a pass" if not differing else ""))
    return passed, detail


def check_tests(tree, spec, label):
    """pytest on one behavioural test file, cwd=tree: rc 0 and exactly the expected number passed."""
    path, expected = spec
    if not path.is_file():
        raise RuntimeError(f"test file missing: {path}")
    basetemp = f"D:/pytest_temp/exp_t2_pred_{tree.name}_{label}"
    proc = run([sys.executable, "-m", "pytest", str(path), "-q", "-p", "no:cacheprovider",
                f"--basetemp={basetemp}"], tree, PYTEST_TIMEOUT_S)
    lines = [line.strip() for line in text(proc.stdout).splitlines() if line.strip()]
    last = lines[-1] if lines else ""
    counts = {kind: int(n) for n, kind in PYTEST_SUMMARY.findall(last)}
    passed = proc.returncode == 0 and counts == {"passed": expected}
    return passed, f"{path.name}: pytest rc={proc.returncode}; expected {expected} passed; last line {last!r}"


def need_gate(gate, gate_error):
    if gate is None:
        raise RuntimeError(f"gate run failed: {gate_error}")
    return gate


def attempt(check_id, fn, *args):
    """Run one check; an error is a FAIL that says why, never a skipped check."""
    try:
        passed, detail = fn(*args)
    except Exception as exc:  # a check that cannot be evaluated is a FAIL
        passed, detail = False, f"cannot evaluate: {type(exc).__name__}: {exc}"
    verdict = "PASS" if passed else "FAIL"
    return verdict, f"{check_id} {verdict} {detail}"


def main(argv):
    if len(argv) != 2 or not all(pathlib.Path(a).is_dir() for a in argv):
        print("usage: python predicates_t2.py <tree> <baseline tree>", file=sys.stderr)
        return 2
    sys.stdout.reconfigure(errors="backslashreplace")
    tree, base = (pathlib.Path(a).resolve() for a in argv)

    diagnostics = [line.replace(f"P{n} ", f"D{n} diagnostic, unscored: ", 1)
                   for n, (_, line) in enumerate(check_structure(tree, base), 1)]
    p3 = attempt("P3", check_p3, tree, base)

    gate, gate_error = None, None
    try:
        gate = gate_run(tree)
    except Exception as exc:
        gate_error = f"{type(exc).__name__}: {exc}"
    c1 = attempt("C1", lambda: check_c1(need_gate(gate, gate_error)))
    c2 = attempt("C2", check_c2, tree)
    c3 = attempt("C3", lambda: check_c3(need_gate(gate, gate_error)))
    c4 = attempt("C4", check_c4, tree, base)
    p4 = attempt("P4", check_tests, tree, CORRECTED, "p4")
    c5 = attempt("C5", check_tests, tree, PRESERVED, "c5")

    primary = [p3, p4]
    constraints = [c1, c2, c3, c4, c5]
    for line in diagnostics + [line for _, line in primary + constraints]:
        print(line)
    print(f"PRIMARY automated {sum(v == 'PASS' for v, _ in primary)}/{len(primary)} "
          f"CONSTRAINTS {sum(v == 'PASS' for v, _ in constraints)}/{len(constraints)} "
          f"STRUCTURE adjudicated")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
