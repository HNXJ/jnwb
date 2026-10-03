- `jnwb.fleiss_kappa(counts)`: Fleiss' kappa over an `(n_items, n_categories)` table of rater
  counts (Fleiss 1971). A table with every rating in one category is refused, never returned as 0.
- `jnwb.spike_count_correlation(spike_times, window_s, *, bin_ms)`: mean pairwise Pearson r of
  binned spike counts (Cohen and Kohn 2011). Units whose counts do not vary are excluded and
  listed in `excluded_units`, never scored as r = 0. `bin_ms` has no default.
- `jnwb.fano_factor(spike_times, onsets_s, window_s, *, summary)`: across-trial variance
  (ddof=1) over mean of each unit's window count, summarised by `summary='mean'` or `'median'`
  (Churchland et al. 2010). Units with a zero mean count are excluded and listed.
- `jnwb.network_burst_index(spike_times, window_s, *, bin_ms, threshold_hz, min_duration_ms)`:
  the fraction of spikes inside network bursts found from the pooled population rate (Wagenaar
  et al. 2006). None of the three burst parameters has a default.
