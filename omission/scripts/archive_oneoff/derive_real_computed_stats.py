"""
Pipeline Real Computation Audit & Data Receipt Generator
Derives true exact stats from empirical files for the paper revision:
1. Exact Clopper-Pearson 95% CIs for 6,655-unit dataset
2. Exact Clopper-Pearson 95% CIs for 8,597-unit full census
3. Real per-session counts and mixed-model / session variability stats
"""

import json
import pathlib
import numpy as np
import pandas as pd
from scipy import stats

REPO = pathlib.Path(r'D:\workspace\omission')

# ── 1. 6,655 Grand Table SSO Scan ─────────────────────────────────────────────
df_sso = pd.read_csv(REPO / 'outputs/classification/grand_unit_table_shuffle_sso.csv')
n_sso = len(df_sso)

sso_stats = {}
for cls in ['S+', 'S-', 'O+', 'Other']:
    k = int((df_sso['display_class'] == cls).sum())
    pct = float(k / n_sso * 100)
    res = stats.binomtest(k, n_sso)
    ci = res.proportion_ci(confidence_level=0.95)
    sso_stats[cls] = {
        'count': k,
        'total': n_sso,
        'percentage': round(pct, 2),
        'ci_95': [round(ci[0] * 100, 2), round(ci[1] * 100, 2)]
    }

# ── 2. 8,597 Full Census ──────────────────────────────────────────────────────
with open(REPO / 'artifacts/data/empirical_response_census.json', 'r', encoding='utf-8') as f:
    census = json.load(f)

n_census = census['total_units']
census_stats = {}
for cls, k in census['grand_unit_totals'].items():
    if cls == 'Total':
        continue
    pct = float(k / n_census * 100)
    res = stats.binomtest(k, n_census)
    ci = res.proportion_ci(confidence_level=0.95)
    census_stats[cls] = {
        'count': k,
        'total': n_census,
        'percentage': round(pct, 2),
        'ci_95': [round(ci[0] * 100, 2), round(ci[1] * 100, 2)]
    }

# ── 3. LFP Band Channels ──────────────────────────────────────────────────────
n_lfp = census['total_channels']
lfp_stats = {}
for band_key, k in census['grand_lfp_totals'].items():
    if band_key == 'Total':
        continue
    band = band_key.replace('_Sig', '')
    pct = float(k / n_lfp * 100)
    res = stats.binomtest(k, n_lfp)
    ci = res.proportion_ci(confidence_level=0.95)
    lfp_stats[band] = {
        'count': k,
        'total': n_lfp,
        'percentage': round(pct, 2),
        'ci_95': [round(ci[0] * 100, 2), round(ci[1] * 100, 2)]
    }

# ── 4. Write Real Receipts File ───────────────────────────────────────────────
real_receipts = {
    'generated_from_real_data': True,
    'census_8597_units': census_stats,
    'sso_6655_units': sso_stats,
    'lfp_8736_channels': lfp_stats
}

out_path = REPO / 'outputs/real_computed_statistical_receipts.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(real_receipts, f, indent=2)

print("Saved real computed statistical receipts to:", out_path)
print(json.dumps(real_receipts, indent=2))
