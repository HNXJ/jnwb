# `context/` — scientific and manuscript state

**Purpose:** where scientific truth, manuscript drafts, and the evidence trail live. Not code.

**Owns:** current-state docs (`PROJECT_STATE.md`, `EVIDENCE_ARCHITECTURE.md`,
`PUBLICATION_STYLE_CRITERIA.md`), the numbered domain reference chain (`00_*.md`–`09_*.md`),
manuscript drafts, figure source + receipts, session handoffs, superseded/archived material.

**Does not own:** analysis code (`../scripts/`, `../jnwb_ext/`), generated non-figure outputs
(`../outputs/`), the private analysis goal (lives at `context/PROJECT_STATE.md`'s sibling — see
`context/ANALYSIS_GOAL.md` once installed).

**Canonical entry points:**
- [`PROJECT_STATE.md`](PROJECT_STATE.md) — authoritative current scientific/repo state
- [`EVIDENCE_ARCHITECTURE.md`](EVIDENCE_ARCHITECTURE.md) — how a measurement becomes a claim
- [`09_conflicts_and_flagged_discrepancies.md`](09_conflicts_and_flagged_discrepancies.md) — open
  HIGH-severity items, checked before trusting any undated number

**Child-domain navigation:**
| Dir | What it holds |
|---|---|
| `figures/` | Manuscript figures 01–07 + supplements — tracked, receipts adjacent to each figure. **Protected: pre-existing concurrent work, do not move/rename anything inside.** |
| `handoff/` | Dated session-handoff bundles, oldest-first by folder name |
| `inventory/` | Superseded corpus-inventory docs (see their own superseded-in-place notes) |
| `drafts/` | Manuscript prose drafts (`omission-a-draft-v*.md`) |
| `archive/` | Superseded docs preserved on disk, gitignored, kept under Conservation |
| `draft-assets/`, `manuscript-docx/` | Gitignored, too-large-for-git editable/rebuildable assets |

**Receipts/current authority:** a receipt named beside a number in `PROJECT_STATE.md` outranks
this file's own prose, which outranks anything recalled from a prior turn. See
[`../../CLAUDE.md`](../../CLAUDE.md)'s truth-precedence tripwire.
