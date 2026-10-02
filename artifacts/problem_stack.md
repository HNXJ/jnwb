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
