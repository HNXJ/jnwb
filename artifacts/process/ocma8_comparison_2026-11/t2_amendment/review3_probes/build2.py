import re, sys
sys.argv = [sys.argv[0]]
import importlib.util
spec = importlib.util.spec_from_file_location("b", r"D:/tmp/claude/acfe204914b1181d/30cef652-1268-5f7a-911c-87a2f8fc2c76/scratchpad/rev_t2c/build.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
b.TREES.mkdir(exist_ok=True)
t = b.fresh("u_const2")
b.wr(t, "scripts/md_cells.py", 'import re\n\nPIPE = re.compile(r"(?<!\\)\|")\n')
for m in b.SITES:
    p = f"scripts/{m}.py"
    s = b.rd(t, p)
    s = s.replace("from scripts.md_cells import split_cells", "from scripts.md_cells import PIPE")
    s = s.replace("split_cells(line, keep_outer=True)", "[_c.strip() for _c in PIPE.split(line)]")
    s = re.sub(r"split_cells\(([a-z_\[\]]+)\)", lambda mo: f'[_c.strip() for _c in PIPE.split({mo.group(1)}.strip().strip("|"))]', s)
    assert "split_cells" not in s, m
    b.wr(t, p, s)
print(b.rd(t, "scripts/md_cells.py"))
