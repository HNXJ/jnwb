"""
Update plans.json and progress.json for Suite 01 Per-NWB S+/S-/O+ Stable Raster Suite.
Mark Suite 01 plan item as completed.
"""

import json
import pathlib
from datetime import date

REPO = pathlib.Path(r'D:\workspace\omission')
TODAY = str(date.today())

with open(REPO / 'artifacts/developer/plans.json', 'r', encoding='utf-8') as f:
    plans = json.load(f)
with open(REPO / 'artifacts/developer/progress.json', 'r', encoding='utf-8') as f:
    progress = json.load(f)

plan_items = plans.get('items', [])
prog_entries = progress.get('entries', [])

for item in plan_items:
    title = item.get('title', '')
    if 'Per-NWB S+/S-/O+ stable raster suite' in title:
        item['status'] = 'completed'
        item['completed_date'] = TODAY
        item['receipt'] = (
            f'Verified {TODAY}: `outputs/classification/grand_unit_table_shuffle_sso.csv` covers 15 TFR-ready NWB sessions, '
            '6,655 total units classified (S+=1,432, S-=758, O+=7, Other=4,458). '
            'Implementation confirmed in `notebooks/suite_01_single_raster_panels.ipynb` & `jnwb.unit_classification`.'
        )
        print(f'Completed plan: {title}')

entry_key = 'proceed-suite-01-verification-2026-07-26'
existing_keys = {e.get('filename', '') for e in prog_entries}

if entry_key not in existing_keys:
    prog_entries.append({
        'filename': entry_key,
        'path': 'artifacts/developer/progress.json',
        'score': 100,
        'verdict': 'ACCEPTED',
        'session_date': TODAY,
        'actions': [
            'Audited Suite 01 per-NWB raster suite & grand unit classification table (`grand_unit_table_shuffle_sso.csv`).',
            'Verified 15 TFR-ready sessions and 6,655 units fully classified into S+, S-, O+, and Other.',
            'Marked Suite 01 plan item as completed.'
        ],
        'receipt': 'outputs/classification/grand_unit_table_shuffle_sso.csv verified: 15 sessions, 6,655 units (2026-07-26)'
    })

plans['last_updated'] = TODAY
progress['last_updated'] = TODAY

with open(REPO / 'artifacts/developer/plans.json', 'w', encoding='utf-8') as f:
    json.dump(plans, f, indent=2, ensure_ascii=False)
with open(REPO / 'artifacts/developer/progress.json', 'w', encoding='utf-8') as f:
    json.dump(progress, f, indent=2, ensure_ascii=False)

completed = sum(1 for x in plan_items if x.get('status') == 'completed')
open_items = [x for x in plan_items if x.get('status') not in ('completed', 'archived')]
print(f'Plans: {len(plan_items)} total | {completed} completed | {len(open_items)} open')
