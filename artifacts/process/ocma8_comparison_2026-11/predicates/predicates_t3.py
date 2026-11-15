"""t3 predicates: the four tests/test_rng_*.py files merged into one file by subject (todo item 17-97).

Usage: python predicates_t3.py <tree> <baseline tree>

Primary (P2 and P3 FAIL when P1 fails):
  P1  exactly one file matches tests/**/test_rng*.py in the tree (baseline: 4).
  P2  pytest --collect-only -q on those files gives the baseline's node count and the same multiset of node
      names (text after the first '::') as the baseline's files.
  P3  those files pass in the tree: rc 0, 0 failed, 0 errors, passed >= 1, passed + skipped = collected.
Constraints:
  C1  every file that differs from the baseline tree is under tests/ (an empty differing set is FAIL: nothing examined).
  C2  the whole-tests/ collection count (last line of --collect-only -q on tests) equals the baseline's.

Prints one line per check (`<id> PASS|FAIL <what was examined>`), then `PRIMARY k/3 CONSTRAINTS j/2`.
Exit 0 when it ran to the end; 2 on a usage error. Each pytest runs with cwd = the tree under test,
PYTHONDONTWRITEBYTECODE=1, -p no:cacheprovider and --basetemp under D:/pytest_temp/exp_t3; nothing is written into a tree.
"""
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
BASETEMP = "D:/pytest_temp/exp_t3"
NODE = re.compile(r"^(\S+?\.py)::(.*)$")
COLLECTED = re.compile(r"(\d+) tests? collected")
OUTCOME = re.compile(r"(\d+) (passed|failed|errors?|skipped)\b")


def git(root, *args):
    p = subprocess.run(["git", "-C", root, *args], stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} rc {p.returncode}: {p.stderr.strip()}")
    return p.stdout


def pytest(root, args, tag):
    cmd = [sys.executable, "-m", "pytest", *args, "-p", "no:cacheprovider", f"--basetemp={BASETEMP}/{tag}"]
    p = subprocess.run(cmd, cwd=root, env=ENV, stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, [ln for ln in (p.stdout + p.stderr).splitlines() if ln.strip()]


def rng_files(root):
    return sorted(p.relative_to(root).as_posix() for p in Path(root).glob("tests/**/test_rng*.py") if p.is_file())


def collect_rng(root, files, tag):
    rc, lines = pytest(root, ["--collect-only", "-q", *files], tag)
    nodes = [m.group(2) for m in (NODE.match(ln) for ln in lines) if m]
    return rc, nodes, (lines[-1] if lines else "")


def check_p2(tree, base, t_files, p1_ok):
    b_files = rng_files(base)
    if not t_files or not b_files:
        return False, f"nothing to collect: tree {len(t_files)} file(s), baseline {len(b_files)}", None
    rc_t, t_nodes, t_last = collect_rng(tree, t_files, "tree_rng_collect")
    rc_b, b_nodes, b_last = collect_rng(base, b_files, "base_rng_collect")
    t_c, b_c = Counter(t_nodes), Counter(b_nodes)
    same = t_c == b_c
    ok = p1_ok and rc_t == 0 and rc_b == 0 and len(t_nodes) == len(b_nodes) and same and len(t_nodes) > 0
    txt = (f"tree {len(t_nodes)} nodes from {len(t_files)} file(s) (rc {rc_t}, last '{t_last}'); "
           f"baseline {len(b_nodes)} nodes from {len(b_files)} file(s) (rc {rc_b}, last '{b_last}'); "
           f"multiset equal {same}")
    if not same:
        txt += f"; only in tree {sorted((t_c - b_c).elements())[:3]}; only in baseline {sorted((b_c - t_c).elements())[:3]}"
    if not p1_ok:
        txt = "P1 failed, so FAIL; " + txt
    return ok, txt, len(t_nodes)


def check_p3(tree, t_files, n_collected, p1_ok):
    if not p1_ok:
        return False, "not run: P1 failed"
    if n_collected is None:
        return False, "no collected count from P2"
    rc, lines = pytest(tree, ["-q", *t_files], "tree_rng_run")
    last = lines[-1] if lines else ""
    got = {}
    for n, kind in OUTCOME.findall(last):
        key = "errors" if kind.startswith("error") else kind
        got[key] = got.get(key, 0) + int(n)
    passed, failed, errors, skipped = (got.get(k, 0) for k in ("passed", "failed", "errors", "skipped"))
    ok = rc == 0 and failed == 0 and errors == 0 and passed >= 1 and passed + skipped == n_collected
    return ok, (f"rc {rc}; last '{last}'; passed {passed}, skipped {skipped}, failed {failed}, "
                f"errors {errors}; collected {n_collected}")


def changed_files(tree, base):
    base_head = git(base, "rev-parse", "HEAD").strip()
    tracked = git(tree, "diff", "--name-only", base_head).splitlines()
    untracked = git(tree, "ls-files", "--others", "--exclude-standard").splitlines()
    return sorted({f for f in tracked + untracked if f})


def check_c1(tree, base):
    changed = changed_files(tree, base)
    if not changed:
        return False, "0 files differ from the baseline tree: empty examined set, scope not shown"
    outside = [f for f in changed if not f.startswith("tests/")]
    return not outside, f"{len(changed)} file(s) differ from baseline {changed}; outside tests/: {outside or 'none'}"


def whole_count(root, tag):
    rc, lines = pytest(root, ["tests", "--collect-only", "-q"], tag)
    last = lines[-1] if lines else ""
    m = COLLECTED.search(last)
    return rc, (int(m.group(1)) if m else None), last


def check_c2(tree, base):
    rc_t, n_t, last_t = whole_count(tree, "tree_all_collect")
    rc_b, n_b, last_b = whole_count(base, "base_all_collect")
    ok = rc_t == 0 and rc_b == 0 and n_t is not None and n_t == n_b and n_b > 0
    return ok, f"tree {n_t} (rc {rc_t}, last '{last_t}') vs baseline {n_b} (rc {rc_b}, last '{last_b}')"


def attempt(fn, *args):
    try:
        return fn(*args)
    except Exception as exc:  # a check that cannot be evaluated is FAIL, and says why
        return False, f"could not evaluate: {exc!r}"


def main(argv):
    if len(argv) != 3 or not all(Path(a).is_dir() for a in argv[1:]):
        print("usage: python predicates_t3.py <tree> <baseline tree>", file=sys.stderr)
        return 2
    tree, base = str(Path(argv[1]).resolve()), str(Path(argv[2]).resolve())
    t_files = rng_files(tree)
    p1_ok = len(t_files) == 1
    results = [("P1", p1_ok, f"{len(t_files)} file(s) match tests/**/test_rng*.py in tree {t_files}; "
                              f"baseline has {len(rng_files(base))}")]
    try:
        p2_ok, p2_txt, n_tree = check_p2(tree, base, t_files, p1_ok)
    except Exception as exc:
        p2_ok, p2_txt, n_tree = False, f"could not evaluate: {exc!r}", None
    results.append(("P2", p2_ok, p2_txt))
    p3_ok, p3_txt = attempt(check_p3, tree, t_files, n_tree, p1_ok)
    results.append(("P3", p3_ok, p3_txt))
    c1_ok, c1_txt = attempt(check_c1, tree, base)
    results.append(("C1", c1_ok, c1_txt))
    c2_ok, c2_txt = attempt(check_c2, tree, base)
    results.append(("C2", c2_ok, c2_txt))
    for cid, ok, txt in results:
        print(f"{cid} {'PASS' if ok else 'FAIL'} {txt}")
    prim = [r for r in results if r[0].startswith("P")]
    cons = [r for r in results if r[0].startswith("C")]
    print(f"PRIMARY {sum(r[1] for r in prim)}/{len(prim)} CONSTRAINTS {sum(r[1] for r in cons)}/{len(cons)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
