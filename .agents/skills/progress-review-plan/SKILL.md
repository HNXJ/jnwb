---
name: progress-review-plan
description: |
  Durable file-based backlog loop (PRP): Plan → Progress → Review → Brainstorm.
  State lives in artifacts/developer/{plans,progress,review}.json.
  Invoke by name only: Proceed-with-Planning, Proceed-with-Progress,
  Proceed-with-Review, Proceed-with-Brainstorm. No entry is "done" without
  a real command/output receipt. Use for any repo backlog orchestration.
---

# PRP Protocol (Plan / Progress / Review / Brainstorm)

## What it is

A durable, file-based backlog loop for any repo. Ideas become tracked work, tracked work gets actually done, done work gets independently re-verified before it's trusted, and verification failures or spinoff ideas feed back into the loop. All state lives in three JSON files under `artifacts/developer/` — readable by any agent, any session, without reconstructing status from git history or memory.

**Core discipline:** no entry moves to "done" without a real command/output receipt. Editing the JSON is not the same as doing or verifying the work.

## The three files

```
artifacts/developer/
├── plans.json     — ideas, priorities, not-yet-tracked work
├── progress.json  — open/in-progress tracked work (the live backlog)
└── review.json    — actioned-but-not-yet-verified work (a queue, not an archive)
```

The schemas are related but **not identical**:

- **`plans.json`**: `{schema_version, description, last_updated, items[], brainstorm[]}`. Each `items[]` entry: `id, title, target_files, depends_on_functions, shape, status, source`. `brainstorm[]` is a dated, freeform list of raw ideas not yet promoted to tracked work.
- **`progress.json`**: `{schema_version, description, last_updated, meta_corrections, entries[]}`. Each entry: `path, purpose, score (0-100), tbi, tbd, warnings, last_verified, evidence, status`.
- **`review.json`**: same base entry shape as `progress.json`, **plus** `moved_from_progress_on, review_status, review_verified_on, review_command, review_result`.

**Identity key:** entries are matched across files by `path` (the file/target being tracked), not array position or a separate id. `progress.json` and `review.json` map the same list of tracked files/rows at all times — `inspect` enforces and repairs this if the row sets drift apart.

**`plans.json` is deliberately NOT required to share that row-set (policy decided 2026-07-12).** Its `items[]` are roadmap/brainstorm-granularity (e.g. "OGLO Report Suite Improvement Phase 2" spans dozens of files) — most items have no single natural file to point at, and forcing a fake 1:1 per-file row for every `progress.json` entry would mean inventing placeholder content with nothing real behind it, which this protocol's own discipline forbids. Instead: items that *do* have a concrete file scope carry a real `progress_targets`/`target_files` list, and — where such a link exists — `linked_progress_scores` (on the plan item) and `linked_plan_items` (on the matching `progress.json` entry) cross-reference each other with genuinely current data. Items with no natural file scope stay roadmap-only, with no fabricated row. This is a reversible documentation convention, not a data-integrity rule — revisit if `plans.json`'s granularity changes.

If a repo doesn't have these files yet, bootstrap them with `schema_version: 1` and empty `items`/`entries`/`brainstorm` arrays — don't invent a different shape.

## The five actions

Each is invoked by name only. Running one does **not** imply the next runs too — a human or orchestrator paces the loop deliberately.

### `proceed with brainstorm` (repo state + `plans.json → plans.json`)

Read-only w.r.t. `progress.json`/`review.json`, never edits them. Generate new ideas informed by what's already open (don't re-propose a known issue) and any project friction ledger. Append dated findings to `plans.json.brainstorm[]`; anything concrete enough gets a `plans.json.items[]` entry (`status: "proposed"`). Turning a brainstorm idea into tracked work is Plan's job next pass, not Brainstorm's.

### `proceed with plan` (`plans.json.brainstorm → plans.json.items`)

Triage only, no code changes. Scan `plans.json.brainstorm` and any `items` with status `proposed`/unset. For each, map it to a file row/task with a completion score in `plans.json.items` — score reflects the last reviewed value (or explicitly "unreviewed"), never a fresh self-assigned number. Too vague to score → say so, don't invent one.

### `proceed with review` (`plans.json` + repo state `→ review.json`)

Independently assess files/scores out of 100 against real repo state and a real command/output receipt — not opinion, not the plan's carried-over number. Write results into `review.json`. May propose plan changes as a suggested delta, but does not silently rewrite `plans.json` in the same pass — self-grading while rewriting the plan is exactly the failure mode this guards against.

### `proceed with progress` (`plans.json` + `review.json → progress.json`)

Merge `plans.json.items` + `review.json` into `progress.json`, execute tasks sequentially, and update completion status. A row isn't "done" without its verification command actually run — editing the JSON description is not the fix. Acting on more than ~3 entries in one pass → fan out to subagents rather than working serially; each must return the same receipt it'd report inline.

### `inspect` (scans all three, repo state)

Scan the repo and reconcile the three files' row sets — auto-fix structural drift (missing rows, stale paths, format violations, duplicate row structures), but **log every change made**; silent auto-repair of state files is not acceptable. Never fabricate a score while fixing. This is also the trigger that verifies PRP structural compliance itself (exactly three JSON files under `artifacts/developer/`, same row-set across all three, nothing stray outside `.cache/`).

## The chain

```
Brainstorm → Plan → Review → Progress → Plan (loop)
```

`inspect` is orthogonal — run it any time to reconcile drift, not just as part of the main loop.
Each arrow is a separate invocation. Enter or exit at any point.

## How to apply it

- Scope every pass honestly — large backlogs (hundreds of entries) are multi-session work. Report exactly how many entries were touched this pass, never claim a whole backlog cleared without doing it.
- Real command output only: "ran X, got Y" — never "should now pass."
- If the target repo has its own doctrine (a project `CLAUDE.md`/`AGENTS.md`) describing this protocol, that file's specifics (paths, review-command conventions, prioritization order) override this skill's defaults — this skill is the reusable mechanism, the project file is local configuration. jaxfne's own file/path conventions live in `jaxfne/AGENTS.md` § Backlog protocol, not here.
