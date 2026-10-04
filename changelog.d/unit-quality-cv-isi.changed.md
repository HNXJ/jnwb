- `UnitAnalyzer.quality_metrics` computes `cv_isi` by the rule of `jnwb.isi_cv`, the unbiased
  (`ddof=1`) standard deviation of the inter-spike intervals over their mean, where it used
  `ddof=0`. For `n` intervals the value is `sqrt(n / (n - 1))` times what 0.2.8 reported:
  `sqrt(2)` larger at two intervals. No other key changes.
