# 00 — Paradigm and Task

Generated 2026-08-17. This document is the rapid-access reference for the experimental
paradigm itself. It draws on `omission/jnwb_ext/session.py`, `omission/jnwb_ext/sequence_layout.py`,
`context/analysis_spec_SPK.md`, and `context/figures/fig01_recording_topology_and_paradigm/`
(the canonical topology-and-paradigm figure — read that figure directly for the visual
reference this document only describes in words).

## What the task is

Multi-area laminar macaque electrophysiology during a **sequential visual omission task** (task
context string: `omission_glo_passive`). A trial presents a sequence of four stimulus/delay
slots; on some trial types one slot is replaced by an **omission** — the expected stimulus does
not appear — probing whether and where the brain represents a prediction that was violated.
Recordings are multi-area, multi-probe, laminar (per-channel depth-resolved via vFLIP2 — see
doc01), across 3 subjects and 22 sessions (see doc01 for the current corpus).

## Trial timing (canonical, ms relative to P1 onset)

Source of truth: `omission.jnwb_ext.sequence_layout.EPOCH_ONSETS_MS`, cross-confirmed by
`OmissionSession.get_epochs`'s own documented "CRITICAL PARADIGM TIMING INVARIANT."

| Epoch | Onset (ms) | `stimulus_number` (phase) |
|---|---|---|
| fx (fixation baseline) | −500 | 1 |
| p1 (Presentation 1) | 0 | 2 |
| d1 (Delay 1) | 531 | — |
| p2 (Presentation 2) | 1031 | 3 |
| d2 (Delay 2) | 1562 | — |
| p3 (Presentation 3) | 2062 | 4 |
| d3 (Delay 3) | 2593 | — |
| p4 (Presentation 4) | 3093 | 5 |
| d4 (Delay 4) | 3624 | — |
| full sequence end | 4124 | — |

Full trial span: −500…4124 ms (4624 ms total). Presentation duration `STIM_MS=531`, delay
duration `DELAY_MS=500`, slot period `SLOT_PERIOD_MS=1031`. **d4's end boundary is variable/
clipped** — excluded from S1's null-epoch sampling pool for exactly this reason (doc03).

`get_epochs(phase=2, ...)` / `get_trial_onsets()` guarantee **P1-aligned** onsets — this is the
canonical trial-alignment convention used everywhere in the codebase; always prefer it over
hand-computing an onset from a raw NWB timestamp.

## Condition grammar

Trials are labelled by 4-letter codes over the alphabet `{A, B, X, R}` — one letter per
presentation slot (P1–P4):

- **A / B** — two structured stimulus identities. `AAAB` and `BBBA` are the **structured
  standard trials** (not random controls — a precision the `manuscript` skill flags explicitly:
  AAAB is structured, not a baseline "random" condition).
- **X** — an **omission** at that slot (expected stimulus replaced by nothing).
- **R** — a **random-control** identity, used in the R-family conditions (`RRRR`, `RXRR`,
  `RRXR`, `RRRX`) that provide the matched, non-structured comparison for omission-responsive
  units — this is the population the O+/O++ template-correlation and Q1 methods draw their
  R-family robustness checks from (doc03).

### Full 12-condition-family table (C31o/V198o — the "default" map)

Source: `omission.jnwb_ext.session.CONDITION_MAP_DEFAULT` (see doc01 for the full numeric crosswalk and the
V182o-specific contiguous variant, `CONDITION_MAP_V182O`). Families: `AAAB`/`AXAB`/`AAXB`/`AAAX`
(A-anchored structured + single-slot omissions), `BBBA`/`BXBA`/`BBXA`/`BBBX` (B-anchored mirror
set), `RRRR`/`RXRR`/`RRXR`/`RRRX` (random-control anchor + matched single-slot omissions).
**Condition-number-to-family mapping is subject-specific** — V182o's RRXR/RRRX slot assignment
is a contiguous split (35-42/43-50), confirmed different from the interleaved default used by
C31o/V198o (confirmed 2026-07-30, V182o's mapping supplied directly by Hamm since automatic
re-derivation from `is_omission` was inconclusive for that subject — see doc01). Always resolve
via `condition_map_for_stem(stem)`, never hardcode a condition number.

## Subjects

Three macaques, aliased by Hamm (2026-08-16/17): **C31o = Cajal, V182o = Ivan, V198o = Joule**.
All three in scope for every current analysis track. See doc01 for the full per-subject session/
unit breakdown and provenance of the alias mapping.

## Ten analysis areas

`V1, V2, V3a/d, V4, MT, MST, TEO, FST, FEF, PFC` — V3 subdivisions (V3a, V3d) pooled to a single
`V3a/d` label for analysis. See doc01 for per-area animal coverage and the confounding/
connectivity structure that governs what can be modeled across them (doc06).

## Unit response classes — the vocabulary, not the classifier

The class names **S+, S−, O+, O++** (and their extended siblings S++/S−−/O−/O−−) name response
*types*, not one fixed *test*. **This project has at least four methodologically distinct ways
to assign these labels to a unit**, each producing different counts on overlapping populations —
see [03_classification_pipelines.md](03_classification_pipelines.md) for the full accounting
before citing any class-membership count. In brief:

- **S+** — stimulus-present excitation (fires more during a real stimulus presentation than
  during fixation baseline).
- **S−** — stimulus-present suppression (fires less).
- **O+** — omission-responsive (fires differently during an omitted slot than expected).
- **O++** — a stricter/more-validated tier of O+, defined differently by each of the four
  generations in doc03.
- **S++/S−−/O−/O−−** — stricter or opposite-direction tiers used by specific generations, not
  universal across all four methods.

## Correct-trials-only convention

Per CLAUDE.md's working agreements: **correct trials only, by default**, everywhere in this
project. `get_epochs(correct_only=True)` is the default and should stay the default unless a
specific analysis explicitly needs incorrect trials (e.g. a behavioral-error control) and says
so.

## Where to go next

- Data topology, corpus counts, per-probe/per-area layout: [01_data_topology_and_corpus.md](01_data_topology_and_corpus.md)
- The `jnwb` package surface: [02_jnwb_api_reference.md](02_jnwb_api_reference.md)
- Unit response classification, all four generations: [03_classification_pipelines.md](03_classification_pipelines.md)
- TFR/LFP/connectivity: [04_signal_processing_tfr_lfp.md](04_signal_processing_tfr_lfp.md)
- The figure pipeline and current manuscript figure status: [05_figures_and_pipelines.md](05_figures_and_pipelines.md)
- Statistical rules for this corpus: [06_statistics_and_inference.md](06_statistics_and_inference.md)
- Skills and memory: [07_skills_and_memory_index.md](07_skills_and_memory_index.md)
- Current scientific state, blocked items, open questions: [08_project_state_and_open_items.md](08_project_state_and_open_items.md)
- Flagged conflicts and this audit's decisions: [09_conflicts_and_flagged_discrepancies.md](09_conflicts_and_flagged_discrepancies.md)
