"""t4 predicates: jynx artifacts/state.md brought under the artifacts audit cap without losing a pointer.

Usage: python predicates_t4.py <tree> <baseline tree>

Primary:
  P1  artifacts/state.md is at most 6000 bytes (STATE_MAX_BYTES in scripts/artifacts_check.py) AND
      `python scripts/artifacts_check.py .` in the tree prints `VERDICT: ACCEPT` with exit 0.
Constraints:
  C1  every hex token (\\b[0-9a-f]{7,40}\\b, with a digit and an a-f letter) and every id (\\b[OTP]-\\d+\\b) that occurs in
      the baseline's artifacts/state.md occurs in the tree's artifacts/state.md or in a git-tracked or untracked
      file under the tree's artifacts/. Prints the number examined and the missing ones; an empty examined set is FAIL.
  C2  every file that differs from the baseline tree is under artifacts/ (an empty differing set is FAIL).

Prints one line per check (`<id> PASS|FAIL <what was examined>`), then `PRIMARY k/1 CONSTRAINTS j/2`.
Exit 0 when it ran to the end; 2 on a usage error. artifacts_check.py and git only read; PYTHONDONTWRITEBYTECODE=1;
nothing is written into a tree.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
CAP = 6000  # scripts/artifacts_check.py: STATE_MAX_BYTES = 6000
TOKEN = re.compile(r"\b(?:[0-9a-f]{7,40}|[OTP]-\d+)\b")


def git(root, *args):
    p = subprocess.run(["git", "-C", root, *args], stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} rc {p.returncode}: {p.stderr.strip()}")
    return p.stdout


def read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def tokens_in(text):
    return set(TOKEN.findall(text))


def is_examined(tok):
    if tok[0] in "OTP":
        return True
    return bool(re.search(r"\d", tok)) and bool(re.search(r"[a-f]", tok))


def artifact_files(tree):
    tracked = git(tree, "ls-files", "artifacts").splitlines()
    status = git(tree, "status", "--porcelain", "--untracked-files=all", "artifacts").splitlines()
    untracked = [ln[3:] for ln in status if ln.startswith("?? ")]
    return sorted({f for f in tracked + untracked if f})


def changed_files(tree, base):
    base_head = git(base, "rev-parse", "HEAD").strip()
    tracked = git(tree, "diff", "--name-only", base_head).splitlines()
    untracked = git(tree, "ls-files", "--others", "--exclude-standard").splitlines()
    return sorted({f for f in tracked + untracked if f})


def check_p1(tree):
    n = len((Path(tree) / "artifacts" / "state.md").read_bytes())
    p = subprocess.run([sys.executable, "scripts/artifacts_check.py", "."], cwd=tree, env=ENV,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace")
    verdicts = [ln.rstrip() for ln in (p.stdout + p.stderr).splitlines() if ln.startswith("VERDICT:")]
    ok = n <= CAP and p.returncode == 0 and verdicts == ["VERDICT: ACCEPT"]
    shown = verdicts[0] if verdicts else "no VERDICT line"
    return ok, f"artifacts/state.md {n} bytes (cap {CAP}); artifacts_check rc {p.returncode}; '{shown}'"


def check_c1(tree, base):
    base_tokens = sorted(t for t in tokens_in(read(Path(base) / "artifacts" / "state.md")) if is_examined(t))
    if not base_tokens:
        return False, "0 examined tokens in the baseline state.md: empty examined set"
    names = ["artifacts/state.md"] + [f for f in artifact_files(tree) if f != "artifacts/state.md"]
    present, searched = set(), 0
    for name in names:
        path = Path(tree) / name
        if path.is_file():
            searched += 1
            present |= tokens_in(read(path))
    missing = [t for t in base_tokens if t not in present]
    n_sha = sum(1 for t in base_tokens if t[0] not in "OTP")
    txt = (f"examined {len(base_tokens)} distinct tokens from baseline state.md ({n_sha} SHA, "
           f"{len(base_tokens) - n_sha} ids) against {searched} file(s) in tree artifacts/; missing {len(missing)}: {missing}")
    return not missing, txt


def check_c2(tree, base):
    changed = changed_files(tree, base)
    if not changed:
        return False, "0 files differ from the baseline tree: empty examined set, scope not shown"
    outside = [f for f in changed if not f.startswith("artifacts/")]
    return not outside, f"{len(changed)} file(s) differ from baseline {changed}; outside artifacts/: {outside or 'none'}"


def attempt(fn, *args):
    try:
        return fn(*args)
    except Exception as exc:  # a check that cannot be evaluated is FAIL, and says why
        return False, f"could not evaluate: {exc!r}"


def main(argv):
    if len(argv) != 3 or not all(Path(a).is_dir() for a in argv[1:]):
        print("usage: python predicates_t4.py <tree> <baseline tree>", file=sys.stderr)
        return 2
    tree, base = str(Path(argv[1]).resolve()), str(Path(argv[2]).resolve())
    results = [("P1", *attempt(check_p1, tree)),
               ("C1", *attempt(check_c1, tree, base)),
               ("C2", *attempt(check_c2, tree, base))]
    for cid, ok, txt in results:
        print(f"{cid} {'PASS' if ok else 'FAIL'} {txt}")
    prim = [r for r in results if r[0].startswith("P")]
    cons = [r for r in results if r[0].startswith("C")]
    print(f"PRIMARY {sum(r[1] for r in prim)}/{len(prim)} CONSTRAINTS {sum(r[1] for r in cons)}/{len(cons)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
