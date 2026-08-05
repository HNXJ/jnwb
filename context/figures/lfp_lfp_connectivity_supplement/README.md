# Figure 5 — LFP-LFP connectivity

**Renumbered and redesigned 2026-08-04.** This folder was `fig06_band_power_coupling/` and its
content (undirected, imaginary-coherency area x area coupling matrices) was originally figure 6.
Two changes landed the same day:

1. **Renumbering**: figures 5/6/7 were reorganized into modality order — LFP-LFP (5), SPK-SPK
   (6), LFP-SPK (7) — so this folder's content moved from slot 6 to slot 5.
2. **Demotion to supplement**: figures 4-7 are required to carry a group-level significant
   result (few exceptions), and this analysis does not — **0/240 area-pair x band cells survive
   Holm-Bonferroni or BH-FDR correction**, in either the omission or stimulus window (see
   `svg/supp_coherency_stats.md`). It is retained as `supp_lfp_lfp_coherency.py` /
   `supp_lfp_lfp_coherency.svg` — an honest null-result supplement, not deleted — and still
   feeds `figS22` (see `../build_supplements.py`). **Figure 5 itself is now a directed Granger
   LFP-LFP network** (`fig05_lfp_lfp_coupling.py`, built 2026-08-04) — directionality is a
   different statistical question from symmetric coherency and was chosen specifically because
   it has a chance of surviving correction where the symmetric measure did not. See that
   script's own section below for its design and result.

## Main figure: directed Granger LFP-LFP network (built 2026-08-04)

**New data product**: `scripts/extract_condition_band_power_trials.py` — per-trial (not
session-pooled) band-power dB time series, session x area x band x condition (RXRR, RRRR),
same window/baseline/channel conventions as `extract_condition_tfr_maps.py` (-500..+2593 ms
re: p1, middle-of-d1 baseline per channel) but keeping the trial axis intact, since
`jnwb.connectivity.granger()` fits its AR model with rows stacked over trials. Output:
`outputs/condition_band_power_trials/trials.npz`.

**Method**: `jnwb.connectivity.directed_network()`, `method='granger'` (`order='auto'` by BIC,
`max_lag=10`, `zscore` detrend — the estimator's own defaults, not tuned per result), run per
(session, band, condition) over every area present, on the FULL trial window (not just the p2
sub-window) since more within-trial samples help the automatic lag-order selection and "the
LFP-LFP network across the whole trial" is the primary question here.

**Statistics**: unit of inference is session, not the within-session analytic F-test p-value —
many single-session fits carry non-stationarity/residual-autocorrelation diagnostic warnings
(expected for a short, event-related, non-stationary LFP segment), so those are not trusted as
the group claim (see `n_warnings`/`diagnostics_warning_rate` in
`outputs/lfp_lfp_granger_network/receipt.json`). Three families, each corrected together
(Holm + BH) across the full directed-edge x band grid: `fig05_RXRR` and `fig05_RRRR` (is net
directionality, across sessions, different from zero within one condition) and `fig05_delta`
(does net directionality differ RRRR vs RXRR, paired by session — the connectivity analogue of
fig04/05-hierarchy's own p2 RXRR-vs-RRRR power contrast).

**Result (run completed 2026-08-04 22:00, 22 sessions, 220 `directed_network()` calls, 301s):
also null.** 0/150 tests survive Holm-Bonferroni across all three families (`fig05_RXRR`,
`fig05_RRRR`, `fig05_delta`) — see `svg/fig05_stats.md` and
`outputs/lfp_lfp_granger_network/receipt.json`. The smallest p in the entire grid is
`low_gamma MT<->TEO net directionality, RRRR vs RXRR` at raw p=0.0077, p_holm=0.38 (n=9
sessions) — a candidate worth another look with more power, not a finding. **Directionality did
not turn out to carry information the symmetric coherency measure lacked, on this corpus.**
`diagnostics_warning_rate` in the receipt is 1.0 — every single-session Granger fit carried a
non-stationarity or residual-autocorrelation diagnostic warning, consistent with this being a
short, strongly evoked (non-stationary-by-design) LFP segment; this doesn't invalidate the
group-level test (which uses session-level point estimates, not the within-session p-values —
see STATISTICS above) but it's a second reason not to over-read any single edge.

**A third method, transfer entropy, was also tried (2026-08-04/05) and is also null.**
`scripts/compute_lfp_lfp_te_network.py` (`n_surrogates=15`, a disclosed runtime/validity
compromise — the estimator's own default of 200 is computationally impractical at this network
size, see that script's docstring) ran the full grid in 88 minutes (22 sessions, 3100 edge
rows). `scripts/aggregate_lfp_lfp_te_stats.py` computes the same three-family group-level test
as the Granger network: **0/150 survive Holm-Bonferroni** — see `svg/fig05_te_stats.md`.

**All three LFP-LFP connectivity methods attempted on this corpus now agree: null at the group
level.** Imaginary coherency (0/240), directed Granger causality (0/150), and transfer entropy
(0/150). This is a real, consistent, three-times-replicated negative result, not a single
underpowered attempt — per [[feedback-figures-require-significance]], fig05's main-figure slot
needs a different kind of content, not a fourth connectivity method. Flagged to the user
2026-08-04 for the pivot decision (most likely candidate: the already-significant, already-
replicated V3a/d beta elevation vs V1 — see `CLAUDE.md`'s omission-a status). All three
connectivity analyses are preserved here as real, honestly-reported supplement content, not
discarded.

**Durable intermediate results** (per "save analysis results as we continue"):
`outputs/condition_band_power_trials/trials.npz` (per-trial band power, checkpointed once at
the end of the extraction run) and `outputs/lfp_lfp_granger_network/edges.csv` (every directed
Granger edge, checkpointed after every session during computation, so a partial run's work is
never lost) are both real, inspectable data products independent of this figure's own
rendering — reusable for figS22-style supplements or a future robustness check (PSI/TE) without
re-running the extraction.

## Supplement: undirected imaginary-coherency coupling (originally figure 6, built 2026-07-30)

**Built 2026-07-30, corrected same day.** `scripts/extract_lfp_coupling_matrices.py` runs
corpus-wide in ~142 s (15/15 readiness-gated sessions usable, 4,560 area/layer-pair x band x
context results) and `supp_lfp_lfp_coherency.py` draws the matrices and writes stats. The
estimator and re-referencing primitives this depends on were built and validated the day before
— see `jnwb.spectral.imaginary_coherency`, `laplacian_reference`, and
`scripts/validate_imaginary_coherency.py`.

**Layer source corrected same day**: the first pass (11/15 sessions, 2 layer groups) used
`outputs/publication_visual_review/area_layer_tfr/layer_masks.json`, believing it to be the
only channel-level layer source in the corpus. That was wrong — found via an unrelated
background search — `outputs/layers/channel_layers_all.csv` has a real, data-driven 3-way
(superficial/mid/deep) split AND covers all 21 sessions (`layer_masks.json` covered only 15
probe-sessions and entirely lacked every V182o session). Switched to it; all 15 readiness-gated
sessions are now usable, and the 3-layer plan originally scoped for this figure is restored
instead of the 2-layer downgrade.

## Result, stated plainly

**No area-pair x band coupling effect survives correction at the group level**, in either
context (0/240 survive Holm-Bonferroni, 0/240 survive Benjamini-Hochberg FDR, in both the
omission-window and stimulus-window families — see `svg/supp_coherency_stats.md`). This is despite
individual sessions showing very strong single-session effects (e.g. MT-MST gamma/beta coupling
during the stimulus window reached z > 20 against its own shuffle null in one pilot session) —
the corpus-level test does not inherit that strength because only a handful of sessions carry
any given area x layer pair, and the effect size varies enough session-to-session that the
paired (by session) test washes it out. This is the same pattern the project has already
documented for LFP band power itself (no direction shared across animals) — read as a real
finding about session-to-session variability, not a pipeline defect. Do not report a specific
area pair as "coupled" from this figure without checking `supp_coherency_stats.md`'s `p_holm`/`q_bh`
columns first.

## A/B/R stimulus-identity question (phase 2, 2026-07-30)

"A/B/R identity" turns out to mean which stimulus-SEQUENCE FAMILY a trial's condition belongs
to (AAAB-rooted / BBBA-rooted / RRRR-rooted -- see `scripts/classify_omission_units_grand.py`'s
`OMISSIONS` dict), not a raw per-trial visual identity independent of condition. AXAB and BXBA
are the A- and B-family conditions whose omission falls at the SAME slot position (2) as RXRR,
giving a directly matched three-way comparison at the identical window (1.031-1.562 s).
`identity_R` reuses the already-extracted `omission` context (same condition, same window) —
not re-run.

**Result: extremely sparse coverage, one testable area pair.** Of 45 possible area pairs, only
**MST-PFC** had >=3 sessions with all three identities present (12 sessions for that pair, 5
tests -- one per band). None reach significance (smallest p = 0.105, alpha band). A/B-family
trials are far rarer in this corpus than the R ("maximum entropy") family per the archived
script's own framing, so most area pairs simply lack enough A/B-family data to test at all --
reported as a coverage limit, not folded into "no effect."

## Multiplicity, done correctly this time

The inventory review (2026-07-30) found that `fig04_laminar` and `fig05_area_by_band` reuse an
identical family name across 4 separately-corrected files (10 tests each) rather than one true
joint family — harmless on that data (no p-value was close to significant either way) but
architecturally unsound. Here the full area x area x band grid for one context (up to 45 pairs
x 5 bands = 225 possible tests, 120 actually computed once pairs with fewer than 3 co-occurring
sessions are excluded) is corrected together as ONE family, in one `write()` call, in one file
— the two contexts are reported as two separate families since they ask different questions,
not folded together.

## What exists to build on (surveyed 2026-07-29, see `.lab/fig06_coupling_estimator_built_20260729.json`)

- **Channel-level layer source, as understood on 2026-07-29 (superseded the next day)**:
  `outputs/publication_visual_review/area_layer_tfr/layer_masks.json` — per
  `session_id|probe_letter`, `superficial_mask`/`deep_mask` boolean arrays from a spectrolaminar
  alpha/beta/gamma crossover, believed to be the only channel-level layer source, with no
  data-driven middle group. User confirmed 2026-07-29 to use 2 layers on that basis. **This was
  wrong**: `outputs/layers/channel_layers_all.csv` has a real 3-way (sup/mid/deep) split and
  covers all 21 sessions — found 2026-07-30 via an unrelated background search, and the figure
  was rebuilt on it the same day (see the top of this file). Kept here for the record of what
  was actually known at each decision point, not as current guidance.
- **Channel-level area source**: `jnwb.session.lfp_channel_areas()` (electrode-table `location`
  string parse) and `outputs/channel_area_vector/channel_area_vector.csv`.
- **No existing per-channel continuous LFP loader** — raw traces must come from direct h5py
  access to `acquisition/probe_X_lfp/.../data` (the project's own sanctioned pattern for LFP,
  per `.agents/skills/jnwb-core/SKILL.md`), loading channel slices rather than the whole array.
- **`extract_condition_tfr_maps.py` / `condition_tfr_maps_p1d1p2d2p3/maps.npz` is not usable
  input** — confirmed trial- and channel-pooled (sums/counts per session|area|layer|cond only),
  no per-channel or per-trial resolution survives. Coupling needs per-channel time series, so
  this figure needs its own extraction pass, not a reuse of that one.
- **jrsa.py** has real, reusable permutation/FDR/stats scaffolding (`stats=True`,
  `permutations=`, `correction=`) if a coupling metric is registered into its dispatch table or
  its stats helpers are called directly on externally-computed values.

## Extraction plan (as drafted 2026-07-29 -- step 4's layer source and count are superseded, see above)

1. **Session gate**: `artifacts/data/session_readiness.csv`, `nwb_ok` and `sidecar_ok` true,
   same gate every other figure in this pipeline uses.
2. **Per session, per probe**: load raw per-channel LFP via h5py (channel slices, not whole
   array — memory footgun already documented in `.agents/skills/jnwb-tfr/SKILL.md`).
3. **Re-reference before anything else**: `laplacian_reference()` (preferred — retains channel
   count, cancels shared-reference/volume-conducted signal identical on neighboring contacts)
   in depth order per probe. `bipolar_reference()` available as the alternative if a reviewer
   wants the more conservative adjacent-difference construction; both are validated.
4. **Assign area (10 areas) and layer** to each re-referenced channel via `lfp_channel_areas()`
   + a channel-level layer source. *(As built: 3 groups -- sup/mid/deep -- via
   `outputs/layers/channel_layers_all.csv`, not the 2-group `layer_masks.json` this step
   originally named; see "Layer source corrected same day" above.)*
5. **Per condition-event pair**: p1/p2/p3 stimulus windows, the omission window (RXRR's omitted
   p2), and the delay windows, each against the middle-of-d1 baseline already established by
   `extract_condition_tfr_maps.py` (706-856 ms from p1) — reuse that baseline definition for
   consistency across figures 4/5/6.
6. **Coupling matrix**: for every (area, layer, band) x (area, layer, band) pair, per session,
   per condition-event, compute `imaginary_coherency()` between one representative channel (or
   a small channel set, TBD against how many channels typically share an area x layer cell) per
   cell — needs a decision on within-cell channel pooling (average channels first, or average
   coupling values after) before the full corpus runs; average-after is preferred by default
   since averaging coupling values (not raw signals) preserves each channel pair's own phase
   relationship, but this should be sanity-checked on one session before committing corpus-wide.
7. **Null**: trial-shuffled surrogates preserving per-channel spectra (shuffle trial-to-trial
   pairing between the two channels/areas while keeping each channel's own within-trial spectral
   content) — report observed-minus-null difference and its exact interval, not the raw
   coupling value alone.
8. **Unit of inference**: session, not channel pair. A matrix built by pooling channel pairs
   within one session describes that session; group-level claims aggregate over sessions.
9. **Multiplicity**: the full matrix is one family, Benjamini-Hochberg controlling FDR across
   it, Holm-Bonferroni reported alongside for the family-wise guarantee — same dual-reporting
   convention as every other figure's `figstats.write()`.
10. **A/B/R identity question** — built 2026-07-30 (see "A/B/R stimulus-identity question"
    above), once the coupling-vs-null pipeline was reviewed as planned here.

## Decisions resolved during the build (2026-07-30) — differ from the original plan above

- **Representative channel, not all-pairs-averaged**: chosen for tractability. An early
  implementation called `imaginary_coherency()` fresh for every one of 200 shuffle
  iterations per pair-band-context and took 257 s for a 3-cell pilot session (would not have
  scaled to the corpus in reasonable time). Rewritten as a vectorized trial-based estimator
  (`trial_band_fft` + `coupling_with_null_vectorized` in `extract_lfp_coupling_matrices.py`):
  one rFFT per trial per channel, Pxx/Pyy computed once (order-independent under trial
  shuffling), only the cross-term Sxy re-paired per shuffle — full corpus in 56 s at
  N_SHUFFLE=1000. All-pairs-averaged remains future work if representative-channel results
  need a robustness check.
- **Two contexts, not the originally planned five windows**: **stimulus** (p1, 0-531 ms,
  present in every condition) and **omission** (p2, 1031-1562 ms, RXRR only) — the two
  windows that isolate the omission manipulation itself, matching what figures 4/5 already
  established as the scientifically load-bearing comparison. d1/d2/p3/delay windows are not
  yet extracted; add as additional `CONTEXTS` entries if needed later.
  Not baselined to middle-of-d1 the way figures 4/5's power ratios are — coherency is already
  a normalized [-1, 1] quantity per se, and comparing it against its own trial-shuffle null
  serves the same "don't take a raw magnitude at face value" purpose a baseline serves for
  power.
- **Trial-averaged cross-spectrum, not concatenate-then-Welch**: standard estimator for
  event-related data (average the complex cross-spectrum across trials rather than
  concatenating short windows and running Welch on the whole thing) — also what made the
  vectorized null tractable in the first place.

## Not yet built

- Layer-resolved (not area-pooled) main-figure panels — `svg/supp_coherency_omission_matrices.svg` and
  its stimulus-window counterpart pool superficial+deep per area for readability; per-layer
  matrices exist implicitly in `coupling.npz` (keyed down to layer) but have no drawn panel yet.
- All-pairs-averaged construction as a robustness check against the representative-channel choice.
- A dedicated identity-comparison figure panel (matrices for identity_A/identity_B side by side)
  — currently only the stats family exists; given only one area pair is testable, a panel was
  judged not worth the space yet. Revisit if a future data addition improves A/B-family coverage.
- **Sliding-window connectivity ("phase 3", 2026-07-30, explicitly deferred until figures 1-5
  are reviewed as finalized)**: see `../PLAN_sliding_window_connectivity.md`. Realigns
  RXRR/RRXR/RRRX (and the A- and B-family equivalents) to the real stimulus immediately before
  each one's own omission, pooling them into one larger per-family trial set instead of RXRR
  alone, and computes coherence/correlation on a 400 ms sliding window (100 ms step) across
  [-400, 2000] ms instead of two fixed snapshots -- a time-resolved "connectivity video." Not
  started; do not begin without explicit direction.

Output (supplement): `supp_lfp_lfp_coherency.py` reads
`outputs/lfp_coupling_matrices/coupling.npz` (written by `extract_lfp_coupling_matrices.py`),
draws `svg/supp_coherency_omission_matrices.svg` and `svg/supp_coherency_stimulus_matrices.svg`
(the latter feeds `figS22`), assembles `supp_lfp_lfp_coherency.svg`, writes
`svg/supp_coherency_stats.md`/`.csv` via `figstats.write()`.
