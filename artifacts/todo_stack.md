# 0.2.6

The remaining work of the 0.2.6 cycle, reorganized 2026-09-22 so that executing it in the order
below reaches the release. Items are deleted when done; git, `CHANGELOG.md` and the receipts hold
history. The previous cycle's record is `artifacts/archive/0.2.5/todo_stack_0.2.5.md`.

0.2.6 is a coherence, reachability and evidence release. It is measured against
`artifacts/goal.md` and opens under the three conditions of `AGENTS.md` §11. Deferred work and the
0.2.7 sequence are in `artifacts/planned_post_0.2.6.md`. Rulings are in `artifacts/rulings/`.

## How this stack is executed

Every item is a delegation packet in the contract of `skills/jnwb-fact-action` §5; the executing
role is `jnwb-developer` (`artifacts/agents/jnwb-developer.md`) unless the item names another.
Map the fields onto the packet: `Role` ROLE, `Skill` DOMAIN SKILL, heading GOAL, id TODO ITEM,
`Reads` extra AUTHORITIES, `Reproduce` OBSERVED BASELINE, `Writes` ALLOWED SCOPE, `Accept`
ACCEPTANCE, `Stop` STOP CONDITIONS.

| Rule | Why it binds |
|---|---|
| `AUTONOMY: max` unless the item says otherwise (`AGENTS.md` §12) | the actor and critic sequence the work and continue past a failing test or a surviving mutant |
| One writable agent per worktree; a lane runs `scripts/verify_lane.py --baseline <commit>` before its first write | a shared tree has silently lost green tests here |
| One item per packet | a batched packet reports the easy items and redefines the hard one |
| The actor is never the verifier | every `repaired` is re-run against the exact diff by someone else |
| Non-reproduction is a result | an imported finding that does not reproduce is returned `unsupported` and its item deleted |
| A contradiction stops the packet | two sources disagreeing on one quantity go to `authority` |
| The dispatcher owns the stacks, `CHANGELOG.md` and `docs/api.md` | a packet reports the disposition, the changelog text and the export change; the dispatcher writes them and regenerates `docs/api.md` at the wave barrier |
| Wave barrier | `python scripts/harness_gate.py` (count the PASS lines), `python -m pytest tests/ -q`, commit, push, confirm CI on `dev` |

Standing stop conditions on every packet: a repair needs a path outside `Writes`; the premise is
already false; acceptance would need invented evidence or a human ruling; a secret would enter the
repository or a transcript.

Item fields: `Release`, `Role`, `Skill` (a skill directory or `none`, `per skill`, `per module`,
`per finding`, `per chain`), `Blocked by` (live item ids or `none`), `Reads`, `Writes` (exact paths
or globs, never a bare directory), `Reproduce`, `Do`, `Discriminator` (fails before, passes after),
`Accept`, `Stop`.

## Execution order

Items in one wave have disjoint `Writes`, resolved by path and closed under generation; run them
in any order, at most two agents at a time unless Hamm raises the cap. Close each wave with the
barrier above.

| Wave | Items |
|---|---|
| W0 | 06-127, 06-122, 06-131, 06-64, 06-83, 06-99 |
| W1 | 06-05, 06-06, 06-16, 06-74, 06-105, 06-86, 06-124, 06-33, 06-123 |
| W2 | 06-07, 06-14, 06-82, 06-114, 06-115, 06-116, 06-117, 06-95, 06-120, 06-135 |
| W3 | 06-118, 06-30 |
| W4 | 06-29, 06-24, 06-57 |
| W5 | 06-52, 06-56, 06-25 |
| W6 | 06-58, 06-32 |
| W7 | 06-59, 06-125, 06-129 |
| W8 | 06-119, 06-121 |
| W9 | 06-51 |
| W10 | 06-53 |
| Rolling | 06-136, re-dispatched at each wave barrier over the repairs landed since its last run |
| Closure | 06-34, then 06-35 06-36 06-37 in any order, then 06-38, 06-39, 06-60, 06-130, 06-40 |

06-17 dispatches one packet per finding into whichever wave its declared paths fit, and all of its
packets finish before 06-34.

## W0. Integration and verification

### 06-127 `jnwb.vis` ships as the optional `vis` extra

Release: required-0.2.6.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: none.
Writes: `pyproject.toml`, `.github/workflows/workflow.yml`, `jnwb/__init__.py`, `jnwb/_lazy_exports.py`, `jnwb/vis/*.py`, `packages/jnwb-vis/*`, `tests/test_vis.py`, `tests/test_docs_decoding_chain.py`, `tests/test_errors_documented.py`, `tests/test_skills_validation.py`, `skills/jnwb-landmark-viz/SKILL.md`.
Ruled 2026-09-22: keep `jnwb.vis` in 0.2.6 as an optional extra. `178b1777` added it with an
undeclared `plotly`, a byte-duplicate under `packages/jnwb-vis/` and a new skill, and turned CI red
on all six legs (three modules fail collection) and gates 4, 5, 9 and 18.
Do: declare `plotly` under `[project.optional-dependencies] vis`; `import jnwb` and every core
export work without it, and `jnwb.vis` raises `ImportError` naming `pip install jnwb[vis]`;
CI installs the extra; delete the duplicate after hashing every pair; add the skill to the
canonical set and fix only rows that disagree with `inspect.signature`.
Discriminator: a subprocess test with `plotly` blocked imports `jnwb` and gets the named
`ImportError` from `jnwb.vis`; removing the guard fails it.
Accept: 18 PASS lines; CI green on every leg; the dispatcher adds the `AGENTS.md` §7 row, the
`CHANGELOG.md` Added entry and the P-33 note; the skill count is ruled (twelve planned, P-180).
Stop: a file pair under `packages/jnwb-vis/` differs from `jnwb/vis/`.

### 06-122 Verify the repairs of 2026-09-22

Release: required-0.2.6.
Role: verifier. Skill: none. Blocked by: none. Writes: none.
Covers P-53 and P-57 (gate 17, and `scripts/release_gate.py` STEP 0a for `Answered in`), P-61,
P-62 (skill half), P-99, P-151 (gate 18), P-165, P-177, P-179, the `t0_bounds_ms` example in
`skills/jnwb-spiking/SKILL.md`, P-181 (`skills/jnwb/SKILL.md` on `jrsa`), P-170 (the PSI spectrum sign), the open-data example (`09_open_data.py`, its excerpt builder and the clock derivation, `02502805`), P-174 (the journal read before replay, and release STEP 2a running `KNOWN_GAPS` in a detached worktree of HEAD), and the 06-95 docstring scope (P-110, cherry-picked as `917352fe`).
One packet per diff. An independent critic already ran mutants against gates 17 and 18 and the
`jrsa` checks; its receipts are the starting point, not the verdict.
Do: re-run each discriminator from the diff; show every selector passes pristine before counting a
failure as a kill.
Accept: each row's closure carries a receipt the verifier produced, or the verifier reports the
case that breaks it.

### 06-131 Attack every deferral

Release: required-0.2.6.
Role: critic. Skill: none. Blocked by: none. Writes: none.
`AGENTS.md` §11 requires a second independent pass over every proposed `DEFERRED`. The 2026-09-22
reorganization deferred seven items to 0.2.7 and reclassified P-84 and P-162 to `DEFERRED`.
Do: for each `DEFERRED->0.2.7` row and each item moved to `artifacts/planned_post_0.2.6.md`, answer
one question with evidence: could this defect make any evidence used to qualify this release
falsely pass? P-162 first.
Accept: every deferral is upheld with its answer, or restored to `BLOCKER` and given an item.

### 06-64 Verify the repairs of 2026-09-19

Release: required-0.2.6.
Role: verifier. Skill: none. Blocked by: none. Writes: none.
The seven repairs landed that day with their author's receipts only: gate 8 classifier versus
matrix, the `jrsa.py` correction fallback, gates 2 and 4 on nested checkouts, `read_nwb`
`allow_missing` and the squeeze warning, collect-all gate reporting, the test-provenance scanners,
and the gate-order tests. P-37 names the shared risk: a proxy mistaken for the invariant.
Do: re-run each discriminator from the diff, and for each ask whether the new check is the
invariant or a better-shaped proxy.
Accept: each claim independently reproduced, or the disagreement stated with its evidence.
Stop: a repair cannot be verified without changing it.

### 06-83 Verify the gate-2 administrative-entry repair

Release: required-0.2.6.
Role: critic. Skill: none. Blocked by: none. Writes: none.
P-56. `_is_git_admin_entry` requires a directory holding `HEAD`, or a file whose first line is
`gitdir:`. Establish whether that is the invariant: a directory holding an empty `HEAD`; a
`gitdir:` file pointing at a missing path; a real worktree whose admin directory is unreadable;
and, observed 2026-09-22 on this machine, an admin directory missing `commondir`.
Accept: P-56 closes `repaired` with the evidence, or re-opens with the breaking case; the
disposition is handed to the dispatcher.

### 06-99 Verify the container-type predicate against the corpus

Release: required-0.2.6.
Role: verifier. Skill: jnwb-nwb-data. Blocked by: none. Writes: none.
Corpus read granted 2026-09-22: read the raw NWB on `D:`, write only to `E:` or the scratchpad,
and copy no corpus identifier into `jnwb/`, `docs/`, `skills/` or `tests/`.
P-54. The predicate fires when the declared type has a schema-fixed data unit and the stored unit
differs. Record per session the declared `neurodata_type`, the stored `data` unit and the dtype of
each acquisition container; read attributes only. P-54's own count (22 sessions against 24 files
under `D:/nwb`) is under test.
Accept: the predicate's behaviour on the corpus is stated with counts; P-54 closes `repaired`, or
the predicate is corrected.

## W1. Freeze, sweeps and harness

### 06-05 Freeze the acceptance set

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none. AUTONOMY: none.
Writes: `artifacts/todo_stack.md`.
Rulings R-2 and R-3 of 2026-09-22 settled the last two lines: "decline" stays in 0.2.6, and
index verification uses a TestPyPI candidate before publication.
Do: re-establish every line of the Acceptance section against the live tree; each line names the
item or check that establishes it, and a line that names neither does not enter the set.
Accept: the Acceptance section is dated as frozen, and the non-goals are part of it.

### 06-06 Publish the canonical architecture page

Release: required-0.2.6.
Role: docs-harness. Skill: jnwb. Blocked by: none.
Reads: `artifacts/direction.md`.
Writes: `docs/architecture.md`, `mkdocs.yml`, `docs/index.md`, `docs/agents.md`.
Do: carry the durable content of the direction ruling into a maintained page: identity, the two
entry paths, the code/documentation/tests relation with skills acting on it, the four routing
outcomes, the boundary test. No ruling or process language.
Accept: `python scripts/docs_build.py` builds strict and the page is in the navigation.

### 06-16 Sweep the substitution class

Release: required-0.2.6.
Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: none.
Writes: `tests/test_substitution_class_sweep.py`, `jnwb/export.py`, `jnwb/jrsa.py`.
Live hits repaired in `b541bb33` (`jrsa` `align`, `reduction`, `alternative`). Remaining:
P-21 (two exports emit a `layer` column whose values are not layer labels, one reading `Unknown`),
and the two scanner blind spots the critic measured: a selector chain nested in an `if` body is
never scanned, and a chain with no `else` is skipped although that is the shape `_resample_axis`
had before its repair.
Discriminator: seeded instances of both blind-spot shapes are found; the live tree finds nothing
unrepaired.
Accept: P-21 closes; the instrument lists what it cannot see in `INSTRUMENT_BLIND_SPOTS`, and that
list matches measurement.
Stop: the `layer` exports live outside `jnwb/export.py`; name the file and widen deliberately.

### 06-74 Dispose of the collection-order fragility

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `tests/test_collection_order_stability.py`.
P-12. The subset that segfaulted is pinned (`b541bb33`; the critic reproduced 3 of 3 crashes with
the old `tests/test_analyzers_coverage.py`). Remaining: on CI legs without torch the pin passes
without testing anything; and the `patch.dict(sys.modules)` detector misses the string-target
form and aliased imports.
Accept: P-12 closes `repaired`, with the torch-absent case stated as skipped with a reason or
exercised, and the detector covers both missed forms.

### 06-105 Gate 8 reads every surface the goal names

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/harness_gate.py`, `tests/test_gate8_covers_every_version_surface.py`.
P-68, ruled 2026-09-22: widen the gate. Gate 8 reads `.github/`, `.readthedocs.yaml` and
`pyproject.toml`, and not `README.md` or `docs/install.md`.
Discriminator: a skewed version in `README.md`, and separately in `docs/install.md`, fails the
gate; the selector passes pristine first.
Accept: P-68 closes `repaired`; `artifacts/goal.md` is not edited.

### 06-86 Name the quantity each order document measures

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `artifacts/benchmarks/complexity_inventory.md`, `artifacts/evidence/0.2.6/computational_order.md`, `tests/test_computational_order_sources_agree.py`.
Ruled 2026-09-22 (P-34, P-127): the inventory records `O` upper bounds justified by the algorithm
and its published reference, and drops "verified"; timed exponents stay a separate, labelled
benchmark with at least three input scales per row.
Do: apply the ruling; resolve the 23 `INV-` labels cited from `computational_order.md` (P-128),
and repair the sentence P-132 names. Do not re-baseline either document to the other.
Discriminator: a row stating an exponent with no named method fails the new test.
Accept: P-34, P-127, P-128 and P-132 close.

### 06-124 Re-stamp the high-risk subset from committed generators

Release: required-0.2.6.
Role: jnwb-developer. Skill: per chain. Blocked by: none.
Writes: `artifacts/evidence/0.2.6/composition_subset_proposal_0.2.6.md`.
P-118. Every magnitude cited from the uncommitted `probe_axis*` and `probe_tfr` receipts is
replaced by the value a committed test produces, naming the test and its seed; a cell with no
committed generator is marked unmeasured.
Discriminator: `probe_axis` and `probe_tfr` no longer occur in the file.
Accept: P-118 closes, and the Acceptance line on the high-risk set names this file.

### 06-33 Retain the benchmark design as explicitly unrun

Release: required-0.2.6.
Role: docs-harness. Skill: none. Blocked by: none.
Writes: `artifacts/planned_post_0.2.6.md`.
Bring the ruled benchmark hypothesis to pre-registration quality: task set, scoring rubric, arms,
repetitions, refusal scoring, inferential unit. It is a non-goal of 0.2.6 and gates nothing.
Accept: every element is declared and the section states that none of it has run.

### 06-123 Review the figure-form lane and close P-178

Release: required-0.2.6.
Role: critic. Skill: jnwb-figures. Blocked by: none. Writes: none.
P-178. Triage of 2026-09-22 removed 48 worktrees whose work was on `dev`, and 06-95 was
cherry-picked as `917352fe`. Left: lane `fig` (`C:/workspace/jnwb-lanes/fig`), which holds 06-52
work that pins every failing raster as a known-failure list instead of repairing it.
Do: say what in that lane is sound and belongs in 06-52, and what repeats the P-37 shape.
Accept: a recommendation per file; P-178 closes when Hamm has ruled on it and the tree is removed.

### 06-129 Problem identifiers stay out of `jnwb/`

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `jnwb/*.py`, `scripts/harness_gate.py`, `tests/test_harness_adversarial_gates.py`.
P-182. Comments and docstrings across `jnwb/` cite problem ids (`P-29`, `P-83`, `P-85`, `P-145`)
and item ids (`05-36`, `06-55`, `06-84`), which the head rule of `AGENTS.md` keeps out of the
library surface, and no gate scans `jnwb/` for them. Scheduled last among the `jnwb/` writers,
because every earlier wave edits some module it touches. Dates such as `2026-08-08` are not ids.
Do: state each behaviour without its identifier; extend the gate that scans `jnwb/` for internal
vocabulary to item and problem identifiers.
Discriminator: a seeded `P-12` in a `jnwb/` docstring fails the gate; the pristine tree passes.
Accept: P-182 closes.
Stop: an identifier carries meaning a reader of the library needs; state the meaning instead.

## W2. API repairs

### 06-07 Gate architecture reachability

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: 06-06.
Writes: `tests/test_architecture_page_reachability.py`.
Assert: the page is a navigation target; `docs/agents.md` links it; no maintained asset draws a
researcher-through-AI chain; the public identity does not require an agent; no maintained asset
describes skills as an implementation authority.
Discriminator: reinsert the chain into a maintained page, or drop the nav entry; the test fails.
Accept: behaviour-shaped assertions only; a whole-prose snapshot fails this item.

### 06-14 `granger_causality` validates `order`

Release: required-0.2.6.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: none.
Writes: `jnwb/connectivity.py`, `tests/test_granger_order_validation.py`, `docs/08_directed_connectivity_and_information.md`, `skills/jnwb-connectivity/SKILL.md`.
Reproduce: `int(order)` in `granger_causality` has no domain check.
Discriminator: mutation-kill the validation, with the selector passing pristine first.
Accept: an invalid order raises instead of returning a plausible number; documentation and the
skill row agree with the implementation.

### 06-82 Reach the waiver from the public API

Release: required-0.2.6.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `jnwb/__init__.py`, `jnwb/nwb_io.py`, `docs/errors.md`, `tests/test_public_api_reachability.py`, `tests/test_nwb_read_tolerance_and_visibility.py`.
P-43, P-45, P-46, P-157, P-158. `read_nwb`, `nwb_read_io`, `hdmf_build_repair_context` and
`SqueezedAttributeWarning` are outside `__all__`, so the ruled waiver is reachable only through a
submodule. A soft link to a valid description is refused. Ruled 2026-09-22 (06-67, option (d)):
`jnwb_waived_requirements` records the waiver that happened on this read; no value changes and no
read starts or stops failing.
Do: export the remedy beside the error; resolve the soft link; document the missingness table in
`docs/errors.md` with the three integrity states P-45 names (dangling soft link, broken external
link, NUL-byte string), one test per row.
Discriminator: a caller catching `MissingRequiredNWBFieldError` reaches the waiver without a
submodule import; the soft-link file opens with its description and no waiver.
Accept: P-43, P-45, P-46, P-157 and P-158 close.

### 06-114 `compress_fp32` takes an explicit selection

Release: required-0.2.6.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `jnwb/compression.py`, `tests/test_compression.py`, `skills/jnwb-nwb-data/SKILL.md`.
Ruled 2026-09-22 (06-13, option (b) staged). Keyword-only `select=` (dataset paths to cast) on
`compress_fp32` and `convert`. A call naming no selection keeps the anchored preset and emits
`FutureWarning` that `select=` becomes required in 0.2.7. A guarded path in `select=` raises
instead of returning a no-op with a false provenance stamp (P-104).
Discriminator: a silent call warns and its output is byte-identical to today's; `select=` naming
the preset's paths does not warn and gives the same bytes; a guarded path raises.
Accept: P-104 closes; the packet hands back an Added entry for `select=` and a Deprecated entry
for the implicit preset.
Stop: any selection rule other than an explicit path list.

### 06-115 `JRSAResult.p[0]` keeps working for one release

Release: required-0.2.6.
Role: jnwb-developer. Skill: jnwb-population. Blocked by: 06-16.
Writes: `jnwb/jrsa.py`, `tests/test_jrsa.py`.
Ruled 2026-09-22 (06-101): `p` and `q` are 0-d on `dev` (`0617d120`); indexing `p[0]` or `q[0]`
keeps returning the scalar in 0.2.6 with a `FutureWarning`, and 0.2.7 removes the shim.
Discriminator: `float(res.p)` without a warning; `res.p[0]` returns the same value with a
`FutureWarning`; `res.p.shape == ()`; a multi-lag result keeps shape `(n_lags,)` and no shim.
Accept: the packet hands back a Changed entry (0-d `p`, `q`) and a Deprecated entry (indexing).
Stop: the shim changes any value, dtype or arithmetic result of `p`.

### 06-116 `aggregate_to_db` refuses an estimand it cannot deliver

Release: required-0.2.6.
Role: jnwb-developer. Skill: jnwb-lfp-spectral. Blocked by: none.
Writes: `jnwb/spectral.py`, `tests/test_tfr_accumulator.py`.
P-114, ruled 2026-09-22: refuse now, deliver in 0.2.7. `how="mean_of_ratios"` on input a
`TFRAccumulator` has already averaged over trials raises `ValueError` naming the estimand and the
per-trial route that delivers it.
Discriminator: the accumulator route with `mean_of_ratios` raises; `ratio_of_means` through it is
unchanged; per-trial input with `mean_of_ratios` is unchanged.
Accept: P-114 closes; the packet hands back a Changed entry.
Stop: recognising trial-averaged input needs a new public marker, which is an API decision.

### 06-117 Exploratory results say they are uncorrected

Release: required-0.2.6.
Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: none.
Writes: `jnwb/statistics.py`, `tests/test_statistics_api_split.py`, `skills/jnwb-statistics/SKILL.md`.
P-91, ruled 2026-09-22: `exploratory_compare` and `exploratory_multi` results gain
`correction: "none"`; `multiple_comparison` stays off the exploratory surface.
Accept: both results carry the key with value `"none"` and neither carries `multiple_comparison`;
P-91 closes; the packet hands back an Added entry.

### 06-95 Close P-110 on the landed scope

Release: required-0.2.6.
Role: verifier. Skill: jnwb-spiking. Blocked by: none. Writes: none.
The docstring repair landed as `917352fe`. The 06-93 mutant (a second, unscoped instruction
leaving every word intact) must fail the pinned assertion.
Accept: the mutant is killed on the landed code; P-110 closes `repaired`.

### 06-120 Gate 15 checks the stack's stated counts

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/harness_gate.py`, `tests/test_harness_adversarial_gates.py`.
P-176. A stated item total that named no ids went stale twice and gate 15 passed. This stack no
longer states such totals; the gate makes their return fail.
Discriminator: a summary sentence stating an item total that differs from the live count fails.
Accept: P-176 closes.
Stop: 06-105 also writes `scripts/harness_gate.py`; the two run one after the other.

### 06-135 A page for `jnwb.vis`

Release: required-0.2.6.
Role: docs-harness. Skill: jnwb-figures. Blocked by: none.
Writes: `docs/vis.md`, `mkdocs.yml`, `docs/install.md`.
P-187, P-183. The public `jnwb.vis` is reachable only through an `install.md` line and its `api.md` row. Ruled 2026-09-22 (P-183): `vis` stays in `__all__`, so `from jnwb import *` without the extra raises an `ImportError` naming `pip install jnwb[vis]`; the page and `docs/install.md` say so.
Accept: the page is in the navigation, shows one canvas built from supplied arrays, and the strict build passes; P-183 and P-187 close.

## W3. Statistics surface, diagrams and the open-data example

### 06-118 `correlate` names its method

Release: required-0.2.6.
Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: 06-117.
Writes: `jnwb/statistics.py`, `tests/test_statistics.py`, `skills/jnwb-statistics/SKILL.md`.
P-92, P-93, ruled 2026-09-22. `correlate` and `exploratory_correlate` gain keyword-only `method=`
(`"both"`, `"pearson"`, `"spearman"`), default `"both"`. Every additive public API change gets an
Added entry and needs no deprecation path, so this packet also hands back the missing Added entry
for 06-45's `method=`.
Discriminator: each method returns only its statistic; `"both"` is value-identical to today; an
unknown method raises.
Accept: P-92 and P-93 close.

### 06-30 Produce the canonical diagrams

Release: required-0.2.6.
Role: docs-harness. Skill: jnwb-figures. Blocked by: 06-06.
Writes: `docs/architecture.md`, `docs/assets/*.svg`.
Dual entry; code, documentation and tests with skill routing over them; the four-outcome decision;
NWB to analysis; the package boundary. One maintained source each, original to jnwb.
Stop: a figure would adapt the external prior art, whose licence forbids derivatives
(`artifacts/direction.md`).

## W4. Maintained figures, skill routing and references

### 06-29 Make generated figures maintained

Release: required-0.2.6.
Role: docs-harness. Skill: jnwb-figures. Blocked by: none.
Writes: `docs/generate_figures.py`, `tests/test_generated_figures_are_maintained.py`, `scripts/harness_gate.py`.
Nothing runs the generator, and re-running it reproduces none of its outputs byte-identically.
Do: map every artifact to its generator, regenerate in isolation, gate on unexplained drift.
Accept: a tolerance the plotting stack meets, justified by measurement; neither byte equality nor
a tolerance wide enough to accept a changed figure.

### 06-24 Skill routing against live behaviour

Release: required-0.2.6.
Role: jnwb-developer. Skill: per skill. Blocked by: 06-82, 06-114, 06-117, 06-118.
Writes: `skills/*/SKILL.md`, `tests/test_skills_validation.py`.
One packet per skill. Every routing row: the callable exists, the signature matches, the return
type and keys match, units match, failure behaviour matches, including conditional return
schemas. The validator is delivered; the rows of eight skill files are unchecked (P-103).
Accept: every claim checked by execution against the live export.

### 06-57 Cite the reference where the implementation matches it

Release: required-0.2.6.
Role: jnwb-developer. Skill: per module. Blocked by: none.
Writes: `jnwb/*.py`, `docs/references.md`.
Under the 2026-09-19 ruling, conformance to an official reference is the evidence of correctness.
Accept: every citation resolves and names the specific result implemented.
Stop: implementation and reference differ; a deliberate divergence is documented where it
happens, an undocumented one goes to the problem stack.

## W5. Figures, execution switch and decline

### 06-52 Figures that carry structure

Release: required-0.2.6.
Role: docs-harness. Skill: jnwb-figures. Blocked by: 06-29, 06-30, 06-123.
Writes: `docs/*.md`, `docs/assets/*.svg`, `tests/test_figure_form.py`.
Rules G1-G4 of `docs/documentation_form.md`. Place the canonical diagrams as inline SVG; the
seven raster PNGs stay unless one fails G1 or G2, which is then fixed and named.
Discriminator: switch the palette scheme; a figure with a hardcoded colour is caught.
Accept: every figure satisfies G1-G4 and is referenced by its prose; P-26 closes.

### 06-56 One execution switch

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: 06-57.
Writes: `jnwb/*.py`, `tests/test_execution_switch.py`.
Every backend-taking export either selects a backend or rejects the argument; a fallback is
announced and names what ran. One mechanism for CPU, parallel CPU, CUDA and JAX Metal.
Discriminator: request an unavailable backend; it fails or warns naming what ran.
Accept: CPU, parallel CPU and CUDA agree within a stated tolerance on the high-risk subset,
measured here; Metal is implemented and declared unverified; P-62's code half closes.
Stop: two backends disagree beyond tolerance.

### 06-25 Decline behaviour as executable evidence

Release: required-0.2.6.
Role: jnwb-developer. Skill: per skill. Blocked by: 06-24.
Writes: `tests/test_skill_decline_behaviour.py`, `skills/*/SKILL.md`.
Ruled 2026-09-22 (R-2): decline stays in 0.2.6. For each applicable skill, representative cases
for the four outcomes of `artifacts/direction.md`: supported routes; missing input is requested;
a non-identifiable result is reported as a failure; an unsupported claim is declined. The check is
that the routed operation raises, returns a declared failure or requests the input.
Accept: each skill satisfies this or is recorded as not requiring it.

## W6. Orders and empirical labelling

### 06-58 Reduce the orders the inventory named

Release: required-0.2.6.
Role: jnwb-developer. Skill: per module. Blocked by: 06-57, 06-86.
Writes: `scripts/measure_order.py`, `jnwb/connectivity.py`, `jnwb/io.py`.
The queue is section 10 of `artifacts/evidence/0.2.6/computational_order.md`. Two named:
`phase_slope_index` measures +2.14 in `n_samples` against an admissible linear order through its
default jackknife; `stream_npz_array` reads and discards instead of seeking, 710x slower at 1.6e7.
Each packet first establishes the exponent is stable, why the path scales so, and whether it
violates a performance contract. The measurement script is committed (P-131).
Accept: the new order is measured, and every numerical result is unchanged within a stated
tolerance against a frozen output; P-131 closes.
Stop: the faster order changes results beyond tolerance.

### 06-32 Separate empirical from synthetic

Release: required-0.2.6.
Role: docs-harness. Skill: jnwb-figures. Blocked by: none.
Writes: `docs/*.md`, `examples/*.py`, `tests/test_synthetic_figures_are_labelled.py`.
Accept: a page carrying a synthetic figure says so, checked mechanically.

## W7. Contracts

### 06-59 Gate the computational contract

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: 06-56, 06-58.
Writes: `scripts/computational_contract_gate.py`, `tests/test_computational_contract_gate.py`.
A backend argument that selects nothing fails; a precision request silently ignored fails; an
export added without a recorded order fails.
Accept: every check fails on its own seeded violation and passes on the live tree.

### 06-125 Documented gate counts follow `GATES`

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: 06-29.
Writes: `AGENTS.md`, `CONTRIBUTING.md`, `artifacts/agents/docs-harness.md`, `tests/test_module_docstrings_match_their_code.py`.
P-126, recurred: `GATES` holds 18 entries while four surfaces say 16. Remove the number from the
prose, or derive it at check time.
Discriminator: a prose count that disagrees with `len(GATES)` fails.
Accept: P-126 closes `repaired`.

## W8. Vocabulary and cost

### 06-119 One glossary

Release: required-0.2.6.
Role: docs-harness. Skill: none. Blocked by: none.
Writes: `docs/glossary.md`, `docs/*.md`, `mkdocs.yml`.
P-96, ruled 2026-09-22: operation; workflow (jnwb ships no pipeline); session is one NWB file and
recording is a continuous series within it; contact is a physical site and channel is a data row;
electrode is one row and electrodes table is the NWB table. Each page uses the defined term.
Accept: P-96 closes; the page is in the navigation; the strict build passes.

### 06-121 Suite cost is measured before release

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/release_gate.py`, `tests/test_semantic_mutation_classes.py`, `tests/test_every_gate_runs.py`, `CONTRIBUTING.md`.
Goal section 8. The 2026-09-22 run took 1241 s; `test_every_class_is_demonstrated_over_the_declared_subset`
took 347 s of it. Reduce the two heaviest tests without losing a demonstrated class or a gate;
the release check prints wall time and the ten slowest tests.
Discriminator: removing a class or a gate from either test still fails it.
Accept: both measured before and after with `--durations`.

## W9-W10. Documentation form

### 06-51 Reduce verbosity against the contract

Release: required-0.2.6.
Role: docs-harness. Skill: none. Blocked by: 06-119.
Writes: `docs/*.md`, `README.md`.
One packet per authored page; the contract is `docs/documentation_form.md`. `docs/api.md` and the
tutorial wrappers are generated or included (P-25); a defect there goes to the generator or the
included script. Two pages have had a pass (P-103); `docs/02` and `docs/04` exceed the length
ceiling for a reason the contract records as a split.
Accept: each page satisfies every rule, and no fact present before is absent after.
Stop: a cut would delete a caveat a test or gate enforces.

### 06-53 Gate the documentation form

Release: required-0.2.6.
Role: docs-harness. Skill: none. Blocked by: 06-51, 06-52.
Writes: `scripts/docs_form_gate.py`, `tests/test_docs_form_gate.py`.
Vocabulary list, heading depth, nav shape, figure theme-independence, and a table where a page
states more than two comparable facts in prose.
Accept: every check fails on its own seeded violation and passes on the live tree; a rule that
cannot be a check is recorded in the contract as a review item.

## Any wave. Confirmed findings

### 06-17 Confirmed findings not claimed by another item

Release: required-0.2.6.
Role: jnwb-developer. Skill: per finding. Blocked by: none. Writes: none.
P-02. One packet per ledger entry in `artifacts/evidence/0.2.6/findings_0.2.6.md` disposed
`reproduced` and claimed by no other item, highest consequence first; each packet declares its own
paths from the finding's receipt.
Accept: each returns `repaired` with a discriminator, or `unsupported` with evidence.

## Rolling verification

### 06-136 Verify the repairs landed after `a9993322`

Release: required-0.2.6.
Role: verifier. Skill: none. Blocked by: none. Writes: none.
06-122 was dispatched at `a9993322`. Every repair landed after it is verified here, by a verifier that implemented none of them, before its row closes. Current list: P-188 (`parse_probe_areas` keeps a slash inside an atlas layer label; `tests/test_addressing.py::test_an_atlas_layer_label_is_one_location_and_two_areas_still_split`); P-189 (series inside containers resolve by name; `tests/test_acquisition_layout.py::TestASeriesInsideAnAcquisitionContainerIsReachableByName`); P-186 (release-gate STEP 7 passes without the `vis` extra; `tests/test_optional_vis_extra.py::test_the_release_gate_export_sweep_passes_without_plotly`). P-184 (`jnwb.vis` vocabulary; `git grep` the reported tokens over `jnwb/vis/`, `tests/test_vis.py` and `skills/jnwb-landmark-viz/SKILL.md`); P-194 (no default crossover depth; `tests/test_vis.py::test_no_crossover_depth_is_drawn_unless_the_caller_computed_one`). Deferrals to attack with 06-131's question: P-190, P-191, P-192.
Do: re-run each discriminator against the exact diff; show the selector passes pristine before counting a kill; try one input the check should catch.
Accept: each listed row carries a receipt the verifier produced, or the breaking case is reported; the list is empty when this item is deleted.

## Closure

### 06-34 Adversarial mutation pass

Release: required-0.2.6.
Role: critic. Skill: none. Blocked by: 06-16, 06-17, 06-24, 06-25, 06-51, 06-53, 06-59, 06-74. Writes: none.
Seed known semantic defects and require the intended gate to catch each; every selector collects
and passes pristine before a verdict counts.

### 06-35 Clean-environment matrix

Release: required-0.2.6.
Role: verifier. Skill: none. Blocked by: 06-34. Writes: none.
P-06, P-09. Every declared interpreter on Ubuntu and Windows, from a fresh environment; record
`jnwb.__file__` for each, because `C:\Python314\Lib\site-packages` holds a 0.2.5 copy and a backup.

### 06-36 Documentation qualification

Release: required-0.2.6.
Role: verifier. Skill: none. Blocked by: 06-34. Writes: none.
Strict build; diagrams render as diagrams, asserted against built output; generated assets
current; links resolve; no stale version claim; the architecture page reachable.

### 06-37 Distribution qualification

Release: required-0.2.6.
Role: verifier. Skill: none. Blocked by: 06-34. Writes: none.
P-04. Build the sdist and wheel into the scratchpad, not `dist/`, and point the distribution
checks at that build: contents, metadata, imports, exports, `SKILLS_URL`, the `vis` extra,
representative workflows, no checkout shadowing, no `examples/data` in the wheel.

### 06-38 Verify the candidate from TestPyPI

Release: required-0.2.6.
Role: verifier. Skill: jnwb-nwb-data. Blocked by: 06-35, 06-36, 06-37. Writes: none.
Ruled 2026-09-22 (R-3). The candidate is published to TestPyPI (authorized as part of 06-40's
sequence); in a clean environment install it from TestPyPI, open an NWB file, analyse, verify.
After production publication the same check runs from PyPI.

### 06-39 Independent critic

Release: required-0.2.6.
Role: critic. Skill: none. Blocked by: 06-38. Writes: none.
A reviewer that implemented none of the repairs, over the acceptance set, the unresolved unknowns,
the mutation evidence, the public claims and the release artifacts.

### 06-60 No blocker remains, confirmed by a pass that finds no new one

Release: required-0.2.6.
Role: critic. Skill: none. Blocked by: 06-39.
Writes: `artifacts/blocker_fixpoint_receipt.md`.
Condition 3 of `AGENTS.md` §11. One independent pass over the documentation, the code and both
stacks applying the blocker predicate. A new blocker re-opens the owning wave; a new non-blocking
observation is recorded `DEFERRED->0.2.7` and does not.
Accept: the receipt names the commit it ran against and reports zero new release-blocking
problems; `scripts/release_gate.py` STEP 0a accepts it only at HEAD.
Stop: a new blocker needs a human ruling; it is not reclassified to close the cycle.

### 06-130 Reconcile `main` with `dev` before the release pull request

Release: required-0.2.6.
Role: human. Skill: none. Blocked by: 06-60. AUTONOMY: none.
Writes: none.
P-180. `origin/main` is `9d738211`, a second copy of the `jnwb.vis` commit on top of the 0.2.5
release merge, while `dev` carries the same content as `178b1777`. A merge of `dev` into `main`
treats `packages/jnwb-vis/` as added on `main` and unchanged on `dev`, so the duplicate 06-127
deletes comes back.
Ruled 2026-09-22: revert on `main` first. `9d738211` is reverted on `main` in its own pull
request, which Hamm authorizes and merges; the verifier then confirms the release merge tree
equals `dev`.
Accept: `git diff dev <merge>` is empty on the release pull request.

### 06-40 Release

Release: required-0.2.6.
Role: human. Skill: none. Blocked by: 06-130. AUTONOMY: none.
Writes: `jnwb/__init__.py`, `CHANGELOG.md`, `README.md`.
dev green; pull request and `main` green; TestPyPI candidate (06-38); tag validates without
publishing; GitHub Release; production PyPI; verification from PyPI in a clean environment.

## Reported and not admitted

Recorded so that nothing reported disappears by not being chosen.

- `dist/` holds only 0.1.1, 0.1.3 and 0.2.4 artifacts; 06-37 builds fresh.
- The ninth unreadable consumer file fails at `root/units` with `Columns must be the same
  length`, separately from the eight that fail on device attributes.

## Out of 0.2.6 scope

Frozen with the acceptance set. Each needs its own authorization.

- Raw-data-to-NWB conversion.
- An authorization or permission subsystem.
- Benchmark execution; the design is retained and marked unrun (06-33).
- A capability-by-capability matrix over the whole public surface.
- Repository minimization: dead tests, hand-transcribed examples, root and documentation cleanup.
- Dataset-specific package code, and new estimators that only improve a demonstration.
- The 36 unverified review findings, except where an item reaches one.

## Acceptance

Frozen by 06-05. Each line names what establishes it.

| Line | Established by |
|---|---|
| no known material defect under the 0.2.6 acceptance set | 06-34, 06-39 |
| one canonical scientific model, published and reachable | 06-06, 06-07, 06-30 |
| every public claim reproduced against the implementation that answers it | 06-17, 06-24, 06-122, 06-64 |
| skills route, decline, and are tested against live behaviour | 06-24, 06-25 |
| cross-surface and compositional audit complete over the declared high-risk set | 06-124, `artifacts/evidence/0.2.6/composition_subset_0.2.6.md` |
| documentation assets render and are regenerable | 06-29, 06-36 |
| one real NWB end-to-end example with provenance | `examples/tutorials/09_open_data.py` (verified by 06-122), 06-32 |
| published artifact independently verified, from TestPyPI before publication and from PyPI after | 06-37, 06-38, 06-40 |
| documentation low-verbosity and consistently formed, against a declared contract | 06-51, 06-52, 06-53, 06-119 |
| one precision switch and one execution switch; CPU, parallel CPU and CUDA exercised here | 06-56, 06-59 |
| no release-blocking problem and no required item remaining, confirmed by a blocker-focused pass | 06-60, `scripts/release_gate.py` STEP 0a |

The form matches 0.2.5's closure: no known material defect under a stated acceptance set, not a
claim of exhaustive correctness. Deliberately absent: a claim that the JAX Metal backend works; it
is implemented and declared unverified.
