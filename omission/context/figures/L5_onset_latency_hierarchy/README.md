# L5 — cross-area LFP onset latency (stim), causal pipeline

Reads `canonical_pooling_method` from [L0](../L0_pooling_reconciliation/L0_stats.json). The
highest-stakes script in the LFP track — the spec calls acausal smoothing "the single most
likely way to get the FF/FB answer wrong." Every stage is causal by construction: single-pass
Butterworth bandpass (`scipy.signal.lfilter`, **not** `filtfilt` — see `omission-signal` S3),
full-wave rectification, canonical-method-(a) pooling (linear, commutes with the causal smoother
so it's applied once on the pooled trace, not once per trial-channel), then
`jnwb.onset_fitting.causal_exp_smooth` + `fit_exponential_onset` — the **same, already-validated**
functions this session's spiking onset-hierarchy fix used
([artifacts/.lab/onset-hierarchy-h1h2h3-fixed-20260815.json](../../../artifacts/.lab/onset-hierarchy-h1h2h3-fixed-20260815.json)),
reused not reimplemented, including the causality-bounded-by-construction `t0` and the
500 ms real-history extraction margin (same fix class as the boundary-pinning bug found and
fixed earlier this session).

**Critical reading note**: absolute `t0` values are shifted by the causal filter's own group
delay plus the smoothing kernel's delay (confirmed on synthetic data: true injected onset 60ms
recovered as fit t0=197ms in absolute terms). **Only cross-area differences within the same
band are meaningful** — the systematic delay is identical across areas for a fixed band/filter,
so it cancels in every comparison this script actually reports (`pairwise`, `hierarchy_verdict`).
Do not quote a single area's `t0_ms` as a physiological latency in isolation.

**Result**: every band returns `H3_simultaneous_or_ambiguous` (Spearman rank correlation between
hierarchy position and onset time, p≥0.05 in all five bands). This is reported as the honest
result it is — not spun into a false discovery. High-gamma shows the tightest CIs and a
qualitatively plausible early-V1 pattern (rho=0.37, still not significant with n≤6 sessions/area).
**Per spec, an H3 result cannot by itself distinguish genuine simultaneous engagement from a
shared volume-conducted field — L6 is now not just next in the dependency graph but actively
required to interpret this result at all.**

Run `python L5_onset_latency_hierarchy.py --test` first: (a) a known injected onset LAG between
two synthetic areas must be recovered within tolerance (recovered 83ms vs 80ms true), (b) a
synthetic zero-lag case must return `discriminating: false` — the spec's own explicit acceptance
test.

Outputs: `L5.svg` / `L5.png` / `L5.pdf`, `L5_stats.json`, `L5_manifest.json`.
