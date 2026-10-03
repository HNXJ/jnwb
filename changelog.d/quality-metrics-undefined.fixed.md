- `UnitAnalyzer.quality_metrics` gives no single-unit verdict on undefined input. A train of
  0 or 1 spikes read `refr_violations_pct` 0.0 and `is_good_single_unit` True; the rate is now
  NaN. The Fano factor is NaN with fewer than two whole 1-s windows, where one window read 0.0.
  `is_good_single_unit` is `None` when either value is NaN; a NaN Fano factor used to pass. The
  2 ms refractory period and the 5 % and Fano-2 cut-offs are the keyword arguments
  `refractory_ms`, `max_violation_pct` and `max_fano`, with those values as defaults; they are
  conventions with no cited source.
