# Roadmap

Work deferred past the cycles the todo stack holds, one row per item. An item moves into the
todo stack, with its full text, when its cycle opens; it is never in both files.

A row is `| id | theme | defect | waits | deferred-X.Y.Z |`: the item id, a short theme, the
defect in one line, the reason it waits (AGENTS.md section 11), and the cycle it is deferred to,
later than the declared version. `scripts/release_gate.py` STEP 0a refuses any row that breaks
this form, and `scripts/fact_gate.py` counts each row's id as a live item. Rows are grouped by theme;
within a theme they run in the order listed, dependencies first.

The full text of each item carried here from the todo stack is in
`artifacts/archive/0.2.10/todo_stack_0.2.10.md`, the stack as it stood when this file opened.

## Laminar validation

Ground truth for vflip2, xflip's null and the curation path.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
| 15-11 | `vflip2` recovers a planted vFLIP2 crossover on Andre Bastos's simulation code | The generator half landed in 1dbcedbf (`artifacts/evidence/0.2.13/vflip2_recovery.md`: recovery 29 of 100, matched null 24 of 100); the same table has not run on his code, under the contract in `artifacts/evidence/0.2.13/vflip2_generator_design.md`; full text: `git log -S '### 15-11' -- artifacts/todo_stack.md`. | His simulation code; nothing shipped changes. Moved to 0.2.15 (ruled 2026-10-19). | deferred-0.2.15 |
| 16-12 | Dashboard real-data cards for `isi_cv` (9,056 units), WaveMAP and the omission results | The dashboard ships with the four committed GLO entries; the others need a receipt computed without calling jnwb: the omission and WaveMAP receipts record jnwb calls (`jnwb_version`, `jnwb_wavemap_commit`), and the `isi_cv` receipt file (branch `claude/site-overview-326890`, commit 9b52c5e7) no longer exists | Independent recomputations with committed receipts; nothing shipped changes. Moved to 0.2.15 (ruled 2026-10-23). | deferred-0.2.15 |
| 12-21 | jnwb recovers a planted delay and a planted direction from a jaxfne field | The spectrum half landed (`tests/test_jaxfne_ground_truth.py`: `compute_psd` recovers the planted 10.0 Hz of jaxfne's protocol_c planar field, commit 21c99f96); a single-frequency field has no phase-slope delay and no direction, so delay (`phase_slope_index`) and direction (`granger`) wait for a broadband jaxfne field | A broadband jaxfne field with a stated delay or coupling; nothing shipped changes. Moved to 0.2.15 (ruled 2026-10-23: the spectrum test closes the item for 0.2.14). | deferred-0.2.15 |
| 16-20 | A distance-aware coherence graph | `cross_area_coherence` and `network_topology` take a coherence matrix as it is, so a graph of nearby contacts or electrodes is dense from field spread alone; Nejat and Hajipour Sardouie 2021 normalize edge weights by distance and compare groups edge by edge (`docs/references.md`, Pitfalls) | raised during 0.2.14, after its scope was set (goal F3, ruled 2026-10-21) | deferred-0.2.15 |

## Fact closure

Items that hold UNHELD facts; signature types before the scans and holder fixes.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
| 17-03 | Declared types on the remaining numeric operations | Fact I4 is UNHELD: only the operations whose parameter names show spikes or LFP declare signal types (`jnwb/_declarations.py`); generic-input operations such as `granger_causality`, `directed_network` and `imaginary_coherency` take either class and declare nothing | A per-call class for generic inputs; nothing shipped changes. Split from I1 (ruled 2026-10-24). | deferred-0.2.15 |
| 17-04 | The deprecated time windows become required | `UnitAnalyzer.psth`/`raster` `window_ms` and `build_time_resolved_matrix`/`compute_population_trajectory` `time_window_ms` warn when omitted and still use (-1000, 2000) ms (`jnwb/_units.py` `omitted_window`); four B3 exceptions rows cite the deprecation | The 0.2.15 cycle: drop the default and the warning, delete the four rows. Ruled 2026-10-24. | deferred-0.2.15 |
| 17-05 | B3's lexicon covers the other choice names | The lexicon holds time windows only (ruled 2026-10-24); defaulted role windows (`response_window`, `response_window_s`, `sink_window_ms`, `exclude_window_ms`, `reward_window_ms`), baselines, bands, bins, segments, null sizes and method names go unchecked | A ruling per name group on which defaults a source cites; nothing shipped changes | deferred-0.2.15 |
| 17-06 | Required windows become keyword-only | Six public functions take a required window positionally (`fano_factor`, `network_burst_index`, `spike_count_correlation`, `fire_indicator`, `fires_in_window`, `rate_in_window`); B3 dropped "keyword-only" (ruled 2026-10-25) | A deprecation path for positional callers | deferred-0.2.15 |

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
