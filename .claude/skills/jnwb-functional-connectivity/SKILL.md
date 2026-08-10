---
name: jnwb-functional-connectivity
description: |
  Functional connectivity and network analysis using jnwb. Covers directed
  connectivity (Granger/PSI/transfer entropy), undirected LFP-LFP coupling
  (imaginary coherency), spike-LFP and spike-spike relationships, and the
  omission-a project's own hard-won statistical design for making any of
  these actually find something on this corpus (see "Statistical design"
  below before building anything -- six methods failed 2026-08-04/05 by
  skipping it).
---

# jnwb-functional-connectivity: directed/undirected connectivity + this corpus's statistics

Module root: `jnwb/` (repo root: `oa.paths.REPO_ROOT`). Two real, current modules:
`jnwb/connectivity.py` (directed estimators, modality-agnostic) and
`jnwb/spectral.py` (undirected LFP-LFP coupling + re-referencing). **Both were
substantially rewritten 2026-08-03/04** -- if you have an older memory of this
package claiming "no coherence function exists" or citing `granger_causality`
as the way to do Granger, that memory is stale; re-read this file.

## Statistical design: test within-session first, pool after (read this before building anything)

**On this corpus, pooling raw session-level point estimates across sessions/subjects and
testing that pool directly manufactures false negatives.** Confirmed the hard way
2026-08-04/05: six connectivity methods (imaginary coherency, directed Granger, transfer
entropy, PPC, directed SPK-SPK Granger) were each built with a real, validated within-session
shuffle null, and each found enormous single-session effects (z > 20-88) -- but every one of
them came back null (0/45 to 0/240 significant) when the *group-level* test pooled raw
per-session point estimates and ran a single t-test/Wilcoxon on the pool. This corpus has
independently documented, large, real, **opposite-signed** between-animal variability in raw
LFP band power -- pooling before testing treats that variability as noise to average over, and
on this corpus it is large enough to erase a real within-session effect before the group test
ever sees it.

**The corrected design** (explicit user instruction, 2026-08-05 -- see
`feedback_pool_after_testing_not_before` memory for the full incident writeup):

1. Per session, per pair (channel/unit/area), compute the coupling/correlation metric AND a
   trial-shuffle permutation null WITHIN that session -- there are enough trials in one session
   for real power here. `scripts/extract_lfp_coupling_matrices.py` and
   `scripts/extract_spike_lfp_coupling.py` already have this exact null-construction pattern,
   vectorized across all shuffles at once (a naive per-shuffle Python loop did not finish one
   session in 5+ minutes on this corpus) -- reuse it, don't reinvent.
2. Only after every session has its own significance decision, pool ACROSS sessions/subjects as
   a **proportion/hit-rate** question ("in how many of N sessions was this pair significant?"),
   tested with an **exact binomial (Clopper-Pearson) interval** against the expected false-
   positive rate -- not a t-test on the raw pooled point estimates. This project's own
   statistical doctrine already prefers Clopper-Pearson for exactly this kind of proportion.
3. Scope order for a new relationship (LFP-LFP, LFP-SPK, or SPK-SPK): (a) within session, within
   probe/area, (b) within session, between probe/area, (c) generalize across sessions --
   accepting that not every area combination is recorded in every session (partial coverage is
   fine, pool over whichever sessions have that specific pair).
4. **PPC is retired as the spike-LFP method** (explicit instruction, it was null anyway). The
   current direction for spike-LFP is trial-level correlation between a channel's band power
   and a unit's/population's spike rate/count in the same sliding window -- same design as
   LFP-LFP and SPK-SPK, just swap which side is "spikes" vs "power." A sliding-window
   trial-realignment plan for pooling RXRR/RRXR/RRRX (and A-/B-family equivalents) into one
   larger per-family trial set already exists at
   `context/figures/PLAN_sliding_window_connectivity.md` -- read it before rebuilding that
   realignment logic from scratch.

## Directed connectivity (`jnwb/connectivity.py`, current, built 2026-08-03/04)

Modality-agnostic: LFP, binned spikes, MUAe, band-power time courses all go through the same
`(n_trials, n_times)` contract via `as_trials()`. No modality-specific arguments.

```python
from jnwb.connectivity import (
    granger, granger_spectral, phase_slope_index, transfer_entropy,
    directed_connectivity, directed_network, bin_spikes, as_trials,
)

# One estimator, X -> Y and Y -> X in one call
res = granger(x, y, order='auto', max_lag=10, detrend='zscore')
# res.x_to_y, res.y_to_x, res.net (=x_to_y - y_to_x), res.p_x_to_y, res.p_y_to_x
# res.diagnostics['warnings']: non-empty means do NOT read the number as biological
# directionality for that pair (non-stationarity / residual autocorrelation) -- this fires
# often on short, strongly evoked LFP segments; it does not invalidate a session-level test
# built on the point estimate (see "Statistical design" above), only a single-pair p-value.

# All-pairs network over N areas/units at once, with FDR across the edge family
net = directed_network({"V1": v1_sig, "PFC": pfc_sig, "MT": mt_sig}, method="granger")
# net['matrix'] (row->col influence, diag NaN), net['p_matrix'], net['q_matrix'], net['labels']

# Bridge spike times into the same (n_trials, n_bins) contract
binned = bin_spikes(spike_times, window=(-0.5, 2.593), bin_size_ms=10.0,
                    trial_starts=trial_onsets_sec, output="rate")
```

`method=` for `directed_connectivity`/`directed_network`: `'granger'`/`'gc'`,
`'granger_spectral'`/`'sgc'` (Geweke band-resolved decomposition of the same VAR --
band-passing the input first and calling plain `granger` does NOT give band-resolved
directionality, the VAR itself must be decomposed), `'psi'`/`'phase_slope_index'`,
`'te'`/`'transfer_entropy'`. **TE is expensive**: default `n_surrogates=200` makes even a
5-area all-pairs network impractically slow (confirmed: one 5-area, one-band, one-condition
call did not finish in 2 minutes). `n_surrogates=15-30` is a disclosed runtime/validity
tradeoff used on this corpus (see `scripts/compute_lfp_lfp_te_network.py`) -- state the tradeoff
explicitly if you reduce it further, don't silently pick a fast setting.

Legacy `granger_causality` (line ~393), `spike_mutual_information`, `network_topology` still
exist and are untouched -- prefer the `granger`/`directed_network` family above for new work
(more complete diagnostics, session-nesting-aware, validated against a mock corpus in
`c662af2`'s test suite) unless there's a specific reason to use the legacy API.

## Undirected LFP-LFP coupling + re-referencing (`jnwb/spectral.py`, current, built 2026-07-29)

```python
from jnwb.spectral import imaginary_coherency, laplacian_reference, bipolar_reference, band_power
```

`imaginary_coherency()` -- zero-lag-mixing-insensitive coupling (Nolte et al. 2004); real,
validated (`scripts/validate_imaginary_coherency.py`) against synthetic zero-lag-mixing vs.
true-lag cases. `laplacian_reference()` / `bipolar_reference()` -- re-reference a probe's
channels in depth order BEFORE computing coupling (volume conduction otherwise inflates
apparent coupling between nearby contacts); Laplacian preferred (retains channel count),
bipolar is the more conservative adjacent-difference alternative. Both exist and are used by
`scripts/extract_lfp_coupling_matrices.py`.

## Mutual information (spike-to-spike, unchanged from earlier versions of this skill)

```python
mi = oa.spike_mutual_information(spike_times1, spike_times2,
                                 time_window=(0.0, 3.0), bin_size_ms=10.0)
```

## JRSA (`jnwb/jrsa.py`) -- unified similarity/relationship engine, unchanged

Still real, still has `granger`/`phase_slope`/`cka`/`rsa`/etc. in its `_METRIC_DISPATCH` table
plus generic permutation/FDR stats. Worth using for a quick one-off multi-dimensional
similarity check; the `connectivity.py` functions above are the better-tested choice for
anything that will end up in a figure, since they carry this corpus's own diagnostic checks
(stationarity, residual autocorrelation) that JRSA's dispatch entries do not.

## Output storage

Connectivity outputs → `outputs/` (e.g. `lfp_lfp_granger_network/`,
`spk_spk_granger_network/`, `lfp_lfp_te_network/`, `lfp_coupling_matrices/`,
`spike_lfp_coupling/`). Figures → `context/figures/fig05_*`, `fig06_*`, `fig07_*`,
`lfp_lfp_connectivity_supplement/` (see `context/figures/README.md` for current figure-to-folder
mapping, which changes -- check it before assuming a figure number's content from memory).
