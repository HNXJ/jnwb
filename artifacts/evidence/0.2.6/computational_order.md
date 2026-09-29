# Computational order of the jnwb public surface

Closes todo item 06-54. **Measurement only. No code changed under this item.** Every
speedup named here is recorded and left in place; item 06-58 applies them, one packet per
gap, and is blocked on this file.

The question this answers, per export and per named input parameter: what order does the
implementation **achieve**, measured, and what order does the problem **admit**, with the
reason. An export whose two orders agree is recorded as agreeing and is not flagged.

An order with no named parameter is useless, so every row names the parameter it is in and
states what was held fixed. Several exports appear on more than one row because they have
more than one input dimension and the orders differ between them.

## 1. Coverage

| Category | Exports | Evidence |
|---|---|---|
| `jnwb.__all__` | 160 | runtime probe with a provenance assertion |
| Cost grows with input size -- measured | 106 | 189 sweeps, 189 completed |
| Cost does not grow with input size -- excluded | 50 | section 7, one reason each |
| Cost grows, input not buildable from this repository | 4 | section 8 |
| **Total** | **160** | partition checked exact against a live `jnwb.__all__` |

The three categories are disjoint and their union is `jnwb.__all__`; no export is in two,
and none is in none. `classification: observed`.

## 2. Method

### 2.1 What was run

Each sweep calls one export at four or five input sizes spanning at least a decade in the
named parameter, five timed repetitions per size after one untimed warm-up, garbage
collection disabled inside the timed region. The reported exponent is the least-squares
slope of log(median time) against log(size); `r2` is that fit's coefficient of
determination. Raw median times are printed beside every exponent, because a fitted slope
with no raw numbers under it cannot be checked.

Inputs are built by a per-spec factory outside the timed region and are deterministic
(`np.random.default_rng(0)`). Every parameter not being swept is pinned and named.

### 2.2 Provenance

A byte-identical copy of `jnwb` sits in `C:\Python314\Lib\site-packages` (problem P-09).
A probe run from the wrong directory would silently measure it, and for a timing
measurement that would be undetectable. Every probe therefore resolves the worktree root
with `git rev-parse --show-toplevel`, inserts it at `sys.path[0]`, and asserts
`root in pathlib.Path(jnwb.__file__).resolve().parents` before doing anything else.

### 2.3 Threads are pinned, and the calibration is why

The first calibration run **failed**: a workload of exactly known order `O(n^3)`
(`numpy.matmul`) recovered a fitted exponent of **1.62**. OpenBLAS was using all 24 cores,
and thread parallelism that grows with problem size suppresses the wall-clock exponent, so
an algorithm reads as a better order than it has. Setting `OMP_NUM_THREADS` and friends did
not fix it -- `threadpoolctl.threadpool_info()` still reported `num_threads: 24`. Only
`threadpoolctl.threadpool_limits(limits=1)` actually pinned it.

Every sweep in this file therefore runs single-threaded under `threadpool_limits(1)`, and
serially: two sweeps at once contend for CPU and corrupt both exponents. `n_jobs` is pinned
to 1 wherever an export accepts it (`jnwb._parallel.resolve_n_jobs` already defaults to
serial), and `device` is pinned to `cpu`.

This means the exponents below are **algorithmic**, not what a caller on 24 cores
experiences. That is the intended reading: the item asks for the computational order, and
the parallel speedup curve is a different measurement.

### 2.4 Calibration against workloads of exactly known order

The harness was run against four workloads whose order is known exactly, to establish how
much of a reported exponent is method error. `classification: observed`.

| Reference workload | True order | Sizes | Fitted exponent | Error |
|---|---|---|---|---|
| `np.add` | `O(n)`, exactly | 1e5 .. 1e7 | +1.06 | 0.06 |
| `np.sort` | `O(n log n)` | 1e4 .. 1e7 | +1.06 (power-law of `n log n` over this range: 1.081) | 0.02 |
| pure-Python double loop | `O(n^2)`, exactly | 100 .. 800 | +2.17 | 0.17 |
| pairwise distances via GEMM | `O(n^2)`, exactly | 200 .. 3200 | +2.18 | 0.18 |
| `np.matmul`, 1 thread | `O(n^3)`, exactly | 512 .. 4096 | +2.86 | 0.14 |
| `np.matmul`, 24 threads | `O(n^3)`, exactly | 256 .. 1536 | +1.85 | **1.15** |

The last row is the one that shaped the method. Pinned, the worst recovery error across
four known orders is **0.18**.

### 2.5 Noise floor and the rules that follow from it

Repeating one identical measurement twelve times gave a relative dispersion of the median
of **0.12-0.14**. An empty Python call costs 2.3-2.7 us, so any timed call below roughly
0.25 ms is dominated by call overhead. `classification: observed`.

| Rule | Value | Reason |
|---|---|---|
| Exponents are reported to | +-0.2 | worst calibrated recovery error on a known order (0.18) |
| A sweep's growth counts as separated from noise when | `t_max/t_min >= 3` | 3x is over 20x the 0.14 dispersion of a repeated identical measurement |
| Two orders count as agreeing when their exponents differ by | `<= 0.25` | the +-0.2 resolution, rounded out |
| A size ladder must span | `>= 10x` in the parameter | required by the item |

Rows below that fail the separation rule are marked `NOT SEPARATED`: for those, the
flatness is the result and the fitted exponent is not evidence of anything finer.

### 2.6 A measured exponent cannot see every gap

This is the main limitation of the method and it is not a small one. A gap of the form
`T(u*e)` against `T(u+e)` -- a nested scan where a hash join would do -- is a genuine order
gap, but a sweep that holds `u` fixed and grows `e` sees **both** forms as linear in `e`.
The gap lives in the product, and a single-parameter sweep cannot distinguish it from a
coefficient. The same is true of an avoidable `log n` factor, which is 0.06 of exponent
over a decade and sits under the calibrated resolution.

So the order gaps in section 4 are split: those a sweep can corroborate, and those the
source reading finds but this measurement cannot confirm or refute. A row in the second
group is **not** evidence against the gap.

## 3. Measured order, by module

`exp` is the fitted exponent in the named parameter, +-0.2. `times` are median seconds
rendered in milliseconds, one per size, in size order. `achieved` is that exponent put into
the nearest named band, with `n` standing for whichever parameter the row names -- not for
some other input dimension. `admissible` is the order the problem admits in the same
parameter, written with the module's own symbols. `cls` classifies the **admissible** claim;
every `exp` is `observed` by construction. `gap` is `agree` when the implemented and
admissible orders match.

A `sub-linear` reading against a linear admissible order is not a faster-than-possible
result: it means a fixed per-call cost dominates over the sizes swept. Where such a row also
contradicts a written claim it appears in section 6.

### `jnwb.addressing`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `classify_layer_from_depth` | n_electrodes | 100000, 300000, 1000000, 3000000, 10000000 | 0.84, 1.34, 2.20, 5.58, 17.7 | +0.65 | 0.961 | 21x | sub-linear | T(1) expected | derived | ORDER |
| `enrich_units_dataframe[n_electrodes]` | n_electrodes | 10000, 30000, 100000, 300000, 1000000 | 157.8, 175.0, 210.4, 288.9, 726.8 | +0.31 | 0.839 | 5x | sub-linear (POOR FIT) | T(e) additive, not multiplicative | derived | ORDER |
| `enrich_units_dataframe[n_units]` | n_units | 100, 300, 1000, 3000 | 72.0, 235.4, 749.0, 2247 | +1.01 | 0.999 | 31x | O(n) | T(u + e) | derived | ORDER |
| `map_peak_channel_to_area` | n_electrodes | 100000, 300000, 1000000, 3000000, 10000000 | 0.81, 1.03, 1.84, 4.39, 14.3 | +0.62 | 0.942 | 18x | sub-linear | T(1) expected for the single-area branch | derived | ORDER |
| `probe_geometry` | n_channels | 1000, 3000, 10000, 30000, 100000 | 1.28, 2.29, 5.37, 11.1, 58.8 | +0.80 | 0.962 | 46x | O(n) | T(n log n) | derived | agree |

### `jnwb.artifact_detection`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `bad_channels_from_correlation[n_channels]` | n_channels | 128, 512, 2048, 4096 | 2.95, 14.2, 101.7, 325.0 | +1.35 | 0.994 | 110x | O(n)-O(n^1.5) | T(n^2) | derived | CONSTANT |
| `bad_trials_single_channel[n_times]` | n_times | 5000, 25000, 100000, 200000 | 27.9, 104.0, 340.5, 654.7 | +0.85 | 0.999 | 23x | O(n) | T(T^2*n) | derived | agree |
| `bad_trials_single_channel[n_trials]` | n_trials | 128, 512, 1024, 2048 | 3.92, 20.9, 55.0, 186.8 | +1.37 | 0.992 | 48x | O(n)-O(n^1.5) | T(T^2*n) | derived | agree |
| `channel_correlation_matrix[n_channels]` | n_channels | 128, 512, 2048, 4096 | 1.10, 9.05, 148.8, 569.8 | +1.82 | 0.996 | 520x | O(n^2) | T(m^2*n) | derived | agree |
| `channel_correlation_matrix[n_samples]` | n_samples | 20000, 100000, 400000, 1000000 | 25.9, 112.2, 457.4, 1076 | +0.96 | 1.000 | 42x | O(n) | T(m^2*n) | derived | agree |
| `consensus_bad_trials[n_channels]` | n_channels | 1000, 10000, 50000, 100000 | 2.24, 22.5, 123.3, 232.3 | +1.01 | 1.000 | 104x | O(n) | T(C*T) | derived | agree |
| `consensus_bad_trials[n_trials]` | n_trials | 10000, 100000, 500000, 1000000 | 5.47, 58.4, 324.6, 748.1 | +1.06 | 0.999 | 137x | O(n) | T(C*T) | derived | agree |
| `trial_correlation_matrix[n_times]` | n_times | 20000, 100000, 400000, 1000000 | 21.1, 108.1, 416.1, 1027 | +0.99 | 1.000 | 49x | O(n) | T(m^2*n) | derived | agree |
| `trial_correlation_matrix[n_trials]` | n_trials | 128, 512, 2048, 4096 | 1.06, 8.73, 124.1, 526.3 | +1.79 | 0.996 | 496x | O(n^2) | T(m^2*n) | derived | agree |

### `jnwb.artifact_repair`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `detect_band_outliers[n_times]` | n_times | 1000, 10000, 50000, 200000 | 3.29, 41.1, 202.5, 817.1 | +1.04 | 0.999 | 248x | O(n) | T(T*n) | derived | agree |
| `detect_band_outliers[n_trials]` | n_trials | 100, 1000, 5000, 20000 | 2.77, 40.6, 231.4, 1071 | +1.12 | 1.000 | 387x | O(n) | T(T*n) | derived | agree |
| `repair_band_artifacts[n_channels]` | n_channels | 4, 16, 64, 128 | 3.03, 10.5, 33.4, 69.7 | +0.89 | 0.999 | 23x | O(n) | T(T*C*F*n) | derived | agree |
| `repair_band_artifacts[n_freqs]` | n_freqs | 50, 200, 800, 2000 | 2.75, 5.12, 19.0, 48.7 | +0.79 | 0.972 | 18x | sub-linear | T(T*C*F*n) | derived | agree |
| `repair_band_artifacts[n_times]` | n_times | 50, 200, 800, 2000 | 3.92, 9.25, 38.3, 80.8 | +0.84 | 0.990 | 21x | O(n) | T(T*C*F*n) | derived | CONSTANT |
| `repair_band_artifacts[n_trials]` | n_trials | 20, 100, 400, 1000 | 3.21, 11.6, 48.7, 114.1 | +0.92 | 0.997 | 36x | O(n) | T(T*C*F*n) | derived | agree |
| `repair_lfp_trials[n_channels]` | n_channels | 8, 64, 256, 1024 | 14.1, 95.1, 361.8, 1544 | +0.96 | 0.999 | 109x | O(n) | T(T*C*n) | derived | agree |
| `repair_lfp_trials[n_times]` | n_times | 500, 5000, 15000, 30000 | 25.0, 229.6, 696.3, 1382 | +0.98 | 1.000 | 55x | O(n) | T(T*C*n) | derived | agree |
| `repair_lfp_trials[n_trials]` | n_trials | 40, 200, 800, 2000 | 27.2, 127.8, 488.3, 1403 | +1.00 | 0.999 | 52x | O(n) | T(T*C*n) | derived | agree |

### `jnwb.compression`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `compress_fp32` | n_bytes | 444912, 1322352, 5709552, 22161552, 87969552 | 130.5, 161.9, 230.4, 802.1, 2601 | +0.57 | 0.918 | 20x | sub-linear | T(n_bytes) with one pass | derived | CONSTANT |

### `jnwb.connectivity`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `as_trials[n_samples]` | n_samples | 1000000, 3000000, 8000000, 20000000, 40000000 | 8.02, 24.7, 59.6, 148.7, 285.3 | +0.96 | 1.000 | 36x | O(n) | T(N) | derived | agree |
| `bin_spikes[n_bins]` | n_bins | 500000, 1500000, 4000000, 10000000, 20000000 | 15.9, 49.5, 141.1, 332.7, 674.8 | +1.01 | 1.000 | 42x | O(n) | T(n_spikes + n_bins) | derived | ORDER |
| `bin_spikes[n_spikes]` | n_spikes | 400000, 1500000, 5000000, 12000000, 20000000 | 8.05, 30.3, 99.3, 239.7, 392.9 | +0.99 | 1.000 | 49x | O(n) | T(n_spikes + n_bins) | derived | ORDER |
| `binary_occupancy_mutual_information[n_spikes]` | n_spikes | 100000, 500000, 2000000, 5000000, 10000000 | 9.36, 50.6, 205.4, 529.1, 1092 | +1.03 | 1.000 | 117x | O(n) | T(n_spikes + n_bins) | derived | ORDER |
| `directed_connectivity[n_samples]` | n_samples | 10000, 40000, 120000, 300000, 600000 | 11.0, 51.7, 174.2, 516.6, 1145 | +1.13 | 1.000 | 104x | O(n) | the dispatched estimator's | derived | agree |
| `directed_network[n_samples]` | n_samples | 1000, 4000, 16000, 64000, 128000 | 21.4, 33.0, 72.2, 298.2, 663.6 | +0.71 | 0.948 | 31x | sub-linear | T(n^2*N) | derived | agree |
| `directed_network[n_signals]` | n_signals | 4, 8, 16, 28, 40 | 19.0, 87.6, 346.2, 1040, 2240 | +2.05 | 1.000 | 118x | O(n^2) | Omega(n^2) irreducible; about T(n^2*N log N + n^2*p^2) | derived | agree |
| `granger[model_order]` | model_order | 2, 6, 18, 40, 70 | 13.9, 28.4, 84.7, 269.1, 619.5 | +1.07 | 0.974 | 45x | O(n) | T(N*p + p^2) at d=2 | derived | ORDER |
| `granger[n_samples]` | n_samples | 10000, 40000, 120000, 300000, 600000 | 11.8, 51.7, 168.6, 469.1, 985.3 | +1.08 | 1.000 | 84x | O(n) | T(N*d^2*p) | derived | agree |
| `granger_causality[model_order]` | model_order | 2, 6, 18, 40, 70 | 11.9, 27.3, 81.4, 281.1, 591.6 | +1.11 | 0.981 | 50x | O(n) | T(N*p + p^2) | derived | ORDER |
| `granger_causality[n_samples]` | n_samples | 10000, 40000, 120000, 300000, 600000 | 11.0, 48.8, 164.6, 470.2, 1010 | +1.11 | 1.000 | 92x | O(n) | T(N*d^2*p) | derived | agree |
| `granger_spectral[model_order]` | model_order | 4, 12, 40, 80, 160 | 8.33, 31.1, 133.5, 291.6, 680.4 | +1.19 | 1.000 | 82x | O(n) | T(N*p + p^2 + F log F) | derived | ORDER |
| `granger_spectral[n_freqs]` | n_freqs | 128, 512, 2048, 8192, 16384 | 10.8, 40.8, 128.8, 527.8, 1023 | +0.93 | 0.999 | 95x | O(n) | T(d^2*F log F + d^3*F) | derived | ORDER |
| `granger_spectral[n_samples]` | n_samples | 8000, 30000, 120000, 400000, 1000000 | 5.95, 14.3, 52.9, 203.2, 556.6 | +0.95 | 0.991 | 94x | O(n) | T(N*d^2*p) | derived | agree |
| `network_topology[n_nodes]` | n_nodes | 800, 1600, 3000, 5000, 8000 | 8.45, 33.2, 115.7, 320.2, 814.8 | +1.98 | 1.000 | 96x | O(n^2) | T(n^2) | derived | agree |
| `phase_slope_index[n_samples]` | n_samples | 60000, 200000, 700000, 2000000, 4000000 | 8.69, 39.9, 123.6, 334.0, 692.1 | +1.02 | 0.996 | 80x | O(n) | T(N log L) | derived | agree |
| `phase_slope_index[n_samples_jackknife]` | n_samples | 60000, 200000, 700000, 2000000, 4000000 | 13.06, 59.15, 197.2, 555.3, 1151 | +1.05 | 0.997 | 88x | O(n) | T(S*L) | derived | agree |
| `spike_count_mutual_information[n_spikes]` | n_spikes | 100000, 500000, 2000000, 5000000, 10000000 | 11.0, 55.3, 228.2, 562.6, 1138 | +1.01 | 1.000 | 104x | O(n) | T(n_spikes + n_bins) | derived | ORDER |
| `spike_mutual_information[n_bins]` | n_bins | 10000, 50000, 200000, 800000, 2000000 | 23.1, 31.5, 78.3, 289.1, 800.8 | +0.68 | 0.933 | 35x | sub-linear | T(n_spikes + n_bins) | derived | ORDER |
| `spike_mutual_information[n_spikes]` | n_spikes | 100000, 500000, 2000000, 5000000, 10000000 | 9.72, 49.9, 208.7, 534.8, 1066 | +1.02 | 1.000 | 110x | O(n) | T(n_spikes + n_bins) | derived | ORDER |
| `transfer_entropy[n_samples]` | n_samples | 1500, 6000, 25000, 80000, 150000 | 13.0, 51.4, 278.1, 1079, 2184 | +1.13 | 0.999 | 169x | O(n) | T(N*(k+l)) expected | derived | ORDER |
| `transfer_entropy[source_history_l]` | source_history_l | 1, 8, 50, 200, 500 | 106.1, 171.8, 411.8, 638.5, 1190 | +0.39 | 0.976 | 11x | sub-linear | T(N*(k+l)) | derived | agree |
| `transfer_entropy[target_history_k]` | target_history_k | 1, 8, 50, 200, 500 | 98.6, 166.9, 389.8, 651.1, 1213 | +0.40 | 0.979 | 12x | sub-linear | T(N*(k+l)) | derived | agree |

`phase_slope_index[n_samples_jackknife]` was re-measured at `19a8496d` after the change in section 6.2, on a ladder 80x wider because the reduced path no longer reaches the timing band over 5000 to 50000. At `f23d96ce` it read +2.14 over that narrower ladder, T(S^2*L).

### `jnwb.continuous`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `epoch_continuous[n_events]` | n_events | 2000, 6000, 20000, 60000 | 8.41, 22.2, 70.8, 213.2 | +0.95 | 0.999 | 25x | O(n) | T(E*W*C) | derived | CONSTANT |
| `epoch_continuous[n_window_samples]` | n_window_samples | 3000, 10000, 30000, 100000 | 4.79, 10.1, 26.0, 84.2 | +0.82 | 0.990 | 18x | O(n) | T(E*W) | derived | agree |

### `jnwb.decoding`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `assign_outer_folds[n_strata]` | n_strata | 10, 50, 250, 1000 | 38.2, 114.7, 491.0, 1962 | +0.86 | 0.993 | 51x | O(n) | T(1) in S with n fixed | derived | ORDER |
| `assign_outer_folds[n_trials]` | n_trials | 2000, 10000, 50000, 200000 | 6.16, 9.27, 36.4, 132.8 | +0.68 | 0.947 | 22x | sub-linear | T(n) | derived | agree |
| `build_inner_validation_partitions[n_groups]` | n_groups | 3, 6, 12, 30 | 18.9, 105.6, 470.7, 3110 | +2.21 | 0.998 | 165x | O(n^2) | T(G^2) for the declared output | derived | agree |
| `build_inner_validation_partitions[n_trials]` | n_trials | 200, 800, 2400, 6000 | 122.1, 442.9, 1308, 3369 | +0.97 | 0.999 | 28x | O(n) | T(n) | derived | CONSTANT |
| `build_representation_ladder[n_time]` | n_time | 32, 128, 512, 2048 | 5.38, 20.6, 89.1, 400.2 | +1.04 | 0.999 | 74x | O(n) | T(T*S*B) | derived | agree |
| `build_representation_ladder[n_trials]` | n_trials | 500, 2000, 10000, 40000 | 2.66, 10.6, 54.3, 207.1 | +1.00 | 1.000 | 78x | O(n) | T(T*S*B) | derived | agree |
| `fold_majority_baseline[n_labels]` | n_labels | 500000, 2000000, 8000000, 32000000 | 3.24, 13.1, 53.3, 208.3 | +1.00 | 1.000 | 64x | O(n) | T(n) expected by hashing | derived | CONSTANT |
| `majority_baseline[n_labels]` | n_labels | 500000, 2000000, 8000000, 32000000 | 3.01, 13.3, 51.3, 227.8 | +1.03 | 1.000 | 76x | O(n) | T(n) expected by hashing | derived | CONSTANT |
| `nested_cv_linear_svm[n_features]` | n_features | 50, 250, 1250, 5000 | 229.7, 287.9, 564.2, 2104 | +0.47 | 0.878 | 9x | sub-linear (POOR FIT) | T(n*d) | derived | CONSTANT |
| `nested_cv_linear_svm[n_folds]` | n_folds | 2, 5, 12, 30 | 127.9, 330.3, 769.1, 1988 | +1.01 | 1.000 | 16x | O(n) | T(k); exact sublinear-in-k SVM CV unknown | unknown | agree |
| `nested_cv_linear_svm[n_trials]` | n_trials | 40, 200, 800, 3000 | 200.1, 212.2, 407.0, 2277 | +0.54 | 0.783 | 11x | sub-linear (POOR FIT) | T(n*d) | derived | ORDER |

### `jnwb.filtering`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `bandpass_filter[n_channels]` | n_channels | 32, 128, 512, 2048 | 16.4, 59.0, 228.2, 904.9 | +0.96 | 1.000 | 55x | O(n) | T(C) | derived | agree |
| `bandpass_filter[n_samples]` | n_samples | 300000, 1000000, 3000000, 10000000 | 8.35, 22.9, 67.8, 214.9 | +0.93 | 0.999 | 26x | O(n) | T(n) | derived | agree |
| `bandpass_filter[order]` | order | 4, 12, 30, 80 | 12.4, 30.7, 73.3, 198.3 | +0.93 | 0.998 | 16x | O(n) | T(1) in p, at O(n log n) in n | derived | ORDER |
| `notch_filter[n_channels]` | n_channels | 32, 128, 512, 2048 | 13.7, 52.3, 199.8, 788.4 | +0.97 | 1.000 | 57x | O(n) | T(C) | derived | agree |
| `notch_filter[n_samples]` | n_samples | 300000, 1000000, 3000000, 10000000 | 6.74, 19.5, 55.4, 184.2 | +0.94 | 0.999 | 27x | O(n) | T(n) | derived | agree |

### `jnwb.io`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `stream_npz_array[n_elements_in_file]` | n_elements_in_file | 100000, 1000000, 4000000, 16000000 | 0.4878, 0.5071, 0.5166, 0.5172 | +0.01 | 0.919 | 1x | O(1) (NOT SEPARATED) | T(k) for ZIP_STORED | observed | agree |
| `stream_npz_array[n_elements_sliced]` | n_elements_sliced | 1000, 10000, 100000, 1000000, 4000000 | 0.87, 0.85, 1.37, 13.9, 45.9 | +0.49 | 0.830 | 53x | sub-linear (POOR FIT) | T(k) | derived | agree |

`stream_npz_array[n_elements_in_file]` was re-measured at `19a8496d` after the change in section 6.2. At `f23d96ce` it read +0.83, T(n): the leading elements were read and discarded.

### `jnwb.jrsa`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `jrsa[n_bootstrap]` | n_bootstrap | 100, 300, 900, 1800 | 151.3, 454.4, 1371, 2783 | +1.01 | 1.000 | 18x | O(n) | T(B) | derived | CONSTANT |
| `jrsa[n_conditions]` | n_conditions | 20, 60, 200, 600 | 24.5, 36.6, 175.3, 2029 | +1.30 | 0.913 | 83x | O(n)-O(n^1.5) | T(C^2 log C) with f and P fixed | derived | agree |
| `jrsa[n_features]` | n_features | 64, 256, 1024, 4096 | 66.9, 92.5, 229.8, 725.2 | +0.58 | 0.948 | 11x | sub-linear | T(C^2*f + P*C^2 log C) | derived | ORDER |
| `jrsa[n_lags]` | n_lags | 2, 6, 20, 60, 200 | 16.3, 48.1, 157.3, 470.9, 1563 | +0.99 | 1.000 | 96x | O(n) | T(1) in L; T(n log n) total for all lags | derived | ORDER |
| `jrsa[n_permutations]` | n_permutations | 100, 300, 900, 1800 | 132.9, 431.9, 1284, 2633 | +1.03 | 1.000 | 20x | O(n) | T(P) | derived | CONSTANT |
| `jrsa[n_samples]` | n_samples | 1000, 5000, 25000, 100000 | 96.5, 163.2, 580.1, 2626 | +0.72 | 0.949 | 27x | sub-linear | T(n) | derived | ORDER |

### `jnwb.laminar`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `label_layers[n_channels]` | n_channels | 2000, 20000, 100000, 200000 | 8.31, 103.1, 444.7, 940.6 | +1.02 | 0.998 | 113x | O(n) | T(C) | derived | CONSTANT |
| `vflip[n_channels]` | n_channels | 64, 512, 4096, 16384 | 0.65, 6.45, 60.6, 243.4 | +1.07 | 1.000 | 377x | O(n) | T(C*F) | derived | agree |
| `vflip[n_freqs]` | n_freqs | 64, 512, 4096, 16384 | 0.40, 0.53, 2.98, 11.3 | +0.62 | 0.911 | 28x | sub-linear | T(C*F) | derived | agree |
| `vflip_from_lfp[n_channels]` | n_channels | 16, 128, 512, 1024 | 16.0, 158.4, 608.4, 1237 | +1.04 | 0.999 | 77x | O(n) | T(C) | derived | agree |
| `vflip_from_lfp[n_samples]` | n_samples | 20000, 100000, 500000, 1500000 | 16.9, 78.4, 471.9, 1457 | +1.04 | 0.999 | 86x | O(n) | T(n log L) | derived | agree |
| `xflip[n_channels]` | n_channels | 32, 128, 512, 1024 | 2.70, 17.0, 283.7, 1206 | +1.78 | 0.989 | 446x | O(n^2) | T(C^2*n + K*C^2) | derived | agree |
| `xflip[n_samples]` | n_samples | 20000, 100000, 400000, 1000000 | 21.9, 75.7, 290.2, 668.9 | +0.88 | 0.997 | 31x | O(n) | T(n) | derived | agree |
| `xflip[n_surrogates]` | n_surrogates | 8, 32, 128, 256 | 19.3, 76.6, 252.8, 529.3 | +0.94 | 0.999 | 27x | O(n) | T(S) | derived | agree |
| `zflip[n_channels]` | n_channels | 8, 64, 256, 1024 | 7.13, 61.1, 258.4, 1064 | +1.03 | 1.000 | 149x | O(n) | T(C*n log L) | derived | agree |
| `zflip[n_samples]` | n_samples | 8192, 50000, 200000, 500000 | 7.36, 22.8, 96.1, 252.3 | +0.86 | 0.983 | 34x | O(n) | T(n log L) | derived | agree |
| `zflip[n_surrogates]` | n_surrogates | 4, 16, 64, 128 | 29.9, 90.1, 347.6, 708.3 | +0.92 | 0.997 | 24x | O(n) | T(S) | derived | agree |

### `jnwb.metadata`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `assign_quality_tier` | n_units | 10000, 30000, 100000, 300000, 1000000 | 3.40, 4.23, 7.51, 18.7, 51.9 | +0.60 | 0.949 | 15x | sub-linear | T(m) | derived | agree |
| `audit_electrodes[n_electrodes]` | n_electrodes | 3000, 10000, 30000, 100000, 300000 | 3.83, 9.69, 27.1, 93.8, 258.7 | +0.93 | 0.998 | 67x | O(n) | T(e) | derived | CONSTANT |
| `audit_electrodes[n_units]` | n_units | 100000, 300000, 1000000, 3000000, 10000000 | 1.66, 2.12, 3.51, 9.11, 35.8 | +0.66 | 0.921 | 22x | sub-linear | T(u) | derived | agree |
| `audit_units` | n_units | 1000, 3000, 10000, 30000, 100000 | 2.60, 3.58, 6.27, 11.3, 30.8 | +0.53 | 0.965 | 12x | sub-linear | T(m) | derived | CONSTANT |
| `classify_unit_quality` | n_units | 200, 600, 2000, 6000, 20000 | 7.21, 11.5, 20.9, 52.0, 190.1 | +0.70 | 0.961 | 26x | sub-linear | T(m*k), k = 3 thresholds fixed | derived | CONSTANT |
| `electrode_inventory` | n_files | 1, 2, 5, 10, 15 | 157.5, 318.7, 785.9, 1532, 2346 | +0.99 | 1.000 | 15x | O(n) | T(F) | derived | CONSTANT |
| `electrode_inventory[n_channels_per_file]` | n_channels | 10, 30, 100, 300 | 167.1, 147.1, 175.2, 194.6 | +0.06 | 0.505 | 1x | O(1) (NOT SEPARATED, POOR FIT) | T(e) per file | derived | agree |
| `filter_by_criteria[n_criteria]` | n_criteria | 2, 5, 10, 25, 50 | 3.45, 5.36, 6.50, 13.7, 25.9 | +0.62 | 0.962 | 8x | sub-linear | T(c) | derived | CONSTANT |
| `filter_by_criteria[n_rows]` | n_rows | 10000, 30000, 100000, 300000, 1000000 | 3.95, 9.17, 24.7, 68.0, 219.4 | +0.87 | 0.998 | 56x | O(n) | T(c*m + m*C) | derived | CONSTANT |
| `get_all_units_metadata` | n_files | 1, 2, 5, 10, 15 | 161.0, 318.9, 807.9, 1543, 2390 | +0.99 | 1.000 | 15x | O(n) | T(F) | derived | CONSTANT |
| `get_all_units_metadata[n_channels_per_file]` | n_channels | 10, 30, 100, 300 | 166.2, 164.1, 199.2, 191.3 | +0.05 | 0.674 | 1x | O(1) (NOT SEPARATED, POOR FIT) | T(u + e) per file | derived | ORDER |
| `get_snr_analysis[n_sessions]` | n_sessions | 2, 5, 20, 50, 100 | 7.19, 12.5, 30.8, 55.7, 101.9 | +0.67 | 0.997 | 14x | sub-linear | T(m + S) | derived | ORDER |
| `get_snr_analysis[n_units]` | n_units | 10000, 30000, 100000, 300000, 1000000 | 1.46, 2.61, 5.59, 16.1, 64.1 | +0.82 | 0.974 | 44x | O(n) | T(m) | derived | agree |
| `unit_census_report[n_groups]` | n_groups | 50, 500, 5000, 20000, 50000 | 15.4, 15.2, 14.9, 17.1, 19.0 | +0.03 | 0.515 | 1x | O(1) (NOT SEPARATED, POOR FIT) | T(g) | derived | agree |
| `unit_census_report[n_units]` | n_units | 1000, 3000, 10000, 30000, 100000 | 9.86, 8.43, 11.2, 17.1, 40.7 | +0.31 | 0.792 | 4x | sub-linear (POOR FIT) | T(m + g) | derived | agree |

### `jnwb.nwb_events`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `event_onsets` | n_events | 50, 500, 5000, 20000 | 89.2, 132.0, 411.1, 1350 | +0.45 | 0.918 | 15x | sub-linear | T(n) on one column | derived | CONSTANT |
| `events` | n_events | 50, 500, 5000, 20000 | 104.0, 120.6, 407.4, 1314 | +0.42 | 0.875 | 13x | sub-linear (POOR FIT) | T(n) on the 2-3 needed columns, vectorized | derived | CONSTANT |
| `resolve_interval_table` | n_events | 50, 500, 5000, 20000 | 97.7, 82.9, 81.1, 99.5 | -0.00 | 0.005 | 1x | O(1) (NOT SEPARATED, POOR FIT) | O(1) in rows; T(t log t) in the number of tables t | observed | agree |

### `jnwb.nwb_inspect`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `acquisition_channel` | n_samples_in_file | 228500, 914000, 3656000, 14624000, 58496000 | 103.9, 121.7, 196.1, 494.3, 1630 | +0.50 | 0.913 | 16x | sub-linear | T(n) | derived | agree |
| `inspect` | n_samples_in_file | 9140, 228500, 3656000, 58496000 | 103.5, 108.4, 99.1, 109.8 | +0.00 | 0.059 | 1x | O(1) (NOT SEPARATED, POOR FIT) | O(1) in n_samples; T(#HDF5 objects + #columns) overall | observed | agree |
| `resolve_acquisition` | n_samples_in_file | 9140, 228500, 3656000, 58496000 | 79.4, 93.0, 91.9, 91.7 | +0.01 | 0.557 | 1x | O(1) (NOT SEPARATED, POOR FIT) | O(1) in n_samples; T(a log a) in the number of series a | observed | agree |
| `unit_spike_times` | n_spikes_per_unit | 50, 500, 5000, 20000 | 98.8, 93.4, 93.7, 99.8 | +0.00 | 0.000 | 1x | O(1) (NOT SEPARATED, POOR FIT) | T(k) | derived | agree |

### `jnwb.onset_fitting`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `causal_exp_smooth[n_samples]` | n_samples | 100000, 500000, 2000000, 8000000 | 5.35, 29.4, 110.9, 450.5 | +1.01 | 1.000 | 84x | O(n) | T(n) | derived | agree |
| `causal_exp_smooth[tau_ms]` | tau_ms | 5, 20, 100, 500, 2000 | 6.95, 8.90, 19.1, 125.4, 455.8 | +0.73 | 0.933 | 66x | sub-linear | T(n), independent of tau | derived | ORDER |
| `fit_exponential_onset[n_grid_points]` | n_grid_points | 5, 15, 50, 150, 250 | 61.3, 163.4, 479.0, 1466, 2432 | +0.94 | 0.999 | 40x | O(n) | T(G); any sublinear alternative unknown | unknown | agree |
| `fit_exponential_onset[n_samples]` | n_samples | 200, 1500, 12000, 100000 | 79.9, 91.9, 207.9, 1644 | +0.48 | 0.846 | 21x | sub-linear (POOR FIT) | T(n) per iteration | derived | agree |
| `onset_model[n_samples]` | n_samples | 200000, 1000000, 5000000, 20000000 | 6.69, 28.9, 156.5, 604.1 | +0.99 | 0.999 | 90x | O(n) | T(n) | derived | agree |

### `jnwb.permutation`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `build_permutation_plan[n_permutations]` | n_permutations | 200, 600, 1500, 4000 | 35.3, 104.6, 264.0, 692.4 | +0.99 | 1.000 | 20x | O(n) | T(B*n) | derived | ORDER |
| `build_permutation_plan[n_samples]` | n_samples | 500, 2000, 8000, 20000 | 42.2, 75.4, 201.4, 439.5 | +0.64 | 0.979 | 10x | sub-linear | T(B*n) | derived | ORDER |
| `permute_labels[n_samples;global]` | n_samples | 200000, 1000000, 4000000, 10000000 | 5.59, 35.3, 222.7, 673.3 | +1.23 | 0.999 | 120x | O(n) | T(n) | derived | agree |
| `permute_labels[n_samples;within_group]` | n_samples | 20000, 100000, 500000, 2000000 | 1.84, 8.79, 53.3, 268.5 | +1.08 | 0.998 | 146x | O(n) | T(n) | derived | ORDER |

### `jnwb.rsa`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `rdm[n_conditions]` | n_conditions | 300, 900, 2500, 6000 | 2.58, 17.6, 124.0, 737.7 | +1.89 | 0.999 | 286x | O(n^2) | T(C^2*f) | derived | CONSTANT |
| `rdm[n_features]` | n_features | 1000, 5000, 25000, 100000 | 3.36, 17.9, 129.1, 639.0 | +1.15 | 0.999 | 190x | O(n) | T(C^2*f) | derived | CONSTANT |
| `rdm_similarity[n_conditions]` | n_conditions | 100, 300, 1000, 2500 | 2.57, 16.9, 265.7, 2119 | +2.11 | 0.996 | 825x | O(n^2) | T(m log m) = T(C^2 log C) | derived | agree |

### `jnwb.spectral`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `aggregate_to_db` | n_units | 400000, 1000000, 3000000, 8000000 | 21.7, 52.9, 165.5, 436.1 | +1.01 | 1.000 | 20x | O(n) | T(U*T) | derived | agree |
| `aperiodic_fit[n_freqs]` | n_freqs | 100000, 300000, 1000000, 2000000 | 9.77, 30.4, 106.9, 217.6 | +1.04 | 1.000 | 22x | O(n) | T(F) | derived | agree |
| `aperiodic_fit[n_spectra]` | n_spectra | 500, 1500, 5000, 10000 | 36.8, 110.8, 367.6, 733.5 | +1.00 | 1.000 | 20x | O(n) | T(n_spectra*F) | derived | CONSTANT |
| `band_power` | n_samples | 300000, 1000000, 3000000, 10000000 | 18.4, 67.3, 212.0, 750.0 | +1.06 | 1.000 | 41x | O(n) | T(n) | derived | agree |
| `bipolar_reference[n_channels]` | n_channels | 128, 512, 1024, 2048 | 12.6, 52.1, 97.8, 199.4 | +0.99 | 1.000 | 16x | O(n) | T(C*n) | derived | CONSTANT |
| `bipolar_reference[n_samples]` | n_samples | 150000, 500000, 1500000, 2500000 | 25.0, 83.1, 251.0, 445.3 | +1.02 | 1.000 | 18x | O(n) | T(C*n) | derived | agree |
| `compute_multitaper_psd[k_tapers]` | k_tapers | 6, 20, 40, 80 | 8.84, 27.3, 57.2, 127.5 | +1.03 | 0.997 | 14x | O(n) | unknown | unknown | agree |
| `compute_multitaper_psd[n_samples]` | n_samples | 16384, 49152, 131072, 262144 | 26.3, 75.3, 206.2, 409.9 | +0.99 | 1.000 | 16x | O(n) | O(K*n log n) best known; lower bound unknown | unknown | agree |
| `compute_multitaper_psd[n_signals]` | n_signals | 128, 384, 1024, 2048 | 51.7, 140.3, 366.2, 729.5 | +0.96 | 1.000 | 14x | O(n) | T(M) | derived | agree |
| `compute_psd[n_channels]` | n_channels | 32, 128, 512, 1024 | 26.7, 134.3, 565.1, 1157 | +1.08 | 0.999 | 43x | O(n) | T(C) | derived | agree |
| `compute_psd[n_samples]` | n_samples | 300000, 1000000, 3000000, 10000000 | 34.2, 109.7, 328.7, 1082 | +0.99 | 1.000 | 32x | O(n) | T(n) | derived | agree |
| `cross_area_coherence[n_bands]` | n_bands | 500, 2000, 8000, 20000 | 28.4, 78.8, 277.7, 676.7 | +0.86 | 0.996 | 24x | O(n) | T(F log F + B log F + sum_bins) | derived | ORDER |
| `cross_area_coherence[n_samples]` | n_samples | 26214, 65536, 131072, 262144 | 50.2, 131.9, 269.7, 568.8 | +1.05 | 1.000 | 11x | O(n) | T((1+S)*n) | derived | agree |
| `cross_area_coherence[n_surrogates]` | n_surrogates | 20, 60, 200, 400 | 80.7, 233.6, 767.4, 1531 | +0.98 | 1.000 | 19x | O(n) | T(S) | derived | agree |
| `current_source_density_1d[n_channels]` | n_channels | 128, 512, 1024, 2048 | 35.9, 145.0, 281.0, 588.1 | +1.00 | 1.000 | 16x | O(n) | T(C*n) | derived | agree |
| `current_source_density_1d[n_samples]` | n_samples | 150000, 500000, 1500000, 2500000 | 64.8, 217.4, 635.8, 1088 | +1.00 | 1.000 | 17x | O(n) | T(C*n) | derived | agree |
| `harmonic_analysis` | n_samples | 300000, 1000000, 3000000, 10000000 | 19.2, 69.5, 215.1, 757.0 | +1.05 | 1.000 | 39x | O(n) | T(n) | derived | agree |
| `imaginary_coherency` | n_samples | 100000, 300000, 1000000, 3000000 | 40.6, 130.3, 435.3, 1294 | +1.02 | 1.000 | 32x | O(n) | T(n) | derived | CONSTANT |
| `laplacian_reference[n_channels]` | n_channels | 128, 512, 1024, 2048 | 22.2, 85.0, 170.2, 345.3 | +0.99 | 1.000 | 16x | O(n) | T(C*n) | derived | CONSTANT |
| `laplacian_reference[n_samples]` | n_samples | 150000, 500000, 1500000, 2500000 | 76.8, 259.0, 773.1, 1292 | +1.00 | 1.000 | 17x | O(n) | T(C*n) | derived | agree |
| `relative_power` | n_units | 400000, 1000000, 3000000, 8000000 | 32.2, 78.6, 239.2, 662.7 | +1.01 | 1.000 | 21x | O(n) | T(U*T) | derived | CONSTANT |
| `spectral_tilt` | n_samples | 300000, 1000000, 3000000, 10000000 | 20.7, 70.3, 214.7, 754.6 | +1.02 | 1.000 | 36x | O(n) | T(n) | derived | agree |
| `to_db` | n_elements | 2000000, 6000000, 20000000, 40000000 | 20.9, 61.9, 210.7, 419.1 | +1.00 | 1.000 | 20x | O(n) | T(n) | derived | agree |
| `voltage_curvature_1d[n_channels]` | n_channels | 128, 512, 1024, 2048 | 34.9, 132.7, 268.9, 546.7 | +0.99 | 1.000 | 16x | O(n) | T(C*n) | derived | agree |
| `voltage_curvature_1d[n_samples]` | n_samples | 150000, 500000, 1500000, 2500000 | 66.0, 193.8, 590.5, 998.8 | +0.97 | 0.999 | 15x | O(n) | T(C*n) | derived | agree |
| `wpli` | n_samples | 300000, 1000000, 3000000, 10000000 | 32.8, 97.7, 279.2, 950.4 | +0.96 | 0.999 | 29x | O(n) | T(n) | derived | agree |

### `jnwb.spiking`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `compute_response_metrics[n_spikes]` | n_spikes | 20000, 100000, 500000, 2000000, 8000000 | 3.39, 4.64, 14.4, 50.8, 222.9 | +0.71 | 0.946 | 66x | sub-linear | T(S log S) comparison / T(S) radix | derived | CONSTANT |
| `compute_response_metrics[n_trials]` | n_trials | 2000, 6000, 20000, 60000 | 27.8, 84.6, 236.2, 747.6 | +0.95 | 0.999 | 27x | O(n) | T(T) | derived | CONSTANT |
| `gaussian_smooth_rate[n_samples]` | n_samples | 100000, 500000, 2000000, 8000000 | 9.38, 46.7, 183.2, 782.3 | +1.01 | 1.000 | 83x | O(n) | T(n) | derived | agree |
| `gaussian_smooth_rate[sigma_ms]` | sigma_ms | 2, 10, 50, 200, 800 | 4.04, 13.2, 43.3, 180.2, 665.7 | +0.85 | 0.994 | 165x | O(n) | T(n), independent of sigma | derived | ORDER |
| `pairwise_phase_consistency[n_samples]` | n_samples | 200000, 1000000, 5000000, 20000000 | 7.17, 31.0, 172.4, 646.9 | +0.99 | 0.999 | 90x | O(n) | T(n) | derived | agree |
| `phase_locking_index[n_lfp_samples]` | n_lfp_samples | 100000, 1000000, 5000000, 20000000 | 5.99, 48.7, 188.4, 660.5 | +0.88 | 1.000 | 110x | O(n) | T(1) in m with a uniform grid; T(log m) per spike by binary search | derived | ORDER |
| `phase_locking_index[n_spikes]` | n_spikes | 50000, 200000, 1000000, 5000000 | 11.7, 28.1, 89.0, 492.1 | +0.80 | 0.985 | 42x | O(n) | T(S) | derived | ORDER |

### `jnwb.statistics`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `assign_subblock_quartiles` | n_rows | 100000, 400000, 1500000, 5000000 | 3.65, 20.5, 126.5, 751.6 | +1.36 | 0.999 | 206x | O(n)-O(n^1.5) | T(n) | derived | ORDER |
| `cluster_permutation_test[n_permutations]` | n_permutations | 200, 600, 1500, 4000 | 61.2, 180.3, 462.0, 1203 | +1.00 | 1.000 | 20x | O(n) | T(B*n*P) upper bound; lower bound unknown | unknown | CONSTANT |
| `cluster_permutation_test[n_points]` | n_points | 200, 600, 2000, 6000 | 60.3, 99.6, 229.9, 670.9 | +0.71 | 0.976 | 11x | sub-linear | T(B*n*P + B*P*alpha) upper bound; lower bound unknown | unknown | agree |
| `cluster_permutation_test[n_samples]` | n_samples | 100, 300, 1000, 3000 | 67.8, 94.8, 399.4, 1099 | +0.86 | 0.959 | 16x | O(n) | T(B*n*P) upper bound; lower bound unknown | unknown | CONSTANT |
| `cross_modal_comparison[n_permutations]` | n_permutations | 100, 200, 500, 1000 | 146.7, 242.9, 522.3, 1035 | +0.85 | 0.996 | 7x | O(n) | O(n log n) per permutation | derived | ORDER |
| `cross_modal_comparison[n_samples]` | n_samples | 3000, 10000, 25000, 50000 | 173.2, 278.1, 551.9, 1231 | +0.68 | 0.946 | 7x | sub-linear | O(n log n) per permutation | derived | ORDER |
| `detect_trial_cycles` | n_rows | 100000, 400000, 1500000, 5000000 | 5.34, 27.4, 160.1, 910.0 | +1.31 | 0.998 | 170x | O(n)-O(n^1.5) | T(n log n) | derived | ORDER |
| `exact_sign_flip[n_mc]` | n_mc | 20000, 60000, 200000, 600000 | 9.98, 30.4, 97.8, 331.9 | +1.02 | 0.999 | 33x | O(n) | T(B*n) | derived | CONSTANT |
| `exact_sign_flip[n_samples_exact]` | n_samples | 2, 5, 10, 15, 20 | 0.17, 0.16, 0.24, 4.05, 149.1 | +2.47 | 0.596 | 870x | O(n^2)-O(n^3) (POOR FIT) | O(2^(N/2)*N) known; true lower bound unknown | unknown | ORDER |
| `exact_sign_flip[n_samples_mc]` | n_samples | 25, 75, 250, 750 | 5.05, 14.4, 49.1, 155.6 | +1.01 | 1.000 | 31x | O(n) | T(B*n) | derived | agree |
| `fdr_correct` | n_tests | 10000, 100000, 1000000, 4000000 | 1.27, 10.6, 149.3, 812.5 | +1.08 | 0.996 | 640x | O(n) | T(m log m) | derived | agree |
| `fire_indicator[n_onsets]` | n_onsets | 100, 300, 1000, 3000 | 4.00, 11.9, 38.6, 122.4 | +1.00 | 1.000 | 31x | O(n) | T(n_onsets log n_spikes) after one validation | derived | ORDER |
| `fire_indicator[n_spikes]` | n_spikes | 20000, 60000, 200000, 600000 | 3.95, 7.92, 75.7, 237.8 | +1.28 | 0.969 | 60x | O(n)-O(n^1.5) | T(n_spikes + n_onsets log n_spikes) | derived | ORDER |
| `fires_in_window` | n_spikes | 200000, 1000000, 5000000, 20000000 | 1.09, 4.78, 24.0, 96.7 | +0.98 | 1.000 | 88x | O(n) | T(log n) per query on already-validated sorted input | derived | ORDER |
| `paired_fire_prob_test[n_bootstrap]` | n_bootstrap | 2000, 6000, 20000, 60000 | 5.40, 10.8, 30.8, 83.5 | +0.81 | 0.994 | 15x | O(n) | T(n + B_b) | derived | ORDER |
| `paired_fire_prob_test[n_shuffles]` | n_shuffles | 2000, 6000, 20000, 60000 | 5.82, 13.1, 38.8, 112.7 | +0.87 | 0.997 | 19x | O(n) | T(n + B_s) | derived | ORDER |
| `paired_fire_prob_test[n_trials]` | n_trials | 100, 300, 1000, 3000 | 3.91, 10.7, 34.1, 102.8 | +0.96 | 1.000 | 26x | O(n) | T(n + B_s + B_b) | derived | ORDER |
| `rate_in_window` | n_spikes | 200000, 1000000, 5000000, 20000000 | 1.03, 4.51, 23.9, 96.0 | +0.99 | 0.999 | 93x | O(n) | T(log n) | derived | ORDER |
| `shuffle_pvalue_paired[n_samples]` | n_samples | 200, 600, 2000, 6000 | 9.78, 27.9, 92.0, 278.9 | +0.99 | 1.000 | 29x | O(n) | T(B*n) | derived | agree |
| `shuffle_pvalue_paired[n_shuffles]` | n_shuffles | 2000, 6000, 20000, 60000 | 4.09, 11.7, 37.6, 110.5 | +0.97 | 1.000 | 27x | O(n) | T(B*n) | derived | CONSTANT |
| `shuffle_pvalue_unpaired[n_samples]` | n_samples | 600, 2000, 6000, 20000 | 64.5, 155.7, 445.6, 1429 | +0.89 | 0.996 | 22x | O(n) | T(B*min(n_a,n_b)) | derived | ORDER |
| `shuffle_pvalue_unpaired[n_shuffles]` | n_shuffles | 1000, 3000, 10000, 30000 | 18.1, 54.6, 179.9, 542.5 | +1.00 | 1.000 | 30x | O(n) | T(B*min(n_a,n_b)) | derived | ORDER |
| `shuffle_r2_ci[n_samples]` | n_samples | 2000, 8000, 20000, 40000 | 165.7, 329.9, 709.6, 1340 | +0.69 | 0.978 | 8x | sub-linear | T(B*n) | derived | CONSTANT |
| `shuffle_r2_ci[n_shuffle]` | n_shuffle | 1000, 2000, 5000, 10000 | 111.2, 229.7, 567.6, 1146 | +1.01 | 1.000 | 10x | O(n) | T(B*n) | derived | CONSTANT |

### `jnwb.tfr`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `complex_tfr[n_channels]` | n_channels | 2, 16, 64, 256 | 2.52, 18.1, 68.5, 258.6 | +0.95 | 1.000 | 103x | O(n) | T(C) | derived | agree |
| `complex_tfr[n_freqs]` | n_freqs | 4, 16, 64, 128 | 15.1, 41.6, 166.8, 238.3 | +0.83 | 0.992 | 16x | O(n) | T(F) | derived | agree |
| `complex_tfr[n_samples]` | n_samples | 5000, 25000, 100000, 400000 | 2.80, 15.0, 87.6, 375.0 | +1.13 | 0.998 | 134x | O(n) | T(F*C*n log n) | derived | agree |
| `morlet_wavelet[n_cycles]` | n_cycles | 1000, 10000, 40000, 100000 | 9.30, 102.3, 431.1, 1072 | +1.03 | 1.000 | 115x | O(n) | T(K) | derived | agree |

### `jnwb.tfr_accumulator`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `TFRAccumulator[n_times]` | n_times | 10000, 1000000, 10000000, 50000000 | 0.06, 0.16, 0.17, 0.21 | +0.15 | 0.916 | 4x | O(1) | T(N) memory; O(1) wall clock | derived | agree |
| `assert_mergeable[n_freqs]` | n_freqs | 100000, 1000000, 5000000, 20000000 | 0.27, 1.79, 9.44, 37.2 | +0.93 | 0.997 | 139x | O(n) | T(m) | derived | CONSTANT |

### `jnwb.viz`

| spec | parameter | sizes | median times (ms) | exp | r2 | t-span | achieved | admissible | cls | gap |
|---|---|---|---|---|---|---|---|---|---|---|
| `apply_tight_auto_axis[n_lines]` | n_lines | 10, 30, 100, 300, 1000 | 0.63, 1.00, 1.86, 5.00, 15.1 | +0.69 | 0.972 | 24x | sub-linear | T(P), P = total points | derived | CONSTANT |
| `apply_tight_auto_axis[n_points]` | n_points | 1000, 3000, 10000, 30000, 100000 | 0.79, 1.29, 2.83, 6.15, 21.8 | +0.71 | 0.977 | 28x | sub-linear | T(P) | derived | CONSTANT |
| `raster_psth[n_bins]` | n_bins | 100, 500, 2000, 10000, 50000 | 6.56, 7.57, 12.0, 31.1, 139.3 | +0.49 | 0.893 | 21x | sub-linear (POOR FIT) | T(T*B) | derived | agree |
| `raster_psth[n_onsets]` | n_onsets | 10, 30, 100, 300, 1000 | 1.00, 2.11, 6.36, 19.1, 53.8 | +0.88 | 0.997 | 54x | O(n) | T(S log S + T*(log S + k + B)) | derived | ORDER |
| `raster_psth[n_spikes]` | n_spikes | 3000, 10000, 30000, 100000, 300000 | 5.44, 6.27, 6.02, 17.9, 45.0 | +0.46 | 0.818 | 8x | sub-linear (POOR FIT) | T(S log S + T*(log S + k + B)) | derived | ORDER |
| `resample_onsets[n_onsets]` | n_onsets | 100000, 300000, 1000000, 3000000, 10000000 | 0.28, 0.24, 0.21, 0.26, 0.25 | -0.01 | 0.040 | 1x | O(1) (NOT SEPARATED, POOR FIT) | T(target_n) | derived | agree |
| `resample_onsets[target_n]` | target_n | 1000, 5000, 20000, 100000, 500000 | 0.28, 0.53, 3.52, 9.56, 30.4 | +0.79 | 0.977 | 108x | sub-linear | T(target_n) | derived | agree |
| `save_figure_suite` | n_figures | 3, 5, 10, 20, 30 | 184.2, 293.2, 594.0, 1303, 2011 | +1.05 | 0.999 | 11x | O(n) | T(F * render) | derived | CONSTANT |

## 4. Gaps

19 order gaps lie along a parameter this measurement swept; 30 do not;
39 are constant-factor gaps that do not move the exponent. Highest measured cost first
within each group.

### 4.1 Order gaps the measurement corroborates

Each row states the exponent predicted **before** the sweep ran, under the implemented
algorithm and under the admissible one, then the exponent measured. A row where the
measurement lands on `pred ach` and away from `pred adm` corroborates the gap.

Three verdicts need reading carefully:

- **`no gap`** means the measurement matched the admissible exponent, so the source reading
  that predicted a worse order is not borne out. Those rows are recorded as measured and are
  **not** forwarded to 06-58. Where the source reading came from a document, section 6 records
  both sides rather than picking.
- **`neither`** is usually a fixed additive base flattening a real linear term: a call whose
  cost is `a + b*n` with a large `a` fits an exponent below 1 even though the `b*n` term is
  genuinely linear. The growth is still there -- check the `t-span` column, which is 14x to
  21x on these rows -- but the exponent understates it. It is evidence of growth, not
  evidence of the exponent.
- **`see note`** marks a cost that is not a power law at all, so no exponent is the right
  summary.

| spec | parameter | pred ach | pred adm | MEASURED | verdict | what the implementation does | admissible order |
|---|---|---|---|---|---|---|---|
| `exact_sign_flip[n_samples_exact]` | n_samples | - | - | +2.47 [POOR FIT] | see note (predicted after this group's sweep had run). EXPONENTIAL in N, not polynomial: a power-law exponent is not the right summary. The raw times, which should roughly double per added sample, are the evidence. | Exhaustive enumeration of all 2^N sign vectors, T(2^N*N): an exponential-exponent gap against the best known algorithm. | O(2^(N/2)*N) known; true lower bound unknown |
| `phase_slope_index[n_samples_jackknife]` | n_samples | +2.00 | +1.00 | +2.14 | **gap confirmed**, then closed: +1.05 after the change (section 6.2). | Before the change: a Python loop of S iterations, each taking a fancy-index COPY fx[keep] of an (S-1, L/2+1) complex array and recomputing three full-frequency means from scratch: T(S^2*L) = T(N^2/L). This is the DEFAULT path (jackknife=True at jnwb/connectivity.py:1604). | T(S*L) |
| `granger_spectral[model_order]` | model_order | +2.00 | +1.00 | +1.19 | **no gap** -- measurement matches the admissible order. | Same. | T(N*p + p^2 + F log F) |
| `granger_causality[model_order]` | model_order | +2.00 | +1.00 | +1.11 | **no gap** -- measurement matches the admissible order. | Same SVD least-squares route. | T(N*p + p^2) |
| `granger[model_order]` | model_order | +2.00 | +1.00 | +1.07 | **no gap** -- measurement matches the admissible order. | A design matrix of (N-p) x (1+2p) is materialised and solved by SVD least squares (LAPACK gelsd), giving T(N p^2 + p^3): a factor p in the data term and p in the solve above the recursion. | T(N*p + p^2) at d=2 |
| `spike_count_mutual_information[n_spikes]` | n_spikes | +1.30 | +1.00 | +1.01 | **no gap** -- measurement matches the admissible order. | The alphabet is the set of distinct per-bin counts, which grows with n_spikes/n_bins, so the dense Python double loop over the alphabet product grows too. | T(n_spikes + n_bins) |
| `jrsa[n_lags]` | n_lags | +1.00 | +0.00 | +0.99 | **gap confirmed**. | A Python loop over lags, each doing a full metric call: T(L*n log n). | T(1) in L; T(n log n) total for all lags |
| `rate_in_window` | n_spikes | +1.00 | +0.00 | +0.99 | **gap confirmed** (predicted after this group's sweep had run). | Same per-call whole-array guard. | T(log n) |
| `fires_in_window` | n_spikes | +1.00 | +0.00 | +0.98 | **gap confirmed** (predicted after this group's sweep had run). | A per-call sortedness and finiteness guard scans the whole array, T(n), and dominates. Verifying sortedness is genuinely Omega(n), so the cost is avoidable only by validating once rather than per query. | T(log n) per query on already-validated sorted input |
| `bandpass_filter[order]` | order | +1.00 | +0.00 | +0.93 | **gap confirmed**. | p biquad sections are applied in sequence, each a full pass. Not a drop-in swap: circular convolution changes transient and edge handling, so the substitution is an order gap, not an equivalence. | T(1) in p, at O(n log n) in n |
| `phase_locking_index[n_lfp_samples]` | n_lfp_samples | +1.00 | +0.00 | +0.88 | **gap confirmed**. | np.cos and np.sin are taken over the ENTIRE LFP trace before interpolating at S spike times: T(m) trig for S << m spikes. | T(1) in m with a uniform grid; T(log m) per spike by binary search |
| `assign_outer_folds[n_strata]` | n_strata | +1.00 | +0.00 | +0.86 | **gap confirmed**. | A Python loop over strata with three .loc assignments and a .map per stratum, about 1.25 ms per stratum: T(S) where T(1) in S is available. | T(1) in S with n fixed |
| `gaussian_smooth_rate[sigma_ms]` | sigma_ms | +1.00 | +0.00 | +0.85 | **gap confirmed**. | scipy.ndimage.gaussian_filter1d uses a direct FIR correlation whose tap count grows as about 8*sigma, so the cost is T(n*sigma). | T(n), independent of sigma |
| `stream_npz_array[n_elements_in_file]` | n_elements_in_file | +1.00 | +0.00 | +0.83 | **gap confirmed**, then closed: +0.01 after the change (section 6.2). | Before the change: _read_skip READS AND DISCARDS the (n-k) leading elements through a 64 KiB memoryview on a ZipExtFile -- a sequential forward skip with no seek. T(n) achieved against T(k) admissible; 710x slower than seek-then-read at n=1.6e7. | T(k) for ZIP_STORED |
| `causal_exp_smooth[tau_ms]` | tau_ms | +1.00 | +0.00 | +0.73 | **neither** -- measured +0.73. | np.convolve with a truncated exponential of 5*tau/bin taps, so T(n*tau). | T(n), independent of tau |
| `get_snr_analysis[n_sessions]` | n_sessions | +1.00 | +0.00 | +0.67 | **neither** -- measured +0.67. | A Python loop over sessions doing a FULL-TABLE boolean scan per session (jnwb/metadata.py:332-341): T(S*m). | T(m + S) |
| `classify_layer_from_depth` | n_electrodes | +1.00 | +0.00 | +0.65 | **neither** -- measured +0.65. | _resolve_electrode_row does a FULL LINEAR SCAN, electrodes_df.index[electrodes_df[id_col] == val] at jnwb/addressing.py:78: T(e). When no explicit id column exists the code already falls through to the T(1) hash path at line 83, so the slow branch is the one the code PREFERS -- and jnwb/addressing.py:60-64 documents why it prefers it, to avoid row-index/channel-ID substitution. | T(1) expected |
| `map_peak_channel_to_area` | n_electrodes | +1.00 | +0.00 | +0.62 | **neither** -- measured +0.62. | Single-area: T(e) where T(1) is available, via the same preferred linear scan. Multi-area: no order gap for a one-shot query; a cached per-probe partition would make repeated queries T(1) amortized. | T(1) expected for the single-area branch |
| `nested_cv_linear_svm[n_trials]` | n_trials | +2.50 | +1.00 | +0.54 [POOR FIT] | **neither** -- measured +0.54. | SVC(kernel='linear') is libsvm kernelized SMO, empirically T(n^2)-T(n^3) on a linear kernel (Bottou & Lin 2007). LinearSVC or SGDClassifier is the linear-time route. | T(n*d) |

### 4.2 Order gaps a single-parameter sweep cannot see

Found by reading the source. **Not confirmed and not refuted by this measurement**; the
reason each is invisible is stated, and it is a property of the sweep, not of the gap.

| spec | parameter | measured exp | why the sweep cannot see it | what the implementation does | admissible order |
|---|---|---|---|---|---|
| `assign_subblock_quartiles` | n_rows | +1.36 | A full sort against linear-time selection is a log n factor; below the calibrated resolution. | A full np.argsort is used where selection suffices: a log n factor. | T(n) |
| `bin_spikes[n_bins]` | n_bins | +1.01 | Both linear in n_bins at fixed n_spikes; the cross term's coefficient is n_spikes/65536 = 1.5 here. | Same edges-array path. | T(n_spikes + n_bins) |
| `bin_spikes[n_spikes]` | n_spikes | +0.99 | Both the block-sort path and bincount are linear in n_spikes; the gap is the (n_spikes/65536)*n_bins cross term's coefficient. | np.histogram is handed an edges ARRAY, which sends NumPy down the non-uniform cumulative path: per 65536-element block a sort plus a searchsorted against the edges. That makes the cost bilinear, T(n_spikes log B + (n_spikes/B)*n_bins), instead of additive. Passing bins=int, range=(t0,t1) is the additive path. | T(n_spikes + n_bins) |
| `binary_occupancy_mutual_information[n_spikes]` | n_spikes | +1.03 | Alias of the same pinned-alphabet path. | Alias of the same path. | T(n_spikes + n_bins) |
| `build_permutation_plan[n_permutations]` | n_permutations | +0.99 | Inherits the pinned G=10. | Inherits the T(G*n) factor from permute_labels; unmeasured at pinned G=10. | T(B*n) |
| `build_permutation_plan[n_samples]` | n_samples | +0.64 | Inherits the pinned G=10. | Same, plus one more T(G*n) pass at the end. | T(B*n) |
| `cross_area_coherence[n_bands]` | n_bands | +0.86 | T(B*F) against T(B log F): both linear in B. The gap is the F coefficient, not the B exponent. | Implemented rebuilds a boolean mask over all F bins per band, giving a T(B*F) term that is avoidable. Measurable only at unrealistic band counts (500-20000), so the exponent describes the band loop, not a plausible call. | T(F log F + B log F + sum_bins) |
| `cross_modal_comparison[n_permutations]` | n_permutations | +0.85 | Both linear in B. | A direct T(L*n) sweep per permutation, and _abs_pearson re-centres and re-norms x at every lag of every permutation although x never changes. Observed: the point estimate also runs spearmanr alongside pearsonr. | O(n log n) per permutation |
| `cross_modal_comparison[n_samples]` | n_samples | +0.68 | T(B*L*n) at pinned L=41 against T(B*n log n): both about linear in n, and the admissible form carries the larger exponent. | Same. | O(n log n) per permutation |
| `detect_trial_cycles` | n_rows | +1.31 | The spec pins zero breaks, so the T(n_breaks*n) branch does no work. Its quadratic branch is unmeasured BY DESIGN, not absent. | The break-accumulation loop is T(n_breaks*n), quadratic when breaks are dense, where a cumsum of a boolean break indicator is T(n). The spec pins zero breaks, so THAT BRANCH IS NOT MEASURED. | T(n log n) |
| `enrich_units_dataframe[n_electrodes]` | n_electrodes | +0.31 | Same, along e. | Same T(u*e) nested scan, seen along e. | T(e) additive, not multiplicative |
| `enrich_units_dataframe[n_units]` | n_units | +1.01 | T(u*e) against T(u+e): both linear in u at fixed e. The gap is multiplicative and needs both to grow. | Three separate .apply passes, each calling a T(e) resolve per unit: T(u*e). | T(u + e) |
| `fire_indicator[n_onsets]` | n_onsets | +1.00 | T(n_onsets*n_spikes) against T(n_onsets log n_spikes): both linear in n_onsets at fixed n_spikes. | A Python comprehension calls fires_in_window once per onset, so the whole spike array is re-validated per onset: T(n_onsets * n_spikes). | T(n_onsets log n_spikes) after one validation |
| `fire_indicator[n_spikes]` | n_spikes | +1.28 | Both linear in n_spikes at fixed n_onsets; the gap is the n_onsets coefficient. | Same re-validation. | T(n_spikes + n_onsets log n_spikes) |
| `get_all_units_metadata[n_channels_per_file]` | n_channels | +0.05 | Inherited gap, invisible at the fixture's fixed 2 units. | Inherited T(u*e); invisible at the fixture's fixed 2 units. | T(u + e) per file |
| `granger_spectral[n_freqs]` | n_freqs | +0.93 | T(F*p) against T(F log F): both linear in F. At the pinned p=5 the admissible FFT route is in fact the slower of the two, since log F is 7 to 14 over this range. No gap at this p. | A Python loop over F frequencies, each summing p complex 2x2 terms: T(F*p) where T(F log F) is available, and the loop is interpreted rather than vectorised over f. | T(d^2*F log F + d^3*F) |
| `jrsa[n_features]` | n_features | +0.58 | T(P*C^2*f) against T(C^2 f + P C^2 log C): both linear in f. The gap is the P coefficient. | _rsa recomputes the condensed distances of BOTH x1 and the permuted x2 on every permutation: T(P*C^2*f) where T(C^2 f) + T(P*C^2 log C) suffices. | T(C^2*f + P*C^2 log C) |
| `jrsa[n_samples]` | n_samples | +0.72 | The discarded spearmanr adds a log n factor; below the calibrated resolution. | _pearson routes through StatisticalAnalysis.exploratory_correlate, which runs BOTH stats.pearsonr and stats.spearmanr (jnwb/statistics.py:948-949) and discards the Spearman, paying a T(n log n) rank sort per evaluation on every permutation and bootstrap draw. | T(n) |
| `paired_fire_prob_test[n_bootstrap]` | n_bootstrap | +0.81 | Same, in B_b. | T(B_b*n): same. | T(n + B_b) |
| `paired_fire_prob_test[n_shuffles]` | n_shuffles | +0.87 | T(B_s*n) against T(n + B_s): both linear in B_s at fixed n. The gap is the n coefficient. | T(B_s*n): the sufficient statistic is not exploited. | T(n + B_s) |
| `paired_fire_prob_test[n_trials]` | n_trials | +0.96 | Both linear in n at fixed B. The gap is the B coefficient. | Same. | T(n + B_s + B_b) |
| `permute_labels[n_samples;within_group]` | n_samples | +1.08 | n_groups is pinned at 10, so the T(G*n) mask loop reads as linear. Stated by the spec author before the run. | A Python loop over groups computes groups == g TWICE per group, so the cost is T(G*n). The spec pins G=10, so THE SWEEP READS AS LINEAR AND DOES NOT EXPOSE THIS. | T(n) |
| `phase_locking_index[n_spikes]` | n_spikes | +0.80 | T(S log m) against T(S): log m is constant at fixed m. | np.interp does a binary search per spike, T(S log m), and cannot exploit the uniform grid. | T(S) |
| `raster_psth[n_onsets]` | n_onsets | +0.88 | T(T*S) against T(T log S): both linear in T at fixed S. | A full boolean mask over the WHOLE spike array per trial (jnwb/viz.py:146-149): T(T*S). The T*S term is removable. | T(S log S + T*(log S + k + B)) |
| `raster_psth[n_spikes]` | n_spikes | +0.46 | T(T*S) against T(S log S + T log S): both about linear in S. | Same per-trial full mask. | T(S log S + T*(log S + k + B)) |
| `shuffle_pvalue_unpaired[n_samples]` | n_samples | +0.89 | Both linear in n. | Same. | T(B*min(n_a,n_b)) |
| `shuffle_pvalue_unpaired[n_shuffles]` | n_shuffles | +1.00 | Both linear in B; the gap is a factor of about 2 in the per-draw work. | A full rng.shuffle over n_a+n_b plus two full np.mean per draw: the statistic admits an incremental update that is not taken. | T(B*min(n_a,n_b)) |
| `spike_mutual_information[n_bins]` | n_bins | +0.68 | np.unique adds only a log n_bins factor over the admissible linear count; below the calibrated resolution. | Same. | T(n_spikes + n_bins) |
| `spike_mutual_information[n_spikes]` | n_spikes | +1.02 | Binary occupancy pins the alphabet at 2x2, so the dense loop is constant and both paths are linear in n_spikes. | Inherits the bin_spikes edges-array path, adds a redundant np.sort of the spike times, and finishes with a dense Python double loop over the full alphabet product. | T(n_spikes + n_bins) |
| `transfer_entropy[n_samples]` | n_samples | +1.13 | The lexsort adds a log N factor over hashing; below the calibrated resolution. | _codes uses np.unique(axis=0, return_inverse=True), a void-dtype lexsort costing T(N*w*log N); the log N factor is avoidable by hashing. | T(N*(k+l)) expected |

### 4.3 Constant-factor gaps

The exponent is already the admissible one. These change the coefficient, sometimes by two
orders of magnitude, and none of them is an order defect.

| spec | parameter | measured exp | what costs more than it needs to |
|---|---|---|---|
| `aperiodic_fit[n_spectra]` | n_spectra | +1.00 | The design matrix is shared, so all rows could go through one lstsq with n_spectra right-hand sides -- one BLAS-3 call instead of n_spectra LAPACK calls. Same exponent. |
| `apply_tight_auto_axis[n_lines]` | n_lines | +0.69 | all_y.extend(ydata[...]) boxes every element into a np.float64 Python object, and np.min over that list re-parses them. A per-line np.nanmin/np.nanmax then a min over L values is the same exponent. |
| `apply_tight_auto_axis[n_points]` | n_points | +0.71 | Same boxing. |
| `assert_mergeable[n_freqs]` | n_freqs | +0.93 | np.array_equal builds the full boolean array before .all(), so it is T(m) even on a first-element mismatch where Omega(1) would do. Irrelevant on equal inputs, a real cost on unequal ones. |
| `audit_electrodes[n_electrodes]` | n_electrodes | +0.93 | A .apply with a Python lambda per row where .str.split().str[0].str.strip() is still T(e). |
| `audit_units` | n_units | +0.53 | The spike-times count is a Python generator loop; a vectorized length check is the same exponent. |
| `bad_channels_from_correlation[n_channels]` | n_channels | +1.35 | An n x n boolean mask ~np.eye(n) is materialised to take each row's off-diagonals, avoidable with two slices per row. |
| `bipolar_reference[n_channels]` | n_channels | +0.99 | A full gather copy is performed even when channel_order is None (an np.arange identity). |
| `build_inner_validation_partitions[n_trials]` | n_trials | +0.97 | A triple nested Python loop with train.iterrows() innermost at about 33 us/row, where np.repeat/np.tile column construction would cut it roughly 100x. |
| `classify_unit_quality` | n_units | +0.70 | A row-wise .apply constructing a Series per row, plus a full-column .apply per threshold whose result is then masked: a very large constant, not a different exponent. |
| `cluster_permutation_test[n_permutations]` | n_permutations | +1.00 | For the paired sign-flip path the sum of squared differences is flip-invariant, so the variance need not be recomputed per draw; only the sign-flip product is, and all B of those are one GEMM. |
| `cluster_permutation_test[n_samples]` | n_samples | +0.86 | Same. |
| `compress_fp32` | n_bytes | +0.57 | About 3 full passes: a per-group h5py copy, a blockwise float64->float32 rewrite, then a second full structural copy into a fresh file. jnwb/compression.py:38-39 justifies the extra pass because HDF5 never reclaims space from deleted objects in the same file. Constant factor about 3, not an order gap. |
| `compute_response_metrics[n_spikes]` | n_spikes | +0.71 | np.sort is re-done on every call even for already-sorted input, which introsort does not detect. |
| `compute_response_metrics[n_trials]` | n_trials | +0.95 | The loop is at Python level (about 7 us/trial) where np.searchsorted already accepts the whole 4T query array in one call. |
| `electrode_inventory` | n_files | +0.99 | The per-file loop is embarrassingly parallel and jnwb._parallel exists but is not used here. |
| `epoch_continuous[n_events]` | n_events | +0.95 | Python for-loop with one slice copy per event; one fancy-index gather removes the per-event dispatch constant without changing the order. |
| `event_onsets` | n_events | +0.45 | Same iterrows walk. |
| `events` | n_events | +0.42 | to_dataframe() materialises all n x c columns and _extract_onsets then walks df.iterrows(), building a pandas Series per row: T(n*c) with about 37 us/row. Same exponent, roughly two orders of magnitude of constant. |
| `exact_sign_flip[n_mc]` | n_mc | +1.02 | Time matches; the whole (B,n) matrix is materialised where a chunked T(n) working set would do. |
| `filter_by_criteria[n_criteria]` | n_criteria | +0.62 | Coefficient m*C instead of m. |
| `filter_by_criteria[n_rows]` | n_rows | +0.87 | In n_rows alone both are T(m); the avoidable factor is the column count C multiplying every criterion, because each criterion does out = out[mask], a full-frame copy. |
| `fold_majority_baseline[n_labels]` | n_labels | +1.00 | Same deliberate np.unique choice. |
| `get_all_units_metadata` | n_files | +0.99 | Same serial per-file loop. |
| `imaginary_coherency` | n_samples | +1.02 | welch(x), welch(y) and csd(x,y) are three separate scipy passes that re-segment and re-transform x and y: 4 forward FFT passes where 2 would serve. |
| `jrsa[n_bootstrap]` | n_bootstrap | +1.01 | Same batching constant as permutations. |
| `jrsa[n_permutations]` | n_permutations | +1.03 | _p_from_null reduces each draw to one scalar, so all P permuted Pearson statistics are one (P x n)-by-(n) matvec rather than P Python-level metric calls. |
| `label_layers[n_channels]` | n_channels | +1.02 | An explicit Python loop with one np.all(np.isfinite(...)) call per contact, vectorisable over the (C,3) array. |
| `laplacian_reference[n_channels]` | n_channels | +0.99 | A Python for-loop over channels with one length-n vector op each, where the same three-term stencil is vectorised in voltage_curvature_1d. |
| `majority_baseline[n_labels]` | n_labels | +1.03 | np.unique sorts. The choice is deliberate and documented at jnwb/decoding.py:68-71: np.bincount was wrong for non-contiguous, negative and string labels. A correctness trade, not an oversight. |
| `nested_cv_linear_svm[n_features]` | n_features | +0.47 | The 4-point C grid recomputes kernel rows for each C with no Gram cache across grid points: about a 12x constant. |
| `rdm[n_conditions]` | n_conditions | +1.89 | scipy pdist runs a scalar C-level loop over all pairs rather than a GEMM: roughly a 10-50x throughput constant, same exponent. Holds for correlation/cosine/euclidean, not for cityblock. |
| `rdm[n_features]` | n_features | +1.15 | Same pdist-vs-GEMM constant. |
| `relative_power` | n_units | +1.01 | About 6 full passes over the data: two isfinite, two <0, one ==0, divide, mean. |
| `repair_band_artifacts[n_times]` | n_times | +0.84 | The substitution loop runs over all time indices for every band even where nothing is flagged, adding T(B*n) Python iterations a single np.where would avoid. Lower-order at fixed B. |
| `save_figure_suite` | n_figures | +1.05 | Renders are independent and serialized. |
| `shuffle_pvalue_paired[n_shuffles]` | n_shuffles | +0.97 | Memory T(B*n) where T(n) suffices. |
| `shuffle_r2_ci[n_samples]` | n_samples | +0.69 | Same. |
| `shuffle_r2_ci[n_shuffle]` | n_shuffle | +1.01 | _r2 recomputes np.std(s) and the full 2x2 corrcoef, including the score's own permutation-invariant variance, on every draw; one dot product against a pre-centred, pre-normalised score suffices. |

## 5. Admissible orders recorded as `unknown`

The item's stop condition: where the admissible order is a research question rather than a
known result, it is recorded as `unknown`. An assumed lower bound is not evidence, and a
plausible one is worse than none.

| spec | parameter | measured exp | best known upper bound | why no lower bound is citable |
|---|---|---|---|---|
| `cluster_permutation_test[n_permutations]` | n_permutations | +1.00 | T(B*n*P) upper bound; lower bound unknown | Each draw's t-map is a length-n contraction at each of P points; scipy.ndimage.label is union-find, T(P*alpha), essentially optimal. Whether the max-cluster null admits a fundamentally cheaper exact estimator is not a settled result. |
| `cluster_permutation_test[n_points]` | n_points | +0.71 | T(B*n*P + B*P*alpha) upper bound; lower bound unknown | Same; the labelling term is near-linear in P and optimal. |
| `cluster_permutation_test[n_samples]` | n_samples | +0.86 | T(B*n*P) upper bound; lower bound unknown | Same. |
| `compute_multitaper_psd[k_tapers]` | k_tapers | +1.03 | unknown | Each taper is a distinct weighted transform, and no citable result computes the K-taper average in fewer than K transforms. An assumed Omega(K) would not be evidence. |
| `compute_multitaper_psd[n_samples]` | n_samples | +0.99 | O(K*n log n) best known; lower bound unknown | K DPSS vectors come from a symmetric-tridiagonal subset eigenproblem, O(n*K) by bisection and inverse iteration; the K length-n transforms are O(K*n log n) by Cooley-Tukey. No Omega(n log n) lower bound for the DFT is proven in the general arithmetic model. |
| `exact_sign_flip[n_samples_exact]` | n_samples | +2.47 | O(2^(N/2)*N) known; true lower bound unknown | Horowitz-Sahni meet-in-the-middle: split the vector, enumerate 2^(N/2) half-sums each side, sort one side, count the tail by binary search. No tight lower bound is citable -- exact subset-sum counting is #P-hard in general. |
| `fit_exponential_onset[n_grid_points]` | n_grid_points | +0.94 | T(G); any sublinear alternative unknown | Brute-force 1-D search over a profile objective needs T(G) evaluations at grid resolution. Whether a sublinear search such as golden-section is valid is unknown: jnwb/onset_fitting.py:83-96 documents that the t0/tau surface is NOT well behaved, which is why the grid exists, but no unimodality result is stated or cited. |
| `nested_cv_linear_svm[n_folds]` | n_folds | +1.01 | T(k); exact sublinear-in-k SVM CV unknown | k-fold CV needs k independent fits unless the model admits an exact incremental shortcut. Ridge and kernel ridge do, via the hat-matrix identity; for the hinge-loss SVM only LOO BOUNDS exist (Vapnik-Chapelle span bound), not exact values. |

## 6. Reconciliation with complexity claims already in the repository

`artifacts/benchmarks/complexity_inventory.md` records upper bounds on time for 14 primitives,
each justified by the algorithm the implementation runs and a published reference, and labels
each row `INV-01` to `INV-14`. It does not claim to be timed. Timing existed before this file:
`artifacts/benchmarks/baseline_performance.json` records `time_ms` for its 21 entries, but at one
input scale each, which fixes no exponent. This file times them over at least three scales.

A bound is compared as a bound, and the columns are derived from it as follows.

| Column | Derivation |
|---|---|
| What it says | The inventory's time bound, quoted in this file's notation |
| Bound admits | The largest degree of the swept symbol over the bound's additive terms, every other symbol held. Where that term carries a log of the swept symbol, the least-squares exponent of the log factor over the spec's own sizes is added. A sweep in samples grows `K_seg` with `T`, because the segment length is held |
| Measured | The section 3 exponent |
| Verdict | `within bound` when Measured is at most Bound admits + 0.25 (section 2.5), `exceeds bound` otherwise |

`tests/test_computational_order_sources_agree.py` re-derives every quoted bound, every
`Bound admits` value and every verdict from the inventory, so an edit to either file that the
other does not follow fails the suite.

### 6.1 Claim-by-claim

| Claim | Source | What it says | Spec | Bound admits | Measured | Verdict |
|---|---|---|---|---|---|---|
| INV-01 | `artifacts/benchmarks/complexity_inventory.md` | complex_tfr: O(C . F . T log T) | `complex_tfr[n_channels]` | +1.00 | +0.95 | within bound |
|  |  |  | `complex_tfr[n_freqs]` | +1.00 | +0.83 | within bound |
|  |  |  | `complex_tfr[n_samples]` | +1.10 | +1.13 | within bound |
| INV-02 | `artifacts/benchmarks/complexity_inventory.md` | TFRAccumulator: O(R . C . F . T) | -- | -- | -- | not tested here: the bound is on the accumulate loop over R trials. The only public export is the constructor, whose cost is allocation. |
| INV-03 | `artifacts/benchmarks/complexity_inventory.md` | compute_psd: O(C . T log N_perseg) | `compute_psd[n_channels]` | +1.00 | +1.08 | within bound |
|  |  |  | `compute_psd[n_samples]` | +1.00 | +0.99 | within bound |
| INV-04 | `artifacts/benchmarks/complexity_inventory.md` | wpli: O(T log N_perseg) | `wpli` | +1.00 | +0.96 | within bound |
| INV-05 | `artifacts/benchmarks/complexity_inventory.md` | phase_slope_index: O(T log N_perseg + K_seg . F) | `phase_slope_index[n_samples]` | +1.00 | +1.02 | within bound; the spec runs `jackknife=False`, which drops the jackknife term |
|  |  |  | `phase_slope_index[n_samples_jackknife]` | +1.00 | +1.05 | within bound; re-measured after the change in section 6.2 |
| INV-06 | `artifacts/benchmarks/complexity_inventory.md` | granger: O(T . P^2 + P^3) | `granger[model_order]` | +3.00 | +1.07 | within bound |
|  |  |  | `granger[n_samples]` | +1.00 | +1.08 | within bound |
|  |  |  | `granger_causality[model_order]` | +3.00 | +1.11 | within bound |
|  |  |  | `granger_causality[n_samples]` | +1.00 | +1.11 | within bound |
| INV-07 | `artifacts/benchmarks/complexity_inventory.md` | transfer_entropy: O(S . T) | `transfer_entropy[n_samples]` | +1.00 | +1.13 | within bound |
| INV-08 | `artifacts/benchmarks/complexity_inventory.md` | vflip: O(C . F) | `vflip[n_channels]` | +1.00 | +1.07 | within bound |
|  |  |  | `vflip[n_freqs]` | +1.00 | +0.62 | within bound |
| INV-09 | `artifacts/benchmarks/complexity_inventory.md` | xflip: O(C^2 . T + S . C^2) | `xflip[n_channels]` | +2.00 | +1.78 | within bound |
|  |  |  | `xflip[n_samples]` | +1.00 | +0.88 | within bound |
|  |  |  | `xflip[n_surrogates]` | +1.00 | +0.94 | within bound |
| INV-10 | `artifacts/benchmarks/complexity_inventory.md` | zflip: O(C . T log N_perseg + S . C . F) | `zflip[n_channels]` | +1.00 | +1.03 | within bound |
|  |  |  | `zflip[n_samples]` | +1.00 | +0.86 | within bound |
|  |  |  | `zflip[n_surrogates]` | +1.00 | +0.92 | within bound |
| INV-11 | `artifacts/benchmarks/complexity_inventory.md` | rdm: O(N^2 . D) | `rdm[n_conditions]` | +2.00 | +1.89 | within bound |
|  |  |  | `rdm[n_features]` | +1.00 | +1.15 | within bound |
| INV-12 | `artifacts/benchmarks/complexity_inventory.md` | rdm_similarity: O(N^2 log N) | `rdm_similarity[n_conditions]` | +2.16 | +2.11 | within bound |
| INV-13 | `artifacts/benchmarks/complexity_inventory.md` | nested_cv_linear_svm: O(K . N_C . R^2 . D) | `nested_cv_linear_svm[n_features]` | +1.00 | +0.47 | within bound |
|  |  |  | `nested_cv_linear_svm[n_folds]` | +1.00 | +1.01 | within bound |
|  |  |  | `nested_cv_linear_svm[n_trials]` | +2.00 | +0.54 | within bound |
| INV-14 | `artifacts/benchmarks/complexity_inventory.md` | stream_npz_array: O(E) | `stream_npz_array[n_elements_in_file]` | +1.00 | +0.01 | within bound; re-measured after the change in section 6.2 |
|  |  |  | `stream_npz_array[n_elements_sliced]` | +1.00 | +0.49 | within bound |
| DOC-01 | `jnwb/rsa.py:70-72` | Complexity: Time: O(N^2 . D); Memory: O(N^2) for condensed or full matrix representation. | `rdm[n_conditions]` | +2.00 | +1.89 | agrees |
|  |  |  | `rdm[n_features]` | +1.00 | +1.15 | agrees |
| DOC-02 | `jnwb/spiking.py:373-375` | Uses the exact O(N) resultant formulation ... mathematically identical to the O(N^2) double sum over all unique pairs. | `pairwise_phase_consistency[n_samples]` | +1.00 | +0.99 | agrees |
| DOC-03 | `jnwb/spectral.py:628` | To reject at a smaller alpha, raise this; the cost is linear. (on n_surrogates) | `cross_area_coherence[n_surrogates]` | +1.00 | +0.98 | agrees |
| DOC-04 | `jnwb/spiking.py:106` | # Searchsorted instead of masking: O(log N) instead of O(N) | -- | -- | -- | not tested here: Scoped to the per-onset lookup, not to the call. The same function sorts the spike train on every call (jnwb/spiking.py:103), so the CALL is not sub-linear in n_spikes and the comment does not claim it is. compute_response_metrics[n_spikes] measures the call. |
| DOC-05 | `jnwb/analyzers.py:8 and :467` | UnitAnalyzer._acg_pearson: vectorized via np.searchsorted (O(N log N), was O(N^2)) | -- | -- | -- | not tested here: A private static method reached through UnitAnalyzer.autocorrelogram. The public export is the class, whose constructor is O(1) and is excluded. Untested here. |
| DOC-06 | `jnwb/jrsa.py:1300-1302 and :1322` | Centered Kernel Alignment optimized for linear complexity O(md^2) when d << m ... O(m*d1*d2) rather than O(m^3) | -- | -- | -- | not tested here: On the metric='cka' path, which no spec exercises. Untested here. |
| DOC-07 | `jnwb/jrsa.py:1348 and :1357` | RV coefficient optimized via trace identity to run at O(md^2) when d << m ... drops calculation from O(m^3) to O(m * d1 * d2 + d1^3). | -- | -- | -- | not tested here: On the metric='rv' path, which no spec exercises. Untested here. |
| DOC-08 | `jnwb/io.py:1, :3, :163-164` | Streaming array slice reader for NPZ archives without full-file RAM allocation ... memory-bounded streaming access ... without loading the full array into RAM. | -- | -- | -- | not tested here: A MEMORY claim, and it is true: peak memory is proportional to the slice. It licenses no time claim, and the measured time is linear in the size of the array in the file. Recorded so 'streaming' is not read as 'cheap'. |
| DOC-09 | `docs/02_paths_addressing_metadata.md:51` | Peak memory is strictly proportional to the requested output slice plus bounded streaming/selection overhead | -- | -- | -- | not tested here: Same: a memory claim, not contradicted. Time is a separate question and INV-14 is the claim that speaks to it. |
| DOC-10 | `jnwb/_backend.py:5` | Eighteen call sites across nine modules route through here. | -- | -- | -- | not tested here: Not a complexity claim. Re-counted: 18 resolve_device call sites across 9 files in jnwb/, excluding the definition. The documentation is accurate. |

### 6.2 Measurements above their bound

None. Eight measurements were recorded here as contradictions while the inventory was read as
stating exponents. Read as upper bounds, six measure below theirs. Two exceeded the bounds as then
written, and the inventory was restated to the cost the code had: the jackknife's `K_seg^2 . F`
term in `INV-05`, and the position bound `O(E)` in `INV-14`. The code then removed both costs, the
inventory was restated to the new code (`INV-05` linear in `K_seg`; `INV-14` still `O(E)`, the
compressed case), and both rows were re-measured with `scripts/measure_order.py` at `19a8496d`:

| Claim | What it says | Spec | Bound admits | Before the change | Measured | Verdict |
|---|---|---|---|---|---|---|
| INV-05 | phase_slope_index: O(T log N_perseg + K_seg . F) | `phase_slope_index[n_samples_jackknife]` | +1.00 | +2.21, +2.02, +2.16 | +1.05 | within bound |
| INV-14 | stream_npz_array: O(E) | `stream_npz_array[n_elements_in_file]` | +1.00 | +0.86, +0.86, +0.87 | +0.01 | within bound |

`Before the change` is three runs at `30bf969c` on the section 3 ladders; `Measured` is the median
of three runs at `19a8496d`. Host: Intel64 Family 6 Model 85, 24 logical CPUs, Python 3.14.3, NumPy
2.4.6, OpenBLAS pinned to one thread and verified; the section 2.4 calibration on this host
recovered `np.add` +1.04, a Python double loop +2.14 and `np.matmul` +2.88. The host is shared: total CPU load sampled after each of the three runs was 37%, 26% and 52%, against single-threaded sweeps.

| Spec | Change | Receipt at `19a8496d` |
|---|---|---|
| `phase_slope_index[n_samples_jackknife]` | Each left-out mean is a prefix sum plus a suffix sum over the band's bins, T(S*B), where each replicate had copied the S-1 remaining segments and recomputed three spectra over every frequency, T(S^2*F). One segment is still left out per replicate | +1.05, +1.05, +1.04 over 60000 to 4000000 samples; at 50000 samples 12.34 ms against 803.6 ms before (65x) |
| `stream_npz_array[n_elements_in_file]` | A stored entry seeks past the elements a slice skips; a compressed entry still decompresses up to the last selected element | +0.01, +0.00, +0.02 over 1e5 to 1.6e7 elements; at 1.6e7 elements 0.5172 ms against 82.11 ms before (159x) |

Both bounds are now looser than the code. The jackknife costs `K_seg . F` rather than
`K_seg^2 . F`, and a stored archive costs the slice rather than its position; the inventory's
algorithm column still describes the replaced code for both rows.

## 7. Exports excluded because their cost does not grow with input size

| Category | Count |
|---|---|
| result container | 21 |
| exception class | 13 |
| constant | 5 |
| stateful class | 4 |
| module | 4 |
| no input | 1 |
| scalar input | 1 |
| scalar input, domain-capped | 1 |
| fixed-shape input | 1 |
| plan description | 1 |
| **Total** | **52** |

| Export | Category | Reason |
|---|---|---|
| `AcquisitionNotFoundError` | exception class | Exception subclass; construction is O(1) in every input dimension. |
| `AlignedDataset` | result container | frozen dataclass, no __post_init__; binds 2 references. |
| `Alignment` | result container | frozen dataclass, no __post_init__; binds 3 scalars. |
| `AmbiguousAcquisitionError` | exception class | Exception subclass; construction is O(1) in every input dimension. |
| `AmbiguousIntervalTableError` | exception class | Exception subclass; construction is O(1) in every input dimension. |
| `AmbiguousLayoutError` | exception class | Exception subclass; construction is O(1) in every input dimension. |
| `AperiodicFitResult` | result container | dataclass, no __post_init__, 7 scalar fields. Triaged directly: is_dataclass True, hasattr __post_init__ False. |
| `CANONICAL_BANDS` | constant | A dict of band edges (jnwb/spectral.py:192). |
| `ChannelIndexError` | exception class | Exception subclass; construction is O(1) in every input dimension. |
| `ColumnNotFoundError` | exception class | Exception subclass; construction is O(1) in every input dimension. |
| `ComplexTFR` | result container | frozen dataclass, no __post_init__; __init__ binds 8 references. Its power/phase/amplitude PROPERTIES do scale, but they are not the export. |
| `DB_AGGREGATIONS` | constant | A 2-element tuple of str literals (jnwb/spectral.py:289). |
| `DETECTION_TAILS` | constant | A 2-element tuple of str literals. |
| `Dataset` | result container | frozen dataclass, no __post_init__. Its __hash__/__eq__ do grow, but construction does not. |
| `DirectedResult` | result container | plain dataclass (jnwb/connectivity.py:627-719); __init__ binds references. Its methods are O(number of bands), not O(input). |
| `EpochCollection` | result container | frozen dataclass, no __post_init__. Its __len__/__eq__ grow; construction does not. |
| `EventTable` | result container | frozen dataclass; generated __init__ binds 8 already-built fields by reference, no __post_init__. |
| `Figure` | result container | mutable dataclass, no __post_init__; binds references. |
| `Interpretation` | result container | frozen dataclass, no __post_init__; default_factory builds empty containers. |
| `IntervalTableNotFoundError` | exception class | Exception subclass; construction is O(1) in every input dimension. |
| `InvalidOnsetValueError` | exception class | Exception subclass; construction is O(1) in every input dimension. |
| `JRSAResult` | result container | plain dataclass (jnwb/jrsa.py:30); construction is O(1) field binding. summary/plot/save do scale but are not the export. |
| `Lineage` | result container | frozen dataclass, no __post_init__. |
| `MissingRequiredNWBFieldError` | exception class | __init__ formats one f-string from one field name: O(1). |
| `NWBEventError` | exception class | Exception subclass; construction is O(1) in every input dimension. |
| `NWBInspectError` | exception class | Exception subclass; construction is O(1) in every input dimension. |
| `PopulationAnalyzer` | stateful class | PopulationAnalyzer defines no __init__; every member is a @staticmethod. Construction is O(1). Its static methods are not separate jnwb.__all__ names. |
| `Preflight` | result container | frozen dataclass; __post_init__ validates the outcome, the reason and each name in `missing`, which a caller's plan bounds, not any data size. |
| `ProbeGeometry` | result container | frozen dataclass, no __post_init__ (verified programmatically); binds references only. |
| `Provenance` | result container | frozen dataclass, no __post_init__. Two init=False fields call a cached version lookup: fixed work, no input-size dependence. |
| `Query` | result container | frozen dataclass, no __post_init__. |
| `Question` | result container | frozen dataclass, no __post_init__. |
| `RELATIVE_POWER_MODELS` | constant | A 3-element tuple of str literals (jnwb/spectral.py:295). |
| `Result` | result container | frozen dataclass, no __post_init__. |
| `SKILLS_URL` | constant | A str literal. |
| `SqueezedAttributeWarning` | exception class | Warning subclass; construction is O(1) in every input dimension. |
| `StatisticalAnalysis` | stateful class | Namespace class: no own __init__ ('__init__' in vars(...) is False), signature (), 0.07 us to construct. |
| `TFRAnalyzer` | stateful class | TFRAnalyzer defines no __init__; every member is a @staticmethod. Construction is O(1). Its static methods are not separate jnwb.__all__ names. |
| `UnitAnalyzer` | stateful class | UnitAnalyzer defines no __init__; every member is a @staticmethod. Construction is O(1). Its static methods are not separate jnwb.__all__ names. |
| `UnitNotFoundError` | exception class | Exception subclass; construction is O(1) in every input dimension. |
| `VFlipResult` | result container | frozen dataclass + DictAccessMixin (read-only accessors); no __post_init__. |
| `XFlipResult` | result container | frozen dataclass, no __post_init__ (jnwb/laminar.py:866); only method is to_dict. |
| `ZFlipResult` | result container | frozen dataclass, no __post_init__ (jnwb/laminar.py:1532); only method is to_dict. |
| `classify_response_significance` | fixed-shape input | Input is the fixed 7-key metrics dict from compute_response_metrics; the body is dict lookups plus one scalar norm.cdf. No input dimension exists to scale. |
| `clopper_pearson` | scalar input | Arguments are counts, not arrays. Work is two scipy.stats.beta.ppf evaluations, measured flat at 136-140 us/call for n = 10 to 1e18 -- 18 orders of magnitude with no trend. |
| `io` | module | Module-valued export: a namespace, not a callable. Nothing to scale. |
| `mann_whitney_p_floor` | scalar input, domain-capped | Cost DOES grow with the numeric value (math.comb is bignum work: 0.58 us at n=5, 48 us at n=512), but float(n_comb) caps the domain: the largest working n1=n2 is 514, and 515 raises OverflowError. At the domain ceiling one call costs 48 us, about 100x below the noise floor, so no admissible size reaches the timing band. |
| `paths` | module | Module-valued export: a namespace, not a callable. Nothing to scale. |
| `preflight` | plan description | Reads the fields of one `Question` and loops once over its named signals; it touches no data array, so no data dimension exists to scale. |
| `setup_vector_graphics` | no input | Takes no data; sets 3 matplotlib rcParams. |
| `vis` | module | Module-valued export (the optional `vis` extra): a namespace, not a callable. Nothing to scale. |
| `visual_qc` | module | Module-valued export: a namespace, not a callable. Nothing to scale. |

## 8. Exports whose cost grows but which cannot be measured here

| Export | What a measurement would need |
|---|---|
| `build_time_resolved_matrix` | An object satisfying the session protocol: get_units(quality=, area=) -> DataFrame whose ROW INDEX POSITION (not the unit_id column) is the spike-lookup key, carrying area and quality columns; plus get_spike_times(row_position) -> ndarray of seconds; plus an epochs DataFrame with a start_time column. All three must be parameterizable in unit count, trial count and spikes per unit. No such class exists in the package: grep 'def get_units' hits only tests/test_trajectory.py:37 and tests/test_pca_device_parity.py:210, both hard-coded mocks with no size parameter. tests/test_declared_return_shapes.py:37 already lists both names under NEEDS_A_SESSION. Writing a stand-in would mean choosing its per-unit spike count and get_units cost, which is the exact freedom that would corrupt the fitted exponent. |
| `compute_population_trajectory` | The same session object -- it delegates to build_time_resolved_matrix on its first line -- plus, to measure the SVD stage independently, a way to supply X directly, which the signature does not offer. |
| `nwb_read_io` | Cost grows with the number of NWB containers and attributes in the file; datasets are read lazily, so their size does not enter until the caller indexes them. A measurement needs NWB files generated at controlled container counts. No such generator exists in the package, and a test-only one would choose the per-container cost, which is the freedom that would corrupt the fitted exponent. It opens the file through the same repair context as `read_nwb`. |
| `read_nwb` | Cost grows with the number of NWB containers and attributes in the file; datasets are read lazily, so their size does not enter until the caller indexes them. A measurement needs NWB files generated at controlled container counts. No such generator exists in the package, and a test-only one would choose the per-container cost, which is the freedom that would corrupt the fitted exponent. |

## 9. Blockers

| Kind | Subject | Blocker | Evidence |
|---|---|---|---|
| fixture-limit | events, event_onsets, unit_spike_times | n_events is capped at 20000 because TimeIntervals.add_row build cost is superlinear: 5000 rows took 27 s and 20000 rows took 607 s. A build-cost limit, not an API limit. | Measured during fixture construction; the 20000-row fixture is cached so the 607 s is paid once. |
| fixture-limit | resolve_acquisition | Its real parameter is the number of acquisitions plus processing interfaces; the fixture always builds exactly one. | -- |
| fixture-limit | resolve_interval_table | Its real parameter is the number of interval tables; interval_layout offers only 1 or 5, not a decade. Rows were swept instead, which shows rows are NOT the parameter. | -- |
| fixture-limit | unit_spike_times, electrode_inventory, get_all_units_metadata | Units per file cannot be varied: build_synth_nwb hardcodes exactly 2 units and unit count is not a SynthNWBBuildOptions field. The parameter a caller most likely cares about is therefore unmeasured. | jnwb/testing/nwb_fixtures.py:351-355. |
| method-limit | 30 of the 49 order gaps | A single-parameter sweep cannot distinguish T(u*e) from T(u+e), nor an avoidable log n factor (0.06 of exponent over a decade) from none. Those gaps are neither confirmed nor refuted here. | Section 2.6 and table 4.2, which names the reason per row. |
| method-limit | every BLAS-backed export | Even pinned to one thread, the wall-clock exponent under-reports the operation-count order: an exactly-O(n^3) GEMM recovers 2.86, not 3.00. Reported exponents inherit that bias. | Calibration section 2.4; worst recovery error 0.18 across four known orders. |
| method-limit | every export with a GPU or parallel path | device is pinned to cpu and n_jobs to 1 throughout, so the orders recorded are algorithmic and say nothing about the CUDA or parallel-CPU paths. | Section 2.3. Items 06-56 and 06-59 own the execution switch. |
| method-limit | fit_exponential_onset, nested_cv_linear_svm | Iteration counts of scipy least_squares and of libsvm SMO are data-dependent and are not a function of the swept parameter, so both sweeps carry scatter that is not a second scaling parameter. | nested_cv classes are linearly separable by construction to limit it. |
| method-limit | granger / granger_causality / granger_spectral in model_order | The source reading and the measurement disagree, and this file does not resolve it. Reading the code predicts T(N p^2) from an SVD least-squares solve on a materialised (N-p) x (1+2p) design, so an exponent near 2.0 in p. The measurement fits +1.07, +1.11 and +1.19, which is the exponent the Levinson recursion would give. Either LAPACK gelsd is not the cost driver at these sizes, or a p-independent term (the adfuller and Ljung-Box passes, both T(N)) dominates and dilutes the exponent. Both readings are recorded; neither is picked. | Measured over p = 2..70 at N = 20000, t-span 45x to 82x, r2 0.974 to 1.000. |
| method-limit | reading an order off the source | Six specs where the source reading predicted a worse order than the measurement found (the three granger rows, spike_count_mutual_information[n_spikes], and the two pandas lookup exports at +0.62 to +0.65). A nested loop in the source is not by itself evidence of the order it looks like, which is why this item required measurement. | Section 4.1, verdict columns 'no gap' and 'neither'. |
| method-limit | spike_count_mutual_information[n_spikes] | The joint-table alphabet is a function of n_spikes/n_bins, so holding it fixed while sweeping n_spikes is impossible without also changing n_bins. The coupling is intrinsic to the estimator, so the fitted exponent is not a pure n_spikes exponent. | -- |
| unknown-bound | cluster_permutation_test | No published result establishes a lower bound for the exact max-cluster permutation null. | Section 5. |
| unknown-bound | compute_multitaper_psd[k_tapers] | No citable result computes the K-taper average in fewer than K transforms. An assumed omega(K) would not be evidence. | Recorded as unknown rather than assumed. |
| unknown-bound | every FFT-driven export | No omega(n log n) lower bound for the DFT is proven in the general arithmetic model, so T(n log L) is the best known order, not a proven optimum. | complex_tfr, vflip_from_lfp, zflip, compute_multitaper_psd rows in section 5. |
| unknown-bound | every Gram-matrix export | The exact optimum is tied to the matrix-multiplication exponent omega, itself an open problem. T(m^2 n) is the practical GEMM answer. | channel_correlation_matrix, trial_correlation_matrix, bad_trials_single_channel, rdm. |
| unknown-bound | exact_sign_flip[n_samples_exact] | Only the Horowitz-Sahni O(2^(N/2) N) upper bound is citable; exact subset-sum tail counting is #P-hard in general, so no tight lower bound exists. | Section 5. |
| unknown-bound | fit_exponential_onset[n_grid_points] | Whether a sublinear search over the t0 grid is valid is unknown: the source documents that the t0/tau surface is not well behaved, which is why the grid exists, but states no unimodality result. | jnwb/onset_fitting.py:83-96. |
| unknown-bound | granger / granger_causality / granger_spectral in model_order | T(N p + p^2) via the Levinson-Whittle recursion is the best PUBLISHED algorithm; no matching lower bound in p exists in the literature. | Whittle 1963; Morf, Vieira, Lee & Kailath 1978; Barnett & Seth 2014. |
| unknown-bound | nested_cv_linear_svm[n_folds] | Ridge and kernel ridge admit an exact leave-one-out shortcut via the hat-matrix identity; for the hinge-loss SVM only LOO BOUNDS exist (Vapnik-Chapelle span bound), not exact values. Whether an exact sublinear-in-k SVM CV shortcut exists is unknown. | Section 5. |
| unknown-bound | transfer_entropy, continuous-valued estimators | The minimal order for a consistent continuous transfer-entropy estimator is an open question. jnwb ships only binned plug-in and Bandt-Pompe symbolic estimators, so the measured rows apply to those and to nothing else. | Recorded so the binned result is not misread as a statement about TE in general. |
| unknown-bound | xflip[n_channels] | Whether the O(K*C^2) segmentation DP admits the O(K*C log C) SMAWK speedup depends on the interval weight matrix satisfying the quadrangle inequality, which is not known for W(u,v)=S(u,v)-gamma*P(u,v) on an arbitrary correlation matrix. | jnwb/laminar.py:1043-1051; establishing it is a research question, not a lookup. |
| unmeasurable | build_time_resolved_matrix, compute_population_trajectory | No scalable session object exists in the package; the only implementations of the protocol are two hard-coded test mocks with no size parameter. Writing a stand-in would mean choosing the very costs being measured. | grep 'def get_units' hits only tests/test_trajectory.py:37 and tests/test_pca_device_parity.py:210. tests/test_declared_return_shapes.py:37 already lists both under NEEDS_A_SESSION. |
| unmeasured-path | UnitAnalyzer.autocorrelogram | The documented O(N log N) claim is on a private static method reached through the class; the public export is the class, whose constructor is O(1) and is excluded. | jnwb/analyzers.py:8, :467. |
| unmeasured-path | acquisition_channel, compress_fp32 | Bytes actually moved by HDF5 were not instrumented, so whether the hyperslab touches n*24 or n*4 bytes, and whether h5py recompresses already-compressed chunks, stay inferred. | -- |
| unmeasured-path | detect_trial_cycles | The spec pins zero cycle breaks, so the T(n_breaks*n) accumulation loop does no work. Its quadratic branch is unmeasured BY DESIGN -- scaling breaks as well as n would scale two things at once. | Stated by the spec author before the run. |
| unmeasured-path | granger, granger_spectral, phase_slope_index, transfer_entropy | n_surrogates is pinned to 0 so the core estimator's exponent is not swamped. transfer_entropy DEFAULTS to n_surrogates=200, so the measured path is about 400x cheaper than the library default. | -- |
| unmeasured-path | jrsa metric='cka' and metric='rv' | The two documented O(md^2) complexity claims sit on these paths, which no spec exercises. The claims are recorded in section 6 and remain unchecked. | jnwb/jrsa.py:1300, :1348. |
| unmeasured-path | map_peak_channel_to_area | The multi-area partition branch was not swept; only the single-area short-circuit was. | jnwb/addressing.py:131-141. |
| unmeasured-path | permute_labels[within_group], build_permutation_plan | n_groups is pinned at 10, so the T(G*n) double-mask loop reads as linear. Exposing it needs a separate n_groups sweep, which is a different scaling parameter. | -- |
| unmeasured-path | phase_slope_index[nperseg] | No valid sweep exists: cost is non-monotone and DECREASING in nperseg at fixed n_samples (0.2185 s at 64 against 0.1542 s at 16384, n=2e6), because the segment count falls as nperseg rises. Fitting an exponent would fit noise. | Measured, not assumed. |
| unmeasured-path | stream_npz_array | The per-element readinto loop in _stream_slice is only reached for strided or multi-dimensional slices; both specs use 1-D contiguous slices. A second suspected order gap is unquantified. | jnwb/io.py:138-151. |

## 10. What item 06-58 should take first

Restricted to the order gaps this measurement corroborates, ordered by the size of the
exponent gap (measured exponent minus the admissible one). That ordering is a proxy for how
badly the export degrades as its input grows, not for how much wall clock it costs any
particular caller. Nothing here is applied under 06-54.

| Rank | Spec | Measured | Exponent gap | Admissible | The change |
|---|---|---|---|---|---|
| 1 | `phase_slope_index[n_samples_jackknife]` | +2.14 in `n_samples` | +1.14 | T(S*L) | **Applied**, +1.05 after (section 6.2). Was: a Python loop of S iterations, each taking a fancy-index COPY fx[keep] of an (S-1, L/2+1) complex array and recomputing three full-frequency means from scratch: T(S^2*L) = T(N^2/L). This is the DEFAULT path (jackknife=True at jnwb/connectivity.py:1604). |
| 2 | `jrsa[n_lags]` | +0.99 in `n_lags` | +0.99 | T(1) in L; T(n log n) total for all lags | A Python loop over lags, each doing a full metric call: T(L*n log n). |
| 3 | `rate_in_window` | +0.99 in `n_spikes` | +0.99 | T(log n) | Same per-call whole-array guard. |
| 4 | `fires_in_window` | +0.98 in `n_spikes` | +0.98 | T(log n) per query on already-validated sorted input | A per-call sortedness and finiteness guard scans the whole array, T(n), and dominates. Verifying sortedness is genuinely Omega(n), so the cost is avoidable only by validating once rather than per query. |
| 5 | `bandpass_filter[order]` | +0.93 in `order` | +0.93 | T(1) in p, at O(n log n) in n | p biquad sections are applied in sequence, each a full pass. Not a drop-in swap: circular convolution changes transient and edge handling, so the substitution is an order gap, not an equivalence. |
| 6 | `phase_locking_index[n_lfp_samples]` | +0.88 in `n_lfp_samples` | +0.88 | T(1) in m with a uniform grid; T(log m) per spike by binary search | np.cos and np.sin are taken over the ENTIRE LFP trace before interpolating at S spike times: T(m) trig for S << m spikes. |
| 7 | `assign_outer_folds[n_strata]` | +0.86 in `n_strata` | +0.86 | T(1) in S with n fixed | A Python loop over strata with three .loc assignments and a .map per stratum, about 1.25 ms per stratum: T(S) where T(1) in S is available. |
| 8 | `gaussian_smooth_rate[sigma_ms]` | +0.85 in `sigma_ms` | +0.85 | T(n), independent of sigma | scipy.ndimage.gaussian_filter1d uses a direct FIR correlation whose tap count grows as about 8*sigma, so the cost is T(n*sigma). |
| 9 | `stream_npz_array[n_elements_in_file]` | +0.83 in `n_elements_in_file` | +0.83 | T(k) for ZIP_STORED | **Applied**, +0.01 after (section 6.2). Was: _read_skip READS AND DISCARDS the (n-k) leading elements through a 64 KiB memoryview on a ZipExtFile -- a sequential forward skip with no seek. T(n) achieved against T(k) admissible; 710x slower than seek-then-read at n=1.6e7. |

---

Generated from 189 timing sweeps over 106 exports at `f23d96ceb4b1`.
Raw per-size medians are in the tables above; the harness, the spec definitions and the
calibration scripts were scratch files and are not part of the repository.
`scripts/measure_order.py` is the committed harness for the four `phase_slope_index` and
`stream_npz_array` sweeps and for the calibration, and re-measured the two rows section 6.2
names at `19a8496d`. The other 185 sweeps have no committed generator.
