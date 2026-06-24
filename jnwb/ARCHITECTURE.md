# jnwb Architecture: 20 Functions + 4 Objects

Complete, production-grade API for omission experiment analysis.

## Core Design

**Philosophy**: `jnwb.<function>(<data>, <context>, <parameters>)`

Every analysis automatically provides:
- ✓ Parametric statistics (t-test, ANOVA, Pearson r, etc.)
- ✓ Non-parametric equivalent (Mann-Whitney U, Kruskal-Wallis, Spearman rho, etc.)
- ✓ Effect sizes (Cohen's d, r², eta², etc.)
- ✓ FDR correction (Benjamini-Hochberg, α=0.05)
- ✓ Publication-ready outputs

---

## 4 Canonical Objects

### 1. TFRAnalyzer
Time-Frequency Representation analysis

**Methods:**
- `extract_band(tfr_data, band)` — Extract frequency band
- `trial_average(tfr_data, epochs)` — Trial-average power
- `compare_conditions(tfr1, tfr2)` — Compare with dual stats + FDR
- `by_layer(tfr_data, layer_bounds)` — Spectrolaminar analysis
- `correlate_areas(tfr1, tfr2, band)` — Inter-area correlation with stats

**Example:**
```python
from jnwb import TFRAnalyzer

alpha_power = TFRAnalyzer.extract_band(tfr_data, 'alpha')
avg = TFRAnalyzer.trial_average(alpha_power)

comparison = TFRAnalyzer.compare_conditions(tfr_stim, tfr_omit)
# Returns: {'parametric': {...}, 'non_parametric': {...}, 'fdr_pval_parametric': ...}
```

### 2. UnitAnalyzer
Single-unit spike analysis

**Methods:**
- `raster(spike_times, trial_onsets, window_ms)` — Spike raster
- `psth(spike_times, trial_onsets, bin_size_ms)` — PSTH with bootstrap CI
- `autocorrelogram(spike_times, max_lag_ms)` — ACG with refractory period test
- `quality_metrics(spike_times, waveform_duration, firing_rate)` — SNR & quality
- `_acg_pearson()` — Internal ACG computation

**Example:**
```python
from jnwb import UnitAnalyzer

raster_data = UnitAnalyzer.raster(spike_times, trial_onsets, window_ms=(-500, 2000))
psth_result = UnitAnalyzer.psth(spike_times, trial_onsets, bin_size_ms=10)
# Returns: {'psth': array, 'sem': array, 'bootstrap_ci': {...}}

acg = UnitAnalyzer.autocorrelogram(spike_times, max_lag_ms=100)
# Returns: {'acg': array, 'refractory_period_violation': p_value, 'is_single_unit': bool}

quality = UnitAnalyzer.quality_metrics(spike_times, waveform_duration_us=400, firing_rate=15)
# Returns: {'firing_rate_hz': 15, 'refr_violations_pct': 2.1, 'is_good_single_unit': True, ...}
```

### 3. PopulationAnalyzer
Population-level statistics

**Methods:**
- `compare_criteria(units1, units2, metric)` — Compare populations with dual stats + FDR
- `distribution_by_area(units, metric)` — Per-area statistics with ANOVA + K-W
- `pie_chart_data(units, criteria)` — Generate pie chart counts/percentages
- `network_connectivity(correlation_matrix, threshold)` — Network graph metrics

**Example:**
```python
from jnwb import PopulationAnalyzer

comparison = PopulationAnalyzer.compare_criteria(v1_units, v4_units, metric='firing_rate')
# Returns: {'group1_mean': 5.2, 'group2_mean': 8.1, 'statistics': {...parametric, non_parametric, FDR...}}

by_area = PopulationAnalyzer.distribution_by_area(all_units, metric='waveform_duration')
# Returns: {'areas': ['V1', 'V4', 'MT'], 'per_area': {...}, 'comparison': {...ANOVA, K-W, FDR...}}

pie = PopulationAnalyzer.pie_chart_data(all_units, criteria={'is_stable_plus': True})
# Returns: {'counts': {'area1': 45, 'area2': 23}, 'percentages': {...}, 'total': 68}

net = PopulationAnalyzer.network_connectivity(corr_matrix, threshold=0.3)
# Returns: {'n_nodes': 7, 'n_edges': 12, 'density': 0.57, 'mean_degree': 3.4, ...}
```

### 4. StatisticalAnalysis
Automatic parametric + non-parametric testing

**Methods:**
- `compare_groups(group1, group2, paired=False)` — t-test + Mann-Whitney U + Cohen's d
- `compare_multiple_groups(groups)` — ANOVA + Kruskal-Wallis + eta²
- `correlate(x, y)` — Pearson r + Spearman rho + R²
- `bootstrap_ci(data, statistic_func, n_bootstrap)` — Bootstrap confidence intervals
- `permutation_test(x, y, n_permutations)` — Permutation test for differences

**Example:**
```python
from jnwb import StatisticalAnalysis

# Independent groups comparison
result = StatisticalAnalysis.compare_groups(v1_data, v4_data, paired=False)
# Returns: {
#   'parametric': {'test': 'independent_t_test', 'statistic': 2.34, 'pval': 0.021, 'effect_size': 0.45},
#   'non_parametric': {'test': 'mann_whitney_u', 'statistic': 1200, 'pval': 0.018},
#   'fdr_pval_parametric': 0.042,  # Benjamini-Hochberg corrected
#   'fdr_pval_nonparametric': 0.036,
#   'significant_parametric': True,
#   'significant_nonparametric': True,
# }

# Multiple groups
groups = {'V1': v1_data, 'V4': v4_data, 'MT': mt_data}
result = StatisticalAnalysis.compare_multiple_groups(groups)
# Returns: {ANOVA results, Kruskal-Wallis results, eta² effect size, per-group summaries, FDR corrections}

# Correlation
corr = StatisticalAnalysis.correlate(firing_rate, waveform_duration)
# Returns: {Pearson r + pval, Spearman rho + pval, R², FDR-corrected pvals}

# Bootstrap confidence interval
ci = StatisticalAnalysis.bootstrap_ci(data, statistic_func=np.mean, n_bootstrap=10000, ci=0.95)
# Returns: {'statistic': 5.2, 'parametric_ci': (4.8, 5.6), 'bootstrap_ci': (4.9, 5.5)}

# Permutation test
perm_result = StatisticalAnalysis.permutation_test(group1, group2, n_permutations=5000)
# Returns: {'observed_difference': 1.2, 'pval': 0.0008, 'significant': True, ...}
```

---

## 20 Canonical Functions

### TFR Analysis (1-5)

**1. tfr_trial_average()**
Trial-averaged TFR power by condition
```python
avg = jnwb.tfr_trial_average(session, area='V1', condition='AAXB', phase=3, band='alpha')
```

**2. tfr_compare_conditions()**
Compare TFR power between conditions (parametric + non-parametric + FDR)
```python
stats = jnwb.tfr_compare_conditions(session, area='V4', condition1='AAAB', condition2='AAXB', band='beta')
# Returns: {'parametric': {...}, 'non_parametric': {...}, 'fdr_pval_parametric': ..., 'fdr_pval_nonparametric': ...}
```

**3. tfr_correlate_areas()**
Inter-area TFR correlation with dual stats
```python
corr = jnwb.tfr_correlate_areas(session, area1='V1', area2='V4', band='alpha', condition='AAXB')
```

**4. tfr_spectrolaminar()**
Layer-wise spectral analysis
```python
layer_stats = jnwb.tfr_spectrolaminar(session, area='MT', condition='omission')
# Returns: {'superficial': {...power stats...}, 'deep': {...power stats...}, 'comparison': {...stats...}}
```

**5. tfr_permutation_test()**
Permutation test for TFR differences
```python
perm_result = jnwb.tfr_permutation_test(session, area='V1', condition1='AAAB', condition2='AAXB', n_permutations=5000)
```

### Raster & PSTH (6-8)

**6. raster_plot()**
Spike raster aligned to phase onset
```python
raster = jnwb.raster_plot(session, unit_id=42, condition='AAXB', phase=3, window_ms=(-1000, 2000))
# Returns: {'raster': [...spike times per trial...], 'n_trials': 50, 'n_spikes': 1234}
```

**7. psth_analysis()**
Peristimulus time histogram with bootstrap CI
```python
psth = jnwb.psth_analysis(session, unit_id=42, condition='AAXB', phase=3, bin_size_ms=10)
# Returns: {'psth': array, 'sem': array, 'bin_centers': array, 'bootstrap_ci': {...}}
```

**8. autocorrelogram()**
Unit autocorrelogram with refractory period test
```python
acg = jnwb.autocorrelogram(session, unit_id=42, max_lag_ms=100)
# Returns: {'acg': array, 'refractory_period_violation': 0.0003, 'is_single_unit': True}
```

### Unit Finding & Quality (9-11)

**9. find_units()**
Find units by quality/area/firing rate
```python
units = jnwb.find_units(session, quality='stable_plus', area='V1', firing_rate_range=(1, 200))
# Returns: DataFrame of matching units
```

**10. unit_quality_scores()**
Unit quality metrics (SNR, refractory violations, stability)
```python
quality = jnwb.unit_quality_scores(session, unit_id=42)
# Returns: {'refr_violations_pct': 1.2, 'is_good_single_unit': True, 'fano_factor': 1.05, ...}
```

**11. unit_channel_mapping()**
Map units to recording channels
```python
mapping = jnwb.unit_channel_mapping(session, area='V1')
# Returns: DataFrame with unit_id, channel_id, area, layer
```

### Population Analysis (12-15)

**12. pie_charts()**
Population pie charts
```python
pies = jnwb.pie_charts(session, criteria={'is_stable_plus': True}, by_area=True)
# Returns: {'counts': {...}, 'percentages': {...}, 'total': 250}
```

**13. compare_populations()**
Compare two unit populations (parametric + non-parametric + FDR)
```python
comp = jnwb.compare_populations(session, 
                                              criteria1={'is_stable_plus': True, 'area': 'V1'},
                                              criteria2={'is_stable_plus': True, 'area': 'V4'},
                                              metric='firing_rate')
# Returns: {'group1_mean': 4.2, 'group2_mean': 7.1, 'statistics': {...full dual stats + FDR...}}
```

**14. population_by_area()**
Population statistics by brain area (ANOVA + Kruskal-Wallis)
```python
by_area = jnwb.population_by_area(session, metric='waveform_duration')
# Returns: {'areas': [...], 'per_area': {...}, 'comparison': {...ANOVA, K-W, eta², FDR...}}
```

**15. network_connectivity()**
Network graph analysis from correlation matrix
```python
net = jnwb.network_connectivity(session, correlation_matrix, threshold=0.3)
# Returns: {'n_nodes': 7, 'n_edges': 12, 'density': 0.57, 'mean_degree': 3.4}
```

### Batch & Cross-Session (16-18)

**16. units_across_sessions()**
Collect matching units across multiple sessions
```python
all_units = jnwb.units_across_sessions(sessions, criteria={'quality': 'stable_plus'})
# Returns: DataFrame with session_id added
```

**17. lfp_channel_areas()**
Map LFP channels to brain areas
```python
lfp_map = jnwb.lfp_channel_areas(session, area='V1')
# Returns: DataFrame with channel_id, area, layer
```

**18. summary_report()**
Generate comprehensive session summary
```python
summary = jnwb.summary_report(session, output_dir='/tmp/')
# Returns: {'file': ..., 'n_units': 368, 'n_stable_plus': 45, 'firing_rate_mean': 5.2, ...}
```

### Advanced (19-20)

**19. noise_vs_signal()**
Signal-to-noise ratio analysis
```python
snr = jnwb.noise_vs_signal(session, unit_id=42)
# Returns: {'snr_db': 8.5, 'is_good_unit': True, ...waveform metrics...}
```

**20. cross_modal_comparison()**
Compare LFP (TFR) vs spike-based networks
```python
xmodal = jnwb.cross_modal_comparison(tfr_array, spike_array, lag_range_ms=(-500, 500))
# Returns: {'correlation': ..., 'lag_ms': ..., 'lfp_leads_spikes': True, ...stats...}
```

---

## Quick Start

### Load and Explore
```python
import jnwb as oa

# Load session
session = oa.read('sub-C31o_ses-230823_rec.nwb')

# Find units
stable_v1 = oa.find_units(session, quality='stable_plus', area='V1')

# Summary
print(session)
summary = oa.summary_report(session)
```

### TFR Analysis
```python
# Trial-average
avg = oa.tfr_trial_average(session, area='V1', condition='AAXB')

# Compare conditions
stats = oa.tfr_compare_conditions(session, area='V4', condition1='AAAB', condition2='AAXB')
# Automatic: t-test + Mann-Whitney U + Cohen's d + FDR

# Spectrolaminar
layers = oa.tfr_spectrolaminar(session, area='MT', condition='omission')
```

### Single-Unit Analysis
```python
# Raster + PSTH
raster = oa.raster_plot(session, unit_id=42, condition='AAXB')
psth = oa.psth_analysis(session, unit_id=42, condition='AAXB')

# Quality check
acg = oa.autocorrelogram(session, unit_id=42)
quality = oa.unit_quality_scores(session, unit_id=42)
```

### Population Analysis
```python
# Pie charts
pies = oa.pie_charts(session, criteria={'is_stable_plus': True}, by_area=True)

# Compare populations
comp = oa.compare_populations(session,
                              criteria1={'area': 'V1', 'is_stable_plus': True},
                              criteria2={'area': 'V4', 'is_stable_plus': True},
                              metric='firing_rate')
# Result: {'group1_mean': 4.2, 'group2_mean': 7.1, 'statistics': {...parametric, non_parametric, FDR...}}

# By area statistics
by_area = oa.population_by_area(session, metric='firing_rate')
# Result: ANOVA F-test + Kruskal-Wallis + effect sizes (eta²) per area + FDR correction
```

### Batch Analysis
```python
# Load all sessions
sessions = oa.batch_read('D:/analysis/nwb')

# Find units across all sessions
all_units = oa.units_across_sessions(sessions, criteria={'quality': 'stable_plus'})
```

---

## Statistical Methods

### Automatic Dual Testing

Every comparative analysis automatically returns:

```python
result = {
    # Parametric (assumes normality)
    'parametric': {
        'test': 'independent_t_test',  # or ANOVA, Pearson r, etc.
        'statistic': 2.34,
        'pval': 0.021,
        'effect_size': 0.45,  # Cohen's d, eta², R², etc.
    },
    # Non-parametric (distribution-free)
    'non_parametric': {
        'test': 'mann_whitney_u',  # or Kruskal-Wallis, Spearman rho, etc.
        'statistic': 1200,
        'pval': 0.018,
    },
    # FDR Correction (Benjamini-Hochberg)
    'fdr_pval_parametric': 0.042,
    'fdr_pval_nonparametric': 0.036,
    'significant_parametric': True,  # p_fdr < 0.05
    'significant_nonparametric': True,
}
```

### Per-Test Methods

| Analysis | Parametric | Non-parametric | Effect Size | FDR |
|----------|-----------|----------------|-------------|-----|
| Compare 2 groups | t-test | Mann-Whitney U | Cohen's d | ✓ |
| Compare 3+ groups | ANOVA | Kruskal-Wallis | eta² | ✓ |
| Correlate | Pearson r | Spearman rho | R² | ✓ |
| Confidence intervals | t-based | Bootstrap | CI bounds | - |
| Permutation test | - | Permutation | p-value | ✓ |

---

## File Structure

```
jnwb/
├── __init__.py          # Main API: 4 objects + 20 functions + session reader
├── session.py           # OmissionSession class
├── statistics.py        # StatisticalAnalysis object (dual testing + FDR)
├── analyzers.py         # 3 analyzer objects (TFR, Unit, Population)
├── functions.py         # 20 canonical functions
├── ARCHITECTURE.md      # This file
└── README.md            # Basic usage guide
```

---

## Design Principles

1. **Clean API** — `oa.<function>(<inputs>, <context>)`
2. **Automatic Statistics** — Every comparison includes parametric + non-parametric + FDR
3. **Effect Sizes** — Always report practical significance (Cohen's d, eta², R², etc.)
4. **Reproducibility** — All random seeds fixed (42), all methods documented
5. **Publication-Ready** — Statistics meet journal standards
6. **Extensible** — Subclass objects for custom methods
7. **Fast Shortcuts** — Common analyses in 1-2 lines

---

**Author**: Claude Code  
**Date**: 2025-06-24  
**Version**: 1.0.0  
**Status**: Complete

