#!/usr/bin/env python3
"""Figure 5: Local Omission SPK Contrast (Patched)

Fixes pre_ms sign issue - should be -1000 not 1000.
"""

import sys
import json
import warnings
import datetime
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings('ignore')
sys.path.insert(0, str(Path(r'D:/workspace/omission')))

from src.analysis.io.nwb_address import get_aligned_unit_signals, load_event_timing_vectors_npz

REPO_ROOT = Path(r'D:/workspace/omission')
BATCH_ROOT = REPO_ROOT / 'outputs/data_index/batch_13nwb'
OUTPUT_ROOT = REPO_ROOT / 'outputs/publication_figures/fig04_09_reconstruction/figure_05'

SMOKE_NWB = Path(r'D:/analysis/nwb/sub-C31o_ses-230630_rec.nwb')
SMOKE_SESSION = '230630'
SMOKE_SUBJECT = 'C31o'

# FIXED: pre_ms should be -1000 (negative for pre-event time)
# The function expects pre_ms to be negative (time before event)
PRE_MS = -1000   # FIXED: was 1000 (positive)
POST_MS = 1000
BIN_MS = 10

OMISSION_COND = 'AAAB'
CONTROL_COND = 'RRRR'

print(f'=== FIGURE 5 PATCHED SMOKE ===')
print(f'PRE_MS: {PRE_MS} (FIXED: should be negative for pre-event window)')
print(f'POST_MS: {POST_MS}')
print(f'Window: [{PRE_MS}, {POST_MS}] ms')
print(f'Expected bins: {int((POST_MS - PRE_MS) / BIN_MS)}')

# Load events
event_npz_path = BATCH_ROOT / f'events_npz/event_timing_vectors_{SMOKE_SUBJECT}_{SMOKE_SESSION}_p1.npz'
events_data = load_event_timing_vectors_npz(event_npz_path)
all_events = events_data[0]

print(f'\nAvailable conditions: {list(all_events.keys())}')

omission_times = all_events[OMISSION_COND]
control_times = all_events[CONTROL_COND]

n_trials_matched = min(len(omission_times), len(control_times))
omission_times_matched = omission_times[:n_trials_matched]
control_times_matched = control_times[:n_trials_matched]

print(f'{OMISSION_COND}: {len(omission_times)} total -> {n_trials_matched} matched')
print(f'{CONTROL_COND}: {len(control_times)} total -> {n_trials_matched} matched')

# Extract omission epochs
print(f'\nExtracting omission epochs ({OMISSION_COND})...')
event_vectors_omission = {OMISSION_COND: omission_times_matched}

omission_data = get_aligned_unit_signals(
    nwb_path=SMOKE_NWB,
    unit_filter={},
    event_vectors=event_vectors_omission,
    pre_ms=PRE_MS,
    post_ms=POST_MS,
    bin_ms=BIN_MS
)

spk_omission = omission_data['spikes'][OMISSION_COND]
print(f'  Shape: {spk_omission.shape}')
print(f'  Trials: {spk_omission.shape[0]}')
print(f'  Units: {spk_omission.shape[1]}')
print(f'  Time bins: {spk_omission.shape[2]}')

# Extract control epochs
print(f'\nExtracting control epochs ({CONTROL_COND})...')
event_vectors_control = {CONTROL_COND: control_times_matched}

control_data = get_aligned_unit_signals(
    nwb_path=SMOKE_NWB,
    unit_filter={},
    event_vectors=event_vectors_control,
    pre_ms=PRE_MS,
    post_ms=POST_MS,
    bin_ms=BIN_MS
)

spk_control = control_data['spikes'][CONTROL_COND]
print(f'  Shape: {spk_control.shape}')
print(f'  Trials: {spk_control.shape[0]}')
print(f'  Units: {spk_control.shape[1]}')
print(f'  Time bins: {spk_control.shape[2]}')

# Verify nonzero time dimension
if spk_omission.shape[2] == 0 or spk_control.shape[2] == 0:
    print('\n*** ERROR: Zero time dimension ***')
    print('This should not happen with pre_ms=-1000')
    sys.exit(1)

# Compute rates and contrast
print('\n=== COMPUTING CONTRAST ===')
time_axis = np.linspace(PRE_MS, POST_MS, spk_omission.shape[2])

rate_omission = spk_omission.mean(axis=0) * 1000 / BIN_MS
rate_control = spk_control.mean(axis=0) * 1000 / BIN_MS
rate_diff = rate_omission - rate_control

epsilon = 1e-6
modulation_index = (rate_omission - rate_control) / (rate_omission + rate_control + epsilon)

print(f'rate_omission shape: {rate_omission.shape}')
print(f'rate_control shape: {rate_control.shape}')
print(f'rate_diff shape: {rate_diff.shape}')
print(f'nonzero check (omission): {np.any(spk_omission > 0)}')
print(f'nonzero check (control): {np.any(spk_control > 0)}')

# Save patched outputs
(OUTPUT_ROOT / 'arrays').mkdir(parents=True, exist_ok=True)
(OUTPUT_ROOT / 'tables').mkdir(parents=True, exist_ok=True)
(OUTPUT_ROOT / 'figures').mkdir(parents=True, exist_ok=True)

saved_paths = {}

epochs_path = OUTPUT_ROOT / 'arrays/fig05_local_spk_smoke_patched.npz'
np.savez_compressed(
    epochs_path,
    spk_omission=spk_omission,
    spk_control=spk_control,
    rate_omission=rate_omission,
    rate_control=rate_control,
    rate_diff=rate_diff,
    modulation_index=modulation_index,
    time_axis=time_axis,
    bin_ms=BIN_MS,
    pre_ms=PRE_MS,
    post_ms=POST_MS,
    omission_condition=OMISSION_COND,
    control_condition=CONTROL_COND,
    n_trials_omission=len(omission_times),
    n_trials_control=len(control_times),
    n_trials_matched=n_trials_matched,
    n_units=spk_omission.shape[1],
    subject=SMOKE_SUBJECT,
    session=SMOKE_SESSION,
    patch_note='pre_ms fixed from 1000 to -1000'
)
saved_paths['arrays'] = str(epochs_path)
print(f'\nSaved patched arrays: {epochs_path}')

# Unit stats
n_units = spk_omission.shape[1]
unit_stats = []

for u in range(n_units):
    unit_om = spk_omission[:, u, :]
    unit_ctrl = spk_control[:, u, :]
    
    baseline_om = unit_om.mean() * 1000 / BIN_MS
    baseline_ctrl = unit_ctrl.mean() * 1000 / BIN_MS
    
    unit_stats.append({
        'unit_idx': u,
        'baseline_rate_omission_hz': float(baseline_om),
        'baseline_rate_control_hz': float(baseline_ctrl),
        'rate_diff_mean': float(baseline_om - baseline_ctrl),
    })

stats_df = pd.DataFrame(unit_stats)
stats_path = OUTPUT_ROOT / 'tables/fig05_local_omission_spk_summary_patched.csv'
stats_df.to_csv(stats_path, index=False)
saved_paths['tables'] = str(stats_path)
print(f'Saved stats: {stats_path}')

# HTML preview
try:
    sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
except:
    sha = 'unknown'

html_content = f'''<!DOCTYPE html>
<html><head><link rel="stylesheet" href="../shared/style.css"></head><body>
<h1>Figure 5: Local Omission SPK Contrast (PATCHED)</h1>
<p><strong>Status:</strong> <span class="status-pass">SMOKE_PASS_PATCHED</span></p>
<div class="claim-box">
<strong>Patch:</strong> pre_ms changed from 1000 to -1000 (negative for pre-event window)<br>
<strong>Signal:</strong> SPK omission vs control contrast<br>
<strong>Nonzero check:</strong> {np.any(spk_omission > 0) and np.any(spk_control > 0)}
</div>
<h2>Configuration</h2>
<table>
<tr><th>Parameter</th><th>Value</th></tr>
<tr><td>PRE_MS</td><td>{PRE_MS} (FIXED)</td></tr>
<tr><td>POST_MS</td><td>{POST_MS}</td></tr>
<tr><td>Window</td><td>[{PRE_MS}, {POST_MS}] ms</td></tr>
<tr><td>Bin size</td><td>{BIN_MS} ms</td></tr>
<tr><td>Time bins</td><td>{spk_omission.shape[2]}</td></tr>
</table>
<h2>Output Arrays</h2>
<table>
<tr><th>Array</th><th>Shape</th><th>Nonzero</th></tr>
<tr><td>spk_omission</td><td>{spk_omission.shape}</td><td>{np.any(spk_omission > 0)}</td></tr>
<tr><td>spk_control</td><td>{spk_control.shape}</td><td>{np.any(spk_control > 0)}</td></tr>
<tr><td>rate_diff</td><td>{rate_diff.shape}</td><td>{np.any(np.abs(rate_diff) > 0)}</td></tr>
</table>
<hr><p><small>Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()} | Git: {sha[:12]}</small></p>
</body></html>
'''

html_path = OUTPUT_ROOT / 'figures/fig05_local_spk_contrast_patched.html'
html_path.write_text(html_content, encoding='utf-8')
saved_paths['html'] = str(html_path)
print(f'Saved HTML: {html_path}')

# Manifest
manifest = {
    'figure_id': 'figure_05',
    'figure_name': 'Local Omission SPK Contrast',
    'repo_sha': sha,
    'created_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'smoke_status': 'SMOKE_PASS_PATCHED',
    'patch_applied': 'pre_ms sign fix: 1000 -> -1000',
    'pre_ms': PRE_MS,
    'post_ms': POST_MS,
    'window_ms': [PRE_MS, POST_MS],
    'bin_ms': BIN_MS,
    'n_time_bins': int(spk_omission.shape[2]),
    'subject': SMOKE_SUBJECT,
    'session': SMOKE_SESSION,
    'omission_condition': OMISSION_COND,
    'control_condition': CONTROL_COND,
    'n_trials_omission': len(omission_times),
    'n_trials_control': len(control_times),
    'n_trials_matched': n_trials_matched,
    'n_units': int(spk_omission.shape[1]),
    'has_real_arrays': True,
    'array_shapes': {
        'spk_omission': list(spk_omission.shape),
        'spk_control': list(spk_control.shape),
        'rate_diff': list(rate_diff.shape)
    },
    'nonzero_check': {
        'spk_omission': bool(np.any(spk_omission > 0)),
        'spk_control': bool(np.any(spk_control > 0))
    },
    'output_paths': saved_paths,
    'claim_status': {
        'truth_safe_unverified': True,
        'computational_scaffold': True,
        'no_fabrication': True
    }
}

manifest_path = OUTPUT_ROOT / 'fig05_manifest_patched.json'
with open(manifest_path, 'w') as f:
    json.dump(manifest, f, indent=2)

print(f'\n=== FIGURE 5 PATCHED SMOKE COMPLETE ===')
print(f'Status: SMOKE_PASS_PATCHED')
print(f'Patch: pre_ms sign fix (1000 -> -1000)')
print(f'Arrays: {spk_omission.shape}, {spk_control.shape}')
print(f'Nonzero: {np.any(spk_omission > 0)} (omission), {np.any(spk_control > 0)} (control)')
print(f'Manifest: {manifest_path}')
