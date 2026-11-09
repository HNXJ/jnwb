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
| 12-21 | jnwb recovers a planted delay and a planted direction from a jaxfne field (validation) | The spectrum half landed (`tests/test_jaxfne_ground_truth.py`: `compute_psd` recovers the planted 10.0 Hz of jaxfne's protocol_c planar field, commit 21c99f96); a single-frequency field has no phase-slope delay and no direction, so delay (`phase_slope_index`) and direction (`granger`) wait for a broadband jaxfne field | A broadband jaxfne field with a stated delay or coupling; nothing shipped changes. Moved to 0.2.15 (ruled 2026-10-23: the spectrum test closes the item for 0.2.14); then 0.2.16 (ruled 2026-10-31), then 0.2.17 (ruled 2026-11-06). | deferred-0.2.17 |

## Rulings, form and CI reach

The open rows of the 2026-11-02 audit (eight auditors at `9fd2b4bd`, per
`artifacts/open_stack.md:35`), moved here by the release plan (ruled 2026-11-05) on
2026-11-06. Each row's full text: `git log -S '| P-216-NN |' -- artifacts/open_stack.md`, with the
number in the Theme cell.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
| 17-130 | Public parameter names (from P-216-25) | 17 time and frequency parameters lack unit suffixes; `window` has four meanings and the bin concept four names; `fs` beside `sampling_rate` | Hamm rules the public names (0.2.18 estimand and parameter decisions) | deferred-0.2.18 |
| 17-131 | `gaussian_smooth_rate` NaN handling (P-216-24) | no `nan_policy=` argument; a comment left in 17-110 calls the question undecided (`jnwb/spiking.py`) | Hamm rules the argument | deferred-0.2.18 |
| 17-132 | Estimand choices no ruling names (P-216-32) | response z uses `np.std` ddof 0 while Fano and CV use ddof 1 (`jnwb/spiking.py:191,969`); `detect_trial_cycles` median gap counts zero gaps (`statistics/_trials.py:33-34`); `laplacian_reference` keeps input row order, `bipolar_reference` depth order (`spectral/_reference.py:79,86,142`) | Hamm, one ruling each, then code | deferred-0.2.18 |
| 17-133 | Tests that skip on every CI leg (P-216-08) | the `validate` extra, torch and jax, the Dryad parity data, the Chromium theme test, omission, commit replay in a shallow checkout, GPU; `workflow.yml` installs `.[test,docs,vis,wavemap]` and sets no `fetch-depth`. Check: each skip runs on one leg, fails under a `JNWB_REQUIRE_*` switch, or is declared, and closes on a PASSED line in a CI log | Hamm approves the tiered CI plan and rules torch, jax, GPU, omission and the Dryad reference; h5py cp315 wheels for Windows | deferred-0.2.19 |
| 17-134 | Rule pairs that disagree (P-216-15) | eight pairs: baseline fast-forward or stop; who writes `dev`; who edits the todo and open stacks; two lane return formats; fragments or `CHANGELOG.md`; loop letters; one-test or five-test extension; defaults in skills | Hamm, one ruling per pair; the other file then points to it | deferred-0.2.21 |
| 17-135 | Release-acceptance cites by number (P-216-16) | `CONTRIBUTING.md:110`, `goal.md:22,25`, `release_gate.py:1644,1951` and the fixpoint receipt cite numbered conditions of `AGENTS.md` §11, whose text has no numbers; the numbered text is `standing.md:153-171`. Check: each "condition N" resolves where it points | the 0.2.21 cycle; `goal.md` is Hamm's | deferred-0.2.21 |
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

## Harness and gates

Gate reach before pruning; guards for the installed-wheel leg.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
