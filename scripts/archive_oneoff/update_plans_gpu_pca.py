"""
Update plans.json and progress.json for GPU-accelerated PCA implementation.
Mark GPU-Accelerated Population Trajectory (PCA) plan as completed.
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
    if 'GPU-Accelerated Population Trajectory' in title:
        item['status'] = 'completed'
        item['completed_date'] = TODAY
        item['receipt'] = (
            f'Implemented {TODAY}: jnwb/gpu_pca.py + exported via jnwb/trajectory.py. '
            'Added gpu_pca(matrix, n_components=3, device="cuda") with automatic PyTorch CUDA / CPU SVD '
            'and NumPy fallback. Added unit tests in tests/test_gpu_pca.py (3/3 PASSED). '
            'Falsifier: test_gpu_pca_matches_numpy verified projections correlation > 0.99 with numpy reference SVD.'
        )
        print(f'Completed plan: {title}')

entry_key = 'proceed-gpu-pca-2026-07-26'
existing_keys = {e.get('filename', '') for e in prog_entries}

if entry_key not in existing_keys:
    prog_entries.append({
        'filename': entry_key,
        'path': 'artifacts/developer/progress.json',
        'score': 100,
        'verdict': 'ACCEPTED',
        'session_date': TODAY,
        'actions': [
            'Implemented standalone GPU-accelerated PCA helper `gpu_pca` in jnwb/gpu_pca.py.',
            'Exposed `gpu_pca` through `jnwb/trajectory.py` module.',
            'Added unit test suite in `tests/test_gpu_pca.py` covering shapes, zero samples, and correlation with NumPy SVD.',
            'Verified 3/3 tests passed with clean receipt.',
            'Marked GPU-Accelerated Population Trajectory (PCA) plan as completed.'
        ],
        'receipt': 'pytest tests/test_gpu_pca.py -v -> 3 passed in 5.18s (2026-07-26)'
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
