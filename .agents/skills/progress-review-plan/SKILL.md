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

**Identity key:** entries are matched across files by `path` (the file/target being tracked), not array position or a separate id. `progress.json` and `review.json` must stay a strict 1-1 mapping on `path` — a `path` never exists in both at once. If you find it in both, that's a bug from a prior pass; resolve it (the `review.json` copy usually wins as more current) before continuing.

If a repo doesn't have these files yet, bootstrap them with `schema_version: 1` and empty `items`/`entries`/`brainstorm` arrays — don't invent a different shape.

## The four actions

Each is invoked by name only. Running one does **not** imply the next runs too — a human or orchestrator paces the loop deliberately.

### Proceed-with-Planning (`plans.json → progress.json`)

Triage only, no code changes. Read `plans.json.items` (status `proposed`/unset) and `.brainstorm`. For each, create or re-score a `progress.json` entry with `score`, `tbi`/`tbd`, `warnings`, `evidence`. Too vague to score → say so in `warnings`, don't invent a number.

### Proceed-with-Progress (`progress.json → review.json`)

Pick highest-value entries and actually fix the underlying file/code/doc (editing the JSON description is not the fix). Acting on more than ~3 entries in one pass → fan out to subagents rather than working serially; each must return the same receipt it'd report inline. For each entry acted on: **move** it — copy into `review.json` (adding `moved_from_progress_on`, `review_status: "pending"`, `review_command`) and **delete** it from `progress.json` in the same pass. `review_command` is the exact command that will verify the change; if nothing is automatable (a prose fix), record the manual check instead. Progress never marks anything "done" itself — that's Review's job.

### Proceed-with-Review (`review.json → progress.json`, + `plans.json` for spinoffs)

For every `pending` entry, **actually run `review_command`** and resolve to exactly one outcome, then remove the entry from `review.json`:

1. **Confirmed** — command passes → update the matching `progress.json` entry (`score`, `evidence`, `last_verified`, `status: "done"`).
2. **Needs re-action** — command fails or the fix is incomplete → `progress.json` entry goes back with `score` down, `status: "open"`, and what broke appended to `warnings`/`tbd`. Front of the Progress queue, never left half-done in `review.json`.
3. **Revealed a new issue** — fix holds but exposes something else → resolve the original as (1) or (2), AND open a new `progress.json` entry (actionable now) or `plans.json.items` entry (`status: "proposed"`, future).

`review.json` trending toward empty is success. If it stalls non-empty, Review isn't actually running commands. If it's already empty with nothing to act on, that's a signal to run Brainstorm or re-score `progress.json` more critically — not evidence the repo is flawless.

### Proceed-with-Brainstorm (repo state + `plans.json → plans.json`)

Read-only w.r.t. `progress.json`/`review.json`, never edits them. Generate new ideas informed by what's already open (don't re-propose a known issue) and any project friction ledger (e.g. jaxfne's `skills/FRICTIONS_STACK.md`). Append dated findings to `plans.json.brainstorm[]`; anything concrete enough gets a `plans.json.items[]` entry (`status: "proposed"`). Turning a brainstorm idea into tracked work is Planning's job next pass, not Brainstorm's.

## The chain

```
Brainstorm → Planning → Progress → Review → Planning (loop)
```

Each arrow is a separate invocation. Enter or exit at any point.

## How to apply it

- Scope every pass honestly — large backlogs (hundreds of entries) are multi-session work. Report exactly how many entries were touched this pass, never claim a whole backlog cleared without doing it.
- Real command output only: "ran X, got Y" — never "should now pass."
- If the target repo has its own doctrine (a project `CLAUDE.md`/`AGENTS.md`) describing this protocol, that file's specifics (paths, review-command conventions, prioritization order) override this skill's defaults — this skill is the reusable mechanism, the project file is local configuration. jaxfne's own file/path conventions live in `jaxfne/AGENTS.md` § Backlog protocol, not here.
