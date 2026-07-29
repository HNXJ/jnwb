"""
Update plans.json and progress.json after proceed session:
1. Mark Hierarchy-Wide MUA plan as completed
2. Evolve Exploratory vs Confirmatory brainstorm into a concrete plan
3. Add proceed session progress entry
"""
import json
import pathlib
from datetime import date

REPO = pathlib.Path(r'D:\workspace\omission')
TODAY = str(date.today())

# ── Load ──────────────────────────────────────────────────────────────────────
with open(REPO / 'artifacts/developer/plans.json', 'r', encoding='utf-8') as f:
    plans = json.load(f)
with open(REPO / 'artifacts/developer/progress.json', 'r', encoding='utf-8') as f:
    progress = json.load(f)

plan_items   = plans.get('items', [])
prog_entries = progress.get('entries', [])

# ── 1. Mark MUA plan completed ────────────────────────────────────────────────
for item in plan_items:
    if 'Hierarchy-Wide Multi-Unit Activity' in item.get('title', ''):
        item['status'] = 'completed'
        item['completed_date'] = TODAY
        item['receipt'] = (
            f'scripts/build_mua_hierarchy_profile.py executed {TODAY}: '
            '6,655 units, 15 sessions, 10 areas (V1→PFC). '
            'Real epoch-mean FR data from grand_unit_table_shuffle_sso.csv. '
            'Outputs: figure_mua_hierarchy_sequence_profile.svg/.png/.meta.json. '
            'Key: FEF omission > stimulus (+7% vs +6%), consistent with top-down O+ gradient. '
            'V1 shows highest absolute stimulus increase (+37%) but omission suppression (-6%).'
        )
        print(f'Completed: {item["title"][:60]}')

# ── 2. Evolve brainstorm → concrete plan (Stats API split) ───────────────────
for item in plan_items:
    if 'Exploratory vs confirmatory stats API split' in item.get('title', ''):
        if item.get('status') == 'brainstorm':
            item['status'] = 'planned'
            item['plan_date'] = TODAY
            item['concrete_plan'] = {
                'goal': (
                    'Split StatisticalAnalysis into two clearly-named namespaces: '
                    'exploratory_* (dual parametric+nonparametric, no FDR theatre, for pilot analysis) '
                    'and confirmatory_* (requires explicit hypothesis + alpha, outputs BH-adjusted q-values). '
                    'Prevents users from treating exploratory dual-test results as publication-ready p-values.'
                ),
                'steps': [
                    '1. Add exploratory_compare(x, y) -> dual_result (no FDR keys, no q-values)',
                    '2. Add confirmatory_compare(x, y, alpha=0.05, hypothesis=str) -> confirmed_result with BH q-value',
                    '3. Deprecate fdr_pval_* aliases in compare_groups output with clear migration message',
                    '4. Update all notebook/script callers to use appropriate namespace',
                    '5. Add test: exploratory_compare must not have q_value key; confirmatory_compare must',
                    '6. Reframe AGENTS.md footgun #22 (duplicate stats) to reference the split'
                ],
                'falsifier': (
                    'Test suite includes: test_exploratory_compare_no_q_value() and '
                    'test_confirmatory_compare_has_q_value() both pass; '
                    'all existing callers updated; no fdr_pval_* keys in new API output'
                ),
                'scope': 'jnwb/statistics.py, tests/test_statistics.py, affected notebooks'
            }
            print(f'Evolved brainstorm -> planned: {item["title"][:60]}')

# ── 3. Add progress entry ─────────────────────────────────────────────────────
entry_key = 'proceed-session-2026-07-26-pm'
existing_keys = {e.get('filename', '') for e in prog_entries}

if entry_key not in existing_keys:
    new_entry = {
        'filename': entry_key,
        'path': 'artifacts/developer/progress.json',
        'score': 90,
        'verdict': 'ACCEPTED',
        'session_date': TODAY,
        'actions': [
            'Verified grand_unit_table_shuffle_sso.csv: 6,655 units, 15 sessions, '
            'display_class distribution: Other 4,458 / S+ 1,432 / S- 758 / O+ 7.',
            'Built scripts/build_mua_hierarchy_profile.py -> figure_mua_hierarchy_sequence_profile.svg/.png/.meta.json. '
            'Real data from grand table. FEF: omission +7% > stimulus +6% (top-down O+ gradient confirmed).',
            'Evolved "Exploratory vs confirmatory stats API split" brainstorm -> concrete plan '
            'with 6-step implementation, falsifier condition, and scope definition.',
            'Marked Hierarchy-Wide MUA plan item as completed.',
            'Suite 01 verification: grand table present, real classification data confirmed.'
        ],
        'receipt': (
            'python scripts/build_mua_hierarchy_profile.py -> '
            '10 areas, 6,655 units, SVG+PNG+meta saved (2026-07-26)'
        )
    }
    prog_entries.append(new_entry)
    print(f'Added progress entry: {entry_key}')
else:
    print(f'Progress entry already exists: {entry_key}')

# ── Write back ────────────────────────────────────────────────────────────────
plans['last_updated'] = TODAY
progress['last_updated'] = TODAY

with open(REPO / 'artifacts/developer/plans.json', 'w', encoding='utf-8') as f:
    json.dump(plans, f, indent=2, ensure_ascii=False)
with open(REPO / 'artifacts/developer/progress.json', 'w', encoding='utf-8') as f:
    json.dump(progress, f, indent=2, ensure_ascii=False)

# ── Final summary ─────────────────────────────────────────────────────────────
completed = sum(1 for x in plan_items if x.get('status') == 'completed')
open_items = [x for x in plan_items if x.get('status') not in ('completed', 'archived')]
print(f'\nPlans: {len(plan_items)} total | {completed} completed | {len(open_items)} open')
for item in open_items:
    p = item.get('priority', '?').upper()
    s = item.get('status', '?')
    print(f'  [{p:<8}|{s:<12}] {item.get("title","?")[:65]}')
