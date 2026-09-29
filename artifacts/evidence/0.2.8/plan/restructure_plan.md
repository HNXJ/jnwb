# Restructure plan, 0.2.8 to 0.2.12

Proposal of 2026-09-28 at `fe14858d`; nothing here is ruled. Every number was measured on that tree
(`wc -l`, `wc -w`, an import of `jnwb`, `git ls-files`). The items named in the last column are in
`todo_stack_0.2.8.md`; the choices that need Hamm are in `decisions.md`.

The order follows the request: state first (it speeds every later cycle), then figures and skills,
then documentation, then the package, then the release apparatus.

| Cycle | Surface rewritten | Items |
|---|---|---|
| 0.2.8 | state files; figures; skills and roles | 08-01, 08-05, 08-06, 08-07, 08-08; 08-02, 08-03, 08-04; 07-30, 07-18, 07-13 |
| 0.2.9 | skill set completed; documentation menu | 07-10, 07-11, 07-12, 07-08, 07-09; 09-01, 09-02, 09-03 |
| 0.2.10 | package modules | 10-01 to 10-09 |
| 0.2.11 | NWB reading and writing | 11-01, 11-02, 07-05, 07-21, 07-22 |
| 0.2.12 | scripts and process tests | 12-01 to 12-06 |

## (a) Package layout

`jnwb/` holds 61 Python files and 28,786 lines; `jnwb.__all__` has 162 names. Five modules hold
11,786 lines, 41 % of the package.

| Module | Lines | Exports | Top-level defs | What is tangled | Proposed split | Cycle |
|---|---|---|---|---|---|---|
| `connectivity.py` | 2679 | 14 | 46 | four estimator families and spike binning in one file; `jrsa` and `analyzers` import it for `bin_spikes` | `connectivity/`: `information` (3 MI functions), `granger` (VAR fit, lag selection, `granger*`), `psi`, `transfer_entropy`, `network` (`DirectedResult`, `directed_*`, `network_topology`), `_trials` (`as_trials`, `bin_spikes`) | 0.2.10, 10-05 |
| `laminar.py` | 2519 | 8 | 20 | three unrelated profile estimators and the labeller | `laminar/`: `vflip`, `xflip`, `zflip`, `labels` | 0.2.10, 10-02 |
| `spectral.py` | 2297 | 17 | 30 | spectra, decibel formation, coupling and referencing on one page of code | `spectral/`: `psd` (PSD, multitaper, tilt, aperiodic, harmonics, segment count), `decibels` (`to_db`, `aggregate_to_db`, `relative_power`, `band_power`), `coupling` (coherence, `imaginary_coherency`, `wpli`), `reference` (bipolar, Laplacian, curvature, CSD) | 0.2.10, 10-02 |
| `jrsa.py` | 2288 | 2 | 53 | 51 private functions behind two exports | `jrsa/`: the two exports in `__init__`, private stages split by the call graph the packet measures | 0.2.10, 10-05 |
| `statistics.py` | 2003 | 16 | 25 | test primitives, firing-window helpers, trial-structure helpers and a 770-line class | `statistics/`: `tests` (sign flip, shuffles, Clopper-Pearson, FDR, p floor), `firing` (window helpers, `paired_fire_prob_test`), `trials` (`detect_trial_cycles`, `assign_subblock_quartiles`), `analysis` (`StatisticalAnalysis`), `cluster`, `regression` (`shuffle_r2_ci`, `coef_rows`, `cross_modal_comparison`) | 0.2.10, 10-07 |
| `nwb_inspect.py` 1083, `addressing.py` 962, `analyzers.py` 856, `compression.py` 825 | 3726 | 19 | | each holds one concern | keep | none |

How a split keeps the API:

| Rule | Why |
|---|---|
| The module becomes a package at the same import path; its `__init__` re-exports every name the old module bound, private names tests import included | `jnwb.spectral.compute_psd` and `from jnwb.spectral import _x` keep working; `jnwb/__init__.py` and `_lazy_exports.py` do not change |
| Public classes keep `__module__` at the old path (D5) | pickles and reprs of `DirectedResult`, `VFlipResult` and the rest stay valid |
| A split is a pure move, in its own commit, before any edge in that module is touched | a diff reviewer sees moves or changes, never both |
| 10-01 lands first: six shared files that name module paths derive them by import | without it the three split lanes would share `tests/test_semantic_mutation_classes.py` and four more |
| Gate 19's two `jnwb/statistics.py` entries are re-pointed with unchanged hashes | the frozen record follows the function, and a changed hash would mean the move edited a body |
| `docs/api.md` is regenerated at the wave barrier | object `__module__` paths inside it may change |

Out of the split and kept as is: `viz.py` (Matplotlib helpers) beside `vis/` (Plotly) is a naming
wart but both are public paths; the non-exported experimental modules `bilinear`, `gpu_pca` and
`nam` wait for the routing ruling of D8.

Scripts, 0.2.12:

| File | Lines | Proposed | Item |
|---|---|---|---|
| `scripts/harness_gate.py` | 3108 | `scripts/gates/`, one module per gate family; `GATES` stays the one list | 12-01 |
| todo-stack parsing, three copies (STEP 0a, gate 15, gate 17) | | one `scripts/stack_parse.py` read by all three | 12-01, 12-02 |
| `scripts/release_gate.py` | 2071 | cheap checks first (0.2.8); the shared parser (0.2.12) | 08-07, 12-02 |
| process tests | 19,323 lines in 48 of 189 test files (30 % of 64,649) | prune and merge by the ruled list | 12-05 |

## (b) Skills

Nine shipped skills (`skills/`), one repository-only (`artifacts/skills/jnwb-fact-action`). All nine
follow one template: Trigger, Routing, Invariants, Minimal Workflow, Verification, Documentation
(the router adds Execution).

| Skill | Words | Routes | Problem | Proposal | Cycle |
|---|---|---|---|---|---|
| `jnwb` (router) | 728 | task to skill | one skill per task phrase; 7 of 8 safeguards also in `AGENTS.md` §4; skill table also in `docs/agents.md`, and the two disagree | composes skill sets (07-08); one table held by a test (07-30) | 0.2.8, 0.2.9 |
| `jnwb-lfp-spectral` | 1756 | spectra, TFR, coherence, CSD, laminar | largest skill; laminar has no page to link | shrinks when `docs/laminar.md` exists and rows link it (10-04); dedup (07-13) | 0.2.8, 0.2.10 |
| `jnwb-nwb-data` | 1336 | inspection, events, addressing, audits | holds paradigm and QC rows | event rows move to `jnwb-paradigm`, audits to `jnwb-qc` | 0.2.9 |
| `jnwb-population` | 1069 | decoding, trajectories, RSA | | none beyond 07-13 | 0.2.8 |
| `jnwb-connectivity` | 1063 | directed, information | volume-conduction line shared with the router | 07-13 | 0.2.8 |
| `jnwb-spiking` | 915 | PSTH, onset, QC metrics | `raster_psth` in two skills (repaired) | none | |
| `jnwb-landmark-viz` | 755 | Plotly figures | routes by module, so no signature check; layout sentence and check bullet say one thing twice | per-function rows (IB-63); one inspect-the-PNG check (07-30) | 0.2.8, 0.2.9 |
| `jnwb-statistics` | 717 | tests, corrections | | none | |
| `jnwb-figures` | 362 | Matplotlib figures | "visual QC" trigger routes unit plots (repaired) | QC rows leave for `jnwb-qc` | 0.2.9 |

Proposed tree after 0.2.9: eleven shipped (the nine plus `jnwb-paradigm` and `jnwb-qc`), two
repository-only (`jnwb-fact-action`, `jnwb-review`). `jnwb-data-engineering` and `jnwb-compute`
stay gated on the 0.2.11 APIs and are not created unless the router cannot carry them.

| Friction (skills audit, 2026-09-28) | Measured | Closed by |
|---|---|---|
| exports no skill names | 26 of 162 | 07-12 |
| modules no skill references | 8 of 48 | 07-12, D8 |
| docs pages no skill links | 20 of 33 | 07-12, after 09-01 settles the pages |
| examples and notebooks no skill names | 12 of 12 | 07-18, 07-12 |
| shared normalised lines | 3 | 07-13 |
| hardcoded skill counts | 2 | 07-30 |

## (c) Documentation

Measured with `wc -l` and `wc -w`. Ceilings are those of `docs/documentation_form.md`.

| Page | Lines | Words | Kind, ceiling | Proposal | Cycle |
|---|---|---|---|---|---|
| `api.md` | 307 | 5207 | reference, none | generated; keep | |
| `common_mistakes.md` | 393 | 2461 | task, 900 | keep (eleven failure modes, tabled excess) | |
| `10_operation_specifications.md` | 127 | 2278 | reference, none | keep | |
| `documentation_form.md` | 191 | 2161 | contract, off-nav | keep; its page count and ceiling prose updated by 09-01 | 0.2.9 |
| `04_spectral_analysis_and_tfr.md` | 346 | 1974 | concept, 1200 | split: PSD and decibels stay; coherence and TFR to `coherence_and_tfr.md` | 0.2.9 |
| `02_paths_addressing_metadata.md` | 311 | 1754 | concept, 1200 | split: paths and streaming to `reading_nwb.md`; addressing and metadata stay | 0.2.9 |
| `errors.md` | 237 | 1739 | task, 900 | keep (pinned messages, tabled excess) | |
| `references.md` | 86 | 1718 | reference, none | keep | |
| `06`, `08`, `03`, `07`, `05`, `09` | 191 to 262 | 1143 to 1200 | concept, 1200 | keep; figure fixes only (08-03) | 0.2.8 |
| `01_architecture_and_philosophy.md` | 119 | 1171 | concept, 1200 | merge into `architecture.md`: two pages on one subject | 0.2.9 |
| `architecture.md` | 119 | 661 | concept, 1200 | absorbs 01; adds the magnitude-direction-delay-inference table (P-269) | 0.2.9 |
| `tutorials/09_open_data.md` | 120 | 959 | included | keep | |
| `agents.md` | 118 | 886 | task, 900 | keep; one skill table held by a test | 0.2.8 |
| `quickstart.md`, `install.md` | 159, 117 | 837, 835 | task, 900 | keep; quickstart figure (08-04) | 0.2.8 |
| `vis.md`, `tutorials/00_your_own_file.md` | 74, 68 | 500, 500 | | keep | |
| `index.md` | 99 | 399 | landing, 400 | gallery images link to full size (08-03) | 0.2.8 |
| `recipes.md`, `glossary.md` | 62, 19 | 348, 235 | | keep | |
| `tutorials/01` to `08` | 20 to 23 | 72 to 94 | included wrappers | keep; each linked from its topic page | 0.2.9 |
| new `laminar.md` | | | concept | the laminar operations have no topic page today | 0.2.10 |

Nav by how a reader arrives (09-01). Filenames of topic pages stay, so skill links hold.

| Group | Pages | Reader |
|---|---|---|
| Start | Welcome, Install, Quickstart, Your own NWB file, Recipes | new user |
| Analyse | Reading NWB, Addressing and metadata, Spikes, Spectra and decibels, Coherence and TFR, Artifacts, Statistics, Directed connectivity, Decoding, Similarity (RSA), Laminar, Plotly figures | has data and a question |
| Tutorials | 01 to 09 | wants a runnable script |
| Use with an agent | Analyzing with an agent | agent or agent builder |
| Fix a problem | Common mistakes, Errors | has an error or a doubt |
| Look up | Public API, Operation specifications, References, Glossary | knows the name |
| Design | Architecture | contributor or reviewer |

Pages on the nav: 32 today, 33 after 0.2.9 (one merge, two splits), 34 after `laminar.md`. Words
do not grow: a split moves text, and 09-01 accepts only with a before-and-after claim table.

## (d) State files

| File | Size | Bloat | Compact form | Owner | Cycle |
|---|---|---|---|---|---|
| `artifacts/todo_stack.md` | 657 lines, 12,600 words | 15 items, three of them containers of 170 bullets, each bullet carrying a paragraph and a repeated `deferred-0.2.8:` line; a completed-scope preamble | `todo_stack_0.2.8.md`: 39 items in five cycles, one line per bullet (defect, check, reason it waits), a lane table per cycle; 9,607 words with the figure work and five cycles added; full text stays at `fe14858d` | agents | 0.2.8, 08-01 |
| `artifacts/problem_stack.md` | 17 lines | none; empty and correct | keep | agents | |
| `artifacts/state.md` | generated, uncommitted | none | keep; 12-05 adds the apparatus line counts | script | 0.2.12 |
| `artifacts/goal.md` | 148 lines | restates the `direction.md` diagram it says it does not restate; long "Held by" sentences | `goal_proposed.md`, every ruled meaning kept | Hamm | ruling |
| `artifacts/fact_stack.md` | 114 lines | a stack-roles section that repeats `AGENTS.md` §2; two boundary facts that overlap | `fact_stack_proposed.md`, every fact kept | Hamm | ruling |
| `artifacts/rulings/*.md` | 7 dated files, 232 lines, plus `history.md` 46 | a ruling's still-binding part and its spent work column sit together; finding the standing rule on a subject means reading every date | D6: one `standing.md` table (subject, rule, date, held by) for rulings that still bind; dated files move to `artifacts/archive/<cycle>/rulings/` at cycle close | Hamm | 0.2.8, 08-01 |
| `artifacts/planned_post_0.2.6.md` | 97 lines | every step landed or is in the stack (checked: `groups=` on `nested_cv_linear_svm`, `select` required, `mean_of_ratios` accumulator, `jnwb.preflight`, gate 20); the benchmark design is the only residue | benchmark design to `artifacts/evidence/0.2.8/stack/`; file deleted | agents | 0.2.8, 08-01 |
| `artifacts/evidence/0.2.8/roadmap_proposal.md` | 88 lines | superseded by this plan | deleted when the stack lands | agents | 0.2.8, 08-01 |
| `AGENTS.md` | 455 lines, 4403 words | reasons and incidents inline with rules | about 1500 words of rules and routes; reasons to `history.md` | Hamm approves | 0.2.8, 08-06 |
| `CHANGELOG.md` | 38,289 words | one file every change edits, so parallel lanes conflict on it | fragments in `changelog.d/`, assembled at release | integrator | 0.2.8, 08-05 |

Two landing notes for 08-01. The live `artifacts/todo_stack.md` is CRLF and this draft is LF;
landing it whole in LF is the wholesale conversion Gate 16 cannot see (P-159), so it lands in CRLF
unless D3 levels endings first. `scripts/release_gate.py` accepts only `deferred-<next>`, so every
item past 0.2.9 carries `deferred-0.2.9` and is relabelled when each cycle opens (D2).
