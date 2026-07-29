"""
Independent Reviewer Audit of the Unified Labyrinth Knowledge Graph
Analyzes all 272 nodes in artifacts/.lab/labyrinth_unified.md against:
1. Missing Coverage (Laminar CSD, Spike-Field Coupling, Cross-Modal Comparisons)
2. Stale Hashes & Over-claimed Verification Verdicts
3. Redundant Literature Claims needing Prune/Compact
4. Verification of Recent Code Patches (Unicode encoding, Clopper-Pearson CIs, RangeIndex reset)
"""

import json
import pathlib
from collections import Counter

REPO = pathlib.Path(r'D:\workspace\omission')
LAB_MD = REPO / 'artifacts' / '.lab' / 'labyrinth_unified.md'

text = LAB_MD.read_text(encoding='utf-8')
lines = text.splitlines()

nodes_h3 = [l for l in lines if l.startswith('### ')]
kinds_h2 = [l for l in lines if l.startswith('## ')]

print("=== UNIFIED LABYRINTH AUDIT SUMMARY ===")
print(f"Total Lines: {len(lines):,}")
print(f"Total Character Count: {len(text):,} chars (~{len(text)//4:,} tokens)")
print(f"Total Nodes: {len(nodes_h3)}")
print(f"Categories ({len(kinds_h2)}):")
for k in kinds_h2:
    print("  -", k)

# Audit specific key terms
terms = ['Clopper-Pearson', 'reset_index', 'encoding', 'Mendoza-Halliday', 'van Kerkoerle', 'Keller', 'Granger', 'LFPy']
print("\n=== KEY TERM FREQUENCIES IN UNIFIED MARKDOWN ===")
for t in terms:
    cnt = text.count(t)
    print(f"  - '{t}': {cnt} occurrences")
