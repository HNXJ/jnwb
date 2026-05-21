"""Regenerate f021/f022 HTML outputs and verify white background pattern."""
import re
from src.f021_madelamo.script import run_f021
from src.f022_madelane.script import run_f022

out21 = run_f021()
out22 = run_f022()
print("F021:", out21)
print("F022:", out22)

white_patterns = [r'"paper_bgcolor":\s*"#?FFFFFF"', r'"paper_bgcolor":\s*"white"']
for path in [out21, out22]:
    content = open(path, encoding="utf-8").read()
    matched = any(re.search(p, content, re.I) for p in white_patterns)
    print(f"WHITE_BG_MATCH {matched}  ...{path[-50:]}")
