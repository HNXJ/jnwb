# Ruling history

Why standing rules in `AGENTS.md` read as they do, moved here so the rules file carries the rules
and this file carries their reasons. Each note names the section and ruling it explains.

## `AGENTS.md` section 11, release acceptance

### Why the three conditions are written down

0.2.5 closed as "no known material defect under its completed acceptance set", which was honest
and narrow. These three conditions are what makes the next claim wider without making it vaguer:
each one is checkable, and the third makes the other two hold at the same moment rather than in
sequence.

### Condition 3, ruled 2026-09-21

A known issue is not a release-blocking issue. The measured dynamics of 0.2.6 are why: across 29
commits the open count went 29 → 101 while the item count stayed flat, because the apparatus that
finds defects is itself the largest source of them.

The 2026-09-21 amendment corrects an error in the original third condition rather than relaxing
it. That condition already named its own failure mode — "the process that empties a stack is the
same process that fills it" — and then concluded that a global fixpoint would resolve it. It does
not. A global fixpoint over *all* discovered problems terminates only if discovery stops, and in a
repository whose auditing machinery is designed to find ever more remote process defects, discovery
stopping is a symptom rather than a goal. Narrowing the fixpoint to *release-blocking material*
problems keeps the terminating property and keeps the record complete, and the blocker predicate
is what stops the narrowing from being a loophole: it is broader than "is it in `jnwb/`", and it
deliberately catches apparatus defects that can make evidence falsely pass.

That is what makes condition 3 terminate at all: the old form could not, because the process that
empties a stack is the same process that fills it.

### Path is not a classifier

P-174 is the standing example: a mutant in a test file disabled the check that would have caught
it and made four green suite runs mean less than they said.

### Condition 3, amended 2026-09-23

The 2026-09-23 ruling moves that record from the problem stack into the todo stack: every finding
leaves the problem stack as a repair, a falsification or an item, so emptying it discards none.

### A red harness, ruled 2026-09-19

Ruled after one false positive at gate 2 of 13 left eleven gates unrun and the tree looking clean.

### Why each condition names its evidence

A condition without a check is a preference. The Metal path is declared unverified because no
machine here can run it, and an unbacked claim is worse than a stated gap.

### The question the blocker predicate asks

The question is never where a defect lives. It is whether the defect affects the artifact, a
public scientific instruction, or the validity of the evidence used to release it. The fixpoint
terminates on finding no new release-blocking material problem, not on finding nothing.

### Conformance and the red harness

Conformance to an official reference narrows what must be re-proved, not what must be exercised:
existing coverage stays and regression behaviour is still tested. A packet may never say "not my
defect" because its own diff did not cause the first failure, because that ordering is an
artifact of the runner, not a finding.

## `AGENTS.md` preamble, the library surface

### Ruled 2026-09-19 (06-02)

The previous rule named `docs/` among the places harness vocabulary may not appear. That
contradicted an intentionally agent-usable package and was already broken by four published
pages. The boundary is now public capability against internal process, not the word "agent". It
is gated where practical: Gate 14 holds `docs/` to terms that are internal by construction, and
its own list says which terms it deliberately leaves out and why, so the gaps read as decisions
rather than as coverage. The aim is that a reader of the library sees a library.

## `AGENTS.md` section 2, project state

### Why a claim is never restated here

A claim that belongs in a slot and appears in `AGENTS.md` as well has two homes and will disagree
with itself.

### Why the state file is generated and not committed

Committing mutable truth makes it record the commit before its own, so it is stale from the moment
it lands. `python scripts/reconstruct_state.py --check` answers in about a third of a second
whether the file on disk was built at the current HEAD. Why the slot needed an artifact at all is P-C7.

### The todo stack's form

The stack groups work under the version that will carry it:

```markdown
# i.j.k
- do this
- test this
- if X: do Y; else: do Z

# i.j.(k+1)
- ...
```

A finished item is deleted because git, the changelog and receipts already hold history, and a
copy of completed work in the stack goes stale.

## `AGENTS.md` section 3, the baseline check in Prepare

The check is first because the worktree provisioner has branched agents 192, 202, 205 and, most
recently, 232 commits behind their stated baseline (P-28, P-153). In each case the cited line
numbers pointed at unrelated code, the named artifacts did not exist, and nothing errored.
`git reset --hard` is ruled out because it discards work the tree may be carrying for someone
else. A packet names a commit and never a
distance for the reasons, and with the measurements, in P-153's row. `scripts/verify_lane.py`
names which of the two drift directions it found.

## `AGENTS.md` section 4, invariants

### Moved to the fact stack, 2026-09-29 (Q3)

Invariants 4.1 to 4.6 and 4.8 became rows of `artifacts/fact_stack.md` (B1, B2, I3, S1, S2, S5,
S6, S8 to S14), and section 4 keeps a table pointing at them, so no invariant is stated twice.
Invariant 4.7 stays a rule in `AGENTS.md` by the ruling of 2026-09-29; fact S7 keeps only its
checkable half.

### The reasons the invariants carried

- Take the logarithm last: averaging decibels biases each site by its own noisiness.
- The project boundary is enforced by `tests/test_jnwb_frozen_boundary.py`. Gate 6 scanned a fixed
  forbidden-token list in `jnwb/`, `skills/` and selected docs, not `tests/` or full comment and
  docstring neutrality; widening it to all four trees is 12-07, which is why fact B2 is UNHELD.
- Call the library function instead of retyping its rule: a retyped copy drifts from the
  docstring unnoticed.

## `AGENTS.md` section 5, vocabulary

### Spikes and LFP, ruled 2026-09-29 (Q-2)

The old section 5 said not to pool spikes and LFP "without namespacing", as item 1 of
"Core scientific invariants" in `CONTRIBUTING.md` does, while the router skill said never to
pool them. Hamm ruled that the router's rule binds: spikes and LFP are never pooled,
namespaced or not.

## `AGENTS.md` section 6, tools

`scripts/docs_build.py` is used instead of bare `mkdocs` because PATH may point at another
interpreter; `CONTRIBUTING.md` says why a warning fails the publish.

Amended 2026-09-19: the section read "the floor and the newest declared version", which is the
policy that let 0.2.5 ship a 3.13 classifier no CI leg exercised. What replaced it is stated in
`artifacts/goal.md` and is fact R6.

## `AGENTS.md` section 8, changes

### Routing rows change with the API

The routing rows in `skills/` hardcode signatures and nothing else keeps them true. Because
`tests/test_skills_validation.py` checks every row against `inspect.signature`, a public API
change that skips them fails the suite instead of shipping a row that calls the old signature.

### One writable agent per worktree

This is not advisory. On 2026-09-15 two implementation agents ran against one worktree at once,
both auditing 0.2.4-04. One session's 26 zFLIP tests were written, run green, and then overwritten
by the other agent between the test run and the commit, so the commit that should have carried
them held only the source file. Nothing errored; the tests ceased to exist, and the loss was found
later from a reflog entry naming a commit that session had not made.

The failure mode is that a shared worktree makes a clean `git status`, a passing test run and a
successful commit each true and jointly meaningless. Recoverable history does not make a shared
worktree safe for concurrent writers.

Six lanes have been dispatched into the main checkout at once; P-144 carries what happened and
why nothing broke.

The rule once sent the reader to "the single-writer recovery protocol in
`artifacts/todo_stack.md`". The todo stack no longer holds one; the protocol is the one sentence
the rule now states itself (unowned changes are evidence; no stash, reset, restore, checkout,
reformat or `git add -A` while they exist).

## `AGENTS.md` section 12, autonomy

The stops bind at `max` because continuing past any of them would require inventing authority.
The listed non-stops are the work itself, not a reason to hand it back.
