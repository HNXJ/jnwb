"""Execute every ```python block of one docs page in order, in one namespace.

Usage: python run_page.py <worktree> <page relative to docs/>
"""
import os
import re
import sys
import warnings

WT = os.path.abspath(sys.argv[1])
sys.path.insert(0, WT)
import jnwb  # noqa: E402

assert os.path.normcase(os.path.abspath(jnwb.__file__)).startswith(os.path.normcase(WT))
os.chdir(WT)
page = open(os.path.join(WT, "docs", sys.argv[2]), encoding="utf-8").read()
ns = {}
for i, b in enumerate(re.findall(r"^```python\n(.*?)^```", page, re.M | re.S)):
    warnings.simplefilter("ignore")
    try:
        exec(compile(b, f"<block {i}>", "exec"), ns)
        print(f"--- block {i} ok")
    except Exception as exc:  # report and continue: some pages hold fragments
        print(f"--- block {i} {type(exc).__name__}: {exc}")
