# Figure 6 — SPK-SPK connectivity

Second of the three connectivity-modality figures built 2026-08-04 (LFP-LFP fig05, SPK-SPK
fig06, LFP-SPK fig07), same directed Granger-causality engine and design as
`fig05_lfp_lfp_coupling/fig05_lfp_lfp_coupling.py` — see that script's own docstring for the
shared statistical rationale.

## Data source

`scripts/extract_condition_spike_trials.py` (new 2026-08-04) → `outputs/condition_spike_trials/
trials.npz` — per-trial, per-area10 **population-pooled** spike-rate (Hz) time series, RXRR vs
RRRR, p1-aligned, same window (-500..+2593 ms) and 10 ms bins as fig05's LFP input so the two
networks share identical nodes and time base. All units in `omission_grand_units.csv` per
session contribute (quality 0 and 1 both — a population-rate connectivity node is not the same
use case as a single-unit classification claim; restricting to quality==1 would silently thin
some areas more than others).

**Bug caught before the full run counted as final**: the first extraction attempt silently
processed only 11 of 21 sessions (92 keys) because the NWB filename pattern assumed a uniform
`..._rec.nwb` suffix — true for C31o/V198o sessions but not V182o (`sub-V182o_ses-260629.nwb`,
no `_rec`). Confirmed by listing `D:/analysis/nwb` directly, not by inspection of the code
alone. Fixed to try both suffixes; re-run recovered all 10 missing V182o sessions (166 keys, 21
sessions).

## Method

`jnwb.connectivity.directed_network()`, `method='granger'` (`order='auto'` by BIC, `max_lag=10`,
`zscore` detrend — identical settings to fig05, not re-tuned per result). One
`directed_network()` call per (session, condition) — no band dimension, spikes have none — over
every area present (up to all 10). 42 calls across 21 sessions, 56s runtime.

## Statistics

Same three-family design as fig05: `fig06_RXRR` and `fig06_RRRR` (net directionality != 0
within one condition, paired by session vs zero) and `fig06_delta` (RRRR vs RXRR paired
difference), corrected together (Holm + BH) across the full directed-edge grid per family.
`diagnostics_warning_rate` = 0.70 (70% of individual session-level Granger fits carried a
non-stationarity or residual-autocorrelation diagnostic warning — lower than fig05's 100%, but
still substantial; the group-level test uses session-level point estimates, not these
within-session p-values, so this doesn't invalidate the result, but any single edge's raw p is
descriptive only).

## Result, stated plainly

**Also null.** 0/45 tests survive Holm-Bonferroni across all three families. Smallest raw p:
`MT<->TEO` net directionality, RXRR (p=0.036, p_holm=0.32, n=8) and RRRR (p=0.050, p_holm=0.45,
n=8) — the same area pair, both conditions, in the same direction. Descriptively interesting
(and notably, `MT<->TEO` was also fig05's smallest-p edge, `low_gamma` band, RRRR-vs-RXRR
delta) but neither survives correction and this is not reported as a finding.

**This is the third of three connectivity methods attempted on this corpus (as of 2026-08-04)
to come back null at the group level for a figures-4-7 slot**: LFP-LFP imaginary coherency
(0/240), LFP-LFP directed Granger (0/150), SPK-SPK directed Granger (0/45). Per
[[feedback-figures-require-significance]], flagged to the user rather than silently accepting a
null main figure or launching a fourth expensive method (e.g. transfer entropy, already running
for fig05 as a multi-hour job) without a decision on strategy.

## Output

`fig06_spk_spk_coupling.py` reads `outputs/condition_spike_trials/trials.npz`, writes
`outputs/spk_spk_granger_network/edges.csv` (checkpointed per session) and `net_directionality.
csv`, draws `svg/fig06_rxrr_network.svg` / `svg/fig06_rrrr_network.svg`, assembles `fig06.svg`,
writes `svg/fig06_stats.md`/`.csv` via `figstats.write()`.
