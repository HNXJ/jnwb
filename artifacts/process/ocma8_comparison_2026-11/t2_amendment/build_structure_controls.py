r"""Build the structure controls of amendment 2 for experiment task t2.

Usage: python build_structure_controls.py <baseline tree> <corrected reference tree> <out dir>

Each control is a `git clone --shared` of the baseline tree (ac995dde) with scripts/ rewritten:
  u1  the corrected reference with its shared splitter copied into each of the six modules (six independent
      definitions, the shared module unused). Behaviour of the corrected reference; not consolidated.
  u2  the corrected reference with six independent copies of the splitter in the one module scripts/md_cells.py,
      one per reader module. Behaviour of the corrected reference; not consolidated.
  u3  the baseline with each of its eight splits changed in place to split on unescaped pipes only.
      Eight independent splitters under their baseline names.
  a1  the corrected reference with the splitter as a static method reached through a module-level attribute
      alias (`split_cells = Row.cells`), a delegation the checker does not resolve. Consolidated.
Bytes in, bytes out; every replacement asserts its count.
"""

import pathlib
import re
import subprocess
import sys

MODULES = ("build_dashboard", "build_fact_graph", "docs_form_gate", "learning_gate", "reconstruct_state",
           "release_gate")
IMPORT = re.compile(rb"^from scripts\.md_cells import split_cells(?P<tail>[^\r\n]*)(?P<nl>\r?\n)", re.M)
SPLIT = re.compile(rb'(?P<body>[A-Za-z_]+(?:\.strip\(\))?\.strip\("\|"\))\.split\("\|"\)')


def clone(base, out):
    subprocess.run(["git", "clone", "-q", "--shared", str(base), str(out)], check=True, stdin=subprocess.DEVNULL)


def splitter_source(reference, name):
    """The def of the reference splitter, renamed, as bytes with the file's own newlines."""
    source = (reference / "scripts" / "md_cells.py").read_bytes()
    start = source.index(b"def split_cells(")
    return source[start:].replace(b"def split_cells(", b"def " + name + b"(", 1)


def from_reference(reference, out):
    for module in MODULES:
        (out / "scripts" / f"{module}.py").write_bytes((reference / "scripts" / f"{module}.py").read_bytes())
    (out / "scripts" / "md_cells.py").write_bytes((reference / "scripts" / "md_cells.py").read_bytes())


def swap_import(path, replacement):
    source = path.read_bytes()
    found = IMPORT.findall(source)
    assert len(found) == 1, (path, len(found))
    path.write_bytes(IMPORT.sub(lambda m: replacement(m.group("nl")), source, count=1))


def build_u1(base, reference, out):
    clone(base, out)
    from_reference(reference, out)
    (out / "scripts" / "md_cells.py").unlink()
    body = splitter_source(reference, b"split_cells")
    for module in MODULES:
        swap_import(out / "scripts" / f"{module}.py", lambda nl: nl + nl + body.rstrip() + nl + nl + nl)


def build_u2(base, reference, out):
    clone(base, out)
    from_reference(reference, out)
    path = out / "scripts" / "md_cells.py"
    source = path.read_bytes()
    nl = b"\r\n" if b"\r\n" in source else b"\n"
    head = source[:source.index(b"def split_cells(")]
    parts = [splitter_source(reference, b"split_cells_%d" % (i + 1)).rstrip() for i in range(len(MODULES))]
    path.write_bytes(head + (nl * 3).join(parts) + nl)
    for i, module in enumerate(MODULES):
        swap_import(out / "scripts" / f"{module}.py", lambda line_nl, i=i: (
            b"from scripts.md_cells import split_cells_%d as split_cells  # noqa: E402" % (i + 1) + line_nl))


def build_u3(base, out):
    clone(base, out)
    total = 0
    for module in MODULES:
        path = out / "scripts" / f"{module}.py"
        source, n = SPLIT.subn(lambda m: b're.split(r"(?<!\\\\)\\|", ' + m.group("body") + b")", path.read_bytes())
        path.write_bytes(source)
        total += n
    assert total == 7, total  # the eighth site (build_dashboard._cells) already splits on unescaped pipes


def build_a1(base, reference, out):
    clone(base, out)
    from_reference(reference, out)
    path = out / "scripts" / "md_cells.py"
    source = path.read_bytes()
    nl = b"\r\n" if b"\r\n" in source else b"\n"
    start = source.index(b"def split_cells(")
    body = source[start:].replace(b"def split_cells(", b"def cells(", 1)
    indented = nl.join((b"    " + line if line.strip() else line) for line in body.rstrip().split(nl))
    path.write_bytes(source[:start] + b"class Row:" + nl + b"    @staticmethod" + nl + indented + nl)
    for module in MODULES:
        swap_import(out / "scripts" / f"{module}.py", lambda line_nl: (
            b"from scripts.md_cells import Row  # noqa: E402" + line_nl + b"split_cells = Row.cells" + line_nl))


def main(argv):
    if len(argv) != 3:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    base, reference, out = (pathlib.Path(a).resolve() for a in argv)
    out.mkdir(parents=True, exist_ok=True)
    build_u1(base, reference, out / "u1")
    build_u2(base, reference, out / "u2")
    build_u3(base, out / "u3")
    build_a1(base, reference, out / "a1")
    for name in ("u1", "u2", "u3", "a1"):
        status = subprocess.run(["git", "-C", str(out / name), "status", "--porcelain"], check=True,
                                capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.split("\n")
        print(name, len([s for s in status if s]), "paths changed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
