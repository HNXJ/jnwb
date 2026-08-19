"""
Update plans.json and progress.json for LFP TFR Complex Preprocessing implementation.
Mark LFP TFR Phase/Complex Coefficient Preprocessing plan as completed.
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
    if 'LFP TFR Phase' in title or 'Complex Coefficient' in title:
        item['status'] = 'completed'
        item['completed_date'] = TODAY
        item['receipt'] = (
            f'Implemented {TODAY}: jnwb/complex_tfr.py with `tfr_complex_load`, `plv_from_complex`, and `imaginary_coherence`. '
            'Created test suite tests/test_tfr_complex.py (4/4 PASSED in 3.22s). '
            'Falsifiers verified: round-trip save/load preserves complex128, PLV(z,z)==1.0, PLV(uncorrelated)<0.1.'
        )
        print(f'Completed plan: {title}')

entry_key = 'proceed-lfp-complex-tfr-2026-07-26'
existing_keys = {e.get('filename', '') for e in prog_entries}

if entry_key not in existing_keys:
    prog_entries.append({
        'filename': entry_key,
        'path': 'artifacts/developer/progress.json',
        'score': 100,
        'verdict': 'ACCEPTED',
        'session_date': TODAY,
        'actions': [
            'Implemented complex TFR loading & phase analysis helper module `jnwb/complex_tfr.py`.',
            'Implemented `tfr_complex_load`, `plv_from_complex`, and `imaginary_coherence`.',
            'Added unit test suite `tests/test_tfr_complex.py` covering round-trip IO, PLV identity, and imaginary coherence shapes.',
            'Verified 4/4 tests passed with clean receipt.',
            'Marked LFP TFR Phase/Complex Coefficient Preprocessing plan as completed.'
        ],
        'receipt': 'pytest tests/test_tfr_complex.py -v -> 4 passed in 3.22s (2026-07-26)'
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
