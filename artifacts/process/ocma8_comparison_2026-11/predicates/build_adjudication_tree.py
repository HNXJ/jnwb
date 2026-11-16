"""Isolate one T2 tree for structural adjudication (t2_adjudication_protocol.md, section 1).

Usage: python build_adjudication_tree.py <tree> <baseline tree> <out root> <key file> <name>

Builds two directories <out root>/<label>/, one per adjudicator slot, each with `tree/` (a `git clone
--shared` of the baseline with <tree>/scripts copied over it, no `__pycache__`), `changes.diff` (git status and diff of `tree/scripts`
against the baseline), `baseline/` (a clone of the baseline) and `RUBRIC.md` (t2_structure_rubric_r2.md beside this script). Labels are 8 random hex characters.
Appends one JSON line per slot to <key file>: name, source, slot, label, UTC time. Prints the two labels.
"""
import datetime
import json
import pathlib
import secrets
import shutil
import subprocess
import sys

RUBRIC = pathlib.Path(__file__).resolve().parent / "t2_structure_rubric_r2.md"


def clone(base, dest):
    subprocess.run(["git", "clone", "-q", "--shared", str(base), str(dest)], check=True,
                   stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main(argv):
    if len(argv) != 5:
        print(__doc__)
        return 2
    tree, base, out, key_path = (pathlib.Path(a).resolve() for a in argv[:4])
    name = argv[4]
    if not (tree / "scripts").is_dir() or not (base / "scripts").is_dir():
        print("no scripts/ directory in the tree or the baseline")
        return 2
    labels = []
    for slot in (1, 2):
        label = secrets.token_hex(4)
        root = out / label
        root.mkdir(parents=True, exist_ok=False)
        clone(base, root / "tree")
        shutil.rmtree(root / "tree" / "scripts")
        shutil.copytree(tree / "scripts", root / "tree" / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        changed = [subprocess.run(["git", "-C", str(root / "tree"), *args], capture_output=True, check=True,
                                  stdin=subprocess.DEVNULL).stdout
                   for args in (("status", "--porcelain", "--untracked-files=all", "--", "scripts"),
                                ("diff", "HEAD", "--", "scripts"))]
        (root / "changes.diff").write_bytes(b"# git status --porcelain -- scripts (?? = new file, read it in tree/)\n"
                                            + changed[0] + b"\n# git diff HEAD -- scripts\n" + changed[1])
        clone(base, root / "baseline")
        shutil.copyfile(RUBRIC, root / "RUBRIC.md")
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(key_path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"name": name, "source": str(tree), "slot": slot, "label": label,
                                     "time": stamp}) + "\n")
        labels.append(label)
    print(" ".join(labels))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
