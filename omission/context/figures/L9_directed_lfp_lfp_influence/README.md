# L9 — directed LFP-LFP influence (Granger causality + phase-slope index)

Reads `canonical_pooling_method` from [L0](../L0_pooling_reconciliation/L0_stats.json), same gate
as L1-L8. Depends on [L7](../L7_cross_area_power_correlation/README.md) (node/pair framework) and
[L8](../L8_cross_area_coherence/README.md) (node-key-collision fix, inherited from the start here
rather than rediscovered).

**Method**: `jnwb.connectivity.granger_spectral` (Geweke frequency-resolved GC) and
`jnwb.connectivity.phase_slope_index` (PSI, volume-conduction-robust by construction), both
reused verbatim — no new directed-connectivity estimator written. `granger_spectral`'s
`n_surrogates` trial-shuffle null **is** the within-session shuffle null omission-signal §10
requires; not rebuilt separately. One representative channel per (area, layer) node, same
limitation L6/L8 already state.

**SNR-matched subsampling control** (spec's own explicit caution — "GC is sensitive to differing
SNR between conditions... without it a GC asymmetry is uninterpretable"): both conditions are
subsampled, seeded, without replacement, down to `min(n_trials_stim, n_trials_omission)` *before*
either condition's GC/PSI is computed, so a stim-vs-omission difference cannot be a trial-count
artifact.

**Directed asymmetry index**: `net = x_to_y - y_to_x` (GC) or the PSI value itself (antisymmetric
by construction). Both directions also reported separately, per spec.

## Bug found and fixed (pseudoreplication in the CI, not a figure bug this time)

A single session can contribute **multiple node-pair instances to the same (area, layer)
identity** — e.g. `sub-V182o_ses-260702` records FEF on two different probes, so both the
within-probe-A pair and the within-probe-B pair collapse to the same identity string
`"FEFsup-FEFdeep"`. The first aggregation pass bootstrapped over these raw instances directly,
so one session could silently count as 2–3 "sessions" in the CI (confirmed: `FEFsup-FEFdeep`
showed `n_sessions=5` from only 3 real sessions) — exactly the channel-vs-session inflation
`omission-statistics` warns against, just at the pair-instance level instead of the channel
level. Fixed by averaging a session's own pair instances to **one point estimate per session**
before bootstrapping over genuine session replicates. Caught before publication, not after —
the raw per-session-per-pair numbers in `L9_stats.json`'s `sessions` tree were correct all
along; only the `pairs_across_sessions` aggregation needed the fix, and it was reapplied
directly against the already-computed real-data output (no need to rerun the ~19-minute GC
computation).

## Result (descriptive — no claim asserted in code)

- **`FEFsup-FEFdeep` (same-probe, adjacent depth) is the only pair with a genuine 3-session
  replicate and a CI that excludes zero**: theta net = −0.174 [−0.286, −0.099] (stim), −0.158
  [−0.238, −0.016] (omission) — i.e. FEFdeep Granger-causes FEFsup more than the reverse,
  consistently across all 3 sessions. **Read with extra caution**: this is exactly the pair type
  [L6](../L6_volume_conduction_control/README.md),
  [L7](../L7_cross_area_power_correlation/README.md), and
  [L8](../L8_cross_area_coherence/README.md) all independently flag as volume-conduction-
  dominated. SNR-matched trial-count subsampling addresses one confound (unequal trial counts
  between conditions) but does **not** address a within-pair channel-SNR asymmetry (one channel
  closer to a shared true source than the other), which is a well-known way for GC between two
  channels of a mixed field to show a spurious directional asymmetry that is not real
  intracortical influence. This finding should not be read as feedforward/feedback evidence
  without that caveat in the manuscript text.
- The two largest-magnitude net asymmetries (`PFCsup-PFCdeep`, `MSTsup-MSTdeep`) have wide CIs
  crossing zero (`PFCsup-PFCdeep`, n_sessions=2) or are single-session point estimates with a
  **degenerate, non-informative CI** (`MSTsup-MSTdeep`, n_sessions=1) — stated explicitly in the
  stats JSON's `ci_note`, not presented as more certain than they are.
- No systematic alpha/beta-omission vs gamma-stim asymmetry pattern (the spec's predicted
  feedback/feedforward signature) is visible across the cross-area (non-same-probe) pairs in this
  small, single-subject (V182o), 3-session sample — reported as the actual, unremarkable pattern,
  not spun into a null-result narrative either.
- `granger_spectral`'s `p_surrogate` is **broadband-derived and identical across every band**
  within one call (documented limitation of the underlying function, not this script) — stated
  explicitly, not treated as an independent per-band significance test. `phase_slope_index`'s
  per-band jackknife `z` is genuinely per-band and is reported separately (`psi_z` in the stats
  JSON) for readers who want a per-band significance proxy.
- Zero GC or PSI diagnostic warnings across all 90 computed pair-conditions (`spectral_radius <
  1`, no non-stationarity flags) — the VAR fits are numerically well-behaved throughout.

## Self-test

`python L9_directed_lfp_lfp_influence.py --test`: synthetic bivariate AR system where X drives Y
with a 2-sample lag (Y[t] += 0.6·X[t-2]) but not the reverse — GC net recovered +0.600 (want >0),
PSI recovered +1.17 (want >0, X leads Y) — PASS. An independent AR(1) control shows GC net ≈0.000,
well below the driven system's magnitude — PASS. SNR-matched subsampling equalizes (50, 30) trial
counts to (30, 30) while preserving X/Y trial pairing within each condition — PASS. Determinism
also checked.

Outputs: `L9.svg` / `L9.png` / `L9.pdf`, `L9_stats.json`, `L9_manifest.json`.
