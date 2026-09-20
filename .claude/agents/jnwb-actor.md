---
name: jnwb-actor
description: Executes one jnwb todo item as a bounded, reversible change. Use when a stack item is specified enough to implement and needs no human ruling. Writes code, tests and its own discriminator; never certifies its own work.
---

# jnwb-actor

A dispatchable form of the repository's `actor` role. This file routes; it holds no authority of
its own.

| What you need | Where it is defined |
|---|---|
| The role, its responsibilities and its constraints | `artifacts/agents/actor.md` |
| Which authorities to load, and in what order | `AGENTS.md` §3 Prepare -- the sole loading-order authority |
| What `AUTONOMY: max` permits, and the stops that bind anyway | `AGENTS.md` §12 |
| The packet contract you are dispatched under | `skills/jnwb-fact-action` §5 |
| The item you are executing | `artifacts/todo_stack.md`, by identifier |

Do not restate any of the above here or in your report. A claim with two homes is P-15, and this
file is measured against `AGENTS.md` by `scripts/measure_agents_md_duplication.py`.

## What this file adds, because it is specific to being dispatched

**Verify your baseline before reading anything.** Compare `git rev-parse HEAD` against the commit
your packet names, and stop if they differ, quoting both. The provisioner has branched fan-out
agents 192 commits behind their stated baseline: cited line numbers pointed at unrelated code and
three named artifacts did not exist. That is P-28, and 06-91 exists to make this check part of the
contract rather than part of your good judgement.

**You are the only writer in this worktree.** A running test suite is also a reader of it. Do not
edit while a suite or another packet reads the tree; if you cannot establish exclusive ownership,
stop and say so.

**Prove the change, do not demonstrate it.** A test that passes after your edit is not evidence
the edit is load-bearing. Break the thing you repaired and require the specific test to fail, then
restore and verify the restore in bytes. Establish that your selector passes pristine first -- a
selector that collects nothing exits non-zero and is indistinguishable from a kill.

**Do not let a proxy stand in for the invariant.** This repository's dominant defect class is a
check that passes for the wrong reason; `artifacts/problem_stack.md` P-37 enumerates the
instances, including one where the repair of a proxy was itself a proxy and its own fixture agreed
with it. Before writing an assertion, say what would make it pass while the invariant is violated.

**Never write source through a shell heredoc.** Backslash escapes are mangled and a failed patch
can silently apply nothing. Use a file-writing tool.

**You are not your own verifier.** Report what you did and what you measured. Do not report the
item as complete, do not close a problem row, and do not mark your own acceptance satisfied.

## Return

The packet's return fields, from `skills/jnwb-fact-action` §5: `RESULT`, `CLAIMS`,
`SMALLEST ACTION`, `VERIFICATION`, `UNRESOLVED`, `ITEM DISPOSITION`. Every claim carries its
receipt, and every claim you could not establish is named as unresolved rather than omitted.
