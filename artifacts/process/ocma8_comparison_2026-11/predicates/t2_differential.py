#!/usr/bin/env python3
"""Differential test of the markdown-table readers of a jnwb tree against a baseline tree.

Usage: python t2_differential.py <tree> <baseline tree> [--seed N] [--rows N] [--out FILE]

PRESERVED: no backslash in the input; tree(doc) must equal baseline(doc) exactly.
CORRECTED: one or two escaped pipes (in the data row, or one in the header for the header-escape family);
normalised tree(doc) must equal normalised baseline(doc with each escaped pipe replaced by a backslash + broken bar).
EXPLORATORY: reported apart, never scored: any input of learning.ledger or state.defect whose data row has no
leading pipe, and any input whose header or data row ends (after strip) in an escaped pipe, open or tight form.
Each input is a document for one reader and is run through that reader only.
Standard library only. Child mode (internal): --child <inputs.json> doc|base_doc, cwd = one tree.
"""
import argparse
import contextlib
import dataclasses
import importlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

BSL = chr(92)          # backslash
BROKEN = chr(0x00A6)   # broken bar: an ordinary character standing in for an escaped pipe
DEFAULT_SEED = 2026111600
DEFAULT_ROWS = 300
CHILD_TIMEOUT_S = 900
MODULES = ("build_dashboard", "build_fact_graph", "docs_form_gate", "learning_gate",
           "reconstruct_state", "release_gate")
EXPLORATORY_READERS = ("learning.ledger", "state.defect")
LEADS = ["|", "", "||", "  |", "\t|"]
TRAILS = ["|", "", "||", "| ", "|  |", " |", "\t"]
CELLVARS = ["valid", "too_few", "too_many", "empty_cell", "ws_cell", "last_empty"]
SEPARATORS = ["|---|---|", "|---||", "|---", "||---|---|", "| :--- | ---: |"]
PROSE = ["Prose with a | pipe in it.", "Note: x | y | z"]
PIPE_LINES = ["||", "| | |", "|||||"]
NORM_RE = re.compile(re.escape(BSL) + "[|" + BROKEN + "]" + "|" + "[|" + BROKEN + "]")
TERMINAL_ENDS = (BSL + "|", BSL + "||")   # open form, tight form: a table line ending in an escaped pipe
BLOCKQUOTES = ("> ", ">", "> > ")
WS_PADS = (("nbsp", chr(0x00A0)), ("emsp", chr(0x2003)), ("vtab", chr(0x0B)), ("ff", chr(0x0C)))
# family, share of inputs, modes; one draw per input, before the existing variations
FAMILY_SHARES = (
    ("header_escape", 0.08, ("corrected",)),
    ("blockquote", 0.06, ("preserved", "corrected")),
    ("long_row", 0.05, ("preserved", "corrected")),
    ("ws_pad", 0.06, ("preserved", "corrected")),
    ("open_escape", 0.03, ("corrected",)),
    ("tight_escape", 0.03, ("corrected",)),
    ("wide_table", 0.05, ("preserved", "corrected")),
)


class HarnessError(Exception):
    pass


# name, entry point (report only), document prefix, header cells, valid cell pools (no backslash)
READERS = [
    ("dashboard.deferred", "build_dashboard.deferred_section (ROADMAP)", "",
     ["ID", "Theme", "Defect", "Waits", "Release"],
     [["01-1", "01-4"], ["Tuning (validation)", "Theme one"], ["defect text", "defect one"],
      ["waits on fixture", "waits on one"], ["deferred-0.3.0", "deferred-90.0.0"]]),
    ("dashboard.references", "build_dashboard.references_section (REFERENCES)", "# References\n\n",
     ["Reference", "Result implemented", "Functions"],
     [["Smith 2001 [paper](https://doi.org/10.1000/x1)", "Jones 2002 (no link)"], ["Result A", "Result B"],
      ["`fn_a`", "`fn_b`"]]),
    ("dashboard.order", "build_dashboard.order_section (ORDER_RECORD)", "### `jnwb.fx`\n\n",
     ["spec", "parameter", "sizes", "median times (ms)", "exp", "r2", "t-span", "achieved", "admissible",
      "cls", "gap"],
     [["`fx.f`"], ["`n`"], ["8, 16"], ["1.5, 3.0"], ["1.02", "0.5"], ["0.99"], ["8-16"],
      ["O(n)", "O(n log n)"], ["O(n)"], ["A"], ["0"]]),
    ("dashboard.studies", "build_dashboard.validations_section, studies cards (REFERENCES)", "# References\n\n",
     ["Reference", "Result reproduced", "Receipt"],
     [["Smith 2001", "Jones 2002"], ["Result A", "Result B"],
      ["`tests/test_a.py::test_one`", "`tests/test_b.py::test_two`"]]),
    ("fact.facts", "build_fact_graph.read_facts", "## Boundary\n\n",
     ["ID", "Domain", "Predicate", "Held by", "Ruled"],
     [["`F1`", "`F2`"], ["boundary"], ["the rule holds", "the rule holds too"],
      ["`mod.a`, `mod.b`", "`mod.a`"], ["2026-01-02"]]),
    ("fact.constants", "build_fact_graph.read_constants", "## Constants\n\n",
     ["Constant", "Values", "Ruled"],
     [["`N_BINS`"], ["`8`, `16`", "`4`"], ["2026-01-02"]]),
    ("fact.references", "build_fact_graph.reference_table_rows", "## Methods\n\n",
     ["Reference", "Result implemented", "Functions"],
     [["[Smith 2001](https://doi.org/10.1000/x1)", "[Jones 2002](u)"], ["Result A", "Result B"],
      ["`fn_a`, `fn_b`", "`fn_a`"]]),
    ("learning.ledger", "learning_gate.ledger_rows", "",
     ["Class", "Seen", "Instances"],
     [["cls:alpha", "cls:beta"], ["3", "x"], ["a; b; c", "none"]]),
    ("learning.mapping", "learning_gate.mapping_tables (artifacts/x.md)",
     "Old file: `docs/old.md` at `abc1234`\nDraft: `docs/draft.md`\n\n",
     ["Old location", "Where now"],
     [["`a`", "`docs/old.md`"], ["`b`", "`docs/draft.md`"]]),
    ("release.roadmap", "release_gate.roadmap_rows", "",
     ["ID", "Theme", "Defect", "Waits", "Release"],
     [["01-1", "01-5"], ["Theme one", "Theme two"], ["defect one"], ["waits on one"],
      ["deferred-90.0.0", "deferred-0.3.0"]]),
    ("release.table_data", "release_gate.table_data_rows", "",
     ["ID", "Note"],
     [["P-1", "-", "02"], ["open", "none yet"]]),
    ("docs.vocabulary", "docs_form_gate.parse_vocabulary", "# Contract\n\n## Vocabulary\n\n",
     ["Concept", "Preferred", "Superseded"],
     [["normalisation", "spike"], ["`normalize`", "`spike`"], ["`normalise`", "`spk`"]]),
    ("state.defect", "reconstruct_state.open_defect_classes (defect_classes.md)", "",
     ["Class", "Seen", "a", "b", "c", "Status"],
     [["alpha:R1", "gamma:R3"], ["3", "1"], ["a"], ["b"], ["c"], ["open", "repaired", "repaired 2026-11-01"]]),
]


# ---------------------------------------------------------------- generator

def render(cells, lead, trail, tab, pad=None):
    if pad is None:
        pad = "\t" if tab else " "
    return lead + "|".join(pad + cell + pad for cell in cells) + trail


def canonical_sep(n):
    return "|" + "|".join(["---"] * n) + "|"


def pick_variant(rng):
    return rng.choice(CELLVARS), rng.choice(LEADS), rng.choice(TRAILS), rng.random() < 0.2


def vary_cells(cells, cellv, rng):
    cells = list(cells)
    if cellv == "too_few":
        del cells[rng.randrange(len(cells))]
    elif cellv == "too_many":
        cells.insert(rng.randrange(len(cells) + 1), "extra")
    elif cellv == "empty_cell":
        cells[rng.randrange(len(cells))] = ""
    elif cellv == "ws_cell":
        cells[rng.randrange(len(cells))] = "  "
    elif cellv == "last_empty":
        cells[-1] = ""
    return cells


def insert_escapes(cells, k, rng):
    """Insert k escaped pipes inside non-empty cells; positions are read on the original text,
    so a second escape never splits the first."""
    cells = list(cells)
    marks = defaultdict(list)
    for _ in range(k):
        candidates = [j for j, cell in enumerate(cells) if cell.strip()]
        if not candidates:
            raise HarnessError("generator: no non-empty cell to hold an escaped pipe")
        j = rng.choice(candidates)
        text = cells[j]
        lo = len(text) - len(text.lstrip())
        hi = len(text.rstrip())
        marks[j].append(rng.randint(lo, hi))
    for j, positions in marks.items():
        text = cells[j]
        for p in sorted(positions, reverse=True):
            text = text[:p] + BSL + "|" + text[p:]
        cells[j] = text
    return cells


def whole_line(rng):
    draw = rng.random()
    if draw < 0.5:
        return rng.choice(PROSE), "prose"
    if draw < 0.75:
        return "", "blank"
    return rng.choice(PIPE_LINES), "pipes"


def pick_family(mode, rng):
    """One draw per input: the new variation family it carries, or None (existing variations only)."""
    draw = rng.random()
    edge = 0.0
    for family, share, modes in FAMILY_SHARES:
        if mode in modes:
            edge += share
            if draw < edge:
                return family
    return None


def insert_header_escape(cells, rng):
    """One escaped pipe inside a non-empty header cell, strictly before the cell's stripped end."""
    cells = list(cells)
    j = rng.choice([j for j, cell in enumerate(cells) if cell.strip()])
    text = cells[j]
    lo = len(text) - len(text.lstrip())
    hi = len(text.rstrip())
    p = rng.randint(lo + 1, hi - 1) if hi - lo >= 2 else lo
    cells[j] = text[:p] + BSL + "|" + text[p:]
    return cells


def terminal_row(cells, tight, tab):
    """Data row whose last cell ends in an escaped pipe: open form, or tight form (one closing pipe, no space)."""
    pad = "\t" if tab else " "
    head = "|" + "|".join(pad + cell + pad for cell in cells[:-1]) + "|"
    return head + pad + cells[-1] + BSL + "|" + ("|" if tight else "")


def make_input(name, prefix, header_cells, pools, mode, rng, rid):
    labels = []
    valid = [rng.choice(pool) for pool in pools]
    header = render(header_cells, "|", "|", False)
    sep = canonical_sep(len(header_cells))
    family = pick_family(mode, rng)
    quote = ""
    if family is not None:
        labels.append(f"fam={family}")
    if family == "blockquote":  # the existing variations below, each table line prefixed
        quote = rng.choice(BLOCKQUOTES)
        labels.append(f"bq={quote!r}")
    escapes = 0
    if family == "header_escape":  # the header carries one escape; the data row is valid
        header = render(insert_header_escape(header_cells, rng), "|", "|", False)
        row = render(valid, "|", "|", False)
        escapes = 1
        labels.append("part=header")
    elif family in ("open_escape", "tight_escape"):  # terminal escaped pipe: exploratory for every reader
        row = terminal_row(valid, family == "tight_escape", rng.random() < 0.2)
        escapes = 1
        labels.append("part=row")
    elif family == "wide_table":  # header, separator and data row all gain 13 to 20 cells
        extra = rng.randint(13, 20)
        header = render(list(header_cells) + [f"h{i}" for i in range(1, extra + 1)], "|", "|", False)
        sep = canonical_sep(len(header_cells) + extra)
        cells = valid + [f"c{i}" for i in range(1, extra + 1)]
        labels.append("part=table")
        if mode == "corrected":
            escapes = rng.choice((1, 2))
            cells = insert_escapes(cells, escapes, rng)
            labels.append(f"escapes={escapes}")
        row = render(cells, "|", "|", False)
    elif family in ("long_row", "ws_pad"):
        cells, pad = valid, None
        if family == "long_row":  # 4 to 20 extra cells appended to the data row
            cells = valid + [f"extra{i}" for i in range(1, rng.randint(4, 20) + 1)]
        else:  # one whitespace character as the cell padding on both sides of every cell
            ws_name, pad = rng.choice(WS_PADS)
            labels.append(f"ws={ws_name}")
        labels.append("part=row")
        if mode == "corrected":
            escapes = rng.choice((1, 2))
            cells = insert_escapes(cells, escapes, rng)
            labels.append(f"escapes={escapes}")
        row = render(cells, "|", "|", False, pad)
    else:  # existing variations
        draw = rng.random()
        if draw < 0.15:  # header or separator carries the variation; the data row is valid
            cells = valid
            if mode == "corrected":
                k = rng.choice((1, 2))
                cells = insert_escapes(cells, k, rng)
                escapes = k
                labels.append(f"escapes={k}")
            row = render(cells, "|", "|", False)
            if rng.random() < 0.5:
                cellv, lead, trail, tab = pick_variant(rng)
                header = render(vary_cells(header_cells, cellv, rng), lead, trail, tab)
                labels += ["part=header", f"hcell={cellv}", f"hlead={lead!r}", f"htrail={trail!r}", f"htab={tab}"]
            else:
                sep = rng.choice(SEPARATORS)
                labels.append("part=separator")
        elif mode == "preserved" and rng.random() < 0.16:  # whole line: prose, blank, pipes only
            row, kind = whole_line(rng)
            labels += ["part=whole", f"whole={kind}"]
        else:  # one generated data row
            cellv, lead, trail, tab = pick_variant(rng)
            cells = vary_cells(valid, cellv, rng)
            labels += ["part=row", f"cell={cellv}", f"lead={lead!r}", f"trail={trail!r}", f"tab={tab}"]
            if mode == "corrected":
                k = rng.choice((1, 2))
                cells = insert_escapes(cells, k, rng)
                escapes = k
                labels.append(f"escapes={k}")
            row = render(cells, lead, trail, tab)
    doc = prefix + quote + header + "\n" + quote + sep + "\n" + quote + row + "\n"
    if mode == "corrected":
        n = doc.count(BSL + "|")
        base_doc = doc.replace(BSL + "|", BSL + BROKEN)
        if not (n == escapes and n >= 1 and doc.count(BSL) == n and base_doc.count(BSL) == n
                and base_doc.count(BSL + "|") == 0 and base_doc.count(BROKEN) == n):
            raise HarnessError(f"generator: escape bookkeeping failed for {rid}: generated={escapes} n={n} "
                               f"doc={doc.count(BSL)} base={base_doc.count(BSL)} "
                               f"base_pipe={base_doc.count(BSL + '|')} base_broken={base_doc.count(BROKEN)} "
                               f"doc={doc!r}")
    else:
        base_doc = doc
        if BSL in doc:
            raise HarnessError(f"generator: backslash in a preserved input {rid}")
    terminal = any(line.strip().endswith(TERMINAL_ENDS) for line in (header, row))
    exploratory = terminal or (name in EXPLORATORY_READERS and not row.lstrip().startswith("|"))
    return {"id": rid, "mode": mode, "reader": name, "bucket": "exploratory" if exploratory else mode,
            "row": quote + row, "doc": doc, "base_doc": base_doc, "labels": labels}


def generate(seed, rows):
    inputs = []
    for mode in ("preserved", "corrected"):
        for name, _entry, prefix, header_cells, pools in READERS:
            rng = random.Random(f"{seed}|{mode}|{name}")
            for index in range(rows):
                inputs.append(make_input(name, prefix, header_cells, pools, mode, rng,
                                         f"{mode}|{name}|{index:05d}"))
    return inputs


# ---------------------------------------------------------------- child side (runs in one tree)

@contextlib.contextmanager
def patched(obj, **attrs):
    saved = {}
    for name, value in attrs.items():
        if not hasattr(obj, name):
            raise AttributeError(f"{obj.__name__} has no attribute {name}")
        saved[name] = getattr(obj, name)
        setattr(obj, name, value)
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(obj, name, value)


def to_json(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): to_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((to_json(v) for v in value), key=repr)
    if isinstance(value, os.PathLike):
        return os.fspath(value)
    if hasattr(value, "_asdict"):
        return to_json(value._asdict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_json({f.name: getattr(value, f.name) for f in dataclasses.fields(value)})
    if hasattr(value, "__dict__"):
        return to_json(dict(vars(value)))
    raise TypeError(f"result of type {type(value).__name__} is not serialisable")


def run_reader_call(thunk):
    """Run the reader's entry point; a raise is reported by class name only."""
    try:
        value = thunk()
    except KeyboardInterrupt:
        raise
    except BaseException as exc:  # a reader's own failure is data
        return {"raises": type(exc).__name__}
    return to_json(value)


def put(directory, name, text):
    path = Path(directory) / name
    path.write_text(text, encoding="utf-8")
    return path


def ad_dashboard_deferred(text, scratch, mods):
    bd = mods["build_dashboard"]
    path = put(scratch, "roadmap.md", text)
    with patched(bd, ROADMAP=path):
        return run_reader_call(bd.deferred_section)


def ad_dashboard_references(text, scratch, mods):
    bd = mods["build_dashboard"]
    path = put(scratch, "references.md", text)
    with patched(bd, REFERENCES=path):
        return run_reader_call(bd.references_section)


def ad_dashboard_order(text, scratch, mods):
    bd = mods["build_dashboard"]
    path = put(scratch, "computational_order.md", text)
    with patched(bd, ORDER_RECORD=path):
        return run_reader_call(bd.order_section)


def ad_dashboard_studies(text, scratch, mods):
    bd = mods["build_dashboard"]
    path = put(scratch, "references.md", text)
    with patched(bd, REFERENCES=path, _receipt=lambda p, card: p.name, _git=lambda *args: "a" * 40,
                 CALIBRATION_RECEIPTS=(), _performance_cards=lambda: [], _frozen_card=lambda: {"id": "frozen"},
                 _closure_card=lambda: {"id": "closure"}, VALIDATION_HTML=Path(scratch) / "no_html"):
        def studies():
            cards = bd.validations_section()
            return [(c["id"], c["title"], c["fields"]) for c in cards if c["id"].startswith("studies-")]
        return run_reader_call(studies)


def ad_fact_facts(text, scratch, mods):
    return run_reader_call(lambda: mods["build_fact_graph"].read_facts(text))


def ad_fact_constants(text, scratch, mods):
    return run_reader_call(lambda: mods["build_fact_graph"].read_constants(text))


def ad_fact_references(text, scratch, mods):
    return run_reader_call(lambda: mods["build_fact_graph"].reference_table_rows(text))


def ad_ledger(text, scratch, mods):
    return run_reader_call(lambda: mods["learning_gate"].ledger_rows(text))


def ad_mapping(text, scratch, mods):
    root = Path(scratch) / "mapping_root"
    (root / "artifacts").mkdir(parents=True, exist_ok=True)
    put(root / "artifacts", "x.md", text)
    return run_reader_call(lambda: mods["learning_gate"].mapping_tables(root))


def ad_roadmap(text, scratch, mods):
    return run_reader_call(lambda: mods["release_gate"].roadmap_rows(text))


def ad_table_data(text, scratch, mods):
    return run_reader_call(lambda: mods["release_gate"].table_data_rows(text))


def ad_vocabulary(text, scratch, mods):
    return run_reader_call(lambda: mods["docs_form_gate"].parse_vocabulary(text))


def ad_defect(text, scratch, mods):
    path = put(scratch, "defect_classes.md", text)
    return run_reader_call(lambda: mods["reconstruct_state"].open_defect_classes(path))


ADAPTERS = {
    "dashboard.deferred": ad_dashboard_deferred,
    "dashboard.references": ad_dashboard_references,
    "dashboard.order": ad_dashboard_order,
    "dashboard.studies": ad_dashboard_studies,
    "fact.facts": ad_fact_facts,
    "fact.constants": ad_fact_constants,
    "fact.references": ad_fact_references,
    "learning.ledger": ad_ledger,
    "learning.mapping": ad_mapping,
    "release.roadmap": ad_roadmap,
    "release.table_data": ad_table_data,
    "docs.vocabulary": ad_vocabulary,
    "state.defect": ad_defect,
}


def child_main(argv):
    if len(argv) != 2 or argv[1] not in ("doc", "base_doc"):
        print("child usage: --child <inputs.json> doc|base_doc", file=sys.stderr)
        return 2
    inputs_path, field = argv
    tree = Path.cwd().resolve()
    scripts = tree / "scripts"
    sys.path.insert(0, str(tree))
    sys.path.insert(0, str(scripts))
    mods, files = {}, {}
    for name in MODULES:
        mod = importlib.import_module(name)
        origin = Path(mod.__file__).resolve()
        if origin.parent != scripts.resolve():
            print(f"module {name} loaded from {origin}, not from {scripts}", file=sys.stderr)
            return 2
        mods[name] = mod
        files[name] = str(origin)
    records = json.loads(Path(inputs_path).read_text(encoding="utf-8"))
    results = {}
    real_stdout = sys.stdout
    sys.stdout = sys.stderr  # a printing reader must not corrupt the JSON on stdout
    try:
        with tempfile.TemporaryDirectory(prefix="t2diff_child_") as scratch:
            for rec in records:
                results[rec["id"]] = ADAPTERS[rec["reader"]](rec[field], Path(scratch), mods)
    finally:
        sys.stdout = real_stdout
    real_stdout.write(json.dumps({"tree": str(tree), "modules": files, "results": results}, sort_keys=True))
    return 0


# ---------------------------------------------------------------- parent side

def run_child(tree, inputs_path, field):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    cmd = [sys.executable, "-B", os.path.abspath(__file__), "--child", str(inputs_path), field]
    try:
        proc = subprocess.run(cmd, cwd=str(tree), env=env, stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=CHILD_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise HarnessError(f"child for {tree} ({field}) timed out after {CHILD_TIMEOUT_S} s")
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace").splitlines()[-20:]
        raise HarnessError(f"child for {tree} ({field}) exited {proc.returncode}:\n" + "\n".join(tail))
    try:
        return json.loads(proc.stdout.decode("utf-8"))
    except ValueError as exc:
        raise HarnessError(f"child for {tree} ({field}) wrote no JSON document: {exc}")


def norm(value):
    if isinstance(value, str):
        return NORM_RE.sub(BROKEN, value)
    if isinstance(value, list):
        return [norm(v) for v in value]
    if isinstance(value, dict):
        return {norm(k): norm(v) for k, v in value.items()}
    return value


def is_empty(value):
    if value is None:
        return True
    if isinstance(value, list):
        return all(is_empty(v) for v in value)
    if isinstance(value, dict):
        return len(value) == 0
    return False


def classify(inputs, tree_res, base_res):
    stats = {name: Counter() for name, *_ in READERS}
    mismatches = []
    for rec in inputs:
        rid, bucket, name = rec["id"], rec["bucket"], rec["reader"]
        tree_value, base_value = tree_res[rid], base_res[rid]
        if rec["mode"] == "corrected":
            same = norm(tree_value) == norm(base_value)
        else:
            same = tree_value == base_value
        counts = stats[name]
        counts[f"{bucket}.n"] += 1
        if isinstance(base_value, dict) and "raises" in base_value:
            counts[f"{bucket}.raised"] += 1
        elif not is_empty(base_value):
            counts[f"{bucket}.nonempty"] += 1
        if not same:
            counts[f"{bucket}.mismatch"] += 1
            mismatches.append((rec, tree_value, base_value))
    return stats, mismatches


def total(stats, bucket, key):
    return sum(c[f"{bucket}.{key}"] for c in stats.values())


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--child"]:
        return child_main(argv[1:])
    parser = argparse.ArgumentParser(description="Differential test of jnwb table-row readers.")
    parser.add_argument("tree")
    parser.add_argument("baseline")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    if args.rows < 1:
        parser.error("--rows must be at least 1")
    for tree in (args.tree, args.baseline):
        if not (Path(tree) / "scripts").is_dir():
            print(f"usage error: {tree} has no scripts/ directory", file=sys.stderr)
            return 2
    trees = [Path(args.tree).resolve(), Path(args.baseline).resolve()]
    inputs = generate(args.seed, args.rows)
    workdir = Path(tempfile.mkdtemp(prefix="t2diff_run_"))
    try:
        inputs_path = workdir / "inputs.json"
        inputs_path.write_text(json.dumps(inputs, sort_keys=True), encoding="utf-8")
        tree_payload = run_child(trees[0], inputs_path, "doc")
        base_payload = run_child(trees[1], inputs_path, "base_doc")
    except HarnessError as exc:
        print(f"harness error: {exc}", file=sys.stderr)
        return 2
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    tree_res, base_res = tree_payload["results"], base_payload["results"]
    if any(rec["id"] not in tree_res or rec["id"] not in base_res for rec in inputs):
        print("harness error: child results do not cover every input", file=sys.stderr)
        return 2
    stats, mismatches = classify(inputs, tree_res, base_res)

    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
                for rec, tree_value, base_value in mismatches:
                    entry = {"bucket": rec["bucket"], "mode": rec["mode"], "reader": rec["reader"],
                             "row": rec["row"], "document": rec["doc"], "baseline_document": rec["base_doc"],
                             "baseline_result": base_value, "tree_result": tree_value}
                    if rec["mode"] == "corrected":
                        entry["tree_result_norm"] = norm(tree_value)
                        entry["baseline_result_norm"] = norm(base_value)
                    handle.write(json.dumps(entry, sort_keys=True) + "\n")
        except OSError as exc:
            print(f"harness error: cannot write --out: {exc}", file=sys.stderr)
            return 2

    print(f"LOAD tree={tree_payload['tree']} modules={len(tree_payload['modules'])}")
    print(f"LOAD baseline={base_payload['tree']} modules={len(base_payload['modules'])}")
    families = defaultdict(Counter)
    for rec in inputs:
        for label in rec["labels"]:
            key, _, value = label.partition("=")
            families[(rec["mode"], key)][value] += 1
    for (mode, key), counter in sorted(families.items()):
        shown = ", ".join(f"{v}={c}" for v, c in sorted(counter.items()))
        print(f"VARIATION {mode} {key}: {shown}")
    for name, _entry, *_rest in READERS:
        c = stats[name]
        line = " | ".join(
            f"{b} n={c[b + '.n']} mismatch={c[b + '.mismatch']} raised={c[b + '.raised']} "
            f"nonempty={c[b + '.nonempty']}" for b in ("preserved", "corrected", "exploratory"))
        print(f"READER {name} | {line}")
        for b in ("preserved", "corrected"):
            if c[b + ".n"] and not c[b + ".nonempty"]:
                print(f"WARN {name}: no non-empty baseline result in {b} bucket (examined set empty)")
    readers_p = sum(1 for c in stats.values() if c["preserved.n"] > 0)
    readers_c = sum(1 for c in stats.values() if c["corrected.n"] > 0)
    print(f"DIFF preserved readers={readers_p} inputs={total(stats, 'preserved', 'n')} "
          f"mismatches={total(stats, 'preserved', 'mismatch')}")
    print(f"DIFF corrected readers={readers_c} inputs={total(stats, 'corrected', 'n')} "
          f"mismatches={total(stats, 'corrected', 'mismatch')}")
    print(f"DIFF exploratory inputs={total(stats, 'exploratory', 'n')} "
          f"mismatches={total(stats, 'exploratory', 'mismatch')}")
    print(f"DIFF seed={args.seed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
