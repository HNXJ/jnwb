"""Build probe trees: clone base --shared, apply pos2.diff, apply a variant. Usage: build.py name [name...]"""
import pathlib
import re
import shutil
import subprocess
import sys

S = pathlib.Path(r"D:/tmp/claude/acfe204914b1181d/30cef652-1268-5f7a-911c-87a2f8fc2c76/scratchpad/rev_t2c")
BASE = r"D:/repos/_work/exp_prereq/t2/base"
DIFF = r"D:/repos/_work/jnwb_pilot_rec/artifacts/process/ocma8_comparison_2026-11/t2_amendment/pos2.diff"
TREES = S / "trees"
SITES = ["build_dashboard", "build_fact_graph", "docs_form_gate", "learning_gate", "reconstruct_state", "release_gate"]


def run(*cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    if p.returncode:
        raise SystemExit(f"{cmd}: {p.stdout}{p.stderr}")
    return p.stdout


def rd(t, rel):
    return (t / rel).read_bytes().decode("utf-8")


def wr(t, rel, text):
    p = t / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))


def sub(t, rel, old, new, count=1):
    s = rd(t, rel)
    assert s.count(old) >= 1, (rel, old)
    if count:
        assert s.count(old) == count, (rel, old, s.count(old))
    wr(t, rel, s.replace(old, new))


def sub_all_sites(t, old, new):
    for m in SITES:
        s = rd(t, f"scripts/{m}.py")
        wr(t, f"scripts/{m}.py", s.replace(old, new))


def fresh(name):
    t = TREES / name
    if t.exists():
        raise SystemExit(f"{t} exists")
    run("git", "clone", "-q", "--shared", BASE, str(t))
    run("git", "-C", str(t), "apply", "--whitespace=nowarn", DIFF)
    return t


# ---------------------------------------------------------------- valid variants

def v_cls(t):
    wr(t, "scripts/mdtable/__init__.py", "")
    wr(t, "scripts/mdtable/rows.py", '''"""Markdown row splitting as an object."""
import re


class RowSplitter:
    _pipe = re.compile(r"(?<!\\\\)\\|")

    def cells(self, line, keep_outer=False):
        body = line if keep_outer else line.strip().strip("|")
        return [c.strip() for c in self._pipe.split(body)]


ROWS = RowSplitter()
''')
    (t / "scripts/md_cells.py").unlink()
    for m in SITES:
        p = f"scripts/{m}.py"
        s = rd(t, p)
        s = s.replace("from scripts.md_cells import split_cells", "from scripts.mdtable.rows import ROWS")
        s = s.replace("split_cells(", "ROWS.cells(")
        wr(t, p, s)


def v_gen(t):
    wr(t, "scripts/md_cells.py", '''"""One row splitter, as a generator over finditer."""
import re

_CELL = re.compile(r"((?:\\\\.|[^|\\\\])*)(?:\\||$)", re.S)


def iter_cells(body):
    pos = 0
    n = len(body)
    while True:
        m = _CELL.match(body, pos)
        yield m.group(1).strip()
        pos = m.end()
        if m.end() >= n and not body.endswith("|"):
            return
        if pos >= n:
            if body.endswith("|") and not body.endswith("\\\\|"):
                yield ""
            return


def split_cells(line, *, keep_outer=False):
    body = line if keep_outer else line.strip().strip("|")
    return list(iter_cells(body))
''')


def v_partial(t):
    s = rd(t, "scripts/md_cells.py")
    wr(t, "scripts/md_cells.py", s.replace("import re\n", "import functools\nimport re\n") +
       "\n\nsplit_cells_outer = functools.partial(split_cells, keep_outer=True)\n")
    sub(t, "scripts/build_dashboard.py", "from scripts.md_cells import split_cells  # noqa: E402",
        "from scripts.md_cells import split_cells_outer  # noqa: E402")
    sub(t, "scripts/build_dashboard.py", "split_cells(line, keep_outer=True)[1:-1]", "split_cells_outer(line)[1:-1]")


def v_map(t):
    # release_gate and learning_gate reach the splitter through map(), the function passed not called
    sub(t, "scripts/release_gate.py", "    return split_cells(stripped)", "    return next(map(split_cells, [stripped]))")
    sub(t, "scripts/release_gate.py", "    return split_cells(body)", "    return next(map(split_cells, [body]))")


def v_wrap(t):
    # baseline names kept as wrappers; sentinel splitter
    wr(t, "scripts/md_cells.py", '''"""Sentinel splitter."""
_ESC = "\\x00"


def split_cells(line, *, keep_outer=False):
    body = line if keep_outer else line.strip().strip("|")
    parts = body.replace("\\\\|", _ESC).split("|")
    return [p.replace(_ESC, "\\\\|").strip() for p in parts]
''')
    for m, extra in (("build_dashboard", None), ("release_gate", None)):
        s = rd(t, f"scripts/{m}.py")
        s = s.replace("_table_row_cells", "_table_cells").replace("_row_cells", "_cells")
        wr(t, f"scripts/{m}.py", s)
    for m in ("build_fact_graph", "learning_gate"):
        s = rd(t, f"scripts/{m}.py")
        s = s.replace("split_cells(line)", "_cells(line)").replace("split_cells(lines[i])", "_cells(lines[i])")
        s = s.replace("_cells(line)\n", "_cells(line)\n")
        marker = "def _all_tables" if m == "build_fact_graph" else "def ledger_rows"
        s = s.replace(marker, "def _cells(line):\n    return split_cells(line)\n\n\n" + marker, 1)
        wr(t, f"scripts/{m}.py", s)
    s = rd(t, "scripts/build_fact_graph.py")
    s = s.replace("def _cells(line):\n    return _cells(line)", "def _cells(line):\n    return split_cells(line)")
    wr(t, "scripts/build_fact_graph.py", s)
    s = rd(t, "scripts/learning_gate.py")
    s = s.replace("def _cells(line):\n    return _cells(line)", "def _cells(line):\n    return split_cells(line)")
    s = s.replace("set(split_cells(line))", "set(_cells(line))")
    wr(t, "scripts/learning_gate.py", s)


def v_split2(t):
    wr(t, "scripts/tables/__init__.py", "")
    wr(t, "scripts/tables/cells.py", '''"""Two-step row reading in a subpackage."""
import re

_SEP = re.compile(r"(?<!\\\\)\\|")


def _body(line, keep_outer):
    return line if keep_outer else line.strip().strip("|")


def _split_body(body):
    return [c.strip() for c in _SEP.split(body)]


def row_cells(line, *, keep_outer=False):
    return _split_body(_body(line, keep_outer))
''')
    (t / "scripts/md_cells.py").unlink()
    for m in SITES:
        p = f"scripts/{m}.py"
        s = rd(t, p)
        s = s.replace("from scripts.md_cells import split_cells", "from scripts.tables import cells as _tc")
        s = s.replace("split_cells(", "_tc.row_cells(")
        wr(t, p, s)
    # rename three private anchors
    for old, new in (("_all_tables", "_collect_tables"), ("_is_mapping_header", "_is_old_where_now_header"),
                     ("_study_cards", "_cards_for_studies")):
        for m in SITES:
            s = rd(t, f"scripts/{m}.py")
            wr(t, f"scripts/{m}.py", re.sub(rf"\b{old}\b", new, s))


def v_scan(t):
    wr(t, "scripts/md_cells.py", '''"""Character scan splitter with a loop-based outer trim."""


def _trim(body):
    body = body.strip()
    while body and body[0] == "|":
        body = body[1:]
    while body and body[-1] == "|":
        body = body[:-1]
    return body


def split_cells(line, *, keep_outer=False):
    body = line if keep_outer else _trim(line)
    cells, cur = [], []
    prev = ""
    for ch in body:
        if ch == "|" and prev != "\\\\":
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        prev = ch
    cells.append("".join(cur).strip())
    return cells
''')


# ---------------------------------------------------------------- unconsolidated variants

def u_disp(t):
    """shared split_cells with a default branch, plus a per-site registry of independent splitters."""
    wr(t, "scripts/md_cells.py", '''"""Shared entry; per-site splitters are selected by the site tag."""
import re


def _s1(line, keep_outer):
    body = line if keep_outer else line.strip().strip("|")
    return [c.strip() for c in body.replace("\\\\|", "\\x00").translate({124: 1}).split(chr(1))]


def _fix(parts):
    return [p.replace("\\x00", "\\\\|") for p in parts]


_IMPLS = {}
for _tag in ("dash", "fact", "docs", "learn", "state", "rel", "rel2"):
    _IMPLS[_tag] = lambda line, keep_outer, _f=_fix: _f(_s1(line, keep_outer))


def split_cells(line, *, keep_outer=False, site=None):
    impl = _IMPLS.get(site)
    if impl:
        return impl(line, keep_outer)
    body = line if keep_outer else line.strip().strip("|")
    return [cell.strip() for cell in re.split(r"(?<!\\\\)\\|", body)]
''')
    tags = {"build_dashboard": "dash", "build_fact_graph": "fact", "docs_form_gate": "docs",
            "learning_gate": "learn", "reconstruct_state": "state", "release_gate": "rel"}
    for m, tag in tags.items():
        s = rd(t, f"scripts/{m}.py")
        s = re.sub(r"split_cells\(([^()]*)\)", lambda mo: f"split_cells({mo.group(1)}, site={tag!r})", s)
        wr(t, f"scripts/{m}.py", s)


def u_hidden_call(t):
    """each module: shared call whose result is only a fallback, its own translate-based splitter is the one used."""
    for m in SITES:
        p = f"scripts/{m}.py"
        s = rd(t, p)
        helper = '''

def _private_split(line, keep_outer=False):
    shared = split_cells(line, keep_outer=keep_outer)
    body = line if keep_outer else line.strip().strip("|")
    own = [c.replace("\\x00", "\\\\|").strip()
           for c in body.replace("\\\\|", "\\x00").translate({124: 1}).split(chr(1))]
    return own if own else shared
'''
        s = s.replace("split_cells(", "_private_split(")
        # the helper itself must call the real one: restore inside helper
        helper = helper.replace("shared = split_cells(", "shared = split_cells(")
        # place helper right after the import of split_cells
        s = re.sub(r"(from scripts\.md_cells import split_cells[^\n]*\n)", lambda mo: mo.group(1) + "@@HELPER@@", s, count=1)
        assert "@@HELPER@@" in s, m
        s = s.replace("from scripts.md_cells import _private_split", "from scripts.md_cells import split_cells")
        s = s.replace("@@HELPER@@", helper.replace("shared = split_cells(", "shared = _real(") + "\n")
        s = s.replace("from scripts.md_cells import split_cells", "from scripts.md_cells import split_cells as _real", 1)
        wr(t, p, s)


def u_const(t):
    """one shared module-level compiled pattern; eight local functions each split with it."""
    wr(t, "scripts/md_cells.py", '''"""Only the pattern is shared."""
import re

PIPE = re.compile(r"(?<!\\\\)\\|")
''')
    for m in SITES:
        p = f"scripts/{m}.py"
        s = rd(t, p)
        s = s.replace("from scripts.md_cells import split_cells", "from scripts.md_cells import PIPE")
        s = re.sub(r"split_cells\(([^()]*?)(?:, keep_outer=True)?\)",
                   lambda mo: (f"[_c.strip() for _c in PIPE.split({mo.group(1)})]" if "keep_outer" not in mo.group(0)
                               else f"[_c.strip() for _c in PIPE.split({mo.group(1)})]"), s)
        wr(t, p, s)
    # the stripping that split_cells did by default: reinstate per site
    for m in SITES:
        p = f"scripts/{m}.py"
        s = rd(t, p)
        s = re.sub(r"PIPE\.split\((?!line\)\[|stripped|body)([a-z_\[\]]+)\)",
                   lambda mo: f'PIPE.split({mo.group(1)}.strip().strip("|"))', s)
        wr(t, p, s)
    s = rd(t, "scripts/release_gate.py")
    s = s.replace("PIPE.split(stripped)", 'PIPE.split(stripped.strip("|"))').replace("PIPE.split(body)", 'PIPE.split(body.strip("|"))')
    wr(t, "scripts/release_gate.py", s)


def u_allhidden(t):
    """eight independent partition-loop splitters, no shared function at all, each in place."""
    (t / "scripts/md_cells.py").unlink()
    loop = '''
def _part_split(line, keep_outer=False):
    body = line if keep_outer else line.strip().strip("|")
    body = body.replace("\\\\|", "\\x00")
    out = []
    while True:
        head, sep, body = body.partition(chr(124))
        out.append(head.replace("\\x00", "\\\\|").strip())
        if not sep:
            return out
'''
    for m in SITES:
        p = f"scripts/{m}.py"
        s = rd(t, p)
        s = s.replace("from scripts.md_cells import split_cells  # noqa: E402\n", "")
        s = s.replace("from scripts.md_cells import split_cells\n", "")
        s = s.replace("split_cells(", "_part_split(")
        s = s.replace("\nclass ", loop + "\n\nclass ", 1) if "\nclass " in s else s
        if "def _part_split" not in s:
            s = s + "\n" + loop
        wr(t, p, s)


def u_dead_shared(t):
    """shared splitter called at every anchor via a no-op, own findall splitter used."""
    for m in SITES:
        p = f"scripts/{m}.py"
        s = rd(t, p)
        s = s.replace("from scripts.md_cells import split_cells", "from scripts.md_cells import split_cells as _shared")
        helper = '''

def _split_here(line, keep_outer=False):
    _shared(line)  # kept so the shared module stays imported
    body = line if keep_outer else line.strip().strip("|")
    return [c.strip() for c in re.findall(r"((?:\\\\.|[^|\\\\])*)(?:\\||$)", body)][:-1] or [body.strip()]
'''
        s = s.replace("split_cells(", "_split_here(")
        s = re.sub(r"(from scripts\.md_cells import split_cells as _shared[^\n]*\n)", lambda mo: mo.group(1) + helper + "\n", s, count=1)
        if not re.search(r"^import re$", s, re.M):
            s = s.replace(helper.splitlines()[1], "import re as _re_mod\n" + helper.splitlines()[1], 1) if False else s
        wr(t, p, s)


# ---------------------------------------------------------------- wrong behaviour

def w_hdr(t):
    sub(t, "scripts/build_fact_graph.py", "            header = split_cells(line)\n",
        '            header = [c.strip() for c in line.strip().strip("|").split("|")]\n')


def w_bq(t):
    sub(t, "scripts/release_gate.py", 'body = line.lstrip(" \\t>").strip()', 'body = line.lstrip(" \\t").strip()')


def w_maxsplit(t):
    sub(t, "scripts/md_cells.py", 're.split(r"(?<!\\\\)\\|", body)', 're.split(r"(?<!\\\\)\\|", body, maxsplit=15)')


def w_ws(t):
    sub(t, "scripts/md_cells.py", "[cell.strip() for cell in", '[cell.strip(" \\t") for cell in')


VARIANTS = {k[2:] if k.startswith(("v_", "u_", "w_")) else k: v for k, v in globals().items()
            if k.startswith(("v_", "u_", "w_"))}
NAMES = {k: v for k, v in globals().items() if k.startswith(("v_", "u_", "w_"))}


if __name__ == "__main__":
    TREES.mkdir(exist_ok=True)
    for name in sys.argv[1:]:
        t = fresh(name)
        NAMES[name](t)
        print("built", t)
