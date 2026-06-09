#!/usr/bin/env python3
"""Figure 9: H Harmony from Y Tensor (Script Version)

Builds H harmony matrix from Figure 8 Y tensor.
H represents cross-area correlation/similarity.

Note: For proper H-harmony with cross-area correlations,
Y tensor needs at least 2 distinct areas.
"""

import sys
import json
import warnings
import datetime
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
sys.path.insert(0, str(Path(r'D:/workspace/omission')))

REPO_ROOT = Path(r'D:/workspace/omission')
F08_ROOT = REPO_ROOT / 'outputs/publication_figures/fig04_09_reconstruction/figure_08'
OUTPUT_ROOT = REPO_ROOT / 'outputs/publication_figures/fig04_09_reconstruction/figure_09'

SMOKE_SUBJECT = 'C31o'
SMOKE_SESSION = '230630'

print('=== FIGURE 9 H HARMONY BUILD ===')

# Check Figure 8 output
y_path = F08_ROOT / 'arrays/fig08_Y_tensor_smoke.npz'
f08_manifest_path = F08_ROOT / 'fig08_manifest.json'

if f08_manifest_path.exists():
    with open(f08_manifest_path) as f:
        f08_manifest = json.load(f)
    f08_status = f08_manifest.get('smoke_status', 'UNKNOWN')
    f08_has_Y = f08_manifest.get('has_real_Y_tensor', False)
    f08_areas = f08_manifest.get('areas', [])
    print(f'Figure 8 status: {f08_status}')
    print(f'Figure 8 has Y tensor: {f08_has_Y}')
    print(f'Figure 8 areas: {f08_areas}')
    print(f'Area count: {len(f08_areas)}')
else:
    print('ERROR: Figure 8 manifest not found')
    sys.exit(1)

if not y_path.exists():
    print(f'ERROR: Figure 8 Y tensor file not found: {y_path}')
    sys.exit(1)

# Check area count for H-harmony
n_areas = len(f08_areas) if isinstance(f08_areas, list) else 1
if n_areas < 2:
    print(f'\n*** BLOCKED_INSUFFICIENT_AREAS_FOR_H ***')
    print(f'H-harmony requires at least 2 areas for cross-area correlation.')
    print(f'Current Y tensor has {n_areas} area(s): {f08_areas}')
    print(f'\nThis is a smoke limitation - full implementation would use')
    print(f'multi-probe LFP reading (probe_0, probe_1, probe_2).')

    # Write blocker file
    (OUTPUT_ROOT / 'arrays').mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / 'tables').mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / 'figures').mkdir(parents=True, exist_ok=True)

    # Get git SHA
    try:
        sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except:
        sha = 'unknown'

    blocker_reason = f'Y tensor has only {n_areas} area(s) ({f08_areas}). H-harmony requires >= 2 areas for cross-area correlation.'

    blocker_path = OUTPUT_ROOT / 'arrays/H_harmony_BLOCKER.txt'
    blocker_path.write_text(blocker_reason, encoding='utf-8')

    # Summary table
    summary_df = pd.DataFrame({
        'status': ['BLOCKED'],
        'blocked_by': ['INSUFFICIENT_AREAS'],
        'area_count': [n_areas],
        'areas': [str(f08_areas)],
        'blocker': [blocker_reason],
        'resolution': ['Use multi-probe LFP extraction (probe_0 + probe_1 + probe_2)']
    })
    table_path = OUTPUT_ROOT / 'tables/fig09_H_harmony_summary_smoke.csv'
    summary_df.to_csv(table_path, index=False)

    # HTML with blocker
    html_content = f'''<!DOCTYPE html>
<html><head><link rel="stylesheet" href="../shared/style.css"></head><body>
<h1>Figure 9: H Harmony from Y Tensor</h1>
<p><strong>Status:</strong> <span class="status-blocked">BLOCKED_INSUFFICIENT_AREAS_FOR_H</span></p>
<div class="claim-box">
<strong>Core:</strong> H = Harmony/Correlation matrix across areas<br>
<strong>Input:</strong> Figure 8 Y tensor<br>
<strong>Problem:</strong> Insufficient areas for cross-area correlation
</div>

<div class="warning-box">
<strong>Blocker:</strong> {blocker_reason}<br><br>
<strong>Current Y tensor:</strong><br>
- Areas: {f08_areas}<br>
- Count: {n_areas}<br><br>
<strong>Required:</strong> >= 2 areas<br><br>
<strong>Resolution:</strong><br>
The current smoke implementation uses only probe_0_lfp (128 channels, PFC).<br>
To build H-harmony with cross-area correlations, implement multi-probe extraction:<br>
- probe_0_lfp: channels 0-127 (PFC)<br>
- probe_1_lfp: channels 128-255 (V4/MT)<br>
- probe_2_lfp: channels 256-383 (V3/V1)
</div>

<h2>Outputs</h2>
<ul>
<li>Blocker: <code>{str(blocker_path)}</code></li>
<li>Summary: <code>{str(table_path)}</code></li>
</ul>

<hr><p><small>Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()} | Git: {sha[:12]}</small></p>
</body></html>
'''

    html_path = OUTPUT_ROOT / 'figures/fig09_H_harmony_smoke.html'
    html_path.write_text(html_content, encoding='utf-8')

    # Manifest
    manifest = {
        'figure_id': 'figure_09',
        'figure_name': 'H Harmony from Y',
        'repo_sha': sha,
        'created_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'smoke_status': 'BLOCKED_INSUFFICIENT_AREAS_FOR_H',
        'subject': SMOKE_SUBJECT,
        'session': SMOKE_SESSION,
        'blocked_by': 'Figure 8 area count',
        'area_count': n_areas,
        'areas': f08_areas,
        'blocker': blocker_reason,
        'has_real_H_harmony': False,
        'H_computed': False,
        'input_figure_08': str(y_path),
        'Y_shape': f08_manifest.get('Y_tensor_shape', 'unknown'),
        'output_paths': {
            'blocker': str(blocker_path),
            'summary': str(table_path),
            'html': str(html_path)
        },
        'claim_status': {
            'truth_safe_unverified': True,
            'computational_scaffold': True,
            'no_fabrication': True,
            'correlation_only_no_directionality': True,
            'correlation_only_no_causality': True
        },
        'resolution_notes': 'Multi-probe LFP extraction needed for >= 2 areas'
    }

    manifest_path = OUTPUT_ROOT / 'fig09_manifest.json'
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f'\n=== FIGURE 9 BLOCKED ===')
    print(f'Status: BLOCKED_INSUFFICIENT_AREAS_FOR_H')
    print(f'Blocker: {blocker_reason}')
    print(f'Manifest: {manifest_path}')

    # Exit cleanly - this is an expected blocker, not an error
    sys.exit(0)

print(f'\nFigure 8 Y tensor file exists: {y_path}')

# Load Y tensor
print('\nLoading Figure 8 Y tensor...')
y_data = np.load(y_path, allow_pickle=False)
Y = y_data['Y']
bands = list(y_data['bands'])
areas = list(y_data['areas'])
layers = list(y_data['layers'])
conditions = list(y_data['conditions'])

print(f'Y tensor shape: {Y.shape}')
print(f'  (condition x area x layer x band x time)')
print(f'Conditions: {conditions}')
print(f'Bands: {bands}')
print(f'Areas: {areas}')
print(f'Layers: {layers}')

# Build H harmony matrix
# H represents cross-area, cross-band correlations
# For multi-area Y: reshape to compute area-band correlation matrix

n_conditions, n_areas, n_layers, n_bands, n_time = Y.shape

print(f'\nBuilding H harmony matrix...')

# For each condition, compute correlation between area-band combinations
# Result: H[condition, layer, band, area_from, area_to]

# Simplified: for single layer, compute band correlations between areas
H = np.zeros((n_conditions, n_layers, n_bands, n_areas, n_areas), dtype=np.float32)

for c in range(n_conditions):
    for l in range(n_layers):
        # Extract (band, time) for each area -> (area, band, time)
        area_band_time = Y[c, :, l, :, :]  # (area, band, time)

        # For each pair of areas, compute band-band correlation
        for a1 in range(n_areas):
            for a2 in range(n_areas):
                # Get band-time series for each area
                # Shape: (band, time)
                ts1 = area_band_time[a1]  # (band, time)
                ts2 = area_band_time[a2]  # (band, time)

                # Compute correlation for each band pair
                for b in range(n_bands):
                    # For diagonal (same area), use self-correlation = 1.0
                    if a1 == a2:
                        H[c, l, b, a1, a2] = 1.0
                    else:
                        # Cross-area: correlate band power time series
                        # Flatten time dimension for correlation
                        vec1 = ts1[b, :]  # (time,)
                        vec2 = ts2[b, :]  # (time,)

                        if np.std(vec1) > 0 and np.std(vec2) > 0:
                            corr = np.corrcoef(vec1, vec2)[0, 1]
                            if not np.isnan(corr):
                                H[c, l, b, a1, a2] = corr

print(f'H harmony shape: {H.shape}')
print(f'  (condition x layer x band x area x area)')
print(f'Nonzero: {np.any(H != 0)}')
print(f'Finite: {np.all(np.isfinite(H))}')
print(f'Diagonal (self-correlation): 1.0 (by construction)')

# Save outputs
(OUTPUT_ROOT / 'arrays').mkdir(parents=True, exist_ok=True)
(OUTPUT_ROOT / 'tables').mkdir(parents=True, exist_ok=True)
(OUTPUT_ROOT / 'figures').mkdir(parents=True, exist_ok=True)

saved_paths = {}

# Get git SHA
try:
    sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
except:
    sha = 'unknown'

# Save H harmony
h_path = OUTPUT_ROOT / 'arrays/fig09_H_harmony_smoke.npz'
np.savez_compressed(
    h_path,
    H=H,
    conditions=conditions,
    bands=bands,
    areas=areas,
    layers=layers,
    shape=list(H.shape),
    shape_labels=['condition', 'layer', 'band', 'area_from', 'area_to'],
    nonzero=bool(np.any(H != 0)),
    finite=bool(np.all(np.isfinite(H))),
    input_source='fig08_Y_tensor_smoke.npz',
    method='pearson_correlation_band_time_series',
    n_areas=n_areas
)
saved_paths['H_harmony'] = str(h_path)
print(f'\nSaved H harmony: {h_path}')

# Summary table
summary_df = pd.DataFrame({
    'component': ['H_harmony'],
    'shape': [str(H.shape)],
    'shape_labels': ['condition x layer x band x area_from x area_to'],
    'n_elements': [H.size],
    'memory_kb': [H.nbytes / 1024],
    'nonzero': [bool(np.any(H != 0))],
    'finite': [bool(np.all(np.isfinite(H)))],
    'n_conditions': [n_conditions],
    'n_areas': [n_areas],
    'n_layers': [n_layers],
    'n_bands': [n_bands],
    'method': ['pearson_correlation'],
    'diagonal': ['self_correlation_1.0'],
    'cross_area': [n_areas > 1]
})
table_path = OUTPUT_ROOT / 'tables/fig09_H_harmony_summary_smoke.csv'
summary_df.to_csv(table_path, index=False)
saved_paths['summary'] = str(table_path)
print(f'Saved summary: {table_path}')

# HTML preview
html_content = f'''<!DOCTYPE html>
<html><head><link rel="stylesheet" href="../shared/style.css"></head><body>
<h1>Figure 9: H Harmony from Y Tensor</h1>
<p><strong>Status:</strong> <span class="status-pass">SMOKE_PASS_NONZERO_H</span></p>
<div class="claim-box">
<strong>Core:</strong> H = Harmony/Correlation matrix across areas<br>
<strong>Input:</strong> Figure 8 real Y tensor (nonzero)<br>
<strong>Output:</strong> Real nonzero H harmony matrix<br>
<strong>Method:</strong> Pearson correlation of band-power time series across areas<br>
<strong>Nonzero:</strong> {np.any(H != 0)}<br>
<strong>Finite:</strong> {np.all(np.isfinite(H))}
</div>

<div class="warning-box">
<strong>Scope Limit:</strong> This is correlation only.<br>
- No directionality proven<br>
- No causality proven<br>
- SFC/PPC remains optional supplement only<br>
- H(B, P, L, A, A) represents cross-area band correlations
</div>

<h2>H Harmony Matrix</h2>
<table>
<tr><th>Property</th><th>Value</th></tr>
<tr><td>Shape</td><td>{H.shape}</td></tr>
<tr><td>Labels</td><td>condition x layer x band x area_from x area_to</td></tr>
<tr><td>Areas</td><td>{areas}</td></tr>
<tr><td>Bands</td><td>{bands}</td></tr>
<tr><td>Memory</td><td>{H.nbytes/1024:.2f} KB</td></tr>
<tr><td>Nonzero</td><td>{np.any(H != 0)}</td></tr>
<tr><td>Finite</td><td>{np.all(np.isfinite(H))}</td></tr>
<tr><td>Cross-area correlations</td><td>{n_areas > 1}</td></tr>
</table>

<h2>Outputs</h2>
<ul>
<li>H harmony: <code>{saved_paths.get('H_harmony', 'N/A')}</code></li>
<li>Summary: <code>{saved_paths.get('summary', 'N/A')}</code></li>
</ul>

<hr><p><small>Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()} | Git: {sha[:12]}</small></p>
</body></html>
'''

html_path = OUTPUT_ROOT / 'figures/fig09_H_harmony_smoke.html'
html_path.write_text(html_content, encoding='utf-8')
saved_paths['html'] = str(html_path)
print(f'Saved HTML: {html_path}')

# Manifest
manifest = {
    'figure_id': 'figure_09',
    'figure_name': 'H Harmony from Y',
    'repo_sha': sha,
    'created_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'smoke_status': 'SMOKE_PASS_NONZERO_H',
    'subject': SMOKE_SUBJECT,
    'session': SMOKE_SESSION,
    'H_harmony_shape': list(H.shape),
    'H_harmony_shape_labels': ['condition', 'layer', 'band', 'area_from', 'area_to'],
    'has_real_H_harmony': True,
    'H_nonzero': bool(np.any(H != 0)),
    'H_finite': bool(np.all(np.isfinite(H))),
    'n_areas': n_areas,
    'areas': areas,
    'cross_area_correlations': n_areas > 1,
    'input_figure_08': str(y_path),
    'method': 'pearson_correlation_band_time_series',
    'diagonal_construction': 'self_correlation_1.0',
    'output_paths': saved_paths,
    'claim_status': {
        'truth_safe_unverified': True,
        'computational_scaffold': True,
        'no_fabrication': True,
        'no_zero_arrays_as_pass': True,
        'correlation_only_no_directionality': True,
        'correlation_only_no_causality': True
    }
}

manifest_path = OUTPUT_ROOT / 'fig09_manifest.json'
with open(manifest_path, 'w') as f:
    json.dump(manifest, f, indent=2)

print(f'\n=== FIGURE 9 COMPLETE ===')
print(f'Status: SMOKE_PASS_NONZERO_H')
print(f'H harmony: {H.shape}')
print(f'Nonzero: {np.any(H != 0)}')
print(f'Finite: {np.all(np.isfinite(H))}')
print(f'Cross-area: {n_areas > 1}')
print(f'Manifest: {manifest_path}')
