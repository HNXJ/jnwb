# 0.2.6

Authorized 2026-09-19 as a fresh cycle. The 0.2.5 stack is not extended: its record is
`artifacts/todo_stack_0.2.5.md`, immutable, and nothing here is appended to it.

Items are deleted when done; finished work is not recorded here. The closure records in the
0.2.5 file say what each of that cycle's items measured.

0.2.5 raised per-surface correctness. The next failure class is system-level: jnwb can hold
correct code, tests, documentation and skills while its public identity, examples, diagrams,
packaging and presentation-facing claims disagree with each other or cannot be reached.
0.2.6 is a coherence, reachability and evidence release, extended on 2026-09-19 by the three
release conditions in `AGENTS.md` §11: documentation form, computational form, and both stacks
empty. It adds no scientific capability. The computational work makes an existing backend
mechanism uniform and truthful; it does not add an estimator.

`artifacts/problem_stack.md` is the companion to this file. This one holds work that was
planned; that one holds defects found while doing it. A problem is not deleted when an item
claims it, and the release requires that file to hold no `open` entry.

## How this stack is executed

Every item below is a delegation packet in the contract of `skills/jnwb-fact-action` §5. The
executing role is `jnwb-developer` (`artifacts/agents/jnwb-developer.md`) unless the item names
another. An item is dispatched by mapping its fields onto the packet:

```text
ROLE:             the item's Role
DOMAIN SKILL:     the item's Skill
GOAL:             the item's heading
TODO ITEM:        the item's identifier
AUTHORITIES:      AGENTS.md, artifacts/fact_stack.md, artifacts/direction.md, this file,
                  plus the item's own Reads
RELEVANT FACTS:   from artifacts/fact_stack.md
OBSERVED BASELINE: the item's Reproduce, run, with its output
INVARIANTS:       shapes, units, axes, coordinate frames, sample rates, index bases
ALLOWED SCOPE:    the item's Writes
ACCEPTANCE:       the item's Accept
STOP CONDITIONS:  the item's Stop, plus the standing conditions below
```

### Dispatch rules

**`AUTONOMY: max` is this stack's default** (`AGENTS.md` §12). An item carrying no `AUTONOMY:`
line inherits it: the actor and critic select the work, reproduce, repair, attack the repair,
verify, reconcile both stacks and move to the next item without being asked. A failing test, a
surviving mutant, a wrong audit claim or a newly discovered todo is the work, not a handback.
Items marked `AUTONOMY: none` are human rulings and the release; an agent may assemble their
evidence and may not make the decision. Autonomy is not authority: `max` grants no permission
that `none` lacks.

**One writable agent per worktree.** Two agents writing one checkout have silently lost green
tests here before. A batch runs at most one packet with a non-empty `Writes` per worktree;
concurrent writers each get their own worktree and are merged one at a time. Packets whose
`Writes` is `none` are read-only and parallelize without limit. `Writes` sets that look disjoint
are not a licence to share a tree.

**One item per packet.** A batch of eight items is eight packets. An agent handed a list reports
progress on the easy items and redefines the hard one.

**The actor is never the verifier.** Every packet returning `ITEM DISPOSITION: repaired` is
followed by a `verifier` packet that re-runs the evidence against the exact diff. The verifier
receives the item and the diff, not the developer's summary.

**Non-reproduction is a successful outcome.** An imported finding that does not reproduce is
returned `unsupported` with its evidence and its item deleted. Correct code is never modified to
match a wrong report.

**A contradiction stops the packet.** Two sources disagreeing on one quantity, a declared path
that does not exist, or a gate whose inputs contradict its output are surfaced to `authority`,
not resolved by the developer.

**Standing stop conditions**, on every packet: a repair needs a path outside `Writes`; the item's
premise is already false; reaching acceptance would require inventing evidence or a human
ruling; a secret would enter the repository or a transcript.

**Batch barrier.** After a batch, one run of `python scripts/harness_gate.py` and
`python -m pytest -q`, then commit and push, then the next batch. Items inside a batch respect
their own `Blocked by`.

### Item fields

`Role` the delegated role. `Skill` the domain skill, or `none` where the item is not scientific.
`Blocked by` items that must be reconciled first. `Reads` what the packet must load beyond the
standing authorities. `Writes` the exact allowed scope, or `none` for a read-only packet.
`Reproduce` the command establishing the baseline and what counts as reproduction. `Do` the
smallest justified action. `Discriminator` the check that must fail before the repair and pass
after. `Accept` the mechanical condition. `Stop` conditions beyond the standing ones.

### Imported evidence

`artifacts/alignment_review_0.2.5.md` (31 confirmed, 12 upheld with dissent, 4 refuted, 36
unverified; identifiers there are stable), disposed in `artifacts/findings_0.2.6.md`,
`artifacts/planned_post_0.2.5.md`,
the two residual limits recorded by 05-85 in `artifacts/todo_stack_0.2.5.md`, the carried
`granger_causality(order=...)` candidate, and the downstream consumer report at
`E:/omission/context/state/JNWB_HANDOUT_20260919.md` (measured against installed 0.2.5, commit
`efdba80`). Of its seven admitted items, three are closed and four stand. 06-43 was refuted by a
working composition. 06-41 was reframed after a 2x2 reproducer showed its first framing tested a
path the reporter's files cannot reach, then ruled and implemented: `read_nwb` gained
`allow_missing`, and the squeeze now warns. 06-42 established that hdmf owns the pandas pin, and
the ruling pinned this machine's environment rather than restating a bound jnwb does not own.
06-44 through 06-47 stand.

A consumer report is evidence of a consumer's experience, not of a jnwb defect. Its items are
reproduced here against this tree before anything is written, and the three capability and
dependency asks end in a scoping proposal for a human ruling, never in an implementation: new
capability is frozen out of this cycle by the non-goals below.

**Every imported finding enters as a hypothesis to reproduce, never as a defect to implement.**
The review's own adversarial pass refuted four findings that read as solid.

## Dispatch map

Re-measured 2026-09-22 against the live stack: **41 of the 56 items below have no blocker**, so
the plan is not blocked, it is unparallelized. Reading 1200 lines to find the next safe piece of
work is the cost this section removes.

The previous measurement here read "45 of the 74 items below" at `b150063d` and stood while the
stack shrank to 57. A navigational section is exactly the kind of file that points at other
files and goes stale without erroring, so its numbers are re-derived rather than carried.

Two agents may run at once exactly when their `Writes` sets are disjoint. That is why a `Writes`
field naming a directory is a defect and not a shorthand: 24 items declared `tests/`, which made
them all look mutually exclusive when almost none of them are. Lane items now name files.

A **lane** owns one worktree and runs its items in sequence. Lanes run concurrently.

**The lane table that stood here is removed rather than corrected.** It assigned 16 items to
five lanes, and by 2026-09-21 **14 of those 16 were retired** -- the compression, statistics and
doctrine lanes pointed entirely at items that no longer existed, leaving only 06-51 and 06-24
live. It read as a plan and resolved to almost nothing, which is worse than absent: a dispatcher
checking it would have found work that was already done.

A lane assignment is derived per wave from the live `Writes:` fields and is not durable, so it
is not kept here. Two agents may run at once exactly when their `Writes:` sets are disjoint **by
resolved path and closed under generation** -- a lane that generates a file conflicts with one
that reads it, even though neither names the other's paths. Derive the wave, dispatch it, and
discard the assignment; what stays below are the three observations that outlived the table.

Three things the map makes visible that the batches did not:

1. **The docs lane is the critical path.** 06-49 blocks 06-51 and 06-53, so it is serial and must
   start first while other lanes fill the time.
2. **`AGENTS.md` is a single-writer surface.** 06-62, 06-72, 06-68 and 06-91 all write it, so they
   are one lane and never concurrent, whatever batch they are filed under.
3. **The dispatcher writes the stacks.** 06-80 and 06-83 name `artifacts/*_stack.md` in their work;
   a packet does not edit them. It reports the disposition it believes a row has earned.

No item waits on a ruling. The rulings of 2026-09-22 (`artifacts/rulings_2026-09-22.md`) decided every
open one; each became an implementation item below or a 0.2.7 entry in
`artifacts/planned_post_0.2.6.md`. What still needs Hamm is 06-40, the release.

## Batch 0. Goal and authority

The goal statement is the artifact 0.2.6 is scored against, and two of its three pillars name
capabilities that do not exist and that this cycle decides not to build. Repairing the
repository against an unrevised goal cannot produce a valid result.

The direction of repair is fixed: **package evidence plus human ruling produces the corrected
goal.** A desired presentation never produces a new package identity. This binds the "dynamic"
wording, the AI-native positioning and the topology figure in particular.

Batch 0 completes before any substantive edit elsewhere. 06-01 and 06-02 were ruled on
2026-09-19, and `artifacts/goal.md` plus the vocabulary rule at the head of `AGENTS.md` carry
those rulings, and the rulings of 2026-09-22 (`artifacts/rulings_2026-09-22.md`) decided 06-67 and the terms
06-05 freezes under. What remains of this batch is executable: 06-64 verifies, 06-05 freezes.

The basis reconstruction and the findings disposition are done and therefore deleted. Their
results live in `artifacts/findings_0.2.6.md`, which resolves all 83 review identifiers, and in
`artifacts/problem_stack.md`, which carries what they found and could not repair.

### 06-64 Verify the repairs of 2026-09-19

Release: required-0.2.6.
Role: verifier. Skill: none. Blocked by: none. Writes: none.
The actor is never the verifier, and seven repairs landed today with their author's own receipts.
Each is a separate read-only packet against the exact diff, never against the author's summary.

| Diff | Repaired | The claim most worth attacking |
|---|---|---|
| gate 8, classifier-versus-matrix | 06-10 agent | That the new check cannot be satisfied by editing the constants, which is how the old one failed |
| `jrsa.py` correction fallback | 06-15 agent | That every statsmodels-present value is bitwise unchanged, and that `bonferroni`'s surviving fallback really does reproduce statsmodels |
| gate 2 and gate 4, nested checkouts | this session | That a genuine duplicate skill tree still fails. A repair that only makes worktrees pass is a hole |
| `nwb_io.py`, `allow_missing` and the squeeze warning | this session | That the default is still refusal. Do **not** verify that `""` is unmistakable -- it is not, and 06-67 rules it |
| collect-all gate reporting | this session | That no gate can be positioned so its failure hides another, and that `PASS` requires all 13 to have executed rather than none to have complained |
| test-provenance scanners | this session | That the three new scanners encode the invariant and not a third proxy, and that the two pre-existing `jnwb.__file__` uses they permit really do hold for an installed copy |
| the gate-order tests, `7e7d1f47` | this session | That rewriting them to read `GATES` did not weaken them. The author's own mutants were a swapped check and a renumbered gate; find a third the rewritten sweep no longer catches, starting with a gate present in the table but absent from the module docstring |

Recorded as P-37: all three harness repairs share one cause, a proxy mistaken for the invariant.
The verification that matters is therefore not "does the repair work" but **"is the new check the
invariant, or a better-shaped proxy for it"**. Attack that.

Do: re-run each discriminator from the diff, not from the report. For the two this session wrote,
assume the author was motivated to see them pass.
Accept: each claim independently reproduced, or the disagreement stated with its evidence.
Stop: a repair cannot be verified without changing it. Say so; do not change it.

### 06-05 Freeze the acceptance set and the non-goals

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `artifacts/todo_stack.md`.
Ruled 2026-09-22: freeze the Acceptance section below as written. 06-13's ruling now has its
implementation item, 06-114, which was the last condition. Freeze from **live reproduced
state**, not by copying the planning text: each line must name the check or the item that
establishes it, and a line that names neither does not enter the set.
Accept: the frozen set is dated and the non-goals section below is part of it.

## Batch 1. Public truth and reachability

### 06-06 Publish the canonical architecture page

Release: required-0.2.6.
Role: docs-harness. Skill: jnwb. Blocked by: none.
06-01 and 06-02 were both ruled
2026-09-19 and deleted as complete. This item read as blocked for a day after it was not.
Reads: `artifacts/direction.md`. Writes: a new page under `docs/*.md` (named at dispatch;
`docs/01_architecture_and_philosophy.md`
already exists and is not it), `mkdocs.yml`, `docs/index.md`, `docs/agents.md`.
Do: extract the durable content of the ruling into a maintained page -- identity, the two entry
paths, the code/documentation/tests relation with skills acting on it, the four routing cases,
the boundary test. No ruling or process language in the public version. The artifact remains the
historical authority.
Accept: `python scripts/docs_build.py` builds strict, and the page is reachable from the
navigation.
Stop: 06-02 is unruled.

### 06-07 Gate architecture reachability

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: 06-06. Writes:
`tests/test_architecture_page_reachability.py`.
Assert: the page is a navigation target; `docs/agents.md` links it; no maintained public asset
draws the researcher-through-AI chain; the public identity does not require an agent to be
present; no maintained asset describes skills as an implementation authority.
Discriminator: reinsert the chain into a maintained page; the test fails. Remove the nav entry;
the test fails.
Accept: behaviour-shaped assertions only. A whole-prose snapshot fails this item, because it
breaks on rewording and passes on a reversed meaning.

## Batch 2. Scientific defects

### 06-14 granger_causality order validation

Release: required-0.2.6.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: none.
Writes: `jnwb/connectivity.py`, `tests/test_granger_order_validation.py`,
`docs/08_directed_connectivity_and_information.md`,
`skills/jnwb-connectivity/SKILL.md`.
Reproduce the carried candidate at `jnwb/connectivity.py` around the `order` parameter before
anything else; it was deferred, not established.
Do: establish the allowed domain and reject invalid orders explicitly.
Discriminator: mutation-kill the validation, with the selector shown to collect and pass pristine
first.
Accept: invalid orders raise rather than returning a plausible number; documentation and the
skill row agree with the implementation.

### 06-16 Sweep the substitution class

Release: required-0.2.6.
Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: none. Writes:
`tests/test_substitution_class_sweep.py`, then per finding, named in the packet.
Repaired instances share one shape: a fallback producing a differently-computed but plausible
result under the original label. 06-15 was one -- statsmodels absent routed every method except
`bonferroni` to Benjamini-Hochberg while the recorded correction echoed the request -- and it now
raises. Sweep the package for the shape rather than fixing instances one at a time.
Two live leads, both recorded while 06-15 was being repaired and neither chased:
**P-31**, `_CORRECTION_METHOD_MAP.get(m_lower, "fdr_bh")` in `jnwb/jrsa.py`, where
`correction="none"` passes validation and is then BH-corrected under the label `none`.
Unreachable today because both `jrsa()` call sites short-circuit first, so it is a latent
instance and exactly what a sweep is for.
**P-21**, two exports emitting a column named `layer` whose values are not the labels a reader
would expect, one of them silently reading `Unknown`. Same shape in data rather than in an
estimator, which is the part a statistics-only sweep would miss.
Do: extract the check as a module-level function and drive it over the live tree, which must find
nothing further, and over constructed seeds carrying the defect, which it must find. A sweep that
has never found anything is not evidence.
Accept: the instrument is shown to detect a seeded instance; every live hit is reproduced before
repair.

### 06-17 Confirmed findings not claimed by another item

Release: required-0.2.6.
Role: jnwb-developer. Skill: per finding. Blocked by: none.
One packet per ledger entry disposed `reproduced` and claimed by no other item, highest
consequence first. Writes: **deferred -- this item dispatches packets and writes nothing itself**; each packet
declares its own set from the finding's receipt. Not schedulable as a single lane. See P-162:
a parser reading this field returned the token `repaired`, scraped off the Accept line below.
Accept: each returns `repaired` with a discriminator, or `unsupported` with evidence.

## Batch 3. Coherence of code, documentation, tests and skills

05-85 recorded two limits: composition's aggregation order and identifier survival were not
swept, and no capability-by-capability matrix was built. A matrix over every public symbol and
every dimension is its own release and is not attempted here. This batch closes the named limits
over a declared subset and records the subset's boundary as part of the result.

### 06-24 Skill routing against live behaviour

Release: required-0.2.6.
Role: jnwb-developer. Skill: per skill, nine packets. Blocked by: none.
Writes: the routed skill file and `tests/test_skills_validation.py`.
Every routing row: the callable exists, the signature matches, the return type and keys match,
units match, failure behaviour matches. Conditional return schemas are in scope -- a skill must
not name a key that exists only under an unstated branch, which is the `cross_modal_comparison`
defect repaired in 0.2.5.
**Partially executed, and not to be read as complete (P-103).** The validator half is
delivered. The rows of the other eight skill files have not been checked against live
behaviour, so this item is one of nine packets done, not nine. The lane reported this rather
than claiming the item.
Accept: every claim checked by execution against the live export, not against the skill's text.

### 06-25 Decline behaviour as executable evidence

Release: required-0.2.6.
Role: jnwb-developer. Skill: per skill. Blocked by: 06-24. Writes:
`tests/test_skill_decline_behaviour.py`, and the routed `skills/*/SKILL.md`.
Representative cases per applicable skill for all four outcomes of `artifacts/direction.md`:
supported routes, missing input is requested, a non-identifiable result is reported as a failure,
an unsupported claim is declined. No language model is required to test this layer: the check is
that the routed operation raises, returns a declared failure, or requests the missing input.
Accept: `direction.md` holds that a skill which cannot decline is incomplete; each skill either
satisfies that or is recorded as not requiring it.

### 06-26 Worked examples stop teaching synthesis

Release: required-0.2.6.
Role: jnwb-developer. Skill: per skill. Blocked by: none. Writes: `skills/*/SKILL.md`,
`tests/test_skill_examples_execute.py`.
Reproduce: six of nine skill files build example inputs with a random generator; only
`skills/jnwb-nwb-data/SKILL.md` opens a file. No test executes any example block.
Do: classify every example input as real NWB, deterministic minimal array, stochastic synthetic,
or explicit calibration fixture, and default normal routing examples to the first two. The
objective is not removing generators from documentation; it is that a normal analysis instruction
never implies inventing data.
Accept: every example block executes in the suite, and each block's input class is declared and
checked.

### 06-74 Dispose of the collection-order fragility

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none. Writes:
`tests/test_collection_order_stability.py`, `artifacts/problem_stack.md`.
P-12, carried. An ad-hoc pytest subset can fail three `test_backend` tests and segfault; the full
suite passes. The release requires no `open` problem, so this ends as a repair or as an
`accepted` with a reason that survives a hostile reader — it cannot simply stay carried.
Reproduce: find the minimal subset that segfaults, and confirm the same tests pass in a full run.
Do: establish whether the fragility is a test-isolation defect in this repository or a property of
an imported extension module. If the former, repair it. If the latter, `accepted` naming the
module and the evidence.
Discriminator: the minimal failing subset passes after the repair, and the full suite is unchanged.
Accept: P-12 closes as `repaired` or `accepted`, never as carried.
Stop: the segfault cannot be reproduced at all. Then the premise is false and the row goes.

## Batch 4. Maintained evidence and demonstrations

### 06-29 Make generated figures maintained

Release: required-0.2.6.
Role: docs-harness. Skill: jnwb-figures. Blocked by: none.
Writes: `docs/generate_figures.py`, `tests/test_generated_figures_are_maintained.py`,
`scripts/harness_gate.py`.
Reproduce: nothing runs the generator -- not CI, not `scripts/harness_gate.py`, not
`scripts/release_gate.py`, not `.readthedocs.yaml`, not any test -- and re-running it reproduces
none of its outputs byte-identically.
Do: map every artifact to its generator, regenerate in isolation, gate on unexplained drift.
Accept: a tolerance the plotting stack can actually meet, justified by measurement rather than
chosen. A byte-equality gate fails this item; so does a tolerance wide enough to accept a changed
figure.

### 06-30 Produce the canonical diagrams

Release: required-0.2.6.
Role: docs-harness. Skill: jnwb-figures. Blocked by: 06-06.
06-08 closed 2026-09-20 and is no longer a blocker.
Writes: `docs/*.md`, `docs/assets/*.svg`.
Dual entry; code, documentation and tests with skill routing over them; the four-outcome
decision; NWB to analysis; the package boundary. One maintained source each, original to jnwb.
Stop: the external prior art is licensed no-derivatives; no figure of it is adapted, in
documentation or in any presentation. That ruling is in `artifacts/direction.md` and is enforced
here, not restated.

### 06-31 One real NWB end-to-end example

Release: required-0.2.6.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: **a Hamm ruling between the two routes
below.** The corpus read granted 2026-09-22 (`artifacts/rulings_2026-09-22.md`) does not unblock
this item: the example must use a redistributable dataset, and the grant keeps every corpus
identifier out of `docs/`. The routes are a public dataset, which needs download permission,
or the rescope described below.
Before the grant, all four routes to a real NWB file were closed: the `D:` corpus
**existed and was denied by policy** (`jnwb.paths.describe()` resolves it; a read was refused);
downloading requires user permission that has not been given; remote streaming needs `ros3`
(absent from this h5py build), or `remfile`/`dandi` (not importable), or a declared `fsspec`
dependency -- and `pyproject.toml` is **not in this item's write set**, so the item cannot
deliver the "remotely accessible" half of its own text; and every fixture in the repository is
synthetic (`git ls-files` finds zero tracked `.nwb`; `jnwb/testing/nwb_fixtures.py` builds from
`np.random.default_rng(seed)`).
**The lane refused to build the obvious workaround and was right to.** A script plus a test that
skips when data is absent would skip **forever** in CI, passing in two gates while the invariant
it names is violated, and would later be cited as "06-31 verified". That is the P-37 shape.
Capability-fit checklist for whoever resumes, derived by measuring call sites across
`examples/tutorials/*.py`: an interval table with onset and code columns (`event_onsets`, 8 sites);
a sorted `units` table (`unit_spike_times`, 3); a continuous `ElectricalSeries` with a
**constant** `rate` (`acquisition_channel` 5 and `epoch_continuous` 8 -- a timestamps-stored
series has `rate_hz: None` and is not epochable); an electrodes table with depth and location for
`vflip_from_lfp`/`zflip`. Note the item says select "by capability fit", which can only be
established from the bytes -- **so the selection step is itself blocked.**
A third disposition exists and needs a ruling: rescope the item to a documented procedure for a
reader's own file, exercised against a synthetic stand-in, with the limitation stated in the
page rather than hidden by a skip. That needs no grant.
Writes: `docs/tutorials/*.md`, `examples/*.py`, `tests/test_real_nwb_example.py`.
Select a small, redistributable or remotely accessible public dataset by capability fit, not by
name. Open, inspect, select, analyse, verify, visualise, reusing the operations the skills route,
with provenance sufficient to reproduce the result.
Accept: the example runs in CI or is skipped with a stated reason, never silently.
Stop: no suitable dataset is redistributable under the licence; surface rather than substituting
a synthetic one and calling it an example.

### 06-32 Separate empirical from synthetic

Release: required-0.2.6.
Role: docs-harness. Skill: jnwb-figures. Blocked by: 06-31. Writes: `docs/*.md`, `examples/*.py`,
`tests/test_synthetic_figures_are_labelled.py`.
Visibly and structurally, in the documentation tree and in the figures.
Accept: a check that a page carrying a synthetic figure says so.

### 06-33 Retain the benchmark design as explicitly unrun

Release: required-0.2.6.
Role: docs-harness. Skill: none. Blocked by: none. Writes: `artifacts/planned_post_0.2.5.md`.
Bring the ruled hypothesis to pre-registration quality and mark it unrun. It is not an acceptance
criterion for this release: an empirical comparison whose either outcome is scientifically
admissible cannot gate a release without giving the experiment a result to reach.
Accept: task set, scoring rubric, arms, repetitions, refusal scoring and inferential unit are all
declared, and the document states that none of it has been executed.

## Batch 5. Documentation form

Condition 1 of the release acceptance in `AGENTS.md` §11. The pages are accurate after Batch 1;
this batch is about whether they can be read. A correct page nobody finishes is not reachable
documentation, and reachability is what 0.2.6 claims.

The order matters: the contract is declared first, because a verbosity or formatting judgement
made page by page is a preference, and twenty-seven pages edited to twenty-seven preferences is
worse than leaving them alone.

### 06-51 Reduce verbosity against the contract

Release: required-0.2.6.
Role: docs-harness. Skill: none. Blocked by: none.
**Unblocked 2026-09-20:** 06-49 closed and left the stack. Writes: `docs/*.md`, `README.md`.
One packet per page, not one packet for the set. A batch handed twenty-seven pages trims the easy
ones and rewrites the hard one.

**Seventeen pages, not twenty-seven.** Measured 2026-09-19 and recorded as P-25: `docs/api.md` is
generated by `scripts/generate_api_md.py` and the nine `docs/tutorials/*.md` are wrappers that
`--8<--` include `examples/tutorials/*.py`. Both say so on the page. An edit to any of the ten is
discarded by the next build without erroring. If one of them violates the contract, the packet
goes to the generator or the included script, and it is a different packet.
The contract is `docs/documentation_form.md`; take the ceilings and the rule numbers from there.
First page is `common_mistakes.md`: 2308 words, zero tables, the largest authored page, and the
one that will show whether rule F2 can be applied without taste.
Do: per page, apply the contract. Prose carrying comparable facts becomes a table; restated
obviousness, hedges and repeated caveats are cut; anything unverified is removed rather than
labelled.
**Partially executed, and not to be read as complete (P-103).** Two of the seventeen authored
pages have had a per-page pass. F1 and F5 were established to hold corpus-wide, but the other
fifteen pages have had none, and `docs/02` and `docs/04` are over the length ceiling for a
reason the contract now records as a *split*, which this item's own stop condition hands
elsewhere. The lane reported this rather than claiming the item, which is the behaviour the
stop condition exists to produce.
Accept: the page satisfies every rule in the contract, and no fact present before is absent
after. Shorter is not the acceptance condition; shorter while lossless is.
Stop: applying the contract would delete a caveat that a test or a gate exists to enforce. Cut
the restatement, keep the one that is load-bearing.

### 06-52 Figures that carry structure

Release: required-0.2.6.
Role: docs-harness. Skill: jnwb-figures. Blocked by: 06-30. Writes: `docs/*.md`,
`docs/assets/*.svg`, `tests/test_figure_form.py`.
Unblocked 2026-09-19. This item's acceptance named a comparison the site could not make: there was
one palette scheme. `mkdocs.yml` now carries `slate` and `default`, each with a toggle, so
"renders in both themes" is executable as written and a figure that hardcodes a background is
falsifiable. The rules are G1 through G4 of `docs/documentation_form.md`; take them from there.
Do: place the canonical diagrams from 06-30 into the pages whose structure they carry, as inline
SVG, so they scale and remain searchable.
**Format is not this item's licence to convert.** The seven existing raster PNGs under
`docs/assets/figures/` stay. An inline-SVG rule was proposed for the contract and removed because
it would forbid what those seven pages already do. Bring new figures in as SVG; leave the rasters
alone unless one actually fails G1 or G2, in which case fix that figure and say which rule it
broke.
Discriminator: switch the scheme. A figure that hardcoded a colour becomes unreadable under the
other one and the check catches it.
Accept: every figure satisfies G1 through G4, every figure is referenced by the prose around it,
and no page carries a figure that repeats what its adjacent table already says. Closes P-26.
Stop: a figure would need to be adapted from Paper2Agent. Its licence forbids derivative figures
and `artifacts/direction.md` records the constraint.
Stop: a figure needs plotly or kaleido. Ruled 2026-09-19 that neither is declared, so a page
depending on them builds here and fails in CI. That is G4, and it is recorded as P-33.

### 06-53 Gate the documentation form

Release: required-0.2.6.
Role: docs-harness. Skill: none. Blocked by: 06-51, 06-52.
**Narrowed 2026-09-20:** 06-49 and 06-50 closed and left the stack. The contract itself is written.
Writes: `scripts/docs_form_gate.py` (new), `tests/test_docs_form_gate.py`.
A contract nothing enforces decays to a preference within one cycle.
Do: make the mechanically checkable rules into checks -- the vocabulary list, heading depth, nav
shape, figure theme-independence, and the presence of a table where a page states more than two
comparable facts in prose.
Discriminator: each check is shown failing on a constructed page that breaks exactly its rule.
Accept: every check fails on its own seeded violation and passes on the live tree. A rule that
cannot be expressed as a check is recorded in the contract as a review item, not silently
dropped.

## Batch 6. Computational form

Condition 2 of the release acceptance in `AGENTS.md` §11. `jnwb/_backend.py` and
`jnwb/_parallel.py` already exist, with 34 `resolve_device` call sites and 11 `parallel_map`
ones, so this batch is about uniformity and truthfulness of a mechanism that is already there,
not about building one.

Two rulings of 2026-09-19 govern this batch -- the JAX Metal path is declared unverified rather
than claimed, and conformance to an official reference is sufficient evidence. Both are stated
in `AGENTS.md` §11 (`:356-358` and `:367-368`), and were restated here in full, which made this
file the second home for a ruling it does not own. The header above already routes to §11; that
pointer is the whole of what belongs here.

### 06-56 One execution switch

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
**Unblocked 2026-09-21:** 06-55 closed. `jnwb/_precision.py` and the policy registry are in the tree, and `resolve_working_dtype` is the shared rule this item generalises from.
Writes: `jnwb/*.py`,
`tests/test_execution_switch.py`.
Reproduce: `jnwb/jrsa.py:222` documents a backend parameter as "accepted for API compatibility".
A parameter accepted and ignored is the substitution class of 06-16 in another form: the caller
asks for one thing, receives another, and nothing errors. Establish for every backend-taking
export whether the argument selects anything.
Do: one mechanism for CPU, parallel CPU, CUDA and JAX Metal. Every backend argument either
selects a backend or is rejected. A fallback is announced, never silent.
Discriminator: request an unavailable backend; it must fail or warn, and the warning must name
what ran instead.
Accept: CPU, parallel CPU and CUDA each produce results agreeing within a stated tolerance on
the declared high-risk subset, measured on this machine. The Metal path is implemented and
documented as unverified, and no page, docstring or release note claims it works.
Stop: two backends disagree beyond tolerance. That is a correctness defect, not a dispatch
defect, and it stops the packet.

### 06-57 Cite the reference where the implementation matches it

Release: required-0.2.6.
Role: jnwb-developer. Skill: per module. Blocked by: none. Writes: `jnwb/*.py`,
`docs/references.md`.
Do: where an implementation follows a published or official reference, cite that reference at the
implementation and in `docs/references.md`. Under the 2026-09-19 ruling the citation is the
evidence of correctness and the algorithm is not re-derived.
Accept: every cited reference resolves, and the citation names the specific result implemented
rather than the paper in general. A citation to a whole paper does not say which equation was
followed and is not sufficient evidence.
Stop: the implementation and the reference differ. A deliberate divergence is documented at the
divergence; an undocumented one is a defect and goes to the problem stack.

### 06-58 Reduce the orders the inventory named

Release: required-0.2.6.
Role: jnwb-developer. Skill: per module. Blocked by: 06-57. Writes: per packet.
Not 06-86, which reads like it: that item resolves a contradiction inside
`artifacts/benchmarks/complexity_inventory.md`, a different file. This one reduces measured
orders in `artifacts/computational_order.md`. Titles nearly collide; the work does not.
The inventory exists: `artifacts/computational_order.md`, 156 exports, 189 sweeps, with a ranked
queue in its section 10. One packet per gap, highest exponent gap first.
Take the ranking for what it is. It orders how badly an export degrades as input grows, **not**
wall clock: `fit_exponential_onset` at 532 ms is the most expensive single call in the baseline
and carries no order gap at all, so it is not this item's business.
Nine gaps are corroborated by measurement and are the queue. Two are worth naming here:
`phase_slope_index` measures **+2.14** in `n_samples` against an admissible T(S*L), and the
jackknife path that causes it is the library **default**; and `stream_npz_array` reads and
discards the leading elements instead of seeking, measured 710x slower than seek-then-read at
n=1.6e7.

**An undesirable exponent is not a mandate**, ruled 2026-09-19. Each packet establishes three
things before touching code: that the exponent is stable on re-measurement, why the path scales as
it does, and whether it violates an actual performance contract rather than merely looking wrong.
A measured number is a finding. Optimising because a figure is unattractive is how a correct
implementation gets rewritten into a subtly different one, and the 06-54 inventory exists to stop
exactly that reasoning, not to license it.
The inventory's coverage claim is also bounded, and the bound matters here: 106 + 48 + 2 = 156
establishes complete **classification coverage of the exports**. It does not establish complete
**complexity characterisation** -- 30 gaps are invisible to the method (P-35) and 8 admissible
orders are `unknown`. Do not read the partition as a statement that the package is now fully
characterised.
Five specs where a source reading predicted a gap and the measurement found none are recorded as
`no gap` and are **not** in the queue. Do not re-derive them from the source: reading order off
the source was wrong on six specs, which is P-36.
Thirty further gaps are invisible to a single-parameter sweep (P-35) and are not in the queue
either. A flat exponent there is not evidence against the gap, and chasing one needs a
two-parameter surface first.
Discriminator: a timing or operation-count measurement that separates the two orders on inputs
large enough for the difference to exceed noise.
Accept: the new order is measured, not argued, and every numerical result is unchanged within a
stated tolerance against a frozen output from before the change.
Stop: the faster order changes results beyond tolerance. Correctness outranks order.

### 06-59 Gate the computational contract

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: 06-56, 06-58.
**Narrowed 2026-09-21:** 06-55 closed and left the stack.
Writes:
`scripts/computational_contract_gate.py` (new),
`tests/test_computational_contract_gate.py`.
Do: make the contract enforceable -- a backend argument that selects nothing fails; a precision
request silently ignored fails; an export added without a recorded order fails.
Discriminator: each check shown failing on a seeded violation.
Accept: every check fails on its own seeded violation and passes on the live tree.

## Batch 7. Independent closure and release

### 06-34 Adversarial mutation pass

Release: required-0.2.6.
Role: critic. Skill: none. Blocked by: all of Batch 3. Writes: none.
Seed known semantic defects and require the intended gate to catch each one. Every selector
collects and passes pristine before any verdict counts.

### 06-35 Clean-environment matrix

Release: required-0.2.6.
Role: verifier. Skill: none. Blocked by: none. Writes: none.
Across the declared Python and operating-system support, resolving the 3.13 question. The
development virtualenv is not package evidence.

### 06-36 Documentation qualification

Release: required-0.2.6.
Role: verifier. Skill: none. Blocked by: 06-06, 06-29, 06-30. Writes: none.
06-08 closed 2026-09-20 and is no longer a blocker.
Strict build; diagrams render as diagrams, asserted against built output; generated assets
current; links resolve; no stale version claim; the canonical architecture page reachable from
the navigation.

### 06-37 Distribution qualification

Release: required-0.2.6.
Role: verifier. Skill: none. Blocked by: all repairs. Writes: none.
Source distribution and wheel: contents, metadata, imports, exports, `SKILLS_URL`, representative
workflows, documentation-facing constants, no checkout shadowing.

### 06-38 Fresh-install workflow

Release: required-0.2.6.
Role: verifier. Skill: jnwb-nwb-data. Blocked by: 06-37. Writes: none.
From the published candidate rather than the checkout: install, open an NWB file, analyse, verify.

### 06-39 Independent critic

Release: required-0.2.6.
Role: critic. Skill: none. Blocked by: 06-34 through 06-38. Writes: none.
A reviewer that implemented none of the repairs, over the acceptance set, the unresolved
unknowns, the mutation evidence, the public claims and the release artifacts.

### 06-60 No blocker remains, verified by an independent pass that finds no new one

Release: required-0.2.6.
Role: critic. Skill: none. Blocked by: 06-39.
Writes: `artifacts/blocker_fixpoint_receipt.md`.
Condition 3 of `AGENTS.md` §11 **as amended 2026-09-21**, and the item that decides whether the
release opens. The amendment replaced "both stacks empty" because that form could not terminate:
across 29 commits of this cycle the open count went 29 -> 101 while the item count stayed flat,
since the apparatus that discovers defects is the largest source of them.
Do: one independent pass over the documentation, the code and both stacks, applying the blocker
predicate in §11. Anything found that is release-blocking re-opens the cycle: the batch that owns
it runs, and this item runs again. Anything found that is not release-blocking is **recorded and
deferred**, and does not re-open the cycle. The pass is not a review of the repairs, which is
06-39's job; it is a search for what nobody has looked at yet.
Accept: `artifacts/blocker_fixpoint_receipt.md` exists, names the commit it ran against, and
reports **zero new release-blocking problems**. The fixpoint is zero new BLOCKERS, not zero new
observations -- new 0.2.7-quality rows may be written during the pass without resetting closure.
`scripts/release_gate.py` STEP 0a reads this receipt and refuses a receipt from any commit other
than HEAD, because a pass that ran against other bytes is not evidence about these bytes.
Discriminator: `tests/test_release_requires_no_blocker.py` shows all six STEP 0a checks both
ways, including that fifty new deferred observations and zero blockers still close the release.
Stop: the pass finds something release-blocking whose repair needs a human ruling. The cycle stays
open; it does not close by reclassifying the finding as `accepted`, and it does not close by
deferring it. `accepted` records that a problem cannot be repaired, never that repairing it is
inconvenient; `DEFERRED` requires all five of its conditions to be **established**, not plausible.

### 06-40 Release

Release: required-0.2.6.
Role: human, with verifier receipts. Skill: none. Blocked by: 06-60. AUTONOMY: none.
Writes: `jnwb/__init__.py`, `CHANGELOG.md`, `README.md`, and the release body through the API.
dev green, pull request and main green, tag validates without publishing, GitHub Release,
production index, then verification from the index in a clean environment. A tag alone validates
artifacts and does not publish; publication happens on the release.

## Batch 8. Problems found while executing 0.2.6

### 06-80 Resolve every `Skill:` field against `skills/`

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none. Writes: `scripts/harness_gate.py`, `tests/test_harness_adversarial_gates.py`. NOT the stacks:
the dispatcher writes those, so a gate item never edits the file it gates.
P-53. Two items named `jnwb-nwb-io`, which has never existed. The name reached two dispatched
packets, nothing errored, and a packet worked around it silently. The standing rule is that a file
pointing at other files goes stale without erroring; this pointer was **born wrong**, so a
staleness check would not have caught it either. Mechanically preventable, which is the criterion
for a gate.
Reproduce: list every `Skill:` value in the stack and diff it against `skills/`. Today that is
`jnwb-nwb-io` twice, plus the placeholder forms `per skill`, `per module`, `per finding` and
`per chain`, which are legitimate and must stay legal.
Do: add a gate resolving each `Skill:` value that is not a declared placeholder against a
directory under `skills/` holding a `SKILL.md`. Do the same for `Role:` against `artifacts/agents/`
if that costs nothing extra. **Widened by P-57:** resolve the cross-references between the
two stacks as well -- a blocker field and a problem's `Answered in` column may name only
a live item. Both went stale during this release with no error: two items named rulings that
had already happened, and two problems pointed at items deleted as complete.
Discriminator: reintroducing `jnwb-nwb-io` into any item fails the gate; every placeholder form
still passes; renaming a real skill directory fails the gate.
Accept: P-53 closes, the gate joins the collect-all table with its own number, the module
docstring lists it, and the count assertions in `tests/test_module_docstrings_match_their_code.py`
still agree on all three sides.
Stop: the placeholder forms cannot be distinguished from a typo by any rule. Then the stack's own
notation is the defect and it is repaired first.

### 06-82 Reach the waiver from the public API

Release: required-0.2.6.
Role: jnwb-developer. Skill: `jnwb-nwb-data`. Blocked by: none. Writes: `jnwb/__init__.py`,
`jnwb/nwb_io.py`, `docs/*.md`, `tests/test_public_api_reachability.py`,
`tests/test_nwb_read_tolerance_and_visibility.py`.
P-43 and P-46. `MissingRequiredNWBFieldError` is exported and documented; `read_nwb`, `nwb_read_io`,
`hdmf_build_repair_context` and `SqueezedAttributeWarning` are in neither `__all__` nor
`dir(jnwb)`, and `read_nwb(path, allow_missing=...)` is reachable only by importing the submodule
directly. **06-41 was ruled, implemented, and is unreachable from the public API** -- the caller
whose report produced the ruling cannot use what was ruled. Separately, a soft link to a valid
description is refused outright by default and with `ValueError: already exists in root.links`
when waived, although the value is on disk and reachable: refusing a file whose required field
**is** present is a false refusal, not a conservative default.
06-67 was ruled on 2026-09-22, option (d): `jnwb_waived_requirements` records the waiver that
actually happened on this read, not the one requested; no value changes and no read starts or
stops failing. This item therefore also repairs P-157, and adds the six-state missingness table
to `docs/errors.md` with one test per row in `tests/test_nwb_read_tolerance_and_visibility.py`.
Reproduce: `import jnwb; jnwb.read_nwb` and record the `AttributeError`; then open the soft-link
file both ways and record both failures.
Do: export the remedy beside the error, document it on the page that documents the error, and
make the soft-link case resolve the link rather than refuse it.
Discriminator: a caller who catches `MissingRequiredNWBFieldError` can reach the waiver without
importing a submodule; the soft-link file opens with the correct description and no waiver.
Accept: P-43, P-46, P-157 and P-158 close.

### 06-83 Verify the gate-2 administrative-entry repair

Release: required-0.2.6.
Role: critic. Skill: none. Blocked by: none. Writes: `artifacts/problem_stack.md`.
P-56, and the same shape as 06-64: a repair made by the dispatcher is verified by someone else.
P-40 closed `repaired` on a repair that was itself the proxy -- "`.git` exists by name" excuses an
empty directory -- and its own `nested-clone` fixture built exactly that counterfeit, so the
discriminator agreed with the defect and passed. `_is_git_admin_entry` now requires a directory
holding `HEAD`, or a file whose first line is `gitdir:`.
Reproduce: the three mutants recorded on P-56, re-derived rather than re-run from the script.
Do: establish whether the new predicate is the invariant or a third proxy. Specifically: a
directory holding an empty `HEAD`; a `gitdir:` file pointing at a path that does not exist; a real
worktree whose admin directory is unreadable. Say which of these the gate should accept and
whether it does.
Discriminator: at least one case the packet constructs that the new predicate gets wrong, or a
stated argument that the three above are the complete boundary.
Accept: P-56 closes `repaired` with the verifier's evidence, or re-opens with the case that breaks it.
Stop: none. A verifier that finds nothing reports finding nothing.

### 06-86 Resolve the two sources that disagree about computational order

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none. Ruled 2026-09-22 (P-34, P-127): the
inventory records `O` upper bounds justified by the algorithm and its published reference, and
drops "verified"; timed exponents stay a separate, labelled benchmark with at least three input
scales per row.
Writes: `artifacts/benchmarks/complexity_inventory.md`, `artifacts/computational_order.md`,
`tests/test_computational_order_sources_agree.py`.
Not 06-58, which reads like it: that item reduces measured orders in
`artifacts/computational_order.md`. This one resolves a contradiction inside a different file
and changes no code. They were nearly merged on the strength of their titles.
P-34. Eight measured exponents contradict `artifacts/benchmarks/complexity_inventory.md`, which
records them as "verified": INV-05 claims +1.00 against a measured +2.14; INV-06 claims +2.00 for
two granger exports measuring +1.07 and +1.11; INV-08 claims +1.00 against +0.62; INV-13 claims
+2.00 and +1.00 against +0.54 and +0.47; INV-14 claims +0.00 and +1.00 against +0.83 and +0.49.
The likely cause is that the inventory was verified against heap allocations and never timed, so
two documents measure different quantities under one word. This is release condition (2): a
document calling an unmeasured claim "verified" is the defect, independent of which number is
right.
Reproduce: re-run the timed sweep for the eight, and establish what the inventory's "verified"
actually verified by reading the script that produced it.
Do: name the quantity in both documents. If they measure different things, say which, and stop
using one word for both. Do not reconcile the numbers by re-baselining the inventory to the
timings -- that would make the contradiction disappear without establishing which was measured.
Discriminator: a test asserts the inventory names its quantity, and fails if a row records an
exponent with no stated measurement method.
**Re-scoped 2026-09-20 after the lane stopped on its stop condition.** Both halves of the
Reproduce step are unexecutable: no generator for the inventory has ever existed on any
branch, and `artifacts/computational_order.md:789` says its own harness and calibration
scripts were scratch files. The lane wrote nothing, which was correct -- repairing the
"verified" clause would have meant inventing provenance for the six rows nothing measured.
What the item found instead is P-127, P-128, P-131 and P-132, and that **P-34's own premise
and count were wrong**. One correction to the lane's report, re-derived on integration: the
receipt `artifacts/benchmarks/baseline_performance.json` is committed and well-formed, with
timings, heap figures and a full provenance block. The receipt is not the defect. The
coverage is -- 6 of 14 rows absent, 13 of 14 single-scale.
The ruling this waited on is recorded (2026-09-22): the inventory asserts `O` upper bounds
justified by the reference, which decides the six rows it names.
Accept: the word "verified" appears only where a method is named and a scale range exists
to support it, and a row with no measurement says so rather than being covered by a blanket
clause. P-34 and P-127 close with it.
Stop: the script that produced the inventory no longer exists or cannot be run. Then the
inventory's claims are unfalsifiable, which is a stronger finding than a disagreement, and it is
reported rather than patched.

### 06-87 Record what reading order off the source costs

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `docs/documentation_form.md` or `artifacts/agents/jnwb-developer.md`.
P-36, and a one-line repair rather than a project. Reading computational order off the source was
wrong on six specs in both directions: five where a source reading predicted a gap no measurement
found, and one exponential case a reading of the loop structure would not have caught. A nested
loop is not evidence of the order it looks like.
Do: write that as a rule where the next person doing order work will read it. One sentence, with
the count, because the count is what makes it credible.
Discriminator: none needed; this is prose. Its absence is the defect and its presence closes it.
Accept: P-36 closes.
Stop: neither file is the right home. Then say which is, and put it there.

### 06-89 Document the unit-to-layer composition

Release: required-0.2.6.
Role: docs-harness. Skill: `jnwb-population`. Blocked by: none.
**Unblocked 2026-09-20:** 06-49 closed and left the stack. Writes: `docs/*.md`,
`skills/*/SKILL.md`.
P-20. The composition works today through existing exports and no document or skill shows it, so
a capability that exists is unreachable by reading -- which is precisely the reachability failure
class 0.2.6 exists to close.
Reproduce: compose it from the public API and record the call sequence that works.
Do: document the sequence on the page that owns the operations, and give the routing skill a
pointer. The skill names the operation; documentation defines it, per `artifacts/direction.md`.
Discriminator: a reader following only the published page reaches layer labels from a units table
without reading source.
Accept: P-20 closes.
Stop: the composition depended on P-49's index-space defect being resolved first, and on 06-77.
Both are discharged -- P-49 is repaired and 06-77 retired complete at `9904fd7f` -- so the
sequence this documents no longer mislabels anatomy. Found stale 2026-09-21 by gate 15's
contradiction check, whose printed suppression named an item with no live header.

### 06-90 Make an absent `peak_channel_id` visible

Release: required-0.2.6.
Role: jnwb-developer. Skill: `jnwb-population`. Blocked by: none.
Writes: `jnwb/addressing.py`, `tests/test_absent_peak_channel_id.py`,
`docs/02_paths_addressing_metadata.md`.
P-22, restated after re-measurement. The row said `jnwb/addressing.py:340` assumes the column
exists. It does not: `:341` guards with `'peak_channel_id' in df.columns`. The real defect is what
the guard does -- when the column is absent the caller silently receives a frame with no `area`
and no `layer` column, no warning, and no indication that enrichment was skipped. That is the
06-16 substitution class in its quiet form: absence of output standing in for absence of input.
Separately and still true: no export derives `peak_channel_id` from an NWB units table, so a
caller who has only a units table cannot supply it.
Reproduce: call the enrichment with and without the column and diff the returned columns.
Do: make the skip observable -- warn, or return a stated indicator -- and decide whether to add a
derivation or to document that the caller supplies it. Both are acceptable; silence is not.
Discriminator: the no-column call is distinguishable from the with-column call by something other
than counting columns.
Accept: P-22 closes on its restated wording.
Stop: making the skip loud breaks a caller who relies on the silent path. Record the caller.

### 06-95 Scope the estimator-delay identity in the smoother's docstring

Release: required-0.2.6.
Role: jnwb-developer. Skill: jnwb-spiking. Blocked by: none.
Writes: `jnwb/onset_fitting.py`, `tests/test_skills_validation.py`.
P-110, found by the 06-93 lane and left unrepaired because `jnwb/**` was a hard stop for it.
`causal_exp_smooth`'s docstring states `t_observed = t_signal + t_estimator(tau_ms, bin_ms)` as a
general identity and then instructs the reader not to read latency differences without accounting
for estimator delay, with no scope. The identity is true of a threshold crossing on the smoothed
trace and false of `fit_exponential_onset`, which sits in the same module and whose bias is
tau-invariant. 06-93 established the numbers: crossing error tracks tau*ln2 while the fitted t0
holds about -0.9 ms and follows `bin_ms`, measured at -0.118, -0.365, -0.860, -1.854 and -4.805 ms
for bin 0.25, 0.5, 1, 2 and 5 ms.
Do: scope the identity to the readout it describes, and name the fit as exempt, in the wording
06-93 settled on for the skill so the two faces cannot drift apart again.
Discriminator: extend the 06-93 assertions to the docstring. Pin one sentence carrying both the
instruction and its scope -- not the presence of the words, which the repaired text states more
than once each. The decisive mutant is the one 06-93 used: add a second, unscoped instruction
leaving every word intact, and require the assertion to fail.
Accept: no instruction in `jnwb/onset_fitting.py` applies a filter-delay correction to a fitted
onset, the skill and the docstring state the same rule, and the mutant above is killed.
Stop: this item does not change what `causal_exp_smooth` computes. If the wording cannot be fixed
without changing behaviour, stop and report.

### 06-97 Give `xflip` a documented call site

Release: required-0.2.6.
Role: docs-harness. Skill: `jnwb-lfp-spectral`. Blocked by: none.
Writes: `docs/06_spikes_psth_and_onset_dynamics.md`, `examples/tutorials/06_laminar.py`,
`tests/test_docs_decoding_chain.py`.
**`tests/test_docs_decoding_chain.py` already exists** -- 06-96 created it on 2026-09-20 with 8 tests gating mermaid edges on every
`docs/` page. Extend that module; do not create it. It must not be held by two lanes at once.
P-55's residue, recorded at `artifacts/unconsumed_producers_0.2.6.md`. `xflip` is the only one of
the eight producers with **zero** documented call sites; the other seven have between one and
five, and `zflip` -- its nearest sibling, ruled a terminal output on the same grounds -- has a
worked example that reads its fields directly. The measured reason `xflip` reads as an unfinished
chain is that absence, not its output.
Do: a worked example that reads `XFlipResult` fields the way `examples/tutorials/06_laminar.py`
already reads `ZFlipResult`, so the two siblings are reachable by the same route.
Discriminator: the example executes in the suite and reads at least one field the operation
actually returns, checked against the live dataclass rather than against a written list of names.
Accept: `xflip` has a documented, executed call site; the ruling's "the gap is documentation"
reading is discharged rather than asserted.
Stop: this item adds no consumer and does not change what `xflip` returns.

### 06-99 Verify the container-type predicate against the corpus

Release: required-0.2.6.
Role: verifier. Skill: `jnwb-nwb-data`. Blocked by: none. Corpus read granted 2026-09-22 (`artifacts/rulings_2026-09-22.md`): read the raw NWB on `D:`, write outputs only to `E:` or the session scratchpad, and copy no corpus identifier into `jnwb/`, `docs/`, `skills/` or `tests/`.
Writes: `artifacts/problem_stack.md`.
P-54's remaining condition, and the only one. 06-84 implemented the ruling and proved it with ten
killed mutants, including a refuse-instead-of-warn mutant, so warn-never-refuse is tested rather
than assumed. What it could not do is run the predicate on real files: `D:` was outside its
packet, and a read of the corpus from this session was refused by the host's data-handling policy.
The gap is exactly one claim. The predicate is "the declared type has a schema-fixed data unit and
the stored unit differs". If the mistyped sessions happen to store `unit: volts` on their spike
containers, **the predicate does not fire on them and the repair does not do what the row says**,
while every fixture still passes. That is the P-37 shape, and it is the reason this item exists
instead of P-54 being closed.
Do: over the corpus, record per session the declared `neurodata_type` and the stored `data` unit
and dtype of each acquisition container, and check the counts against the ruling's premise. Read
attributes and dtypes only; no array data is needed and none should be read.
Discriminator: the counts are measured, not restated from P-54. **P-54's own numbers are one of
the things under test** -- a scan of `D:/nwb` from this session counted 24 `.nwb` files where the
row says 22 sessions, which may be two corpora under one root or may mean the row is counting
something else.
Accept: the predicate's behaviour on the corpus is stated with counts; P-54 closes as `repaired`
if it fires where the ruling says, or the predicate is corrected if it does not.
Stop: this item reads the corpus and writes nothing to it. If access is not granted it stays
blocked rather than being closed on fixture evidence, which is the whole point of the row.

### 06-106 Gate 9 checks the Type column against the runtime

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/harness_gate.py`.
**Single-writer warning:** 06-103 and 06-105 write the same file. None of the three may run
concurrently with another.
P-151. Gate 9's two checks constrain the first column and the page-versus-generator agreement,
and nothing constrains the Type column against the live object. 06-09 proved it rather than
argued it: `_object_type_name` returning the literal `"BLINDSPOT"` for all 156 exports, page
regenerated, gate still `16 of 16`.
The test landed as `tests/test_api_md_member_types.py` with its oracle written out rather than
imported, because importing the generator's classifier rebuilds the fixed point. **The gate does
not yet run that check**, so the durable half is outstanding.
Do: wire a gate that asserts each row's Type against the runtime object, with the oracle stated
independently of `scripts/generate_api_md.py`.
Discriminator: the `BLINDSPOT` mutant must fail the gate, and the pristine tree must pass it.
Accept: the gate count rises by one, the new PASS line is counted by `grep -c '^PASS'` rather
than read off the verdict line, and the mutant is recorded in the item.
Stop: the wiring would require importing the generator to build the oracle. That reintroduces
the fixed point and is the one thing this item exists to prevent.

### 06-113 A run states the tree it ran against

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/mutation_harness.py`, `tests/test_mutation_harness_validity.py`.
**Single-writer warning:** 06-111 writes the same two files. The two may not run concurrently,
and 06-111's `expected_survivor` work is the natural companion to this one.
P-174. A mutant left by a harness that predates the journal is invisible to the journal, because
`_read_journal` returns `[]` for a **missing** file and for an **unparseable** one alike -- so an
absence of records reads as an absence of mutants, and a report that "the journal is empty"
carries no information about the tree. A mutant that suppresses a check is additionally invisible
to the suite, because the check it suppresses is the one that would fail.
Do: distinguish "no journal" from "journal says nothing outstanding", and make a run state the
tree it ran against -- compare `git status --porcelain` for tracked source paths against the set
the caller declares it intends to have modified, and refuse rather than proceed on a surprise.
Discriminator: plant a no-op-shaped mutant (one that breaks no test) in a tracked file, run, and
the run must refuse. Restore, and it must proceed. The 0.2.5 D13 mutant broke something and was
caught; this one broke nothing and was not, so **the discriminator must use the silent shape**.
Accept: a missing journal is reported as unknown rather than empty; a run over a tree with
undeclared modifications refuses; and the refusal names the offending paths.
Stop: if the check would have to enumerate legitimate in-progress edits to stay usable, stop and
say so -- a gate that must be told what to ignore becomes a gate nobody runs.

### 06-110 a type oracle for documented call shapes

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `tests/test_docs_call_shapes.py`.
P-167 remainder. P-79b, P-79c and P-82 are **not catchable by any call-shape check**: all three
`Signature.bind` cleanly and are wrong-*type*, not wrong-shape -- `plot_noise_vs_signal(units_df,
figsize=...)` really does accept two positionals. 06-100 measured this rather than assuming it.
Do: add a type oracle over the same corpus 06-100 widened, checking documented argument
expressions against annotated parameter types where both are resolvable.
Discriminator: the three named defects must be caught; the corpus must stay green otherwise.
Accept: each of P-79b, P-79c, P-82 is killed by a named assertion, and the count of corpus calls
the oracle can rule on is stated as a measured figure, not as a fraction of the whole.
Stop: if the oracle can rule on fewer calls than it skips, say so and stop -- a checker that
abstains on the majority is a proxy, which is the whole shape of P-37.

### 06-111 the mutation harness can record an intentional survivor

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/mutation_harness.py`, `tests/test_mutation_harness_validity.py`.
P-172. A `Verdict` with `killed=False` is only ever a failure, so a **measured** coverage gap
cannot be pinned in the suite and has to live in a report instead. 06-27 found two such gaps and
both are narrated rather than tested, which is exactly how a measured hole becomes a forgotten
one.
Do: add a way to declare an expected survivor with its reason, so a known gap is asserted to
still be a gap and fails loudly when someone closes it without updating the record.
Discriminator: an expected survivor that starts being killed must fail the harness.
Accept: 06-27's two measured gaps (P-170, P-171) are expressed as expected survivors and the
narration is deleted.
Stop: `scripts/mutation_harness.py` is single-writer. Do not run concurrently with any item
naming it.

### 06-112 a gate reads artifacts/state.md when it is present

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/harness_gate.py`.
**Single-writer warning:** 06-105, 06-106 and 06-111 write files in this set's vicinity; 06-105
and 06-106 write this same file. None may run concurrently.
Handover from 06-103, which could not write the gate because the file was outside its scope. A
regenerating gate is **not** tractable: `build()` shells out to `scripts/harness_gate.py` and
would recurse. A `--check`-only gate is. Absent -> PASS, because absence is the fresh-checkout
state and `reconstruct_state.py --check` already reports it.
Do: compare the `| HEAD | <40 hex> |` row against `git rev-parse HEAD` when the file is present.
Discriminator: zero the HEAD row, the gate must fail; restore it and `grep -c '^PASS'` must read
**17**, counted from PASS lines rather than off the verdict line.
Accept: gate count rises to 17 by PASS-line count, and
`tests/test_state_basis_is_checked.py::test_the_generated_prose_agrees_with_whether_a_gate_reads_the_file`
fails **by design** until the emitted sentence is updated to say what the gate does -- that
coupling is the point, and 06-103's M5 mutant proves it fires.
Stop: if the gate would need to regenerate rather than check, stop -- that is the recursion.

### 06-104 Close the skill coverage and authority gaps as one pass

Release: required-0.2.6.
Role: docs-harness. Skill: `jnwb-fact-action`. Blocked by: none.
Writes: `artifacts/skills_coverage_0.2.6.md`.
P-63, P-61, P-100 and P-101, which are one surface seen four ways and should not be four packets.
| Row | What is measured |
|---|---|
| P-63 | **30 public exports are named in no skill**, including `TFRAnalyzer`, `UnitAnalyzer`, `PopulationAnalyzer` and the whole `Query`/`Question`/`Result`/`Interpretation`/`Lineage`/`Provenance` cluster -- an agent-facing subsystem no skill discovers |
| P-61 | **Eight statements across six skills carry implementation authority rather than routing** -- joblib pool internals, the Welford accumulator, `10*log10(ratio)`, the fitted exponential form, Beta-quantile inversion, the `location`-then-`area` order, and what `granger` wraps |
| P-100 | Gate 14 gates **2 of the 6** agent role names; `authority`, `critic`, `actor` and `verifier` are ordinary English and are not gated |
| P-101 | `checked >= 65` in the skills signature test sits against **116 actual rows** -- a floor loose enough that a mass deletion passes |
**Skill files are doctrine-adjacent: this item proposes wording and applies none of it.** It writes
one artifact carrying the coverage table, the eight statements with a routing rewrite for each, and
the two harness repairs (the gate's name set, the floor).
Discriminator: the coverage count is recomputed from `jnwb.__all__` and the skill tree at the time
of writing, not copied from P-63. **P-63's own number is under test** -- a row asserting 30 was
written before this cycle changed the export surface.
Accept: every one of the four rows has either a proposed edit or a measured reason it needs none,
and the floor repair is stated as a number derived from the tree.
Stop: propose, do not apply. Any edit to `skills/**` requires Hamm, and the two harness repairs
belong to whoever holds `scripts/harness_gate.py`.

### 06-105 Make gate 8 enforce the convergence the goal says it enforces

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
**Unblocked 2026-09-20:** 06-94 closed, so the gate script is free. The previous wording recorded this item as blocking **itself** -- a typo for "06-94, since it and this item both write the gate script". Do not run concurrently with 06-103, which writes the same file.
Writes: `scripts/harness_gate.py`, `tests/test_gate8_covers_every_version_surface.py`.
P-68. `artifacts/goal.md` "Supported interpreters" claims gate 8 enforces convergence across `requires-python`, the
classifiers, the CI matrix, the install documentation, the README and release material. **Gate 8
reads three files**: `.github/`, `.readthedocs.yaml`, `pyproject.toml`. No README, no
`docs/install.md`. P-C4 is the evidence that nothing mechanical holds the rest -- it records
`docs/install.md` being corrected **by hand**.
Two repairs are available and they are not equivalent. Narrowing the claim edits
`artifacts/goal.md`, which is Hamm's slot and not an agent's to touch. **Widening the gate makes
the existing claim true and needs no ruling**, so that is the direction unless it proves
impossible.
Do: extend gate 8 to the two surfaces it omits. Derive the expected version from
`jnwb.__version__` and `pyproject.toml` rather than maintaining a list.
Discriminator: a version is skewed in the README, and separately in `docs/install.md`, and the
gate fails for each. **Prove the selector passes pristine first** -- a gate that reads a file it
cannot find also reports zero violations.
Accept: every surface `artifacts/goal.md` "Supported interpreters" names is read by gate 8, and P-68 closes as
`repaired` without `artifacts/goal.md` being edited. If some named surface genuinely cannot be
checked mechanically, say which and why, and P-68 then needs Hamm rather than this item.
Stop: do not edit `artifacts/goal.md`. If the claim cannot be made true, report that and stop.

### 06-114 `compress_fp32` takes an explicit selection

Release: required-0.2.6.
Role: jnwb-developer. Skill: `jnwb-nwb-data`. Blocked by: none.
Writes: `jnwb/compression.py`, `tests/test_compression.py`,
`skills/jnwb-nwb-data/SKILL.md`, `CHANGELOG.md`.
06-13 ruled 2026-09-22, option (b) staged. Add keyword-only `select=` (dataset paths to cast) to
`compress_fp32` and `convert`. A call naming no selection keeps today's anchored preset and emits
`FutureWarning` saying `select=` becomes required in 0.2.7. A guarded path named in `select=`
raises instead of returning a no-op with a false provenance stamp (P-104).
Discriminator: a silent call warns and its output is byte-identical to today's; `select=` naming
the preset's paths does not warn and gives the same bytes; a guarded path in `select=` raises.
Accept: P-104, P-105 and P-107 close; `CHANGELOG.md` carries an Added entry for `select=` and a
Deprecated entry for the implicit preset.
Stop: any selection rule other than an explicit path list. That is 0.2.7's to design.

### 06-115 `JRSAResult.p[0]` keeps working for one release

Release: required-0.2.6.
Role: jnwb-developer. Skill: `jnwb-population`. Blocked by: none.
Writes: `jnwb/jrsa.py`, `tests/test_jrsa.py`, `CHANGELOG.md`.
06-101 ruled 2026-09-22: fix the field, staged. The field is already fixed on `dev` (`0617d120`):
`p` and `q` are 0-d, matching `value`, `statistic` and `ci`. What the ruling adds is the stage:
indexing `p[0]` or `q[0]`, which worked on 0.2.5's shape-`(1,)` arrays, keeps returning the
scalar in 0.2.6 and emits `FutureWarning`; 0.2.7 removes the shim.
Discriminator: `float(res.p)` works without a warning; `res.p[0]` returns the same value with a
`FutureWarning`; `res.p.shape == ()`; a multi-lag result keeps shape `(n_lags,)` and no shim.
Accept: `CHANGELOG.md` carries a Changed entry (0-d `p`, `q`) and a Deprecated entry (indexing).
Stop: a shim that changes any value, dtype or arithmetic result of `p`.

### 06-116 `aggregate_to_db` refuses an estimand it cannot deliver

Release: required-0.2.6.
Role: jnwb-developer. Skill: `jnwb-lfp-spectral`. Blocked by: none.
Writes: `jnwb/spectral.py`, `tests/test_tfr_accumulator.py`, `CHANGELOG.md`.
P-114, ruled 2026-09-22: refuse now, deliver in 0.2.7. `aggregate_to_db(how="mean_of_ratios")` on
input a `TFRAccumulator` has already averaged over trials raises `ValueError` naming the estimand
it cannot deliver and the per-trial route that can.
Discriminator: the accumulator route with `mean_of_ratios` raises; `ratio_of_means` through the
same route is unchanged; per-trial input with `mean_of_ratios` is unchanged.
Accept: P-114 closes; `CHANGELOG.md` Changed entry.
Stop: the input cannot be recognised as trial-averaged without a new public marker. Then the
marker is a public API decision, and this item reports it.

### 06-117 Exploratory results say they are uncorrected

Release: required-0.2.6.
Role: jnwb-developer. Skill: `jnwb-statistics`. Blocked by: none.
Writes: `jnwb/statistics.py`, `tests/test_statistics_api_split.py`, `skills/jnwb-statistics/SKILL.md`,
`CHANGELOG.md`.
P-91, ruled 2026-09-22. `exploratory_compare` and `exploratory_multi` results gain
`correction: "none"`; the `multiple_comparison` block stays off the exploratory surface.
Discriminator: both results carry the key with value `"none"`; neither carries
`multiple_comparison`.
Accept: P-91 closes; `CHANGELOG.md` Added entry.

### 06-118 `correlate` names its method

Release: required-0.2.6.
Role: jnwb-developer. Skill: `jnwb-statistics`. Blocked by: none.
Writes: `jnwb/statistics.py`, `tests/test_statistics.py`,
`skills/jnwb-statistics/SKILL.md`, `CHANGELOG.md`.
P-92 and P-93, ruled 2026-09-22. `correlate` and `exploratory_correlate` gain keyword-only
`method=` (`"both"`, `"pearson"`, `"spearman"`), defaulting to `"both"` so current results are
unchanged. Every additive public API change gets a `CHANGELOG.md` Added entry and needs no
deprecation path, so this item also writes the missing Added entry for 06-45's `method=`.
Discriminator: each method returns only its own statistic; `"both"` is value-identical to the
current output; an unknown method raises.
Accept: P-92 and P-93 close.

### 06-119 One glossary

Release: required-0.2.6.
Role: docs-harness. Skill: none. Blocked by: none.
Writes: `docs/glossary.md`, `docs/*.md`, `mkdocs.yml`.
P-96, ruled 2026-09-22. Define both terms of each pair once, on one page: operation; workflow
(jnwb ships no pipeline); session is one NWB file and recording is a continuous series within
it; contact is a physical site and channel is a data row; electrode is one row and electrodes
table is the NWB table. Each page then uses the defined term.
Accept: P-96 closes; the page is in the MkDocs nav and `python scripts/docs_build.py` passes.

### 06-120 Gate 15 checks the dispatch map's count

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/harness_gate.py`, `tests/test_harness_adversarial_gates.py`,
`artifacts/todo_stack.md`.
P-176. The dispatch map stated "37 of the 57 items below" while the stack held 52, and gate 15,
which claims every summary count agrees with its items, passed: the count names no ids, so the
enumerated-form rule cannot see it. Either derive the count at check time and compare, or remove
the number from the prose.
Discriminator: a stack whose stated total differs from its `### 06-` count fails the gate.
Accept: P-176 closes.

### 06-121 Suite cost is measured before release

Release: required-0.2.6.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/release_gate.py`, `tests/test_semantic_mutation_classes.py`,
`tests/test_every_gate_runs.py`, `CONTRIBUTING.md`.
Goal section 8. The release check records suite wall time and the ten slowest
tests. Two tests cost about 37% of a 1120 s run: the semantic-mutation class demonstration
(326 s) and `test_every_gate_runs` parametrized over every gate (about 85 s). Reduce both
without losing a demonstrated class or a gate.
Discriminator: removing a class from the demonstration, or a gate from the parametrization, still
fails.
Accept: both tests are measured before and after with `--durations`, and the release check
prints wall time.

## Reported and not admitted

Not frozen and not scheduled. Recorded so that nothing reported disappears by not being chosen.

- **`dist/` holds only superseded artifacts.** The basis reconstruction observed `jnwb-0.1.1`, `jnwb-0.1.3` and
  `jnwb-0.2.4.tar.gz` and no 0.2.5 build, so
  `tests/test_distribution_manifest_inspection.py::test_any_distribution_present_in_this_checkout_is_clean`
  currently inspects three releases nobody ships and never the one that did. The test is not
  wrong; the evidence under it is stale. 06-37 builds a fresh artifact and is where this is
  answered, so it is recorded here rather than given its own item.
- **The ninth unreadable file.** Reported to fail at `root/units` with `Columns must be the same
  length`, separately from the eight that fail on device attributes. Not admitted; recorded so
  that repairing 06-41 is not mistaken for restoring all nine files.

## Out of 0.2.6 scope

Frozen as part of the acceptance set. Each needs its own authorization.

- Raw-data-to-NWB conversion. Documentation may route a reader toward external conversion
  systems; implementing conversion is feature expansion.
- An authorization or permission subsystem.
- Benchmark execution. The design is retained and marked unrun.
- A capability-by-capability matrix over the whole public surface.
- Repository minimization: dead tests, hand-transcribed examples, root and documentation
  cleanup. It advances no goal claim and it risks the release.
- Dataset-specific package code, and new estimators that only improve a demonstration.
- The 36 unverified review findings, except where a batch above reaches one.

## Acceptance

    no known material defect under the 0.2.6 acceptance set
  + one canonical scientific model, published and reachable
  + every public claim reproduced against the implementation that answers it
  + skills route, decline, and are tested against live behaviour
  + cross-surface and compositional audit complete over the declared 0.2.6 high-risk set
  + documentation assets render and are regenerable
  + one real NWB end-to-end example with provenance
  + published artifact independently verified from the index
  + documentation low-verbosity and consistently formed, against a declared contract
  + one precision switch and one execution switch, CPU, parallel CPU and CUDA exercised here
  + no release-blocking problem and no required item remaining, confirmed by an independent
    blocker-focused pass that discovered no new blocker (amended 2026-09-21; the record of
    discovered truth carries forward rather than being emptied)

The fifth line is bounded deliberately and does not claim package-wide semantic completeness.
The form matches 0.2.5's closure: no known material defect under a stated acceptance set, not a
claim of exhaustive correctness. What changed is that the set is cross-surface and compositional
rather than per-surface.

The last three lines were added on 2026-09-19, before this set was frozen, and they are the
three conditions of `AGENTS.md` §11. They are not a second release: 06-05 freezes this set with
them in it. The last of the three is what makes the other two hold at the same moment, because a
cycle that satisfies its conditions in sequence has satisfied none of them together.

One line that is deliberately absent: a claim that the JAX Metal backend works. It is
implemented and declared unverified, since no machine available here can execute it.
