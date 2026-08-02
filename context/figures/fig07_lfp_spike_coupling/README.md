# Figure 7 — spike-LFP phase coupling (PPC)

**Built 2026-07-30, corrected and extended same day.** `scripts/extract_spike_lfp_coupling.py`
runs corpus-wide in ~24.5 minutes (1,469 s, 15/15 readiness-gated sessions usable, 1,755 SUA
units, 78,400 area x band x context x unit results across 4 contexts, 6,000 same-electrode
exclusions applied) and `fig07_lfp_spike_coupling.py` draws the area x band summary and writes
stats. Both originally-required controls below were implemented as planned.

**Layer source corrected same day**: the first pass (9/15 sessions, 2 layer groups, inherited
from figure 6's extraction code) used `outputs/publication_visual_review/area_layer_tfr/layer_masks.json`,
believing it the only channel-level layer source. That was wrong — `outputs/layers/channel_layers_all.csv`
has a real 3-way (sup/mid/deep) split and covers all 21 sessions. Switched to it (same fix
applied to figure 6's shared `extract_lfp_coupling_matrices.py` module, which this script
imports from); usable sessions rose from 9 to 15 and units from 1,176 to 1,749.

## Method

**Pairwise phase consistency (PPC, Vinck et al. 2010)** between each SUA unit's spike times and
its own area's representative-channel LFP phase (band-passed + Hilbert), computed per trial
window and pooled — this is the bias-corrected estimator the original plan called for: PPC does
not rise with spike count the way raw vector strength or a Rayleigh z does, so areas/units with
more spikes are not spuriously favored.

**Same-electrode contamination control**: `peak_channel_id` (a corpus-wide global index, 0-511
across 4 probes — not the same as the unusable, entirely-`NaN` `local_channel` column) is
converted to a probe-local index, and any unit within `EXCLUDE_RADIUS=2` channels of the cell's
representative LFP channel is excluded from that cell's estimate (1,570 exclusions corpus-wide)
rather than silently included.

**Null**: spike-count-matched random-time resampling — for each real spike, the null draws a
phase from a uniformly random time within that spike's own trial window, preserving each
trial's phase content and per-trial spike count while breaking the true spike-to-phase pairing.

**Contexts**: same stimulus (p1, every condition) / omission (p2, RXRR only) windows as figure 6,
not the originally-scoped full band x area x layer x session grid across every condition —
scoped down to the two windows that isolate the omission manipulation itself, matching figures
4-6. Layer-resolved panels (not area-pooled) are not yet drawn; the layer-coverage-differs-by-
animal caveat in the original plan still applies whenever they are.

**Unit of inference**: session, not unit — many units in one session are not independent
replicates. Units are pooled to one session-level effect per area x band before any group test.

## Result, stated plainly

**No area x band effect survives correction at the group level** in either context (0/60 in
each of `fig07_omission`/`fig07_stimulus`, both Holm and BH-FDR — see `svg/fig07_stats.md`).
Same pattern as figure 6: individual sessions and units can show strong PPC well above their own
null (e.g. one MT unit reached z > 88 against its shuffle null during the stimulus window in a
pilot session), but it does not survive correction across sessions and must not be reported as
a finding from this figure alone.

## Multiplicity

Same convention as figure 6: the full area x band grid for one context is corrected together as
ONE family (30 tests per context here, after excluding area x band cells with fewer than 3
sessions), in one `write()` call, in one file — not split per band or per file the way
`fig04_laminar`/`fig05_area_by_band` were (flagged during the 2026-07-30 inventory review).

## A/B/R stimulus-identity question (phase 2, 2026-07-30)

Same construction as figure 6's identity comparison: "A/B/R identity" is which
stimulus-sequence family (AAAB-rooted / BBBA-rooted / RRRR-rooted) a trial's condition belongs
to. AXAB, BXBA, RXRR all have their omission at slot position 2, giving a matched three-way
comparison at the identical window; `identity_R` reuses the `omission` context (RXRR) rather
than re-extracting it. Coverage here is much better than figure 6's LFP-LFP version (spike-LFP
PPC only needs a unit + its own area's LFP, not a co-occurring second area): 25 of a possible
35 area x band cells (7 areas x 5 bands) were testable. **No effect survives correction**
(0/25, smallest raw p = 0.081, PFC alpha) — consistent with every other group-level test in
this figure and figure 6.

## Bugs found and fixed during the build (not left for a reader to discover)

- **Per-trial phase extraction, not a session-spanning slice**: an early version pulled one LFP
  slice from the earliest to the latest trial onset and band-filtered the whole thing — for
  trials spread across a session that slice can be most of the recording (confirmed: >1 GB RAM,
  3+ minutes with zero trials actually processed on one pilot session). Rewritten to extract and
  filter only the ~0.5-0.8 s around each trial (with edge padding so the filter's transient
  decays outside the window of interest), matching how figure 6's extraction works.
- **A no-op null construction caught before it shipped**: PPC is an aggregate statistic over the
  whole set of phases and does not depend on their order, so permuting an already-collected
  phase array (`phases[rng.permutation(...)]`) recomputes the identical PPC value every time —
  the null would have silently reported zero variance and a meaningless z-score. Replaced with
  the random-time-resampling null described above, which actually breaks the spike-to-phase
  relationship.
- **Vectorized across all shuffles at once**: `ppc_batch()` computes PPC for an
  `(n_shuffle, n_spikes)` array of resampled phases in one call instead of looping `ppc()` once
  per shuffle — the same fix figure 6 needed for its own null, for the same reason (a
  per-shuffle python loop did not finish one pilot session in 5+ minutes; vectorized, the full
  corpus took 6.4 minutes total).

## Not yet built

- Cross-area spike-LFP coupling (a unit's spikes against a DIFFERENT area's LFP) — current
  scope is within-area only.
- Layer-resolved (not area-pooled) panels.
- **Sliding-window connectivity ("phase 3", 2026-07-30, explicitly deferred until figures 1-5
  are reviewed as finalized)**: see `../PLAN_sliding_window_connectivity.md`. Same realignment
  and pooling logic as figure 6's plan, applied to PPC instead of imaginary coherency. Not
  started; do not begin without explicit direction.

Output: `fig07_lfp_spike_coupling.py` reads `outputs/spike_lfp_coupling/coupling.npz` (written
by `extract_spike_lfp_coupling.py`), draws `svg/fig07_omission_ppc.svg` (main figure) and
`svg/fig07_stimulus_ppc.svg` (feeds a supplement), assembles `fig07.svg`, writes
`svg/fig07_stats.md`/`.csv`.
