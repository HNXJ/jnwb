# L6 — volume conduction control

Reads `canonical_pooling_method` from [L0](../L0_pooling_reconciliation/L0_stats.json), same gate
as L1-L5. Built because [L5](../L5_onset_latency_hierarchy/README.md) returned
`H3_simultaneous_or_ambiguous` for every band — per the spec's own text, that verdict alone
cannot distinguish genuine simultaneous engagement from a shared volume-conducted field, so L6 is
required to interpret L5's result, not just next in the dependency graph.

**Method** (both parts of the spec's two-pronged control, applied together and compared
separately):
- **(a) Bipolar/Laplacian re-referencing** — `jnwb.spectral.laplacian_reference`, already
  validated as this project's CSD estimator (L0 method (d), all of L4). Applied to a 5-channel
  block around one representative channel per area before coherence is computed, per
  `imaginary_coherency`'s own docstring ("callers are responsible for re-referencing... before
  calling this").
- **(b) Removing zero-lag components** — `jnwb.spectral.imaginary_coherency` itself. Its own
  docstring already identifies it as "the estimator this project's fig06/fig07 volume-conduction
  control requires."

`zero_lag_fraction = 1 - clip(icoh_abs_mean / sqrt(coh_mag_mean), 0, 1)` — an informal scalar
summary of `imaginary_coherency`'s own documented coh_mag-vs-icoh comparison, not a new estimator
or a formal variance decomposition. Stated as such in the stats JSON.

**Comparison design**: within-probe vs across-probe area pairs, resolved **fresh per session**
via `_l_lfp_common.find_probe_for_area` (probe↔area assignment is not fixed across sessions on
this corpus — see L0-L5 READMEs) rather than assumed from the pair identity. Pairs: V1-V2 and
MT-MST (within-probe on this corpus), FEF-PFC and V1-MT (always across-probe). Up to 3 sessions
per pair, stim condition (RRRR) only, broadband 4-80 Hz, one representative channel per area (not
full-area coverage) — all stated scope limits, not hidden.

## Result (descriptive, no formal test — n=3 sessions/pair)

| Pair | probe relation | zero-lag fraction (raw) | zero-lag fraction (CSD) | coh_mag (raw→CSD) |
|---|---|---|---|---|
| V1-V2 | within-probe | 0.82 | 0.43 | 0.332 → 0.006 (−98%) |
| MT-MST | within-probe | 0.31 | 0.47 | 0.252 → 0.123 (−51%) |
| FEF-PFC | across-probe | 0.70 | 0.43 | 0.048 → 0.008 (−82%) |
| V1-MT | across-probe | 0.60 | 0.51 | 0.092 → 0.007 (−92%) |

**No clean within-vs-across-probe separation** — reported honestly, not forced into the naive
expectation. MT-MST (within-probe) has the *lowest* raw zero-lag fraction of all four pairs and
retains the *most* coherence after Laplacian re-referencing (only −51%, vs −82% to −98% for the
other three), suggesting its raw coupling is comparatively less reference-driven. V1-V2 (also
within-probe) shows the opposite pattern: the highest raw zero-lag fraction and the largest
CSD-driven coherence collapse (−98%) of any pair. Across-probe FEF-PFC and V1-MT sit in between.
After CSD re-referencing all four pairs converge to a narrower zero-lag-fraction band
(0.43-0.51).

**Reading against L5**: three of the four pairs (V1-V2, FEF-PFC, V1-MT) lose the large majority
of their raw magnitude-squared coherence once Laplacian-referenced — consistent with (not proof
of) a substantial reference/volume-conduction contribution to raw cross-area LFP coupling on this
corpus, which is the kind of contamination that could make a genuine lead-lag onset difference
(L5) hard to detect. MT-MST is the exception. This does **not** by itself explain or resolve L5's
all-H3 result — it is one input to that reading, stated as such, not a conclusion drawn in code.

## Self-test

`python L6_volume_conduction_control.py --test`:
(a) a purely zero-lag shared synthetic source gives high `coh_mag`, low `icoh_abs`, high
`zero_lag_fraction` (0.973); (b) a genuinely 20ms-lagged shared source gives comparably high
`coh_mag` but much higher `icoh_abs` and a meaningfully lower `zero_lag_fraction` (0.364);
(c) independent noise gives low `coh_mag` for both. (d) Laplacian re-referencing reduces
`coh_mag_mean` for a common-average-reference-only synthetic artifact (0.871 → 0.010) — the
re-referencing half of the control actually removes what it claims to remove. Determinism also
checked.

Outputs: `L6.svg` / `L6.png` / `L6.pdf`, `L6_stats.json`, `L6_manifest.json`.
