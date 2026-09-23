# Planned work after 0.2.6

Ruled by Hamm on 2026-09-22. Not part of the 0.2.6 stack, which stays closed to architecture
expansion: 0.2.6 repairs the established skill defects (P-61, P-62, P-99, P-53, P-42, P-181 and
the `t0_bounds` example in `skills/jnwb-spiking/SKILL.md`), checks routing rows against live
behaviour (06-24) and tests decline behaviour (06-25, kept in 0.2.6 by ruling R-2). Everything
below is authorized input to the 0.2.7 cycle, which reproduces each item against its own tree when
it opens its stack.

The rulings themselves are durable and live in `artifacts/fact_stack.md` under "Skill creation is
capability-gated" and "NWB mutation and execution infrastructure belong in the core". This file
holds the sequence, not the rules.

## Step 1. Common skill architecture

- One compact template for every `SKILL.md`: trigger, routing table, invariants, one worked
  example, verification. The template and its checks are defined in `CONTRIBUTING.md`.
- `skills/jnwb` routes to the minimal skill set a task needs instead of matching keywords. Plotting
  supplied arrays reaches `jnwb-figures` and `jnwb-qc`; comparing a band between two conditions
  reaches paradigm, NWB data, spectral, statistics, figures and QC.
- An analysis preflight before substantial work: goal, data, paradigm, signals, units, axes,
  conditions, inferential unit, missing information, required skills, verification plan. It ends
  in one of the four outcomes of `artifacts/direction.md`.
- Adversarial composition tests where two correct operations compose into a wrong result. The
  four-outcome routing tests land in 0.2.6 as 06-25.

## Step 2. Coverage

- `jnwb-paradigm`: experiment structure, timing and condition semantics over `events`,
  `EventTable`, `resolve_interval_table`, `EpochCollection`, `epoch_continuous` and
  `detect_trial_cycles`. Condition meaning is resolved from explicit metadata first and structural
  inference last, and an undocumented code is reported, never named. Depends on the 06-67
  missingness ruling.
- `jnwb-qc`: independent scientific and output QC over `visual_qc`, `audit_units`,
  `audit_electrodes`, `Result`, `Provenance` and `Lineage`, split out of `jnwb-figures` so the skill
  that makes a figure is not the one that judges it.
- Route the public exports no skill names (P-63).
- Remove duplication from the existing skills rather than growing them.

## Carried by rulings of 2026-09-22

`artifacts/rulings/2026-09-22.md` holds each ruling.

- `compress_fp32`: `select=` becomes required; 0.2.6 ships the `FutureWarning` (06-13).
- `aggregate_to_db(how="mean_of_ratios")` delivered through an accumulator path that keeps
  per-trial ratios; 0.2.6 refuses it on trial-averaged input (P-114).
- `nested_cv_linear_svm` gains keyword-only `groups=` for grouped outer folds (P-122).

## Deferred from the 0.2.6 stack

Moved here on 2026-09-22. Each is `DEFERRED->0.2.7` under `AGENTS.md` §11, and 06-131 attacks
every deferral before 0.2.6 closes. The full item text is in `artifacts/todo_stack.md` at
`917352fe`.

| Item | Work | Row |
|---|---|---|
| 06-26 | Skill examples use real NWB or deterministic arrays, and a test executes every example block | none |
| 06-87 | One rule where order work is read: a loop nest is not evidence of the order it looks like | P-36 |
| 06-89 | Document the unit-to-layer composition from existing exports | P-20 |
| 06-90 | Enrichment that skips on an absent `peak_channel_id` says so | P-192 |
| 06-97 | A documented call site for `xflip` | P-55 residue |
| 06-110 | A type oracle for documented call shapes | P-167 |
| 06-112 | A `--check`-only gate over `artifacts/state.md` when it is present | none |

## Capability-gated

Each lands as API, documentation and tests first, or atomically with its skill. Neither skill is
a required endpoint.

- Public NWB mutation API (validate, write, transform, convert, structural repair, verified output),
  then `jnwb-data-engineering` if the surface warrants one.
- Public execution and cache API (device, precision, workers, content-addressed checkpoints), after
  numerical identity and performance evidence, then `jnwb-compute` only if the router cannot carry
  it.
