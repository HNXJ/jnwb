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
`efdba80`). Of its seven admitted items, 06-43 was refuted by a working composition and
deleted; 06-41 is being rewritten after its first framing proved to test a path the reporter's
files cannot reach; 06-42, 06-44 through 06-47 stand.

A consumer report is evidence of a consumer's experience, not of a jnwb defect. Its items are
reproduced here against this tree before anything is written, and the three capability and
dependency asks end in a scoping proposal for a human ruling, never in an implementation: new
capability is frozen out of this cycle by the non-goals below.

**Every imported finding enters as a hypothesis to reproduce, never as a defect to implement.**
The review's own adversarial pass refuted four findings that read as solid.

## Batch 0. Goal and authority

The goal statement is the artifact 0.2.6 is scored against, and two of its three pillars name
capabilities that do not exist and that this cycle decides not to build. Repairing the
repository against an unrevised goal cannot produce a valid result.

The direction of repair is fixed: **package evidence plus human ruling produces the corrected
goal.** A desired presentation never produces a new package identity. This binds the "dynamic"
wording, the AI-native positioning and the topology figure in particular.

Batch 0 completes before any substantive edit elsewhere. Three of its six items require a human
ruling and cannot be dispatched to any agent.

The basis reconstruction and the findings disposition are done and therefore deleted. Their
results live in `artifacts/findings_0.2.6.md`, which resolves all 83 review identifiers, and in
`artifacts/problem_stack.md`, which carries what they found and could not repair.

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

### 06-41 Rule on opening a file that lacks a required field

Role: human ruling. Skill: none. Blocked by: none. Writes: `artifacts/goal.md` if the ruling
changes a non-goal.
The measurement is complete and this item is now only the ruling it produced. Its first framing
named the wrong defect: it asked about length-1 device attribute arrays, and that framing tested
a path the reporter's files cannot reach.

A 2x2 reproducer -- `session_description` present or absent, crossed with device attributes
scalar or length-1 object array -- was measured through both `pynwb.NWBHDF5IO` and
`jnwb.nwb_io.read_nwb`, with the mutations confirmed in bytes with h5py before every read:

| | device attrs scalar | device attrs length-1 array |
|---|---|---|
| `session_description` present | both open | pynwb `ConstructError`; **jnwb opens**, `description` a `str` |
| `session_description` absent | both refuse | both refuse, **for different reasons** |

The consumer's corpus is the bottom-right cell. jnwb refuses there at `jnwb/nwb_io.py:71` with
`MissingRequiredNWBFieldError`, and it refuses *first*: `_repair_builder` was instrumented and
receives exactly one builder, `('root', 'NWBFile')`, where the passing cells pass 95 and include
the Device. HDMF never constructs the Device, so **the length-1 squeeze at `nwb_io.py:59-64` is
unreachable on that shape** -- untested, not failing. The earlier packet's reproducer carried a
`session_description`, which is the top-right cell, which is why it saw only the squeeze.

Two facts bound the ruling. There is no escape hatch today: `read_nwb` and `nwb_read_io` forward
`**kwargs` to `NWBHDF5IO` and the check at line 71 runs unconditionally for every `mode == "r"`
read, every path-taking reader funnels through it, and `docs/errors.md:153` says so outright --
"There is no argument to pass: the file is incomplete." And the refusal is deliberate, though
less clearly mandated than it first looks: `artifacts/goal.md` section 4 forbids substituting
synthetic values "for missing empirical data in an analysis path", and `session_description` is
metadata read outside any analysis path. The non-goal is adjacent to this refusal rather than the
source of it. Whether it should be read to cover required metadata is itself part of the ruling.

Rule between: (a) the refusal stands and the consumer repairs their files upstream; (b) an
explicit opt-in such as `read_nwb(path, allow_missing=("session_description",))` that refuses by
default, synthesizes nothing, and records on the returned object what it tolerated; (c) something
else.
Accept: the ruling, written into `artifacts/goal.md` if it moves a non-goal, and an item written
for the implementation if it authorizes one. See also P-17.
Stop: no agent takes this item.

### 06-42 Scope the hdmf and pandas version contradiction

Role: jnwb-developer. Skill: none. Blocked by: none. Writes: none.
Reads: `E:/omission/context/state/JNWB_HANDOUT_20260919.md` section H2.
A consumer reports that hdmf 4.3.1 declares `pandas<3,>=1.2.0`, that their corpus needs pandas
3.0.5 for units-table construction to succeed, and that installing jnwb resolves pandas back to
2.3.3 and breaks them.
Reproduce: resolve what jnwb itself declares for pandas and hdmf, and whether jnwb's declaration
or hdmf's transitive pin is what moves the resolver. A contradiction inside a dependency jnwb
merely requires is not the same finding as a contradiction jnwb declares.
Do: nothing to `pyproject.toml`. Return which side owns the pin, with the receipt.
Accept: the owner is named from the live dependency metadata, not inferred.
Stop: the answer is "hdmf must move". jnwb cannot relax another project's pin, and deciding to
diverge from a dependency's declared range is a human ruling.

### 06-61 Reconcile the skill's authority loading order with the five X slots

Role: human ruling. Skill: none. Blocked by: none. Writes: `skills/jnwb-fact-action/SKILL.md`,
`tests/test_harness_adversarial_gates.py`.
Problem P-15's sibling, recorded as P-14. `AGENTS.md` §3 now loads `goal.md`, `state.md` and
`problem_stack.md` alongside the fact and todo stacks. The skill's Mandatory Authority Loading
Order still names five items and omits three of them, and packets follow the skill rather than
this file, so three slots of `X` reach no packet.
Reproduce: `grep -n -A8 "Mandatory Authority Loading Order" skills/jnwb-fact-action/SKILL.md`
against `AGENTS.md` §3. Reproduced when the two lists differ.
Do: rule the skill amendment. A skill file is doctrine-adjacent and is not edited on a
developer's judgement.
Accept: the two orders agree and `tests/test_harness_adversarial_gates.py` asserts the agreement
by parsing both, not by listing either.
Stop: the ruling would require loading an artifact that does not exist on a fresh clone.
`artifacts/state.md` is generated and ignored, so the order must say regenerate-then-read.

### 06-62 Measure what AGENTS.md duplicates, then reduce it

Role: docs-harness. Skill: none. Blocked by: 06-61. Writes: `AGENTS.md`.
Recorded as P-15. The operating contract requires `AGENTS.md` to be a thin router -- scope,
authority, project map, canonical state, required capabilities, invariants, verification, stop
conditions -- and to duplicate no project truth. It is over 360 lines. Size is not evidence of
duplication, so measure before cutting.
Reproduce: for each section, name the slot of `X`, the skill, or the generated artifact that
already carries its content. A section with no such owner is router content and stays.
Do: move each duplicated claim to its owner and leave a pointer. Nothing is deleted that has no
other home.
Discriminator: a claim moved to its owner is found by following the pointer, and the check that
guarded it still passes.
Accept: every remaining section is router content by the contract's list, and no claim appears
in two places. Line count is the consequence, not the target.
Stop: a duplicated claim's owner does not exist yet. Create the owner or leave the claim; do not
delete it because it is repeated.

### 06-05 Freeze the acceptance set and the non-goals

Role: human ruling. Skill: none. Blocked by: 06-01, 06-02, 06-41, 06-42.
Writes: this file.
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
Writes: `scripts/harness_gate.py`, `tests/`.
Ruled 2026-09-19: supported Python is 3.12, 3.13 and 3.14, and 3.13 is added to CI rather than
having its classifier withdrawn. Immutable historical artifacts are not rewritten to look
retroactively correct.

**The surface convergence is already done and is not this item's work.** On 2026-09-19, commit
`026b9a6f`, the v0.2.5 release body was corrected to "Python 3.12 through 3.14", the CI matrix
and `PYTHON_CI_REQUIRED` gained 3.13, and `README.md`, `docs/install.md`, `AGENTS.md` and the
gate's own comments were converged on the ruling. What remains is the durable prevention the
ruling called for, and only that.

Reproduce: the gap is in the constants, not the surfaces. Gate 8 checks that the CI matrix covers
`PYTHON_CI_REQUIRED` and that the classifiers equal `PYTHON_SUPPORTED`, but nothing relates the
two constants. Revert `PYTHON_CI_REQUIRED` to `("3.12", "3.14")` and shrink the matrix to match:
gate 8 prints "all agree", the suite stays green, and a declared 3.13 goes untested again. Every
existing assertion is a containment or a membership -- `set(PYTHON_CI_REQUIRED) <=
set(PYTHON_SUPPORTED)`, floor in, head in -- and all four survive that revert. Reproduction is
that green run.
Do: make gate 8 compare the classifier set against the matrix itself, so a claimed version no leg
runs is a gate failure regardless of what the constants say. Prefer this to asserting the two
constants equal: the constants are the thing that can be edited to make the check agree with a
wrong tree.
Discriminator: the revert above, which must fail the gate afterwards and does not today.
Accept: a version in the classifiers that no CI leg exercises fails `python scripts/harness_gate.py`,
demonstrated by running it against a constructed tree carrying that defect.

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

Role: jnwb-developer. Skill: per finding. Blocked by: none.
One packet per ledger entry disposed `reproduced` and claimed by no other item, highest
consequence first. Writes: named per packet from the finding's own receipt.
Accept: each returns `repaired` with a discriminator, or `unsupported` with evidence.

### 06-44 The fdr_pval keys that are not FDR-corrected

Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: none.
Writes: `jnwb/statistics.py`, `tests/`, and the documentation page that names the keys.
A consumer reports that `fdr_pval_parametric` and `fdr_pval_nonparametric`, referenced at
`statistics.py:1117`, `:1132` and `:1147`, mirror the raw p-values. This is the same shape as
06-15: a plausible value under a label that says it is something else, returned with no error.
Reproduce: call the producing function on input whose raw and corrected p-values must differ,
and compare the `fdr_*` key against both. Reproduction is the two being equal where correction
would have changed them.
Do: either correct the values or remove the keys. Do not rename a key to something vaguer.
Discriminator: a test that fails against the current implementation and passes after.
Accept: no key whose name asserts a correction returns an uncorrected value; the choice between
correcting and removing is recorded with its reason.
Stop: removing the keys breaks a documented return schema. That is an API change and needs a
ruling.

### 06-45 Automatic dual testing in compare_groups

Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: 06-44.
Writes: `jnwb/statistics.py`, `tests/`, the routed skill file.
A consumer reports that `compare_groups` and `compare_multiple_groups` return parametric and
non-parametric results by construction, with no `test=`, which makes a pre-registered family
budget unenforceable because the caller cannot declare one primary test.
Reproduce: show from the live signature and return value that both are always computed and that
no parameter selects one.
Do: the smallest change that lets a caller name one primary test, with the second available
only on request. A docstring that merely warns is not sufficient here: the defect is that the
count of tests performed is not under the caller's control.
Discriminator: a call naming one test that returns the other's keys fails after the change.
Accept: the primary test is explicit at the call site, the existing default behaviour is either
preserved or its change recorded in `CHANGELOG.md`, and the skill row matches the new signature.
Stop: the minimal change is not backward compatible. Escalate rather than choosing.

### 06-46 permutation_test on grouped data

Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: none.
Writes: `jnwb/statistics.py` or its docstring, `tests/`.
A consumer reports that `StatisticalAnalysis.permutation_test` is a flat ungrouped shuffle with
no `groups=` or `scheme=`, while `jnwb.permutation.permute_labels` already implements grouped
schemes; they report it having shipped as a real bug once.
Reproduce: show from the live signature that no grouping is accepted, and construct grouped
input where a flat shuffle and a within-group shuffle give materially different null
distributions. Reproduction is that difference, not the signature alone.
Do: the smaller of the two admissible repairs -- accept the same grouping arguments, or state in
the docstring that the method must not be used on grouped data and name `permute_labels` as the
tool that must be used instead. Prefer the docstring where accepting grouping would duplicate
`permute_labels`.
Discriminator: whichever repair is chosen, a check that fails before it and passes after.
Accept: a caller reading only the method's own documentation cannot apply it to grouped data
believing it is correct.

### 06-47 Staggered electrode shafts read as non-linear

Role: jnwb-developer. Skill: jnwb-spiking. Blocked by: none.
Writes: `jnwb/addressing.py`, `jnwb/laminar.py`, `tests/`.
Reads: `E:/omission/context/state/JNWB_HANDOUT_20260919.md` section H3.
Admitted 2026-09-19 after the reporter named it, with H1, as one of their two unblockers.
A consumer reports that `probe_geometry` returns `is_linear=False` and `nominal_pitch=47.17`
for a shaft whose contacts advance by a constant 25 um along z with a 40 um lateral stagger in
x. `47.17` is `sqrt(25^2 + 40^2)`, so the lateral offset is being measured as advance along the
shaft. `label_layers` then refuses those channels: reportedly 9 of 36 probes and 25% of their
channels.
Reproduce: construct a two-column staggered shaft with a constant axial pitch and a fixed
lateral offset, and show `probe_geometry` reporting it non-linear with a pitch equal to the
hypotenuse rather than the axial step. Reproduction is that specific arithmetic, not merely
`is_linear=False`.
Do: measure pitch along the dominant axis of contact advance and record the lateral offset as a
stagger rather than as non-linearity. A staggered shaft is linear in the sense `label_layers`
needs, which is that depth is monotone along one axis.
Discriminator: the constructed staggered shaft, which must report the axial pitch after the
change and the hypotenuse before it; and a genuinely non-linear arrangement, which must still
report `is_linear=False` afterwards. Both directions, or the repair is just a widened tolerance.
Accept: no arrangement whose contacts advance monotonically along one axis is refused by
`label_layers` for lateral stagger alone, and the layer labels computed over a staggered shaft
are checked, not just their count. Widening which contacts are labelled changes what every
label is computed over.
Stop: the repair would change layer labels on shafts that already work. That is a silent result
change and needs a ruling, not a developer judgement.

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
The developer packet proposes the smallest high-consequence set from reproduced evidence; the
authority packet rules it. The proposal states, for every chain:

    producer -> consumer -> risk -> failure class -> existing evidence -> proposed discriminator

A count of chains is not a proposal. The six fields are what make the boundary reviewable.
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

## Batch 5. Documentation form

Condition 1 of the release acceptance in `AGENTS.md` §11. The pages are accurate after Batch 1;
this batch is about whether they can be read. A correct page nobody finishes is not reachable
documentation, and reachability is what 0.2.6 claims.

The order matters: the contract is declared first, because a verbosity or formatting judgement
made page by page is a preference, and twenty-seven pages edited to twenty-seven preferences is
worse than leaving them alone.

### 06-48 Complete the figure section of the documentation form contract

Role: docs-harness. Skill: none. Blocked by: P-24 ruling. Writes: `docs/documentation_form.md`.
The contract exists: `docs/documentation_form.md`, on the nav, written 2026-09-19. Seven form
rules, five nav rules, verbosity ceilings by page kind, and a table of four proposed rules that
were removed with the reason each was removed. Only the figure section is unfinished, and it is
unfinished for a reason that is not a writing problem.

The item's stop condition fired, as designed. "Figures are inline SVG, never raster" would forbid
what seven pages do today, and the item says that is a signal the rule is wrong rather than the
pages. It was removed and recorded as removed. The deeper obstruction is P-24: `mkdocs.yml`
declares one palette scheme, `slate`, with no light scheme and no toggle, so "renders in both
themes" is not checkable against this tree at all. Two rules survive regardless and are already
written -- no figure encodes its own background colour, and no figure is adapted from
Paper2Agent.

A third measurement belongs to the contract and is already in it: ten of twenty-seven pages are
not authored prose. `docs/api.md` is generated by `scripts/generate_api_md.py`, and the nine
`docs/tutorials/*.md` are wrappers that `--8<--` include `examples/tutorials/*.py`. Recorded as
P-25, and 06-51 now carries the carve-out.
Do: once P-24 is ruled, write the figure rules the ruling makes checkable, and delete this item.
Accept: the figure section states rules rather than an explanation of why it cannot.

### 06-49 One term per concept

Role: docs-harness. Skill: none. Blocked by: none. Writes: `docs/`, `tests/`.
Unblocked 2026-09-19: 06-48 now covers only the figure section, and vocabulary does not depend on
it. Rule F5 of `docs/documentation_form.md` is this item's target.
Reproduce: build the term inventory first. For each concept the documentation names, list every
surface form in use across `docs/`, `README.md` and the skill files. Reproduction is any concept
with more than one surface form.
Do: pick one form per concept and converge. Where two forms mean subtly different things, that
is not a synonym problem and the item records the distinction instead of collapsing it.
Discriminator: reintroduce a superseded term on one page; the check names the page and the term.
Accept: a machine-checked vocabulary list, and no concept in it with a second surface form.
Stop: a term is fixed by an upstream project, such as NWB's own nomenclature. Those are adopted,
not renamed.

### 06-50 Reorganize the left menu

Role: docs-harness. Skill: none. Blocked by: none. Writes: `mkdocs.yml`.
The nav has 28 entries and every target resolves, so this is not a broken-link item. The order is
the question: it currently reflects the order the pages were written.
Rules N1, N2, N3 and N5 of `docs/documentation_form.md` already hold -- four groups, depth two,
every target on disk, no group of one. **N4 is this item's entire content**: a top-level group is
named for the question a reader arrives with, not for the material it contains. Two measured
violations: "Getting started" carries the generated API reference, the bibliography and the
documentation-form contract, none of which anyone arriving to get started is looking for; and
"Architecture & Foundations" carries `03_representational_similarity_jrsa.md` and
`04_spectral_analysis_and_tfr.md`, which are methods rather than architecture.
Do: order by arrival. A reader arrives with one of a small number of questions, and the menu's
top level answers which question this reader has. Group depth stays at two.
Accept: every page is reachable in at most two clicks from a top-level group whose name a reader
would pick without opening it, and no group holds one page.
Stop: the ordering requires splitting or merging pages. That is 06-51's business.

### 06-51 Reduce verbosity against the contract

Role: docs-harness. Skill: none. Blocked by: 06-49. Writes: `docs/`, `README.md`.
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
Accept: the page satisfies every rule in the contract, and no fact present before is absent
after. Shorter is not the acceptance condition; shorter while lossless is.
Stop: applying the contract would delete a caveat that a test or a gate exists to enforce. Cut
the restatement, keep the one that is load-bearing.

### 06-52 Figures that carry structure

Role: docs-harness. Skill: jnwb-figures. Blocked by: 06-30, P-24 ruling. Writes: `docs/`,
`docs/assets/`, `tests/`.
Do: place the canonical diagrams from 06-30 into the pages whose structure they carry, as inline
HTML or SVG rather than as raster images, so they scale and remain searchable. Each figure is
theme-matched: no figure encodes its own background colour.

**This item's acceptance does not currently parse against the tree.** It accepted on "renders
legibly in both the light and the dark MkDocs theme" and discriminated by "switch the theme".
Measured 2026-09-19: `mkdocs.yml:25-26` declares exactly one palette scheme, `slate`. There is no
light scheme and no toggle, so there is no theme to switch to and no second rendering to compare.
Recorded as P-24. Adding a light scheme is new user-visible behaviour and a scope decision, not a
repair, so this item waits on the ruling rather than assuming either answer. Seven pages carry
raster PNGs from `docs/assets/figures/`; whether those are this item's debt to clear is the same
ruling (P-26).
Discriminator, once the ruling exists: a figure that hardcoded a colour is caught. How it is
caught depends on whether a second theme exists.
Accept: every figure renders in both themes, every figure is referenced by the prose around it,
and no page carries a figure that repeats what its adjacent table already says.
Stop: a figure would need to be adapted from Paper2Agent. Its licence forbids derivative figures
and `artifacts/direction.md` records the constraint.

### 06-53 Gate the documentation form

Role: docs-harness. Skill: none. Blocked by: 06-48, 06-49, 06-50, 06-51, 06-52.
Writes: `scripts/`, `tests/`.
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

Ruled 2026-09-19: CPU, parallel CPU and CUDA are exercised on the development machine. The JAX
Metal path is implemented and declared unverified, because no machine here can execute it. A
declared gap is admissible; an unbacked claim is not.

Ruled 2026-09-19: where an implementation matches the official documentation of the method it
implements, a citation to that documentation is sufficient evidence of correctness and the
algorithm is not independently re-derived. This narrows what must be re-proved. It does not
remove tests, and existing coverage stays.

### 06-54 Inventory the computational order

Role: jnwb-developer. Skill: none. Blocked by: none. Writes: `artifacts/`.
Measure before changing anything. For each public export whose cost grows with input size,
record the order it achieves and the order its problem admits, with the measurement that shows
it. An export whose two orders agree is recorded as such and is not touched.
Accept: a table of exports with measured and admissible order, and every gap named. No
optimisation happens under this item.
Stop: the admissible order is a research question rather than a known result. Record it as
unknown; an assumed lower bound is not evidence.

### 06-55 One precision switch

Role: jnwb-developer. Skill: none. Blocked by: none. Writes: `jnwb/`, `tests/`.
Reproduce: enumerate how precision is currently selected across the 29 modules that mention a
dtype. Reproduction is more than one mechanism, or any path where the output dtype is not
determined by the input and the caller's request.
Do: one mechanism for 32-bit and 64-bit, applied uniformly. A function that cannot honour a
requested precision says so rather than silently upcasting.
Discriminator: request the precision a function does not honour; before the change it returns
the other one silently, after it raises or is documented to promote.
Accept: the dtype of every public return is a stated function of the input dtype and the
request, and a test asserts it for the declared high-risk subset.
Stop: honouring 32-bit would change a result beyond its documented tolerance. Record the
function as 64-bit only; do not quietly return 64-bit from a 32-bit request.

### 06-56 One execution switch

Role: jnwb-developer. Skill: none. Blocked by: 06-55. Writes: `jnwb/`, `tests/`.
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

Role: jnwb-developer. Skill: per module. Blocked by: none. Writes: `jnwb/`, `docs/references.md`.
Do: where an implementation follows a published or official reference, cite that reference at the
implementation and in `docs/references.md`. Under the 2026-09-19 ruling the citation is the
evidence of correctness and the algorithm is not re-derived.
Accept: every cited reference resolves, and the citation names the specific result implemented
rather than the paper in general. A citation to a whole paper does not say which equation was
followed and is not sufficient evidence.
Stop: the implementation and the reference differ. A deliberate divergence is documented at the
divergence; an undocumented one is a defect and goes to the problem stack.

### 06-58 Reduce the orders the inventory named

Role: jnwb-developer. Skill: per module. Blocked by: 06-54, 06-57. Writes: per packet.
One packet per gap from 06-54, highest cost first.
Discriminator: a timing or operation-count measurement that separates the two orders on inputs
large enough for the difference to exceed noise.
Accept: the new order is measured, not argued, and every numerical result is unchanged within a
stated tolerance against a frozen output from before the change.
Stop: the faster order changes results beyond tolerance. Correctness outranks order.

### 06-59 Gate the computational contract

Role: jnwb-developer. Skill: none. Blocked by: 06-55, 06-56, 06-58. Writes: `scripts/`, `tests/`.
Do: make the contract enforceable -- a backend argument that selects nothing fails; a precision
request silently ignored fails; an export added without a recorded order fails.
Discriminator: each check shown failing on a seeded violation.
Accept: every check fails on its own seeded violation and passes on the live tree.

## Batch 7. Independent closure and release

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

### 06-60 Both stacks empty, verified by a pass that finds nothing

Role: critic. Skill: none. Blocked by: 06-39. Writes: `artifacts/problem_stack.md`.
Condition 3 of `AGENTS.md` §11, and the item that decides whether the release opens.
Do: one full pass over the documentation, the code and both stacks. Anything found is written to
the problem stack, which re-opens the cycle: the batch that owns it runs, and this item runs
again. The pass is not a review of the repairs, which is 06-39's job; it is a search for what
nobody has looked at yet.
Accept: `artifacts/todo_stack.md` holds no item, `artifacts/problem_stack.md` holds no `open`
problem, and this pass discovered nothing new. All three at the same moment, which is the point
of the fixpoint -- two of them holding while the third is being worked is the state every cycle
passes through and is not the terminating condition.
Stop: the pass finds something whose repair needs a human ruling. The cycle stays open; it does
not close by reclassifying the finding as `accepted`. `accepted` records that a problem cannot be
repaired, never that repairing it is inconvenient.

### 06-40 Release

Role: human, with verifier receipts. Skill: none. Blocked by: 06-60.
Writes: `jnwb/__init__.py`, `CHANGELOG.md`, `README.md`, and the release body through the API.
dev green, pull request and main green, tag validates without publishing, GitHub Release,
production index, then verification from the index in a clean environment. A tag alone validates
artifacts and does not publish; publication happens on the release.

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
  + both stacks empty, confirmed by a full pass that discovered nothing new

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
