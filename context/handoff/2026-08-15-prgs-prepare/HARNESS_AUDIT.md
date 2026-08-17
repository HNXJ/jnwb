# Harness audit — PRGS Prepare snapshot, 2026-08-15

Inventory of everything that actually controls agent behavior in this repository right now,
with path, scope, precedence, and purpose. Findings are flagged inline; nothing here has been
repaired.

## Inventory

| Source | Path | Scope | Precedence (per its own text) | Purpose |
|---|---|---|---|---|
| Global user memory | `C:\Users\nejath\.claude\CLAUDE.md` | machine-wide | safety/legal → explicit user instruction → project `CLAUDE.md` → this file | universal invariants, claims/changes/stop-condition doctrine |
| Project constitution | `C:\workspace\omission\CLAUDE.md` | this repo | adds to, never overrides, global | domain framing, "where truth lives" table, 10 numbered tripwires, working agreements, skill list |
| Project state | `context/PROJECT_STATE.md` | this repo | explicitly "contains no instructions to any agent"; wins over `EVIDENCE_ARCHITECTURE.md` while that file is `proposed` | current scientific/repo state, dated observations |
| Evidence contract | `context/EVIDENCE_ARCHITECTURE.md` | this repo | **self-declared `proposed`, not adopted** — see finding H1 | claim ladder (L0-L4), evidence-chain, receipt discipline, graph edge vocabulary |
| Skills (project) | `.claude/skills/{omission-data,omission-signal,omission-spiking,omission-statistics,omission-figures,manuscript,labyrinth}/SKILL.md` | this repo, git-tracked | loaded on trigger match, per CLAUDE.md's skill list | domain-specific procedural knowledge, TRIGGER-worded descriptions |
| Skills (user) | `~/.claude/skills/{numerical-computing,biophysical-modeling}` | machine-wide | same | cross-project technical doctrine |
| Settings | `.claude/settings.json` | this repo, **git-tracked** (deliberately, since 2026-08-12) | binds mechanically — see finding H2 | permission allow/deny lists |
| Settings rationale | `.claude/SETTINGS_RATIONALE.md` | this repo | documentation only | explains why `settings.local.json`'s looser grant was removed |
| Evidence graph | `artifacts/.lab/*.json` (421+ files) + `artifacts/.lab/labyrinth.db` | this repo, `.lab/` explicitly un-ignored (`!artifacts/.lab/` in `.gitignore`) | governed by `labyrinth` skill, not a constitution itself | durable findings/claims/receipts |
| Root .gitignore | `.gitignore` | this repo | mechanical | excludes `outputs/`, `data/`, `legacy/context_for_agents/` etc.; **does not** exclude `legacy/` itself (149 tracked files) |

**No `AGENTS.md` exists anywhere in the repo** (confirmed: `Glob **/AGENTS.md` → no matches;
`.agents/` directory exists but is empty, 0 entries besides `.`/`..`). This is intentional —
commit `47d364e`'s message states `.agents/AGENTS.md` was retired as a "second constitution"
with its invariants redistributed into the kernel (global `CLAUDE.md`) and the skills that apply
them.

## Findings

### H1 — `EVIDENCE_ARCHITECTURE.md` is self-declared unadopted, and its own required file doesn't exist

`context/EVIDENCE_ARCHITECTURE.md`'s "Acceptance" section (lines 87-98) states the contract is
adopted only when five conditions hold, including "the harness acceptance tests
(`ACCEPTANCE_TESTS.md`) pass," and explicitly: **"Until all five hold, this file is `proposed`,
and where it conflicts with a receipted result in `PROJECT_STATE.md`, that file wins."**

**OBSERVED FACT:** no `context/ACCEPTANCE_TESTS.md` exists anywhere in the repo (`Glob
context/ACCEPTANCE_TESTS.md` → no matches; a broader `Glob **/*.md` scan of `context/` also
shows no such file). The evidence contract names a canonical file that does not exist — this is
**exactly the stop condition `EVIDENCE_ARCHITECTURE.md` itself lists** ("a declared canonical
module or path that does not exist") and the one `CLAUDE.md`'s "Where truth lives" table warns
against trusting from memory. **Practical consequence:** the evidence-standing/claim-ladder
machinery (`context/EVIDENCE_ARCHITECTURE.md`) that the project's own `PROJECT_STATE.md` and
`CLAUDE.md` point to as "how a claim earns its standing" is, by its own stated rule, not
currently binding — `PROJECT_STATE.md` alone is authoritative until adoption completes. Not
clear whether this is a known, accepted, in-progress state or a dropped thread. **Surfaced, not
resolved**, per the stop-condition doctrine both files share.

### H2 — Tracked settings.json is doctrine-consistent; local override history shows the failure mode it now prevents

`.claude/settings.json` (git-tracked, per `SETTINGS_RATIONALE.md`, deliberately, since the
harness reset) currently allows only read-only git inspection commands and denies
`git add .`/`git add -A:*`/`git push --force:*`/`git reset --hard:*`. `SETTINGS_RATIONALE.md`
documents that the *previous* `settings.local.json` granted `Bash(git add *)` and
`Bash(git commit -m ' *)` without prompt — **looser than the textual doctrine sitting right
next to it**, which requires exact-path staging and asking before commits. That specific
regression is fixed. **Open item the rationale file itself flags and leaves unresolved:**
`~/.claude/settings.json` sets `permissions.defaultMode: "auto"` machine-wide — "a larger lever
than either project grant," left unchanged "pending an explicit decision." Still open as of this
audit; not evaluated further here (out of this repo's control surface).

### H3 — A stale test enforces the pre-reset harness shape (cross-reference: `JNWB_TEST_EVIDENCE.md`)

`tests/test_skill_tree_consolidation.py` asserts `.claude/skills/` contains ≥10 skills including
`jnwb-core/SKILL.md`. The 2026-08-12 harness reset intentionally reduced this to 7 project
skills and moved `jnwb-core` (and 13 others) to `context/archive/harness-reset-20260812/`. The
test was not updated and now fails against the current, intended state. This is the mirror image
of "rules no longer enforced by the implementation" — here the implementation changed
correctly and the **test** is the stale artifact. Ironically, this test's own stated purpose
(per its docstring, not independently re-read this pass, inferred from its assertions) appears
to have been to *prevent* exactly the kind of harness sprawl the 2026-08-12 reset fixed — it is
now asserting the sprawl-era shape as correct. **Recommend:** update the test's expected count
and specific-skill assertion to match the post-reset 9-skill (7 project + 2 user) shape, or
delete it if `.claude/skills/` shape is no longer considered something a `pytest` run should gate
(scope decision, not made here).

### H4 — Two stale, git-tracked competing-constitution fragments outside `.claude/`, and one untracked one

- **`legacy/` (149 git-tracked files, 7.0 MB)** — not gitignored, sits at repo root, contains
  `legacy/context/`, `legacy/tests/` (57 files, separate from the live 36-file `tests/`),
  `legacy/examples/`, `legacy/docs/constitution/` (a directory literally named "constitution").
  None of this is referenced by `CLAUDE.md`'s "where truth lives" table. **This is exactly the
  kind of "excessive context that could cause routing/drift" the audit task asks to flag** — a
  future agent globbing broadly, or asked to "check the tests," could easily pick up
  `legacy/tests/` (57 files) alongside or instead of the real `tests/` (36 files), or read
  `legacy/docs/constitution/*` as if it were current doctrine.
- **`outputs/docs/GEMINI.md`** — **gitignored** (`outputs/` is excluded via `.gitignore` line 19,
  confirmed via `git check-ignore -v`), so it is not part of the repository proper and would not
  survive a fresh clone. But it exists on this machine's working tree right now and is a full,
  internally-consistent *competing constitution* for a **different repository layout**
  (`src/analysis/registry.py`, `docs/skills/`, `D:/workspace/omission/src/` — none of which
  exist in the current `jnwb`/`scripts`/`context` layout), written for a different AI tool
  (filename `GEMINI.md`). It postdates none of the 2026-08-12 reset's cleanup (that reset only
  named `.agents/AGENTS.md` and `context/docs/CONTEXT.md` as retired competing constitutions) —
  this one was never in scope for that reset because it lives outside version control entirely.
  **Low severity** (gitignored, won't propagate to a fresh clone or another machine) but
  **nonzero** (any agent session on *this* machine that globs `outputs/docs/*.md` looking for
  documentation will find it and could be misled). Sibling files in the same directory
  (`JNWB_FINAL_STATUS.md`, `JNWB_100_GOAL_STATUS.md`, `JNWB_PROGRESS_UPDATE.md`,
  `JNWB_REAL_DATA_VALIDATION_REPORT.md`, etc. — 9 files total) were not opened this pass but are
  plausibly the same class of stale, superseded status document; not confirmed.

### H5 — `jnwb/_unused/`'s move is git-incomplete (cross-reference: `JNWB_ARCHITECTURE.md` §0/§9)

Not a harness-doctrine issue per se, but a repository-hygiene finding adjacent to the "registries
go stale silently" tripwire: the `git status` staged/unstaged split for the
`complex_tfr.py`/`markdown_report.py` move means a careless `git restore` sequence could
resurrect a duplicate file pair. Flagged here because it is exactly the kind of state a
harness-level "verify before destructive acts" check (global `CLAUDE.md`) is meant to catch
before any commit is made — this audit deliberately did not touch it.

### H6 — Duplicated/contradicted rule content: none found at the constitution level

Direct comparison of global `CLAUDE.md` and project `CLAUDE.md`: no overlapping numbered rule
found stated twice with different content. The project file's 10 tripwires are domain-specific
extensions of, not restatements of, the global file's claims/changes/stop-condition doctrine.
`PROJECT_STATE.md` and `EVIDENCE_ARCHITECTURE.md` are cleanly partitioned (state vs. semantics)
per their own opening paragraphs, and this partition holds under inspection — `PROJECT_STATE.md`
contains no instructions, `EVIDENCE_ARCHITECTURE.md` contains no corpus counts/paths. **No
contradiction found here** — this is a clean result, stated rather than omitted, per this task's
instruction not to only report failures.

### H7 — Missing skill / harness capability: no test-suite-awareness skill

None of the 9 active skills (project or user) mentions `pytest`, `tests/`, or a testing/CI
protocol. The repository has a 442-test suite with a nontrivial pass/fail/skip taxonomy (see
`JNWB_TEST_EVIDENCE.md`) and no skill tells an agent when to run it, how to interpret a skip vs.
a fail, or that `tests/` and `legacy/tests/` are different things. This is an **absence**, not a
contradiction — flagged per the task's explicit ask to surface "missing skills or harness
capabilities."

## Not evaluated this pass

- Tool permissions/capabilities beyond `.claude/settings.json`'s allow/deny lists (no MCP server
  permission audit performed here).
- `artifacts/.lab/labyrinth.db` internal schema/graph-health measurement — `PROJECT_STATE.md §7`
  already flags this as needing independent re-derivation ("re-derive, do not inherit," last
  recorded figure of 330 nodes / 395 current JSON nodes is stated stale by that file itself); not
  re-run here, out of this Prepare pass's scope (Prepare reconstructs, it does not re-derive
  graph health — that is Labyrinth-skill work).
- The 8 sibling files in `outputs/docs/` beside `GEMINI.md` (see H4) — not opened.
