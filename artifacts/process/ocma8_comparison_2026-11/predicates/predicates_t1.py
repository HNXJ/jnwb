"""Predicates for experiment task t1 (jarness T-82): selfcheck.py must report a required hook that settings.json
does not wire. The required set is the "Hook wiring" table of <baseline tree>/harness/README.md.

Usage: python predicates_t1.py <tree> <baseline tree>     (exit 2 on a usage error)

Primary:
  P1  selfcheck on a fake home that wires every required hook except SubagentStop (subagent_log.py): a finding
      names SubagentStop or subagent_log, and the exit code is 1.
  P2  the same fake home with every required hook wired: no finding line names a required hook script or event.
      The examined set is the lines P1 flagged; an empty set is a FAIL (nothing was compared).
  P3  red first: each test file under harness/ that the tree adds or changes against the baseline has a failing
      test in a scratch copy whose harness/selfcheck.py is the baseline's, and passes in the tree.
Constraints:
  C1  every file that differs between the trees (ignoring __pycache__, .pytest_cache, .git) is under harness/ or
      artifacts/.
  C2  python harness/lint.py exits 0 in the tree.
  C3  python harness/audit.py --selftest exits 0 in the tree.

Writes: fixtures under this file's fixtures/ folder; pytest basetemp and the P3 scratch copy under D:/pytest_temp.
Output: one line per check (`<id> PASS|FAIL <what was examined, with numbers>`), indented detail lines, then
`PRIMARY k/3 CONSTRAINTS j/3`.
"""
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
PYTEST_TEMP = Path("D:/pytest_temp")
SKIP = (".git", "__pycache__", ".pytest_cache")
EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "SubagentStop")
OMIT = ("SubagentStop", "subagent_log.py")  # (event, script) left unwired in the P1 fixture
FLAG = ("SubagentStop", "subagent_log")  # a P1 finding line must carry one of these
VERDICT = "VERDICT:"


def run(args, cwd, env=None, timeout=900):
    """(rc, stdout, stderr); rc is None when the command did not start or finish. Stdin is closed."""
    e = dict(os.environ if env is None else env)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        r = subprocess.run([str(a) for a in args], cwd=str(cwd), env=e, stdin=subprocess.DEVNULL,
                           capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as ex:
        return None, "", f"{type(ex).__name__}: {ex}"
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def last_line(text):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return lines[-1].strip() if lines else "(no output)"


def head(tree):
    rc, out, _ = run(["git", "-C", tree, "rev-parse", "HEAD"], tree)
    if rc != 0 or not out.strip():
        raise RuntimeError(f"git rev-parse HEAD failed in {tree}")
    return out.strip()


def required(baseline):
    """[{event, matcher, path, name, arg}], one per hook row of the Hook wiring table in the baseline README."""
    text = (baseline / "harness" / "README.md").read_text(encoding="utf-8")
    m = re.search(r"^## Hook wiring\n(.*?)(?=^## )", text, re.M | re.S)
    if m is None:
        raise ValueError("no '## Hook wiring' section in the baseline README")
    rows = []
    for line in m.group(1).splitlines():
        if not line.startswith("|"):
            continue
        # an escaped pipe inside a matcher (`Bash\|PowerShell`) is not a cell separator
        cells = [c.replace("\x00", "|").strip() for c in line.replace("\\|", "\x00").strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0] not in EVENTS:
            continue
        for item in re.findall(r"`([^`]+)`", cells[2]):
            path, _, arg = item.partition(" ")
            rows.append({"event": cells[0], "matcher": cells[1].strip("`"), "path": path,
                         "name": path.rsplit("/", 1)[-1], "arg": arg})
    return rows


def key(r):
    return (r["event"], r["name"])


def script_path(claude, r):
    return claude / r["path"] if "/" in r["path"] else claude / "hooks" / r["path"]


def build_home(name, tree, rows, wired, sha):
    """Fake home FIXTURES/<name>. Every required script exists as an empty file; settings.json wires `wired`;
    the receipt names the tree's HEAD with dirty false, so the install receipt is not what gets measured."""
    fx = FIXTURES / name
    if fx.exists():
        shutil.rmtree(fx)
    claude = fx / ".claude"
    for r in rows:
        p = script_path(claude, r)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", encoding="utf-8")
    hooks = {}
    for r in wired:
        cmd = f'python "{script_path(claude, r).as_posix()}"' + (f" {r['arg']}" if r["arg"] else "")
        group = {"hooks": [{"type": "command", "command": cmd}]}
        if r["matcher"] != "any":
            group = {"matcher": r["matcher"], **group}
        hooks.setdefault(r["event"], []).append(group)
    (claude / "settings.json").write_text(json.dumps({"hooks": hooks}, indent=2), encoding="utf-8")
    (claude / "harness-install.json").write_text(
        json.dumps({"source": tree.as_posix(), "sha": sha, "dirty": False}), encoding="utf-8")
    return fx


def selfcheck(tree, fx):
    """Run the tree's selfcheck.py with --claude-home under fx. Its install.py subprocess reads USERPROFILE/HOME,
    so both point at fx: the real ~/.claude is not read."""
    env = dict(os.environ, USERPROFILE=str(fx), HOME=str(fx))
    rc, out, err = run([sys.executable, tree / "harness" / "selfcheck.py", "--claude-home", fx / ".claude"],
                       tree, env=env)
    findings = [ln for ln in out.splitlines() if ln.startswith("- [")]
    ran = rc in (0, 1) and VERDICT in out and "Traceback" not in err
    return ran, rc, findings, err


def check_p1(tree, rows, sha):
    wired = [r for r in rows if key(r) != OMIT]
    fx = build_home("p1", tree, rows, wired, sha)
    ran, rc, findings, err = selfcheck(tree, fx)
    if not ran:
        return False, f"selfcheck did not run to a VERDICT (rc={rc}, stderr {last_line(err)!r})", [], []
    flagged = [ln for ln in findings if any(n in ln for n in FLAG)]
    inst = [ln for ln in findings if ln.startswith("- [install]")]
    under = sum(str(fx).lower() in ln.lower() for ln in inst)
    text = (f"selfcheck rc={rc}, {len(findings)} findings, {len(flagged)} name SubagentStop or subagent_log; "
            f"fixture: {len(wired)} of {len(rows)} required hooks wired, {OMIT[0]} {OMIT[1]} omitted; "
            f"install lines under the fixture home: {under} of {len(inst)}")
    details = [f"  P1 flagged: {ln}" for ln in flagged] or ["  P1 flagged: none"]
    return rc == 1 and bool(flagged), text, details, flagged


def check_p2(tree, rows, sha, examined):
    fx = build_home("p2", tree, rows, rows, sha)
    ran, rc, findings, err = selfcheck(tree, fx)
    names = sorted({r["name"] for r in rows} | set(EVENTS))
    hits = [ln for ln in findings if any(n in ln for n in names)]
    details = [f"  P2 compared (P1 flagged): {ln}" for ln in examined] or ["  P2 compared (P1 flagged): none"]
    details += [f"  P2 finding: {ln}" for ln in findings] or ["  P2 finding: none"]
    if not ran:
        return False, f"selfcheck did not run to a VERDICT on the all-wired home (rc={rc})", details
    if not examined:
        return False, (f"examined set empty: P1 flagged no line, so nothing was compared; all-wired home rc={rc}, "
                       f"{len(findings)} findings, {len(hits)} name a required hook or event"), details
    text = (f"selfcheck rc={rc} on the all-wired home, {len(findings)} findings, {len(hits)} name a required hook "
            f"script or event; compared {len(examined)} P1-flagged line(s) and {len(findings)} finding line(s)")
    return not hits, text, details


def tally(out):
    """{passed, failed, error} from pytest's last summary line, or None when there is none."""
    summary = None
    for ln in out.splitlines():
        if re.search(r"\d+ (passed|failed|errors?)\b|no tests ran", ln):
            summary = ln
    if summary is None:
        return None
    t = {"passed": 0, "failed": 0, "error": 0}
    for n, k in re.findall(r"(\d+) (passed|failed|errors?)\b", summary):
        t["error" if k.startswith("error") else k] += int(n)
    return t


def pytest_one(root, rel, tag, i):
    bt = PYTEST_TEMP / "exp_t1_p3" / f"{tag}_{i}"
    rc, out, _ = run([sys.executable, "-m", "pytest", rel, "-q", "-p", "no:cacheprovider", f"--basetemp={bt}"], root)
    return rc, tally(out), last_line(out)


def check_p3(tree, base):
    tests = []
    for p in (tree / "harness").rglob("*.py"):
        rel = p.relative_to(tree)
        if set(rel.parts) & set(SKIP):
            continue
        if p.name.startswith("test_") or p.name.endswith("_test.py"):
            tests.append(rel.as_posix())
    tests.sort()
    changed = [r for r in tests if not (base / r).is_file() or not filecmp.cmp(tree / r, base / r, shallow=False)]
    if not changed:
        return False, (f"checked {len(tests)} of {len(tests)} test files under harness/: none added or changed "
                       f"against the baseline, so red-first has nothing to run"), []
    scr_root = PYTEST_TEMP / "exp_t1_p3"
    scr_root.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="run_", dir=str(scr_root))) / "tree"
    for outside in (tree, base):
        if str(scratch).lower().startswith(str(outside).lower()):
            raise RuntimeError("scratch copy must lie outside both trees")
    shutil.copytree(tree, scratch, ignore=shutil.ignore_patterns(*SKIP))
    shutil.copyfile(base / "harness" / "selfcheck.py", scratch / "harness" / "selfcheck.py")
    if not filecmp.cmp(scratch / "harness" / "selfcheck.py", base / "harness" / "selfcheck.py", shallow=False):
        raise RuntimeError("scratch selfcheck.py is not the baseline's")
    red = [(r,) + pytest_one(scratch, r, "scr", i) for i, r in enumerate(changed)]
    green = [(r,) + pytest_one(tree, r, "tree", i) for i, r in enumerate(changed)]
    failed_scr = sum((t or {}).get("failed", 0) for _, _, t, _ in red)
    red_files = sum(1 for _, _, t, _ in red if t and t["failed"] >= 1)
    green_ok = sum(1 for _, rc, t, _ in green
                   if rc == 0 and t and t["passed"] >= 1 and t["failed"] == 0 and t["error"] == 0)
    ok = failed_scr >= 1 and green_ok == len(changed)
    text = (f"checked {len(changed)} of {len(changed)} changed test files ({', '.join(changed)}); scratch with the "
            f"baseline selfcheck.py: {failed_scr} failed test(s), {red_files} of {len(changed)} files red; "
            f"tree: {green_ok} of {len(changed)} files pass (rc 0, passed >= 1, no failed or error)")
    details = [f"  P3 scratch copy: {scratch}"]
    details += [f"  P3 scratch {r}: rc={rc} {t} | {ln}" for r, rc, t, ln in red]
    details += [f"  P3 tree {r}: rc={rc} {t} | {ln}" for r, rc, t, ln in green]
    return ok, text, details


def files_of(root):
    out = {}
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP]
        for f in files:
            if f not in SKIP:
                p = Path(d) / f
                out[p.relative_to(root).as_posix()] = p
    return out


def check_c1(tree, base):
    a, b = files_of(tree), files_of(base)
    both = set(a) & set(b)
    diff = sorted((set(a) ^ set(b)) | {k for k in both if not filecmp.cmp(a[k], b[k], shallow=False)})
    outside = [k for k in diff if not k.startswith(("harness/", "artifacts/"))]
    examined = set(a) | set(b)
    text = (f"{len(examined)} files compared across both trees, {len(diff)} differ; checked {len(diff)} of "
            f"{len(diff)} differing files: {len(diff) - len(outside)} under harness/ or artifacts/, "
            f"outside: {outside or 'none'}")
    return bool(examined) and not outside, text, [f"  C1 differs: {k}" for k in diff]


def check_c2(tree):
    rc, out, err = run([sys.executable, "harness/lint.py"], tree, timeout=600)
    return rc == 0, f"python harness/lint.py rc={rc}; last line: {last_line(out or err)}", []


def check_c3(tree):
    rc, out, err = run([sys.executable, "harness/audit.py", "--selftest"], tree, timeout=600)
    ok = rc == 0 and "selftest ok" in out
    return ok, f"python harness/audit.py --selftest rc={rc}; last line: {last_line(out or err)}", []


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(argv) != 2 or not all(Path(a).is_dir() for a in argv):
        print("usage: python predicates_t1.py <tree> <baseline tree>", file=sys.stderr)
        return 2
    tree, base = Path(argv[0]).resolve(), Path(argv[1]).resolve()
    results = []

    def emit(cid, ok, text, details=()):
        results.append((cid, ok))
        print(f"{cid} {'PASS' if ok else 'FAIL'} {text}")
        for d in details:
            print(d)

    rows, sha, reason = None, None, ""
    try:
        rows = required(base)
        if sum(key(r) == OMIT for r in rows) != 1:
            raise ValueError(f"baseline README table does not hold exactly one {OMIT[0]} {OMIT[1]} row")
        sha = head(tree)
    except Exception as ex:
        rows, reason = None, f"{type(ex).__name__}: {ex}"

    flagged = []
    try:
        if rows is None:
            raise RuntimeError(f"no required-hook table: {reason}")
        ok, text, details, flagged = check_p1(tree, rows, sha)
        emit("P1", ok, text, details)
    except Exception as ex:
        emit("P1", False, f"cannot evaluate: {type(ex).__name__}: {ex}")
    try:
        if rows is None:
            raise RuntimeError(f"no required-hook table: {reason}")
        ok, text, details = check_p2(tree, rows, sha, flagged)
        emit("P2", ok, text, details)
    except Exception as ex:
        emit("P2", False, f"cannot evaluate: {type(ex).__name__}: {ex}")
    try:
        ok, text, details = check_p3(tree, base)
        emit("P3", ok, text, details)
    except Exception as ex:
        emit("P3", False, f"cannot evaluate: {type(ex).__name__}: {ex}")
    for cid, fn in (("C1", lambda: check_c1(tree, base)), ("C2", lambda: check_c2(tree)),
                    ("C3", lambda: check_c3(tree))):
        try:
            ok, text, details = fn()
            emit(cid, ok, text, details)
        except Exception as ex:
            emit(cid, False, f"cannot evaluate: {type(ex).__name__}: {ex}")
    k = sum(ok for cid, ok in results if cid.startswith("P"))
    j = sum(ok for cid, ok in results if cid.startswith("C"))
    print(f"PRIMARY {k}/3 CONSTRAINTS {j}/3")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
