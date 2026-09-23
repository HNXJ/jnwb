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
| W0 |  |
| W1 |  |
| W2 |  |
| W3 |  |
| W4 |  |
| W5 |  |
| W6 |  |
| W7 | 06-142, 06-129 |
| W8 |  |
| W9 |  |
| W10 | 06-53 |
| Rolling | 06-136, re-dispatched at each wave barrier over the repairs landed since its last run |
| Closure | 06-34, then 06-35 06-36 06-37 in any order, then 06-38, 06-39, 06-60, 06-130, 06-40 |

06-17 dispatches one packet per finding into whichever wave its declared paths fit, and all of its
packets finish before 06-34.

## W0. Integration and verification

## W1. Freeze, sweeps and harness

### 06-142 Repair what the fourth verification pass broke

Release: required-0.2.6.
Role: jnwb-developer. Skill: per skill. Blocked by: none.
Writes: `jnwb/tfr_accumulator.py`, `jnwb/compression.py`, `jnwb/io.py`, `jnwb/addressing.py`, `jnwb/nwb_events.py`, `jnwb/spectral.py`, `tests/test_*.py`, `docs/install.md`, `docs/10_operation_specifications.md`, `CHANGELOG.md`.
P-114 (refuse any array sharing memory with a trial-averaged buffer, not only a `.base` chain),
P-104 (refuse selecting a dataset the conversion rewrites, as `spike_train` is refused), P-239 (refuse
a scalar dataset before writing, or correct the CHANGELOG line), P-272 (NumPy indexing semantics, as
documented), P-261 (the CUDA agreement checks run whatever the worker order), P-215 (`<NA>`, `NaT`),
P-243 (the `event_onsets` docstring), P-273 (device documentation).
Discriminator: each repair has a test that fails with the repair reverted.
Accept: each row is repaired pending verification.
Stop: a repair needs a public API choice the documentation does not already make.

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

## W3. Statistics surface, diagrams and the open-data example

## W4. Maintained figures, skill routing and references

## W5. Figures, execution switch and decline

## W6. Orders and empirical labelling

## W7. Contracts

## W8. Vocabulary and cost

## W9-W10. Documentation form

### 06-53 Gate the documentation form

Release: required-0.2.6.
Role: docs-harness. Skill: none. Blocked by: none.
Writes: `scripts/docs_form_gate.py`, `tests/test_docs_form_gate.py`.
Vocabulary list, heading depth, nav shape, figure theme-independence, and a table where a page
states more than two comparable facts in prose.
Accept: every check fails on its own seeded violation and passes on the live tree; a rule that
cannot be a check is recorded in the contract as a review item.

## Any wave. Confirmed findings

## Rolling verification

### 06-136 Verify the repairs landed after `a9993322`

Release: required-0.2.6.
Role: verifier. Skill: none. Blocked by: none. Writes: none.
Every repair landed after `a9993322` is verified here, by a verifier that implemented none of them, before its row closes. The pass at `9cecf53c` closed twelve rows; the pass at `a01cea1c` closed P-183, P-187, P-176 and P-126 and the `JRSAResult.p[0]` shim and synthetic-figure labels; the pass at `c304432b` closed P-21, P-91, P-127, P-128, P-132, P-211, P-56, P-43, P-45, P-158, P-202, P-46 and P-157 and the Granger order validation, and re-opened P-214, P-215, P-195 and P-114 into 06-140 (now closed) and P-34 into 06-58 (now closed); the pass at `aae8e027` closed P-223, P-214, P-224, P-233, P-226, P-205, P-206, P-207 and P-26, and re-opened P-114, P-215 and P-195. The pass at `fc7a0cb5` closed P-62, P-248, P-249, P-131, P-34, P-237, P-247, P-225, P-180, P-96, P-212, P-213, P-222, P-118, P-92, P-195 and P-217 and verified the Metal claim, the trimmed adversarial cases, the decline tests, the suite-cost change and the reference citations; it broke P-114 and P-104, left P-215 and P-243 partial, and re-disposed P-261. Current list: P-93 (on its own). P-114, P-104, P-239, P-272, P-261, P-215, P-243, P-273 (06-142). The four skill-routing mutants H03/H05 are P-279. The value repairs (06-141, now closed): P-250..P-253 and P-262 at `fef0d29b`, `785ff078`, `53ebda76`, `ec0ab24f` and `14ed1eb2`, including the NaN `df` ruling. The contract gate (06-59, now closed; `b524e5bf`) and P-263 (`a0fb1b5e`): seed each check's violation against the live tree. The findings answered by 06-17 (now closed; `6497ce5c`): the three repairs and their discriminators, and each of the ten `unsupported` answers against the line it cites (P-02). P-271 (`b7827b89`).
Do: re-run each discriminator against the exact diff; show the selector passes pristine before counting a kill; try one input the check should catch.
Accept: each listed row carries a receipt the verifier produced, or the breaking case is reported; the list is empty when this item is deleted.

## Closure

### 06-34 Adversarial mutation pass

Release: required-0.2.6.
Role: critic. Skill: none. Blocked by: 06-53, 06-129, 06-136, 06-142. Writes: none.
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
current, with `tests/test_generated_figures_are_maintained.py` run where the figures were
generated and reporting zero skips; links resolve; no stale version claim; the architecture page reachable.

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
treats `packages/jnwb-vis/` as added on `main` and unchanged on `dev`, so the duplicate that `dev`
deleted comes back.
Ruled 2026-09-22: revert on `main` first. `9d738211` is reverted on `main` in its own pull
request, which Hamm authorizes and merges; the verifier then confirms the release merge tree
equals `dev`.
Ruled 2026-09-23: opened ahead of the closure order as HNXJ/jnwb#20 and merged at `5e8ff14d`;
`main`'s tree equals `efdba807`, and `git merge-tree --write-tree origin/main origin/dev` at
`679e70a9` equals `dev`. What remains here is the same check on the release pull request.
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
| one canonical scientific model, published and reachable | `docs/architecture.md` (in the navigation since `d3d17871`), `tests/test_architecture_page_reachability.py`, the four diagrams on that page |
| every public claim reproduced against the implementation that answers it | 06-17 (now closed), 06-24, 06-136 |
| skills route, decline, and are tested against live behaviour | 06-24, 06-25 (now closed), `tests/test_skill_decline_behaviour.py` |
| cross-surface and compositional audit complete over the declared high-risk set | `artifacts/evidence/0.2.6/composition_subset_0.2.6.md` and its proposal, every magnitude naming a committed test and seed (re-stamped 2026-09-23) |
| documentation assets render and are regenerable | `tests/test_generated_figures_are_maintained.py`, 06-36 |
| one real NWB end-to-end example with provenance | `examples/tutorials/09_open_data.py` (verified at `a9993322`; P-199 and P-200 carry its gaps), `tests/test_synthetic_figures_are_labelled.py` |
| published artifact independently verified, from TestPyPI before publication and from PyPI after | 06-37, 06-38, 06-40 |
| documentation low-verbosity and consistently formed, against a declared contract | 06-51 (now closed), 06-53, `docs/glossary.md`, `tests/test_figure_form.py` |
| one precision switch and one execution switch; CPU, parallel CPU and CUDA exercised here | 06-56 (now closed), 06-59 (now closed), `scripts/computational_contract_gate.py` |
| every declared interpreter qualified by CI on Ubuntu and Windows, and every surface declaring the same set | gate 8, CI on `dev`, 06-35 |
| a read invents no metadata, and a named waiver is recorded as it happened | `tests/test_nwb_read_tolerance_and_visibility.py`, `tests/test_public_api_reachability.py` |
| `jnwb.vis` is an optional extra and `import jnwb` works without it | `tests/test_optional_vis_extra.py`, 06-37 |
| suite wall time and the slowest tests measured before release | `scripts/release_gate.py` STEP 1 |
| no release-blocking problem and no required item remaining, confirmed by a blocker-focused pass | 06-60, `scripts/release_gate.py` STEP 0a |

The form matches 0.2.5's closure: no known material defect under a stated acceptance set, not a
claim of exhaustive correctness. Deliberately absent: a claim that the JAX Metal backend works; it
is implemented and declared unverified.
