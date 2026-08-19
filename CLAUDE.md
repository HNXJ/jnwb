# CLAUDE.md — jnwb

Generic, dataset-agnostic NWB (Neurodata Without Borders) analysis library. Project-specific
doctrine (paradigms, corpus specifics, manuscript rules) lives under each project folder's own
`CLAUDE.md` — e.g. [`omission/CLAUDE.md`](omission/CLAUDE.md) for the `omission` example
project — and adds to, never overrides, what's here.

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
