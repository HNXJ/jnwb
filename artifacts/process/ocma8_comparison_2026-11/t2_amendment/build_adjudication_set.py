"""Build the blinded control set for T2 structural adjudication.

Usage: python build_adjudication_set.py <baseline tree> <out dir> <key file>

Each control tree becomes <out dir>/kNN: a `git clone --shared` of the baseline with the control's `scripts/`
copied over it (no `__pycache__`), so every tree looks alike from outside. Labels are a seeded shuffle
(SEED). The key (label, source, anchor verdict set by the lead before adjudication, origin of the anchor) is
written to <key file>, outside <out dir>. The baseline itself is copied beside the set as <out dir>/baseline.
"""
import json
import pathlib
import random
import shutil
import subprocess
import sys

SEED = 2026111601
W = "D:/repos/_work"
V = "D:/tmp/claude/acfe204914b1181d/30cef652-1268-5f7a-911c-87a2f8fc2c76/scratchpad/rev_t2c/trees"
#: (source tree, anchor, who built the tree and declared it). Anchors are structure only, behaviour aside.
CONTROLS = [
    (f"{W}/exp_t2beh/pos2", "PASS", "orchestrator: corrected reference"),
    (f"{W}/exp_t2ctl/v1", "PASS", "review 2: valid"),
    (f"{W}/exp_t2ctl/v2", "PASS", "review 2: valid"),
    (f"{W}/exp_t2ctl/v3", "PASS", "review 2: valid"),
    (f"{W}/exp_t2ctl/a1", "PASS", "orchestrator: valid, static method behind an alias"),
    (f"{V}/v_cls", "PASS", "review 3: valid"),
    (f"{V}/v_gen", "PASS", "review 3: valid"),
    (f"{V}/v_partial", "PASS", "review 3: valid"),
    (f"{V}/v_map", "PASS", "review 3: valid"),
    (f"{V}/v_split2", "PASS", "review 3: valid"),
    (f"{V}/v_scan", "PASS", "review 3: valid"),
    (f"{V}/v_wrap", "PASS", "review 3: valid"),
    (f"{W}/exp_prereq/t2/pos", "PASS", "orchestrator: defective behaviour, one shared splitter"),
    (f"{W}/exp_t2ctl/s_led", "PASS", "review 2: wrong convention, one shared splitter"),
    (f"{W}/exp_prereq/t2/base", "FAIL", "baseline: eight independent splitters"),
    (f"{W}/exp_t2ctl/u1", "FAIL", "orchestrator: six per-module copies (F2)"),
    (f"{W}/exp_t2ctl/u2", "FAIL", "orchestrator: six copies in one module (F2)"),
    (f"{W}/exp_t2ctl/u3", "FAIL", "orchestrator: eight splits fixed in place (F1)"),
    (f"{W}/exp_prereq/t2/pos_inline", "FAIL", "orchestrator: three inline splits left (F1)"),
    (f"{V}/u_disp", "FAIL", "review 3: shared entry dispatching to per-site splitters (F3)"),
    (f"{V}/u_hidden_call", "FAIL", "review 3: own splitter effective beside a shared call (F4)"),
    (f"{V}/u_const2", "FAIL", "review 3: eight inline splits sharing one pattern (F5)"),
    (f"{V}/u_allhidden", "FAIL", "review 3: eight partition loops (F1)"),
]


def main(argv):
    base, out, key_path = (pathlib.Path(a).resolve() for a in argv)
    out.mkdir(parents=True, exist_ok=False)
    order = list(range(len(CONTROLS)))
    random.Random(SEED).shuffle(order)
    key = []
    ignore = shutil.ignore_patterns("__pycache__")
    for n, index in enumerate(order, 1):
        source, anchor, origin = CONTROLS[index]
        label = f"k{n:02d}"
        dest = out / label
        subprocess.run(["git", "clone", "-q", "--shared", str(base), str(dest)], check=True,
                       stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        shutil.rmtree(dest / "scripts")
        shutil.copytree(pathlib.Path(source) / "scripts", dest / "scripts", ignore=ignore)
        key.append({"label": label, "source": source, "anchor": anchor, "origin": origin})
    subprocess.run(["git", "clone", "-q", "--shared", str(base), str(out / "baseline")], check=True,
                   stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    key_path.write_text(json.dumps({"seed": SEED, "trees": key}, indent=1) + "\n", encoding="utf-8")
    print(len(key), "trees;", sum(k["anchor"] == "PASS" for k in key), "PASS anchors;",
          sum(k["anchor"] == "FAIL" for k in key), "FAIL anchors")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
