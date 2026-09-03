# CLAUDE.md — jnwb

Generic, dataset-agnostic NWB (Neurodata Without Borders) analysis library. Project-specific
doctrine (paradigms, corpus specifics, manuscript rules) lives under each project folder's own
`CLAUDE.md` — e.g. [`omission/CLAUDE.md`](omission/CLAUDE.md) for the `omission` example
project — and adds to, never overrides, what's here.

## Phase (2026-08-24): repository normalization closed, analysis phase active

Repository normalization ended 2026-08-24 by Hamm's explicit instruction. The repo-wide
no-commit freeze (originally declared 2026-08-19 → 2026-09-28) is **superseded**, not merely
suspended: its own commit history (`310a8ac`) carries no rationale beyond a scheduling pause, and
Hamm's 2026-08-24 instruction to begin scientific analysis is a newer, explicit instruction that
supersedes a project-level scheduling decision per this project's own precedence rule. Routine
commit/push activity may resume for analysis-phase work; nothing about this reinstates unrelated
normalization/cleanup work (see "Analysis-only" doctrine in `omission/CLAUDE.md`).

**The `jnwb/` freeze itself is unaffected and remains in force** — it was never justified by the
scheduling pause; it is justified by `omission` being `jnwb`'s primary dataset and test corpus.
`jnwb/` stays frozen and read-only. Do not edit, add to, or refactor anything under `jnwb/`
except in the rare case Hamm explicitly authorizes it for that specific change. Every
omission-track task (analyses, figures, scripts, evidence) works *through* the frozen API, never
by extending it. If a task seems to need a new `jnwb` function or a change to an existing one,
stop and say so rather than writing it.

All omission-related work — scripts, figures, evidence, tests, docs — stays inside `omission/`.

**The freeze is enforced, not just stated**: `tests/test_jnwb_frozen_boundary.py` asserts
`jnwb/` has zero omission/ imports beyond the one authorized exception (see tripwire 3 below),
that it stays lazy (function-body-local, not module-level), that `import jnwb` succeeds even with
omission/ blocked from `sys.path` entirely, and that every `jnwb.__all__` name actually resolves.
A change that breaks the freeze fails this test before it fails a human review.

**Still protected, unrelated to phase**: paths that were dirty/uncommitted as of 2026-08-22 —
pre-existing concurrent figure/script work under `omission/context/figures/` and
`omission/scripts/`, plus `omission-data/SKILL.md` — remain untouched by any Claude session:
do not move, stage, revert, stash, or commit them. This protection is not tied to the
normalization effort; it protects concurrent human work regardless of what phase this repo is in.

## Where truth lives

| Question | Source | Never |
|---|---|---|
| What is in the public API | `jnwb/__init__.py`'s `__all__` | a symbol list remembered from any document, including this one |
| What was actually computed | the receipt named beside the number | a summary of it |

## Tripwires

1. **No empirical value in any output that no script computed from data.** Hardcoded values
   are permitted only for visual/task constants or output explicitly marked synthetic.
2. **Take the logarithm last.** Average power, divide by baseline, `10·log10` once. Never
   average decibels — it biases each site by its own noisiness.
3. **`jnwb/` does not import from any project folder** (e.g. `omission/`). The dependency runs
   one way: projects depend on `jnwb`, never the reverse. **There are now zero exceptions** —
   do not add one without discussing the layering first. (`jrsa.py`'s former exception, a lazy
   import of `phase_slope_index`, was removed 2026-08-23 when `connectivity.py` promoted to
   `jnwb/connectivity.py`. `addressing.py`'s — a call-time import of
   `omission.jnwb_ext.sequence_layout.parse_probe_areas` — was removed 2026-09-03: an optional
   import made jnwb resolve probe areas differently depending on whether omission happened to
   be importable, so merely installing a project package changed which cortical area a unit was
   assigned to. Area-name canonicalization now lives in `addressing.py`. `DP` is deliberately
   *not* aliased to `V4`: that alias collapsed a `"DP/V4"` probe to `('V4','V4')`, and whether
   the two are one area is an anatomical question generic addressing does not decide.)

   The invariant this protects: **`jnwb` gives identical scientific behaviour whether a project
   package is installed or absent.** Installing one must never be the mechanism that keeps
   `jnwb` correct.
4. **Preserve module- and array-level invariants**: units, coordinate frames, timestamps,
   sample rates, 0- vs 1-indexing do not change silently across a `jnwb` function boundary.

## Working agreements

- Preserve originals; write revisions as new files.
- Do not commit or push unless asked.

## Skills

Load the skill before doing the work; do not reinvent its contents. See a project folder's own
`CLAUDE.md` for its task-scoped skills (e.g. `omission/CLAUDE.md`).
`numerical-computing` · `biophysical-modeling`
