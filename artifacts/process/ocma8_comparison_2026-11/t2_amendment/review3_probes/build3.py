import importlib.util
spec = importlib.util.spec_from_file_location("b", r"D:/tmp/claude/acfe204914b1181d/30cef652-1268-5f7a-911c-87a2f8fc2c76/scratchpad/rev_t2c/build.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
t = b.fresh("w_hdr2")
b.sub(t, "scripts/build_fact_graph.py", "            header = split_cells(line)\n",
      '            header = [c.strip() for c in line.strip().strip("|").split(chr(124))]\n')
print("built", t)
