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
| W0 | 06-127 |
| W1 |  |
| W2 | 06-114, 06-115 |
| W3 | 06-118, 06-30, 06-120 |
| W4 | 06-24, 06-57 |
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

## W1. Freeze, sweeps and harness

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
Role: jnwb-developer. Skill: jnwb-population. Blocked by: none.
Writes: `jnwb/jrsa.py`, `tests/test_jrsa.py`.
Ruled 2026-09-22 (06-101): `p` and `q` are 0-d on `dev` (`0617d120`); indexing `p[0]` or `q[0]`
keeps returning the scalar in 0.2.6 with a `FutureWarning`, and 0.2.7 removes the shim.
Discriminator: `float(res.p)` without a warning; `res.p[0]` returns the same value with a
`FutureWarning`; `res.p.shape == ()`; a multi-lag result keeps shape `(n_lags,)` and no shim.
Accept: the packet hands back a Changed entry (0-d `p`, `q`) and a Deprecated entry (indexing).
Stop: the shim changes any value, dtype or arithmetic result of `p`.

### 06-120 Gate 15 checks the stack's stated counts

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/harness_gate.py`, `tests/test_harness_adversarial_gates.py`.
P-176. A stated item total that named no ids went stale twice and gate 15 passed. This stack no
longer states such totals; the gate makes their return fail.
Discriminator: a summary sentence stating an item total that differs from the live count fails.
Accept: P-176 closes.

## W3. Statistics surface, diagrams and the open-data example

### 06-118 `correlate` names its method

Release: required-0.2.6.
Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: none.
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
Role: docs-harness. Skill: jnwb-figures. Blocked by: none.
Writes: `docs/architecture.md`, `docs/assets/*.svg`.
Dual entry; code, documentation and tests with skill routing over them; the four-outcome decision;
NWB to analysis; the package boundary. One maintained source each, original to jnwb.
Stop: a figure would adapt the external prior art, whose licence forbids derivatives
(`artifacts/direction.md`).

## W4. Maintained figures, skill routing and references

### 06-24 Skill routing against live behaviour

Release: required-0.2.6.
Role: jnwb-developer. Skill: per skill. Blocked by: 06-114, 06-118.
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
Role: docs-harness. Skill: jnwb-figures. Blocked by: 06-30.
Writes: `docs/*.md`, `docs/assets/*.svg`, `docs/assets/*.png`, `docs/assets/figures/*.png`, `docs/generate_figures.py`, `docs/_theme_override.css`, `examples/quickstart_jnwb.py`, `tests/test_figure_form.py`.
Widened 2026-09-23 by ruling (P-178): the figure captions are on `dev`; the known-failure lists
of the retired lane were not taken. Repair, not pin: P-205 (opaque white rasters, the orphan
quickstart SVG), P-206 (the theme stylesheet paints dark chrome under both schemes, so G2 is
unobservable), P-207 (the fig08 title names `permute_labels`; the generator sign-flips), and the
contract page's counts (nine raster pages, not seven) and item identifiers (P-208).
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
Role: jnwb-developer. Skill: per module. Blocked by: 06-57.
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
Role: jnwb-developer. Skill: none. Blocked by: none.
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
Every repair landed after `a9993322` is verified here, by a verifier that implemented none of them, before its row closes. The pass at `9cecf53c` closed P-188, P-189, P-186, P-184, P-194, P-68, P-57, P-201, P-99, P-110, P-12 and the substitution-sweep widening, and re-opened P-56 and P-195. Current list: P-62 skill half (the GPU line in `skills/jnwb/SKILL.md`, re-worded 2026-09-23 after the pass found it incomplete). P-21 (`tests/test_substitution_class_sweep.py::test_depth_class_carries_the_geometric_vocabulary_and_layer_is_a_warned_copy` and `tests/test_metadata.py::TestDepthClassColumn`; judge the warning on write and the census default). P-114 (`tests/test_composition_aggregation_order.py::TestH6AccumulatorToDecibels::test_the_route_refuses_the_estimand_it_cannot_deliver`). The Granger order validation (`tests/test_granger_order_validation.py`). P-91 (`tests/test_statistics_api_split.py::test_exploratory_results_say_they_are_uncorrected`). The architecture page `docs/architecture.md` against `artifacts/direction.md`. P-34, P-127, P-128, P-132 (`tests/test_computational_order_sources_agree.py` and the two restated bounds). P-118 (each magnitude in `composition_subset_proposal_0.2.6.md` against its named test). P-211, P-212 (captions), P-213, P-214, P-215 (repaired at `26e6f276`). P-56 (gate 2 at `53aa3921`: `tests/test_gate2_ignores_nested_checkouts.py`, the `E-gitdir-to-the-roots-own-git` case; judge whether the worktree-list check adds anything the identity check does not). P-195 (STEP 0a at `0f26e836`: `tests/test_release_requires_no_blocker.py`, the heading-depth and unreadable-heading cases; on a pass the remaining Gate 17 gaps return to `DEFERRED->0.2.7`, since each fails safe). P-43, P-45, P-46, P-157, P-158, P-202 (the waiver export at `8f78c37a`: `tests/test_public_api_reachability.py` and the `test_missingness_row_*` tests; judge the exclusion of `hdmf_build_repair_context` and the ten-row table against the six-state ruling). The architecture reachability test (`tests/test_architecture_page_reachability.py`, landed without an item after its own seven mutants were killed; judge whether the skill-authority and agent-precondition patterns are wide enough to mean anything). P-183, P-187, P-222 (`docs/vis.md` in the navigation, its example run against the installed extra, the `docs/install.md` star-import sentence, and the `jnwb.vis` docstrings against what each panel computes). P-217 and the fig09 half of P-212 (`tests/test_generated_figures_are_maintained.py`: judge the tolerance against its measurements and the minor-version skip as a hole). The figure captions from lane `fig` other than those P-212 names were verified at `9cecf53c`.
Do: re-run each discriminator against the exact diff; show the selector passes pristine before counting a kill; try one input the check should catch.
Accept: each listed row carries a receipt the verifier produced, or the breaking case is reported; the list is empty when this item is deleted.

## Closure

### 06-34 Adversarial mutation pass

Release: required-0.2.6.
Role: critic. Skill: none. Blocked by: 06-17, 06-24, 06-25, 06-51, 06-53, 06-59. Writes: none.
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

Frozen 2026-09-23 (06-05, closed), each line re-established against the live tree; the non-goals under "Out of 0.2.6 scope" are frozen with it. Each line names what establishes it.

| Line | Established by |
|---|---|
| no known material defect under the 0.2.6 acceptance set | 06-34, 06-39 |
| one canonical scientific model, published and reachable | `docs/architecture.md` (in the navigation since `d3d17871`), `tests/test_architecture_page_reachability.py`, 06-30 |
| every public claim reproduced against the implementation that answers it | 06-17, 06-24, 06-136 |
| skills route, decline, and are tested against live behaviour | 06-24, 06-25 |
| cross-surface and compositional audit complete over the declared high-risk set | `artifacts/evidence/0.2.6/composition_subset_0.2.6.md` and its proposal, every magnitude naming a committed test and seed (re-stamped 2026-09-23) |
| documentation assets render and are regenerable | `tests/test_generated_figures_are_maintained.py`, 06-36 |
| one real NWB end-to-end example with provenance | `examples/tutorials/09_open_data.py` (verified at `a9993322`; P-199 and P-200 carry its gaps), 06-32 |
| published artifact independently verified, from TestPyPI before publication and from PyPI after | 06-37, 06-38, 06-40 |
| documentation low-verbosity and consistently formed, against a declared contract | 06-51, 06-52, 06-53, 06-119 |
| one precision switch and one execution switch; CPU, parallel CPU and CUDA exercised here | 06-56, 06-59 |
| every declared interpreter qualified by CI on Ubuntu and Windows, and every surface declaring the same set | gate 8, CI on `dev`, 06-35 |
| a read invents no metadata, and a named waiver is recorded as it happened | `tests/test_nwb_read_tolerance_and_visibility.py`, `tests/test_public_api_reachability.py` |
| `jnwb.vis` is an optional extra and `import jnwb` works without it | `tests/test_optional_vis_extra.py`, 06-37 |
| suite wall time and the slowest tests measured before release | 06-121 |
| no release-blocking problem and no required item remaining, confirmed by a blocker-focused pass | 06-60, `scripts/release_gate.py` STEP 0a |

The form matches 0.2.5's closure: no known material defect under a stated acceptance set, not a
claim of exhaustive correctness. Deliberately absent: a claim that the JAX Metal backend works; it
is implemented and declared unverified.
