# Problem stack

Problems found and not yet triaged. Triage creates work in `artifacts/todo_stack.md`.

## The rule

A release requires this file to hold no problem row (`AGENTS.md` section 11, ruled 2026-09-23).
A problem leaves in one of three ways: it is repaired, or it is shown false, and its row is
deleted with the evidence in the commit message; or it moves into the todo stack as work, marked
`required-<cycle>` when it meets the blocker predicate of section 11 and `deferred-<next>`
otherwise, where `<cycle>` is the version being released and `<next>` the one after it. Git
holds every row that has left.

## Open

| ID | Problem | Found by |
|---|---|---|
| P-369 | `xflip`'s omnibus surrogate p carries no information on volume-conducted LFP: phase-randomized surrogates make channels independent, so on 10 of 10 boundary-free probes (24 contacts, exponential spatial kernel of 3 contacts, seeds 0 to 9, 100 surrogates) p was the floor 1/101. Only the `min_boundary_drop` gate rejected them. The docstring and `p_values` present p as the test of the partition | main model, 2026-10-13 |
