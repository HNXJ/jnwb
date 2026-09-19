# 0.2.6

Authorized 2026-09-19 as a fresh cycle. The 0.2.5 stack is not extended: its record is
`artifacts/todo_stack_0.2.5.md`, immutable, and nothing here is appended to it.

Items are deleted when done; finished work is not recorded here. The closure records in the
0.2.5 file say what each of that cycle's items measured.

0.2.5 raised per-surface correctness. The next failure class is system-level: jnwb can hold
correct code, tests, documentation and skills while its public identity, examples, diagrams,
packaging and presentation-facing claims disagree with each other or cannot be reached.
0.2.6 is a coherence, reachability and evidence release. It adds no scientific capability.

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
unverified; identifiers there are stable and are what 06-03 cites), `artifacts/planned_post_0.2.5.md`,
the two residual limits recorded by 05-85 in `artifacts/todo_stack_0.2.5.md`, and the carried
`granger_causality(order=...)` candidate.

**Every imported finding enters as a hypothesis to reproduce, never as a defect to implement.**
The review's own adversarial pass refuted four findings that read as solid.

## Batch 0. Goal and authority

The goal statement is the artifact 0.2.6 is scored against, and two of its three pillars name
capabilities that do not exist and that this cycle decides not to build. Repairing the
repository against an unrevised goal cannot produce a valid result.

The direction of repair is fixed: **package evidence plus human ruling produces the corrected
goal.** A desired presentation never produces a new package identity. This binds the "dynamic"
wording, the AI-native positioning and the topology figure in particular.

Batch 0 completes before any substantive edit elsewhere. Three of its five items require a human
ruling and cannot be dispatched to any agent.

### 06-01 Rule the corrected goal statement

Role: human ruling. Skill: none. Blocked by: none. Writes: a new goal statement, path to be
ruled.
Reads: `artifacts/direction.md`, `artifacts/alignment_review_0.2.5.md` §Confirmed.
Five decisions, each derived from package evidence rather than from a desired slide:
(a) researcher and AI agent are parallel entry paths; AI is never a mandatory intermediate
layer. (b) code, documentation and tests constrain each other, and skills route over that tested
surface holding no mutable API fact of their own. (c) authorization is not a jnwb capability; the
real boundary is that an agent may execute operations and may not decide scientific assumptions.
(d) "does not generate data" means no substitution of synthetic values for missing empirical
observations in an analysis path, with `jnwb.testing` named as test and calibration
infrastructure and not an analysis surface. (e) "dynamic" means adaptation to unfamiliar NWB
structure, not raw-data-to-NWB conversion.
Accept: the ruling exists, is dated, and every later item that cites a goal claim cites it.
Stop: any decision that would widen the package boundary; that is not a wording ruling.

### 06-02 Reconcile the agent-vocabulary rule

Role: human ruling. Skill: none. Blocked by: none. Writes: `AGENTS.md`.
Reproduce: `grep -n "Harness vocabulary" AGENTS.md` gives the rule restricting agent vocabulary
to four places, excluding `docs/`; `grep -rni "agent" docs/*.md` shows `docs/` already carries it.
Reproduced when both hold and no gate enforces either side.
A known contradiction between a rule and its own subject is a stop condition, and 06-06 writes
an architecture page into exactly the excluded directory.
Do: rule the scope of the vocabulary restriction.
Accept: the rule and `docs/` agree, and a check exists for whichever side was ruled.
Stop: the ruling would require rewriting `docs/agents.md`, which is a maintained asset four test
modules already check; surface that cost before ruling.

### 06-03 Disposition every imported finding

Role: jnwb-developer. Skill: none. Blocked by: none.
Reads: `artifacts/alignment_review_0.2.5.md`. Writes: `artifacts/findings_0.2.6.md`.
Build a ledger resolving each of the 31 confirmed and 12 dissent-carrying findings, by its
identifier, to one of: reproduced, refuted, stale, already repaired, deferred. **No finding may
disappear for falling outside a batch.** Every deferred entry records why it is out of scope and
where it stays discoverable. The 36 unverified findings are listed by identifier only, so the set
stays recoverable, and are not individually dispositioned unless a batch reaches one.
Known correction to carry: `public-claims/classifier-3-13-never-tested` is weaker than graded.
`python scripts/harness_gate.py` prints that the 3.12 floor, the classifiers and the CI matrix
"all agree", so the gate permits the gap by design; this is a policy question, not a broken gate.
Accept: every identifier in the review resolves to exactly one disposition in the ledger, and a
check asserts that the identifier sets match.
Discriminator: delete one entry from the ledger; the check fails.

### 06-04 Reconstruct the live basis

Role: jnwb-developer. Skill: none. Blocked by: none. Writes: none.
Re-resolve rather than recall: branch, HEAD, tree state, package metadata, declared Python
support, CI matrix, exports, skills, published documentation, packaging, gates.
Accept: a receipt per line, each a command and its output.
Stop: any recorded value disagrees with the live tree.

### 06-05 Freeze the acceptance set and the non-goals

Role: human ruling. Skill: none. Blocked by: 06-01, 06-02, 06-03, 06-04. Writes: this file.
Accept: the frozen set is dated and the non-goals section below is part of it.

## Batch 1. Public truth and reachability

### 06-06 Publish the canonical architecture page

Role: docs-harness. Skill: jnwb. Blocked by: 06-01, 06-02.
Reads: `artifacts/direction.md`. Writes: a new page under `docs/`, `mkdocs.yml`,
`docs/index.md`, `docs/agents.md`.
Do: extract the durable content of the ruling into a maintained page -- identity, the two entry
paths, the code/documentation/tests relation with skills acting on it, the four routing cases,
the boundary test. No ruling or process language in the public version. The artifact remains the
historical authority.
Accept: `python scripts/docs_build.py` builds strict, and the page is reachable from the
navigation.
Stop: 06-02 is unruled.

### 06-07 Gate architecture reachability

Role: jnwb-developer. Skill: none. Blocked by: 06-06. Writes: a new test module under `tests/`.
Assert: the page is a navigation target; `docs/agents.md` links it; no maintained public asset
draws the researcher-through-AI chain; the public identity does not require an agent to be
present; no maintained asset describes skills as an implementation authority.
Discriminator: reinsert the chain into a maintained page; the test fails. Remove the nav entry;
the test fails.
Accept: behaviour-shaped assertions only. A whole-prose snapshot fails this item, because it
breaks on rewording and passes on a reversed meaning.

### 06-08 Make diagrams render

Role: docs-harness. Skill: jnwb-figures. Blocked by: none.
Writes: `mkdocs.yml`, a new test module under `tests/`.
Reproduce: `grep -n "custom_fences\|mermaid" mkdocs.yml` exits non-zero while
`grep -rn '```mermaid' docs/*.md` returns five fences. Reproduced when both hold.
Do: configure rendering for the fences already present. No new diagram in this item.
Discriminator: remove the configuration; the new check fails.
Accept: a strict build produces, for each of the five pages, output carrying a mermaid container
rather than a highlighted code block containing `graph TD`. Assert against the built HTML, not
against `mkdocs.yml`.

### 06-09 Correct the SKILLS_URL entry on the public API page

Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/generate_api_md.py`, `docs/api.md`, a new test module under `tests/`.
Reproduce: `grep -n "SKILLS_URL" docs/api.md` shows it typed `function` with the `str`
constructor docstring, while a provenance-asserting probe shows `type(jnwb.SKILLS_URL) is str`
and `callable(jnwb.SKILLS_URL)` is false.
Do: repair the generator's scalar-constant branch, which enumerates container types only, then
regenerate. Never hand-patch generated output.
Discriminator: revert the generator change and regenerate; the new check fails.
Accept: no name in `jnwb.__all__` whose runtime value is not callable is typed `function` in
`docs/api.md`, and harness gate 9 still passes.

### 06-10 One truth for Python support

Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `README.md`, `docs/install.md`, and the release body through the API.
Reproduce: `gh release view v0.2.5 --json body -q .body` ends "Python 3.10 through 3.14" while
`grep -n requires-python pyproject.toml` gives `>=3.12`; `grep -n "3.10 through 3.14" CHANGELOG.md`
shows the phrase was inherited from the 0.1.0 entry. `docs/install.md` states no minimum at all.
Do: correct the release body and state the minimum on the install page.
Stop and surface: whether 3.13 is supported. Harness gate 8 reports the 3.12 floor, classifiers
`['3.12','3.13','3.14']` and CI `['3.12','3.14']` as agreeing, so the gap is permitted by design.
Absence from CI is not evidence of non-support. This half needs a ruling, not a repair.
Accept: every surface states one minimum, and the 3.13 question is recorded as ruled or open.

### 06-11 Gate the release body

Role: jnwb-developer. Skill: none. Blocked by: 06-10.
Writes: `scripts/release_gate.py`, a new test module under `tests/`.
The release body is the one version-bearing surface nothing reads, and a correct changelog does
not make it correct.
Do: check its mechanically knowable claims -- version, Python support, install command, release
status -- against package metadata. Derive rather than maintain a second prose replica.
Discriminator: a body naming a version or a Python floor that metadata contradicts is rejected.
Accept: the check runs without network access against a supplied body string, and separately
against the live body when a token is present.

### 06-12 Repair the relative_power routing row

Role: jnwb-developer. Skill: jnwb-lfp-spectral. Blocked by: none.
Writes: `skills/jnwb-lfp-spectral/SKILL.md`, `tests/test_skills_validation.py`.
Reproduce: the row states the model is named in the result; a provenance-asserting probe shows
`jnwb.relative_power` returns a bare array with no `model` attribute and no structured dtype.
Do: repair the skill claim, not the API. A richer return needs independent scientific
justification and is out of scope here.
Discriminator: restore the original wording; the new check fails.
Accept: a check covering the class, not the instance -- a skill claim about return *contents*,
which the signature harness cannot see. Note the amendment rule: the skill edit is authorized by
this item and by nothing wider.

## Batch 2. Scientific defects

### 06-13 compress_fp32 dataset specificity

Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `jnwb/compression.py`, `tests/test_compression.py`, `docs/`, `skills/jnwb-nwb-data/SKILL.md`.
Reproduce: `jnwb/compression.py:93` compiles `probe_\d+_(?:lfp|muae)`; `:107` and `:108` fix
spike-train paths; `:472` names `acquisition/probe_0_lfp`. Confirm `compress_fp32` is in
`jnwb.__all__` by probe.
Do: apply the boundary test of `artifacts/direction.md` -- generic, dataset-independent,
scientifically stable, explicitly parameterized, independently testable. Separate generic
mechanics from dataset-specific selection and make the selection an explicit caller input.
Discriminator: adversarial names that must not be matched silently, and a standard NWB layout
that must not be mistaken for the corpus one.
Accept: no dataset-specific literal governs behaviour without a caller saying so, and the
existing compression tests still pass.
Stop: preserving the current default would require keeping a corpus name in a code path; surface
the compatibility question rather than deciding it.

### 06-14 granger_causality order validation

Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: none.
Writes: `jnwb/connectivity.py`, `tests/`, `docs/08_directed_connectivity_and_information.md`,
`skills/jnwb-connectivity/SKILL.md`.
Reproduce the carried candidate at `jnwb/connectivity.py` around the `order` parameter before
anything else; it was deferred, not established.
Do: establish the allowed domain and reject invalid orders explicitly.
Discriminator: mutation-kill the validation, with the selector shown to collect and pass pristine
first.
Accept: invalid orders raise rather than returning a plausible number; documentation and the
skill row agree with the implementation.

### 06-15 The jrsa correction fallback

Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: none.
Writes: `jnwb/jrsa.py`, `tests/`.
Reproduce: `jnwb/jrsa.py:1039-1045` routes every method except `bonferroni` to
Benjamini-Hochberg when `statsmodels` is unimportable, while the recorded correction still echoes
the request. Reachable only where a declared hard dependency is absent, so reproduce by
simulating the import failure rather than by breaking the environment.
Do: raise, as the unrecognised-method path at `:1027-1034` already does. Its comment states the
principle: a run corrected one way was recorded as corrected another.
Discriminator: restore the fallback; a check asserting that `holm` never returns values
elementwise equal to `fdr_bh` on a seeded p-vector fails.
Accept: an estimator failure is not converted into a plausible labelled result.

### 06-16 Sweep the substitution class

Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: 06-15. Writes: `tests/`, then per finding.
The two repairs above share one shape: a fallback producing a differently-computed but plausible
result under the original label. Sweep the package for it rather than fixing two instances.
Do: extract the check as a module-level function and drive it over the live tree, which must find
nothing further, and over constructed seeds carrying the defect, which it must find. A sweep that
has never found anything is not evidence.
Accept: the instrument is shown to detect a seeded instance; every live hit is reproduced before
repair.

### 06-17 Confirmed findings not claimed by another item

Role: jnwb-developer. Skill: per finding. Blocked by: 06-03.
One packet per ledger entry disposed `reproduced` and claimed by no other item, highest
consequence first. Writes: named per packet from the finding's own receipt.
Accept: each returns `repaired` with a discriminator, or `unsupported` with evidence.

## Batch 3. Coherence of code, documentation, tests and skills

05-85 recorded two limits: composition's aggregation order and identifier survival were not
swept, and no capability-by-capability matrix was built. A matrix over every public symbol and
every dimension is its own release and is not attempted here. This batch closes the named limits
over a declared subset and records the subset's boundary as part of the result.

### 06-18 Declare the high-risk subset

Role: authority, on a proposal from jnwb-developer. Skill: none. Blocked by: none.
Writes: `artifacts/composition_subset_0.2.6.md`.
Name the producer-consumer chains before any test in 06-19 through 06-23 is written. Within the
declared subset, unknown is not a pass. The boundary of the subset is part of the acceptance
record, not an omission from it.
Accept: each later item in this batch cites chains from this file and adds none of its own.
Stop: a chain proposed for the subset has no consumer in the public API; that is a capability
question, not a composition one.

### 06-19 Aggregation order

Role: jnwb-developer. Skill: jnwb-lfp-spectral. Blocked by: 06-18. Writes: `tests/`.
Channel aggregation against ratio; averaging against log and dB; trial and session aggregation;
band integration; baseline normalisation; group weighting; non-finite filtering relative to
aggregation.
Discriminator: asymmetric inputs where the two orders differ by more than tolerance. An input on
which both orders agree tests nothing and fails this item.
Accept: for each chain, the documented order is the computed order, shown by execution.

### 06-20 Identifier survival

Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: 06-18. Writes: `tests/`.
Channel, unit, probe, area, trial and session identity through selection, transform, filtering,
permutation and aggregation.
Discriminator: permute the input order; a positional reassignment that has become semantic
identity produces a different answer.
Accept: no identifier is reconstructed from position anywhere in the declared subset.

### 06-21 Axis composition

Role: jnwb-developer. Skill: jnwb-lfp-spectral. Blocked by: 06-18. Writes: `tests/`.
Extend 05-85's per-function axis work to chains, especially channel-major to time-major
boundaries.
Discriminator: deliberately unequal dimensions, so a transpose cannot pass by coincidence. Equal
dimensions fail this item.

### 06-22 Failure propagation

Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: 06-18. Writes: `tests/`.
A missing, ambiguous or non-identifiable intermediate must produce an explicit downstream
failure, never a zero, a non-finite value read as a result, or an empty valid-looking output.
Accept: for each chain, the failure surfaces at the boundary where it arises.

### 06-23 Randomness propagation

Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: 06-18. Writes: `tests/`.
The caller's generator reaches every stochastic child; no child reseeds; one seed reproduces a
whole workflow; observed and null estimators stay identical where the comparison requires it.
Discriminator: a child that reseeds produces identical output across two different caller seeds.

### 06-24 Skill routing against live behaviour

Role: jnwb-developer. Skill: per skill, nine packets. Blocked by: none.
Writes: the routed skill file and `tests/test_skills_validation.py`.
Every routing row: the callable exists, the signature matches, the return type and keys match,
units match, failure behaviour matches. Conditional return schemas are in scope -- a skill must
not name a key that exists only under an unstated branch, which is the `cross_modal_comparison`
defect repaired in 0.2.5.
Accept: every claim checked by execution against the live export, not against the skill's text.

### 06-25 Decline behaviour as executable evidence

Role: jnwb-developer. Skill: per skill. Blocked by: 06-24. Writes: `tests/`, skill files.
Representative cases per applicable skill for all four outcomes of `artifacts/direction.md`:
supported routes, missing input is requested, a non-identifiable result is reported as a failure,
an unsupported claim is declined. No language model is required to test this layer: the check is
that the routed operation raises, returns a declared failure, or requests the missing input.
Accept: `direction.md` holds that a skill which cannot decline is incomplete; each skill either
satisfies that or is recorded as not requiring it.

### 06-26 Worked examples stop teaching synthesis

Role: jnwb-developer. Skill: per skill. Blocked by: none. Writes: skill files, `tests/`.
Reproduce: six of nine skill files build example inputs with a random generator; only
`skills/jnwb-nwb-data/SKILL.md` opens a file. No test executes any example block.
Do: classify every example input as real NWB, deterministic minimal array, stochastic synthetic,
or explicit calibration fixture, and default normal routing examples to the first two. The
objective is not removing generators from documentation; it is that a normal analysis instruction
never implies inventing data.
Accept: every example block executes in the suite, and each block's input class is declared and
checked.

### 06-27 Semantic mutation classes over the declared subset

Role: jnwb-developer. Skill: per chain. Blocked by: 06-18, 06-28. Writes: `tests/`.
Unit scaling, axis swap, sign flip, conjugation, density against spectrum, mean against median
and sum, log before aggregate, permutation p-value substitution, generator ignored, support gate
removed, failure converted to a default, identity restoration removed, result key deleted,
signature drift. A class list, not a mutation score.

### 06-28 Mutation harness validity as a precondition

Role: jnwb-developer. Skill: none. Blocked by: none. Writes: `tests/`, `scripts/`.
Per case, enforced by the harness itself: the pristine selector collects; the pristine selector
passes; the mutation lands exactly once; the source differs; the expected test is collected under
mutation; the mutant fails on the semantic property; the restore is byte-exact; the whole-run
digest is clean.
Selectors must be class-qualified where the test is a method: a bare test name collects nothing,
exits non-zero, and reads as a kill. Six false kills were reported this way in 0.2.5 and hid a
real gap.
Discriminator: a selector naming no test must be rejected before any verdict, not counted as a
kill.
Accept: no verdict is emitted by a harness that has not first proven its own selectors.

## Batch 4. Maintained evidence and demonstrations

### 06-29 Make generated figures maintained

Role: docs-harness. Skill: jnwb-figures. Blocked by: none.
Writes: `docs/generate_figures.py`, `tests/`, a gate.
Reproduce: nothing runs the generator -- not CI, not `scripts/harness_gate.py`, not
`scripts/release_gate.py`, not `.readthedocs.yaml`, not any test -- and re-running it reproduces
none of its outputs byte-identically.
Do: map every artifact to its generator, regenerate in isolation, gate on unexplained drift.
Accept: a tolerance the plotting stack can actually meet, justified by measurement rather than
chosen. A byte-equality gate fails this item; so does a tolerance wide enough to accept a changed
figure.

### 06-30 Produce the canonical diagrams

Role: docs-harness. Skill: jnwb-figures. Blocked by: 06-06, 06-08.
Writes: `docs/`, `docs/assets/`.
Dual entry; code, documentation and tests with skill routing over them; the four-outcome
decision; NWB to analysis; the package boundary. One maintained source each, original to jnwb.
Stop: the external prior art is licensed no-derivatives; no figure of it is adapted, in
documentation or in any presentation. That ruling is in `artifacts/direction.md` and is enforced
here, not restated.

### 06-31 One real NWB end-to-end example

Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `docs/tutorials/`, `examples/`, `tests/`.
Select a small, redistributable or remotely accessible public dataset by capability fit, not by
name. Open, inspect, select, analyse, verify, visualise, reusing the operations the skills route,
with provenance sufficient to reproduce the result.
Accept: the example runs in CI or is skipped with a stated reason, never silently.
Stop: no suitable dataset is redistributable under the licence; surface rather than substituting
a synthetic one and calling it an example.

### 06-32 Separate empirical from synthetic

Role: docs-harness. Skill: jnwb-figures. Blocked by: 06-31. Writes: `docs/`, `examples/`, `tests/`.
Visibly and structurally, in the documentation tree and in the figures.
Accept: a check that a page carrying a synthetic figure says so.

### 06-33 Retain the benchmark design as explicitly unrun

Role: docs-harness. Skill: none. Blocked by: none. Writes: `artifacts/planned_post_0.2.5.md`.
Bring the ruled hypothesis to pre-registration quality and mark it unrun. It is not an acceptance
criterion for this release: an empirical comparison whose either outcome is scientifically
admissible cannot gate a release without giving the experiment a result to reach.
Accept: task set, scoring rubric, arms, repetitions, refusal scoring and inferential unit are all
declared, and the document states that none of it has been executed.

## Batch 5. Independent closure and release

### 06-34 Adversarial mutation pass

Role: critic. Skill: none. Blocked by: all of Batch 3. Writes: none.
Seed known semantic defects and require the intended gate to catch each one. Every selector
collects and passes pristine before any verdict counts.

### 06-35 Clean-environment matrix

Role: verifier. Skill: none. Blocked by: 06-10. Writes: none.
Across the declared Python and operating-system support, resolving the 3.13 question. The
development virtualenv is not package evidence.

### 06-36 Documentation qualification

Role: verifier. Skill: none. Blocked by: 06-06, 06-08, 06-29, 06-30. Writes: none.
Strict build; diagrams render as diagrams, asserted against built output; generated assets
current; links resolve; no stale version claim; the canonical architecture page reachable from
the navigation.

### 06-37 Distribution qualification

Role: verifier. Skill: none. Blocked by: all repairs. Writes: none.
Source distribution and wheel: contents, metadata, imports, exports, `SKILLS_URL`, representative
workflows, documentation-facing constants, no checkout shadowing.

### 06-38 Fresh-install workflow

Role: verifier. Skill: jnwb-nwb-data. Blocked by: 06-37. Writes: none.
From the published candidate rather than the checkout: install, open an NWB file, analyse, verify.

### 06-39 Independent critic

Role: critic. Skill: none. Blocked by: 06-34 through 06-38. Writes: none.
A reviewer that implemented none of the repairs, over the acceptance set, the unresolved
unknowns, the mutation evidence, the public claims and the release artifacts.

### 06-40 Release

Role: human, with verifier receipts. Skill: none. Blocked by: 06-39.
Writes: `jnwb/__init__.py`, `CHANGELOG.md`, `README.md`, and the release body through the API.
dev green, pull request and main green, tag validates without publishing, GitHub Release,
production index, then verification from the index in a clean environment. A tag alone validates
artifacts and does not publish; publication happens on the release.

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

The fifth line is bounded deliberately and does not claim package-wide semantic completeness.
The form matches 0.2.5's closure: no known material defect under a stated acceptance set, not a
claim of exhaustive correctness. What changed is that the set is cross-surface and compositional
rather than per-surface.
