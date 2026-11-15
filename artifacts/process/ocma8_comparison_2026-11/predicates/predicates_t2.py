r"""Predicates for experiment task t2: one markdown table cell splitter under scripts/ (jnwb item 17-95).

Usage: python predicates_t2.py <tree> <baseline tree>

Prints one line per check (P1..P4, C1..C5), then `PRIMARY k/4 CONSTRAINTS j/5`. Exit 0 when it runs to
the end, 2 on a usage error. Standard library only (P4 and C5 run pytest as a subprocess); every subprocess
runs with cwd=<tree>.

P1  exactly one function under scripts/**/*.py is a markdown-row cell splitter. A function counts when its
    name is in BASELINE_NAMES, or when a return statement in it matches SPLIT_RETURN (applied to the
    return statement's source). Inline split lines outside counted functions are printed, not counted.
P2  that one splitter honours escaped pipes: it is loaded by file path with importlib in a subprocess
    (`-I`, cwd=<tree>) and called on `| a \| b | c |` (2 cells; first `a \| b` or `a | b` after strip,
    second `c`) and on `| x | y |` (['x', 'y'] after strip). FAIL when P1 does not count exactly 1.
P3  no inline markdown-row split remains: SPLIT_INLINE (the idiom `.strip("|").split("|")` or a split on
    an unescaped/escaped pipe) matches no line under scripts/**/*.py outside the counted splitter
    definitions (the single remaining one, when P1 is 1). PASS only when the count is 0; FAIL when P1
    is not exactly 1. The matches are printed; at the baseline they are BASELINE_INLINE_SITES.
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

Baseline (ac995dde) splitter definitions are BASELINE_DEFINITIONS; the survey counted 5 definitions in 4
files, and 8 pipe-split sites (the 5 definitions plus 3 inline sites in larger functions).
"""

import ast
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys

#: Splitter definitions at the baseline ac995dde, from an AST survey: (file, line, name).
#: Line numbers are the baseline's; P1 matches the tree by file and name.
BASELINE_DEFINITIONS = (
    ("scripts/build_dashboard.py", 353, "_cells"),
    ("scripts/build_fact_graph.py", 224, "_cells"),
    ("scripts/learning_gate.py", 52, "_cells"),
    ("scripts/release_gate.py", 1289, "_cells"),
    ("scripts/release_gate.py", 1296, "_table_cells"),
)
BASELINE_NAMES = frozenset(name for _, _, name in BASELINE_DEFINITIONS)
#: The baseline idiom in a return statement: a split on a pipe, escaped-pipe lookbehind included.
SPLIT_RETURN = re.compile(r"""split\(\s*r?["'][^"']*\|""")
#: P3's idiom: an inline split on a pipe, in any statement (not only a return). Counted by P3 outside the
#: splitter definitions. At the baseline it matches 8 lines: the 5 definition bodies and the 3 sites below.
SPLIT_INLINE = re.compile(r"""strip\(\s*["']\|["']\s*\)\.split\(|split\(\s*r?["'](?:\(\?<!\\\\\))?\\?\|["']""")
#: The inline split sites at the baseline ac995dde outside the five definitions: (file, line). Checked by
#: P3 at the baseline: SPLIT_INLINE matches exactly these three lines outside BASELINE_DEFINITIONS.
BASELINE_INLINE_SITES = (
    ("scripts/build_fact_graph.py", 399),
    ("scripts/docs_form_gate.py", 285),
    ("scripts/reconstruct_state.py", 224),
)
ROW_ESCAPED = "| a \\| b | c |"
ROW_PLAIN = "| x | y |"
GATE_PASS = re.compile(r"ALL HARNESS GATES PASSED\. (\d+) of (\d+) gates executed\.")
PROBE_TAG = "T2_PROBE_RESULT "
GATE_TIMEOUT_S = 540
SELF = pathlib.Path(__file__).resolve()
#: Behavioural tests (t2 amendment): file and the exact number of tests that must pass.
CORRECTED = (SELF.parent / "t2_corrected_test.py", 6)
PRESERVED = (SELF.parent.parent / "accept" / "t2_preserved_test.py", 31)
PYTEST_SUMMARY = re.compile(r"(\d+) (passed|failed|error|errors|skipped|xfailed|xpassed|deselected)\b")
PYTEST_TIMEOUT_S = 300
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


def definitions(tree):
    """Counted splitter definitions as (file, line, name, by_name, by_body), and inline split lines."""
    found, inline = [], []
    for path in script_files(tree):
        source = path.read_text(encoding="utf-8")
        module = ast.parse(source, filename=str(path))
        rel = path.relative_to(tree).as_posix()
        spans = []
        for fn in ast.walk(module):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            by_name = fn.name in BASELINE_NAMES
            by_body = any(isinstance(node, ast.Return) and node.value is not None
                          and SPLIT_RETURN.search(ast.get_source_segment(source, node) or "")
                          for node in ast.walk(fn))
            if by_name or by_body:
                found.append((rel, fn.lineno, fn.name, by_name, by_body))
                spans.append((fn.lineno, fn.end_lineno))
        for number, line in enumerate(source.splitlines(), 1):
            if SPLIT_INLINE.search(line) and not any(a <= number <= b for a, b in spans):
                inline.append(f"{rel}:{number}")
    return sorted(found), inline


def probe(tree, rel, name):
    """Import the splitter by path in a child with cwd=tree, call it on both rows, return the JSON result."""
    payload = json.dumps({"path": str(tree / rel), "name": name, "rows": [ROW_ESCAPED, ROW_PLAIN]})
    proc = run([sys.executable, "-I", str(SELF)], tree, 120, dict(CHILD_ENV, T2_PROBE=payload))
    if proc.returncode != 0:
        last = (text(proc.stderr).strip().splitlines() or ["no stderr"])[-1]
        raise RuntimeError(f"probe rc={proc.returncode}: {last}")
    for line in text(proc.stdout).splitlines():
        if line.startswith(PROBE_TAG):
            return json.loads(line[len(PROBE_TAG):])
    raise RuntimeError("probe printed no result line")


def probe_child():
    """Child mode, entered only through the T2_PROBE environment variable set by probe()."""
    payload = json.loads(os.environ["T2_PROBE"])
    sys.path[:0] = [os.getcwd(), os.path.dirname(payload["path"])]
    spec = importlib.util.spec_from_file_location("t2_probe_target", payload["path"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    function = getattr(module, payload["name"])
    out = {}
    for row in payload["rows"]:
        value = function(row)
        out[row] = {"type": type(value).__name__,
                    "value": list(value) if isinstance(value, (list, tuple)) else None}
    print(PROBE_TAG + json.dumps(out))


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


def check_p1(found, inline):
    counted = ", ".join(f"{rel}:{line} {name}" for rel, line, name, _, _ in found) or "none"
    by_name = sum(1 for f in found if f[3])
    by_body = sum(1 for f in found if f[4])
    still = sum(1 for rel, _, name in BASELINE_DEFINITIONS
                if any(f[0] == rel and f[2] == name for f in found))
    detail = (f"definitions={len(found)} [{counted}] by_name={by_name} by_body={by_body} "
              f"baseline_pairs_still_defined={still}/{len(BASELINE_DEFINITIONS)} "
              f"inline_not_counted={len(inline)} [{', '.join(inline)}]")
    return len(found) == 1, detail


def check_p2(tree, found):
    if len(found) != 1:
        return False, f"not evaluated: P1 counted {len(found)} splitters, need exactly 1"
    rel, line, name = found[0][0], found[0][1], found[0][2]
    result = probe(tree, rel, name)
    one, two = result[ROW_ESCAPED], result[ROW_PLAIN]
    cells_one, cells_two = one["value"], two["value"]
    ok_one = (cells_one is not None and len(cells_one) == 2
              and cells_one[0].strip() in ("a \\| b", "a | b") and cells_one[1].strip() == "c")
    ok_two = cells_two is not None and [c.strip() for c in cells_two] == ["x", "y"]
    detail = (f"{rel}:{line} {name}: {ROW_ESCAPED!r} -> {cells_one} ({one['type']}); "
              f"{ROW_PLAIN!r} -> {cells_two} ({two['type']})")
    return ok_one and ok_two, detail


def check_p3(found, inline):
    matched = {site.rsplit(":", 1)[0] for site in inline}
    files_still = sum(1 for rel, _ in BASELINE_INLINE_SITES if rel in matched)
    detail = (f"inline split matches outside the splitter={len(inline)} [{', '.join(inline)}] "
              f"baseline_files_still_matching={files_still}/{len(BASELINE_INLINE_SITES)}")
    return len(found) == 1 and not inline, detail


def check_c1(gate):
    if gate is None:
        raise RuntimeError("gate did not run")
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
    if gate is None:
        raise RuntimeError("gate did not run")
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
    return passed, f"{check_id} {'PASS' if passed else 'FAIL'} {detail}"


def main(argv):
    if os.environ.get("T2_PROBE"):
        probe_child()
        return 0
    if len(argv) != 2 or not all(pathlib.Path(a).is_dir() for a in argv):
        print("usage: python predicates_t2.py <tree> <baseline tree>", file=sys.stderr)
        return 2
    sys.stdout.reconfigure(errors="backslashreplace")
    tree, base = (pathlib.Path(a).resolve() for a in argv)

    found, inline = [], []
    try:
        found, inline = definitions(tree)
        p1_ok, p1_detail = check_p1(found, inline)
        p1 = (p1_ok, f"P1 {'PASS' if p1_ok else 'FAIL'} {p1_detail}")
    except Exception as exc:
        p1 = (False, f"P1 FAIL cannot evaluate: {type(exc).__name__}: {exc}")
    p2 = attempt("P2", check_p2, tree, found)
    p3 = attempt("P3", check_p3, found, inline)

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

    primary = [p1, p2, p3, p4]
    constraints = [c1, c2, c3, c4, c5]
    for _, line in primary + constraints:
        print(line)
    print(f"PRIMARY {sum(ok for ok, _ in primary)}/{len(primary)} "
          f"CONSTRAINTS {sum(ok for ok, _ in constraints)}/{len(constraints)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
