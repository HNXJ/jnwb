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
