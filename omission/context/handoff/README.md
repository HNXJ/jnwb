# `context/handoff/` — dated session-handoff bundles

**Purpose:** point-in-time snapshots written at the end of a significant session, for the next
session (human or agent) to reconstruct context without re-deriving it from scratch.

**Owns:** one subfolder per handoff event, named `YYYY-MM-DD-<slug>/`.

**Does not own:** current state (that's `../PROJECT_STATE.md` — a handoff bundle is a snapshot,
not a live document; do not edit one after the fact except to correct a factual error).

**Canonical entry points (newest first):**
- [`2026-08-24-f06-stage-a-complete/HANDOFF.md`](2026-08-24-f06-stage-a-complete/HANDOFF.md) —
  F04/F05 candidate atlases done, F06 Stage A (matched SPK-LFP substrate + primary geometry +
  direct dissociation test) complete and receipted, F06 Stage B/F07 not yet started
- [`2026-08-15-prgs-prepare/PRGS_PREPARE.md`](2026-08-15-prgs-prepare/PRGS_PREPARE.md) — the most
  recent full harness-reconstruction handoff
- [`pre-20260815-handouts/`](pre-20260815-handouts/) — earlier handout/audit/session-handoff docs
  (moved here 2026-08-24 from a top-level `omission/docs/`, which duplicated this folder's role
  with zero code references to any file in it — consolidated, not deleted)

**How to apply:** when starting a new large phase of work, read the newest bundle first; older
ones are historical unless a current doc explicitly cites them.
