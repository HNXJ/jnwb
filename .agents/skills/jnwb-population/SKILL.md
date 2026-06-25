---
name: jnwb-population
description: |
  Population-level analysis using jnwb. Covers PopulationAnalyzer object,
  the canonical functions compare_populations, population_by_area, pie_charts,
  network_connectivity, and units_across_sessions. Use this for any analysis
  that groups, compares, or summarises multiple units or areas at once.
---

# jnwb-population: Population Analysis

Module root: `d:/workspace/omission/jnwb/`  
Primary files: `analyzers.py` (PopulationAnalyzer), `functions.py` (compare_populations, population_by_area, pie_charts, network_connectivity, units_across_sessions)

## Import

```python
import sys; sys.path.insert(0, 'd:/workspace/omission')
import jnwb as oa
from jnwb import PopulationAnalyzer
from jnwb import (
    compare_populations, population_by_area,
    pie_charts, network_connectivity,
    units_across_sessions,
)
```

## PopulationAnalyzer Object

```python
# Compare two populations (dual stats + FDR)
result = PopulationAnalyzer.compare_criteria(units_v1, units_v4, metric='firing_rate')
# Returns: {'group1_mean': 5.2, 'group2_mean': 8.1,
#           'statistics': {'parametric': {...}, 'non_parametric': {...},
#                          'fdr_pval_parametric': ..., 'fdr_pval_nonparametric': ...}}

# Per-area statistics (ANOVA + Kruskal-Wallis)
by_area = PopulationAnalyzer.distribution_by_area(all_units, metric='waveform_duration')
# Returns: {'areas': ['V1','V4','MT'], 'per_area': {...}, 'comparison': {ANOVA, K-W, eta², FDR}}

# Pie chart counts and percentages
pie = PopulationAnalyzer.pie_chart_data(all_units, criteria={'is_stable_plus': True})
# Returns: {'counts': {'V1': 45, 'V4': 23, ...}, 'percentages': {...}, 'total': 68}

# Network graph metrics from correlation matrix
net = PopulationAnalyzer.network_connectivity(corr_matrix, threshold=0.3)
# Returns: {'n_nodes': 7, 'n_edges': 12, 'density': 0.57, 'mean_degree': 3.4, ...}
```

## Canonical Functions (session-level)

```python
session = oa.read('path/to/file.nwb')

# Compare two subpopulations
comp = compare_populations(session,
    criteria1={'is_stable_plus': True, 'area': 'V1'},
    criteria2={'is_stable_plus': True, 'area': 'V4'},
    metric='firing_rate')

# Distribution by area
by_area = population_by_area(session, metric='waveform_duration')

# Pie charts
pies = pie_charts(session, criteria={'is_stable_plus': True}, by_area=True)

# Network connectivity
net = network_connectivity(session, correlation_matrix, threshold=0.3)
```

## OmissionSession Shortcut

```python
# Pie charts with single session
result = session.pie_charts(criteria={'is_stable_plus': True}, by_area=True)
result = session.pie_charts(criteria={'firing_rate': (20, 200)}, by_layer=True)
```

## Cross-Session Aggregation

```python
sessions = oa.batch_read('D:/analysis/nwb')

# Collect stable+ units across all 13 sessions
all_units_df = units_across_sessions(sessions, criteria={'quality': 'stable_plus'})
# Returns DataFrame with session_id column added

# Example: compare areas across all sessions
for sess in sessions:
    by_area = population_by_area(sess, metric='firing_rate')
```

## Grand Population Counts

| Category              | N      |
|-----------------------|--------|
| All units             | 6,040  |
| Stable-plus           | 661    |
| Stable (all)          | 3,071  |
| Superficial (putative)| 614    |
| Deep (putative)       | 1,813  |
| Unresolved laminar    | ~3,613 |
| S+ (omission resp.)   | 1,468  |
| S- (omission resp.)   | 986    |
| Other / non-selective | 3,586  |
| Bursty                | 12+    |

## Presence Ratio Tiers (Panel A)

| Label           | Threshold       |
|-----------------|-----------------|
| Low             | < 50 % presence |
| Moderate-low    | 50–80 %         |
| Moderate        | 80–98 %         |
| Present (gate)  | ≥ 98 %          |
