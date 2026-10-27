# Roadmap

Work deferred past the cycles the todo stack holds, one row per item. An item moves into the
todo stack, with its full text, when its cycle opens; it is never in both files.

A row is `| id | theme | defect | waits | deferred-X.Y.Z |`: the item id, a short theme, the
defect in one line, the reason it waits (AGENTS.md section 11), and the cycle it is deferred to,
later than the declared version. `scripts/release_gate.py` STEP 0a refuses any row that breaks
this form, and `scripts/fact_gate.py` counts each row's id as a live item. Rows are grouped by theme;
within a theme they run in the order listed, dependencies first. A theme ending in `(validation)`
marks a validation, which the dashboard lists as not started.

The full text of each item carried here from the todo stack is in
`artifacts/archive/0.2.10/todo_stack_0.2.10.md`, the stack as it stood when this file opened.

## Laminar validation

Ground truth for vflip2, xflip's null and the curation path.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
| 15-11 | `vflip2` recovers a planted vFLIP2 crossover on Andre Bastos's simulation code (validation) | The generator half landed in 1dbcedbf (`artifacts/evidence/0.2.13/vflip2_recovery.md`: recovery 29 of 100, matched null 24 of 100); the same table has not run on his code, under the contract in `artifacts/evidence/0.2.13/vflip2_generator_design.md`; full text: `git log -S '### 15-11' -- artifacts/todo_stack.md`. | His simulation code; nothing shipped changes. Moved to 0.2.15 (ruled 2026-10-19). | deferred-0.2.15 |
| 16-12 | Dashboard real-data cards for `isi_cv` (9,056 units), WaveMAP and the omission results (validation) | The dashboard ships with the four committed GLO entries; the others need a receipt computed without calling jnwb: the omission and WaveMAP receipts record jnwb calls (`jnwb_version`, `jnwb_wavemap_commit`), and the `isi_cv` receipt file (branch `claude/site-overview-326890`, commit 9b52c5e7) no longer exists | Independent recomputations with committed receipts; nothing shipped changes. Moved to 0.2.15 (ruled 2026-10-23). | deferred-0.2.15 |
| 11-03 | Design facts held | D1-D3, D5-D10 report UNHELD: no scan reads delegation or side-effect categories (D1-D3), `AmbiguousMappingError` and `UndeclaredUnitError` are exported and never raised (D5, D7, D9), and no test holds condition meaning, trial semantics or cache decisions (D6, D8, D10) | Ruled 2026-10-26: each needs its own scan or refusal with a planted case; D4 and D11 are held | deferred-0.2.15 |
| 17-57 | Paper, library and methods verdicts on the dashboard | Each showcase replication carries one verdict and no numeric paper value, where jaxfne splits the verdict into paper, library and methods | Ruled 2026-10-26: one verdict per replication in 0.2.14; the split needs each replication's receipts read again | deferred-0.2.15 |
| 12-21 | jnwb recovers a planted delay and a planted direction from a jaxfne field (validation) | The spectrum half landed (`tests/test_jaxfne_ground_truth.py`: `compute_psd` recovers the planted 10.0 Hz of jaxfne's protocol_c planar field, commit 21c99f96); a single-frequency field has no phase-slope delay and no direction, so delay (`phase_slope_index`) and direction (`granger`) wait for a broadband jaxfne field | A broadband jaxfne field with a stated delay or coupling; nothing shipped changes. Moved to 0.2.15 (ruled 2026-10-23: the spectrum test closes the item for 0.2.14). | deferred-0.2.15 |
| 16-20 | A distance-aware coherence graph | `cross_area_coherence` and `network_topology` take a coherence matrix as it is, so a graph of nearby contacts or electrodes is dense from field spread alone; Nejat and Hajipour Sardouie 2021 normalize edge weights by distance and compare groups edge by edge (`docs/references.md`, Pitfalls) | raised during 0.2.14, after its scope was set (goal F3, ruled 2026-10-21) | deferred-0.2.15 |

## Fact closure

Items that hold UNHELD facts; signature types before the scans and holder fixes.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
| 17-03 | Declared types on the remaining numeric operations | Fact I4 is UNHELD: only the operations whose parameter names show spikes or LFP declare signal types (`jnwb/_declarations.py`); generic-input operations such as `granger_causality`, `directed_network` and `imaginary_coherency` take either class and declare nothing | A per-call class for generic inputs; nothing shipped changes. Split from I1 (ruled 2026-10-24). | deferred-0.2.15 |
| 17-04 | The deprecated time windows become required | `UnitAnalyzer.psth`/`raster` `window_ms` and `build_time_resolved_matrix`/`compute_population_trajectory` `time_window_ms` warn when omitted and still use (-1000, 2000) ms (`jnwb/_units.py` `omitted_window`); four B3 exceptions rows cite the deprecation | The 0.2.15 cycle: drop the default and the warning, delete the four rows. Ruled 2026-10-24. | deferred-0.2.15 |
| 17-05 | B3's lexicon covers the other choice names | The lexicon holds time windows only (ruled 2026-10-24); defaulted role windows (`response_window`, `response_window_s`, `sink_window_ms`, `exclude_window_ms`, `reward_window_ms`), baselines, bands, bins, segments, null sizes and method names go unchecked | A ruling per name group on which defaults a source cites; nothing shipped changes | deferred-0.2.15 |
| 17-06 | Required windows become keyword-only | Six public functions take a required window positionally (`fano_factor`, `network_burst_index`, `spike_count_correlation`, `fire_indicator`, `fires_in_window`, `rate_in_window`); B3 dropped "keyword-only" (ruled 2026-10-25) | A deprecation path for positional callers | deferred-0.2.15 |
| 17-07 | S8 over prose | S8's check reads figure labels and returned units only (ruled 2026-10-25); a sentence-level vocabulary scan of docs, skills and docstrings hit 49 sentences, about 47 legitimate (zflip's delays, "volume conduction", transfer entropy's `delay=`, negations). Two read as overclaims: `skills/jnwb-connectivity/SKILL.md` calls PSI "the frequency-dependent driver/receiver lag", and the `jnwb/connectivity/_transfer_entropy.py` module docstring calls TE "directed information flow"; `UnitAnalyzer.correlate_areas` (`jnwb/analyzers.py:304`) calls a correlation of band power "inter-area synchrony" (audit 2026-10-25) | A ruled per-class vocabulary and a reviewed exceptions table; the skill line needs an amendment ruling | deferred-0.2.15 |
| 17-08 | I3 beyond named units | I3's check reads unit- and base-suffixed names across call edges (ruled 2026-10-25); a coordinate frame, a sample rate (`fs` carries no suffix) or an index base a name does not spell can still change at a boundary unseen | A representation of frames, rates and bases a scan can read | deferred-0.2.15 |
| 17-24 | Non-finite inputs fail loudly | S9's holder reads swallowed handlers only (ruled 2026-10-25); NaN or inf passed to a public numeric function can still return a number without a refusal or warning, as seven functions did in the 2026-10-25 audit (items 17-10, 17-13, 17-21, 17-23, 17-50, 17-51) | A computed holder that feeds NaN and inf to each public numeric function and requires a refusal or a warning. Ruled 2026-10-25. | deferred-0.2.15 |
| 11-09 | Planned skills | The fact gate can report a planned skill for which K1 or K5 does not hold; K5 (a skill only for a coherent capability surface no existing skill handles more simply) has no mechanical predicate, and the planned set is prose only; the full text is in `git log -S '### 11-09' -- artifacts/todo_stack.md` | No planned skill ships in 0.2.14 and nothing public claims one; K5 is held by review until a predicate exists. Ruled 2026-10-25. | deferred-0.2.15 |
| 17-59 | Frozen bodies kill every planted change | Planted changes that survive the tests the core freeze names (measured 2026-10-26): `shuffle_r2_ci` with its CI upper percentile 97.5 -> 95 or its p-value +1; `cluster_permutation_test` with its t standard error x2 or the max-mass statistic; the GPU branch of `cross_area_coherence` on a CPU-only machine | Each frozen body has a test that kills a planted change, so the freeze holds; the survivors are behaviours no test pins, and no released number is shown wrong | deferred-0.2.15 |

## Public API

Each needs Hamm's ruling before code.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|

## NWB reading edges

Reader and integrity edge cases.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|

## Consumers and docs

Use of jnwb from outside: a new dataset, a downstream agent, tutorial figures.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|

## Harness and gates

Gate reach before pruning; guards for the installed-wheel leg.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
