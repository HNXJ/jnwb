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

## What actually happened (checked against the current tree, 2026-08-22 — corrected same day)

**CORRECTION (2026-08-22, later same day):** this section originally claimed the ontology was
"never adopted... zero matches anywhere in jnwb/ or omission/." That claim was **false** and has
been replaced below. The error: the Batch-1 `legacy/tests/` audit found zero matches for
`SessionManifest`/`SignalBlock`/`DataLoader` — a *different*, genuinely dead architecture
(`src.analysis.contracts`, referenced only by the deleted `legacy/tests/` fossils) — and that
finding was wrongly generalized to the `Query`/`Dataset`/`EpochCollection` ontology described in
this document, without independently checking `jnwb/__init__.py` or `jnwb/ontology.py`
themselves. Caught during Batch 2 when `jnwb/__init__.py` turned out to import and export
`Query`, `Dataset`, `AlignedDataset`, `Alignment`, `EpochCollection`, `Question`, `Result`,
`Interpretation`, `Figure`, `Provenance`, `Lineage` from `.ontology` directly, under "Core
ontology objects (immutable, stable)" in `__all__` — the opposite of dead code. `jnwb/ontology.py`
is dated the same day as this design effort (2026-06-25) and was touched as recently as the
commit immediately preceding this normalization work (`5505211 fix(jnwb): resolve ontology.py
NotImplementedError stubs`).

**The accurate picture: built, exported, tested — but with zero production callers.**
`jnwb/ontology.py` implements the 13-object model for real (not stubs, as of the just-mentioned
fix commit). `omission/jnwb_ext/factories.py` (670 lines, live, non-legacy) bridges it to
`OmissionSession` — e.g. `dataset_from_session(session, query)` builds a `Dataset` by reading
`session.get_units()` and filtering by `Query.areas`/`Query.units`. `omission/tests/test_factories.py`
exercises two of those factory functions directly, and its docstring records a real, fixed bug:
`result_from_decoding_analysis`/`result_from_tfr_analysis` previously fabricated statistics via
`np.random` regardless of whether real data was available; the test now locks in that both must
return `'insufficient_data'` rather than fabricated numbers when real computation isn't possible.
That is active, serious maintenance — not an abandoned corner.

What genuinely has zero current callers: **every place that actually *instantiates* `Query(...)`
outside `jnwb/ontology.py` itself, `omission/jnwb_ext/factories.py`, and
`omission/tests/test_factories.py` is in `omission/legacy/examples/*.py`** (already-legacy,
already-flagged example scripts). No script under `omission/scripts/`, no figure-generation code,
and no analysis pipeline constructs a `Query`, calls `dataset_from_session`, or calls
`.answer(question)` for a real result. `01_ontology.md`'s own stated plan — "OmissionSession is
deprecated in favor of Query -> Dataset -> Question -> Result" in v1.0 — has not happened: real
analysis work still goes through `OmissionSession` directly, everywhere. The ontology is a live,
tested, bridged parallel API with no production adoption yet, not dead code and not the primary
interface either — a third state distinct from both.

**Why this matters for reorganization:** `jnwb/ontology.py` + `omission/jnwb_ext/factories.py`
are exactly the kind of load-bearing-looking-but-actually-unused surface the "canonicalize
semantics before reorganizing" principle exists to catch. Neither is a Batch-2 target (frozen
`jnwb/`; `factories.py` isn't part of the 259-script analysis surface), but any future decision
to promote `jnwb_ext` code or prune "unused" surface must check real call sites first — this
correction is itself the receipt for why.

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
serializability, strict semver) describe mechanics of the `Query`/`Dataset` object model
specifically. `jnwb/ontology.py`'s dataclasses are genuinely `@dataclass(frozen=True)` (SW-001
holds for the ontology itself), but the contracts were written as if the ontology were the
*only* public interface — they say nothing about `OmissionSession`, which is not built to those
specs (its methods mutate, return heterogeneous dict shapes, and expose numpy/matplotlib
directly) and is not asserted here to satisfy them. Since `OmissionSession` remains the actual
production interface (see above), these contracts currently constrain a real but low-traffic
part of the public surface, not the part analysis work actually goes through.

## Versioning plan (`04_versioning.md`) — disposition

A full semver policy (breaking vs. non-breaking change catalog, v1.0/v1.1/v2.0 timeline) was
written for the 13-object API's eventual freeze, on the premise that it would become *the*
public interface at v1.0 with `OmissionSession` deprecated. Since that deprecation never
happened and the ontology never became the primary interface (see above), the versioning
policy's premise didn't materialize and it is not current practice — even though the ontology
classes it was written for do exist and are exported. Not reproduced here beyond this note; it
is process scaffolding for a migration that stalled, not a currently-enforced policy.

## Where the originals are

`legacy/docs/adr/ADR-001-immutable-datasets.md` and `legacy/docs/constitution/*.md` (01-04) were
removed from the tree 2026-08-22 after this consolidation — full text remains recoverable from
git history (`git log --follow -- omission/legacy/docs/constitution/01_ontology.md` etc.). This
document is now the sole current authoritative summary of that design effort.
