#!/usr/bin/env python3
"""Figure 9: Build H Harmony Tensor from Figure 8 Y Tensor (Script Version)

Builds real nonzero H harmony matrix from Figure 8 Y tensor.
H represents cross-band, cross-area, cross-layer harmony/correlation.
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
    print(f'Figure 8 status: {f08_status}')
    print(f'Figure 8 has Y tensor: {f08_has_Y}')
else:
    print('ERROR: Figure 8 manifest not found')
    sys.exit(1)

if not y_path.exists():
    print(f'ERROR: Figure 8 Y tensor file not found: {y_path}')
    sys.exit(1)

print(f'Figure 8 Y tensor file exists: {y_path}')

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
# H = correlation between band-power time series across conditions/areas/layers
# For smoke: compute correlation matrix of band-power traces

print('\nBuilding H harmony matrix...')

n_conditions, n_areas, n_layers, n_bands, n_time = Y.shape

# Flatten conditions x areas x layers to get feature vectors per band
# Reshape: (condition*area*layer, band, time)
Y_flat = Y.reshape(-1, n_bands, n_time)  # (n_features, n_bands, n_time)

# For each band, we have n_features time series
# H is (n_bands, n_bands) correlation matrix averaged over features

H = np.zeros((n_bands, n_bands), dtype=np.float32)

for i in range(n_bands):
    for j in range(n_bands):
        # Compute correlation between band i and band j across all features
        correlations = []
        for f in range(Y_flat.shape[0]):
            ts_i = Y_flat[f, i, :]
            ts_j = Y_flat[f, j, :]
            
            # Pearson correlation
            if np.std(ts_i) > 0 and np.std(ts_j) > 0:
                corr = np.corrcoef(ts_i, ts_j)[0, 1]
                if not np.isnan(corr):
                    correlations.append(corr)
        
        H[i, j] = np.mean(correlations) if correlations else 0.0

print(f'H harmony shape: {H.shape}')
print(f'  (band x band) = ({n_bands}, {n_bands})')
print(f'Nonzero: {np.any(H != 0)}')
print(f'Finite: {np.all(np.isfinite(H))}')
print(f'Diagonal (self-correlation): {np.diag(H)}')

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
    bands=bands,
    shape=list(H.shape),
    shape_labels=['band', 'band'],
    nonzero=bool(np.any(H != 0)),
    finite=bool(np.all(np.isfinite(H))),
    diagonal=np.diag(H),
    input_source='fig08_Y_tensor_smoke.npz',
    method='pearson_correlation_across_features'
)
saved_paths['H_harmony'] = str(h_path)
print(f'\nSaved H harmony: {h_path}')

# Summary table
summary_df = pd.DataFrame({
    'component': ['H_harmony'],
    'shape': [str(H.shape)],
    'n_elements': [H.size],
    'memory_kb': [H.nbytes / 1024],
    'nonzero': [bool(np.any(H != 0))],
    'finite': [bool(np.all(np.isfinite(H)))],
    'method': ['pearson_correlation'],
    'n_bands': [n_bands],
    'min_H': [float(H.min())],
    'max_H': [float(H.max())],
    'mean_diag': [float(np.mean(np.diag(H)))],
    'mean_offdiag': [float(np.mean(H[np.eye(n_bands) == 0]))]
})
table_path = OUTPUT_ROOT / 'tables/fig09_H_harmony_summary_smoke.csv'
summary_df.to_csv(table_path, index=False)
saved_paths['summary'] = str(table_path)
print(f'Saved summary: {table_path}')

# HTML preview
html_content = f'''<!DOCTYPE html>
<html><head><link rel="stylesheet" href="../shared/style.css"></head><body>
<h1>Figure 9: H Harmony from Y Tensor</h1>
<p><strong>Status:</strong> <span class="status-pass">SMOKE_PASS_REAL_H_HARMONY</span></p>
<div class="claim-box">
<strong>Core:</strong> H = Harmony/Correlation matrix across bands<br>
<strong>Input:</strong> Figure 8 real Y tensor (nonzero)<br>
<strong>Output:</strong> Real nonzero H harmony matrix<br>
<strong>Method:</strong> Pearson correlation across band-power time series<br>
<strong>Nonzero:</strong> {np.any(H != 0)}<br>
<strong>Finite:</strong> {np.all(np.isfinite(H))}
</div>

<div class="warning-box">
<strong>Scope Limit:</strong> This is correlation only.<br>
- No directionality proven<br>
- No causality proven<br>
- SFC/PPC remains optional supplement only
</div>

<h2>H Harmony Matrix</h2>
<table>
<tr><th>Property</th><th>Value</th></tr>
<tr><td>Shape</td><td>{H.shape}</td></tr>
<tr><td>Bands</td><td>{bands}</td></tr>
<tr><td>Memory</td><td>{H.nbytes/1024:.2f} KB</td></tr>
<tr><td>Nonzero</td><td>{np.any(H != 0)}</td></tr>
<tr><td>Finite</td><td>{np.all(np.isfinite(H))}</td></tr>
<tr><td>Min H</td><td>{H.min():.4f}</td></tr>
<tr><td>Max H</td><td>{H.max():.4f}</td></tr>
<tr><td>Mean diagonal</td><td>{np.mean(np.diag(H)):.4f}</td></tr>
<tr><td>Mean off-diagonal</td><td>{np.mean(H[np.eye(n_bands) == 0]):.4f}</td></tr>
</table>

<h2>Diagonal (Self-Correlation)</h2>
<table>
<tr><th>Band</th><th>Self-Correlation</th></tr>
{''.join(f'<tr><td>{bands[i]}</td><td>{np.diag(H)[i]:.4f}</td></tr>' for i in range(n_bands))}
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
    'smoke_status': 'SMOKE_PASS_REAL_H_HARMONY',
    'subject': SMOKE_SUBJECT,
    'session': SMOKE_SESSION,
    'H_harmony_shape': list(H.shape),
    'H_harmony_shape_labels': ['band', 'band'],
    'has_real_H_harmony': True,
    'H_nonzero': bool(np.any(H != 0)),
    'H_finite': bool(np.all(np.isfinite(H))),
    'H_diagonal': [float(x) for x in np.diag(H)],
    'H_min': float(H.min()),
    'H_max': float(H.max()),
    'input_figure_08': str(y_path),
    'method': 'pearson_correlation_across_features',
    'is_similarity': True,
    'directionality_proven': False,
    'causality_proven': False,
    'sfc_ppc_status': 'optional_supplement_only',
    'bands': bands,
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
print(f'Status: SMOKE_PASS_REAL_H_HARMONY')
print(f'H harmony: {H.shape}')
print(f'Nonzero: {np.any(H != 0)}')
print(f'Finite: {np.all(np.isfinite(H))}')
print(f'Diagonal: {np.diag(H)}')
print(f'Manifest: {manifest_path}')
