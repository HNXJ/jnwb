# CLAUDE.md — Omission (project doctrine)

Multi-area laminar macaque electrophysiology during a sequential visual omission task,
analysed with the `jnwb` library (repo root) via this project's `omission` package. Manuscripts
are lettered `omission-a`, `-b`, … — each a distinct paper. Address the user as **Hamm**; assume
domain fluency.

This file is project doctrine, scoped to `omission/`. Library-level invariants live in the repo
root [`CLAUDE.md`](../CLAUDE.md) — read both.

## Where truth lives

| Question | Source | Never |
|---|---|---|
| What data exists, where, how much | `omission/scripts/discover_corpus.py` → `omission/artifacts/data/corpus_manifest.json` | a path or count remembered from any document, including this one |
| What is scientifically established, superseded, blocked | `omission/context/PROJECT_STATE.md` | prose in a doctrine file |
| How a claim earns its standing | `omission/context/EVIDENCE_ARCHITECTURE.md` | narrative consistency |
| What was actually computed | the receipt named beside the number | a summary of it |

**No absolute data path or corpus count appears in this file, by design.** Both have drifted
before and both are discoverable.

**Truth precedence when sources disagree**: a receipt (the artifact a script actually wrote,
named beside the number) outranks the current project state (`PROJECT_STATE.md`), which
outranks narrative memory (anything recalled from a prior turn, a skill's prose, or this file).
Re-derive from the higher-precedence source rather than trusting the lower one's summary of it.

## Tripwires

These fire when you do not know you are in the domain. Everything else is in a skill.

1. **No empirical value in any output that no script computed from data.** Hardcoded values
   are permitted only for visual/task constants or output explicitly marked synthetic.
2. **Any figure or panel containing placeholder, synthetic, or fallback content renders an
   unmissable red `PLACEHOLDER-DUMMY` title.** Per-panel scope escalates to the whole figure.
3. **Take the logarithm last.** Average power, divide by baseline, `10·log10` once. Never
   average decibels. Averaging dB biases each site by its own noisiness and has flipped a
   subject's sign on this corpus.
4. **State the unit of inference.** Channels within a shank and trials within a session are
   not independent. Say which level carries the replication before reporting any p-value.
5. **Apply the denominator before claiming enrichment.** Raw counts follow recording effort.
6. **Check whether a selection criterion contains the conclusion** before interpreting a
   group's composition.
7. **Check whether a test is one- or two-sided** before reporting an absence of an effect.
8. **Check whether a column is constant** before interpreting it.
9. **Diff a same-named column on the overlap** before joining two tables on it. Same name is
   not the same field.
10. **A valid null is a result.** Report it. Redesign is justified by a broken estimand, leakage,
    a failed assumption, or prospectively identified low power — never by `p ≥ α` alone.
11. **Prevalence, magnitude, information, and mechanism are different estimands.** "How many
    units show X" answers none of "how large is X," "how much can be decoded from X," or "what
    causes X." Name which one a result answers before comparing it to another result or to a
    hypothesis.
12. **Association, directionality, and causality are different claims.** A correlation, a
    Granger/PSI/transfer-entropy directional estimate, and a causal mechanism require
    progressively stronger designs — do not let a stronger-sounding word describe a
    weaker-designed result.

## Stop conditions (project)

Stop and surface rather than choose:

- corpus counts or paths disagree between the manifest, a readiness table, and the filesystem;
- a readiness gate reports zero eligible sessions while the artifacts it gates exist on disk;
- a figure's source table is marked confounded or blocked in `PROJECT_STATE.md`;
- an area, band, window, or signal class is about to be pooled across a boundary
  `PROJECT_STATE.md` marks as an assumption rather than a measurement.

## Working agreements

- Correct trials only, by default.
- SPK/SUA, MUAe, LFP, and behavior are never pooled across modality. Session, area, layer,
  probe and unit namespaces are preserved throughout.
- Results go under `omission/context/figures/`.
- Preserve originals; write revisions as new files.
- Record evidence in `omission/artifacts/.lab/` when a claim's standing changes — not on turn
  cadence.
- Do not commit or push unless asked.

## Structural freeze + analysis-only (2026-08-24)

`omission/`'s top-level structure was reorganized 2026-08-24 (doc/handoff consolidation only —
`context/figures/` and `scripts/`'s internal layouts were explicitly left untouched: the former
is protected concurrent work, the latter has a repo-wide `parents[N]` path-resolution dependency
that a depth change would silently break; see `scripts/README.md`). **Structure is now frozen**:
do not move, rename, or restructure directories under `omission/` without a concrete defect that
requires it. The private controlling goal for this phase is
[`context/ANALYSIS_GOAL.md`](context/ANALYSIS_GOAL.md) (gitignored — not public doctrine).

**ANALYSIS ONLY.** Allowed: inspect data, run analyses, write/refactor analysis code, use
`jnwb`, generate deterministic products, statistics, controls, figures, receipts,
analysis-specific context updates, tests required by analysis. Not allowed unless directly
required to make an analysis correct: repo-wide normalization, general cleanup, broad API
redesign, unrelated `jnwb` promotion, legacy cleanup, further directory reorganization,
documentation gardening, style-only refactors. When an unrelated defect is discovered:

```python
if defect_blocks_or_invalidates_analysis:
    make_smallest_verified_fix()
else:
    record_debt()
    continue_analysis()
```

## Skills

Load the skill before doing the work; do not reinvent its contents.
`omission-data` · `omission-signal` · `omission-spiking` · `omission-statistics` ·
`omission-figures` · `manuscript` · `labyrinth` · `numerical-computing` ·
`biophysical-modeling`
