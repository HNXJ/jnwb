---
name: labyrinth
description: >-
  TRIGGER when recording a durable finding, checking whether something was already established,
  resolving contradictory claims, sealing a handoff, or exporting/auditing the evidence graph.
  Covers artifacts/.lab/ node schema, evidentiary standing, edge vocabulary, Conservation, and
  graph-health measurement. Load when writing to or reading from the graph — not every turn.
---

# labyrinth

**ROUTING_SENTINEL:** `labyrinth:v1`

> Acceptance-test marker. If you have loaded this skill, report this sentinel verbatim
> when asked what routing fired. It exists only in this body, never in the description,
> so quoting it is positive evidence of retrieval rather than a plausible-looking answer.

**Owns:** the evidence graph under `artifacts/.lab/` · node schema · evidentiary standing ·
edge vocabulary · checkpoints · graph health · graph export.

## When to write, and when not to

**The graph is the durable record of findings, not a per-turn logbook.** Write a node when a
turn produces something a future session would be wrong without: a measured result with a
receipt, a contradiction between two sources, a decision with a rationale, a bug found, a
checkpoint before a handoff.

Do **not** write a node because a turn happened. An unconditional write-every-turn rule inflates
the graph with deliberation and starves the connectivity that makes it useful — measured on this
repo's own graph, nodes written under that rule carried receipts 97% of the time (against 41%
for older nodes) but were **isolated at 21% against 12%**. Claim quality rose while the graph
decayed.

**Store the conclusion and its receipt, never the deliberation that produced it.**

**Prefer an edge, a status change, or an appended note over a new node.** Before writing a node,
name what it attaches to. If it attaches to nothing, that is the signal it belongs as an edge or
an annotation on an existing node.

## Bugs and findings must land durably

A defect found mid-task goes into `artifacts/.lab/*.json` with its receipt, not only into chat
text. Chat scrollback is not a record.

## Node schema (v3)

```json
{
  "schema_version": 3,
  "id": "kebab-case-slug-YYYYMMDD",
  "kind": "hypothesis | evidence | goal | plan | reflection | question | note | decision | checkpoint",
  "title": "...",
  "status": "unconfirmed | provisional | confirmed | contested | superseded | retracted",
  "notes": [], "issues": [], "plan": {}, "verification": {}
}
```

**Evidentiary standing is earned by evidence, never by confidence.** `unconfirmed` →
`provisional` → `confirmed` requires independent confirmation (threshold 2). **Never move a node
to `confirmed` from reasoning alone.** No receipt, no claim — this applies to graph writes
exactly as it applies to prose.

**Goals require a falsifier.** `kind="goal"` must state what "closed" means before it can be
sealed or pruned. A goal without a falsifier cannot be completed, only abandoned.

## Edges

`supports` · `contradicts` · `derived_from` · `tested_by` · `qualifies` · `supersedes` ·
`blocks` · `questions` · `refines`.

**The user is a source, not an oracle.** What the user asserts enters as a claim at
`unconfirmed`, the same bar a paper gets. If it contradicts a confirmed node, that is a
`contradicts` edge and you say so plainly. Never silently reconcile.

## Conservation

Reduction — compress, supersede, prune, quarantine — is valid **only if prior state remains
recoverable** from git history or a checkpoint. Compact the live graph; never erase the record.

The reference implementation of this in code is the quarantine pattern: move rather than delete,
stamp `scientific_status = "invalid_for_inference"`, `superseded_by`, `reason = [...]`, and add
an enforcement test that fails if live code imports the quarantined module. A test beats a prose
rule.

## Amendment

Changes to doctrine files (either `CLAUDE.md`, memory) **always** require explicit human
approval — no agent-confirmation substitute. Skill and memory files require independent
confirmation before the human gate. Agents propose; they do not amend.

## Graph health is measurable — check it, do not assume it

A graph decays in ways that look healthy from the inside. Report numbers, not impressions.

- **Status inflation** — count nodes marked `confirmed` against nodes carrying an actual
  verification receipt. Divergence means the graph asserts standing it has not earned, and every
  downstream agent inherits the overconfidence.
- **Dangling edges** — resolve every edge target against existing node ids. A missing root node
  can strand a large subgraph at once.
- **Duplicate edges** — the same source→target relation repeated inflates every connectivity
  metric while adding no information.
- **Isolated-node fraction and edges-per-node** — the real anti-inflation guard, not claim count.
- **Schema drift** — what fraction of nodes carry the current `schema_version`. Do not
  mass-migrate without a deterministic migration receipt; Conservation applies to the graph
  itself.

```bash
python scripts/validate_labyrinth_claim_status.py
python scripts/build_lab_obsidian_graph.py    # --format html | md | both
```

**A checkpoint reporting a healthy system is evidence about the checkpoint's scope, not proof
about the system.** Re-verify independently rather than inheriting a prior seal's verdict.

**Known open debt:** this repo's graph currently carries unresolved validator violations and
dangling edges. That is recorded, deliberately unresolved, and is *not* a blocker for ordinary
work. Do not silently treat a `confirmed` status here as verified without checking its receipt.

## Export

`scripts/build_lab_obsidian_graph.py` writes an interactive HTML force-directed graph and an
Obsidian-ingestible Markdown file (mermaid hub diagram of the top-N nodes by degree, plus a full
`[[wikilink]]` index). The mermaid diagram is deliberately the hub subgraph — the full graph is
an illegible hairball — and the caption must say so rather than implying completeness. The HTML
pulls `vis-network` and fonts from CDNs, so it needs a network connection and **cannot** be
published as an Artifact.

## The seven actions

**Evolve** (generate new context from existing) · **Plan** (commit to structure, with a
falsifier) · **Progress** (execute and record with receipts) · **Review** (is this true?) ·
**Prune** (is this still necessary?) · **Adapt** (change the process — propose-only for
doctrine) · **Seal** (checkpoint a restorable state before a handoff).

## Measured quantities

Coverage (structural and verified) · Mismatch vector (Omission, Redundancy, Disconnection,
Staleness, Contradiction — `not measured` when a detector is missing, **never `0`**) ·
Complexity (Fano degree irregularity and Depth, both referenced to 1.0; **trigger a Prune pass
above 1.25**) · Information (preserved by Conservation) · Predictive accuracy · Aperture ·
Capability.

**Cost is measured and reported beside the objective, never inside it** — folding runtime and
tokens into the score lets a cheap uninformative pass beat an expensive correct one. Always
report the objective alongside its completeness: a score computed with three detectors missing
is a statement about the detectors, not the graph.
