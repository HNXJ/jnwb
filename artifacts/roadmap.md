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
| 15-11 | `vflip2` recovers a planted vFLIP2 crossover on Andre Bastos's simulation code (validation) | The generator half landed in 1dbcedbf (`artifacts/evidence/0.2.13/vflip2_recovery.md`: recovery 29 of 100, matched null 24 of 100); the same table has not run on his code, under the contract in `artifacts/evidence/0.2.13/vflip2_generator_design.md`; full text: `git log -S '### 15-11' -- artifacts/todo_stack.md`. | His simulation code; nothing shipped changes. Moved to 0.2.15 (ruled 2026-10-19), then 0.2.16 (ruled 2026-10-31), then 0.2.17 (ruled 2026-11-06). | deferred-0.2.17 |
| 16-12 | Dashboard real-data cards for `isi_cv` (9,056 units), WaveMAP and the omission results (validation) | The dashboard ships with the four committed GLO entries; the others need a receipt computed without calling jnwb: the omission and WaveMAP receipts record jnwb calls (`jnwb_version`, `jnwb_wavemap_commit`), and the `isi_cv` receipt file (branch `claude/site-overview-326890`, commit 9b52c5e7) no longer exists | Independent recomputations with committed receipts; nothing shipped changes. Moved to 0.2.15 (ruled 2026-10-23), then 0.2.16 (ruled 2026-10-31), then 0.2.17 (ruled 2026-11-06). | deferred-0.2.17 |
| 12-21 | jnwb recovers a planted delay and a planted direction from a jaxfne field (validation) | The spectrum half landed (`tests/test_jaxfne_ground_truth.py`: `compute_psd` recovers the planted 10.0 Hz of jaxfne's protocol_c planar field, test commit 166d6c87; the field generator is jaxfne commit 21c99f96); a single-frequency field has no phase-slope delay and no direction, so delay (`phase_slope_index`) and direction (`granger`) wait for a broadband jaxfne field | A broadband jaxfne field with a stated delay or coupling; nothing shipped changes. Moved to 0.2.15 (ruled 2026-10-23: the spectrum test closes the item for 0.2.14); then 0.2.16 (ruled 2026-10-31), then 0.2.17 (ruled 2026-11-06). Requested from jaxfne 2026-11-09 (ruled that day). | deferred-0.2.17 |

## Rulings, form and CI reach

The open rows of the 2026-11-02 audit (eight auditors at `9fd2b4bd`, per
`artifacts/open_stack.md:35`), moved here by the release plan (ruled 2026-11-05) on
2026-11-06. Each row's full text: `git log -S '| P-216-NN |' -- artifacts/open_stack.md`, with the
number in the Theme cell.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
| 17-130 | Public parameter names (from P-216-25) | 17 time and frequency parameters lack unit suffixes; `window` has four meanings and the bin concept four names; `fs` beside `sampling_rate` | Hamm rules the public names (0.2.18 estimand and parameter decisions) | deferred-0.2.18 |
| 17-131 | `gaussian_smooth_rate` NaN handling (P-216-24) | no `nan_policy=` argument; a comment left in 17-110 calls the question undecided (`jnwb/spiking.py`) | Hamm rules the argument | deferred-0.2.18 |
| 17-132 | Estimand choices no ruling names (P-216-32) | response z uses `np.std` ddof 0 while Fano and CV use ddof 1 (`jnwb/spiking.py:191,980`); `detect_trial_cycles` median gap counts zero gaps (`statistics/_trials.py:33-34`); `laplacian_reference` keeps input row order, `bipolar_reference` depth order (`spectral/_reference.py:73-79,86,142`) | Hamm, one ruling each, then code | deferred-0.2.18 |
| 17-133 | Tests that skip on every CI leg (P-216-08) | the `validate` extra, torch and jax, the Dryad parity data, the Chromium theme test, omission, commit replay in a shallow checkout, GPU; `workflow.yml` installs `.[test,docs,vis,wavemap]` and sets no `fetch-depth`. Check: each skip runs on one leg, fails under a `JNWB_REQUIRE_*` switch, or is declared, and closes on a PASSED line in a CI log | Hamm approves the tiered CI plan and rules torch, jax, GPU, omission and the Dryad reference; h5py cp315 wheels for Windows | deferred-0.2.19 |
| 17-134 | Rule pairs that disagree (P-216-15) | eight pairs: baseline fast-forward or stop; who writes `dev`; who edits the todo and open stacks; two lane return formats; fragments or `CHANGELOG.md`; loop letters; one-test or five-test extension; defaults in skills | Hamm, one ruling per pair; the other file then points to it | deferred-0.2.21 |
| 17-135 | Release-acceptance cites by number (P-216-16) | `CONTRIBUTING.md:110`, `goal.md:22,25`, `release_gate.py:1544,1737,1881,2188` and the fixpoint receipt cite numbered conditions of `AGENTS.md` §11, whose text has no numbers; the numbered text is `standing.md:153-171`. Check: each "condition N" resolves where it points | the 0.2.21 cycle; `goal.md` is Hamm's | deferred-0.2.21 |
| 17-136 | Stale rows in Hamm's files (P-216-17) | `standing.md:20,21,23,136` (corpus on `D:`, remote branch set, current cycle, `preflight` arity); `goal.md:19` cites absent roadmap rows and keeps the closed 0.2.14 table; joins 17-77 | Hamm's word on his files | deferred-0.2.21 |
| 17-137 | Stack form against the jarness template (P-216-18) | `state.md` ignored while check in reads it; id forms; 19 goal rows against a cap of 10; `roadmap.md` a second deferred stack; root 11 files and 9 folders against 4 and 6; "lane" has three meanings; `artifacts_check.py --status` prints 0 for every jnwb stack (a jarness defect) | Hamm rules the project form; the jarness keeper fixes `--status` | deferred-0.2.21 |
| 17-138 | Tracked rules that depend on local files (P-216-19) | `scripts/jnwb_push.sh:25-28` runs CI helpers from `~/.claude/bin`; the mistake log is in auto memory; `memory.md:8` cites a log that is gone; verifications go to jchat. Same class as 17-101 | Hamm: vendor the helpers or name the dependency | deferred-0.2.21 |
| 17-139 | `AGENTS.md` rules against jarness (P-216-20) | §8 keeps originals where jarness deletes a superseded note; §9's rule on unverified text names no scope; dead lines: the `docs/` fallback, the `problem_stack.md` pointer, the repeated reset rule | Hamm scopes §8 and §9 | deferred-0.2.21 |
| 17-140 | One concept, two names (P-216-21) | reviewer and verifier; integrator and keeper; the retired "problem" slot in the fact-action skill; `artifacts/scratch/` against the ignored `artifacts/_temp/`; the check order (`CONTRIBUTING.md:60` against `:383-389`). Check: grep finds the other name only in history | the 0.2.21 cycle; the skill line is Hamm's | deferred-0.2.21 |
| 17-141 | Flow steps with no performer or check (P-216-22) | the Seal step's "verify the sync"; an `artifacts/`-only push runs no test (`scripts/jnwb_push.sh:3-4,17-24`); the `state.md` and Writes checks landed in 17-117 | Hamm rules the `artifacts/` exemption and the Seal wording | deferred-0.2.21 |

## Fact closure

Items that hold UNHELD facts; signature types before the scans and holder fixes.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|

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
| 17-151 | Public docs state the adopted direction (`artifacts/direction.md`) | `README.md`, `docs/index.md`, `docs/architecture.md`, `docs/agents.md` lack the AI-assisted and autonomous analysis direction; Check as in the todo stack at `7ecaf327` | ruled 2026-11-22 off the 0.2.17 critical path; 17-99, 17-100 and 17-129 share its files | deferred-0.2.18 |
| 17-155 | Removal of three deprecated public names | `TFRAnalyzer.LEGACY_VIZ_BANDS`, `DEFAULT_BANDS`, `nwb_read_io(mode=)` deprecated in 0.2.17 (17-96) | ruled 2026-11-22: removal only after a check of compatibility commitments and downstream use | deferred-0.2.18 |
| 17-159 | One threshold refusal for both depth classifiers | `classify_layer_from_depth` refuses a NaN, Inf or negative `threshold` (507e4cfb); `enrich_units_dataframe` takes the same `threshold` and still gives 'Unknown' per unit for NaN (`addressing.py` calls `_depth_class_from_row` without `_refuse_bad_depth_arguments`) | refusing it there changes a public function's output and its `depth_unit` refusal; an estimand-parameter decision of the 0.2.18 cycle | deferred-0.2.18 |
| 17-160 | One home for the coherency normalization | `_psi_leave_one_out` (`jnwb/connectivity/_psi.py:109-113`) retypes `_coherency`'s `sxy / sqrt(sxx * syy)` with its zero guard on leave-one-out means; a shared normalizer over given means keeps one rule (found by the 17-94 survey verifier, 2026-11-23) | `_psi_leave_one_out` feeds the PSI null; a change reruns its tests and any receipt that hashes it | deferred-0.2.18 |
| 17-161 | Raises coverage past the public functions' own bodies | `tests/test_public_raises_documented.py` (17-128) checks the 163 functions in `jnwb.__all__` and their nested helpers; exceptions raised by called module helpers, 5 public-class methods (`ExecutionRecord.__post_init__`) and 51 functions exported only from `jnwb.paths` and `jnwb.testing` are unchecked (verifier, 2026-11-23); `assert_mergeable` needs a skill row first | Hamm's skill row for `assert_mergeable` | deferred-0.2.18 |
| 17-162 | Documentation form findings of the 0.2.17 §11 review | `artifacts/evidence/0.2.17/r2_documentation_review.md` (none blocks): one sentence on 13 pages and one on 11 (tutorial template; one snippet); the Python and CI version sentence in `README.md:43`, `docs/install.md:9`, `docs/index.md:23`; numbered H1s of pages 02 to 10 against nav order 02, 06, 04, 05, 07, 08, 09, 03, and nav labels unlike H1s; "Analyze" group order and Tutorials after 15 Analyze pages; "X is not Y" forms; 40-word table cells in page 10; "cluster permutation" vs "cluster-based" | 17-99 and 17-100 share the files | deferred-0.2.18 |
| 17-156 | Four cardless-receipt OCMA card specs (open row `OCMA-5`) | four drafts under `artifacts/process/ocma_card_specs/`, each `STATUS: draft-awaiting-Hamm`, with their flags (release mismatch, claim class, `synth_laminar_motif` outside `jnwb.__all__`, SciPy parity wording, Welch crossings) | ruled 2026-11-22 (A4): drafts and open decisions kept; Hamm rules each before card code | deferred-0.2.20 |
| 17-102 | Showcase and calibration files nothing names | 14 of 24 `openscope_glo/scripts/` and 8 of 23 `receipts/` (823 KB) named by no tracked file; `curation_calibration_0.2.13_raw.json` (49,820 lines) named by nothing | ruled 2026-11-22: the 0.2.20 scope reduces these to receipts of record; files and references kept until then | deferred-0.2.20 |

## Harness and gates

Gate reach before pruning; guards for the installed-wheel leg.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
