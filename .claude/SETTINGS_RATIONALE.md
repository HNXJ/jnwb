# Settings repair rationale

## What changed

`settings.local.json` previously granted, without prompt:

    "Bash(git add *)"
    "Bash(git commit -m ' *)"

Both are removed.

## Why

The mechanical permission was **less restrictive than the textual doctrine it sits beside**.
Doctrine requires staging exact paths, forbids wildcard staging, requires branch and upstream
verification before any commit, and says not to commit unless asked. The permission layer
pre-approved exactly the wildcard staging the text prohibits, and pre-approved committing.

Principle applied: **mechanical permissions must be at least as restrictive as textual
doctrine.** Where they disagree, the permission layer is the one that actually binds, so a
looser permission silently repeals the rule.

## What replaces it

An allowlist of read-only inspection commands, which removes real prompt friction without
granting any mutation, plus an explicit deny list for the four operations doctrine names as
requiring authorization. Staging and committing now prompt — which is the intended behavior,
since doctrine says they happen only when asked.

## Open item, user scope

`~/.claude/settings.json` sets `permissions.defaultMode: "auto"` machine-wide. That is a larger
lever than either project grant and is left unchanged pending an explicit decision.
