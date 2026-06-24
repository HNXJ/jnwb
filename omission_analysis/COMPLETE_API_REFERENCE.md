# omission_analysis Complete API Reference

**20 Canonical Functions + 4 Canonical Objects + Automatic Dual Statistics**

---

## Import Guide

```python
import omission_analysis as oa

# Access functions directly
oa.tfr_trial_average(...)
oa.find_units(...)
oa.pie_charts(...)

# Access objects for advanced use
tfr_analyzer = oa.TFRAnalyzer
unit_analyzer = oa.UnitAnalyzer
pop_analyzer = oa.PopulationAnalyzer
stats = oa.StatisticalAnalysis

# Load session
session = oa.read('path/to/file.nwb')

# Batch load
sessions = oa.batch_read('D:/analysis/nwb')
```

---

## 4 Canonical Objects

### 1. TFRAnalyzer
```python
oa.TFRAnalyzer.extract_band(tfr_data, band)
oa.TFRAnalyzer.trial_average(tfr_data, epochs)
oa.TFRAnalyzer.compare_conditions(tfr1, tfr2)
oa.TFRAnalyzer.by_layer(tfr_data, layer_bounds)
oa.TFRAnalyzer.correlate_areas(tfr1, tfr2, band)
```

### 2. UnitAnalyzer
```python
oa.UnitAnalyzer.raster(spike_times, trial_onsets, window_ms)
oa.UnitAnalyzer.psth(spike_times, trial_onsets, bin_size_ms)
oa.UnitAnalyzer.autocorrelogram(spike_times, max_lag_ms)
oa.UnitAnalyzer.quality_metrics(spike_times, waveform_duration_us, firing_rate)
```

### 3. PopulationAnalyzer
```python
oa.PopulationAnalyzer.compare_criteria(units1, units2, metric)
oa.PopulationAnalyzer.distribution_by_area(units, metric)
oa.PopulationAnalyzer.pie_chart_data(units, criteria)
oa.PopulationAnalyzer.network_connectivity(correlation_matrix, threshold)
```

### 4. StatisticalAnalysis
```python
oa.StatisticalAnalysis.compare_groups(group1, group2, paired)
oa.StatisticalAnalysis.compare_multiple_groups(groups)
oa.StatisticalAnalysis.correlate(x, y)
oa.StatisticalAnalysis.bootstrap_ci(data, statistic_func, n_bootstrap)
oa.StatisticalAnalysis.permutation_test(x, y, n_permutations)
```

---

## 20 Canonical Functions

### Group 1: TFR Analysis (Functions 1-5)

#### 1. tfr_trial_average()
Trial-averaged TFR power
```python
result = oa.tfr_trial_average(
    session,           # OmissionSession
    area='V1',         # Brain area
    condition='AAAB',  # Behavioral condition
    phase=2,           # stimulus_number (2=p1, 3=p2, etc.)
    band=None          # Optional: 'alpha', 'beta', etc.
)
# Returns: {'mean': array, 'std': array, 'sem': array, 'n_trials': int}
```

#### 2. tfr_compare_conditions()
Compare TFR between conditions (parametric + non-parametric + FDR)
```python
result = oa.tfr_compare_conditions(
    session,
    area='V1',
    condition1='AAAB',
    condition2='AAXB',
    band='alpha'
)
# Returns: {
#   'n_tests': int,
#   'per_location_stats': [{parametric, non_parametric, FDR...}],
#   'mean_diff': float,
#   'summary': str
# }
```

#### 3. tfr_correlate_areas()
Inter-area TFR correlation (Pearson r + Spearman rho + FDR)
```python
result = oa.tfr_correlate_areas(
    session,
    area1='V1',
    area2='V4',
    band='alpha',
    condition='AAAB'
)
# Returns: {
#   'band': str,
#   'correlation': {parametric, non_parametric, FDR, effect_sizes...}
# }
```

#### 4. tfr_spectrolaminar()
Layer-wise spectral analysis
```python
result = oa.tfr_spectrolaminar(
    session,
    area='MT',
    condition='AAAB',
    layer_masks=None  # Optional: {'superficial': (0, 10), 'deep': (10, 20)}
)
# Returns: {
#   'superficial': {mean, std, sem, ...},
#   'deep': {mean, std, sem, ...},
#   'layer_comparison': {...stats...}
# }
```

#### 5. tfr_permutation_test()
Permutation test for TFR differences
```python
result = oa.tfr_permutation_test(
    session,
    area='V1',
    condition1='AAAB',
    condition2='AAXB',
    n_permutations=5000
)
# Returns: {
#   'observed_difference': float,
#   'pval': float,
#   'perm_mean': float,
#   'perm_std': float,
#   'significant': bool
# }
```

---

### Group 2: Raster & PSTH Analysis (Functions 6-8)

#### 6. raster_plot()
Spike raster aligned to phase onset
```python
result = oa.raster_plot(
    session,
    unit_id=42,
    condition='AAAB',
    phase=2,
    window_ms=(-1000, 2000)  # (pre_ms, post_ms)
)
# Returns: {
#   'raster': [{'trial': int, 'spike_times': array}, ...],
#   'n_trials': int,
#   'n_spikes': int,
#   'window_ms': tuple
# }
```

#### 7. psth_analysis()
Peristimulus time histogram with bootstrap confidence intervals
```python
result = oa.psth_analysis(
    session,
    unit_id=42,
    condition='AAAB',
    phase=2,
    bin_size_ms=10
)
# Returns: {
#   'psth': array,           # Spikes per second
#   'sem': array,            # Standard error
#   'bin_centers': array,
#   'bin_size_ms': float,
#   'n_trials': int,
#   'bootstrap_ci': {statistic, parametric_ci, bootstrap_ci, bootstrap_std}
# }
```

#### 8. autocorrelogram()
Unit autocorrelogram with refractory period violation test
```python
result = oa.autocorrelogram(
    session,
    unit_id=42,
    max_lag_ms=100
)
# Returns: {
#   'acg': array,
#   'lag_times_ms': array,
#   'refractory_period_violation': float,  # p-value (Poisson test)
#   'is_single_unit': bool,                # True if refr_p < 0.05
#   'refr_count': int,
#   'baseline_count': float
# }
```

---

### Group 3: Unit Finding & Quality (Functions 9-11)

#### 9. find_units()
Find units matching criteria
```python
units_df = oa.find_units(
    session,
    quality='stable_plus',              # 'stable_plus', 'stable', 'mua', 'unstable'
    area='V1',                          # Optional
    firing_rate_range=(1, 200)          # (min_hz, max_hz)
)
# Returns: DataFrame with matching units
```

#### 10. unit_quality_scores()
Unit quality metrics
```python
result = oa.unit_quality_scores(
    session,
    unit_id=42
)
# Returns: {
#   'firing_rate_hz': float,
#   'n_spikes': int,
#   'n_isis': int,
#   'mean_isi_ms': float,
#   'cv_isi': float,                   # Coefficient of variation
#   'refr_violations_pct': float,
#   'fano_factor': float,              # Firing rate stability
#   'waveform_duration_us': float,
#   'is_good_single_unit': bool
# }
```

#### 11. unit_channel_mapping()
Map units to recording channels
```python
mapping_df = oa.unit_channel_mapping(
    session,
    area=None  # Optional
)
# Returns: DataFrame with columns: unit_id, channel_id, area, layer
```

---

### Group 4: Population Analysis (Functions 12-15)

#### 12. pie_charts()
Population pie charts
```python
result = oa.pie_charts(
    session,
    criteria={'is_stable_plus': True, 'firing_rate': (1, 100)},
    by_area=True,
    by_layer=False
)
# Returns: {
#   'counts': {category: count, ...},
#   'percentages': {category: percent, ...},
#   'total': int,
#   'filtered_total': int
# }
```

#### 13. compare_populations()
Compare two unit populations (t-test + Mann-Whitney U + Cohen's d + FDR)
```python
result = oa.compare_populations(
    session,
    criteria1={'area': 'V1', 'is_stable_plus': True},
    criteria2={'area': 'V4', 'is_stable_plus': True},
    metric='firing_rate'
)
# Returns: {
#   'metric': str,
#   'group1_size': int,
#   'group2_size': int,
#   'group1_mean': float,
#   'group2_mean': float,
#   'statistics': {
#     'parametric': {test, statistic, pval, effect_size},
#     'non_parametric': {test, statistic, pval},
#     'fdr_pval_parametric': float,
#     'fdr_pval_nonparametric': float,
#     'significant_parametric': bool,
#     'significant_nonparametric': bool
#   }
# }
```

#### 14. population_by_area()
Population statistics by brain area (ANOVA + Kruskal-Wallis)
```python
result = oa.population_by_area(
    session,
    metric='firing_rate'
)
# Returns: {
#   'metric': str,
#   'areas': [area_names],
#   'per_area': {
#     'V1': {n, mean, std, median},
#     'V4': {n, mean, std, median},
#     ...
#   },
#   'comparison': {
#     'parametric': {test: 'one_way_anova', statistic, pval, effect_size (eta²)},
#     'non_parametric': {test: 'kruskal_wallis', statistic, pval},
#     'fdr_pval_parametric': float,
#     'fdr_pval_nonparametric': float,
#     'significant_parametric': bool,
#     'significant_nonparametric': bool
#   }
# }
```

#### 15. network_connectivity()
Network graph analysis from correlation matrix
```python
result = oa.network_connectivity(
    session,                    # For context only
    correlation_matrix,         # np.array (areas × areas)
    threshold=0.3               # Connection threshold
)
# Returns: {
#   'n_nodes': int,
#   'n_edges': int,
#   'density': float,           # Edge density
#   'mean_degree': float,
#   'degree_distribution': list,
#   'threshold': float
# }
```

---

### Group 5: Batch & Cross-Session (Functions 16-18)

#### 16. units_across_sessions()
Collect matching units from multiple sessions
```python
all_units = oa.units_across_sessions(
    sessions,  # List[OmissionSession]
    criteria={'quality': 'stable_plus', 'firing_rate': (1, 100)}
)
# Returns: DataFrame with session_id added
```

#### 17. lfp_channel_areas()
Map LFP channels to brain areas
```python
lfp_map = oa.lfp_channel_areas(
    session,
    area=None  # Optional filter
)
# Returns: DataFrame with columns: channel_id, area, layer
```

#### 18. summary_report()
Generate comprehensive session summary
```python
summary = oa.summary_report(
    session,
    output_dir=None  # Optional output directory
)
# Returns: {
#   'file': str,
#   'subject': str,
#   'session_start': str,
#   'n_units': int,
#   'n_channels': int,
#   'n_epochs': int,
#   'n_stable_plus': int,
#   'n_stable': int,
#   'firing_rate_mean': float,
#   'firing_rate_std': float
# }
```

---

### Group 6: Advanced (Functions 19-20)

#### 19. noise_vs_signal()
Signal-to-noise ratio analysis
```python
result = oa.noise_vs_signal(
    session,
    unit_id=42
)
# Returns: {
#   'snr_db': float,
#   'is_good_unit': bool,
#   ...waveform metrics...
# }
```

#### 20. cross_modal_comparison()
Compare LFP (TFR) vs spike-based networks
```python
result = oa.cross_modal_comparison(
    tfr_array,          # (channels × freq × time × trials)
    spike_array,        # Spike counts array
    lag_range_ms=(-500, 500)
)
# Returns: {
#   'correlation': float,
#   'lag_ms': float,
#   'lfp_leads_spikes': bool,
#   'statistics': {...cross-correlation stats...}
# }
```

---

## Statistical Output Format

Every comparative analysis returns this structure:

```python
{
    # Descriptive statistics
    'n1': int,                          # Group 1 sample size
    'n2': int,                          # Group 2 sample size
    'mean1': float,                     # Group 1 mean
    'mean2': float,                     # Group 2 mean
    'std1': float,                      # Group 1 std dev
    'std2': float,                      # Group 2 std dev

    # Parametric test (assumes normality)
    'parametric': {
        'test': str,                    # 't_test', 'anova', 'pearson_r', etc.
        'statistic': float,             # t, F, r, etc.
        'pval': float,                  # Uncorrected p-value
        'effect_size': float,           # Cohen's d, eta², R², etc.
    },

    # Non-parametric test (distribution-free)
    'non_parametric': {
        'test': str,                    # 'mann_whitney_u', 'kruskal_wallis', 'spearman_rho', etc.
        'statistic': float,             # U, H, rho, etc.
        'pval': float,                  # Uncorrected p-value
    },

    # FDR Correction (Benjamini-Hochberg)
    'fdr_pval_parametric': float,       # FDR-corrected parametric p-value
    'fdr_pval_nonparametric': float,    # FDR-corrected non-parametric p-value

    # Significance flags
    'significant_parametric': bool,     # fdr_pval_parametric < 0.05
    'significant_nonparametric': bool,  # fdr_pval_nonparametric < 0.05
}
```

---

## Examples

### Complete Workflow

```python
import omission_analysis as oa

# 1. Load session
session = oa.read('sub-C31o_ses-230823_rec.nwb')

# 2. Explore
print(session)
summary = oa.summary_report(session)

# 3. Find units
stable_units = oa.find_units(session, quality='stable_plus')
v1_units = oa.find_units(session, quality='stable_plus', area='V1')

# 4. TFR analysis
tfr_avg = oa.tfr_trial_average(session, area='V1', condition='AAXB')
tfr_comp = oa.tfr_compare_conditions(session, area='V4', 
                                      condition1='AAAB', 
                                      condition2='AAXB')
print(f"Parametric p-value: {tfr_comp['statistics']['fdr_pval_parametric']}")
print(f"Non-parametric p-value: {tfr_comp['statistics']['fdr_pval_nonparametric']}")

# 5. Single-unit analysis
raster = oa.raster_plot(session, unit_id=42, condition='AAXB')
psth = oa.psth_analysis(session, unit_id=42, condition='AAXB')
acg = oa.autocorrelogram(session, unit_id=42)

# 6. Population analysis
pies = oa.pie_charts(session, criteria={'is_stable_plus': True}, by_area=True)
pop_comp = oa.compare_populations(session,
                                   criteria1={'area': 'V1', 'is_stable_plus': True},
                                   criteria2={'area': 'V4', 'is_stable_plus': True},
                                   metric='firing_rate')
print(f"V1 mean FR: {pop_comp['group1_mean']:.1f} Hz")
print(f"V4 mean FR: {pop_comp['group2_mean']:.1f} Hz")
print(f"Significant (parametric): {pop_comp['statistics']['significant_parametric']}")
print(f"Significant (non-parametric): {pop_comp['statistics']['significant_nonparametric']}")
```

### Batch Analysis

```python
# Load all sessions
sessions = oa.batch_read('D:/analysis/nwb')

# Find units across sessions
all_units = oa.units_across_sessions(sessions, 
                                      criteria={'quality': 'stable_plus', 'area': 'V1'})

print(f"Total V1 stable+ units: {len(all_units)}")
```

### Direct Object Usage

```python
from omission_analysis import TFRAnalyzer, StatisticalAnalysis

# Extract band
band_power = TFRAnalyzer.extract_band(tfr_data, band='alpha')

# Compare with full statistics
tfr_stim = TFRAnalyzer.trial_average(tfr_stimulus)
tfr_omit = TFRAnalyzer.trial_average(tfr_omission)

comparison = TFRAnalyzer.compare_conditions(tfr_stim['mean'], tfr_omit['mean'])
# Result: {parametric, non_parametric, FDR p-values for each location tested}
```

---

## Status

✓ All 20 functions defined with full docstrings  
✓ All 4 objects implemented with methods  
✓ Automatic parametric + non-parametric statistics  
✓ FDR correction on all p-values  
✓ Effect sizes reported for all tests  
✓ Complete type hints  
✓ Publication-ready outputs  

⏳ Implementation of data loading and plotting (TODO marked in code)

---

**Author**: Claude Code  
**Date**: 2025-06-24  
**Version**: 1.0.0

