# Data-model design rationale: the v0.9.1 ontology/contracts effort

**Moved out of `legacy/` 2026-08-22** (repository normalization, Batch 1 item 4), consolidated
from `legacy/docs/adr/ADR-001-immutable-datasets.md` and the four `legacy/docs/constitution/`
files (`01_ontology.md`, `02_contracts.md`, `03_workflow.md`, `04_versioning.md`, ~860 lines
total). Administrative/process language (phase-completion status, THETA-protocol validation
ceremony, code-review report format) is stripped; what survives is the design objective, the
invariants, the rejected alternatives, and — checked against the current codebase, not assumed —
what actually happened to the plan.

## Objective

Circa 2026-06-25, the project proposed a formal 13-object ontology (`Session`, `Query`,
`Dataset`, `Alignment`, `EpochCollection`, `Question`, `AnalysisPlan`, `Result`,
`Interpretation`, `Figure`, `Provenance`, `Lineage`) with a fixed `Query -> Dataset -> Alignment
-> EpochCollection -> Question -> AnalysisPlan -> Result -> Interpretation -> Figure` pipeline,
frozen as the public API for a planned v1.0. The goal: make irreproducibility structurally hard
by having every object except `Figure` be immutable, provenance-carrying, and serializable, and
by having filtering/alignment operations return new objects rather than mutate in place (spelled
out at length in ADR-001, which rejected in-place `.filter()` mutation, copy-on-write, and manual
snapshot management as alternatives — each for breaking lineage tracking or adding user-facing
complexity).

## What actually happened (checked against the current tree, 2026-08-22)

**The ontology was never adopted as the primary interface.** `01_ontology.md` itself states the
plan plainly: "OmissionSession methods remain in v0.9.x for backwards compatibility. In v1.0,
OmissionSession is deprecated in favor of Query -> Dataset -> Question -> Result." That
deprecation did not happen. The current codebase's data-access layer is `OmissionSession` +
`jnwb.paths` — confirmed by the `legacy/tests/` audit (2026-08-22): grepping the current tree for
`SessionManifest`, `SignalBlock`, `DataLoader`, `Query`, `Dataset.from_query`, `EpochCollection`,
or any of the other 13 objects' class definitions returns zero matches anywhere in `jnwb/` or
`omission/`. `OmissionSession` is not a legacy holdover awaiting removal — it is, and apparently
always remained, the actual interface.

This is not the ADR's own "Alternatives Considered" list (those were rejected *before* shipping,
in favor of the ontology). This is a documented plan that shipped in doctrine but not in code —
a third category distinct from either "current design" or "considered and rejected."

## What survived anyway: the scientific contracts

The ontology's six **scientific contracts** (SC-00X, non-negotiable "what must be true about the
neuroscience") describe invariants, not the abandoned object model, and each has a live
counterpart in current doctrine — meaning the *principles* outlived the API that was built to
enforce them mechanically:

| Contract | Original rule | Current embodiment |
|---|---|---|
| SC-001 Raw Data Immutability | raw recordings/spike times never modified | `omission/CLAUDE.md` tripwire 1 (no empirical value not computed from data) |
| SC-002 Inferential Unit Transparency | every analysis declares its unit of inference | `omission/CLAUDE.md` tripwire 4 ("State the unit of inference") |
| SC-003 Alignment as Semantic Labeling | alignment relabels time=0, never shifts timestamps | not restated verbatim in current doctrine — worth a spot-check if an alignment bug is ever suspected, since there is no current equivalent tripwire naming this explicitly |
| SC-004 Signal Class Preservation | SPK/MUAe/LFP stay distinct until an explicit fusion stage | `omission/CLAUDE.md` working agreement ("SPK/SUA, MUAe and LFP are never pooled") |
| SC-005 Trial Identity Preservation | trial identity never silently discarded | folds into the unit-of-inference tripwire (SC-002's current form) |
| SC-006 Session Provenance Traceability | every Dataset/Result/Figure traces to source Session(s) | `omission/CLAUDE.md` "Where truth lives" table + labyrinth evidence-graph requirement to record standing changes |

The five **software contracts** (SW-00X: public objects immutable via frozen dataclasses, purely
neuroscience-language API hiding numpy/scipy/matplotlib, no circular ownership, JSON
serializability, strict semver) describe mechanics of the abandoned `Query`/`Dataset` object
model specifically and have no current equivalent — `OmissionSession` was not built to those
specs and this document does not assert it satisfies them. Whether `OmissionSession` degrades on
any of these axes (mutability, backend leakage, serializability) has not been checked here; flag
as a possible future audit, not a current claim.

## Versioning plan (`04_versioning.md`) — disposition

A full semver policy (breaking vs. non-breaking change catalog, v1.0/v1.1/v2.0 timeline) was
written for the 13-object API's eventual freeze. Since that API never shipped as the public
interface, the versioning policy never took effect and is not current practice. Not reproduced
here beyond this note — it is pure process scaffolding for code that isn't load-bearing.

## Where the originals are

`legacy/docs/adr/ADR-001-immutable-datasets.md` and `legacy/docs/constitution/*.md` (01-04) were
removed from the tree 2026-08-22 after this consolidation — full text remains recoverable from
git history (`git log --follow -- omission/legacy/docs/constitution/01_ontology.md` etc.). This
document is now the sole current authoritative summary of that design effort.
