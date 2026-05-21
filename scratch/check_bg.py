import os
import re

path = 'outputs/oglo-8figs/f007-sfc'
files = [f for f in os.listdir(path) if f.endswith('.html')]
white_patterns = [r'"paper_bgcolor":\s*"#?FFFFFF"', r'"paper_bgcolor":\s*"white"']

print("Auditing Figure 7 HTML backgrounds:")
for f in sorted(files):
    fpath = os.path.join(path, f)
    mtime = os.path.getmtime(fpath)
    size = os.path.getsize(fpath)
    content = open(fpath, 'r', encoding='utf-8', errors='ignore').read()
    matched = any(re.search(p, content, re.I) for p in white_patterns)
    print(f"File: {f} | Size: {size} | Mtime: {mtime} | Match: {matched}")
