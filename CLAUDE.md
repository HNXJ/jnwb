# CLAUDE.md — jnwb

Generic, dataset-agnostic NWB (Neurodata Without Borders) analysis library. Project-specific
doctrine (paradigms, corpus specifics, manuscript rules) lives under each project folder's own
`CLAUDE.md` — e.g. [`omission/CLAUDE.md`](omission/CLAUDE.md) for the `omission` example
project — and adds to, never overrides, what's here.

## Freeze policy (2026-08-19)

`omission` is now `jnwb`'s major dataset, test corpus, and main reason for the library's
existence — not a peer project. Given that, **`jnwb/` is frozen and read-only from here
forward.** Do not edit, add to, or refactor anything under `jnwb/` except in the rare case Hamm
explicitly authorizes it for that specific change. Every other omission-track task (new
analyses, figures, scripts, evidence) works *through* the frozen API, never by extending it.
If a task seems to need a new `jnwb` function or a change to an existing one, stop and say so
rather than writing it — that is exactly the case requiring authorization first.

All omission-related work — scripts, figures, evidence, tests, docs — stays inside `omission/`.
That folder is expected to eventually move to `.gitignore` (kept locally, backed up outside git)
and be absorbed into `jnwb`'s examples/docs in reduced form; treat it as project-local, not as
part of the library's own tracked surface, even before that gitignore change actually lands.

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
   one way: projects depend on `jnwb`, never the reverse. A handful of narrow, documented
   exceptions exist today (lazy, call-time-only imports for optional cross-project delegation,
   e.g. in `addressing.py` and `jrsa.py`) — do not add more without discussing the layering
   first.
4. **Preserve module- and array-level invariants**: units, coordinate frames, timestamps,
   sample rates, 0- vs 1-indexing do not change silently across a `jnwb` function boundary.

## Working agreements

- Preserve originals; write revisions as new files.
- Do not commit or push unless asked.

## Skills

Load the skill before doing the work; do not reinvent its contents. See a project folder's own
`CLAUDE.md` for its task-scoped skills (e.g. `omission/CLAUDE.md`).
`numerical-computing` · `biophysical-modeling`
