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

## Batch 0. Goal and authority

The goal statement is the artifact 0.2.6 is scored against, and two of its three pillars name
capabilities that do not exist and that this cycle decides not to build. Repairing the
repository against an unrevised goal cannot produce a valid result.

The direction of repair is fixed: **package evidence plus human ruling produces the corrected
goal.** A desired presentation never produces a new package identity. This binds the "dynamic"
wording, the AI-native positioning and the topology figure in particular.

Batch 0 completes before any substantive edit elsewhere. 06-01 and 06-02 were ruled on
2026-09-19, and `artifacts/goal.md` plus the vocabulary rule at the head of `AGENTS.md` carry
those rulings. What remains of this batch is three items Hamm must decide (`AUTONOMY: none`) and
the read-only packets that assemble the evidence each decision needs.

The basis reconstruction and the findings disposition are done and therefore deleted. Their
results live in `artifacts/findings_0.2.6.md`, which resolves all 83 review identifiers, and in
`artifacts/problem_stack.md`, which carries what they found and could not repair.

### 06-62 Measure what AGENTS.md duplicates, then reduce it

Role: docs-harness. Skill: none. Blocked by: none -- 06-61 was ruled C on 2026-09-19 and deleted as complete. `AGENTS.md`
§3 is the sole loading-order authority and the skill points at it, which is the premise this
item needed. Writes: `AGENTS.md`.
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

### 06-75 Report the observed interpreter-CI policy for Hamm's fact update

Role: critic. Skill: none. Blocked by: none. Writes: none. AUTONOMY: max.
P-41. `artifacts/fact_stack.md:58` carries a policy the repository falsifies. The `fact` slot is
not agent-editable, so this packet reports and does not repair. Hamm rules the replacement text.
Hamm's instruction, binding on the shape of the report: **the fact should record observed policy
and state, not merely invert the stale wording.**
Do: report three things and nothing else. (1) The precise stale sentence at
`artifacts/fact_stack.md:58`, quoted with its line number. (2) The three actual CI legs, read from
`.github/workflows/workflow.yml`, with the line number and the operating systems each runs on.
(3) What the repository *observably* does about interpreter coverage -- the `requires-python`
floor, the classifier list, what gate 8 enforces, and whether any declared version has no CI leg.
Accept: every one of the three is quoted from the file that owns it, with a line number, and the
report proposes no replacement sentence. Proposing the wording is Hamm's, not this packet's.
Stop: the stale sentence is not at line 58, or `workflow.yml` does not run three legs. Either
means P-41's premise moved; report the correction and stop.

### 06-67 Rule the missingness truth table for the read path

Role: human ruling. Skill: none. Blocked by: none. Writes: `jnwb/nwb_io.py`, `artifacts/goal.md`, AUTONOMY: none.
`docs/errors.md`, `tests/`.
The opt-in shipped on 2026-09-19 and one cell of its behaviour is undecided. Stating it as a table
first, because sentinel semantics decided after implementation are decided by the implementation.

One correction to how this was framed. There is **no prior competing specification** for the empty
string; nothing in jnwb assigned it a meaning before this session. It was chosen here as the
least-deceptive value once pynwb made true absence impossible -- `NWBFile.__init__` takes
`session_description` as a required positional argument, so waiving jnwb's check alone leaves the
file unopenable. The question is therefore whether to introduce the overload at all, not how to
reconcile two requests.

| On disk | `allow_missing` | Today | Ruled? |
|---|---|---|---|
| present, non-empty | default | the value | yes, unchanged |
| absent | default | `MissingRequiredNWBFieldError` | yes, unchanged |
| absent | field named | opens; field reads `""`; `jnwb_waived_requirements == ("session_description",)` | **the open cell** |
| **present and empty on disk** | default | opens; field reads `""`; `jnwb_waived_requirements == ()` | **the ambiguity** |
| present, wrong type | either | undefined; no refusal exists for it | not yet a case |
| field named that jnwb never refuses on | either | `ValueError`, rejected rather than silently doing nothing | yes, unchanged |

Rows three and four are the problem: **a file that genuinely records an empty description is
value-identical to one whose description was waived.** They are distinguishable only by
`jnwb_waived_requirements`, and only for a caller who reads it. A caller who checks
`nwbfile.session_description` alone cannot tell them apart.
Rule between: (a) keep `""` and rely on the waiver attribute, documenting that the value alone
does not distinguish the two; (b) use a sentinel that cannot occur on disk, which trades
"indistinguishable from empty" for "a value no NWB reader expects"; (c) refuse a file whose
`session_description` is present and empty, making `""` unambiguously jnwb's mark -- which
changes behaviour for files that open today; (d) something else.
Accept: the ruled cell, the table written into `docs/errors.md`, and a test per row.
Stop: no agent takes this item.

### 06-64 Verify the repairs of 2026-09-19

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

### 06-65 Anchor the compression path match

Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `jnwb/compression.py`, `tests/test_compression.py`.
Recorded as P-29, and independent of the 06-13 ruling: this is wrong under every candidate
default, so it does not wait for one.
Reproduce: the corpus pattern is applied with an unanchored `.search()`. Measured by 06-13, 6 of
6 adversarial names are selected for lossy fp32 downcast, among them
`stimulus/probe_0_lfp/data`, `analysis/probe_0_lfp/data`, `scratch/backup_probe_0_lfp/data` and
`acquisition/my_probe_0_lfp/data`. A path in `/scratch` being silently downcast is not a
selection policy anyone chose.
Do: anchor the match so the pattern selects the group it names and not any path whose tail
contains it.
Discriminator: those six names, which must stop being selected, and the corpus path, which must
continue to be.
Accept: the six adversarial names are rejected, `acquisition/probe_0_lfp/data` is still selected,
and `tests/test_compression.py` passes unchanged.
Stop: anchoring changes which corpus paths are selected. That is the 06-13 ruling's business, not
this item's.

### 06-66 Point the compression provenance at a script that exists

Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `jnwb/compression.py`, `tests/`.
Recorded as P-30. `compress_fp32` stamps every output with
`conversion_script = "scripts/convert_nwb_compressed.py"`, which is not in the repository. Every
compressed file carries provenance naming a script nobody can run. Carried from
`alignment_review_0.2.5.md:611` and still true.
Do: stamp something that resolves -- the public entry point that actually performed the
conversion is the obvious candidate.
Discriminator: a check that resolves the stamped value against the tree and fails when it does
not exist. The reason this survived a release is that nothing ever resolved it.
Accept: the stamp resolves, and the check fails on a seeded bad stamp.

### 06-05 Freeze the acceptance set and the non-goals

Role: human ruling. Skill: none. Blocked by: 06-13. AUTONOMY: none.
Writes: this file.
06-01 and 06-02 were ruled on 2026-09-19 and are no longer blockers; 06-13 is the last one.
Freeze the set from **live reproduced state**, not by copying the planning text: each condition
is re-established against this tree at the moment of freezing, and one that cannot be reproduced
does not enter the set.
Accept: the frozen set is dated and the non-goals section below is part of it.

### 06-68 Gate the public-vocabulary boundary

Role: jnwb-developer. Skill: none. Blocked by: none. Writes: `scripts/harness_gate.py`,
`tests/test_harness_adversarial_gates.py`, `AGENTS.md` docstring list.
06-02 was ruled on 2026-09-19: public documentation may describe agents, skills and routing as
public capabilities; internal repository-agent roles, harness and process vocabulary, private
coordination state and implementation-only terminology may not appear there. The ruling says to
gate the distinction mechanically **where practical**, and the phrase is load-bearing: the old
rule failed because it gated the word "agent", which is a proxy for the boundary and not the
boundary. Do not rebuild that.
Reproduce: `grep -rni "packet\|todo stack\|problem stack\|worktree\|harness gate\|fan out" docs/`
and record which hits are internal process and which explain a public interface. Reproduced when
the two sets are distinguishable by a rule you can state in one sentence.
Do: gate the terms that are internal by construction and have no public-interface use --
delegation packets, the todo and problem stacks, worktrees, batches, harness gates, agent role
names from `artifacts/agents/`. Do not gate "agent", "skill" or "routing".
Discriminator: a new `docs/` page containing "delegation packet" fails the gate; `docs/agents.md`
and the four published pages that legitimately describe agent-assisted use pass unchanged.
Accept: the gate runs in the collect-all table with its own number, the module docstring lists
it, and the existing 13 gates still pass.
Stop: the one-sentence rule cannot be stated, or the gate can only pass by editing the four
published pages. Both mean the boundary is not yet mechanical; say so and leave it to prose.

## Batch 1. Public truth and reachability

### 06-06 Publish the canonical architecture page

Role: docs-harness. Skill: jnwb. Blocked by: none -- 06-01 and 06-02 were both ruled
2026-09-19 and deleted as complete. This item read as blocked for a day after it was not.
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

### 06-11 Gate the release body

Role: jnwb-developer. Skill: none. Blocked by: none.
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

### 06-13 Rule the default selection of compress_fp32

Role: human ruling. Skill: none. Blocked by: none. Writes: this file, then an implementation item. AUTONOMY: none.
The item's named stop condition fired, and it was proven mechanically rather than asserted. The
mechanical split -- generic mechanics, with selection as an explicit `select=` caller input -- is
designed and ready. It is blocked on one thing only: what happens when the caller says nothing.

`compress_fp32` currently selects `acquisition/probe_0_lfp/data` via the corpus pattern
`probe_\d+_(?:lfp|muae)`. Four candidate dataset-independent defaults were measured against the
corpus fixtures and **every one changes what is lost**:

| Candidate default | Diverges by |
|---|---|
| float64 and 2-D | newly downcasts `eye_position` and `convolved_spike_train` |
| float64 and basename `data` | the same two |
| float64, under `acquisition/`, basename `data` | newly downcasts `eye_position` |
| parent `neurodata_type == ElectricalSeries` | no longer casts `probe_0_lfp`, which `tests/test_compression.py:73` asserts is float32 |

Two measured facts close off the obvious escapes. The corpus fixtures carry **zero**
`neurodata_type` attributes, so type-based selection selects nothing there. And
`convolved_spike_train` is float64 and *deliberately* not downcast -- the docstring says so -- so
dtype and rank cannot separate it from LFP. A standard NWB file (`ElectricalSeries` plus an
`ecephys` module) is refused outright with `KeyError`.

Rule between: (a) the default becomes a named, caller-overridable corpus preset -- status quo,
honest about itself, but a dataset-specific literal still governs when the caller is silent;
(b) the default becomes `None` and selection is required, which breaks every existing caller;
(c) the default becomes a generic rule, which changes what is lost, including for a series the
docstring promises to preserve.

The governing principle, ruled 2026-09-19: **irreversible lossy selection must be explicit where
no generic semantic rule exists.** No candidate is semantics-preserving, so genericity alone is
not a reason to pick one. That points at (b), with a compatibility path only if its behaviour can
be documented precisely.
**Before the ruling, this table is required** -- one row per candidate policy, filled by
measurement rather than by reading the selector:

| Candidate policy | LFP | MUAe | spikes | behavioural series | arbitrary acquisition | information newly lost | previously compressed, now preserved |
|---|---|---|---|---|---|---|---|

The last two columns are the ruling. A policy that loses nothing new and preserves nothing newly
is the status quo under another name; any other policy changes which data is irreversibly reduced
to fp32, and that is what is being decided.
Accept: the table, then the ruling, then an implementation item written against it.
Stop: no agent takes this item. See also P-29, which is independent of this ruling and repairable
without it.

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

### 06-16 Sweep the substitution class

Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: none. Writes: `tests/`, then per finding.
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
The proposal is assembled and sits at `artifacts/composition_subset_proposal_0.2.6.md`: 10
chains, 11 exclusions, 6 stop conditions, with H1, H2 and H3 reproduced. The declared write
above is the **ruled** subset and stays absent until Hamm rules, so this item is not complete
when the proposal exists.
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

### 06-72 Resolve the eight duplicated claims in AGENTS.md

Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `AGENTS.md`, `artifacts/fact_stack.md` (pointer only), `CONTRIBUTING.md`.
P-15 said 436 lines against a thin-router contract, and that the duplication was unmeasured so
the size was not yet evidence. It is measured now, in `artifacts/agents_md_duplication.md`:
181 claim-bearing sentences, **8 duplicated (4.4%)** and 10 echoed (5.5%). Size is not the
defect. Eight specific claims with two homes are.
Do: for each of the eight, decide which file owns the claim and make the other one point at it.
The owner is the file whose slot the claim belongs to (`AGENTS.md` §2), not the one that says it
better. One case — the fixpoint sentence at Jaccard 1.00, verbatim in `AGENTS.md` §11 and
`artifacts/problem_stack.md` — is a pure copy and settles by deletion from the non-owner.
Discriminator: re-run the measurement script; the eight are gone and no new pair appears above
0.34.
Accept: the duplicate count is 0 at the 0.34 threshold, every gate still passes, and no claim was
deleted from both homes.
Stop: a duplicate turns out to be two different claims that merely share vocabulary. Say which,
and leave both.

### 06-73 Exclude the derived cache by path, not by extension

Role: jnwb-developer. Skill: none. Blocked by: none. Writes: `.gitignore`, `tests/`.
P-10. `.gitignore` excludes the 6.7 GB derived cache under `artifacts/developer/.cache/` by
extension (`*.pkl`). A cache file written with any other suffix lands untracked and is visible to
a careless `git add -A` — and the repository rule is to stage exact paths precisely because that
failure mode is real.
Reproduce: write a file with a non-`.pkl` suffix under that directory and confirm `git status`
shows it. Delete it afterwards and confirm the tree is clean again.
Do: exclude the directory by path. Keep the extension rule if it covers anything the path rule
does not.
Discriminator: the probe file above is invisible to `git status` after the change, and a
tracked file elsewhere with the same suffix is unaffected.
Accept: a test asserts the path exclusion, so a later `.gitignore` edit cannot silently undo it.
Stop: the cache directory is not where the row says it is. Re-measure and correct the row first.

### 06-74 Dispose of the collection-order fragility

Role: jnwb-developer. Skill: none. Blocked by: none. Writes: `tests/`, `artifacts/problem_stack.md`.
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

Role: docs-harness. Skill: jnwb-figures. Blocked by: 06-30. Writes: `docs/`,
`docs/assets/`, `tests/`.
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

Role: docs-harness. Skill: none. Blocked by: 06-49, 06-50, 06-51, 06-52. The contract itself is written.
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

Role: jnwb-developer. Skill: per module. Blocked by: 06-57. Writes: per packet.
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

Role: verifier. Skill: none. Blocked by: none. Writes: none.
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

Role: human, with verifier receipts. Skill: none. Blocked by: 06-60. AUTONOMY: none.
Writes: `jnwb/__init__.py`, `CHANGELOG.md`, `README.md`, and the release body through the API.
dev green, pull request and main green, tag validates without publishing, GitHub Release,
production index, then verification from the index in a clean environment. A tag alone validates
artifacts and does not publish; publication happens on the release.

## Batch 8. Problems found while executing 0.2.6

Every item below claims a row opened in `artifacts/problem_stack.md` after this stack was
frozen. They are collected in their own batch rather than filed into Batches 1 through 7 because
their common property is when they were found, not what they touch: each came out of a packet
measuring something else. The release condition is that both stacks are empty, so a problem
found during execution needs an item exactly as much as a problem found during planning.

Two are `AUTONOMY: none`. They are capability decisions -- what jnwb owes a mistyped corpus, and
whether an export with no consumer is an unfinished chain or a mistake -- and neither has a
repair that is correct independent of the ruling.

### 06-76 Resolve `correction='none'` and the test set that cannot reach it

Role: jnwb-developer. Skill: `jnwb-statistics`. Blocked by: none. Writes: `jnwb/jrsa.py`,
`tests/test_jrsa_correction_fallback.py`, `artifacts/problem_stack.md`.
P-50, P-51, P-52, and P-31 which P-50 supersedes. `'none'` is not a key of
`_CORRECTION_METHOD_MAP`, so `.get('none', 'fdr_bh')` returns Benjamini-Hochberg under the label
`none` when statsmodels is present, and raises `ImportError` demanding statsmodels when it is
absent -- asking for no correction requires the library that does correction. Both are live on
the main path; P-31 recorded the first as latent and that framing is now wrong.
Reproduce: call the estimator with `correction='none'` under both import conditions and record
what comes back. Do not read the call sites' short-circuit as a defence; the function is public.
Do: make `'none'` mean no correction, explicitly, in the map or ahead of it. Then repair the test
set: `SUBSTITUTED_METHODS` is derived from `_CORRECTION_METHOD_MAP`, so it is structurally
incapable of covering a value missing from that map. Enumerate the accepted values from the
documented contract instead, and assert the map matches the enumeration. Rename
`test_holm_never_returns_the_benjamini_hochberg_values`, or restore an assertion that runs, so
the name matches what it enforces. Change `p_flat * len(p_flat)` to a float multiplier.
Discriminator: delete `'none'` from wherever the repair puts it and a test must fail naming
`'none'`; the old derived-case-set spelling must fail the new enumeration assertion.
Accept: P-50, P-51, P-52 close; P-31 closes as superseded with the evidence that replaced it.
Stop: making `'none'` explicit changes what a documented default returns. Say so and stop; that
is a contract change, not a repair.

### 06-77 Refuse or reconcile the two crossover index spaces

Role: jnwb-developer. Skill: `jnwb-lfp-spectral`. Blocked by: none. Writes: `jnwb/laminar.py`,
`tests/`, `docs/`.
P-49, and the most consequential open row: layer labels are scientific output. `vflip` reorders
`psd_arr[order]` only when `probe_geometry` is supplied (`jnwb/laminar.py:297`); `label_layers`
always builds `rank` from `probe_geometry.linear_order` (`:811-815`); the boundary check compares
only channel **count** (`:763-768`). Measured: 18 of 24 contacts receive a different layer,
`accepted=True`, no warning.
Reproduce: run `vflip` without geometry and `label_layers` with it over a table order non-monotone
in depth, and count differing labels. A channel **reversal** will not do -- it is
permutation-covariant here because `probe_geometry` re-derives its principal direction, so that
test passes and proves nothing.
Do: decide which index space `crossover_contact` is in, name it in the signature or the docstring,
and make the mismatch a refusal at the boundary rather than a silent reorder. A count check is not
a frame check.
Discriminator: the non-monotone case raises or warns; the all-geometry case still returns 0 of 24
differing and stays silent.
Accept: P-49 closes, and a test holds the refusal.
Stop: the correct index space cannot be established from the code and the documentation together.
That is a contract question for Hamm, not a repair.

### 06-78 Give the preserved series a dtype test before claiming it survives

Role: jnwb-developer. Skill: `jnwb-nwb-data`. Blocked by: none. Writes: `tests/test_compression.py`.
P-48. `convolved_spike_train` appears twice in the compression tests, both times in fixture
construction, with no dtype assertion. 06-69 measured three candidate policies that downcast it
while passing 15 of 15 tests, so "the existing contract survives R1, R2 and R4" is a statement
about candidates that happen not to break an unenforced rule.
Reproduce: assert the dtype the contract requires, then apply one of 06-69's downcasting
candidates and confirm the new test fails where the 15 did not.
Do: add the assertion. Nothing else -- this item exists so 06-13 can be ruled against an enforced
contract rather than an assumed one.
Discriminator: the downcasting candidate above fails; the shipped policy passes.
Accept: P-48 closes, and 06-13's "survives" column means something testable.
Stop: the contract's required dtype is not stated anywhere. Then the contract is the thing that is
missing, and that is a finding, not a test.

### 06-79 Make the chunk shape follow the dataset rank

Role: jnwb-developer. Skill: `jnwb-nwb-data`. Blocked by: none. Writes: `jnwb/compression.py`,
`tests/test_compression.py`.
P-47, and a sequencing item rather than a policy one. `jnwb/compression.py:293`, `:339` and `:354`
all build `chunks = (min(N, shape[0]), n)` and hand it to `create_dataset` at `:172`, so a 1-D
dataset raises `ValueError: 'chunks' must have same rank`. Latent today because nothing selects a
1-D dataset, and load-bearing the moment `select=` exists, which every explicit-caller-selection
candidate in 06-13 implies.
Reproduce: compress a 1-D dataset and record the raise.
Do: derive the chunk shape from the dataset's rank. Do not special-case rank 1.
Discriminator: a 1-D and a 3-D dataset both compress; the 2-D chunk shape on the real corpus is
byte-identical to today's.
Accept: P-47 closes, and 06-13 can be ruled without its repair being blocked by this.
Stop: the corpus 2-D chunking changes at all. That is a re-baseline, not a repair.

### 06-80 Resolve every `Skill:` field against `skills/`

Role: jnwb-developer. Skill: none. Blocked by: none. Writes: `scripts/harness_gate.py`, `tests/`,
`artifacts/todo_stack.md`.
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
two stacks as well -- a `Blocked by:` field and a problem's `Answered in` column may name only
a live item. Both went stale during this release with no error: two items sat blocked by
rulings that had already happened, and two problems pointed at items deleted as complete.
Discriminator: reintroducing `jnwb-nwb-io` into any item fails the gate; every placeholder form
still passes; renaming a real skill directory fails the gate.
Accept: P-53 closes, the gate joins the collect-all table with its own number, the module
docstring lists it, and the count assertions in `tests/test_module_docstrings_match_their_code.py`
still agree on all three sides.
Stop: the placeholder forms cannot be distinguished from a typo by any rule. Then the stack's own
notation is the defect and it is repaired first.

### 06-81 Make the copy under test identifiable

Role: jnwb-developer. Skill: none. Blocked by: none. Writes: `jnwb/`, `tests/`.
P-44. The installed copy and this worktree both report `0.2.5` while their `read_nwb` signatures
differ -- the installed one raises `TypeError: unrecognized argument: 'allow_missing'`. A probe
that identifies a copy by `__version__` cannot tell them apart, which is the weak point in the
`tests inspect the selected installation` invariant: the scanners assert which copy is imported,
but a probe taking the shortcut is unprotected.
Reproduce: import both copies and compare `__version__` against `inspect.signature(read_nwb)`.
Do: decide what identifies a copy -- `__file__`, a build marker, or a dev-suffixed version -- and
make the answer available without importing a private name.
Discriminator: the two copies above compare unequal under the new identifier while both still
report `0.2.5`.
Accept: P-44 closes, and 06-35's clean-environment matrix can state which copy each cell measured.
Stop: the only honest answer is to bump the working version, which is a release decision.

### 06-82 Reach the waiver from the public API

Role: jnwb-developer. Skill: `jnwb-nwb-data`. Blocked by: 06-67. Writes: `jnwb/__init__.py`,
`jnwb/nwb_io.py`, `docs/`, `tests/`.
P-43 and P-46. `MissingRequiredNWBFieldError` is exported and documented; `read_nwb`, `nwb_read_io`,
`hdmf_build_repair_context` and `SqueezedAttributeWarning` are in neither `__all__` nor
`dir(jnwb)`, and `read_nwb(path, allow_missing=...)` is reachable only by importing the submodule
directly. **06-41 was ruled, implemented, and is unreachable from the public API** -- the caller
whose report produced the ruling cannot use what was ruled. Separately, a soft link to a valid
description is refused outright by default and with `ValueError: already exists in root.links`
when waived, although the value is on disk and reachable: refusing a file whose required field
**is** present is a false refusal, not a conservative default.
Blocked by 06-67 because the shape of the export depends on what a waiver is ruled to mean.
Reproduce: `import jnwb; jnwb.read_nwb` and record the `AttributeError`; then open the soft-link
file both ways and record both failures.
Do: export the remedy beside the error, document it on the page that documents the error, and
make the soft-link case resolve the link rather than refuse it.
Discriminator: a caller who catches `MissingRequiredNWBFieldError` can reach the waiver without
importing a submodule; the soft-link file opens with the correct description and no waiver.
Accept: P-43 and P-46 close.
Stop: 06-67 rules that a waived field must be represented in a way the current signature cannot
express. Then the signature is the item, and this one waits.

### 06-83 Verify the gate-2 administrative-entry repair

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

### 06-84 Decide whether the corpus `neurodata_type` mistyping is jnwb's problem

Role: jnwb-developer. Skill: `jnwb-nwb-data`. Blocked by: Hamm. **AUTONOMY: none.**
Writes: `artifacts/problem_stack.md`, and code only after the ruling.
P-54. Measured across 22 real sessions: 9 type spike-train containers as `ElectricalSeries`,
including an int16 dataset, 12 type the same logical series as `TimeSeries`, and 1 omits
`neurodata_type` entirely. 06-69 found this while measuring something else and no item claims it.
The decision is whether jnwb refuses, warns, or is indifferent to a container whose declared type
contradicts its contents. `artifacts/fact_stack.md` says a function's signal class must not be
silently substituted across a jnwb boundary, which argues for at least a warning; it also says
jnwb is dataset-agnostic, which argues that a corpus's typing is the corpus's business.
Those two pull opposite ways here, which is why this is a ruling and not a repair.
Accept: the row closes as a decision with its reason, or as an item that implements the decision.
Stop: this item does not implement anything before the ruling.

### 06-85 Decide the eight producers with no public consumer

Role: jnwb-developer. Skill: none. Blocked by: Hamm. **AUTONOMY: none.**
Writes: `artifacts/problem_stack.md`, and `jnwb/__init__.py` or `docs/` only after the ruling.
P-55. `assign_outer_folds`, `build_inner_validation_partitions`, `fit_exponential_onset`,
`aperiodic_fit`, `xflip`, `zflip`, `consensus_bad_trials` and `detect_band_outliers` produce output
that no public jnwb operation consumes -- the decoder accepts neither `groups` nor a fold column.
06-18's stop condition fired correctly and it did not propose them for the composition subset.
A producer whose output nothing public consumes is either an unfinished chain or an export that
should not be public, and the two have opposite repairs. `artifacts/goal.md` §2 says a skill names
an operation and documentation defines it; neither says an operation must terminate somewhere.
Accept: each of the eight is ruled as a chain to complete or an export to withdraw.
Stop: this item does not withdraw an export before the ruling. Withdrawing a public name is a
breaking change and a release decision.

### 06-86 Resolve the two sources that disagree about computational order

Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `artifacts/benchmarks/complexity_inventory.md`, `artifacts/computational_order.md`, `tests/`.
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
Accept: P-34 closes, and the word "verified" appears only where a method is named.
Stop: the script that produced the inventory no longer exists or cannot be run. Then the
inventory's claims are unfalsifiable, which is a stronger finding than a disagreement, and it is
reported rather than patched.

### 06-87 Record what reading order off the source costs

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

### 06-88 Stamp compressed files with provenance that exists

Role: jnwb-developer. Skill: `jnwb-nwb-data`. Blocked by: none.
Writes: `jnwb/compression.py`, `tests/test_compression.py`.
P-30, and worse in production than the row originally recorded: **22 of 22 real files** carry
`conversion_script = "scripts/convert_nwb_compressed.py"`, which does not exist in this
repository, and newly written files still mint it. Every compressed file points at a script
nobody can run, which is provenance that actively misleads rather than merely missing.
Reproduce: write a file and read its `conversion_script` attribute back; confirm the path does
not resolve.
Do: stamp something that resolves -- the module and the version that did the work -- or stop
claiming a script. Do not add a script to make the string true; that is satisfying the stamp
rather than the caller.
Discriminator: a test resolves the stamped provenance against the repository and fails when it
does not exist. The 22 already-written files are not rewritten; the row records that their stamp
stays wrong, which is the same shape as P-C6.
Accept: P-30 closes, and newly written files carry provenance a reader can follow.
Stop: the attribute is part of a format contract a consumer already reads. Then changing it is a
compatibility decision, not a repair.

### 06-89 Document the unit-to-layer composition

Role: docs-harness. Skill: `jnwb-population`. Blocked by: 06-49. Writes: `docs/`, `skills/`.
P-20. The composition works today through existing exports and no document or skill shows it, so
a capability that exists is unreachable by reading -- which is precisely the reachability failure
class 0.2.6 exists to close.
Reproduce: compose it from the public API and record the call sequence that works.
Do: document the sequence on the page that owns the operations, and give the routing skill a
pointer. The skill names the operation; documentation defines it, per `artifacts/direction.md`.
Discriminator: a reader following only the published page reaches layer labels from a units table
without reading source.
Accept: P-20 closes.
Stop: the composition depends on P-49's index-space defect being resolved first. Then this waits
on 06-77 and says so rather than documenting a sequence that mislabels anatomy.

### 06-90 Make an absent `peak_channel_id` visible

Role: jnwb-developer. Skill: `jnwb-population`. Blocked by: none.
Writes: `jnwb/addressing.py`, `tests/`, `docs/`.
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

### 06-91 Make a packet verify its own baseline

Role: jnwb-developer. Skill: `jnwb-fact-action`. Blocked by: none.
Writes: `skills/jnwb-fact-action/SKILL.md`, `AGENTS.md`, `tests/`.
P-28. The provisioner branched three fan-out agents from `5ecc12eb`, 192 commits behind the
`f23d96ce` their packets named. `artifacts/goal.md`, `artifacts/problem_stack.md` and
`artifacts/agents/jnwb-developer.md` did not exist there and the cited line numbers pointed at
unrelated code. All three detected it independently; a packet that had trusted its baseline would
have measured the 0.1.8 tree and reported against it as though it were current.
Measured 2026-09-20: neither `AGENTS.md` nor the skill requires a packet to check the commit it
was given against the commit its packet names. The packet contract has an `OBSERVED BASELINE`
field, and it records what the packet ran, not whether it ran it on the right tree.
Do: make the first action of a packet the comparison of `git rev-parse HEAD` against the packet's
declared baseline, and a stop condition when they differ. Skill files are doctrine-adjacent, so
propose the wording rather than applying it unilaterally.
Discriminator: a packet handed a baseline that does not match its worktree stops, and says both
SHAs.
Accept: P-28 closes.
Stop: the packet contract is Hamm's to amend. If the wording changes what a packet is obliged to
do rather than how it checks, it is a ruling.

### 06-92 Rule the fact-slot sentence on CI coverage

Role: human ruling. Skill: none. Blocked by: none. **AUTONOMY: none.**
Writes: `artifacts/fact_stack.md`, after the ruling only.
P-41. `artifacts/fact_stack.md:58` reads "CI tests the declared floor and newest supported
version." Three sources falsify it, and the important one is not the workflow:

| Source | What it says |
|---|---|
| `.github/workflows/workflow.yml:41-46` | `os: [ubuntu-latest, windows-latest]` x `python-version: ["3.12","3.13","3.14"]` -- six legs, all three declared versions |
| `AGENTS.md:200-202` | the 2026-09-19 amendment that retired this policy, with its stated reason. Read it there -- restating it here would give the claim a second home, which is P-15 |
| `artifacts/goal.md` | "Every claimed version is exercised in CI" |

The last is the one that matters: `goal` and `fact` are both slots Hamm rules, and they state
incompatible policies about the same thing. An agent loading both in the order `AGENTS.md` §3
prescribes receives two authoritative and contradictory claims.
The `fact` slot is not agent-editable, so this item assembles and does not write. Hamm's own
instruction stands: the replacement records observed policy and state, rather than merely
inverting the stale wording.
Accept: the sentence is replaced by Hamm, and `goal.md` and `fact_stack.md` agree.
Stop: this item writes nothing to `artifacts/fact_stack.md` before the ruling.

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
