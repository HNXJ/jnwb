"""
Independent Labyrinth Graph Auditor
Analyzes graph for:
1. Missing coverage (domain gaps)
2. Stale / outdated claims and unnormalized schema fields
3. Redundant / duplicated nodes needing Prune/Compact
"""

import json
import pathlib
from collections import Counter

REPO = pathlib.Path(r'D:\workspace\omission')
lab_dir = REPO / 'artifacts' / '.lab'

files = [f for f in lab_dir.glob('*.json') if not f.name.startswith('labyrinth_unified')]
nodes = []
for f in files:
    try:
        data = json.loads(f.read_text(encoding='utf-8'))
        nodes.append(data)
    except Exception as e:
        pass

print(f"Total Nodes Analyzed: {len(nodes)}")

# 1. Non-schema v3 kinds (unnormalized)
non_schema_kinds = [n for n in nodes if n.get('kind') not in ('hypothesis', 'evidence', 'goal', 'plan', 'reflection', 'question', 'note', 'decision', 'checkpoint')]
print(f"\n1. Non-Schema v3 Kinds ({len(non_schema_kinds)} nodes):")
for n in non_schema_kinds:
    print(f"   - `{n.get('id')}`: kind='{n.get('kind')}' | title: {n.get('title','')[:50]}")

# 2. Check for empty notes or generic titles
empty_notes = [n for n in nodes if not n.get('notes') and not n.get('plan') and not n.get('description')]
print(f"\n2. Empty / Sparse Content Nodes ({len(empty_notes)} nodes):")
for n in empty_notes:
    print(f"   - `{n.get('id')}`: {n.get('title','')[:60]}")

# 3. Check redundant PRP plan nodes vs live plans.json
with open(REPO / 'artifacts/developer/plans.json', 'r', encoding='utf-8') as f:
    plans_data = json.load(f)
prp_plan_titles = {p.get('title') for p in plans_data.get('items', [])}

prp_nodes = [n for n in nodes if n.get('kind') in ('plan', 'prp_item') or n.get('id','').startswith('prp-plan')]
print(f"\n3. PRP Plan Nodes ({len(prp_nodes)} total):")

# 4. Verification verdict breakdown
verdicts = Counter()
for n in nodes:
    ver = n.get('verification', {})
    if isinstance(ver, dict):
        v = ver.get('verdict', 'unverified')
        verdicts[v] += 1
    else:
        verdicts['unverified'] += 1
print(f"\n4. Verification Verdict Breakdown: {dict(verdicts)}")
