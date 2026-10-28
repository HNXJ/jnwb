# 0.2.15

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. 0.2.14
closed on 2026-10-27 (tag `v0.2.14`). Items run fastest first; the lanes below split them into
parallel writers that share no file.

## How this stack is executed

| Rule | Why |
|---|---|
| `AUTONOMY: max` unless an item says otherwise (`AGENTS.md` §12) | actor and critic sequence the work |
| One item per packet (`artifacts/skills/jnwb-fact-action` §5); a lane is one clone and one Haiku 5.5 `worker`; up to three lanes at once; a lane's items run in the order listed | lanes share no file, so they merge without conflict |
| A public signature, an estimand or a skill line goes to Hamm before code, batched in one message per wave; Haiku implements a ruled signature and never chooses one | public API and skills are Hamm's |
| A packet reproduces its bullet first, writes the failing test, then the fix; a `reviewer` that did not write it verifies; the integrator commits, owns the stacks, `CHANGELOG.md` and `docs/api.md` | the actor is never the verifier |
| Wave barrier: `python scripts/harness_gate.py`, the full suite, push, CI green on `dev` at that SHA | a local pass is not a CI pass |

Item fields: `Release`, `Role`, `Skill`, `Blocked by`, `Writes`, then one bullet:
`ID: defect with numbers. Check: a predicate naming the file and the asserted value. Waits: why.`
At most eight lines per item.

## Lanes

Speed: S is one module and one test file, M adds a public signature or several files, L needs a
design or a scan across `jnwb/`.

| Wave | Lane | Items, in order | Speed | Needs first |
|---|---|---|---|---|
| 1 | C windows | 17-04, 17-06, 17-65 | M, M, M | ruled 2026-10-28 |
| 2 | F units | 17-68 | M | ruled 2026-10-28 |
| 3 | G tests and dashboard | 17-59, 17-60 | M, L | nothing |
| 3 | H declarations | 17-03, 16-20 | M, L | 16-20 reviewed by `reviewer` at high |
| 3 | I fact graph | 17-08, 11-03, 11-09 | L, L, L | nothing |
| 4 | J non-finite | 17-24 | L | waves 1 to 3 merged (writes across `jnwb/`) |
| - | Held | 17-05, 17-07 | - | Hamm's rulings |

### 17-04 The deprecated time windows become required

Release: deferred-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `jnwb/_units.py`, `jnwb/analyzers.py`, `jnwb/trajectory.py`, `artifacts/fact_stack.md`, `skills/jnwb-population/SKILL.md`, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/common_mistakes.md`, the tests that pin the old warning.
- 17-04: `UnitAnalyzer.psth`/`raster` `window_ms` and `build_time_resolved_matrix`/`compute_population_trajectory` `time_window_ms` warn when omitted and still use (-1000, 2000) ms (`jnwb/_units.py` `omitted_window`); four B3 exceptions rows cite the deprecation. Check: omitting any of the four windows raises instead of warning, and the four rows are gone from the `## B3 exceptions` table of `artifacts/fact_stack.md`. Waits: The 0.2.15 cycle: drop the default and the warning, delete the four rows. Ruled 2026-10-24.

### 17-06 Required windows become keyword-only

Release: deferred-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `jnwb/spiking.py`, `jnwb/statistics/_firing.py`, `tests/test_api_consistency.py`, `artifacts/fact_stack.md`, `skills/jnwb-spiking/SKILL.md`.
- 17-06: Six public functions take a required window positionally (`fano_factor`, `network_burst_index`, `spike_count_correlation`, `fire_indicator`, `fires_in_window`, `rate_in_window`); B3 dropped "keyword-only" (ruled 2026-10-25). Check: `tests/test_api_consistency.py` asserts the deprecation path for each of the six positional callers. Waits: A deprecation path for positional callers.

### 17-65 Bin times say which edge they name

Release: deferred-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: 17-04 (same signatures).
Writes: `jnwb/analyzers.py`, `jnwb/trajectory.py`, `jnwb/_bins.py`, `tests/test_api_consistency.py`.
- 17-65: `UnitAnalyzer.psth` (`bin_centers_ms`, `jnwb/analyzers.py:417`) and `build_time_resolved_matrix` (`jnwb/trajectory.py:63`) label a bin at its centre only, so an onset read off the trace leads an instantaneous event by half a bin (omission JNWB-024). Check: each binning helper takes `label='center'|'right'` (right: bin (t-w, t] labelled t) and returns the convention it used; a step at t=0 first shows in the bin labelled 0 under `'right'`. Waits: requested 2026-10-27.

### 17-68 One unit table with a column dictionary

Release: deferred-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `jnwb/metadata.py`, `tests/test_metadata.py`.
- 17-68: Every consumer rebuilds the per-unit join of identity, probe, peak channel, area, layer and waveform features (omission JNWB-027). Check: `units_table(nwb)` returns one row per unit in unit order with a column dictionary (definition, source, units), and on the 17-61 fixture area comes through `units.electrodes`. Waits: requested 2026-10-27.

### 17-59 Frozen bodies kill every planted change

Release: deferred-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `artifacts/process/frozen_validated.json`, `tests/test_frozen_core_mutants.py`.
- 17-59: Planted changes that survive the tests the core freeze names (measured 2026-10-26): `shuffle_r2_ci` with its CI upper percentile 97.5 -> 95 or its p-value +1; `cluster_permutation_test` with its t standard error x2 or the max-mass statistic; the GPU branch of `cross_area_coherence` on a CPU-only machine. Check: each planted change in that list fails a test in `tests/test_frozen_core_mutants.py`. Waits: Each frozen body has a test that kills a planted change, so the freeze holds; the survivors are behaviours no test pins, and no released number is shown wrong.

### 17-60 Paper, library and methods verdicts on the dashboard

Release: deferred-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/build_dashboard.py`, `artifacts/showcases/openscope_glo.json`, `tests/test_build_dashboard.py`.
- 17-60: Each showcase replication carries one verdict and no numeric paper value, where jaxfne splits the verdict into paper, library and methods. Check: `tests/test_build_dashboard.py` asserts each replication card carries a paper, a library and a methods verdict. Waits: one verdict per replication was ruled for 0.2.14 (2026-10-26); the split needs each replication's receipts read again. Roadmap row 17-57 until 2026-10-27, renumbered because 17-57 names a finished item.

### 17-03 Declared types on the remaining numeric operations

Release: deferred-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `jnwb/_declarations.py`, `jnwb/connectivity/_granger.py`, `jnwb/connectivity/_network.py`, `jnwb/spectral/_coupling.py`.
- 17-03: Fact I4 is UNHELD: only the operations whose parameter names show spikes or LFP declare signal types (`jnwb/_declarations.py`); generic-input operations such as `granger_causality`, `directed_network` and `imaginary_coherency` take either class and declare nothing. Check: each generic-input operation declares a per-call class in `jnwb/_declarations.py`, and fact I4 reports HELD. Waits: A per-call class for generic inputs; nothing shipped changes. Split from I1 (ruled 2026-10-24).

### 16-20 A distance-aware coherence graph

Release: deferred-0.2.15.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: nothing.
Writes: `jnwb/spectral/_coupling.py`, `jnwb/connectivity/_network.py`, `tests/test_connectivity_pitfalls.py`, `docs/references.md`.
- 16-20: `cross_area_coherence` and `network_topology` take a coherence matrix as it is, so a graph of nearby contacts or electrodes is dense from field spread alone; Nejat and Hajipour Sardouie 2021 normalize edge weights by distance and compare groups edge by edge (`docs/references.md`, Pitfalls). Check: on a planted field with spread between nearby contacts, the distance-normalized edges differ from the raw coherence edges, asserted in `tests/test_connectivity_pitfalls.py`. Waits: raised during 0.2.14, after its scope was set (goal F3, ruled 2026-10-21).

### 17-08 I3 beyond named units

Release: deferred-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/build_fact_graph.py`, `artifacts/fact_stack.md`.
- 17-08: I3's check reads unit- and base-suffixed names across call edges (ruled 2026-10-25); a coordinate frame, a sample rate (`fs` carries no suffix) or an index base a name does not spell can still change at a boundary unseen. Check: the I3 rule in `scripts/build_fact_graph.py` reports a planted boundary call that changes a frame, a rate or an index base the name does not spell. Waits: A representation of frames, rates and bases a scan can read.

### 11-03 Design facts held

Release: deferred-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- 11-03: D1-D3, D5-D10 report UNHELD: no scan reads delegation or side-effect categories (D1-D3), `AmbiguousMappingError` and `UndeclaredUnitError` are exported and never raised (D5, D7, D9), and no test holds condition meaning, trial semantics or cache decisions (D6, D8, D10). Check: each of D1-D3 and D5-D10 gets its own scan or refusal with a planted case. Waits: Ruled 2026-10-26: each needs its own scan or refusal with a planted case; D4 and D11 are held.
Accept: the Design table reports no UNHELD fact.

### 11-09 Planned skills

Release: deferred-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- 11-09: The fact gate can report a planned skill for which K1 or K5 does not hold; K5 (a skill only for a coherent capability surface no existing skill handles more simply) has no mechanical predicate, and the planned set is prose only. Check: the fact gate reports a planned skill only when K1 and K5 hold for it. Waits: No planned skill ships in 0.2.14 and nothing public claims one; K5 is held by review until a predicate exists. Ruled 2026-10-25.
Accept: K5 reports HELD; no UNHELD fact names a 0.2.15 item.

### 17-24 Non-finite inputs fail loudly

Release: deferred-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/build_fact_graph.py`, `jnwb/**/*.py`.
- 17-24: S9's holder reads swallowed handlers only (ruled 2026-10-25); NaN or inf passed to a public numeric function can still return a number without a refusal or warning, as seven functions did in the 2026-10-25 audit (items 17-10, 17-13, 17-21, 17-23, 17-50, 17-51). Check: the S9 holder in `scripts/build_fact_graph.py` feeds NaN and inf to each public numeric function and asserts a refusal or a warning. Waits: A computed holder that feeds NaN and inf to each public numeric function and requires a refusal or a warning. Ruled 2026-10-25.

### 17-05 B3's lexicon covers the other choice names

Release: deferred-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: a ruling per name group on which defaults a source cites (Hamm).
Writes: `artifacts/fact_stack.md`, `scripts/build_fact_graph.py`.
- 17-05: The lexicon holds time windows only (ruled 2026-10-24); defaulted role windows (`response_window`, `response_window_s`, `sink_window_ms`, `exclude_window_ms`, `reward_window_ms`), baselines, bands, bins, segments, null sizes and method names go unchecked. Check: each name group is in the `B3 choice names` constant of `artifacts/fact_stack.md` or excepted in its `## B3 exceptions` table with a source-cited reason. Waits: A ruling per name group on which defaults a source cites; nothing shipped changes.

### 17-07 S8 over prose

Release: deferred-0.2.15.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: Hamm's rulings on the per-class vocabulary and the skill line.
Writes: `skills/jnwb-connectivity/SKILL.md`, `jnwb/connectivity/_transfer_entropy.py`, `jnwb/analyzers.py`, `scripts/build_fact_graph.py`.
- 17-07: S8's check reads figure labels and returned units only (ruled 2026-10-25); a sentence-level vocabulary scan of docs, skills and docstrings hit 49 sentences, about 47 legitimate (zflip's delays, "volume conduction", transfer entropy's `delay=`, negations). Two read as overclaims: `skills/jnwb-connectivity/SKILL.md` calls PSI "the frequency-dependent driver/receiver lag", and the `jnwb/connectivity/_transfer_entropy.py` module docstring calls TE "directed information flow"; `UnitAnalyzer.correlate_areas` (`jnwb/analyzers.py:306`) calls a correlation of band power "inter-area synchrony" (audit 2026-10-25). Check: a ruled per-class vocabulary and a reviewed exceptions table decide each sentence the scan hits, and the two overclaims are reworded or cut. Waits: A ruled per-class vocabulary and a reviewed exceptions table; the skill line needs an amendment ruling.
