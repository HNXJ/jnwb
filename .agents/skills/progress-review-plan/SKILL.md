# progress-review-plan (PRP v3)

Durably track backlog task state across sessions. State lives in JSON files under `artifacts/developer/`, not in chat memory.

## State Files

All state is preserved in four files under `artifacts/developer/`:
- `plans.json` — Untriaged work, ideas, brainstorm entries, and checkpoints (written by Seal).
- `progress.json` — Live backlog of open and in-progress tracked work.
- `review.json` — Actioned-but-not-yet-verified work queue (trends toward empty).
- `adapt.json` — proposed tweaks to the agent skills, rules, or memory systems.

Entries match across files by path, never in both `progress.json` and `review.json` at once. Every completed entry must include evidence (literal command + real output snippet).

## Phased Actions (Explicit Invocation Only)

1. **Brainstorm**: repo state → `plans.json`. Read-only w.r.t. progress/review. Generates ideas into `brainstorm[]`.
2. **Planning**: `plans.json` → `progress.json`. Triage only (no code changes). Scores/tags items.
3. **Progress**: `progress.json` → `review.json`. Performs the code changes. Checks `requires_explicit_gate` first. Moves acted-on entries to `review.json`.
4. **Review**: `review.json` → `progress.json`. Runs verification command. Resolves entries to `Confirmed`, `Needs-re-action`, or `New-issue`.
5. **Adapt**: session history → `adapt.json` → `skills/` / `memory`. Meta-loop proposing system modifications. approval is required for rule/memory changes.
6. **Seal**: all 4 files → `plans.json.checkpoints[]`. Marks current state as a restorable checkpoint. Fails if `review.json` is not empty, paths overlap, or done entries lack evidence.

When to skip: single-session tasks or one-off fixes do not require PRP tracking.
