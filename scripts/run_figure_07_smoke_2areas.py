#!/usr/bin/env python3
"""Figure 7: Expanded Band-Power Smoke with 2 Areas

Runs band-power extraction on PFC + V4/MT (2 areas, 8 channels each = 16 channels)
to enable H-harmony cross-area correlation in Figure 9.
"""

import sys
import json
import warnings
import datetime
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
sys.path.insert(0, str(Path(r'D:/workspace/omission')))

# Import MNE first to verify availability
try:
    import mne
    mne_version = mne.__version__
    mne_available = True
    print(f'MNE version: {mne_version}')
except ImportError as e:
    mne_available = False
    mne_version = None
    raise RuntimeError(f'BLOCKED_MNE_NOT_INSTALLED: {e}')

# Import analysis functions
from src.analysis.io.nwb_address import load_event_timing_vectors_npz
from src.analysis.recipes.signals import get_lfp_epochs
from src.analysis.recipes.specs import WindowSpec
from src.analysis.recipes.analyses import run_band_power

REPO_ROOT = Path(r'D:/workspace/omission')
BATCH_ROOT = REPO_ROOT / 'outputs/data_index/batch_13nwb'
OUTPUT_ROOT = REPO_ROOT / 'outputs/publication_figures/fig04_09_reconstruction/figure_07'

SMOKE_NWB = Path(r'D:/analysis/nwb/sub-C31o_ses-230630_rec.nwb')
SMOKE_SESSION = '230630'
SMOKE_SUBJECT = 'C31o'

# Two areas for H-harmony cross-area correlation
SMOKE_AREAS = ['PFC', 'V4, MT']  # 2 areas for H-harmony
SMOKE_CHANNELS_PER_AREA = 8  # 8 channels per area
WINDOW_PRE = 500
WINDOW_POST = 1300  # Extended for MNE multitaper

start_time = time.time()
print(f'\n=== FIGURE 7 BOUNDED BAND-POWER SMOKE (2 AREAS) ===')
print(f'Session: {SMOKE_SUBJECT}_{SMOKE_SESSION}')
print(f'NWB: {SMOKE_NWB.name}')
print(f'MNE: {mne_version}')
print(f'Started: {datetime.datetime.now().isoformat()}')

# Load channel map
chmap_path = BATCH_ROOT / f'channel_maps/channel_area_layer_map_{SMOKE_SUBJECT}_{SMOKE_SESSION}.csv'
print(f'\nLoading channel map: {chmap_path}')
chmap_df = pd.read_csv(chmap_path)
print(f'  Total channels: {len(chmap_df)}')
print(f'  Areas: {dict(chmap_df["area"].value_counts())}')

# Select channels from 2 areas
channels_by_area = {}
for area in SMOKE_AREAS:
    area_channels = chmap_df[chmap_df['area'] == area]['channel_index_global'].values
    channels_by_area[area] = area_channels[:SMOKE_CHANNELS_PER_AREA]
    print(f'\n{area}: {len(channels_by_area[area])} channels')
    print(f'  Channel indices: {list(channels_by_area[area])}')

# Combine all smoke channels
all_smoke_channels = []
for area, chans in channels_by_area.items():
    all_smoke_channels.extend(chans)
all_smoke_channels = sorted(all_smoke_channels)
print(f'\nTotal smoke channels: {len(all_smoke_channels)}')

# Load events
event_npz_path = BATCH_ROOT / f'events_npz/event_timing_vectors_{SMOKE_SUBJECT}_{SMOKE_SESSION}_p1.npz'
print(f'\nLoading events: {event_npz_path.name}')
events_data = load_event_timing_vectors_npz(event_npz_path)
all_events = events_data[0]

print(f'Available conditions: {list(all_events.keys())}')

# Select smoke conditions
SMOKE_CONDITIONS = ['AAAB', 'RRRR']
smoke_events = {}
for cond in SMOKE_CONDITIONS:
    n_events = len(all_events.get(cond, []))
    n_smoke = min(n_events, 10)  # 10 trials per condition
    smoke_events[cond] = all_events[cond][:n_smoke]
    print(f'{cond}: {n_events} total -> {n_smoke} smoke trials')

print(f'\nSmoke conditions: {list(smoke_events.keys())}')

# Define window
print(f'\n=== EXTRACTING LFP EPOCHS ===')
print(f'  Window: [-{WINDOW_PRE}, +{WINDOW_POST}] ms')
print(f'  Channels: {len(all_smoke_channels)} total across {len(SMOKE_AREAS)} areas')
print(f'  Conditions: {list(smoke_events.keys())}')
print(f'  Trials per condition: 10 (bounded)')

window_spec = WindowSpec(pre_ms=-WINDOW_PRE, post_ms=WINDOW_POST)
channel_filter = {'channel_indices': all_smoke_channels}

extraction_start = time.time()
try:
    lfp_epochs = get_lfp_epochs(
        nwb_path=SMOKE_NWB,
        event_vectors=smoke_events,
        window=window_spec,
        channel_filter=channel_filter,
        signal_name_hint='lfp'
    )
    extraction_time = time.time() - extraction_start
    lfp_success = True
    lfp_blocker = None

    print(f'\n  SUCCESS (took {extraction_time:.1f}s):')
    for cond, arr in lfp_epochs.items():
        print(f'    {cond}: shape {arr.shape}, dtype {arr.dtype}')
        print(f'      Range: [{arr.min():.2f}, {arr.max():.2f}] uV')
        print(f'      Nonzero: {np.any(arr != 0)}')

except Exception as e:
    lfp_success = False
    lfp_blocker = str(e)
    print(f'\n  EXTRACTION FAILED: {lfp_blocker}')
    raise RuntimeError(f'BLOCKED_LFP_EXTRACTION: {lfp_blocker}')

# Compute band-power
print(f'\n=== COMPUTING BAND-POWER ===')
print(f'Bands: {list(run_band_power.__code__.co_vardefaults[0].keys() if run_band_power.__defaults__ else ["alpha", "beta_L", "beta_H", "gamma_L", "gamma_M"])}')
print(f'Method: Efficient band-power (no full TFR storage)')

computation_start = time.time()
band_power_all = {}

for cond, lfp_array in lfp_epochs.items():
    print(f'\n  Processing {cond}...')
    band_power_all[cond] = run_band_power(
        lfp_epochs={cond: lfp_array},
        bands=None,  # Use defaults
        baseline_ms=None  # Raw power for smoke
    )

computation_time = time.time() - computation_start

# Verify nonzero band-power
print(f'\n  SUCCESS (took {computation_time:.1f}s):')
all_nonzero = True
all_finite = True
band_shapes = {}

for cond in SMOKE_CONDITIONS:
    print(f'\n    {cond}:')
    bands = band_power_all[cond][cond]
    for band_name, power in bands.items():
        if '_db' in band_name:
            continue  # Skip dB versions
        nonzero = np.any(power != 0)
        finite = np.all(np.isfinite(power))
        all_nonzero = all_nonzero and nonzero
        all_finite = all_finite and finite
        print(f'      {band_name}: shape {power.shape}, nonzero={nonzero}')
        band_shapes[band_name] = power.shape

# Combine into single array: (condition, trial, channel, band, time)
# Split channels back into area groups for H-harmony
n_conditions = len(SMOKE_CONDITIONS)
n_trials = 10
n_channels = len(all_smoke_channels)
n_bands = len([b for b in band_shapes.keys() if '_db' not in b])
n_time = band_shapes[list(band_shapes.keys())[0]][2] if band_shapes else 0

print(f'\n  Combined array shape: ({n_conditions}, {n_trials}, {n_channels}, {n_bands}, {n_time})')
print(f'    (condition x trial x channel x band x time)')
print(f'    = ({n_conditions} x {n_trials} x {n_channels} x {n_bands} x {n_time})')

# Build combined array
band_names = [b for b in band_shapes.keys() if '_db' not in b]
combined_array = np.zeros((n_conditions, n_trials, n_channels, n_bands, n_time), dtype=np.float32)

for c_idx, cond in enumerate(SMOKE_CONDITIONS):
    for b_idx, band_name in enumerate(band_names):
        power = band_power_all[cond][cond][band_name]  # (trials, channels, time)
        combined_array[c_idx, :, :, b_idx, :] = power

print(f'    Total elements: {combined_array.size:,}')
print(f'    Memory: {combined_array.nbytes / 1024 / 1024:.2f} MB')
print(f'    Nonzero: {np.any(combined_array > 0)}')
print(f'    Finite: {np.all(np.isfinite(combined_array))}')

if not np.any(combined_array > 0):
    raise RuntimeError('BLOCKED_ZERO_BANDPOWER: All band-power values are zero')

print(f'\n  [OK] Real nonzero band-power verified')

# Save outputs
(OUTPUT_ROOT / 'arrays').mkdir(parents=True, exist_ok=True)
(OUTPUT_ROOT / 'tables').mkdir(parents=True, exist_ok=True)
(OUTPUT_ROOT / 'figures').mkdir(parents=True, exist_ok=True)

saved_paths = {}

# Save band-power array
bp_path = OUTPUT_ROOT / 'arrays/fig07_bandpower_smoke_2areas.npz'
np.savez_compressed(
    bp_path,
    band_power=combined_array,
    conditions=SMOKE_CONDITIONS,
    bands=band_names,
    band_freqs={
        'alpha': [8, 12],
        'beta_L': [12, 20],
        'beta_H': [20, 30],
        'gamma_L': [32, 50],
        'gamma_M': [50, 90]
    },
    time_axis_ms=np.linspace(-WINDOW_PRE, WINDOW_POST, n_time),
    channels=all_smoke_channels,
    areas=SMOKE_AREAS,
    channels_per_area=SMOKE_CHANNELS_PER_AREA,
    area_map={area: list(channels_by_area[area]) for area in SMOKE_AREAS},
    subject=SMOKE_SUBJECT,
    session=SMOKE_SESSION,
    shape_description=f'condition({n_conditions}) x trial({n_trials}) x channel({n_channels}) x band({n_bands}) x time({n_time})',
    nonzero_verified=bool(np.any(combined_array > 0)),
    finite_verified=bool(np.all(np.isfinite(combined_array)))
)
saved_paths['bandpower'] = str(bp_path)
print(f'\nSaved band-power: {bp_path}')
print(f'  Shape: {combined_array.shape}')
print(f'  File size: {bp_path.stat().st_size / 1024:.1f} KB')
print(f'  Nonzero: {np.any(combined_array > 0)}')

# Create inventory table
inventory_rows = []
for c_idx, cond in enumerate(SMOKE_CONDITIONS):
    for b_idx, band_name in enumerate(band_names):
        power = combined_array[c_idx, :, :, b_idx, :]
        inventory_rows.append({
            'condition': cond,
            'band': band_name,
            'trials': power.shape[0],
            'channels': power.shape[1],
            'time_samples': power.shape[2],
            'mean_power': float(power.mean()),
            'std_power': float(power.std()),
            'min_power': float(power.min()),
            'max_power': float(power.max()),
            'nonzero': bool(np.any(power > 0)),
            'finite': bool(np.all(np.isfinite(power)))
        })

inventory_df = pd.DataFrame(inventory_rows)
inv_path = OUTPUT_ROOT / 'tables/fig07_tfr_inventory_smoke_2areas.csv'
inventory_df.to_csv(inv_path, index=False)
saved_paths['inventory'] = str(inv_path)
print(f'\nSaved inventory: {inv_path}')
print(f'  Rows: {len(inventory_df)}')

# Get git SHA
try:
    sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
except:
    sha = 'unknown'

# HTML preview
html_content = f'''<!DOCTYPE html>
<html><head><link rel="stylesheet" href="../shared/style.css"></head><body>
<h1>Figure 7: Omission-Centered Band-Power Smoke (2 Areas)</h1>
<p><strong>Status:</strong> <span class="status-pass">SMOKE_PASS_REAL_BANDPOWER</span></p>
<div class="claim-box">
<strong>Core:</strong> Time-frequency power around omission (P4 in AAAB) vs control (RRRR)<br>
<strong>Signal:</strong> LFP (2 areas: PFC, V4/MT)<br>
<strong>Method:</strong> MNE multitaper band-power<br>
<strong>Output:</strong> Real nonzero band-power array<br>
<strong>Nonzero:</strong> {np.any(combined_array > 0)}<br>
<strong>Finite:</strong> {np.all(np.isfinite(combined_array))}
</div>

<h2>Configuration</h2>
<table>
<tr><th>Parameter</th><th>Value</th></tr>
<tr><td>Session</td><td>{SMOKE_SUBJECT}_{SMOKE_SESSION}</td></tr>
<tr><td>Areas</td><td>{', '.join(SMOKE_AREAS)}</td></tr>
<tr><td>Channels</td><td>{n_channels} ({SMOKE_CHANNELS_PER_AREA} per area)</td></tr>
<tr><td>Window</td><td>[-{WINDOW_PRE}, +{WINDOW_POST}] ms</td></tr>
<tr><td>Bands</td><td>{', '.join(band_names)}</td></tr>
<tr><td>Conditions</td><td>{', '.join(SMOKE_CONDITIONS)}</td></tr>
<tr><td>Trials per condition</td><td>{n_trials}</td></tr>
</table>

<h2>Output Array</h2>
<table>
<tr><th>Property</th><th>Value</th></tr>
<tr><td>Shape</td><td>{combined_array.shape}</td></tr>
<tr><td>Axis order</td><td>condition x trial x channel x band x time</td></tr>
<tr><td>Memory</td><td>{combined_array.nbytes / 1024 / 1024:.2f} MB</td></tr>
<tr><td>Nonzero</td><td>{np.any(combined_array > 0)}</td></tr>
<tr><td>Finite</td><td>{np.all(np.isfinite(combined_array))}</td></tr>
</table>

<h2>Inventory</h2>
<table>
<tr><th>Condition</th><th>Band</th><th>Mean Power</th><th>Nonzero</th><th>Finite</th></tr>
{''.join(f'<tr><td>{r["condition"]}</td><td>{r["band"]}</td><td>{r["mean_power"]:.2f}</td><td>{r["nonzero"]}</td><td>{r["finite"]}</td></tr>' for _, r in inventory_df.iterrows())}
</table>

<h2>Outputs</h2>
<ul>
<li>Band-power: <code>{saved_paths.get('bandpower', 'N/A')}</code></li>
<li>Inventory: <code>{saved_paths.get('inventory', 'N/A')}</code></li>
</ul>

<hr><p><small>Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()} | Git: {sha[:12]}</small></p>
</body></html>
'''

html_path = OUTPUT_ROOT / 'figures/fig07_bandpower_smoke_2areas.html'
html_path.write_text(html_content, encoding='utf-8')
saved_paths['html'] = str(html_path)
print(f'Saved HTML: {html_path}')

# Manifest
runtime = time.time() - start_time
manifest = {
    'figure_id': 'figure_07',
    'figure_name': 'Omission-Centered Band-Power (2 Areas)',
    'repo_sha': sha,
    'created_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'smoke_status': 'SMOKE_PASS_REAL_BANDPOWER',
    'subject': SMOKE_SUBJECT,
    'session': SMOKE_SESSION,
    'time_base': 'omission_relative',
    'window_ms': [-WINDOW_PRE, WINDOW_POST],
    'n_channels_smoke': n_channels,
    'channels': all_smoke_channels,
    'areas': SMOKE_AREAS,
    'channels_per_area': SMOKE_CHANNELS_PER_AREA,
    'area_channel_map': {area: list(channels_by_area[area]) for area in SMOKE_AREAS},
    'trials_per_condition_smoke': n_trials,
    'conditions': SMOKE_CONDITIONS,
    'bands': band_names,
    'band_freqs_hz': {
        'alpha': [8, 12],
        'beta_L': [12, 20],
        'beta_H': [20, 30],
        'gamma_L': [32, 50],
        'gamma_M': [50, 90]
    },
    'mne_version': mne_version,
    'has_real_bandpower': True,
    'nonzero_check': bool(np.any(combined_array > 0)),
    'finite_check': bool(np.all(np.isfinite(combined_array))),
    'array_shape': list(combined_array.shape),
    'array_shape_description': f'condition({n_conditions}) x trial({n_trials}) x channel({n_channels}) x band({n_bands}) x time({n_time})',
    'total_elements': int(combined_array.size),
    'memory_bytes': int(combined_array.nbytes),
    'runtime_seconds': runtime,
    'extraction_time_seconds': extraction_time,
    'computation_time_seconds': computation_time,
    'output_paths': saved_paths,
    'source_functions': ['get_lfp_epochs', 'run_band_power'],
    'extraction_method': 'bounded_nwb_read',
    'computation_method': 'mne_multitaper_bandpower',
    'claim_status': {
        'truth_safe_unverified': True,
        'computational_scaffold': True,
        'no_fabrication': True
    }
}

manifest_path = OUTPUT_ROOT / 'fig07_manifest_2areas.json'
with open(manifest_path, 'w') as f:
    json.dump(manifest, f, indent=2)

print(f'\n=== FIGURE 7 COMPLETE (2 AREAS) ===')
print(f'Total time: {runtime:.1f}s')
print(f'Status: SMOKE_PASS_REAL_BANDPOWER')
print(f'Array: {combined_array.shape} ({combined_array.nbytes / 1024 / 1024:.2f} MB)')
print(f'Nonzero: {np.any(combined_array > 0)}')
print(f'Manifest: {manifest_path}')

print('\nOutputs:')
for k, v in saved_paths.items():
    print(f'  {k}: {v}')

print('\nFigure 7 smoke with 2 areas complete!')
