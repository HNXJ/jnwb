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

## Stop conditions (project)

Stop and surface rather than choose:

- corpus counts or paths disagree between the manifest, a readiness table, and the filesystem;
- a readiness gate reports zero eligible sessions while the artifacts it gates exist on disk;
- a figure's source table is marked confounded or blocked in `PROJECT_STATE.md`;
- an area, band, window, or signal class is about to be pooled across a boundary
  `PROJECT_STATE.md` marks as an assumption rather than a measurement.

## Working agreements

- Correct trials only, by default.
- SPK/SUA, MUAe and LFP are never pooled. Session, area, layer, probe and unit namespaces are
  preserved throughout.
- Results go under `omission/context/figures/`.
- Preserve originals; write revisions as new files.
- Record evidence in `omission/artifacts/.lab/` when a claim's standing changes — not on turn
  cadence.
- Do not commit or push unless asked.

## Skills

Load the skill before doing the work; do not reinvent its contents.
`omission-data` · `omission-signal` · `omission-spiking` · `omission-statistics` ·
`omission-figures` · `manuscript` · `labyrinth` · `numerical-computing` ·
`biophysical-modeling`
