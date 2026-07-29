"""
Update plans.json after double-proceed session:
1. Mark Exploratory vs Confirmatory Stats API split as completed
2. Evolve LFP TFR Phase/Complex brainstorm -> concrete plan
3. Evolve GPU Population Trajectory brainstorm -> concrete plan
4. Log progress entry
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

plan_items   = plans.get('items', [])
prog_entries = progress.get('entries', [])

for item in plan_items:
    title = item.get('title', '')

    # 1. Mark stats API split completed
    if 'Exploratory vs confirmatory stats API' in title:
        item['status'] = 'completed'
        item['completed_date'] = TODAY
        item['receipt'] = (
            f'Implemented {TODAY}: jnwb/statistics.py — added exploratory_compare(), '
            'exploratory_correlate(), exploratory_multi(), confirmatory_compare(). '
            '_uncorrected_flags() now emits DeprecationWarning. '
            'New test file: tests/test_statistics_api_split.py — 23/23 passed in 4.28s. '
            'Full suite: 197 passed, 22 skipped, 0 failed. '
            'Falsifier: test_exploratory_compare_no_q_value PASS, '
            'test_confirmatory_compare_has_q_value PASS.'
        )
        print(f'Completed: {title[:65]}')

    # 2. Evolve LFP TFR Phase/Complex brainstorm -> planned
    if 'LFP TFR Phase' in title and item.get('status') == 'brainstorm':
        item['status'] = 'planned'
        item['plan_date'] = TODAY
        item['concrete_plan'] = {
            'goal': (
                'Preprocess and save both real Re(freq,time) and imaginary Im(freq,time) '
                'Morlet wavelet coefficient components alongside the power TFR arrays. '
                'Enables phase-locking value (PLV), imaginary coherence, and cross-area '
                'complex correlation analyses without re-running the full Morlet transform.'
            ),
            'steps': [
                '1. Modify jnwb/tfr.py precompute path to save .real.npy and .imag.npy '
                'alongside existing .npy power arrays in D:/workspace/data/tfr_arrays/',
                '2. Add tfr_complex_load(session, probe, area, cond) -> complex array helper',
                '3. Add plv_from_complex(z1, z2) -> float helper (mean angle difference)',
                '4. Add imaginary_coherence(z1, z2) -> array (Im-part of normalized cross-spectrum)',
                '5. Add test: test_complex_tfr_round_trip (save+load re/im == original)',
                '6. Update TFRAnalyzer to expose complex coefficient access',
                '7. Gate on session_readiness suite_tfr_ready=True before loading'
            ],
            'falsifier': (
                'test_complex_tfr_round_trip passes; '
                'tfr_complex_load returns dtype=complex128 array with correct shape; '
                'plv_from_complex(z, z) == 1.0; '
                'plv_from_complex(z, -z) < 0.1'
            ),
            'scope': 'jnwb/tfr.py, D:/workspace/data/tfr_arrays/, tests/test_tfr_complex.py',
            'dependency': 'suite_tfr_ready sessions (15/21); requires ~5 GB additional disk per session'
        }
        print(f'Evolved brainstorm -> planned: {title[:65]}')

    # 3. Evolve GPU Population Trajectory brainstorm -> planned
    if 'GPU-Accelerated Population Trajectory' in title and item.get('status') == 'brainstorm':
        item['status'] = 'planned'
        item['plan_date'] = TODAY
        item['concrete_plan'] = {
            'goal': (
                'Accelerate population trajectory PCA using PyTorch SVD on GPU, '
                'enabling fast dimensionality reduction across thousands of units '
                'across all 21 sessions without the 30-60 min numpy SVD bottleneck.'
            ),
            'steps': [
                '1. Add gpu_pca(matrix, n_components=3, device="cuda") in jnwb/trajectory.py '
                '   using torch.linalg.svd (falls back to numpy if cuda unavailable)',
                '2. Benchmark: numpy SVD vs torch CPU vs torch CUDA on 6655x5000 matrix',
                '3. Add test: test_gpu_pca_matches_numpy (max abs diff < 1e-4 on projections)',
                '4. Integrate into compute_population_trajectory() via backend= kwarg',
                '5. Add session_readiness gate: skip GPU path if torch.cuda.is_available() False',
                '6. Output: population_trajectory_gpu_{session}.npy + 3D PCA plot (SVG)'
            ],
            'falsifier': (
                'test_gpu_pca_matches_numpy passes; '
                'torch.linalg.svd output matches np.linalg.svd to within 1e-4; '
                'fallback to numpy works when cuda=False'
            ),
            'scope': 'jnwb/trajectory.py, tests/test_trajectory.py (extend), outputs/population/',
            'dependency': 'torch >= 2.0 installed; GPU optional (CPU fallback always active)'
        }
        print(f'Evolved brainstorm -> planned: {title[:65]}')

# 4. Add progress entry
entry_key = 'proceed-double-proceed-2026-07-26'
existing_keys = {e.get('filename', '') for e in prog_entries}

if entry_key not in existing_keys:
    prog_entries.append({
        'filename': entry_key,
        'path': 'artifacts/developer/progress.json',
        'score': 95,
        'verdict': 'ACCEPTED',
        'session_date': TODAY,
        'actions': [
            'Implemented Exploratory/Confirmatory Stats API split in jnwb/statistics.py: '
            'added exploratory_compare, exploratory_correlate, exploratory_multi, '
            'confirmatory_compare; _uncorrected_flags now emits DeprecationWarning.',
            'Added tests/test_statistics_api_split.py: 23 tests covering all falsifier conditions.',
            '23/23 new tests passed; full suite 197 passed, 22 skipped, 0 failed.',
            'Evolved LFP TFR Phase/Complex brainstorm -> concrete 7-step plan with falsifier.',
            'Evolved GPU Population Trajectory brainstorm -> concrete 6-step plan with falsifier.',
            'Marked Exploratory vs Confirmatory Stats API plan item as completed.'
        ],
        'receipt': (
            'pytest tests/test_statistics_api_split.py -v -> 23 passed in 4.28s; '
            'pytest tests/ -q -> 197 passed, 22 skipped, 0 failed (2026-07-26)'
        )
    })
    print(f'Added progress entry: {entry_key}')

plans['last_updated'] = TODAY
progress['last_updated'] = TODAY

with open(REPO / 'artifacts/developer/plans.json', 'w', encoding='utf-8') as f:
    json.dump(plans, f, indent=2, ensure_ascii=False)
with open(REPO / 'artifacts/developer/progress.json', 'w', encoding='utf-8') as f:
    json.dump(progress, f, indent=2, ensure_ascii=False)

# Final summary
completed = sum(1 for x in plan_items if x.get('status') == 'completed')
open_items = [x for x in plan_items if x.get('status') not in ('completed', 'archived')]
open_items.sort(key=lambda x: {'critical':0,'high':1,'medium':2,'low':3}.get(x.get('priority','low'),3))
print(f'\nPlans: {len(plan_items)} total | {completed} completed | {len(open_items)} open')
for item in open_items:
    p = item.get('priority', '?').upper()
    s = item.get('status', '?')
    print(f'  [{p:<8}|{s:<12}] {item.get("title","?")[:65]}')
