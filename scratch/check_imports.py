"""Full pipeline import scan — checks all imports in run_pipeline.py."""
import importlib, re
from pathlib import Path

pipeline = Path('src/scripts/run_pipeline.py').read_text()
imports = re.findall(r'from (src\.[^\s]+) import (\w+)', pipeline)

ok = []
broken = []
for mod, sym in imports:
    try:
        m = importlib.import_module(mod)
        getattr(m, sym)
        ok.append((mod, sym))
    except Exception as e:
        broken.append((mod, sym, type(e).__name__, str(e)[:100]))

print(f"OK: {len(ok)}  BROKEN: {len(broken)}")
if broken:
    print()
    for b in broken:
        print(f"BROKEN  {b[0]}  ({b[1]})  => {b[2]}: {b[3]}")
else:
    print("All pipeline imports clean.")
